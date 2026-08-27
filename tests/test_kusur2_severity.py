"""KUSUR #2 (risk yukseltme) — policy_gate birim testleri.

Olculen kusur: model politika-ihlalini GORUYOR ve DOGRU ADLANDIRIYOR (recall %47, kategori %33)
ama ONEM DERECESINI dusuk veriyor (47 tespitin 34'u severity=Dusuk) -> risk tabani Dusuk ->
sevk kapisi acilmiyor. Cozum: severity operatorun BEYANINDAN (settings.facility_policy) gelir,
olay<->kural eslesmesi MODEL ile (anlamsal) yapilir.

VLM/GPU GEREKTIRMEZ: tek VLM temas noktasi (graph._get_vlm) sahte istemciyle degistirilir.

Kosum:  python tests/test_kusur2_severity.py        (repo kokunden)
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import policy, prompts
from dilajan.agent import graph as G
from dilajan.config import settings
from dilajan.schema import (
    Action,
    AnalysisResult,
    Event,
    EventCategory,
    RiskAssessment,
    Severity,
)

FAILS: list = []
_ORIG_VLM = G._get_vlm


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  [OK]   " if cond else "  [FAIL] ") + name + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


class FakeVLM:
    """policy_gate'in kullandigi tek arayuz: .chat(...) -> JSON metni. Cagri sayaci tutar."""

    def __init__(self, payload="", raise_exc: bool = False):
        self.payload = payload
        self.raise_exc = raise_exc
        self.calls = 0
        self.last_prompt = ""

    def gorev(self, _gorev: str):
        return self

    def chat(self, messages, **kw):
        self.calls += 1
        self.last_prompt = messages[-1]["content"] if messages else ""
        if self.raise_exc:
            raise RuntimeError("sahte VLM patlamasi (simule)")
        return self.payload

    def analyze_frames(self, frames, prompt, **kw):
        self.calls += 1
        if self.raise_exc:
            raise RuntimeError("sahte VLM patlamasi (simule)")
        return self.payload


def use(vlm):
    G._get_vlm = lambda: vlm
    return vlm


def restore():
    G._get_vlm = _ORIG_VLM


class policy_cfg:
    """Test suresince settings uzerinde gecici override (cikista geri yuklenir)."""

    def __init__(self, **kw):
        self.kw = kw
        self.prev = {}

    def __enter__(self):
        for k, v in self.kw.items():
            self.prev[k] = getattr(settings, k)
            setattr(settings, k, v)
        policy.clear_cache()
        return settings

    def __exit__(self, *a):
        for k, v in self.prev.items():
            setattr(settings, k, v)
        policy.clear_cache()
        return False


# --- GERCEK olay metinleri (eval_20260726_171601.json, hepsi severity=Dusuk almisti) ---
GERCEK_METINLER = [
    "Forklift aşırı yük taşıyor",
    "Forklift aşırı yüklenmiş ve yük yüksekliği güvenlik sınırlarını aşıyor",
    "İşçi forklift sahasına hızlı adımlarla ilerliyor",
    "Forklift yük taşıma kapasitesini aşmış, makineye dokunma riski taşıyor",
    "İşçi, forkliftin yolunu kesmeyecek şekilde ancak tehlikeli pozisyonda duruyor",
]

# Operatorun BEYAN ETTIGI ornek politika (KODDA DEGIL, testte/dagitimda yazilir)
ORNEK_POLITIKA = (
    "Personel yalnızca işaretli yürüyüş yolunda hareket eder | yürüyüş yolu içinde kalmak | Yüksek\n"
    "Yetkisiz personel makine panellerine müdahale etmez | | Yüksek | sevk\n"
    "Yük taşıma araçları beyan edilen yük sınırını aşamaz | yük sınırı içinde taşıma | Yüksek\n"
    "Personel çalışan makine ve araç sahasına yaya olarak giremez | | Yüksek\n"
)


def ev(text, sev=Severity.DUSUK, cat=EventCategory.ANOMALI, time="00:03", **kw):
    return Event(time=time, event=text, severity=sev, category=cat, **kw)


def state(events, **kw):
    s = {"events": list(events), "trace": []}
    s.update(kw)
    return s


def verdict_json(items):
    return json.dumps({"sonuc": items}, ensure_ascii=False)


