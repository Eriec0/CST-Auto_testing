"""
Rencana simulasi toleransi fabrikasi untuk desain akhir (P0-2 bagian B). Tidak butuh CST.

  py tools/make_tolerance.py --run MicrostripAntena_RO4350B --sample 112 --plan oat
  py tools/make_tolerance.py --run MicrostripAntena_RO4350B --sample 112 --plan corners   (jalankan setelah OAT selesai)
  py tools/make_tolerance.py --run MicrostripAntena_RO4350B --sample 112 --plan random --n-random 12

Plan:
  oat      satu parameter digeser + dan - (6 parameter, 12 simulasi)
  corners  4 sudut: fr turun, fr naik, BW turun, gain turun. Tanda tiap parameter diambil dari hasil OAT bila sudah ada
           di data/<run>_tol/; bila belum, dipakai 4 pola tanda yang menyebar (dan dicetak sebagai peringatan)
  random   n sampel acak seragam di dalam toleransi, semua parameter sekaligus

Toleransi bawaan: Lp, Wp, LI 0,1 mm; gU, gD 0,05 mm (tidak turun di bawah --gap-min); hs 10 persen dengan Wf dihitung ulang
(tools/wf50.py, er dari SUBSTRATE desain). --keep-wf menahan Wf tetap (lebar jalur hasil etsa tidak ikut berubah).
Ubah dengan --tol "Lp=0.2,hs=5%".

Keluaran: data/<run>_tol/samples/tol_<plan>_s<ID>.csv dan berkas _meta.csv di sebelahnya. sample_id = ID*100 + k
(OAT k 1..12, corners 21..24, random 31..), jadi beberapa desain dan plan bisa berbagi satu run toleransi tanpa tabrakan id.
Nominal tidak disimulasikan ulang: analyze_tolerance.py mengambilnya dari data/<run>/batch_lhs.csv.
Jalankan simulasi:
  py main.py run --run-name <run>_tol --samples <CSV> --auto-yes
"""
import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cstopt import paths                       # noqa: E402
from cstopt.loader import load_design_module   # noqa: E402
from wf50 import wf                            # noqa: E402

DEFAULT_TOL = {"Lp": (0.1, False), "Wp": (0.1, False), "gU": (0.05, False), "gD": (0.05, False),
               "LI": (0.1, False), "hs": (0.10, True)}      # nilai, relatif?
ORDER = ["Lp", "Wp", "gU", "gD", "LI", "hs"]
GAPS = {"gU", "gD"}
K_OAT, K_CORNER, K_RANDOM = 1, 21, 31


def find_design(run, name=None):
    if name:
        return load_design_module(name)
    for d in paths.list_designs():
        try:
            m = load_design_module(d)
        except Exception:
            continue
        if getattr(m, "RUN_NAME", None) == run:
            return m
    raise SystemExit(f"Tidak ada desain dengan RUN_NAME '{run}'. Sebutkan --design.")


def parse_tol(text):
    tol = dict(DEFAULT_TOL)
    for part in [p.strip() for p in (text or "").split(",") if p.strip()]:
        k, v = part.split("=")
        k, v = k.strip(), v.strip()
        if k not in ORDER:
            raise SystemExit(f"--tol: parameter '{k}' tidak dikenal. Pilihan: {ORDER}")
        tol[k] = (float(v.rstrip("%")) / (100.0 if v.endswith("%") else 1.0), v.endswith("%"))
    return tol


def oat_signs(tol_run, base, nominal):
    """Arah pengaruh tiap parameter dari hasil OAT: {param: {metrik: +1 bila menaikkan metrik}}.
    Sisi yang tidak disimulasikan (geometri tidak valid) dibandingkan dengan nominal. None bila belum ada hasil OAT."""
    res = os.path.join(paths.run_dir(tol_run), "batch_lhs.csv")
    metas = glob.glob(os.path.join(paths.samples_dir(tol_run), "*_meta.csv"))
    if not os.path.exists(res) or not metas:
        return None
    meta = pd.concat([pd.read_csv(m) for m in metas], ignore_index=True)
    meta = meta[(meta.base_id == base) & (meta.plan == "oat")]
    r = pd.read_csv(res).merge(meta, on="sample_id")
    if r.empty:
        return None
    out = {}
    for p in ORDER:
        up, dn = r[(r.param == p) & (r.sign > 0)], r[(r.param == p) & (r.sign < 0)]
        out[p] = {}
        for m in ("fr_ghz", "bw_mhz", "gain_fr_ieee_dbi"):
            hi = float(up[m].iloc[0]) if not up.empty else float(nominal[m])
            lo = float(dn[m].iloc[0]) if not dn.empty else float(nominal[m])
            out[p][m] = np.sign(hi - lo) or 1.0
    return out


