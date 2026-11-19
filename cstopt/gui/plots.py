"""Grafik interaktif dari CSV (G3c): kurva S11 sampel terpilih, sebar dua kolom dengan garis Pareto,
dan koordinat paralel (satu garis per sampel, satu sumbu per kolom).

Kandidat BO terakhir (`samples/bo_candidates_report.csv`, termasuk batas `--sweep` bila ada) bisa ditumpuk
di grafik sebar dan koordinat paralel: titik/garis kandidat memakai PREDIKSI model (`pred_<kolom>`), bukan hasil
simulasi, dan diberi tanda tersendiri.

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
from cstopt.gui.layout import fit_window, make_flow

MAX_CURVES = 12
RL_LINE_DB = -10.0
CAND_FILE = "bo_candidates_report.csv"
PARALLEL_TARGETS = ("fr_ghz", "rl_min_db", "bw_mhz", "gain_fr_ieee_dbi")
PRESETS = ("Geometri + target", "Geometri", "Target")


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


def candidates_path(run):
    return os.path.join(paths.run_dir(run), "samples", CAND_FILE)


def load_candidates(run):
    """Kandidat BO terakhir (DataFrame) atau None bila berkas tidak ada, kosong, atau rusak."""
    p = candidates_path(run)
    if not os.path.isfile(p):
        return None
    try:
        d = pd.read_csv(p)
    except Exception:
        return None
    return d if len(d) else None


def candidate_values(cands, col):
    """(nilai, std, dari_prediksi) kandidat untuk kolom `col`; None bila kolom tidak ada di berkas kandidat.

    Kolom model (fr_ghz, bw_mhz, ...) memakai `pred_<col>` dan `std_<col>` (std None bila tidak ada);
    parameter geometri memakai nilainya langsung (std None)."""
    if cands is None:
        return None
    pc = f"pred_{col}"
    if pc in cands.columns:
        sc = f"std_{col}"
        std = cands[sc].to_numpy(float) if sc in cands.columns else None
        return cands[pc].to_numpy(float), std, True
    if col in cands.columns:
        return cands[col].to_numpy(float), None, False
    return None


def default_parallel_columns(df, preset="Geometri + target"):
    """Kolom bawaan koordinat paralel menurut preset, hanya kolom numerik yang ada di df."""
    from cstopt.gui.dataview import column_group
    num = numeric_columns(df)
    geo = [c for c in num if column_group(c) == "Geometri"]
    tgt = [c for c in PARALLEL_TARGETS if c in num]
    if preset == "Geometri":
        return geo
    if preset == "Target":
        return tgt
    return geo + tgt


def parse_columns(text, available):
    """Daftar kolom dari teks 'a, b, c'. ValueError bila ada yang tidak dikenal atau kurang dari 2 kolom."""
    cols = [c.strip() for c in str(text).replace(";", ",").split(",") if c.strip()]
    cols = list(dict.fromkeys(cols))
    bad = [c for c in cols if c not in available]
    if bad:
        raise ValueError("Kolom tidak ada atau bukan angka: " + ", ".join(bad))
    if len(cols) < 2:
        raise ValueError("Pilih minimal 2 kolom (pisahkan dengan koma).")
    return cols


def parallel_norm(values, lo=None, hi=None):
    """Normalisasi tiap kolom ke 0..1. values: (n, k). lo/hi (opsional, panjang k) memaksa rentang
    (dipakai agar kandidat dinormalisasi dengan rentang data). Kolom konstan -> 0,5. NaN tetap NaN."""
    v = np.asarray(values, float)
    lo = np.nanmin(v, axis=0) if lo is None else np.asarray(lo, float)
    hi = np.nanmax(v, axis=0) if hi is None else np.asarray(hi, float)
    span = hi - lo
    flat = ~(span > 0)
    out = (v - lo) / np.where(flat, 1.0, span)
    out[:, flat] = np.where(np.isnan(v[:, flat]), np.nan, 0.5)
    return out, lo, hi


class PlotWindow(tk.Toplevel):
    def __init__(self, data_tab):
        super().__init__(data_tab.parent)
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        from matplotlib.figure import Figure
        self.dt = data_tab
        self.title("Grafik interaktif")
        fit_window(self, 1120, 760, 640, 440)              # G4a: tidak melebihi layar
        self.ids_var = tk.StringVar()
        self.rl_var = tk.BooleanVar(value=True)
        self.xcol = tk.StringVar()
        self.ycol = tk.StringVar()
        self.xdir = tk.StringVar(value="maks")
        self.ydir = tk.StringVar(value="maks")
        self.pareto_var = tk.BooleanVar(value=True)
        self.onlyview_var = tk.BooleanVar(value=False)
        self.cand_var = tk.BooleanVar(value=True)           # tumpuk kandidat BO (prediksi) bila berkas ada
        self.preset_var = tk.StringVar(value=PRESETS[0])
        self.pcols_var = tk.StringVar()
        self.pcolor = tk.StringVar()
        self.pstage_var = tk.BooleanVar(value=True)
        self.psel_var = tk.BooleanVar(value=True)
        self.info_var = tk.StringVar(value="")
        self._pts = None                                   # (x, y, id) titik sebar yang tampil, untuk klik
        self._cand_pts = None                              # (x, y, id, sweep_bound atau None) kandidat di sebar
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
        make_flow(r1)

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
        ttk.Checkbutton(r2, text="kandidat BO (prediksi)", variable=self.cand_var).pack(side="left", padx=(8, 0))
        ttk.Button(r2, text="Gambar sebar", command=self.draw_scatter).pack(side="left", padx=8)
        make_flow(r2)

        r3 = ttk.Frame(self, padding=(8, 6, 8, 0))
        r3.pack(fill="x")
        ttk.Label(r3, text="Koordinat paralel: preset").pack(side="left")
        pcb = ttk.Combobox(r3, textvariable=self.preset_var, values=list(PRESETS), state="readonly", width=17)
        pcb.pack(side="left", padx=(4, 6))
        pcb.bind("<<ComboboxSelected>>", lambda ev: self.apply_preset())
        ttk.Label(r3, text="kolom").pack(side="left")
        pe = ttk.Entry(r3, textvariable=self.pcols_var, width=44)
        pe.pack(side="left", padx=(4, 6))
        pe.bind("<Return>", lambda ev: self.draw_parallel())
        ttk.Label(r3, text="warna").pack(side="left")
        self.pccb = ttk.Combobox(r3, textvariable=self.pcolor, state="readonly", width=16)
        self.pccb.pack(side="left", padx=(4, 6))
        ttk.Checkbutton(r3, text="sorot lolos tahap", variable=self.pstage_var).pack(side="left")
        ttk.Checkbutton(r3, text="sorot baris terpilih", variable=self.psel_var).pack(side="left", padx=(6, 0))
        ttk.Button(r3, text="Gambar koordinat paralel", command=self.draw_parallel).pack(side="left", padx=8)
        make_flow(r3)

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
            self.pccb.configure(values=cols)
            if self.pcolor.get() not in cols:
                self.pcolor.set("bw_mhz" if "bw_mhz" in cols else cols[-1])
            if not self.pcols_var.get().strip():
                self.apply_preset()

    def apply_preset(self):
        df = self.dt.df
        if df is None:
            return
        self.pcols_var.set(", ".join(default_parallel_columns(df, self.preset_var.get())))

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
        self._cand_pts = None
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
        cand_msg = self._overlay_candidates(ax, xc, yc)
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
        self.info_var.set(f"{len(d)} titik, {int(isst.sum())} lolos tahap ini, {len(front)} titik Pareto. "
                          f"Klik titik untuk melihat id sampel.{cand_msg}")

    def _overlay_candidates(self, ax, xc, yc):
        """Tumpuk kandidat BO terakhir (prediksi) di sebar. Mengembalikan kalimat status untuk bilah info."""
        self.n_cand = 0
        if not self.cand_var.get():
            return ""
        cands = load_candidates(self.dt.run_var.get())
        if cands is None:
            return " Tidak ada berkas kandidat BO untuk run ini (jalankan suggest dulu)."
        cx, cy = candidate_values(cands, xc), candidate_values(cands, yc)
        if cx is None or cy is None:
            miss = xc if cx is None else yc
            return f" Kandidat BO tidak punya kolom '{miss}', jadi tidak digambar."
        xv, xs, _ = cx
        yv, ys, _ = cy
        ids = cands["sample_id"].to_numpy() if "sample_id" in cands.columns else np.arange(len(cands))
        sweep = cands["sweep_bound"].to_numpy(float) if "sweep_bound" in cands.columns else None
        if xs is not None or ys is not None:
            ax.errorbar(xv, yv, xerr=xs, yerr=ys, fmt="none", ecolor="#e8a87c", elinewidth=0.8, alpha=0.8, zorder=5)
        if sweep is not None and not np.all(np.isnan(sweep)):
            sc = ax.scatter(xv, yv, s=70, c=sweep, cmap="plasma", marker="D", edgecolors="black", linewidths=0.7,
                            zorder=7, label="kandidat BO (prediksi)")
            self.fig.colorbar(sc, ax=ax, label="batas sweep")
        else:
            ax.scatter(xv, yv, s=70, color="#f59f00", marker="D", edgecolors="black", linewidths=0.7,
                       zorder=7, label="kandidat BO (prediksi)")
        for i in range(len(xv)):
            if np.isfinite(xv[i]) and np.isfinite(yv[i]):
                ax.annotate(str(int(ids[i])), (xv[i], yv[i]), xytext=(5, 5), textcoords="offset points", fontsize=7, zorder=8)
        self._cand_pts = (xv, yv, np.asarray(ids), sweep)
        self.n_cand = len(xv)
        tag = " (sapuan batas)" if sweep is not None and not np.all(np.isnan(sweep)) else ""
        return f" {len(xv)} kandidat BO{tag} digambar dari prediksi model, bukan hasil simulasi."

    def draw_parallel(self):
        df = self.dt.view if (self.onlyview_var.get() and self.dt.view is not None) else self.dt.df
        if df is None:
            messagebox.showinfo("Koordinat paralel", "Belum ada data. Pilih run di tab Data dulu.", parent=self)
            return
        try:
            cols = parse_columns(self.pcols_var.get(), numeric_columns(self.dt.df))
        except ValueError as e:
            messagebox.showwarning("Koordinat paralel", str(e), parent=self)
            return
        ccol = self.pcolor.get() if self.pcolor.get() in df.columns else cols[-1]
        need = list(dict.fromkeys(["sample_id"] + cols + [ccol]))
        d = df[[c for c in need if c in df.columns]].dropna(subset=cols + [ccol]).copy()
        if d.empty:
            messagebox.showinfo("Koordinat paralel", "Tidak ada baris tanpa nilai kosong untuk kolom yang dipilih.", parent=self)
            return
        import matplotlib
        self._reset_axes()
        ax = self.ax
        run = self.dt.run_var.get()
        full = self.dt.df
        lo, hi = full[cols].min().to_numpy(float), full[cols].max().to_numpy(float)   # rentang dari SELURUH data
        M, _, _ = parallel_norm(d[cols].to_numpy(float), lo, hi)
        cv = d[ccol].to_numpy(float)
        order = np.argsort(cv)
        cmap = matplotlib.colormaps["viridis"]
        vmin, vmax = float(np.nanmin(cv)), float(np.nanmax(cv))
        norm = matplotlib.colors.Normalize(vmin=vmin, vmax=vmax if vmax > vmin else vmin + 1.0)
        xs = np.arange(len(cols))
        for k in order:
            ax.plot(xs, M[k], color=cmap(norm(cv[k])), linewidth=0.8, alpha=0.55, zorder=2)
        sid = d["sample_id"].to_numpy() if "sample_id" in d else np.arange(len(d))
        n_stage = n_sel = 0
        stage = self.dt.stage_ids if run == self.dt._design_run else set()
        if self.pstage_var.get() and stage:
            for k in range(len(d)):
                if int(sid[k]) in stage:
                    ax.plot(xs, M[k], color="#2e9e4f", linewidth=1.6, alpha=0.95, zorder=4)
                    n_stage += 1
        sel = set(self.dt.selected_ids()) if self.psel_var.get() else set()
        for k in range(len(d)):
            if int(sid[k]) in sel:
                ax.plot(xs, M[k], color="#d9480f", linewidth=2.4, zorder=6)
                n_sel += 1
        cand_msg = self._parallel_candidates(ax, cols, lo, hi)
        for i, c in enumerate(cols):
            ax.axvline(i, color="#444444", linewidth=0.9, zorder=3)
            ax.text(i, 1.03, f"{hi[i]:.4g}", ha="center", va="bottom", fontsize=7, color="#444444")
            ax.text(i, -0.03, f"{lo[i]:.4g}", ha="center", va="top", fontsize=7, color="#444444")
        ax.set_xticks(xs)
        ax.set_xticklabels(cols, rotation=30 if len(cols) > 8 else 0, ha="right" if len(cols) > 8 else "center", fontsize=8)
        ax.set_yticks([])
        ax.set_ylim(-0.1, 1.1)
        ax.set_xlim(-0.3, len(cols) - 0.7)
        ax.set_title(f"Koordinat paralel, {run} (warna: {ccol})")
        sm = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap)
        self.fig.colorbar(sm, ax=ax, label=ccol, pad=0.02)
        self.fig.tight_layout()
        self.canvas.draw()
        self.toolbar.update()
        self.n_lines = len(d)
        self.n_parallel_stage, self.n_parallel_sel = n_stage, n_sel
        extra = f", {n_stage} lolos tahap (hijau)" if n_stage else ""
        extra += f", {n_sel} baris terpilih (merah)" if n_sel else ""
        self.info_var.set(f"{len(d)} garis, {len(cols)} sumbu{extra}. Tiap sumbu diskalakan min..maks seluruh data "
                          f"(angka di atas dan bawah sumbu).{cand_msg}")

    def _parallel_candidates(self, ax, cols, lo, hi):
        self.n_parallel_cand = 0
        if not self.cand_var.get():
            return ""
        cands = load_candidates(self.dt.run_var.get())
        if cands is None:
            return " Tidak ada berkas kandidat BO untuk run ini."
        vals, miss = [], []
        for c in cols:
            v = candidate_values(cands, c)
            if v is None:
                miss.append(c)
            else:
                vals.append(v[0])
        if miss:
            return f" Kandidat BO tidak digambar (kolom tanpa nilai kandidat: {', '.join(miss)})."
        C, _, _ = parallel_norm(np.column_stack(vals), lo, hi)
        xs = np.arange(len(cols))
        for k in range(len(C)):
            ax.plot(xs, C[k], color="#f59f00", linewidth=1.6, linestyle="--", marker="D", markersize=3.5, zorder=5,
                    label="kandidat BO (prediksi)" if k == 0 else None)
        ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.13))      # di bawah sumbu: tidak menutup angka rentang
        self.n_parallel_cand = len(C)
        return f" {len(C)} kandidat BO (garis putus-putus oranye) memakai prediksi model; nilai di luar rentang data tergambar di luar sumbu."

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
        cand = self._cand_pts
        if len(x) == 0 and cand is None:
            return
        best = None                                        # (jarak piksel, x, y, id, kandidat?, batas sweep)
        if len(x):
            pts = ev.inaxes.transData.transform(np.column_stack([x, y]))
            dist = np.hypot(pts[:, 0] - ev.x, pts[:, 1] - ev.y)
            k = int(np.argmin(dist))
            best = (float(dist[k]), x[k], y[k], int(sid[k]), False, None)
        if cand is not None and len(cand[0]):
            cp = ev.inaxes.transData.transform(np.column_stack([cand[0], cand[1]]))
            cd = np.hypot(cp[:, 0] - ev.x, cp[:, 1] - ev.y)
            cd = np.where(np.isfinite(cd), cd, np.inf)
            kc = int(np.argmin(cd))
            if best is None or cd[kc] <= best[0]:          # kandidat menang bila lebih dekat (tampil di atas)
                sw = None if cand[3] is None else float(cand[3][kc])
                best = (float(cd[kc]), cand[0][kc], cand[1][kc], int(cand[2][kc]), True, sw)
        if best is None or best[0] > 12:
            return
        dist_k, bx, by, bid, is_cand, bsw = best
        if self._ann is not None:
            try:
                self._ann.remove()
            except Exception:
                pass
        label = f"kandidat {bid} (prediksi)" if is_cand else f"id {bid}"
        if is_cand and bsw is not None and np.isfinite(bsw):
            label += f"\nbatas sweep {bsw:.4g}"
        self._ann = ev.inaxes.annotate(f"{label}\n({bx:.4g}, {by:.4g})", (bx, by), xytext=(12, 12),
                                       textcoords="offset points", fontsize=8,
                                       bbox=dict(boxstyle="round", fc="#fffbe6", ec="#999999"),
                                       arrowprops=dict(arrowstyle="-", color="#666666"), zorder=10)
        self.canvas.draw_idle()
        self.picked_id = bid
        self.picked_is_candidate = is_cand
        self.info_var.set(f"Titik dipilih: {'kandidat' if is_cand else 'sampel'} {bid}")
