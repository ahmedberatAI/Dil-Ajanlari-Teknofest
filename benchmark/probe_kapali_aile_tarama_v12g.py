#!/usr/bin/env python
"""v12g: olay-sız kliplerde kapalı aile taraması ve bağımsız atomik doğrulama."""
from __future__ import annotations

import concurrent.futures
import hashlib
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


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_194722.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")
CHOICES = (
    "YANGIN_DUMAN", "KISI_DUSME", "SIDDET_SILAH", "ARAC_KAZA", "YUK_COKME",
    "MAKINE_SIKISMA", "ASKIDA_YUK", "SINIR_IHLALI", "KKD_EKSIK",
    "OLAY_YOK", "GORUNMUYOR",
)
FAMILIES = {
    "YANGIN_DUMAN": "yangın/duman",
    "KISI_DUSME": "düşme/yaralı kişi",
    "SIDDET_SILAH": "şiddet/silah",
    "ARAC_KAZA": "çarpışma/devrilme",
    "YUK_COKME": "kontrolsüz yük/çökme",
    "MAKINE_SIKISMA": "makineye sıkışma/ezilme",
    "ASKIDA_YUK": "askıda yük/düşme bölgesi",
    "SINIR_IHLALI": "yetkisiz giriş/müdahale",
    "KKD_EKSIK": "KKD eksikliği",
}
SCAN_PROMPT = (
    "Bu kısa videoyu kronolojik incele. Yalnız doğrudan görülen en belirgin yüksek "
    "öncelikli İSG olay AİLESİNİ seç. Rutin çalışma/yürüme/taşıma olay değildir. "
    "Yangın için gerçek alev/yayılan duman; kişi düşmesi için zemine geçiş/yerde yatma; "
    "araç kazası için temas veya kontrol kaybı/devrilme; yük çökmesi için yük/raf/yapının "
    "destekli konumunu kaybetmesi; makine sıkışması için beden/uzuv/giysinin yakalanması; "
    "askıda yük için kişinin düşme-salınım bölgesinde kalması; sınır ihlali için görünür "
    "bariyer/kısıtlı sınır geçişi; KKD için yeterince görünür kişide açık eksiklik gerekir. "
    "Hiçbiri açık değilse OLAY_YOK, görüntü yetersizse GORUNMUYOR seç. Yalnız izin verilen "
    "etiketi yaz."
)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _items() -> list[dict]:
    with open(BASELINE, encoding="utf-8") as f:
        baseline = json.load(f)
    out = []
    for row in baseline["rows"]:
        if row["n_events"]:
            continue
        path = os.path.join(ROOT, row["path"])
        out.append({"path": path, "rel_path": row["path"],
                    "positive": bool(row["is_anomaly"]), "sha256": _sha256(path)})
    return out


def _run(item: dict) -> dict:
    start = time.perf_counter()
    frames, info = extract_timestamped_frames(item["path"])
    root = VLMClient()
    errors = {}
    selected = ""
    try:
        selected = root.gorev("olay").analyze_frames(
            frames, SCAN_PROMPT, temperature=0.0, max_tokens=20,
            system=ATOMIK_SISTEM, guided_choice=CHOICES).strip().upper()
    except Exception as ex:
        errors["scan"] = f"{type(ex).__name__}: {ex}"
    family = FAMILIES.get(selected)
    evidence = None
    if family and not errors:
        result = dogrula(root, frames, family)
        evidence = {"family": family, "prediction": result.hukum.value,
                    "answers": result.cevaplar, "errors": result.hatalar}
        if result.hatalar:
            errors["evidence"] = result.hatalar
    supported = bool(evidence and evidence["prediction"] == Hukum.SUPPORTED.value
                     and not errors)
    return {
        **{k: v for k, v in item.items() if k != "path"},
        "duration_s": info.duration, "selected": selected,
        "supported": supported, "evidence": evidence, "errors": errors,
        "latency_s": round(time.perf_counter() - start, 2),
    }


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    items = _items()
    positives = sum(x["positive"] for x in items)
    negatives = len(items) - positives
    if (positives, negatives) != (17, 43):
        raise RuntimeError(
            f"Ön kayıt örneklemi değişti: positive={positives}, negative={negatives}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    pos = [x for x in rows if x["positive"]]
    neg = [x for x in rows if not x["positive"]]
    recovered = sum(x["supported"] for x in pos)
    new_fp = sum(x["supported"] for x in neg)
    errors = sum(bool(x["errors"]) for x in rows)
    summary = {
        "n": len(rows), "positive": len(pos), "negative": len(neg),
        "recovered": recovered, "new_fp": new_fp, "errors": errors,
        "latency_median": statistics.median(x["latency_s"] for x in rows),
        "accepted": recovered >= 3 and new_fp == 0 and errors == 0,
    }
    os.makedirs(RESULTS, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"kapali_aile_tarama_v12g_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"contract": contract, "baseline": os.path.relpath(BASELINE, ROOT),
                   "summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(os.path.relpath(out, ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
