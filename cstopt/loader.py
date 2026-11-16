"""Memuat file desain dari folder designs/ (satu file per desain atau substrat)."""
import importlib
import sys

from cstopt import paths


def load_design_module(name=None):
    """name: 'uslot_dgs_fr4', 'uslot_dgs_fr4.py', atau 'designs.uslot_dgs_fr4'. None = desain bawaan."""
    name = name or paths.DEFAULT_DESIGN
    if name.endswith(".py"):
        name = name[:-3]
    if name.startswith("designs."):
        name = name[len("designs."):]
    if paths.ROOT not in sys.path:
        sys.path.insert(0, paths.ROOT)
    try:
        return importlib.import_module(f"designs.{name}")
    except ModuleNotFoundError as e:
        if e.name == f"designs.{name}":
            raise SystemExit(f"Desain '{name}' tidak ditemukan di {paths.DESIGNS_DIR}. "
                             f"Tersedia: {', '.join(paths.list_designs()) or '(kosong)'}")
        raise


def default_run_name(design=None):
    """RUN_NAME (nama project CST / folder data) dari desain yang dipilih."""
    return load_design_module(design).RUN_NAME


def module_for_run(run_name=None, design=None):
    """Modul desain untuk qc dan alat lain yang tidak boleh mengimpor paket CST. design (nama) menang; bila tidak ada, cari desain
    dengan RUN_NAME sama persis atau awalan terpanjang yang diikuti garis bawah (mis. <run>_tol); bila tak ada, desain bawaan."""
    if design:
        return load_design_module(design)
    best, best_len = None, -1
    for name in paths.list_designs():
        try:
            rn = getattr(load_design_module(name), "RUN_NAME", None)
        except Exception:
            continue
        if rn and run_name and (run_name == rn or run_name.startswith(rn + "_")) and len(rn) > best_len:
            best, best_len = name, len(rn)
    return load_design_module(best) if best else load_design_module(None)
