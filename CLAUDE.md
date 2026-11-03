# CLAUDE.md: konteks proyek dan aturan kerja

Baca file ini dulu di setiap percakapan baru. Perbarui bagian 5 dan 6 di akhir sesi (lihat bagian 9).
Rincian hasil ada di `docs/` (progres_fr4.md, pilot_h.md, kontrol_tand.md, substrat_ro4350b.md); baca hanya bila perlu.

## 0. Aturan hemat token (wajib)

- Jangan membuka halaman GitHub repo atau menjelajah repo luas lewat konektor. Repo memuat ratusan berkas data; satu listing saja mahal.
- Jangan membaca isi `data/` (curves/, eff/, ff/ berisi ratusan berkas). Hampir semua tugas tidak butuh itu. Bila perlu angka, minta pengguna
  mengunggah `batch_lhs.csv`, baca dengan pandas (`usecols`), dan tampilkan ringkasan (head, describe), bukan seluruh isi.
- Daftar kode: `git ls-files | grep -v "^data/"`. Baca bagian yang perlu saja (`grep -n`, `sed -n 'a,bp'`). Ukuran kira kira: `ml/core.py` 500 baris,
  `cst/batch.py` 450, `cst/export.py` 350, `gui/app.py` 450. Jangan memuat seluruh file untuk perubahan kecil.
- Batasi keluaran tool (`| head -20`, `| tail`, `grep`). Jangan mencetak CSV atau log penuh. Ringkas hasilnya sendiri.
- Gunakan angka di bagian 5; jangan mengulang analisis yang sudah ada. Status proyek: `py main.py status`, bukan memuat data.
- Ubah file dengan patch string-replace, dan serahkan zip berisi HANYA file yang berubah (bukan seluruh repo).
- Jawaban ringkas, jangan menyalin isi file ke jawaban, paling banyak satu pertanyaan per giliran.
- Tugas besar (lebih dari sekitar 5 file atau banyak uji): sampaikan rencana singkat dan minta persetujuan dulu.
- Uji ML cepat: `--restarts 2 --pool 8192`. Pelatihan penuh memakan puluhan detik sampai menit.

## 1. Pengguna dan preferensi

- Arya, mahasiswa S1 Fisika (UNESA), magang riset dengan mitra ITS. Bahasa percakapan: Indonesia. Pengguna Windows (PowerShell), venv `cst_env`, CST Studio Suite 2024.
- Gaya: ringkas; alur bertahap dengan persetujuan; tunjukkan perhitungan sebelum mengubah file; gambar PNG (bukan HTML/SVG);
  prosa akademik (laporan, naskah) tanpa tanda hubung dan em dash.
- Dosen tidak ketat soal isi proposal selama hasil akhir bagus; yang terpenting metode ML dan alurnya bisa dipakai ulang untuk desain lain.
  Proposal ditulis dengan keputusan yang longgar, jadi target boleh dikoreksi bila bukti menunjukkan tidak tercapai, asalkan dilaporkan terbuka.
- Tenggat akhir: 1 Desember 2026 (sudah diperpanjang dari 18 Oktober).

## 2. Tujuan dan target proposal

Optimasi antena mikrostrip U-Slot + DGS Dumbbell untuk 5G Sub-6 GHz dengan LHS, simulasi CST, surrogate GPR, dan Constrained BO (EI x PoF).
Target proposal: fr 3,3 sampai 3,7 GHz, RL minimum <= -10 dB, BW >= 200 MHz, gain >= 5 dBi (ideal 6), R2 model >= 0,85.
Catatan: proposal ambigu soal BW (>= 200 MHz di mana saja dalam pita, atau cakupan penuh 3,3 sampai 3,7 GHz). 11 parameter geometri:
Lp Wp LU WU gU PU LI LD WD gD PD. Substrat awal FR-4 (er 4,3, tan d 0,025, h 1,6 mm).

## 3. Repo dan perintah

Repo: github.com/Eriec0/CST-Auto_testing. Satu pintu masuk `py main.py` (GUI tkinter bila tanpa argumen). Struktur:
`main.py`; `designs/` (satu file per desain atau substrat: parameter, BOUNDS, aturan geometri, STAGES, FOCI); `cstopt/` (paths, loader, status,
`sampling/lhs.py`, `cst/` batch, export, farfield, dialog_watcher, `ml/` core, train, suggest, backtest, `qc/`, `gui/`); `data/<RUN>/` (batch_lhs.csv,
curves/ eff/ ff/, samples/, models/, figures/); `macros/` (VBA, setup terpisah); `cst_projects/`; `tools/`; `docs/`.

