"""Uji T2 (tata letak tab 1 sampai 5 dan 7): panel info, Analisis model di tab 4, opsi lanjutan terlipat, tinggi tabel.

  py tools\\test_gui_t2.py [--shot FOLDER] [--size 1366x728@1.333]
Linux tanpa layar:  xvfb-run -a python3 tools/test_gui_t2.py

Bagian A tidak butuh tkinter (kunci baru status --json, penguraian hasil QC). Bagian B butuh tkinter dan memeriksa tata letak
pada layar tiruan; tinggi tabel dicetak sebagai angka ukur (bukan perkiraan) supaya bisa dibandingkan dengan rencana.
"""
import argparse
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

FAILS = []


def check(name, cond, extra=""):
    print(("  [OK]   " if cond else "  [GAGAL] ") + name + (f"  {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)


def part_a():
    print("A: status --json dan penguraian QC (tanpa tkinter)")
    from cstopt import paths, status
    for d in paths.list_designs():
        s = status.summary(d)
        if "run" not in s:
            continue
        tag = d + ": "
        check(tag + "params ada dan lengkap", "params" in s and len(s["params"]) >= 1 and all(
            {"name", "lo", "hi", "base_lo", "base_hi", "changed"} <= set(p) for p in s["params"]))
        check(tag + "lo < hi", all(p["lo"] < p["hi"] for p in s.get("params", [])))
        for k in ("n_lhs", "pending_lhs", "pending_bo", "n_curves"):
            check(tag + f"{k} bilangan bulat >= 0", isinstance(s.get(k), int) and s[k] >= 0, str(s.get(k)))
        if "n_samples" in s:
            q = s.get("qc_view", {})
            check(tag + "qc_view memuat n dan batas pita", q.get("n") == s["n_samples"] and len(q.get("band", [])) == 2, str(q))
            check(tag + "in_band <= n dan rl_ok <= n", q.get("in_band", 0) <= q["n"] and q.get("rl_ok", 0) <= q["n"])
        txt = status.format_summary(s)
        check(tag + "teks CLI tidak memuat kunci baru", "pending" not in txt and "qc_view" not in txt)
    # penguraian hasil QC lewat App._note_qc tanpa membuat jendela (tkinter tiruan kosong bila tidak terpasang: hanya untuk impor)
    try:
        import tkinter  # noqa: F401
    except ImportError:
        for name in ("tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox"):
            m = types.ModuleType(name)
            sys.modules[name] = m
        sys.modules["tkinter"].ttk = sys.modules["tkinter.ttk"]
        sys.modules["tkinter"].filedialog = sys.modules["tkinter.filedialog"]
        sys.modules["tkinter"].messagebox = sys.modules["tkinter.messagebox"]
        print("  (tkinter tidak ada: memakai modul tiruan kosong untuk impor)")
    from cstopt.gui import app as gapp
    stub = types.SimpleNamespace(_user_stopped=False, qc_last={"qc": "x", "curves": "x"}, _cap=[], _render_qc_last=lambda: None)
    note = lambda name, rc, lines: (stub.__setattr__("_cap", lines), gapp.App._note_qc(stub, name, rc), stub.qc_last[name])[-1]
    check("QC lulus", "semua pemeriksaan lulus" in note("qc", 0, ["Baris: 3", "  Semua pemeriksaan lulus."]))
    check("QC masalah dihitung", note("qc", 1, ["  [MASALAH] a", "  [MASALAH] b"]).startswith("2 masalah"))
    check("QC tanpa keluaran dan gagal", "gagal (kode 2)" in note("qc", 2, []))
    check("kurva KONSISTEN", note("curves", 0, ["KESIMPULAN: kurva KONSISTEN dengan data CST di CSV (asli, folder benar)."]).startswith("KONSISTEN"))
    check("kurva tidak cocok", note("curves", 1, ["KESIMPULAN: ADA KETIDAKCOCOKAN: kurva mungkin"]).startswith("TIDAK konsisten"))
    stub._user_stopped = True
    stub.qc_last["qc"] = "lama"
    stub._cap = ["  Semua pemeriksaan lulus."]
    gapp.App._note_qc(stub, "qc", 0)
    check("dihentikan pengguna: hasil tidak diubah", stub.qc_last["qc"] == "lama")


def texts(widget):
    out = []
    for c in widget.winfo_children():
        try:
            out.append(str(c.cget("text")))
        except Exception:
            pass
        out += texts(c)
    return out


def part_b(size, shots):
    import tkinter as tk
    if not hasattr(tk, "Tk"):                                # modul tiruan dari bagian A
        print("B: dilewati (tkinter tidak terpasang di sini)")
        return
    from tkinter import messagebox
    from cstopt.gui import app as gapp
    from test_gui_g4 import parse_sizes, problems_in, pump, shot, wait_for
    SW, SH, scaling = parse_sizes(size)[0]
    tag = f"{SW}x{SH}@{scaling}"
    print(f"B: layar tiruan {tag}")
    tk.Misc.winfo_screenwidth = lambda self, _w=SW: _w
    tk.Misc.winfo_screenheight = lambda self, _h=SH: _h
    root = tk.Tk()
    root.report_callback_exception = lambda *e: (print("  [GAGAL] galat callback Tk:", e[1]), FAILS.append("callback Tk"))
    root.tk.call("tk", "scaling", scaling)
    warned = []
    messagebox.showwarning = lambda *a, **k: warned.append(a)
    messagebox.showinfo = lambda *a, **k: None
    a = gapp.App(root)
    wait_for(root, lambda: a.status.get("run") and not a._status_busy)
    pump(root, 0.5)
    s = a.status

    def tab(i):
        a.nb.select(i)
        pump(root, 0.3)

    for i in range(a.nb.index("end")):
        tab(i)
        title = a.nb.tab(i, "text")
        probs = problems_in(root, tk, f"tab {title}: ")
        check(f"tab '{title}' tanpa widget terpotong", not probs, "; ".join(probs[:4]))
        shot(root, shots, f"t2_{tag}_tab{i + 1}")

    tab(0)
    check("tab 1: baris rentang = jumlah parameter", len(a.rng_tree.get_children()) == len(s.get("params", [])) > 0)
    check("tab 1: panel kanan di samping panel kiri (lebar cukup)", a.rng_tree.winfo_rootx() - a.tab_lhs.winfo_rootx() > 400,
          str(a.rng_tree.winfo_rootx() - a.tab_lhs.winfo_rootx()))
    check("tab 1: info lhs_samples terisi", a.lhs_info.get().startswith("lhs_samples.csv"), a.lhs_info.get())
    tab(1)
    check("tab 2: teks progres terisi", "Dataset:" in a.sim_text.get() and "Kurva S11" in a.sim_text.get(), a.sim_text.get())
    check("tab 2: bilah progres = jumlah sampel", int(float(a.sim_bar.cget("value"))) == s.get("n_samples", 0))
    tab(2)
    check("tab 3: ringkasan data terisi", "Sampel:" in a.qc_text.get() and "fr di pita" in a.qc_text.get(), a.qc_text.get())
    check("tab 3: QC terakhir awalnya belum dijalankan", "belum dijalankan" in a.qc_last_text.get())
    tab(3)
    t4 = texts(a.tab_gpr)
    check("tab 4: tombol Analisis model ada", all(any(x.startswith(k) for x in t4) for k in ("Validasi maju", "Sensitivitas", "Rentang parameter")))
    check("tab 4: tabel metrik >= 130 px", a.metrics.winfo_height() >= 130, str(a.metrics.winfo_height()))
    tab(4)
    t5 = texts(a.tab_bo)
    check("tab 5: tombol Analisis model sudah tidak di sini", not any(x.startswith(k) for x in t5 for k in ("Validasi maju", "Sensitivitas", "Rentang parameter")))
    check("tab 5: opsi lanjutan tertutup bawaan", (not a.adv.is_open) and not a.adv.body.winfo_ismapped())
    cv = a.tab_bo.master
    check("tab 5 (tertutup): tidak perlu menggulir", a.tab_bo.winfo_reqheight() <= cv.winfo_height() + 1,
          f"isi {a.tab_bo.winfo_reqheight()} > area {cv.winfo_height()}")
    h_closed = a.cand.winfo_height()
    print(f"  [ukur] tabel kandidat tab 5 tertutup: {h_closed} px")
    check("tab 5 (tertutup): tabel kandidat >= 200 px", h_closed >= 200, str(h_closed))
    a.bo_sweep.set("x=1:2")
    pump(root, 0.1)
    check("opsi aktif terlihat di judul terlipat", a.adv_info.get() == "1 opsi aktif", a.adv_info.get())
    a.adv.toggle()
    pump(root, 0.4)
    check("tab 5: bagian terbuka menampilkan isi", a.adv.is_open and a.adv.body.winfo_ismapped())
    print(f"  [ukur] tabel kandidat tab 5 terbuka: {a.cand.winfo_height()} px; isi {a.tab_bo.winfo_reqheight()} vs area {cv.winfo_height()}")
    shot(root, shots, f"t2_{tag}_tab5_opsi_terbuka")
    check("tab 5 terbuka: tanpa widget terpotong", not problems_in(root, tk, "tab 5 terbuka: "))
    a.adv.toggle()
    a.bo_sweep.set("format salah")
    a.bo_focus.set("otomatis")
    pump(root, 0.2)
    ok = a._check_bo_inputs()
    check("validasi gagal membuka bagian terlipat", (ok is False) and a.adv.is_open and bool(warned))
    a.bo_sweep.set("")
    a.adv.set_open(False)
    pump(root, 0.2)
    check("opsi aktif hilang setelah dikosongkan", a.adv_info.get() == "")
    tab(6)
    h7 = a.data_tab.tree.winfo_height()
    print(f"  [ukur] tabel tab 7: {h7} px")
    check("tab 7: tabel >= 180 px", h7 >= 180, str(h7))
    check("tab 7: menu Kolom ada", hasattr(a.data_tab, "col_menu"))
    a.data_tab.grp_vars["Gain"].set(False)
    a.data_tab._rebuild_columns()
    check("tab 7: menu Kolom mengubah kolom", not any(c.startswith("gain") for c in a.data_tab.tree["columns"]))
    a.data_tab.grp_vars["Gain"].set(True)
    a.data_tab._rebuild_columns()
    # lebar sempit: panel kanan turun
    root.geometry("800x600")
    pump(root, 0.5)
    tab(0)
    check("lebar sempit: panel kanan tab 1 turun ke bawah", a.rng_tree.winfo_rooty() > a.lhs_info.master.winfo_rooty() - 1 and
          a.rng_tree.winfo_rootx() - a.tab_lhs.winfo_rootx() < 400, str(a.rng_tree.winfo_rootx() - a.tab_lhs.winfo_rootx()))
    root.destroy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default=None)
    ap.add_argument("--size", default="1366x728@1.333")
    args = ap.parse_args()
    part_a()
    part_b(args.size, args.shot)
    print("\nSEMUA LULUS" if not FAILS else f"\n{len(FAILS)} GAGAL: {FAILS}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
