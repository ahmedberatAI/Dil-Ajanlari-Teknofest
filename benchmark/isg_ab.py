#!/usr/bin/env python
"""ISG A/B karsilastirmasi — ON-KAYITLI esikleri MEKANIK uygular. GPU GEREKMEZ.

NEDEN BU DOSYA VAR
------------------
HANDOFF §7.4: "Ön-kayıtlı eşik. Koşudan ÖNCE 'hangi sonuç ne demek' yaz. Ama
MEKANIK UYGULAMA — D31'de red kriteri gürültüye takıldı, tekrar ölçümü kurtardı."

Esikleri koda gomup karari ARAC verdirmek, sonucu gordukten sonra esigi kaydirma
tuzagini kapatir. Esikler `docs/on_kayit_isg_2026-08-16.md`den gelir ve burada
BIR YERDE tanimlidir (ESIKLER sozlugu).

ESLESTIRME
----------
A ve B AYNI klipler uzerinde, tek degiskeni farkli iki kosudur -> EslESTIRILMIS.
Dogru test McNemar exact'tir (benchmark/stats_utils.mcnemar_test). Klipler
`path` alanina gore eslenir; eslenemeyen satirlar SESSIZCE ATILMAZ, raporlanir.

OLCULEN METRIKLER
-----------------
  recall              : klipte >=1 olay (anomali kliplerinde)
  cat_d28             : kayitli `category_match` (D28 olumsuzlama kapisi)
  cat_onarik          : ayni kural + ONARILMIS olumsuzlama kapisi (D33)
  isg_tam_dogru       : ISG sinifina ozgu tehlikeyi adlandirdi VE dogru yonlendirdi
  normal_temiz        : normal klipte HIC olay/tetik yok (yuksek = iyi)

Kullanim:
    python benchmark/isg_ab.py A.json B.json
    python benchmark/isg_ab.py A.json B.json --label-a varsayilan --label-b kurallar
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Callable, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from benchmark.isg_rescore import _satir_olc  # noqa: E402
    from benchmark.labels import any_match, isg_guvensiz, isg_sinif_from_path, row_text
    from benchmark.stats_utils import mcnemar_test  # noqa: E402
except ImportError:  # benchmark/ icinden dogrudan calistirma
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from isg_rescore import _satir_olc  # type: ignore  # noqa: E402
    from labels import (any_match, isg_guvensiz,  # type: ignore  # noqa: E402
                        isg_sinif_from_path, row_text)
    from stats_utils import mcnemar_test  # type: ignore  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# METRIK TANIMLARI — her biri (satir -> bool | None). None = bu klipte TANIMSIZ.
# ---------------------------------------------------------------------------
def _m_recall(r: dict) -> Optional[bool]:
    return (r.get("n_events", 0) > 0) if r.get("is_anomaly") else None


def _m_cat_d28(r: dict) -> Optional[bool]:
    if not r.get("is_anomaly"):
        return None
    v = r.get("category_match")
    return None if v is None else bool(v)


def _m_cat_onarik(r: dict) -> Optional[bool]:
    if not r.get("is_anomaly"):
        return None
    return any_match(row_text(r, with_summary=True), str(r.get("category") or ""),
                     mode="strict", onarik_olumsuzlama=True)


def _m_isg_tam(r: dict) -> Optional[bool]:
    sinif = isg_sinif_from_path(str(r.get("path") or ""))
    if not sinif or not isg_guvensiz(sinif):
        return None
    return bool(_satir_olc(r, sinif)["tam_dogru"])


def _m_normal_temiz(r: dict) -> Optional[bool]:
    """Normal klipte HIC olay ve HIC tetik yok -> True (YUKSEK = IYI yonune cevrildi)."""
    if r.get("is_anomaly"):
        return None
    return r.get("n_events", 0) == 0 and not r.get("triggered")


#: (anahtar, ekran adi, fonksiyon, on-kayitli esik puani veya None)
#: Esik = B-A farkinin ANLAMLI sayilmasi icin gereken EN AZ puan (yon: yuksek=iyi).
METRIKLER: Tuple[Tuple[str, str, Callable[[dict], Optional[bool]], Optional[int]], ...] = (
    ("recall", "Anomali recall (>=1 olay)", _m_recall, 15),
    ("cat_d28", "Kategori eslesme [D28 kapisi]", _m_cat_d28, None),
    ("cat_onarik", "Kategori eslesme [ONARIK kapi]", _m_cat_onarik, 12),
    ("isg_tam", "ISG TAM DOGRU (adlandir+yonlendir)", _m_isg_tam, None),
    ("normal_temiz", "Normal klip TEMIZ (olay/tetik yok)", _m_normal_temiz, None),
)

#: On-kayit (docs/on_kayit_isg_2026-08-16.md §3) — karar metinleri
ESIKLER: Dict[str, dict] = {
    "recall": {
        "hipotez": "H1", "esik_puan": 15, "alpha": 0.05,
        "gecerse": "26 Temmuz'daki +27 puan REPLIKE OLDU",
        "kalirsa": "26 Temmuz'daki +27 puan REPLIKE OLMADI",
    },
    "cat_onarik": {
        "hipotez": "H2", "esik_puan": 12, "alpha": 0.05,
        "gecerse": "kural enjeksiyonu adlandirmayi ARTIRIYOR",
        "kalirsa": "kazanc KANITLANAMAZ",
    },
    "normal_temiz": {
        "hipotez": "H3", "esik_puan": -15, "alpha": 0.05,
        "yon": "maliyet",
        "gecerse": "kural enjeksiyonunun BEDELI dogrulandi (normal kliplerde gurultu artti)",
        "kalirsa": "maliyet KANITLANAMADI",
    },
}


def esle(a_rows: List[dict], b_rows: List[dict]) -> Tuple[List[Tuple[dict, dict]], List[str]]:
    """Klipleri `path` alanina gore esler. Eslenemeyenler AYRICA dondurulur (K7)."""
    a_map = {str(r.get("path")): r for r in a_rows}
    b_map = {str(r.get("path")): r for r in b_rows}
    ortak = sorted(set(a_map) & set(b_map))
    tek_kalan = sorted((set(a_map) ^ set(b_map)))
    return [(a_map[p], b_map[p]) for p in ortak], tek_kalan


def _2x2(ciftler: List[Tuple[dict, dict]], fn) -> Tuple[int, int, int, int, int]:
    """(a, b, c, d, tanimsiz) — a: ikisi de dogru, b: yalniz A, c: yalniz B, d: ikisi de yanlis."""
    a = b = c = d = tanimsiz = 0
    for ra, rb in ciftler:
        va, vb = fn(ra), fn(rb)
        if va is None or vb is None:
            tanimsiz += 1
            continue
        if va and vb:
            a += 1
        elif va and not vb:
            b += 1
        elif not va and vb:
            c += 1
        else:
            d += 1
    return a, b, c, d, tanimsiz


def karsilastir(a_yol: str, b_yol: str, label_a: str, label_b: str,
                gurultu: bool = False) -> dict:
    """gurultu=True: iki kol AYNI yapilandirmadir (A vs A'). Bu durumda on-kayitli
    hipotez kararlari BASILMAZ — cunku onlar "mudahale etkili mi?" sorusunun
    cevabidir ve ayni yapilandirmada anlamsizdir. Bunun yerine olculen fark
    GURULTU TABANI olarak raporlanir (§7.1/§7.2).
    """
    with open(a_yol, encoding="utf-8") as f:
        A = json.load(f)
    with open(b_yol, encoding="utf-8") as f:
        B = json.load(f)
    ciftler, tek_kalan = esle(A.get("rows") or [], B.get("rows") or [])

    print("=" * 96)
    print("ISG GURULTU TABANI — AYNI yapilandirmanin iki kosusu (§7.1/§7.2)"
          if gurultu else "ISG A/B — ON-KAYITLI ESIKLER MEKANIK UYGULANIYOR")
    print(f"  A = {label_a:24s} {os.path.relpath(a_yol, ROOT)}")
    print(f"  B = {label_b:24s} {os.path.relpath(b_yol, ROOT)}")
    print(f"  eslenen klip: {len(ciftler)}"
          + (f"   ⚠ ESLENEMEYEN: {len(tek_kalan)} -> {tek_kalan[:3]}" if tek_kalan else ""))
    print("  Test: McNemar EXACT (esleştirilmiş — ayni klipler, tek degisken)")
    print("=" * 96)

    sonuclar: Dict[str, dict] = {}
    for anahtar, ad, fn, _esik in METRIKLER:
        a, b, c, d, tanimsiz = _2x2(ciftler, fn)
        n = a + b + c + d
        if n == 0:
            print(f"\n{ad}\n    (bu dosya ciftinde TANIMSIZ — atlandi)")
            continue
        t = mcnemar_test(a, b, c, d)
        pa = (a + b) / n
        pb = (a + c) / n
        fark = (pb - pa) * 100
        print(f"\n{ad}")
        print(f"    A={a + b}/{n} (%{pa * 100:.0f})   B={a + c}/{n} (%{pb * 100:.0f})   "
              f"fark = {fark:+.0f} puan")
        print(f"    uyusmayan cift: yalniz A dogru b={b} · yalniz B dogru c={c}   "
              f"(uyusan: a={a}, d={d})")
        print(f"    McNemar exact p = {t['p_exact']:.4f}   ({t['direction']})")
        print(f"    fark GA (Newcombe) = [{t['diff_ci_low'] * 100:+.0f}, "
              f"{t['diff_ci_high'] * 100:+.0f}] puan")

        kayit = {"a": a, "b": b, "c": c, "d": d, "n": n, "tanimsiz": tanimsiz,
                 "oran_a": pa, "oran_b": pb, "fark_puan": fark,
                 "p_exact": t["p_exact"], "anlamli": t["significant"],
                 "fark_ga": [t["diff_ci_low"], t["diff_ci_high"]]}

        # --- GURULTU KIPI: hipotez karari YOK, gurultu tabani raporlanir ---
        if gurultu:
            # round(): fark ikili kayan noktada 26.999999999999996 gibi cikabiliyor;
            # bu bir RAPOR alanidir, kayan nokta artigi tasimamali.
            kayit["gurultu_puan"] = round(abs(fark), 1)
            kayit["gurultu_cevirme"] = b + c
            print(f"    >>> GURULTU TABANI: |fark| = {abs(fark):.0f} puan   "
                  f"(klip-duzeyi cevirme: {b + c})")
            sonuclar[anahtar] = kayit
            continue

        # --- ON-KAYITLI KARAR (mekanik) ---
        ok = ESIKLER.get(anahtar)
        if ok:
            esik = ok["esik_puan"]
            anlamli = t["p_exact"] <= ok["alpha"]
            if ok.get("yon") == "maliyet":
                gecti = (fark <= esik) and anlamli
                kosul = f"fark <= {esik} puan VE p <= {ok['alpha']}"
            else:
                gecti = (fark >= esik) and anlamli
                kosul = f"fark >= +{esik} puan VE p <= {ok['alpha']}"
            karar = ok["gecerse"] if gecti else ok["kalirsa"]
            print(f"    >>> {ok['hipotez']} on-kayitli kosul: {kosul}")
            print(f"    >>> KARAR: {'GECTI' if gecti else 'GECEMEDI'} — {karar}")
            kayit.update({"hipotez": ok["hipotez"], "esik": esik,
                          "gecti": gecti, "karar": karar})
        sonuclar[anahtar] = kayit

    print("\n" + "=" * 96)
    if gurultu:
        print("OKUMA: buradaki farklar MUDAHALE DEGIL, yalnizca calisma-arasi degiskenliktir")
        print("       (temperature=0 olmasina ragmen vLLM toplu-islem belirsizligi).")
        print("       Bir A/B kazanci, ILGILI METRIGIN bu tabanindan BUYUK olmalidir.")
    else:
        print("NOT (§7.2): bu TEK kosu ciftidir. Asil iddialar icin ayni yapilandirmanin")
        print("            TEKRAR kosusu (A') gerekir — `--gurultu` ile koşun.")
    print("=" * 96)
    return {"a": os.path.relpath(a_yol, ROOT), "b": os.path.relpath(b_yol, ROOT),
            "label_a": label_a, "label_b": label_b, "n_cift": len(ciftler),
            "gurultu_kipi": gurultu,
            "eslenemeyen": tek_kalan, "metrikler": sonuclar}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", help="A kosusu (taban) JSON")
    ap.add_argument("b", help="B kosusu (mudahale) JSON")
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--label-b", default="B")
    ap.add_argument("--gurultu", action="store_true",
                    help="iki kol AYNI yapilandirma (A vs A'): hipotez karari basma, "
                         "GURULTU TABANI raporla")
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args(argv)

    for y in (args.a, args.b):
        if not os.path.exists(y):
            print(f"[HATA] bulunamadi: {y}")
            return 1
    s = karsilastir(args.a, args.b, args.label_a, args.label_b, gurultu=args.gurultu)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
        print(f"Kaydedildi: {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