| Perintah | Fungsi |
|---|---|
| `py main.py status` | ringkasan (sampel, tahap BO, terbaik, peringatan batas) |
| `lhs`, `run`, `qc`, `curves`, `train`, `suggest`, `backtest` | tahap alur; opsi: `-h` |
| `run` (butuh CST) | `--samples CSV --auto-yes --limit N --run-name NAMA`; kolom hs/Wf/lossTan di CSV otomatis jadi parameter ekstra |
| `suggest` | `-q 5 --seed 0 --restarts 2 --pool 8192`; opsi lanjutan: `--focus --constraint --region --region-auto --margin --calibrate --composite` |
| `tools/make_seeds.py`, `tools/wf50.py`, `tools/smoke_test.py` | seed antar substrat; Wf 50 ohm; uji instalasi |

Satu project CST = satu `RUN_NAME` = satu folder `data/<RUN>/`. Desain dipilih dengan `--design nama` (tanpa .py), bawaan `uslot_dgs_fr4`.
BO: tahap otomatis (Tahap 1 minimalkan rl_band_min_db sampai ada sampel feasible, lalu Tahap 2 maksimalkan bw_mhz); atau fokus manual dari `FOCI`.

## 4. Riwayat singkat

1. Awal: kode CST + ML masih berantakan; perbaikan BO dua tahap, fitur dip, `BOUNDS` diperlebar bertahap, peringatan parameter menempel batas.
2. Restruktur repo ke tata letak di atas (PR sudah di-merge ke main): satu `main.py`, GUI, paket `cstopt/`, `designs/`, `data/<RUN>/`, skrip migrasi.
3. Hasil FR-4 (155 sampel) dan diagnosis: target tidak tercapai; bukti batas fisik (bagian 5).
4. Pilot ketebalan h (8 simulasi) dan kontrol tan d (7 simulasi) lewat parameter CST ekstra.
5. Revisi BO v2 (region, margin, kalibrasi, komposit, fokus) dan desain Rogers RO4350B.

## 5. Temuan (angka acuan)

- FR-4 h = 1,6 mm, 155 sampel: terbaik di dalam pita: sampel 137 (fr 3,698 GHz, RL -18,2 dB, BW 180,6 MHz, gain 2,80 dBi); sampel 139 lebih aman
  (fr 3,682, BW 178,1). Maksimum seluruh data: gain 3,13 dBi, eta 0,511, cakupan pita 38,9% (sampel 120). BO vs LHS: 0 dari 80 vs 52 dari 70 feasible.
- BW dan fr naik bersamaan (mengecilkan Lp, melebarkan WD); BW pecahan menjenuh sekitar 5%; BW 200 MHz butuh 5,4 sampai 5,7%. Melonggarkan batas fr
  sampai 3,9 GHz hanya memberi 195 MHz. Gain 5 dBi butuh eta sekitar 0,67 padahal maksimum 0,51.
- Model fr bias +245 MHz pada 20 sampel BO baru (prediksi 20/20 di pita, kenyataan 5/20); R2 validasi silang: BW 0,94 sampai 0,96, RL 0,82 sampai 0,88,
  fr 0,65 sampai 0,69, gain 0,27 sampai 0,5 (komposit D + 10 log eta: 0,61). Parameterisasi skala+bentuk tidak membantu. Kalibrasi std dari validasi silang
  tidak mengubah apa pun (pengali 1,00); yang membantu adalah margin dan region.
- Desain BW terbaik hanya mencakup 23 sampai 37% pita (S11 di 3,5 GHz hanya -4 sampai -7 dB) karena BW absolut mendorong resonansi ke tepi atas.
- Pilot h (geometri tetap, Wf = 1,945 h): BW naik maksimum 5 sampai 6% lalu turun, eta turun sekitar 10%, gain datar, fr naik; keputusan tetap h = 1,6 mm.
- Kontrol tan d (0,025 ke 0,001): eta 0,47 ke 0,82, gain 2,77 ke 5,23 dBi, tetapi BW 150 MHz ke 0 (RL min -20,5 ke -9,8 dB, geometri tidak dicocokkan ulang).
  Jadi ada trade-off BW dan gain; BW 200 MHz dan gain 5 dBi sekaligus kemungkinan besar tidak bisa dengan topologi ini pada h 1,6 mm.
