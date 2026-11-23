"""
Auto run batch: satu putaran penuh BO berulang N kali, tanpa menunggu pengguna di antara langkah.

  py main.py autorun --batches 5 --qc --train --project cst_projects\\MicrostripAntena_RO4350B.cst -- \\
      -q 5 --kernel rbf --restarts 5 --focus bw --constraint "gain_fr_ieee_dbi>=4.5" --region-auto 6:0.15

Semua yang ada setelah `--` diteruskan APA ADANYA ke `py main.py suggest` (GUI menyusunnya dengan fungsi yang sama
dengan tombol Suggest), jadi autorun tidak punya parser opsi BO sendiri dan hasil `suggest` identik dengan pemanggilan manual.

Urutan satu batch:
  (a) simulasi sampel yang menunggu (pending_lhs dari lhs_samples.csv, pending_bo dari bo_candidates.csv)
  (b) suggest (melatih GPR sendiri; langkah `train` di bawah hanya untuk memantau R2)
  (c) run pada bo_candidates.csv
  (d) periksa jumlah sampel bertambah
  (e) qc (opsional, --qc)
  (f) train (opsional, --train)
  (g) catat satu baris ke data/<RUN>/auto_run_log.csv

Berhenti bila: langkah gagal (kode 1), jumlah sampel tidak bertambah setelah simulasi (kode 3), parameter menempel batas rentang dengan
--bounds-check stop (kode 4, setelah batch itu dicatat; tidak dipakai pada batch terakhir), atau Ctrl+C (kode 130).
Pemeriksaan batas (--bounds-check warn|stop|off, bawaan warn): di akhir tiap batch, sebuah parameter dianggap menempel batas bila nilainya pada sampel terbaik,
atau pada separuh kandidat batch itu atau lebih, berada dalam --bounds-frac (bawaan 0,02) rentang efektif dari batas. Autorun TIDAK melebarkan rentang sendiri.
`run` melewati sampel yang sudah ada, jadi aman dihentikan lalu dimulai ulang: sampel yang menunggu diselesaikan di
langkah (a) batch berikutnya tanpa simulasi ganda. Nomor batch di log kumulatif; --batches N = N batch baru per pemanggilan.

Keluaran untuk GUI: baris `[autorun] {json}` (batch, of, step, done, total); baris `[autorun] teks` untuk manusia.
"""
import argparse
import csv
import json
import math
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, "main.py")
LOG_NAME = "auto_run_log.csv"
LOG_COLS = ["batch", "waktu", "n_sampel", "n_feasible", "nilai_terbaik", "id_terbaik", "n_baru", "durasi_detik"]
EXIT_FAIL, EXIT_NOGROW, EXIT_BOUND, EXIT_INT = 1, 3, 4, 130
_CUR = [None]                                   # anak proses yang sedang berjalan (untuk dimatikan saat Ctrl+C)


