#!/usr/bin/env python
"""SynthSite v4: nötr VLM kanıt defteri + metin-temelli llm-large hakemi."""
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

PIPELINE_REVISION = "synthsite-neutral-evidence-ledger-v4"
LEDGER_SCHEMA = {
    "type": "object",
    "properties": {
        "yuk_destek_gozlemi": {"type": "string"},
        "en_yakin_calisan_gozlemi": {"type": "string"},
        "engel_derinlik_gozlemi": {"type": "string"},
        "zamansal_gozlem": {"type": "string"},
        "bilinmeyenler": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["yuk_destek_gozlemi", "en_yakin_calisan_gozlemi",
                 "engel_derinlik_gozlemi", "zamansal_gozlem", "bilinmeyenler"],
    "additionalProperties": False,
}
LEDGER_PROMPT = (
    "Tehlike, risk, ihlal veya güvenli/guvensiz karari VERME. Videoyu en erken, "
    "orta ve en gec anlarda karsilastirip yalniz dogrudan gorulen kaniti yaz. "
    "(1) Kancaya/sapana bagli kati yuk gercekten havada mi, yoksa zemin/arac/istif "
    "tarafindan destekli mi? (2) En yakin calisanin ayak ve govde konumu yukun "
    "yatay siluetinin altinda mi, yaninda mi; on/arka plan ayrimi goruluyor mu? "
    "(3) Arada korkuluk, bariyer, duvar, kapali alan veya belirgin derinlik ayrimi "
    "var mi? (4) Bu gorulen iliski kac farkli anda ve yaklasik kac saniye suruyor? "
    "Insaat sahnesinden, vinc-kisi birlikteliginden veya niyetten sonuc cikarma. "
    "Gorulmeyeni bilinmeyenler listesine yaz; koordinat ve olay uydurma."
)
JUDGE_CHOICES = ("KANIT_UYUMLU", "ACIK_KARSI_KANIT", "KANIT_YETERSIZ")
JUDGE_SYSTEM = (
    "Sen yalniz verilen görsel kanıt defterini denetleyen bir ISG mantık hakemisin. "
    "Videoyu görmüyorsun; defterde yazmayan olguyu varsayma. Çelişkili veya eksik "
    "defteri olumlu sayma. Açıklamasız yalnız izin verilen etiketi yaz."
)
JUDGE_PROMPT = (
    "Kuralın fiziksel önkoşulları: gerçek yük havada asılı olmalı; çalışanın gövdesi/"
    "ayak noktası yükün dikey düşme veya salınım bölgesinde olmalı; arada koruyucu "
    "engel/ayrı derinlik olmamalı; bu ilişki en az 1 saniye görünmeli.\n"
    "ACIK_KARSI_KANIT: defter yükün destekli/yok olduğunu, çalışanın yalnız yanda/"
    "farklı derinlikte olduğunu, arada engel bulunduğunu veya geçişin <1 sn olduğunu "
    "açıkça söylüyorsa. KANIT_UYUMLU: defter dört önkoşulu da açık ve çelişkisiz "
    "destekliyorsa. Bunların dışında KANIT_YETERSIZ.\n\nKANIT DEFTERI:\n{ledger}"
)


def _judge_prediction(raw: str | None, error: str | None) -> str:
    if error or raw is None:
        return "error"
    value = raw.strip().upper()
    return value if value in JUDGE_CHOICES else "error"


def _combine(base: str, judge: str) -> str:
    if base == "error" or judge == "error":
        return "error"
    if base == "IHLAL_YOK" or judge == "ACIK_KARSI_KANIT":
        return "IHLAL_YOK"
    if base == "GORUNMUYOR" or judge == "KANIT_YETERSIZ":
        return "GORUNMUYOR"
    return "IHLAL_VAR" if judge == "KANIT_UYUMLU" else "error"


def _rotated_choices(filename: str) -> tuple[str, ...]:
    """Structured-output seçenek sırası tüm kümede tek yönde yanlı olmasın."""
    n = int(hashlib.sha256(filename.encode()).hexdigest(), 16) % len(JUDGE_CHOICES)
    return JUDGE_CHOICES[n:] + JUDGE_CHOICES[:n]


def _probe(item: dict, base_row: dict) -> dict:
    path = DATA_ROOT / "videos" / item["filename"]
    started = time.perf_counter()
    ledger_raw = None
    ledger_error = None
    judge_raw = None
    judge_error = None
    try:
        perception = VLMClient().gorev("algi")
        session = perception.video_oturumu(
            str(path), system=ATOMIK_SISTEM,
            giris_metni="Bu video için tarafsız fiziksel kanıt defteri çıkar.")
        ledger_raw = session.sor(
            LEDGER_PROMPT, temperature=0.0, max_tokens=420, hatirla=False,
            json_schema=LEDGER_SCHEMA, schema_name="isg_kanit_defteri")
        ledger_error = session.hata
        if not ledger_error:
            json.loads(ledger_raw or "")
    except Exception as exc:
        ledger_error = f"{type(exc).__name__}: {exc}"

    judge = "error"
    if not ledger_error and ledger_raw:
        try:
            reasoning = VLMClient().gorev("olay")
            judge_raw = reasoning.chat([
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": JUDGE_PROMPT.format(ledger=ledger_raw)},
            ], temperature=0.0, max_tokens=12,
                guided_choice=_rotated_choices(item["filename"]))
        except Exception as exc:
            judge_error = f"{type(exc).__name__}: {exc}"
        judge = _judge_prediction(judge_raw, judge_error)
    return {
        **item, "generator": base_row["generator"],
        "video_sha256": base_row["video_sha256"],
        "base_prediction": base_row["prediction"], "base_answers": base_row["answers"],
        "ledger": ledger_raw, "ledger_error": ledger_error,
        "judge": judge, "judge_raw": judge_raw, "judge_error": judge_error,
        "judge_choice_order": list(_rotated_choices(item["filename"])),
        "prediction": _combine(base_row["prediction"], judge),
        "latency_s": round(time.perf_counter() - started, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    contract = model_sozlesmesini_dogrula()
    base_path = Path(args.base)
    base_doc = json.loads(base_path.read_text(encoding="utf-8"))
    base_rows = {x["filename"]: x for x in base_doc["rows"]}
    items = _development_subset(tier1_etiketleri(), len(base_rows))
    if set(base_rows) != {x["filename"] for x in items}:
        raise RuntimeError("v2 tabanı ile geliştirme dilimi eşleşmiyor")
    key_body = json.dumps({
        "revision": PIPELINE_REVISION, "base_sha256": _sha_file(base_path),
        "ledger_prompt": LEDGER_PROMPT, "ledger_schema": LEDGER_SCHEMA,
        "judge_prompt": JUDGE_PROMPT, "judge_choices": JUDGE_CHOICES,
        "contract": contract, "files": sorted(base_rows),
    }, ensure_ascii=False, sort_keys=True)
    key = hashlib.sha256(key_body.encode()).hexdigest()[:12]
    journal = RESULTS / f".synthsite_ledger_v4_{key}.jsonl"
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
    print(f"SynthSite ledger v4: n={len(items)}, kalan={len(pending)}, workers={args.workers}")
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(_probe, item, base_rows[item["filename"]]): item
                   for item in pending}
        for i, future in enumerate(as_completed(futures), 1):
            row = future.result(); completed[row["filename"]] = row
            with journal.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n"); fh.flush(); os.fsync(fh.fileno())
            print(f"[{i}/{len(pending)}] {row['filename']}: {row['judge']} "
                  f"=> {row['prediction']} ({row['latency_s']}s)")
    rows = [completed[x["filename"]] for x in items]
    metrics = puanla(rows)
    out = {
        "benchmark": "SynthSite neutral evidence ledger v4 development",
        "created_at": datetime.now().astimezone().isoformat(),
        "development_only": True, "independent_holdout": False,
        "base_result": str(base_path), "base_sha256": _sha_file(base_path),
        "inference": {"learned_inference": "special_api_only",
                      "model_contract": contract, "pipeline_revision": PIPELINE_REVISION,
                      "ledger_prompt": LEDGER_PROMPT, "ledger_schema": LEDGER_SCHEMA,
                      "judge_system": JUDGE_SYSTEM, "judge_prompt": JUDGE_PROMPT,
                      "judge_choices": list(JUDGE_CHOICES),
                      "decision": "v2 AND neutral-ledger judge"},
        "metrics": metrics, "rows": rows,
    }
    target = RESULTS / f"synthsite_ledger_v4_{datetime.now():%Y%m%d_%H%M%S}.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2)); print(target)


if __name__ == "__main__":
    main()
