#!/usr/bin/env python
"""v13l: kaynak videoda kişi + kontrolsüz geçiş + fiziksel sonuç AND kapısı."""
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


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_234737.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")
POSITIVES = {
    "87O1pBSGtR0_trim_102.mp4",
    "uOAJL-g4Y_w_trim_1.mp4",
    "zJqzjDX-XFU_trim_45.mp4",
}
CHOICES = ("A", "B", "C", "D")
QUESTIONS = (
    (
        "person", "algi",
        "Videoda olay boyunca izlenebilen gerçek bir kişi, bedeni ve destek/zemin "
        "ilişkisi seçilebilir biçimde görünüyor mu? A: Gerçek kişi ve bedeni yeterli "
        "açıklıkta görünür. B: Yalnız nesne, gölge, araç veya çok küçük/örtülü şekil. "
        "C: Kişi yok. D: Görüntü yetersiz. Açıklamasız yalnız A, B, C veya D yaz."
    ),
    (
        "transition", "olay",
        "Videoyu kronolojik izle. Aynı gerçek kişi destekli/dik konumdan istemsiz "
        "ve kontrolsüz biçimde aşağı hareket edip dengesini veya ayak desteğini "
        "kaybediyor mu? A: Kontrolsüz destek kaybı/düşey düşüş açık. B: Rutin eğilme, "
        "çömelme, yük kaldırma, planlı iniş, normal koşma/yürüme veya sahne kesimi. "
        "C: Böyle geçiş yok. D: Görüntü yetersiz. Açıklamasız yalnız A, B, C veya D yaz."
    ),
    (
        "outcome", "olay",
        "Videoyu kronolojik izle. Aynı kişinin kontrolsüz geçişi fiziksel bir sonuçla "
        "tamamlanıyor mu: bedeni zemine/sert yüzeye temas ediyor, kişi destekten asılı "
        "kalıyor veya düşme temasından sonra yeniden toparlanıyor mu? A: Aynı kişide "
        "düşme teması/asilma ve sonucu açık. B: Yalnız yürüme/koşma, rutin taşıma veya "
        "nesne düşürme; kişi düşmüyor. C: Farklı kişi/sahne ya da sonuç yok. "
        "D: Görüntü yetersiz. Açıklamasız yalnız A, B, C veya D yaz."
    ),
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
    root = VLMClient()
    answers = {}
    errors = {}
    try:
        session = root.video_oturumu(item["path"], system=ATOMIK_SISTEM)
    except Exception as ex:
        session = None
        errors["session"] = f"{type(ex).__name__}: {ex}"
    if session is not None and not session.hazir:
        errors["session"] = session.hata or "kurulamadi"
    if session is not None and session.hazir and not errors:
        original = session.istemci
        try:
            for name, role, prompt in QUESTIONS:
                session.istemci = root.gorev(role)
                answer = session.sor(
                    prompt, guided_choice=CHOICES, temperature=0.0,
                    max_tokens=8, hatirla=False)
                if answer is None:
                    errors[name] = session.hata or "cevap alinamadi"
                else:
                    answers[name] = answer.strip().upper()
        finally:
            session.istemci = original
    supported = bool(
        not errors and answers == {"person": "A", "transition": "A", "outcome": "A"})
    return {
        **{k: v for k, v in item.items() if k != "path"},
        "answers": answers,
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
        "accepted": recovered >= 1 and fp == 0 and errors == 0,
    }
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"sonuclu_destek_kaybi_v13l_{stamp}.json")
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
