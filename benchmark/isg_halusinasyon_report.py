#!/usr/bin/env python
"""Eval arsivlerinde normal-klip alarm ailelerini ve varsayilan projeksiyonu sayar."""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dilajan.agent.graph import _claim_families  # noqa: E402

SEV = {"Düşük": 1, "Orta": 2, "Yüksek": 3, "Kritik": 4}
FACILITY_PREFIXES = {
    "panel_roi": "Pano kapağı açık bırakılmış:",
    "vest_authority": "Yetkisiz müdahale:",
    "forklift_threshold": "Forklift aşırı yük taşıyor:",
}


def load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["rows"]


def report(path: str) -> dict:
    rows = load(path)
    normal = [r for r in rows if not r.get("is_anomaly")]
    family_rows: dict[str, int] = {}
    narrative_family_rows: dict[str, int] = {}
    source_rows = {name: 0 for name in FACILITY_PREFIXES}
    projected_events = 0
    projected_high = 0
    for row in normal:
        families = set()
        narrative_families = set()
        remaining = []
        for event in row.get("events", []) or []:
            text = str(event.get("event", ""))
            fs = set(_claim_families(text))
            families |= fs
            source = next((name for name, prefix in FACILITY_PREFIXES.items()
                           if text.startswith(prefix)), None)
            if source:
                source_rows[source] += 1
            else:
                narrative_families |= fs
            # Genel UI varsayilani: tesis beyani gerektiren panel, yelek-yetki
            # ve forklift kasa-esigi kurallari kapali.
            if source not in {"panel_roi", "vest_authority", "forklift_threshold"}:
                remaining.append(event)
        for family in families:
            family_rows[family] = family_rows.get(family, 0) + 1
        for family in narrative_families:
            narrative_family_rows[family] = narrative_family_rows.get(family, 0) + 1
        if remaining:
            projected_events += 1
        if max((SEV.get(e.get("severity", ""), 0) for e in remaining), default=0) >= 3:
            projected_high += 1
    return {
        "file": os.path.relpath(path, ROOT).replace("\\", "/"),
        "normal_n": len(normal),
        "recorded_normal_high_fp": sum(
            r.get("max_severity", 0) >= 3 or r.get("risk_ord", 0) >= 3 for r in normal),
        "recorded_normal_operational_fp": sum(
            bool(r.get("events")) or bool(r.get("triggered")) for r in normal),
        "normal_rows_by_claim_family": dict(sorted(family_rows.items())),
        "normal_rows_by_narrative_claim_family": dict(sorted(narrative_family_rows.items())),
        "normal_rows_by_facility_rule_source": source_rows,
        "projected_default_normal_high_fp": projected_high,
        "projected_default_normal_operational_fp": projected_events,
        "projection_note": ("panel ROI, yelek-yetki ve forklift kasa-esigi kurallari kapali; reason risk tavani "
                            "kalan en yuksek Event severity'sine uygulanmis sayilir"),
    }


if __name__ == "__main__":
    paths = sys.argv[1:] or [
        os.path.join(ROOT, "benchmark", "results", "eval_20260825_114341.json"),
        os.path.join(ROOT, "benchmark", "results", "eval_20260827_121237.json"),
        os.path.join(ROOT, "benchmark", "results", "eval_20260827_130900.json"),
    ]
    print(json.dumps([report(os.path.abspath(p)) for p in paths],
                     ensure_ascii=False, indent=2))
