"""Uji GUI G4a (tata letak): status ringkas, log terlipat, baris tombol membungkus, widget tidak terpotong.

  py tools\\test_gui_g4.py [--shot FOLDER] [--sizes 1366x728@2.0,1920x1080@1.333,1280x720@2.5]
Di Linux tanpa layar:  xvfb-run -a python3 tools/test_gui_g4.py

Bagian A tidak butuh layar (logika pembungkus baris). Bagian B membuka jendela GUI pada tiap ukuran layar tiruan
(ukuran layar dan skala Tk disimulasikan; jendela ditata seolah layarnya seukuran itu) dan memeriksa:
jendela muat di layar, bilah log tidak terpotong, tidak ada widget yang melewati batas induknya (terpotong) atau
terhimpit sampai hampir nol, tiap tab, dialog Rentang parameter, dan perilaku status serta log.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cstopt.gui import layout as L  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  [OK]   " if cond else "  [GAGAL] ") + name + (f"  {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)


# ---------------------------------------------------------------- bagian A: tanpa layar
class FakeW:
    def __init__(self, w, h=20):
        self.w, self.h, self.pos = w, h, None

    def winfo_reqwidth(self):
        return self.w

    def winfo_reqheight(self):
        return self.h

    def place(self, **kw):
        self.pos = kw


class FakeFrame:
    def __init__(self):
        self.height = None

    def configure(self, **kw):
        self.height = kw.get("height", self.height)


def flow(widths, width, heights=None, pads=None):
    fr = FakeFrame()
    heights = heights or [20] * len(widths)
    ws = [FakeW(x, h) for x, h in zip(widths, heights)]
    pads = pads or [(0, 8)] * len(ws)
    fr._flow_items = [(w, p[0], p[1]) for w, p in zip(ws, pads)]
    fr._flow_sig, fr._flow_gap = None, 4
    L._relayout(fr, width)
    return ws, fr


def rows_of(ws):
    ys = sorted({w.pos["y"] for w in ws})
    return [sum(1 for w in ws if w.pos["y"] == y) for y in ys]


def part_a():
    print("A: logika pembungkus baris (tanpa layar)")
    check("_pad int", L._pad(8) == (8, 8))
    check("_pad tuple", L._pad((4, 12)) == (4, 12))
    check("_pad teks", L._pad("4 12") == (4, 12) and L._pad("6") == (6, 6))
    check("_pad rusak", L._pad("abc") == (0, 0))
    ws, fr = flow([100, 100, 100], 10 ** 6)
    check("lebar cukup: satu baris", rows_of(ws) == [3], rows_of(ws))
    check("tinggi frame = tinggi satu baris", fr.height == 20, fr.height)
    ws, fr = flow([100, 100, 100], 250)                      # tiap item 108 -> 2 per baris
    check("lebar sempit: membungkus 2 + 1", rows_of(ws) == [2, 1], rows_of(ws))
    check("tinggi frame = dua baris + jarak", fr.height == 44, fr.height)
    # tiap widget harus berada di dalam lebar yang tersedia (bug versi grid: kolom dipakai bersama antar baris)
    for width in (180, 250, 330, 500):
        ws, fr = flow([203, 246, 51, 120, 90, 266, 130], width)
        worst = max(w.pos["x"] + w.w for w in ws)
        single = max(w.w for w in ws)
        check(f"semua widget di dalam lebar {width}", worst <= max(width, single), f"terjauh {worst}")
    ws, fr = flow([500], 100)
    check("item lebih lebar dari baris tetap di baris sendiri", rows_of(ws) == [1], rows_of(ws))
    ws, fr = flow([100, 100], 10 ** 6, heights=[20, 40])
    check("widget lebih pendek diratakan vertikal ke tengah baris", ws[0].pos["y"] == 10 and ws[1].pos["y"] == 0,
          (ws[0].pos, ws[1].pos))
    ws, fr = flow([100, 100, 100], 250)
    for w in ws:
        w.pos = None
    L._relayout(fr, 250)                                     # keadaan sama: tidak diatur ulang (hindari lingkaran Configure)
    check("tanpa perubahan tidak dipasang ulang", all(w.pos is None for w in ws))
    L._relayout(fr, 10 ** 6)
    check("melebar lagi: kembali satu baris", rows_of(ws) == [3], rows_of(ws))


# ---------------------------------------------------------------- bagian B: dengan layar
def parse_sizes(txt):
    out = []
    for part in txt.split(","):
        wh, sc = part.strip().split("@")
        w, h = wh.lower().split("x")
        out.append((int(w), int(h), float(sc)))
    return out


def problems_in(widget, tk, label=""):
    """Widget tampak yang melewati batas induknya (terpotong) atau terhimpit; keluaran daftar teks."""
    probs = []
    squeezed = ("TButton", "TEntry", "TCombobox", "TSpinbox", "TCheckbutton", "TRadiobutton")

    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Toplevel):
                continue
            try:
                if not c.winfo_viewable():
                    continue
            except tk.TclError:
                continue
            x, y, cw, ch = c.winfo_x(), c.winfo_y(), c.winfo_width(), c.winfo_height()
            pw, ph = w.winfo_width(), w.winfo_height()
            name = f"{c.winfo_class()}:{str(c).split('.')[-1]}"
            if not isinstance(w, tk.Canvas):
                if x < -1 or y < -1 or x + cw > pw + 1 or y + ch > ph + 1:
                    probs.append(f"{label}{name} keluar dari induk ({x},{y},{cw}x{ch} di {pw}x{ph})")
                if c.winfo_class() in squeezed and (cw < 12 or ch < 12):
                    probs.append(f"{label}{name} terhimpit ({cw}x{ch})")
            walk(c)                                          # juga masuk ke isi Canvas (tab yang bisa digulir)
    walk(widget)
    return probs


def pump(root, secs=0.2):
    end = time.time() + secs
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def wait_for(root, cond, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.02)
    return False


def shot(root, folder, name):
    if not folder:
        return
    try:
        from PIL import ImageGrab
        os.makedirs(folder, exist_ok=True)
        root.update()
        x, y, w, h = root.winfo_rootx(), root.winfo_rooty(), root.winfo_width(), root.winfo_height()
        bbox = (x, y, x + w, y + h)
        img = ImageGrab.grab(bbox=bbox) if os.name == "nt" else ImageGrab.grab(bbox=bbox, xdisplay=os.environ.get("DISPLAY"))
        img.save(os.path.join(folder, name + ".png"))
    except Exception as e:                                   # tangkap layar hanya tambahan
        print(f"  (tangkap layar dilewati: {e})")


def run_size(SW, SH, scaling, shots, behaviour):
    import tkinter as tk
    from tkinter import messagebox
    from cstopt.gui import app as gapp
    from cstopt.gui import commands as cmd

    tag = f"{SW}x{SH}@{scaling}"
    print(f"B: layar tiruan {tag}")
    tk.Misc.winfo_screenwidth = lambda self, _w=SW: _w       # fit_window membaca ukuran layar dari sini
    tk.Misc.winfo_screenheight = lambda self, _h=SH: _h
    root = tk.Tk()
    root.report_callback_exception = lambda *e: (print("  [GAGAL] galat callback Tk:", e[1]), FAILS.append("callback Tk " + tag))
    root.tk.call("tk", "scaling", scaling)
    messagebox.showwarning = lambda *a, **k: None
    messagebox.showinfo = lambda *a, **k: None
    a = gapp.App(root)
    wait_for(root, lambda: a.status.get("run") and not a._status_busy)
    pump(root, 0.4)

    check(f"{tag}: jendela muat di layar", root.winfo_width() <= SW and root.winfo_height() <= SH,
          f"{root.winfo_width()}x{root.winfo_height()}")
    check(f"{tag}: bilah log tidak terpotong",
          a.log_frame.winfo_y() + a.log_frame.winfo_height() <= root.winfo_height() + 1,
          f"{a.log_frame.winfo_y()}+{a.log_frame.winfo_height()} dari {root.winfo_height()}")
    check(f"{tag}: area tab cukup tinggi (>= 230 px)", a.nb.winfo_height() >= 230, str(a.nb.winfo_height()))
    check(f"{tag}: status awal ringkas (<= 3 baris)", int(a.status_text.cget("height")) <= 3, a.status_text.cget("height"))
    check(f"{tag}: log awal terlipat", (not a._log_open) and not a.box.winfo_ismapped())

    for i in range(a.nb.index("end")):
        a.nb.select(i)
        pump(root, 0.3)
        title = a.nb.tab(i, "text")
        if title.startswith("5"):                            # tab 5 bisa digulir: bagian bawah harus terjangkau
            cv = a.tab_bo.master
            check(f"{tag}: tab 5 punya kanvas gulir", cv.winfo_class() == "Canvas")
            if a.tab_bo.winfo_reqheight() > cv.winfo_height():
                cv.yview_moveto(1.0)
                pump(root, 0.2)
                bot = a.tab_bo.winfo_rooty() + a.tab_bo.winfo_height()
                check(f"{tag}: tab 5 tergulir sampai dasar", cv.yview()[1] >= 0.999, str(cv.yview()))
                cv.yview_moveto(0.0)
                pump(root, 0.2)
        probs = problems_in(root, tk, f"tab {title}: ")
        check(f"{tag}: tab '{title}' tanpa widget terpotong", not probs, "; ".join(probs[:4]))
        shot(root, shots, f"{tag}_tab{i + 1}")

    if behaviour:
        # status: ringkas <-> detail
        n0 = int(a.status_text.cget("height"))
        a.toggle_status_detail()
        pump(root, 0.2)
        check("status detail memuat nama run", a.status.get("run", "?") in a.status_text.get("1.0", "end"))
        check("status detail: lebih banyak baris", int(a.status_text.cget("height")) > n0, a.status_text.cget("height"))
        txt = a.status_text.get("1.0", "end")
        check("status detail memuat 'Feasible'", "Feasible" in txt or "Sampel" in txt, txt[:60])
        a.toggle_status_detail()
        pump(root, 0.2)
        check("kembali ringkas", int(a.status_text.cget("height")) == n0)
        check("status ringkas memuat nama desain", a.status.get("design", "?") in a.status_text.get("1.0", "end"))

        # log: buka manual dan geser
        a.toggle_log()
        pump(root, 0.2)
        check("log terbuka manual", a._log_open and a.box.winfo_ismapped() and a.log_btn.cget("text") == "Tutup log")
        check("log terbuka: bilah tetap di dalam jendela",
              a.log_frame.winfo_y() + a.log_frame.winfo_height() <= root.winfo_height() + 1)
        h0 = a._log_lines
        a._grip_start(type("E", (), {"y_root": 500})())
        a._grip_drag(type("E", (), {"y_root": 500 - 100})())
        check("seret pegangan ke atas menambah tinggi log", a._log_lines > h0, f"{h0} -> {a._log_lines}")
        a._grip_drag(type("E", (), {"y_root": 500 + 5000})())
        check("tinggi log dibatasi minimum 3", a._log_lines == 3, a._log_lines)
        a.toggle_log()
        pump(root, 0.2)
        a._log("[selesai: uji]\n", "ok")
        check("baris terakhir tampil saat terlipat", a.last_var.get() == "[selesai: uji]", a.last_var.get())
        a._set_log_open(True, auto=False)
        a._auto_collapse()
        check("log buka manual tidak dilipat otomatis", a._log_open)
        a._set_log_open(False)

        # perintah nyata: log terbuka otomatis, lalu terlipat lagi (hanya bila berhasil dan tidak sedang dibaca)
        seen_open = []
        orig = a._on_line
        a._on_line = lambda line: (seen_open.append(a._log_open), orig(line))
        a.run_cmd(cmd.status(a.design()))
        pump(root, 0.1)
        check("perintah berjalan: log terbuka otomatis", a._log_open and a._log_auto)
        wait_for(root, lambda: not a.runner.busy, 90)
        a._on_line = orig
        wait_for(root, lambda: not a._log_open, 6)
        check("selesai berhasil: log dilipat otomatis", not a._log_open)
        check("baris terakhir memuat '[selesai'", "[selesai" in a.last_var.get(), a.last_var.get())

        # dialog Rentang parameter muat di layar
        a.open_bounds()
        dlg = a._bounds_dlg
        wait_for(root, lambda: not dlg.busy, 60)
        pump(root, 0.4)
        top = dlg.top
        check(f"{tag}: dialog rentang muat di layar", top.winfo_width() <= SW and top.winfo_height() <= SH,
              f"{top.winfo_width()}x{top.winfo_height()}")
        probs = problems_in(top, tk, "dialog: ")
        check(f"{tag}: dialog rentang tanpa widget terpotong", not probs, "; ".join(probs[:4]))
        shot(top, shots, f"{tag}_dialog_rentang")
        top.destroy()

    root.destroy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default=None, help="folder tangkap layar (butuh Pillow)")
    ap.add_argument("--sizes", default="1366x728@1.333,1366x728@2.0,1920x1080@1.333,1280x720@2.5")
    ap.add_argument("--only-a", action="store_true", help="hanya bagian A (tanpa layar)")
    args = ap.parse_args()
    part_a()
    if not args.only_a:
        for i, (w, h, sc) in enumerate(parse_sizes(args.sizes)):
            run_size(w, h, sc, args.shot, behaviour=(i == 0))
    print()
    if FAILS:
        print(f"GAGAL: {len(FAILS)} pemeriksaan")
        for f in FAILS:
            print("  -", f)
        sys.exit(1)
    print("SEMUA LULUS")


if __name__ == "__main__":
    main()
