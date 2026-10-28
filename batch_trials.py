"""
Menjalankan batch simulasi CST dari file sampel (export/lhs_samples.csv atau bo_candidates.csv),
lalu menyimpan semua hasil per project ke:  export/<nama_project>/batch_lhs.csv

Skrip ini memanggil objek VBA CST langsung dari Python lewat project.model3d
(StoreDoubleParameter, FarfieldPlot, ASCIIExport, dan seterusnya).

Untuk macro dengan monitor farfield multi-frekuensi (antena_uslot_dgs_dumbbell4.bas):
  per sampel diekspor farfield monitor 3,5 GHz DAN monitor yang paling dekat dengan frekuensi
  resonansi (fr), sehingga directivity dan gain tersedia di sekitar fr.

Keluaran per project (export/<nama_project>/):
  batch_lhs.csv   satu baris per sampel      curves/  kurva S11 per sampel
  eff/            kurva efisiensi per sampel  ff/      file farfield mentah per sampel

Prasyarat:
  - CST terbuka dengan project antena (hasil macro v4) dan project SUDAH DISIMPAN (.cst ada di disk)
  - export_dataset.py dan farfield_utils.py ada di folder yang sama dengan skrip ini
  - export/lhs_samples.csv sudah dibuat:  py lhs_maximin.py
  - file .cst yang dipakai harus SAMA dengan project yang aktif di CST. Skrip mencoba mendeteksinya
    sendiri; jika gagal, berikan --project "C:\\...\\MicrostripAntena.cst". Jika dua-duanya ada tetapi
    berbeda, skrip berhenti (mencegah hasil dari project lain ikut terbaca).

Pemakaian (urutan pengujian yang disarankan):
  py batch_trials.py --probe            cek koneksi, method, dan project yang terdeteksi
  py batch_trials.py --check-samples    validasi CSV sampel (tanpa CST)
  py batch_trials.py --check-monitors   periksa kurva efisiensi punya titik sebanyak monitor
                                        (jalankan setelah satu simulasi selesai dan project disimpan)
  py batch_trials.py --test-set         ganti parameter ke sampel pertama lalu kembalikan (tanpa solver)
  py batch_trials.py --test-export      ekspor farfield 3,5 GHz dan 3,0 GHz dari hasil yang ada
  py batch_trials.py --limit 2          jalankan 2 sampel pertama saja (uji penuh singkat)
  py batch_trials.py                    jalankan semua sampel di CSV
  py batch_trials.py --samples export/bo_candidates.csv --auto-yes     (iterasi BO)

Lanjut otomatis (resume): sampel yang kombinasi parameternya sudah ada di batch_lhs.csv dilewati.
"""
import argparse
import csv
import os
import subprocess
import sys
import time
from datetime import datetime

import numpy as np
import cst.interface
import cst.results

import export_dataset as ed
from farfield_utils import peak_over_files

EXPORT_DIR = ed.EXPORT_DIR
SAMPLES_CSV = os.path.join(EXPORT_DIR, "lhs_samples.csv")   # keluaran lhs_maximin.py
CSV_NAME = "batch_lhs.csv"

BASE = dict(Lp=20.22, Wp=26.33, LU=10.0, WU=10.5, gU=0.6, PU=2.0,
            LI=6.15, LD=3.0, WD=3.0, gD=0.3, PD=0.0)

REQUIRED = ["StoreDoubleParameter", "full_history_rebuild", "SelectTreeItem",
            "FarfieldPlot", "ASCIIExport", "run_solver"]


