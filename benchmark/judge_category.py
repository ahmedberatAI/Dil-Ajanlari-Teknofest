#!/usr/bin/env python
"""Kategori-dogrulugu icin LLM-as-judge (keyword eslesmenin yerine titiz olcum).

Her ANOMALI klibi icin: gercek kategori + sistemin tespit ettigi olaylar verilir; hakem
sistemin olay TURUNU dogru tanimlayip tanimlamadigini 0/1/2 puanlar:
  2 = olay turunu DOGRU adlandirdi
  1 = anormal bir sey tespit etti ama tur yanlis/muglak
  0 = kacirdi veya normal dedi

Kullanim:  python benchmark/judge_category.py [eval_*.json]
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.utils import extract_json  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "benchmark", "results")

# kategori -> gercek olay turunun Turkce tarifi (hakeme verilir)
CATEGORY_TR = {
    "RoadAccidents": "trafik kazasi / arac carpismasi / devrilme",
    "Explosion": "patlama / parlama",
    "Fighting": "kavga / dovus / fiziksel catisma",
    "Assault": "saldiri / darp / birine vurma",
    "Abuse": "istismar / siddet / eziyet",
    "Burglary": "hirsizlik / soygun / izinsiz mekana girme",
    "Shooting": "silahla ates etme / vurma / silahli saldiri",
    "Vandalism": "vandalizm / mala kasitli zarar verme",
    "Fire": "yangin / alev",
    "Smoke": "duman",
    "Fall": "dusme / yere yigilma / yerde hareketsiz kisi",
}

JUDGE = """Bir video-analiz sisteminin olay tespitini degerlendiren tarafsiz bir hakemsin.

Bu klipteki GERCEK olay turu: {truth}

Sistemin tespit ettigi olaylar:
{events}

Sistem bu GERCEK olay turunu dogru tanidi mi? Sadece su olcege gore puanla:
  2 = olay turunu DOGRU tanimladi/adlandirdi (es anlamli ifadeler kabul)
  1 = anormal/riskli bir sey tespit etti ama turu YANLIS ya da cok muglak
  0 = ilgili olayi kacirdi (olay yok veya tamamen alakasiz/normal dedi)

YALNIZCA su JSON: {{"score": 0|1|2, "gerekce": "kisa"}}"""


def _events_text(row: dict) -> str:
    evs = row.get("events")
    if evs:
        return "\n".join(f"- [{e.get('time')}] {e.get('event')} ({e.get('severity')})" for e in evs) or "(olay yok)"
    # eski sonuc: olay metni yok -> ozet + sayi
    return f"(olay metni kayitli degil; ozet: {row.get('summary','')[:200]} | olay sayisi: {row.get('n_events')})"


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        files = sorted(glob.glob(os.path.join(RESULTS_DIR, "eval_*.json")))
        if not files:
            print("Sonuc dosyasi yok."); return
        path = files[-1]
    print(f"Degerlendirilen: {os.path.relpath(path, ROOT)}\n")

    rows = json.load(open(path, encoding="utf-8"))["rows"]
    client = VLMClient()
    by_cat = defaultdict(list)
    for r in rows:
        cat = r.get("category")
        if cat not in CATEGORY_TR:  # yalnizca anomali kategorileri
            continue
        prompt = JUDGE.format(truth=CATEGORY_TR[cat], events=_events_text(r))
        try:
            raw = client.chat(
                [{"role": "system", "content": "Sen tarafsiz bir degerlendirme hakemisin."},
                 {"role": "user", "content": prompt}],
                temperature=0.0, max_tokens=150,
            )
            sc = int(extract_json(raw).get("score", 0))
        except Exception as e:
            print(f"  [judge hatasi] {r.get('path')}: {e}"); sc = 0
        by_cat[cat].append(sc)

    print("=" * 56)
    print("KATEGORİ DOĞRULUĞU (LLM-judge):")
    print("  kategori        n   doğru(2)  tespit(>=1)  ort-puan")
    all_scores = []
    for cat in CATEGORY_TR:
        ss = by_cat.get(cat)
        if not ss:
            continue
        all_scores += ss
        correct = sum(1 for s in ss if s == 2) / len(ss)
        detected = sum(1 for s in ss if s >= 1) / len(ss)
        print(f"  {cat:14s} {len(ss):3d}   {correct*100:5.0f}%     {detected*100:5.0f}%      {statistics.mean(ss):.2f}")
    if all_scores:
        c = sum(1 for s in all_scores if s == 2) / len(all_scores)
        d = sum(1 for s in all_scores if s >= 1) / len(all_scores)
        print("-" * 56)
        print(f"  {'TOPLAM':14s} {len(all_scores):3d}   {c*100:5.0f}%     {d*100:5.0f}%      {statistics.mean(all_scores):.2f}")
    print("=" * 56)


if __name__ == "__main__":
    main()
