#!/usr/bin/env python
"""GMDCSA-24 gercek dusme videolarini indirir (GitHub raw, auth yok, CC BY 4.0).
Cikti: data/falls_real/Fall/*.mp4 (gercek dusme) + data/falls_real/Normal/*.mp4 (ADL)."""
from __future__ import annotations

import os
import urllib.parse
import urllib.request

H = {"User-Agent": "Mozilla/5.0"}
BASE = ("https://raw.githubusercontent.com/ekramalam/"
        "GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos/master")
OUT = os.path.join("data", "falls_real")

JOBS = []
for subj in ["Subject 1", "Subject 2", "Subject 3"]:
    sj = subj.replace(" ", "")
    for n in ["01", "02", "03"]:
        JOBS.append((f"{subj}/Fall/{n}.mp4", f"Fall/{sj}_fall{n}.mp4"))
    for n in ["01", "02"]:
        JOBS.append((f"{subj}/ADL/{n}.mp4", f"Normal/{sj}_adl{n}.mp4"))


def main() -> None:
    n_ok = 0
    for src, dst in JOBS:
        url = BASE + "/" + urllib.parse.quote(src)
        out = os.path.join(OUT, dst)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            print("zaten var:", dst); n_ok += 1; continue
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=90) as r, open(out, "wb") as w:
                w.write(r.read())
            print("indi:", dst, round(os.path.getsize(out) / 1e6, 1), "MB"); n_ok += 1
        except Exception as e:
            print("hata:", src, str(e)[:60])
    print(f"BITTI: {n_ok} klip -> {OUT}")


if __name__ == "__main__":
    main()
