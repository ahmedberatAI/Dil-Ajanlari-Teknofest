#!/usr/bin/env python
"""iSafetyBench'ten daha önce kullanılmamış, hash-kilitli v12 holdout kurar."""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DATA = os.path.join(ROOT, "data")
SOURCE = os.path.join(DATA, "isafety_bench", "videos")
TARGET = os.path.join(DATA, "eval_genelleme_holdout_v12")
RESULTS = os.path.join(ROOT, "benchmark", "results")
SEED = 20260827
N_PER_CLASS = 100


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _json_video_names(value) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for v in value.values():
            out.update(_json_video_names(v))
    elif isinstance(value, list):
        for v in value:
            out.update(_json_video_names(v))
    elif isinstance(value, str) and re.search(r"\.(mp4|avi|mkv|mov)$", value, re.I):
        out.add(os.path.basename(value))
    return out


def _used_names() -> set[str]:
    """Kaynak havuzu dışındaki kopyalar ve arşivlenmiş ölçüm yolları."""
    used: set[str] = set()
    source_abs = os.path.abspath(SOURCE)
    target_abs = os.path.abspath(TARGET)
    for base, _dirs, files in os.walk(DATA):
        base_abs = os.path.abspath(base)
        if base_abs.startswith(source_abs) or base_abs.startswith(target_abs):
            continue
        for name in files:
            if name.lower().endswith((".mp4", ".avi", ".mkv", ".mov")):
                used.add(name)
    if os.path.isdir(RESULTS):
        for name in os.listdir(RESULTS):
            if not (name.startswith("isafety_") and name.endswith(".json")):
                continue
            try:
                with open(os.path.join(RESULTS, name), encoding="utf-8") as f:
                    used.update(_json_video_names(json.load(f)))
            except Exception:
                continue
    return used


def main() -> int:
    from dilajan.veri_lisans import degerlendirmede_kullanilabilir
    if not degerlendirmede_kullanilabilir("data/isafety_bench"):
        raise RuntimeError("iSafetyBench değerlendirme lisans kapısı kapalı")
    if os.path.exists(TARGET):
        raise RuntimeError(f"Holdout hedefi zaten var; üzerine yazılmadı: {TARGET}")
    used = _used_names()
    plan = (("hazard", "Anomali", "Hazard"),
            ("normal", "Normal", "Normal"))
    selected: list[dict] = []
    staged: list[tuple[str, str]] = []
    for index, (source_class, bucket, leaf) in enumerate(plan):
        source_dir = os.path.join(SOURCE, source_class)
        candidates = [os.path.join(source_dir, n)
                      for n in sorted(os.listdir(source_dir))
                      if n.lower().endswith(".mp4") and n not in used]
        if len(candidates) < N_PER_CLASS:
            raise RuntimeError(
                f"{source_class}: {N_PER_CLASS} benzersiz aday gerekli, {len(candidates)} var")
        rng = random.Random(SEED + index)
        chosen = rng.sample(candidates, N_PER_CLASS)
        target_dir = os.path.join(TARGET, bucket, leaf)
        for src in sorted(chosen):
            dst = os.path.join(target_dir, os.path.basename(src))
            staged.append((src, dst))
            selected.append({
                "label": source_class,
                "source": os.path.relpath(src, ROOT).replace("\\", "/"),
                "target": os.path.relpath(dst, ROOT).replace("\\", "/"),
                "sha256": _sha256(src),
            })

    for _src, dst in staged:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
    for src, dst in staged:
        os.link(src, dst)
    manifest = {
        "dataset": "iSafetyBench",
        "purpose": "evaluation_only_unseen_v12_holdout",
        "seed": SEED,
        "n_per_class": N_PER_CLASS,
        "excluded_previously_used_names": len(used),
        "items": selected,
    }
    with open(os.path.join(TARGET, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(json.dumps({"target": os.path.relpath(TARGET, ROOT).replace("\\", "/"),
                      "n": len(selected), "used_excluded": len(used)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
