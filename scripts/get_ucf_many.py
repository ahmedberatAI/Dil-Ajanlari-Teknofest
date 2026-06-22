#!/usr/bin/env python
"""G6: Buyuk/dengeli UCF-Crime degerlendirme seti (HF mirror) indirir.

Istatistiksel olarak zayif kucuk seti (8-30 klip) buyutmek icin: kategori basina
N en kucuk klibi data/eval_big/<Kategori>/ altina indirir. Boylece daha buyuk n +
daha dar guven araligi + koşu-arasi varyans olcumu mumkun olur.

Kullanim:  N_ANOM=6 N_NORM=12 python scripts/get_ucf_many.py
"""
from __future__ import annotations

import json
import os
import urllib.request

REPO = "ertiaM/Anomaly_Detection_in_Surveillance_Videos"
API_BASE = f"https://huggingface.co/api/datasets/{REPO}"
DL_BASE = f"https://huggingface.co/datasets/{REPO}"
OUT_ROOT = os.path.join("data", "eval_big")

ANOM = ["RoadAccidents", "Explosion", "Fighting", "Assault", "Burglary", "Shooting", "Vandalism", "Abuse"]
N_ANOM = int(os.environ.get("N_ANOM", "6"))
N_NORM = int(os.environ.get("N_NORM", "12"))


def list_category(cat: str):
    found = []
    # anomaliler Anomaly-Videos-Part-{1..4}; normaller Testing/Training-Normal-Videos-* altinda
    trees = [f"Anomaly-Videos-Part-{p}/{cat}" for p in range(1, 5)] if cat != "Normal" else [
        "Testing_Normal_Videos_Anomaly", "Training-Normal-Videos-Part-1", "Training-Normal-Videos-Part-2",
    ]
    for t in trees:
        try:
            data = json.load(urllib.request.urlopen(f"{API_BASE}/tree/main/{t}", timeout=40))
        except Exception:
            continue
        for f in data:
            if isinstance(f, dict) and f.get("path", "").endswith(".mp4"):
                found.append((f.get("size", 0) or 0, f["path"]))
    found.sort()
    return found


def fetch(cat: str, n: int):
    out_dir = os.path.join(OUT_ROOT, cat)
    os.makedirs(out_dir, exist_ok=True)
    got = 0
    for size, path in list_category(cat):
        name = os.path.basename(path)
        out = os.path.join(out_dir, name)
        if os.path.exists(out):
            got += 1
            continue
        try:
            urllib.request.urlretrieve(f"{DL_BASE}/resolve/main/{path}", out)
            print(f"  {cat}: {name} ({size/1e6:.1f} MB)", flush=True)
            got += 1
        except Exception as e:
            print(f"  hata {name}: {e}", flush=True)
        if got >= n:
            break
    return got


def main() -> None:
    total = 0
    for cat in ANOM:
        total += fetch(cat, N_ANOM)
    total += fetch("Normal", N_NORM)
    print(f"DONE: {total} klip -> {OUT_ROOT}")


if __name__ == "__main__":
    main()
