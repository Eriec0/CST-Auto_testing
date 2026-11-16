# Toleransi fabrikasi: MicrostripAntena_RO4350B

Syarat lulus: fr 3.3 sampai 3.7 GHz, RL minimum <= -10 dB, BW >= 90% BW nominal, gain >= 4.5 dBi.

## Desain sampel 165

Nominal: fr 3.616 GHz, RL -24.9 dB, BW 158.6 MHz, gain 5.03 dBi; syarat BW >= 142.7 MHz; nominal lulus.

| besaran | nominal | minimum | maksimum | simpangan baku | selisih maks dari nominal |
|---|---|---|---|---|---|
| fr (GHz) | 3.6160 | 3.5880 | 3.6640 | 0.0206 | 0.0480 |
| RL minimum (dB) | -24.90 | -27.55 | -22.92 | 1.33 | 2.65 |
| BW (MHz) | 158.6 | 151.2 | 164.2 | 3.8 | 7.4 |
| gain di fr (dBi) | 5.03 | 4.81 | 5.09 | 0.08 | 0.22 |

| plan | direncanakan | dilewati (geometri) | belum tersimulasi | tersimulasi | lulus | yield |
|---|---|---|---|---|---|---|
| oat | 12 | 1 | 0 | 11 | 11 | 100% |
| corners | 4 | 2 | 0 | 2 | 2 | 100% |
| random | 12 | 5 | 0 | 7 | 7 | 100% |
| semua | 28 | 8 | 0 | 20 | 20 | 100% |

Skenario yang tidak disimulasikan karena geometri tidak valid: fr_turun (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU); bw_turun (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU); acak1 (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU); acak2 (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU); acak3 (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU); acak9 (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU); acak11 (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU); gU+ (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU).

Tornado: tolerance_MicrostripAntena_RO4350B_s165_tornado.png

## Desain sampel 179

Nominal: fr 3.534 GHz, RL -22.1 dB, BW 247.5 MHz, gain 4.43 dBi; syarat BW >= 222.7 MHz; nominal TIDAK lulus.

| besaran | nominal | minimum | maksimum | simpangan baku | selisih maks dari nominal |
|---|---|---|---|---|---|
| fr (GHz) | 3.5340 | 3.5080 | 4.3760 | 0.1765 | 0.8420 |
| RL minimum (dB) | -22.14 | -26.43 | -19.04 | 1.46 | 4.28 |
| BW (MHz) | 247.5 | 33.2 | 257.8 | 44.5 | 214.3 |
| gain di fr (dBi) | 4.43 | 2.60 | 4.70 | 0.39 | 1.83 |

| plan | direncanakan | dilewati (geometri) | belum tersimulasi | tersimulasi | lulus | yield |
|---|---|---|---|---|---|---|
| oat | 12 | 1 | 0 | 11 | 1 | 9% |
| corners | 4 | 2 | 0 | 2 | 1 | 50% |
| random | 12 | 2 | 0 | 10 | 2 | 20% |
| semua | 28 | 5 | 0 | 23 | 4 | 17% |

Syarat yang gagal (jumlah skenario): fr di pita 1, BW 1, gain 19.

Skenario yang tidak disimulasikan karena geometri tidak valid: fr_naik (dilewati, geometri tidak valid: DGS keluar dari proyeksi patch); gain_turun (dilewati, geometri tidak valid: DGS keluar dari proyeksi patch); acak7 (dilewati, geometri tidak valid: DGS keluar dari proyeksi patch); acak10 (dilewati, geometri tidak valid: DGS keluar dari proyeksi patch); Lp- (dilewati, geometri tidak valid: DGS keluar dari proyeksi patch).

Tornado: tolerance_MicrostripAntena_RO4350B_s179_tornado.png

## Desain sampel 180

Nominal: fr 3.514 GHz, RL -26.4 dB, BW 228.2 MHz, gain 4.63 dBi; syarat BW >= 205.3 MHz; nominal lulus.

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
