#!/usr/bin/env python
"""v11 yangın slotu önerilerinde atomik kapıyı koşullu olarak ölç."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import statistics
import sys
import time


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from benchmark.eval_clips import _ozel_api_model_sozlesmesini_dogrula  # noqa: E402
from benchmark.stats_utils import rate_from_bools  # noqa: E402
from dilajan.isg_kanit import Hukum, dogrula, dogrula_video  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames, servis_videosu  # noqa: E402


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_194722.json")
ANNOTATIONS = os.path.join(ROOT, "data", "isafety_bench", "annotations",
                           "annotations_hazard.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _candidates() -> list[dict]:
    with open(BASELINE, encoding="utf-8") as f:
        baseline = json.load(f)
    with open(ANNOTATIONS, encoding="utf-8") as f:
        anns = {x["video_name"]: x for x in json.load(f)}
    out = []
    for row in baseline["rows"]:
        if not any(e.get("isg_kod") == "Warehouse_Visible_Fire"
                   for e in row.get("events", [])):
            continue
        path = os.path.join(ROOT, row["path"])
        name = os.path.basename(path)
        actions = anns.get(name, {}).get("gt_actions", [])
        out.append({
            "path": path,
            "rel_path": row["path"],
            "positive": "fire incident" in actions,
            "gt_actions": actions,
            "sha256": _sha256(path),
        })
    return out


def _run(item: dict) -> dict:
    start = time.perf_counter()
    frames, info = extract_timestamped_frames(item["path"])
    mode = os.environ.get("DILAJAN_FIRE_PROBE_MODE", "frames").strip().lower()
    if mode == "highres":
        video = servis_videosu(item["path"], max_side=1920)
        result = dogrula_video(VLMClient(), video, "yangın/duman")
    else:
        result = dogrula(VLMClient(), frames, "yangın/duman")
    return {
        **{k: v for k, v in item.items() if k != "path"},
        "duration_s": info.duration,
        "mode": mode,
        "prediction": result.hukum.value,
        "supported": result.hukum == Hukum.SUPPORTED,
        "answers": result.cevaplar,
        "errors": result.hatalar,
        "latency_s": round(time.perf_counter() - start, 2),
    }


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    items = _candidates()
    positives = sum(x["positive"] for x in items)
    negatives = len(items) - positives
    if (positives, negatives) != (11, 15):
        raise RuntimeError(
            f"Ön kayıt örneklemi değişti: positive={positives}, negative={negatives}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    pos = [x for x in rows if x["positive"]]
    neg = [x for x in rows if not x["positive"]]
    tp = sum(x["supported"] for x in pos)
    fp = sum(x["supported"] for x in neg)
    errors = sum(bool(x["errors"]) for x in rows)
    summary = {
        "n": len(rows), "positive": len(pos), "negative": len(neg),
        "tp": tp, "fn": len(pos) - tp, "fp": fp, "tn": len(neg) - fp,
        "recall": rate_from_bools([x["supported"] for x in pos]),
        "fpr": rate_from_bools([x["supported"] for x in neg]),
        "errors": errors,
        "latency_median": statistics.median(x["latency_s"] for x in rows),
        "accepted": tp >= 9 and fp <= 5 and errors == 0,
    }
    os.makedirs(RESULTS, exist_ok=True)
    mode = os.environ.get("DILAJAN_FIRE_PROBE_MODE", "frames").strip().lower()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"fire_atomic_{mode}_v12_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"contract": contract, "baseline": os.path.relpath(BASELINE, ROOT),
                   "summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(os.path.relpath(out, ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
