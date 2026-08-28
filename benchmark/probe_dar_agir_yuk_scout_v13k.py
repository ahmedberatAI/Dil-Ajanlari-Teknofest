#!/usr/bin/env python
"""v13k: olay-sız klipte dar ağır-yük scout + mevcut atomik aile."""
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
from dilajan.isg_kanit import ATOMIK_SISTEM, Hukum, dogrula  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_234737.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")
FAMILY = "dengesini kaybeden ağır yük"
POSITIVES = {
    "1b1NOLpwCz8_trim_4.mp4",
    "1b1NOLpwCz8_trim_16.mp4",
    "1s2Tcqr3Rgg_trim_111.mp4",
    "fs0TzsV5NgU_trim_5.mp4",
    "fs0TzsV5NgU_trim_6.mp4",
}
CHOICES = ("KONTROLSUZ_AGIR_YUK", "KONTROLLU_TASIMA", "OLAY_YOK", "GORUNMUYOR")
SCAN_PROMPT = (
    "Bu kısa videoyu kronolojik incele ve yalnız ağır-yük hareketini sınıflandır. "
    "KONTROLSUZ_AGIR_YUK: ağır levha, kiriş, kalıp, platform, pres, askıdaki yük "
    "veya taşıyıcı sistem destek/denge kaybederek serbestçe düşer, devrilir, kayar, "
    "kopar ya da insanlara doğru kontrolsüz iner. KONTROLLU_TASIMA: vinç, forklift "
    "veya kişiler yükü planlı biçimde kaldırır, indirir, yerleştirir veya taşır; yük "
    "destek ve kontrolünü korur. Küçük el aleti, yalnız kişi düşmesi, ışık/buhar, "
    "kamera hareketi ve sabit yük ağır-yük olayı değildir. Ağır yük yoksa OLAY_YOK; "
    "kanıt seçilemiyorsa GORUNMUYOR. Açıklamasız yalnız izin verilen etiketi yaz."
)


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
    selected = ""
    result = None
    errors = {}
    try:
        selected = root.gorev("olay").analyze_frames(
            frames, SCAN_PROMPT, temperature=0.0, max_tokens=24,
            system=ATOMIK_SISTEM, guided_choice=CHOICES,
        ).strip().upper()
    except Exception as ex:
        errors["scan"] = f"{type(ex).__name__}: {ex}"
    if selected == "KONTROLSUZ_AGIR_YUK" and not errors:
        result = dogrula(root, frames, FAMILY)
        if result.hatalar:
            errors["evidence"] = result.hatalar
    supported = bool(result and result.hukum == Hukum.SUPPORTED and not errors)
    return {
        **{k: v for k, v in item.items() if k != "path"},
        "selected": selected,
        "prediction": result.hukum.value if result else None,
        "answers": result.cevaplar if result else {},
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
    if (len(pos), len(neg), contrast) != (5, 114, 21):
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
    out = os.path.join(RESULTS, f"dar_agir_yuk_scout_v13k_{stamp}.json")
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
