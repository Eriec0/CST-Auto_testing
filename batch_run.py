"""
Ekspor hasil simulasi CST Studio Suite 2024 ke CSV untuk dataset GPR dan BO.

Keluaran di OUT_DIR:
  dataset.csv                          satu baris per simulasi (11 parameter + hasil)
  curves/s11_sample<id>_run<id>.csv    kurva S11 (frekuensi vs dB) per simulasi

Pemakaian (simulasi sudah selesai, project terbuka di CST):
  python export_cst_to_csv.py --list                 lihat path item di result tree
  python export_cst_to_csv.py                        ekspor semua run di project
  python export_cst_to_csv.py --sample-id 7          beri nomor sampel manual
"""
import argparse
import csv
import os
from datetime import datetime

import numpy as np
import cst.results

# ====================== KONFIGURASI ======================
PROJECT_PATH = r"C:\Users\User\Playground\CST_Auto\Antena_Microstrips.cst"   # ganti ke lokasi file .cst Anda
OUT_DIR = r"C:\Users\User\Playground\CST_Auto\export"

S11_PATH = r"1D Results\S-Parameters\S1,1"
# Path kurva gain terhadap frekuensi di result tree (isi setelah cek dengan --list).
# Contoh bentuk: r"1D Results\Gain\Gain vs Frequency". None = gain dilewati (NaN).
GAIN_PATH = None

RL_LIMIT_DB = -10.0
BAND_GHZ = (3.3, 3.7)
BW_MIN_MHZ = 200.0
GAIN_MIN_DBI = 5.0

PARAM_NAMES = ["Lp", "Wp", "LU", "WU", "gU", "PU", "LI", "LD", "WD", "gD", "PD"]
# =========================================================


def to_ghz(freq):
    """Jaga-jaga: jika sumbu frekuensi dalam Hz, ubah ke GHz."""
    freq = np.asarray(freq, dtype=float)
    if freq.size and freq.max() > 1e6:
        freq = freq / 1e9
    return freq


def load_s11(res, run_id):
    item = res.get_result_item(S11_PATH, run_id)
    f = to_ghz(item.get_xdata())
    s = np.asarray(item.get_ydata())
    s11_db = 20.0 * np.log10(np.maximum(np.abs(s), 1e-12))
    order = np.argsort(f)
    return f[order], s11_db[order]


def bandwidth_around_min(f, s11_db, limit):
    """Bandwidth pada return loss <= limit di sekitar resonansi terdalam."""
    i = int(np.argmin(s11_db))
    fr, rl_min = float(f[i]), float(s11_db[i])
    if rl_min > limit:
        return fr, rl_min, np.nan, np.nan, 0.0

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

    return fr, rl_min, f_low, f_high, (f_high - f_low) * 1000.0


def band_coverage_percent(f, s11_db, band, limit):
    """Persentase rentang band target yang memenuhi return loss <= limit."""
    grid = np.linspace(band[0], band[1], 401)
    db = np.interp(grid, f, s11_db)
    return float(np.mean(db <= limit) * 100.0)


def load_gain(res, run_id, f0):
    if not GAIN_PATH:
        return float("nan")
    try:
        item = res.get_result_item(GAIN_PATH, run_id)
        x = to_ghz(item.get_xdata())
        y = np.real(np.asarray(item.get_ydata(), dtype=complex))
        return float(np.interp(f0, x, y))
    except Exception as e:
        print(f"  [peringatan] gain tidak terbaca ({e}). Cek GAIN_PATH dengan --list.")
        return float("nan")


def get_params(res, run_id):
    try:
        p = res.get_parameter_combination(run_id)
        return {k: float(p[k]) for k in PARAM_NAMES if k in p}
    except Exception as e:
        print(f"  [peringatan] parameter run {run_id} tidak terbaca ({e}).")
        return {}


def get_run_ids(res):
    try:
        ids = list(res.get_all_run_ids())
        return ids if ids else [0]
    except Exception:
        return [0]