def main():
    ap = argparse.ArgumentParser(description="Rencana toleransi fabrikasi")
    ap.add_argument("--run", required=True, help="nama run dataset utama, mis. MicrostripAntena_RO4350B")
    ap.add_argument("--design", default=None, help="file desain (default: yang RUN_NAME-nya sama dengan --run)")
    ap.add_argument("--sample", type=int, nargs="+", required=True, help="satu atau lebih sample_id desain akhir")
    ap.add_argument("--plan", nargs="+", choices=["oat", "corners", "random"], default=["oat"])
    ap.add_argument("--n-random", type=int, default=12)
    ap.add_argument("--tol", default=None, help='ubah toleransi, mis. "Lp=0.2,hs=5%%"')
    ap.add_argument("--gap-min", type=float, default=0.2, help="batas bawah celah gU dan gD (mm), batas etsa PCB")
    ap.add_argument("--keep-wf", action="store_true", help="Wf tidak dihitung ulang saat hs berubah")
    ap.add_argument("--keep-invalid", action="store_true",
                    help="tetap tulis baris yang melanggar aturan geometri (bawaan: dilewati dan dicatat di meta)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None, help="CSV keluaran (default: data/<run>_tol/samples/tol_<plan>_s<ID>.csv)")
    a = ap.parse_args()

    D = find_design(a.run, a.design)
    names, dec = list(D.PARAM_NAMES), int(getattr(D, "DECIMALS", 3))
    er, h_nom = float(D.SUBSTRATE["er"]), float(D.SUBSTRATE["h"])
    tol = parse_tol(a.tol)
    tol_run = a.run + "_tol"
    src = os.path.join(paths.run_dir(a.run), "batch_lhs.csv")
    if not os.path.exists(src):
        raise SystemExit(f"Tidak ada {src}")
    main_df = pd.read_csv(src)

    rows, meta = [], []
    for base in a.sample:
        r = main_df[main_df.sample_id == base]
        if r.empty:
            raise SystemExit(f"sample_id {base} tidak ada di {src}")
        r = r.iloc[0]
        nom = {n: float(r[n]) for n in names}
        hs0 = float(r["hs"]) if "hs" in r.index and pd.notna(r["hs"]) else h_nom
        wf0 = float(r["Wf"]) if "Wf" in r.index and pd.notna(r["Wf"]) else wf(er, hs0)[0]
        print(f"Sampel {base}: hs {hs0:g} mm, Wf {wf0:.3f} mm (er {er:g})")

        def make(sv, sid, plan, label, param="", sign=0):
            """sv: {param: pengali -1..+1 dari toleransi}. Kembalikan baris CSV dan catat meta."""
            p, notes = dict(nom), []
            for k, s in sv.items():
                if k == "hs":
                    continue
                v, rel = tol[k]
                p[k] = nom[k] * (1 + s * v) if rel else nom[k] + s * v
                if k in GAPS and p[k] < a.gap_min:
                    notes.append(f"{k} dikunci ke {a.gap_min:g}")
                    p[k] = a.gap_min
            hs, wf_v = hs0, wf0
            if "hs" in sv:
                v, rel = tol["hs"]
                hs = hs0 * (1 + sv["hs"] * v) if rel else hs0 + sv["hs"] * v
                wf_v = wf0 if a.keep_wf else wf(er, hs)[0]
            row = {"sample_id": base * 100 + sid}
            row.update({n: round(p[n], dec) for n in names})
            row.update({"hs": round(hs, dec), "Wf": round(wf_v, dec)})
            bad = D.geometry_problems({n: row[n] for n in names}) if hasattr(D, "geometry_problems") else []
            skip = bool(bad) and not a.keep_invalid
            if bad:
                notes.append(("dilewati, " if skip else "") + "geometri tidak valid: " + "; ".join(bad))
                print(f"  [{'dilewati' if skip else 'peringatan'}] {row['sample_id']} {label}: {'; '.join(bad)}")
            if not skip:
                rows.append(row)
            meta.append({"sample_id": row["sample_id"], "base_id": base, "plan": plan, "label": label, "param": param,
                         "sign": sign, "dilewati": int(skip),
                         "signs": " ".join(f"{k}{'+' if s > 0 else '-'}" for k, s in sv.items()) if plan != "oat" else "",
                         "catatan": "; ".join(notes)})

        if "oat" in a.plan:
            k = K_OAT
            for pn in ORDER:
                for s in (+1, -1):
                    make({pn: s}, k, "oat", f"{pn}{'+' if s > 0 else '-'}", pn, s)
                    k += 1
        if "corners" in a.plan:
            sg = oat_signs(tol_run, base, r)
            if sg is None:
                print("  [peringatan] hasil OAT belum ada: sudut memakai pola tanda yang menyebar, bukan sudut terburuk sebenarnya. "
                      "Jalankan OAT dulu lalu ulangi plan corners.")
                pats = {"semua_plus": [1] * 6, "semua_minus": [-1] * 6,
                        "selang_seling_a": [1, -1, 1, -1, 1, -1], "selang_seling_b": [-1, 1, -1, 1, -1, 1]}
                corners = {n: dict(zip(ORDER, v)) for n, v in pats.items()}
            else:
                corners = {"fr_turun": {p: -sg[p]["fr_ghz"] for p in ORDER},
                           "fr_naik": {p: sg[p]["fr_ghz"] for p in ORDER},
                           "bw_turun": {p: -sg[p]["bw_mhz"] for p in ORDER},
                           "gain_turun": {p: -sg[p]["gain_fr_ieee_dbi"] for p in ORDER}}
            for i, (n, sv) in enumerate(corners.items()):
                make(sv, K_CORNER + i, "corners", n)
        if "random" in a.plan:
            rng = np.random.default_rng(a.seed + base)
            for i in range(a.n_random):
                make({pn: float(rng.uniform(-1, 1)) for pn in ORDER}, K_RANDOM + i, "random", f"acak{i + 1}")

    out = a.out or os.path.join(paths.samples_dir(tol_run),
                                f"tol_{'+'.join(a.plan)}_s{'-'.join(map(str, a.sample))}.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    mpath = os.path.splitext(out)[0] + "_meta.csv"
    pd.DataFrame(meta).to_csv(mpath, index=False)
    n_skip = sum(m["dilewati"] for m in meta)
    if n_skip:
        print(f"\n{n_skip} skenario dilewati karena geometri tidak valid (tercatat di meta; analisis melaporkannya).")
    print(f"\n{len(df)} simulasi disimpan: {out}\nMeta: {mpath}")
    print("Jalankan:\n  py main.py run --run-name " + tol_run + " --samples " + os.path.relpath(out, ROOT) + " --auto-yes")


if __name__ == "__main__":
    main()
