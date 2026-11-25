"""Override rentang parameter (BOUNDS) per run (G2).

Berkas: data/<RUN>/bounds_override.json  ->  {"bounds": {"Lp": [15.0, 25.0], ...}, "catatan": "..."}
File desain (designs/*.py) TIDAK pernah diedit. Tanpa berkas override, rentang = BOUNDS file desain (perilaku lama, IDENTIK).
Modul ini ringan (hanya json/os) agar bisa dipakai LHS, ml.core, CLI `bounds`, dan GUI tanpa impor berat.
"""
import json
import math
import os
import sys
from datetime import datetime

OVERRIDE_FILE = "bounds_override.json"
_ANNOUNCED = set()
_CACHE = {}


def run_dir(mod):
    return os.path.dirname(os.path.abspath(mod.DATASET_CSV))


def override_path(mod):
    return os.path.join(run_dir(mod), OVERRIDE_FILE)


def base_bounds(mod):
    return {k: (float(v[0]), float(v[1])) for k, v in mod.BOUNDS.items()}


def check_bounds(params, new):
    """Daftar masalah (kosong = valid) untuk dict {param: (lo, hi)}."""
    bad = []
    for k, v in new.items():
        if k not in params:
            bad.append(f"parameter tidak dikenal: {k}")
            continue
        try:
            lo, hi = float(v[0]), float(v[1])
        except (TypeError, ValueError, IndexError):
            bad.append(f"{k}: nilai harus [min, max]")
            continue
        if not (math.isfinite(lo) and math.isfinite(hi)):
            bad.append(f"{k}: nilai tidak hingga")
        elif lo >= hi:
            bad.append(f"{k}: min ({lo:g}) harus lebih kecil dari max ({hi:g})")
    return bad


def read_override(mod):
    """Kembalikan {param: (lo, hi)} dari berkas override ({} bila tidak ada). Berkas rusak -> RuntimeError (tidak diam-diam diabaikan)."""
    p = override_path(mod)
    if not os.path.exists(p):
        return {}
    key = (p, os.stat(p).st_mtime_ns, os.stat(p).st_size)
    if key in _CACHE:
        return dict(_CACHE[key])
    try:
        with open(p, encoding="utf-8") as fh:
            raw = json.load(fh)
        ov = raw.get("bounds", raw)
        if not isinstance(ov, dict):
            raise ValueError("isi 'bounds' harus objek {parameter: [min, max]}")
    except (OSError, ValueError) as e:
        raise RuntimeError(f"{p} tidak bisa dibaca: {e}. Perbaiki atau hapus (py main.py bounds --reset).")
    bad = check_bounds(list(mod.PARAM_NAMES), ov)
    if bad:
        raise RuntimeError(f"{p} tidak valid: " + "; ".join(bad) + ". Perbaiki atau hapus (py main.py bounds --reset).")
    out = {k: (float(v[0]), float(v[1])) for k, v in ov.items()}
    _CACHE.clear()
    _CACHE[key] = out
    return dict(out)


def effective_bounds(mod, announce=True):
    """(bounds {param: (lo, hi)}, daftar parameter yang berbeda dari file desain). Mencetak satu baris sekali per proses ke stderr
    bila ada parameter yang berbeda, agar override tidak pernah diam-diam."""
    b = base_bounds(mod)
    ov = read_override(mod)
    changed = [k for k, v in ov.items() if v != b.get(k)]
    b.update(ov)
    p = override_path(mod)
    if announce and changed and p not in _ANNOUNCED:
        _ANNOUNCED.add(p)
        print(f"[opsi] rentang parameter dari {OVERRIDE_FILE} ({len(changed)} berbeda dari file desain: {', '.join(changed)}); "
              f"hapus dengan: py main.py bounds --reset", file=sys.stderr)
    return b, changed


def write_override(mod, new, note=""):
    """Tulis override (gabungan dengan yang ada: parameter di `new` menggantikan). Salinan lama disimpan sebagai .bak. Kembalikan path."""
    bad = check_bounds(list(mod.PARAM_NAMES), new)
    if bad:
        raise ValueError("; ".join(bad))
    cur = read_override(mod)
    cur.update({k: (float(v[0]), float(v[1])) for k, v in new.items()})
    p = override_path(mod)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh, open(p + ".bak", "w", encoding="utf-8") as bk:
            bk.write(fh.read())
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"bounds": {k: [v[0], v[1]] for k, v in cur.items()}, "catatan": note,
                   "ditulis": datetime.now().isoformat(timespec="seconds")}, fh, indent=1)
    os.replace(tmp, p)
    _CACHE.clear()
    return p


def reset_override(mod):
    """Hapus override. True bila ada yang dihapus."""
    p = override_path(mod)
    _CACHE.clear()
    if os.path.exists(p):
        os.remove(p)
        return True
    return False
