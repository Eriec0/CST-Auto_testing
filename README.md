# Optimasi antena mikrostrip dengan CST, GPR, dan Bayesian Optimization

Alur otomatis untuk mengoptimasi antena mikrostrip U-Slot dengan DGS Dumbbell (target 5G Sub-6 GHz, 3,3 sampai 3,7 GHz):
sampel awal Latin Hypercube, simulasi batch di CST Studio Suite, surrogate Gaussian Process Regression, lalu Constrained
Bayesian Optimization (Expected Improvement x Probability of Feasibility).

Semua tahap bisa dijalankan dari satu GUI atau dari baris perintah dengan `py main.py`.
Bagian ML tidak membutuhkan CST, sehingga bisa dipakai di perangkat lain. Hasil terkini ada di [docs/progres_fr4.md](docs/progres_fr4.md).

## Alur kerja

```
 1 lhs      sampel awal (LHS maximin)                data/<RUN>/samples/lhs_samples.csv
 2 run      simulasi batch di CST        (butuh CST)  data/<RUN>/batch_lhs.csv + curves/ eff/ ff/
 3 qc       pemeriksaan kualitas data
 4 train    latih dan evaluasi model GPR             data/<RUN>/models/ dan figures/
 5 suggest  usulkan kandidat BO berikutnya           data/<RUN>/samples/bo_candidates.csv
            -> kembali ke langkah 2 dengan --samples bo_candidates.csv, ulangi 2 sampai 5
 6 suggest --report / backtest   kurva konvergensi dan uji BO vs acak
```

BO berjalan dalam tahap (`STAGES` di file desain) dan berpindah otomatis dari data: Tahap 1 meminimalkan `rl_band_min_db`
sampai ada sampel yang memenuhi constraint Tahap 2, lalu Tahap 2 memaksimalkan `bw_mhz`.

## Struktur repo

```
main.py                  pintu masuk: GUI atau perintah CLI
requirements.txt         paket ML dan GUI (portabel)
requirements-cst.txt     tambahan khusus Windows dengan CST
designs/                 SATU FILE PER DESAIN atau substrat (parameter, rentang, constraint, lokasi data)
  uslot_dgs_fr4.py
macros/                  macro VBA untuk membangun model di CST (setup terpisah, dijalankan manual di CST)
cst_projects/            file project .cst
cstopt/                  kode
  paths.py loader.py status.py
  sampling/lhs.py        LHS maximin
  cst/                   batch.py, export.py, farfield.py, dialog_watcher.py   (butuh CST)
  ml/                    core.py, train.py, suggest.py, backtest.py
  qc/                    dataset.py, curves.py
  gui/                   app.py, runner.py, commands.py
data/<RUN>/              dataset dan hasil, satu folder per project CST
tools/                   migrate_layout.py, smoke_test.py, compare_csv.py
docs/                    catatan hasil
```

## Instalasi

Python 3.10 atau lebih baru. tkinter sudah ikut pada Python untuk Windows.

```
python -m venv cst_env
cst_env\Scripts\activate
pip install -r requirements.txt          # bagian ML dan GUI (OS apa pun)
pip install -r requirements-cst.txt      # hanya bila akan menjalankan CST (Windows + CST Studio Suite)
py tools\smoke_test.py                   # memeriksa instalasi
```

Setup CST (sekali per project): buka CST, jalankan macro dari `macros/` untuk membangun model, simpan sebagai
`cst_projects/<RUN_NAME>.cst`. Nama project harus sama dengan `RUN_NAME` di file desain.

## Pemakaian

GUI: `py main.py`. Setiap tombol menjalankan perintah CLI yang sama dan menampilkan lognya.

