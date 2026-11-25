"""Rentang parameter (BOUNDS) per run: lihat, usulkan pelebaran, atur manual, atau kembalikan ke bawaan (G2).

  py main.py bounds                          tampilkan: file desain vs aktif vs rentang data vs parameter menempel batas
  py main.py bounds --propose                usulkan pelebaran (TIDAK menulis apa pun)
  py main.py bounds --apply                  tulis usulan pelebaran ke data/<RUN>/bounds_override.json
  py main.py bounds --set "Lp=15:25,WD=2:9"  atur manual sebagian parameter (digabung dengan override yang ada)
  py main.py bounds --reset                  hapus override (kembali ke BOUNDS file desain)
  --widen 0.2   pelebaran per sisi yang menempel, sebagai fraksi lebar rentang (bawaan 0,2)
  --dry-run     dengan --set atau --apply: laporkan saja, tanpa menulis berkas
  --json        tambahkan satu baris JSON di akhir keluaran (dipakai GUI)

File desain (designs/*.py) tidak pernah diubah. Mengubah rentang mengubah normalisasi ruang satuan: jarak --spread, --diversity,
dan min_dist ikut berubah makna, dan hasil suggest tidak identik dengan sebelumnya. Jalankan `train` ulang setelahnya.
Region (subset pencarian per putaran: --region, --region-auto, --region-adapt) berbeda dari bounds (domain global parameter).
"""
import argparse
import json
import os
import re

import numpy as np
import pandas as pd

from cstopt import boundsio
from cstopt.ml import core as mc

POS_FLOOR = 0.5      # parameter berbatas bawah positif: batas bawah baru tidak boleh kurang dari 0,5 x batas bawah lama


def valid_fraction(d, bounds, m=4000, seed=0):
    """Persentase titik acak seragam di dalam kotak `bounds` yang lolos aturan geometri desain (None bila tidak ada aturan)."""
    fn = getattr(d.mod, "is_valid", None)
    if fn is None:
        return None
    rng = np.random.default_rng(seed)
    U = rng.random((m, len(d.params)))
    lo = np.array([bounds[p][0] for p in d.params])
    hi = np.array([bounds[p][1] for p in d.params])
    P = lo + U * (hi - lo)
    return 100.0 * float(np.mean([bool(fn(dict(zip(d.params, row)))) for row in P]))


def sticky(d, df, k=10):
    """{param: 'bawah'|'atas'} dari k desain terbaik dan dari kandidat BO terakhir (bila ada)."""
    out = {}
    for name, side, *_ in mc.bound_hits(d, df, k=k):
        out[name] = side
    cand = getattr(d.mod, "CANDIDATES_CSV", None)
    if cand and os.path.exists(cand):
        try:
            X = pd.read_csv(cand)[d.params].values
            for name, side, *_ in mc.edge_hits(d, X):
                out.setdefault(name, side)
        except (KeyError, ValueError, OSError):
            pass
    return out


def propose(d, st, widen=0.2):
    """Usulan pelebaran: sisi yang menempel diperlebar widen x lebar rentang. Kembalikan ({param: (lo, hi)}, catatan)."""
    new, notes = {}, []
    for j, p in enumerate(d.params):
        if p not in st:
            continue
        lo, hi = float(d.lo[j]), float(d.hi[j])
        w = hi - lo
        if st[p] == "bawah":
            n_lo = lo - widen * w
            if lo > 0:                                   # parameter berbatas bawah positif tidak boleh mendekati nol
                n_lo = max(n_lo, POS_FLOOR * lo)
            lo = n_lo
        else:
            hi = hi + widen * w
        new[p] = (round(lo, d.decimals), round(hi, d.decimals))
        notes.append(f"{p} ({st[p]}): {d.lo[j]:g}..{d.hi[j]:g} -> {new[p][0]:g}..{new[p][1]:g}")
    return new, notes


