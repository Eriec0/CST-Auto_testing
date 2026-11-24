# Membuat desain baru

Satu desain adalah satu file di `designs/`. Kode inti (`cstopt/`) tidak perlu diubah selama antena yang dioptimasi memakai satu port dan keluaran yang sama dengan desain U-Slot + DGS: S11, efisiensi, dan directivity dari monitor farfield. MIMO dan array di luar lingkup (butuh matriks S multi port).

## 1. Prasyarat di project CST

1. Parameter geometri di CST bernama PERSIS sama dengan `PARAM_NAMES` di file desain (huruf besar kecil dihitung).
2. Nama parameter tidak boleh sama dengan nama objek VBA CST. Contoh yang ditolak: `tand`; pakai `lossTan`. Uji nama baru di CST sebelum menulis kode yang bergantung padanya.
3. Satu project CST = satu `RUN_NAME` = satu folder `data/<RUN_NAME>/`. Nama file project (tanpa `.cst`) disamakan dengan `RUN_NAME`; bila beda, `run` mencetak peringatan.
4. Macro membuat monitor farfield pada frekuensi yang sama dengan `CST["monitors_ghz"]` (mulai, akhir, langkah) dan satu monitor di `f0_ghz`. Kedua sisi harus sama; perbedaan membuat gain di frekuensi resonansi salah tanpa pesan galat.
5. Parameter ekstra yang ikut berubah (tebal substrat `hs`, lebar saluran `Wf`, `lossTan`) didaftarkan di `EXTRA_BASE`; kolomnya di CSV sampel otomatis dipakai oleh `run`.

## 2. Membuat file desain

```
py tools\new_design.py nama_desain --er 3.66 --tand 0.0037 --h 1.524 --material "Rogers RO4350B"
```

Perintah ini menyalin `designs/_template.py` (atau desain lain lewat `--from`) dan mengganti `NAME`, `RUN_NAME` (bawaan `MicrostripAntena_<nama>`; ubah dengan `--run-name`), `SUBSTRATE`, serta `hs` dan `Wf` (Hammerstad) di `EXTRA_BASE`. Perintah menolak nama tidak valid, file yang sudah ada (kecuali `--force`), dan `RUN_NAME` yang sudah dipakai desain lain.

Sesudahnya edit `designs/nama_desain.py`. Bagian bertanda `[GANTI]` di templat wajib diperiksa:

| Atribut | Isi |
|---|---|
| `PARAM_NAMES`, `BOUNDS` | parameter geometri dan rentangnya (mm) |
| `geometry_problems(p)` | daftar masalah geometri (kosong = valid); dipakai LHS, BO, dan `run` |
| `BASE_PARAMS` | nilai parameter di project CST; model dipulihkan ke nilai ini setelah batch. Tanpa atribut ini `run` memakai baseline FR-4 |
| `EXTRA_BASE` | parameter ekstra dan baselinenya |
| `CST` | pita, batas RL, f0, rentang monitor, ambang BW dan gain untuk laporan |
| `N_INITIAL` | jumlah sampel awal LHS; id lebih besar dianggap hasil BO |
| `TARGETS`, `TRANSFORMS` | kolom yang dimodelkan GPR |
| `STAGES`, `FOCI` | objective dan constraint tiap tahap BO atau fokus manual |

Hook opsional `features(df, d)`: dipanggil saat dataset dimuat, harus mengembalikan DataFrame dengan jumlah dan urutan baris sama. Bila ada, ia MENGGANTIKAN fitur kurva S11 bawaan, jadi panggil `add_s11_features(df, d)` di dalamnya bila fitur itu masih dipakai (templat melakukannya). Kolom baru yang ingin dimodelkan didaftarkan di `TARGETS`. Tanpa hook, perilaku sama seperti dulu.

Rentang awal yang aman untuk substrat baru: skalakan dari desain yang sudah ada (panjang dikali sqrt(eeff lama / eeff baru), celah tetap), seperti yang dilakukan untuk RO4350B.

## 3. Alur kerja

```
py main.py lhs --design nama_desain -n 40            # sampel awal (data/<RUN>/samples/lhs_samples.csv)
py main.py run --design nama_desain --auto-yes       # simulasi CST (Windows)
py main.py qc --design nama_desain                   # pemeriksaan dataset
py main.py curves --run-name <RUN>                   # kurva konsisten dengan CSV
py main.py train --design nama_desain
py main.py suggest --design nama_desain -q 5         # kandidat BO, lalu py main.py run --samples <bo_candidates.csv>
py main.py pareto --runs <RUN>                       # front Pareto, hypervolume, knee
```

Uji kecil dulu: `run --limit 1`, lalu sisanya. Ke substrat lain sebagai seed: `tools/make_seeds.py`. Peringatan: `suggest` untuk fokus selain tahap otomatis sebaiknya memakai `--region-auto` dan `--margin` (lihat `CLAUDE.md`).

## 4. Menguji tanpa CST

Desain demo `designs/_demo_analytic.py` mengganti CST dengan fungsi analitik `mock_response(p, f)`; `tools/mock_run.py` memakainya untuk menulis `batch_lhs.csv`, `curves/`, dan `eff/` dengan kolom dan rumus yang sama dengan `run` (baris dibuat oleh `export.extract`).

```
py tools\test_flow.py          # lhs, mock_run, qc, curves, train, suggest, pareto, sensitivity, validate, report
```

Untuk desain Anda sendiri, tambahkan `mock_response(p, f)` ke file desain yang mengembalikan dict `s11_db`, `eta_rad`, `eta_tot`, `d_dbi` (array sepanjang `f`), lalu `py tools\mock_run.py --design nama_desain --run-name <RUN_UJI>`. Pakai `--run-name` khusus uji agar data tiruan tidak bercampur dengan data CST.

Pemeriksaan lain tanpa CST:

```
py tools\smoke_test.py                                  # semua file desain: atribut wajib, Design terbentuk, LHS valid
py main.py run --design nama_desain --check-samples     # validasi CSV sampel (geometri, kolom ekstra)
```

## 5. Batasan dan jebakan

- Hasil `mock_run` adalah data buatan; jangan dipakai untuk kesimpulan fisika.
- Nilai di desain demo sengaja sederhana (satu resonansi); BW dan gain-nya tidak mewakili antena nyata.
- Fitur turunan kurva untuk antena multi resonansi mungkin butuh hook `features` sendiri; fitur S11 bawaan mengambil dip terdekat ke pita.
- `qc` dan `curves` memakai `--run-name`; `qc` juga menerima `--design`. Konstanta pemeriksaan efisiensi (`--expect-eff`, `--mon-step`) bernilai bawaan FR-4 (9 titik, langkah 0,25 GHz); ubah bila rentang monitor berbeda.
- Nama parameter yang dipakai GUI untuk tabel kandidat (Lp, Wp, LU, WU, WD) hanya preferensi; bila tidak ada, GUI menampilkan 8 kolom pertama.

## Contoh lengkap

Antena kedua dengan geometri berbeda (patch FR-4 berbentuk E, pita 2,4 sampai 2,6 GHz): `designs/eshape_fr4.py` dan `macros/eshape_fr4.bas`; prosedur demonstrasi lewat GUI di `docs/demonstrasi_gui.md`.
Uji kesesuaian macro dan desain tanpa CST: `py tools\test_demo_design.py` (dapat dijadikan acuan untuk desain baru Anda: nama parameter, nilai awal, hs dan Wf, rentang frekuensi dan monitor, serta ambang aturan geometri harus sama di macro dan file desain).
