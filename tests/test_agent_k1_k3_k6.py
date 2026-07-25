"""K1 / K3 / K6 birim testleri (denetim kusurlari).

  K1  act() operasyon-kaydi YARIS DURUMU  (n_samples>1 paralel grafik kosusu)
  K3  act() dispatch'inin SESSIZCE DUSMESI (pydantic argüman hatasi)
  K6  perceive / reexamine / finalize dugum-seviyesi try/except

VLM/GPU GEREKTIRMEZ: tek VLM temas noktasi (_get_vlm) sahte bir istemciyle degistirilir.

Kosum:  python tests/test_agent_k1_k3_k6.py       (repo kokunden)
"""
from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import mock_functions as MF
from dilajan.agent import graph as G
from dilajan.schema import (
    Action,
    AnalysisResult,
    Event,
    EventCategory,
    RiskAssessment,
    Severity,
)

FAILS: list = []
_local = threading.local()


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  [OK]   " if cond else "  [FAIL] ") + name + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


class FakeVLM:
    """act()'in kullandigi tek arayuz: .chat(messages, ...) -> JSON metni."""

    def __init__(self, payload: str):
        self.payload = payload

    def chat(self, messages, **kw):
        time.sleep(0.005)  # thread'lerin gercekten ic ice gecmesi icin
        return self.payload


def _state(events, risk_level=Severity.KRITIK) -> dict:
    return {"events": events, "risk": RiskAssessment(level=risk_level, rationale="test"), "trace": []}


def _kritik(text: str = "kritik olay", region=None) -> list:
    return [Event(time="00:01", event=text, severity=Severity.KRITIK,
                  category=EventCategory.KAZA, region=region)]


_ORIG = {"_get_vlm": G._get_vlm, "ingest": G.ingest, "perceive": G.perceive, "reason": G.reason}


# =====================================================================
# K1 — paralel act() cagrilarinda operasyon-kaydi izolasyonu
# =====================================================================
print("\n=== K1: act() operasyon-kaydi yaris durumu ===")

PLAN = {
    "A": ('{"calls":[{"function":"saglik_ekibi_yonlendir","args":{"konum":"A-depo","aciliyet":"Kritik"}}]}',
          ["saglik_ekibi_yonlendir"]),
    "B": ('{"calls":[{"function":"guvenlik_ekibi_uyar","args":{"konum":"B-kapi","sebep":"B-kavga"}},'
          '{"function":"yonetici_bilgilendir","args":{"mesaj":"B-olayi"}}]}',
          ["guvenlik_ekibi_uyar", "yonetici_bilgilendir"]),
    "C": ('{"calls":[{"function":"acil_durdurma_tetikle","args":{"ekipman":"C-forklift"}},'
          '{"function":"alan_guvenligini_sagla","args":{"alan":"C-saha"}},'
          '{"function":"olay_kaydi_olustur","args":{"ozet":"C-ozet","risk":"Kritik"}}]}',
          ["acil_durdurma_tetikle", "alan_guvenligini_sagla", "olay_kaydi_olustur"]),
}

G._get_vlm = lambda: FakeVLM(PLAN[_local.tag][0])


def _run_act(tag):
    _local.tag = tag
    return tag, G.act(_state(_kritik(f"{tag} kritik olay")))


tags = [t for _ in range(8) for t in ("A", "B", "C")]  # 24 kosu / 12 thread
with ThreadPoolExecutor(max_workers=12) as pool:
    results = list(pool.map(_run_act, tags))

bad = [(t, o["triggered_functions"]) for t, o in results if o["triggered_functions"] != PLAN[t][1]]
check("24 paralel act(): her kosu YALNIZ kendi cagrilarini gorur", not bad, f"sapmalar={bad[:3]}")

# args degerleri kosu etiketini tasiyor -> capraz sizinti dogrudan yakalanir
leak = [(t, e) for t, o in results for e in o["action_log"] if t not in str(e.get("args", ""))]
check("action_log kayitlari dogru kosuya ait (capraz sizinti yok)", not leak, str(leak[:2]))
check("action_log uzunlugu triggered_functions ile tutarli",
      all(len(o["action_log"]) == len(o["triggered_functions"]) for _, o in results))


def _kayitno_probe(_):
    G._get_vlm = lambda: FakeVLM(
        '{"calls":[{"function":"olay_kaydi_olustur","args":{"ozet":"tek","risk":"Kritik"}}]}')
    o = G.act(_state(_kritik()))
    return o["action_log"][0]["result"] if o["action_log"] else "YOK"


with ThreadPoolExecutor(max_workers=8) as pool:
    nos = set(pool.map(_kayitno_probe, range(16)))