| Perintah | Fungsi |
|---|---|
| `py main.py status` | ringkasan: sampel, tahap BO, terbaik, peringatan batas, berkas |
| `py main.py lhs -n 80` | bangkitkan sampel LHS |
| `py main.py run --check-samples` | validasi sampel (butuh paket CST terpasang) |
| `py main.py run --auto-yes` | batch simulasi CST dari `lhs_samples.csv` |
| `py main.py run --samples data/<RUN>/samples/bo_candidates.csv --auto-yes` | simulasikan kandidat BO |
| `py main.py qc` / `py main.py curves` | QC dataset / verifikasi kurva S11 |
| `py main.py train` | latih dan evaluasi GPR |
| `py main.py suggest -q 5` | usulkan 5 kandidat berikutnya |
| `py main.py suggest --report` | kurva konvergensi |
| `py main.py backtest` | uji BO vs acak pada data yang ada |

Opsi tiap perintah: `py main.py <perintah> -h`. Opsi `--design nama` memilih file di `designs/` (bawaan: `uslot_dgs_fr4`).

Contoh satu putaran BO: `suggest -q 5`, lalu `run --samples data/MicrostripAntena/samples/bo_candidates.csv --auto-yes`,
lalu ulangi. `suggest` memberi peringatan bila desain terbaik menempel di batas parameter (tanda `BOUNDS` perlu dilebarkan).

## Data

```
data/<RUN>/
  batch_lhs.csv          satu baris per sampel (parameter dan hasil)
  curves/ eff/ ff/       kurva S11, efisiensi, dan farfield mentah per sampel
  samples/               lhs_samples.csv, bo_candidates.csv (+ report), archive/
  models/                gpr_models.joblib, gpr_metrics.csv, gpr_sensitivity.csv
  figures/               gpr_parity.png, bo_convergence.png, bo_backtest.png
```

Kolom `batch_lhs.csv`: `sample_id`; 11 parameter (`Lp Wp LU WU gU PU LI LD WD gD PD`); `fr_ghz` (frekuensi resonansi),
`rl_min_db` (S11 minimum), `bw_mhz` (lebar pita S11 <= -10 dB), `s11_at_f0_db`; `d_peak_dbi`, `d_peak_fr_dbi` (directivity),
`eta_rad_fr` (efisiensi radiasi), `gain_fr_ieee_dbi` (gain IEEE = D + 10 log10 eta); serta `feasible_all`, `feasible_wo_gain`.
Fitur turunan (`rl_band_*`, `dip_dist_ghz`, `dip_nearest_db`) dihitung dari `curves/` saat data dimuat.

## Mengganti desain

Salin `designs/uslot_dgs_fr4.py` ke `designs/nama_baru.py`, ubah `RUN_NAME`, parameter, `BOUNDS`, aturan geometri,
`TARGETS`, dan `STAGES`, lalu pilih `nama_baru` di GUI atau dengan `--design nama_baru`. Bagian `lhs`, `qc`, `train`,
`suggest`, dan `backtest` membaca semuanya dari file desain tersebut.

Keterbatasan saat ini: modul CST (`cst/batch.py`, `cst/export.py`) masih memuat beberapa konstanta khusus desain ini
(baseline parameter, frekuensi monitor farfield, aturan geometri), dan fitur kurva S11 di `ml/core.py` khusus antena.
Penyederhanaan untuk desain atau substrat lain direncanakan terpisah.

## Masalah yang sering muncul

| Gejala | Penyebab dan solusi |
|---|---|
| `Perintah 'run' butuh CST ...` | paket CST belum terpasang: `pip install -r requirements-cst.txt` (hanya Windows dengan CST). |
| `Desain '...' tidak ditemukan` | nama pada `--design` harus sama dengan nama file di `designs/` tanpa `.py`. |
| `[error] ... FileNotFoundError` | dataset atau sampel belum dibuat. Lihat `py main.py status`, mulai dari `lhs` lalu `run`. |
| Dialog "Recalculate"/"Abort" muncul di CST | gunakan `--auto-yes`; dialog dijawab oleh `cst/dialog_watcher.py`. |
| `run_solver melaporkan error (Terminated on unknown error)` | umumnya tidak berbahaya bila hasil tetap terbentuk; skrip melanjutkannya otomatis. |
| `suggest` lama | kurangi `--restarts` (mis. 3) atau `--pool`. |
| Peringatan parameter menempel batas | lebarkan `BOUNDS` di file desain; sampel lama tetap valid. |
