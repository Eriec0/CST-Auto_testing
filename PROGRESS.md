# PROGRESS.md: status berjalan dan serah terima ke percakapan Claude lain

Diperbarui: 16 November 2026. Sisa waktu per tanggal ini: 8 hari sampai pembekuan fitur (24 November), 12 hari sampai laporan final (28 November), 15 hari sampai tenggat (1 Desember). Tenggat proyek: 1 Desember 2026; fitur baru dibekukan tujuh hari sebelumnya (24 November).
Semua angka di bawah berasal dari keluaran perintah yang sudah dijalankan (log pengguna atau uji di sandbox). Yang tidak terukur ditulis "belum".

## 0. Sedang dikerjakan (Claude memperbarui bagian ini SEBELUM menulis kode dan setelah tiap tahap)

- **P2-4 `--region-adapt` (16 Nov 2026): SELESAI (kode dan uji sandbox), paketO.zip. Hasil: aman dan bergerak masuk akal, tetapi manfaat TIDAK terbukti (replay kurang berdaya). Keputusan adopsi ada pada pengguna; opsi mati secara bawaan.**
  File: `cstopt/ml/core.py` (`region_adapt`), `cstopt/ml/suggest.py` (`--region-adapt`, `samples/region_state.json`, saling eksklusif dengan `--region` dan `--region-auto`), `cstopt/ml/backtest.py` (`--region-adapt`, `--region-auto K:M`, `--adapt-every 5`; keluaran `figures/bo_backtest_region_*.png` dan `models/backtest_region_*.csv`).
  Aturan: pusat = terbaik feasible; sisi awal 0,3 x lebar BOUNDS; 2 sukses berturut-turut sisi x 1,5 (maks 0,8); 3 gagal berturut-turut sisi / 2 (min 0,05); eps = `--xi` x std objective; pembaruan hanya bila ada sampel baru; tidak ada hitungan gagal selama belum ada feasible; reset bila tahap/fokus/constraint berubah.
  Uji (sandbox): `suggest` seed 0 FR-4 tanpa opsi IDENTIK dan tidak membuat file keadaan; `--region-adapt` dua kali tanpa data baru: keadaan dan kandidat identik; kombinasi dengan `--region-auto` ditolak; `smoke_test` SEMUA LULUS.
  Replay riwayat (fungsi saja, per 5 sampel): RO4350B sisi 0,30 ke 0,45 ke 0,11 ke 0,25 ke 0,38 (tidak macet di batas); FR-4 sisi mencapai batas atas 0,8 lalu turun ke 0,4 setelah tiga gagal berturut-turut.
  Backtest (10 ulangan, 30 langkah, restarts 1, seed sama; BO capai optimum dataset pada 20/30/40 evaluasi): FR-4 tanpa region 30/100/100%, `--region-auto 6:0.15` 40/70/100%, `--region-adapt` 80/100/100%; RO4350B tanpa region 70/80/90%, auto 60/80/100%, adapt 70/80/90%.
  Lintasan sisi median per batch: FR-4 0,30 0,30 0,30 0,38 0,38 0,22 (rentang 0,15 sampai 0,45); RO4350B 0,30 0,30 0,45 0,45 0,45 0,22 (rentang 0,15 sampai 0,45).
  PEMBATAS UTAMA: kumpulan sampel diskret sehingga region sering kosong dan pilihan jatuh ke seluruh sisa kumpulan: fallback adapt 92% (FR-4) dan 87% (RO4350B) langkah, auto 24% dan 28%. Karena itu `--region-adapt` di replay hampir sama dengan tanpa region (RO4350B identik), dan selisih antar mode (10 ulangan, 1 ulangan = 10 poin persen) tidak bermakna. Gerbang "tidak lebih buruk dari --region-auto" terpenuhi secara lemah; "region bergerak masuk akal" terpenuhi; manfaat nyata belum terbukti.
  Saran: jangan mengklaim perbaikan di laporan; sebut sebagai opsi yang aman dan menggantikan pemilihan K:margin manual. Untuk praktik tetap `--region-auto` yang sudah teruji. Belum teruji: Windows, CST nyata, `suggest --region-adapt` bersama `--focus`/`--sweep`/`--diversity` (hanya diperiksa pada FR-4 tahap otomatis), ulangan lebih banyak.
