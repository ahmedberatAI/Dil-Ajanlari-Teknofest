#!/usr/bin/env python
"""KOL KOL kosulmus eval sonuclarini TEK sonuc dosyasinda birlestirir. GPU GEREKMEZ.

NEDEN BU DOSYA VAR (HANDOFF §9 "Tuzaklar")
-------------------------------------------
Makine bir kez cokmustu (Kernel-Power 41) — ~23 dk kesintisiz GPU yukunun ardindan.
O yuzden uzun olcumler KOL KOL kosuluyor, arada sogutma birakiliyor:

    EVAL_CATS=Anomali python benchmark/eval_clips.py     # kol 1
    <soguma>
    EVAL_CATS=Normal  python benchmark/eval_clips.py     # kol 2

Ama `eval_clips.py` her kol icin AYRI bir ozet uretir: kol 1'de `normal_fp`
paydasi 0, kol 2'de `recall` paydasi 0. Butun sette anlamli olan tek sayi
ikisinin BIRLESIMIDIR. Bu arac satirlari birlestirir ve ozeti
`eval_clips.py` ILE AYNI FORMULLERLE yeniden hesaplar.

DOGRULUK GARANTISI — YUVARLAK YOLCULUK TESTI
--------------------------------------------
Formulleri kopyalamak "iki kaynak-dogru" riski dogurur: eval_clips.py degisir,
burasi degismez ve sayilar SESSIZCE ayrisir. Buna karsi tests/test_merge_arms.py
BUTUN bir n=200 kosusunu Anomali/Normal diye ikiye BOLER, bu araca verir ve
uretilen ozetin ORIJINAL dosyanin ozetiyle BIREBIR ayni oldugunu dogrular.
Formuller ayrisirsa test kirmizi yanar.

MUKERRER ELEME (K10) UYARISI
----------------------------
`eval_clips.py` MD5 mukerrer elemesini KOL ICINDE yapar; kollar arasi mukerrer
kacabilir. Bu arac birlesik sette MD5 DEGIL yol tekrarini denetler ve ayni yol
iki kolda da varsa UYARIR (sessizce cift saymaz).

Kullanim:
    python benchmark/merge_arms.py kol1.json kol2.json -o birlesik.json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from benchmark.stats_utils import fmt_rate_dict, rate_from_bools  # noqa: E402
except ImportError:  # benchmark/ icinden dogrudan calistirma
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from stats_utils import fmt_rate_dict, rate_from_bools  # type: ignore  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ozet_hesapla(rows: List[dict]) -> dict:
    """`eval_clips.py:main()` ile AYNI formuller. Alan adlari da AYNI olmali.

    Bu fonksiyonun eval_clips.py ile ozdes kaldigi tests/test_merge_arms.py'de
    GERCEK bir arsiv dosyasi uzerinde yuvarlak-yolculukla dogrulanir.
    """
    anom = [r for r in rows if r.get("is_anomaly")]
    norm = [r for r in rows if not r.get("is_anomaly")]

    def _d28_alani(ad: str):
        """D28 ONCESI arsivlerde bu alan HIC YOKTUR. Yoklugu 0.0 diye raporlamak
        YANLISTIR ("olculdu ve sifir cikti" der). Alan hicbir anomali satirinda
        yoksa None doner — eval_clips.py'nin tanimsiz eslesme icin kullandigi
        isaretin aynisi.
        """
        if not any(ad in r for r in anom):
            return None
        return rate_from_bools([bool(r.get(ad)) for r in anom])

    R = {
        "recall": rate_from_bools([r["n_events"] > 0 for r in anom]),
        "risk_cal_anom": rate_from_bools([r["risk_ord"] >= 3 for r in anom]),
        "cat_match": rate_from_bools([bool(r["category_match"]) for r in anom]),
        "cat_match_eski": _d28_alani("category_match_eski"),
        "cat_match_grup": _d28_alani("category_match_grup"),
        "normal_fp": rate_from_bools(
            [(r["max_severity"] >= 3 or r["risk_ord"] >= 3) for r in norm]),
        "normal_fp_operational": rate_from_bools(
            [(r["n_events"] > 0 or len(r.get("triggered", [])) > 0) for r in norm]),
        "normal_dispatch_fp": rate_from_bools([len(r.get("triggered", [])) > 0 for r in norm]),
        "risk_cal_norm": rate_from_bools([r["risk_ord"] <= 1 for r in norm]),
    }
    lat = [r["latency_s"] for r in rows]

    # per-kategori (eval_clips.py ile ayni: CATEGORY_EXPECT sirasinda gezer)
    try:
        from benchmark.labels import CATEGORY_EXPECT
    except ImportError:  # pragma: no cover
        from labels import CATEGORY_EXPECT  # type: ignore
    per_category: Dict[str, dict] = {}
    for cat in CATEGORY_EXPECT:
        cr = [r for r in rows if r.get("category") == cat]
        if not cr:
            continue
        per_category[cat] = {
            "recall": rate_from_bools([r["n_events"] > 0 for r in cr]),
            "cat_match": rate_from_bools(
                [bool(r["category_match"]) for r in cr if r.get("is_anomaly")]),
        }

    kurallar = {r.get("category_match_kural") for r in rows if r.get("category_match_kural")}
    return {
        "n_anomaly": len(anom), "n_normal": len(norm),
        "recall": R["recall"]["p"], "risk_cal_anom": R["risk_cal_anom"]["p"],
        "cat_match": R["cat_match"]["p"],
        # D28 ONCESI arsivde alan YOKSA duz oran da None kalir (0.0 DEGIL).
        "cat_match_eski": (R["cat_match_eski"] or {}).get("p"),
        "cat_match_grup": (R["cat_match_grup"] or {}).get("p"),
        "cat_match_kural": (kurallar.pop() if len(kurallar) == 1 else sorted(kurallar)),
        "normal_fp": R["normal_fp"]["p"],
        "normal_fp_operational": R["normal_fp_operational"]["p"],
        "normal_dispatch_fp": R["normal_dispatch_fp"]["p"],
        "risk_cal_norm": R["risk_cal_norm"]["p"],
        "latency_median": statistics.median(lat) if lat else 0,
        "ci": R, "ci_method": "wilson", "ci_level": 0.95,
        "per_category_ci": per_category,
    }


def birlestir(yollar: List[str]) -> dict:
    """Kol dosyalarini okur, satirlari birlestirir, ozeti yeniden hesaplar."""
    rows: List[dict] = []
    kaynaklar: List[dict] = []
    eval_dirs = set()
    for yol in yollar:
        with open(yol, encoding="utf-8") as f:
            d = json.load(f)
        r = d.get("rows") or []
        rows.extend(r)
        eval_dirs.add(str(d.get("eval_dir") or "?"))
        kaynaklar.append({
            "dosya": os.path.relpath(yol, ROOT).replace("\\", "/"),
            "n_satir": len(r),
            "kategoriler": sorted({str(x.get("category")) for x in r}),
            "dedup": d.get("dedup"),
        })

    # Kollar arasi AYNI YOL iki kez sayildi mi? (K10'un kol-arasi bosluğu)
    yol_say: Dict[str, int] = {}
    for r in rows:
        p = str(r.get("path") or "")
        yol_say[p] = yol_say.get(p, 0) + 1
    tekrar = sorted(p for p, n in yol_say.items() if n > 1)

    if len(eval_dirs) > 1:
        print(f"⚠ UYARI: kollar FARKLI setlerden geliyor: {sorted(eval_dirs)}")
    if tekrar:
        print(f"⚠ UYARI (K10): {len(tekrar)} klip birden cok kolda var — CIFT SAYIM riski:")
        for p in tekrar[:10]:
            print(f"    - {p}")

    return {
        "summary": ozet_hesapla(rows),
        "eval_dir": sorted(eval_dirs)[0] if len(eval_dirs) == 1 else sorted(eval_dirs),
        "birlesim": {
            "aciklama": ("KOL KOL kosulup birlestirildi (HANDOFF §9 termal onlemi). "
                         "Ozet benchmark/merge_arms.py ile eval_clips.py'nin AYNI "
                         "formulleriyle yeniden hesaplandi."),
            "kaynaklar": kaynaklar,
            "n_toplam": len(rows),
            "kollar_arasi_tekrar": tekrar,
        },
        "rows": rows,
    }


def bas(birlesik: dict) -> None:
    s = birlesik["summary"]
    R = s["ci"]
    print("=" * 72)
    print(f"BIRLESIK  ·  set: {birlesik['eval_dir']}  ·  toplam satir: "
          f"{birlesik['birlesim']['n_toplam']}")
    for k in birlesik["birlesim"]["kaynaklar"]:
        print(f"    kol: {k['dosya']}  n={k['n_satir']}  {k['kategoriler']}")
    print("-" * 72)
    print(f"Anomali klipleri: {s['n_anomaly']}   Normal klipleri: {s['n_normal']}")
    print("Tum oranlar: nokta-deger [Wilson %95 GA]  (k/n)")
    print("-" * 72)
    print(f"  Anomali RECALL (>=1 olay)      : {fmt_rate_dict(R['recall'])}")
    print(f"  Anomali risk kalibrasyonu(>=Y) : {fmt_rate_dict(R['risk_cal_anom'])}")
    print(f"  Kategori eslesme [ESKI kural]  : {fmt_rate_dict(R['cat_match_eski'])}")
    print(f"  Kategori eslesme [YENI kural]  : {fmt_rate_dict(R['cat_match'])}")
    print(f"  Kategori eslesme [GRUP duzeyi] : {fmt_rate_dict(R['cat_match_grup'])}")
    print(f"  NORMAL FP (dar: sev/risk>=Y)   : {fmt_rate_dict(R['normal_fp'])}   (dusuk = iyi)")
    print(f"  NORMAL FP (operasyonel)        : {fmt_rate_dict(R['normal_fp_operational'])}")
    print(f"  NORMAL yanlis operasyonel-tetik: {fmt_rate_dict(R['normal_dispatch_fp'])}")
    print(f"  Normal risk=Dusuk orani        : {fmt_rate_dict(R['risk_cal_norm'])}")
    print(f"  Gecikme medyan                 : {s['latency_median']:.1f}s")
    print("=" * 72)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dosyalar", nargs="+", help="kol sonuc JSON dosyalari")
    ap.add_argument("-o", "--out", required=True, help="birlesik cikti JSON yolu")
    args = ap.parse_args(argv)

    eksik = [y for y in args.dosyalar if not os.path.exists(y)]
    if eksik:
        print(f"[HATA] bulunamadi: {eksik}")
        return 1

    birlesik = birlestir(args.dosyalar)
    bas(birlesik)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(birlesik, f, ensure_ascii=False, indent=2)
    print(f"\nKaydedildi: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
