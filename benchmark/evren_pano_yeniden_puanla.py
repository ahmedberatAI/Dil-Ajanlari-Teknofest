#!/usr/bin/env python
"""D42 — TUM PANO HUCRELERINI KAYITLI HAM CEVAPLARDAN YENIDEN PUANLA (istek YOK).

    python benchmark/evren_pano_yeniden_puanla.py

NEDEN: ilk kosumda PUANLAMA KUSURU vardi — sayisal hucre mantigi yalnizca kod=="H5"
icin calisiyordu, post-hoc H8 (tam kare + sayisal) puanlanmadan "MCC 0,000 / 34
kararsiz" diye raporlandi. Ham cevaplar DOGRU kaydedilmisti; yalnizca yorumlama
yanlisti. Bu betik TUM hucreleri kayitli JSONL'lerden yeniden puanlar, boylece
tek bir ek servis istegi yapilmadan dogru tablo uretilir.

AYRICA: H5 (ROI kirpma + sayisal) vs H8 (TAM KARE + sayisal) ESLI KARSILASTIRMASI —
"ROI kirpmasi GERCEKTEN gerekli mi?" sorusunun cevabi budur ve mimari karari
dogrudan etkiler (ROI'yi uretmek icin deterministik dedektor gerekir).
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

from evren_model_kars import tablo, dejenere_kontrol  # noqa: E402
from evren_pano_ozel import (_ikili, _mekanizma, _karsilastirma,  # noqa: E402
                             _sayisal_yorum, esik_tara, permutasyon)

YORUM = {"H1": _ikili, "H2": _ikili, "H3": _ikili, "H4": _mekanizma,
         "H6": _karsilastirma, "H7": _karsilastirma, "H9": _ikili}
SAYISAL = {"H5", "H8"}
ON_KAYITLI = {"H1", "H2", "H3", "H4", "H5", "H6", "H7"}


def yukle(kume):
    """Ayni kumenin TUM JSONL'lerini birlestir (post-hoc kosum ayri dosyada)."""
    satirlar = {}
    for yol in sorted(glob.glob(os.path.join(
            KOK, f"benchmark/results/evren_pano_ozel_{kume}*.jsonl"))):
        if "smoke" in yol:
            continue
        for s in open(yol, encoding="utf-8"):
            r = json.loads(s)
            if r.get("tur") != "klip":
                continue
            d = satirlar.setdefault(r["klip"], {"ihlal": r["ihlal"], "cevap": {}})
            for k, v in r["cevap"].items():
                if not str(v).startswith("__REFERANS"):
                    d["cevap"][k] = v
    return satirlar


def kol(satirlar, kod, esik=None):
    out = []
    for ad, d in sorted(satirlar.items()):
        c = d["cevap"].get(kod)
        if c is None:
            continue
        hata = str(c).startswith("__")
        if kod in SAYISAL:
            karar = None if (hata or esik is None) else _sayisal_yorum(esik)(c)
        else:
            karar = None if hata else YORUM[kod](c)
        out.append({"klip": ad, "ihlal": d["ihlal"], "hata": hata,
                    "ham": "" if hata else str(c), "karar": karar})
    return out


def mcnemar(a_sat, b_sat):
    ai = {r["klip"]: r for r in a_sat}
    bi = {r["klip"]: r for r in b_sat}
    ab = ba = ad = bd = n = 0
    for k in set(ai) & set(bi):
        ra, rb = ai[k], bi[k]
        if ra["karar"] is None or rb["karar"] is None or ra["hata"] or rb["hata"]:
            continue
        n += 1
        da, db = ra["karar"] == ra["ihlal"], rb["karar"] == rb["ihlal"]
        ad += da; bd += db
        if da and not db:
            ab += 1
        elif db and not da:
            ba += 1
    d = ab + ba
    p = 1.0 if d == 0 else min(1.0, 2 * sum(
        math.comb(d, i) for i in range(0, min(ab, ba) + 1)) / (2 ** d))
    return {"n": n, "a_dogru": ad, "b_dogru": bd, "a+b-": ab, "b+a-": ba, "p": p}