# =====================================================================
print("\n=== (1) GERCEK olay metinleri + ornek politika -> severity YUKSELIYOR mu ===")
# =====================================================================
with policy_cfg(facility_policy=ORNEK_POLITIKA, policy_dispatch=False,
                policy_max_escalations=8, policy_verify_frames=False):
    evs = [ev(t, time=f"00:0{i}") for i, t in enumerate(GERCEK_METINLER)]
    # Model YALNIZCA eslesme + kanit doner (severity ISTENMEZ / cikti-uzayinda YOKTUR)
    payload = verdict_json([
        {"no": 1, "kural": "R3", "karar": "IHLAL", "kanit": "aşırı yük taşıyor"},
        {"no": 2, "kural": "R3", "karar": "IHLAL", "kanit": "yük yüksekliği güvenlik sınırlarını aşıyor"},
        {"no": 3, "kural": "R4", "karar": "IHLAL", "kanit": "forklift sahasına hızlı adımlarla ilerliyor"},
        {"no": 4, "kural": "R3", "karar": "IHLAL", "kanit": "yük taşıma kapasitesini aşmış"},
        {"no": 5, "kural": "R1", "karar": "IHLAL", "kanit": "tehlikeli pozisyonda duruyor"},
    ])
    vlm = use(FakeVLM(payload))
    out = G.policy_gate(state(evs))
    sevs = [e.severity for e in out["events"]]
    check("5 gercek olay metninin tamami Dusuk -> Yuksek yukseltildi",
          sevs == [Severity.YUKSEK] * 5, str([s.value for s in sevs]))
    check("model cagrisi VIDEO BASINA TEK (goruntusuz chat)", vlm.calls == 1, f"calls={vlm.calls}")
    check("promptta severity ISTENMIYOR (model cikti-uzayinda yok)",
          "severity" not in vlm.last_prompt.lower()
          and "ÖNEM/CİDDİYET DERECESİ BELİRLEMEYECEKSİN" in vlm.last_prompt)
    check("policy_escalations kaydi 5 yukseltme icerir", len(out["policy_escalations"]) == 5)
    check("policy_max_intrinsic yukseltme ONCESI degeri tasiyor (Dusuk=1)",
          out["policy_max_intrinsic"] == 1, str(out["policy_max_intrinsic"]))
    check("K5: her yukseltme kural-ID + karar + kanit ile karar-izine yazildi",
          sum(1 for t in out["trace"] if "karar=IHLAL" in t and "kanit=" in t) == 5
          and all(("Düşük->Yüksek" in t) for t in out["trace"] if "karar=IHLAL" in t),
          str([t for t in out["trace"] if t.startswith("policy:")][:3]))
    check("K5: ayristirilmis KURAL TABLOSU (beyan) karar-izinde",
          any("kural ayristirildi" in t and "beyan=Yüksek" in t for t in out["trace"]))
    check("K5: teshis satiri (aday/yukseltme/red/karar dagilimi/sevk yolu) var",
          any("aday," in t and "sevk yolu KAPALI" in t for t in out["trace"]))
    check("olay METNI ve KATEGORISI degismedi, YENI OLAY uretilmedi",
          [e.event for e in out["events"]] == GERCEK_METINLER
          and [e.category for e in out["events"]] == [EventCategory.ANOMALI] * 5)
restore()


# =====================================================================
print("\n=== (2) K2 REGRESYON: facility_policy BOS -> davranis BIREBIR AYNI ===")
# =====================================================================
with policy_cfg(facility_policy=""):
    evs = [ev(t) for t in GERCEK_METINLER]
    before = [e.model_dump() for e in evs]
    vlm = use(FakeVLM(verdict_json([{"no": 1, "kural": "R1", "karar": "IHLAL", "kanit": "x"}])))
    out = G.policy_gate(state(evs))
    check("policy_gate TAM NO-OP: bos sozluk doner", out == {}, str(out))
    check("MODEL CAGRISI YAPILMADI (calls=0)", vlm.calls == 0, f"calls={vlm.calls}")
    check("olaylar BIT DUZEYINDE ayni (model_dump identik)",
          [e.model_dump() for e in evs] == before)
    check("karar-izine SATIR BILE eklenmedi", "trace" not in out)
restore()

with policy_cfg(facility_policy="   \n  \n"):
    vlm = use(FakeVLM("{}"))
    check("yalniz bosluk/satir-sonu iceren politika da TAM NO-OP",
          G.policy_gate(state([ev("x")])) == {} and vlm.calls == 0)
restore()

with policy_cfg(facility_policy="kisa | Yüksek"):  # < 12 normalize karakter -> madde REDDEDILIR
    vlm = use(FakeVLM("{}"))
    out = G.policy_gate(state([ev("Forklift aşırı yük taşıyor")]))
    check("gecerli kural cikmazsa: cagri yok + yukseltme yok",
          vlm.calls == 0 and "events" not in out
          and any("gecerli kural cikarilamadi" in t for t in out.get("trace", [])))
restore()


# =====================================================================
print("\n=== (2b) K2 CEBIR: bos politikada uc-terimli dispatch = eski iki-terimli ifade ===")
# =====================================================================


def eski_kapi(max_ev, risk_ord, recall_bias):
    """D18'deki (degistirilmeden onceki) ifade."""
    return (max_ev >= 3) or (risk_ord >= 3 and not recall_bias)


def yeni_kapi(max_ev, risk_ord, recall_bias, max_intrinsic, esc_sevk, policy_only):
    return ((max_intrinsic >= 3)
            or (esc_sevk and max_ev >= 3)
            or (risk_ord >= 3 and not recall_bias and not policy_only))


ayrik = [(m, r, b) for m in range(0, 5) for r in range(0, 5) for b in (False, True)
         if eski_kapi(m, r, b) != yeni_kapi(m, r, b, m, False, False)]
check("politika YOKKEN (max_intrinsic==max_ev, esc_sevk=F, policy_only=F) iki ifade "
      "TUM 50 kombinasyonda OZDES", not ayrik, str(ayrik[:3]))

