"""
Pintu masuk tunggal proyek optimasi antena (CST + GPR + Bayesian Optimization).

  py main.py                 buka GUI (sama dengan: py main.py gui)
  py main.py <perintah> ...  jalankan satu tahap dari baris perintah

Perintah:
  status     ringkasan kondisi proyek (sampel, tahap BO, terbaik, berkas)
  lhs        bangkitkan sampel LHS maximin
  run        jalankan batch simulasi CST            (butuh Windows + CST + requirements-cst.txt)
  export     ekstraksi hasil CST (CLI lama)         (butuh CST)
  qc         pemeriksaan kualitas dataset
  curves     verifikasi kurva S11 vs CSV
  train      latih dan evaluasi surrogate GPR
  suggest    usulkan kandidat BO berikutnya (--report: kurva konvergensi)
  backtest   uji BO vs pencarian acak pada data yang ada

Setiap perintah punya opsi sendiri:  py main.py suggest -h
"""
import importlib
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

COMMANDS = {
    "gui": "cstopt.gui.app",
    "status": "cstopt.status",
    "lhs": "cstopt.sampling.lhs",
    "run": "cstopt.cst.batch",
    "export": "cstopt.cst.export",
    "qc": "cstopt.qc.dataset",
    "curves": "cstopt.qc.curves",
    "train": "cstopt.ml.train",
    "suggest": "cstopt.ml.suggest",
    "backtest": "cstopt.ml.backtest",
}
CST_ONLY = {"run", "export"}
CST_MODULES = {"cst", "win32api", "win32gui", "win32con", "pythoncom", "pywinauto", "comtypes"}


def run(argv):
    if not argv:
        argv = ["gui"]
    cmd = argv[0]
    if cmd in ("-h", "--help", "help") or cmd not in COMMANDS:
        print(__doc__)
        return 0 if cmd in ("-h", "--help", "help") else 2
    try:
        mod = importlib.import_module(COMMANDS[cmd])
    except ModuleNotFoundError as e:
        if cmd in CST_ONLY or (e.name or "").split(".")[0] in CST_MODULES:
            print(f"Perintah '{cmd}' butuh CST Studio Suite dan paket Windows (modul '{e.name}' tidak ada).\n"
                  "Pasang dengan:  pip install -r requirements-cst.txt   (hanya Windows dengan CST).\n"
                  "Perintah lain (lhs, qc, train, suggest, backtest, status) tidak membutuhkannya.")
            return 2
        raise
    sys.argv = [f"main.py {cmd}"] + argv[1:]
    try:
        rc = mod.main()
    except FileNotFoundError as e:                       # mis. dataset/sampel belum dibuat
        print(f"[error] {e}\nPeriksa tahap sebelumnya (lihat:  py main.py status).")
        return 1
    return rc if isinstance(rc, int) else 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
