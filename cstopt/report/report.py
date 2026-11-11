"""
Generator laporan otomatis (P1-5). Tidak butuh CST. Hanya membaca batch_lhs.csv, kurva S11, dan gambar yang sudah ada.

  py main.py report
  py main.py report --focus bw --constraint "MicrostripAntena_RO4350B:gain_fr_ieee_dbi>=5.0" \\
                                --constraint "MicrostripAntena_RO4350B:gain_fr_ieee_dbi>=4.0"
  py main.py report --runs MicrostripAntena MicrostripAntena_RO4350B --out-dir data/_compare

--focus bw|cover|gain : besaran yang dimaksimalkan untuk memilih desain terbaik (default bw)
--constraint [RUN:]KOLOM>=NILAI : constraint tambahan di atas syarat dasar (fr di pita dan RL minimum). Boleh diulang; tiap
    constraint menjadi satu skenario. Diawali nama run bila hanya untuk run itu. Tanpa --constraint: satu skenario dasar per run.

Keluaran di data/_compare/: report.md, pareto.png, pareto_progress.png, pareto_front.csv, report_s11_<run>.png,
report_convergence.png, dan salinan gambar model (parity GPR, validasi maju, backtest) bila ada di folder figures run.
Semua angka di report.md dibaca dari data. Jangan menambah angka lain saat menyalin ke laporan.
"""
import argparse
import contextlib
import datetime
import io
import os
import platform
import shutil
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                 # noqa: E402
import pandas as pd                # noqa: E402

from cstopt import paths                                  # noqa: E402
from cstopt.loader import load_design_module              # noqa: E402
from cstopt.ml import core as mc                          # noqa: E402
from cstopt.report import pareto as pr                    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FOCUS_COL = {"bw": "bw_mhz", "cover": "band_cover_pct", "gain": "gain_fr_ieee_dbi"}
T_BW, T_GAIN = 200.0, 5.0          # target proposal
NEED = ["sample_id", "fr_ghz", "rl_min_db", "bw_mhz", "gain_fr_ieee_dbi"]


def git_hash():
    try:
        h = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        return h.stdout.strip() if h.returncode == 0 and h.stdout.strip() else "tidak tersedia"
    except Exception:
        return "tidak tersedia"


def versions():
    out = [f"Python {platform.python_version()}"]
    for m in ("numpy", "pandas", "sklearn", "scipy", "matplotlib"):
        try:
            out.append(f"{m} {__import__(m).__version__}")
        except Exception:
            pass
    return ", ".join(out)


def design_for_run(run):
    for name in paths.list_designs():
        try:
            if load_design_module(name).RUN_NAME == run:
                return name
        except Exception:
            continue
    return None


def parse_scenarios(items, runs):
    """-> {run: [(label, [constraint dicts])]}"""
    per = {r: [] for r in runs}
    for it in items or []:
        run, text = (it.split(":", 1) if ":" in it else (None, it))
        cons = mc.parse_constraints(text)
        label = ", ".join(f"{c['column']} {c['op']} {c['value']:g}" for c in cons)
        for r in ([run] if run else runs):
            if r in per:
                per[r].append((label, cons))
    for r in runs:
        if not per[r]:
            per[r] = [("syarat dasar", [])]
    return per


def feasible(df, band, rl_limit, cons):
    ok = df.fr_ghz.between(*band) & (df.rl_min_db <= rl_limit)
    for c in cons:
        if c["column"] not in df.columns:
            raise SystemExit(f"Constraint memakai kolom yang tidak ada di dataset: {c['column']}")
        v = df[c["column"]]
        ok &= (v >= c["value"]) if c["op"] == ">=" else (v <= c["value"])
    return ok.fillna(False)


def f_(v, dp=2):
    return "tidak ada" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{dp}f}"


