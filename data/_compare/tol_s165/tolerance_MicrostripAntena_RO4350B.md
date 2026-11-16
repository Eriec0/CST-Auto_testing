# Toleransi fabrikasi: MicrostripAntena_RO4350B

Syarat lulus: fr 3.3 sampai 3.7 GHz, RL minimum <= -10 dB, BW >= 90% BW nominal, gain >= 5 dBi.

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
| oat | 12 | 1 | 0 | 11 | 9 | 82% |
| corners | 4 | 2 | 0 | 2 | 0 | 0% |
| random | 12 | 5 | 0 | 7 | 6 | 86% |
| semua | 28 | 8 | 0 | 20 | 15 | 75% |

Syarat yang gagal (jumlah skenario): gain 5.

Skenario yang tidak disimulasikan karena geometri tidak valid: fr_turun (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU); bw_turun (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU); acak1 (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU); acak2 (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU); acak3 (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU); acak9 (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU); acak11 (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU); gU+ (dilewati, geometri tidak valid: WU terlalu sempit terhadap gU).

Tornado: tolerance_MicrostripAntena_RO4350B_s165_tornado.png

Catatan: yield plan random dengan 12 sampel memiliki galat baku sampai sekitar 14 poin persen. OAT dan corners adalah kasus terburuk, bukan peluang. Kalimat laporan hanya boleh memakai angka di tabel ini.
