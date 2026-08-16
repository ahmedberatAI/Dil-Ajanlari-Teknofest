#!/usr/bin/env python
"""VERI LISANS KAPISI testleri (dilajan/veri_lisans.py). GPU/model GEREKTIRMEZ.

    python tests/test_isg_lisans.py     # cikis kodu 0 = hepsi gecti

NEDEN BU TESTLER VAR
--------------------
`data/isafety_bench` **CC BY-NC-SA 4.0**tir: degerlendirmede serbest, **egitimde
YASAK**. ShareAlike ince ayarda model agirliklarini turev eser yapabilir ve
modelimizi de CC BY-NC-SA'ya mahkum edebilir (HANDOFF §6.3 takim karari).

Bu kural yalnizca bir BELGEDE dursaydi aylar sonra biri farkinda olmadan cignerdi.
Testler kurali **kod duzeyinde** kilitler: kapi gevsetilirse test kirmizi yanar.

KAPSAM
  1  YASAK SETLER     : isafety_bench + eval setleri egitimde REDDEDILIYOR
  2  SERBEST SETLER   : industrial egitimde geciyor (asil havuz)
  3  ALT DIZIN        : yasak, ALT dizinlere de miras kaliyor (en uzun onek)
  4  KUNYE ONCELIGI   : veriyle gelen LISANS.json BILINEN tablosunu EZIYOR
  5  FAIL-CLOSED      : dogrulama ISTISNA firlatiyor (sessizce True donmuyor)
  6  BILINMEYEN VERI  : kural yoksa SERBEST (kapi beyaz-liste degil, kara-liste)
  7  KUNYE ICERIGI    : indirilmisse gercek LISANS.json dogru bayragi tasiyor
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.veri_lisans import (  # noqa: E402
    BILINEN, LisansIhlali, degerlendirmede_kullanilabilir, egitim_icin_dogrula,
    egitimde_kullanilabilir, kunye_oku, kural_bul, rapor,
)

_FAILURES: list = []
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(kosul: bool, mesaj: str) -> None:
    print(("  [OK]   " if kosul else "  [HATA] ") + mesaj)
    if not kosul:
        _FAILURES.append(mesaj)


# ===========================================================================
def test_1_yasak_setler() -> None:
    """Egitimde kullanilmasi YASAK setler reddedilmeli."""
    print("TEST 1 — egitimde YASAK setler")
    for yol, neden in (
        ("data/isafety_bench", "CC BY-NC-SA ShareAlike"),
        ("data/eval_defense", "degerlendirme seti — egitim olcumu gecersiz kilar"),
        ("data/eval_holdout", "holdout — egitimde kullanimi sizintidir"),
    ):
        check(egitimde_kullanilabilir(yol) is False, f"{yol} egitimde YASAK ({neden})")
        check(degerlendirmede_kullanilabilir(yol) is True,
              f"{yol} degerlendirmede SERBEST")


# ===========================================================================
def test_2_serbest_setler() -> None:
    """Asil havuz egitimde kullanilabilmeli (kapi her seyi engellemiyor)."""
    print("TEST 2 — egitimde SERBEST setler")
    check(egitimde_kullanilabilir("data/industrial") is True,
          "data/industrial egitimde SERBEST (asil havuz, CC BY)")
    check(egitimde_kullanilabilir("data/ppe") is True,
          "data/ppe egitimde SERBEST (KKD, CC BY 4.0 — YOLO dogrulayici icin)")
    try:
        egitim_icin_dogrula(["data/industrial", "data/ppe"])
        ok = True
    except LisansIhlali:
        ok = False
    check(ok, "egitim_icin_dogrula(['data/industrial','data/ppe']) sessizce geciyor")
    # KKD alt dizinleri de serbest olmali
    check(egitimde_kullanilabilir("data/ppe/hard_hat/data") is True,
          "data/ppe alt dizinleri de serbest (miras dogru yonde calisiyor)")


# ===========================================================================
def test_3_alt_dizin_mirasi() -> None:
    """Yasak, ALT dizinlere de uygulanmali — yoksa kapi trivially atlanir."""
    print("TEST 3 — alt dizin mirasi")
    for alt in ("data/isafety_bench/videos",
                "data/isafety_bench/videos/hazard",
                "data/isafety_bench/annotations"):
        check(egitimde_kullanilabilir(alt) is False,
              f"{alt} -> yasak MIRAS ALINDI")
    # En UZUN onek kazanmali (eval_defense, data/ altinda ama kendi kurali var)
    k = kural_bul("data/eval_defense/Anomali/Safe_Walkway_Violation/0_te1.mp4")
    check(k is not None and k.get("_dizin") == "data/eval_defense",
          f"derin yol en UZUN onege eslesti ({k.get('_dizin') if k else None})")


# ===========================================================================
def test_4_kunye_onceligi() -> None:
    """Veriyle gelen LISANS.json, BILINEN tablosunu EZMELI.

    NEDEN: kural veriyle BIRLIKTE seyahat etmeli. Biri seti baska bir yola
    kopyalarsa kunye yaninda gider; BILINEN tablosu gitmez.
    """
    print("TEST 4 — kunye (LISANS.json) onceligi")
    with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, "data")) as td:
        rel = os.path.relpath(td, ROOT).replace("\\", "/")
        # Kunye YOKKEN: bilinmeyen dizin -> SERBEST
        check(egitimde_kullanilabilir(rel) is True,
              "kunyesiz bilinmeyen dizin egitimde serbest (kara-liste mantigi)")
        # Kunye EKLENINCE: yasak
        with open(os.path.join(td, "LISANS.json"), "w", encoding="utf-8") as f:
            json.dump({"lisans": "CC BY-NC-SA 4.0",
                       "egitimde_kullanilabilir": False,
                       "gerekce": "test kunyesi"}, f)
        check(egitimde_kullanilabilir(rel) is False,
              "LISANS.json eklenince ayni dizin YASAK oldu")
        k = kural_bul(rel)
        check(k is not None and k.get("_kaynak") == "LISANS.json",
              "kural kaynagi KUNYE olarak isaretlendi")


# ===========================================================================
def test_5_fail_closed() -> None:
    """Dogrulama ISTISNA firlatmali — sessizce gecmemeli (BILEREK fail-closed)."""
    print("TEST 5 — fail-closed davranis")
    firladi = False
    mesaj = ""
    try:
        egitim_icin_dogrula(["data/industrial", "data/isafety_bench"])
    except LisansIhlali as e:
        firladi = True
        mesaj = str(e)
    check(firladi, "karisik listede LisansIhlali FIRLADI (sessizce gecmedi)")
    check("isafety_bench" in mesaj and "ShareAlike" in mesaj,
          "istisna mesaji HANGI dizin ve NEDEN oldugunu yaziyor")
    check("HANDOFF" in mesaj,
          "istisna mesaji karari nereden aldigini gosteriyor (izlenebilirlik)")
    # Tek string de kabul edilmeli
    try:
        egitim_icin_dogrula("data/isafety_bench")
        tek_ok = False
    except LisansIhlali:
        tek_ok = True
    check(tek_ok, "tek string argüman da dogrulaniyor")


# ===========================================================================
def test_6_bilinmeyen_veri() -> None:
    """Kural yoksa SERBEST — kapi kara-listedir, beyaz-liste DEGIL.

    Bu kasitlidir: kapi BILINEN yasaklari zorlar. Aksi halde her yeni veri
    dizini sessizce egitimi kirardi ve kapi kapatilirdi.
    """
    print("TEST 6 — bilinmeyen veri serbest")
    check(egitimde_kullanilabilir("data/boyle_bir_set_yok") is True,
          "bilinmeyen dizin egitimde serbest")
    check(kural_bul("data/boyle_bir_set_yok") is None,
          "bilinmeyen dizin icin kural None")


# ===========================================================================
def test_7_gercek_kunye() -> None:
    """iSafetyBench indirildiyse GERCEK kunyesi dogru bayragi tasimali."""
    print("TEST 7 — indirilmis gercek kunye")
    d = os.path.join(ROOT, "data", "isafety_bench")
    if not os.path.isdir(d):
        print("  [ATLA] data/isafety_bench henuz indirilmemis")
        return
    k = kunye_oku("data/isafety_bench")
    check(k is not None, "LISANS.json okunabildi")
    if not k:
        return
    check(k.get("egitimde_kullanilabilir") is False,
          "kunye: egitimde_kullanilabilir = False")
    check(k.get("degerlendirmede_kullanilabilir") is True,
          "kunye: degerlendirmede_kullanilabilir = True")
    check("NC" in str(k.get("lisans", "")).upper().replace("-", ""),
          f"kunye lisansi NonCommercial iceriyor: {k.get('lisans')}")
    check(os.path.exists(os.path.join(d, "NOKULLAN_EGITIM.md")),
          "insan-okur uyari dosyasi NOKULLAN_EGITIM.md var")
    # Kapi gercek dizinde de calisiyor mu
    check(egitimde_kullanilabilir("data/isafety_bench") is False,
          "gercek dizin uzerinde kapi YASAK diyor")


# ===========================================================================
def test_8_rapor() -> None:
    """rapor() cokmeden okunabilir cikti uretmeli."""
    print("TEST 8 — rapor")
    try:
        r = rapor()
        ok = isinstance(r, str) and "isafety_bench" in r and "industrial" in r
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"        cokme: {type(e).__name__}: {e}")
    check(ok, "rapor() tum bilinen setleri listeliyor")
    check(len(BILINEN) >= 4, f"BILINEN tablosunda en az 4 kayit var ({len(BILINEN)})")


# ===========================================================================
def main() -> int:
    for fn in (test_1_yasak_setler, test_2_serbest_setler, test_3_alt_dizin_mirasi,
               test_4_kunye_onceligi, test_5_fail_closed, test_6_bilinmeyen_veri,
               test_7_gercek_kunye, test_8_rapor):
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
