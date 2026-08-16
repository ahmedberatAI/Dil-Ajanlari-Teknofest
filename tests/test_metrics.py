#!/usr/bin/env python
"""benchmark/metrics.py birim testleri. GPU/vLLM/model/pytest GEREKTIRMEZ.

    python tests/test_metrics.py        # cikis kodu 0 = hepsi gecti

YONTEM: her formul, ELDE HESAPLANABILIR kucuk bir ornekle dogrulanir. Beklenen
degerin NEREDEN geldigi her testin yorumunda ARITMETIK OLARAK gosterilir — "kod ne
donduruyorsa o dogrudur" tuzagina dusmemek icin beklenen degerler koddan DEGIL,
elle yapilan hesaptan gelir.

KAPSAM
  1  BILINEN 2x2      : TP=8 FP=2 TN=7 FN=3 -> P/R/F1/F2/F0.5/MCC/kappa elle hesaplandi
  2  MUKEMMEL/TERS    : mukemmel -> hepsi 1.0 ; tamamen yanlis -> MCC = -1, kappa = -1
  3  DENGESIZ SINIF   : accuracy 0.95 ama MCC 0.295 — metrigin NEDEN gerektigini kanitlar
  4  KENAR DURUMLAR   : sifira bolme, tek sinif, bos girdi -> COKME YOK, 0.0 DEGIL None
  5  F-BETA           : kapali form ile P/R formu ozdes; beta yonu dogru (F2 recall'a doner)
  6  MACRO/MICRO/WGT  : ucunun FARKLI cikitigi bir ornek + micro==accuracy kosulu
  7  COK-SINIFLI KENAR: bos matris, destegi sifir sinif, tek sinif -> COKME YOK
  8  TOP-1 SKORU      : kategori_skoru > 0  <=>  labels.match_category True (tutarlilik)
  9  BERABERLIK       : uc politikanin (belirsiz/sabit/iyimser) davranisi
 10  GERCEK VERI      : arsiv dosyasindan hesaplanan TP, dosyanin KENDI summary'siyle
                        birebir ayni (olcum hattinin arsivle bagi kopmamis)
 11  SISIRME KILIDI   : D32 denetiminde bulunan iki SISIRME yolu kapatildi mi —
                        (a) destegi 0 ama TAHMIN EDILMIS sinif makro ortalamaya
                            0.0 olarak GIRMELI (disarida birakmak skoru sisirir)
                        (b) gercekte hic bulunmayan ama tahmin edilen sinifin FP'leri
                            micro havuzuna GIRMELI
                        + bicimleyiciler tamamen bos matriste COKMEMELI
"""
from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.labels import match_category  # noqa: E402
from benchmark.metrics import (  # noqa: E402
    BELIRSIZ, CokSinifliMatris, IKILI_TANIMLAR, IkiliMatris, coksinifli_matris_bas,
    coksinifli_matris_kur, coksinifli_metrik_tablosu, f_beta_kapali,
    grup_dogrudan_matris, ikili_matris_kur, kategori_skoru, rapor_uret, satir_metni,
    top1_tahmin,
)

_FAILURES: list = []
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Gercek-veri testlerinin dayandigi ARSIV dosyasi (eval_holdout tam kosusu).
ARSIV = os.path.join(ROOT, "benchmark", "results", "evidence_ab_A_20260811_205728.json")

TOL = 1e-9


def check(kosul: bool, mesaj: str) -> None:
    print(("  [OK]   " if kosul else "  [HATA] ") + mesaj)
    if not kosul:
        _FAILURES.append(mesaj)


def yakin(a, b, tol: float = 1e-6) -> bool:
    """None-guvenli yaklasik esitlik (None sadece None'a esittir)."""
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


# ===========================================================================
def test_1_bilinen_2x2() -> None:
    """TP=8, FP=2, TN=7, FN=3 (N=20) — TUM degerler ELLE hesaplandi.

    precision   = TP/(TP+FP)   = 8/10          = 0.800000
    recall      = TP/(TP+FN)   = 8/11          = 0.727273
    specificity = TN/(TN+FP)   = 7/9           = 0.777778
    NPV         = TN/(TN+FN)   = 7/10          = 0.700000
    accuracy    = 15/20                        = 0.750000
    FPR         = 2/9                          = 0.222222
    FNR         = 3/11                         = 0.272727
    F1   = 2TP/(2TP+FP+FN)     = 16/21         = 0.761905
    F2   = 5TP/(5TP+4FN+FP)    = 40/(40+12+2)  = 40/54  = 0.740741
    F0.5 = 1.25TP/(1.25TP+0.25FN+FP) = 10/12.75        = 0.784314
    bal.acc = (8/11 + 7/9)/2                   = 0.752525
    MCC  = (8*7 - 2*3)/sqrt(10*11*9*10) = 50/sqrt(9900) = 50/99.498744 = 0.502519
    kappa: po = 0.75
           pe = (tahminP*gercekP + tahminN*gercekN)/N^2 = (10*11 + 10*9)/400 = 0.5
           kappa = (0.75-0.5)/(1-0.5)          = 0.500000
    """
    print("TEST 1 — bilinen 2x2 matris, elle hesaplanmis referans degerler")
    m = IkiliMatris(tp=8, fp=2, tn=7, fn=3)
    check(m.n == 20 and m.gercek_pozitif == 11 and m.gercek_negatif == 9
          and m.tahmin_pozitif == 10, "kenar toplamlari dogru (N=20, P=11, N=9, tahminP=10)")
    check(yakin(m.precision, 0.800000), f"precision = 0.800000 (gelen {m.precision})")
    check(yakin(m.recall, 8 / 11), f"recall = 0.727273 (gelen {m.recall})")
    check(yakin(m.specificity, 7 / 9), f"specificity = 0.777778 (gelen {m.specificity})")
    check(yakin(m.npv, 0.700000), f"NPV = 0.700000 (gelen {m.npv})")
    check(yakin(m.accuracy, 0.750000), f"accuracy = 0.750000 (gelen {m.accuracy})")
    check(yakin(m.fpr, 2 / 9), f"FPR = 0.222222 (gelen {m.fpr})")
    check(yakin(m.fnr, 3 / 11), f"FNR = 0.272727 (gelen {m.fnr})")
    check(yakin(m.f1, 16 / 21), f"F1 = 0.761905 (gelen {m.f1})")
    check(yakin(m.f2, 40 / 54), f"F2 = 0.740741 (gelen {m.f2})")
    check(yakin(m.f05, 10 / 12.75), f"F0.5 = 0.784314 (gelen {m.f05})")
    check(yakin(m.balanced_accuracy, (8 / 11 + 7 / 9) / 2),
          f"balanced accuracy = 0.752525 (gelen {m.balanced_accuracy})")
    check(yakin(m.mcc, 50.0 / math.sqrt(9900.0)), f"MCC = 0.502519 (gelen {m.mcc})")
    check(yakin(m.cohen_kappa, 0.5), f"Cohen kappa = 0.500000 (gelen {m.cohen_kappa})")
    # FPR/FNR tumleyen iliskisi
    check(yakin(m.fpr + m.specificity, 1.0) and yakin(m.fnr + m.recall, 1.0),
          "FPR = 1-specificity ve FNR = 1-recall ozdesligi saglaniyor")
    # F0.5 > F1 > F2 : precision (0.80) > recall (0.727) oldugundan
    check(m.f05 > m.f1 > m.f2,
          f"precision>recall iken F0.5 > F1 > F2 ({m.f05:.4f} > {m.f1:.4f} > {m.f2:.4f})")


