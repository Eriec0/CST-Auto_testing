"""
Satu iterasi Constrained Bayesian Optimization (GPR + Expected Improvement x Probability of Feasibility).

Alur satu iterasi (simulasi CST tetap dijalankan oleh `main.py run`):

  1.  py main.py suggest -q 5                     -> data/<RUN_NAME>/samples/bo_candidates.csv  (+ laporan prediksi)
  2.  py main.py run --samples data/<RUN_NAME>/samples/bo_candidates.csv --auto-yes
  3.  ulangi dari langkah 1  (data baru otomatis ikut melatih ulang GPR)

Opsi lain:
  py main.py suggest --report                     tampilkan & gambar kurva konvergensi (tanpa kandidat baru)
  py main.py suggest -q 3 --kernel matern52 --seed 1
Format bo_candidates.csv sama dengan lhs_samples.csv, jadi tidak ada yang perlu diubah di cst/batch.py.
"""
import argparse
import json
import os
import shutil
from datetime import datetime

import matplotlib
import numpy as np
import pandas as pd

from cstopt.ml import core as mc

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
    os.makedirs(d.figures_dir, exist_ok=True)
    path = os.path.join(d.figures_dir, "bo_convergence.png")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    print(f"Gambar: {path}")


def warn_hits(hits, subjek):
    """Cetak peringatan bila parameter menempel batas rentang."""
    if not hits:
        return
    daftar = ", ".join(f"{p} ({sisi}, {n_hit}/{n}, batas {v:g})" for p, sisi, n_hit, n, v in hits)
    print(f"[peringatan] Parameter menempel batas pada {subjek}: {daftar}")
    print("             Optimum mungkin di luar rentang. Pertimbangkan memperlebar BOUNDS (sampel lama tetap valid).")


