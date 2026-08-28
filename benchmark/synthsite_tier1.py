#!/usr/bin/env python
"""SynthSite Tier-1 askidaki-yuk ISG benchmarki (yalniz sabit ozel API).

Etiketler prompta verilmez. Yalniz tam insan uzlasili Tier-1 klipler puanlanir;
belirsiz Tier-2 klipler ana paydadan dislanir.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import time
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from benchmark.stats_utils import wilson_ci  # noqa: E402
from dilajan.config import settings  # noqa: E402
from dilajan.gozlem import GOZLEM_SISTEM  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402


DATA_ROOT = ROOT / "data" / "external" / "synthsite"
LABEL_PATH = DATA_ROOT / "synthetic_video_labels.csv"
RESULTS = ROOT / "benchmark" / "results"
REPO_ID = "govtech/SynthSite"
REVISION = "2904ec01c3dbf2efba09f2cb1b7bdf17841d4d39"
PRIVATE_API_BASE = "https://evren-llmapi.ssyz.org.tr/v1"
MODEL_CONTRACT = {
    "algi": "vlm",
    "olay": "llm-large",
    "yapi": "llm-fast",
    "ozet": "llm-fast",
}
CHOICES = ("IHLAL_VAR", "IHLAL_YOK", "GORUNMUYOR")
PROMPT = (
    "Bu videoda yalniz su ISG kuralini olc: Bir calisan, vincle havada ASILI "
    "tasinan yukun dogrudan DUSME BOLGESINDE en az 1 saniye kaliyor mu? "
    "IHLAL_VAR yalniz su uc kosul birlikte acikca goruluyorsa secilir: "
    "(1) yuk gercekten havada asilidir, (2) calisan yukun dogrudan altindaki "
    "dusme bolgesindedir, (3) bu durum en az 1 saniye surer. Calisan yalnizca "
    "yakinindaysa, bariyer arkasindaysa, perspektif altindaymis gibi gosteriyorsa, "
    "yuk yerdeyse veya gecis 1 saniyeden kisaysa IHLAL_YOK sec. Uc kosuldan biri "
    "goruntuden guvenilir bicimde olculemiyorsa GORUNMUYOR sec. Yalniz etiketi yaz."
)
GATES = {
    "recall_min": 0.90,
    "precision_min": 0.90,
    "false_positive_rate_max": 0.10,
    "coverage_min": 0.90,
    "strict_accuracy_min": 0.90,
}


def model_sozlesmesini_dogrula() -> dict:
    actual = {role: settings.gorev_modeli(role) for role in MODEL_CONTRACT}
    if not settings.uzak_api_mi or settings.base_url.rstrip("/") != PRIVATE_API_BASE:
        raise RuntimeError(f"Yalniz sabit ozel API kabul edilir: {settings.base_url!r}")
    mismatch = {k: {"actual": actual[k], "expected": v}
                for k, v in MODEL_CONTRACT.items() if actual[k] != v}
    if mismatch:
        raise RuntimeError(f"Sabit model sozlesmesi bozuldu: {mismatch}")
    return {"base_url": settings.base_url, **actual}


def tier1_etiketleri(path: Path = LABEL_PATH) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        source = [r for r in csv.DictReader(f) if r.get("tier") == "1"]
    rows = []
    for r in source:
        labels = [r.get(f"labeler_{i}_label", "").strip()
                  for i in range(1, 4) if r.get(f"labeler_{i}_label", "").strip()]
        resolved = r.get("resolved_label", "")
        if len(labels) < 2 or any(x != resolved for x in labels):
            raise RuntimeError(f"Tier-1 tam uzlasi yok: {r.get('filename')}")
        if resolved not in {"True_Positive", "False_Positive"}:
            raise RuntimeError(f"Bilinmeyen etiket: {resolved!r}")
        rows.append({
            "filename": r["filename"],
            "target": "unsafe" if resolved == "True_Positive" else "safe",
            "num_labelers": len(labels),
        })
    if len(rows) != 150:
        raise RuntimeError(f"Tier-1 n=150 olmali, bulunan={len(rows)}")
    counts = {x: sum(r["target"] == x for r in rows) for x in ("unsafe", "safe")}
    if counts != {"unsafe": 76, "safe": 74}:
        raise RuntimeError(f"Beklenmeyen sinif dagilimi: {counts}")
    return rows


def _rate(k: int, n: int) -> dict:
    if n <= 0:
        return {"k": k, "n": n, "rate": None, "wilson95": [None, None]}
    lo, hi = wilson_ci(k, n)
    return {"k": k, "n": n, "rate": k / n, "wilson95": [lo, hi]}


def _prediction(raw: str | None, error: str | None = None) -> str:
    if error or raw is None:
        return "error"
    answer = raw.strip().upper()
    return answer if answer in CHOICES else "error"


def puanla(rows: Iterable[dict]) -> dict:
    rows = list(rows)
    tp = sum(r["target"] == "unsafe" and r["prediction"] == "IHLAL_VAR" for r in rows)
    fp = sum(r["target"] == "safe" and r["prediction"] == "IHLAL_VAR" for r in rows)
    tn = sum(r["target"] == "safe" and r["prediction"] == "IHLAL_YOK" for r in rows)
    fn_decided = sum(r["target"] == "unsafe" and r["prediction"] == "IHLAL_YOK" for r in rows)
    abstain_pos = sum(r["target"] == "unsafe" and r["prediction"] in {"GORUNMUYOR", "error"}
                      for r in rows)
    abstain_neg = sum(r["target"] == "safe" and r["prediction"] in {"GORUNMUYOR", "error"}
                      for r in rows)
    pos = sum(r["target"] == "unsafe" for r in rows)
    neg = sum(r["target"] == "safe" for r in rows)
    decided = sum(r["prediction"] in {"IHLAL_VAR", "IHLAL_YOK"} for r in rows)
    strict_correct = tp + tn
    precision_n = tp + fp
    out = {
        "n": len(rows),
        "confusion": {
            "tp": tp, "fp": fp, "tn": tn, "fn_decided": fn_decided,
            "abstain_or_error_positive": abstain_pos,
            "abstain_or_error_negative": abstain_neg,
        },
        "recall_strict": _rate(tp, pos),
        "precision": _rate(tp, precision_n),
        "false_positive_rate": _rate(fp, neg),
        "specificity_strict": _rate(tn, neg),
        "coverage": _rate(decided, len(rows)),
        "strict_accuracy": _rate(strict_correct, len(rows)),
        "selective_accuracy": _rate(strict_correct, decided),
        "abstention_or_error": _rate(len(rows) - decided, len(rows)),
    }
    rates = {k: v["rate"] for k, v in out.items() if isinstance(v, dict) and "rate" in v}
    checks = {
        "recall": rates["recall_strict"] is not None and rates["recall_strict"] >= GATES["recall_min"],
        "precision": rates["precision"] is not None and rates["precision"] >= GATES["precision_min"],
        "false_positive_rate": rates["false_positive_rate"] is not None and rates["false_positive_rate"] <= GATES["false_positive_rate_max"],
        "coverage": rates["coverage"] is not None and rates["coverage"] >= GATES["coverage_min"],
        "strict_accuracy": rates["strict_accuracy"] is not None and rates["strict_accuracy"] >= GATES["strict_accuracy_min"],
    }
    out["acceptance"] = {"gates": GATES, "checks": checks, "pass": all(checks.values())}
    return out


def _generator(filename: str) -> str:
    return filename.rsplit("_", 1)[0]


def _probe(item: dict) -> dict:
    path = DATA_ROOT / "videos" / item["filename"]
    t0 = time.perf_counter()
    error = None
    raw = None
    usage = None
    retries = None
    try:
        client = VLMClient().gorev("algi")
        session = client.video_oturumu(
            str(path), system=GOZLEM_SISTEM,
            giris_metni="Bu videoyu gorsel bir olcum icin incele.",
        )
        raw = session.sor(
            PROMPT,
            guided_choice=CHOICES,
            temperature=0.0,
            max_tokens=8,
            hatirla=False,
        )
        error = session.hata
        usage = getattr(client, "son_kullanim", None)
        retries = getattr(client, "son_deneme_sayisi", None)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    return {
        **item,
        "generator": _generator(item["filename"]),
        "prediction": _prediction(raw, error),
        "raw": raw,
        "error": error,
        "latency_s": round(time.perf_counter() - t0, 3),
        "usage": usage,
        "retries": retries,
    }


def _run_key(items: list[dict], contract: dict) -> str:
    body = json.dumps({
        "repo": REPO_ID,
        "revision": REVISION,
        "files": [x["filename"] for x in items],
        "prompt": PROMPT,
        "choices": CHOICES,
        "contract": contract,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="Yalniz tesisat/duman testi; nihai rapor icin 0")
    args = parser.parse_args()

    contract = model_sozlesmesini_dogrula()
    items = tier1_etiketleri()
    if args.limit:
        items = items[:args.limit]
    missing = [x["filename"] for x in items if not (DATA_ROOT / "videos" / x["filename"]).is_file()]
    if missing:
        raise RuntimeError(f"Eksik video ({len(missing)}): once scripts/get_synthsite_tier1.py calistir")

    RESULTS.mkdir(parents=True, exist_ok=True)
    key = _run_key(items, contract)
    journal = RESULTS / f".synthsite_tier1_{key}.jsonl"
    completed: dict[str, dict] = {}
    if journal.exists():
        for line in journal.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("filename"):
                completed[row["filename"]] = row

    pending = [x for x in items if x["filename"] not in completed]
    print(f"SynthSite Tier-1: n={len(items)}, kalan={len(pending)}, workers={args.workers}")
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(_probe, item): item for item in pending}
        for i, future in enumerate(as_completed(futures), start=1):
            row = future.result()
            completed[row["filename"]] = row
            with journal.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            print(f"[{i}/{len(pending)}] {row['filename']}: {row['prediction']} ({row['latency_s']}s)")

    rows = [completed[x["filename"]] for x in items]
    metrics = puanla(rows)
    slices = {}
    for generator in sorted({r["generator"] for r in rows}):
        slices[generator] = puanla([r for r in rows if r["generator"] == generator])
    output = {
        "benchmark": "SynthSite Tier-1 suspended-load rule",
        "created_at": datetime.now().astimezone().isoformat(),
        "dataset": {
            "repo_id": REPO_ID,
            "revision": REVISION,
            "selection": "tier == 1; two-or-more human reviewers unanimous",
            "n": len(rows),
            "unsafe": sum(r["target"] == "unsafe" for r in rows),
            "safe": sum(r["target"] == "safe" for r in rows),
            "tier2_excluded": True,
        },
        "inference": {
            "learned_inference": "special_api_only",
            "model_contract": contract,
            "role_used": "algi",
            "model_used": contract["algi"],
            "temperature": 0.0,
            "prompt": PROMPT,
            "prompt_sha256": hashlib.sha256(PROMPT.encode("utf-8")).hexdigest(),
            "choices": list(CHOICES),
        },
        "metrics": metrics,
        "slices_by_generator": slices,
        "rows": rows,
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = RESULTS / f"synthsite_tier1_{stamp}.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(target)


if __name__ == "__main__":
    main()
