#!/usr/bin/env python
"""Iki (veya daha fazla) degerlendirme sonucunu yan yana karsilastirir.

Kullanim:
    python benchmark/compare.py                       # en son 2 sonuc
    python benchmark/compare.py a.json b.json
"""
from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "benchmark", "results")

LABELS = [
    ("n_anomaly", "Anomali klip", "{:.0f}"),
    ("n_normal", "Normal klip", "{:.0f}"),
    ("recall", "Anomali recall", "{:.0%}"),
    ("risk_cal_anom", "Risk kalib. (anomali>=Y)", "{:.0%}"),
    ("cat_match", "Kategori eslesme", "{:.0%}"),
    ("normal_fp", "Normal YANLIS-POZITIF", "{:.0%}"),
    ("risk_cal_norm", "Normal risk=Dusuk", "{:.0%}"),
    ("latency_median", "Gecikme medyan (s)", "{:.1f}"),
]


def main() -> None:
    files = sys.argv[1:]
    if not files:
        files = sorted(glob.glob(os.path.join(RESULTS_DIR, "eval_*.json")))[-2:]
    if len(files) < 1:
        print("Sonuc dosyasi yok.")
        return

    sums = []
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        sums.append((os.path.basename(f), d.get("summary", {})))

    name_w = 26
    col_w = 22
    header = "Metrik".ljust(name_w) + "".join(n[-col_w:].rjust(col_w) for n, _ in sums)
    print(header)
    print("-" * len(header))
    for key, label, fmt in LABELS:
        row = label.ljust(name_w)
        for _, s in sums:
            v = s.get(key)
            cell = fmt.format(v) if isinstance(v, (int, float)) else "-"
            row += cell.rjust(col_w)
        print(row)


if __name__ == "__main__":
    main()
