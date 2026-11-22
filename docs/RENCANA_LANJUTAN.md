# RENCANA LANJUTAN: panduan terpadu untuk percakapan Claude berikutnya

Dokumen ini menggabungkan seluruh diskusi sebelumnya (fitur, tampilan data, perbaikan metode ML, generalisasi desain, validasi, laporan)
menjadi satu rencana kerja berprioritas. Baca bersama `CLAUDE.md` (konteks dan aturan hemat token). Setiap tugas punya ID dan bisa dikerjakan
sendiri-sendiri; baca hanya bagian tugas yang sedang dikerjakan.

## Daftar isi

0. Cara memakai dokumen ini
1. Keadaan saat ini (ringkas)
2. Peta prioritas
3. Urutan dan jadwal sampai 1 Desember
4. Tugas P0 (wajib)
5. Tugas P1 (sangat disarankan)
6. Tugas P2 (bila ada waktu dan bukti)
7. Tugas yang sengaja tidak dikerjakan
8. Definisi target dan cara menyajikan data
9. Aturan pengujian dan kriteria lulus (berlaku untuk semua tugas)
10. Umpan balik jujur
11. Templat prompt untuk percakapan baru
12. Lampiran: angka acuan dan jebakan
13. Rencana penutup (20 November 2026): report per desain, laporan, rilis, uji CST, fitur lanjutan, demonstrasi

---

## 0. Cara memakai dokumen ini

1. Di percakapan baru, unggah `CLAUDE.md` dan dokumen ini. Jangan beri akses seluruh repo lewat konektor (penyebab utama boros token).
2. Unggah kode tanpa data. Dari root repo (PowerShell), satu perintah, daftar jalur eksplisit supaya `data/` tidak ikut:
   ```
   git archive --format=zip -o code.zip HEAD main.py CLAUDE.md README.md requirements.txt requirements-cst.txt cstopt designs tools docs macros
   ```
   Unggah `code.zip` (kecil). Bila tugas butuh angka dari dataset, unggah hanya `data/<RUN>/batch_lhs.csv` yang relevan (bukan `curves/`, `eff/`, `ff/`).
3. Minta Claude mengerjakan SATU tugas (ID), dengan templat di bagian 11. Claude harus menyerahkan zip berisi hanya file yang berubah,
   perintah PowerShell untuk menerapkannya, hasil uji, dan pernyataan jujur tentang apa yang belum teruji.
4. Setelah tugas selesai, perbarui `CLAUDE.md` bagian 5 dan 6 (temuan dan status) dan centang tugas di tabel bagian 2.

## 1. Keadaan saat ini (ringkas)

> Diperbarui 20 November 2026: isi bagian ini adalah keadaan 16 November dan sebagian usang (FR-4 156 sampel, RO4350B 185 sampel dan selesai). Rencana kerja terbaru ada di bagian 13.

- Alur lengkap sudah jalan: `py main.py` (GUI) dan perintah `lhs run qc curves train suggest backtest pareto status`; satu project CST = satu `RUN_NAME`
  = satu folder `data/<RUN>/`; satu desain = satu file di `designs/`.
- FR-4 (h 1,6 mm) selesai: 155 sampel. Terbaik: sampel 137 (fr 3,698 GHz, RL -18,2 dB, BW 180,6 MHz, gain 2,80 dBi); alternatif lebih aman sampel 139 dan 134.
  Target proposal BW 200 MHz dan gain 5 dBi tidak tercapai; penyebabnya sudah dibuktikan (pilot h, kontrol tan d, BW pecahan menjenuh sekitar 5%).
- Rogers RO4350B sedang dikumpulkan (project `MicrostripAntena_RO4350B`, desain `uslot_dgs_ro4350b`). Data awal (30 sampel): gain 4,9 sampai 5,4 dBi,
  BW 22 sampai 110 MHz, cakupan pita maksimum sekitar 26%.
- Fitur BO v2 sudah ada (mati secara bawaan): `--focus --constraint --region --region-auto --margin --calibrate --composite`.
- Sudah terbukti tidak membantu: kalibrasi std dari validasi silang (pengali 1,00), parameterisasi skala+bentuk (R2 fr 0,72 vs 0,69, dalam noise),
  residu rumus fisika patch untuk fr (R2 0,66 vs 0,69; di dalam pita 0,07 vs 0,74).

## 2. Peta prioritas

| ID | Tugas | Prio | Usaha | Butuh CST | Bergantung pada |
|---|---|---|---|---|---|
| P0-1 | Selesaikan data RO4350B (seed, BO, sweep gain) | P0 | 6 sampai 8 jam CST | ya | - |
| P0-2 | Validasi desain akhir: mesh rapat + toleransi ringan | P0 | 3 jam CST + skrip | ya | P0-1 |
| P0-3 | Laporan, tabel target vs tercapai, ringkasan dosen, tag rilis | P0 | 1 sampai 2 hari | tidak | P0-1 |
| P1-1 | Generalisasi desain (paket B) | P1 | 2 sampai 3 hari | tidak (uji pakai mock) | - |
| P1-2 | Validasi maju + margin dari data + R2/RMSE di wilayah kerja | P1 | 1 hari | tidak | - |
| P1-3 | Hypervolume + Pareto bentuk tangga + titik knee | P1 | 0,5 hari | tidak | - |
| P1-4 | Sensitivitas ARD/Sobol + backtest BO vs acak + aturan berhenti | P1 | 1 hari | tidak | - |
| P1-5 | Generator laporan otomatis + overlay S11 | P1 | 1 hari | tidak | P1-3 |
| P2-1 | Sapuan ε-constraint otomatis dalam satu batch (`--sweep`) | P2 | 0,5 hari | tidak | - |
| P2-2 | Local penalization (`--diversity`) | P2 | 0,5 hari | tidak | - |
| P2-3 | PoF klasifikasi + model dua bagian untuk BW (uji offline dulu) | P2 | 1 sampai 2 hari | tidak | P1-2 |
| P2-4 | Trust region adaptif (`--region-adapt`) | P2 | 1 hari | tidak | - |
| P2-5 | h diskret dan parameter turunan di BO | P2 | 1 sampai 2 hari + 30 simulasi | ya | P1-1 |
| P2-6 | ParEGO (opsional, tanpa BoTorch) | P2 | 1 hari | tidak | P2-1 |

## 3. Urutan dan jadwal sampai 1 Desember

Sisa waktu pendek. Prinsip: semua yang tidak butuh CST dikerjakan paralel selagi pengguna menjalankan simulasi.

- **Minggu 1:** P0-1 (pengguna menjalankan CST). Paralel (Claude): P1-2, P1-3.
- **Minggu 2:** P0-2 (CST). Paralel: P1-1 (paket B), P1-4.
- **Minggu 3:** P0-3, P1-5. Bekukan fitur (tidak ada fitur baru setelah ini). P2 hanya bila P0 dan P1 selesai dan ada bukti offline bahwa ia membantu.
- **Gerbang keputusan:** (a) tujuh hari sebelum tenggat: pembekuan fitur; (b) tiga hari sebelum tenggat: laporan final dan tag rilis; (c) bila P0-1 mundur,
  P1-1 dan P1-4 dikorbankan lebih dulu, bukan P0-2 atau P0-3.

---

## 4. Tugas P0

### P0-1 Selesaikan data RO4350B

Tujuan: mendapatkan kurva trade-off BW terhadap gain pada RO4350B (target gain >= 5 dBi dengan BW setinggi mungkin, dan titik gain lebih rendah).
Langkah (rinci di `docs/substrat_ro4350b.md`):
1. Project CST `MicrostripAntena_RO4350B` sudah dibuat (material library, `hs` 1,524, `Wf` dari `tools/wf50.py`). Catat epsilon dan tan delta library dan cocokkan dengan
   `SUBSTRATE` di `designs/uslot_dgs_ro4350b.py` (asumsi 3,66 dan 0,0037); bila beda, ubah `SUBSTRATE`, dan hitung ulang `Wf` dan seed.
