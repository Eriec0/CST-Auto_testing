"""
Analisis kontrol loss tangent.  py tools/analyze_control_tand.py

Membaca data/MicrostripAntena_control_tand/batch_lhs.csv (7 simulasi), membandingkan baris kontrol (tan d = 0,025)
dengan dataset utama, lalu menulis tabel (CSV) dan grafik (PNG) ke data/<run>/figures/.
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import pandas as pd                       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOSS_NAMES = ["lossTan", "dLoss", "tanDelta", "tdelta"]      # nama parameter CST yang mungkin dipakai
REF = {1: 109, 2: 109, 3: 109, 4: 109, 5: 137, 6: 137, 7: 137}
COLS = ["tand", "fr_ghz", "rl_min_db", "bw_mhz", "fbw_pct", "band_cover_pct", "s11_at_f0_db",
        "eta_rad_fr", "d_peak_fr_dbi", "gain_fr_ieee_dbi"]
METRICS = ["fr_ghz", "bw_mhz", "eta_rad_fr", "gain_fr_ieee_dbi"]


def main():
    ap = argparse.ArgumentParser(description="Analisis kontrol tan d")
    ap.add_argument("--run", default="MicrostripAntena_control_tand")
    ap.add_argument("--main-run", default="MicrostripAntena")
    args = ap.parse_args()
    d = os.path.join(ROOT, "data", args.run)
    path = os.path.join(d, "batch_lhs.csv")
    if not os.path.exists(path):
        sys.exit(f"Hasil kontrol belum ada: {path}\nJalankan dulu simulasinya (lihat docs/kontrol_tand.md).")
    df = pd.read_csv(path)
    loss_col = next((c for c in LOSS_NAMES if c in df.columns), None)
    if loss_col is None:
        sys.exit(f"Kolom loss tangent tidak ditemukan di {path} (dicari: {LOSS_NAMES}).")
    df = df.rename(columns={loss_col: "tand"})            # nama internal skrip ini
    df["ref"] = df["sample_id"].map(REF)
    mp = os.path.join(ROOT, "data", args.main_run, "batch_lhs.csv")
    main = pd.read_csv(mp).set_index("sample_id") if os.path.exists(mp) else None

    # baris acuan tan d = 0,025: sampel 1 (kontrol sendiri) untuk 109; dataset utama untuk 137
    if main is not None:
        if 137 in main.index:
            r = main.loc[137].to_dict(); r.update({"sample_id": 0, "ref": 137, "tand": 0.025})
            df = pd.concat([df, pd.DataFrame([r])], ignore_index=True)
        if 109 in main.index and 1 in set(df.sample_id):
            o, k = main.loc[109], df[df.sample_id == 1].iloc[0]
            print("Kontrol reproduksi (tan d = 0,025, material kini berparameter) vs sampel 109 asli:")
            print(f"  fr {k.fr_ghz:.3f} vs {o.fr_ghz:.3f} GHz (selisih {1000*(k.fr_ghz-o.fr_ghz):+.1f} MHz), "
                  f"BW {k.bw_mhz:.1f} vs {o.bw_mhz:.1f} MHz, eta {k.eta_rad_fr:.3f} vs {o.eta_rad_fr:.3f}")
            print("  (selisih fr di bawah sekitar 10 MHz dianggap baik; jika jauh lebih besar, periksa pengaturan material dulu)\n")
    df["fbw_pct"] = 100 * df["bw_mhz"] / (df["fr_ghz"] * 1000)
    df = df.sort_values(["ref", "tand"], ascending=[True, False])
    for ref, g in df.groupby("ref"):
        print(f"--- Baseline sampel {int(ref)}")
        print(g[COLS].round(4).to_string(index=False))
        b = g.iloc[0]
        print("  relatif terhadap tan d = 0,025: " + "; ".join(
            f"tan d {r.tand:g}: BW {r.bw_mhz/b.bw_mhz:.2f}x, eta {r.eta_rad_fr/b.eta_rad_fr:.2f}x, gain {r.gain_fr_ieee_dbi-b.gain_fr_ieee_dbi:+.2f} dB"
            for _, r in g.iloc[1:].iterrows()))
        print()

    os.makedirs(os.path.join(d, "figures"), exist_ok=True)
    df[["ref"] + COLS].round(5).to_csv(os.path.join(d, "control_tand_summary.csv"), index=False)
    fig, ax = plt.subplots(2, 3, figsize=(13, 7))
    panels = [("bw_mhz", "BW (MHz)"), ("fbw_pct", "BW pecahan (%)"), ("band_cover_pct", "cakupan pita 3,3 sampai 3,7 GHz (%)"),
              ("eta_rad_fr", "efisiensi radiasi di fr"), ("gain_fr_ieee_dbi", "gain di fr (dBi)")]
    for a, (col, label) in zip(ax.ravel()[:5], panels):
        for ref, g in df.groupby("ref"):
            a.plot(g.tand, g[col], "o-", label=f"baseline {int(ref)}")
        a.set_xscale("log")
        a.set_xticks([0.025, 0.01, 0.004, 0.001])
        a.set_xticklabels(["0,025", "0,01", "0,004", "0,001"])
        a.minorticks_off()
        a.invert_xaxis()
        a.set_xlabel("loss tangent (kiri = rugi besar)")
        a.set_ylabel(label)
        a.grid(alpha=0.3)
        if col == "bw_mhz":
            a.axhline(200, color="red", ls="--", lw=1)
        if col == "gain_fr_ieee_dbi":
            a.axhline(5.0, color="red", ls="--", lw=1)
    ax[0, 0].legend()
    a = ax[1, 2]
    for ref, g in df.groupby("ref"):
        a.plot(g.bw_mhz, g.gain_fr_ieee_dbi, "o-", label=f"baseline {int(ref)}")
        for _, r in g.iterrows():
            a.annotate(f"{r.tand:g}", (r.bw_mhz, r.gain_fr_ieee_dbi), textcoords="offset points", xytext=(4, 4), fontsize=8)
    a.axhline(5.0, color="red", ls="--", lw=1)
    a.axvline(200, color="red", ls="--", lw=1)
    a.set_xlabel("BW (MHz)")
    a.set_ylabel("gain di fr (dBi)")
    a.set_title("trade-off BW dan gain (label = tan d)", fontsize=9)
    a.grid(alpha=0.3)
    fig.suptitle("Kontrol loss tangent (geometri dan h = 1,6 mm tetap)")
    fig.tight_layout()
    out = os.path.join(d, "figures", "control_tand.png")
    fig.savefig(out, dpi=130)
    print(f"Gambar: {out}\nTabel : {os.path.join(d, 'control_tand_summary.csv')}")


if __name__ == "__main__":
    main()
