"""
Bandingkan dua run (data/<A>/batch_lhs.csv dan data/<B>/batch_lhs.csv) untuk sampel dengan parameter geometri yang sama.
Dipakai pada F8 (uji CST nyata: simulasi ulang satu titik ke folder terpisah harus mereproduksi hasil lama) dan untuk pemeriksaan mesh.

  py tools\\compare_runs.py MicrostripAntena_RO4350B MicrostripAntena_RO4350B_uji
  py tools\\compare_runs.py A B --tol-fr-mhz 2 --tol-bw-pct 2 --tol-rl-db 1 --design uslot_dgs_ro4350b

Kecocokan sampel lewat parameter geometri yang dibulatkan 3 desimal (nilai hs dan Wf tidak ikut). Ambang bawaan (2 MHz, 2 persen, 1 dB)
adalah pilihan konvensi: mesh rapat pada data Anda memberi selisih fr paling besar 2 MHz dan BW 0,34 persen; simulasi ulang pada mesh dan
project yang sama seharusnya memberi selisih jauh lebih kecil. Kode keluar 0 bila semua sampel yang cocok di bawah ambang, 1 bila ada yang melewati,
2 bila tidak ada sampel yang cocok atau berkas tidak ada.
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cstopt import paths  # noqa: E402
from cstopt.loader import load_design_module  # noqa: E402


def design_for_run(run):
    """Nama file desain untuk sebuah run: RUN_NAME sama persis, atau awalan terpanjang yang diikuti garis bawah (mis. _fine, _tol, _uji). Tanpa modul CST."""
    best, best_len = None, -1
    for name in paths.list_designs():
        try:
            rn = getattr(load_design_module(name), "RUN_NAME", None)
        except Exception:                                # noqa: BLE001
            continue
        if rn == run:
            return name
        if rn and run.startswith(rn + "_") and len(rn) > best_len:
            best, best_len = name, len(rn)
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_a", help="run acuan (hasil lama)")
    ap.add_argument("run_b", help="run pembanding (hasil baru)")
    ap.add_argument("--design", default=None, help="file desain untuk daftar parameter (bawaan: dicocokkan dari nama run A)")
    ap.add_argument("--tol-fr-mhz", type=float, default=2.0)
    ap.add_argument("--tol-bw-pct", type=float, default=2.0)
    ap.add_argument("--tol-rl-db", type=float, default=1.0)
    a = ap.parse_args()
    pa, pb = (os.path.join(paths.run_dir(r), "batch_lhs.csv") for r in (a.run_a, a.run_b))
    for p in (pa, pb):
        if not os.path.exists(p):
            print(f"[error] tidak ada: {p}")
            return 2
    name = a.design or design_for_run(a.run_a)
    if not name:
        print("[error] desain tidak ditemukan dari nama run; berikan --design")
        return 2
    params = list(load_design_module(name).PARAM_NAMES)
    A, B = pd.read_csv(pa), pd.read_csv(pb)
    key = lambda df: df[params].round(3).astype(str).agg("|".join, axis=1)   # noqa: E731
    A["_k"], B["_k"] = key(A), key(B)
    m = A.merge(B, on="_k", suffixes=("_a", "_b"))
    if m.empty:
        print(f"Tidak ada sampel dengan parameter sama antara {a.run_a} ({len(A)} sampel) dan {a.run_b} ({len(B)} sampel).")
        return 2
    out = pd.DataFrame({"id_a": m["sample_id_a"], "id_b": m["sample_id_b"],
                        "fr_a": m["fr_ghz_a"], "fr_b": m["fr_ghz_b"], "d_fr_MHz": (m["fr_ghz_b"] - m["fr_ghz_a"]) * 1000,
                        "bw_a": m["bw_mhz_a"], "bw_b": m["bw_mhz_b"],
                        "d_bw_%": 100 * (m["bw_mhz_b"] - m["bw_mhz_a"]) / m["bw_mhz_a"].where(m["bw_mhz_a"] > 0, np.nan),
                        "rl_a": m["rl_min_db_a"], "rl_b": m["rl_min_db_b"], "d_rl_dB": m["rl_min_db_b"] - m["rl_min_db_a"]})
    if "gain_fr_ieee_dbi_a" in m:
        out["d_gain_dB"] = m["gain_fr_ieee_dbi_b"] - m["gain_fr_ieee_dbi_a"]
    pd.set_option("display.width", 200)
    print(out.round(3).to_string(index=False))
    bad = (out["d_fr_MHz"].abs() > a.tol_fr_mhz) | (out["d_bw_%"].abs() > a.tol_bw_pct) | (out["d_rl_dB"].abs() > a.tol_rl_db)
    print(f"\nSampel cocok: {len(out)} dari {len(B)} di {a.run_b}. Melewati ambang (fr {a.tol_fr_mhz:g} MHz, BW {a.tol_bw_pct:g}%, RL {a.tol_rl_db:g} dB): {int(bad.sum())}.")
    print("HASIL: " + ("COCOK" if not bad.any() else "TIDAK COCOK, periksa sampel di atas"))
    return 1 if bad.any() else 0


if __name__ == "__main__":
    sys.exit(main())
