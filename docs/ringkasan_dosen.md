# Ringkasan untuk dosen pembimbing

Judul kerja: optimasi otomatis antena mikrostrip U-slot dengan DGS dumbbell menggunakan CST, surrogate GPR, dan Bayesian optimization (BO), pada FR-4 dan Rogers RO4350B.

## Hasil utama

| Substrat | Sampel | Hasil terbaik | Catatan |
|---|---|---|---|
| FR-4 h 1,6 mm | 156 | BW 180,6 MHz pada gain 2,80 dBi (fr 3,698 GHz, RL -18,2 dB) | 90% dari target BW 200 MHz; BO: 52 dari 70 sampel memenuhi syarat, sampling acak: 0 dari 80 |
| RO4350B h 1,524 mm | 185 | gain >= 5 dBi sampai BW 158,6 MHz; BW 228,2 MHz pada gain 4,63 dBi (tahan toleransi); BW nominal tertinggi 247,5 MHz pada 4,43 dBi | front Pareto 22 titik; hypervolume 1324,9 vs 518,5 (FR-4) dalam MHz*dBi |

Kurva Pareto BW terhadap gain untuk dua substrat: `data/_compare/pareto.png` (bentuk tangga, knee ditandai, hypervolume per substrat). Tabel lengkap target vs tercapai: `data/_compare/report.md` (dibuat `py main.py report`).

## Yang tidak tercapai dan kenapa

- BW >= 200 MHz dan gain >= 5 dBi sekaligus tidak tercapai di kedua substrat; ada trade-off sekitar -0,0067 dB per MHz pada RO4350B.
- FR-4: efisiensi radiasi maksimum 0,51 (gain 5 dBi butuh sekitar 0,67) dan BW pecahan menjenuh sekitar 5%. Pilot h dan kontrol tan delta menunjukkan batasnya berasal dari rugi substrat, bukan dari geometri.
- Model surrogate: R2 tinggi pada uji acak tetapi lebih rendah pada validasi maju (RO4350B: BW 0,73; fr 0,89; gain 0,64 di dalam pita). BO karena itu dipandu margin dan region.
- Rincian dan bukti: `docs/deviasi_proposal.md`.

## Ketahanan desain RO4350B

Mesh rapat lulus untuk tiga desain (selisih fr paling besar 2 MHz, BW 0,34%). Toleransi (28 skenario): desain 180 menjaga BW di atas 200 MHz; desain 165 gain turun sampai 4,81 dBi; desain 179 runtuh pada LI + 0,1 mm (tidak disarankan sebagai desain utama).

## Yang dapat dipakai ulang

Alur: `status`, `run`, `qc`, `curves`, `train`, `suggest` (BO), `validate`, `sensitivity`, `backtest`, `pareto`, `report`, ditambah `tools/make_tolerance.py` dan `tools/analyze_tolerance.py`.
Desain baru satu port ditambahkan sebagai file di `designs/` tanpa mengubah bagian ML; bagian CST masih memuat konstanta khusus desain ini (generalisasi tahap P1-1 belum selesai). Dataset dapat dikemas dengan `tools/package_dataset.py` untuk diunggah (opsional Zenodo).

## Yang diminta dari dosen

Persetujuan atas dua target operasional (FR-4: BW maksimum dengan gain >= 2,5 dBi; RO4350B: dua tingkat, gain >= 5 dBi dan BW tertinggi) dan atas bagian "Deviasi dari proposal" sebagai bentuk laporan akhir.
