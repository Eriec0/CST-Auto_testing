"""Uji parameter substrat (tanpa CST): lebar saluran 50 ohm dan impedansi, baseline hs dan Wf yang diturunkan dari SUBSTRATE desain,
pemeriksaan hs dan Wf di project, dan penerapan di config.configure dan batch.check_substrate. Modul `cst` ditiru bila tidak terpasang.

  py tools\\test_substrate.py
"""
import contextlib
import io
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

try:                                                         # di Windows modul cst asli ada; di tempat lain ditiru
    import cst.interface  # noqa: F401
    import cst.results    # noqa: F401
except ImportError:
    _c = types.ModuleType("cst")
    _c.results, _c.interface = types.ModuleType("cst.results"), types.ModuleType("cst.interface")
    sys.modules.update({"cst": _c, "cst.results": _c.results, "cst.interface": _c.interface})

from cstopt import substrate as sb          # noqa: E402
from cstopt.loader import load_design_module  # noqa: E402
import wf50                                 # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print((" [OK]    " if cond else " [GAGAL] ") + name + (f"  {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)


class FakeM3D:
    def __init__(self, hs, wf, fail=False):
        self.v, self.fail = {"hs": hs, "Wf": wf}, fail

    def RestoreDoubleParameter(self, k):        # noqa: N802  (nama method CST)
        if self.fail:
            raise RuntimeError("ERROR: parameter tidak ada")
        return self.v[k]


def main():
    print("rumus")
    check("wf50 sama dengan tools/wf50.py (FR-4, RO4350B 1,524, RO4350B 1,6)",
          all(abs(sb.wf50(er, h) - wf50.wf(er, h)[0]) < 1e-9 for er, h in ((4.3, 1.6), (3.66, 1.524), (3.66, 1.6))))
    check("FR-4: er 4,3 dan h 1,6 memberi Wf 3,11 (nilai macro FR-4)", abs(sb.wf50(4.3, 1.6) - 3.11) < 0.01)
    check("RO4350B: Wf 50 ohm untuk h 1,524 adalah 3,336", abs(sb.wf50(3.66, 1.524) - 3.336) < 0.001)
    check("impedansi Wf 3,336 pada h 1,524 sekitar 50 ohm", abs(sb.z0_line(3.66, 1.524, 3.336) - 50.0) < 0.6, str(sb.z0_line(3.66, 1.524, 3.336)))
    check("impedansi hs 1,6 dan Wf 3,11 pada er 3,66 sekitar 54 ohm (yang terbaca di CST)", abs(sb.z0_line(3.66, 1.6, 3.11) - 54.0) < 0.6, str(sb.z0_line(3.66, 1.6, 3.11)))
    ro, fr4, demo = (load_design_module(n) for n in ("uslot_dgs_ro4350b", "uslot_dgs_fr4", "_demo_analytic"))
    check("baseline turunan RO4350B = hs 1,524 dan Wf 3,336", sb.default_extra_base(ro.SUBSTRATE) == {"hs": 1.524, "Wf": 3.336}, str(sb.default_extra_base(ro.SUBSTRATE)))
    check("baseline turunan FR-4 mendekati EXTRA_BASE yang ditulis (hs 1,6; Wf 3,11)", abs(sb.default_extra_base(fr4.SUBSTRATE)["Wf"] - fr4.EXTRA_BASE["Wf"]) < 0.005)
    check("SUBSTRATE tidak lengkap atau kosong memberi None", sb.default_extra_base({"er": 3.0}) is None and sb.default_extra_base(None) is None)
    print("pemeriksaan nilai")
    w = sb.check_values(ro.SUBSTRATE, 1.6, 3.11)
    check("nilai FR-4 pada RO4350B: tiga peringatan (hs, Wf, impedansi 54 ohm)", len(w) == 3 and "hs di project = 1.6" in w[0] and "3.336" in w[1] and "54.0" in w[2], str(w))
    check("nilai benar (1,524 dan 3,336): tanpa peringatan", sb.check_values(ro.SUBSTRATE, 1.524, 3.336) == [])
    check("selisih Wf 0,04 mm masih dalam toleransi; selisih hs 0,02 mm tidak", sb.check_values(ro.SUBSTRATE, 1.524, 3.376) == [] and len(sb.check_values(ro.SUBSTRATE, 1.544, 3.336)) >= 2)
    check("tanpa data substrat: tanpa peringatan", sb.check_values({}, 1.0, 1.0) == [])

    print("config.configure (baseline setelah run yang menyetel hs dan Wf)")
    from cstopt.cst import config as cfg
    for name, want in (("uslot_dgs_ro4350b", {"hs": 1.524, "Wf": 3.336}), ("uslot_dgs_fr4", {"hs": 1.6, "Wf": 3.11})):
        fake = types.SimpleNamespace(BASE={}, BASE_EXTRA={"hs": 1.6, "Wf": 3.11}, check_geometry=None)
        cfg.configure(name, fake)
        check(f"{name}: BASE_EXTRA = {want}", fake.BASE_EXTRA == want, str(fake.BASE_EXTRA))
    fake = types.SimpleNamespace(BASE={}, BASE_EXTRA={"hs": 9.9, "Wf": 9.9}, check_geometry=None)
    cfg.configure("_demo_analytic", fake)
    check("_demo_analytic tanpa EXTRA_BASE: diturunkan dari SUBSTRATE (bukan nilai lama)", fake.BASE_EXTRA["hs"] == 1.6 and abs(fake.BASE_EXTRA["Wf"] - 3.112) < 0.001, str(fake.BASE_EXTRA))

    print("batch.check_substrate")
    from cstopt.cst import batch

    def run(m3d, design):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            batch.check_substrate(m3d, design)
        return buf.getvalue()
    o = run(FakeM3D(1.6, 3.11), ro)
    check("project berisi nilai FR-4 pada desain RO4350B: nilai dicetak dan tiga PERINGATAN", "hs = 1.6 mm, Wf = 3.11 mm" in o and o.count("[PERINGATAN]") == 3, o)
    o = run(FakeM3D(1.524, 3.336), ro)
    check("project berisi nilai yang benar: tanpa PERINGATAN", "[PERINGATAN]" not in o and "hs = 1.524" in o, o)
    o = run(FakeM3D(0, 0, fail=True), ro)
    check("hs atau Wf tidak terbaca: info saja, tanpa galat", "[info]" in o and "dilewati" in o, o)
    check("desain tanpa SUBSTRATE: tidak mencetak apa pun", run(FakeM3D(1, 1), types.SimpleNamespace()) == "")
    print("\n" + ("SEMUA LULUS" if not FAILS else f"{len(FAILS)} pemeriksaan GAGAL: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
