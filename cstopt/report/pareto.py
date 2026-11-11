"""
Kurva Pareto trade-off: BW terhadap gain dan cakupan pita terhadap gain, dari satu atau lebih run.

  py main.py pareto                                       semua desain di designs/ yang datanya sudah ada
  py main.py pareto --runs MicrostripAntena MicrostripAntena_RO4350B
  py main.py pareto --all                                 ikut tampilkan sampel yang tidak memenuhi syarat (abu abu)
  py main.py pareto --ref 0 0                             titik acuan hypervolume (sumbu x, gain)

Hanya sampel yang resonansinya di dalam pita dan RL minimum <= batas yang diikutkan. Titik Pareto = tidak ada sampel lain
yang sekaligus lebih baik pada kedua sumbu (keduanya dimaksimalkan). Front digambar sebagai tangga (bukan garis lurus,
karena trade-off tidak harus linear), titik knee ditandai bintang, dan hypervolume dicetak per run.
Keluaran: data/_compare/pareto.png, pareto_front.csv, dan pareto_progress.png (hypervolume terhadap jumlah sampel)
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
MIN_FRONT_POINTS = 6          # front lebih pendek dari ini dianggap belum representatif
MIN_RANGE_FRAC = 0.20         # rentang x front minimal 20% rentang x data yang memenuhi syarat


def pareto_front(x, y):
    """Indeks titik non-dominated (x dan y sama sama dimaksimalkan)."""
    order = np.lexsort((-np.asarray(y), -np.asarray(x)))
    best, keep = -np.inf, []
    for i in order:
        if y[i] > best + 1e-12:
            keep.append(i)
            best = y[i]
    return np.array(keep, dtype=int)


def hypervolume_2d(points, ref=(0.0, 0.0)):
    """Hypervolume (luas) dua sumbu yang dimaksimalkan terhadap titik acuan ref.

    Titik yang tidak lebih besar dari ref di kedua sumbu dibuang (kontribusi nol). Sisanya dikurangi ke front, diurutkan
    x menurun (maka y naik): HV = jumlah (x_i - ref_x) * (y_i - y_{i-1}) dengan y_0 = ref_y.
    """
    pts = np.asarray(points, dtype=float).reshape(-1, 2)
    pts = pts[np.isfinite(pts).all(axis=1)]
    pts = pts[(pts[:, 0] > ref[0]) & (pts[:, 1] > ref[1])]
    if len(pts) == 0:
        return 0.0
    f = pts[pareto_front(pts[:, 0], pts[:, 1])]
    f = f[np.argsort(-f[:, 0])]
    hv, y_prev = 0.0, float(ref[1])
    for x, y in f:
        hv += (x - ref[0]) * (y - y_prev)
        y_prev = y
    return float(hv)


def knee_index(fx, fy):
    """Indeks titik knee: jarak terbesar ke garis antara dua ujung front, setelah normalisasi 0..1.
    None bila front kurang dari 3 titik atau kedua ujung berimpit."""
    f = np.column_stack([fx, fy]).astype(float)
    if len(f) < 3:
        return None
    lo, hi = f.min(axis=0), f.max(axis=0)
    z = (f - lo) / np.where(hi - lo > 0, hi - lo, 1.0)
    order = np.argsort(z[:, 0])
    a, b = z[order[0]], z[order[-1]]
    d = b - a
    norm = float(np.hypot(d[0], d[1]))
    if norm == 0:
        return None
    dist = np.abs(d[0] * (z[:, 1] - a[1]) - d[1] * (z[:, 0] - a[0])) / norm
    return int(np.argmax(dist))


def front_warnings(front_x, data_x):
    """Daftar alasan front belum representatif (kosong bila memadai)."""
    why = []
    if len(front_x) < MIN_FRONT_POINTS:
        why.append(f"hanya {len(front_x)} titik (minimal {MIN_FRONT_POINTS})")
    r_data = float(np.max(data_x) - np.min(data_x)) if len(data_x) else 0.0
    r_front = float(np.max(front_x) - np.min(front_x)) if len(front_x) else 0.0
    if r_data > 0 and r_front < MIN_RANGE_FRAC * r_data:
        why.append(f"rentang front {r_front:.1f} hanya {100 * r_front / r_data:.0f}% dari rentang data {r_data:.1f} "
                   f"(minimal {100 * MIN_RANGE_FRAC:.0f}%)")
    return why


def hv_progress(df, ok, xc, ref):
    """Hypervolume setelah tiap sampel ditambahkan berurutan menurut sample_id."""
    d = df.assign(_ok=np.asarray(ok)).sort_values("sample_id")
    xs, ys = d[xc].values.astype(float), d.gain_fr_ieee_dbi.values.astype(float)
    good = d["_ok"].values & np.isfinite(xs) & np.isfinite(ys)
    hv = [hypervolume_2d(np.column_stack([xs[:i][good[:i]], ys[:i][good[:i]]]), ref) for i in range(1, len(d) + 1)]
    return np.arange(1, len(d) + 1), np.array(hv)


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
    ap.add_argument("--ref", nargs=2, type=float, default=[0.0, 0.0], metavar=("X", "GAIN"),
                    help="titik acuan hypervolume: sumbu x (BW atau cakupan) dan gain dBi (default 0 0)")
    ap.add_argument("--out", default=None, help="berkas PNG keluaran (default: data/_compare/pareto.png)")
    args = ap.parse_args()
    ref = (float(args.ref[0]), float(args.ref[1]))

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

    panels = [("bw_mhz", "BW (MHz)", 200.0, "MHz")]
    if any("band_cover_pct" in df.columns for df, _ in data.values()):
        panels.append(("band_cover_pct", f"cakupan pita {band[0]:g} sampai {band[1]:g} GHz (%)", None, "%"))
    fig, axes = plt.subplots(1, len(panels), figsize=(6.2 * len(panels), 5.2), squeeze=False)
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    hv_rows, warns = [], []
    for ax, (xc, xl, xt, unit) in zip(axes[0], panels):
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
            fr = f.iloc[idx].sort_values(xc).reset_index(drop=True)
            ax.step(fr[xc], fr.gain_fr_ieee_dbi, where="post", color=c, lw=1.8, zorder=3)
            ax.plot(fr[xc], fr.gain_fr_ieee_dbi, "o", color=c, ms=6, zorder=3, label=f"front Pareto {run} ({len(fr)})")
            kn = knee_index(fr[xc].values, fr.gain_fr_ieee_dbi.values)
            if kn is not None:
                ax.plot(fr[xc][kn], fr.gain_fr_ieee_dbi[kn], "*", color=c, ms=15, mec="black", zorder=4,
                        label=f"knee {run}: sampel {int(fr.sample_id[kn])}")
            hv = hypervolume_2d(np.column_stack([f[xc], f.gain_fr_ieee_dbi]), ref)
            hv_rows.append((run, xc, unit, hv, len(fr), None if kn is None else int(fr.sample_id[kn])))
            why = front_warnings(fr[xc].values, f[xc].values)
            if why:
                warns.append((run, xc, why))
            if xc == "bw_mhz":
                fronts.append(fr.assign(run=run))
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
    plt.close(fig)

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

    if hv_rows:
        print(f"\nHypervolume (acuan x={ref[0]:g}, gain={ref[1]:g} dBi), makin besar makin baik:")
        for run, xc, unit, hv, n, kn in hv_rows:
            ktxt = f", knee sampel {kn}" if kn is not None else ""
            print(f"  {run:28s} {xc:15s} {hv:10.1f} {unit}*dBi  (front {n} titik{ktxt})")
    for run, xc, why in warns:
        print(f"[peringatan] front {run} ({xc}) belum representatif: " + "; ".join(why)
              + ". Tambah sampel dengan --sweep atau --focus.")

    # kemajuan hypervolume terhadap jumlah sampel
    fig2, axes2 = plt.subplots(1, len(panels), figsize=(6.2 * len(panels), 4.2), squeeze=False)
    for ax, (xc, xl, xt, unit) in zip(axes2[0], panels):
        for k, (run, (df, ok)) in enumerate(data.items()):
            if xc not in df.columns:
                continue
            n, hv = hv_progress(df, ok, xc, ref)
            ax.plot(n, hv, color=colors[k % len(colors)], lw=1.8, label=run)
        ax.set_xlabel("jumlah sampel (urut sample_id)")
        ax.set_ylabel(f"hypervolume ({unit} x dBi)")
        ax.set_title(xl, fontsize=10)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc="best")
    fig2.suptitle("Kemajuan hypervolume")
    fig2.tight_layout()
    prog_png = os.path.splitext(out_png)[0] + "_progress.png"
    fig2.savefig(prog_png, dpi=130)
    plt.close(fig2)
    print(f"Kemajuan: {prog_png}")


if __name__ == "__main__":
    main()
