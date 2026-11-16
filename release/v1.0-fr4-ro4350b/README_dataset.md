# Dataset simulasi antena mikrostrip U-slot dengan DGS dumbbell (v1.0-fr4-ro4350b)

Dibuat: 2026-11-16. Seluruh data berasal dari simulasi CST (bukan pengukuran).
Lisensi: belum ditentukan (isi sebelum diunggah, mis. CC BY 4.0).

## Run

| run | baris | desain | substrat | parameter geometri |
|---|---|---|---|---|
| MicrostripAntena | 156 | uslot_dgs_fr4 | FR-4 (lossy): er 4.3, tan delta 0.025, h 1.6 mm (nilai di file desain) | Lp, Wp, LU, WU, gU, PU, LI, LD, WD, gD, PD |
| MicrostripAntena_RO4350B | 185 | uslot_dgs_ro4350b | Rogers RO4350B (lossy): er 3.66, tan delta 0.0037, h 1.524 mm (nilai di file desain) | Lp, Wp, LU, WU, gU, PU, LI, LD, WD, gD, PD |
| MicrostripAntena_RO4350B_fine | 3 | tidak ada | tidak diketahui |  |
| MicrostripAntena_RO4350B_tol | 71 | tidak ada | tidak diketahui |  |
| MicrostripAntena_control_tand | 7 | tidak ada | tidak diketahui |  |
| MicrostripAntena_pilot_h | 8 | tidak ada | tidak diketahui |  |

## Kolom utama (satuan mm bila panjang)

| kolom | arti |
|---|---|
| sample_id | nomor sampel dalam run |
| fr_ghz | frekuensi resonansi (GHz): frekuensi minimum S11 |
| rl_min_db | nilai minimum S11 (dB) |
| bw_mhz | lebar pita S11 <= -10 dB di sekitar minimum global (MHz); 0 bila RL minimum > -10 dB |
| band_cover_pct | persentase frekuensi di 3,3 sampai 3,7 GHz dengan S11 <= -10 dB |
| s11_at_f0_db | S11 di 3,5 GHz (dB) |
| gain_fr_ieee_dbi | gain IEEE di frekuensi resonansi (D + 10 log eta), dBi |
| eta_rad_fr | efisiensi radiasi di frekuensi resonansi |
| d_peak_fr_dbi | directivity puncak di frekuensi resonansi (dBi) |
| hs | tebal substrat (mm), bila kolom ada |
| Wf | lebar jalur catu (mm), bila kolom ada |

Kolom lain (mis. eta_tot, vswr, gain_real_dbi, feasible_all) mengikuti `cstopt/cst/export.py` di repositori kode.
Run berakhiran `_tol` adalah skenario toleransi fabrikasi (sample_id = ID desain * 100 + k; berkas `*_meta.csv` di `samples/` memberi plan dan skenarionya),
`_fine` adalah simulasi ulang dengan mesh lebih halus, dan `_pilot_h` adalah pilot ketebalan substrat.

## Berkas dan checksum

Lihat `CHECKSUMS.sha256` (SHA256 tiap berkas).