# act() uzerinde uctan-uca: politika yokken kapi eskisi gibi calisir
use(FakeVLM('{"calls":[{"function":"yonetici_bilgilendir","args":{"mesaj":"x"}}]}'))
o = G.act(state([ev("kritik olay", Severity.KRITIK, EventCategory.KAZA)],
                risk=RiskAssessment(level=Severity.KRITIK, rationale="r")))
check("act: politika yokken YUKSEK olay -> sevk ACILIR (mevcut davranis)",
      o["triggered_functions"] == ["yonetici_bilgilendir"], str(o["triggered_functions"]))
o = G.act(state([ev("olagan", Severity.ORTA, EventCategory.NORMAL)],
                risk=RiskAssessment(level=Severity.ORTA, rationale="r")))
check("act: politika yokken Orta sinyal -> sevk YOK (mevcut davranis)",
      o["triggered_functions"] == [])
restore()


# =====================================================================
print("\n=== (3) K3 FP KORUMASI: normal/olagan metinler YUKSELTILMEZ ===")
# =====================================================================
with policy_cfg(facility_policy=ORNEK_POLITIKA):
    normaller = [
        ev("İşçi yürüyor", time="00:01"),
        ev("Forklift normal seyrediyor", time="00:02"),
        ev("İşçi güvenli yürüme yolu üzerinde ilerliyor", time="00:03"),
        ev("Rutin malzeme taşıma işlemi sürüyor", time="00:04"),
    ]
    # Model dogru davranir: alakasiz -> R0, uyum tarafi -> UYGUN
    vlm = use(FakeVLM(verdict_json([
        {"no": 1, "kural": "R0", "karar": "UYGUN", "kanit": ""},
        {"no": 2, "kural": "R0", "karar": "UYGUN", "kanit": ""},
        {"no": 3, "kural": "R1", "karar": "UYGUN", "kanit": ""},
        {"no": 4, "kural": "R0", "karar": "UYGUN", "kanit": ""},
    ])))
    out = G.policy_gate(state(normaller))
    check("normal/uyumlu 4 olayin HICBIRI yukseltilmedi",
          [e.severity for e in out["events"]] == [Severity.DUSUK] * 4
          and out["policy_escalations"] == [])
    check("iki-tarafli kural temsili: UYGUN karari karar-izinde gerekcelendirildi",
          any("karar=UYGUN" in t and "YUKSELTME YOK" in t for t in out["trace"]))

    # Kategori NORMAL olan olay ADAY BILE OLMAZ (bedava eleme)
    vlm = use(FakeVLM(verdict_json([])))
    out = G.policy_gate(state([ev("İşçi yürüyor", cat=EventCategory.NORMAL)]))
    check("kategori=Normal olay ADAY ALINMAZ -> model cagrisi hic yapilmaz",
          vlm.calls == 0 and "events" not in out
          and any("aday olay yok" in t for t in out.get("trace", [])))

    # G3 CEKINCE kapisi
    vlm = use(FakeVLM(verdict_json([{"no": 1, "kural": "R3", "karar": "IHLAL",
                                     "kanit": "yük kapasitesi aşımı"}])))
    out = G.policy_gate(state([ev("Yük kapasitesi aşımı şüpheli")]))
    check("G3: cekinceli metin ('şüpheli') -> YUKSELTME YOK",
          out["events"][0].severity == Severity.DUSUK
          and any("CEKINCE kapisi" in t for t in out["trace"]))

    vlm = use(FakeVLM(verdict_json([{"no": 1, "kural": "R3", "karar": "IHLAL",
                                     "kanit": "makineye dokunduğu veya çok yakın olduğu"}])))
    out = G.policy_gate(state([ev("Yükün makineye dokunduğu veya çok yakın olduğu görülüyor")]))
    check("G3: 'veya' cekincesi -> YUKSELTME YOK (bilincli FP-oncelikli asimetri)",
          out["events"][0].severity == Severity.DUSUK)

with policy_cfg(facility_policy=ORNEK_POLITIKA, policy_accept_hedged=True):
    vlm = use(FakeVLM(verdict_json([{"no": 1, "kural": "R3", "karar": "IHLAL",
                                     "kanit": "yük kapasitesi aşımı"}])))
    out = G.policy_gate(state([ev("Yük kapasitesi aşımı şüpheli")]))
    check("G3: policy_accept_hedged=True -> cekinceli metin YUKSELIR (opt-in)",
          out["events"][0].severity == Severity.YUKSEK)
restore()

