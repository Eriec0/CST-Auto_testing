"""
Satu iterasi Constrained Bayesian Optimization (GPR + Expected Improvement x Probability of Feasibility).

Alur satu iterasi (simulasi CST tetap dijalankan oleh batch_trials.py):

  1.  py bo_suggest.py -q 5                     -> export/bo_candidates.csv  (+ laporan prediksi)
  2.  py batch_trial_LHS.py --samples export/bo_candidates.csv --auto-yes
  3.  ulangi dari langkah 1  (data baru otomatis ikut melatih ulang GPR)

Opsi lain:
  py bo_suggest.py --report                     tampilkan & gambar kurva konvergensi (tanpa kandidat baru)
  py bo_suggest.py -q 3 --kernel matern52 --seed 1
Format bo_candidates.csv sama dengan lhs_samples.csv, jadi tidak ada yang perlu diubah di batch_trials.py.
"""
import argparse
import os
import shutil
from datetime import datetime

import matplotlib
import numpy as np
import pandas as pd

import ml_core as mc

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def report(d, df):
    best = mc.convergence(d, df)
    oc = d.objective["column"]
    n0 = d.n_initial
    print(f"\nKonvergensi: terbaik yang feasible untuk '{oc}' ({d.objective['goal']}) per jumlah evaluasi")
    steps = sorted(set([10, 20, 40, 60, n0, len(df)] + list(range(n0 + 5, len(df) + 1, 5))))
    for k in steps:
        if 1 <= k <= len(df):
            v = best[k - 1]
            tag = "LHS" if k <= n0 else "BO "
            print(f"  evaluasi {k:3d} [{tag}] : {'belum ada yang feasible' if np.isnan(v) else f'{v:.4f}'}")
    fig, ax = plt.subplots(figsize=(6.4, 4))
    ax.plot(np.arange(1, len(df) + 1), best, drawstyle="steps-post")
    if 0 < n0 < len(df):
        ax.axvline(n0 + 0.5, color="gray", ls="--", lw=0.8)
        ax.text(n0 + 1, ax.get_ylim()[0], " mulai BO", va="bottom", fontsize=8)
    ax.set_xlabel("jumlah evaluasi simulasi")
    ax.set_ylabel(f"{oc} terbaik (feasible)")
    ax.set_title("Kurva konvergensi")
    fig.tight_layout()
    path = os.path.join(os.path.dirname(d.dataset), "bo_convergence.png")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    print(f"Gambar: {path}")


def main():
    ap = argparse.ArgumentParser(description="Usulkan kandidat berikutnya dengan Constrained BO")
    ap.add_argument("--design", default="design_uslot_dgs")
    ap.add_argument("-q", type=int, default=5, help="jumlah kandidat per iterasi (batch)")
    ap.add_argument("--kernel", default="rbf", choices=["rbf", "matern52"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--pool", type=int, default=32768, help="jumlah kandidat acak (Sobol) yang dinilai")
    ap.add_argument("--xi", type=float, default=0.01, help="margin eksplorasi EI (fraksi std objective)")
    ap.add_argument("--restarts", type=int, default=5)
    ap.add_argument("--spread", type=float, default=0.3,
                    help="jarak minimum antar kandidat dalam satu batch (ruang satuan; 0 = tanpa batas)")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    d = mc.load_design(args.design)
    df = mc.load_dataset(d)
    print(f"Desain: {d.name} | {len(df)} sampel | objective: {d.objective['goal']} "
          f"{d.objective['column']} | constraint: "
          f"{[(c['column'], c['op'], c['value']) for c in d.constraints]}")
    n_feas = int(mc.feasible_mask(d, df).sum())
    print(f"Sampel yang memenuhi semua constraint: {n_feas}/{len(df)}")

    if args.report:
        report(d, df)
        return

    cand, rep = mc.suggest(d, df, q=args.q, kind=args.kernel, seed=args.seed, pool=args.pool,
                           xi_frac=args.xi, n_restarts=args.restarts, spread=args.spread)
    # id kandidat BO selalu > N_INITIAL agar tidak bentrok dengan id sampel LHS yang belum dijalankan
    next_id = max(int(df[d.id_col].max()), int(d.n_initial)) + 1
    cand.insert(0, d.id_col, range(next_id, next_id + len(cand)))
    rep.insert(0, d.id_col, cand[d.id_col].values)

    if os.path.exists(d.candidates):                       # arsipkan file kandidat sebelumnya
        arc = os.path.join(os.path.dirname(d.candidates), "bo_archive")
        os.makedirs(arc, exist_ok=True)
        shutil.move(d.candidates, os.path.join(arc, f"bo_candidates_{datetime.now():%Y%m%d_%H%M%S}.csv"))
    cand.to_csv(d.candidates, index=False)
    rep_path = d.candidates.replace(".csv", "_report.csv")
    rep.to_csv(rep_path, index=False)

    oc = d.objective["column"]
    show = [d.id_col, "acq", "pof", f"pred_{oc}", f"std_{oc}"] + \
        [f"pred_{c['column']}" for c in d.constraints if c["column"] != oc]
    pd.set_option("display.width", 200)
    print(f"\n{len(cand)} kandidat disimpan: {d.candidates}")
    print(rep[show].round(4).to_string(index=False))
    print(f"\nLaporan lengkap (prediksi mean/std semua target): {rep_path}")
    print("\nLangkah berikutnya:")
    print(f"  py batch_trial_LHS.py --samples \"{d.candidates}\" --auto-yes")


if __name__ == "__main__":
    main()