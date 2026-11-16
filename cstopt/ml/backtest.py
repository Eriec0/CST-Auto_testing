"""
Backtest Bayesian Optimization pada dataset yang SUDAH ADA (tanpa simulasi baru).

Ide: dataset dianggap "kumpulan semua desain yang mungkin". BO mulai dari n0 sampel acak,
lalu pada tiap langkah memilih SATU sampel dari yang belum 'dievaluasi' dengan acquisition-nya,
dan dibandingkan dengan pemilihan acak. Diulang beberapa kali dengan titik awal berbeda.

  py main.py backtest                       20 ulangan, mulai 10 sampel, 30 langkah
  py main.py backtest --reps 30 --n0 15 --steps 40

Cara membaca:
  - Jika kurva BO turun/naik lebih cepat dan lebih rendah/tinggi dari acak, GPR+EI memang memandu
    pencarian dengan baik pada dataset ini.
  - 'feasible ditemukan' = persentase ulangan yang sudah menemukan sampel memenuhi semua constraint.
  - Ini hanya MENGUJI strategi pada titik yang tersedia (pool diskret), bukan ruang kontinu penuh.
"""
import argparse
import os

import matplotlib
import numpy as np

from cstopt.ml import core as mc

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def best_curve(d, df, order):
    sub = df.iloc[order].reset_index(drop=True)
    return mc.convergence(d, sub)


