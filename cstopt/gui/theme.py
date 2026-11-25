"""T1: tema gelap/terang untuk GUI (tkinter + ttk + matplotlib).

Ide dasar: warna diperlakukan sebagai PERAN (bg, fg, muted, warn, ...), bukan angka heksadesimal.
- Kode GUI lama menulis warna terang secara langsung (mis. foreground="#b45f06"). `retheme()` berjalan di seluruh
  pohon widget dan mengganti tiap warna yang dikenali (literal terang, literal gelap, atau nama warna sistem)
  dengan warna peran yang sama untuk mode aktif. Jadi kode lama tidak perlu diubah satu per satu dan peralihan
  gelap <-> terang bisa berulang tanpa kehilangan warna aslinya.
- Warna yang diatur saat berjalan memakai `color("peran")`.
- Mode gelap memakai tema ttk `clam` (tema bawaan Windows tidak bisa diwarnai). Mode terang mengembalikan tema ttk
  awal, jadi tampilan terang sama seperti sebelum T1.
- matplotlib: `rcParams` diganti saat mode berubah (grafik baru ikut). Jendela grafik yang terbuka mendaftar lewat
  `add_listener` supaya digambar ulang. PNG hasil CLI (train, pareto) tidak diubah: tetap berlatar putih, hanya
  bingkai kanvasnya yang gelap.

Fungsi murni (palet, peran, kontras, penyimpanan pilihan) tidak butuh tkinter dan diuji di `tools/test_gui_t1.py`.
"""
import json
import os

# peran: (terang, gelap, nama lain yang dikenali sebagai peran yang sama)
ROLES = {
    "bg":      ("#f0f0f0", "#2b2d31", ("SystemButtonFace", "#d9d9d9", "SystemMenu")),
    "surface": ("#f6f6f6", "#35383d", ("#f5f5f5",)),
    "field":   ("#ffffff", "#33363b", ("SystemWindow", "white")),
    "fg":      ("#000000", "#e6e6e6", ("SystemWindowText", "SystemButtonText", "SystemMenuText", "black", "#000")),
    "muted":   ("#666666", "#a3a9b0", ("#444", "#444444", "#555", "#555555", "#666", "SystemDisabledText")),
    "warn":    ("#b45f06", "#f0a050", ()),
    "bad":     ("#b00020", "#ff7b7b", ()),
    "ok":      ("#2e7d32", "#7fd07f", ()),
    "info":    ("#1565c0", "#6cb2ff", ()),
    "grip":    ("#c9ced3", "#4a4e55", ()),
    "feas":    ("#d8f0d8", "#2f4a35", ()),
    "border":  ("#bbbbbb", "#555a61", ("#999999", "#999")),
    "logbg":   ("#101418", "#1b1d20", ()),
    "tip":     ("#fffbe6", "#4a4430", ()),
    "active":  ("#ececec", "#3c4047", ()),
    "accent":  ("#0067c0", "#336cad", ("SystemHighlight", "#c3c3c3")),
    "selfg":   ("#ffffff", "#ffffff", ("SystemHighlightText",)),
    "button":  ("#e1e1e1", "#40444b", ()),
    "tab":     ("#e8e8e8", "#383b40", ()),
    "trough":  ("#e4e4e4", "#25272b", ()),
}
MODES = ("light", "dark")

_ROLE_OF = {}
for _r, (_l, _d, _alias) in ROLES.items():
    for _c in (_l, _d) + tuple(_alias):
        _ROLE_OF.setdefault(_c.lower(), _r)
# beberapa literal berbagi nilai antar peran (mis. terang "bg" = "#f0f0f0"); yang pertama didaftarkan menang.

MODE = "light"
_ORIG_THEME = [None]
_LISTENERS = []
PREF_PATH = os.path.join(os.path.expanduser("~"), ".cstopt_gui.json")
DEFAULT_MODE = "dark"
TREE_TAGS = ("chg", "low", "feas", "edge")


# ---------------------------------------------------------------------------------------------- fungsi murni
def color(role, mode=None):
    """Warna peran untuk mode (bawaan: mode aktif)."""
    m = mode or MODE
    return ROLES[role][1 if m == "dark" else 0]


