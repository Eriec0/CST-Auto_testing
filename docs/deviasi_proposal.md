# Deviasi dari proposal

Target proposal: fr 3,3 sampai 3,7 GHz, RL minimum <= -10 dB, BW >= 200 MHz, gain >= 5 dBi (ideal 6 dBi), R2 model >= 0,85.
Semua angka di bawah berasal dari simulasi CST (belum ada fabrikasi atau pengukuran) dan dari berkas di `data/` serta `data/_compare/`.

## 1. Target vs tercapai

| Target | FR-4 h 1,6 mm (sampel 137) | RO4350B h 1,524 mm | Status |
|---|---|---|---|
| fr di 3,3 sampai 3,7 GHz | 3,698 GHz (2 MHz dari tepi atas) | 3,616 (sampel 165); 3,514 (sampel 180) | tercapai |
| RL minimum <= -10 dB | -18,2 dB | -24,9 dan -26,4 dB | tercapai |
| BW >= 200 MHz | 180,6 MHz (90% dari target) | 228,2 MHz (sampel 180, tahan toleransi); 247,5 MHz (sampel 179, tidak tahan toleransi) | FR-4 tidak tercapai; RO4350B tercapai |
| gain >= 5 dBi | 2,80 dBi | 5,03 dBi (sampel 165) | FR-4 tidak tercapai; RO4350B tercapai |
| BW >= 200 MHz dan gain >= 5 dBi sekaligus | tidak | tidak: BW 228,2 pada gain 4,63; gain 5,03 pada BW 158,6 | tidak tercapai di kedua substrat |
| R2 model >= 0,85 | lihat bagian 3 | lihat bagian 3 | sebagian |

Pada RO4350B front Pareto berisi 22 titik: gain >= 5 dBi hanya sampai BW 158,6 MHz, gain >= 4,5 dBi sampai 234,2 MHz, dan BW tertinggi 247,5 MHz pada gain 4,43 dBi.
Kemiringan trade-off dari (158,6 MHz; 5,03 dBi) ke (247,5 MHz; 4,43 dBi) sekitar -0,0067 dB per MHz.

Pemilihan desain RO4350B. Desain dengan BW tertinggi (sampel 179) tidak dipakai sebagai desain utama karena tidak tahan toleransi (bagian 6). Laporan otomatis (`py main.py report --min-yield 90`) memisahkan dua hal:
desain BW tertinggi dan desain rekomendasi, yaitu BW tertinggi di antara desain yang punya data toleransi dengan yield di atas ambang. Ambang 90% dan kriteria lulus (BW minimal 90% BW nominal, gain minimal 4,5 dBi sesuai `GAIN_MIN_DBI` desain, fr di pita, RL minimum <= -10 dB) adalah konvensi, bukan hasil pengukuran.
Hanya sampel 165, 179, dan 180 yang punya data toleransi, sehingga rekomendasi (sampel 180) berlaku di antara ketiganya. Sampel 176 dan 178 di front (BW 234,2 dan 228,9 MHz) belum diuji.

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

## 4. Fase pengumpulan data RO4350B (rentang parameter)

Rentang parameter RO4350B dilebarkan di tengah pengumpulan (WD dari 14 ke 18 mm, LI dari 7,55 ke 8,20 mm; tercatat di `designs/uslot_dgs_ro4350b.py`). Data menunjukkan dua fase:
- Sampel 17 sampai 125: BW fisibel terbaik naik pelan dari 109 ke 134 MHz (dataran). Pada sampel 46 sampai 120 nilai WD maksimum persis 10,0 mm. Batas awal 10 mm diduga dari pola ini dan belum diverifikasi dari riwayat git.
- Setelah WD dilebarkan, wilayah WD 15 sampai 18 mm dan LI sekitar 5,8 sampai 6,3 mm memberi BW 190 sampai 247 MHz. Seluruh 13 sampel dengan BW >= 190 MHz berada di wilayah itu (sampel pertama 146). Lompatan terbesar pada terbaik sejauh ini: 181,0 ke 214,1 MHz pada sampel 146, dengan WD maksimum 14,00 mm sebelumnya dan 18,00 mm sesudahnya.
- Akibatnya histogram BW tidak merata: 91 dari 185 sampel berada di 100 sampai 140 MHz dan hanya 2 sampel di 200 sampai 220 MHz. Korelasi Spearman WD terhadap BW pada sampel fisibel +0,89.

Tafsir: loncatan itu mencerminkan bahwa optimum berada di luar rentang awal dan BO baru menemukannya setelah rentang dilebarkan; bukan ketidakstabilan BO. Dugaan yang belum diuji: validasi maju RO4350B yang lemah (bagian 3) sebagian berasal dari pergeseran wilayah ini.
Pelajaran untuk desain baru: mulai dengan rentang fisik yang lebar lalu persempit dengan `--region-auto` atau `--region-adapt`, dan periksa peringatan menempel batas di laporan (bagian 8).

## 5. Pola radiasi dan metrik tambahan (simulasi, irisan bidang utama)

