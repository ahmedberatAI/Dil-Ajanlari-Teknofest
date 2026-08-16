#!/usr/bin/env python
"""STANDART ML METRIKLERI — karisiklik matrisi, P/R/F1/F2, MCC, Cohen kappa. GPU GEREKMEZ.

NEDEN BU DOSYA VAR
------------------
Bu depoda simdiye kadar KENDI TURETTIGIMIZ olcutler raporlandi:
    recall     = anomali klipte n_events > 0 mi  ("bir sey isaretledi mi")
    cat_match  = olay metni beklenen anahtar kelimelerden birini iceriyor mu
Bunlar standart ML metrikleri DEGILDIR ve elimizde KARISIKLIK MATRISI yoktu.
Bu modul ayni ARSIVLENMIS ciktilardan standart metrikleri uretir: TP/FP/TN/FN,
precision, recall, specificity, NPV, F1/F0.5/F2, accuracy, balanced accuracy,
MCC, Cohen kappa, FPR/FNR — her orana Wilson %95 guven araligi ile.

KAVRAMSAL UYARI — cat_match COK-SINIFLI BIR TAHMIN DEGILDIR
------------------------------------------------------------
cat_match yalnizca "GERCEK sinifin anahtar kelimesi metinde geciyor mu" diye bakar.
Bir metin AYNI ANDA birden cok sinifin kelimesini icerebilir (olculdu: klip basina
~2 YANLIS kategori de tetikleniyor). Dolayisiyla cat_match'ten DOGRUDAN karisiklik
matrisi CIKARILAMAZ. Matris icin her klibe TEK BIR tahmin edilen sinif atanmalidir.
Bu atama (top-1) BIZIM TASARIM KARARIMIZDIR, modelin dogrudan ciktisi DEGILDIR —
bkz. `top1_tahmin` ve TOP1_KEYFILIK notu.

TANIMSIZLIK POLITIKASI (sifira bolme)
-------------------------------------
Tanimsiz bir metrik icin 0.0 DONDURULMEZ, None dondurulur ve tabloda "n/a" basilir.
Ornegin hic pozitif tahmin yoksa precision = 0/0'dir; "%0 precision" yazmak
"her tahmini yanlis" demektir ve YANLIS bir iddiadir.
Istisna: F-beta kapali formu (asagida) TP=FP=FN=0 disinda her zaman tanimlidir;
TP=0 ama FP veya FN>0 iken F=0.0 gercekten dogrudur, tanimsiz degildir.
MCC'de bir kenar toplami sifir oldugunda payda 0'dir; sklearn burada 0.0 dondurur,
biz None donduruyoruz — "0.0 = sans duzeyi" okumasi yanlis olurdu.

BAGIMLILIK POLITIKASI: yalniz stdlib + benchmark.labels + benchmark.stats_utils.
scipy/sklearn KASITLI OLARAK yok (bkz. stats_utils.py ayni politika).

Kullanim:
    python benchmark/metrics.py                                  # varsayilan dosya
    python benchmark/metrics.py benchmark/results/evidence_ab_A_*.json
    python benchmark/metrics.py <a.json> <b.json> --json cikti.json

Birim testleri:  python tests/test_metrics.py
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from benchmark.labels import (  # noqa: E402
        _OLUMSUZ_RE, _cumlecikler, _kalip_konumlari, SEMANTIC_GROUPS,
        group_of, patterns_for, row_text, tr_lower,
    )
    from benchmark.stats_utils import fmt_rate, rate, wilson_ci  # noqa: E402
except ImportError:  # benchmark/ icinden dogrudan calistirma
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from labels import (  # type: ignore  # noqa: E402
        _OLUMSUZ_RE, _cumlecikler, _kalip_konumlari, SEMANTIC_GROUPS,
        group_of, patterns_for, row_text, tr_lower,
    )
    from stats_utils import fmt_rate, rate, wilson_ci  # type: ignore  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Karisiklik matrisinde "hicbir sinif secilemedi" sutunu.
BELIRSIZ = "BELIRSIZ"

__all__ = [
    "BELIRSIZ", "IkiliMatris", "CokSinifliMatris", "IKILI_TANIMLAR",
    "HESAPLANAMAYAN", "TOP1_KEYFILIK",
    "f_beta_kapali", "kategori_skoru", "satir_metni", "top1_tahmin",
    "ikili_matris_kur", "coksinifli_matris_kur", "grup_matrisi",
    "yukle", "rapor_uret", "main",
]


# ===========================================================================
# 1) IKILI (2x2) KARISIKLIK MATRISI VE TUREVLERI
# ===========================================================================

def _oran(pay: float, payda: float) -> Optional[float]:
    """Sifira bolmede None dondurur (0.0 DEGIL — bkz. modul basligi)."""
    return (pay / payda) if payda else None


def f_beta_kapali(tp: int, fp: int, fn: int, beta: float) -> Optional[float]:
    """F_beta'nin sayim uzerinden KAPALI formu — precision/recall'dan gecmez.

        F_beta = (1+b^2)*TP / ((1+b^2)*TP + b^2*FN + FP)

    P/R uzerinden hesaplamaya gore avantaji: P veya R tanimsiz oldugunda bile
    (TP+FP=0 ya da TP+FN=0) formul dogru degeri verir. Yalnizca TP=FP=FN=0 iken
    (sinif hic gorulmemis VE hic tahmin edilmemis) gercekten tanimsizdir -> None.

    beta > 1 -> recall'a agirlik (F2), beta < 1 -> precision'a agirlik (F0.5).
    """
    b2 = beta * beta
    payda = (1.0 + b2) * tp + b2 * fn + fp
    if payda <= 0:
        return None
    return ((1.0 + b2) * tp) / payda


@dataclass(frozen=True)
class IkiliMatris:
    """2x2 karisiklik matrisi ve ondan turetilen TUM standart metrikler.

    Alanlar tam sayidir; tum metrikler ozellik (property) olarak hesaplanir.
    Tanimsiz metrik None dondurur — cagiran taraf "n/a" basmalidir.
    """
    tp: int
    fp: int
    tn: int
    fn: int
    ad: str = ""
    tanim: str = ""

    # --- temel sayimlar ---
    @property
    def n(self) -> int:
        return self.tp + self.fp + self.tn + self.fn

    @property
    def gercek_pozitif(self) -> int:
        """Gercek pozitif SINIF buyuklugu (TP+FN) — tahmin degil, etiket sayisi."""
        return self.tp + self.fn

    @property
    def gercek_negatif(self) -> int:
        return self.tn + self.fp

    @property
    def tahmin_pozitif(self) -> int:
        return self.tp + self.fp

    @property
    def prevalans(self) -> Optional[float]:
        """Pozitif sinif orani — dengesizligi gosterir (accuracy'nin yaniltici oldugu yer)."""
        return _oran(self.gercek_pozitif, self.n)

    # --- oran metrikleri (hepsi k/n bicimindedir -> Wilson CI verilebilir) ---
    @property
    def precision(self) -> Optional[float]:
        """PPV = TP/(TP+FP). Hic pozitif tahmin yoksa TANIMSIZ (None)."""
        return _oran(self.tp, self.tahmin_pozitif)

    @property
    def recall(self) -> Optional[float]:
        """TPR / duyarlilik = TP/(TP+FN). Hic gercek pozitif yoksa TANIMSIZ."""
        return _oran(self.tp, self.gercek_pozitif)

    @property
    def specificity(self) -> Optional[float]:
        """TNR / secicilik = TN/(TN+FP). Hic gercek negatif yoksa TANIMSIZ."""
        return _oran(self.tn, self.gercek_negatif)

    @property
    def npv(self) -> Optional[float]:
        """Negatif ongoru degeri = TN/(TN+FN). Hic negatif tahmin yoksa TANIMSIZ."""
        return _oran(self.tn, self.tn + self.fn)

    @property
    def fpr(self) -> Optional[float]:
        """Yanlis alarm orani = FP/(FP+TN) = 1 - specificity."""
        return _oran(self.fp, self.gercek_negatif)

    @property
    def fnr(self) -> Optional[float]:
        """Kacirma orani = FN/(FN+TP) = 1 - recall. GUVENLIK sisteminde en pahali hata."""
        return _oran(self.fn, self.gercek_pozitif)

    @property
    def accuracy(self) -> Optional[float]:
        """(TP+TN)/N. DENGESIZ sinifta YANILTICI — bkz. balanced_accuracy ve mcc."""
        return _oran(self.tp + self.tn, self.n)

    def oran_sayimlari(self) -> List[Tuple[str, str, int, int]]:
        """(anahtar, insan-okur ad, k, n) — Wilson CI uygulanabilen metrikler.

        F1/MCC/kappa/balanced-accuracy BU LISTEDE YOKTUR: bunlar k/n bicimli
        binom oranlari DEGILDIR, dolayisiyla Wilson araligi onlara UYGULANAMAZ
        (uygulamak sahte bir kesinlik iddiasi olurdu).
        """
        return [
            ("precision", "Precision (PPV)", self.tp, self.tahmin_pozitif),
            ("recall", "Recall (TPR/duyarlilik)", self.tp, self.gercek_pozitif),
            ("specificity", "Specificity (TNR)", self.tn, self.gercek_negatif),
            ("npv", "NPV", self.tn, self.tn + self.fn),
            ("accuracy", "Accuracy", self.tp + self.tn, self.n),
            ("fpr", "FPR (yanlis alarm)", self.fp, self.gercek_negatif),
            ("fnr", "FNR (kacirma)", self.fn, self.gercek_pozitif),
        ]

    # --- birlesik metrikler (Wilson CI UYGULANAMAZ) ---
    def f_beta(self, beta: float) -> Optional[float]:
        return f_beta_kapali(self.tp, self.fp, self.fn, beta)

    @property
    def f1(self) -> Optional[float]:
        return self.f_beta(1.0)

    @property
    def f05(self) -> Optional[float]:
        """F0.5 — precision'a 2 kat agirlik. 'Yanlis alarm pahali' varsayimi."""
        return self.f_beta(0.5)

    @property
    def f2(self) -> Optional[float]:
        """F2 — recall'a 2 kat agirlik.

        NEDEN BU GOREVDE F2 ONEMLI: bir guvenlik/gozetim sisteminde KACIRILAN olay
        (FN) ile YANLIS ALARM (FP) esit maliyetli degildir. Yanlis alarm operatorun
        10 saniyesini alir; kacirilan yangin/kavga geri donusu olmayan zarardir.
        F1 ikisini esit tartar, F2 recall'i precision'in 2 kati agirlikta tartar ve
        bizim maliyet yapimizi F1'den daha iyi temsil eder.
        """
        return self.f_beta(2.0)

    @property
    def balanced_accuracy(self) -> Optional[float]:
        """(TPR + TNR)/2 — sinif dengesizligine karsi accuracy'nin duzeltilmisi."""
        r, s = self.recall, self.specificity
        if r is None or s is None:
            return None
        return (r + s) / 2.0

    @property
    def mcc(self) -> Optional[float]:
        """Matthews korelasyon katsayisi, [-1, +1].

        MCC dort hucreyi de kullanan tek ozet skordur; ancak +1 alabilmek icin
        hem pozitif hem negatif sinifta iyi olmak gerekir. Dengesiz sinifta
        accuracy'nin sisirdigi yeri gorunur kilar.
        Payda 0 ise (bir kenar toplami sifir) TANIMSIZ -> None (sklearn 0.0 der).
        """
        payda2 = (float(self.tp + self.fp) * float(self.tp + self.fn)
                  * float(self.tn + self.fp) * float(self.tn + self.fn))
        if payda2 <= 0:
            return None
        return (self.tp * self.tn - self.fp * self.fn) / math.sqrt(payda2)

    @property
    def cohen_kappa(self) -> Optional[float]:
        """Cohen kappa — sansa gore duzeltilmis uyum. (po - pe) / (1 - pe)."""
        n = self.n
        if n == 0:
            return None
        po = (self.tp + self.tn) / n
        pe = ((self.tahmin_pozitif * self.gercek_pozitif
               + (self.fn + self.tn) * self.gercek_negatif) / float(n * n))
        if abs(1.0 - pe) < 1e-12:
            return None                       # tek sinifa cokmus: kappa TANIMSIZ
        return (po - pe) / (1.0 - pe)

    def to_dict(self) -> dict:
        d: Dict[str, object] = {
            "ad": self.ad, "tanim": self.tanim,
            "tp": self.tp, "fp": self.fp, "tn": self.tn, "fn": self.fn, "n": self.n,
            "prevalans": self.prevalans,
        }
        for anahtar, _etiket, k, nn in self.oran_sayimlari():
            d[anahtar] = rate(k, nn) if nn else None
        d.update({
            "f1": self.f1, "f0_5": self.f05, "f2": self.f2,
            "balanced_accuracy": self.balanced_accuracy,
            "mcc": self.mcc, "cohen_kappa": self.cohen_kappa,
        })
        return d


# ===========================================================================
# 2) IKILI GOREV TANIMLARI — "tahmin pozitif" NE DEMEK?
# ===========================================================================
# Sistem bir SKOR uretmiyor, AYRIK bir karar uretiyor. "Pozitif" sayilan sey
# hangi cikti alanina baktigimiza gore degisir. Tek bir tanim secip digerlerini
# gizlemek olcum secmeciligidir; UCUNU DE yan yana raporluyoruz.

def _ev(r: dict) -> int:
    return int(r.get("n_events") or 0)


def _sev(r: dict) -> int:
    return int(r.get("max_severity") or 0)


def _risk(r: dict) -> int:
    return int(r.get("risk_ord") or 0)


def _trig(r: dict) -> int:
    # ARSIV NOTU: alan adi `triggered` (paired_test.py ile ayni). `triggered_functions`
    # DIYE BIR ALAN YOKTUR — dosyalar okunarak dogrulandi.
    return len(r.get("triggered") or [])


#: (anahtar, ekran adi, aciklama, pozitif-tahmin yordami)
IKILI_TANIMLAR: Tuple[Tuple[str, str, str, Callable[[dict], bool]], ...] = (
    ("gevsek", "GEVSEK  (n_events > 0)",
     "klipte en az bir olay isaretlendi — en genis tanim, dikkat cekme esigi",
     lambda r: _ev(r) > 0),
    ("siki", "SIKI    (max_sev>=Yuksek VEYA risk>=Yuksek)",
     "gercek alarm esigi: yuksek/kritik siddette olay ya da yuksek risk karari",
     lambda r: _sev(r) >= 3 or _risk(r) >= 3),
    ("sevk", "SEVK    (triggered != bos)",
     "operasyonel eylem: en az bir arac/fonksiyon tetiklendi (ekip sevki)",
     lambda r: _trig(r) > 0),
)


def ikili_matris_kur(rows: Sequence[dict], pozitif: Callable[[dict], bool],
                     ad: str = "", tanim: str = "") -> IkiliMatris:
    """Satirlardan 2x2 matris kurar. Gercek pozitif = row['is_anomaly'] dogru."""
    tp = fp = tn = fn = 0
    for r in rows:
        g = bool(r.get("is_anomaly"))
        t = bool(pozitif(r))
        if g and t:
            tp += 1
        elif (not g) and t:
            fp += 1
        elif (not g) and (not t):
            tn += 1
        else:
            fn += 1
    return IkiliMatris(tp=tp, fp=fp, tn=tn, fn=fn, ad=ad, tanim=tanim)


# ===========================================================================
# 3) TOP-1 SINIF ATAMASI  (BIZIM TASARIM KARARIMIZ — modelin ciktisi DEGIL)
# ===========================================================================
TOP1_KEYFILIK = """\
TOP-1 ATAMASI NASIL YAPILDI VE NERESI KEYFI
-------------------------------------------
Model klip basina TEK BIR sinif etiketi URETMIYOR; serbest metin (events[] + summary)
uretiyor. Karisiklik matrisi icin tek bir tahmin gerektiginden metinden bir sinif
CIKARIYORUZ. Bu bir OLCUM KATMANIDIR, modelin dogrudan ciktisi degildir.

  1  METIN     : events[].event parcalari + summary, " . " ile birlestirilir
                 (rescore.py'nin ozgulluk olcusuyle BIREBIR ayni metin).
  2  SKOR      : her aday sinif icin, o sinifin CATEGORY_PATTERNS listesinden KAC
                 FARKLI kalibin metinde (olumsuzlama kapisindan gecerek) eslestigi.
                 Kalip sayisi -> tekrar sayisi DEGIL: "kavga" kelimesinin 5 kez
                 gecmesi, 2 farkli kalibin eslesmesinden daha guclu sayilmaz.
  3  KARAR     : en yuksek skorlu sinif = tahmin. Skor 0 ise -> BELIRSIZ.

KEYFI OLAN UC NOKTA — DURUSTCE:
  (a) ADAY KUMESI. Aday siniflar, degerlendirme setinde GERCEKTEN BULUNAN siniflarla
      sinirlandirildi (KAPALI KUME). Model calisirken boyle bir kisiti YOKTUR; bu
      kisit modelin isini KOLAYLASTIRIR. Acik kumede (Fire/Smoke/Fall/Anomali da
      aday) sonuc dusen klip sayisi raporda ayrica verilir.
  (b) BERABERLIK. Iki sinif ayni en yuksek skoru alirsa varsayilan politika
      BELIRSIZ'dir (yani KENDI ALEYHIMIZE karar veririz). "iyimser" politika
      beraberligi gercek sinif lehine cozer ve bir UST SINIR verir; bu politika
      calisma zamaninda UYGULANAMAZ (gercek sinifi bilmek gerekir) ve yalnizca
      araligi gostermek icin raporlanir. "sabit" politika ise sabit bir oncelik
      sirasi kullanir ve calisma zamaninda uygulanabilir.
  (c) SKOR TANIMI. "farkli eslesen kalip sayisi" bir seciimdir. Kaliplarin sayisi
      siniflar arasinda esit degildir (Burglary 17 kalip, Smoke 4 kalip); cok kalipli
      siniflarin yuksek skor alma sansi yapisal olarak daha fazladir.
"""

#: BERABERLIK cozumunde kullanilan SABIT oncelik sirasi (calisma zamaninda uygulanabilir).
#: Sira, kalip listesi DAR olandan GENIS olana dogrudur: dar kalipli sinif eslesiyorsa
#: daha ozgul bir kanit vardir. Bu da bir SECIMDIR, kanitla turetilmemistir.
SABIT_ONCELIK: Tuple[str, ...] = (
    "Shooting", "RoadAccidents", "Explosion", "Fire", "Smoke", "Fall",
    "Burglary", "Vandalism", "Abuse", "Fighting", "Assault", "Anomali",
)


def satir_metni(row: dict, *, with_summary: bool = True) -> str:
    """Bir eval satirinin eslestirmeye giren TAM metni (rescore.py ile ayni bicim)."""
    return " . ".join(row_text(row, with_summary=with_summary))


def kategori_skoru(metin: str, kategori: str, *, negation: bool = True) -> int:
    """Metinde kategorinin KAC FARKLI kalibi (olumsuzlama kapisindan gecerek) eslesti.

    labels.match_category ile TUTARLIDIR: skor > 0  <=>  match_category(...) True.
    (Bu esdeger tests/test_metrics.py'de dogrulanir.)
    """
    kaliplar = patterns_for(kategori)
    if not metin or not kaliplar:
        return 0
    cumlecikler = _cumlecikler(tr_lower(metin))
    eslesen: set = set()
    for kalip in kaliplar:
        k_low = tr_lower(kalip)
        for cumlecik in cumlecikler:
            vuruldu = False
            for _bas, son in _kalip_konumlari(cumlecik, k_low):
                if negation and _OLUMSUZ_RE.search(cumlecik, son):
                    continue                  # "kaza belirtisi YOK" -> sayilmaz
                vuruldu = True
                break
            if vuruldu:
                eslesen.add(kalip)
                break
    return len(eslesen)


def top1_tahmin(metin: str, adaylar: Sequence[str], *, beraberlik: str = "belirsiz",
                gercek: Optional[str] = None) -> Tuple[str, Dict[str, int], bool]:
    """Metne TEK bir sinif atar.

    Args:
        metin: klip metni (satir_metni ciktisi)
        adaylar: aday sinif kumesi (KAPALI KUME — bkz. TOP1_KEYFILIK/a)
        beraberlik: "belirsiz" (varsayilan, aleyhimize) | "sabit" | "iyimser"
        gercek: yalnizca beraberlik="iyimser" icin gereklidir (UST SINIR olcumu)

    Returns:
        (tahmin, skorlar, berabere_mi). Hicbir kalip eslesmezse tahmin = BELIRSIZ.
    """
    skorlar = {c: kategori_skoru(metin, c) for c in adaylar}
    en_iyi = max(skorlar.values()) if skorlar else 0
    if en_iyi <= 0:
        return (BELIRSIZ, skorlar, False)
    kazananlar = [c for c in adaylar if skorlar[c] == en_iyi]
    berabere = len(kazananlar) > 1
    if not berabere:
        return (kazananlar[0], skorlar, False)
    if beraberlik == "iyimser" and gercek in kazananlar:
        return (gercek, skorlar, True)        # UST SINIR — calisma zamaninda UYGULANAMAZ
    if beraberlik == "sabit":
        for c in SABIT_ONCELIK:
            if c in kazananlar:
                return (c, skorlar, True)
        return (sorted(kazananlar)[0], skorlar, True)
    return (BELIRSIZ, skorlar, True)


# ===========================================================================
# 4) COK-SINIFLI KARISIKLIK MATRISI
# ===========================================================================

@dataclass
class CokSinifliMatris:
    """Cok-sinifli karisiklik matrisi ve sinif-basi + toplulastirilmis metrikler.

    `siniflar`  : GERCEK etiket kumesi (matrisin SATIRLARI)
    `tahminler` : tahmin kumesi (SUTUNLAR) — BELIRSIZ sutunu iceerebilir
    `hucre`     : (gercek, tahmin) -> sayim
    """
    siniflar: List[str]
    tahminler: List[str]
    hucre: Dict[Tuple[str, str], int] = field(default_factory=dict)
    ad: str = ""

    # --- kurulum ---
    def ekle(self, gercek: str, tahmin: str) -> None:
        self.hucre[(gercek, tahmin)] = self.hucre.get((gercek, tahmin), 0) + 1

    def say(self, gercek: str, tahmin: str) -> int:
        return self.hucre.get((gercek, tahmin), 0)

    @property
    def n(self) -> int:
        return sum(self.hucre.values())

    def destek(self, c: str) -> int:
        """Sinifin GERCEK ornek sayisi (satir toplami)."""
        return sum(self.say(c, t) for t in self.tahminler)

    def tahmin_sayisi(self, c: str) -> int:
        """Sinifin TAHMIN edilme sayisi (sutun toplami)."""
        return sum(self.say(g, c) for g in self.siniflar)

    def bir_vs_hepsi(self, c: str) -> IkiliMatris:
        """Sinif c icin bir-e-karsi-hepsi 2x2 matris (sinif basi P/R/F1'in temeli)."""
        tp = self.say(c, c)
        fn = self.destek(c) - tp
        fp = self.tahmin_sayisi(c) - tp if c in self.tahminler else 0
        tn = self.n - tp - fn - fp
        return IkiliMatris(tp=tp, fp=fp, tn=tn, fn=fn, ad=c)

    # --- toplulastirilmis metrikler ---
    @property
    def accuracy(self) -> Optional[float]:
        return _oran(sum(self.say(c, c) for c in self.siniflar), self.n)

    def etiket_kumesi(self) -> List[str]:
        """Toplulastirmanin (macro/micro/weighted) uzerinde donecegi ETIKET kumesi.

        = satirlar (gercek siniflar) BIRLESIM sutunlar (tahmin edilen siniflar), BELIRSIZ haric.

        NEDEN BIRLESIM — SISIRME ONARIMI (D32): yalnizca GERCEK siniflar uzerinden
        ortalama alinirsa, "hic gercek ornegi olmayan ama MODELIN TAHMIN ETTIGI" bir
        sinifin YANLIS POZITIFLERI hicbir ortalamaya girmez. O sinifin F1'i 0.0'dir
        (tanimlidir!) ve disarida birakmak makro skoru YUKARI ceker. Olculdu: acik aday
        kumesinde (Fire/Smoke/Fall/Anomali de aday) modelin 13 klipte tahmin ettigi
        Fall/Anomali siniflari disarida kaliyordu; makro-F1 0.125 gorunuyordu, dogrusu
        0.100. Birlesim kullanmak sklearn.metrics'in varsayilan davranisidir
        (labels = y_true U y_pred).

        BELIRSIZ NEDEN HARIC: BELIRSIZ bir SINIF degil, CEKIMSER KALMA'dir. Onu bir
        sinif sayip F1=0.0 vermek, hicbir modelin kazanamayacagi yapay bir sinif
        eklerdi (asagi yonlu carpitma). BELIRSIZ tahminler yine de gercek sinifa FN
        yazar ve accuracy paydasinda kalir — yani cezasi ZATEN odenir.
        """
        return [c for c in dict.fromkeys(list(self.siniflar) + list(self.tahminler))
                if c != BELIRSIZ]

    def _ortalama_tabani(self) -> List[str]:
        """F1'i TANIMLI olan etiketler (TP=FP=FN=0 olanlar 0/0'dir, disarida kalir).

        DIKKAT — INCE AYRIM: "destek = 0" ile "F1 tanimsiz" AYNI SEY DEGILDIR.
          * destek 0 VE hic tahmin edilmemis -> TP=FP=FN=0 -> F1 gercekten 0/0 -> DISARIDA
          * destek 0 AMA tahmin edilmis      -> FP>0 -> F1 = 0.0 TANIMLIDIR -> ICERIDE
        Ikincisini disarida birakmak makro skoru SISIRIR (bkz. etiket_kumesi).
        """
        return [c for c in self.etiket_kumesi() if self.bir_vs_hepsi(c).f1 is not None]

    def macro_f1(self) -> Optional[float]:
        """Her sinifin F1'inin DUZ ortalamasi. Nadir sinifi sik sinif kadar tartar.

        macro-F1, macro-P ve macro-R'den TUREMEZ: once sinif basina F1 hesaplanir,
        SONRA ortalama alinir (harmonik ortalamanin ortalamasi != ortalamalarin
        harmonik ortalamasi).
        """
        f = [self.bir_vs_hepsi(c).f1 for c in self._ortalama_tabani()]
        return (sum(f) / len(f)) if f else None

    def weighted_f1(self) -> Optional[float]:
        """DESTEK ile agirlikli F1 ortalamasi. Sik sinifin performansini one cikarir.

        Destegi 0 olan sinif agirligi 0 aldigi icin sonucu degistirmez — bu yuzden
        etiket kumesini genisletmek weighted-F1'i ETKILEMEZ (sklearn ile ayni).
        """
        pay = payda = 0.0
        for c in self._ortalama_tabani():
            f1 = self.bir_vs_hepsi(c).f1
            d = self.destek(c)
            pay += d * f1
            payda += d
        return (pay / payda) if payda else None

    def micro_toplamlari(self) -> Tuple[int, int, int]:
        """(TP, FP, FN) toplamlari — etiket kumesi uzerinden (BELIRSIZ haric).

        SISIRME ONARIMI (D32): eskiden yalnizca GERCEK siniflar toplaniyordu; gercekte
        hic bulunmayan ama TAHMIN EDILEN bir sinifin FP'leri havuza girmiyordu ve
        micro-F1 yukari cikiyordu. Artik etiket_kumesi() uzerinden toplaniyor.
        """
        tp = fp = fn = 0
        for c in self.etiket_kumesi():
            m = self.bir_vs_hepsi(c)
            tp += m.tp
            fp += m.fp
            fn += m.fn
        return (tp, fp, fn)

    def micro_f1(self) -> Optional[float]:
        """Tum sayimlari havuzlayan F1.

        NOT — MICRO-F1 == ACCURACY MI? Tek etiketli cok-sinifli problemde, TAHMINLER
        DE ayni sinif kumesindeyse evet. Bizde BELIRSIZ sutunu var: BELIRSIZ tahmini
        hicbir gercek sinifa FP yazmaz ama gercek sinifa FN yazar. Bu yuzden
        micro-precision > micro-recall olur ve micro-F1 accuracy'den FARKLILASIR.
        """
        tp, fp, fn = self.micro_toplamlari()
        return f_beta_kapali(tp, fp, fn, 1.0)

    def cohen_kappa(self) -> Optional[float]:
        """Cok-sinifli Cohen kappa; etiket kumesi satir+sutun BIRLESIMIDIR."""
        n = self.n
        if n == 0:
            return None
        birlesim = list(dict.fromkeys(list(self.siniflar) + list(self.tahminler)))
        po = sum(self.say(c, c) for c in birlesim if c in self.siniflar) / float(n)
        pe = 0.0
        for c in birlesim:
            satir = self.destek(c) if c in self.siniflar else 0
            sutun = self.tahmin_sayisi(c) if c in self.tahminler else 0
            pe += (satir * sutun) / float(n * n)
        if abs(1.0 - pe) < 1e-12:
            return None
        return (po - pe) / (1.0 - pe)

    def to_dict(self) -> dict:
        tp, fp, fn = self.micro_toplamlari()
        return {
            "ad": self.ad,
            "siniflar": list(self.siniflar),
            "tahminler": list(self.tahminler),
            "matris": {f"{g}|{t}": v for (g, t), v in sorted(self.hucre.items())},
            "n": self.n,
            # etiket_kumesi(): yalniz gercek siniflar DEGIL, TAHMIN EDILEN siniflar da.
            # Boylece "hic gercek ornegi yok ama model bunu tahmin etti" satiri
            # (saf FP yigini) tabloda GORUNUR olur, gizlenmez.
            "sinif_basi": {
                c: {
                    "destek": self.destek(c),
                    "tp": b.tp, "fp": b.fp, "fn": b.fn,
                    "precision": b.precision, "recall": b.recall, "f1": b.f1,
                    "yalniz_tahmin": c not in self.siniflar,
                } for c, b in ((c, self.bir_vs_hepsi(c)) for c in self.etiket_kumesi())
            },
            "accuracy": self.accuracy,
            "macro_f1": self.macro_f1(),
            "micro_f1": self.micro_f1(),
            "micro_tp_fp_fn": [tp, fp, fn],
            "weighted_f1": self.weighted_f1(),
            "cohen_kappa": self.cohen_kappa(),
        }


def coksinifli_matris_kur(rows: Sequence[dict], adaylar: Sequence[str], *,
                          beraberlik: str = "belirsiz",
                          ad: str = "") -> Tuple[CokSinifliMatris, List[dict]]:
    """Anomali satirlarindan top-1 atamasi yapip cok-sinifli matris kurar.

    Returns:
        (matris, ayrinti) — ayrinti her klip icin {path, gercek, tahmin, berabere, skor}.
    """
    siniflar = sorted({str(r.get("category") or "?") for r in rows})
    tahmin_kumesi = list(dict.fromkeys(list(adaylar) + [BELIRSIZ]))
    m = CokSinifliMatris(siniflar=siniflar, tahminler=tahmin_kumesi, ad=ad)
    ayrinti: List[dict] = []
    for r in rows:
        g = str(r.get("category") or "?")
        metin = satir_metni(r)
        t, skorlar, berabere = top1_tahmin(metin, adaylar, beraberlik=beraberlik, gercek=g)
        m.ekle(g, t)
        ayrinti.append({
            "path": r.get("path"), "gercek": g, "tahmin": t, "berabere": berabere,
            "skor": {k: v for k, v in sorted(skorlar.items(), key=lambda x: -x[1]) if v},
        })
    return (m, ayrinti)


def grup_matrisi(ayrinti: Sequence[dict], ad: str = "") -> CokSinifliMatris:
    """(A) ESLENMIS grup matrisi: kategori top-1 karari grubuna tasinir.

    TASARIM: grup duzeyinde YENIDEN top-1 CALISTIRILMAZ; kategori duzeyindeki
    ayni tek karar grubuna eslenir. Boylece iki tablo AYNI karardan turer.

    ! BILINEN OLCUM ARTEFAKTI: Fighting/Assault/Abuse ayni gruptadir ve kalip
    listeleri buyuk olcude ortaktir ("şiddet", "kavga", "saldır"). Bu kategoriler
    kategori duzeyinde SIK SIK beraberlige girer ve pesimist politika onlari
    BELIRSIZ yapar. Oysa GRUP duzeyinde bu bir beraberlik DEGILDIR — ucu de ayni
    grubu gosterir. Bu yuzden asagidaki `grup_dogrudan_matris` fonksiyonu
    beraberligi grup duzeyinde COZER ve iki tablo YAN YANA raporlanir.
    """
    gruplar = sorted({(group_of(a["gercek"]) or a["gercek"]) for a in ayrinti})
    tahmin_gruplari = sorted({(group_of(a["tahmin"]) or a["tahmin"])
                              for a in ayrinti if a["tahmin"] != BELIRSIZ})
    m = CokSinifliMatris(siniflar=gruplar,
                         tahminler=list(dict.fromkeys(tahmin_gruplari + [BELIRSIZ])), ad=ad)
    for a in ayrinti:
        g = group_of(a["gercek"]) or a["gercek"]
        t = BELIRSIZ if a["tahmin"] == BELIRSIZ else (group_of(a["tahmin"]) or a["tahmin"])
        m.ekle(g, t)
    return m


def grup_uyelikleri(adaylar: Sequence[str]) -> Dict[str, List[str]]:
    """Aday kategorileri semantik gruplara toplar (grubu olmayan kendi basina grup olur)."""
    out: Dict[str, List[str]] = {}
    for c in adaylar:
        out.setdefault(group_of(c) or c, []).append(c)
    return out


def grup_top1(metin: str, gruplar: Dict[str, List[str]], *,
              beraberlik: str = "belirsiz",
              gercek: Optional[str] = None) -> Tuple[str, Dict[str, int], bool]:
    """DOGRUDAN grup duzeyinde top-1: grup skoru = uyelerinin EN YUKSEK skoru.

    max (toplam degil) kullanilir: aksi halde uc uyeli Siddet grubu, tek uyeli
    Trafik grubuna karsi yapisal bir avantaj kazanirdi.
    """
    skorlar = {g: max((kategori_skoru(metin, c) for c in uyeler), default=0)
               for g, uyeler in gruplar.items()}
    en_iyi = max(skorlar.values()) if skorlar else 0
    if en_iyi <= 0:
        return (BELIRSIZ, skorlar, False)
    kazananlar = [g for g in gruplar if skorlar[g] == en_iyi]
    berabere = len(kazananlar) > 1
    if not berabere:
        return (kazananlar[0], skorlar, False)
    if beraberlik == "iyimser" and gercek in kazananlar:
        return (gercek, skorlar, True)
    if beraberlik == "sabit":
        for c in SABIT_ONCELIK:               # kategori onceligini gruba tasi
            g = group_of(c) or c
            if g in kazananlar:
                return (g, skorlar, True)
        return (sorted(kazananlar)[0], skorlar, True)
    return (BELIRSIZ, skorlar, True)


def grup_dogrudan_matris(rows: Sequence[dict], adaylar: Sequence[str], *,
                         beraberlik: str = "belirsiz",
                         ad: str = "grup_dogrudan") -> Tuple[CokSinifliMatris, int]:
    """(B) DOGRUDAN grup matrisi: top-1 GRUP duzeyinde calistirilir.

    Returns: (matris, grup_duzeyinde_kalan_beraberlik_sayisi)
    """
    gruplar = grup_uyelikleri(adaylar)
    gercek_gruplar = sorted({(group_of(str(r.get("category") or "?"))
                              or str(r.get("category") or "?")) for r in rows})
    m = CokSinifliMatris(siniflar=gercek_gruplar,
                         tahminler=list(dict.fromkeys(sorted(gruplar) + [BELIRSIZ])), ad=ad)
    berabere_n = 0
    for r in rows:
        c = str(r.get("category") or "?")
        g = group_of(c) or c
        t, _s, b = grup_top1(satir_metni(r), gruplar, beraberlik=beraberlik, gercek=g)
        berabere_n += int(b)
        m.ekle(g, t)
    return (m, berabere_n)


# ===========================================================================
# 5) HESAPLANAMAYAN METRIKLER — durustce
# ===========================================================================
#: (metrik, NEDEN hesaplanamiyor, ELDE ETMEK ICIN ne gerekir)
HESAPLANAMAYAN: Tuple[Tuple[str, str, str], ...] = (
    ("ROC-AUC / PR-AUC",
     "Model surekli bir GUVEN SKORU uretmiyor; AYRIK bir karar (olay listesi + risk "
     "seviyesi) uretiyor. Egri cizmek icin esigi supurup her esikte TPR/FPR gerekir; "
     "supurulecek surekli bir eksen YOK. Elimizdeki 3 tanim (gevsek/siki/sevk) ROC "
     "uzayinda yalnizca 3 AYRIK NOKTADIR, bir egri degildir.",
     "Cikti sozlesmesine klip-duzeyi kalibre edilmis bir anomali olasiligi (0-1) "
     "eklemek ve ayni kliplerde esigi supurmek gerekir."),
    ("mAP / IoU (nesne tespiti)",
     "Kare-duzeyi sinirlayici kutu (bbox) ALTIN ETIKETIMIZ yok. UCF-Crime klip-duzeyi "
     "etiketle geliyor; biz de klip-duzeyi calisiyoruz. mAP'i tanimlamak icin "
     "gereken (kutu, sinif, kare) uclusu veride MEVCUT DEGIL.",
     "Degerlendirme kliplerinin kare-duzeyi bbox etiketlenmesi (insan anotasyonu) "
     "ve ajanin bbox dondurmesi gerekir."),
    ("Zamansal IoU / olay yerellestirme",
     "Olayin BASLANGIC-BITIS altin etiketi yok; elimizde yalnizca 'bu klipte X vardir' "
     "bilgisi var. Model events[].time uretiyor ama karsilastirilacak GERCEK zaman "
     "araligi olmadigi icin dogrulanamaz.",
     "Klip basina (baslangic_sn, bitis_sn) araliklarinin insan tarafindan "
     "isaretlenmesi; ya da data/temporal gibi splice noktasi TASARIMDAN bilinen "
     "kompozit kliplerin sistematik uretilmesi."),
    ("Kare-duzeyi AUC (UCF-Crime standart protokolu)",
     "UCF-Crime'in TEST bolumunde kare-duzeyi etiketler VARDIR, ama biz klip duzeyinde "
     "olcuyoruz ve ajan kare-basi skor uretmiyor. Literaturdeki kare-AUC sayilariyla "
     "DOGRUDAN KIYASLANAMAZ — ayni sayi degildir.",
     "Kare-basi anomali skoru ureten bir cikti yolu + resmi UCF-Crime test bolumu "
     "kare etiketlerinin indirilmesi."),
    ("Ozgullugun (specificity) kategori-basi kirilimi",
     "Normal klipler kategori ETIKETI TASIMIYOR (hepsi 'Normal'). Bu yuzden "
     "'Fighting icin FPR' gibi bir sayi tanimlanamaz: bir normal klibin hangi "
     "kategoriye karsi negatif oldugu belirsizdir.",
     "Normal kliplerin 'hangi anomaliye benziyor' diye alt-etiketlenmesi (or. "
     "yangin-benzeri negatif, kalabalik-benzeri negatif) gerekir."),
)


# ===========================================================================
# 6) RAPOR BICIMLEME
# ===========================================================================
CIZGI = "=" * 92
INCE = "-" * 92


def _f(x: Optional[float], basamak: int = 3) -> str:
    """Tanimsiz metrik icin 0.0 DEGIL 'n/a' basar."""
    return "n/a" if x is None else f"{x:.{basamak}f}"


def _kisalt(adlar: Sequence[str], genislik: int = 4) -> Dict[str, str]:
    """Matris basliklari icin BENZERSIZ kisaltma uretir (cakisirsa uzatir)."""
    out: Dict[str, str] = {}
    for a in adlar:
        k = a[:genislik]
        i = genislik
        while k in out.values() and i < len(a):
            i += 1
            k = a[:i]
        out[a] = "?" if a == BELIRSIZ else k
    return out


def ikili_matris_bas(m: IkiliMatris) -> List[str]:
    """2x2 matrisi okunakli bicimde basar."""
    s = [
        f"  {m.ad}",
        f"    tanim: {m.tanim}",
        "",
        "                          T A H M I N",
        "                     pozitif   negatif        toplam",
        f"    GERCEK  anomali  {m.tp:7d}   {m.fn:7d}   |  {m.gercek_pozitif:6d}",
        f"            normal   {m.fp:7d}   {m.tn:7d}   |  {m.gercek_negatif:6d}",
        "                     -------   -------      -------",
        f"            toplam   {m.tahmin_pozitif:7d}   {m.tn + m.fn:7d}   |  {m.n:6d}",
        "",
        f"    TP={m.tp}  FP={m.fp}  TN={m.tn}  FN={m.fn}"
        f"   (prevalans = {_f(m.prevalans)}, yani pozitif sinif orani)",
    ]
    return s


def ikili_metrik_tablosu(m: IkiliMatris) -> List[str]:
    """Oran metrikleri (Wilson CI ile) + birlesik metrikler (CI'siz)."""
    out = ["", "    ORAN METRIKLERI  (k/n bicimli -> Wilson %95 GA mesru)",
           f"    {'metrik':26s} {'deger':>7s}   {'Wilson %95 GA + sayimlar'}"]
    for _anahtar, etiket, k, n in m.oran_sayimlari():
        if n == 0:
            out.append(f"    {etiket:26s} {'n/a':>7s}   (payda 0 — TANIMSIZ, 0.0 DEGIL)")
            continue
        out.append(f"    {etiket:26s} {k / n:7.3f}   {fmt_rate(k, n)}")
    out += [
        "",
        "    BIRLESIK METRIKLER  (binom orani DEGIL -> Wilson GA UYGULANAMAZ)",
        f"    {'F1  (P ve R esit)':26s} {_f(m.f1):>7s}",
        f"    {'F0.5 (precision agirlikli)':26s} {_f(m.f05):>7s}",
        f"    {'F2  (RECALL agirlikli)':26s} {_f(m.f2):>7s}   <- guvenlik gorevinde ANA metrik",
        f"    {'Balanced accuracy':26s} {_f(m.balanced_accuracy):>7s}",
        f"    {'MCC (Matthews)':26s} {_f(m.mcc):>7s}   [-1, +1]",
        f"    {'Cohen kappa':26s} {_f(m.cohen_kappa):>7s}",
    ]
    return out


def coksinifli_matris_bas(m: CokSinifliMatris, baslik: str) -> List[str]:
    """Cok-sinifli karisiklik matrisini okunakli grid olarak basar."""
    kis = _kisalt(list(m.siniflar) + [t for t in m.tahminler if t not in m.siniflar])
    out = ["", f"  {baslik}", ""]
    if not kis:                                # TAMAMEN BOS matris: basilacak eksen yok
        return out + ["    (matriste hicbir sinif/tahmin yok — basilacak tablo yok)"]
    genis = max(4, max(len(v) for v in kis.values()))
    basliklar = "".join(f"{kis[t]:>{genis + 2}s}" for t in m.tahminler)
    out.append(f"    {'gercek \\ tahmin':22s}{basliklar}{'dest':>7s}")
    out.append("    " + "-" * (22 + (genis + 2) * len(m.tahminler) + 7))
    for g in m.siniflar:
        hucreler = ""
        for t in m.tahminler:
            v = m.say(g, t)
            im = "." if v == 0 else str(v)
            if g == t and v:
                im = f"[{v}]"                  # KOSEGEN = dogru tahmin
            hucreler += f"{im:>{genis + 2}s}"
        out.append(f"    {g:22s}{hucreler}{m.destek(g):>7d}")
    out.append("    " + "-" * (22 + (genis + 2) * len(m.tahminler) + 7))
    alt = "".join(f"{m.tahmin_sayisi(t):>{genis + 2}d}" for t in m.tahminler)
    out.append(f"    {'tahmin toplami':22s}{alt}{m.n:>7d}")
    out.append("")
    out.append("    Sutun kisaltmalari: " + ", ".join(
        f"{v}={k}" for k, v in kis.items() if k != BELIRSIZ))
    out.append(f"    ? = {BELIRSIZ} (hicbir kalip eslesmedi ya da beraberlik cozulemedi)")
    out.append("    [n] = KOSEGEN (dogru tahmin)")
    return out


def coksinifli_metrik_tablosu(m: CokSinifliMatris) -> List[str]:
    out = ["", "    SINIF BASINA  (bir-e-karsi-hepsi)",
           f"    {'sinif':16s} {'destek':>6s} {'TP':>4s} {'FP':>4s} {'FN':>4s} "
           f"{'prec':>7s} {'recall':>7s} {'F1':>7s}"]
    for c in m.etiket_kumesi():               # gercek siniflar + YALNIZ TAHMIN EDILENLER
        b = m.bir_vs_hepsi(c)
        im = "" if c in m.siniflar else "  <- gercek ornegi YOK, yalniz TAHMIN edildi (saf FP)"
        out.append(f"    {c:16s} {m.destek(c):>6d} {b.tp:>4d} {b.fp:>4d} {b.fn:>4d} "
                   f"{_f(b.precision):>7s} {_f(b.recall):>7s} {_f(b.f1):>7s}{im}")
    tp, fp, fn = m.micro_toplamlari()
    out += [
        "",
        f"    Cok-sinifli accuracy : {_f(m.accuracy)}   ({sum(m.say(c, c) for c in m.siniflar)}/{m.n})",
        f"    MACRO-F1             : {_f(m.macro_f1())}   sinif F1'lerinin DUZ ortalamasi "
        f"— nadir sinif = sik sinif",
        f"    MICRO-F1             : {_f(m.micro_f1())}   tum TP/FP/FN havuzlanir "
        f"(TP={tp} FP={fp} FN={fn}) — sik sinif baskin",
        f"    WEIGHTED-F1          : {_f(m.weighted_f1())}   destekle agirlikli ortalama",
        f"    Cohen kappa          : {_f(m.cohen_kappa())}   sansa gore duzeltilmis uyum",
        "",
        "    UCUNUN FARKI: MACRO her sinifa esit oy verir (bir sinifta cokmek toplami",
        "    asagi ceker). MICRO orneklere esit oy verir; sinif dengesi bozuksa buyuk",
        "    sinifin performansini yansitir. WEIGHTED sinif F1'lerini destege gore tartar,",
        "    yani MICRO'ya yaklasir ama sinif-ici P/R dengesini korur. Bizim setimizde",
        "    her sinif 3 klip oldugundan MACRO ~ WEIGHTED; MICRO ise BELIRSIZ sutunu",
        "    yuzunden accuracy'den ayrilir (BELIRSIZ tahmin FN yazar, FP yazmaz).",
    ]
    return out


# ===========================================================================
# 7) SURUCU
# ===========================================================================

def yukle(yol: str) -> dict:
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


def rapor_uret(yol: str, *, beraberlik: str = "belirsiz",
               acik_kume: Optional[Sequence[str]] = None) -> Tuple[List[str], dict]:
    """Tek bir sonuc dosyasi icin TUM tablolari uretir. (satirlar, json_sozluk)"""
    veri = yukle(yol)
    rows = veri.get("rows") or []
    anom = [r for r in rows if r.get("is_anomaly")]
    norm = [r for r in rows if not r.get("is_anomaly")]
    dosya_adi = os.path.basename(yol)

    L: List[str] = [CIZGI,
                    "STANDART ML METRIKLERI — karisiklik matrisi tabanli",
                    CIZGI,
                    f"KAYNAK DOSYA : benchmark/results/{dosya_adi}",
                    f"SET          : {veri.get('eval_dir') or '?'}",
                    f"KLIP         : {len(rows)} toplam = {len(anom)} anomali + {len(norm)} normal",
                    f"DEDUP        : {(veri.get('dedup') or {}).get('n_skipped', '?')} atlandi"
                    f"   ·   SIZINTI UYARISI: {veri.get('leak_warning') or 'yok'}"]
    if not rows:
        L += ["", "!! DOSYADA SATIR YOK — hicbir metrik hesaplanamaz."]
        return (L, {"dosya": dosya_adi, "hata": "bos"})

    prev = len(anom) / len(rows) if rows else 0.0
    L += ["",
          f"SINIF DENGESIZLIGI: prevalans = {prev:.3f} ({len(anom)}/{len(rows)}).",
          "  Hicbir sey yapmayip 'hepsi anomali' diyen bir sistem accuracy "
          f"{prev:.3f} alir.",
          "  Bu yuzden ACCURACY TEK BASINA YANILTICIDIR; asagida MCC, balanced",
          "  accuracy ve F2 birlikte raporlanir. MCC dort hucreyi de kullandigi icin",
          "  bos-tahminciyi 0 civarina cakar; accuracy cakmaz."]

    # ---- 2) IKILI GOREV ----
    L += ["", CIZGI, "2) IKILI GOREV — ANOMALI TESPITI", CIZGI,
          "Gercek pozitif = is_anomaly True. 'Tahmin pozitif' TEK BIR SEY DEGILDIR:",
          "cikti sozlesmesinin hangi alanina baktigimiza gore degisir. Uc tanim da",
          "asagida YAN YANA verilir; birini secip digerlerini gizlemek olcum secmeciligi olurdu."]
    ikili_json: Dict[str, object] = {}
    matrisler: List[IkiliMatris] = []
    for anahtar, ad, tanim, fn in IKILI_TANIMLAR:
        m = ikili_matris_kur(rows, fn, ad=ad, tanim=tanim)
        matrisler.append(m)
        ikili_json[anahtar] = m.to_dict()
        L += ["", INCE] + ikili_matris_bas(m) + ikili_metrik_tablosu(m)
        L += [f"    KAYNAK: benchmark/results/{dosya_adi}"]

    L += ["", INCE, "  UC TANIM YAN YANA",
          f"  {'tanim':14s} {'TP':>4s} {'FP':>4s} {'TN':>4s} {'FN':>4s} "
          f"{'prec':>7s} {'recall':>7s} {'F1':>7s} {'F2':>7s} {'MCC':>7s} {'bal.acc':>8s}"]
    for anahtar, m in zip([a for a, *_ in IKILI_TANIMLAR], matrisler):
        L.append(f"  {anahtar:14s} {m.tp:>4d} {m.fp:>4d} {m.tn:>4d} {m.fn:>4d} "
                 f"{_f(m.precision):>7s} {_f(m.recall):>7s} {_f(m.f1):>7s} "
                 f"{_f(m.f2):>7s} {_f(m.mcc):>7s} {_f(m.balanced_accuracy):>8s}")
    L += [f"  KAYNAK: benchmark/results/{dosya_adi}"]

    # --- TANIMLARIN BAGIMSIZLIK DENETIMI: iki tanim ayni karari mi veriyor? ---
    # Ayni SAYILARI uretmek yetmez; SATIR BAZINDA ayni olup olmadiklarina bakilir.
    # Aynilarsa iki tanim BAGIMSIZ KANIT DEGILDIR ve ayri metrik gibi sunulmamalidir.
    ozdes: List[str] = []
    tanim_listesi = list(IKILI_TANIMLAR)
    for i in range(len(tanim_listesi)):
        for j in range(i + 1, len(tanim_listesi)):
            ai, _adi, _ti, fi = tanim_listesi[i]
            aj, _adj, _tj, fj = tanim_listesi[j]
            fark = sum(1 for r in rows if bool(fi(r)) != bool(fj(r)))
            if fark == 0:
                ozdes.append(f"{ai} == {aj}")
    if ozdes:
        L += ["", f"  !! TANIM OZDESLIGI: {', '.join(ozdes)} — bu tanimlar SATIR BAZINDA",
              "     birebir ayni karari veriyor (yalnizca ayni ozetleri degil). Yani ayri",
              "     ayri raporlamak BAGIMSIZ KANIT SAYILMAZ: risk esigi ile sevk politikasi",
              "     bu kosuda tamamen birlesmis durumda. Uc satir gibi gorunen tablo",
              "     GERCEKTE IKI bagimsiz karar noktasi iceriyor."]
    else:
        L += ["", "  Tanim ozdeslik denetimi: uc tanimin hicbir ikilisi satir bazinda ayni degil."]

    # ---- 3) COK-SINIFLI GOREV ----
    adaylar = sorted({str(r.get("category") or "?") for r in anom})
    L += ["", CIZGI, "3) COK-SINIFLI GOREV — OLAY TURU ADLANDIRMA", CIZGI]
    L += TOP1_KEYFILIK.rstrip().splitlines()
    L += ["", f"  Aday sinif kumesi (KAPALI): {', '.join(adaylar)}",
          f"  Beraberlik politikasi     : {beraberlik}"]

    m_cok, ayrinti = coksinifli_matris_kur(anom, adaylar, beraberlik=beraberlik,
                                           ad="kategori")
    L += coksinifli_matris_bas(
        m_cok, "KARISIKLIK MATRISI — KATEGORI duzeyi  (top-1 = BIZIM OLCUM KATMANIMIZ, "
               "modelin dogrudan ciktisi DEGIL)")
    L += coksinifli_metrik_tablosu(m_cok)
    L += [f"    KAYNAK: benchmark/results/{dosya_adi}"]

    berabere_n = sum(1 for a in ayrinti if a["berabere"])
    belirsiz_n = sum(1 for a in ayrinti if a["tahmin"] == BELIRSIZ)
    sifir_n = sum(1 for a in ayrinti if not a["skor"])
    L += ["", f"    BERABERLIK/BELIRSIZLIK: {berabere_n}/{len(ayrinti)} klipte beraberlik,",
          f"    {belirsiz_n}/{len(ayrinti)} klip BELIRSIZ atandi "
          f"(bunlarin {sifir_n} tanesinde HICBIR kalip eslesmedi)."]

    # UST SINIR / ALT SINIR araligi: beraberlik politikasinin etkisi
    L += ["", "    BERABERLIK POLITIKASININ ETKISI (ayni model ciktisi, farkli olcum karari):"]
    politika_json: Dict[str, object] = {}
    for pol in ("belirsiz", "sabit", "iyimser"):
        mm, _ = coksinifli_matris_kur(anom, adaylar, beraberlik=pol)
        politika_json[pol] = {"accuracy": mm.accuracy, "macro_f1": mm.macro_f1()}
        etiket = {"belirsiz": "belirsiz (varsayilan, ALEYHIMIZE)",
                  "sabit": "sabit oncelik (calisma zamaninda uygulanabilir)",
                  "iyimser": "iyimser (UST SINIR — calisma zamaninda UYGULANAMAZ)"}[pol]
        L.append(f"      {etiket:52s} accuracy={_f(mm.accuracy)}  macro-F1={_f(mm.macro_f1())}")

    # ACIK KUME etkisi
    genis = list(acik_kume) if acik_kume else sorted(
        set(adaylar) | {"Fire", "Smoke", "Fall", "Anomali"})
    m_acik, _ = coksinifli_matris_kur(anom, genis, beraberlik=beraberlik, ad="acik_kume")
    L += ["", "    ADAY KUMESI KISITININ ETKISI (TOP1_KEYFILIK/a):",
          f"      kapali kume ({len(adaylar)} sinif) accuracy = {_f(m_cok.accuracy)}",
          f"      acik kume   ({len(genis)} sinif) accuracy = {_f(m_acik.accuracy)}",
          "      Fark, degerlendirme setinde bulunmayan siniflarin (Fire/Smoke/Fall/Anomali)",
          "      calindigi klip sayisidir. Kapali kume modelin isini KOLAYLASTIRIR."]

    # GRUP DUZEYI
    m_grup = grup_matrisi(ayrinti, ad="grup")
    L += ["", INCE]
    L += coksinifli_matris_bas(
        m_grup, "KARISIKLIK MATRISI — SEMANTIK GRUP duzeyi  (ayni top-1 karari, "
                "gruba eslenmis)")
    L += coksinifli_metrik_tablosu(m_grup)
    L += ["", "    GRUP TANIMLARI: " + "; ".join(
        f"{g}={'/'.join(u)}" for g, u in SEMANTIC_GROUPS.items()),
        "    Gerekce: 'Fighting' yerine 'Assault' demek OPERATOR ICIN AYNI mudahaleyi",
        "    dogurur (guvenlik ekibi sevk). 'Fighting' yerine 'Fire' demek DOGURMAZ.",
        f"    KAYNAK: benchmark/results/{dosya_adi}"]

    # --- (B) DOGRUDAN grup top-1: grup-ICI beraberlik grup duzeyinde beraberlik DEGILDIR ---
    m_grup2, grup_berabere = grup_dogrudan_matris(anom, adaylar, beraberlik=beraberlik)
    L += ["", INCE,
          "  NEDEN IKINCI BIR GRUP TABLOSU VAR (olcum artefakti duzeltmesi):",
          "  Yukaridaki (A) tablosu kategori duzeyindeki karari gruba TASIR. Ama",
          "  Fighting/Assault/Abuse ayni gruptadir ve kalip listeleri ortaktir",
          "  ('şiddet','kavga','saldır'). Bu ucu kategori duzeyinde surekli BERABERE",
          "  kaliyor ve pesimist politika onlari BELIRSIZ yapiyor — oysa GRUP duzeyinde",
          "  ucu de AYNI CEVABI gosteriyor, yani orada beraberlik YOKTUR. (A) tablosu",
          "  bu yuzden grup performansini SISTEMATIK OLARAK DUSUK gosterir.",
          "  (B) tablosu top-1'i dogrudan grup duzeyinde calistirir: grup skoru =",
          "  uyelerinin EN YUKSEK skoru (toplam DEGIL — cok uyeli grup avantaj kazanmasin)."]
    L += coksinifli_matris_bas(
        m_grup2, "KARISIKLIK MATRISI — SEMANTIK GRUP duzeyi (B) DOGRUDAN top-1")
    L += coksinifli_metrik_tablosu(m_grup2)
    L += ["", f"    Grup duzeyinde COZULEMEYEN beraberlik: {grup_berabere}/{len(anom)} klip",
          f"    (kategori duzeyinde {berabere_n}/{len(anom)} idi).",
          "    IKI TABLONUN FARKI MODELDEN DEGIL, OLCUM KARARINDAN gelir:",
          f"      (A) eslenmis  : accuracy={_f(m_grup.accuracy)}  macro-F1={_f(m_grup.macro_f1())}",
          f"      (B) dogrudan  : accuracy={_f(m_grup2.accuracy)}  macro-F1={_f(m_grup2.macro_f1())}",
          "    Ikisini de basiyoruz; hangisinin 'gercek' oldugu gorev tanimina baglidir.",
          f"    KAYNAK: benchmark/results/{dosya_adi}"]

    # ---- 4) HESAPLANAMAYANLAR ----
    L += ["", CIZGI, "4) HESAPLANAMAYAN METRIKLER — 'yapamadik' degil, VERI/GOREV TANIMI IZIN VERMIYOR",
          CIZGI]
    for ad, neden, gerek in HESAPLANAMAYAN:
        L += ["", f"  {ad}", f"    NEDEN  : {neden}", f"    GEREKLI: {gerek}"]

    L += ["", CIZGI]

    return (L, {
        "dosya": dosya_adi,
        "eval_dir": veri.get("eval_dir"),
        "n_toplam": len(rows), "n_anomali": len(anom), "n_normal": len(norm),
        "prevalans": prev,
        "ikili": ikili_json,
        "tanim_ozdeslikleri": ozdes,
        "coksinifli_kategori": m_cok.to_dict(),
        "coksinifli_grup_eslenmis": m_grup.to_dict(),
        "coksinifli_grup_dogrudan": m_grup2.to_dict(),
        "berabere_kategori": berabere_n,
        "berabere_grup": grup_berabere,
        "belirsiz_kategori": belirsiz_n,
        "beraberlik_politikalari": politika_json,
        "acik_kume_accuracy": m_acik.accuracy,
        "top1_ayrinti": ayrinti,
        "hesaplanamayan": [{"metrik": a, "neden": n, "gerekli": g}
                           for a, n, g in HESAPLANAMAYAN],
    })


def _varsayilan_dosyalar() -> List[str]:
    """Varsayilan: eval_holdout tam kosusu (en guncel, 8 sinif x 3 klip + 8 normal)."""
    return [os.path.join(ROOT, "benchmark", "results",
                         "evidence_ab_A_20260811_205728.json")]


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dosyalar", nargs="*", help="eval sonuc JSON dosyalari")
    ap.add_argument("--beraberlik", choices=("belirsiz", "sabit", "iyimser"),
                    default="belirsiz", help="top-1 beraberlik politikasi")
    ap.add_argument("--json", dest="json_out", help="sonuclari JSON olarak kaydet")
    args = ap.parse_args(argv)

    dosyalar = list(args.dosyalar) or _varsayilan_dosyalar()
    hepsi = []
    for yol in dosyalar:
        if not os.path.isabs(yol):
            aday = os.path.join(ROOT, yol)
            yol = aday if os.path.exists(aday) else yol
        if not os.path.exists(yol):
            print(f"[ATLANDI] bulunamadi: {yol}")
            continue
        satirlar, js = rapor_uret(yol, beraberlik=args.beraberlik)
        print("\n".join(satirlar))
        hepsi.append(js)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({"dosyalar": hepsi}, f, ensure_ascii=False, indent=2)
        print(f"Kaydedildi: {args.json_out}")
    return 0 if hepsi else 1


if __name__ == "__main__":
    raise SystemExit(main())
