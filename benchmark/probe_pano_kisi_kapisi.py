#!/usr/bin/env python
"""Arsiv slot izlerinde `pano koyu + kisi yok` kapisini mekanik puanlar."""
from __future__ import annotations

import ast
import json
import math
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARSIV = os.path.join(ROOT, "benchmark", "results", "eval_20260825_114341.json")
SLOT_RE = re.compile(r"slot=\[(.*?)\]")
PANEL_TEXT = "Pano kapağı açık bırakılmış"


def slots(row: dict) -> list[dict]:
    out = []
    for line in row.get("guven_trace", []) or []:
        m = SLOT_RE.search(str(line))
        if not m:
            continue
        try:
            out.append(dict(ast.literal_eval("[" + m.group(1) + "]")))
        except Exception:
            continue
    return out


def mcc(tp: int, fp: int, fn: int, tn: int) -> float:
    den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return (tp * tn - fp * fn) / den if den else 0.0


with open(ARSIV, encoding="utf-8") as f:
    rows = json.load(f)["rows"]

pred: dict[str, bool] = {}
missing = 0
for row in rows:
    ss = slots(row)
    pano = max((int(s["pano_koyuluk_0_10"]) for s in ss
                if s.get("pano_koyuluk_0_10") is not None), default=None)
    kisi = next((int(s["makine_basinda_kisi"]) for s in ss
                 if s.get("makine_basinda_kisi") is not None), None)
    if pano is None or kisi is None:
        missing += 1
    pred[row["path"]] = bool(pano is not None and pano >= 6 and kisi == 0)

pair = [r for r in rows if r.get("isg_sinif") in
        {"Opened_Panel_Cover", "Closed_Panel_Cover"}]
tp = sum(pred[r["path"]] and r["isg_sinif"] == "Opened_Panel_Cover" for r in pair)
fp = sum(pred[r["path"]] and r["isg_sinif"] == "Closed_Panel_Cover" for r in pair)
fn = sum((not pred[r["path"]]) and r["isg_sinif"] == "Opened_Panel_Cover" for r in pair)
tn = sum((not pred[r["path"]]) and r["isg_sinif"] == "Closed_Panel_Cover" for r in pair)

# Yeni reason risk tavaniyla, normal satirdaki TEK Yuksek olay panel ise bu
# panel kapandiginda Yuksek FP de mekanik olarak kapanir.
only_panel_closed = 0
normal_panel_before = 0
for row in rows:
    if row.get("is_anomaly"):
        continue
    high = [e for e in row.get("events", [])
            if e.get("severity") in {"Yüksek", "Kritik"}]
    panel_high = [e for e in high if PANEL_TEXT in e.get("event", "")]
    if panel_high:
        normal_panel_before += 1
    if panel_high and len(panel_high) == len(high) and not pred[row["path"]]:
        only_panel_closed += 1

result = {
    "source": os.path.relpath(ARSIV, ROOT).replace("\\", "/"),
    "rule": "pano_koyuluk_0_10>=6 AND makine_basinda_kisi==0",
    "matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
               "mcc": round(mcc(tp, fp, fn, tn), 6)},
    "normal_panel_high_before": normal_panel_before,
    "normal_only_panel_high_closed": only_panel_closed,
    "rows_missing_either_slot": missing,
    "accept": bool(mcc(tp, fp, fn, tn) >= 0.910 and fn <= 2 and
                   only_panel_closed >= 5),
}
print(json.dumps(result, ensure_ascii=False, indent=2))