with policy_cfg(facility_policy=ORNEK_POLITIKA):
    # G1 KAPSAM: BELIRSIZ / R0 / aralik disi kural kimligi
    for karar, rid, ad in (("BELIRSIZ", "R3", "karar=BELIRSIZ"),
                           ("IHLAL", "R0", "kural=R0"),
                           ("IHLAL", "R9", "aralik disi kural kimligi"),
                           ("UYGUN", "R3", "karar=UYGUN")):
        use(FakeVLM(verdict_json([{"no": 1, "kural": rid, "karar": karar,
                                   "kanit": "aşırı yük taşıyor"}])))
        out = G.policy_gate(state([ev("Forklift aşırı yük taşıyor")]))
        check(f"G1: {ad} -> YUKSELTME YOK", out["events"][0].severity == Severity.DUSUK)

    # G2 KANIT: uydurma / parafraz / cok kisa dayanak
    for kanit, ad in (("makinede yangın çıktı", "uydurma dayanak"),
                      ("yük", "tek-token dayanak"),
                      ("", "bos dayanak")):
        use(FakeVLM(verdict_json([{"no": 1, "kural": "R3", "karar": "IHLAL", "kanit": kanit}])))
        out = G.policy_gate(state([ev("Forklift aşırı yük taşıyor")]))
        check(f"G2: {ad} -> YUKSELTME YOK", out["events"][0].severity == Severity.DUSUK)

    # Bozuk JSON / eksik karar
    use(FakeVLM("bu bir JSON degil"))
    out = G.policy_gate(state([ev("Forklift aşırı yük taşıyor")]))
    check("bozuk JSON -> yukseltme yok, olaylar korunur, akis surer",
          out["events"][0].severity == Severity.DUSUK and out["policy_escalations"] == [])

    # G4 TAVAN: tek-yonlu, beyani asmaz, dusurmez
    use(FakeVLM(verdict_json([{"no": 1, "kural": "R3", "karar": "IHLAL",
                               "kanit": "aşırı yük taşıyor"}])))
    out = G.policy_gate(state([ev("Forklift aşırı yük taşıyor", Severity.KRITIK)]))
    check("G4: mevcut severity beyanin USTUNDE -> DUSURULMEZ (aday bile olmaz)",
          out.get("events", [ev("x", Severity.KRITIK)])[0].severity == Severity.KRITIK
          if "events" in out else True)

with policy_cfg(facility_policy="Yük taşıma araçları beyan edilen yük sınırını aşamaz | | Kritik"):
    use(FakeVLM(verdict_json([{"no": 1, "kural": "R1", "karar": "IHLAL",
                               "kanit": "aşırı yük taşıyor"}])))
    out = G.policy_gate(state([ev("Forklift aşırı yük taşıyor", Severity.ORTA)]))
    check("G4: yukseltme tam olarak BEYAN edilen dereceye cikar (Orta->Kritik), asmaz",
          out["events"][0].severity == Severity.KRITIK)

with policy_cfg(facility_policy="Yük taşıma araçları beyan edilen yük sınırını aşamaz | | Orta"):
    use(FakeVLM(verdict_json([{"no": 1, "kural": "R1", "karar": "IHLAL",
                               "kanit": "aşırı yük taşıyor"}])))
    out = G.policy_gate(state([ev("Forklift aşırı yük taşıyor", Severity.ORTA)]))
    check("G4: beyan mevcut severity'ye ESITSE aday alinmaz/yukseltme yok",
          out.get("events", [ev("x", Severity.ORTA)])[0].severity == Severity.ORTA)

with policy_cfg(facility_policy=ORNEK_POLITIKA, policy_max_escalations=2):
    evs = [ev(t, time=f"00:0{i}") for i, t in enumerate(GERCEK_METINLER)]
    use(FakeVLM(verdict_json([{"no": i + 1, "kural": "R3", "karar": "IHLAL",
                               "kanit": " ".join(t.split()[:4])}
                              for i, t in enumerate(GERCEK_METINLER)])))
    out = G.policy_gate(state(evs))
    n_up = sum(1 for e in out["events"] if e.severity == Severity.YUKSEK)
    check("G0 BUTCE: policy_max_escalations=2 -> en fazla 2 yukseltme",
          n_up == 2 and len(out["policy_escalations"]) == 2, f"n_up={n_up}")
restore()


# =====================================================================
print("\n=== (4) FAIL-OPEN: yeni mekanizma hata verirse eski severity korunur ===")
# =====================================================================
with policy_cfg(facility_policy=ORNEK_POLITIKA):
    evs = [ev(t) for t in GERCEK_METINLER[:2]]
    before = [e.model_dump() for e in evs]
    use(FakeVLM(raise_exc=True))
    out = G.policy_gate(state(evs))
    check("VLM istisnasi -> olaylar DEGISMEDEN korunur, trace'e not, akis surer",
          "events" not in out and [e.model_dump() for e in evs] == before
          and any("policy_gate: dugum hatasi" in t for t in out["trace"]))

    # policy modulunun kendisi patlarsa
    _orig = policy.adjudicate
    policy.adjudicate = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("hakemlik patlamasi"))
    try:
        use(FakeVLM(verdict_json([{"no": 1, "kural": "R3", "karar": "IHLAL", "kanit": "aşırı yük"}])))
        out = G.policy_gate(state([ev("Forklift aşırı yük taşıyor")]))
        check("policy modulu istisnasi -> FAIL-OPEN (olay degismez, trace'te not)",
              "events" not in out and any("dugum hatasi" in t for t in out["trace"]))
    finally:
        policy.adjudicate = _orig

    # parse_policy her kosulda liste dondurur (icten fail-open)
    check("parse_policy(None) cokmez", policy.parse_policy(None, Severity.YUKSEK) == [])
