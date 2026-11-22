"""
Bagian 9 laporan: pola radiasi 2D, metrik pola, VSWR dan efisiensi terhadap frekuensi, tabel ringkas desain final,
tabel toleransi (bila sudah dianalisis), dan gambar fase optimasi.

Semua dibaca dari berkas yang sudah ada (batch_lhs.csv, curves/, eff/, ff/); tidak butuh CST. Berkas yang tidak ada
dilewati dengan catatan, bukan galat. Dipanggil dari cstopt/report/report.py lewat build().

Catatan data: ff/ berisi DIRECTIVITY (dBi), bukan gain. Gain = directivity + 10 log10(efisiensi). Irisan yang tersimpan hanya
phi = 0 dan phi = 90 pada frekuensi monitor (mis. 3,5 GHz), jadi pola yang digambar adalah pola 2D bidang utama.
"""
import glob
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                 # noqa: E402
import pandas as pd                # noqa: E402

from cstopt import paths                      # noqa: E402
from cstopt.report import pareto as pr        # noqa: E402

FF_RE = re.compile(r"ff_dir_s(\d+)_f([0-9.]+)_phi(\d+)\.txt$")
COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]


# ---------------------------------------------------------------- pembacaan berkas
def ff_files(run, sid):
    """{frekuensi GHz: {phi: path}} untuk satu sampel."""
    d = os.path.join(paths.run_dir(run), "ff")
    out = {}
    for p in glob.glob(os.path.join(d, f"ff_dir_s{int(sid)}_f*_phi*.txt")):
        m = FF_RE.search(os.path.basename(p))
        if m:
            out.setdefault(float(m.group(2)), {})[int(m.group(3))] = p
    return out


def read_cut(path):
    """Irisan pola: sudut bertanda (-180..180) terurut, directivity, komponen Theta dan Phi, axial ratio. None bila gagal."""
    try:
        a = np.atleast_2d(np.loadtxt(path, skiprows=2))
        th, phi = a[:, 0], a[:, 1]
        # satu berkas = irisan penuh: Phi sama dengan baris pertama (sisi positif) lalu Phi + 180 (sisi negatif), theta selalu 0 sampai 180
        side = np.where(np.abs(((phi - phi[0] + 180.0) % 360.0) - 180.0) < 90.0, 1.0, -1.0)
        ang = th * side
        o = np.argsort(ang, kind="stable")
        c = dict(ang=ang[o], dir=a[o, 2], th=a[o, 3], ph=a[o, 5], ax=(a[o, 7] if a.shape[1] > 7 else None))
        return c if len(c["ang"]) >= 8 else None
    except (OSError, ValueError, IndexError):
        return None


def _walk(d, p, step, thr, dstep):
    """Lebar (derajat) dari puncak p ke satu arah sampai d turun di bawah thr (sirkular, interpolasi linear). None bila tidak turun."""
    n = len(d)
    for k in range(1, n):
        j = (p + step * k) % n
        if d[j] < thr:
            j0 = (p + step * (k - 1)) % n
            x = (d[j0] - thr) / (d[j0] - d[j]) if d[j0] != d[j] else 0.0
            return (k - 1 + x) * dstep
    return None


def metrics(c):
    """Dmax, arah puncak, HPBW, front to back, XPD di puncak, axial ratio di boresight, dan bidang (E atau H)."""
    ang, d = c["ang"], c["dir"]
    p = int(np.nanargmax(d))
    dmax = float(d[p])
    dstep = float(np.median(np.diff(ang)))
    r, l = _walk(d, p, +1, dmax - 3.0, dstep), _walk(d, p, -1, dmax - 3.0, dstep)
    hpbw = (r + l) if (r is not None and l is not None) else None
    dd = ((ang - ang[p] + 180.0) % 360.0) - 180.0
    rear = np.abs(dd) >= 90.0
    fb = dmax - float(np.nanmax(d[rear])) if rear.any() else None
    i0 = int(np.argmin(np.abs(ang)))
    co_is_phi = c["ph"][i0] >= c["th"][i0]
    co, cross = (c["ph"], c["th"]) if co_is_phi else (c["th"], c["ph"])
    sector = np.abs(dd) <= (hpbw / 2.0 if hpbw else 45.0)
    xpd = float(co[p] - np.nanmax(cross[sector]))
    ar = float(c["ax"][i0]) if c["ax"] is not None else None
    # bidang yang memuat vektor E: komponen dominan di boresight adalah Theta (dalam bidang irisan)
    plane = "H" if co_is_phi else "E"
    return dict(dmax=dmax, theta_peak=float(ang[p]), hpbw=hpbw, fb=fb, xpd=xpd, ar=ar, plane=plane)


