"""
Uji cepat instalasi (tanpa CST):  py tools/smoke_test.py

Memeriksa paket Python, semua file di designs/, pembangkitan sampel kecil, dan keberadaan CST.
Berguna setelah clone di perangkat lain.
"""
import importlib
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
fails = 0


def check(label, ok, detail=""):
    global fails
    fails += 0 if ok else 1
    print(f"  [{'OK' if ok else 'GAGAL'}] {label}" + (f"  {detail}" if detail else ""))


print(f"Python {sys.version.split()[0]} di {sys.platform}")
print("\nPaket ML (wajib):")
for mod, pip in [("numpy", "numpy"), ("pandas", "pandas"), ("scipy", "scipy"), ("sklearn", "scikit-learn"),
                 ("matplotlib", "matplotlib"), ("joblib", "joblib")]:
    check(pip, importlib.util.find_spec(mod) is not None)
print("\nOpsional:")
for mod, label in [("PIL", "pillow (tampilan gambar di GUI)"), ("tkinter", "tkinter (GUI)")]:
    ok = importlib.util.find_spec(mod) is not None
    print(f"  [{'OK' if ok else 'tidak ada'}] {label}")
cst = importlib.util.find_spec("cst") is not None and sys.platform == "win32"
print(f"  [{'OK' if cst else 'tidak ada'}] CST (cst-studio-suite-link + Windows): "
      + ("tab Simulasi CST aktif" if cst else "perintah `run` dan `export` tidak tersedia (bagian ML tetap jalan)"))

print("\nDesain:")
from cstopt import paths                                  # noqa: E402
from cstopt.loader import load_design_module              # noqa: E402

names = paths.list_designs()
check("ada file desain di designs/", bool(names), ", ".join(names))
for n in names:
    try:
        mod = load_design_module(n)
        need = ["NAME", "RUN_NAME", "PARAM_NAMES", "BOUNDS", "DATASET_CSV", "TARGETS"]
        miss = [k for k in need if not hasattr(mod, k)]
        check(f"{n}: atribut wajib", not miss, f"hilang: {miss}" if miss else "")
        if hasattr(mod, "STAGES") or (hasattr(mod, "OBJECTIVE") and hasattr(mod, "CONSTRAINTS")):
            from cstopt.ml import core as mc              # noqa: E402
            d = mc.load_design(n)
            check(f"{n}: Design terbentuk", True, f"{len(d.params)} parameter, {len(d.stages)} tahap BO")
        else:
            check(f"{n}: objective/constraint", False, "tidak ada STAGES atau OBJECTIVE+CONSTRAINTS")
        if hasattr(mod, "geometry_problems"):
            from cstopt.sampling import lhs               # noqa: E402
            x, params, _ = lhs.generate(10, mod, seed=1, n_start=3, n_iter=300)
            bad = [p for p in params if mod.geometry_problems(p)]
            check(f"{n}: LHS 10 sampel valid geometri", not bad)
    except Exception as e:
        check(f"{n}", False, f"{type(e).__name__}: {e}")

print("\n" + ("SEMUA LULUS" if not fails else f"{fails} pemeriksaan gagal"))
sys.exit(1 if fails else 0)
