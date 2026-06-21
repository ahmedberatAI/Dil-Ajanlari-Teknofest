#!/usr/bin/env python
"""UCF-Crime Normal test kliplerini indirir (yanlis-pozitif olcumu icin).

Kaynak: shahadalll/UCF-cime-binary-balanced (data/test/normal). Dev dosyalar atlanir.
Kullanim:  N_NORMAL=8 python scripts/get_normal_clips.py
"""
from __future__ import annotations

import json
import os
import urllib.request

REPO = "shahadalll/UCF-cime-binary-balanced"
API = f"https://huggingface.co/api/datasets/{REPO}/tree/main/data/test/normal?limit=1000"
DL = f"https://huggingface.co/datasets/{REPO}/resolve/main"
N = int(os.environ.get("N_NORMAL", "8"))
MAX_MB = float(os.environ.get("MAX_MB", "20"))
OUTDIR = os.path.join("data", "eval", "Normal")


def main() -> None:
    data = json.load(urllib.request.urlopen(API, timeout=60))
    clips = sorted(
        (f.get("size", 0) or 0, f["path"])
        for f in data
        if f.get("path", "").endswith(".mp4") and (f.get("size", 0) or 0) < MAX_MB * 1e6
    )
    os.makedirs(OUTDIR, exist_ok=True)
    total = 0
    for size, path in clips[:N]:
        out = os.path.join(OUTDIR, os.path.basename(path))
        if os.path.exists(out) and os.path.getsize(out) > 0:
            print(f"zaten var: {os.path.basename(path)}", flush=True)
            continue
        try:
            urllib.request.urlretrieve(f"{DL}/{path}", out)
            total += 1
            print(f"indi: {os.path.basename(path)} ({size/1e6:.1f} MB)", flush=True)
        except Exception as e:
            print(f"hata {path}: {e}", flush=True)
    print(f"BITTI: {total} normal klip -> {OUTDIR}", flush=True)


if __name__ == "__main__":
    main()