def test_2_mukemmel_ve_tamamen_yanlis() -> None:
    """Ucler: mukemmel siniflandirici ve tam tersi.

    Mukemmel (TP=5, FP=0, TN=5, FN=0): her metrik 1.0.
    Tamamen yanlis (TP=0, FP=5, TN=0, FN=5):
        MCC = (0*0 - 5*5)/sqrt(5*5*5*5) = -25/25 = -1.0
        kappa: po=0, pe=(5*5 + 5*5)/100 = 0.5  ->  (0-0.5)/0.5 = -1.0
    """
    print("TEST 2 — mukemmel siniflandirici / tamamen yanlis siniflandirici")
    iyi = IkiliMatris(tp=5, fp=0, tn=5, fn=0)
    for ad, deger in (("precision", iyi.precision), ("recall", iyi.recall),
                      ("specificity", iyi.specificity), ("npv", iyi.npv),
                      ("accuracy", iyi.accuracy), ("F1", iyi.f1), ("F2", iyi.f2),
                      ("F0.5", iyi.f05), ("bal.acc", iyi.balanced_accuracy),
                      ("MCC", iyi.mcc), ("kappa", iyi.cohen_kappa)):
        check(yakin(deger, 1.0), f"mukemmel siniflandirici: {ad} = 1.0 (gelen {deger})")
    check(yakin(iyi.fpr, 0.0) and yakin(iyi.fnr, 0.0),
          "mukemmel siniflandirici: FPR = FNR = 0.0")

    ters = IkiliMatris(tp=0, fp=5, tn=0, fn=5)
    check(yakin(ters.mcc, -1.0), f"tamamen yanlis: MCC = -1.0 (gelen {ters.mcc})")
    check(yakin(ters.cohen_kappa, -1.0), f"tamamen yanlis: kappa = -1.0 (gelen {ters.cohen_kappa})")
    check(yakin(ters.accuracy, 0.0) and yakin(ters.f1, 0.0),
          "tamamen yanlis: accuracy = 0.0 ve F1 = 0.0 (TANIMSIZ degil — gercekten sifir)")


def test_3_dengesiz_sinif_accuracy_yaniltir() -> None:
    """DENGESIZ SINIF: accuracy yuksek ama MCC dusuk — MCC'nin NEDEN gerektigi.

    100 klip, yalnizca 5'i gercek pozitif (prevalans 0.05).
    Tahminci neredeyse hep 'negatif' diyor: TP=1, FP=1, TN=94, FN=4.
        accuracy = (1+94)/100 = 0.95      <- "%95 basari" gibi gorunur
        precision = 1/2 = 0.5 ; recall = 1/5 = 0.2
        F1  = 2*1/(2+1+4) = 2/7      = 0.285714
        F2  = 5*1/(5+16+1) = 5/22    = 0.227273   (recall dusuk oldugu icin F1'den DUSUK)
        MCC = (1*94 - 1*4)/sqrt(2*5*95*98) = 90/sqrt(93100) = 0.294969
        bal.acc = (0.2 + 94/95)/2 = 0.594737
    Yani accuracy 0.95 derken MCC 0.29 diyor: sistem pozitif sinifta neredeyse KOR.
    """
    print("TEST 3 — dengesiz sinif: accuracy yuksek, MCC dusuk")
    m = IkiliMatris(tp=1, fp=1, tn=94, fn=4)
    check(yakin(m.accuracy, 0.95), f"accuracy = 0.95 (gelen {m.accuracy})")
    check(yakin(m.mcc, 90.0 / math.sqrt(93100.0)), f"MCC = 0.294969 (gelen {m.mcc})")
    check(yakin(m.f1, 2 / 7), f"F1 = 0.285714 (gelen {m.f1})")
    check(yakin(m.f2, 5 / 22), f"F2 = 0.227273 (gelen {m.f2})")
    check(yakin(m.balanced_accuracy, (0.2 + 94 / 95) / 2),
          f"balanced accuracy = 0.594737 (gelen {m.balanced_accuracy})")
    check(m.accuracy - m.mcc > 0.6,
          f"accuracy ({m.accuracy:.3f}) MCC'yi ({m.mcc:.3f}) 0.6'dan fazla sisiriyor "
          "— dengesiz sinifta accuracy TEK BASINA raporlanamaz")
    check(m.accuracy > m.balanced_accuracy > m.f2,
          "accuracy > balanced accuracy > F2 : her duzeltme katmani sisirmeyi geri aliyor")

    # TAMAMEN cokmus tahminci ("hepsi negatif"): accuracy hala 0.95, MCC TANIMSIZ.
    cokmus = IkiliMatris(tp=0, fp=0, tn=95, fn=5)
    check(yakin(cokmus.accuracy, 0.95),
          "hicbir sey tespit etmeyen tahminci de accuracy 0.95 aliyor (!)")
    check(cokmus.mcc is None,
          "cokmus tahminci: MCC TANIMSIZ (None) — payda sifir; '0.0' demek yanlis olurdu")
    check(cokmus.precision is None,
          "cokmus tahminci: precision TANIMSIZ (hic pozitif TAHMIN yok -> 0/0)")
    check(yakin(cokmus.recall, 0.0),
          "cokmus tahminci: recall = 0.0 (TANIMSIZ degil — gercek pozitif VAR, hicbiri bulunamadi)")
    # F1 BURADA TANIMSIZ DEGILDIR: 2TP/(2TP+FP+FN) = 0/(0+0+5) = 0.0. precision 0/0
    # oldugu halde F1'in tanimli olmasi, kapali formun tam da bu ise yaradigini gosterir.
    check(yakin(cokmus.f1, 0.0),
          "cokmus tahminci: F1 = 0.0 — precision TANIMSIZ olsa bile F1 kapali formla "
          "TANIMLI (FN=5>0), ve 0.0 burada DOGRU bir iddia")
    check(yakin(cokmus.f2, 0.0) and cokmus.balanced_accuracy is not None,
          "cokmus tahminci: F2 = 0.0 ve balanced accuracy hesaplanabiliyor")


