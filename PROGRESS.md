# PROGRESS.md: status berjalan dan serah terima ke percakapan Claude lain

Diperbarui: 11 November 2026. Tenggat proyek: 1 Desember 2026; fitur baru dibekukan tujuh hari sebelumnya (24 November).
Semua angka di bawah berasal dari keluaran perintah yang sudah dijalankan (log pengguna atau uji di sandbox). Yang tidak terukur ditulis "belum".

## 1. Cara melanjutkan di Claude lain

Unggah: `CLAUDE.md`, `RENCANA_LANJUTAN.md`, file ini, dan `batch_lhs.csv` terbaru kedua run (FR-4 dan RO4350B). Zip repo hanya bila perlu mengubah kode
(kirim folder `data/` tanpa `curves/`, `eff/`, `ff/` agar ringan). Lalu tempel prompt ini:

> Baca CLAUDE.md, RENCANA_LANJUTAN.md, lalu PROGRESS.md. Patuhi aturan hemat token (jangan baca data/, jangan listing repo; baca file lewat grep atau sed).
> Lanjutkan dari bagian "Langkah berikutnya" di PROGRESS.md. Sebelum mengubah file, tunjukkan rencana singkat dan perhitungan, lalu tunggu persetujuan.
> Serahkan zip berisi file yang berubah saja, perintah PowerShell, hasil uji (termasuk regresi seed 0), dan daftar jujur yang belum teruji.

Gaya kerja yang diinginkan pengguna: Bahasa Indonesia, ringkas; alur bertahap dengan persetujuan; perhitungan ditunjukkan sebelum file diubah; gambar PNG
(bukan HTML atau SVG); tanpa tanda hubung atau em dash pada prosa akademik; tugas diselesaikan cepat dan hanya bagian yang perlu. Akses Claude ke repo
dimatikan untuk menghemat token, jadi file dan keluaran terminal dikirim lewat unggahan.

## 2. Status per tugas (RENCANA_LANJUTAN.md)

| Tugas | Status | Catatan |
|---|---|---|
| P0-1 data RO4350B | berjalan | 150 sampel; BO jalan; celah front belum terisi (bagian 3) |
| P0-2 A mesh rapat | belum | butuh CST |
| P0-2 B toleransi | kode siap | `tools/make_tolerance.py`, `tools/analyze_tolerance.py`; diuji hanya dengan data sintetik, belum dengan CST |
| P0-3 laporan dan rilis | belum | |
| P1-1 generalisasi desain | ditunda | dikorbankan lebih dulu sesuai gerbang keputusan |
| P1-2 validasi maju | selesai | `py main.py validate`; angka uji manual FR-4 terreproduksi |
| P1-3 hypervolume dan Pareto | selesai | `cstopt/report/pareto.py` |
| P1-4 sensitivitas dan aturan berhenti | belum | |
| P1-5 generator laporan | selesai | `py main.py report` |
| P2 semua | ditunda | hanya bila P0 dan P1 selesai dan ada bukti offline |
| Perbaikan `qc` | selesai | `qc --run-name RUN` kini jalan tanpa `lhs_samples.csv` |

Berkas yang sudah diserahkan: Paket A (`pareto.py`, `make_tolerance.py`, `analyze_tolerance.py`) dan Paket B (`validate.py`, `report.py`, `qc/dataset.py`,
`main.py`, `CLAUDE.md`, `PROGRESS.md`). Regresi `suggest -q 5 --seed 0 --restarts 2 --pool 8192` pada FR-4: IDENTIK dengan versi asli; `smoke_test.py`: SEMUA LULUS.

## 3. Temuan data terbaru

FR-4 (MicrostripAntena): 156 sampel, 52 memenuhi syarat dasar; front BW terhadap gain 4 titik (BW 126,2 sampai 180,6 MHz, gain 2,89 sampai 2,80 dBi);
hypervolume BW 518,5 MHz*dBi; knee sampel 91. Terbaik: sampel 137 (BW 180,6 MHz, gain 2,80 dBi, fr 3,698 GHz, hanya 2 MHz dari tepi pita 3,7).

RO4350B (MicrostripAntena_RO4350B): 150 sampel, 143 memenuhi syarat dasar; front 15 titik, BW 115,8 sampai 227,0 MHz; hypervolume BW 1217,0 dan cakupan 303,1; knee sampel 132
(BW 160,6 MHz, gain 4,95 dBi). Titik penting:

