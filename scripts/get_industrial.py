#!/usr/bin/env python
"""Eskisehir endustriyel isyeri guvenligi veri setinden (Mendeley xjmtb22pff, 1080p)
sinif basina N en kucuk klibi indirir. Dosya adi onek = sinif (0-7).

Kullanim:  N_PER_CLASS=1 python scripts/get_industrial.py
"""
from __future__ import annotations

import json
import os
import urllib.request
from collections import defaultdict

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
META = "https://data.mendeley.com/public-api/datasets/xjmtb22pff"
N = int(os.environ.get("N_PER_CLASS", "1"))
OUT = os.path.join("data", "industrial")


def main() -> None:
    d = json.load(urllib.request.urlopen(urllib.request.Request(META, headers=H), timeout=60))
    by_class = defaultdict(list)
    for f in d["files"]:
        cls = f["filename"].split("_")[0]
        by_class[cls].append((f["size"], f["filename"], f["content_details"]["download_url"]))

    total = 0
    for cls, lst in sorted(by_class.items()):
        lst.sort()
        outdir = os.path.join(OUT, f"class{cls}")
        os.makedirs(outdir, exist_ok=True)
        for size, name, url in lst[:N]:
            out = os.path.join(outdir, name)
            if os.path.exists(out) and os.path.getsize(out) > 0:
                print(f"zaten var: class{cls}/{name}", flush=True)
                continue
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=180) as r, open(out, "wb") as w:
                    w.write(r.read())
                total += 1
                print(f"indi: class{cls}/{name} ({size/1e6:.1f} MB)", flush=True)
            except Exception as e:
                print(f"hata class{cls}/{name}: {e}", flush=True)
    print(f"BITTI: {total} klip -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
