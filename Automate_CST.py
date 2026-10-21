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


"""
Ekspor hasil simulasi CST ke dataset.csv: satu baris per simulasi, semua kolom berisi angka.

Alur:
  1. Jalankan macro desain (antena_uslot_dgs_dumbbell.bas). Macro menggambar, menjalankan
     solver, lalu mengekspor farfield: export/ff_dir_phi0.txt dan export/ff_dir_phi90.txt
  2. Simpan project di CST, lalu jalankan:  py export_dataset.py --project <file.cst>

Taruh skrip ini bersama farfield_utils.py. Folder export dibuat di sebelah skrip dan harus
sama dengan FF_OUT_DIR di macro.

Cara hitung gain (di frekuensi monitor farfield, 3,5 GHz):
  gain_ieee_dbi = D_puncak + 10*log10(efisiensi radiasi)
  gain_real_dbi = D_puncak + 10*log10(efisiensi total)   (memasukkan mismatch)
gain_fr_approx_dbi = D_puncak (monitor 3,5 GHz) + 10*log10(efisiensi radiasi di fr), perkiraan kasar.
Syarat gain >= 5 dBi pada kolom feasible_all memakai gain_ieee_dbi, karena pencocokan
impedansi sudah dinilai terpisah lewat return loss.
"""
import argparse
import csv
import os
from datetime import datetime

import numpy as np
import cst.results

from farfield_utils import peak_over_files, eff_to_linear

# ====================== KONFIGURASI ======================
BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT_PATH = r"C:\Users\User\Playground\CST_Auto\AntenaMicrostrips.cst"   # ganti ke file .cst Anda
OUT_DIR = os.path.join(BASE, "export")

F0_GHZ = 3.5                      # frekuensi monitor farfield
S11_PATH = r"1D Results\S-Parameters\S1,1"
EFF_RAD_PATH = r"1D Results\Efficiencies\Rad. Efficiency [1]"
EFF_TOT_PATH = r"1D Results\Efficiencies\Tot. Efficiency [1]"
FF_FILES = ["ff_dir_phi0.txt", "ff_dir_phi90.txt"]

RL_LIMIT_DB = -10.0
BAND_GHZ = (3.3, 3.7)
BW_MIN_MHZ = 200.0
GAIN_MIN_DBI = 5.0

PARAM_NAMES = ["Lp", "Wp", "LU", "WU", "gU", "PU", "LI", "LD", "WD", "gD", "PD"]

FIELDS = (["sample_id", "run_id", "timestamp"] + PARAM_NAMES + [
    "fr_ghz", "rl_min_db", "vswr", "bw_mhz", "band_cover_pct", "s11_at_f0_db",
    "eta_rad", "eta_tot", "eta_rad_fr", "d_peak_dbi", "d_boresight_dbi", "theta_peak_deg",
    "gain_ieee_dbi", "gain_real_dbi", "gain_fr_approx_dbi", "feasible_wo_gain", "feasible_all"])
# =========================================================


def get_curve(res, path, run_id):
    item = res.get_result_item(path, run_id)
    x = np.asarray(item.get_xdata(), dtype=float)
    if x.size and x.max() > 1e6:          # jaga-jaga bila dalam Hz
        x = x / 1e9
    y = np.asarray(item.get_ydata(), dtype=complex)
    order = np.argsort(x)
    return x[order], y[order]


def eff_at(res, path, run_id, f0):
    x, y = get_curve(res, path, run_id)
    return float(eff_to_linear(float(np.interp(f0, x, np.real(y)))))


def bandwidth_around_min(f, s11_db, limit):
    i = int(np.argmin(s11_db))
    fr, rl_min = float(f[i]), float(s11_db[i])
    if rl_min > limit:
        return fr, rl_min, 0.0
    lo = i
    while lo > 0 and s11_db[lo - 1] <= limit:
        lo -= 1
    hi = i
    while hi < len(f) - 1 and s11_db[hi + 1] <= limit:
        hi += 1
    f_low = float(f[lo])
    if lo > 0:
        f_low = float(np.interp(limit, [s11_db[lo], s11_db[lo - 1]], [f[lo], f[lo - 1]]))
    f_high = float(f[hi])
    if hi < len(f) - 1:
        f_high = float(np.interp(limit, [s11_db[hi], s11_db[hi + 1]], [f[hi], f[hi + 1]]))
    return fr, rl_min, (f_high - f_low) * 1000.0


def band_coverage_percent(f, s11_db, band, limit):
    grid = np.linspace(band[0], band[1], 401)
    return float(np.mean(np.interp(grid, f, s11_db) <= limit) * 100.0)


def get_params(res, run_id):
    p = res.get_parameter_combination(run_id)
    missing = [k for k in PARAM_NAMES if k not in p]
    if missing:
        raise RuntimeError(f"Parameter tidak ditemukan di hasil run {run_id}: {missing}")
    return {k: float(p[k]) for k in PARAM_NAMES}


