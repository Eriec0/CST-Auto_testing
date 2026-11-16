# Toleransi fabrikasi: MicrostripAntena_RO4350B

Syarat lulus: fr 3.3 sampai 3.7 GHz, RL minimum <= -10 dB, BW >= 200 MHz, gain >= 4 dBi.

## Desain sampel 179

Nominal: fr 3.534 GHz, RL -22.1 dB, BW 247.5 MHz, gain 4.43 dBi; syarat BW >= 200 MHz; nominal lulus.

| besaran | nominal | minimum | maksimum | simpangan baku | selisih maks dari nominal |
|---|---|---|---|---|---|
| fr (GHz) | 3.5340 | 3.5080 | 4.3760 | 0.1765 | 0.8420 |
| RL minimum (dB) | -22.14 | -26.43 | -19.04 | 1.46 | 4.28 |
| BW (MHz) | 247.5 | 33.2 | 257.8 | 44.5 | 214.3 |
| gain di fr (dBi) | 4.43 | 2.60 | 4.70 | 0.39 | 1.83 |

| plan | direncanakan | dilewati (geometri) | belum tersimulasi | tersimulasi | lulus | yield |
|---|---|---|---|---|---|---|
| oat | 12 | 1 | 0 | 11 | 10 | 91% |
| corners | 4 | 2 | 0 | 2 | 2 | 100% |
| random | 12 | 2 | 0 | 10 | 10 | 100% |
| semua | 28 | 5 | 0 | 23 | 22 | 96% |

Syarat yang gagal (jumlah skenario): fr di pita 1, BW 1, gain 1.

Skenario yang tidak disimulasikan karena geometri tidak valid: fr_naik (dilewati, geometri tidak valid: DGS keluar dari proyeksi patch); gain_turun (dilewati, geometri tidak valid: DGS keluar dari proyeksi patch); acak7 (dilewati, geometri tidak valid: DGS keluar dari proyeksi patch); acak10 (dilewati, geometri tidak valid: DGS keluar dari proyeksi patch); Lp- (dilewati, geometri tidak valid: DGS keluar dari proyeksi patch).

Tornado: tolerance_MicrostripAntena_RO4350B_s179_tornado.png

Catatan: yield plan random dengan 12 sampel memiliki galat baku sampai sekitar 14 poin persen. OAT dan corners adalah kasus terburuk, bukan peluang. Kalimat laporan hanya boleh memakai angka di tabel ini.
