#!/usr/bin/env python
"""v13j: dar scout seçimi sonrası kaynak-video atomik yeniden hakemliği."""
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
from benchmark.probe_dar_endustriyel_ikinci_tarama_v13e import (  # noqa: E402
    CHOICES, SCAN_PROMPT,
)
from dilajan.isg_kanit import ATOMIK_SISTEM, Hukum, dogrula, dogrula_video  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_234737.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")
TARGET = "KISI_DESTEK_KAYBI"
FAMILY = "kişi destek kaybı/düşme"
POSITIVES = {
    "87O1pBSGtR0_trim_102.mp4",
    "uOAJL-g4Y_w_trim_1.mp4",
    "zJqzjDX-XFU_trim_45.mp4",
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
            "positive": name in POSITIVES,
            "is_anomaly": bool(row["is_anomaly"]),
        })
    return out


def _run(item):
    start = time.perf_counter()
    frames, _ = extract_timestamped_frames(item["path"])
    root = VLMClient()
    errors = {}
    selected = ""
    frame_result = source_result = None
    try:
        selected = root.gorev("olay").analyze_frames(
            frames, SCAN_PROMPT, temperature=0.0, max_tokens=24,
            system=ATOMIK_SISTEM, guided_choice=CHOICES,
        ).strip().upper()
    except Exception as ex:
        errors["scan"] = f"{type(ex).__name__}: {ex}"
    if selected == TARGET and not errors:
        frame_result = dogrula(root, frames, FAMILY)
        if frame_result.hatalar:
            errors["frame"] = frame_result.hatalar
        elif frame_result.hukum != Hukum.SUPPORTED:
            source_result = dogrula_video(root, item["path"], FAMILY)
            if source_result.hatalar:
                errors["source"] = source_result.hatalar
    frame_supported = bool(
        frame_result and frame_result.hukum == Hukum.SUPPORTED and not frame_result.hatalar)
    source_supported = bool(
        source_result and source_result.hukum == Hukum.SUPPORTED and not source_result.hatalar)
    supported = bool((frame_supported or source_supported) and not errors)
    return {
        **{k: v for k, v in item.items() if k != "path"},
        "selected": selected,
        "frame_prediction": frame_result.hukum.value if frame_result else None,
        "frame_answers": frame_result.cevaplar if frame_result else {},
        "source_prediction": source_result.hukum.value if source_result else None,
        "source_answers": source_result.cevaplar if source_result else {},
        "frame_supported": frame_supported,
        "source_supported": source_supported,
        "supported": supported,
        "semantic_ok": bool(supported and item["positive"]),
        "errors": errors,
        "latency_s": round(time.perf_counter() - start, 2),
    }


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    items = _items()
    pos = [x for x in items if x["positive"]]
    neg = [x for x in items if not x["positive"]]
    contrast = sum(x["is_anomaly"] for x in neg)
    if (len(pos), len(neg), contrast) != (3, 116, 23):
        raise RuntimeError(
            f"Ön kayıt örneklemi değişti: pos={len(pos)} neg={len(neg)} "
            f"contrast={contrast}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    pos_rows = [x for x in rows if x["positive"]]
    neg_rows = [x for x in rows if not x["positive"]]
    recovered = sum(x["semantic_ok"] for x in pos_rows)
    source_recovered = sum(x["semantic_ok"] and x["source_supported"] for x in pos_rows)
    fp = sum(x["supported"] for x in neg_rows)
    errors = sum(bool(x["errors"]) for x in rows)
    summary = {
        "positive": len(pos_rows),
        "negative": len(neg_rows),
        "anomaly_contrast_negative": contrast,
        "semantic_recovered": recovered,
        "source_recovered": source_recovered,
        "new_fp": fp,
        "errors": errors,
        "latency_median": statistics.median(x["latency_s"] for x in rows),
        "accepted": source_recovered >= 1 and recovered >= source_recovered
                    and fp == 0 and errors == 0,
    }
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"rota_kilitli_kaynak_hakem_v13j_{stamp}.json")
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
