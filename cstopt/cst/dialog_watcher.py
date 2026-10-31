"""
Penekan dialog Yes/Ya untuk CST, dijalankan sebagai PROSES TERPISAH.
Dipanggil otomatis oleh  main.py run --auto-yes , atau jalankan manual:

  py cstopt/cst/dialog_watcher.py            pantau terus; tekan Yes HANYA pada dialog yang dikenal
  py cstopt/cst/dialog_watcher.py --diag     DIAGNOSA: cetak semua jendela kecil milik CST beserta isinya
  py cstopt/cst/dialog_watcher.py --verbose  ikut cetak jendela lain (progress, plot, lisensi) satu kali per teks

Aturan keamanan: tombol Yes ditekan hanya jika teks dialog memuat salah satu ALLOW_KEYWORDS:
  - "recalculate"             -> "All required results are already present. Recalculate?"
  - "abort this calculation"  -> konfirmasi setelah Anda menghentikan solver (mis. Ctrl+C)
Dialog Yes/No lain TIDAK disentuh; skrip hanya memberi peringatan satu kali.
Tambah kata kunci:  py cstopt/cst/dialog_watcher.py --keywords "kata1,kata2"

Butuh:  pip install pywinauto
"""
import argparse
import ctypes
import sys
import time
from ctypes import wintypes

YES = {"yes", "ya"}
ALLOW_KEYWORDS = ["recalculate", "abort this calculation"]
MAX_W, MAX_H = 900, 600            # jendela lebih besar dari ini dianggap jendela utama CST

if hasattr(ctypes, "windll"):
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
else:                                   # agar modul bisa diimpor untuk pengujian di luar Windows
    user32 = kernel32 = None
if user32 is not None:
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    kernel32.OpenProcess.restype = wintypes.HANDLE

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM) if user32 is not None else None


def exe_name(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)                    # QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        n = wintypes.DWORD(520)
        ok = kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
        return buf.value.lower() if ok else ""
    finally:
        kernel32.CloseHandle(h)


def info(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    title = ctypes.create_unicode_buffer(256)
    cls = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, title, 256)
    user32.GetClassNameW(hwnd, cls, 256)
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return {"hwnd": hwnd, "pid": pid.value, "title": title.value, "cls": cls.value,
            "w": r.right - r.left, "h": r.bottom - r.top,
            "owned": bool(user32.GetWindow(hwnd, 4))}               # GW_OWNER


def cst_windows():
    """Semua jendela terlihat milik proses CST (termasuk dialog milik jendela induk)."""
    found = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    out = []
    for hwnd in found:
        try:
            i = info(hwnd)
            if "cst" in exe_name(i["pid"]):
                out.append(i)
        except Exception:
            continue
    return out


def is_small(i):
    return 100 < i["w"] <= MAX_W and 40 < i["h"] <= MAX_H


def wrap(hwnd):
    from pywinauto.controls.uiawrapper import UIAWrapper
    from pywinauto.uia_element_info import UIAElementInfo
    return UIAWrapper(UIAElementInfo(handle_or_elem=hwnd))


def describe(w, i):
    lines = [f"JENDELA title='{i['title']}' class='{i['cls']}' ukuran={i['w']}x{i['h']} "
             f"milik_jendela_lain={i['owned']}"]
    try:
        for d in w.descendants():
            lines.append(f"    {str(d.element_info.control_type):12s} name='{d.window_text()}'")
    except Exception as e:
        lines.append(f"    (gagal membaca isi lewat UIA: {type(e).__name__}: {e})")
    return "\n".join(lines)


def should_click(text, keywords=None):
    """True hanya jika teks dialog memuat salah satu kata kunci yang diizinkan."""
    t = " ".join(str(text).lower().split())
    return any(k.lower() in t for k in (keywords or ALLOW_KEYWORDS))


def find_yes(kids):
    for b in kids:
        try:
            if (str(b.element_info.control_type) == "Button"
                    and b.window_text().replace("&", "").strip().lower() in YES):
                return b
        except Exception:
            continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diag", action="store_true")
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--heartbeat", type=float, default=0, help="cetak status tiap N detik (0 = mati)")
    ap.add_argument("--verbose", action="store_true", help="cetak juga jendela tanpa tombol Yes (sekali per teks)")
    ap.add_argument("--keywords", default="", help="kata kunci tambahan (pisahkan dengan koma)")
    args = ap.parse_args()
    keywords = ALLOW_KEYWORDS + [k.strip() for k in args.keywords.split(",") if k.strip()]

    try:
        import pywinauto  # noqa: F401
    except ImportError:
        print("[auto-yes] pywinauto belum terpasang:  pip install pywinauto")
        return 1

    if args.diag:
        wins = cst_windows()
        if not wins:
            print("Tidak ada jendela terlihat milik proses CST (cek apakah CST berjalan).")
        for i in wins:
            if is_small(i):
                print(describe(wrap(i["hwnd"]), i))
            else:
                print(f"(jendela besar: '{i['title'][:60]}' class='{i['cls']}' {i['w']}x{i['h']})")
        return 0

    print(f"[auto-yes] pemantau aktif. Hanya menekan Yes untuk dialog dengan teks: {keywords}", flush=True)
    printed, last_click, last_err, last_hb = set(), {}, None, time.time()
    while True:
        try:
            wins = cst_windows()
            if args.heartbeat and time.time() - last_hb >= args.heartbeat:
                last_hb = time.time()
                small = [f"'{x['title'][:30]}' {x['w']}x{x['h']}" for x in wins if is_small(x)]
                print(f"[auto-yes] aktif | jendela CST terlihat: {len(wins)} | kecil: {small}", flush=True)
            for i in wins:
                if not is_small(i):
                    continue
                hwnd = i["hwnd"]
                w = wrap(hwnd)
                kids = list(w.descendants())
                btn = find_yes(kids)
                texts = " | ".join(k.window_text() for k in kids
                                   if str(k.element_info.control_type) == "Text" and k.window_text().strip())
                key = (i["title"], texts)
                if btn is None:
                    if args.verbose and key not in printed:
                        printed.add(key)
                        print(f"[auto-yes] (info) '{i['title']}': {texts[:200]}", flush=True)
                    continue
                if should_click(texts, keywords):
                    if time.time() - last_click.get(hwnd, 0) < 5:
                        continue
                    print(f"[auto-yes] '{i['title']}': {texts[:200]} -> {btn.window_text()}", flush=True)
                    try:
                        btn.invoke()
                    except Exception:
                        btn.click_input()
                    last_click[hwnd] = time.time()
                elif key not in printed:
                    printed.add(key)
                    print(f"[auto-yes] PERINGATAN: dialog Yes/Ya TIDAK dikenal, tidak ditekan -> "
                          f"'{i['title']}': {texts[:200]}\n             Tekan manual, atau tambahkan "
                          "kata kuncinya dengan --keywords.", flush=True)
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            if msg != last_err:
                print(f"[auto-yes] peringatan: {msg}", flush=True)
                last_err = msg
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())