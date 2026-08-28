#!/usr/bin/env python
"""Kilitli InspecSafe kararini sabit ``llm-fast`` formatter ile smoke-test et."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.inspecsafe_v1 import (  # noqa: E402
    CONTRACT,
    LABELS,
    PRIVATE_API,
    _call_format,
    _canonical_json_sha,
    _contract,
    _error,
    _sha_file,
    parse_formatted,
)
from benchmark.inspecsafe_v1_hierarchical import candidate_prediction  # noqa: E402


def _choose(rows: list[dict[str, Any]], spec: dict[str, Any], count: int) -> list[dict[str, Any]]:
    """Gold'a bakmadan tahmin siniflari arasinda deterministik round-robin sec."""
    buckets = {label: [] for label in LABELS}
    for row in sorted(rows, key=lambda value: value["id"]):
        decision = candidate_prediction(row, spec)
        if decision in LABELS and (row.get("observation") or "").strip():
            buckets[decision].append(row)
    chosen: list[dict[str, Any]] = []
    offset = 0
    while len(chosen) < count:
        added = False
        for label in LABELS:
            if offset < len(buckets[label]):
                chosen.append(buckets[label][offset])
                added = True
                if len(chosen) == count:
                    break
        if not added:
            break
        offset += 1
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("holdout_result", type=Path)
    parser.add_argument("--count", type=int, default=8)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count >= 1 olmali")

    result = json.loads(args.holdout_result.read_text(encoding="utf-8"))
    protocol = result.get("meta", {}).get("protocol", {})
    summary = result.get("summary", {})
    if protocol.get("phase") != "holdout" or not summary.get("gate", {}).get("pass"):
        raise RuntimeError("Formatter smoke yalniz kapidan gecen holdout sonucuyla acilir")
    runner = ROOT / "benchmark" / "inspecsafe_v1_hierarchical.py"
    if _sha_file(runner) != protocol.get("runner_sha256"):
        raise RuntimeError("Holdout sonrasi hiyerarsik runner degismis")
    contract = _contract()
    if contract.get("models") != CONTRACT or contract.get("base_url", "").rstrip("/") != PRIVATE_API:
        raise RuntimeError("Sabit ozel API/model sozlesmesi bozuldu")

    spec = dict(summary["spec"])
    chosen = _choose(list(result.get("rows") or []), spec, args.count)
    if len(chosen) != args.count:
        raise RuntimeError(f"Formatter smoke icin {args.count} gecerli karar yok: {len(chosen)}")

    records: list[dict[str, Any]] = []
    for row in chosen:
        observation = str(row["observation"]).strip()
        decision = candidate_prediction(row, spec)
        raw = error = None
        formatted = None
        meta: dict[str, Any] = {}
        try:
            raw, meta = _call_format(observation, decision)
            formatted = parse_formatted(raw, decision)
            if formatted is None:
                error = "parse_error: locked formatter schema mismatch"
        except Exception as exc:  # noqa: BLE001
            error = _error(exc)
        fallback = formatted is None
        final = formatted or {
            "image_description": observation,
            "safety_level": decision,
        }
        if final["safety_level"] != decision:
            raise RuntimeError("Formatter kilitli karari degistirdi")
        records.append({
            "id": row["id"],
            "decision": decision,
            "raw": raw,
            "formatted": final,
            "error": error,
            "deterministic_fallback": fallback,
            "call": meta,
        })

    bindings_ok = all(
        record["call"].get("role") == "yapi"
        and record["call"].get("model") == CONTRACT["yapi"]
        for record in records
    )
    decision_lock_ok = all(
        record["formatted"]["safety_level"] == record["decision"] for record in records)
    if not bindings_ok or not decision_lock_ok:
        raise RuntimeError("Uc-model formatter smoke kapisi kaldi")

    payload = {
        "meta": {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "source_holdout": str(args.holdout_result),
            "source_holdout_sha256": _sha_file(args.holdout_result),
            "source_runner_sha256": protocol["runner_sha256"],
            "formatter_runner_sha256": _sha_file(Path(__file__)),
            "private_api": PRIVATE_API,
            "contract": contract,
            "decision_spec": spec,
        },
        "summary": {
            "count": len(records),
            "bindings_ok": bindings_ok,
            "decision_lock_ok": decision_lock_ok,
            "schema_valid": sum(not record["deterministic_fallback"] for record in records),
            "fallbacks": sum(record["deterministic_fallback"] for record in records),
        },
        "records": records,
    }
    run_key = _canonical_json_sha(payload["meta"])[:16]
    output = ROOT / "benchmark" / "results" / f"inspecsafe_formatter_smoke_{run_key}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                      encoding="utf-8")
    print(f"FORMATTER SMOKE PASS: {len(records)}/{len(records)} fallback={payload['summary']['fallbacks']}")
    print(f"RESULT={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
