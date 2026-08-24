#!/usr/bin/env python
"""D42 — TEK CAGRI BELIRLENIMLILIK: ayni klip, ayni istek, n=5 tekrar (T=0, seed=1234).

Dokumantasyon: 250 token -> 13 farkli cikti, 900 token -> 20 farkli. K1 ciktisi
~400 token; RISK degeri operatorun gordugu KARARDIR, oynamamalidir.
"""
import base64, hashlib, json, os, sys, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dilajan.config import settings
from dilajan.video import servis_videosu
from dilajan.prompts import SYSTEM_PERSONA
from openai import OpenAI

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEVERITY = ["Düşük", "Orta", "Yüksek", "Kritik"]
K1 = {"type": "object",
      "properties": {"summary": {"type": "string"},
                     "events": {"type": "array", "items": {"type": "object",
                         "properties": {"time": {"type": "string", "pattern": "^[0-9]{2}:[0-9]{2}$"},
                                        "event": {"type": "string"}},
                         "required": ["time", "event"], "additionalProperties": False}},
                     "risk": {"type": "string", "enum": SEVERITY},
                     "actions": {"type": "array", "items": {"type": "string"}}},
      "required": ["summary", "events", "risk", "actions"], "additionalProperties": False}
RF = {"type": "json_schema", "json_schema": {"name": "k1", "schema": K1, "strict": True}}
GOREV = ("Bu bir güvenlik kamerası kaydıdır. Kaydı baştan sona izle ve operatöre tek seferde "
         "eksiksiz bir durum raporu üret: summary, events(time MM:SS, event), "
         "risk (Düşük/Orta/Yüksek/Kritik), actions. Yalnızca gördüğüne dayan.")
istemci = OpenAI(base_url=settings.base_url, api_key=settings.etkin_api_key, timeout=900)

KLIPLER = [("holdout/Fighting023", "data/eval_holdout/Fighting/Fighting023_x264.mp4"),
           ("isg/Guvenli_tasima", "data/eval_defense/Normal/Safe_Carrying/7_tr18.mp4")]

sonuc = {"kunye": {"tarih": datetime.now().isoformat(timespec="seconds"), "T": 0.0,
                   "seed": 1234, "n": 5, "model": "llm-large", "max_tokens": 1200},
         "satirlar": []}
for etiket, rel in KLIPLER:
    b = servis_videosu(os.path.join(KOK, rel), max_side=768, crf=28)
    url = "data:video/mp4;base64," + base64.b64encode(b).decode()
    print("\n=== " + etiket)
    hs, riskler, nev = [], [], []
    for i in range(5):
        m = [{"role": "system", "content": SYSTEM_PERSONA},
             {"role": "user", "content": [{"type": "video_url", "video_url": {"url": url}},
                                          {"type": "text", "text": GOREV}]}]
        r = istemci.chat.completions.create(model="llm-large", messages=m, temperature=0.0,
                                           max_tokens=1200, seed=1234, response_format=RF,
                                           extra_body={"chat_template_kwargs": {"enable_thinking": False}})
        t = r.choices[0].message.content or ""
        v = json.loads(t)
        h = hashlib.md5(t.encode()).hexdigest()[:8]
        hs.append(h); riskler.append(v["risk"]); nev.append(len(v["events"]))
        print("  #%d md5=%s risk=%-8s n_ev=%d tok=%d" % (i, h, v["risk"], len(v["events"]),
                                                          r.usage.completion_tokens))
        sonuc["satirlar"].append({"klip": etiket, "tekrar": i, "md5": h, "risk": v["risk"],
                                  "n_event": len(v["events"]), "cikti": v})
    print("  -> benzersiz cikti: %d/5 | benzersiz risk: %s | olay sayilari: %s"
          % (len(set(hs)), sorted(set(riskler)), nev))

p = os.path.join(KOK, "benchmark", "results",
                 "tekcagri_kararlilik_%s.json" % datetime.now().strftime("%Y%m%d_%H%M%S"))
json.dump(sonuc, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\nyazildi: " + p)
