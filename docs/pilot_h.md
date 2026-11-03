# Pilot ketebalan substrat (h), FR-4

Tujuan: melihat pengaruh h terhadap BW, cakupan pita, efisiensi, dan gain pada dua desain terbaik, dengan geometri lain tetap.
Tanpa mengubah macro: `hs` dan `Wf` sudah parameter CST dan diubah langsung oleh `py main.py run`.

Sampel (`data/MicrostripAntena_pilot_h/samples/pilot_h.csv`, 8 baris):
- id 1 sampai 4: geometri sampel 109 (fr 3,512 GHz, BW 150,6 MHz) pada h = 1,6; 2,0; 2,4; 3,2 mm
- id 5 sampai 8: geometri sampel 137 (fr 3,698 GHz, BW 180,6 MHz) pada h yang sama
- `Wf` mengikuti h untuk 50 ohm (Hammerstad, er 4,3): 3,11 (h 1,6, nilai macro); 3,89; 4,67; 6,23 mm

Baris h = 1,6 adalah kontrol: harus mereproduksi hasil asli (fr selisih di bawah sekitar 10 MHz).

## Perintah (PowerShell, di root repo, CST terbuka dengan cst_projects\MicrostripAntena.cst)

```
py main.py run --check-samples --run-name MicrostripAntena_pilot_h --samples data\MicrostripAntena_pilot_h\samples\pilot_h.csv
py main.py run --run-name MicrostripAntena_pilot_h --samples data\MicrostripAntena_pilot_h\samples\pilot_h.csv --auto-yes --limit 1
py main.py run --run-name MicrostripAntena_pilot_h --samples data\MicrostripAntena_pilot_h\samples\pilot_h.csv --auto-yes
py tools\analyze_pilot_h.py
```

Langkah kedua menjalankan satu kontrol saja (sampel 1). Langkah ketiga melanjutkan sisanya (sampel yang sudah ada dilewati).
Hasil: `data\MicrostripAntena_pilot_h\` (batch_lhs.csv, figures\pilot_h.png, pilot_h_summary.csv).

## Cara membaca hasil

- Kontrol tidak reproduksi (fr selisih lebih dari sekitar 10 MHz): berhenti dan periksa pengaturan CST sebelum percaya hasil lain.
- BW pecahan dan cakupan pita naik dengan h sementara efisiensi tidak turun jauh: pilih h terbaik untuk putaran BO berikutnya.
- Efisiensi turun tajam saat h naik: tetap di 1,6 mm.
- fr bergeser keluar pita: wajar, geometri perlu diskalakan ulang; BO yang menyesuaikan.

## Hasil (8 simulasi, geometri tidak dioptimasi ulang)

Rasio terhadap h = 1,6 mm (baseline 109 / 137):

| h (mm) | BW | efisiensi | selisih fr (MHz) |
|---|---|---|---|
| 2,0 | 1,06x / 1,00x | 0,95x / 0,94x | +20 / +30 |
| 2,4 | 1,04x / 1,05x | 0,91x / 0,94x | +38 / +56 |
| 3,2 | 0,92x / 0,83x | 0,91x / 0,90x | +48 / +82 |

Baris kontrol h = 1,6 identik dengan dataset utama. BW naik paling banyak 5 sampai 6% di h 2,0 sampai 2,4 mm lalu turun;
efisiensi turun monoton sekitar 10%; gain datar (2,6 sampai 2,95 dBi) karena directivity naik; fr naik dengan h dan pencocokan
memburuk karena geometri disetel untuk 1,6 mm. BW pecahan maksimum 5,04% tetap di plateau sekitar 5%.
Keputusan: tetap h = 1,6 mm; h tidak ditambahkan ke BO. Keterbatasan: dua baseline, tanpa optimasi ulang pada tiap h.

