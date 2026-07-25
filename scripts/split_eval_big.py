#!/usr/bin/env python
"""K9: ``data/eval_big``'i BIRBIRINDEN AYRIK iki alt sete boler.

SORUN (denetim bulgusu K9): ``data/eval``, ``data/eval_big``'in %100 alt
kumesiydi -- 31/31 klip ayni MD5. Yani "kucuk sette ayar yaptik, buyuk sette
BAGIMSIZ dogruladik" iddiasi gecersizdi: buyuk set kucuk seti tamamen
iceriyordu, hicbir klip gorulmemis degildi.

COZUM: eval_big deterministik olarak ikiye bolunur:
  data/eval_tune/     -> ayar/gelistirme (prompt, esik, few-shot uzerinde calisilabilir)
  data/eval_holdout/  -> DOKUNULMAZ dogrulama (yalnizca son olcumde kosulur)

GARANTILER
  * Bolme MD5 tabanlidir: once ICERIK tekillestirilir (ayni MD5'li klipler tek
    sayilir), sonra kategori icinde ~50/50 bolunur. Boylece iki set arasinda
    ne AD ne de ICERIK cakismasi kalir.
  * Deterministik: ayni EVAL_SEED ayni bolmeyi verir.
  * Kategori dengesi korunur (her kategori kendi icinde bolunur).
  * SILME YOK: dosyalar hardlink ile baglanir (ayni birimde ek disk harcamaz,
    MD5 aynidir); hardlink desteklenmezse kopyalanir. ``data/eval_big``
    oldugu gibi kalir.
  * ``data/eval_split_manifest.json`` her klibin hangi sette oldugunu, MD5'ini
    ve boyutunu belgeler; ayrica ayriklik kaniti (kesisim = 0) yazilir.

Kullanim:
  python scripts/split_eval_big.py --list     # sadece plan + ayriklik kaniti
  python scripts/split_eval_big.py            # setleri kur
  EVAL_SEED=7 python scripts/split_eval_big.py --list
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections import defaultdict

from _sampling import env_str, get_seed, label_seed

SRC = env_str("SPLIT_SRC", os.path.join("data", "eval_big"))
TUNE = env_str("TUNE_OUT", os.path.join("data", "eval_tune"))
HOLD = env_str("HOLDOUT_OUT", os.path.join("data", "eval_holdout"))
MANIFEST = env_str("SPLIT_MANIFEST", os.path.join("data", "eval_split_manifest.json"))
EXTS = (".mp4", ".avi", ".mkv", ".mov")


def md5(path: str, chunk: int = 1 << 20) -> str:
    """Dosya MD5'i (akis halinde)."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def scan(src: str) -> dict[str, list[dict]]:
    """Kategori -> klip kayitlari. Ayni MD5'e sahip klipler TEK kayda indirgenir."""
    by_cat: dict[str, list[dict]] = defaultdict(list)
    seen: dict[str, str] = {}          # md5 -> ilk gorulen yol
    dupes: list[tuple[str, str]] = []
    for cat in sorted(os.listdir(src)):
        d = os.path.join(src, cat)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.lower().endswith(EXTS):
                continue
            p = os.path.join(d, fn)
            h = md5(p)
            if h in seen:
                dupes.append((p, seen[h]))
                continue
            seen[h] = p
            by_cat[cat].append({"ad": fn, "yol": p.replace("\\", "/"),
                                "md5": h, "boyut": os.path.getsize(p)})
    if dupes:
        print(f"# ICERIK MUKERRERI: {len(dupes)} klip elendi (ayni MD5):", flush=True)
        for a, b in dupes:
            print(f"    {a}  ==  {b}", flush=True)
    return by_cat


def split(by_cat: dict[str, list[dict]]) -> tuple[list[dict], list[dict]]:
    """Her kategoriyi deterministik olarak ~50/50 boler."""
    import random

    tune: list[dict] = []
    hold: list[dict] = []
    for cat, items in sorted(by_cat.items()):
        order = sorted(items, key=lambda r: r["md5"])   # kanonik siralama
        rnd = random.Random(label_seed(f"split:{cat}"))
        rnd.shuffle(order)
        k = len(order) // 2                              # tek sayida ise fazlasi holdout'a
        for r in order[:k]:
            r["set"] = "tune"
            r["kategori"] = cat
            tune.append(r)
        for r in order[k:]:
            r["set"] = "holdout"
            r["kategori"] = cat
            hold.append(r)
    return tune, hold


def materialise(rows: list[dict], out_root: str) -> int:
    """Kayitlari hedef kok altina hardlink'ler (olmazsa kopyalar)."""
    n = 0
    for r in rows:
        d = os.path.join(out_root, r["kategori"])
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, r["ad"])
        if not os.path.exists(dst):
            try:
                os.link(r["yol"], dst)
            except Exception:
                shutil.copy2(r["yol"], dst)
        n += 1
    return n


