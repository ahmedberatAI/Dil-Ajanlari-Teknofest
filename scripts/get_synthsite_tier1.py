#!/usr/bin/env python
"""SynthSite'in yalnizca insan-uzlasili Tier-1 bolumunu indir ve dogrula.

Bu betik model veya model agirligi indirmez. Yalniz veri setinin sabitlenmis
revizyonundaki etiketleri ve 150 video klibini indirir.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from huggingface_hub import snapshot_download


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "external" / "synthsite"
REPO_ID = "govtech/SynthSite"
REVISION = "2904ec01c3dbf2efba09f2cb1b7bdf17841d4d39"
LABEL_FILE = "synthetic_video_labels.csv"
META_PATTERNS = [
    "README.md",
    "LICENSE",
    LABEL_FILE,
    "results/annotators_agreement/*",
    "docs/*",
]


def tier1_satirlari(label_path: Path) -> list[dict[str, str]]:
    with label_path.open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("tier") == "1"]

    if len(rows) != 150:
        raise RuntimeError(f"SynthSite Tier-1 sayisi 150 olmali, bulunan={len(rows)}")
    counts = {"True_Positive": 0, "False_Positive": 0}
    for row in rows:
        resolved = row.get("resolved_label", "")
        if resolved not in counts:
            raise RuntimeError(f"Bilinmeyen etiket: {resolved!r}")
        labels = [
            row.get(f"labeler_{i}_label", "").strip()
            for i in range(1, 4)
            if row.get(f"labeler_{i}_label", "").strip()
        ]
        if len(labels) < 2 or len(labels) != int(row.get("num_labelers") or 0):
            raise RuntimeError(f"Eksik degerlendirici etiketi: {row.get('filename')}")
        if any(label != resolved for label in labels):
            raise RuntimeError(f"Tier-1 uzlasisi bozuk: {row.get('filename')}")
        counts[resolved] += 1
    if counts != {"True_Positive": 76, "False_Positive": 74}:
        raise RuntimeError(f"Beklenmeyen sinif dagilimi: {counts}")
    return rows


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        revision=REVISION,
        local_dir=str(DEST),
        allow_patterns=META_PATTERNS,
    )
    rows = tier1_satirlari(DEST / LABEL_FILE)
    paths = [f"videos/{r['filename']}" for r in rows]
    snapshot_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        revision=REVISION,
        local_dir=str(DEST),
        allow_patterns=paths,
    )

    files = []
    for rel in paths:
        path = DEST / rel
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"Eksik/bos video: {rel}")
        files.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha256(path)})

    manifest = {
        "dataset": "SynthSite Tier-1",
        "repo_id": REPO_ID,
        "revision": REVISION,
        "license": "GovTech Singapore Open Source Software Licence",
        "selection": "tier == 1; en az iki insan degerlendirici tam uzlasili",
        "n": len(rows),
        "unsafe": 76,
        "safe": 74,
        "files": files,
    }
    target = DEST / "tier1_download_manifest.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)
    print(f"Dogrulandi: {len(files)} video, {sum(x['bytes'] for x in files)/1e9:.3f} GB")
    print(target)


if __name__ == "__main__":
    main()
