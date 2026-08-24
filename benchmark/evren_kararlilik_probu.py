#!/usr/bin/env python
"""D42 — KARARLILIK (DETERMINIZM) PROBU.

SORU: Iki eski olcum AYNI hucrede (llm-large · yelek · 768/crf28) 50 klibin
34'unde FARKLI cevap vermis:
    evren_model_kars (D41)     : 47/50 GORUNMUYOR      <- yeni izgara BUNU tekrarladi
    evren_cozunurluk (tarama)  : 13/50 GORUNMUYOR, 26 YELEK_YOK
Iki aciklama var:
  (A) PROTOKOL FARKI  — taramada baska bir sistem promptu / soru / kod cozme kullanildi
  (B) NONDETERMINIZM  — T=0 olsa da paylasilan vLLM toplu-islem (batching) yuzunden
                        cikti kararsiz
Bu prob (B)'yi DOGRUDAN olcer: AYNI klip, AYNI baytlar, AYNI istek, N kez.
Cikti kararliysa (B) elenir ve geriye (A) kalir.

    python benchmark/evren_kararlilik_probu.py [--n 12] [--tekrar 2]
"""
from __future__ import annotations

import argparse
import base64
import collections
import glob
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SET = os.environ.get("DILAJAN_PROB_SET") or os.path.join(KOK, "data/eval_defense")

SISTEM = ("Sen bir endustriyel is guvenligi kamerasi analiz sistemisin. Sana bir "
          "guvenlik kamerasindan alinmis kisa bir video verilir. YALNIZCA GORDUGUNE "
          "dayan; varsayim yapma. Ayirt edemiyorsan kacis secenegini kullan.")
GIRIS = "Bu guvenlik kamerasi videosunu inceleyeceğiz."
SORU = "Makinenin/panonun basinda duran kiside yesil reflektif yelek var mi?"
SECENEK = ["YELEK_VAR", "YELEK_YOK", "KISI_YOK", "GORUNMUYOR"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12, help="klip sayisi")
    ap.add_argument("--tekrar", type=int, default=2, help="ayni klip kac kez sorulacak")
    ap.add_argument("--model", default="llm-large")
    a = ap.parse_args()

    from dilajan.llm_client import VLMClient
    from dilajan.video import servis_videosu
    from dilajan.config import settings
    if settings.mock_mode:
        print("HATA: DILAJAN_MOCK acik."); sys.exit(2)

    ist = VLMClient().client.with_options(timeout=300.0)
    ihlal = sorted(glob.glob(os.path.join(SET, "Anomali/Unauthorized_Intervention/*.mp4")))
    norm = sorted(glob.glob(os.path.join(SET, "Normal/Authorized_Intervention/*.mp4")))
    yollar = ihlal[:a.n // 2] + norm[:a.n - a.n // 2]

    print(f"model={a.model} · 768/crf28 · T=0 · max_tokens=24 · structured_outputs")
    print(f"klip={len(yollar)} · her klip {a.tekrar} kez\n")

    kayit, kararsiz_klip = [], 0
    for yol in yollar:
        ad = os.path.basename(yol)
        baytlar = servis_videosu(yol, max_side=768, crf=28)
        url = "data:video/mp4;base64," + base64.b64encode(baytlar).decode()
        mesajlar = [
            {"role": "system", "content": SISTEM},
            {"role": "user", "content": [
                {"type": "text", "text": GIRIS},
                {"type": "video_url", "video_url": {"url": url}}]},
            {"role": "user", "content": SORU},
        ]
        cevaplar = []
        for _ in range(a.tekrar):
            try:
                r = ist.chat.completions.create(
                    model=a.model, messages=mesajlar, temperature=0.0, max_tokens=24,
                    extra_body={"structured_outputs": {"choice": SECENEK}})
                cevaplar.append((r.choices[0].message.content or "").strip().upper())
            except Exception as e:
                cevaplar.append(f"__HATA__{type(e).__name__}")
            time.sleep(0.2)
        ayni = len(set(cevaplar)) == 1
        if not ayni:
            kararsiz_klip += 1
        kayit.append({"klip": ad, "cevaplar": cevaplar, "kararli": ayni})
        print(f"  {ad:16s} {' | '.join(cevaplar)}   {'KARARLI' if ayni else '<<< DEGISTI'}")

    n = len(kayit)
    print(f"\nKARARLILIK: {n-kararsiz_klip}/{n} klipte {a.tekrar} cevap BIREBIR ayni "
          f"({(n-kararsiz_klip)/n:.0%})")
    dag = collections.Counter(k["cevaplar"][0] for k in kayit)
    print(f"ilk cevap dagilimi: {dict(dag.most_common())}")
    print("\nYORUM:")
    if kararsiz_klip <= max(1, n // 10):
        print("  Cikti KARARLI -> nondeterminizm (B) aciklama OLARAK ELENIR.")
        print("  Iki eski olcum arasindaki 34/50 fark PROTOKOL FARKINDAN (A) gelir.")
    else:
        print(f"  Cikti KARARSIZ ({kararsiz_klip}/{n}) -> nondeterminizm gercek bir")
        print("  aciklama; eski olcumler arasindaki fark buna baglanabilir ve")
        print("  TEK KOSUMLUK tum sonuclar (bizimkiler dahil) tekrar gerektirir.")

    cik = os.path.join(KOK, "benchmark/results",
                       f"evren_kararlilik_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(cik, "w", encoding="utf-8") as f:
        json.dump({"model": a.model, "tekrar": a.tekrar, "kayit": kayit,
                   "kararli_klip": n - kararsiz_klip, "n": n}, f,
                  ensure_ascii=False, indent=2)
    print(f"\nyazildi: {cik}")


if __name__ == "__main__":
    main()
