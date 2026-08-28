#!/usr/bin/env python
"""v12h: makine sıkışma ailesinde gerçek daralma ile rutin boru işini ayır."""
from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import time


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from benchmark.eval_clips import _ozel_api_model_sozlesmesini_dogrula  # noqa: E402
from dilajan.isg_kanit import Hukum, dogrula  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402


CASES = (
    ("data/eval_genelleme/Anomali/Hazard/_a46_s5WViY_trim_0.mp4", True),
    ("data/eval_genelleme/Normal/Normal/YE7VTtHbtQA_trim_0.mp4", False),
)
RESULTS = os.path.join(ROOT, "benchmark", "results")


def _run(case):
    rel, positive = case
    start = time.perf_counter()
    frames, _ = extract_timestamped_frames(os.path.join(ROOT, rel))
    result = dogrula(VLMClient(), frames, "makineye sıkışma/ezilme")
    return {"rel_path": rel, "positive": positive,
            "prediction": result.hukum.value, "supported": result.supported,
            "answers": result.cevaplar, "errors": result.hatalar,
            "latency_s": round(time.perf_counter() - start, 2)}


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(_run, CASES))
    pos = next(x for x in rows if x["positive"])
    neg = next(x for x in rows if not x["positive"])
    errors = sum(bool(x["errors"]) for x in rows)
    summary = {"tp": int(pos["supported"]), "fp": int(neg["supported"]),
               "errors": errors,
               "accepted": pos["supported"] and not neg["supported"] and errors == 0}
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"makine_geometri_v12h_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"contract": contract, "summary": summary, "rows": rows},
                  f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(os.path.relpath(out, ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