def test_4_kenar_durumlar_cokme_yok() -> None:
    """Sifira bolme / tek sinif / bos girdi — hicbiri COKMEMELI, 0.0 DEGIL None donmeli."""
    print("TEST 4 — kenar durumlar: sifira bolme, tek sinif, bos girdi")
    bos = IkiliMatris(tp=0, fp=0, tn=0, fn=0)
    check(bos.n == 0, "bos matris: N = 0")
    for ad, deger in (("precision", bos.precision), ("recall", bos.recall),
                      ("specificity", bos.specificity), ("npv", bos.npv),
                      ("accuracy", bos.accuracy), ("F1", bos.f1), ("F2", bos.f2),
                      ("bal.acc", bos.balanced_accuracy), ("MCC", bos.mcc),
                      ("kappa", bos.cohen_kappa), ("prevalans", bos.prevalans)):
        check(deger is None, f"bos matris: {ad} = None (0.0 DEGIL)")
    check(isinstance(bos.to_dict(), dict), "bos matris: to_dict() COKMUYOR")

    # TEK SINIF — hepsi negatif ve hepsi dogru bilinmis
    tek_neg = IkiliMatris(tp=0, fp=0, tn=10, fn=0)
    check(tek_neg.precision is None, "tek sinif (hepsi negatif): precision TANIMSIZ")
    check(tek_neg.recall is None, "tek sinif (hepsi negatif): recall TANIMSIZ (gercek pozitif YOK)")
    check(yakin(tek_neg.specificity, 1.0), "tek sinif (hepsi negatif): specificity = 1.0")
    check(tek_neg.f1 is None, "tek sinif (hepsi negatif): F1 TANIMSIZ (TP=FP=FN=0)")
    check(tek_neg.cohen_kappa is None, "tek sinif (hepsi negatif): kappa TANIMSIZ (pe = 1)")
    check(yakin(tek_neg.accuracy, 1.0), "tek sinif (hepsi negatif): accuracy = 1.0")

    # TEK SINIF — hepsi pozitif ve hepsi dogru bilinmis
    tek_poz = IkiliMatris(tp=10, fp=0, tn=0, fn=0)
    check(tek_poz.specificity is None and tek_poz.npv is None,
          "tek sinif (hepsi pozitif): specificity ve NPV TANIMSIZ")
    check(yakin(tek_poz.f1, 1.0), "tek sinif (hepsi pozitif): F1 = 1.0")
    check(tek_poz.mcc is None, "tek sinif (hepsi pozitif): MCC TANIMSIZ")
    check(tek_poz.balanced_accuracy is None,
          "tek sinif (hepsi pozitif): balanced accuracy TANIMSIZ (specificity yok)")

    # BOS SATIR LISTESI -> matris kurucusu cokmemeli
    bos_m = ikili_matris_kur([], IKILI_TANIMLAR[0][3])
    check(bos_m.n == 0, "ikili_matris_kur([]) COKMUYOR, N = 0 doner")

    # EKSIK ALANLI satirlar (arsiv uyumu / fail-open): KeyError ATMAMALI
    eksik = [{"is_anomaly": True}, {"is_anomaly": False}, {}]
    for _anahtar, _ad, _tanim, fn in IKILI_TANIMLAR:
        m = ikili_matris_kur(eksik, fn)
        check(m.n == 3, f"eksik alanli satirlar fail-open: {_anahtar} tanimi cokmedi (N=3)")


