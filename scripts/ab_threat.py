#!/usr/bin/env python
"""A/B: threat_interpretation (guvenlik-analisti tehdit-yorumu katmani) KAPALI vs ACIK.
SUC: recall + risk-kalib(>=Yuksek) ARTMALI. NORMAL: dar-FP(>=Yuksek) ARTMAMALI, op-FP izle.
FLAGSHIP (yangin+dusme): recall/risk KORUNMALI."""
from __future__ import annotations
import glob, os, sys
sys.path.insert(0, ".")
from dilajan.config import settings
from dilajan.agent.graph import analyze_video
from dilajan.schema import Severity

SEV = {Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4}
CATS = ["Abuse", "Assault", "Burglary", "Explosion", "Fighting", "RoadAccidents", "Shooting", "Vandalism"]
CRIME, NORMAL, FLAG = [], [], []
for c in CATS:
    CRIME += sorted(glob.glob(f"data/eval/{c}/*.mp4"))
NORMAL = sorted(glob.glob("data/eval/Normal/*.mp4")) + sorted(glob.glob("data/eval_scenario/Normal/*.*"))
FLAG = sorted(glob.glob("data/eval_scenario/Fire/*.*")) + sorted(glob.glob("data/eval_scenario/Fall/*.*"))


def run(paths):
    out = []
    for p in paths:
        r = analyze_video(p)
        ev = r.events
        out.append((max([SEV[e.severity] for e in ev], default=0), SEV.get(r.risk.level, 0), len(ev)))
    return out


def rep(tag, crime, norm, flag):
    crec = 100 * sum(1 for _, _, n in crime if n > 0) / max(len(crime), 1)
    crisk = 100 * sum(1 for _, rk, _ in crime if rk >= 3) / max(len(crime), 1)
    nop = 100 * sum(1 for _, _, n in norm if n > 0) / max(len(norm), 1)
    ndar = 100 * sum(1 for ms, rk, _ in norm if ms >= 3 or rk >= 3) / max(len(norm), 1)
    frec = 100 * sum(1 for _, _, n in flag if n > 0) / max(len(flag), 1)
    frisk = 100 * sum(1 for _, rk, _ in flag if rk >= 3) / max(len(flag), 1)
    print(f"  [{tag}] SUÇ(n={len(crime)}): recall={crec:.0f}% risk≥Y={crisk:.0f}%  "
          f"NORMAL(n={len(norm)}): op-FP={nop:.0f}% dar-FP={ndar:.0f}%  "
          f"FLAGSHIP(n={len(flag)}): recall={frec:.0f}% risk={frisk:.0f}%")
    return crec, crisk, nop, ndar, frec, frisk


def main():
    print(f"SUÇ={len(CRIME)} NORMAL={len(NORMAL)} FLAGSHIP={len(FLAG)}")
    settings.threat_interpretation = False
    off = rep("KAPALI", run(CRIME), run(NORMAL), run(FLAG))
    settings.threat_interpretation = True
    on = rep("AÇIK  ", run(CRIME), run(NORMAL), run(FLAG))
    d = [o - f for o, f in zip(on, off)]
    print(f"\n  DELTA: suç-recall {d[0]:+.0f} / suç-risk {d[1]:+.0f} / norm-opFP {d[2]:+.0f} / "
          f"norm-darFP {d[3]:+.0f} / flag-recall {d[4]:+.0f} / flag-risk {d[5]:+.0f}")


if __name__ == "__main__":
    main()
