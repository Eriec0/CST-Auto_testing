# Deviasi dari proposal

Target proposal: fr 3,3 sampai 3,7 GHz, RL minimum <= -10 dB, BW >= 200 MHz, gain >= 5 dBi (ideal 6 dBi), R2 model >= 0,85.
Semua angka di bawah berasal dari simulasi CST (belum ada fabrikasi atau pengukuran) dan dari berkas di `data/` serta `data/_compare/`.

## 1. Target vs tercapai

| Target | FR-4 h 1,6 mm (sampel 137) | RO4350B h 1,524 mm | Status |
|---|---|---|---|
| fr di 3,3 sampai 3,7 GHz | 3,698 GHz (2 MHz dari tepi atas) | 3,616 (sampel 165); 3,514 (sampel 180) | tercapai |
| RL minimum <= -10 dB | -18,2 dB | -24,9 dan -26,4 dB | tercapai |
| BW >= 200 MHz | 180,6 MHz (90% dari target) | 228,2 MHz (sampel 180); 247,5 MHz (sampel 179) | FR-4 tidak tercapai; RO4350B tercapai |
| gain >= 5 dBi | 2,80 dBi | 5,03 dBi (sampel 165) | FR-4 tidak tercapai; RO4350B tercapai |
| BW >= 200 MHz dan gain >= 5 dBi sekaligus | tidak | tidak: BW 228,2 pada gain 4,63; gain 5,03 pada BW 158,6 | tidak tercapai di kedua substrat |
| R2 model >= 0,85 | lihat bagian 3 | lihat bagian 3 | sebagian |

Pada RO4350B front Pareto berisi 22 titik: gain >= 5 dBi hanya sampai BW 158,6 MHz, gain >= 4,5 dBi sampai 234,2 MHz, dan BW tertinggi 247,5 MHz pada gain 4,43 dBi.
Kemiringan trade-off dari (158,6 MHz; 5,03 dBi) ke (247,5 MHz; 4,43 dBi) sekitar -0,0067 dB per MHz.

## 2. Target yang diubah dan alasannya

Target operasional memakai dua tingkat dan selalu ditampilkan bersama selisihnya terhadap proposal:
- FR-4: maksimalkan BW dengan gain >= 2,5 dBi (hasil 180,6 MHz pada 2,80 dBi).
- RO4350B: (A) gain >= 5 dBi dengan BW setinggi mungkin (158,6 MHz); (B) BW setinggi mungkin dengan gain >= 4 dBi (247,5 MHz nominal; 228,2 MHz pada desain yang tahan toleransi).

Bukti perubahan:
1. Batas efisiensi FR-4. Efisiensi radiasi maksimum seluruh data 0,51 dan directivity maksimum 6,73 dBi; gain 5 dBi membutuhkan efisiensi sekitar 0,67. Gain terbaik seluruh data 3,13 dBi.
2. Plateau BW pecahan FR-4 sekitar 5% (maksimum 4,88% di dalam pita, 5,05% di seluruh data). BW 200 MHz butuh 5,4% pada 3,7 GHz atau 5,7% pada 3,5 GHz. Dengan batas atas fr dilonggarkan sampai 3,9 GHz, BW terbaik hanya 195,4 MHz.
3. Pilot ketebalan h (FR-4, geometri tetap, h 1,6 sampai 3,2 mm): BW naik paling banyak 5 sampai 6% lalu turun, efisiensi turun sekitar 10%, gain datar. Keputusan: tetap h = 1,6 mm.
4. Kontrol tan delta (FR-4, geometri tetap, 0,025 ke 0,001): efisiensi 0,47 ke 0,82 dan gain 2,77 ke 5,23 dBi, tetapi BW 150 MHz turun ke 0 (RL minimum -20,5 ke -9,8 dB karena geometri tidak dicocokkan ulang). Ada trade-off BW dan gain, dan plateau BW pecahan di FR-4 sebagian berasal dari rugi dielektrik.
5. RO4350B (tan delta lebih kecil; nilai di file desain er 3,66 dan tan delta 0,0037, konfirmasikan dengan material library CST) melampaui plateau 5%: BW pecahan 7,0% pada sampel 179 dan efisiensi 0,83 sampai 0,86 pada desain front tertinggi. Batas di FR-4 karena itu berasal dari rugi substrat, bukan batas topologi. Pada RO4350B kendalanya berpindah menjadi trade-off BW dan gain.

## 3. R2 model

| Ukuran | FR-4 | RO4350B |
|---|---|---|
| Uji acak (R2 data uji) | BW 0,98; RL minimum 0,86; fr 0,76; gain 0,69 | BW 0,962; fr 0,939; RL minimum 0,504; gain 0,895 |
| Validasi silang (R2_cv) | BW 0,94 sampai 0,96; fr 0,65 sampai 0,69; gain 0,27 sampai 0,5 | BW 0,820; fr -0,183; gain 0,933 |
| Validasi maju di dalam pita (BO memakai model begini) | BW 0,65; fr -0,98 | BW 0,73; fr 0,89; gain 0,64 |

Target R2 >= 0,85 tercapai pada uji acak untuk sebagian target, tidak pada validasi maju. Ukuran maju yang relevan untuk BO karena model dipakai mengekstrapolasi.
Ketidakpastian model terlalu sempit (cakupan interval 95% pada RO4350B: gain 65%, fr 81%), jadi BO dipandu margin dan region, bukan oleh sigma model.

## 4. Keterbatasan yang dilaporkan terbuka

- Satu topologi (U-slot dengan DGS dumbbell), dua substrat, hasil simulasi; tidak ada fabrikasi.
- Mesh rapat diuji pada tiga desain RO4350B (selisih fr paling besar 2 MHz, BW 0,34%); tidak pada seluruh front.
- Toleransi dengan hs +/-10% dan 28 skenario per desain. Desain 165: gain turun sampai 4,81 dBi dan 8 dari 28 skenario dilewati karena geometri. Desain 179: LI + 0,1 mm meruntuhkan resonansi (fr 4,376 GHz, BW 33,2 MHz). Desain 180: BW tetap di atas 200 MHz pada seluruh 28 skenario. Yield dari 12 sampel acak bukan peluang.
- Sensitivitas FR-4: korelasi mentah WD dengan BW pecahan +0,77, tetapi relevansi ARD dan Sobol WD untuk BW hampir nol; penyebabnya belum dibuktikan.
- Desain BW tertinggi menempel batas parameter (WD 18,0 mm, sekitar 57 sampai 61% lebar patch); BW di atas 230 MHz bergantung pada pelebaran batas.

## 5. Kontribusi yang bisa diklaim

Alur otomatis (CST, surrogate GPR, BO dengan region, margin, dan komposit), diagnosis batas fisik lewat pilot h dan kontrol tan delta, perbandingan dua substrat dengan kurva Pareto dan hypervolume,
validasi maju dan analisis toleransi, serta dataset dan kode yang dapat dipakai ulang. Jangan mengklaim kebaruan analisis toleransi (topik mapan).