def test_5_f_beta() -> None:
    """F-beta kapali formu ile P/R formu OZDES; beta yonu dogru."""
    print("TEST 5 — F-beta: kapali form == P/R formu, beta yonu dogru")
    for tp, fp, fn in ((8, 2, 3), (1, 1, 4), (5, 0, 0), (0, 3, 7), (12, 9, 1)):
        p = tp / (tp + fp) if (tp + fp) else None
        r = tp / (tp + fn) if (tp + fn) else None
        for beta in (0.5, 1.0, 2.0):
            kapali = f_beta_kapali(tp, fp, fn, beta)
            if p is None or r is None or (p == 0 and r == 0):
                continue
            b2 = beta * beta
            pr = ((1 + b2) * p * r / (b2 * p + r)) if (b2 * p + r) else 0.0
            check(yakin(kapali, pr, 1e-12),
                  f"F{beta} kapali form == P/R formu  (TP={tp} FP={fp} FN={fn}: "
                  f"{kapali:.9f} vs {pr:.9f})")
    check(f_beta_kapali(0, 0, 0, 1.0) is None,
          "F1(TP=FP=FN=0) TANIMSIZ -> None (sinif hic yok VE hic tahmin edilmemis)")
    check(yakin(f_beta_kapali(0, 5, 5, 1.0), 0.0),
          "F1(TP=0, FP=5, FN=5) = 0.0 — bu TANIMSIZ degil, gercekten sifir")

    # BETA YONU: recall dusuk / precision yuksek bir noktada F2 < F1 < F0.5 olmali
    dusuk_recall = IkiliMatris(tp=2, fp=0, tn=0, fn=8)   # P=1.00, R=0.20
    check(dusuk_recall.f2 < dusuk_recall.f1 < dusuk_recall.f05,
          f"recall dusuk (P=1.0, R=0.2): F2 {dusuk_recall.f2:.3f} < F1 "
          f"{dusuk_recall.f1:.3f} < F0.5 {dusuk_recall.f05:.3f} — F2 recall'i CEZALANDIRIYOR")
    dusuk_prec = IkiliMatris(tp=8, fp=32, tn=0, fn=0)    # P=0.20, R=1.00
    check(dusuk_prec.f05 < dusuk_prec.f1 < dusuk_prec.f2,
          f"precision dusuk (P=0.2, R=1.0): F0.5 {dusuk_prec.f05:.3f} < F1 "
          f"{dusuk_prec.f1:.3f} < F2 {dusuk_prec.f2:.3f} — F2 recall'i ODULLENDIRIYOR")


def test_6_macro_micro_weighted_farki() -> None:
    """MACRO / MICRO / WEIGHTED F1 farkinin GORUNDUGU ornek.

    A sinifi 90 ornek, B sinifi 10 ornek (dengesiz).
    Tahminler: A'nin hepsi dogru; B'nin 2'si dogru, 8'i A denmis.
        (A,A)=90 ; (B,B)=2 ; (B,A)=8    -> N=100, kosegen = 92
        accuracy = 92/100 = 0.920000
        A: TP=90 FP=8 FN=0 -> F1 = 180/(180+8+0) = 180/188 = 0.957447
        B: TP=2  FP=0 FN=8 -> F1 =   4/(4+0+8)   =   4/12  = 0.333333
        MACRO-F1    = (0.957447 + 0.333333)/2                = 0.645390
        WEIGHTED-F1 = (90*0.957447 + 10*0.333333)/100        = 0.895035
        MICRO-F1    : TP=92 FP=8 FN=8 -> 184/(184+8+8) = 0.920000  == accuracy
    Yorum: MACRO kucuk sinifta cokmeyi GORUYOR (0.645), WEIGHTED ve MICRO GIZLIYOR.
    """
    print("TEST 6 — MACRO vs MICRO vs WEIGHTED F1 farki")
    m = CokSinifliMatris(siniflar=["A", "B"], tahminler=["A", "B"])
    m.hucre = {("A", "A"): 90, ("B", "B"): 2, ("B", "A"): 8}
    f1_a, f1_b = 180 / 188, 4 / 12
    check(yakin(m.accuracy, 0.92), f"accuracy = 0.920000 (gelen {m.accuracy})")
    check(yakin(m.bir_vs_hepsi("A").f1, f1_a), f"A sinifi F1 = 0.957447")
    check(yakin(m.bir_vs_hepsi("B").f1, f1_b), f"B sinifi F1 = 0.333333")
    check(yakin(m.macro_f1(), (f1_a + f1_b) / 2), f"MACRO-F1 = 0.645390 (gelen {m.macro_f1()})")
    check(yakin(m.weighted_f1(), (90 * f1_a + 10 * f1_b) / 100),
          f"WEIGHTED-F1 = 0.895035 (gelen {m.weighted_f1()})")
    check(yakin(m.micro_f1(), 0.92), f"MICRO-F1 = 0.920000 (gelen {m.micro_f1()})")
    check(yakin(m.micro_f1(), m.accuracy),
          "BELIRSIZ sutunu YOKKEN micro-F1 == accuracy (tek etiketli cok-sinifta ozdeslik)")
    check(m.macro_f1() < m.weighted_f1() < m.micro_f1(),
          f"MACRO ({m.macro_f1():.3f}) < WEIGHTED ({m.weighted_f1():.3f}) < "
          f"MICRO ({m.micro_f1():.3f}) — uc sayi AYNI SEY DEGIL")

    # BELIRSIZ sutunu eklenince micro-F1 accuracy'den AYRILIR (rapordaki notun kaniti)
    m2 = CokSinifliMatris(siniflar=["A", "B"], tahminler=["A", "B", BELIRSIZ])
    m2.hucre = {("A", "A"): 90, ("B", "B"): 2, ("B", "A"): 3, ("B", BELIRSIZ): 5}
    check(yakin(m2.accuracy, 0.92), f"BELIRSIZ'li ornek: accuracy = 0.92 (gelen {m2.accuracy})")
    check(yakin(m2.micro_f1(), 184 / 195),
          f"BELIRSIZ'li ornek: micro-F1 = 184/195 = 0.943590 (gelen {m2.micro_f1()})")
    check(not yakin(m2.micro_f1(), m2.accuracy),
          "BELIRSIZ tahmin FN yaziyor ama FP yazmiyor -> micro-F1 != accuracy")

    # Cok-sinifli Cohen kappa: elle hesap
    #   po = 0.92 ; pe = (satirA*sutunA + satirB*sutunB)/N^2 = (90*98 + 10*2)/10000 = 0.8840
    #   kappa = (0.92 - 0.884)/(1 - 0.884) = 0.036/0.116 = 0.310345
    check(yakin(m.cohen_kappa(), 0.036 / 0.116),
          f"cok-sinifli Cohen kappa = 0.310345 (gelen {m.cohen_kappa()})")


