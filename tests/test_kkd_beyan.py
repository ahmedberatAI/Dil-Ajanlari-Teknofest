"""KKD tesis-beyani kapisinin modelsiz, saf birim testleri."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.kkd_beyan import beyanlari_cikar, iddia_karari


fails: list[str] = []


def check(label: str, condition: bool) -> None:
    print(("  [OK]   " if condition else "  [FAIL] ") + label)
    if not condition:
        fails.append(label)


print("=== BEYAN CIKARIMI ===")
bos = beyanlari_cikar(ppe_detection=False, ppe_kits="baret,yelek")
check("ppe_detection kapaliyken varsayilan kit listesi beyan degildir", not bos.kitler)

politika = beyanlari_cikar(
    facility_policy="Baretsiz çalışma | Baret takılı | Yüksek")
check("facility_policy ihlal alani baret zorunlulugudur", politika.kitler == ("baret",))

kural = beyanlari_cikar(
    facility_rules="Üretim alanında reflektif yelek kullanılması zorunludur.")
check("acik tesis kurali yelek zorunlulugudur", kural.kitler == ("yelek",))

fiil_kurali = beyanlari_cikar(
    facility_rules="Baretsiz çalışmak yasaktır; reflektif yelek giymek gerekir.")
check("yasak ve gerekir cekimleri acik zorunluluktur",
      fiil_kurali.kitler == ("baret", "yelek"))

kit = beyanlari_cikar(ppe_detection=True, ppe_kits="baret,yelek")
check("bilerek etkinlestirilen destekli kitler beyandir",
      kit.kitler == ("baret", "yelek"))

negatif = beyanlari_cikar(
    facility_rules="Bu alanda baret zorunlu değildir; reflektif yelek zorunludur.",
    ppe_detection=True,
    ppe_kits="baret")
check("zorunlu degil beyani etkin kiti de fail-closed ezer",
      negatif.kitler == ("yelek",) and negatif.olumsuzlanan_kitler == ("baret",))

celiski = beyanlari_cikar(
    facility_policy="Baretsiz çalışma | Baret takılı | Yüksek",
    facility_rules="Baret zorunluluğu yoktur")
check("kaynaklar arasi celiskide olumsuzluk baskindir",
      not celiski.kitler and celiski.olumsuzlanan_kitler == ("baret",))

yasak = beyanlari_cikar(facility_rules="Bu laboratuvarda baret takmak yasaktır")
check("ekipman kullaniminin yasak olmasi zorunluluk sayilmaz", not yasak.kitler)

liste = beyanlari_cikar(
    facility_rules="Baret, reflektif yelek kullanılması zorunludur")
check("paylasilan yuklemde belirsiz ilk kalem fail-closed kalir", liste.kitler == ("yelek",))

atlanmis = beyanlari_cikar(ppe_detection=True, ppe_kits="baret,eldiven")
check("desteklenmeyen etkin kit beyan uzayina girmez",
      atlanmis.kitler == ("baret",) and atlanmis.atlanan_ppe_kitleri == ("eldiven",))


print("\n=== IDDIA KAPISI ===")
ret = iddia_karari(
    "Personel standart baret yerine bere takıyor",
    ppe_detection=False,
    ppe_kits="baret,yelek")
check("beyansiz baret iddiasi reddedilir",
      not ret.izinli and ret.hukum == "BEYAN_YOK")

kabul = iddia_karari(
    "Personel standart baret yerine bere takıyor",
    facility_policy="Baretsiz çalışma | Baret takılı | Yüksek")
check("beyanli baret ihlali gorsel kapida sinanabilir",
      kabul.izinli and kabul.hukum == "BEYANLI")

yelek = iddia_karari(
    "Çalışan reflektif yelek olmadan, yeleksiz çalışıyor",
    facility_rules="Reflektif yelek kullanımı zorunludur")
check("beyanli yelek ihlali kabul edilir", yelek.izinli)

takmamasi = iddia_karari(
    "Çalışanın baretini takmaması açık bir KKD ihlalidir",
    ppe_detection=True,
    ppe_kits="baret")
check("takmamasi cekimi acik ihlal olarak korunur", takmamasi.izinli)

olmadan = iddia_karari(
    "Çalışan kask, reflektif yelek olmadan üretim alanında bulunuyor",
    ppe_detection=True,
    ppe_kits="baret,yelek")
check("kask ve yelek olmadan cekimi iki beyanli kiti korur",
      olmadan.izinli and olmadan.iddia_kitleri == ("baret", "yelek"))

giymemesi = iddia_karari(
    "Personelin reflektif yeleği giymemesi güvenlik ihlalidir",
    ppe_detection=True,
    ppe_kits="yelek")
check("giymemesi cekimi acik ihlal olarak korunur", giymemesi.izinli)

birlesik = iddia_karari(
    "Personel baret yerine bere takıyor ve eldivensiz çalışıyor",
    facility_policy="Baretsiz çalışma | Baret takılı | Yüksek")
check("desteklenmeyen eldiven birlesik iddianin tamamini reddeder",
      not birlesik.izinli and birlesik.hukum == "DESTEKLENMEYEN_KIT"
      and birlesik.desteklenmeyen_kitler == ("eldiven",))

gozluk = iddia_karari(
    "Koruyucu gözlük ve baret eksik",
    ppe_detection=True,
    ppe_kits="baret")
check("gozluk+baret birlesik iddiasi fail-closed",
      not gozluk.izinli and gozluk.hukum == "DESTEKLENMEYEN_KIT")

gozluk_cekimi = iddia_karari(
    "Çalışanın koruyucu gözlüğü ve bareti eksik",
    ppe_detection=True,
    ppe_kits="baret")
check("cekime girmis desteklenmeyen gozluk de fail-closed",
      not gozluk_cekimi.izinli and gozluk_cekimi.hukum == "DESTEKLENMEYEN_KIT")

iki_kit = iddia_karari(
    "Çalışanda baret ve reflektif yelek yok",
    ppe_detection=True,
    ppe_kits="baret")
check("birlesik destekli iddianin tum kitleri beyanli olmalidir",
      not iki_kit.izinli and iki_kit.eksik_beyanlar == ("yelek",))

uyumlu = iddia_karari(
    "Personelin bareti takılı ve reflektif yeleği mevcut",
    ppe_detection=True,
    ppe_kits="baret,yelek")
check("uyumlu gorunum ihlal olayi degildir",
      not uyumlu.izinli and uyumlu.hukum == "IHLAL_IDDIASI_YOK")

uyumlu_dusme = iddia_karari(
    "Sarı reflektif yelekli kişi yere düştü",
    ppe_detection=True,
    ppe_kits="yelek")
check("uyumlu yelekli kisi dusmesi KKD ihlali degildir",
      not uyumlu_dusme.izinli and uyumlu_dusme.hukum == "IHLAL_IDDIASI_YOK")

genel = iddia_karari(
    "Çalışanda KKD eksikliği var",
    ppe_detection=True,
    ppe_kits="baret")
check("hangi ekipman oldugu belirtilmeyen genel KKD iddiasi reddedilir",
      not genel.izinli and genel.hukum == "IDDIA_KITI_YOK")

negatif_iddia = iddia_karari(
    "Baret eksik değil, personelde baret mevcut",
    ppe_detection=True,
    ppe_kits="baret")
check("olumsuz/uyumlu iddia alarm yetkisi kazanmaz",
      not negatif_iddia.izinli and negatif_iddia.hukum == "IHLAL_IDDIASI_YOK")

check("karar izi ham politika metnini sizdirmaz",
      "Baretsiz çalışma" not in kabul.iz_satiri()
      and "beyanli=baret" in kabul.iz_satiri())


print(f"\nkalan={len(fails)}")
raise SystemExit(1 if fails else 0)
