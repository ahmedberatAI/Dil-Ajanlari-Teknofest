#!/usr/bin/env python
"""Görünür bakım/müdahale eylemi kapısını eşlenmiş İSG çiftinde ölçer."""
from __future__ import annotations

import concurrent.futures
import datetime
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dilajan.gozlem import GOZLEM_SISTEM
from dilajan.llm_client import VLMClient
from dilajan.video import servis_videosu


ANOM = ROOT / "data/eval_defense/Anomali/Unauthorized_Intervention"
NORM = ROOT / "data/eval_defense/Normal/Authorized_Intervention"
HARD = ROOT / "data/_mislabeled_unsafe/eval_big_0_tr128.mp4"
BASE = ROOT / "benchmark/results/d43_gozlem_20260825_075248.json"
CHOICES = ["BAKIM_MUDAHALE", "RUTIN_KULLANIM", "KISI_YOK", "GORUNMUYOR"]
QUESTION = (
    "Makine basindaki kisinin gorunur faaliyeti hangisi? "
    "BAKIM_MUDAHALE = koruyucu kapak acma, makinenin icine el/alet uzatma, "
    "parca sokme-takma veya ariza/bakim mudahalesi. "
    "RUTIN_KULLANIM = sandalyede oturma, kumanda panelini kullanma, normal "
    "uretim veya yalnizca yaninda durma. Yalnizca BAKIM_MUDAHALE, "
    "RUTIN_KULLANIM, KISI_YOK veya GORUNMUYOR yaz."
)


def _mcc(tp: int, fp: int, fn: int, tn: int) -> float:
    den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return (tp * tn - fp * fn) / den if den else 0.0


def _baseline() -> dict[str, dict]:
    data = json.loads(BASE.read_text(encoding="utf-8"))
    out = {}
    for row in data["satirlar"]:
        if row.get("cift") != "Unauthorized_Intervention":
            continue
        out[row["klip"]] = row["slotlar"]
    return out


def _one(item: tuple[Path, bool, bool]) -> dict:
    path, unsafe, hard = item
    client = VLMClient().gorev("algi")
    video = servis_videosu(str(path), fps=8, sabit_bit="800k")
    session = client.video_oturumu(video, system=GOZLEM_SISTEM)
    answer = session.sor(
        QUESTION, guided_choice=CHOICES, temperature=0.0,
        max_tokens=16, hatirla=False,
    )
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "clip": path.name,
        "unsafe": unsafe,
        "hard_negative": hard,
        "answer": (answer or "HATA").strip().upper(),
        "error": session.hata,
    }


def main() -> None:
    items = ([(p, True, False) for p in sorted(ANOM.glob("*.mp4"))]
             + [(p, False, False) for p in sorted(NORM.glob("*.mp4"))]
             + [(HARD, False, True)])
    workers = max(1, int(os.environ.get("EVAL_ISCI", "4")))
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(_one, items):
            rows.append(row)
            print(f"{row['answer']:<16} {row['path']}", flush=True)

    base = _baseline()
    tp = fp = fn = tn = 0
    for row in rows:
        if row["hard_negative"]:
            continue
        slots = base[row["clip"]]
        old = (int(slots.get("makine_basinda_kisi", 0)) >= 1
               and slots.get("makine_basinda_yelek") == "YOK")
        pred = old and row["answer"] == "BAKIM_MUDAHALE"
        if row["unsafe"]:
            tp += int(pred); fn += int(not pred)
        else:
            fp += int(pred); tn += int(not pred)

    hard = next(r for r in rows if r["hard_negative"])
    counts = {c: sum(r["answer"] == c for r in rows if not r["hard_negative"])
              for c in CHOICES}
    result = {
        "question": QUESTION,
        "choices": CHOICES,
        "matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                   "mcc": round(_mcc(tp, fp, fn, tn), 6)},
        "answer_counts": counts,
        "hard_negative_answer": hard["answer"],
        "rows": rows,
    }
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ROOT / f"benchmark/results/mudahale_kapisi_{stamp}.json"
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["matrix"], ensure_ascii=False), flush=True)
    print(f"hard_negative={hard['answer']} counts={counts}", flush=True)
    print(f"Kaydedildi: {dest.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