restore()


# =====================================================================
print("\n=== (5) K4 CIKTI SOZLESMESI: to_sartname_dict BOZULMADI ===")
# =====================================================================
with policy_cfg(facility_policy=ORNEK_POLITIKA):
    e0 = ev("Forklift aşırı yük taşıyor", end_time="00:09", bbox=[10, 20, 30, 40], region="merkez")
    use(FakeVLM(verdict_json([{"no": 1, "kural": "R3", "karar": "IHLAL",
                               "kanit": "aşırı yük taşıyor"}])))
    out = G.policy_gate(state([e0]))
    up = out["events"][0]
    check("K4/T8 ALAN KORUMA: end_time/bbox/region/kategori yukseltmeden sonra KORUNUR",
          up.end_time == "00:09" and up.bbox == [10, 20, 30, 40] and up.region == "merkez"
          and up.category == EventCategory.ANOMALI and up.severity == Severity.YUKSEK)
    check("K5: policy_ref / policy_prev olaya yazildi (aciklanabilirlik)",
          getattr(up, "policy_ref", None) == "R3"
          and getattr(up, "policy_prev", None) == Severity.DUSUK)
    check("K4: Event.model_dump() ANAHTARLARI degismedi (yeni alanlar sizmaz)",
          set(up.model_dump()) == {"time", "end_time", "event", "severity", "category",
                                   "bbox", "region"}, str(sorted(up.model_dump())))
    res = AnalysisResult(summary="ozet", events=out["events"],
                         risk=RiskAssessment(level=Severity.YUKSEK, rationale="r"),
                         actions=[Action(action="Ekip gönder", priority=Severity.YUKSEK)])
    d = res.to_sartname_dict()
    check("to_sartname_dict anahtarlari {summary, events[{time,event}], risk, actions}",
          set(d) == {"summary", "events", "risk", "actions"}
          and d["events"] == [{"time": "00:03", "event": "Forklift aşırı yük taşıyor"}]
          and d["risk"] == "Yüksek" and d["actions"] == ["Ekip gönder"], str(d))
    check("to_sartname_dict JSON-serilestirilebilir", isinstance(json.dumps(d, ensure_ascii=False), str))
restore()


# =====================================================================
print("\n=== (6) SEVK KAPISI: severity yukselince act tetiklenebilir hale geliyor mu ===")
# =====================================================================
DISPATCH_PAYLOAD = '{"calls":[{"function":"guvenlik_ekibi_uyar","args":{"konum":"saha","sebep":"ihlal"}}]}'


def _pipeline(policy_text, verdict_payload, *, dispatch=False, model_risk=Severity.DUSUK):
    """policy_gate -> reason -> act zincirini SAHTE VLM ile uctan uca kosturur."""
    with policy_cfg(facility_policy=policy_text, policy_dispatch=dispatch):
        st = state([ev("Forklift aşırı yük taşıyor")])
        use(FakeVLM(verdict_payload))
        st.update(G.policy_gate(st))
        use(FakeVLM(json.dumps({"summary": "ozet",
                                "risk": {"level": model_risk.value, "rationale": "r"},
                                "actions": []}, ensure_ascii=False)))
        st.update(G.reason(st))
        use(FakeVLM(DISPATCH_PAYLOAD))
        st.update(G.act(st))
    return st


V_IHLAL = verdict_json([{"no": 1, "kural": "R1", "karar": "IHLAL", "kanit": "aşırı yük taşıyor"}])
P_SEVKSIZ = "Yük taşıma araçları beyan edilen yük sınırını aşamaz | | Yüksek"
P_SEVKLI = "Yük taşıma araçları beyan edilen yük sınırını aşamaz | | Yüksek | sevk"

st = _pipeline(P_SEVKSIZ, V_IHLAL)
check("RISK ZINCIRE AKTI: Dusuk olay -> politika Yuksek -> genel RISK Yüksek",
      st["risk"].level == Severity.YUKSEK, st["risk"].level.value)
check("K3: policy_dispatch=False iken triggered_functions BOS (sevk yolu kapali)",
      st["triggered_functions"] == [], str(st["triggered_functions"]))
check("K3: risk_from_policy_only bayragi set edildi (3. terim maskelendi)",
      st.get("risk_from_policy_only") is True)
check("K5: sevk yolunun neden kapali oldugu karar-izinde",
      any("SEVK yolu kapali" in t for t in st["trace"]))
check("confirm-then-act aksiyonu operatore sunuldu (yol acik birakildi)",
      any("politika ihlali" in a.action and "teyidi" in a.action for a in st["actions"]),
      str([a.action for a in st["actions"]]))

st = _pipeline(P_SEVKLI, V_IHLAL, dispatch=True)
check("B2 kolu: kuralda 'sevk' + policy_dispatch=True -> operasyonel cagri TETIKLENIR",
      st["triggered_functions"] == ["guvenlik_ekibi_uyar"], str(st["triggered_functions"]))

