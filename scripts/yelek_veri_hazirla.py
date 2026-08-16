#!/usr/bin/env python
"""YELEK (hi-vis) YOLO veri setini hazirlar. GPU GEREKMEZ.

NEDEN YELEK — OLCULMUS GEREKCE (D35)
------------------------------------
`scripts/ppe_etiket_hazirla.py` ile uretilen inceleme paketi ELLE incelendi:
tesiste isciler **baret TAKMIYOR**, **yesil hi-vis YELEK giyiyor**. Baret
dedektorumuz dogru calisiyor (tesiste kutular tam baretsiz kafalarda) ama bu
pres atolyesinde baret muhtemelen zorunlu degil -> "baretsiz personel" burada
bir IHLAL OLMAYABILIR.

**Bu dagitim icin anlamli KKD YELEKTIR.**

Onceki denemede yelek egitilememisti: `data/ppe`de yelek kutusu TOPLAM 91'di.
Yeni kaynak bunu 22 KAT artiriyor.

KAYNAK
------
`LibreYOLO/construction-safety-gsnvb` (HuggingFace)
  * Lisans **CC BY 4.0** — `data.yaml` icindeki `roboflow.license` alanindan
    BIREBIR teyitli (dosyanin kendisi soyluyor, metadata tahmini degil)
  * Roboflow 100 Benchmark parcasi
  * Kutu sayimi (train+test): vest **1.202**, no-vest **802**

⚠️ NEDEN BARET VERISIYLE BIRLESTIRILMIYOR
------------------------------------------
Iki setin etiket uzayi AYRIK: baret seti (keremberke) yelekleri ETIKETLEMEZ.
Birlestirilseydi, baret setindeki YELEKLI bir isci "etiketsiz" kalir ve modele
"burada yelek YOK" diye ogretilirdi -> yelek sinifi icin SISTEMATIK yanlis-negatif.
Bu, veri birlestirmede klasik ve sessiz bir hatadir.

COZUM: AYRI dedektor. Iki YOLO cikarimi klip basina ~2.2 ms — K4 butcesinde
(klip basina ~20 sn) tamamen ihmal edilebilir.

Bu betik yalnizca `vest` / `no-vest` siniflarini alir; `helmet`/`no-helmet`/
`person` ATILIR (baret icin ayri ve 20 kat buyuk verimiz var).

Kullanim:
    python scripts/yelek_veri_hazirla.py
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

KAYNAK = os.path.join(ROOT, "data", "ppe", "gsnvb_vest")
HEDEF = os.path.join(ROOT, "data", "yelek_yolo")

#: Birlesik taksonomi (baret dedektoruyle AYNI desen: <sey>_var / <sey>_yok)
SINIFLAR = ["yelek_var", "yelek_yok"]
#: kaynak sinif adi -> hedef indeks. Listede olmayan ATILIR (sayilarak raporlanir).
ESLEME = {"vest": 0, "no-vest": 1}

BOLUM_ESLEME = {"train": "train", "valid": "valid", "test": "test"}


def _kaynak_adlari() -> list:
    import yaml
    with open(os.path.join(KAYNAK, "data.yaml"), encoding="utf-8") as f:
        d = yaml.safe_load(f)
    adlar = d.get("names")
    if isinstance(adlar, dict):
        adlar = [adlar[k] for k in sorted(adlar)]
    return list(adlar or [])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--link", action="store_true", default=True,
                    help="gorselleri kopyalamak yerine SABIT LINK ver (varsayilan)")
    args = ap.parse_args()

    if not os.path.isdir(KAYNAK):
        print(f"[HATA] kaynak yok: {os.path.relpath(KAYNAK, ROOT)}")
        print("       HuggingFace'ten indirin: LibreYOLO/construction-safety-gsnvb")
        return 1

    adlar = _kaynak_adlari()
    print("=" * 82)
    print("YELEK (hi-vis) YOLO veri seti")
    print(f"  kaynak siniflar : {adlar}")
    print(f"  hedef siniflar  : {SINIFLAR}   (vest->yelek_var, no-vest->yelek_yok)")
    print("  ⚠️ helmet/no-helmet/person ATILIYOR — baret icin AYRI ve 20 kat buyuk veri var")
    print("=" * 82)

    istat = {"bolumler": {}, "atilan": collections.Counter()}
    for kay_b, hed_b in BOLUM_ESLEME.items():
        k_img = os.path.join(KAYNAK, kay_b, "images")
        k_lbl = os.path.join(KAYNAK, kay_b, "labels")
        if not os.path.isdir(k_img):
            continue
        h_img = os.path.join(HEDEF, "images", hed_b)
        h_lbl = os.path.join(HEDEF, "labels", hed_b)
        os.makedirs(h_img, exist_ok=True)
        os.makedirs(h_lbl, exist_ok=True)

        n_img = n_box = n_bos = 0
        say = collections.Counter()
        for dosya in sorted(os.listdir(k_img)):
            tab, uzt = os.path.splitext(dosya)
            if uzt.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            lbl = os.path.join(k_lbl, tab + ".txt")
            satirlar = []
            if os.path.exists(lbl):
                for satir in open(lbl, encoding="utf-8"):
                    p = satir.split()
                    if len(p) < 5:
                        continue
                    ad = adlar[int(p[0])] if int(p[0]) < len(adlar) else str(p[0])
                    if ad not in ESLEME:
                        istat["atilan"][ad] += 1
                        continue
                    satirlar.append(f"{ESLEME[ad]} {' '.join(p[1:5])}")
                    say[SINIFLAR[ESLEME[ad]]] += 1

            hedef_img = os.path.join(h_img, dosya)
            if not os.path.exists(hedef_img):
                try:
                    if args.link:
                        os.link(os.path.join(k_img, dosya), hedef_img)
                    else:
                        raise OSError
                except OSError:
                    shutil.copy2(os.path.join(k_img, dosya), hedef_img)
            # BOS .txt = NEGATIF ornek. Yelek olmayan sahneler yanlis-pozitifi
            # dusurur -> atilmaz, bilerek yazilir.
            with open(os.path.join(h_lbl, tab + ".txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(satirlar))
            n_img += 1
            n_box += len(satirlar)
            if not satirlar:
                n_bos += 1

        istat["bolumler"][hed_b] = {"gorsel": n_img, "kutu": n_box,
                                    "kutusuz": n_bos, "sinif": dict(say)}
        print(f"  {hed_b:6s} gorsel={n_img:5d}  kutu={n_box:5d}  kutusuz={n_bos:4d}  {dict(say)}")

    # --- yaml ---
    with open(os.path.join(HEDEF, "yelek.yaml"), "w", encoding="utf-8") as f:
        f.write(
            "# YELEK (hi-vis) — YOLO veri seti tanimi\n"
            "# URETEN: scripts/yelek_veri_hazirla.py\n"
            "# KAYNAK: LibreYOLO/construction-safety-gsnvb (HF)\n"
            "# LISANS: CC BY 4.0 (kaynak data.yaml roboflow.license alanindan teyitli)\n"
            "# NOT: baret verisiyle BIRLESTIRILMEZ — etiket uzaylari ayrik (bkz. betik basligi)\n"
            f"path: {os.path.abspath(HEDEF)}\n"
            "train: images/train\nval: images/valid\ntest: images/test\n"
            "names:\n" + "".join(f"  {i}: {a}\n" for i, a in enumerate(SINIFLAR))
        )

    # --- kunye (lisans kapisi bunu okur) ---
    with open(os.path.join(HEDEF, "LISANS.json"), "w", encoding="utf-8") as f:
        json.dump({
            "veri_seti": "YELEK (hi-vis) — gsnvb turevi",
            "kaynak": "https://huggingface.co/datasets/LibreYOLO/construction-safety-gsnvb",
            "lisans": "CC BY 4.0",
            "lisans_teyidi": "kaynak data.yaml icindeki roboflow.license alani",
            "egitimde_kullanilabilir": True,
            "degerlendirmede_kullanilabilir": True,
            "yeniden_yayimlanabilir": True,
            "gerekce": ("D35 gorsel denetimi: tesiste isciler BARET takmiyor, hi-vis "
                        "YELEK giyiyor -> bu dagitim icin anlamli KKD yelektir."),
            "alan_uyarisi": ("Kaynak SANTIYE goruntusu; tesisimiz URETIM. Deterministik "
                             "dedektor icin fark kucuk ama SIFIR DEGIL."),
            "neden_baretle_birlestirilmedi": (
                "Etiket uzaylari AYRIK: baret seti yelekleri etiketlemez. Birlestirme "
                "yelek sinifi icin SISTEMATIK yanlis-negatif uretirdi."),
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  ATILAN kaynak siniflari: {dict(istat['atilan'].most_common())}")
    t = sum(b["kutu"] for b in istat["bolumler"].values())
    print(f"  TOPLAM yelek kutusu: {t}   (onceki elimizdeki: 91 -> {t / 91:.0f} kat)")
    print(f"  yaml : {os.path.relpath(os.path.join(HEDEF, 'yelek.yaml'), ROOT)}")
    print("=" * 82)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
