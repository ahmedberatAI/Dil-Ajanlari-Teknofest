#!/usr/bin/env python
"""benchmark/stats_utils.py birim testleri (K15 dogrulamasi).

Bagimliligi YOK (GPU/vLLM/torch/pytest gerekmez) — dogrudan kosturulur:
    python benchmark/test_stats_utils.py     # cikis kodu 0 = hepsi gecti

Fonksiyonlar duz 'test_*' + assert oldugundan pytest KURULUYSA onunla da toplanabilir;
bu depoda pytest kurulu degildir, dogrulama yukaridaki dogrudan kosumla yapilir.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from benchmark.stats_utils import (  # noqa: E402
        Z95, fmt_pct, fmt_rate, mean_sd, pct_decimals, pseudo_replication_note,
        rate, rate_from_bools, wilson_ci,
    )
except ImportError:  # dogrudan benchmark/ icinden calistirilirsa
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from stats_utils import (  # noqa: E402
        Z95, fmt_pct, fmt_rate, mean_sd, pct_decimals, pseudo_replication_note,
        rate, rate_from_bools, wilson_ci,
    )


def _close(a: float, b: float, tol: float = 5e-4) -> bool:
    return abs(a - b) <= tol


def test_wilson_referans_degerler() -> None:
    """Gorevde verilen 3 referans deger (elle dogrulanmis Wilson score araligi)."""
    lo, hi = wilson_ci(17, 18)
    assert _close(lo, 0.742) and _close(hi, 0.990), f"17/18 -> ({lo:.4f}, {hi:.4f})"

    lo, hi = wilson_ci(18, 18)
    assert _close(lo, 0.824) and _close(hi, 1.000), f"18/18 -> ({lo:.4f}, {hi:.4f})"

    lo, hi = wilson_ci(0, 6)
    assert _close(lo, 0.000) and _close(hi, 0.390), f"0/6 -> ({lo:.4f}, {hi:.4f})"


def test_wilson_sinir_durumlari() -> None:
    # n=0: bilgi yok -> hicbir iddia yok
    assert wilson_ci(0, 0) == (0.0, 1.0)
    # aralik her zaman [0,1] icinde ve alt <= p <= ust
    for n in range(1, 40):
        for k in range(0, n + 1):
            lo, hi = wilson_ci(k, n)
            p = k / n
            assert 0.0 <= lo <= p <= hi <= 1.0, f"{k}/{n} -> ({lo}, {hi})"
    # k=n asla ust sinir 1.0'in uzerine cikmaz, k=0 asla alt sinir <0 olmaz
    assert wilson_ci(5, 5)[1] <= 1.0
    assert wilson_ci(0, 5)[0] >= 0.0
    # simetri: k/n ile (n-k)/n araliklari aynada
    lo1, hi1 = wilson_ci(3, 10)
    lo2, hi2 = wilson_ci(7, 10)
    assert _close(lo1, 1 - hi2) and _close(hi1, 1 - lo2)
    # n buyudukce aralik daralir
    assert (wilson_ci(50, 100)[1] - wilson_ci(50, 100)[0]) < (wilson_ci(5, 10)[1] - wilson_ci(5, 10)[0])


def test_wilson_gecersiz_girdi() -> None:
    for k, n in [(-1, 5), (6, 5)]:
        try:
            wilson_ci(k, n)
        except ValueError:
            continue
        raise AssertionError(f"gecersiz {k}/{n} icin ValueError bekleniyordu")


def test_rate_sozlugu() -> None:
    d = rate(0, 6)
    assert d["k"] == 0 and d["n"] == 6 and d["p"] == 0.0
    assert d["ci_method"] == "wilson" and d["ci_level"] == 0.95
    assert _close(d["ci_high"], 0.390)
    # "FP %0" iddiasinin gercekte %39'a kadar cikabildigi ACIKCA gorunur
    assert d["ci_high"] > 0.35

    d2 = rate_from_bools([True] * 17 + [False])
    assert d2["k"] == 17 and d2["n"] == 18
    assert _close(d2["ci_low"], 0.742)

    # n=0 -> iddia yok
    d3 = rate(0, 0)
    assert d3["n"] == 0 and d3["ci_low"] == 0.0 and d3["ci_high"] == 1.0


def test_ondalik_hijyeni() -> None:
    """n<=48 -> tam sayi yuzde ("%98.7" sahte kesinligi yasak)."""
    assert pct_decimals(18) == 0
    assert pct_decimals(48) == 0
    assert pct_decimals(49) == 1
    assert fmt_pct(0.9868, 48) == "%99"        # yuvarlanir, ondalik YOK
    assert fmt_pct(0.9868, 100) == "%98.7"     # buyuk n -> 1 ondalik mesru
    s = fmt_rate(0, 6)
    assert s.startswith("%0 [") and "39" in s and "(0/6)" in s, s
    assert fmt_rate(0, 0).startswith("n/a")


def test_pseudo_replikasyon_notu() -> None:
    note = pseudo_replication_note(30, 90)
    assert note and "PSEUDO-REPLIKASYON" in note and "30" in note and "90" in note
    assert pseudo_replication_note(30, 30) is None
    assert pseudo_replication_note(0, 0) is None


def test_mean_sd() -> None:
    m, sd, n = mean_sd([1, 2, 3, 4])
    assert _close(m, 2.5) and _close(sd, 1.2910) and n == 4
    assert mean_sd([]) == (None, 0.0, 0)
    assert mean_sd([5]) == (5.0, 0.0, 1)


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    print(f"stats_utils birim testleri (z95={Z95:.6f})")
    print("-" * 60)
    for t in tests:
        try:
            t()
            print(f"  [GECTI]  {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  [KALDI]  {t.__name__}: {e}")
    print("-" * 60)
    print(f"{len(tests) - failed}/{len(tests)} test gecti")
    # referans degerleri gorunur bicimde de yazdir
    for k, n in [(17, 18), (18, 18), (0, 6)]:
        lo, hi = wilson_ci(k, n)
        print(f"  wilson_ci({k:2d},{n:2d}) = [{lo:.4f}, {hi:.4f}]   ->  {fmt_rate(k, n)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
