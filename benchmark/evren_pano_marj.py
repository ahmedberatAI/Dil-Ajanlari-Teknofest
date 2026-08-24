#!/usr/bin/env python
"""D42 — VLM SAYISAL KOL (H5) vs DETERMINISTIK PARLAKLIK DEDEKTORU: ADIL YUZLESME.

    python benchmark/evren_pano_marj.py

NEDEN BU BETIK VAR (kendi hatami duzeltiyorum)
----------------------------------------------
Ilk analizde "dedektor 29/34, VLM 34/34" yazdim. Bu DEDEKTORE HAKSIZDIR: 87,6 esigi
BASKA bir kumede kalibre edilmisti. Ayni SECIM kumesinde esik yeniden ayarlanirsa
dedektor de mukemmel ayrim yapabilir. Dogru soru "hangisi daha cok dogru bildi" degil,
**AYRIM MARJI NE KADAR GENIS** sorusudur — cunku pano kuralinin BILINEN kirilma
sebebi (docs/pano_dedektoru: MCC 0,845 -> 0,270 baska kamera gorusunde) tam olarak
DAR MARJDIR.

Bu betik ikisini de AYNI kurala tabi tutar:
  1. Esik SECIM (_tr) kumesinde secilir.
  2. Ayni esik TUTMA (_te) kumesine DEGISTIRILMEDEN uygulanir.
  3. Her ikisi icin AYRIM MARJI ve MUKEMMEL-AYRIM ESIK ARALIGI raporlanir.
"""
from __future__ import annotations

import glob
import io
import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
sys.path.insert(0, os.path.join(KOK, "benchmark"))

from evren_model_kars import mcc  # noqa: E402

SET = os.path.join(KOK, "data/eval_defense")
ROI = (0.08, 0.55, 0.21, 0.73)
ESIK_URETIM = 87.6


def roi_min_luma(yol):
    import numpy as np
    from PIL import Image
    from dilajan.video import extract_timestamped_frames
    fr, _ = extract_timestamped_frames(yol)
    lum = []
    for _t, j in fr:
        im = Image.open(io.BytesIO(j)).convert("L")
        w, h = im.size
        x1, y1, x2, y2 = ROI
        a = np.asarray(im, dtype=np.float32)[int(y1*h):int(y2*h), int(x1*w):int(x2*w)]
        lum.append(float(a.mean()) if a.size else 255.0)
    return min(lum) if lum else None


def klipler(kume):
    out = []
    for alt, ihlal in [("Anomali/Opened_Panel_Cover", True),
                       ("Normal/Closed_Panel_Cover", False)]:
        for y in sorted(glob.glob(os.path.join(SET, alt, "*.mp4"))):
            ad = os.path.basename(y)
            if ("_te" in ad) != (kume == "te"):
                continue
            out.append((ad, y, ihlal))
    return out


def vlm_cevaplari(kume):
    """En son JSONL'den H5 ham sayilarini oku (yeniden istek YOK)."""
    desen = os.path.join(KOK, f"benchmark/results/evren_pano_ozel_{kume}_2*.jsonl")
    yollar = sorted(glob.glob(desen))
    if not yollar:
        return {}
    out = {}
    for satir in open(yollar[-1], encoding="utf-8"):
        r = json.loads(satir)
        if r.get("tur") != "klip":
            continue
        c = r["cevap"].get("H5")
        if c is None or str(c).startswith("__"):
            continue
        try:
            out[r["klip"]] = int(str(c).strip())
        except ValueError:
            pass
    return out


def dogruluk(degerler, etiketler, esik, yon):
    """yon=-1: deger < esik -> POZITIF (karanlik=acik). yon=+1: deger >= esik -> POZITIF."""
    tp = fp = fn = tn = 0
    for v, e in zip(degerler, etiketler):
        poz = (v < esik) if yon < 0 else (v >= esik)
        if e and poz:
            tp += 1
        elif e:
            fn += 1
        elif poz:
            fp += 1
        else:
            tn += 1
    n = tp + fp + fn + tn
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "dogruluk": (tp + tn) / n if n else 0.0, "mcc": mcc(tp, fp, fn, tn)}


def marj(degerler, etiketler, yon):
    """Ayrim marji: pozitif ve negatif dagilimlar arasindaki bosluk (ortusme varsa negatif)."""
    poz = [v for v, e in zip(degerler, etiketler) if e]
    neg = [v for v, e in zip(degerler, etiketler) if not e]
    if not poz or not neg:
        return None
    if yon < 0:                      # dusuk deger = pozitif
        return min(neg) - max(poz), (max(poz), min(neg))
    return min(poz) - max(neg), (max(neg), min(poz))


def esik_araligi(degerler, etiketler, yon, adaylar):
    """Mukemmel (en yuksek) dogrulugu veren esiklerin araligi."""
    en = max(dogruluk(degerler, etiketler, e, yon)["dogruluk"] for e in adaylar)
    iyi = [e for e in adaylar
           if abs(dogruluk(degerler, etiketler, e, yon)["dogruluk"] - en) < 1e-9]
    return en, (min(iyi), max(iyi)), len(iyi)


