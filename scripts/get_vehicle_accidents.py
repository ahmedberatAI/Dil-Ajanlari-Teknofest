#!/usr/bin/env python
"""E2: gercek arac-kazasi/devrilme klipleri (UCF RoadAccidents, HF mirror) indirir.

Acik-lisansli gercek FORKLIFT-devrilme videosu yok (arastirma ile dogrulandi);
en yakin gercek "devrilme/carpisma" kaniti UCF RoadAccidents (gercek CCTV goruntusu).
Bu betik N en kucuk RoadAccidents klibini data/e2_vehicle/RoadAccidents/ altina indirir
(mevcut data/eval/RoadAccidents ile cakisanlari atlar).

Kullanim:  N=6 python scripts/get_vehicle_accidents.py
"""
from __future__ import annotations

import json
import os
import urllib.request

REPO = "ertiaM/Anomaly_Detection_in_Surveillance_Videos"
API_BASE = f"https://huggingface.co/api/datasets/{REPO}"
DL_BASE = f"https://huggingface.co/datasets/{REPO}"
CAT = "RoadAccidents"
N = int(os.environ.get("N", "6"))
OUT = os.path.join("data", "e2_vehicle", CAT)
EXISTING = os.path.join("data", "eval", "RoadAccidents")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    have = set(os.listdir(EXISTING)) if os.path.isdir(EXISTING) else set()
    found = []
    for part in range(1, 5):
        api = f"{API_BASE}/tree/main/Anomaly-Videos-Part-{part}/{CAT}"
        try:
            data = json.load(urllib.request.urlopen(api, timeout=40))
        except Exception:
            continue
        for f in data:
            if isinstance(f, dict) and f.get("path", "").endswith(".mp4"):
                found.append((f.get("size", 0) or 0, f["path"]))
    found.sort()
    got = 0
    for size, path in found:
        name = os.path.basename(path)
        if name in have:
            continue
        out = os.path.join(OUT, name)
        if os.path.exists(out):
            continue
        url = f"{DL_BASE}/resolve/main/{path}"
        try:
            urllib.request.urlretrieve(url, out)
            print(f"indirildi: {name} ({size/1e6:.1f} MB)", flush=True)
            got += 1
        except Exception as e:
            print(f"hata {name}: {e}", flush=True)
        if got >= N:
            break
    print(f"DONE: {got} yeni klip -> {OUT}")


if __name__ == "__main__":
    main()