def get_run_ids(res):
    try:
        ids = list(res.get_all_run_ids())
        return ids if ids else [0]
    except Exception:
        return [0]


def param_key(params):
    return tuple(round(float(params[k]), 6) for k in PARAM_NAMES)


def read_existing(dataset_path):
    """Kembalikan (jumlah baris, himpunan kunci parameter) dari dataset yang ada."""
    keys, n = set(), 0
    if os.path.exists(dataset_path):
        with open(dataset_path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                n += 1
                try:
                    keys.add(tuple(round(float(row[k]), 6) for k in PARAM_NAMES))
                except (KeyError, ValueError):
                    pass
    return n, keys


def prepare_dataset_file(dataset_path):
    """Jika dataset lama berformat beda, ganti namanya agar tidak tercampur."""
    if not os.path.exists(dataset_path):
        return
    with open(dataset_path, newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh), [])
    if header != FIELDS:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = dataset_path.replace(".csv", f"_lama_{stamp}.csv")
        os.rename(dataset_path, new_name)
        print(f"Format dataset lama berbeda, dipindah ke: {new_name}")


def extract(res, run_id, sample_id, ff_paths):
    x, s = get_curve(res, S11_PATH, run_id)
    s11_db = 20.0 * np.log10(np.maximum(np.abs(s), 1e-12))

    fr, rl_min, bw = bandwidth_around_min(x, s11_db, RL_LIMIT_DB)
    gamma = min(10.0 ** (rl_min / 20.0), 0.999999)
    vswr = (1 + gamma) / (1 - gamma)
    cover = band_coverage_percent(x, s11_db, BAND_GHZ, RL_LIMIT_DB)
    s11_f0 = float(np.interp(F0_GHZ, x, s11_db))

    eta_rad = max(eff_at(res, EFF_RAD_PATH, run_id, F0_GHZ), 1e-12)
    eta_tot = max(eff_at(res, EFF_TOT_PATH, run_id, F0_GHZ), 1e-12)

    # efisiensi radiasi di frekuensi resonansi (bukan di 3,5 GHz)
    eta_rad_fr = max(eff_at(res, EFF_RAD_PATH, run_id, fr), 1e-12)

    pk = peak_over_files(ff_paths)
    d_peak = pk["dir_peak_dbi"]
    gain_ieee = d_peak + 10.0 * np.log10(eta_rad)
    gain_real = d_peak + 10.0 * np.log10(eta_tot)
    # perkiraan: directivity dari monitor 3,5 GHz, efisiensi radiasi di fr
    gain_fr = d_peak + 10.0 * np.log10(eta_rad_fr)

    ok_core = (BAND_GHZ[0] <= fr <= BAND_GHZ[1]) and rl_min <= RL_LIMIT_DB and bw >= BW_MIN_MHZ
    row = {"sample_id": sample_id, "run_id": run_id,
           "timestamp": datetime.now().isoformat(timespec="seconds")}
    row.update(get_params(res, run_id))
    row.update({
        "fr_ghz": round(fr, 5),
        "rl_min_db": round(rl_min, 3),
        "vswr": round(vswr, 4),
        "bw_mhz": round(bw, 2),
        "band_cover_pct": round(cover, 1),
        "s11_at_f0_db": round(s11_f0, 3),
        "eta_rad": round(eta_rad, 5),
        "eta_tot": round(eta_tot, 5),
        "eta_rad_fr": round(eta_rad_fr, 5),
        "d_peak_dbi": round(d_peak, 3),
        "d_boresight_dbi": round(pk["dir_boresight_dbi"], 3),
        "theta_peak_deg": round(pk["theta_peak_deg"], 1),
        "gain_ieee_dbi": round(gain_ieee, 3),
        "gain_real_dbi": round(gain_real, 3),
        "gain_fr_approx_dbi": round(gain_fr, 3),
        "feasible_wo_gain": int(ok_core),
        "feasible_all": int(ok_core and gain_ieee >= GAIN_MIN_DBI),
    })
    return row, x, s11_db