def read_curve(run, design, sid):
    """Kurva S11 (frekuensi GHz, dB) dengan konvensi desain; None bila tidak ada."""
    cdir = design.curves_dir if design is not None and getattr(design, "curves_dir", None) else os.path.join(paths.run_dir(run), "curves")
    cfile = design.curve_file if design is not None and getattr(design, "curve_file", None) else "s11_sample{sid}.csv"
    p = os.path.join(cdir, cfile.format(sid=int(sid)))
    if not os.path.exists(p):
        return None
    try:
        c = pd.read_csv(p)
        return c.iloc[:, 0].values.astype(float), c.iloc[:, 1].values.astype(float)
    except (OSError, ValueError, pd.errors.ParserError):
        return None


def read_eff(run, sid):
    p = os.path.join(paths.run_dir(run), "eff", f"eff_sample{int(sid)}.csv")
    if not os.path.exists(p):
        return None
    try:
        e = pd.read_csv(p)
        return e if {"freq_ghz", "eta_rad", "eta_tot"} <= set(e.columns) else None
    except (OSError, ValueError, pd.errors.ParserError):
        return None


def vswr_from_db(s_db):
    g = np.minimum(10.0 ** (np.asarray(s_db, float) / 20.0), 0.999)
    return (1.0 + g) / (1.0 - g)


def df_md(df, dp=3):
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join((f"{v:.{dp}f}" if isinstance(v, (float, np.floating)) else str(v)) for v in r.values) + " |")
    return out


def f_(v, dp=2):
    return "tidak ada" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{dp}f}"


# ---------------------------------------------------------------- pemilihan desain
def pick_designs(run, best, front_all):
    """[(sample_id, peran)] : desain terbaik skenario pertama dan titik knee front Pareto."""
    out = []
    for (r, label), (b, _, _) in best.items():
        if r == run and b is not None:
            out.append([int(b.sample_id), f"terbaik ({label})"])
            break
    g = front_all[front_all.run == run].sort_values("bw_mhz").reset_index(drop=True)
    if len(g) >= 3:
        k = pr.knee_index(g.bw_mhz.values, g.gain_fr_ieee_dbi.values)
        if k is not None:
            sid = int(g.sample_id[k])
            same = [o for o in out if o[0] == sid]
            if same:
                same[0][1] += " dan knee Pareto"
            else:
                out.append([sid, "knee Pareto"])
    return [(s, r) for s, r in out]