| Tujuan | Sampel | BW (MHz) | Gain (dBi) | Catatan |
|---|---|---|---|---|
| gain >= 5 dengan BW tertinggi | 145 | 150,0 | 5,13 | fr 3,694 GHz |
| gain tertinggi | 102 | 115,8 | 5,82 | |
| BW tertinggi | 149 | 227,0 | 4,40 | fr 3,572; RL minimum -15,8 dB; cakupan 56,6%; BW pecahan 6,35% |

Kemiringan trade-off dari (150 MHz; 5,13 dBi) ke (227 MHz; 4,40 dBi): sekitar -0,0095 dB per MHz. BW terbaik yang feasible: 134 MHz (id sampai 125), 181 (id 140), 227 (id 149):
ujung kanan front belum konvergen dan tidak ada sampel feasible pada BW 190 sampai 210 MHz (celah sampling, bukan fisika).

Peringatan yang harus diselesaikan sebelum angka 227 MHz masuk laporan: BW pecahan 6,35% dan cakupan 56,6% melampaui asumsi lama (menjenuh sekitar 5%, cakupan di atas 45% tidak
realistis). Mungkin nyata, mungkin dua resonansi menyatu atau artefak mesh. Narasi "BW dibatasi fisika" harus diubah menjadi "gain dikorbankan untuk BW".

BOUNDS RO4350B: pengguna mengubahnya tiga kali; nilai akhir di `designs/uslot_dgs_ro4350b.py` di komputer pengguna tidak dikirim. Usulan Claude (batas yang mentok digeser 50% lebar rentang lama):
Wp atas 38,3; LD atas 7,5; WD atas 14,0; gD atas 1,4; LU bawah 1,5; WU bawah 3,0. Pada data terbaru WD terbaik 14,0 sampai 16,4 dan LU masih menyentuh 1,5 pada setidaknya satu dari 8 desain
BW tertinggi (U-slot mungkin hampir tidak berkontribusi: hipotesis). Lebar substrat `Ws = Wp + 6*hs` mengikuti Wp otomatis (macro). Aturan geometri: `WU > 4*gU` dan `1,25 + LD <= Lp/2`.

Validasi maju (`py main.py validate`):
- FR-4, `--split 135 --max-id 155 --restarts 2`: bias fr +244,5 MHz (aktual lebih tinggi pada 18 dari 20), RMSE fr 316,2 MHz; bias BW +25,1 MHz, RMSE 27,9 MHz; PoF fr model 0,68 vs aktual 0,25
  (spesifikasi: 0,65 vs 0,25; selisih kecil karena restart GP). Mode batch berurutan (batch 5) pada FR-4: 76 sampel uji, 51 detik; bias fr +83,7 MHz, RMSE 167,4 MHz;
  PoF rata rata 0,64 vs aktual 0,68, Brier 0,173 (acuan 0,216). Jadi model cukup terkalibrasi saat interpolasi dan buruk saat ekstrapolasi (uji 135 ke 155).
- RO4350B (diuji pada 125 sampel di sandbox TANPA kurva S11, jadi `rl_band_min_db` dan PoF tidak valid; ulangi di komputer pengguna): kolom dari CSV saja: bias fr +1,5 MHz, RMSE fr 34,8 MHz
  (di pita: R2 0,95; RMSE 14,9 MHz); BW R2 0,19 dengan RMSE 23,3 MHz; gain R2 0,26 dengan RMSE 0,174 dBi.

Log pengguna yang relevan: `py main.py curves --run-name MicrostripAntena_RO4350B` KONSISTEN (125 kurva, selisih maksimum jauh di bawah batas). `status` memberi peringatan parameter menempel batas
(Wp, LU, WU, LD, WD, gD) pada 125 sampel; itu sebab BOUNDS diperlebar.

## 4. Langkah berikutnya (urut)

1. Isi celah BW. Tiap putaran: `suggest` lalu `run`; 2 ronde per tingkat; tingkat 200, lalu 190 dan 215 bila front masih berlubang.
```powershell
py main.py suggest --design uslot_dgs_ro4350b --focus gain --constraint "bw_mhz>=200" --region-auto 5:0.2 --margin fr_ghz=0.08 -q 5
py main.py run --samples data\MicrostripAntena_RO4350B\samples\bo_candidates.csv --run-name MicrostripAntena_RO4350B --auto-yes
```
2. Periksa kurva S11 dan jalankan mesh rapat (P0-2 A) untuk sampel 149, 140, 132; bila selisih fr < 10 MHz dan BW < 5%, angka boleh dipakai.
3. Hentikan BO. Pilih 3 desain final RO4350B: (A) gain >= 5 dengan BW tertinggi (sekitar sampel 145), (B) knee (sampel 132), (C) BW tertinggi. Pilih yang tidak menempel batas geometri.
4. Toleransi desain final (butuh CST):
```powershell
py tools\make_tolerance.py --run MicrostripAntena_RO4350B --sample <ID> --plan oat
py main.py run --run-name MicrostripAntena_RO4350B_tol --samples data\MicrostripAntena_RO4350B_tol\samples\tol_oat_s<ID>.csv --auto-yes
py tools\make_tolerance.py --run MicrostripAntena_RO4350B --sample <ID> --plan corners random
py main.py run --run-name MicrostripAntena_RO4350B_tol --samples data\MicrostripAntena_RO4350B_tol\samples\tol_corners+random_s<ID>.csv --auto-yes
py tools\analyze_tolerance.py --run MicrostripAntena_RO4350B
```
   Jalankan corners setelah OAT selesai (tanda tiap parameter diambil dari hasil OAT).
