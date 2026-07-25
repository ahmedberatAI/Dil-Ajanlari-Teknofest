#!/usr/bin/env python
"""Coklu eval kosularini set-imzasina (n_anomali, n_normal) gore gruplayip her metrigin
ORTALAMA ± STD'sini raporlar. Amac: tek-kosu "cherry-pick %100" yerine durust varyans bandi.

K15 — RAPORLAMA HIJYENI (bu surumde eklendi):
  1) Her oran metrigi Wilson %95 guven araligi ile birlikte verilir. GA, TEK KOSUNUN klip
     sayisi uzerinden hesaplanir — kosu sayisiyla CARPILMAZ.
  2) PSEUDO-REPLIKASYON acikca etiketlenir: ayni klip setinde 3 kez kosmak 3 kat bagimsiz
     gozlem URETMEZ. "n_klip" (bagimsiz birim) ile "n_gozlem"/"n_altskor" AYRI alanlardir.
  3) Kalite skorlarinda (independent_scores.json) 30 klip x 3 eksen = 90 alt-skor
     "n=90" diye raporlanamaz; bagimsiz birim sayisi 30'dur.
  4) Ondalik disiplini: n<=48 iken yuzdeler TAM SAYI yazilir.

Kullanim:  python benchmark/aggregate.py
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from benchmark.stats_utils import (  # noqa: E402
        fmt_pct, fmt_rate, pseudo_replication_note, rate,
    )
except ImportError:  # benchmark/ icinden dogrudan calistirma
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from stats_utils import (  # type: ignore  # noqa: E402
        fmt_pct, fmt_rate, pseudo_replication_note, rate,
    )

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "benchmark", "results")

# set-imzasi -> okunabilir etiket (gerektiginde guncelle)
LABELS = {
    (24, 8): "UCF-Crime (grainy, dayanıklılık stresi)",
    (18, 12): "Senaryo (yangın+düşme+normal)",
    (10, 12): "Senaryo (yalnız yangın+normal)",
    (9, 6): "Gerçek düşme (GMDCSA-24)",
}

# (anahtar, etiket, hangi_payda)  payda: "anom" | "norm"
METRICS = [
    ("recall", "Anomali recall", "anom"),
    ("risk_cal_anom", "Risk kalib (≥Y)", "anom"),
    ("cat_match", "Kategori eşleşme", "anom"),
    ("normal_fp", "Normal FP (dar)", "norm"),
    ("normal_fp_operational", "Normal FP (operasyonel)", "norm"),
    ("normal_dispatch_fp", "Normal yanlış-tetik", "norm"),
]


def _load_runs():
    groups: dict = {}
    for f in sorted(glob.glob(os.path.join(RESULTS, "eval_*.json"))):
        try:
            doc = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        s = doc.get("summary", {})
        if not s:
            continue
        s["_file"] = os.path.basename(f)
        s["_dedup"] = doc.get("dedup", {})
        groups.setdefault((s.get("n_anomaly"), s.get("n_normal")), []).append(s)
    return groups


def _report_group(sig, runs) -> None:
    n_anom, n_norm = sig[0] or 0, sig[1] or 0
    n_klip = n_anom + n_norm
    n_kosu = len(runs)
    label = LABELS.get(sig, f"set n_anom={n_anom} n_norm={n_norm}")

    print(f"\n▌ {label}")
    print(f"    n_klip (BAĞIMSIZ birim) = {n_klip}   "
          f"n_koşu = {n_kosu}   n_gözlem (klip×koşu) = {n_klip * n_kosu}")
    note = pseudo_replication_note(n_klip, n_klip * n_kosu, unit="klip")
    if note:
        print(f"    ⚠ {note}")

    # dedup bilgisi (K10): paydanin mukerrer-arindirilmis olup olmadigi gorunsun
    ded = [r.get("_dedup") or {} for r in runs]
    n_skipped = max([d.get("n_skipped", 0) for d in ded] or [0])
    if any(d.get("enabled") is not None for d in ded):
        state = "AÇIK" if any(d.get("enabled") for d in ded) else "KAPALI"
        print(f"    MD5 mükerrer eleme: {state}"
              + (f" — {n_skipped} klip elendi (payda düzeltildi)" if n_skipped else ""))
    else:
        print("    MD5 mükerrer eleme: bilinmiyor (dedup öncesi koşu — payda şişmiş olabilir)")

    for key, name, denom_kind in METRICS:
        vals = [r[key] for r in runs if key in r and r[key] is not None]
        if not vals:
            continue
        n_metric = n_anom if denom_kind == "anom" else n_norm
        if n_metric == 0:
            # payda yok -> metrik TANIMSIZ. "%0" yazmak sahte bir basari/basarisizlik iddiasidir.
            print(f"    {name:24s}: TANIMSIZ (bu sette payda n=0)")
            continue
        m = statistics.mean(vals)
        sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        rng = (f" [koşu bandı {fmt_pct(min(vals), n_metric)}–{fmt_pct(max(vals), n_metric)}]"
               if len(vals) > 1 else "")
        # GA TEK kosunun klip sayisi uzerinden — kosu tekrari bagimsiz gozlem SAYILMAZ
        k = int(round(m * n_metric))
        ci = rate(k, n_metric)
        print(f"    {name:24s}: {fmt_pct(m, n_metric)} ± {fmt_pct(sd, n_metric)}"
              f"{rng}")
        print(f"    {'':24s}  Wilson %95 GA (n_klip={n_metric}): "
              f"[{fmt_pct(ci['ci_low'], n_metric)}–{fmt_pct(ci['ci_high'], n_metric)}]"
              f"   (≈{k}/{n_metric}, {n_kosu} koşu ort.)")


def _report_quality() -> None:
    """independent_scores.json — kalite skorlarinda n_klip / n_altskor AYRIMI."""
    path = os.path.join(RESULTS, "independent_scores.json")
    if not os.path.exists(path):
        return
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        return

    print("\n" + "=" * 78)
    print("KALİTE SKORLARI (LLM-hakem) — pseudo-replikasyon etiketli")
    print("=" * 78)
    print(f"  Hakem modeli: {d.get('judge_model', '?')}")
    for name, blk in d.items():
        if not isinstance(blk, dict) or "mean" not in blk:
            continue
        n_klip = blk.get("n_klip")
        n_alt = blk.get("n_altskor", blk.get("n"))
        n_eksen = blk.get("n_eksen")
        tur = blk.get("metrik_turu", "?")
        print(f"\n  ▸ {name}   [{tur}]")
        print(f"      ortalama = {blk['mean']} ± {blk.get('std', 0)}")
        if n_klip is not None:
            print(f"      n_klip (BAĞIMSIZ birim) = {n_klip}"
                  + (f"   n_eksen = {n_eksen}" if n_eksen else "")
                  + f"   n_altskor = {n_alt}")
            note = pseudo_replication_note(n_klip, n_alt or 0, unit="klip")
            if note:
                print(f"      ⚠ {note}")
        else:
            print(f"      n = {n_alt}  ⚠ n_klip alani yok — bu 'n' alt-skor sayisi olabilir "
                  f"(bağımsız gözlem sayısı DEĞİL).")


def main() -> None:
    groups = _load_runs()

    print("=" * 78)
    print("KONSOLİDE BENCHMARK — koşu-bazlı ortalama ± std + Wilson %95 GA")
    print("=" * 78)
    if not groups:
        print("benchmark/results/eval_*.json bulunamadi.")
    for sig, runs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        _report_group(sig, runs)

    _report_quality()

    print("\n" + "=" * 78)
    print("OKUMA KILAVUZU")
    print("  • Küçük setlerde (8–24 klip) tek koşu yanıltıcı; bant + std + GA esastır.")
    print("  • Aynı sette N koşu = N kat bağımsız gözlem DEĞİLDİR (pseudo-replikasyon);")
    print("    güven aralığı n_klip üzerinden okunur, n_klip×n_koşu üzerinden değil.")
    print("  • n≤48 iken yüzdeler tam sayı verilir; '%98.7' sahte kesinliktir.")
    print("=" * 78)


if __name__ == "__main__":
    main()
