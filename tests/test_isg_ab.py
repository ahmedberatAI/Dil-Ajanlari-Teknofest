#!/usr/bin/env python
"""benchmark/isg_ab.py birim testleri. GPU/vLLM/model/pytest GEREKTIRMEZ.

    python tests/test_isg_ab.py     # cikis kodu 0 = hepsi gecti

ANA FIKIR — ARSIVLE KILITLE
---------------------------
26 Temmuz'daki facility_rules A/B'si `docs/olcum_2026-07-26_kusur_sonrasi.md`de
SAYILARLA yazili (recall 20/100 -> 47/100, b=8, c=35). Bu testler araci O
sayilari yeniden uretmeye zorlar. Boylece esik mantigi veya eslestirme ileride
sessizce bozulursa test kirmizi yanar.

KAPSAM
  1  ARSIV KILIDI    : 26 Tem A/B, belgede yazili b/c ve oranlari birebir veriyor
  2  ESLESTIRME      : klipler `path` ile eslesiyor; eslenemeyen SESSIZCE ATILMIYOR
  3  METRIK YONU     : normal_temiz "YUKSEK = IYI" yonunde (FP metrigi cevrildi)
  4  ESIK MEKANIGI   : on-kayitli karar SAYIDAN turetiliyor (elle yazilmiyor)
  5  TANIMSIZ KLIP   : anomali metrigi normal klipte, normal metrigi anomalide
                       TANIMSIZ sayiliyor (paydaya girmiyor)
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.isg_ab import (ESIKLER, METRIKLER, _2x2, _m_normal_temiz,  # noqa: E402
                              _m_recall, esle, karsilastir)

_FAILURES: list = []
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

A_ARSIV = os.path.join(ROOT, "benchmark", "results", "eval_20260726_162613.json")  # kural KAPALI
B_ARSIV = os.path.join(ROOT, "benchmark", "results", "eval_20260726_171601.json")  # kural ACIK


def check(kosul: bool, mesaj: str) -> None:
    print(("  [OK]   " if kosul else "  [HATA] ") + mesaj)
    if not kosul:
        _FAILURES.append(mesaj)


def _yukle():
    with open(A_ARSIV, encoding="utf-8") as f:
        A = json.load(f)["rows"]
    with open(B_ARSIV, encoding="utf-8") as f:
        B = json.load(f)["rows"]
    return A, B


# ===========================================================================
def test_1_arsiv_kilidi() -> None:
    """docs/olcum_2026-07-26_kusur_sonrasi.md:126 — recall 20/100 -> 47/100, b=8, c=35."""
    print("TEST 1 — arsiv kilidi (26 Tem facility_rules A/B)")
    if not (os.path.exists(A_ARSIV) and os.path.exists(B_ARSIV)):
        print("  [ATLA] arsiv dosyalari yok")
        return
    A, B = _yukle()
    ciftler, tek = esle(A, B)
    check(len(ciftler) == 200 and not tek,
          f"200 klip eslendi, eslenemeyen yok ({len(ciftler)}, {len(tek)})")

    a, b, c, d, _ = _2x2(ciftler, _m_recall)
    n = a + b + c + d
    check(n == 100, f"recall paydasi 100 anomali klip ({n})")
    check(a + b == 20 and a + c == 47,
          f"BELGEDEKI oranlar: A={a + b}/100 (bekl 20), B={a + c}/100 (bekl 47)")
    check(b == 8 and c == 35,
          f"BELGEDEKI uyusmazlik sayimlari: b={b} (bekl 8), c={c} (bekl 35)")

    # docs:129 — normal kliplerde 'temiz' 83 -> 65 (p=0.0014)
    a2, b2, c2, d2, _ = _2x2(ciftler, _m_normal_temiz)
    check(a2 + b2 == 83 and a2 + c2 == 65,
          f"BELGEDEKI normal-temiz: A={a2 + b2}/100 (bekl 83), B={a2 + c2}/100 (bekl 65)")


# ===========================================================================
def test_2_eslestirme_kacak_vermiyor() -> None:
    """Eslenemeyen klip SESSIZCE ATILMAZ — ayrica dondurulur (K7)."""
    print("TEST 2 — eslestirme kacak vermiyor")
    A, B = _yukle() if os.path.exists(A_ARSIV) else ([], [])
    if not A:
        print("  [ATLA] arsiv yok")
        return
    # B'den bir klibi cikar -> eslenemeyen listesine DUSMELI
    B_eksik = [r for r in B if r.get("path") != A[0].get("path")]
    ciftler, tek = esle(A, B_eksik)
    check(len(ciftler) == 199 and tek == [str(A[0].get("path"))],
          f"eksik klip eslenemeyen listesinde ({len(ciftler)} cift, {len(tek)} tek)")


# ===========================================================================
def test_3_metrik_yonu() -> None:
    """normal_temiz YUKSEK = IYI yonunde olmali (FP metrigi cevrildi)."""
    print("TEST 3 — metrik yonu")
    temiz = {"is_anomaly": False, "n_events": 0, "triggered": []}
    kirli = {"is_anomaly": False, "n_events": 2, "triggered": []}
    tetikli = {"is_anomaly": False, "n_events": 0, "triggered": ["ekip_cagir"]}
    check(_m_normal_temiz(temiz) is True, "olaysiz+tetiksiz normal klip -> True (IYI)")
    check(_m_normal_temiz(kirli) is False, "olay ureten normal klip -> False")
    check(_m_normal_temiz(tetikli) is False, "fonksiyon tetikleyen normal klip -> False")
    check(_m_normal_temiz({"is_anomaly": True, "n_events": 0}) is None,
          "ANOMALI klipte normal metrigi TANIMSIZ (paydaya girmez)")
    check(_m_recall({"is_anomaly": False, "n_events": 3}) is None,
          "NORMAL klipte recall TANIMSIZ (paydaya girmez)")


# ===========================================================================
def test_4_esik_mekanigi() -> None:
    """Karar SAYIDAN turetiliyor mu — esik/alpha degisince karar de degismeli."""
    print("TEST 4 — on-kayitli esik mekanigi")
    check(ESIKLER["recall"]["esik_puan"] == 15 and ESIKLER["recall"]["alpha"] == 0.05,
          "H1 esigi on-kayittaki gibi: +15 puan, alpha 0.05")
    check(ESIKLER["cat_onarik"]["esik_puan"] == 12,
          "H2 esigi on-kayittaki gibi: +12 puan (gurultu tabani %8'in uzeri)")
    check(ESIKLER["normal_temiz"]["esik_puan"] == -15
          and ESIKLER["normal_temiz"].get("yon") == "maliyet",
          "H3 MALIYET yonunde: fark <= -15 puan")
    # Her esikli metrigin bir hipotez etiketi ve iki karar metni olmali
    for anahtar, ok in ESIKLER.items():
        check(bool(ok.get("hipotez")) and bool(ok.get("gecerse")) and bool(ok.get("kalirsa")),
              f"{anahtar}: hipotez etiketi + GECTI/GECEMEDI metinleri tanimli")
    # METRIKLER tablosundaki esik ile ESIKLER sozlugu CELISMEMELI (tek kaynak-dogru)
    for anahtar, _ad, _fn, esik in METRIKLER:
        if esik is not None:
            check(ESIKLER[anahtar]["esik_puan"] == esik or
                  ESIKLER[anahtar]["esik_puan"] == -esik,
                  f"{anahtar}: METRIKLER esigi ({esik}) ESIKLER ile tutarli "
                  f"({ESIKLER[anahtar]['esik_puan']})")


# ===========================================================================
def test_5_uctan_uca() -> None:
    """karsilastir() cokmeden calisiyor ve arsivde H1/H2/H3'u GECIRIYOR."""
    print("TEST 5 — uctan uca (arsiv A/B)")
    if not (os.path.exists(A_ARSIV) and os.path.exists(B_ARSIV)):
        print("  [ATLA] arsiv yok")
        return
    s = karsilastir(A_ARSIV, B_ARSIV, "kapali", "acik")
    m = s["metrikler"]
    check(m["recall"]["gecti"] is True,
          f"H1 arsivde GECIYOR (fark {m['recall']['fark_puan']:+.0f} puan, "
          f"p={m['recall']['p_exact']:.4f})")
    check(m["cat_onarik"]["gecti"] is True,
          f"H2 ONARILMIS kapiyla da GECIYOR (fark {m['cat_onarik']['fark_puan']:+.0f} puan) "
          f"— kural kazanci olcum kusurunun ARTIFAKTI DEGIL")
    check(m["normal_temiz"]["gecti"] is True,
          f"H3 maliyet arsivde DOGRULANIYOR (fark {m['normal_temiz']['fark_puan']:+.0f} puan)")
    check(m["cat_onarik"]["oran_b"] < m["cat_d28"]["oran_b"],
          f"onarik kapi D28'den DAHA DUSUK skor veriyor "
          f"({m['cat_onarik']['oran_b']:.2f} < {m['cat_d28']['oran_b']:.2f}) — beklenen yon")


