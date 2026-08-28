#!/usr/bin/env python
"""v13h: ani lokal patlama/parlama için üç atomlu özel-API uzman probu."""
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
from dilajan.isg_kanit import ATOMIK_SISTEM  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_234737.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")
POSITIVES = {
    "1gx7OURLLBs_trim_6.mp4",
    "1gx7OURLLBs_trim_8.mp4",
}
CHOICES = ("A", "B", "C", "D")

VISUAL_PROMPT = (
    "Bu kısa videoda tek bir lokal noktada ani patlama/enerji boşalmasına ait "
    "yoğun beyaz-turuncu parlak çekirdek ile yeni oluşan bulut, duman veya "
    "parçacık saçılması birlikte açıkça görünüyor mu? A: Evet, lokal patlama "
    "çekirdeği ve yeni bulut/parçacık birlikte açık. B: Yalnız far, el feneri, "
    "sabit lamba, yansıma veya kamera pozlaması. C: Böyle bir belirti yok. "
    "D: Görüntü yetersiz. Açıklamasız yalnız A, B, C veya D yaz."
)
TEMPORAL_PROMPT = (
    "Videoyu kronolojik izle. Lokal parlak olay sıradan durumdan aniden başlayıp "
    "hızla genişliyor veya şiddetleniyor, ardından sönüyor/dağılıyor mu? A: Ani "
    "başlangıç-genişleme-sönme patlama geçişi açık. B: Hareketli far/fener huzmesi, "
    "sabit ışık veya yalnız kamera pozlama değişimi. C: İlgili geçiş yok. "
    "D: Görüntü yetersiz. Açıklamasız yalnız A, B, C veya D yaz."
)
AFTERMATH_PROMPT = (
    "Videoyu kronolojik izle. Parlama tepesinin hemen ardından aynı lokal bölgede "
    "yeni duman/bulut/parçacık izi kalıyor veya yakındaki gerçek kişi doğrudan "
    "irkilip geri çekiliyor/kaçıyor mu? A: Olayla zaman uyumlu fiziksel iz veya "
    "doğrudan tepki açık. B: Yalnız rutin/önceden başlamış insan hareketi ya da "
    "ışık huzmesi var. C: Sonuç/tepki yok. D: Görüntü yetersiz. Açıklamasız yalnız "
    "A, B, C veya D yaz."
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


def _ask(root, role, frames, prompt):
    return root.gorev(role).analyze_frames(
        frames, prompt, temperature=0.0, max_tokens=8,
        system=ATOMIK_SISTEM, guided_choice=CHOICES,
    ).strip().upper()


def _run(item):
    start = time.perf_counter()
    frames, _ = extract_timestamped_frames(item["path"])
    root = VLMClient()
    answers = {}
    errors = {}
    for name, role, prompt in (
        ("visual", "algi", VISUAL_PROMPT),
        ("temporal", "olay", TEMPORAL_PROMPT),
        ("aftermath", "olay", AFTERMATH_PROMPT),
    ):
        try:
            answers[name] = _ask(root, role, frames, prompt)
        except Exception as ex:
            errors[name] = f"{type(ex).__name__}: {ex}"
    supported = bool(not errors and answers == {
        "visual": "A", "temporal": "A", "aftermath": "A",
    })
    return {
        **{k: v for k, v in item.items() if k != "path"},
        "answers": answers,
        "supported": supported,
        "errors": errors,
        "latency_s": round(time.perf_counter() - start, 2),
    }


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    items = _items()
    pos = [x for x in items if x["positive"]]
    neg = [x for x in items if not x["positive"]]
    contrast = sum(x["is_anomaly"] for x in neg)
    if (len(pos), len(neg), contrast) != (2, 117, 24):
        raise RuntimeError(
            f"Ön kayıt örneklemi değişti: pos={len(pos)} neg={len(neg)} "
            f"contrast={contrast}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    pos_rows = [x for x in rows if x["positive"]]
    neg_rows = [x for x in rows if not x["positive"]]
    recovered = sum(x["supported"] for x in pos_rows)
    fp = sum(x["supported"] for x in neg_rows)
    errors = sum(bool(x["errors"]) for x in rows)
    summary = {
        "positive": len(pos_rows),
        "negative": len(neg_rows),
        "anomaly_contrast_negative": contrast,
        "recovered": recovered,
        "new_fp": fp,
        "errors": errors,
        "latency_median": statistics.median(x["latency_s"] for x in rows),
        "accepted": recovered == 2 and fp == 0 and errors == 0,
    }
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"ani_patlama_parlama_v13h_{stamp}.json")
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
