# CLAUDE.md: konteks proyek dan aturan kerja

Baca file ini dulu di setiap percakapan baru, lalu `PROGRESS.md` (status terkini dan langkah berikutnya). Perbarui bagian 5 dan 6 di akhir sesi (lihat bagian 9).
Rincian hasil ada di `docs/` (progres_fr4.md, pilot_h.md, kontrol_tand.md, substrat_ro4350b.md); baca hanya bila perlu.

## 0. Aturan hemat token (wajib)

- Jangan membuka halaman GitHub repo atau menjelajah repo luas lewat konektor. Repo memuat ratusan berkas data; satu listing saja mahal.
- Jangan membaca isi `data/` (curves/, eff/, ff/ berisi ratusan berkas). Hampir semua tugas tidak butuh itu. Bila perlu angka, minta pengguna
  mengunggah `batch_lhs.csv`, baca dengan pandas (`usecols`), dan tampilkan ringkasan (head, describe), bukan seluruh isi.
- Daftar kode: `git ls-files | grep -v "^data/"`. Baca bagian yang perlu saja (`grep -n`, `sed -n 'a,bp'`). Ukuran kira kira: `ml/core.py` 500 baris,
  `cst/batch.py` 450, `cst/export.py` 350, `gui/app.py` 760. Jangan memuat seluruh file untuk perubahan kecil.
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
`sampling/lhs.py`, `cst/` batch, export, farfield, dialog_watcher, `ml/` core, train, suggest, backtest, `qc/`, `report/pareto.py`, `gui/`); `data/<RUN>/` (batch_lhs.csv,
curves/ eff/ ff/, samples/, models/, figures/); `macros/` (VBA, setup terpisah); `cst_projects/`; `tools/`; `docs/`.

| Perintah | Fungsi |
|---|---|
| `py main.py status` | ringkasan (sampel, tahap BO, terbaik, peringatan batas) |
| `lhs`, `run`, `qc`, `curves`, `train`, `suggest`, `backtest` | tahap alur; opsi: `-h` |
| `pareto` | kurva Pareto BW vs gain dan cakupan vs gain dari semua run (`data/_compare/pareto.png` dan `_front.csv`); juga tombol di GUI tab 6 |
| `run` (butuh CST) | `--samples CSV --auto-yes --limit N --run-name NAMA`; kolom hs/Wf/lossTan di CSV otomatis jadi parameter ekstra |
| `suggest` | `-q 5 --seed 0 --restarts 2 --pool 8192`; opsi lanjutan: `--focus --constraint --region --region-auto --margin --calibrate --composite --sweep --diversity R --region-adapt` (`--sweep "gain_fr_ieee_dbi=4.0:5.4"`: satu batas constraint per kandidat, butuh `--focus`; `--diversity R`: penalti lunak jarak antar kandidat, efektif bila R > 0,3, mis. 0,4; uji: `tools/test_p2.py [--mode diversity]`) |
| `autorun` (run butuh CST) | `--batches N [--qc] [--train] [--project P] [--dry-run] -- <opsi suggest>`: putaran penuh BO diulang N batch (simulasi menunggu, suggest, run, qc, train, log `data/<RUN>/auto_run_log.csv`); berhenti bila langkah gagal, sampel tidak bertambah, parameter menempel batas rentang dengan `--bounds-check stop` (4, bawaan hanya peringatan), atau Ctrl+C (130); uji `tools/test_autorun.py` |
| `tools/make_seeds.py`, `tools/wf50.py`, `tools/smoke_test.py` | seed antar substrat; Wf 50 ohm; uji instalasi |
| `tools/test_flow.py`, `tools/mock_run.py` | uji alur penuh tanpa CST (desain demo `_demo_analytic`); `mock_run` pengganti `run` untuk desain yang punya `mock_response`; panduan `docs/membuat_desain_baru.md` |
| `tools/new_design.py NAMA [--from D] [--er --tand --h]` | buat `designs/NAMA.py` dari `designs/_template.py`; hook opsional `features(df, d)` di file desain menggantikan fitur S11 bawaan |

Satu project CST = satu `RUN_NAME` = satu folder `data/<RUN>/`. Desain dipilih dengan `--design nama` (tanpa .py), bawaan `uslot_dgs_fr4`.
BO: tahap otomatis (Tahap 1 minimalkan rl_band_min_db sampai ada sampel feasible, lalu Tahap 2 maksimalkan bw_mhz); atau fokus manual dari `FOCI`.