st = _pipeline(P_SEVKSIZ, V_IHLAL, dispatch=True)
check("policy_dispatch=True ama kuralda 'sevk' YOK -> sevk YOK (kural-basi yetki)",
      st["triggered_functions"] == [])

st = _pipeline(P_SEVKSIZ, V_IHLAL, model_risk=Severity.KRITIK)
check("model KENDI basina Yuksek+ risk verdiyse maske UYGULANMAZ (sevk eskisi gibi acilir)",
      st.get("risk_from_policy_only") is False and st["triggered_functions"] == ["guvenlik_ekibi_uyar"],
      str(st["triggered_functions"]))
restore()


# =====================================================================
print("\n=== (7) ONBELLEK / REEXAMINE-RUTIN / K1 GREP ===")
# =====================================================================
policy.clear_cache()
sev = Severity.YUKSEK


def _parse_once(_):
    return len(policy.parse_policy(ORNEK_POLITIKA, sev, 8))


with ThreadPoolExecutor(max_workers=8) as pool:
    lens = list(pool.map(_parse_once, range(32)))
check("T12 ONBELLEK: 32 paralel cagri -> AYRISTIRMA yalniz 1 kez, sonuc tutarli",
      policy.PARSE_STATS["parse"] == 1 and set(lens) == {4},
      f"parse={policy.PARSE_STATS}, lens={set(lens)}")

rules = policy.parse_policy(ORNEK_POLITIKA, sev, 8)
check("kural ayristirma: 4 madde, 2. maddede 'sevk' yetkisi, hepsi beyan=Yüksek",
      len(rules) == 4 and rules[1].sevk is True and rules[0].sevk is False
      and all(r.severity == Severity.YUKSEK for r in rules)
      and rules[0].uygun == "yürüyüş yolu içinde kalmak", str(rules[:2]))

with policy_cfg(facility_policy=ORNEK_POLITIKA):
    e_rutin = ev("Forklift aşırı yük taşıyor")
    vlm = use(FakeVLM(verdict_json([{"no": 1, "kural": "R3", "karar": "IHLAL",
                                     "kanit": "aşırı yük taşıyor"}])))
    out = G.policy_gate(state([e_rutin], reexamine_routine=[policy.event_key(e_rutin)]))
    check("T13 REEXAMINE-RUTIN: 'RUTIN' isaretli olay ADAY ALINMAZ (cagri bile yok)",
          vlm.calls == 0 and "events" not in out)
restore()

# T14 — K1 GREP TESTI: kodda ve promptta tesise-ozgu TEK terim gecmez
YASAKLI = ["forklift", "pano", "panel", "yürüyüş yolu", "yuruyus yolu", "yürüme yolu",
           "yurume yolu", "aşırı yük", "asiri yuk", "kapasite", "yetkisiz", "baret",
           "yangın", "yangin", "duman"]
_src = open(policy.__file__, encoding="utf-8").read()
_n_src = policy._norm(_src)
_n_prompt = policy._norm(prompts.POLICY_ADJUDICATE_INSTRUCTION)
hits_src = [t for t in YASAKLI if policy._norm(t) in _n_src]
hits_prompt = [t for t in YASAKLI if policy._norm(t) in _n_prompt]
check("T14/K1: policy.py icinde tesise-ozgu ALAN TERIMI YOK", not hits_src, str(hits_src))
check("T14/K1: POLICY_ADJUDICATE_INSTRUCTION icinde ALAN TERIMI YOK", not hits_prompt, str(hits_prompt))

# TR-normalizasyon: 'İşçi'.lower() tuzagi bu modulun kapilarinda YOK.
# (Ham lower() 'i' + U+0307 uretir -> "işçi" alt-dizgi eslesmesi SESSIZCE kacar.)
check("ham str.lower() TR tuzagi GERCEK ('işçi' alt-dizgisi 'İşçi'.lower() icinde YOK)",
      "işçi" not in "İşçi".lower(), repr("İşçi".lower()))
check("_norm TR-guvenli: 'İşçi' -> 'isci'", policy._norm("İşçi") == "isci",
      repr(policy._norm("İşçi")))
check("_norm: 'İ' + combining sorunu cozuldu", "isci" in policy._norm("İŞÇİ ilerliyor"))
check("evidence_ok TR metinde calisir",
      policy.evidence_ok("aşırı yük taşıyor", "Forklift AŞIRI YÜK taşıyor")
      and not policy.evidence_ok("aşırı yük taşıyor", "İşçi yürüyor"))


# =====================================================================
print("\n=== (8) UCTAN-UCA: gercek LangGraph grafigi (kanal propagasyonu) ===")
# =====================================================================
_O = {"ingest": G.ingest, "perceive": G.perceive, "reexamine": G.reexamine}


def _fake_ingest(s):
    return {"segments": [], "video_info": None, "scene_cuts": [], "trace": s.get("trace", [])}


def _fake_perceive(s):
    return {"events": [ev("Forklift aşırı yük taşıyor")], "trace": s.get("trace", [])}