def parse_set(text, params):
    new = {}
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        m = re.fullmatch(r"([A-Za-z_]\w*)\s*=\s*(-?\d+(?:\.\d+)?)\s*:\s*(-?\d+(?:\.\d+)?)", item)
        if not m:
            raise ValueError(f"format salah: '{item}' (harus NAMA=MIN:MAX, dipisah koma)")
        new[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    bad = boundsio.check_bounds(params, new)
    if bad:
        raise ValueError("; ".join(bad))
    return new


def report_change(d, df, new):
    """Cetak ringkasan perubahan + pemeriksaan validitas dan sampel di luar rentang. Kembalikan dict untuk JSON."""
    cur = {p: (float(d.lo[j]), float(d.hi[j])) for j, p in enumerate(d.params)}
    after = dict(cur)
    after.update(new)
    v0, v1 = valid_fraction(d, cur), valid_fraction(d, after)
    warns = []
    out_of = {}
    for p, (lo, hi) in new.items():
        x = df[p].values.astype(float)
        n_out = int(((x < lo - 1e-9) | (x > hi + 1e-9)).sum())
        if n_out:
            out_of[p] = n_out
            warns.append(f"{p}: {n_out} sampel yang ada berada di luar rentang baru (rentang dipersempit); "
                         f"di ruang satuan koordinatnya di luar [0,1]")
    if v0 is not None and v1 is not None:
        print(f"Titik acak yang lolos aturan geometri: {v0:.1f}% (rentang sekarang) -> {v1:.1f}% (rentang baru)")
        if v1 < 5.0 or v1 < 0.5 * v0:
            warns.append(f"proporsi titik valid turun tajam ({v0:.1f}% -> {v1:.1f}%): LHS dan pool kandidat BO bisa kekurangan titik valid; "
                         f"pertimbangkan pelebaran yang lebih kecil (--widen)")
    for w in warns:
        print(f"[peringatan] {w}")
    return {"valid_before_pct": v0, "valid_after_pct": v1, "warnings": warns, "out_of_range": out_of}


def table(d, df, st, changed):
    rows = []
    base = boundsio.base_bounds(d.mod)
    for j, p in enumerate(d.params):
        x = df[p].values.astype(float) if p in df.columns else np.array([np.nan])
        rows.append({"param": p, "base": list(base[p]), "active": [float(d.lo[j]), float(d.hi[j])],
                     "data": [float(np.nanmin(x)), float(np.nanmax(x))], "sticky": st.get(p, ""), "changed": p in changed})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(prog="main.py bounds", description="Rentang parameter (BOUNDS) per run: lihat, usulkan, atur, reset",
                                 epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--design", default=None)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--propose", action="store_true", help="usulkan pelebaran tanpa menulis")
    g.add_argument("--apply", action="store_true", help="usulkan lalu tulis override")
    g.add_argument("--set", default=None, metavar="NAMA=MIN:MAX,...", help="atur manual (digabung dengan override yang ada)")
    g.add_argument("--reset", action="store_true", help="hapus override")
    ap.add_argument("--widen", type=float, default=0.2, help="pelebaran per sisi yang menempel (fraksi lebar; bawaan 0.2)")
    ap.add_argument("--k", type=int, default=10, help="jumlah desain terbaik untuk mendeteksi parameter yang menempel batas")
    ap.add_argument("--dry-run", action="store_true", help="dengan --set atau --apply: hitung dan laporkan tanpa menulis berkas")
    ap.add_argument("--json", action="store_true", help="tambahkan satu baris JSON di akhir keluaran")
    args = ap.parse_args(argv)
    if args.widen <= 0:
        ap.error("--widen harus > 0")

    d = mc.load_design(args.design)
    path = boundsio.override_path(d.mod)
    js = {"override_path": path, "written": False}

    if args.reset:
        gone = boundsio.reset_override(d.mod)
        print("Override dihapus; rentang kembali ke BOUNDS file desain." if gone else "Tidak ada override; tidak ada yang diubah.")
        if gone:
            print("Jalankan `train` ulang bila model lama dibuat dengan rentang override.")
        js.update(written=gone, action="reset")
        if args.json:
            print(json.dumps(js))
        return

    df = mc.load_dataset(d)
    st = sticky(d, df, args.k)

    if args.propose or args.apply or args.set is not None:
        if args.set is not None:
            try:
                new = parse_set(args.set, d.params)
            except ValueError as e:
                ap.error(str(e))
            notes = [f"{p}: {d.lo[d.params.index(p)]:g}..{d.hi[d.params.index(p)]:g} -> {v[0]:g}..{v[1]:g}" for p, v in new.items()]
            action = "set"
        else:
            new, notes = propose(d, st, args.widen)
            action = "apply" if args.apply else "propose"
            if not new:
                print("Tidak ada parameter yang menempel batas pada desain terbaik dan kandidat terakhir; tidak ada usulan.")
        if new:
            print(("Usulan" if action == "propose" else "Perubahan") + " rentang:")
            for n in notes:
                print("  " + n)
            js.update(report_change(d, df, new))
        js.update(action=action, proposal={p: list(v) for p, v in new.items()})
        if action != "propose" and new and args.dry_run:
            print("\n(Simulasi --dry-run: belum ditulis.)")
        elif action != "propose" and new:
            note = f"{action} {args.set if action == 'set' else 'widen=' + format(args.widen, 'g')}"
            p = boundsio.write_override(d.mod, new, note)
            js["written"] = True
            print(f"\nDitulis: {p}")
            cur0 = {q: (float(d.lo[i]), float(d.hi[i])) for i, q in enumerate(d.params)}
            if any(tuple(v) != cur0[q] for q, v in new.items()):
                print("Catatan: hasil `suggest` setelah ini TIDAK identik dengan sebelumnya (normalisasi ruang satuan berubah). "
                      "Jalankan `train` ulang. Kembalikan dengan: py main.py bounds --reset")
            else:
                print("Nilai sama dengan rentang aktif: hasil `suggest` tidak berubah.")
        elif action == "propose" and new:
            print("\n(Belum ditulis. Terapkan dengan: py main.py bounds --apply)")
    else:
        print(f"Desain: {d.name} | run: {os.path.basename(boundsio.run_dir(d.mod))} | override: "
              f"{'ADA (' + str(len(d.bounds_changed)) + ' parameter berbeda)' if d.bounds_changed else 'tidak ada / identik'}")
        print(f"{'param':6s} {'file desain':>15s} {'aktif':>15s} {'rentang data':>17s}  menempel batas")
        for r in table(d, df, st, d.bounds_changed):
            mark = "*" if r["changed"] else " "
            print(f"{r['param']:6s} {r['base'][0]:7.2f}..{r['base'][1]:<7.2f} {r['active'][0]:7.2f}..{r['active'][1]:<7.2f}{mark} "
                  f"{r['data'][0]:8.2f}..{r['data'][1]:<8.2f}  {r['sticky']}")
        print("* = berbeda dari file desain")
        js.update(action="show", table=table(d, df, st, d.bounds_changed), changed=d.bounds_changed)
    if args.json:
        print(json.dumps(js, default=float))


if __name__ == "__main__":
    main()
