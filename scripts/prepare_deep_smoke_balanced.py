#!/usr/bin/env python3
"""Project RISE'tan sabit-sahne, dengeli endustriyel duman benchmarki hazirla.

Secim sonucu model ciktisina bakmaz. Resmi metadata icindeki tek bir kamera,
tek bir gorus ve tek bir gunun tum guclu arastirmaci etiketleri kullanilir:

* camera_id=0, view_id=0
* dosya tarihi=2019-02-02
* label_state_admin=23 -> duman var
* label_state_admin=16 -> duman yok

Bu sabit filtre resmi snapshot'ta 28 pozitif + 28 negatif verir. Dosyalar etiket
sizmamasi icin ayni ``clips`` dizinine, yalniz kayit kimligiyle indirilir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "external" / "deep_smoke_machine_e796bf3"
METADATA_PATH = SOURCE_DIR / "metadata_02242020.json"
OUT_DIR = ROOT / "data" / "eval_deep_smoke_balanced_v1"
CLIPS_DIR = OUT_DIR / "clips"
META_DIR = OUT_DIR / "_metadata"
MANIFEST_PATH = META_DIR / "manifest.json"

SOURCE_REPO = "https://github.com/CMU-CREATE-Lab/deep-smoke-machine"
SOURCE_COMMIT = "e796bf36988226b8bc657872bdc83c6cbad791cd"
METADATA_SHA256 = "cc85ad6db07557ae4afacc4f12f443b6e68ae0d88e30869fcf031f4c7dc7ee18"
CAMERA_ID = 0
VIEW_ID = 0
FILE_DATE_PREFIX = "0-0-2019-02-02-"
LABEL_MAP = {23: 1, 16: 0}
EXPECTED_PER_CLASS = 28


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source_url_320(row: dict[str, Any]) -> str:
    root = str(row["url_root"]).replace("/180/", "/320/")
    part = str(row["url_part"]).replace("-180-180-", "-320-320-")
    return root + part


def select_rows() -> list[dict[str, Any]]:
    if not METADATA_PATH.is_file():
        raise FileNotFoundError(f"Resmi metadata bulunamadi: {METADATA_PATH}")
    actual = sha256_file(METADATA_PATH)
    if actual != METADATA_SHA256:
        raise RuntimeError(
            "Metadata SHA256 uyusmuyor; secim sessizce degistirilmeyecek: "
            f"actual={actual}, expected={METADATA_SHA256}"
        )
    rows = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    selected = [
        row
        for row in rows
        if int(row.get("camera_id", -1)) == CAMERA_ID
        and int(row.get("view_id", -1)) == VIEW_ID
        and str(row.get("file_name", "")).startswith(FILE_DATE_PREFIX)
        and int(row.get("label_state_admin", -999)) in LABEL_MAP
    ]
    selected.sort(key=lambda row: (int(row["start_time"]), int(row["id"])))
    counts = {
        label: sum(LABEL_MAP[int(row["label_state_admin"])] == label for row in selected)
        for label in (0, 1)
    }
    if counts != {0: EXPECTED_PER_CLASS, 1: EXPECTED_PER_CLASS}:
        raise RuntimeError(
            "Sabit secim filtresi beklenen 28+28 dengeyi vermedi; veri/surum "
            f"degismis olabilir: {counts}"
        )
    return selected


def build_manifest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    for row in rows:
        clip_id = int(row["id"])
        items.append(
            {
                "source_id": clip_id,
                "file": f"clips/rise_{clip_id}.mp4",
                "gold_smoke": LABEL_MAP[int(row["label_state_admin"])],
                "label_state_admin": int(row["label_state_admin"]),
                "label_provenance": "researcher_strong",
                "camera_id": int(row["camera_id"]),
                "view_id": int(row["view_id"]),
                "date": "2019-02-02",
                "start_time": int(row["start_time"]),
                "source_file_name": str(row["file_name"]),
                "source_url_320": source_url_320(row),
            }
        )
    return {
        "dataset": "Project RISE / Deep Smoke Machine",
        "purpose": "balanced external industrial-smoke evaluation",
        "source_repo": SOURCE_REPO,
        "source_commit": SOURCE_COMMIT,
        "metadata_file": str(METADATA_PATH.relative_to(ROOT)).replace("\\", "/"),
        "metadata_sha256": METADATA_SHA256,
        "license": "CC0-1.0 (dataset); BSD-3-Clause (code)",
        "selection": {
            "camera_id": CAMERA_ID,
            "view_id": VIEW_ID,
            "file_date_prefix": FILE_DATE_PREFIX,
            "accepted_admin_labels": {"23": "smoke", "16": "no_smoke"},
            "sampling": "none; all matching strong researcher labels",
        },
        "counts": {"smoke": EXPECTED_PER_CLASS, "no_smoke": EXPECTED_PER_CLASS, "total": 56},
        "label_blind_storage": True,
        "items": items,
    }


def download_one(item: dict[str, Any], timeout: int = 90) -> dict[str, Any]:
    target = OUT_DIR / item["file"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.stat().st_size == 0:
        tmp = target.with_suffix(target.suffix + ".part")
        if tmp.exists():
            tmp.unlink()
        request = urllib.request.Request(
            item["source_url_320"],
            headers={"User-Agent": "DilAjanlariTeknofest-benchmark/1.0"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response, tmp.open("wb") as fh:
            shutil.copyfileobj(response, fh)
        os.replace(tmp, target)
    if target.stat().st_size < 1024:
        raise RuntimeError(f"Indirilen video gecersiz derecede kucuk: {target}")
    out = dict(item)
    out["bytes"] = target.stat().st_size
    out["sha256"] = sha256_file(target)
    return out


def probe_video(item: dict[str, Any]) -> dict[str, Any]:
    target = OUT_DIR / item["file"]
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "stream=codec_type,codec_name,width,height,nb_frames,r_frame_rate,duration:format=duration",
            "-of", "json", str(target),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
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
    out = dict(item)
    out["media"] = {
        "codec": stream.get("codec_name"),
        "width": 320,
        "height": 320,
        "fps": stream.get("r_frame_rate"),
        "frames": 36,
        "duration_s": duration,
        "audio_streams": 0,
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    selected = select_rows()
    manifest = build_manifest(selected)
    META_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Secim kilitlendi: {MANIFEST_PATH.relative_to(ROOT)} (28 duman + 28 dumansiz)")
    if args.manifest_only:
        return 0

    completed: dict[int, dict[str, Any]] = {}
    workers = max(1, args.workers)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(download_one, item): item for item in manifest["items"]}
        for index, future in enumerate(as_completed(futures), start=1):
            item = future.result()
            completed[int(item["source_id"])] = item
            print(f"[{index:02d}/56] rise_{item['source_id']}.mp4", flush=True)

    manifest["items"] = [completed[int(item["source_id"])] for item in manifest["items"]]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        manifest["items"] = list(pool.map(probe_video, manifest["items"]))
    manifest["download"] = {
        "resolution": "320x320",
        "completed": len(completed),
        "total_bytes": sum(int(item["bytes"]) for item in manifest["items"]),
        "media_validation": "56/56: H.264 video, 320x320, 36 frames, 3.0 s, no audio",
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Tamam: 56/56, {manifest['download']['total_bytes'] / 1024 / 1024:.1f} MiB, "
        f"manifest={MANIFEST_PATH.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
