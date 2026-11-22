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
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from cstopt import paths
from cstopt.gui import commands as cmd
from cstopt.gui import theme
from cstopt.gui.dataview import DataTab
from cstopt.gui.layout import Collapsible, autowrap, fit_window, make_flow, make_scrollable, two_panes
from cstopt.gui.runner import Runner

try:
    from PIL import Image, ImageTk
    from cstopt.gui.viewers import ZoomImage
except Exception:                                    # pillow opsional (hanya untuk menampilkan gambar)
    Image = ImageTk = ZoomImage = None

MAIN_PY = os.path.join(paths.ROOT, "main.py")
CST_OK = sys.platform == "win32" and importlib.util.find_spec("cst") is not None
R2_TARGET = 0.85
LOG_MAX_LINES = 4000
REPORT_SCOPES = ("Desain terpilih", "Semua desain (gabungan)")


def _descendants(w):
    """Semua widget turunan (rekursif)."""
    for c in w.winfo_children():
        yield c
        yield from _descendants(c)


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
        theme.init(root)                              # T1: tema (gelap bawaan; pilihan terakhir tersimpan) sebelum widget dibuat
        root.title("Optimasi antena: CST + GPR + Bayesian Optimization")
        fit_window(root, 1120, 820, 860, 520)             # G4a: ukuran awal dibatasi layar
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
        self._zoom_path = None
        self._user_stopped = False
        self._auto_active, self._auto_last = False, ""      # auto run: sedang berjalan; pesan berhenti terakhir dari CLI
        self.status_detail = False                   # G4a: status ringkas (2 baris) atau detail
        self._status_full, self._status_compact = [], []
        self._log_open = False
        self._log_lines = 8                          # tinggi panel log saat terbuka (baris), bisa digeser
        self._log_auto = False                       # log dibuka otomatis oleh perintah (boleh dilipat lagi sendiri)
        self._collapse_job = None
        self.qc_last = {"qc": "belum dijalankan", "curves": "belum dijalankan"}     # T2: hasil QC terakhir sesi ini (panel tab 3)
        self._cur_cmd = None
        self._cap = []
        self._build_top()
        self._build_log()                            # dipasang di bawah lebih dulu agar tidak pernah terpotong
        self._build_tabs()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        theme.retheme(root)                          # T1: warna literal terang di kode tab diganti warna peran tema aktif
        self.refresh_status()

    # ------------------------------------------------------------------ tata letak
    def _build_top(self):
        outer = ttk.Frame(self.root, padding=(10, 8, 10, 0))      # padding di bingkai luar: tinggi baris membungkus tidak ikut terpotong
        outer.pack(fill="x")
        f = ttk.Frame(outer)
        f.pack(fill="x")
        ttk.Label(f, text="Desain:").pack(side="left")
        cb = ttk.Combobox(f, textvariable=self.design_var, values=self.designs, state="readonly", width=28)
        cb.pack(side="left", padx=(4, 10))
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_status())
        ttk.Button(f, text="Muat ulang status", command=self.refresh_status).pack(side="left")
        ttk.Button(f, text="Buka folder data", command=self.open_data).pack(side="left", padx=6)
        self.detail_btn = ttk.Button(f, text="Detail", width=8, command=self.toggle_status_detail)
        self.detail_btn.pack(side="left")
        self.theme_btn = ttk.Button(f, text=self._theme_label(), width=13, command=self.toggle_theme)
        self.theme_btn.pack(side="left", padx=6)
        make_flow(f)
        self.status_text = tk.Text(self.root, height=2, wrap="none", font="TkDefaultFont", state="disabled",
                                   background="#f6f6f6", relief="flat", padx=8, pady=4)
        self.status_text.pack(fill="x", padx=10, pady=(6, 4))
        self.status_text.tag_configure("warn", foreground="#b45f06")
        self.status_text.tag_configure("err", foreground="#b00020")

    @staticmethod
    def _theme_label():
        return "Tema: gelap" if theme.MODE == "dark" else "Tema: terang"

    def toggle_theme(self):
        theme.toggle(self.root)
        self.theme_btn.configure(text=self._theme_label())

    def _build_tabs(self):
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=10, pady=4)
        self.tab_lhs = self._tab("1  Sampel LHS")
        self.tab_cst = self._tab("2  Simulasi CST")
        self.tab_qc = self._tab("3  Data dan QC")
        self.tab_gpr = self._tab("4  Model GPR")
        self.tab_bo = self._tab("5  Optimasi BO", scroll=True)       # isinya tinggi: bisa digulir di layar kecil
        self.tab_res = self._tab("6  Hasil")
        self.tab_data = self._tab("7  Data")
        self._fill_lhs()
        self._fill_cst()
        self._fill_qc()
        self._fill_gpr()
        self._fill_bo()
        self._fill_results()
        self.data_tab = DataTab(self.tab_data, self)

    def _tab(self, title, scroll=False):
        if scroll:
            outer, f = make_scrollable(self.nb, padding=12)
            self.nb.add(outer, text=title)
            return f
        f = ttk.Frame(self.nb, padding=12)
        self.nb.add(f, text=title)
        return f

    def _build_log(self):
        """Panel log di bawah: terlipat jadi satu baris (baris terakhir) saat tidak ada proses; terbuka saat perintah jalan."""
        f = ttk.Frame(self.root, padding=(10, 0, 10, 6))
        f.pack(side="bottom", fill="x")
        self.log_frame = f
        bar = ttk.Frame(f)
        bar.pack(fill="x")
        self.log_btn = ttk.Button(bar, text="Buka log", width=10, command=self.toggle_log)
        self.log_btn.pack(side="left")
        self.state_var = tk.StringVar(value="Siap")
        ttk.Label(bar, textvariable=self.state_var, width=16).pack(side="left", padx=(8, 0))
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=90)
        self.progress.pack(side="left", padx=8)
        self.stop_btn = ttk.Button(bar, text="Hentikan", command=self.stop, state="disabled")
        self.stop_btn.pack(side="right")
        ttk.Button(bar, text="Bersihkan log", command=self.clear_log).pack(side="right", padx=6)
        self.last_var = tk.StringVar(value="")
        self.last_lbl = ttk.Label(bar, textvariable=self.last_var, width=12, foreground="#555")
        self.last_lbl.pack(side="left", fill="x", expand=True)       # width kecil: teks panjang terpotong, tidak melebarkan jendela
        self.grip = tk.Frame(f, height=7, cursor="sb_v_double_arrow", background="#c9ced3")
        self.grip.bind("<ButtonPress-1>", self._grip_start)
        self.grip.bind("<B1-Motion>", self._grip_drag)
        self.box = ttk.Frame(f)
        self.log = tk.Text(self.box, height=self._log_lines, wrap="none", font="TkFixedFont", state="disabled",
                           background="#101418", foreground="#d7dde3", insertbackground="#d7dde3", padx=8, pady=6)
        sb = ttk.Scrollbar(self.box, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        self.log.bind("<Enter>", lambda e: self._cancel_collapse())  # pengguna sedang membaca: jangan dilipat otomatis
        self.log.tag_configure("cmd", foreground="#7fd1ff")
        self.log.tag_configure("warn", foreground="#ffc66d")
        self.log.tag_configure("ok", foreground="#8fdc8f")
        self.log.tag_configure("bad", foreground="#ff8f8f")

    def _set_log_open(self, on, auto=False):
        self._cancel_collapse()
        if on == self._log_open:
            if on and not auto:
                self._log_auto = False
            return
        self._log_open = on
        self._log_auto = bool(on and auto)
        if on:
            self.grip.pack(fill="x", pady=(4, 0))
            self.box.pack(fill="both", expand=True)
            self.log.see("end")
        else:
            self.box.pack_forget()
            self.grip.pack_forget()
        self.log_btn.configure(text="Tutup log" if on else "Buka log")

    def toggle_log(self):
        self._set_log_open(not self._log_open, auto=False)

    def _cancel_collapse(self):
        if self._collapse_job is not None:
            self.root.after_cancel(self._collapse_job)
            self._collapse_job = None

    def _grip_start(self, e):
        self._grip_y = e.y_root
        self._grip_lines0 = self._log_lines

    def _grip_drag(self, e):
        from tkinter import font as tkfont
        lh = max(8, tkfont.nametofont("TkFixedFont").metrics("linespace"))
        n = self._grip_lines0 + int(round((self._grip_y - e.y_root) / lh))      # seret ke atas = log lebih tinggi
        self._log_lines = max(3, min(30, n))
        self.log.configure(height=self._log_lines)

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
        box, L, R = two_panes(self.tab_lhs, right_width=400)
        box.pack(fill="both", expand=True)
        t = L
        t.columnconfigure(1, weight=1)
        autowrap(ttk.Label(t, text="Bangkitkan sampel awal Latin Hypercube (maximin) dari rentang parameter di file desain "
                                   "(atau dari override rentang bila ada).", wraplength=420, justify="left")
                 ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.lhs_n = tk.IntVar(value=80)
        self.lhs_seed = tk.IntVar(value=42)
        self.lhs_report = tk.BooleanVar(value=False)
        self._row(t, 1, "Jumlah sampel", lambda p: ttk.Spinbox(p, from_=10, to=500, textvariable=self.lhs_n, width=8))
        self._row(t, 2, "Seed", lambda p: ttk.Spinbox(p, from_=0, to=9999, textvariable=self.lhs_seed, width=8))
        self._row(t, 3, "", lambda p: ttk.Checkbutton(p, text="Tampilkan perbandingan dengan LHS biasa dan acak",
                                                      variable=self.lhs_report))
        self._btn(t, "Bangkitkan sampel", self.do_lhs, row=4, column=1, sticky="w", pady=10)
        autowrap(ttk.Label(t, text="Keluaran: data/<RUN>/samples/lhs_samples.csv. Pembangkitan ulang menimpa berkas itu.",
                           foreground="#666", wraplength=420, justify="left")).grid(row=5, column=0, columnspan=2, sticky="w")
        pan = ttk.LabelFrame(R, text="Rentang parameter aktif (mm)", padding=6)
        pan.pack(fill="both", expand=True)
        pan.columnconfigure(0, weight=1)
        cols = ["param", "lo", "hi", "status"]
        self.rng_tree = ttk.Treeview(pan, columns=cols, show="headings", height=11, selectmode="none")
        for c, txt, w, an in [("param", "Parameter", 80, "w"), ("lo", "Min", 66, "e"), ("hi", "Maks", 66, "e"), ("status", "Status", 150, "w")]:
            self.rng_tree.heading(c, text=txt)
            self.rng_tree.column(c, width=w, anchor=an)
        self.rng_tree.tag_configure("chg", foreground="#b45f06")
        rsb = ttk.Scrollbar(pan, command=self.rng_tree.yview)
        self.rng_tree.configure(yscrollcommand=rsb.set)
        self.rng_tree.grid(row=0, column=0, sticky="nsew")
        rsb.grid(row=0, column=1, sticky="ns")
        self.lhs_info = tk.StringVar(value="")
        ttk.Label(pan, textvariable=self.lhs_info, foreground="#666").grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def _fill_cst(self):
        box, t, R = two_panes(self.tab_cst, right_width=380, min_total=1000)
        box.pack(fill="both", expand=True)
        t.columnconfigure(1, weight=1)
        if not CST_OK:
            autowrap(ttk.Label(t, foreground="#b45f06", wraplength=560, justify="left",
                               text="CST atau paket Windows tidak terdeteksi di perangkat ini, jadi tab ini nonaktif. "
                                    "Bagian ML (tab lain) tetap bisa dipakai. Untuk mengaktifkan: pip install -r "
                                    "requirements-cst.txt (hanya Windows dengan CST Studio Suite).")).grid(row=0, column=0, columnspan=3, sticky="w")
        else:
            autowrap(ttk.Label(t, text="Buka project di CST lebih dulu (file .cst yang sudah dibangun dengan macro). "
                                       "Hasil ditambahkan ke data/<RUN>/batch_lhs.csv; sampel yang sudah ada dilewati.",
                               wraplength=560, justify="left")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self.cst_samples = tk.StringVar(value="")
        self.cst_project = tk.StringVar(value="")
        self.cst_auto = tk.BooleanVar(value=True)
        self.cst_limit = tk.IntVar(value=0)
        self._row(t, 1, "Berkas sampel", lambda p: ttk.Entry(p, textvariable=self.cst_samples, width=44))
        ttk.Button(t, text="Pilih...", command=lambda: self._browse(self.cst_samples, paths.DATA_DIR)).grid(row=1, column=2, padx=6)
        self._row(t, 2, "Project .cst (opsional)", lambda p: ttk.Entry(p, textvariable=self.cst_project, width=44))
        ttk.Button(t, text="Pilih...", command=lambda: self._browse(self.cst_project, paths.CST_PROJECTS_DIR)).grid(row=2, column=2, padx=6)
        autowrap(ttk.Label(t, text="Kosongkan berkas sampel untuk memakai lhs_samples.csv; kosongkan project agar dideteksi dari CST.",
                           foreground="#666", wraplength=420, justify="left")).grid(row=3, column=1, columnspan=2, sticky="w")
        self._row(t, 4, "", lambda p: ttk.Checkbutton(p, text="Tekan Yes otomatis pada dialog CST yang dikenal (--auto-yes)", variable=self.cst_auto))
        self._row(t, 5, "Batas jumlah sampel", lambda p: ttk.Spinbox(p, from_=0, to=500, textvariable=self.cst_limit, width=8))
        bar = ttk.Frame(t)
        bar.grid(row=6, column=1, columnspan=2, sticky="ew", pady=10)
        for text, fn in [("Cek koneksi", self.do_probe), ("Cek sampel", self.do_check), ("Jalankan batch", self.do_batch)]:
            b = ttk.Button(bar, text=text, command=fn)
            b.pack(side="left", padx=(0, 8))
            self.buttons.append(b)
        make_flow(bar)
        self.cst_widgets = [w for w in _descendants(t) if w.winfo_class() in ("TEntry", "TButton", "TCheckbutton", "TSpinbox")]
        if not CST_OK:
            for w in self.cst_widgets:
                try:
                    w.state(["disabled"])
                except Exception:
                    pass
        pan = ttk.LabelFrame(R, text="Progres simulasi", padding=8)
        pan.pack(fill="both", expand=True)
        pan.columnconfigure(0, weight=1)
        self.sim_bar = ttk.Progressbar(pan, mode="determinate", maximum=1, value=0)
        self.sim_bar.grid(row=0, column=0, sticky="ew")
        self.sim_text = tk.StringVar(value="Memuat status ...")
        ttk.Label(pan, textvariable=self.sim_text, justify="left", wraplength=340).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(pan, foreground="#666", justify="left", wraplength=340,
                  text="Bilah: sampel yang sudah disimulasikan dibanding yang masih menunggu (lhs_samples.csv dan bo_candidates.csv)."
                  ).grid(row=2, column=0, sticky="w", pady=(8, 0))

    def _fill_qc(self):
        box, t, R = two_panes(self.tab_qc, right_width=420, min_total=900)
        box.pack(fill="both", expand=True)
        autowrap(ttk.Label(t, text="Pemeriksaan kualitas data hasil simulasi (tanpa CST).", wraplength=420, justify="left")
                 ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        bar = ttk.Frame(t)
        bar.grid(row=1, column=0, sticky="ew")
        t.columnconfigure(0, weight=1)
        for text, fn in [("QC dataset", self.do_qc), ("Verifikasi kurva S11", self.do_curves)]:
            b = ttk.Button(bar, text=text, command=fn)
            b.pack(side="left", padx=(0, 8))
            self.buttons.append(b)
        make_flow(bar)
        autowrap(ttk.Label(t, text="QC dataset harus berakhir \"Semua pemeriksaan lulus\"; verifikasi kurva harus \"KONSISTEN\".",
                           foreground="#666", wraplength=420, justify="left")).grid(row=2, column=0, sticky="w", pady=8)
        pan = ttk.LabelFrame(R, text="Ringkasan data", padding=8)
        pan.pack(fill="both", expand=True)
        self.qc_text = tk.StringVar(value="Memuat status ...")
        ttk.Label(pan, textvariable=self.qc_text, justify="left", wraplength=390).pack(anchor="w")
        pan2 = ttk.LabelFrame(R, text="QC terakhir (sesi ini)", padding=8)
        pan2.pack(fill="x", pady=(10, 0))
        self.qc_last_text = tk.StringVar(value="")
        ttk.Label(pan2, textvariable=self.qc_last_text, justify="left", wraplength=390).pack(anchor="w")
        self._render_qc_last()

    def _fill_gpr(self):
        t = self.tab_gpr
        t.columnconfigure(0, weight=1)
        t.rowconfigure(2, weight=1)
        top = ttk.Frame(t)
        top.grid(row=0, column=0, sticky="ew")
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
        make_flow(top)
        ttk.Label(t, text="Akurasi tiap target. Merah = R2 cross-validation di bawah 0,85 (indikator di proposal).",
                  foreground="#666").grid(row=1, column=0, sticky="w", pady=6)
        cols = ["target", "R2_test", "R2_cv", "RMSE_cv", "cov95"]
        box = ttk.Frame(t)
        box.grid(row=2, column=0, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        self.metrics = ttk.Treeview(box, columns=cols, show="headings", height=8)
        msb = ttk.Scrollbar(box, command=self.metrics.yview)
        self.metrics.configure(yscrollcommand=msb.set)
        msb.grid(row=0, column=1, sticky="ns")
        for c in cols:
            self.metrics.heading(c, text=c)
            self.metrics.column(c, width=140 if c == "target" else 100, anchor="w" if c == "target" else "e")
        self.metrics.tag_configure("low", foreground="#b00020")
        self.metrics.grid(row=0, column=0, sticky="nsew")
        # T2: analisis model dipindah dari tab 5 (isinya soal model, bukan soal usulan kandidat)
        an = ttk.LabelFrame(t, text="Analisis model", padding=(8, 4, 8, 6))
        an.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        an.columnconfigure(0, weight=1)
        autowrap(ttk.Label(an, foreground="#666", justify="left", wraplength=900,
                           text="Validasi maju menguji prediksi pada sampel yang datang belakangan; Sensitivitas memakai ARD dan Sobol; "
                                "Rentang parameter membuka dialog batas parameter (file desain tidak diedit)."
                           )).grid(row=0, column=0, sticky="ew")
        abar = ttk.Frame(an)
        abar.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        for text, fn in [("Validasi maju", self.do_validate), ("Validasi + bandingkan PoF (lambat)", self.do_validate_pof),
                         ("Sensitivitas (ARD, Sobol)", self.do_sensitivity)]:
            b = ttk.Button(abar, text=text, command=fn)
            b.pack(side="left", padx=(0, 8))
            self.buttons.append(b)
        ttk.Button(abar, text="Rentang parameter...", command=self.open_bounds).pack(side="left", padx=(8, 0))
        make_flow(abar)

    def _fill_bo(self):
        t = self.tab_bo
        t.columnconfigure(0, weight=1)
        t.rowconfigure(5, weight=1)
        top = ttk.Frame(t)
        top.grid(row=0, column=0, sticky="ew")
        self.bo_q = tk.IntVar(value=5)
        self.bo_kernel = tk.StringVar(value="rbf")
        self.bo_restarts = tk.IntVar(value=5)
        self.bo_stage = tk.StringVar(value="otomatis")
        self.bo_focus = tk.StringVar(value="otomatis")
        self.bo_constraint = tk.StringVar(value="")
        self.bo_region = tk.StringVar(value="")
        self.bo_region_auto = tk.StringVar(value="")
        self.bo_margin = tk.StringVar(value="")
        self.bo_calib = tk.BooleanVar(value=False)
        self.bo_comp = tk.BooleanVar(value=False)
        self.bo_sweep = tk.StringVar(value="")
        self.bo_div = tk.StringVar(value="")
        self.bo_radapt = tk.BooleanVar(value=False)
        ttk.Label(top, text="Jumlah kandidat").pack(side="left")
        ttk.Spinbox(top, from_=1, to=20, textvariable=self.bo_q, width=4).pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Kernel").pack(side="left")
        ttk.Combobox(top, textvariable=self.bo_kernel, values=["rbf", "matern52"], state="readonly", width=9).pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Restart").pack(side="left")
        ttk.Spinbox(top, from_=1, to=20, textvariable=self.bo_restarts, width=4).pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Tahap").pack(side="left")
        ttk.Combobox(top, textvariable=self.bo_stage, values=["otomatis", "1", "2"], state="readonly", width=9).pack(side="left", padx=(4, 12))
        make_flow(top)
        # T2: opsi lanjutan dapat dilipat, tertutup bawaan; jumlah opsi aktif tetap terlihat di judulnya
        self.adv_info = tk.StringVar(value="")
        self.adv = Collapsible(t, "Opsi lanjutan (kosong = perilaku bawaan)", open_=False, info_var=self.adv_info)
        self.adv.frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        adv = self.adv.body
        adv.columnconfigure(3, weight=1)
        ttk.Label(adv, text="Fokus").grid(row=0, column=0, sticky="w")
        self.focus_cb = ttk.Combobox(adv, textvariable=self.bo_focus, values=["otomatis"], state="readonly", width=12)
        self.focus_cb.grid(row=0, column=1, padx=(4, 12))
        ttk.Label(adv, text="Constraint fokus").grid(row=0, column=2, sticky="w")
        ttk.Entry(adv, textvariable=self.bo_constraint, width=34).grid(row=0, column=3, sticky="ew", padx=4)
        ttk.Label(adv, text="Region manual").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.e_region = ttk.Entry(adv, textvariable=self.bo_region, width=34)
        self.e_region.grid(row=1, column=1, sticky="w", padx=(4, 12), pady=(4, 0))
        ttk.Label(adv, text="atau otomatis K:margin").grid(row=1, column=2, sticky="w", padx=(0, 4), pady=(4, 0))
        self.e_region_auto = ttk.Entry(adv, textvariable=self.bo_region_auto, width=12)
        self.e_region_auto.grid(row=1, column=3, sticky="w", padx=4, pady=(4, 0))
        ttk.Label(adv, text="Margin PoF").grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(adv, textvariable=self.bo_margin, width=34).grid(row=2, column=1, sticky="w", padx=(4, 12), pady=(4, 0))
        chk = ttk.Frame(adv)
        chk.grid(row=2, column=2, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Checkbutton(chk, text="Kalibrasi std", variable=self.bo_calib).pack(side="left", padx=(4, 12))
        ttk.Checkbutton(chk, text="Gain komposit", variable=self.bo_comp).pack(side="left")
        ttk.Label(adv, text="Sweep batas").grid(row=3, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(adv, textvariable=self.bo_sweep, width=34).grid(row=3, column=1, sticky="w", padx=(4, 12), pady=(4, 0))
        sub = ttk.Frame(adv)
        sub.grid(row=3, column=2, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(sub, text="Diversity R").pack(side="left", padx=(4, 4))
        ttk.Entry(sub, textvariable=self.bo_div, width=6).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(sub, text="Region adaptif", variable=self.bo_radapt, command=self._toggle_radapt).pack(side="left")
        autowrap(ttk.Label(adv, foreground="#666", wraplength=950, justify="left",
                  text="contoh: constraint bw_mhz>=120 | region Lp=16:19,WD=7:8 | region otomatis 8:0.15 | margin fr_ghz=0.08 | "
                       "sweep gain_fr_ieee_dbi=4.0:5.4 (butuh Fokus dan jumlah kandidat >= 2; satu batas per kandidat) | "
                       "diversity 0.4 (R > 0.3 agar terasa) | region adaptif menggantikan region manual dan otomatis",
                  )).grid(row=4, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        for v in (self.bo_focus, self.bo_constraint, self.bo_region, self.bo_region_auto, self.bo_margin, self.bo_sweep,
                  self.bo_div, self.bo_calib, self.bo_comp, self.bo_radapt):
            v.trace_add("write", lambda *a: self._adv_count())
        # Auto run: logika ada di CLI `autorun`; GUI hanya membungkusnya sebagai subprocess
        self.auto_n = tk.IntVar(value=5)
        self.auto_qc = tk.BooleanVar(value=True)
        self.auto_train = tk.BooleanVar(value=True)
        self.auto_msg = tk.StringVar(value="")
        auto = ttk.Frame(t)
        auto.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        arow = ttk.Frame(auto)
        arow.pack(fill="x")
        ttk.Label(arow, text="Auto run: batch").pack(side="left")
        ttk.Spinbox(arow, from_=1, to=99, textvariable=self.auto_n, width=4).pack(side="left", padx=(4, 12))
        ttk.Checkbutton(arow, text="QC", variable=self.auto_qc).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(arow, text="Latih GPR", variable=self.auto_train).pack(side="left", padx=(0, 12))
        self.auto_btn = ttk.Button(arow, text="Mulai auto run", command=self.do_autorun)
        self.auto_btn.pack(side="left")
        self.buttons.append(self.auto_btn)
        if not CST_OK:
            self.auto_btn.state(["disabled"])
        make_flow(arow)
        autowrap(ttk.Label(auto, textvariable=self.auto_msg, foreground="#666", wraplength=900, justify="left")).pack(fill="x", pady=(2, 0))
        self._auto_box = (top, self.adv.body, arow)
        bar = ttk.Frame(t)
        bar.grid(row=3, column=0, sticky="ew", pady=8)
        for text, fn in [("Usulkan kandidat", self.do_suggest), ("Kurva konvergensi", self.do_report), ("Uji BO vs acak (backtest)", self.do_backtest)]:
            b = ttk.Button(bar, text=text, command=fn)
            b.pack(side="left", padx=(0, 8))
            self.buttons.append(b)
        ttk.Button(bar, text="Pakai kandidat di tab 2", command=self.use_candidates).pack(side="left", padx=(8, 0))
        make_flow(bar)
        autowrap(ttk.Label(t, textvariable=self.warn_var, foreground="#b45f06", wraplength=1000)).grid(row=4, column=0, sticky="w")
        cbox = ttk.Frame(t)
        cbox.grid(row=5, column=0, sticky="nsew", pady=(4, 0))
        cbox.columnconfigure(0, weight=1)
        cbox.rowconfigure(0, weight=1)
        self.cand = ttk.Treeview(cbox, show="headings", height=8)
        csb = ttk.Scrollbar(cbox, command=self.cand.yview)
        self.cand.configure(yscrollcommand=csb.set)
        self.cand.grid(row=0, column=0, sticky="nsew")
        csb.grid(row=0, column=1, sticky="ns")

    def _adv_count(self):
        """Jumlah opsi lanjutan yang terisi (ditampilkan di judul bagian terlipat agar tidak ada setelan tersembunyi)."""
        n = sum(1 for v in (self.bo_constraint, self.bo_region, self.bo_region_auto, self.bo_margin, self.bo_sweep, self.bo_div)
                if v.get().strip())
        n += 1 if self.bo_focus.get() not in ("", "otomatis") else 0
        n += sum(1 for v in (self.bo_calib, self.bo_comp, self.bo_radapt) if v.get())
        self.adv_info.set(f"{n} opsi aktif" if n else "")

    def _fill_results(self):
        t = self.tab_res
        t.columnconfigure(0, weight=1)
        t.rowconfigure(1, weight=1)
        top = ttk.Frame(t)
        top.grid(row=0, column=0, sticky="ew")
        self.fig_var = tk.StringVar()
        row_a = ttk.Frame(top)
        row_a.pack(fill="x")
        ttk.Label(row_a, text="Gambar").pack(side="left")
        self.fig_cb = ttk.Combobox(row_a, textvariable=self.fig_var, state="readonly", width=34)
        self.fig_cb.pack(side="left", padx=6)
        self.fig_cb.bind("<<ComboboxSelected>>", lambda e: self._draw_figure())
        ttk.Button(row_a, text="Buka folder gambar", command=lambda: self.open_data("figures")).pack(side="left", padx=6)
        b = ttk.Button(row_a, text="Buat kurva Pareto (semua run)", command=self.do_pareto)
        b.pack(side="left", padx=6)
        self.buttons.append(b)
        make_flow(row_a)
        row_b = ttk.Frame(top)
        row_b.pack(fill="x", pady=(6, 0))
        self.rep_focus = tk.StringVar(value="")
        self.rep_constraint = tk.StringVar(value="")
        self.rep_scope = tk.StringVar(value=REPORT_SCOPES[0])
        ttk.Label(row_b, text="Laporan untuk").pack(side="left")
        ttk.Combobox(row_b, textvariable=self.rep_scope, values=REPORT_SCOPES, state="readonly", width=22).pack(side="left", padx=(4, 10))
        ttk.Label(row_b, text="fokus").pack(side="left")
        ttk.Combobox(row_b, textvariable=self.rep_focus, values=["", "bw", "cover", "gain"], state="readonly", width=7).pack(side="left", padx=(4, 10))
        ttk.Label(row_b, text="constraint (pisahkan dengan ;)").pack(side="left")
        ttk.Entry(row_b, textvariable=self.rep_constraint, width=46).pack(side="left", padx=(4, 8))
        b = ttk.Button(row_b, text="Buat laporan", command=self.do_make_report)
        b.pack(side="left", padx=(0, 6))
        self.buttons.append(b)
        ttk.Button(row_b, text="Buka folder laporan", command=self.open_compare).pack(side="left")
        make_flow(row_b)
        autowrap(ttk.Label(t, foreground="#666", text="contoh constraint: MicrostripAntena_RO4350B:gain_fr_ieee_dbi>=5.0; MicrostripAntena_RO4350B:gain_fr_ieee_dbi>=4.0   (keluaran: data/_report_<run> untuk desain terpilih, data/_compare untuk gabungan)",
                  )).grid(row=2, column=0, sticky="ew")
        if ZoomImage is not None:                              # dengan Pillow: zoom (roda mouse), geser (seret), simpan tampilan
            self.zoom = ZoomImage(t)
            self.zoom.grid(row=1, column=0, sticky="nsew", pady=8)
            self.fig_label = None
        else:                                                  # tanpa Pillow: gambar diam seperti sebelumnya
            self.zoom = None
            self.fig_label = ttk.Label(t, anchor="center")
            self.fig_label.grid(row=1, column=0, sticky="nsew", pady=8)
            self.fig_label.bind("<Configure>", lambda e: self._draw_figure())
        self.fig_paths = {}
        self.extra_figs = {}                                   # gambar di luar folder figures run (mis. Pareto)

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
        self._render_panels(s)
        self._load_metrics()
        self._load_candidates()
        self._load_figure_list()
        self.data_tab.sync(s.get("run"), s.get("feasible_ids"))
        self.focus_cb.configure(values=["otomatis"] + list(s.get("foci", [])))
        if self.bo_focus.get() not in self.focus_cb.cget("values"):
            self.bo_focus.set("otomatis")

    def _set_status_text(self, text, tags=None):
        self._status_full = self._status_compact = [(text, tags or ())]
        self._apply_status()

    def toggle_status_detail(self):
        self.status_detail = not self.status_detail
        self.detail_btn.configure(text="Ringkas" if self.status_detail else "Detail")
        self._apply_status()

    def _apply_status(self):
        """Tampilkan status ringkas (2 baris, huruf proporsional) atau detail (semua baris, huruf lebar tetap)."""
        segs = self._status_full if self.status_detail else self._status_compact
        n = sum(t.count("\n") for t, _ in segs) + (0 if segs and segs[-1][0].endswith("\n") else 1)
        tw = self.status_text
        tw.configure(state="normal", font="TkFixedFont" if self.status_detail else "TkDefaultFont",
                     height=max(2, min(n, 12)))
        tw.delete("1.0", "end")
        for text, tags in segs:
            tw.insert("end", text, tags)
        tw.configure(state="disabled")

    def _render_status(self, s):
        if "error" in s and "run" not in s:
            self._set_status_text(s["error"], ("err",))
            return
        full, compact, warns = [], [], []

        def w(_end, text, tags=()):
            full.append((text, tags))
        w("end", f"Desain  : {s['design']} ({s['design_name']})\nRun     : {s['run']}   {s['run_dir']}\n")
        line1 = f"{s['design']}"          # nama run dan folder ada di tampilan Detail (baris ringkas harus muat di layar 1366 px)
        if "note" in s:
            w("end", s["note"] + "\n", ("warn",))
            warns.append(s["note"])
        if "error" in s:
            w("end", f"[error] dataset gagal dimuat: {s['error']}\n", ("err",))
            warns.append("dataset gagal dimuat")
        line2 = ""
        if "n_samples" in s:
            st = s["stage"]
            w("end", f"Sampel  : {s['n_samples']} (awal {s['n_initial']}, BO {s['n_bo']})   "
                     f"Tahap BO: {st['index']}/{st['total']} {st['name']}   "
                     f"objective: {s['objective']['goal']} {s['objective']['column']}\n")
            w("end", f"Feasible: {s['n_feasible']} dari {s['n_samples']} memenuhi constraint tahap ini\n")
            line1 += f"  |  {s['n_samples']} sampel (BO {s['n_bo']})  |  tahap {st['index']}/{st['total']}  |  feasible {s['n_feasible']}"
            if "best" in s:
                b = s["best"]
                extra = "  ".join(f"{k}={b[k]:.3g}" for k in ("fr_ghz", "rl_min_db", "bw_mhz", "gain_fr_ieee_dbi")
                                  if k in b and k != s["objective"]["column"])
                tag = "Terbaik " if b["feasible"] else "Terbaik (belum ada yang feasible) "
                w("end", f"{tag}: sampel {b['sample_id']}   {s['objective']['column']}={b['value']:.4g}   {extra}\n")
                line2 = f"{tag.strip()}: sampel {b['sample_id']}   {s['objective']['column']}={b['value']:.4g}   {extra}"
            for h in s.get("bound_hits", []):
                msg = f"{h['param']} menempel batas {h['side']} ({h['bound']:g}) pada {h['n']}/{h['of']} desain terbaik"
                w("end", f"[peringatan] {msg}\n", ("warn",))
                warns.append(msg)
        if s.get("bounds_changed"):
            w("end", f"[opsi] Rentang parameter: override aktif ({', '.join(s['bounds_changed'])}); lihat tombol Rentang parameter... di tab 5\n", ("warn",))
            warns.append("rentang parameter: override aktif")
        f = s.get("files", {})
        parts = []
        for key, label in [("lhs_samples", "lhs_samples"), ("bo_candidates", "kandidat BO"), ("models", "model GPR")]:
            if key in f:
                parts.append(f"{label}: {'ada' if f[key]['exists'] else 'belum'}")
        if parts:
            w("end", "Berkas  : " + "   ".join(parts) + "\n")
        compact.append((line1 + "\n", ()))
        compact.append((line2, ()))
        if warns:
            compact.append(((("   " if line2 else "") + f"[{len(warns)} catatan: tekan Detail]"), ("warn",)))
        self._status_full, self._status_compact = full, compact
        self._apply_status()

    # ------------------------------------------------------------------ T2: panel info tab 1 sampai 3
    def _render_panels(self, s):
        """Isi panel kanan tab 1 sampai 3 dari status (tanpa memuat model)."""
        for r in self.rng_tree.get_children():
            self.rng_tree.delete(r)
        for p in s.get("params", []):
            chg = p.get("changed")
            st = f"override (file: {p['base_lo']:g} sampai {p['base_hi']:g})" if chg else "file desain"
            self.rng_tree.insert("", "end", tags=("chg",) if chg else (),
                                 values=[p["name"], f"{p['lo']:g}", f"{p['hi']:g}", st])
        if "params_error" in s:
            self.lhs_info.set("Rentang tidak terbaca: " + s["params_error"])
        elif s.get("n_lhs"):
            self.lhs_info.set(f"lhs_samples.csv: {s['n_lhs']} baris (diubah {s.get('lhs_time') or '?'})")
        elif "run" in s:
            self.lhs_info.set("lhs_samples.csv: belum ada")
        else:
            self.lhs_info.set("")
        n, pl, pb = s.get("n_samples", 0), s.get("pending_lhs", 0), s.get("pending_bo", 0)
        if "run" not in s:
            self.sim_bar.configure(maximum=1, value=0)
            self.sim_text.set(s.get("error", "Status belum tersedia."))
        else:
            self.sim_bar.configure(maximum=max(1, n + pl + pb), value=n)
            nc = s.get("n_curves", 0)
            lines = [f"Dataset: {n} sampel sudah disimulasikan",
                     f"Menunggu simulasi: {pl} dari lhs_samples.csv, {pb} dari bo_candidates.csv",
                     f"Simulasi terakhir: {s.get('last_sim') or 'belum ada dataset'}",
                     f"Kurva S11: {nc} berkas" + ("" if nc == n else f" (dataset {n} baris, selisih {abs(nc - n)})"),
                     "CST: " + ("terdeteksi" if CST_OK else "tidak terdeteksi (tombol jalankan nonaktif)")]
            self.sim_text.set("\n".join(lines))
        q = s.get("qc_view")
        if not q:
            self.qc_text.set(s.get("note") or s.get("error") or "Belum ada data untuk diringkas.")
        else:
            lo, hi = q["band"]
            L = [f"Sampel: {q['n']}   |   kurva S11: {q['n_curves']} berkas"]
            if "in_band" in q:
                L.append(f"fr di pita {lo:g} sampai {hi:g} GHz: {q['in_band']} dari {q['n']}")
            if "rl_ok" in q:
                L.append(f"RL minimum <= {q['rl_limit']:g} dB: {q['rl_ok']} dari {q['n']}")
            if "gain_max" in q:
                L.append(f"Gain di fr: median {q['gain_median']:.2f}, maksimum {q['gain_max']:.2f} dBi")
            if "bw_max" in q:
                L.append(f"BW maksimum: {q['bw_max']:.1f} MHz")
            L.append(f"Sel target kosong: {q['nan_cells']}")
            self.qc_text.set("\n".join(L))

    def _render_qc_last(self):
        self.qc_last_text.set(f"QC dataset: {self.qc_last['qc']}\nKurva S11: {self.qc_last['curves']}")

    def _note_qc(self, name, rc):
        """Simpan ringkasan hasil `qc` / `curves` dari keluarannya (hanya untuk panel tab 3)."""
        if name not in ("qc", "curves") or self._user_stopped:
            return
        lines, stamp = self._cap, time.strftime("%H:%M")
        bad = sum(1 for x in lines if "[MASALAH]" in x)
        if name == "qc":
            if rc != 0 and not lines:
                res = f"gagal (kode {rc})"
            elif any("Semua pemeriksaan lulus" in x for x in lines):
                res = "semua pemeriksaan lulus"
            else:
                res = f"{bad} masalah (lihat log)" if bad else f"selesai kode {rc}, hasil tidak dikenali (lihat log)"
        else:
            if any("kurva KONSISTEN" in x for x in lines) and not bad:
                res = "KONSISTEN"
            elif any("KESIMPULAN" in x for x in lines) or bad:
                res = "TIDAK konsisten (lihat log)"
            else:
                res = f"selesai kode {rc}, hasil tidak dikenali (lihat log)"
        self.qc_last[name] = f"{res} ({stamp})"
        self._render_qc_last()

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
        want = ["sample_id", "sweep_bound", "acq", "pof", f"pred_{oc}", f"std_{oc}", "Lp", "Wp", "LU", "WU", "WD"]
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
        self.fig_paths.update(self.extra_figs)
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

    def show_path(self, path):
        """Tampilkan gambar dari jalur sembarang (mis. data/_compare/pareto.png)."""
        if os.path.exists(path):
            self.extra_figs[os.path.basename(path)] = path
            self._load_figure_list()
            self.fig_var.set(os.path.basename(path))
            self._draw_figure()
        self.nb.select(self.tab_res)

    def _draw_figure(self):
        path = self.fig_paths.get(self.fig_var.get())
        if self.zoom is not None:
            if not path or not os.path.exists(path):
                self._zoom_path = None
                self.zoom.set_message("Belum ada gambar. Jalankan Latih (tab 4) atau Kurva konvergensi (tab 5).")
            elif (path, os.path.getmtime(path)) != self._zoom_path:      # jangan reset zoom bila gambar sama
                self._zoom_path = (path, os.path.getmtime(path))
                self.zoom.set_image(path)
            return
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
        self._cur_cmd, self._cap = argv[0], []
        self._set_log_open(True, auto=True)          # log terbuka otomatis selama perintah berjalan
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
        if self._cur_cmd == "autorun":
            if line.startswith("[autorun] {") and self._auto_progress(line):
                return
            if "BERHENTI" in line or "dihentikan" in line:
                self._auto_last = line.replace("[autorun] ", "", 1).strip()
        if self._cur_cmd in ("qc", "curves") and len(self._cap) < 2000:
            self._cap.append(line)
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
            for w in list(self.cst_widgets) + [self.auto_btn]:
                try:
                    w.state(["disabled"])
                except Exception:
                    pass
        ok = rc == 0
        if argv[0] == "autorun":
            self._auto_finish(rc, self._user_stopped)
        self._note_qc(argv[0], rc)
        if self._user_stopped:
            self._user_stopped = False
            self.state_var.set("Dihentikan")
        else:
            self.state_var.set("Siap" if ok else f"Selesai dengan kode {rc}")
            self._log(f"[{'selesai' if ok else 'gagal, kode ' + str(rc)}: {argv[0]}]\n\n", "ok" if ok else "bad")
        self._status_busy = False
        self.refresh_status()
        if ok and self._log_open and self._log_auto:     # berhasil dan dibuka otomatis: lipat lagi setelah 3 detik (kecuali sedang dibaca)
            self._cancel_collapse()
            self._collapse_job = self.root.after(3000, self._auto_collapse)
        if ok and after:
            self.root.after(400, after)

    def _auto_collapse(self):
        self._collapse_job = None
        if self._log_open and self._log_auto and not self.runner.busy:
            self._set_log_open(False)

    def stop(self):
        self._user_stopped = self.runner.busy
        self.runner.stop()
        self._log("[dihentikan oleh pengguna] Bila sedang menjalankan CST, simulasi yang berjalan mungkin masih selesai di CST.\n", "bad")

    def _log(self, text, tag=None):
        last = [ln for ln in text.splitlines() if ln.strip()]
        if last:                                         # baris terakhir tampil di bilah log saat terlipat
            self.last_var.set(last[-1].strip())
            self.last_lbl.configure(foreground=theme.color({"ok": "ok", "bad": "bad", "warn": "warn", "cmd": "info"}.get(tag, "muted")))
        self.log.configure(state="normal")
        self.log.insert("end", text, (tag,) if tag else ())
        n = int(self.log.index("end-1c").split(".")[0])
        if n > LOG_MAX_LINES:
            self.log.delete("1.0", f"{n - LOG_MAX_LINES}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self):
        self.last_var.set("")
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

    def _suggest_argv(self, report=False):
        focus = self.bo_focus.get()
        focus = None if focus in ("", "otomatis") else focus
        return cmd.suggest(self.bo_q.get(), self.bo_kernel.get(), self.bo_restarts.get(), self._stage(), self.design(),
                           report=report, focus=focus, constraint=self.bo_constraint.get().strip() or None,
                           region=self.bo_region.get().strip() or None, region_auto=self.bo_region_auto.get().strip() or None,
                           margin=self.bo_margin.get().strip() or None, calibrate=self.bo_calib.get(),
                           composite=self.bo_comp.get(), sweep=self.bo_sweep.get().strip() or None,
                           diversity=self.bo_div.get().strip() or None, region_adapt=self.bo_radapt.get())

    def _toggle_radapt(self):
        """Region adaptif saling eksklusif dengan region manual dan otomatis."""
        on = self.bo_radapt.get()
        if on:
            self.bo_region.set("")
            self.bo_region_auto.set("")
        for e in (self.e_region, self.e_region_auto):
            e.configure(state="disabled" if on else "normal")

    def _check_bo_inputs(self):
        """Periksa opsi BO sebelum menjalankan; tampilkan pesan ramah, bukan galat CLI."""
        sweep, div = self.bo_sweep.get().strip(), self.bo_div.get().strip()
        if sweep:
            m = re.fullmatch(r"\s*([A-Za-z_][\w]*)\s*=\s*(-?\d+(?:\.\d+)?)\s*:\s*(-?\d+(?:\.\d+)?)\s*", sweep)
            if not m:
                messagebox.showwarning("Sweep", "Format sweep: KOLOM=LO:HI, mis. gain_fr_ieee_dbi=4.0:5.4")
                self.adv.set_open(True)
                return False
            if self.bo_focus.get() in ("", "otomatis"):
                messagebox.showwarning("Sweep", "Sweep hanya dipakai bersama Fokus (pilih fokus di Opsi lanjutan) dan KOLOM harus constraint fokus itu "
                                       "(tambahkan lewat Constraint fokus bila perlu).")
                self.adv.set_open(True)
                return False
            if int(self.bo_q.get()) < 2:
                messagebox.showwarning("Sweep", "Sweep butuh jumlah kandidat minimal 2.")
                self.adv.set_open(True)
                return False
        if div:
            try:
                ok = float(div) > 0
            except ValueError:
                ok = False
            if not ok:
                messagebox.showwarning("Diversity", "Diversity R harus angka lebih dari 0 (mis. 0.4).")
                self.adv.set_open(True)
                return False
        return True

    # ------------------------------------------------------------------ auto run
    def _lock_bo(self, lock):
        """Kunci (atau buka) semua masukan tab 5 selama auto run, agar opsi yang dibaca saat Mulai tidak berubah."""
        for box in self._auto_box:
            for w in _descendants(box):
                if w.winfo_class() in ("TEntry", "TCombobox", "TSpinbox", "TCheckbutton"):
                    try:
                        w.state(["disabled"] if lock else ["!disabled"])
                    except Exception:
                        pass
        if not lock:
            self._toggle_radapt()                      # keadaan entri region mengikuti kotak Region adaptif lagi

    def do_autorun(self):
        if self.runner.busy:
            messagebox.showinfo("Sedang berjalan", "Masih ada proses yang berjalan. Tunggu atau tekan Hentikan.")
            return
        try:
            n, q = int(self.auto_n.get()), int(self.bo_q.get())
            if not 1 <= n <= 99:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showwarning("Auto run", "Jumlah batch harus bilangan bulat 1 sampai 99.")
            return
        if not self._check_bo_inputs():
            return
        st = getattr(self, "status", None) or {}
        pend = int(st.get("pending_lhs", 0) or 0) + int(st.get("pending_bo", 0) or 0)
        mins = cmd.autorun_minutes(n, q, pend)
        argv = cmd.autorun(n, self.auto_qc.get(), self.auto_train.get(), self.design(), self.cst_project.get().strip() or None,
                           self._suggest_argv())
        text = (f"Auto run {n} batch, {q} kandidat per batch, sampel menunggu {pend}.\n\n"
                f"Estimasi simulasi: ({n} x {q} + {pend}) x 5 menit = {mins:.0f} menit (sekitar {mins / 60:.1f} jam), "
                f"belum termasuk suggest, QC, dan latih GPR.\n\n"
                "Semua opsi tab 5 dibaca sekarang lalu dikunci sampai selesai. Hentikan kapan saja; sampel yang sudah "
                "disimulasikan dilewati saat dilanjutkan.\n\nMulai?")
        if not messagebox.askokcancel("Mulai auto run", text):
            return
        self._auto_active, self._auto_last = True, ""
        self._lock_bo(True)
        self.auto_msg.set(f"Batch 1/{n}: memulai ...")
        self.run_cmd(argv)

    def _auto_progress(self, line):
        try:
            d = json.loads(line[len("[autorun] "):])
        except ValueError:
            return False
        txt = cmd.autorun_text(d)
        if txt:
            self.auto_msg.set(txt)
            self.state_var.set("Auto run: " + txt)
        if d.get("step") == "selesai" and not self._status_busy:
            self.refresh_status()                      # angka sampel dan terbaik di panel ikut diperbarui tiap batch
        return True

    def _auto_finish(self, rc, stopped):
        self._auto_active = False
        self._lock_bo(False)
        if stopped or rc == 130:
            self.auto_msg.set("Dihentikan. Jalankan lagi untuk melanjutkan; sampel yang sudah ada dilewati.")
        elif rc == 0:
            self.auto_msg.set(self.auto_msg.get() if self.auto_msg.get().startswith("Selesai") else "Selesai.")
        else:
            self.auto_msg.set(f"Berhenti (kode {rc}). " + (self._auto_last or "Lihat log."))

    def do_suggest(self):
        if not self._check_bo_inputs():
            return
        self.run_cmd(self._suggest_argv())

    def _focus_or_none(self):
        f = self.bo_focus.get()
        return None if f in ("", "otomatis") else f

    def do_validate(self, pof_compare=False):
        self.run_cmd(cmd.validate(self.design(), 5, self.bo_restarts.get(), self.bo_kernel.get(), pof_compare,
                                  self._focus_or_none(), self.bo_constraint.get().strip() or None),
                     after=lambda: self.show_figure("forward_validation.png"))

    def do_validate_pof(self):
        self.do_validate(pof_compare=True)

    def do_sensitivity(self):
        self.run_cmd(cmd.sensitivity(self.design(), self.bo_region_auto.get().strip() or None, self.bo_restarts.get(), self.bo_kernel.get()),
                     after=lambda: self.show_figure("sensitivity.png"))

    def _report_target(self):
        """(runs, folder keluaran). Desain terpilih: hanya run itu ke data/_report_<run>; gabungan: semua run ke data/_compare."""
        if self.rep_scope.get() == REPORT_SCOPES[0]:
            run = self.run_name()
            if run:
                return [run], os.path.join(paths.DATA_DIR, f"_report_{run}")
            return None, None
        return None, os.path.join(paths.DATA_DIR, "_compare")

    def do_make_report(self):
        runs, out = self._report_target()
        if out is None:
            messagebox.showwarning("Laporan", "Run desain belum diketahui (status belum dimuat). Tekan Muat ulang status, atau pilih Semua desain (gabungan).")
            return
        cons = [c.strip() for c in self.rep_constraint.get().split(";") if c.strip()]
        self.run_cmd(cmd.report(runs, self.rep_focus.get() or None, cons, out_dir=(out if runs else None)),
                     after=lambda: self.show_path(os.path.join(out, "pareto.png")))

    def open_bounds(self):
        if self._auto_active:
            messagebox.showinfo("Auto run", "Rentang parameter dikunci selama auto run berjalan (suggest membacanya tiap batch). Hentikan auto run dulu.")
            return
        from cstopt.gui.bounds_dialog import BoundsDialog
        dlg = getattr(self, "_bounds_dlg", None)
        if dlg is not None and dlg.top.winfo_exists():
            dlg.top.lift()
            return
        self._bounds_dlg = BoundsDialog(self)

    def open_compare(self):
        d = self._report_target()[1] or os.path.join(paths.DATA_DIR, "_compare")
        if not os.path.isdir(d):
            messagebox.showinfo("Belum ada", f"Folder belum ada (jalankan Buat laporan dulu):\n{d}")
            return
        open_path(d)

    def do_report(self):
        self.run_cmd(self._suggest_argv(report=True), after=lambda: self.show_figure("bo_convergence.png"))

    def do_pareto(self):
        self.run_cmd(cmd.pareto(), after=lambda: self.show_path(os.path.join(paths.DATA_DIR, "_compare", "pareto.png")))

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