## 4. Riwayat singkat

1. Awal: kode CST + ML masih berantakan; perbaikan BO dua tahap, fitur dip, `BOUNDS` diperlebar bertahap, peringatan parameter menempel batas.
2. Restruktur repo ke tata letak di atas (PR sudah di-merge ke main): satu `main.py`, GUI, paket `cstopt/`, `designs/`, `data/<RUN>/`, skrip migrasi.
3. Hasil FR-4 (155 sampel) dan diagnosis: target tidak tercapai; bukti batas fisik (bagian 5).
4. Pilot ketebalan h (8 simulasi) dan kontrol tan d (7 simulasi) lewat parameter CST ekstra.
5. Revisi BO v2 (region, margin, kalibrasi, komposit, fokus) dan desain Rogers RO4350B.
6. Data RO4350B 150 sampel (BOUNDS diubah tiga kali); alat baru: `pareto` (tangga, knee, hypervolume), `validate`, `report`, `tools/make_tolerance.py`, `tools/analyze_tolerance.py`; `qc` jalan tanpa `lhs_samples.csv`.

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
- RO4350B h 1,524 mm, 185 sampel (BO dibekukan): front 22 titik, BW 116 sampai 247 MHz; gain >= 5 dBi sampai BW 158,6 MHz (sampel 165, 5,03 dBi); BW 247,5 MHz pada gain 4,43 dBi (sampel 179). Mesh rapat lulus (selisih fr paling besar 2 MHz, BW 0,34%). Toleransi: 180 paling tahan (BW >= 215 MHz di 28 skenario); 165 gain turun sampai 4,81 dBi; 179 runtuh pada LI + 0,1 mm. Hypervolume BW: FR-4 518,5, RO 1324,9.
- Validasi maju FR-4 (latih id 1 sampai 135, uji 136 sampai 155): bias fr +244,5 MHz, RMSE 316 MHz, PoF fr 0,68 vs aktual 0,25 (terreproduksi); mode batch berurutan jauh lebih baik (PoF 0,64 vs 0,68).

## 6. Keputusan dan langkah berikutnya

Keputusan: tetap FR-4 h = 1,6 mm untuk hasil FR-4; substrat kedua Rogers RO4350B dari material library CST (project terpisah
`MicrostripAntena_RO4350B`, desain `uslot_dgs_ro4350b`, seed dari FR-4 diskalakan sqrt(eeff)); hasil utama = kurva Pareto BW vs gain untuk dua substrat
lewat fokus (`--focus bw --constraint "gain_fr_ieee_dbi>=4.5"`, dst.), selalu bersama `--region-auto` dan `--margin fr_ghz=0.08`.

