"""
cstopt/ml/core.py - inti GPR + Constrained Bayesian Optimization yang TIDAK bergantung pada desain antena.

Semua hal spesifik desain (nama parameter, rentang, kolom target, objective, constraint, aturan
geometri) dibaca dari satu file konfigurasi, mis. designs/uslot_dgs_fr4.py. Untuk desain lain cukup
membuat file konfigurasi baru; kode di sini tidak perlu diubah.

Isi:
  - load_design / Design     : membaca konfigurasi desain
  - load_dataset             : membaca CSV hasil simulasi (+ fitur turunan dari kurva S11)
  - fit_gp / fit_models      : GPR (scikit-learn) dengan kernel ARD, input dinormalisasi ke [0,1]
  - acquisition              : Expected Improvement x Probability of Feasibility (constrained EI)
  - suggest                  : memilih q titik berikutnya (batch, Kriging believer)

Tahap (STAGES): objective dan constraint bisa didefinisikan sebagai daftar tahap di file desain.
Tahap aktif dipilih OTOMATIS dari data: BO tetap di tahap sekarang sampai ada minimal satu sampel
yang memenuhi constraint tahap berikutnya (atau 'advance_when'), lalu pindah ke tahap itu.
"""
import importlib
import os
import sys
import warnings

import re

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from scipy.stats import norm, qmc
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import (RBF, ConstantKernel, Matern,
                                              WhiteKernel)

TRANSFORMS = {"none": (lambda y: y, lambda y: y),
              "log1p": (np.log1p, np.expm1),
              "log10": (np.log10, lambda y: np.power(10.0, y))}