def test_7_coksinifli_kenar_durumlar() -> None:
    """Bos matris, destegi SIFIR sinif, tek sinif — COKME YOK."""
    print("TEST 7 — cok-sinifli kenar durumlar")
    bos = CokSinifliMatris(siniflar=[], tahminler=[])
    check(bos.n == 0, "bos cok-sinifli matris: N = 0")
    check(bos.accuracy is None and bos.macro_f1() is None and bos.micro_f1() is None
          and bos.cohen_kappa() is None and bos.weighted_f1() is None,
          "bos cok-sinifli matris: TUM metrikler None, COKME YOK")
    check(isinstance(bos.to_dict(), dict), "bos cok-sinifli matris: to_dict() COKMUYOR")

    # DESTEGI SIFIR sinif: 'C' bildirildi ama hic ornegi yok -> makro ortalamayi BOZMAMALI
    m = CokSinifliMatris(siniflar=["A", "B", "C"], tahminler=["A", "B", "C"])
    m.hucre = {("A", "A"): 4, ("B", "B"): 4}
    check(m.destek("C") == 0, "destegi sifir sinif tespit edildi")
    check(yakin(m.macro_f1(), 1.0),
          f"destegi sifir sinif makro ortalamaya 0.0 olarak GIRMIYOR "
          f"(macro = {m.macro_f1()}, beklenen 1.0)")
    check(m.bir_vs_hepsi("C").f1 is None,
          "destegi sifir ve hic tahmin edilmemis sinif: F1 TANIMSIZ (None)")

    # TEK SINIF: kappa TANIMSIZ (pe = 1)
    tek = CokSinifliMatris(siniflar=["A"], tahminler=["A"])
    tek.hucre = {("A", "A"): 7}
    check(yakin(tek.accuracy, 1.0), "tek sinif: accuracy = 1.0")
    check(tek.cohen_kappa() is None, "tek sinif: Cohen kappa TANIMSIZ (pe = 1, sifira bolme)")

    # HEPSI BELIRSIZ: hic dogru tahmin yok
    hic = CokSinifliMatris(siniflar=["A", "B"], tahminler=["A", "B", BELIRSIZ])
    hic.hucre = {("A", BELIRSIZ): 5, ("B", BELIRSIZ): 5}
    check(yakin(hic.accuracy, 0.0), "hepsi BELIRSIZ: accuracy = 0.0")
    check(yakin(hic.micro_f1(), 0.0), "hepsi BELIRSIZ: micro-F1 = 0.0 (TP=0, FN=10)")
    check(hic.cohen_kappa() is not None and yakin(hic.cohen_kappa(), 0.0),
          f"hepsi BELIRSIZ: kappa = 0.0 (po=0, pe=0) (gelen {hic.cohen_kappa()})")

    # BOS SATIR LISTESI -> coksinifli kurucu cokmemeli
    mm, ayr = coksinifli_matris_kur([], ["Fighting"])
    check(mm.n == 0 and ayr == [], "coksinifli_matris_kur([]) COKMUYOR")
    gm, gb = grup_dogrudan_matris([], ["Fighting"])
    check(gm.n == 0 and gb == 0, "grup_dogrudan_matris([]) COKMUYOR")


def test_8_top1_skoru_labels_ile_tutarli() -> None:
    """kategori_skoru > 0  <=>  labels.match_category(...) True.

    Top-1 katmani, D28'de ONARILMIS eslestiriciyle AYNI karari vermelidir; aksi
    halde iki ayri "eslesme" tanimi ortaya cikar ve tablolar kiyaslanamaz olur.
    """
    print("TEST 8 — kategori_skoru, labels.match_category ile TUTARLI")
    ornekler = [
        "iki kişi arasında kavga çıktı",
        "araç çarpması sonucu trafik kazası meydana geldi",
        "kırmızı bir obje taşıyan kişi",              # "kır" TETIKLEMEMELI
        "olayın önemi vurgulanmadı",                  # "vur" TETIKLEMEMELI
        "düşük çözünürlüklü görüntü",                 # "düş" TETIKLEMEMELI
        "yangın gözlenmedi",                          # olumsuzlama kapisi
        "İstismar şüphesi var",                       # Turkce buyuk I
        "yerde hareketsiz yatan bir kişi",
        "",
    ]
    kategoriler = ["RoadAccidents", "Explosion", "Fighting", "Assault", "Abuse",
                   "Burglary", "Shooting", "Vandalism", "Fire", "Smoke", "Fall", "Normal"]
    uyumsuz = []
    for t in ornekler:
        for c in kategoriler:
            s = kategori_skoru(t, c)
            m = match_category(t, c)
            if (s > 0) != m:
                uyumsuz.append((t[:30], c, s, m))
    check(not uyumsuz, f"tum ornek x kategori ciftlerinde skor>0 <=> match_category "
                       f"(uyumsuz: {uyumsuz})")
    check(kategori_skoru("yangın gözlenmedi", "Fire") == 0,
          "olumsuzlama kapisi skora da uygulaniyor: 'yangın gözlenmedi' -> Fire skoru 0")
    check(kategori_skoru("kırmızı bir obje", "Burglary") == 0,
          "kelime siniri skora da uygulaniyor: 'kırmızı' -> Burglary skoru 0")
    check(kategori_skoru("", "Fighting") == 0 and kategori_skoru("x", "Normal") == 0,
          "bos metin ve kalipsiz kategori (Normal) skoru 0 — COKME YOK")
    # SKOR ARTIYOR MU: daha cok farkli kalip -> daha yuksek skor
    az = kategori_skoru("trafik kazası oldu", "RoadAccidents")
    cok = kategori_skoru("trafik kazası oldu, araç çarptı ve devrildi", "RoadAccidents")
    check(cok > az, f"daha cok FARKLI kalip eslesince skor artiyor ({az} -> {cok})")


