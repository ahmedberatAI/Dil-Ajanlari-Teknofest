#!/usr/bin/env python
"""G6: Buyuk/dengeli UCF-Crime degerlendirme seti (HF mirror) indirir.

Istatistiksel olarak zayif kucuk seti (8-30 klip) buyutmek icin: kategori basina
N klibi data/eval_big/<Kategori>/ altina indirir. Boylece daha buyuk n +
daha dar guven araligi + kosu-arasi varyans olcumu mumkun olur.

K12 DUZELTMESI: eskiden ``found.sort()`` ile aday listesi DOSYA BOYUTUNA gore
siralanip en kucukten baslayarak N tane aliniyordu -> sistematik orneklem
yanliligi (kisa/dusuk-bit-hizli klipler asiri temsil). Artik sabit tohumlu
DETERMINISTIK RASTGELE orneklem (bkz. scripts/_sampling.py). Eski davranis
``--smallest`` bayragiyla korunur.

Kullanim:
  N_ANOM=6 N_NORM=12 python scripts/get_ucf_many.py --list
  N_ANOM=6 N_NORM=12 python scripts/get_ucf_many.py
  python scripts/get_ucf_many.py --smallest --list      # eski (yanli) secim
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request

from _sampling import add_sampling_args, env_str, get_seed, print_selection, sample_clips

REPO = "ertiaM/Anomaly_Detection_in_Surveillance_Videos"
API_BASE = f"https://huggingface.co/api/datasets/{REPO}"
DL_BASE = f"https://huggingface.co/datasets/{REPO}"

# Normal klipler AYRI bir depoda. Eski surumde "Testing_Normal_Videos_Anomaly" /
# "Training-Normal-Videos-Part-*" dallari denenip SESSIZCE bos donuyordu: ertiaM
# aynasinin kokunde YALNIZCA Anomaly-Videos-Part-1..4 var (API ile dogrulandi),
# yani Normal kategorisi hicbir zaman inmiyordu. data/eval_big/Normal aslinda
# get_normal_clips.py (shahadalll aynasi) ile dolduruldu -> asagida ayni kaynak.
NORM_REPO = "shahadalll/UCF-cime-binary-balanced"
NORM_API = f"https://huggingface.co/api/datasets/{NORM_REPO}/tree/main/data/test/normal?limit=1000"
NORM_DL = f"https://huggingface.co/datasets/{NORM_REPO}"

OUT_ROOT = env_str("EVAL_BIG_OUT", os.path.join("data", "eval_big"))

ANOM = ["RoadAccidents", "Explosion", "Fighting", "Assault", "Burglary", "Shooting", "Vandalism", "Abuse"]
N_ANOM = int(os.environ.get("N_ANOM", "6"))
N_NORM = int(os.environ.get("N_NORM", "12"))


def list_category(cat: str) -> list[tuple[int, str]]:
    """Kategorinin HF agac dallarini tara -> ``(boyut, yol)`` aday listesi."""
    found: list[tuple[int, str]] = []
    if cat == "Normal":
        try:
            data = json.load(urllib.request.urlopen(NORM_API, timeout=40))
        except Exception as e:
            print(f"  [Normal] listeleme hatasi: {e}", flush=True)
            return found
        return [(f.get("size", 0) or 0, f["path"]) for f in data if f.get("path", "").endswith(".mp4")]
    for t in [f"Anomaly-Videos-Part-{p}/{cat}" for p in range(1, 5)]:
        try:
            data = json.load(urllib.request.urlopen(f"{API_BASE}/tree/main/{t}?limit=1000", timeout=40))
        except Exception:
            continue
        for f in data:
            if isinstance(f, dict) and f.get("path", "").endswith(".mp4"):
                found.append((f.get("size", 0) or 0, f["path"]))
    return found


def fetch(cat: str, n: int, args: argparse.Namespace) -> int:
    """Kategoriden n klip sec ve (liste modunda degilse) indir."""
    pool = list_category(cat)
    picked = sample_clips(pool, n, cat, smallest=args.smallest, seed=args.seed)
    if args.list_only:
        print_selection(cat, picked, len(pool))
        return len(picked)
    out_dir = os.path.join(OUT_ROOT, cat)
    os.makedirs(out_dir, exist_ok=True)
    base = NORM_DL if cat == "Normal" else DL_BASE
    got = 0
    for size, path in picked:
        name = os.path.basename(path)
        out = os.path.join(out_dir, name)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            got += 1
            continue
        try:
            urllib.request.urlretrieve(f"{base}/resolve/main/{path}", out)
            print(f"  {cat}: {name} ({size/1e6:.1f} MB)", flush=True)
            got += 1
        except Exception as e:
            print(f"  hata {name}: {e}", flush=True)
    return got


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_sampling_args(ap)
    args = ap.parse_args()
    mode = "en-kucuk-N (ESKI/YANLI)" if args.smallest else f"rastgele (seed={args.seed or get_seed()})"
    print(f"# orneklem: {mode}  |  N_ANOM={N_ANOM} N_NORM={N_NORM}  |  cikti={OUT_ROOT}", flush=True)
    total = 0
    for cat in ANOM:
        total += fetch(cat, N_ANOM, args)
    total += fetch("Normal", N_NORM, args)
    print(f"DONE: {total} klip -> {OUT_ROOT}" if not args.list_only
          else f"LISTE MODU: {total} klip secildi, indirme YOK.")


if __name__ == "__main__":
    main()
