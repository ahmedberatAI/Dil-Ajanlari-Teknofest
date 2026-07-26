#!/usr/bin/env python
"""benchmark/paired_test.py + stats_utils eslestirilmis/guc araclarinin birim testleri.

Bagimliligi YOK (GPU/vLLM/torch/scipy/pytest gerekmez) — dogrudan kosturulur:
    python benchmark/test_paired_test.py     # cikis kodu 0 = hepsi gecti

Fonksiyonlar duz 'test_*' + assert oldugundan pytest KURULUYSA onunla da toplanabilir;
bu depoda pytest kurulu degildir, dogrulama yukaridaki dogrudan kosumla yapilir.

REFERANS DEGERLER (elle dogrulanabilir, tam dyadik kesirler):
    b=2, c=8  -> exact iki-yonlu p = 2*(C(10,0)+C(10,1)+C(10,2))/2^10 = 112/1024 = 0.109375
    b=0, c=5  -> exact iki-yonlu p = 2*C(5,0)/2^5 = 2/32 = 0.0625
    b=c       -> p = 1.0 (kirpilmis)
    b=c=0     -> p = 1.0 (bolme hatasi YOK)
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from benchmark.paired_test import (  # noqa: E402
        METRICS, compare, contingency, format_report, mcnemar_chi2_cc, mcnemar_exact_p,
        mcnemar_power, mcnemar_power_analytic, mcnemar_test, newcombe_paired_diff_ci,
        norm_cdf, norm_ppf, pair_rows, phi_coefficient, project_to_n, required_n,
        required_n_analytic,
    )
    from benchmark.stats_utils import Z95, wilson_ci  # noqa: E402
except ImportError:  # dogrudan benchmark/ icinden calistirilirsa
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from paired_test import (  # noqa: E402
        METRICS, compare, contingency, format_report, mcnemar_chi2_cc, mcnemar_exact_p,
        mcnemar_power, mcnemar_power_analytic, mcnemar_test, newcombe_paired_diff_ci,
        norm_cdf, norm_ppf, pair_rows, phi_coefficient, project_to_n, required_n,
        required_n_analytic,
    )
    from stats_utils import Z95, wilson_ci  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


# ===========================================================================
# 1) McNEMAR EXACT — referans degerler
# ===========================================================================

def test_mcnemar_exact_referans_8_2() -> None:
    """Gozlenen recall oruntusu: 8 klip B lehine, 2 klip A lehine -> p = 0.109375."""
    p = mcnemar_exact_p(2, 8)
    assert _close(p, 0.109375), f"b=2,c=8 -> {p!r} (bekl 0.109375)"
    # elle kontrol: 2*(1+10+45)/1024
    assert _close(p, 2 * (1 + 10 + 45) / 1024)
    # simetrik olmali (iki-yonlu test yon ayirt etmez)
    assert _close(mcnemar_exact_p(8, 2), 0.109375)
    # alpha=0.05'te ANLAMLI DEGIL -> gorevdeki iddia dogrulanir
    assert p > 0.05


def test_mcnemar_exact_referans_5_0() -> None:
    """Gozlenen kategori oruntusu: 5-0 -> p = 0.0625 (sinirda, hala anlamli DEGIL)."""
    p = mcnemar_exact_p(0, 5)
    assert _close(p, 0.0625), f"b=0,c=5 -> {p!r} (bekl 0.0625)"
    assert _close(p, 2 / 32)
    assert _close(mcnemar_exact_p(5, 0), 0.0625)
    assert p > 0.05
    # 6-0 ilk kez esigi gecer (2/64 = 0.03125): tek klip farkin onemi
    assert _close(mcnemar_exact_p(0, 6), 0.03125) and mcnemar_exact_p(0, 6) < 0.05


def test_mcnemar_exact_esitlik_ve_sifir() -> None:
    """b == c -> p = 1.0 (kanit yok);  n = 0 -> p = 1.0 (bolme hatasi YOK)."""
    for k in range(0, 25):
        p = mcnemar_exact_p(k, k)
        assert _close(p, 1.0), f"b=c={k} -> {p!r}"
    assert mcnemar_exact_p(0, 0) == 1.0          # n=0: ZeroDivisionError OLMAZ
    assert mcnemar_test(0, 0, 0, 0)["p_exact"] == 1.0
    assert mcnemar_test(10, 0, 0, 10)["p_exact"] == 1.0  # hic uyusmazlik yok


def test_mcnemar_exact_ozellikleri() -> None:
    """p her zaman (0, 1]; b+c buyudukce ayni oranda etki daha anlamli olur."""
    for b in range(0, 12):
        for c in range(0, 12):
            p = mcnemar_exact_p(b, c)
            assert 0.0 < p <= 1.0, f"({b},{c}) -> {p}"
    # ayni 4:1 orani, artan n -> p monoton azalir
    ps = [mcnemar_exact_p(k, 4 * k) for k in (1, 2, 4, 8, 16)]
    assert all(ps[i] > ps[i + 1] for i in range(len(ps) - 1)), ps
    # gorevdeki ana iddia: 8-2 oruntusu n=100'e (40-10) tasindiginda p < 0.001
    assert mcnemar_exact_p(10, 40) < 0.001
    # gecersiz girdi reddedilir
    for bad in [(-1, 5), (3, -2)]:
        try:
            mcnemar_exact_p(*bad)
        except ValueError:
            continue
        raise AssertionError(f"gecersiz {bad} icin ValueError bekleniyordu")


def test_chi2_cc_bilgi_amacli() -> None:
    """Sureklilik-duzeltmeli chi-kare: (|8-2|-1)^2/10 = 2.5, p ~ 0.1138."""
    chi2, p = mcnemar_chi2_cc(2, 8)
    assert _close(chi2, 2.5), chi2
    assert abs(p - 0.1138) < 5e-4, p
    assert mcnemar_chi2_cc(0, 0) == (0.0, 1.0)
    # |b-c| <= 1 iken duzeltme chi2'yi 0'a kirpar (negatif kare uretmez)
    assert mcnemar_chi2_cc(3, 4)[0] == 0.0 and _close(mcnemar_chi2_cc(3, 4)[1], 1.0)
    # exact ile ayni buyukluk mertebesinde olmali (karar exact ile verilir)
    assert abs(p - mcnemar_exact_p(2, 8)) < 0.02


# ===========================================================================
# 2) NEWCOMBE ESLESTIRILMIS FARK-GA
# ===========================================================================

def test_newcombe_fark_ga_recall() -> None:
    """Olculen recall tablosu: a=3, b=2, c=8, d=7 (n=20; A 5/20, B 11/20)."""
    a, b, c, d = 3, 2, 8, 7
    assert (a + b) == 5 and (a + c) == 11 and (a + b + c + d) == 20
    lo, hi = newcombe_paired_diff_ci(a, b, c, d)
    diff = (c - b) / 20
    assert _close(diff, 0.30)
    assert lo < diff < hi
    # elle hesap (Wilson 5/20 ve 11/20 + phi duzeltmesi) ~ [0.007, 0.530]
    assert abs(lo - 0.0071) < 2e-3, lo
    assert abs(hi - 0.5298) < 2e-3, hi
    # aralik her zaman [-1, 1] icinde
    assert -1.0 <= lo <= hi <= 1.0


def test_newcombe_sinir_durumlari() -> None:
    # n=0 -> hicbir iddia yok
    assert newcombe_paired_diff_ci(0, 0, 0, 0) == (-1.0, 1.0)
    # hic uyusmazlik yok -> fark 0 ve aralik 0'i icerir
    lo, hi = newcombe_paired_diff_ci(10, 0, 0, 10)
    assert lo <= 0.0 <= hi
    # tam ters yon -> fark negatif
    lo, hi = newcombe_paired_diff_ci(3, 8, 2, 7)
    assert hi < 0.0 or (lo < -0.2 < hi)
    assert _close((2 - 8) / 20, -0.30)
    # uc durumlar: A 0/n, B n/n
    lo, hi = newcombe_paired_diff_ci(0, 0, 10, 0)
    assert lo > 0.5 and hi <= 1.0, (lo, hi)
    # her (a,b,c,d) icin aralik gecerli ve farki icerir
    for a in range(0, 6):
        for b in range(0, 6):
            for c in range(0, 6):
                for d in range(0, 6):
                    n = a + b + c + d
                    if n == 0:
                        continue
                    lo, hi = newcombe_paired_diff_ci(a, b, c, d)
                    diff = (c - b) / n
                    assert -1.0 <= lo <= diff <= hi <= 1.0, (a, b, c, d, lo, diff, hi)


def test_newcombe_phi_duzeltmesi_gercekten_uygulaniyor() -> None:
    """TAM uyumda (b=c=0, p=0.5) aralik [0,0]'a COKMELI.

    Bu, eslestirilmis (phi-duzeltmeli) formulun BAGIMSIZ 'square-and-add'den ayirt
    edildigi kritik testtir: her klipte iki kosu ayni sonucu verdiyse fark kesin 0'dir
    ve belirsizlik YOKTUR. phi duzeltmesi yapilmazsa aralik hatali sekilde genis cikar.
    """
    lo, hi = newcombe_paired_diff_ci(10, 0, 0, 10)   # p1 = p2 = 0.5
    assert _close(phi_coefficient(10, 0, 0, 10), 1.0)
    assert _close(lo, 0.0) and _close(hi, 0.0), (lo, hi)
    # duzeltmesiz (bagimsiz) hesap ayni tabloda cok daha genis olurdu (~+/-0.31)
    wl, wu = wilson_ci(10, 20)
    naive = math.sqrt((0.5 - wl) ** 2 + (wu - 0.5) ** 2)
    assert naive > 0.25, naive
    # DOKUMANTE EDILEN SINIRLILIK: p != 0.5 iken tam uyumda bile kucuk genislik kalir
    lo2, hi2 = newcombe_paired_diff_ci(5, 0, 0, 15)  # p1 = p2 = 0.25
    assert lo2 < 0.0 < hi2 and (hi2 - lo2) < 0.20, (lo2, hi2)


def test_phi_katsayisi() -> None:
    assert _close(phi_coefficient(0, 0, 0, 0), 0.0)      # kenar toplami 0 -> 0
    assert _close(phi_coefficient(10, 0, 0, 10), 1.0)    # tam uyum
    assert -1.0 <= phi_coefficient(3, 2, 8, 7) <= 1.0
    # eslestirme guclu ise (buyuk a,d) fark-GA'si daha DAR olmali
    w_dep = newcombe_paired_diff_ci(45, 2, 8, 45)
    w_ind = newcombe_paired_diff_ci(20, 2, 8, 70)
    assert (w_dep[1] - w_dep[0]) < (w_ind[1] - w_ind[0])


def test_mcnemar_test_sozlugu() -> None:
    d = mcnemar_test(3, 2, 8, 7, alpha=0.05)
    assert d["n_pairs"] == 20 and d["b"] == 2 and d["c"] == 8
    assert d["rate_a"]["k"] == 5 and d["rate_b"]["k"] == 11
    assert _close(d["p_exact"], 0.109375)
    assert d["significant"] is False
    assert d["direction"] == "B daha iyi"
    assert _close(d["diff_b_minus_a"], 0.30)
    assert "newcombe" in d["diff_ci_method"].lower()
    # kol oranlari Wilson GA'si ile uyusmali (K15)
    lo, hi = wilson_ci(5, 20)
    assert _close(d["rate_a"]["ci_low"], round(lo, 4)) and _close(d["rate_a"]["ci_high"], round(hi, 4))


# ===========================================================================
# 3) NORMAL DAGILIM YARDIMCILARI
# ===========================================================================

def test_norm_cdf_ppf() -> None:
    assert _close(norm_cdf(0.0), 0.5)
    assert abs(norm_cdf(1.959963984540054) - 0.975) < 1e-12
    assert abs(norm_ppf(0.975) - Z95) < 1e-9
    assert abs(norm_ppf(0.80) - 0.8416212335729143) < 1e-9
    assert abs(norm_ppf(0.5)) < 1e-12
    # ters fonksiyon tutarliligi
    for p in (0.001, 0.01, 0.2, 0.5, 0.7, 0.99, 0.999):
        assert abs(norm_cdf(norm_ppf(p)) - p) < 1e-10, p
    for bad in (0.0, 1.0, -0.1, 1.5):
        try:
            norm_ppf(bad)
        except ValueError:
            continue
        raise AssertionError(f"norm_ppf({bad}) ValueError vermeliydi")


# ===========================================================================
# 4) GUC ANALIZI
# ===========================================================================

def test_guc_temel_ozellikler() -> None:
    """Guc: n ile artar, etki ile artar; etki yoksa alpha'nin altinda kalir."""
    pd_, ratio = 0.5, 4.0
    powers = [mcnemar_power(pd_, ratio, n) for n in (10, 20, 50, 100, 200)]
    assert all(powers[i] <= powers[i + 1] + 1e-12 for i in range(len(powers) - 1)), powers
    assert powers[0] < 0.3 and powers[-1] > 0.99
    # n=20'de olculen etki icin guc DUSUK (gorevdeki "yetersiz guc" iddiasinin kaniti)
    assert mcnemar_power(0.5, 4.0, 20) < 0.5
    # n=100'de ayni etki icin guc COK YUKSEK
    assert mcnemar_power(0.5, 4.0, 100) > 0.95
    # etki yok (ratio=1) -> deger gucun degil gerceklesen tip-1 hatasinin tahmini;
    # exact test AYRIK oldugu icin alpha'nin ALTINDA kalir (muhafazakar)
    assert mcnemar_power(0.5, 1.0, 20) <= 0.05
    assert mcnemar_power(0.5, 1.0, 100) <= 0.05
    # uyusmazlik yok / n yok -> red imkansiz
    assert mcnemar_power(0.0, 4.0, 100) == 0.0
    assert mcnemar_power(0.5, 4.0, 0) == 0.0
    # ratio=inf (A hic tek basina dogru degil) desteklenir
    assert 0.0 < mcnemar_power(0.25, math.inf, 20) < 1.0
    assert mcnemar_power(0.25, math.inf, 100) > 0.99
    # buyuk etki -> daha yuksek guc
    assert mcnemar_power(0.5, 9.0, 20) > mcnemar_power(0.5, 2.0, 20)


