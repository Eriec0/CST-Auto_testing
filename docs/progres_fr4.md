# Progres dan hasil: substrat FR-4

Status berdasarkan 155 sampel (`data/MicrostripAntena/batch_lhs.csv`). Target proposal: fr 3,3 sampai 3,7 GHz,
RL minimum <= -10 dB, BW >= 200 MHz, gain >= 5 dBi.

## Proses

| Tahap | Sampel (id) | Keterangan |
|---|---|---|
| LHS maximin | 1 sampai 80 | sampel awal, 11 parameter |
| BO Tahap 1 | 81 sampai 85 | meminimalkan `rl_band_min_db` (belum ada sampel feasible) |
| BO Tahap 2 | 86 sampai 155 | memaksimalkan `bw_mhz`, beralih otomatis setelah ada sampel feasible |

Rentang parameter (`BOUNDS`) dilebarkan tiga kali sesuai peringatan "menempel batas": Lp 20-23 menjadi 18-25 lalu 15-25,
LU 6-10,5 menjadi 5-12 lalu 3-12, WU 7-13 menjadi 6-13 lalu 4,5-13, WD 2-5 menjadi 2-6 lalu 2-8.

## Hasil

Efektivitas BO terhadap sampling acak: dari 80 sampel LHS tidak ada yang memenuhi constraint Tahap 2 (0 dari 80),
sedangkan 52 dari 70 sampel BO Tahap 2 memenuhinya.

Hasil terbaik di dalam pita 3,3 sampai 3,7 GHz:

| Kriteria | Target | Sampel 137 | Sampel 139 (margin fr lebih aman) |
|---|---|---|---|
| fr | 3,3 sampai 3,7 GHz | 3,698 GHz | 3,682 GHz |
| RL minimum | <= -10 dB | -18,2 dB | -18,4 dB |
| BW | >= 200 MHz | 180,6 MHz | 178,1 MHz |
| Gain | >= 5 dBi | 2,80 dBi | 2,72 dBi |

Akurasi surrogate GPR (kernel RBF ARD, split 80/20, R2 data uji): `bw_mhz` 0,98, `rl_min_db` 0,86 (memenuhi 0,85);
`fr_ghz` 0,76 dan `gain_fr_ieee_dbi` 0,69 (belum). Lonjakan mode (dip terdalam berpindah) menyulitkan model `fr_ghz`.

## Mengapa 200 MHz dan 5 dBi tidak tercapai di FR-4

- BW dan fr naik bersamaan: mengecilkan Lp dan melebarkan WD menaikkan BW sekaligus fr. Korelasi BW pecahan dengan Lp
  -0,77 dan dengan WD +0,85; korelasi fr dengan Lp -0,75. Desain dengan BW terbesar karena itu cenderung berada di atas 3,7 GHz.
- BW pecahan (BW/fr) menjenuh di sekitar 5% (maksimum 4,88% di dalam pita, 5,05% di seluruh data). BW 200 MHz butuh 5,4% pada
  3,7 GHz atau 5,7% pada 3,5 GHz. Dengan batas atas fr dilonggarkan sampai 3,9 GHz, BW terbaik hanya 195,4 MHz.
- Efisiensi radiasi maksimum 0,51 dan directivity maksimum 6,73 dBi. Gain 5 dBi membutuhkan efisiensi sekitar 0,67
  (6 dBi sekitar 0,85). Gain terbaik di seluruh data 3,13 dBi.

Kesimpulan: pada FR-4 (h = 1,6 mm, rugi dielektrik besar) BO menemukan kompromi terbaik sekitar 180 MHz dan sekitar 2,8 dBi;
target proposal membutuhkan substrat berbeda (rugi lebih kecil dan/atau lebih tebal).

## Berikutnya

1. Bekukan hasil FR-4 dan susun hasil akhir (tabel di atas, kurva S11 desain terbaik, konvergensi BO, parity GPR).
2. Uji substrat lain dengan alur yang sama (file desain baru di `designs/`).
