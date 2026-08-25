#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Yaya yolu: DORT karar kurali, TEK kosumdan, ESLESMIS.

ON KAYIT: docs/on_kayit_yaya_zemin_2026-08-25.md
  BIRINCIL kol   : zemin (tek basina)
  IKINCIL kollar : mesafe · mesafe+kapi · zemin+kapi   -> Holm duzeltmesi
  KABUL          : cift ici MCC >= +0,45 VE saha kesinligi >= 0,237
  ON-RET         : dejenerelik (>= %90 ayni cevap) · bulasma · cerceveleme

Kosum, `yaya_zemin` ve `yaya_cizgi_mesafe` slotlarini AYNI oturumda doldurur.
Dolayisiyla dort kural AYNI ileri gecis kumesinden puanlanir: kollar arasi
fark modelden degil YALNIZCA karar kuralindan gelir. Yeni API cagrisi YOK.

Kullanim:
    python benchmark/yaya_kollari.py [benchmark/results/eval_*.json]
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from benchmark.yumusak_esik import (  # noqa: E402
    dagilimlari_oku, mcc, mcnemar, _argmaks, _p_esik_ustu, _satirlari_al,
)

IHLAL_DIZIN = "Anomali/Safe_Walkway_Violation"
NORMAL_DIZIN = "Normal/Safe_Walkway"
MESAFE_ESIK = 7          # deger < esik -> ihlal (AltEsikKurali)

# SEVK EDILEN UC MATRIS — bulasma kapisi bunlara bakar
SEVK_MATRIS = {
    "Carrying_Overload_with_Forklift": (24, 2, 1, 23),
    "Opened_Panel_Cover": (23, 0, 1, 25),
    "Unauthorized_Intervention": (19, 2, 6, 23),
}
SEVK_CIFT = {
    "Carrying_Overload_with_Forklift": ("Anomali/Carrying_Overload_with_Forklift",
                                        "Normal/Safe_Carrying",
                                        "catal_kasa_sayisi", 3, "ust"),
    "Opened_Panel_Cover": ("Anomali/Opened_Panel_Cover", "Normal/Closed_Panel_Cover",
                           "pano_koyuluk_0_10", 6, "ust"),
    "Unauthorized_Intervention": ("Anomali/Unauthorized_Intervention",
                                  "Normal/Authorized_Intervention",
                                  "makine_basinda_yelek", None, "etiket"),
}

KOLLAR = [
    ("zemin",          "yaya_zemin",         False, "BIRINCIL"),
    ("zemin+kapi",     "yaya_zemin",         True,  "ikincil"),
    ("mesafe",         "yaya_cizgi_mesafe",  False, "ikincil"),
    ("mesafe+kapi",    "yaya_cizgi_mesafe",  True,  "ikincil"),
]


def _kapi_acik(seg):
    """`on_azami=0`: makinenin basinda KIMSE YOKSA kural gecerli.

    Fail-closed: on slot olculemediyse kural SUSAR (iddia etme).
    """
    k = seg.get("makine_basinda_kisi")
    if not k:
        return False
    v = str(_argmaks(k) or "").rstrip("+")
    return v.isdigit() and int(v) == 0


def _ihlal_mi(seg, slot):
    d = seg.get(slot)
    if not d:
        return False
    v = _argmaks(d)
    if slot == "yaya_zemin":
        return v == "GRI_BETON"
    s = str(v or "").rstrip("+")
    return s.isdigit() and int(s) < MESAFE_ESIK        # AltEsikKurali


def atesledi(segler, slot, kapili):
    for seg in segler:
        if kapili and not _kapi_acik(seg):
            continue
        if _ihlal_mi(seg, slot):
            return True
    return False


def puanla(satirlar, slot, kapili):
    tp = fp = fn = tn = 0
    dogru = []
    for yol, r in sorted(satirlar.items()):
        y = "/" + yol.replace("\\", "/")
        poz = ("/" + IHLAL_DIZIN + "/") in y
        neg = ("/" + NORMAL_DIZIN + "/") in y
        if not (poz or neg):
            continue
        a = atesledi(dagilimlari_oku(r), slot, kapili)
        if poz:
            tp, fn = (tp + 1, fn) if a else (tp, fn + 1)
        else:
            fp, tn = (fp + 1, tn) if a else (fp, tn + 1)
        dogru.append(a == poz)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "mcc": mcc(tp, fp, fn, tn), "dogru": dogru}


def saha(satirlar, slot, kapili):
    ates = dogru_ates = 0
    capraz = collections.Counter()
    for yol, r in satirlar.items():
        y = "/" + yol.replace("\\", "/")
        if not atesledi(dagilimlari_oku(r), slot, kapili):
            continue
        ates += 1
        if ("/" + IHLAL_DIZIN + "/") in y:
            dogru_ates += 1
        else:
            capraz[os.path.basename(os.path.dirname(yol))] += 1
    return dogru_ates, ates, capraz


def sevk_matrisleri(satirlar):
    """Bulasma kapisi: sevk edilen uc matris DEGISTI mi?"""
    from benchmark.yumusak_esik import kol_puanla
    out = {}
    for kod, cift in SEVK_CIFT.items():
        s = kol_puanla(satirlar, (kod,) + cift[:2] + cift[2:], "sert")
        out[kod] = (s["tp"], s["fp"], s["fn"], s["tn"], s["mcc"])
    return out


def holm(pler):
    """Holm-Bonferroni: (ad, p) listesi -> (ad, p, duzeltilmis) sirali."""
    sirali = sorted(pler, key=lambda t: t[1])
    m = len(sirali)
    out, onceki = [], 0.0
    for i, (ad, p) in enumerate(sirali):
        d = min(1.0, max(onceki, (m - i) * p))
        onceki = d
        out.append((ad, p, d))
    return out


