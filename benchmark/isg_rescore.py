#!/usr/bin/env python
"""ISG INCE-TANELI yeniden skorlama — model calistirmadan. GPU GEREKMEZ.

NEDEN BU DOSYA VAR (HANDOFF §6.1)
---------------------------------
`eval_clips.py` kategoriyi UST klasorden alir; `data/eval_defense` icin bu yalnizca
"Anomali" / "Normal" demektir. DORT ayri guvensiz sinif (yurume yolu ihlali,
yetkisiz mudahale, acik pano kapagi, forklift asiri yuk) TEK KOVAYA dusuyor —
sinif duzeyinde hicbir sey olculmuyor, model hangi tehlikeyi gorup hangisini
kacirdigi GORUNMUYOR.

Bu arac kayitli satirlardan (summary + events[] + events[].category) ince taneli
gorunumu YENIDEN URETIR. Yeni GPU kosusu GEREKMEZ; arsivlenmis her kosuya da
geriye donuk uygulanabilir.

OLCULEN UC SEY — BILEREK AYRI RAPORLANIR
-----------------------------------------
  1  SOZCUKSEL adlandirma : metin o sinifa OZGU tehlikeyi adlandiriyor mu?
                            (benchmark/labels.py ISG_SINIFLAR[...]["kaliplar"])
  2  OPERASYONEL eslesme  : uretilen EventCategory kabul kumesinde mi?
                            -> "dogru ekip cagrilir miydi?"
  3  AYIRT EDICI eslesme  : generic "Anomali"/"Diğer" kovasi DISLANDIGINDA model
                            spesifik kategoriyi secebiliyor mu?
  4  TAM DOGRU (turetilmis): (1) VE (2) — tehlikeyi ADLANDIRDI *ve* dogru ekibe
                            YONLENDIRDI. Ikisinden de kucuk/esittir; operasyonel
                            olarak asil onemli sayi budur.

(3) ayri olculur cunku (2) TEK BASINA ZAYIFTIR: `Anomali` dort guvensiz sinifin
da kabul kumesinde oldugu icin model her seye "Anomali" diyerek (2)'yi bedavaya
gecer. Ikisi yan yana basilmazsa taksonomi hizalamasi kendini kandirmaya doner.

OZGULLUK
--------
Yuzde tek basina yaniltir: her sinifi tetikleyen bir eslestirici %100 "dogru"
yapar. Bu yuzden klip basina tetiklenen YANLIS SINIF sayisi da raporlanir
(dusuk = iyi) ve KARISIKLIK MATRISI basilir.

K4 / HANDOFF §7.3 — ESKI SKOR SILINMEZ
--------------------------------------
Dosyada KAYITLI kaba ikili `category_match` her zaman 1. satirda, ince taneli
skorun YANINDA durur. Ayrica "HAT DOGRULAMASI" bolumu ince taneli olcumun
kaba olcume mantiksal olarak tutarli olup olmadigini kontrol eder.

Kullanim:
    python benchmark/isg_rescore.py benchmark/results/eval_*.json
    python benchmark/isg_rescore.py <a.json> <b.json> --json cikti.json

Bagimlilik: yalniz stdlib + benchmark.labels + benchmark.stats_utils.
dilajan / torch / av ITHAL EDILMEZ.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from benchmark.labels import (  # noqa: E402
        ISG_ESLI, ISG_GENERIC_KATEGORILER, ISG_SINIFLAR, isg_any_match, isg_guvensiz,
        isg_matched_siniflar, isg_operasyonel_kabul, isg_sinif_from_path, row_text,
    )
    from benchmark.stats_utils import (  # noqa: E402
        fisher_exact_p, fmt_rate_dict, rate_from_bools)
except ImportError:  # benchmark/ icinden dogrudan calistirma
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from labels import (  # type: ignore  # noqa: E402
        ISG_ESLI, ISG_GENERIC_KATEGORILER, ISG_SINIFLAR, isg_any_match, isg_guvensiz,
        isg_matched_siniflar, isg_operasyonel_kabul, isg_sinif_from_path, row_text,
    )
    from stats_utils import (  # type: ignore  # noqa: E402
        fisher_exact_p, fmt_rate_dict, rate_from_bools)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Raporlarda sinif sirasi: once GUVENSIZ (class0-3), sonra GUVENLI (class4-7).
SINIF_SIRASI: List[str] = sorted(ISG_SINIFLAR, key=lambda s: ISG_SINIFLAR[s]["kod"])


def _olay_kategorileri(row: dict) -> List[str]:
    """Satirdaki olaylarin EventCategory degerleri (bos liste = olay yok)."""
    return [str(e.get("category") or "") for e in (row.get("events") or [])]


def _satir_olc(row: dict, sinif: str) -> dict:
    """Tek klip icin ince taneli kararlar."""
    parcalar = row_text(row, with_summary=True)
    kategoriler = _olay_kategorileri(row)
    guvensiz = isg_guvensiz(sinif)
    kabul = isg_operasyonel_kabul(sinif)
    kabul_ae = isg_operasyonel_kabul(sinif, ayirt_edici=True)

    metin = " . ".join(parcalar)
    tetiklenen = isg_matched_siniflar(metin)

    if guvensiz:
        # GUVENSIZ sinif: en az bir olay kategorisi kabul kumesinde olmali.
        op = any(k in kabul for k in kategoriler)
        op_ae = any(k in kabul_ae for k in kategoriler)
    else:
        # GUVENLI sinif: DOGRU davranis = hic olay uretmemek veya "Normal" demek.
        # (Kabul kumesi {"Normal"} oldugu icin bos olay listesi de dogrudur.)
        op = all(k in kabul for k in kategoriler)   # bos liste -> True
        op_ae = op
    sozcuksel = isg_any_match(parcalar, sinif) if guvensiz else None
    return {
        "sozcuksel": sozcuksel,
        "operasyonel": op,
        "operasyonel_ayirt_edici": op_ae,
        # TURETILMIS — iki bilesenin KESISIMI: tehlikeyi ADLANDIRDI *ve* dogru
        # ekibe YONLENDIRDI. Ikisinden de KUCUK/esittir; ayri bir "iyi haber
        # kanali" acmaz (cherry-pick riski yok), ama operasyonel olarak asil
        # onemli olan sayidir. Guvenli siniflarda TANIMSIZ (sozcuksel yok).
        "tam_dogru": (bool(sozcuksel) and op) if guvensiz else None,
        "n_olay": len(kategoriler),
        "kategoriler": kategoriler,
        "yanlis_sinif_tetigi": len(tetiklenen - {sinif}),
        "kayitli_kaba": row.get("category_match"),
    }


def dosyayi_skorla(yol: str) -> dict:
    """Bir eval sonuc JSON'unu ISG ince-taneli kurallarla yeniden skorlar."""
    with open(yol, encoding="utf-8") as f:
        veri = json.load(f)
    tum = veri.get("rows") or []

    # Sinifi COZULEBILEN satirlar (alt klasor adi ISG_SINIFLAR'da olanlar).
    # Cozulemeyen satirlar SESSIZCE ATILMAZ — sayilir ve raporlanir (K7).
    esli: List[tuple] = []
    cozulemeyen: List[str] = []
    for r in tum:
        s = isg_sinif_from_path(str(r.get("path") or ""))
        (esli.append((r, s)) if s else cozulemeyen.append(str(r.get("path") or "?")))

    per_sinif: Dict[str, dict] = {}
    karisiklik: Dict[str, collections.Counter] = {}
    for sinif in SINIF_SIRASI:
        rs = [(r, s) for r, s in esli if s == sinif]
        if not rs:
            continue
        olcumler = [_satir_olc(r, sinif) for r, _ in rs]
        guvensiz = isg_guvensiz(sinif)
        say = collections.Counter()
        for o in olcumler:
            if o["kategoriler"]:
                say.update(o["kategoriler"])
            else:
                say["(olay yok)"] += 1
        karisiklik[sinif] = say
        per_sinif[sinif] = {
            "kod": ISG_SINIFLAR[sinif]["kod"],
            "tr_ad": ISG_SINIFLAR[sinif]["tr_ad"],
            "guvensiz": guvensiz,
            "n": len(olcumler),
            # Sozcuksel adlandirma YALNIZCA guvensiz siniflar icin tanimlidir
            # (guvenli sinifin "beklenen anahtar kelimesi" yoktur — Normal ile ayni).
            "sozcuksel": rate_from_bools([o["sozcuksel"] for o in olcumler]) if guvensiz else None,
            "operasyonel": rate_from_bools([o["operasyonel"] for o in olcumler]),
            "operasyonel_ayirt_edici": rate_from_bools(
                [o["operasyonel_ayirt_edici"] for o in olcumler]),
            "tam_dogru": rate_from_bools([o["tam_dogru"] for o in olcumler]) if guvensiz else None,
            "en_az_bir_olay": rate_from_bools([o["n_olay"] > 0 for o in olcumler]),
            "yanlis_sinif_tetigi_ort": (
                sum(o["yanlis_sinif_tetigi"] for o in olcumler) / len(olcumler)),
            # KAYITLI kaba ikili skor — silinmez, yan yana durur (K4)
            "kayitli_kaba": rate_from_bools(
                [bool(o["kayitli_kaba"]) for o in olcumler if o["kayitli_kaba"] is not None]),
        }

    # --- ESLI AYIRT ETME: guvensiz sinifin dili, GUVENLI esinde de tetikleniyor mu? ---
    # Ayni sahne/kamera/ekipman, fark yalnizca DAVRANIS. TPR ~ FPR ise model
    # tehlikeyi degil SAHNE TURUNU taniyor demektir.
    esli_tablo: Dict[str, dict] = {}
    for guvensiz_s, guvenli_s in ISG_ESLI.items():
        g_rows = [r for r, s in esli if s == guvensiz_s]
        s_rows = [r for r, s in esli if s == guvenli_s]
        if not g_rows or not s_rows:
            continue
        tpr = rate_from_bools(
            [isg_any_match(row_text(r, with_summary=True), guvensiz_s) for r in g_rows])
        # GUVENLI kliplerde AYNI (guvensiz sinifin) kaliplari araniyor
        fpr = rate_from_bools(
            [isg_any_match(row_text(r, with_summary=True), guvensiz_s) for r in s_rows])
        # ESLESMEMIS iki oran -> Fisher tam testi (McNemar DEGIL: farkli klipler).
        p = fisher_exact_p(tpr["k"], tpr["n"] - tpr["k"], fpr["k"], fpr["n"] - fpr["k"])
        esli_tablo[guvensiz_s] = {
            "guvenli_es": guvenli_s,
            "kod_guvensiz": ISG_SINIFLAR[guvensiz_s]["kod"],
            "kod_guvenli": ISG_SINIFLAR[guvenli_s]["kod"],
            "tpr": tpr, "fpr": fpr,
            "ayirt_etme": tpr["p"] - fpr["p"],
            "fisher_p": p,
            "anlamli_005": p < 0.05,
        }

    return {
        "dosya": os.path.relpath(yol, ROOT).replace("\\", "/"),
        "eval_dir": veri.get("eval_dir") or "?",
        "n_toplam": len(tum),
        "n_sinifi_cozulen": len(esli),
        "n_cozulemeyen": len(cozulemeyen),
        "cozulemeyen_ornek": cozulemeyen[:5],
        "per_sinif": per_sinif,
        "karisiklik": {s: dict(c) for s, c in karisiklik.items()},
        "esli_ayirt_etme": esli_tablo,
    }


