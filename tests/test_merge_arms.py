#!/usr/bin/env python
"""benchmark/merge_arms.py birim testleri. GPU/vLLM/model/pytest GEREKTIRMEZ.

    python tests/test_merge_arms.py     # cikis kodu 0 = hepsi gecti

ANA TEST — YUVARLAK YOLCULUK
----------------------------
merge_arms.ozet_hesapla(), eval_clips.py:main()'in ozet formullerinin KOPYASIDIR.
Kopya, "iki kaynak-dogru" riski tasir: eval_clips.py degisir, merge_arms degismez
ve sayilar SESSIZCE ayrisir.

Bu testler riski soyle kapatir: BUTUN bir n=200 arsiv kosusu Anomali/Normal diye
IKIYE BOLUNUR, merge_arms ile birlestirilir ve uretilen ozet, ORIJINAL dosyanin
KENDI `summary` alaniyla (yani eval_clips.py'nin GERCEKTEN urettigi degerlerle)
alan alan karsilastirilir. Formuller ayrisirsa bu test kirmizi yanar.

KAPSAM
  1  YUVARLAK YOLCULUK : ikiye bol -> birlestir -> ozet ORIJINALLE birebir
  2  CI SOZLUGU        : ci{} altindaki her metrigin k/n/p degerleri de birebir
  3  ARSIV VINTAGE'I   : D28 ONCESI kosuda `category_match_eski` alani HIC YOKTUR;
                         birlestirici bunu 0.0 diye raporlamamali (0.0 "olculdu ve
                         sifir cikti" demektir — YANLIS iddia), None birakmali
  4  KOL BAGIMSIZLIGI  : tek kol tek basina EKSIK ozet uretir (bu araci gerektiren
                         sebebin kendisi) — recall paydasi 0 vb.
  5  CIFT SAYIM KAPISI : ayni klip iki kolda ise UYARI listesine giriyor
  6  BOS/KENAR         : bos satir listesi COKME uretmiyor
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.merge_arms import birlestir, ozet_hesapla  # noqa: E402

_FAILURES: list = []
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Yuvarlak yolculugun dayandigi ARSIV — D28 SONRASI kosu olmali, cunku
#: `cat_match_eski`/`cat_match_grup` alanlari D28'de eklendi; daha eski bir dosyada
#: bu alanlar HIC YOKTUR ve tam karsilastirma yapilamaz (bkz. test 3).
ARSIV = os.path.join(ROOT, "benchmark", "results", "evidence_ab_A_20260811_205728.json")
#: D28 ONCESI kosu — vintage testinde kullanilir.
ARSIV_ESKI = os.path.join(ROOT, "benchmark", "results", "eval_20260726_171601.json")
TOL = 1e-12


def check(kosul: bool, mesaj: str) -> None:
    print(("  [OK]   " if kosul else "  [HATA] ") + mesaj)
    if not kosul:
        _FAILURES.append(mesaj)


def yakin(a, b, tol: float = TOL) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


def _kollara_bol(tmpdir: str, arsiv: str = ARSIV) -> list:
    """Arsiv dosyasini ANOMALI / NORMAL kollarina boler, iki dosya yazar.

    Bolme `is_anomaly` uzerinden yapilir (kategori adi uzerinden DEGIL), boylece
    hem eval_defense (Anomali/Normal) hem eval_holdout (8 UCF sinifi + Normal)
    dosyalarinda ayni sekilde calisir — gercek EVAL_CATS kol bolmesinin karsiligi.
    """
    with open(arsiv, encoding="utf-8") as f:
        veri = json.load(f)
    yollar = []
    for ad, kosul in (("anomali", True), ("normal", False)):
        rows = [r for r in veri["rows"] if bool(r.get("is_anomaly")) is kosul]
        p = os.path.join(tmpdir, f"kol_{ad}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"summary": {}, "eval_dir": veri.get("eval_dir"),
                       "dedup": {}, "rows": rows}, f, ensure_ascii=False)
        yollar.append(p)
    return yollar


# ===========================================================================
def test_1_yuvarlak_yolculuk() -> None:
    """Ikiye bol -> birlestir -> ozet ORIJINALLE birebir ayni olmali."""
    print("TEST 1 — yuvarlak yolculuk (merge == eval_clips)")
    if not os.path.exists(ARSIV):
        print("  [ATLA] arsiv dosyasi yok")
        return
    import tempfile
    with open(ARSIV, encoding="utf-8") as f:
        orijinal = json.load(f)["summary"]
    with tempfile.TemporaryDirectory() as td:
        yollar = _kollara_bol(td)
        birlesik = birlestir(yollar)["summary"]

    check(birlesik["n_anomaly"] == orijinal["n_anomaly"]
          and birlesik["n_normal"] == orijinal["n_normal"]
          and birlesik["n_anomaly"] > 0 and birlesik["n_normal"] > 0,
          f"n_anomaly/n_normal birebir ({birlesik['n_anomaly']}/{birlesik['n_normal']})")

    duz = ("recall", "risk_cal_anom", "cat_match", "cat_match_eski", "cat_match_grup",
           "normal_fp", "normal_fp_operational", "normal_dispatch_fp",
           "risk_cal_norm", "latency_median")
    for alan in duz:
        check(yakin(birlesik.get(alan), orijinal.get(alan)),
              f"{alan}: birlesik={birlesik.get(alan)} == orijinal={orijinal.get(alan)}")


# ===========================================================================
def test_2_ci_sozlugu_birebir() -> None:
    """ci{} altindaki her metrigin k/n/p/ci_low/ci_high degerleri de birebir."""
    print("TEST 2 — Wilson CI sozlugu birebir")
    if not os.path.exists(ARSIV):
        print("  [ATLA] arsiv dosyasi yok")
        return
    import tempfile
    with open(ARSIV, encoding="utf-8") as f:
        orijinal = json.load(f)["summary"]
    with tempfile.TemporaryDirectory() as td:
        birlesik = birlestir(_kollara_bol(td))["summary"]

    o_ci, b_ci = orijinal.get("ci") or {}, birlesik["ci"]
    check(set(b_ci) == set(o_ci), f"ci anahtar kumesi ayni (fark: {set(b_ci) ^ set(o_ci) or 'yok'})")
    for metrik in sorted(set(b_ci) & set(o_ci)):
        b, o = b_ci[metrik], o_ci[metrik]
        ayni = (b.get("k") == o.get("k") and b.get("n") == o.get("n")
                and yakin(b.get("p"), o.get("p"))
                and yakin(b.get("ci_low"), o.get("ci_low"))
                and yakin(b.get("ci_high"), o.get("ci_high")))
        check(ayni, f"ci[{metrik}]: k/n/p/CI birebir "
                    f"({b.get('k')}/{b.get('n')} vs {o.get('k')}/{o.get('n')})")


# ===========================================================================
def test_3_arsiv_vintage() -> None:
    """D28 ONCESI kosuda `category_match_eski` alani HIC YOKTUR.

    Bunu 0.0 diye raporlamak "olculdu ve SIFIR cikti" iddiasidir — yanlis ve
    tehlikeli (taban cizgisini olmadigi yerde sifir gosterir). Dogru davranis:
    None birakip "olculmedi" demek.
    """
    print("TEST 3 — arsiv vintage'i (D28 oncesi alanlar)")
    if not os.path.exists(ARSIV_ESKI):
        print("  [ATLA] eski arsiv dosyasi yok")
        return
    import tempfile
    with open(ARSIV_ESKI, encoding="utf-8") as f:
        veri = json.load(f)
    anom = [r for r in veri["rows"] if r.get("is_anomaly")]
    check(not any("category_match_eski" in r for r in anom),
          "on kosul: bu arsivde 'category_match_eski' alani GERCEKTEN yok (D28 oncesi)")

    with tempfile.TemporaryDirectory() as td:
        b = birlestir(_kollara_bol(td, ARSIV_ESKI))["summary"]
    check(b["cat_match_eski"] is None and b["cat_match_grup"] is None,
          f"eksik D28 alanlari None kaliyor, 0.0 DEGIL "
          f"(eski={b['cat_match_eski']}, grup={b['cat_match_grup']})")
    check(b["ci"]["cat_match_eski"] is None,
          "ci sozlugunde de None — sahte %0 taban cizgisi uretilmiyor")
    # Alani OLAN metrikler yine de dogru hesaplanmali
    check(yakin(b["recall"], veri["summary"]["recall"])
          and yakin(b["cat_match"], veri["summary"]["cat_match"]),
          f"ayni dosyada MEVCUT alanlar yine birebir "
          f"(recall={b['recall']}, cat_match={b['cat_match']})")


# ===========================================================================
def test_4_tek_kol_eksik_ozet() -> None:
    """Tek kol TEK BASINA eksik ozet verir — bu aracin VAROLUS sebebi."""
    print("TEST 4 — tek kol eksik ozet uretir (aracin gerekcesi)")
    if not os.path.exists(ARSIV):
        print("  [ATLA] arsiv dosyasi yok")
        return
    with open(ARSIV, encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    yalniz_anom = [r for r in rows if r.get("is_anomaly")]
    yalniz_norm = [r for r in rows if not r.get("is_anomaly")]

    s_a = ozet_hesapla(yalniz_anom)
    s_n = ozet_hesapla(yalniz_norm)
    check(s_a["ci"]["normal_fp"]["n"] == 0,
          "Anomali kolunda normal_fp paydasi 0 (tek basina raporlanamaz)")
    check(s_n["ci"]["recall"]["n"] == 0,
          "Normal kolunda recall paydasi 0 (tek basina raporlanamaz)")
    check(s_a["ci"]["recall"]["n"] == len(yalniz_anom)
          and s_n["ci"]["normal_fp"]["n"] == len(yalniz_norm),
          "her kol KENDI metriginde tam paydali")


# ===========================================================================
def test_5_cift_sayim_kapisi() -> None:
    """Ayni klip iki kolda ise UYARI listesine girmeli (K10 kol-arasi bosluk)."""
    print("TEST 5 — kollar arasi cift sayim kapisi")
    import tempfile
    satir = {"path": "data/x/A/k.mp4", "category": "A", "is_anomaly": True,
             "n_events": 1, "max_severity": 2, "risk_ord": 2, "category_match": True,
             "latency_s": 1.0, "triggered": [], "events": []}
    with tempfile.TemporaryDirectory() as td:
        yollar = []
        for i in (1, 2):
            p = os.path.join(td, f"k{i}.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"eval_dir": "data/x", "rows": [dict(satir)]}, f)
            yollar.append(p)
        b = birlestir(yollar)
    check(b["birlesim"]["kollar_arasi_tekrar"] == ["data/x/A/k.mp4"],
          "ayni yol iki kolda -> tekrar listesinde (sessizce cift SAYILMIYOR)")
    check(b["birlesim"]["n_toplam"] == 2,
          "satirlar yine de atilmiyor; karar operatorde (fail-open, K3)")


# ===========================================================================
def test_6_bos_kenar() -> None:
    """Bos satir listesi COKME uretmemeli (K3 fail-open)."""
    print("TEST 6 — bos/kenar durumlar")
    try:
        s = ozet_hesapla([])
        ok = (s["n_anomaly"] == 0 and s["n_normal"] == 0 and s["latency_median"] == 0)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"        cokme: {type(e).__name__}: {e}")
    check(ok, "bos satir listesi COKMUYOR, sifir paydali ozet donuyor")


# ===========================================================================
def main() -> int:
    for fn in (test_1_yuvarlak_yolculuk, test_2_ci_sozlugu_birebir,
               test_3_arsiv_vintage, test_4_tek_kol_eksik_ozet,
               test_5_cift_sayim_kapisi, test_6_bos_kenar):
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
