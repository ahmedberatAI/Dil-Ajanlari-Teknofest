#!/usr/bin/env python
"""PROMPTLARIN KENDI TURKCESI — bozuk yazim GERI GELEMEZ.

OLCULDU (2026-08-25, 855 ozet + 1385 olay metni, iki arsiv):
Ciktilarin %48,8'i ASCII-lestirilmis Turkce iceriyor. Sebep model degil
PROMPT: `CHAT_SYSTEM`in ORNEKLER blogunda birebir su yaziyordu —
   "yalnizca video analizi ... icin buradayim. Analizle ilgili nasil
    yardimci olabilirim?"
Model bu ornegi YAZIM HATASIYLA BIRLIKTE kopyaliyor; ayni kalip arsivlenmis
diyalog kosumlarinda 26 kez gecti.

ONEMLI AYRIM — `gozlem.py` slot sorulari BILEREK ASCII'dir ve bu test onlara
DOKUNMAZ: slot sorularini gercek Turkceye cevirmek OLCULDU ve REDDEDILDI
(yelek ciftinde MCC -0,199). O metinler operatore GITMEZ; sartnamenin
puanladigi Turkce ANLATI duzleminde uretilir.

KOD YORUMLARI da ASCII kalir (depo kurali). Bu test yalnizca MODELE/OPERATORE
giden DIZE icerigini denetler.

TUZAK: 'i' (U+0131) katlandiginda 'i' olur — yani KATLAYARAK bakan bir
denetci DOGRU yazimi da bozuk sanir. Bu test HAM metne bakar.
"""
import os, sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import tests.taban as taban  # noqa: E402
taban.taban_uygula()

from dilajan import prompts as P  # noqa: E402

g = k = 0
def c(ad, kosul):
    global g, k
    if kosul: g += 1; print(f"  ok   {ad}")
    else: k += 1; print(f"  KALAN {ad}")

# BOZUK bicimler: Turkce'de 'i' olmasi gerekirken 'i' yazilmis
BOZUK = [
    "yalnizca", "Yalnizca", "kisa", "nasil", "yardimci", "yardımci",
    "buradayim", "hizli", "saglik", "sağlik", "saygili", "talimatlari",
    "talimatlarim", "onaylarsaniz", "korunmasini", "hatirlat",
    "hatırlatirsin", "cikarmani", "çikarmani", "aynisini", "olasi",
    "alanina", "açikça", "kisaca", "adimlarina", "almasina", "mesajindaki",
    "çağirma", "alakasiz", "dişinda", "kapsamim", "kayittan", "kalmazsin",
    "yaparsin", "insansi", "kaydindaki", "dayanina", "talimatini",
]

print("=== CHAT_SYSTEM: OPERATORE GIDEN METIN TEMIZ OLMALI ===")
bulunan = {b: P.CHAT_SYSTEM.count(b) for b in BOZUK if P.CHAT_SYSTEM.count(b)}
c("CHAT_SYSTEM'de bozuk yazim YOK (bulunan: %s)" % (bulunan or "-"),
  not bulunan)

print("=== ORNEKLER BLOGU — model BUNU birebir kopyaliyor ===")
c("'nasıl yardımcı' DOGRU yazilmis", "nasıl yardımcı" in P.CHAT_SYSTEM)
c("'buradayım' DOGRU yazilmis", "buradayım" in P.CHAT_SYSTEM)
c("'yalnızca' DOGRU yazilmis", "yalnızca" in P.CHAT_SYSTEM)
c("eski bozuk kalip ARTIK YOK", "nasil yardimci" not in P.CHAT_SYSTEM)

print("=== ANLAM DEGISMEDI (davranis kurallari yerinde) ===")
for parca in ("GERÇEKLİK", "İNİSİYATİF", "GÖREVE BAĞLILIK", "ÜSLUP",
              "ANALİZ BAĞLAMI", "{context}"):
    c("CHAT_SYSTEM hala '%s' iceriyor" % parca, parca in P.CHAT_SYSTEM)

print("=== SLOT SORULARI ASCII KALMALI (olculmus karar, -0,199) ===")
from dilajan import gozlem as G  # noqa: E402
c("slot sorulari hala ASCII (yelek)",
  not any(ch in G.SLOT_YELEK.soru for ch in "ışğüöçİŞĞÜÖÇ"))
c("GOZLEM_SISTEM hala ASCII",
  not any(ch in G.GOZLEM_SISTEM for ch in "ışğüöçİŞĞÜÖÇ"))

print("=== SAYAC ARACI VAR ===")
c("benchmark/tr_dil_kapisi.py mevcut",
  os.path.exists(os.path.join(KOK, "benchmark", "tr_dil_kapisi.py")))

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