def test_9_beraberlik_politikalari() -> None:
    """Uc beraberlik politikasinin davranisi (top-1 tasarim kararinin keyfi yeri)."""
    print("TEST 9 — beraberlik politikalari: belirsiz / sabit / iyimser")
    adaylar = ["Fighting", "Assault", "Abuse", "RoadAccidents", "Burglary",
               "Explosion", "Shooting", "Vandalism"]

    # "kavga" hem Fighting hem Assault kalibi -> BERABERLIK
    t = "iki kişi arasında kavga çıktı"
    p1, s1, b1 = top1_tahmin(t, adaylar, beraberlik="belirsiz")
    check(b1 and p1 == BELIRSIZ,
          f"beraberlikte varsayilan politika ALEYHIMIZE: {p1} (skorlar Figh={s1['Fighting']}, "
          f"Assa={s1['Assault']})")
    p2, _s2, b2 = top1_tahmin(t, adaylar, beraberlik="sabit")
    check(b2 and p2 in ("Fighting", "Assault") and p2 != BELIRSIZ,
          f"'sabit' politika beraberligi DETERMINISTIK cozuyor -> {p2}")
    p3, _s3, _b3 = top1_tahmin(t, adaylar, beraberlik="iyimser", gercek="Assault")
    check(p3 == "Assault",
          "'iyimser' politika beraberligi GERCEK sinif lehine cozer (UST SINIR, "
          "calisma zamaninda UYGULANAMAZ)")
    p4, _s4, _b4 = top1_tahmin(t, adaylar, beraberlik="iyimser", gercek="Explosion")
    check(p4 == BELIRSIZ,
          "'iyimser' politika gercek sinif kazananlar arasinda DEGILSE hediye VERMIYOR")

    # Tek kazanan: beraberlik yok, uc politika da AYNI cevabi vermeli
    t2 = "araç çarpması sonucu trafik kazası meydana geldi ve araç devrildi"
    cevaplar = {pol: top1_tahmin(t2, adaylar, beraberlik=pol, gercek="RoadAccidents")[0]
                for pol in ("belirsiz", "sabit", "iyimser")}
    check(set(cevaplar.values()) == {"RoadAccidents"},
          f"tek kazanan varken uc politika da AYNI: {cevaplar}")

    # Hicbir kalip eslesmiyor -> BELIRSIZ, hangi politika olursa olsun
    t3 = "hava bugün oldukça ılıman"
    check(all(top1_tahmin(t3, adaylar, beraberlik=pol, gercek="Fighting")[0] == BELIRSIZ
              for pol in ("belirsiz", "sabit", "iyimser")),
          "hicbir kalip eslesmezse HER politika BELIRSIZ der (iyimser bile hediye vermez)")
    check(top1_tahmin("herhangi bir metin", [], beraberlik="belirsiz")[0] == BELIRSIZ,
          "BOS aday kumesi COKMUYOR -> BELIRSIZ")