def main():
    ap = argparse.ArgumentParser(description="Usulkan kandidat berikutnya dengan Constrained BO")
    ap.add_argument("--design", default=None, help="nama file di designs/ (default: desain bawaan)")
    ap.add_argument("-q", type=int, default=5, help="jumlah kandidat per iterasi (batch)")
    ap.add_argument("--kernel", default="rbf", choices=["rbf", "matern52"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--pool", type=int, default=32768, help="jumlah kandidat acak (Sobol) yang dinilai")
    ap.add_argument("--xi", type=float, default=0.01, help="margin eksplorasi EI (fraksi std objective)")
    ap.add_argument("--restarts", type=int, default=5)
    ap.add_argument("--spread", type=float, default=0.3,
                    help="jarak minimum antar kandidat dalam satu batch (ruang satuan; 0 = tanpa batas)")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--stage", type=int, default=None,
                    help="paksa tahap BO (1, 2, ...); default: dipilih otomatis dari data")
    ap.add_argument("--focus", default=None,
                    help="fokus manual dari FOCI di file desain (mis. bw, cover, gain, match); menggantikan tahap otomatis")
    ap.add_argument("--constraint", default=None,
                    help="ganti/tambah constraint pada --focus, mis. \"bw_mhz>=100,gain_fr_ieee_dbi>=4.5\"")
    ap.add_argument("--region", default=None, help="region pencarian manual, mis. \"Lp=16:19,WD=7:8\" (lainnya rentang penuh)")
    ap.add_argument("--region-auto", default=None, metavar="K:MARGIN",
                    help="region otomatis di sekitar K desain terbaik, diperlebar MARGIN x lebar BOUNDS (mis. 8:0.15)")
    ap.add_argument("--region-adapt", action="store_true",
                    help="trust region adaptif di sekitar desain terbaik; sisi tumbuh/menyusut menurut kemajuan antar putaran "
                         "(keadaan di samples/region_state.json); menggantikan --region dan --region-auto")
    ap.add_argument("--margin", default=None,
                    help="perketat constraint untuk PoF saja, mis. \"fr_ghz=0.1\" (menahan kandidat dari tepi pita)")
    ap.add_argument("--sweep", default=None, metavar="KOLOM=LO:HI",
                    help="sapuan epsilon-constraint: q batas merata dari LO ke HI untuk constraint KOLOM, satu batas per kandidat "
                         "(mis. \"gain_fr_ieee_dbi=4.0:5.4\"); butuh --focus dan KOLOM harus constraint aktif")
    ap.add_argument("--diversity", type=float, default=None, metavar="R",
                    help="penalti lunak jarak antar kandidat: akuisisi dikali 1-exp(-(jarak/R)^2) (ruang satuan; "
                         "efek baru terasa bila R > --spread, mis. 0.4 sampai 0.5)")
    ap.add_argument("--calibrate", action="store_true", help="kalibrasi std prediksi constraint dari validasi silang")
    ap.add_argument("--composite", dest="composite", action="store_true", default=None,
                    help="pakai model komposit (mis. gain = D + 10 log10 eta); bawaan mengikuti file desain")
    ap.add_argument("--no-composite", dest="composite", action="store_false")
    args = ap.parse_args()

    d = mc.load_design(args.design)
    if args.constraint and not args.focus:
        ap.error("--constraint hanya dipakai bersama --focus")
    if args.focus:
        d.set_focus(args.focus, mc.parse_constraints(args.constraint))
    if args.stage is not None:
        d.force_stage = args.stage - 1
    if args.composite is not None:
        d.use_composites = args.composite
    sweep = None
    if args.sweep:
        if not args.focus:
            ap.error("--sweep hanya dipakai bersama --focus")
        try:
            col, rng_txt = args.sweep.split("=")
            lo, hi = (float(v) for v in rng_txt.split(":"))
        except ValueError:
            ap.error("--sweep harus berformat KOLOM=LO:HI, mis. gain_fr_ieee_dbi=4.0:5.4")
        if args.q < 2:
            ap.error("--sweep butuh -q >= 2")
        col = col.strip()
        if col not in [c["column"] for c in d.constraints]:
            ap.error(f"--sweep: '{col}' bukan constraint fokus ini ({[c['column'] for c in d.constraints]}); "
                     f"tambahkan lewat --constraint")
        sweep = {"column": col, "bounds": [round(float(b), 6) for b in np.linspace(lo, hi, args.q)]}
    if args.diversity is not None and args.diversity <= 0:
        ap.error("--diversity harus > 0")
    d.calibrate = args.calibrate
    d.margins = mc.parse_margins(args.margin)
    df = mc.load_dataset(d)
    if sum(bool(x) for x in (args.region, args.region_auto, args.region_adapt)) > 1:
        ap.error("pilih salah satu: --region, --region-auto, atau --region-adapt")
    if args.region_adapt and not args.report:
        state_path = os.path.join(os.path.dirname(d.candidates), "region_state.json")
        state = None
        if os.path.exists(state_path):
            try:
                with open(state_path, encoding="utf-8") as fh:
                    state = json.load(fh)
            except (OSError, ValueError):
                state = None
        eps = args.xi * float(np.nanstd(df[d.objective["column"]].values))
        d.region, state, info = mc.region_adapt(d, df, state, eps)
        try:
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=1)
        except OSError:
            print(f"[peringatan] keadaan region tidak bisa disimpan: {state_path}")
        print(f"[opsi] region adaptif: sisi {state['side']:.3f} x lebar BOUNDS (sukses {state['succ']}, gagal {state['fail']}; {info})")
    if args.region:
        d.region = mc.parse_region(d, args.region)
    elif args.region_auto:
        k, m = args.region_auto.split(":")
        d.region = mc.region_auto(d, df, int(k), float(m))
    if d.focus:
        print(f"Fokus BO: {d.stage_name} (manual)")
    else:
        mode = "dipaksa" if args.stage is not None else "otomatis"
        print(f"Tahap BO: {d.stage_idx + 1}/{len(d.stages)} ({d.stage_name}, {mode})")
    print(f"Desain: {d.name} | {len(df)} sampel | objective: {d.objective['goal']} "
          f"{d.objective['column']} | constraint: "
          f"{[(c['column'], c['op'], c['value']) for c in d.constraints]}")
    n_feas = int(mc.feasible_mask(d, df).sum())
    print(f"Sampel yang memenuhi semua constraint: {n_feas}/{len(df)}")
    warn_hits(mc.bound_hits(d, df), "desain terbaik")

    if args.report:
        report(d, df)
        return

    cand, rep = mc.suggest(d, df, q=args.q, kind=args.kernel, seed=args.seed, pool=args.pool,
                           xi_frac=args.xi, n_restarts=args.restarts, spread=args.spread, sweep=sweep,
                           diversity=args.diversity)
    # id kandidat BO selalu > N_INITIAL agar tidak bentrok dengan id sampel LHS yang belum dijalankan
    next_id = max(int(df[d.id_col].max()), int(d.n_initial)) + 1
    cand.insert(0, d.id_col, range(next_id, next_id + len(cand)))
    rep.insert(0, d.id_col, cand[d.id_col].values)

    if os.path.exists(d.candidates):                       # arsipkan file kandidat sebelumnya
        arc = os.path.join(os.path.dirname(d.candidates), "archive")
        os.makedirs(arc, exist_ok=True)
        shutil.move(d.candidates, os.path.join(arc, f"bo_candidates_{datetime.now():%Y%m%d_%H%M%S}.csv"))
    cand.to_csv(d.candidates, index=False)
    rep_path = d.candidates.replace(".csv", "_report.csv")
    rep.to_csv(rep_path, index=False)

    oc = d.objective["column"]
    extra = [c for c in dict.fromkeys(c["column"] for c in d.constraints) if c != oc]   # tanpa duplikat
    show = [d.id_col] + (["sweep_bound"] if sweep else []) + ["acq", "pof", f"pred_{oc}", f"std_{oc}"] \
        + [f"pred_{c}" for c in extra]
    pd.set_option("display.width", 200)
    print(f"\n{len(cand)} kandidat disimpan: {d.candidates}")
    print(rep[show].round(4).to_string(index=False))
    warn_hits(mc.edge_hits(d, cand[d.params].values), "kandidat BO ini")
    if sweep:
        print(f"\n[sweep] {sweep['column']} >= " + ", ".join(f"{b:g}" for b in sweep["bounds"])
              + " (satu batas per kandidat); aturan berhenti dilewati karena EI antar batas tidak sebanding.")
    else:
        stop_rule(d, df, rep)
    print(f"\nLaporan lengkap (prediksi mean/std semua target): {rep_path}")
    print("\nLangkah berikutnya:")
    print(f"  py main.py run --samples \"{d.candidates}\" --auto-yes")