- Uji reproduksi: kontrol h = 1,6 dan tan d = 0,025 identik dengan data asli (CST deterministik, bisa dipercaya).

## 6. Keputusan dan langkah berikutnya

Keputusan: tetap FR-4 h = 1,6 mm untuk hasil FR-4; substrat kedua Rogers RO4350B dari material library CST (project terpisah
`MicrostripAntena_RO4350B`, desain `uslot_dgs_ro4350b`, seed dari FR-4 diskalakan sqrt(eeff)); hasil utama = kurva Pareto BW vs gain untuk dua substrat
lewat fokus (`--focus bw --constraint "gain_fr_ieee_dbi>=4.5"`, dst.), selalu bersama `--region-auto` dan `--margin fr_ghz=0.08`.

Status (perbarui!): paket BO v2 + desain RO4350B + `docs/substrat_ro4350b.md` sudah dibuat; belum dijalankan oleh pengguna.
Berikutnya: (a) pengguna menyiapkan project RO4350B di CST dan melaporkan epsilon dan tan d dari library (desain mengasumsikan 3,66 dan 0,0037; ubah
`SUBSTRATE` bila beda); (b) seed dan putaran BO RO4350B (sekitar 40 sampai 60 simulasi); (c) fokus Pareto; (d) validasi mesh rapat dan toleransi
+-0,1 mm pada desain akhir; (e) gambar Pareto FR-4 dari 155 sampel (belum dibuat) dan ringkasan satu halaman untuk dosen (belum dibuat);
(f) laporan dan naskah; (g) perbarui `docs/progres_fr4.md` dengan hasil akhir.
Cabang git: restruktur sudah di-merge; pilot-h dan control-tand dibuat bertumpuk; paket BO v2 di cabang bo-v2. Cek `git branch -a` dan `git log --oneline -8`.

## 7. Jebakan dan catatan teknis

- Nama parameter CST `tand` DITOLAK (bentrok nama objek VBA). Loss tangent memakai `lossTan` (alternatif `dLoss`, `tanDelta`, `tdelta`; nama kolom CSV harus sama).
- `Wf` 50 ohm = Hammerstad (`tools/wf50.py`); 3,11 mm untuk FR-4 h 1,6; sekitar 3,34 mm untuk RO4350B h 1,524.
- Kolom hs/Wf/lossTan di CSV sampel otomatis dipakai sebagai parameter ekstra; tanpa deteksi kolom itu akan diabaikan dan sampel dianggap duplikat.
- `batch.py` mengembalikan model ke baseline di akhir (geometri baseline FR-4; ekstra ke nilai tetap `BASE_EXTRA`).
- Prediksi cakupan pita di atas sekitar 45% tidak realistis (BW pecahan sekitar 5%); fokus gain dan cakupan tanpa region menghasilkan ekstrapolasi GP ekstrem.
- Opsi lanjutan BO mati secara bawaan: `suggest` tanpa opsi harus identik dengan versi sebelumnya (uji dengan `tools/compare_csv.py`, seed 0).
- `bo_suggest.py` lama menyebut `batch_trial_LHS.py`; nama yang benar `py main.py run`.

## 8. Cara bekerja dan menguji di sandbox

- Sandbox: `/bin/sh` tanpa brace expansion (tulis jalur satu per satu atau `bash -c`). Pasang `python3-tk` dan pakai `xvfb-run` untuk menguji GUI (tangkap layar dengan
  `PIL.ImageGrab(xdisplay=...)`). CST tidak ada; uji logika `run` dengan modul tiruan `cst` (paket kosong berisi `results.py` dan `interface.py` dengan `DesignEnvironment`).
- Alur patch: salin repo ke folder kerja, ubah, uji pada data asli (regresi seed 0, uji tiap opsi baru, uji GUI), buat zip berisi file berubah saja, berikan perintah
  PowerShell (`Expand-Archive -Path ... -DestinationPath . -Force`, branch baru, commit) dan nyatakan terus terang apa yang belum teruji (terutama CST nyata).
- Dataset 155 sampel terbaru ada di komputer pengguna; minta unggahan `batch_lhs.csv` bila perlu. Simpan keluaran kecil, jangan data mentah.

## 9. Memperbarui file ini

Di akhir sesi: perbarui bagian 5 (temuan baru, singkat) dan bagian 6 (status dan langkah berikutnya); tambahkan jebakan baru di bagian 7. Jaga file ini di bawah
sekitar 200 baris; pindahkan rincian panjang ke `docs/`.