# ---------------------------------------------------------------- gambar
def fig_patterns(run, designs, df, out_dir, notes):
    """Satu gambar per run: tiap desain satu baris (polar kiri, kartesian kanan), bidang E dan H pada monitor terdekat fr."""
    rows, mrows = [], []
    for sid, role in designs:
        files = ff_files(run, sid)
        if not files:
            notes.append(f"Pola radiasi sampel {sid} ({run}): tidak ada berkas ff/, dilewati.")
            continue
        fr = float(df.loc[df.sample_id == sid, "fr_ghz"].iloc[0])
        f = min(files, key=lambda x: abs(x - fr))
        cuts = {phi: read_cut(p) for phi, p in sorted(files[f].items())}
        cuts = {k: v for k, v in cuts.items() if v is not None}
        if not cuts:
            notes.append(f"Pola radiasi sampel {sid} ({run}): berkas ff/ tidak terbaca, dilewati.")
            continue
        rows.append((sid, role, f, fr, cuts))
    if not rows:
        return None, []
    fig = plt.figure(figsize=(9.6, 4.2 * len(rows)))
    for i, (sid, role, f, fr, cuts) in enumerate(rows):
        axp = fig.add_subplot(len(rows), 2, 2 * i + 1, projection="polar")
        axc = fig.add_subplot(len(rows), 2, 2 * i + 2)
        dmax_all = max(float(np.nanmax(c["dir"])) for c in cuts.values())
        for k, (phi, c) in enumerate(cuts.items()):
            m = metrics(c)
            lab = f"phi {phi} (bidang {m['plane']})"
            axp.plot(np.radians(c["ang"]), c["dir"], color=COLORS[k % 4], lw=1.3, label=lab)
            axc.plot(c["ang"], c["dir"], color=COLORS[k % 4], lw=1.3, label=lab)
            mrows.append(dict(run=run, sampel=sid, peran=role, f=f, phi=phi, **m))
        axp.set_theta_zero_location("N")
        axp.set_theta_direction(-1)
        axp.set_rlim(dmax_all - 40.0, dmax_all + 2.0)
        axp.set_title(f"sampel {sid}, {role}\nmonitor {f:g} GHz (fr {fr:.3f} GHz), directivity dBi", fontsize=8)
        axp.legend(fontsize=7, loc="lower left", bbox_to_anchor=(-0.2, -0.18))
        axc.axhline(dmax_all - 3.0, color="gray", ls="--", lw=0.8, label="puncak dikurangi 3 dB")
        axc.set_xlim(-180, 180)
        axc.set_ylim(dmax_all - 40.0, dmax_all + 2.0)
        axc.set_xlabel("theta (derajat)")
        axc.set_ylabel("directivity (dBi)")
        axc.grid(alpha=0.3)
        axc.legend(fontsize=7, loc="lower center")
    fig.suptitle(f"Pola radiasi 2D bidang utama: {run}", fontsize=10)
    fig.tight_layout()
    fn = f"report_pattern_{run}.png"
    fig.savefig(os.path.join(out_dir, fn), dpi=130)
    plt.close(fig)
    return fn, mrows


def fig_vswr_eff(run, design, designs, band, out_dir, notes):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.0))
    n1 = n2 = 0
    for k, (sid, role) in enumerate(designs):
        col = COLORS[k % 4]
        c = read_curve(run, design, sid)
        if c is None:
            notes.append(f"VSWR sampel {sid} ({run}): kurva S11 tidak ada, dilewati.")
        else:
            a1.plot(c[0], vswr_from_db(c[1]), color=col, lw=1.4, label=f"sampel {sid}, {role}")
            n1 += 1
        e = read_eff(run, sid)
        if e is None:
            notes.append(f"Efisiensi sampel {sid} ({run}): berkas eff/ tidak ada, dilewati.")
        else:
            a2.plot(e.freq_ghz, e.eta_rad, color=col, lw=1.4, label=f"eta radiasi, sampel {sid}")
            a2.plot(e.freq_ghz, e.eta_tot, color=col, lw=1.2, ls="--", label=f"eta total, sampel {sid}")
            n2 += 1
    if not (n1 or n2):
        plt.close(fig)
        return None
    for a in (a1, a2):
        a.axvspan(band[0], band[1], color="gray", alpha=0.18)
        a.set_xlabel("frekuensi (GHz)")
        a.grid(alpha=0.3)
    a1.axhline(2.0, color="red", ls="--", lw=1, label="VSWR 2")
    a1.set_ylim(1.0, 6.0)
    a1.set_ylabel("VSWR")
    a1.set_title("VSWR dari S11", fontsize=9)
    a1.legend(fontsize=7)
    a2.set_ylim(0.0, 1.0)
    a2.set_ylabel("efisiensi")
    a2.set_title("Efisiensi radiasi dan total", fontsize=9)
    a2.legend(fontsize=6.5, loc="lower right")
    fig.suptitle(f"{run} (area abu: pita {band[0]:g} sampai {band[1]:g} GHz)", fontsize=10)
    fig.tight_layout()
    fn = f"report_vswr_eff_{run}.png"
    fig.savefig(os.path.join(out_dir, fn), dpi=130)
    plt.close(fig)
    return fn


