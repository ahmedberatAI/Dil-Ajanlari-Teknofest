#!/usr/bin/env python
"""Semantik-olabilirlik A/B: KAPALI vs ACIK. Recall-guard: gercek kisi-olaylari (kisi karede) korunmali;
FP: kisisiz sahnede halusinasyon kisi-olayi dusmeli. Toggle settings.semantic_plausibility."""
from __future__ import annotations
import glob, sys
sys.path.insert(0, ".")
from dilajan.config import settings
from dilajan.agent.graph import analyze_video
from dilajan.schema import Severity

SEV = {Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4}
CLIPS = (sorted(glob.glob("data/eval/Abuse/*.mp4"))[:1]
         + sorted(glob.glob("data/eval_big/Assault/*.mp4"))[:1]
         + sorted(glob.glob("data/eval_big/Fighting/*.mp4"))[:1]
         + ["data/sample_data/02_dusme.mp4"]
         + sorted(glob.glob("data/e2_vehicle/RoadAccidents/*.mp4"))[:1]
         + ["data/sample_data/01_yangin.mp4"]
         + sorted(glob.glob("data/eval/Normal*/*.mp4"))[:2])


def snap(p):
    r = analyze_video(p)
    return SEV.get(r.risk.level, 0), len(r.events), sorted([SEV[e.severity] for e in r.events], reverse=True)


def main():
    print(f"{'klip':28s} {'mod':6s} {'risk':>4} {'n':>3} {'sev':>16}")
    print("-" * 66)
    fired = 0
    for p in [c for c in CLIPS if c]:
        settings.semantic_plausibility = False
        rk0, n0, s0 = snap(p)
        settings.semantic_plausibility = True
        rk1, n1, s1 = snap(p)
        nm = p.split("/")[-1][:27]
        diff = (rk0 != rk1 or s0 != s1)
        if diff:
            fired += 1
        print(f"{nm:28s} {'KAPALI':6s} {rk0:>4} {n0:>3} {str(s0):>16}")
        print(f"{'':28s} {'AÇIK':6s} {rk1:>4} {n1:>3} {str(s1):>16}   {'≠ DÜŞÜRDÜ' if diff else '= aynı'}")
    settings.semantic_plausibility = False
    print("-" * 66)
    print(f"Kural {fired}/{len([c for c in CLIPS if c])} klipte fark yarattı (gerisi recall-safe değişmez).")


if __name__ == "__main__":
    main()