def main():
    desen = sys.argv[1] if len(sys.argv) > 1 else "benchmark/results/eval_*.json"
    dosyalar = sorted(glob.glob(os.path.join(KOK, desen)), key=os.path.getmtime)
    if not dosyalar:
        print("arsiv bulunamadi")
        return 1
    yol = dosyalar[-1]
    ham = json.load(open(yol, encoding="utf-8"))
    satirlar = _satirlari_al(ham)
    kunye = ham.get("kosum") or ham.get("kunye") or {}
    print("arsiv: " + os.path.relpath(yol, KOK) + "   satir: " + str(len(satirlar)))
    print("isg_slotlari: " + str(kunye.get("isg_slotlari")))
    if "yaya_zemin" not in str(kunye.get("isg_slotlari")):
        print("!! bu arsivde yaya_zemin YOK — yanlis dosya")
        return 2

    # ---------- ON-RET KAPISI (a): DEJENERELIK ----------
    print()
    print("=== ON-RET KAPISI (a): DEJENERELIK ===")
    for slot in ("yaya_zemin", "yaya_cizgi_mesafe"):
        say = collections.Counter()
        for r in satirlar.values():
            for seg in dagilimlari_oku(r):
                if slot in seg:
                    say[_argmaks(seg[slot])] += 1
        n = sum(say.values())
        if not n:
            print("  %-20s HIC SORULMAMIS" % slot)
            continue
        pay = max(say.values()) / float(n)
        print("  %-20s n=%-4d en sik %-18s %%%.1f  %s"
              % (slot, n, max(say, key=say.get), 100 * pay,
                 "DEJENERE -> RET" if pay >= 0.90 else "gecti"))
        print("       dagilim: " + str(dict(say.most_common(6))))

    # ---------- ON-RET KAPISI (c): BULASMA ----------
    print()
    print("=== ON-RET KAPISI (c): BULASMA (sevk edilen uc matris) ===")
    bulasma = False
    for kod, (tp, fp, fn, tn, m) in sevk_matrisleri(satirlar).items():
        bek = SEVK_MATRIS[kod]
        ok = (tp, fp, fn, tn) == bek
        bulasma = bulasma or not ok
        print("  %-32s TP%-3d FP%-3d FN%-3d TN%-3d %+0.3f   %s"
              % (kod, tp, fp, fn, tn, m,
                 "birebir" if ok else "SAPTI beklenen " + str(bek)))
    if bulasma:
        print("  !! BULASMA — kol degerlendirilmez, once sapmanin kaynagi bulunur")

    # ---------- KOLLAR ----------
    print()
    print("=== KOLLAR (cift ici + saha) ===")
    print("%-14s%-10s%4s%4s%4s%4s%9s%12s" %
          ("kol", "etiket", "TP", "FP", "FN", "TN", "MCC", "saha kes."))
    print("-" * 76)
    sonuc = {}
    for ad, slot, kapili, etiket in KOLLAR:
        s = puanla(satirlar, slot, kapili)
        d, a, capraz = saha(satirlar, slot, kapili)
        sk = (float(d) / a) if a else 0.0
        sonuc[ad] = (s, d, a, sk, capraz)
        gecti = (s["mcc"] >= 0.45) and (sk >= 0.237)
        print("%-14s%-10s%4d%4d%4d%4d%+9.3f%8.3f (%d/%d) %s"
              % (ad, etiket, s["tp"], s["fp"], s["fn"], s["tn"], s["mcc"],
                 sk, d, a, "<<< IKI KAPI DA GECTI" if gecti else ""))
        if capraz:
            print("%-24scapraz atesleme: %s" % ("", dict(capraz.most_common(4))))

    # ---------- ESLESMIS KARSILASTIRMA ----------
    print()
    print("=== ESLESMIS (McNemar exact) — taban: mesafe (9. kol) ===")
    taban = sonuc["mesafe"][0]["dogru"]
    pler = []
    for ad in ("zemin", "zemin+kapi", "mesafe+kapi"):
        mc = mcnemar(taban, sonuc[ad][0]["dogru"])
        pler.append((ad, mc["p"]))
        print("  %-14s duzeltti=%-3d bozdu=%-3d p=%.4f   dMCC=%+0.3f"
              % (ad, mc["duzeltti"], mc["bozdu"], mc["p"],
                 sonuc[ad][0]["mcc"] - taban_mcc(sonuc)))
    print()
    print("=== HOLM DUZELTMESI (ikincil kollar) ===")
    for ad, p, d in holm(pler):
        print("  %-14s ham p=%.4f  duzeltilmis p=%.4f  %s"
              % (ad, p, d, "anlamli" if d < 0.05 else "anlamli DEGIL"))

    # ---------- HUKUM ----------
    print()
    print("=== ON KAYITLI HUKUM ===")
    s, d, a, sk, _ = sonuc["zemin"]
    print("  BIRINCIL kol 'zemin':  MCC %+0.3f (esik +0,450)  |  "
          "saha kes. %.3f (esik 0,237)" % (s["mcc"], sk))
    if s["mcc"] >= 0.45 and sk >= 0.237:
        print("  -> IKI KAPI DA GECTI. isg_match kontrolu gerekli (>= 0,76).")
    else:
        print("  -> RET (on kayit §3).")
    return 0


def taban_mcc(sonuc):
    return sonuc["mesafe"][0]["mcc"]


if __name__ == "__main__":
    sys.exit(main())
