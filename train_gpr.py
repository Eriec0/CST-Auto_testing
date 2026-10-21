"""
Melatih dan mengevaluasi surrogate GPR untuk SEMUA kolom target di konfigurasi desain.

  py train_gpr.py                                 desain default (design_uslot_dgs), kernel RBF-ARD
  py train_gpr.py --kernel both                   bandingkan RBF vs Matern 5/2
  py train_gpr.py --design design_lain --seed 3

Keluaran (folder export/):
  gpr_metrics.csv       R2, RMSE, MAE (split 80/20) + R2/RMSE cross-validation + kalibrasi 95%
  gpr_sensitivity.csv   relevansi tiap parameter (1/length-scale ARD, dinormalisasi)
  gpr_parity.png        prediksi vs aktual pada data uji
  gpr_models.joblib     model yang dilatih pada SELURUH data (untuk dipakai ulang)

Catatan membaca hasil:
  - Dengan N ~ 80, data uji hanya ~16 titik: R2 test sangat berfluktuasi. Percayai R2 cross-validation
    (pakai semua data) lebih daripada R2 test tunggal.
  - cov95 = porsi titik uji yang jatuh dalam +-1,96 sigma prediksi. Idealnya ~0,95;
    jauh di bawah itu berarti model terlalu percaya diri (ketidakpastiannya tidak bisa dipercaya).
"""
import argparse
import os

import joblib
import matplotlib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, train_test_split

import ml_core as mc

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def rmse(y, p):
    return float(np.sqrt(mean_squared_error(y, p)))


def evaluate(d, df, kind, seed, test_size, n_cv, restarts):
    X = d.to_unit(df[d.params].values)
    idx = np.arange(len(df))
    tr, te = train_test_split(idx, test_size=test_size, random_state=seed)
    rows, parity, sens, final = [], {}, {}, {}
    for col in d.model_columns:
        y = df[col].values.astype(float)
        fin = np.isfinite(y)
        fwd, inv = d.T(col)
        trm, tem = [i for i in tr if fin[i]], [i for i in te if fin[i]]
        gp = mc.fit_gp(X[trm], fwd(y[trm]), kind, restarts, seed)
        mu, sd = gp.predict(X[tem], return_std=True)
        pred = inv(mu)
        cov = float(np.mean(np.abs(fwd(y[tem]) - mu) <= 1.96 * np.maximum(sd, 1e-9)))
        parity[col] = (y[tem], pred, inv(mu - 1.96 * sd), inv(mu + 1.96 * sd))

        # cross-validation pada seluruh data (prediksi out-of-fold)
        fi = np.where(fin)[0]
        oof = np.full(len(fi), np.nan)
        for a, b in KFold(n_cv, shuffle=True, random_state=seed).split(fi):
            g = mc.fit_gp(X[fi[a]], fwd(y[fi[a]]), kind, max(1, restarts // 2), seed)
            oof[b] = inv(g.predict(X[fi[b]]))
        zero_frac = float(np.mean(y[fin] == 0.0))

        full = mc.fit_gp(X[fi], fwd(y[fi]), kind, restarts, seed)
        final[col] = full
        ls = mc.lengthscales(full)
        if ls.size == len(d.params):
            rel = 1.0 / ls
            sens[col] = rel / rel.sum()

        rows.append({"target": col, "n_train": len(trm), "n_test": len(tem),
                     "R2_test": r2_score(y[tem], pred), "RMSE_test": rmse(y[tem], pred),
                     "MAE_test": mean_absolute_error(y[tem], pred), "cov95": cov,
                     "R2_cv": r2_score(y[fi], oof), "RMSE_cv": rmse(y[fi], oof),
                     "y_std": float(np.std(y[fin])), "zero_frac": zero_frac})
    return pd.DataFrame(rows), parity, pd.DataFrame(sens, index=d.params), final


def plot_parity(parity, path):
    n = len(parity)
    cols = min(4, n)
    rows = int(np.ceil(n / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(4 * cols, 3.6 * rows), squeeze=False)
    for ax, (col, (y, p, lo, hi)) in zip(axs.ravel(), parity.items()):
        ax.errorbar(y, p, yerr=[np.maximum(p - lo, 0), np.maximum(hi - p, 0)], fmt="o", ms=4,
                    alpha=0.7, elinewidth=0.8)
        lim = [min(y.min(), p.min()), max(y.max(), p.max())]
        ax.plot(lim, lim, "k--", lw=0.8)
        ax.set_title(col, fontsize=10)
        ax.set_xlabel("aktual")
        ax.set_ylabel("prediksi (+-1,96 sigma)")
    for ax in axs.ravel()[n:]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="Latih & evaluasi surrogate GPR")
    ap.add_argument("--design", default="design_uslot_dgs")
    ap.add_argument("--kernel", default="rbf", choices=["rbf", "matern52", "both"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--test-size", type=float, default=0.2)
    ap.add_argument("--cv", type=int, default=5)
    ap.add_argument("--restarts", type=int, default=5)
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()

    d = mc.load_design(args.design)
    df = mc.load_dataset(d)
    out = os.path.dirname(d.dataset)
    print(f"Desain: {d.name} | {len(df)} sampel | {len(d.params)} parameter | "
          f"{len(d.model_columns)} target")

    kinds = ["rbf", "matern52"] if args.kernel == "both" else [args.kernel]
    pd.set_option("display.width", 200)
    for kind in kinds:
        met, parity, sens, final = evaluate(d, df, kind, args.seed, args.test_size, args.cv, args.restarts)
        print(f"\n=== Kernel {kind.upper()} (ARD) ===")
        print(met.round(3).to_string(index=False))
        flag = met[(met["R2_cv"] < 0.85)]
        if len(flag):
            print(f"\nTarget dengan R2_cv < 0,85 (target proposal): {', '.join(flag['target'])}")
        zi = met[met["zero_frac"] > 0.3]
        if len(zi):
            print("Peringatan: banyak nilai persis 0 pada:", ", ".join(zi["target"]),
                  "(distribusi 'nol-menggelembung' sulit dipelajari GPR).")
        if not sens.empty:
            oc = d.objective["column"]
            print(f"\nParameter paling berpengaruh pada '{oc}' (relevansi ARD):")
            print(sens[oc].sort_values(ascending=False).head(5).round(3).to_string())

        suffix = "" if len(kinds) == 1 else f"_{kind}"
        met.to_csv(os.path.join(out, f"gpr_metrics{suffix}.csv"), index=False)
        sens.to_csv(os.path.join(out, f"gpr_sensitivity{suffix}.csv"))
        if not args.no_plot:
            plot_parity(parity, os.path.join(out, f"gpr_parity{suffix}.png"))
        joblib.dump({"design": d.name, "kernel": kind, "params": d.params,
                     "lo": d.lo, "hi": d.hi, "models": final},
                    os.path.join(out, f"gpr_models{suffix}.joblib"))
    print(f"\nFile hasil disimpan di: {out}")


if __name__ == "__main__":
    main()