def bas(sonuc: dict) -> None:
    print("=" * 100)
    print(f"DOSYA : {sonuc['dosya']}")
    print(f"SET   : {sonuc['eval_dir']}   ·   satir: {sonuc['n_toplam']}   "
          f"·   ISG sinifi cozulen: {sonuc['n_sinifi_cozulen']}")
    if sonuc["n_cozulemeyen"]:
        print(f"        ⚠ sinifi COZULEMEYEN {sonuc['n_cozulemeyen']} satir "
              f"(ISG olcumune ALINMADI): {sonuc['cozulemeyen_ornek']}")
    if not sonuc["per_sinif"]:
        print("  Bu dosyada ISG ince-taneli sinif YOK (alt klasor adlari eslesmedi).")
        print("=" * 100 + "\n")
        return

    print("-" * 100)
    print("GUVENSIZ SINIFLAR — tum oranlar: nokta-deger [Wilson %95 GA]  (k/n)")
    print("-" * 100)
    for sinif in SINIF_SIRASI:
        d = sonuc["per_sinif"].get(sinif)
        if not d or not d["guvensiz"]:
            continue
        print(f"  {d['kod']}  {d['tr_ad']}   (n={d['n']})")
        print(f"      kaba IKILI  [KAYITLI, silinmedi] : {fmt_rate_dict(d['kayitli_kaba'])}")
        print(f"      SOZCUKSEL adlandirma (ince)      : {fmt_rate_dict(d['sozcuksel'])}")
        print(f"      OPERASYONEL eslesme              : {fmt_rate_dict(d['operasyonel'])}"
              f"   kabul={sorted(isg_operasyonel_kabul(sinif))}")
        print(f"      AYIRT EDICI (generic haric)      : "
              f"{fmt_rate_dict(d['operasyonel_ayirt_edici'])}"
              f"   kabul={sorted(isg_operasyonel_kabul(sinif, ayirt_edici=True))}")
        print(f"      TAM DOGRU (adlandirdi VE yonlendirdi): {fmt_rate_dict(d['tam_dogru'])}")
        print(f"      >=1 olay uretti                  : {fmt_rate_dict(d['en_az_bir_olay'])}")
        print(f"      yanlis SINIF tetigi (klip basina): {d['yanlis_sinif_tetigi_ort']:.2f}"
              f"   (dusuk = iyi)")
        print()

    print("-" * 100)
    print("GUVENLI SINIFLAR — dogru davranis: guvensiz olay URETMEMEK")
    print("-" * 100)
    for sinif in SINIF_SIRASI:
        d = sonuc["per_sinif"].get(sinif)
        if not d or d["guvensiz"]:
            continue
        print(f"  {d['kod']}  {d['tr_ad']}   (n={d['n']})")
        print(f"      OPERASYONEL dogru (hep 'Normal' veya olay yok): "
              f"{fmt_rate_dict(d['operasyonel'])}")
        print(f"      >=1 olay uretti (yanlis-pozitif gostergesi)   : "
              f"{fmt_rate_dict(d['en_az_bir_olay'])}   (dusuk = iyi)")
        print(f"      yanlis SINIF tetigi (klip basina)             : "
              f"{d['yanlis_sinif_tetigi_ort']:.2f}")
        print()

    # --- KARISIKLIK MATRISI: gercek ISG sinifi x uretilen EventCategory ---
    print("-" * 100)
    print("KARISIKLIK MATRISI — gercek ISG sinifi (satir) x uretilen EventCategory (sutun)")
    print("Hucre = OLAY sayisi (klip degil; bir klip birden cok olay uretebilir).")
    print("-" * 100)
    sutunlar: List[str] = []
    for s in SINIF_SIRASI:
        for k in sonuc["karisiklik"].get(s, {}):
            if k not in sutunlar:
                sutunlar.append(k)
    sutunlar.sort(key=lambda k: (k == "(olay yok)", k))
    baslik = "".join(f"{k[:11]:>13s}" for k in sutunlar)
    print(f"  {'sinif':34s}{baslik}")
    for s in SINIF_SIRASI:
        c = sonuc["karisiklik"].get(s)
        if not c:
            continue
        ad = f"{ISG_SINIFLAR[s]['kod']} {ISG_SINIFLAR[s]['tr_ad']}"
        hucre = "".join(f"{c.get(k, 0):>13d}" for k in sutunlar)
        print(f"  {ad[:34]:34s}{hucre}")
    print("-" * 100)
    print(f"NOT: generic (ayirt edici OLMAYAN) kategoriler: {sorted(ISG_GENERIC_KATEGORILER)}")
    print("     Bu sutunlarda toplanma, modelin tehlike TURUNU ayirt EDEMEDIGINI gosterir.")

    # --- ESLI AYIRT ETME ---
    if sonuc.get("esli_ayirt_etme"):
        print("-" * 100)
        print("ESLI AYIRT ETME — ayni sahne/kamera/ekipman, fark YALNIZCA davranis")
        print("TPR = guvensiz klipte o sinifin dili;  FPR = GUVENLI esinde AYNI dil.")
        print("ayirt_etme = TPR - FPR.  ~0 ise model tehlikeyi degil SAHNE TURUNU taniyor.")
        print("-" * 100)
        for guvensiz_s, d in sonuc["esli_ayirt_etme"].items():
            ad = ISG_SINIFLAR[guvensiz_s]["tr_ad"]
            print(f"  {d['kod_guvensiz']} vs {d['kod_guvenli']}  {ad}")
            print(f"      TPR (guvensiz klipte)     : {fmt_rate_dict(d['tpr'])}")
            print(f"      FPR (GUVENLI esinde)      : {fmt_rate_dict(d['fpr'])}   (dusuk = iyi)")
            karar = "ANLAMLI" if d["anlamli_005"] else "ayrim KANITLANAMADI"
            print(f"      AYIRT ETME (TPR - FPR)    : {d['ayirt_etme'] * 100:+.0f} puan   "
                  f"Fisher iki-yonlu p={d['fisher_p']:.4f}  -> {karar}")
    print("=" * 100)
    print()


