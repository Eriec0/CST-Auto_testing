# Demonstrasi alat pada antena lain (lewat GUI): patch FR-4 berbentuk E, pita 2,4 sampai 2,6 GHz

Tujuan: menunjukkan bahwa alat bisa dipakai pada antena yang geometrinya berbeda tanpa mengubah kode inti. Yang berbeda hanya dua berkas:
`designs/eshape_fr4.py` (parameter, rentang, aturan geometri, pita, target) dan `macros/eshape_fr4.bas` (model CST). Semua langkah sesudah persiapan memakai GUI.

Yang boleh diklaim: alur LHS, simulasi, QC, model GPR, BO, dan laporan berjalan pada geometri lain hanya dengan file desain dan macro baru.
Yang TIDAK boleh diklaim: bahwa hasilnya optimum, bahwa BO lebih baik dari metode lain, atau bahwa nilai awal macro sudah resonan di pita (itu perkiraan dari rumus patch, belum disimulasikan).

Geometri: patch persegi panjang FR-4 (er 4,3; tan delta 0,025; h 1,6 mm) dengan dua slot sejajar yang terbuka di tepi y = Lp, umpan inset di tepi y = 0.
Parameter BO (6): `Lp`, `Wp` (ukuran patch), `Lsl`, `Wsl` (panjang dan lebar tiap slot), `Dsl` (jarak pusat slot dari sumbu), `LI` (kedalaman inset).
Tetap: hs = 1,6 mm, Wf = 3,11 mm (saluran 50 ohm, impedansi hitungan 50,3 ohm), gI = 1 mm, Lf = 10 mm.

## Alur setelah macro dijalankan

```
macro (model di CST) -> simpan project -> GUI: pilih desain -> tab 1 bangkitkan LHS
   -> tab 2 simulasi: uji 1 sampel, lalu semua -> tab 3 QC -> tab 7 lihat data
   -> tab 4 latih GPR (untuk memeriksa model) -> tab 5 BO: Usulkan kandidat -> simulasikan -> ulangi, atau Auto run
   -> tab 6 laporan
```
- LHS dulu: BO butuh data awal yang tersebar. Sampel LHS adalah "sampel awal" (jumlahnya sama dengan `N_INITIAL` di file desain: 60 bawaan sekarang, 16 cukup untuk versi cepat); semua sampel berikutnya adalah hasil BO. Bila jumlah LHS yang Anda bangkitkan berbeda dari `N_INITIAL`, ubah `N_INITIAL` di `designs/eshape_fr4.py` agar status tidak menghitung sampel LHS sebagai hasil BO.
- Latih GPR (tab 4) BUKAN prasyarat BO: `Usulkan kandidat` dan Auto run melatih model sendiri tiap dipanggil. Tab 4 dipakai untuk melihat seberapa baik model (R2 dan parity) dan untuk memantau.
- Satu putaran BO = Usulkan kandidat (q sampel) -> Pakai kandidat di tab 2 -> Jalankan batch -> data bertambah -> ulangi. Auto run mengerjakan putaran ini otomatis N kali.
- Mulai BO setelah semua sampel LHS selesai. Dengan data sedikit model masih kasar; itu wajar.

## Target dan kriteria desain bagus

Pesan dosen: untuk mencari desain yang bagus, lihat RL saja. Jadi untuk demonstrasi ini:

- **Kriteria utama: RL minimum paling negatif (S11 terdalam), dengan resonansi di dalam pita 2,4 sampai 2,6 GHz.** Di BO ini adalah fokus `match` (objective `rl_band_min_db`, diminimalkan, dengan syarat fr di pita dan directivity di fr minimal 4 dBi).
- Cara membaca RL: lebih negatif dari -10 dB berarti cocok (ambang bandwidth); sekitar -20 dB baik; -30 dB sudah sangat baik. Nilai di bawah sekitar -40 dB biasanya hanya berarti satu frekuensi pas sekali dan peka terhadap simulasi serta toleransi.
- Peringatan dari data Anda sendiri: pada RO4350B, mengurutkan hanya dengan RL memilih sampel 34 (RL -61,9 dB, tetapi BW hanya 98,6 MHz), sedangkan sampel 180 punya RL -26,4 dB dengan BW 228 MHz. RL terdalam tidak menjamin pita lebar,
  jadi laporan tetap mencantumkan fr, BW, dan gain di samping RL.
- Target sekunder (hanya dilaporkan, bukan syarat memilih): BW 100 MHz dan gain 3 dBi, diambil dari `CST` di file desain. Angka ini perkiraan konservatif untuk patch FR-4 berloss; ubah bersama pembimbing.

