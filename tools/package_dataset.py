"""
Kemas dataset untuk rilis (mis. unggah ke Zenodo untuk DOI). Tidak butuh CST.

  py tools/package_dataset.py --version v1.0-fr4-ro4350b
  py tools/package_dataset.py --version v1.0-fr4-ro4350b --with-curves
  py tools/package_dataset.py --version v1.0-fr4-ro4350b --with-curves --with-ff

Isi: batch_lhs.csv tiap run di data/ (kecuali folder yang diawali garis bawah), hasil di data/_compare (pareto_front.csv, ringkasan toleransi, report.md) bila ada, laporan per desain di data/_report_* (report.md, gambar, csv) bila ada,
README_dataset.md (definisi kolom dan target, substrat per run), dan CHECKSUMS.sha256. Kurva S11 (folder curves/) hanya ikut dengan --with-curves, dan data pola radiasi serta efisiensi (folder ff/ dan eff/, dibutuhkan untuk mereproduksi bagian 9 laporan) hanya dengan --with-ff, karena besar.
Keluaran: release/<version>/ dan release/<version>.zip. Lisensi sengaja dibiarkan kosong untuk diisi penulis sebelum diunggah.
"""
import argparse
import datetime
import hashlib
import os
import shutil
import sys
import zipfile

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cstopt import paths                       # noqa: E402
from cstopt.loader import load_design_module   # noqa: E402

