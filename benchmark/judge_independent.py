#!/usr/bin/env python
"""BAGIMSIZ (farkli model ailesi) LLM-as-judge — self-evaluation donguselligini kirar (E1).

Sorun: ozet/aksiyon/risk-gerekce/diyalog kalite skorlari simdiye kadar Qwen3-VL'in KENDISI
tarafindan puanlaniyordu (ureten = puanlayan -> dongusel, sismis skor riski).

Cozum: Qwen3-VL ciktilarini onceden kaydet (eval_clips.py + gen_dialogue.py), sonra FARKLI
bir aile modeli (DILAJAN_JUDGE_MODEL, or. Gemma/Aya/Llama) servis edip bu betikle puanla.

NOT: recall / FP / risk-kalibrasyon / keyword-kategori ZATEN objektiftir (dataset etiketine
karsi olculur, LLM-judge degil) -> dongusel DEGIL. Bu betik yalniz METIN-KALITE skorlarini
bagimsizlastirir.

Kullanim (judge modeli vLLM'de servis edildikten SONRA):
    DILAJAN_JUDGE_MODEL=google/gemma-2-9b-it python benchmark/judge_independent.py [eval_xx.json]
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.utils import extract_json  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "benchmark", "results")
JUDGE_MODEL = os.environ.get("DILAJAN_JUDGE_MODEL", "").strip()

SYS = "Sen tarafsiz, titiz bir degerlendirme hakemisin. Yalnizca istenen JSON'u uret."

SUMMARY_JUDGE = """Bir video analiz sisteminin urettigi Turkce OZETI degerlendiren tarafsiz hakemsin.

Sistemin o videoda tespit ettigi olaylar:
{events}

Uretilen ozet:
"{summary}"