def role_of(literal):
    """Peran dari sebuah warna (literal terang atau gelap atau nama sistem); None bila tidak dikenal."""
    if literal is None:
        return None
    return _ROLE_OF.get(str(literal).strip().lower())


def convert(literal, mode=None):
    """Warna yang setara untuk mode; warna yang tidak dikenal dikembalikan apa adanya."""
    r = role_of(literal)
    return color(r, mode) if r else literal


def _lum(hexcolor):
    h = hexcolor.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]


def contrast(a, b):
    """Rasio kontras WCAG antara dua warna heksadesimal."""
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def load_pref(path=None):
    try:
        with open(path or PREF_PATH, encoding="utf-8") as fh:
            m = json.load(fh).get("theme")
        return m if m in MODES else DEFAULT_MODE
    except (OSError, ValueError, AttributeError):
        return DEFAULT_MODE


def save_pref(mode, path=None):
    try:
        with open(path or PREF_PATH, "w", encoding="utf-8") as fh:
            json.dump({"theme": mode}, fh)
        return True
    except OSError:
        return False


def mpl_rc(mode):
    """rcParams matplotlib untuk mode gelap; mode terang memakai nilai bawaan matplotlib (diisi oleh `_apply_mpl`)."""
    if mode != "dark":
        return {}
    bg, ax, fg = color("bg", "dark"), color("field", "dark"), color("fg", "dark")
    return {
        "figure.facecolor": bg, "figure.edgecolor": bg,
        "axes.facecolor": ax, "axes.edgecolor": color("border", "dark"),
        "axes.labelcolor": fg, "text.color": fg,
        "xtick.color": color("muted", "dark"), "ytick.color": color("muted", "dark"),
        "grid.color": "#4a4e55",
        "legend.facecolor": ax, "legend.edgecolor": color("border", "dark"), "legend.labelcolor": fg,
    }


def add_listener(fn):
    if fn not in _LISTENERS:
        _LISTENERS.append(fn)


def remove_listener(fn):
    if fn in _LISTENERS:
        _LISTENERS.remove(fn)


def _apply_mpl(mode):
    try:
        import matplotlib as mpl
    except ImportError:
        return
    keys = set(mpl_rc("dark"))
    for k in keys:                                        # kembali ke bawaan dulu, lalu timpa bila gelap
        try:
            mpl.rcParams[k] = mpl.rcParamsDefault[k]
        except KeyError:
            pass
    for k, v in mpl_rc(mode).items():
        try:
            mpl.rcParams[k] = v
        except (KeyError, ValueError):
            pass                                          # kunci tidak ada di matplotlib lama: dilewati


