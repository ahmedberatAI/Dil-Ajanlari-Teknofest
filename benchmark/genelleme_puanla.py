#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ALAN DISI GENELLEME — G1/G2 olcutleri MEKANIK uygulanir.

ON KAYIT: docs/on_kayit_genelleme_2026-08-25.md
  G1 tehlike ayrimi : recall >= 0,70 VE normal FP <= 0,40 VE MCC >= +0,30
  G2 alan disi yanlis atesleme: ISG kurali atesleyen klip orani <= 0,25
  ON-RET: kosum butunlugu >= %90 · dejenerelik (>= %95 hep olay / hep sessiz)

Kume: data/isafety_bench (CC BY-NC-SA — YALNIZCA DEGERLENDIRME).
Alan uyarisi: dagitim alani sabit-kamera CCTV, bu set YouTube kaynakli.
Sonuc GENELLEME STRES TESTIDIR, ayni-alan kaniti DEGIL.

Kullanim:  python benchmark/genelleme_puanla.py [arsiv.json]
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from benchmark.yumusak_esik import mcc, _satirlari_al          # noqa: E402
from benchmark.stats_utils import wilson_ci                    # noqa: E402

G1_RECALL, G1_FP, G1_MCC = 0.70, 0.40, 0.30
G2_ATES = 0.25
ISG_KOD = {"Opened_Panel_Cover", "Carrying_Overload_with_Forklift",
           "Unauthorized_Intervention", "Safe_Walkway_Violation"}
ACIL = {"acil_durdurma_tetikle", "saglik_ekibi_yonlendir", "alan_guvenligini_sagla"}


def isg_olayi_var(r):
    """Tesise KALIBRE deterministik ISG kurallarindan biri atesledi mi?

    Kural olaylari SABLON metindir; karar izindeki `slot=[...]` notu yerine
    olay metnini kaliplarla eslemek yerine, sablonun ayirt edici basini
    kullaniriz (model nesri bu kaliplari uretmez).
    """
    BAS = ("Pano kapağı açık bırakılmış", "Forklift aşırı yük taşıyor",
           "Yetkisiz müdahale:", "Yaya yolu ihlali:")
    for e in (r.get("events") or []):
        m = e.get("event") or ""
        if any(m.startswith(b) for b in BAS):
            return True
    return False


