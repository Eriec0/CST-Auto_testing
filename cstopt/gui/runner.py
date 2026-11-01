"""Menjalankan `main.py <perintah>` sebagai subprocess dan mengalirkan keluarannya baris demi baris.

Sengaja memakai subprocess (bukan import langsung): proses CST/COM terisolasi, GUI tidak membeku,
dan GUI sendiri ringan (tidak memuat scikit-learn).
"""
import json
import os
import queue
import subprocess
import sys
import threading

CREATE_NO_WINDOW = 0x08000000


class Runner:
    def __init__(self, main_py, cwd):
        self.main_py, self.cwd = main_py, cwd
        self._proc = None
        self._q = queue.Queue()
        self._on_line = self._on_done = None

    @property
    def busy(self):
        return self._proc is not None

    def _env(self):
        return dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")

    def _popen(self, argv):
        flags = CREATE_NO_WINDOW if sys.platform == "win32" else 0
        return subprocess.Popen([sys.executable, "-u", self.main_py] + argv, cwd=self.cwd,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", env=self._env(), creationflags=flags)

    def start(self, argv, on_line, on_done):
        if self.busy:
            raise RuntimeError("masih ada proses yang berjalan")
        self._on_line, self._on_done = on_line, on_done
        self._q = queue.Queue()
        self._proc = self._popen(argv)
        threading.Thread(target=self._pump, args=(self._proc, self._q), daemon=True).start()

    @staticmethod
    def _pump(proc, q):
        for line in proc.stdout:
            q.put(("line", line.rstrip("\r\n")))
        q.put(("done", proc.wait()))

    def poll(self):
        """Dipanggil berkala dari thread UI. Kembalikan True selama proses masih berjalan."""
        try:
            while True:
                kind, val = self._q.get_nowait()
                if kind == "line":
                    self._on_line(val)
                else:
                    self._proc = None
                    self._on_done(val)
                    return False
        except queue.Empty:
            return self.busy

    def stop(self):
        """Hentikan proses beserta anaknya (di Windows: taskkill /T, agar dialog_watcher ikut berhenti)."""
        p = self._proc
        if p is None:
            return
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True,
                           creationflags=CREATE_NO_WINDOW)
        else:
            p.terminate()

    def capture_json(self, argv):
        """Jalankan perintah singkat dan ambil JSON dari baris terakhir keluarannya (blocking; panggil dari thread)."""
        p = self._popen(argv)
        out = p.communicate()[0]
        lines = [x for x in out.splitlines() if x.strip()]
        try:
            return json.loads(lines[-1])
        except Exception:
            return {"error": "status gagal: " + (lines[-1] if lines else "(tanpa keluaran)")}
