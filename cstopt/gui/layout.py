"""
Bantuan tata letak GUI (G4a): murni tampilan, tidak menyentuh logika.

- make_flow(frame): ubah baris widget yang di-pack side="left" menjadi baris yang membungkus ke baris berikut
  saat lebarnya tidak cukup (tombol tidak lagi terpotong di kanan). Frame harus dipasang dengan lebar penuh
  (grid sticky "ew" atau pack fill "x").
- fit_window(win, w, h, minw, minh): ukuran jendela awal dibatasi layar (layar laptop 1366x728 sudah tidak muat 1120x820).
- autowrap(label): wraplength mengikuti lebar induknya.
"""

SCREEN_MARGIN_W = 30          # sisa lebar layar (piksel)
SCREEN_MARGIN_H = 110         # sisa tinggi layar: bilah judul + bilah tugas Windows


def _pad(v):
    """Nilai padx hasil pack_info -> (kiri, kanan) dalam piksel."""
    if isinstance(v, (int, float)):
        return int(v), int(v)
    if isinstance(v, str):
        v = v.split()
    try:
        vals = [int(float(x)) for x in v]
    except (TypeError, ValueError):
        return 0, 0
    if not vals:
        return 0, 0
    return (vals[0], vals[0]) if len(vals) == 1 else (vals[0], vals[1])


def make_flow(frame, gap_y=4):
    """Ubah semua anak frame yang di-pack menjadi tata letak membungkus (urutan pack dipertahankan)."""
    items = []
    for w in frame.pack_slaves():
        padl, padr = _pad(w.pack_info().get("padx", 0))
        w.pack_forget()
        items.append((w, padl, padr))
    frame._flow_items = items
    frame._flow_sig = None
    frame._flow_gap = gap_y
    frame.pack_propagate(False)
    frame.grid_propagate(False)
    frame.bind("<Configure>", lambda e: _relayout(frame, e.width), add="+")
    _relayout(frame, 10 ** 6)


def _relayout(frame, width):
    """Susun dengan place (bukan grid): kolom grid dipakai bersama antar baris sehingga lebar baris bisa melebihi batas."""
    rows, row, x = [], [], 0
    for it in frame._flow_items:
        w, padl, padr = it
        need = w.winfo_reqwidth() + padl + padr
        if row and x + need > width:
            rows.append(row)
            row, x = [], 0
        row.append(it)
        x += need
    if row:
        rows.append(row)
    sig = (width if not rows else None, tuple(tuple(id(it[0]) for it in r) for r in rows),
           tuple(it[0].winfo_reqwidth() for it in frame._flow_items), tuple(it[0].winfo_reqheight() for it in frame._flow_items))
    if sig == frame._flow_sig:                       # tidak berubah: jangan atur ulang (hindari lingkaran Configure)
        return
    frame._flow_sig = sig
    y = 0
    for r, line in enumerate(rows):
        rowh = max(it[0].winfo_reqheight() for it in line)
        x = 0
        for w, padl, padr in line:
            x += padl
            w.place(x=x, y=y + (rowh - w.winfo_reqheight()) // 2)
            x += w.winfo_reqwidth() + padr
        y += rowh + frame._flow_gap
    frame.configure(height=max(1, y - frame._flow_gap))


def fit_window(win, w, h, minw=700, minh=420, center=True):
    """Atur geometry awal agar muat di layar; minsize tidak melebihi ukuran awal."""
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    W = max(400, min(w, sw - SCREEN_MARGIN_W))
    H = max(300, min(h, sh - SCREEN_MARGIN_H))
    win.minsize(min(minw, W), min(minh, H))
    if center:
        x = max(0, (sw - W) // 2)
        y = max(0, (sh - H) // 4)
        win.geometry(f"{W}x{H}+{x}+{y}")
    else:
        win.geometry(f"{W}x{H}")
    return W, H


def autowrap(label, pad=24):
    """wraplength label mengikuti lebar induknya (minimum 200 piksel)."""
    def _on(e):
        try:
            label.configure(wraplength=max(200, e.width - pad))
        except Exception:                            # widget sudah dihancurkan
            pass
    label.master.bind("<Configure>", _on, add="+")
    return label


def make_scrollable(parent, padding=12):
    """Bingkai tab yang bisa digulir vertikal bila isinya lebih tinggi dari area tab. Mengembalikan (luar, dalam):
    tambahkan `luar` ke Notebook dan isi `dalam`. Bila ada ruang lebih, `dalam` memenuhi area (baris berbobot tetap meregang)."""
    import tkinter as tk
    from tkinter import ttk
    outer = ttk.Frame(parent)
    canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0)       # tanpa yscrollincrement: gulir per piksel, dasar tercapai persis
    vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner = ttk.Frame(canvas, padding=padding)
    win = canvas.create_window(0, 0, window=inner, anchor="nw")

    def fit(_e=None):
        cw, ch = canvas.winfo_width(), canvas.winfo_height()
        h = max(ch, inner.winfo_reqheight())
        canvas.itemconfigure(win, width=cw, height=h)
        canvas.configure(scrollregion=(0, 0, cw, h))
    canvas.bind("<Configure>", fit)
    inner.bind("<Configure>", fit)

    def on_wheel(e):
        w = canvas.winfo_containing(e.x_root, e.y_root)
        if w is None or not str(w).startswith(str(outer)):
            return
        if w.winfo_class() in ("Treeview", "Text", "TCombobox", "Listbox"):    # widget ini menggulir sendiri
            return
        if canvas.yview() == (0.0, 1.0):
            return
        d = getattr(e, "delta", 0)
        step = (-1 if d > 0 else 1) if d else (-1 if getattr(e, "num", 0) == 4 else 1)
        lo, hi = canvas.yview()
        canvas.yview_moveto(lo + step * 0.12 * (hi - lo))                 # 12% dari tinggi yang terlihat per klik roda

    def on_map(_e=None):
        canvas.bind_all("<MouseWheel>", on_wheel)
        canvas.bind_all("<Button-4>", on_wheel)
        canvas.bind_all("<Button-5>", on_wheel)

    def on_unmap(_e=None):
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canvas.unbind_all(seq)
    outer.bind("<Map>", on_map)
    outer.bind("<Unmap>", on_unmap)
    outer.canvas = canvas
    return outer, inner
