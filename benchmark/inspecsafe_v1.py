#!/usr/bin/env python
"""InspecSafe-V1 resmi testinde checkpoint'li, satir-bazli ozel-API benchmarki.

Iki eslesik kolu olcer:

* ``direct``: ``vlm`` + resmi prompt (yayim protokolune en yakin kol),
* ``system``: ``vlm`` tarafsiz gozlem -> ``llm-large`` gorsel karar ->
  ``llm-fast`` kilitli JSON yapilandirma (mevcut uc-modelli sistem).

Ogrenilmis cikarim yalniz sabit ozel API'de yapilir. Dosya adi, klasor, etiket,
anotasyon veya maske hicbir model mesajina girmez.
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import io
import json
import math
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import av
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.stats_utils import mcnemar_exact_p, rate  # noqa: E402
from dilajan.config import settings  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402


PRIVATE_API = "https://evren-llmapi.ssyz.org.tr/v1"
CONTRACT = {
    "algi": "vlm",
    "olay": "llm-large",
    "yapi": "llm-fast",
    "ozet": "llm-fast",
}
DATASET_REVISION = "f3cb7d3e7827c1afc1c5bfd0524257984bba46ab"
OFFICIAL_CODE_REVISION = "d2f66e0ada2edc4dc65c25213d37b00a4039910f"
OFFICIAL_SCRIPT_SHA256 = "70ac21176a1d2051ea182cf04d5ca0b2b5636317367b62c82f0e743c27761448"
OFFICIAL_PROMPT_SHA256 = "f13a8837108f41e590d2bfddcc41ed55f9f880cea79d621b2cfd993e8ddceb9d"
ARCHIVE_SHA256 = "818086e696f970e036bf6a76758e4fb851fa26f771fe4eac56f8dc073b44358d"
ARCHIVE_SIZE = 5_748_799_871
EXPECTED_TEST = 1_250
EXPECTED_NORMAL = 999
EXPECTED_ABNORMAL = 251
REVISION = "inspecsafe-v1-private-api-preregistered-v1"

LABELS = ("LEVEL_ONE", "LEVEL_TWO", "LEVEL_THREE", "NO_ABNORMALITY")
PATH_TO_LABEL = {
    "1": "LEVEL_ONE",
    "2": "LEVEL_TWO",
    "3": "LEVEL_THREE",
    "4": "NO_ABNORMALITY",
}
DISPLAY = {
    "LEVEL_ONE": "Level I",
    "LEVEL_TWO": "Level II",
    "LEVEL_THREE": "Level III",
    "NO_ABNORMALITY": "Level IV / normal",
}
PUBLISHED_ACCURACY = {
    "doubao-seed-1-6-vision-250815": 0.8128,
    "qwen3-vl-32b-thinking": 0.7688,
    "qwen3-vl-235b-a22b-thinking": 0.7544,
    "grok-4.1-fast": 0.7296,
    "qwen3-vl-235b-a22b-instruct": 0.7240,
    "glm-4.5v": 0.7200,
    "claude-opus-4-5-20251101": 0.7168,
    "qwen3-vl-8b-thinking": 0.7024,
    "qwen3-vl-8b-instruct": 0.6936,
    "gemini-3-flash-preview": 0.6888,
    "GLM-4.1V-Thinking-Flash": 0.6856,
    "qwen3-vl-32b-instruct": 0.6824,
    "gpt-5.2": 0.6248,
    "yi-vision": 0.6120,
    "glm-4.6": 0.4168,
}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

OFFICIAL_SCRIPT = ROOT / "data" / "external" / "inspecsafe_code" / "model_api_generate_results.py"
DEFAULT_DATA_ROOT = ROOT / "data" / "external" / "inspecsafe_v1" / "extracted"
RESULTS = ROOT / "benchmark" / "results"


NEUTRAL_SYSTEM = (
    "You are a neutral forensic observer of one real industrial inspection image. "
    "Report only directly visible entities, human actions, object states, environmental "
    "conditions and candidate hazard evidence. Do not infer a person, injury, missing PPE, "
    "smoke, flame, leak or violation merely from the scene type. Distinguish confirmed "
    "evidence from ambiguity. Do not assign a safety level."
)
NEUTRAL_PROMPT = (
    "Describe the decision-relevant visible evidence in at most 120 English words. "
    "Mention visibility limitations explicitly. Do not output Level I, II, III or IV."
)
CLASSIFY_SYSTEM = (
    "You are the safety-level decision stage of an industrial inspection system. The image "
    "is primary evidence; the supplied neutral observation is secondary and may be imperfect. "
    "Apply the supplied official scenario-dependent rules exactly. Use the most severe visible "
    "hazard. Never treat an unclear or occluded region as proof that a person, hazard or PPE "
    "violation exists. Output exactly one allowed code and nothing else."
)
CLASSIFY_SUFFIX = """

ADDITIONAL PIPELINE INPUT
Neutral visual observation (not ground truth):
{observation}

Code mapping:
- Level one -> LEVEL_ONE
- Level two -> LEVEL_TWO
- Level three -> LEVEL_THREE
- no abnormalities observed -> NO_ABNORMALITY

Re-check the original image, apply the official criteria above, and output exactly one code.
""".strip()
FORMAT_SYSTEM = (
    "You are a deterministic report formatter. The supplied safety code is locked by the "
    "upstream assessor: copy it exactly and do not reassess, correct, escalate or downgrade it. "
    "Use only the supplied observation. Return only JSON matching the schema."
)
FORMAT_PROMPT = """Neutral observation:
{observation}

Locked safety code: {decision}

