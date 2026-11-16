# PROGRESS.md: status berjalan dan serah terima ke percakapan Claude lain

Diperbarui: 16 November 2026. Sisa waktu per tanggal ini: 8 hari sampai pembekuan fitur (24 November), 12 hari sampai laporan final (28 November), 15 hari sampai tenggat (1 Desember). Tenggat proyek: 1 Desember 2026; fitur baru dibekukan tujuh hari sebelumnya (24 November).
Semua angka di bawah berasal dari keluaran perintah yang sudah dijalankan (log pengguna atau uji di sandbox). Yang tidak terukur ditulis "belum".

## 0. Sedang dikerjakan (Claude memperbarui bagian ini SEBELUM menulis kode dan setelah tiap tahap)

- Tahap selesai: P1-4 (paketF.zip) dan P0-3 draf (paketG.zip): `docs/deviasi_proposal.md`, `docs/ringkasan_dosen.md`, `docs/progres_fr4.md` (diperbarui), `tools/package_dataset.py`
- Tugas aktif berikutnya: P1-1 generalisasi desain (konstanta CST dipindah ke file desain dengan nilai bawaan; uji dengan paket `cst` tiruan). Status: belum mulai; baca `RENCANA_LANJUTAN.md` bagian P1-1 dan inventaris `grep -n "PARAM_NAMES\|BASE\b\|BAND\|MON_\|BW_MIN\|GAIN_MIN\|check_geometry" cstopt/cst/*.py`
- Bila P1-1 mundur: dikorbankan lebih dulu sesuai gerbang keputusan; P2 hanya bila ada bukti offline
- Tugas pengguna yang menunggu: jalankan `sensitivity` RO4350B dan `backtest` FR-4, jalankan ulang `report`, baca `docs/deviasi_proposal.md` dan `docs/ringkasan_dosen.md` (semua angka berasal dari data yang sudah dibahas; koreksi bila ada yang tidak cocok), `py tools\package_dataset.py --version v1.0-fr4-ro4350b`, isi lisensi, commit
- Tag rilis `v1.0-fr4-ro4350b` dipasang pada commit akhir (sesudah P1-1 atau saat P1-1 diputuskan dilewati), bukan sekarang
- Zip terakhir yang diserahkan ke pengguna: paketG.zip (P0-3)

## 1. Cara melanjutkan di Claude lain

Unggah: `CLAUDE.md`, `RENCANA_LANJUTAN.md`, file ini, dan `batch_lhs.csv` terbaru kedua run (FR-4 dan RO4350B). Zip repo hanya bila perlu mengubah kode
(kirim folder `data/` tanpa `curves/`, `eff/`, `ff/` agar ringan). Lalu tempel prompt ini:

> Baca CLAUDE.md (termasuk bagian 10), RENCANA_LANJUTAN.md, lalu PROGRESS.md (mulai dari bagian 0). Patuhi aturan hemat token (jangan baca data/, jangan listing repo; baca file lewat grep atau sed).
> Lanjutkan dari bagian "Langkah berikutnya" di PROGRESS.md. Sebelum mengubah file, tunjukkan rencana singkat dan perhitungan, lalu tunggu persetujuan.
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
| P1-1 generalisasi desain | ditunda | dikorbankan lebih dulu sesuai gerbang keputusan |
| P1-2 validasi maju | selesai | dijalankan pada RO4350B (185 sampel) dan FR-4 (156 sampel) |
| P1-3 hypervolume dan Pareto | selesai | `cstopt/report/pareto.py` |
| P1-4 sensitivitas dan aturan berhenti | selesai (kode) | `py main.py sensitivity`; backtest FR-4 dan sensitivitas RO4350B dijalankan pengguna (bagian 4) |
| P1-5 generator laporan | selesai | `py main.py report` |
| P2 semua | ditunda | hanya bila P0 dan P1 selesai dan ada bukti offline |
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
- GUI Windows tidak disentuh.

## 7. Jangan menulis di laporan

Angka yang bukan dari tabel hasil; klaim kebaruan analisis toleransi (topik mapan); "BW dibatasi fisika" untuk RO4350B (bertentangan dengan BW 227 MHz pada gain 4,40 dBi);
klaim BW 247 MHz sebagai desain tahan toleransi (desain 179 runtuh pada LI + 0,1 mm); yield dari OAT atau corners sebagai peluang.