2. Seed: `py tools\make_seeds.py --to uslot_dgs_ro4350b --n 10`, jalankan 1 sampel dulu lalu sisanya.
3. Putaran BO, 6 sampai 8 putaran @5 sampel:
   `py main.py suggest --design uslot_dgs_ro4350b --region-auto 6:0.15 --margin fr_ghz=0.08 -q 5` lalu `py main.py run --samples <bo_candidates.csv> --auto-yes`.
4. Sapuan batas gain (tiap batas 1 sampai 2 putaran): `--focus bw --constraint "gain_fr_ieee_dbi>=5.2"`, lalu 5,0; 4,5; 4,0; 3,5. Tambahkan `--focus cover` dan `--focus gain --constraint "bw_mhz>=100"`.
5. `py main.py curves --run-name MicrostripAntena_RO4350B` harus "KONSISTEN"; `py main.py qc`; `py main.py pareto`.
Kriteria lulus: kedua sumbu front Pareto RO punya minimal 6 titik dan rentang BW front lebih dari 50 MHz, atau dilaporkan terus terang bahwa front pendek karena BW dibatasi fisika.
Catatan: BW = 0 bila RL minimum > -10 dB (definisi, bukan bug); banyak seed awal bisa BW = 0 karena geometri FR-4 belum dicocokkan ulang.

### P0-2 Validasi desain akhir (mesh rapat dan toleransi ringan)

Tujuan: menunjukkan hasil akhir stabil terhadap mesh dan masuk akal terhadap toleransi fabrikasi. Ini versi ringan "robust design"; bukan klaim kebaruan
(topiknya mapan di literatur desain antena; jangan menyebutnya kontribusi utama).

Bagian A, mesh: pilih 2 sampai 3 desain akhir per substrat. Naikkan mesh di CST satu tingkat (mis. lines per wavelength atau akurasi solver; catat nilai lama dan baru),
simulasikan ulang lewat `--run-name <run>_fine`. Lulus bila selisih fr < 10 MHz dan BW < 5% (bila tidak, laporkan selisihnya).

Bagian B, toleransi. Buat `tools/make_tolerance.py` (baru):
- Masukan: `--run`, `--sample ID`, `--plan oat|corners|random`, `--out CSV`.
- Ambil parameter sampel dari `data/<run>/batch_lhs.csv`. Perturbasi satu per satu (OAT) +/-: Lp dan Wp +/-0,1 mm; gU dan gD +/-0,05 mm (jaga >= batas fabrikasi, lihat bagian 8);
  LI +/-0,1 mm; `hs` +/-10% (kolom `hs` dan `Wf` otomatis jadi parameter ekstra; `Wf` dihitung ulang dengan `tools/wf50.py`); opsional epsilon +/-0,05 (butuh parameter
  CST baru, pakai nama aman seperti `epsR`; JANGAN `er`/`tand` bila ditolak CST: nama tidak boleh sama dengan nama objek VBA).
- `corners`: 4 kombinasi terburuk (semua toleransi searah memperkecil fr, searah memperbesar fr, dst.). `random`: 12 sampel acak dari distribusi seragam dalam toleransi.
- Total sekitar 12 sampai 20 simulasi per desain. Keluaran CSV dengan kolom parameter + `hs` + `Wf` (+ `epsR`) siap untuk `py main.py run --run-name <run>_tol --samples ...`.

Buat `tools/analyze_tolerance.py` (baru): baca `data/<run>_tol/batch_lhs.csv`; hitung per kolom (fr, RL, BW, gain) nominal, minimum, maksimum, simpangan baku, dan "yield" =
proporsi skenario yang masih memenuhi target (fr di pita, RL <= -10, BW >= X, gain >= Y; X dan Y dari bagian 8). Keluaran tabel (CSV, markdown) dan PNG tornado (dampak tiap parameter).
Kriteria lulus: tabel worst-case dan yield untuk tiap desain akhir; kalimat laporan hanya memakai angka dari tabel ini.

### P0-3 Laporan dan rilis

1. Tabel "target proposal vs tercapai" per substrat (bagian 8), ditulis apa adanya termasuk yang tidak tercapai.
2. Bagian "Deviasi dari proposal" (1 halaman): target yang diubah, alasan, bukti (pilot h, kontrol tan d, plateau BW pecahan, batas efisiensi).
3. Ringkasan satu halaman untuk dosen: hasil utama, kurva Pareto dua substrat, apa yang tidak tercapai dan kenapa, apa yang bisa dipakai ulang (alur dan kode).
4. Perbarui `docs/progres_fr4.md` dan `CLAUDE.md`; tag rilis `v1.0-fr4-ro4350b` pada commit akhir; opsional unggah dataset ke Zenodo untuk DOI (luaran "dataset" di proposal).
5. Pengerjaan sebagian bisa otomatis lewat P1-5.

---

## 5. Tugas P1

### P1-1 Generalisasi desain (paket B)

Tujuan: desain antena lain (bentuk slot dan DGS lain, satu port) bisa dipakai tanpa mengubah kode inti. MIMO dan array di luar lingkup (butuh matriks S multi port).
Sekarang bagian ML sudah generik (semua di `designs/`), tetapi sisi CST masih memuat konstanta khusus desain ini.

Inventaris yang harus dipindahkan ke file desain (cari dengan `grep -n "PARAM_NAMES\|BASE\b\|BAND\|MON_\|BW_MIN\|GAIN_MIN\|check_geometry" cstopt/cst/*.py`):
- `cst/export.py`: `PARAM_NAMES` (11 nama), `FIELDS` (turunan dari `PARAM_NAMES`), `BAND_GHZ`, ambang (RL, BW, gain), `MON_START/STOP/STEP` (frekuensi monitor farfield), frekuensi f0.
- `cst/batch.py`: dict `BASE` (baseline parameter), `BASE_EXTRA` dan `LOSS_NAMES`, fungsi `check_geometry` (duplikat `geometry_problems` di file desain).
- `ml/core.py`: `s11_features` dan `add_s11_features` (fitur kurva S11 khusus antena).

Antarmuka file desain yang dituju (tambahkan, dengan nilai bawaan agar desain lama tetap jalan):
```python
BASE_PARAMS = {"Lp": 20.22, ...}                 # baseline CST (dulu BASE di batch.py)
EXTRA_BASE = {"hs": 1.6, "Wf": 3.11, "lossTan": 0.025}   # parameter ekstra yang boleh muncul di CSV, beserta baseline
CST = {"band_ghz": (3.3, 3.7), "rl_limit_db": -10.0, "f0_ghz": 3.5,
       "monitors_ghz": (2.5, 4.5, 0.25)}
def features(df, d): ...                          # opsional: fitur turunan dari kurva; bawaan = fitur S11 yang ada
DISCRETE = {"hs": [1.6, 2.0, 2.4]}                # opsional (untuk P2-5)
DERIVED = {"Wf": lambda p: wf50(4.3, p["hs"])}    # opsional (untuk P2-5)
```
Langkah:
1. Buat `cstopt/cst/config.py` dengan `configure(design_module)` yang mengisi variabel modul `export` dan `batch` (PARAM_NAMES, FIELDS, BASE, ambang, monitor) dari file desain;
   bila atribut tidak ada pakai nilai lama (kompatibel mundur). Panggil di `batch.main()` dan `export.main()` setelah `parse_args`, dengan opsi baru `--design` (bawaan desain bawaan).
