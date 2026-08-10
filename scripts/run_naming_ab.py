#!/usr/bin/env python
"""Sorgu-gudumlu analiz — ADLANDIRMA (cat_match) uzerindeki etkiyi olcer. 3 kol.

SORULAN SORU
------------
D27'de sorgunun ZARAR VERMEDIGI kanitlandi (eval_scenario, yangin 10/10, p=1.0000).
Ama o sette cat_match zaten %92-96 idi -> TAVAN ETKISI, iyilesme gorulemezdi.

Modelin GERCEK zayif noktasi eval_holdout: recall %96 ama cat_match %38 (9/24).
Yani model olayi GORUYOR ama ADLANDIRAMIYOR. Bu kosu, sorgunun bu bosluga
yardim edip etmedigini olcer.

!!! OLCUM TUZAGI — ONCE BUNU OKU !!!
------------------------------------
cat_match soyle hesaplanir: "olay metni beklenen ANAHTAR KELIMELERDEN birini iceriyor mu"
(bkz. benchmark/labels.py CATEGORY_EXPECT). Ornek:
    Fighting -> kavga, dovus, saldir, siddet, itis
    Shooting -> silah, ates, vur, catis

Sorguya bu kelimeler yazilirsa model onlari YANKILAR ve cat_match MEKANIK olarak yukselir.
Bu YETENEK KAZANCI DEGILDIR — cevap anahtarini modele vermektir.
Bu yuzden kollar bilerek ikiye ayrildi:

  B kolu (TEMIZ)  : cevap anahtarindan TEK KELIME icermez. Artis olursa GERCEKTIR.
  C kolu (KIRLI)  : tum taksonomiyi listeler. Artisin bir kismi MEKANIK YANKIDIR.
                    Yine de gecerli bir URUN senaryosudur (operator tesis taksonomisini
                    bir kez tanimlar) — ama YETENEK kaniti olarak SUNULAMAZ.

B ile C arasindaki fark, gercek anlamayi mekanik yankidan ayirir.

GUC UYARISI
-----------
Anomali alt kumesi 24 klip; D27'de olculen kosudan-kosuya gurultu tabani ~%8.
%38 -> %50 (3 klip) GURULTU SINIRINDA kalir, yorumlanamaz. Net kazanc icin %60+ gerekir.
Bu esik BASTAN yazildi ki zayif sonuc "az da olsa iyilesti" diye yuvarlanmasin.

Kullanim:
    python scripts/run_naming_ab.py                # uc kolu da kos + karsilastir
    python scripts/run_naming_ab.py --only B       # tek kol
    python scripts/run_naming_ab.py --dry          # yalniz plani yazdir
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SONUC_DIZIN = os.path.join(ROOT, "benchmark", "results")

EVAL_DIR = "data/eval_holdout"

# --- B kolu: TEMIZ. CATEGORY_EXPECT icindeki HICBIR anahtar kelimeyi icermez. ---
# Yalnizca ALAN BAGLAMI ve "belirli ol" talimati verir; hangi olay turlerinin
# aranacagini SOYLEMEZ. Artis olursa modelin kendi ayirt etme yetenegindendir.
SORGU_TEMIZ = (
    "Bu bir şehir güvenlik kamerası kaydıdır; görüntü kalitesi zayıf ve tanelidir. "
    "Gördüğün olayın NE OLDUĞUNU açıkça ve belirli biçimde adlandır. "
    "'Bir şeyler oluyor', 'anormal durum' gibi genel ifadeler yerine olayın türünü yaz."
)

# --- C kolu: KIRLI (bilerek). Tesis olay taksonomisini listeler. ---
# Bu liste KLIP-OZEL DEGILDIR: her klipte AYNI 8 kategori verilir, yani hangi klibin
# hangisi oldugu sizdirilmaz. Ama kategori adlari cat_match anahtar kelimeleriyle
# ORTUSUR -> artisin bir kismi mekanik yankidir. Rapor bunu ACIKCA yazar.
SORGU_TAKSONOMI = (
    "Bu bir şehir güvenlik kamerası kaydıdır; görüntü kalitesi zayıf ve tanelidir. "
    "Bu izleme merkezinin olay taksonomisi şudur: trafik kazası, patlama, kavga, "
    "saldırı, istismar, hırsızlık, silahlı olay, vandalizm. "
    "Gördüğün olayı bu listeden en uygun türle adlandır; hiçbiri uymuyorsa kendi "
    "ifadenle adlandır. Listeyi zorlama — gerçekten gördüğünü yaz."
)

KOLLAR = {
    "A": ("", "TABAN — sorgu yok"),
    "B": (SORGU_TEMIZ, "TEMIZ — alan baglami, kategori adi YOK"),
    "C": (SORGU_TAKSONOMI, "KIRLI (bilerek) — tam taksonomi listelenir"),
}


def _en_yeni_sonuc() -> str | None:
    adaylar = glob.glob(os.path.join(SONUC_DIZIN, "eval_*.json"))
    return max(adaylar, key=os.path.getmtime) if adaylar else None


def kol_kos(ad: str) -> str | None:
    sorgu, aciklama = KOLLAR[ad]
    onceki = _en_yeni_sonuc()
    env = dict(os.environ)
    env.update({
        "DILAJAN_EVAL_DIR": EVAL_DIR,
        "DILAJAN_TEMPERATURE": "0",
        "DILAJAN_ANALYSIS_QUERY": sorgu,
        "PYTHONUNBUFFERED": "1",
    })
    print("=" * 78)
    print(f"  {ad} KOLU — {aciklama}")
    print(f"  set={EVAL_DIR}  temperature=0")
    print(f"  sorgu: {sorgu if sorgu else '(YOK)'}")
    print("=" * 78, flush=True)

    t0 = time.time()
    rc = subprocess.run([sys.executable, os.path.join("benchmark", "eval_clips.py")],
                        cwd=ROOT, env=env).returncode
    if rc != 0:
        print(f"\n[HATA] {ad} kolu cikis kodu {rc}.")
        return None
    uretilen = _en_yeni_sonuc()
    if not uretilen or uretilen == onceki:
        print(f"\n[HATA] {ad} kolu yeni sonuc dosyasi uretmedi.")
        return None
    hedef = os.path.join(SONUC_DIZIN, f"naming_ab_{ad}_{os.path.basename(uretilen)[5:]}")
    shutil.copy2(uretilen, hedef)
    print(f"\n  -> {ad} bitti ({(time.time() - t0) / 60:.1f} dk)  ·  "
          f"{os.path.relpath(hedef, ROOT)}\n", flush=True)
    return hedef


def ozet(yol: str) -> dict:
    with open(yol, encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    anom = [r for r in rows if r.get("is_anomaly")]
    return {
        "n": len(anom),
        "recall": sum(1 for r in anom if r.get("n_events", 0) > 0),
        "cat": sum(1 for r in anom if r.get("category_match")),
        "rows": {r["path"]: r for r in rows},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=list(KOLLAR))
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    print(__doc__)
    if args.dry:
        print("KURU KOSU — olcum yapilmadi.")
        return

    hedefler = [args.only] if args.only else list(KOLLAR)
    yollar = {ad: kol_kos(ad) for ad in hedefler}
    yollar = {k: v for k, v in yollar.items() if v}
    if not yollar:
        return

    print("=" * 78)
    print("  KOL OZETLERI  (asil metrik: cat_match — ADLANDIRMA)")
    print("=" * 78)
    oz = {}
    for ad in sorted(yollar):
        o = ozet(yollar[ad])
        oz[ad] = o
        print(f"  {ad} ({KOLLAR[ad][1]:38s}): "
              f"recall {o['recall']}/{o['n']} (%{100 * o['recall'] / o['n']:.0f})  ·  "
              f"cat_match {o['cat']}/{o['n']} (%{100 * o['cat'] / o['n']:.0f})")
    print()
    if "A" in oz:
        taban = 100 * oz["A"]["cat"] / oz["A"]["n"]
        for ad in ("B", "C"):
            if ad in oz:
                v = 100 * oz[ad]["cat"] / oz[ad]["n"]
                yorum = ("NET KAZANC" if v >= 60 else
                         "GURULTU SINIRINDA — yorumlanamaz" if v - taban < 12 else
                         "kismi")
                etiket = "" if ad == "B" else "  [!] bir kismi MEKANIK YANKI olabilir"
                print(f"  {ad} - A = %{v - taban:+.0f}  ->  {yorum}{etiket}")
    print()

    if len(yollar) > 1 and "A" in yollar:
        for ad in sorted(set(yollar) - {"A"}):
            print("=" * 78)
            print(f"  ESLI TEST — A vs {ad}")
            print("=" * 78, flush=True)
            subprocess.run([sys.executable, os.path.join("benchmark", "paired_test.py"),
                            yollar["A"], yollar[ad]], cwd=ROOT)


if __name__ == "__main__":
    main()
