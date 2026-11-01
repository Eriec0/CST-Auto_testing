"""Ringkasan kondisi proyek: jumlah sampel, tahap BO aktif, sampel terbaik, peringatan batas, berkas hasil.

Dipakai oleh  `py main.py status`  dan oleh GUI (lewat `status --json`).
"""
import argparse
import glob
import json
import os
import time

from cstopt import paths
from cstopt.loader import load_design_module

EXTRA_COLS = ["fr_ghz", "rl_min_db", "bw_mhz", "gain_fr_ieee_dbi", "eta_rad_fr", "d_peak_fr_dbi"]


def _stamp(path):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))


def _file_info(path):
    return {"path": path, "exists": os.path.exists(path), "time": _stamp(path) if os.path.exists(path) else None}


def summary(design=None):
    """Kembalikan dict ringkasan. Tidak melempar error bila data belum ada (isi 'error' / 'note')."""
    mod = load_design_module(design)
    run = mod.RUN_NAME
    s = {"design": design or paths.DEFAULT_DESIGN, "design_name": getattr(mod, "NAME", run), "run": run,
         "run_dir": paths.run_dir(run), "available_designs": paths.list_designs()}
    cand = getattr(mod, "CANDIDATES_CSV", os.path.join(paths.samples_dir(run), "bo_candidates.csv"))
    s["files"] = {
        "dataset": _file_info(mod.DATASET_CSV),
        "lhs_samples": _file_info(os.path.join(paths.samples_dir(run), "lhs_samples.csv")),
        "bo_candidates": _file_info(cand),
        "models": _file_info(os.path.join(paths.models_dir(run), "gpr_models.joblib")),
        "metrics": _file_info(os.path.join(paths.models_dir(run), "gpr_metrics.csv")),
    }
    s["figures"] = sorted(glob.glob(os.path.join(paths.figures_dir(run), "*.png")))
    if not os.path.exists(mod.DATASET_CSV):
        s["note"] = "Dataset belum ada. Mulai dari: lhs, lalu run (simulasi CST)."
        return s
    try:
        from cstopt.ml import core as mc
        d = mc.load_design(design)
        df = mc.load_dataset(d)
    except Exception as e:                                   # data ada tetapi tidak bisa dimuat
        s["error"] = f"{type(e).__name__}: {e}"
        return s
    n0 = int(getattr(mod, "N_INITIAL", 0))
    ids = df[d.id_col]
    s["n_samples"] = int(len(df))
    s["id_range"] = [int(ids.min()), int(ids.max())]
    s["n_initial"] = int((ids <= n0).sum())
    s["n_bo"] = int((ids > n0).sum())
    s["stage"] = {"index": d.stage_idx + 1, "total": len(d.stages), "name": d.stage_name}
    oc = d.objective["column"]
    s["objective"] = {"column": oc, "goal": d.objective["goal"]}
    ok = mc.feasible_mask(d, df)
    s["n_feasible"] = int(ok.sum())
    pool = df[ok] if ok.any() else df
    pool = pool.dropna(subset=[oc]).sort_values(oc, ascending=(d.objective["goal"] == "min"))
    if len(pool):
        r = pool.iloc[0]
        best = {"sample_id": int(r[d.id_col]), "value": float(r[oc]), "feasible": bool(ok.any())}
        best.update({c: float(r[c]) for c in EXTRA_COLS if c in df.columns})
        s["best"] = best
    s["bound_hits"] = [{"param": p, "side": side, "n": a, "of": n, "bound": v}
                       for p, side, a, n, v in mc.bound_hits(d, df)]
    if os.path.exists(cand):
        import pandas as pd
        s["n_candidates"] = int(len(pd.read_csv(cand)))
    return s


def format_summary(s):
    L = [f"Desain   : {s['design']} ({s['design_name']})", f"Run      : {s['run']}  ->  {s['run_dir']}"]
    if "note" in s:
        L.append(s["note"])
    if "error" in s:
        L.append(f"[error] dataset ada tetapi gagal dimuat: {s['error']}")
    if "n_samples" in s:
        L.append(f"Sampel   : {s['n_samples']} (id {s['id_range'][0]}-{s['id_range'][1]}; awal {s['n_initial']}, BO {s['n_bo']})")
        st = s["stage"]
        L.append(f"Tahap BO : {st['index']}/{st['total']} ({st['name']}), objective {s['objective']['goal']} {s['objective']['column']}")
        L.append(f"Feasible : {s['n_feasible']}/{s['n_samples']} sampel memenuhi constraint tahap ini")
        if "best" in s:
            b = s["best"]
            tag = "terbaik feasible" if b["feasible"] else "terbaik (belum ada yang feasible)"
            extra = ", ".join(f"{k}={b[k]:.3g}" for k in EXTRA_COLS if k in b and k != s["objective"]["column"])
            L.append(f"Terbaik  : {tag}: sampel {b['sample_id']}, {s['objective']['column']}={b['value']:.4g}  [{extra}]")
        for h in s.get("bound_hits", []):
            L.append(f"[peringatan] {h['param']} menempel batas {h['side']} ({h['bound']:g}) pada {h['n']}/{h['of']} desain terbaik")
    f = s["files"]
    for key, label in [("lhs_samples", "lhs_samples.csv"), ("bo_candidates", "bo_candidates.csv"),
                       ("models", "model GPR"), ("metrics", "gpr_metrics.csv")]:
        L.append(f"{label:<17}: " + (f"ada ({f[key]['time']})" if f[key]["exists"] else "belum ada"))
    if "n_candidates" in s:
        L.append(f"Kandidat BO      : {s['n_candidates']} baris di bo_candidates.csv")
    L.append(f"Gambar           : {len(s['figures'])} berkas PNG")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Ringkasan kondisi proyek")
    ap.add_argument("--design", default=None, help="nama file di designs/ (default: desain bawaan)")
    ap.add_argument("--json", action="store_true", help="keluaran JSON (dipakai GUI)")
    args = ap.parse_args()
    s = summary(args.design)
    print(json.dumps(s, ensure_ascii=False) if args.json else format_summary(s))
