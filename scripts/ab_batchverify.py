#!/usr/bin/env python
"""A/B: batch_verify KAPALI vs ACIK. Cok-yuksek-sev klipte latency dususu + accuracy (risk/severity korunmus mu).
Recall-safe olmali: ayni olaylar, ayni severity dagilimi (verify dusur-only)."""
from __future__ import annotations
import glob, time, sys
sys.path.insert(0, ".")
from dilajan.config import settings
from dilajan.agent.graph import analyze_video
from dilajan.schema import Severity

SEV = {Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4}
CLIPS = ([p for p in ["data/sample_data/01_yangin.mp4", "data/eval_scenario/Fire/posVideo1.868.avi"] if glob.glob(p)][:1]
         + sorted(glob.glob("data/eval_big/Fighting/*.mp4"))[:1]
         + sorted(glob.glob("data/e2_vehicle/RoadAccidents/RoadAccidents035*.mp4"))[:1]
         + sorted(glob.glob("data/eval_big/Abuse/*.mp4"))[:1])


def snap(p):
    t0 = time.time(); r = analyze_video(p); dt = time.time() - t0
    sevs = sorted([SEV[e.severity] for e in r.events], reverse=True)
    return dt, SEV.get(r.risk.level, 0), len(r.events), sevs


def main():
    print(f"{'klip':30s} {'mod':6s} {'süre':>7} {'risk':>5} {'n':>3} {'severity-dağılım':>20}")
    print("-" * 78)
    tot_off = tot_on = 0.0
    for p in CLIPS:
        settings.batch_verify = False
        d0, rk0, n0, s0 = snap(p)
        settings.batch_verify = True
        d1, rk1, n1, s1 = snap(p)
        tot_off += d0; tot_on += d1
        nm = p.split("/")[-1][:29]
        same = "✓ aynı" if (rk0 == rk1 and n0 == n1 and s0 == s1) else "≠ FARK"
        print(f"{nm:30s} {'KAPALI':6s} {d0:>6.1f}s {rk0:>5} {n0:>3} {str(s0):>20}")
        print(f"{'':30s} {'AÇIK':6s} {d1:>6.1f}s {rk1:>5} {n1:>3} {str(s1):>20}   accuracy: {same}")
    print("-" * 78)
    print(f"TOPLAM süre: KAPALI {tot_off:.1f}s -> AÇIK {tot_on:.1f}s  ({100*(tot_off-tot_on)/max(tot_off,1):+.0f}%)")
    settings.batch_verify = False


if __name__ == "__main__":
    main()
