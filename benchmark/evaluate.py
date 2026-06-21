#!/usr/bin/env python
"""KPI degerlendirme: ajani ground-truth'a karsi calistirir ve metrik raporu uretir.

Metrikler:
  - Olay tespit: precision / recall / F1 (zaman penceresi + anahtar kelime eslesmesi)
  - Kritik olay yakalama orani
  - Risk seviyesi dogrulugu
  - Islem suresi (toplam ve video saniyesi basina)

Kullanim:
    python benchmark/evaluate.py
    python benchmark/evaluate.py --gt benchmark/ground_truth.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.agent import analyze_video  # noqa: E402
from dilajan.utils import format_timestamp  # noqa: E402

DEFAULT_GT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ground_truth.json")
TOLERANCE_S = 3.0  # zaman penceresi toleransi


def _to_sec(mmss: str) -> int:
    m, s = mmss.split(":")
    return int(m) * 60 + int(s)


def match_events(detected, gt_events, tol=TOLERANCE_S):
    """Greedy eslestirme: her GT olayini bir tespit edilen olaya bagla."""
    used = set()
    tp = matched_critical = 0
    total_critical = sum(1 for g in gt_events if g.get("critical"))
    for g in gt_events:
        lo = _to_sec(g["window"][0]) - tol
        hi = _to_sec(g["window"][1]) + tol
        kws = [k.lower() for k in g["keywords"]]
        for i, e in enumerate(detected):
            if i in used:
                continue
            try:
                et = _to_sec(e.time)
            except Exception:
                continue
            if lo <= et <= hi and any(k in e.event.lower() for k in kws):
                used.add(i)
                tp += 1
                if g.get("critical"):
                    matched_critical += 1
                break
    fp = len(detected) - len(used)
    fn = len(gt_events) - tp
    return tp, fp, fn, matched_critical, total_critical


def _f1(p, r):
    return 2 * p * r / (p + r) if (p + r) else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default=DEFAULT_GT)
    args = ap.parse_args()

    with open(args.gt, encoding="utf-8") as f:
        gt = json.load(f)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tot_tp = tot_fp = tot_fn = tot_mc = tot_tc = 0
    risk_hits = 0
    n = 0
    print("=" * 64)
    for rel_video, spec in gt.items():
        video = os.path.join(root, rel_video)
        if not os.path.exists(video):
            print(f"[ATLANDI] bulunamadi: {rel_video}")
            continue
        n += 1
        t0 = time.time()
        result = analyze_video(video)
        dt = time.time() - t0

        tp, fp, fn, mc, tc = match_events(result.events, spec["events"])
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        risk_ok = result.risk.level.value == spec.get("risk")
        crit_rate = (mc / tc) if tc else 1.0

        tot_tp += tp; tot_fp += fp; tot_fn += fn; tot_mc += mc; tot_tc += tc
        risk_hits += int(risk_ok)

        dur = _to_sec(result.video_duration) if result.video_duration else 0
        print(f"VIDEO: {rel_video}")
        print(f"  Olay tespiti     : P={prec:.2f} R={rec:.2f} F1={_f1(prec, rec):.2f}  (TP={tp} FP={fp} FN={fn})")
        print(f"  Kritik yakalama  : {mc}/{tc}  ({crit_rate*100:.0f}%)")
        print(f"  Risk seviyesi    : {'DOGRU' if risk_ok else 'YANLIS'}  (model={result.risk.level.value}, gt={spec.get('risk')})")
        print(f"  Tetiklenen fonk. : {', '.join(result.triggered_functions) or '-'}")
        print(f"  Islem suresi     : {dt:.1f}s  (video {format_timestamp(dur)}, {dt/max(dur,1):.2f}s/video-sn)")
        print("-" * 64)

    if n:
        P = tot_tp / (tot_tp + tot_fp) if (tot_tp + tot_fp) else 0.0
        R = tot_tp / (tot_tp + tot_fn) if (tot_tp + tot_fn) else 0.0
        print("GENEL:")
        print(f"  Olay tespiti F1        : {_f1(P, R):.2f}  (P={P:.2f}, R={R:.2f})")
        print(f"  Kritik olay yakalama   : {tot_mc}/{tot_tc}  ({(tot_mc/tot_tc*100) if tot_tc else 100:.0f}%)")
        print(f"  Risk seviyesi dogrulugu: {risk_hits}/{n}")
        print("=" * 64)


if __name__ == "__main__":
    main()
