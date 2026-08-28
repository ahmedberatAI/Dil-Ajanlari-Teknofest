#!/usr/bin/env python3
"""Project RISE'tan ayrik duman gelistirme ve kilitli dogrulama setleri kur.

Secim model ciktisindan tamamen bagimsizdir. Her bolmede tek kamera/gorus/gun
kullanilir; guclu arastirmaci etiketlerinden azinlik sinifinin tamami, cogunluk
sinifinin ise gunu bastan sona kapsayan sabit nicelik (quantile) ornegi alinir.

Bolmeler:
  * dev:     camera=0, view=5, 2018-06-11 -> 33 + 33
  * dev_optical: camera=1, view=0, 2018-08-24 -> 24 + 24
  * holdout: camera=2, view=0, 2018-06-12 -> 23 + 23

Ilk Project RISE benchmarki (camera=0, view=0, 2019-02-02) bu dosyada bilincli
olarak yoktur; donmus sonuc ayar verisine donusturulmez.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "external" / "deep_smoke_machine_e796bf3"
METADATA_PATH = SOURCE_DIR / "metadata_02242020.json"
OUT_ROOT = ROOT / "data" / "eval_deep_smoke_v2"

SOURCE_REPO = "https://github.com/CMU-CREATE-Lab/deep-smoke-machine"
SOURCE_COMMIT = "e796bf36988226b8bc657872bdc83c6cbad791cd"
METADATA_SHA256 = "cc85ad6db07557ae4afacc4f12f443b6e68ae0d88e30869fcf031f4c7dc7ee18"
LABEL_MAP = {23: 1, 16: 0}


@dataclass(frozen=True)
class SplitSpec:
    name: str
    camera_id: int
    view_id: int
    date: str
    expected_raw: tuple[int, int]  # (no-smoke, smoke)
    target_per_class: int
    role: str

    @property
    def prefix(self) -> str:
        return f"{self.camera_id}-{self.view_id}-{self.date}-"


SPECS = {
    "dev": SplitSpec(
        "dev", 0, 5, "2018-06-11", (51, 33), 33,
        "architecture development; labels may be inspected after inference",
    ),
    "dev_optical": SplitSpec(
        "dev_optical", 1, 0, "2018-08-24", (24, 34), 24,
        "fresh architecture development for smoke-versus-steam evidence; "
        "frozen after v2 plume-presence failure and before v3 inference",
    ),
    "holdout": SplitSpec(
        "holdout", 2, 0, "2018-06-12", (23, 27), 23,
        "locked final validation; no tuning after unsealing",
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_url_320(row: dict[str, Any]) -> str:
    root = str(row["url_root"]).replace("/180/", "/320/")
    part = str(row["url_part"]).replace("-180-180-", "-320-320-")
    return root + part


def evenly_spaced(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    """Sirali gun akisini bastan sona kapsayan deterministik alt ornek."""
    if count > len(rows):
        raise ValueError(f"{count} ornek {len(rows)} kayittan secilemez")
    if count == len(rows):
        return list(rows)
    if count == 1:
        return [rows[len(rows) // 2]]
    indices = [round(i * (len(rows) - 1) / (count - 1)) for i in range(count)]
    if len(set(indices)) != count:
        raise RuntimeError(f"Nicelik secimi benzersiz indeks vermedi: {indices}")
    return [rows[index] for index in indices]


def load_metadata() -> list[dict[str, Any]]:
    if not METADATA_PATH.is_file():
        raise FileNotFoundError(f"Resmi metadata bulunamadi: {METADATA_PATH}")
    actual = sha256_file(METADATA_PATH)
    if actual != METADATA_SHA256:
        raise RuntimeError(
            "Metadata SHA256 uyusmuyor; bolmeler sessizce degistirilmeyecek: "
            f"actual={actual}, expected={METADATA_SHA256}"
        )
    rows = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise TypeError("Project RISE metadata kokunun liste olmasi bekleniyordu")
    return rows


def select_rows(rows: list[dict[str, Any]], spec: SplitSpec) -> list[dict[str, Any]]:
    eligible = [
        row for row in rows
        if int(row.get("camera_id", -1)) == spec.camera_id
        and int(row.get("view_id", -1)) == spec.view_id
        and str(row.get("file_name", "")).startswith(spec.prefix)
        and int(row.get("label_state_admin", -999)) in LABEL_MAP
    ]
    by_gold: dict[int, list[dict[str, Any]]] = {0: [], 1: []}
    for row in eligible:
        by_gold[LABEL_MAP[int(row["label_state_admin"])]].append(row)
    for values in by_gold.values():
        values.sort(key=lambda row: (int(row["start_time"]), int(row["id"])))
    raw_counts = (len(by_gold[0]), len(by_gold[1]))
    if raw_counts != spec.expected_raw:
        raise RuntimeError(
            f"{spec.name} ham sayim degisti: actual={raw_counts}, "
            f"expected={spec.expected_raw}"
        )
    selected = (
        evenly_spaced(by_gold[0], spec.target_per_class)
        + evenly_spaced(by_gold[1], spec.target_per_class)
    )
    selected.sort(key=lambda row: (int(row["start_time"]), int(row["id"])))
    return selected


def build_manifest(rows: list[dict[str, Any]], spec: SplitSpec) -> dict[str, Any]:
    items = []
    for row in rows:
        source_id = int(row["id"])
        items.append({
            "source_id": source_id,
            "file": f"clips/rise_{source_id}.mp4",
            "gold_smoke": LABEL_MAP[int(row["label_state_admin"])],
            "label_state_admin": int(row["label_state_admin"]),
            "label_provenance": "researcher_strong",
            "camera_id": int(row["camera_id"]),
            "view_id": int(row["view_id"]),
            "date": spec.date,
            "start_time": int(row["start_time"]),
            "source_file_name": str(row["file_name"]),
            "source_url_320": source_url_320(row),
        })
    selection = {
        "camera_id": spec.camera_id,
        "view_id": spec.view_id,
        "file_date_prefix": spec.prefix,
        "accepted_admin_labels": {"23": "smoke", "16": "no_smoke"},
        "raw_counts": {"no_smoke": spec.expected_raw[0], "smoke": spec.expected_raw[1]},
        "sampling": (
            "per class, sort by (start_time,id); take all when target equals class "
            "size, otherwise round(i*(N-1)/(target-1)) for i=0..target-1"
        ),
        "target_per_class": spec.target_per_class,
        "selection_frozen_before_inference": True,
    }
    manifest = {
        "dataset": "Project RISE / Deep Smoke Machine",
        "split": spec.name,
        "role": spec.role,
        "source_repo": SOURCE_REPO,
        "source_commit": SOURCE_COMMIT,
        "metadata_file": str(METADATA_PATH.relative_to(ROOT)).replace("\\", "/"),
        "metadata_sha256": METADATA_SHA256,
        "license": "CC0-1.0 (dataset); BSD-3-Clause (code)",
        "selection": selection,
        "counts": {
            "smoke": spec.target_per_class,
            "no_smoke": spec.target_per_class,
            "total": 2 * spec.target_per_class,
        },
        "label_blind_storage": True,
        "items": items,
    }
    canonical = json.dumps(items, sort_keys=True, ensure_ascii=False).encode("utf-8")
    manifest["selection_sha256"] = hashlib.sha256(canonical).hexdigest()
    return manifest


def download_one(split_dir: Path, item: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    target = split_dir / item["file"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.stat().st_size == 0:
        temporary = target.with_suffix(target.suffix + ".part")
        if temporary.exists():
            temporary.unlink()
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                if temporary.exists():
                    temporary.unlink()
                request = urllib.request.Request(
                    item["source_url_320"],
                    headers={"User-Agent": "DilAjanlariTeknofest-benchmark/2.0"},
                )
                with urllib.request.urlopen(request, timeout=timeout) as response, temporary.open("wb") as output:
                    shutil.copyfileobj(response, output)
                os.replace(temporary, target)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(2 ** attempt)
        if last_error is not None:
            raise last_error
    if target.stat().st_size < 1024:
        raise RuntimeError(f"Indirilen video gecersiz derecede kucuk: {target}")
    result = dict(item)
    result["bytes"] = target.stat().st_size
    result["sha256"] = sha256_file(target)
    return result


def probe_video(split_dir: Path, item: dict[str, Any]) -> dict[str, Any]:
    target = split_dir / item["file"]
    process = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "stream=codec_type,codec_name,width,height,nb_frames,r_frame_rate,duration:format=duration",
            "-of", "json", str(target),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(process.stdout)
    video_streams = [s for s in payload.get("streams", []) if s.get("codec_type") == "video"]
    audio_streams = [s for s in payload.get("streams", []) if s.get("codec_type") == "audio"]
    if len(video_streams) != 1 or audio_streams:
        raise RuntimeError(
            f"Beklenmeyen medya akisi {target}: video={len(video_streams)}, audio={len(audio_streams)}"
        )
    stream = video_streams[0]
    duration = float(payload.get("format", {}).get("duration") or stream.get("duration") or 0)
    if (int(stream.get("width") or 0), int(stream.get("height") or 0)) != (320, 320):
        raise RuntimeError(f"Beklenmeyen cozunurluk {target}: {stream}")
    if int(stream.get("nb_frames") or 0) != 36 or not (2.9 <= duration <= 3.1):
        raise RuntimeError(f"Beklenmeyen sure/kare {target}: {stream}, duration={duration}")
    result = dict(item)
    result["media"] = {
        "codec": stream.get("codec_name"),
        "width": 320,
        "height": 320,
        "fps": stream.get("r_frame_rate"),
        "frames": 36,
        "duration_s": duration,
        "audio_streams": 0,
    }
    return result


def prepare(spec: SplitSpec, metadata: list[dict[str, Any]], workers: int,
            manifest_only: bool) -> None:
    selected = select_rows(metadata, spec)
    manifest = build_manifest(selected, spec)
    split_dir = OUT_ROOT / spec.name
    manifest_path = split_dir / "_metadata" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    count = int(manifest["counts"]["total"])
    print(
        f"{spec.name}: secim kilitlendi ({spec.target_per_class}+{spec.target_per_class}); "
        f"sha256={manifest['selection_sha256']}",
        flush=True,
    )
    if manifest_only:
        return

    completed: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(download_one, split_dir, item): item
            for item in manifest["items"]
        }
        for index, future in enumerate(as_completed(futures), start=1):
            item = future.result()
            completed[int(item["source_id"])] = item
            print(f"{spec.name} [{index:02d}/{count:02d}] rise_{item['source_id']}.mp4", flush=True)
    manifest["items"] = [completed[int(item["source_id"])] for item in manifest["items"]]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        manifest["items"] = list(
            pool.map(lambda item: probe_video(split_dir, item), manifest["items"])
        )
    total_bytes = sum(int(item["bytes"]) for item in manifest["items"])
    manifest["download"] = {
        "resolution": "320x320",
        "completed": len(completed),
        "total_bytes": total_bytes,
        "media_validation": (
            f"{count}/{count}: one video stream, 320x320, 36 frames, 3.0 s, no audio"
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{spec.name}: tamam {count}/{count}, {total_bytes / 1024 / 1024:.1f} MiB", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("all", *SPECS), default="all")
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    metadata = load_metadata()
    names = list(SPECS) if args.split == "all" else [args.split]
    for name in names:
        prepare(SPECS[name], metadata, args.workers, args.manifest_only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
