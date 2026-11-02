# Kontrol loss tangent (tan d), FR-4

Tujuan: memisahkan efek rugi material dari efek geometri. Geometri dan h = 1,6 mm tetap; hanya loss tangent (tan d) yang diubah.
Ini kontrol diagnostik, bukan pergantian substrat (epsilon_r tetap 4,3).

Sampel (`data/MicrostripAntena_control_tand/samples/control_tand.csv`, 7 baris):
- id 1: sampel 109 pada tan d = 0,025 (kontrol, harus mereproduksi hasil asli)
- id 2 sampai 4: sampel 109 pada tan d = 0,010; 0,004; 0,001
- id 5 sampai 7: sampel 137 pada tan d yang sama

Acuan tan d: 0,025 = FR-4 (lossy) bawaan CST; 0,004 kira kira laminat rugi rendah (sebanding Rogers 4350B pada literatur proposal); 0,001 hampir tanpa rugi (diagnostik).

## A. Siapkan material berparameter di CST (sekali)

Nama `tand` ditolak CST (bentrok dengan nama objek VBA), jadi parameternya bernama `lossTan`.

Buka `cst_projects\MicrostripAntena.cst`.
1. Buka Parameter List (tab Modeling atau Home, tergantung versi CST) dan tambah parameter baru: nama `lossTan`, nilai `0.025`.
2. Di Navigator Tree buka Materials, klik dua kali "FR-4 (lossy)". Pada bagian dielectric loss, isi kolom Tan delta dengan `lossTan`
   (ketik persis seperti itu). Jangan ubah Epsilon (4,3), frekuensi, atau model loss. OK, lalu simpan project.
3. Pastikan nilai parameter `lossTan` tetap 0.025 (baseline). Batch akan mengembalikannya ke 0,025 di akhir.

Bila `lossTan` juga ditolak, pakai salah satu nama ini: `dLoss`, `tanDelta`, atau `tdelta` (semuanya sudah dikenali kode).
Setelah CST menerima satu nama, ganti nama kolom di baris pertama CSV sampel agar sama, misalnya untuk `tanDelta`:

```
$f = "data\MicrostripAntena_control_tand\samples\control_tand.csv"
(Get-Content $f -Raw) -replace 'lossTan','tanDelta' | Set-Content $f
```

Nama parameter di CST dan nama kolom di CSV harus sama persis. Hanya satu nama yang dipakai.

## B. Perintah (PowerShell, root repo, CST terbuka dengan project itu)

```
py main.py run --check-samples --run-name MicrostripAntena_control_tand --samples data\MicrostripAntena_control_tand\samples\control_tand.csv
py main.py run --run-name MicrostripAntena_control_tand --samples data\MicrostripAntena_control_tand\samples\control_tand.csv --auto-yes --limit 1
py main.py run --run-name MicrostripAntena_control_tand --samples data\MicrostripAntena_control_tand\samples\control_tand.csv --auto-yes
py tools\analyze_control_tand.py
```

Langkah kedua menjalankan kontrol saja (sampel 1): fr harus sekitar 3,512 GHz, BW sekitar 150,6 MHz, eta sekitar 0,474.
Bila fr selisih lebih dari sekitar 10 MHz, berhenti dan periksa langkah A sebelum melanjutkan.

## Hipotesis (ditulis sebelum ada hasil)

Model Q sederhana (tanpa rugi konduktor dan gelombang permukaan, dikalibrasi eta = 0,49 pada tan d = 0,025). Model sejenis
sudah meleset untuk h, jadi ini hipotesis yang diuji, bukan prediksi.

| tan d | eta | BW relatif | gain (D 5,9 dBi) |
|---|---|---|---|
| 0,025 | 0,49 | 1,00x | 2,8 dBi |
| 0,010 | 0,71 | 0,69x | 4,4 dBi |
| 0,004 | 0,86 | 0,57x | 5,2 dBi |
| 0,001 | 0,96 | 0,51x | 5,7 dBi |

Intinya: rugi yang lebih kecil menaikkan efisiensi dan gain tetapi menyempitkan BW (rugi ikut melebarkan pita).
Hipotesis ditolak bila pada tan d = 0,004 eta di bawah sekitar 0,65 (rugi bukan penyebab utama) atau BW masih di atas sekitar 0,9x
(rugi tidak melebarkan pita).

## Cara membaca hasil

- eta tinggi dan BW turun jauh: trade-off BW dan gain. Satu geometri tidak bisa memenuhi BW 200 MHz dan gain 5 dBi sekaligus;
  perlu BO ulang pada substrat itu untuk melihat kurva trade-off yang dapat dicapai.
- eta tinggi dan BW tetap: substrat rugi rendah memenuhi keduanya; alasan kuat untuk BO pada substrat baru.
- eta hampir tidak berubah: rugi material bukan pembatas; cari penyebab lain (radiasi, gelombang permukaan, topologi).
