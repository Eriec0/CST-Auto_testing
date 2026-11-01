"""
Migrasi tata letak repo lama -> baru. Jalankan SETELAH folder baru (main.py, cstopt/, designs/, tools/) disalin
ke root repo, dengan CST dan Excel ditutup.

  py tools/migrate_layout.py            simulasi saja: tampilkan apa yang akan dipindah (tidak mengubah apa pun)
  py tools/migrate_layout.py --apply    jalankan pemindahan (memakai `git mv` bila berkas dilacak git)

Yang dilakukan:
  export/<RUN>/            -> data/<RUN>/   (gpr_* ke models/, *.png ke figures/)
  export/*.csv             -> data/<RUN>/samples/   (lhs_samples, bo_candidates, seed, sweep, dll.)
  export/bo_archive/*      -> data/<RUN>/samples/archive/
  *.bas                    -> macros/   (versi lama ke macros/old/)
  *.cst                    -> cst_projects/
  skrip .py lama di root   -> dihapus (sudah digantikan oleh cstopt/ dan designs/)
Tidak pernah menimpa berkas yang sudah ada; yang bentrok dilewati dan dilaporkan.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

OLD_SCRIPTS = ["batch_trials.py", "bo_backtest.py", "bo_suggest.py", "check_curves.py", "design_uslot_dgs.py",
               "dialog_watcher.py", "export_dataset.py", "farfield_utils.py", "lhs_maximin.py", "ml_core.py",
               "qc_dataset.py", "train_gpr.py"]
BAS_RENAME = {"antena_uslot_dgs_dumbbell4.bas": "macros/uslot_dgs_dumbbell_v4.bas",
              "antena_uslot_dgs_dumbbell3.bas": "macros/old/uslot_dgs_dumbbell_v3.bas"}


class Mover:
    def __init__(self, root, apply):
        self.root, self.apply = root, apply
        self.git = shutil.which("git") is not None and os.path.isdir(os.path.join(root, ".git"))
        self.done = self.skipped = 0
        self.failed = []

    def p(self, rel):
        return os.path.join(self.root, *rel.split("/"))

    def tracked(self, rel):
        if not self.git:
            return False
        r = subprocess.run(["git", "-C", self.root, "ls-files", "--", rel], capture_output=True, text=True)
        return bool(r.stdout.strip())

    def move(self, src, dst):
        s, d = self.p(src), self.p(dst)
        if not os.path.exists(s):
            return
        if os.path.exists(d):
            print(f"  [lewati] {dst} sudah ada (tidak ditimpa); {src} dibiarkan")
            self.skipped += 1
            return
        print(f"  {src}  ->  {dst}")
        self.done += 1
        if not self.apply:
            return
        try:
            os.makedirs(os.path.dirname(d), exist_ok=True)
            if self.tracked(src):
                subprocess.run(["git", "-C", self.root, "mv", src, dst], check=True, capture_output=True, text=True)
            else:
                shutil.move(s, d)
        except (OSError, subprocess.CalledProcessError) as e:
            self.failed.append((src, str(getattr(e, "stderr", "") or e).strip()))
            print(f"  [GAGAL] {src}: {self.failed[-1][1]}  (tutup CST/Excel lalu jalankan ulang; aman diulang)")

    def remove(self, rel):
        s = self.p(rel)
        if not os.path.exists(s):
            return
        print(f"  hapus {rel}")
        self.done += 1
        if not self.apply:
            return
        try:
            if self.tracked(rel):
                subprocess.run(["git", "-C", self.root, "rm", "-q", "-f", rel], check=True, capture_output=True, text=True)
            else:
                os.remove(s)
        except (OSError, subprocess.CalledProcessError) as e:
            self.failed.append((rel, str(getattr(e, "stderr", "") or e).strip()))
            print(f"  [GAGAL] hapus {rel}: {self.failed[-1][1]}")


def default_run(root):
    try:
        t = open(os.path.join(root, "designs", "uslot_dgs_fr4.py"), encoding="utf-8").read()
        return re.search(r'RUN_NAME\s*=\s*"([^"]+)"', t).group(1)
    except Exception:
        return "MicrostripAntena"


def main():
    ap = argparse.ArgumentParser(description="Migrasi tata letak repo")
    ap.add_argument("--apply", action="store_true", help="jalankan (default: simulasi)")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    for need in ("main.py", "cstopt", "designs"):
        if not os.path.exists(os.path.join(root, need)):
            sys.exit(f"'{need}' tidak ada di {root}. Salin dulu isi paket baru ke root repo.")
    m = Mover(root, args.apply)
    run = default_run(root)
    print(("MODE SIMULASI (tidak ada yang diubah). Tambahkan --apply untuk menjalankan.\n" if not args.apply
           else "MENJALANKAN pemindahan.\n") + f"Root: {root} | RUN bawaan: {run} | git: {'ya' if m.git else 'tidak'}\n")

    exp = m.p("export")
    print("[1] Data run")
    if os.path.isdir(exp):
        for name in sorted(os.listdir(exp)):
            if os.path.isdir(os.path.join(exp, name)) and name != "bo_archive":
                m.move(f"export/{name}", f"data/{name}")
        print("[2] Berkas sampel dan kandidat")
        for name in sorted(os.listdir(exp)):
            if os.path.isfile(os.path.join(exp, name)) and name.lower().endswith(".csv"):
                m.move(f"export/{name}", f"data/{run}/samples/{name}")
        arc = os.path.join(exp, "bo_archive")
        if os.path.isdir(arc):
            for name in sorted(os.listdir(arc)):
                m.move(f"export/bo_archive/{name}", f"data/{run}/samples/archive/{name}")
    else:
        print("  (folder export/ tidak ada, dilewati)")

    print("[3] Model dan gambar di dalam data/<RUN>/")
    for rdir in ([m.p(f"data/{n}") for n in sorted(os.listdir(m.p("data")))] if os.path.isdir(m.p("data")) else []):
        for name in sorted(os.listdir(rdir)):
            rel = f"data/{os.path.basename(rdir)}/{name}"
            if os.path.isfile(os.path.join(rdir, name)):
                if name.startswith("gpr_") and name.endswith((".csv", ".joblib")):
                    m.move(rel, f"data/{os.path.basename(rdir)}/models/{name}")
                elif name.lower().endswith(".png"):
                    m.move(rel, f"data/{os.path.basename(rdir)}/figures/{name}")
    if not args.apply:
        print("  (pada simulasi, langkah 3 hanya melihat isi data/ yang sudah ada; jalankan --apply untuk hasil penuh)")

    print("[4] Macro dan project CST")
    for name in sorted(os.listdir(root)):
        if name in BAS_RENAME:
            m.move(name, BAS_RENAME[name])
        elif name.lower().endswith(".bas"):
            m.move(name, f"macros/old/{name}")
        elif name.lower().endswith(".cst") and os.path.isfile(os.path.join(root, name)):
            m.move(name, f"cst_projects/{name}")
            stem = name[:-4]                         # folder pendamping CST (hasil simulasi), biasanya tidak dilacak git
            if os.path.isdir(os.path.join(root, stem)):
                m.move(stem, f"cst_projects/{stem}")

    print("[5] Skrip lama di root (sudah digantikan)")
    for name in OLD_SCRIPTS:
        m.remove(name)
    others = [f for f in os.listdir(root) if f.endswith(".py") and f not in ("main.py",) and f not in OLD_SCRIPTS]
    for f in others:
        print(f"  [dibiarkan] {f} (tidak dikenal)")

    if args.apply:                       # buang export/ bila kosong
        for sub in ("export/bo_archive", "export"):
            try:
                os.rmdir(m.p(sub))
            except OSError:
                pass
        if os.path.isdir(m.p("export")):
            print("\n[catatan] export/ masih berisi berkas yang belum dipindah (periksa manual).")
    print(f"\nRingkasan: {m.done} tindakan, {m.skipped} dilewati, {len(m.failed)} gagal." + ("" if args.apply else "  (simulasi)"))
    if m.failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
