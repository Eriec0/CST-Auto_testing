"""
Buat file desain baru dari templat atau dari desain yang sudah ada.

  py tools/new_design.py rogers_ro4003c --er 3.55 --tand 0.0027 --h 1.524 --material "Rogers RO4003C"
  py tools/new_design.py slot_lain --from uslot_dgs_fr4 --run-name MicrostripAntena_SlotLain

Yang diganti otomatis: NAME, RUN_NAME, SUBSTRATE, dan (bila --er dan --h diberikan) hs dan Wf di EXTRA_BASE
(Wf dihitung Hammerstad, lihat tools/wf50.py). Yang HARUS Anda periksa sendiri sesudahnya dicetak di akhir
(PARAM_NAMES, BOUNDS, geometry_problems, BASE_PARAMS, macro CST). Keluaran: designs/<nama>.py.
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from cstopt import paths                      # noqa: E402
from cstopt.loader import load_design_module  # noqa: E402
import wf50                                   # noqa: E402

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
DOC_RE = re.compile(r'\A"""(.*?)"""\n', re.S)


def _sub_line(text, key, new_line):
    """Ganti satu baris `key = ...` (di awal baris). Kembalikan (teks, berhasil)."""
    pat = re.compile(rf"^{key}\s*=.*$", re.M)
    if len(pat.findall(text)) != 1:
        return text, False
    return pat.sub(lambda m: new_line, text, count=1), True


def _q(v):
    return json.dumps(v, ensure_ascii=False) if isinstance(v, str) else repr(v)


def _dict_literal(d):
    return "{" + ", ".join(f"{_q(k)}: {_q(v)}" for k, v in d.items()) + "}"


def main():
    ap = argparse.ArgumentParser(description="Buat designs/<nama>.py dari templat atau desain lain")
    ap.add_argument("name", help="nama file desain tanpa .py (huruf, angka, garis bawah; tidak diawali garis bawah)")
    ap.add_argument("--from", dest="src", default="_template", help="desain sumber (bawaan: _template)")
    ap.add_argument("--run-name", default=None,
                    help="RUN_NAME = nama project CST = folder data (bawaan: MicrostripAntena_<nama>)")
    ap.add_argument("--material", default=None, help="nama material untuk SUBSTRATE")
    ap.add_argument("--er", type=float, default=None, help="permitivitas relatif")
    ap.add_argument("--tand", type=float, default=None, help="loss tangent")
    ap.add_argument("--h", type=float, default=None, help="tebal substrat (mm)")
    ap.add_argument("--force", action="store_true", help="timpa file desain yang sudah ada")
    a = ap.parse_args()

    if not NAME_RE.match(a.name):
        sys.exit(f"Nama '{a.name}' tidak valid: pakai huruf, angka, garis bawah; tidak diawali angka atau garis bawah.")
    src_path = os.path.join(paths.DESIGNS_DIR, a.src[:-3] if a.src.endswith(".py") else a.src) + ".py"
    if not os.path.exists(src_path):
        sys.exit(f"Desain sumber tidak ada: {src_path}")
    dst_path = os.path.join(paths.DESIGNS_DIR, a.name + ".py")
    if os.path.exists(dst_path) and not a.force:
        sys.exit(f"{dst_path} sudah ada (pakai --force untuk menimpa).")
    run_name = a.run_name or f"MicrostripAntena_{a.name}"
    if not NAME_RE.match(run_name):
        sys.exit(f"RUN_NAME '{run_name}' tidak valid (dipakai sebagai nama folder dan project).")

    # RUN_NAME harus unik: dua desain dengan RUN_NAME sama berbagi folder data (sumber kekacauan)
    src_mod = load_design_module(os.path.basename(src_path)[:-3])
    for other in paths.list_designs():
        if other == a.name:
            continue
        if getattr(load_design_module(other), "RUN_NAME", None) == run_name:
            sys.exit(f"RUN_NAME '{run_name}' sudah dipakai desain '{other}'; pilih --run-name lain.")

    text = open(src_path, encoding="utf-8").read()
    todo = []

    text, ok = _sub_line(text, "NAME", f'NAME = "{a.name}"')
    if not ok:
        sys.exit("Baris NAME tidak ditemukan tepat satu kali di sumber.")
    text, ok = _sub_line(text, "RUN_NAME", f'RUN_NAME = "{run_name}"')
    if not ok:
        sys.exit("Baris RUN_NAME tidak ditemukan tepat satu kali di sumber.")

    # SUBSTRATE
    sub = dict(getattr(src_mod, "SUBSTRATE", {"material": "?", "er": None, "tand": None, "h": None}))
    for key, val in (("material", a.material), ("er", a.er), ("tand", a.tand), ("h", a.h)):
        if val is not None:
            sub[key] = val
    text, ok = _sub_line(text, "SUBSTRATE", f"SUBSTRATE = {_dict_literal(sub)}")
    if not ok:
        todo.append("SUBSTRATE tidak ditemukan sebagai satu baris; isi sendiri")
    if a.er is None and a.h is None and a.src != "_template":
        todo.append("SUBSTRATE disalin dari sumber; ganti --er --tand --h bila substrat berbeda")

    # EXTRA_BASE: hs dan Wf
    extra = dict(getattr(src_mod, "EXTRA_BASE", {}))
    if a.h is not None:
        extra["hs"] = a.h
    if a.er is not None and a.h is not None:
        extra["Wf"] = round(wf50.wf(a.er, a.h)[0], 3)
    elif a.er is not None or a.h is not None:
        todo.append("Wf TIDAK dihitung ulang (butuh --er dan --h sekaligus): jalankan tools/wf50.py")
    if a.tand is not None and "lossTan" in extra:
        extra["lossTan"] = a.tand
    if extra != getattr(src_mod, "EXTRA_BASE", {}):
        text, ok = _sub_line(text, "EXTRA_BASE", f"EXTRA_BASE = {_dict_literal(extra)}")
        if not ok and not re.search(r"^EXTRA_BASE\s*=", text, re.M):      # sumber belum punya: tambahkan di akhir
            text = text.rstrip("\n") + f"\n\n\n# Parameter ekstra CST (ditambahkan tools/new_design.py)\nEXTRA_BASE = {_dict_literal(extra)}\n"
        elif not ok:
            todo.append("EXTRA_BASE bukan satu baris; ubah hs dan Wf sendiri")

    # docstring modul diganti ringkas (templat memuat panduan panjang yang tidak perlu disalin)
    mat = sub.get("material", "?")
    new_doc = (f'"""\nKonfigurasi desain {a.name} (substrat {mat}), dibuat oleh tools/new_design.py dari {os.path.basename(src_path)}.\n'
               "Satu-satunya file yang spesifik untuk desain ini; panduan lengkap: designs/_template.py dan docs/membuat_desain_baru.md.\n"
               '"""\n')
    text = DOC_RE.sub(lambda m: new_doc, text, count=1) if DOC_RE.match(text) else new_doc + text

    with open(dst_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    # validasi: file baru harus bisa dimuat dan membentuk Design
    from cstopt.ml import core as mc
    d = mc.load_design(a.name)
    print(f"Dibuat: {os.path.relpath(dst_path, ROOT)}  (RUN_NAME = {run_name}, {len(d.params)} parameter, {len(d.stages)} tahap BO)")
    if "Wf" in extra:
        print(f"EXTRA_BASE = {_dict_literal(extra)}")
    print("\nPeriksa dan ubah sebelum dipakai:")
    items = []
    if a.src in ("_template", "uslot_dgs_fr4") or getattr(src_mod, "PARAM_NAMES", None) == getattr(
            load_design_module("uslot_dgs_fr4"), "PARAM_NAMES", None):
        items.append("PARAM_NAMES dan BOUNDS masih milik U-Slot + DGS FR-4: ganti bila geometrinya lain, atau skala dari seed (tools/make_seeds.py)")
    items += ["geometry_problems: aturan geometri sesuai antena Anda",
              "BASE_PARAMS: nilai parameter di project CST Anda (tanpa itu batch.py memulihkan baseline FR-4)",
              "N_INITIAL, BAND_GHZ, STAGES, FOCI sesuai target",
              f"project CST bernama {run_name} dengan parameter bernama persis sama dengan PARAM_NAMES (bukan nama objek VBA)"]
    for i, t in enumerate(todo + items, 1):
        print(f"  {i}. {t}")
    print(f"\nUji: py tools/smoke_test.py ; lalu  py main.py lhs --design {a.name} -h")


if __name__ == "__main__":
    main()
