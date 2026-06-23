#!/usr/bin/env python
"""TUM etiketli veri setlerinde modeli calistirip her birinin basarisini AYRI raporlar.

Guncel model (domain/severity/rp/M3/poz fix'leriyle) tum setlerde -> konsolide per-dataset karne.
Kullanim:  python scripts/eval_all_datasets.py
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "benchmark"))

from eval_clips import CATEGORY_EXPECT, evaluate_clip  # noqa: E402

DATASETS = [
    ("Senaryo (Yangın+Düşme+Normal)", "data/eval_scenario"),
    ("UCF dengeli (8 kategori)", "data/eval"),
    ("UCF büyük (8 kategori)", "data/eval_big"),
    ("Gerçek düşme — GMDCSA", "data/falls_real"),
    ("Overhead düşme — URFD", "data/falls_surveillance"),
    ("Araç kazası — UCF Road", "data/e2_vehicle"),
]
EXTS = ("*.mp4", "*.avi", "*.mkv", "*.mov", "*.mpg", "*.mpeg")


def frac(xs):
    return 100 * sum(xs) / len(xs) if xs else 0.0


def main():
    summary = {}
    filt = sys.argv[1:]  # argv verilirse yalniz rel-path'inde bu altdizgi gecen setler
    for name, rel in DATASETS:
        if filt and not any(f in rel for f in filt):
            continue
        d = os.path.join(ROOT, rel)
        if not os.path.isdir(d):
            print(f"[atla] {rel} yok")
            continue
        rows = []
        for cat in sorted(os.listdir(d)):
            cdir = os.path.join(d, cat)
            if not os.path.isdir(cdir):
                continue
            paths = []
            for e in EXTS:
                paths.extend(glob.glob(os.path.join(cdir, e)))
            for p in sorted(paths):
                try:
                    rows.append(evaluate_clip(p, cat))
                except Exception as ex:
                    print(f"  [HATA] {os.path.basename(p)}: {ex}")
        if not rows:
            continue
        anom = [r for r in rows if r["is_anomaly"]]
        norm = [r for r in rows if not r["is_anomaly"]]
        rec = frac([1 if r["n_events"] > 0 else 0 for r in anom])
        riskc = frac([1 if r["risk_ord"] >= 3 else 0 for r in anom])
        catm = frac([1 if r["category_match"] else 0 for r in anom])
        nfp = frac([1 if (r["max_severity"] >= 3 or r["risk_ord"] >= 3) else 0 for r in norm])
        opfp = frac([1 if (r["n_events"] > 0 or len(r.get("triggered", [])) > 0) else 0 for r in norm])
        lat = [r["latency_s"] / max(r["duration_s"], 1) for r in rows]
        summary[name] = dict(n_anom=len(anom), n_norm=len(norm), recall=rec, risk_cal=riskc,
                             cat=catm, narrow_fp=nfp, op_fp=opfp, lat=statistics.median(lat) if lat else 0)
        print(f"\n▌ {name}  (anomali={len(anom)}, normal={len(norm)})")
        print(f"   Recall={rec:.0f}%  Risk-kalib={riskc:.0f}%  Kategori={catm:.0f}%  "
              f"Dar-FP={nfp:.0f}%  Op-FP={opfp:.0f}%  Gecikme={summary[name]['lat']:.2f}s/vsn")
        # per-kategori recall
        for c in CATEGORY_EXPECT:
            cr = [r for r in rows if r["category"] == c and r["is_anomaly"]]
            if cr:
                print(f"      {c:14s} n={len(cr):2d} recall={frac([1 if r['n_events']>0 else 0 for r in cr]):3.0f}%")

    print("\n" + "=" * 78)
    print(f"{'VERİ SETİ':34s} {'Anom':>4} {'Norm':>4} {'Recall':>7} {'RiskK':>6} {'Kat':>5} {'DarFP':>6} {'OpFP':>5}")
    print("-" * 78)
    for name, s in summary.items():
        print(f"{name:34s} {s['n_anom']:>4} {s['n_norm']:>4} {s['recall']:>6.0f}% {s['risk_cal']:>5.0f}% "
              f"{s['cat']:>4.0f}% {s['narrow_fp']:>5.0f}% {s['op_fp']:>4.0f}%")
    print("=" * 78)
    out = os.path.join(ROOT, "benchmark", "results", "all_datasets_" + time.strftime("%Y%m%d_%H%M%S") + ".json")
    json.dump(summary, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("Kaydedildi:", os.path.relpath(out, ROOT))


if __name__ == "__main__":
    main()