Status (16 Nov 2026): BO RO4350B dibekukan pada 185 sampel; mesh dan toleransi desain 165, 180, 179 selesai. Rincian, perintah, dan daftar belum diketahui ada di `PROGRESS.md`.
P2 sesi 1: P2-1 `--sweep` dan P2-2 `--diversity` selesai di sandbox (paketM); adopsi menunggu keputusan pengguna dan uji akhir (`PROGRESS.md` bagian 0).
P2-4 `--region-adapt` selesai di sandbox (paketO): aman, manfaat tidak terbukti (replay kurang berdaya, fallback 87 sampai 92%); jangan diklaim sebagai perbaikan.
P2-3 Tahap A selesai: PoF klasifikasi dan dua bagian BW TIDAK membantu (validasi maju FR-4 dan RO4350B; `validate --pof-compare`); tidak diadopsi, `suggest` tidak berubah.
G2a selesai di sandbox (paketS): `py main.py bounds` (lihat/usulkan/atur/reset rentang parameter lewat `data/<RUN>/bounds_override.json`; file desain tidak pernah diedit; tanpa override hasil IDENTIK; uji `tools/test_bounds.py`); G2b selesai (paketT): tombol "Rentang parameter..." di tab 5 membuka dialog yang membungkus `bounds --json` (uji `tools/test_gui_g2b.py`, xvfb di Linux).
GUI G1 selesai di sandbox (paketR): tab 5 memuat sweep, diversity, region adaptif, tombol Validasi/Sensitivitas; tab 6 memuat Buat laporan; uji `tools/test_gui_g1.py` (xvfb di Linux). G2 sampai G5 (rentang parameter, tampilan data, tampilan, dialog substrat) menunggu keputusan pembekuan; rencana di `docs/RENCANA_LANJUTAN.md`.
G3 (tab Data, zoom, grafik interaktif) selesai di sandbox (paketU sampai Y); sisa G3 (paketAA): koordinat paralel dan kandidat BO/sweep di grafik sebar selesai di sandbox, belum diuji di Windows; perbaikan `report` menunggu contoh bagian yang dianggap kurang. G4a (tata letak: status ringkas, log terlipat, baris tombol membungkus, ukuran dari layar) kodenya selesai (paketZ) tetapi BELUM dijalankan sama sekali (sandbox tanpa tkinter): jalankan `py tools\\test_gui_g4.py` di Windows. G4b dan G5a belum.
T2 (tata letak tab 1 sampai 5 dan 7: panel info, Analisis model di tab 4, opsi lanjutan terlipat) kodenya selesai (paketT2) tetapi BELUM dijalankan sebagai GUI (sandbox tanpa tkinter): jalankan `py tools\\test_gui_t2.py --shot shots_t2` di Windows; T1 (tema gelap) kodenya selesai (paketT1: `cstopt/gui/theme.py`, warna berbasis peran, ttk `clam`, tombol Tema di bilah atas, pilihan tersimpan di `~/.cstopt_gui.json`) tetapi BELUM dijalankan sebagai GUI: jalankan `py tools\\test_gui_t1.py --shot shots_t1` di Windows. G4b dibatalkan.
Berikutnya (lebar dulu): (a) P1-1 selesai (kode, tiga tahap); (b) pengguna: `sensitivity` RO4350B, `backtest` FR-4, `report`, `package_dataset`, commit, lalu tag rilis. P1-4 dan P0-3 (draf) selesai.
Autorun: CLI `py main.py autorun` (paketAU1) dan GUI tab 5 (paketAU2: baris Auto run, kunci opsi, label progres, Hentikan) selesai di sandbox, uji lulus, `suggest` seed 0 identik; belum diuji di Windows dan dengan CST nyata (uji `tools/test_autorun.py`, `tools/test_gui_autorun.py`). Rencana penutup: `docs/RENCANA_LANJUTAN.md` bagian 13. F1 sampai F3 (paketF1) selesai di sandbox: tombol Laporan per desain (`data/_report_<run>`), bagian 9 laporan (`cstopt/report/pattern.py`: pola 2D, metrik, VSWR, efisiensi, toleransi, fase optimasi); uji `tools/test_report_pattern.py`, `tools/test_gui_report.py`. F4a (paketF4a): `report --min-yield` (desain rekomendasi tahan toleransi), peringatan parameter di batas rentang, kalimat target bersamaan. F4 dan F5 selesai (paketF5: docs deviasi dan ringkasan dosen diperbarui). F6 dilewati (naskah mengikuti format kampus); F7 siap di sisi kode (paketF7: `package_dataset` menyertakan `_report_*` dan `--with-ff`). Berikutnya F8 (uji CST nyata oleh pengguna, prosedur di `docs/RENCANA_LANJUTAN.md`; alat pembanding `tools/compare_runs.py`) lalu tag rilis. F8 langkah A pertama tidak cocok: penyebab di kode ditemukan dan diperbaiki (paketF8b): desain tanpa `EXTRA_BASE` dulu mewarisi hs 1,6 dan Wf 3,11 (FR-4) dan project RO4350B ikut berubah setelah run toleransi; baseline kini diturunkan dari `SUBSTRATE` (`cstopt/substrate.py`) dan `run` memeriksa hs dan Wf di project (uji `tools/test_substrate.py`). Langkah A0 (setel hs 1,524 dan Wf 3,336 lalu ulangi) harus dibuktikan pengguna.
Rincian di `PROGRESS.md`; per 16 November: 8 hari ke pembekuan fitur (24 November), laporan final 28 November, tenggat 1 Desember.
Cabang git: restruktur sudah di-merge; pilot-h dan control-tand dibuat bertumpuk; paket BO v2 di cabang bo-v2. Cek `git branch -a` dan `git log --oneline -8`.

## 7. Jebakan dan catatan teknis

