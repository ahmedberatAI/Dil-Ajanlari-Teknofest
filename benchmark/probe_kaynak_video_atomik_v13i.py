#!/usr/bin/env python
"""v13i: iki fiziksel aileyi kaynak MP4 üzerinde atomik yeniden doğrula."""
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
from dilajan.isg_kanit import Hukum, dogrula_video  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_234737.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")
HEAVY = "dengesini kaybeden ağır yük"
SUPPORT = "kişi destek kaybı/düşme"
EXPECTED = {
    "1b1NOLpwCz8_trim_4.mp4": HEAVY,
    "1b1NOLpwCz8_trim_16.mp4": HEAVY,
    "1s2Tcqr3Rgg_trim_111.mp4": HEAVY,
    "fs0TzsV5NgU_trim_5.mp4": HEAVY,
    "fs0TzsV5NgU_trim_6.mp4": HEAVY,
    "87O1pBSGtR0_trim_102.mp4": SUPPORT,
    "uOAJL-g4Y_w_trim_1.mp4": SUPPORT,
    "zJqzjDX-XFU_trim_45.mp4": SUPPORT,
}


def _items():
    with open(BASELINE, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for row in data["rows"]:
        if row["n_events"]:
            continue
        name = os.path.basename(row["path"])
        out.append({
            "path": os.path.join(ROOT, row["path"]),
            "rel_path": row["path"],
            "positive": name in EXPECTED,
            "expected": EXPECTED.get(name),
            "is_anomaly": bool(row["is_anomaly"]),
        })
    return out


def _run(item):
    start = time.perf_counter()
    root = VLMClient()
    families = (item["expected"],) if item["positive"] else (HEAVY, SUPPORT)
    results = {}
    errors = {}
    for family in families:
        result = dogrula_video(root, item["path"], family)
        results[family] = {
            "prediction": result.hukum.value,
            "answers": result.cevaplar,
            "errors": result.hatalar,
        }
        if result.hatalar:
            errors[family] = result.hatalar
    supported_families = [
        family for family, result in results.items()
        if result["prediction"] == Hukum.SUPPORTED.value and not result["errors"]
    ]
    supported = bool(supported_families)
    semantic_ok = bool(
        item["positive"] and supported_families == [item["expected"]]
    )
    return {
        **{k: v for k, v in item.items() if k != "path"},
        "results": results,
        "supported_families": supported_families,
        "supported": supported,
        "semantic_ok": semantic_ok,
        "errors": errors,
        "latency_s": round(time.perf_counter() - start, 2),
    }


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    items = _items()
    pos = [x for x in items if x["positive"]]
    neg = [x for x in items if not x["positive"]]
    contrast = sum(x["is_anomaly"] for x in neg)
    if (len(pos), len(neg), contrast, len(EXPECTED)) != (8, 111, 18, 8):
        raise RuntimeError(
            f"Ön kayıt örneklemi değişti: pos={len(pos)} neg={len(neg)} "
            f"contrast={contrast}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    pos_rows = [x for x in rows if x["positive"]]
    neg_rows = [x for x in rows if not x["positive"]]
    recovered = sum(x["semantic_ok"] for x in pos_rows)
    fp = sum(x["supported"] for x in neg_rows)
    errors = sum(bool(x["errors"]) for x in rows)
    summary = {
        "positive": len(pos_rows),
        "negative": len(neg_rows),
        "anomaly_contrast_negative": contrast,
        "semantic_recovered": recovered,
        "new_fp": fp,
        "errors": errors,
        "latency_median": statistics.median(x["latency_s"] for x in rows),
        "accepted": recovered >= 2 and fp == 0 and errors == 0,
    }
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"kaynak_video_atomik_v13i_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "contract": contract,
            "baseline": os.path.relpath(BASELINE, ROOT),
            "summary": summary,
            "rows": rows,
        }, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(os.path.relpath(out, ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