## Perkiraan waktu

Satu sampel sekitar 4 menit di mesin Anda untuk antena sebelumnya; antena ini belum diukur, jadi ukur dari sampel pertama.
Bila 4 menit: 16 sampel LHS sekitar 65 menit (60 sampel sekitar 4 jam), dua batch auto run (6 sampel) sekitar 25 menit ditambah beberapa menit untuk suggest dan latih model per batch. Total sekitar 2 jam.

## 0. Persiapan (sekali, di luar GUI)

1. Pasang paket demonstrasi di folder repo (`Expand-Archive ... -Force`), lalu `py tools\smoke_test.py` dan `py tools\test_demo_design.py` harus SEMUA LULUS.
2. Di CST buat project baru dengan cara yang sama seperti Anda dulu menjalankan `macros\uslot_dgs_dumbbell_v4.bas`: buka macro `macros\eshape_fr4.bas` dan jalankan. Macro HANYA menggambar model (`RUN_SIM = False`) dan tidak menjalankan solver.
   Jendela peringatan geometri tidak boleh muncul pada nilai awal.
3. Periksa daftar parameter CST: harus ada `hs, tc, Wf, Lf, gI, Lp, Wp, Lsl, Wsl, Dsl, LI, Wsub` dengan nilai awal 1.6, 0.035, 3.11, 10, 1.0, 27.0, 38.0, 12.0, 2.0, 9.0, 7.0 dan Wsub = Wp+6*hs. Model berbentuk patch dengan dua slot yang terbuka di sisi atas.
4. Simpan sebagai `cst_projects\MicrostripAntena_EShape.cst`. Nama project HARUS sama dengan `RUN_NAME` di file desain (`MicrostripAntena_EShape`). Biarkan project terbuka di CST.

## 1. Jalankan GUI dan pilih desain

`py main.py`. Di kotak Desain (kiri atas) pilih `eshape_fr4`. Bila tidak ada di daftar, tutup GUI dan buka lagi (daftar dibaca saat GUI dimulai).
Baris status di atas harus menunjukkan desain `eshape_fr4` dengan 0 sampel.

## 2. Tab 1 Sampel LHS

1. Isi jumlah sampel sama dengan `N_INITIAL` di file desain (60 bawaan; 16 untuk versi cepat setelah mengubah `N_INITIAL`) dan seed 1.
2. Tekan Bangkitkan sampel. Log harus menyebut fraksi kandidat yang lolos aturan geometri (sekitar 80%) dan "semua valid".
3. Lihat kotak Rentang parameter aktif: enam parameter dengan rentang lebar (lihat bagian Mengubah parameter).

## 3. Tab 2 Simulasi CST

1. Di kolom project tekan Pilih... dan pilih `cst_projects\MicrostripAntena_EShape.cst`. Kolom berkas sampel dikosongkan (memakai `lhs_samples.csv`).
2. Tekan Cek koneksi. (Pilih project dulu sebelum Cek sampel dan Jalankan batch: desain dipilih dari nama project, bukan dari kotak Desain.) Harus tertulis terhubung ke CST dan semua method tersedia. Di log baris `Substrat di project: hs = 1.6 mm, Wf = 3.11 mm` TIDAK boleh disertai `[PERINGATAN]`.
3. Tekan Cek sampel. Harus menyebut semua sampel lolos check_geometry.
4. UJI SATU SAMPEL dulu: isi batas jumlah 1, centang tekan Yes otomatis (`--auto-yes`), tekan Jalankan batch. Catat waktu solver dan hasil di log (fr, RL, BW, gain).
   Bila fr sampel ini jauh di luar 1,5 sampai 3,5 GHz atau hasilnya tidak masuk akal, berhenti dan periksa model sebelum lanjut.
5. Kosongkan batas jumlah dan tekan Jalankan batch untuk sampel yang tersisa (sampel yang sudah ada dilewati). Tombol Hentikan bisa dipakai kapan saja; menjalankan lagi akan melanjutkan.

## 4. Tab 3 Data dan QC

Tekan QC dataset: harus berakhir "Semua pemeriksaan lulus" (QC memakai pita, monitor, dan ambang BW dari file desain). Tekan Verifikasi kurva S11. Panel Ringkasan data menunjukkan jumlah sampel dan sebaran fr.

## 5. Tab 7 Data (lihat datanya)

Pilih grafik kurva S11 beberapa sampel (resonansi dan pita 2,4 sampai 2,6 GHz harus tampak), grafik sebar fr terhadap RL, dan koordinat paralel. Ini juga cara memeriksa apakah sebagian sampel awal sudah resonan di pita.