class Stop(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code, self.msg = code, msg


def say(msg):
    print(f"[autorun] {msg}", flush=True)


def progress(**kw):
    print("[autorun] " + json.dumps(kw, ensure_ascii=False), flush=True)


# ---------------------------------------------------------------- anak proses
def kill_tree(proc):
    """Matikan proses beserta anaknya (Windows: taskkill /T; lainnya: grup sesi)."""
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def spawn(argv, tick=None, poll=20.0):
    """Jalankan argv, teruskan keluarannya per baris, panggil tick() tiap `poll` detik. Kembalikan kode keluar."""
    kw = {} if sys.platform == "win32" else {"start_new_session": True}
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", env=env, **kw)
    _CUR[0] = proc
    q = queue.Queue()

    def pump():
        for line in proc.stdout:
            q.put(line.rstrip("\r\n"))
        q.put(None)

    threading.Thread(target=pump, daemon=True).start()
    wait, last = min(max(poll, 0.05), 1.0), time.time()      # tunggu pendek agar Ctrl+C cepat ditangani (juga di Windows)
    try:
        while True:
            try:
                item = q.get(timeout=wait)
            except queue.Empty:
                item = False
            if item is None:
                break
            if item is not False:
                print(item, flush=True)
            if tick and time.time() - last >= poll:
                tick()
                last = time.time()
        rc = proc.wait()
        if tick:
            tick()
        return rc
    finally:
        kill_tree(proc)                                      # no-op bila sudah selesai; mematikan anak saat Ctrl+C
        _CUR[0] = None


def main_cmd(cmd, args):
    return [sys.executable, "-u", MAIN, cmd] + list(args)


# ---------------------------------------------------------------- keadaan proyek
def summary(design):
    from cstopt import status
    return status.summary(design)


def count_rows(path):
    from cstopt import status
    return len(set(status._csv_ids(path, "sample_id")))     # ringan, tanpa pandas (dipakai untuk progres)


class Ctx:
    def __init__(self, args, sug_args):
        self.a, self.sug = args, sug_args
        self.k = self.i = 0                                  # nomor batch di log dan urutan dalam pemanggilan ini
        self.n = args.batches

    def run_argv(self, samples):
        if self.a.run_script:                                # pengganti uji (tools/mock_run.py), tanpa CST
            return [sys.executable, "-u", self.a.run_script, "--design", self.a.design, "--samples", samples]
        extra = ["--project", self.a.project] if self.a.project else []
        return main_cmd("run", ["--samples", samples, "--auto-yes"] + extra)

    def design_args(self):
        return ["--design", self.a.design] if self.a.design else []


def simulate(ctx, samples, n_expected, label):
    """Jalankan `run` pada berkas sampel, lalu pastikan jumlah sampel bertambah."""
    s = summary(ctx.a.design)
    n_before, ds = s.get("n_samples", 0), s["files"]["dataset"]["path"]
    rows_before = count_rows(ds)

    def tick():
        progress(batch=ctx.i, of=ctx.n, step=label, done=max(0, count_rows(ds) - rows_before), total=n_expected)

    tick()
    rc = spawn(ctx.run_argv(samples), tick=tick, poll=ctx.a.poll)
    if rc != 0:
        raise Stop(EXIT_FAIL, f"run gagal (kode {rc}) pada batch {ctx.k}; hasil yang sudah selesai tersimpan, bisa dilanjutkan")
    n_after = summary(ctx.a.design).get("n_samples", 0)
    if n_after <= n_before:
        raise Stop(EXIT_NOGROW, f"jumlah sampel tidak bertambah setelah simulasi ({n_before} ke {n_after}); "
                                f"periksa CST dan {samples}")
    say(f"simulasi selesai: sampel {n_before} ke {n_after}")


def bound_check(ctx, s, cand_path):
    """{(parameter, 'atas'|'bawah'): [alasan]} untuk parameter yang menempel batas rentang efektif pada sampel terbaik atau pada separuh kandidat batch ini atau lebih."""
    try:
        import pandas as pd
        from cstopt.ml import core as mc
        d = mc.load_design(ctx.a.design)
        frac = ctx.a.bounds_frac
        df = pd.read_csv(s["files"]["dataset"]["path"])
        bid = (s.get("best") or {}).get("sample_id")
        row = df[df["sample_id"] == bid].iloc[0] if bid is not None and (df["sample_id"] == bid).any() else None
        cand = pd.read_csv(cand_path) if os.path.exists(cand_path) else None
        hits = {}
        for p, lo, hi in zip(d.params, d.lo, d.hi):
            rng = float(hi - lo)
            if not rng > 0:
                continue

            def side(v):
                return "atas" if v >= hi - frac * rng else ("bawah" if v <= lo + frac * rng else None)
            if row is not None and p in row.index:
                sd = side(float(row[p]))
                if sd:
                    hits.setdefault((p, sd), []).append(f"sampel terbaik {int(bid)} = {float(row[p]):.3f}")
            if cand is not None and p in cand.columns and len(cand):
                for sd in ("atas", "bawah"):
                    n = sum(1 for v in cand[p] if side(float(v)) == sd)
                    if n >= max(1, math.ceil(len(cand) / 2)):
                        hits.setdefault((p, sd), []).append(f"{n} dari {len(cand)} kandidat batch ini")
        return hits
    except Exception as e:                              # noqa: BLE001  (pemeriksaan tambahan tidak boleh menghentikan autorun)
        say(f"pemeriksaan batas dilewati ({type(e).__name__}: {e})")
        return {}


def one_batch(ctx):
    t0 = time.time()
    s = summary(ctx.a.design)
    start_n = s.get("n_samples", 0)
    lhs_path, cand_path = s["files"]["lhs_samples"]["path"], s["files"]["bo_candidates"]["path"]
    say(f"batch {ctx.i}/{ctx.n} (nomor log {ctx.k}) mulai: {start_n} sampel, menunggu LHS {s['pending_lhs']}, BO {s['pending_bo']}")
    # (a) sampel yang menunggu
    if s["pending_lhs"] > 0:
        simulate(ctx, lhs_path, s["pending_lhs"], "simulasi")
    if s["pending_bo"] > 0 and os.path.exists(cand_path):
        simulate(ctx, cand_path, s["pending_bo"], "simulasi")
    # (b) suggest
    progress(batch=ctx.i, of=ctx.n, step="suggest")
    rc = spawn(main_cmd("suggest", ctx.sug))
    if rc != 0:
        raise Stop(EXIT_FAIL, f"suggest gagal (kode {rc})")
    s = summary(ctx.a.design)
    if s["pending_bo"] <= 0:
        raise Stop(EXIT_NOGROW, "suggest tidak menghasilkan kandidat yang belum disimulasikan")
    # (c) dan (d) simulasi kandidat, periksa jumlah sampel bertambah
    simulate(ctx, cand_path, s["pending_bo"], "simulasi")
    # (e) qc, (f) train
    if ctx.a.qc:
        progress(batch=ctx.i, of=ctx.n, step="qc")
        rc = spawn(main_cmd("qc", ctx.design_args()))
        if rc != 0:
            raise Stop(EXIT_FAIL, f"qc gagal (kode {rc}); periksa data sebelum melanjutkan")
    if ctx.a.train:
        progress(batch=ctx.i, of=ctx.n, step="train")
        rc = spawn(main_cmd("train", ctx.design_args() + ["--restarts", str(ctx.a.train_restarts)]))
        if rc != 0:
            raise Stop(EXIT_FAIL, f"train gagal (kode {rc})")
    # (g) catat
    s = summary(ctx.a.design)
    best = s.get("best") or {}
    row = {"batch": ctx.k, "waktu": datetime.now().isoformat(timespec="seconds"), "n_sampel": s.get("n_samples", 0),
           "n_feasible": s.get("n_feasible", 0), "nilai_terbaik": best.get("value", ""),
           "id_terbaik": best.get("sample_id", ""), "n_baru": s.get("n_samples", 0) - start_n,
           "durasi_detik": round(time.time() - t0)}
    write_log(s["run_dir"], row)
    progress(batch=ctx.i, of=ctx.n, step="selesai", n_sampel=row["n_sampel"], n_feasible=row["n_feasible"],
             nilai_terbaik=row["nilai_terbaik"])
    say(f"batch {ctx.i}/{ctx.n} selesai: {row['n_sampel']} sampel ({row['n_baru']} baru), feasible {row['n_feasible']}, "
        f"terbaik {row['nilai_terbaik']} (id {row['id_terbaik']}); dicatat di {os.path.join(s['run_dir'], LOG_NAME)}")
    if ctx.a.bounds_check != "off":
        hits = bound_check(ctx, s, cand_path)
        if hits:
            names = sorted({p for p, _ in hits})
            detail = "; ".join(f"{p} di batas {sd} ({', '.join(why)})" for (p, sd), why in sorted(hits.items()))
            progress(batch=ctx.i, of=ctx.n, step="batas", params=names)
            say(f"PERINGATAN batas rentang: {detail}. Optimum mungkin dibatasi rentang; pertimbangkan melebarkan lewat `py main.py bounds` "
                "atau dialog Rentang parameter, lalu lanjutkan.")
            if ctx.a.bounds_check == "stop" and ctx.i < ctx.n:
                raise Stop(EXIT_BOUND, f"parameter menempel batas rentang ({', '.join(names)}) setelah batch {ctx.k}; lebarkan rentang lalu jalankan autorun lagi, "
                                       "atau pakai --bounds-check warn")


# ---------------------------------------------------------------- log
def next_batch_no(run_dir):
    path = os.path.join(run_dir, LOG_NAME)
    last = 0
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                try:
                    last = max(last, int(r["batch"]))
                except (KeyError, TypeError, ValueError):
                    pass
    return last + 1


def write_log(run_dir, row):
    path = os.path.join(run_dir, LOG_NAME)
    new = not os.path.exists(path)
    os.makedirs(run_dir, exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LOG_COLS)
        if new:
            w.writeheader()
        w.writerow(row)


# ---------------------------------------------------------------- CLI
def split_argv(argv):
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1:]
    return argv, []


