"""
Konfigurasi sisi CST dari file desain (P1-1 tahap 1), agar desain baru tidak perlu mengubah kode inti.

Atribut opsional di file desain (bila tidak ada, nilai lama di export.py dan batch.py tetap dipakai: kompatibel mundur):
  PARAM_NAMES        daftar nama parameter geometri (persis sama dengan parameter di macro CST)
  BASE_PARAMS        dict baseline parameter di model CST (dulu BASE di batch.py), dipakai untuk mengembalikan model setelah batch
  EXTRA_BASE         dict parameter ekstra yang boleh muncul di CSV beserta baselinenya (dulu BASE_EXTRA), mis. {"hs": 1.6, "Wf": 3.11}
                     Bila tidak ada tetapi SUBSTRATE (er dan h) ada, baseline diturunkan darinya: hs = h dan Wf = lebar 50 ohm (cstopt/substrate.py),
                     BUKAN nilai bawaan FR-4 (itu dulu membuat project RO4350B berubah menjadi hs 1,6 dan Wf 3,11 setelah run yang menyetel hs dan Wf).
  CST                dict opsional: band_ghz, rl_limit_db, f0_ghz, monitors_ghz (mulai, akhir, langkah), bw_min_mhz, gain_min_dbi
  geometry_problems  fungsi(p) -> daftar masalah; dipakai menggantikan check_geometry lama di batch.py
Catatan: MON_* (monitors_ghz) harus SAMA dengan FF_F_START/STOP/STEP di macro CST.
"""
import ntpath
import os

from cstopt import paths
from cstopt import substrate
from cstopt.cst import export as ed
from cstopt.loader import load_design_module

CST_KEYS = {"band_ghz": "BAND_GHZ", "rl_limit_db": "RL_LIMIT_DB", "f0_ghz": "F0_GHZ",
            "bw_min_mhz": "BW_MIN_MHZ", "gain_min_dbi": "GAIN_MIN_DBI"}


def design_for_run(run_name, exact=False):
    """Nama file desain untuk sebuah nama run: RUN_NAME sama persis, atau (bila exact False) awalan terpanjang
    yang diikuti garis bawah (mis. MicrostripAntena_RO4350B_tol mengikuti desain RO4350B). None bila tidak ada."""
    if not run_name:
        return None
    best, best_len = None, -1
    for name in paths.list_designs():
        try:
            rn = getattr(load_design_module(name), "RUN_NAME", None)
        except Exception:
            continue
        if not rn:
            continue
        if rn == run_name:
            return name
        if not exact and run_name.startswith(rn + "_") and len(rn) > best_len:
            best, best_len = name, len(rn)
    return best


def configure(design=None, batch_module=None):
    """Isi variabel modul export (dan batch bila diberikan) dari file desain. design: None (bawaan), nama, atau modul.
    Dipanggil satu kali setelah parse_args dan sebelum --extra-params diproses. Mengembalikan modul desain."""
    m = design if (design is not None and not isinstance(design, str)) else load_design_module(design)
    names = getattr(m, "PARAM_NAMES", None)
    if names and list(names) != list(ed.PARAM_NAMES):
        tail = ed.FIELDS[ed.FIELDS.index(ed.PARAM_NAMES[-1]) + 1:]
        ed.PARAM_NAMES[:] = list(names)                                   # di tempat: modul lain memegang referensi list yang sama
        ed.FIELDS[:] = ["sample_id", "run_id", "timestamp"] + ed.PARAM_NAMES + tail
    cst = getattr(m, "CST", None) or {}
    for key, attr in CST_KEYS.items():
        if key in cst:
            setattr(ed, attr, tuple(cst[key]) if key == "band_ghz" else float(cst[key]))
    if "monitors_ghz" in cst:
        ed.MON_START, ed.MON_STOP, ed.MON_STEP = (float(x) for x in cst["monitors_ghz"])
    if cst:
        ed.MONITORS_GHZ = ed._build_monitors()                            # dihitung saat impor, bangun ulang
    if batch_module is not None:
        if getattr(m, "BASE_PARAMS", None):
            batch_module.BASE.clear()
            batch_module.BASE.update(m.BASE_PARAMS)
        eb = getattr(m, "EXTRA_BASE", None) or substrate.default_extra_base(getattr(m, "SUBSTRATE", None))
        if eb:
            batch_module.BASE_EXTRA.clear()
            batch_module.BASE_EXTRA.update(eb)
        if callable(getattr(m, "geometry_problems", None)):
            batch_module.check_geometry = m.geometry_problems            # satu sumber aturan, tidak ada duplikat
    return m


def warn_project_mismatch(project, design_module, explicit_design=None):
    """Peringatan bila nama project CST berbeda dari RUN_NAME desain yang dipakai (sumber kekacauan data)."""
    name = os.path.splitext(ntpath.basename(str(project)))[0]      # ntpath: path Windows dan Linux sama sama terpecah
    run = getattr(design_module, "RUN_NAME", None)
    if not run or name == run:
        return None
    other = design_for_run(name, exact=True)
    msg = f"[peringatan] project CST '{name}' berbeda dari RUN_NAME desain yang dipakai ('{run}')."
    if other and not explicit_design:
        msg += f" Project ini cocok dengan desain '{other}': ulangi dengan --design {other}."
    else:
        msg += " Pastikan desain (--design) dan --run-name sesuai agar hasil tidak tercampur."
    print(msg)
    return msg
