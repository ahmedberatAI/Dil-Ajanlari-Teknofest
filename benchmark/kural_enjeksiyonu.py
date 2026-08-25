#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tesis kurali enjeksiyonu kolu — DORT KAPI birden puanlanir.

ON KAYIT: docs/on_kayit_kural_enjeksiyonu_2026-08-25.md
  P  BIRINCIL : Safe_Walkway_Violation isg_match >= 0,50   (mevcut 0,000)
  A  CIFT     : yaya yolu cift dogrulugu >= 0,80           (cerceve tabani 0,729)
  B  BULASMA  : uc sevk kuralinin cift MCC'si 0,05'ten fazla DUSMEYECEK
  C  GURULTU  : normal kliplerde ACIL mudahale orani <= 0,15  (mevcut 0,082)
Dordu birden saglanmazsa RET.

Kalip listesi (`ISG_SINIFLAR`) DEGISTIRILMEZ — degistirilirse olcum gecersiz.

Kullanim:
    python benchmark/kural_enjeksiyonu.py <yeni_arsiv.json> [taban_arsiv.json]
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from benchmark.labels import ISG_SINIFLAR, isg_any_match          # noqa: E402
from benchmark.yumusak_esik import (                              # noqa: E402
    kol_puanla, _satirlari_al, CIFTLER,
)

TABAN_MCC = {
    "forklift": 0.881,
    "pano": 0.960,
    "yelek": 0.689,
}
ACIL = {"acil_durdurma_tetikle", "saglik_ekibi_yonlendir", "alan_guvenligini_sagla"}
YOL_IHL = "Safe_Walkway_Violation"
YOL_NRM = "Safe_Walkway"


def _yukle(yol):
    return _satirlari_al(json.load(open(yol, encoding="utf-8")))


def sinif_isg(sat):
    per = collections.defaultdict(lambda: [0, 0])
    for r in sat.values():
        s = r.get("isg_sinif")
        if not s:
            continue
        per[s][1] += 1
        if r.get("isg_match"):
            per[s][0] += 1
    return per


def yol_kalibi_esliyor(r):
    """Uretilen metin (olaylar + ozet) YAYA YOLU kaliplariyla esliyor mu?

    `eval_clips` ile AYNI kapsam: olay metinleri + summary.
    Kalip listesi DEGISTIRILMEZ.
    """
    parcalar = [e.get("event", "") for e in (r.get("events") or []) if e.get("event")]
    if r.get("summary"):
        parcalar.append(r["summary"])
    return bool(isg_any_match(parcalar, YOL_IHL))


