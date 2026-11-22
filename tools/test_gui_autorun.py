"""Uji GUI auto run (tanpa CST, tanpa menjalankan simulasi): argumen, validasi, kunci kontrol, label progres, Hentikan.

  py tools\\test_gui_autorun.py        (membuka jendela GUI sebentar; CST dianggap ada hanya untuk uji ini)
Di Linux tanpa layar:  xvfb-run -a python3 tools/test_gui_autorun.py

Bagian A memakai run_cmd tiruan (menangkap argumen). Bagian B memakai Runner sungguhan dengan main.py palsu di folder
sementara (mencetak baris `[autorun] {json}`, tidur, atau keluar dengan kode tertentu) untuk memeriksa label progres,
kunci kontrol, dan bahwa tombol Hentikan benar-benar mematikan subprocess.
"""
import os
import sys
import tempfile
import time
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cstopt.gui import app as gapp  # noqa: E402
from cstopt.gui import commands as cmd  # noqa: E402
from cstopt.gui.runner import Runner  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print((" [OK]    " if cond else " [GAGAL] ") + name + (f"  {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)


def lockable(a):
    out = []
    for box in a._auto_box:
        out += [w for w in gapp._descendants(box) if w.winfo_class() in ("TEntry", "TCombobox", "TSpinbox", "TCheckbutton")]
    return out


def all_disabled(ws):
    return all(w.instate(["disabled"]) for w in ws)


def none_disabled(ws, skip=()):
    return all(not w.instate(["disabled"]) for w in ws if w not in skip)


def pump(root, cond, timeout=25.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        root.update()
        if cond():
            return True
        time.sleep(0.05)
    return False


FAKE = r'''
import sys, time, json
if "status" in sys.argv:
    print(json.dumps({"error": "fake"})); sys.exit(0)
mode = open(sys.argv[0] + ".mode").read().strip()
def p(**k): print("[autorun] " + json.dumps(k), flush=True)
if mode == "sleep":
    p(batch=1, of=2, step="simulasi", done=1, total=3)
    time.sleep(120)
elif mode == "fail":
    p(batch=1, of=2, step="suggest")
    print("[autorun] BERHENTI: jumlah sampel tidak bertambah setelah simulasi (20 ke 20)", flush=True)
    sys.exit(3)
else:
    p(batch=1, of=2, step="simulasi", done=3, total=3)
    p(batch=1, of=2, step="selesai", n_sampel=25, n_feasible=4, nilai_terbaik=212.5)
    p(batch=2, of=2, step="selesai", n_sampel=30, n_feasible=5, nilai_terbaik=220.25)
    p(step="selesai_semua", batches=2)
    sys.exit(0)
'''


def main():
    gapp.CST_OK = True                                  # hanya untuk uji: tombol Mulai aktif; tidak ada simulasi nyata
    root = tk.Tk()
    a = gapp.App(root)
    root.update()
    warns, infos, asked = [], [], []
    messagebox.showwarning = lambda title, msg, **k: warns.append(title)
    messagebox.showinfo = lambda title, msg, **k: infos.append(title)
    messagebox.askokcancel = lambda title, msg, **k: (asked.append(msg), answer[0])[1]
    answer = [True]
    captured = []
    real_run_cmd = a.run_cmd
    a.run_cmd = lambda argv, after=None: captured.append(list(argv))

    print("A. argumen, validasi, kunci")
    ws = lockable(a)
    check("ada widget masukan yang dikunci (entri, spinbox, kotak centang)", len(ws) >= 12, str(len(ws)))
    a.do_autorun()
    argv = captured[-1]
    check("bawaan: autorun --batches 5 --qc --train ... --", argv[:5] == ["autorun", "--batches", "5", "--qc", "--train"] and "--" in argv, str(argv))
    check("argumen setelah -- = argumen suggest tombol Suggest", argv[argv.index("--") + 1:] == a._suggest_argv()[1:], str(argv))
    check("dialog estimasi: 5 x 5 + 0 = 125 menit", "(5 x 5 + 0) x 5 menit = 125 menit" in asked[-1], asked[-1][:200])
    check("setelah Mulai: kontrol terkunci, bendera aktif", a._auto_active and all_disabled(ws))
    check("bounds dikunci saat auto run", (a.open_bounds(), infos[-1] == "Auto run" and not getattr(a, "_bounds_dlg", None))[1])
    a._auto_finish(0, False)
    check("selesai: kontrol terbuka lagi", (not a._auto_active) and none_disabled(ws, skip=(a.e_region, a.e_region_auto)) or none_disabled(ws))

    a.auto_n.set(2)
    a.auto_qc.set(False)
    a.bo_q.set(3)
    a.bo_focus.set("bw")
    a.bo_constraint.set("gain_fr_ieee_dbi>=4.5")
    a.bo_sweep.set("gain_fr_ieee_dbi=4.0:5.4")
    a.bo_div.set("0.4")
    a.bo_margin.set("fr_ghz=0.08")
    a.bo_region_auto.set("6:0.15")
    a.cst_project.set("cst_projects/X.cst")
    a.do_autorun()
    argv = captured[-1]
    sug = argv[argv.index("--") + 1:]
    check("opsi tab 5 ikut (focus, constraint, sweep, diversity, margin, region-auto, q)",
          all(x in sug for x in ("--focus", "bw", "--sweep", "--diversity", "0.4", "--margin", "--region-auto", "6:0.15")) and sug[sug.index("-q") + 1] == "3", str(sug))
    check("qc mati: tanpa --qc; --train ada; --project ada; 2 batch", "--qc" not in argv[:argv.index("--")] and "--train" in argv and argv[argv.index("--project") + 1] == "cst_projects/X.cst" and argv[2] == "2", str(argv))
    check("estimasi 2 x 3 = 6 sampel = 30 menit", "(2 x 3 + 0) x 5 menit = 30 menit" in asked[-1])
    a._auto_finish(0, False)

    n_before = len(captured)
    for bad in (0, 100):
        a.auto_n.set(bad)
        a.do_autorun()
    check("jumlah batch 0 dan 100 ditolak tanpa menjalankan", len(captured) == n_before and warns[-1] == "Auto run")
    a.auto_n.set(2)
    a.bo_sweep.set("ngawur")
    a.do_autorun()
    check("opsi tidak valid (sweep) ditolak oleh _check_bo_inputs", len(captured) == n_before and warns[-1] == "Sweep" and not a._auto_active)
    a.bo_sweep.set("")
    answer[0] = False
    a.do_autorun()
    check("batal di dialog: tidak berjalan, tidak terkunci", len(captured) == n_before and not a._auto_active and none_disabled(ws, skip=(a.e_region, a.e_region_auto)))
    answer[0] = True

    a.bo_radapt.set(True)
    a._toggle_radapt()
    a.do_autorun()
    a._auto_finish(0, False)
    check("selesai dengan region adaptif aktif: entri region tetap nonaktif", str(a.e_region.cget("state")) == "disabled")
    a.bo_radapt.set(False)
    a._toggle_radapt()

    print("   parsing progres dan pesan berhenti")
    a._cur_cmd = "autorun"
    log_before = a.log.get("1.0", "end")
    a._on_line('[autorun] {"batch":2,"of":5,"step":"simulasi","done":3,"total":5}')
    check("label: Batch 2/5: simulasi (3/5 sampel)", a.auto_msg.get() == "Batch 2/5: simulasi (3/5 sampel)", a.auto_msg.get())
    check("baris JSON tidak masuk log", a.log.get("1.0", "end") == log_before)
    a._on_line("[autorun] BERHENTI: run gagal (kode 1)")
    a._auto_active = True
    a._auto_finish(1, False)
    check("pesan berhenti memuat kode dan penyebab", "Berhenti (kode 1)" in a.auto_msg.get() and "run gagal" in a.auto_msg.get(), a.auto_msg.get())
    a._cur_cmd = None

    print("B. Runner sungguhan dengan main.py palsu")
    tmp = tempfile.mkdtemp(prefix="gui_autorun_")
    fake = os.path.join(tmp, "main.py")
    open(fake, "w").write(FAKE)
    a.run_cmd = real_run_cmd
    a.runner = Runner(fake, tmp)

    def start(mode):
        open(fake + ".mode", "w").write(mode)
        a.bo_sweep.set("")
        a.bo_focus.set("otomatis")
        a.auto_n.set(2)
        a.do_autorun()

    start("sleep")
    ok = pump(root, lambda: a.auto_msg.get().startswith("Batch 1/2: simulasi (1/3"))
    check("label progres dari subprocess: Batch 1/2: simulasi (1/3 sampel)", ok, a.auto_msg.get())
    check("selama berjalan: kontrol terkunci, Mulai nonaktif, Hentikan aktif",
          all_disabled(ws) and a.auto_btn.instate(["disabled"]) and not a.stop_btn.instate(["disabled"]))
    proc = a.runner._proc
    a.stop()
    done = pump(root, lambda: not a.runner.busy and not a._auto_active)
    check("Hentikan mematikan subprocess", done and proc is not None and proc.poll() is not None, f"poll={proc.poll() if proc else None}")
    check("label Dihentikan, kontrol terbuka, Mulai aktif lagi", a.auto_msg.get().startswith("Dihentikan") and none_disabled(ws, skip=(a.e_region, a.e_region_auto)) and not a.auto_btn.instate(["disabled"]), a.auto_msg.get())

    start("fail")
    done = pump(root, lambda: not a.runner.busy and not a._auto_active)
    check("langkah gagal kode 3: label Berhenti (kode 3) dengan penyebab", done and "Berhenti (kode 3)" in a.auto_msg.get() and "tidak bertambah" in a.auto_msg.get(), a.auto_msg.get())
    check("kontrol terbuka setelah berhenti", none_disabled(ws, skip=(a.e_region, a.e_region_auto)))

    start("ok")
    done = pump(root, lambda: not a.runner.busy and not a._auto_active)
    check("selesai normal: label Selesai 2 batch", done and a.auto_msg.get() == "Selesai 2 batch", a.auto_msg.get())
    check("kontrol terbuka setelah selesai", none_disabled(ws, skip=(a.e_region, a.e_region_auto)))

    root.destroy()
    print("\n" + ("SEMUA LULUS" if not FAILS else f"{len(FAILS)} pemeriksaan GAGAL: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
