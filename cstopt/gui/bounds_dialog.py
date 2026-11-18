"""Dialog "Rentang parameter" (G2b): pembungkus tipis atas `py main.py bounds --json`. Semua logika (usulan, validasi, penulisan override)
ada di cstopt/ml/bounds.py; dialog hanya menampilkan dan memanggilnya, jadi perilaku GUI dan CLI sama."""
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from cstopt.gui import commands as cmd


def _fmt(v):
    return format(float(v), ".6f").rstrip("0").rstrip(".")


class BoundsDialog:
    def __init__(self, app):
        self.app = app
        self.top = tk.Toplevel(app.root)
        self.top.title("Rentang parameter (BOUNDS)")
        self.top.geometry("980x700")
        self.top.minsize(860, 560)
        self.top.transient(app.root)
        self.q = queue.Queue()
        self.busy = False
        self.rows = {}              # param -> dict(lo=StringVar, hi=StringVar, base=Label, data=Label, stick=Label, mark=Label)
        self.active = {}            # param -> (lo, hi) tersimpan (aktif saat ini)
        self.base = {}              # param -> (lo, hi) file desain
        self.changed = []           # parameter yang berbeda dari file desain (override)
        self.widen = tk.StringVar(value="0.2")
        self.status_var = tk.StringVar(value="")
        self._build()
        self.top.protocol("WM_DELETE_WINDOW", self.top.destroy)
        self._poll()
        self.reload()

    # ------------------------------------------------------------------ tampilan
    def _build(self):
        t = self.top
        t.columnconfigure(0, weight=1)
        t.rowconfigure(2, weight=1)
        ttk.Label(t, wraplength=940, justify="left", foreground="#444", text=(
            "Rentang parameter adalah domain global yang dijelajahi LHS dan BO. Mengubahnya mengubah normalisasi ruang satuan: hasil Usulkan "
            "kandidat setelahnya TIDAK identik dengan sebelumnya, jalankan Latih model ulang, dan pastikan geometri baru bisa disimulasikan di CST. "
            "Ini berbeda dari Region (subset pencarian per putaran di tab 5). File desain tidak diubah; disimpan sebagai "
            "data/<RUN>/bounds_override.json.")).grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        bar = ttk.Frame(t)
        bar.grid(row=1, column=0, sticky="w", padx=10, pady=(4, 6))
        ttk.Label(bar, text="Lebar usulan").pack(side="left")
        ttk.Spinbox(bar, from_=0.05, to=1.0, increment=0.05, textvariable=self.widen, width=5).pack(side="left", padx=(4, 10))
        self.btns = []
        for text, fn in [("Usulkan pelebaran", self.propose), ("Periksa geometri", self.check), ("Simpan override", self.save),
                         ("Kembalikan ke bawaan", self.reset), ("Muat ulang", self.reload)]:
            b = ttk.Button(bar, text=text, command=fn)
            b.pack(side="left", padx=(0, 6))
            self.btns.append(b)
        ttk.Button(bar, text="Tutup", command=t.destroy).pack(side="left", padx=(12, 0))
        mid = ttk.Frame(t)
        mid.grid(row=2, column=0, sticky="nsew", padx=10)
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(0, weight=1)
        canvas = tk.Canvas(mid, highlightthickness=0, height=300)
        sb = ttk.Scrollbar(mid, orient="vertical", command=canvas.yview)
        self.grid_frame = ttk.Frame(canvas)
        self.grid_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        for c, (text, w) in enumerate([("Parameter", 9), ("File desain", 17), ("Min aktif", 10), ("Max aktif", 10),
                                       ("Rentang data", 19), ("Menempel batas", 14), ("Status", 14)]):
            ttk.Label(self.grid_frame, text=text, font=("TkDefaultFont", 9, "bold"), width=w).grid(row=0, column=c, padx=3, pady=(0, 4), sticky="w")
        ttk.Label(t, textvariable=self.status_var, foreground="#555").grid(row=3, column=0, sticky="w", padx=10, pady=(4, 0))
        self.msg = tk.Text(t, height=9, wrap="word", state="disabled", background="#f5f5f5", relief="flat", padx=8, pady=6)
        self.msg.tag_configure("warn", foreground="#b45f06")
        self.msg.tag_configure("err", foreground="#b00020")
        self.msg.tag_configure("ok", foreground="#2e7d32")
        self.msg.grid(row=4, column=0, sticky="ew", padx=10, pady=(4, 10))

    def _say(self, lines, tag=None):
        self.msg.configure(state="normal")
        self.msg.delete("1.0", "end")
        for ln in lines:
            t = tag
            if ln.startswith("[peringatan]"):
                t = "warn"
            self.msg.insert("end", ln + "\n", (t,) if t else ())
        self.msg.configure(state="disabled")

    def _ensure_rows(self, params):
        if self.rows:
            return
        for i, p in enumerate(params, start=1):
            r = {"lo": tk.StringVar(), "hi": tk.StringVar()}
            ttk.Label(self.grid_frame, text=p, width=9).grid(row=i, column=0, padx=3, pady=1, sticky="w")
            r["base"] = ttk.Label(self.grid_frame, width=17)
            r["base"].grid(row=i, column=1, padx=3, sticky="w")
            ttk.Entry(self.grid_frame, textvariable=r["lo"], width=10).grid(row=i, column=2, padx=3)
            ttk.Entry(self.grid_frame, textvariable=r["hi"], width=10).grid(row=i, column=3, padx=3)
            r["data"] = ttk.Label(self.grid_frame, width=19)
            r["data"].grid(row=i, column=4, padx=3, sticky="w")
            r["stick"] = ttk.Label(self.grid_frame, width=14, foreground="#b45f06")
            r["stick"].grid(row=i, column=5, padx=3, sticky="w")
            r["mark"] = ttk.Label(self.grid_frame, width=14)
            r["mark"].grid(row=i, column=6, padx=3, sticky="w")
            for v in (r["lo"], r["hi"]):
                v.trace_add("write", lambda *a, name=p: self._update_mark(name))
            self.rows[p] = r

    def _update_mark(self, p):
        r = self.rows[p]
        a = self.active.get(p)
        try:
            lo, hi = float(r["lo"].get()), float(r["hi"].get())
        except ValueError:
            r["mark"].configure(text="angka tidak valid", foreground="#b00020")
            return
        if a is not None and (abs(lo - a[0]) > 1e-9 or abs(hi - a[1]) > 1e-9):
            r["mark"].configure(text="diubah (belum simpan)", foreground="#b45f06")
        elif p in self.changed:
            r["mark"].configure(text="override", foreground="#1565c0")
        else:
            r["mark"].configure(text="", foreground="#000")

    def _fill(self, table, changed):
        self.changed = list(changed)
        self._ensure_rows([r["param"] for r in table])
        for r in table:
            p, row = r["param"], self.rows[r["param"]]
            self.active[p] = tuple(r["active"])
            self.base[p] = tuple(r["base"])
            row["lo"].set(_fmt(r["active"][0]))
            row["hi"].set(_fmt(r["active"][1]))
            row["base"].configure(text=f"{r['base'][0]:g} .. {r['base'][1]:g}")
            row["data"].configure(text=f"{r['data'][0]:.2f} .. {r['data'][1]:.2f}")
            row["stick"].configure(text=r["sticky"] or "")
            self._update_mark(p)

    # ------------------------------------------------------------------ pemanggilan CLI (di thread, hasil lewat antrean)
    def _set_busy(self, on, text=""):
        self.busy = on
        for b in self.btns:
            b.configure(state="disabled" if on else "normal")
        self.status_var.set(text)

    def _call(self, argv, done, text="Menjalankan..."):
        if self.busy:
            return
        self._set_busy(True, text)

        def work():
            self.q.put((done, self.app.runner.capture_json(argv)))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        if not self.top.winfo_exists():
            return
        try:
            while True:
                done, res = self.q.get_nowait()
                self._set_busy(False, "")
                done(res)
        except queue.Empty:
            pass
        self.top.after(100, self._poll)

    # ------------------------------------------------------------------ aksi
    def _read_entries(self):
        """{param: (lo, hi)} dari kolom, atau None bila ada yang tidak valid (pesan sudah ditampilkan)."""
        out = {}
        for p, r in self.rows.items():
            try:
                lo, hi = float(r["lo"].get()), float(r["hi"].get())
            except ValueError:
                self._say([f"{p}: nilai harus angka."], "err")
                return None
            if not lo < hi:
                self._say([f"{p}: min ({lo:g}) harus lebih kecil dari max ({hi:g})."], "err")
                return None
            out[p] = (lo, hi)
        return out

    def _diff_set(self):
        vals = self._read_entries()
        if vals is None:
            return None
        parts = [f"{p}={_fmt(lo)}:{_fmt(hi)}" for p, (lo, hi) in vals.items()
                 if abs(lo - self.active[p][0]) > 1e-9 or abs(hi - self.active[p][1]) > 1e-9]
        return ",".join(parts)

    def _fail(self, res):
        if "error" in res:
            self._say([f"[galat] {str(res['error']).replace('status gagal: ', '')}"], "err")
            return True
        return False

    def reload(self):
        def done(res):
            if self._fail(res):
                return
            self._fill(res["table"], res.get("changed", []))
            n = len(res.get("changed", []))
            self._say([f"Rentang aktif dimuat. Override: {n} parameter berbeda dari file desain." if n
                       else "Rentang aktif = file desain (tidak ada override).",
                       "Parameter yang menempel batas dihitung dari 10 desain terbaik dan kandidat BO terakhir."])
        self._call(cmd.bounds(self.app.design()), done, "Memuat rentang dan data (beberapa detik)...")

    def propose(self):
        try:
            w = float(self.widen.get())
            if w <= 0:
                raise ValueError
        except ValueError:
            self._say(["Lebar usulan harus angka lebih dari 0 (mis. 0.2)."], "err")
            return

        def done(res):
            if self._fail(res):
                return
            prop = res.get("proposal", {})
            if not prop:
                self._say(["Tidak ada parameter yang menempel batas pada desain terbaik dan kandidat terakhir; tidak ada usulan."])
                return
            for p, (lo, hi) in prop.items():
                self.rows[p]["lo"].set(_fmt(lo))
                self.rows[p]["hi"].set(_fmt(hi))
            self._say(self._report_lines(res, "Usulan diisikan ke kolom (BELUM disimpan). Periksa lalu klik Simpan override.", prop))
        self._call(cmd.bounds(self.app.design(), propose=True, widen=w), done, "Menghitung usulan...")

    def _report_lines(self, res, head, prop):
        lines = [head]
        for p, (lo, hi) in prop.items():
            a = self.active.get(p)
            lines.append(f"  {p}: {a[0]:g}..{a[1]:g} -> {lo:g}..{hi:g}" if a else f"  {p}: {lo:g}..{hi:g}")
        v0, v1 = res.get("valid_before_pct"), res.get("valid_after_pct")
        if v0 is not None and v1 is not None:
            lines.append(f"Titik acak yang lolos aturan geometri: {v0:.1f}% -> {v1:.1f}%")
        lines += [f"[peringatan] {w}" for w in res.get("warnings", [])]
        return lines

    def check(self):
        s = self._diff_set()
        if s is None:
            return
        if not s:
            self._say(["Tidak ada perubahan dibanding rentang aktif."])
            return

        def done(res):
            if self._fail(res):
                return
            self._say(self._report_lines(res, "Simulasi (tidak menulis apa pun):", res.get("proposal", {})))
        self._call(cmd.bounds(self.app.design(), set_=s, dry_run=True), done, "Memeriksa geometri...")

    def save(self):
        s = self._diff_set()
        if s is None:
            return
        if not s:
            self._say(["Tidak ada perubahan untuk disimpan."])
            return
        if not messagebox.askyesno("Simpan override", "Perubahan rentang:\n  " + s.replace(",", "\n  ") +
                                   "\n\nHasil Usulkan kandidat setelah ini tidak identik dengan sebelumnya dan model perlu dilatih ulang. "
                                   "Lanjutkan?", parent=self.top):
            return

        def done(res):
            if self._fail(res):
                return
            if res.get("written"):
                self._say(["Override disimpan: " + res.get("override_path", ""),
                           "Jalankan Latih model ulang (tab 4). Kembalikan kapan saja dengan Kembalikan ke bawaan."], "ok")
                self.reload_quiet()
                self.app.refresh_status()
            else:
                self._say(["Tidak ada yang ditulis."])
        self._call(cmd.bounds(self.app.design(), set_=s), done, "Menyimpan...")

    def reload_quiet(self):
        def done(res):
            if "table" in res:
                self._fill(res["table"], res.get("changed", []))
        self._call(cmd.bounds(self.app.design()), done, "Memuat ulang...")

    def reset(self):
        if not self.changed and not messagebox.askyesno("Kembalikan", "Tidak ada override yang aktif. Tetap jalankan reset?", parent=self.top):
            return
        if self.changed and not messagebox.askyesno("Kembalikan ke bawaan", "Hapus override dan kembali ke BOUNDS file desain?\n"
                                                    "Model yang dilatih dengan rentang override perlu dilatih ulang.", parent=self.top):
            return

        def done(res):
            if self._fail(res):
                return
            self._say(["Override dihapus; rentang kembali ke BOUNDS file desain." if res.get("written")
                       else "Tidak ada override; tidak ada yang diubah."], "ok")
            self.reload_quiet()
            self.app.refresh_status()
        self._call(cmd.bounds(self.app.design(), reset=True), done, "Mengembalikan...")
