"""Penyusun argumen perintah untuk GUI (murni, tanpa tkinter, agar mudah diuji).

Setiap fungsi mengembalikan daftar argumen untuk `py main.py <argumen>`.
"""


def _design(args, design):
    return args + (["--design", design] if design else [])


def lhs(n, seed, report=False, design=None):
    a = ["lhs", "-n", str(int(n)), "--seed", str(int(seed))]
    if report:
        a.append("--report")
    return _design(a, design)


def run_probe(project=None):
    return ["run", "--probe"] + (["--project", project] if project else [])


def run_check(samples=None, project=None):
    a = ["run", "--check-samples"]
    if samples:
        a += ["--samples", samples]
    if project:
        a += ["--project", project]
    return a


def run_batch(samples=None, auto_yes=True, limit=0, project=None):
    a = ["run"]
    if samples:
        a += ["--samples", samples]
    if auto_yes:
        a.append("--auto-yes")
    if int(limit) > 0:
        a += ["--limit", str(int(limit))]
    if project:
        a += ["--project", project]
    return a


def qc(run=None):
    return ["qc"] + (["--run-name", run] if run else [])


def curves(run=None):
    return ["curves"] + (["--run-name", run] if run else [])


def train(kernel="rbf", restarts=5, cv=5, seed=0, design=None):
    return _design(["train", "--kernel", kernel, "--restarts", str(int(restarts)),
                    "--cv", str(int(cv)), "--seed", str(int(seed))], design)


def suggest(q=5, kernel="rbf", restarts=5, stage=None, design=None, report=False, focus=None, constraint=None,
            region=None, region_auto=None, margin=None, calibrate=False, composite=False,
            sweep=None, diversity=None, region_adapt=False):
    a = ["suggest"]
    if report:
        a.append("--report")
    else:
        a += ["-q", str(int(q)), "--kernel", kernel, "--restarts", str(int(restarts))]
    if focus:
        a += ["--focus", focus]
        if constraint:
            a += ["--constraint", constraint]
    elif stage in (1, 2, 3, 4):
        a += ["--stage", str(stage)]
    if region:
        a += ["--region", region]
    elif region_auto:
        a += ["--region-auto", region_auto]
    elif region_adapt:                         # saling eksklusif dengan region manual dan otomatis
        a.append("--region-adapt")
    if not report:
        if sweep:                              # KOLOM=LO:HI; butuh --focus (diperiksa GUI sebelum menjalankan)
            a += ["--sweep", sweep]
        if diversity:
            a += ["--diversity", str(diversity)]
    if margin:
        a += ["--margin", margin]
    if calibrate:
        a.append("--calibrate")
    if composite:
        a.append("--composite")
    return _design(a, design)


def backtest(reps=20, steps=30, restarts=2, design=None):
    return _design(["backtest", "--reps", str(int(reps)), "--steps", str(int(steps)),
                    "--restarts", str(int(restarts))], design)


def validate(design=None, batch=5, restarts=2, kernel="rbf", pof_compare=False, focus=None, constraint=None):
    a = ["validate", "--batch", str(int(batch)), "--kernel", kernel, "--restarts", str(int(restarts))]
    if pof_compare:
        a.append("--pof-compare")
    if focus:
        a += ["--focus", focus]
        if constraint:
            a += ["--constraint", constraint]
    return _design(a, design)


def sensitivity(design=None, region_auto=None, restarts=2, kernel="rbf"):
    a = ["sensitivity", "--kernel", kernel, "--restarts", str(int(restarts))]
    if region_auto:
        a += ["--region-auto", region_auto]
    return _design(a, design)


def report(runs=None, focus=None, constraints=None, out_dir=None):
    """Laporan otomatis (bawaan data/_compare). constraints: daftar teks '[RUN:]kolom>=nilai'. out_dir: folder keluaran."""
    a = ["report"]
    if runs:
        a += ["--runs", *runs]
    if out_dir:
        a += ["--out-dir", out_dir]
    if focus:
        a += ["--focus", focus]
    for c in constraints or []:
        a += ["--constraint", c]
    return a


def bounds(design=None, propose=False, apply=False, set_=None, reset=False, widen=None, dry_run=False):
    """Perintah `bounds` (selalu dengan --json; baris terakhir keluaran = JSON)."""
    a = ["bounds"]
    if reset:
        a.append("--reset")
    elif set_:
        a += ["--set", set_]
    elif apply:
        a.append("--apply")
    elif propose:
        a.append("--propose")
    if widen is not None and (propose or apply):
        a += ["--widen", str(widen)]
    if dry_run:
        a.append("--dry-run")
    a.append("--json")
    return _design(a, design)


def autorun(batches, qc=False, train=False, design=None, project=None, suggest_argv=None, bounds_check=None):
    """Perintah `autorun`. suggest_argv = hasil suggest(...) (diteruskan apa adanya ke `suggest` setelah `--`)."""
    a = ["autorun", "--batches", str(int(batches))]
    if qc:
        a.append("--qc")
    if train:
        a.append("--train")
    if design:
        a += ["--design", design]
    if project:
        a += ["--project", project]
    if bounds_check:
        a += ["--bounds-check", bounds_check]
    sug = list(suggest_argv or [])
    if sug and sug[0] == "suggest":
        sug = sug[1:]
    return a + ["--"] + sug


def autorun_minutes(batches, q, pending=0, per_sample=5.0):
    """Estimasi menit simulasi: (batch x q + sampel menunggu) x menit per sampel."""
    return (int(batches) * int(q) + int(pending)) * float(per_sample)


def autorun_text(d):
    """Teks progres dari satu objek JSON baris `[autorun] {...}` (lihat cstopt/autorun.py)."""
    step, i, n = d.get("step"), d.get("batch"), d.get("of")
    pre = f"Batch {i}/{n}: " if i and n else ""
    if step == "simulasi":
        return f"{pre}simulasi ({d.get('done', 0)}/{d.get('total', 0)} sampel)"
    if step == "suggest":
        return f"{pre}suggest (melatih GPR, memilih kandidat)"
    if step == "qc":
        return f"{pre}QC"
    if step == "train":
        return f"{pre}latih GPR"
    if step == "selesai":
        v = d.get("nilai_terbaik")
        best = f", terbaik {float(v):.4g}" if v not in (None, "") else ""
        return f"{pre}selesai: {d.get('n_sampel')} sampel, {d.get('n_feasible')} feasible{best}"
    if step == "selesai_semua":
        return f"Selesai {d.get('batches')} batch"
    if step == "batas":
        return f"{pre}peringatan: {', '.join(d.get('params', []))} menempel batas rentang"
    if step == "berhenti":
        return f"Berhenti (kode {d.get('kode')})"
    return ""


def pareto(runs=None, all_points=False):
    a = ["pareto"]
    if runs:
        a += ["--runs", *runs]
    if all_points:
        a.append("--all")
    return a


def status(design=None):
    return _design(["status", "--json"], design)


def display(argv):
    """Teks perintah untuk ditampilkan di log."""
    return "py main.py " + " ".join(f'"{x}"' if " " in x else x for x in argv)
