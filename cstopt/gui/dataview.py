"""Tab 7 Data: tampilkan SEMUA baris dan SEMUA kolom batch_lhs.csv satu run.

Fitur: pilihan run, urut dengan klik header, filter (feasible, id sampel, ekspresi kolom),
sorotan feasible, pilihan kelompok kolom, ekspor CSV dari tampilan saat ini.
Fungsi murni (tanpa Tk) ada di bagian atas supaya bisa diuji tanpa layar.
"""
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd

from cstopt import paths
from cstopt.gui.layout import make_flow

OPS = (">=", "<=", "==", "!=", ">", "<")
X_STEP = 90                                            # piksel per klik panah scrollbar atau per notch roda (Shift+roda)
GROUPS = ("Identitas", "Geometri", "S11", "Efisiensi", "Gain", "Status")
_IDENT = {"sample_id", "run_id", "timestamp"}
_S11 = {"fr_ghz", "rl_min_db", "vswr", "bw_mhz", "band_cover_pct", "s11_at_f0_db", "fr_edge_flag"}
_EFF = {"f_mon_fr_ghz", "n_eff_points"}


def column_group(col):
    """Kelompok kolom. Kolom yang tidak dikenal dianggap parameter geometri desain."""
    if col in _IDENT:
        return "Identitas"
    if col in _S11:
        return "S11"
    if col.startswith("eta") or col in _EFF:
        return "Efisiensi"
    if col.startswith(("d_", "theta", "gain")):
        return "Gain"
    if col.startswith("feasible"):
        return "Status"
    return "Geometri"


def list_runs():
    """Nama run yang punya batch_lhs.csv di folder data."""
    out = []
    if os.path.isdir(paths.DATA_DIR):
        for n in sorted(os.listdir(paths.DATA_DIR)):
            if os.path.isfile(os.path.join(paths.DATA_DIR, n, "batch_lhs.csv")):
                out.append(n)
    return out


def table_path(run):
    return os.path.join(paths.run_dir(run), "batch_lhs.csv")


def load_table(run):
    return pd.read_csv(table_path(run))


def load_raw(run):
    """Teks asli tiap sel batch_lhs.csv (tanpa konversi angka) supaya tampilan dan ekspor tidak dibulatkan."""
    return pd.read_csv(table_path(run), dtype=str, keep_default_na=False)


def parse_filters(text, columns):
    """'bw_mhz>=150; gain_fr_ieee_dbi>=4.5' -> [(kolom, op, nilai)]. ValueError bila salah."""
    out = []
    for part in re.split(r"[;\n]", text or ""):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^([A-Za-z_]\w*)\s*(>=|<=|==|!=|>|<)\s*(\S+)$", part)
        if not m:
            raise ValueError(f"Format filter salah: '{part}'. Contoh: bw_mhz>=150")
        col, op, val = m.groups()
        if col not in columns:
            raise ValueError(f"Kolom tidak ada: {col}")
        try:
            out.append((col, op, float(val)))
        except ValueError:
            raise ValueError(f"Nilai bukan angka: '{val}' pada filter '{part}'")
    return out


