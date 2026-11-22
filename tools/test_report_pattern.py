"""Uji bagian 9 laporan (cstopt/report/pattern.py): metrik pola pada pola sintetik berjawaban diketahui, pembacaan irisan CST,
berkas hilang dilewati, dan (bila data/ ada) laporan per desain.

  py tools\\test_report_pattern.py
"""
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cstopt import paths  # noqa: E402
from cstopt.report import pattern as pt  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print((" [OK]    " if cond else " [GAGAL] ") + name + (f"  {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)


def write_cut(path, dmax=6.0, n=2.0, floor=-40.0, co="phi", phi_cut=0):
    """Berkas gaya CST: theta 0..180 pada phi_cut lalu theta 179..1 pada phi_cut + 180. D = dmax + 10 log10(cos^n), batas bawah floor."""
    rows = []
    for th, phi in [(t, phi_cut) for t in range(0, 181)] + [(t, phi_cut + 180) for t in range(179, 0, -1)]:
        c = np.cos(np.radians(th)) if th < 90 else 0.0
        d = max(floor, dmax + 10 * np.log10(max(c, 1e-9) ** n))
        co_v, cr_v = d, d - 60.0
        at, ap = (cr_v, co_v) if co == "phi" else (co_v, cr_v)
        rows.append(f"{th:9.3f} {phi:15.3f} {d:16.3e} {at:16.3e} {100.0:12.3f} {ap:16.3e} {200.0:12.3f} {40.0:14.3e}")
    with open(path, "w") as fh:
        fh.write("Theta [deg.]  Phi   [deg.]  Abs(Dir.)[dBi   ]   Abs(Theta)[dBi   ]  Phase(Theta)[deg.]  Abs(Phi  )[dBi   ]  Phase(Phi  )[deg.]  Ax.Ratio[dB    ]\n")
        fh.write("-" * 120 + "\n")
        fh.write("\n".join(rows) + "\n")


def main():
    tmp = tempfile.mkdtemp(prefix="pat_")
    f1 = os.path.join(tmp, "a.txt")
    write_cut(f1, dmax=6.0, n=2.0, co="phi")
    c = pt.read_cut(f1)
    check("read_cut: 360 titik, sudut -179 sampai 180 bertanda", c is not None and len(c["ang"]) == 360 and c["ang"].min() == -179 and c["ang"].max() == 180)
    d_at = lambda x: float(c["dir"][int(np.argmin(np.abs(c["ang"] - x)))])      # noqa: E731
    check("read_cut: sisi negatif (Phi + 180) simetris: D(-45) = D(+45) = 3 dBi", abs(d_at(45) - 3.01) < 0.02 and abs(d_at(-45) - d_at(45)) < 1e-9, f"{d_at(45)} {d_at(-45)}")
    m = pt.metrics(c)
    check("Dmax 6 dBi dan arah puncak 0", abs(m["dmax"] - 6.0) < 1e-6 and abs(m["theta_peak"]) < 1e-6)
    check("HPBW cos^2 = 90 derajat (galat di bawah 1)", m["hpbw"] is not None and abs(m["hpbw"] - 90.0) < 1.0, str(m["hpbw"]))
    check("F/B = 6 dikurangi lantai (-40) = 46 dB", abs(m["fb"] - 46.0) < 1e-6, str(m["fb"]))
    check("komponen utama Phi: irisan ini bidang H; XPD sektor sekitar 60 dB", m["plane"] == "H" and abs(m["xpd"] - 60.0) < 1e-6, str(m))
    check("axial ratio di boresight terbaca (40 dB)", m["ar"] == 40.0)
    f2 = os.path.join(tmp, "b.txt")
    write_cut(f2, co="theta", phi_cut=90)
    check("komponen utama Theta: bidang E", pt.metrics(pt.read_cut(f2))["plane"] == "E")
    f3 = os.path.join(tmp, "c.txt")
    write_cut(f3, dmax=3.0, n=0.0, floor=-40.0)               # pola isotropik: tidak turun 3 dB di mana pun
    mi = pt.metrics(pt.read_cut(f3))
    check("pola datar: HPBW tidak terdefinisi (None), bukan angka palsu", mi["hpbw"] is None)
    check("berkas rusak mengembalikan None", pt.read_cut(os.path.join(tmp, "tidak_ada.txt")) is None)
    check("VSWR dari S11: 0 dB mendekati batas, -9.54 dB sekitar 2", abs(float(pt.vswr_from_db(-9.5424)) - 2.0) < 0.01)
    notes = []
    fn, rows = pt.fig_patterns("RUN_TIDAK_ADA", [(1, "x")], pd.DataFrame({"sample_id": [1], "fr_ghz": [3.5]}), tmp, notes)
    check("ff hilang: dilewati dengan catatan, tanpa galat", fn is None and rows == [] and notes and "tidak ada berkas ff" in notes[0], str(notes))

    # laporan per desain pada data nyata (dilewati bila data tidak ada)
    ro, fr4 = "MicrostripAntena_RO4350B", "MicrostripAntena"
    have = [r for r in (ro, fr4) if os.path.exists(os.path.join(paths.run_dir(r), "batch_lhs.csv"))]
    if not have:
        print("  (data/ tidak ada: uji laporan per desain dilewati)")
    for r in have:
        out = os.path.join(tmp, "rep_" + r)
        res = subprocess.run([sys.executable, os.path.join(ROOT, "main.py"), "report", "--runs", r, "--out-dir", out], cwd=ROOT, capture_output=True, text=True, timeout=900)
        check(f"report --runs {r}: kode 0", res.returncode == 0, (res.stdout + res.stderr)[-300:])
        md = open(os.path.join(out, "report.md"), encoding="utf-8").read() if os.path.exists(os.path.join(out, "report.md")) else ""
        check(f"{r}: bagian 1 sampai 9 ada", all(f"## {i}. " in md for i in range(1, 10)))
        other = [x for x in (ro, fr4) if x != r][0]
        check(f"{r}: tidak menyebut desain lain ({other})", re.search(re.escape(other) + r"(?![A-Za-z0-9_])", md) is None)
        for nm in ("pattern", "vswr_eff", "phase"):
            check(f"{r}: gambar {nm} dibuat", os.path.exists(os.path.join(out, f"report_{nm}_{r}.png")))
        check(f"{r}: tabel metrik pola dan ringkasan ada", "HPBW (derajat)" in md and "directivity di fr (dBi)" in md)
    print("\n" + ("SEMUA LULUS" if not FAILS else f"{len(FAILS)} pemeriksaan GAGAL: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
