"""D43 asama-2 — KAZANAN SECIMI + ESLI TESTLER + DAGITIM TABLOSU.

evren_kombinasyon.py'yi ice aktarir; tr'de secer, te'de raporlar, ve
"kombinasyon tekil kolu GERCEKTEN geciyor mu?" sorusunu esli onyukleme ile test eder.
"""
from __future__ import annotations

import json
import math

import numpy as np

import evren_kombinasyon as EK

B_BOOT = 2000
SEED = 20260824

# --- kollarin GERCEK kunyesi (kod adlarindan okunabilir olsun diye)
ETIKET = {
    "COZ:llm-large@768":  "llm-large @768  SISTEM PROMPTU YOK",
    "COZ:llm-large@1280": "llm-large @1280 SISTEM PROMPTU YOK",
    "COZ:llm-large@1920": "llm-large @1920 SISTEM PROMPTU YOK",
    "KAC:A0_taban":       "llm-large @1280 sistem VAR + kacis secenegi VAR",
    "KAC:H1_kacissiz":    "llm-large @1280 sistem VAR + kacis secenegi YOK",
    "KAC:H2_iki_asama":   "llm-large @1280 iki asamali soru",
    "KAC:H3_sistem":      "llm-large @1280 sistem cumlesi TERSINE",
    "KAC:H4_capa":        "llm-large @1280 gorsel capa (lime)",
    "KAC:H5_tersine":     "llm-large @1280 olumsuz soru + ters secenek",
    "KAC:F1_sissiz_kacisli":   "llm-large @1280 SISTEM YOK + kacis VAR",
    "KAC:F2_sissiz_kacissiz":  "llm-large @1280 SISTEM YOK + kacis YOK",
    "OZL:H1": "llm-large ROI-dar kirpma, ikili soru",
    "OZL:H2": "llm-large ROI-baglam kirpma, ikili soru",
    "OZL:H3": "vlm ROI-baglam kirpma, ikili soru",
    "OZL:H4": "llm-large ROI-baglam, mekanizma sorusu (koyu oyuk)",
    "OZL:H6": "llm-large 2-goruntu (ACIK referans + sorgu)",
    "OZL:H7": "llm-fast 2-goruntu (ACIK referans + sorgu)",
    "OZL:H9": "llm-large ROI-baglam, kacissiz ikili soru",
}
for t in range(1, 11):
    ETIKET[f"OZL:H5>={t}"] = f"llm-large ROI-baglam, 0-10 KARANLIK skoru, esik>={t}"
    ETIKET[f"OZL:H8>={t}"] = f"llm-large TAM KARE, 0-10 KARANLIK skoru, esik>={t}"
for m in ("vlm", "llm-large", "llm-fast"):
    for c in (768, 1280, 1920):
        ETIKET[f"IZG:{m}@{c}"] = f"{m} @{c} sistem VAR + kacis secenegi VAR"


def etiketle(ad):
    for k in sorted(ETIKET, key=len, reverse=True):
        ad = ad.replace(k, ETIKET[k])
    return ad


def mcc_alt(vec, y, idx):
    tp = fp = fn = tn = 0
    for i in idx:
        v, lab = vec[i], y[i]
        if v is None:
            continue
        if v and lab:
            tp += 1
        elif v and not lab:
            fp += 1
        elif (not v) and lab:
            fn += 1
        else:
            tn += 1
    return EK.mcc4(tp, fp, fn, tn), tp + fp + fn + tn


def esli_onyukleme(v1, v2, y, idx, B=B_BOOT, seed=SEED):
    """AYNI kliplerde iki adayin MCC farki icin esli onyukleme %95 GA."""
    rng = np.random.default_rng(seed)
    idx = np.array(idx)
    d0 = mcc_alt(v1, y, idx)[0] - mcc_alt(v2, y, idx)[0]
    fark = np.empty(B)
    for b in range(B):
        s = rng.choice(idx, size=len(idx), replace=True)
        fark[b] = mcc_alt(v1, y, s)[0] - mcc_alt(v2, y, s)[0]
    lo, hi = np.quantile(fark, [0.025, 0.975])
    return {"fark": d0, "ga": [float(lo), float(hi)],
            "p_iki_yonlu": float(2 * min((fark <= 0).mean(), (fark >= 0).mean()))}


def ozdes_mi(v1, v2, idx):
    return all(v1[i] == v2[i] for i in idx)