def main():
    veri = {}
    for kume in ("tr", "te"):
        ks = klipler(kume)
        vlm = vlm_cevaplari(kume)
        satir = []
        for ad, yol, ihlal in ks:
            L = roi_min_luma(yol)
            satir.append({"klip": ad, "ihlal": ihlal, "luma": L, "vlm": vlm.get(ad)})
        veri[kume] = satir
        print(f"{kume}: n={len(satir)}  VLM cevabi olan={sum(1 for s in satir if s['vlm'] is not None)}")

    tr = veri["tr"]
    L_tr = [s["luma"] for s in tr]
    y_tr = [s["ihlal"] for s in tr]
    tr_v = [s for s in tr if s["vlm"] is not None]
    V_tr = [s["vlm"] for s in tr_v]
    yv_tr = [s["ihlal"] for s in tr_v]

    print(f"\n{'='*88}\n1) SECIM KUMESI (_tr) — DAGILIMLAR\n{'='*88}")
    for ad, vals, ys, yon in [("ROI min parlaklik", L_tr, y_tr, -1),
                              ("VLM sayisi (0-10)", V_tr, yv_tr, +1)]:
        poz = sorted(v for v, e in zip(vals, ys) if e)
        neg = sorted(v for v, e in zip(vals, ys) if not e)
        m, (a, b) = marj(vals, ys, yon)
        aralik = max(vals) - min(vals)
        print(f"\n  {ad}")
        print(f"    ACIK   (n={len(poz)}): {min(poz):.1f} .. {max(poz):.1f}")
        print(f"    KAPALI (n={len(neg)}): {min(neg):.1f} .. {max(neg):.1f}")
        print(f"    AYRIM MARJI = {m:.2f}  (sinir {a:.1f} | {b:.1f})   "
              f"olcek genisligi = {aralik:.1f}   BAGIL MARJ = {m/aralik*100:.1f}%")

    print(f"\n{'='*88}\n2) ESIK SECIMI — SADECE _tr UZERINDE\n{'='*88}")
    luma_adaylar = [round(x * 0.1, 1) for x in range(500, 1200)]
    en_l, (l_lo, l_hi), n_l = esik_araligi(L_tr, y_tr, -1, luma_adaylar)
    luma_esik = round((l_lo + l_hi) / 2, 1)
    print(f"  PARLAKLIK: en iyi tr dogrulugu {en_l:.3f}; bunu veren esik araligi "
          f"[{l_lo:.1f}, {l_hi:.1f}] genislik {l_hi-l_lo:.1f}  -> SECILEN esik {luma_esik}")
    vlm_adaylar = list(range(1, 11))
    en_v, (v_lo, v_hi), n_v = esik_araligi(V_tr, yv_tr, +1, vlm_adaylar)
    vlm_esik = 3
    print(f"  VLM:       en iyi tr dogrulugu {en_v:.3f}; bunu veren esik araligi "
          f"[{v_lo}, {v_hi}] ({n_v} tam sayi) -> ON-KAYITTA SECILEN esik {vlm_esik}")
    print(f"\n  URETIMDEKI MEVCUT esik {ESIK_URETIM} (BASKA kumede kalibre edilmisti): "
          f"tr dogrulugu {dogruluk(L_tr, y_tr, ESIK_URETIM, -1)['dogruluk']:.3f}")

    print(f"\n{'='*88}\n3) TUTMA KUMESI (_te) — ESIKLER DEGISTIRILMEDEN UYGULANDI\n{'='*88}")
    te = veri["te"]
    L_te = [s["luma"] for s in te]
    y_te = [s["ihlal"] for s in te]
    te_v = [s for s in te if s["vlm"] is not None]
    print(f"  te: n={len(te)} (ACIK={sum(y_te)} KAPALI={len(te)-sum(y_te)})  "
          f"-> UYARI: 3 pozitif KARAR VERDIRMEZ")
    for ad, r in [("parlaklik (tr esigi %.1f)" % luma_esik,
                   dogruluk(L_te, y_te, luma_esik, -1)),
                  ("parlaklik (uretim esigi %.1f)" % ESIK_URETIM,
                   dogruluk(L_te, y_te, ESIK_URETIM, -1))]:
        print(f"    {ad:34s} TP={r['tp']} FP={r['fp']} FN={r['fn']} TN={r['tn']}  "
              f"dogruluk={r['dogruluk']:.3f}  MCC={r['mcc']:+.3f}")
    if te_v:
        V_te = [s["vlm"] for s in te_v]
        yv_te = [s["ihlal"] for s in te_v]
        r = dogruluk(V_te, yv_te, vlm_esik, +1)
        print(f"    {'VLM sayisal (tr esigi %d)' % vlm_esik:34s} TP={r['tp']} FP={r['fp']} "
              f"FN={r['fn']} TN={r['tn']}  dogruluk={r['dogruluk']:.3f}  MCC={r['mcc']:+.3f}")
        m = marj(V_te, yv_te, +1)
        if m:
            print(f"    te VLM ayrim marji = {m[0]}  (sinir {m[1][0]} | {m[1][1]})")
    else:
        print("    VLM: te kosumu HENUZ YOK")
    ml = marj(L_te, y_te, -1)
    if ml:
        print(f"    te parlaklik ayrim marji = {ml[0]:.2f}  (sinir {ml[1][0]:.1f} | {ml[1][1]:.1f})")

    print(f"\n{'='*88}\n4) HER KLIP (te)\n{'='*88}")
    print(f"  {'klip':14s} {'gercek':7s} {'ROIluma':>8s} {'parl.karar':>11s} {'VLM':>4s} {'VLM karar':>10s}")
    for s in sorted(te, key=lambda s: (not s["ihlal"], s["klip"])):
        pk = "ACIK" if s["luma"] < luma_esik else "KAPALI"
        vk = "-" if s["vlm"] is None else ("ACIK" if s["vlm"] >= vlm_esik else "KAPALI")
        print(f"  {s['klip']:14s} {'ACIK' if s['ihlal'] else 'KAPALI':7s} {s['luma']:8.1f} "
              f"{pk:>11s} {str(s['vlm'] if s['vlm'] is not None else '-'):>4s} {vk:>10s}")

    json.dump(veri, open(os.path.join(KOK, "benchmark/results/evren_pano_marj.json"),
                         "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