2. Hapus duplikat `check_geometry` di `batch.py`; pakai `design.geometry_problems`.
3. `ml/core.py`: ganti pemanggilan `add_s11_features(df, d)` menjadi `d.mod.features(df, d)` bila ada, selain itu fungsi lama.
4. `batch.py`: peringatan bila nama project CST berbeda dari `RUN_NAME` desain (sumber kekacauan data). `detect_extras` memakai `EXTRA_BASE` desain.
5. `designs/_template.py` (diawali garis bawah agar tidak muncul di daftar) berisi semua antarmuka di atas dengan komentar; `tools/new_design.py NAMA --from uslot_dgs_fr4` menyalin dan mengganti `NAME`, `RUN_NAME`, `SUBSTRATE`.
6. `docs/membuat_desain_baru.md`: konvensi macro (macro VBA mendefinisikan parameter dengan nama yang PERSIS sama dengan `PARAM_NAMES`; nama parameter tidak boleh nama objek VBA), langkah membuat project, seed, dan menjalankan alur.
7. Uji tanpa CST: `designs/_demo_analytic.py` dan `tools/mock_run.py` yang mengganti `run` dengan fungsi analitik (menulis `batch_lhs.csv` dan `curves/` sintetis dengan kolom sama). Dengan itu seluruh alur (lhs, mock_run, train, suggest, pareto) bisa diuji di mesin mana pun.
Kriteria lulus: (a) `suggest` seed 0 pada FR-4 identik dengan sebelum perubahan (`tools/compare_csv.py`); (b) `run --check-samples` dengan modul `cst` tiruan tetap lolos untuk CSV pilot dan kontrol; (c) desain demo analitik menjalankan alur penuh;
(d) desain baru dari scaffolder lolos `tools/smoke_test.py`. Risiko: `export.py` memakai variabel global di banyak fungsi; ubah lewat `configure` yang mengisi global, jangan menulis ulang fungsi.

### P1-2 Validasi maju, margin dari data, dan akurasi di wilayah kerja

Tujuan: mengganti kalibrasi sigma dan "conformal" dengan ukuran yang jujur terhadap cara model dipakai (berurutan, di wilayah ekstrapolasi). Hasil uji manual sebelumnya yang harus bisa direproduksi:
latih pada id 1 sampai 135, uji pada 136 sampai 155: fr bias +245 MHz (aktual lebih tinggi pada 18 dari 20), RMSE 316 MHz; P(fr di pita) menurut model 0,65 vs kenyataan 0,25; BW bias +25 MHz, RMSE 28 MHz.

Buat `cstopt/ml/validate.py` dan daftarkan `validate` di `main.py` (`COMMANDS`). Algoritma:
1. `d = load_design`, `df = load_dataset(d)`. Kelompokkan sampel `id > N_INITIAL` menjadi batch berurutan berukuran `--batch` (bawaan 5).
2. Untuk tiap batch b (mulai dari batch yang punya minimal `--min-train` sampel sebelumnya, bawaan `N_INITIAL`): `fit_models` pada sampel dengan id lebih kecil, hanya untuk kolom constraint dan objective tahap aktif; prediksi batch b (`predict_t`, `to_raw`).
3. Per kolom kumpulkan: bias (aktual - prediksi), RMSE, MAE, rata-rata dan simpangan baku z-score, cakupan interval 68% dan 95%.
4. Kalibrasi PoF: untuk tiap sampel uji hitung peluang feasible model (perkalian peluang constraint, sama seperti `acquisition`) dan bandingkan dengan feasible aktual: skor Brier, tabel reliabilitas (bin peluang), rata-rata prediksi vs aktual.
5. Wilayah kerja: hitung R2 dan RMSE (dalam satuan asli, mis. MHz) hanya untuk sampel dengan fr di dalam pita. Laporkan keduanya; R2 saja menyesatkan (fr di pita: R2 validasi silang 0,74 +/- 0,22, n = 58).
6. Rekomendasi: untuk constraint satu sisi yang mengikat (fr batas atas), `margin saran` = persentil 90 dari galat searah sisi itu (aktual - prediksi untuk batas atas), dibulatkan; cetak sebagai saran `--margin fr_ghz=...`.
7. Keluaran: `models/forward_validation.csv`, `figures/forward_validation.png` (kurva reliabilitas dan bias per batch), teks ringkas di terminal.
Kriteria lulus: reproduksi angka di atas (toleransi kecil karena restart GP); berjalan pada FR-4 (155 sampel) dalam kurang dari 5 menit dengan `--restarts 2`; tidak mengubah perilaku `suggest`.

### P1-3 Hypervolume dan tampilan Pareto

Ubah `cstopt/report/pareto.py`:
- Fungsi `hypervolume_2d(points, ref)` untuk dua sumbu yang dimaksimalkan. Urutkan titik front menurun pada x (maka y naik): (x1 > x2 > ..., y1 < y2 < ...).
  Daerah yang didominasi adalah gabungan persegi panjang [ref_x, x_i] x [ref_y, y_i], sehingga HV = jumlah dari i = 1..n dari (x_i - ref_x) * (y_i - y_{i-1}) dengan y_0 = ref_y.
  Uji dengan kasus tangan: satu titik (HV = luas satu persegi panjang), dua titik, dan titik yang berada di bawah ref (kontribusi nol, buang sebelum dihitung). Titik acuan `--ref` bawaan (0, 0) untuk (BW, gain) dan (cakupan, gain).
- Cetak hypervolume tiap run, dan hypervolume terhadap jumlah sampel (tambahkan sampel berurutan berdasarkan id) sebagai kurva kemajuan (panel baru atau gambar kedua `pareto_progress.png`).
- Gambar front sebagai tangga (`ax.step(..., where="post")`) bukan garis lurus (garis lurus antar titik menyesatkan: trade-off tidak harus linear).
- Titik knee: titik front dengan jarak terbesar ke garis yang menghubungkan dua ujung front (setelah normalisasi 0..1); beri tanda dan cetak.
- Peringatan bila front kurang dari 6 titik atau rentang BW front kurang dari 20% rentang BW data: "front belum representatif; tambah sampel dengan --sweep atau --focus".
Kriteria lulus: untuk data FR-4 155 sampel angka hypervolume stabil dan bisa dihitung tangan; gambar tetap dua panel; opsi lama tidak berubah.

### P1-4 Sensitivitas, backtest BO vs acak, dan aturan berhenti

1. Sensitivitas: perintah `sensitivity` (`cstopt/ml/sensitivity.py`). (a) ARD: ambil panjang skala kernel tiap model dari `models/gpr_sensitivity.csv` atau dari model terlatih, relevansi = 1/panjang skala (sudah dicetak untuk bw di `train`), gambar peta panas target x parameter. (b) Sobol: sampel Saltelli dengan `scipy.stats.qmc.Sobol` (N = 2048 * (2d + 2)) lewat prediksi MEAN GP, hitung indeks orde satu dan total; PNG `figures/sensitivity.png` dan CSV.
   Tafsirkan secara fisik hanya setelah angkanya keluar; jangan menulis kesimpulan lebih dulu.
2. Backtest: jalankan `py main.py backtest --reps 20 --steps 30 --restarts 2` pada FR-4, simpan `figures/bo_backtest.png` dan ringkasannya untuk laporan (efisiensi BO vs pencarian acak).
3. Aturan berhenti: di `suggest`, hitung `EI_maks / |f_terbaik|` dari kandidat terpilih dan cetak; bila < 1% pada dua putaran berurutan cetak "BO dianggap konvergen". Hanya informasi, tidak menghentikan apa pun.
Kriteria lulus: hasil sensitivitas FR-4 dibandingkan dengan dua temuan sebelumnya dan perbedaannya dilaporkan, tidak disembunyikan: relevansi ARD untuk BW (135 sampel) WU 0,218, PU 0,127, LU 0,121, Lp 0,118, LD 0,108;
  korelasi dengan BW pecahan WD +0,85 dan Lp -0,77 (korelasi dan sensitivitas model tidak harus sama urutannya). Backtest berjalan; `suggest` tanpa opsi tetap identik.

### P1-5 Generator laporan otomatis

