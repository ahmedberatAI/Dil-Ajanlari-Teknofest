#!/usr/bin/env python
"""v12e: yeni ışık/bulut -> ilişkili insan tepkisi yangın şüphesi probu."""
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
from benchmark.stats_utils import rate_from_bools  # noqa: E402
from dilajan.isg_kanit import ATOMIK_SISTEM  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_194722.json")
HAZARD_ANN = os.path.join(ROOT, "data", "isafety_bench", "annotations",
                          "annotations_hazard.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")

GORSEL_SECENEKLER = (
    "YENI_ISIK_BULUT", "SUREKLI_ALEV_DUMAN", "BUHAR_TOZ_PARLAMA",
    "DEGISIM_YOK", "GORUNMUYOR",
)
TEPKI_SECENEKLER = (
    "KAYNAKLA_BAGLANTILI_TEPKI", "RUTIN_HAREKET", "ZAMAN_ILISKISI_YOK",
    "KISI_YOK", "GORUNMUYOR",
)

GORSEL_SORU = (
    "Videoyu ilk kareden son kareye kronolojik karşılaştır. Önce yokken sonradan "
    "beliren ve yerel olarak büyüyen/yayılan alev, parlak ışık veya sınırları yumuşak "
    "bulutumsu bulanıklık var mı? Kamera pozlaması, far/kaynak parlaması, sabit ışık, "
    "rutin buhar ve toz yangın belirtisi değildir. Yalnız YENI_ISIK_BULUT, "
    "SUREKLI_ALEV_DUMAN, BUHAR_TOZ_PARLAMA, DEGISIM_YOK veya GORUNMUYOR yaz."
)
TEPKI_SORU = (
    "Videoyu kronolojik karşılaştır. Yeni ışık/alev/bulutumsu oluşumdan SONRA insanlar "
    "aynı kaynağa bakıp yöneliyor, kaynaktan uzaklaşıyor/kaçıyor ya da ona hortum/"
    "söndürücüyle müdahale ediyor mu? Rutin yürüme, çalışma, önceden başlamış hareket "
    "ve yalnız eşzamanlı bulunma nedensel tepki değildir. Yalnız "
    "KAYNAKLA_BAGLANTILI_TEPKI, RUTIN_HAREKET, ZAMAN_ILISKISI_YOK, KISI_YOK veya "
    "GORUNMUYOR yaz."
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
    with open(HAZARD_ANN, encoding="utf-8") as f:
        anns = {x["video_name"]: x for x in json.load(f)}
    out = []
    for row in baseline["rows"]:
        name = os.path.basename(row["path"])
        fire = bool(row["is_anomaly"] and
                    "fire incident" in anns.get(name, {}).get("gt_actions", []))
        normal = not row["is_anomaly"]
        if not (fire or normal):
            continue
        path = os.path.join(ROOT, row["path"])
        out.append({
            "path": path,
            "rel_path": row["path"],
            "positive": fire,
            "baseline_alarm": bool(row["n_events"]),
            "sha256": _sha256(path),
        })
    return out


def _run(item: dict) -> dict:
    start = time.perf_counter()
    errors: dict[str, str] = {}
    answers: dict[str, str] = {}
    frames, info = extract_timestamped_frames(item["path"])
    root = VLMClient()
    try:
        answers["yeni_belirti"] = root.gorev("algi").analyze_frames(
            frames, GORSEL_SORU, temperature=0.0, max_tokens=12,
            system=ATOMIK_SISTEM, guided_choice=GORSEL_SECENEKLER)
    except Exception as ex:
        errors["yeni_belirti"] = f"{type(ex).__name__}: {ex}"
    # İkinci rol yalnız ilk, kapalı-uzay ölçümü destek verdiyse çağrılır.
    if answers.get("yeni_belirti", "").strip().upper() == "YENI_ISIK_BULUT":
        try:
            answers["insan_tepkisi"] = root.gorev("olay").analyze_frames(
                frames, TEPKI_SORU, temperature=0.0, max_tokens=12,
                system=ATOMIK_SISTEM, guided_choice=TEPKI_SECENEKLER)
        except Exception as ex:
            errors["insan_tepkisi"] = f"{type(ex).__name__}: {ex}"
    supported = (
        not errors
        and answers.get("yeni_belirti", "").strip().upper() == "YENI_ISIK_BULUT"
        and answers.get("insan_tepkisi", "").strip().upper()
        == "KAYNAKLA_BAGLANTILI_TEPKI"
    )
    return {
        **{k: v for k, v in item.items() if k != "path"},
        "duration_s": info.duration,
        "supported": supported,
        "answers": answers,
        "errors": errors,
        "latency_s": round(time.perf_counter() - start, 2),
    }


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    items = _items()
    positives = sum(x["positive"] for x in items)
    negatives = len(items) - positives
    if (positives, negatives) != (13, 50):
        raise RuntimeError(
            f"Ön kayıt örneklemi değişti: positive={positives}, negative={negatives}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    pos = [x for x in rows if x["positive"]]
    neg = [x for x in rows if not x["positive"]]
    recovered = sum(x["supported"] and not x["baseline_alarm"] for x in pos)
    normal_triggers = sum(x["supported"] for x in neg)
    new_fp = sum(x["supported"] and not x["baseline_alarm"] for x in neg)
    errors = sum(bool(x["errors"]) for x in rows)
    summary = {
        "n": len(rows), "positive": len(pos), "negative": len(neg),
        "fire_suspicion_tp": sum(x["supported"] for x in pos),
        "fire_suspicion_recall": rate_from_bools([x["supported"] for x in pos]),
        "recovered_baseline_fire_misses": recovered,
        "normal_triggers": normal_triggers,
        "normal_trigger_rate": rate_from_bools([x["supported"] for x in neg]),
        "new_fp_on_baseline_tn": new_fp,
        "errors": errors,
        "latency_median": statistics.median(x["latency_s"] for x in rows),
        "accepted": recovered >= 1 and new_fp == 0 and normal_triggers <= 2
                    and errors == 0,
    }
    os.makedirs(RESULTS, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"yangin_zamansal_suphe_v12e_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"contract": contract, "baseline": os.path.relpath(BASELINE, ROOT),
                   "summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(os.path.relpath(out, ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
