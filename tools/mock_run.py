"""
Pengganti `py main.py run` tanpa CST: simulasi diganti fungsi analitik `mock_response(p, f)` dari file desain.

  py tools/mock_run.py --design _demo_analytic --samples data/DemoAnalytic/samples/lhs_samples.csv
  py tools/mock_run.py --design _demo_analytic --samples data/DemoAnalytic/samples/bo_candidates.csv --limit 5

Keluaran: data/<RUN_NAME>/batch_lhs.csv, curves/s11_sample{id}.csv, eff/eff_sample{id}.csv, dengan kolom dan rumus yang SAMA
dengan `run` karena baris dibuat oleh cstopt.cst.export.extract (hanya sumber data kurva dan farfield yang diganti).
Perilaku seperti `run`: sampel yang parameternya sudah ada dilewati (resume), CSV lama berformat beda dipindah namanya,
sampel yang melanggar aturan geometri membatalkan batch. Kolom ekstra (mis. hs, Wf) di CSV sampel ikut bila ada di EXTRA_BASE desain.

Desain harus punya  mock_response(p, f) -> dict(s11_db, eta_rad, eta_tot, d_dbi)  dengan array sepanjang f (lihat designs/_demo_analytic.py).
Hasil BUKAN data CST: jangan dicampur dengan folder data nyata (pakai RUN_NAME khusus uji).
"""
import argparse
import csv
import os
import sys
import types

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:                                              # paket `cst` hanya ada di Windows dengan CST; selain itu pakai tiruan kosong
    import cst.results  # noqa: F401
except ImportError:
    pkg = types.ModuleType("cst")
    pkg.results = types.ModuleType("cst.results")
    sys.modules["cst"], sys.modules["cst.results"] = pkg, pkg.results

from cstopt import paths                          # noqa: E402
from cstopt.cst import config as cfg              # noqa: E402
from cstopt.cst import export as ed               # noqa: E402

SWEEP = (2.5, 4.5, 0.002)                         # rentang dan langkah frekuensi kurva S11 (sama dengan data CST)


def read_samples(path, extras_allowed):
    """(daftar (sid, params), nama kolom ekstra yang dipakai)."""
    if not os.path.exists(path):
        raise SystemExit(f"File sampel tidak ditemukan: {path}\nJalankan dulu:  py main.py lhs --design <desain>")
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        extras = [k for k in extras_allowed if k in header]
        ed.set_extra_params(extras)
        miss = [k for k in ed.PARAM_NAMES if k not in header]
        if miss:
            raise SystemExit(f"Kolom parameter tidak ada di {path}: {miss}")
        has_id = "sample_id" in header
        out = []
        for n, row in enumerate(reader, 1):
            out.append((int(float(row["sample_id"])) if has_id else n, {k: float(row[k]) for k in ed.PARAM_NAMES}))
    if not out:
        raise SystemExit(f"Tidak ada sampel di {path}")
    return out, extras


def make_collector(mod):
    """Pasang pengganti sumber data CST di modul export, lalu kembalikan fungsi simulate(sid, params) -> (row, curves)."""
    f = np.round(np.arange(ed.MON_START, ed.MON_STOP + 1e-9, SWEEP[2]), 6)       # rentang = monitor desain (desain lama: 2,5 sampai 4,5)
    state = {}

    def eff_curve(res, path, run_id):
        r = state["resp_mon"]
        return state["xe"], (r["eta_rad"] if path == ed.EFF_RAD_PATH else r["eta_tot"])

    def peak_over_files(items):                   # items = [("mock", f_ghz)]: directivity di frekuensi itu
        fq = items[0][1]
        d = float(mod.mock_response(state["p"], np.array([fq]))["d_dbi"][0])
        return {"dir_peak_dbi": d, "dir_boresight_dbi": d - 0.3, "theta_peak_deg": 0.0, "theta_peak_fr_deg": 0.0}

    ed.eff_curve, ed.peak_over_files = eff_curve, peak_over_files
    ed.get_params = lambda res, run_id: dict(state["p"])

    def simulate(sid, params):
        state["p"] = params
        xe = np.array(sorted(ed.MONITORS_GHZ), float)
        state["xe"], state["resp_mon"] = xe, mod.mock_response(params, xe)
        s11_db = np.asarray(mod.mock_response(params, f)["s11_db"], float)
        fr, rl_min, bw = ed.bandwidth_around_min(f, s11_db, ed.RL_LIMIT_DB)
        f_mon = ed.nearest_monitor(fr)
        s11 = (f, s11_db, fr, rl_min, bw)
        return ed.extract(None, 0, sid, [("mock", ed.F0_GHZ)], [("mock", f_mon)], f_mon, s11=s11)

    return simulate