Perintah `report` (`cstopt/report/report.py`). Keluaran `data/_compare/report.md` (+ PNG):
- Tabel target vs tercapai per run (bagian 8), memakai desain terbaik menurut fokus yang dinyatakan (`--focus bw|cover|gain`, `--constraint`).
- Tabel parameter desain terbaik (11 parameter + substrat).
- Gambar Pareto (panggil `pareto`), hypervolume, kurva konvergensi BO, parity GPR (salin dari `figures/`).
- Overlay kurva S11 desain di front Pareto (membaca `curves/s11_sample{id}.csv`; lewati dengan peringatan bila kurva tidak ada), garis pita 3,3 sampai 3,7 GHz dan -10 dB.
- Info reproduksi: hash commit git (`git rev-parse HEAD` bila tersedia), jumlah sampel, tanggal, versi paket.
Kriteria lulus: `py main.py report` membuat markdown yang bisa ditempel ke laporan tanpa penyuntingan angka; berjalan di mesin tanpa CST.

---

## 6. Tugas P2 (hanya bila P0 dan P1 selesai, dan ada bukti offline)

### P2-1 Sapuan ε-constraint otomatis (`--sweep`)
Tujuan: satu batch menyebar sepanjang front Pareto. Opsi `suggest --focus bw --sweep "gain_fr_ieee_dbi=4.0:5.4"`: bagi q kandidat ke q batas bawah gain yang merata pada rentang itu;
kandidat ke-i dipilih dengan constraint `gain >= batas_i` (tetap memakai Kriging believer antar kandidat). Implementasi di `suggest`: dalam loop pemilihan batch, ubah constraint fokus per iterasi
(`d.set_focus` dengan nilai batas berbeda) dan pulihkan setelahnya. Ini jauh lebih sederhana dari ParEGO dan memanfaatkan mesin yang ada. Lulus bila lima kandidat punya gain prediksi berbeda terurut sesuai batas.

### P2-2 Local penalization (`--diversity R`)
Tujuan: batch tidak berisi kandidat hampir kembar (sering terjadi). Setelah kandidat ke-i dipilih, kalikan akuisisi sisa dengan `1 - exp(-(jarak/R)^2)` (jarak di ruang satuan; R bawaan 0,15). Lulus bila jarak minimum antar kandidat lebih besar dari tanpa opsi, dan tanpa opsi hasil identik.

### P2-3 PoF klasifikasi dan model dua bagian untuk BW
Hipotesis: PoF = perkalian regresi independen terlalu optimis (0,65 vs 0,25 di uji maju), dan 44% nilai BW adalah 0. LANGKAH PERTAMA wajib uji offline lewat `validate` (P1-2): bandingkan skor Brier dan kalibrasi
(a) PoF perkalian regresi, (b) klasifikator langsung (mis. `GaussianProcessClassifier` atau regresi logistik pada fitur RBF) untuk label `feasible`, (c) model dua bagian: P(BW > 0) dari klasifikator x BW | BW > 0 dari GP pada log BW.
Adopsi hanya bila Brier membaik lebih dari 10% dan kemiringan kalibrasi lebih dekat ke 1 pada validasi maju FR-4 dan data RO. Bila diadopsi: opsi `--pof classifier`; bawaan tetap lama.

### P2-4 Trust region adaptif (`--region-adapt`)
Pusat = desain feasible terbaik; panjang sisi awal 0,3 x lebar BOUNDS; setelah tiap putaran: bila terbaik membaik lebih dari epsilon maka hitung sukses, dua sukses berturut-turut: sisi x 1,5 (maks 0,8);
tiga gagal berturut-turut: sisi / 2 (min 0,05). Simpan keadaan di `data/<RUN>/samples/region_state.json`. Menggantikan pemilihan `K:margin` manual. Lulus: region bergerak masuk akal pada riwayat FR-4 (replay lewat `backtest`).

### P2-5 h diskret dan parameter turunan di BO (butuh P1-1)
Tujuan: h menjadi variabel BO bersama geometri (bukan "h dulu baru geometri": geometri optimum bergantung pada h, dan pilot memakai geometri yang disetel untuk 1,6 mm sehingga bias).
`PARAM_NAMES` ditambah `hs`; `BOUNDS["hs"] = (1.6, 2.4)`; `DISCRETE = {"hs": [1.6, 2.0, 2.4]}` (cek ketebalan laminat vendor); `snap()` membulatkan ke nilai diizinkan terdekat; kolom turunan `Wf` dihitung dari `hs`
(DERIVED) dan ditulis ke `bo_candidates.csv` supaya `run` otomatis mengaturnya. Dataset lama di-backfill `hs = 1.6` dan pilot h (8 sampel) digabung. Perkiraan keuntungan: BW paling banyak +10 sampai 15 MHz di FR-4;
pada RO4350B h = 1,524 mm sudah laminat standar paling tebal (cek datasheet), jadi tidak ada ruang naik. Prioritas rendah untuk target laporan; nilainya terutama sebagai demonstrasi parameter diskret dan turunan.

### P2-6 ParEGO (opsional)
Hanya bila P2-1 tidak cukup. Skalarisasi Chebyshev acak per kandidat (bobot dari simpleks), objektif tunggal ternormalisasi, akuisisi EI yang ada. Tanpa BoTorch/PyTorch (repo sengaja ringan).

---

## 7. Yang sengaja tidak dikerjakan (dan alasannya)

| Item | Alasan |
|---|---|
| Conformal prediction | Jaminan cakupan membutuhkan data yang dapat dipertukarkan; sampel BO dipilih berurutan di wilayah ekstrapolasi, tepat kasus yang gagal. Gantinya: P1-2. |
| BoTorch qEHVI | Menambah PyTorch yang berat; Pareto sudah didapat lewat ε-constraint dan P2-1. |
| Multi-fidelity BO | Butuh macro mesh kasar dan 1 minggu; di luar tenggat. Future work. |
| Transfer learning formal (GP multi-tugas) | Klaim hemat 30 sampai 50% belum terbukti; seed berskala sqrt(eeff) sudah bentuk ringan transfer. Future work. |
| Residu rumus fisika untuk fr | Sudah diuji: R2 0,66 vs 0,69 (lebih buruk); di dalam pita 0,07. Gugur. |
| Parameterisasi skala+bentuk | Sudah diuji: 0,72 vs 0,69 (dalam noise). Gugur. |
| Kalibrasi std dari validasi silang | Sudah diuji: pengali 1,00; masalah fr adalah bias ekstrapolasi, bukan sebaran. Tetap tersedia (`--calibrate`) tetapi tidak berguna di data ini. |
| BMA, clustering, cost-aware BO | Insight terbatas untuk lingkup ini. |
| GUI klik titik lalu lihat S11 | Nilai ilmiah rendah; overlay S11 statis di P1-5 sudah cukup. |
| MIMO dan array | Butuh matriks S multi port; di luar lingkup. |
| Topologi dua resonansi (patch bertumpuk atau parasitik) | Kemungkinan jalan untuk BW >= 200 MHz sekaligus gain >= 5 dBi pada substrat rugi rendah; cocok sebagai future work di laporan, bukan dikerjakan sekarang. |

## 8. Definisi target dan cara menyajikan data

Target proposal sebagai acuan: fr 3,3 sampai 3,7 GHz, RL minimum <= -10 dB, BW >= 200 MHz, gain >= 5 dBi (ideal 6), R2 model >= 0,85. Dua target terakhir tidak tercapai bersamaan di kedua substrat; laporkan terbuka.
Gunakan target realistis dua tingkat dan selalu tampilkan selisih terhadap proposal:

| Substrat | Target realistis | Cara mendapatkan |
|---|---|---|
| FR-4 h 1,6 | maksimalkan BW dengan gain >= 2,5 dBi | sudah tercapai: 180,6 MHz (90% dari 200); gain 2,80 |
| RO4350B h 1,524 | (A) gain >= 5 dBi dengan BW setinggi mungkin; (B) BW setinggi mungkin dengan gain >= 4 dBi | `--focus bw --constraint "gain_fr_ieee_dbi>=5.0"` dan `>=4.0` |

