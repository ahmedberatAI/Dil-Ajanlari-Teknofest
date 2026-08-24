"""D43 — EN IYI KOMBINASYON (yeniden analiz, YENI MODEL CAGRISI YOK).

ON-KAYIT: benchmark/results/evren_kombinasyon_onkayit.json
(kosumdan / hicbir MCC hesaplanmadan ONCE yazildi; EK_ON_KAYIT_1 de oyle).

Onceki uc taramanin HAM JSONL ciktilarini yukler, tekil kollari ve
K1..K5 kombinasyon kurallarini AYNI klipler uzerinde (esli tasarim) puanlar.
Secim YALNIZ _tr; manset YALNIZ _te. Maks-istatistigi permutasyonu ile
coklu-karsilastirma duzeltmesi yapar.

    python benchmark/evren_kombinasyon.py
"""
from __future__ import annotations

import itertools
import json
import math
import os
from collections import Counter, defaultdict

import numpy as np

R = "/mnt/c/Users/omen/Desktop/DilAjanlariTeknofest/benchmark/results/"
B_PERM = 2000
SEED = 20260824
MIN_KARAR = 8          # bu sayidan az karar -> MCC 0 sayilir
DEJ_ESIK = 0.85


# --------------------------------------------------------------- yardimcilar
def jsonl(fn):
    out = []
    with open(R + fn, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def bolum(klip):
    return "te" if "_te" in klip else "tr"


def _kasa(c):
    c = (c or "").strip().upper()
    if c.endswith("+"):
        c = c[:-1]
    if c.isdigit():
        return int(c) >= 3
    return None


def _yelek(c):
    c = (c or "").strip().upper()
    if c == "YELEK_YOK":
        return True
    if c == "YELEK_VAR":
        return False
    return None


def _pano(c):
    c = (c or "").strip().upper()
    if c == "ACIK":
        return True
    if c == "KAPALI":
        return False
    return None


def _oyuk(c):
    c = (c or "").strip().upper()
    if c == "OYUK_VAR":
        return True
    if c == "OYUK_YOK":
        return False
    return None


def _iki_goruntu(c):
    """Referans goruntu ACIK. Sorgu (ikinci) goruntu acik mi?"""
    c = (c or "").strip().upper()
    if c in ("IKISI_DE", "IKINCI"):
        return True
    if c in ("BIRINCI", "HICBIRI"):
        return False
    return None


def _sayi(c):
    c = (c or "").strip()
    return int(c) if c.isdigit() else None


# --------------------------------------------------------------- veri yukleme
def veri_yukle():
    """sinif -> {"etiket": {klip: 0/1}, "kollar": {ad: {klip: True/False/None}},
                 "ham": {ad: {klip: str}}}"""
    S = {c: {"etiket": {}, "kollar": defaultdict(dict), "ham": defaultdict(dict)}
         for c in ("forklift", "yelek", "pano")}
    yorum = {"forklift": _kasa, "yelek": _yelek, "pano": _pano}

    # 1) evren_izgara  (forklift + yelek, 3 model x cozunurluk)
    gorulen = set()
    for r in jsonl("evren_izgara_20260824_122459.jsonl"):
        if r.get("hata"):
            continue
        k = (r["klip"], r["model"], r["cozunurluk"])
        if k in gorulen:            # on-kayit: mukerrer -> ILK kayit
            continue
        gorulen.add(k)
        sn = r["sinif"]
        ad = f"IZG:{r['model']}@{r['cozunurluk']}"
        S[sn]["etiket"][r["klip"]] = int(r["etiket"])
        S[sn]["kollar"][ad][r["klip"]] = yorum[sn](r["ham_cevap"])
        S[sn]["ham"][ad][r["klip"]] = r["ham_cevap"]

    # 2) evren_cozunurluk_ham  (yelek + pano, llm-large, 3 cozunurluk)
    for r in jsonl("evren_cozunurluk_ham_20260824_120530.jsonl"):
        sn = r["sinif"]
        ad = f"COZ:llm-large@{r['max_side']}"
        S[sn]["etiket"][r["klip"]] = int(r["etiket"])
        S[sn]["kollar"][ad][r["klip"]] = yorum[sn](r["cevap"])
        S[sn]["ham"][ad][r["klip"]] = r["cevap"]

    # 3) evren_kacis  (yelek + pano, llm-large@1280, 8 prompt kolu)
    for r in jsonl("evren_kacis_20260824_122433.jsonl"):
        if r.get("tur") != "cevap" or r.get("hata"):
            continue
        sn = r["sinif"]
        ad = f"KAC:{r['kol']}"
        S[sn]["etiket"][r["klip"]] = 1 if r["ihlal"] else 0
        S[sn]["kollar"][ad][r["klip"]] = r["karar"]
        S[sn]["ham"][ad][r["klip"]] = r["ham"]

    # 4) pano_ozel (tr + te + posthoc)
    kat = {"H1": _pano, "H2": _pano, "H3": _pano, "H9": _pano,
           "H4": _oyuk, "H6": _iki_goruntu, "H7": _iki_goruntu}
    for fn in ("evren_pano_ozel_tr_20260824_122707.jsonl",
               "evren_pano_ozel_te_20260824_130447.jsonl",
               "evren_pano_ozel_tr_posthoc_20260824_131614.jsonl"):
        for r in jsonl(fn):
            if r.get("tur") != "klip":
                continue
            S["pano"]["etiket"][r["klip"]] = 1 if r["ihlal"] else 0
            for kod, cev in r["cevap"].items():
                if kod in kat:
                    ad = f"OZL:{kod}"
                    S["pano"]["kollar"][ad][r["klip"]] = kat[kod](cev)
                    S["pano"]["ham"][ad][r["klip"]] = cev
                elif kod in ("H5", "H8"):          # sayisal, esik taranir
                    v = _sayi(cev)
                    for t in range(1, 11):
                        ad = f"OZL:{kod}>={t}"
                        S["pano"]["kollar"][ad][r["klip"]] = (
                            None if v is None else v >= t)
                        S["pano"]["ham"][ad][r["klip"]] = cev
    return S


def yerel_taban():
    """Qwen3-VL-8B-FP8 yerel, islemsel prompt (kol B). klip bazli."""
    d = json.load(open(R + "islemsel_prompt_20260819_122138.json", encoding="utf-8"))
    esle = {"forklift-asiri-yuk": "forklift", "yetki-yelek": "yelek",
            "pano-kapak": "pano"}
    out = {}
    for kol, sn in esle.items():
        out[sn] = {r["klip"]: r["B_islemsel"] for r in d["kollar"][kol]["satirlar"]}
    return out


# --------------------------------------------------------------- istatistik
def mcc4(tp, fp, fn, tn):
    p = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return (tp * tn - fp * fn) / p if p else 0.0


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def puanla(vec, y):
    """vec: klip sirasinda 1/0/None; y: 1/0 etiket. Ana tablo = karar verilenler."""
    tp = fp = fn = tn = kararsiz = 0
    for v, lab in zip(vec, y):
        if v is None:
            kararsiz += 1
        elif v and lab:
            tp += 1
        elif v and not lab:
            fp += 1
        elif (not v) and lab:
            fn += 1
        else:
            tn += 1
    n = len(y)
    karar = tp + fp + fn + tn
    m = mcc4(tp, fp, fn, tn) if karar >= MIN_KARAR else 0.0
    dog = (tp + tn) / karar if karar else 0.0
    lo, hi = wilson(tp + tn, karar)
    # ikincil: sahada dagitim (kararsiz -> alarm yok)
    d_tp = tp
    d_fp = fp
    d_fn = fn + sum(1 for v, lab in zip(vec, y) if v is None and lab)
    d_tn = tn + sum(1 for v, lab in zip(vec, y) if v is None and not lab)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "kararsiz": kararsiz,
            "n": n, "karar": karar, "karar_orani": karar / n if n else 0.0,
            "mcc": m, "dogruluk": dog, "wilson": [lo, hi],
            "dagitim": {"tp": d_tp, "fp": d_fp, "fn": d_fn, "tn": d_tn,
                        "mcc": mcc4(d_tp, d_fp, d_fn, d_tn),
                        "dogruluk": (d_tp + d_tn) / n if n else 0.0}}


