"""Uji T1 (tema gelap/terang).

  py tools\\test_gui_t1.py [--shot FOLDER] [--size 1366x728@1.333]
Linux tanpa layar:  xvfb-run -a python3 tools/test_gui_t1.py

Bagian A tidak butuh tkinter: palet, kontras, peran warna, literal warna di kode GUI, pilihan tersimpan, rcParams
matplotlib, dan logika `retheme` pada widget tiruan. Bagian B butuh tkinter: membuat aplikasi, bolak balik gelap <-> terang,
memeriksa sisa warna terang di mode gelap, dialog rentang dan jendela grafik saat tema berganti, tangkapan layar tiap tab.
"""
import argparse
import glob
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

FAILS = []


def check(name, cond, extra=""):
    print(("  [OK]   " if cond else "  [GAGAL] ") + name + (f"  {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)


# warna yang memang bukan peran tema: warna data grafik dan warna tag log (log selalu gelap di kedua mode)
ALLOWED_PLAIN = {"#d7dde3", "#7fd1ff", "#ffc66d", "#8fdc8f", "#ff8f8f",
                 "#9aa5b1", "#2e9e4f", "#d9480f", "#f59f00", "#e8a87c", "#888888"}


class FakeWidget:
    """Widget tiruan untuk menguji `theme.retheme` tanpa tkinter."""

    def __init__(self, cls, opts=None, tags=None, kids=(), tree_tags=None):
        self.cls, self.opts, self.tags, self.kids, self.tree_tags = cls, dict(opts or {}), dict(tags or {}), list(kids), dict(tree_tags or {})

    def winfo_class(self):
        return self.cls

    def winfo_children(self):
        return self.kids

    def cget(self, opt):
        if opt not in self.opts:
            raise RuntimeError("opsi tidak ada")
        return self.opts[opt]

    def configure(self, **kw):
        for k, v in kw.items():
            if k not in self.opts:
                raise RuntimeError("opsi tidak ada: " + k)
            self.opts[k] = v

    def tag_names(self):
        return list(self.tags) + ["sel"]

    def tag_cget(self, tag, opt):
        return self.tags[tag].get(opt, "")

    def tag_configure(self, tag, **kw):
        if self.cls == "Treeview":
            if kw:
                self.tree_tags[tag].update(kw)
                return None
            return dict(self.tree_tags.get(tag, {}))
        self.tags[tag].update(kw)


def part_a():
    print("A: palet, peran, kode GUI, pilihan, matplotlib, retheme tiruan (tanpa tkinter)")
    from cstopt.gui import theme as T

    hexre = re.compile(r"^#[0-9a-f]{6}$")
    check("semua peran punya warna terang dan gelap heksadesimal", all(hexre.match(a) and hexre.match(b) for a, b, _ in T.ROLES.values()))
    for m in T.MODES:
        bg, fi, su = (T.color(r, m) for r in ("bg", "field", "surface"))
        check(f"{m}: teks utama kontras >= 7 di latar", T.contrast(T.color("fg", m), bg) >= 7, f"{T.contrast(T.color('fg', m), bg):.1f}")
        for r in ("muted", "warn", "bad", "ok", "info"):
            lim = 4.5 if m == "dark" else {"warn": 3.9, "ok": 4.4}.get(r, 4.5)      # warn/ok terang adalah warna lama dari sebelum T1
            c = min(T.contrast(T.color(r, m), x) for x in (bg, fi, su))
            check(f"{m}: peran {r} terbaca di latar/kolom/permukaan (>= {lim})", c >= lim, f"{c:.1f}")
        check(f"{m}: teks seleksi terbaca di warna seleksi (>= 4,5)", T.contrast(T.color("selfg", m), T.color("accent", m)) >= 4.5,
              f"{T.contrast(T.color('selfg', m), T.color('accent', m)):.1f}")
    # gelap bukan hitam pekat dan bukan terlalu terang
    check("latar gelap berupa abu gelap (kecerahan 0,01 sampai 0,05)", 0.01 <= T._lum(T.color("bg", "dark")) <= 0.05, f"{T._lum(T.color('bg', 'dark')):.3f}")

    check("peran dikenali dari huruf besar/kecil dan nama sistem", T.role_of("#B45F06") == "warn" and T.role_of("SystemWindowText") == "fg"
          and T.role_of("systembuttonface") == "bg")
    check("warna tak dikenal tidak diubah", T.convert("#123456", "dark") == "#123456" and T.convert("", "dark") == "")
    ok = True
    for r, (l, d, _) in T.ROLES.items():
        ok &= T.role_of(l) is not None and T.role_of(d) is not None
    check("literal terang dan gelap tiap peran dikenali", ok)
    check("bolak balik: terang -> gelap -> terang kembali ke peran yang sama",
          all(T.role_of(T.convert(T.convert(T.ROLES[r][0], "dark"), "light")) == T.role_of(T.ROLES[r][0]) for r in T.ROLES))

    # literal warna di kode GUI: harus peran tema atau warna data yang sah
    unknown = {}
    for f in glob.glob(os.path.join(HERE, "..", "cstopt", "gui", "*.py")):
        if f.endswith("theme.py"):
            continue
        for lit in set(re.findall(r"[\"'](#[0-9a-fA-F]{3,6})[\"']", open(f, encoding="utf-8").read())):
            if T.role_of(lit) is None and lit.lower() not in ALLOWED_PLAIN:
                unknown.setdefault(os.path.basename(f), []).append(lit)
    check("tidak ada literal warna di kode GUI di luar peran dan daftar sah", not unknown, str(unknown))

    # pilihan tersimpan
    d = tempfile.mkdtemp()
    p = os.path.join(d, "pref.json")
    check("pilihan awal (tanpa berkas) = gelap", T.load_pref(p) == "dark")
    T.save_pref("light", p)
    check("pilihan terang tersimpan dan terbaca", T.load_pref(p) == "light")
    open(p, "w").write("{rusak")
    check("berkas rusak -> bawaan, tanpa galat", T.load_pref(p) == "dark")
    open(p, "w").write('{"theme": "ungu"}')
    check("nilai asing -> bawaan", T.load_pref(p) == "dark")

    # matplotlib
    try:
        import matplotlib
        matplotlib.use("Agg")
        T._apply_mpl("dark")
        c1 = (matplotlib.rcParams["axes.facecolor"], matplotlib.rcParams["figure.facecolor"], matplotlib.rcParams["text.color"])
        T._apply_mpl("light")
        c2 = (matplotlib.rcParams["axes.facecolor"], matplotlib.rcParams["figure.facecolor"], matplotlib.rcParams["text.color"])
        check("matplotlib gelap memakai warna palet", c1 == (T.color("field", "dark"), T.color("bg", "dark"), T.color("fg", "dark")), str(c1))
        check("matplotlib terang kembali ke bawaan", c2 == tuple(matplotlib.rcParamsDefault[k] for k in ("axes.facecolor", "figure.facecolor", "text.color")), str(c2))
        from matplotlib.figure import Figure
        T._apply_mpl("dark")
        fig = Figure()
        ax = fig.add_subplot(111)
        ax.plot([0, 1], [0, 1], label="x")
        ax.legend()
        fig.canvas.draw() if hasattr(fig.canvas, "draw") else None
        check("Figure baru di mode gelap berlatar palet", fig.get_facecolor()[:3] == matplotlib.colors.to_rgb(T.color("bg", "dark")))
        T._apply_mpl("light")
    except ImportError:
        print("  (matplotlib tidak terpasang: bagian matplotlib dilewati)")

    # retheme pada widget tiruan
    T.MODE = "dark"
    lbl = FakeWidget("TLabel", {"foreground": "#b45f06", "background": ""})
    muted = FakeWidget("TLabel", {"foreground": "#555", "background": ""})
    plain = FakeWidget("TLabel", {"foreground": "", "background": ""})
    status = FakeWidget("Text", {"background": "#f6f6f6", "foreground": "SystemWindowText", "insertbackground": "SystemWindowText",
                                 "selectbackground": "SystemHighlight", "selectforeground": "SystemHighlightText"},
                        tags={"warn": {"foreground": "#b45f06"}, "err": {"foreground": "#b00020"}})
    log = FakeWidget("Text", {"background": "#101418", "foreground": "#d7dde3", "insertbackground": "#d7dde3",
                              "selectbackground": "SystemHighlight", "selectforeground": "SystemHighlightText"},
                     tags={"cmd": {"foreground": "#7fd1ff"}, "ok": {"foreground": "#8fdc8f"}})
    grip = FakeWidget("Frame", {"background": "#c9ced3", "highlightbackground": "SystemButtonFace", "highlightcolor": "SystemWindowFrame"})
    canvas = FakeWidget("Canvas", {"background": "#ffffff", "highlightbackground": "#bbbbbb"})
    menu = FakeWidget("Menu", {"background": "SystemMenu", "foreground": "SystemMenuText", "activebackground": "SystemHighlight",
                               "activeforeground": "SystemHighlightText", "selectcolor": "black"})
    tree = FakeWidget("Treeview", {}, tree_tags={"chg": {"foreground": "#b45f06"}, "feas": {"background": "#d8f0d8"},
                                                  "low": {"foreground": "#b00020"}, "edge": {"foreground": "#b45f06"}})
    top = FakeWidget("Toplevel", {"background": "SystemButtonFace"}, kids=[lbl, muted, plain, status, log, grip, canvas, menu, tree])
    T.retheme(top)
    d_ = lambda r: T.color(r, "dark")
    check("retheme: ttk Label peran warn -> gelap", lbl.opts["foreground"] == d_("warn"), lbl.opts["foreground"])
    check("retheme: abu '#555' -> muted gelap", muted.opts["foreground"] == d_("muted"))
    check("retheme: ttk Label tanpa warna tetap kosong", plain.opts["foreground"] == "")
    check("retheme: Text status latar dan teks", status.opts["background"] == d_("surface") and status.opts["foreground"] == d_("fg"),
          str(status.opts))
    check("retheme: tag Text warn/err", status.tags["warn"]["foreground"] == d_("warn") and status.tags["err"]["foreground"] == d_("bad"))
    check("retheme: seleksi Text memakai peran accent/selfg", status.opts["selectbackground"] == d_("accent") and status.opts["selectforeground"] == d_("selfg"))
    check("retheme: log tetap gelap (latar peran logbg, teks tidak diubah)",
          log.opts["background"] == d_("logbg") and log.opts["foreground"] == "#d7dde3" and log.tags["cmd"]["foreground"] == "#7fd1ff")
    check("retheme: pegangan log dan kanvas", grip.opts["background"] == d_("grip") and canvas.opts["background"] == d_("field")
          and canvas.opts["highlightbackground"] == d_("border"))
    check("retheme: nilai bawaan sistem (SystemButtonFace) -> bg", grip.opts["highlightbackground"] == d_("bg") and top.opts["background"] == d_("bg"))
    check("retheme: Menu diwarnai eksplisit", menu.opts["background"] == d_("field") and menu.opts["activebackground"] == d_("accent"))
    check("retheme: tag Treeview", tree.tree_tags["chg"]["foreground"] == d_("warn") and tree.tree_tags["feas"]["background"] == d_("feas")
          and tree.tree_tags["low"]["foreground"] == d_("bad"))
    T.MODE = "light"
    T.retheme(top)
    l_ = lambda r: T.color(r, "light")
    check("retheme: kembali ke terang (peran sama)", lbl.opts["foreground"] == l_("warn") and status.opts["background"] == l_("surface")
          and tree.tree_tags["feas"]["background"] == l_("feas") and status.tags["err"]["foreground"] == l_("bad"))
    check("retheme: peralihan berulang stabil", (T.retheme(top), lbl.opts["foreground"])[1] == l_("warn"))
    T.MODE = "light"


def lit_leftovers(root, tk, T):
    """Widget tk (bukan log) yang masih memakai warna TERANG dari peran saat mode gelap."""
    light = {T.ROLES[r][0].lower(): r for r in ("surface", "field", "grip", "feas", "border", "tip", "button", "tab", "active")}
    light["#f0f0f0"] = "bg"
    bad = []

    def walk(w):
        yield w
        for c in w.winfo_children():
            yield from walk(c)
    for w in walk(root):
        cls = w.winfo_class()
        if cls in ("Text", "Canvas", "Frame", "Toplevel", "Tk", "Label", "Button", "Menu"):
            for opt in ("background", "foreground"):
                try:
                    v = str(w.cget(opt)).lower()
                except Exception:
                    continue
                if v in light and light[v] != T.role_of(T.ROLES[light[v]][1]) and v != T.ROLES[light[v]][1].lower():
                    bad.append(f"{w} {cls}.{opt}={v}")
    return bad


def part_b(size, shots):
    try:
        import tkinter as tk
    except ImportError:
        print("B: dilewati (tkinter tidak terpasang di sini)")
        return
    from tkinter import messagebox, ttk
    from cstopt.gui import app as gapp, theme as T
    from test_gui_g4 import parse_sizes, pump, shot, wait_for
    SW, SH, scaling = parse_sizes(size)[0]
    tag = f"{SW}x{SH}@{scaling}"
    print(f"B: layar tiruan {tag}")
    tk.Misc.winfo_screenwidth = lambda self, _w=SW: _w
    tk.Misc.winfo_screenheight = lambda self, _h=SH: _h
    T.PREF_PATH = os.path.join(tempfile.mkdtemp(), "pref.json")           # jangan menimpa pilihan pengguna
    root = tk.Tk()
    root.report_callback_exception = lambda *e: (print("  [GAGAL] galat callback Tk:", e[1]), FAILS.append("callback Tk"))
    root.tk.call("tk", "scaling", scaling)
    messagebox.showwarning = lambda *a, **k: None
    messagebox.showinfo = lambda *a, **k: None
    a = gapp.App(root)
    wait_for(root, lambda: a.status.get("run") and not a._status_busy)
    pump(root, 0.5)
    st = ttk.Style(root)
    check("bawaan: mode gelap dan tema ttk clam", T.MODE == "dark" and st.theme_use() == "clam")
    check("tombol Tema menampilkan mode aktif", a.theme_btn.cget("text") == "Tema: gelap")
    check("gaya Treeview gelap", st.lookup("Treeview", "background") == T.color("field", "dark"))
    check("status ringkas bernuansa gelap", a.status_text.cget("background") == T.color("surface", "dark"))
    check("tidak ada warna terang tersisa (gelap)", not lit_leftovers(root, tk, T), "; ".join(lit_leftovers(root, tk, T)[:5]))
    for i in range(a.nb.index("end")):
        a.nb.select(i)
        pump(root, 0.3)
        shot(root, shots, f"t1_{tag}_gelap_tab{i + 1}")
    a.nb.select(6)
    tree = a.data_tab.tree
    feas_bg = str(tree.tag_configure("feas", "background"))
    check("tag hijau Treeview (feasible) memakai warna gelap", feas_bg.lower() == T.color("feas", "dark").lower(), feas_bg)

    # dialog dan jendela grafik terbuka saat tema berganti
    a.open_bounds()
    pump(root, 0.5)
    tops = [w for w in root.winfo_children() if w.winfo_class() == "Toplevel"]
    check("dialog rentang terbuka dan bergaya gelap", bool(tops) and str(tops[0].cget("background")).lower() == T.color("bg", "dark").lower())
    shot(root, shots, f"t1_{tag}_gelap_dialog_rentang")
    a.data_tab.open_plot("scatter")
    pump(root, 1.0)
    pw = [w for w in root.winfo_children() if w.winfo_class() == "Toplevel" and hasattr(w, "fig")]
    check("jendela grafik terbuka", bool(pw))
    if pw:
        import matplotlib
        check("grafik gelap: latar figur dan sumbu", matplotlib.colors.to_hex(pw[0].fig.get_facecolor()).lower() == T.color("bg", "dark").lower()
              and matplotlib.colors.to_hex(pw[0].ax.get_facecolor()).lower() == T.color("field", "dark").lower())
        shot(root, shots, f"t1_{tag}_gelap_grafik")

    a.theme_btn.invoke()
    pump(root, 1.0)
    check("tombol -> mode terang, tema ttk kembali ke awal", T.MODE == "light" and st.theme_use() != "clam" or T.MODE == "light")
    check("tombol Tema menampilkan 'terang'", a.theme_btn.cget("text") == "Tema: terang")
    check("status ringkas terang", a.status_text.cget("background").lower() == T.color("surface", "light").lower(), a.status_text.cget("background"))
    check("pilihan terang tersimpan", T.load_pref(T.PREF_PATH) == "light")
    if pw:
        check("grafik terbuka ikut terang", matplotlib.colors.to_hex(pw[0].fig.get_facecolor()).lower() == "#ffffff"
              and matplotlib.colors.to_hex(pw[0].ax.get_facecolor()).lower() == "#ffffff")
        shot(root, shots, f"t1_{tag}_terang_grafik")
    for i in range(a.nb.index("end")):
        a.nb.select(i)
        pump(root, 0.3)
        shot(root, shots, f"t1_{tag}_terang_tab{i + 1}")
    a.theme_btn.invoke()
    pump(root, 1.0)
    check("kembali ke gelap: tag Treeview dan status", T.MODE == "dark" and a.status_text.cget("background").lower() == T.color("surface", "dark").lower())
    check("tidak ada warna terang tersisa setelah bolak balik", not lit_leftovers(root, tk, T), "; ".join(lit_leftovers(root, tk, T)[:5]))
    # perintah nyata: log ikut tema
    a.runner  # noqa: B018
    a._log("[uji] baris log\n", "ok")
    check("warna baris log terakhir mengikuti mode", str(a.last_lbl.cget("foreground")).lower() == T.color("ok", "dark").lower(), str(a.last_lbl.cget("foreground")))
    root.destroy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default=None)
    ap.add_argument("--size", default="1366x728@1.333")
    args = ap.parse_args()
    part_a()
    part_b(args.size, args.shot)
    print("\nSEMUA LULUS" if not FAILS else f"\n{len(FAILS)} GAGAL: {FAILS}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
