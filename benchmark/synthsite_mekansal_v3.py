#!/usr/bin/env python
"""SynthSite v3: atomik v2 üzerine kontrastif mekânsal karşı-kanıt kapısı."""
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

from benchmark.synthsite_atomik_v2 import (  # noqa: E402
    ATOMIK_SISTEM, DATA_ROOT, MODEL_CONTRACT, RESULTS, _development_subset,
    _sha_file, model_sozlesmesini_dogrula, puanla, tier1_etiketleri,
)
from dilajan.llm_client import VLMClient  # noqa: E402

PIPELINE_REVISION = "synthsite-spatial-contrast-v3"
CHOICES = (
    "DOGRUDAN_DUSUM_BOLGESI", "YALNIZ_YAKIN_YAN_TARAFTA",
    "FARKLI_DERINLIK", "FIZIKSEL_ENGEL_ARKASI", "ASILI_YUK_YOK",
    "KISI_YOK", "GORUNMUYOR",
)
PROMPT = (
    "Bu bir tehlike tahmini degil, yalniz mekansal geometri olcumudur. Videoyu "
    "kronolojik karsilastir. Gercekten havada asili yukun YATAY SILUETINI ve en "
    "yakin calisanin AYAK/GOVDE noktasini bul. Yuk hic yana kaymadan dikey olarak "
    "inse, katı yuk govdesi ayni derinlikteki calisanin govdesine/ayak noktasina "
    "ulasir mi? Yalniz bu cakisma birden fazla anda acik ve arada fiziksel engel "
    "yoksa DOGRUDAN_DUSUM_BOLGESI sec.\n\n"
    "Karsit ornekler (bunlar ihlal DEGILDIR): (1) yuk kadrajin ust-ortasinda, "
    "calisan alt-on planda ve aralarinda belirgin derinlik/mesafe varsa "
    "FARKLI_DERINLIK; (2) calisan yukun hemen yaninda ama dikey izdüşüm disindaysa "
    "YALNIZ_YAKIN_YAN_TARAFTA; (3) mavi/celik bariyer, korkuluk, duvar veya kapali "
    "alan ayiriyorsa FIZIKSEL_ENGEL_ARKASI; (4) kanca yukarida olsa da kiris/istif "
    "zemin, arac veya destek ustundeyse ASILI_YUK_YOK. Insaat sahnesi olmasindan "
    "veya vinc-kisi birlikte gorunmesinden ihlal varsayma. Perspektifte ust uste "
    "gorunmek ayni derinlik kaniti degildir. Kisi yoksa KISI_YOK; ayak noktasi, "
    "yuk siniri veya derinlik secilemiyorsa GORUNMUYOR. Yalniz etiketi yaz."
)


def _spatial_prediction(raw: str | None, error: str | None) -> str:
    if error or raw is None:
        return "error"
    value = raw.strip().upper()
    return value if value in CHOICES else "error"


def _combine(base: str, spatial: str) -> str:
    if base == "error" or spatial == "error":
        return "error"
    if base == "IHLAL_YOK":
        return "IHLAL_YOK"
    if base == "GORUNMUYOR" or spatial == "GORUNMUYOR":
        return "GORUNMUYOR"
    if base == "IHLAL_VAR" and spatial == "DOGRUDAN_DUSUM_BOLGESI":
        return "IHLAL_VAR"
    return "IHLAL_YOK"


def _probe(item: dict, base_row: dict) -> dict:
    path = DATA_ROOT / "videos" / item["filename"]
    t0 = time.perf_counter()
    raw = None
    error = None
    usage = None
    retries = None
    try:
        client = VLMClient().gorev("algi")
        session = client.video_oturumu(
            str(path), system=ATOMIK_SISTEM,
            giris_metni="Bu videoyu mekansal bir ISG kanit olcumu icin incele.")
        raw = session.sor(PROMPT, guided_choice=CHOICES, temperature=0.0,
                          max_tokens=12, hatirla=False)
        error = session.hata
        usage = getattr(client, "son_kullanim", None)
        retries = getattr(client, "son_deneme_sayisi", None)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    spatial = _spatial_prediction(raw, error)
    return {
        **item,
        "generator": base_row["generator"],
        "video_sha256": base_row["video_sha256"],
        "base_prediction": base_row["prediction"],
        "base_answers": base_row["answers"],
        "spatial": spatial,
        "spatial_raw": raw,
        "error": error,
        "prediction": _combine(base_row["prediction"], spatial),
        "latency_s": round(time.perf_counter() - t0, 3),
        "usage": usage, "retries": retries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="Atomik v2 JSON sonucu")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    contract = model_sozlesmesini_dogrula()
    base_path = Path(args.base)
    base_doc = json.loads(base_path.read_text(encoding="utf-8"))
    base_rows = {x["filename"]: x for x in base_doc["rows"]}
    items = _development_subset(tier1_etiketleri(), len(base_rows))
    if set(base_rows) != {x["filename"] for x in items}:
        raise RuntimeError("v2 tabanı ile deterministik geliştirme dilimi eşleşmiyor")

    key_body = json.dumps({
        "revision": PIPELINE_REVISION, "base_sha256": _sha_file(base_path),
        "prompt": PROMPT, "choices": CHOICES, "contract": contract,
        "files": sorted(base_rows),
    }, ensure_ascii=False, sort_keys=True)
    key = hashlib.sha256(key_body.encode()).hexdigest()[:12]
    journal = RESULTS / f".synthsite_mekansal_v3_{key}.jsonl"
    completed = {}
    if journal.exists():
        for line in journal.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("filename"):
                completed[row["filename"]] = row
    pending = [x for x in items if x["filename"] not in completed]
    print(f"SynthSite spatial v3: n={len(items)}, kalan={len(pending)}, workers={args.workers}")
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(_probe, item, base_rows[item["filename"]]): item
                   for item in pending}
        for i, future in enumerate(as_completed(futures), 1):
            row = future.result()
            completed[row["filename"]] = row
            with journal.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush(); os.fsync(fh.fileno())
            print(f"[{i}/{len(pending)}] {row['filename']}: {row['spatial']} "
                  f"=> {row['prediction']} ({row['latency_s']}s)")
    rows = [completed[x["filename"]] for x in items]
    metrics = puanla(rows)
    out = {
        "benchmark": "SynthSite spatial contrast v3 development",
        "created_at": datetime.now().astimezone().isoformat(),
        "development_only": True, "independent_holdout": False,
        "base_result": str(base_path), "base_sha256": _sha_file(base_path),
        "inference": {"learned_inference": "special_api_only",
                      "model_contract": contract, "role_used": "algi",
                      "pipeline_revision": PIPELINE_REVISION, "prompt": PROMPT,
                      "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
                      "choices": list(CHOICES), "decision": "v2 AND spatial"},
        "metrics": metrics, "rows": rows,
    }
    target = RESULTS / f"synthsite_mekansal_v3_{datetime.now():%Y%m%d_%H%M%S}.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2)); print(target)


if __name__ == "__main__":
    main()