def dejenere(vec, ham_sayac):
    """D1 en sik HAM cevap >=85%  ·  D2 karar verilenlerde bir taraf >=85%."""
    n = len(vec)
    d1 = False
    if ham_sayac:
        tot = sum(ham_sayac.values())
        d1 = tot > 0 and max(ham_sayac.values()) / tot >= DEJ_ESIK
    kar = [v for v in vec if v is not None]
    d2 = False
    if kar:
        pos = sum(1 for v in kar if v)
        d2 = max(pos, len(kar) - pos) / len(kar) >= DEJ_ESIK
    return d1, d2, (d1 or d2)


# --------------------------------------------------------------- kombinasyon
def k1_uzlasi(a, b):
    return [x if (x is not None and x == y) else None for x, y in zip(a, b)]


def k2_yedek(a, b):
    return [x if x is not None else y for x, y in zip(a, b)]


def k3_cogunluk(a, b, c):
    out = []
    for t in zip(a, b, c):
        kar = [v for v in t if v is not None]
        if not kar:
            out.append(None)
            continue
        pos = sum(1 for v in kar if v)
        neg = len(kar) - pos
        out.append(True if pos > neg else (False if neg > pos else None))
    return out


def k5_agirlikli(vecs, agirliklar):
    out = []
    for t in zip(*vecs):
        sp = sn = 0.0
        for v, w in zip(t, agirliklar):
            if v is True:
                sp += w
            elif v is False:
                sn += w
        if sp == 0 and sn == 0:
            out.append(None)
        elif sp == sn:
            out.append(None)
        else:
            out.append(sp > sn)
    return out