- **P2-3 Tahap A (16 Nov 2026): SELESAI, hasil: TIDAK MEMBANTU (gerbang gagal di FR-4 dan RO4350B). Tahap B (`--pof classifier`) TIDAK dikerjakan; `suggest` dan `core.py` tidak diubah.** paketN.zip.
  File: `cstopt/ml/pof_alt.py` (baru), `cstopt/ml/validate.py` (flag `--pof-compare`, mati bawaan; menulis `models/pof_compare.csv`). Uji dengan `py main.py validate --design NAMA --restarts 2 --pof-compare` (sekitar 2 sampai 4 menit per desain).
  Penaksir yang diuji (tanpa penyetelan hyperparameter): GPC isotropik (kernel RBF, ruang satuan), regresi logistik pada fitur Nystroem RBF (100 komponen), dan model dua bagian BW (GPC untuk BW > 0 dan GP pada log BW).
  Reproduksi acuan lama: FR-4 76 uji, PoF (a) 0,64 vs aktual 0,68, Brier 0,173 (acuan 0,216), BW di pita RMSE 28,04 MHz; RO4350B 175 uji, Brier 0,068 (acuan 0,059), BW di pita RMSE 21,95 MHz.
  Brier (a) perkalian regresi / GPC / logit; selisih (a-b) dengan CI 95% bootstrap berpasangan: FR-4 0,173 / 0,220 (-27,3%; CI -0,084 sampai -0,014) / 0,315 (-82,8%); RO4350B 0,068 / 0,069 (-1,7%; CI -0,017 sampai +0,017) / 0,060 (+11,3%; CI -0,008 sampai +0,026, mencakup 0).
  Kemiringan kalibrasi: (a) 0,25 FR-4 dan 0,36 RO4350B (jauh di bawah 1: PoF terlalu yakin di kedua ujung); GPC 0,18 dan 1,69; logit 0,09 dan 0,42. Hanya logit RO4350B Brier membaik lebih dari 10%, tetapi CI mencakup 0 dan di FR-4 logit jauh lebih buruk.
  Dua bagian BW: lebih buruk dari GP mentah. RMSE BW di pita FR-4 28,04 ke 32,59 MHz (bias +19,6), RO4350B 21,95 ke 32,14 MHz (bias +10,1). P(BW>0) tidak lebih informatif dari laju tetap (Brier 0,048 vs acuan 0,061 FR-4; 0,017 vs 0,017 RO4350B); BW = 0 hanya 7% (FR-4) dan 2% (RO4350B) sampel uji.
  Catatan untuk laporan: pada validasi maju PoF perkalian regresi kurang terkalibrasi (kemiringan 0,25 sampai 0,36), tetapi klasifikator generik pada konfigurasi yang diuji tidak memperbaikinya; ini temuan negatif yang dilaporkan apa adanya. Keterbatasan: hyperparameter tidak disetel dan n kecil (76 dan 175 titik uji).
  Belum teruji: Windows, `validate` tanpa `--pof-compare` di komputer pengguna (di sandbox hanya diperiksa tidak gagal), desain lain selain FR-4 dan RO4350B.
- **P2-2 `--diversity R` (16 Nov 2026): SELESAI (kode dan uji sandbox), paketM.zip (menggantikan paketL: `core.py` dan `suggest.py` memuat P2-1 dan P2-2).** Keputusan pengguna: uji di komputernya (bagian 0B, termasuk `tools\test_p2.py`) ditunda sampai akhir.
  `core.suggest(..., diversity=None)`: setelah kandidat dipilih, akuisisi sisa dikali prod(1 - exp(-(jarak/R)^2)) (penalti lunak, di atas `--spread`); `suggest.py` opsi `--diversity R`; `tools/test_p2.py --mode diversity`.
  Uji (sandbox): regresi seed 0 FR-4 tanpa opsi IDENTIK. Jarak min antar kandidat (tanpa opsi / R 0,15 / R 0,4 / R 0,6): FR-4 seed 0 0,332/0,332/0,473/0,473; seed 1 0,332/0,332/0,470/0,438; seed 2 0,440/0,440/0,440/0,712;
  RO4350B (fokus bw, gain >= 5,0, region-auto 6:0.15, margin fr 0,08) seed 0 0,345/0,345/0,622/0,622; seed 1 0,301/0,301/0,354/belum terbaca; seed 2 belum terbaca.
  Biaya: mean PoF kandidat turun sekitar 0,02 sampai 0,12 pada R >= 0,4 (mis. FR-4 seed 2 R 0,6: 0,460 ke 0,341); BW prediksi praktis sama (selisih sekitar 1 sampai 2 MHz).
  Gerbang P2-2 (jarak min lebih besar): TERPENUHI secara teknis untuk R sekitar 0,4 sampai 0,6 (5 dari 6 perbandingan terbaca; FR-4 seed 2 R 0,4 tidak berubah); R 0,15 identik dengan tanpa opsi. Manfaat kecil karena `--spread` 0,3 sudah menjaga jarak, dengan harga PoF lebih rendah: fitur marginal.
  Keputusan adopsi ada pada pengguna (opsi mati secara bawaan). Belum terbaca: RO4350B seed 1 R 0,6 dan seed 2 (jalankan `py tools\test_p2.py --mode diversity --seeds 1,2`). Belum teruji: Windows, CST nyata, `-q` selain 5, diversity bersama `--sweep`.
  Sesi 1 tuntas; sesi 2 (`--region-adapt`) hanya bila diputuskan; ingat gerbang waktu: sesi 2 dan 3 dibatalkan bila sesi 1 belum selesai pada 20 November (sesi 1 selesai 16 November).
