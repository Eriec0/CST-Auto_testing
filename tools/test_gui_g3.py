"""Uji GUI G3 (tanpa CST): tab Data (G3a), penampil zoom (G3b), grafik interaktif (G3c).

  py tools\\test_gui_g3.py        (butuh layar; membuka jendela GUI sebentar lalu menutupnya)
Di Linux tanpa layar:  xvfb-run -a python3 tools/test_gui_g3.py
"""
import os
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cstopt.gui import app as gapp  # noqa: E402
from cstopt.gui import dataview as dv  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  [OK]   " if cond else "  [GAGAL] ") + name + (f"  {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)


def wait_status(root, a):
    for _ in range(200):
        root.update()
        if a.status.get("run") and not a._status_busy:
            return
        root.after(50)
        root.update()


def main():
    root = tk.Tk()
    root.report_callback_exception = lambda *e: (print("  [GAGAL] galat callback Tk:", e[1]), FAILS.append("callback Tk"))
    a = gapp.App(root)
    wait_status(root, a)
    warns = []
    messagebox.showwarning = lambda title, msg, **k: warns.append((title, msg))
    messagebox.showinfo = lambda *a_, **k: None
    run = a.run_name()
    full = pd.read_csv(dv.table_path(run))
    t = a.data_tab

    print("G3a: tab Data")
    check("ada tab 7 Data", "7  Data" in [a.nb.tab(i, "text") for i in range(a.nb.index("end"))])
    check("run mengikuti desain", t.run_var.get() == run, t.run_var.get())
    check("semua baris tampil", len(t.tree.get_children()) == len(full), f"{len(t.tree.get_children())} vs {len(full)}")
    check("semua kolom tampil", len(t.tree["columns"]) == full.shape[1], f"{len(t.tree['columns'])} vs {full.shape[1]}")
    check("tiap kolom punya kelompok", all(dv.column_group(c) in dv.GROUPS for c in full.columns))
    check("kelompok mencakup semua kolom", sum(len([c for c in full.columns if dv.column_group(c) == g]) for g in dv.GROUPS) == full.shape[1])

    # nilai tidak dibulatkan: teks sel sama persis dengan teks di CSV
    raw = pd.read_csv(dv.table_path(run), dtype=str, keep_default_na=False)
    bad = [(i, c) for i in t.tree.get_children() for c in t.tree["columns"] if t.tree.set(i, c) != raw.loc[int(i), c]]
    check("semua sel tabel sama persis dengan teks CSV (tanpa pembulatan)", not bad, str(bad[:3]))
    long_cells = [c for c in raw.columns if raw[c].str.replace(r"\D", "", regex=True).str.len().max() > 6]
    check("ada sel dengan lebih dari 6 digit (bukti tidak dipotong)", len(long_cells) > 0, "tidak ada kolom panjang di data uji")

    # geser horizontal: langkah cukup besar
    import types as _ty
    a.nb.select(a.tab_data)
    root.update()
    root.update_idletasks()
    total = sum(int(t.tree.column(c, "width")) for c in t.tree["columns"])
    vis = t.tree.winfo_width()
    check("tabel lebih lebar dari area tampil (ada scroll horizontal)", total > vis, f"{total} vs {vis}")
    t.tree.xview_moveto(0)
    root.update()
    t._xscroll("scroll", "1", "units")
    root.update()
    moved = t.tree.xview()[0] * total
    check("satu klik panah menggeser sekitar X_STEP piksel", abs(moved - dv.X_STEP) < 0.15 * dv.X_STEP, f"{moved:.0f} px")
    t._on_shift_wheel(_ty.SimpleNamespace(delta=-120))
    root.update()
    moved2 = t.tree.xview()[0] * total
    check("Shift+roda ke bawah menggeser ke kanan", moved2 > moved + 0.8 * dv.X_STEP, f"{moved2:.0f}")
    t._on_shift_wheel(_ty.SimpleNamespace(delta=120))
    root.update()
    check("Shift+roda ke atas menggeser ke kiri", t.tree.xview()[0] * total < moved2 - 0.8 * dv.X_STEP)
    t._xscroll("moveto", "0.5")
    root.update()
    check("seret scrollbar (moveto) tetap berfungsi", abs(t.tree.xview()[0] - 0.5) < 0.02)
    t.tree.xview_moveto(0)

    # urut
    col = "bw_mhz" if "bw_mhz" in full.columns else full.columns[3]
    t.sort_by(col)
    first = [t.tree.set(i, col) for i in t.tree.get_children()]
    vals = [float(x) for x in first if x != ""]
    check("urut naik", vals == sorted(vals))
    t.sort_by(col)
    vals = [float(t.tree.set(i, col)) for i in t.tree.get_children() if t.tree.set(i, col) != ""]
    check("klik lagi: urut turun", vals == sorted(vals, reverse=True))
    check("nilai terbesar sama dengan CSV", abs(vals[0] - full[col].max()) < 1e-3 * max(1, abs(full[col].max())))

    # filter
    t.flt_var.set("bw_mhz>=150; fr_ghz>0")
    t.refresh_rows()
    exp = int(((full["bw_mhz"] >= 150) & (full["fr_ghz"] > 0)).sum())
    check("filter ekspresi", len(t.tree.get_children()) == exp, f"{len(t.tree.get_children())} vs {exp}")
    t.flt_var.set("kolom_ngawur>=1")
    n0 = len(warns)
    t.refresh_rows()
    check("kolom tak dikenal ditolak", len(warns) == n0 + 1 and "Kolom tidak ada" in warns[-1][1])
    t.flt_var.set("bw_mhz>>5")
    t.refresh_rows()
    check("format filter salah ditolak", len(warns) == n0 + 2)
    t.flt_var.set("")
    t.id_var.set("1, 3, 10-12")
    t.refresh_rows()
    got = sorted(int(full.loc[int(i), "sample_id"]) for i in t.tree.get_children())
    check("filter id sampel", got == [1, 3, 10, 11, 12], str(got))
    t.id_var.set("a-b")
    t.refresh_rows()
    check("id salah ditolak", len(warns) == n0 + 3)
    t.reset_filters()
    check("reset mengembalikan semua baris", len(t.tree.get_children()) == len(full))
    t.feas_var.set("feasible_wo_gain")
    t.refresh_rows()
    exp = int((full["feasible_wo_gain"] == 1).sum())
    check("tampilkan hanya feasible_wo_gain", len(t.tree.get_children()) == exp, f"{len(t.tree.get_children())} vs {exp}")
    t.reset_filters()

    # kelompok kolom
    t.grp_vars["Gain"].set(False)
    t._rebuild_columns()
    ng = len([c for c in full.columns if dv.column_group(c) == "Gain"])
    check("sembunyikan kelompok Gain", len(t.tree["columns"]) == full.shape[1] - ng and len(t.tree.get_children()) == len(full))
    t.grp_vars["Gain"].set(True)
    t._rebuild_columns()

    # sorotan dan filter "lolos tahap ini" (harus sama dengan status di atas tab)
    n_st = a.status.get("n_feasible", 0)
    tags_all = [t.tree.item(i, "tags") for i in t.tree.get_children()]
    check("jumlah baris hijau sama dengan status", sum(1 for g in tags_all if "feas" in g) == n_st, f"{sum(1 for g in tags_all if 'feas' in g)} vs {n_st}")
    t.feas_var.set("stage")
    t.refresh_rows()
    check("filter lolos tahap ini", len(t.tree.get_children()) == n_st)
    check("id yang tampil = feasible_ids status", sorted(int(full.loc[int(i), "sample_id"]) for i in t.tree.get_children()) == sorted(a.status.get("feasible_ids", [])))
    t.reset_filters()

    # ekspor
    out = os.path.join(tempfile.mkdtemp(), "tampil.csv")
    filedialog.asksaveasfilename = lambda **k: out
    t.flt_var.set("bw_mhz>=150")
    t.refresh_rows()
    t.export_csv()
    ex = pd.read_csv(out)
    check("ekspor memuat baris dan kolom tampilan", ex.shape == (len(t.tree.get_children()), len(t.tree["columns"])), str(ex.shape))
    exr = pd.read_csv(out, dtype=str, keep_default_na=False)
    check("ekspor mempertahankan teks asli", all(exr.iloc[k][c] == raw.loc[int(i), c] for k, i in enumerate(t.tree.get_children()) for c in exr.columns))
    t.reset_filters()

    # ganti run
    other = [r for r in dv.list_runs() if r != run]
    if other:
        t.run_var.set(other[0])
        t.load()
        o = pd.read_csv(dv.table_path(other[0]))
        check("ganti run memuat tabel run itu", len(t.tree.get_children()) == len(o), other[0])
        check("opsi lolos tahap dinonaktifkan untuk run lain", "disabled" in t.radios["stage"].state())

    print("G3b: penampil gambar dengan zoom (tab 6)")
    check("tab 6 memakai penampil zoom", a.zoom is not None)
    a.nb.select(a.tab_res)
    root.update()
    imgs = sorted(a.fig_paths.values())
    check("ada gambar untuk diuji", len(imgs) > 0)
    z = a.zoom
    if imgs:
        a.fig_var.set(os.path.basename(imgs[0]))
        a._draw_figure()
        root.update()
        from PIL import Image
        iw, ih = Image.open(imgs[0]).size
        cw, ch = z._size()
        s0 = z.scale
        check("awal muat jendela, tidak diperbesar melebihi 100%", abs(s0 - min(cw / iw, ch / ih, 1.0)) < 1e-9 and s0 <= 1.0, f"{s0}")
        z.zoom_by(2.0)
        check("perbesar 2x", abs(z.scale - min(s0 * 2, 16.0)) < 1e-9, f"{z.scale}")
        z.actual()
        check("100% = piksel asli", abs(z.scale - 1.0) < 1e-9)
        z.zoom_by(100)
        check("zoom dibatasi 16x", abs(z.scale - 16.0) < 1e-9)
        ox0, oy0 = z.ox, z.oy
        z.pan(-30, -20)
        check("geser mengubah posisi", (z.ox, z.oy) != (ox0, oy0))
        z.pan(100000, 100000)
        check("geser tidak keluar dari gambar", z.ox <= 0 and z.oy <= 0)
        z.zoom_to(1.0, 10, 10)
        iw1 = z.im.width * z.scale
        check("posisi di dalam batas setelah zoom", (z.ox <= 0 or iw1 <= z._size()[0]))
        z.canvas.event_generate("<Button-4>", x=50, y=50)
        root.update()
        check("roda mouse (Button-4) memperbesar", z.scale > 1.0, f"{z.scale}")
        z.fit()
        check("muat jendela mengembalikan skala awal", abs(z.scale - s0) < 1e-9)
        z.zoom_by(3.0)
        out = os.path.join(tempfile.mkdtemp(), "tampilan.png")
        filedialog.asksaveasfilename = lambda **k: out
        z.save_view()
        sv = Image.open(out)
        check("simpan tampilan menghasilkan PNG", sv.format == "PNG" and sv.width > 0, str(sv.size))
        # pilih gambar lain lalu kembali: zoom tidak direset bila gambar yang sama dipanggil ulang
        z.zoom_to(2.0)
        sc = z.scale
        a._draw_figure()
        check("menggambar ulang gambar yang sama tidak mereset zoom", abs(z.scale - sc) < 1e-9)
        if len(imgs) > 1:
            a.fig_var.set(os.path.basename(imgs[1]))
            a._draw_figure()
            check("ganti gambar memuat gambar baru", z.name == imgs[1])
        z.set_message("uji")
        check("pesan tanpa gambar tidak error", z.im is None)

    print("G3c: grafik interaktif")
    t.run_var.set(run)
    t.load()
    import types
    from cstopt.gui import plots as pl
    import numpy as np
    pf = pl.pareto_front([1, 2, 3, 4, 2.5], [4, 3.5, 1, 0.5, 3.6])
    check("pareto_front (maks, maks) benar", pf == [0, 4, 2, 3], str(pf))
    pf2 = pl.pareto_front([1, 2, 3], [3, 2, 1])
    check("pareto_front semua tak terdominasi", pf2 == [0, 1, 2], str(pf2))
    pf3 = pl.pareto_front([1, 2, 3], [1, 2, 3])
    check("pareto_front satu titik dominan", pf3 == [2], str(pf3))
    pf4 = pl.pareto_front([1, 2, 3], [3, 2, 1], max_x=False, max_y=False)
    check("pareto_front (min, min) benar", pf4 == [0, 1, 2], str(pf4))
    pf6 = pl.pareto_front([1, 2, 3], [1, 2, 3], max_x=False, max_y=False)
    check("pareto_front (min, min) satu titik dominan", pf6 == [0], str(pf6))
    pf5 = pl.pareto_front([1, np.nan, 3], [1, 5, 3])
    check("pareto_front mengabaikan NaN", 1 not in pf5, str(pf5))
    c = pl.read_s11(run, int(full["sample_id"].iloc[0]))
    check("read_s11 membaca kurva", c is not None and len(c[0]) > 100 and len(c[0]) == len(c[1]))
    check("read_s11 id tak ada -> None", pl.read_s11(run, 999999) is None)

    t.reset_filters()
    kids = list(t.tree.get_children())[:3]
    t.tree.selection_set(kids)
    root.update()
    exp_ids = sorted(int(full.loc[int(i), "sample_id"]) for i in kids)
    check("selected_ids sesuai baris terpilih", sorted(t.selected_ids()) == exp_ids)
    t.open_plot("s11")
    w = t.plot_win
    root.update()
    check("jendela grafik terbuka", w is not None and w.winfo_exists())
    n_lines = len(w.ax.lines)
    check("S11: 3 kurva + garis -10 dB", n_lines == 4 and w.curve_count == 3, f"{n_lines}, {getattr(w, 'curve_count', None)}")
    check("S11: sumbu berlabel", w.ax.get_xlabel().startswith("Frekuensi") and "S11" in w.ax.get_ylabel())
    w.ids_var.set("999999")
    w.draw_s11()
    check("S11: id tanpa berkas dilaporkan", "Tidak ada berkas kurva" in w.info_var.get())
    w.ids_var.set("x")
    n0 = len(warns)
    w.draw_s11()
    check("S11: id salah ditolak", len(warns) == n0 + 1)
    w.ids_var.set(", ".join(str(i) for i in range(1, 30)))
    w.draw_s11()
    check("S11: dibatasi 12 kurva", w.curve_count <= pl.MAX_CURVES and "hanya" in w.info_var.get(), w.info_var.get())

    w.draw_scatter()
    root.update()
    check("sebar: x dan y terisi default", w.xcol.get() != "" and w.ycol.get() != "")
    npts = len(w._pts[0])
    check("sebar: semua baris data digambar", npts == len(full.dropna(subset=[w.xcol.get(), w.ycol.get()])), f"{npts}")
    check("sebar: ada titik Pareto", w.n_front >= 1)
    xl0 = w.ax.get_xlim()
    ev = types.SimpleNamespace(inaxes=w.ax, xdata=float(np.mean(xl0)), ydata=float(np.mean(w.ax.get_ylim())), button="up")
    w._on_scroll(ev)
    xl1 = w.ax.get_xlim()
    check("roda mouse memperbesar sumbu", (xl1[1] - xl1[0]) < (xl0[1] - xl0[0]))
    ev.button = "down"
    w._on_scroll(ev)
    xl2 = w.ax.get_xlim()
    check("roda mouse ke arah sebaliknya memperkecil", (xl2[1] - xl2[0]) > (xl1[1] - xl1[0]))
    px, py = w.ax.transData.transform((w._pts[0][0], w._pts[1][0]))
    w.toolbar.mode = ""
    w._on_click(types.SimpleNamespace(inaxes=w.ax, x=px, y=py, button=1))
    check("klik titik menampilkan id sampel", getattr(w, "picked_id", None) == int(w._pts[2][0]) and w._ann is not None, str(getattr(w, "picked_id", None)))
    out = os.path.join(tempfile.mkdtemp(), "sebar.png")
    w.fig.savefig(out)
    from PIL import Image as _I
    check("grafik dapat disimpan sebagai PNG", _I.open(out).format == "PNG")
    # hanya tampilan tabel
    t.flt_var.set("bw_mhz>=150")
    t.refresh_rows()
    w.onlyview_var.set(True)
    w.draw_scatter()
    check("sebar hanya tampilan tabel", len(w._pts[0]) <= len(t.view) and len(w._pts[0]) > 0, f"{len(w._pts[0])} vs {len(t.view)}")
    t.reset_filters()
    # klik ganda baris -> S11
    t.tree.selection_set(kids[:1])
    t.open_plot("s11")
    check("buka ulang memakai jendela yang sama", t.plot_win is w)
    # tanpa baris terpilih
    t.tree.selection_set([])
    n_i = []
    messagebox.showinfo = lambda title, msg, **k: n_i.append(title)
    t.open_plot("s11")
    check("S11 tanpa baris terpilih memberi petunjuk", n_i == ["Grafik S11"])
    w.destroy()
    root.destroy()
    print()
    if FAILS:
        print(f"GAGAL: {len(FAILS)} uji: {FAILS}")
        sys.exit(1)
    print("SEMUA LULUS")


if __name__ == "__main__":
    main()
