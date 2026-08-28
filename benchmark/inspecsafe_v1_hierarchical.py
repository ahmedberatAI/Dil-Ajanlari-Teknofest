#!/usr/bin/env python
"""InspecSafe-V1 train icinde sizintisiz hiyerarsik karar gelistirmesi.

Resmi test kosucusu ``benchmark/inspecsafe_v1.py`` degistirilmez. Bu arac
yalniz resmi train bolumunu calibration/development/holdout gruplarina ayirir,
mevcut duz dort-sinif karar ile iki-asamali unsafe+severity kararini eslesik
olarak olcer ve kapilari sirayla uygular.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.inspecsafe_v1 import (  # noqa: E402
    CONTRACT,
    DATASET_REVISION,
    IMAGE_SUFFIXES,
    LABELS,
    OFFICIAL_CODE_REVISION,
    PATH_TO_LABEL,
    PRIVATE_API,
    _PATH_LEVEL,
    _annotation_level,
    _call_classify,
    _call_direct,
    _call_observe,
    _canonical_json_sha,
    _contract,
    _error,
    _load_official_prompt,
    _scenario,
    _sha_bytes,
    _sha_file,
    _still_as_video_url,
    _usage,
    parse_official_level,
    prompt_hashes,
)
from benchmark.stats_utils import mcnemar_exact_p, rate  # noqa: E402
from dilajan.gozlem import secim_dagilimi  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402


TRAIN_ARCHIVE_SIZE = 17_886_855_594
TRAIN_ARCHIVE_SHA256 = "ef03b9eb2f9bd91b03f203a8e6cfcc3464cb0d9f0215349a80ad95281fa88cd6"
EXPECTED_TRAIN = 3_763
EXPECTED_NORMAL = 3_014
EXPECTED_ABNORMAL = 749
SPLIT_SALT = "inspecsafe-v1-hier-v1"
REVISION = "inspecsafe-v1-hierarchical-train-v2"
THRESHOLDS = tuple(round(i / 100.0, 2) for i in range(1, 100))
VETO_THRESHOLDS = tuple(round(i / 100.0, 2) for i in range(1, 51))
RESCUE_THRESHOLDS = tuple(round(i / 100.0, 2) for i in range(50, 100))
BINARY_CHOICES = ("UNSAFE", "NORMAL")
SEVERITY_CHOICES = ("LEVEL_ONE", "LEVEL_TWO", "LEVEL_THREE")
PHASES = ("calibration", "development", "holdout")
EXPECTED_DOMAINS = {
    "coal_conveyor", "metallurgy", "oil_gas_chemical", "power", "tunnel",
}

TEST_LABEL_COUNTS = {
    "LEVEL_ONE": 169,
    "LEVEL_TWO": 75,
    "LEVEL_THREE": 7,
    "NO_ABNORMALITY": 999,
}
TEST_N = sum(TEST_LABEL_COUNTS.values())
TEST_PRIORS = {label: count / TEST_N for label, count in TEST_LABEL_COUNTS.items()}
TEST_UNSAFE_PRIOR = 251 / 1250

DEFAULT_DATA_ROOT = ROOT / "data" / "external" / "inspecsafe_v1" / "extracted"
DEFAULT_ARCHIVE = (
    ROOT / "data" / "external" / "inspecsafe_v1" / "ranges_v3"
    / "train.ranges.tar.gz"
)
RESULTS = ROOT / "benchmark" / "results"

BINARY_SYSTEM = (
    "You are the binary hazard-presence stage of an industrial inspection system. "
    "The image is primary evidence and the neutral observation is untrusted secondary "
    "evidence. Apply the supplied official industry-specific table exactly. Choose UNSAFE "
    "when at least one directly visible factor belongs to Level one, two, or three. Choose "
    "NORMAL only when no listed safety factor is visibly supported. Do not invent people, "
    "PPE absence, smoke, flame, liquid, foreign objects, actions, or equipment states from "
    "scene type, blur, glare, occlusion, or uncertainty. Output one allowed code only."
)
BINARY_SUFFIX = """

HIERARCHICAL BINARY DECISION
Neutral visual observation (not ground truth):
{observation}

Aggregate all three abnormal levels before deciding:
- UNSAFE: one or more Level one, Level two, or Level three criteria are directly visible.
- NORMAL: none of those criteria is directly visible.

Re-check the original image. Output exactly UNSAFE or NORMAL.
""".strip()

SEVERITY_SYSTEM = (
    "You are the conditional severity stage of an industrial inspection system. A separate "
    "binary gate has established that at least one official safety factor is visible. Re-check "
    "the image and apply the supplied industry-specific table. Select the most severe supported "
    "abnormal level. Do not output normal and do not infer unsupported hazards. Output exactly "
    "one allowed code."
)
SEVERITY_SUFFIX = """

HIERARCHICAL SEVERITY DECISION
Neutral visual observation (not ground truth):
{observation}

Condition: at least one listed safety factor is visible. Select its most severe supported code:
- LEVEL_ONE
- LEVEL_TWO
- LEVEL_THREE

