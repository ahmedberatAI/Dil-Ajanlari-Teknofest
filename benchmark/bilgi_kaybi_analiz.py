#!/usr/bin/env python
"""D43 — bilgi_kaybi_prob.py ciktilarini K1/K2/K3 asamalarina AYIRIR ve sayar.

    python benchmark/bilgi_kaybi_analiz.py --boru <boru.json> \
        --islemsel <a.json> [<b.json> ...] --islemsel-ad "kacisli"

UC OLCUM KATMANI (hepsi AYNI klip kumesinde, yan yana):

 SOZCUKSEL (labels.isg_match) : boru hattinin gercekte puanlandigi kapi.
     desc'e, events'e ve events+summary'ye AYRI AYRI uygulanir.
 BOLUM-FARKINDA SOZCUKSEL : ayni kapi, ama betimlemenin "1) Ortam ve Beklenen
     Normal" bolumu ATILDIKTAN sonra. Cunku model her betimlemeye
     "bu alanda forkliftlerin yuk tasimasi ... olagandir" diye basliyor ve
     ISG kalibi ("yuk tasi") BU RUTIN CUMLEYE takiliyor — yani ham desc
     eslesmesi tehlikeyi DEGIL, sablonu olcuyor.
 ISLEMSEL KANIT : sinif ciftinin GOZLEMLENEBILIR olcutu metinde ANILIYOR mu?
     (kasa/istif sayisi · yelek/KKD · pano kapagi · yaya seridi). Ihlal
     IDDIASI gerektirmez; modelin DOGRU YERE BAKIP BAKMADIGINI olcer.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from benchmark.labels import ISG_SINIFLAR, isg_match, tr_lower  # noqa: E402
from benchmark.labels import _cumlecikler, _kalip_konumlari      # noqa: E402

CIFT_SINIF = {"forklift": "Carrying_Overload_with_Forklift",
              "yetki": "Unauthorized_Intervention",
              "pano": "Opened_Panel_Cover",
              "yol": "Safe_Walkway_Violation"}
CIFTLER = ("forklift", "yetki", "pano", "yol")

# --- ISLEMSEL KANIT KALIPLARI ---------------------------------------------
# "Model dogru YERE bakti mi?" — ihlal IDDIASI gerektirmez.
# forklift'te YALIN "yuk" BILEREK YOK: her betimlemenin rutin cumlesinde geciyor
# ("forkliftlerin yuk tasimasi olagandir") -> olcum sisirir. Olcut SAYIM/ISTIFTIR.
ISLEMSEL_KANIT = {
    "forklift": [r"kasa", r"blok", r"palet", r"koli", r"kutu", r"istif", r"üst üste",
                 r"yığ", r"çatal", r"catal", r"\d+\s*(adet\s*)?(kasa|kutu|palet|blok)"],
    "yetki": [r"yelek", r"reflekt", r"baret", r"kask", r"kkd",
              r"koruyucu (donan|ekip|kıyaf)", r"yetkisiz", r"izinsiz"],
    "pano": [r"pano", r"elektrik dolab", r"kontrol kutu", r"kapa[ğg]ı", r"kapak",
             r"terminal", r"sigorta"],
    "yol": [r"yaya", r"yürüme yolu", r"yürüyüş yolu", r"şerit", r"serit",
            r"sarı çizg", r"sari cizg", r"işaretli yol", r"isaretli yol",
            r"yol çizg", r"yol dış"],
}
_KANIT_RE = {k: re.compile("|".join(v)) for k, v in ISLEMSEL_KANIT.items()}

# Betimlemenin RUTIN ("1) Ortam ve Beklenen Normal") bolumunu kesip atmak icin.
_SAPMA_BAS = re.compile(r"\*{0,2}\s*#{0,4}\s*\*{0,2}\s*2\s*\)?\s*[\.\-–]?\s*sapma", re.I)


def kanit_var(cift: str, metin: str) -> bool:
    return bool(_KANIT_RE[cift].search(tr_lower(metin or "")))


def sapma_bolumu(desc: str) -> str:
    """Betimlemenin '2) Sapmalar' ve sonrasi. Bulunamazsa metnin tamami."""
    m = _SAPMA_BAS.search(desc or "")
    return desc[m.start():] if m else (desc or "")


def eslesen_kaliplar(metin: str, sinif: str):
    hit = []
    for k in ISG_SINIFLAR[sinif]["kaliplar"]:
        for c in _cumlecikler(tr_lower(metin or "")):
            if _kalip_konumlari(c, tr_lower(k)):
                hit.append(k)
                break
    return hit


def _birlesik(r, alan):
    if alan == "desc":
        return "\n".join(r.get("desc") or [])
    if alan == "desc_sapma":
        return "\n".join(sapma_bolumu(d) for d in (r.get("desc") or []))
    if alan == "events":
        return "\n".join(e["event"] for e in (r.get("events") or []))
    if alan == "events_summary":
        return "\n".join([e["event"] for e in (r.get("events") or [])]
                         + ([r.get("summary")] if r.get("summary") else []))
    raise ValueError(alan)


def mcc(tp, fp, fn, tn):
    p = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return (tp * tn - fp * fn) / p if p else 0.0


# =============================================================== A KOLU ANALIZI
def analiz_boru(satirlar):
    print("\n" + "=" * 92)
    print("A KOLU — MEVCUT SERBEST-METIN BORU HATTI   (n=%d klip)" % len(satirlar))
    print("=" * 92)
    ihlal = [r for r in satirlar if r["ihlal"]]
    normal = [r for r in satirlar if not r["ihlal"]]
    n = len(ihlal)

    print("\nGUVENSIZ KLIPLER — asama asama (True = bilgi O ASAMADA VAR)")
    print(f"{'klip':<14}{'cift':<10}{'olay':>5}{'K1kanit':>9}{'K1desc':>8}"
          f"{'K1sapma':>9}{'K2olay':>8}{'K3olay+ozet':>12}   eslesen_kalip(desc)")
    s = dict(kanit=0, desc=0, sapma=0, olay=0, oo=0)
    for r in ihlal:
        sinif = CIFT_SINIF[r["cift"]]
        d, ds = _birlesik(r, "desc"), _birlesik(r, "desc_sapma")
        ev, eo = _birlesik(r, "events"), _birlesik(r, "events_summary")
        a, b, c, e, f = (kanit_var(r["cift"], d), isg_match(d, sinif),
                         isg_match(ds, sinif), isg_match(ev, sinif),
                         isg_match(eo, sinif))
        for k, v in zip(("kanit", "desc", "sapma", "olay", "oo"), (a, b, c, e, f)):
            s[k] += bool(v)
        print(f"{os.path.basename(r['yol']):<14}{r['cift']:<10}"
              f"{len(r.get('events') or []):>5}{str(a):>9}{str(b):>8}{str(c):>9}"
              f"{str(e):>8}{str(f):>12}   {eslesen_kaliplar(d, sinif)}")

    print(f"\n  TOPLAM (n={n} guvensiz klip)")
    print(f"    K1-a  betimleme dogru YERE bakti (islemsel kanit anildi) : {s['kanit']:>2}/{n}")
    print(f"    K1-b  betimleme HAM metni ISG kalibiyla esliyor          : {s['desc']:>2}/{n}")
    print(f"    K1-c  ... rutin ('Beklenen Normal') bolumu ATILINCA      : {s['sapma']:>2}/{n}")
    print(f"    K2    OLAY listesi ISG kalibiyla esliyor                 : {s['olay']:>2}/{n}")
    print(f"    K3    olay+ozet (uretimde PUANLANAN alan) = isg_ozgul    : {s['oo']:>2}/{n}")

    sifir = [r for r in ihlal if not (r.get("events") or [])]
    sapma_yok = [r for r in ihlal
                 if re.search(r"sapma\s*yok", tr_lower(_birlesik(r, "desc")))]
    print(f"\n    boru hatti SIFIR olay uretti                            : {len(sifir):>2}/{n}")
    print(f"    betimleme acikca 'SAPMA YOK' dedi                       : {len(sapma_yok):>2}/{n}")

    print("\n  OZGULLUK (GUVENLI es siniflar):")
    yp = sum(isg_match(_birlesik(r, "events_summary"), CIFT_SINIF[r["cift"]])
             for r in normal)
    yp_olay = sum(1 for r in normal if (r.get("events") or []))
    print(f"    isg_match yanlis pozitif : {yp}/{len(normal)}")
    print(f"    HERHANGI bir olay uretti : {yp_olay}/{len(normal)}")

    print("\n  CIFT BAZINDA (guvensiz n=5/cift):")
    print(f"    {'cift':<10}{'K1kanit':>9}{'K1desc':>8}{'K1sapma':>9}{'K2':>5}{'K3':>5}"
          f"{'top.olay':>10}")
    for c in CIFTLER:
        g = [r for r in ihlal if r["cift"] == c]
        if not g:
            continue
        sn = CIFT_SINIF[c]
        print(f"    {c:<10}"
              f"{sum(kanit_var(c, _birlesik(r,'desc')) for r in g):>9}"
              f"{sum(isg_match(_birlesik(r,'desc'), sn) for r in g):>8}"
              f"{sum(isg_match(_birlesik(r,'desc_sapma'), sn) for r in g):>9}"
              f"{sum(isg_match(_birlesik(r,'events'), sn) for r in g):>5}"
              f"{sum(isg_match(_birlesik(r,'events_summary'), sn) for r in g):>5}"
              f"{sum(len(r.get('events') or []) for r in g):>10}")
    return {"n": n, "n_normal": len(normal), **s, "yp": yp}


# =============================================================== B KOLU ANALIZI
def yeniden_uret(satirlar):
    """B kolunun MEKANIK K1 sozlesmesini KAYITLI ham cevaptan YENIDEN kurar.

    Neden: sablon metin kosum aninda yazildi ve ilk surumu ASCII idi
    ("yetkisiz mudahale"), `isg_match` ise diakritikli kalip ariyor
    ("yetkisiz müdahale") -> 5 dogru karar SESSIZCE kayboluyordu. Sablonu
    tek yerde (bilgi_kaybi_prob.ISLEMSEL) tutup burada yeniden uretmek,
    puanlamayi kosum anindaki yazim kazasindan bagimsiz kilar.
    """
    from benchmark.bilgi_kaybi_prob import ISLEMSEL
    for r in satirlar:
        cfg = ISLEMSEL[r["cift"]]
        if r.get("karar") is True:
            n = re.findall(r"\d+", r.get("ham") or "")
            metin = cfg["olay"].format(c=n[-1] if n else "3+")
            r["events"] = [{"time": "00:00", "event": metin,
                            "severity": cfg["severity"], "category": cfg["kategori"]}]
            r["summary"] = metin + "."
        else:
            r["events"] = []
            r["summary"] = ("Islemsel kontrolde ihlal olcutu saglanmadi."
                            if r.get("karar") is False else
                            "Islemsel kontrol karar veremedi.")
    return satirlar


def analiz_islemsel(satirlar, ad):
    print("\n" + "=" * 92)
    print(f"B KOLU — ISLEMSEL SORU -> MEKANIK K1   [{ad}]   (n=%d klip)" % len(satirlar))
    print("=" * 92)
    ihlal = [r for r in satirlar if r["ihlal"]]
    normal = [r for r in satirlar if not r["ihlal"]]
    tp = sum(1 for r in ihlal
             if isg_match(_birlesik(r, "events_summary"), CIFT_SINIF[r["cift"]]))
    fp = sum(1 for r in normal
             if isg_match(_birlesik(r, "events_summary"), CIFT_SINIF[r["cift"]]))
    karar = sum(1 for r in satirlar if r.get("karar") in (True, False))
    print(f"    isg_ozgul (guvensizde sozcuksel isabet) : {tp}/{len(ihlal)}")
    print(f"    yanlis pozitif (guvenli es sinif)       : {fp}/{len(normal)}")
    print(f"    KARAR ORANI (kacmadan cevap)            : {karar}/{len(satirlar)}")
    print(f"\n    {'cift':<10}{'model':<12}{'TP/n':>8}{'FP/n':>8}{'MCC':>8}"
          f"{'karar':>8}   ham cevaplar")
    for c in CIFTLER:
        gi = [r for r in ihlal if r["cift"] == c]
        gn = [r for r in normal if r["cift"] == c]
        if not gi and not gn:
            continue
        t = sum(1 for r in gi if r.get("karar") is True)
        f_ = sum(1 for r in gn if r.get("karar") is True)
        fn_ = len(gi) - t
        tn = len(gn) - f_
        kr = sum(1 for r in gi + gn if r.get("karar") in (True, False))
        mdl = (gi + gn)[0].get("model", "?")
        print(f"    {c:<10}{mdl:<12}{f'{t}/{len(gi)}':>8}{f'{f_}/{len(gn)}':>8}"
              f"{mcc(t, f_, fn_, tn):>8.3f}{f'{kr}/{len(gi)+len(gn)}':>8}   "
              + " ".join(str(r["ham"]) for r in gi) + " | "
              + " ".join(str(r["ham"]) for r in gn))
    return {"tp": tp, "n": len(ihlal), "fp": fp, "n_normal": len(normal),
            "karar": karar, "toplam": len(satirlar), "ad": ad}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boru", required=True)
    ap.add_argument("--islemsel", nargs="*", default=[],
                    help="'ad=dosya' ciftleri; ayni ad'li dosyalar BIRLESTIRILIR")
    a = ap.parse_args()

    b = json.load(open(a.boru, encoding="utf-8"))
    print("BORU KUNYESI:", json.dumps(b.get("kunye"), ensure_ascii=False))
    ozet_a = analiz_boru(b["satirlar"])

    gruplar = {}
    for spec in a.islemsel:
        ad, _, yol = spec.partition("=")
        if not yol:
            ad, yol = "islemsel", ad
        d = json.load(open(yol, encoding="utf-8"))
        gruplar.setdefault(ad, []).extend(d["satirlar"])

    ozetler = [analiz_islemsel(yeniden_uret(v), k) for k, v in gruplar.items()]

    if ozetler:
        print("\n" + "=" * 92)
        print("YAN YANA — AYNI 30 KLIP, AYNI ESLESTIRICI (isg_match)")
        print("=" * 92)
        print("  {:<44}{:>12}{:>12}{:>10}".format(
            "mimari", "isg_ozgul", "yanlis_poz", "karar"))
        print("  {:<44}{:>12}{:>12}{:>10}".format(
            "A serbest metin boru hatti (mevcut)",
            "{}/{}".format(ozet_a["oo"], ozet_a["n"]),
            "{}/{}".format(ozet_a["yp"], ozet_a["n_normal"]),
            "{}/{}".format(ozet_a["n"] + ozet_a["n_normal"],
                           ozet_a["n"] + ozet_a["n_normal"])))
        for o in ozetler:
            print("  {:<44}{:>12}{:>12}{:>10}".format(
                "B islemsel boru hatti [{}]".format(o["ad"]),
                "{}/{}".format(o["tp"], o["n"]),
                "{}/{}".format(o["fp"], o["n_normal"]),
                "{}/{}".format(o["karar"], o["toplam"])))


if __name__ == "__main__":
    main()