Dari berkas `ff/` pada monitor 3,5 GHz (laporan bagian 9). Yang tersimpan adalah directivity, bukan gain; gain di tabel hasil dihitung di fr saja. Pola 3D dan impedansi masukan belum ada (fitur lanjutan).

| Sampel | Peran | Directivity puncak (dBi) | HPBW bidang H / E (derajat) | F/B bidang H / E (dB) |
|---|---|---|---|---|
| 179 | BW tertinggi | 5,17 | 94,1 / 82,6 | 3,42 / 3,11 |
| 180 | rekomendasi | 5,27 | 93,3 / 83,2 | 3,63 / 3,33 |
| 165 | knee Pareto | 5,67 | 92,7 / 85,4 | 5,36 / 4,95 |

Puncak berada di boresight. Cross pol di bidang H sekitar 23 dB di bawah komponen utama dalam sektor HPBW; di bidang E nilainya di atas 60 dB dan hanya mencerminkan batas numerik pada geometri simetris, bukan nilai yang bisa diukur.
Rasio depan belakang rendah (3,1 sampai 5,4 dB) dengan directivity di arah belakang 0,3 sampai 1,75 dBi. Dugaan: DGS pada bidang ground ikut meradiasi ke belakang. Dugaan ini belum diuji (misalnya dengan menyimulasikan satu desain tanpa DGS atau dengan ground lebih besar).

## 6. Keterbatasan yang dilaporkan terbuka

- Satu topologi (U-slot dengan DGS dumbbell), dua substrat, hasil simulasi; tidak ada fabrikasi.
- Mesh rapat diuji pada tiga desain RO4350B (selisih fr paling besar 2 MHz, BW 0,34%); tidak pada seluruh front.
- Toleransi dengan hs +/-10% dan 28 skenario per desain. Yield (baris `semua`): desain 165 100% (20 dari 20 yang tersimulasi; 8 dari 28 skenario dilewati karena geometri; gain turun sampai 4,81 dBi); desain 179 17,4% (4 dari 23; LI + 0,1 mm meruntuhkan resonansi: fr 4,376 GHz, BW 33,2 MHz, gain 2,60 dBi); desain 180 96,4% (27 dari 28; BW minimum 215,4 MHz). Satu skenario desain 180 yang gagal (sampel 18024) gagal karena gain 4,476 dBi, sedikit di bawah batas 4,5 dBi; BW-nya 229,3 MHz. Yield dari sampel acak bukan peluang.
- Sensitivitas FR-4: korelasi mentah WD dengan BW pecahan +0,77, tetapi relevansi ARD dan Sobol WD untuk BW hampir nol; penyebabnya belum dibuktikan.
- Desain BW tertinggi menempel batas parameter di kedua substrat: RO4350B sampel 179 pada WD 18,0 mm (sekitar 58% lebar patch), dan FR-4 sampel 137 pada WD 8,0 mm (batas atas FR-4 dilebarkan 5, 6, lalu 8 mm). BW di atas 230 MHz pada RO4350B bergantung pada pelebaran batas.
- Kesimpulan bahwa batas FR-4 berasal dari rugi substrat (bagian 2) didukung pilot h dan kontrol tan delta pada geometri tetap. Tetapi pencarian FR-4 sendiri berhenti di batas WD 8 mm, sehingga efek pelebaran lebih lanjut tidak diuji; kesimpulan itu sebaiknya ditulis sebagai bukti kuat, bukan bukti tunggal.
- Satu seed dan satu putaran per substrat; perbandingan FR-4 dan RO4350B tidak setara (156 dan 185 sampel, rentang berubah di tengah pengumpulan, syarat gain berbeda), sehingga hypervolume antar substrat hanya acuan kasar.
- Gain diukur di fr, bukan di seluruh pita; pola radiasi hanya dua irisan bidang utama pada 3,5 GHz.
- Substrat project CST RO4350B. Setelah run toleransi 12 November, project RO4350B sempat berisi hs 1,6 mm dan Wf 3,11 mm (impedansi saluran sekitar 54 ohm) karena baseline bawaan kode memakai nilai FR-4; ini diperbaiki pada 23 November. Data utama dikumpulkan pada hs 1,524 mm dan Wf 3,336 mm: simulasi ulang titik awal 1 pada nilai itu mereproduksi hasil lama persis (selisih 0,0 pada fr, BW, RL, dan gain), sedangkan pada hs 1,6 dan Wf 3,11 fr titik itu bergeser minus 16 MHz. Data toleransi menyetel hs dan Wf sendiri sehingga tidak terpengaruh.
- Tidak ada pembanding surrogate atau optimizer lain karena di luar lingkup proposal (surrogate GPR dengan BO).

## 7. Kontribusi yang bisa diklaim

Alur otomatis (CST, surrogate GPR, BO dengan region, margin, dan komposit), diagnosis batas fisik lewat pilot h dan kontrol tan delta, perbandingan dua substrat dengan kurva Pareto dan hypervolume,
validasi maju dan analisis toleransi, serta dataset dan kode yang dapat dipakai ulang. Jangan mengklaim kebaruan analisis toleransi (topik mapan).
