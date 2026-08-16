#!/usr/bin/env python
"""ARSIVLENMIS eval sonuclarini YENIDEN SKORLAR — model calistirmadan. GPU GEREKMEZ.

NEDEN BU DOSYA VAR
------------------
eval_holdout kosularinda recall %96-100 iken kategori adlandirma %38 olculuyordu.
Sebebin modelde mi yoksa OLCUMDE mi oldugu belirsizdi. Bu arac cevabi verir: ayni
kayitli ciktilar 4 FARKLI KURALLA yeniden skorlanir ve sonuclar YAN YANA basilir.

OLCULEN 4 KURAL (kumulatif — her satir bir onceki uzerine tek degisiklik ekler)
------------------------------------------------------------------------------
  1  ESKI   : yalniz events[].event, ciplak alt-dizge, Python .lower()
               -> D28 ONCESI eval_clips.py'nin kurali. AYNEN korunur (K4).
  2  +summary : ayni GEVSEK eslestirici, ama summary de taranir.
               -> summary sartname cikti sozlesmesinin (K3) parcasi ve operatorun
                  OKUDUGU alandir; disarida birakilmasi olcum kusuruydu.
  3  +sikilastirilmis : Turkce-guvenli kucuk harf + kelime siniri + olumsuzlama kapisi
               -> "kırmızı"nin Burglary, "vurgulanmadı"nin Assault tetiklemesini keser.
  4  +SEMANTIK GRUP : Fighting/Assault/Abuse gibi operatorel olarak AYNI mudahaleyi
               doguran kategoriler tek grup sayilir (arXiv 2511.07171).

K4 — OLCUM DURUSTLUGU
---------------------
Metrigi degistirmek taban cizgisini YUKSELTIR. Bu yuzden ESKI skor SILINMEZ,
GIZLENMEZ, USTUNE YAZILMAZ: her zaman 1. satirda durur. Ayrica "HAT DOGRULAMASI"
bolumu, kural 1'in dosyadaki KAYITLI category_match degerini birebir yeniden
uretip uretmedigini kontrol eder — uretmiyorsa yeniden skorlama hattinda hata vardir
ve butun tablo supheli sayilmalidir.

OZGULLUK
--------
Yuzde tek basina yaniltir: her kategoriyi tetikleyen bir eslestirici %100 "dogru"
yapar. Bu yuzden her kural icin klip basina tetiklenen YANLIS kategori sayisi da
raporlanir (dusuk = iyi).

Kullanim:
    python benchmark/rescore.py benchmark/results/naming_ab_A_*.json
    python benchmark/rescore.py <a.json> <b.json> --kategori --json cikti.json

Bagimlilik: yalniz stdlib + benchmark.labels. dilajan/torch/av ITHAL EDILMEZ.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from benchmark.labels import (  # noqa: E402
        any_match, group_of, matched_categories, matched_groups, row_text,
    )
except ImportError:  # benchmark/ icinden dogrudan calistirma
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from labels import (  # type: ignore  # noqa: E402
        any_match, group_of, matched_categories, matched_groups, row_text,
    )

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: (anahtar, ekrandaki ad, summary dahil mi, eslestirici modu, grup duzeyi mi,
#:  onarilmis olumsuzlama kapisi mi)
KURALLAR: Tuple[Tuple[str, str, bool, str, bool, bool], ...] = (
    ("eski", "ESKI  (yalniz event, ciplak alt-dizge)", False, "loose", False, False),
    ("summary", "+summary (AYNI gevsek eslestirici)", True, "loose", False, False),
    ("siki", "+summary +SIKILASTIRILMIS eslestirici", True, "strict", False, False),
    ("grup", "+summary +sikilastirilmis +SEMANTIK GRUP", True, "strict", True, False),
    # D33 — OLCULMUS KUSUR: D28 olumsuzlama kapisi `gözlen` kokunu biliyor ama
    # model "gözlemlenmedi" yaziyor (arsivde 520 gecis) ve kapidan KACIYOR. Sonuc:
    # "hicbir tehlike ... gözlemlenmedi" cumlesi, icindeki "yetkisiz"/"ihlal"
    # kelimeleri yuzunden DOGRU KATEGORI ADLANDIRMASI sayiliyor.
    # Bu satir, 3. kuralin (siki) UZERINE yalnizca onarilmis kapiyi ekler; aradaki
    # fark DOGRUDAN kusurun buyuklugudur.
    ("olumsuz", "+summary +sikilastirilmis +ONARIK OLUMSUZLAMA", True, "strict", False, True),
)


def _satir_sonucu(row: dict, summary_dahil: bool, mod: str, grup: bool,
                  onarik: bool = False) -> bool:
    """Tek klip icin tek kuralin karari."""
    parcalar = row_text(row, with_summary=summary_dahil)
    return any_match(parcalar, row.get("category", ""), mode=mod, group=grup,
                     onarik_olumsuzlama=onarik)


def _yanlis_tetik(row: dict, summary_dahil: bool, mod: str, grup: bool) -> int:
    """Klipte tetiklenen YANLIS kategori (veya grup) sayisi — OZGULLUK olcusu."""
    metin = " . ".join(row_text(row, with_summary=summary_dahil))
    dogru = row.get("category", "")
    if grup:
        return len(matched_groups(metin) - {group_of(dogru) or dogru})
    return len(matched_categories(metin, mode=mod) - {dogru})


def dosyayi_skorla(yol: str) -> dict:
    """Bir sonuc JSON'unu 4 kuralla yeniden skorlar (fail-open: eksik alanlar tolere edilir)."""
    with open(yol, encoding="utf-8") as f:
        veri = json.load(f)
    # Arsivlenmis dosyalarda yeni alanlar YOKTUR — okuyan kod COKMEMELI (K3).
    tum = veri.get("rows") or []
    anom = [r for r in tum if r.get("is_anomaly")]

    kural_sonuc: Dict[str, dict] = {}
    for anahtar, ad, s_dahil, mod, grup, onarik in KURALLAR:
        kararlar = [_satir_sonucu(r, s_dahil, mod, grup, onarik) for r in anom]
        yanlislar = [_yanlis_tetik(r, s_dahil, mod, grup) for r in anom]
        kural_sonuc[anahtar] = {
            "ad": ad,
            "k": sum(kararlar),
            "n": len(anom),
            "ozgulluk": (sum(yanlislar) / len(yanlislar)) if yanlislar else 0.0,
            "kararlar": kararlar,
        }

    # --- HAT DOGRULAMASI: kural 1, dosyadaki KAYITLI degeri yeniden uretiyor mu? ---
    # D33 DUZELTMESI: kural 1 ESKI (gevsek) kuraldir. Ama D28'den SONRA uretilen
    # dosyalarda `category_match` alanini YENI kural doldurur (bkz. eval_clips.py
    # MATCH_MODE / satirdaki `category_match_kural`). Eskiden bu kontrol her zaman
    # `category_match`e bakiyordu; D28 sonrasi her dosyada SAHTE "TABLO SUPHELI"
    # alarmi veriyordu (or. taze kosuda 74/100). Dogru karsilik `category_match_eski`.
    def _taban(r: dict):
        """Kural 1 ile karsilastirilacak KAYITLI alan (fail-open, K3)."""
        if r.get("category_match_kural") == "yeni" and "category_match_eski" in r:
            return r.get("category_match_eski")
        return r.get("category_match")

    kayitli = [_taban(r) for r in anom]
    taban_alani = ("category_match_eski"
                   if any(r.get("category_match_kural") == "yeni"
                          and "category_match_eski" in r for r in anom)
                   else "category_match")
    yeniden = kural_sonuc["eski"]["kararlar"]
    karsilastirilabilir = [i for i, v in enumerate(kayitli) if v is not None]
    uyan = sum(1 for i in karsilastirilabilir if bool(kayitli[i]) == yeniden[i])

    # --- kategori bazli dokum ---
    per_cat: Dict[str, Dict[str, List[int]]] = {}
    for i, r in enumerate(anom):
        c = r.get("category", "?")
        d = per_cat.setdefault(c, {a: [0, 0] for a, *_ in KURALLAR})
        for anahtar, *_ in KURALLAR:
            d[anahtar][1] += 1
            d[anahtar][0] += int(kural_sonuc[anahtar]["kararlar"][i])

    return {
        "dosya": os.path.relpath(yol, ROOT).replace("\\", "/"),
        "eval_dir": veri.get("eval_dir") or "?",
        "n_anomali": len(anom),
        "n_toplam": len(tum),
        "kurallar": kural_sonuc,
        "hat_dogrulama": {
            "karsilastirilabilir": len(karsilastirilabilir),
            "uyan": uyan,
            "tamam": uyan == len(karsilastirilabilir) and len(karsilastirilabilir) > 0,
            # Hangi KAYITLI alanla karsilastirildigi tahmine birakilmaz (K7).
            "taban_alani": taban_alani,
        },
        "per_category": per_cat,
    }