# --------------------------------------------------------------- aday havuzu
def havuz_kur(kollar, klipler, tr_idx):
    """kollar: {ad: {klip: karar}} -> aday listesi [(ad, tur, vec)]"""
    tekil = {}
    for ad, m in sorted(kollar.items()):
        tekil[ad] = [m.get(k) for k in klipler]

    adaylar = [(ad, "TEKIL", v) for ad, v in tekil.items()]
    adlar = sorted(tekil)

    for a, b in itertools.combinations(adlar, 2):
        adaylar.append((f"K1[{a} & {b}]", "K1", k1_uzlasi(tekil[a], tekil[b])))
    for a, b in itertools.permutations(adlar, 2):
        adaylar.append((f"K2[{a} -> {b}]", "K2", k2_yedek(tekil[a], tekil[b])))
    for a, b, c in itertools.combinations(adlar, 3):
        adaylar.append((f"K3[{a} | {b} | {c}]", "K3",
                        k3_cogunluk(tekil[a], tekil[b], tekil[c])))
    return adaylar, tekil


def k5_ekle(adaylar, tekil, uclu, tr_idx):
    """K5: agirlik = 1 - (tr kacis orani).  Agirliklar YALNIZ tr'den."""
    uclu = [a for a in uclu if a in tekil]
    if len(uclu) < 2:
        return None
    ag = []
    for a in uclu:
        v = [tekil[a][i] for i in tr_idx]
        kacis = sum(1 for x in v if x is None) / len(v) if v else 1.0
        ag.append(1.0 - kacis)
    vec = k5_agirlikli([tekil[a] for a in uclu], ag)
    ad = "K5[" + " + ".join(uclu) + "]  ag=" + ",".join(f"{w:.2f}" for w in ag)
    adaylar.append((ad, "K5", vec))
    return ad, ag


