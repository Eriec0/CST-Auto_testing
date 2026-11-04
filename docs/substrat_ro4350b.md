# Substrat kedua: Rogers RO4350B

Tujuan: menjalankan alur yang sama pada substrat rugi rendah, sebagai demonstrasi lintas substrat dan untuk melihat kurva
trade-off BW dan gain. Satu substrat = satu project CST (`MicrostripAntena_RO4350B`) + satu file desain
(`designs/uslot_dgs_ro4350b.py`). Data masuk ke `data/MicrostripAntena_RO4350B/`, terpisah dari FR-4.

## A. Siapkan project CST (sekali)

1. Buka `cst_projects\MicrostripAntena.cst`, lalu File > Save As: `cst_projects\MicrostripAntena_RO4350B.cst`.
   Nama project harus persis seperti itu (sama dengan `RUN_NAME` di file desain).
2. Muat material dari library: Materials > Load from Material Library, pilih "Rogers RO4350B (lossy)". Ganti material solid
   "Substrate" ke material itu (klik kanan Substrate di Navigator Tree > Change Material).
3. Buka dialog material RO4350B dan catat nilai Epsilon dan Tan delta dari library. Desain mengasumsikan 3,66 dan 0,0037
   (`SUBSTRATE` di file desain). Bila berbeda, kabari saya atau ubah `SUBSTRATE` dan jalankan ulang langkah 5.
4. Ubah parameter: `hs` = `1.524` (60 mil) dan `Wf` sesuai hasil `py tools\wf50.py --er 3.66 --h 1.524` (sekitar 3,336 mm).
   Gunakan epsilon dari library bila berbeda. `Ws` dan rentang port ikut berubah otomatis (ekspresi dari `hs`).
5. Simpan project. Parameter `lossTan` dan material FR-4 yang tersisa tidak dipakai lagi; biarkan saja.

## B. Seed dari desain FR-4 (transfer)

```
py tools\make_seeds.py --to uslot_dgs_ro4350b --n 10
```

Membaca `data\MicrostripAntena\batch_lhs.csv`, memilih 10 desain FR-4 terbaik (BW, cakupan pita, tengah pita), menskalakan panjangnya
dengan s = sqrt(eeff_FR4 / eeff_RO) (sekitar 1,08), lalu menulis `data\MicrostripAntena_RO4350B\samples\seed_from_uslot_dgs_fr4.csv`.

```
py main.py run --samples data\MicrostripAntena_RO4350B\samples\seed_from_uslot_dgs_fr4.csv --auto-yes --limit 1
py main.py run --samples data\MicrostripAntena_RO4350B\samples\seed_from_uslot_dgs_fr4.csv --auto-yes
py main.py status --design uslot_dgs_ro4350b
```

Langkah pertama hanya satu sampel untuk memeriksa pengaturan; sisanya setelah hasilnya masuk akal (fr dekat 3,5 sampai 3,7 GHz).

## C. Putaran BO

```
py main.py suggest --design uslot_dgs_ro4350b --region-auto 6:0.15 --margin fr_ghz=0.08 -q 5
py main.py run --samples data\MicrostripAntena_RO4350B\samples\bo_candidates.csv --auto-yes
```

Ulangi sekitar 6 sampai 8 putaran (30 sampai 40 simulasi). Tahap otomatis: Tahap 1 mencari pencocokan, Tahap 2 memaksimalkan BW
dengan gain >= 4,5 dBi (`GAIN_MIN_DBI` di file desain). Model gain memakai komposit D + 10 log10(eta) (`USE_COMPOSITES = True`).

## D. Kurva Pareto BW dan gain (fokus)

Tiap fokus berbagi dataset dan model yang sama; jalankan 1 sampai 2 putaran per titik:

```
py main.py suggest --design uslot_dgs_ro4350b --focus bw --constraint "gain_fr_ieee_dbi>=4.5" --region-auto 8:0.15 --margin fr_ghz=0.08
py main.py suggest --design uslot_dgs_ro4350b --focus bw --constraint "gain_fr_ieee_dbi>=5.0" --region-auto 8:0.15 --margin fr_ghz=0.08
py main.py suggest --design uslot_dgs_ro4350b --focus cover --region-auto 8:0.15 --margin fr_ghz=0.08
py main.py suggest --design uslot_dgs_ro4350b --focus gain --constraint "bw_mhz>=100" --region-auto 8:0.15 --margin fr_ghz=0.08
```

Setelah semua titik terkumpul, gambar kurva Pareto kedua substrat dalam satu gambar: `py main.py pareto`
(atau tombol "Buat kurva Pareto" di GUI tab 6). Keluaran: `data\_compare\pareto.png` dan `pareto_front.csv`.

## Yang diharapkan dan yang dicari

- Hipotesis dari kontrol tan d: gain 5 dBi dicapai dengan BW jauh lebih sempit dari FR-4 bila geometri tidak dicocokkan ulang; BO pada
  substrat ini mencari seberapa banyak BW bisa dipulihkan pada gain tinggi.
- Prediksi cakupan pita di atas sekitar 45% tidak realistis (BW pecahan sekitar 5% membatasinya); GP bisa terlalu optimis di sana.
- Hasil utama untuk laporan: kurva trade-off BW terhadap gain untuk FR-4 dan RO4350B pada satu gambar.
