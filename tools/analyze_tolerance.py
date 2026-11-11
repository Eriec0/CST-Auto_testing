"""
Analisis hasil simulasi toleransi (P0-2 bagian B). Tidak butuh CST.

  py tools/analyze_tolerance.py --run MicrostripAntena_RO4350B
  py tools/analyze_tolerance.py --run MicrostripAntena_RO4350B --sample 112 --bw-min 120 --gain-min 5.0

Membaca data/<run>_tol/batch_lhs.csv (hasil `py main.py run --run-name <run>_tol ...`), berkas _meta.csv dari make_tolerance.py,
dan nominal dari data/<run>/batch_lhs.csv. Per desain dihitung nominal, minimum, maksimum, simpangan baku, selisih terbesar
terhadap nominal, dan yield = proporsi skenario yang masih memenuhi semua syarat:
  fr di dalam BAND_GHZ desain, RL minimum <= batas desain, BW >= --bw-min, gain >= --gain-min.
Bawaan: --bw-min = 90 persen BW nominal, --gain-min = GAIN_MIN_DBI desain (atau 5,0 bila tidak ada).
Keluaran di data/_compare/: tolerance_<run>.md, _summary.csv, _yield.csv, dan tolerance_<run>_s<ID>_tornado.png.
Catatan: yield dihitung terpisah per plan. Hanya plan random yang mendekati yield statistik, dan dengan 12 sampel galat bakunya
bisa sekitar 14 poin persen. OAT dan corners adalah analisis kasus terburuk, bukan peluang.
"""
import argparse
import glob
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                 # noqa: E402
import pandas as pd                # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cstopt import paths                       # noqa: E402
from cstopt.loader import load_design_module   # noqa: E402

METRICS = [("fr_ghz", "fr (GHz)", 4), ("rl_min_db", "RL minimum (dB)", 2),
           ("bw_mhz", "BW (MHz)", 1), ("gain_fr_ieee_dbi", "gain di fr (dBi)", 2)]
PLAN_ORDER = ["oat", "corners", "random"]


def find_design(run, name=None):
    if name:
        return load_design_module(name)
    for d in paths.list_designs():
        try:
            m = load_design_module(d)
        except Exception:
            continue
        if getattr(m, "RUN_NAME", None) == run:
            return m
    raise SystemExit(f"Tidak ada desain dengan RUN_NAME '{run}'. Sebutkan --design.")


def pass_mask(df, band, rl_limit, bw_min, g_min):
    c = {"fr di pita": df.fr_ghz.between(*band), "RL": df.rl_min_db <= rl_limit,
         "BW": df.bw_mhz >= bw_min, "gain": df.gain_fr_ieee_dbi >= g_min}
    ok = np.logical_and.reduce([v.values for v in c.values()])
    return pd.Series(ok, index=df.index), c


