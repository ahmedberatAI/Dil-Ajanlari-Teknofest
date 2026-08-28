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
    ("Kişi panikle koşup dengesini kaybetti", "olağandışı kişi hareketi"),
    ("İki çalışan kavga ediyor", "şiddet/silah"),
    ("Forklift devrildi", "çarpışma/devrilme"),
    ("Yetkisiz kişi kısıtlı bölgeye girdi", "yetkisiz giriş/müdahale"),
    ("İşçide KKD eksikliği var", "KKD eksikliği"),
    ("İşçi askıda yük altında düşme bölgesinde", "askıda yük/düşme bölgesi"),
):
    check(f"{family}: yakalanir", family in G._claim_families(text))
check("yaya yolu ihlali yetkisiz-erisim sayilmaz",
      "yetkisiz giriş/müdahale" not in G._claim_families("Yaya yolu ihlali"))
check("onem etiketi Dusuk, dusme iddiasi sayilmaz",
      "düşme/yaralı kişi" not in G._claim_families("Önem derecesi: Düşük"))
check("dusunmek, dusme iddiasi sayilmaz",
      "düşme/yaralı kişi" not in G._claim_families("Kişi ne yapacağını düşünüyor"))

print("\n=== GENISLETILMIS FIZIKSEL AILELER BAYRAKLI ===")
old_decomp = G.settings.atomic_claim_decomposition
old_extended = G.settings.atomic_extended_families
try:
    G.settings.atomic_claim_decomposition = False
    G.settings.atomic_extended_families = False
    check("bayrak kapaliyken yeni yük ailesi davranışı değiştirmez",
          "kontrolsüz yük/çökme" not in G._claim_families("Raf devrilerek yere düştü"))
    G.settings.atomic_claim_decomposition = True
    G.settings.atomic_extended_families = True
    check("kontrolsüz yük/çökme ayrı aile olarak yakalanır",
          "kontrolsüz yük/çökme" in G._claim_families("Raf devrilerek yere düştü"))
    check("yük devrilmesi açık çarpışma yoksa çarpışma atomu istemez",
          "çarpışma/devrilme" not in G._claim_families("Ağır yük devrilerek yere düştü"))
    check("makineye sıkışma ayrı aile olarak yakalanır",
          "makineye sıkışma/ezilme" in G._claim_families("İşçinin giysisi makineye takılıp sıkıştı"))
finally:
    G.settings.atomic_claim_decomposition = old_decomp
    G.settings.atomic_extended_families = old_extended


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
old_policy = G.settings.narrative_event_policy
old_atomic = G.settings.atomic_claim_guard
try:
    G.settings.claim_guard = True
    G.settings.atomic_claim_guard = False
    G.settings.narrative_event_policy = "all"
    kept, note = G._guard_narrative_claims(verifier, _Segment(), events)
finally:
    G.settings.claim_guard = old_claim
    G.settings.atomic_claim_guard = old_atomic
    G.settings.narrative_event_policy = old_policy
check("HAYIR denilen Dusuk duman iddiasi tamamen silinir", events[0] not in kept)
check("dogrulama hatasi fail-closed: yarali iddiasi silinir", events[1] not in kept)
check("somut alarm iddiasi olmayan rutin olay korunur", kept == [events[2]])
check("yalniz iki somut iddia icin iki cagri", verifier.calls == 2)
check("redler karar izine acikca yazilir", bool(note and "2 desteklenmeyen" in note))


print("\n=== ISG-ODAKLI SERBEST ANLATI POLITIKASI ===")
policy_events = [
    Event(time="00:01", event="Raf arkasında kırmızı bir nesne anlık belirdi",
          severity=Severity.ORTA, category=EventCategory.ANOMALI),
    Event(time="00:02", event="Personel aceleci hareket edip dengesini kaybetti",
          severity=Severity.ORTA, category=EventCategory.ANOMALI),
    Event(time="00:03", event="Forklift rafa çarparak rafı devirdi",
          severity=Severity.YUKSEK, category=EventCategory.KAZA),
]
policy_verifier = _Verifier(["EVET. Açık temas ve devrilme görülüyor."])
old_claim = G.settings.claim_guard
old_policy = G.settings.narrative_event_policy
old_atomic = G.settings.atomic_claim_guard
try:
    G.settings.claim_guard = True
    G.settings.atomic_claim_guard = False
    G.settings.narrative_event_policy = "isg_grounded"
    policy_kept, policy_note = G._guard_narrative_claims(
        policy_verifier, _Segment(), policy_events)
finally:
    G.settings.claim_guard = old_claim
    G.settings.atomic_claim_guard = old_atomic
    G.settings.narrative_event_policy = old_policy
check("ailesiz görsel değişim alarm değildir", policy_events[0] not in policy_kept)
check("tek başına muğlak kişi hareketi alarm değildir", policy_events[1] not in policy_kept)
check("doğrulanmış fiziksel çarpışma korunur", policy_kept == [policy_events[2]])
check("politika yalnız doğrulanabilir fiziksel aile için VLM çağırır",
      policy_verifier.calls == 1)
check("politika redleri karar izine yazılır",
      bool(policy_note and "2 desteklenmeyen" in policy_note))

print("\n=== KKD YALNIZ ACIK TESIS BEYANIYLA OLAYDIR ===")
kkd_event = Event(time="00:06", event="Personelin güvenlik baretini takmaması",
                  severity=Severity.ORTA, category=EventCategory.GUVENLIK)
