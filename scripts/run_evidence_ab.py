#!/usr/bin/env python
"""KANIT SORULARI (ASK-HINT) — ADLANDIRMA (cat_match) uzerindeki etkiyi olcer. 2 kol.

SORULAN SORU
------------
eval_holdout'ta recall %96-100 ama ADLANDIRMA (onarilmis olcumle, D29) %46: model olayi
GORUYOR, ADLANDIRAMIYOR. D28'de PROMPT/SORGU yonlendirmesinin bu boslugu KAPATMADIGI
olculdu (3 kol: %38 · %42 · %33, p=1.0000). Bu kosu FARKLI bir mekanizmayi olcer:

  betimleme -> [4 AYRI ikili gorsel kanit sorusu] -> birlestirme -> olay ADINI yenile

Literatur (arXiv 2510.02155, WACV 2026): ayri ayri sorulan ince-taneli ikili sorular
UCF-Crime AUC'yi 74.50 -> 89.83 tasidi (DONMUS model). Bizde hedef AUC degil ADLANDIRMA.

  A kolu: DILAJAN_EVIDENCE_QUESTIONS=0   (TABAN — mevcut davranis, ek cagri yok)
  B kolu: DILAJAN_EVIDENCE_QUESTIONS=1   (kanit sorulari acik)

Tek degisken budur; set/temperature/model AYNIDIR.

!!! OKUMA ESIGI — KOSMADAN ONCE YAZILDI (sonucu yuvarlamamak icin) !!!
----------------------------------------------------------------------
Anomali alt kumesi n=24. D27'de olculen kosudan-kosuya GURULTU TABANI ~%8 (yaklasik 2 klip).
  * B - A < +12 puan  -> GURULTU SINIRINDA, YORUMLANAMAZ ("az da olsa iyilesti" DENMEZ).
  * B - A >= +12 puan -> kismi kazanc; esli test (McNemar) ile birlikte raporlanir.
  * B >= %60          -> NET KAZANC.
Ayrica esli testin p degeri ve etki yonu HER DURUMDA basilir; p >= 0.05 ise sonuc
"kanitlanmadi" olarak yazilir, kol farki ne olursa olsun.

!!! DURUSTLUK NOTU — MEKANIK YANKI RISKI (D28 dersi) !!!
--------------------------------------------------------
cat_match, olay metninin beklenen ANAHTAR KELIMELERI icerip icermedigine bakar. Kanit
sorularinin metni ("ates, alev, duman veya patlama var mi?") ve ipucu metni ("yangin /
duman / patlama") bu kelimelerle ORTUSUR. Bu yuzden artisin bir kismi MEKANIK YANKI
olabilir. Bu kosuyu D28'in "kirli C kolundan" ayiran uc yapisal fark:
  1. Ipucu KOSULLUDUR: yalnizca ilgili soruya GORSEL olarak EVET denirse uretilir. Model
     sorularin hepsine EVET derse ipucu tamamen BASTIRILIR (evidence_questions.MAX_EVET).
  2. Ipucu ancak ZATEN TESPIT EDILMIS bir olay varsa devreye girer; olaysiz klipte tek
     cagri bile yapilmaz. (DIKKAT: bu tek basina YETMEZ — son kosuda 8 normal klipin 3'u
     olay uretti. Asil guvence asagidaki 4. maddedir.)
  3. "Hayır" denen kanit, ada YAZILAMAZ (veto). Yani yanki serbest degil, kanit-kilitlidir.
  4. ALARM MUHAFIZI (adversaryel denetim onarimi): yeniden adlandirilmis metin severity'yi
     ve sevk kapisini ETKILEYEMEZ — `reexamine` hakemi kanit-ONCESI metni gorur, `act`
     sevk kapisinda risk terimi maskelenir. Bu yuzden `fp_sevk`in ARTMAMASI YAPISALDIR;
     `fp_dar` (risk seviyesi) ise hala olculur ve artarsa kol REDDEDILIR.
Bu tez ANCAK asagidaki iki rapor birlikte okunursa gecerlidir; bu yuzden betik
KATEGORI KIRILIMINI ve NORMAL KLIP YANLIS-ALARMINI ayrica basar:
  * dogru kategoride artis + yanlis kategorilerde artis YOKSA  -> kanit calisiyor
  * her kategoride ayni yonde artis varsa                      -> yanki suphesi
  * normal kliplerde FP artisi varsa                           -> KOL REDDEDILIR

Kullanim:
    python scripts/run_evidence_ab.py            # iki kolu da kos + karsilastir
    python scripts/run_evidence_ab.py --only B   # tek kol
    python scripts/run_evidence_ab.py --dry      # yalniz plani yazdir (GPU gerekmez)
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
SORU_SETI = "sokak"  # eval_holdout = UCF-Crime sokak sucu profili

#: Gurultu tabani (D27 olcumu) ve yorum esikleri — BASTAN sabit.
GURULTU_PUAN = 8
ESIK_YORUMLANABILIR = 12
ESIK_NET_KAZANC = 60

KOLLAR = {
    "A": ("0", "TABAN — kanit sorulari KAPALI"),
    "B": ("1", "KANIT SORULARI ACIK (ASK-HINT)"),
}


def _en_yeni_sonuc() -> "str | None":
    adaylar = glob.glob(os.path.join(SONUC_DIZIN, "eval_*.json"))
    return max(adaylar, key=os.path.getmtime) if adaylar else None


def kol_kos(ad: str) -> "str | None":
    deger, aciklama = KOLLAR[ad]
    onceki = _en_yeni_sonuc()
    env = dict(os.environ)
    env.update({
        "DILAJAN_EVAL_DIR": EVAL_DIR,
        "DILAJAN_TEMPERATURE": "0",
        "DILAJAN_EVIDENCE_QUESTIONS": deger,
        "DILAJAN_EVIDENCE_QUESTION_SET": SORU_SETI,
        # Tek degisken kalsin: sorgu-gudumlu analiz KAPALI (D28 kolu ile karismasin).
        "DILAJAN_ANALYSIS_QUERY": "",
        "PYTHONUNBUFFERED": "1",
    })
    print("=" * 78)
    print(f"  {ad} KOLU — {aciklama}")
    print(f"  set={EVAL_DIR}  temperature=0  DILAJAN_EVIDENCE_QUESTIONS={deger}"
          f"  soru_seti={SORU_SETI}")
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
    hedef = os.path.join(SONUC_DIZIN, f"evidence_ab_{ad}_{os.path.basename(uretilen)[5:]}")
    shutil.copy2(uretilen, hedef)
    print(f"\n  -> {ad} bitti ({(time.time() - t0) / 60:.1f} dk)  ·  "
          f"{os.path.relpath(hedef, ROOT)}\n", flush=True)
    return hedef


def ozet(yol: str) -> dict:
    with open(yol, encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    anom = [r for r in rows if r.get("is_anomaly")]
    norm = [r for r in rows if not r.get("is_anomaly")]
    kategoriler: dict = {}
    for r in anom:
        k = kategoriler.setdefault(r.get("category", "?"), {"n": 0, "cat": 0, "recall": 0})
        k["n"] += 1
        k["cat"] += 1 if r.get("category_match") else 0
        k["recall"] += 1 if r.get("n_events", 0) > 0 else 0
    return {
        "n": len(anom),
        "recall": sum(1 for r in anom if r.get("n_events", 0) > 0),
        "cat": sum(1 for r in anom if r.get("category_match")),
        "cat_grup": sum(1 for r in anom if r.get("category_match_grup")),
        "kategoriler": kategoriler,
        # --- NORMAL klip yanlis-alarm profili (kolun REDDEDILME kriteri) ---
        "n_norm": len(norm),
        "fp_dar": sum(1 for r in norm
                      if r.get("max_severity", 0) >= 3 or r.get("risk_ord", 0) >= 3),
        "fp_sevk": sum(1 for r in norm if len(r.get("triggered", []) or []) > 0),
        "fp_olay": sum(1 for r in norm if r.get("n_events", 0) > 0),
        "gecikme": [r.get("latency_s") for r in rows if isinstance(r.get("latency_s"), (int, float))],
    }


def _yuzde(pay: int, payda: int) -> float:
    return (100.0 * pay / payda) if payda else 0.0


def _medyan(xs) -> float:
    xs = sorted(x for x in xs if isinstance(x, (int, float)))
    if not xs:
        return 0.0
    m = len(xs) // 2
    return float(xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2)


def rapor(oz: dict) -> None:
    print("=" * 78)
    print("  KOL OZETLERI  (asil metrik: cat_match — ADLANDIRMA)")
    print("=" * 78)
    for ad in sorted(oz):
        o = oz[ad]
        print(f"  {ad} ({KOLLAR[ad][1]:34s}): "
              f"recall {o['recall']}/{o['n']} (%{_yuzde(o['recall'], o['n']):.0f})  ·  "
              f"cat_match {o['cat']}/{o['n']} (%{_yuzde(o['cat'], o['n']):.0f})  ·  "
              f"grup {o['cat_grup']}/{o['n']} (%{_yuzde(o['cat_grup'], o['n']):.0f})  ·  "
              f"medyan gecikme {_medyan(o['gecikme']):.1f}s")
    print()

    if "A" in oz and "B" in oz:
        a, b = oz["A"], oz["B"]
        fark = _yuzde(b["cat"], b["n"]) - _yuzde(a["cat"], a["n"])
        v = _yuzde(b["cat"], b["n"])
        yorum = ("NET KAZANC" if v >= ESIK_NET_KAZANC else
                 f"GURULTU SINIRINDA (<{ESIK_YORUMLANABILIR} puan) — YORUMLANAMAZ"
                 if fark < ESIK_YORUMLANABILIR else "kismi kazanc")
        print(f"  B - A = %{fark:+.0f} puan  ->  {yorum}"
              f"   (gurultu tabani ~%{GURULTU_PUAN}, n={b['n']})")
        ga, gb = _medyan(a["gecikme"]), _medyan(b["gecikme"])
        print(f"  Gecikme: A {ga:.1f}s -> B {gb:.1f}s  "
              f"({(gb / ga) if ga else 0:.2f}x — K4 tavani 3x)")
        print()

        # --- KATEGORI KIRILIMI: kazanc dogru sinifta mi, yoksa her yerde mi? ---
        print("-" * 78)
        print("  KATEGORI KIRILIMI (mekanik yanki denetimi)")
        print("-" * 78)
        tum = sorted(set(a["kategoriler"]) | set(b["kategoriler"]))
        for k in tum:
            ka = a["kategoriler"].get(k, {"n": 0, "cat": 0})
            kb = b["kategoriler"].get(k, {"n": 0, "cat": 0})
            print(f"  {k:16s} n={ka['n'] or kb['n']:2d}  "
                  f"A {ka['cat']}/{ka['n'] or 1}  ->  B {kb['cat']}/{kb['n'] or 1}")
        print("  (Beklenen: artis BELIRLI kategorilerde. HER kategoride ayni yonde artis"
              " -> yanki suphesi.)")
        print()

        # --- NORMAL KLIP YANLIS-ALARMI: kolun REDDEDILME kriteri ---
        print("-" * 78)
        print("  NORMAL KLIP YANLIS-ALARMI (kolun kabul/red kriteri)")
        print("-" * 78)
        for ad in ("A", "B"):
            o = oz[ad]
            print(f"  {ad}: n={o['n_norm']}  dar-FP {o['fp_dar']} "
                  f"(%{_yuzde(o['fp_dar'], o['n_norm']):.0f})  ·  "
                  f"sevk-FP {o['fp_sevk']} (%{_yuzde(o['fp_sevk'], o['n_norm']):.0f})  ·  "
                  f"olay-uretimi {o['fp_olay']} (%{_yuzde(o['fp_olay'], o['n_norm']):.0f})")
        if b["fp_dar"] > a["fp_dar"] or b["fp_sevk"] > a["fp_sevk"]:
            print("  [!] B kolu NORMAL kliplerde yanlis-alarmi ARTIRDI -> adlandirma kazanci ne"
                  " olursa olsun KOL REDDEDILIR.")
            if b["fp_sevk"] > a["fp_sevk"]:
                print("      [!!] sevk-FP ARTISI: ALARM MUHAFIZI'nin (reexamine kanit-oncesi metin"
                      " + act risk maskesi) kirildigi anlamina gelir -> KOD KUSURU olarak incele.")
            if b["fp_dar"] > a["fp_dar"]:
                print("      [!] dar-FP artisi: BEKLENEN KALAN RISK — yeniden adlandirilmis metni"
                      " `reason` okuyor ve GOSTERILEN risk seviyesini yukseltebiliyor.")
        else:
            print("  [OK] B kolu normal-klip yanlis-alarmini ARTIRMADI (sevk-FP artmamasi YAPISAL:"
                  " alarm muhafizi; dar-FP artmamasi ise OLCUM sonucudur).")
        print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=list(KOLLAR))
    ap.add_argument("--dry", action="store_true", help="yalniz plani yazdir (model cagrisi YOK)")
    args = ap.parse_args()

    print(__doc__)
    if args.dry:
        print("KURU KOSU — olcum yapilmadi. Plan:")
        for ad in (list(KOLLAR) if not args.only else [args.only]):
            deger, aciklama = KOLLAR[ad]
            print(f"  {ad}: {aciklama}")
            print(f"     env: DILAJAN_EVAL_DIR={EVAL_DIR} · DILAJAN_TEMPERATURE=0 · "
                  f"DILAJAN_EVIDENCE_QUESTIONS={deger} · "
                  f"DILAJAN_EVIDENCE_QUESTION_SET={SORU_SETI} · DILAJAN_ANALYSIS_QUERY=")
            print(f"     komut: {os.path.basename(sys.executable)} benchmark/eval_clips.py")
        print("  sonra: benchmark/paired_test.py <A.json> <B.json>  (esli/McNemar)")
        print(f"  okuma esigi: <+{ESIK_YORUMLANABILIR} puan yorumlanamaz · "
              f">=%{ESIK_NET_KAZANC} net kazanc · normal-FP artisi = RED")
        return

    hedefler = [args.only] if args.only else list(KOLLAR)
    yollar = {ad: kol_kos(ad) for ad in hedefler}
    yollar = {k: v for k, v in yollar.items() if v}
    if not yollar:
        return

    rapor({ad: ozet(yol) for ad, yol in yollar.items()})

    if "A" in yollar and "B" in yollar:
        print("=" * 78)
        print("  ESLI TEST — A vs B (McNemar; klip-duzeyi eslesme)")
        print("=" * 78, flush=True)
        subprocess.run([sys.executable, os.path.join("benchmark", "paired_test.py"),
                        yollar["A"], yollar["B"],
                        "--label-a", "taban", "--label-b", "kanit-sorulari"], cwd=ROOT)


if __name__ == "__main__":
    main()
