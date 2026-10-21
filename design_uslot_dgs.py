"""
Konfigurasi desain: antena mikrostrip U-Slot + DGS Dumbbell, FR-4, target 3,3-3,7 GHz.

INI SATU-SATUNYA FILE YANG SPESIFIK UNTUK ANTENA INI. Untuk desain lain, salin file ini,
ganti isinya, lalu jalankan skrip dengan  --design nama_file_baru  (tanpa .py).
"""
import os

from lhs_maximin import BOUNDS, DECIMALS, PARAM_NAMES, geometry_problems   # sumber tunggal rentang & aturan

NAME = "uslot_dgs_dumbbell_fr4"
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- data
# Nama project CST = nama folder keluaran batch_trials.py:  export/<RUN_NAME>/
RUN_NAME = "MicrostripAntena"
RUN_DIR = os.path.join(HERE, "export", RUN_NAME)
DATASET_CSV = os.path.join(RUN_DIR, "batch_lhs.csv")                 # keluaran batch_trials.py
CANDIDATES_CSV = os.path.join(HERE, "export", "bo_candidates.csv")   # masukan batch_trials.py --samples
CURVES_DIR = os.path.join(RUN_DIR, "curves")                         # s11_sample{sid}.csv
CURVE_FILE = "s11_sample{sid}.csv"
ID_COLUMN = "sample_id"
N_INITIAL = 80          # jumlah sampel awal (LHS); sampel dengan id lebih besar dianggap hasil BO

# ---------------------------------------------------------------- parameter (dari lhs_maximin.py)
# PARAM_NAMES, BOUNDS, DECIMALS diimpor di atas. Untuk desain lain, definisikan langsung di sini:
#   PARAM_NAMES = ["a", "b", ...];  BOUNDS = {"a": (min, max), ...};  DECIMALS = 3


def is_valid(params):
    """Aturan geometri desain (sama dengan check_geometry di batch_trials.py)."""
    return not geometry_problems(params)


# ---------------------------------------------------------------- target pemodelan
BAND_GHZ = (3.3, 3.7)    # pita yang diinginkan; dipakai untuk fitur turunan dari kurva S11
RL_LIMIT_DB = -10.0

# Kolom dataset yang dimodelkan GPR. Kolom turunan (rl_band_*, dip_dist_ghz, dip_nearest_db, n_dips)
# dihitung otomatis dari kurva S11 di CURVES_DIR.
TARGETS = ["fr_ghz", "rl_min_db", "bw_mhz", "s11_at_f0_db", "d_peak_dbi", "d_peak_fr_dbi",
           "eta_rad_fr", "gain_fr_ieee_dbi",
           "rl_band_min_db", "rl_band_max_db", "rl_band_mean_db",
           "dip_dist_ghz", "dip_nearest_db"]

# Transformasi untuk target yang distribusinya miring/banyak nol (hanya untuk TARGETS non-objective)
TRANSFORMS = {"bw_mhz": "log1p"}

# ---------------------------------------------------------------- objective & constraint
# TAHAP 1 (default): rl_band_min_db = S11 TERBAIK di dalam pita 3,3-3,7 GHz (makin negatif makin baik).
# Nilainya selalu terdefinisi dan membaik mulus saat dip resonansi bergerak ke dalam pita, jadi
# GPR punya gradien untuk dipelajari (BW langsung = 0 untuk sebagian besar sampel, sehingga datar).
OBJECTIVE = {"column": "rl_band_min_db", "goal": "min"}

# Constraint = daftar syarat feasibility. CONTOH/PLACEHOLDER: sesuaikan dengan spesifikasi Anda.
# d_peak_fr_dbi = directivity di monitor terdekat frekuensi resonansi (penjaga pola radiasi).
# Gain (gain_fr_ieee_dbi) kini valid karena efisiensi diukur di banyak frekuensi, tetapi target
# >= 5 dBi untuk satu patch FR-4 sulit tercapai; tentukan batas gain bersama pembimbing sebelum memakainya.
CONSTRAINTS = [
    {"column": "d_peak_fr_dbi", "op": ">=", "value": 4.0},
]

# TAHAP 2 (setelah ada sampel dengan rl_band_min_db <= -10): maksimalkan bandwidth, dengan
# resonansi di dalam pita dan pencocokan terpenuhi. Ganti OBJECTIVE dan CONSTRAINTS menjadi:
#
# OBJECTIVE = {"column": "bw_mhz", "goal": "max"}      # (objective tidak boleh di-TRANSFORMS)
# CONSTRAINTS = [
#     {"column": "fr_ghz",         "op": ">=", "value": 3.3},
#     {"column": "fr_ghz",         "op": "<=", "value": 3.7},
#     {"column": "rl_band_min_db", "op": "<=", "value": -10.0},
#     {"column": "d_peak_fr_dbi",  "op": ">=", "value": 4.0},
# ]
# dan hapus "bw_mhz" dari TRANSFORMS.