old_claim = G.settings.claim_guard
old_atomic = G.settings.atomic_claim_guard
old_policy = G.settings.narrative_event_policy
old_rules = G.settings.facility_rules
old_facility_policy = G.settings.facility_policy
old_ppe = G.settings.ppe_detection
old_kits = G.settings.ppe_kits
try:
    G.settings.claim_guard = True
    G.settings.atomic_claim_guard = False
    G.settings.narrative_event_policy = "isg_grounded"
    G.settings.facility_rules = ""
    G.settings.facility_policy = ""
    G.settings.ppe_detection = False
    G.settings.ppe_kits = "baret,yelek"
    no_policy_v = _Verifier([])
    no_policy_kept, no_policy_note = G._guard_narrative_claims(
        no_policy_v, _Segment(), [kkd_event])
    check("varsayılan ppe_kits tek başına KKD politikası değildir",
          not no_policy_kept and no_policy_v.calls == 0)
    check("KKD beyan yokluğu karar izine yazılır",
          bool(no_policy_note and "KKD_BEYANI_YOK" in no_policy_note))

    G.settings.facility_rules = "Üretim alanında baret zorunludur"
    declared_v = _Verifier(["EVET. Baret açıkça eksik."])
    declared_kept, _ = G._guard_narrative_claims(
        declared_v, _Segment(), [kkd_event])
    check("açık baret zorunluluğu ve görsel destek olayı korur",
          declared_kept == [kkd_event] and declared_v.calls == 1)

    G.settings.facility_rules = "Bu alanda baret zorunlu değildir"
    negative_v = _Verifier([])
    negative_kept, _ = G._guard_narrative_claims(
        negative_v, _Segment(), [kkd_event])
    check("olumsuz kural baret zorunluluğu sayılmaz",
          not negative_kept and negative_v.calls == 0)

    G.settings.facility_rules = "Baret zorunludur"
    mixed = Event(time="00:07", event="Baret ve koruyucu eldiven eksik",
                  severity=Severity.ORTA, category=EventCategory.GUVENLIK)
    mixed_v = _Verifier([])
    mixed_kept, _ = G._guard_narrative_claims(mixed_v, _Segment(), [mixed])
    check("spekte olmayan eldiven iddiası birleşik KKD olayından sızmaz",
          not mixed_kept and mixed_v.calls == 0)
finally:
    G.settings.claim_guard = old_claim
    G.settings.atomic_claim_guard = old_atomic
    G.settings.narrative_event_policy = old_policy
    G.settings.facility_rules = old_rules
    G.settings.facility_policy = old_facility_policy
    G.settings.ppe_detection = old_ppe
    G.settings.ppe_kits = old_kits

print("\n=== ATOMIK KAPIDA YARDIMCI HAREKET AILESI ANA OLAYI VETO ETMEZ ===")
karma = Event(time="00:04",
              event="Forklift rafa çarptı, yakındaki kişi ani kaçınma hareketi yaptı",
              severity=Severity.KRITIK, category=EventCategory.KAZA)
atomik_verifier = _Verifier(["IKI_AYRI_VARLIK", "DOGRUDAN_TEMAS_VE_SONUC"])
old_claim = G.settings.claim_guard
old_policy = G.settings.narrative_event_policy
old_atomic = G.settings.atomic_claim_guard
try:
    G.settings.claim_guard = True
    G.settings.atomic_claim_guard = True
    G.settings.narrative_event_policy = "isg_grounded"
    atomik_kept, _atomik_note = G._guard_narrative_claims(
        atomik_verifier, _Segment(), [karma])
finally:
    G.settings.claim_guard = old_claim
    G.settings.atomic_claim_guard = old_atomic
    G.settings.narrative_event_policy = old_policy
check("doğrulanmış çarpışma yardımcı kaçınma ifadesine rağmen korunur",
      atomik_kept == [karma])
check("yalnız çarpışmanın iki fiziksel atomu sorulur", atomik_verifier.calls == 2)

print("\n=== KARMA IDDIADA DESTEKLI ATOM KORUNUR ===")
partial = Event(time="00:05",
                event="Sürücü araçtan yere düştü ve araç duvara çarptı",
                severity=Severity.KRITIK, category=EventCategory.KAZA)
# düşme SUPPORTED; çarpışma REFUTED
partial_verifier = _Verifier([
    "KISI_VAR", "DUSME_GECISI",
    "AYRI_HEDEF_YOK", "GORUNMUYOR",
])
old_claim = G.settings.claim_guard
old_policy = G.settings.narrative_event_policy
old_atomic = G.settings.atomic_claim_guard
old_decomp = G.settings.atomic_claim_decomposition
try:
    G.settings.claim_guard = True
    G.settings.atomic_claim_guard = True
    G.settings.atomic_claim_decomposition = True
    G.settings.narrative_event_policy = "isg_grounded"
    partial_kept, partial_note = G._guard_narrative_claims(
        partial_verifier, _Segment(), [partial])
finally:
    G.settings.claim_guard = old_claim
    G.settings.atomic_claim_guard = old_atomic
    G.settings.atomic_claim_decomposition = old_decomp
    G.settings.narrative_event_policy = old_policy
check("reddedilen çarpışma nesri korunmaz",
      len(partial_kept) == 1 and "çarpışma" not in partial_kept[0].event.lower())
check("desteklenen düşme sabit şablonla korunur",
      len(partial_kept) == 1 and "Kişi düşmesi" in partial_kept[0].event)
check("kısmi karar izde görünür", bool(partial_note and "atomik-kısmi" in partial_note))


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

print(f"\nkalan={len(fails)}")
raise SystemExit(1 if fails else 0)
