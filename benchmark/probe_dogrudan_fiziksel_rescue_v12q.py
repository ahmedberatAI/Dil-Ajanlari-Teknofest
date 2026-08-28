#!/usr/bin/env python
"""v12q: v12p scout'unun atladığı yük ve kavga ailelerini doğrudan atomik ölç."""
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
from dilajan.isg_kanit import Hukum, dogrula  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_213224.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")
POSITIVES = {
    "0RcFgtZFhgg_clip0_trim_2.mp4": "karşılıklı fiziksel kavga",
    "1s2Tcqr3Rgg_trim_126.mp4": "dengesini kaybeden ağır yük",
    "87O1pBSGtR0_trim_24.mp4": "dengesini kaybeden ağır yük",
}
FAMILIES = ("dengesini kaybeden ağır yük", "karşılıklı fiziksel kavga")


def _items():
    with open(BASELINE, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for row in data["rows"]:
        name = os.path.basename(row["path"])
        positive = name in POSITIVES
        negative = not row["is_anomaly"] and not row["n_events"]
        if positive or negative:
            out.append({"path": os.path.join(ROOT, row["path"]),
                        "rel_path": row["path"], "positive": positive,
                        "target": POSITIVES.get(name)})
    return out


def _run(item):
    start = time.perf_counter()
    frames, _ = extract_timestamped_frames(item["path"])
    root = VLMClient()
    decisions = {}
    errors = {}
    for family in FAMILIES:
        result = dogrula(root, frames, family)
        decisions[family] = {"prediction": result.hukum.value,
                             "answers": result.cevaplar, "errors": result.hatalar}
        if result.hatalar:
            errors[family] = result.hatalar
    supported_families = [f for f in FAMILIES
                          if decisions[f]["prediction"] == Hukum.SUPPORTED.value
                          and not decisions[f]["errors"]]
    return {**{k: v for k, v in item.items() if k != "path"},
            "supported": bool(supported_families),
            "supported_families": supported_families,
            "decisions": decisions, "errors": errors,
            "latency_s": round(time.perf_counter() - start, 2)}


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    items = _items()
    p = sum(x["positive"] for x in items)
    n = len(items) - p
    if (p, n) != (3, 48):
        raise RuntimeError(f"Ön kayıt örneklemi değişti: positive={p}, negative={n}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    pos = [x for x in rows if x["positive"]]
    neg = [x for x in rows if not x["positive"]]
    recovered = sum(x["supported"] for x in pos)
    fp = sum(x["supported"] for x in neg)
    errors = sum(bool(x["errors"]) for x in rows)
    target_supported = sum(x["target"] in x["supported_families"] for x in pos)
    summary = {"positive": p, "negative": n, "recovered": recovered,
               "target_supported": target_supported, "new_fp": fp,
               "errors": errors,
               "latency_median": statistics.median(x["latency_s"] for x in rows),
               "accepted": recovered >= 2 and target_supported >= 2
                           and fp == 0 and errors == 0}
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"dogrudan_fiziksel_rescue_v12q_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"contract": contract, "baseline": os.path.relpath(BASELINE, ROOT),
                   "summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(os.path.relpath(out, ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