def test_10_gercek_veri_arsivle_tutarli() -> None:
    """HAT DOGRULAMASI: gercek arsiv dosyasindan hesaplanan sayimlar, dosyanin
    KENDI summary blogundaki k/n degerleriyle BIREBIR ayni olmali.

    Ayni sey degilse metrics.py arsivden KOPMUS demektir ve butun tablolar supheli.
    """
    print("TEST 10 — gercek arsiv verisiyle hat dogrulamasi")
    if not os.path.exists(ARSIV):
        check(False, f"arsiv dosyasi bulunamadi: {ARSIV}")
        return
    with open(ARSIV, encoding="utf-8") as f:
        veri = json.load(f)
    rows = veri["rows"]
    ozet = veri["summary"]
    fn_map = {a: fn for a, _ad, _t, fn in IKILI_TANIMLAR}

    # (1) GEVSEK tanim TP'si == summary.recall.k  (recall = anomalide n_events>0)
    m_gevsek = ikili_matris_kur(rows, fn_map["gevsek"])
    check(m_gevsek.tp == ozet["ci"]["recall"]["k"] and
          m_gevsek.gercek_pozitif == ozet["ci"]["recall"]["n"],
          f"GEVSEK TP/P = {m_gevsek.tp}/{m_gevsek.gercek_pozitif} == "
          f"summary.recall {ozet['ci']['recall']['k']}/{ozet['ci']['recall']['n']}")

    # (2) SIKI tanimin FP'si == summary.normal_fp.k  (normalde sev>=3 veya risk>=3)
    m_siki = ikili_matris_kur(rows, fn_map["siki"])
    check(m_siki.fp == ozet["ci"]["normal_fp"]["k"] and
          m_siki.gercek_negatif == ozet["ci"]["normal_fp"]["n"],
          f"SIKI FP/N = {m_siki.fp}/{m_siki.gercek_negatif} == "
          f"summary.normal_fp {ozet['ci']['normal_fp']['k']}/{ozet['ci']['normal_fp']['n']}")

    # (3) SIKI tanimin TP'si == summary.risk_cal_anom.k'den BUYUK VEYA ESIT
    #     (risk_cal_anom yalniz risk_ord>=3'e bakar; SIKI ayrica max_severity>=3'u de sayar)
    check(m_siki.tp >= ozet["ci"]["risk_cal_anom"]["k"],
          f"SIKI TP ({m_siki.tp}) >= summary.risk_cal_anom.k "
          f"({ozet['ci']['risk_cal_anom']['k']}) — SIKI daha genis bir kosul")

    # (4) SEVK tanimin FP'si == summary.normal_dispatch_fp.k
    m_sevk = ikili_matris_kur(rows, fn_map["sevk"])
    check(m_sevk.fp == ozet["ci"]["normal_dispatch_fp"]["k"],
          f"SEVK FP = {m_sevk.fp} == summary.normal_dispatch_fp.k "
          f"({ozet['ci']['normal_dispatch_fp']['k']})")

    # (5) Her tanimda TP+FP+TN+FN == toplam klip sayisi (hucre kaybi yok)
    for anahtar, _ad, _t, fn in IKILI_TANIMLAR:
        m = ikili_matris_kur(rows, fn)
        check(m.n == len(rows),
              f"{anahtar}: TP+FP+TN+FN = {m.n} == satir sayisi {len(rows)} (hucre kaybi yok)")

    # (6) Cok-sinifli matriste hucre toplami == anomali klip sayisi
    anom = [r for r in rows if r["is_anomaly"]]
    adaylar = sorted({r["category"] for r in anom})
    m_cok, ayrinti = coksinifli_matris_kur(anom, adaylar)
    check(m_cok.n == len(anom) == len(ayrinti),
          f"cok-sinifli matris hucre toplami {m_cok.n} == anomali klip {len(anom)}")
    check(all(m_cok.destek(c) == 3 for c in adaylar),
          "her sinifin destegi 3 (8 sinif x 3 klip = 24) — kurgu dogrulandi")

    # (7) TOP-1 accuracy, cat_match'ten DUSUK OLMALI: cat_match "gercek sinifin kelimesi
    #     var mi" der ve ayni metinde baska siniflar da tetiklenmisse yine 'dogru' sayar.
    #     Top-1 ise TEK bir kazanan secer; beraberlikte kaybeder. Ikisi AYNI SEY DEGILDIR.
    cat_match_k = ozet["ci"]["cat_match"]["k"]
    dogru_top1 = sum(m_cok.say(c, c) for c in adaylar)
    check(dogru_top1 <= cat_match_k,
          f"top-1 dogru sayisi ({dogru_top1}) <= cat_match ({cat_match_k}) — "
          "top-1 DAHA SIKI bir olcut, cat_match'in yerine gecmez")

    # (8) Grup duzeyi >= kategori duzeyi (gruplama ayrimi TOLERE eder, ZORLASTIRMAZ)
    m_grup2, _b = grup_dogrudan_matris(anom, adaylar)
    check(m_grup2.accuracy >= m_cok.accuracy,
          f"DOGRUDAN grup accuracy ({m_grup2.accuracy:.3f}) >= kategori accuracy "
          f"({m_cok.accuracy:.3f}) — gruplama ayrimi tolere eder")

    # (9) rapor_uret ucdan uca cokmuyor ve JSON serilestirilebilir
    satirlar, js = rapor_uret(ARSIV)
    check(len(satirlar) > 100, f"rapor_uret {len(satirlar)} satir uretti")
    try:
        json.dumps(js, ensure_ascii=False)
        ok = True
    except (TypeError, ValueError) as e:
        ok = False
        print(f"        JSON hatasi: {e}")
    check(ok, "rapor_uret ciktisi JSON'a serilestirilebiliyor")
    check(js["n_toplam"] == 32 and js["n_anomali"] == 24 and js["n_normal"] == 8,
          f"rapor JSON sayimlari: {js['n_toplam']} = {js['n_anomali']} + {js['n_normal']}")

    # (10) satir_metni bos satirda cokmuyor
    check(satir_metni({}) == "", "satir_metni({}) = '' — eksik alanda COKME YOK")


