"""
Kurva Pareto trade-off: BW terhadap gain dan cakupan pita terhadap gain, dari satu atau lebih run.

  py main.py pareto                                       semua desain di designs/ yang datanya sudah ada
  py main.py pareto --runs MicrostripAntena MicrostripAntena_RO4350B
  py main.py pareto --all                                 ikut tampilkan sampel yang tidak memenuhi syarat (abu abu)

Hanya sampel yang resonansinya di dalam pita dan RL minimum <= batas yang diikutkan. Titik Pareto = tidak ada sampel lain
yang sekaligus lebih baik pada kedua sumbu (keduanya dimaksimalkan).
Keluaran: data/_compare/pareto.png dan data/_compare/pareto_front.csv
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                        # noqa: E402
import pandas as pd                       # noqa: E402

from cstopt import paths                  # noqa: E402
from cstopt.loader import load_design_module   # noqa: E402

NEED = ["sample_id", "fr_ghz", "rl_min_db", "bw_mhz", "gain_fr_ieee_dbi"]
OPT = ["band_cover_pct", "eta_rad_fr", "d_peak_fr_dbi"]


def pareto_front(x, y):
    """Indeks titik non-dominated (x dan y sama sama dimaksimalkan)."""
    order = np.lexsort((-np.asarray(y), -np.asarray(x)))
    best, keep = -np.inf, []
    for i in order:
        if y[i] > best + 1e-12:
            keep.append(i)
            best = y[i]
    return np.array(keep, dtype=int)


def default_runs():
    runs = []
    for name in paths.list_designs():
        try:
            r = load_design_module(name).RUN_NAME
        except Exception:
            continue
        if r not in runs and os.path.exists(os.path.join(paths.run_dir(r), "batch_lhs.csv")):
            runs.append(r)
    return runs


def main():
    ap = argparse.ArgumentParser(description="Kurva Pareto BW dan gain")
    ap.add_argument("--runs", nargs="+", default=None, help="nama run (folder di data/); default: semua desain yang datanya ada")
    ap.add_argument("--band", nargs=2, type=float, default=None, metavar=("LO", "HI"), help="pita fr GHz (default: BAND_GHZ desain bawaan)")
    ap.add_argument("--rl-limit", type=float, default=-10.0)
    ap.add_argument("--min-d", type=float, default=None, help="syarat directivity minimum (dBi), opsional")
    ap.add_argument("--all", action="store_true", help="tampilkan juga sampel yang tidak memenuhi syarat")
    ap.add_argument("--out", default=None, help="berkas PNG keluaran (default: data/_compare/pareto.png)")
    args = ap.parse_args()

    band = tuple(args.band) if args.band else tuple(load_design_module().BAND_GHZ)
    runs = args.runs or default_runs()
    if not runs:
        sys.exit("Tidak ada run dengan batch_lhs.csv. Jalankan simulasi dulu atau sebutkan --runs.")
    out_png = args.out or os.path.join(paths.DATA_DIR, "_compare", "pareto.png")
    os.makedirs(os.path.dirname(out_png), exist_ok=True)

    data, fronts = {}, []
    print(f"Pita fr {band[0]} sampai {band[1]} GHz, RL minimum <= {args.rl_limit:g} dB"
          + (f", D >= {args.min_d:g} dBi" if args.min_d is not None else ""))
    for run in runs:
        p = os.path.join(paths.run_dir(run), "batch_lhs.csv")
        if not os.path.exists(p):
            print(f"[lewati] {run}: batch_lhs.csv tidak ada")
            continue
        df = pd.read_csv(p)
        miss = [c for c in NEED if c not in df.columns]
        if miss:
            print(f"[lewati] {run}: kolom hilang {miss}")
            continue
        ok = df.fr_ghz.between(*band) & (df.rl_min_db <= args.rl_limit)
        if args.min_d is not None and "d_peak_fr_dbi" in df.columns:
            ok &= df.d_peak_fr_dbi >= args.min_d
        data[run] = (df, ok)
        print(f"  {run}: {len(df)} sampel, {int(ok.sum())} memenuhi syarat")
    if not data:
        sys.exit("Tidak ada data yang bisa diplot.")

    panels = [("bw_mhz", "BW (MHz)", 200.0)]
    if any("band_cover_pct" in df.columns for df, _ in data.values()):
        panels.append(("band_cover_pct", f"cakupan pita {band[0]:g} sampai {band[1]:g} GHz (%)", None))
    fig, axes = plt.subplots(1, len(panels), figsize=(6.2 * len(panels), 5.2), squeeze=False)
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for ax, (xc, xl, xt) in zip(axes[0], panels):
        for k, (run, (df, ok)) in enumerate(data.items()):
            if xc not in df.columns:
                continue
            c = colors[k % len(colors)]
            if args.all:
                ax.scatter(df[~ok][xc], df[~ok].gain_fr_ieee_dbi, s=10, color="#c8c8c8", zorder=1)
            f = df[ok].dropna(subset=[xc, "gain_fr_ieee_dbi"]).reset_index(drop=True)
            if f.empty:
                continue
            ax.scatter(f[xc], f.gain_fr_ieee_dbi, s=22, color=c, alpha=0.55, zorder=2, label=f"{run} ({len(f)})")
            idx = pareto_front(f[xc].values, f.gain_fr_ieee_dbi.values)
            fr = f.iloc[idx].sort_values(xc)
            ax.plot(fr[xc], fr.gain_fr_ieee_dbi, "-o", color=c, lw=1.8, ms=6, zorder=3, label=f"front Pareto {run} ({len(fr)})")
            if xc == "bw_mhz":
                t = fr.assign(run=run)
                fronts.append(t)
        ax.axhline(5.0, color="red", ls="--", lw=1)
        if xt:
            ax.axvline(xt, color="red", ls="--", lw=1)
        ax.set_xlabel(xl)
        ax.set_ylabel("gain di fr (dBi)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc="best")
    fig.suptitle("Trade-off BW dan gain (garis merah = target proposal)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)

    if fronts:
        allf = pd.concat(fronts, ignore_index=True)
        cols = ["run", "sample_id", "bw_mhz", "gain_fr_ieee_dbi", "fr_ghz", "rl_min_db"] + [c for c in OPT if c in allf.columns]
        allf = allf[cols].sort_values(["run", "bw_mhz"], ascending=[True, False])
        csv_path = os.path.splitext(out_png)[0] + "_front.csv"
        allf.round(4).to_csv(csv_path, index=False)
        for run, g in allf.groupby("run", sort=False):
            print(f"\nTitik Pareto {run} (BW terhadap gain), BW menurun:")
            print(g.drop(columns="run").round(3).to_string(index=False))
            best = [f"BW >= {b:g}: gain maks {g[g.bw_mhz >= b].gain_fr_ieee_dbi.max():.2f} dBi" for b in (100, 150, 180) if (g.bw_mhz >= b).any()]
            if best:
                print("  " + "; ".join(best))
        print(f"\nGambar: {out_png}\nTabel : {csv_path}")


if __name__ == "__main__":
    main()
