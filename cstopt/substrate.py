"""
Parameter substrat turunan, tanpa CST: lebar saluran 50 ohm (Hammerstad), impedansi saluran dari lebarnya, baseline hs dan Wf dari
SUBSTRATE desain, dan pemeriksaan nilai hs dan Wf yang terbaca dari project CST.

Latar belakang: run yang menyetel hs dan Wf (mis. toleransi) mengembalikan model ke baseline EXTRA_BASE di akhir batch. Desain tanpa
EXTRA_BASE dulu memakai nilai bawaan FR-4 (hs 1,6 mm, Wf 3,11 mm), sehingga project RO4350B diam diam berubah menjadi hs 1,6 dan Wf 3,11
(impedansi sekitar 54 ohm) setelah run toleransi. Sekarang baseline diturunkan dari SUBSTRATE desain bila EXTRA_BASE tidak ditulis.
"""
import math


def wf50(er, h, z0=50.0):
    """Lebar saluran microstrip (mm) untuk impedansi z0 pada substrat er dan tebal h (mm), Hammerstad. Sama dengan tools/wf50.py."""
    a = z0 / 60 * math.sqrt((er + 1) / 2) + (er - 1) / (er + 1) * (0.23 + 0.11 / er)
    w_h = 8 * math.exp(a) / (math.exp(2 * a) - 2)
    if w_h > 2:
        b = 377 * math.pi / (2 * z0 * math.sqrt(er))
        w_h = 2 / math.pi * (b - 1 - math.log(2 * b - 1) + (er - 1) / (2 * er) * (math.log(b - 1) + 0.39 - 0.61 / er))
    return w_h * h


def z0_line(er, h, w):
    """Impedansi karakteristik (ohm) saluran microstrip lebar w pada substrat er, tebal h (rumus Hammerstad dan Jensen, tanpa ketebalan konduktor)."""
    u = w / h
    eeff = (er + 1) / 2 + (er - 1) / 2 / math.sqrt(1 + 12 / u)
    if u <= 1:
        return 60 / math.sqrt(eeff) * math.log(8 / u + u / 4)
    return 120 * math.pi / (math.sqrt(eeff) * (u + 1.393 + 0.667 * math.log(u + 1.444)))


def default_extra_base(substrate):
    """{'hs': h, 'Wf': Wf 50 ohm} dari dict SUBSTRATE desain ('er' dan 'h'); None bila datanya tidak lengkap."""
    try:
        er, h = float(substrate["er"]), float(substrate["h"])
    except (KeyError, TypeError, ValueError):
        return None
    return {"hs": h, "Wf": round(wf50(er, h), 3)}


def check_values(substrate, hs, wf, tol_h=0.005, tol_wf=0.05):
    """Daftar peringatan (teks) bila hs atau Wf di project berbeda dari substrat desain. Kosong bila cocok atau datanya tidak lengkap."""
    base = default_extra_base(substrate)
    if base is None:
        return []
    er = float(substrate["er"])
    out = []
    if abs(hs - base["hs"]) > tol_h:
        out.append(f"hs di project = {hs:g} mm, tetapi substrat desain h = {base['hs']:g} mm.")
    if abs(wf - base["Wf"]) > tol_wf:
        out.append(f"Wf di project = {wf:g} mm, tetapi Wf 50 ohm untuk er {er:g} dan h {base['hs']:g} mm adalah {base['Wf']:g} mm.")
    if out:
        out.append(f"Impedansi saluran dengan hs {hs:g} mm dan Wf {wf:g} mm kira kira {z0_line(er, hs, wf):.1f} ohm (bukan 50 ohm); "
                   "S11 dihitung terhadap saluran itu. Setel hs dan Wf di project CST, atau pastikan data lama memang dibuat dengan nilai ini.")
    return out