- **P2 Sesi 1 (16 Nov 2026): P2-1 SELESAI (kode dan uji sandbox), paketL.zip; P2-2 BELUM dikerjakan (percakapan berikutnya, lihat titik lanjut).** Cabang `p2-sweep-diversity`.
  P2-1 `--sweep "KOLOM=LO:HI"` (butuh `--focus`, KOLOM harus constraint aktif; q batas merata, satu per kandidat): `cstopt/ml/core.py` (`suggest(..., sweep=None)`; f_best dihitung ulang per batas; constraint dipulihkan di `finally`), `cstopt/ml/suggest.py` (opsi, kolom `sweep_bound`, `stop_rule` dilewati saat sweep), `tools/test_p2.py`.
  Uji (sandbox, tanpa CST): regresi `suggest` seed 0 FR-4 IDENTIK (`compare_csv.py`); `smoke_test` SEMUA LULUS; `tools/test_p2.py` RO4350B fokus bw, gain >= 5,0 + `--region-auto 6:0.15 --margin fr_ghz=0.08`, sapuan gain 4,0:5,4, seed 0/1/2:
  lebar rentang gain prediksi tanpa sweep 0,07/0,06/0,02 dBi vs sweep 0,78/0,83/0,95 dBi; Spearman terhadap batas +0,40/+0,90/+1,00; gain prediksi >= batas pada 4/5, 5/5, 4/5 kandidat.
  Gerbang P2-1: "lima kandidat berbeda" TERPENUHI; "terurut sesuai batas" TERPENUHI SEBAGIAN (kecenderungan, bukan monoton ketat: batas bawah tidak mengikat dan ada efek Kriging believer). Keputusan adopsi ada pada pengguna; opsi mati secara bawaan.
  Titik lanjut P2-2 `--diversity R`: tambahkan `diversity=None` di `core.suggest` (setelah kandidat ke-i dipilih, kalikan akuisisi sisa dengan `1 - exp(-(jarak/R)^2)`, jarak ke semua kandidat terpilih, ruang satuan), opsi di `suggest.py`, tambahkan kasus ke `tools/test_p2.py`.
  Gerbang P2-2: jarak minimum antar kandidat lebih besar dari tanpa opsi (acuan seed 0: FR-4 0,332; RO4350B fokus bw gain >= 5,0 0,345; `--spread` bawaan 0,3 sudah menjaga jarak, jadi R perlu sekitar 0,4 sampai 0,5; R 0,15 praktis tanpa efek). Bila gagal: catat "tidak membantu", jangan di-merge sebagai fitur.
  Belum teruji: Windows/PowerShell, CST nyata (sweep hanya mengubah pemilihan kandidat; `run` tidak disentuh), `--sweep` pada FR-4 dan pada `-q` selain 5, sweep tanpa `--region-auto`.
- Tahap selesai: P1-4 (paketF.zip) dan P0-3 draf (paketG.zip): `docs/deviasi_proposal.md`, `docs/ringkasan_dosen.md`, `docs/progres_fr4.md` (diperbarui), `tools/package_dataset.py`
- Tugas aktif berikutnya: P1-1 generalisasi desain, tiga tahap kecil, SEMUA SELESAI (kode); sisa: pengguna menjalankan (lihat bawah); tiap tahap berakhir dengan zip ke pengguna, dan bagian ini diperbarui sebelum dan sesudahnya
  - Tahap 1 SELESAI (paketI.zip): `cstopt/cst/config.py` (`configure`, `design_for_run`, `warn_project_mismatch`), `batch.py` dan `export.py` memakai opsi `--design` dan membaca konstanta dari file desain (nilai lama tetap bawaan),
    `check_geometry` lama diganti `design.geometry_problems`, FR-4 `designs/uslot_dgs_fr4.py` kini memuat `BASE_PARAMS`, `EXTRA_BASE`, `CST`. Uji (modul `cst` tiruan): `run --check-samples` identik untuk CSV FR-4, seed RO, dan pilot h; `configure` dengan desain tiruan benar;
    `suggest` seed 0 identik; `smoke_test` lulus. Perubahan perilaku yang disengaja: aturan geometri desain lebih ketat (CSV toleransi: 2 dari 12 baris tidak valid, dulu 1)
  - Tahap 2 SELESAI (paketJ.zip): `cstopt/ml/core.py` (`load_dataset` memanggil `d.mod.features(df, d)` bila ada; bila tidak ada, fitur S11 lama seperti semula; hasil hook harus DataFrame dengan jumlah baris sama, jika tidak `ValueError`), `designs/_template.py` (semua antarmuka, bagian [GANTI] ditandai, `features` bawaan mendelegasikan ke `add_s11_features`), `tools/new_design.py` (`py tools\new_design.py NAMA [--from desain] [--run-name] [--material --er --tand --h]`: mengganti NAME, RUN_NAME, SUBSTRATE, hs dan Wf di EXTRA_BASE (Wf Hammerstad), menolak nama tidak valid, file sudah ada, dan RUN_NAME yang dipakai desain lain, lalu mencetak daftar yang harus diperiksa).
    Uji (sandbox, tanpa CST): `suggest -q 5 --seed 0 --restarts 2 --pool 8192` FR-4 IDENTIK dengan sebelum perubahan (`compare_csv.py`); hook delegasi ke `add_s11_features` menghasilkan DataFrame identik dengan jalur lama (156 x 45); hook kustom menambah kolom; hook yang mengembalikan baris salah ditolak; desain RO4350B (tanpa hook) tetap memuat 185 sampel; desain dari scaffolder (dari `_template` dan dari `uslot_dgs_ro4350b`) lolos `smoke_test.py` (SEMUA LULUS); berkas uji dihapus dari paket.
    Catatan: scaffolder dari `_template` memberi BASE_PARAMS, PARAM_NAMES, BOUNDS FR-4 apa adanya (harus diganti pengguna); docstring `_template.py` merujuk `docs/membuat_desain_baru.md` yang baru dibuat di tahap 3.
  - Tahap 3 SELESAI (paketK.zip): `designs/_demo_analytic.py` (patch resonan analitik 4 parameter L W g s, `mock_response(p, f)`), `tools/mock_run.py` (pengganti `run`: baris dibuat oleh `export.extract` asli dengan sumber kurva dan farfield diganti; resume, geometri tidak valid membatalkan batch, kolom ekstra ikut; memakai paket `cst` tiruan bila CST tidak ada), `tools/test_flow.py` (uji alur penuh sekali jalan, data di `data/DemoAnalytic/` dihapus di akhir), `docs/membuat_desain_baru.md`.
    Temuan dan perbaikan dari uji alur: `qc` memuat 11 nama parameter FR-4 secara tetap dan gagal pada desain lain; kini memakai `PARAM_NAMES` desain (`cstopt/qc/dataset.py` opsi baru `--design`, `cstopt/loader.py` fungsi `module_for_run` tanpa impor CST). `.gitignore`: `data/DemoAnalytic/`.
    Uji (sandbox): `tools/test_flow.py` SEMUA LULUS (lhs, mock_run, resume, qc, curves, train, 2 ronde suggest + mock_run, status, pareto, sensitivity, validate, report); `backtest` dan `report` pada data demo juga jalan; `qc` FR-4 dan RO4350B identik dengan versi lama (selisih hanya jalur folder); `suggest` seed 0 FR-4 IDENTIK; `smoke_test.py` SEMUA LULUS.
  - Aturan per tahap: keluaran perintah dipotong pendek, tanpa listing besar; perbarui bagian ini; serahkan zip; baru mulai tahap berikutnya
