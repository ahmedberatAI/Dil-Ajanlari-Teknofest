"""Duman v3: kaynak, duman-buhar, akutluk ve sevk maskesi regresyonlari."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import duman_kanit as D
from dilajan.agent import graph as G
from dilajan.schema import Event, EventCategory, RiskAssessment, Severity


def _result(level: D.DumanDuzeyi, supports: int = 2, refutes: int = 0):
    return D.DumanKanitSonucu(
        duzey=level,
        slot_degeri="VAR",
        cevaplar={
            "gorunur_kaynakli_plum": "KAYNAKTAN_CIKAN_PLUM",
            "optik_madde": "DUMAN_OPAKLIGI",
            "zamansal_madde": "KALICI_DUMAN_AEROSOLU",
        },
        destek_sayisi=supports,
        curutme_sayisi=refutes,
        madde_destek_sayisi=2 if level != D.DumanDuzeyi.YOK else 0,
    )


def test_two_of_three_is_required_and_slot_can_be_rescued():
    one = D.sonuclandir("VAR", {
        "gorunur_kaynakli_plum": "PLUM_YOK",
        "zamansal_kaynak": "GORUNMUYOR",
    })
    assert one.duzey == D.DumanDuzeyi.YOK

    rescued = D.sonuclandir("YOK", {
        "gorunur_kaynakli_plum": "KAYNAKTAN_CIKAN_PLUM",
        "zamansal_kaynak": "ENDUSTRIYEL_KAYNAKLI_PLUM",
        "optik_madde": "DUMAN_OPAKLIGI",
        "zamansal_madde": "KALICI_DUMAN_AEROSOLU",
    })
    assert rescued.duzey == D.DumanDuzeyi.GOZLEM
    assert rescued.destek_sayisi == 2


def test_acute_gate_is_separate_from_plume_observation():
    observation = D.sonuclandir("VAR", {
        "gorunur_kaynakli_plum": "KAYNAKTAN_CIKAN_PLUM",
        "zamansal_kaynak": "KISA_GECICI_SALIM",
        "optik_madde": "DUMAN_BUHAR_KARISIMI",
        "zamansal_madde": "DUMAN_BUHAR_BIRLIKTE",
        "akut_belirti": "YALNIZ_PLUM_EMISYONU",
    })
    assert observation.duzey == D.DumanDuzeyi.GOZLEM

    acute = D.sonuclandir("VAR", {
        "gorunur_kaynakli_plum": "KAYNAKTAN_CIKAN_PLUM",
        "zamansal_kaynak": "ENDUSTRIYEL_KAYNAKLI_PLUM",
        "optik_madde": "DUMAN_OPAKLIGI",
        "zamansal_madde": "KALICI_DUMAN_AEROSOLU",
        "akut_belirti": "ACIK_ALEV",
    })
    assert acute.duzey == D.DumanDuzeyi.AKUT_YANGIN


def test_two_explicit_refutations_are_terminal():
    result = D.sonuclandir("VAR", {
        "gorunur_kaynakli_plum": "SABIT_PARLAKLIK_GOLGE",
        "zamansal_kaynak": "PLUM_YOK",
    })
    assert result.duzey == D.DumanDuzeyi.YOK
    assert result.refuted


def test_plume_presence_alone_is_not_smoke_and_steam_refutes():
    plume_only = D.sonuclandir("VAR", {
        "gorunur_kaynakli_plum": "KAYNAKTAN_CIKAN_PLUM",
        "zamansal_kaynak": "ENDUSTRIYEL_KAYNAKLI_PLUM",
    })
    assert plume_only.duzey == D.DumanDuzeyi.YOK
    assert plume_only.destek_sayisi == 3
    assert plume_only.madde_destek_sayisi == 0

    steam = D.sonuclandir("VAR", {
        "gorunur_kaynakli_plum": "KAYNAKTAN_CIKAN_PLUM",
        "zamansal_kaynak": "ENDUSTRIYEL_KAYNAKLI_PLUM",
        "optik_madde": "PARLAK_BEYAZ_BUHAR",
        "zamansal_madde": "HIZLA_INCELEN_YOGUSMA",
    })
    assert steam.duzey == D.DumanDuzeyi.YOK
    assert steam.madde_curutme_sayisi == 2
    assert steam.refuted


def test_video_adapter_keeps_fixed_roles_and_independent_questions():
    class Role:
        def __init__(self, name):
            self.name = name

    class Session:
        hazir = True
        hata = None

        def __init__(self, client):
            self.istemci = client
            self.calls = []

        def sor(self, _question, *, guided_choice, **kwargs):
            self.calls.append((self.istemci.name, tuple(guided_choice), kwargs))
            answers = {
                tuple(D.GORSEL_SECENEKLER): "KAYNAKTAN_CIKAN_PLUM",
                tuple(D.ZAMANSAL_SECENEKLER): "ENDUSTRIYEL_KAYNAKLI_PLUM",
                tuple(D.OPTIK_SECENEKLER): "DUMAN_OPAKLIGI",
                tuple(D.DAGILIM_SECENEKLER): "KALICI_DUMAN_AEROSOLU",
                tuple(D.AKUT_SECENEKLER): "ACIL_BELIRTI_YOK",
            }
            return answers[tuple(guided_choice)]

    class Client(Role):
        def __init__(self):
            super().__init__("root")
            self.session = Session(self)

        def video_oturumu(self, *_args, **_kwargs):
            return self.session

        def gorev(self, role):
            return Role(role)

    client = Client()
    result = D.dogrula_video(client, b"video", "VAR")
    assert result.duzey == D.DumanDuzeyi.GOZLEM
    assert [call[0] for call in client.session.calls] == [
        "algi", "olay", "algi", "olay", "algi",
    ]
    assert all(call[2]["hatirla"] is False for call in client.session.calls)


def test_graph_replaces_narrative_hallucination_with_verified_smoke_observation():
    narrative = Event(
        time="00:02",
        event="Depoda büyük yangın ve duman var, herkes tahliye edilmeli",
        severity=Severity.KRITIK,
        category=EventCategory.GUVENLIK,
    )
    other = Event(
        time="00:01", event="forklift hareketi", severity=Severity.ORTA,
        category=EventCategory.ANOMALI,
    )
    old = D.dogrula_video
    try:
        D.dogrula_video = lambda *_args, **_kwargs: _result(D.DumanDuzeyi.GOZLEM)
        events, note, refuted = G._yapisal_duman_hakemligi(
            object(), b"video", [narrative, other], "VAR", zaman="00:00", bitis="00:03"
        )
    finally:
        D.dogrula_video = old
    smoke = [event for event in events if getattr(event, "isg_kod", "") == "Industrial_Smoke_Emission"]
    assert len(smoke) == 1
    assert smoke[0].severity == Severity.ORTA
    assert smoke[0].category == EventCategory.ANOMALI
    assert getattr(smoke[0], "dispatch_eligible", True) is False
    assert "tahliye" not in smoke[0].event.lower()
    assert other in events
    assert "GOZLEM" in note
    assert not refuted


def test_graph_removes_all_smoke_claims_when_evidence_is_refuted():
    structured = Event(
        time="00:00", event="duman", severity=Severity.ORTA,
        category=EventCategory.ANOMALI,
    ).model_copy(update={"isg_kod": "Industrial_Visible_Plume"})
    result = _result(D.DumanDuzeyi.YOK, supports=1, refutes=2)
    old = D.dogrula_video
    try:
        D.dogrula_video = lambda *_args, **_kwargs: result
        events, _note, refuted = G._yapisal_duman_hakemligi(
            object(), b"video", [structured], "VAR"
        )
    finally:
        D.dogrula_video = old
    assert events == []
    assert refuted


def test_non_acute_smoke_observation_cannot_dispatch_even_with_high_risk():
    smoke = Event(
        time="00:00",
        event="Görünür duman/plüm emisyonu gözlemi",
        severity=Severity.ORTA,
        category=EventCategory.ANOMALI,
    ).model_copy(update={
        "isg_kod": "Industrial_Visible_Plume",
        "smoke_observation_src": True,
        "dispatch_eligible": False,
    })
    result = G.act({
        "events": [smoke],
        "risk": RiskAssessment(level=Severity.YUKSEK, rationale="gözlem"),
        "trace": [],
    })
    assert result["triggered_functions"] == []
    assert any("dispatch_eligible=False" in line for line in result["trace"])


def test_smoke_observation_does_not_enter_generic_reexamine_route():
    smoke = Event(
        time="00:00", event="duman/plüm", severity=Severity.ORTA,
        category=EventCategory.ANOMALI,
    ).model_copy(update={"smoke_observation_src": True, "dispatch_eligible": False})
    assert G.route_after_perceive({"events": [smoke]}) == "reason"


def main() -> int:
    tests = [
        test_two_of_three_is_required_and_slot_can_be_rescued,
        test_acute_gate_is_separate_from_plume_observation,
        test_two_explicit_refutations_are_terminal,
        test_plume_presence_alone_is_not_smoke_and_steam_refutes,
        test_video_adapter_keeps_fixed_roles_and_independent_questions,
        test_graph_replaces_narrative_hallucination_with_verified_smoke_observation,
        test_graph_removes_all_smoke_claims_when_evidence_is_refuted,
        test_non_acute_smoke_observation_cannot_dispatch_even_with_high_risk,
        test_smoke_observation_does_not_enter_generic_reexamine_route,
    ]
    for test in tests:
        test()
        print(f"ok {test.__name__}")
    print("TUM DUMAN V3 TESTLERI GECTI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