def test_guc_exact_vs_analitik() -> None:
    """Analitik (Connor) guc, exact gucu buyuklukce dogrulamali (exact daha muhafazakar)."""
    for n in (20, 50, 100, 200):
        pe = mcnemar_power(0.5, 4.0, n)
        pa = mcnemar_power_analytic(0.5, 4.0, n)
        assert abs(pe - pa) < 0.15, (n, pe, pa)
        assert pe <= pa + 1e-9, f"n={n}: exact ({pe}) analitikten ({pa}) buyuk cikti"


def test_required_n_mantik() -> None:
    """DAHA KUCUK etki -> DAHA BUYUK n (gorevde istenen mantik testi)."""
    # etkiyi ratio ile kucult: 9 > 4 > 2 > 1.5  =>  n artmali
    ns = [required_n(0.5, r) for r in (9.0, 4.0, 2.0, 1.5)]
    assert all(x is not None for x in ns), ns
    assert ns[0] < ns[1] < ns[2] < ns[3], ns
    # uyusmazlik oranini dusurmek de etkiyi kucultur -> n artar
    assert required_n(0.5, 4.0) < required_n(0.2, 4.0) < required_n(0.05, 4.0)
    # daha yuksek guc talebi -> daha buyuk n
    assert required_n(0.5, 4.0, power=0.80) < required_n(0.5, 4.0, power=0.95)
    # daha kucuk alpha -> daha buyuk n
    assert required_n(0.5, 4.0, alpha=0.05) < required_n(0.5, 4.0, alpha=0.01)
    # etki yok -> hicbir n yetmez
    assert required_n(0.5, 1.0) is None
    assert required_n(0.0, 4.0) is None
    # n_max asilirsa None (sonsuz donguye girmez)
    assert required_n(0.02, 1.05, n_max=500) is None
    # gecersiz guc reddedilir
    for bad in (0.0, 1.0, 1.2):
        try:
            required_n(0.5, 4.0, power=bad)
        except ValueError:
            continue
        raise AssertionError(f"power={bad} ValueError vermeliydi")