# --------------------------------------------------------------- ana akis
def analiz(sinif, S, taban):
    et = S[sinif]["etiket"]
    klipler = sorted(et)
    y = [et[k] for k in klipler]
    tr_idx = [i for i, k in enumerate(klipler) if bolum(k) == "tr"]
    te_idx = [i for i, k in enumerate(klipler) if bolum(k) == "te"]

    kollar = {a: dict(m) for a, m in S[sinif]["kollar"].items()}
    adaylar, tekil = havuz_kur(kollar, klipler, tr_idx)

    # K5 (sinif basina TEK aday, on-kayitta ilan edildi)
    K5_SET = {"forklift": ["IZG:vlm@1280", "IZG:llm-large@1280", "IZG:llm-fast@1280"],
              "yelek": ["IZG:vlm@1280", "IZG:llm-large@1280", "IZG:llm-fast@1280"],
              "pano": ["OZL:H2", "OZL:H3", "OZL:H7"]}
    k5info = k5_ekle(adaylar, tekil, K5_SET[sinif], tr_idx)

    # --- dejenerelik kapisi (etiketten bagimsiz, tr uzerinde)
    ham = S[sinif]["ham"]
    sonuc = []
    for ad, tur, vec in adaylar:
        vtr = [vec[i] for i in tr_idx]
        hs = None
        if tur == "TEKIL" and ad in ham:
            hs = Counter(ham[ad][klipler[i]] for i in tr_idx
                         if klipler[i] in ham[ad])
        d1, d2, dej = dejenere(vtr, hs)
        sonuc.append({"ad": ad, "tur": tur, "vec": vec,
                      "dej": dej, "d1": d1, "d2": d2})

    temiz = [s for s in sonuc if not s["dej"]]

    # --- tr puanlari
    ytr = [y[i] for i in tr_idx]
    yte = [y[i] for i in te_idx]
    for s in sonuc:
        s["tr"] = puanla([s["vec"][i] for i in tr_idx], ytr)
        vte = [s["vec"][i] for i in te_idx]
        s["te"] = puanla(vte, yte) if te_idx else None
        s["te_olculdu"] = any(v is not None for v in vte)

    # --- permutasyon (yalniz temiz havuz; her turda TUM havuz yeniden puanlanir)
    rng = np.random.default_rng(SEED)
    M = np.array([[1 if s["vec"][i] is True else (0 if s["vec"][i] is False else -1)
                   for i in tr_idx] for s in temiz], dtype=np.int8)
    pos = (M == 1).astype(np.float64)
    neg = (M == 0).astype(np.float64)
    ytr_a = np.array(ytr, dtype=np.float64)
    karar_say = (pos + neg).sum(1)
    yeterli = karar_say >= MIN_KARAR

    def mcc_vec(yv):
        tp = pos @ yv
        fp = pos @ (1 - yv)
        fn = neg @ yv
        tn = neg @ (1 - yv)
        den = np.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
        out = np.zeros_like(den)
        nz = den > 0
        out[nz] = (tp[nz] * tn[nz] - fp[nz] * fn[nz]) / den[nz]
        out[~yeterli] = 0.0
        return out

    gozlenen = mcc_vec(ytr_a)
    bos_max = np.empty(B_PERM)
    for b in range(B_PERM):
        bos_max[b] = np.abs(mcc_vec(rng.permutation(ytr_a))).max()
    q95 = float(np.quantile(bos_max, 0.95))

    for s, m in zip(temiz, gozlenen):
        s["tr_mcc_np"] = float(m)
        s["p_duz"] = float((1 + (bos_max >= abs(m)).sum()) / (B_PERM + 1))

    # --- yerel taban ayni bolunmede
    tb = taban.get(sinif, {})
    tb_vec = [tb.get(k) for k in klipler]
    tb_tr = puanla([tb_vec[i] for i in tr_idx], ytr)
    tb_te = puanla([tb_vec[i] for i in te_idx], yte)
    hs_tb = Counter(str(tb_vec[i]) for i in tr_idx)
    tb_dej = dejenere([tb_vec[i] for i in tr_idx], hs_tb)

    return {"sinif": sinif, "klipler": klipler, "y": y, "tr_idx": tr_idx,
            "te_idx": te_idx, "sonuc": sonuc, "temiz": temiz, "q95": q95,
            "bos_max": bos_max, "taban": {"tr": tb_tr, "te": tb_te,
                                          "dej": tb_dej[2]},
            "k5": k5info, "n_aday": len(adaylar), "n_temiz": len(temiz)}


