"""
Memeriksa bahwa kurva S11 di data/<project>/curves/ benar-benar kurva hasil CST untuk baris yang sama
di batch_lhs.csv (bukan kurva buatan, bukan dari proyek lain).

  py main.py curves
  py main.py curves --run-name MicrostripAntena

Idenya: kolom s11_at_f0_db, fr_ghz, rl_min_db, dan band_cover_pct di CSV dihitung dari S11 asli CST saat
simulasi. Kurva di folder curves/ disimpan dari S11 yang sama. Jika keduanya berasal dari sumber yang sama,
nilai yang dihitung ulang dari kurva harus cocok dengan kolom CSV. Kurva sintetis atau salah folder tidak akan cocok.
"""
import argparse
import os
import sys

from cstopt import paths
from cstopt.loader import default_run_name, module_for_run

import numpy as np
import pandas as pd



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-name", default=None, help="default: RUN_NAME desain bawaan")
    ap.add_argument("--design", default=None, help="file desain untuk f0, pita, dan batas RL (bawaan: dicocokkan dari nama run)")
    ap.add_argument("--f0", type=float, default=None, help="GHz; bawaan: CST[\"f0_ghz\"] desain")
    ap.add_argument("--band", type=float, nargs=2, default=None, help="GHz; bawaan: BAND_GHZ desain")
    ap.add_argument("--limit", type=float, default=None, help="dB; bawaan: CST[\"rl_limit_db\"] desain, atau -10")
    args = ap.parse_args()

    run = args.run_name or default_run_name(args.design)       # folder data mengikuti --design, bukan desain bawaan
    mod = module_for_run(run, args.design)                 # f0, pita, dan batas RL harus sama dengan yang dipakai saat ekspor (dari file desain)
    cst_cfg = getattr(mod, "CST", None) or {}
    if args.f0 is None:
        args.f0 = float(cst_cfg.get("f0_ghz", 3.5))
    if args.band is None:
        args.band = tuple(getattr(mod, "BAND_GHZ", (3.3, 3.7)))
    if args.limit is None:
        args.limit = float(cst_cfg.get("rl_limit_db", -10.0))
    print(f"Desain {getattr(mod, 'NAME', '?')}: f0 {args.f0:g} GHz, pita {args.band[0]:g} sampai {args.band[1]:g} GHz, batas RL {args.limit:g} dB")

    rd = paths.run_dir(run)
    csv_path = os.path.join(rd, "batch_lhs.csv")
    cdir = os.path.join(rd, "curves")
    if not os.path.exists(csv_path) or not os.path.isdir(cdir):
        sys.exit(f"Tidak ditemukan: {csv_path} atau {cdir}")
    df = pd.read_csv(csv_path)

    rows, missing = [], []
    for r in df.itertuples():
        p = os.path.join(cdir, f"s11_sample{int(r.sample_id)}.csv")
        if not os.path.exists(p):
            missing.append(int(r.sample_id))
            continue
        c = pd.read_csv(p)
        f, s = c.iloc[:, 0].values, c.iloc[:, 1].values
        i = int(np.argmin(s))
        grid = np.linspace(args.band[0], args.band[1], 401)
        cover = 100.0 * np.mean(np.interp(grid, f, s) <= args.limit)
        rows.append({"id": int(r.sample_id), "n_pts": len(f), "f_min": f.min(), "f_max": f.max(),
                     "d_s11_f0": abs(np.interp(args.f0, f, s) - r.s11_at_f0_db),
                     "d_fr": abs(f[i] - r.fr_ghz), "d_rl": abs(s[i] - r.rl_min_db),
                     "d_cover": abs(cover - r.band_cover_pct)})
    if missing:
        print(f"[MASALAH] {len(missing)} sampel tanpa file kurva: {missing[:15]}")
    if not rows:
        sys.exit("Tidak ada kurva yang bisa diperiksa.")
    R = pd.DataFrame(rows)

    tol = {"d_s11_f0": 0.01, "d_fr": 0.006, "d_rl": 0.01, "d_cover": 0.5}
    print(f"Diperiksa: {len(R)} kurva | titik per kurva: {R.n_pts.min()}..{R.n_pts.max()} | "
          f"rentang frekuensi: {R.f_min.min():.2f}..{R.f_max.max():.2f} GHz\n")
    print(f"{'pemeriksaan':34s} {'selisih maks':>13s} {'batas':>7s} {'sampel di luar batas':>22s}")
    ok_all = True
    for k, label in [("d_s11_f0", f"S11 di {args.f0} GHz vs s11_at_f0_db"), ("d_fr", "frekuensi minimum vs fr_ghz"),
                     ("d_rl", "nilai minimum vs rl_min_db"), ("d_cover", "cakupan pita vs band_cover_pct")]:
        bad = R.id[R[k] > tol[k]].tolist()
        ok_all &= not bad
        print(f"{label:34s} {R[k].max():13.4g} {tol[k]:7g} {len(bad):22d}" + (f"  {bad[:8]}" if bad else ""))
    print("\nKESIMPULAN:", "kurva KONSISTEN dengan data CST di CSV (asli, folder benar)." if ok_all and not missing
          else "ADA KETIDAKCOCOKAN: kurva mungkin bukan dari simulasi yang sama (buatan, kadaluarsa, atau salah folder).")
    return 0 if ok_all and not missing else 1


if __name__ == "__main__":
    sys.exit(main())