- P1-1 tidak mundur (selesai di sisi kode). P2 dikerjakan di percakapan lain, hanya bila ada bukti offline: lihat bagian 0A (urutan, cabang, gerbang) dan bagian 0B (status uji di komputer pengguna)
- Tugas pengguna yang menunggu: jalankan `sensitivity` RO4350B dan `backtest` FR-4, jalankan ulang `report`, baca `docs/deviasi_proposal.md` dan `docs/ringkasan_dosen.md` (semua angka berasal dari data yang sudah dibahas; koreksi bila ada yang tidak cocok), `py tools\package_dataset.py --version v1.0-fr4-ro4350b`, isi lisensi, commit
- Tag rilis `v1.0-fr4-ro4350b` dipasang pada commit akhir (sesudah P1-1 atau saat P1-1 diputuskan dilewati), bukan sekarang
- Zip terakhir yang diserahkan ke pengguna: paketO.zip (P2-4 region-adapt); sebelumnya paketN.zip (P2-3 Tahap A, hasil negatif), paketM.zip (P2-1 dan P2-2), paketL.zip (P2-1 sweep), paketK.zip (P1-1 tahap 3); sebelumnya paketJ.zip (tahap 2), paketI.zip (tahap 1), paketH.zip (rencana), paketG.zip (P0-3)

## 0A. Alur P2 (dikerjakan di percakapan Claude lain; satu percakapan = satu sesi di bawah, urut)

Prinsip: P2-1, P2-2, dan P2-4 sama-sama mengubah `cstopt/ml/suggest.py`, jadi TIDAK boleh dikerjakan paralel di percakapan berbeda (konflik merge). Kerjakan berurutan; tiap sesi satu cabang dari `main` terbaru, lalu di-merge ke `main` sebelum sesi berikutnya dimulai. Semua opsi baru mati secara bawaan: `suggest` tanpa opsi harus IDENTIK dengan sekarang (`tools/compare_csv.py`, seed 0, FR-4).

| Sesi | Tugas | Cabang | File utama | Gerbang bukti (adopsi hanya bila terpenuhi; bila tidak, catat "tidak membantu" dan jangan di-merge sebagai fitur) | Status |
|---|---|---|---|---|---|
| 0 | prasyarat: merge cabang P1-1 (`p1-1-tahap2`, `p1-1-tahap3`, serta tahap 1) ke `main`, pengguna menjalankan bagian 0B | - | - | uji bagian 0B lulus di komputer pengguna | belum |
| 1 | P2-1 `--sweep` + P2-2 `--diversity R` (satu sesi) | `p2-sweep-diversity` | `ml/suggest.py`, `ml/core.py` | P2-1: lima kandidat punya gain prediksi berbeda dan terurut sesuai batas. P2-2: jarak minimum antar kandidat lebih besar dari tanpa opsi. Keduanya: tanpa opsi IDENTIK | P2-1 (paketL) dan P2-2 (paketM) selesai di sandbox; adopsi P2-2 menunggu keputusan |
| 2 | P2-4 `--region-adapt` | `p2-region-adapt` | `ml/suggest.py`, `ml/backtest.py` | replay riwayat FR-4 lewat `backtest`: region bergerak masuk akal dan hasil tidak lebih buruk dari `--region-auto` | selesai di sandbox (paketO): aman, manfaat tidak terbukti (replay kurang berdaya); adopsi menunggu keputusan |
| 3 | P2-3 PoF klasifikasi dan model dua bagian (UJI OFFLINE DULU lewat `validate`, jangan mengubah `suggest` sebelum ada bukti) | `p2-pof-classifier` | `ml/validate.py`, lalu `ml/core.py` bila lolos | Brier membaik lebih dari 10% dan kemiringan kalibrasi lebih dekat ke 1 pada validasi maju FR-4 DAN RO4350B. Bila lolos: opsi `--pof classifier` (bawaan tetap lama) | Tahap A selesai: TIDAK membantu (Brier tidak membaik di FR-4 dan RO4350B); Tahap B dibatalkan |
| - | P2-5 h diskret dan parameter turunan | - | - | DILEWATI (butuh sekitar 30 simulasi CST, keuntungan paling banyak +10 sampai 15 MHz di FR-4) | dilewati |
| - | P2-6 ParEGO | - | - | hanya bila P2-1 terbukti tidak cukup; kemungkinan besar dilewati | dilewati |

Gerbang waktu: fitur P2 yang diadopsi harus sudah ter-merge ke `main` sebelum pembekuan fitur 24 November. Sesudahnya hanya perbaikan bug. Bila sesi 1 belum selesai pada 20 November, sesi 2 dan 3 dibatalkan (P0 dan laporan lebih penting). Setelah sesi terakhir: pengguna menjalankan bagian 0B lagi, jalankan ulang `report`, perbarui `docs/progres_fr4.md`, lalu pasang tag `v1.0-fr4-ro4350b` pada commit akhir.
Aturan tiap sesi P2: tunjukkan rencana dan perhitungan lebih dulu; hasil uji dibandingkan opsi mati vs hidup pada data asli (bukan hanya "berjalan tanpa error"); perbarui bagian 0 dan tabel ini di akhir sesi; serahkan zip file berubah saja.

