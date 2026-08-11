#!/usr/bin/env python
"""D28 — ESLESTIRICI ve YENIDEN SKORLAMA testleri. GPU/vLLM/model GEREKTIRMEZ.

Bagimsiz calisir (pytest gerekmez):
    python tests/test_rescore.py

Kapsam (gorev sartlari birebir):
  1  TURKCE KUCUK HARF : "İstismar" -> Abuse ESLESIYOR (Python .lower() bunu BOZUYOR)
  2  KELIME SINIRI     : "kırmızı" Burglary/Vandalism TETIKLEMIYOR; gercek "kır" TETIKLIYOR
  3  KELIME SINIRI     : "vurgulanmadı" Assault TETIKLEMIYOR; "vurdu" TETIKLIYOR
  4  TURKCE SONEK      : "düşük çözünürlük" Fall TETIKLEMIYOR; "düştü/düşerek/düşmüş" TETIKLIYOR
  5  OLUMSUZLAMA       : "yangın gözlenmedi" Fire TETIKLEMIYOR; asiri eleme YAPMIYOR
  6  ESKI KURAL        : arsivlenmis A dosyasinda 9/24 BIREBIR yeniden uretiliyor (K4)
  7  SEMANTIK GRUP     : grup uyeligi ve grup duzeyi eslesme dogru calisiyor
  8  OZGULLUK          : sikilastirilmis eslestirici klip basina daha AZ yanlis kategori tetikliyor
  9  FAIL-OPEN (K3)    : yeni alanlari OLMAYAN arsiv satirlari yeniden skorlamayi COKERTMIYOR
 10  K2 GERI DONUS     : loose_match ESKI davranisi birebir koruyor (taban yeniden uretilebilir)
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.labels import (  # noqa: E402
    CATEGORY_EXPECT, CATEGORY_PATTERNS, SEMANTIC_GROUPS, any_match, group_match,
    group_members, group_of, loose_match, match_category, matched_categories, row_text,
    tr_lower,
)
from benchmark.rescore import dosyayi_skorla  # noqa: E402

_FAILURES: list = []
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Gorevde adi gecen dogrulama noktasi: ESKI kural bu dosyada 9/24 URETMELI.
A_DOSYA = os.path.join(ROOT, "benchmark", "results", "naming_ab_A_20260810_210033.json")


def check(cond: bool, label: str) -> None:
    print(("  [OK]   " if cond else "  [FAIL] ") + label)
    if not cond:
        _FAILURES.append(label)


def test_1_turkce_kucuk_harf() -> None:
    print("1) TURKCE-GUVENLI KUCUK HARF")
    # Python'un kusuru KANITLANIR: "İ".lower() = i + U+0307 BIRLESIK NOKTA
    check("İstismar".lower() != "istismar",
          "Python .lower() 'İstismar'i BOZUYOR (kusur gercek — testin sebebi bu)")
    check("\u0307" in "İstismar".lower(),
          "bozulmanin sebebi U+0307 birlesik nokta")
    check(tr_lower("İstismar") == "istismar", "tr_lower('İstismar') == 'istismar'")
    check(tr_lower("Itfaiye") == "ıtfaiye", "tr_lower('Itfaiye') == 'ıtfaiye' (I -> ı)")
    check(tr_lower("İTİŞME") == "itişme", "tr_lower('İTİŞME') == 'itişme'")
    # ESAS SART: buyuk harfle baslayan metin kategoriye ESLESIYOR
    check(match_category("İstismar şüphesi var", "Abuse"),
          "'İstismar şüphesi var' -> Abuse ESLESIYOR")
    check(match_category("İtişme yaşandı", "Fighting"),
          "'İtişme yaşandı' -> Fighting ESLESIYOR")
    # Ayni metin ESKI kuralla ESLESMIYOR -> duzeltmenin etkisi olculebilir
    check(not loose_match("İstismar şüphesi var", "Abuse"),
          "ESKI kural ayni metni KACIRIYOR (duzeltmenin etkisi somut)")


def test_2_kelime_siniri_kir() -> None:
    print("2) KELIME SINIRI — 'kır'")
    check(not match_category("bina önünde kırmızı sıvı yayılımı", "Burglary"),
          "'kırmızı' Burglary TETIKLEMIYOR")
    check(not match_category("bina önünde kırmızı sıvı yayılımı", "Vandalism"),
          "'kırmızı' Vandalism TETIKLEMIYOR")
    check(loose_match("bina önünde kırmızı sıvı yayılımı", "Vandalism"),
          "ESKI kural ayni metinde Vandalism tetikliyordu (kusur gercek)")
    check(match_category("Kişi vitrini kırdı", "Vandalism"), "'kırdı' Vandalism TETIKLIYOR")
    check(match_category("camı kırarak içeri girdi", "Vandalism"), "'kırarak' TETIKLIYOR")
    check(match_category("cam kırılmış", "Vandalism"), "'kırılmış' TETIKLIYOR")
    check(match_category("kilidi kırarak girdi", "Burglary"),
          "'kilidi kır' cok-kelimeli kalibi Burglary TETIKLIYOR")
    # Kelime ORTASINDA gecen kok sayilmamali
    check(not match_category("kolunu savurdu", "Assault"),
          "'savurdu' icindeki 'vur' SAYILMIYOR (kelime ortasi)")


def test_3_kelime_siniri_vur() -> None:
    print("3) KELIME SINIRI — 'vur'")
    check(not match_category("Bu konu vurgulanmadı", "Assault"),
          "'vurgulanmadı' Assault TETIKLEMIYOR")
    check(loose_match("Bu konu vurgulanmadı", "Assault"),
          "ESKI kural 'vurgulanmadı'yi Assault sayiyordu (kusur gercek)")
    check(not match_category("raporda vurgu yapılmış", "Assault"), "'vurgu' TETIKLEMIYOR")
    check(match_category("Bir kişi diğerine vurdu", "Assault"), "'vurdu' Assault TETIKLIYOR")
    check(match_category("kişi yumrukla vuruyor", "Assault"), "'vuruyor' TETIKLIYOR")
    check(match_category("yere vurarak müdahale etti", "Assault"), "'vurarak' TETIKLIYOR")


def test_4_turkce_sonek_dus() -> None:
    print("4) TURKCE SONEK DENGESI — 'düş'")
    # ESLESMEMELI
    for metin in ("düşük çözünürlüklü görüntü", "görüntü kalitesi düşük",
                  "operatör bunu düşünüyor", "bu bir düşünce deneyidir",
                  "riskin düşük olduğu değerlendirildi"):
        check(not match_category(metin, "Fall"), f"Fall TETIKLEMIYOR: {metin!r}")
    check(loose_match("düşük çözünürlüklü görüntü", "Fall"),
          "ESKI kural 'düşük'u Fall sayiyordu (kusur gercek)")
    # ESLESMELI
    for metin in ("kişi yere düştü", "kişi düşerek yere yığıldı", "yere düşmüş bir kişi var",
                  "düşme anı kaydedildi", "yere düşen kişi hareketsiz"):
        check(match_category(metin, "Fall"), f"Fall TETIKLIYOR: {metin!r}")


def test_5_olumsuzlama() -> None:
    print("5) OLUMSUZLAMA KAPISI")
    # DUSMELI
    for metin, kat in (("yangın gözlenmedi", "Fire"),
                       ("kaza belirtisi yok", "RoadAccidents"),
                       ("duman tespit edilmedi", "Smoke"),
                       ("silah bulunmamaktadır", "Shooting"),
                       ("herhangi bir kavga izlenmemektedir", "Fighting"),
                       ("bu bir kavga değil", "Fighting")):
        check(not match_category(metin, kat), f"{kat} TETIKLEMIYOR: {metin!r}")
    check(loose_match("yangın gözlenmedi", "Fire"),
          "ESKI kural 'yangın gözlenmedi'yi Fire sayiyordu (kusur gercek)")
    # ASIRIYA KACMAMALI — baska bir fiilin olumsuzu olayi IPTAL ETMEZ
    check(match_category("kavga eden kişiler durdurulamadı", "Fighting"),
          "'durdurulamadı' kavgayi IPTAL ETMIYOR (asiri eleme yok)")
    check(match_category("yere düşen kişi hareketsiz, tepki vermiyor", "Fall"),
          "sonraki cumlecikteki olumsuzlama onceki olayi IPTAL ETMIYOR")
    check(match_category("yangın çıktı, itfaiye henüz gelmedi", "Fire"),
          "'gelmedi' yangini IPTAL ETMIYOR (ayri cumlecik)")
    # Kapi kapatilabilir olmali
    check(match_category("yangın gözlenmedi", "Fire", negation=False),
          "negation=False ile olumsuzlama kapisi KAPATILABILIYOR")


def test_6_eski_kural_yeniden_uretiliyor() -> None:
    print("6) ESKI KURAL YENIDEN URETILEBILIYOR (K4 — en kritik test)")
    if not os.path.exists(A_DOSYA):
        check(False, f"arsiv dosyasi yok: {A_DOSYA}")
        return
    s = dosyayi_skorla(A_DOSYA)
    eski = s["kurallar"]["eski"]
    check(eski["n"] == 24, f"A dosyasinda 24 anomali klip var (gelen: {eski['n']})")
    check(eski["k"] == 9, f"ESKI kural 9/24 URETIYOR (gelen: {eski['k']}/{eski['n']})")
    hd = s["hat_dogrulama"]
    check(hd["tamam"],
          f"ESKI kural, dosyadaki KAYITLI category_match ile birebir ayni "
          f"({hd['uyan']}/{hd['karsilastirilabilir']})")
    # Yeni kurallarin taban cizgisini gizlemedigini dogrula
    check(s["kurallar"]["summary"]["k"] >= eski["k"],
          "summary eklemek skoru DUSURMUYOR (kapsam genisliyor)")
    check(all(k in s["kurallar"] for k in ("eski", "summary", "siki", "grup")),
          "dort kural da raporlaniyor")


def test_7_semantik_grup() -> None:
    print("7) SEMANTIK GRUPLAMA")
    check(group_of("Fighting") == "Siddet" and group_of("Assault") == "Siddet"
          and group_of("Abuse") == "Siddet", "Fighting/Assault/Abuse -> Siddet")
    check(group_of("Burglary") == group_of("Vandalism") == "MalSuclari",
          "Burglary/Vandalism -> MalSuclari")
    check(group_of("Explosion") == group_of("Fire") == group_of("Smoke") == "Yikim",
          "Explosion/Fire/Smoke -> Yikim")
    check(group_of("RoadAccidents") == "Trafik" and group_of("Shooting") == "Silahli"
          and group_of("Fall") == "Dusme", "Trafik / Silahli / Dusme tekil gruplar")
    check(group_of("Normal") is None, "Normal'in semantik grubu YOK")
    check(group_members("Normal") == ["Normal"], "grubu olmayan kategori kendi uyesidir")
    # Mevcut CATEGORY_EXPECT anahtarlari SILINMEDI (gorev sarti)
    for uyeler in SEMANTIC_GROUPS.values():
        for c in uyeler:
            check(c in CATEGORY_EXPECT, f"'{c}' CATEGORY_EXPECT'te DURUYOR (silinmedi)")
    # Grup duzeyi eslesme: Abuse klibinde "kavga" denmis -> kategori KACIRIR, grup YAKALAR
    metin = "iki kişi arasında fiziksel kavga meydana geldi"
    check(not match_category(metin, "Burglary"), "kavga metni Burglary'yi tetiklemiyor")
    check(group_match(metin, "Abuse"), "kavga metni Abuse'un GRUBUNU (Siddet) yakaliyor")
    check(not group_match(metin, "Fire"), "kavga metni Yikim grubunu YAKALAMIYOR (grup sinirli)")


def test_8_ozgulluk_artti() -> None:
    print("8) OZGULLUK — klip basina yanlis kategori")
    metin = ("kırmızı bir obje ile müdahale ediliyor, kapıdan giriş yapan personel "
             "görüldü, yüksek risk yok ve kaza belirtisi yok")
    gevsek = matched_categories(metin, mode="loose")
    siki = matched_categories(metin, mode="strict")
    check(len(siki) < len(gevsek),
          f"sikilastirilmis eslestirici daha AZ kategori tetikliyor ({len(siki)} < {len(gevsek)})")
    check("Burglary" in gevsek and "Burglary" not in siki,
          "Burglary yanlis tetigi GIDERILDI")
    check("RoadAccidents" in gevsek and "RoadAccidents" not in siki,
          "RoadAccidents yanlis tetigi (olumsuzlama) GIDERILDI")
    # Arsivlenmis kosuda da ozgulluk ARTMALI (yanlis tetik sayisi DUSMELI)
    if os.path.exists(A_DOSYA):
        s = dosyayi_skorla(A_DOSYA)
        check(s["kurallar"]["siki"]["ozgulluk"] < s["kurallar"]["summary"]["ozgulluk"],
              f"A kosusunda yanlis tetik/klip DUSTU "
              f"({s['kurallar']['summary']['ozgulluk']:.2f} -> {s['kurallar']['siki']['ozgulluk']:.2f})")
        check(s["kurallar"]["grup"]["ozgulluk"] < s["kurallar"]["siki"]["ozgulluk"],
              "grup duzeyinde yanlis tetik daha da DUSUYOR")


def test_9_fail_open_eksik_alan() -> None:
    print("9) FAIL-OPEN (K3) — eksik/bozuk alanli arsiv satirlari")
    # Yeni alanlarin HICBIRI olmayan, hatta events/summary'si eksik satirlar
    sahte = {
        "eval_dir": "data/eval_holdout",
        "rows": [
            {"path": "a.mp4", "category": "Fighting", "is_anomaly": True,
             "events": [{"event": "iki kişi kavga ediyor"}], "summary": "kavga var"},
            {"path": "b.mp4", "category": "Fire", "is_anomaly": True},          # events/summary YOK
            {"path": "c.mp4", "category": "Fall", "is_anomaly": True,
             "events": None, "summary": None},                                  # None degerler
            {"path": "d.mp4", "category": "Normal", "is_anomaly": False},
        ],
    }
    yol = os.path.join(ROOT, "benchmark", "results", "_test_fail_open.json")
    try:
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(sahte, f, ensure_ascii=False)
        s = dosyayi_skorla(yol)
        check(s["n_anomali"] == 3, "anomali satirlari sayildi (Normal disarida)")
        check(s["kurallar"]["eski"]["k"] == 1, "yalniz gercek olay eslesti, COKME YOK")
        check(s["hat_dogrulama"]["karsilastirilabilir"] == 0,
              "kayitli category_match olmayan dosyada hat dogrulamasi COKMUYOR")
        check(s["hat_dogrulama"]["tamam"] is False,
              "karsilastirilacak veri yoksa 'TAMAM' IDDIA EDILMIYOR (sessiz yesil yok)")
    finally:
        if os.path.exists(yol):
            os.remove(yol)
    # Bos/None metinler eslestiriciyi cokertmemeli
    check(match_category("", "Fire") is False, "bos metin -> False (cokme yok)")
    check(match_category(None, "Fire") is False, "None metin -> False (cokme yok)")  # type: ignore
    check(match_category("yangın var", "BilinmeyenKategori") is False,
          "bilinmeyen kategori -> False (cokme yok)")
    check(row_text({}, with_summary=True) == [], "bos satirdan bos metin listesi")


def test_10_geri_donus_ve_kapsam() -> None:
    print("10) K2 GERI DONUS + kapsam ayrimi")
    # loose_match, D28 ONCESI ifadeyi BIREBIR korumali
    for metin, kat in (("kırmızı", "Vandalism"), ("vurgulanmadı", "Assault"),
                       ("düşük", "Fall"), ("kaza yok", "RoadAccidents")):
        beklenen = any(k in metin.lower() for k in CATEGORY_EXPECT[kat][0])
        check(loose_match(metin, kat) == beklenen,
              f"loose_match ESKI ifadeyi birebir koruyor: {metin!r} -> {kat}")
    # row_text kapsam ayrimi: summary DAHIL/HARIC
    satir = {"events": [{"event": "olay metni"}], "summary": "ozet metni"}
    check(row_text(satir, with_summary=False) == ["olay metni"], "summary HARIC kapsam")
    check(row_text(satir, with_summary=True) == ["olay metni", "ozet metni"], "summary DAHIL kapsam")
    # any_match kapsam farkini gosteriyor: adlandirma YALNIZ summary'de ise
    satir2 = {"events": [{"event": "merkezde hareketlilik var"}],
              "summary": "iki kişi arasında kavga meydana geldi"}
    check(not any_match(row_text(satir2, with_summary=False), "Fighting", mode="strict"),
          "summary HARIC iken adlandirma KACIYOR (olculen kusurun ta kendisi)")
    check(any_match(row_text(satir2, with_summary=True), "Fighting", mode="strict"),
          "summary DAHIL iken adlandirma YAKALANIYOR")
    # Kalip sozlugu, etiket sozlugunun anahtarlarini KAYBETMEMELI
    check(set(CATEGORY_PATTERNS) == set(CATEGORY_EXPECT),
          "CATEGORY_PATTERNS ve CATEGORY_EXPECT ayni kategori kumesini kapsiyor")


def main() -> int:
    for fn in (test_1_turkce_kucuk_harf, test_2_kelime_siniri_kir, test_3_kelime_siniri_vur,
               test_4_turkce_sonek_dus, test_5_olumsuzlama,
               test_6_eski_kural_yeniden_uretiliyor, test_7_semantik_grup,
               test_8_ozgulluk_artti, test_9_fail_open_eksik_alan,
               test_10_geri_donus_ve_kapsam):
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
