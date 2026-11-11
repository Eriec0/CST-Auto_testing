"""
Seed awal untuk desain/substrat baru dari hasil desain lain (transfer antar substrat).

  py tools/make_seeds.py --from uslot_dgs_fr4 --to uslot_dgs_ro4350b --n 10

Memilih desain terbaik dari dataset sumber (hanya membaca batch_lhs.csv, tanpa kurva): beberapa dengan BW terbesar,
beberapa dengan cakupan pita terbesar, dan beberapa di tengah pita. Panjang diskalakan dengan
s = sqrt(eeff_sumber / eeff_tujuan) (Hammerstad, memakai SUBSTRATE di kedua file desain) agar frekuensi resonansi
mendekati sama; gap gU dan gD tidak diskalakan. Hasil dijepit ke BOUNDS tujuan dan disaring aturan geometri.
Keluaran: data/<RUN tujuan>/samples/seed_from_<sumber>.csv (siap untuk `py main.py run --samples ...`).
"""
import argparse
import math
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cstopt import paths                       # noqa: E402
from cstopt.loader import load_design_module   # noqa: E402

SCALE = {"Lp", "Wp", "LU", "WU", "LI", "LD", "WD", "PU", "PD"}


def eeff(er, h, w):
    return (er + 1) / 2 + (er - 1) / 2 * (1 + 12 * h / w) ** -0.5


def main():
    ap = argparse.ArgumentParser(description="Seed dari desain lain")
    ap.add_argument("--from", dest="src", default="uslot_dgs_fr4")
    ap.add_argument("--to", dest="dst", required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    S, D = load_design_module(args.src), load_design_module(args.dst)
    path = S.DATASET_CSV
    if not os.path.exists(path):
        sys.exit(f"Dataset sumber tidak ada: {path}")
    df = pd.read_csv(path)
    lo, hi = S.BAND_GHZ
    ok = df[(df.rl_min_db <= -10) & (df.d_peak_fr_dbi >= 4) & df.fr_ghz.between(lo, hi)]
    if ok.empty:
        sys.exit("Tidak ada sampel feasible di dataset sumber.")
    n_bw, n_cov = max(1, round(args.n * 0.5)), max(1, round(args.n * 0.3))
    picks = list(ok.sort_values("bw_mhz", ascending=False).head(n_bw).sample_id)
    picks += [i for i in ok.sort_values("band_cover_pct", ascending=False).sample_id if i not in picks][:n_cov]
    mid = ok[ok.fr_ghz.between(0.5 * (lo + hi) - 0.07, 0.5 * (lo + hi) + 0.07)].sort_values("bw_mhz", ascending=False)
    picks += [i for i in mid.sample_id if i not in picks][:args.n - len(picks)]
    picks += [i for i in ok.sort_values("bw_mhz", ascending=False).sample_id if i not in picks][:args.n - len(picks)]

    rows, info = [], []
    for sid in picks[:args.n]:
        r = df[df.sample_id == sid].iloc[0]
        s = math.sqrt(eeff(S.SUBSTRATE["er"], S.SUBSTRATE["h"], r.Wp) / eeff(D.SUBSTRATE["er"], D.SUBSTRATE["h"], r.Wp))
        p = {}
        for k in D.PARAM_NAMES:
            v = float(r[k]) * (s if k in SCALE else 1.0)
            a, b = D.BOUNDS[k]
            p[k] = round(min(max(v, a), b), D.DECIMALS)
        bad = D.geometry_problems(p)
        info.append((int(sid), r.fr_ghz, r.bw_mhz, r.band_cover_pct, s, "valid" if not bad else "dilewati: " + "; ".join(bad)))
        if not bad:
            rows.append(p)
    out = pd.DataFrame(rows)
    out.insert(0, "sample_id", range(1, len(out) + 1))
    path_out = args.out or os.path.join(paths.samples_dir(D.RUN_NAME), f"seed_from_{args.src}.csv")
    os.makedirs(os.path.dirname(path_out), exist_ok=True)
    out.to_csv(path_out, index=False)
    print(f"Sumber: {args.src} ({len(df)} sampel, {len(ok)} feasible) -> tujuan: {args.dst}")
    print("  asal  fr_ghz   BW   cakupan%  skala  status")
    for i, f, b, c, s, st in info:
        print(f"  {i:4d}  {f:.3f}  {b:5.1f}  {c:6.1f}    {s:.3f}  {st}")
    print(f"\n{len(out)} seed disimpan: {path_out}")


if __name__ == "__main__":
    main()