Penyajian data (urutan prioritas):
1. Tabel target vs tercapai per substrat (fr, RL, BW, BW pecahan, cakupan pita, gain, efisiensi, selisih terhadap proposal).
2. Kurva Pareto BW vs gain dan cakupan vs gain, dua substrat dalam satu gambar, bentuk tangga, knee ditandai, hypervolume per substrat.
3. Overlay S11 desain di front, pita 3,3 sampai 3,7 GHz diarsir.
4. Bukti batas fisik: kontrol tan d (efisiensi dan gain naik, BW turun) dan pilot h (h tidak membantu) sebagai dua gambar kecil.
5. Metode: konvergensi BO, BO vs acak (backtest), parity GPR dengan RMSE dalam MHz, sensitivitas parameter.
6. Toleransi: tabel worst-case dan yield (P0-2).
Catatan definisi yang HARUS tertulis di laporan: BW = lebar pita S11 <= -10 dB di sekitar minimum global (BW = 0 bila RL minimum > -10 dB); cakupan pita = persentase frekuensi di 3,3 sampai 3,7 GHz dengan S11 <= -10 dB;
gain = gain IEEE di frekuensi resonansi (D + 10 log eta); substrat dari library CST dengan nilai epsilon dan tan delta yang tertulis di material.
Peringatan: prediksi cakupan pita di atas sekitar 45% tidak realistis (BW pecahan menjenuh sekitar 5%); manufaktur: celah gU dan gD boleh sampai 0,2 mm, mendekati batas etsa PCB: tanyakan batas vendor dan jadikan constraint di `geometry_problems`.

## 9. Aturan pengujian dan kriteria lulus (semua tugas)

- Regresi wajib: `py main.py suggest -q 5 --seed 0 --restarts 2 --pool 8192` pada FR-4 harus identik dengan sebelum perubahan (`py tools\compare_csv.py lama.csv baru.csv` harus IDENTIK) selama opsi baru tidak dipakai.
- `py tools\smoke_test.py` harus SEMUA LULUS untuk semua desain.
- Uji tanpa CST memakai paket `cst` tiruan (`cst/__init__.py`, `cst/results.py`, `cst/interface.py` dengan kelas `DesignEnvironment`) dan objek project tiruan yang punya `StoreDoubleParameter`, `RestoreDoubleParameter`, `full_history_rebuild`.
- GUI diuji di layar virtual (`apt-get install python3-tk`, `xvfb-run`, tangkap layar dengan `PIL.ImageGrab(xdisplay=...)`) dan perubahan GUI tidak boleh merusak tab lain.
- Bila opsi baru mengubah hasil, bandingkan dengan opsi mati dan tunjukkan perbedaannya pada data asli, bukan hanya "berjalan tanpa error".
- Penyerahan: zip berisi hanya file yang berubah, perintah PowerShell (`Expand-Archive -Path ... -DestinationPath . -Force`, branch baru, commit), dan daftar jujur "belum teruji" (terutama CST nyata dan tampilan GUI di Windows).
- Jangan mencetak CSV atau log penuh; jangan membaca `data/` (aturan di `CLAUDE.md` bagian 0).

## 10. Umpan balik jujur

Kekuatan hasil: alur utuh dan bisa direproduksi (kontrol CST identik dengan data asli); diagnosis berbasis bukti (BO vs LHS: 0 dari 80 vs 52 dari 70 feasible; bias model fr terukur; batas fisik dibuktikan dua eksperimen); dua substrat dengan alur yang sama.

Kelemahan yang perlu diwaspadai:
1. Kesimpulan pilot h dan kontrol tan d bersandar pada dua desain dasar dan geometri yang tidak dioptimasi ulang; tulis keterbatasan itu.
2. Data RO4350B masih awal; front Pareto-nya pendek. Jangan menyimpulkan bentuk trade-off sebelum titiknya cukup (P0-1 kriteria).
3. Beberapa prediksi saya meleset (BW ∝ h, efisiensi naik dengan h; model Q sederhana terlalu optimis). Perlakukan prediksi model sederhana sebagai hipotesis yang diuji. Verifikasi klaim fisika sebelum menuliskannya.
4. GP mengekstrapolasi terlalu optimis: peluang feasible 0,65 vs kenyataan 0,25; fokus gain dan cakupan tanpa region menghasilkan prediksi ekstrem (BW 424 MHz). Selalu pakai `--region-auto` dan `--margin` untuk fokus.
5. Dokumen "AI lain" memuat klaim yang tidak bisa dipegang: kebaruan analisis toleransi (topik mapan), jaminan conformal pada data BO, contoh kalimat hasil ("RO4350B 5,1 turun ke 4,6 dBi, yield 92%"; "BW 141 vs 105") yang bukan data kita.
   Jangan menuliskan angka yang tidak berasal dari tabel hasil.
6. Risiko ruang lingkup: tenggat 1 Desember. Fitur baru tidak boleh mengorbankan P0. Bekukan fitur tujuh hari sebelum tenggat. P2 hanya dengan bukti offline.
7. Target publikasi di proposal adalah jurnal nasional terakreditasi; kontribusi yang sudah ada (alur, diagnosis, dua substrat, trade-off) cukup kuat bila ditulis jujur dengan bagian "Deviasi dari proposal".
8. Higiene: satu cabang per tugas, commit kecil, tag rilis, perbarui `CLAUDE.md` setiap akhir sesi.

## 11. Templat prompt untuk percakapan baru

Mulai (selalu):
> Baca CLAUDE.md dan RENCANA_LANJUTAN.md. Kerjakan HANYA tugas <ID> sesuai spesifikasinya. Patuhi aturan hemat token (jangan baca data/, jangan listing repo; baca file lewat grep atau sed).
> Sebelum mengubah file, tunjukkan rencana singkat dan perhitungan, lalu tunggu persetujuan. Serahkan zip file yang berubah, perintah PowerShell, hasil uji (termasuk regresi seed 0), dan daftar jujur yang belum teruji.

Contoh P1-2:
> ...tugas P1-2 (validasi maju). Saya unggah code.zip dan data/MicrostripAntena/batch_lhs.csv. Reproduksi angka di spesifikasi (bias fr +245 MHz, P in-band 0,65 vs 0,25) sebelum menambah apa pun.

Contoh P1-1:
> ...tugas P1-1 (generalisasi desain). Mulai dengan inventaris konstanta (grep) dan tunjukkan daftar yang akan dipindah ke file desain; jangan menulis ulang fungsi, ubah lewat configure().

Contoh analisis hasil:
> ...saya unggah batch_lhs.csv RO4350B (ringkasan saja). Baca front Pareto, hitung hypervolume, dan beri tahu titik mana yang perlu ditambah sebelum saya menjalankan CST lagi.

## 12. Lampiran: angka acuan dan jebakan