def count_rows(path):
    if not os.path.exists(path):
        return 0
    with open(path, newline="", encoding="utf-8") as fh:
        return max(sum(1 for _ in fh) - 1, 0)


def extract_run(res, run_id, sample_id):
    f, s11_db = load_s11(res, run_id)
    fr, rl_min, f_low, f_high, bw = bandwidth_around_min(f, s11_db, RL_LIMIT_DB)
    gamma = 10.0 ** (rl_min / 20.0)
    vswr = (1 + gamma) / (1 - gamma) if gamma < 1 else float("inf")
    gain = load_gain(res, run_id, fr)
    cover = band_coverage_percent(f, s11_db, BAND_GHZ, RL_LIMIT_DB)

    in_band = BAND_GHZ[0] <= fr <= BAND_GHZ[1]
    ok_core = in_band and rl_min <= RL_LIMIT_DB and bw >= BW_MIN_MHZ
    ok_gain = (not np.isnan(gain)) and gain >= GAIN_MIN_DBI

    params = get_params(res, run_id)
    row = {
        "sample_id": sample_id,
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    for k in PARAM_NAMES:
        row[k] = params.get(k, float("nan"))
    row.update({
        "fr_ghz": round(fr, 5),
        "rl_min_db": round(rl_min, 3),
        "vswr": round(vswr, 4),
        "bw_mhz": round(bw, 2),
        "f_low_ghz": round(f_low, 5) if not np.isnan(f_low) else float("nan"),
        "f_high_ghz": round(f_high, 5) if not np.isnan(f_high) else float("nan"),
        "band_cover_pct": round(cover, 1),
        "gain_dbi": round(gain, 3) if not np.isnan(gain) else float("nan"),
        "feasible_wo_gain": int(ok_core),
        "feasible_all": int(ok_core and ok_gain),
    })
    return row, f, s11_db


def export_all(project_path, sample_id=None):
    os.makedirs(os.path.join(OUT_DIR, "curves"), exist_ok=True)
    dataset_path = os.path.join(OUT_DIR, "dataset.csv")

    proj = cst.results.ProjectFile(project_path, allow_interactive=True)
    res = proj.get_3d()

    next_id = count_rows(dataset_path) + 1 if sample_id is None else int(sample_id)
    rows = []
    for k, run_id in enumerate(get_run_ids(res)):
        sid = next_id + k
        print(f"Mengekspor run {run_id} sebagai sampel {sid} ...")
        row, f, s11_db = extract_run(res, run_id, sid)
        rows.append(row)

        curve_path = os.path.join(OUT_DIR, "curves", f"s11_sample{sid}_run{run_id}.csv")
        with open(curve_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["freq_ghz", "s11_db"])
            w.writerows(zip(np.round(f, 6), np.round(s11_db, 4)))

    write_header = not os.path.exists(dataset_path)
    with open(dataset_path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        if write_header:
            w.writeheader()
        w.writerows(rows)

    for r in rows:
        print(f"  sampel {r['sample_id']}: fr={r['fr_ghz']} GHz, RL={r['rl_min_db']} dB, "
              f"BW={r['bw_mhz']} MHz, gain={r['gain_dbi']} dBi")
    print(f"Selesai. Dataset: {dataset_path}")


def main():
    ap = argparse.ArgumentParser(description="Ekspor hasil CST ke CSV")
    ap.add_argument("--project", default=PROJECT_PATH)
    ap.add_argument("--sample-id", default=None, help="nomor sampel awal (default: otomatis)")
    ap.add_argument("--list", action="store_true", help="tampilkan item result tree lalu keluar")
    args = ap.parse_args()

    if args.list:
        proj = cst.results.ProjectFile(args.project, allow_interactive=True)
        for item in proj.get_3d().get_tree_items():
            print(item)
        return

    export_all(args.project, args.sample_id)


if __name__ == "__main__":
    main()