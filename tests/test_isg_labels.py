#!/usr/bin/env python
"""ISG taksonomisi (benchmark/labels.py D33 bolumu) + benchmark/isg_rescore.py
birim testleri. GPU/vLLM/model/pytest GEREKTIRMEZ.

    python tests/test_isg_labels.py     # cikis kodu 0 = hepsi gecti

YONTEM: beklenen degerler KODDAN DEGIL, sinif tanimindan (data/industrial/CLASSES.md,
data/eval_defense/MANIFEST.json) ve elle yazilmis orneklerden gelir.

KAPSAM
  1  TAKSONOMI BUTUNLUGU : 8 sinif, class0-7, 4 guvensiz + 4 guvenli; dizin adlari
                           data/eval_defense'teki GERCEK klasorlerle birebir
  2  YOL -> SINIF         : alt klasorden ince taneli etiket cikarma; bilinmeyen -> None
  3  KALIP ESLESME        : her guvensiz sinif icin pozitif + negatif ornekler
  4  GENERIC KOK KILIDI   : D28 dersi — yalin "forklift"/"müdahale"/"yol" TEK BASINA
                            tetiklememeli (bu tesisin her klibinde geciyorlar)
  5  OLUMSUZLAMA KAPISI   : "... gozlenmedi" eslesmeyi IPTAL etmeli
  6  TAKSONOMI HIZALAMASI : her sinifin kabul kumesi var; ayirt edici kume = kabul
                            eksi generic; generic kume kabul kumesini BOSALTMAMALI
  7  OZGULLUK             : isg_matched_siniflar YANLIS sinifi da doner (olcum var)
  8  K2/K4 GERILEME       : ISG eklemesi ESKI sozlugu/eslestiriciyi DEGISTIRMEDI
  9  GUVENLI SINIF        : kalibi yok -> isg_match her zaman False; puanlama
                            "guvensiz olay uretme" uzerinden
 10  GERCEK VERI          : arsiv kosusunda class2 sozcuksel skoru 0 ve bunun sebebi
                            metinde 'pano/panel/kapak' kelimesinin HIC gecmemesi
                            (yani ESLESTIRICI HATASI DEGIL, gercek algi bosluğu)
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.isg_rescore import dosyayi_skorla  # noqa: E402
from benchmark.labels import (  # noqa: E402
    CATEGORY_EXPECT, CATEGORY_PATTERNS, ISG_GENERIC_KATEGORILER, ISG_OPERASYONEL_KABUL,
    ISG_SINIFLAR, KAPSAM, isg_guvensiz, isg_match, isg_matched_siniflar,
    isg_operasyonel_kabul, isg_patterns_for, isg_sinif_from_path, loose_match,
    match_category, row_text, tr_lower,
)

_FAILURES: list = []
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Gercek-veri testinin dayandigi ARSIV dosyasi (26 Tem, facility_rules ACIK, n=200).
ARSIV = os.path.join(ROOT, "benchmark", "results", "eval_20260726_171601.json")


def check(kosul: bool, mesaj: str) -> None:
    print(("  [OK]   " if kosul else "  [HATA] ") + mesaj)
    if not kosul:
        _FAILURES.append(mesaj)


# ===========================================================================
def test_1_taksonomi_butunlugu() -> None:
    """8 sinif, class0-7, 4+4. Dizin adlari GERCEK klasorlerle birebir olmali."""
    print("TEST 1 — taksonomi butunlugu")
    kodlar = sorted(v["kod"] for v in ISG_SINIFLAR.values())
    check(kodlar == [f"class{i}" for i in range(8)],
          f"8 sinif ve kodlar class0..class7 ({kodlar})")

    guvensiz = {s for s in ISG_SINIFLAR if isg_guvensiz(s)}
    guvenli = set(ISG_SINIFLAR) - guvensiz
    check(len(guvensiz) == 4 and len(guvenli) == 4,
          f"4 GUVENSIZ (class0-3) + 4 GUVENLI (class4-7) — {len(guvensiz)}+{len(guvenli)}")
    # MANIFEST.json'daki eslemeyle karsilastir: class0-3 = Anomali, class4-7 = Normal
    for s, v in ISG_SINIFLAR.items():
        beklenen = int(v["kod"].replace("class", "")) <= 3
        check(v["guvensiz"] == beklenen,
              f"{v['kod']} {s}: guvensiz={v['guvensiz']} (MANIFEST beklentisi {beklenen})")

    # Dizin adlari diskteki GERCEK klasorlerle ayni mi? (set yoksa test ATLANIR)
    kok = os.path.join(ROOT, "data", "eval_defense")
    if os.path.isdir(kok):
        diskte = set()
        for ust in ("Anomali", "Normal"):
            p = os.path.join(kok, ust)
            if os.path.isdir(p):
                diskte |= {d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))}
        check(diskte == set(ISG_SINIFLAR),
              f"dizin adlari data/eval_defense ile BIREBIR (fark: "
              f"{diskte ^ set(ISG_SINIFLAR) or 'yok'})")
    else:
        print("  [ATLA] data/eval_defense yok — dizin adi karsilastirmasi atlandi")


# ===========================================================================
def test_2_yol_cozumleme() -> None:
    """Alt klasorden ince taneli etiket; bilinmeyen yol -> None (uydurma YOK)."""
    print("TEST 2 — yol -> ISG sinifi")
    check(isg_sinif_from_path(
        "data/eval_defense/Anomali/Opened_Panel_Cover/2_te1.mp4") == "Opened_Panel_Cover",
        "ic ice klasorden dogru sinif")
    check(isg_sinif_from_path(
        "data\\eval_defense\\Normal\\Safe_Walkway\\4_tr9.mp4") == "Safe_Walkway",
        "ters bolu (Windows) yollari da cozuluyor")
    check(isg_sinif_from_path("data/eval_holdout/Fighting/x.mp4") is None,
          "ISG olmayan yol -> None (UYDURMA etiket uretilmiyor)")
    check(isg_sinif_from_path("Safe_Walkway.mp4") is None,
          "DOSYA adi sinif adi olsa bile klasor degil -> None")

    # ASIL HAVUZ `data/industrial` ham class0..class7 adlarini kullanir (§6.4)
    check(isg_sinif_from_path("data/industrial/class2/2_te1.mp4") == "Opened_Panel_Cover",
          "data/industrial 'class2' -> Opened_Panel_Cover (CLASSES.md eslemesi)")
    check(isg_sinif_from_path("data/industrial/class7/7_tr3.mp4") == "Safe_Carrying",
          "data/industrial 'class7' -> Safe_Carrying")
    # Esleme CLASSES.md ile tutarli mi — kod tablosundan TURETILIYOR, elle yazilmiyor
    for kod, beklenen in (("class0", "Safe_Walkway_Violation"),
                          ("class1", "Unauthorized_Intervention"),
                          ("class3", "Carrying_Overload_with_Forklift"),
                          ("class4", "Safe_Walkway"),
                          ("class5", "Authorized_Intervention"),
                          ("class6", "Closed_Panel_Cover")):
        check(isg_sinif_from_path(f"data/industrial/{kod}/x.mp4") == beklenen,
              f"{kod} -> {beklenen}")


# ===========================================================================
def test_3_kalip_eslesme() -> None:
    """Her guvensiz sinif icin pozitif + negatif ornekler (elle yazildi)."""
    print("TEST 3 — kalip eslesme")
    ornekler = [
        ("Safe_Walkway_Violation", "İşçi güvenlik yolu dışında makinelerin yakınından geçiyor", True),
        ("Safe_Walkway_Violation", "İşçi yürüyüş yolunun dışına çıktı", True),
        ("Safe_Walkway_Violation", "Güvenlik çizgisi dışında hızla ilerliyor", True),
        ("Safe_Walkway_Violation", "Yaya geçidi ihlali var", True),
        ("Safe_Walkway_Violation", "Forklift depoda yük indiriyor", False),
        ("Unauthorized_Intervention", "Yetkisiz kişi makineye müdahale ediyor", True),
        ("Unauthorized_Intervention", "İşçi kontrol paneline eliyle müdahale ediyor", True),
        ("Unauthorized_Intervention", "Yetkisiz erişim tespit edildi", True),
        ("Unauthorized_Intervention", "Sağlık ekibi hastaya müdahale ediyor", False),
        ("Opened_Panel_Cover", "Elektrik panosunun kapağı açık bırakılmış", True),
        ("Opened_Panel_Cover", "Pano kapağı açık duruyor", True),
        ("Opened_Panel_Cover", "İşçi koridorda yürüyor", False),
        ("Carrying_Overload_with_Forklift", "Forklift aşırı yük taşıyor", True),
        ("Carrying_Overload_with_Forklift", "Yük dengesiz ve devrilme riski var", True),
        ("Carrying_Overload_with_Forklift", "İşçi panoya bakıyor", False),
    ]
    for sinif, metin, beklenen in ornekler:
        check(isg_match(metin, sinif) == beklenen,
              f"{ISG_SINIFLAR[sinif]['kod']} bekl={beklenen!s:5s}  {metin[:56]!r}")


# ===========================================================================
def test_4_generic_kok_kilidi() -> None:
    """D28 dersi: bu tesisin HER klibinde gecen yalin kokler tetiklememeli.

    "forklift" tek basina ihlal DEGIL (class7 Safe_Carrying da forklift icerir);
    "müdahale" saglik/guvenlik mudahalesinde de geciyor; "yol"/"geç" her cumlede.
    Bu testler kalip listesi ILERIDE GENISLETILIRSE sessizce bozulmayi engeller.
    """
    print("TEST 4 — generic kok kilidi (D28 dersi)")
    check(not isg_match("Forklift koridorda ilerliyor", "Carrying_Overload_with_Forklift"),
          "yalin 'forklift' class3'u TEK BASINA tetiklemiyor")
    check(not isg_match("Teknisyen ekipmana müdahale ediyor", "Unauthorized_Intervention")
          or "ekipmana müdahale" in " ".join(isg_patterns_for("Unauthorized_Intervention")),
          "'müdahale' yalnizca YETKISIZ/nesne-baglantili kaliplarla tetikleniyor")
    check(not isg_match("İşçi yolunda ilerliyor", "Safe_Walkway_Violation"),
          "yalin 'yol' class0'i TEK BASINA tetiklemiyor")
    check(not isg_match("Kişi kameranın önünden geçiyor", "Safe_Walkway_Violation"),
          "yalin 'geç' class0'i TEK BASINA tetiklemiyor")
    # Kalip listelerinde yalin generic kok BULUNMAMALI (tasarim kilidi)
    for sinif, yasak in (("Carrying_Overload_with_Forklift", "forklift"),
                         ("Unauthorized_Intervention", "müdahale"),
                         ("Safe_Walkway_Violation", "yol"),
                         ("Safe_Walkway_Violation", "geç")):
        check(yasak not in isg_patterns_for(sinif),
              f"{ISG_SINIFLAR[sinif]['kod']} kalip listesinde yalin {yasak!r} YOK")


# ===========================================================================
def test_5_olumsuzlama_kapisi() -> None:
    """'... gozlenmedi/tespit edilmedi' eslesmeyi IPTAL etmeli (D28 kapisi)."""
    print("TEST 5 — olumsuzlama kapisi")
    check(not isg_match("Açık pano kapağı gözlenmedi", "Opened_Panel_Cover"),
          "'açık pano kapağı gözlenmedi' -> ESLESMEZ")
    check(not isg_match("Aşırı yük tespit edilmedi", "Carrying_Overload_with_Forklift"),
          "'aşırı yük tespit edilmedi' -> ESLESMEZ")
    check(isg_match("Aşırı yük var, ancak kimse yaralanmadı",
                    "Carrying_Overload_with_Forklift"),
          "olumsuzlama YALNIZ kendi cumleciginde — 'yaralanmadı' ihlali IPTAL ETMEZ")


# ===========================================================================
def test_6_taksonomi_hizalamasi() -> None:
    """Her sinifin kabul kumesi var; ayirt edici kume = kabul eksi generic."""
    print("TEST 6 — taksonomi hizalamasi (EventCategory)")
    from dilajan.schema import EventCategory  # gec ithal: torch/av CEKMEZ

    gecerli = {e.value for e in EventCategory}
    check(set(ISG_OPERASYONEL_KABUL) == set(ISG_SINIFLAR),
          "her ISG sinifinin bir kabul kumesi TANIMLI")
    for sinif, kabul in ISG_OPERASYONEL_KABUL.items():
        check(kabul <= gecerli,
              f"{ISG_SINIFLAR[sinif]['kod']} kabul kumesi EventCategory icinde "
              f"(kacak: {kabul - gecerli or 'yok'})")
        ae = isg_operasyonel_kabul(sinif, ayirt_edici=True)
        check(ae == kabul - ISG_GENERIC_KATEGORILER,
              f"{ISG_SINIFLAR[sinif]['kod']} ayirt edici kume = kabul - generic")
        if isg_guvensiz(sinif):
            check(len(ae) > 0,
                  f"{ISG_SINIFLAR[sinif]['kod']} generic cikarilinca kabul kumesi "
                  f"BOSALMIYOR (aksi halde ayirt edici olcum tanimsiz olur)")
    # Guvenli siniflarin dogru cevabi "Normal"
    for sinif in ISG_SINIFLAR:
        if not isg_guvensiz(sinif):
            check(ISG_OPERASYONEL_KABUL[sinif] == {"Normal"},
                  f"{ISG_SINIFLAR[sinif]['kod']} (GUVENLI) kabul kumesi = {{Normal}}")
    check("Anomali" in ISG_GENERIC_KATEGORILER,
          "'Anomali' GENERIC sayiliyor — dort guvensiz sinifin da kabul kumesinde")


# ===========================================================================
def test_7_ozgulluk() -> None:
    """isg_matched_siniflar YANLIS sinifi da dondurmeli (ozgulluk olculebilsin)."""
    print("TEST 7 — ozgulluk olcusu")
    metin = "İşçi güvenlik yolu dışında yürüyor ve forklift aşırı yük taşıyor"
    tetik = isg_matched_siniflar(metin)
    check("Safe_Walkway_Violation" in tetik and "Carrying_Overload_with_Forklift" in tetik,
          f"iki ihlali de iceren metin IKI sinif tetikliyor ({sorted(tetik)})")
    check(len(isg_matched_siniflar("Ortamda olagan faaliyet suruyor")) == 0,
          "notr metin HICBIR sinifi tetiklemiyor")
    # Guvenli siniflar kalibi olmadigi icin ASLA tetiklenmez
    check(not any(not isg_guvensiz(s) for s in isg_matched_siniflar(metin)),
          "GUVENLI siniflar hicbir zaman tetiklenmiyor (kalibi yok)")


# ===========================================================================
def test_8_k2_k4_gerileme() -> None:
    """ISG eklemesi ESKI sozlugu/eslestiriciyi DEGISTIRMEDI (K2/K4)."""
    print("TEST 8 — K2/K4 gerileme kilidi")
    ucf = ["RoadAccidents", "Explosion", "Fighting", "Assault", "Abuse",
           "Burglary", "Shooting", "Vandalism"]
    check(all(c in CATEGORY_EXPECT for c in ucf),
          "UCF kategorileri SILINMEDI — arsiv kosulari yeniden skorlanabilir")
    check(all(c in CATEGORY_PATTERNS for c in ucf),
          "UCF kaliplari da duruyor")
    check(CATEGORY_EXPECT["Anomali"][1] is True and CATEGORY_EXPECT["Normal"][1] is False,
          "kaba ikili etiketler (Anomali/Normal) DEGISMEDI")
    # Eski eslestiriciler aynen calisiyor
    check(match_category("Yerde hareketsiz bir kişi var", "Fall"),
          "match_category (D28 kurali) hala calisiyor")
    check(loose_match("kırmızı sıvı", "Burglary"),
          "loose_match KASITLI KUSURU koruyor ('kırmızı' -> 'kır') — arsiv uyumu")
    # Kapsam etiketleri: UCF arsiv, ISG kapsamda
    check(all(KAPSAM.get(c) == "arsiv_ucf" for c in ucf),
          "UCF kategorileri KAPSAM'da 'arsiv_ucf' isaretli")
    check(KAPSAM.get("Anomali") == "isg_ikili" and KAPSAM.get("Fire") == "isg_senaryo",
          "ISG kategorileri kapsam etiketli")


# ===========================================================================
def test_9_guvenli_sinif_puanlama() -> None:
    """Guvenli siniflarin kalibi YOK -> isg_match her zaman False."""
    print("TEST 9 — guvenli sinif puanlamasi")
    for sinif in ISG_SINIFLAR:
        if isg_guvensiz(sinif):
            continue
        check(isg_patterns_for(sinif) == [],
              f"{ISG_SINIFLAR[sinif]['kod']} ({sinif}) kalip listesi BOS")
        check(not isg_match("Herhangi bir metin, aşırı yük, pano kapağı açık", sinif),
              f"{ISG_SINIFLAR[sinif]['kod']} isg_match her zaman False")


# ===========================================================================
def test_10_gercek_veri() -> None:
    """Arsiv kosusu: class2 sozcuksel skoru 0 VE sebebi metinde kelimenin HIC
    gecmemesi (eslestirici hatasi DEGIL). Bu iki sartin BIRLIKTE dogrulanmasi,
    '%0' iddiasini olcum kusurundan ayirir.
    """
    print("TEST 10 — gercek veri (arsiv)")
    if not os.path.exists(ARSIV):
        print("  [ATLA] arsiv dosyasi yok")
        return
    s = dosyayi_skorla(ARSIV)
    check(s["n_sinifi_cozulen"] == 200 and s["n_cozulemeyen"] == 0,
          f"200 satirin TAMAMI ISG sinifina cozuldu ({s['n_sinifi_cozulen']}/200, "
          f"cozulemeyen {s['n_cozulemeyen']})")
    c2 = s["per_sinif"]["Opened_Panel_Cover"]
    check(c2["sozcuksel"]["k"] == 0,
          f"class2 SOZCUKSEL adlandirma = 0/{c2['sozcuksel']['n']}")

    # ... ve sebebi: metinlerde 'pano/panel/kapak' HIC gecmiyor
    veri = json.load(open(ARSIV, encoding="utf-8"))
    rows = [r for r in veri["rows"]
            if isg_sinif_from_path(str(r.get("path") or "")) == "Opened_Panel_Cover"]
    gecen = sum(1 for r in rows
                if any(k in tr_lower(" . ".join(row_text(r, with_summary=True)))
                       for k in ("pano", "panel", "kapak", "kapağ")))
    check(gecen == 0,
          f"class2 kliplerinde 'pano/panel/kapak' kelimesi gecen klip: {gecen}/25 "
          f"-> %0 ESLESTIRICI HATASI DEGIL, gercek algi/ifade boslugu")

    # KAYITLI kaba skor SILINMEDI ve ince skordan FARKLI olabilir (yan yana durur)
    check(c2["kayitli_kaba"]["n"] == 25,
          "kaba IKILI skor 25 klipte KAYITLI (silinmemis, yan yana raporlanıyor)")
    check(c2["kayitli_kaba"]["k"] >= c2["sozcuksel"]["k"],
          f"kaba skor ({c2['kayitli_kaba']['k']}) >= ince skor ({c2['sozcuksel']['k']}) "
          f"— kaba kova havuzlanmis kaliplarla daha COMERT, beklenen yon")

    # TURETILMIS metrigin degismezligi: kesisim, iki bilesenden de kucuk/esit
    # olmali. Bu, "tam_dogru"nun sessizce bir IYI HABER KANALI'na donusmesini
    # engelleyen yapisal kilittir.
    for sinif, d in s["per_sinif"].items():
        if not d["guvensiz"]:
            continue
        check(d["tam_dogru"]["k"] <= min(d["sozcuksel"]["k"], d["operasyonel"]["k"]),
              f"{d['kod']} tam_dogru ({d['tam_dogru']['k']}) <= min(sozcuksel "
              f"{d['sozcuksel']['k']}, operasyonel {d['operasyonel']['k']})")
    check(all(s["per_sinif"][x]["tam_dogru"] is None
              for x in s["per_sinif"] if not s["per_sinif"][x]["guvensiz"]),
          "GUVENLI siniflarda tam_dogru TANIMSIZ (None) — sahte skor uretilmiyor")


# ===========================================================================
def test_11_olumsuzlama_onarimi() -> None:
    """D33 — `gözlemlenmedi` ailesi ONARILMIS kapida elenmeli, ESKI kapida ELENMEMELI.

    Kusurun kaydi: model "Görüntülerde herhangi bir tehlike, kaza, YETKISIZ GIRIS
    veya anormal davranış gözlemlenmedi." derken, icindeki "yetkisiz" kelimesi
    yuzunden DOGRU KATEGORI ADLANDIRMASI sayiliyordu.

    K2 KILIDI: eski kapinin davranisi DEGISMEMELI — arsiv yeniden uretilebilir kalir.
    """
    print("TEST 11 — olumsuzlama kapisi onarimi (D33)")
    kusurlu = ("Video süresince herhangi bir olay tespit edilmedi. Görüntülerde "
               "herhangi bir tehlike, kaza, yetkisiz giriş veya anormal davranış "
               "gözlemlenmedi.")
    check(match_category(kusurlu, "Anomali") is True,
          "ESKI kapi hala KUSURLU (arsiv uyumu KORUNDU — bu kasitli)")
    check(match_category(kusurlu, "Anomali", onarik_olumsuzlama=True) is False,
          "ONARIK kapi 'gözlemlenmedi' cumlecigini ELIYOR")

    # Onarilan bicimler tek tek
    for bicim in ("gözlemlenmedi", "gözlemlenmemiş", "gözlemlenmemektedir",
                  "belirtilmedi"):
        metin = f"Görüntüde yetkisiz giriş {bicim}"
        check(match_category(metin, "Anomali", onarik_olumsuzlama=True) is False,
              f"onarik kapi {bicim!r} bicimini yakaliyor")
    # ZATEN calisan bicimler bozulmamali
    for bicim in ("tespit edilmedi", "gözlenmedi", "görülmedi"):
        metin = f"Görüntüde yetkisiz giriş {bicim}"
        check(match_category(metin, "Anomali", onarik_olumsuzlama=True) is False
              and match_category(metin, "Anomali") is False,
              f"{bicim!r} HER IKI kapida da eleniyor (gerileme yok)")

    # YANLIS ELEME KILIDI: gercek olay hala SAYILMALI (modul kurali: yanlis eleme,
    # yanlis kabulden daha kotudur)
    gercek = "İşçi güvenlik yolu dışında yürüyor, yetkisiz giriş yaptı"
    check(match_category(gercek, "Anomali", onarik_olumsuzlama=True) is True,
          "GERCEK ihlal onarik kapida da SAYILIYOR (yanlis eleme yok)")
    check(isg_match(gercek, "Safe_Walkway_Violation") is True,
          "isg_match (onarik kapi kullanir) gercek ihlali SAYIYOR")
    check(isg_match("Güvenlik yolu ihlali gözlemlenmedi", "Safe_Walkway_Violation") is False,
          "isg_match 'gözlemlenmedi' cumlecigini ELIYOR")


# ===========================================================================
def main() -> int:
    for fn in (test_1_taksonomi_butunlugu, test_2_yol_cozumleme, test_3_kalip_eslesme,
               test_4_generic_kok_kilidi, test_5_olumsuzlama_kapisi,
               test_6_taksonomi_hizalamasi, test_7_ozgulluk, test_8_k2_k4_gerileme,
               test_9_guvenli_sinif_puanlama, test_10_gercek_veri,
               test_11_olumsuzlama_onarimi):
        fn()
        print()
    if _FAILURES:
        print(f"SONUC: {len(_FAILURES)} BASARISIZ")
        for f in _FAILURES:
            print("  - " + f)
        return 1
    print("SONUC: TUM TESTLER GECTI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
