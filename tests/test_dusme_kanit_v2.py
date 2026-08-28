"""Dort atomlu dusme/destek-kaybi kapisinin modelsiz testleri."""
from __future__ import annotations

import pytest

from dilajan.dusme_kanit_v2 import (
    DUSME_ATOMLARI,
    DUSME_MAX_TOKENS,
    DUSME_SISTEM,
    SABIT_MODEL_SOZLESMESI,
    DusmeHukmu,
    dogrula_video,
    sonuclandir,
)


def _tum_destek() -> dict[str, str]:
    return {atom.ad: "A" for atom in DUSME_ATOMLARI}


def test_saf_karar_yalniz_dort_acik_destegi_kabul_eder():
    sonuc = sonuclandir(_tum_destek())

    assert sonuc.hukum == DusmeHukmu.SUPPORTED
    assert sonuc.supported
    assert set(sonuc.atom_hukumleri.values()) == {DusmeHukmu.SUPPORTED}


@pytest.mark.parametrize("atom_adi", [atom.ad for atom in DUSME_ATOMLARI])
@pytest.mark.parametrize("cevap", ["B", "C"])
def test_her_atomdaki_acik_karsi_kanit_tum_iddiayi_curutur(atom_adi, cevap):
    cevaplar = _tum_destek()
    cevaplar[atom_adi] = cevap

    sonuc = sonuclandir(cevaplar)

    assert sonuc.hukum == DusmeHukmu.REFUTED
    assert sonuc.atom_hukumleri[atom_adi] == DusmeHukmu.REFUTED


@pytest.mark.parametrize("cevap", ["D", "", "izin-disi", None])
def test_belirsiz_eksik_ve_izin_disi_cevap_fail_closed(cevap):
    cevaplar = _tum_destek()
    cevaplar["outcome"] = cevap

    sonuc = sonuclandir(cevaplar)

    assert sonuc.hukum == DusmeHukmu.INSUFFICIENT
    assert not sonuc.supported


def test_hata_acik_curutme_olsa_bile_fail_closed_insufficient_doner():
    cevaplar = _tum_destek()
    cevaplar["transition"] = "B"

    sonuc = sonuclandir(cevaplar, {"person": RuntimeError("servis yok")})

    assert sonuc.hukum == DusmeHukmu.INSUFFICIENT
    assert "servis yok" in sonuc.hatalar["person"]


def test_ayni_kisi_tek_plan_atomunun_destegi_zorunludur():
    cevaplar = _tum_destek()
    cevaplar["continuous_chain"] = "B"
    kesik = sonuclandir(cevaplar)
    cevaplar["continuous_chain"] = "D"
    belirsiz = sonuclandir(cevaplar)

    assert kesik.hukum == DusmeHukmu.REFUTED
    assert belirsiz.hukum == DusmeHukmu.INSUFFICIENT
    assert not kesik.supported and not belirsiz.supported


def test_atomlarin_sirasi_rollleri_ve_model_sozlesmesi_sabittir():
    assert [atom.ad for atom in DUSME_ATOMLARI] == [
        "person", "transition", "outcome", "continuous_chain",
    ]
    assert [atom.gorev for atom in DUSME_ATOMLARI] == [
        "algi", "olay", "olay", "olay",
    ]
    assert all(atom.secenekler == ("A", "B", "C", "D") for atom in DUSME_ATOMLARI)
    assert dict(SABIT_MODEL_SOZLESMESI) == {
        "algi": "vlm",
        "olay": "llm-large",
        "yapi": "llm-fast",
        "ozet": "llm-fast",
    }


class _Rol:
    def __init__(self, ad: str):
        self.ad = ad


class _Oturum:
    def __init__(self, cevaplar=None, hazir=True, hata=None):
        self.hazir = hazir
        self.hata = hata
        self.istemci = _Rol("kok")
        self.ilk_istemci = self.istemci
        self.cevaplar = dict(cevaplar or {})
        self.cagrilar = []

    def sor(self, _soru, **kwargs):
        atom_adi = [atom.ad for atom in DUSME_ATOMLARI][len(self.cagrilar)]
        self.cagrilar.append((self.istemci.ad, kwargs))
        cevap = self.cevaplar.get(atom_adi, "A")
        if isinstance(cevap, Exception):
            raise cevap
        return cevap


class _Istemci:
    def __init__(self, oturum=None, oturum_hatasi=None):
        self.oturum = oturum or _Oturum()
        self.oturum_hatasi = oturum_hatasi
        self.video_system = None

    def video_oturumu(self, _video, system=None):
        self.video_system = system
        if self.oturum_hatasi:
            raise self.oturum_hatasi
        return self.oturum

    def gorev(self, ad):
        return _Rol(ad)


def test_video_adaptoru_sabit_rollere_hafizasiz_kapali_sorular_gonderir():
    oturum = _Oturum()
    istemci = _Istemci(oturum)

    sonuc = dogrula_video(istemci, b"kaynak-video")

    assert sonuc.supported
    assert istemci.video_system == DUSME_SISTEM
    assert [rol for rol, _kwargs in oturum.cagrilar] == [
        "algi", "olay", "olay", "olay",
    ]
    assert all(kwargs["guided_choice"] == ("A", "B", "C", "D")
               for _rol, kwargs in oturum.cagrilar)
    assert all(kwargs["temperature"] == 0.0 for _rol, kwargs in oturum.cagrilar)
    assert all(kwargs["max_tokens"] == DUSME_MAX_TOKENS
               for _rol, kwargs in oturum.cagrilar)
    assert all(kwargs["hatirla"] is False for _rol, kwargs in oturum.cagrilar)
    assert oturum.istemci is oturum.ilk_istemci


def test_atom_cagri_hatasi_diger_atomlari_engellemez_ama_alarm_uretmez():
    oturum = _Oturum({"transition": RuntimeError("gecici API hatasi")})
    istemci = _Istemci(oturum)

    sonuc = dogrula_video(istemci, b"video")

    assert sonuc.hukum == DusmeHukmu.INSUFFICIENT
    assert len(oturum.cagrilar) == 4
    assert "gecici API hatasi" in sonuc.hatalar["transition"]
    assert oturum.istemci is oturum.ilk_istemci


@pytest.mark.parametrize("istemci", [
    _Istemci(oturum_hatasi=RuntimeError("oturum acilamadi")),
    _Istemci(_Oturum(hazir=False, hata="servis hazir degil")),
])
def test_oturum_hatalari_istisna_siz_fail_closed_doner(istemci):
    sonuc = dogrula_video(istemci, "video.mp4")

    assert sonuc.hukum == DusmeHukmu.INSUFFICIENT
    assert "oturum" in sonuc.hatalar


def test_none_cevap_hata_kaydina_donusur():
    oturum = _Oturum({"outcome": None})
    istemci = _Istemci(oturum)

    sonuc = dogrula_video(istemci, b"video")

    assert sonuc.hukum == DusmeHukmu.INSUFFICIENT
    assert sonuc.hatalar["outcome"] == "cevap alinamadi"
