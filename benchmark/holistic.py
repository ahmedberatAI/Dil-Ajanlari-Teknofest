#!/usr/bin/env python
"""Holistik sartname performans testi: temsili sette tum zorunlu ciktilar olculur ve
4 puanlama eksenine (Islevsellik/Teknik/Otonomi/Inovasyon) eslenen bir KARNE uretir.

Kapatilan boşluklar:
  M1 aksiyon kalitesi (LLM-judge)   M2 agentic dispatch dogrulugu (anomali->fonksiyon, normal->yok)
  M3 JSON sema uyumu                 M4 risk gerekce kalitesi (LLM-judge)
  + mevcut: tespit, risk-seviyesi, ozet kalitesi (judge), gecikme.

!!! K11 — OLCUM SINIRI (RAPORLARKEN MUTLAKA BELIRT) !!!
Buradaki LLM-judge eksenleri (M1 aksiyon kalitesi, M4 risk gerekcesi, ozet kalitesi)
IC TUTARLILIK olcer, videoya DAYANAKLILIK DEGIL: hakeme sistemin KENDI ciktilari verilir,
klibin gercek etiketi/kareleri verilmez. Uydurulmus ama kendi icinde tutarli bir cikti
tam puan alabilir. OBJEKTIF eksenler (M2 dispatch dogrulugu, M3 JSON sema uyumu, tespit,
risk-seviyesi, gecikme) dataset etiketine/semaya karsi olculur -> bunlar dayanaklidir.
Dayanakli ozet/aksiyon olcumu icin: benchmark/judge_independent.py (etiket-dayanakli mod).

Kullanim:  python benchmark/holistic.py
"""
from __future__ import annotations

import glob
import json
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.agent import analyze_video  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.utils import extract_json  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _first(*globs):
    for g in globs:
        m = sorted(glob.glob(os.path.join(ROOT, g)))
        if m:
            return m[0]
    return None


# temsili set: (yol, tur, anomali_mi)
def build_set():
    s = []
    fires = sorted(glob.glob(os.path.join(ROOT, "data/eval_scenario/Fire/*.avi")))[:2]
    falls = sorted(glob.glob(os.path.join(ROOT, "data/falls_real/Fall/*.mp4")))[:2]
    for f in fires:
        s.append((f, "Yangın", True))
    for f in falls:
        s.append((f, "Düşme", True))
    for p, t in [("data/ucf_explosion.mp4", "Patlama"), ("data/ucf_roadaccidents.mp4", "Trafik kazası")]:
        fp = os.path.join(ROOT, p)
        if os.path.exists(fp):
            s.append((fp, t, True))
    norms = []
    n1 = _first("data/industrial/class0/*.mp4")
    n2 = _first("data/eval/Normal/Normal_Videos_926_x264.mp4", "data/eval/Normal/*.mp4")
    n3 = _first("data/falls_real/Normal/*.mp4")
    for n in (n1, n2, n3):
        if n:
            norms.append(n)
    for n in norms:
        s.append((n, "Normal", False))
    return s


ACT_JUDGE = """Bir güvenlik operasyon merkezi karar-destek sisteminin ürettiği AKSİYON önerilerini değerlendiren tarafsiz hakemsin.
Tespit edilen olaylar: {events}
Risk: {risk}
Üretilen aksiyon önerileri: {actions}
1-5 puanla (5 en iyi): alaka (olay/riskle ilişkili mi), uygulanabilirlik (somut, emir kipinde, operatörün yapabileceği), oncelik (önem sırası doğru mu), kapsama (kritik olay için gerekli aksiyon eksik mi).
YALNIZCA JSON: {{"alaka":n,"uygulanabilirlik":n,"oncelik":n,"kapsama":n}}"""

RISK_JUDGE = """Bir risk değerlendirmesinin GEREKÇESİNİ değerlendiren tarafsiz hakemsin.
Tespit edilen olaylar: {events}
Risk seviyesi: {level}
Risk gerekçesi: "{rationale}"
1-5 puanla: dayanaklilik (gerekçe gerçekten olaylara dayaniyor mu, uydurma yok), tutarlilik (gerekçe ile seviye çelişmiyor mu), eyleme_donukluk (neden-aciliyet veriyor mu).
YALNIZCA JSON: {{"dayanaklilik":n,"tutarlilik":n,"eyleme_donukluk":n}}"""

REQUIRED_KEYS = {"summary", "events", "risk", "actions"}
MMSS = re.compile(r"^\d{1,2}:\d{2}(–\d{1,2}:\d{2})?$")


