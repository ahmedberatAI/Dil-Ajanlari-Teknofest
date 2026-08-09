#!/usr/bin/env python
"""Sorgu-gudumlu analiz (D26) A/B olcum kosucusu — "sorgu ODAKLAR, FILTRELEMEZ" iddiasini SINAR.

JURININ SORACAGI SORU:
    "Operator 'sadece forklift hareketlerine bak' dedi. Yangini kacirdiniz mi?"

Bu kosu o soruya SAYIYLA cevap verir.

TASARIM
-------
Set  : data/eval_scenario  (Fall 15 + Fire 10 + Normal 12 = 37 klip)
       Set BILEREK secildi: icinde HIC forklift YOK. B kolundaki sorgu bu sete
       tamamen ILGISIZ; yani en kotu durum sinaniyor. Sorgu bir filtre gibi
       davransaydi, yangin ve dusme tespitleri COKERDI.

A kolu: sorgu YOK          (DILAJAN_ANALYSIS_QUERY = "")
B kolu: DAR ve ILGISIZ sorgu ("Sadece forklift hareketlerine bak. ...")

TEK DEGISKEN: DILAJAN_ANALYSIS_QUERY. Diger her sey (set, model, esikler,
kare sayisi, tesis kurali durumu) IKI KOLDA DA AYNI -> olculen fark yalnizca
sorgudan gelir.

DETERMINIZM (kusur #8'e karsi onlem)
------------------------------------
Iki kol da temperature=0 (acgozlu cozumleme) ile kosar. Varsayilan 0.2'lik
ornekleme, daha once kusur #2 olcumunu oldurmustu (metrik +-15 klip saliniyor,
p=0.48). temperature=0 bu gurultuyu kaldirir; olculen fark ORNEKLEMEDEN degil
SORGUDAN gelir. NOT: vLLM'de toplu-islem (batching) kaynakli kucuk bir
belirsizlik kalir; bu yuzden fark yine de ESLI testle degerlendirilir.

ISTATISTIK
----------
Ayni klipler iki kolda da kosuldugu icin olcum ESLIDIR. Analiz
benchmark/paired_test.py (McNemar exact + Newcombe fark GA) ile yapilir:
    python benchmark/paired_test.py <A.json> <B.json>

Kullanim:
    python scripts/run_query_ab.py              # iki kolu da kosar, sonra karsilastirir
    python scripts/run_query_ab.py --only A     # yalnizca A kolu
    python scripts/run_query_ab.py --only B     # yalnizca B kolu
    python scripts/run_query_ab.py --dry        # yalnizca plani yazdirir
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

EVAL_DIR = "data/eval_scenario"

# B kolu sorgusu: sete BILEREK tamamen ILGISIZ + "baska hicbir seye bakma" baskisi.
# Sorgu bir filtre gibi davransaydi, bu metin yangin/dusme tespitini yok ederdi.
DAR_SORGU = (
    "Sadece forklift hareketlerine bak. Yalnizca forkliftlerin nereye gittigini "
    "ve yuk tasiyip tasimadiklarini rapor et. Baska hicbir seyle ilgilenme."
)


def _en_yeni_sonuc() -> str | None:
    """benchmark/results/ altindaki en yeni eval_*.json dosyasini dondurur."""
    adaylar = glob.glob(os.path.join(SONUC_DIZIN, "eval_*.json"))
    return max(adaylar, key=os.path.getmtime) if adaylar else None


def kol_kos(ad: str, sorgu: str) -> str | None:
    """Tek bir kolu kosar ve uretilen sonuc dosyasini <ad> ile etiketleyip dondurur."""
    onceki = _en_yeni_sonuc()
    env = dict(os.environ)
    env.update({
        "DILAJAN_EVAL_DIR": EVAL_DIR,
        "DILAJAN_TEMPERATURE": "0",        # determinizm — kusur #8 onlemi
        "DILAJAN_ANALYSIS_QUERY": sorgu,   # TEK DEGISKEN
        "PYTHONUNBUFFERED": "1",
    })
    print("=" * 78)
    print(f"  {ad} KOLU  ·  temperature=0  ·  set={EVAL_DIR}")
    print(f"  sorgu: {sorgu if sorgu else '(YOK — taban kol)'}")
    print("=" * 78, flush=True)

    t0 = time.time()
    rc = subprocess.run([sys.executable, os.path.join("benchmark", "eval_clips.py")],
                        cwd=ROOT, env=env).returncode
    sure = time.time() - t0
    if rc != 0:
        print(f"\n[HATA] {ad} kolu cikis kodu {rc} ile bitti.")
        return None

    uretilen = _en_yeni_sonuc()
    if not uretilen or uretilen == onceki:
        print(f"\n[HATA] {ad} kolu yeni sonuc dosyasi uretmedi.")
        return None

    hedef = os.path.join(SONUC_DIZIN, f"query_ab_{ad}_{os.path.basename(uretilen)[5:]}")
    shutil.copy2(uretilen, hedef)
    print(f"\n  -> {ad} kolu bitti ({sure / 60:.1f} dk)  ·  {os.path.relpath(hedef, ROOT)}\n",
          flush=True)
    return hedef


def ozet(yol: str, ad: str) -> dict:
    """Sonuc dosyasindan kisa bir tespit ozeti cikarir (ekrana basmak icin)."""
    with open(yol, encoding="utf-8") as f:
        d = json.load(f)
    satirlar = d.get("rows", d if isinstance(d, list) else [])
    anom = [r for r in satirlar if r.get("is_anomaly")]
    norm = [r for r in satirlar if not r.get("is_anomaly")]
    tespit = sum(1 for r in anom if r.get("n_events", 0) > 0)
    yanlis = sum(1 for r in norm if r.get("n_events", 0) > 0)
    return {"ad": ad, "anomali": len(anom), "tespit": tespit,
            "normal": len(norm), "yanlis_alarm": yanlis,
            "recall": tespit / len(anom) if anom else 0.0}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=["A", "B"], help="yalnizca tek kolu kos")
    ap.add_argument("--dry", action="store_true", help="yalnizca plani yazdir")
    args = ap.parse_args()

    print(__doc__)
    if args.dry:
        print("KURU KOSU — hicbir olcum yapilmadi.")
        return

    yollar: dict = {}
    if args.only in (None, "A"):
        yollar["A"] = kol_kos("A", "")
    if args.only in (None, "B"):
        yollar["B"] = kol_kos("B", DAR_SORGU)

    if len(yollar) < 2 or not all(yollar.values()):
        print("Tek kol kosuldu veya bir kol hata verdi — karsilastirma atlandi.")
        return

    print("=" * 78)
    print("  KOL OZETLERI")
    print("=" * 78)
    for ad in ("A", "B"):
        o = ozet(yollar[ad], ad)
        print(f"  {ad}: anomali {o['tespit']}/{o['anomali']} tespit "
              f"(recall %{o['recall'] * 100:.0f})  ·  "
              f"normal {o['normal']} klipte {o['yanlis_alarm']} yanlis alarm")
    print()

    print("=" * 78)
    print("  ESLI ISTATISTIKSEL KARSILASTIRMA (McNemar exact)")
    print("=" * 78, flush=True)
    subprocess.run([sys.executable, os.path.join("benchmark", "paired_test.py"),
                    yollar["A"], yollar["B"]], cwd=ROOT)


if __name__ == "__main__":
    main()
