#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""KUNYE TAMLIGI — davranisi degistiren HER ayar ara-kayit kimligine girmeli.

NEDEN BU TEST VAR: bu kusur bu depoda UC KEZ isledi.
  1. `isg_lens`      kunyede yoktu
  2. `panel_roi`     kunyede yoktu
  3. `yelek_roi_vlm` kunyede yoktu (2026-08-25)

Kusurun sekli her seferinde ayni: ara-kayit dosyasinin adi kunyenin md5'idir.
Kunyeye YAZILMAYAN bir ayar, ACIK ve KAPALI kollarin AYNI ara dosyayi
paylasmasina yol acar; ikinci kosum birincinin satirlarini "tamamlanmis" diye
DEVRALIR ve "acik" diye raporlanan sayilar aslinda KAPALI kolun sayilari olur.
Kosum coker de VERMEZ, hata da vermez — sessizce yanlis olcum uretir.

Kod yorumlari her seferinde uyariyordu; uyari yetmedi. Bu test uyariyi
MEKANIK hale getirir: alan listesi SLOT ve KURAL kataloglarindan TURETILIR,
yani ileride eklenecek her slot/kural OTOMATIK kapsanir.
"""
import importlib
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import tests.taban as taban  # noqa: E402
taban.taban_uygula()

g = k = 0


def c(ad, kosul):
    global g, k
    if kosul:
        g += 1
        print("  ok   " + ad)
    else:
        k += 1
        print("  KALAN " + ad)


def _temizle():
    for m in list(sys.modules):
        if m.startswith("dilajan") or m.startswith("benchmark"):
            del sys.modules[m]


def kimlik(**cevre):
    """Verilen ortamla ara-kayit dosya adini uret."""
    eski = {}
    for a, d in cevre.items():
        eski[a] = os.environ.get(a)
        if d is None:
            os.environ.pop(a, None)
        else:
            os.environ[a] = d
    try:
        _temizle()
        ec = importlib.import_module("benchmark.eval_clips")
        return os.path.basename(ec._ara_kayit_yol())
    finally:
        for a, v in eski.items():
            if v is None:
                os.environ.pop(a, None)
            else:
                os.environ[a] = v
        _temizle()


# --- Davranisi degistiren alanlari KATALOGLARDAN TURET ---
_temizle()
from dilajan import gozlem as G, isg_kural as K  # noqa: E402

ALANLAR = set()
for s in G.SLOT_KATALOG.values():
    for nitelik in ("roi_alani", "fps_alani", "dislanan_gorus_alani",
                    "gorus_esik_alani"):
        ad = getattr(s, nitelik, "")
        if ad:
            ALANLAR.add(ad)
for kr in K.KURALLAR:
    ad = getattr(kr, "esik_alani", "")
    if ad:
        ALANLAR.add(ad)
# katalogdan turemeyen ama davranisi degistiren bayraklar
ALANLAR |= {"isg_slotlari", "slot_guven", "kodlama_normalize", "kodlama_fps",
            "kodlama_bit", "forklift_yuk"}

# Bazi alanlar SAYISAL/BOOL — deneme degeri tipe gore secilir
DENEME = {
    "yol_gorus_esik": "0.5", "panel_koyuluk_esik": "9", "forklift_esik": "5",
    "yol_mesafe_esik": "2", "yol_kodlama_fps": "4", "kodlama_fps": "12",
    "slot_guven": "1", "kodlama_normalize": "0", "kodlama_bit": "1200k",
    "isg_slotlari": "catal_kasa_sayisi", "forklift_yuk": "1",
    "panel_luma_esik": "9",
}

print("=== KUNYE, DAVRANIS DEGISTIREN HER ALANI AYIRT ETMELI ===")
print("  (alan listesi SLOT ve KURAL kataloglarindan TURETILDI: %d alan)"
      % len(ALANLAR))
taban_kimlik = kimlik()
for alan in sorted(ALANLAR):
    cevre_ad = "DILAJAN_" + alan.upper()
    deger = DENEME.get(alan, "0.11,0.22,0.33,0.44")
    yeni = kimlik(**{cevre_ad: deger})
    c("%-24s -> ara-kayit adi DEGISIYOR" % alan, yeni != taban_kimlik)

print()
print("=== KUNYE ALANLARI GERCEKTEN YAZILIYOR MU ===")
_temizle()
ec = importlib.import_module("benchmark.eval_clips")
kn = ec._kosum_kunyesi()
# Bazi alanlar kunyeye UZUNLUK olarak girer (imzalar cok uzun): esleme tablosu
ESANLAM = {"yol_dislanan_gorus": "yol_gorus_imza_uzunluk",
           "panel_gorus_imza": "panel_gorus_imza_uzunluk"}
for alan in sorted(ALANLAR):
    anahtar = ESANLAM.get(alan, alan)
    c("%-24s kunye sozlugunde (%s)" % (alan, anahtar), anahtar in kn)

print()
print("=== AYNI AYAR -> AYNI DOSYA (surdurulebilirlik korunmali) ===")
c("ayni ortam ayni adi uretir", kimlik() == taban_kimlik)

print()
print("gecen=%d  kalan=%d" % (g, k))
sys.exit(1 if k else 0)
