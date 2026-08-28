#!/usr/bin/env python
"""v13g: iki farklı scout + iki atom tekrarındaki dar çelişki kurtarması."""
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
    CHOICES as NARROW_CHOICES, EXPECTED, SCAN_PROMPT as NARROW_PROMPT,
)
from benchmark.probe_endustriyel_olay_scout_v13a import (  # noqa: E402
    CHOICES as BROAD_CHOICES, SCAN_PROMPT as BROAD_PROMPT,
)
from dilajan.isg_kanit import ATOMIK_SISTEM, dogrula  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_234737.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")
TARGET = "KISI_DESTEK_KAYBI"
FAMILY = "kişi destek kaybı/düşme"


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


def _scan(root, frames, prompt, choices):
    return root.gorev("olay").analyze_frames(
        frames, prompt, temperature=0.0, max_tokens=24,
        system=ATOMIK_SISTEM, guided_choice=choices,
    ).strip().upper()


def _conflict(result):
    return bool(
        not result.hatalar
        and result.cevaplar.get("riskli_kisi_pozu", "").strip().upper()
        == "RUTIN_ZEMIN_HAREKETI"
        and result.cevaplar.get("destek_kaybi_dusme", "").strip().upper()
        == "DESTEK_KAYBI_DUSME_ASILMA"
    )


def _run(item):
    start = time.perf_counter()
    frames, _ = extract_timestamped_frames(item["path"])
    root = VLMClient()
    errors = {}
    broad = narrow = ""
    first = second = None
    try:
        broad = _scan(root, frames, BROAD_PROMPT, BROAD_CHOICES)
        narrow = _scan(root, frames, NARROW_PROMPT, NARROW_CHOICES)
    except Exception as ex:
        errors["scan"] = f"{type(ex).__name__}: {ex}"
    if broad == narrow == TARGET and not errors:
        first = dogrula(root, frames, FAMILY)
        second = dogrula(root, frames, FAMILY)
        if first.hatalar or second.hatalar:
            errors["evidence"] = {"first": first.hatalar, "second": second.hatalar}
    rescued = bool(first and second and _conflict(first) and _conflict(second) and not errors)
    semantic_ok = bool(rescued and item["expected"] == TARGET)
    return {
        **{k: v for k, v in item.items() if k != "path"},
        "broad": broad,
        "narrow": narrow,
        "first_answers": first.cevaplar if first else {},
        "second_answers": second.cevaplar if second else {},
        "rescued": rescued,
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
    if (len(pos), len(neg), contrast, len(EXPECTED)) != (7, 112, 19, 7):
        raise RuntimeError(
            f"Ön kayıt örneklemi değişti: pos={len(pos)} neg={len(neg)} "
            f"contrast={contrast}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    pos_rows = [x for x in rows if x["positive"]]
    neg_rows = [x for x in rows if not x["positive"]]
    recovered = sum(x["rescued"] for x in pos_rows)
    semantic = sum(x["semantic_ok"] for x in pos_rows)
    fp = sum(x["rescued"] for x in neg_rows)
    errors = sum(bool(x["errors"]) for x in rows)
    summary = {
        "positive": len(pos_rows),
        "negative": len(neg_rows),
        "anomaly_contrast_negative": contrast,
        "conflict_recovered": recovered,
        "semantic_supported": semantic,
        "new_fp": fp,
        "errors": errors,
        "latency_median": statistics.median(x["latency_s"] for x in rows),
        "accepted": recovered >= 1 and semantic == recovered and fp == 0 and errors == 0,
    }
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"cift_scout_celiski_v13g_{stamp}.json")
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