Re-check the original image and output exactly one code.
""".strip()


class UnionFind:
    def __init__(self, values: set[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a == b:
            return
        lo, hi = sorted((a, b))
        self.parent[hi] = lo


def _prompt_hashes(official_prompt: str) -> dict[str, str]:
    values = prompt_hashes(official_prompt)
    values.update({
        "binary_system": _sha_bytes(BINARY_SYSTEM.encode("utf-8")),
        "binary_suffix": _sha_bytes(BINARY_SUFFIX.encode("utf-8")),
        "severity_system": _sha_bytes(SEVERITY_SYSTEM.encode("utf-8")),
        "severity_suffix": _sha_bytes(SEVERITY_SUFFIX.encode("utf-8")),
    })
    return values


def verify_train_archive(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"Train arsivi yok: {path}")
    size = path.stat().st_size
    if size != TRAIN_ARCHIVE_SIZE:
        raise RuntimeError(f"Train arsivi boyutu uyusmuyor: {size} != {TRAIN_ARCHIVE_SIZE}")
    digest = _sha_file(path)
    if digest != TRAIN_ARCHIVE_SHA256:
        raise RuntimeError(f"Train arsivi SHA-256 uyusmuyor: {digest}")
    return {"path": str(path), "size": size, "sha256": digest}


def _phase_for_group(group_id: str) -> str:
    raw = hashlib.sha256(f"{SPLIT_SALT}|{group_id}".encode("utf-8")).digest()
    value = int.from_bytes(raw[:8], "big") / float(2**64)
    if value < 0.50:
        return "calibration"
    if value < 0.75:
        return "development"
    return "holdout"


def _sample_rank(sample_id: str) -> str:
    return hashlib.sha256(f"{SPLIT_SALT}|normal-sample|{sample_id}".encode("utf-8")).hexdigest()


def _stratified_take(rows: list[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    """Etiketleri koruyarak deterministik grup temsilcileri sec.

    Bir alan/fazda normal ve unsafe bagimsiz grup sayilari esit olmayabilir.
    Ikili benchmark dengesi icin kalabalik taraf da az olan tarafin sayisina
    indirilir. Unsafe taraf indirilirken mevcut her siddet seviyesinden en az
    bir grup tutulur ve kalan kota dogal seviye oranina en yakin bicimde
    dagitilir. Model ciktisi veya dosya sirasi secime etki etmez.
    """
    if target < 1:
        raise RuntimeError("Dengeli secim hedefi pozitif olmali")
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row["gold"])].append(row)
    labels = sorted(buckets)
    if target < len(labels):
        raise RuntimeError(
            f"Hedef {target}, mevcut {len(labels)} etiketi korumaya yetmiyor")
    for label in labels:
        buckets[label].sort(key=lambda row: _sample_rank(str(row["id"])))
    if target >= len(rows):
        return sorted(rows, key=lambda row: _sample_rank(str(row["id"])))

    counts = {label: len(bucket) for label, bucket in buckets.items()}
    allocations = {label: 1 for label in labels}
    total = len(rows)
    while sum(allocations.values()) < target:
        eligible = [label for label in labels if allocations[label] < counts[label]]
        if not eligible:
            raise RuntimeError("Dengeli secim kotasi doldurulamadi")
        # En buyuk oransal acigi kapat; etiket adi yalniz esitlik bozucudur.
        label = min(
            eligible,
            key=lambda value: (
                allocations[value] - target * counts[value] / total,
                value,
            ),
        )
        allocations[label] += 1
    chosen = [
        row
        for label in labels
        for row in buckets[label][:allocations[label]]
    ]
    return sorted(chosen, key=lambda row: _sample_rank(str(row["id"])))


def _resolve_gold(path_gold: str, annotation_text: str) -> tuple[str | None, bool]:
    """Resmi `.txt` sidecar etiketini otorite kabul et.

    InspecSafe'in resmi confusion-matrix kodu ground truth'u klasor adindan
    degil ayni govdeli `.txt` dosyasinin son satirindan okur. Train arsivinde
    bir ornegin yolu Level01 iken sidecar'i Level 3'tur. Bu, model ciktisi
    gorulmeden once bulunan bir veri-kunye celiskisidir; ornegi sessizce yol
    etiketine zorlamak yerine resmi scorer ile ayni otorite kullanilir ve
    celiski manifeste kaydedilir.
    """
    annotation_gold = _annotation_level(annotation_text)
    if annotation_gold not in LABELS:
        return None, False
    return annotation_gold, annotation_gold != path_gold


def _attach_groups(rows: list[dict[str, Any]]) -> None:
    parents = {str(Path(row["relative_path"]).parent) for row in rows}
    union = UnionFind(parents)
    parents_by_hash: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        parents_by_hash[row["image_sha256"]].add(str(Path(row["relative_path"]).parent))
    for group in parents_by_hash.values():
        ordered = sorted(group)
        for other in ordered[1:]:
            union.union(ordered[0], other)

    components: dict[str, set[str]] = defaultdict(set)
    for parent in parents:
        components[union.find(parent)].add(parent)
    group_ids: dict[str, str] = {}
    for component in components.values():
        key = "\n".join(sorted(component))
        group_id = _sha_bytes(key.encode("utf-8"))[:20]
        for parent in component:
            group_ids[parent] = group_id
    for row in rows:
        parent = str(Path(row["relative_path"]).parent)
        row["group_id"] = group_ids[parent]
        row["phase"] = _phase_for_group(row["group_id"])


def discover_train(data_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not data_root.is_dir():
        raise RuntimeError(f"Cikarilmis veri dizini yok: {data_root}")
    images = sorted(
        path for path in data_root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        and any(part.lower() == "train" for part in path.parts)
        and any(part.lower() == "annotations" for part in path.parts)
    )
    if len(images) != EXPECTED_TRAIN:
        raise RuntimeError(f"Train goruntu sayisi {len(images)}; beklenen {EXPECTED_TRAIN}")

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    path_annotation_mismatches: list[dict[str, str]] = []
    for image in images:
        rel = image.relative_to(data_root).as_posix()
        matches = _PATH_LEVEL.findall(rel)
        if len(set(matches)) != 1:
            errors.append(f"yol seviyesi belirsiz: {rel}")
            continue
        path_gold = PATH_TO_LABEL[matches[-1]]
        lower_parts = {part.lower() for part in image.parts}
        subset = "normal" if "normal_data" in lower_parts else (
            "abnormal" if "anomaly_data" in lower_parts else "unknown"
        )
        if subset == "unknown":
            errors.append(f"normal/anomaly klasoru yok: {rel}")

        annotation = image.with_suffix(".txt")
        if not annotation.is_file():
            errors.append(f"adas metin anotasyonu yok: {rel}")
            annotation_rel = None
            gold = None
        else:
            annotation_rel = annotation.relative_to(data_root).as_posix()
            text = annotation.read_text(encoding="utf-8", errors="replace")
            gold, mismatch = _resolve_gold(path_gold, text)
            if gold is None:
                errors.append(f"adas metin anotasyonunda tek seviye yok: {rel}")
            elif mismatch:
                path_annotation_mismatches.append({
                    "relative_path": rel,
                    "path_gold": path_gold,
                    "annotation_gold": gold,
                })
        if gold is not None and subset == "normal" and gold != "NO_ABNORMALITY":
            errors.append(f"normal klasorunde anormal sidecar seviyesi: {rel}")
        if gold is not None and subset == "abnormal" and gold == "NO_ABNORMALITY":
            errors.append(f"anomaly klasorunde normal sidecar seviyesi: {rel}")

        rows.append({
            "id": _sha_bytes(rel.encode("utf-8"))[:20],
            "path": str(image),
            "relative_path": rel,
            "annotation_relative_path": annotation_rel,
            "gold": gold,
            "path_gold": path_gold,
            "subset": subset,
            "domain": _scenario(Path(rel)),
            "size": image.stat().st_size,
            "image_sha256": _sha_file(image),
        })

    if errors:
        raise RuntimeError(f"Train veri butunluk hatasi ({len(errors)}):\n" + "\n".join(errors[:20]))
    subset_counts = Counter(row["subset"] for row in rows)
    expected = Counter({"normal": EXPECTED_NORMAL, "abnormal": EXPECTED_ABNORMAL})
    if subset_counts != expected:
        raise RuntimeError(f"Train normal/anormal dagilimi uyusmuyor: {dict(subset_counts)}")
    domain_counts = Counter(row["domain"] for row in rows)
    if set(domain_counts) != EXPECTED_DOMAINS:
        raise RuntimeError(f"Train alanlari uyusmuyor: {dict(domain_counts)}")

    hashes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        hashes[row["image_sha256"]].append(row)
    conflicts = [group for group in hashes.values()
                 if len({row["gold"] for row in group}) > 1]
    if conflicts:
        raise RuntimeError(f"Ayni train goruntusunde celisen etiket: {len(conflicts)} grup")
    _attach_groups(rows)
    labels_by_group: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        labels_by_group[row["group_id"]].add(row["gold"])
    mixed_groups = [group for group, labels in labels_by_group.items() if len(labels) > 1]
    if mixed_groups:
        raise RuntimeError(f"Inspection grubunda celisen etiket: {len(mixed_groups)}")

    selected: dict[str, list[dict[str, Any]]] = {}
    for phase in PHASES:
        phase_rows = sorted((row for row in rows if row["phase"] == phase),
                            key=lambda row: row["id"])
        unique_by_group: dict[str, dict[str, Any]] = {}
        for row in phase_rows:
            unique_by_group.setdefault(row["group_id"], row)
        candidates = list(unique_by_group.values())
        abnormal = [row for row in candidates if row["subset"] == "abnormal"]
        chosen_abnormal: list[dict[str, Any]] = []
        chosen_normal: list[dict[str, Any]] = []
        for domain in sorted(EXPECTED_DOMAINS):
            domain_abnormal = [row for row in abnormal if row["domain"] == domain]
            domain_normal = [
                row for row in candidates
                if row["subset"] == "normal" and row["domain"] == domain
            ]
            if not domain_abnormal:
                raise RuntimeError(f"{phase}/{domain}: unsafe ornek yok")
            if not domain_normal:
                raise RuntimeError(f"{phase}/{domain}: normal ornek yok")
            target = min(len(domain_abnormal), len(domain_normal))
            chosen_abnormal.extend(_stratified_take(domain_abnormal, target))
            chosen_normal.extend(_stratified_take(domain_normal, target))
        chosen = chosen_abnormal + chosen_normal
        chosen_labels = {row["gold"] for row in chosen}
        chosen_domains = {row["domain"] for row in chosen}
        if chosen_labels != set(LABELS):
            raise RuntimeError(f"{phase}: eksik seviye: {sorted(set(LABELS) - chosen_labels)}")
        if chosen_domains != EXPECTED_DOMAINS:
            raise RuntimeError(f"{phase}: eksik alan: {sorted(EXPECTED_DOMAINS - chosen_domains)}")
        selected[phase] = sorted(chosen, key=lambda row: row["id"])

    group_sets = {phase: {row["group_id"] for row in selected[phase]} for phase in PHASES}
    for i, left in enumerate(PHASES):
        for right in PHASES[i + 1:]:
            if group_sets[left] & group_sets[right]:
                raise RuntimeError(f"Grup sizintisi: {left}/{right}")

    manifest_rows = [{key: row[key] for key in (
        "id", "relative_path", "annotation_relative_path", "gold", "path_gold", "subset",
        "domain", "size", "image_sha256", "group_id", "phase")}
        for row in rows]
    validation = {
        "dataset_revision": DATASET_REVISION,
        "count": len(rows),
        "subset_counts": dict(sorted(subset_counts.items())),
        "label_counts": dict(sorted(Counter(row["gold"] for row in rows).items())),
        "domain_counts": dict(sorted(domain_counts.items())),
        "unique_image_sha256": len(hashes),
        "duplicate_groups": sum(len(group) > 1 for group in hashes.values()),
        "inspection_components": len({row["group_id"] for row in rows}),
        "manifest_sha256": _canonical_json_sha(manifest_rows),
        "ground_truth_authority": "same-stem .txt sidecar (official scorer behavior)",
        "path_annotation_crosscheck": {
            "status": "mismatches_recorded" if path_annotation_mismatches else "pass",
            "mismatch_count": len(path_annotation_mismatches),
            "mismatches": path_annotation_mismatches,
        },
        "labels_sent_to_model": False,
        "sampling_policy": (
            "per-phase/per-domain 1:1 normal:unsafe independent-group sampling; "
            "larger side deterministically downsampled; all available unsafe severity "
            "labels retained then allocated proportionally"
        ),
        "selection": {
            phase: {
                "count": len(selected[phase]),
                "subset_counts": dict(sorted(Counter(row["subset"] for row in selected[phase]).items())),
                "label_counts": dict(sorted(Counter(row["gold"] for row in selected[phase]).items())),
                "domain_counts": dict(sorted(Counter(row["domain"] for row in selected[phase]).items())),
                "domain_subset_counts": {
                    domain: dict(sorted(Counter(
                        row["subset"] for row in selected[phase]
                        if row["domain"] == domain).items()))
                    for domain in sorted(EXPECTED_DOMAINS)
                },
                "groups": len(group_sets[phase]),
            }
            for phase in PHASES
        },
    }
    return rows, {"validation": validation, "selected": selected}


def _parse_allowed(raw: str | None, allowed: tuple[str, ...]) -> str | None:
    value = (raw or "").strip()
    return value if value in allowed else None


def _call_binary(video_url: str, observation: str,
                 official_prompt: str) -> tuple[str | None, float | None, dict[str, Any], dict[str, Any]]:
    client = VLMClient().gorev("olay")
    started = time.perf_counter()
    prompt = official_prompt + "\n\n" + BINARY_SUFFIX.format(observation=observation)
    raw = client.chat([
        {"role": "system", "content": BINARY_SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "video_url", "video_url": {"url": video_url}},
        ]},
    ], temperature=0.0, max_tokens=8, guided_choice=BINARY_CHOICES,
        logprobs=True, top_logprobs=20)
    logprob = getattr(client, "son_logprob", None) or {}
    distribution = secim_dagilimi(BINARY_CHOICES, logprob.get("ust") or {})
    masses = distribution.get("p") or {}
    unsafe_mass = float(masses.get("UNSAFE", 0.0))
    normal_mass = float(masses.get("NORMAL", 0.0))
    denominator = unsafe_mass + normal_mass
    score = unsafe_mass / denominator if denominator > 0.0 else None
    meta = {
        "stage": "binary", "role": "olay", "model": client.model,
        "latency_s": round(time.perf_counter() - started, 3),
        "retries": int(getattr(client, "son_deneme_sayisi", 0)),
        "usage": _usage(client),
    }
    return raw, score, distribution, meta


def _call_severity(video_url: str, observation: str,
                   official_prompt: str) -> tuple[str | None, dict[str, Any]]:
    client = VLMClient().gorev("olay")
    started = time.perf_counter()
    prompt = official_prompt + "\n\n" + SEVERITY_SUFFIX.format(observation=observation)
    raw = client.chat([
        {"role": "system", "content": SEVERITY_SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "video_url", "video_url": {"url": video_url}},
        ]},
    ], temperature=0.0, max_tokens=8, guided_choice=SEVERITY_CHOICES)
    return raw, {
        "stage": "severity", "role": "olay", "model": client.model,
        "latency_s": round(time.perf_counter() - started, 3),
        "retries": int(getattr(client, "son_deneme_sayisi", 0)),
        "usage": _usage(client),
    }


def probe(item: dict[str, Any], official_prompt: str,
          calibration: bool, decision_spec: dict[str, Any] | None) -> dict[str, Any]:
    started = time.perf_counter()
    calls: list[dict[str, Any]] = []
    observation = direct_raw = flat_raw = binary_raw = severity_raw = None
    observe_error = direct_error = flat_error = binary_error = severity_error = None
    direct_label = flat_label = binary_label = severity_label = None
    p_unsafe = None
    distribution: dict[str, Any] = {}
    score_fallback = False
    try:
        encoded = _still_as_video_url(Path(item["path"]))
    except Exception as exc:  # noqa: BLE001
        encoded = ""
        observe_error = _error(exc)

    if not observe_error:
        should_run_direct = (
            calibration
            or bool(decision_spec and decision_spec.get("architecture") == "consensus_hybrid")
        )
        if should_run_direct:
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
            flat_raw, meta = _call_classify(encoded, observation or "", official_prompt)
            meta["stage"] = "flat_classify"
            calls.append(meta)
            flat_label = _parse_allowed(flat_raw, LABELS)
            if flat_label is None:
                flat_error = "parse_error: invalid flat choice"
        except Exception as exc:  # noqa: BLE001
            flat_error = _error(exc)

        try:
            binary_raw, p_unsafe, distribution, meta = _call_binary(
                encoded, observation or "", official_prompt)
            calls.append(meta)
            binary_label = _parse_allowed(binary_raw, BINARY_CHOICES)
            if binary_label is None:
                binary_error = "parse_error: invalid binary choice"
            if p_unsafe is None and binary_label is not None:
                p_unsafe = 1.0 if binary_label == "UNSAFE" else 0.0
                score_fallback = True
        except Exception as exc:  # noqa: BLE001
            binary_error = _error(exc)

        locked_severity = False
        if p_unsafe is not None and decision_spec:
            if decision_spec.get("architecture") == "hierarchy":
                locked_severity = p_unsafe >= float(decision_spec["threshold"])
            elif decision_spec.get("architecture") == "hybrid":
                locked_severity = (
                    flat_label in (None, "NO_ABNORMALITY")
                    and p_unsafe >= float(decision_spec["rescue_threshold"])
                )
            elif decision_spec.get("architecture") == "consensus_hybrid":
                locked_severity = (
                    flat_label in (None, "NO_ABNORMALITY")
                    and direct_label in SEVERITY_CHOICES
                    and p_unsafe >= float(decision_spec["rescue_threshold"])
                )
        should_run_severity = (
            p_unsafe is not None and not binary_error
            and (calibration or locked_severity)
        )
        if should_run_severity:
            try:
                severity_raw, meta = _call_severity(encoded, observation or "", official_prompt)
                calls.append(meta)
                severity_label = _parse_allowed(severity_raw, SEVERITY_CHOICES)
                if severity_label is None:
                    severity_error = "parse_error: invalid severity choice"
            except Exception as exc:  # noqa: BLE001
                severity_error = _error(exc)

    return {
        "id": item["id"],
        "relative_path": item["relative_path"],
        "image_sha256": item["image_sha256"],
        "group_id": item["group_id"],
        "phase": item["phase"],
        "gold": item["gold"],
        "subset": item["subset"],
        "domain": item["domain"],
        "observation": observation,
        "observe_error": observe_error,
        "direct": {"label": direct_label, "raw": direct_raw, "error": direct_error},
        "flat": {"label": flat_label, "raw": flat_raw, "error": flat_error},
        "binary": {
            "label": binary_label, "raw": binary_raw, "error": binary_error,
            "p_unsafe": round(p_unsafe, 8) if p_unsafe is not None else None,
            "distribution": distribution, "score_fallback": score_fallback,
        },
        "severity": {"label": severity_label, "raw": severity_raw, "error": severity_error},
        "calls": calls,
        "latency_s": round(time.perf_counter() - started, 3),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def hierarchy_prediction(row: dict[str, Any], threshold: float) -> str | None:
    if row.get("observe_error") or row["binary"].get("error"):
        return None
    score = row["binary"].get("p_unsafe")
    if score is None:
        return None
    if float(score) < threshold:
        return "NO_ABNORMALITY"
    return row["severity"].get("label")


def hybrid_prediction(row: dict[str, Any], veto_threshold: float,
                      rescue_threshold: float) -> str | None:
    flat = row["flat"].get("label")
    if row.get("observe_error"):
        return flat if flat in LABELS else None
    if row["binary"].get("error"):
        return flat if flat in LABELS else None
    score = row["binary"].get("p_unsafe")
    if score is None:
        return flat if flat in LABELS else None
    score = float(score)
    if flat in SEVERITY_CHOICES:
        return "NO_ABNORMALITY" if score < veto_threshold else flat
    if score >= rescue_threshold:
        severity = row["severity"].get("label")
        return severity if severity in SEVERITY_CHOICES else (
            flat if flat in LABELS else None)
    return "NO_ABNORMALITY" if flat == "NO_ABNORMALITY" else None


def consensus_hybrid_prediction(row: dict[str, Any], veto_threshold: float,
                                rescue_threshold: float) -> str | None:
    """Duz karari koru; yardimci VLM ve ikili hakem uzlasirsa degistir."""
    flat = row["flat"].get("label")
    if row.get("observe_error") or row["binary"].get("error"):
        return flat if flat in LABELS else None
    score = row["binary"].get("p_unsafe")
    if score is None:
        return flat if flat in LABELS else None
    direct = row.get("direct", {}).get("label")
    score = float(score)
    if flat in SEVERITY_CHOICES:
        if direct == "NO_ABNORMALITY" and score < veto_threshold:
            return "NO_ABNORMALITY"
        return flat
    if direct in SEVERITY_CHOICES and score >= rescue_threshold:
        severity = row["severity"].get("label")
        return severity if severity in SEVERITY_CHOICES else (
            flat if flat in LABELS else None)
    return "NO_ABNORMALITY" if flat == "NO_ABNORMALITY" else None


def candidate_prediction(row: dict[str, Any], spec: dict[str, Any]) -> str | None:
    architecture = spec.get("architecture")
    if architecture == "hierarchy":
        return hierarchy_prediction(row, float(spec["threshold"]))
    if architecture == "hybrid":
        return hybrid_prediction(
            row, float(spec["veto_threshold"]), float(spec["rescue_threshold"]))
    if architecture == "consensus_hybrid":
        return consensus_hybrid_prediction(
            row, float(spec["veto_threshold"]), float(spec["rescue_threshold"]))
    raise ValueError(f"Bilinmeyen karar mimarisi: {architecture}")


def severity_call_rate(rows: list[dict[str, Any]], spec: dict[str, Any]) -> float:
    needed = 0
    for row in rows:
        score = row["binary"].get("p_unsafe")
        if score is None:
            continue
        if spec["architecture"] == "hierarchy":
            needed += float(score) >= float(spec["threshold"])
        elif spec["architecture"] == "hybrid":
            needed += (
                row["flat"].get("label") in (None, "NO_ABNORMALITY")
                and float(score) >= float(spec["rescue_threshold"])
            )
        else:
            needed += (
                row["flat"].get("label") in (None, "NO_ABNORMALITY")
                and row.get("direct", {}).get("label") in SEVERITY_CHOICES
                and float(score) >= float(spec["rescue_threshold"])
            )
    return round(needed / len(rows), 8) if rows else 0.0


def evaluate(rows: list[dict[str, Any]], predictor: Callable[[dict[str, Any]], str | None]) -> dict[str, Any]:
    confusion = {gold: {pred: 0 for pred in (*LABELS, "INVALID")} for gold in LABELS}
    tp = tn = fp = fn = valid = correct = 0
    for row in rows:
        gold = row["gold"]
        pred = predictor(row)
        key = pred if pred in LABELS else "INVALID"
        confusion[gold][key] += 1
        if pred in LABELS:
            valid += 1
        if pred == gold:
            correct += 1
        gold_unsafe = gold != "NO_ABNORMALITY"
        if pred not in LABELS:
            if gold_unsafe:
                fn += 1
            else:
                fp += 1
        else:
            pred_unsafe = pred != "NO_ABNORMALITY"
            if gold_unsafe and pred_unsafe:
                tp += 1
            elif gold_unsafe:
                fn += 1
            elif pred_unsafe:
                fp += 1
            else:
                tn += 1

    recall = tp / (tp + fn) if tp + fn else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    denominator = recall * TEST_UNSAFE_PRIOR + fpr * (1.0 - TEST_UNSAFE_PRIOR)
    precision_prior = recall * TEST_UNSAFE_PRIOR / denominator if denominator else 0.0
    f1_prior = (2.0 * precision_prior * recall / (precision_prior + recall)
                if precision_prior + recall else 0.0)
    per_class: dict[str, dict[str, Any]] = {}
    weighted_accuracy = 0.0
    for label in LABELS:
        support = sum(confusion[label].values())
        class_recall = confusion[label][label] / support if support else 0.0
        per_class[label] = {
            "support": support,
            "correct": confusion[label][label],
            "recall": round(class_recall, 8),
        }
        weighted_accuracy += TEST_PRIORS[label] * class_recall
    macro_recall = sum(value["recall"] for value in per_class.values()) / len(LABELS)
    by_domain: dict[str, dict[str, Any]] = {}
    for domain in sorted({row["domain"] for row in rows}):
        domain_rows = [row for row in rows if row["domain"] == domain]
        d_tp = d_tn = d_fp = d_fn = d_correct = 0
        for row in domain_rows:
            pred = predictor(row)
            if pred == row["gold"]:
                d_correct += 1
            gold_unsafe = row["gold"] != "NO_ABNORMALITY"
            if pred not in LABELS:
                if gold_unsafe:
                    d_fn += 1
                else:
                    d_fp += 1
                continue
            pred_unsafe = pred != "NO_ABNORMALITY"
            if gold_unsafe and pred_unsafe:
                d_tp += 1
            elif gold_unsafe:
                d_fn += 1
            elif pred_unsafe:
                d_fp += 1
            else:
                d_tn += 1
        d_recall = d_tp / (d_tp + d_fn) if d_tp + d_fn else 0.0
        d_fpr = d_fp / (d_fp + d_tn) if d_fp + d_tn else 0.0
        d_denominator = d_recall * TEST_UNSAFE_PRIOR + d_fpr * (1.0 - TEST_UNSAFE_PRIOR)
        d_precision = (d_recall * TEST_UNSAFE_PRIOR / d_denominator
                       if d_denominator else 0.0)
        by_domain[domain] = {
            "n": len(domain_rows), "tp": d_tp, "tn": d_tn,
            "fp": d_fp, "fn": d_fn,
            "accuracy": rate(d_correct, len(domain_rows)),
            "recall": rate(d_tp, d_tp + d_fn),
            "fpr": rate(d_fp, d_fp + d_tn),
            "test_prior_precision": round(d_precision, 8),
        }
    return {
        "n": len(rows),
        "coverage": rate(valid, len(rows)),
        "empirical_accuracy": rate(correct, len(rows)),
        "test_prior_weighted_accuracy": round(weighted_accuracy, 8),
        "macro_recall": round(macro_recall, 8),
        "binary": {
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "recall": rate(tp, tp + fn),
            "fpr": rate(fp, fp + tn),
            "test_prior_precision": round(precision_prior, 8),
            "test_prior_f1": round(f1_prior, 8),
        },
        "per_class": per_class,
        "by_domain": by_domain,
        "confusion": confusion,
    }


def non_regression_gate(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    eps = 1e-12
    baseline_worst_recall = min(
        value["recall"]["p"] for value in baseline["by_domain"].values())
    candidate_worst_recall = min(
        value["recall"]["p"] for value in candidate["by_domain"].values())
    baseline_worst_fpr = max(
        value["fpr"]["p"] for value in baseline["by_domain"].values())
    candidate_worst_fpr = max(
        value["fpr"]["p"] for value in candidate["by_domain"].values())
    all_domain_recall = all(
        candidate["by_domain"][domain]["recall"]["p"] + eps
        >= baseline["by_domain"][domain]["recall"]["p"]
        for domain in baseline["by_domain"]
    )
    all_domain_fpr = all(
        candidate["by_domain"][domain]["fpr"]["p"]
        <= baseline["by_domain"][domain]["fpr"]["p"] + eps
        for domain in baseline["by_domain"]
    )
    strict_gain = any((
        candidate["binary"]["test_prior_precision"]
        > baseline["binary"]["test_prior_precision"] + eps,
        candidate["binary"]["recall"]["p"]
        > baseline["binary"]["recall"]["p"] + eps,
        candidate["binary"]["fpr"]["p"] + eps
        < baseline["binary"]["fpr"]["p"],
        candidate["test_prior_weighted_accuracy"]
        > baseline["test_prior_weighted_accuracy"] + eps,
    ))
    checks = {
        "unsafe_precision_non_decreasing": (
            candidate["binary"]["test_prior_precision"] + eps
            >= baseline["binary"]["test_prior_precision"]),
        "unsafe_recall_non_decreasing": (
            candidate["binary"]["recall"]["p"] + eps
            >= baseline["binary"]["recall"]["p"]),
        "normal_fpr_non_increasing": (
            candidate["binary"]["fpr"]["p"]
            <= baseline["binary"]["fpr"]["p"] + eps),
        "weighted_accuracy_non_decreasing": (
            candidate["test_prior_weighted_accuracy"] + eps
            >= baseline["test_prior_weighted_accuracy"]),
        "level_one_recall_non_decreasing": (
            candidate["per_class"]["LEVEL_ONE"]["recall"] + eps
            >= baseline["per_class"]["LEVEL_ONE"]["recall"]),
        "worst_domain_recall_non_decreasing": (
            candidate_worst_recall + eps >= baseline_worst_recall),
        "worst_domain_fpr_non_increasing": (
            candidate_worst_fpr <= baseline_worst_fpr + eps),
        "every_domain_recall_non_decreasing": all_domain_recall,
        "every_domain_fpr_non_increasing": all_domain_fpr,
        "coverage_at_least_99pct": candidate["coverage"]["p"] >= 0.99,
        "at_least_one_strict_primary_gain": strict_gain,
    }
    return {"checks": checks, "pass": all(checks.values())}


def select_threshold(rows: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = evaluate(rows, lambda row: row["flat"].get("label"))
    candidates: list[dict[str, Any]] = []
    for threshold in THRESHOLDS:
        spec = {"architecture": "hierarchy", "threshold": threshold}
        metrics = evaluate(rows, lambda row, s=spec: candidate_prediction(row, s))
        gate = non_regression_gate(baseline, metrics)
        candidates.append({
            "spec": spec, "metrics": metrics, "gate": gate,
            "severity_call_rate": severity_call_rate(rows, spec),
        })
    for veto_threshold in VETO_THRESHOLDS:
        for rescue_threshold in RESCUE_THRESHOLDS:
            spec = {
                "architecture": "hybrid",
                "veto_threshold": veto_threshold,
                "rescue_threshold": rescue_threshold,
            }
            metrics = evaluate(rows, lambda row, s=spec: candidate_prediction(row, s))
            gate = non_regression_gate(baseline, metrics)
            candidates.append({
                "spec": spec, "metrics": metrics, "gate": gate,
                "severity_call_rate": severity_call_rate(rows, spec),
            })
            consensus_spec = {
                "architecture": "consensus_hybrid",
                "veto_threshold": veto_threshold,
                "rescue_threshold": rescue_threshold,
            }
            consensus_metrics = evaluate(
                rows, lambda row, s=consensus_spec: candidate_prediction(row, s))
            consensus_gate = non_regression_gate(baseline, consensus_metrics)
            candidates.append({
                "spec": consensus_spec,
                "metrics": consensus_metrics,
                "gate": consensus_gate,
                "severity_call_rate": severity_call_rate(rows, consensus_spec),
            })
    feasible = [candidate for candidate in candidates if candidate["gate"]["pass"]]
    selected = max(
        feasible,
        key=lambda candidate: (
            candidate["metrics"]["binary"]["test_prior_f1"],
            candidate["metrics"]["test_prior_weighted_accuracy"],
            -candidate["severity_call_rate"],
            candidate["spec"]["architecture"] == "hierarchy",
        ),
        default=None,
    )
    return {"baseline": baseline, "candidates": candidates, "selected": selected}


def compare_at_spec(rows: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    baseline = evaluate(rows, lambda row: row["flat"].get("label"))
    candidate = evaluate(rows, lambda row: candidate_prediction(row, spec))
    baseline_correct = [row["flat"].get("label") == row["gold"] for row in rows]
    candidate_correct = [candidate_prediction(row, spec) == row["gold"] for row in rows]
    fixed = sum((not left) and right for left, right in zip(baseline_correct, candidate_correct))
    broke = sum(left and (not right) for left, right in zip(baseline_correct, candidate_correct))
    return {
        "spec": spec,
        "baseline": baseline,
        "candidate": candidate,
        "severity_call_rate": severity_call_rate(rows, spec),
        "gate": non_regression_gate(baseline, candidate),
        "paired": {
            "candidate_fixed": fixed,
            "candidate_broke": broke,
            "mcnemar_exact_p": mcnemar_exact_p(fixed, broke),
        },
    }


def execution_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bindings = Counter(
        (call.get("stage"), call.get("role"), call.get("model"))
        for row in rows for call in row.get("calls", [])
    )
    retries = [int(call.get("retries") or 0)
               for row in rows for call in row.get("calls", [])]
    return {
        "rows": len(rows),
        "observe_errors": sum(bool(row.get("observe_error")) for row in rows),
        "direct_errors": sum(bool(row.get("direct", {}).get("error")) for row in rows),
        "flat_errors": sum(bool(row["flat"].get("error")) for row in rows),
        "binary_errors": sum(bool(row["binary"].get("error")) for row in rows),
        "severity_errors": sum(bool(row["severity"].get("error")) for row in rows),
        "score_fallbacks": sum(bool(row["binary"].get("score_fallback")) for row in rows),
        "retry_calls": sum(value > 0 for value in retries),
        "max_retries": max(retries, default=0),
        "call_bindings": [
            {"stage": stage, "role": role, "model": model, "calls": count}
            for (stage, role, model), count in sorted(bindings.items())
        ],
    }


def _load_journal(path: Path, run_key: str) -> dict[str, dict[str, Any]]:
    done: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return done
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("run_key") != run_key:
            raise RuntimeError(f"Jurnal kosum anahtari uyusmuyor: satir {line_number}")
        row = record.get("row") or {}
        sample_id = row.get("id")
        if not sample_id or sample_id in done:
            raise RuntimeError(f"Jurnalde gecersiz/tekrar kimlik: satir {line_number}")
        done[sample_id] = row
    return done


def _append_journal(path: Path, run_key: str, row: dict[str, Any]) -> None:
    record = json.dumps({"run_key": run_key, "row": row}, ensure_ascii=False, sort_keys=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _lock_path(manifest_sha: str) -> Path:
    return RESULTS / f"inspecsafe_hier_lock_{manifest_sha[:16]}.json"


def _dev_pass_path(lock_hash: str) -> Path:
    return RESULTS / f"inspecsafe_hier_development_pass_{lock_hash[:16]}.json"


def _read_lock(path: Path, expected: dict[str, Any]) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise RuntimeError(f"Calibration kilidi yok: {path}")
    lock = json.loads(path.read_text(encoding="utf-8"))
    for key in (
        "runner_sha256", "manifest_sha256", "prompt_hashes", "contract",
        "private_api", "dataset_revision", "official_code_revision",
        "split_salt", "revision",
    ):
        if lock.get(key) != expected.get(key):
            raise RuntimeError(f"Calibration kilidi degisti: {key}")
    return lock, _canonical_json_sha(lock)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=PHASES, default="calibration")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--smoke", type=int, default=0)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.workers < 1 or args.smoke < 0:
        parser.error("--workers >= 1 ve --smoke >= 0 olmali")

    official_prompt = _load_official_prompt()
    archive = verify_train_archive(args.archive)
    all_rows, discovered = discover_train(args.data_root.resolve())
    validation = discovered["validation"]
    selected = discovered["selected"][args.phase]
    contract = _contract()
    prompts = _prompt_hashes(official_prompt)
    runner_sha = _sha_file(Path(__file__))
    manifest_sha = validation["manifest_sha256"]
    RESULTS.mkdir(parents=True, exist_ok=True)
    manifest_path = RESULTS / f"inspecsafe_train_manifest_{manifest_sha[:16]}.json"
    manifest_path.write_text(json.dumps({
        "validation": validation,
        "items": [{key: row[key] for key in (
            "id", "relative_path", "annotation_relative_path", "gold", "path_gold", "subset",
            "domain", "size", "image_sha256", "group_id", "phase")}
            for row in all_rows],
    }, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    expected_lock = {
        "runner_sha256": runner_sha,
        "manifest_sha256": manifest_sha,
        "prompt_hashes": prompts,
        "contract": contract,
        "private_api": PRIVATE_API,
        "dataset_revision": DATASET_REVISION,
        "official_code_revision": OFFICIAL_CODE_REVISION,
        "split_salt": SPLIT_SALT,
        "revision": REVISION,
    }
    calibration_lock_path = _lock_path(manifest_sha)
    if (args.phase == "calibration" and not args.smoke and not args.validate_only
            and calibration_lock_path.exists()):
        raise RuntimeError(
            f"Calibration kilidi degistirilemez; zaten var: {calibration_lock_path}")
    decision_spec = None
    lock_hash = None
    if args.phase != "calibration":
        lock, lock_hash = _read_lock(calibration_lock_path, expected_lock)
        decision_spec = dict(lock["decision_spec"])
        if (args.phase == "development" and not args.smoke and not args.validate_only
                and _dev_pass_path(lock_hash).exists()):
            raise RuntimeError("Development onayi degistirilemez; kilit zaten gecmis")
        if args.phase == "holdout":
            pass_path = _dev_pass_path(lock_hash)
            if not pass_path.is_file():
                raise RuntimeError("Development kapisi gecmeden holdout acilamaz")
            approval = json.loads(pass_path.read_text(encoding="utf-8"))
            if approval.get("lock_hash") != lock_hash or not approval.get("gate_pass"):
                raise RuntimeError("Development onayi calibration kilidiyle uyusmuyor")

    if args.smoke:
        selected = selected[:args.smoke]
    protocol = {
        "revision": REVISION,
        "phase": args.phase,
        "smoke": args.smoke,
        "dataset_revision": DATASET_REVISION,
        "official_code_revision": OFFICIAL_CODE_REVISION,
        "archive": archive,
        "manifest_sha256": manifest_sha,
        "runner_sha256": runner_sha,
        "prompt_hashes": prompts,
        "contract": contract,
        "decision_spec": decision_spec,
        "search_grid": ({
            "hierarchy": THRESHOLDS,
            "hybrid_veto": VETO_THRESHOLDS,
            "hybrid_rescue": RESCUE_THRESHOLDS,
            "consensus_hybrid_veto": VETO_THRESHOLDS,
            "consensus_hybrid_rescue": RESCUE_THRESHOLDS,
        } if args.phase == "calibration" else None),
        "split_salt": SPLIT_SALT,
        "labels_sent_to_model": False,
        "generation": {
            "temperature": 0.0,
            "repeats": 1,
            "max_tokens": {"observe": 256, "flat": 8, "binary": 8, "severity": 8},
            "media_transport": {
                "type": "two identical frames in MP4",
                "codec": "H.264 libx264, CRF=0, yuv420p, 2 fps",
                "temporal_information_added": False,
            },
        },
    }
    run_key = _canonical_json_sha(protocol)[:16]
    print(f"InspecSafe-V1 train PASS: n={validation['count']} manifest={manifest_sha}")
    print(f"selection={validation['selection'][args.phase]} phase={args.phase}")
    print(f"private_api={PRIVATE_API} models={CONTRACT} run_key={run_key}")
    if args.validate_only:
        print(f"manifest={manifest_path}")
        return 0

    journal = RESULTS / f".inspecsafe_hier_{args.phase}_{run_key}.jsonl"
    done = _load_journal(journal, run_key)
    pending = [item for item in selected if item["id"] not in done]
    print(f"checkpoint={len(done)} selected={len(selected)} pending={len(pending)} workers={args.workers}")
    started = time.perf_counter()
    completed_now = 0
    calibration = args.phase == "calibration"
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(probe, item, official_prompt, calibration, decision_spec): item
            for item in pending
        }
        for future in as_completed(futures):
            item = futures[future]
            try:
                row = future.result()
            except Exception as exc:  # pragma: no cover
                raise RuntimeError(f"Satir islenemedi: {item['id']}: {_error(exc)}") from exc
            _append_journal(journal, run_key, row)
            done[row["id"]] = row
            completed_now += 1
            total = sum(item["id"] in done for item in selected)
            elapsed = time.perf_counter() - started
            speed = completed_now / elapsed if elapsed else 0.0
            eta = (len(selected) - total) / speed if speed else 0.0
            print(f"[{total}/{len(selected)}] {row['id']} calls={len(row['calls'])} "
                  f"row={row['latency_s']:.1f}s eta={eta/60:.1f}m", flush=True)

    rows = [done[item["id"]] for item in selected]
    if args.smoke:
        complete = sum(
            row["observation"] is not None
            and (
                not calibration
                or row["direct"]["label"] is not None
            )
            and row["flat"]["label"] is not None
            and row["binary"]["p_unsafe"] is not None
            and (
                row["severity"]["label"] is not None
                if calibration else candidate_prediction(row, decision_spec or {}) in LABELS
            )
            for row in rows
        )
        if complete != len(rows):
            raise RuntimeError(f"Smoke kapisi kaldi: {complete}/{len(rows)}")
        print(f"SMOKE PASS: {complete}/{len(rows)}; skor gizlendi")
        return 0

    if args.phase == "calibration":
        summary = select_threshold(rows)
    else:
        if decision_spec is None:
            raise RuntimeError("Kilitli karar tanimi yok")
        summary = compare_at_spec(rows, decision_spec)
    summary["execution"] = execution_summary(rows)

    result = {
        "meta": {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "run_key": run_key,
            "protocol": protocol,
            "dataset_validation": validation,
            "journal": str(journal),
            "manifest": str(manifest_path),
        },
        "summary": summary,
        "rows": rows,
    }
    result_path = RESULTS / f"inspecsafe_hier_{args.phase}_{run_key}.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
                           encoding="utf-8")
    print(f"RESULT={result_path}")

    if args.phase == "calibration":
        selected_candidate = summary.get("selected")
        if selected_candidate is None:
            print("CALIBRATION GATE FAILED: uygun esik yok")
            return 2
        lock = {
            **expected_lock,
            "decision_spec": selected_candidate["spec"],
            "calibration_run_key": run_key,
            "calibration_result_sha256": _sha_file(result_path),
            "selection_objective": (
                "prior_f1, weighted_accuracy, lower_severity_call_rate, simpler_architecture"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        lock_path = calibration_lock_path
        lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True),
                             encoding="utf-8")
        print(f"LOCK={lock_path} decision_spec={json.dumps(lock['decision_spec'], sort_keys=True)}")
        return 0

    gate_pass = bool(summary["gate"]["pass"])
    print(json.dumps({"decision_spec": decision_spec, "gate": summary["gate"]}, indent=2))
    if args.phase == "development" and gate_pass:
        if lock_hash is None:
            raise RuntimeError("Calibration lock hash yok")
        approval = {
            "lock_hash": lock_hash,
            "gate_pass": True,
            "development_run_key": run_key,
            "development_result_sha256": _sha_file(result_path),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        approval_path = _dev_pass_path(lock_hash)
        approval_path.write_text(json.dumps(approval, indent=2, sort_keys=True), encoding="utf-8")
        print(f"DEVELOPMENT_PASS={approval_path}")
    return 0 if gate_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