def main():
    arsiv = sys.argv[1] if len(sys.argv) > 1 else sorted(
        glob.glob(os.path.join(KOK, "benchmark/results/eval_*.json")),
        key=os.path.getmtime)[-1]
    ham = json.load(open(arsiv, encoding="utf-8"))
    sat = _satirlari_al(ham)
    kn = ham.get("kosum") or {}
    print("arsiv: %s   klip: %d" % (os.path.basename(arsiv), len(sat)))
    print("yapilandirma: isg_slotlari=%s | facility_rules=%s | panel_roi=%s"
          % (kn.get("isg_slotlari"), kn.get("facility_rules_dolu"),
             kn.get("panel_roi_vlm")))

    teh = [r for p, r in sat.items() if "/Anomali/" in p.replace("\\", "/")]
    nrm = [r for p, r in sat.items() if "/Normal/" in p.replace("\\", "/")]
    n = len(teh) + len(nrm)

    print()
    print("### ON-RET KAPILARI")
    butun = n / 100.0
    print("  (a) kosum butunlugu : %d/100 = %.2f  -> %s"
          % (n, butun, "gecti" if butun >= 0.90 else "GECERSIZ"))
    olayli = sum(1 for r in teh + nrm if (r.get("n_events") or 0) > 0)
    o = olayli / float(n) if n else 0
    dej = o >= 0.95 or o <= 0.05
    print("  (b) dejenerelik     : olay ureten %d/%d = %.3f -> %s"
          % (olayli, n, o, "DEJENERE" if dej else "gecti"))
    if butun < 0.90 or dej:
        print("\n!! ON-RET: olcum gecersiz, sayi raporlanmaz")
        return 2

    # ---------- G1 ----------
    tp = sum(1 for r in teh if (r.get("n_events") or 0) > 0)
    fn = len(teh) - tp
    fp = sum(1 for r in nrm if (r.get("n_events") or 0) > 0)
    tn = len(nrm) - fp
    rec = tp / float(len(teh)) if teh else 0
    fpo = fp / float(len(nrm)) if nrm else 0
    m = mcc(tp, fp, fn, tn)
    rlo, rhi = wilson_ci(tp, len(teh))
    flo, fhi = wilson_ci(fp, len(nrm))
    print()
    print("### G1 — TEHLIKE AYRIMI")
    print("  TP%-4d FP%-4d FN%-4d TN%-4d" % (tp, fp, fn, tn))
    print("  %-22s %.3f  [%.3f-%.3f]  esik >= %.2f  %s"
          % ("tehlike recall", rec, rlo, rhi, G1_RECALL,
             "GECTI" if rec >= G1_RECALL else "KALDI"))
    print("  %-22s %.3f  [%.3f-%.3f]  esik <= %.2f  %s"
          % ("normal FP", fpo, flo, fhi, G1_FP,
             "GECTI" if fpo <= G1_FP else "KALDI"))
    print("  %-22s %+.3f%18s esik >= %.2f  %s"
          % ("MCC", m, "", G1_MCC, "GECTI" if m >= G1_MCC else "KALDI"))
    g1 = rec >= G1_RECALL and fpo <= G1_FP and m >= G1_MCC
    print("  -> G1 %s" % ("GECTI" if g1 else "KALDI"))

    # ---------- G2 ----------
    isg = sum(1 for r in teh + nrm if isg_olayi_var(r))
    io = isg / float(n)
    g2 = io <= G2_ATES
    print()
    print("### G2 — TESISE KALIBRE KURALLARIN ALAN DISI ATESLEMESI")
    print("  ISG kurali atesleyen klip: %d/%d = %.3f   esik <= %.2f  -> %s"
          % (isg, n, io, G2_ATES, "GECTI" if g2 else "KALDI"))
    if isg:
        say = collections.Counter()
        for r in teh + nrm:
            for e in (r.get("events") or []):
                mtn = e.get("event") or ""
                for b, ad in (("Pano kapağı", "pano"),
                              ("Forklift aşırı", "forklift"),
                              ("Yetkisiz müdahale", "yelek"),
                              ("Yaya yolu ihlali", "yaya")):
                    if mtn.startswith(b):
                        say[ad] += 1
        print("  hangi kural: %s" % dict(say.most_common()))
    if not g2:
        print("  !! ACIK RISK: gozlem duzlemi alan disinda GURULTU uretiyor")

    # ---------- ek okuma ----------
    print()
    print("### EK OKUMA (olcut degil)")
    for ad, kume in (("TEHLIKE", teh), ("NORMAL", nrm)):
        rk = collections.Counter(r.get("risk_level") for r in kume)
        ac = sum(1 for r in kume if set(r.get("triggered") or []) & ACIL)
        cm = sum(1 for r in kume if r.get("category_match"))
        print("  %-8s n=%-4d risk=%s" % (ad, len(kume), dict(rk)))
        print("           ACIL mudahale %d/%d = %.3f | category_match %d/%d = %.3f"
              % (ac, len(kume), ac / float(len(kume)),
                 cm, len(kume), cm / float(len(kume))))
    ler = sorted(r.get("latency_s") or 0 for r in teh + nrm)
    if ler:
        print("  gecikme medyan %.1f sn (min %.1f maks %.1f)"
              % (ler[len(ler) // 2], ler[0], ler[-1]))

    print()
    print("=" * 64)
    print("HUKUM: G1=%s  G2=%s" % ("GECTI" if g1 else "KALDI",
                                   "GECTI" if g2 else "KALDI"))
    print("ALAN UYARISI: bu set YouTube kaynakli; sonuc GENELLEME STRES")
    print("TESTIDIR, ayni-alan kaniti DEGIL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
