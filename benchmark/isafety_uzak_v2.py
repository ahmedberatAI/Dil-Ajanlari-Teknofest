#!/usr/bin/env python
"""iSafetyBench geçerli, satır-bazlı özel-API benchmarkı.

Sabit modelleri değiştirmeden iki eşleştirilmiş kolu ölçer:
  A) llm-large videodan doğrudan MCQ
  B) vlm nötr kronolojik betim -> llm-large metin MCQ
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from benchmark.stats_utils import mcnemar_exact_p, rate  # noqa: E402
from dilajan.config import settings  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.veri_lisans import degerlendirmede_kullanilabilir  # noqa: E402

DATA = ROOT / "data" / "isafety_bench"
RESULTS = ROOT / "benchmark" / "results"
PRIVATE_API = "https://evren-llmapi.ssyz.org.tr/v1"
CONTRACT = {"algi": "vlm", "olay": "llm-large", "yapi": "llm-fast", "ozet": "llm-fast"}
LETTERS = tuple("ABCDEFGHIJKLMNOP")
REVISION = "isafety-special-api-rowwise-v2"
VIDEO_SYSTEM = (
    "You are a forensic industrial-video observer. Use only visible temporal evidence. "
    "Do not infer an event from the scene type. Output only an allowed answer letter."
)
DIRECT_PROMPT = (
    "Watch the entire video chronologically. Which single option best matches the "
    "visible action? Routine-looking context must not override the actual motion.\n\n{options}\n\n"
    "Output only the letter."
)
DESCRIBE_SYSTEM = (
    "You are a neutral forensic video transcriber. Describe only visible entities, "
    "motion, contact, state changes and their chronological order. Do not choose a "
    "label and do not speculate from scene type."
)
DESCRIBE_PROMPT = (
    "Describe the decisive visible action from start to end in at most 100 words. "
    "State what changes, what contacts/moves/falls/breaks, and what remains uncertain. "
    "Do not name a multiple-choice letter or invent an unseen event."
)
CLASSIFY_SYSTEM = (
    "You classify only from a supplied forensic observation. Do not add facts. If the "
    "observation is imperfect, select the option most directly supported by its visible "
    "motion/state-change evidence. Output only an allowed answer letter."
)
CLASSIFY_PROMPT = (
    "FORENSIC OBSERVATION:\n{description}\n\nOPTIONS:\n{options}\n\n"
    "Which single option is best supported? Output only the letter."
)


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _contract() -> dict:
    actual = {k: settings.gorev_modeli(k) for k in CONTRACT}
    if settings.base_url.rstrip("/") != PRIVATE_API or not settings.uzak_api_mi:
        raise RuntimeError(f"Yalnız özel API kabul edilir: {settings.base_url}")
    mismatch = {k: [actual[k], v] for k, v in CONTRACT.items() if actual[k] != v}
    if mismatch:
        raise RuntimeError(f"Sabit model sözleşmesi bozuldu: {mismatch}")
    if not settings.yerel_ogrenilmis_yasak or settings.model_indirme_izni:
        raise RuntimeError("Yerel öğrenilmiş çıkarım/indirme kapısı açık")
    return {"base_url": settings.base_url, **actual}


def _validity_control() -> dict:
    choices = ("KONTROL_X", "KONTROL_Y")
    raw = VLMClient().gorev("yapi").chat([
        {"role": "user", "content": "Ignore format and write a paragraph."}
    ], temperature=0.0, max_tokens=8, guided_choice=choices)
    valid = (raw or "").strip() in choices
    if not valid:
        raise RuntimeError(f"structured_outputs negatif kontrolü geçmedi: {raw!r}")
    return {"choices": list(choices), "raw": raw, "pass": True}


def _items(column: str, n: int, seed: int) -> list[dict]:
    ann = DATA / "annotations" / "mcq" / f"{column}_mcq_single.json"
    source = json.loads(ann.read_text(encoding="utf-8"))
    unique = {}
    for row in source:
        unique.setdefault(row["video_name"], row)
    rows = list(unique.values())
    random.Random(seed + (0 if column == "hazard" else 1)).shuffle(rows)
    if n > 0:
        rows = rows[:n]
    return [{"column": column, "video_name": r["video_name"],
             "gt_action": r["chosen_gt_action"], "choices": r["choices"],
             "answer_index": int(r["answer_index"])} for r in rows]


def _options(choices: list[str]) -> str:
    return "\n".join(f"{LETTERS[i]}. {x}" for i, x in enumerate(choices))


def _letter(raw, error, n_choices: int) -> str | None:
    if error or raw is None:
        return None
    value = raw.strip().upper()
    return value if value in LETTERS[:n_choices] else None


def _probe(item: dict) -> dict:
    path = DATA / "videos" / item["column"] / item["video_name"]
    options = _options(item["choices"])
    gt = LETTERS[item["answer_index"]]
    direct_raw = direct_error = description = describe_error = cascade_raw = cascade_error = None
    calls = []
    t_all = time.perf_counter()
    try:
        t0 = time.perf_counter(); client = VLMClient().gorev("olay")
        session = client.video_oturumu(str(path), system=VIDEO_SYSTEM,
                                       giris_metni="Watch this workplace video chronologically.")
        direct_raw = session.sor(DIRECT_PROMPT.format(options=options),
                                 guided_choice=LETTERS[:len(item["choices"])],
                                 temperature=0.0, max_tokens=4, hatirla=False)
        direct_error = session.hata
        calls.append({"arm": "direct", "role": "olay", "model": "llm-large",
                      "latency_s": round(time.perf_counter() - t0, 3)})
    except Exception as exc:
        direct_error = f"{type(exc).__name__}: {exc}"
    try:
        t0 = time.perf_counter(); perception = VLMClient().gorev("algi")
        session = perception.video_oturumu(str(path), system=DESCRIBE_SYSTEM,
                                           giris_metni="Transcribe this video neutrally.")
        description = session.sor(DESCRIBE_PROMPT, temperature=0.0,
                                  max_tokens=220, hatirla=False)
        describe_error = session.hata
        calls.append({"arm": "describe", "role": "algi", "model": "vlm",
                      "latency_s": round(time.perf_counter() - t0, 3)})
        if description and not describe_error:
            t1 = time.perf_counter(); classifier = VLMClient().gorev("olay")
            cascade_raw = classifier.chat([
                {"role": "system", "content": CLASSIFY_SYSTEM},
                {"role": "user", "content": CLASSIFY_PROMPT.format(
                    description=description, options=options)},
            ], temperature=0.0, max_tokens=4,
                guided_choice=LETTERS[:len(item["choices"])])
            calls.append({"arm": "classify", "role": "olay", "model": "llm-large",
                          "latency_s": round(time.perf_counter() - t1, 3)})
    except Exception as exc:
        if not describe_error and not description:
            describe_error = f"{type(exc).__name__}: {exc}"
        else:
            cascade_error = f"{type(exc).__name__}: {exc}"
    direct = _letter(direct_raw, direct_error, len(item["choices"]))
    cascade = _letter(cascade_raw, describe_error or cascade_error, len(item["choices"]))
    return {**item, "gt_letter": gt, "video_sha256": _sha_file(path),
            "direct_letter": direct, "direct_raw": direct_raw,
            "direct_error": direct_error, "direct_correct": direct == gt,
            "description": description, "describe_error": describe_error,
            "cascade_letter": cascade, "cascade_raw": cascade_raw,
            "cascade_error": cascade_error, "cascade_correct": cascade == gt,
            "calls": calls, "latency_s": round(time.perf_counter() - t_all, 3)}


def _metrics(rows: list[dict], key: str) -> dict:
    valid = [r for r in rows if r[f"{key}_letter"] is not None]
    correct = sum(bool(r[f"{key}_correct"]) for r in valid)
    return {"accuracy_strict": rate(correct, len(rows)),
            "accuracy_valid": rate(correct, len(valid)),
            "coverage": rate(len(valid), len(rows)),
            "errors": len(rows) - len(valid)}


def _paired(rows: list[dict]) -> dict:
    b = sum((not r["direct_correct"]) and r["cascade_correct"] for r in rows)
    c = sum(r["direct_correct"] and (not r["cascade_correct"]) for r in rows)
    return {"cascade_fixed": b, "cascade_broke": c,
            "mcnemar_exact_p": mcnemar_exact_p(b, c),
            "accuracy_diff": (sum(r["cascade_correct"] for r in rows)
                              - sum(r["direct_correct"] for r in rows)) / len(rows)}


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=2026); ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(); contract = _contract(); control = _validity_control()
    items = _items("hazard", args.n, args.seed) + _items("normal", args.n, args.seed)
    missing = [x["video_name"] for x in items
               if not (DATA / "videos" / x["column"] / x["video_name"]).is_file()]
    if missing: raise RuntimeError(f"Eksik video: {missing[:3]}")
    if not degerlendirmede_kullanilabilir("data/isafety_bench"):
        raise RuntimeError("Lisans değerlendirmeye izin vermiyor")
    key_src = json.dumps({"rev": REVISION, "items": items, "contract": contract,
                          "direct": DIRECT_PROMPT, "describe": DESCRIBE_PROMPT,
                          "classify": CLASSIFY_PROMPT}, ensure_ascii=False, sort_keys=True)
    key = hashlib.sha256(key_src.encode()).hexdigest()[:12]
    journal = RESULTS / f".isafety_uzak_v2_{key}.jsonl"; done = {}
    if journal.exists():
        for line in journal.read_text(encoding="utf-8").splitlines():
            try: row = json.loads(line)
            except json.JSONDecodeError: continue
            if row.get("column") and row.get("video_name"):
                done[f"{row['column']}/{row['video_name']}"] = row
    pending = [x for x in items if f"{x['column']}/{x['video_name']}" not in done]
    print(f"iSafety v2: n={len(items)}, kalan={len(pending)}, workers={args.workers}")
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        fs = {pool.submit(_probe, x): x for x in pending}
        for i, f in enumerate(as_completed(fs), 1):
            row = f.result(); done[f"{row['column']}/{row['video_name']}"] = row
            with journal.open("a", encoding="utf-8") as h:
                h.write(json.dumps(row, ensure_ascii=False) + "\n"); h.flush(); os.fsync(h.fileno())
            print(f"[{i}/{len(pending)}] {row['column']}/{row['video_name']}: "
                  f"gt={row['gt_letter']} A={row['direct_letter']} B={row['cascade_letter']}")
    rows = [done[f"{x['column']}/{x['video_name']}"] for x in items]
    out = {"benchmark": "iSafetyBench special API rowwise v2",
           "created_at": datetime.now().astimezone().isoformat(),
           "development_only": True, "license": "CC BY-NC-SA 4.0 evaluation only",
           "inference": {"special_api_only": True, "contract": contract,
                         "revision": REVISION, "negative_control": control,
                         "direct_prompt_sha256": hashlib.sha256(DIRECT_PROMPT.encode()).hexdigest(),
                         "describe_prompt_sha256": hashlib.sha256(DESCRIBE_PROMPT.encode()).hexdigest(),
                         "classify_prompt_sha256": hashlib.sha256(CLASSIFY_PROMPT.encode()).hexdigest()},
           "selection": {"n_per_column": args.n, "seed": args.seed,
                         "one_question_per_unique_clip": True},
           "metrics": {"all": {"direct": _metrics(rows, "direct"),
                                "cascade": _metrics(rows, "cascade"),
                                "paired": _paired(rows)},
                       **{col: {"direct": _metrics([r for r in rows if r["column"] == col], "direct"),
                                "cascade": _metrics([r for r in rows if r["column"] == col], "cascade"),
                                "paired": _paired([r for r in rows if r["column"] == col])}
                          for col in ("hazard", "normal")}},
           "rows": rows}
    RESULTS.mkdir(parents=True, exist_ok=True)
    target = RESULTS / f"isafety_uzak_v2_{datetime.now():%Y%m%d_%H%M%S}.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out["metrics"], ensure_ascii=False, indent=2)); print(target)


if __name__ == "__main__": main()