## 0B. Status uji di komputer pengguna (Windows) dan tes akhir

Semua uji di bagian 0 (tahap 1 sampai 3) dijalankan Claude di sandbox Linux tanpa CST. PENGGUNA BELUM menjalankan satupun di komputernya (diputuskan 16 November: tes dilakukan di akhir, setelah kode P2 selesai). Claude di percakapan lain: jangan menganggap kode ini sudah terbukti jalan di Windows atau CST.

Uji offline (tanpa CST), jalankan di akhir setelah semua cabang ter-merge; semua BELUM dijalankan pengguna:
1. `py tools\smoke_test.py` (harus SEMUA LULUS)
2. `py tools\test_flow.py` (harus SEMUA LULUS), lalu uji `new_design.py` terpisah: `py tools\new_design.py uji_baru --er 3.66 --tand 0.0037 --h 1.524`, periksa `designs\uji_baru.py`, lalu hapus filenya
3. Regresi: `py main.py suggest -q 5 --seed 0 --restarts 2 --pool 8192` sebelum dan sesudah merge, bandingkan dengan `py tools\compare_csv.py lama.csv baru.csv` (harus IDENTIK)
4. `py main.py qc` dan `py main.py qc --run-name MicrostripAntena_RO4350B` (harus sama dengan sebelum P1-1 tahap 3)

Uji dengan CST nyata (satu sesi di komputer pengguna, setelah uji offline lulus):
5. `py main.py run --design uslot_dgs_ro4350b --check-samples` dan `run --limit 1` pada sampel yang sudah ada di data (hasil harus sama dengan baris lama; CST deterministik)
6. Peringatan nama project (`warn_project_mismatch`) dengan project yang namanya sengaja berbeda
7. `export.main --design`
8. Isi `BASE_PARAMS` desain `uslot_dgs_ro4350b` dari nilai parameter project RO4350B sebelum langkah 5 (tanpa itu `batch.py` memulihkan baseline FR-4 setelah batch)
9. GUI Windows: buka `py main.py`, periksa semua tab

Hasil tiap uji dikirim ke Claude (keluaran dipotong pendek) lalu dicatat di bagian 6; yang gagal diperbaiki sebelum tag rilis.

## 1. Cara melanjutkan di Claude lain

Unggah: `CLAUDE.md`, `RENCANA_LANJUTAN.md`, file ini, dan `batch_lhs.csv` terbaru kedua run (FR-4 dan RO4350B). Zip repo hanya bila perlu mengubah kode
(kirim folder `data/` tanpa `curves/`, `eff/`, `ff/` agar ringan). Lalu tempel prompt ini:

> Baca CLAUDE.md (termasuk bagian 10), RENCANA_LANJUTAN.md, lalu PROGRESS.md (mulai dari bagian 0). Patuhi aturan hemat token (jangan baca data/, jangan listing repo; baca file lewat grep atau sed).
> Lanjutkan dari bagian 0A (alur P2: ambil sesi berstatus "belum" pertama yang prasyaratnya terpenuhi) dan perhatikan bagian 0B (uji di komputer pengguna belum dijalankan). Sebelum mengubah file, tunjukkan rencana singkat dan perhitungan, lalu tunggu persetujuan.
> Serahkan zip berisi file yang berubah saja, perintah PowerShell, hasil uji (termasuk regresi seed 0), dan daftar jujur yang belum teruji.

Gaya kerja yang diinginkan pengguna: Bahasa Indonesia, ringkas; alur bertahap dengan persetujuan; perhitungan ditunjukkan sebelum file diubah; gambar PNG
(bukan HTML atau SVG); tanpa tanda hubung atau em dash pada prosa akademik; tugas diselesaikan cepat dan hanya bagian yang perlu. Akses Claude ke repo
dimatikan untuk menghemat token, jadi file dan keluaran terminal dikirim lewat unggahan.

## 2. Status per tugas (RENCANA_LANJUTAN.md)

| Tugas | Status | Catatan |
|---|---|---|
| P0-1 data RO4350B | selesai | BO dibekukan pada 185 sampel; front 22 titik |
| P0-2 A mesh rapat | selesai | sampel 165, 179, 180 lulus (selisih fr paling besar 2 MHz, BW 0,34%) |
| P0-2 B toleransi | selesai | ketiga desain; hasil di bagian 3.3; sampel 126 tidak dijalankan (keputusan pengguna) |
| P0-3 laporan dan rilis | selesai (draf) | `docs/deviasi_proposal.md`, `docs/ringkasan_dosen.md`, `tools/package_dataset.py`; sisa: pengguna membaca, `report`, commit, tag |
| P1-1 generalisasi desain | selesai (kode, 3 tahap) | dikorbankan lebih dulu bila mundur; lihat bagian 0 |
| P1-2 validasi maju | selesai | dijalankan pada RO4350B (185 sampel) dan FR-4 (156 sampel) |
| P1-3 hypervolume dan Pareto | selesai | `cstopt/report/pareto.py` |
| P1-4 sensitivitas dan aturan berhenti | selesai (kode) | `py main.py sensitivity`; backtest FR-4 dan sensitivitas RO4350B dijalankan pengguna (bagian 4) |
| P1-5 generator laporan | selesai | `py main.py report` |
| P2 semua | direncanakan, belum dikerjakan | urutan, cabang, dan gerbang bukti di bagian 0A; dikerjakan di percakapan lain |
| Perbaikan `qc` | selesai | `qc --run-name RUN` jalan tanpa `lhs_samples.csv` |