def test_required_n_dondugu_n_gucu_saglar() -> None:
    """required_n'in dondurdugu n GERCEKTEN hedef gucu saglar; n-1 saglamaz-civari."""
    for pd_, ratio in ((0.5, 4.0), (0.25, math.inf), (0.4, 3.0)):
        n = required_n(pd_, ratio, power=0.80)
        assert n is not None
        assert mcnemar_power(pd_, ratio, n) >= 0.80, (pd_, ratio, n)
        # analitik saglama ayni mertebede olmali (exact >= analitik, ayrik test)
        na = required_n_analytic(pd_, ratio, power=0.80)
        assert na is not None and abs(n - na) <= max(6, 0.35 * na), (n, na)


def test_project_to_n_gorev_sorusu() -> None:
    """'Gozlenen 8-2 oruntusu n=100'de anlamli olur mu?' -> EVET, p<0.001."""
    pw = project_to_n(2, 8, n_obs=20, n_target=100)
    assert pw["observed"]["p_exact"] == 0.109375
    assert pw["observed"]["significant"] is False
    assert _close(pw["p_disagree"], 0.5)
    assert pw["ratio_c_over_b"] == 4.0
    # oransal olcek: 2->10, 8->40
    assert pw["scaled"]["b"] == 10 and pw["scaled"]["c"] == 40
    assert pw["scaled"]["p_exact"] < 0.001 and pw["scaled"]["significant"] is True
    # guc: n=20'de yetersiz, n=100'de yeterli
    assert pw["power_at_n_obs"] < 0.5
    assert pw["power_at_n_target"] > 0.95
    # %80 guc icin gereken n, 20'nin UZERINDE ama 100'un ALTINDA olmali
    assert 20 < pw["required_n_power80"] < 100, pw["required_n_power80"]

    # kategori oruntusu 5-0 (ratio = inf)
    pc = project_to_n(0, 5, n_obs=20, n_target=100)
    assert pc["observed"]["p_exact"] == 0.0625
    assert pc["ratio_c_over_b"] == "inf"
    assert pc["scaled"]["b"] == 0 and pc["scaled"]["c"] == 25
    assert pc["scaled"]["p_exact"] < 0.001
    assert 20 < pc["required_n_power80"] < 100

    # gecersiz girdi: b+c, n_obs'u asamaz
    for bad in [(5, 20, 20), (0, 0, 0)]:
        try:
            project_to_n(bad[0], bad[1], n_obs=bad[2], n_target=100)
        except ValueError:
            continue
        raise AssertionError(f"gecersiz {bad} icin ValueError bekleniyordu")


