#!/usr/bin/env python
"""Raporlama hijyeni yardimcilari (K15): Wilson %95 guven araligi + ondalik disiplini.

NEDEN: Kucuk orneklemlerde (n<=48) tek bir nokta-deger ("%98.7", "%0 yanlis pozitif")
yaniltici. Ornegin 0/6 gozlem "FP %0" gibi gorunur ama gercek oran %39'a kadar cikabilir.
Bu modul her oran metrigini (k/n) Wilson score araligi ile birlikte sunar.

Neden Wilson: normal-yaklasim (Wald) araligi k=0 veya k=n oldugunda cokuyor
([0,0] / [1,1] uretiyor) ve kucuk n'de kapsama orani bozuk. Wilson bu uclarda da
anlamli, asimetrik ve [0,1] icinde kalan bir aralik verir.

Kullanim:
    from benchmark.stats_utils import wilson_ci, rate, fmt_rate
    lo, hi = wilson_ci(17, 18)          # -> (0.7424, 0.9901)
    rate(0, 6)                          # -> {"k":0,"n":6,"p":0.0,"ci_low":0.0,"ci_high":0.3903,...}
    fmt_rate(17, 18)                    # -> "%94 [%74–%99]  (17/18)"

ESLESTIRILMIS (paired) A/B araclari — ayni klipler uzerinde iki kosu kiyaslanirken:
    mcnemar_exact_p(b=2, c=8)           # -> 0.109375  (iki-yonlu tam binom testi)
    newcombe_paired_diff_ci(3, 2, 8, 7) # -> pB - pA farkinin %95 GA'si
    mcnemar_power(0.5, 4.0, n=20)       # eslestirilmis tasarimda GUC
    required_n(0.5, 4.0, power=0.80)    # %80 guc icin gereken cift sayisi
    project_to_n(2, 8, 20, 100)         # "8-2 oruntusu n=100'de anlamli olur mu?"

BAGIMLILIK POLITIKASI: yalniz stdlib (math). scipy/statsmodels KASITLI OLARAK yok —
math.comb ile tam (exact) binom hesabi yapiliyor, yaklasima ihtiyac duyulmuyor.

Birim testleri:  python benchmark/test_stats_utils.py
                 python benchmark/test_paired_test.py
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Iterable, Optional, Sequence, Tuple

# %95 iki-yonlu normal kuantil (z_{0.975})
Z95 = 1.959963984540054

# Bu esigin altinda/esitinde ondalikli yuzde YAZILMAZ (n=18'de "%94.4" sahte kesinlik).
SMALL_N_THRESHOLD = 48


def wilson_ci(k: int, n: int, z: float = Z95) -> Tuple[float, float]:
    """k basari / n deneme icin Wilson score guven araligi.

    Args:
        k: basari sayisi (0 <= k <= n)
        n: toplam deneme sayisi
        z: normal kuantil (varsayilan %95 -> 1.96)

    Returns:
        (alt_sinir, ust_sinir), her ikisi de [0.0, 1.0] araliginda.
        n == 0 ise bilgi yok demektir -> (0.0, 1.0) doner (FAIL-OPEN: iddia yok).

    Raises:
        ValueError: k negatif veya k > n ise.
    """
    if n < 0:
        raise ValueError(f"n negatif olamaz: {n}")
    if n == 0:
        return (0.0, 1.0)
    if k < 0 or k > n:
        raise ValueError(f"gecersiz k/n: {k}/{n}")

    z2 = z * z
    denom = n + z2
    center = (k + z2 / 2.0) / denom
    half = (z / denom) * math.sqrt((k * (n - k)) / n + z2 / 4.0)
    lo = center - half
    hi = center + half
    # Uc noktalarda kapali form TAM 0 / TAM 1 verir; kayan-nokta artigini (≈5e-17) temizle.
    if k == 0:
        lo = 0.0
    if k == n:
        hi = 1.0
    return (max(0.0, lo), min(1.0, hi))


def rate(k: int, n: int, z: float = Z95) -> dict:
    """Oran metrigini nokta-deger + Wilson araligi ile yapilandirilmis sozluk olarak dondurur.

    Cikti JSON'una BU sozluk yazilir; nokta-deger tek basina raporlanmaz.
    """
    lo, hi = wilson_ci(k, n, z) if n else (0.0, 1.0)
    p = (k / n) if n else 0.0
    return {
        "k": int(k),
        "n": int(n),
        "p": round(p, 4),
        "ci_low": round(lo, 4),
        "ci_high": round(hi, 4),
        "ci_method": "wilson",
        "ci_level": 0.95,
    }


def rate_from_bools(xs: Iterable[bool], z: float = Z95) -> dict:
    """Bool/0-1 dizisinden dogrudan oran+CI uretir (frac() yerine kullanilmali)."""
    xs = [1 if x else 0 for x in xs]
    return rate(sum(xs), len(xs), z)


def pct_decimals(n: int) -> int:
    """Ornekleme buyuklugune gore kac ondalik basamak MESRU (K15 ondalik hijyeni).

    n <= 48  -> 0 basamak  (n=18'de tek bir klip %5.6 oynatir; ondalik sahte kesinlik)
    n  > 48  -> 1 basamak
    """
    return 0 if n <= SMALL_N_THRESHOLD else 1


def fmt_pct(p: float, n: int) -> str:
    """Orani, ornekleme buyuklugune uygun ondalik disiplini ile yuzdeye cevirir."""
    return f"%{p * 100:.{pct_decimals(n)}f}"


def fmt_rate(k: int, n: int, z: float = Z95, show_counts: bool = True) -> str:
    """Insan-okur tek satir: nokta-deger + Wilson %95 CI + ham sayimlar.

    Ornek: fmt_rate(0, 6) -> "%0 [%0–%39]  (0/6)"
    """
    if n == 0:
        return "n/a  (0/0)"
    d = rate(k, n, z)
    s = (f"{fmt_pct(d['p'], n)} "
         f"[{fmt_pct(d['ci_low'], n)}–{fmt_pct(d['ci_high'], n)}]")
    if show_counts:
        s += f"  ({k}/{n})"
    return s


def fmt_rate_dict(d: Optional[dict], show_counts: bool = True) -> str:
    """rate() sozlugunu insan-okur satira cevirir (yeniden hesaplamadan)."""
    if not d or not d.get("n"):
        return "n/a  (0/0)"
    n = d["n"]
    s = (f"{fmt_pct(d['p'], n)} "
         f"[{fmt_pct(d['ci_low'], n)}–{fmt_pct(d['ci_high'], n)}]")
    if show_counts:
        s += f"  ({d['k']}/{n})"
    return s


def pseudo_replication_note(n_unit: int, n_subscore: int, unit: str = "klip") -> Optional[str]:
    """Alt-skor sayisi bagimsiz birim sayisindan buyukse PSEUDO-REPLIKASYON uyarisi uretir.

    Or. 30 klip x 3 kalite ekseni = 90 alt-skor; "n=90" yazmak bagimsizlik iddiasidir
    ve YANLISTIR. Bagimsiz birim sayisi 30'dur.
    """
    if n_unit and n_subscore > n_unit:
        return (f"PSEUDO-REPLIKASYON: {n_subscore} alt-skor yalnizca {n_unit} bagimsiz "
                f"{unit}den geliyor; guven araligi n={n_unit} uzerinden okunmalidir.")
    return None


def mean_sd(vals: Sequence[float]) -> Tuple[Optional[float], float, int]:
    """(ortalama, orneklem std, n). Bos dizide (None, 0.0, 0)."""
    vals = [float(v) for v in vals]
    if not vals:
        return (None, 0.0, 0)
    m = sum(vals) / len(vals)
    if len(vals) < 2:
        return (m, 0.0, 1)
    var = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
    return (m, math.sqrt(var), len(vals))


# ===========================================================================
# NORMAL DAGILIM (guc analizi icin gerekli; scipy YOK)
# ===========================================================================

def norm_cdf(x: float) -> float:
    """Standart normal birikimli dagilim Phi(x) — math.erf uzerinden tam."""
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


# Acklam rasyonel yaklasimi katsayilari (norm_ppf icin)
_PPF_A = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
          1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
_PPF_B = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
          6.680131188771972e+01, -1.328068155288572e+01)
_PPF_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
          -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
_PPF_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
          3.754408661907416e+00)
_PPF_PLOW = 0.02425


def norm_ppf(p: float) -> float:
    """Standart normal ters birikimli dagilim (kuantil) Phi^-1(p).

    Acklam rasyonel yaklasimi + tek adim Halley duzeltmesi -> bagil hata ~1e-15.
    scipy.stats.norm.ppf yerine kullanilir (bagimlilik eklememek icin).

    Raises:
        ValueError: p, (0, 1) araliginda degilse.
    """
    if not (0.0 < p < 1.0):
        raise ValueError(f"norm_ppf icin 0<p<1 gerekir: {p}")
    if p < _PPF_PLOW:
        q = math.sqrt(-2.0 * math.log(p))
        x = ((((((_PPF_C[0] * q + _PPF_C[1]) * q + _PPF_C[2]) * q + _PPF_C[3]) * q
              + _PPF_C[4]) * q + _PPF_C[5])
             / ((((_PPF_D[0] * q + _PPF_D[1]) * q + _PPF_D[2]) * q + _PPF_D[3]) * q + 1.0))
    elif p <= 1.0 - _PPF_PLOW:
        q = p - 0.5
        r = q * q
        x = (((((((_PPF_A[0] * r + _PPF_A[1]) * r + _PPF_A[2]) * r + _PPF_A[3]) * r
               + _PPF_A[4]) * r + _PPF_A[5]) * q)
             / ((((((_PPF_B[0] * r + _PPF_B[1]) * r + _PPF_B[2]) * r + _PPF_B[3]) * r
                 + _PPF_B[4]) * r + 1.0)))
    else:
        q = math.sqrt(-2.0 * math.log1p(-p))
        x = -((((((_PPF_C[0] * q + _PPF_C[1]) * q + _PPF_C[2]) * q + _PPF_C[3]) * q
               + _PPF_C[4]) * q + _PPF_C[5])
              / ((((_PPF_D[0] * q + _PPF_D[1]) * q + _PPF_D[2]) * q + _PPF_D[3]) * q + 1.0))
    # Halley ile bir adim iyilestirme (yaklasimin ~1e-9 hatasini ~1e-15'e indirir)
    e = norm_cdf(x) - p
    u = e * math.sqrt(2.0 * math.pi) * math.exp(x * x / 2.0)
    return x - u / (1.0 + x * u / 2.0)


# ===========================================================================
# BINOM YARDIMCILARI (log-uzayinda kararli; buyuk m'de tasma yok)
# ===========================================================================

def _binom_pmf_log(m: int, i: int, p: float) -> float:
    """log P(X=i), X~Binom(m, p). Imkansiz durumda -inf."""
    if i < 0 or i > m:
        return -math.inf
    if p <= 0.0:
        return 0.0 if i == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if i == m else -math.inf
    return (math.lgamma(m + 1) - math.lgamma(i + 1) - math.lgamma(m - i + 1)
            + i * math.log(p) + (m - i) * math.log1p(-p))


def _binom_cdf(m: int, k: int, p: float) -> float:
    """P(X <= k), X~Binom(m, p). Log-toplam ile kararli (log-sum-exp)."""
    if m <= 0:
        return 1.0
    if k < 0:
        return 0.0
    if k >= m:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0
    lp, lq = math.log(p), math.log1p(-p)
    logs = []
    lc = 0.0  # log C(m, 0) = 0
    for i in range(k + 1):
        logs.append(lc + i * lp + (m - i) * lq)
        if i < k:
            lc += math.log(m - i) - math.log(i + 1)
    mx = max(logs)
    if mx == -math.inf:
        return 0.0
    return min(1.0, math.exp(mx) * sum(math.exp(l - mx) for l in logs))


# ===========================================================================
# McNEMAR — ESLESTIRILMIS IKILI METRIK TESTI
# ===========================================================================
# 2x2 uyusmazlik tablosu (ayni klip, iki kosu; "dogru" = metrik saglandi):
#
#                   B dogru   B yanlis
#     A dogru          a          b        <- b: YALNIZ A dogru
#     A yanlis         c          d        <- c: YALNIZ B dogru
#
# H0: uyusmayan ciftlerde yon simetriktir (pi_b == pi_c).
# Uyusan cifler (a, d) H0 hakkinda BILGI TASIMAZ; bu yuzden test yalniz b ve c'ye bakar.

def mcnemar_exact_p(b: int, c: int) -> float:
    """McNemar TAM (exact) iki-yonlu p degeri — binom(n=b+c, p=0.5) uzerinden.

    Kucuk orneklemde DOGRU olan yontem budur: chi-kare yaklasimi n<25 civarinda
    p'yi kucuk gosterir (liberal), tam test ise kesin dagilimi kullanir.

    p = min(1, 2 * P(X <= min(b,c)))   ,  X ~ Binom(b+c, 0.5)

    Args:
        b: yalniz A kosusunun dogru oldugu cift sayisi
        c: yalniz B kosusunun dogru oldugu cift sayisi

    Returns:
        [0, 1] araliginda iki-yonlu p degeri. b+c == 0 ise 1.0 (kanit yok — FAIL-OPEN,
        bolme hatasi da olmaz).

    Referans degerler (birim testi):
        mcnemar_exact_p(2, 8) == 0.109375
        mcnemar_exact_p(0, 5) == 0.0625
        mcnemar_exact_p(k, k) == 1.0   (her k icin)

    Not: b+c > ~1050 oldugunda ve p astronomik kucukken kayan-nokta tabani
    tukendigi icin tam 0.0 donebilir ("p < 1e-308" olarak okunmalidir).
    """
    b, c = int(b), int(c)
    if b < 0 or c < 0:
        raise ValueError(f"b/c negatif olamaz: b={b}, c={c}")
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1))
    # int/int bolme: buyuk sayilarda da dogru yuvarlanir (tasma yok, gerekirse 0.0'a iner)
    return min(1.0, (2 * tail) / (1 << n))


def mcnemar_chi2_cc(b: int, c: int) -> Tuple[float, float]:
    """Sureklilik-duzeltmeli (Edwards) McNemar chi-kare — YALNIZ BILGI AMACLI.

    chi2 = (|b-c| - 1)^2 / (b+c),  1 serbestlik derecesi.

    KARAR bu degerle VERILMEZ (bkz. mcnemar_exact_p): duzeltmeli chi-kare kucuk n'de
    asiri muhafazakar, duzeltmesiz hali ise asiri liberaldir. Burada yalnizca
    literaturle karsilastirilabilirlik icin raporlanir.

    Returns:
        (chi2, p). b+c == 0 ise (0.0, 1.0).
    """
    n = b + c
    if n == 0:
        return (0.0, 1.0)
    chi2 = max(0.0, (abs(b - c) - 1.0)) ** 2 / n
    # 1 sd chi-kare kuyrugu: P(X > chi2) = erfc(sqrt(chi2/2))
    return (chi2, math.erfc(math.sqrt(chi2 / 2.0)))


def phi_coefficient(a: int, b: int, c: int, d: int) -> float:
    """2x2 tablo icin phi (Pearson) korelasyon katsayisi; kenar toplami 0 ise 0.0.

    Eslestirilmis fark-GA'sinda (Newcombe) iki kolun bagimliligini duzeltmek icin
    kullanilir: eslestirme ne kadar guclu ise fark-GA'si o kadar DARALIR.
    """
    marg = (a + b) * (c + d) * (a + c) * (b + d)
    if marg <= 0:
        return 0.0
    return max(-1.0, min(1.0, (a * d - b * c) / math.sqrt(marg)))


def newcombe_paired_diff_ci(a: int, b: int, c: int, d: int,
                            z: float = Z95) -> Tuple[float, float]:
    """ESLESTIRILMIS oran farki (pB - pA) icin %95 guven araligi.

    YONTEM: Newcombe (1998) "Improved confidence intervals for the difference between
    binomial proportions based on paired data", Statistics in Medicine 17:2635-2650,
    Method 10 — "square-and-add" (MOVER) Wilson araliklarinin phi-duzeltmeli
    birlesimi. Yani: her iki kol icin ayri ayri Wilson araligi alinir, kok-kareler
    toplanir ve eslestirmeden gelen korelasyon (phi) ile daraltilir.

    NEDEN Wald degil: Wald fark-GA'si k=0/k=n uclarinda cokuyor ve [-1,1] disina
    tasiyor; Newcombe-Wilson bu uclarda da anlamli kaliyor.

    DURUSTLUK NOTU: bu aralik, tam (exact) McNemar testinin TERSI DEGILDIR. Sinir
    durumlarda GA'nin 0'i dislamasi ile exact p > alpha olmasi AYNI ANDA gorulebilir.
    KARAR her zaman mcnemar_exact_p ile verilir; GA yalnizca ETKI BUYUKLUGUNU
    (farkin buyuklugu ve belirsizligi) gostermek icindir.
    (Olculen ornek: a=3,b=2,c=8,d=7 -> GA [+%1, +%53] 0'i dislar ama exact p=0.109.
     Ayni tabloda eslestirilmis Wald GA'si da [+%2, +%58] verip 0'i dislar; yani bu
     uyusmazlik uygulama hatasi degil, skor-tabanli GA ile ayrik exact testin
     bilinen yontem farkidir. paired_test.py bunu 'ci_test_disagree' ile isaretler.)

    BILINEN SINIRLILIK: Wilson araligi asimetrik oldugu icin, TAM uyum halinde
    (b=c=0) aralik yalnizca p=0.5 civarinda tam olarak [0,0]'a coker; diger
    oranlarda kucuk bir genislik kalir (or. a=5,d=15 -> ~[-%8, +%8]). Bu, yontemin
    muhafazakar tarafta kalan bilinen bir artigidir.

    Args:
        a: her ikisi de dogru
        b: yalniz A dogru
        c: yalniz B dogru
        d: hicbiri dogru degil

    Returns:
        (alt, ust) — pB - pA farki icin aralik, [-1, 1] icinde kirpilmis.
        n == 0 ise (-1.0, 1.0) (bilgi yok -> iddia yok).
    """
    n = a + b + c + d
    if n <= 0:
        return (-1.0, 1.0)
    p_a = (a + b) / n          # A kosusunun basari orani
    p_b = (a + c) / n          # B kosusunun basari orani
    delta = p_b - p_a          # = (c - b) / n
    l_a, u_a = wilson_ci(a + b, n, z)
    l_b, u_b = wilson_ci(a + c, n, z)
    phi = phi_coefficient(a, b, c, d)

    # Alt sinir: B'nin alt sapmasi ile A'nin ust sapmasi birlesir
    t1, t2 = (p_b - l_b), (u_a - p_a)
    rad_lo = t1 * t1 - 2.0 * phi * t1 * t2 + t2 * t2
    # Ust sinir: B'nin ust sapmasi ile A'nin alt sapmasi birlesir
    s1, s2 = (u_b - p_b), (p_a - l_a)
    rad_hi = s1 * s1 - 2.0 * phi * s1 * s2 + s2 * s2

    lo = delta - math.sqrt(max(0.0, rad_lo))
    hi = delta + math.sqrt(max(0.0, rad_hi))
    return (max(-1.0, lo), min(1.0, hi))


def mcnemar_test(a: int, b: int, c: int, d: int, alpha: float = 0.05,
                 z: float = Z95) -> dict:
    """Eslestirilmis 2x2 tablodan TAM rapor sozlugu uretir (JSON'a bu yazilir).

    Args:
        a: her ikisi de dogru,  b: yalniz A dogru,  c: yalniz B dogru,  d: hicbiri
        alpha: anlamlilik esigi (karar exact p ile verilir)

    Returns:
        Sayimlar, iki kolun oran+Wilson GA'si, fark + Newcombe fark-GA'si,
        exact p (KARAR), bilgi amacli chi2-cc, phi ve yon.
    """
    n = a + b + c + d
    p_exact = mcnemar_exact_p(b, c)
    chi2, p_chi2 = mcnemar_chi2_cc(b, c)
    ci_lo, ci_hi = newcombe_paired_diff_ci(a, b, c, d, z)
    delta = ((c - b) / n) if n else 0.0
    return {
        "n_pairs": n,
        "both": int(a), "only_a": int(b), "only_b": int(c), "neither": int(d),
        "b": int(b), "c": int(c),
        "rate_a": rate(a + b, n, z),
        "rate_b": rate(a + c, n, z),
        "diff_b_minus_a": round(delta, 4),
        "diff_ci_low": round(ci_lo, 4),
        "diff_ci_high": round(ci_hi, 4),
        "diff_ci_method": "newcombe1998-method10 (paired wilson square-and-add, phi-corrected)",
        "diff_ci_level": 0.95,
        "phi": round(phi_coefficient(a, b, c, d), 4),
        "p_exact": p_exact,
        "p_method": "mcnemar exact binom(n=b+c, p=0.5), iki-yonlu",
        "chi2_cc": round(chi2, 4),
        "p_chi2_cc": round(p_chi2, 6),
        "alpha": alpha,
        "significant": bool(p_exact <= alpha),
        "direction": ("B daha iyi" if c > b else ("A daha iyi" if b > c else "esit")),
    }


# ===========================================================================
# GUC ANALIZI (eslestirilmis tasarim)
# ===========================================================================

def _rho_from_ratio(ratio: float) -> float:
    """ratio = pi_c / pi_b  ->  rho = uyusmayan cifler icinde B'nin payi = pi_c/(pi_b+pi_c).

    ratio = inf (b hic gorulmuyor) -> rho = 1.0;  ratio = 0 -> rho = 0.0.
    """
    if ratio < 0:
        raise ValueError(f"ratio negatif olamaz: {ratio}")
    if math.isinf(ratio):
        return 1.0
    return ratio / (1.0 + ratio)


@lru_cache(maxsize=8192)
def _exact_crit_k(m: int, alpha: float) -> Optional[int]:
    """m uyusmayan cift icin exact McNemar'in RED BOLGESI esigi.

    En buyuk k (0 <= k <= (m-1)//2) dondurur; oyle ki min(b,c) <= k oldugunda
    exact iki-yonlu p <= alpha. Hicbir k icin red mumkun degilse None.

    Or. alpha=0.05: m=5 -> None (en iyi durumda p=0.0625), m=6 -> 0 (p=0.03125).
    """
    if m <= 0:
        return None
    best: Optional[int] = None
    kmax = (m - 1) // 2
    if m <= 512:
        # tam (big-int) yol: kesin ve hizli
        total = 0
        for k in range(kmax + 1):
            total += math.comb(m, k)
            if (2 * total) / (1 << m) <= alpha:
                best = k
            else:
                break
        return best
    # buyuk m: log-uzayinda (kayan nokta) — alpha ile karsilastirma icin fazlasiyla hassas
    for k in range(kmax + 1):
        if 2.0 * _binom_cdf(m, k, 0.5) <= alpha:
            best = k
        else:
            break
    return best


def mcnemar_power(p_disagree: float, ratio: float, n: int, alpha: float = 0.05,
                  sigma_span: float = 10.0) -> float:
    """ESLESTIRILMIS tasarimda exact McNemar testinin GUCU (kosulsuz/unconditional).

    Model: her cift bagimsiz olarak
        - olasilik p_disagree ile UYUSMAZ (biri dogru, digeri yanlis),
        - uyusmadiysa olasilik rho = ratio/(1+ratio) ile B lehinedir.
    Uyusmayan cift sayisi M ~ Binom(n, p_disagree); M=m verildiginde c ~ Binom(m, rho).
    Guc = SUM_m P(M=m) * P(exact p <= alpha | m)   — yaklasim degil, tam hesap
    (yalnizca P(M=m) ihmal edilebilir olan uc kuyruklar kirpilir, bkz. sigma_span).

    Args:
        p_disagree: uyusmazlik (discordance) olasiligi, [0, 1]
        ratio: pi_c / pi_b (B lehine uyusmazliklarin A lehine olanlara orani).
               math.inf verilebilir (A hic tek basina dogru olmuyor).
        n: cift (klip) sayisi
        alpha: anlamlilik esigi
        sigma_span: M dagiliminda ortalamadan kac std uzaga kadar toplanacagi

    Returns:
        [0, 1] araliginda guc. p_disagree<=0 veya n<=0 ise 0.0 (red imkansiz).

    NOT: ratio == 1 (gercek etki YOK) verildiginde donen deger gucun degil, testin
    GERCEKLESEN TIP-1 HATASININ tahminidir; exact test ayrik oldugu icin bu deger
    alpha'nin ALTINDA kalir (muhafazakarlik).
    """
    if n <= 0 or p_disagree <= 0.0:
        return 0.0
    p_disagree = min(1.0, float(p_disagree))
    rho = _rho_from_ratio(ratio)
    mean = n * p_disagree
    sd = math.sqrt(n * p_disagree * (1.0 - p_disagree))
    lo = max(0, int(mean - sigma_span * sd) - 1)
    hi = min(n, int(mean + sigma_span * sd) + 1)
    total = 0.0
    for m in range(lo, hi + 1):
        log_pm = _binom_pmf_log(n, m, p_disagree)
        if log_pm == -math.inf:
            continue
        pm = math.exp(log_pm)
        if pm <= 0.0:
            continue
        k = _exact_crit_k(m, alpha)
        if k is None:
            continue
        # P(c <= k) + P(c >= m-k);  ikinci terim simetri ile: Binom(m, 1-rho) alt kuyrugu.
        # k <= (m-1)//2 oldugundan iki bolge AYRIKTIR (cift sayim yok).
        p_rej = _binom_cdf(m, k, rho) + _binom_cdf(m, k, 1.0 - rho)
        total += pm * min(1.0, p_rej)
    return min(1.0, total)


def mcnemar_power_analytic(p_disagree: float, ratio: float, n: int,
                           alpha: float = 0.05) -> float:
    """Connor (1987) normal-yaklasimli eslestirilmis guc — SAGLAMA (cross-check) icin.

    z_beta = (|delta|*sqrt(n) - z_{alpha/2}*sqrt(p_d)) / sqrt(p_d - delta^2),
    delta = pi_c - pi_b,  p_d = p_disagree.  Guc = Phi(z_beta).

    Karar/raporlama icin mcnemar_power (exact) tercih edilir; bu fonksiyon yalnizca
    exact hesabin buyuklugunu dogrulamak icindir.
    """
    if n <= 0 or p_disagree <= 0.0:
        return 0.0
    rho = _rho_from_ratio(ratio)
    pi_c = p_disagree * rho
    pi_b = p_disagree * (1.0 - rho)
    delta = pi_c - pi_b
    if delta == 0.0:
        return alpha
    var = p_disagree - delta * delta
    if var <= 0.0:
        return 1.0
    z_a = norm_ppf(1.0 - alpha / 2.0)
    z_beta = (abs(delta) * math.sqrt(n) - z_a * math.sqrt(p_disagree)) / math.sqrt(var)
    return max(0.0, min(1.0, norm_cdf(z_beta)))


def required_n(p_disagree: float, ratio: float, power: float = 0.80,
               alpha: float = 0.05, n_max: int = 20000,
               stable_window: int = 3) -> Optional[int]:
    """Verilen etki icin hedef guce ulasan EN KUCUK cift sayisi (exact McNemar).

    Args:
        p_disagree: uyusmazlik olasiligi
        ratio: pi_c / pi_b (math.inf olabilir)
        power: hedef guc (varsayilan 0.80)
        alpha: anlamlilik esigi
        n_max: arama ust siniri; asilirsa None doner ("bu etki icin pratik degil")
        stable_window: exact test AYRIK oldugu icin guc(n) testere-disi (monoton
            degil) davranir. Donen n icin [n, n+stable_window] araligindaki TUM
            degerlerin hedefi saglamasi sarti konur — yani "sinirda titreyen" bir n
            raporlanmaz.

    Returns:
        Gereken n, ya da etki sifirsa / n_max'e kadar ulasilamazsa None.
        ratio == 1 (etki yok) -> None (hicbir n yetmez).
    """
    if not (0.0 < power < 1.0):
        raise ValueError(f"power (0,1) araliginda olmali: {power}")
    if p_disagree <= 0.0:
        return None
    if (not math.isinf(ratio)) and abs(ratio - 1.0) < 1e-12:
        return None  # gercek fark yok -> hicbir orneklem buyuklugu yetmez

    def ok(n: int) -> bool:
        return mcnemar_power(p_disagree, ratio, n, alpha) >= power

    # 1) ust sinir bul (ikiye katlayarak)
    hi = 8
    while hi <= n_max and not ok(hi):
        hi *= 2
    if hi > n_max:
        return None
    # 2) ikili arama ile ilk saglayan n
    lo = max(1, hi // 2)
    while lo < hi:
        mid = (lo + hi) // 2
        if ok(mid):
            hi = mid
        else:
            lo = mid + 1
    # 3) testere-disi kararliligi: pencere boyunca hedef korunmali
    n = lo
    while n <= n_max:
        if all(ok(n + j) for j in range(1, stable_window + 1)):
            return n
        n += 1
    return None


def required_n_analytic(p_disagree: float, ratio: float, power: float = 0.80,
                        alpha: float = 0.05) -> Optional[int]:
    """Connor (1987) kapali-form orneklem buyuklugu — exact required_n icin SAGLAMA.

    n = [z_{alpha/2}*sqrt(p_d) + z_{power}*sqrt(p_d - delta^2)]^2 / delta^2
    """
    if p_disagree <= 0.0:
        return None
    rho = _rho_from_ratio(ratio)
    delta = p_disagree * (2.0 * rho - 1.0)
    if abs(delta) < 1e-12:
        return None
    var = max(0.0, p_disagree - delta * delta)
    z_a = norm_ppf(1.0 - alpha / 2.0)
    z_p = norm_ppf(power)
    n = (z_a * math.sqrt(p_disagree) + z_p * math.sqrt(var)) ** 2 / (delta * delta)
    return int(math.ceil(n))


def project_to_n(b: int, c: int, n_obs: int, n_target: int,
                 alpha: float = 0.05) -> dict:
    """"Gozlenen b-c oruntusu n_target klipte anlamli olur mu?" sorusunu cevaplar.

    Iki ayri bilgi uretir — karistirilmamalidir:
      1) OLCEKLENMIS SENARYO: ayni oran korunursa (b,c) -> (b*f, c*f), f=n_target/n_obs;
         bu tablonun exact p'si. Bu bir TAHMIN DEGIL, "aynisi tekrarlanirsa" senaryosu.
      2) GUC: gozlenen uyusmazlik yapisi (p_disagree, ratio) GERCEK etki kabul
         edilirse, n_target'te anlamlilik yakalama olasiligi.

    Args:
        b: gozlenen "yalniz A dogru" sayisi
        c: gozlenen "yalniz B dogru" sayisi
        n_obs: gozlemin yapildigi cift sayisi (b+c <= n_obs olmali)
        n_target: hedef cift sayisi
        alpha: anlamlilik esigi

    Returns:
        Olceklenmis sayimlar, exact p'ler, mevcut/hedef guc ve %80 guc icin gereken n.
    """
    if n_obs <= 0:
        raise ValueError("n_obs > 0 olmali")
    if b + c > n_obs:
        raise ValueError(f"b+c ({b + c}) n_obs ({n_obs}) degerini asamaz")
    f = n_target / n_obs
    b2, c2 = int(round(b * f)), int(round(c * f))
    p_disagree = (b + c) / n_obs
    ratio = math.inf if b == 0 else (c / b)
    return {
        "observed": {"b": int(b), "c": int(c), "n": int(n_obs),
                     "p_exact": mcnemar_exact_p(b, c),
                     "significant": mcnemar_exact_p(b, c) <= alpha},
        "p_disagree": round(p_disagree, 4),
        "ratio_c_over_b": ("inf" if math.isinf(ratio) else round(ratio, 3)),
        "power_at_n_obs": round(mcnemar_power(p_disagree, ratio, n_obs, alpha), 4),
        "scaled": {"b": b2, "c": c2, "n": int(n_target),
                   "p_exact": mcnemar_exact_p(b2, c2),
                   "significant": mcnemar_exact_p(b2, c2) <= alpha},
        "power_at_n_target": round(mcnemar_power(p_disagree, ratio, n_target, alpha), 4),
        "required_n_power80": required_n(p_disagree, ratio, 0.80, alpha),
        "required_n_power80_analytic": required_n_analytic(p_disagree, ratio, 0.80, alpha),
        "alpha": alpha,
        "note": ("olceklenmis p, 'ayni oruntu n_target'te birebir tekrarlanirsa' "
                 "senaryosudur; belirsizligi guc satirlari tasir"),
    }
