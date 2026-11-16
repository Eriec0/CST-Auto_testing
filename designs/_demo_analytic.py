"""
Desain DEMO analitik: pengganti CST untuk menguji seluruh alur (lhs, mock_run, qc, train, suggest, pareto) di mesin mana pun.

BUKAN model antena yang akurat. Satu patch resonan sederhana: fr dari panjang L dan lebar W (rumus patch), pencocokan
dari offset catu s (kopling beta), bandwidth dari faktor kualitas Q = 500/W, efisiensi dan directivity dari W dan fr.
Kolom hasil identik dengan keluaran `main.py run`, jadi kode ML, BO, dan Pareto berjalan tanpa diubah.

Pakai:  py tools/mock_run.py --design _demo_analytic --samples <csv>        (panduan: docs/membuat_desain_baru.md)
File ini diawali garis bawah: tidak muncul di daftar desain dan tidak diuji `smoke_test.py`.
"""
import os

import numpy as np

from cstopt import paths

NAME = "demo_analytic"

# ---------------------------------------------------------------- data
RUN_NAME = "DemoAnalytic"
RUN_DIR = paths.run_dir(RUN_NAME)
DATASET_CSV = os.path.join(RUN_DIR, "batch_lhs.csv")
CANDIDATES_CSV = os.path.join(paths.samples_dir(RUN_NAME), "bo_candidates.csv")
CURVES_DIR = os.path.join(RUN_DIR, "curves")
MODELS_DIR = paths.models_dir(RUN_NAME)
FIGURES_DIR = paths.figures_dir(RUN_NAME)
CURVE_FILE = "s11_sample{sid}.csv"
ID_COLUMN = "sample_id"
N_INITIAL = 20

# ---------------------------------------------------------------- parameter dan geometri
PARAM_NAMES = ["L", "W", "g", "s"]            # panjang patch, lebar patch, celah, offset catu (mm)
BOUNDS = {"L": (18.0, 26.0), "W": (20.0, 32.0), "g": (0.2, 1.0), "s": (0.0, 4.0)}
DECIMALS = 3


def geometry_problems(p):
    """Aturan contoh (sering menolak sebagian sampel LHS, supaya jalur penyaringan ikut teruji)."""
    bad = []
    if p["g"] > p["W"] / 30.0:
        bad.append("celah terlalu lebar terhadap W")
    if p["s"] >= p["L"] / 4.0:
        bad.append("offset catu terlalu jauh")
    return bad


def is_valid(params):
    return not geometry_problems(params)


# ---------------------------------------------------------------- target pemodelan (sama dengan desain FR-4)
BAND_GHZ = (3.3, 3.7)
RL_LIMIT_DB = -10.0
TARGETS = ["fr_ghz", "rl_min_db", "bw_mhz", "s11_at_f0_db", "d_peak_dbi", "d_peak_fr_dbi",
           "eta_rad_fr", "gain_fr_ieee_dbi",
           "rl_band_min_db", "rl_band_max_db", "rl_band_mean_db",
           "dip_dist_ghz", "dip_nearest_db"]
TRANSFORMS = {"bw_mhz": "log1p"}

STAGES = [
    {"name": "tahap1_match",
     "objective": {"column": "rl_band_min_db", "goal": "min"},
     "constraints": [{"column": "d_peak_fr_dbi", "op": ">=", "value": 4.0}]},
    {"name": "tahap2_bandwidth",
     "objective": {"column": "bw_mhz", "goal": "max"},
     "constraints": [{"column": "fr_ghz", "op": ">=", "value": BAND_GHZ[0]},
                     {"column": "fr_ghz", "op": "<=", "value": BAND_GHZ[1]},
                     {"column": "rl_band_min_db", "op": "<=", "value": RL_LIMIT_DB},
                     {"column": "d_peak_fr_dbi", "op": ">=", "value": 4.0}]},
]
SUBSTRATE = {"material": "Demo analitik", "er": 4.3, "tand": 0.02, "h": 1.6}

_IN_BAND = [{"column": "fr_ghz", "op": ">=", "value": BAND_GHZ[0]},
            {"column": "fr_ghz", "op": "<=", "value": BAND_GHZ[1]},
            {"column": "rl_band_min_db", "op": "<=", "value": RL_LIMIT_DB},
            {"column": "d_peak_fr_dbi", "op": ">=", "value": 4.0}]
FOCI = {
    "bw": {"objective": {"column": "bw_mhz", "goal": "max"}, "constraints": _IN_BAND},
    "gain": {"objective": {"column": "gain_fr_ieee_dbi", "goal": "max"},
             "constraints": _IN_BAND + [{"column": "bw_mhz", "op": ">=", "value": 50.0}]},
}

# ---------------------------------------------------------------- antarmuka sisi CST (dibaca config.py; di sini hanya untuk mock_run)
BASE_PARAMS = dict(L=21.0, W=26.0, g=0.5, s=2.0)
CST = {"band_ghz": BAND_GHZ, "rl_limit_db": RL_LIMIT_DB, "f0_ghz": 3.5, "monitors_ghz": (2.5, 4.5, 0.25),
       "bw_min_mhz": 100.0, "gain_min_dbi": 5.0}


# ---------------------------------------------------------------- model analitik (dipakai tools/mock_run.py)
def mock_response(p, f):
    """Respons buatan pada frekuensi f (GHz, array). Kembalikan dict array dengan panjang sama dengan f:
    s11_db, eta_rad, eta_tot, d_dbi (directivity puncak). Antarmuka ini yang diminta mock_run dari desain mana pun."""
    f = np.asarray(f, float)
    L, W, g, s = p["L"], p["W"], p["g"], p["s"]
    er, h = SUBSTRATE["er"], SUBSTRATE["h"]
    eeff = (er + 1) / 2 + (er - 1) / 2 / np.sqrt(1 + 12 * h / W)
    fr = 300.0 / (2 * L * np.sqrt(eeff)) * (1 - 0.02 * g)           # GHz (c = 300 mm/ns)
    q0 = 500.0 / W                                                   # makin lebar, makin lebar pita
    beta = np.exp(0.45 * (s - 2.0))                                  # kopling: beta = 1 cocok sempurna
    delta = f / fr - fr / f
    gam = (beta - 1 + 1j * q0 * delta) / (beta + 1 + 1j * q0 * delta)
    s11 = 20 * np.log10(np.maximum(np.abs(gam), 1e-4))
    eta_rad = np.clip(0.80 - 0.012 * (W - 22.0) - 0.15 * np.abs(f - fr) / 0.5, 0.05, 0.95)
    eta_tot = eta_rad * (1 - np.abs(gam) ** 2)
    d_dbi = 6.5 + 0.03 * (W - 22.0) + 0.4 * (f - 3.5)
    return {"s11_db": s11, "eta_rad": eta_rad, "eta_tot": eta_tot, "d_dbi": d_dbi}
