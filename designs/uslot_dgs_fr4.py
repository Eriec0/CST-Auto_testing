"""
Konfigurasi desain: antena mikrostrip U-Slot + DGS Dumbbell, FR-4, target 3,3-3,7 GHz.

INI SATU-SATUNYA FILE YANG SPESIFIK UNTUK ANTENA/SUBSTRAT INI. Isinya: parameter, rentang (BOUNDS),
aturan geometri, lokasi data, kolom target, objective dan constraint tiap tahap BO.
Untuk desain atau substrat lain: salin file ini ke designs/nama_baru.py, ubah isinya, lalu pilih
desain itu di GUI atau dengan  --design nama_baru  (tanpa .py).
"""
import os

from cstopt import paths

NAME = "uslot_dgs_dumbbell_fr4"

# ---------------------------------------------------------------- data
# Nama project CST = nama folder data:  data/<RUN_NAME>/
RUN_NAME = "MicrostripAntena"
RUN_DIR = paths.run_dir(RUN_NAME)
DATASET_CSV = os.path.join(RUN_DIR, "batch_lhs.csv")                           # keluaran `main.py run`
CANDIDATES_CSV = os.path.join(paths.samples_dir(RUN_NAME), "bo_candidates.csv")  # masukan `main.py run --samples`
CURVES_DIR = os.path.join(RUN_DIR, "curves")                                   # s11_sample{sid}.csv
MODELS_DIR = paths.models_dir(RUN_NAME)                                        # gpr_models.joblib, gpr_metrics.csv
FIGURES_DIR = paths.figures_dir(RUN_NAME)                                      # gambar PNG
CURVE_FILE = "s11_sample{sid}.csv"
ID_COLUMN = "sample_id"
N_INITIAL = 80          # jumlah sampel awal (LHS); sampel dengan id lebih besar dianggap hasil BO

# ---------------------------------------------------------------- parameter, rentang, aturan geometri
PARAM_NAMES = ["Lp", "Wp", "LU", "WU", "gU", "PU", "LI", "LD", "WD", "gD", "PD"]

# Rentang (min, max) dalam mm. Titik acuan baseline ada di komentar.
# Lp digeser ke atas karena resonansi baseline (3,99 GHz) berada di atas 3,5 GHz
# (percobaan Anda sebelumnya bergerak ke Lp ~ 20,8). SESUAIKAN bila perlu.
BOUNDS = {
    "Lp": (15.0, 25.0),   # baseline 20.22 | diperlebar (semula 20-23, lalu 18-25): desain BW tertinggi menempel di 18
    "Wp": (22.0, 31.0),   # baseline 26.33 | diperlebar (semula 24-29)
    "LU": (3.0, 12.0),    # baseline 10.0  | diperlebar (semula 6-10,5, lalu 5-12): desain BW tertinggi menempel di 5
    "WU": (4.5, 13.0),    # baseline 10.5  | batas bawah 7 -> 6 -> 4,5: desain BW tertinggi menempel di 6
    "gU": (0.4, 1.2),     # baseline 0.6
    "PU": (-1.0, 3.5),    # baseline 2.0
    "LI": (4.5, 7.0),     # baseline 6.15
    "LD": (1.0, 5.0),     # baseline 3.0   | batas bawah 2 -> 1 (semua kandidat BO menempel di 2)
    "WD": (2.0, 8.0),     # baseline 3.0   | batas atas 5 -> 6 -> 8: desain BW tertinggi menempel di 6 (Ws = Wp+6*hs, aman)
    "gD": (0.2, 1.0),     # baseline 0.3
    "PD": (-3.0, 3.0),    # baseline 0.0
}
DECIMALS = 3              # pembulatan nilai parameter (mm)
AD = 2.5                  # panjang penghubung dumbbell (tetap, sama dengan macro)
MARGIN = 0.5              # margin dari check_geometry


