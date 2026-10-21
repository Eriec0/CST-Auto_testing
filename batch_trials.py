"""
Menjalankan 3 percobaan CST dengan perubahan parameter kecil, lalu menyimpan semua hasil
ke SATU file: export/batch_trials.csv

Skrip ini memanggil objek VBA CST langsung dari Python lewat project.model3d
(StoreDoubleParameter, FarfieldPlot, ASCIIExport, dan seterusnya), jadi tidak ada kode VBA
yang masuk ke history list.

Prasyarat:
  - CST terbuka dengan project antena yang sudah digambar oleh macro
    (macro boleh dijalankan dengan RUN_SIM = False, cukup sampai model jadi)
  - export_dataset.py dan farfield_utils.py ada di folder yang sama dengan skrip ini
  - PROJECT_PATH di export_dataset.py (atau --project) menunjuk file .cst yang sedang terbuka

Pemakaian (urutan pengujian yang disarankan):
  py batch_trials.py --probe          cek koneksi dan method yang dibutuhkan
  py batch_trials.py --test-set       ganti parameter ke percobaan 1, rebuild, baca balik, lalu
                                      kembalikan ke baseline (tanpa solver)
  py batch_trials.py --test-export    ekspor farfield dari hasil yang sudah ada (tanpa solver)
  py batch_trials.py                  jalankan 3 percobaan penuh

Tiap percobaan: set 11 parameter -> rebuild -> solver -> ekspor farfield -> baca S11,
efisiensi, parameter -> satu baris di CSV. Parameter yang terbaca kembali dari CST
dibandingkan dengan yang diminta, sebagai bukti bahwa perubahan benar-benar masuk model.
"""
import argparse
import csv
import os
import shutil
import sys
import time

import numpy as np
import cst.interface
import cst.results

import export_dataset as ed
from farfield_utils import peak_over_files

OUT_DIR = ed.OUT_DIR
OUT_CSV = os.path.join(OUT_DIR, "batch_trials.csv")
FF_ITEM = r"Farfields\farfield (f=3.5) [1]"

BASE = dict(Lp=20.22, Wp=26.33, LU=10.0, WU=10.5, gU=0.6, PU=2.0,
            LI=6.15, LD=3.0, WD=3.0, gD=0.3, PD=0.0)

# Perubahan kecil dari baseline (sekitar 1 sampai 3 persen). Lp diperbesar bertahap
# karena resonansi baseline (3,99 GHz) berada di atas 3,5 GHz.
TRIALS = [
    {**BASE, "Lp": 20.35, "LU": 10.15, "WD": 3.15, "gD": 0.33},
    {**BASE, "Lp": 20.62, "LU": 10.2, "WD": 3.2, "gD": 0.34},
    {**BASE, "Lp": 20.82, "LU": 10.3, "WD": 3.3, "gD": 0.36},
]

REQUIRED = ["StoreDoubleParameter", "full_history_rebuild", "SelectTreeItem",
            "FarfieldPlot", "ASCIIExport", "run_solver"]


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


def run_solver(m3d):
    try:
        m3d.run_solver()
    except RuntimeError as e:
        print(f"  run_solver gagal: {e}")
        print("  Mencoba start_solver sebagai cadangan ...")
        try:
            m3d.start_solver()
        except RuntimeError as e2:
            raise RuntimeError(
                f"Solver tidak bisa dijalankan dari Python ({e2}). Lihat Message Window di CST "
                "dan cek history list: item bertanda merah berarti rebuild gagal, "
                "dan solver tidak akan jalan pada model yang tidak utuh.") from e2
    while m3d.is_solver_running():
        time.sleep(2)


def export_farfield(m3d, t0):
    paths = []
    for phi in (0, 90):
        fname = os.path.join(OUT_DIR, f"ff_dir_phi{phi}.txt")
        if os.path.exists(fname):
            os.remove(fname)
        m3d.SelectTreeItem(FF_ITEM)
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
            raise RuntimeError(f"File farfield baru tidak terbentuk: {fname}. "
                               "Cek FF_ITEM (nama item di Navigation Tree) dan folder export.")
        paths.append(fname)
    return paths


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


# ---------------------------------------------------------------- utama
def main():
    ap = argparse.ArgumentParser(description="Batch 3 percobaan CST")
    ap.add_argument("--project", default=ed.PROJECT_PATH, help="file .cst yang sedang terbuka")
    ap.add_argument("--probe", action="store_true", help="cek koneksi dan API saja")
    ap.add_argument("--test-set", action="store_true", help="uji ganti parameter saja")
    ap.add_argument("--test-export", action="store_true", help="uji ekspor farfield saja")
    args = ap.parse_args()

    de, prj = connect()
    m3d = prj.model3d
    print("Terhubung ke CST.")
    if not check_api(m3d):
        return 1
    if args.probe:
        return 0

    os.makedirs(os.path.join(OUT_DIR, "curves"), exist_ok=True)

    if args.test_set:
        print("Mengganti parameter ke percobaan 1 ...")
        set_params(m3d, TRIALS[0])
        print("Mengembalikan ke baseline ...")
        set_params(m3d, BASE)
        print("Uji set parameter selesai.")
        return 0

    if args.test_export:
        t0 = time.time() - 1
        paths = export_farfield(m3d, t0)
        print("File terbentuk:", paths)
        print("Puncak:", peak_over_files(paths))
        return 0

    for i, p in enumerate(TRIALS, 1):
        problems = check_geometry(p)
        if problems:
            print(f"Percobaan {i} tidak valid: {problems}")
            return 1

    rows = []
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ed.FIELDS)
        writer.writeheader()

        for i, params in enumerate(TRIALS, 1):
            print(f"\n=== Percobaan {i}/{len(TRIALS)}: {params}")
            t0 = time.time()

            set_params(m3d, params)
            print("  menjalankan solver ...")
            run_solver(m3d)
            print(f"  solver selesai ({time.time() - t0:.0f} detik).")
            try:
                m3d.Save()
            except Exception as e:
                print(f"  [peringatan] project tidak tersimpan otomatis ({e}).")

            ff_paths = export_farfield(m3d, t0)
            for pth in ff_paths:
                base, ext = os.path.splitext(os.path.basename(pth))
                shutil.copyfile(pth, os.path.join(OUT_DIR, f"{base}_trial{i}{ext}"))

            res = cst.results.ProjectFile(args.project, allow_interactive=True).get_3d()
            row, f, s11_db = ed.extract(res, 0, i, ff_paths)

            bad = compare_params(params, row)
            if bad:
                print(f"  [PERINGATAN] parameter di hasil CST berbeda dari yang diminta: {bad}")

            writer.writerow(row)
            fh.flush()
            rows.append(row)

            curve = os.path.join(OUT_DIR, "curves", f"s11_trial{i}.csv")
            with open(curve, "w", newline="", encoding="utf-8") as cf:
                w = csv.writer(cf)
                w.writerow(["freq_ghz", "s11_db"])
                w.writerows(zip(np.round(f, 6), np.round(s11_db, 4)))

            print(f"  fr={row['fr_ghz']} GHz | RL={row['rl_min_db']} dB | BW={row['bw_mhz']} MHz | "
                  f"D={row['d_peak_dbi']} dBi | eta_rad(3,5)={row['eta_rad']} | "
                  f"eta_rad(fr)={row['eta_rad_fr']} | gain_ieee={row['gain_ieee_dbi']} dBi")

    set_params(m3d, BASE)
    print(f"\nSelesai. Hasil semua percobaan: {OUT_CSV}")
    print("Model dikembalikan ke parameter baseline (belum disimulasikan ulang).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
