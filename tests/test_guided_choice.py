#!/usr/bin/env python
"""D40 — KISITLI KOD COZME regresyon kilidi.

    python tests/test_guided_choice.py            # sunucu YOKSA da calisir (statik denetim)
    python tests/test_guided_choice.py --canli    # vLLM ayaktaysa GERCEK kisiti da sinar

KUSUR (2026-08-19, olculdu): vLLM 0.23 `extra_body` icindeki eski `guided_choice`
alanini SESSIZCE yok sayiyor — hata da uyari da vermiyor, serbest metin donduruyor.
Ayni isteğin kisit ACIK ve KAPALI ciktilari BIREBIR AYNI cikti.

    guided_choice               -> serbest metin  (ATIL)
    guided_decoding.choice      -> serbest metin  (ATIL)
    response_format json_schema -> '"X"'          (tirnakli, kirli)
    structured_outputs.choice   -> 'X'            <- DOGRUSU

ETKISI BUYUKTU: bu alani kullanan TUM olcumler kisitsiz kosmustu —
  - D37 mentor prompt mimarisi probu ("kapali secenek listesi olculdu -> RET")
  - D33 pano probu ("guided_choice ile 20/20 KAPALI dedi")
  - iSafetyBench MCQ olcumu (ustelik cevabi ILK KARAKTERDEN okuyor: serbest
    metin "Bu videoda..." diye baslarsa 'B' secenegi olarak AYRISTIRILIR)

Bu test iki sey yapar:
  1) STATIK: hicbir yerde ham `extra_body={"guided_choice": ...}` kalmadigini,
     ve `llm_client`'in dogru alani gonderdigini dogrular. Sunucu gerekmez.
  2) CANLI (--canli): ayni istegi kisit ACIK/KAPALI kosar; ACIK olan cikti
     MUTLAKA listeden biri olmali, KAPALI olan olmamali (aksi halde kisit
     yine atil demektir).
"""
import argparse
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_gecti = 0
_kaldi = 0


def check(ad, kosul, ayrinti=""):
    global _gecti, _kaldi
    if kosul:
        _gecti += 1
        print(f"  ok   {ad}")
    else:
        _kaldi += 1
        print(f"  FAIL {ad}  {ayrinti}")


def py_dosyalari():
    for kok, dizinler, dosyalar in os.walk(KOK):
        dizinler[:] = [d for d in dizinler
                       if d not in {"data", ".git", "__pycache__", ".venv", "paylasim"}]
        for f in dosyalar:
            # bu testin KENDISI deseni docstring'inde tasiyor -> haric
            if f.endswith(".py") and f != os.path.basename(__file__):
                yield os.path.join(kok, f)


print("=== STATIK: atil alan hicbir yerde kalmamali ===")
ATIL = re.compile(r'extra_body\s*=\s*\{\s*["\']guided_choice["\']')
bulunan = []
for p in py_dosyalari():
    try:
        s = io.open(p, encoding="utf-8").read()
    except Exception:
        continue
    if ATIL.search(s):
        bulunan.append(os.path.relpath(p, KOK))
check("ham extra_body={'guided_choice': ...} kalmadi", not bulunan,
      f"-> {bulunan}")

print("\n=== STATIK: llm_client dogru alani gonderiyor ===")
lc = io.open(os.path.join(KOK, "dilajan/llm_client.py"), encoding="utf-8").read()
check("structured_outputs kullaniliyor", '"structured_outputs"' in lc)
check("choice anahtari var", '"choice"' in lc)
check("atil alan artik gonderilmiyor",
      'ek["guided_choice"]' not in lc)

print("\n=== STATIK: kusur belgelenmis (gelecekte tekrar edilmesin) ===")
check("llm_client'ta kusur notu var",
      "SESSIZCE" in lc or "sessizce" in lc.lower())

if "--canli" in sys.argv:
    print("\n=== CANLI: kisit GERCEKTEN baglıyor mu ===")
    SEC = ["ELMA", "ARMUT", "KAYISI"]
    try:
        from dilajan.llm_client import VLMClient
        i = VLMClient()
        soru = [{"role": "user",
                 "content": "Turkiye'nin baskenti neresidir? Uzun uzun anlat."}]
        acik = (i.chat(soru, max_tokens=40, temperature=0.0, guided_choice=SEC) or "").strip()
        kapali = (i.chat(soru, max_tokens=40, temperature=0.0) or "").strip()
        check("KISIT ACIK -> cikti listeden biri", acik in SEC, f"-> {acik!r}")
        check("KISIT KAPALI -> cikti listeden DEGIL", kapali not in SEC,
              f"-> {kapali[:50]!r}")
        # Asil kilit: ikisi AYNI ise kisit atildir (kusurun imzasi buydu)
        check("acik ve kapali ciktilar FARKLI (kisit atil degil)", acik != kapali,
              "-> BIREBIR AYNI = kisit yine calismiyor")
    except Exception as e:
        print(f"  ATLA canli test: sunucuya ulasilamadi ({type(e).__name__})")
else:
    print("\n  (canli test atlandi — vLLM ayaktayken: python tests/test_guided_choice.py --canli)")

print(f"\ngecen={_gecti}  kalan={_kaldi}")
sys.exit(1 if _kaldi else 0)
