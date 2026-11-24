"""
Konfigurasi desain eshape_fr4 (substrat FR-4 (lossy)), dibuat oleh tools/new_design.py dari _template.py.
Satu-satunya file yang spesifik untuk desain ini; panduan lengkap: designs/_template.py dan docs/membuat_desain_baru.md.
"""
import os

from cstopt import paths

NAME = "eshape_fr4"

# ---------------------------------------------------------------- data
# Nama project CST = nama folder data:  data/<RUN_NAME>/
RUN_NAME = "MicrostripAntena_EShape"
RUN_DIR = paths.run_dir(RUN_NAME)
DATASET_CSV = os.path.join(RUN_DIR, "batch_lhs.csv")                           # keluaran `main.py run`
CANDIDATES_CSV = os.path.join(paths.samples_dir(RUN_NAME), "bo_candidates.csv")  # masukan `main.py run --samples`
CURVES_DIR = os.path.join(RUN_DIR, "curves")                                   # s11_sample{sid}.csv
MODELS_DIR = paths.models_dir(RUN_NAME)                                        # gpr_models.joblib, gpr_metrics.csv
FIGURES_DIR = paths.figures_dir(RUN_NAME)                                      # gambar PNG
CURVE_FILE = "s11_sample{sid}.csv"
ID_COLUMN = "sample_id"
N_INITIAL = 60          # jumlah sampel awal (LHS); sampel dengan id lebih besar dianggap hasil BO. Samakan dengan jumlah LHS yang dibangkitkan (16 cukup untuk versi cepat)

# ---------------------------------------------------------------- parameter, rentang, aturan geometri
# Antena demonstrasi: patch persegi panjang FR-4 dengan dua slot sejajar yang terbuka di tepi y = Lp (patch berbentuk E),
# umpan inset di tepi y = 0. Geometri BERBEDA dari U-Slot + DGS, dipakai untuk mendemonstrasikan bahwa alat bisa dipakai pada antena lain
# hanya dengan file desain ini dan macro macros/eshape_fr4.bas.
#   Lp, Wp   : panjang (arah y) dan lebar (arah x) patch
#   Lsl, Wsl : panjang (arah y) dan lebar (arah x) tiap slot; slot memanjang dari y = Lp - Lsl sampai tepi y = Lp
#   Dsl      : jarak pusat tiap slot dari sumbu x = 0 (dua slot simetris di x = -Dsl dan x = +Dsl)
#   LI       : kedalaman inset umpan (celah gI = 1 mm tetap, Wf = 3,11 mm tetap untuk 50 ohm di FR-4 1,6 mm)
# Nama parameter memakai Lsl, Wsl, Dsl (bukan Ls, Ws, Ds) supaya tidak bentrok dengan parameter turunan Wsub di macro.
PARAM_NAMES = ["Lp", "Wp", "Lsl", "Wsl", "Dsl", "LI"]

# Rentang (min, max) dalam mm. SENGAJA LEBAR (pelajaran dari RO4350B: rentang awal yang sempit membuat BO menempel batas selama puluhan sampel).
# Nilai awal hanya perkiraan dari rumus patch standar pada 2,45 GHz, BUKAN hasil simulasi.
BOUNDS = {
    "Lp": (22.0, 32.0),    # baseline 27.0
    "Wp": (30.0, 44.0),    # baseline 38.0
    "Lsl": (6.0, 18.0),    # baseline 12.0
    "Wsl": (1.0, 4.0),     # baseline 2.0
    "Dsl": (5.0, 15.0),    # baseline 9.0
    "LI": (4.0, 10.0),     # baseline 7.0
}
DECIMALS = 3              # pembulatan nilai parameter (mm)
MARGIN = 0.5              # margin dasar slot terhadap ujung inset (mm)
CENTER_PRONG = 3.0        # setengah lebar minimum lengan tengah (mm); harus > Wf/2 + gI = 2,555 agar slot tidak menabrak celah inset
EDGE_PRONG = 2.0          # lebar minimum lengan luar (mm)


