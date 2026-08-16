#!/usr/bin/env python
"""KKD veri setlerini COCO -> YOLO bicimine cevirir ve BIRLESTIRIR. GPU GEREKMEZ.

NEDEN BIRLESIK TAKSONOMI
------------------------
Iki set FARKLI sinif kumeleri kullaniyor:
  data/ppe/hard_hat            : 2 sinif  (hardhat, no-hardhat)
  data/ppe/construction_safety : 17 sinif (hardhat, no-hardhat, safety vest, ...)

Bize gereken sinyal **ihlal**dir: "baret var mi" degil, **"baretsiz kafa var mi"**.
Neyse ki iki set de bunu AYRI SINIF olarak etiketlemis (kutular kafa boyutunda).

  sinif 0 = baret_var  <- hardhat
  sinif 1 = baret_yok  <- no-hardhat

⚠️ YELEK NEDEN YOK — OLCULMUS GEREKCE
--------------------------------------
`construction_safety` egitim bolumunde yelek kutulari: **safety vest 45 · no-safety
vest 21 = 66 kutu**. Baret icin 38.701 kutu var. 66 kutu ile egitilen bir sinif,
DETERMINISTIK DOGRULAYICI olarak kullanilamaz — guvenilmez bir dedektor, hic
dedektor olmamasindan KOTUDUR (yanlis alarm en pahali hatadir, HANDOFF §3).

Bu yuzden yelek sinifi BILEREK DISARIDA birakildi. Veri duruyor; yelek icin ayri
ve yeterli bir set bulununca eklenir. Bu karar `data/ppe_yolo/DATASET.md`ye de yazilir.

⚠️ ALAN FARKI
-------------
Setler SANTIYE goruntusu; tesisimiz URETIM/IMALAT. Deterministik bir dedektor icin
bu fark bir VLM'in sahne anlamasina gore COK DAHA KUCUKTUR (baret bir kafanin
uzerindedir, santiyede de fabrikada da) — ama SIFIR DEGILDIR ve tesis verisinde
ayrica dogrulanmalidir.

Kullanim:
    python scripts/ppe_coco2yolo.py
    python scripts/ppe_coco2yolo.py --hedef data/ppe_yolo --sembolik-link
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: BIRLESIK taksonomi — yalnizca baret (yelek icin veri YETERSIZ, bkz. modul basligi)
SINIFLAR = ["baret_var", "baret_yok"]

#: Kaynak COCO sinif adi -> birlesik sinif indeksi. Listede OLMAYAN her sinif ATILIR.
#: Atilanlar sessizce degil, SAYILARAK raporlanir (K7).
ESLEME = {
    "hardhat": 0,
    "no-hardhat": 1,
}

#: (yerel ad, COCO kok dizini)
KAYNAKLAR = (
    ("hard_hat", os.path.join(ROOT, "data", "ppe", "hard_hat", "data")),
    ("construction_safety", os.path.join(ROOT, "data", "ppe", "construction_safety", "data")),
)

BOLUMLER = ("train", "valid", "test")


def _yolo_satiri(bbox, iw: int, ih: int, sinif: int) -> str | None:
    """COCO [x,y,w,h] (piksel) -> YOLO 'sinif cx cy w h' (0-1 normalize)."""
    x, y, w, h = bbox
    if w <= 0 or h <= 0 or iw <= 0 or ih <= 0:
        return None
    cx, cy = (x + w / 2.0) / iw, (y + h / 2.0) / ih
    nw, nh = w / iw, h / ih
    # Kirp: Roboflow disa aktarimlarinda kenar kutular 1.0'i asabiliyor
    cx, cy = min(max(cx, 0.0), 1.0), min(max(cy, 0.0), 1.0)
    nw, nh = min(nw, 1.0), min(nh, 1.0)
    if nw <= 0 or nh <= 0:
        return None
    return f"{sinif} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}"


def cevir(hedef: str, link: bool) -> dict:
    istat: dict = {"bolumler": {}, "atilan_siniflar": collections.Counter(),
                   "kaynak_bazinda": collections.defaultdict(
                       lambda: collections.Counter())}
    for bolum in BOLUMLER:
        img_dir = os.path.join(hedef, "images", bolum)
        lbl_dir = os.path.join(hedef, "labels", bolum)
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(lbl_dir, exist_ok=True)

        n_img = n_box = n_bos = 0
        sinif_say: collections.Counter = collections.Counter()

        for kaynak_ad, kok in KAYNAKLAR:
            ann_yol = os.path.join(kok, bolum, "_annotations.coco.json")
            if not os.path.exists(ann_yol):
                print(f"    [ATLA] {kaynak_ad}/{bolum}: etiket yok")
                continue
            with open(ann_yol, encoding="utf-8") as f:
                d = json.load(f)
            cats = {c["id"]: c["name"] for c in d.get("categories", [])}
            per_img: dict = collections.defaultdict(list)
            for a in d.get("annotations", []):
                ad = cats.get(a["category_id"], "?")
                if ad not in ESLEME:
                    istat["atilan_siniflar"][ad] += 1
                    continue
                per_img[a["image_id"]].append((ESLEME[ad], a["bbox"]))

            for im in d.get("images", []):
                kaynak_img = os.path.join(kok, bolum, im["file_name"])
                if not os.path.exists(kaynak_img):
                    continue
                # Ad cakismasi olmasin: kaynak onekiyle yaz
                yeni_ad = f"{kaynak_ad}__{im['file_name']}"
                hedef_img = os.path.join(img_dir, yeni_ad)
                if not os.path.exists(hedef_img):
                    if link:
                        try:
                            os.link(kaynak_img, hedef_img)      # sabit link: disk tasarrufu
                        except OSError:
                            shutil.copy2(kaynak_img, hedef_img)
                    else:
                        shutil.copy2(kaynak_img, hedef_img)

                satirlar = []
                for sinif, bbox in per_img.get(im["id"], []):
                    s = _yolo_satiri(bbox, im.get("width", 0), im.get("height", 0), sinif)
                    if s:
                        satirlar.append(s)
                        sinif_say[SINIFLAR[sinif]] += 1
                        istat["kaynak_bazinda"][kaynak_ad][SINIFLAR[sinif]] += 1
                # NEGATIF ornek (hic kutu yok) YOLO'da BOS .txt ile ifade edilir ve
                # yanlis-pozitifi dusurmek icin DEGERLIDIR -> atilmaz.
                if not satirlar:
                    n_bos += 1
                with open(os.path.join(lbl_dir, os.path.splitext(yeni_ad)[0] + ".txt"),
                          "w", encoding="utf-8") as f:
                    f.write("\n".join(satirlar))
                n_img += 1
                n_box += len(satirlar)

        istat["bolumler"][bolum] = {"gorsel": n_img, "kutu": n_box,
                                    "kutusuz_gorsel": n_bos, "sinif": dict(sinif_say)}
        print(f"    {bolum:6s} gorsel={n_img:6d}  kutu={n_box:7d}  "
              f"kutusuz={n_bos:5d}  {dict(sinif_say)}")
    return istat


def yaml_yaz(hedef: str) -> str:
    yol = os.path.join(hedef, "ppe.yaml")
    with open(yol, "w", encoding="utf-8") as f:
        f.write(
            "# KKD (baret) — YOLO veri seti tanimi\n"
            "# URETEN: scripts/ppe_coco2yolo.py   ·   LISANS: CC BY 4.0 (bkz. data/ppe/LISANS.json)\n"
            "# ⚠️ Yelek sinifi BILEREK YOK: egitimde yalnizca 66 kutu vardi (baret: 38.701).\n"
            f"path: {os.path.abspath(hedef)}\n"
            "train: images/train\n"
            "val: images/valid\n"
            "test: images/test\n"
            "names:\n"
            + "".join(f"  {i}: {ad}\n" for i, ad in enumerate(SINIFLAR))
        )
    return yol


def kunye_yaz(hedef: str, istat: dict) -> None:
    atilan = dict(istat["atilan_siniflar"].most_common())
    with open(os.path.join(hedef, "DATASET.md"), "w", encoding="utf-8") as f:
        f.write(f"""\
