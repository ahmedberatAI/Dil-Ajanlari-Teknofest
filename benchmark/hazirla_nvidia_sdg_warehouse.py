#!/usr/bin/env python
"""NVIDIA SDG-Warehouse'tan deterministik, kucuk bir benchmark dilimi hazirla.

Secim model ciktisina bakmaz: sabit depo revizyonunda her senaryonun sabit
bir baslangic konumundan N WebDataset run'i ve bu run'lardaki TUM RGB kameralar
alinir. Ayni run'in coklu
goruntuleri manifestte ayni ``run_id`` ile kalir; puanlayici run'lari bagimsiz
ornek, kameralari ise gorus-tekrari olarak ele alabilsin.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVISION = "d5b88d3abcf659f304a107f4336b71b4e2159133"
REPO = "nvidia/PhysicalAI-WorldModel-Synthetic-Warehouse-Operations-Scenes"
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}"

SCENARIOS = {
    "nearmiss": {
        "shard": "rgb/forklift_human_nearmiss/nearmiss-rgb-00000.tar",
        "category": "RoadAccidents",
        "rule": "Forklift ile insan ayni yol uzaminda ramak-kala/dogrudan temas olayi",
        "unsafe": True,
    },
    "fire": {
        "shard": "rgb/warehouse_fire/fire-rgb-00000.tar",
        "category": "Fire",
        "rule": "Depoda gorunur alev ve/veya dumanla yangin; calisanlar cikisa tahliye olur",
        "unsafe": True,
    },
    "forklift_collision": {
        "shard": "rgb/forklift_shelf_collision/forklift_collision-rgb-00000.tar",
        "category": "RoadAccidents",
        "rule": "Forklift depolama rafina carpar; raf/devrilme ve dokuntu dinamigi olusur",
        "unsafe": True,
    },
    "box_pickup": {
        "shard": "rgb/warehouse_box_pickup/box_pickup-rgb-00000.tar",
        "category": "Normal",
        "rule": "Calisan kutuyu rutin bicimde alir ve depoda tasir; guvenlik olayi yoktur",
        "unsafe": False,
    },
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _run_id(name: str) -> str:
    for suffix in (".meta.json", ".metadata.txt"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    marker = "."
    return name.split(marker, 1)[0]


def indir(scenario: str, run_limit: int, run_offset: int, out_root: Path) -> list[dict]:
    spec = SCENARIOS[scenario]
    url = f"{BASE}/{spec['shard']}"
    target = out_root / spec["category"]
    target.mkdir(parents=True, exist_ok=True)
    secilen: list[str] = []
    gorulen: list[str] = []
    tamamlanan: set[str] = set()
    rows: list[dict] = []
    meta_by_run: dict[str, dict] = {}

    req = urllib.request.Request(url, headers={"User-Agent": "DilAjanlari-benchmark/1.0"})
    print(f"[{scenario}] akis aciliyor: {url}", flush=True)
    with urllib.request.urlopen(req, timeout=120) as response:
        with tarfile.open(fileobj=response, mode="r|*") as tar:
            for member in tar:
                name = Path(member.name).name
                run_id = _run_id(name)
                if run_id not in gorulen:
                    gorulen.append(run_id)
                if gorulen.index(run_id) < run_offset:
                    continue
                if run_id not in secilen:
                    if len(secilen) >= run_limit:
                        continue
                    secilen.append(run_id)
                    print(f"[{scenario}] run {len(secilen)}/{run_limit} "
                          f"(kaynak sira {run_offset + len(secilen)}): {run_id}", flush=True)
                if run_id not in secilen:
                    continue
                src = tar.extractfile(member)
                if src is None:
                    continue
                if name.endswith(".rgb.mp4"):
                    camera = name[len(run_id) + 1 : -len(".rgb.mp4")]
                    filename = f"{scenario}__{run_id}__{camera}.mp4"
                    dest = target / filename
                    if not dest.exists() or dest.stat().st_size != member.size:
                        part = dest.with_suffix(dest.suffix + ".part")
                        with part.open("wb") as f:
                            shutil.copyfileobj(src, f, length=1024 * 1024)
                        os.replace(part, dest)
                    rows.append({
                        "path": dest.relative_to(ROOT).as_posix(),
                        "scenario": scenario,
                        "category": spec["category"],
                        "unsafe": spec["unsafe"],
                        "rule": spec["rule"],
                        "run_id": run_id,
                        "camera": camera,
                        "bytes": dest.stat().st_size,
                        "sha256": _sha256(dest),
                    })
                elif name.endswith(".meta.json"):
                    try:
                        meta_by_run[run_id] = json.load(src)
                    except Exception:
                        meta_by_run[run_id] = {}
                    tamamlanan.add(run_id)
                    if len(tamamlanan) >= run_limit:
                        break

    for row in rows:
        meta = meta_by_run.get(row["run_id"], {})
        row["seed"] = meta.get("seed")
    if len(tamamlanan) != run_limit:
        raise RuntimeError(f"{scenario}: beklenen {run_limit} run, tamamlanan {len(tamamlanan)}")
    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--runs", type=int, default=5, help="senaryo basina run (varsayilan 5)")
    p.add_argument("--start-run", type=int, default=0,
                   help="ilk kac tar-run'inin atlanacagi (varsayilan 0)")
    p.add_argument("--out", default="data/eval_nvidia_warehouse")
    args = p.parse_args()
    if args.runs < 1:
        raise SystemExit("--runs en az 1 olmali")
    if args.start_run < 0:
        raise SystemExit("--start-run negatif olamaz")
    out_root = (ROOT / args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for scenario in SCENARIOS:
        rows.extend(indir(scenario, args.runs, args.start_run, out_root))
    manifest = {
        "source_repo": REPO,
        "source_revision": REVISION,
        "license": "OpenMDW-1.1",
        "selection": ("her senaryonun tar sirasinda sabit offset'ten baslayan N run'i; "
                      "run icindeki tum RGB kameralar"),
        "run_limit_per_scenario": args.runs,
        "run_offset_per_scenario": args.start_run,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "rows": rows,
    }
    manifest_path = out_root / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Manifest: {manifest_path}  klip={len(rows)}  run={len({r['run_id'] for r in rows})}")


if __name__ == "__main__":
    main()
