"""Uji GUI F1: tombol Laporan memakai desain terpilih (data/_report_<run>) atau gabungan (data/_compare). Tanpa CST.

  py tools\\test_gui_report.py        (Linux tanpa layar:  xvfb-run -a python3 tools/test_gui_report.py)
"""
import os
import sys
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cstopt import paths  # noqa: E402
from cstopt.gui import app as gapp  # noqa: E402
from cstopt.gui import commands as cmd  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print((" [OK]    " if cond else " [GAGAL] ") + name + (f"  {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)


def main():
    # fungsi murni
    a0 = cmd.report(["R1"], "bw", ["R1:gain_fr_ieee_dbi>=4"], out_dir="data/_report_R1")
    check("commands.report: --runs dan --out-dir", a0[:5] == ["report", "--runs", "R1", "--out-dir", "data/_report_R1"] and "--focus" in a0 and "--constraint" in a0, str(a0))
    check("commands.report tanpa out_dir tetap seperti dulu", cmd.report(None) == ["report"])

    root = tk.Tk()
    a = gapp.App(root)
    root.update()
    warns, captured = [], []
    messagebox.showwarning = lambda title, msg, **k: warns.append(title)
    a.run_cmd = lambda argv, after=None: captured.append(list(argv))
    check("pilihan laporan bawaan: Desain terpilih", a.rep_scope.get() == gapp.REPORT_SCOPES[0])

    a.status = {"run": "RunContoh"}
    a.do_make_report()
    argv = captured[-1]
    out = argv[argv.index("--out-dir") + 1]
    check("desain terpilih: --runs RunContoh", argv[argv.index("--runs") + 1] == "RunContoh" and argv.count("--runs") == 1, str(argv))
    check("desain terpilih: keluaran data/_report_RunContoh", out == os.path.join(paths.DATA_DIR, "_report_RunContoh"), out)

    a.rep_scope.set(gapp.REPORT_SCOPES[1])
    a.do_make_report()
    argv = captured[-1]
    check("gabungan: tanpa --runs dan tanpa --out-dir (bawaan data/_compare)", "--runs" not in argv and "--out-dir" not in argv, str(argv))

    a.rep_scope.set(gapp.REPORT_SCOPES[0])
    a.rep_focus.set("gain")
    a.rep_constraint.set("RunContoh:bw_mhz>=100; RunContoh:gain_fr_ieee_dbi>=4")
    a.do_make_report()
    argv = captured[-1]
    check("fokus dan dua constraint ikut", argv[argv.index("--focus") + 1] == "gain" and argv.count("--constraint") == 2, str(argv))

    n = len(captured)
    a.status = {}
    a.do_make_report()
    check("run belum diketahui: peringatan, tidak menjalankan", len(captured) == n and warns and warns[-1] == "Laporan")
    root.destroy()
    print("\n" + ("SEMUA LULUS" if not FAILS else f"{len(FAILS)} pemeriksaan GAGAL: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