Kode yang sudah diserahkan: Paket A (`pareto.py`, `make_tolerance.py`, `analyze_tolerance.py`), Paket B (`validate.py`, `report.py`, `qc/dataset.py`, `main.py`), dan pembaruan `PROGRESS.md` dan `CLAUDE.md`.
Regresi `suggest -q 5 --seed 0 --restarts 2 --pool 8192` pada FR-4: IDENTIK dengan versi asli; `smoke_test.py`: SEMUA LULUS.

## 3. Temuan data

### 3.1 Data utama

FR-4 (MicrostripAntena): 156 sampel, 52 memenuhi syarat dasar; front 4 titik (BW 126,2 sampai 180,6 MHz, gain 2,89 sampai 2,80 dBi); hypervolume BW 518,5; knee sampel 91.
Terbaik: sampel 137 (BW 180,6 MHz, gain 2,80 dBi, fr 3,698 GHz, hanya 2 MHz dari tepi pita 3,7). Peringatan front FR-4 belum representatif akan muncul di laporan (4 titik).

RO4350B (MicrostripAntena_RO4350B): 185 sampel, 177 memenuhi syarat dasar; front 22 titik, BW 115,8 sampai 247,5 MHz; hypervolume BW 1324,9 dan cakupan 330,4 (front cakupan 16 titik); knee sampel 165.
Sampel 181 sampai 185 hanya menambah 0,1 hypervolume, jadi pembekuan BO tepat.

| Tujuan | Sampel | BW (MHz) | Gain (dBi) | Catatan |
|---|---|---|---|---|
| gain >= 5 dengan BW tertinggi (juga knee) | 165 | 158,6 | 5,03 | fr 3,616 GHz; RL minimum -24,9 dB |
| cadangan margin gain lebih aman | 126 | 145,7 | 5,28 | fr 3,600 GHz; RL minimum -23,1 dB |
| BW menengah | 173 | 195,1 | 4,81 | RL minimum -32,2 dB |
| BW >= 200 dengan gain tertinggi | 180 | 228,2 | 4,63 | fr 3,514 GHz; RL minimum -26,4 dB; cakupan 56,9% |
| BW tertinggi | 179 | 247,5 | 4,43 | fr 3,534 GHz; RL minimum -22,1 dB; cakupan 61,8%; BW pecahan 7,0% |
| gain tertinggi | 102 | 115,8 | 5,82 | |

Batas BW untuk tiap gain minimum: gain >= 5 sampai 158,6 MHz (sampel 165), >= 4,75 sampai 195,1 (173), >= 4,5 sampai 234,2 (176), >= 4,0 sampai 247,5 (179).
Kemiringan trade-off dari (158,6 MHz; 5,03 dBi) ke (247,5 MHz; 4,43 dBi): sekitar -0,0067 dB per MHz. Narasi "BW dibatasi fisika" harus diubah menjadi "gain dikorbankan untuk BW".
BOUNDS RO4350B: pengguna mengubahnya tiga kali; nilai akhir tidak dikirim. Usulan Claude: Wp atas 38,3; LD atas 7,5; WD atas 14,0; gD atas 1,4; LU bawah 1,5; WU bawah 3,0.
Pada data akhir WD maksimum 18,0 (tampaknya batas atas), PU atas 3,78 dan LU bawah 1,5 masih tersentuh desain BW tertinggi, dan WD sama dengan 57 sampai 61% Wp.
Lebar substrat `Ws = Wp + 6*hs` mengikuti Wp otomatis. Aturan geometri: `WU > 4*gU` dan `1,25 + LD <= Lp/2`.

### 3.2 Mesh rapat (lulus)

Kriteria: selisih fr < 10 MHz dan selisih BW < 5%. Run `MicrostripAntena_RO4350B_fine`. Nilai mesh lama dan baru tidak dikirim ke Claude; catat di naskah.

| Sampel | fr lama / baru (GHz) | selisih fr (MHz) | BW lama / baru (MHz) | selisih BW | selisih gain (dB) |
|---|---|---|---|---|---|
| 165 | 3,616 / 3,618 | 2,0 | 158,57 / 158,88 | 0,20% | +0,027 |
| 180 | 3,514 / 3,514 | 0,0 | 228,15 / 228,46 | 0,14% | +0,028 |
| 179 | 3,534 / 3,534 | 0,0 | 247,49 / 248,33 | 0,34% | +0,046 |

Mesh halus memberi gain sedikit lebih tinggi (+0,03 sampai +0,05 dB). Hasil nominal dianggap konvergen terhadap mesh, sehingga BW 247 MHz bukan artefak mesh.

### 3.3 Toleransi (run MicrostripAntena_RO4350B_tol)

Analisis bawaan memakai gain >= 4,5 dBi (batas tahap BO), yang tidak sesuai klaim tiap desain; angka di bawah memakai ambang yang sesuai klaim. Yield dari 12 sampel acak punya galat baku sampai sekitar 14 poin persen: bukan peluang.

