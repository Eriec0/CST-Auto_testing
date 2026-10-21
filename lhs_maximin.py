"""
Latin Hypercube Sampling (Maximin) untuk 11 parameter antena U-Slot + DGS Dumbbell.

Keluaran: export/lhs_samples.csv  (sample_id + 11 parameter), siap dipakai batch runner.

Alur:
  1. Bangkitkan LHS di ruang satuan [0,1]^11, lalu optimasi MAXIMIN
     (memaksimalkan jarak minimum antar titik) dengan swap dalam kolom.
     Kriteria yang dioptimasi adalah phi_p (Morris & Mitchell, 1995), pendekatan halus
     dari maximin; jarak minimum aslinya tetap dilaporkan.
  2. Petakan ke rentang parameter (mm), bulatkan, lalu saring dengan aturan geometri
     yang sama seperti check_geometry() di batch_trials.py dan CheckGeometry() di macro.
  3. Dari titik yang lolos, pilih N titik dengan seleksi maximin (greedy + swap).

Catatan jujur soal langkah 2-3: setelah penyaringan, sifat Latin "tepat satu sampel
per stratum" tidak lagi dijamin sempurna, tetapi cakupan ruang tetap merata karena
dipilih dengan kriteria maximin. Jika ingin LHS murni, pakai --no-filter (risiko:
sebagian sampel geometris tidak valid dan harus dilewati).

Pemakaian:
  py lhs_maximin.py                  80 sampel (default)
  py lhs_maximin.py -n 60 --seed 7
  py lhs_maximin.py --report         tampilkan perbandingan dengan LHS biasa dan random
  py lhs_maximin.py --no-filter      LHS murni tanpa penyaringan geometri
"""
import argparse
import csv
import os

import numpy as np

# ====================== KONFIGURASI ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "export")
OUT_CSV = os.path.join(OUT_DIR, "lhs_samples.csv")

PARAM_NAMES = ["Lp", "Wp", "LU", "WU", "gU", "PU", "LI", "LD", "WD", "gD", "PD"]

# Rentang (min, max) dalam mm. Titik acuan baseline ada di komentar.
# Lp digeser ke atas karena resonansi baseline (3,99 GHz) berada di atas 3,5 GHz
# (percobaan Anda sebelumnya bergerak ke Lp ~ 20,8). SESUAIKAN bila perlu.
BOUNDS = {
    "Lp": (20.0, 23.0),   # baseline 20.22
    "Wp": (24.0, 29.0),   # baseline 26.33
    "LU": (6.0, 10.5),    # baseline 10.0
    "WU": (7.0, 13.0),    # baseline 10.5
    "gU": (0.4, 1.2),     # baseline 0.6
    "PU": (-1.0, 3.5),    # baseline 2.0
    "LI": (4.5, 7.0),     # baseline 6.15
    "LD": (2.0, 5.0),     # baseline 3.0
    "WD": (2.0, 5.0),     # baseline 3.0
    "gD": (0.2, 1.0),     # baseline 0.3
    "PD": (-3.0, 3.0),    # baseline 0.0
}
DECIMALS = 3              # pembulatan nilai parameter (mm)
AD = 2.5                  # panjang penghubung dumbbell (tetap, sama dengan macro)
MARGIN = 0.5              # margin dari check_geometry
# =========================================================


