"""Bandingkan dua CSV kandidat (mis. sebelum dan sesudah restruktur).  py tools/compare_csv.py a.csv b.csv"""
import sys

import pandas as pd

a, b = pd.read_csv(sys.argv[1]), pd.read_csv(sys.argv[2])
cols = [c for c in a.columns if c in b.columns and a[c].dtype != object]
same_shape = a.shape == b.shape
diff = float((a[cols] - b[cols]).abs().max().max()) if same_shape else float("nan")
print(f"bentuk sama: {same_shape} | selisih maksimum: {diff:.3g}")
print("IDENTIK" if same_shape and diff < 1e-9 else "BERBEDA")
