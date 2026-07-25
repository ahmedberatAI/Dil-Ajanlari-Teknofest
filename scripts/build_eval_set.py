#!/usr/bin/env python
"""UCF-Crime (HF mirror) icinden dengeli bir degerlendirme seti indirir.

K12 DUZELTMESI: eskiden her kategoriden "EN KUCUK N" klip aliniyordu
(``clips.sort(); clips[:N]``) -> sistematik orneklem yanliligi. Artik sabit
tohumlu DETERMINISTIK RASTGELE orneklem yapilir (bkz. scripts/_sampling.py).
Eski davranis ``--smallest`` ile hala erisilebilir.

K9 DUZELTMESI: data/eval, data/eval_big'in %100 alt kumesiydi (31/31 ayni MD5)
-> "bagimsiz buyuk-n dogrulama" iddiasi gecersizdi. Artik varsayilan olarak
``data/eval_big`` altinda ZATEN BULUNAN dosya adlari aday havuzundan DISLANIR
(``--allow-overlap`` ile kapatilabilir). Boylece yeni kurulan set eval_big'den
AYRIK (disjoint) olur.

Kullanim:
  N_PER_CAT=3 python scripts/build_eval_set.py --list      # indirmeden secimi gor
  N_PER_CAT=3 python scripts/build_eval_set.py             # indir
  EVAL_SEED=7 N_PER_CAT=3 python scripts/build_eval_set.py --list
  python scripts/build_eval_set.py --smallest              # eski (yanli) secim
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request

from _sampling import add_sampling_args, env_str, get_seed, print_selection, sample_clips

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
OUTROOT = env_str("EVAL_OUT", os.path.join("data", "eval"))
#: K9: bu dizinlerde ZATEN olan klip adlari aday havuzundan cikarilir (sizinti onleme)
EXCLUDE_ROOTS = [p for p in env_str("EXCLUDE_ROOTS", os.path.join("data", "eval_big")).split(os.pathsep) if p]


def existing_names(roots: list[str]) -> set[str]:
    """Verilen koklerin altindaki tum .mp4 dosya adlarini (basename) topla."""
    seen: set[str] = set()
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                if fn.lower().endswith(".mp4"):
                    seen.add(fn)
    return seen


def list_clips(cat: str) -> list[tuple[int, str]]:
    """Kategorinin HF agac listesini cek -> ``(boyut, yol)`` adaylari."""
    part = CATEGORY_PART[cat]
    url = f"{API}/tree/main/Anomaly-Videos-Part-{part}/{cat}?limit=1000"
    data = json.load(urllib.request.urlopen(url, timeout=60))
    return [(f.get("size", 0) or 0, f["path"]) for f in data if f.get("path", "").endswith(".mp4")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_sampling_args(ap)
    ap.add_argument(
        "--allow-overlap",
        action="store_true",
        help="K9 korumasini kapat: eval_big ile ayni klipler de secilebilsin.",
    )
    args = ap.parse_args()

    blocked = set() if args.allow_overlap else existing_names(EXCLUDE_ROOTS)
    mode = "en-kucuk-N (ESKI/YANLI)" if args.smallest else f"rastgele (seed={args.seed or get_seed()})"
    print(f"# orneklem: {mode}  |  N_PER_CAT={N}  |  cikti={OUTROOT}", flush=True)
    if blocked:
        print(f"# K9 ayriklik: {len(blocked)} klip adi dislandi ({', '.join(EXCLUDE_ROOTS)})", flush=True)

    total = 0
    for cat in EVAL_CATEGORIES:
        try:
            clips = list_clips(cat)
        except Exception as e:
            print(f"[{cat}] listeleme hatasi: {e}", flush=True)
            continue
        pool = [c for c in clips if os.path.basename(c[1]) not in blocked]
        picked = sample_clips(pool, N, cat, smallest=args.smallest, seed=args.seed)
        if args.list_only:
            print_selection(cat, picked, len(pool))
            continue
        outdir = os.path.join(OUTROOT, cat)
        os.makedirs(outdir, exist_ok=True)
        for size, path in picked:
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
    if args.list_only:
        print("LISTE MODU: hicbir dosya indirilmedi.", flush=True)
    else:
        print(f"BITTI: {total} klip indirildi -> {OUTROOT}", flush=True)


if __name__ == "__main__":
    main()
