#!/usr/bin/env python
"""D36 — TURKCE BUYUK-I kusuru regresyon kilidi.

    python tests/test_tr_lower.py       # cikis kodu 0 = hepsi gecti

KUSUR: Python'un str.lower()'i Turkce degildir.
    "İşçi".lower() -> "i" + U+0307 (birlesik nokta) + "şçi"
Bu, regex'teki duz "işçi" kalibiyla ESLESMEZ -> model cumleye "İşçi ..." diye
basladiginda _PERSON_RE kisiyi GORMEZ.

OLCULDU (6 arsiv, 267 olay metni): %13,5'i (36 olay) etkileniyordu. Aralarinda
"İşçi zemine düşmüş ve hareketsiz kalmış" gibi tam da poz-dogrulamasi tetiklemesi
gereken olaylar vardi.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.agent.graph import (_apply_pose_fall_verdict, _calibrate_severity, _is_person_fall_event,  # noqa: E402
                                 _PERSON_RE, _tr_lower)
from dilajan.schema import Event, EventCategory, Severity  # noqa: E402

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


print("=== _tr_lower temel davranis ===")
check("İ -> i (birlesik nokta YOK)", _tr_lower("İşçi") == "işçi",
      f"-> {_tr_lower('İşçi')!r} kod={[hex(ord(c)) for c in _tr_lower('İşçi')]}")
check("I -> ı (noktasiz)", _tr_lower("Islak") == "ıslak", f"-> {_tr_lower('Islak')!r}")
check("zaten kucuk metin degismez", _tr_lower("işçi yere düştü") == "işçi yere düştü")
check("bos girdi guvenli", _tr_lower("") == "" and _tr_lower(None or "") == "")
check("U+0307 kalintisi temizlenir", "̇" not in _tr_lower("İstismar"))
# Duz .lower() ile FARK olmali — yoksa test bir sey kanitlamiyor
check("duz .lower()'dan GERCEKTEN farkli", _tr_lower("İşçi") != "İşçi".lower(),
      "fark yoksa bu test hicbir sey kanitlamaz")

print("\n=== _PERSON_RE artik cumle basi 'İşçi'yi goruyor ===")
for metin in ("İşçi yere düştü",
              "İşçiler arasında fiziksel temas",
              "İşçi zemine düşmüş ve hareketsiz kalmış"):
    check(f"PERSON_RE: {metin[:38]!r}", bool(_PERSON_RE.search(_tr_lower(metin))))

print("\n=== _is_person_fall_event (poz dogrulamasinin kapisi) ===")
for metin in ("İşçi yere düştü",
              "İşçi zemine düşmüş ve hareketsiz kalmış",
              "İşçi ani şekilde devrildi ve yere düştü"):
    check(f"dusme olayi taniniyor: {metin[:38]!r}", _is_person_fall_event(metin))

# Kucuk harfli hali ZATEN calisiyordu — bozulmadigini dogrula (gerileme kilidi)
for metin in ("işçi yere düştü", "Kişi yere düştü", "personel yere yığıldı"):
    check(f"eskiden calisan hala calisiyor: {metin[:30]!r}", _is_person_fall_event(metin))

print("\n=== YANLIS POZITIF olmamali ===")
for metin in ("Forklift yük taşıyor", "Zeminde metal halka duruyor"):
    check(f"kisi-dusmesi DEGIL: {metin[:34]!r}", not _is_person_fall_event(metin))

print("\n=== NESNE-vs-KISI mantigi: dusmus KISI severity YUKSELIR ===")
# "dusmus NESNE kritik degil" kurali, kisiyi nesne sanarsa yanlis calisir.
kisi = _calibrate_severity("İşçi yere düştü ve hareketsiz kaldı", Severity.DUSUK)
nesne = _calibrate_severity("Yere düşmüş metal malzeme", Severity.DUSUK)
check("İ ile baslayan KISI dusmesi severity YUKSELTIYOR",
      kisi != Severity.DUSUK, f"-> {kisi}")
check("NESNE dusmesi severity YUKSELTMIYOR (kural korundu)",
      nesne == Severity.DUSUK, f"-> {nesne}")

print("\n=== POZ REDDI: reddedilen dusme reason katmanina TASINMAZ ===")
olaylar = [
    Event(time="00:00", event="Kişinin zemindeki engeli fark edemeyip sert bir şekilde yere düşmesi",
          severity=Severity.YUKSEK, category=EventCategory.SAGLIK),
    Event(time="00:00", event="Pano kapağı açık bırakılmış",
          severity=Severity.YUKSEK, category=EventCategory.GUVENLIK),
    Event(time="00:02", event="Mücadele sırasında iki kişinin yere yığılması",
          severity=Severity.YUKSEK, category=EventCategory.GUVENLIK),
]
filtreli, silinen = _apply_pose_fall_verdict(olaylar, "REJECT")
check("REJECT saf kisi-dusme iddiasini siliyor", silinen == 1 and len(filtreli) == 2,
      f"silinen={silinen} kalan={len(filtreli)}")
check("REJECT diger olayi koruyor", filtreli[0].event == "Pano kapağı açık bırakılmış")
check("REJECT siddet baglamli dusmeyi koruyor", "Mücadele" in filtreli[1].event)
korunan, silinen2 = _apply_pose_fall_verdict(olaylar, "ABSTAIN")
check("ABSTAIN fail-open: olaylari koruyor", silinen2 == 0 and len(korunan) == 3,
      f"silinen={silinen2} kalan={len(korunan)}")

print(f"\ngecen={_gecti}  kalan={_kaldi}")
sys.exit(1 if _kaldi else 0)
