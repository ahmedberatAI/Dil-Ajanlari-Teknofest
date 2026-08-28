#!/usr/bin/env python
"""v12p: olay-sız fiziksel FN ailelerini kapalı scout + atomik kapıyla ölç."""
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


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_213224.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")
POSITIVES = {
    "0RcFgtZFhgg_clip0_trim_2.mp4": "KAVGA",
    "0W6vtPakFt8_trim_2.mp4": "ARAC_KONTROL_KAYBI",
    "1s2Tcqr3Rgg_trim_126.mp4": "YUK_DENGE_KAYBI",
    "87O1pBSGtR0_trim_24.mp4": "YUK_DENGE_KAYBI",
    "aTW27C3AG-o_trim_147.mp4": "SARKAN_KISI",
    "aTW27C3AG-o_trim_55.mp4": "ARAC_KONTROL_KAYBI",
}
CHOICES = ("SARKAN_KISI", "ARAC_KONTROL_KAYBI", "YUK_DENGE_KAYBI", "KAVGA",
           "OLAY_YOK", "GORUNMUYOR")
FAMILIES = {
    "SARKAN_KISI": "destekten sarkan kişi",
    "ARAC_KONTROL_KAYBI": "kontrolünü kaybeden araç",
    "YUK_DENGE_KAYBI": "dengesini kaybeden ağır yük",
    "KAVGA": "karşılıklı fiziksel kavga",
}
SCAN_PROMPT = (
    "Bu kısa videoyu kronolojik incele ve yalnız doğrudan görülen en belirgin fiziksel "
    "olay etiketini seç. SARKAN_KISI: kişi ayak desteğini kaybedip yüksek kenar/borudan "
    "elleriyle asılı kalır. ARAC_KONTROL_KAYBI: araç/iş makinesi savrulur, devrilir, "
    "kenardan düşer, çarpar veya içerideki kişiyi fırlatacak şiddette yön/duruş kaybeder. "
    "YUK_DENGE_KAYBI: ağır yük düşer/kayar ya da vinç/taşıyıcı yük nedeniyle açıkça "
    "dengesizleşir. KAVGA: iki kişi tekrarlanan sert vurma/tekme/itme/boğuşma yapar. "
    "Rutin sürüş, manevra, taşıma, tırmanma, çalışma, kalabalık hareketi ve yalnız niyet "
    "tahmini olay değildir. Hiçbiri açık değilse OLAY_YOK; görüntü yetersizse GORUNMUYOR. "
    "Açıklamasız yalnız izin verilen etiketi yaz."
)


def _items():
    with open(BASELINE, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for row in data["rows"]:
        name = os.path.basename(row["path"])
        positive = name in POSITIVES
        negative = not row["is_anomaly"] and not row["n_events"]
        if positive or negative:
            out.append({"path": os.path.join(ROOT, row["path"]),
                        "rel_path": row["path"], "positive": positive,
                        "target": POSITIVES.get(name)})
    return out


def _run(item):
    start = time.perf_counter()
    frames, _ = extract_timestamped_frames(item["path"])
    root = VLMClient()
    errors = {}
    selected = ""
    try:
        selected = root.gorev("olay").analyze_frames(
            frames, SCAN_PROMPT, temperature=0.0, max_tokens=24,
            system=ATOMIK_SISTEM, guided_choice=CHOICES).strip().upper()
    except Exception as ex:
        errors["scan"] = f"{type(ex).__name__}: {ex}"
    family = FAMILIES.get(selected)
    result = None
    if family and not errors:
        result = dogrula(root, frames, family)
        if result.hatalar:
            errors["evidence"] = result.hatalar
    supported = bool(result and result.hukum == Hukum.SUPPORTED and not errors)
    return {**{k: v for k, v in item.items() if k != "path"},
            "selected": selected, "family": family, "supported": supported,
            "prediction": result.hukum.value if result else None,
            "answers": result.cevaplar if result else {}, "errors": errors,
            "latency_s": round(time.perf_counter() - start, 2)}


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    items = _items()
    p = sum(x["positive"] for x in items)
    n = len(items) - p
    if (p, n) != (6, 48):
        raise RuntimeError(f"Ön kayıt örneklemi değişti: positive={p}, negative={n}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    pos = [x for x in rows if x["positive"]]
    neg = [x for x in rows if not x["positive"]]
    tp = sum(x["supported"] for x in pos)
    fp = sum(x["supported"] for x in neg)
    errors = sum(bool(x["errors"]) for x in rows)
    target_match = sum(x["selected"] == x["target"] for x in pos)
    summary = {"positive": p, "negative": n, "scout_target_match": target_match,
               "recovered": tp, "new_fp": fp, "errors": errors,
               "latency_median": statistics.median(x["latency_s"] for x in rows),
               "accepted": tp >= 3 and fp == 0 and errors == 0}
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"fiziksel_uzmanlar_v12p_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"contract": contract, "baseline": os.path.relpath(BASELINE, ROOT),
                   "summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(os.path.relpath(out, ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
