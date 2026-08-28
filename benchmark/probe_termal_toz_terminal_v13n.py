#!/usr/bin/env python
"""v13n: termal/toz çapraz-aile terminal abstain mikro-probu."""
from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import time


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from benchmark.eval_clips import (  # noqa: E402
    _ozel_api_model_sozlesmesini_dogrula,
    evaluate_clip,
)
from dilajan.config import settings  # noqa: E402


RESULTS = os.path.join(ROOT, "benchmark", "results")
SAMPLES = (
    ("data/eval_genelleme_v13_dev/Normal/Normal/ZQVQZdOgDlQ_trim_1.mp4", "Normal", False),
    ("data/eval_genelleme_v13_dev/Anomali/Hazard/1s2Tcqr3Rgg_trim_84.mp4", "Anomali", True),
    ("data/eval_genelleme_v13_dev/Anomali/Hazard/6fhnKhZQE4o_trim_3.mp4", "Anomali", True),
    ("data/eval_genelleme_v13_dev/Anomali/Hazard/7QFdUqCdML8_trim_1.mp4", "Anomali", True),
    ("data/eval_genelleme_v13_dev/Anomali/Hazard/qJLf_5RJFG8_trim_3.mp4", "Anomali", True),
)


def _flags():
    return {
        "closed_family_fallback": settings.closed_family_fallback,
        "structured_fire_dust_veto": settings.structured_fire_dust_veto,
        "thermal_fallback": settings.thermal_fallback,
        "physical_expert_fallback": settings.physical_expert_fallback,
        "industrial_incident_fallback": settings.industrial_incident_fallback,
        "narrow_industrial_retry": settings.narrow_industrial_retry,
        "continuous_fall_fallback": settings.continuous_fall_fallback,
        "yerel_ogrenilmis_izni": settings.yerel_ogrenilmis_izni,
        "model_indirme_izni": settings.model_indirme_izni,
    }


def _run(sample):
    rel, category, positive = sample
    try:
        row = evaluate_clip(os.path.join(ROOT, rel), category)
        return {"positive": positive, "error": None, **row}
    except Exception as ex:
        return {
            "path": rel, "positive": positive, "n_events": 0,
            "isg_trace": [], "error": f"{type(ex).__name__}: {ex}",
        }


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    flags = _flags()
    required_true = {
        "closed_family_fallback", "structured_fire_dust_veto", "thermal_fallback",
        "physical_expert_fallback", "industrial_incident_fallback",
        "narrow_industrial_retry", "continuous_fall_fallback",
    }
    if any(not flags[k] for k in required_true):
        raise RuntimeError(f"Ön kayıt bayrakları açık değil: {flags}")
    if flags["yerel_ogrenilmis_izni"] or flags["model_indirme_izni"]:
        raise RuntimeError(f"Yerel öğrenilmiş çıkarım/model indirme yasak: {flags}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, SAMPLES))
    negative = next(x for x in rows if not x["positive"])
    positives = [x for x in rows if x["positive"]]
    trace = "\n".join(negative.get("isg_trace") or [])
    errors = sum(bool(x.get("error")) for x in rows)
    measured_failures = sum(
        "hata/fail-closed" in "\n".join(x.get("isg_trace") or [])
        or "OLCULEMEDI" in "\n".join(x.get("isg_trace") or [])
        for x in rows
    )
    summary = {
        "negative_events": int(negative.get("n_events", 0)),
        "terminal_trace": "TERMINAL_ABSTAIN" in trace,
        "positive_recovered": sum(int(x.get("n_events", 0)) > 0 for x in positives),
        "positive_total": len(positives),
        "errors": errors,
        "measured_failures": measured_failures,
    }
    summary["accepted"] = bool(
        summary["negative_events"] == 0
        and summary["terminal_trace"]
        and summary["positive_recovered"] == summary["positive_total"] == 4
        and errors == 0 and measured_failures == 0
    )
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"termal_toz_terminal_v13n_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "contract": contract, "flags": flags,
            "summary": summary, "rows": rows,
        }, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(os.path.relpath(out, ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
