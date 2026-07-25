#!/usr/bin/env python
"""K2/K4/K5 regresyon testleri — istek izolasyonu + diyalog icra kapisi.

Bagimsiz calisir (pytest gerekmez):
    python tests/test_agent_k2_k4_k5.py

Kapsam:
  K2  app.analyze()'in istek-kapsamli konfigi (config.request_config): eszamanli iki
      "analiz" birbirinin tesis-kuralini/bolgesini EZMEZ ve degerler istekten sonra
      GERI YUKLENIR (sizinti yok).
  K4  chat_agent._maybe_execute dedup'i (fonksiyon, NORMALIZE-args) ciftine bakar:
      ayni fn + ayni arg -> 1 kez; ayni fn + FARKLI arg -> 2 kez.
  K5  chat_agent.is_confirmation olumsuzlama-farkindalikli: "gönderme"/"onaylamıyorum"
      icra tetiklemez.
"""
from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import chat_agent, memory  # noqa: E402
from dilajan.config import request_config, settings  # noqa: E402

_FAILURES: list = []


def check(cond: bool, label: str) -> None:
    print(("  [OK]   " if cond else "  [FAIL] ") + label)
    if not cond:
        _FAILURES.append(label)


# ---------------------------------------------------------------- K2
def test_k2_request_isolation() -> None:
    print("K2 — istek izolasyonu (eszamanli iki analiz)")
    base_rules, base_zones = settings.facility_rules, settings.restricted_zones
    base_crowd = settings.detect_crowd
    observed: dict = {}
    errors: list = []

    def fake_analyze(name: str, rules: str, zones: str, crowd: bool) -> None:
        """analyze() ile ayni sekilde istek-kapsamli konfig acar ve 'graph' kosar gibi
        settings'i tekrar tekrar okur (graph.py/detector.py `settings.<alan>` okur)."""
        try:
            seen = set()
            with request_config(facility_rules=rules, restricted_zones=zones,
                                detect_crowd=crowd):
                for _ in range(40):  # ~0.4 sn boyunca surekli oku
                    seen.add((settings.facility_rules, settings.restricted_zones,
                              settings.detect_crowd))
                    time.sleep(0.01)
            observed[name] = seen
        except Exception as ex:  # pragma: no cover
            errors.append(f"{name}: {ex}")

    t1 = threading.Thread(target=fake_analyze, args=("A", "A-KURAL", "üst sağ", True))
    t2 = threading.Thread(target=fake_analyze, args=("B", "B-KURAL", "alt sol", False))
    t1.start()
    time.sleep(0.02)  # B, A calisirken devreye girer
    t2.start()
    t1.join(30)
    t2.join(30)

    check(not errors, f"thread hatasi yok ({errors})")
    check(observed.get("A") == {("A-KURAL", "üst sağ", True)},
          f"A yalniz KENDI konfigini gordu -> {observed.get('A')}")
    check(observed.get("B") == {("B-KURAL", "alt sol", False)},
          f"B yalniz KENDI konfigini gordu -> {observed.get('B')}")
    check((settings.facility_rules, settings.restricted_zones, settings.detect_crowd)
          == (base_rules, base_zones, base_crowd),
          "istek sonrasi global degerler GERI YUKLENDI (sonraki isteme sizmaz)")


def test_k2_restore_on_exception() -> None:
    print("K2 — hata durumunda geri yukleme + kapinin serbest birakilmasi")
    base = settings.facility_rules
    try:
        with request_config(facility_rules="PATLAYAN"):
            raise RuntimeError("analiz coktu")
    except RuntimeError:
        pass
    check(settings.facility_rules == base, "exception sonrasi eski deger geri yuklendi")
    with request_config(facility_rules="X"):  # kapi serbest mi? (deadlock olmamali)
        check(settings.facility_rules == "X", "kapi serbest — yeni istek acilabildi")
    check(settings.facility_rules == base, "ikinci istek de temiz kapandi")


def test_k2_unknown_field_failopen() -> None:
    print("K2 — bilinmeyen alan fail-open")
    ok = True
    try:
        with request_config(facility_rules="Y", bu_alan_yok=123):
            ok = settings.facility_rules == "Y" and not hasattr(settings, "bu_alan_yok")
    except Exception as ex:  # pragma: no cover
        ok = False
        print(f"    beklenmeyen hata: {ex}")
    check(ok, "bilinmeyen alan sessizce yok sayildi, analiz surdu")


# ---------------------------------------------------------------- K4
class _FakeClient:
    """LLM yerine sabit JSON dondurur (GPU/vLLM gerektirmez)."""

    def __init__(self) -> None:
        self.payload = '{"calls": []}'

    def chat(self, *a, **kw) -> str:
        return self.payload