def suggest_q(sug):
    for i, x in enumerate(sug):
        if x in ("-q", "--q") and i + 1 < len(sug):
            try:
                return int(sug[i + 1])
            except ValueError:
                return 5
    return 5


def build_parser():
    ap = argparse.ArgumentParser(prog="main.py autorun", description="Auto run batch BO (lihat docstring cstopt/autorun.py).",
                                 epilog="Opsi suggest ditulis setelah `--`, mis.  autorun --batches 3 -- -q 5 --restarts 2 --pool 8192")
    ap.add_argument("--batches", "-n", type=int, default=3, help="jumlah batch baru pada pemanggilan ini")
    ap.add_argument("--design", default=None, help="nama file di designs/ (diteruskan ke suggest, qc, train)")
    ap.add_argument("--project", default=None, help="file .cst (diteruskan ke run; kosong = project yang terbuka di CST)")
    ap.add_argument("--qc", action="store_true", help="jalankan qc setelah tiap batch")
    ap.add_argument("--train", action="store_true", help="jalankan train setelah tiap batch (hanya memantau R2 dan parity)")
    ap.add_argument("--train-restarts", type=int, default=2, help="restarts untuk train pemantauan (bawaan 2)")
    ap.add_argument("--min-per-sample", type=float, default=5.0, help="perkiraan menit per sampel, hanya untuk estimasi")
    ap.add_argument("--dry-run", action="store_true", help="cetak rencana dan estimasi waktu, tanpa menjalankan apa pun")
    ap.add_argument("--bounds-check", choices=("warn", "stop", "off"), default="warn",
                    help="pemeriksaan parameter menempel batas rentang di akhir tiap batch: warn (bawaan), stop (kode 4), off")
    ap.add_argument("--bounds-frac", type=float, default=0.02, help="jarak ke batas (pecahan rentang efektif) yang dianggap menempel; bawaan 0,02")
    ap.add_argument("--run-script", default=None, help=argparse.SUPPRESS)      # uji: pakai tools/mock_run.py sebagai pengganti run
    ap.add_argument("--poll", type=float, default=20.0, help=argparse.SUPPRESS)  # detik antar pembaruan progres simulasi
    return ap