def _yuzde(k: int, n: int) -> str:
    return f"%{100.0 * k / n:.1f}" if n else "%-"


def bas(sonuc: dict, kategori_dokumu: bool = False) -> None:
    n = sonuc["n_anomali"]
    print("=" * 86)
    print(f"DOSYA : {sonuc['dosya']}")
    print(f"SET   : {sonuc['eval_dir']}   ·   anomali klip: {n}  (toplam satir: {sonuc['n_toplam']})")
    print("-" * 86)
    print(f"{'kural':46s} {'dogru/n':>9s} {'yuzde':>8s} {'ozgulluk*':>11s}")
    print("-" * 86)
    taban: Optional[int] = None
    for anahtar, *_ in KURALLAR:
        r = sonuc["kurallar"][anahtar]
        if taban is None:
            taban = r["k"]
        fark = f"  ({r['k'] - taban:+d})" if r["k"] != taban else ""
        print(f"{r['ad']:46s} {r['k']:5d}/{r['n']:<3d} {_yuzde(r['k'], r['n']):>8s} "
              f"{r['ozgulluk']:>11.2f}{fark}")
    print("-" * 86)
    print("* ozgulluk = klip basina tetiklenen YANLIS kategori sayisi (dusuk = iyi).")
    print("  Yuzde TEK BASINA yaniltir: her kategoriyi tetikleyen eslestirici %100 'dogru' yapar.")

    hd = sonuc["hat_dogrulama"]
    durum = "TAMAM" if hd["tamam"] else "!!! UYUSMAZLIK — TABLO SUPHELI !!!"
    print(f"HAT DOGRULAMASI: kural 1, dosyadaki kayitli `{hd.get('taban_alani', 'category_match')}` "
          f"ile {hd['uyan']}/{hd['karsilastirilabilir']} ayni  [{durum}]")

    if kategori_dokumu:
        print("-" * 86)
        print("Kategori bazli (n kucuk — CI olmadan tek basina yorumlanmamali):")
        basliklar = "  ".join(f"{a:>8s}" for a, *_ in KURALLAR)
        print(f"  {'kategori':16s} {basliklar}")
        for c in sorted(sonuc["per_category"]):
            d = sonuc["per_category"][c]
            hucre = "  ".join(f"{d[a][0]:>4d}/{d[a][1]:<3d}" for a, *_ in KURALLAR)
            print(f"  {c:16s} {hucre}")
    print("=" * 86)
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dosyalar", nargs="+", help="eval sonuc JSON dosyalari")
    ap.add_argument("--kategori", action="store_true", help="kategori bazli dokum de bas")
    ap.add_argument("--json", dest="json_out", help="sonuclari JSON olarak kaydet")
    args = ap.parse_args()

    print(__doc__.split("Kullanim:")[0])
    hepsi = []
    for yol in args.dosyalar:
        if not os.path.exists(yol):
            print(f"[ATLANDI] bulunamadi: {yol}")
            continue
        s = dosyayi_skorla(yol)
        bas(s, kategori_dokumu=args.kategori)
        hepsi.append(s)

    if len(hepsi) > 1:
        print("=" * 86)
        print("  KOLLAR YAN YANA  (satir = kural, sutun = dosya; dogru/n)")
        print("=" * 86)
        ad = [os.path.basename(s["dosya"]).replace(".json", "")[:22] for s in hepsi]
        print(f"  {'kural':46s} " + "  ".join(f"{a:>22s}" for a in ad))
        for anahtar, etiket, *_ in KURALLAR:
            hucre = "  ".join(
                f"{s['kurallar'][anahtar]['k']:>4d}/{s['kurallar'][anahtar]['n']:<3d} "
                f"{_yuzde(s['kurallar'][anahtar]['k'], s['kurallar'][anahtar]['n']):>7s}"
                .rjust(22) for s in hepsi)
            print(f"  {etiket:46s} " + hucre)
        print("=" * 86)
        # GRUPLAMA KAZANCI: her dosyada kural 4 - kural 3 (literatur +15.7 puan vaat ediyor)
        print("SEMANTIK GRUPLAMA KAZANCI (kural 4 - kural 3), literatur karsilastirmasi:")
        for s in hepsi:
            k3, k4 = s["kurallar"]["siki"], s["kurallar"]["grup"]
            fark = 100.0 * (k4["k"] - k3["k"]) / k3["n"] if k3["n"] else 0.0
            print(f"  {os.path.basename(s['dosya']):46s} {k3['k']:>3d} -> {k4['k']:<3d} "
                  f"({fark:+.1f} puan)")
        print("  Literatur (arXiv 2511.07171, Ovis-8B/UCF-Crime): +15.7 puan.")
        print("=" * 86)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({"dosyalar": hepsi}, f, ensure_ascii=False, indent=2)
        print(f"Kaydedildi: {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