# ===========================================================================
def test_6_gurultu_kipi() -> None:
    """--gurultu kipinde hipotez KARARI basilmamali (yanlis okuma kapisi).

    NEDEN: A vs A' kosusunda esikler "mudahale etkili mi?" sorusunun cevabidir ve
    ayni yapilandirmada ANLAMSIZDIR. Kip olmadan arac "H1 GECEMEDI — REPLIKE
    OLMADI" basiyordu; bu, gurultu olcumunu BASARISIZLIK gibi gosteriyordu.
    """
    print("TEST 6 — gurultu kipi")
    if not (os.path.exists(A_ARSIV) and os.path.exists(B_ARSIV)):
        print("  [ATLA] arsiv yok")
        return
    normal = karsilastir(A_ARSIV, B_ARSIV, "a", "b", gurultu=False)
    gur = karsilastir(A_ARSIV, B_ARSIV, "a", "b", gurultu=True)

    check(normal["metrikler"]["recall"].get("karar") is not None,
          "NORMAL kipte hipotez karari VAR")
    check("karar" not in gur["metrikler"]["recall"]
          and "gecti" not in gur["metrikler"]["recall"],
          "GURULTU kipinde hipotez karari YOK (yanlis okuma engellendi)")
    check(gur["metrikler"]["recall"].get("gurultu_puan") == 27
          and gur["metrikler"]["recall"].get("gurultu_cevirme") == 43,
          f"gurultu alanlari dolu: |fark|={gur['metrikler']['recall'].get('gurultu_puan')} "
          f"cevirme={gur['metrikler']['recall'].get('gurultu_cevirme')}")
    check(gur["gurultu_kipi"] is True and normal["gurultu_kipi"] is False,
          "cikti JSON'unda kip ACIKCA isaretli (sonradan karistirilamaz)")
    # Sayimlar kipten BAGIMSIZ olmali — yalnizca YORUM degisir
    for k in ("a", "b", "c", "d", "n", "p_exact"):
        check(gur["metrikler"]["recall"][k] == normal["metrikler"]["recall"][k],
              f"recall.{k} iki kipte AYNI (kip yalnizca yorumu degistirir)")


# ===========================================================================
def main() -> int:
    for fn in (test_1_arsiv_kilidi, test_2_eslestirme_kacak_vermiyor,
               test_3_metrik_yonu, test_4_esik_mekanigi, test_5_uctan_uca,
               test_6_gurultu_kipi):
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
