"""
Uji `py main.py autorun` tanpa CST (pengganti run = tools/mock_run.py, desain _demo_analytic, data di data/DemoAnalytic/).

  py tools/test_autorun.py [--keep]

Skenario: (1) dry-run tidak menjalankan apa pun; (2) 3 batch berjalan sampai selesai, log tercatat, sampel menunggu LHS
ikut diselesaikan; (3) suggest gagal -> berhenti kode 1; (4) run gagal -> kode 1; (5) simulasi tanpa menambah sampel -> kode 3;
(6) Ctrl+C (SIGINT) saat simulasi -> kode 130, lalu dimulai ulang tanpa simulasi ganda (dilewati di Windows).
Data nyata tidak tersentuh; folder data/DemoAnalytic dihapus di awal dan di akhir (kecuali --keep).
"""
import argparse
import csv
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cstopt import paths  # noqa: E402

DESIGN, RUN, PY = "_demo_analytic", "DemoAnalytic", sys.executable
MOCK = os.path.join(ROOT, "tools", "mock_run.py")
RD = paths.run_dir(RUN)
DATASET = os.path.join(RD, "batch_lhs.csv")
LOG = os.path.join(RD, "auto_run_log.csv")
SAMPLES = os.path.join(paths.samples_dir(RUN), "lhs_samples.csv")
SUG = ["-q", "3", "--restarts", "1", "--pool", "2048", "--seed", "0"]
fails = []


def check(name, cond, extra=""):
    print(f"  [{'OK' if cond else 'GAGAL'}] {name}" + (f"  ({extra})" if (extra and not cond) else ""))
    if not cond:
        fails.append(name)


def autorun(args, sug=SUG, extra_env=None, timeout=900):
    cmd = [PY, "-u", os.path.join(ROOT, "main.py"), "autorun", "--design", DESIGN, "--poll", "0.3"] + args + ["--"] + sug
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, env=dict(os.environ, PYTHONIOENCODING="utf-8"))


def rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def ids():
    return [r[list(r)[0]] for r in rows(DATASET)]


