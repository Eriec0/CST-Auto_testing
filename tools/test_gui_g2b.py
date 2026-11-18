"""Uji dialog "Rentang parameter" (G2b), memakai runner dan perintah `bounds` SUNGGUHAN (tanpa CST).

  py tools\\test_gui_g2b.py [--shot FOLDER]     (butuh layar; sekitar 1 menit)
Di Linux tanpa layar:  xvfb-run -a python3 tools/test_gui_g2b.py
Berkas data\\<RUN>\\bounds_override.json milik Anda dicadangkan lebih dulu dan dipulihkan di akhir.
"""
import argparse
import os
import shutil
import sys
import tempfile
import time
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cstopt import boundsio  # noqa: E402
from cstopt.gui import app as gapp  # noqa: E402
from cstopt.ml import core as mc  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  [OK]   " if cond else "  [GAGAL] ") + name + (f"  {extra}" if (extra and not cond) else ""), flush=True)
    if not cond:
        FAILS.append(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default=None, help="folder untuk tangkap layar dialog (butuh Pillow)")
    args = ap.parse_args()
    mod = mc.load_design(None).mod
    path = boundsio.override_path(mod)
    saved = None
    if os.path.exists(path):
        saved = tempfile.mktemp()
        shutil.copy(path, saved)
        os.remove(path)
    bak = path + ".bak"
    had_bak = os.path.exists(bak)
    root = tk.Tk()
    root.geometry("1100x760")
    try:
        a = gapp.App(root)

        def pump(sec):
            t = time.time()
            while time.time() - t < sec:
                root.update()
                time.sleep(0.03)

        def wait(dlg, limit=120):
            t = time.time()
            pump(0.3)
            while dlg.busy and time.time() - t < limit:
                pump(0.2)
            pump(0.3)
            return not dlg.busy

        def text(dlg):
            return dlg.msg.get("1.0", "end")

        warns = []
        messagebox.askyesno = lambda *x, **k: True
        messagebox.showwarning = lambda title, msg, **k: warns.append(msg)
        pump(3)
        a.open_bounds()
        dlg = a._bounds_dlg
        check("dialog selesai memuat", wait(dlg) and len(dlg.rows) > 0)
        params = list(mod.PARAM_NAMES)
        check("tabel memuat semua parameter", list(dlg.rows) == params, str(list(dlg.rows)))
        check("kolom = rentang aktif", all(abs(float(dlg.rows[p]["lo"].get()) - dlg.active[p][0]) < 1e-6 for p in params))
        check("status awal: tidak ada override", not dlg.changed)

        # usulan mengisi kolom tanpa menyimpan
        dlg.widen.set("0.2")
        dlg.propose()
        wait(dlg)
        diff = [p for p in params if abs(float(dlg.rows[p]["lo"].get()) - dlg.active[p][0]) > 1e-9
                or abs(float(dlg.rows[p]["hi"].get()) - dlg.active[p][1]) > 1e-9]
        if diff:
            check("usulan mengisi kolom dan berkas BELUM ditulis", not os.path.exists(path) and "BELUM disimpan" in text(dlg), text(dlg)[:200])
            check("baris yang diubah ditandai", all("diubah" in str(dlg.rows[p]["mark"].cget("text")) for p in diff))
        else:
            print("  [info] tidak ada parameter menempel batas pada data ini; usulan kosong; kolom diubah manual untuk uji berikutnya")
            check("usulan kosong dilaporkan", "Tidak ada parameter" in text(dlg))
            dlg.rows["WU"]["lo"].set(f"{dlg.active['WU'][0] - 0.5:g}")
            diff = ["WU"]

        # periksa (dry-run) tidak menulis
        dlg.check()
        wait(dlg)
        check("periksa geometri tidak menulis berkas", not os.path.exists(path) and "Simulasi" in text(dlg), text(dlg)[:200])

        # entri tidak valid ditolak tanpa memanggil CLI
        keep = dlg.rows[params[0]]["lo"].get()
        dlg.rows[params[0]]["lo"].set("abc")
        dlg.check()
        check("entri bukan angka ditolak tanpa memanggil CLI", not dlg.busy and "angka" in text(dlg))
        dlg.rows[params[0]]["lo"].set(keep)
        hi = dlg.rows[params[0]]["hi"].get()
        dlg.rows[params[0]]["lo"].set(str(float(hi) + 1))
        dlg.save()
        check("min >= max ditolak", not dlg.busy and "lebih kecil" in text(dlg) and not os.path.exists(path))
        dlg.rows[params[0]]["lo"].set(keep)

        # simpan
        dlg.save()
        wait(dlg)
        pump(1)
        wait(dlg)
        check("simpan membuat berkas override", os.path.exists(path), text(dlg)[:200])
        check("tabel menandai parameter override", dlg.changed != [] and
              any("override" in str(dlg.rows[p]["mark"].cget("text")) for p in dlg.changed))
        check("override terbaca oleh Design", mc.load_design(None).bounds_changed != [])
        pump(8)
        check("status utama menampilkan override aktif", bool(a.status.get("bounds_changed")), str(a.status.get("bounds_changed")))
        if args.shot:
            try:
                from PIL import ImageGrab
                os.makedirs(args.shot, exist_ok=True)
                dlg.top.lift()
                pump(1)
                img = ImageGrab.grab() if os.name == "nt" else ImageGrab.grab(xdisplay=os.environ.get("DISPLAY"))
                img.save(os.path.join(args.shot, "dialog_rentang.png"))
                print("  [info] tangkap layar:", os.path.join(args.shot, "dialog_rentang.png"))
            except Exception as e:  # noqa: BLE001
                print("  [info] tangkap layar dilewati:", e)

        # reset
        dlg.reset()
        wait(dlg)
        pump(1)
        wait(dlg)
        check("reset menghapus berkas", not os.path.exists(path))
        check("setelah reset: tidak ada override di tabel", dlg.changed == [])
        dlg.top.destroy()
        a.runner.stop()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
        if os.path.exists(path):
            os.remove(path)
        if os.path.exists(bak) and not had_bak:
            os.remove(bak)
        if saved:
            shutil.copy(saved, path)
            os.remove(saved)
    print("\nSEMUA LULUS" if not FAILS else f"\n{len(FAILS)} GAGAL: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