# ---------------------------------------------------------------- sampel LHS
def load_samples(path):
    """Baca CSV sampel. Kembalikan list (sample_id, dict parameter float)."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"File sampel tidak ditemukan: {path}\nJalankan dulu:  py lhs_maximin.py")
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [k for k in ed.PARAM_NAMES if k not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Kolom parameter tidak ada di {path}: {missing}")
        has_id = "sample_id" in reader.fieldnames
        samples = []
        for n, row in enumerate(reader, 1):
            try:
                params = {k: float(row[k]) for k in ed.PARAM_NAMES}
            except (TypeError, ValueError) as e:
                raise ValueError(f"Nilai tidak valid di baris data ke-{n} ({path}): {e}") from e
            sid = int(float(row["sample_id"])) if has_id else n
            samples.append((sid, params))
    if not samples:
        raise ValueError(f"Tidak ada sampel di {path}")
    return samples


def select_samples(samples, start, limit):
    """Pilih sampel mulai dari sample_id >= start, maksimal 'limit' sampel."""
    sel = [s for s in samples if s[0] >= start]
    return sel[:limit] if limit else sel


def done_keys(path):
    """Kunci parameter dari semua baris yang sudah ada di CSV hasil (untuk resume)."""
    keys = set()
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                try:
                    keys.add(tuple(round(float(row[k]), 6) for k in ed.PARAM_NAMES))
                except (KeyError, ValueError):
                    pass
    return keys


def prepare_out_csv(path):
    """Jika CSV hasil lama berformat beda, ganti namanya agar tidak tercampur."""
    if not os.path.exists(path):
        return
    with open(path, newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh), [])
    if header != ed.FIELDS:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = path.replace(".csv", f"_lama_{stamp}.csv")
        os.rename(path, new_name)
        print(f"Format CSV hasil lama berbeda, dipindah ke: {new_name}")


# ---------------------------------------------------------------- koneksi CST
def connect():
    de = cst.interface.DesignEnvironment.connect_to_any_or_new()
    prj = de.active_project()
    if prj is None:
        raise RuntimeError("Tidak ada project aktif di CST. Buka project antena dulu.")
    return de, prj


def check_api(m3d):
    names = set(n for n in dir(m3d) if not n.startswith("_"))
    missing = [n for n in REQUIRED if n not in names]
    if missing:
        print(f"Method yang dibutuhkan tidak ditemukan: {missing}")
        return False
    print("Semua method yang dibutuhkan tersedia.")
    return True


# ---------------------------------------------------------------- operasi CST
def set_params(m3d, params):
    for k, v in params.items():
        m3d.StoreDoubleParameter(k, float(v))
    m3d.full_history_rebuild()
    # baca balik sebagai bukti parameter masuk
    try:
        got = {k: float(m3d.RestoreDoubleParameter(k)) for k in params}
    except Exception as e:
        print(f"  [info] pembacaan balik parameter dilewati ({e})")
        return
    bad = {k: (params[k], got[k]) for k in params if abs(got[k] - float(params[k])) > 1e-9}
    if bad:
        raise RuntimeError(f"Parameter tidak sesuai setelah diset (diminta, terbaca): {bad}")
    print("  parameter terverifikasi (dibaca balik dari CST).")


def _short_err(e):
    """Ambil satu baris error yang informatif dari pesan CST yang panjang."""
    lines = [l.strip() for l in str(e).splitlines() if l.strip()]
    pick = [l for l in lines if l.upper().startswith("ERROR")]
    return pick[0] if pick else (lines[-1] if lines else "tidak diketahui")


def find_run(project, params):
    """Cari run di hasil CST yang parameternya SAMA dengan 'params'.
    Kembalikan (res, run_id) atau (res, None) bila belum ada hasil untuk kombinasi itu."""
    res = cst.results.ProjectFile(project, allow_interactive=True).get_3d()
    want = ed.param_key(params)
    ids = sorted(ed.get_run_ids(res), key=lambda i: (i != 0, i))     # coba run 0 dulu
    for rid in ids:
        try:
            if ed.param_key(ed.get_params(res, rid)) != want:
                continue
            ed.get_curve(res, ed.S11_PATH, rid)      # run harus benar-benar punya kurva S11
            return res, rid
        except Exception:
            continue                                  # run terdaftar tapi tanpa hasil: abaikan
    return res, None


def run_solver(m3d, project, params, had_before):
    try:
        m3d.run_solver()
    except RuntimeError as e:
        print(f"  run_solver melaporkan error ({_short_err(e)}).")
        if not had_before:
            # error kadang muncul SETELAH hasil selesai dihitung; cek apakah hasilnya sudah ada
            try:
                m3d.Save()
            except Exception:
                pass
            _, rid = find_run(project, params)
            if rid is not None:
                print(f"  hasil untuk parameter ini ternyata sudah terbentuk (run {rid}); "
                      "start_solver dilewati.")
                return
        print("  Memakai start_solver ...")
        try:
            m3d.start_solver()
        except RuntimeError as e2:
            raise RuntimeError(
                f"Solver tidak bisa dijalankan dari Python ({_short_err(e2)}). Lihat Message Window "
                "di CST dan cek history list: item bertanda merah berarti rebuild gagal.") from e2
    while m3d.is_solver_running():
        time.sleep(2)


def resolve_project(prj, arg):
    """File .cst yang dipakai, dipastikan SAMA dengan project aktif di CST (jika bisa dideteksi)."""
    norm = lambda p: os.path.normcase(os.path.abspath(str(p)))                       # noqa: E731
    active = None
    try:
        a = str(prj.filename())
        active = a if a.lower().endswith(".cst") else None
    except Exception:
        pass
    if arg and active:
        if norm(arg) != norm(active):
            raise RuntimeError(
                f"--project ({arg}) BERBEDA dari project yang aktif di CST ({active}).\n"
                "Hasil dibaca dari file .cst, sedangkan farfield diekspor dari project aktif; bila keduanya "
                "berbeda, data dari dua project akan tercampur. Samakan keduanya.")
        path = arg
    elif arg:
        print("  [peringatan] project aktif tidak bisa dideteksi; pastikan --project adalah file yang "
              "SEDANG TERBUKA di CST.")
        path = arg
    elif active:
        print(f"Project terdeteksi dari CST: {active}")
        path = active
    else:
        raise RuntimeError("Project tidak bisa dideteksi. Berikan --project \"C:\\...\\NamaProject.cst\".")
    if not os.path.exists(path):
        raise FileNotFoundError(f"File project tidak ada di disk: {path}\nSimpan project di CST dulu (Ctrl+S).")
    return path


def export_farfield(m3d, t0, f_ghz, rd, sid):
    """Ekspor irisan directivity phi=0 dan phi=90 dari monitor f_ghz. Kembalikan 2 path file."""
    ffd = os.path.join(rd, "ff")
    os.makedirs(ffd, exist_ok=True)
    item = ed.monitor_item(f_ghz)
    paths = []
    for phi in (0, 90):
        fname = os.path.join(ffd, f"ff_dir_s{sid}_f{ed.fmt_f(f_ghz)}_phi{phi}.txt")
        if os.path.exists(fname):
            os.remove(fname)
        m3d.SelectTreeItem(item)
        ff = m3d.FarfieldPlot
        ff.Reset()
        ff.Plottype("Polar")
        ff.Vary("angle1")
        ff.Theta("0")
        ff.Phi(str(phi))
        ff.Step("1")
        ff.Step2("1")
        ff.SetLockSteps("True")
        ff.SetPlotMode("Directivity")
        ff.Plot()
        ex = m3d.ASCIIExport
        ex.Reset()
        ex.FileName(fname)
        ex.Mode("FixedWidth")
        ex.Execute()
        if not os.path.exists(fname) or os.path.getmtime(fname) < t0:
            raise RuntimeError(f"File farfield baru tidak terbentuk: {fname}. Cek nama item monitor "
                               f"'{item}' di Navigation Tree (MON_START/STOP/STEP di export_dataset.py "
                               "harus sama dengan macro).")
        paths.append(fname)
    return paths


def collect_sample(m3d, project, rd, sid, params, t0):
    """Setelah solver selesai: pilih run yang cocok, ekspor farfield (3,5 GHz dan monitor terdekat fr),
    lalu ekstrak satu baris data. Kembalikan (row, curves)."""
    res, rid = find_run(project, params)
    if rid is None:
        raise RuntimeError("tidak ada hasil di CST dengan parameter sampel ini "
                           "(dialog dijawab No sebelum hasil ada, atau solver gagal?)")
    s11 = ed.s11_summary(res, rid)
    fr = s11[2]
    f_mon = ed.nearest_monitor(fr)
    main_paths = export_farfield(m3d, t0, ed.F0_GHZ, rd, sid)
    fr_paths = main_paths if abs(f_mon - ed.F0_GHZ) < 1e-9 else export_farfield(m3d, t0, f_mon, rd, sid)
    row, curves = ed.extract(res, rid, sid, main_paths, fr_paths, f_mon, s11=s11)
    bad = compare_params(params, row)
    if bad:
        raise RuntimeError(f"parameter pada hasil berbeda dari yang diminta: {bad}")
    return row, curves


def check_monitors(project):
    """Periksa bahwa kurva efisiensi punya titik sebanyak monitor yang diharapkan."""
    res = cst.results.ProjectFile(project, allow_interactive=True).get_3d()
    items = [str(i) for i in res.get_tree_items()]
    ff = [i for i in items if "farfield" in i.lower()]
    print(f"Item farfield yang terlihat di result tree: {len(ff)} (informasi saja)")
    ok = False
    for rid in ed.get_run_ids(res)[:1]:
        try:
            x, v = ed.eff_curve(res, ed.EFF_RAD_PATH, rid)
        except Exception as e:
            print(f"Run {rid}: kurva efisiensi tidak terbaca ({e}). Sudah ada simulasi yang selesai dan tersimpan?")
            continue
        print(f"Run {rid}: kurva Rad. Efficiency punya {len(x)} titik (diharapkan {len(ed.MONITORS_GHZ)}).")
        print("  frekuensi (GHz):", np.round(x, 4).tolist())
        print("  eta_rad        :", np.round(v, 4).tolist())
        miss = [f for f in ed.MONITORS_GHZ if not np.any(np.abs(x - f) < 1e-4)]
        if miss:
            print("  Monitor yang tidak ada di kurva:", miss, "\n  Cek FF_F_START/STOP/STEP di macro vs MON_* di export_dataset.py.")
        ok = len(x) >= len(ed.MONITORS_GHZ) and not miss
    print("HASIL:", "OK, monitor lengkap." if ok else "BELUM LENGKAP, lihat pesan di atas.")
    return 0 if ok else 1


def wait_solver_idle(m3d, timeout=120):
    """Tunggu solver benar-benar berhenti (mis. setelah Ctrl+C) sebelum mengubah parameter."""
    t = time.time()
    while time.time() - t < timeout:
        try:
            if not m3d.is_solver_running():
                return True
        except Exception:
            return True
        time.sleep(2)
    return False


# ---------------------------------------------------------------- dialog otomatis
def start_dialog_watcher():
    """Jalankan dialog_watcher.py sebagai PROSES TERPISAH (menghindari konflik COM dengan API CST)."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dialog_watcher.py")
    if not os.path.exists(script):
        print(f"  [auto-yes] {script} tidak ditemukan; fitur dimatikan.")
        return None
    return subprocess.Popen([sys.executable, script])