# ---------------------------------------------------------------------------------------------- ttk
def _style_dark(st, root):
    P = {r: color(r, "dark") for r in ROLES}
    bg, fg, field, muted, border, accent = P["bg"], P["fg"], P["field"], P["muted"], P["border"], P["accent"]
    btn, act, tab = P["button"], P["active"], P["tab"]
    st.configure(".", background=bg, foreground=fg, fieldbackground=field, troughcolor=P["trough"], bordercolor=border,
                 darkcolor=bg, lightcolor=bg, selectbackground=accent, selectforeground=P["selfg"], insertcolor=fg,
                 focuscolor=accent)
    st.map(".", foreground=[("disabled", muted)], background=[("disabled", bg)])
    st.configure("TButton", background=btn, foreground=fg, bordercolor=border, lightcolor=btn, darkcolor=btn)
    st.map("TButton", background=[("disabled", bg), ("pressed", P["border"]), ("active", "#4a4f57")],
           lightcolor=[("pressed", btn), ("active", "#4a4f57")], darkcolor=[("pressed", btn), ("active", "#4a4f57")],
           foreground=[("disabled", muted)], bordercolor=[("disabled", P["border"])])
    st.configure("TMenubutton", background=btn, foreground=fg, bordercolor=border, arrowcolor=fg, lightcolor=btn, darkcolor=btn)
    st.map("TMenubutton", background=[("disabled", bg), ("active", "#4a4f57")], foreground=[("disabled", muted)])
    for name in ("TEntry", "TSpinbox"):
        st.configure(name, fieldbackground=field, foreground=fg, insertcolor=fg, bordercolor=border,
                     lightcolor=border, darkcolor=border, arrowcolor=fg, background=btn)
        st.map(name, fieldbackground=[("disabled", bg), ("readonly", bg)], foreground=[("disabled", muted)],
               bordercolor=[("focus", accent)])
    st.configure("TCombobox", fieldbackground=field, background=btn, foreground=fg, arrowcolor=fg, bordercolor=border,
                 lightcolor=border, darkcolor=border, insertcolor=fg, selectbackground=field, selectforeground=fg)
    st.map("TCombobox", fieldbackground=[("readonly", field), ("disabled", bg)], foreground=[("readonly", fg), ("disabled", muted)],
           selectbackground=[("readonly", field)], selectforeground=[("readonly", fg)],
           background=[("active", "#4a4f57"), ("disabled", bg)], bordercolor=[("focus", accent)])
    st.configure("TNotebook", background=bg, bordercolor=border, lightcolor=border, darkcolor=border)
    st.configure("TNotebook.Tab", background=tab, foreground=muted, bordercolor=border, lightcolor=border, darkcolor=border)
    st.map("TNotebook.Tab", background=[("selected", bg), ("active", act)], foreground=[("selected", fg), ("active", fg)],
           lightcolor=[("selected", border)], bordercolor=[("selected", border)])
    st.configure("TFrame", background=bg)
    st.configure("TLabel", background=bg, foreground=fg)
    st.configure("TLabelframe", background=bg, bordercolor=border, lightcolor=border, darkcolor=border)
    st.configure("TLabelframe.Label", background=bg, foreground=fg)
    for name in ("TCheckbutton", "TRadiobutton"):
        st.configure(name, background=bg, foreground=fg, indicatorbackground=field, indicatorforeground=fg,
                     upperbordercolor=border, lowerbordercolor=border, indicatorcolor=field)
        st.map(name, background=[("active", bg)], foreground=[("disabled", muted)],
               indicatorbackground=[("pressed", act), ("disabled", bg)], indicatorcolor=[("selected", accent), ("pressed", act)])
    st.configure("TScrollbar", background="#454951", troughcolor=P["trough"], bordercolor=bg, arrowcolor=fg,
                 lightcolor="#454951", darkcolor="#454951")
    st.map("TScrollbar", background=[("active", "#565b63"), ("pressed", "#656b73")])
    for name in ("Horizontal.TProgressbar", "Vertical.TProgressbar", "TProgressbar"):
        st.configure(name, troughcolor=P["trough"], background=accent, bordercolor=border, lightcolor=accent, darkcolor=accent)
    st.configure("Treeview", background=field, fieldbackground=field, foreground=fg, bordercolor=border,
                 lightcolor=border, darkcolor=border)
    st.map("Treeview", background=[("selected", accent)], foreground=[("selected", P["selfg"])])
    st.configure("Treeview.Heading", background=tab, foreground=fg, bordercolor=border, lightcolor=tab, darkcolor=tab, relief="flat")
    st.map("Treeview.Heading", background=[("active", act)])
    st.configure("TSeparator", background=border)
    st.configure("TSizegrip", background=bg)


def _fix_tree_tags(st):
    """Perbaikan Tk 8.6.9 (Windows, tema terang): peta warna Treeview tanpa entri yang menutup warna tag."""
    try:
        def fixed(opt):
            return [e for e in st.map("Treeview", query_opt=opt) if tuple(e[:2]) != ("!disabled", "!selected")]
        st.map("Treeview", foreground=fixed("foreground"), background=fixed("background"))
    except Exception:
        pass


def _option_db(root):
    """Warna bawaan untuk widget tk (non-ttk) yang dibuat SESUDAH ini: bilah alat matplotlib, dialog, menu."""
    def o(pattern, value):
        root.option_add(pattern, value, 80)
    o("*Toplevel.background", color("bg"))
    o("*Frame.background", color("bg"))
    o("*Canvas.background", color("bg"))
    o("*Label.background", color("bg"))
    o("*Label.foreground", color("fg"))
    o("*Button.background", color("button"))
    o("*Button.foreground", color("fg"))
    o("*Button.activeBackground", color("active"))
    o("*Button.activeForeground", color("fg"))
    o("*Checkbutton.background", color("bg"))
    o("*Checkbutton.foreground", color("fg"))
    o("*Checkbutton.activeBackground", color("active"))
    o("*Checkbutton.selectColor", color("field"))
    o("*Text.background", color("field"))
    o("*Text.foreground", color("fg"))
    o("*Text.insertBackground", color("fg"))
    o("*Listbox.background", color("field"))
    o("*Listbox.foreground", color("fg"))
    o("*Menu.background", color("field"))
    o("*Menu.foreground", color("fg"))
    o("*Menu.activeBackground", color("accent"))
    o("*Menu.activeForeground", color("selfg"))
    o("*TCombobox*Listbox.background", color("field"))          # daftar turun combobox (listbox tk biasa)
    o("*TCombobox*Listbox.foreground", color("fg"))
    o("*TCombobox*Listbox.selectBackground", color("accent"))
    o("*TCombobox*Listbox.selectForeground", color("selfg"))