def mock(args):
    r = subprocess.run([PY, MOCK, "--design", DESIGN] + args, cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def fresh():
    shutil.rmtree(RD, ignore_errors=True)
    r = subprocess.run([PY, "main.py", "lhs", "--design", DESIGN, "-n", "20", "--seed", "1"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="autorun_")
    try:
        print("0. bound_check (unit, tanpa CST)")
        import types
        import numpy as np
        import pandas as pd
        from cstopt import autorun as au
        from cstopt.ml import core as mc

        class _D:                                                  # desain tiruan: rentang 0 sampai 10 untuk A, B, C
            params = ["A", "B", "C"]
            lo = np.array([0.0, 0.0, 0.0])
            hi = np.array([10.0, 10.0, 10.0])
        dsp, csp = os.path.join(tmp, "ds.csv"), os.path.join(tmp, "cand.csv")
        pd.DataFrame({"sample_id": [1, 2, 3], "A": [5.0, 9.99, 4.0], "B": [5.0, 5.0, 5.0], "C": [5.0, 5.0, 5.0]}).to_csv(dsp, index=False)
        pd.DataFrame({"sample_id": [4, 5, 6], "A": [5.0, 5.0, 5.0], "B": [0.1, 0.15, 5.0], "C": [9.9, 5.0, 5.0]}).to_csv(csp, index=False)
        s_fake = {"files": {"dataset": {"path": dsp}}, "best": {"sample_id": 2}}
        ctx0 = types.SimpleNamespace(a=types.SimpleNamespace(design=None, bounds_frac=0.02))
        real_ld, mc.load_design = mc.load_design, (lambda name=None: _D())
        try:
            h = au.bound_check(ctx0, s_fake, csp)
            check("A menempel batas atas pada sampel terbaik, B batas bawah pada 2 dari 3 kandidat, C (1 dari 3) tidak",
                  set(h) == {("A", "atas"), ("B", "bawah")}, str(h))
            check("alasan memuat sampel terbaik dan jumlah kandidat", "sampel terbaik 2" in h[("A", "atas")][0] and "2 dari 3 kandidat" in h[("B", "bawah")][0], str(h))
            check("tanpa sampel terbaik dan tanpa berkas kandidat: tidak ada temuan, tanpa galat",
                  au.bound_check(ctx0, {"files": {"dataset": {"path": dsp}}, "best": None}, os.path.join(tmp, "tidak_ada.csv")) == {})
            check("jarak 0,5 rentang: semua parameter dekat batas", len({p for p, _ in au.bound_check(types.SimpleNamespace(a=types.SimpleNamespace(design=None, bounds_frac=0.5)), s_fake, csp)}) == 3)
        finally:
            mc.load_design = real_ld

        print("1. dry-run")
        fresh()
        mock(["--samples", SAMPLES, "--limit", "12"])                     # 12 dari 20 sampel LHS disimulasikan, 8 menunggu
        r = autorun(["--batches", "2", "--dry-run"])
        check("dry-run kode 0", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])
        check("dry-run menyebut estimasi dan 8 sampel menunggu", "estimasi simulasi" in r.stdout and "menunggu LHS 8" in r.stdout)
        check("dry-run tidak menulis log atau sampel", not os.path.exists(LOG) and len(ids()) == 12)

        print("2. tiga batch sampai selesai (dengan 8 sampel LHS menunggu, qc dan train aktif)")
        r = autorun(["--batches", "3", "--run-script", MOCK, "--qc", "--train", "--train-restarts", "1"])
        check("kode 0", r.returncode == 0, (r.stdout + r.stderr)[-600:])
        lg = rows(LOG)
        check("log punya 3 baris, batch 1..3", [x["batch"] for x in lg] == ["1", "2", "3"], str(lg))
        check("sampel 20 lalu 23, 26, 29", [x["n_sampel"] for x in lg] == ["23", "26", "29"], str([x["n_sampel"] for x in lg]))
        check("n_baru batch 1 = 11 (8 menunggu + 3 BO), lainnya 3", [x["n_baru"] for x in lg] == ["11", "3", "3"], str([x["n_baru"] for x in lg]))
        check("kolom nilai terbaik dan feasible terisi", all(x["nilai_terbaik"] != "" and x["n_feasible"] != "" for x in lg))
        check("dataset 29 baris tanpa id ganda", len(ids()) == 29 and len(set(ids())) == 29)
        check("keluaran memuat progres JSON simulasi", '"step": "simulasi"' in r.stdout and '"step": "selesai"' in r.stdout)
        check("model hasil train ada", os.path.exists(os.path.join(RD, "models", "gpr_models.joblib")))
        n_ok, log_ok = len(ids()), len(lg)

        print("3. suggest gagal (kernel tidak dikenal)")
        r = autorun(["--batches", "2", "--run-script", MOCK], sug=["-q", "3", "--kernel", "bogus"])
        check("kode 1 dan pesan BERHENTI", r.returncode == 1 and "BERHENTI" in r.stdout, f"rc={r.returncode}")
        check("data dan log tidak berubah", len(ids()) == n_ok and len(rows(LOG)) == log_ok)

        print("4. run gagal (skrip simulasi tidak ada)")
        r = autorun(["--batches", "2", "--run-script", os.path.join(tmp, "tidak_ada.py")])
        check("kode 1 dan pesan run gagal", r.returncode == 1 and "run gagal" in r.stdout, f"rc={r.returncode}")
        check("log tidak bertambah", len(rows(LOG)) == log_ok)

        print("5. simulasi selesai tanpa menambah sampel")
        noop = os.path.join(tmp, "noop.py")
        open(noop, "w").write("import sys\nsys.exit(0)\n")
        r = autorun(["--batches", "1", "--run-script", noop])
        check("kode 3", r.returncode == 3, f"rc={r.returncode} " + r.stdout[-300:])
        check("pesan 'tidak bertambah'", "tidak bertambah" in r.stdout)
        check("log tidak bertambah", len(rows(LOG)) == log_ok)

        print("6. Ctrl+C lalu lanjut tanpa simulasi ganda")
        if sys.platform == "win32":
            print("  (dilewati di Windows: SIGINT ke proses anak tidak tersedia di uji ini; coba manual dengan Ctrl+C di terminal)")
        else:
            slow = os.path.join(tmp, "slow.py")
            open(slow, "w").write(
                "import subprocess, sys, time\n"
                f"subprocess.run([sys.executable, {MOCK!r}] + sys.argv[1:] + ['--limit', '1'], check=True)\n"
                "print('SLOW tidur', flush=True)\ntime.sleep(120)\n")
            n0 = len(ids())
            cmd = [PY, "-u", os.path.join(ROOT, "main.py"), "autorun", "--design", DESIGN, "--poll", "0.3", "--batches", "1",
                   "--run-script", slow, "--"] + SUG
            p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
            out, t0 = [], time.time()
            for line in p.stdout:
                out.append(line)
                if "SLOW tidur" in line:
                    p.send_signal(signal.SIGINT)
                    break
                if time.time() - t0 > 300:
                    p.kill()
                    break
            rest = p.communicate(timeout=60)[0]
            text = "".join(out) + rest
            check("Ctrl+C keluar kode 130", p.returncode == 130, f"rc={p.returncode} " + text[-300:])
            check("pesan dihentikan", "dihentikan" in text)
            n1 = len(ids())
            check("1 dari 3 kandidat sempat disimulasikan", n1 == n0 + 1, f"{n0} ke {n1}")
            check("log tidak bertambah", len(rows(LOG)) == log_ok)
            r = autorun(["--batches", "1", "--run-script", MOCK])
            check("mulai ulang kode 0", r.returncode == 0, (r.stdout + r.stderr)[-400:])
            lg = rows(LOG)
            check("log batch 4 dengan n_baru 5 (2 menunggu, lalu 3 baru) dari 1 yang sudah ada", len(lg) == log_ok + 1 and lg[-1]["batch"] == "4" and lg[-1]["n_baru"] == "5",
                  str(lg[-1:]))
            check("tanpa id ganda: total = awal + 1 + 5", len(ids()) == n0 + 6 and len(set(ids())) == n0 + 6, f"{len(ids())} baris, {len(set(ids()))} unik")
        print("7. pemeriksaan menempel batas (--bounds-frac 1.0 memaksa temuan)")
        n_log = len(rows(LOG))
        r = autorun(["--batches", "2", "--run-script", MOCK, "--bounds-check", "warn", "--bounds-frac", "1.0"])
        check("warn: selesai kode 0", r.returncode == 0, (r.stdout + r.stderr)[-300:])
        check("warn: peringatan tiap batch (2) dan progres JSON step batas", r.stdout.count("PERINGATAN batas rentang") == 2 and '"step": "batas"' in r.stdout)
        check("warn: dua batch dicatat", len(rows(LOG)) == n_log + 2)
        n_log = len(rows(LOG))
        r = autorun(["--batches", "3", "--run-script", MOCK, "--bounds-check", "stop", "--bounds-frac", "1.0"])
        check("stop: kode 4 setelah batch pertama", r.returncode == 4, f"rc={r.returncode} " + r.stdout[-300:])
        check("stop: pesan BERHENTI menyebut menempel batas dan hanya satu peringatan", "BERHENTI" in r.stdout and "menempel batas" in r.stdout and r.stdout.count("PERINGATAN batas rentang") == 1)
        check("stop: batch yang memicu tetap dicatat (satu baris)", len(rows(LOG)) == n_log + 1)
        n_log = len(rows(LOG))
        r = autorun(["--batches", "1", "--run-script", MOCK, "--bounds-check", "stop", "--bounds-frac", "1.0"])
        check("stop pada batch terakhir: tidak berhenti (kode 0) tetapi tetap memperingatkan", r.returncode == 0 and "PERINGATAN batas rentang" in r.stdout, f"rc={r.returncode}")
        r = autorun(["--batches", "1", "--run-script", MOCK, "--bounds-check", "off", "--bounds-frac", "1.0"])
        check("off: tanpa peringatan", r.returncode == 0 and "PERINGATAN" not in r.stdout and '"step": "batas"' not in r.stdout)
        r = autorun(["--batches", "1", "--run-script", MOCK, "--bounds-frac", "0"])
        check("--bounds-frac 0 ditolak (kode 2)", r.returncode == 2, f"rc={r.returncode}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if not a.keep:
            shutil.rmtree(RD, ignore_errors=True)
    print("\n" + ("SEMUA LULUS" if not fails else f"{len(fails)} pemeriksaan GAGAL: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
