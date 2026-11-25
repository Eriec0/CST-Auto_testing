"""
Sensitivitas model GPR (P1-4). Tidak butuh CST.

  py main.py sensitivity --design uslot_dgs_fr4
  py main.py sensitivity --design uslot_dgs_ro4350b --region-auto 8:0.15 --n 2048
  py main.py sensitivity --design uslot_dgs_ro4350b --targets bw_mhz fr_ghz gain_fr_ieee_dbi

Dua ukuran yang saling melengkapi, dari model GPR yang dilatih pada data yang ada:
  1. Relevansi ARD: 1/panjang skala kernel tiap parameter, dinormalisasi sehingga jumlahnya 1 per target (sama dengan yang dicetak `train`).
     Panjang skala besar berarti target hampir tidak berubah terhadap parameter itu.
  2. Indeks Sobol orde satu (S1) dan total (ST) dari prediksi MEAN GPR (estimator Saltelli 2010 untuk S1 dan Jansen untuk ST;
     N sampel dasar, N*(d+2) prediksi). ST jauh lebih besar dari S1 berarti pengaruh parameter itu lewat interaksi.
Sobol dihitung di seluruh kotak BOUNDS (atau di --region-auto), termasuk kombinasi yang melanggar aturan geometri; GPR hanya dilatih
pada desain valid, jadi di sana ia mengekstrapolasi. Persentase sampel valid dicetak. Pakai --region-auto untuk sensitivitas lokal di sekitar desain terbaik.
Tafsirkan secara fisik hanya setelah angkanya keluar. Korelasi mentah dengan BW pecahan ikut dicetak sebagai pembanding, karena
korelasi dan sensitivitas model tidak harus berurutan sama.

Keluaran: <models>/sensitivity_ard.csv, <models>/sensitivity_sobol.csv, <figures>/sensitivity.png
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                 # noqa: E402
import pandas as pd                # noqa: E402
from scipy.stats import qmc        # noqa: E402

from cstopt.ml import core as mc   # noqa: E402

# acuan temuan sebelumnya pada FR-4 (135 sampel), dari RENCANA_LANJUTAN.md P1-4
REF_FR4_ARD_BW = {"WU": 0.218, "PU": 0.127, "LU": 0.121, "Lp": 0.118, "LD": 0.108}
REF_FR4_CORR = {"WD": +0.85, "Lp": -0.77}


def ard_relevance(models, params):
    out = {}
    for col, m in models.items():
        r = 1.0 / mc.lengthscales(m.gp)
        out[col] = r / r.sum()
    return pd.DataFrame(out, index=params)


def sobol_indices(d, models, cols, n, seed, lo, hi):
    """S1 dan ST dari prediksi mean GPR. n harus pangkat 2."""
    dn = len(d.params)
    m = int(np.log2(n))
    if 2 ** m != n:
        raise SystemExit("--n harus pangkat 2 (mis. 1024, 2048, 4096).")
    Z = qmc.Sobol(2 * dn, scramble=True, seed=seed).random_base2(m)
    A, B = Z[:, :dn], Z[:, dn:]
    blocks = [A, B]
    for i in range(dn):
        AB = A.copy()
        AB[:, i] = B[:, i]
        blocks.append(AB)
    U = np.vstack(blocks)
    P = lo + U * (hi - lo)
    Xu = d.to_unit(P)
    rows = []
    for col in cols:
        y = d.T(col)[1](models[col].gp.predict(Xu))            # prediksi mean, satuan asli
        fA, fB = y[:n], y[n:2 * n]
        var = np.var(np.concatenate([fA, fB]))
        for i, p in enumerate(d.params):
            fAB = y[(2 + i) * n:(3 + i) * n]
            s1 = np.mean(fB * (fAB - fA)) / var if var > 0 else np.nan
            st = 0.5 * np.mean((fA - fAB) ** 2) / var if var > 0 else np.nan
            rows.append({"target": col, "param": p, "S1": s1, "ST": st})
    valid = float(np.mean([bool(d.is_valid(dict(zip(d.params, r)))) for r in P[:n]]))
    return pd.DataFrame(rows), valid


def heat(ax, M, title):
    im = ax.imshow(M.values.T, aspect="auto", cmap="viridis", vmin=0)
    ax.set_xticks(range(M.shape[0]))
    ax.set_xticklabels(M.index, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(M.shape[1]))
    ax.set_yticklabels(M.columns, fontsize=8)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M.values[i, j]
            ax.text(i, j, f"{v:.2f}", ha="center", va="center", fontsize=6.5, color="white" if v < 0.55 * np.nanmax(M.values) else "black")
    ax.set_title(title, fontsize=9)
    return im


def main():
    ap = argparse.ArgumentParser(description="Sensitivitas ARD dan Sobol dari model GPR")
    ap.add_argument("--design", default=None)
    ap.add_argument("--targets", nargs="+", default=None, help="kolom target (default: objective, fr, gain, RL minimum, cakupan pita)")
    ap.add_argument("--n", type=int, default=2048, help="sampel dasar Sobol, pangkat 2 (default 2048; prediksi N*(d+2))")
    ap.add_argument("--region-auto", default=None, metavar="K:MARGIN", help="hitung Sobol di region sekitar K desain terbaik")
    ap.add_argument("--kernel", default="rbf", choices=["rbf", "matern52"])
    ap.add_argument("--restarts", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    d = mc.load_design(args.design)
    df = mc.load_dataset(d)
    oc = d.objective["column"]
    want = args.targets or [oc, "fr_ghz", "gain_fr_ieee_dbi", "rl_min_db", "band_cover_pct"]
    cols = [c for c in dict.fromkeys(want) if c in df.columns]
    if not cols:
        raise SystemExit("Tidak ada kolom target yang cocok di dataset.")
    print(f"Desain {d.name} | {len(df)} sampel | target: {', '.join(cols)}")
    models = mc.fit_models(d, df, cols, args.kernel, args.restarts, args.seed)

    ard = ard_relevance(models, d.params)
    lo, hi = d.lo.copy(), d.hi.copy()
    if args.region_auto:
        k, m = args.region_auto.split(":")
        reg = mc.region_auto(d, df, int(k), float(m))
        for j, p in enumerate(d.params):
            if p in reg:
                lo[j], hi[j] = reg[p]
        print("Sobol di region: " + ", ".join(f"{p} {a:.2f}:{b:.2f}" for p, (a, b) in reg.items()))
    sob, valid = sobol_indices(d, models, cols, args.n, args.seed, lo, hi)
    print(f"Sobol: N = {args.n}, {args.n * (len(d.params) + 2)} prediksi per target; {100 * valid:.0f}% sampel dasar memenuhi aturan geometri.")

    print(f"\n== RELEVANSI ARD untuk '{oc}' (jumlah = 1) ==")
    print(ard[oc].sort_values(ascending=False).round(3).to_string())
    S = sob[sob.target == oc].set_index("param")[["S1", "ST"]].sort_values("ST", ascending=False)
    print(f"\n== INDEKS SOBOL untuk '{oc}' (S1 = pengaruh sendiri, ST = total termasuk interaksi) ==")
    print(S.round(3).to_string())
    print(f"Jumlah S1 = {S.S1.sum():.2f} (selisih terhadap 1 menunjukkan interaksi dan galat estimasi).")

    # korelasi mentah dengan BW pecahan (pembanding)
    corr = None
    if {"bw_mhz", "fr_ghz"}.issubset(df.columns):
        b = df[df.fr_ghz.between(*(d.band or (0, 99))) & (df.bw_mhz > 0)]
        if len(b) > 10:
            fb = b.bw_mhz / (b.fr_ghz * 1000.0)
            corr = pd.Series({p: np.corrcoef(b[p], fb)[0, 1] for p in d.params}).sort_values(key=np.abs, ascending=False)
            print(f"\n== KORELASI MENTAH dengan BW pecahan (n = {len(b)}, fr di pita) ==")
            print(corr.head(5).round(2).to_string())

    if "fr4" in d.name.lower() and set(REF_FR4_ARD_BW) <= set(d.params):      # pembanding hanya untuk desain yang punya parameter U-slot itu
        print("\n== PEMBANDING dengan temuan lama FR-4 (135 sampel) ==")
        ref = pd.Series(REF_FR4_ARD_BW)
        now = ard[oc]
        print(f"{'param':6s} {'ARD lama':>9s} {'ARD sekarang':>13s}")
        for p in ref.index:
            print(f"{p:6s} {ref[p]:9.3f} {now[p]:13.3f}")
        if corr is not None:
            print("Korelasi BW pecahan lama: " + ", ".join(f"{k} {v:+.2f}" for k, v in REF_FR4_CORR.items())
                  + " | sekarang: " + ", ".join(f"{k} {corr[k]:+.2f}" for k in REF_FR4_CORR))
        print("Perbedaan urutan wajar: ARD dan korelasi mengukur hal berbeda, dan data kini lebih banyak. Laporkan perbedaannya, jangan disembunyikan.")

    os.makedirs(d.models_dir, exist_ok=True)
    os.makedirs(d.figures_dir, exist_ok=True)
    ard.round(5).to_csv(os.path.join(d.models_dir, "sensitivity_ard.csv"))
    sob.round(5).to_csv(os.path.join(d.models_dir, "sensitivity_sobol.csv"), index=False)

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6), gridspec_kw={"width_ratios": [1.25, 1.25, 1.0]})
    A = ard.T.reindex(cols)                       # target x parameter
    heat(axes[0], A.T, "Relevansi ARD (jumlah 1 per target)")
    ST = sob.pivot(index="target", columns="param", values="ST").reindex(index=cols, columns=d.params)
    heat(axes[1], ST.T, "Indeks Sobol total ST")
    S2 = S.sort_values("ST")
    y = np.arange(len(S2))
    axes[2].barh(y - 0.19, S2.S1, height=0.36, label="S1 (sendiri)", color="#1f77b4")
    axes[2].barh(y + 0.19, S2.ST, height=0.36, label="ST (total)", color="#ff7f0e")
    axes[2].set_yticks(y)
    axes[2].set_yticklabels(S2.index, fontsize=8)
    axes[2].set_title(f"Sobol untuk {oc}", fontsize=9)
    axes[2].legend(fontsize=8)
    axes[2].grid(alpha=0.3, axis="x")
    fig.suptitle(f"Sensitivitas {d.name} ({len(df)} sampel)", fontsize=11)
    fig.tight_layout()
    out_png = os.path.join(d.figures_dir, "sensitivity.png")
    fig.savefig(out_png, dpi=130)
    plt.close(fig)
    print(f"\nTabel : {os.path.join(d.models_dir, 'sensitivity_ard.csv')}\n        {os.path.join(d.models_dir, 'sensitivity_sobol.csv')}\nGambar: {out_png}")


if __name__ == "__main__":
    main()