# ===========================================================================
# 5) ESLESTIRME + TABLO KURULUMU (JSON'suz, sentetik satirlarla)
# ===========================================================================

def _row(path: str, anom: bool, n_events: int = 0, cat: bool = False,
         risk: int = 1, trig: int = 0, sev: int = 0) -> dict:
    return {"path": path, "is_anomaly": anom, "n_events": n_events,
            "category_match": cat, "risk_ord": risk, "max_severity": sev,
            "triggered": ["x"] * trig}


def test_pair_rows_ve_contingency() -> None:
    a = {"p1": _row("p1", True, 0), "p2": _row("p2", True, 2), "pX": _row("pX", True, 1)}
    b = {"p1": _row("p1", True, 3), "p2": _row("p2", True, 0), "pY": _row("pY", True, 1)}
    pairs, only_a, only_b = pair_rows(a, b)
    assert [p for p, _, _ in pairs] == ["p1", "p2"]
    assert only_a == ["pX"] and only_b == ["pY"]

    recall = next(m for m in METRICS if m.name == "recall")
    ca, cb, cc, cd, flip_a, flip_b = contingency(pairs, recall)
    # p1: A yanlis / B dogru -> c ;  p2: A dogru / B yanlis -> b
    assert (ca, cb, cc, cd) == (0, 1, 1, 0)
    assert flip_a == ["p2"] and flip_b == ["p1"]

    # alt kume filtresi: normal metrigi anomali kliplerde HIC sayilmaz
    nod = next(m for m in METRICS if m.name == "normal_no_dispatch")
    assert sum(contingency(pairs, nod)[:4]) == 0

    # is_anomaly CELISKISI olan klip dislanir (sessizce yanlis kumeye girmez)
    a2 = {"pz": _row("pz", True, 0)}
    b2 = {"pz": _row("pz", False, 3)}
    pairs2, _, _ = pair_rows(a2, b2)
    assert sum(contingency(pairs2, recall)[:4]) == 0


