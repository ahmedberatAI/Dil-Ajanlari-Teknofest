"""KURAL SABLONU <-> ISG KALIP tutarliligi.

KUSUR (2026-08-25): sablon metinleri ASCII'lestirilmis Turkce ile yazilmisti
("Yetkisiz mudahale"), `isg_any_match` kaliplari ise gercek Turkce
("yetkisiz müdahale"). Sonuc: DORT sablondan IKISI kendi sinifiyla
ESLESMIYORDU — kural DOGRU ateslese bile olcum onu KACIRMA sayiyordu.
Ayni metinler arayuzde OPERATORE de gosteriliyordu, yani juri bozuk
Turkce goruyordu.

Bu test iki yonlu bagi kilitler:
  1) her sablon KENDI sinifiyla eslesmeli,
  2) BASKA hicbir sinifi tetiklememeli (ozgulluk).
Sablon metni degistirilirse bu test dusen ILK sey olur.
"""
import re
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dilajan import isg_kural as K
import benchmark.labels as L

g = k = 0
def c(ad, kosul):
    global g, k
    if kosul: g += 1; print("  ok  ", ad)
    else: k += 1; print("  FAIL", ad)

# sablonlar cesitli degerlerle render edilir (deger metne girdigi icin)
DEGERLER = [(0, 3), (3, 3), (8, 6), (10, 7)]

print("=== HER SABLON KENDI SINIFIYLA ESLESIR ===")
for kural in K.KURALLAR:
    for d, e in DEGERLER:
        metin = kural.sablon.format(deger=d, esik=e)
        c(f"{kural.kod[:26]:26s} deger={d:2d} -> eslesiyor",
          L.isg_any_match([metin], kural.kod))

print()
print("=== OZGULLUK: BASKA SINIF TETIKLENMEZ ===")
for kural in K.KURALLAR:
    metin = kural.sablon.format(deger=8, esik=3)
    tetik = L.isg_matched_siniflar(metin)
    c(f"{kural.kod[:26]:26s} yalniz kendi sinifi",
      tetik == {kural.kod})

print()
print("=== SABLONLAR GERCEK TURKCE (ASCII'lestirilmemis) ===")
# Turkce'ye ozgu harflerden en az biri her sablonda gecmeli; ayrica
# ASCII'lestirmenin tipik izleri BULUNMAMALI.
TR = set("çğıöşüÇĞİÖŞÜ")
BOZUK = ("mudahale", "kapagi", "acik", "gorul", "asiri", "guvenli",
         "cizgi", "uzaklik", "istiflenmis", "kisi", "yuk", "sinir")
for kural in K.KURALLAR:
    metin = kural.sablon.format(deger=8, esik=3)
    c(f"{kural.kod[:26]:26s} Turkce harf iceriyor", bool(TR & set(metin)))
    # KELIME SINIRI SART: "Yetkisiz" kelimesi ASCII "kisi" dizgesini ICERIR;
    # naif alt-dizge kontrolu yanlis alarm verir (bu testin ilk surumu verdi).
    bulunan = [b for b in BOZUK
               if re.search(r"" + b, metin.lower())]
    c(f"{kural.kod[:26]:26s} ASCII izi yok {bulunan or ''}", not bulunan)

print()
print("=== KURAL KODLARI ISG TAKSONOMISINDE VAR ===")
for kural in K.KURALLAR:
    c(f"{kural.kod[:26]:26s} kalip listesi tanimli",
      bool(L.isg_patterns_for(kural.kod)))

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