def main():
    if len(sys.argv) > 1:
        yeni = sys.argv[1]
    else:
        d = sorted(glob.glob(os.path.join(KOK, "benchmark/results/eval_*.json")),
                   key=os.path.getmtime)
        yeni = d[-1]
    taban = sys.argv[2] if len(sys.argv) > 2 else \
        os.path.join(KOK, "benchmark/results/eval_20260825_114341.json")

    sat = _yukle(yeni)
    kunye = (json.load(open(yeni, encoding="utf-8")).get("kosum") or {})
    print("arsiv : " + os.path.basename(yeni) + "   satir: " + str(len(sat)))
    print("kunye : facility_rules_dolu=" + str(kunye.get("facility_rules_dolu"))
          + "  isg_slotlari=" + str(kunye.get("isg_slotlari")))
    if not kunye.get("facility_rules_dolu"):
        print("!! bu arsivde facility_rules KAPALI — yanlis dosya")
        return 2

    # ---------- P: BIRINCIL ----------
    per = sinif_isg(sat)
    per_t = sinif_isg(_yukle(taban)) if os.path.exists(taban) else {}
    print()
    print("=== SINIF SINIF isg_match ===")
    print("%-34s %10s %10s %8s" % ("sinif", "taban", "kural ACIK", "fark"))
    guvensiz_d = guvensiz_t = 0
    for s in sorted(per):
        d, t = per[s]
        td, tt = per_t.get(s, [0, 0])
        o_y = d / t if t else 0.0
        o_t = td / tt if tt else 0.0
        if ISG_SINIFLAR.get(s, {}).get("guvensiz"):
            guvensiz_d += d
            guvensiz_t += t
        print("%-34s %4d/%-3d %.3f %4d/%-3d %.3f %+8.3f"
              % (s, td, tt, o_t, d, t, o_y, o_y - o_t))
    print("%-34s %16s %10.3f"
          % ("(GUVENSIZ 4 SINIF = isg_match)", "",
             guvensiz_d / guvensiz_t if guvensiz_t else 0.0))

    p_deger = (per.get(YOL_IHL, [0, 1])[0] /
               float(per.get(YOL_IHL, [0, 1])[1] or 1))
    p_gecti = p_deger >= 0.50
    print()
    print("KAPI P (birincil): %s isg_match = %.3f   esik 0,50   -> %s"
          % (YOL_IHL, p_deger, "GECTI" if p_gecti else "KALDI"))

    # ---------- A: CIFT ----------
    tp = fn = fp = tn = 0
    for p, r in sat.items():
        y = "/" + p.replace("\\", "/")
        ihl = ("/" + YOL_IHL + "/") in y
        nrm = ("/" + YOL_NRM + "/") in y
        if not (ihl or nrm):
            continue
        m = yol_kalibi_esliyor(r)
        if ihl:
            tp, fn = (tp + 1, fn) if m else (tp, fn + 1)
        else:
            fp, tn = (fp + 1, tn) if m else (fp, tn + 1)
    n = tp + fn + fp + tn
    dog = (tp + tn) / float(n) if n else 0.0
    a_gecti = dog >= 0.80
    print("KAPI A (cift)    : TP%d FP%d FN%d TN%d  dogruluk %.3f  "
          "esik 0,80 (cerceve tabani 0,729) -> %s"
          % (tp, fp, fn, tn, dog, "GECTI" if a_gecti else "KALDI"))

    # ---------- B: BULASMA ----------
    print()
    print("KAPI B (bulasma) — sevk edilen uc cift")
    b_gecti = True
    for cift in CIFTLER:
        s = kol_puanla(sat, cift, "sert")
        t = TABAN_MCC[cift[0]]
        dus = t - s["mcc"]
        ok = dus <= 0.05
        b_gecti = b_gecti and ok
        print("   %-10s TP%-3d FP%-3d FN%-3d TN%-3d  %+0.3f  (taban %+0.3f, "
              "dusus %+0.3f)  %s"
              % (cift[0], s["tp"], s["fp"], s["fn"], s["tn"], s["mcc"], t, -dus,
                 "ok" if ok else "IHLAL"))
    print("   -> %s" % ("GECTI" if b_gecti else "KALDI"))

    # ---------- C: GURULTU ----------
    nrm_klip = [r for p, r in sat.items() if "/Normal/" in p.replace("\\", "/")]
    acil = sum(1 for r in nrm_klip if set(r.get("triggered") or []) & ACIL)
    olayli = sum(1 for r in nrm_klip if (r.get("n_events") or 0) > 0)
    oran = acil / float(len(nrm_klip)) if nrm_klip else 0.0
    c_gecti = oran <= 0.15
    print()
    print("KAPI C (gurultu) : normal klipte ACIL %d/%d = %.3f  esik 0,15 -> %s"
          % (acil, len(nrm_klip), oran, "GECTI" if c_gecti else "KALDI"))
    print("                   (bilgi) normal klipte OLAY ureten: %d/%d = %.3f"
          % (olayli, len(nrm_klip), olayli / float(len(nrm_klip) or 1)))

    # ---------- ON-RET (a) DEJENERELIK ----------
    hepsi_yuksek = all((per[s][0] / (per[s][1] or 1)) >= 0.90
                       for s in per if ISG_SINIFLAR.get(s, {}).get("guvensiz"))
    print()
    print("ON-RET (a) DEJENERELIK: dort guvensiz sinifin HEPSI >= 0,90 mi -> %s"
          % ("EVET -> RET" if hepsi_yuksek else "hayir, gecti"))

    # ---------- HUKUM ----------
    print()
    print("=" * 70)
    kapilar = {"P": p_gecti, "A": a_gecti, "B": b_gecti, "C": c_gecti}
    print("ON KAYITLI HUKUM: " + "  ".join(
        "%s=%s" % (k, "GECTI" if v else "KALDI") for k, v in kapilar.items()))
    if all(kapilar.values()) and not hepsi_yuksek:
        print("-> DORT KAPI DA GECTI. Kol SEVK EDILEBILIR.")
    else:
        print("-> RET (on kayit §3: dordu birden saglanmazsa RET).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