## 6. Tab 4 Model GPR

Tekan Latih dan evaluasi, lalu Lihat parity. Catat R2 cross validation tiap target. Dengan sampel sedikit (16) dan 6 parameter R2 bisa rendah; dengan 60 sampel seharusnya lebih baik; itu hasil jujur untuk data sedikit, bukan galat alat.

## 7. Tab 5 Optimasi BO (kriteria RL)

1. Jumlah kandidat 3. Buka Opsi lanjutan dan atur Fokus = `match` (kriteria RL; "otomatis" akan pindah ke tahap BW setelah ada sampel yang memenuhi syarat, itu bukan yang dosen minta). Opsi lain kosong.
2. Tekan Usulkan kandidat: tabel menampilkan 3 kandidat. Periksa kandidat tidak menempel batas rentang (bila banyak, lihat Mengubah parameter).
3. Baris Auto run: batch 2, centang QC dan Latih GPR, Batas rentang: peringatkan. Tekan Mulai auto run; dialog estimasi menampilkan (2 x 3 + sampel menunggu) x 5 menit; setujui.
   Semua opsi tab 5 dibaca saat Mulai lalu dikunci; label menunjukkan "Batch i/2: simulasi (n/m sampel)". Tombol Hentikan tersedia.
4. Setelah selesai label menunjukkan Selesai 2 batch. Bila muncul "Peringatan: ... menempel batas rentang", lebarkan parameter itu lewat Rentang parameter... bila masuk akal secara fisik, lalu jalankan Auto run lagi.
   `data\MicrostripAntena_EShape\auto_run_log.csv` mencatat sampel, jumlah feasible, dan nilai terbaik tiap batch.

## 8. Tab 6 Hasil (kriteria RL)

Laporan untuk: Desain terpilih. Fokus: `rl`. Tekan Buat laporan, lalu Buka folder laporan (`data\_report_MicrostripAntena_EShape`). Laporan hanya memuat antena ini, dan "Desain dengan RL terdalam" adalah desain fisibel dengan RL minimum paling negatif.
Kurva Pareto di laporan tetap BW terhadap gain (bukan RL); fokus rl menentukan desain terpilih di bagian 3, 4, dan 9. Tidak ada data toleransi untuk antena ini, jadi desain rekomendasi tidak dibuat; itu wajar.
Kolom constraint di tab 6 memakai pemisah titik koma dan bentuk `RUN:kolom>=nilai`, misalnya `MicrostripAntena_EShape:bw_mhz>=100` untuk membuat skenario kedua.

## Opsi BO di tab 5: kapan memakai apa

Semua opsi ini ada di Opsi lanjutan, kosong berarti perilaku bawaan, dan semuanya sudah divalidasi sebelum dijalankan (angka salah ditolak dengan pesan).

| Opsi | Artinya | Contoh untuk antena ini |
|---|---|---|
| Fokus | objective BO. `otomatis` = tahap 1 (RL di pita), pindah ke tahap 2 (BW) bila sudah ada sampel yang fr di pita, RL <= -10 dB, directivity >= 4 dBi. `match` = RL di pita saja. `bw` = BW terbesar. `cover` = cakupan pita. `gain` = gain terbesar dengan BW >= 100 MHz | kriteria dosen: `match` |
| Constraint | syarat tambahan pada fokus, bentuk `kolom>=nilai` atau `kolom<=nilai`, beberapa dipisah koma | `d_peak_fr_dbi>=5` (menjaga directivity); `bw_mhz>=100` (RL terdalam tetapi pita tidak sempit) |
| Margin | memperketat constraint hanya saat menghitung peluang lolos (PoF), supaya kandidat tidak menempel tepi pita | `fr_ghz=0.03` (resonansi tidak terlalu dekat 2,4 atau 2,6 GHz) |
| Sweep | menyapu batas sebuah constraint merata dari LO ke HI, satu batas per kandidat dalam satu batch; butuh Fokus dan kolomnya harus constraint aktif | Fokus `match`, Constraint `bw_mhz>=60`, Sweep `bw_mhz=60:140`: tiap kandidat mengejar RL terdalam pada syarat BW berbeda, menunjukkan trade off RL dan BW |
| Region | membatasi pencarian ke kotak yang lebih kecil, bentuk `Lp=24:28,Wp=34:40` | setelah beberapa batch, bila RL terbaik terkumpul di wilayah sempit |
| Region otomatis | kotak di sekitar K desain terbaik, diperlebar M kali lebar rentang, bentuk `K:M` | `6:0.15` |
| Region adaptif | kotak otomatis yang menyusut atau membesar menurut kemajuan antar putaran (disimpan di `samples\region_state.json`) | dipakai pada Auto run beberapa batch; manfaat belum terbukti pada data FR-4 |
| Diversity | menghukum kandidat yang terlalu berdekatan dalam satu batch | `0.4` bila kandidat mengelompok |
| Kalibrasi std, gain komposit | penyetelan model; biarkan bawaan | |