# ---------------------------------------------------------------- geometri
# [GANTI] aturan geometri; kembalikan daftar masalah (kosong = valid). Dipakai LHS, BO, dan `run --check-samples`.
def geometry_problems(p):
    """Daftar masalah geometri (kosong = valid). Aturan yang sama dengan CheckGeometry di macros/eshape_fr4.bas."""
    bad = []
    if p["Lp"] - p["Lsl"] <= p["LI"] + MARGIN:
        bad.append("dasar slot terlalu dekat ujung inset")
    if p["Dsl"] - p["Wsl"] / 2 < CENTER_PRONG:
        bad.append("lengan tengah terlalu sempit")
    if p["Dsl"] + p["Wsl"] / 2 > p["Wp"] / 2 - EDGE_PRONG:
        bad.append("slot terlalu dekat tepi samping patch")
    return bad


def is_valid(params):
    """Aturan geometri desain (sama dengan check_geometry di cstopt/cst/batch.py)."""
    return not geometry_problems(params)


# ---------------------------------------------------------------- target pemodelan
BAND_GHZ = (2.4, 2.6)    # SATU-SATUNYA tempat mengubah pita: dipakai fitur kurva S11 dan constraint fr tahap 2
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
# TAHAP 1: rl_band_min_db = S11 TERBAIK di dalam pita 2,4-2,6 GHz (makin negatif makin baik).
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


# ---------------------------------------------------------------- informasi substrat (dipakai make_seeds.py)
# [GANTI] diisi dari argumen --er --tand --h --material di tools/new_design.py
SUBSTRATE = {"material": "FR-4 (lossy)", "er": 4.3, "tand": 0.025, "h": 1.6}

# ---------------------------------------------------------------- model turunan (opsional)
# gain = D + 10 log10(eta), dimodelkan dari D dan eta terpisah. Aktifkan dengan USE_COMPOSITES = True atau --composite.
COMPOSITES = {"gain_fr_ieee_dbi": [("d_peak_fr_dbi", 1.0, "none"), ("eta_rad_fr", 10.0, "log10")]}
USE_COMPOSITES = False

# ---------------------------------------------------------------- fokus manual (opsional)
# Dipilih dengan  py main.py suggest --focus NAMA  (menggantikan pergantian tahap otomatis). Batas constraint dapat
# diganti lewat  --constraint "bw_mhz>=100". Semua fokus berbagi dataset dan model yang sama.
_IN_BAND = [{"column": "fr_ghz", "op": ">=", "value": BAND_GHZ[0]},
            {"column": "fr_ghz", "op": "<=", "value": BAND_GHZ[1]},
            {"column": "rl_band_min_db", "op": "<=", "value": RL_LIMIT_DB},
            {"column": "d_peak_fr_dbi", "op": ">=", "value": 4.0}]
FOCI = {
    "bw": {"objective": {"column": "bw_mhz", "goal": "max"}, "constraints": _IN_BAND},
    "cover": {"objective": {"column": "band_cover_pct", "goal": "max"}, "constraints": _IN_BAND},
    "match": {"objective": {"column": "rl_band_min_db", "goal": "min"},
              "constraints": [c for c in _IN_BAND if c["column"] in ("fr_ghz", "d_peak_fr_dbi")]},
    "gain": {"objective": {"column": "gain_fr_ieee_dbi", "goal": "max"},
             "constraints": _IN_BAND + [{"column": "bw_mhz", "op": ">=", "value": 100.0}]},
}