def test_fp_metrikleri_yuksek_iyi_yonunde() -> None:
    """Normal kliplerde 'dogru' = FP YOK; B daha cok tetiklerse c<b olmali."""
    a = {f"n{i}": _row(f"n{i}", False, 0, trig=0) for i in range(4)}
    b = {f"n{i}": _row(f"n{i}", False, 0, trig=(1 if i < 3 else 0)) for i in range(4)}
    pairs, _, _ = pair_rows(a, b)
    nod = next(m for m in METRICS if m.name == "normal_no_dispatch")
    ca, cb, cc, cd, _, _ = contingency(pairs, nod)
    # A hepsinde FP'siz (dogru), B 3'unde tetikledi (yanlis) -> b=3, c=0
    assert (ca, cb, cc, cd) == (1, 3, 0, 0)
    res = mcnemar_test(ca, cb, cc, cd)
    assert res["diff_b_minus_a"] < 0 and res["direction"] == "A daha iyi"


def test_metrik_kaydi_tutarli() -> None:
    names = [m.name for m in METRICS]
    assert len(names) == len(set(names)), "metrik adlari mukerrer"
    assert {m.subset for m in METRICS} == {"anomali", "normal"}
    # gorevde istenen dort cekirdek metrik mevcut mu
    for req in ("recall", "cat_match", "risk_cal_anom", "normal_no_dispatch"):
        assert req in names, req
    for m in METRICS:
        assert m.label and m.desc, m.name
        assert isinstance(m.ok(_row("x", True, 1, True, 4, 1, 4)), bool)


