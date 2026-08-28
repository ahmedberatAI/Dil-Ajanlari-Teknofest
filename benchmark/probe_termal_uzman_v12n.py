#!/usr/bin/env python
"""v12n: olay-sız kliplerde ayrı termal aşırı ısınma uzmanını ölç."""
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


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_211458.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")
POSITIVE = "1s2Tcqr3Rgg_trim_19.mp4"


def _items():
    with open(BASELINE, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for row in data["rows"]:
        name = os.path.basename(row["path"])
        positive = name == POSITIVE
        negative = not row["is_anomaly"] and not row["n_events"]
        if positive or negative:
            out.append({"path": os.path.join(ROOT, row["path"]),
                        "rel_path": row["path"], "positive": positive})
    return out


def _run(item):
    start = time.perf_counter()
    frames, _ = extract_timestamped_frames(item["path"])
    result = dogrula(VLMClient(), frames, "termal aşırı ısınma")
    return {**{k: v for k, v in item.items() if k != "path"},
            "supported": result.hukum == Hukum.SUPPORTED,
            "prediction": result.hukum.value, "answers": result.cevaplar,
            "errors": result.hatalar,
            "latency_s": round(time.perf_counter() - start, 2)}


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    items = _items()
    p, n = sum(x["positive"] for x in items), sum(not x["positive"] for x in items)
    if (p, n) != (1, 47):
        raise RuntimeError(f"Ön kayıt örneklemi değişti: positive={p}, negative={n}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    pos = next(x for x in rows if x["positive"])
    neg = [x for x in rows if not x["positive"]]
    fp = sum(x["supported"] for x in neg)
    errors = sum(bool(x["errors"]) for x in rows)
    summary = {"positive": 1, "negative": len(neg), "tp": int(pos["supported"]),
               "fp": fp, "errors": errors,
               "latency_median": statistics.median(x["latency_s"] for x in rows),
               "accepted": pos["supported"] and fp == 0 and errors == 0}
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"termal_uzman_v12n_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"contract": contract, "summary": summary, "rows": rows},
                  f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(os.path.relpath(out, ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
