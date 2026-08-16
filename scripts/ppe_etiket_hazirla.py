#!/usr/bin/env python
"""TESIS kliplerinde KKD ground-truth uretmek icin INSAN-INCELEME paketi hazirlar.

NEDEN BU ARAC VAR
-----------------
KKD dedektoru kendi test bolumunde mAP50 0,934 aliyor — ama o veri SANTIYE.
Bizim tesis URETIM. Dedektorun DAGITILACAGI yerdeki dogrulugu **olculemiyor**,
cunku `data/eval_defense` kliplerinde KKD etiketi YOK (Mendeley seti baretle
ilgili degil). Bu yuzden `ppe_dispatch` KAPALI birakildi.

Bu betik o boslugu kapatmayi 20 dakikalik bir ise indirger:

  1. Kliplerden kare cikarir, dedektoru kosar
  2. Kutulari CIZER ve klip basina bir KONTAK SAYFASI (kare izgarasi) uretir
  3. Insanin yalnizca VAR/YOK/BELIRSIZ yazacagi bir CSV sablonu olusturur

⚠️ ORNEKLEM TASARIMI — NEDEN "TESPIT EDILENLER" YETMEZ
------------------------------------------------------
Yalnizca dedektorun ihlal buldugu klipler incelenirse **precision** olculur,
**recall** OLCULEMEZ (kacirilanlar hic gorunmez). Bu yuzden paket UC KOVADAN
dengeli ornek alir:

  A) dedektor IHLAL buldu            -> yanlis-pozitif avi (precision)
  B) dedektor BARETLI kafa buldu     -> siniflandirma hatasi avi
  C) dedektor HICBIR SEY bulmadi     -> KACIRMA avi (recall) ← en cok atlanan

⚠️ ONEMLI: kontak sayfalarinda kutular CIZILIDIR. Bu, insani dedektore dogru
yanlilastirir (anchoring). O yuzden CSV'de "dedektor ne dedi" sutunu vardir ve
`--kutusuz` bayragi kutusuz sayfa da uretir — sart kosullarinda ikisi
karsilastirilmalidir. Sonuc raporlanirken hangi kipin kullanildigi YAZILMALIDIR.

⚠️ KVKK: uretilen sayfalar TANINABILIR CALISANLAR icerir. `data/` altina yazilir
(gitignore'da) ve **yeniden yayimlanmaz** (bkz. docs/veri_lisans_karari.md §4).

Kullanim:
    python scripts/ppe_etiket_hazirla.py                 # kova basina 15 klip
    python scripts/ppe_etiket_hazirla.py --n 25 --kutusuz
"""
from __future__ import annotations

import argparse
import csv
import glob
import io
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw  # noqa: E402

from dilajan import detector  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402

HEDEF = os.path.join(ROOT, "data", "ppe_tesis_etiket")
# TASARIM NOTU (olculdu, ilk surumde YANLISTI):
# Tesis kamerasi TAVANDAN ve UZAKTAN cekiyor; 1080p karede bir kafa ~20-30 piksel.
# Ilk surum 3x3 izgara + 400 px hucre kullaniyordu -> kafa ~10 piksele iniyordu ve
# INSAN GUVENILIR ETIKETLEYEMIYORDU. Etiketlenemeyen bir paket ise yaramaz.
# Cozum: (a) 2x2 izgara + buyuk hucre, (b) en-boy orani KORUNUR (siyah bant yok),
# (c) tespit VARSA ayrica YAKINLASTIRILMIS KIRPMA sayfasi uretilir.
IZGARA = (2, 2)          # kontak sayfasi: 2x2 = 4 kare (buyuk)
HUCRE = 760              # hucre uzun kenari (piksel)
KIRPMA_PAY = 3.0         # tespit kutusunun kac katini kirp (baglam icin)
KIRPMA_BOY = 320         # kirpma karesinin cikti boyu


def _kareler(yol: str, azami: int = 9):
    ham, _ = extract_timestamped_frames(yol)
    if not ham:
        return []
    if len(ham) > azami:
        adim = len(ham) / azami
        ham = [ham[int(i * adim)] for i in range(azami)]
    return [(f"{int(t) // 60:02d}:{int(t) % 60:02d}", j) for t, j in ham]


def _model_kutulari(frames, conf: float):
    """Kare basina [(sinif_adi, xyxy, guven)] — kutu cizimi icin."""
    model = detector._get_ppe_model()
    if model is None:
        return None
    imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in frames]
    sonuc = model.predict(imgs, conf=conf, verbose=False, device="cuda")
    adlar = getattr(model, "names", {}) or {}
    out = []
    for r in sonuc:
        kutular = []
        for box, cls, cf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(),
                                r.boxes.conf.tolist()):
            kutular.append((str(adlar.get(int(cls), int(cls))), box, float(cf)))
        out.append(kutular)
    return imgs, out


def _renk(ad: str):
    """baret_yok = IHLAL -> kirmizi ; baret_var -> yesil."""
    return (255, 70, 70) if ad == "baret_yok" else (70, 220, 120)


