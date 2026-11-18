"""Uji GUI G1 (tanpa CST, tanpa menjalankan perintah sungguhan): argumen yang terbentuk, validasi opsi, kunci region adaptif.

  py tools\\test_gui_g1.py        (butuh layar; membuka jendela GUI sebentar lalu menutupnya)
Di Linux tanpa layar:  xvfb-run -a python3 tools/test_gui_g1.py
"""
import os
import sys
import tempfile
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cstopt.gui import app as gapp  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  [OK]   " if cond else "  [GAGAL] ") + name + (f"  {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)


def main():
    root = tk.Tk()
    a = gapp.App(root)
    root.update()
    warns, captured = [], []
    messagebox.showwarning = lambda title, msg, **k: warns.append(title)
    a.run_cmd = lambda argv, after=None: captured.append(list(argv))

    # 1. bawaan: tidak ada opsi P2
    argv = a._suggest_argv()
    check("bawaan tanpa --sweep/--diversity/--region-adapt", not any(x in argv for x in ("--sweep", "--diversity", "--region-adapt")), str(argv))

    # 2. validasi sweep
    a.bo_sweep.set("ngawur")
    check("sweep format salah ditolak", a._check_bo_inputs() is False and warns[-1] == "Sweep")
    a.bo_sweep.set("gain_fr_ieee_dbi=4.0:5.4")
    a.bo_focus.set("otomatis")
    check("sweep tanpa fokus ditolak", a._check_bo_inputs() is False)
    a.bo_focus.set("bw")
    a.bo_q.set(1)
    check("sweep dengan q=1 ditolak", a._check_bo_inputs() is False)
    a.bo_q.set(5)
    check("sweep valid diterima", a._check_bo_inputs() is True)
    argv = a._suggest_argv()
    check("argv memuat --sweep dan --focus", "--sweep" in argv and "gain_fr_ieee_dbi=4.0:5.4" in argv and "--focus" in argv, str(argv))

    # 3. diversity
    a.bo_div.set("abc")
    check("diversity bukan angka ditolak", a._check_bo_inputs() is False and warns[-1] == "Diversity")
    a.bo_div.set("-1")
    check("diversity negatif ditolak", a._check_bo_inputs() is False)
    a.bo_div.set("0.4")
    check("diversity 0.4 diterima", a._check_bo_inputs() is True)
    check("argv memuat --diversity 0.4", "--diversity" in a._suggest_argv() and "0.4" in a._suggest_argv())

    # 4. region adaptif saling eksklusif dengan region manual dan otomatis
    a.bo_region.set("Lp=16:19")
    a.bo_region_auto.set("6:0.15")
    a.bo_radapt.set(True)
    a._toggle_radapt()
    argv = a._suggest_argv()
    check("region adaptif mengosongkan region manual dan otomatis", a.bo_region.get() == "" and a.bo_region_auto.get() == "")
    check("entri region dinonaktifkan", str(a.e_region.cget("state")) == "disabled" and str(a.e_region_auto.cget("state")) == "disabled")
    check("argv memuat --region-adapt saja", "--region-adapt" in argv and "--region" not in argv and "--region-auto" not in argv, str(argv))
    a.bo_radapt.set(False)
    a._toggle_radapt()
    check("entri region aktif lagi", str(a.e_region.cget("state")) == "normal")

    # 5. tombol memanggil perintah yang benar
    a.bo_sweep.set(""), a.bo_div.set("")
    captured.clear()
    a.do_suggest()
    a.do_validate()
    a.do_validate_pof()
    a.do_sensitivity()
    a.rep_focus.set("bw")
    a.rep_constraint.set("R1:gain_fr_ieee_dbi>=5.0; R1:gain_fr_ieee_dbi>=4.0")
    a.do_make_report()
    names = [c[0] for c in captured]
    check("urutan perintah suggest, validate, validate, sensitivity, report", names == ["suggest", "validate", "validate", "sensitivity", "report"], str(names))
    check("validate kedua memuat --pof-compare", "--pof-compare" in captured[2] and "--pof-compare" not in captured[1])
    rep = captured[4]
    check("report memuat dua --constraint dan --focus bw", rep.count("--constraint") == 2 and "--focus" in rep and "bw" in rep, str(rep))
    captured.clear()
    a.bo_sweep.set("ngawur")
    a.do_suggest()
    check("do_suggest tidak menjalankan bila opsi tidak valid", captured == [])

    # 6. tabel kandidat memuat kolom sweep_bound
    with tempfile.TemporaryDirectory() as td:
        pth = os.path.join(td, "bo_candidates.csv")
        with open(pth, "w", encoding="utf-8") as fh:
            fh.write("sample_id,Lp,Wp,LU,WU,WD\n7,1,2,3,4,5\n")
        with open(os.path.join(td, "bo_candidates_report.csv"), "w", encoding="utf-8") as fh:
            fh.write("sample_id,sweep_bound,acq,pof,pred_bw_mhz,std_bw_mhz,Lp,Wp,LU,WU,WD\n7,4.35,1.0,0.5,200,5,1,2,3,4,5\n")
        a.status = {"files": {"bo_candidates": {"path": pth}}, "objective": {"column": "bw_mhz"}}
        a._load_candidates()
        cols = list(a.cand["columns"])
        check("tabel kandidat memuat sweep_bound", "sweep_bound" in cols, str(cols))

    root.destroy()
    print("\nSEMUA LULUS" if not FAILS else f"\n{len(FAILS)} GAGAL: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
