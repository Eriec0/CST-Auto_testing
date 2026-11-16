# Toleransi fabrikasi: MicrostripAntena_RO4350B

Syarat lulus: fr 3.3 sampai 3.7 GHz, RL minimum <= -10 dB, BW >= 200 MHz, gain >= 4.5 dBi.

## Desain sampel 180

Nominal: fr 3.514 GHz, RL -26.4 dB, BW 228.2 MHz, gain 4.63 dBi; syarat BW >= 200 MHz; nominal lulus.

| besaran | nominal | minimum | maksimum | simpangan baku | selisih maks dari nominal |
|---|---|---|---|---|---|
| fr (GHz) | 3.5140 | 3.4680 | 3.5420 | 0.0172 | 0.0460 |
| RL minimum (dB) | -26.41 | -30.33 | -22.97 | 1.63 | 3.91 |
| BW (MHz) | 228.2 | 215.4 | 235.7 | 4.6 | 12.8 |
| gain di fr (dBi) | 4.63 | 4.48 | 4.66 | 0.05 | 0.16 |

| plan | direncanakan | dilewati (geometri) | belum tersimulasi | tersimulasi | lulus | yield |
|---|---|---|---|---|---|---|
| oat | 12 | 0 | 0 | 12 | 12 | 100% |
| corners | 4 | 0 | 0 | 4 | 3 | 75% |
| random | 12 | 0 | 0 | 12 | 12 | 100% |
| semua | 28 | 0 | 0 | 28 | 27 | 96% |

Syarat yang gagal (jumlah skenario): gain 1.

Tornado: tolerance_MicrostripAntena_RO4350B_s180_tornado.png

Catatan: yield plan random dengan 12 sampel memiliki galat baku sampai sekitar 14 poin persen. OAT dan corners adalah kasus terburuk, bukan peluang. Kalimat laporan hanya boleh memakai angka di tabel ini.
