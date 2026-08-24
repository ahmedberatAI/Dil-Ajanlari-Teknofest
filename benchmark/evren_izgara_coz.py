#!/usr/bin/env python
"""D42 — EVREN TAM IZGARA COZUMLEMESI (evren_izgara.py ciktisini yorumlar).

    python benchmark/evren_izgara_coz.py benchmark/results/evren_izgara_<zaman>.jsonl

ON-KAYITTA ILAN EDILEN kurallari UYGULAR (yeniden karar VERMEZ):
  · KACIS (GORUNMUYOR/KISI_YOK) = KARARSIZ. ANA tablo yalniz karar verilenlerden.
  · Ikincil "sahada dagitim" tablosu: kararsiz -> alarm yok (ACIKCA ikincil).
  · DEJENERELIK: D1 en sik ham cevap >= %85 · D2 karar verilenlerde bir taraf >= %85.
  · SECIM YALNIZ tr · MANSET YALNIZ te.
  · COKLU KARSILASTIRMA: etiket permutasyonu + MAKS-ISTATISTIGI (sinif ici permutasyon,
    hucrelerin esli yapisi korunur), 10.000 tekrar, bos maks|MCC| dagiliminin %95 kuantili.
  · Wilson %95 GA dogruluk uzerinden.
"""
from __future__ import annotations

import collections
import json
import math
import os
import random
import sys

KACIS = {"GORUNMUYOR", "KISI_YOK", ""}
MODEL_SIRA = ["vlm", "llm-large", "llm-fast"]
SECENEK = {
    "forklift": ["0", "1", "2", "3", "4", "5", "6+", "GORUNMUYOR"],
    "yelek": ["YELEK_VAR", "YELEK_YOK", "KISI_YOK", "GORUNMUYOR"],
    "pano": ["ACIK", "KAPALI", "GORUNMUYOR"],
}
BEKLENEN_N = {"forklift": 50, "yelek": 50, "pano": 49}
EKSIK_HUCRE: dict = {}


# ------------------------------------------------------------------ yorumlayici
def yorum(sinif, c):
    """Doner True(ihlal) / False(ihlal degil) / None(kararsiz)."""
    c = (c or "").strip().upper()
    if sinif == "forklift":
        if c in KACIS:
            return None
        if c.endswith("+"):
            c = c[:-1]
        try:
            return int(c) >= 3
        except ValueError:
            return None
    if sinif == "yelek":
        if c == "YELEK_YOK":
            return True
        if c == "YELEK_VAR":
            return False
        return None
    if sinif == "pano":
        if c == "ACIK":
            return True
        if c == "KAPALI":
            return False
        return None
    raise ValueError(sinif)


# -------------------------------------------------------------------- istatistik
def mcc_sayim(tp, fp, fn, tn):
    p = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return (tp * tn - fp * fn) / p if p else 0.0


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    q = k / n
    d = 1 + z * z / n
    m = (q + z * z / (2 * n)) / d
    y = z * math.sqrt(q * (1 - q) / n + z * z / (4 * n * n)) / d
    return (max(0.0, m - y), min(1.0, m + y))


def tablo(kayitlar, ikincil=False):
    """kayitlar: [(etiket_bool, karar_bool|None, hata_bool)]"""
    tp = fp = fn = tn = kararsiz = hata = 0
    for et, kr, ht in kayitlar:
        if ht:
            hata += 1
            continue
        if kr is None:
            if not ikincil:
                kararsiz += 1
                continue
            kr = False
        if et and kr:
            tp += 1
        elif et:
            fn += 1
        elif kr:
            fp += 1
        else:
            tn += 1
    n = tp + fp + fn + tn
    lo, hi = wilson(tp + tn, n)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "kararsiz": kararsiz, "hata": hata,
            "n": n, "mcc": round(mcc_sayim(tp, fp, fn, tn), 4),
            "dogruluk": round((tp + tn) / n, 4) if n else 0.0,
            "ga95": [round(lo, 4), round(hi, 4)]}


def dejenere(kayitlar, hamlar):
    gecerli = [(k, h) for k, h in zip(kayitlar, hamlar) if not k[2]]
    n = len(gecerli)
    sayim = collections.Counter((h or "").strip().upper() or "(BOS)" for _, h in gecerli)
    en_sik, en_sik_n = sayim.most_common(1)[0] if sayim else ("", 0)
    d1 = bool(n) and en_sik_n >= 0.85 * n
    kararli = [k for k, _ in gecerli if k[1] is not None]
    nk = len(kararli)
    poz = sum(1 for k in kararli if k[1])
    d2 = bool(nk) and (poz >= 0.85 * nk or (nk - poz) >= 0.85 * nk)
    return {"dejenere": bool(d1 or d2), "D1": d1, "D2": d2,
            "en_sik": en_sik, "en_sik_oran": round(en_sik_n / n, 3) if n else 0.0,
            "dagilim": dict(sayim.most_common())}


