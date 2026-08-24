#!/usr/bin/env python
"""D42 EK ANALIZ — evren_pano_ozel.py JSONL ciktisini MODEL CAGIRMADAN yeniden yorumlar.

    python benchmark/evren_pano_ozel_analiz.py benchmark/results/evren_pano_ozel_tr_*.jsonl

UC SORUYA CEVAP VERIR (hicbiri ek istek gerektirmez):

  A) KACIS ANALIZI — her hucrede kacis ("GORUNMUYOR"/"HICBIRI") orani, GERCEK ETIKETE
     gore ayrilmis. Kacis SINIF-KORELE ise, kacis rastgele bir "bilmiyorum" degil
     GIZLI BIR KARARDIR ve ana tablodan dusurulmesi bilgi KAYBEDER.

  B) SAYISAL KOL vs DETERMINISTIK DEDEKTOR — H5'in verdigi 0-10 sayisi, bizim
     dedektorumuzun olctugu ROI MINIMUM PARLAKLIGI ile ne kadar ortusuyor?
     Yuksek (ters) korelasyon => VLM dedektoru YENIDEN TURETIYOR, uzerine bilgi
     EKLEMIYOR. Bu, "VLM'i mi dedektoru mu kullanalim" karari icin BELIRLEYICIDIR.

  C) ESLI KARSILASTIRMA — hucreler arasi McNemar (ayni klipler, ayni etiketler).
     Ozellikle H2 (ikili) vs H5 (sayisal): AYNI OTURUM, AYNI VIDEO, farkli SORU.
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
sys.path.insert(0, os.path.join(KOK, "benchmark"))

from evren_model_kars import mcc, tablo  # noqa: E402

KACIS = {"GORUNMUYOR", "HICBIRI", ""}


def oku(yol):
    kunye, klipler, ozet = None, [], None
    for satir in open(yol, encoding="utf-8"):
        r = json.loads(satir)
        if r.get("tur") == "kunye":
            kunye = r
        elif r.get("tur") == "klip":
            klipler.append(r)
        elif r.get("tur") == "ozet":
            ozet = r
    return kunye, klipler, ozet


# ------------------------------------------------------------------ A) kacis
def kacis_analizi(klipler, kodlar):
    print(f"\n{'='*92}\nA) KACIS ANALIZI — kacis orani GERCEK ETIKETE gore\n{'='*92}")
    print(f"{'hucre':6s} {'ACIK klip kacis':>18s} {'KAPALI klip kacis':>19s} {'fark':>8s}  yorum")
    print("-" * 92)
    for kod in kodlar:
        a = [r for r in klipler if r["ihlal"]]
        k = [r for r in klipler if not r["ihlal"]]
        def oran(grup):
            g = [r for r in grup if kod in r["cevap"]
                 and not str(r["cevap"][kod]).startswith("__")]
            if not g:
                return None, 0, 0
            n = sum(1 for r in g if str(r["cevap"][kod]).strip().upper() in KACIS)
            return n / len(g), n, len(g)
        oa, na, da = oran(a)
        ok, nk, dk = oran(k)
        if oa is None or ok is None:
            continue
        fark = oa - ok
        yorum = ("KACIS SINIF-KORELE (gizli karar)" if abs(fark) >= 0.20
                 else "kacis siniftan bagimsiz")
        print(f"{kod:6s} {na:5d}/{da:<3d} = {oa:6.2f}   {nk:5d}/{dk:<3d} = {ok:6.2f}  "
              f"{fark:+8.2f}  {yorum}")


# ------------------------------------- B) sayisal kol vs deterministik dedektor
def roi_min_luma(klip_adlari, set_kok, roi):
    """Uretim kod yoluyla ROI minimum ortalama parlakligi (dedektorun olctugu skaler)."""
    import io
    import numpy as np
    from PIL import Image
    from dilajan.video import extract_timestamped_frames

    out = {}
    for ad, yol in klip_adlari.items():
        try:
            fr, _ = extract_timestamped_frames(yol)
            lum = []
            for _t, j in fr:
                im = Image.open(io.BytesIO(j)).convert("L")
                w, h = im.size
                x1, y1, x2, y2 = roi
                a = np.asarray(im, dtype=np.float32)[int(y1*h):int(y2*h),
                                                     int(x1*w):int(x2*w)]
                lum.append(float(a.mean()) if a.size else 255.0)
            out[ad] = min(lum) if lum else None
        except Exception as e:
            print(f"  [luma HATA] {ad}: {e}")
            out[ad] = None
    return out


def spearman(x, y):
    n = len(x)
    if n < 3:
        return float("nan")
    def sira(v):
        s = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[s[j+1]] == v[s[i]]:
                j += 1
            ort = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[s[k]] = ort
            i = j + 1
        return r
    rx, ry = sira(x), sira(y)
    mx, my = sum(rx)/n, sum(ry)/n
    num = sum((a-mx)*(b-my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a-mx)**2 for a in rx) * sum((b-my)**2 for b in ry))
    return num/den if den else float("nan")


def sayisal_vs_dedektor(klipler, set_kok, roi, esik_luma=87.6):
    print(f"\n{'='*92}\nB) H5 (VLM sayisal 0-10) vs DETERMINISTIK DEDEKTOR (ROI min parlaklik)\n{'='*92}")
    adlar = {}
    for r in klipler:
        c = r["cevap"].get("H5")
        if c is None or str(c).startswith("__"):
            continue
        alt = "Anomali/Opened_Panel_Cover" if r["ihlal"] else "Normal/Closed_Panel_Cover"
        adlar[r["klip"]] = os.path.join(set_kok, alt, r["klip"])
    if not adlar:
        print("  H5 kaydi yok — atlandi.")
        return
    print(f"  {len(adlar)} klip icin ROI min parlaklik hesaplaniyor (uretim kod yolu)...")
    luma = roi_min_luma(adlar, set_kok, roi)

    xs, ys, satir = [], [], []
    for r in klipler:
        c = r["cevap"].get("H5")
        if c is None or str(c).startswith("__"):
            continue
        cs = str(c).strip().upper()
        if cs in KACIS:
            continue
        try:
            n = int(cs)
        except ValueError:
            continue
        L = luma.get(r["klip"])
        if L is None:
            continue
        xs.append(n); ys.append(L)
        satir.append((r["klip"], r["ihlal"], n, L))
    rho = spearman(xs, ys)
    print(f"\n  Spearman(VLM sayisi , ROI min parlaklik) = {rho:+.3f}   (n={len(xs)})")
    print("  BEKLENTI: karanlik = yuksek sayi => NEGATIF korelasyon. |rho| >= 0,70 ise")
    print("  VLM dedektorle AYNI SKALERI olcuyor demektir (uzerine bilgi eklemiyor).")

    # dedektorun kendi kararlariyla ANLASMA
    print(f"\n  {'klip':14s} {'gercek':7s} {'VLM':>4s} {'ROIluma':>8s} {'dedektor':>9s}")
    print("  " + "-" * 50)
    ded_dogru = vlm_dogru = 0
    for ad, ihlal, n, L in sorted(satir, key=lambda t: (not t[1], t[0])):
        ded = L < esik_luma
        print(f"  {ad:14s} {'ACIK' if ihlal else 'KAPALI':7s} {n:4d} {L:8.1f} "
              f"{'ACIK' if ded else 'KAPALI':>9s}")
        ded_dogru += (ded == ihlal)
        vlm_dogru += 0
    print(f"\n  deterministik dedektor (yalniz parlaklik, esik {esik_luma}): "
          f"{ded_dogru}/{len(satir)} = {ded_dogru/len(satir):.3f} dogruluk")


# ------------------------------------------------------------- C) esli McNemar
def mcnemar(klipler, kod_a, kod_b, yorumlar):
    a_dogru = b_dogru = 0
    ab = ba = 0
    for r in klipler:
        ca, cb = r["cevap"].get(kod_a), r["cevap"].get(kod_b)
        if ca is None or cb is None or str(ca).startswith("__") or str(cb).startswith("__"):
            continue
        ka, kb = yorumlar[kod_a](ca), yorumlar[kod_b](cb)
        if ka is None or kb is None:
            continue
        da, db = (ka == r["ihlal"]), (kb == r["ihlal"])
        a_dogru += da; b_dogru += db
        if da and not db:
            ab += 1
        elif db and not da:
            ba += 1
    n = ab + ba
    if n == 0:
        return None
    p = sum(math.comb(n, k) for k in range(0, min(ab, ba) + 1)) / (2 ** n) * 2
    return {"a_dogru": a_dogru, "b_dogru": b_dogru, "a_kazandi": ab,
            "b_kazandi": ba, "p": min(1.0, p)}


def main():
    desen = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        KOK, "benchmark/results/evren_pano_ozel_tr_2*.jsonl")
    yollar = sorted(glob.glob(desen))
    if not yollar:
        print(f"JSONL bulunamadi: {desen}")
        return 2
    yol = yollar[-1]
    print(f"kaynak: {os.path.relpath(yol, KOK)}")
    kunye, klipler, ozet = oku(yol)
    if kunye is None:
        print("kunye yok")
        return 2
    kodlar = [h["kod"] for h in kunye["hucreler"]]
    roi = tuple(kunye["roi"])
    print(f"kume={kunye['kume']} n={len(klipler)} hucreler={kodlar}")

    kacis_analizi(klipler, kodlar)

    from evren_pano_ozel import _ikili, _mekanizma, _karsilastirma, _sayisal_yorum
    esik = (ozet or {}).get("h5_esik") or 3
    yorumlar = {"H1": _ikili, "H2": _ikili, "H3": _ikili, "H4": _mekanizma,
                "H5": _sayisal_yorum(esik), "H6": _karsilastirma, "H7": _karsilastirma}

    print(f"\n{'='*92}\nC) ESLI KARSILASTIRMA (McNemar, ayni klipler)\n{'='*92}")
    print(f"  (H5 esigi = {esik}, tr'de secildi)")
    ciftler = [("H1", "H2"), ("H2", "H3"), ("H2", "H4"), ("H2", "H5"),
               ("H2", "H6"), ("H6", "H7"), ("H4", "H5")]
    for a, b in ciftler:
        if a not in kodlar or b not in kodlar:
            continue
        m = mcnemar(klipler, a, b, yorumlar)
        if m is None:
            print(f"  {a} vs {b}: ortak KARAR VERILEN klip yok / tam anlasma")
            continue
        print(f"  {a} vs {b}: {a} dogru={m['a_dogru']:2d}  {b} dogru={m['b_dogru']:2d}  "
              f"({a}+/{b}- = {m['a_kazandi']}, {b}+/{a}- = {m['b_kazandi']})  p={m['p']:.4f}")

    sayisal_vs_dedektor(klipler, kunye.get("set") or os.path.join(KOK, "data/eval_defense"),
                        roi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