# ================================================================ desain
class Design:
    """Pembungkus modul konfigurasi desain."""

    REQUIRED = ["NAME", "PARAM_NAMES", "BOUNDS", "DATASET_CSV", "TARGETS"]

    def __init__(self, mod):
        miss = [k for k in self.REQUIRED if not hasattr(mod, k)]
        if not hasattr(mod, "STAGES"):
            miss += [k for k in ("OBJECTIVE", "CONSTRAINTS") if not hasattr(mod, k)]
        if miss:
            raise AttributeError(f"Konfigurasi desain '{mod.__name__}' belum punya: {miss}")
        self.mod = mod
        self.name = mod.NAME
        self.params = list(mod.PARAM_NAMES)
        self.lo = np.array([mod.BOUNDS[k][0] for k in self.params], float)
        self.hi = np.array([mod.BOUNDS[k][1] for k in self.params], float)
        self.decimals = getattr(mod, "DECIMALS", 3)
        self.id_col = getattr(mod, "ID_COLUMN", "sample_id")
        self.dataset = mod.DATASET_CSV
        self.run_dir = getattr(mod, "RUN_DIR", os.path.dirname(mod.DATASET_CSV))
        self.models_dir = getattr(mod, "MODELS_DIR", self.run_dir)      # gpr_models.joblib, gpr_metrics.csv
        self.figures_dir = getattr(mod, "FIGURES_DIR", self.run_dir)    # gambar PNG
        self.candidates = getattr(mod, "CANDIDATES_CSV",
                                  os.path.join(os.path.dirname(mod.DATASET_CSV), "bo_candidates.csv"))
        self.n_initial = getattr(mod, "N_INITIAL", 0)
        self.base_transforms = dict(getattr(mod, "TRANSFORMS", {}))
        self.is_valid = getattr(mod, "is_valid", lambda p: True)
        self.band = getattr(mod, "BAND_GHZ", None)
        self.curves_dir = getattr(mod, "CURVES_DIR", None)
        self.curve_file = getattr(mod, "CURVE_FILE", "s11_sample{sid}.csv")
        self.targets = list(mod.TARGETS)

        if hasattr(mod, "STAGES"):
            self.stages = [dict(st) for st in mod.STAGES]
        else:
            self.stages = [{"name": "tunggal", "objective": mod.OBJECTIVE, "constraints": mod.CONSTRAINTS}]
        if not self.stages:
            raise ValueError("STAGES tidak boleh kosong")
        for st in self.stages:
            if st["objective"]["goal"] not in ("min", "max"):
                raise ValueError("OBJECTIVE['goal'] harus 'min' atau 'max'")
            for c in st["constraints"]:
                if c["op"] not in (">=", "<="):
                    raise ValueError("op constraint harus '>=' atau '<='")
        self.force_stage = None      # isi dengan indeks (0,1,..) untuk memaksa tahap tertentu
        self.stage_idx = 0
        # --- opsi BO tambahan (semua nonaktif secara bawaan)
        self.foci = {k: dict(v) for k, v in getattr(mod, "FOCI", {}).items()}   # fokus: objective + constraint yang dipilih manual
        self.focus = None                                                       # stage-dict fokus aktif
        self.composites = dict(getattr(mod, "COMPOSITES", {}))                  # mis. gain = D + 10 log10(eta)
        self.use_composites = bool(getattr(mod, "USE_COMPOSITES", False))
        self.region = None            # {param: (lo, hi)} : region pencarian aktif (lebih sempit dari BOUNDS)
        self.margins = {}             # {kolom: margin}    : constraint diperketat sebesar margin hanya untuk PoF model
        self.sigma_mult = {}          # {kolom: pengali}   : kalibrasi std prediksi constraint
        self.calibrate = False
        self._load_stage(0)

    # --- tahap
    def _load_stage(self, i):
        self.stage_idx = i
        self._apply_stage(self.stages[i], self.stages[i].get("name", f"tahap{i + 1}"))

    def _apply_stage(self, st, name):
        self.stage_name = name
        self.objective = dict(st["objective"])
        self.constraints = [dict(c) for c in st["constraints"]]
        # EI dihitung di ruang asli objective, jadi objective tidak boleh ditransformasi
        self.transforms = {k: v for k, v in self.base_transforms.items()
                           if k != self.objective["column"]}
        cols = list(self.targets) + [self.objective["column"]] + [c["column"] for c in self.constraints]
        self.model_columns = list(dict.fromkeys(cols))
        self.sign = 1.0 if self.objective["goal"] == "max" else -1.0

    def activate(self, df):
        """Pilih tahap aktif dari data. Maju ke tahap berikutnya bila sudah ada sampel yang memenuhi
        'advance_when' (default: constraint tahap berikutnya). Mengembalikan indeks tahap."""
        if self.focus is not None:                      # fokus manual menggantikan tahap otomatis
            self._apply_stage(self.focus, self.focus["name"])
            return self.stage_idx
        if self.force_stage is not None:
            i = int(self.force_stage)
            if not 0 <= i < len(self.stages):
                raise ValueError(f"--stage di luar jangkauan (1..{len(self.stages)})")
        else:
            i = 0
            while i < len(self.stages) - 1:
                cond = self.stages[i].get("advance_when", self.stages[i + 1]["constraints"])
                if any(c["column"] not in df.columns for c in cond):
                    break
                if not feasible_mask(self, df, cond).any():
                    break
                i += 1
        self._load_stage(i)
        return i

    def set_focus(self, name, constraints=None):
        """Pilih fokus manual (objective + constraint dari FOCI di file desain), tanpa pindah tahap otomatis.
        constraints: daftar {'column','op','value'} yang mengganti (kolom, op) yang sama atau menambah constraint baru."""
        if name not in self.foci:
            raise SystemExit(f"Fokus '{name}' tidak ada. Tersedia: {', '.join(self.foci) or '(tidak ada FOCI di file desain)'}")
        st = {"name": f"fokus_{name}", "objective": dict(self.foci[name]["objective"]),
              "constraints": [dict(c) for c in self.foci[name]["constraints"]]}
        for new in constraints or []:
            hit = [c for c in st["constraints"] if c["column"] == new["column"] and c["op"] == new["op"]]
            if hit:
                for c in hit:
                    c["value"] = new["value"]
            else:
                st["constraints"].append(dict(new))
        self.focus = st
        self._apply_stage(st, st["name"])

    # --- skala
    def to_unit(self, P):
        return (np.asarray(P, float) - self.lo) / (self.hi - self.lo)

    def from_unit(self, U):
        return self.lo + np.asarray(U, float) * (self.hi - self.lo)

    def T(self, col):
        return TRANSFORMS[self.transforms.get(col, "none")]


def load_design(name=None):
    """Muat file desain dari designs/ (None = desain bawaan)."""
    from cstopt.loader import load_design_module
    return Design(load_design_module(name))


