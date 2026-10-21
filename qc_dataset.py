"""
Pemeriksaan kualitas dataset hasil batch_trials.py (tanpa CST, hanya membaca file).

  py qc_dataset.py                          project MicrostripAntena, dibandingkan dengan export/lhs_samples.csv
  py qc_dataset.py --run-name NamaLain --samples export/lhs_samples.csv --expect-eff 9

Yang diperiksa:
  1. jumlah baris, sampel yang hilang, id/parameter ganda
  2. parameter di hasil sama persis dengan yang diminta di CSV sampel
  3. nilai kosong (NaN) pada kolom inti
  4. kurva efisiensi punya titik sebanyak monitor (n_eff_points)
  5. file kurva S11 ada untuk setiap sampel
  6. selisih |fr - monitor| tidak melebihi setengah langkah monitor; fr yang menempel di tepi sweep
Lalu ringkasan sebaran hasil (bukan pemeriksaan benar/salah).
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
PARAMS = ["Lp", "Wp", "LU", "WU", "gU", "PU", "LI", "LD", "WD", "gD", "PD"]
CORE = ["fr_ghz", "rl_min_db", "bw_mhz", "s11_at_f0_db", "eta_rad", "eta_rad_fr", "d_peak_dbi",
        "d_peak_fr_dbi", "gain_fr_ieee_dbi", "f_mon_fr_ghz", "n_eff_points"]


def main():
    ap = argparse.ArgumentParser(description="QC dataset batch CST")
    ap.add_argument("--run-name", default="MicrostripAntena")
    ap.add_argument("--samples", default=os.path.join(BASE, "export", "lhs_samples.csv"))
    ap.add_argument("--expect-eff", type=int, default=9, help="jumlah titik kurva efisiensi (jumlah monitor)")
    ap.add_argument("--mon-step", type=float, default=0.25)
    args = ap.parse_args()

    rd = os.path.join(BASE, "export", args.run_name)
    csv_path = os.path.join(rd, "batch_lhs.csv")
    if not os.path.exists(csv_path):
        sys.exit(f"Tidak ada: {csv_path}")
    df = pd.read_csv(csv_path)
    req = pd.read_csv(args.samples)
    problems, notes = [], []

    # 1. jumlah, hilang, ganda
    miss = sorted(set(req.sample_id) - set(df.sample_id))
    extra = sorted(set(df.sample_id) - set(req.sample_id))
    print(f"Baris: {len(df)} | sampel diminta: {len(req)}")
    if miss:
        problems.append(f"{len(miss)} sampel belum ada hasilnya: {miss[:15]}{' ...' if len(miss) > 15 else ''}")
    if extra:
        notes.append(f"{len(extra)} sampel ada di hasil tapi tidak di CSV sampel ini (mis. dari BO): {extra[:10]}")
    if df.sample_id.duplicated().any():
        problems.append(f"id ganda: {df.sample_id[df.sample_id.duplicated()].tolist()}")
    key = df[PARAMS].round(6).apply(tuple, axis=1)
    if key.duplicated().any():
        problems.append(f"{int(key.duplicated().sum())} kombinasi parameter ganda di hasil")

    # 2. parameter cocok dengan yang diminta
    m = df.merge(req, on="sample_id", suffixes=("", "_req"))
    bad = [int(r.sample_id) for r in m.itertuples()
           if any(abs(getattr(r, p) - getattr(r, p + "_req")) > 1e-6 for p in PARAMS)]
    if bad:
        problems.append(f"parameter hasil TIDAK sama dengan yang diminta pada sampel: {bad}")

    # 3. kosong
    for c in CORE:
        if c not in df.columns:
            problems.append(f"kolom tidak ada: {c} (CSV dari versi kode lama?)")
        elif df[c].isna().any():
            problems.append(f"{int(df[c].isna().sum())} nilai kosong di {c}")

    # 4. efisiensi
    if "n_eff_points" in df.columns:
        bad_eff = df.sample_id[df.n_eff_points != args.expect_eff].tolist()
        if bad_eff:
            problems.append(f"n_eff_points != {args.expect_eff} pada sampel: {bad_eff[:15]}")
    if {"eta_rad", "eta_rad_fr"} <= set(df.columns) and np.allclose(df.eta_rad, df.eta_rad_fr):
        problems.append("eta_rad == eta_rad_fr di semua baris: monitor multi-frekuensi tidak terbaca")

    # 5. kurva
    cdir = os.path.join(rd, "curves")
    if not os.path.isdir(cdir):
        problems.append(f"folder kurva tidak ada: {cdir}")
    else:
        nocurve = [int(i) for i in df.sample_id if not os.path.exists(os.path.join(cdir, f"s11_sample{int(i)}.csv"))]
        if nocurve:
            problems.append(f"{len(nocurve)} sampel tanpa file kurva S11: {nocurve[:15]}")

    # 6. monitor & tepi
    if {"fr_ghz", "f_mon_fr_ghz"} <= set(df.columns):
        far = df.sample_id[(df.fr_ghz - df.f_mon_fr_ghz).abs() > args.mon_step / 2 + 1e-3].tolist()
        if far:
            problems.append(f"monitor terpilih bukan yang terdekat dengan fr pada sampel: {far[:15]}")
    if "fr_edge_flag" in df.columns and df.fr_edge_flag.sum():
        notes.append(f"{int(df.fr_edge_flag.sum())} sampel punya fr menempel di tepi sweep "
                     f"(id {df.sample_id[df.fr_edge_flag == 1].tolist()[:12]}): resonansi sebenarnya mungkin di luar 2,5-4,5 GHz")

    print("\n== HASIL PEMERIKSAAN ==")
    if problems:
        for p in problems:
            print("  [MASALAH]", p)
    else:
        print("  Semua pemeriksaan lulus.")
    for n in notes:
        print("  [catatan]", n)

    # ringkasan
    if {"fr_ghz", "rl_min_db", "bw_mhz"} <= set(df.columns):
        fr = df.fr_ghz
        print("\n== RINGKASAN SEBARAN ==")
        edges = [2.5, 2.9, 3.3, 3.7, 4.1, 4.6]
        h, _ = np.histogram(fr, edges)
        print("  fr: " + " | ".join(f"{a:.1f}-{b:.1f}: {c}" for a, b, c in zip(edges[:-1], edges[1:], h)))
        print(f"  fr di 3,3-3,7 GHz: {int(((fr >= 3.3) & (fr <= 3.7)).sum())} | RL <= -10 dB: {int((df.rl_min_db <= -10).sum())}"
              f" | BW > 0: {int((df.bw_mhz > 0).sum())} | BW maks: {df.bw_mhz.max():.0f} MHz | BW >= 200: {int((df.bw_mhz >= 200).sum())}")
        if "gain_fr_ieee_dbi" in df.columns:
            g = df.gain_fr_ieee_dbi
            print(f"  gain di fr (IEEE): median {g.median():.2f}, maks {g.max():.2f} dBi | >= 3 dBi: {int((g >= 3).sum())} | >= 5 dBi: {int((g >= 5).sum())}")
        if "d_peak_fr_dbi" in df.columns:
            print(f"  directivity di fr: {df.d_peak_fr_dbi.min():.2f} .. {df.d_peak_fr_dbi.max():.2f} dBi")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
