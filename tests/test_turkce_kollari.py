# -*- coding: utf-8 -*-
"""TURKCE URETIM KOLLARI — sevk edilen durum ve ALET saglamligi.

Iki ayri sey korunur:
  1) SEVK DURUMU: iki bayrak da ACIK ve BIRLIKTE acik (ayri acilirsa
     olculmemis yapilandirma olur — Kol 4 tek basina terim oranini
     0,571 -> 0,158 DUSURUYOR).
  2) ALET SAGLAMLIGI: `kanonik_oran_*` sayaci bir kez SESSIZCE kirildi
     (varyant dizgesi kanonigin ALT-DIZGESIydi -> tavan 0,50, esik 0,70
     ulasilamazdi ve saglam bir kol RET aldi). O kusur geri gelmesin.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.tr_dil_kapisi import TERIM, sayaclar          # noqa: E402
from dilajan.config import Settings                           # noqa: E402
from dilajan import prompts                                   # noqa: E402

hata = 0


def kontrol(ad, kosul, ek=""):
    global hata
    if kosul:
        print("  gecti : %s" % ad)
    else:
        hata += 1
        print("  KALDI : %s %s" % (ad, ek))


print("### 1) SEVK DURUMU")
v = Settings()
kontrol("ozet_terim_sozlugu ACIK", v.ozet_terim_sozlugu is True)
kontrol("ozet_uslup_kisiti ACIK", v.ozet_uslup_kisiti is True)
kontrol("IKISI BIRDEN ayni durumda (etkilesim)",
        v.ozet_terim_sozlugu == v.ozet_uslup_kisiti,
        "-> yalniz biri acik: OLCULMEMIS yapilandirma")

print("### 2) PROMPT EKLERI VAR ve TESPIT IDDIASI EKLEMIYOR")
for ad in ("OZET_TERIM_SOZLUGU", "OZET_USLUP_KISITI"):
    kontrol("%s tanimli" % ad, bool(getattr(prompts, ad, "").strip()))
# Kolun ISI adlandirma/uslup; MODELE YENI TEHLIKE ARATTIRAN fiil olmamali
# (facility_rules / isg_lens bu yuzden REDDEDILDI — esik dusuruyorlardi).
# KELIME SINIRIYLA aranir: alt-dizge esleme Turkce'de YANLIS POZITIF verir
# (yonelme eki "-lara " -> "Talimatlara serh" icinde "ara " goruluyordu).
YASAK = [r"ara", r"tara", r"kontrol et", r"incele",
         r"tespit et", r"araştır", r"gözden geçir", r"dikkatle bak"]
for ad in ("OZET_TERIM_SOZLUGU", "OZET_USLUP_KISITI"):
    m = getattr(prompts, ad).lower()
    kotu = [y for y in YASAK if re.search(y, m)]
    kontrol("%s tehlike-arattirma fiili YOK" % ad, not kotu, str(kotu))
kontrol("terim ekinde acik uyari var",
        "yeni bir tespit ekleme" in prompts.OZET_TERIM_SOZLUGU)

print("### 3) ALET SAGLAMLIGI — kanonik sayaci alt-dizgeyi CIFT SAYMAMALI")
# Bu kusur veriye BAKMADAN kanitlanabilir: varyant kanonigin alt-dizgesiyse
# duz str.count her kanonik gecisi varyant da sayar ve tavan 0,50'de kalir.
for ad, tk in TERIM.items():
    for kan in tk["kanonik"]:
        d = sayaclar([kan + " gorulmustur."], [], [])
        kontrol("%-10s yalniz KANONIK -> 1,000 (%r)" % (ad, kan[:28]),
                d["kanonik_oran_" + ad] == 1.0,
                "-> %s" % d["kanonik_oran_" + ad])
    for var in tk["varyant"]:
        d = sayaclar([var + " gorulmustur."], [], [])
        if d["kanonik_oran_" + ad] is None:
            continue
        kontrol("%-10s yalniz VARYANT -> 0,000 (%r)" % (ad, var[:28]),
                d["kanonik_oran_" + ad] == 0.0,
                "-> %s" % d["kanonik_oran_" + ad])

print("### 4) K2 — kapaliyken prompt BAYT OZDES (kollarin geri donus yolu)")
from dilajan.agent import graph as _G                          # noqa: E402
_ev = [_G.Event(time="00:03", event="Forklift asiri yuk tasiyor",
                severity="Yüksek", category="Güvenlik")]


def _instr(terim, uslup):
    x = prompts.DECISION_SUPPORT_INSTRUCTION.format(
        events_block=_G._events_block_scened(_ev, []), duration="00:10")
    if terim:
        x += prompts.OZET_TERIM_SOZLUGU
    if uslup:
        x += prompts.OZET_USLUP_KISITI
    return x


kontrol("ikisi de KAPALI -> ozellik-oncesi metinle BIREBIR AYNI",
        _instr(False, False) == prompts.DECISION_SUPPORT_INSTRUCTION.format(
            events_block=_G._events_block_scened(_ev, []), duration="00:10"))
kontrol("ikisi de ACIK -> metin UZUYOR (ek gercekten bagli)",
        len(_instr(True, True)) > len(_instr(False, False)))
kontrol("ekler yalnizca SONA ekleniyor (mevcut metin degismiyor)",
        _instr(True, True).startswith(_instr(False, False)))

print("### 5) `tekrar_4gram_orani` KORPUS-BAGIMLI oldugu BELGELENMIS olmali")
import io as _io                                              # noqa: E402
_k = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_s = _io.open(os.path.join(_k, "benchmark/tr_dil_kapisi.py"), encoding="utf-8").read()
kontrol("korpus-bagimlilik uyarisi kaynakta", "KORPUS BOYUTUNA" in _s)

print()
print("SONUC: %s (%d hata)" % ("GECTI" if hata == 0 else "KALDI", hata))
sys.exit(1 if hata else 0)
