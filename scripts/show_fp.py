#!/usr/bin/env python
"""Bir eval_*.json icin: normal kliplerde uretilen olaylar (FP/halusinasyon) +
kacirilan anomaliler (recall acigi). E3/E5 teshisi icin."""
import glob
import json
import os
import sys

f = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob("benchmark/results/eval_*.json"))[-1]
d = json.load(open(f, encoding="utf-8"))
rows = d["rows"]
print("FILE:", f)
print("\n=== NORMAL klipler OLAY uretti (operasyonel FP / halusinasyon) ===")
for r in rows:
    if not r["is_anomaly"] and r["n_events"] > 0:
        print(f"\n[{os.path.basename(r['path'])}]  risk={r['risk_level']}  tetik={r.get('triggered')}")
        for e in r["events"]:
            print(f"   [{e['time']}] ({e['severity']}/{e['category']}) {e['event']}")
        print(f"   OZET: {r['summary'][:200]}")
print("\n=== ANOMALI KACIRILDI (n_events=0) ===")
miss = [r for r in rows if r["is_anomaly"] and r["n_events"] == 0]
for r in miss:
    print(f"  MISS [{r['category']}] {os.path.basename(r['path'])}")
if not miss:
    print("  (yok)")