def yaz(A):
    sn = A["sinif"]
    print("=" * 96)
    print(f"### {sn.upper()}   n_tr={len(A['tr_idx'])}  n_te={len(A['te_idx'])}"
          f"   aday={A['n_aday']}  (dejenere olmayan={A['n_temiz']})")
    print(f"    maks-istatistigi bos dagilim %95 kuantili (tr) = {A['q95']:+.3f}")
    tb = A["taban"]
    print(f"    YEREL TABAN (Qwen3-VL-8B, islemsel prompt): "
          f"tr MCC {tb['tr']['mcc']:+.3f} (karar {tb['tr']['karar_orani']:.2f}, "
          f"dej={tb['dej']})  |  te MCC {tb['te']['mcc']:+.3f} "
          f"(karar {tb['te']['karar_orani']:.2f})")
    print()

    def satir(s, etiket=""):
        t = s["tr"]
        e = s["te"]
        p = s.get("p_duz")
        ps = f"{p:.4f}" if p is not None else "  DEJ "
        te_s = (f"{e['mcc']:+.3f}/{e['dogruluk']:.2f}/{e['karar_orani']:.2f}"
                if s["te_olculdu"] else "   OLCULMEDI   ")
        print(f"  {etiket}{s['ad'][:62]:62s} | tr {t['mcc']:+.3f} "
              f"kar{t['karar_orani']:.2f} "
              f"[{t['tp']:2d}/{t['fp']:2d}/{t['fn']:2d}/{t['tn']:2d} ks{t['kararsiz']:2d}]"
              f" p={ps} | te {te_s}")

    print("  -- TEKIL kollar (dejenere olanlar DAHIL, isaretli) --")
    tek = sorted([s for s in A["sonuc"] if s["tur"] == "TEKIL"],
                 key=lambda s: -s["tr"]["mcc"])
    for s in tek:
        satir(s, "DEJ " if s["dej"] else "    ")
    print()
    for tur in ("K1", "K2", "K3", "K5"):
        gr = [s for s in A["temiz"] if s["tur"] == tur]
        if not gr:
            continue
        gr.sort(key=lambda s: -s["tr"]["mcc"])
        print(f"  -- {tur} en iyi 5 (dejenere olmayanlar) --")
        for s in gr[:5]:
            satir(s, "    ")
        print()


def main():
    S = veri_yukle()
    taban = yerel_taban()
    hepsi = {}
    for sn in ("forklift", "yelek", "pano"):
        A = analiz(sn, S, taban)
        hepsi[sn] = A
        yaz(A)

    # ---- kayit
    out = {}
    for sn, A in hepsi.items():
        kayit = []
        for s in A["sonuc"]:
            kayit.append({k: v for k, v in s.items() if k != "vec"})
        out[sn] = {"q95": A["q95"], "n_aday": A["n_aday"],
                   "n_temiz": A["n_temiz"], "taban": A["taban"],
                   "n_tr": len(A["tr_idx"]), "n_te": len(A["te_idx"]),
                   "adaylar": kayit}
    with open(R + "evren_kombinasyon_sonuc.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("kaydedildi:", R + "evren_kombinasyon_sonuc.json")
    return hepsi


if __name__ == "__main__":
    main()