# ---------------------------------------------------------------------------------------------- pohon widget
_COLOR_OPTS = ("background", "foreground", "activebackground", "activeforeground", "highlightbackground",
               "highlightcolor", "insertbackground", "selectbackground", "selectforeground", "disabledforeground",
               "troughcolor", "selectcolor")
_TTK_COLOR_OPTS = ("foreground", "background")


def _walk(w):
    yield w
    try:
        kids = w.winfo_children()
    except Exception:
        kids = []
    for c in kids:
        yield from _walk(c)


def _cget(w, opt):
    try:
        return str(w.cget(opt))
    except Exception:
        return None


def _set(w, **kw):
    try:
        w.configure(**kw)
    except Exception:
        pass


def _recolor(w):
    cls = w.winfo_class()
    is_ttk = (cls.startswith("T") and cls not in ("Tk", "Toplevel", "Text")) or cls == "Treeview"
    if cls == "Menu":
        _set(w, background=color("field"), foreground=color("fg"), activebackground=color("accent"),
             activeforeground=color("selfg"), selectcolor=color("fg"))
        return
    for opt in (_TTK_COLOR_OPTS if is_ttk else _COLOR_OPTS):
        cur = _cget(w, opt)
        if not cur:
            continue
        new = convert(cur)
        if new != cur:
            _set(w, **{opt: new})
    if cls in ("Text", "Entry", "Spinbox", "Listbox"):
        _set(w, selectbackground=color("accent"), selectforeground=color("selfg"))
    if cls == "Text":
        for tag in w.tag_names():
            if tag == "sel":
                continue
            for opt in ("foreground", "background"):
                try:
                    cur = str(w.tag_cget(tag, opt))
                except Exception:
                    continue
                if cur and convert(cur) != cur:
                    try:
                        w.tag_configure(tag, **{opt: convert(cur)})
                    except Exception:
                        pass
    if cls == "Treeview":
        for tag in TREE_TAGS:
            try:
                d = w.tag_configure(tag)
            except Exception:
                continue
            for opt in ("foreground", "background"):
                cur = str((d or {}).get(opt) or "")
                if cur and convert(cur) != cur:
                    try:
                        w.tag_configure(tag, **{opt: convert(cur)})
                    except Exception:
                        pass


def retheme(widget):
    """Warnai ulang `widget` dan seluruh turunannya sesuai mode aktif. Aman dipanggil berulang."""
    for w in _walk(widget):
        _recolor(w)


def apply(root, mode):
    """Pasang mode ("dark" atau "light") untuk seluruh aplikasi."""
    global MODE
    from tkinter import ttk
    MODE = "dark" if mode == "dark" else "light"
    st = ttk.Style(root)
    if _ORIG_THEME[0] is None:
        _ORIG_THEME[0] = st.theme_use()
    if MODE == "dark":
        st.theme_use("clam")
        _style_dark(st, root)
    else:
        st.theme_use(_ORIG_THEME[0])
        _fix_tree_tags(st)
    _option_db(root)
    _apply_mpl(MODE)
    retheme(root)
    for fn in list(_LISTENERS):
        try:
            fn(MODE)
        except Exception:
            pass
    return MODE


def init(root, mode=None):
    """Dipanggil sekali di awal aplikasi, sebelum widget dibuat (memakai pilihan tersimpan bila `mode` kosong)."""
    return apply(root, mode or load_pref())


def toggle(root):
    new = "light" if MODE == "dark" else "dark"
    apply(root, new)
    save_pref(new)
    return new
