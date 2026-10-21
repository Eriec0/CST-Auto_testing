"""
Ekstraksi hasil simulasi CST menjadi satu baris data per sampel (dipakai batch_trials.py).

Perubahan untuk macro dengan monitor farfield multi-frekuensi (antena_uslot_dgs_dumbbell4.bas):
  - Efisiensi dibaca dari kurva yang kini punya banyak titik (satu per monitor), jadi efisiensi
    di frekuensi resonansi (eta_rad_fr) benar-benar diinterpolasi, bukan konstan.
  - Directivity/gain juga dihitung pada monitor yang PALING DEKAT dengan frekuensi resonansi
    (d_peak_fr_dbi, gain_fr_ieee_dbi, gain_fr_real_dbi), selain nilai lama di 3,5 GHz.
  - Semua keluaran per project disimpan di export/<nama_project>/ agar hasil dari project/model
    yang berbeda tidak pernah tercampur atau saling menimpa.

Cara hitung gain:
  gain_ieee_dbi       = D_puncak(3,5 GHz)  + 10*log10(eta_rad(3,5 GHz))          (nilai lama)
  gain_real_dbi       = D_puncak(3,5 GHz)  + 10*log10(eta_tot(3,5 GHz))
  gain_fr_ieee_dbi    = D_puncak(f_mon)    + 10*log10(eta_rad(f_mon))            <- di sekitar fr
  gain_fr_real_dbi    = D_puncak(f_mon)    + 10*log10(eta_tot(f_mon))
  f_mon = monitor terdekat dengan fr (selisih maksimum = setengah MON_STEP).
Syarat gain pada feasible_all memakai gain_fr_ieee_dbi (jika ada), karena pencocokan impedansi
sudah dinilai terpisah lewat return loss.

PENTING: MON_START/MON_STOP/MON_STEP harus SAMA dengan FF_F_START/FF_F_STOP/FF_F_STEP di macro.
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
EXPORT_DIR = os.path.join(BASE, "export")      # file bersama (mis. lhs_samples.csv, bo_candidates.csv)
PROJECT_PATH = None                            # TIDAK ADA default: dideteksi dari CST aktif atau --project

F0_GHZ = 3.5                                   # frekuensi monitor utama (nama "farfield (f=3.5)")
MON_START, MON_STOP, MON_STEP = 2.5, 4.5, 0.25  # samakan dengan macro
S11_PATH = r"1D Results\S-Parameters\S1,1"
EFF_RAD_PATH = r"1D Results\Efficiencies\Rad. Efficiency [1]"
EFF_TOT_PATH = r"1D Results\Efficiencies\Tot. Efficiency [1]"
FF_FILES = ["ff_dir_phi0.txt", "ff_dir_phi90.txt"]   # hanya untuk CLI lama (ekspor macro)

RL_LIMIT_DB = -10.0
BAND_GHZ = (3.3, 3.7)
BW_MIN_MHZ = 200.0
GAIN_MIN_DBI = 5.0           # SPESIFIKASI PROPOSAL; untuk satu patch FR-4 nilai ini sulit dicapai (lihat analisis)
EDGE_TOL_GHZ = 0.05          # fr sedekat ini dengan tepi sweep ditandai (fr_edge_flag)

PARAM_NAMES = ["Lp", "Wp", "LU", "WU", "gU", "PU", "LI", "LD", "WD", "gD", "PD"]

FIELDS = (["sample_id", "run_id", "timestamp"] + PARAM_NAMES + [
    "fr_ghz", "rl_min_db", "vswr", "bw_mhz", "band_cover_pct", "s11_at_f0_db", "fr_edge_flag",
    "eta_rad", "eta_tot", "eta_rad_fr", "f_mon_fr_ghz", "eta_rad_mon", "eta_tot_mon", "n_eff_points",
    "d_peak_dbi", "d_boresight_dbi", "theta_peak_deg", "d_peak_fr_dbi", "theta_peak_fr_deg",
    "gain_ieee_dbi", "gain_real_dbi", "gain_fr_ieee_dbi", "gain_fr_real_dbi",
    "feasible_wo_gain", "feasible_all"])
# =========================================================


# ---------------------------------------------------------------- monitor
def _r4(x):
    return int(x * 10000 + 0.5) / 10000


def _build_monitors():
    n = int((MON_STOP - MON_START) / MON_STEP + 0.5)
    mons = [_r4(MON_START + i * MON_STEP) for i in range(n + 1)]
    if not any(abs(m - F0_GHZ) < 1e-6 for m in mons):
        mons.append(F0_GHZ)                      # macro selalu membuat monitor utama
    return sorted(mons)


MONITORS_GHZ = _build_monitors()


def fmt_f(f):
    """Teks frekuensi sama dengan macro (FFText): 3.0 -> '3', 2.75 -> '2.75'."""
    return ("%.4f" % f).rstrip("0").rstrip(".")


def monitor_item(f):
    return rf"Farfields\farfield (f={fmt_f(f)}) [1]"


def nearest_monitor(f):
    return min(MONITORS_GHZ, key=lambda m: abs(m - f))


def run_dir(project_path):
    """Folder keluaran khusus project: export/<nama_project>/"""
    return os.path.join(EXPORT_DIR, os.path.splitext(os.path.basename(project_path))[0])


# ---------------------------------------------------------------- pembacaan hasil
def get_curve(res, path, run_id):
    item = res.get_result_item(path, run_id)
    x = np.asarray(item.get_xdata(), dtype=float)
    if x.size and x.max() > 1e6:          # jaga-jaga bila dalam Hz
        x = x / 1e9
    y = np.asarray(item.get_ydata(), dtype=complex)
    order = np.argsort(x)
    return x[order], y[order]


def eff_curve(res, path, run_id):
    """Kurva efisiensi sebagai rasio 0..1 (satuan dideteksi pada SELURUH kurva, bukan per titik)."""
    x, y = get_curve(res, path, run_id)
    return x, np.asarray(eff_to_linear(np.real(y)), dtype=float)


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


def s11_summary(res, run_id):
    """(f, s11_db, fr, rl_min, bw_mhz) dari kurva S11 run ini."""
    x, s = get_curve(res, S11_PATH, run_id)
    s11_db = 20.0 * np.log10(np.maximum(np.abs(s), 1e-12))
    fr, rl_min, bw = bandwidth_around_min(x, s11_db, RL_LIMIT_DB)
    return x, s11_db, fr, rl_min, bw


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


# ---------------------------------------------------------------- ekstraksi satu run
def extract(res, run_id, sample_id, ff_main_paths, ff_fr_paths=None, f_mon=None, s11=None):
    """Satu baris data + kurva untuk disimpan.

    ff_main_paths : file farfield monitor 3,5 GHz (phi=0 dan 90)
    ff_fr_paths   : file farfield monitor terdekat fr (None -> kolom *_fr jadi NaN)
    f_mon         : frekuensi monitor itu (GHz)
    s11           : hasil s11_summary() bila sudah dihitung (hindari baca ulang)
    """
    x, s11_db, fr, rl_min, bw = s11 if s11 is not None else s11_summary(res, run_id)
    gamma = min(10.0 ** (rl_min / 20.0), 0.999999)
    vswr = (1 + gamma) / (1 - gamma)
    cover = band_coverage_percent(x, s11_db, BAND_GHZ, RL_LIMIT_DB)
    s11_f0 = float(np.interp(F0_GHZ, x, s11_db))
    edge = int(fr <= x.min() + EDGE_TOL_GHZ or fr >= x.max() - EDGE_TOL_GHZ)

    xe, eta_rad_c = eff_curve(res, EFF_RAD_PATH, run_id)
    _, eta_tot_c = eff_curve(res, EFF_TOT_PATH, run_id)
    tiny = 1e-12
    eta_rad = max(float(np.interp(F0_GHZ, xe, eta_rad_c)), tiny)
    eta_tot = max(float(np.interp(F0_GHZ, xe, eta_tot_c)), tiny)
    eta_rad_fr = max(float(np.interp(fr, xe, eta_rad_c)), tiny)

    pk = peak_over_files(ff_main_paths)
    d_peak = pk["dir_peak_dbi"]
    gain_ieee = d_peak + 10.0 * np.log10(eta_rad)
    gain_real = d_peak + 10.0 * np.log10(eta_tot)

    nan = float("nan")
    d_fr = th_fr = g_fr_ieee = g_fr_real = eta_rad_mon = eta_tot_mon = nan
    if ff_fr_paths and f_mon is not None:
        pkf = peak_over_files(ff_fr_paths)
        d_fr, th_fr = pkf["dir_peak_dbi"], pkf["theta_peak_deg"]
        eta_rad_mon = max(float(np.interp(f_mon, xe, eta_rad_c)), tiny)
        eta_tot_mon = max(float(np.interp(f_mon, xe, eta_tot_c)), tiny)
        g_fr_ieee = d_fr + 10.0 * np.log10(eta_rad_mon)
        g_fr_real = d_fr + 10.0 * np.log10(eta_tot_mon)

    g_ref = g_fr_ieee if np.isfinite(g_fr_ieee) else gain_ieee
    ok_core = (BAND_GHZ[0] <= fr <= BAND_GHZ[1]) and rl_min <= RL_LIMIT_DB and bw >= BW_MIN_MHZ
    row = {"sample_id": sample_id, "run_id": run_id,
           "timestamp": datetime.now().isoformat(timespec="seconds")}
    row.update(get_params(res, run_id))
    row.update({
        "fr_ghz": round(fr, 5), "rl_min_db": round(rl_min, 3), "vswr": round(vswr, 4),
        "bw_mhz": round(bw, 2), "band_cover_pct": round(cover, 1), "s11_at_f0_db": round(s11_f0, 3),
        "fr_edge_flag": edge,
        "eta_rad": round(eta_rad, 5), "eta_tot": round(eta_tot, 5), "eta_rad_fr": round(eta_rad_fr, 5),
        "f_mon_fr_ghz": nan if f_mon is None else round(float(f_mon), 4),
        "eta_rad_mon": round(eta_rad_mon, 5), "eta_tot_mon": round(eta_tot_mon, 5),
        "n_eff_points": int(len(xe)),
        "d_peak_dbi": round(d_peak, 3), "d_boresight_dbi": round(pk["dir_boresight_dbi"], 3),
        "theta_peak_deg": round(pk["theta_peak_deg"], 1),
        "d_peak_fr_dbi": round(d_fr, 3), "theta_peak_fr_deg": round(th_fr, 1),
        "gain_ieee_dbi": round(gain_ieee, 3), "gain_real_dbi": round(gain_real, 3),
        "gain_fr_ieee_dbi": round(g_fr_ieee, 3), "gain_fr_real_dbi": round(g_fr_real, 3),
        "feasible_wo_gain": int(ok_core),
        "feasible_all": int(ok_core and g_ref >= GAIN_MIN_DBI),
    })
    curves = {"s11": (x, s11_db), "eff": (xe, eta_rad_c, eta_tot_c)}
    return row, curves


def save_curves(rd, sid, curves):
    os.makedirs(os.path.join(rd, "curves"), exist_ok=True)
    os.makedirs(os.path.join(rd, "eff"), exist_ok=True)
    x, s11_db = curves["s11"]
    with open(os.path.join(rd, "curves", f"s11_sample{sid}.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["freq_ghz", "s11_db"])
        w.writerows(zip(np.round(x, 6), np.round(s11_db, 4)))
    xe, er, et = curves["eff"]
    with open(os.path.join(rd, "eff", f"eff_sample{sid}.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["freq_ghz", "eta_rad", "eta_tot"])
        w.writerows(zip(np.round(xe, 6), np.round(er, 5), np.round(et, 5)))


# ---------------------------------------------------------------- CLI lama (ekspor dari macro)
def main():
    ap = argparse.ArgumentParser(description="Ekspor hasil CST (run yang sudah ada) ke dataset.csv")
    ap.add_argument("--project", required=True, help="file .cst (WAJIB, tidak ada default)")
    ap.add_argument("--sample-id", default=None, help="nomor sampel awal (default: otomatis)")
    ap.add_argument("--ff-dir", default=None,
                    help="folder berisi ff_dir_phi0.txt & ff_dir_phi90.txt (default: export/<project>/)")
    ap.add_argument("--list", action="store_true", help="tampilkan item result tree lalu keluar")
    args = ap.parse_args()

    res = cst.results.ProjectFile(args.project, allow_interactive=True).get_3d()
    if args.list:
        for item in res.get_tree_items():
            print(item)
        return

    rd = run_dir(args.project)
    os.makedirs(rd, exist_ok=True)
    ffd = args.ff_dir or rd
    ff_paths = [os.path.join(ffd, n) for n in FF_FILES]
    missing = [p for p in ff_paths if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError("File farfield belum ada: " + ", ".join(missing) +
                                "\nJalankan macro dengan RUN_SIM dan EXPORT_FF = True dan samakan FF_OUT_DIR "
                                f"dengan folder: {ffd}")
    dataset_path = os.path.join(rd, "dataset.csv")
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
        row, curves = extract(res, run_id, sid, ff_paths)       # tanpa monitor fr -> kolom *_fr = NaN
        rows.append(row)
        seen.add(key)
        save_curves(rd, sid, curves)

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
              f"BW={r['bw_mhz']} MHz | D={r['d_peak_dbi']} dBi | gain_ieee={r['gain_ieee_dbi']} dBi")
    print(f"Selesai. Dataset: {dataset_path}")


if __name__ == "__main__":
    main()