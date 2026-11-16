"""P2-3 Tahap A: penaksir alternatif peluang feasible (PoF) dan model dua bagian untuk BW, HANYA untuk uji offline.

Dipakai oleh `py main.py validate --pof-compare`. Tidak dipakai oleh `suggest`. Penaksir (semua dilatih pada data
latih yang sama dengan model GP di tiap batch maju):
  (a) p_prod  : PoF perkalian regresi (yang dipakai acquisition sekarang)
  (b) p_gpc   : GaussianProcessClassifier langsung untuk label feasible
      p_logit : regresi logistik pada fitur RBF (Nystroem)
  (c) dua bagian untuk BW: P(BW > 0) dari klasifikator x BW | BW > 0 dari GP pada log BW
Ukuran: skor Brier, selisih Brier berpasangan dengan bootstrap, kemiringan kalibrasi (idealnya 1).
"""
import warnings

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessClassifier
from sklearn.gaussian_process.kernels import ConstantKernel as C, RBF
from sklearn.kernel_approximation import Nystroem
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from cstopt.ml import core as mc


def _const(ytr, n):
    return np.full(n, float(np.mean(ytr)) if len(ytr) else 0.5)


def gpc_proba(Xtr, ytr, Xte, seed=0):
    """GP classifier isotropik (ruang satuan). Satu kelas saja -> laju tetap."""
    if len(ytr) < 5 or ytr.min() == ytr.max():
        return _const(ytr, len(Xte))
    clf = GaussianProcessClassifier(kernel=C(1.0, (0.1, 100.0)) * RBF(0.5, (0.05, 5.0)),
                                    n_restarts_optimizer=0, random_state=seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        clf.fit(Xtr, ytr)
    return clf.predict_proba(Xte)[:, list(clf.classes_).index(1)]


def logit_proba(Xtr, ytr, Xte, seed=0):
    """Regresi logistik L2 pada fitur RBF acak (Nystroem)."""
    if len(ytr) < 5 or ytr.min() == ytr.max():
        return _const(ytr, len(Xte))
    pipe = make_pipeline(Nystroem(gamma=1.0, n_components=min(100, len(Xtr)), random_state=seed),
                         LogisticRegression(C=1.0, max_iter=3000))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        pipe.fit(Xtr, ytr)
    return pipe.predict_proba(Xte)[:, 1]


def batch_predict(d, models, tr, te, Xu, p_prod, kind="rbf", restarts=2, seed=0):
    """Satu batch uji: kembalikan DataFrame penaksir alternatif untuk baris te."""
    Xtr = d.to_unit(tr[d.params].values)
    ytr = mc.feasible_mask(d, tr).astype(int)
    out = {"sample_id": te[d.id_col].values.astype(int), "y": mc.feasible_mask(d, te).astype(int),
           "p_prod": np.asarray(p_prod, float), "p_gpc": gpc_proba(Xtr, ytr, Xu, seed),
           "p_logit": logit_proba(Xtr, ytr, Xu, seed)}
    n = len(te)
    nan = np.full(n, np.nan)
    band = getattr(d, "band", None)
    out["inband"] = (te["fr_ghz"].between(*band).values.astype(int)
                     if band is not None and "fr_ghz" in te.columns else np.zeros(n, int))
    out.update(bw_aktual=nan, bw_gp=nan, bw_2part=nan, pos_aktual=nan, p_pos_gp=nan, p_pos_gpc=nan)
    if "bw_mhz" in tr.columns:
        bw_tr = tr["bw_mhz"].values.astype(float)
        ok = np.isfinite(bw_tr)
        pos = ok & (bw_tr > 0)
        mdl = models.get("bw_mhz") or mc.fit_models(d, tr, ["bw_mhz"], kind, restarts, seed)["bw_mhz"]
        mu, sd = mdl.predict_t(Xu)
        r_mu, r_sd = mdl.to_raw(mu, sd)
        p_pos = gpc_proba(Xtr[ok], pos[ok].astype(int), Xu, seed)
        cond = nan
        if pos.sum() >= 8:
            gp = mc.fit_gp(Xtr[pos], np.log(bw_tr[pos]), kind, restarts, seed)
            m, s = gp.predict(Xu, return_std=True)
            cond = np.exp(m + 0.5 * s ** 2)
        bw_te = te["bw_mhz"].values.astype(float)
        out.update(bw_aktual=bw_te, bw_gp=np.asarray(r_mu, float), bw_2part=p_pos * cond,
                   pos_aktual=(bw_te > 0).astype(float), p_pos_gp=norm.cdf(np.asarray(r_mu) / np.maximum(r_sd, 1e-9)),
                   p_pos_gpc=p_pos)
    return pd.DataFrame(out)


def brier(p, y):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def calib_slope(p, y):
    """Kemiringan regresi logistik label terhadap logit(p): 1 = terkalibrasi, < 1 = terlalu yakin."""
    y = np.asarray(y)
    if y.min() == y.max():
        return float("nan")
    z = np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
    lr = LogisticRegression(C=1e6, max_iter=1000).fit(z.reshape(-1, 1), y)
    return float(lr.coef_[0, 0])


def boot_diff(pa, pb, y, n=1000, seed=0):
    """Selisih Brier berpasangan (a dikurangi b; positif = b lebih baik): rata rata dan CI 95% bootstrap."""
    da = (np.asarray(pa) - y) ** 2 - (np.asarray(pb) - y) ** 2
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(da), (n, len(da)))
    bm = da[idx].mean(axis=1)
    return float(da.mean()), float(np.percentile(bm, 2.5)), float(np.percentile(bm, 97.5))


