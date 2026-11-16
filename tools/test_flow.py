"""
Uji alur penuh tanpa CST memakai desain demo analitik:  py tools/test_flow.py [--keep] [--rounds N]

Urutan: lhs, mock_run, qc, curves, train, suggest + mock_run (N ronde BO), pareto, status, sensitivity, validate, report.
Semua berjalan di data/DemoAnalytic/ (dihapus di akhir kecuali --keep) dan keluaran pareto/report ke folder sementara,
jadi data nyata tidak tersentuh. Lulus bila setiap langkah selesai tanpa galat dan menghasilkan berkas yang diharapkan.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cstopt import paths  # noqa: E402

DESIGN, RUN = "_demo_analytic", "DemoAnalytic"
PY = sys.executable
fails = []


def step(label, args, expect=None):
    r = subprocess.run([PY] + args, cwd=ROOT, capture_output=True, text=True)
    ok = r.returncode == 0 and all(os.path.exists(e) for e in (expect or []))
    print(f"  [{'OK' if ok else 'GAGAL'}] {label}")
    if not ok:
        fails.append(label)
        print("      " + "\n      ".join((r.stdout + r.stderr).strip().splitlines()[-6:]))
    return ok


def main():
    ap = argparse.ArgumentParser(description="Uji alur penuh offline (desain demo analitik)")
    ap.add_argument("--keep", action="store_true", help="jangan hapus data/DemoAnalytic di akhir")
    ap.add_argument("--rounds", type=int, default=2, help="jumlah ronde BO (suggest + mock_run)")
    a = ap.parse_args()

    rd = paths.run_dir(RUN)
    samples = os.path.join(paths.samples_dir(RUN), "lhs_samples.csv")
    cand = os.path.join(paths.samples_dir(RUN), "bo_candidates.csv")
    tmp = tempfile.mkdtemp(prefix="flow_")
    d = ["--design", DESIGN]
    shutil.rmtree(rd, ignore_errors=True)
    print(f"Uji alur penuh offline ({DESIGN}, data di {rd})")
    try:
        step("lhs (20 sampel)", ["main.py", "lhs"] + d + ["-n", "20", "--seed", "1"], [samples])
        step("mock_run LHS", ["tools/mock_run.py"] + d + ["--samples", samples], [os.path.join(rd, "batch_lhs.csv")])
        step("mock_run ulang (resume)", ["tools/mock_run.py"] + d + ["--samples", samples])
        step("qc", ["main.py", "qc", "--design", DESIGN, "--run-name", RUN])
        step("curves", ["main.py", "curves", "--run-name", RUN])
        step("train", ["main.py", "train"] + d + ["--restarts", "2"], [os.path.join(rd, "models")])
        for i in range(1, a.rounds + 1):
            step(f"suggest ronde {i}", ["main.py", "suggest"] + d + ["-q", "5", "--seed", "0", "--restarts", "2", "--pool", "8192"], [cand])
            step(f"mock_run kandidat ronde {i}", ["tools/mock_run.py"] + d + ["--samples", cand])
        step("status", ["main.py", "status"] + d)
        step("pareto", ["main.py", "pareto", "--runs", RUN, "--out", os.path.join(tmp, "pareto")], [os.path.join(tmp, "pareto_front.csv")])
        step("sensitivity", ["main.py", "sensitivity"] + d)
        step("validate", ["main.py", "validate"] + d + ["--restarts", "2"])
        step("report", ["main.py", "report", "--runs", RUN, "--out-dir", os.path.join(tmp, "rep")], [os.path.join(tmp, "rep", "report.md")])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if not a.keep:
            shutil.rmtree(rd, ignore_errors=True)
    n = sum(1 for _ in open(os.path.join(rd, "batch_lhs.csv"))) - 1 if a.keep and os.path.exists(os.path.join(rd, "batch_lhs.csv")) else None
    if n is not None:
        print(f"  baris data: {n}")
    print("\n" + ("SEMUA LULUS" if not fails else f"{len(fails)} langkah gagal: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