check("paralel kosularda olay kayit-no DETERMINISTIK (hepsi OLY-0001)",
      nos == {"Olay kaydı OLY-0001 oluşturuldu."}, str(sorted(nos)))


# --- mock_functions kayit listesi baglam-yerel mi ---
def _probe(tag):
    MF.reset_log()
    for i in range(20):
        MF.yonetici_bilgilendir.invoke({"mesaj": f"{tag}-{i}"})
        time.sleep(0.001)
    return tag, [e["args"]["mesaj"].split("-")[0] for e in MF.get_log()]


with ThreadPoolExecutor(max_workers=6) as pool:
    probes = list(pool.map(_probe, list("PQRSTU")))
check("mock_functions kaydi thread-yerel (6 thread x 20 cagri)",
      all(set(seen) == {tag} and len(seen) == 20 for tag, seen in probes),
      str([(t, len(s), sorted(set(s))) for t, s in probes]))

# --- ESKI tasarimin ayni yuk altinda GERCEKTEN bozuldugu (regresyon kaniti) ---
_OLD_LOG: list = []


def _old_act(tag):
    _OLD_LOG.clear()                                     # eski: reset_log() -> global clear
    for fname in PLAN[tag][1]:
        time.sleep(0.001)
        _OLD_LOG.append({"function": fname})             # eski: global append
    time.sleep(0.001)
    return tag, [e["function"] for e in _OLD_LOG]        # eski: global okuma


with ThreadPoolExecutor(max_workers=12) as pool:
    old = list(pool.map(_old_act, tags))
old_bad = [t for t, g in old if g != PLAN[t][1]]
check(f"REGRESYON KANITI: eski modul-globali tasarimi ayni yukte bozuluyor ({len(old_bad)}/{len(old)})",
      len(old_bad) > 0, "yaris yeniden uretilemedi (test zayif)")

# --- OPERATION_LOG geriye-uyumu (app.py / report.py / benchmark kirilmasin) ---
MF.reset_log()
MF.saglik_ekibi_yonlendir.invoke({"konum": "x", "aciliyet": "Orta"})
check("OPERATION_LOG len/iter/getitem/slice/bool geriye-uyumlu",
      len(MF.OPERATION_LOG) == 1
      and MF.OPERATION_LOG[0]["function"] == "saglik_ekibi_yonlendir"
      and [e["function"] for e in MF.OPERATION_LOG] == ["saglik_ekibi_yonlendir"]
      and list(MF.OPERATION_LOG) == MF.OPERATION_LOG[0:1]
      and bool(MF.OPERATION_LOG) is True)
MF.OPERATION_LOG.clear()
check("OPERATION_LOG.clear() geriye-uyumlu", len(MF.OPERATION_LOG) == 0)


# =====================================================================
# K3 — yanlis/eksik argümanla cagri SESSIZCE DUSMEMELI
# =====================================================================
print("\n=== K3: act() dispatch'inin sessizce dusmesi ===")


def act_with(payload, events=None, risk=Severity.KRITIK):
    G._get_vlm = lambda: FakeVLM(payload)
    ev = events if events is not None else [
        Event(time="00:03", event="İşçi yere yığıldı, hareketsiz", severity=Severity.KRITIK,
              category=EventCategory.SAGLIK, region="alt sol")]
    return G.act(_state(ev, risk))


out = act_with('{"calls":[{"function":"saglik_ekibi_yonlendir","args":{"yer":"depo"}}]}')
a = out["action_log"][0]["args"] if out["action_log"] else {}
check("yanlis arg-adi {'yer':'depo'} -> cagri GERCEKLESTI",
      out["triggered_functions"] == ["saglik_ekibi_yonlendir"], str(out["triggered_functions"]))
check("  'yer' -> 'konum' eslendi", a.get("konum") == "depo", str(a))
check("  eksik 'aciliyet' olay severity'siyle dolduruldu", a.get("aciliyet") == "Kritik", str(a))
check("  onarim karar-izine (trace) yazildi", any("onarildi" in t for t in out["trace"]))

out = act_with('{"calls":[{"function":"guvenlik_ekibi_uyar","args":{}}]}')
a = out["action_log"][0]["args"] if out["action_log"] else {}
check("bos args -> cagri GERCEKLESTI", out["triggered_functions"] == ["guvenlik_ekibi_uyar"])
check("  eksik 'konum' olay bolgesinden dolduruldu", a.get("konum") == "alt sol", str(a))
check("  eksik 'sebep' olay metninden dolduruldu", "yığıl" in str(a.get("sebep", "")), str(a))

out = act_with('{"calls":[{"function":"acil_durdurma_tetikle",'
               '"args":{"makine":"forklift","oncelik":"yuksek","alakasiz":"x"}}]}')
