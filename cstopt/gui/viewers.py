"""Penampil gambar dengan zoom untuk tab 6 (butuh Pillow).

Roda mouse: zoom di posisi kursor. Seret dengan tombol kiri: geser. Klik ganda: muat jendela.
Tombol: perbesar, perkecil, muat jendela, 100% (piksel asli), simpan tampilan sebagai PNG.
Hanya bagian yang terlihat yang digambar ulang, jadi zoom besar pada PNG besar tetap ringan.
Batas: PNG adalah raster, jadi pembesaran melewati 100% tidak menambah detail.
"""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

ZOOM_STEP = 1.25
MAX_SCALE = 16.0


class ZoomImage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.im = None
        self.name = ""
        self.scale = 1.0
        self.ox = 0.0                                   # posisi kiri-atas gambar di kanvas
        self.oy = 0.0
        self.fit_mode = True
        self._tk = None
        self._crop = None
        self._drag = None
        self.info_var = tk.StringVar(value="")
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Button(bar, text="Perbesar", width=9, command=lambda: self.zoom_by(ZOOM_STEP)).pack(side="left")
        ttk.Button(bar, text="Perkecil", width=9, command=lambda: self.zoom_by(1 / ZOOM_STEP)).pack(side="left", padx=4)
        ttk.Button(bar, text="Muat jendela", command=self.fit).pack(side="left")
        ttk.Button(bar, text="100%", width=6, command=self.actual).pack(side="left", padx=4)
        ttk.Button(bar, text="Simpan tampilan...", command=self.save_view).pack(side="left")
        ttk.Label(bar, textvariable=self.info_var, foreground="#555").pack(side="left", padx=10)
        self.canvas = tk.Canvas(self, background="#ffffff", highlightthickness=1, highlightbackground="#bbbbbb", cursor="fleur")
        self.canvas.pack(fill="both", expand=True, pady=(4, 0))
        c = self.canvas
        c.bind("<Configure>", lambda e: self._on_resize())
        c.bind("<Enter>", lambda e: c.focus_set())
        c.bind("<MouseWheel>", self._on_wheel)                          # Windows dan macOS
        c.bind("<Button-4>", lambda e: self.zoom_by(ZOOM_STEP, e.x, e.y))   # Linux
        c.bind("<Button-5>", lambda e: self.zoom_by(1 / ZOOM_STEP, e.x, e.y))
        c.bind("<ButtonPress-1>", self._press)
        c.bind("<B1-Motion>", self._motion)
        c.bind("<Double-Button-1>", lambda e: self.fit())

    # ------------------------------------------------------------------ isi
    def set_image(self, path):
        """Muat gambar dari berkas; tampil muat jendela. Mengembalikan True bila berhasil."""
        try:
            im = Image.open(path)
            im.load()
            im = im.convert("RGBA") if im.mode in ("P", "LA", "RGBA") else im.convert("RGB")
        except Exception as e:
            self.set_message(f"Gagal menampilkan {path}: {e}")
            return False
        self.im = im
        self.name = path
        self.fit()
        return True

    def set_message(self, text):
        self.im = None
        self._crop = None
        self._tk = None
        self.canvas.delete("all")
        w = max(self.canvas.winfo_width(), 400)
        h = max(self.canvas.winfo_height(), 300)
        self.canvas.create_text(w / 2, h / 2, text=text, fill="#555555", width=max(w - 40, 200))
        self.info_var.set("")

    # ------------------------------------------------------------------ zoom dan geser
    def _size(self):
        return max(self.canvas.winfo_width(), 50), max(self.canvas.winfo_height(), 50)

    def fit_scale(self):
        cw, ch = self._size()
        return min(cw / self.im.width, ch / self.im.height, 1.0)

    def fit(self):
        if self.im is None:
            return
        self.fit_mode = True
        self.scale = self.fit_scale()
        self.render()

    def actual(self):
        if self.im is not None:
            self.zoom_to(1.0)

    def zoom_to(self, new_scale, cx=None, cy=None):
        if self.im is None:
            return
        cw, ch = self._size()
        cx = cw / 2 if cx is None else cx
        cy = ch / 2 if cy is None else cy
        new_scale = max(min(new_scale, MAX_SCALE), self.fit_scale())
        ix, iy = (cx - self.ox) / self.scale, (cy - self.oy) / self.scale     # titik gambar di bawah kursor
        self.scale = new_scale
        self.ox, self.oy = cx - ix * new_scale, cy - iy * new_scale
        self.fit_mode = False
        self.render()

    def zoom_by(self, factor, cx=None, cy=None):
        self.zoom_to(self.scale * factor, cx, cy)

    def _on_wheel(self, e):
        self.zoom_by(ZOOM_STEP ** (1 if e.delta > 0 else -1), e.x, e.y)

    def _press(self, e):
        self._drag = (e.x, e.y)

    def _motion(self, e):
        if self._drag is None or self.im is None:
            return
        self.pan(e.x - self._drag[0], e.y - self._drag[1])
        self._drag = (e.x, e.y)

    def pan(self, dx, dy):
        self.ox += dx
        self.oy += dy
        self.fit_mode = False
        self.render()

    def _on_resize(self):
        if self.im is not None:
            if self.fit_mode:
                self.scale = self.fit_scale()
            self.render()

    # ------------------------------------------------------------------ gambar ulang
    def _clamp(self):
        cw, ch = self._size()
        dw, dh = self.im.width * self.scale, self.im.height * self.scale
        self.ox = (cw - dw) / 2 if dw <= cw else min(0.0, max(cw - dw, self.ox))
        self.oy = (ch - dh) / 2 if dh <= ch else min(0.0, max(ch - dh, self.oy))

    def render(self):
        if self.im is None:
            return
        self._clamp()
        cw, ch = self._size()
        s = self.scale
        left, top = max(0.0, -self.ox / s), max(0.0, -self.oy / s)
        right, bottom = min(float(self.im.width), (cw - self.ox) / s), min(float(self.im.height), (ch - self.oy) / s)
        box = (int(left), int(top), min(self.im.width, int(right) + 1), min(self.im.height, int(bottom) + 1))
        crop = self.im.crop(box)
        size = (max(1, round(crop.width * s)), max(1, round(crop.height * s)))
        method = Image.NEAREST if s >= 4 else (Image.BILINEAR if s >= 1 else Image.LANCZOS)
        self._crop = crop.resize(size, method)
        self._tk = ImageTk.PhotoImage(self._crop)
        self.canvas.delete("all")
        self.canvas.create_image(self.ox + box[0] * s, self.oy + box[1] * s, image=self._tk, anchor="nw")
        base = self.name.replace("\\", "/").split("/")[-1]
        self.info_var.set(f"{base}   {self.im.width}x{self.im.height} px   zoom {s * 100:.0f}%")

    def save_view(self):
        if self._crop is None:
            messagebox.showinfo("Simpan", "Belum ada gambar.")
            return
        path = filedialog.asksaveasfilename(title="Simpan tampilan sebagai PNG", defaultextension=".png",
                                            filetypes=[("PNG", "*.png")])
        if not path:
            return
        try:
            self._crop.save(path)
        except Exception as e:
            messagebox.showerror("Simpan gagal", str(e))
