#!/usr/bin/env python
"""K17: ``data/`` altindaki ATIL / OLU YUKU raporlar. SILME YAPMAZ.

Denetim bulgusu K17: depoda kullanilmayan buyuk yigin var --
  * ``data/nvidia/``            ~1 GB, docs/veri_kaynaklari.md'de "denendi,
                                KULLANILMADI" olarak belgeli. Ustelik icinde
                                hem ``*_partial.tar`` hem de acilmis
                                ``*_extract/`` var (ayni icerik iki kez).
  * ``data/scenario/_dl/*.zip`` ~782 MB, ZATEN acilmis (pos/ + neg/ mevcut).
                                Artik ``scripts/get_firesense.py`` ile Zenodo'dan
                                istenildigi an yeniden indirilebilir ve MD5'i
                                dogrulanabilir -> repoda tutmak zorunlu degil.

BU BETIK KARAR VERMEZ. Yalnizca oneri uretir; karar kullanicinindir.
  * VARSAYILAN : rapor (hicbir dosya degismez)
  * ``--archive``: secilen ogeleri ``data/_attic/`` altina TASIR. SILMEZ.
    Geri almak icin ``data/_attic/`` icinden geri tasimak yeterlidir.

Kullanim:
  python scripts/cleanup_suggest.py                       # rapor
  python scripts/cleanup_suggest.py --archive nvidia      # data/nvidia -> data/_attic/
  python scripts/cleanup_suggest.py --archive zips        # _dl/*.zip -> data/_attic/
  python scripts/cleanup_suggest.py --archive nvidia zips
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil

ATTIC = os.path.join("data", "_attic")


def dir_size(path: str) -> int:
    """Dizin (veya dosya) toplam boyutu, bayt."""
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    total = 0
    for dp, _dn, fns in os.walk(path):
        for fn in fns:
            try:
                total += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                continue
    return total


def count_files(path: str) -> int:
    """Dizin altindaki dosya sayisi."""
    if os.path.isfile(path):
        return 1
    return sum(len(fns) for _dp, _dn, fns in os.walk(path))


#: (anahtar, yollar, gerekce, geri-kazanim yolu)
def candidates() -> list[dict]:
    """Temizlik adaylarini (yol + gerekce + geri-alma yolu) uret."""
    out: list[dict] = []

    nvidia = os.path.join("data", "nvidia")
    if os.path.isdir(nvidia):
        out.append({
            "anahtar": "nvidia",
            "yollar": [nvidia],
            "gerekce": ("docs/veri_kaynaklari.md ve README.md bu veriyi 'denendi, KULLANILMIYOR' "
                        "olarak belgeliyor. Ayrica *_partial.tar arsivleri ile *_extract/ "
                        "dizinleri ayni icerigi IKI KEZ tutuyor."),
            "geri_kazanim": ("HF: nvidia/PhysicalAI-WorldModel-Synthetic-Warehouse-Operations-Scenes "
                             "(OpenMDW 1.1) — gerekirse yeniden indirilebilir."),
        })

    zips = sorted(glob.glob(os.path.join("data", "scenario", "_dl", "*.zip")))
    if zips:
        pos = glob.glob(os.path.join("data", "scenario", "_dl", "pos", "*"))
        neg = glob.glob(os.path.join("data", "scenario", "_dl", "neg", "*"))
        out.append({
            "anahtar": "zips",
            "yollar": zips,
            "gerekce": (f"Arsivler ZATEN acilmis (pos={len(pos)}, neg={len(neg)} klip mevcut). "
                        "Ayni icerigi ikinci kez tutuyorlar."),
            "geri_kazanim": ("python scripts/get_firesense.py  "
                             "(Zenodo 836749'dan yeniden indirir ve MD5 dogrular — "
                             "yerel kopyalarin Zenodo checksum'i ile BIREBIR AYNI oldugu dogrulandi)"),
        })

    for tar in sorted(glob.glob(os.path.join("data", "nvidia", "*_partial.tar"))):
        stem = os.path.basename(tar).replace("_partial.tar", "_extract")
        ext = os.path.join("data", "nvidia", stem)
        if os.path.isdir(ext):
            out.append({
                "anahtar": "nvidia_tar",
                "yollar": [tar],
                "gerekce": f"'{ext}' dizinine ZATEN acilmis; tar ayni icerigin ikinci kopyasi.",
                "geri_kazanim": "HF PhysicalAI deposundan yeniden indirilebilir.",
            })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archive", nargs="*", default=None, metavar="ANAHTAR",
                    help="Secilen adaylari data/_attic/ altina TASI (SILME yok). "
                         "Anahtar verilmezse tum adaylar.")
    args = ap.parse_args()

    cands = candidates()
    if not cands:
        print("temizlik adayi bulunamadi.", flush=True)
        return

    print(f"{'anahtar':<12}{'boyut':>11}{'dosya':>8}  yol", flush=True)
    print("-" * 78, flush=True)
    ust_yollar: list[str] = []           # ic-ice sayimi onlemek icin
    for c in cands:
        size = sum(dir_size(p) for p in c["yollar"])
        nfil = sum(count_files(p) for p in c["yollar"])
        yol = c["yollar"][0] if len(c["yollar"]) == 1 else f"{len(c['yollar'])} dosya"
        nested = all(
            any(os.path.normpath(p).startswith(os.path.normpath(u) + os.sep) for u in ust_yollar)
            for p in c["yollar"]
        ) if ust_yollar else False
        c["_boyut"] = size
        c["_ic_ice"] = nested
        if not nested:
            ust_yollar.extend(c["yollar"])
        print(f"{c['anahtar']:<12}{size/1e6:>9.1f} MB{nfil:>8}  {yol}"
              f"{'   [ustteki bir adayin ICINDE — toplama eklenmez]' if nested else ''}", flush=True)
        print(f"{'':<12}gerekce      : {c['gerekce']}", flush=True)
        print(f"{'':<12}geri kazanim : {c['geri_kazanim']}", flush=True)
        print("", flush=True)
    toplam = sum(c["_boyut"] for c in cands if not c["_ic_ice"])
    print("-" * 78, flush=True)
    print(f"TOPLAM ONERILEN (ic-ice sayim haric): {toplam/1e6:.1f} MB  ({toplam/1e9:.2f} GB)", flush=True)

    if args.archive is None:
        print("\n(RAPOR MODU: hicbir dosya degistirilmedi.)", flush=True)
        print("Tasimak icin:  python scripts/cleanup_suggest.py --archive nvidia zips", flush=True)
        print("NOT: --archive SILMEZ, yalnizca data/_attic/ altina tasir.", flush=True)
        return

    keys = set(args.archive) if args.archive else {c["anahtar"] for c in cands}
    os.makedirs(ATTIC, exist_ok=True)
    moved = 0
    freed = 0
    for c in cands:
        if c["anahtar"] not in keys:
            continue
        for p in c["yollar"]:
            if not os.path.exists(p):
                continue
            dst = os.path.join(ATTIC, os.path.basename(p.rstrip("/\\")))
            if os.path.exists(dst):
                print(f"atlandi (arsivde zaten var): {p}", flush=True)
                continue
            size = dir_size(p)
            try:
                shutil.move(p, dst)
                moved += 1
                freed += size
                print(f"tasindi (SILINMEDI): {p} -> {dst}  ({size/1e6:.1f} MB)", flush=True)
            except Exception as e:
                print(f"tasima hatasi {p}: {type(e).__name__}: {str(e)[:100]}", flush=True)
    print(f"\nBITTI: {moved} oge -> {ATTIC}  (~{freed/1e6:.1f} MB). "
          f"HICBIR SEY SILINMEDI; geri almak icin {ATTIC} icinden geri tasiyin.", flush=True)


if __name__ == "__main__":
    main()
