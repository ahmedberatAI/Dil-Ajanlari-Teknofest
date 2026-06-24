#!/usr/bin/env python
"""A/B: risk_recall_bias (Agent-C #1) KAPALI vs ACIK.
ANOMALI: risk-kalib (risk>=Yuksek) ARTMALI. NORMAL: dar-FP (risk>=Yuksek VEYA maxsev>=Yuksek) ARTMAMALI.
Recall (TESPIT) korunmali. Risk-kalibrasyon bosluklari: arac %67, dusme %78, UCF %75."""
from __future__ import annotations
import glob, os, sys
sys.path.insert(0, ".")
from dilajan.config import settings
from dilajan.agent.graph import analyze_video
from dilajan.schema import Severity

SEV = {Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4}
ANOM = (sorted(glob.glob("data/e2_vehicle/RoadAccidents/*.mp4")) +
        sorted(glob.glob("data/falls_real/Fall/*.*")) +
        [p for c in ["Abuse","Assault","Burglary","Explosion","Fighting","RoadAccidents","Shooting","Vandalism"]
         for p in sorted(glob.glob(f"data/eval/{c}/*.mp4"))])
NORMAL = (sorted(glob.glob("data/eval/Normal/*.mp4")) +
          sorted(glob.glob("data/falls_real/Normal/*.*")) +
          sorted(glob.glob("data/eval_scenario/Normal/*.*")))


def run(paths):
    out = []
    for p in paths:
        r = analyze_video(p)
        ev = r.events
        disp = len(getattr(r, "triggered_functions", []) or [])
        out.append((len(ev) > 0, SEV.get(r.risk.level, 0), max([SEV[e.severity] for e in ev], default=0), disp))
    return out


def rep(tag, A, N):
    rec = 100*sum(1 for d,_,_,_ in A if d)/len(A)
    rc = 100*sum(1 for _,rk,_,_ in A if rk >= 3)/len(A)
    dar = 100*sum(1 for _,rk,ms,_ in N if rk >= 3 or ms >= 3)/len(N)
    opf = 100*sum(1 for d,_,_,_ in N if d)/len(N)
    disp = 100*sum(1 for _,_,_,dp in N if dp > 0)/len(N)
    print(f"  [{tag}] ANOM(n={len(A)}): recall={rec:.0f}% risk-kalib={rc:.0f}%   NORMAL(n={len(N)}): dar-FP={dar:.0f}% dispatch-FP={disp:.0f}% op-FP={opf:.0f}%")
    return rec, rc, dar, opf, disp


def main():
    print(f"ANOM={len(ANOM)} NORMAL={len(NORMAL)}")
    settings.risk_recall_bias = False
    o = rep("KAPALI", run(ANOM), run(NORMAL))
    settings.risk_recall_bias = True
    v = rep("AÇIK  ", run(ANOM), run(NORMAL))
    print(f"\n  DELTA: recall {v[0]-o[0]:+.0f} / risk-kalib {v[1]-o[1]:+.0f} / dar-FP {v[2]-o[2]:+.0f} / dispatch-FP {v[4]-o[4]:+.0f} / op-FP {v[3]-o[3]:+.0f}")
    settings.risk_recall_bias = False


if __name__ == "__main__":
    main()
