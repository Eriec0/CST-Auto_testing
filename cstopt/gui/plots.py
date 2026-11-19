"""Grafik interaktif dari CSV (G3c): kurva S11 sampel terpilih, sebar dua kolom dengan garis Pareto.

Jendela memakai matplotlib dengan toolbar standar: zoom kotak, geser, kembali ke awal, simpan PNG.
Tambahan: roda mouse memperbesar di posisi kursor, klik pada titik sebar menampilkan id sampelnya.
Karena digambar ulang dari data (bukan PNG), zoom tetap tajam pada berapa pun pembesaran.
Fungsi murni di bagian atas (tanpa Tk dan tanpa matplotlib) bisa diuji tanpa layar.
"""
import os
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
import pandas as pd

from cstopt import paths
from cstopt.gui.dataview import parse_ids

MAX_CURVES = 12
RL_LINE_DB = -10.0


def curve_path(run, sample_id):
    return os.path.join(paths.run_dir(run), "curves", f"s11_sample{int(sample_id)}.csv")


def read_s11(run, sample_id):
    """(freq_ghz, s11_db) sebagai array numpy, atau None bila berkas kurva tidak ada atau rusak."""
    p = curve_path(run, sample_id)
    if not os.path.isfile(p):
        return None
    try:
        d = pd.read_csv(p)
        return d["freq_ghz"].to_numpy(float), d["s11_db"].to_numpy(float)
    except Exception:
        return None


def pareto_front(xs, ys, max_x=True, max_y=True):
    """Indeks titik non-dominated (urut naik menurut x). NaN diabaikan."""
    x = np.asarray(xs, float) * (1 if max_x else -1)
    y = np.asarray(ys, float) * (1 if max_y else -1)
    ok = np.where(~(np.isnan(x) | np.isnan(y)))[0]
    order = ok[np.lexsort((-y[ok], -x[ok]))]            # x turun, lalu y turun
    keep, best = [], -np.inf
    for i in order:
        if y[i] > best:
            keep.append(int(i))
            best = y[i]
    keep.sort(key=lambda i: float(np.asarray(xs, float)[i]))
    return keep


def numeric_columns(df):
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c not in ("run_id",)]