- FR-4 155 sampel: feasible Tahap 2: 52 (LHS 0 dari 80; BO tahap 2 52 dari 70). BW = 0 pada 68 dari 155 sampel, semuanya RL minimum di antara -10,0 dan -4,2 dB.
- Maksimum seluruh data FR-4: gain 3,13 dBi, eta 0,511, directivity 6,73 dBi, cakupan pita 38,9% (sampel 120). Gain 5 dBi butuh eta sekitar 0,67.
- Pilot h (rasio terhadap 1,6 mm, baseline 109/137): h 2,0: BW 1,06/1,00x, eta 0,95/0,94x, fr +20/+30 MHz; h 2,4: BW 1,04/1,05x, eta 0,91/0,94x, fr +38/+56; h 3,2: BW 0,92/0,83x, eta 0,91/0,90x, fr +48/+82.
- Kontrol tan d (109): 0,025: eta 0,474, gain 2,77, BW 150,6; 0,010: 0,639, 4,13, 95,9; 0,004: 0,750, 4,84, 50,3; 0,001: 0,817, 5,23, 0 (RL minimum -9,77).
- R2 validasi silang FR-4: BW 0,94 sampai 0,96; RL minimum 0,82 sampai 0,88; fr 0,65 sampai 0,69; gain 0,27 sampai 0,5 (komposit D + 10 log eta: 0,61); BW pecahan 0,95.
- Nama parameter CST: `tand` DITOLAK; pakai `lossTan` (alias `dLoss`, `tanDelta`, `tdelta`). Nama parameter baru harus bukan nama objek VBA; uji di CST sebelum menulis kode yang bergantung padanya.
- Kolom `hs`, `Wf`, `lossTan` di CSV sampel otomatis menjadi parameter ekstra (jangan sampai diabaikan; tanpa itu baris dianggap duplikat).
- Sandbox: `/bin/sh` tanpa brace expansion; salin folder data dengan `cp -r a/. b/` (bukan `cp -r a b` bila `b` sudah ada); GUI hanya bisa diuji lewat `xvfb-run`.
- Wf 50 ohm: FR-4 h 1,6: 3,112 mm (macro 3,11); RO4350B h 1,524 dengan epsilon 3,66: sekitar 3,336 mm.


## Lanjutan: GUI, rentang parameter, tampilan data, dan ide (disepakati 18 November 2026)

Konteks: P0, P1, dan P2-1 sampai P2-4 selesai (P2-3 hasil negatif; P2-5 dan P2-6 dilewati). Permintaan pengguna: memperbaiki tampilan GUI,
menyambungkan semua fitur ke GUI, mengubah rentang parameter (BOUNDS) secara manual atau otomatis dari GUI, mengatur h, memperkaya tampilan data,
laporan, dan grafik, serta mengoptimalkan metode ML. Tiap tahap = satu zip berisi file berubah saja; opsi baru mati secara bawaan; regresi
`suggest` seed 0 harus tetap IDENTIK; uji GUI di sandbox lewat xvfb dan tangkap layar (tampilan di Windows dan CST nyata diuji pengguna).

Status pembekuan fitur 24 November untuk pekerjaan GUI: BELUM diputuskan pengguna. G1 dimulai 18 November karena risikonya paling rendah
(tidak menyentuh inti `suggest`); G2 sampai G5 menunggu keputusan itu.

| Tahap | Isi | Risiko | Butuh CST | File utama |
|---|---|---|---|---|
| G1 | Sambungkan ke GUI: `--sweep`, `--diversity`, `--region-adapt` (saling eksklusif dengan region manual dan otomatis), serta tombol `validate`, `sensitivity`, `report` | rendah | tidak | `gui/app.py`, `gui/commands.py` |
| G2 | Panel rentang parameter: tabel min/max yang bisa diedit; tombol "usulkan pelebaran" dari peringatan parameter menempel batas; validasi geometri sebelum disimpan; disimpan sebagai file override per run (bukan mengedit `designs/*.py`); tanpa override hasil IDENTIK | sedang | tidak (tetapi geometri hasil pelebaran harus bisa disimulasikan di CST: keputusan pengguna) | `ml/core.py` (`load_design`), `gui/app.py` |
| G3 | Tampilan data: tabel sampel yang bisa diurutkan dan disaring, sorotan feasible, klik baris untuk melihat kurva S11; tab grafik (Pareto dengan kandidat sweep, parameter vs objective, koordinat paralel); ekspor PNG; perbaikan `report` | rendah | tidak | `gui/app.py`, `report/` (perlu contoh bagian laporan yang dianggap kurang) |
| G4 | Perbaikan tampilan: tema, tata letak, bilah status, skala font untuk layar laptop (tangkap layar dari sandbox untuk dinilai pengguna) | rendah | tidak | `gui/app.py` |
| G5a | Dialog substrat (er, tan delta, h; Wf dihitung otomatis lewat `tools/wf50.py`) yang membungkus `tools/new_design.py` | rendah | tidak | `gui/app.py` |

Status 18 November 2026: G1 selesai (paketR); G2a (backend dan CLI `bounds`) selesai (paketS); G2b (dialog GUI) selesai (paketT); G3 sampai G5 menunggu keputusan pengguna.
Status 19 November 2026: G3 selesai di sandbox kecuali perbaikan `report` (koordinat paralel dan kandidat sweep di grafik: paketAA; `report` menunggu contoh bagian yang kurang); G4a kode selesai (paketZ sampai Z3), G4b dibatalkan.

Catatan penting G2: mengubah BOUNDS mengubah normalisasi ruang satuan, sehingga jarak `--spread`, `--diversity`, dan `min_dist` ikut berubah makna.
Sampel lama tetap valid dan model dilatih ulang tiap putaran, tetapi hasil tidak identik dengan sebelum pelebaran. Pelebaran otomatis hanya MENGUSULKAN;
penerapannya selalu lewat konfirmasi pengguna. Motivasi: log pengguna 18 November menunjukkan kandidat menempel batas (FR-4: WU bawah, WD atas;
RO4350B: LU bawah, WD atas) dan RO4350B belum konvergen (EI maks 12,7% dari terbaik, ambang 1%).

### Catatan untuk nanti (BELUM dijadwalkan; dicoba hanya bila pengguna memutuskan)
- **G5b: h sebagai variabel BO** (= P2-5). `hs` masuk `PARAM_NAMES` dengan `DISCRETE` (nilai laminat vendor) dan `Wf` sebagai kolom turunan (`DERIVED`, lewat `wf50`),
  dataset lama di-backfill. Butuh sekitar 30 simulasi CST; perkiraan untung paling banyak +10 sampai 15 MHz di FR-4; RO4350B tidak punya ruang naik
  (1,524 mm sudah laminat standar paling tebal; cek datasheet vendor). Nilai utamanya demonstrasi parameter diskret dan turunan. Detail ada di bagian P2-5 di atas.
- **Optimasi ML** (jalur terpisah, tiap ide wajib lolos gerbang validasi maju yang sama dengan P2-3: Brier dan RMSE di wilayah kerja, baik FR-4 maupun RO4350B):
  kernel Matern vs RBF lewat `validate --kernel`, level noise, transformasi input, prior tren. Data hanya 156 dan 185 sampel dan PoF terlalu yakin
  (kemiringan kalibrasi 0,25 sampai 0,36), jadi jangan menjanjikan perbaikan besar; G2 (rentang) kemungkinan lebih berpengaruh daripada perubahan model.

Status 19 November 2026 (T2): tata letak tab 1 sampai 5 dan 7 selesai di sandbox tanpa uji GUI (paketT2); berikutnya T1 tema gelap (`gui/theme.py`).

---

## 13. Rencana penutup (disepakati 20 November 2026): report per desain, laporan, rilis, uji CST, fitur lanjutan, demonstrasi

Bagian ini menggantikan urutan kerja di bagian 3 untuk sisa waktu. Bagian 1 sampai 12 tetap sebagai referensi (angka bagian 1 adalah keadaan 16 November dan sebagian sudah usang:
FR-4 kini 156 sampel, RO4350B 185 sampel dan pengumpulan data selesai).

### 13.1 Keputusan pengguna

- Dosen menerima target proposal yang tidak tercapai (target dibuat terlalu tinggi); yang penting gain dan RL tinggi. Target yang meleset ditulis apa adanya, tanpa dikejar lagi.
- ML di proposal adalah surrogate GPR dengan BO. Tidak ada pembanding ML lain karena riset tidak menyinggungnya. Tidak ada penyetelan BO lagi.
- GUI, grafik, dan autorun dibuat atas inisiatif sendiri agar pengguna lain tidak perlu CLI. Tidak ada fitur GUI baru; GUI hanya diubah untuk F1.
- Demonstrasi pada desain antena lain dilakukan setelah kode final dan laporan selesai.
- Report dijalankan per desain (tidak digabung), supaya demonstrasi tidak ikut membawa desain lama.
- Impedansi masukan dan pola radiasi 3D dicatat sebagai fitur lanjutan (F11), dikerjakan sebelum demonstrasi.