def report(A, band_col=None):
    """Cetak tabel perbandingan dan kembalikan ringkasan {penaksir: dict}."""
    y = A["y"].values.astype(float)
    ref = float(y.mean() * (1 - y.mean()))
    ba = brier(A["p_prod"], y)
    sa = calib_slope(A["p_prod"].values, y)
    print(f"\n== PERBANDINGAN PoF (P2-3, n = {len(A)}; laju feasible aktual {y.mean():.2f}; Brier acuan laju tetap {ref:.3f}) ==")
    print(f"{'penaksir':10s} {'rata p':>7s} {'Brier':>7s} {'vs (a)':>8s} {'selisih Brier (a-b) [CI 95%]':>32s} {'kemiringan':>11s}")
    summ = {}
    for name, label in (("p_prod", "(a) prod"), ("p_gpc", "(b) GPC"), ("p_logit", "(b) logit")):
        p = A[name].values
        b = brier(p, y)
        sl = calib_slope(p, y)
        if name == "p_prod":
            print(f"{label:10s} {p.mean():7.2f} {b:7.3f} {'-':>8s} {'-':>32s} {sl:11.2f}")
            continue
        dm, lo, hi = boot_diff(A["p_prod"].values, p, y)
        rel = (ba - b) / ba if ba > 0 else float("nan")
        better_slope = abs(1 - sl) < abs(1 - sa) if np.isfinite(sl) and np.isfinite(sa) else False
        passed = bool(rel > 0.10 and lo > 0 and better_slope)
        summ[name] = dict(brier=b, rel=rel, lo=lo, hi=hi, slope=sl, passed=passed)
        print(f"{label:10s} {p.mean():7.2f} {b:7.3f} {100 * rel:+7.1f}% {dm:+10.4f} [{lo:+.4f}, {hi:+.4f}] {sl:11.2f}"
              f"   {'LOLOS gerbang' if passed else 'tidak lolos'}")
    print(f"kemiringan (a) = {sa:.2f}. Gerbang per run: Brier membaik > 10%, CI selisih di atas 0, kemiringan lebih dekat ke 1.")
    if A["bw_aktual"].notna().any():
        m = A["bw_aktual"].notna() & A["bw_2part"].notna()
        a, g, t = A.loc[m, "bw_aktual"].values, A.loc[m, "bw_gp"].values, A.loc[m, "bw_2part"].values
        print(f"\n== BW: GP mentah vs dua bagian (n = {int(m.sum())}; BW = 0 pada {100 * np.mean(a <= 0):.0f}% sampel uji) ==")
        for nm, v in (("GP mentah", g), ("dua bagian", t)):
            print(f"  {nm:11s} RMSE {np.sqrt(np.mean((a - v) ** 2)):7.2f} MHz | MAE {np.mean(np.abs(a - v)):7.2f} MHz | bias {np.mean(a - v):+7.2f} MHz")
        pa = A.loc[m, "pos_aktual"].values
        for nm, col in (("P(BW>0) dari GP", "p_pos_gp"), ("P(BW>0) dari GPC", "p_pos_gpc")):
            print(f"  {nm:17s} Brier {brier(A.loc[m, col].values, pa):.3f} (acuan laju tetap {pa.mean() * (1 - pa.mean()):.3f})")
        ib = m & (A["inband"].values == 1)
        if ib.sum() >= 3:
            a, g, t = A.loc[ib, "bw_aktual"].values, A.loc[ib, "bw_gp"].values, A.loc[ib, "bw_2part"].values
            print(f"  di dalam pita (fr aktual di pita, n = {int(ib.sum())}):")
            for nm, v in (("GP mentah", g), ("dua bagian", t)):
                print(f"    {nm:11s} RMSE {np.sqrt(np.mean((a - v) ** 2)):7.2f} MHz | MAE {np.mean(np.abs(a - v)):7.2f} MHz | bias {np.mean(a - v):+7.2f} MHz")
    return summ