def tornado(oat, nom, base, path):
    """oat: baris OAT dengan kolom param, sign dan hasil. Tiga panel: geser fr (MHz), perubahan BW (MHz), perubahan gain (dB)."""
    items = [("geser fr (MHz)", lambda d: (d.fr_ghz - nom.fr_ghz) * 1000.0),
             ("perubahan BW (MHz)", lambda d: d.bw_mhz - nom.bw_mhz),
             ("perubahan gain (dB)", lambda d: d.gain_fr_ieee_dbi - nom.gain_fr_ieee_dbi)]
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.8))
    for ax, (title, fn) in zip(axes, items):
        tab = {}
        for p, g in oat.groupby("param"):
            lo, hi = g[g.sign < 0], g[g.sign > 0]
            tab[p] = (float(fn(lo).iloc[0]) if len(lo) else np.nan, float(fn(hi).iloc[0]) if len(hi) else np.nan)
        order = sorted(tab, key=lambda k: -np.nanmax(np.abs(tab[k])) if not np.all(np.isnan(tab[k])) else 0)[::-1]
        y = np.arange(len(order))
        ax.barh(y - 0.19, [tab[k][0] for k in order], height=0.36, color="#1f77b4", label="parameter turun (-)")
        ax.barh(y + 0.19, [tab[k][1] for k in order], height=0.36, color="#ff7f0e", label="parameter naik (+)")
        ax.set_yticks(y)
        ax.set_yticklabels(order)
        ax.axvline(0, color="black", lw=0.8)
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.3, axis="x")
    axes[0].legend(fontsize=8, loc="best")
    fig.suptitle(f"Dampak toleransi satu parameter (OAT), sampel {base}")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="Analisis hasil toleransi")
    ap.add_argument("--run", required=True, help="nama run dataset utama")
    ap.add_argument("--design", default=None)
    ap.add_argument("--tol-run", default=None, help="default: <run>_tol")
    ap.add_argument("--sample", type=int, nargs="+", default=None, help="desain yang dianalisis (default: semua di meta)")
    ap.add_argument("--bw-min", type=float, default=None, help="syarat BW (MHz); default 90 persen BW nominal")
    ap.add_argument("--gain-min", type=float, default=None, help="syarat gain (dBi); default GAIN_MIN_DBI desain")
    ap.add_argument("--out-dir", default=os.path.join(paths.DATA_DIR, "_compare"))
    a = ap.parse_args()

    D = find_design(a.run, a.design)
    band, rl_limit = tuple(D.BAND_GHZ), float(getattr(D, "RL_LIMIT_DB", -10.0))
    g_min = a.gain_min if a.gain_min is not None else float(getattr(D, "GAIN_MIN_DBI", 5.0))
    tol_run = a.tol_run or a.run + "_tol"
    res_path = os.path.join(paths.run_dir(tol_run), "batch_lhs.csv")
    if not os.path.exists(res_path):
        raise SystemExit(f"Belum ada hasil: {res_path}\nJalankan: py main.py run --run-name {tol_run} --samples <CSV dari make_tolerance.py> --auto-yes")
    main_df = pd.read_csv(os.path.join(paths.run_dir(a.run), "batch_lhs.csv"))
    res = pd.read_csv(res_path)
    metas = glob.glob(os.path.join(paths.samples_dir(tol_run), "*_meta.csv"))
    if metas:
        meta = pd.concat([pd.read_csv(m) for m in metas], ignore_index=True).drop_duplicates("sample_id", keep="last")
    else:
        print("[peringatan] berkas _meta.csv tidak ada: plan tidak diketahui, semua baris dianggap satu kelompok.")
        meta = pd.DataFrame({"sample_id": res.sample_id, "base_id": res.sample_id // 100, "plan": "semua",
                             "label": "", "param": "", "sign": 0, "dilewati": 0})
    for c, v in (("dilewati", 0), ("param", ""), ("sign", 0), ("signs", ""), ("catatan", "")):
        if c not in meta.columns:
            meta[c] = v
    meta["param"] = meta["param"].fillna("")
    bases = a.sample or sorted(meta.base_id.unique())
    os.makedirs(a.out_dir, exist_ok=True)

    md = [f"# Toleransi fabrikasi: {a.run}", "",
          f"Syarat lulus: fr {band[0]:g} sampai {band[1]:g} GHz, RL minimum <= {rl_limit:g} dB, "
          f"BW >= {'90% BW nominal' if a.bw_min is None else format(a.bw_min, 'g') + ' MHz'}, gain >= {g_min:g} dBi.", ""]
    sum_rows, yld_rows = [], []
    for base in bases:
        nr = main_df[main_df.sample_id == base]
        if nr.empty:
            print(f"[lewati] sampel {base} tidak ada di dataset utama")
            continue
        nom = nr.iloc[0]
        bw_min = a.bw_min if a.bw_min is not None else round(0.9 * float(nom.bw_mhz), 1)
        mb = meta[meta.base_id == base]
        rb = res.merge(mb, on="sample_id", how="inner")
        if rb.empty:
            print(f"[lewati] sampel {base}: belum ada hasil simulasi toleransi")
            continue
        nom_ok = bool(pass_mask(pd.DataFrame([nom]), band, rl_limit, bw_min, g_min)[0].iloc[0])
        md += [f"## Desain sampel {base}", "",
               f"Nominal: fr {nom.fr_ghz:.3f} GHz, RL {nom.rl_min_db:.1f} dB, BW {nom.bw_mhz:.1f} MHz, gain {nom.gain_fr_ieee_dbi:.2f} dBi; "
               f"syarat BW >= {bw_min:g} MHz; nominal {'lulus' if nom_ok else 'TIDAK lulus'}.", "",
               "| besaran | nominal | minimum | maksimum | simpangan baku | selisih maks dari nominal |", "|---|---|---|---|---|---|"]
        print(f"\nSampel {base}: {len(rb)} skenario terhitung; syarat BW >= {bw_min:g} MHz, gain >= {g_min:g} dBi; nominal {'lulus' if nom_ok else 'TIDAK lulus'}")
        for col, lab, dp in METRICS:
            v = rb[col].astype(float)
            sd = float(v.std(ddof=1)) if len(v) > 1 else float("nan")
            dev = float((v - float(nom[col])).abs().max())
            sum_rows.append({"sample_id": base, "besaran": col, "nominal": nom[col], "minimum": v.min(), "maksimum": v.max(),
                             "simpangan_baku": sd, "selisih_maks": dev, "n": len(v)})
            md.append(f"| {lab} | {nom[col]:.{dp}f} | {v.min():.{dp}f} | {v.max():.{dp}f} | {sd:.{dp}f} | {dev:.{dp}f} |")
            print(f"  {lab:18s} nominal {nom[col]:.{dp}f}  min {v.min():.{dp}f}  maks {v.max():.{dp}f}  sd {sd:.{dp}f}  selisih maks {dev:.{dp}f}")
        ok, conds = pass_mask(rb, band, rl_limit, bw_min, g_min)
        rb = rb.assign(lulus=ok.values)
        md += ["", "| plan | direncanakan | dilewati (geometri) | belum tersimulasi | tersimulasi | lulus | yield |", "|---|---|---|---|---|---|---|"]
        plans = [p for p in PLAN_ORDER if p in set(mb.plan)] + [p for p in sorted(set(mb.plan)) if p not in PLAN_ORDER]
        for pl in plans + ["semua"]:
            mp = mb if pl == "semua" else mb[mb.plan == pl]
            rp = rb if pl == "semua" else rb[rb.plan == pl]
            n_skip, n_sim = int(mp.dilewati.sum()), len(rp)
            n_ok = int(rp.lulus.sum())
            y = 100.0 * n_ok / n_sim if n_sim else float("nan")
            n_wait = len(mp) - n_skip - n_sim
            yld_rows.append({"sample_id": base, "plan": pl, "direncanakan": len(mp), "dilewati": n_skip,
                             "belum_tersimulasi": n_wait, "tersimulasi": n_sim, "lulus": n_ok, "yield_pct": y})
            md.append(f"| {pl} | {len(mp)} | {n_skip} | {n_wait} | {n_sim} | {n_ok} | {y:.0f}% |")
            print(f"  yield {pl:8s}: {n_ok}/{n_sim} lulus ({y:.0f}%), dilewati {n_skip}, belum tersimulasi {n_wait}, direncanakan {len(mp)}")
        fails = {k: int((~v.loc[rb.index]).sum()) for k, v in conds.items()}
        fails = {k: n for k, n in fails.items() if n}
        if fails:
            txt = ", ".join(f"{k} {n}" for k, n in fails.items())
            md += ["", f"Syarat yang gagal (jumlah skenario): {txt}."]
            print(f"  gagal per syarat: {txt}")
        skipped = mb[mb.dilewati == 1]
        if len(skipped):
            md += ["", "Skenario yang tidak disimulasikan karena geometri tidak valid: " +
                   "; ".join(f"{r.label} ({r.catatan})" for r in skipped.itertuples()) + "."]
        oat = rb[rb.plan == "oat"]
        if len(oat):
            png = os.path.join(a.out_dir, f"tolerance_{a.run}_s{base}_tornado.png")
            tornado(oat, nom, base, png)
            md += ["", f"Tornado: {os.path.basename(png)}"]
            print(f"  tornado: {png}")
        md.append("")
    md += ["Catatan: yield plan random dengan 12 sampel memiliki galat baku sampai sekitar 14 poin persen. OAT dan corners "
           "adalah kasus terburuk, bukan peluang. Kalimat laporan hanya boleh memakai angka di tabel ini.", ""]
    pd.DataFrame(sum_rows).round(5).to_csv(os.path.join(a.out_dir, f"tolerance_{a.run}_summary.csv"), index=False)
    pd.DataFrame(yld_rows).round(2).to_csv(os.path.join(a.out_dir, f"tolerance_{a.run}_yield.csv"), index=False)
    md_path = os.path.join(a.out_dir, f"tolerance_{a.run}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"\nTabel: {md_path}")


if __name__ == "__main__":
    main()
