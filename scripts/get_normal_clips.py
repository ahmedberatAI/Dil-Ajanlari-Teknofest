#!/usr/bin/env python
"""UCF-Crime Normal test kliplerini indirir (yanlis-pozitif olcumu icin).

Kaynak: shahadalll/UCF-cime-binary-balanced (data/test/normal). Dev dosyalar atlanir.

K12 DUZELTMESI: eskiden aday listesi boyuta gore siralanip ``clips[:N]`` ile
EN KUCUK N klip aliniyordu -> yanlis-pozitif orani sistematik olarak
kucuk/kisa kliplerden olculuyordu (yanli). Artik sabit tohumlu DETERMINISTIK
RASTGELE orneklem. Eski davranis ``--smallest`` ile korunur.

Kullanim:
  N_NORMAL=8 python scripts/get_normal_clips.py --list
  N_NORMAL=8 python scripts/get_normal_clips.py
  python scripts/get_normal_clips.py --smallest --list   # eski (yanli) secim
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request

from _sampling import add_sampling_args, env_str, get_seed, print_selection, sample_clips

REPO = "shahadalll/UCF-cime-binary-balanced"
API = f"https://huggingface.co/api/datasets/{REPO}/tree/main/data/test/normal?limit=1000"
DL = f"https://huggingface.co/datasets/{REPO}/resolve/main"
N = int(os.environ.get("N_NORMAL", "8"))
MAX_MB = float(os.environ.get("MAX_MB", "20"))
OUTDIR = env_str("NORMAL_OUT", os.path.join("data", "eval", "Normal"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_sampling_args(ap)
    args = ap.parse_args()

    data = json.load(urllib.request.urlopen(API, timeout=60))
    # MAX_MB filtresi KORUNDU (disk/sure siniri); ama filtre SONRASI secim rastgele.
    pool = [
        ((f.get("size", 0) or 0), f["path"])
        for f in data
        if f.get("path", "").endswith(".mp4") and (f.get("size", 0) or 0) < MAX_MB * 1e6
    ]
    mode = "en-kucuk-N (ESKI/YANLI)" if args.smallest else f"rastgele (seed={args.seed or get_seed()})"
    print(f"# orneklem: {mode}  |  N_NORMAL={N}  MAX_MB={MAX_MB}  |  cikti={OUTDIR}", flush=True)
    picked = sample_clips(pool, N, "Normal", smallest=args.smallest, seed=args.seed)
    if args.list_only:
        print_selection("Normal", picked, len(pool))
        print("LISTE MODU: hicbir dosya indirilmedi.", flush=True)
        return

    os.makedirs(OUTDIR, exist_ok=True)
    total = 0
    for size, path in picked:
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
