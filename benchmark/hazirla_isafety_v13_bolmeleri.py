#!/usr/bin/env python
"""Daha önce görülmemiş yerel iSafety kliplerinden v13 dev + holdout'u tek sefer kur."""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "isafety_bench" / "videos"
DEV = ROOT / "data" / "eval_genelleme_v13_dev"
HOLDOUT = ROOT / "data" / "eval_genelleme_holdout_v13"
MANIFEST = ROOT / "data" / "isafety_v13_split_manifest.json"
SEED = 2026082713
MP4_RE = re.compile(r'([^"/\\]+\.mp4)', re.IGNORECASE)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _seen_names() -> set[str]:
    seen: set[str] = set()
    for path in (ROOT / "data").glob("eval*"):
        if path.is_dir():
            seen.update(x.name for x in path.rglob("*.mp4"))
    results = ROOT / "benchmark" / "results"
    for path in results.rglob("*.json"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        seen.update(m.group(1) for m in MP4_RE.finditer(text))
    return seen


def _pool(column: str, seen: set[str]) -> list[Path]:
    return sorted((x for x in (SOURCE / column).glob("*.mp4")
                   if x.name not in seen), key=lambda x: x.name)


def main() -> int:
    if DEV.exists() or HOLDOUT.exists() or MANIFEST.exists():
        raise RuntimeError("v13 hedefi/manifesti zaten var; üzerine yazma reddedildi")
    seen = _seen_names()
    rng = random.Random(SEED)
    pools = {column: _pool(column, seen) for column in ("hazard", "normal")}
    for column, pool in pools.items():
        if len(pool) < 200:
            raise RuntimeError(f"{column} için 200 görülmemiş klip yok: {len(pool)}")
        rng.shuffle(pool)

    rows = []
    for column, category in (("hazard", ("Anomali", "Hazard")),
                             ("normal", ("Normal", "Normal"))):
        pool = pools[column]
        for split, root, chosen in (("dev", DEV, pool[:100]),
                                    ("holdout", HOLDOUT, pool[100:200])):
            target_dir = root.joinpath(*category)
            target_dir.mkdir(parents=True, exist_ok=False)
            for src in chosen:
                dst = target_dir / src.name
                shutil.copy2(src, dst)
                rows.append({
                    "split": split, "column": column,
                    "source": src.relative_to(ROOT).as_posix(),
                    "target": dst.relative_to(ROOT).as_posix(),
                    "sha256": _sha256(dst), "size": dst.stat().st_size,
                })
    payload = {
        "revision": "isafety-v13-unseen-split-2026-08-27",
        "seed": SEED, "excluded_name_count": len(seen),
        "available_unseen": {k: len(v) for k, v in pools.items()},
        "counts": {"dev_hazard": 100, "dev_normal": 100,
                   "holdout_hazard": 100, "holdout_normal": 100},
        "rows": rows,
    }
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(json.dumps({k: payload[k] for k in
                      ("revision", "seed", "excluded_name_count",
                       "available_unseen", "counts")}, ensure_ascii=False, indent=2))
    print(MANIFEST.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
