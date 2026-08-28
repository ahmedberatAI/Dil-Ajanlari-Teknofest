#!/usr/bin/env python
"""v13f: v13e scout'unun yalnız dar kişi/makine dallarını taze tekrarla."""
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
    BASELINE, CHOICES, EXPECTED, SCAN_PROMPT, _items,
)
from dilajan.isg_kanit import ATOMIK_SISTEM, Hukum, dogrula  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402


RESULTS = os.path.join(ROOT, "benchmark", "results")
ALLOWLIST = {
    "MAKINE_YAKALAMA": "aktif makine yakalama/sıkışma",
    "KISI_DESTEK_KAYBI": "kişi destek kaybı/düşme",
}


def _run(item):
    start = time.perf_counter()
    frames, _ = extract_timestamped_frames(item["path"])
    root = VLMClient()
    errors = {}
    selected = ""
    try:
        selected = root.gorev("olay").analyze_frames(
            frames, SCAN_PROMPT, temperature=0.0, max_tokens=24,
            system=ATOMIK_SISTEM, guided_choice=CHOICES,
        ).strip().upper()
    except Exception as ex:
        errors["scan"] = f"{type(ex).__name__}: {ex}"
    family = ALLOWLIST.get(selected)
    result = None
    if family and not errors:
        result = dogrula(root, frames, family)
        if result.hatalar:
            errors["evidence"] = result.hatalar
    supported = bool(result and result.hukum == Hukum.SUPPORTED and not errors)
    semantic_ok = bool(supported and item["expected"] == selected)
    return {
        **{k: v for k, v in item.items() if k != "path"},
        "selected": selected,
        "family": family,
        "supported": supported,
        "semantic_ok": semantic_ok,
        "prediction": result.hukum.value if result else None,
        "answers": result.cevaplar if result else {},
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
        raise RuntimeError("Ön kayıt örneklemi değişti")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    pos_rows = [x for x in rows if x["positive"]]
    neg_rows = [x for x in rows if not x["positive"]]
    recovered = sum(x["supported"] for x in pos_rows)
    semantic = sum(x["semantic_ok"] for x in pos_rows)
    fp = sum(x["supported"] for x in neg_rows)
    errors = sum(bool(x["errors"]) for x in rows)
    summary = {
        "positive": len(pos_rows),
        "negative": len(neg_rows),
        "anomaly_contrast_negative": contrast,
        "recovered": recovered,
        "semantic_supported": semantic,
        "new_fp": fp,
        "errors": errors,
        "latency_median": statistics.median(x["latency_s"] for x in rows),
        "accepted": recovered >= 2 and semantic == recovered and fp == 0 and errors == 0,
    }
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"dar_kisi_makine_ikinci_tarama_v13f_{stamp}.json")
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