def sec(A, tur_filtre=None, te_zorunlu=False):
    """tr'de en iyi: MCC -> karar orani -> az kol (sadelik). DEJENERE haric."""
    ad = [s for s in A["temiz"]
          if (tur_filtre is None or s["tur"] in tur_filtre)
          and (not te_zorunlu or s["te_olculdu"])]
    if not ad:
        return None
    ad.sort(key=lambda s: (-round(s["tr"]["mcc"], 6),
                           -round(s["tr"]["karar_orani"], 6),
                           s["ad"].count("&") + s["ad"].count("|")
                           + s["ad"].count("->") + s["ad"].count("+"),
                           len(s["ad"])))
    return ad[0]


def rapor(A):
    sn = A["sinif"]
    y, tri, tei = A["y"], A["tr_idx"], A["te_idx"]
    print("=" * 100)
    print(f"###  {sn.upper()}   n_tr={len(tri)}  n_te={len(tei)}   "
          f"aday havuzu={A['n_aday']} (dejenere olmayan {A['n_temiz']})")
    print(f"     maks-istatistigi bos dagilim %95 kuantili = {A['q95']:+.3f}")

    en_tekil = sec(A, {"TEKIL"})
    en_komb = sec(A, {"K1", "K2", "K3", "K5"})
    en_genel = sec(A)
    en_te = sec(A, te_zorunlu=True)

    def blok(s, basl):
        if s is None:
            print(f"  {basl}: YOK")
            return
        t, e = s["tr"], s["te"]
        lo, hi = e["wilson"]
        print(f"  {basl}")
        print(f"     kol      : {etiketle(s['ad'])}")
        print(f"     tr (SECIM): MCC {t['mcc']:+.3f}  karar {t['karar_orani']:.2f}  "
              f"TP/FP/FN/TN = {t['tp']}/{t['fp']}/{t['fn']}/{t['tn']}  "
              f"kararsiz {t['kararsiz']}  duzeltilmis p={s.get('p_duz'):.4f}")
        if s["te_olculdu"]:
            print(f"     te (RAPOR): MCC {e['mcc']:+.3f}  dogruluk {e['dogruluk']:.3f} "
                  f"[Wilson {lo:.2f}-{hi:.2f}]  karar {e['karar_orani']:.2f}  "
                  f"TP/FP/FN/TN = {e['tp']}/{e['fp']}/{e['fn']}/{e['tn']} "
                  f"kararsiz {e['kararsiz']}")
        else:
            print("     te (RAPOR): BU KOL te'DE OLCULMEDI")
        d = t["dagitim"]
        print(f"     ikincil (sahada dagitim, kararsiz->alarm yok) tr: "
              f"MCC {d['mcc']:+.3f} dogruluk {d['dogruluk']:.3f} "
              f"TP/FP/FN/TN = {d['tp']}/{d['fp']}/{d['fn']}/{d['tn']}")

    blok(en_tekil, "EN IYI TEKIL (tr)")
    print()
    blok(en_komb, "EN IYI KOMBINASYON (tr)")
    print()

    # --- kombinasyon tekil kolu GERCEKTEN geciyor mu?
    if en_tekil and en_komb:
        if ozdes_mi(en_komb["vec"], en_tekil["vec"], tri + tei):
            print("  >> KOMBINASYON, TEKIL KOL ILE BIREBIR AYNI KARARLARI VERIYOR "
                  "(cebirsel olarak ozdes; 'kombinasyon kazanci' YOKTUR).")
        else:
            b = esli_onyukleme(en_komb["vec"], en_tekil["vec"], y, tri)
            print(f"  >> ESLI TEST (tr, kombinasyon - tekil): "
                  f"fark {b['fark']:+.3f}  %95 GA [{b['ga'][0]:+.3f}, {b['ga'][1]:+.3f}]  "
                  f"p={b['p_iki_yonlu']:.3f}")
            kk = en_komb["tr"]["karar_orani"] - en_tekil["tr"]["karar_orani"]
            print(f"     karar orani farki: {kk:+.2f}")
            if b["ga"][0] <= 0 <= b["ga"][1] or abs(b["fark"]) < 0.05:
                print("     HUKUM: ANLAMLI FARK YOK (GA sifiri iceriyor "
                      "ve/veya fark 0,05 gurultu esiginin altinda) -> BERABERE")
            else:
                print("     HUKUM: fark GA'ya gore sifirdan uzak")
    print()

    if en_te and en_genel and en_te["ad"] != en_genel["ad"]:
        blok(en_te, "te'DE OLCULEBILEN EN IYI tr ADAYI (on-kayitli yedek)")
        print()

    # --- yerel taban
    tb = A["taban"]
    print(f"  YEREL TABAN (Qwen3-VL-8B-FP8, islemsel prompt, kare tabanli):")
    print(f"     tr MCC {tb['tr']['mcc']:+.3f} karar {tb['tr']['karar_orani']:.2f} "
          f"TP/FP/FN/TN={tb['tr']['tp']}/{tb['tr']['fp']}/{tb['tr']['fn']}/{tb['tr']['tn']} "
          f"dejenere={tb['dej']}")
    print(f"     te MCC {tb['te']['mcc']:+.3f} dogruluk {tb['te']['dogruluk']:.3f} "
          f"karar {tb['te']['karar_orani']:.2f}")
    # esli test: kazanan vs yerel taban
    tbv = A.get("taban_vec")
    if tbv is not None and en_genel is not None and not tb["dej"]:
        b_tr = esli_onyukleme(en_genel["vec"], tbv, y, tri)
        print(f"     ESLI (tr, kazanan - yerel): fark {b_tr['fark']:+.3f} "
              f"%95 GA [{b_tr['ga'][0]:+.3f}, {b_tr['ga'][1]:+.3f}] p={b_tr['p_iki_yonlu']:.3f}")
        if en_genel["te_olculdu"]:
            b_te = esli_onyukleme(en_genel["vec"], tbv, y, tei)
            print(f"     ESLI (te, kazanan - yerel): fark {b_te['fark']:+.3f} "
                  f"%95 GA [{b_te['ga'][0]:+.3f}, {b_te['ga'][1]:+.3f}] p={b_te['p_iki_yonlu']:.3f}")
    elif tb["dej"]:
        print("     -> YEREL TABAN DEJENERE (hic karar vermiyor): "
              "esli test ANLAMSIZ; uzak servis 'kazandi' demek yerine "
              "'yerel taban bu sinifta YOK' demek dogrudur.")
    print()

    # --- basari olcutu
    print("  BASARI OLCUTU (dorttu birden):")
    for s, ad in ((en_genel, "en iyi genel"),):
        if s is None:
            continue
        t = s["tr"]
        a = not s["dej"]
        b_ = t["mcc"] >= 0.40
        c = t["karar_orani"] >= 0.70
        d = t["mcc"] > A["q95"]
        print(f"     (a) dejenere degil : {a}")
        print(f"     (b) tr MCC>=+0,40  : {b_}  ({t['mcc']:+.3f})")
        print(f"     (c) karar>=0,70    : {c}  ({t['karar_orani']:.2f})")
        print(f"     (d) > bos %95      : {d}  ({t['mcc']:+.3f} vs {A['q95']:+.3f})")
        print(f"     ==> {'GECTI' if all((a, b_, c, d)) else 'GECMEDI'}")
    print()
    return {"tekil": en_tekil, "komb": en_komb, "genel": en_genel, "te": en_te}


