#!/usr/bin/env python
"""A/B: threat-lens V1 (siddet) vs V2 (siddet+mulk+kaza). AKSIYON-recall (dogru guvenlik-tepki sinifi)
ARTMALI; normal dar-FP ARTMAMALI; TANIMA da raporlanir."""
from __future__ import annotations
import glob, os, sys
sys.path.insert(0, ".")
sys.path.insert(0, "scripts")
from dilajan.config import settings
from dilajan import prompts
from dilajan.agent.graph import analyze_video
from dilajan.schema import Severity
from action_recall import SUPER, TERMS, text_of  # super-sinif terimleri

SEV = {Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4}
V1 = prompts.THREAT_LENS_SUFFIX
V2 = prompts.THREAT_LENS_SUFFIX_V2

CATS = ["Abuse", "Assault", "Burglary", "Explosion", "Fighting", "RoadAccidents", "Shooting", "Vandalism"]
CRIME = []
for c in CATS:
    CRIME += [(c, p) for p in sorted(glob.glob(f"data/eval/{c}/*.mp4"))]
NORMAL = sorted(glob.glob("data/eval/Normal/*.mp4")) + sorted(glob.glob("data/eval_scenario/Normal/*.*"))


def run_crime():
    rows = []
    for c, p in CRIME:
        r = analyze_video(p)
        txt = text_of({"events": [{"olay": e.event} for e in r.events], "summary": r.summary})
        act = any(t in txt for t in TERMS[SUPER[c]])
        rows.append((c, len(r.events) > 0, act))
    return rows


def run_norm():
    out = []
    for p in NORMAL:
        r = analyze_video(p)
        out.append(max([SEV[e.severity] for e in r.events], default=0))
    return out


def rep(tag, crime, norm):
    det = 100*sum(1 for _, d, _ in crime if d)/len(crime)
    act = 100*sum(1 for _, _, a in crime if a)/len(crime)
    dar = 100*sum(1 for m in norm if m >= 3)/len(norm)
    opf = 100*sum(1 for m in norm if m >= 1)/len(norm)
    print(f"  [{tag}] SUÇ(n={len(crime)}): TESPİT={det:.0f}% AKSİYON={act:.0f}%   NORMAL(n={len(norm)}): op-FP={opf:.0f}% dar-FP={dar:.0f}%")
    return det, act, opf, dar


def main():
    print(f"SUÇ={len(CRIME)} NORMAL={len(NORMAL)}")
    prompts.THREAT_LENS_SUFFIX = V1; settings.threat_interpretation = True
    c0, n0 = run_crime(), run_norm(); o = rep("V1", c0, n0)
    prompts.THREAT_LENS_SUFFIX = V2
    c1, n1 = run_crime(), run_norm(); v = rep("V2", c1, n1)
    print(f"\n  DELTA: TESPİT {v[0]-o[0]:+.0f} / AKSİYON {v[1]-o[1]:+.0f} / op-FP {v[2]-o[2]:+.0f} / dar-FP {v[3]-o[3]:+.0f}")
    print("\n  AKSİYON kategori-bazlı (V1->V2):")
    from collections import defaultdict
    a0 = defaultdict(list); a1 = defaultdict(list)
    for (c, _, a) in c0: a0[c].append(a)
    for (c, _, a) in c1: a1[c].append(a)
    for c in CATS:
        if a0[c]:
            print(f"    {c:14s} {100*sum(a0[c])/len(a0[c]):3.0f}% -> {100*sum(a1[c])/len(a1[c]):3.0f}%")
    prompts.THREAT_LENS_SUFFIX = V1


if __name__ == "__main__":
    main()