def mislabeled_industrial(by_cat: dict[str, list[dict]]) -> list[str]:
    """"Normal" altina konmus ama aslinda GUVENSIZ olan endustriyel klipleri bul (K14).

    Mendeley xjmtb22pff dosya adi ``<sinif>_<tr|te><no>.mp4`` bicimindedir ve
    class0-3 GUVENSIZ davranistir (bkz. data/industrial/CLASSES.md). Bu klipler
    "Normal" kategorisinde ise etiket YANLISTIR.
    """
    import re

    pat = re.compile(r"^([0-7])_(tr|te)\d+\.(mp4|avi)$", re.I)
    bad: list[str] = []
    for cat, items in by_cat.items():
        if "normal" not in cat.lower():
            continue
        for r in items:
            m = pat.match(r["ad"])
            if m and m.group(1) in "0123":
                bad.append(f"{cat}/{r['ad']}")
    return sorted(bad)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", "--dry-run", dest="dry", action="store_true",
                    help="Dosya olusturma; yalnizca plan ve ayriklik kanitini goster.")
    args = ap.parse_args()

    if not os.path.isdir(SRC):
        print(f"kaynak yok: {SRC}", flush=True)
        return
    print(f"# kaynak={SRC}  seed={get_seed()}", flush=True)
    by_cat = scan(SRC)
    tune, hold = split(by_cat)

    t_md5 = {r["md5"] for r in tune}
    h_md5 = {r["md5"] for r in hold}
    t_ad = {r["ad"] for r in tune}
    h_ad = {r["ad"] for r in hold}
    kesisim_md5 = sorted(t_md5 & h_md5)
    kesisim_ad = sorted(t_ad & h_ad)

    print(f"\n{'kategori':<16}{'toplam':>8}{'tune':>7}{'holdout':>9}", flush=True)
    print("-" * 40, flush=True)
    for cat in sorted(by_cat):
        nt = sum(1 for r in tune if r["kategori"] == cat)
        nh = sum(1 for r in hold if r["kategori"] == cat)
        print(f"{cat:<16}{nt+nh:>8}{nt:>7}{nh:>9}", flush=True)
    print("-" * 40, flush=True)
    print(f"{'TOPLAM':<16}{len(tune)+len(hold):>8}{len(tune):>7}{len(hold):>9}", flush=True)

    print(f"\nAYRIKLIK KANITI:  MD5 kesisimi={len(kesisim_md5)}  ad kesisimi={len(kesisim_ad)}"
          f"  ->  {'AYRIK (disjoint) DOGRULANDI' if not (kesisim_md5 or kesisim_ad) else 'CAKISMA VAR!'}",
          flush=True)

    yanlis = mislabeled_industrial(by_cat)
    if yanlis:
        print(f"\n!! ETIKET UYARISI (K14): 'Normal' altinda {len(yanlis)} adet GUVENSIZ "
              f"endustriyel klip var.\n   Mendeley class0-3 = guvensiz davranis "
              f"(bkz. data/industrial/CLASSES.md).\n   Bu klipler 'Normal' sayildigi surece "
              f"yanlis-pozitif orani OLDUGUNDAN DUSUK olcuLur:", flush=True)
        for y in yanlis:
            print(f"     {y}", flush=True)

    if args.dry:
        print("\nLISTE MODU: hicbir dosya olusturulmadi.", flush=True)
        return

    nt = materialise(tune, TUNE)
    nh = materialise(hold, HOLD)
    manifest = {
        "_aciklama": ("K9 duzeltmesi: data/eval_big ikiye AYRIK bolundu. eval_tune ayar icin, "
                      "eval_holdout yalnizca son dogrulama icin kullanilir. "
                      "DIKKAT: data/eval (eski kucuk set) eval_big'in ALT KUMESIDIR; "
                      "eval_holdout ile birlikte RAPORLANMAMALIDIR."),
        "kaynak": SRC.replace("\\", "/"),
        "seed": get_seed(),
        "tune_dizin": TUNE.replace("\\", "/"),
        "holdout_dizin": HOLD.replace("\\", "/"),
        "tune_sayisi": len(tune),
        "holdout_sayisi": len(hold),
        "md5_kesisimi": kesisim_md5,
        "ad_kesisimi": kesisim_ad,
        "ayrik_mi": not (kesisim_md5 or kesisim_ad),
        "yanlis_etiketli_endustriyel": yanlis,
        "klipler": sorted(tune + hold, key=lambda r: (r["kategori"], r["ad"])),
    }
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(f"\ntune={nt} -> {TUNE}\nholdout={nh} -> {HOLD}\nmanifest -> {MANIFEST}", flush=True)


if __name__ == "__main__":
    main()
