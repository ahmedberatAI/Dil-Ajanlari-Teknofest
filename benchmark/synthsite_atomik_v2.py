#!/usr/bin/env python
"""SynthSite Tier-1 atomik askıda-yük benchmarkı.

Öğrenilmiş çıkarım yalnız sabit özel API ve sabit üç model aliası üzerinden
yapılır. Tek birleşik karar yerine varlık/olgu (`vlm`) ve ilişki/zaman
(`llm-large`) bağımsız, kapalı cevap uzaylarında ölçülür; son karar kodda AND'dir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from benchmark.synthsite_tier1 import (  # noqa: E402
    DATA_ROOT, GATES, MODEL_CONTRACT, PRIVATE_API_BASE, RESULTS, REVISION,
    REPO_ID, _generator, model_sozlesmesini_dogrula, puanla, tier1_etiketleri,
)
from dilajan.isg_kanit import (  # noqa: E402
    ATOMIK_SISTEM, Hukum, SPEKLER, sonuclandir,
)
from dilajan.llm_client import VLMClient  # noqa: E402

PIPELINE_REVISION = "synthsite-atomic-v2"
FAMILY = "askıda yük/düşme bölgesi"
SPEC = SPEKLER[FAMILY]


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _prediction(result) -> str:
    if result.hatalar:
        return "error"
    if result.hukum == Hukum.SUPPORTED:
        return "IHLAL_VAR"
    if result.hukum == Hukum.REFUTED:
        return "IHLAL_YOK"
    return "GORUNMUYOR"


def _development_subset(items: list[dict], limit: int) -> list[dict]:
    """Etiketten dengeli, dosya-adı hash'iyle deterministik geliştirme dilimi."""
    if not limit or limit >= len(items):
        return list(items)
    hedefler = {"unsafe": (limit + 1) // 2, "safe": limit // 2}
    out = []
    for target, n in hedefler.items():
        aday = [x for x in items if x["target"] == target]
        aday.sort(key=lambda x: hashlib.sha256(x["filename"].encode()).hexdigest())
        out.extend(aday[:n])
    return sorted(out, key=lambda x: hashlib.sha256(x["filename"].encode()).hexdigest())


def _probe(item: dict) -> dict:
    path = DATA_ROOT / "videos" / item["filename"]
    started = time.perf_counter()
    answers: dict[str, str] = {}
    errors: dict[str, str] = {}
    calls = []
    for question in SPEC.sorular:
        t0 = time.perf_counter()
        raw = None
        error = None
        usage = None
        retries = None
        try:
            client = VLMClient().gorev(question.gorev)
            session = client.video_oturumu(
                str(path), system=ATOMIK_SISTEM,
                giris_metni="Bu videoyu adli bir ISG olcumu icin kronolojik incele.")
            raw = session.sor(
                question.soru,
                guided_choice=question.secenekler,
                temperature=0.0, max_tokens=12, hatirla=False)
            error = session.hata
            usage = getattr(client, "son_kullanim", None)
            retries = getattr(client, "son_deneme_sayisi", None)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        if error:
            errors[question.ad] = str(error)
        else:
            answers[question.ad] = str(raw or "").strip().upper()
        calls.append({
            "atom": question.ad,
            "role": question.gorev,
            "model": MODEL_CONTRACT[question.gorev],
            "raw": raw,
            "error": error,
            "latency_s": round(time.perf_counter() - t0, 3),
            "usage": usage,
            "retries": retries,
        })
    result = sonuclandir(SPEC, answers, errors)
    return {
        **item,
        "generator": _generator(item["filename"]),
        "video_sha256": _sha_file(path),
        "prediction": _prediction(result),
        "judgment": result.hukum.value,
        "answers": result.cevaplar,
        "errors": result.hatalar,
        "calls": calls,
        "latency_s": round(time.perf_counter() - started, 3),
    }


def _spec_manifest() -> list[dict]:
    return [{
        "atom": q.ad, "role": q.gorev, "model": MODEL_CONTRACT[q.gorev],
        "prompt": q.soru, "prompt_sha256": hashlib.sha256(q.soru.encode()).hexdigest(),
        "choices": list(q.secenekler), "support": sorted(q.destek),
        "refute": sorted(q.curutme),
    } for q in SPEC.sorular]


def _run_key(items: list[dict], contract: dict) -> str:
    body = json.dumps({
        "pipeline_revision": PIPELINE_REVISION,
        "dataset_revision": REVISION,
        "label_sha256": _sha_file(DATA_ROOT / "synthetic_video_labels.csv"),
        "files": [x["filename"] for x in items],
        "contract": contract,
        "system_sha256": hashlib.sha256(ATOMIK_SISTEM.encode()).hexdigest(),
        "atoms": _spec_manifest(),
    }, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()[:12]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0,
                        help="Etiketten dengeli geliştirme dilimi; 0=tüm Tier-1")
    args = parser.parse_args()

    contract = model_sozlesmesini_dogrula()
    if contract["base_url"].rstrip("/") != PRIVATE_API_BASE:
        raise RuntimeError("Özel API sözleşmesi bozuldu")
    all_items = tier1_etiketleri()
    items = _development_subset(all_items, args.limit)
    missing = [x["filename"] for x in items
               if not (DATA_ROOT / "videos" / x["filename"]).is_file()]
    if missing:
        raise RuntimeError(f"Eksik video ({len(missing)})")

    RESULTS.mkdir(parents=True, exist_ok=True)
    key = _run_key(items, contract)
    journal = RESULTS / f".synthsite_atomik_v2_{key}.jsonl"
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
    print(f"SynthSite atomic v2: n={len(items)}, kalan={len(pending)}, workers={args.workers}")
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(_probe, item): item for item in pending}
        for i, future in enumerate(as_completed(futures), start=1):
            row = future.result()
            completed[row["filename"]] = row
            with journal.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            print(f"[{i}/{len(pending)}] {row['filename']}: {row['prediction']} "
                  f"{row['answers']} ({row['latency_s']}s)")

    rows = [completed[x["filename"]] for x in items]
    metrics = puanla(rows)
    slices = {generator: puanla([r for r in rows if r["generator"] == generator])
              for generator in sorted({r["generator"] for r in rows})}
    output = {
        "benchmark": "SynthSite Tier-1 suspended-load atomic v2",
        "created_at": datetime.now().astimezone().isoformat(),
        "development_only": True,
        "independent_holdout": False,
        "contamination_note": "Tier-1 sonuçları daha önce görüldü; yalnız mimari geliştirme ölçümüdür.",
        "dataset": {
            "repo_id": REPO_ID, "revision": REVISION,
            "labels_sha256": _sha_file(DATA_ROOT / "synthetic_video_labels.csv"),
            "selection": "tier==1; unanimous humans; deterministic class-balanced subset",
            "n": len(rows), "unsafe": sum(r["target"] == "unsafe" for r in rows),
            "safe": sum(r["target"] == "safe" for r in rows),
        },
        "inference": {
            "learned_inference": "special_api_only", "model_contract": contract,
            "pipeline_revision": PIPELINE_REVISION, "temperature": 0.0,
            "system_prompt": ATOMIK_SISTEM,
            "system_sha256": hashlib.sha256(ATOMIK_SISTEM.encode()).hexdigest(),
            "atoms": _spec_manifest(), "decision": "deterministic AND",
        },
        "gates": GATES,
        "metrics": metrics,
        "slices_by_generator": slices,
        "rows": rows,
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = RESULTS / f"synthsite_atomik_v2_{stamp}.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(target)


if __name__ == "__main__":
    main()
