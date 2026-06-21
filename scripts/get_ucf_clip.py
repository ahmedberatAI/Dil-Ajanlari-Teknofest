#!/usr/bin/env python
"""UCF-Crime (HF mirror) icinden bir kategorinin en kucuk klibini indirir.

Kullanim: python scripts/get_ucf_clip.py RoadAccidents
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

REPO = "ertiaM/Anomaly_Detection_in_Surveillance_Videos"
API_BASE = f"https://huggingface.co/api/datasets/{REPO}"   # listeleme (JSON)
DL_BASE = f"https://huggingface.co/datasets/{REPO}"        # indirme (resolve)


def main() -> None:
    cat = sys.argv[1] if len(sys.argv) > 1 else "RoadAccidents"
    found = []
    for part in range(1, 5):
        api = f"{API_BASE}/tree/main/Anomaly-Videos-Part-{part}/{cat}"
        try:
            data = json.load(urllib.request.urlopen(api, timeout=30))
        except Exception:
            continue
        for f in data:
            if isinstance(f, dict) and f.get("path", "").endswith(".mp4"):
                found.append((f.get("size", 0) or 0, f["path"]))
    if not found:
        print(f"'{cat}' icin klip bulunamadi")
        sys.exit(1)
    found.sort()
    size, path = found[0]
    url = f"{DL_BASE}/resolve/main/{path}"
    out = os.path.join("data", f"ucf_{cat.lower()}.mp4")
    print(f"en kucuk: {size/1e6:.1f} MB  {path}")
    urllib.request.urlretrieve(url, out)
    print(f"indirildi: {out}  ({os.path.getsize(out)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