# ---------------------------------------------------------------- pengecekan
def check_geometry(p):
    yb = p["Lp"] / 2 + p["PU"] - p["LU"] / 2
    yt = p["Lp"] / 2 + p["PU"] + p["LU"] / 2
    problems = []
    if yb <= p["LI"] + 0.5:
        problems.append(f"dasar U-Slot (y={yb:.2f}) terlalu dekat ujung inset (LI={p['LI']})")
    if yt >= p["Lp"] - 0.5:
        problems.append(f"ujung U-Slot (y={yt:.2f}) hampir keluar patch (Lp={p['Lp']})")
    return problems


def compare_params(requested, row):
    return [k for k in requested if abs(float(row[k]) - float(requested[k])) > 1e-6]


def summarize(samples):
    print(f"{len(samples)} sampel. Rentang tiap parameter:")
    for k in ed.PARAM_NAMES:
        v = np.array([p[k] for _, p in samples])
        print(f"  {k:3s}: {v.min():8.3f} .. {v.max():8.3f}")


def validate_all(samples):
    bad = {sid: check_geometry(p) for sid, p in samples if check_geometry(p)}
    if bad:
        print(f"{len(bad)} sampel tidak valid secara geometri:")
        for sid, pr in list(bad.items())[:10]:
            print(f"  sampel {sid}: {pr}")
        return False
    print("Semua sampel lolos check_geometry.")
    return True


