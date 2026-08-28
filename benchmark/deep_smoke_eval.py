#!/usr/bin/env python3
"""Project RISE sabit-sahne bolmelerinde tam DilAjanlari akisini olc.

Model tahmini, olay ve ozet metninde olumsuzlama-korumali ``Smoke`` eslesmesidir.
Altin etiket veya etiketli dizin adi modele verilmez; tum klipler tek, notr dizindedir.

Kilitli ``holdout`` bolmesi ancak ``DEEP_SMOKE_UNSEAL_HOLDOUT=1`` ile acilir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.eval_clips import (  # noqa: E402
    _kosum_kunyesi,
    _ozel_api_model_sozlesmesini_dogrula,
    evaluate_clip,
)
from benchmark.labels import any_match, row_text  # noqa: E402
from benchmark.stats_utils import fmt_rate_dict, rate  # noqa: E402
from dilajan.config import settings  # noqa: E402


RESULTS_DIR = ROOT / "benchmark" / "results"

SPLITS = {
    "frozen": ROOT / "data" / "eval_deep_smoke_balanced_v1",
    "dev": ROOT / "data" / "eval_deep_smoke_v2" / "dev",
    "dev_optical": ROOT / "data" / "eval_deep_smoke_v2" / "dev_optical",
    "holdout": ROOT / "data" / "eval_deep_smoke_v2" / "holdout",
}


def smoke_prediction(row: dict[str, Any]) -> bool:
    """Etkin olay+ozette olumlu duman/emisyon iddiasi var mi?"""
    return any_match(
        row_text(row, with_summary=True),
        "Smoke",
        mode="strict",
        onarik_olumsuzlama=True,
    )


def confusion_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [row for row in rows if not row.get("error")]
    tp = sum(row["gold_smoke"] == 1 and row["smoke_pred"] for row in usable)
    fn = sum(row["gold_smoke"] == 1 and not row["smoke_pred"] for row in usable)
    fp = sum(row["gold_smoke"] == 0 and row["smoke_pred"] for row in usable)
    tn = sum(row["gold_smoke"] == 0 and not row["smoke_pred"] for row in usable)
    total = tp + fn + fp + tn
    precision_den = tp + fp
    f1_den = 2 * tp + fp + fn
    mcc_den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return {
        "confusion": {"tp": tp, "fn": fn, "fp": fp, "tn": tn},
        "smoke_recall": rate(tp, tp + fn),
        "smoke_false_positive_rate": rate(fp, fp + tn),
        "specificity": rate(tn, tn + fp),
        "precision": rate(tp, precision_den),
        "accuracy": round((tp + tn) / total, 4) if total else 0.0,
        "balanced_accuracy": round(
            0.5 * (tp / (tp + fn) + tn / (tn + fp)), 4
        ) if (tp + fn) and (tn + fp) else 0.0,
        "f1": round((2 * tp) / f1_den, 4) if f1_den else 0.0,
        "mcc": round(((tp * tn) - (fp * fn)) / mcc_den, 4) if mcc_den else 0.0,
        "coverage": rate(len(usable), len(rows)),
    }


def _checkpoint_path(manifest: dict[str, Any], run_card: dict[str, Any]) -> Path:
    identity = json.dumps(
        {"manifest": manifest, "run": run_card}, sort_keys=True, ensure_ascii=False
    ).encode("utf-8")
    return RESULTS_DIR / f".deep_smoke_{hashlib.sha256(identity).hexdigest()[:12]}.jsonl"


def _load_checkpoint(path: Path) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and "source_id" in row:
            rows[int(row["source_id"])] = row
    return rows


def _append_checkpoint(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=tuple(SPLITS), default="frozen")
    parser.add_argument(
        "--tag", default="", help="Sonuc dosyasina eklenecek kisa mimari etiketi"
    )
    args = parser.parse_args()
    split = args.split
    if split == "holdout" and os.environ.get("DEEP_SMOKE_UNSEAL_HOLDOUT") != "1":
        raise RuntimeError(
            "Kilitli holdout acilmadi. Yalniz nihai tek kosuda "
            "DEEP_SMOKE_UNSEAL_HOLDOUT=1 kullanin."
        )
    data_dir = SPLITS[split]
    manifest_path = data_dir / "_metadata" / "manifest.json"
    contract = _ozel_api_model_sozlesmesini_dogrula()
    if settings.yerel_ogrenilmis_izni or settings.model_indirme_izni:
        raise RuntimeError("Yerel ogrenilmis cikarim/model indirme benchmarkta yasak")
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest yok: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = list(manifest.get("items") or [])
    counts = {
        0: sum(int(item["gold_smoke"]) == 0 for item in items),
        1: sum(int(item["gold_smoke"]) == 1 for item in items),
    }
    expected = int(manifest.get("counts", {}).get("smoke", -1))
    if expected <= 0 or counts != {0: expected, 1: expected}:
        raise RuntimeError(f"Manifest dengesi bozuk: {counts}")
    for item in items:
        path = data_dir / item["file"]
        if not path.is_file() or not item.get("sha256"):
            raise RuntimeError(f"Eksik/dogrulanmamis klip: {path}")

    run_card = _kosum_kunyesi()
    run_card["deep_smoke_split"] = split
    run_card["deep_smoke_tag"] = args.tag.strip()
    checkpoint = _checkpoint_path(manifest, run_card)
    completed = _load_checkpoint(checkpoint)
    rows = list(completed.values())
    remaining = [item for item in items if int(item["source_id"]) not in completed]
    workers = max(1, int(os.environ.get("EVAL_ISCI", "4")))
    lock = threading.Lock()

    print(
        f"Project RISE/{split}: {expected} duman + {expected} dumansiz; "
        f"{len(remaining)} klip kaldi; "
        f"{workers} isci; ozel API={contract['base_url']}",
        flush=True,
    )

    def evaluate(item: dict[str, Any]) -> dict[str, Any]:
        source_id = int(item["source_id"])
        path = data_dir / item["file"]
        try:
            # Kategori skorlama icindir; analyze_video yalniz notr klip yolunu gorur.
            row = evaluate_clip(str(path), "Smoke" if int(item["gold_smoke"]) else "Normal")
            row.update(
                {
                    "source_id": source_id,
                    "gold_smoke": int(item["gold_smoke"]),
                    "label_state_admin": int(item["label_state_admin"]),
                    "smoke_pred": False,
                }
            )
            row["smoke_pred"] = smoke_prediction(row)
            return row
        except Exception as exc:
            return {
                "source_id": source_id,
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "gold_smoke": int(item["gold_smoke"]),
                "smoke_pred": False,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def store(item: dict[str, Any]) -> None:
        row = evaluate(item)
        with lock:
            rows.append(row)
            _append_checkpoint(checkpoint, row)
            verdict = "ERR" if row.get("error") else ("TP/TN" if bool(row["smoke_pred"]) == bool(row["gold_smoke"]) else "FP/FN")
            print(
                f"[{len(rows):02d}/{len(items):02d}] id={row['source_id']} "
                f"gold={row['gold_smoke']} "
                f"pred={int(bool(row['smoke_pred']))} {verdict}",
                flush=True,
            )

    if workers == 1:
        for item in remaining:
            store(item)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(store, remaining))

    rows.sort(key=lambda row: int(row["source_id"]))
    metrics = confusion_metrics(rows)
    positives = [row for row in rows if row.get("gold_smoke") == 1 and not row.get("error")]
    negatives = [row for row in rows if row.get("gold_smoke") == 0 and not row.get("error")]
    metrics["operational_event_recall"] = rate(
        sum(int(row.get("n_events", 0)) > 0 for row in positives), len(positives)
    )
    metrics["operational_fp"] = rate(
        sum(int(row.get("n_events", 0)) > 0 or bool(row.get("triggered")) for row in negatives),
        len(negatives),
    )
    metrics["high_risk_fp"] = rate(
        sum(int(row.get("max_severity", 0)) >= 3 or int(row.get("risk_ord", 0)) >= 3 for row in negatives),
        len(negatives),
    )
    metrics["dispatch_fp"] = rate(
        sum(bool(row.get("triggered")) for row in negatives), len(negatives)
    )
    latencies = [float(row["latency_s"]) for row in rows if not row.get("error") and "latency_s" in row]
    metrics["latency_median_s"] = round(statistics.median(latencies), 2) if latencies else None
    failures = [row for row in rows if row.get("error")]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    safe_tag = "".join(c for c in args.tag.strip().lower() if c.isalnum() or c in "-_")
    suffix = f"_{safe_tag}" if safe_tag else ""
    output = RESULTS_DIR / f"deep_smoke_{split}{suffix}_{stamp}.json"
    payload = {
        "benchmark": f"Project RISE {split} same-view same-day balanced smoke",
        "manifest": str(manifest_path.relative_to(ROOT)).replace("\\", "/"),
        "model_contract": contract,
        "run": run_card,
        "prediction_rule": "events+summary; Smoke strict matcher; repaired negation gate",
        "metrics": metrics,
        "failures": failures,
        "rows": rows,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if checkpoint.exists():
        checkpoint.unlink()

    print("\n" + "=" * 72)
    print(f"Smoke recall : {fmt_rate_dict(metrics['smoke_recall'])}")
    print(f"Smoke FP     : {fmt_rate_dict(metrics['smoke_false_positive_rate'])}")
    print(f"Precision    : {fmt_rate_dict(metrics['precision'])}")
    print(f"Specificity  : {fmt_rate_dict(metrics['specificity'])}")
    print(f"Operasyonel FP: {fmt_rate_dict(metrics['operational_fp'])}")
    print(f"Dispatch FP   : {fmt_rate_dict(metrics['dispatch_fp'])}")
    print(f"F1={metrics['f1']:.3f}  MCC={metrics['mcc']:.3f}  balanced_acc={metrics['balanced_accuracy']:.3f}")
    print(f"Kapsama: {fmt_rate_dict(metrics['coverage'])}; hata={len(failures)}")
    print(f"Kaydedildi: {output.relative_to(ROOT)}")
    print("=" * 72)
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
