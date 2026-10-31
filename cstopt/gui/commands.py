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


def suggest(q=5, kernel="rbf", restarts=5, stage=None, design=None, report=False):
    a = ["suggest"]
    if report:
        a.append("--report")
    else:
        a += ["-q", str(int(q)), "--kernel", kernel, "--restarts", str(int(restarts))]
    if stage in (1, 2, 3, 4):
        a += ["--stage", str(stage)]
    return _design(a, design)


def backtest(reps=20, steps=30, restarts=2, design=None):
    return _design(["backtest", "--reps", str(int(reps)), "--steps", str(int(steps)),
                    "--restarts", str(int(restarts))], design)


def status(design=None):
    return _design(["status", "--json"], design)


def display(argv):
    """Teks perintah untuk ditampilkan di log."""
    return "py main.py " + " ".join(f'"{x}"' if " " in x else x for x in argv)
