"""
GUI (tkinter) untuk seluruh alur: sampel LHS -> simulasi CST -> QC -> GPR -> Bayesian Optimization -> hasil.

Jalankan:  py main.py        (atau  py main.py gui)

GUI hanya "peluncur": setiap tombol menjalankan perintah yang sama dengan baris perintah
(`py main.py <perintah>`) dan menampilkan lognya. Tab 2 (CST) otomatis nonaktif bila CST tidak terpasang,
sehingga GUI tetap bisa dipakai di perangkat lain untuk bagian ML.
"""
import csv
import importlib.util
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from cstopt import paths
from cstopt.gui import commands as cmd
from cstopt.gui.runner import Runner

try:
    from PIL import Image, ImageTk
except Exception:                                    # pillow opsional (hanya untuk menampilkan gambar)
    Image = ImageTk = None

MAIN_PY = os.path.join(paths.ROOT, "main.py")
CST_OK = sys.platform == "win32" and importlib.util.find_spec("cst") is not None
R2_TARGET = 0.85
LOG_MAX_LINES = 4000


def open_path(path):
    """Buka folder atau berkas dengan aplikasi bawaan sistem."""
    if sys.platform == "win32":
        os.startfile(path)                           # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def read_csv_rows(path):
    if not path or not os.path.exists(path):
        return [], []
    with open(path, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        return list(rd.fieldnames or []), list(rd)


def fmt(v, nd=3):
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


class App:
    def __init__(self, root, design=None):
        self.root = root
        root.title("Optimasi antena: CST + GPR + Bayesian Optimization")
        root.geometry("1120x820")
        root.minsize(920, 660)
        self.runner = Runner(MAIN_PY, paths.ROOT)
        self.status = {}
        self.buttons = []                            # tombol aksi yang dinonaktifkan selama proses berjalan
        self._status_q = queue.Queue()
        self._status_busy = False
        designs = paths.list_designs() or [paths.DEFAULT_DESIGN]
        self.design_var = tk.StringVar(value=design or (paths.DEFAULT_DESIGN if paths.DEFAULT_DESIGN in designs else designs[0]))
        self.designs = designs
        self.warn_var = tk.StringVar(value="")
        self._photo = None
        self._user_stopped = False
        self._build_top()
        self._build_tabs()
        self._build_log()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.refresh_status()

    # ------------------------------------------------------------------ tata letak
    def _build_top(self):
        f = ttk.Frame(self.root, padding=(10, 8, 10, 0))
        f.pack(fill="x")
        ttk.Label(f, text="Desain:").pack(side="left")
        cb = ttk.Combobox(f, textvariable=self.design_var, values=self.designs, state="readonly", width=28)
        cb.pack(side="left", padx=(4, 10))
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_status())
        ttk.Button(f, text="Muat ulang status", command=self.refresh_status).pack(side="left")
        ttk.Button(f, text="Buka folder data", command=self.open_data).pack(side="left", padx=6)
        self.status_text = tk.Text(self.root, height=8, wrap="none", font="TkFixedFont", state="disabled",
                                   background="#f6f6f6", relief="flat", padx=8, pady=6)
        self.status_text.pack(fill="x", padx=10, pady=(6, 4))
        self.status_text.tag_configure("warn", foreground="#b45f06")
        self.status_text.tag_configure("err", foreground="#b00020")

    def _build_tabs(self):
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=10, pady=4)
        self.tab_lhs = self._tab("1  Sampel LHS")
        self.tab_cst = self._tab("2  Simulasi CST")
        self.tab_qc = self._tab("3  Data dan QC")
        self.tab_gpr = self._tab("4  Model GPR")
        self.tab_bo = self._tab("5  Optimasi BO")
        self.tab_res = self._tab("6  Hasil")
        self._fill_lhs()
        self._fill_cst()
        self._fill_qc()
        self._fill_gpr()
        self._fill_bo()
        self._fill_results()

    def _tab(self, title):
        f = ttk.Frame(self.nb, padding=12)
        self.nb.add(f, text=title)
        return f

    def _build_log(self):
        f = ttk.Frame(self.root, padding=(10, 0, 10, 8))
        f.pack(fill="both", expand=False)
        bar = ttk.Frame(f)
        bar.pack(fill="x")
        self.state_var = tk.StringVar(value="Siap")
        ttk.Label(bar, textvariable=self.state_var).pack(side="left")
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=120)
        self.progress.pack(side="left", padx=8)
        self.stop_btn = ttk.Button(bar, text="Hentikan", command=self.stop, state="disabled")
        self.stop_btn.pack(side="right")
        ttk.Button(bar, text="Bersihkan log", command=self.clear_log).pack(side="right", padx=6)
        box = ttk.Frame(f)
        box.pack(fill="both", expand=True, pady=(4, 0))
        self.log = tk.Text(box, height=11, wrap="none", font="TkFixedFont", state="disabled",
                           background="#101418", foreground="#d7dde3", insertbackground="#d7dde3", padx=8, pady=6)
        sb = ttk.Scrollbar(box, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        self.log.tag_configure("cmd", foreground="#7fd1ff")
        self.log.tag_configure("warn", foreground="#ffc66d")
        self.log.tag_configure("ok", foreground="#8fdc8f")
        self.log.tag_configure("bad", foreground="#ff8f8f")

    # ------------------------------------------------------------------ isi tab
    def _row(self, parent, r, label, widget_factory):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", pady=3, padx=(0, 10))
        w = widget_factory(parent)
        w.grid(row=r, column=1, sticky="w", pady=3)
        return w

    def _btn(self, parent, text, command, **grid):
        b = ttk.Button(parent, text=text, command=command)
        b.grid(**grid)
        self.buttons.append(b)
        return b

    def _fill_lhs(self):
        t = self.tab_lhs
        ttk.Label(t, text="Bangkitkan sampel awal Latin Hypercube (maximin) dari rentang parameter di file desain.",
                  wraplength=900).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self.lhs_n = tk.IntVar(value=80)
        self.lhs_seed = tk.IntVar(value=42)
        self.lhs_report = tk.BooleanVar(value=False)
        self._row(t, 1, "Jumlah sampel", lambda p: ttk.Spinbox(p, from_=10, to=500, textvariable=self.lhs_n, width=8))
        self._row(t, 2, "Seed", lambda p: ttk.Spinbox(p, from_=0, to=9999, textvariable=self.lhs_seed, width=8))
        self._row(t, 3, "", lambda p: ttk.Checkbutton(p, text="Tampilkan perbandingan dengan LHS biasa dan acak",
                                                      variable=self.lhs_report))
        self._btn(t, "Bangkitkan sampel", self.do_lhs, row=4, column=1, sticky="w", pady=10)
        ttk.Label(t, text="Keluaran: data/<RUN>/samples/lhs_samples.csv. Pembangkitan ulang menimpa berkas itu.",
                  foreground="#666").grid(row=5, column=0, columnspan=3, sticky="w")

    def _fill_cst(self):
        t = self.tab_cst
        t.columnconfigure(1, weight=1)
        if not CST_OK:
            ttk.Label(t, foreground="#b45f06", wraplength=900,
                      text="CST atau paket Windows tidak terdeteksi di perangkat ini, jadi tab ini nonaktif. "
                           "Bagian ML (tab lain) tetap bisa dipakai. Untuk mengaktifkan: pip install -r "
                           "requirements-cst.txt (hanya Windows dengan CST Studio Suite).").grid(row=0, column=0, columnspan=3, sticky="w")
        else:
            ttk.Label(t, text="Buka project di CST lebih dulu (file .cst yang sudah dibangun dengan macro). "
                              "Hasil ditambahkan ke data/<RUN>/batch_lhs.csv; sampel yang sudah ada dilewati.",
                      wraplength=900).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self.cst_samples = tk.StringVar(value="")
        self.cst_project = tk.StringVar(value="")
        self.cst_auto = tk.BooleanVar(value=True)
        self.cst_limit = tk.IntVar(value=0)
        e1 = self._row(t, 1, "Berkas sampel", lambda p: ttk.Entry(p, textvariable=self.cst_samples, width=70))
        ttk.Button(t, text="Pilih...", command=lambda: self._browse(self.cst_samples, paths.DATA_DIR)).grid(row=1, column=2, padx=6)
        self._row(t, 2, "Project .cst (opsional)", lambda p: ttk.Entry(p, textvariable=self.cst_project, width=70))
        ttk.Button(t, text="Pilih...", command=lambda: self._browse(self.cst_project, paths.CST_PROJECTS_DIR)).grid(row=2, column=2, padx=6)
        ttk.Label(t, text="Kosongkan berkas sampel untuk memakai lhs_samples.csv; kosongkan project agar dideteksi dari CST.",
                  foreground="#666").grid(row=3, column=1, sticky="w")
        self._row(t, 4, "", lambda p: ttk.Checkbutton(p, text="Tekan Yes otomatis pada dialog CST yang dikenal (--auto-yes)", variable=self.cst_auto))
        self._row(t, 5, "Batas jumlah sampel", lambda p: ttk.Spinbox(p, from_=0, to=500, textvariable=self.cst_limit, width=8))
        bar = ttk.Frame(t)
        bar.grid(row=6, column=1, sticky="w", pady=10)
        for text, fn in [("Cek koneksi", self.do_probe), ("Cek sampel", self.do_check), ("Jalankan batch", self.do_batch)]:
            b = ttk.Button(bar, text=text, command=fn)
            b.pack(side="left", padx=(0, 8))
            self.buttons.append(b)
        self.cst_widgets = [w for w in t.winfo_children() if not isinstance(w, ttk.Label)] + list(bar.winfo_children())
        if not CST_OK:
            for w in self.cst_widgets:
                try:
                    w.state(["disabled"])
                except Exception:
                    pass

    def _fill_qc(self):
        t = self.tab_qc
        ttk.Label(t, text="Pemeriksaan kualitas data hasil simulasi (tanpa CST).", wraplength=900).grid(row=0, column=0, sticky="w", pady=(0, 8))
        bar = ttk.Frame(t)
        bar.grid(row=1, column=0, sticky="w")
        for text, fn in [("QC dataset", self.do_qc), ("Verifikasi kurva S11", self.do_curves)]:
            b = ttk.Button(bar, text=text, command=fn)
            b.pack(side="left", padx=(0, 8))
            self.buttons.append(b)
        ttk.Label(t, text="QC dataset harus berakhir \"Semua pemeriksaan lulus\"; verifikasi kurva harus \"KONSISTEN\".",
                  foreground="#666").grid(row=2, column=0, sticky="w", pady=8)

    def _fill_gpr(self):
        t = self.tab_gpr
        t.columnconfigure(0, weight=1)
        t.rowconfigure(2, weight=1)
        top = ttk.Frame(t)
        top.grid(row=0, column=0, sticky="w")
        self.gpr_kernel = tk.StringVar(value="rbf")
        self.gpr_restarts = tk.IntVar(value=5)
        self.gpr_cv = tk.IntVar(value=5)
        ttk.Label(top, text="Kernel").pack(side="left")
        ttk.Combobox(top, textvariable=self.gpr_kernel, values=["rbf", "matern52", "both"], state="readonly", width=10).pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Restart").pack(side="left")
        ttk.Spinbox(top, from_=1, to=20, textvariable=self.gpr_restarts, width=4).pack(side="left", padx=(4, 12))
        ttk.Label(top, text="CV lipatan").pack(side="left")
        ttk.Spinbox(top, from_=2, to=10, textvariable=self.gpr_cv, width=4).pack(side="left", padx=(4, 12))
        b = ttk.Button(top, text="Latih dan evaluasi", command=self.do_train)
        b.pack(side="left", padx=(8, 8))
        self.buttons.append(b)
        ttk.Button(top, text="Lihat parity", command=lambda: self.show_figure("gpr_parity.png")).pack(side="left")
        ttk.Label(t, text="Akurasi tiap target. Merah = R2 cross-validation di bawah 0,85 (indikator di proposal).",
                  foreground="#666").grid(row=1, column=0, sticky="w", pady=6)
        cols = ["target", "R2_test", "R2_cv", "RMSE_cv", "cov95"]
        box = ttk.Frame(t)
        box.grid(row=2, column=0, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        self.metrics = ttk.Treeview(box, columns=cols, show="headings", height=10)
        msb = ttk.Scrollbar(box, command=self.metrics.yview)
        self.metrics.configure(yscrollcommand=msb.set)
        msb.grid(row=0, column=1, sticky="ns")
        for c in cols:
            self.metrics.heading(c, text=c)
            self.metrics.column(c, width=140 if c == "target" else 100, anchor="w" if c == "target" else "e")
        self.metrics.tag_configure("low", foreground="#b00020")
        self.metrics.grid(row=0, column=0, sticky="nsew")

    def _fill_bo(self):
        t = self.tab_bo
        t.columnconfigure(0, weight=1)
        t.rowconfigure(3, weight=1)
        top = ttk.Frame(t)
        top.grid(row=0, column=0, sticky="w")
        self.bo_q = tk.IntVar(value=5)
        self.bo_kernel = tk.StringVar(value="rbf")
        self.bo_restarts = tk.IntVar(value=5)
        self.bo_stage = tk.StringVar(value="otomatis")
        ttk.Label(top, text="Jumlah kandidat").pack(side="left")
        ttk.Spinbox(top, from_=1, to=20, textvariable=self.bo_q, width=4).pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Kernel").pack(side="left")
        ttk.Combobox(top, textvariable=self.bo_kernel, values=["rbf", "matern52"], state="readonly", width=9).pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Restart").pack(side="left")
        ttk.Spinbox(top, from_=1, to=20, textvariable=self.bo_restarts, width=4).pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Tahap").pack(side="left")
        ttk.Combobox(top, textvariable=self.bo_stage, values=["otomatis", "1", "2"], state="readonly", width=9).pack(side="left", padx=(4, 12))
        bar = ttk.Frame(t)
        bar.grid(row=1, column=0, sticky="w", pady=8)
        for text, fn in [("Usulkan kandidat", self.do_suggest), ("Kurva konvergensi", self.do_report), ("Uji BO vs acak (backtest)", self.do_backtest)]:
            b = ttk.Button(bar, text=text, command=fn)
            b.pack(side="left", padx=(0, 8))
            self.buttons.append(b)
        ttk.Button(bar, text="Pakai kandidat di tab 2", command=self.use_candidates).pack(side="left", padx=(8, 0))
        ttk.Label(t, textvariable=self.warn_var, foreground="#b45f06", wraplength=1000).grid(row=2, column=0, sticky="w")
        cbox = ttk.Frame(t)
        cbox.grid(row=3, column=0, sticky="nsew", pady=(4, 0))
        cbox.columnconfigure(0, weight=1)
        cbox.rowconfigure(0, weight=1)
        self.cand = ttk.Treeview(cbox, show="headings", height=8)
        csb = ttk.Scrollbar(cbox, command=self.cand.yview)
        self.cand.configure(yscrollcommand=csb.set)
        self.cand.grid(row=0, column=0, sticky="nsew")
        csb.grid(row=0, column=1, sticky="ns")

    def _fill_results(self):
        t = self.tab_res
        t.columnconfigure(0, weight=1)
        t.rowconfigure(1, weight=1)
        top = ttk.Frame(t)
        top.grid(row=0, column=0, sticky="w")
        self.fig_var = tk.StringVar()
        ttk.Label(top, text="Gambar").pack(side="left")
        self.fig_cb = ttk.Combobox(top, textvariable=self.fig_var, state="readonly", width=34)
        self.fig_cb.pack(side="left", padx=6)
        self.fig_cb.bind("<<ComboboxSelected>>", lambda e: self._draw_figure())
        ttk.Button(top, text="Buka folder gambar", command=lambda: self.open_data("figures")).pack(side="left", padx=6)
        self.fig_label = ttk.Label(t, anchor="center")
        self.fig_label.grid(row=1, column=0, sticky="nsew", pady=8)
        self.fig_label.bind("<Configure>", lambda e: self._draw_figure())
        self.fig_paths = {}

    # ------------------------------------------------------------------ status
    def design(self):
        return self.design_var.get() or None

    def refresh_status(self):
        if self._status_busy:
            return
        self._status_busy = True
        self._set_status_text("Memuat status ...")
        d = self.design()
        threading.Thread(target=lambda: self._status_q.put(self.runner.capture_json(cmd.status(d))), daemon=True).start()
        self.root.after(150, self._check_status)

    def _check_status(self):
        try:
            s = self._status_q.get_nowait()
        except queue.Empty:
            self.root.after(150, self._check_status)
            return
        self._status_busy = False
        self.status = s
        self._render_status(s)
        self._load_metrics()
        self._load_candidates()
        self._load_figure_list()

    def _set_status_text(self, text, tags=None):
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", "end")
        self.status_text.insert("end", text, tags or ())
        self.status_text.configure(state="disabled")

    def _render_status(self, s):
        if "error" in s and "run" not in s:
            self._set_status_text(s["error"], ("err",))
            return
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", "end")
        w = self.status_text.insert
        w("end", f"Desain  : {s['design']} ({s['design_name']})\nRun     : {s['run']}   {s['run_dir']}\n")
        if "note" in s:
            w("end", s["note"] + "\n", ("warn",))
        if "error" in s:
            w("end", f"[error] dataset gagal dimuat: {s['error']}\n", ("err",))
        if "n_samples" in s:
            st = s["stage"]
            w("end", f"Sampel  : {s['n_samples']} (awal {s['n_initial']}, BO {s['n_bo']})   "
                     f"Tahap BO: {st['index']}/{st['total']} {st['name']}   "
                     f"objective: {s['objective']['goal']} {s['objective']['column']}\n")
            w("end", f"Feasible: {s['n_feasible']} dari {s['n_samples']} memenuhi constraint tahap ini\n")
            if "best" in s:
                b = s["best"]
                extra = "  ".join(f"{k}={b[k]:.3g}" for k in ("fr_ghz", "rl_min_db", "bw_mhz", "gain_fr_ieee_dbi")
                                  if k in b and k != s["objective"]["column"])
                tag = "Terbaik " if b["feasible"] else "Terbaik (belum ada yang feasible) "
                w("end", f"{tag}: sampel {b['sample_id']}   {s['objective']['column']}={b['value']:.4g}   {extra}\n")
            for h in s.get("bound_hits", []):
                w("end", f"[peringatan] {h['param']} menempel batas {h['side']} ({h['bound']:g}) pada {h['n']}/{h['of']} desain terbaik\n", ("warn",))
        f = s.get("files", {})
        parts = []
        for key, label in [("lhs_samples", "lhs_samples"), ("bo_candidates", "kandidat BO"), ("models", "model GPR")]:
            if key in f:
                parts.append(f"{label}: {'ada' if f[key]['exists'] else 'belum'}")
        if parts:
            w("end", "Berkas  : " + "   ".join(parts) + "\n")
        self.status_text.configure(state="disabled")

    def _load_metrics(self):
        self.metrics.delete(*self.metrics.get_children())
        path = self.status.get("files", {}).get("metrics", {}).get("path")
        _, rows = read_csv_rows(path)
        for r in rows:
            try:
                low = float(r["R2_cv"]) < R2_TARGET
            except (KeyError, ValueError):
                low = False
            self.metrics.insert("", "end", tags=("low",) if low else (),
                                values=[r.get("target", ""), fmt(r.get("R2_test", "")), fmt(r.get("R2_cv", "")),
                                        fmt(r.get("RMSE_cv", ""), 3), fmt(r.get("cov95", ""), 2)])

    def _load_candidates(self):
        self.cand.delete(*self.cand.get_children())
        path = self.status.get("files", {}).get("bo_candidates", {}).get("path")
        report = path.replace(".csv", "_report.csv") if path else None
        header, rows = read_csv_rows(report if report and os.path.exists(report) else path)
        oc = self.status.get("objective", {}).get("column", "")
        want = ["sample_id", "acq", "pof", f"pred_{oc}", f"std_{oc}", "Lp", "Wp", "LU", "WU", "WD"]
        cols = [c for c in want if c in header] or header[:8]
        self.cand.configure(columns=cols)
        for c in cols:
            self.cand.heading(c, text=c)
            self.cand.column(c, width=90, anchor="e")
        for r in rows:
            self.cand.insert("", "end", values=[fmt(r.get(c, ""), 3) if c != "sample_id" else r.get(c, "") for c in cols])

    def _load_figure_list(self):
        figs = self.status.get("figures", [])
        self.fig_paths = {os.path.basename(p): p for p in figs}
        self.fig_cb.configure(values=list(self.fig_paths))
        if self.fig_paths and self.fig_var.get() not in self.fig_paths:
            self.fig_var.set(next(iter(self.fig_paths)))
        self._draw_figure()

    # ------------------------------------------------------------------ gambar
    def show_figure(self, name):
        self._load_figure_list()
        if name in self.fig_paths:
            self.fig_var.set(name)
            self._draw_figure()
        self.nb.select(self.tab_res)

    def _draw_figure(self):
        path = self.fig_paths.get(self.fig_var.get())
        if not path or not os.path.exists(path):
            self.fig_label.configure(image="", text="Belum ada gambar. Jalankan Latih (tab 4) atau Kurva konvergensi (tab 5).")
            self._photo = None
            return
        w = max(self.fig_label.winfo_width(), 400)
        h = max(self.fig_label.winfo_height(), 300)
        try:
            if Image is not None:
                im = Image.open(path)
                im.thumbnail((w - 10, h - 10))
                self._photo = ImageTk.PhotoImage(im)
            else:
                ph = tk.PhotoImage(file=path)
                k = max(1, -(-ph.width() // w), -(-ph.height() // h))
                self._photo = ph.subsample(k, k) if k > 1 else ph
            self.fig_label.configure(image=self._photo, text="")
        except Exception as e:                       # berkas rusak atau format tak didukung
            self.fig_label.configure(image="", text=f"Gagal menampilkan {os.path.basename(path)}: {e}")

    # ------------------------------------------------------------------ eksekusi perintah
    def run_cmd(self, argv, after=None):
        if self.runner.busy:
            messagebox.showinfo("Sedang berjalan", "Masih ada proses yang berjalan. Tunggu atau tekan Hentikan.")
            return
        self.warn_var.set("")
        self._log(cmd.display(argv) + "\n", "cmd")
        self.state_var.set("Berjalan: " + argv[0])
        for b in self.buttons:
            b.state(["disabled"])
        self.stop_btn.state(["!disabled"])
        self.progress.start(12)
        try:
            self.runner.start(argv, self._on_line, lambda rc: self._on_done(rc, argv, after))
        except Exception as e:
            self._on_done(-1, argv, None)
            self._log(f"Gagal memulai: {e}\n", "bad")
            return
        self.root.after(100, self._poll)

    def _poll(self):
        if self.runner.poll():
            self.root.after(100, self._poll)

    def _on_line(self, line):
        tag = "warn" if line.startswith("[peringatan]") or line.startswith("[info]") else None
        if line.startswith("[peringatan]"):
            self.warn_var.set((self.warn_var.get() + "  " + line.strip()).strip())
        self._log(line + "\n", tag)

    def _on_done(self, rc, argv, after):
        self.progress.stop()
        self.progress.configure(value=0)
        self.stop_btn.state(["disabled"])
        for b in self.buttons:
            b.state(["!disabled"])
        if not CST_OK:                                # tombol CST tetap nonaktif
            for w in self.cst_widgets:
                try:
                    w.state(["disabled"])
                except Exception:
                    pass
        ok = rc == 0
        if self._user_stopped:
            self._user_stopped = False
            self.state_var.set("Dihentikan")
        else:
            self.state_var.set("Siap" if ok else f"Selesai dengan kode {rc}")
            self._log(f"[{'selesai' if ok else 'gagal, kode ' + str(rc)}: {argv[0]}]\n\n", "ok" if ok else "bad")
        self._status_busy = False
        self.refresh_status()
        if ok and after:
            self.root.after(400, after)

    def stop(self):
        self._user_stopped = self.runner.busy
        self.runner.stop()
        self._log("[dihentikan oleh pengguna] Bila sedang menjalankan CST, simulasi yang berjalan mungkin masih selesai di CST.\n", "bad")

    def _log(self, text, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", text, (tag,) if tag else ())
        n = int(self.log.index("end-1c").split(".")[0])
        if n > LOG_MAX_LINES:
            self.log.delete("1.0", f"{n - LOG_MAX_LINES}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    # ------------------------------------------------------------------ aksi tombol
    def run_name(self):
        return self.status.get("run")

    def do_lhs(self):
        path = os.path.join(paths.samples_dir(self.run_name() or ""), "lhs_samples.csv") if self.run_name() else ""
        if path and os.path.exists(path) and not messagebox.askyesno("Timpa sampel?", f"{path}\nsudah ada dan akan ditimpa. Lanjutkan?"):
            return
        self.run_cmd(cmd.lhs(self.lhs_n.get(), self.lhs_seed.get(), self.lhs_report.get(), self.design()))

    def do_probe(self):
        self.run_cmd(cmd.run_probe(self.cst_project.get() or None))

    def do_check(self):
        self.run_cmd(cmd.run_check(self.cst_samples.get() or None, self.cst_project.get() or None))

    def do_batch(self):
        samples = self.cst_samples.get() or None
        if not messagebox.askyesno("Jalankan batch CST", "Batch memakai CST dan dapat berjalan lama (sekitar 4-6 menit per sampel). Lanjutkan?"):
            return
        self.run_cmd(cmd.run_batch(samples, self.cst_auto.get(), self.cst_limit.get(), self.cst_project.get() or None))

    def do_qc(self):
        self.run_cmd(cmd.qc(self.run_name()))

    def do_curves(self):
        self.run_cmd(cmd.curves(self.run_name()))

    def do_train(self):
        self.run_cmd(cmd.train(self.gpr_kernel.get(), self.gpr_restarts.get(), self.gpr_cv.get(), 0, self.design()),
                     after=lambda: self.show_figure("gpr_parity.png"))

    def _stage(self):
        s = self.bo_stage.get()
        return int(s) if s.isdigit() else None

    def do_suggest(self):
        self.run_cmd(cmd.suggest(self.bo_q.get(), self.bo_kernel.get(), self.bo_restarts.get(), self._stage(), self.design()))

    def do_report(self):
        self.run_cmd(cmd.suggest(stage=self._stage(), design=self.design(), report=True),
                     after=lambda: self.show_figure("bo_convergence.png"))

    def do_backtest(self):
        self.run_cmd(cmd.backtest(design=self.design()), after=lambda: self.show_figure("bo_backtest.png"))

    def use_candidates(self):
        path = self.status.get("files", {}).get("bo_candidates", {}).get("path", "")
        if path:
            self.cst_samples.set(path)
            self.nb.select(self.tab_cst)

    def _browse(self, var, initial):
        p = filedialog.askopenfilename(initialdir=initial if os.path.isdir(initial) else paths.ROOT)
        if p:
            var.set(p)

    def open_data(self, sub=None):
        d = paths.run_dir(self.run_name() or "")
        if sub:
            d = os.path.join(d, sub)
        if not os.path.isdir(d):
            messagebox.showinfo("Belum ada", f"Folder belum ada:\n{d}")
            return
        open_path(d)

    def _on_close(self):
        if self.runner.busy and not messagebox.askyesno("Keluar", "Proses masih berjalan. Hentikan dan keluar?"):
            return
        self.runner.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()