def main():
    ap = argparse.ArgumentParser(description="Pengganti `run` tanpa CST (fungsi analitik dari file desain)")
    ap.add_argument("--design", default=None, help="nama file di designs/ (boleh diawali garis bawah)")
    ap.add_argument("--run-name", default=None, help="folder keluaran di data/ (bawaan: RUN_NAME desain)")
    ap.add_argument("--samples", default=None, help="CSV sampel (bawaan: data/<run>/samples/lhs_samples.csv)")
    ap.add_argument("--start", type=int, default=1, help="mulai dari sample_id ini")
    ap.add_argument("--limit", type=int, default=0, help="maksimal N sampel (0 = semua)")
    a = ap.parse_args()

    mod = cfg.configure(a.design)
    if not callable(getattr(mod, "mock_response", None)):
        raise SystemExit(f"Desain '{mod.__name__}' tidak punya mock_response(p, f); lihat designs/_demo_analytic.py")
    run = a.run_name or mod.RUN_NAME
    rd = os.path.join(paths.DATA_DIR, run)
    out_csv = os.path.join(rd, "batch_lhs.csv")
    samples_csv = a.samples or os.path.join(paths.samples_dir(run), "lhs_samples.csv")

    samples, extras = read_samples(samples_csv, list(getattr(mod, "EXTRA_BASE", {})))
    samples = [s for s in samples if s[0] >= a.start]
    if a.limit:
        samples = samples[:a.limit]
    problems = [(sid, mod.geometry_problems(p)) for sid, p in samples if callable(getattr(mod, "geometry_problems", None))]
    problems = [(sid, b) for sid, b in problems if b]
    if problems:
        for sid, b in problems[:10]:
            print(f"  [geometri tidak valid] sampel {sid}: {'; '.join(b)}")
        print(f"{len(problems)} sampel melanggar aturan geometri; batch dibatalkan (sama seperti `run`).")
        return 1

    ed.prepare_dataset_file(out_csv)
    _, seen = ed.read_existing(out_csv)
    todo = [(sid, p) for sid, p in samples if ed.param_key(p) not in seen]
    print(f"[MOCK] {mod.__name__} -> {out_csv}\nSudah selesai sebelumnya: {len(samples) - len(todo)} | akan dijalankan: {len(todo)}")
    if not todo:
        return 0
    os.makedirs(rd, exist_ok=True)
    simulate = make_collector(mod)
    new_file = not os.path.exists(out_csv)
    with open(out_csv, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=ed.FIELDS)
        if new_file:
            w.writeheader()
        for sid, p in todo:
            row, curves = simulate(sid, p)
            w.writerow({k: row.get(k, "") for k in ed.FIELDS})
            fh.flush()
            ed.save_curves(rd, sid, curves)
            print(f"  sampel {sid}: fr={row['fr_ghz']} GHz | RL={row['rl_min_db']} dB | BW={row['bw_mhz']} MHz | gain={row['gain_fr_ieee_dbi']} dBi")
    print(f"Selesai: {len(todo)} sampel (data simulasi buatan, bukan CST).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