def main():
    ap = argparse.ArgumentParser(description="Ekspor hasil CST ke dataset.csv")
    ap.add_argument("--project", default=PROJECT_PATH)
    ap.add_argument("--sample-id", default=None, help="nomor sampel awal (default: otomatis)")
    ap.add_argument("--list", action="store_true", help="tampilkan item result tree lalu keluar")
    args = ap.parse_args()

    res = cst.results.ProjectFile(args.project, allow_interactive=True).get_3d()
    if args.list:
        for item in res.get_tree_items():
            print(item)
        return

    os.makedirs(os.path.join(OUT_DIR, "curves"), exist_ok=True)
    ff_paths = [os.path.join(OUT_DIR, n) for n in FF_FILES]
    missing = [p for p in ff_paths if not os.path.exists(p)]
    if missing:
        isi = sorted(f for f in os.listdir(OUT_DIR) if f.lower().endswith(".txt"))
        raise FileNotFoundError(
            "File farfield belum ada: " + ", ".join(missing) + "\n"
            f"File .txt yang ada di {OUT_DIR}: {isi if isi else 'tidak ada'}\n"
            "Jalankan macro desain terbaru (RUN_SIM dan EXPORT_FF = True) pada project ini, "
            "tunggu sampai selesai, dan pastikan FF_OUT_DIR di macro sama dengan folder di atas.")
    dataset_path = os.path.join(OUT_DIR, "dataset.csv")
    prepare_dataset_file(dataset_path)
    n_exist, seen = read_existing(dataset_path)
    next_id = n_exist + 1 if args.sample_id is None else int(args.sample_id)

    rows = []
    for run_id in get_run_ids(res):
        key = param_key(get_params(res, run_id))
        if key in seen:
            print(f"Run {run_id} dilewati: kombinasi parameter sudah ada di dataset.")
            continue
        sid = next_id + len(rows)
        row, f, s11_db = extract(res, run_id, sid, ff_paths)
        rows.append(row)
        seen.add(key)

        curve_path = os.path.join(OUT_DIR, "curves", f"s11_sample{sid}_run{run_id}.csv")
        with open(curve_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["freq_ghz", "s11_db"])
            w.writerows(zip(np.round(f, 6), np.round(s11_db, 4)))

    if not rows:
        print("Tidak ada baris baru untuk ditulis.")
        return

    write_header = not os.path.exists(dataset_path)
    with open(dataset_path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        w.writerows(rows)

    for r in rows:
        print(f"Sampel {r['sample_id']}: fr={r['fr_ghz']} GHz | RL={r['rl_min_db']} dB | "
              f"BW={r['bw_mhz']} MHz | D={r['d_peak_dbi']} dBi | "
              f"eta_rad={r['eta_rad']} eta_tot={r['eta_tot']} | "
              f"gain_ieee={r['gain_ieee_dbi']} dBi | gain_real={r['gain_real_dbi']} dBi")
    print(f"Selesai. Dataset: {dataset_path}")


if __name__ == "__main__":
    main()



"""
Pembaca hasil ekspor farfield ASCII CST dan penghitung gain.

Format file (dari ekspor plot farfield CST):
  kolom: Theta, Phi, Abs(Dir.) [dBi], Abs(Theta), Phase(Theta), Abs(Phi), Phase(Phi), Ax.Ratio
  dua baris pertama adalah header.

Catatan: bila header kolom ke-3 berbunyi Abs(Dir.), isinya DIRECTIVITY, bukan gain.
  Bila plot diekspor dalam mode Gain, header berbunyi Abs(Gain) dan nilainya sudah gain
  (nama kunci dir_peak_dbi tetap dipakai untuk keduanya).
  Gain (IEEE)    = D + 10*log10(efisiensi radiasi)
  Realized gain  = D + 10*log10(efisiensi total)
"""
import numpy as np


def read_farfield(path):
    d = np.loadtxt(path, skiprows=2)
    return {"theta": d[:, 0], "phi": d[:, 1], "dir_dbi": d[:, 2]}


def peak_directivity(path):
    """Nilai puncak directivity pada data yang diekspor, beserta arahnya."""
    ff = read_farfield(path)
    i = int(np.argmax(ff["dir_dbi"]))
    bore = ff["dir_dbi"][ff["theta"] == 0.0]
    return {
        "dir_peak_dbi": float(ff["dir_dbi"][i]),
        "theta_peak_deg": float(ff["theta"][i]),
        "phi_peak_deg": float(ff["phi"][i]),
        "dir_boresight_dbi": float(np.mean(bore)) if bore.size else float("nan"),
        "n_phi_cuts": int(np.unique(ff["phi"]).size),
    }


def peak_over_files(paths):
    """Puncak directivity/gain dari beberapa irisan (mis. phi=0 dan phi=90)."""
    best = None
    for p in paths:
        info = peak_directivity(p)
        info["file"] = str(p)
        if best is None or info["dir_peak_dbi"] > best["dir_peak_dbi"]:
            best = info
    return best


def eff_to_linear(value):
    """Ubah efisiensi ke rasio 0..1. Menangani rasio, persen, atau dB."""
    v = np.asarray(value, dtype=float)
    if np.all(v <= 0.0):          # dB
        return 10.0 ** (v / 10.0)
    if np.nanmax(v) > 1.5:        # persen
        return v / 100.0
    return v                      # rasio


def gain_dbi(dir_dbi, efficiency):
    """Gain (dBi) dari directivity (dBi) dan efisiensi (rasio 0..1)."""
    eta = float(eff_to_linear(efficiency))
    return float(dir_dbi + 10.0 * np.log10(eta))


if __name__ == "__main__":
    import sys
    info = peak_directivity(sys.argv[1])
    print(info)
    if len(sys.argv) > 2:
        print("gain (dBi):", gain_dbi(info["dir_peak_dbi"], float(sys.argv[2])))
