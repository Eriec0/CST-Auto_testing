"""
Analisis pilot ketebalan substrat (h).  py tools/analyze_pilot_h.py

Membaca data/<run>/batch_lhs.csv dari pilot (default run: MicrostripAntena_pilot_h), membandingkan baris kontrol
(h = 1,6 mm) dengan hasil asli di dataset utama, lalu menulis tabel (CSV) dan grafik (PNG) ke data/<run>/figures/.
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import pandas as pd                       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = {1: 109, 2: 109, 3: 109, 4: 109, 5: 137, 6: 137, 7: 137, 8: 137}     # sample_id pilot -> sampel asal
COLS = ["hs", "fr_ghz", "rl_min_db", "bw_mhz", "fbw_pct", "band_cover_pct", "s11_at_f0_db",
        "eta_rad_fr", "d_peak_fr_dbi", "gain_fr_ieee_dbi"]


def main():
    ap = argparse.ArgumentParser(description="Analisis pilot h")
    ap.add_argument("--run", default="MicrostripAntena_pilot_h")
    ap.add_argument("--main-run", default="MicrostripAntena", help="dataset utama untuk pembanding baris kontrol")
    args = ap.parse_args()
    d = os.path.join(ROOT, "data", args.run)
    path = os.path.join(d, "batch_lhs.csv")
    if not os.path.exists(path):
        sys.exit(f"Hasil pilot belum ada: {path}\nJalankan dulu simulasi pilot (lihat instruksi).")
    df = pd.read_csv(path)
    df["ref"] = df["sample_id"].map(REF)
    df["fbw_pct"] = 100 * df["bw_mhz"] / (df["fr_ghz"] * 1000)
    df = df.sort_values(["ref", "hs"])
    print(f"Hasil pilot: {len(df)} dari 8 simulasi\n")
    for ref, g in df.groupby("ref"):
        print(f"--- Baseline sampel {int(ref)}")
        print(g[COLS].round(3).to_string(index=False))
        print()

    # kontrol: baris h = 1,6 harus mereproduksi dataset utama
    mp = os.path.join(ROOT, "data", args.main_run, "batch_lhs.csv")
    if os.path.exists(mp):
        main = pd.read_csv(mp).set_index("sample_id")
        print("Kontrol reproduksi (h = 1,6 mm vs dataset utama):")
        for ref, g in df[abs(df.hs - 1.6) < 1e-9].groupby("ref"):
            if int(ref) not in main.index:
                print(f"  sampel {int(ref)}: tidak ada di dataset utama ({len(main)} sampel), kontrol dilewati")
                continue
            r, o = g.iloc[0], main.loc[int(ref)]
            print(f"  sampel {int(ref)}: fr {r.fr_ghz:.3f} vs {o.fr_ghz:.3f} GHz (selisih {1000*(r.fr_ghz-o.fr_ghz):+.1f} MHz), "
                  f"BW {r.bw_mhz:.1f} vs {o.bw_mhz:.1f} MHz, eta {r.eta_rad_fr:.3f} vs {o.eta_rad_fr:.3f}")
        print("  (selisih fr di bawah sekitar 10 MHz dianggap reproduksi baik; jika jauh lebih besar, periksa pengaturan CST dulu)\n")

    # ringkasan tren
    print("Tren dari h terkecil ke terbesar:")
    for ref, g in df.groupby("ref"):
        a, b = g.iloc[0], g.iloc[-1]
        print(f"  sampel {int(ref)}: BW {a.bw_mhz:.0f} -> {b.bw_mhz:.0f} MHz, eta {a.eta_rad_fr:.2f} -> {b.eta_rad_fr:.2f}, "
              f"gain {a.gain_fr_ieee_dbi:.2f} -> {b.gain_fr_ieee_dbi:.2f} dBi, fr {a.fr_ghz:.3f} -> {b.fr_ghz:.3f} GHz, "
              f"cakupan pita {a.band_cover_pct:.0f} -> {b.band_cover_pct:.0f}%")

    os.makedirs(os.path.join(d, "figures"), exist_ok=True)
    df[["ref"] + COLS].round(4).to_csv(os.path.join(d, "pilot_h_summary.csv"), index=False)
    fig, ax = plt.subplots(2, 3, figsize=(13, 7))
    panels = [("bw_mhz", "BW (MHz)"), ("fbw_pct", "BW pecahan (%)"), ("band_cover_pct", "cakupan pita 3,3 sampai 3,7 GHz (%)"),
              ("eta_rad_fr", "efisiensi radiasi di fr"), ("gain_fr_ieee_dbi", "gain di fr (dBi)"), ("fr_ghz", "fr (GHz)")]
    for a, (col, label) in zip(ax.ravel(), panels):
        for ref, g in df.groupby("ref"):
            a.plot(g.hs, g[col], "o-", label=f"baseline {int(ref)}")
        a.set_xlabel("tebal substrat h (mm)")
        a.set_ylabel(label)
        a.grid(alpha=0.3)
        if col == "fr_ghz":
            a.axhspan(3.3, 3.7, color="green", alpha=0.08)
        if col == "gain_fr_ieee_dbi":
            a.axhline(5.0, color="red", ls="--", lw=1)
        if col == "bw_mhz":
            a.axhline(200, color="red", ls="--", lw=1)
    ax[0, 0].legend()
    fig.suptitle("Pilot ketebalan substrat FR-4 (geometri lain tetap, Wf mengikuti h)")
    fig.tight_layout()
    out = os.path.join(d, "figures", "pilot_h.png")
    fig.savefig(out, dpi=130)
    print(f"\nGambar: {out}\nTabel : {os.path.join(d, 'pilot_h_summary.csv')}")


if __name__ == "__main__":
    main()