Bu ozeti 1-5 puanla (5 en iyi):
- dogruluk: Ozet tespit edilen olaylari sadik/tutarli yansitiyor mu (uydurma/eksik var mi)
- akicilik: Turkce dil bilgisi + akicilik (yabanci kelime/karakter sizintisi varsa dusur)
- ozluluk: Gereksiz tekrar yok, operatorun hizli karar almasini destekler mi
YALNIZCA JSON: {{"dogruluk": n, "akicilik": n, "ozluluk": n}}"""

ACT_JUDGE = """Bir guvenlik operasyon merkezi karar-destek sisteminin urettigi AKSIYON onerilerini degerlendiren tarafsiz hakemsin.
Tespit edilen olaylar: {events}
Risk: {risk}
Uretilen aksiyon onerileri: {actions}
1-5 puanla: alaka (olay/riskle iliskili mi), uygulanabilirlik (somut/emir kipinde/operatorun yapabilecegi), oncelik (onem sirasi dogru mu), kapsama (kritik olay icin gerekli aksiyon eksik mi).
YALNIZCA JSON: {{"alaka":n,"uygulanabilirlik":n,"oncelik":n,"kapsama":n}}"""

RISK_JUDGE = """Bir risk degerlendirmesinin GEREKCESINI degerlendiren tarafsiz hakemsin.
Tespit edilen olaylar: {events}
Risk seviyesi: {level}
Risk gerekcesi: "{rationale}"
1-5 puanla: dayanaklilik (gerekce gercekten olaylara dayaniyor mu, uydurma yok), tutarlilik (gerekce ile seviye celismiyor mu), eyleme_donukluk (neden-aciliyet veriyor mu).
YALNIZCA JSON: {{"dayanaklilik":n,"tutarlilik":n,"eyleme_donukluk":n}}"""

SINGLE_JUDGE = """Bir guvenlik karar-destek asistaninin verdigi yaniti degerlendiren tarafsiz hakemsin.
Senaryo turu: {stype}
Beklenen davranis: {expected}
Operator mesaji: "{msg}"
Asistanin yaniti: "{resp}"
Asistan beklenen davranisi ne kadar karsiladi? 1-5 (5=tam). YALNIZCA JSON: {{"uygunluk": n}}"""

MT_JUDGE = """Bir guvenlik asistaniyla cok-turlu sohbette asistanin SON yanitini degerlendiren tarafsiz hakemsin.
Su ana kadarki sohbet:
{history}
Operatorun son mesaji: "{msg}"
Asistanin son yaniti: "{resp}"
Beklenen davranis: {expected}
Asistan ONCEKI turlarin baglamini dogru kullandi mi (gonderme/zaman/oz-referans), tutarli ve grounded mi?
1-5 (5=tam). YALNIZCA JSON: {{"uygunluk": n}}"""


def _score(client: VLMClient, prompt: str, keys: list[str], maxt: int = 150):
    raw = client.chat([{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
                      temperature=0.0, max_tokens=maxt)
    s = extract_json(raw)
    vals = []
    for k in keys:
        v = float(s.get(k, 0))
        if 1 <= v <= 5:
            vals.append(v)
    return vals


def _events_text(row: dict) -> str:
    evs = row.get("events", [])
    if not evs:
        return "(olay yok)"
    return "; ".join(f"[{e.get('time')}] {e.get('event')} (onem:{e.get('severity')})" for e in evs)


def _ms(vals):
    if not vals:
        return (None, None, 0)
    return (statistics.mean(vals), statistics.stdev(vals) if len(vals) > 1 else 0.0, len(vals))


def main() -> None:
    if not JUDGE_MODEL:
        print("HATA: DILAJAN_JUDGE_MODEL ayarli degil. Or: DILAJAN_JUDGE_MODEL=google/gemma-2-9b-it ...")
        sys.exit(1)
    client = VLMClient(model=JUDGE_MODEL)
    if not client.health_check():
        print(f"HATA: judge modeli '{JUDGE_MODEL}' vLLM'de servis edilmiyor. Once swap-serve et.")
        sys.exit(1)
    print(f"BAGIMSIZ JUDGE: {JUDGE_MODEL}\n" + "=" * 60)

    # --- analiz ciktilari (en son eval_*.json) ---
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        files = sorted(glob.glob(os.path.join(RESULTS_DIR, "eval_*.json")))
        path = files[-1] if files else None
    out = {"judge_model": JUDGE_MODEL}

    if path and os.path.exists(path):
        rows = json.load(open(path, encoding="utf-8"))["rows"]
        print(f"Analiz ciktilari: {os.path.relpath(path, ROOT)} ({len(rows)} klip)")
        summ, act, risk = [], [], []
        for r in rows:
            ev_txt = _events_text(r)
            if r.get("summary"):
                summ += _score(client, SUMMARY_JUDGE.format(events=ev_txt, summary=r["summary"]),
                               ["dogruluk", "akicilik", "ozluluk"])
            if r.get("events") and r.get("actions"):
                act_txt = "; ".join(f"[{a.get('priority')}] {a.get('action')}" for a in r["actions"])
                act += _score(client, ACT_JUDGE.format(events=ev_txt, risk=r.get("risk_level"), actions=act_txt),
                              ["alaka", "uygulanabilirlik", "oncelik", "kapsama"], maxt=120)
            if r.get("events") and r.get("risk_rationale"):
                risk += _score(client, RISK_JUDGE.format(events=ev_txt, level=r.get("risk_level"),
                               rationale=r["risk_rationale"]),
                               ["dayanaklilik", "tutarlilik", "eyleme_donukluk"], maxt=120)
        for name, vals in [("OZET kalitesi", summ), ("AKSIYON kalitesi", act), ("RISK gerekce", risk)]:
            m, sd, n = _ms(vals)
            if m is not None:
                print(f"  {name:18s}: {m:.2f} ± {sd:.2f}   (n={n})")
                out[name] = {"mean": round(m, 2), "std": round(sd, 2), "n": n}
    else:
        print("(eval_*.json yok — once: python benchmark/eval_clips.py)")

    # --- diyalog ciktilari ---
    dpath = os.path.join(RESULTS_DIR, "dialogue_responses.json")
    if os.path.exists(dpath):
        d = json.load(open(dpath, encoding="utf-8"))
        print(f"\nDiyalog yanitlari: dialogue_responses.json "
              f"(tek={len(d['single'])}, cok-tur={len(d['multi'])})")
        single = []
        for it in d["single"]:
            single += _score(client, SINGLE_JUDGE.format(stype=it["stype"], expected=it["expected"],
                             msg=it["msg"], resp=it["resp"]), ["uygunluk"], maxt=80)
        multi = []
        for it in d["multi"]:
            multi += _score(client, MT_JUDGE.format(history=it["history"], msg=it["msg"],
                            resp=it["resp"], expected=it["expected"]), ["uygunluk"], maxt=80)
        for name, vals in [("DIYALOG tek-tur", single), ("DIYALOG cok-tur", multi)]:
            m, sd, n = _ms(vals)
            if m is not None:
                print(f"  {name:18s}: {m:.2f} ± {sd:.2f}   (n={n})")
                out[name] = {"mean": round(m, 2), "std": round(sd, 2), "n": n}
    else:
        print("\n(dialogue_responses.json yok — once: python benchmark/gen_dialogue.py)")

    op = os.path.join(RESULTS_DIR, "independent_scores.json")
    with open(op, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n" + "=" * 60)
    print(f"Kaydedildi: {os.path.relpath(op, ROOT)}")
    print("Karsilastir: bunlar FARKLI aile modelle (dongusel-olmayan) skorlar.")


if __name__ == "__main__":
    main()
