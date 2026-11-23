"""Uji tools/package_dataset.py (tanpa CST): isi paket, checksum, --with-ff, dan laporan per desain. Hanya membaca data/ (menulis ke folder sementara);
membuat lalu menghapus data/_report_testpkg untuk menguji penyertaan laporan per desain.

  py tools\\test_package_dataset.py
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cstopt import paths  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print((" [OK]    " if cond else " [GAGAL] ") + name + (f"  {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)


def pack(out, *flags):
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "package_dataset.py"), "--version", "vTEST", "--out-dir", out, *flags],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    return r


def main():
    runs = [d for d in os.listdir(paths.DATA_DIR) if not d.startswith("_") and os.path.exists(os.path.join(paths.DATA_DIR, d, "batch_lhs.csv"))]
    if not runs:
        print("  (data/ tidak ada: uji dilewati)")
        return 0
    rep = os.path.join(paths.DATA_DIR, "_report_testpkg")
    tmp = tempfile.mkdtemp(prefix="pkg_")
    try:
        os.makedirs(rep, exist_ok=True)
        open(os.path.join(rep, "report.md"), "w").write("# uji\n")
        open(os.path.join(rep, "x.png"), "wb").write(b"\x89PNG")
        open(os.path.join(rep, "catatan.tmp"), "w").write("bukan untuk paket")
        out1 = os.path.join(tmp, "a")
        r = pack(out1)
        check("paket dasar: kode 0", r.returncode == 0, (r.stdout + r.stderr)[-300:])
        d1 = os.path.join(out1, "vTEST")
        check("README_dataset.md dan CHECKSUMS.sha256 ada", os.path.exists(os.path.join(d1, "README_dataset.md")) and os.path.exists(os.path.join(d1, "CHECKSUMS.sha256")))
        check("tiap run punya batch_lhs.csv di paket", all(os.path.exists(os.path.join(d1, "data", x, "batch_lhs.csv")) for x in runs))
        check("laporan per desain ikut (report.md dan png), berkas .tmp tidak",
              os.path.exists(os.path.join(d1, "data", "_report_testpkg", "report.md")) and os.path.exists(os.path.join(d1, "data", "_report_testpkg", "x.png"))
              and not os.path.exists(os.path.join(d1, "data", "_report_testpkg", "catatan.tmp")))
        bad = []
        for line in open(os.path.join(d1, "CHECKSUMS.sha256"), encoding="utf-8"):
            h, rel = line.rstrip("\n").split("  ", 1)
            if hashlib.sha256(open(os.path.join(d1, rel), "rb").read()).hexdigest() != h:
                bad.append(rel)
        check("semua checksum cocok", not bad, str(bad[:3]))
        check("tanpa --with-ff tidak ada ff/ dan eff/", not any(os.path.isdir(os.path.join(d1, "data", x, "ff")) for x in runs))
        with zipfile.ZipFile(out1 + "/vTEST.zip") as z:
            names = z.namelist()
        check("zip berawalan vTEST/ dan memuat laporan per desain", all(n.startswith("vTEST/") for n in names) and "vTEST/data/_report_testpkg/report.md" in names)
        txt = open(os.path.join(d1, "README_dataset.md"), encoding="utf-8").read()
        check("README menjelaskan ff (directivity, bukan gain) dan _report", "DIRECTIVITY" in txt and "_report_" in txt)
        have_ff = [x for x in runs if os.path.isdir(os.path.join(paths.DATA_DIR, x, "ff"))]
        out2 = os.path.join(tmp, "b")
        r2 = pack(out2, "--with-ff")
        check("--with-ff: kode 0", r2.returncode == 0, (r2.stdout + r2.stderr)[-300:])
        d2 = os.path.join(out2, "vTEST")
        check("--with-ff menyalin ff/ tiap run yang punya", all(os.path.isdir(os.path.join(d2, "data", x, "ff")) for x in have_ff) if have_ff else True)
    finally:
        shutil.rmtree(rep, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + ("SEMUA LULUS" if not FAILS else f"{len(FAILS)} pemeriksaan GAGAL: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
