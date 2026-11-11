"""
Validasi maju model GPR: model dilatih pada sampel yang SUDAH ada lalu diuji pada sampel berikutnya, sama seperti cara
BO memakainya (berurutan dan mengekstrapolasi). Tidak butuh CST dan tidak mengubah perilaku `suggest`.

  py main.py validate --design uslot_dgs_fr4 --restarts 2
  py main.py validate --design uslot_dgs_ro4350b --batch 5
  py main.py validate --design uslot_dgs_fr4 --split 135       latih id <= 135, uji id > 135 (satu pembagian)
  py main.py validate --design uslot_dgs_ro4350b --focus bw --constraint "gain_fr_ieee_dbi>=5.0"

Yang dihitung (hanya kolom objective dan constraint tahap atau fokus aktif):
  1. per kolom: bias (aktual dikurangi prediksi), RMSE, MAE, rata rata dan simpangan baku z-score, cakupan interval 68 dan 95 persen
  2. kalibrasi peluang feasible (PoF) seperti di acquisition: skor Brier, tabel reliabilitas, dan PoF rata rata per kolom
     constraint dibanding laju feasible sebenarnya
  3. wilayah kerja: R2 dan RMSE (satuan asli) hanya untuk sampel dengan fr di dalam pita. R2 saja menyesatkan, jadi keduanya dilaporkan
  4. saran margin: persentil 90 galat searah sisi tiap constraint, dibulatkan ke atas dua angka penting, untuk --margin pada suggest
Keluaran: <models>/forward_validation.csv (per sampel uji), <figures>/forward_validation.png, ringkasan di terminal.
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                 # noqa: E402
import pandas as pd                # noqa: E402

from cstopt.ml import core as mc   # noqa: E402

BIN_EDGES = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0000001]


def scale_of(col):
    """(pengali tampilan, satuan): kolom GHz ditampilkan dalam MHz."""
    return (1000.0, "MHz") if col.endswith("_ghz") else (1.0, "")


def ceil2(v):
    """Bulatkan ke atas dengan dua angka penting."""
    if not np.isfinite(v) or v <= 0:
        return 0.0
    e = int(np.floor(np.log10(v))) - 1
    return float(np.ceil(v / 10 ** e - 1e-9) * 10 ** e)


def pof_subset(d, models, Xu, cons):
    """PoF model untuk subset constraint (rumus yang sama dengan acquisition, tanpa margin dan kalibrasi)."""
    saved = d.constraints
    d.constraints = cons
    try:
        return mc.acquisition(d, models, Xu, None, 0.0)[2]
    finally:
        d.constraints = saved


def main():
    ap = argparse.ArgumentParser(description="Validasi maju model GPR")
    ap.add_argument("--design", default=None, help="nama file di designs/ (default: desain bawaan)")
    ap.add_argument("--batch", type=int, default=5, help="ukuran batch uji berurutan (default 5)")
    ap.add_argument("--min-train", type=int, default=None, help="minimal sampel latih per batch (default N_INITIAL desain)")
    ap.add_argument("--split", type=int, default=None, metavar="N", help="satu pembagian: latih id <= N, uji id > N")
    ap.add_argument("--max-id", type=int, default=None, help="abaikan sampel dengan id lebih besar dari ini (untuk mereproduksi uji lama)")
    ap.add_argument("--kernel", default="rbf", choices=["rbf", "matern52"])
    ap.add_argument("--restarts", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--stage", type=int, default=None, help="paksa tahap BO (1, 2, ...)")
    ap.add_argument("--focus", default=None, help="fokus manual dari FOCI di file desain")
    ap.add_argument("--constraint", default=None, help='ganti atau tambah constraint pada --focus, mis. "gain_fr_ieee_dbi>=5.0"')
    args = ap.parse_args()

    d = mc.load_design(args.design)
    if args.constraint and not args.focus:
        ap.error("--constraint hanya dipakai bersama --focus")
    if args.focus:
        d.set_focus(args.focus, mc.parse_constraints(args.constraint))
    if args.stage is not None:
        d.force_stage = args.stage - 1
    d.margins, d.sigma_mult = {}, {}
    df = mc.load_dataset(d)
    if args.max_id is not None:
        df = df[df[d.id_col] <= args.max_id].reset_index(drop=True)
    oc = d.objective["column"]
    cols = list(dict.fromkeys([oc] + [c["column"] for c in d.constraints]))
    if d.use_composites and d.composites:          # sama seperti suggest: kolom turunan dari komponennya
        for col, parts in d.composites.items():
            if col in cols:
                cols += [s for s, _, tn in parts if tn == "none" and s not in cols]
    ids = df[d.id_col].values
    n0 = int(d.n_initial)
    min_train = args.min_train if args.min_train is not None else max(n0, 10)
    if args.split is not None:
        groups = [np.where(ids > args.split)[0]]
    else:
        pos = np.where(ids > n0)[0]
        groups = [pos[i:i + args.batch] for i in range(0, len(pos), args.batch)]
    groups = [g for g in groups if len(g) and g[0] >= min_train]
    if not groups:
        raise SystemExit(f"Tidak ada batch uji: butuh sampel dengan id > {args.split if args.split is not None else n0} "
                         f"dan minimal {min_train} sampel latih sebelumnya.")
    mode = f"satu pembagian (latih id <= {args.split})" if args.split is not None else f"batch berurutan ukuran {args.batch}"
    print(f"Desain {d.name} | {len(df)} sampel | {mode} | {len(groups)} batch uji")
    print(f"Tahap/fokus: {d.stage_name} | objective {d.objective['goal']} {oc} | constraint: "
          f"{[(c['column'], c['op'], c['value']) for c in d.constraints]}")

    rows, pof_all, pof_col = [], [], {}
    cons_cols = list(dict.fromkeys(c["column"] for c in d.constraints))
    for b, g in enumerate(groups):
        tr, te = df.iloc[:g[0]], df.iloc[g]
        models = mc.fit_models(d, tr, cols, args.kernel, args.restarts, args.seed)
        if d.use_composites and d.composites:
            models = mc.apply_composites(d, models, tr, args.kernel, args.restarts, args.seed)
        Xu = d.to_unit(te[d.params].values)
        pred = {}
        for col in cols:
            mu_t, sd_t = models[col].predict_t(Xu)
            pred[col] = models[col].to_raw(mu_t, sd_t)
        pof = mc.acquisition(d, models, Xu, None, 0.0)[2]
        pc = {c: pof_subset(d, models, Xu, [x for x in d.constraints if x["column"] == c]) for c in cons_cols}
        feas = mc.feasible_mask(d, te)
        for k in range(len(te)):
            r = {"sample_id": int(te[d.id_col].iloc[k]), "batch": b + 1, "n_latih": len(tr),
                 "pof_model": float(pof[k]), "feasible_aktual": int(feas[k])}
            for col in cols:
                r[f"{col}_aktual"] = float(te[col].iloc[k])
                r[f"{col}_pred"] = float(pred[col][0][k])
                r[f"{col}_sd"] = float(pred[col][1][k])
            for c in cons_cols:
                r[f"pof_{c}"] = float(pc[c][k])
                r[f"ok_{c}"] = int(mc.feasible_mask(d, te.iloc[[k]], [x for x in d.constraints if x["column"] == c])[0])
            rows.append(r)
        print(f"  batch {b + 1}/{len(groups)}: latih {len(tr)} sampel, uji id {int(te[d.id_col].iloc[0])}..{int(te[d.id_col].iloc[-1])}",
              end="\r")
    print()
    V = pd.DataFrame(rows)

    for col in cols:
        nn = int(V[f"{col}_aktual"].isna().sum())
        if nn > 0.1 * len(V):
            print(f"[peringatan] {col}: {nn} dari {len(V)} nilai aktual kosong (kurva S11 tidak ada atau fitur gagal dihitung). "
                  "Akurasi dan PoF yang memakai kolom ini tidak bisa dipercaya.")

    # 1. akurasi per kolom
    print(f"\n== AKURASI PREDIKSI ({len(V)} sampel uji) ==")
    print(f"{'kolom':20s} {'n':>4s} {'bias':>9s} {'RMSE':>9s} {'MAE':>9s} {'naik':>6s} {'z rata':>7s} {'z sd':>6s} {'cov68':>6s} {'cov95':>6s}")
    stats = {}
    for col in cols:
        a, p, s = V[f"{col}_aktual"].values, V[f"{col}_pred"].values, V[f"{col}_sd"].values
        m = np.isfinite(a) & np.isfinite(p)
        e, z = (a - p)[m], ((a - p) / np.maximum(s, 1e-9))[m]
        k, u = scale_of(col)
        stats[col] = dict(n=int(m.sum()), bias=e.mean(), rmse=float(np.sqrt(np.mean(e ** 2))), mae=float(np.mean(np.abs(e))),
                          up=int((e > 0).sum()), zm=z.mean(), zs=z.std(), c68=np.mean(np.abs(z) < 1), c95=np.mean(np.abs(z) < 1.96))
        t = stats[col]
        print(f"{col:20s} {t['n']:4d} {t['bias'] * k:+9.3f} {t['rmse'] * k:9.3f} {t['mae'] * k:9.3f} {t['up']:3d}/{t['n']:<2d} "
              f"{t['zm']:+7.2f} {t['zs']:6.2f} {100 * t['c68']:5.0f}% {100 * t['c95']:5.0f}%   {u}")
    print("bias = rata rata (aktual dikurangi prediksi); naik = jumlah sampel dengan aktual lebih tinggi dari prediksi; "
          "cov = porsi |z| di bawah 1 dan 1,96 (ideal 68 dan 95 persen).")

    # 3. wilayah kerja
    if d.band is not None and "fr_ghz_aktual" in V.columns:
        inb = V.fr_ghz_aktual.between(*d.band).values
        print(f"\n== WILAYAH KERJA (fr aktual di {d.band[0]:g} sampai {d.band[1]:g} GHz, n = {int(inb.sum())} dari {len(V)}) ==")
        if inb.sum() >= 3:
            for col in cols:
                a, p = V[f"{col}_aktual"].values[inb], V[f"{col}_pred"].values[inb]
                m = np.isfinite(a) & np.isfinite(p)
                if m.sum() < 3:
                    continue
                sst = np.sum((a[m] - a[m].mean()) ** 2)
                r2 = 1 - np.sum((a[m] - p[m]) ** 2) / sst if sst > 0 else float("nan")
                k, u = scale_of(col)
                print(f"  {col:20s} R2 {r2:+.2f} | RMSE {np.sqrt(np.mean((a[m] - p[m]) ** 2)) * k:.3f} {u}")
        else:
            print("  terlalu sedikit sampel di pita untuk R2.")

    # 2. kalibrasi PoF
    y, p = V.feasible_aktual.values.astype(float), V.pof_model.values
    brier = float(np.mean((p - y) ** 2))
    ref = float(y.mean() * (1 - y.mean()))
    print(f"\n== KALIBRASI PELUANG FEASIBLE ==\nPoF model rata rata {p.mean():.2f} vs feasible aktual {y.mean():.2f} | "
          f"Brier {brier:.3f} (acuan laju tetap {ref:.3f}, makin kecil makin baik)")
    for c in cons_cols:
        print(f"  {c:20s} PoF model {V[f'pof_{c}'].mean():.2f} vs aktual {V[f'ok_{c}'].mean():.2f}")
    print(f"{'bin PoF':>10s} {'n':>4s} {'rata model':>11s} {'aktual':>7s}")
    rel = []
    for lo, hi in zip(BIN_EDGES[:-1], BIN_EDGES[1:]):
        m = (p >= lo) & (p < hi)
        if m.any():
            rel.append((p[m].mean(), y[m].mean(), int(m.sum())))
            print(f"{lo:4.1f}-{min(hi, 1):3.1f} {int(m.sum()):4d} {p[m].mean():11.2f} {y[m].mean():7.2f}")

    # 4. saran margin
    print("\n== SARAN MARGIN (persentil 90 galat searah sisi constraint, satuan asli) ==")
    sugg = {}
    for c in d.constraints:
        a, pr = V[f"{c['column']}_aktual"].values, V[f"{c['column']}_pred"].values
        m = np.isfinite(a) & np.isfinite(pr)
        e = (a - pr)[m] if c["op"] == "<=" else (pr - a)[m]
        q90 = float(np.percentile(e, 90))
        k, u = scale_of(c["column"])
        print(f"  {c['column']} {c['op']} {c['value']:g}: P90 galat searah {q90 * k:+.3f} {u}")
        if q90 > 0:
            sugg[c["column"]] = max(sugg.get(c["column"], 0.0), ceil2(q90))
    for col, mg in sugg.items():
        sides = [c["value"] for c in d.constraints if c["column"] == col]
        if len(sides) == 2 and mg >= (max(sides) - min(sides)) / 2:
            print(f"[peringatan] margin saran {col} ({mg:g}) melebihi setengah lebar pita ({(max(sides) - min(sides)) / 2:g}): "
                  "model tidak layak dipakai untuk constraint ini di wilayah ekstrapolasi kecuali region dipersempit (--region-auto).")
    if sugg:
        print("Saran: --margin " + ",".join(f"{k}={v:g}" for k, v in sugg.items())
              + "  (margin berlaku simetris untuk tiap kolom; sisi yang kurang mengikat ikut diperketat)")
    else:
        print("Tidak ada galat searah yang positif pada persentil 90: margin tidak diperlukan.")

    out_csv = os.path.join(d.models_dir, "forward_validation.csv")
    os.makedirs(d.models_dir, exist_ok=True)
    V.round(5).to_csv(out_csv, index=False)

    # gambar: reliabilitas dan bias per batch
    show = cols[:5]
    fig, axes = plt.subplots(2, 3, figsize=(14, 7))
    ax = axes[0, 0]
    ax.plot([0, 1], [0, 1], "k:", lw=1)
    if rel:
        ax.plot([r[0] for r in rel], [r[1] for r in rel], "o-", color="C0")
        for r in rel:
            ax.annotate(str(r[2]), (r[0], r[1]), textcoords="offset points", xytext=(4, 4), fontsize=8)
    ax.set_xlabel("PoF model (rata rata per bin)")
    ax.set_ylabel("laju feasible aktual")
    ax.set_title(f"Reliabilitas PoF (Brier {brier:.3f}; angka = jumlah sampel)", fontsize=9)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.3)
    for ax, col in zip(axes.flat[1:], show):
        k, u = scale_of(col)
        g = V.assign(e=(V[f"{col}_aktual"] - V[f"{col}_pred"]) * k).groupby("batch").e.mean()
        ax.bar(g.index, g.values, color=np.where(g.values >= 0, "#ff7f0e", "#1f77b4"))
        ax.axhline(0, color="black", lw=0.8)
        ax.set_title(f"bias per batch: {col} ({u or 'satuan asli'})", fontsize=9)
        ax.set_xlabel("batch uji (urut waktu)")
        ax.grid(alpha=0.3, axis="y")
    for ax in axes.flat[1 + len(show):]:
        ax.axis("off")
    fig.suptitle(f"Validasi maju {d.name}: bias positif = aktual lebih tinggi dari prediksi", fontsize=11)
    fig.tight_layout()
    os.makedirs(d.figures_dir, exist_ok=True)
    out_png = os.path.join(d.figures_dir, "forward_validation.png")
    fig.savefig(out_png, dpi=130)
    plt.close(fig)
    print(f"\nTabel : {out_csv}\nGambar: {out_png}")


if __name__ == "__main__":
    main()