class _RouteVLM:
    """Dugume gore farkli JSON doner (policy / reason / act)."""

    def __init__(self):
        self.calls = 0

    def gorev(self, _gorev: str):
        return self

    def chat(self, messages, **kw):
        self.calls += 1
        p = messages[-1]["content"]
        if "POLİTİKA MADDELERİ" in p:
            return V_IHLAL
        if "\"calls\"" in p or "FONKSİYONLAR" in p:
            return DISPATCH_PAYLOAD
        return json.dumps({"summary": "ozet", "risk": {"level": "Düşük", "rationale": "r"},
                           "actions": []}, ensure_ascii=False)

    def analyze_frames(self, frames, prompt, **kw):
        return "BELIRSIZ"


G.ingest, G.perceive = _fake_ingest, _fake_perceive
try:
    with policy_cfg(facility_policy=P_SEVKSIZ, policy_dispatch=False, adaptive_reexamine=False):
        rv = use(_RouteVLM())
        res = G.build_graph().invoke({"video_path": "sahte.mp4", "trace": []})["result"]
        check("gercek grafik: policy_gate -> reason -> act zinciri kosuyor (kanal DUSMEDI)",
              res.events[0].severity == Severity.YUKSEK and res.risk.level == Severity.YUKSEK,
              f"sev={res.events[0].severity.value}, risk={res.risk.level.value}")
        check("gercek grafik: K3 sevk kapisi KAPALI (triggered_functions bos)",
              res.triggered_functions == [], str(res.triggered_functions))
        d = res.to_sartname_dict()
        check("gercek grafik: cikti sozlesmesi saglam",
              set(d) == {"summary", "events", "risk", "actions"} and d["risk"] == "Yüksek")
    with policy_cfg(facility_policy="", adaptive_reexamine=False):
        rv = use(_RouteVLM())
        res = G.build_graph().invoke({"video_path": "sahte.mp4", "trace": []})["result"]
        check("gercek grafik + BOS politika: severity/risk Dusuk kalir (K2 uctan-uca)",
              res.events[0].severity == Severity.DUSUK and res.risk.level == Severity.DUSUK
              and res.triggered_functions == []
              and not any(t.startswith("policy") for t in res.decision_trace),
              f"sev={res.events[0].severity.value}, risk={res.risk.level.value}")
except Exception:
    traceback.print_exc()
    FAILS.append("uctan-uca grafik")
finally:
    G.ingest, G.perceive, G.reexamine = _O["ingest"], _O["perceive"], _O["reexamine"]
    restore()

G.build_graph()
check("build_graph() (gercek dugumlerle) derleniyor", True)


# =====================================================================
# ADVERSARYEL DENETIM REGRESYONLARI (fiilen uretilmis kusurlar)
# =====================================================================
print("\n=== ADV-1: karar ayristirma — OLUMSUZLANMIS ifade IHLAL sayilmamali ===")
# KUSUR (olculdu): `_norm_karar` ham alt-dizgi ariyordu; model kapali kumeden sapip
# "ihlal yok" / "İhlal edilmemiştir" yazinca karar IHLAL okunuyordu ve 4 NORMAL olay
# metni Düşük->Yüksek YUKSELIYORDU. Onarim: karar sozcugune bagli olumsuzlama muhafizi.
_KARAR_MATRIS = [
    ("IHLAL", "IHLAL"), ("ihlal", "IHLAL"), ("  IHLAL  ", "IHLAL"), ("violation", "IHLAL"),
    ("UYGUN", "UYGUN"), ("BELIRSIZ", "BELIRSIZ"), ("unclear", "BELIRSIZ"),
    # olumsuzlanmis -> ASLA yukseltme (FAIL-CLOSED)
    ("ihlal yok", "BELIRSIZ"), ("İhlal edilmemiştir", "BELIRSIZ"),
    ("ihlal tespit edilmedi", "BELIRSIZ"), ("ihlal bulunmuyor", "BELIRSIZ"),
    ("İHLAL SAPTANMADI", "BELIRSIZ"), ("hiçbir ihlal görülmedi", "BELIRSIZ"),
    ("ihlal değil", "BELIRSIZ"), ("no violation", "BELIRSIZ"), ("not a violation", "BELIRSIZ"),
    # gecerli karar + parantezli/tireli gerekce -> ASIRI ENGELLENMEMELI
    ("IHLAL (koruyucu ekipman yok)", "IHLAL"), ("IHLAL - ekipman yok", "IHLAL"),
    ("IHLAL: R1", "IHLAL"),
    # str-disi/bozuk degerler -> cokme yok, FAIL-CLOSED
    (None, "BELIRSIZ"), (123, "BELIRSIZ"), ([1, 2], "BELIRSIZ"), ({"a": 1}, "BELIRSIZ"),
]
for _raw, _exp in _KARAR_MATRIS:
    _got = policy._norm_karar(_raw)
    check(f"_norm_karar({_raw!r}) -> {_exp}", _got == _exp, _got)