| Desain | Ambang | Lulus | Rentang di bawah toleransi | Kegagalan |
|---|---|---|---|---|
| 180 | BW >= 200, gain >= 4,5 | 27 dari 28 (oat 12/12, corners 3/4, random 12/12) | BW 215,4 sampai 235,7; gain 4,48 sampai 4,66; fr 3,468 sampai 3,542 | satu skenario gain 4,48 (kurang 0,02 dari batas) |
| 165 | BW >= 142,7 (90% nominal), gain >= 5,0 | 15 dari 20 (oat 9/11, corners 0/2, random 6/7); 8 dari 28 dilewati karena geometri | BW 151,2 sampai 164,2; gain 4,81 sampai 5,09; fr 3,588 sampai 3,664 | semua 5 kegagalan karena gain di bawah 5,0 |
| 179 | BW >= 200, gain >= 4,0 | 22 dari 23 (5 dari 28 dilewati) | BW 246 sampai 258 kecuali satu skenario | LI + 0,1 mm (sampel 17909): fr 4,376 GHz, BW 33,2 MHz, gain 2,60 dBi |

Kesimpulan: 180 paling tahan (BW > 200 MHz di seluruh 28 skenario). 165 memenuhi gain >= 5 hanya nominal; di bawah toleransi gain turun sampai 4,81. 179 dekat jurang geometri terhadap LI (satu skenario +0,1 mm meruntuhkan resonansi),
sehingga hanya layak sebagai angka BW nominal dengan peringatan. Toleransi hs +/-10% (0,15 mm) mungkin lebih besar dari toleransi ketebalan laminat sebenarnya (cek datasheet); dominasi hs terhadap gain 165 belum diperiksa.

### 3.4 Model, validasi, dan backtest

RO4350B, `validate` batch 5 (185 sampel, 175 uji; restarts 2): di wilayah kerja (fr aktual di pita) BW R2 0,73 dengan RMSE 21,9 MHz; fr R2 0,89 dengan RMSE 22,1 MHz; gain R2 0,64 dengan RMSE 0,208 dBi; `rl_band_min_db` R2 -0,12.
Cakupan interval 95%: gain 65%, fr 81% (ketidakpastian model terlalu sempit). PoF rata rata 0,89 vs aktual 0,94; Brier 0,068 (acuan 0,059): PoF tidak lebih informatif daripada laju feasible tetap. Saran margin fr 0,029 GHz (lebih kecil dari 0,08 yang dipakai, jadi BO berhati hati).
FR-4 (76 uji): BW R2 0,65 dengan RMSE 28,0; fr R2 -0,98 dengan RMSE 135,6 MHz; PoF 0,64 vs 0,68, Brier 0,173 (acuan 0,216); saran margin fr 0,34 GHz melebihi setengah lebar pita (model tidak layak dipakai tanpa region sempit).
`train` RO4350B (148 latih, 37 uji): BW R2_test 0,962 dan R2_cv 0,820; fr R2_test 0,939 tetapi R2_cv -0,183 (RMSE_cv 0,107 GHz); parameter paling berpengaruh pada BW: LI 0,291, Lp 0,214, WD 0,122, Wp 0,122, LD 0,087.
Laporkan ukuran maju (validate) di samping ukuran acak (train); ukuran maju yang relevan untuk BO.
`backtest` RO4350B (20 ulangan; optimum dataset 234,2 MHz karena constraint gain >= 4,5): pada 30 evaluasi BO mencapai optimum di 95% ulangan vs acak 10%; pada 40 evaluasi 100% vs 20%.

### 3.5 Sensitivitas FR-4 (156 sampel; `py main.py sensitivity --design uslot_dgs_fr4`, 9 detik)

ARD untuk BW (jumlah 1): WU 0,221; Lp 0,175; LU 0,129; PU 0,107; Wp 0,093. Sobol BW (S1 dan ST): WU 0,352 dan 0,565; Lp 0,276 dan 0,384; LU 0,051 dan 0,218; PU 0,006 dan 0,079; jumlah S1 0,70 (interaksi cukup besar);
67% sampel dasar memenuhi aturan geometri (Sobol dihitung di seluruh kotak BOUNDS; GPR mengekstrapolasi di wilayah tidak valid).
Korelasi mentah dengan BW pecahan (n = 52): LU -0,79; WU -0,78; WD +0,77; Lp -0,73; Wp -0,51.
Pembanding temuan lama (135 sampel): ARD WU 0,218, PU 0,127, LU 0,121, Lp 0,118, LD 0,108 (sekarang WU 0,221, PU 0,107, LU 0,129, Lp 0,175, LD 0,089); korelasi BW pecahan WD +0,85 dan Lp -0,77 (sekarang +0,77 dan -0,73).
Perbedaan yang harus dilaporkan: WD berkorelasi tinggi dengan BW pecahan tetapi relevansi ARD (0,017) dan ST Sobol (0,001) untuk BW hampir nol; kemungkinan WD berubah bersama parameter lain di data (kolinearitas), belum dibuktikan.
Belum ditafsirkan secara fisik. Aturan berhenti pada FR-4: EI maks / |objective terbaik| = 2,74% (belum di bawah 1%); nilai RO4350B belum diukur (tidak bisa di sandbox karena kurva tidak lengkap).

## 4. Langkah berikutnya (urut; selesaikan seluruh rencana secara lebar dulu)

Keputusan pengguna: BO dihentikan; sampel 126 tidak dijalankan; 180 desain utama. Klaim 165 ditulis apa adanya dari data: gain 4,81 sampai 5,09 dBi pada toleransi yang diuji
(hs +/-10%, 8 dari 28 skenario dilewati karena geometri), nominal 5,03 dBi. Desain 179 hanya sebagai BW nominal tertinggi dengan peringatan LI + 0,1 mm.