def fig_phase(run, df, params, obj, ylabel, band, rl, out_dir):
    """Nilai fokus terhadap sample_id, berwarna oleh parameter dengan korelasi Spearman terbesar terhadap fokus.
    Mengembalikan (nama berkas, teks ringkas) atau (None, alasan)."""
    ok = (df.fr_ghz.between(band[0], band[1])) & (df.rl_min_db <= rl) & df[obj].notna()
    if int(ok.sum()) < 8:
        return None, f"kurang dari 8 sampel fisibel di {run}; gambar fase optimasi dilewati."
    cand = [p for p in params if p in df.columns]
    sub = df[ok]
    rho = {p: sub[p].corr(sub[obj], method="spearman") for p in cand if sub[p].nunique() > 2}
    rho = {k: v for k, v in rho.items() if np.isfinite(v)}
    prm = max(rho, key=lambda k: abs(rho[k])) if rho else None
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    ax.scatter(df.sample_id[~ok], df[obj][~ok].fillna(0), s=10, color="lightgray", label="di luar pita atau RL di atas batas")
    sc = ax.scatter(df.sample_id[ok], df[obj][ok], s=22, c=(df[prm][ok] if prm else "#1f77b4"), cmap="viridis")
    if prm:
        fig.colorbar(sc, ax=ax, label=f"{prm} (mm)")
    runbest = df[obj].where(ok).cummax()
    ax.step(df.sample_id, runbest, where="post", color="red", lw=1.3, label="terbaik sejauh ini (fisibel)")
    ax.set_xlabel("sample_id")
    ax.set_ylabel(ylabel)
    ax.set_title(f"Fase optimasi: {run}", fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fn = f"report_phase_{run}.png"
    fig.savefig(os.path.join(out_dir, fn), dpi=130)
    plt.close(fig)
    # lompatan terbaik-sejauh-ini terbesar
    rb = runbest.values
    ids = df.sample_id.values
    jumps = [(rb[i] - rb[i - 1], i) for i in range(1, len(rb)) if np.isfinite(rb[i]) and np.isfinite(rb[i - 1]) and rb[i] > rb[i - 1]]
    txt = []
    if prm:
        txt.append(f"Parameter pewarna: {prm} (korelasi Spearman {rho[prm]:+.2f} terhadap {ylabel} pada sampel fisibel).")
    if jumps:
        gain, i = max(jumps)
        sid = int(ids[i])
        txt.append(f"Lompatan terbesar pada terbaik sejauh ini: {rb[i - 1]:.1f} ke {rb[i]:.1f} pada sampel {sid}.")
        if prm:
            before = df.loc[df.sample_id < sid, prm].max()
            after = df.loc[df.sample_id >= sid, prm].max()
            txt.append(f"Nilai maksimum {prm} sebelum sampel itu {before:.2f} mm dan sesudahnya {after:.2f} mm; bila keduanya berbeda jauh, "
                       "periksa apakah rentang parameter diubah di tengah pengumpulan (wilayah lama terbatas oleh batas).")
    return fn, " ".join(txt)


# ---------------------------------------------------------------- tabel
def table_summary(run, designs, df, design, band):
    rows = []
    for sid, role in designs:
        r = df.loc[df.sample_id == sid].iloc[0]
        e = read_eff(run, sid)
        eta_tot = float(np.interp(r.fr_ghz, e.freq_ghz, e.eta_tot)) if e is not None else None
        rows.append({"sampel": sid, "peran": role, "fr (GHz)": r.fr_ghz, "RL min (dB)": r.rl_min_db,
                     "VSWR": r.get("vswr", np.nan), "BW (MHz)": r.bw_mhz, "cakupan pita (%)": r.get("band_cover_pct", np.nan),
                     "directivity di fr (dBi)": r.get("d_peak_fr_dbi", np.nan), "gain di fr (dBi)": r.gain_fr_ieee_dbi,
                     "eta radiasi di fr": r.get("eta_rad_fr", np.nan), "eta total di fr": eta_tot if eta_tot is not None else np.nan})
    return pd.DataFrame(rows)


def tolerance_tables(run, out_dir):
    """Tabel dari analyze_tolerance (tolerance_<run>_summary.csv dan _yield.csv) bila ada di out_dir atau data/_compare."""
    res = {}
    for kind in ("summary", "yield"):
        for d in (out_dir, os.path.join(paths.DATA_DIR, "_compare")):
            p = os.path.join(d, f"tolerance_{run}_{kind}.csv")
            if os.path.exists(p):
                try:
                    res[kind] = pd.read_csv(p)
                    break
                except (OSError, ValueError, pd.errors.ParserError):
                    pass
    return res


# ---------------------------------------------------------------- pintu masuk
def build(runs, data, designs_by_run, best, front_all, out_dir, band, rl, obj, ylabel, mc, notes):
    """Kembalikan (baris markdown bagian 9, jumlah). Catatan tambahan ditambahkan ke `notes`."""
    md = ["## 9. Pola radiasi, metrik tambahan, dan fase optimasi", "",
          "Bagian ini dibaca dari berkas yang sudah ada (`curves/`, `eff/`, `ff/`, `batch_lhs.csv`). Pola yang tersimpan adalah DIRECTIVITY (dBi) "
          "pada irisan phi = 0 dan phi = 90 di frekuensi monitor terdekat dengan fr; gain di tabel ringkas dihitung terpisah dan dibatasi di fr, bukan di seluruh pita. "
          "Bidang E atau H ditentukan dari komponen dominan di boresight. Sumbu theta bertanda: sisi positif adalah sisi phi irisan, sisi negatif adalah phi + 180.", ""]
    for run in runs:
        df = data[run]
        dn = designs_by_run.get(run)
        dd = mc.load_design(dn) if dn else None
        sel = pick_designs(run, best, front_all)
        md += [f"### 9.{runs.index(run) + 1} {run}", ""]
        if not sel:
            md += ["Tidak ada desain fisibel untuk dipilih; bagian ini dilewati.", ""]
            continue
        sel = [(s, r) for s, r in sel if (df.sample_id == s).any()]
        md += ["**Tabel ringkas desain final**", ""] + df_md(table_summary(run, sel, df, dd, band)) + [""]
        fn, mrows = fig_patterns(run, sel, df, out_dir, notes)
        if fn:
            md += ["**Pola radiasi 2D (directivity)**", "", f"![Pola radiasi {run}]({fn})", ""]
            mt = pd.DataFrame([{"sampel": m["sampel"], "peran": m["peran"], "f (GHz)": m["f"], "phi": m["phi"], "bidang": m["plane"],
                                "Dmax (dBi)": m["dmax"], "arah puncak (derajat)": m["theta_peak"], "HPBW (derajat)": m["hpbw"],
                                "F/B (dB)": m["fb"], "XPD sektor HPBW (dB)": m["xpd"], "AR boresight (dB)": m["ar"]} for m in mrows]).round(2)
            mt = mt.astype(object).where(mt.notna(), "tidak ada")
            md += ["**Metrik pola** (HPBW: lebar sudut dengan directivity di atas puncak dikurangi 3 dB; F/B: puncak dikurangi maksimum di belahan belakang, "
                   "yaitu sudut 90 derajat atau lebih dari arah puncak; XPD: komponen utama di arah puncak dikurangi komponen silang maksimum di sektor HPBW; nilai di atas sekitar 60 dB mencerminkan batas numerik simulasi pada geometri simetris, bukan komponen silang yang bisa diukur)", ""] + df_md(mt, 2) + [""]
        fn = fig_vswr_eff(run, dd, sel, band, out_dir, notes)
        if fn:
            md += ["**VSWR dan efisiensi terhadap frekuensi**", "", f"![VSWR dan efisiensi {run}]({fn})", ""]
        tol = tolerance_tables(run, out_dir)
        if tol:
            md += ["**Toleransi fabrikasi** (dari `tools/analyze_tolerance.py`)", ""]
            if "summary" in tol:
                md += df_md(tol["summary"], 3) + [""]
            if "yield" in tol:
                md += df_md(tol["yield"], 2) + [""]
        fn, txt = fig_phase(run, df, list(dd.params) if dd else [], obj, ylabel, band, rl, out_dir)
        if fn:
            md += ["**Fase optimasi** (titik berwarna: sampel fisibel di pita dengan RL sesuai batas, tanpa syarat gain)", "", f"![Fase optimasi {run}]({fn})", "", txt, ""]
        else:
            notes.append(txt)
    return md