a = out["action_log"][0]["args"] if out["action_log"] else {}
check("fazladan + yanlis anahtar -> cagri GERCEKLESTI",
      out["triggered_functions"] == ["acil_durdurma_tetikle"])
check("  'makine' -> 'ekipman' eslendi, fazlaliklar atildi", a == {"ekipman": "forklift"}, str(a))

out = act_with('{"calls":[{"function":"olay_kaydi_olustur","args":{"ozeti":"depoda kaza","rsk":"Kritik"}}]}')
a = out["action_log"][0]["args"] if out["action_log"] else {}
check("yazim hatali arg adlari (difflib) -> cagri GERCEKLESTI",
      out["triggered_functions"] == ["olay_kaydi_olustur"])
check("  'ozeti'->'ozet', 'rsk'->'risk'",
      a.get("ozet") == "depoda kaza" and a.get("risk") == "Kritik", str(a))

out = act_with('{"calls":[{"function":"yonetici_bilgilendir","args":"{\\"mesaj\\":\\"acil\\"}"}]}')
check("args sozluk yerine JSON METNI ise cozuluyor",
      out["triggered_functions"] == ["yonetici_bilgilendir"], str(out["triggered_functions"]))

out = act_with('{"calls":[{"function":"saglik_ekibi_yonlendirr","args":{"konum":"d","aciliyet":"Kritik"}}]}')
check("yakin-isimli (hatali) fonksiyon adi cozuluyor",
      out["triggered_functions"] == ["saglik_ekibi_yonlendir"], str(out["triggered_functions"]))

out = act_with('{"calls":[{"function":"uzay_gemisi_firlat","args":{"x":1}}]}')
check("gercekten bilinmeyen fonksiyon -> cagri yok AMA trace'te NET uyari",
      out["triggered_functions"] == [] and any("UYARI" in t for t in out["trace"]))


class _Boom:
    name = "patlayan_arac"
    args = {"konum": {"type": "string"}}
    args_schema = None

    def invoke(self, a):
        raise ValueError("her zaman patlar")


MF.TOOL_REGISTRY["patlayan_arac"] = _Boom()
try:
    out = act_with('{"calls":[{"function":"patlayan_arac","args":{"konum":"depo"}}]}')
    check("onarilamayan kalici hata -> SESSIZ degil, trace'te NET uyari",
          out["triggered_functions"] == []
          and any("ÇAĞRI YAPILAMADI" in t for t in out["trace"]),
          str([t for t in out["trace"] if t.startswith("act:")]))
finally:
    MF.TOOL_REGISTRY.pop("patlayan_arac", None)

# VARSAYILAN DAVRANIS: dogru argümanlarda hicbir onarim/degisiklik olmamali
out = act_with('{"calls":[{"function":"saglik_ekibi_yonlendir","args":{"konum":"Depo-2","aciliyet":"Yüksek"}},'
               '{"function":"olay_kaydi_olustur","args":{"ozet":"kaza","risk":"Kritik"}}]}')
check("dogru argümanlar -> onarim YOK, kayit icerigi eskisiyle ayni",
      out["triggered_functions"] == ["saglik_ekibi_yonlendir", "olay_kaydi_olustur"]
      and out["action_log"][0]["args"] == {"konum": "Depo-2", "aciliyet": "Yüksek"}
      and out["action_log"][0]["result"] == "Sağlık ekibi Depo-2 konumuna yönlendirildi (aciliyet: Yüksek)."
      and out["action_log"][1]["result"] == "Olay kaydı OLY-0002 oluşturuldu."   # 2. cagri (eski kodla ayni)
      and set(out["action_log"][0]) == {"function", "args", "result", "ts"}
      and not any("onarildi" in t for t in out["trace"]),
      str(out["action_log"]))

out = act_with('{"calls":[{"function":"yonetici_bilgilendir","args":{"mesaj":"x"}}]}',
               events=[Event(time="00:01", event="normal", severity=Severity.ORTA,
                             category=EventCategory.NORMAL)], risk=Severity.ORTA)
check("dispatch kapisi KORUNDU (Orta sinyal -> operasyonel cagri yok)",
      out["triggered_functions"] == [] and any("dispatch kapisi" in t for t in out["trace"]))


# =====================================================================
# K6 — dugum-seviyesi hata toleransi
# =====================================================================
print("\n=== K6: perceive / reexamine / finalize try/except ===")


class _BadSegment:
    index = 0
    start_str, end_str = "00:00", "00:05"

    @property
    def frames(self):
        raise RuntimeError("bozuk segment (simule)")


G._get_vlm = lambda: (_ for _ in ()).throw(RuntimeError("vLLM istemcisi kurulamadi (simule)"))
try:
    out = G.perceive({"segments": [_BadSegment()], "trace": []})
    ok = out.get("events") == [] and any("perceive: dugum hatasi" in t for t in out["trace"])