# ================================================================ dataset
def s11_features(f, s_db, band, limit=-10.0, dip_db=-6.0):
    """Fitur kontinu dari kurva S11 (selalu terdefinisi, tidak 'nol-menggelembung').

    rl_band_*      : statistik S11 di dalam pita (min = terbaik, makin negatif makin baik)
    n_dips         : jumlah dip (minimum lokal) dengan S11 <= dip_db
    dip_dist_ghz   : jarak (GHz) dari dip terdekat ke pita; 0 bila ada dip di dalam pita.
                     Bila tidak ada dip <= dip_db, titik minimum global kurva dipakai sebagai dip.
    dip_nearest_db : S11 (dB) di dip terdekat tersebut (bila jarak sama, dip yang lebih dalam).
    """
    grid = np.linspace(band[0], band[1], 401)
    sb = np.interp(grid, f, s_db)
    inner = s_db[1:-1]
    mins = np.where((inner < s_db[:-2]) & (inner <= s_db[2:]))[0] + 1
    dips = mins[s_db[mins] <= dip_db]
    cand = dips if len(dips) else np.array([int(np.argmin(s_db))])
    dist = np.maximum(np.maximum(band[0] - f[cand], f[cand] - band[1]), 0.0)
    order = np.lexsort((s_db[cand], dist))          # jarak terkecil, lalu paling dalam
    k = cand[order[0]]
    return {"rl_band_min_db": float(sb.min()),      # S11 TERBAIK di dalam pita
            "rl_band_max_db": float(sb.max()),      # S11 terburuk di dalam pita (datar bila pita >> BW antena)
            "rl_band_mean_db": float(sb.mean()),
            "n_dips": int(len(dips)),
            "dip_dist_ghz": float(dist[order[0]]),
            "dip_nearest_db": float(s_db[k])}


def add_s11_features(df, d):
    feats, missing = [], 0
    for sid in df[d.id_col].astype(int):
        path = os.path.join(d.curves_dir, d.curve_file.format(sid=sid))
        if not os.path.exists(path):
            feats.append({}); missing += 1
            continue
        c = pd.read_csv(path)
        feats.append(s11_features(c.iloc[:, 0].values, c.iloc[:, 1].values, d.band))
    out = pd.concat([df.reset_index(drop=True), pd.DataFrame(feats)], axis=1)
    if missing:
        print(f"[peringatan] {missing} sampel tidak punya file kurva di {d.curves_dir}; fitur turunannya NaN.")
    return out


def load_dataset(d):
    if not os.path.exists(d.dataset):
        raise FileNotFoundError(f"Dataset tidak ditemukan: {d.dataset}")
    df = pd.read_csv(d.dataset)
    miss = [k for k in d.params + [d.id_col] if k not in df.columns]
    if miss:
        raise ValueError(f"Kolom tidak ada di dataset: {miss}")
    df = df.sort_values(d.id_col).reset_index(drop=True)
    if d.band is not None and d.curves_dir:
        df = add_s11_features(df, d)
    d.activate(df)                       # pilih tahap BO aktif dari data (atau d.force_stage)
    need = [c for c in d.model_columns if c not in df.columns]
    if need:
        raise ValueError(f"Kolom target tidak ada di dataset: {need}. "
                         "Jika itu fitur dari kurva S11, pastikan CURVES_DIR benar.")
    return df


# ================================================================ GPR
def make_kernel(kind, dim):
    ls = np.ones(dim)
    if kind == "rbf":
        base = RBF(length_scale=ls, length_scale_bounds=(0.05, 20.0))
    elif kind == "matern52":
        base = Matern(length_scale=ls, length_scale_bounds=(0.05, 20.0), nu=2.5)
    else:
        raise ValueError("kernel harus 'rbf' atau 'matern52'")
    return (ConstantKernel(1.0, (1e-2, 1e2)) * base
            + WhiteKernel(1e-2, (1e-6, 1.0)))