def main():
    ap = argparse.ArgumentParser(description="Backtest BO vs pencarian acak pada dataset yang ada")
    ap.add_argument("--design", default=None, help="nama file di designs/ (default: desain bawaan)")
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--n0", type=int, default=10, help="jumlah sampel awal acak")
    ap.add_argument("--steps", type=int, default=30, help="jumlah langkah evaluasi tambahan")
    ap.add_argument("--kernel", default="rbf", choices=["rbf", "matern52"])
    ap.add_argument("--restarts", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--xi", type=float, default=0.01)
    ap.add_argument("--region-auto", default=None, metavar="K:MARGIN",
                    help="batasi pilihan ke region otomatis di sekitar K desain terbaik (seperti suggest --region-auto)")
    ap.add_argument("--region-adapt", action="store_true", help="batasi pilihan ke trust region adaptif (P2-4)")
    ap.add_argument("--adapt-every", type=int, default=5,
                    help="region dihitung ulang tiap N evaluasi (meniru satu batch suggest; default 5)")
    ap.add_argument("--stage", type=int, default=None,
                    help="paksa tahap BO (1, 2, ...); default: dipilih otomatis dari data")
    args = ap.parse_args()
    if args.region_auto and args.region_adapt:
        ap.error("pilih salah satu: --region-auto atau --region-adapt")
    mode = "adapt" if args.region_adapt else ("auto" if args.region_auto else "none")

    d = mc.load_design(args.design)
    if args.stage is not None:
        d.force_stage = args.stage - 1
    df = mc.load_dataset(d)
    print(f"Tahap BO: {d.stage_idx + 1}/{len(d.stages)} ({d.stage_name})")
    oc = d.objective["column"]
    n = len(df)
    steps = min(args.steps, n - args.n0)
    # backtest hanya butuh model untuk objective dan constraint (jauh lebih cepat daripada semua target)
    cols = list(dict.fromkeys([d.objective["column"]] + [c["column"] for c in d.constraints]))
    Xall = d.to_unit(df[d.params].values)

    ok_all = mc.feasible_mask(d, df) & np.isfinite(df[oc].values)
    if not ok_all.any():
        raise SystemExit("Tidak ada sampel yang memenuhi semua constraint di dataset; backtest tidak bermakna.")
    opt = (df[oc].values[ok_all].max() if d.sign > 0 else df[oc].values[ok_all].min())
    print(f"Dataset {n} sampel, {int(ok_all.sum())} feasible. Optimum dalam dataset ({oc}): {opt:.4f}")

    rng_master = np.random.default_rng(args.seed)
    bo_curves, rd_curves = [], []
    sides, n_fallback, n_steps_total = [], 0, 0
    Pall = df[d.params].values.astype(float)
    for rep in range(args.reps):
        rng = np.random.default_rng(rng_master.integers(1 << 31))
        init = list(rng.choice(n, args.n0, replace=False))
        # --- BO
        sel = list(init)
        reg, state, side_traj = None, None, []
        for step in range(steps):
            sub = df.iloc[sel].reset_index(drop=True)
            models = mc.fit_models(d, sub, cols, args.kernel, args.restarts, int(rng.integers(1 << 31)))
            f_best, _ = mc.best_feasible(d, sub)
            xi = args.xi * float(np.nanstd(sub[oc].values))
            rest = np.array([i for i in range(n) if i not in set(sel)])
            if mode != "none":
                if step % args.adapt_every == 0:            # region ditetapkan per batch, seperti satu panggilan suggest
                    if mode == "adapt":
                        reg, state, _ = mc.region_adapt(d, sub, state, xi)
                        side_traj.append(state["side"])
                    else:
                        k_, m_ = args.region_auto.split(":")
                        reg = mc.region_auto(d, sub, int(k_), float(m_))
                inreg = np.ones(len(rest), bool)
                for j, p in enumerate(d.params):
                    inreg &= (Pall[rest, j] >= reg[p][0] - 1e-9) & (Pall[rest, j] <= reg[p][1] + 1e-9)
                n_steps_total += 1
                if inreg.any():
                    rest = rest[inreg]
                else:
                    n_fallback += 1                         # tidak ada sampel di region: pakai seluruh sisa kumpulan
            acq, _, _ = mc.acquisition(d, models, Xall[rest], f_best, xi)
            sel.append(int(rest[int(np.argmax(acq))]))
        bo_curves.append(best_curve(d, df, sel))
        sides.append(side_traj)
        # --- acak
        rest = np.array([i for i in range(n) if i not in set(init)])
        rnd = list(init) + list(rng.permutation(rest)[:steps])
        rd_curves.append(best_curve(d, df, rnd))
        print(f"ulangan {rep + 1}/{args.reps} selesai", end="\r")
    print()

    bo, rd = np.array(bo_curves), np.array(rd_curves)
    ks = [k for k in (args.n0, args.n0 + 5, args.n0 + 10, args.n0 + 20, args.n0 + steps)
          if k <= args.n0 + steps]
    print(f"\n{'evaluasi':>9} | {'BO median':>10} {'acak median':>12} | {'BO capai optimum':>16} {'acak capai optimum':>18}"
          f" | {'BO feasible':>11} {'acak feasible':>13}")
    for k in sorted(set(ks)):
        b, r = bo[:, k - 1], rd[:, k - 1]
        med = lambda a: "-" if np.all(np.isnan(a)) else f"{np.nanmedian(a):.3f}"          # noqa: E731
        hit = lambda a: 100 * np.mean(np.isclose(a, opt, atol=1e-6))                       # noqa: E731
        print(f"{k:9d} | {med(b):>10} {med(r):>12} | {hit(b):15.0f}% {hit(r):17.0f}%"
              f" | {100 * np.mean(~np.isnan(b)):10.0f}% {100 * np.mean(~np.isnan(r)):12.0f}%")
    print("\n'capai optimum' = persentase ulangan yang sudah menemukan sampel terbaik di dataset. "
          "Bandingkan BO vs acak pada jumlah evaluasi yang sama;\nperbedaan kecil dengan ulangan sedikit "
          "belum bermakna (dataset ini punya satu titik terbaik yang menonjol).")

    if mode != "none":
        print(f"\nRegion ({mode}): pilihan dibatasi ke sampel di dalam region; fallback ke seluruh sisa kumpulan pada "
              f"{n_fallback} dari {n_steps_total} langkah ({100 * n_fallback / max(n_steps_total, 1):.0f}%).")
        print(f"Catatan: kumpulan sampel diskret dan sudah terkumpul dekat desain terbaik; replay ini hanya uji kewajaran, "
              f"bukan pembuktian untuk ruang kontinu.")
    if mode == "adapt":
        arr = np.array(sides, float)
        print("Lintasan sisi region (median antar ulangan, per batch): " + ", ".join(f"{v:.2f}" for v in np.median(arr, axis=0))
              + f" | min {arr.min():.2f}, maks {arr.max():.2f}")
    tag = "" if mode == "none" else f"_region_{mode}"
    os.makedirs(d.models_dir, exist_ok=True)
    import pandas as pd
    pd.DataFrame({"evaluasi": np.arange(1, bo.shape[1] + 1), "bo_median": np.nanmedian(bo, axis=0),
                  "bo_q25": np.nanpercentile(bo, 25, axis=0), "bo_q75": np.nanpercentile(bo, 75, axis=0),
                  "bo_capai_optimum_pct": [100 * np.mean(np.isclose(bo[:, k], opt, atol=1e-6)) for k in range(bo.shape[1])],
                  "acak_median": np.nanmedian(rd, axis=0)}).round(4).to_csv(
        os.path.join(d.models_dir, f"backtest{tag}.csv"), index=False)

    x = np.arange(1, bo.shape[1] + 1)
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    for arr, lab, c in ((bo, "BO (GPR + cEI)", "C0"), (rd, "acak", "C1")):
        med = np.nanmedian(arr, axis=0)
        lo, hi = np.nanpercentile(arr, 25, axis=0), np.nanpercentile(arr, 75, axis=0)
        ax.plot(x, med, label=lab, color=c)
        ax.fill_between(x, lo, hi, color=c, alpha=0.2)
    ax.axhline(opt, color="gray", ls=":", lw=0.9, label="optimum dalam dataset")
    ax.axvline(args.n0 + 0.5, color="gray", ls="--", lw=0.7)
    ax.set_xlabel("jumlah evaluasi")
    ax.set_ylabel(f"{oc} terbaik (feasible)")
    ax.legend()
    ax.set_title(f"Backtest ({args.reps} ulangan; garis=median, area=IQR)")
    fig.tight_layout()
    os.makedirs(d.figures_dir, exist_ok=True)
    path = os.path.join(d.figures_dir, f"bo_backtest{tag}.png")
    fig.savefig(path, dpi=130)
    print(f"\nGambar: {path}")


if __name__ == "__main__":
    main()