# ---------------------------------------------------------------- geometri
def geometry_problems(p):
    """Aturan yang sama dengan check_geometry() di cstopt/cst/batch.py, ditambah beberapa
    pengaman wajar. Kembalikan daftar masalah (kosong = valid)."""
    yb = p["Lp"] / 2 + p["PU"] - p["LU"] / 2
    yt = p["Lp"] / 2 + p["PU"] + p["LU"] / 2
    bad = []
    if yb <= p["LI"] + MARGIN:
        bad.append("dasar U-Slot terlalu dekat ujung inset")
    if yt >= p["Lp"] - MARGIN:
        bad.append("ujung U-Slot hampir keluar patch")
    if p["WU"] >= p["Wp"] - 1:
        bad.append("WU terlalu lebar terhadap Wp")
    if p["WU"] <= 4 * p["gU"]:
        bad.append("WU terlalu sempit terhadap gU")
    if p["gD"] >= p["WD"]:
        bad.append("penghubung DGS lebih lebar dari kepala")
    yd = p["Lp"] / 2 + p["PD"]
    half = AD / 2 + p["LD"]
    if yd - half < 0 or yd + half > p["Lp"]:
        bad.append("DGS keluar dari proyeksi patch")
    return bad


def is_valid(params):
    """Aturan geometri desain (sama dengan check_geometry di cstopt/cst/batch.py)."""
    return not geometry_problems(params)


# ---------------------------------------------------------------- target pemodelan
BAND_GHZ = (3.3, 3.7)    # SATU-SATUNYA tempat mengubah pita: dipakai fitur kurva S11 dan constraint fr tahap 2
RL_LIMIT_DB = -10.0

# Kolom dataset yang dimodelkan GPR. Kolom turunan (rl_band_*, dip_dist_ghz, dip_nearest_db, n_dips)
# dihitung otomatis dari kurva S11 di CURVES_DIR.
TARGETS = ["fr_ghz", "rl_min_db", "bw_mhz", "s11_at_f0_db", "d_peak_dbi", "d_peak_fr_dbi",
           "eta_rad_fr", "gain_fr_ieee_dbi",
           "rl_band_min_db", "rl_band_max_db", "rl_band_mean_db",
           "dip_dist_ghz", "dip_nearest_db"]

# Transformasi untuk target yang distribusinya miring/banyak nol (hanya untuk TARGETS non-objective)
TRANSFORMS = {"bw_mhz": "log1p"}

# ---------------------------------------------------------------- tahap BO (objective & constraint)
# BO berjalan dalam TAHAP. Tahap aktif dipilih OTOMATIS dari data: tetap di tahap sekarang sampai
# ada minimal satu sampel yang memenuhi constraint tahap berikutnya, lalu pindah ke sana.
# Paksa tahap tertentu dengan  --stage N  (1 = tahap 1, 2 = tahap 2) di `main.py suggest` / `main.py backtest`.
#
# TAHAP 1: rl_band_min_db = S11 TERBAIK di dalam pita 3,3-3,7 GHz (makin negatif makin baik).
#   Nilainya selalu terdefinisi dan membaik mulus saat dip resonansi bergerak ke dalam pita, jadi
#   GPR punya gradien untuk dipelajari (BW langsung = 0 untuk sebagian besar sampel, sehingga datar).
#   d_peak_fr_dbi = directivity di monitor terdekat frekuensi resonansi (penjaga pola radiasi).
#   Gain (gain_fr_ieee_dbi) sengaja tidak dipakai sebagai constraint: >= 5 dBi untuk satu patch FR-4
#   sulit tercapai (efisiensi radiasi di fr hanya sekitar 0,3-0,4); tentukan batasnya bersama pembimbing.
# TAHAP 2: maksimalkan bandwidth dengan resonansi di dalam pita dan pencocokan terpenuhi.
STAGES = [
    {"name": "tahap1_match",
     "objective": {"column": "rl_band_min_db", "goal": "min"},
     "constraints": [
         {"column": "d_peak_fr_dbi", "op": ">=", "value": 4.0},
     ]},
    {"name": "tahap2_bandwidth",
     "objective": {"column": "bw_mhz", "goal": "max"},
     "constraints": [
         {"column": "fr_ghz",         "op": ">=", "value": BAND_GHZ[0]},   # batas pita hanya di BAND_GHZ
         {"column": "fr_ghz",         "op": "<=", "value": BAND_GHZ[1]},
         {"column": "rl_band_min_db", "op": "<=", "value": RL_LIMIT_DB},
         {"column": "d_peak_fr_dbi",  "op": ">=", "value": 4.0},
     ]},
    # Syarat pindah tahap 1 -> 2 (default = constraint tahap 2) bisa diganti per tahap dengan
    # kunci "advance_when": [ ...daftar constraint... ].
]
