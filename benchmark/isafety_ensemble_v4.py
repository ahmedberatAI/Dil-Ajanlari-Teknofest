#!/usr/bin/env python
"""iSafety v4: üç sabit kol anlaşmazlığında llm-fast seçici hakem."""
from __future__ import annotations
import argparse,hashlib,json,os,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:os.sys.path.insert(0,str(ROOT))
from benchmark.isafety_uzak_v2 import CLASSIFY_SYSTEM,_contract,_metrics,_options  # noqa:E402
from benchmark.isafety_vlm_arm_v3 import _paired  # noqa:E402
from dilajan.llm_client import VLMClient  # noqa:E402
RESULTS=ROOT/"benchmark"/"results"
SYSTEM=("You arbitrate between candidate answer letters using only the neutral forensic "
        "observation and option texts. Do not vote by majority and do not invent video facts. "
        "Output only one of the supplied candidate letters.")
PROMPT=("FORENSIC OBSERVATION:\n{description}\n\nALL OPTIONS:\n{options}\n\n"
        "Independent fixed-model candidates: {candidates}. Select the candidate most directly "
        "supported by the observation. Output only that candidate letter.")

def _candidates(r):
 vals=[]
 for k in ("direct_letter","vlm_letter","cascade_letter"):
  v=r.get(k)
  if v and v not in vals:vals.append(v)
 return tuple(vals)

def _probe(r):
 cand=_candidates(r);raw=err=None;t0=time.perf_counter()
 if not cand:return {"column":r["column"],"video_name":r["video_name"],"ensemble_letter":None,"ensemble_error":"aday yok"}
 if len(cand)==1:raw=cand[0]
 else:
  try:
   judge=VLMClient().gorev("yapi")
   raw=judge.chat([{"role":"system","content":SYSTEM},{"role":"user","content":PROMPT.format(description=r.get("description") or "(observation unavailable)",options=_options(r["choices"]),candidates=", ".join(cand))}],temperature=0,max_tokens=4,guided_choice=cand)
  except Exception as ex:err=f"{type(ex).__name__}: {ex}"
 pred=(raw or "").strip().upper() if not err else None
 if pred not in cand:err=err or f"aday dışı çıktı: {raw!r}";pred=None
 return {"column":r["column"],"video_name":r["video_name"],"ensemble_letter":pred,
         "ensemble_raw":raw,"ensemble_error":err,"candidates":list(cand),
         "ensemble_correct":pred==r["gt_letter"],"latency_s":round(time.perf_counter()-t0,3)}

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--base",required=True);ap.add_argument("--workers",type=int,default=4);a=ap.parse_args();contract=_contract()
 bp=Path(a.base);base=json.loads(bp.read_text(encoding="utf-8"));br=base["rows"]
 key=hashlib.sha256((hashlib.sha256(bp.read_bytes()).hexdigest()+SYSTEM+PROMPT).encode()).hexdigest()[:12]
 journal=RESULTS/f".isafety_ensemble_v4_{key}.jsonl";done={}
 if journal.exists():
  for line in journal.read_text(encoding="utf-8").splitlines():
   try:r=json.loads(line)
   except json.JSONDecodeError:continue
   done[f"{r['column']}/{r['video_name']}"]=r
 pending=[r for r in br if f"{r['column']}/{r['video_name']}" not in done]
 print(f"iSafety ensemble v4: n={len(br)}, kalan={len(pending)}")
 with ThreadPoolExecutor(max_workers=max(1,a.workers)) as pool:
  fs={pool.submit(_probe,r):r for r in pending}
  for i,f in enumerate(as_completed(fs),1):
   r=f.result();done[f"{r['column']}/{r['video_name']}"]=r
   with journal.open("a",encoding="utf-8") as h:h.write(json.dumps(r,ensure_ascii=False)+"\n");h.flush();os.fsync(h.fileno())
   print(f"[{i}/{len(pending)}] {r['column']}/{r['video_name']}: {r.get('candidates')} => {r['ensemble_letter']}")
 rows=[]
 for r in br:rows.append({**r,**done[f"{r['column']}/{r['video_name']}"]})
 def block(xs):return {"ensemble":_metrics(xs,"ensemble"),"direct_vs_ensemble":_paired(xs,"direct_correct","ensemble_correct")}
 out={"benchmark":"iSafety selective fixed-model ensemble v4","created_at":datetime.now().astimezone().isoformat(),"development_only":True,
      "base_result":str(bp),"base_sha256":hashlib.sha256(bp.read_bytes()).hexdigest(),
      "inference":{"special_api_only":True,"contract":contract,"judge_role":"yapi","judge_model":"llm-fast","system":SYSTEM,"prompt":PROMPT},
      "metrics":{"all":block(rows),**{c:block([r for r in rows if r["column"]==c]) for c in ("hazard","normal")}},"rows":rows}
 target=RESULTS/f"isafety_ensemble_v4_{datetime.now():%Y%m%d_%H%M%S}.json";target.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(out["metrics"],ensure_ascii=False,indent=2));print(target)
if __name__=="__main__":main()