def rapor(kume):
    satirlar = yukle(kume)
    if not satirlar:
        print(f"[{kume}] kayit yok")
        return None, None
    kodlar = sorted({k for d in satirlar.values() for k in d["cevap"]},
                    key=lambda x: int(x[1:]))
    npoz = sum(1 for d in satirlar.values() if d["ihlal"])
    print(f"\n{'#'*104}\n# KUME {kume.upper()}  n={len(satirlar)} "
          f"(ACIK={npoz} KAPALI={len(satirlar)-npoz})  hucreler={kodlar}\n{'#'*104}")

    esikler, kollar = {}, {}
    for kod in kodlar:
        if kod in SAYISAL:
            if kume == "tr":
                e, _m, _s = esik_tara(kol(satirlar, kod, esik=3))
                esikler[kod] = e
                duyar = {x: tablo(kol(satirlar, kod, esik=x))["mcc"] for x in range(1, 11)}
                print(f"  {kod} esik taramasi (SADECE tr) -> {e};  esik duyarliligi: {duyar}")
            else:
                esikler[kod] = ESIK_TR.get(kod, 3)
                print(f"  {kod} esik SABIT {esikler[kod]} (tr'den; te'de tarama YOK)")
        kollar[kod] = kol(satirlar, kod, esik=esikler.get(kod))

    print(f"\n{'kod':4s} {'aile':8s} {'TP':>3s} {'FP':>3s} {'FN':>3s} {'TN':>3s} "
          f"{'krsz':>4s} {'n':>3s} {'MCC':>7s} {'dogr':>6s} {'GA95':>13s} "
          f"{'karar':>6s} {'DEJ':>4s}  en_sik")
    print("-" * 104)
    ozet = {}
    for kod in kodlar:
        sat = kollar[kod]
        an = tablo(sat)
        dej = dejenere_kontrol(sat)
        gec = [r for r in sat if not r["hata"]]
        ko = an["n_karar"] / len(gec) if gec else 0.0
        ozet[kod] = {"ana": an, "dej": dej, "karar_orani": ko,
                     "esik": esikler.get(kod), "ikincil": tablo(sat, ikincil=True)}
        print(f"{kod:4s} {'on-kayit' if kod in ON_KAYITLI else 'POST-HOC':8s} "
              f"{an['tp']:3d} {an['fp']:3d} {an['fn']:3d} {an['tn']:3d} {an['kararsiz']:4d} "
              f"{an['n_karar']:3d} {an['mcc']:+7.3f} {an['dogruluk']:6.3f} "
              f"[{an['ga95'][0]:.2f},{an['ga95'][1]:.2f}] {ko:6.2f} "
              f"{'EVET' if dej['dejenere'] else '  - ':4s}  {dej['en_sik_cevap']!r}"
              f" ({dej['en_sik_oran']:.2f})")
    return kollar, ozet


ESIK_TR = {}


def main():
    global ESIK_TR
    kollar_tr, ozet_tr = rapor("tr")
    if ozet_tr:
        ESIK_TR = {k: v["esik"] for k, v in ozet_tr.items() if v["esik"]}
        aile = {k: v for k, v in kollar_tr.items() if k in ON_KAYITLI}
        perm = permutasyon(aile)
        print(f"\n  COKLU KARSILASTIRMA — ON-KAYITLI AILE ({sorted(aile)}), "
              f"{perm['n_perm']} permutasyon")
        print(f"    bos dagilim %95 kuantili = {perm['bos_q95']:+.3f}   "
              f"gozlenen maks = {perm['gozlenen_maks']:+.3f}   "
              f"duzeltilmis p = {perm['p_duzeltilmis']:.5f}")
        print(f"    hucre bazli duzeltilmis p: {perm['p_hucre']}")
        ph = {k: v for k, v in kollar_tr.items() if k not in ON_KAYITLI}
        if ph:
            p2 = permutasyon(ph)
            print(f"\n  COKLU KARSILASTIRMA — POST-HOC AILE ({sorted(ph)}) AYRI duzeltildi")
            print(f"    bos %95 = {p2['bos_q95']:+.3f}  gozlenen maks = "
                  f"{p2['gozlenen_maks']:+.3f}  duzeltilmis p = {p2['p_duzeltilmis']:.5f}")

        print(f"\n  ESLI KARSILASTIRMALAR (McNemar, tr)")
        for a, b, ne in [("H5", "H8", "ROI kirpma GEREKLI mi? (sayisal soru sabit)"),
                         ("H5", "H3", "model/soru: llm-large sayisal vs vlm ikili"),
                         ("H2", "H9", "kacis secenegi kaldirilinca ikili DUZELIYOR mu?"),
                         ("H8", "H3", "tam kare sayisal vs ROI ikili (vlm)")]:
            if a in kollar_tr and b in kollar_tr:
                m = mcnemar(kollar_tr[a], kollar_tr[b])
                print(f"    {a} vs {b}: n={m['n']}  {a} dogru={m['a_dogru']} "
                      f"{b} dogru={m['b_dogru']}  ({a}+/{b}-={m['a+b-']}, "
                      f"{b}+/{a}-={m['b+a-']})  p={m['p']:.4f}   <- {ne}")
    rapor("te")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