class PlotWindow(tk.Toplevel):
    def __init__(self, data_tab):
        super().__init__(data_tab.parent)
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        from matplotlib.figure import Figure
        self.dt = data_tab
        self.title("Grafik interaktif")
        self.geometry("1120x760")
        self.minsize(720, 520)
        self.ids_var = tk.StringVar()
        self.rl_var = tk.BooleanVar(value=True)
        self.xcol = tk.StringVar()
        self.ycol = tk.StringVar()
        self.xdir = tk.StringVar(value="maks")
        self.ydir = tk.StringVar(value="maks")
        self.pareto_var = tk.BooleanVar(value=True)
        self.onlyview_var = tk.BooleanVar(value=False)
        self.info_var = tk.StringVar(value="")
        self._pts = None                                   # (x, y, id) titik sebar yang tampil, untuk klik
        self._ann = None

        r1 = ttk.Frame(self, padding=(8, 8, 8, 0))
        r1.pack(fill="x")
        ttk.Label(r1, text="Kurva S11, sampel (id):").pack(side="left")
        e = ttk.Entry(r1, textvariable=self.ids_var, width=24)
        e.pack(side="left", padx=(4, 6))
        e.bind("<Return>", lambda ev: self.draw_s11())
        ttk.Checkbutton(r1, text="garis -10 dB", variable=self.rl_var).pack(side="left")
        ttk.Button(r1, text="Gambar S11", command=self.draw_s11).pack(side="left", padx=6)
        ttk.Button(r1, text="Pakai baris terpilih di tabel", command=self.use_selection).pack(side="left")

        r2 = ttk.Frame(self, padding=(8, 6, 8, 0))
        r2.pack(fill="x")
        ttk.Label(r2, text="Sebar: x").pack(side="left")
        self.xcb = ttk.Combobox(r2, textvariable=self.xcol, state="readonly", width=16)
        self.xcb.pack(side="left", padx=(4, 2))
        ttk.Combobox(r2, textvariable=self.xdir, values=["maks", "min"], state="readonly", width=5).pack(side="left")
        ttk.Label(r2, text="  y").pack(side="left")
        self.ycb = ttk.Combobox(r2, textvariable=self.ycol, state="readonly", width=16)
        self.ycb.pack(side="left", padx=(4, 2))
        ttk.Combobox(r2, textvariable=self.ydir, values=["maks", "min"], state="readonly", width=5).pack(side="left")
        ttk.Checkbutton(r2, text="garis Pareto", variable=self.pareto_var).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(r2, text="hanya baris tampilan tabel", variable=self.onlyview_var).pack(side="left", padx=(8, 0))
        ttk.Button(r2, text="Gambar sebar", command=self.draw_scatter).pack(side="left", padx=8)

        ttk.Label(self, textvariable=self.info_var, foreground="#555", padding=(10, 4, 8, 0)).pack(fill="x")
        self.fig = Figure(figsize=(9, 5.6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        bar = ttk.Frame(self)
        self.toolbar = NavigationToolbar2Tk(self.canvas, bar, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side="left", fill="x")
        bar.pack(side="bottom", fill="x", padx=8, pady=(0, 6))
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True, padx=8, pady=6)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.refresh_columns()

    # ------------------------------------------------------------------ data dari tab
    def refresh_columns(self):
        df = self.dt.df
        cols = numeric_columns(df) if df is not None else []
        self.xcb.configure(values=cols)
        self.ycb.configure(values=cols)
        if cols:
            if self.xcol.get() not in cols:
                self.xcol.set("gain_fr_ieee_dbi" if "gain_fr_ieee_dbi" in cols else cols[0])
            if self.ycol.get() not in cols:
                self.ycol.set("bw_mhz" if "bw_mhz" in cols else cols[-1])

    def use_selection(self):
        ids = self.dt.selected_ids()
        if not ids:
            messagebox.showinfo("Kurva S11", "Belum ada baris terpilih di tabel (Ctrl atau Shift untuk memilih banyak).", parent=self)
            return
        self.ids_var.set(", ".join(str(i) for i in ids[:MAX_CURVES]))
        self.draw_s11()

    # ------------------------------------------------------------------ menggambar
    def _reset_axes(self):
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self._pts = None
        self._ann = None
        self.toolbar.update()                             # kosongkan riwayat zoom

    def draw_s11(self):
        run = self.dt.run_var.get()
        try:
            ids = parse_ids(self.ids_var.get())
        except ValueError as e:
            messagebox.showwarning("Kurva S11", str(e), parent=self)
            return
        if not ids:
            messagebox.showinfo("Kurva S11", "Isi id sampel, atau pilih baris di tabel lalu tekan Pakai baris terpilih.", parent=self)
            return
        ids = sorted(ids)
        extra = ""
        if len(ids) > MAX_CURVES:
            extra = f" (hanya {MAX_CURVES} pertama dari {len(ids)} yang digambar)"
            ids = ids[:MAX_CURVES]
        self._reset_axes()
        ax, missing, n = self.ax, [], 0
        for i in ids:
            c = read_s11(run, i)
            if c is None:
                missing.append(i)
                continue
            ax.plot(c[0], c[1], linewidth=1.4, label=f"sampel {i}")
            n += 1
        if self.rl_var.get():
            ax.axhline(RL_LINE_DB, color="#888888", linestyle="--", linewidth=1)
        ax.set_xlabel("Frekuensi (GHz)")
        ax.set_ylabel("S11 (dB)")
        ax.set_title(f"Kurva S11, {run}")
        ax.grid(True, alpha=0.3)
        if n:
            ax.legend(fontsize=8, ncol=2 if n > 6 else 1)
        self.fig.tight_layout()
        self.canvas.draw()
        self.toolbar.update()
        self.curve_count = n
        msg = f"{n} kurva digambar{extra}."
        if missing:
            msg += f" Tidak ada berkas kurva untuk id: {', '.join(map(str, missing))}."
        self.info_var.set(msg)

    def draw_scatter(self):
        df = self.dt.view if (self.onlyview_var.get() and self.dt.view is not None) else self.dt.df
        if df is None or not self.xcol.get() or not self.ycol.get():
            messagebox.showinfo("Sebar", "Belum ada data. Pilih run di tab Data dulu.", parent=self)
            return
        xc, yc = self.xcol.get(), self.ycol.get()
        d = df[[c for c in dict.fromkeys(["sample_id", xc, yc]) if c in df.columns]].copy()
        d = d.dropna(subset=[xc, yc])
        stage = self.dt.stage_ids if self.dt.run_var.get() == self.dt._design_run else set()
        self._reset_axes()
        ax = self.ax
        sid = d["sample_id"].to_numpy() if "sample_id" in d else np.arange(len(d))
        x, y = d[xc].to_numpy(float), d[yc].to_numpy(float)
        isst = np.array([int(i) in stage for i in sid]) if stage else np.zeros(len(d), bool)
        ax.scatter(x[~isst], y[~isst], s=22, color="#9aa5b1", label="lainnya", zorder=2)
        if isst.any():
            ax.scatter(x[isst], y[isst], s=26, color="#2e9e4f", label="lolos tahap ini", zorder=3)
        front = []
        if self.pareto_var.get() and len(d):
            front = pareto_front(x, y, self.xdir.get() == "maks", self.ydir.get() == "maks")
            if front:
                ax.step(x[front], y[front], where="post", color="#d9480f", linewidth=1.3, zorder=4, label="Pareto")
                ax.scatter(x[front], y[front], s=40, facecolors="none", edgecolors="#d9480f", zorder=5)
        ax.set_xlabel(xc)
        ax.set_ylabel(yc)
        ax.set_title(f"{yc} terhadap {xc}, {self.dt.run_var.get()}")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        self.fig.tight_layout()
        self.canvas.draw()
        self.toolbar.update()
        self._pts = (x, y, np.asarray(sid))
        self.n_front = len(front)
        self.info_var.set(f"{len(d)} titik, {int(isst.sum())} lolos tahap ini, {len(front)} titik Pareto. Klik titik untuk melihat id sampel.")

    # ------------------------------------------------------------------ interaksi
    def _on_scroll(self, ev):
        ax = ev.inaxes
        if ax is None or ev.xdata is None or ev.ydata is None:
            return
        f = 1 / 1.25 if ev.button == "up" else 1.25
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        ax.set_xlim(ev.xdata - (ev.xdata - x0) * f, ev.xdata + (x1 - ev.xdata) * f)
        ax.set_ylim(ev.ydata - (ev.ydata - y0) * f, ev.ydata + (y1 - ev.ydata) * f)
        self.canvas.draw_idle()

    def _on_click(self, ev):
        if ev.inaxes is None or self._pts is None or ev.button != 1 or str(self.toolbar.mode):
            return                                         # abaikan saat mode zoom atau geser toolbar aktif
        x, y, sid = self._pts
        if len(x) == 0:
            return
        pts = ev.inaxes.transData.transform(np.column_stack([x, y]))
        dist = np.hypot(pts[:, 0] - ev.x, pts[:, 1] - ev.y)
        k = int(np.argmin(dist))
        if dist[k] > 12:
            return
        if self._ann is not None:
            try:
                self._ann.remove()
            except Exception:
                pass
        self._ann = ev.inaxes.annotate(f"id {int(sid[k])}\n({x[k]:.4g}, {y[k]:.4g})", (x[k], y[k]), xytext=(12, 12),
                                       textcoords="offset points", fontsize=8,
                                       bbox=dict(boxstyle="round", fc="#fffbe6", ec="#999999"),
                                       arrowprops=dict(arrowstyle="-", color="#666666"), zorder=10)
        self.canvas.draw_idle()
        self.picked_id = int(sid[k])
        self.info_var.set(f"Titik dipilih: sampel {int(sid[k])}")
