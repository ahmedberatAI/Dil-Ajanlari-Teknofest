#!/usr/bin/env python
"""EVS tam-pipeline A/B: analyze_video image-path (vpr=0) vs video-path+EVS (vpr=0.5).
Recall-guard: olay-sayisi/risk REGRESYON olmamali; normalde FP cikmamali. + latency.
Sunucu --video-pruning-rate>0 ile calismali."""
from __future__ import annotations
import glob, time, sys
sys.path.insert(0, ".")
from dilajan.config import settings
from dilajan.agent.graph import analyze_video
from dilajan.schema import Severity

SEV = {Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4}
CLIPS = (["data/sample_data/01_yangin.mp4"]
         + sorted(glob.glob("data/eval/Shooting/*.mp4"))[:1]
         + sorted(glob.glob("data/eval_big/Fighting/*.mp4"))[:1]
         + sorted(glob.glob("data/e2_vehicle/RoadAccidents/RoadAccidents035*.mp4"))[:1]
         + sorted(glob.glob("data/eval/Abuse/*.mp4"))[:1]
         + sorted(glob.glob("data/eval/Normal*/*.mp4"))[:1]
         + sorted(glob.glob("data/eval_big/Normal*/*.mp4"))[:1])


def snap(p):
    t0 = time.time(); r = analyze_video(p); dt = time.time() - t0
    return dt, SEV.get(r.risk.level, 0), len(r.events), sorted([SEV[e.severity] for e in r.events], reverse=True)


def main():
    print(f"{'klip':28s} {'mod':10s} {'süre':>6} {'risk':>4} {'n':>3} {'sev':>16}")
    print("-" * 74)
    ti = tv = 0.0
    for p in [c for c in CLIPS if c]:
        settings.video_pruning_rate = 0.0
        di, rki, ni, si = snap(p)
        settings.video_pruning_rate = 0.5
        dv, rkv, nv, sv = snap(p)
        ti += di; tv += dv
        nm = p.split("/")[-1][:27]
        flag = "✓" if (rki == rkv and ni == nv and si == sv) else ("risk≠" if rki != rkv else "olay≠")
        print(f"{nm:28s} {'IMAGE':10s} {di:>5.1f}s {rki:>4} {ni:>3} {str(si):>16}")
        print(f"{'':28s} {'VIDEO+EVS':10s} {dv:>5.1f}s {rkv:>4} {nv:>3} {str(sv):>16}   {flag}")
    settings.video_pruning_rate = 0.0
    print("-" * 74)
    print(f"TOPLAM: IMAGE {ti:.1f}s -> VIDEO+EVS {tv:.1f}s ({100*(ti-tv)/max(ti,1):+.0f}%)")


if __name__ == "__main__":
    main()