# KKD (baret) — YOLO veri seti

**Ureten:** `scripts/ppe_coco2yolo.py` · **Lisans:** CC BY 4.0
**Kaynaklar:** `keremberke/hard-hat-detection` + `keremberke/construction-safety-object-detection`

## Siniflar

| id | ad | anlam |
|---|---|---|
| 0 | `baret_var` | baret TAKAN kafa |
| 1 | `baret_yok` | baret TAKMAYAN kafa — **ihlal sinyali** |

## Bolumler

| bolum | gorsel | kutu | kutusuz gorsel |
|---|---|---|---|
""")
        for b in BOLUMLER:
            d = istat["bolumler"].get(b, {})
            f.write(f"| {b} | {d.get('gorsel', 0)} | {d.get('kutu', 0)} | "
                    f"{d.get('kutusuz_gorsel', 0)} |\n")
        f.write(f"""
Sinif dagilimi (train): {istat['bolumler'].get('train', {}).get('sinif', {})}

## ⚠️ YELEK NEDEN YOK — olculmus gerekce

`construction_safety` egitim bolumunde yelek kutulari **66** (safety vest 45 +
no-safety vest 21). Baret icin **38.701** kutu var.

66 kutu ile egitilen bir sinif **deterministik dogrulayici** olarak kullanilamaz.
Guvenilmez bir dedektor, hic dedektor olmamasindan KOTUDUR: bu sistemde
**yanlis alarm en pahali hatadir** (HANDOFF §3, sevk kapisinin varlik sebebi).

