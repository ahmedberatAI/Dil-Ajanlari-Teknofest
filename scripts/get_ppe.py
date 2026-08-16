#!/usr/bin/env python
"""KKD (PPE) veri setlerini indirir — YOLO DOGRULAYICI EGITIMI icin. GPU GEREKMEZ.

NEDEN BU VERI (olculmus gerekce)
--------------------------------
HANDOFF §5.2 Bosluk 2, KKD'yi **"ISG'nin en yaygin senaryosu, jurinin ilk test
edecegi sey"** diye isaretliyor ve bizde HIC yok.

§6.2 mimari karari: **KKD tespiti VLM isi DEGIL, YOLO isidir.** Ham nesne
listesini VLM'e "kanit" diye vermek yanlis alarmi %0 -> %12 yukseltmisti;
dogru yol `detector.verify_pose_falls` gibi **deterministik dogrulayici**.

D33 (2026-08-16) bu karari BAGIMSIZ olarak dogruladi: `guided_choice` ile
zorunlu secim yaptirildiginda model, acik/kapali pano kapagi sorusunda 20 klibin
20'sinde de "KAPALI" dedi (10'u gercekte ACIK). Yani **ince, ikili gorsel durum**
bu VLM'in okuyabildigi bir sey degil. Baret var/yok tam olarak ayni problem
sinifidir -> deterministik dedektor gerekir.

⚖️ LISANS SUZGECI — NEDEN BU SETLER SECILDI
--------------------------------------------
Bu veriyle **AGIRLIK URETILECEK** (YOLO ince ayari). Dolayisiyla lisans
**izin verici** olmali. Elenenler ve gerekceleri:

| Aday | Lisans | Karar |
|---|---|---|
| **SH17** (8.099 gorsel, 17 sinif, *uretim sanayi*) | **CC BY-NC-SA 4.0** | ⛔ ELENDI — ShareAlike agirliklari kirletir; alan eslesmesi EN IYI olmasina ragmen |
| Ultralytics Construction-PPE (1.416 gorsel) | **AGPL-3.0** | ⛔ ELENDI — copyleft riski |
| iSafetyBench | CC BY-NC-SA 4.0 | ⛔ zaten yalniz DEGERLENDIRME (bkz. scripts/get_isafety_bench.py) |
| **keremberke/hard-hat-detection** | **CC BY 4.0** | ✅ ALINDI |
| **keremberke/construction-safety-object-detection** | **CC BY 4.0** | ✅ ALINDI |

⚠️ **ALAN FARKI — DURUSTCE YAZILIYOR:** alinan iki set **santiye** goruntusudur;
bizim tesis **uretim/imalat**tir. En iyi alan eslesmesi olan SH17 lisans yuzunden
elendi. Deterministik bir dedektor icin bu fark, bir VLM'in sahne anlamasina gore
COK DAHA AZ onemlidir (baret bir kafanin uzerindedir, santiyede de fabrikada da) —
ama **sifir degildir** ve tesis verisinde ayrica dogrulanmalidir.

Kullanim:
    python scripts/get_ppe.py                # ikisini de indir + ac
    python scripts/get_ppe.py --sadece-kucuk # yalniz cok-sinifli kucuk set (~hizli)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEDEF = os.path.join(ROOT, "data", "ppe")

#: (HF repo, yerel ad, lisans, aciklama, ~boyut)
SETLER = (
    ("keremberke/hard-hat-detection", "hard_hat", "CC BY 4.0",
     "19.745 gorsel · siniflar: Hardhat / NO-Hardhat · COCO · 640x640", "~1.12 GB"),
    ("keremberke/construction-safety-object-detection", "construction_safety", "CC BY 4.0",
     "398 gorsel · 17 sinif (hardhat, safety vest, gloves, no-hardhat, "
     "no-safety vest, ...) · COCO", "~30 MB"),
)

KUNYE_NOTU = """\
# KKD (PPE) veri setleri — EGITIMDE KULLANILABILIR

**Amac:** HANDOFF §6.2'nin mimari karari geregi **deterministik YOLO dogrulayici**
egitmek. VLM'e metin enjeksiyonu OLARAK KULLANILMAZ (olculdu: yanlis alarm %0 -> %12).

## Alinan setler