### 13.2 Temuan yang dipakai (jangan dihitung ulang tanpa perlu)

- RO4350B punya dua fase karena rentang parameter dilebarkan di tengah pengumpulan. Sampel 46 sampai 120 menempel pada WD maksimum 10,0 mm dengan BW fisibel terbaik 127 sampai 134 MHz.
  Setelah WD dilebarkan (14 mm lalu 18 mm), wilayah WD 15 sampai 18 mm dan LI sekitar 5,8 sampai 6,3 mm memberi BW 190 sampai 247 MHz (13 sampel, id terkecil 146). Sebanyak 91 dari 185 sampel
  berada di 100 sampai 140 MHz dan hanya 2 sampel di 200 sampai 220 MHz. Itu pergeseran wilayah akibat batas, bukan ketidakstabilan BO. Batas awal 10 mm belum diverifikasi dari riwayat git.
  Dugaan (BELUM diuji): validasi maju RO4350B yang lemah sebagian berasal dari pergeseran wilayah ini; perlu hitung ulang yang memisahkan dua fase.
- Impedansi: `export.py` membaca S11 kompleks, tetapi `curves/*.csv` hanya menyimpan magnitudo dalam dB. Fase tidak tersimpan, sehingga Zin dan Smith chart tidak bisa direkonstruksi dari data yang ada.
- `ff/` berisi DIRECTIVITY (bukan gain) irisan phi = 0 dan phi = 90 di 3,5 GHz dan monitor terdekat fr (RO4350B: 414 berkas, 360 sudut per irisan), dengan kolom Abs(Theta), Abs(Phi), dan Ax.Ratio.
  Gain dihitung sebagai directivity ditambah 10 log10 efisiensi. Pola 3D tidak ada di data.
- Tombol Laporan di GUI memanggil `report` tanpa `--runs` dan `--out-dir`, sehingga selalu gabungan dan menimpa `data/_compare`. CLI sudah mendukung per desain (`--runs RUN --out-dir DIR`);
  diuji di sandbox untuk RO4350B: 8 bagian, tanpa FR-4.
- Keterbatasan yang harus ditulis di laporan: satu seed dan satu putaran per substrat; perbandingan FR-4 dan RO4350B tidak setara (156 vs 185 sampel, BOUNDS RO diubah tiga kali, syarat gain berbeda);
  gain diukur di fr, bukan di seluruh pita; tidak ada pembanding surrogate atau optimizer lain.

### 13.3 Tugas

| ID | Tugas | Butuh CST | Pelaksana | Bergantung pada |
|---|---|---|---|---|
| F1 | Tombol Laporan di GUI per desain | tidak | Claude | tidak ada |
| F2 | Bagian 9 laporan: pola 2D, metrik pola, VSWR, efisiensi, tabel ringkas | tidak | Claude | tidak ada |
| F3 | Gambar fase optimasi (nilai fokus terhadap sample_id) | tidak | Claude | tidak ada |
| F4 | Membuat report per desain dan memeriksa angkanya | tidak | pengguna dan Claude | F1 sampai F3 |
| F5 | Memperbarui deviasi_proposal dan ringkasan_dosen | tidak | Claude | F4 |
| F6 | Naskah laporan final | tidak | pengguna dan Claude | F4, F5 |
| F7 | `package_dataset` dan tag rilis `v1.0-fr4-ro4350b` | tidak | pengguna | F6, F8 |
| F8 | Uji CST nyata (daftar periksa) | ya | pengguna | tidak ada |
| F9 | Pemeriksaan menempel batas di autorun (opsional) | tidak | Claude | tidak ada |
| F10 | Perbaikan skrip uji `test_gui_t2` (opsional) | tidak | Claude | tidak ada |
| F11 | Fitur lanjutan: impedansi dan pola 3D (sebelum demonstrasi) | ya | Claude dan pengguna | F8 |
| F12 | Demonstrasi pada desain antena lain | ya | pengguna dan Claude | F7, F11 |

Status 22 November 2026 (lanjutan): F4 dan F5 selesai (laporan RO4350B diperiksa; `deviasi_proposal.md` dan `ringkasan_dosen.md` diperbarui, paketF5). Berikutnya F6, F7, F8.

Status 22 November 2026: F4a (tambahan di luar daftar awal) selesai di sandbox: desain rekomendasi tahan toleransi (`--min-yield`, bawaan 90), peringatan parameter di batas rentang, dan kalimat target bersamaan di bagian 3; dipicu oleh laporan RO4350B yang memilih sampel 179 (yield toleransi 17,4%). F4 (memeriksa angka laporan) berjalan; F5 memakai temuan ini.

Status 20 November 2026: F1, F2, dan F3 selesai di sandbox (paketF1; uji `tools/test_report_pattern.py` dan `tools/test_gui_report.py` lulus, `suggest` seed 0 identik). Belum diuji di Windows. Berikutnya F4.

#### F1 Tombol Laporan di GUI per desain
- `commands.report(runs, focus, constraints, out_dir=None)` menambahkan `--out-dir` bila diisi. CLI tidak berubah (bawaan tetap `data/_compare`).
- `do_report` memakai run dari desain yang dipilih di kotak Desain dan keluaran `data/_report_<run>`. Opsi "Semua desain (gabungan)" boleh ada, tetapi bukan bawaan.
- Uji: argumen yang dibentuk (`--runs <run> --out-dir data/_report_<run>`), tombol terkunci saat berjalan, tangkapan layar tab 6.

#### F2 Bagian 9 laporan (modul baru `cstopt/report/pattern.py`, dipanggil dari `report.py`)
- Pola 2D (polar dan kartesian) irisan phi = 0 dan phi = 90 di 3,5 GHz dan monitor fr, untuk desain terbaik dan desain knee tiap run. Sumbu dan keterangan harus berbunyi directivity (dBi), bukan gain.
- Metrik dari `ff/`: HPBW bidang E dan H, front to back ratio, level cross pol (selisih komponen), axial ratio di boresight, arah puncak. Tulis kolom sumbernya dan asumsi bidang E dan H.
- VSWR terhadap frekuensi dari `curves/` (VSWR = (1 + |S11|) / (1 - |S11|)) dan efisiensi radiasi serta total terhadap frekuensi dari `eff/`.
- Tabel ringkas desain final: dimensi, fr, RL minimum, VSWR, BW, cakupan pita, directivity, gain, efisiensi. Tabel toleransi bila `data/<run>_tol` ada.
- Berkas yang tidak ada dilewati dengan catatan di laporan, bukan galat. Keluaran PNG dan markdown. Uji pada data RO4350B dan FR-4 di sandbox; tanpa CST.

#### F3 Gambar fase optimasi
- `report` menambah gambar nilai fokus (BW) terhadap `sample_id`, berwarna oleh satu parameter. Bawaan: parameter dengan korelasi Spearman terbesar terhadap fokus; `--color-by` untuk menimpa.
  Garis penanda perubahan rentang bila `bounds_override.json` ada. Untuk RO4350B diharapkan menonjolkan WD. Tanpa CST; PNG.

Aturan uji F1 sampai F3 (bagian 9 tetap berlaku): `suggest -q 5 --seed 0 --restarts 2 --pool 8192` FR-4 harus IDENTIK (md5 `c69126f3`), `smoke_test`, semua `test_gui_*` (dua kegagalan lama:
`test_gui_t1` jendela grafik di sandbox dan `test_gui_t2` bagian B, bukan dari perubahan baru), dan `report` dijalankan per desain.

#### F4 Membuat report
```
py main.py report --runs MicrostripAntena --out-dir data\_report_fr4
py main.py report --runs MicrostripAntena_RO4350B --out-dir data\_report_ro4350b
py main.py report --runs MicrostripAntena MicrostripAntena_RO4350B --out-dir data\_compare
```
Periksa: angka di bagian 3 dan 4 sama dengan `batch_lhs.csv`; cakupan pita desain terbaik dicantumkan; tidak ada klaim di luar tabel; titik referensi hypervolume sama untuk kedua substrat.
Syarat gain per run lewat `--constraint "RUN:kolom>=nilai"`.