# ---------------------------------------------------------------- konfigurasi sisi CST (dibaca cstopt/cst/config.py)
# Nilai identik dengan konstanta lama di cstopt/cst/batch.py dan export.py. MON_* harus sama dengan FF_F_* di macro CST.
# [GANTI] nilai parameter di project CST (baseline) = nilai awal di macros/eshape_fr4.bas; batch.py mengembalikan model ke nilai ini.
BASE_PARAMS = dict(Lp=27.0, Wp=38.0, Lsl=12.0, Wsl=2.0, Dsl=9.0, LI=7.0)
# Parameter ekstra (bukan geometri BO): tebal substrat dan lebar saluran 50 ohm (FR-4 1,6 mm: 3,11 mm, nilai macro).
EXTRA_BASE = {"hs": 1.6, "Wf": 3.11}
# Pita demonstrasi 2,4 sampai 2,6 GHz (tidak harus standar). Monitor farfield 1,5 sampai 3,5 GHz langkah 0,25 (9 titik, termasuk f0 = 2,5);
# harus sama dengan FF_F_START, FF_F_STOP, FF_F_STEP, FF_F_MAIN di macro. bw_min_mhz dan gain_min_dbi hanya target SEKUNDER untuk `report` (perkiraan; kriteria utama desain bagus adalah RL, atas saran dosen).
# Gain 3 dBi dipilih konservatif untuk satu patch FR-4 berloss (tan delta 0,025); ubah bersama pembimbing bila perlu.
CST = {"band_ghz": (2.4, 2.6), "rl_limit_db": -10.0, "f0_ghz": 2.5, "monitors_ghz": (1.5, 3.5, 0.25),
       "bw_min_mhz": 100.0, "gain_min_dbi": 3.0}


# monitors_ghz = (awal, akhir, langkah) frekuensi monitor farfield; harus sama dengan FF_F_* di macro CST.
# bw_min_mhz dan gain_min_dbi = ambang target proposal untuk laporan (`report`), bukan constraint BO.


# ---------------------------------------------------------------- fitur turunan dari kurva (opsional)
def features(df, d):
    """Hook opsional: tambahkan kolom turunan ke df dan kembalikan df (jumlah baris sama, urutan sama).

    Dipanggil oleh cstopt.ml.core.load_dataset. Bawaan di sini = fitur kurva S11 yang dipakai FR-4
    (rl_band_min/max/mean_db, n_dips, dip_dist_ghz, dip_nearest_db). Ganti untuk antena yang butuh fitur lain,
    dan daftarkan nama kolom barunya di TARGETS agar dimodelkan GPR. Hapus fungsi ini bila tidak perlu
    fitur turunan sama sekali (kolom di dataset dipakai apa adanya).
    """
    from cstopt.ml.core import add_s11_features
    return add_s11_features(df, d)


# ---------------------------------------------------------------- parameter diskret dan turunan (opsional; P2-5, belum dipakai BO)
# DISCRETE = {"hs": [1.6, 2.0, 2.4]}                          # nilai laminat yang tersedia
# DERIVED = {"Wf": lambda p: wf50(4.3, p["hs"])}              # kolom turunan dari parameter lain


# ---------------------------------------------------------------- respons buatan untuk uji tanpa CST (tools/mock_run.py)
# BUKAN fisika antena; hanya fungsi mulus dengan satu resonansi supaya alur lhs, run, qc, train, suggest, report bisa diuji tanpa CST.
def mock_response(p, f):
    import numpy as np
    f = np.asarray(f, float)
    er, h = SUBSTRATE["er"], SUBSTRATE["h"]
    W = p["Wp"]
    eeff = (er + 1) / 2 + (er - 1) / 2 / np.sqrt(1 + 12 * h / W)
    leff = p["Lp"] + 0.35 * p["Lsl"]                               # slot memperpanjang jalur arus
    fr = 300.0 / (2 * leff * np.sqrt(eeff))                         # GHz (c = 300 mm/ns)
    q0 = 30.0 / (1 + 0.15 * (p["Wsl"] - 1.0)) * (36.0 / W)           # slot lebar dan patch lebar memperlebar pita
    beta = np.exp(0.5 * (p["LI"] - 7.0))                             # kopling: beta = 1 cocok sempurna
    delta = f / fr - fr / f
    gam = (beta - 1 + 1j * q0 * delta) / (beta + 1 + 1j * q0 * delta)
    s11 = 20 * np.log10(np.maximum(np.abs(gam), 1e-4))
    eta_rad = np.clip(0.72 - 0.004 * (W - 38.0) - 0.12 * np.abs(f - fr) / 0.5, 0.05, 0.95)
    eta_tot = eta_rad * (1 - np.abs(gam) ** 2)
    d_dbi = 6.6 + 0.04 * (W - 38.0) + 0.3 * (f - 2.5)
    return {"s11_db": s11, "eta_rad": eta_rad, "eta_tot": eta_tot, "d_dbi": d_dbi}