def stop_rule(d, df, rep):
    """Aturan berhenti (hanya informasi): rasio EI maks kandidat terhadap |objective terbaik yang feasible|.
    Objective tidak ditransformasi, jadi keduanya dalam satuan asli. Bila rasio < 1% pada dua putaran berurutan
    (objective dan constraint yang sama) dicetak bahwa BO dianggap konvergen. Tidak menghentikan apa pun dan tidak mengubah kandidat."""
    f_best, _ = mc.best_feasible(d, df)
    if f_best is None or "ei" not in rep.columns or abs(f_best) < 1e-12:
        return
    ei_max = float(rep["ei"].max())
    ratio = ei_max / abs(f_best)
    sig = f"{d.stage_name}|{d.objective['goal']} {d.objective['column']}|" + ";".join(
        f"{c['column']}{c['op']}{c['value']:g}" for c in d.constraints)
    path = os.path.join(d.models_dir, "ei_history.csv")
    row = pd.DataFrame([{"waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "n_sampel": len(df), "sinyal": sig,
                         "ei_maks": ei_max, "f_terbaik": abs(f_best), "rasio": ratio}])
    try:
        os.makedirs(d.models_dir, exist_ok=True)
        hist = pd.concat([pd.read_csv(path), row], ignore_index=True) if os.path.exists(path) else row
        hist.to_csv(path, index=False)
    except OSError:
        hist = row
    same = hist[hist["sinyal"] == sig].tail(2)
    print(f"\n[info] EI maks / |objective terbaik| = {100 * ratio:.2f}% (ambang konvergen: di bawah 1% pada dua putaran berurutan)")
    if len(same) == 2 and (same["rasio"] < 0.01).all():
        print("[info] BO dianggap konvergen untuk objective dan constraint ini (hanya informasi, tidak menghentikan apa pun).")


if __name__ == "__main__":
    main()