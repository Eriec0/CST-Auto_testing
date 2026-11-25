"""Uji P2-1 (--sweep) dan P2-2 (--diversity) tanpa CST, pada data yang ada di repo.

  py tools\\test_p2.py                 (sweep, RO4350B, seed 0 1 2; sekitar 1 menit)
  py tools\\test_p2.py --mode diversity   (jarak antar kandidat tanpa dan dengan --diversity R, FR-4 dan RO4350B)
Mencetak, per seed: gain prediksi tiap kandidat terhadap batas sapuan, korelasi peringkat Spearman, dan
jumlah kandidat dengan gain prediksi >= batas. Pembanding: rentang gain prediksi tanpa sweep.
Juga memeriksa bahwa constraint desain dipulihkan setelah suggest(sweep=...).
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from scipy.stats import spearmanr  # noqa: E402

from cstopt.ml import core as mc  # noqa: E402


def run(design, seed, sweep, q, restarts, pool, col):
    d = mc.load_design(design)
    d.set_focus("bw", mc.parse_constraints(f"{col}>=5.0"))
    d.margins = mc.parse_margins("fr_ghz=0.08")
    df = mc.load_dataset(d)
    d.region = mc.region_auto(d, df, 6, 0.15)
    before = [dict(c) for c in d.constraints]
    _, rep = mc.suggest(d, df, q=q, seed=seed, pool=pool, n_restarts=restarts, sweep=sweep)
    assert d.constraints == before, "constraint tidak dipulihkan"
    return rep[f"pred_{col}"].values


def diversity_test(a):
    from scipy.spatial.distance import pdist
    cases = [("uslot_dgs_fr4", None), ("uslot_dgs_ro4350b", "bw")]
    for design, focus in cases:
        d = mc.load_design(design)
        if focus:
            d.set_focus(focus, mc.parse_constraints("gain_fr_ieee_dbi>=5.0"))
            d.margins = mc.parse_margins("fr_ghz=0.08")
        df = mc.load_dataset(d)
        if focus:
            d.region = mc.region_auto(d, df, 6, 0.15)
        print(f"\n{design} (focus {focus}): jarak antar kandidat (ruang satuan), mean pof, mean pred {d.objective['column']}")
        for sd in (int(x) for x in a.seeds.split(",")):
            for R in [None] + [float(x) for x in a.rs.split(",")]:
                cand, rep = mc.suggest(d, df, q=a.q, seed=sd, pool=a.pool, n_restarts=a.restarts, diversity=R)
                U = d.to_unit(cand[d.params].values)
                dd = pdist(U)
                print(f"seed {sd} R={'-' if R is None else R:>5}: min {dd.min():.3f} median {np.median(dd):.3f} | "
                      f"pof {rep['pof'].mean():.3f} | pred {rep['pred_' + d.objective['column']].mean():.2f}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="sweep", choices=["sweep", "diversity"])
    ap.add_argument("--rs", default="0.4", help="nilai R untuk mode diversity, mis. 0.15,0.4,0.6")
    ap.add_argument("--design", default="uslot_dgs_ro4350b")
    ap.add_argument("--col", default="gain_fr_ieee_dbi")
    ap.add_argument("--range", default="4.0:5.4")
    ap.add_argument("--seeds", default="0", help="mis. 0,1,2 untuk uji penuh (lama)")
    ap.add_argument("--no-baseline", action="store_true", help="mode sweep: lewati panggilan pembanding tanpa sweep (separuh waktu)")
    ap.add_argument("-q", type=int, default=5)
    ap.add_argument("--restarts", type=int, default=1, help="uji penuh: 2")
    ap.add_argument("--pool", type=int, default=4096, help="uji penuh: 8192")
    a = ap.parse_args()
    if a.mode == "diversity":
        return diversity_test(a)
    lo, hi = (float(v) for v in a.range.split(":"))
    n_seed = len(a.seeds.split(","))
    print(f"Mode sweep: {(1 if a.no_baseline else 2) * n_seed} panggilan suggest (restarts {a.restarts}, pool {a.pool}); tiap panggilan 20 detik sampai "
          f"beberapa menit tergantung komputer. Ctrl+C aman (cukup sekali, tunggu sebentar).", flush=True)
    bounds = [round(float(b), 6) for b in np.linspace(lo, hi, a.q)]
    print(f"batas sapuan: {bounds}")
    for sd in (int(x) for x in a.seeds.split(",")):
        t0 = time.time()
        if not a.no_baseline:
            print(f"seed {sd}: panggilan 1/2 (tanpa sweep) ...", flush=True)
        g0 = None if a.no_baseline else run(a.design, sd, None, a.q, a.restarts, a.pool, a.col)
        print(f"seed {sd}: panggilan {1 if a.no_baseline else '2/2'}{'/1' if a.no_baseline else ''} (dengan sweep) ... ({time.time() - t0:.0f} dtk sejauh ini)", flush=True)
        g1 = run(a.design, sd, {"column": a.col, "bounds": bounds}, a.q, a.restarts, a.pool, a.col)
        rho = spearmanr(bounds, g1)[0]
        ok = int((g1 >= np.array(bounds)).sum())
        print(f"seed {sd}: tanpa sweep " + ("dilewati" if g0 is None else f"rentang {g0.min():.2f}..{g0.max():.2f} (lebar {np.ptp(g0):.2f})") + " | "
              f"sweep {np.round(g1, 2).tolist()} (lebar {np.ptp(g1):.2f}) | Spearman {rho:+.2f} | gain >= batas: {ok}/{a.q} | {time.time() - t0:.0f} dtk", flush=True)
    print("constraint dipulihkan: OK")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:        # Ctrl+C: keluar rapi; baris seed yang sudah tercetak di atas tetap berlaku
        print("\n[dihentikan oleh pengguna] hasil sebagian ada di atas.")
        sys.exit(130)
