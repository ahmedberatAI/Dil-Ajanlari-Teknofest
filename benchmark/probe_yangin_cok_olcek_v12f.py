#!/usr/bin/env python
"""v12f: olay üretmeyen kliplerde çok-ölçekli doğrudan yangın atomik probu."""
from __future__ import annotations

import concurrent.futures
import hashlib
import io
import json
import os
import statistics
import sys
import time

from PIL import Image


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from benchmark.eval_clips import _ozel_api_model_sozlesmesini_dogrula  # noqa: E402
from dilajan.isg_kanit import Hukum, dogrula  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_194722.json")
HAZARD_ANN = os.path.join(ROOT, "data", "isafety_bench", "annotations",
                          "annotations_hazard.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")
VIEWS = {
    "ust": (0.0, 0.0, 1.0, 0.60),
    "alt": (0.0, 0.40, 1.0, 1.0),
    "sol": (0.0, 0.0, 0.60, 1.0),
    "sag": (0.40, 0.0, 1.0, 1.0),
}


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _items() -> list[dict]:
    with open(BASELINE, encoding="utf-8") as f:
        baseline = json.load(f)
    with open(HAZARD_ANN, encoding="utf-8") as f:
        anns = {x["video_name"]: x for x in json.load(f)}
    out = []
    for row in baseline["rows"]:
        if row["n_events"]:
            continue
        name = os.path.basename(row["path"])
        fire = bool(row["is_anomaly"] and
                    "fire incident" in anns.get(name, {}).get("gt_actions", []))
        normal_tn = not row["is_anomaly"]
        if not (fire or normal_tn):
            continue
        path = os.path.join(ROOT, row["path"])
        out.append({"path": path, "rel_path": row["path"], "positive": fire,
                    "sha256": _sha256(path)})
    return out


def _crop_frames(frames, box):
    out = []
    for ts, jpeg in frames:
        img = Image.open(io.BytesIO(jpeg)).convert("RGB")
        w, h = img.size
        x1, y1, x2, y2 = box
        crop = img.crop((int(w * x1), int(h * y1), int(w * x2), int(h * y2)))
        scale = 768 / max(crop.size)
        if scale != 1.0:
            crop = crop.resize((max(2, int(crop.width * scale)),
                                max(2, int(crop.height * scale))), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        crop.save(buf, format="JPEG", quality=92)
        out.append((ts, buf.getvalue()))
    return out


def _run(item: dict) -> dict:
    start = time.perf_counter()
    frames, info = extract_timestamped_frames(item["path"])
    root = VLMClient()
    views = {}
    supported = False
    for name, box in VIEWS.items():
        result = dogrula(root, _crop_frames(frames, box), "yangın/duman")
        views[name] = {"prediction": result.hukum.value,
                       "answers": result.cevaplar, "errors": result.hatalar}
        supported = supported or result.hukum == Hukum.SUPPORTED
    return {
        **{k: v for k, v in item.items() if k != "path"},
        "duration_s": info.duration,
        "supported": supported,
        "views": views,
        "latency_s": round(time.perf_counter() - start, 2),
    }


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    items = _items()
    positives = sum(x["positive"] for x in items)
    negatives = len(items) - positives
    if (positives, negatives) != (2, 43):
        raise RuntimeError(
            f"Ön kayıt örneklemi değişti: positive={positives}, negative={negatives}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    pos = [x for x in rows if x["positive"]]
    neg = [x for x in rows if not x["positive"]]
    recovered = sum(x["supported"] for x in pos)
    new_fp = sum(x["supported"] for x in neg)
    errors = sum(any(v["errors"] for v in x["views"].values()) for x in rows)
    summary = {
        "n": len(rows), "positive": len(pos), "negative": len(neg),
        "recovered": recovered, "new_fp": new_fp, "errors": errors,
        "latency_median": statistics.median(x["latency_s"] for x in rows),
        "accepted": recovered >= 1 and new_fp == 0 and errors == 0,
    }
    os.makedirs(RESULTS, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"yangin_cok_olcek_v12f_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"contract": contract, "baseline": os.path.relpath(BASELINE, ROOT),
                   "views": VIEWS, "summary": summary, "rows": rows},
                  f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(os.path.relpath(out, ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
