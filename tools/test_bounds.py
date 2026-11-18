"""Uji cepat override rentang parameter (G2a), tanpa CST dan tanpa menjalankan suggest.

  py tools\\test_bounds.py
Memakai desain bawaan (FR-4). Berkas override yang sudah ada dicadangkan lalu dipulihkan. Uji regresi `suggest` seed 0 tetap lewat compare_csv.py
(lihat PROGRESS.md): tanpa override, dan setelah `py main.py bounds --reset`, hasilnya harus IDENTIK.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cstopt import boundsio  # noqa: E402
from cstopt.ml import bounds as cli  # noqa: E402
from cstopt.ml import core as mc  # noqa: E402
from cstopt.sampling import lhs  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  [OK]   " if cond else "  [GAGAL] ") + name + (f"  {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)


def raises(fn, exc=Exception):
    try:
        fn()
    except exc:
        return True
    return False


def main():
    d0 = mc.load_design(None)
    mod = d0.mod
    path = boundsio.override_path(mod)
    saved = None
    if os.path.exists(path):
        saved = tempfile.mktemp()
        shutil.copy(path, saved)
        os.remove(path)
    bak = path + ".bak"
    had_bak = os.path.exists(bak)
    try:
        params = list(mod.PARAM_NAMES)
        base = boundsio.base_bounds(mod)
        # 1. validasi
        check("min >= max ditolak", len(boundsio.check_bounds(params, {"Lp": (25, 15)})) == 1)
        check("parameter tidak dikenal ditolak", len(boundsio.check_bounds(params, {"XX": (1, 2)})) == 1)
        check("nilai NaN ditolak", len(boundsio.check_bounds(params, {"Lp": (float("nan"), 2)})) == 1)
        check("rentang sah diterima", boundsio.check_bounds(params, {"Lp": (15, 26)}) == [])
        # 2. tanpa override = identik
        b, ch = boundsio.effective_bounds(mod, announce=False)
        check("tanpa override: rentang = BOUNDS file desain dan tidak ada yang berbeda", b == base and ch == [])
        # 3. tulis, baca, Design, LHS
        boundsio.write_override(mod, {"WU": (2.8, 13.0)}, "uji")
        d1 = mc.load_design(None)
        j = d1.params.index("WU")
        check("Design memakai override (lo WU = 2.8)", abs(d1.lo[j] - 2.8) < 1e-12 and abs(d1.hi[j] - 13.0) < 1e-12 and d1.bounds_changed == ["WU"])
        check("parameter lain tidak berubah", all(d1.lo[i] == d0.lo[i] and d1.hi[i] == d0.hi[i] for i in range(len(params)) if i != j))
        u = d1.to_unit(d1.from_unit(d1.lo * 0 + 0.5))
        check("to_unit dan from_unit konsisten", abs(u - 0.5).max() < 1e-9)
        row = lhs.to_params(d1.lo * 0, mod)
        check("LHS memakai rentang yang sama (u=0 -> 2.8)", abs(row["WU"] - 2.8) < 1e-9)
        boundsio.write_override(mod, {"Lp": (14.0, 25.0)}, "uji 2")
        check("penulisan kedua menggabungkan dan menyimpan .bak", os.path.exists(bak) and set(boundsio.read_override(mod)) == {"WU", "Lp"})
        # 4. berkas rusak tidak diam-diam diabaikan
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{ bukan json")
        check("berkas rusak -> RuntimeError", raises(lambda: boundsio.effective_bounds(mod), RuntimeError))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('{"bounds": {"XX": [1, 2]}}')
        check("parameter tidak dikenal di berkas -> RuntimeError", raises(lambda: boundsio.effective_bounds(mod), RuntimeError))
        # 5. reset
        check("reset menghapus berkas", boundsio.reset_override(mod) and not os.path.exists(path))
        d2 = mc.load_design(None)
        check("setelah reset: lo/hi kembali identik", (d2.lo == d0.lo).all() and (d2.hi == d0.hi).all())
        check("reset kedua tidak mengubah apa pun", boundsio.reset_override(mod) is False)
        # 6. CLI: parse dan usulan
        check("parse_set sah", cli.parse_set("Lp=15:25, WD=2:9", params) == {"Lp": (15.0, 25.0), "WD": (2.0, 9.0)})
        check("parse_set min > max ditolak", raises(lambda: cli.parse_set("Lp=25:15", params), ValueError))
        check("parse_set parameter asing ditolak", raises(lambda: cli.parse_set("foo=1:2", params), ValueError))
        check("parse_set format salah ditolak", raises(lambda: cli.parse_set("Lp=15-25", params), ValueError))
        new, _ = cli.propose(d0, {"WD": "atas", "LU": "bawah", "PU": "bawah"}, 0.2)
        jl, jw, jp = d0.params.index("LU"), d0.params.index("WD"), d0.params.index("PU")
        check("usulan atas: WD diperlebar 20% dari lebar", abs(new["WD"][1] - round(d0.hi[jw] + 0.2 * (d0.hi[jw] - d0.lo[jw]), d0.decimals)) < 1e-9)
        check("batas bawah positif tidak turun di bawah 0,5 x lama (LU)", abs(new["LU"][0] - 0.5 * d0.lo[jl]) < 1e-9, str(new["LU"]))
        check("batas bawah negatif diperlebar biasa (PU)", new["PU"][0] < d0.lo[jp])
        v = cli.valid_fraction(d0, {p: (float(d0.lo[i]), float(d0.hi[i])) for i, p in enumerate(d0.params)}, m=500)
        check("valid_fraction antara 0 dan 100", v is not None and 0 <= v <= 100)
    finally:
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
