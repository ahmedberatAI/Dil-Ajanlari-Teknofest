#!/usr/bin/env python
"""UCF-Crime (HF mirror) icinden dengeli bir degerlendirme seti indirir.

Her kategoriden en kucuk N klibi data/eval/<kategori>/ altina indirir.
Kullanim:  N_PER_CAT=3 python scripts/build_eval_set.py
"""
from __future__ import annotations

import json
import os
import urllib.request

REPO = "ertiaM/Anomaly_Detection_in_Surveillance_Videos"
API = f"https://huggingface.co/api/datasets/{REPO}"
DL = f"https://huggingface.co/datasets/{REPO}"

# kategori -> hangi Part klasorunde (onceden listelendi)
CATEGORY_PART = {
    "Abuse": 1, "Arrest": 1, "Arson": 1, "Assault": 1,
    "Burglary": 2, "Explosion": 2, "Fighting": 2,
    "RoadAccidents": 3, "Robbery": 3, "Shooting": 3,
    "Shoplifting": 4, "Stealing": 4, "Vandalism": 4,
}

# degerlendirme icin secilen kategoriler (senaryoya yakin + cesitlilik)
EVAL_CATEGORIES = [
    "RoadAccidents", "Explosion", "Fighting", "Assault",
    "Abuse", "Burglary", "Shooting", "Vandalism",
]

N = int(os.environ.get("N_PER_CAT", "3"))
OUTROOT = os.path.join("data", "eval")


def list_clips(cat: str):
    part = CATEGORY_PART[cat]
    url = f"{API}/tree/main/Anomaly-Videos-Part-{part}/{cat}?limit=1000"
    data = json.load(urllib.request.urlopen(url, timeout=60))
    clips = [(f.get("size", 0) or 0, f["path"]) for f in data if f.get("path", "").endswith(".mp4")]
    clips.sort()
    return clips


def main() -> None:
    total = 0
    for cat in EVAL_CATEGORIES:
        try:
            clips = list_clips(cat)
        except Exception as e:
            print(f"[{cat}] listeleme hatasi: {e}", flush=True)
            continue
        outdir = os.path.join(OUTROOT, cat)
        os.makedirs(outdir, exist_ok=True)
        for size, path in clips[:N]:
            name = os.path.basename(path)
            out = os.path.join(outdir, name)
            if os.path.exists(out) and os.path.getsize(out) > 0:
                print(f"[{cat}] zaten var: {name}", flush=True)
                continue
            url = f"{DL}/resolve/main/{path}"
            try:
                urllib.request.urlretrieve(url, out)
                total += 1
                print(f"[{cat}] indi: {name} ({size/1e6:.1f} MB)", flush=True)
            except Exception as e:
                print(f"[{cat}] indirme hatasi {name}: {e}", flush=True)
    print(f"BITTI: {total} klip indirildi -> {OUTROOT}", flush=True)


if __name__ == "__main__":
    main()
