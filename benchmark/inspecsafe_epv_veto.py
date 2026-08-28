#!/usr/bin/env python
"""InspecSafe hiyerarsik rescue kararlari icin acik-oncul dogrulamasi.

Girdi, tamamlanmis calibration sonucudur. Gold/sidecar bilgisi hicbir API
mesajina girmez. Yalniz duz kolun normal dedigi fakat kilitlenecek hiyerarsik
adayin unsafe'a kurtardigi satirlar incelenir. Tum cikarilan onculer hem `vlm`
hem `llm-large` tarafindan acikca curutulurse rescue veto edilir; hata,
belirsizlik, bos oncul ve ayrisma fail-open'dir.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from benchmark.inspecsafe_factor_ledger import (  # noqa: E402
    FACTOR_CHOICES,
    FACTOR_PROMPT,
    FACTOR_SYSTEM,
    FACTORS,
    parse_factors,
    verification_prompt,
)
from benchmark.inspecsafe_v1 import (  # noqa: E402
    CONTRACT,
    DEFAULT_DATA_ROOT,
    PRIVATE_API,
    _canonical_json_sha,
    _contract,
    _error,
    _sha_bytes,
    _sha_file,
    _still_as_video_url,
    _usage,
)
from benchmark.inspecsafe_v1_hierarchical import (  # noqa: E402
    LABELS,
    RESULTS,
    _append_journal,
    _load_journal,
    candidate_prediction,
    evaluate,
    non_regression_gate,
)
from benchmark.report_inspecsafe_hierarchical import (  # noqa: E402
    high_performance_gate,
    select_high_performance,
)
from benchmark.stats_utils import mcnemar_exact_p  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402


REVISION = "inspecsafe-epv-rescue-veto-v1"
VERDICTS = ("SUPPORTED", "NOT_SUPPORTED", "UNCERTAIN")
EPV_SYSTEM = (
    "You are an explicit visual-premise verifier for industrial safety. The original "
    "image is primary evidence. Check only the named premise. Do not infer it from scene "
    "type, the earlier observation, risk severity, or possibility. Output exactly one "
    "allowed verdict."
)


def _meta(client: VLMClient, stage: str, role: str, started: float) -> dict[str, Any]:
    return {
        "stage": stage,
        "role": role,
        "model": client.model,
        "latency_s": round(time.perf_counter() - started, 3),
        "retries": int(getattr(client, "son_deneme_sayisi", 0)),
        "usage": _usage(client),
    }


def _extract_factors(observation: str) -> tuple[str | None, tuple[str, ...] | None,
                                                  dict[str, Any]]:
    client = VLMClient().gorev("yapi")
    prompt = FACTOR_PROMPT.format(
        observation=observation,
        factors=", ".join(FACTORS),
    )
    started = time.perf_counter()
    raw = client.chat([
        {"role": "system", "content": FACTOR_SYSTEM},
        {"role": "user", "content": prompt},
    ], temperature=0.0, max_tokens=64, guided_choice=FACTOR_CHOICES)
    return raw, parse_factors(raw), _meta(client, "factor_extract", "yapi", started)


def _verify(video_url: str, factor: str, role: str) -> tuple[str | None, dict[str, Any]]:
    client = VLMClient().gorev(role)
    started = time.perf_counter()
    raw = client.chat([
        {"role": "system", "content": EPV_SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": verification_prompt(
                factor, relation=(role == "olay"))},
            {"type": "video_url", "video_url": {"url": video_url}},
        ]},
    ], temperature=0.0, max_tokens=16, guided_choice=VERDICTS)
    value = (raw or "").strip()
    return (value if value in VERDICTS else None,
            _meta(client, f"verify_{factor.lower()}", role, started))


def probe(row: dict[str, Any], data_root: Path) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    extraction_raw = None
    factors: tuple[str, ...] | None = None
    extraction_error = None
    verifications: dict[str, dict[str, Any]] = {}
    started = time.perf_counter()
    try:
        extraction_raw, factors, meta = _extract_factors(row.get("observation") or "")
        calls.append(meta)
        if factors is None:
            extraction_error = "parse_error: invalid factor choice"
    except Exception as exc:  # noqa: BLE001
        extraction_error = _error(exc)

    video_url = None
    video_error = None
    if factors:
        try:
            video_url = _still_as_video_url(data_root / row["relative_path"])
        except Exception as exc:  # noqa: BLE001
            video_error = _error(exc)
    if video_url:
        for factor in factors or ():
            values: dict[str, Any] = {}
            for role in ("algi", "olay"):
                try:
                    verdict, meta = _verify(video_url, factor, role)
                    calls.append(meta)
                    values[role] = verdict
                    values[f"{role}_error"] = (
                        None if verdict is not None else "parse_error: invalid verdict")
                except Exception as exc:  # noqa: BLE001
                    values[role] = None
                    values[f"{role}_error"] = _error(exc)
            verifications[factor] = values
    return {
        "id": row["id"],
        "factor_raw": extraction_raw,
        "factors": list(factors) if factors is not None else None,
        "factor_error": extraction_error,
        "video_error": video_error,
        "verifications": verifications,
        "veto": epv_should_veto({
            "factors": list(factors) if factors is not None else None,
            "factor_error": extraction_error,
            "video_error": video_error,
            "verifications": verifications,
        }),
        "calls": calls,
        "latency_s": round(time.perf_counter() - started, 3),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def epv_should_veto(record: dict[str, Any] | None) -> bool:
    if not record or record.get("factor_error") or record.get("video_error"):
        return False
    factors = record.get("factors")
    if not factors:
        return False
    verifications = record.get("verifications") or {}
    for factor in factors:
        values = verifications.get(factor) or {}
        if values.get("algi_error") or values.get("olay_error"):
            return False
        if values.get("algi") != "NOT_SUPPORTED" or values.get("olay") != "NOT_SUPPORTED":
            return False
    return True


def epv_prediction(row: dict[str, Any], spec: dict[str, Any],
                   records: dict[str, dict[str, Any]]) -> str | None:
    base = candidate_prediction(row, spec)
    if (base in LABELS[:-1]
            and row.get("flat", {}).get("label") == "NO_ABNORMALITY"
            and epv_should_veto(records.get(row["id"]))):
        return "NO_ABNORMALITY"
    return base


def _paired(rows: list[dict[str, Any]], spec: dict[str, Any],
            records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    left = [candidate_prediction(row, spec) == row["gold"] for row in rows]
    right = [epv_prediction(row, spec, records) == row["gold"] for row in rows]
    fixed = sum((not a) and b for a, b in zip(left, right))
    broke = sum(a and (not b) for a, b in zip(left, right))
    return {
        "epv_fixed": fixed,
        "epv_broke": broke,
        "mcnemar_exact_p": mcnemar_exact_p(fixed, broke),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("calibration_result", type=Path)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--smoke", type=int, default=0)
    args = parser.parse_args()
    if args.workers < 1 or args.smoke < 0:
        parser.error("--workers >= 1 ve --smoke >= 0 olmali")

    source_path = args.calibration_result.resolve()
    source = json.loads(source_path.read_text(encoding="utf-8"))
    protocol = source.get("meta", {}).get("protocol", {})
    if protocol.get("phase") != "calibration" or protocol.get("smoke"):
        raise RuntimeError("Kaynak tam calibration sonucu degil")
    rows = source.get("rows") or []
    if len(rows) != 734:
        raise RuntimeError(f"Kaynak calibration kapsami 734 degil: {len(rows)}")
    contract = _contract()
    if protocol.get("contract") != contract:
        raise RuntimeError("Kaynak model/API sozlesmesi mevcut sozlesmeyle uyusmuyor")
    selected = select_high_performance(source["summary"])
    if selected is None or not high_performance_gate(selected["metrics"])["pass"]:
        raise RuntimeError("Kaynakta yuksek-performans adayi yok")
    spec = dict(selected["spec"])
    targets = [
        row for row in rows
        if row.get("flat", {}).get("label") == "NO_ABNORMALITY"
        and candidate_prediction(row, spec) in LABELS[:-1]
    ]
    target_manifest = _canonical_json_sha([
        {"id": row["id"], "image_sha256": row["image_sha256"]} for row in targets
    ])
    source_sha = _sha_file(source_path)
    epv_protocol = {
        "revision": REVISION,
        "source_result_sha256": source_sha,
        "source_run_key": source["meta"]["run_key"],
        "source_manifest_sha256": protocol["manifest_sha256"],
        "decision_spec": spec,
        "target_manifest_sha256": target_manifest,
        "target_count": len(targets),
        "contract": contract,
        "private_api": PRIVATE_API,
        "models": CONTRACT,
        "prompt_hashes": {
            "factor_system": _sha_bytes(FACTOR_SYSTEM.encode("utf-8")),
            "factor_prompt": _sha_bytes(FACTOR_PROMPT.encode("utf-8")),
            "epv_system": _sha_bytes(EPV_SYSTEM.encode("utf-8")),
            "factor_evidence": _canonical_json_sha(
                {factor: verification_prompt(factor) for factor in FACTORS}),
        },
        "decision_rule": (
            "veto only flat-normal to candidate-unsafe rescue when 1-2 extracted "
            "premises are all NOT_SUPPORTED by both algi and olay; every error/empty/"
            "UNCERTAIN/disagreement is fail-open"
        ),
        "labels_sent_to_model": False,
        "temperature": 0.0,
        "smoke": args.smoke,
    }
    run_key = _canonical_json_sha(epv_protocol)[:16]
    if args.smoke:
        targets = targets[:args.smoke]
    RESULTS.mkdir(parents=True, exist_ok=True)
    journal = RESULTS / f".inspecsafe_epv_{run_key}.jsonl"
    done = _load_journal(journal, run_key)
    pending = [row for row in targets if row["id"] not in done]
    print(f"source={source_sha} spec={spec} targets={len(targets)} "
          f"checkpoint={len(done)} pending={len(pending)} run_key={run_key}")
    started = time.perf_counter()
    completed_now = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(probe, row, args.data_root.resolve()): row for row in pending}
        for future in as_completed(futures):
            record = future.result()
            _append_journal(journal, run_key, record)
            done[record["id"]] = record
            completed_now += 1
            elapsed = time.perf_counter() - started
            speed = completed_now / elapsed if elapsed else 0.0
            eta = (len(targets) - len(done)) / speed if speed else 0.0
            print(f"[{len(done)}/{len(targets)}] {record['id']} "
                  f"factors={len(record.get('factors') or [])} "
                  f"calls={len(record['calls'])} veto={int(record['veto'])} "
                  f"row={record['latency_s']:.1f}s eta={eta/60:.1f}m", flush=True)

    records = {row["id"]: done[row["id"]] for row in targets}
    if args.smoke:
        bad = [row for row in records.values()
               if row.get("factor_error") or row.get("video_error")
               or any(value.get("algi_error") or value.get("olay_error")
                      for value in row.get("verifications", {}).values())]
        if bad:
            raise RuntimeError(f"EPV smoke kapisi kaldi: {len(bad)}/{len(records)} hata")
        print(f"SMOKE PASS: {len(records)}/{len(records)}; skor gizlendi")
        return 0

    base_metrics = evaluate(rows, lambda row: candidate_prediction(row, spec))
    epv_metrics = evaluate(rows, lambda row: epv_prediction(row, spec, records))
    gate = non_regression_gate(base_metrics, epv_metrics)
    result = {
        "meta": {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "run_key": run_key,
            "protocol": epv_protocol,
            "source": str(source_path),
            "journal": str(journal),
        },
        "summary": {
            "base_high_performance": base_metrics,
            "epv_candidate": epv_metrics,
            "gate": gate,
            "paired": _paired(rows, spec, records),
            "target_count": len(targets),
            "veto_count": sum(row["veto"] for row in records.values()),
        },
        "records": list(records.values()),
    }
    output = RESULTS / f"inspecsafe_epv_{run_key}.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
                      encoding="utf-8")
    print(f"GATE={'PASS' if gate['pass'] else 'FAIL'} paired={result['summary']['paired']}")
    print(f"RESULT={output}")
    return 0 if gate["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