except Exception:
    ok = False
    traceback.print_exc()
check("perceive: hata halinde cokmez, trace'e not + bos olay listesi", ok)

evs = [Event(time="00:02", event="belirsiz durum", severity=Severity.ORTA, category=EventCategory.ANOMALI)]
try:
    out = G.reexamine({"events": evs, "segments": [], "trace": []})
    ok = (out["events"] == evs and out["reexamined"] is True
          and any("reexamine: dugum hatasi" in t for t in out["trace"]))
except Exception:
    ok = False
    traceback.print_exc()
check("reexamine: hata halinde olaylar DEGISMEDEN korunur + reexamined=True", ok)

G._get_vlm = _ORIG["_get_vlm"]


class _BadInfo:
    @property
    def duration_str(self):
        raise RuntimeError("bozuk video_info (simule)")


try:
    out = G.finalize({"summary": "ozet", "events": evs, "video_info": _BadInfo(),
                      "risk": RiskAssessment(level=Severity.YUKSEK, rationale="r"), "trace": []})
    res = out.get("result")
    ok = isinstance(res, AnalysisResult) and any("finalize: dugum hatasi" in t for t in res.decision_trace)
except Exception:
    ok = False
    traceback.print_exc()
check("finalize: hatada bile GECERLI AnalysisResult doner ('result' KeyError'i yok)", ok)

out = G.finalize({"summary": "ozet", "events": evs, "video_info": None,
                  "risk": RiskAssessment(level=Severity.YUKSEK, rationale="r"),
                  "actions": [Action(action="Ekip gonder", priority=Severity.YUKSEK)],
                  "triggered_functions": ["yonetici_bilgilendir"],
                  "action_log": [{"function": "yonetici_bilgilendir"}], "trace": ["t"]})
d = out["result"].to_sartname_dict()
check("CIKTI SOZLESMESI (to_sartname_dict) BOZULMADI",
      set(d) == {"summary", "events", "risk", "actions"}
      and d["events"] == [{"time": "00:02", "event": "belirsiz durum"}]
      and d["risk"] == "Yüksek" and d["actions"] == ["Ekip gonder"], str(d))


# =====================================================================
# UCTAN-UCA: GERCEK LangGraph grafigi, analyze_video(n_samples>1) deseninde paralel
# (LangGraph kendi calistiricisi contextvars kopyalayabilir -> izolasyon burada da gecerli mi?)
# =====================================================================
print("\n=== Uctan-uca: gercek LangGraph grafigi paralel kosuluyor ===")


def _fake_ingest(state):
    return {"segments": [], "video_info": None, "scene_cuts": [], "trace": state.get("trace", [])}


def _fake_perceive(state):
    time.sleep(0.005)
    return {"events": _kritik(f"{_local.tag} kritik olay"), "trace": state.get("trace", [])}


def _fake_reason(state):
    time.sleep(0.005)
    return {"summary": f"{_local.tag} ozet",
            "risk": RiskAssessment(level=Severity.KRITIK, rationale="r"),
            "actions": [], "trace": state.get("trace", [])}


G.ingest, G.perceive, G.reason = _fake_ingest, _fake_perceive, _fake_reason
G._get_vlm = lambda: FakeVLM(PLAN[_local.tag][0])
try:
    graph = G.build_graph()  # act + finalize + kosullu kenar GERCEK

    def _run_graph(tag):
        _local.tag = tag
        return tag, graph.invoke({"video_path": "sahte.mp4", "trace": []})["result"]

    with ThreadPoolExecutor(max_workers=10) as pool:
        gout = list(pool.map(_run_graph, [t for _ in range(10) for t in ("A", "B", "C")]))
    gbad = [(t, r.triggered_functions) for t, r in gout if r.triggered_functions != PLAN[t][1]]
    gmix = [t for t, r in gout if not r.summary.startswith(t)]
    check("30 paralel LangGraph kosusu: triggered_functions kosu-basina dogru", not gbad, str(gbad[:3]))
    check("30 paralel LangGraph kosusu: ozet/kayit capraz-karisma yok", not gmix, str(gmix[:3]))
finally:
    G.ingest, G.perceive, G.reason = _ORIG["ingest"], _ORIG["perceive"], _ORIG["reason"]
    G._get_vlm = _ORIG["_get_vlm"]

G.build_graph()
check("build_graph() (gercek dugumlerle) derleniyor", True)

print("\n" + "=" * 46)
print("TUM TESTLER GECTI" if not FAILS else f"{len(FAILS)} TEST BASARISIZ: {FAILS}")
sys.exit(1 if FAILS else 0)