Veri siliNMEDI; yelek icin yeterli ve izin-verici lisansli bir set bulununca eklenir.

## Cevirmede ATILAN kaynak siniflari (sayilarla — sessizce atilmadi)

{json.dumps(atilan, ensure_ascii=False, indent=2)}

## ⚠️ ALAN FARKI

Setler **santiye** goruntusudur; dagitim ortamimiz **uretim/imalat tesisi**
(Eskisehir OSB). Deterministik dedektor icin bu fark bir VLM'e gore cok daha
kucuktur ama **sifir degildir** — tesis verisinde ayrica dogrulanmalidir.
""")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hedef", default=os.path.join("data", "ppe_yolo"))
    ap.add_argument("--sembolik-link", action="store_true",
                    help="gorselleri kopyalamak yerine SABIT LINK ver (disk tasarrufu)")
    args = ap.parse_args()

    hedef = args.hedef if os.path.isabs(args.hedef) else os.path.join(ROOT, args.hedef)
    print("=" * 78)
    print("KKD COCO -> YOLO cevirisi")
    print(f"  siniflar : {SINIFLAR}")
    print(f"  hedef    : {os.path.relpath(hedef, ROOT)}")
    print("  ⚠️ yelek BILEREK disarida (egitimde 66 kutu — dogrulayici icin yetersiz)")
    print("=" * 78)

    for _ad, kok in KAYNAKLAR:
        if not os.path.isdir(kok):
            print(f"[HATA] kaynak yok: {kok}\n       once: python scripts/get_ppe.py")
            return 1

    istat = cevir(hedef, bool(args.sembolik_link))
    yol = yaml_yaz(hedef)
    kunye_yaz(hedef, istat)

    print("\nATILAN kaynak siniflari (birlesik taksonomiye girmeyenler):")
    for ad, n in istat["atilan_siniflar"].most_common(12):
        print(f"    {ad:20s} {n:6d} kutu")
    print(f"\nYAML: {os.path.relpath(yol, ROOT)}")
    print(f"KUNYE: {os.path.relpath(os.path.join(hedef, 'DATASET.md'), ROOT)}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