def main() -> None:
    clips = build_set()
    print(f"Holistik test — {len(clips)} temsili klip\n")
    C = VLMClient()
    rows = []
    for path, typ, is_anom in clips:
        t0 = time.time()
        r = analyze_video(path)
        dt = time.time() - t0
        d = r.to_sartname_dict()

        # M3 JSON uyum
        json_ok = REQUIRED_KEYS.issubset(d.keys())
        times_ok = all(MMSS.match(str(e.get("time", ""))) for e in d["events"]) if d["events"] else True
        try:
            json.dumps(d, ensure_ascii=False)
            parse_ok = True
        except Exception:
            parse_ok = False
        json_score = json_ok and times_ok and parse_ok

        # M2 dispatch dogrulugu
        n_trig = len(r.triggered_functions)
        if is_anom:
            dispatch_ok = n_trig >= 1            # anomalide >=1 fonksiyon beklenir
        else:
            dispatch_ok = n_trig == 0            # normalde fonksiyon tetiklenmemeli

        # tespit
        detected = len(r.events) > 0
        risk_ok = (r.risk.level.value in ("Yüksek", "Kritik")) if is_anom else (r.risk.level.value == "Düşük")

        ev_txt = "; ".join(e.event for e in r.events) or "(yok)"
        act_txt = "; ".join(f"[{a.priority.value}] {a.action}" for a in r.actions) or "(yok)"

        # M1 aksiyon kalitesi (yalniz anomalide anlamli)
        act_score = None
        if is_anom and r.actions:
            try:
                s = extract_json(C.chat([{"role": "system", "content": "Tarafsiz hakemsin."},
                    {"role": "user", "content": ACT_JUDGE.format(events=ev_txt, risk=r.risk.level.value, actions=act_txt)}],
                    temperature=0.0, max_tokens=120))
                act_score = statistics.mean([float(s[k]) for k in ("alaka", "uygulanabilirlik", "oncelik", "kapsama")])
            except Exception:
                act_score = None

        # M4 risk gerekce (yalniz anomalide)
        risk_jscore = None
        if is_anom:
            try:
                s = extract_json(C.chat([{"role": "system", "content": "Tarafsiz hakemsin."},
                    {"role": "user", "content": RISK_JUDGE.format(events=ev_txt, level=r.risk.level.value, rationale=r.risk.rationale)}],
                    temperature=0.0, max_tokens=120))
                risk_jscore = statistics.mean([float(s[k]) for k in ("dayanaklilik", "tutarlilik", "eyleme_donukluk")])
            except Exception:
                risk_jscore = None

        rows.append(dict(typ=typ, is_anom=is_anom, detected=detected, risk_ok=risk_ok,
                         json_score=json_score, dispatch_ok=dispatch_ok, n_trig=n_trig,
                         act_score=act_score, risk_jscore=risk_jscore, lat=dt))
        mark = "✓" if (detected if is_anom else not detected) else "·"
        print(f"  {mark} [{typ:13s}] tespit={detected} risk={r.risk.level.value:6s} "
              f"json={'✓' if json_score else '✗'} dispatch={'✓' if dispatch_ok else '✗'}({n_trig}) "
              f"aksiyon={act_score if act_score is None else round(act_score,1)} "
              f"riskGerekce={risk_jscore if risk_jscore is None else round(risk_jscore,1)}")

    # --- toplulastir ---
    anom = [r for r in rows if r["is_anom"]]
    norm = [r for r in rows if not r["is_anom"]]

    def frac(xs):
        return 100 * sum(xs) / len(xs) if xs else 0

    def avg(xs):
        xs = [x for x in xs if x is not None]
        return round(statistics.mean(xs), 2) if xs else None

    print("\n" + "=" * 60)
    print("KARNE (holistik)")
    print("=" * 60)
    print("İŞLEVSELLİK (%35):")
    print(f"  Olay tespiti (anomali recall)   : {frac([r['detected'] for r in anom]):.0f}%")
    print(f"  Risk seviyesi doğruluğu         : {frac([r['risk_ok'] for r in rows]):.0f}%")
    print(f"  Aksiyon kalitesi (M1, 1-5)      : {avg([r['act_score'] for r in anom])}")
    print(f"  Risk gerekçe kalitesi (M4, 1-5) : {avg([r['risk_jscore'] for r in anom])}")
    print(f"  JSON şema uyumu (M3)            : {frac([r['json_score'] for r in rows]):.0f}%")
    print(f"  Normal yanlış-pozitif (tespit)  : {frac([r['detected'] for r in norm]):.0f}%  (düşük=iyi)")
    print("OTONOMİ (%20):")
    print(f"  Agentic dispatch doğruluğu (M2) : {frac([r['dispatch_ok'] for r in rows]):.0f}%")
    print(f"    - anomalide fonksiyon tetik   : {frac([r['n_trig']>0 for r in anom]):.0f}%")
    print(f"    - normalde yanlış-tetik YOK   : {frac([r['n_trig']==0 for r in norm]):.0f}%")
    print("TEKNİK (%35):")
    print(f"  Gecikme medyan                  : {statistics.median([r['lat'] for r in rows]):.0f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