# ===========================================================================
# 6) UCTAN UCA: gercek eval JSON'lari varsa eslestirilmis kosuyu dogrula
# ===========================================================================

A_FILE = os.path.join(ROOT, "benchmark", "results", "eval_20260726_002608.json")
B_FILE = os.path.join(ROOT, "benchmark", "results", "eval_20260726_003531.json")


def test_gercek_dosyalarla_uctan_uca() -> None:
    """Olculen A/B (kurallar KAPALI vs ACIK): recall 8-2 p~0.109, kategori 5-0 p~0.063.

    Dosyalar yoksa test ATLANIR (baska makinede de kosabilsin diye).
    """
    if not (os.path.isfile(A_FILE) and os.path.isfile(B_FILE)):
        print("      (atlandi: eval JSON dosyalari yok)")
        return
    res = compare(A_FILE, B_FILE, label_a="kurallar KAPALI", label_b="kurallar ACIK",
                  project_n=100)
    assert res["meta"]["n_pairs"] == 40, res["meta"]
    assert res["meta"]["n_anomaly_pairs"] == 20 and res["meta"]["n_normal_pairs"] == 20
    assert res["meta"]["n_only_a"] == 0 and res["meta"]["n_only_b"] == 0

    rc = res["metrics"]["recall"]
    assert (rc["b"], rc["c"]) == (2, 8), (rc["b"], rc["c"])
    assert rc["rate_a"]["k"] == 5 and rc["rate_b"]["k"] == 11
    assert _close(rc["p_exact"], 0.109375)
    assert rc["significant"] is False

    cm = res["metrics"]["cat_match"]
    assert (cm["b"], cm["c"]) == (0, 5), (cm["b"], cm["c"])
    assert cm["rate_a"]["k"] == 2 and cm["rate_b"]["k"] == 7
    assert _close(cm["p_exact"], 0.0625)
    assert cm["significant"] is False

    # guc bolumu: her iki oruntu de n=100'de anlamli olur
    assert res["power"]["recall"]["scaled"]["p_exact"] < 0.001
    assert res["power"]["cat_match"]["scaled"]["p_exact"] < 0.001

    # rapor metni uretilebiliyor ve kritik bilgileri iceriyor
    txt = format_report(res, show_flips=True)
    assert "McNemar" in txt and "0.1094" in txt and "GUC ANALIZI" in txt
    assert "ANOMALI klipler" in txt and "NORMAL klipler" in txt


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    print("paired_test / stats_utils eslestirilmis+guc birim testleri")
    print("-" * 72)
    for t in tests:
        try:
            t()
            print(f"  [GECTI]  {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  [KALDI]  {t.__name__}: {type(e).__name__}: {e}")
    print("-" * 72)
    print(f"{len(tests) - failed}/{len(tests)} test gecti")
    print()
    print("Referans degerler (gorunur dogrulama):")
    for b, c in [(2, 8), (0, 5), (0, 6), (5, 5), (0, 0), (10, 40)]:
        print(f"  mcnemar_exact_p(b={b:2d}, c={c:2d}) = {mcnemar_exact_p(b, c):.10g}")
    print(f"  newcombe_paired_diff_ci(3,2,8,7)  = "
          f"[{newcombe_paired_diff_ci(3, 2, 8, 7)[0]:+.4f}, "
          f"{newcombe_paired_diff_ci(3, 2, 8, 7)[1]:+.4f}]")
    for n in (20, 40, 100):
        print(f"  mcnemar_power(p_disagree=0.5, ratio=4, n={n:3d}) = "
              f"{mcnemar_power(0.5, 4.0, n):.4f}")
    print(f"  required_n(0.5, 4.0, power=0.80)  = {required_n(0.5, 4.0)}   "
          f"(analitik: {required_n_analytic(0.5, 4.0)})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