def main():
    S = EK.veri_yukle()
    taban = EK.yerel_taban()
    kazananlar = {}
    for sn in ("forklift", "yelek", "pano"):
        A = EK.analiz(sn, S, taban)
        tb = taban.get(sn, {})
        A["taban_vec"] = [tb.get(k) for k in A["klipler"]]
        kazananlar[sn] = (A, rapor(A))

    # --- nihai dagitim tablosu
    print("=" * 100)
    print("NIHAI DAGITIM TABLOSU  (secim=_tr, manset=_te)")
    print("=" * 100)
    hdr = (f"{'sinif':9s} | {'secilen yapilandirma':58s} | {'te-MCC':>7s} | "
           f"{'te-dog':>6s} | {'Wilson %95':>12s} | {'karar':>5s} | "
           f"{'YEREL':>7s} | anlamli mi")
    print(hdr)
    print("-" * len(hdr))
    for sn, (A, w) in kazananlar.items():
        s = w["genel"]
        if s is None:
            continue
        if not s["te_olculdu"] and w["te"] is not None:
            s = w["te"]
        e = s["te"]
        lo, hi = e["wilson"]
        tb = A["taban"]
        yer = "YOK(dej)" if tb["dej"] else f"{tb['te']['mcc']:+.3f}"
        print(f"{sn:9s} | {etiketle(s['ad'])[:58]:58s} | {e['mcc']:+7.3f} | "
              f"{e['dogruluk']:6.3f} | {lo:5.2f}-{hi:5.2f}  | {e['karar_orani']:5.2f} | "
              f"{yer:>8s} |")
    return kazananlar


if __name__ == "__main__":
    main()