def test_11_sisirme_kilitleri() -> None:
    """D32 MATEMATIK DENETIMI — kapatilan iki SISIRME yolunun REGRESYON KILIDI.

    (a) DESTEGI 0 AMA TAHMIN EDILMIS SINIF
        siniflar = [A, B, C], hucre = {(A,A):4, (B,B):3, (B,C):1}
        C'nin GERCEK ornegi yok (destek 0) ama model onu 1 kez TAHMIN etti:
            C: TP=0, FP=1, FN=0  ->  F1 = 2*0/(0+1+0) = 0.0   (TANIMLI! 0/0 DEGIL)
        A: TP=4 FP=0 FN=0 -> F1 = 1.000000
        B: TP=3 FP=0 FN=1 -> F1 = 6/7 = 0.857143
        DOGRU  macro = (1.000000 + 0.857143 + 0.0)/3 = 0.619048
        YANLIS macro = (1.000000 + 0.857143)/2       = 0.928571   <- +0.31 SISIRME
        Onarim oncesi modul YANLIS olani veriyordu.

    (b) DESTEGI 0 VE HIC TAHMIN EDILMEMIS SINIF — bu farkli bir durumdur:
        C: TP=FP=FN=0 -> F1 gercekten 0/0'dir, TANIMSIZDIR, ortalamaya GIRMEZ.
        Bunu 0.0 saymak skoru HAKSIZ YERE dusururdu. (TEST 7 bu yonu koruyor.)

    (c) MICRO havuzu: (a) ornegindeki C'nin FP'si micro toplamina girmeli.
        TP=7, FP=1, FN=1 -> micro-F1 = 14/(14+1+1) = 14/16 = 0.875000
        C disarida birakilsaydi TP=7 FP=0 FN=1 -> 14/15 = 0.933333  <- SISIRME
    """
    print("TEST 11 — SISIRME kilitleri (D32 denetimi) + bos matris bicimleyici")
    m = CokSinifliMatris(siniflar=["A", "B", "C"], tahminler=["A", "B", "C"])
    m.hucre = {("A", "A"): 4, ("B", "B"): 3, ("B", "C"): 1}
    c = m.bir_vs_hepsi("C")
    check(m.destek("C") == 0 and c.tp == 0 and c.fp == 1 and c.fn == 0,
          f"C: destek=0 ama FP=1 (tahmin edilmis) — TP={c.tp} FP={c.fp} FN={c.fn}")
    check(yakin(c.f1, 0.0),
          f"destegi 0 AMA tahmin edilmis sinifin F1'i 0.0 — TANIMLI, 0/0 DEGIL (gelen {c.f1})")
    check(yakin(m.macro_f1(), (1.0 + 6 / 7 + 0.0) / 3),
          f"macro-F1 = 0.619048 — saf-FP sinifi ortalamaya 0.0 olarak GIRIYOR "
          f"(gelen {m.macro_f1()}); disarida birakan surum 0.928571 verirdi (SISIRME)")
    check(m.macro_f1() < 0.928571,
          f"SISIRME KILIDI: macro-F1 ({m.macro_f1():.6f}) eski/yanlis degerin (0.928571) ALTINDA")
    check(m.micro_toplamlari() == (7, 1, 1),
          f"micro havuzu saf-FP sinifini iceriyor: TP/FP/FN = {m.micro_toplamlari()} "
          "(beklenen (7, 1, 1))")
    check(yakin(m.micro_f1(), 14 / 16),
          f"micro-F1 = 0.875000 (gelen {m.micro_f1()}); C disarida kalsaydi 0.933333 olurdu")
    # WEIGHTED etkilenmez: destek 0 -> agirlik 0 (sklearn ile ayni)
    check(yakin(m.weighted_f1(), (4 * 1.0 + 4 * (6 / 7)) / 8),
          f"weighted-F1 destek agirlikli oldugu icin DEGISMEZ (gelen {m.weighted_f1()})")

    # (d) ETIKET KUMESI: gercekte hic olmayan ama TAHMIN EDILEN sinif kumeye GIRER,
    #     BELIRSIZ (cekimserlik) GIRMEZ.
    m2 = CokSinifliMatris(siniflar=["A", "B"], tahminler=["A", "B", "Z", BELIRSIZ])
    m2.hucre = {("A", "A"): 5, ("B", "Z"): 3, ("A", BELIRSIZ): 2}
    check(m2.etiket_kumesi() == ["A", "B", "Z"],
          f"etiket kumesi = satirlar U sutunlar, BELIRSIZ HARIC (gelen {m2.etiket_kumesi()})")
    #   Z: TP=0 FP=3 FN=0 -> F1 0.0 ; A: TP=5 FP=0 FN=2 -> 10/12 ; B: TP=0 FP=0 FN=3 -> 0.0
    check(yakin(m2.macro_f1(), (10 / 12 + 0.0 + 0.0) / 3),
          f"gercekte olmayan Z sinifi makroya 0.0 ile giriyor (gelen {m2.macro_f1()})")
    check(m2.micro_toplamlari() == (5, 3, 5),
          f"Z'nin 3 FP'si micro havuzunda (gelen {m2.micro_toplamlari()})")
    check(BELIRSIZ not in m2.to_dict()["sinif_basi"] and "Z" in m2.to_dict()["sinif_basi"],
          "to_dict sinif_basi: Z var (saf FP gorunur), BELIRSIZ yok (sinif degil)")
    check(m2.to_dict()["sinif_basi"]["Z"]["yalniz_tahmin"] is True,
          "saf-FP sinifi 'yalniz_tahmin' bayragiyla ISARETLENIYOR (gizlenmiyor)")

    # (e) GERCEK VERIDE degisiklik OLMAMALI: aday kume == gercek kume oldugundan
    #     etiket kumesi genislemesi RAPORLANAN sayilari degistirmez.
    if os.path.exists(ARSIV):
        with open(ARSIV, encoding="utf-8") as f:
            rows = json.load(f)["rows"]
        anom = [r for r in rows if r["is_anomaly"]]
        adaylar = sorted({r["category"] for r in anom})
        mk, _ = coksinifli_matris_kur(anom, adaylar)
        check(mk.etiket_kumesi() == adaylar,
              f"gercek veride etiket kumesi == 8 aday sinif (BELIRSIZ haric) — "
              f"raporlanan macro/micro DEGISMEDI ({len(mk.etiket_kumesi())} etiket)")
        check(yakin(mk.macro_f1(), 0.2130952380952381, 1e-9)
              and yakin(mk.micro_f1(), 10 / 33, 1e-9),
              f"gercek veri macro-F1 {mk.macro_f1()} / micro-F1 {mk.micro_f1()} onarimdan "
              "ETKILENMEDI (kapali kumede saf-FP sinifi yok)")

    # (f) BICIMLEYICILER tamamen bos matriste COKMEMELI (D32'de ValueError veriyordu)
    try:
        s1 = coksinifli_matris_bas(CokSinifliMatris(siniflar=[], tahminler=[]), "bos")
        s2 = coksinifli_metrik_tablosu(CokSinifliMatris(siniflar=[], tahminler=[]))
        ok = isinstance(s1, list) and isinstance(s2, list)
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"        cokme: {type(e).__name__}: {e}")
    check(ok, "TAMAMEN BOS matris: coksinifli_matris_bas/metrik_tablosu COKMUYOR")


def main() -> int:
    for fn in (test_1_bilinen_2x2, test_2_mukemmel_ve_tamamen_yanlis,
               test_3_dengesiz_sinif_accuracy_yaniltir, test_4_kenar_durumlar_cokme_yok,
               test_5_f_beta, test_6_macro_micro_weighted_farki,
               test_7_coksinifli_kenar_durumlar, test_8_top1_skoru_labels_ile_tutarli,
               test_9_beraberlik_politikalari, test_10_gercek_veri_arsivle_tutarli,
               test_11_sisirme_kilitleri):
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
