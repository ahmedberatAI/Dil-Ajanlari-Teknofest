#!/usr/bin/env python
"""Coklu eval kosularini set-imzasina (n_anomali, n_normal) gore gruplayip her metrigin
ORTALAMA ± STD'sini raporlar. Amac: tek-kosu "cherry-pick %100" yerine durust varyans bandi.

Kullanim:  python benchmark/aggregate.py
"""
from __future__ import annotations

import glob
import json
import os
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "benchmark", "results")

# set-imzasi -> okunabilir etiket (gerektiginde guncelle)
LABELS = {
    (24, 8): "UCF-Crime (grainy, dayanıklılık stresi)",
    (18, 12): "Senaryo (yangın+düşme+normal)",
    (10, 12): "Senaryo (yalnız yangın+normal)",
    (9, 6): "Gerçek düşme (GMDCSA-24)",
}
METRICS = [("recall", "Anomali recall"), ("risk_cal_anom", "Risk kalib (≥Y)"),
           ("cat_match", "Kategori eşleşme"), ("normal_fp", "Normal FP (dar)"),
           ("normal_fp_operational", "Normal FP (operasyonel)")]


def main() -> None:
    groups: dict = {}
    for f in sorted(glob.glob(os.path.join(RESULTS, "eval_*.json"))):
        try:
            s = json.load(open(f, encoding="utf-8")).get("summary", {})
        except Exception:
            continue
        sig = (s.get("n_anomaly"), s.get("n_normal"))
        groups.setdefault(sig, []).append(s)

    print("=" * 70)
    print("KONSOLİDE BENCHMARK — koşu-bazlı ortalama ± std (dürüst varyans)")
    print("=" * 70)
    for sig, runs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        label = LABELS.get(sig, f"set n_anom={sig[0]} n_norm={sig[1]}")
        print(f"\n▌ {label}   [{len(runs)} koşu, n_anom={sig[0]}, n_norm={sig[1]}]")
        for key, name in METRICS:
            vals = [r[key] for r in runs if key in r and r[key] is not None]
            if not vals:
                continue
            m = statistics.mean(vals)
            sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
            rng = f" [{min(vals)*100:.0f}–{max(vals)*100:.0f}]" if len(vals) > 1 else ""
            print(f"    {name:24s}: %{m*100:.0f} ± {sd*100:.0f}{rng}  (n={len(vals)})")
    print("\n" + "=" * 70)
    print("Not: Küçük setlerde (8–24 klip) tek koşu yanıltıcı; bant + std esastır.")


if __name__ == "__main__":
    main()
