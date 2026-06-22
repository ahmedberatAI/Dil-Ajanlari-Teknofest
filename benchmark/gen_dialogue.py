#!/usr/bin/env python
"""Diyalog yanitlarini MEVCUT servis edilen modelle (Qwen3-VL) uretir ve KAYDEDER.

E1 (self-eval dongusellik kirma) icin iki-fazli akisin 1. fazi:
  faz-1: Qwen3-VL servis edilirken bu betik yanitlari uretir -> results/dialogue_responses.json
  faz-2: FARKLI aile bir judge modeli servis edilirken benchmark/judge_independent.py puanlar.

Boylece "ureten model" ile "puanlayan model" farkli olur (dongusellik yok).

Kullanim:  python benchmark/gen_dialogue.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # benchmark/ -> dialogue_test

from dilajan import chat_agent  # noqa: E402
from dialogue_test import CONTEXT, SCENARIOS, MULTI_TURN  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "benchmark", "results", "dialogue_responses.json")


def main() -> None:
    single = []
    print("### TEK-TUR yanitlari uretiliyor (Qwen3-VL)...")
    for stype, msg, expected in SCENARIOS:
        resp = chat_agent.respond(CONTEXT, [], msg)
        single.append({"stype": stype, "msg": msg, "expected": expected, "resp": resp})
        print(f"  [{stype}] {resp[:90]}")

    print("\n### COK-TUR yanitlari uretiliyor (baglam tasiyarak)...")
    multi = []
    history: list = []
    for msg, expected in MULTI_TURN:
        hist_txt = "\n".join(f"{m['role']}: {m['content'][:120]}" for m in history) or "(baslangic)"
        resp = chat_agent.respond(CONTEXT, history, msg)
        multi.append({"msg": msg, "expected": expected, "resp": resp, "history": hist_txt})
        print(f"  S: {msg}\n  C: {resp[:90]}")
        history += [{"role": "user", "content": msg}, {"role": "assistant", "content": resp}]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"context": CONTEXT, "single": single, "multi": multi}, f,
                  ensure_ascii=False, indent=2)
    print(f"\nKaydedildi: {os.path.relpath(OUT, ROOT)}  (tek={len(single)}, cok-tur={len(multi)})")


if __name__ == "__main__":
    main()