def test_k4_arg_aware_dedup() -> None:
    print("K4 — argüman-farkindali mükerrer-dispatch korumasi")
    fake = _FakeClient()
    original = chat_agent._get_client
    chat_agent._get_client = lambda: fake  # type: ignore[assignment]
    try:
        memory.reset_decisions()

        def run(calls_json: str) -> str:
            fake.payload = calls_json
            return chat_agent._maybe_execute("ctx", [], "evet gönder")

        depo_a = ('{"calls":[{"function":"saglik_ekibi_yonlendir",'
                  '"args":{"konum":"Depo A","aciliyet":"Yüksek"}}]}')
        # ayni cagri; arg SIRASI + bosluk + BUYUK/kucuk harf farkli -> AYNI sayilmali
        depo_a_noisy = ('{"calls":[{"function":"saglik_ekibi_yonlendir",'
                        '"args":{"aciliyet":"yüksek","konum":"  depo   a "}}]}')
        depo_b = ('{"calls":[{"function":"saglik_ekibi_yonlendir",'
                  '"args":{"konum":"Depo B","aciliyet":"Yüksek"}}]}')

        r1 = run(depo_a)
        check(bool(r1) and len(memory.SESSION_DECISIONS) == 1,
              "1. cagri (Depo A) YURUTULDU")
        r2 = run(depo_a)
        check(r2 == "" and len(memory.SESSION_DECISIONS) == 1,
              "ayni fn + AYNI arg tekrari ENGELLENDI (mükerrer koruma korundu)")
        r3 = run(depo_a_noisy)
        check(r3 == "" and len(memory.SESSION_DECISIONS) == 1,
              "normalize (sira/bosluk/harf) sonrasi da AYNI sayildi -> engellendi")
        r4 = run(depo_b)
        check(bool(r4) and len(memory.SESSION_DECISIONS) == 2,
              "ayni fn + FARKLI arg (Depo B) YURUTULDU — K4 duzeltildi")

        # ayni yanit icinde ozdes iki cagri -> tek icra
        memory.reset_decisions()
        r5 = run('{"calls":[{"function":"guvenlik_ekibi_uyar","args":{"konum":"K1","sebep":"kavga"}},'
                 '{"function":"guvenlik_ekibi_uyar","args":{"konum":"K1","sebep":"kavga"}},'
                 '{"function":"guvenlik_ekibi_uyar","args":{"konum":"K2","sebep":"kavga"}}]}')
        check(len(memory.SESSION_DECISIONS) == 2 and r5.count("guvenlik_ekibi_uyar") == 2,
              "tek yanitta: ozdes cagri 1 kez, farkli konum ayrica yurutuldu")
        memory.reset_decisions()
    finally:
        chat_agent._get_client = original  # type: ignore[assignment]


# ---------------------------------------------------------------- K5
_POSITIVE = [
    "evet gönder", "onaylıyorum", "tamam sevk et", "evet, sağlık ekibini çağır",
    "onayla ve uygula", "tamam devam et", "olur, başlat", "hallet",
]
_NEGATIVE = [
    "gönderme", "onaylamıyorum", "tamam değil", "iptal et", "şu an gerek yok",
    "vazgeçtim", "şimdilik bekle", "hayır, sevk etme", "sağlık ekibi çağırma",
    "acil durdurmayı tetikleme", "onaylamıyorum, dur", "evet ama şimdilik bekleyin",
    "gerek yok", "yapma", "olmaz",
]
_NO_CONFIRM = ["en kritik olay neydi?", "durumu özetler misin", "kaç olay var"]


def test_k5_negation_aware_confirm() -> None:
    print("K5 — olumsuzlama-farkindali onay tespiti")
    for msg in _POSITIVE:
        check(chat_agent.is_confirmation(msg) is True, f"POZITIF -> True : {msg!r}")
    for msg in _NEGATIVE:
        check(chat_agent.is_confirmation(msg) is False, f"NEGATIF -> False: {msg!r}")
    for msg in _NO_CONFIRM:
        check(chat_agent.is_confirmation(msg) is False, f"ONAY YOK -> False: {msg!r}")
    check(chat_agent.is_confirmation(None) is False and chat_agent.is_confirmation("") is False,
          "bos/None girdi -> False")


if __name__ == "__main__":
    test_k2_request_isolation()
    test_k2_restore_on_exception()
    test_k2_unknown_field_failopen()
    test_k4_arg_aware_dedup()
    test_k5_negation_aware_confirm()
    print()
    if _FAILURES:
        print(f"BASARISIZ ({len(_FAILURES)}):")
        for f in _FAILURES:
            print("  - " + f)
        sys.exit(1)
    print("TUM TESTLER GECTI")