def fit_gp(X, y, kind="rbf", n_restarts=5, seed=0):
    gp = GaussianProcessRegressor(kernel=make_kernel(kind, X.shape[1]), normalize_y=True,
                                  n_restarts_optimizer=n_restarts, random_state=seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        gp.fit(X, y)
    return gp


def lengthscales(gp):
    return np.atleast_1d(gp.kernel_.k1.k2.length_scale)


class GPModel:
    def __init__(self, col, tname, gp, X, yt, kind):
        self.col, self.tname, self.gp, self.X, self.yt, self.kind = col, tname, gp, X, yt, kind

    def predict_t(self, Xu):
        mu, sd = self.gp.predict(Xu, return_std=True)
        return mu, np.maximum(sd, 1e-9)

    def to_raw(self, mu, sd):
        inv = TRANSFORMS[self.tname][1]
        return inv(mu), 0.5 * np.abs(inv(mu + sd) - inv(mu - sd))

    def believe(self, x, y_t):
        """Kriging believer: tambahkan titik fantasi (hyperparameter kernel dikunci)."""
        Xa = np.vstack([self.X, x[None, :]])
        ya = np.append(self.yt, y_t)
        gp = GaussianProcessRegressor(kernel=self.gp.kernel_, optimizer=None, normalize_y=True)
        gp.fit(Xa, ya)
        return GPModel(self.col, self.tname, gp, Xa, ya, self.kind)


def fit_models(d, df, columns, kind="rbf", n_restarts=5, seed=0):
    X = d.to_unit(df[d.params].values)
    models = {}
    for col in columns:
        y = df[col].values.astype(float)
        m = np.isfinite(y)
        fwd, _ = d.T(col)
        yt = fwd(y[m])
        models[col] = GPModel(col, d.transforms.get(col, "none"),
                              fit_gp(X[m], yt, kind, n_restarts, seed), X[m], yt, kind)
    return models


# ================================================================ model turunan, region, kalibrasi
class CompositeModel:
    """Model turunan: jumlah berbobot beberapa model komponen, mis. gain = D + 10 log10(eta).
    Std digabung dengan asumsi komponen saling bebas."""

    def __init__(self, col, parts):
        self.col, self.parts, self.tname = col, parts, "none"        # parts: [(GPModel, bobot), ...]

    def predict_t(self, Xu):
        mu, var = 0.0, 0.0
        for m, w in self.parts:
            a, s = m.predict_t(Xu)
            mu, var = mu + w * a, var + (w * s) ** 2
        return mu, np.maximum(np.sqrt(var), 1e-9)

    def to_raw(self, mu, sd):
        return mu, sd

    def believe(self, x, y_t):
        parts = []
        for m, w in self.parts:
            a, _ = m.predict_t(x[None, :])
            parts.append((m.believe(x, float(a[0])), w))
        return CompositeModel(self.col, parts)


def apply_composites(d, models, df, kind="rbf", n_restarts=5, seed=0):
    """Ganti model langsung kolom turunan (COMPOSITES di file desain) dengan model komposit dari komponennya."""
    if not d.use_composites:
        return models
    X = d.to_unit(df[d.params].values)
    out = dict(models)
    for col, parts in d.composites.items():
        if col not in models:
            continue
        comps = []
        for src, w, tname in parts:
            if tname == "none" and src in models:
                comps.append((models[src], w))
                continue
            y = df[src].values.astype(float)
            m = np.isfinite(y) & ((y > 0) if tname == "log10" else True)
            yt = TRANSFORMS[tname][0](y[m])
            comps.append((GPModel(src, tname, fit_gp(X[m], yt, kind, n_restarts, seed), X[m], yt, kind), w))
        out[col] = CompositeModel(col, comps)
    return out


def calibrate_sigma(d, models, folds=5, seed=0):
    """Pengali std prediksi tiap kolom constraint dari z-score validasi silang (hyperparameter dikunci).
    Mengembalikan {kolom: (pengali, bias_z)}; pengali = std(z) dibatasi [1, 3]."""
    from sklearn.model_selection import KFold
    out = {}
    for col in dict.fromkeys(c["column"] for c in d.constraints):
        m = models.get(col)
        if not isinstance(m, GPModel) or len(m.yt) < 2 * folds:
            continue
        z = []
        for tr, te in KFold(folds, shuffle=True, random_state=seed).split(m.X):
            gp = GaussianProcessRegressor(kernel=m.gp.kernel_, optimizer=None, normalize_y=True)
            gp.fit(m.X[tr], m.yt[tr])
            mu, sd = gp.predict(m.X[te], return_std=True)
            z.extend((m.yt[te] - mu) / np.maximum(sd, 1e-9))
        z = np.asarray(z)
        out[col] = (float(np.clip(np.std(z), 1.0, 3.0)), float(np.mean(z)))
    return out


def parse_region(d, text):
    """'Lp=16:19,WD=7:8' -> {param: (lo, hi)} dijepit ke BOUNDS. Parameter yang tidak disebut memakai rentang penuh."""
    reg = {}
    for item in [x for x in (text or "").split(",") if x.strip()]:
        name, rng = item.split("=")
        name = name.strip()
        if name not in d.params:
            raise SystemExit(f"--region: parameter '{name}' tidak dikenal. Parameter: {', '.join(d.params)}")
        j = d.params.index(name)
        lo, hi = (float(v) for v in rng.split(":"))
        reg[name] = (max(lo, float(d.lo[j])), min(hi, float(d.hi[j])))
    return reg


def region_auto(d, df, k=8, margin=0.15):
    """Region di sekitar k desain terbaik (yang feasible bila ada): rentang tiap parameter diperlebar
    margin x lebar BOUNDS, dijepit ke BOUNDS."""
    oc = d.objective["column"]
    ok = feasible_mask(d, df)
    pool = (df[ok] if ok.any() else df).dropna(subset=[oc])
    pool = pool.sort_values(oc, ascending=(d.objective["goal"] == "min")).head(k)
    reg = {}
    for j, p in enumerate(d.params):
        w = margin * float(d.hi[j] - d.lo[j])
        reg[p] = (max(float(d.lo[j]), float(pool[p].min()) - w), min(float(d.hi[j]), float(pool[p].max()) + w))
    return reg


def parse_constraints(text):
    """'bw_mhz>=100,rl_band_min_db<=-10' -> [{'column','op','value'}]"""
    out = []
    for item in [x for x in (text or "").split(",") if x.strip()]:
        m = re.match(r"\s*([A-Za-z0-9_]+)\s*(>=|<=)\s*(-?[0-9.eE+-]+)\s*$", item)
        if not m:
            raise SystemExit(f"Constraint tidak valid: '{item}'. Format: kolom>=nilai atau kolom<=nilai")
        out.append({"column": m.group(1), "op": m.group(2), "value": float(m.group(3))})
    return out


def parse_margins(text):
    """'fr_ghz=0.1,d_peak_fr_dbi=0.2' -> {kolom: margin}"""
    out = {}
    for item in [x for x in (text or "").split(",") if x.strip()]:
        k, v = item.split("=")
        out[k.strip()] = float(v)
    return out


# ================================================================ BO
def feasible_mask(d, df, constraints=None):
    ok = np.ones(len(df), bool)
    for c in (d.constraints if constraints is None else constraints):
        v = df[c["column"]].values.astype(float)
        ok &= np.isfinite(v) & ((v >= c["value"]) if c["op"] == ">=" else (v <= c["value"]))
    return ok


def best_feasible(d, df):
    """Kembalikan (nilai terbaik dalam ruang 'maksimasi', indeks) atau (None, None)."""
    y = df[d.objective["column"]].values.astype(float)
    ok = feasible_mask(d, df) & np.isfinite(y)
    if not ok.any():
        return None, None
    s = np.where(ok, d.sign * y, -np.inf)
    i = int(np.argmax(s))
    return float(s[i]), i


def acquisition(d, models, Xu, f_best, xi):
    """Constrained EI = EI(x) * prod_i P(g_i(x) >= 0).
    Jika belum ada titik feasible, yang dimaksimalkan adalah probabilitas feasibility saja."""
    mu, sd = models[d.objective["column"]].predict_t(Xu)
    m = d.sign * mu
    pof = np.ones(len(Xu))
    for c in d.constraints:
        mc, sc = models[c["column"]].predict_t(Xu)
        sc = sc * d.sigma_mult.get(c["column"], 1.0)                   # kalibrasi std (opsional)
        mg = d.margins.get(c["column"], c.get("margin", 0.0))           # margin: constraint diperketat untuk PoF saja
        val = c["value"] + mg if c["op"] == ">=" else c["value"] - mg
        thr = d.T(c["column"])[0](val)
        pof *= norm.cdf((mc - thr) / sc) if c["op"] == ">=" else norm.cdf((thr - mc) / sc)
    if f_best is None:
        ei = np.zeros(len(Xu))
        acq = pof + 1e-6 * (m - m.mean()) / (m.std() + 1e-12)
    else:
        imp = m - f_best - xi
        z = imp / sd
        ei = imp * norm.cdf(z) + sd * norm.pdf(z)
        acq = ei * pof
    return acq, ei, pof


def snap(d, U):
    """Bulatkan ke resolusi parameter, jepit ke rentang, dan saring dengan aturan geometri desain."""
    U = np.clip(np.asarray(U, float), 0.0, 1.0)
    P = np.clip(np.round(d.from_unit(U), d.decimals), d.lo, d.hi)
    ok = np.array([bool(d.is_valid(dict(zip(d.params, row)))) for row in P])
    reg = getattr(d, "region", None)
    if reg:                                           # region pencarian aktif (lebih sempit dari BOUNDS)
        for j, p in enumerate(d.params):
            if p in reg:
                ok &= (P[:, j] >= reg[p][0] - 1e-9) & (P[:, j] <= reg[p][1] + 1e-9)
    return d.to_unit(P), P, ok


def candidate_pool(d, n, seed, X_existing, min_dist):
    m = int(np.ceil(np.log2(max(n, 2))))
    U = qmc.Sobol(len(d.params), scramble=True, seed=seed).random_base2(m)
    reg = getattr(d, "region", None)
    if reg:                                           # bangkitkan kandidat DI DALAM region (bukan saring setelahnya)
        span = d.hi - d.lo
        lo_u = np.array([(reg[p][0] - d.lo[j]) / span[j] if p in reg else 0.0 for j, p in enumerate(d.params)])
        hi_u = np.array([(reg[p][1] - d.lo[j]) / span[j] if p in reg else 1.0 for j, p in enumerate(d.params)])
        U = lo_u + U * (hi_u - lo_u)
    U, P, ok = snap(d, U)
    U = U[ok]
    if len(X_existing):
        U = U[cdist(U, X_existing).min(axis=1) >= min_dist]
    return U


def refine(d, models, U0, f_best, xi, rng, n_iter=12, n_jit=300, s0=0.08):
    """Pencarian lokal sederhana di sekitar kandidat terbaik (aman terhadap aturan geometri)."""
    out = []
    for u in U0:
        best_u = u.copy()
        best_a = acquisition(d, models, best_u[None, :], f_best, xi)[0][0]
        s = s0
        for _ in range(n_iter):
            J, _, ok = snap(d, best_u + rng.normal(0, s, (n_jit, len(u))))
            J = J[ok]
            if len(J) == 0:
                s *= 0.6
                continue
            a = acquisition(d, models, J, f_best, xi)[0]
            k = int(np.argmax(a))
            if a[k] > best_a:
                best_u, best_a = J[k], a[k]
            else:
                s *= 0.6
        out.append(best_u)
    return np.array(out)


def suggest(d, df, q=5, kind="rbf", seed=0, pool=32768, xi_frac=0.01, n_restarts=5, min_dist=0.05,
            spread=0.3):
    """Pilih q kandidat berikutnya. Kembalikan (DataFrame parameter, DataFrame laporan).
    min_dist : jarak minimum (ruang satuan [0,1]^d) dari data yang sudah ada
    spread   : jarak minimum antar kandidat dalam SATU batch (agar batch tidak kembar)"""
    rng = np.random.default_rng(seed)
    oc = d.objective["column"]
    models = fit_models(d, df, d.model_columns, kind, n_restarts, seed)
    if d.use_composites and d.composites:
        models = apply_composites(d, models, df, kind, n_restarts, seed)
        print("[opsi] model komposit aktif: " + ", ".join(c for c in d.composites if c in models))
    if d.calibrate:
        cal = calibrate_sigma(d, models, seed=seed)
        d.sigma_mult = {c: v[0] for c, v in cal.items()}
        print("[opsi] kalibrasi std: " + ", ".join(f"{c} x{v[0]:.2f} (bias z {v[1]:+.2f})" for c, v in cal.items()))
    if d.margins:
        print("[opsi] margin constraint (untuk PoF): " + ", ".join(f"{c} {m:g}" for c, m in d.margins.items()))
    if d.region:
        print("[opsi] region pencarian: " + ", ".join(f"{p} {lo:.2f}:{hi:.2f}" for p, (lo, hi) in d.region.items()))
    f_best, ib = best_feasible(d, df)
    xi = xi_frac * float(np.nanstd(df[oc].values))
    Xex = d.to_unit(df[d.params].values)
    U = candidate_pool(d, pool, seed, Xex, min_dist)
    if len(U) < q:
        raise RuntimeError("Kandidat valid terlalu sedikit; longgarkan BOUNDS atau aturan geometri.")

    if f_best is None:
        print("[info] Belum ada titik yang memenuhi SEMUA constraint; acquisition = probabilitas feasibility.")
    else:
        print(f"[info] Terbaik yang feasible saat ini ({oc}) = {d.sign * f_best:.4f} (sampel id "
              f"{int(df[d.id_col].iloc[ib])})")

    cur, picks, rows, chosen = dict(models), [], [], []
    for k in range(q):
        acq, _, _ = acquisition(d, cur, U, f_best, xi)
        seeds = U[np.argsort(-acq)[:8]]
        Ur = refine(d, cur, seeds, f_best, xi, rng)
        allU = np.vstack([U, Ur])
        a_all, ei_all, pof_all = acquisition(d, cur, allU, f_best, xi)
        if chosen:
            far = cdist(allU, np.array(chosen)).min(axis=1) >= spread
            a_all = np.where(far, a_all, -np.inf)
        j = int(np.argmax(a_all))
        x = allU[j]
        chosen.append(x)
        row = {**dict(zip(d.params, np.round(d.from_unit(x), d.decimals))),
               "acq": float(a_all[j]), "ei": float(ei_all[j]), "pof": float(pof_all[j])}
        for col, mdl in models.items():          # prediksi memakai model ASLI (bukan fantasi)
            mu, sd = mdl.predict_t(x[None, :])
            r_mu, r_sd = mdl.to_raw(mu, sd)
            row[f"pred_{col}"] = float(r_mu[0])
            row[f"std_{col}"] = float(r_sd[0])
        rows.append(row)
        picks.append(dict(zip(d.params, np.round(d.from_unit(x), d.decimals))))
        # Kriging believer: anggap prediksi mean sebagai hasil, lalu update model kerja
        for col in cur:
            mu, _ = cur[col].predict_t(x[None, :])
            cur[col] = cur[col].believe(x, float(mu[0]))
        U = U[cdist(U, x[None, :])[:, 0] >= spread]
    return pd.DataFrame(picks), pd.DataFrame(rows)


def convergence(d, df):
    """Nilai objective terbaik yang feasible setelah tiap evaluasi (urut sample_id)."""
    y = df[d.objective["column"]].values.astype(float)
    ok = feasible_mask(d, df) & np.isfinite(y)
    best, cur = [], np.nan
    for i in range(len(df)):
        if ok[i] and (np.isnan(cur) or d.sign * y[i] > d.sign * cur):
            cur = y[i]
        best.append(cur)
    return np.array(best)


# ---------------------------------------------------------------- peringatan batas parameter
def edge_hits(d, X, edge=0.05, frac=0.6):
    """Parameter yang menempel batas pada >= frac dari baris X (nilai asli, kolom = d.params).
    Kembalikan daftar (nama, 'bawah'|'atas', jumlah, n, nilai batas)."""
    X = np.atleast_2d(np.asarray(X, float))
    n = len(X)
    if n < 3:
        return []
    U = d.to_unit(X)
    hits = []
    for j, p in enumerate(d.params):
        lo_n, hi_n = int((U[:, j] < edge).sum()), int((U[:, j] > 1 - edge).sum())
        if lo_n >= frac * n:
            hits.append((p, "bawah", lo_n, n, float(d.lo[j])))
        elif hi_n >= frac * n:
            hits.append((p, "atas", hi_n, n, float(d.hi[j])))
    return hits


def bound_hits(d, df, k=10, edge=0.05, frac=0.6):
    """Cek k desain terbaik (yang feasible bila ada) terhadap batas parameter."""
    oc = d.objective["column"]
    ok = feasible_mask(d, df)
    pool = (df[ok] if ok.any() else df).dropna(subset=[oc])
    pool = pool.sort_values(oc, ascending=(d.objective["goal"] == "min")).head(k)
    return edge_hits(d, pool[d.params].values, edge, frac)

