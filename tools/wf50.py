"""
Lebar saluran microstrip 50 ohm (Hammerstad) untuk substrat tertentu.

  py tools/wf50.py --er 3.66 --h 1.524
Keluaran: Wf (mm). Pakai nilai ini untuk parameter Wf di CST saat mengganti substrat atau ketebalan.
Pemeriksaan: er 4,3 dan h 1,6 mm memberi 3,11 mm (nilai di macro FR-4).
"""
import argparse
import math


def wf(er, h, z0=50.0):
    a = z0 / 60 * math.sqrt((er + 1) / 2) + (er - 1) / (er + 1) * (0.23 + 0.11 / er)
    w_h = 8 * math.exp(a) / (math.exp(2 * a) - 2)
    if w_h > 2:                                       # rumus kedua Hammerstad untuk W/h > 2
        b = 377 * math.pi / (2 * z0 * math.sqrt(er))
        w_h = 2 / math.pi * (b - 1 - math.log(2 * b - 1) + (er - 1) / (2 * er) * (math.log(b - 1) + 0.39 - 0.61 / er))
    return w_h * h, w_h


def main():
    ap = argparse.ArgumentParser(description="Wf 50 ohm (Hammerstad)")
    ap.add_argument("--er", type=float, required=True)
    ap.add_argument("--h", type=float, required=True, help="tebal substrat (mm)")
    ap.add_argument("--z0", type=float, default=50.0)
    a = ap.parse_args()
    w, r = wf(a.er, a.h, a.z0)
    print(f"er={a.er}, h={a.h} mm, Z0={a.z0:g} ohm -> W/h = {r:.4f}, Wf = {w:.3f} mm")


if __name__ == "__main__":
    main()