# ---------------------------------------------------------------- utama
def main():
    ap = argparse.ArgumentParser(description="Batch simulasi CST dari sampel LHS/BO")
    ap.add_argument("--project", default=None, help="file .cst yang sedang terbuka (default: dideteksi dari CST)")
    ap.add_argument("--run-name", default=None,
                    help="nama folder keluaran di export/ (default: nama file project tanpa .cst)")
    ap.add_argument("--samples", default=SAMPLES_CSV, help="CSV sampel (lhs_samples.csv / bo_candidates.csv)")
    ap.add_argument("--start", type=int, default=1, help="mulai dari sample_id ini")
    ap.add_argument("--limit", type=int, default=0, help="jalankan maksimal N sampel (0 = semua)")
    ap.add_argument("--auto-yes", action="store_true",
                    help="tekan otomatis tombol Yes pada dialog CST selama batch (butuh pywinauto)")
    ap.add_argument("--reuse-results", action="store_true",
                    help="jika CST sudah punya hasil untuk parameter yang sama, pakai itu (lewati solver)")
    ap.add_argument("--probe", action="store_true", help="cek koneksi, API, dan project yang terdeteksi")
    ap.add_argument("--check-samples", action="store_true", help="validasi CSV sampel saja")
    ap.add_argument("--check-monitors", action="store_true", help="periksa kurva efisiensi vs jumlah monitor")
    ap.add_argument("--test-set", action="store_true", help="uji ganti parameter saja")
    ap.add_argument("--test-export", action="store_true", help="uji ekspor farfield saja")
    args = ap.parse_args()

    # --- perintah yang tidak butuh CST
    if args.check_samples:
        samples = select_samples(load_samples(args.samples), args.start, args.limit)
        summarize(samples)
        validate_all(samples)
        name = args.run_name or (os.path.splitext(os.path.basename(args.project))[0] if args.project else None)
        if name:
            out_csv = os.path.join(EXPORT_DIR, name, CSV_NAME)
            n_done = len(done_keys(out_csv) & {ed.param_key(p) for _, p in samples})
            print(f"Sudah ada hasilnya di {out_csv}: {n_done} sampel.")
        else:
            print("(Tambahkan --project atau --run-name untuk melihat berapa sampel yang sudah selesai.)")
        return 0

    de, prj = connect()
    m3d = prj.model3d
    print("Terhubung ke CST.")
    if not check_api(m3d):
        return 1
    project = resolve_project(prj, args.project)
    rd = os.path.join(EXPORT_DIR, args.run_name) if args.run_name else ed.run_dir(project)
    out_csv = os.path.join(rd, CSV_NAME)
    print(f"Project : {project}\nKeluaran: {rd}")
    if args.probe:
        return 0
    os.makedirs(os.path.join(rd, "curves"), exist_ok=True)

    if args.check_monitors:
        return check_monitors(project)

    if args.test_export:
        t0 = time.time() - 1
        for f in (ed.F0_GHZ, 3.0):
            paths = export_farfield(m3d, t0, f, rd, 0)
            print(f"Monitor {f} GHz -> file:", paths)
            print("  puncak:", peak_over_files(paths))
        return 0

    samples = select_samples(load_samples(args.samples), args.start, args.limit)
    print(f"Membaca {len(samples)} sampel dari {args.samples}")

    if args.test_set:
        sid, params = samples[0]
        print(f"Mengganti parameter ke sampel {sid} ...")
        set_params(m3d, params)
        print("Mengembalikan ke baseline ...")
        set_params(m3d, BASE)
        print("Uji set parameter selesai.")
        return 0

    if not validate_all(samples):
        return 1

    prepare_out_csv(out_csv)
    seen = done_keys(out_csv)
    todo = [(sid, p) for sid, p in samples if ed.param_key(p) not in seen]
    print(f"Sudah selesai sebelumnya: {len(samples) - len(todo)} | akan dijalankan: {len(todo)}")
    if not todo:
        print("Tidak ada yang perlu dijalankan.")
        return 0

    write_header = not os.path.exists(out_csv)
    failed = []
    watcher = None
    if args.auto_yes:
        watcher = start_dialog_watcher()
    t_all = time.time()
    try:
        with open(out_csv, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=ed.FIELDS)
            if write_header:
                writer.writeheader()

            for n, (sid, params) in enumerate(todo, 1):
                print(f"\n=== Sampel {sid} ({n}/{len(todo)}): {params}")
                t0 = time.time()
                try:
                    set_params(m3d, params)
                    _, existing = find_run(project, params)
                    if existing is not None and args.reuse_results:
                        print(f"  hasil untuk parameter ini sudah ada di CST (run {existing}); "
                              "solver dilewati (--reuse-results).")
                    else:
                        if existing is not None:
                            print(f"  [info] CST sudah punya hasil untuk parameter ini (run {existing}) "
                                  "dari simulasi sebelumnya. Dialog 'recalculate' mungkin muncul: "
                                  "jawab Yes, atau jalankan dengan --reuse-results.")
                        print("  menjalankan solver ...")
                        run_solver(m3d, project, params, existing is not None)
                        print(f"  solver selesai ({time.time() - t0:.0f} detik).")
                    try:
                        m3d.Save()
                    except Exception as e:
                        print(f"  [peringatan] project tidak tersimpan otomatis ({e}).")
                    row, curves = collect_sample(m3d, project, rd, sid, params, t0)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"  [GAGAL] sampel {sid}: {e}")
                    failed.append(sid)
                    continue

                writer.writerow(row)
                fh.flush()
                ed.save_curves(rd, sid, curves)

                print(f"  fr={row['fr_ghz']} GHz | RL={row['rl_min_db']} dB | BW={row['bw_mhz']} MHz | "
                      f"monitor fr={row['f_mon_fr_ghz']} GHz")
                print(f"  D(3,5)={row['d_peak_dbi']} dBi | D(fr)={row['d_peak_fr_dbi']} dBi | "
                      f"eta_rad(fr)={row['eta_rad_fr']} | gain(fr,IEEE)={row['gain_fr_ieee_dbi']} dBi")
                if row["n_eff_points"] < len(ed.MONITORS_GHZ):
                    print(f"  [peringatan] kurva efisiensi hanya {row['n_eff_points']} titik "
                          f"(diharapkan {len(ed.MONITORS_GHZ)}): monitor macro tidak lengkap?")
                if row["fr_edge_flag"]:
                    print("  [peringatan] fr menempel di tepi rentang sweep; resonansi sebenarnya mungkin di luar.")

                el = time.time() - t_all
                eta = el / n * (len(todo) - n)
                print(f"  progres {n}/{len(todo)} | berlalu {el / 60:.0f} mnt | sisa sekitar {eta / 60:.0f} mnt")
    except KeyboardInterrupt:
        print("\nDihentikan oleh pengguna. Hasil yang sudah selesai tersimpan; "
              "jalankan lagi perintah yang sama untuk melanjutkan.")
    finally:
        if watcher:
            watcher.terminate()
        if not wait_solver_idle(m3d):
            print("[peringatan] solver masih berjalan; hentikan di CST (Stop) lalu atur parameter secara manual.")
        try:
            set_params(m3d, BASE)
            print("Model dikembalikan ke parameter baseline (belum disimulasikan ulang).")
        except Exception as e:
            print(f"[peringatan] gagal mengembalikan baseline: {e}")

    if failed:
        print(f"\nSampel gagal ({len(failed)}): {failed}")
        print("Jalankan ulang perintah yang sama untuk mencoba lagi sampel yang gagal.")
    print(f"\nSelesai. Hasil semua sampel: {out_csv}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())