#!/usr/bin/env python
"""Ozet kalitesi icin LLM-as-judge (sartname KPI: 'ozet kalitesi').

Bir eval sonuc JSON'undaki ozetleri, tespit edilen olaylara gore puanlar:
referanssiz tutarlilik/akicilik/ozluluk degerlendirmesi.

Kullanim:
    python benchmark/judge.py                       # en son eval_*.json
    python benchmark/judge.py benchmark/results/eval_XX;.json
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.utils import extract_json  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "benchmark", "results")

JUDGE_PROMPT = """Bir video analiz sisteminin ürettiği Türkçe ÖZETİ değerlendiren tarafsiz bir hakemsin.

Sistemin o videoda tespit ettiği olaylar:
{events}

Üretilen özet:
"{summary}"

Bu özeti 1-5 arasi puanla (5 en iyi):
- dogruluk: Özet, tespit edilen olaylari sadik ve tutarli biçimde yansitiyor mu? (uydurma/eksik var mi)
- akicilik: Türkçe dil bilgisi ve akicilik (yabanci kelime/karakter sizintisi varsa düşür)
- ozluluk: Gereksiz tekrar olmadan, operatörün hizli karar almasini destekleyecek özlülük

YALNIZCA şu JSON: {{"dogruluk": n, "akicilik": n, "ozluluk": n, "gerekce": "kisa"}}"""


def _events_text(row: dict) -> str:
    # eval rows ozet+olay metnini icermiyor olabilir; ozet var, olaylari summary'den cikaramayiz
    # bu yuzden mevcutsa triggered + n_events baglamini kullan, yoksa sadece ozet tutarliligi
    return f"(tespit edilen olay sayisi: {row.get('n_events')}, risk: {row.get('risk_level')})"


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        files = sorted(glob.glob(os.path.join(RESULTS_DIR, "eval_*.json")))
        if not files:
            print("Sonuc dosyasi yok. Once: python benchmark/eval_clips.py")
            return
        path = files[-1]
    print(f"Degerlendirilen: {os.path.relpath(path, ROOT)}")

    data = json.load(open(path, encoding="utf-8"))
    rows = data["rows"]
    client = VLMClient()

    scores = {"dogruluk": [], "akicilik": [], "ozluluk": []}
    for r in rows:
        summary = r.get("summary", "")
        if not summary:
            continue
        prompt = JUDGE_PROMPT.format(events=_events_text(r), summary=summary)
        try:
            raw = client.chat(
                [{"role": "system", "content": "Sen tarafsiz bir degerlendirme hakemisin."},
                 {"role": "user", "content": prompt}],
                temperature=0.0, max_tokens=200,
            )
            s = extract_json(raw)
            for k in scores:
                v = float(s.get(k, 0))
                if 1 <= v <= 5:
                    scores[k].append(v)
        except Exception as e:
            print(f"  [judge hatasi] {r.get('path')}: {e}")

    print("\n" + "=" * 50)
    print("ÖZET KALİTESİ (LLM-judge, 1-5):")
    for k, vs in scores.items():
        if vs:
            print(f"  {k:10s}: {statistics.mean(vs):.2f}  (n={len(vs)})")
    allv = [v for vs in scores.values() for v in vs]
    if allv:
        print(f"  {'GENEL':10s}: {statistics.mean(allv):.2f}")
    print("=" * 50)


if __name__ == "__main__":
    main()
