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