5. Setelah data lengkap: `py main.py validate --design uslot_dgs_ro4350b --restarts 2` dan `py main.py train` dan `py main.py backtest`, lalu
```powershell
py main.py pareto
py main.py report --constraint "MicrostripAntena_RO4350B:gain_fr_ieee_dbi>=5.0" --constraint "MicrostripAntena_RO4350B:gain_fr_ieee_dbi>=4.0"
```
6. Opsional: satu atau dua ronde FR-4 `--focus gain --constraint "bw_mhz>=150"` (front FR-4 hanya 4 titik; peringatan akan muncul di laporan bila tidak ditambah).
7. Naskah: ringkasan satu halaman untuk dosen, laporan, bagian "Deviasi dari proposal"; perbarui `CLAUDE.md` bagian 5 dan 6 di akhir tiap sesi.

## 5. Keputusan dan asumsi yang perlu diingat

- Toleransi bawaan: Lp, Wp, LI +/-0,1 mm; gU, gD +/-0,05 mm (batas bawah celah 0,2 mm, `--gap-min`); hs +/-10% dengan `Wf` dihitung ulang (`--keep-wf` menahan `Wf` tetap, lebih dekat ke kenyataan etsa). Epsilon tidak ditoleransi (butuh parameter CST baru, belum terbukti diterima).
- Skenario toleransi yang melanggar aturan geometri dilewati dan dicatat di berkas `_meta.csv` (bukan dikirim ke CST). Pada uji sampel 112 (menempel batas), 5 dari 24 skenario dan 3 dari 4 corners terlewati:
  `gU + 0,05` melanggar `WU > 4*gU`, dan `LI + 0,1` melanggar jarak U-slot ke inset. Pilih desain final yang punya ruang geometri. `--keep-invalid` memaksa menulis barisnya, tetapi `run` bisa menolaknya.
- Yield dihitung terpisah per plan; hanya plan random yang mendekati yield statistik, dan dengan 12 sampel galat bakunya sekitar 14 poin persen. OAT dan corners adalah kasus terburuk, bukan peluang. Syarat BW default: 90% BW nominal.
- `validate` memakai kolom objective dan constraint tahap atau fokus aktif, dan tidak mengubah `suggest`. Saran `--margin` bisa sangat besar bila model buruk di ekstrapolasi (FR-4 split 135: fr 0,5 GHz); itu sinyal untuk mempersempit region, bukan untuk dipakai apa adanya.
- `report` memilih desain terbaik langsung dari CSV (fr di pita, RL minimum <= -10 dB, constraint tambahan), konsisten dengan `pareto`; overlay S11 butuh `curves/s11_sample{id}.csv`.

## 6. Belum teruji (jujur)

- Seluruh jalur CST nyata untuk toleransi: `run --run-name ..._tol` dengan kolom `hs` dan `Wf`, dan alur `corners` berbasis OAT. Alat toleransi hanya diuji dengan data sintetik buatan Claude.
- `validate` dan `report` pada RO4350B dengan kurva lengkap (di sandbox kurva RO hanya ada sampai id 35); GUI Windows tidak disentuh.
- Mesh rapat (P0-2 A) belum direncanakan atau dijalankan.
- Nilai BOUNDS akhir RO4350B dan apakah front BW di atas 200 MHz bertahan setelah verifikasi mesh.

## 7. Jangan menulis di laporan

Angka yang bukan dari tabel hasil; klaim kebaruan analisis toleransi (topik mapan); "BW dibatasi fisika" untuk RO4350B (bertentangan dengan BW 227 MHz pada gain 4,40 dBi);
klaim BW 227 MHz sebelum verifikasi S11 dan mesh; yield dari OAT atau corners sebagai peluang.
