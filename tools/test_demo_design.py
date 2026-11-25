"""Uji konsistensi desain demonstrasi E-patch (tanpa CST): macros/eshape_fr4.bas harus sama dengan designs/eshape_fr4.py.

  py tools\\test_demo_design.py

Macro tidak bisa dijalankan di sini, jadi uji ini membaca teks macro dan membandingkannya dengan file desain: nama parameter, nilai awal, substrat,
rentang frekuensi dan monitor, serta ambang aturan geometri. Juga memeriksa nilai awal valid, di dalam rentang, dan peluang lolos aturan geometri.
"""
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cstopt import substrate as sb              # noqa: E402
from cstopt.loader import load_design_module    # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print((" [OK]    " if cond else " [GAGAL] ") + name + (f"  {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)


def main():
    d = load_design_module("eshape_fr4")
    mac = open(os.path.join(ROOT, "macros", "eshape_fr4.bas"), encoding="utf-8").read().replace("\r\n", "\n")
    consts = {k: v for k, v in re.findall(r'^Const (\w+) = ("[^"]*"|[^\s\']+)', mac, re.M)}
    vals = {k[2:]: float(v.strip('"')) for k, v in consts.items() if k.startswith("V_")}
    setp = re.findall(r'SetP "(\w+)", ', mac)

    print("parameter")
    check("macro mendefinisikan semua PARAM_NAMES desain", all(p in setp for p in d.PARAM_NAMES), str([p for p in d.PARAM_NAMES if p not in setp]))
    check("parameter lain di macro hanya yang tetap atau turunan (hs, tc, Wf, Lf, gI, Wsub)", set(setp) - set(d.PARAM_NAMES) == {"hs", "tc", "Wf", "Lf", "gI", "Wsub"}, str(set(setp) - set(d.PARAM_NAMES)))
    check("nilai awal macro = BASE_PARAMS desain", all(abs(vals[p] - d.BASE_PARAMS[p]) < 1e-9 for p in d.PARAM_NAMES), str({p: (vals.get(p), d.BASE_PARAMS[p]) for p in d.PARAM_NAMES}))
    check("hs dan Wf macro = EXTRA_BASE desain", abs(vals["hs"] - d.EXTRA_BASE["hs"]) < 1e-9 and abs(vals["Wf"] - d.EXTRA_BASE["Wf"]) < 1e-9)
    check("hs macro = SUBSTRATE h; material macro = SUBSTRATE material", abs(vals["hs"] - d.SUBSTRATE["h"]) < 1e-9 and consts["MAT_SUB"].strip('"') == d.SUBSTRATE["material"], consts["MAT_SUB"])
    check("Wf macro memberi saluran 50 ohm (Hammerstad): lebar 3,11 mm dan impedansi 50 plus minus 1 ohm",
          abs(sb.wf50(d.SUBSTRATE["er"], d.SUBSTRATE["h"]) - vals["Wf"]) < 0.01 and abs(sb.z0_line(d.SUBSTRATE["er"], vals["hs"], vals["Wf"]) - 50) < 1.0)

    print("frekuensi dan monitor")
    m0, m1, ms = d.CST["monitors_ghz"]
    check("FF_F_START, FF_F_STOP, FF_F_STEP macro = CST['monitors_ghz']", (float(consts["FF_F_START"]), float(consts["FF_F_STOP"]), float(consts["FF_F_STEP"])) == (m0, m1, ms))
    check("FF_F_MAIN macro = CST['f0_ghz'] dan f0 ada di grid monitor", float(consts["FF_F_MAIN"]) == d.CST["f0_ghz"] and abs(((d.CST["f0_ghz"] - m0) / ms) - round((d.CST["f0_ghz"] - m0) / ms)) < 1e-9)
    fr = re.search(r'Solver\.FrequencyRange " & Q\("([\d.]+)"\) & ", " & Q\("([\d.]+)"\)', mac)
    check("Solver.FrequencyRange macro = rentang monitor", fr and (float(fr.group(1)), float(fr.group(2))) == (m0, m1), str(fr.groups() if fr else None))
    check("pita desain di dalam rentang monitor", m0 <= d.BAND_GHZ[0] < d.BAND_GHZ[1] <= m1 and d.BAND_GHZ == tuple(d.CST["band_ghz"]))
    check("jumlah monitor = 9 (sama dengan bawaan qc --expect-eff)", int(round((m1 - m0) / ms)) + 1 == 9)

    print("aturan geometri macro = desain")
    a = re.search(r"Val\(V_Lp\) - Val\(V_Lsl\) <= Val\(V_LI\) \+ ([\d.]+)", mac)
    b = re.search(r"Val\(V_Dsl\) - Val\(V_Wsl\) / 2 < ([\d.]+)", mac)
    c = re.search(r"Val\(V_Dsl\) \+ Val\(V_Wsl\) / 2 > Val\(V_Wp\) / 2 - ([\d.]+)", mac)
    check("ambang macro = MARGIN, CENTER_PRONG, EDGE_PRONG desain", a and b and c and (float(a.group(1)), float(b.group(1)), float(c.group(1))) == (d.MARGIN, d.CENTER_PRONG, d.EDGE_PRONG),
          str([x.group(1) if x else None for x in (a, b, c)]))
    check("CENTER_PRONG lebih besar dari setengah celah inset (Wf/2 + gI)", d.CENTER_PRONG > vals["Wf"] / 2 + vals["gI"], str(vals["Wf"] / 2 + vals["gI"]))

    print("desain")
    base = dict(d.BASE_PARAMS)
    check("nilai awal di dalam BOUNDS dan lolos geometry_problems", all(d.BOUNDS[p][0] <= base[p] <= d.BOUNDS[p][1] for p in d.PARAM_NAMES) and d.geometry_problems(base) == [], str(d.geometry_problems(base)))
    rng = np.random.default_rng(0)
    pts = [{p: rng.uniform(*d.BOUNDS[p]) for p in d.PARAM_NAMES} for _ in range(4000)]
    ok = sum(1 for q in pts if not d.geometry_problems(q)) / len(pts)
    check("peluang lolos aturan geometri di dalam BOUNDS di atas 50 persen (LHS tidak boros)", ok > 0.5, f"{ok:.2f}")
    check("SLOT tidak keluar patch: Lsl maksimum lebih kecil dari Lp minimum", d.BOUNDS["Lsl"][1] < d.BOUNDS["Lp"][0])
    resp = d.mock_response(base, np.linspace(m0, m1, 200))
    check("mock_response nilai awal: array sepanjang f dan S11 terbatas", all(len(v) == 200 and np.all(np.isfinite(v)) for v in resp.values()))
    check("nama desain dan RUN_NAME: RUN_NAME diawali MicrostripAntena dan berbeda dari desain lain", d.RUN_NAME == "MicrostripAntena_EShape" and d.NAME == "eshape_fr4")
    print("\n" + ("SEMUA LULUS" if not FAILS else f"{len(FAILS)} pemeriksaan GAGAL: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