COLS = {
    "sample_id": "nomor sampel dalam run",
    "fr_ghz": "frekuensi resonansi (GHz): frekuensi minimum S11",
    "rl_min_db": "nilai minimum S11 (dB)",
    "bw_mhz": "lebar pita S11 <= -10 dB di sekitar minimum global (MHz); 0 bila RL minimum > -10 dB",
    "band_cover_pct": "persentase frekuensi di 3,3 sampai 3,7 GHz dengan S11 <= -10 dB",
    "s11_at_f0_db": "S11 di 3,5 GHz (dB)",
    "gain_fr_ieee_dbi": "gain IEEE di frekuensi resonansi (D + 10 log eta), dBi",
    "eta_rad_fr": "efisiensi radiasi di frekuensi resonansi",
    "d_peak_fr_dbi": "directivity puncak di frekuensi resonansi (dBi)",
    "hs": "tebal substrat (mm), bila kolom ada",
    "Wf": "lebar jalur catu (mm), bila kolom ada",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def substrate_of(run):
    for name in paths.list_designs():
        try:
            m = load_design_module(name)
        except Exception:
            continue
        if getattr(m, "RUN_NAME", None) == run:
            return name, getattr(m, "SUBSTRATE", None), list(getattr(m, "PARAM_NAMES", []))
    return None, None, []


def main():
    ap = argparse.ArgumentParser(description="Kemas dataset untuk rilis")
    ap.add_argument("--version", required=True, help="mis. v1.0-fr4-ro4350b")
    ap.add_argument("--with-curves", action="store_true", help="ikut sertakan folder curves/ tiap run")
    ap.add_argument("--with-ff", action="store_true", help="ikut sertakan folder ff/ (directivity irisan bidang utama) dan eff/ (efisiensi) tiap run")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "release"))
    a = ap.parse_args()

    dest = os.path.join(a.out_dir, a.version)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    items, readme_runs = [], []
    for run in sorted(os.listdir(paths.DATA_DIR)):
        rd = os.path.join(paths.DATA_DIR, run)
        if run.startswith("_") or not os.path.isdir(rd):
            continue
        src = os.path.join(rd, "batch_lhs.csv")
        if not os.path.exists(src):
            continue
        out = os.path.join(dest, "data", run)
        os.makedirs(out, exist_ok=True)
        shutil.copyfile(src, os.path.join(out, "batch_lhs.csv"))
        items.append(os.path.join("data", run, "batch_lhs.csv"))
        for sub in ("samples",):
            sd = os.path.join(rd, sub)
            if os.path.isdir(sd):
                shutil.copytree(sd, os.path.join(out, sub))
                items += [os.path.join("data", run, sub, f) for f in sorted(os.listdir(sd))]
        if a.with_curves and os.path.isdir(os.path.join(rd, "curves")):
            shutil.copytree(os.path.join(rd, "curves"), os.path.join(out, "curves"))
            items += [os.path.join("data", run, "curves", f) for f in sorted(os.listdir(os.path.join(rd, "curves")))]
        if a.with_ff:
            for sub_dir in ("ff", "eff"):
                sd = os.path.join(rd, sub_dir)
                if os.path.isdir(sd):
                    shutil.copytree(sd, os.path.join(out, sub_dir))
        df = pd.read_csv(src)
        dname, sub, params = substrate_of(run)
        readme_runs.append((run, len(df), dname, sub, [c for c in params if c in df.columns]))
    cmp_dir = os.path.join(paths.DATA_DIR, "_compare")
    if os.path.isdir(cmp_dir):
        keep = [f for f in sorted(os.listdir(cmp_dir)) if f in ("pareto_front.csv", "report.md") or (f.startswith("tolerance_") and f.endswith((".csv", ".md")))]
        if keep:
            os.makedirs(os.path.join(dest, "data", "_compare"), exist_ok=True)
        for f in keep:
            shutil.copyfile(os.path.join(cmp_dir, f), os.path.join(dest, "data", "_compare", f))
            items.append(os.path.join("data", "_compare", f))
    for d in sorted(os.listdir(paths.DATA_DIR)):          # laporan per desain (py main.py report --runs RUN --out-dir data/_report_RUN)
        rp = os.path.join(paths.DATA_DIR, d)
        if d.startswith("_report_") and os.path.isdir(rp):
            keep = [f for f in sorted(os.listdir(rp)) if f.endswith((".md", ".png", ".csv"))]
            if keep:
                os.makedirs(os.path.join(dest, "data", d), exist_ok=True)
            for f in keep:
                shutil.copyfile(os.path.join(rp, f), os.path.join(dest, "data", d, f))
    if not readme_runs:
        raise SystemExit("Tidak ada run dengan batch_lhs.csv di data/.")

    md = [f"# Dataset simulasi antena mikrostrip U-slot dengan DGS dumbbell ({a.version})", "",
          f"Dibuat: {datetime.date.today().isoformat()}. Seluruh data berasal dari simulasi CST (bukan pengukuran).",
          "Lisensi: belum ditentukan (isi sebelum diunggah, mis. CC BY 4.0).", "", "## Run", "",
          "| run | baris | desain | substrat | parameter geometri |", "|---|---|---|---|---|"]
    for run, n, dname, sub, params in readme_runs:
        st = f"{sub.get('material', '')}: er {sub.get('er')}, tan delta {sub.get('tand')}, h {sub.get('h')} mm (nilai di file desain)" if sub else "tidak diketahui"
        md.append(f"| {run} | {n} | {dname or 'tidak ada'} | {st} | {', '.join(params)} |")
    md += ["", "## Kolom utama (satuan mm bila panjang)", "", "| kolom | arti |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in COLS.items()]
    md += ["", "Kolom lain (mis. eta_tot, vswr, gain_real_dbi, feasible_all) mengikuti `cstopt/cst/export.py` di repositori kode.",
           "Run berakhiran `_tol` adalah skenario toleransi fabrikasi (sample_id = ID desain * 100 + k; berkas `*_meta.csv` di `samples/` memberi plan dan skenarionya),",
           "`_fine` adalah simulasi ulang dengan mesh lebih halus, dan `_pilot_h` adalah pilot ketebalan substrat.",
           "Folder `data/_report_<run>/` (bila ada) berisi laporan otomatis per desain (`report.md` dan gambarnya); `data/_compare/` berisi versi gabungan dan tabel toleransi.",
           "Berkas `ff/` (bila disertakan) berisi DIRECTIVITY (dBi), bukan gain, untuk irisan phi = 0 dan phi = 90 pada frekuensi monitor; satu berkas adalah irisan penuh:",
           "Theta 0 sampai 180 pada Phi irisan lalu Theta 179 sampai 1 pada Phi + 180. Berkas `eff/` berisi efisiensi radiasi dan total terhadap frekuensi.", "",
           "## Berkas dan checksum", "", "Lihat `CHECKSUMS.sha256` (SHA256 tiap berkas)."]
    with open(os.path.join(dest, "README_dataset.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    items = []
    for root, _, files in os.walk(dest):          # semua berkas yang benar benar tersalin (subfolder samples/archive ikut)
        for fn in files:
            rel = os.path.relpath(os.path.join(root, fn), dest)
            if rel != "CHECKSUMS.sha256":
                items.append(rel)
    with open(os.path.join(dest, "CHECKSUMS.sha256"), "w", encoding="utf-8") as f:
        for rel in sorted(items):
            f.write(f"{sha256(os.path.join(dest, rel))}  {rel.replace(os.sep, '/')}\n")
    zp = dest + ".zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(items + ["CHECKSUMS.sha256"]):
            z.write(os.path.join(dest, rel), arcname=os.path.join(a.version, rel))
    print(f"{len(items)} berkas dikemas.\nFolder: {dest}\nZip   : {zp} ({os.path.getsize(zp) / 1024:.0f} KB)")
    print("Langkah berikutnya: isi lisensi di README_dataset.md, lalu unggah ke Zenodo (opsional) dan catat DOI di README repo.")


if __name__ == "__main__":
    main()