| Urutan | Tugas | Butuh CST | Batas waktu |
|---|---|---|---|
| 1 | P1-4: `sensitivity` (ARD dan Sobol), aturan berhenti di `suggest`: kode selesai | tidak | selesai; sisa dijalankan pengguna: `py main.py sensitivity --design uslot_dgs_ro4350b --region-auto 8:0.15` dan `py main.py backtest --design uslot_dgs_fr4 --reps 20 --steps 30 --restarts 2` |
| 2 | P0-3: draf tabel target vs tercapai (dari `report`), "Deviasi dari proposal", ringkasan satu halaman, paket dataset: selesai | tidak | selesai (draf); pengguna membaca dan menyetujui |
| 3 | P1-1: generalisasi desain (konstanta CST dipindah ke file desain, uji dengan paket `cst` tiruan) | tidak | selesai sebelum pembekuan fitur 24 Nov; dikorbankan lebih dulu bila mundur |
| 4 | P2: hanya bila P0 dan P1 selesai dan ada bukti offline | tidak | kemungkinan besar dilewati |
| 5 | Jalankan ulang `report`, perbarui `docs/progres_fr4.md`, tag rilis `v1.0-fr4-ro4350b` | tidak | laporan final 28 Nov |

Perintah akhir oleh pengguna: `py main.py report --constraint "MicrostripAntena_RO4350B:gain_fr_ieee_dbi>=5.0" --constraint "MicrostripAntena_RO4350B:gain_fr_ieee_dbi>=4.0"`, lalu commit dan tag.
Opsional: satu atau dua ronde FR-4 `--focus gain --constraint "bw_mhz>=150"` (front FR-4 hanya 4 titik).

## 5. Keputusan dan asumsi yang perlu diingat

- Toleransi bawaan: Lp, Wp, LI +/-0,1 mm; gU, gD +/-0,05 mm (batas bawah celah 0,2 mm, `--gap-min`); hs +/-10% dengan `Wf` dihitung ulang (`--keep-wf` menahan `Wf` tetap, lebih dekat ke kenyataan etsa). Epsilon tidak ditoleransi (butuh parameter CST baru, belum terbukti diterima).
- Skenario toleransi yang melanggar aturan geometri dilewati dan dicatat di berkas `_meta.csv` (bukan dikirim ke CST). Pada uji sampel 112 (menempel batas), 5 dari 24 skenario dan 3 dari 4 corners terlewati:
  `gU + 0,05` melanggar `WU > 4*gU`, dan `LI + 0,1` melanggar jarak U-slot ke inset. Pilih desain final yang punya ruang geometri. `--keep-invalid` memaksa menulis barisnya, tetapi `run` bisa menolaknya.
- Analisis toleransi memakai ambang yang harus disesuaikan dengan klaim desain (--bw-min, --gain-min); bawaan gain 4,5 dBi dan BW 90% nominal. Yield dihitung terpisah per plan; hanya plan random yang mendekati yield statistik, dan dengan 12 sampel galat bakunya sekitar 14 poin persen. OAT dan corners adalah kasus terburuk, bukan peluang. Syarat BW default: 90% BW nominal.
- `validate` memakai kolom objective dan constraint tahap atau fokus aktif, dan tidak mengubah `suggest`. Saran `--margin` bisa sangat besar bila model buruk di ekstrapolasi (FR-4 split 135: fr 0,5 GHz); itu sinyal untuk mempersempit region, bukan untuk dipakai apa adanya.
- `report` memilih desain terbaik langsung dari CSV (fr di pita, RL minimum <= -10 dB, constraint tambahan), konsisten dengan `pareto`; overlay S11 butuh `curves/s11_sample{id}.csv`.

## 6. Belum teruji atau belum diketahui

- Belum diverifikasi (saran AI lain): `hs+` dominan pada kegagalan gain 165, spesifikasi ketebalan RO4350B +/-5%, dan gain minimum sekitar 4,90 bila toleransi +/-5%. Hasil perintah penelusuran skenario gain 165 belum dikirim ke Claude, dan pada data 179 `hs+` justru menaikkan gain (+0,27 dB), jadi arah dugaannya perlu dicek. Klaim yang aman: gain 4,81 sampai 5,09 dBi pada toleransi yang diuji.
- Skenario yang dilewati karena geometri (8 dari 28 pada 165; 5 dari 28 pada 179): ketahanan terhadap sisi itu tidak teruji.
- Nilai mesh lama dan baru serta nilai BOUNDS akhir RO4350B tidak dikirim ke Claude; catat di naskah.
- P1-1 tahap 1 hanya diuji dengan modul `cst` tiruan (`--check-samples`); `run` penuh di CST nyata, `export.main --design`, dan peringatan nama project belum dijalankan di CST. Baseline `BASE_PARAMS` desain RO4350B belum diketahui: tanpa atribut itu `batch.py` mengembalikan model ke baseline FR-4 (perilaku lama); isi dari nilai parameter project RO4350B Anda.
- P1-1 tahap 2: `new_design.py` belum dijalankan di Windows (PowerShell); path memakai `os.path`, tetapi belum dibuktikan. Hook `features` belum diuji dengan desain nyata yang memakai fitur selain S11.
- P1-1 tahap 3: model analitik demo tidak mewakili antena nyata (hanya menguji alur); `run` penuh dengan CST nyata untuk desain baru belum diuji; `qc --expect-eff` dan `--mon-step` tetap bawaan FR-4 (9 titik, 0,25 GHz) untuk desain dengan monitor lain.
- GUI Windows tidak disentuh.

## 7. Jangan menulis di laporan

Angka yang bukan dari tabel hasil; klaim kebaruan analisis toleransi (topik mapan); "BW dibatasi fisika" untuk RO4350B (bertentangan dengan BW 227 MHz pada gain 4,40 dBi);
klaim BW 247 MHz sebagai desain tahan toleransi (desain 179 runtuh pada LI + 0,1 mm); yield dari OAT atau corners sebagai peluang.
