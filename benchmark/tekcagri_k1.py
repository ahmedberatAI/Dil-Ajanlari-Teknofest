#!/usr/bin/env python
"""D42 — TEK CAGRI ile K1 sozlesmesi (video -> summary/events/risk/actions).

KURULUM (SONUCLARA BAKILMADAN ilan edildi):
  klipler   : 12 (asagida KLIPLER listesinde sabit)
  video     : servis_videosu(max_side=768, crf=28)
  ornekleme : T=0.0, seed=1234, max_tokens=1200, thinking KAPALI
  kollar    : L-strict  (llm-large + response_format json_schema strict:True)
              F-strict  (llm-fast  + ayni)
              L-serbest (llm-large + response_format YOK, yalniz promptta "JSON uret")
  denetim   : TAM 4 anahtar / events[].time MM:SS / risk Severity kumesinde /
              actions bos mu / JSON ayristirma hatasi
"""
import base64
import json
import os
import re
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dilajan.config import settings
from dilajan.video import servis_videosu
from dilajan.prompts import SYSTEM_PERSONA
from openai import OpenAI

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KLIPLER = [
    ("holdout/Explosion001",   True,  "data/eval_holdout/Explosion/Explosion001_x264.mp4"),
    ("holdout/Fighting023",    True,  "data/eval_holdout/Fighting/Fighting023_x264.mp4"),
    ("holdout/RoadAcc021",     True,  "data/eval_holdout/RoadAccidents/RoadAccidents021_x264.mp4"),
    ("holdout/Shooting001",    True,  "data/eval_holdout/Shooting/Shooting001_x264.mp4"),
    ("holdout/Normal_6te10",   False, "data/eval_holdout/Normal/6_te10.mp4"),
    ("holdout/Normal_939",     False, "data/eval_holdout/Normal/Normal_Videos_939_x264.mp4"),
    ("isg/Forklift_asiri_yuk", True,  "data/eval_defense/Anomali/Carrying_Overload_with_Forklift/3_tr5.mp4"),
    ("isg/Yaya_yolu_ihlali",   True,  "data/eval_defense/Anomali/Safe_Walkway_Violation/0_tr11.mp4"),
    ("isg/Pano_kapagi_acik",   True,  "data/eval_defense/Anomali/Opened_Panel_Cover/2_tr126.mp4"),
    ("isg/Guvenli_tasima",     False, "data/eval_defense/Normal/Safe_Carrying/7_tr18.mp4"),
    ("isg/Guvenli_yaya_yolu",  False, "data/eval_defense/Normal/Safe_Walkway/4_tr47.mp4"),
    ("isg/Pano_kapagi_kapali", False, "data/eval_defense/Normal/Closed_Panel_Cover/6_tr1.mp4"),
]

# dilajan/schema.py Severity kumesi ile BIREBIR ayni olmali
SEVERITY = ["Düşük", "Orta", "Yüksek", "Kritik"]

K1_SEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "events": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "time": {"type": "string", "pattern": "^[0-9]{2}:[0-9]{2}$"},
                "event": {"type": "string"},
            },
            "required": ["time", "event"],
            "additionalProperties": False,
        }},
        "risk": {"type": "string", "enum": SEVERITY},
        "actions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "events", "risk", "actions"],
    "additionalProperties": False,
}
RF = {"type": "json_schema",
      "json_schema": {"name": "k1_sartname", "schema": K1_SEMA, "strict": True}}

GOREV = (
    "Bu bir güvenlik kamerası kaydıdır. Kaydı baştan sona izle ve operatöre tek seferde "
    "eksiksiz bir durum raporu üret.\n"
    "Rapor şu dört parçadan oluşur:\n"
    "- summary: kayıtta olup biteni anlatan kısa Türkçe özet.\n"
    "- events: dikkat çekici her olay için zaman damgası (MM:SS, kaydın başından itibaren) "
    "ve olayın Türkçe kısa açıklaması. Dikkat çekici hiçbir şey yoksa liste boş kalır.\n"
    "- risk: kaydın genel risk seviyesi; yalnızca şu dördünden biri: Düşük, Orta, Yüksek, Kritik.\n"
    "- actions: operatörün şimdi yapabileceği somut, uygulanabilir adımlar (Türkçe, emir kipinde).\n"
    "Yalnızca görüntüde gerçekten gördüğüne dayan; görmediğin bir olayı yazma."
)
SERBEST_EK = (
    "\nYanıtını YALNIZCA tek bir JSON nesnesi olarak ver; şu dört anahtarı içersin: "
    "summary, events, risk, actions. events öğeleri {\"time\": \"MM:SS\", \"event\": \"...\"} "
    "biçiminde olsun. JSON dışında hiçbir metin yazma."
)

istemci = OpenAI(base_url=settings.base_url, api_key=settings.etkin_api_key, timeout=1800)

_JSON_RE = re.compile(r"\{.*\}", re.S)
MMSS = re.compile(r"^\d{2}:\d{2}$")
GENEL_AKSIYON = ("dikkatli ol", "güvenlik önlemlerini", "gerekli önlemleri",
                 "önlem al", "takip ed", "izlemeye devam")


def ayristir(ham):
    """(veri, yontem) -> yontem: 'dogrudan' | 'kurtarma' | None"""
    if not ham:
        return None, None
    try:
        return json.loads(ham), "dogrudan"
    except Exception:
        pass
    t = ham.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"```\s*$", "", t).strip()
        try:
            return json.loads(t), "kurtarma"
        except Exception:
            pass
    m = _JSON_RE.search(ham)
    if m:
        try:
            return json.loads(m.group(0)), "kurtarma"
        except Exception:
            pass
    return None, None