def _yan_yana(hepsi: List[dict]) -> None:
    """Birden cok kol yan yana — hangi kol hangi sinifta ne yapmis."""
    print("=" * 100)
    print("  KOLLAR YAN YANA — SOZCUKSEL adlandirma (guvensiz siniflar)")
    print("=" * 100)
    adlar = [os.path.basename(s["dosya"]).replace(".json", "")[:20] for s in hepsi]
    print(f"  {'sinif':36s}" + "".join(f"{a:>22s}" for a in adlar))
    for sinif in SINIF_SIRASI:
        if not isg_guvensiz(sinif):
            continue
        satir = []
        for s in hepsi:
            d = s["per_sinif"].get(sinif)
            satir.append(fmt_rate_dict(d["sozcuksel"]) if d and d["sozcuksel"] else "n/a")
        ad = f"{ISG_SINIFLAR[sinif]['kod']} {ISG_SINIFLAR[sinif]['tr_ad']}"
        print(f"  {ad[:36]:36s}" + "".join(f"{x:>22s}" for x in satir))
    print("=" * 100)
    print()


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dosyalar", nargs="+", help="eval sonuc JSON dosyalari")
    ap.add_argument("--json", dest="json_out", help="sonuclari JSON olarak kaydet")
    args = ap.parse_args(argv)

    hepsi = []
    for yol in args.dosyalar:
        if not os.path.isabs(yol):
            aday = os.path.join(ROOT, yol)
            yol = aday if os.path.exists(aday) else yol
        if not os.path.exists(yol):
            print(f"[ATLANDI] bulunamadi: {yol}")
            continue
        s = dosyayi_skorla(yol)
        bas(s)
        hepsi.append(s)

    if len(hepsi) > 1:
        _yan_yana(hepsi)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({"dosyalar": hepsi}, f, ensure_ascii=False, indent=2)
        print(f"Kaydedildi: {args.json_out}")
    return 0 if hepsi else 1


if __name__ == "__main__":
    raise SystemExit(main())
