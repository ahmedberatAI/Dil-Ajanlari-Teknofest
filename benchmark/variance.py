#!/usr/bin/env python
"""Varyans analizi: ayni klibi N kez analiz edip ciktilarin kararliligini olcer.

Model stokastiktir; olay sayisi, risk seviyesi ve tetiklenen fonksiyonlar turlar
arasi degisebilir. Bu betik bu sapmayi nicelendirir.

Kullanim:  python benchmark/variance.py data/test_clip.mp4 5
"""
from __future__ import annotations

import os
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.agent import analyze_video  # noqa: E402


def main() -> None:
    video = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "test_clip.mp4")
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    n_events, risks, lat = [], [], []
    trig_sets = []
    print(f"{video} -> {n} tur\n")
    for i in range(n):
        r = analyze_video(video)
        n_events.append(len(r.events))
        risks.append(r.risk.level.value)
        trig_sets.append(frozenset(r.triggered_functions))
        print(f"  tur {i+1}: olay={len(r.events)} risk={r.risk.level.value} "
              f"fonk={sorted(r.triggered_functions)}")

    print("\n" + "=" * 50)
    print(f"olay sayisi   : ort={statistics.mean(n_events):.1f} "
          f"std={statistics.pstdev(n_events):.2f} min={min(n_events)} max={max(n_events)}")
    print(f"risk dagilimi : {dict(Counter(risks))}")
    # tetiklenen fonksiyon kararliligi (ortalama ikili Jaccard)
    if len(trig_sets) > 1:
        sims = []
        for a in range(len(trig_sets)):
            for b in range(a + 1, len(trig_sets)):
                u = trig_sets[a] | trig_sets[b]
                sims.append(len(trig_sets[a] & trig_sets[b]) / len(u) if u else 1.0)
        print(f"fonk Jaccard  : {statistics.mean(sims):.2f}  (1.0 = tam kararli)")
    print("=" * 50)


if __name__ == "__main__":
    main()
