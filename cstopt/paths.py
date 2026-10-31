"""Satu-satunya tempat yang tahu letak folder proyek.

Semua modul memakai fungsi di sini, bukan menghitung path sendiri, sehingga folder
repo boleh dipindah atau dipakai di perangkat lain tanpa mengubah kode.

Tata letak data per RUN_NAME (nama project CST):
  data/<RUN_NAME>/batch_lhs.csv, curves/, eff/, ff/      dataset hasil simulasi
  data/<RUN_NAME>/samples/                               lhs_samples.csv, bo_candidates.csv, archive/
  data/<RUN_NAME>/models/                                gpr_models.joblib, gpr_metrics.csv, gpr_sensitivity.csv
  data/<RUN_NAME>/figures/                               gambar PNG (parity, konvergensi, backtest)
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESIGNS_DIR = os.path.join(ROOT, "designs")
DATA_DIR = os.path.join(ROOT, "data")
MACROS_DIR = os.path.join(ROOT, "macros")
CST_PROJECTS_DIR = os.path.join(ROOT, "cst_projects")
DEFAULT_DESIGN = "uslot_dgs_fr4"


def run_dir(run_name):
    return os.path.join(DATA_DIR, run_name)


def samples_dir(run_name):
    return os.path.join(run_dir(run_name), "samples")


def models_dir(run_name):
    return os.path.join(run_dir(run_name), "models")


def figures_dir(run_name):
    return os.path.join(run_dir(run_name), "figures")


def list_designs():
    """Nama file desain di folder designs/ (tanpa .py)."""
    if not os.path.isdir(DESIGNS_DIR):
        return []
    return sorted(f[:-3] for f in os.listdir(DESIGNS_DIR)
                  if f.endswith(".py") and not f.startswith("_"))
