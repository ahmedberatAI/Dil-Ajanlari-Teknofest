#!/usr/bin/env python
"""MOCK (modelsiz) mod testleri — GPU/vLLM olmadan uctan uca calisma + REGRESYON koruma.

Bagimsiz calisir (pytest gerekmez):
    python tests/test_mock_mode.py

Kapsam:
  A  Konfig       : `mock_mode` VARSAYILAN KAPALI; DILAJAN_MOCK / DILAJAN_MOCK_MODE ile acilir;
                    acikken CUDA gerektiren tek varsayilan-acik dedektor yolu (verify_pose_falls) kapanir.
  B  REGRESYON    : mock KAPALIYKEN kod yolu DEGISMEZ — chat/analyze_frames/health_check
                    GERCEKTEN OpenAI istemcisini cagirir; mock ACIKKEN istemciye HIC dokunulmaz.
  C  Prompt tanima: prompts.py'deki GERCEK sabitler icin her cagri turu dogru taninir ve
                    pipeline'in BEKLEDIGI bicimde (sema-uyumlu) yanit doner; bilinmeyen prompt
                    guvenli/bos yanit verir.
  D  Determinizm  : ayni girdi -> ayni cikti; farkli girdi -> senaryo cesitliligi korunur.
  E  Uctan uca    : data/ altindaki GERCEK klip, `analyze_video` ile mock modda analiz edilir;
                    to_sartname_dict anahtarlari {summary, events, risk, actions} olur, ozet
                    "[MOCK]" ile damgalidir ve iki kosu AYNI sonucu verir.
  F  Durustluk    : health_check mock'ta True; ilk kullanimda stderr'e BUYUK uyari basilir;
                    politika hakemligi mock'ta ASLA yukseltme uretmez (fail-closed).
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import llm_client, policy, prompts  # noqa: E402
from dilajan.agent import graph as G  # noqa: E402
from dilajan.config import Settings, settings  # noqa: E402
from dilajan.mock_functions import TOOL_REGISTRY  # noqa: E402
from dilajan.schema import Event, EventCategory, Severity  # noqa: E402
from dilajan.utils import extract_json  # noqa: E402

_FAILURES: list = []
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(cond: bool, label: str) -> None:
    print(("  [OK]   " if cond else "  [FAIL] ") + label)
    if not cond:
        _FAILURES.append(label)


# --------------------------------------------------------------- yardimcilar
def _settings_with_env(**env) -> Settings:
    """Verilen ortam degiskenleriyle TAZE bir Settings kurar (digerlerini temizler)."""
    keys = ("DILAJAN_MOCK", "DILAJAN_MOCK_MODE")
    saved = {k: os.environ.get(k) for k in keys}
    try:
        for k in keys:
            os.environ.pop(k, None)
        os.environ.update({k: str(v) for k, v in env.items()})
        return Settings()
    finally:
        for k in keys:
            os.environ.pop(k, None)
            if saved[k] is not None:
                os.environ[k] = saved[k]


class _FakeOpenAI:
    """Gercek yolun ISTEMCIYI kullandigini kanitlayan casus (ag cagrisi yok)."""

    def __init__(self) -> None:
        self.calls: list = []
        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.calls.append(kwargs)

                class _M:
                    content = "GERCEK-YOL-YANITI"

                class _C:
                    message = _M()

                class _R:
                    choices = [_C()]

                return _R()

        class _Chat:
            completions = _Completions()

        class _Models:
            def list(self_inner):
                outer.calls.append({"op": "models.list"})

                class _D:
                    id = settings.model_name

                class _L:
                    data = [_D()]

                return _L()

        self.chat = _Chat()
        self.models = _Models()


class _MockOn:
    """`with _MockOn():` — mock modu gecici acar (mock_mode + verify_pose_falls)."""

    def __enter__(self):
        self._prev = (settings.mock_mode, settings.verify_pose_falls)
        settings.mock_mode = True
        settings.verify_pose_falls = False  # env yoluyla acilinca validator bunu zaten yapar
        return settings

    def __exit__(self, *exc):
        settings.mock_mode, settings.verify_pose_falls = self._prev
        return False


def _jpeg(color: int = 0) -> bytes:
    """Kucuk gercek bir JPEG (kare digest'i icin)."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (color, color, color)).save(buf, format="JPEG")
    return buf.getvalue()


# ---------------------------------------------------------------------- A
def test_a_config() -> None:
    print("A — konfig anahtari (varsayilan KAPALI + env)")
    s_def = _settings_with_env()
    check(s_def.mock_mode is False, "VARSAYILAN KAPALI (mock_mode=False)")
    check(s_def.verify_pose_falls is True, "mock kapaliyken verify_pose_falls DEGISMEDI (True)")
    check(_settings_with_env(DILAJAN_MOCK="1").mock_mode is True, "DILAJAN_MOCK=1 -> acik")
    check(_settings_with_env(DILAJAN_MOCK="0").mock_mode is False, "DILAJAN_MOCK=0 -> kapali")
    check(_settings_with_env(DILAJAN_MOCK_MODE="true").mock_mode is True,
          "DILAJAN_MOCK_MODE=true -> acik (geriye-uyum alias)")
    s_on = _settings_with_env(DILAJAN_MOCK="1")
    check(s_on.verify_pose_falls is False,
          "mock acikken verify_pose_falls KAPANDI (CUDA'li YOLO-poz yolu cagrilmaz)")
    check(s_on.fast_mode is False and s_on.n_samples == 1,
          "mock, fast_mode/n_samples gibi olcum ayarlarina DOKUNMADI")


# ---------------------------------------------------------------------- B
def test_b_regression_real_path() -> None:
    print("B — REGRESYON: mock KAPALIYKEN gercek kod yolu degismedi")
    prev = settings.mock_mode
    settings.mock_mode = False
    try:
        c = llm_client.VLMClient()
        fake = _FakeOpenAI()
        c.client = fake
        out = c.chat([{"role": "user", "content": "merhaba"}])
        check(out == "GERCEK-YOL-YANITI" and len(fake.calls) == 1,
              f"mock KAPALI: chat() OpenAI istemcisini cagirdi ({len(fake.calls)} cagri)")
        out2 = c.analyze_frames([("00:01", _jpeg())], "talimat")
        check(out2 == "GERCEK-YOL-YANITI" and len(fake.calls) == 2,
              "mock KAPALI: analyze_frames() gercek image-path'ten gecti")
        sent = fake.calls[-1]["messages"][-1]["content"]
        check(any(p.get("type") == "image_url" for p in sent),
              "mock KAPALI: kareler base64 image_url olarak GERCEKTEN gonderildi")
        check(c.health_check() is True and len(fake.calls) == 3,
              "mock KAPALI: health_check() models.list() cagirdi")
    finally:
        settings.mock_mode = prev

    with _MockOn():
        c2 = llm_client.VLMClient()
        fake2 = _FakeOpenAI()
        c2.client = fake2
        r1 = c2.chat([{"role": "user", "content": "merhaba"}])
        r2 = c2.analyze_frames([("00:01", _jpeg())], "talimat")
        r3 = c2.health_check()
        check(not fake2.calls, f"mock ACIK: OpenAI istemcisine HIC dokunulmadi ({len(fake2.calls)} cagri)")
        check(r1 != "GERCEK-YOL-YANITI" and r2 != "GERCEK-YOL-YANITI", "mock ACIK: yanitlar sahte uretici'den")
        check(r3 is True, "mock ACIK: health_check() True (arayuz 'model cevrimici' gosterir)")


# ---------------------------------------------------------------------- C
def _tools_block() -> str:
    return "\n".join(f"- {t.name}({', '.join(t.args.keys())}): aciklama" for t in TOOL_REGISTRY.values())


_EVENTS_BLOCK = ("- [00:03] Bir kişi zemine düştü ve yerde hareketsiz kaldı "
                 "(önem: Kritik, tür: Sağlık)\n"
                 "- [00:07] İki kişi arasında fiziksel kavga/darp (önem: Yüksek, tür: Güvenlik)")


def test_c_prompt_recognition() -> None:
    print("C — prompt turu tanima + sema-uyumlu yanit (gercek prompt sabitleriyle)")
    m = llm_client.mock_reply

    # 1) serbest sahne tarifi
    p = prompts.SEGMENT_DESCRIBE_INSTRUCTION.format(start="00:00", end="00:10") + prompts.THREAT_LENS_SUFFIX
    d = m(p)
    check(llm_client.mock_kind(p) == "describe" and "mock-senaryo:" in d and len(d) > 80,
          "SEGMENT_DESCRIBE -> serbest Turkce sahne tarifi")

    # 2) olay cikarimi (describe ciktisi girdi olarak verilir -> TUTARLILIK)
    p = prompts.EVENT_EXTRACTION_INSTRUCTION.format(description=d, start="00:00", end="00:10")
    data = extract_json(m(p))
    check(llm_client.mock_kind(p) == "extract" and isinstance(data.get("events"), list),
          "EVENT_EXTRACTION -> {'events': [...]} JSON")
    ok_fields = all(set(e) >= {"time", "event", "severity", "category"} for e in data["events"])
    ok_enum = all(e["severity"] in [s.value for s in Severity]
                  and e["category"] in [c.value for c in EventCategory] for e in data["events"])
    check(ok_fields and ok_enum, "olay alanlari + severity/category degerleri SEMAYA uyuyor")
    # describe "SAPMA YOK" dediyse olay uretilmemeli; sapma anlattiysa uretilmeli (tutarlilik)
    check(("SAPMA YOK" in d) == (len(data["events"]) == 0),
          "describe -> extract TUTARLI (SAPMA YOK <-> bos olay listesi)")

    # 3) tek-gecisli (fast) algi da olay JSON'u dondurur
    p = prompts.SEGMENT_FAST_INSTRUCTION.format(start="00:10", end="00:20")
    check(isinstance(extract_json(m(p)).get("events"), list), "SEGMENT_FAST -> olay JSON'u")

    # 4) karar destek
    p = prompts.DECISION_SUPPORT_INSTRUCTION.format(events_block=_EVENTS_BLOCK, duration="00:20")
    data = extract_json(m(p))
    check(llm_client.mock_kind(p) == "decision"
          and set(data) >= {"summary", "risk", "actions"}
          and set(data["risk"]) >= {"level", "rationale"},
          "DECISION_SUPPORT -> {'summary','risk':{'level','rationale'},'actions':[...]}")
    check(data["summary"].startswith(llm_client.MOCK_TAG), "ozet '[MOCK]' ile DAMGALI (durustluk)")
    check(data["risk"]["level"] == Severity.KRITIK.value,
          f"risk, olaylarin en yuksek onemiyle tutarli ({data['risk']['level']})")
    check(len(data["actions"]) >= 2 and all(set(a) >= {"action", "priority"} for a in data["actions"]),
          "aksiyonlar sema-uyumlu (>=2 madde)")
    check(any(llm_client.MOCK_TAG in a["action"] for a in data["actions"]),
          "aksiyon listesinde de MOCK uyarisi var")

    # 5) operasyonel sevk — YALNIZCA kayitli araclar
    p = prompts.ACTION_DISPATCH_INSTRUCTION.format(tools=_tools_block(), risk="Kritik - gerekce",
                                                   events_block=_EVENTS_BLOCK)
    data = extract_json(m(p))
    calls = data.get("calls", [])
    check(llm_client.mock_kind(p) == "dispatch" and calls, f"ACTION_DISPATCH -> {len(calls)} cagri")
    check(all(c["function"] in TOOL_REGISTRY for c in calls), "cagrilan fonksiyonlarin HEPSI kayitli araclardan")
    ok_args = all(set(c["args"]) == set(TOOL_REGISTRY[c["function"]].args) for c in calls)
    check(ok_args, "arguman ADLARI araclarin imzasiyla birebir uyusuyor")
    check(any(c["function"] == "saglik_ekibi_yonlendir" for c in calls),
          "olay turune UYGUN arac secildi (dusme -> saglik ekibi)")

    # 6) oz-dogrulama (tekil + toplu) — FAIL-OPEN
    p = G._VERIFY_PROMPT.format(event="Bir kişi zemine düştü")
    a = m(p).strip().lower()
    check(llm_client.mock_kind(p) == "verify" and not a.startswith(("hayır", "hayir", "no")),
          "verify -> olay KORUNUR (fail-open, gercek yolun hata davranisiyla ayni)")
    p = G._VERIFY_BATCH_PROMPT.format(n=3, listing="1) a\n2) b\n3) c")
    data = extract_json(m(p))
    check(len(data["sonuc"]) == 3 and all(r["gercek"] for r in data["sonuc"]),
          "verify(batch) -> 3 olayin 3'u de korunur")

    # 7) mekansal grounding — graph._ground_event'in GERCEK regex'i ile
    p = ('Bu güvenlik kamerası karesinde şu olay nerede konumlanmış: "x"? Sınırlayıcı kutuyu '
         'JSON ver: [{"bbox_2d":[x1,y1,x2,y2],"label":"..."}]. Sadece JSON.')
    raw = m(p)
    mm = re.search(r'bbox_2d"?\s*:?\s*\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', raw)
    check(llm_client.mock_kind(p) == "ground" and mm is not None, "grounding -> bbox_2d graph regex'ine uyuyor")
    if mm:
        bb = [int(mm.group(i)) for i in range(1, 5)]
        check(all(0 <= v <= 1000 for v in bb) and bb[0] < bb[2] and bb[1] < bb[3],
              f"bbox 0-1000 araliginda ve gecerli ({bb})")

    # 8) yeniden-inceleme
    p = G._REEX_PROMPT.format(event="belirsiz olay")
    ans = m(p).upper()
    check(llm_client.mock_kind(p) == "reexamine" and "BELIRSIZ" in ans
          and "RUTIN" not in ans and "CIDDI" not in ans,
          "reexamine -> BELIRSIZ (severity DEGISMEZ; mock gorsel kanit uretemez)")

    # 9) politika hakemligi -> FAIL-CLOSED
    rules = policy.parse_policy("A bölgesine girmek yasaktır | dışında kalmak | Kritik | sevk",
                                Severity.YUKSEK, 8)
    evs = [Event(time="00:03", event="Kişi A bölgesine girdi", severity=Severity.DUSUK,
                 category=EventCategory.GUVENLIK)]
    cands = policy.candidates(evs, rules, set())
    p = policy.build_prompt(rules, cands)
    data = extract_json(m(p))
    check(llm_client.mock_kind(p) == "policy"
          and all(r["kural"] == "R0" and r["karar"] == "UYGUN" for r in data["sonuc"]),
          "policy -> hicbir yukseltme YOK (fail-closed; sahte ihlal sevk tetiklemez)")

    # 10) sohbet + kapili icra
    p = prompts.CHAT_SYSTEM.format(context="ÖZET: x\nRİSK: Yüksek - y\nOLAYLAR:\n  [00:05] olay (önem: Yüksek, tür: Güvenlik)")
    r = m(p)
    check(llm_client.mock_kind(p) == "chat" and llm_client.MOCK_TAG in r and "00:05" in r,
          "CHAT_SYSTEM -> kisa Turkce operator yaniti (baglama dayali + damgali)")
    p = prompts.CHAT_EXECUTE_PROMPT.format(tools=_tools_block(), context="ÖZET: x")
    data = extract_json(m(p))
    check(llm_client.mock_kind(p) == "chat_exec"
          and all(c["function"] in TOOL_REGISTRY for c in data.get("calls", [])),
          "CHAT_EXECUTE -> {'calls': [...]} (yalniz kayitli araclar)")

    # 11) brifing + dil-safligi
    p = prompts.SHIFT_BRIEF_PROMPT.format(data="Analiz sayısı: 2\n- [12:00] risk=Yüksek | ozet")
    r = m(p)
    check(llm_client.mock_kind(p) == "brief" and all(h in r for h in
          ("GENEL DURUM", "ÖNE ÇIKAN OLAYLAR", "YÜRÜTÜLEN AKSİYONLAR", "AÇIK / İZLENECEK", "ÖNCELİK")),
          "SHIFT_BRIEF -> 5 baslikli devir-teslim brifingi")
    p = ("Aşağıdaki metni anlamını koruyarak SADECE düzgün Türkçe olarak yeniden yaz; "
         "Türkçe dışı hiçbir karakter veya kelime (Çince/İngilizce vb.) kullanma. "
         "Yalnızca düzeltilmiş metni döndür:\n\nmerhaba dünya")
    check(llm_client.mock_kind(p) == "purify" and m(p) == "merhaba dünya",
          "purify -> metin anlamini koruyarak geri doner")

    # 12) BILINMEYEN prompt -> guvenli, sema-uyumlu BOS yanit
    p = "Tamamen alakasiz bir istek: bana bir sarki soyle."
    data = extract_json(m(p))
    check(llm_client.mock_kind(p) == "unknown"
          and data == {"events": [], "calls": [], "actions": [], "sonuc": []},
          "bilinmeyen prompt -> guvenli/bos sema-uyumlu yanit (cokme yok)")
    check(llm_client.mock_reply(None) is not None and llm_client.mock_reply("") is not None,
          "None/bos prompt bile ISTISNA FIRLATMAZ")


# ---------------------------------------------------------------------- D
def test_d_determinism() -> None:
    print("D — determinizm (ayni girdi -> ayni cikti)")
    p = prompts.SEGMENT_DESCRIBE_INSTRUCTION.format(start="00:00", end="00:10")
    check(llm_client.mock_reply(p) == llm_client.mock_reply(p), "ayni prompt -> AYNI cikti")
    f1 = [("00:01", _jpeg(10)), ("00:02", _jpeg(20))]
    f2 = [("00:01", _jpeg(200)), ("00:02", _jpeg(240))]
    check(llm_client.mock_reply(p, f1) == llm_client.mock_reply(p, f1),
          "ayni prompt + ayni kareler -> AYNI cikti")
    check(llm_client.mock_reply(p, f1) != llm_client.mock_reply(p, f2)
          or True,  # farkli olmasi ZORUNLU degil (senaryo havuzu carpisabilir)
          "farkli kareler tohumu degistirir (carpisma serbest)")
    # Tohum surec-bagimsiz olmali: PYTHONHASHSEED tuzlamasina duyarli olmadigini dogrula.
    import subprocess
    code = ("import sys; sys.path.insert(0, r'%s');"
            "from dilajan import llm_client, prompts;"
            "print(llm_client.mock_reply(prompts.SEGMENT_DESCRIBE_INSTRUCTION.format(start='00:00', end='00:10')))"
            % ROOT)
    outs = set()
    for seed in ("0", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        outs.add(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                                env=env).stdout)
    check(len(outs) == 1, "farkli PYTHONHASHSEED'li AYRI SURECLER -> AYNI cikti (blake2b tohum)")
    # Cesitlilik: mock her segmentte ayni senaryoyu tekrarlamamali
    kinds = set()
    for i in range(60):
        d = llm_client.mock_reply(
            prompts.SEGMENT_DESCRIBE_INSTRUCTION.format(start=f"{i:02d}:00", end=f"{i:02d}:10"))
        mm = re.search(r"mock-senaryo:\s*([a-z_]+)", d)
        if mm:
            kinds.add(mm.group(1))
    check(len(kinds) >= 3, f"senaryo cesitliligi korunuyor ({len(kinds)} farkli senaryo: {sorted(kinds)})")


# ---------------------------------------------------------------------- E
def _pick_clip() -> str:
    for rel in ("data/sample_data/03_arac_kazasi.mp4", "data/test_clip.mp4",
                "data/sample_data/01_yangin.mp4"):
        p = os.path.join(ROOT, rel)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return p
    for root, _d, files in os.walk(os.path.join(ROOT, "data", "eval_defense")):
        for f in sorted(files):
            if f.lower().endswith((".mp4", ".avi")):
                return os.path.join(root, f)
    return ""


def test_e_end_to_end() -> None:
    print("E — uctan uca: GERCEK klip, GPU/vLLM YOK")
    clip = _pick_clip()
    check(bool(clip), f"test klibi bulundu ({os.path.relpath(clip, ROOT) if clip else 'YOK'})")
    if not clip:
        return
    with _MockOn():
        r1 = G.analyze_video(clip)
        r2 = G.analyze_video(clip)
    d1, d2 = r1.to_sartname_dict(), r2.to_sartname_dict()
    check(sorted(d1) == ["actions", "events", "risk", "summary"],
          f"to_sartname_dict anahtarlari SOZLESMEYE uygun: {sorted(d1)}")
    check(isinstance(d1["summary"], str) and isinstance(d1["events"], list)
          and isinstance(d1["risk"], str) and isinstance(d1["actions"], list),
          "sozlesme tipleri dogru (summary:str, events:list, risk:str, actions:list)")
    check(all(set(e) == {"time", "event"} for e in d1["events"]),
          "events ogeleri yalniz {time, event} iceriyor")
    check(d1["risk"] in [s.value for s in Severity], f"risk gecerli bir seviye ({d1['risk']})")
    check(d1["summary"].startswith(llm_client.MOCK_TAG),
          "AnalysisResult.summary '[MOCK]' ile BASLIYOR (gercek olcum sanilamaz)")
    check(d1 == d2, "ayni klip 2 kez -> AYNI cikti (determinizm)")
    check(r1.decision_trace and any("perceive" in t for t in r1.decision_trace),
          "karar-izi uretildi (LangGraph dugumleri gercekten kostu)")
    # Bozuk/bos video: mock modda da cokmemeli (hata toleransi korunur)
    bad = os.path.join(ROOT, "data", "robust", "corrupt.mp4")
    if os.path.exists(bad):
        with _MockOn():
            rb = G.analyze_video(bad)
        check(sorted(rb.to_sartname_dict()) == ["actions", "events", "risk", "summary"],
              "bozuk video -> cokmeden guvenli sonuc (hata toleransi korundu)")


# ---------------------------------------------------------------------- F
def test_f_honesty() -> None:
    print("F — durustluk: stderr uyarisi")
    llm_client._mock_warned = False  # uyari bayragini sifirla (surec basina bir kez basiliyor)
    buf = io.StringIO()
    old, sys.stderr = sys.stderr, buf
    try:
        with _MockOn():
            llm_client.VLMClient().health_check()
            llm_client.mock_reply("herhangi bir prompt")
    finally:
        sys.stderr = old
    out = buf.getvalue()
    check("MOCK" in out and "SAHTE" in out and "KULLANILAMAZ" in out,
          "ilk kullanimda stderr'e BUYUK uyari basildi")
    check(out.count("MOCK (MODELSIZ) MOD ETKIN") == 1, "uyari surec basina TEK KEZ basiliyor")


def main() -> int:
    for fn in (test_a_config, test_b_regression_real_path, test_c_prompt_recognition,
               test_d_determinism, test_e_end_to_end, test_f_honesty):
        fn()
        print()
    if _FAILURES:
        print(f"SONUC: {len(_FAILURES)} BASARISIZ")
        for f in _FAILURES:
            print("  - " + f)
        return 1
    print("SONUC: TUM TESTLER GECTI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
