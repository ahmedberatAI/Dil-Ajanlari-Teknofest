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

Birim testi:  python benchmark/test_stats_utils.py
"""
from __future__ import annotations

import math
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
