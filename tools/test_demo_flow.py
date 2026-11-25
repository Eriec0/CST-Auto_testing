"""Uji alur lengkap tanpa CST pada desain demonstrasi E-patch (eshape_fr4), dengan nama run TERPISAH sehingga data asli tidak tersentuh:
lhs, mock_run (respons buatan), qc, curves, pareto, report. Memastikan tidak ada konstanta antena pertama (pita 3,3 sampai 3,7 GHz, f0 3,5 GHz,
BW 200 MHz, gain 5 dBi) yang tertinggal di alur untuk desain dengan pita dan f0 lain.

  py tools\\test_demo_flow.py

Menulis hanya ke data/MicrostripAntena_EShape_mocktest dan folder sementara; folder itu dihapus di akhir. Tidak menyentuh data/MicrostripAntena_EShape.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cstopt import paths  # noqa: E402

RUN = "MicrostripAntena_EShape_mocktest"
FAILS = []


def check(name, cond, extra=""):
    print((" [OK]    " if cond else " [GAGAL] ") + name + (f"  {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)


def sh(*args, timeout=900):
    r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return r, r.stdout + r.stderr


def main():
    rd = paths.run_dir(RUN)
    shutil.rmtree(rd, ignore_errors=True)
    tmp = tempfile.mkdtemp(prefix="demoflow_")
    try:
        lhs = os.path.join(tmp, "lhs.csv")
        r, o = sh("main.py", "lhs", "--design", "eshape_fr4", "-n", "16", "--seed", "1", "--out", lhs)
        check("lhs 16 sampel ke berkas sementara", r.returncode == 0 and "semua valid" in o, o[-200:])
        r, o = sh("tools/mock_run.py", "--design", "eshape_fr4", "--run-name", RUN, "--samples", lhs)
        check("mock_run ke run terpisah", r.returncode == 0 and os.path.exists(os.path.join(rd, "batch_lhs.csv")), o[-300:])
        r, o = sh("main.py", "qc", "--run-name", RUN)
        check("qc: lulus, ringkasan memakai pita 2,4 sampai 2,6 GHz dan BW 100 MHz (bukan 3,3 sampai 3,7 dan 200)",
              r.returncode == 0 and "Semua pemeriksaan lulus" in o and "fr di 2.4-2.6 GHz" in o and "BW >= 100" in o and "3.3-3.7" not in o and "BW >= 200" not in o, o[-300:])
        r, o = sh("main.py", "curves", "--run-name", RUN)
        check("curves: konsisten (f0 2,5 GHz dan pita 2,4 sampai 2,6 dari desain)", r.returncode == 0 and "KONSISTEN" in o and "f0 2.5 GHz" in o and "pita 2.4 sampai 2.6" in o, o[-400:])
        r, o = sh("main.py", "curves", "--run-name", RUN, "--f0", "3.5", "--band", "3.3", "3.7")
        check("curves dengan konstanta antena pertama (3,5 GHz, 3,3 sampai 3,7) TIDAK cocok (membuktikan pemeriksa sensitif)", r.returncode == 1 and "ADA KETIDAKCOCOKAN" in o, o[-300:])
        png = os.path.join(tmp, "pareto.png")
        r, o = sh("main.py", "pareto", "--runs", RUN, "--out", png)
        n_ok = re.search(r"(\d+) memenuhi syarat", o)
        check("pareto: target BW 100 dan gain 3 dari desain, pita 2,4 sampai 2,6, ada sampel memenuhi syarat, gambar dibuat",
              r.returncode == 0 and "BW >= 100 MHz, gain >= 3 dBi" in o and "Pita fr 2.4 sampai 2.6" in o and n_ok and int(n_ok.group(1)) > 0 and os.path.exists(png), o[-400:])
        rep = os.path.join(tmp, "rep")
        r, o = sh("main.py", "report", "--runs", RUN, "--out-dir", rep)
        md = open(os.path.join(rep, "report.md"), encoding="utf-8").read() if os.path.exists(os.path.join(rep, "report.md")) else ""
        check("report: 9 bagian, target BW 100 dan gain 3, pita 2,4 sampai 2,6 GHz, tanpa pita 3,3 sampai 3,7",
              r.returncode == 0 and all(f"## {i}. " in md for i in range(1, 10)) and "BW >= 100 MHz, gain >= 3 dBi" in md and "2.4 sampai 2.6" in md and "3.3 sampai 3.7" not in md, o[-300:])
        r, o = sh("main.py", "report", "--runs", RUN, "--focus", "rl", "--out-dir", os.path.join(tmp, "rep_rl"))
        md = open(os.path.join(tmp, "rep_rl", "report.md"), encoding="utf-8").read() if os.path.exists(os.path.join(tmp, "rep_rl", "report.md")) else ""
        check("report fokus rl pada desain demonstrasi", r.returncode == 0 and "Desain dengan RL terdalam" in md, o[-300:])
    finally:
        shutil.rmtree(rd, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + ("SEMUA LULUS" if not FAILS else f"{len(FAILS)} pemeriksaan GAGAL: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
