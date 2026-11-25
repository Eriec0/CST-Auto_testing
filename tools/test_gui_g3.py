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
    test_g3d(root, a, t, w, full, run, warns)
    w.destroy()
    root.destroy()
    print()
    if FAILS:
        print(f"GAGAL: {len(FAILS)} uji: {FAILS}")
        sys.exit(1)
    print("SEMUA LULUS")


def test_g3d(root, a, t, w, full, run, warns):
    """Kandidat BO/sweep di grafik sebar dan koordinat paralel."""
    import shutil
    import types
    import numpy as np
    from cstopt.gui import plots as pl
    print("G3d: kandidat BO/sweep dan koordinat paralel")
    # --- fungsi murni
    M, lo, hi = pl.parallel_norm([[0, 10, 7], [5, 20, 7], [10, 30, 7]])
    check("parallel_norm: 0..1 per kolom", np.allclose(M[:, 0], [0, 0.5, 1]) and np.allclose(M[:, 1], [0, 0.5, 1]))
    check("parallel_norm: kolom konstan = 0,5", np.allclose(M[:, 2], 0.5))
    M2, _, _ = pl.parallel_norm([[np.nan, 1], [2, 3]])
    check("parallel_norm: NaN tetap NaN", np.isnan(M2[0, 0]) and not np.isnan(M2[1, 1]))
    M3, _, _ = pl.parallel_norm([[15.0]], lo=[0.0], hi=[10.0])
    check("parallel_norm: rentang dipaksa, nilai di luar rentang > 1", abs(M3[0, 0] - 1.5) < 1e-12)
    check("parse_columns benar", pl.parse_columns("Lp, bw_mhz", ["Lp", "bw_mhz", "x"]) == ["Lp", "bw_mhz"])
    for bad in ("Lp, nama_ngawur", "Lp", ""):
        try:
            pl.parse_columns(bad, ["Lp", "bw_mhz"])
            ok = False
        except ValueError:
            ok = True
        check(f"parse_columns menolak '{bad}'", ok)
    num = pl.numeric_columns(full)
    for pr in pl.PRESETS:
        cols = pl.default_parallel_columns(full, pr)
        check(f"preset '{pr}' hanya kolom numerik yang ada", len(cols) >= 2 and all(c in num for c in cols), str(cols))
    check("preset Target memuat bw_mhz", "bw_mhz" in pl.default_parallel_columns(full, "Target"))
    check("preset Geometri tanpa kolom target", not set(pl.default_parallel_columns(full, "Geometri")) & set(pl.PARALLEL_TARGETS))

    # --- berkas kandidat: cadangkan, ganti dengan data uji, pulihkan di akhir
    cpath = pl.candidates_path(run)
    bak = cpath + ".g3d_bak"
    had = os.path.isfile(cpath)
    if had:
        shutil.copy2(cpath, bak)
    try:
        if not had:
            print("  (tidak ada bo_candidates_report.csv untuk run ini; dibuat dari data uji)")
        os.makedirs(os.path.dirname(cpath), exist_ok=True)
        src = full.head(4).copy()
        cand = pd.DataFrame({"sample_id": [9001, 9002, 9003, 9004]})
        for c in ("Lp", "Wp", "LU", "WU", "gU", "PU", "LI", "LD", "WD", "gD", "PD"):
            if c in src.columns:
                cand[c] = src[c].to_numpy() * 1.01
        for c in ("fr_ghz", "rl_min_db", "bw_mhz", "gain_fr_ieee_dbi"):
            cand[f"pred_{c}"] = src[c].to_numpy() * 1.02
            cand[f"std_{c}"] = np.abs(src[c].to_numpy()) * 0.03
        cand.to_csv(cpath, index=False)
        lc = pl.load_candidates(run)
        check("load_candidates membaca berkas", lc is not None and len(lc) == 4)
        v = pl.candidate_values(lc, "bw_mhz")
        check("candidate_values: kolom model memakai pred_ dan std_", v is not None and v[2] and v[1] is not None and np.allclose(v[0], cand["pred_bw_mhz"]))
        v = pl.candidate_values(lc, "Lp")
        check("candidate_values: parameter memakai nilai langsung", v is not None and not v[2] and v[1] is None)
        check("candidate_values: kolom tak ada -> None", pl.candidate_values(lc, "kolom_ngawur") is None)
        check("candidate_values: tanpa kandidat -> None", pl.candidate_values(None, "bw_mhz") is None)

        # --- sebar dengan kandidat (tanpa sweep_bound)
        t.reset_filters()
        w.onlyview_var.set(False)
        w.cand_var.set(True)
        w.xcol.set("gain_fr_ieee_dbi")
        w.ycol.set("bw_mhz")
        w.draw_scatter()
        root.update()
        n_data = len(full.dropna(subset=["gain_fr_ieee_dbi", "bw_mhz"]))
        check("sebar+kandidat: titik data tetap lengkap", len(w._pts[0]) == n_data, f"{len(w._pts[0])} vs {n_data}")
        check("sebar+kandidat: 4 kandidat digambar", w.n_cand == 4 and w._cand_pts is not None and len(w._cand_pts[0]) == 4)
        check("sebar+kandidat: garis Pareto hanya dari data (bukan kandidat)", w.n_front >= 1)
        check("sebar+kandidat: info menyebut prediksi", "prediksi" in w.info_var.get(), w.info_var.get())
        check("sebar+kandidat: tanpa sweep tidak ada colorbar", len(w.fig.axes) == 1, str(len(w.fig.axes)))
        cx, cy = w._cand_pts[0][1], w._cand_pts[1][1]
        px, py = w.ax.transData.transform((cx, cy))
        w.toolbar.mode = ""
        w._on_click(types.SimpleNamespace(inaxes=w.ax, x=px, y=py, button=1))
        check("klik kandidat menandai kandidat dan id-nya", getattr(w, "picked_is_candidate", False) and w.picked_id == 9002, str(getattr(w, "picked_id", None)))
        check("klik kandidat: label bertuliskan kandidat", "kandidat 9002" in w._ann.get_text(), w._ann.get_text())
        px, py = w.ax.transData.transform((w._pts[0][0], w._pts[1][0]))
        if not np.isclose(w._pts[0][0], w._cand_pts[0]).any():
            w._on_click(types.SimpleNamespace(inaxes=w.ax, x=px, y=py, button=1))
            check("klik titik data tetap memberi id sampel (bukan kandidat)", not w.picked_is_candidate and w.picked_id == int(w._pts[2][0]), str(w.picked_id))

        # --- dengan sweep_bound
        cand["sweep_bound"] = [4.0, 4.5, 5.0, 5.4]
        cand.to_csv(cpath, index=False)
        w.draw_scatter()
        root.update()
        check("sebar+sweep: ada colorbar batas sweep", len(w.fig.axes) == 2 and w.fig.axes[1].get_ylabel() == "batas sweep", str([x.get_ylabel() for x in w.fig.axes]))
        check("sebar+sweep: info menyebut sapuan batas", "sapuan batas" in w.info_var.get(), w.info_var.get())
        cx, cy = w._cand_pts[0][2], w._cand_pts[1][2]
        px, py = w.ax.transData.transform((cx, cy))
        w._on_click(types.SimpleNamespace(inaxes=w.ax, x=px, y=py, button=1))
        check("klik kandidat sweep menampilkan batas sweep", w.picked_id == 9003 and "batas sweep 5" in w._ann.get_text(), w._ann.get_text())

        # --- opsi dan kasus tepi
        w.cand_var.set(False)
        w.draw_scatter()
        check("kandidat dimatikan: tidak digambar", w.n_cand == 0 and w._cand_pts is None)
        w.cand_var.set(True)
        miss_cols = [c for c in num if c not in cand.columns and f"pred_{c}" not in cand.columns]
        if miss_cols:
            w.xcol.set(miss_cols[0])
            w.draw_scatter()
            check("kolom tanpa nilai kandidat: pesan jelas, kandidat tidak digambar", w._cand_pts is None and "tidak punya kolom" in w.info_var.get(), w.info_var.get())
            w.xcol.set("gain_fr_ieee_dbi")
        w.draw_scatter()
        os.replace(cpath, cpath + ".tmp")
        w.draw_scatter()
        check("tanpa berkas kandidat: pesan jelas, sebar tetap jalan", w._cand_pts is None and "Tidak ada berkas kandidat" in w.info_var.get() and len(w._pts[0]) == n_data)
        os.replace(cpath + ".tmp", cpath)
        with open(cpath, "w", encoding="utf-8") as f:
            f.write("rusak,,,\n\"")
        w.draw_scatter()
        check("berkas kandidat rusak tidak membuat galat", len(w._pts[0]) == n_data)
        cand.drop(columns=["sweep_bound"]).to_csv(cpath, index=False)

        # --- koordinat paralel
        print("  koordinat paralel")
        t.reset_filters()
        w.onlyview_var.set(False)
        t.tree.selection_set([])
        w.preset_var.set("Geometri + target")
        w.apply_preset()
        cols = pl.parse_columns(w.pcols_var.get(), num)
        check("preset mengisi kolom", len(cols) >= 5, str(cols))
        w.draw_parallel()
        root.update()
        d_ok = full.dropna(subset=cols + [w.pcolor.get()])
        check("paralel: satu garis per sampel", w.n_lines == len(d_ok), f"{w.n_lines} vs {len(d_ok)}")
        check("paralel: satu sumbu per kolom", len(w.ax.get_xticks()) == len(cols))
        check("paralel: label sumbu = nama kolom", [x.get_text() for x in w.ax.get_xticklabels()] == cols)
        check("paralel: kandidat digambar (garis putus-putus)", w.n_parallel_cand == 4, str(w.n_parallel_cand))
        n_expected = len(d_ok) + len(cols) + 4          # garis data + sumbu vertikal (axvline) + kandidat
        check("paralel: jumlah garis di sumbu masuk akal", len(w.ax.lines) >= len(d_ok) + 4, f"{len(w.ax.lines)} vs {n_expected}")
        stage = t.stage_ids if run == t._design_run else set()
        exp_st = int(d_ok["sample_id"].isin(stage).sum()) if stage else 0
        check("paralel: jumlah garis hijau = lolos tahap", w.n_parallel_stage == exp_st, f"{w.n_parallel_stage} vs {exp_st}")
        w.pstage_var.set(False)
        w.draw_parallel()
        check("paralel: sorot tahap bisa dimatikan", w.n_parallel_stage == 0)
        w.pstage_var.set(True)
        kids = list(t.tree.get_children())[:2]
        t.tree.selection_set(kids)
        root.update()
        w.draw_parallel()
        check("paralel: baris terpilih di tabel disorot", w.n_parallel_sel == 2, str(w.n_parallel_sel))
        t.tree.selection_set([])
        w.cand_var.set(False)
        w.draw_parallel()
        check("paralel: kandidat bisa dimatikan", w.n_parallel_cand == 0)
        w.cand_var.set(True)
        # kolom custom
        w.pcols_var.set("Lp, bw_mhz")
        w.draw_parallel()
        check("paralel: kolom kustom 2 sumbu", len(w.ax.get_xticks()) == 2)
        w.pcols_var.set("Lp, kolom_ngawur")
        n0 = len(warns)
        w.draw_parallel()
        check("paralel: kolom tak dikenal ditolak", len(warns) == n0 + 1 and "Kolom tidak ada" in warns[-1][1])
        w.pcols_var.set("Lp")
        n0 = len(warns)
        w.draw_parallel()
        check("paralel: kurang dari 2 kolom ditolak", len(warns) == n0 + 1)
        if miss_cols:
            w.pcols_var.set(f"Lp, {miss_cols[0]}")
            w.draw_parallel()
            check("paralel: kolom tanpa nilai kandidat -> kandidat tidak digambar, ada pesan", w.n_parallel_cand == 0 and "tanpa nilai kandidat" in w.info_var.get(), w.info_var.get())
        # filter tabel
        w.preset_var.set("Target")
        w.apply_preset()
        t.flt_var.set("bw_mhz>=150")
        t.refresh_rows()
        w.onlyview_var.set(True)
        w.draw_parallel()
        check("paralel: hanya baris tampilan tabel", 0 < w.n_lines <= len(t.view), f"{w.n_lines} vs {len(t.view)}")
        t.reset_filters()
        w.onlyview_var.set(False)
        out = os.path.join(tempfile.mkdtemp(), "paralel.png")
        w.fig.savefig(out)
        from PIL import Image as _I
        check("paralel: dapat disimpan sebagai PNG", _I.open(out).format == "PNG")
        # klik di mode paralel tidak error
        w._on_click(types.SimpleNamespace(inaxes=w.ax, x=10, y=10, button=1))
        check("paralel: klik tidak menimbulkan galat", True)
        # tombol di tab Data
        w.n_lines = -1
        t.open_plot("parallel")
        check("tab Data: tombol koordinat paralel menggambar", w.n_lines > 0, str(w.n_lines))
        # sebar masih jalan setelah paralel (axes direset, colorbar hilang)
        w.draw_scatter()
        check("sebar setelah paralel: sumbu bersih", len(w._pts[0]) == n_data and len(w.fig.axes) == 1, str(len(w.fig.axes)))
    finally:
        for f in (cpath + ".tmp",):
            if os.path.isfile(f):
                os.remove(f)
        if had:
            shutil.copy2(bak, cpath)
            os.remove(bak)
        elif os.path.isfile(cpath):
            os.remove(cpath)


if __name__ == "__main__":
    main()