#### F5 Dokumen deviasi dan ringkasan dosen
Tambahkan: dua fase RO4350B (angka di 13.2), cakupan pita desain final dengan angka dari kurva, penegasan bahwa dosen menerima target yang meleset, dan daftar keterbatasan di 13.2.

#### F6 Naskah laporan final (28 November)
Kerangka: (1) latar dan target proposal beserta deviasinya; (2) metode: LHS, CST, GPR, probabilitas kelayakan dan constraint, BO, region dan margin; (3) hasil FR-4 dan batas fisiknya (pilot h, kontrol tan delta);
(4) hasil RO4350B dalam dua fase; (5) Pareto, hypervolume, desain terpilih, pola radiasi dan metrik; (6) validasi: validasi maju, sensitivitas, backtest, mesh rapat, toleransi; (7) keterbatasan; (8) cara memakai alat (GUI dan CLI) dan reproduksibilitas.
Prosa akademik tanpa tanda hubung dan em dash. Setiap angka bersumber dari tabel F4.

#### F7 Dataset dan rilis
`py tools\package_dataset.py`, lalu tag `v1.0-fr4-ro4350b` setelah F8. Bila F8 tidak sempat, tag boleh dibuat tetapi catatan rilis harus jujur menyebut bahwa `run` belum diuji ulang di CST setelah refactor P1-1.

#### F8 Uji CST nyata (daftar periksa pengguna, dengan catatan hasil di PROGRESS.md)
1. `BASE_PARAMS` RO4350B terisi dan cocok dengan project CST.
2. `py main.py run --check-samples`, lalu `py main.py run --limit 1`, lalu `py main.py export`.
3. Autorun kecil: `py main.py autorun --batches 1 --qc --train --project <file.cst> -- -q 2`; periksa `auto_run_log.csv`.
4. Hentikan di tengah simulasi (tombol Hentikan dan Ctrl+C), mulai ulang, pastikan tidak ada simulasi ganda dan tidak ada proses CST yatim.
5. `py tools\test_gui_autorun.py` dan semua `test_gui_*` di Windows; catat yang gagal.

#### F9 Pemeriksaan menempel batas di autorun (opsional, menunggu persetujuan)
`--bounds-check warn|stop|off`. Di akhir tiap batch periksa sampel terbaik dan kandidat; bila sebuah parameter berada dalam 2% rentang dari batas pada sampel terbaik atau pada separuh kandidat atau lebih,
tulis pesan dan (mode stop) berhenti dengan kode 4. Autorun TIDAK melebarkan sendiri; pelebaran lewat dialog Rentang parameter lalu lanjutkan. Hanya menyentuh `autorun.py` dan `gui/commands.py`; uji dengan `mock_run`.

#### F10 Perbaikan skrip uji `test_gui_t2` (opsional)
Bagian B memakai `a.lhs_info.master` padahal `lhs_info` adalah StringVar. Ini galat di skrip uji, bukan di GUI.

#### F11 Fitur lanjutan sebelum demonstrasi (BELUM dikerjakan; di luar pembekuan 24 November karena tidak mengubah inti BO)
- **Impedansi masukan.** Simpan S11 kompleks (Re dan Im) ke folder baru `smith/` per sampel; JANGAN mengubah format `curves/` agar `curves --verify` dan data lama tetap valid. Alat `tools/export_s11_complex.py`
  untuk 2 sampai 3 desain final yang sudah ada (butuh membuka project di CST; bila hasil tidak tersimpan, simulasi ulang). Di laporan: Zin(f) = 50 (1 + S11) / (1 - S11) (Re dan Im terhadap frekuensi), Smith chart, dan impedansi di fr.
  Risiko: format ekspor S kompleks di CST belum teruji; butuh uji CST nyata.
- **Pola radiasi 3D.** Ekspor farfield 3D (theta 0 sampai 180, phi 0 sampai 360, langkah 5 derajat, sekitar 2.600 titik) hanya untuk 2 sampai 3 desain final di 3,5 GHz dan fr, bukan semua sampel (berkas besar).
  Gambar permukaan dengan matplotlib (PNG), atau tangkapan layar dari CST. Butuh CST.
- Keduanya opsional dan terpisah (mati secara bawaan atau di folder baru). Bila selesai sebelum 28 November boleh masuk laporan sebagai tambahan; bila tidak, masuk daftar pekerjaan lanjutan.

#### F12 Demonstrasi pada desain antena lain
1. Pilih antena dengan parameter dan substrat yang jelas. Sampel butuh sekitar 5 menit di CST, jadi rencanakan total simulasi (misalnya 20 LHS ditambah 3 batch x q).
2. Buat file desain dengan `tools\new_design.py`. Isi rentang awal LEBAR (pelajaran RO4350B: rentang awal yang sempit membuat BO menempel batas selama 75 sampel); persempit lewat `--region-auto` atau `--region-adapt`.
3. Buat project CST (satu project = satu RUN_NAME), lalu `lhs`, `run --check-samples`, `run --limit 1`.
4. `autorun --batches 3 --qc --train -- -q 3` (dengan `--bounds-check` bila F9 ada). Bila sebuah parameter menempel batas, lebarkan lewat dialog Rentang parameter lalu lanjutkan.
5. `report --runs <RUN_DEMO> --out-dir data\_report_<RUN_DEMO>`.
Kriteria berhasil: tidak ada perubahan pada kode inti (hanya file desain); laporan terbentuk; jumlah simulasi, waktu, dan R2 validasi silang dicatat. Jangan mengklaim optimum atau keunggulan atas metode lain.
Sebelum demonstrasi, Claude menulis `docs/panduan_desain_baru.md` (urutan perintah dan aturan rentang awal).

### 13.4 Jadwal

| Tanggal | Pekerjaan |
|---|---|
| Jumat 20 November | Rencana diperbarui (ini). F1, F2, F3 (Claude). |
| Sabtu 21 November | F4 membuat report, F5 dokumen. F8 bila ada akses CST. |
| Minggu 22 sampai Senin 23 November | Perbaikan temuan dari F4. F9 dan F10 bila disetujui. Lanjutkan F8. Kerangka F6. |
| Selasa 24 November | PEMBEKUAN FITUR: kode F1 sampai F3 (dan F9 bila dikerjakan) selesai dan lulus uji. Setelah ini hanya perbaikan galat. |
| Rabu 25 sampai Jumat 27 November | F6 naskah, F7 `package_dataset`. |
| Sabtu 28 November | Laporan final. |
| Minggu 29 sampai Senin 30 November | Cadangan, tag rilis (setelah F8). |
| Selasa 1 Desember | Tenggat. |
| Setelah laporan final | F11, lalu panduan desain baru, lalu F12. |

Gerbang keputusan: bila waktu kurang, korbankan berurutan F12, F11, F9, F10. F1 sampai F8 tidak dikorbankan. Bila F8 tidak sempat, klaim "alur bisa dipakai ulang di CST" diturunkan menjadi
"tersedia dan diuji dengan mock_run", dan itu ditulis di laporan.

### 13.5 Belum teruji dan risiko (jujur)

- Semua kode setelah paketT1 (T1, T2, G3, G4a, autorun CLI dan GUI) belum dijalankan di Windows dan belum dengan CST nyata.
- Kurva dan ff untuk F2 dibaca dari berkas yang sudah ada; bila format berkas desain lain berbeda, F2 harus dilewati dengan catatan, bukan membuat laporan gagal.
- Dugaan sebab validasi maju RO4350B yang lemah (13.2) belum diuji.
- Impedansi dan 3D (F11) bergantung pada perilaku ekspor CST yang belum pernah dicoba.