# ---------------------------------------------------------------- geometri
def geometry_problems(p):
    """Aturan yang sama dengan check_geometry() di batch_trials.py, ditambah beberapa
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


def to_params(unit_row):
    lo = np.array([BOUNDS[k][0] for k in PARAM_NAMES])
    hi = np.array([BOUNDS[k][1] for k in PARAM_NAMES])
    vals = np.round(lo + unit_row * (hi - lo), DECIMALS)
    return dict(zip(PARAM_NAMES, map(float, vals)))


# ---------------------------------------------------------------- LHS dasar
def plain_lhs(n, d, rng):
    """LHS klasik: satu titik acak per stratum, dipermutasi per kolom."""
    cut = (np.arange(n)[:, None] + rng.random((n, d))) / n
    for j in range(d):
        cut[:, j] = cut[rng.permutation(n), j]
    return cut


def min_dist(x):
    diff = x[:, None, :] - x[None, :, :]
    dm = np.sqrt((diff ** 2).sum(-1))
    dm[np.diag_indices(len(x))] = np.inf
    return float(dm.min())


def phi_p(x, p=50):
    """Kriteria Morris-Mitchell. Makin kecil makin baik (mendekati maximin saat p besar)."""
    diff = x[:, None, :] - x[None, :, :]
    dm = np.sqrt((diff ** 2).sum(-1))
    iu = np.triu_indices(len(x), 1)
    dist = np.maximum(dm[iu], 1e-12)
    dmin = dist.min()
    return float(dmin * (np.sum((dmin / dist) ** p)) ** (1.0 / p))


def maximin_lhs(n, d, rng, n_start=20, n_iter=4000, p=50):
    """LHS dengan optimasi maximin: swap dua nilai dalam satu kolom (tetap Latin),
    diterima bila phi_p turun. Beberapa titik awal acak, ambil yang terbaik."""
    best, best_phi = None, np.inf
    for _ in range(n_start):
        x = plain_lhs(n, d, rng)
        cur = phi_p(x, p)
        for _ in range(n_iter):
            j = rng.integers(d)
            a, b = rng.choice(n, 2, replace=False)
            x[[a, b], j] = x[[b, a], j]
            new = phi_p(x, p)
            if new < cur:
                cur = new
            else:
                x[[a, b], j] = x[[b, a], j]       # batalkan swap
        if cur < best_phi:
            best, best_phi = x.copy(), cur
    return best


# ---------------------------------------------------------------- seleksi maximin
def greedy_maximin_subset(x, n, rng, n_swap=3000):
    """Pilih n titik dari kandidat x agar jarak minimumnya sebesar mungkin."""
    m = len(x)
    diff = x[:, None, :] - x[None, :, :]
    dm = np.sqrt((diff ** 2).sum(-1))
    # titik awal: yang paling jauh dari pusat
    chosen = [int(np.argmax(np.linalg.norm(x - x.mean(0), axis=1)))]
    dmin = dm[chosen[0]].copy()
    while len(chosen) < n:
        dmin[chosen] = -1
        nxt = int(np.argmax(dmin))
        chosen.append(nxt)
        dmin = np.minimum(dmin, dm[nxt])
    # perbaikan dengan swap: tukar satu titik terpilih dengan satu kandidat tak terpilih
    chosen = np.array(chosen)
    cur = dm[np.ix_(chosen, chosen)] + np.diag([np.inf] * n)
    cur_min = cur.min()
    rest = np.setdiff1d(np.arange(m), chosen)
    for _ in range(n_swap):
        if len(rest) == 0:
            break
        i = rng.integers(n)
        k = rng.integers(len(rest))
        cand = chosen.copy()
        cand[i] = rest[k]
        sub = dm[np.ix_(cand, cand)] + np.diag([np.inf] * n)
        if sub.min() > cur_min:
            rest[k], chosen[i] = chosen[i], rest[k]
            cur_min = sub.min()
    return x[chosen]


# ---------------------------------------------------------------- utama
def generate(n, seed=0, oversample=3.0, filter_geometry=True, n_start=20, n_iter=4000):
    rng = np.random.default_rng(seed)
    d = len(PARAM_NAMES)

    if not filter_geometry:
        x = maximin_lhs(n, d, rng, n_start, n_iter)
        return x, [to_params(r) for r in x], 1.0

    m = int(np.ceil(n * oversample))
    for _ in range(6):                               # naikkan kandidat bila yang valid kurang
        cand = maximin_lhs(m, d, rng, max(5, n_start // 4), max(1500, n_iter // 2))
        params = [to_params(r) for r in cand]
        ok = np.array([not geometry_problems(p) for p in params])
        if ok.sum() >= n:
            break
        m = int(m * 1.6)
    else:
        raise RuntimeError(
            f"Hanya {int(ok.sum())} titik valid dari {m} kandidat. Rentang BOUNDS terlalu "
            "sempit/bertabrakan dengan aturan geometri. Longgarkan atau ubah rentang.")

    x_ok = cand[ok]
    x_sel = greedy_maximin_subset(x_ok, n, rng)
    return x_sel, [to_params(r) for r in x_sel], float(ok.mean())


def save_csv(params_list, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["sample_id"] + PARAM_NAMES)
        w.writeheader()
        for i, p in enumerate(params_list, 1):
            w.writerow({"sample_id": i, **p})


def load_samples(path=OUT_CSV):
    """Dipakai batch runner: kembalikan list dict parameter (float)."""
    with open(path, newline="", encoding="utf-8") as fh:
        return [{k: float(r[k]) for k in PARAM_NAMES} for r in csv.DictReader(fh)]


def report(n, d, seed):
    rng = np.random.default_rng(seed + 1)
    rand = np.mean([min_dist(rng.random((n, d))) for _ in range(30)])
    lhs = np.mean([min_dist(plain_lhs(n, d, rng)) for _ in range(30)])
    print(f"Rata-rata jarak minimum (ruang satuan, n={n}, d={d}):")
    print(f"  random biasa : {rand:.4f}")
    print(f"  LHS biasa    : {lhs:.4f}")


def main():
    ap = argparse.ArgumentParser(description="LHS maximin untuk 11 parameter antena")
    ap.add_argument("-n", "--n-samples", type=int, default=80, help="jumlah sampel (50-80)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--oversample", type=float, default=3.0,
                    help="faktor kandidat sebelum disaring geometri")
    ap.add_argument("--no-filter", action="store_true", help="LHS murni, tanpa saring geometri")
    ap.add_argument("--out", default=OUT_CSV)
    ap.add_argument("--report", action="store_true", help="bandingkan dengan LHS biasa/random")
    args = ap.parse_args()

    x, params, feas = generate(args.n_samples, args.seed, args.oversample, not args.no_filter)
    save_csv(params, args.out)

    print(f"{len(params)} sampel disimpan: {args.out}")
    print(f"Jarak minimum maximin (ruang satuan): {min_dist(x):.4f}")
    if not args.no_filter:
        print(f"Fraksi kandidat yang lolos aturan geometri: {feas * 100:.0f}%")
    bad = [i for i, p in enumerate(params, 1) if geometry_problems(p)]
    print("Pemeriksaan akhir geometri:", "semua valid" if not bad else f"bermasalah: {bad}")
    if args.report:
        report(len(params), len(PARAM_NAMES), args.seed)


if __name__ == "__main__":
    main()
