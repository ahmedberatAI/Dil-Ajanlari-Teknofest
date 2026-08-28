#!/usr/bin/env python
"""v13b: v13a'dan ayrışan üç ailenin doğrudan atomik özgüllük kapısı."""
from __future__ import annotations

import concurrent.futures
import json
import os
import statistics
import sys
import time


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from benchmark.eval_clips import _ozel_api_model_sozlesmesini_dogrula  # noqa: E402
from benchmark.probe_endustriyel_olay_scout_v13a import (  # noqa: E402
    POSITIVES as V13A_POSITIVES,
)
from dilajan.isg_kanit import Hukum, dogrula  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_223953.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")
GROUPS = {
    "ani endüstriyel enerji/ekipman olayı": {
        "1s2Tcqr3Rgg_trim_84.mp4", "2uuwpx1ykPQ_trim_0.mp4",
        "6fhnKhZQE4o_trim_3.mp4", "fs0TzsV5NgU_trim_6.mp4",
        "qJLf_5RJFG8_trim_3.mp4",
    },
    "aktif makine yakalama/sıkışma": {
        "0QHQ2nmdE78_clip0_trim_4.mp4", "7QFdUqCdML8_trim_1.mp4",
        "_a46_s5WViY_trim_1.mp4",
    },
    "kişi destek kaybı/düşme": {
        "8t1ci0ezwP8_trim_2.mp4", "zJqzjDX-XFU_trim_45.mp4",
    },
}
THRESHOLDS = {
    "ani endüstriyel enerji/ekipman olayı": 4,
    "aktif makine yakalama/sıkışma": 2,
    "kişi destek kaybı/düşme": 2,
}


def _items():
    with open(BASELINE, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for row in data["rows"]:
        name = os.path.basename(row["path"])
        family = next((f for f, names in GROUPS.items() if name in names), None)
        # v13a'nın diğer 12 fiziksel pozitifi bu dar saflaştırma probunda ne pozitif
        # ne negatiftir; ölçüm dışıdır. Karşıt negatif yalnız v13a'nın kilitli 13'üdür.
        contrast = (row["is_anomaly"] and not row["n_events"]
                    and name not in V13A_POSITIVES)
        normal_tn = not row["is_anomaly"] and not row["n_events"]
        if family or contrast or normal_tn:
            out.append({"path": os.path.join(ROOT, row["path"]),
                        "rel_path": row["path"], "target_family": family,
                        "negative": not bool(family)})
    return out


def _run(item):
    start = time.perf_counter()
    frames, _ = extract_timestamped_frames(item["path"])
    root = VLMClient()
    decisions = {}
    # Pozitifte yalnız hedef aile; negatifte üç aile de doğrudan stres edilir.
    families = (item["target_family"],) if item["target_family"] else tuple(GROUPS)
    for family in families:
        result = dogrula(root, frames, family)
        decisions[family] = {"prediction": result.hukum.value,
                             "answers": result.cevaplar, "errors": result.hatalar}
    supported = [f for f, d in decisions.items()
                 if d["prediction"] == Hukum.SUPPORTED.value and not d["errors"]]
    return {**{k: v for k, v in item.items() if k != "path"},
            "supported_families": supported, "decisions": decisions,
            "errors": {f: d["errors"] for f, d in decisions.items() if d["errors"]},
            "latency_s": round(time.perf_counter() - start, 2)}


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    items = _items()
    positives = [x for x in items if x["target_family"]]
    negatives = [x for x in items if x["negative"]]
    if (len(positives), len(negatives)) != (10, 109):
        raise RuntimeError(
            f"Ön kayıt örneklemi değişti: pos={len(positives)} neg={len(negatives)}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    per_family = {}
    accepted_families = []
    for family, names in GROUPS.items():
        pos = [x for x in rows if x["target_family"] == family]
        tp = sum(family in x["supported_families"] for x in pos)
        fp = sum(family in x["supported_families"]
                 for x in rows if x["negative"])
        passed = tp >= THRESHOLDS[family] and fp == 0
        per_family[family] = {"positive": len(names), "tp": tp, "fp": fp,
                              "threshold_tp": THRESHOLDS[family], "accepted": passed}
        if passed:
            accepted_families.append(family)
    errors = sum(bool(x["errors"]) for x in rows)
    recovered = sum(v["tp"] for v in per_family.values() if v["accepted"])
    union_fp = sum(any(f in x["supported_families"] for f in accepted_families)
                   for x in rows if x["negative"])
    summary = {"positive": 10, "negative": 109, "per_family": per_family,
               "accepted_families": accepted_families,
               "accepted_recovered": recovered, "accepted_union_fp": union_fp,
               "errors": errors,
               "latency_median": statistics.median(x["latency_s"] for x in rows),
               "accepted": recovered >= 7 and union_fp == 0 and errors == 0}
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"endustriyel_aile_saflastirma_v13b_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"contract": contract, "baseline": os.path.relpath(BASELINE, ROOT),
                   "summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(os.path.relpath(out, ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
