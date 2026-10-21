"""
Pembaca hasil ekspor farfield ASCII CST dan penghitung gain.

Format file (dari ekspor plot farfield CST):
  kolom: Theta, Phi, Abs(Dir.) [dBi], Abs(Theta), Phase(Theta), Abs(Phi), Phase(Phi), Ax.Ratio
  dua baris pertama adalah header.

Catatan: bila header kolom ke-3 berbunyi Abs(Dir.), isinya DIRECTIVITY, bukan gain.
  Bila plot diekspor dalam mode Gain, header berbunyi Abs(Gain) dan nilainya sudah gain
  (nama kunci dir_peak_dbi tetap dipakai untuk keduanya).
  Gain (IEEE)    = D + 10*log10(efisiensi radiasi)
  Realized gain  = D + 10*log10(efisiensi total)
"""
import numpy as np


def read_farfield(path):
    d = np.loadtxt(path, skiprows=2)
    return {"theta": d[:, 0], "phi": d[:, 1], "dir_dbi": d[:, 2]}


def peak_directivity(path):
    """Nilai puncak directivity pada data yang diekspor, beserta arahnya."""
    ff = read_farfield(path)
    i = int(np.argmax(ff["dir_dbi"]))
    bore = ff["dir_dbi"][ff["theta"] == 0.0]
    return {
        "dir_peak_dbi": float(ff["dir_dbi"][i]),
        "theta_peak_deg": float(ff["theta"][i]),
        "phi_peak_deg": float(ff["phi"][i]),
        "dir_boresight_dbi": float(np.mean(bore)) if bore.size else float("nan"),
        "n_phi_cuts": int(np.unique(ff["phi"]).size),
    }


def peak_over_files(paths):
    """Puncak directivity/gain dari beberapa irisan (mis. phi=0 dan phi=90)."""
    best = None
    for p in paths:
        info = peak_directivity(p)
        info["file"] = str(p)
        if best is None or info["dir_peak_dbi"] > best["dir_peak_dbi"]:
            best = info
    return best


def eff_to_linear(value):
    """Ubah efisiensi ke rasio 0..1. Menangani rasio, persen, atau dB."""
    v = np.asarray(value, dtype=float)
    if np.all(v <= 0.0):          # dB
        return 10.0 ** (v / 10.0)
    if np.nanmax(v) > 1.5:        # persen
        return v / 100.0
    return v                      # rasio


def gain_dbi(dir_dbi, efficiency):
    """Gain (dBi) dari directivity (dBi) dan efisiensi (rasio 0..1)."""
    eta = float(eff_to_linear(efficiency))
    return float(dir_dbi + 10.0 * np.log10(eta))


if __name__ == "__main__":
    import sys
    info = peak_directivity(sys.argv[1])
    print(info)
    if len(sys.argv) > 2:
        print("gain (dBi):", gain_dbi(info["dir_peak_dbi"], float(sys.argv[2])))