# uctan-uca: olumsuz karar veren model NORMAL metinleri yukseltmemeli
_NORMAL_METINLER = [
    "İşçi yürüyor", "Forklift boş hâlde duruyor", "Operatör panele bakıyor",
    "İki kişi konuşuyor", "Yük indiriliyor", "İşçi işaretli yürüyüş yolunda ilerliyor",
    "Elektrik panosunun kapağı kapalı durumda", "Yetkili teknisyen bakım yapıyor",
    "Depoda rutin malzeme taşıma işlemi sürüyor", "Vardiya değişimi için personel toplanıyor",
    "Forklift park alanına yanaşıyor", "Kamera görüş alanında hareket yok",
]
_norm_evs = [Event(time="00:0%d" % (i % 10), event=t, severity=Severity.DUSUK,
                   category=EventCategory.ANOMALI) for i, t in enumerate(_NORMAL_METINLER)]


class _NegVLM(FakeVLM):
    """Kapali kumeden SAPIP 'ihlal yok' yazan model (her adaya SADIK kanit verir)."""

    def chat(self, messages, **kw):
        self.calls += 1
        p = messages[-1]["content"]
        obs = re.findall(r"^\s*(\d+)\)\s*\[[^\]]*\]\s*(.+)$", p, re.M)
        return json.dumps({"sonuc": [{"no": int(n), "kural": "R1", "karar": "ihlal yok",
                                      "kanit": " ".join(t.split()[:3])} for n, t in obs]},
                          ensure_ascii=False)


with policy_cfg(facility_policy=P_SEVKSIZ):
    use(_NegVLM())
    _out = G.policy_gate({"events": list(_norm_evs), "trace": []})
    _after = _out.get("events", _norm_evs)
    check("ADV-1 uctan-uca: 'ihlal yok' diyen model 12 NORMAL metnin HICBIRINI yukseltmez",
          all(a.severity == b.severity for a, b in zip(_after, _norm_evs)),
          str([(a.event, a.severity.value) for a, b in zip(_after, _norm_evs)
               if a.severity != b.severity]))
    restore()

print("\n=== ADV-2: YINELENEN karar numarasi -> o aday tamamen dusurulur ===")
# KUSUR (olculdu): model ayni `no` icin birden fazla karar dondurunce "ilk gelen kazaniyordu"
# ve baska bir gozlemin karari adaya baglanabiliyordu. Onarim: yinelenen no FAIL-CLOSED.
_v = policy.parse_verdicts(
    json.dumps({"sonuc": [
        {"no": 1, "kural": "R1", "karar": "IHLAL", "kanit": "aaa bbb"},
        {"no": 1, "kural": "R1", "karar": "IHLAL", "kanit": "ccc ddd"},
        {"no": 2, "kural": "R1", "karar": "IHLAL", "kanit": "eee fff"},
    ]}), 2, {"R1"})
check("ADV-2: yinelenen no=1 dusuruldu, no=2 korundu", set(_v) == {2}, str(sorted(_v)))


class _DupVLM(FakeVLM):
    """Her karari no=1 ile dondurup ayni adayi tekrar tekrar isaretleyen bozuk model."""

    def chat(self, messages, **kw):
        self.calls += 1
        p = messages[-1]["content"]
        obs = re.findall(r"^\s*(\d+)\)\s*\[[^\]]*\]\s*(.+)$", p, re.M)
        return json.dumps({"sonuc": [{"no": 1, "kural": "R1", "karar": "IHLAL",
                                      "kanit": " ".join(t.split()[:3])} for _n, t in obs]},
                          ensure_ascii=False)


with policy_cfg(facility_policy=P_SEVKSIZ):
    use(_DupVLM())
    _evs = [Event(time="00:01", event="Forklift aşırı yük taşıyor", severity=Severity.DUSUK,
                  category=EventCategory.ANOMALI),
            Event(time="00:05", event="İşçi yürüyüş yolu dışında ilerliyor",
                  severity=Severity.DUSUK, category=EventCategory.ANOMALI)]
    _snap = [e.model_dump() for e in _evs]
    _out = G.policy_gate({"events": list(_evs), "trace": []})
    check("ADV-2 uctan-uca: yinelenen numaralamada HICBIR yukseltme yok",
          all(a.model_dump() == b for a, b in zip(_out.get("events", _evs), _snap)))
    restore()

print("\n=== ADV-3: risk nesnesindeki `policy_only` yedek bayragi dil-guardinda kaybolmamali ===")
# KUSUR: dil-safligi guardi RiskAssessment'i YENIDEN KURUYOR ve ek oznitelig dusuruyordu ->
# act()'teki yedek maske yolu o dalda olu kaliyordu. Onarim: model_copy ile yeniden kurma.
_r = RiskAssessment(level=Severity.YUKSEK, rationale="a").model_copy(update={"policy_only": True})
_r2 = _r.model_copy(update={"rationale": "b"})
check("ADV-3: risk.model_copy(rationale) policy_only bayragini KORUR",
      getattr(_r2, "policy_only", False) is True and _r2.level == Severity.YUKSEK)
check("ADV-3: policy_only sema alani DEGIL (model_dump'a sizmaz)",
      set(_r2.model_dump()) == {"level", "rationale"}, str(sorted(_r2.model_dump())))

print("\n" + "=" * 46)
print("TUM TESTLER GECTI" if not FAILS else f"{len(FAILS)} TEST BASARISIZ: {FAILS}")
sys.exit(1 if FAILS else 0)
