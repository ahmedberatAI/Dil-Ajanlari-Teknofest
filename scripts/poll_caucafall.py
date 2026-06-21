#!/usr/bin/env python
"""CAUCAFall (Mendeley 7w7fccy7ky) metadata'sini Mendeley kesintisi gecene kadar
periyodik yoklar. Basarili olunca metadata'yi kaydedip yapiyi ozetler ve cikar (exit 0).
Bu sayede dis sunucu kesintisi 'bekleme'sini arka plan gorevi ustlenir.

Ortam: MAX_TRIES (vars 18), GAP (sn, vars 600)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from collections import Counter

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
URL = "https://data.mendeley.com/public-api/datasets/7w7fccy7ky"
OUT = os.path.join("data", "scenario", "caucafall_meta.json")
MAX_TRIES = int(os.environ.get("MAX_TRIES", "18"))
GAP = int(os.environ.get("GAP", "600"))


def main() -> int:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for i in range(MAX_TRIES):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(URL, headers=H), timeout=60))
            files = d.get("files", [])
            if files:
                with open(OUT, "w", encoding="utf-8") as f:
                    json.dump(d, f)
                ext = Counter(x["filename"].lower().rsplit(".", 1)[-1] for x in files)
                print(f"BASARILI (deneme {i+1}) | dosya={len(files)} | uzantilar={dict(ext)}", flush=True)
                for x in files[:12]:
                    print(f"  - {x['filename']}  {round(x['size']/1e6,2)} MB", flush=True)
                return 0
            print(f"deneme {i+1}: bos liste", flush=True)
        except Exception as e:
            print(f"deneme {i+1}: hata {str(e)[:70]}", flush=True)
        if i < MAX_TRIES - 1:
            time.sleep(GAP)
    print(f"VAZGECILDI: {MAX_TRIES} deneme basarisiz (Mendeley hala kesintide)", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