Produce the final structured report. Copy the locked code exactly.
"""


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_json_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha_bytes(raw.encode("utf-8"))


def _load_official_prompt() -> str:
    if not OFFICIAL_SCRIPT.is_file():
        raise RuntimeError(f"Resmi betik yok: {OFFICIAL_SCRIPT}")
    actual = _sha_file(OFFICIAL_SCRIPT)
    if actual != OFFICIAL_SCRIPT_SHA256:
        raise RuntimeError(f"Resmi betik SHA-256 degisti: {actual}")
    tree = ast.parse(OFFICIAL_SCRIPT.read_text(encoding="utf-8"))
    prompt = None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "prompt" for target in node.targets):
            prompt = ast.literal_eval(node.value)
            break
    if not isinstance(prompt, str):
        raise RuntimeError("Resmi prompt AST'den bulunamadi")
    actual_prompt = _sha_bytes(prompt.encode("utf-8"))
    if actual_prompt != OFFICIAL_PROMPT_SHA256:
        raise RuntimeError(f"Resmi prompt SHA-256 degisti: {actual_prompt}")
    return prompt


def prompt_hashes(official_prompt: str) -> dict[str, str]:
    return {
        "official": _sha_bytes(official_prompt.encode("utf-8")),
        "neutral_system": _sha_bytes(NEUTRAL_SYSTEM.encode("utf-8")),
        "neutral_prompt": _sha_bytes(NEUTRAL_PROMPT.encode("utf-8")),
        "classify_system": _sha_bytes(CLASSIFY_SYSTEM.encode("utf-8")),
        "classify_suffix": _sha_bytes(CLASSIFY_SUFFIX.encode("utf-8")),
        "format_system": _sha_bytes(FORMAT_SYSTEM.encode("utf-8")),
        "format_prompt": _sha_bytes(FORMAT_PROMPT.encode("utf-8")),
    }


def _contract() -> dict[str, Any]:
    actual = {role: settings.gorev_modeli(role) for role in CONTRACT}
    if settings.base_url.rstrip("/") != PRIVATE_API or not settings.uzak_api_mi:
        raise RuntimeError(f"Yalniz ozel API kabul edilir: {settings.base_url}")
    mismatch = {k: {"actual": actual[k], "expected": v}
                for k, v in CONTRACT.items() if actual[k] != v}
    if mismatch:
        raise RuntimeError(f"Sabit model sozlesmesi bozuldu: {mismatch}")
    if not settings.yerel_ogrenilmis_yasak or settings.model_indirme_izni:
        raise RuntimeError("Yerel ogrenilmis cikarim/model indirme kapisi acik")
    if settings.mock_mode:
        raise RuntimeError("Gercek benchmark MOCK modda kosamaz")
    if not settings.etkin_api_key or settings.etkin_api_key == "EMPTY":
        raise RuntimeError("Ozel API anahtari yok")
    # On kayit: ilk cagri + dort ek deneme = en fazla bes girisim.
    settings.yeniden_deneme = 4
    return {
        "base_url": settings.base_url,
        "models": actual,
        "local_learned_inference_forbidden": settings.yerel_ogrenilmis_yasak,
        "model_download_allowed": settings.model_indirme_izni,
        "temperature": 0.0,
        "attempts_max": 5,
    }


def verify_archive(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"Arsiv yok: {path}")
    size = path.stat().st_size
    if size != ARCHIVE_SIZE:
        raise RuntimeError(f"Arsiv boyutu uyusmuyor: {size} != {ARCHIVE_SIZE}")
    digest = _sha_file(path)
    if digest != ARCHIVE_SHA256:
        raise RuntimeError(f"Arsiv SHA-256 uyusmuyor: {digest}")
    return {"path": str(path), "size": size, "sha256": digest}


_PATH_LEVEL = re.compile(r"level[\s_-]*0?([1-4])", re.IGNORECASE)
_ROMAN_LEVEL = re.compile(
    r"(?:safety\s+level(?:\s+is)?\s*[:：\]-]?\s*(?:grade\s+)?|"
    r"\[?(?:level|grade)\s+)(four|three|two|one|IV|III|II|I|[1-4])\b",
    re.IGNORECASE,
)


def _annotation_level(text: str) -> str | None:
    # Etiket tipik olarak metnin sonundaki Safety Level alanindadir. Birden cok
    # farkli seviye geciyorsa sessizce birini secmek yerine dogrulamayi durdur.
    tokens = {match.upper() for match in _ROMAN_LEVEL.findall(text)}
    mapping = {
        "I": "LEVEL_ONE", "ONE": "LEVEL_ONE", "1": "LEVEL_ONE",
        "II": "LEVEL_TWO", "TWO": "LEVEL_TWO", "2": "LEVEL_TWO",
        "III": "LEVEL_THREE", "THREE": "LEVEL_THREE", "3": "LEVEL_THREE",
        "IV": "NO_ABNORMALITY", "FOUR": "NO_ABNORMALITY", "4": "NO_ABNORMALITY",
    }
    labels = {mapping[token] for token in tokens if token in mapping}
    if re.search(r"\bno\s+abnormalit(?:y|ies)\s+observed\b", text, re.IGNORECASE):
        labels.add("NO_ABNORMALITY")
    return next(iter(labels)) if len(labels) == 1 else None


def _scenario(path: Path) -> str:
    source = " ".join(path.parts).lower()
    rules = (
        ("oil_gas_chemical", ("oil", "gas", "chemical", "petro")),
        ("coal_conveyor", ("coal", "conveyor", "trestle")),
        ("tunnel", ("tunnel",)),
        ("power", ("power", "electric", "substation")),
        ("metallurgy", ("metall", "sinter", "steel")),
    )
    for label, needles in rules:
        if any(needle in source for needle in needles):
            return label
    for part in reversed(path.parts[:-1]):
        if _PATH_LEVEL.search(part):
            raw = _PATH_LEVEL.sub("", part).strip(" _-")
            if raw:
                return re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_") or "unknown"
    return "unknown"


def discover_dataset(data_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not data_root.is_dir():
        raise RuntimeError(f"Cikarilmis veri dizini yok: {data_root}")
    images = sorted(
        p for p in data_root.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
        and any(part.lower() == "annotations" for part in p.parts)
    )
    if len(images) != EXPECTED_TEST:
        raise RuntimeError(f"Test goruntu sayisi {len(images)}; beklenen {EXPECTED_TEST}")

    rows: list[dict[str, Any]] = []
    validation_errors: list[str] = []
    for image in images:
        rel = image.relative_to(data_root).as_posix()
        matches = _PATH_LEVEL.findall(rel)
        if len(set(matches)) != 1:
            validation_errors.append(f"yol seviyesi belirsiz: {rel}")
            continue
        digit = matches[-1]
        gold = PATH_TO_LABEL[digit]
        lower_parts = {part.lower() for part in image.parts}
        subset = "normal" if "normal_data" in lower_parts else (
            "abnormal" if "anomaly_data" in lower_parts else "unknown"
        )
        if subset == "unknown":
            validation_errors.append(f"normal/anomaly klasoru yok: {rel}")
        if subset == "normal" and gold != "NO_ABNORMALITY":
            validation_errors.append(f"normal klasorunde anormal seviye: {rel}")
        if subset == "abnormal" and gold == "NO_ABNORMALITY":
            validation_errors.append(f"anomaly klasorunde Level04: {rel}")

        candidates = [image.with_suffix(".txt")]
        if not candidates[0].is_file():
            candidates = sorted(image.parent.glob("*.txt"))
        if len(candidates) != 1 or not candidates[0].is_file():
            validation_errors.append(f"tekil metin anotasyonu yok: {rel}")
            annotation_rel = None
            annotation_gold = None
        else:
            annotation_rel = candidates[0].relative_to(data_root).as_posix()
            text = candidates[0].read_text(encoding="utf-8", errors="replace")
            annotation_gold = _annotation_level(text)
            if annotation_gold != gold:
                validation_errors.append(
                    f"anotasyon/yol seviyesi celisiyor: {rel}: {annotation_gold} != {gold}"
                )

        rows.append({
            "id": _sha_bytes(rel.encode("utf-8"))[:20],
            "path": str(image),
            "relative_path": rel,
            "annotation_relative_path": annotation_rel,
            "gold": gold,
            "subset": subset,
            "domain": _scenario(Path(rel)),
            "size": image.stat().st_size,
            "image_sha256": _sha_file(image),
        })

    if validation_errors:
        sample = "\n".join(validation_errors[:20])
        raise RuntimeError(f"Veri butunluk hatasi ({len(validation_errors)}):\n{sample}")

    subset_counts = Counter(row["subset"] for row in rows)
    if subset_counts != Counter({"normal": EXPECTED_NORMAL, "abnormal": EXPECTED_ABNORMAL}):
        raise RuntimeError(f"Normal/anormal dagilimi uyusmuyor: {dict(subset_counts)}")
    hashes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        hashes[row["image_sha256"]].append(row)
    conflicting = [group for group in hashes.values()
                   if len({row["gold"] for row in group}) > 1]
    if conflicting:
        raise RuntimeError(f"Ayni goruntu baytinda celisen etiket: {len(conflicting)} grup")

    manifest_rows = [{k: row[k] for k in (
        "relative_path", "annotation_relative_path", "gold", "subset", "domain",
        "size", "image_sha256")}
        for row in rows]
    validation = {
        "dataset_revision": DATASET_REVISION,
        "count": len(rows),
        "subset_counts": dict(sorted(subset_counts.items())),
        "label_counts": dict(sorted(Counter(row["gold"] for row in rows).items())),
        "domain_counts": dict(sorted(Counter(row["domain"] for row in rows).items())),
        "unique_image_sha256": len(hashes),
        "duplicate_groups": sum(len(group) > 1 for group in hashes.values()),
        "manifest_sha256": _canonical_json_sha(manifest_rows),
        "path_annotation_crosscheck": "pass",
        "labels_sent_to_model": False,
    }
    return rows, validation


def _still_as_video_url(path: Path) -> str:
    """Tek resmi servis-zorunlu videoya, iki ozdes kareyle kayipsiza yakin sar.

    Ozel API'deki sabit ``vlm`` aliasi ``max_images=0`` ve video-yerlidir. Bu
    nedenle resmi iki ozdes kareli H.264/MP4 olarak gondeririz. Zamansal kanit
    eklenmez; orijinal uzamsal cozunurluk korunur. YUV420 renk alt-orneklemesi
    disinda x264 CRF=0 kullanilir.
    """
    with Image.open(io.BytesIO(path.read_bytes())) as source:
        image = source.convert("RGB")
    width = max(2, image.width - image.width % 2)
    height = max(2, image.height - image.height % 2)
    if (width, height) != image.size:
        image = image.crop((0, 0, width, height))
    frame = av.VideoFrame.from_ndarray(np.asarray(image), format="rgb24")
    buffer = io.BytesIO()
    container = av.open(buffer, mode="w", format="mp4")
    stream = container.add_stream("libx264", rate=2)
    stream.width = width
    stream.height = height
    stream.pix_fmt = "yuv420p"
    stream.options = {"crf": "0", "preset": "veryfast", "tune": "stillimage"}
    for _ in range(2):
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:video/mp4;base64,{encoded}"


def parse_official_level(raw: str | None) -> str | None:
    """Resmi ``model_confusion_matrix.py`` son-sozcuk ayristiricisini uygula."""
    if not raw:
        return None
    lines = raw.splitlines()
    if not lines:
        return None
    last_line = lines[-1].strip()
    if "(" in last_line:
        last_line = last_line.split("(", 1)[0]
    words = last_line.split()
    if not words:
        return None
    last_word = words[-1].rstrip(".").strip().lower()
    last_word = last_word.replace("level]", "").replace("]", "")
    mapping = {
        "observed": "NO_ABNORMALITY",
        "one": "LEVEL_ONE",
        "two": "LEVEL_TWO",
        "ii": "LEVEL_TWO",
        "2": "LEVEL_TWO",
        "three": "LEVEL_THREE",
    }
    return mapping.get(last_word)


def parse_choice(raw: str | None) -> str | None:
    value = (raw or "").strip()
    return value if value in LABELS else None


def parse_formatted(raw: str | None, locked: str) -> dict[str, str] | None:
    try:
        obj = json.loads(raw or "")
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(obj, dict) or set(obj) != {"image_description", "safety_level"}:
        return None
    if obj.get("safety_level") != locked:
        return None
    description = obj.get("image_description")
    if not isinstance(description, str) or not description.strip():
        return None
    return {"image_description": description.strip(), "safety_level": locked}


def _usage(client: VLMClient) -> dict[str, int] | None:
    value = getattr(client, "son_kullanim", None)
    return dict(value) if isinstance(value, dict) else None


def _call_direct(video_url: str, official_prompt: str) -> tuple[str | None, dict[str, Any]]:
    client = VLMClient().gorev("algi")
    started = time.perf_counter()
    raw = client.chat([{"role": "user", "content": [
        {"type": "text", "text": official_prompt},
        {"type": "video_url", "video_url": {"url": video_url}},
    ]}], temperature=0.0, max_tokens=768)
    return raw, {
        "stage": "direct", "role": "algi", "model": client.model,
        "latency_s": round(time.perf_counter() - started, 3),
        "retries": int(getattr(client, "son_deneme_sayisi", 0)), "usage": _usage(client),
    }


def _call_observe(video_url: str) -> tuple[str | None, dict[str, Any]]:
    client = VLMClient().gorev("algi")
    started = time.perf_counter()
    raw = client.chat([
        {"role": "system", "content": NEUTRAL_SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": NEUTRAL_PROMPT},
            {"type": "video_url", "video_url": {"url": video_url}},
        ]},
    ], temperature=0.0, max_tokens=256)
    return raw, {
        "stage": "observe", "role": "algi", "model": client.model,
        "latency_s": round(time.perf_counter() - started, 3),
        "retries": int(getattr(client, "son_deneme_sayisi", 0)), "usage": _usage(client),
    }


def _call_classify(video_url: str, observation: str,
                   official_prompt: str) -> tuple[str | None, dict[str, Any]]:
    client = VLMClient().gorev("olay")
    started = time.perf_counter()
    prompt = official_prompt + "\n\n" + CLASSIFY_SUFFIX.format(observation=observation)
    raw = client.chat([
        {"role": "system", "content": CLASSIFY_SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "video_url", "video_url": {"url": video_url}},
        ]},
    ], temperature=0.0, max_tokens=8, guided_choice=LABELS)
    return raw, {
        "stage": "classify", "role": "olay", "model": client.model,
        "latency_s": round(time.perf_counter() - started, 3),
        "retries": int(getattr(client, "son_deneme_sayisi", 0)), "usage": _usage(client),
    }


def _call_format(observation: str, decision: str) -> tuple[str | None, dict[str, Any]]:
    client = VLMClient().gorev("yapi")
    started = time.perf_counter()
    schema = {
        "type": "object",
        "properties": {
            "image_description": {"type": "string", "minLength": 1},
            "safety_level": {"type": "string", "enum": [decision]},
        },
        "required": ["image_description", "safety_level"],
        "additionalProperties": False,
    }
    raw = client.chat([
        {"role": "system", "content": FORMAT_SYSTEM},
        {"role": "user", "content": FORMAT_PROMPT.format(
            observation=observation, decision=decision)},
    ], temperature=0.0, max_tokens=320, json_schema=schema,
        schema_name="inspecsafe_report")
    return raw, {
        "stage": "format", "role": "yapi", "model": client.model,
        "latency_s": round(time.perf_counter() - started, 3),
        "retries": int(getattr(client, "son_deneme_sayisi", 0)), "usage": _usage(client),
    }


def _error(exc: BaseException) -> str:
    text = re.sub(r"\s+", " ", str(exc)).strip()
    # API govdesi anahtar veya fazla sunucu ayrintisi tasiyabilir; jurnal icin sinirla.
    return f"{type(exc).__name__}: {text[:1000]}"


def probe(item: dict[str, Any], official_prompt: str) -> dict[str, Any]:
    image = Path(item["path"])
    started = time.perf_counter()
    calls: list[dict[str, Any]] = []
    direct_raw = direct_error = observation = observe_error = None
    classify_raw = classify_error = format_raw = format_error = None
    direct_label = system_label = None
    formatted = None

    try:
        encoded = _still_as_video_url(image)
    except Exception as exc:  # pragma: no cover - veri dogrulamasi normalde yakalar
        encoded = ""
        encoding_error = _error(exc)
    else:
        encoding_error = None

    if not encoding_error:
        try:
            direct_raw, meta = _call_direct(encoded, official_prompt)
            calls.append(meta)
            direct_label = parse_official_level(direct_raw)
            if direct_label is None:
                direct_error = "parse_error: official safety level is not unique"
        except Exception as exc:  # noqa: BLE001
            direct_error = _error(exc)

        try:
            observation, meta = _call_observe(encoded)
            calls.append(meta)
            if not (observation or "").strip():
                observe_error = "empty_observation"
        except Exception as exc:  # noqa: BLE001
            observe_error = _error(exc)

        if not observe_error:
            try:
                classify_raw, meta = _call_classify(encoded, observation or "", official_prompt)
                calls.append(meta)
                system_label = parse_choice(classify_raw)
                if system_label is None:
                    classify_error = "parse_error: invalid structured choice"
            except Exception as exc:  # noqa: BLE001
                classify_error = _error(exc)

        if system_label is not None and not classify_error:
            try:
                format_raw, meta = _call_format(observation or "", system_label)
                calls.append(meta)
                formatted = parse_formatted(format_raw, system_label)
                if formatted is None:
                    format_error = "parse_error: invalid or changed locked JSON"
            except Exception as exc:  # noqa: BLE001
                format_error = _error(exc)
    else:
        direct_error = observe_error = encoding_error

    gold = item["gold"]
    return {
        "id": item["id"],
        "relative_path": item["relative_path"],
        "image_sha256": item["image_sha256"],
        "gold": gold,
        "subset": item["subset"],
        "domain": item["domain"],
        "direct": {
            "label": direct_label, "raw": direct_raw, "error": direct_error,
            "correct": direct_label == gold,
        },
        "system": {
            "observation": observation, "observe_error": observe_error,
            "label": system_label, "classify_raw": classify_raw,
            "classify_error": classify_error, "correct": system_label == gold,
            "formatted": formatted, "format_raw": format_raw, "format_error": format_error,
            "end_to_end_valid": formatted is not None,
            "end_to_end_correct": formatted is not None and system_label == gold,
        },
        "calls": calls,
        "latency_s": round(time.perf_counter() - started, 3),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def _prediction(row: dict[str, Any], arm: str) -> str | None:
    if arm == "direct":
        return row["direct"]["label"]
    if arm == "system":
        return row["system"]["label"] if not row["system"]["observe_error"] else None
    if arm == "end_to_end":
        return row["system"]["label"] if row["system"]["end_to_end_valid"] else None
    raise ValueError(arm)


def _safe_div(a: int | float, b: int | float) -> float:
    return float(a / b) if b else 0.0


def _mcc(tp: int, fp: int, fn: int, tn: int) -> float:
    denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return (tp * tn - fp * fn) / denom if denom else 0.0


def _binary(rows: Sequence[dict[str, Any]], arm: str) -> dict[str, Any]:
    # Invalid: metrikleri iyilestirmesin diye adversarial sayilir. Unsafe altinda
    # FN, normal altinda FP. Ayrica valid-only tablo ayri verilir.
    tp = fp = fn = tn = 0
    vtp = vfp = vfn = vtn = 0
    invalid = 0
    for row in rows:
        truth = row["gold"] != "NO_ABNORMALITY"
        pred = _prediction(row, arm)
        if pred is None:
            invalid += 1
            if truth:
                fn += 1
            else:
                fp += 1
            continue
        positive = pred != "NO_ABNORMALITY"
        if truth and positive:
            tp += 1; vtp += 1
        elif truth and not positive:
            fn += 1; vfn += 1
        elif not truth and positive:
            fp += 1; vfp += 1
        else:
            tn += 1; vtn += 1

    def pack(a: int, b: int, c: int, d: int) -> dict[str, Any]:
        precision = rate(a, a + b)
        recall = rate(a, a + c)
        specificity = rate(d, d + b)
        fpr = rate(b, b + d)
        return {
            "tp": a, "fp": b, "fn": c, "tn": d,
            "precision": precision,
            "recall": recall,
            "f1": round(_safe_div(2 * precision["p"] * recall["p"],
                                  precision["p"] + recall["p"]), 4),
            "specificity": specificity,
            "false_positive_rate": fpr,
            "balanced_accuracy": round((recall["p"] + specificity["p"]) / 2, 4),
            "mcc": round(_mcc(a, b, c, d), 4),
        }

    return {
        "invalid_policy": "adversarial: unsafe invalid=FN, normal invalid=FP",
        "invalid": invalid,
        "strict": pack(tp, fp, fn, tn),
        "valid_only": pack(vtp, vfp, vfn, vtn),
    }


def _multiclass(rows: Sequence[dict[str, Any]], arm: str) -> dict[str, Any]:
    matrix = {gold: {pred: 0 for pred in (*LABELS, "INVALID")} for gold in LABELS}
    valid = correct = 0
    for row in rows:
        pred = _prediction(row, arm)
        matrix[row["gold"]][pred or "INVALID"] += 1
        valid += pred is not None
        correct += pred == row["gold"]
    per_class: dict[str, Any] = {}
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[gold][label] for gold in LABELS if gold != label)
        fn = sum(matrix[label][pred] for pred in (*LABELS, "INVALID") if pred != label)
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        per_class[label] = {
            "support": sum(matrix[label].values()),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(_safe_div(2 * precision * recall, precision + recall), 4),
        }
    return {
        "accuracy_strict": rate(correct, len(rows)),
        "accuracy_valid": rate(correct, valid),
        "coverage": rate(valid, len(rows)),
        "confusion": matrix,
        "per_class": per_class,
        "macro_precision": round(statistics.fmean(x["precision"] for x in per_class.values()), 4),
        "macro_recall_balanced_accuracy": round(
            statistics.fmean(x["recall"] for x in per_class.values()), 4),
        "macro_f1": round(statistics.fmean(x["f1"] for x in per_class.values()), 4),
    }


def _severe_undercall(rows: Sequence[dict[str, Any]], arm: str) -> dict[str, Any]:
    level_one = [row for row in rows if row["gold"] == "LEVEL_ONE"]
    level_two = [row for row in rows if row["gold"] == "LEVEL_TWO"]
    l1_recalled = sum(_prediction(row, arm) == "LEVEL_ONE" for row in level_one)
    l1_severe = sum(_prediction(row, arm) in (None, "LEVEL_THREE", "NO_ABNORMALITY")
                    for row in level_one)
    l2_normal = sum(_prediction(row, arm) in (None, "NO_ABNORMALITY") for row in level_two)
    return {
        "level_one_recall": rate(l1_recalled, len(level_one)),
        "level_one_to_level3_normal_or_invalid": rate(l1_severe, len(level_one)),
        "level_two_to_normal_or_invalid": rate(l2_normal, len(level_two)),
    }


def _percentile(values: Iterable[float], q: float) -> float | None:
    vals = sorted(float(x) for x in values)
    if not vals:
        return None
    pos = (len(vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return round(vals[lo], 3)
    return round(vals[lo] + (vals[hi] - vals[lo]) * (pos - lo), 3)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    arms: dict[str, Any] = {}
    for arm in ("direct", "system", "end_to_end"):
        multi = _multiclass(rows, arm)
        by_domain = {}
        for domain in sorted({row["domain"] for row in rows}):
            domain_rows = [row for row in rows if row["domain"] == domain]
            by_domain[domain] = _multiclass(domain_rows, arm)["accuracy_strict"]
        arms[arm] = {
            "multiclass": multi,
            "binary": _binary(rows, arm),
            "severe_undercall": _severe_undercall(rows, arm),
            "accuracy_by_domain": by_domain,
            "worst_domain": min(by_domain, key=lambda key: by_domain[key]["p"]),
        }

    fixed = sum((not row["direct"]["correct"]) and row["system"]["end_to_end_correct"]
                for row in rows)
    broke = sum(row["direct"]["correct"] and (not row["system"]["end_to_end_correct"])
                for row in rows)
    direct = arms["direct"]
    # Kullaniciya sunulan sistem skoru uc asamanin da basarili oldugu uctan-uca
    # koldur. ``system`` yalniz semantik llm-large kararini tani icin ayri tutar.
    system = arms["end_to_end"]
    gate_checks = {
        "four_class_accuracy_non_decreasing":
            system["multiclass"]["accuracy_strict"]["p"] >= direct["multiclass"]["accuracy_strict"]["p"],
        "unsafe_precision_non_decreasing":
            system["binary"]["strict"]["precision"]["p"] >= direct["binary"]["strict"]["precision"]["p"],
        "unsafe_recall_non_decreasing":
            system["binary"]["strict"]["recall"]["p"] >= direct["binary"]["strict"]["recall"]["p"],
        "normal_fpr_non_increasing":
            system["binary"]["strict"]["false_positive_rate"]["p"] <= direct["binary"]["strict"]["false_positive_rate"]["p"],
        "end_to_end_coverage_at_least_99pct":
            arms["end_to_end"]["multiclass"]["coverage"]["p"] >= 0.99,
    }
    call_latencies = [call["latency_s"] for row in rows for call in row["calls"]]
    row_latencies = [row["latency_s"] for row in rows]
    return {
        "n": len(rows),
        "arms": arms,
        "paired_direct_vs_system": {
            "system_fixed": fixed,
            "system_broke": broke,
            "accuracy_difference": round(
                system["multiclass"]["accuracy_strict"]["p"]
                - direct["multiclass"]["accuracy_strict"]["p"], 4),
            "mcnemar_exact_p": mcnemar_exact_p(fixed, broke),
        },
        "non_regression_gate": {
            "checks": gate_checks,
            "pass": all(gate_checks.values()),
        },
        "latency_seconds": {
            "call_p50": _percentile(call_latencies, 0.5),
            "call_p95": _percentile(call_latencies, 0.95),
            "row_p50": _percentile(row_latencies, 0.5),
            "row_p95": _percentile(row_latencies, 0.95),
        },
    }


def _pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def render_markdown(meta: dict[str, Any], summary: dict[str, Any]) -> str:
    lines = [
        "# InspecSafe-V1 gercek test sonucu",
        "",
        f"- Tamamlanma (UTC): `{meta['completed_at']}`",
        f"- Test: **{summary['n']} / {EXPECTED_TEST}** resmî ornek",
        f"- Veri manifest SHA-256: `{meta['dataset_validation']['manifest_sha256']}`",
        f"- Kosum anahtari: `{meta['run_key']}`",
        "- Ogrenilmis cikarim: yalniz ozel API; yerel model/model indirme yok",
        "",
        "## Ana sonuclar",
        "",
        "| Kol | 4-sinif strict accuracy | Kapsama | Unsafe precision | Unsafe recall | Unsafe F1 | Normal FPR | MCC |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    arm_names = {"direct": "direct VLM", "system": "ara karar (vlm + llm-large)",
                 "end_to_end": "tam sistem (3 model)"}
    for arm in ("direct", "system", "end_to_end"):
        data = summary["arms"][arm]
        multi = data["multiclass"]
        binary = data["binary"]["strict"]
        acc = multi["accuracy_strict"]
        lines.append(
            f"| {arm_names[arm]} | {_pct(acc['p'])} ({acc['k']}/{acc['n']}; "
            f"95% GA {_pct(acc['ci_low'])}–{_pct(acc['ci_high'])}) | "
            f"{_pct(multi['coverage']['p'])} | {_pct(binary['precision']['p'])} | "
            f"{_pct(binary['recall']['p'])} | {_pct(binary['f1'])} | "
            f"{_pct(binary['false_positive_rate']['p'])} | {binary['mcc']:.3f} |"
        )

    paired = summary["paired_direct_vs_system"]
    gate = summary["non_regression_gate"]
    lines += [
        "",
        "## Eslesik karsilastirma",
        "",
        f"Sistem dogrudan kolun **{paired['system_fixed']}** hatasini duzeltti; "
        f"**{paired['system_broke']}** dogrusunu bozdu. Accuracy farki "
        f"{paired['accuracy_difference'] * 100:+.1f} puan, exact McNemar "
        f"p=`{paired['mcnemar_exact_p']:.6g}`.",
        "",
        f"On-kayitli gerilemesizlik kapisi: **{'GECTI' if gate['pass'] else 'KALDI'}**.",
        "",
    ]
    for name, passed in gate["checks"].items():
        lines.append(f"- {'GECTI' if passed else 'KALDI'} — `{name}`")

    direct_acc = summary["arms"]["direct"]["multiclass"]["accuracy_strict"]["p"]
    published_above = sum(value > direct_acc for value in PUBLISHED_ACCURACY.values())
    lines += [
        "", "## Yayimlanmis dogrudan VLM referansi", "",
        "Yalniz `direct VLM` kolu, resmi tek-goruntu + standart prompt protokolune "
        "yakindir. Ozel API `image_url` kabul etmedigi icin ayni tek kare iki ozdes "
        "kareli kayipsiza-yakin MP4'e sarilmistir; tam uc-modelli sistem skoru bu "
        "tek-model siralamasiyla dogrudan kiyaslanamaz. Resmi betik T=0.1, bu kosum "
        "T=0.0 kullandigi icin yayin karsilastirmasi yalniz yon gostericidir.", "",
        f"Yayimlanan 15 modelin accuracy araligi `{_pct(min(PUBLISHED_ACCURACY.values()))}`–"
        f"`{_pct(max(PUBLISHED_ACCURACY.values()))}`. Bizim direct kol nokta degerinden "
        f"daha yuksek {published_above}/15 yayim satiri vardir.", "",
        "| Yayin modeli | Accuracy |", "|---|---:|",
    ]
    for name, value in sorted(PUBLISHED_ACCURACY.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"| {name} | {_pct(value)} |")

    lines += ["", "## Dort-sinif confusion matrix", ""]
    for arm in ("direct", "system", "end_to_end"):
        lines += [f"### {arm_names[arm]}", "", "| Gercek \\ Tahmin | Level I | Level II | Level III | Normal | Invalid |",
                  "|---|---:|---:|---:|---:|---:|"]
        matrix = summary["arms"][arm]["multiclass"]["confusion"]
        for gold in LABELS:
            vals = matrix[gold]
            lines.append(f"| {DISPLAY[gold]} | {vals['LEVEL_ONE']} | {vals['LEVEL_TWO']} | "
                         f"{vals['LEVEL_THREE']} | {vals['NO_ABNORMALITY']} | {vals['INVALID']} |")
        lines.append("")

    lines += ["## Alan bazinda strict accuracy", "",
              "| Alan | Direct | System | Uctan uca |", "|---|---:|---:|---:|"]
    domains = sorted(summary["arms"]["direct"]["accuracy_by_domain"])
    for domain in domains:
        lines.append(
            f"| {domain} | {_pct(summary['arms']['direct']['accuracy_by_domain'][domain]['p'])} | "
            f"{_pct(summary['arms']['system']['accuracy_by_domain'][domain]['p'])} | "
            f"{_pct(summary['arms']['end_to_end']['accuracy_by_domain'][domain]['p'])} |"
        )

    latency = summary["latency_seconds"]
    lines += [
        "", "## Kosum ve yorum siniri", "",
        f"Cagri gecikmesi p50/p95: `{latency['call_p50']}` / `{latency['call_p95']}` sn; "
        f"satir gecikmesi p50/p95: `{latency['row_p50']}` / `{latency['row_p95']}` sn.",
        "",
        "Semantik betim benzerligi raporlanmadi; resmi BGE-M3 degerlendiricisi sabit "
        "model sozlesmesi disinda oldugu icin calistirilmadi. InspecSafe-V1 tek kareli ve "
        "agirlikla normal bir robot-denetim testidir; sonuc video zamansalligini veya butun "
        "ISG dagilimlarini tek basina kanitlamaz.",
        "",
    ]
    return "\n".join(lines)


def _load_journal(path: Path, run_key: str) -> dict[str, dict[str, Any]]:
    done: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return done
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Jurnal JSON bozuk satir {line_no}: {exc}") from exc
        if value.get("run_key") != run_key:
            raise RuntimeError(f"Jurnal run_key uyusmazligi satir {line_no}")
        row = value.get("row")
        if isinstance(row, dict):
            done[row["id"]] = row
    return done


def _append_journal(path: Path, run_key: str, row: dict[str, Any]) -> None:
    record = json.dumps({"run_key": run_key, "row": row}, ensure_ascii=False, sort_keys=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(record + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--archive", type=Path,
                        default=ROOT / "data" / "external" / "inspecsafe_v1" / "test.tar.gz")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--smoke", type=int, default=0,
                        help="Ilk N satiri kos; tahmin/etiket metrigi yazdirma. Tam kosu ayni jurnali surdurur.")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.smoke < 0 or args.workers < 1:
        parser.error("--smoke >= 0 ve --workers >= 1 olmali")

    official_prompt = _load_official_prompt()
    archive = verify_archive(args.archive)
    items, validation = discover_dataset(args.data_root.resolve())
    contract = _contract()
    prompts = prompt_hashes(official_prompt)
    script_sha = _sha_file(Path(__file__))
    protocol = {
        "revision": REVISION,
        "dataset_revision": DATASET_REVISION,
        "official_code_revision": OFFICIAL_CODE_REVISION,
        "archive": archive,
        "dataset_manifest_sha256": validation["manifest_sha256"],
        "contract": contract,
        "prompt_hashes": prompts,
        "runner_sha256": script_sha,
        "generation": {"temperature": 0.0, "repeats": 1,
                       "max_tokens": {"direct": 768, "observe": 256,
                                      "classify": 8, "format": 320},
                       "media_transport": {
                           "reason": "private vlm alias rejects image_url (max_images=0)",
                           "type": "two identical frames in MP4",
                           "codec": "H.264 libx264, CRF=0, yuv420p, 2 fps",
                           "spatial": "original resolution; at most one odd edge pixel cropped",
                           "temporal_information_added": False,
                       }},
        "invalid_policy": "strict wrong; binary adversarial",
    }
    run_key = _canonical_json_sha(protocol)[:16]
    RESULTS.mkdir(parents=True, exist_ok=True)
    manifest_path = RESULTS / f"inspecsafe_v1_manifest_{validation['manifest_sha256'][:16]}.json"
    manifest_path.write_text(json.dumps({
        "validation": validation,
        "items": [{k: row[k] for k in (
            "id", "relative_path", "annotation_relative_path", "gold", "subset",
            "domain", "size", "image_sha256")}
            for row in items],
    }, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    print(f"InspecSafe-V1 validation PASS: n={len(items)}, manifest={validation['manifest_sha256']}")
    print(f"labels={validation['label_counts']} domains={validation['domain_counts']}")
    print(f"private_api={contract['base_url']} models={contract['models']} run_key={run_key}")
    if args.validate_only:
        print(f"manifest={manifest_path}")
        return 0

    selected = items[:args.smoke] if args.smoke else items
    journal = RESULTS / f".inspecsafe_v1_{run_key}.jsonl"
    done = _load_journal(journal, run_key)
    pending = [item for item in selected if item["id"] not in done]
    print(f"checkpoint={len(done)} selected={len(selected)} pending={len(pending)} workers={args.workers}")
    started = time.perf_counter()
    completed_now = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(probe, item, official_prompt): item for item in pending}
        for future in as_completed(futures):
            item = futures[future]
            try:
                row = future.result()
            except Exception as exc:  # pragma: no cover - probe normalde satir-hata dondurur
                raise RuntimeError(f"Satir islenemedi: {item['relative_path']}: {_error(exc)}") from exc
            _append_journal(journal, run_key, row)
            done[row["id"]] = row
            completed_now += 1
            total_complete = sum(item["id"] in done for item in selected)
            elapsed = time.perf_counter() - started
            rate_rows = completed_now / elapsed if elapsed else 0.0
            remaining = len(selected) - total_complete
            eta = remaining / rate_rows if rate_rows else 0.0
            stages_ok = sum(call["stage"] in {"direct", "observe", "classify", "format"}
                            for call in row["calls"])
            print(f"[{total_complete}/{len(selected)}] {row['id']} stages={stages_ok}/4 "
                  f"row={row['latency_s']:.1f}s eta={eta/60:.1f}m", flush=True)

    rows = [done[item["id"]] for item in selected]
    if args.smoke:
        valid_stages = sum(
            row["direct"]["raw"] is not None
            and row["system"]["label"] is not None
            and row["system"]["end_to_end_valid"]
            for row in rows
        )
        if valid_stages != len(rows):
            raise RuntimeError(f"Duman testi bicim/API kapisi kaldi: {valid_stages}/{len(rows)}")
        print(f"SMOKE PASS: {valid_stages}/{len(rows)} satirda dort asama gecerli; skor gizlendi.")
        return 0

    if len(rows) != EXPECTED_TEST:
        raise RuntimeError(f"Tam rapor icin {EXPECTED_TEST} satir gerekir; elde {len(rows)}")
    summary = summarize(rows)
    completed_at = datetime.now(timezone.utc).isoformat()
    meta = {
        "completed_at": completed_at,
        "run_key": run_key,
        "protocol": protocol,
        "dataset_validation": validation,
        "journal": str(journal),
        "manifest": str(manifest_path),
    }
    result = {"meta": meta, "summary": summary, "rows": rows}
    json_path = RESULTS / f"inspecsafe_v1_{run_key}.json"
    report_path = ROOT / "docs" / f"benchmark_inspecsafe_v1_{run_key}_2026-08-28.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
                         encoding="utf-8")
    report_path.write_text(render_markdown(meta, summary), encoding="utf-8")
    print(f"RESULT={json_path}")
    print(f"REPORT={report_path}")
    print(json.dumps({
        "direct_accuracy": summary["arms"]["direct"]["multiclass"]["accuracy_strict"],
        "system_accuracy": summary["arms"]["system"]["multiclass"]["accuracy_strict"],
        "end_to_end_accuracy": summary["arms"]["end_to_end"]["multiclass"]["accuracy_strict"],
        "gate": summary["non_regression_gate"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
