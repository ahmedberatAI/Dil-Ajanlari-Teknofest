#!/usr/bin/env python
"""ISG serbest-metin halusinasyon muhafizlari — modelsiz regresyon kilidi."""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dilajan.agent import graph as G  # noqa: E402
from dilajan.schema import Event, EventCategory, Severity  # noqa: E402


fails: list[str] = []


def check(label: str, condition: bool) -> None:
    print(("  [OK]   " if condition else "  [FAIL] ") + label)
    if not condition:
        fails.append(label)


class _Segment:
    index = 0
    frames = [("00:00", b"frame")]


class _Verifier:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    def gorev(self, _name):
        return self

    def analyze_frames(self, *_args, **_kwargs):
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


print("=== IDDIA AILELERI ===")
for text, family in (
    ("Makineden yoğun duman yükseliyor", "yangın/duman"),
    ("Zeminde hareketsiz yaralı kişi var", "düşme/yaralı kişi"),
    ("İki çalışan kavga ediyor", "şiddet/silah"),
    ("Forklift devrildi", "çarpışma/devrilme"),
    ("Yetkisiz kişi kısıtlı bölgeye girdi", "yetkisiz giriş/müdahale"),
    ("İşçide KKD eksikliği var", "KKD eksikliği"),
):
    check(f"{family}: yakalanir", family in G._claim_families(text))
check("yaya yolu ihlali yetkisiz-erisim sayilmaz",
      "yetkisiz giriş/müdahale" not in G._claim_families("Yaya yolu ihlali"))


print("\n=== SIDDDETTEN BAGIMSIZ FAIL-CLOSED GORSEL KAPI ===")
events = [
    Event(time="00:01", event="Makineden hafif duman yükseliyor",
          severity=Severity.DUSUK, category=EventCategory.GUVENLIK),
    Event(time="00:02", event="Zeminde hareketsiz yaralı kişi var",
          severity=Severity.DUSUK, category=EventCategory.SAGLIK),
    Event(time="00:03", event="Çalışan rutin olarak makineyi kullanıyor",
          severity=Severity.DUSUK, category=EventCategory.NORMAL),
]
verifier = _Verifier(["HAYIR. Gri platform duman değildir.", RuntimeError("servis")])
old_claim = G.settings.claim_guard
try:
    G.settings.claim_guard = True
    kept, note = G._guard_narrative_claims(verifier, _Segment(), events)
finally:
    G.settings.claim_guard = old_claim
check("HAYIR denilen Dusuk duman iddiasi tamamen silinir", events[0] not in kept)
check("dogrulama hatasi fail-closed: yarali iddiasi silinir", events[1] not in kept)
check("somut alarm iddiasi olmayan rutin olay korunur", kept == [events[2]])
check("yalniz iki somut iddia icin iki cagri", verifier.calls == 2)
check("redler karar izine acikca yazilir", bool(note and "2 desteklenmeyen" in note))


print("\n=== OZET + RISK + AKSIYON KANIT SINIRI ===")


class _ReasonVLM:
    def __init__(self, payload):
        self.payload = payload

    def gorev(self, _name):
        return self

    def chat(self, *_args, **_kwargs):
        return json.dumps(self.payload, ensure_ascii=False)


def run_reason(payload, events):
    old_get = G._get_vlm
    old_summary = G.settings.summary_evidence_guard
    old_ceiling = G.settings.risk_event_ceiling
    old_conf = G.settings.perception_confidence
    old_recall = G.settings.risk_recall_bias
    try:
        G._get_vlm = lambda: _ReasonVLM(payload)
        G.settings.summary_evidence_guard = True
        G.settings.risk_event_ceiling = True
        G.settings.perception_confidence = False
        G.settings.risk_recall_bias = False
        return G.reason({"events": events, "trace": [], "scene_cuts": []})
    finally:
        G._get_vlm = old_get
        G.settings.summary_evidence_guard = old_summary
        G.settings.risk_event_ceiling = old_ceiling
        G.settings.perception_confidence = old_conf
        G.settings.risk_recall_bias = old_recall


hallucinated = {
    "summary": "Yetkisiz erişim, KKD eksikliği ve yaralı kişi var.",
    "risk": {"level": "Kritik", "rationale": "Yaralı nedeniyle acil risk."},
    "actions": [{"action": "Acil sağlık ekibi çağır", "priority": "Kritik"}],
}
empty = run_reason(hallucinated, [])
check("olay yoksa ozet kanitsiz iddia tasimaz",
      not G._claim_families(empty["summary"]))
check("olay yoksa risk Dusuk", empty["risk"].level == Severity.DUSUK)
check("olay yoksa model aksiyonlari silinir", empty["actions"] == [])

low_event = Event(time="00:04", event="Rutin kapı hareketi gözlendi",
                  severity=Severity.DUSUK, category=EventCategory.NORMAL)
one = run_reason({
    "summary": "Rutin kapı hareketi yanında yoğun duman görüldü.",
    "risk": {"level": "Kritik", "rationale": "Yoğun duman nedeniyle kritik."},
    "actions": [{"action": "Kapıyı kontrol et", "priority": "Kritik"}],
}, [low_event])
check("ozetin ekledigi duman iddiasi cikarimsal ozetle degistirilir",
      "duman" not in one["summary"].lower())
check("risk dogrulanmis en yuksek olay onemini asamaz",
      one["risk"].level == Severity.DUSUK)
check("aksiyon onceligi olay tavanini asamaz",
      one["actions"] and one["actions"][0].priority == Severity.DUSUK)

print(f"\ngecen={18 - len(fails)} kalan={len(fails)}")
raise SystemExit(1 if fails else 0)