Urutan pakai yang disarankan untuk demonstrasi: batch pertama tanpa opsi apa pun selain Fokus `match`; tambahkan Constraint bila RL terbaik didapat dengan BW sempit; Sweep bila ingin melihat trade off; Region hanya setelah data cukup (lebih dari sekitar 25 sampel).

## Mengubah parameter

- **Rentang parameter (min dan max):** tab 5, tombol Rentang parameter... Dialog menampilkan rentang efektif tiap parameter, menandai yang menempel batas, dan mengusulkan pelebaran. Ubah nilai lalu simpan; perubahan tercatat di `data\MicrostripAntena_EShape\bounds_override.json`
  dan dipakai LHS dan BO berikutnya. Tombol reset mengembalikan ke rentang file desain. Dialog dikunci saat Auto run berjalan (suggest membaca rentang tiap batch).
  Memperlebar rentang aman (sampel lama tetap valid). Mempersempit diperbolehkan, tetapi akan ada peringatan jumlah sampel yang sudah ada berada di luar rentang baru.
- **Pita, target, aturan geometri, parameter baru:** bukan dari GUI. Ubah `designs/eshape_fr4.py` (`BAND_GHZ`, blok `CST`, `geometry_problems`) dan, bila menyangkut model, `macros/eshape_fr4.bas`; jaga keduanya konsisten lewat `py tools\test_demo_design.py`; lalu tutup dan buka GUI lagi.
  Mengubah pita atau monitor berarti hasil lama tidak sebanding; gunakan RUN_NAME baru.

## 9. Lembar catatan (isi saat berjalan)

| Catatan | Nilai |
|---|---|
| Tanggal, mesin, versi CST | |
| Waktu per sampel (menit) | |
| Jumlah simulasi total (LHS + BO) | |
| Sampel dengan fr di pita 2,4 sampai 2,6 GHz | |
| RL minimum terbaik (dB), fr, BW, gain pada desain itu | |
| RL terbaik dari sampel LHS, dan RL terbaik setelah BO | |
| R2 cross validation (fr, rl_min_db, bw_mhz) | |
| Opsi tab 5 yang dipakai | |
| Peringatan menempel batas (parameter) | |
| Masalah, galat, atau kejutan | |
| Apakah ada berkas kode inti yang harus diubah (harus: tidak) | |

Kriteria berhasil alat: tidak ada kode inti yang diubah; seluruh alur 2 sampai 8 dijalankan lewat GUI tanpa perintah CLI; laporan terbentuk; lembar catatan terisi.
Kriteria berhasil antena (opsional, bukan syarat): RL terbaik setelah BO lebih negatif daripada RL terbaik dari sampel LHS, dengan fr di pita.

## 10. Pembersihan

Hapus `data\MicrostripAntena_EShape` dan `data\_report_MicrostripAntena_EShape` bila tidak ingin ikut paket dataset (`package_dataset` menyertakan semua folder run di `data\`). Simpan salinan bila ingin dijadikan lampiran.
Jangan menaruh demonstrasi ini di tag rilis `v1.0-fr4-ro4350b` kecuali sengaja.

## Catatan

- Rentang parameter sengaja lebar. Pada RO4350B, rentang awal yang sempit membuat BO menempel batas selama puluhan sampel. Bila sebuah parameter menempel batas, lebarkan lewat dialog Rentang parameter (autorun tidak melebarkan sendiri).
- Nilai awal di macro hanya perkiraan dari rumus patch standar pada 2,45 GHz (panjang efektif diperpanjang oleh slot). Bila resonansi awal berada jauh dari pita, itu bukan kesalahan alat; BO tahap 1 mengejar RL terbaik di pita.
- Yang belum diuji di sini: macro di CST nyata, GUI di Windows untuk desain ini, dan waktu simulasi antena ini. `tools\test_demo_design.py` hanya memeriksa kesesuaian teks macro dengan file desain; alur tanpa CST sudah dicoba dengan `tools\mock_run.py` (respons buatan, bukan fisika antena).
- Bila macro menghasilkan galat VBA atau model tidak sesuai gambaran, kirim pesan galat dan tangkapan layar model; jangan mengubah file desain sebelum macro benar.
