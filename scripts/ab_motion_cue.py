#!/usr/bin/env python
"""A/B: motion_saliency_cue KAPALI vs ACIK.
Arac kazasi (recall + risk-kalib >=Yuksek) ve NORMAL (op-FP=herhangi olay, dar-FP>=Yuksek) etkisi.
Net kazanc varsa default acilir; yoksa durust raporlanir."""
from __future__ import annotations
import glob, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dilajan.config import settings
from dilajan.agent.graph import analyze_video
from dilajan.schema import Severity

SEV = {Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4}

ROAD = sorted(glob.glob(os.path.join(ROOT, "data/e2_vehicle/RoadAccidents/*.mp4")))
NORMAL = (sorted(glob.glob(os.path.join(ROOT, "data/eval_scenario/Normal/*.*"))) +
          sorted(glob.glob(os.path.join(ROOT, "data/eval/Normal/*.*"))))


def run(paths):
    rows = []
    for p in paths:
        r = analyze_video(p)
        ev = r.events
        maxsev = max([SEV[e.severity] for e in ev], default=0)
        risk = SEV.get(r.risk.level, 0)
        rows.append((os.path.basename(p), len(ev), maxsev, risk))
    return rows


def report(tag, road, norm):
    n_r = len(road)
    rec = 100 * sum(1 for _, n, _, _ in road if n > 0) / max(n_r, 1)
    riskc = 100 * sum(1 for _, _, _, rk in road if rk >= 3) / max(n_r, 1)
    n_n = len(norm)
    opfp = 100 * sum(1 for _, n, _, _ in norm if n > 0) / max(n_n, 1)
    narrowfp = 100 * sum(1 for _, _, ms, rk in norm if ms >= 3 or rk >= 3) / max(n_n, 1)
    print(f"  [{tag}] ARAC(n={n_r}): recall={rec:.0f}%  risk>=Yuksek={riskc:.0f}%   "
          f"NORMAL(n={n_n}): op-FP={opfp:.0f}%  dar-FP={narrowfp:.0f}%")
    return rec, riskc, opfp, narrowfp


def main():
    print(f"ARAC={len(ROAD)} NORMAL={len(NORMAL)}")
    settings.motion_saliency_cue = False
    r0, n0 = run(ROAD), run(NORMAL)
    off = report("KAPALI", r0, n0)
    settings.motion_saliency_cue = True
    r1, n1 = run(ROAD), run(NORMAL)
    on = report("ACIK  ", r1, n1)
    print("\n  DELTA: recall %+.0f / risk %+.0f / op-FP %+.0f / dar-FP %+.0f" %
          (on[0]-off[0], on[1]-off[1], on[2]-off[2], on[3]-off[3]))
    # klip-bazli degisen araclar
    print("\n  arac klip-bazli (KAPALI->ACIK n_olay / risk):")
    for (nm, n_a, _, rk_a), (_, n_b, _, rk_b) in zip(r0, r1):
        if n_a != n_b or rk_a != rk_b:
            print(f"    {nm:30s} olay {n_a}->{n_b}  risk {rk_a}->{rk_b}")


if __name__ == "__main__":
    main()