def _kontak_sayfasi(imgs, kutular, kutu_ciz: bool) -> Image.Image:
    """2x2 kontak sayfasi. En-boy orani KORUNUR (hucre yatay videoya gore olculur)."""
    sut, sat = IZGARA
    ornek = imgs[0]
    oran = HUCRE / max(ornek.width, ornek.height)
    hw, hh = int(ornek.width * oran), int(ornek.height * oran)
    sayfa = Image.new("RGB", (sut * hw, sat * hh), (24, 24, 28))
    for i, im in enumerate(imgs[: sut * sat]):
        yeni = im.resize((hw, hh))
        d = ImageDraw.Draw(yeni)
        if kutu_ciz and kutular:
            for ad, (x1, y1, x2, y2), cf in kutular[i]:
                r = _renk(ad)
                d.rectangle([x1 * oran, y1 * oran, x2 * oran, y2 * oran],
                            outline=r, width=3)
                d.text((x1 * oran + 2, max(0, y1 * oran - 12)), f"{ad} {cf:.2f}", fill=r)
        sayfa.paste(yeni, ((i % sut) * hw, (i // sut) * hh))
    return sayfa


def _kirpma_sayfasi(imgs, kutular):
    """Her tespitin ETRAFINI yakinlastirip tek sayfada toplar.

    Tesis kamerasinda kafa ~20-30 piksel; tam kare uzerinden insan karar veremez.
    Kutunun KIRPMA_PAY kati kadar baglamla kirpilir ve buyutulur -> etiketlenebilir.
    Tespit yoksa None (C_bos kovasinda kirpma anlamsizdir).
    """
    parcalar = []
    for i, kk in enumerate(kutular or []):
        im = imgs[i]
        for ad, (x1, y1, x2, y2), cf in kk:
            gw, gh = x2 - x1, y2 - y1
            k = max(gw, gh) * KIRPMA_PAY / 2.0
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            kutu = (max(0, int(cx - k)), max(0, int(cy - k)),
                    min(im.width, int(cx + k)), min(im.height, int(cy + k)))
            if kutu[2] - kutu[0] < 8 or kutu[3] - kutu[1] < 8:
                continue
            kirp = im.crop(kutu).resize((KIRPMA_BOY, KIRPMA_BOY), Image.LANCZOS)
            d = ImageDraw.Draw(kirp)
            o = KIRPMA_BOY / max(1, kutu[2] - kutu[0])
            d.rectangle([(x1 - kutu[0]) * o, (y1 - kutu[1]) * o,
                         (x2 - kutu[0]) * o, (y2 - kutu[1]) * o],
                        outline=_renk(ad), width=2)
            d.text((4, 4), f"{ad} {cf:.2f}", fill=_renk(ad))
            parcalar.append(kirp)
    if not parcalar:
        return None
    sut = min(4, len(parcalar))
    sat = (len(parcalar) + sut - 1) // sut
    sayfa = Image.new("RGB", (sut * KIRPMA_BOY, sat * KIRPMA_BOY), (24, 24, 28))
    for i, p in enumerate(parcalar[: sut * sat]):
        sayfa.paste(p, ((i % sut) * KIRPMA_BOY, (i // sut) * KIRPMA_BOY))
    return sayfa


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=15, help="KOVA BASINA klip sayisi")
    ap.add_argument("--conf", type=float, default=0.45)
    ap.add_argument("--tohum", type=int, default=2026)
    ap.add_argument("--kutusuz", action="store_true",
                    help="kutu CIZMEDEN de sayfa uret (anchoring karsilastirmasi)")
    args = ap.parse_args()

    if not detector.ppe_available():
        print("[HATA] yolo11n-ppe.pt yok — once: python scripts/train_ppe.py")
        return 1

    klipler = sorted(glob.glob(os.path.join(ROOT, "data", "eval_defense",
                                            "*", "*", "*.mp4")))
    if not klipler:
        print("[HATA] data/eval_defense klipleri yok")
        return 1
    random.Random(args.tohum).shuffle(klipler)

    os.makedirs(HEDEF, exist_ok=True)
    kovalar = {"A_ihlal": [], "B_baretli": [], "C_bos": []}
    hedef_n = args.n

    print("=" * 86)
    print("KKD TESIS ETIKETLEME PAKETI")
    print(f"  kova basina hedef: {hedef_n} klip   ·   conf={args.conf}")
    print("  A=dedektor IHLAL buldu · B=BARETLI buldu · C=HICBIR SEY bulmadi")
    print("  ⚠️ C kovasi RECALL icin sarttir — atlanirsa yalnizca precision olculur")
    print("=" * 86)

    satirlar = []
    for yol in klipler:
        if all(len(v) >= hedef_n for v in kovalar.values()):
            break
        frames = _kareler(yol)
        if not frames:
            continue
        paket = _model_kutulari(frames, args.conf)
        if paket is None:
            print("[HATA] model yuklenemedi")
            return 1
        imgs, kutular = paket
        n_yok = sum(1 for kk in kutular for ad, _, _ in kk if ad == "baret_yok")
        n_var = sum(1 for kk in kutular for ad, _, _ in kk if ad == "baret_var")

        kova = "A_ihlal" if n_yok else ("B_baretli" if n_var else "C_bos")
        if len(kovalar[kova]) >= hedef_n:
            continue
        kovalar[kova].append(yol)

        ad = os.path.splitext(os.path.basename(yol))[0]
        alt = os.path.join(HEDEF, kova)
        os.makedirs(alt, exist_ok=True)
        _kontak_sayfasi(imgs, kutular, kutu_ciz=True).save(
            os.path.join(alt, f"{ad}__kutulu.jpg"), quality=90)
        if args.kutusuz:
            _kontak_sayfasi(imgs, kutular, kutu_ciz=False).save(
                os.path.join(alt, f"{ad}__kutusuz.jpg"), quality=90)
        # Tespit varsa YAKINLASTIRILMIS kirpma sayfasi — kafa ~20-30 px oldugu icin
        # tam kare uzerinden insan karar veremez (olculdu).
        kirpma = _kirpma_sayfasi(imgs, kutular)
        if kirpma is not None:
            kirpma.save(os.path.join(alt, f"{ad}__yakin.jpg"), quality=92)

        satirlar.append({
            "kova": kova,
            "klip": os.path.relpath(yol, ROOT).replace("\\", "/"),
            "sayfa": f"{kova}/{ad}__kutulu.jpg",
            "dedektor_baretsiz_kutu": n_yok,
            "dedektor_baretli_kutu": n_var,
            "dedektor_karari": "IHLAL" if n_yok else "ihlal_yok",
            # --- INSAN DOLDURACAK ---
            "insan_baretsiz_kisi_VAR_MI": "",   # EVET / HAYIR / BELIRSIZ
            "not": "",
        })
        print(f"  [{kova}] {os.path.basename(yol):16s} baretsiz={n_yok} baretli={n_var}")

    csv_yol = os.path.join(HEDEF, "etiket_sablonu.csv")
    with open(csv_yol, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(satirlar[0].keys()) if satirlar else [])
        w.writeheader()
        w.writerows(satirlar)

    with open(os.path.join(HEDEF, "NASIL_ETIKETLENIR.md"), "w", encoding="utf-8") as f:
        f.write(f"""\
# KKD tesis etiketleme — nasıl doldurulur

**Amaç:** dedektörün **dağıtılacağı yerde** (üretim tesisi) doğruluğunu ölçmek.
Şu an bu ölçüm yok, o yüzden `ppe_dispatch` kapalı.

## Yapılacak (≈20 dk)

`etiket_sablonu.csv` dosyasını aç. Her satır için ilgili kontak sayfasına bak
(`sayfa` sütunundaki dosya) ve **tek bir sütunu** doldur:

`insan_baretsiz_kisi_VAR_MI` → **EVET** / **HAYIR** / **BELIRSIZ**

Soru şu: *bu klipte baret takmayan en az bir kişi var mı?*
- Kişi hiç yoksa → **HAYIR**
- Kafa seçilemiyorsa / çok küçük / bulanıksa → **BELIRSIZ** (zorlamayın, tahmin etmeyin)

## ⚠️ Üç kova neden var

| Kova | Ne | Neyi ölçer |
|---|---|---|
| `A_ihlal` | dedektör ihlal buldu | **precision** (yanlış alarm) |
| `B_baretli` | dedektör baretli kafa buldu | sınıflandırma hatası |
| `C_bos` | dedektör hiçbir şey bulmadı | **recall** (kaçırma) |

**`C_bos` kovasını atlamayın.** Yalnızca A'ya bakılırsa precision ölçülür,
recall ölçülemez — kaçırdıkları hiç görünmez.

## ⚠️ Yanlılık uyarısı

Kontak sayfalarında dedektörün kutuları **çizilidir**. Bu sizi onun kararına
doğru yanlılaştırır (anchoring). `--kutusuz` ile üretildiyse önce **kutusuz**
sayfaya bakıp karar verin, sonra kutuluyu açın.
Raporlarken hangi kipte etiketlendiği **yazılmalıdır**.

## ⚠️ KVKK

Bu sayfalar tanınabilir çalışanlar içerir. `data/` altındadır (gitignore'da),
**yeniden yayımlanmaz**. Bkz. `docs/veri_lisans_karari.md` §4.

## Doldurduktan sonra

```bash
python scripts/ppe_etiket_olc.py
```
""")

    print("\n" + "=" * 86)
    for k, v in kovalar.items():
        print(f"  {k:12s} {len(v):3d} klip")
    print(f"\n  Kontak sayfalari : {os.path.relpath(HEDEF, ROOT)}/<kova>/")
    print(f"  Doldurulacak CSV : {os.path.relpath(csv_yol, ROOT)}")
    print(f"  Yonerge          : {os.path.relpath(HEDEF, ROOT)}/NASIL_ETIKETLENIR.md")
    print("=" * 86)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
