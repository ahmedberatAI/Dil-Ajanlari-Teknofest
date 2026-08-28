#!/usr/bin/env python
"""iSafety v2 satırlarına eşleştirilmiş doğrudan `vlm` üçüncü kolu."""
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
if str(ROOT) not in os.sys.path: os.sys.path.insert(0, str(ROOT))

from benchmark.isafety_uzak_v2 import (  # noqa: E402
    DATA, DIRECT_PROMPT, LETTERS, VIDEO_SYSTEM, _contract, _letter, _metrics, _options,
)
from benchmark.stats_utils import mcnemar_exact_p  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402

RESULTS = ROOT / "benchmark" / "results"


def _probe(row: dict) -> dict:
    path = DATA / "videos" / row["column"] / row["video_name"]
    raw = error = None; t0 = time.perf_counter()
    try:
        client = VLMClient().gorev("algi")
        session = client.video_oturumu(str(path), system=VIDEO_SYSTEM,
                                       giris_metni="Watch this workplace video chronologically.")
        raw = session.sor(DIRECT_PROMPT.format(options=_options(row["choices"])),
                          guided_choice=LETTERS[:len(row["choices"])],
                          temperature=0.0, max_tokens=4, hatirla=False)
        error = session.hata
    except Exception as exc: error = f"{type(exc).__name__}: {exc}"
    pred = _letter(raw, error, len(row["choices"]))
    return {"column": row["column"], "video_name": row["video_name"],
            "gt_letter": row["gt_letter"], "video_sha256": row["video_sha256"],
            "vlm_letter": pred, "vlm_raw": raw, "vlm_error": error,
            "vlm_correct": pred == row["gt_letter"],
            "latency_s": round(time.perf_counter() - t0, 3)}


def _paired(rows, a_key, b_key):
    fixed = sum((not r[a_key]) and r[b_key] for r in rows)
    broke = sum(r[a_key] and (not r[b_key]) for r in rows)
    return {"fixed": fixed, "broke": broke,
            "mcnemar_exact_p": mcnemar_exact_p(fixed, broke),
            "diff": (sum(r[b_key] for r in rows) - sum(r[a_key] for r in rows)) / len(rows)}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--base", required=True)
    ap.add_argument("--workers", type=int, default=4); args=ap.parse_args(); contract=_contract()
    base_path=Path(args.base); base=json.loads(base_path.read_text(encoding="utf-8")); base_rows=base["rows"]
    key=hashlib.sha256((hashlib.sha256(base_path.read_bytes()).hexdigest()+"vlm-direct-v3").encode()).hexdigest()[:12]
    journal=RESULTS/f".isafety_vlm_v3_{key}.jsonl"; done={}
    if journal.exists():
        for line in journal.read_text(encoding="utf-8").splitlines():
            try:r=json.loads(line)
            except json.JSONDecodeError:continue
            done[f"{r['column']}/{r['video_name']}"]=r
    pending=[r for r in base_rows if f"{r['column']}/{r['video_name']}" not in done]
    print(f"iSafety VLM v3: n={len(base_rows)}, kalan={len(pending)}")
    with ThreadPoolExecutor(max_workers=max(1,args.workers)) as pool:
        fs={pool.submit(_probe,r):r for r in pending}
        for i,f in enumerate(as_completed(fs),1):
            r=f.result();done[f"{r['column']}/{r['video_name']}"]=r
            with journal.open("a",encoding="utf-8") as h:
                h.write(json.dumps(r,ensure_ascii=False)+"\n");h.flush();os.fsync(h.fileno())
            print(f"[{i}/{len(pending)}] {r['column']}/{r['video_name']}: gt={r['gt_letter']} vlm={r['vlm_letter']}")
    rows=[]
    for br in base_rows:
        vr=done[f"{br['column']}/{br['video_name']}"]
        rows.append({**br,**vr})
    def block(rs):
        oracle=sum(r["direct_correct"] or r["cascade_correct"] or r["vlm_correct"] for r in rs)
        return {"vlm":_metrics(rs,"vlm"),
                "direct_vs_vlm":_paired(rs,"direct_correct","vlm_correct"),
                "cascade_vs_vlm":_paired(rs,"cascade_correct","vlm_correct"),
                "three_arm_oracle": {"correct":oracle,"n":len(rs),"rate":oracle/len(rs)}}
    out={"benchmark":"iSafety paired direct-vlm arm v3",
         "created_at":datetime.now().astimezone().isoformat(),"development_only":True,
         "base_result":str(base_path),"base_sha256":hashlib.sha256(base_path.read_bytes()).hexdigest(),
         "inference":{"special_api_only":True,"contract":contract,"role":"algi","model":"vlm"},
         "metrics":{"all":block(rows),**{c:block([r for r in rows if r["column"]==c]) for c in ("hazard","normal")}},
         "rows":rows}
    target=RESULTS/f"isafety_vlm_v3_{datetime.now():%Y%m%d_%H%M%S}.json"
    target.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(out["metrics"],ensure_ascii=False,indent=2));print(target)


if __name__=="__main__":main()
