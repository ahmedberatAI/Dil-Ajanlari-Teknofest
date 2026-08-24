#!/usr/bin/env python
"""D42 — INSAN-ONAY KAPISI regresyon kilidi.

    python tests/test_onay_kapisi.py

KUSUR (2026-08-24, olculdu): icra kapisi YALNIZ operatorun mesajina bakiyordu.
BOS gecmiste 'Tamam.' yazildiginda UC MODEL DE (llm-large, llm-fast, router)
6/6 kosumda GERCEK mock fonksiyonlari YURUTTU — ortada onaylanacak oneri yokken.
CHAT_EXECUTE_PROMPT bunu ACIKCA yasakliyordu; ucu de kurali cigneddi.

DERS: insan-onay kapisi MODEL YARGISINA birakilamaz. Model degistirmek hatayi
KAPATMIYOR. Deterministik onkosul sart: gecmiste ASISTAN turu YOKSA icra YOK.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dilajan.chat_agent import is_confirmation, onaylanacak_oneri_var_mi
g = k = 0
def c(ad, kosul, ek=""):
    global g, k
    if kosul: g += 1; print(f"  ok   {ad}")
    else: k += 1; print(f"  FAIL {ad}  {ek}")

print("=== D42: bos gecmiste 'Tamam.' ICRA ETMEMELI ===")
c("is_confirmation('Tamam.') hala True (on-filtre bozulmadi)", is_confirmation("Tamam."))
c("BOS gecmis -> onaylanacak oneri YOK", onaylanacak_oneri_var_mi([]) is False)
c("None gecmis -> oneri YOK", onaylanacak_oneri_var_mi(None) is False)
c("yalniz kullanici turlari -> oneri YOK",
  onaylanacak_oneri_var_mi([{"role": "user", "content": "merhaba"}]) is False)
c("bos icerikli asistan turu -> oneri YOK",
  onaylanacak_oneri_var_mi([{"role": "assistant", "content": "   "}]) is False)
print("\n=== gercek oneri VARSA kapi ACILMALI ===")
c("asistan turu var -> oneri VAR",
  onaylanacak_oneri_var_mi([{"role": "user", "content": "ne oldu?"},
                            {"role": "assistant", "content": "Sağlık ekibi yönlendirmeyi öneririm."}]) is True)
c("eski asistan turu da sayilir",
  onaylanacak_oneri_var_mi([{"role": "assistant", "content": "Öneri X"},
                            {"role": "user", "content": "peki"},
                            {"role": "user", "content": "tamam"}]) is True)
print("\n=== BIRLESIK KAPI (asil davranis) ===")
def kapi(msg, hist): return is_confirmation(msg) and onaylanacak_oneri_var_mi(hist)
c("'Tamam.' + BOS gecmis -> ICRA YOK  [D42 kusuru]", kapi("Tamam.", []) is False)
c("'Tamam.' + oneri var -> ICRA VAR",
  kapi("Tamam.", [{"role": "assistant", "content": "Sağlık ekibi yönlendir."}]) is True)
c("'Gönderme.' + oneri var -> ICRA YOK (olumsuzlama korundu)",
  kapi("Gönderme.", [{"role": "assistant", "content": "Sağlık ekibi yönlendir."}]) is False)
c("'onaylamıyorum' + oneri var -> ICRA YOK",
  kapi("onaylamıyorum", [{"role": "assistant", "content": "Öneri"}]) is False)
print(f"\ngecen={g}  kalan={k}")
sys.exit(1 if k else 0)