def denetle(veri):
    d = {}
    if veri is None or not isinstance(veri, dict):
        return {"ayristi": False}
    d["ayristi"] = True
    anahtarlar = set(veri.keys())
    hedef = {"summary", "events", "risk", "actions"}
    d["anahtarlar"] = sorted(anahtarlar)
    d["tam4"] = anahtarlar == hedef
    d["fazla"] = sorted(anahtarlar - hedef)
    d["eksik"] = sorted(hedef - anahtarlar)
    ev = veri.get("events")
    d["events_liste"] = isinstance(ev, list)
    d["n_event"] = len(ev) if isinstance(ev, list) else None
    if isinstance(ev, list):
        d["event_alan_tam"] = all(isinstance(e, dict) and set(e.keys()) == {"time", "event"} for e in ev)
        d["time_mmss"] = all(isinstance(e, dict) and MMSS.match(str(e.get("time", ""))) for e in ev)
        d["kotu_time"] = [e.get("time") for e in ev
                          if isinstance(e, dict) and not MMSS.match(str(e.get("time", "")))]
    d["risk"] = veri.get("risk")
    d["risk_kumede"] = veri.get("risk") in SEVERITY
    ac = veri.get("actions")
    d["actions_liste"] = isinstance(ac, list)
    d["n_action"] = len(ac) if isinstance(ac, list) else None
    d["actions_bos"] = (isinstance(ac, list) and len(ac) == 0)
    if isinstance(ac, list) and ac:
        d["actions_genel"] = sum(1 for a in ac if isinstance(a, str)
                                 and any(g in a.lower() for g in GENEL_AKSIYON) and len(a) < 70)
        d["actions_ort_uzunluk"] = round(sum(len(str(a)) for a in ac) / len(ac), 1)
    d["summary_str"] = isinstance(veri.get("summary"), str)
    d["summary_uzunluk"] = len(veri.get("summary") or "") if isinstance(veri.get("summary"), str) else None
    return d


def tek_cagri(model, video_url, sema_zorla, max_tokens=1200):
    metin = GOREV if sema_zorla else GOREV + SERBEST_EK
    mesajlar = [
        {"role": "system", "content": SYSTEM_PERSONA},
        {"role": "user", "content": [
            {"type": "video_url", "video_url": {"url": video_url}},
            {"type": "text", "text": metin},
        ]},
    ]
    kw = dict(model=model, messages=mesajlar, temperature=0.0, max_tokens=max_tokens, seed=1234,
              extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    if sema_zorla:
        kw["response_format"] = RF
    t0 = time.time()
    r = istemci.chat.completions.create(**kw)
    sure = time.time() - t0
    return (r.choices[0].message.content or "", sure,
            r.usage.completion_tokens, r.usage.prompt_tokens)


def main():
    kollar = [("L-strict", "llm-large", True),
              ("F-strict", "llm-fast", True),
              ("L-serbest", "llm-large", False)]
    sonuc = {"kunye": {"tarih": datetime.now().isoformat(timespec="seconds"),
                       "video": "servis_videosu(max_side=768, crf=28)",
                       "T": 0.0, "seed": 1234, "max_tokens": 1200,
                       "thinking": "kapali (enable_thinking=False)",
                       "sema": K1_SEMA, "gorev_prompt": GOREV,
                       "base_url": settings.base_url},
              "klipler": [{"etiket": e, "anomali": a, "yol": y} for e, a, y in KLIPLER],
              "satirlar": []}

    for etiket, anomali, rel in KLIPLER:
        yol = os.path.join(KOK, rel)
        if not os.path.exists(yol):
            print("!! YOK: " + rel)
            continue
        b = servis_videosu(yol, max_side=768, crf=28)
        url = "data:video/mp4;base64," + base64.b64encode(b).decode()
        print("\n=== %s  (%.2f MB)" % (etiket, len(b) / 1e6))
        for kol, model, zorla in kollar:
            try:
                ham, sure, ctok, ptok = tek_cagri(model, url, zorla)
                veri, yontem = ayristir(ham)
                d = denetle(veri)
                satir = {"klip": etiket, "anomali": anomali, "kol": kol, "model": model,
                         "strict": zorla, "sure_s": round(sure, 2), "cikti_token": ctok,
                         "girdi_token": ptok, "ayristirma": yontem, "denetim": d,
                         "ham_ilk300": ham[:300], "cikti": veri}
                bayrak = "OK" if d.get("tam4") else "SOZLESME-IHLAL"
                if yontem is None:
                    bayrak = "AYRISTIRMA-HATASI"
                elif yontem == "kurtarma":
                    bayrak += "/kurtarildi"
                print("  %-10s %6.1fs tok=%4d risk=%-8s n_ev=%s n_ac=%s -> %s"
                      % (kol, sure, ctok, str(d.get("risk")), d.get("n_event"),
                         d.get("n_action"), bayrak))
            except Exception as e:
                satir = {"klip": etiket, "anomali": anomali, "kol": kol, "model": model,
                         "strict": zorla, "hata": "%s: %s" % (type(e).__name__, str(e)[:300])}
                print("  %-10s HATA %s: %s" % (kol, type(e).__name__, str(e)[:200]))
            sonuc["satirlar"].append(satir)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    cikti = os.path.join(KOK, "benchmark", "results", "tekcagri_k1_%s.json" % ts)
    with open(cikti, "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=1)
    print("\nyazildi: " + cikti)


if __name__ == "__main__":
    main()
