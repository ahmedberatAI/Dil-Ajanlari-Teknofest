#!/usr/bin/env python
"""Birlesik A/B (eval_big, daha az gurultu): BASELINE (V1 threat-lens + persist KAPALI) vs
PAKET (V2 threat-lens + persist ACIK). AKSIYON-recall (V2 metrigi) + risk-kalib (persist metrigi)
+ TESPIT + dar-FP/op-FP. Ikisi bagimsiz -> ayri atfedilebilir."""
from __future__ import annotations
import glob, sys
sys.path.insert(0, "."); sys.path.insert(0, "scripts")
from dilajan.config import settings
from dilajan import prompts
from dilajan.agent.graph import analyze_video
from dilajan.schema import Severity
from action_recall import SUPER, TERMS, text_of

SEV = {Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4}
V1 = prompts.THREAT_LENS_SUFFIX; V2 = prompts.THREAT_LENS_SUFFIX_V2
CATS = ["Abuse", "Assault", "Burglary", "Explosion", "Fighting", "RoadAccidents", "Shooting", "Vandalism"]
CRIME = []
for c in CATS:
    CRIME += [(c, p) for p in sorted(glob.glob(f"data/eval_big/{c}/*.mp4"))]
NORMAL = sorted(glob.glob("data/eval_big/Normal/*.mp4"))


def run():
    crime = []
    for c, p in CRIME:
        r = analyze_video(p)
        txt = text_of({"events": [{"olay": e.event} for e in r.events], "summary": r.summary})
        crime.append((c, len(r.events) > 0, any(t in txt for t in TERMS[SUPER[c]]),
                      SEV.get(r.risk.level, 0)))
    norm = []
    for p in NORMAL:
        r = analyze_video(p)
        norm.append(max([SEV[e.severity] for e in r.events], default=0))
    return crime, norm


def rep(tag, crime, norm):
    det = 100*sum(1 for _, d, _, _ in crime if d)/len(crime)
    act = 100*sum(1 for _, _, a, _ in crime if a)/len(crime)
    rc = 100*sum(1 for _, _, _, rk in crime if rk >= 3)/len(crime)
    dar = 100*sum(1 for m in norm if m >= 3)/len(norm)
    opf = 100*sum(1 for m in norm if m >= 1)/len(norm)
    print(f"  [{tag}] SUÇ(n={len(crime)}): TESPİT={det:.0f}% AKSİYON={act:.0f}% riskKalib={rc:.0f}%   NORMAL(n={len(norm)}): op-FP={opf:.0f}% dar-FP={dar:.0f}%")
    return det, act, rc, opf, dar


def main():
    print(f"SUÇ={len(CRIME)} NORMAL={len(NORMAL)}")
    prompts.THREAT_LENS_SUFFIX = V1; settings.threat_interpretation = True; settings.persist_escalation = False
    o = rep("BASELINE (V1, persist-off)", *run())
    prompts.THREAT_LENS_SUFFIX = V2; settings.persist_escalation = True
    v = rep("PAKET (V2, persist-on)    ", *run())
    print(f"\n  DELTA: TESPİT {v[0]-o[0]:+.0f} / AKSİYON {v[1]-o[1]:+.0f} / riskKalib {v[2]-o[2]:+.0f} / op-FP {v[3]-o[3]:+.0f} / dar-FP {v[4]-o[4]:+.0f}")
    prompts.THREAT_LENS_SUFFIX = V1; settings.persist_escalation = False


if __name__ == "__main__":
    main()
