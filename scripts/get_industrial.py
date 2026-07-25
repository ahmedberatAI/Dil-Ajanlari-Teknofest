#!/usr/bin/env python
"""Eskisehir endustriyel isyeri guvenligi veri setinden (Mendeley xjmtb22pff, 1080p)
sinif basina N klip indirir. Dosya adi onek = sinif (0-7).

Kaynak: "Video Dataset for Safe and Unsafe Behaviours", 691 klip, 1920x1080 @24fps,
CC BY 4.0.  https://data.mendeley.com/datasets/xjmtb22pff
Sinif -> anlam eslemesi icin bkz. data/industrial/CLASSES.md (0-3 GUVENSIZ, 4-7 GUVENLI).

K12 DUZELTMESI: eskiden ``lst.sort(); lst[:N]`` ile sinif basina EN KUCUK N klip
aliniyordu -> en kisa (dolayisiyla en az olay iceren) klipler asiri temsil.
Artik sabit tohumlu DETERMINISTIK RASTGELE orneklem. Eski davranis ``--smallest``.

K14 NOTU: bizde su an sinif basina 1 klip var ve HEPSI "Normal" etiketlenmis;
oysa class0-3 GUVENSIZ davranistir. Domain-ici pozitif uretmek icin
``N_PER_CLASS`` buyutup indirin, sonra ``scripts/build_defense_eval.py`` calistirin.

Kullanim:
  N_PER_CLASS=1 python scripts/get_industrial.py --list
  N_PER_CLASS=5 python scripts/get_industrial.py
  N_PER_CLASS=5 CLASSES=0,1,2,3 python scripts/get_industrial.py   # yalnizca guvensiz
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from collections import defaultdict

from _sampling import add_sampling_args, env_str, get_seed, print_selection, sample_clips

H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
META = "https://data.mendeley.com/public-api/datasets/xjmtb22pff"
N = int(os.environ.get("N_PER_CLASS", "1"))
OUT = env_str("INDUSTRIAL_OUT", os.path.join("data", "industrial"))
#: hangi siniflar indirilsin (bos -> hepsi). Or. CLASSES=0,1,2,3
WANT = [c.strip() for c in os.environ.get("CLASSES", "").split(",") if c.strip()]
#: klip basina ust boyut siniri (MB); 0 -> sinir yok. 1080p klipler 10-60 MB olabilir.
MAX_MB = float(os.environ.get("MAX_MB", "0"))

#: Sinif -> (ad, guvenlik etiketi). Kaynak: Data in Brief makalesi (PMC11367630),
#: klip sayilari Mendeley API ile BIREBIR dogrulandi (210/108/142/56/75/38/32/30).
CLASS_MAP: dict[str, tuple[str, str]] = {
    "0": ("Safe Walkway Violation", "unsafe"),
    "1": ("Unauthorized Intervention", "unsafe"),
    "2": ("Opened Panel Cover", "unsafe"),
    "3": ("Carrying Overload with Forklift", "unsafe"),
    "4": ("Safe Walkway", "safe"),
    "5": ("Authorized Intervention", "safe"),
    "6": ("Closed Panel Cover", "safe"),
    "7": ("Safe Carrying", "safe"),
}


def fetch_meta() -> dict:
    """Mendeley public-api metadata'sini cek."""
    return json.load(urllib.request.urlopen(urllib.request.Request(META, headers=H), timeout=60))


def group_by_class(meta: dict) -> dict[str, list[tuple[int, str]]]:
    """Dosyalari sinif onekine gore grupla -> ``{sinif: [(boyut, dosya_adi), ...]}``."""
    by_class: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for f in meta["files"]:
        cls = f["filename"].split("_")[0]
        size = int(f.get("size") or 0)
        if MAX_MB and size > MAX_MB * 1e6:
            continue
        by_class[cls].append((size, f["filename"]))
    return by_class


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_sampling_args(ap)
    args = ap.parse_args()

    try:
        meta = fetch_meta()
    except Exception as e:
        print(f"metadata cekilemedi (ag yok?): {e}", flush=True)
        return
    url_of = {f["filename"]: f["content_details"]["download_url"] for f in meta["files"]}
    by_class = group_by_class(meta)

    mode = "en-kucuk-N (ESKI/YANLI)" if args.smallest else f"rastgele (seed={args.seed or get_seed()})"
    print(f"# orneklem: {mode}  |  N_PER_CLASS={N}  |  cikti={OUT}", flush=True)

    total = 0
    for cls, lst in sorted(by_class.items()):
        if WANT and cls not in WANT:
            continue
        name, safety = CLASS_MAP.get(cls, ("?", "?"))
        picked = sample_clips(lst, N, f"industrial{cls}", smallest=args.smallest, seed=args.seed)
        if args.list_only:
            print_selection(f"class{cls} {name} [{safety}]", picked, len(lst))
            continue
        outdir = os.path.join(OUT, f"class{cls}")
        os.makedirs(outdir, exist_ok=True)
        for size, fname in picked:
            out = os.path.join(outdir, fname)
            if os.path.exists(out) and os.path.getsize(out) > 0:
                print(f"zaten var: class{cls}/{fname}", flush=True)
                continue
            try:
                req = urllib.request.Request(url_of[fname], headers=H)
                with urllib.request.urlopen(req, timeout=300) as r, open(out, "wb") as w:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        w.write(chunk)
                total += 1
                print(f"indi: class{cls}/{fname} ({size/1e6:.1f} MB) [{safety}]", flush=True)
            except Exception as e:
                print(f"hata class{cls}/{fname}: {e}", flush=True)
    if args.list_only:
        print("LISTE MODU: hicbir dosya indirilmedi.", flush=True)
    else:
        print(f"BITTI: {total} klip -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