- Nama parameter CST `tand` DITOLAK (bentrok nama objek VBA). Loss tangent memakai `lossTan` (alternatif `dLoss`, `tanDelta`, `tdelta`; nama kolom CSV harus sama).
- `Wf` 50 ohm = Hammerstad (`tools/wf50.py`); 3,11 mm untuk FR-4 h 1,6; sekitar 3,34 mm untuk RO4350B h 1,524.
- Kolom hs/Wf/lossTan di CSV sampel otomatis dipakai sebagai parameter ekstra; tanpa deteksi kolom itu akan diabaikan dan sampel dianggap duplikat.
- `batch.py` mengembalikan model ke baseline di akhir (geometri baseline FR-4; ekstra ke nilai tetap `BASE_EXTRA`).
- Prediksi cakupan pita di atas sekitar 45% tidak realistis (BW pecahan sekitar 5%); fokus gain dan cakupan tanpa region menghasilkan ekstrapolasi GP ekstrem.
- Opsi lanjutan BO mati secara bawaan: `suggest` tanpa opsi harus identik dengan versi sebelumnya (uji dengan `tools/compare_csv.py`, seed 0).
- `bo_suggest.py` lama menyebut `batch_trial_LHS.py`; nama yang benar `py main.py run`.

- `qc` kini memakai `PARAM_NAMES` desain (`--design` atau dicocokkan dari `--run-name`); dulu 11 nama FR-4 tertanam. Desain berawalan garis bawah (`_template`, `_demo_analytic`) tidak muncul di `list_designs` dan hanya bisa dipilih lewat `--design`.

## 8. Cara bekerja dan menguji di sandbox

- Sandbox: `/bin/sh` tanpa brace expansion (tulis jalur satu per satu atau `bash -c`). Pasang `python3-tk` dan pakai `xvfb-run` untuk menguji GUI (tangkap layar dengan
  `PIL.ImageGrab(xdisplay=...)`). CST tidak ada; uji logika `run` dengan modul tiruan `cst` (paket kosong berisi `results.py` dan `interface.py` dengan `DesignEnvironment`).
- Alur patch: salin repo ke folder kerja, ubah, uji pada data asli (regresi seed 0, uji tiap opsi baru, uji GUI), buat zip berisi file berubah saja, berikan perintah
  PowerShell (`Expand-Archive -Path ... -DestinationPath . -Force`, branch baru, commit) dan nyatakan terus terang apa yang belum teruji (terutama CST nyata).
- Dataset 155 sampel terbaru ada di komputer pengguna; minta unggahan `batch_lhs.csv` bila perlu. Simpan keluaran kecil, jangan data mentah.

## 9. Memperbarui file ini

Di akhir sesi: perbarui bagian 5 (temuan baru, singkat) dan bagian 6 (status dan langkah berikutnya); tambahkan jebakan baru di bagian 7. Jaga file ini di bawah
sekitar 200 baris; pindahkan rincian panjang ke `docs/`.

## 10. Aturan kerja Claude: progres dan serah terima (wajib)

1. Sebelum menulis atau mengubah kode, perbarui `PROGRESS.md` bagian 0 ("Sedang dikerjakan"): tugas aktif, rencana file, status "mulai". Setelah tiap file atau tahap selesai, perbarui lagi: file selesai, file berikutnya, perintah uji, dan yang belum teruji.
2. Claude tidak bisa melihat sisa token dengan pasti, jadi jangan menunggu "hampir habis". Tulis titik lanjut di `PROGRESS.md` pada setiap tahap. Bila percakapan terasa panjang atau mendekati batas, berhenti menambah fitur, tulis "Titik lanjut" (file setengah jadi, yang kurang, perintah uji), lalu serahkan zip.
3. Serahkan zip ke pengguna di setiap tahap selesai (`present_files`), bukan hanya di akhir. Zip selalu memuat `PROGRESS.md` terbaru. Jangan mulai tahap berikutnya sebelum zip tahap sebelumnya diserahkan.
4. Urutan prioritas: selesaikan seluruh rencana secara lebar dulu (P0, lalu P1 sesuai gerbang di `RENCANA_LANJUTAN.md` bagian 3), baru perdalam atau sesuaikan bagian yang kurang. Jangan terpaku pada satu hal. Gerbang: pembekuan fitur 24 November, laporan final dan tag rilis 28 November.
5. Saran dari AI lain atau klaim yang belum diperiksa dengan data dicatat sebagai "belum diverifikasi", bukan sebagai fakta.