def main():
    ap = argparse.ArgumentParser(description="Generator laporan otomatis")
    ap.add_argument("--runs", nargs="+", default=None)
    ap.add_argument("--focus", choices=list(FOCUS_COL), default="bw")
    ap.add_argument("--constraint", action="append", default=None, metavar="[RUN:]KOLOM>=NILAI")
    ap.add_argument("--band", nargs=2, type=float, default=None, metavar=("LO", "HI"))
    ap.add_argument("--rl-limit", type=float, default=-10.0)
    ap.add_argument("--out-dir", default=os.path.join(paths.DATA_DIR, "_compare"))
    args = ap.parse_args()

    runs = args.runs or pr.default_runs()
    if not runs:
        sys.exit("Tidak ada run dengan batch_lhs.csv.")
    os.makedirs(args.out_dir, exist_ok=True)
    designs = {r: design_for_run(r) for r in runs}
    d0 = mc.load_design(next((v for v in designs.values() if v), None))
    band = tuple(args.band) if args.band else tuple(d0.band or load_design_module().BAND_GHZ)
    rl = args.rl_limit
    scen = parse_scenarios(args.constraint, runs)
    obj = FOCUS_COL[args.focus]

    data, notes = {}, []
    for r in runs:
        p = os.path.join(paths.run_dir(r), "batch_lhs.csv")
        if not os.path.exists(p):
            notes.append(f"Run {r}: batch_lhs.csv tidak ada, dilewati.")
            continue
        df = pd.read_csv(p).sort_values("sample_id").reset_index(drop=True)
        miss = [c for c in NEED + [obj] if c not in df.columns]
        if miss:
            notes.append(f"Run {r}: kolom hilang {miss}, dilewati.")
            continue
        data[r] = df
    runs = list(data)
    if not runs:
        sys.exit("Tidak ada data yang bisa dilaporkan.\n" + "\n".join(notes))

    # Pareto (gambar dan tabel front dari modul pareto)
    out_png = os.path.join(args.out_dir, "pareto.png")
    argv0, buf = sys.argv, io.StringIO()
    sys.argv = ["pareto", "--runs", *runs, "--band", str(band[0]), str(band[1]), "--rl-limit", str(rl), "--out", out_png]
    try:
        with contextlib.redirect_stdout(buf):
            pr.main()
    finally:
        sys.argv = argv0
    front_all = pd.read_csv(os.path.join(args.out_dir, "pareto_front.csv"))

    # pilih desain terbaik per run dan skenario
    best = {}
    for r in runs:
        df = data[r]
        for label, cons in scen[r]:
            ok = feasible(df, band, rl, cons) & df[obj].notna()
            best[(r, label)] = (df.loc[df.loc[ok, obj].idxmax()] if ok.any() else None, int(ok.sum()), cons)

    md = ["# Laporan hasil optimasi antena", ""]
    md += ["## 1. Informasi reproduksi", "",
           f"- Tanggal: {datetime.date.today().isoformat()}",
           f"- Commit git: {git_hash()}",
           f"- Paket: {versions()}",
           "- Sampel per run: " + "; ".join(f"{r} {len(data[r])} sampel" for r in runs),
           f"- Syarat dasar: fr {band[0]:g} sampai {band[1]:g} GHz dan RL minimum <= {rl:g} dB; desain terbaik dipilih dengan memaksimalkan {obj}", ""]
    md += ["## 2. Definisi", "",
           "- BW: lebar pita S11 <= -10 dB di sekitar minimum global (BW = 0 bila RL minimum > -10 dB).",
           f"- Cakupan pita: persentase frekuensi di {band[0]:g} sampai {band[1]:g} GHz dengan S11 <= -10 dB.",
           "- Gain: gain IEEE di frekuensi resonansi (D + 10 log eta).",
           "- Substrat: nilai epsilon dan tan delta di bawah berasal dari file desain; konfirmasikan dengan material library CST.",
           f"- Target proposal: fr {band[0]:g} sampai {band[1]:g} GHz, RL minimum <= {rl:g} dB, BW >= {T_BW:g} MHz, gain >= {T_GAIN:g} dBi.", ""]

    md += ["## 3. Target dan hasil tercapai", ""]
    for (r, label), (b, n_ok, cons) in best.items():
        md += [f"### {r}: skenario {label}", ""]
        if b is None:
            md += [f"Tidak ada sampel yang memenuhi syarat ({label}).", ""]
            continue
        bw, g, fr_, rlm = float(b.bw_mhz), float(b.gain_fr_ieee_dbi), float(b.fr_ghz), float(b.rl_min_db)
        edge = min(fr_ - band[0], band[1] - fr_) * 1000
        rows = [("fr (GHz)", f"{band[0]:g} sampai {band[1]:g}", f_(fr_, 3), f"{edge:.0f} MHz dari tepi pita terdekat", "tercapai"),
                ("RL minimum (dB)", f"<= {rl:g}", f_(rlm, 1), f"{rlm - rl:+.1f} dB", "tercapai" if rlm <= rl else "tidak tercapai"),
                ("BW (MHz)", f">= {T_BW:g}", f_(bw, 1), f"{bw - T_BW:+.1f} MHz ({100 * bw / T_BW:.0f}% dari target)", "tercapai" if bw >= T_BW else "tidak tercapai"),
                ("BW pecahan (%)", "tidak ada", f_(100 * bw / (fr_ * 1000), 2), "", "acuan"),
                ("Cakupan pita (%)", "tidak ada", f_(b.get("band_cover_pct", np.nan), 1), "", "acuan"),
                ("Gain IEEE (dBi)", f">= {T_GAIN:g}", f_(g, 2), f"{g - T_GAIN:+.2f} dB", "tercapai" if g >= T_GAIN else "tidak tercapai"),
                ("Efisiensi radiasi di fr (%)", "tidak ada", f_(100 * b.get("eta_rad_fr", np.nan), 1), "", "acuan"),
                ("Directivity di fr (dBi)", "tidak ada", f_(b.get("d_peak_fr_dbi", np.nan), 2), "", "acuan")]
        md += [f"Desain terbaik: sampel {int(b.sample_id)} ({n_ok} sampel memenuhi syarat skenario ini).", "",
               "| besaran | target proposal | tercapai | selisih terhadap target | status |", "|---|---|---|---|---|"]
        md += [f"| {a} | {t} | {c} | {s} | {st} |" for a, t, c, s, st in rows]
        md.append("")
        df = data[r]
        okb = feasible(df, band, rl, cons)
        if okb.any():
            ib = df.loc[okb, "bw_mhz"].idxmax()
            ig = df.loc[okb, "gain_fr_ieee_dbi"].idxmax()
            md += [f"Maksimum terpisah pada skenario ini: BW {df.bw_mhz[ib]:.1f} MHz (sampel {int(df.sample_id[ib])}, gain {df.gain_fr_ieee_dbi[ib]:.2f} dBi); "
                   f"gain {df.gain_fr_ieee_dbi[ig]:.2f} dBi (sampel {int(df.sample_id[ig])}, BW {df.bw_mhz[ig]:.1f} MHz).", ""]

    md += ["## 4. Parameter desain terbaik", ""]
    shown = set()
    for (r, label), (b, _, _) in best.items():
        if b is None or r in shown:
            continue
        shown.add(r)
        dn = designs.get(r)
        dd = mc.load_design(dn) if dn else None
        params = list(dd.params) if dd else [c for c in data[r].columns if c in ("Lp", "Wp", "LU", "WU", "gU", "PU", "LI", "LD", "WD", "gD", "PD")]
        extra = [c for c in ("hs", "Wf") if c in data[r].columns]
        md += [f"### {r}: sampel {int(b.sample_id)} (skenario {label})", "", "| parameter | nilai (mm) |", "|---|---|"]
        md += [f"| {p} | {float(b[p]):.3f} |" for p in params + extra]
        sub = getattr(dd.mod, "SUBSTRATE", None) if dd else None
        if sub:
            md += [f"| substrat | {sub.get('material', '')}: epsilon {sub.get('er')}, tan delta {sub.get('tand')}, h {sub.get('h')} mm |"]
        md.append("")

    md += ["## 5. Kurva Pareto", "", "![Pareto](pareto.png)", "", "![Kemajuan hypervolume](pareto_progress.png)", "",
           "Hypervolume (acuan 0, 0; satuan MHz*dBi untuk BW dan %*dBi untuk cakupan; makin besar makin baik):", "",
           "| run | sumbu | hypervolume | titik front | knee (sampel) |", "|---|---|---|---|---|"]
    warns = []
    for r in runs:
        df = data[r]
        ok = feasible(df, band, rl, [])
        for xc, name in (("bw_mhz", "BW"), ("band_cover_pct", "cakupan pita")):
            if xc not in df.columns:
                continue
            f = df[ok].dropna(subset=[xc, "gain_fr_ieee_dbi"]).reset_index(drop=True)
            if f.empty:
                continue
            fr_ = f.iloc[pr.pareto_front(f[xc].values, f.gain_fr_ieee_dbi.values)].sort_values(xc).reset_index(drop=True)
            kn = pr.knee_index(fr_[xc].values, fr_.gain_fr_ieee_dbi.values)
            hv = pr.hypervolume_2d(np.column_stack([f[xc], f.gain_fr_ieee_dbi]), (0.0, 0.0))
            md.append(f"| {r} | {name} | {hv:.1f} | {len(fr_)} | {'tidak ada' if kn is None else int(fr_.sample_id[kn])} |")
            why = pr.front_warnings(fr_[xc].values, f[xc].values)
            if why:
                warns.append(f"Front {r} ({name}) belum representatif: " + "; ".join(why) + ".")
    md += ["", "Titik front BW terhadap gain (BW menurun):", ""]
    for r in runs:
        g = front_all[front_all.run == r].sort_values("bw_mhz", ascending=False)
        if g.empty:
            continue
        md += [f"**{r}**", "", "| sampel | BW (MHz) | gain (dBi) | fr (GHz) | RL min (dB) | cakupan (%) |", "|---|---|---|---|---|---|"]
        md += [f"| {int(x.sample_id)} | {x.bw_mhz:.1f} | {x.gain_fr_ieee_dbi:.2f} | {x.fr_ghz:.3f} | {x.rl_min_db:.1f} | "
               f"{f_(getattr(x, 'band_cover_pct', np.nan), 1)} |" for x in g.itertuples()]
        md.append("")

    # overlay S11 desain di front
    md += ["## 6. Overlay S11 desain di front Pareto", ""]
    for r in runs:
        g = front_all[front_all.run == r].sort_values("bw_mhz").reset_index(drop=True)
        dn = designs.get(r)
        dd = mc.load_design(dn) if dn else None
        cdir = (dd.curves_dir if dd and dd.curves_dir else os.path.join(paths.run_dir(r), "curves"))
        cfile = dd.curve_file if dd else "s11_sample{sid}.csv"
        if g.empty:
            continue
        pick = np.unique(np.linspace(0, len(g) - 1, min(6, len(g))).round().astype(int))
        fig, ax = plt.subplots(figsize=(7, 4.4))
        plotted, missing = 0, []
        for i in pick:
            sid = int(g.sample_id[i])
            cp = os.path.join(cdir, cfile.format(sid=sid))
            if not os.path.exists(cp):
                missing.append(sid)
                continue
            c = pd.read_csv(cp)
            ax.plot(c.iloc[:, 0], c.iloc[:, 1], lw=1.4, label=f"sampel {sid}: BW {g.bw_mhz[i]:.0f} MHz, gain {g.gain_fr_ieee_dbi[i]:.2f} dBi")
            plotted += 1
        if missing:
            notes.append(f"Kurva S11 sampel {missing} ({r}) tidak ada di {cdir}; dilewati dari overlay.")
        if plotted:
            ax.axvspan(band[0], band[1], color="gray", alpha=0.18, label=f"pita {band[0]:g} sampai {band[1]:g} GHz")
            ax.axhline(rl, color="red", ls="--", lw=1, label=f"{rl:g} dB")
            ax.set_xlabel("frekuensi (GHz)")
            ax.set_ylabel("S11 (dB)")
            ax.set_title(f"S11 desain di front Pareto: {r}", fontsize=10)
            ax.grid(alpha=0.3)
            ax.legend(fontsize=7, loc="lower right")
            fig.tight_layout()
            fn = f"report_s11_{r}.png"
            fig.savefig(os.path.join(args.out_dir, fn), dpi=130)
            md += [f"![S11 {r}]({fn})", ""]
        plt.close(fig)

    # konvergensi dan gambar model
    md += ["## 7. Metode: konvergensi BO dan model", ""]
    fig, axes = plt.subplots(1, len(runs), figsize=(5.8 * len(runs), 4.0), squeeze=False)
    for ax, r in zip(axes[0], runs):
        df = data[r]
        for label, cons in scen[r]:
            ok = (feasible(df, band, rl, cons) & df[obj].notna()).values
            cur, curve = np.nan, []
            for i in range(len(df)):
                if ok[i] and (np.isnan(cur) or df[obj].values[i] > cur):
                    cur = float(df[obj].values[i])
                curve.append(cur)
            ax.plot(df.sample_id, curve, lw=1.6, label=label)
        dn = designs.get(r)
        n0 = mc.load_design(dn).n_initial if dn else 0
        if n0:
            ax.axvline(n0 + 0.5, color="gray", ls="--", lw=0.8)
        ax.set_title(r, fontsize=10)
        ax.set_xlabel("sample_id")
        ax.set_ylabel(f"{obj} terbaik (feasible)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
    fig.suptitle("Konvergensi (garis putus abu abu = akhir sampel awal)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out_dir, "report_convergence.png"), dpi=130)
    plt.close(fig)
    md += ["![Konvergensi](report_convergence.png)", ""]
    for r in runs:
        dn = designs.get(r)
        fdir = mc.load_design(dn).figures_dir if dn else os.path.join(paths.run_dir(r), "figures")
        for src, cap in (("gpr_parity.png", "Parity GPR"), ("forward_validation.png", "Validasi maju"),
                         ("bo_backtest.png", "Backtest BO vs acak")):
            sp = os.path.join(fdir, src)
            if os.path.exists(sp):
                fn = f"report_{r}_{src}"
                shutil.copyfile(sp, os.path.join(args.out_dir, fn))
                md += [f"{cap} ({r}):", "", f"![{cap} {r}]({fn})", ""]
            else:
                notes.append(f"{cap} ({r}): {src} belum ada di {fdir} (jalankan train, validate, atau backtest).")

    for r in runs:
        df = data[r]
        if "fr_edge_flag" in df.columns and int(df.fr_edge_flag.sum()):
            notes.append(f"{r}: {int(df.fr_edge_flag.sum())} sampel punya fr menempel di tepi sweep; resonansi sebenarnya mungkin di luar rentang sweep.")
    md += ["## 8. Catatan otomatis", ""]
    allnotes = warns + notes
    md += [f"- {n}" for n in allnotes] if allnotes else ["- Tidak ada peringatan."]
    md.append("")
    path = os.path.join(args.out_dir, "report.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))
    print(f"Laporan: {path}")
    for n in allnotes:
        print("[catatan]", n)


if __name__ == "__main__":
    main()