def parse_ids(text):
    """'1, 5, 10-20' -> himpunan id (set int). Kosong -> None. ValueError bila salah."""
    text = (text or "").strip()
    if not text:
        return None
    ids = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d+)\s*-\s*(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                raise ValueError(f"Rentang id terbalik: '{part}'")
            ids.update(range(a, b + 1))
        elif part.isdigit():
            ids.add(int(part))
        else:
            raise ValueError(f"Id sampel salah: '{part}'. Contoh: 1, 5, 10-20")
    return ids


def apply_filters(df, filters=(), feas=None, ids=None, stage_ids=None):
    """Kembalikan baris yang lolos semua syarat (DataFrame, indeks asli dipertahankan).

    feas="stage" memakai stage_ids (sample_id yang lolos constraint tahap BO saat ini, dari status)."""
    mask = pd.Series(True, index=df.index)
    ops = {">=": lambda s, v: s >= v, "<=": lambda s, v: s <= v, "==": lambda s, v: s == v,
           "!=": lambda s, v: s != v, ">": lambda s, v: s > v, "<": lambda s, v: s < v}
    for col, op, val in filters:
        mask &= ops[op](pd.to_numeric(df[col], errors="coerce"), val)
    if feas == "stage":
        mask &= df["sample_id"].isin(stage_ids or ())
    elif feas and feas in df.columns:
        mask &= pd.to_numeric(df[feas], errors="coerce") == 1
    if ids is not None and "sample_id" in df.columns:
        mask &= df["sample_id"].isin(ids)
    return df[mask]


def fmt(v):
    if v != v:                                          # NaN
        return ""
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


class DataTab:
    def __init__(self, parent, app):
        self.parent, self.app = parent, app
        self.df = None
        self.raw = None
        self.view = None
        self.cols = []
        self.sort_col, self.sort_desc = None, False
        self._mtime = None
        self._synced = None
        self._design_run = None
        self.plot_win = None
        self.stage_ids = set()
        self.run_var = tk.StringVar()
        self.feas_var = tk.StringVar(value="semua")
        self.id_var = tk.StringVar()
        self.flt_var = tk.StringVar()
        self.info_var = tk.StringVar(value="")
        self.grp_vars = {g: tk.BooleanVar(value=True) for g in GROUPS}
        self._build()

    # ------------------------------------------------------------------ tata letak
    def _build(self):
        t = self.parent
        t.columnconfigure(0, weight=1)
        t.rowconfigure(3, weight=1)
        r0 = ttk.Frame(t)
        r0.grid(row=0, column=0, sticky="ew")
        ttk.Label(r0, text="Run:").pack(side="left")
        self.run_cb = ttk.Combobox(r0, textvariable=self.run_var, values=[], state="readonly", width=34)
        self.run_cb.pack(side="left", padx=(4, 8))
        self.run_cb.bind("<<ComboboxSelected>>", lambda e: self.load())
        ttk.Button(r0, text="Muat ulang", command=self.load).pack(side="left")
        ttk.Button(r0, text="Ekspor CSV (tampilan ini)", command=self.export_csv).pack(side="left", padx=8)
        ttk.Button(r0, text="Grafik S11 (baris terpilih)", command=lambda: self.open_plot("s11")).pack(side="left")
        ttk.Button(r0, text="Grafik sebar dan Pareto", command=lambda: self.open_plot("scatter")).pack(side="left", padx=8)
        make_flow(r0)

        r1 = ttk.Frame(t)
        r1.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(r1, text="Tampilkan:").pack(side="left")
        self.radios = {}
        for val, txt in (("semua", "semua"), ("stage", "lolos tahap ini"), ("feasible_wo_gain", "feasible_wo_gain"), ("feasible_all", "feasible_all")):
            rb = ttk.Radiobutton(r1, text=txt, value=val, variable=self.feas_var, command=self.refresh_rows)
            rb.pack(side="left", padx=(4, 0))
            self.radios[val] = rb
        ttk.Label(r1, text="  id").pack(side="left")
        e1 = ttk.Entry(r1, textvariable=self.id_var, width=10)
        e1.pack(side="left", padx=(4, 6))
        ttk.Label(r1, text="filter").pack(side="left")
        e2 = ttk.Entry(r1, textvariable=self.flt_var, width=24)
        e2.pack(side="left", padx=(4, 6))
        for e in (e1, e2):
            e.bind("<Return>", lambda ev: self.refresh_rows())
        ttk.Button(r1, text="Terapkan", command=self.refresh_rows).pack(side="left")
        ttk.Button(r1, text="Reset", command=self.reset_filters).pack(side="left", padx=4)
        make_flow(r1)

        r2 = ttk.Frame(t)
        r2.grid(row=2, column=0, sticky="ew", pady=(6, 6))
        ttk.Label(r2, text="Kolom:").pack(side="left")
        for g in GROUPS:
            ttk.Checkbutton(r2, text=g, variable=self.grp_vars[g], command=self._rebuild_columns).pack(side="left", padx=(6, 0))
        make_flow(r2)

        box = ttk.Frame(t)
        box.grid(row=3, column=0, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(box, show="headings", selectmode="extended")
        ys = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(box, orient="horizontal", command=self.tree.xview)
        xs.configure(command=self._xscroll)                 # langkah geser horizontal lebih besar dari bawaan (1 piksel)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        self._fix_tag_colors()
        self.tree.tag_configure("feas", background="#d8f0d8")
        self.tree.tag_configure("edge", foreground="#b45f06")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_info())
        self.tree.bind("<Double-1>", self._on_double)
        self.tree.bind("<Shift-MouseWheel>", self._on_shift_wheel)          # Windows dan macOS
        self.tree.bind("<Shift-Button-4>", lambda e: self._xscroll("scroll", -1, "units") or "break")   # Linux
        self.tree.bind("<Shift-Button-5>", lambda e: self._xscroll("scroll", 1, "units") or "break")

        ttk.Label(t, textvariable=self.info_var).grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Label(t, foreground="#666", text="Hijau: lolos constraint tahap BO saat ini (hanya run desain, sama dengan status di atas). Teks oranye: fr_edge_flag. "
                  "Contoh filter: bw_mhz>=150; gain_fr_ieee_dbi>=4.5 (pisahkan dengan ;)").grid(row=5, column=0, sticky="w")

    def _xscroll(self, *args):
        """Perintah scrollbar horizontal: klik panah menggeser X_STEP piksel, seret dan klik palung tetap bawaan."""
        if args and args[0] == "scroll" and args[2] == "units":
            self.tree.xview_scroll(int(args[1]) * X_STEP, "units")
        else:
            self.tree.xview(*args)

    def _on_shift_wheel(self, ev):
        self._xscroll("scroll", -1 if ev.delta > 0 else 1, "units")
        return "break"

    def _fix_tag_colors(self):
        """Perbaikan Tk 8.6.9 (Windows) agar warna tag Treeview tampil."""
        style = ttk.Style()

        def fixed(opt):
            return [e for e in style.map("Treeview", query_opt=opt) if e[:2] != ("!disabled", "!selected")]
        try:
            style.map("Treeview", foreground=fixed("foreground"), background=fixed("background"))
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ data
    def sync(self, run, stage_ids=None):
        """Dipanggil App setiap status dimuat: ikuti run desain; muat ulang bila berkas berubah.

        stage_ids: sample_id yang lolos constraint tahap BO saat ini (dari status; hanya untuk run desain)."""
        self.stage_ids = set(stage_ids or ())
        self._design_run = run
        runs = list_runs()
        self.run_cb.configure(values=runs)
        if run and run != self._synced:
            self._synced = run
            self.run_var.set(run)
            self.load()
            return
        cur = self.run_var.get()
        if cur and os.path.isfile(table_path(cur)) and os.path.getmtime(table_path(cur)) != self._mtime:
            self.load()
        else:
            self.refresh_rows()

    def load(self):
        run = self.run_var.get()
        self.df, self.raw, self.view, self._mtime = None, None, None, None
        if not run or not os.path.isfile(table_path(run)):
            self._rebuild_columns()
            self.info_var.set("Belum ada batch_lhs.csv untuk run ini." if run else "")
            return
        try:
            self.df = load_table(run)
            self.raw = load_raw(run)
            self._mtime = os.path.getmtime(table_path(run))
        except Exception as e:
            self._rebuild_columns()
            self.info_var.set(f"Gagal membaca batch_lhs.csv: {e}")
            return
        if self.sort_col not in self.df.columns:
            self.sort_col = None
        self._rebuild_columns()
        if self.plot_win is not None and self.plot_win.winfo_exists():
            self.plot_win.refresh_columns()

    def reset_filters(self):
        self.feas_var.set("semua")
        self.id_var.set("")
        self.flt_var.set("")
        self.refresh_rows()

    # ------------------------------------------------------------------ tabel
    def _visible_columns(self):
        if self.df is None:
            return []
        return [c for c in self.df.columns if self.grp_vars[column_group(c)].get()]

    def _rebuild_columns(self):
        self.cols = self._visible_columns()
        self.tree.configure(columns=self.cols, displaycolumns=self.cols)
        for c in self.cols:
            self.tree.heading(c, text=self._head_text(c), command=lambda col=c: self.sort_by(col))
            w = 175 if c == "timestamp" else max(70, len(c) * 8 + 26)
            self.tree.column(c, width=w, minwidth=60, stretch=False, anchor="e" if c != "timestamp" else "w")
        self.refresh_rows()

    def _head_text(self, c):
        if c == self.sort_col:
            return c + (" \u25bc" if self.sort_desc else " \u25b2")
        return c

    def sort_by(self, col):
        if col == self.sort_col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col, self.sort_desc = col, False
        for c in self.cols:
            self.tree.heading(c, text=self._head_text(c))
        self.refresh_rows()

    def refresh_rows(self):
        self.tree.delete(*self.tree.get_children())
        if self.df is None:
            return
        try:
            filters = parse_filters(self.flt_var.get(), list(self.df.columns))
            ids = parse_ids(self.id_var.get())
        except ValueError as e:
            messagebox.showwarning("Filter", str(e))
            return
        stage_ok = self.run_var.get() == self._design_run
        self.radios["stage"].state(["!disabled"] if stage_ok else ["disabled"])
        if not stage_ok and self.feas_var.get() == "stage":
            self.feas_var.set("semua")
        feas = None if self.feas_var.get() == "semua" else self.feas_var.get()
        view = apply_filters(self.df, filters, feas, ids, self.stage_ids if stage_ok else None)
        if self.sort_col in view.columns:
            view = view.sort_values(self.sort_col, ascending=not self.sort_desc, kind="mergesort", na_position="last")
        self.view = view
        sid = view["sample_id"].tolist() if "sample_id" in view else [None] * len(view)
        fs = [stage_ok and x in self.stage_ids for x in sid]
        fe = view["fr_edge_flag"].tolist() if "fr_edge_flag" in view else [0] * len(view)
        rows = self.raw.loc[view.index, self.cols].to_numpy().tolist() if self.cols else [[] for _ in range(len(view))]
        for i, (idx, row) in enumerate(zip(view.index, rows)):
            tags = []
            if fs[i]:
                tags.append("feas")
            if fe[i] == 1:
                tags.append("edge")
            self.tree.insert("", "end", iid=str(idx), values=row, tags=tags)
        self._update_info()

    def _update_info(self):
        if self.df is None or self.view is None:
            return
        n_st = None
        if self.run_var.get() == self._design_run and "sample_id" in self.view:
            n_st = int(self.view["sample_id"].isin(self.stage_ids).sum())
        txt = (f"{len(self.view)} dari {len(self.df)} baris, {len(self.cols)} dari {len(self.df.columns)} kolom ditampilkan. ")
        if n_st is not None:
            txt += f"Lolos tahap ini: {n_st}. "
        self.info_var.set(txt + f"Terpilih: {len(self.tree.selection())}")

    def selected_ids(self):
        """sample_id baris yang dipilih di tabel (urut seperti tampil)."""
        if self.df is None or "sample_id" not in self.df.columns:
            return []
        return [int(self.df.loc[int(i), "sample_id"]) for i in self.tree.selection()]

    def _on_double(self, ev):
        if self.tree.identify_region(ev.x, ev.y) == "cell":
            self.open_plot("s11")

    def open_plot(self, mode):
        """Buka jendela grafik interaktif (matplotlib dimuat saat pertama dipakai)."""
        if self.df is None:
            messagebox.showinfo("Grafik", "Belum ada data. Pilih run yang punya batch_lhs.csv.")
            return
        if mode == "s11" and not self.selected_ids():
            messagebox.showinfo("Grafik S11", "Pilih satu atau lebih baris di tabel dulu (Ctrl atau Shift untuk memilih banyak), "
                                "atau klik ganda pada satu baris.")
            return
        w = self.plot_win
        if w is None or not w.winfo_exists():
            try:
                from cstopt.gui.plots import PlotWindow
                w = self.plot_win = PlotWindow(self)
            except Exception as e:
                messagebox.showerror("Grafik", f"Gagal membuka jendela grafik: {e}")
                return
        else:
            w.deiconify()
            w.lift()
            w.refresh_columns()
        if mode == "s11":
            w.use_selection()
        else:
            w.draw_scatter()

    def export_csv(self):
        if self.view is None or not self.cols:
            messagebox.showinfo("Ekspor", "Belum ada data untuk diekspor.")
            return
        path = filedialog.asksaveasfilename(title="Simpan tampilan sebagai CSV", defaultextension=".csv",
                                            initialfile=f"{self.run_var.get()}_tampilan.csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            self.raw.loc[self.view.index, self.cols].to_csv(path, index=False, encoding="utf-8")
        except Exception as e:
            messagebox.showerror("Ekspor gagal", str(e))
            return
        self.info_var.set(f"Tersimpan: {path} ({len(self.view)} baris, {len(self.cols)} kolom)")
