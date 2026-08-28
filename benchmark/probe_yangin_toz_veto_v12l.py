#!/usr/bin/env python
"""v12l: yapılandırılmış yangında yalnız açık BUHAR/TOZ alternatifini veto et."""
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
from benchmark.probe_fire_atomic_v12 import _candidates  # noqa: E402
from dilajan.isg_kanit import dogrula  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402


RESULTS = os.path.join(ROOT, "benchmark", "results")
VETO = "BUHAR_TOZ_PARLAMA"


def _run(item):
    start = time.perf_counter()
    frames, _ = extract_timestamped_frames(item["path"])
    result = dogrula(VLMClient(), frames, "yangın/duman")
    temporal = result.cevaplar.get("zamansal_davranis", "").strip().upper()
    veto = temporal == VETO and not result.hatalar
    return {**{k: v for k, v in item.items() if k != "path"},
            "temporal": temporal, "veto": veto, "kept": not veto,
            "answers": result.cevaplar, "errors": result.hatalar,
            "latency_s": round(time.perf_counter() - start, 2)}


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    items = _candidates()
    p, n = sum(x["positive"] for x in items), sum(not x["positive"] for x in items)
    if (p, n) != (11, 15):
        raise RuntimeError(f"Ön kayıt örneklemi değişti: positive={p}, negative={n}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    pos = [x for x in rows if x["positive"]]
    neg = [x for x in rows if not x["positive"]]
    kept_pos = sum(x["kept"] for x in pos)
    vetoed_neg = sum(x["veto"] for x in neg)
    errors = sum(bool(x["errors"]) for x in rows)
    summary = {"positive": len(pos), "negative": len(neg),
               "kept_positive": kept_pos, "vetoed_negative": vetoed_neg,
               "errors": errors,
               "latency_median": statistics.median(x["latency_s"] for x in rows),
               "accepted": kept_pos >= 10 and vetoed_neg >= 10 and errors == 0}
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"yangin_toz_veto_v12l_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"contract": contract, "summary": summary, "rows": rows},
                  f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(os.path.relpath(out, ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