def main():
    own, sug = split_argv(sys.argv[1:])
    ap = build_parser()
    a = ap.parse_args(own)
    if sug and sug[0] == "suggest":
        sug = sug[1:]
    if a.batches < 1 or a.batches > 999:
        ap.error("--batches harus 1 sampai 999")
    if not 0.0 < a.bounds_frac <= 1.0:
        ap.error("--bounds-frac harus lebih dari 0 dan paling besar 1")
    if "--report" in sug:
        ap.error("--report bukan opsi untuk autorun (suggest --report tidak membuat kandidat)")
    if "--design" in sug:
        i = sug.index("--design")
        a.design = a.design or (sug[i + 1] if i + 1 < len(sug) else None)
    elif a.design:
        sug = sug + ["--design", a.design]
    if a.run_script and not a.design:
        ap.error("--run-script butuh --design")
    ctx = Ctx(a, sug)

    s = summary(a.design)
    if "error" in s:
        print(f"[error] data tidak bisa dimuat: {s['error']}")
        return 2
    q = suggest_q(sug)
    pend = s.get("pending_lhs", 0) + s.get("pending_bo", 0)
    mins = (a.batches * q + pend) * a.min_per_sample
    say(f"desain {s['design']} (run {s['run']}), {s.get('n_samples', 0)} sampel, menunggu LHS {s.get('pending_lhs', 0)} dan BO {s.get('pending_bo', 0)}")
    say(f"rencana: {a.batches} batch x q {q}; suggest: {' '.join(sug) or '(bawaan)'}; qc {'ya' if a.qc else 'tidak'}; train {'ya' if a.train else 'tidak'}; periksa batas rentang: {a.bounds_check}")
    say(f"estimasi simulasi: ({a.batches} x {q} + {pend} menunggu) x {a.min_per_sample:g} menit = {mins:.0f} menit "
        f"(sekitar {mins / 60:.1f} jam), belum termasuk suggest, qc, train")
    if a.dry_run:
        return 0
    try:
        first = next_batch_no(s["run_dir"])
        for i in range(1, a.batches + 1):
            ctx.i, ctx.k = i, first + i - 1
            one_batch(ctx)
    except Stop as e:
        say(f"BERHENTI: {e.msg}")
        progress(step="berhenti", kode=e.code)
        return e.code
    except KeyboardInterrupt:
        kill_tree(_CUR[0])
        say("dihentikan (Ctrl+C); jalankan lagi untuk melanjutkan, sampel yang sudah ada dilewati")
        progress(step="berhenti", kode=EXIT_INT)
        return EXIT_INT
    say(f"SELESAI: {a.batches} batch")
    progress(step="selesai_semua", batches=a.batches)
    return 0


if __name__ == "__main__":
    sys.exit(main())