def mcnemar(a_dogru, b_dogru):
    """Esli (ayni klipler) dogru/yanlis vektorleri. Tam binom (iki yanli)."""
    b = sum(1 for x, y in zip(a_dogru, b_dogru) if x and not y)   # A dogru, B yanlis
    c = sum(1 for x, y in zip(a_dogru, b_dogru) if y and not x)   # B dogru, A yanlis
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "p": 1.0}
    k = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return {"b": b, "c": c, "p": round(min(1.0, p), 5)}


# ------------------------------------------------------------------------- ana
def main():
    yol = sys.argv[1]
    satirlar = [json.loads(l) for l in open(yol, encoding="utf-8")]

    # hucre -> sinif -> {klip: (karar, ham, hata)}
    hucreler = collections.defaultdict(dict)
    etiketler = collections.defaultdict(dict)     # sinif -> klip -> (etiket, bolum)
    for r in satirlar:
        anahtar = (r["sinif"], r["model"], r["cozunurluk"])
        ham = r.get("ham_cevap")
        ht = ham is None
        hucreler[anahtar][r["klip"]] = (None if ht else yorum(r["sinif"], ham), ham, ht)
        etiketler[r["sinif"]][r["klip"]] = (bool(r["etiket"]), r["bolum"])

    print(f"kaynak: {yol}\nsatir: {len(satirlar)}  hucre: {len(hucreler)}\n")

    # ------------------------------------------------ PROTOKOL BUTUNLUK KONTROLU
    # D40 KUSURU: vLLM eski `guided_choice` alanini SESSIZCE YOK SAYIYORDU ve
    # cikti serbest metne dusuyordu. Bu kontrol, kisitli kod cozmenin GERCEKTEN
    # baglayip baglamadigini VERIDEN dogrular: liste disi tek bir cevap bile varsa
    # o hucrenin olcumu SUPHELIDIR.
    dis = collections.Counter()
    hata_n = eksik = 0
    for r in satirlar:
        h = r.get("ham_cevap")
        if h is None:
            hata_n += 1
            continue
        if h.strip().upper() not in {s.upper() for s in SECENEK[r["sinif"]]}:
            dis[(r["sinif"], r["model"], r["cozunurluk"], h)] += 1
    # TEKIL klip sayisi (satir degil): yeniden baslatmalar birkac klibi iki kez
    # sormus olabilir; tekrar satirlari tamlik olcusunu SISIRMEMELI.
    bekl = {a: len(hucreler[a]) for a in hucreler}
    print("PROTOKOL BUTUNLUK: "
          + ("secenek listesi DISINDA cevap YOK -> kisitli kod cozme BAGLADI"
             if not dis else f"!! LISTE DISI {sum(dis.values())} cevap: {dict(dis)}"))
    print(f"  hata/bos cevap: {hata_n}  ·  hucre basina satir: "
          f"min={min(bekl.values())} maks={max(bekl.values())}")
    # TAMLIK: eksik hucre SESSIZCE puanlanmaz — acikca EKSIK diye yazilir.
    global EKSIK_HUCRE
    EKSIK_HUCRE = {a: bekl[a] for a in bekl if bekl[a] < BEKLENEN_N[a[0]]}
    if EKSIK_HUCRE:
        print(f"  !! EKSIK HUCRE {len(EKSIK_HUCRE)}: "
              + ", ".join(f"{s}@{c}/{m}={n}/{BEKLENEN_N[s]}"
                          for (s, m, c), n in sorted(EKSIK_HUCRE.items(), key=str))
              + "\n     -> bu hucrelerin sayilari TAMAMLANMAMIS kosumdandir, "
                "KARSILASTIRMADA KULLANILMAZ.")
    else:
        print("  tamlik: TUM hucreler tam (eksik klip yok)")
    kaynakli = collections.Counter(r.get("kaynak", "bu kosum") for r in satirlar)
    print(f"  satir kaynagi: {dict(kaynakli)}\n")

    # ---------------------------------------------------------- hucre tablolari
    ozet = {}
    for anahtar in sorted(hucreler):
        sinif, model, coz = anahtar
        klipler = sorted(hucreler[anahtar])
        for bol in ("tr", "te", "hepsi"):
            secili = [k for k in klipler
                      if bol == "hepsi" or etiketler[sinif][k][1] == bol]
            kay, ham = [], []
            for k in secili:
                kr, h, ht = hucreler[anahtar][k]
                kay.append((etiketler[sinif][k][0], kr, ht))
                ham.append(h)
            ana = tablo(kay)
            ikn = tablo(kay, ikincil=True)
            dej = dejenere(kay, ham)
            gecerli = sum(1 for x in kay if not x[2])
            ozet[(sinif, model, coz, bol)] = {
                "ana": ana, "ikincil": ikn, "dej": dej, "n_klip": len(secili),
                "karar_orani": round(ana["n"] / gecerli, 3) if gecerli else 0.0}

    # ------------------------------------------- coklu karsilastirma duzeltmesi
    # sinif ici etiket permutasyonu; TUM hucreler AYNI permutasyonla yeniden puanlanir
    random.seed(20260824)
    TEKRAR = int(os.environ.get("IZGARA_PERM", "10000"))
    # AILE TANIMI: coklu-karsilastirma duzeltmesi, SECIME GIREN hucrelerin
    # kumesi uzerinden yapilir. EKSIK (yarim kosulmus) hucreler secime giremez
    # (bkz. kullanilabilir()), bu yuzden AILEYE DE ALINMAZ — yoksa kucuk-n'li
    # yarim hucrelerin oynak MCC'si bos maks-dagilimini yapay olarak SISIRIR ve
    # duzeltmeyi hak edilmemis sekilde sertlestirir.
    tr_hucre = [a for a in hucreler
                if a not in EKSIK_HUCRE
                and any(etiketler[a[0]][k][1] == "tr" for k in hucreler[a])]
    sinif_klip = {}
    for s in etiketler:
        ks = sorted(k for k in etiketler[s] if etiketler[s][k][1] == "tr")
        sinif_klip[s] = (ks, [etiketler[s][k][0] for k in ks])

    hucre_karar = {}          # hucre -> [(klip_idx, karar)] yalniz KARAR VERILENLER
    for a in tr_hucre:
        s = a[0]
        ks = sinif_klip[s][0]
        idx = {k: i for i, k in enumerate(ks)}
        hucre_karar[a] = [(idx[k], hucreler[a][k][0]) for k in ks
                          if k in hucreler[a] and hucreler[a][k][0] is not None]

    def mcc_ile(a, et_vek):
        tp = fp = fn = tn = 0
        for i, kr in hucre_karar[a]:
            et = et_vek[i]
            if et and kr:
                tp += 1
            elif et:
                fn += 1
            elif kr:
                fp += 1
            else:
                tn += 1
        return mcc_sayim(tp, fp, fn, tn)

    gozlenen = {a: mcc_ile(a, sinif_klip[a[0]][1]) for a in tr_hucre}
    bos_maks = []
    bos_tek = {a: 0 for a in tr_hucre}
    for _ in range(TEKRAR):
        perm = {}
        for s, (ks, ev) in sinif_klip.items():
            v = list(ev)
            random.shuffle(v)
            perm[s] = v
        m = 0.0
        for a in tr_hucre:
            x = abs(mcc_ile(a, perm[a[0]]))
            m = max(m, x)
            if x >= abs(gozlenen[a]):
                bos_tek[a] += 1
        bos_maks.append(m)
    bos_maks.sort()
    esik95 = bos_maks[int(0.95 * TEKRAR)]
    print(f"COKLU KARSILASTIRMA (etiket permutasyonu, maks-istatistigi, "
          f"{TEKRAR} tekrar, {len(tr_hucre)} hucre)")
    print(f"  bos maks|MCC| dagilimi: medyan={bos_maks[TEKRAR//2]:.3f}  "
          f"%95={esik95:.3f}  %99={bos_maks[int(0.99*TEKRAR)]:.3f}  maks={bos_maks[-1]:.3f}")
    print(f"  -> bir hucre coklu karsilastirmaya RAGMEN gercek sayilmasi icin "
          f"MCC_tr >= {esik95:.3f} olmali\n")

    # ------------------------------------------------------------------ tablo
    def kullanilabilir(a):
        if a in EKSIK_HUCRE:      # tamamlanmamis hucre SECIME GIREMEZ
            return False
        o = ozet[(a[0], a[1], a[2], "tr")]
        return (not o["dej"]["dejenere"] and o["ana"]["mcc"] >= 0.40
                and o["karar_orani"] >= 0.70 and o["ana"]["ga95"][0] > 0.50
                and abs(gozlenen.get(a, 0.0)) >= esik95)

    for sinif in ("forklift", "yelek", "pano"):
        aday = sorted([a for a in hucreler if a[0] == sinif], key=lambda x: (x[1], x[2]))
        if not aday:
            continue
        print(f"{'='*104}\nSINIF {sinif.upper()}")
        for bol in ("tr", "te"):
            n0 = ozet[(aday[0][0], aday[0][1], aday[0][2], bol)]["n_klip"]
            etiket_bilgi = ("SECIM kumesi" if bol == "tr" else "TUTMA kumesi (MANSET)")
            print(f"\n  --- {bol.upper()} ({etiket_bilgi}) n={n0} ---")
            print(f"  {'model':10s} {'coz':>5s} | {'TP':>2s} {'FP':>2s} {'FN':>2s} {'TN':>2s} "
                  f"{'krsz':>4s} {'hata':>4s} | {'MCC':>7s} {'dog':>5s} {'Wilson95':>13s} "
                  f"{'kar_or':>6s} | {'ikincil_MCC':>11s} | durum")
            for a in aday:
                o = ozet[(a[0], a[1], a[2], bol)]
                e, ik = o["ana"], o["ikincil"]
                d = " DEJENERE" if o["dej"]["dejenere"] else ""
                ku = " [KULLANILABILIR]" if (bol == "tr" and kullanilabilir(a)) else ""
                print(f"  {a[1]:10s} {a[2]:>5d} | {e['tp']:2d} {e['fp']:2d} {e['fn']:2d} "
                      f"{e['tn']:2d} {e['kararsiz']:4d} {e['hata']:4d} | {e['mcc']:+7.3f} "
                      f"{e['dogruluk']:5.3f} [{e['ga95'][0]:.2f}-{e['ga95'][1]:.2f}] "
                      f"{o['karar_orani']:6.2f} | {ik['mcc']:+11.3f} |{d}{ku}")
            if bol == "tr":
                for a in aday:
                    o = ozet[(a[0], a[1], a[2], "tr")]
                    p_tek = (bos_tek[a] + 1) / (TEKRAR + 1) if a in bos_tek else None
                    print(f"    {a[1]:10s}@{a[2]:<5d} ham: {o['dej']['dagilim']}"
                          f"  (en sik {o['dej']['en_sik_oran']:.0%})"
                          + (f"  perm_p={p_tek:.4f}" if p_tek is not None else ""))
        # cozunurluk esli testleri (tr, ikincil ikilestirme -> her klipte tahmin var)
        cozs = sorted({a[2] for a in aday})
        if len(cozs) > 1:
            print(f"\n  --- {sinif} COZUNURLUK ESLI TESTI (tr, sahada-dagitim ikilestirmesi) ---")
            for model in sorted({a[1] for a in aday}):
                ks = sinif_klip[sinif][0]
                ev = dict(zip(ks, sinif_klip[sinif][1]))
                for i in range(len(cozs) - 1):
                    c1, c2 = cozs[i], cozs[i + 1]
                    a1, a2 = (sinif, model, c1), (sinif, model, c2)
                    if a1 not in hucreler or a2 not in hucreler:
                        continue
                    d1 = [(hucreler[a1][k][0] or False) == ev[k] for k in ks if k in hucreler[a1]]
                    d2 = [(hucreler[a2][k][0] or False) == ev[k] for k in ks if k in hucreler[a2]]
                    if len(d1) != len(d2):
                        continue
                    mc = mcnemar(d2, d1)   # b = c2 duzeltti, c = c2 bozdu
                    print(f"    {model:10s} {c1}->{c2}: duzeldi={mc['b']:2d} bozuldu={mc['c']:2d} "
                          f"McNemar p={mc['p']:.4f}"
                          + ("   <- GERCEK" if mc["p"] < 0.05 else "   (gurultu)"))
        print()

    # ------------------------------------------------- IZGARA MATRISI (ozet)
    print("=" * 104)
    print("IZGARA MATRISI — MCC (ANA tablo: yalniz KARAR VERILEN klipler)")
    print("  D=dejenere · *=coklu-karsilastirma esigini gecti · (kararsiz sayisi parantezde)")
    for bol in ("tr", "te"):
        print(f"\n  [{bol.upper()}] " + ("SECIM kumesi" if bol == "tr"
                                         else "TUTMA kumesi — MANSET"))
        print(f"  {'sinif':9s} {'model':10s} " +
              " ".join(f"{c:>18d}" for c in (768, 1280, 1920)))
        for sinif in ("forklift", "yelek", "pano"):
            for model in MODEL_SIRA:
                hucre_var = [(sinif, model, c) for c in (768, 1280, 1920)
                             if (sinif, model, c) in hucreler]
                if not hucre_var:
                    continue
                parcalar = []
                for c in (768, 1280, 1920):
                    a = (sinif, model, c)
                    if a not in hucreler:
                        parcalar.append(f"{'—':>18s}")
                        continue
                    o = ozet[(sinif, model, c, bol)]
                    im = "E" if a in EKSIK_HUCRE else ("D" if o["dej"]["dejenere"] else " ")
                    yz = ("*" if (bol == "tr" and abs(gozlenen.get(a, 0.0)) >= esik95)
                          else " ")
                    parcalar.append(
                        f"{o['ana']['mcc']:+7.3f}{im}{yz}(krsz{o['ana']['kararsiz']:2d})")
                print(f"  {sinif:9s} {model:10s} " + " ".join(parcalar))
    print("\n  [HEPSI] tr+te birlesik — YALNIZ eski olcumlerle KARSILASTIRMA icin;")
    print("          SECIMDE ve MANSETTE KULLANILMAZ (tr/te ayrimini bozar).")
    print(f"  {'sinif':9s} {'model':10s} " + " ".join(f"{c:>18d}" for c in (768, 1280, 1920)))
    for sinif in ("forklift", "yelek", "pano"):
        for model in MODEL_SIRA:
            if not any((sinif, model, c) in hucreler for c in (768, 1280, 1920)):
                continue
            parcalar = []
            for c in (768, 1280, 1920):
                a = (sinif, model, c)
                if a not in hucreler:
                    parcalar.append(f"{'—':>18s}")
                    continue
                o = ozet[(sinif, model, c, "hepsi")]
                im = "D" if o["dej"]["dejenere"] else " "
                parcalar.append(f"{o['ana']['mcc']:+7.3f}{im} (krsz{o['ana']['kararsiz']:2d})")
            print(f"  {sinif:9s} {model:10s} " + " ".join(parcalar))

    print("\nIZGARA MATRISI — ikincil SAHADA-DAGITIM MCC (kararsiz -> alarm yok)")
    for sinif in ("forklift", "yelek", "pano"):
        for model in MODEL_SIRA:
            if not any((sinif, model, c) in hucreler for c in (768, 1280, 1920)):
                continue
            parcalar = []
            for c in (768, 1280, 1920):
                a = (sinif, model, c)
                parcalar.append(f"{ozet[(sinif,model,c,'tr')]['ikincil']['mcc']:+8.3f}"
                                if a in hucreler else f"{'—':>8s}")
            print(f"  tr  {sinif:9s} {model:10s} " + " ".join(parcalar))
    print()

    # ------------------------------------------------------- sinif kazananlari
    print("=" * 104)
    print("SINIF KAZANANLARI (SECIM tr'de, on-kayittaki olcutle; berabere esigi 0,05 MCC)")
    for sinif in ("forklift", "yelek", "pano"):
        aday = [a for a in hucreler if a[0] == sinif]
        uygun = [a for a in aday if kullanilabilir(a)]
        if not uygun:
            print(f"  {sinif:9s}: KULLANILABILIR HUCRE YOK "
                  f"(en iyi MCC_tr={max((ozet[(a[0],a[1],a[2],'tr')]['ana']['mcc'] for a in aday), default=0):+.3f})")
            continue
        uygun.sort(key=lambda a: -ozet[(a[0], a[1], a[2], "tr")]["ana"]["mcc"])
        en = ozet[(uygun[0][0], uygun[0][1], uygun[0][2], "tr")]["ana"]["mcc"]
        berabere = [a for a in uygun
                    if en - ozet[(a[0], a[1], a[2], "tr")]["ana"]["mcc"] <= 0.05]
        print(f"  {sinif:9s}: {' = '.join(f'{a[1]}@{a[2]}' for a in berabere)}  "
              f"MCC_tr={en:+.3f}" + ("  (berabere)" if len(berabere) > 1 else ""))
        for a in berabere:
            t = ozet[(a[0], a[1], a[2], "te")]
            e = t["ana"]
            print(f"      MANSET (te, n={t['n_klip']}): {a[1]}@{a[2]}  "
                  f"TP={e['tp']} FP={e['fp']} FN={e['fn']} TN={e['tn']} "
                  f"kararsiz={e['kararsiz']} hata={e['hata']}  MCC={e['mcc']:+.3f} "
                  f"dog={e['dogruluk']:.3f} Wilson95=[{e['ga95'][0]:.2f}-{e['ga95'][1]:.2f}]"
                  + ("  ** n KUCUK: te TEK BASINA KARAR VERDIRMEZ **" if t["n_klip"] < 30 else ""))
    print()


if __name__ == "__main__":
    main()
