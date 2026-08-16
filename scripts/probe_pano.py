#!/usr/bin/env python
"""class2 (acik pano kapagi) TESHIS PROBU — ALGI SINIRI mi, IFADE eksikligi mi?

SORU
----
D33 olcumunde `class2` (Opened Panel Cover) DORT kosunun dordunde de sozcuksel
adlandirmada %0 aldi: model 100 pano klibinin HICBIRINDE "pano/panel/kapak"
kelimesini kullanmadi — tesis kuralinin 3. maddesi ACIKCA "pano kapaklari kapali
olmalidir" dedigi halde.

Iki farkli aciklama var ve BUNLARIN AYRIMI ONERIYI TAMAMEN DEGISTIRIR:

  (a) IFADE eksikligi : model panoyu GORUYOR ama kendiliginden SOYLEMIYOR
                        -> cozum UCUZ: sorgu/prompt (DILAJAN_ANALYSIS_QUERY)
  (b) ALGI SINIRI     : model acik/kapali pano kapagini AYIRT EDEMIYOR
                        -> cozum PAHALI: deterministik YOLO dogrulayici
                           (HANDOFF §6.2'nin KKD icin verdigi mimari kararin aynisi)

YONTEM
------
Ayni klipler DOGRUDAN SORU ile yeniden analiz edilir:
    "Elektrik panosunun kapağı açık mı kapalı mı?"
GUVENSIZ (class2, kapak ACIK) ve GUVENLI (class6, kapak KAPALI) kliplerden esit
sayida ornek alinir. Model ayirt edebiliyorsa (a), edemiyorsa (b).

⚠ Bu bir TESHIS probudur, A/B degil: n kucuk ve amac karar degil YON tayini.
Sonucu "kanit" diye raporlamayin; asil olcum icin tam kol kosulmalidir.

Kullanim:
    python scripts/probe_pano.py            # sinif basina 6 klip
    python scripts/probe_pano.py --n 10
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.agent import analyze_video  # noqa: E402
from dilajan.config import request_config  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SORU = "Elektrik panosunun veya kontrol panelinin kapağı açık mı, kapalı mı? Sadece bunu değerlendir."

#: (dizin, insan-okur ad, GERCEK durum)
KOLLAR = (
    (os.path.join(ROOT, "data", "eval_defense", "Anomali", "Opened_Panel_Cover"),
     "class2 KAPAK ACIK", "acik"),
    (os.path.join(ROOT, "data", "eval_defense", "Normal", "Closed_Panel_Cover"),
     "class6 KAPAK KAPALI", "kapali"),
)

#: Cevabin YONUNU okumak icin basit sozcuk kapilari (tr_lower sonrasi aranir).
ACIK_IZ = ("açık", "acik", "kapağı açık", "kapak açık", "açılmış")
KAPALI_IZ = ("kapalı", "kapali", "kapağı kapalı", "kapak kapalı")


def _yon(metin: str) -> str:
    """Cevap 'acik' mi 'kapali' mi diyor? Belirsizse '?'."""
    from benchmark.labels import tr_lower
    t = tr_lower(metin)
    a = any(x in t for x in ACIK_IZ)
    k = any(x in t for x in KAPALI_IZ)
    if a and not k:
        return "acik"
    if k and not a:
        return "kapali"
    if a and k:
        return "ikisi"
    return "?"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=6, help="sinif basina klip sayisi")
    args = ap.parse_args()

    print("=" * 92)
    print("class2 TESHIS PROBU — model DOGRUDAN SORULDUGUNDA panoyu ayirt ediyor mu?")
    print(f"SORU: {SORU}")
    print("=" * 92)

    dogru = toplam = 0
    for dizin, ad, gercek in KOLLAR:
        klipler = sorted(glob.glob(os.path.join(dizin, "*.mp4")))[:args.n]
        if not klipler:
            print(f"\n[ATLANDI] klip yok: {dizin}")
            continue
        print(f"\n--- {ad}  (gercek durum: {gercek.upper()}, n={len(klipler)}) ---")
        for yol in klipler:
            try:
                with request_config(analysis_query=SORU):
                    r = analyze_video(yol)
            except Exception as e:  # noqa: BLE001  (K3 fail-open)
                print(f"  [HATA] {os.path.basename(yol)}: {type(e).__name__}: {e}")
                continue
            cevap = getattr(r, "query_answer", None) or r.summary or ""
            y = _yon(cevap)
            toplam += 1
            if y == gercek:
                dogru += 1
            isaret = "✓" if y == gercek else ("·" if y in ("?", "ikisi") else "✗")
            print(f"  {isaret} [{y:6s}] {os.path.basename(yol):16s} {cevap[:120]}")

    print("\n" + "=" * 92)
    if toplam:
        print(f"DOGRUDAN SORULDUGUNDA: {dogru}/{toplam} klipte durum DOGRU okundu "
              f"(%{100.0 * dogru / toplam:.0f})")
        print("  ~%50 -> yazi-tura: ALGI SINIRI (b) -> deterministik dogrulayici gerekir")
        print("  belirgin >%50 -> IFADE eksikligi (a) -> sorgu/prompt ile cozulebilir")
    else:
        print("Hic klip islenemedi.")
    print("⚠ TESHIS probudur, kanit degil: n kucuk, karar icin tam kol kosulmali.")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
