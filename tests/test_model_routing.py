#!/usr/bin/env python
"""Ana ajan grafiginde goreve-gore model yonlendirme regresyon kilidi.

GPU, sunucu veya ag gerektirmez:
    python tests/test_model_routing.py
"""
from __future__ import annotations

import ast
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dilajan.config import (  # noqa: E402
    FIXED_MODEL_ALIASES,
    PRIVATE_API_BASE_URL,
    Settings,
    settings,
)
from dilajan.llm_client import VLMClient  # noqa: E402

FAILS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(("  [OK]   " if condition else "  [FAIL] ") + label)
    if not condition:
        FAILS.append(label)
        if detail:
            print("         " + detail)


def task_calls(function: ast.FunctionDef) -> list[str]:
    calls: list[str] = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "gorev" or len(node.args) != 1:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            calls.append(arg.value)
    return calls


print("=== GRAPH: ALTI CAGRI NOKTASI GERCEK ALIASA GIDIYOR ===")
graph_path = os.path.join(ROOT, "dilajan", "agent", "graph.py")
tree = ast.parse(open(graph_path, encoding="utf-8").read(), filename=graph_path)
functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
expected = {
    "perceive": ["olay"],
    "reexamine": ["olay"],
    "policy_gate": ["yapi", "algi"],
    "reason": ["ozet"],
    "act": ["yapi"],
}
all_calls: list[str] = []
for name, wanted in expected.items():
    got = task_calls(functions[name])
    all_calls.extend(got)
    check(f"{name}: {wanted}", Counter(got) == Counter(wanted), f"gelen={got}")
check("toplam tam 6 gorev yonlendirmesi", len(all_calls) == 6, f"gelen={all_calls}")


print("\n=== CONFIG: BOS ALIAS K2, DOLU ALIAS GERCEK MODEL ===")
defaults = Settings(_env_file=None)
default_roles = ("algi", "sayim", "olay", "yapi", "ozet", "diyalog",
                 "yonlendirme", "guvenlik", "gomme")
check("temiz kurulum sabit ozel API'ye gider",
      defaults.base_url == PRIVATE_API_BASE_URL)
check("temiz kurulum yalniz sabit uc modeli kullanir",
      {defaults.gorev_modeli(role) for role in default_roles} <= FIXED_MODEL_ALIASES)
plain = Settings(
    _env_file=None,
    model_name="base-model",
    model_algi="",
    model_olay="",
    model_yapi="",
    model_ozet="",
)
check("bos alias model_name'e duser", all(
    plain.gorev_modeli(name) == "base-model" for name in ("algi", "olay", "yapi", "ozet")
))

old = {name: getattr(settings, name) for name in
       ("model_name", "model_algi", "model_olay", "model_yapi", "model_ozet")}
try:
    settings.model_name = "base-model"
    settings.model_algi = "vision-model"
    settings.model_olay = "event-model"
    settings.model_yapi = "structure-model"
    settings.model_ozet = "summary-model"
    base = VLMClient(base_url="http://127.0.0.1:1/v1", api_key="test", model="base-model")
    views = {name: base.gorev(name) for name in ("algi", "olay", "yapi", "ozet")}
    check("dolu aliaslar farkli modele bakar",
          {name: view.model for name, view in views.items()} == {
              "algi": "vision-model", "olay": "event-model",
              "yapi": "structure-model", "ozet": "summary-model"})
    check("gorev gorunumleri ayni HTTP istemcisini paylasir",
          all(view.client is base.client for view in views.values()))
    check("ana istemcinin modeli degismez", base.model == "base-model")
finally:
    for name, value in old.items():
        setattr(settings, name, value)

print(f"\ngecen={12 - len(FAILS)}  kalan={len(FAILS)}")
raise SystemExit(1 if FAILS else 0)