| Set | Kaynak | Lisans | Icerik |
|---|---|---|---|
| `hard_hat/` | [keremberke/hard-hat-detection](https://huggingface.co/datasets/keremberke/hard-hat-detection) | **CC BY 4.0** | 19.745 gorsel · Hardhat / NO-Hardhat |
| `construction_safety/` | [keremberke/construction-safety-object-detection](https://huggingface.co/datasets/keremberke/construction-safety-object-detection) | **CC BY 4.0** | 398 gorsel · 17 sinif (yelek/eldiven dahil) |

## Elenenler ve NEDEN (kayit — tekrar onerilmesin)

| Aday | Lisans | Neden elendi |
|---|---|---|
| **SH17** (8.099 gorsel, 17 sinif, **uretim sanayi**) | CC BY-NC-SA 4.0 | ShareAlike: agirliklar turev eser sayilabilir. **Alan eslesmesi EN IYI olan adaydi**; yalnizca lisans yuzunden elendi. |
| Ultralytics Construction-PPE | AGPL-3.0 | copyleft riski |
| iSafetyBench | CC BY-NC-SA 4.0 | yalnizca degerlendirme (bkz. `data/isafety_bench/NOKULLAN_EGITIM.md`) |

## ⚠️ ALAN FARKI (rapor yazarken belirtilmeli)

Bu iki set **santiye** goruntusudur; dagitim ortamimiz **uretim/imalat tesisi**
(Eskisehir OSB). Deterministik dedektor icin bu fark VLM'e gore cok daha az
onemlidir ama **sifir degildir**: tesis verisinde ayrica dogrulanmalidir.

## ATIF (CC BY — zorunlu)

Her iki set de Roboflow Universe uzerinden yayimlanmis, HuggingFace'te
`keremberke` tarafindan aynalanmistir. Kullanimda kaynak ve CC BY 4.0 atfi verilir.
"""


def indir(repo: str, yerel: str) -> bool:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("  [HATA] huggingface_hub yok: pip install huggingface_hub")
        return False
    hedef = os.path.join(HEDEF, yerel)
    os.makedirs(hedef, exist_ok=True)
    print(f"  indiriliyor: {repo} -> data/ppe/{yerel}")
    try:
        snapshot_download(repo_id=repo, repo_type="dataset", local_dir=hedef,
                          max_workers=4)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  [HATA] {type(e).__name__}: {e}")
        return False


def zipleri_ac(yerel: str) -> int:
    """data/*.zip dosyalarini yerinde acar (Roboflow disa aktarim bicimi)."""
    kok = os.path.join(HEDEF, yerel)
    acilan = 0
    for dp, _dn, fs in os.walk(kok):
        for f in fs:
            if not f.endswith(".zip"):
                continue
            z = os.path.join(dp, f)
            cikis = os.path.join(dp, f[:-4])
            if os.path.isdir(cikis) and os.listdir(cikis):
                continue                      # zaten acilmis
            try:
                with zipfile.ZipFile(z) as zf:
                    zf.extractall(cikis)
                acilan += 1
                print(f"    acildi: {os.path.relpath(cikis, ROOT)}")
            except (zipfile.BadZipFile, OSError) as e:
                print(f"    [UYARI] acilamadi {f}: {e}")
    return acilan


def kunye_yaz() -> None:
    os.makedirs(HEDEF, exist_ok=True)
    with open(os.path.join(HEDEF, "KAYNAKLAR.md"), "w", encoding="utf-8") as f:
        f.write(KUNYE_NOTU)
    with open(os.path.join(HEDEF, "LISANS.json"), "w", encoding="utf-8") as f:
        json.dump({
            "veri_seti": "KKD (PPE) — YOLO dogrulayici egitimi icin",
            "lisans": "CC BY 4.0",
            "egitimde_kullanilabilir": True,
            "degerlendirmede_kullanilabilir": True,
            "yeniden_yayimlanabilir": True,
            "kaynaklar": [
                {"repo": r, "yerel": y, "lisans": lis, "icerik": ic, "boyut": b}
                for r, y, lis, ic, b in SETLER
            ],
            "elenen_adaylar": [
                {"ad": "SH17", "lisans": "CC BY-NC-SA 4.0",
                 "neden": "ShareAlike agirliklari kirletir; ALAN ESLESMESI EN IYI olan adaydi"},
                {"ad": "Ultralytics Construction-PPE", "lisans": "AGPL-3.0",
                 "neden": "copyleft riski"},
            ],
            "alan_uyarisi": ("Setler SANTIYE goruntusudur; dagitim ortami URETIM tesisi. "
                             "Deterministik dedektor icin fark kucuktur ama SIFIR DEGILDIR — "
                             "tesis verisinde ayrica dogrulanmali."),
            "mimari_karar": ("HANDOFF §6.2: KKD tespiti VLM isi DEGIL. Deterministik "
                             "dogrulayici olarak eklenir; ham nesne listesi VLM'e KANIT "
                             "diye VERILMEZ (olculdu: yanlis alarm %0 -> %12)."),
        }, f, ensure_ascii=False, indent=2)
    print(f"  kunye yazildi: data/ppe/LISANS.json + KAYNAKLAR.md")


def ozet() -> None:
    for _r, yerel, lis, _ic, _b in SETLER:
        kok = os.path.join(HEDEF, yerel)
        if not os.path.isdir(kok):
            print(f"    {yerel:22s} [yok]")
            continue
        n_img = sum(1 for dp, _, fs in os.walk(kok) for f in fs
                    if f.lower().endswith((".jpg", ".jpeg", ".png")))
        n_json = sum(1 for dp, _, fs in os.walk(kok) for f in fs if f.endswith(".json"))
        boyut = sum(os.path.getsize(os.path.join(dp, f))
                    for dp, _, fs in os.walk(kok) for f in fs)
        print(f"    {yerel:22s} {n_img:6d} gorsel  {n_json:3d} json  "
              f"{boyut / 1e6:8.1f} MB  [{lis}]")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sadece-kucuk", action="store_true",
                    help="yalniz cok-sinifli kucuk seti indir (hizli deneme)")
    args = ap.parse_args()

    print("=" * 78)
    print("KKD (PPE) VERI SETLERI — YOLO dogrulayici egitimi icin")
    print("✅ LISANS: CC BY 4.0 (egitimde KULLANILABILIR)")
    print("⛔ SH17 ve Ultralytics-PPE ELENDI — CC BY-NC-SA / AGPL (bkz. KAYNAKLAR.md)")
    print("=" * 78)

    kunye_yaz()
    setler = SETLER[1:] if args.sadece_kucuk else SETLER
    for repo, yerel, lis, icerik, boyut in setler:
        print(f"\n--- {yerel}  [{lis}]  {boyut}")
        print(f"    {icerik}")
        if not indir(repo, yerel):
            return 1
        n = zipleri_ac(yerel)
        if n:
            print(f"    {n} arsiv acildi")

    print("\nOZET:")
    ozet()
    print("\n" + "=" * 78)
    print("SONRAKI ADIM: YOLO bicimine cevir ve deterministik dogrulayici olarak ekle")
    print("  (§6.2 karari: metin enjeksiyonu DEGIL, detector.verify_* gibi dogrulayici)")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
