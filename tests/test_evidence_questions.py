#!/usr/bin/env python
"""KANIT SORULARI (ASK-HINT) testleri — GPU/vLLM GEREKTIRMEZ.

Bagimsiz calisir (pytest gerekmez):
    python tests/test_evidence_questions.py

Kapsam (gorev sartlari birebir):
  1  KAPALIYKEN (K2): prompt METINLERI ve VLM CAGRI SAYISI ozellik-ONCESI ile BIREBIR AYNI.
  2  ACIKKEN      : 4 ek IKILI soru cagrisi + 1 adlandirma cagrisi; sorular promptta geciyor;
                    betimleme/cikarim promptlari BIREBIR DEGISMIYOR (sorular SONRA soruluyor).
  3  YANIT AYRISTIRMA: "Evet" · "evet." · "Evet, iki kisi..." · "Hayır" · "Hayir" · "HAYIR" ·
                    "Bilmiyorum" · "" · sacma metin -> hepsi dogru sinifa dusuyor, cokme yok.
  4  BIRLESTIRME  : her yanit kombinasyonu -> beklenen ipucu (cakisma, hepsi-hayir, hepsi-evet).
  5  GUVENLIK (EN ONEMLI): tum sorulara "Evet" diyen sahte VLM + NORMAL klip -> soru bile
                    SORULMUYOR; olayli durumda da severity/kategori/risk/SEVK DEGISMIYOR.
  6  FAIL-OPEN (K3): soru cagrisi istisna atar / bos doner / bozuk JSON -> analiz TAMAMLANIYOR.
  7  SOZLESME (K1): to_sartname_dict() TAM 4 anahtar (acik ve kapali).
  8  UCTAN UCA (DILAJAN_MOCK=1): gercek klip, acik ve kapali, cokme yok.
  9  KONFIG/SET SAGLIGI: varsayilan KAPALI, env ile acilir, istek-kapsamli; soru setleri
                    <=5 soru, AYIRT EDICI gruplar ve benchmark/labels.py SEMANTIC_GROUPS uyumu.
"""
from __future__ import annotations

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import config as C  # noqa: E402
from tests.taban import taban_uygula

# TABAN DAVRANIS TESTI: gozlem duzlemi ve dedektorler ACIKCA kapali.
# Ortamdan miras alinmaz — sevk yapilandirmasi .env'e yazildiginda
# bu testler kirilmamalidir (bir kez kirildi).
taban_uygula()
from dilajan import evidence_questions as EQ  # noqa: E402
from dilajan import prompts  # noqa: E402
from dilajan.agent import graph as G  # noqa: E402
from dilajan.config import Settings, request_config, settings  # noqa: E402
from dilajan.schema import AnalysisResult, RiskAssessment, Severity  # noqa: E402

_FAILURES: list = []
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(cond: bool, label: str) -> None:
    print(("  [OK]   " if cond else "  [FAIL] ") + label)
    if not cond:
        _FAILURES.append(label)


# --------------------------------------------------------------- yardimcilar
class _Cfg:
    """`with _Cfg(alan=deger):` — settings alanlarini gecici degistirir, cikista geri yukler."""

    def __init__(self, **kw) -> None:
        self._kw = kw
        self._prev: dict = {}

    def __enter__(self):
        for k, v in self._kw.items():
            self._prev[k] = getattr(settings, k)
            setattr(settings, k, v)
        return settings

    def __exit__(self, *exc):
        for k, v in self._prev.items():
            setattr(settings, k, v)
        return False


def _jpeg(color: int = 0) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (color, color, color)).save(buf, format="JPEG")
    return buf.getvalue()


class _Seg:
    """graph._analyze_one_segment'in bekledigi minimum segment arayuzu (<3 kare -> motion cue sessiz)."""

    def __init__(self) -> None:
        self.index = 0
        self.start_str = "00:00"
        self.end_str = "00:10"
        self.frames = [("00:01", _jpeg()), ("00:05", _jpeg(80))]


#: Testlerde SABIT tutulan konfig — her kosuda ayni yol calisir (tek degisken: evidence_questions).
_KONTROL = dict(
    facility_rules="", use_detector=False, single_pass_perceive=False,
    threat_interpretation=True, motion_saliency_cue=True, restricted_zones="",
    detect_vehicles=False, detect_crowd=False, verify_events=True, spatial_grounding=True,
    semantic_plausibility=False, verify_pose_falls=False, batch_verify=False,
    claim_guard=False, atomic_claim_guard=False, narrative_event_policy="all",
    closed_family_fallback=False, structured_fire_dust_veto=False,
    thermal_fallback=False, physical_expert_fallback=False,
    analysis_query="", event_consistency_n=1, evidence_question_set="sokak",
)

_BETIM = ("Dış mekân; dar bir sokak. 00:03 civarında iki kişi birbirine yaklaşıyor ve "
          "aralarında ani, sert bir hareketlilik oluyor.")

#: Model cikarimindan gelen KRITIK olay (verify + grounding yollarini da kosturur).
_KRITIK_JSON = json.dumps({"events": [{
    "time": "00:03", "event": "Kadrajın ortasında ani ve sert bir hareketlilik gözlendi",
    "severity": "Kritik", "category": "Güvenlik"}]}, ensure_ascii=False)

#: Belirsiz (Orta) olay — guvenlik testinde severity/sevk degismezligi bunun uzerinde olculur.
_ORTA_JSON = json.dumps({"events": [{
    "time": "00:03", "event": "İki kişi arasında yakın fiziksel temas gözlendi",
    "severity": "Orta", "category": "Güvenlik"}]}, ensure_ascii=False)

_BOS_JSON = json.dumps({"events": []}, ensure_ascii=False)

_AD_KAVGA = "İki kişi arasında fiziksel kavga ve darp"
_AD_JSON = json.dumps({"adlar": [{"no": 1, "ad": _AD_KAVGA}]}, ensure_ascii=False)


def _tur(metin: str) -> str:
    """Sahte VLM'e gelen istemin turunu ayirt eder (test-ici yonlendirme)."""
    if "ADLANDIRILACAK GÖZLEMLER" in metin:
        return "adlandirma"
    if "SORU:" in metin:
        return "kanit"
    if "İddia edilen YÜKSEK ÖNEMLİ olay" in metin:
        return "verify"
    if "bbox_2d" in metin:
        return "ground"
    if "DİKKAT ÇEKİCİ olaylari çikar" in metin:
        return "extract"
    return "describe"


class _KanitVLM:
    """Cagrilari KAYDEDEN sahte VLM (ag/GPU yok). Kanit sorularina istenen yaniti verir."""

    def __init__(self, *, olay_json: str = _KRITIK_JSON, yanitlar=None,
                 varsayilan_yanit: str = "Hayır", ad_json: str = _AD_JSON,
                 soru_hatasi: bool = False, ad_hatasi: bool = False) -> None:
        self.cagrilar: list = []          # (tur, istem)
        self.olay_json = olay_json
        self.yanitlar = dict(yanitlar or {})
        self.varsayilan_yanit = varsayilan_yanit
        self.ad_json = ad_json
        self.soru_hatasi = soru_hatasi
        self.ad_hatasi = ad_hatasi

    def gorev(self, _gorev: str):
        return self

    # --- yardimci ---
    def _kanit_yaniti(self, istem: str) -> str:
        for soru in EQ.soru_seti(settings.evidence_question_set):
            if soru.metin[:40] in istem:
                return self.yanitlar.get(soru.sid, self.varsayilan_yanit)
        return self.varsayilan_yanit

    @property
    def turler(self) -> list:
        return [t for t, _ in self.cagrilar]

    def istem(self, tur: str, n: int = 0) -> str:
        eslesen = [p for t, p in self.cagrilar if t == tur]
        return eslesen[n] if len(eslesen) > n else ""

    # --- VLMClient arayuzu ---
    def analyze_frames(self, frames, instr, **kw) -> str:
        tur = _tur(instr)
        self.cagrilar.append((tur, instr))
        if tur == "kanit":
            if self.soru_hatasi:
                raise RuntimeError("model sunucusu yanit vermedi (test)")
            return self._kanit_yaniti(instr)
        if tur == "verify":
            return "EVET, gerçek bir güvenlik olayı."
        if tur == "ground":
            return "{}"
        return _BETIM

    def chat(self, messages, **kw) -> str:
        istem = messages[-1]["content"]
        tur = _tur(istem)
        self.cagrilar.append((tur, istem))
        if tur == "adlandirma":
            if self.ad_hatasi:
                raise RuntimeError("adlandirma cagrisi coktu (test)")
            return self.ad_json
        return self.olay_json


def _kos(vlm, **cfg):
    """`_analyze_one_segment`i kontrollu konfigle kosturur -> (olaylar, not)."""
    with _Cfg(**{**_KONTROL, **cfg}):
        return G._analyze_one_segment(vlm, _Seg())


def _beklenen_describe() -> str:
    """Ozellik EKLENMEDEN ONCEKI perceive (describe) istemi — K2 referansi."""
    seg = _Seg()
    return (prompts.SEGMENT_DESCRIBE_INSTRUCTION.format(start=seg.start_str, end=seg.end_str)
            + prompts.THREAT_LENS_SUFFIX)


# ---------------------------------------------------------------------- 1
def test_1_kapaliyken_birebir_ayni() -> None:
    print("1 — KAPALIYKEN (K2): prompt METNI ve CAGRI SAYISI ozellik-ONCESI ile AYNI")
    s = Settings(_env_file=None)
    check(s.evidence_questions is False, f"evidence_questions varsayilani KAPALI ({s.evidence_questions})")
    check(s.evidence_question_set == "sokak", f"soru seti varsayilani 'sokak' ({s.evidence_question_set})")

    vlm = _KanitVLM()
    events, note = _kos(vlm, evidence_questions=False)
    check(vlm.turler == ["describe", "extract", "verify", "ground"],
          f"cagri dizisi ozellik-ONCESI ile AYNI: {vlm.turler}")
    check(len(vlm.cagrilar) == 4, f"toplam VLM cagrisi 4 (ek cagri YOK): {len(vlm.cagrilar)}")
    check(vlm.istem("describe") == _beklenen_describe(),
          "betimleme istemi ozellik-ONCESI metinle BIREBIR AYNI (sifir sapma)")
    check(not any("SORU:" in p for _t, p in vlm.cagrilar),
          "hicbir isteme kanit sorusu SIZMADI")
    check(not any("ADLANDIRILACAK" in p for _t, p in vlm.cagrilar),
          "adlandirma istemi HIC kurulmadi")
    check(note is None, f"karar-izine SATIR BILE eklenmedi (note={note!r})")
    check(len(events) == 1 and events[0].event.startswith("Kadrajın ortasında"),
          "olay metni DEGISMEDI (kapali yolda yeniden adlandirma yok)")

    # Kapali iken yardimci fonksiyon da erken doner: TEK cagri bile yapmaz.
    vlm2 = _KanitVLM()
    with _Cfg(evidence_questions=False):
        evs, notes = G._kanit_adlandirma(vlm2, _Seg(), _BETIM, list(events))
    check(vlm2.cagrilar == [] and notes == [] and evs == events,
          "_kanit_adlandirma kapaliyken ILK SATIRDA donuyor (cagri/not/mutasyon yok)")


# ---------------------------------------------------------------------- 2
def test_2_acikken_ek_cagrilar() -> None:
    print("2 — ACIKKEN: 4 ikili soru + 1 adlandirma cagrisi; sorular istemde")
    ref = _KanitVLM()
    _kos(ref, evidence_questions=False)

    vlm = _KanitVLM(yanitlar={"S1": "Evet"})
    events, note = _kos(vlm, evidence_questions=True)
    check(vlm.turler == ["describe", "extract", "verify", "ground",
                         "kanit", "kanit", "kanit", "kanit", "adlandirma"],
          f"cagri dizisi: {vlm.turler}")
    check(len(vlm.cagrilar) - len(ref.cagrilar) == 5,
          f"ek cagri sayisi 5 = 4 soru + 1 adlandirma ({len(vlm.cagrilar)} - {len(ref.cagrilar)})")
    check(vlm.istem("describe") == ref.istem("describe") and vlm.istem("extract") == ref.istem("extract"),
          "betimleme ve olay-cikarim istemleri BIREBIR DEGISMEDI (sorular SONRA soruluyor)")

    sorular = EQ.soru_seti("sokak")
    kanit_istemleri = [p for t, p in vlm.cagrilar if t == "kanit"]
    check(len(kanit_istemleri) == len(sorular) == 4, f"{len(sorular)} soru, {len(kanit_istemleri)} cagri")
    check(all(s.metin in kanit_istemleri[i] for i, s in enumerate(sorular)),
          "her soru KENDI cagrisinda ve SIRAYLA soruldu (pool.map sirayi koruyor)")
    check(all("TEK KELİME" in p and "BİLİNMİYOR" in p for p in kanit_istemleri),
          "her soru istemi TEK KELIME yanit + BILINMIYOR secenegi iceriyor")
    check(all("EVET veya HAYIR" not in p for p in kanit_istemleri),
          "oz-dogrulama isteminin imzasi ('EVET veya HAYIR') KULLANILMADI (mock tur-tanima korunur)")

    ad_istemi = vlm.istem("adlandirma")
    check("kavga / fiziksel saldırı / darp" in ad_istemi, "ipucu (S1=Evet) adlandirma isteminde")
    check("Kadrajın ortasında ani ve sert" in ad_istemi, "mevcut olay adi numarali olarak istemde")
    check(_BETIM[:40] in ad_istemi, "sahne betimlemesi adlandirma istemine tasindi")
    check("-> EVET" in ad_istemi and "-> HAYIR" in ad_istemi,
          "soru->yanit tablosu istemde (model 'Hayır' denen kaniti ada yazamaz)")
    check("ÖNEM DERECESİ" in ad_istemi and "DEĞİŞMEYECEK" in ad_istemi,
          "istem severity ISTEMIYOR ve degismeyecegini soyluyor (promptta ikinci kilit)")

    check(events[0].event == _AD_KAVGA, f"olay ADI kanitla guncellendi: {events[0].event!r}")
    check(note and "kanıt soruları" in note and "S1(Siddet)=Evet" in note,
          f"karar-izinde sorular ve yanitlar var: {note!r}")
    check(note and "kanıt-adlandırma: 1/1" in note, "karar-izinde adlandirma sonucu var")


# ---------------------------------------------------------------------- 3
def test_3_yanit_ayristirma() -> None:
    print("3 — YANIT AYRISTIRMA: her yazim dogru sinifa dusuyor, cokme yok")
    beklenen = [
        ("Evet", EQ.EVET), ("evet.", EQ.EVET), ("EVET", EQ.EVET),
        ("Evet, iki kişi kavga ediyor.", EQ.EVET), ("  evet  ", EQ.EVET),
        ("Hayır", EQ.HAYIR), ("Hayir", EQ.HAYIR), ("HAYIR", EQ.HAYIR),
        ("hayır.", EQ.HAYIR), ("HAYIR, böyle bir şey yok.", EQ.HAYIR),
        ("Görüntüde ateş, alev, duman veya patlama var mı? HAYIR", EQ.HAYIR),
        ("Bilmiyorum", EQ.BILINMIYOR), ("BİLİNMİYOR", EQ.BILINMIYOR),
        ("Belirsiz", EQ.BILINMIYOR), ("emin değilim", EQ.BILINMIYOR),
        ("", EQ.BILINMIYOR), ("   ", EQ.BILINMIYOR),
        ("qwertyuiop", EQ.BILINMIYOR), ("42", EQ.BILINMIYOR),
        (None, EQ.BILINMIYOR), ({"a": 1}, EQ.BILINMIYOR), (["x"], EQ.BILINMIYOR),
    ]
    for ham, bek in beklenen:
        try:
            got = EQ.yanit_ayristir(ham)
        except Exception as ex:  # ayristirici ASLA cokmemeli
            got = f"ISTISNA: {ex}"
        check(got == bek, f"{ham!r:52s} -> {got!r} (beklenen {bek!r})")
    check(EQ.katla("HAYIR") == EQ.katla("Hayır") == EQ.katla("Hayir") == "hayir",
          "Turkce buyuk-I tuzagi: dort yazim da AYNI anahtara katlaniyor")
    # Mock modun taninmayan-istem yaniti (JSON) yanlislikla EVET/HAYIR sayilmamali
    check(EQ.yanit_ayristir('{"events": [], "calls": [], "actions": [], "sonuc": []}') == EQ.BILINMIYOR,
          "mock 'unknown' JSON yaniti -> BILINMIYOR (sahte kanit uretmiyor)")

    # --- TURKCE EKLEME (agglutinasyon) TUZAGI — adversaryel denetimde bulundu ---
    # `\bdegil\b` "degilim/degiliz/degildir"i KACIRIYORDU -> cekinceli yanit EVET sayiliyordu.
    for ham, bek in (("emin değilim ama evet", EQ.BILINMIYOR),
                     ("kesin değilim", EQ.BILINMIYOR),
                     ("net değildir", EQ.BILINMIYOR),
                     ("belli değil", EQ.BILINMIYOR),
                     ("öyle değilim", EQ.HAYIR),
                     ("böyle bir durum değildir", EQ.HAYIR),
                     ("yoktur", EQ.HAYIR), ("yoktu", EQ.HAYIR)):
        check(EQ.yanit_ayristir(ham) == bek,
              f"ekleme toleransi: {ham!r} -> {EQ.yanit_ayristir(ham)!r} (beklenen {bek!r})")
    check(EQ.yanit_ayristir("hayırlı işler") != EQ.HAYIR,
          "'hayırlı' HAYIR sayilmiyor (kok siniri korunuyor)")

    # --- SORU YANKISI TUZAGI — soru metninin KENDISI karar uretmemeli ---
    for setad, sorular in EQ.SORU_SETLERI.items():
        for s in sorular:
            check(s.metin.rstrip().endswith("?"),
                  f"[{setad}] {s.sid} soru metni '?' ile BITIYOR (yanki ayiklamasi bunu varsayar)")
            check(EQ.yanit_ayristir(s.metin) == EQ.BILINMIYOR,
                  f"[{setad}] {s.sid} yalniz soru yankilanirsa YANIT YOK -> BILINMIYOR")
            check(EQ.yanit_ayristir(s.metin + " EVET") == EQ.EVET,
                  f"[{setad}] {s.sid} yanki + EVET -> EVET")
            check(EQ.yanit_ayristir(s.metin + " HAYIR") == EQ.HAYIR,
                  f"[{setad}] {s.sid} yanki + HAYIR -> HAYIR")


# ---------------------------------------------------------------------- 4
def test_4_birlestirme() -> None:
    print("4 — BIRLESTIRME: yanit kombinasyonlari -> beklenen ipucu")
    S = EQ.soru_seti("sokak")

    hepsi_hayir = EQ.birlestir(S, ["Hayır"] * 4)
    check(hepsi_hayir.ipucu == "" and hepsi_hayir.durum == "kanit-yok",
          "HEPSI HAYIR -> ipucu URETILMEZ (ad degismez, ek cagri yapilmaz)")
    check("hiçbir soru EVET demedi" in hepsi_hayir.ozet_satiri, "ozet satiri durumu aciklıyor")

    tek = EQ.birlestir(S, ["Evet", "Hayır", "Hayır", "Hayır"])
    check(tek.durum == "ipucu" and tek.gruplar == ("Siddet",), f"TEK EVET -> {tek.gruplar}")
    check("kavga" in tek.ipucu and "darp" in tek.ipucu, "ipucu o grubun ADLARINI oneriyor")
    check("anormal durum" in tek.ipucu, "ipucu 'genel ifade kullanma' talimatini iceriyor")

    cift = EQ.birlestir(S, ["Evet", "Evet", "Hayır", "Hayır"])
    check(cift.durum == "ipucu" and cift.gruplar == ("Siddet", "Trafik"),
          f"IKI EVET (cakisma) -> her ikisi de yaziliyor: {cift.gruplar}")
    check("ÇELİŞEBİLİR" in cift.ipucu and "SEÇ" in cift.ipucu,
          "cakismada model 'gercekten gordugunu SEC' diye uyariliyor")

    hepsi_evet = EQ.birlestir(S, ["Evet"] * 4)
    check(hepsi_evet.ipucu == "" and hepsi_evet.durum == "cakisma",
          "HEPSI EVET -> ayirt edici degil, ipucu BASTIRILDI (yanlis-pozitif kapisi)")
    check(EQ.birlestir(S, ["Evet", "Evet", "Evet", "Hayır"]).ipucu == "",
          f"MAX_EVET={EQ.MAX_EVET} ustu her kombinasyon BASTIRILIYOR")

    belirsiz = EQ.birlestir(S, ["Bilmiyorum", "", "saçma", "Hayır"])
    check(belirsiz.ipucu == "" and belirsiz.durum == "kanit-yok",
          "BELIRSIZ/BOS/SACMA yanitlar hicbir yone kanit saymiyor")
    check(EQ.birlestir([], []).ipucu == "" and EQ.birlestir(S, []).ipucu == "",
          "bos soru/yanit listesi -> guvenli bos ozet (cokme yok)")
    check(EQ.birlestir(S, ["Evet"]).gruplar == ("Siddet",),
          "yanit sayisi soru sayisindan AZ olsa da cokmuyor (zip)")

    # DETERMINIZM: ayni girdi -> ayni cikti (saf fonksiyon)
    check(EQ.birlestir(S, ["Evet", "Hayır", "Hayır", "Hayır"]).ipucu == tek.ipucu,
          "DETERMINIZM: ayni yanitlar -> ayni ipucu")

    # VETO: "Hayır" denen kanit ada YAZILAMAZ
    ok, sebep = EQ.ad_kabul_edilebilir_mi("Binada yangın ve yoğun duman", tek)
    check(not ok and "S3" in sebep, f"yangin sorusu Hayır iken 'yangın' adi REDDEDILDI ({sebep})")
    check(EQ.ad_kabul_edilebilir_mi(_AD_KAVGA, tek)[0], "kanitla TUTARLI ad kabul ediliyor")
    check(not EQ.ad_kabul_edilebilir_mi("", tek)[0], "bos ad reddediliyor")
    check(not EQ.ad_kabul_edilebilir_mi("A" * 500, tek)[0], "asiri uzun ad reddediliyor")
    check(not EQ.ad_kabul_edilebilir_mi("两个人打架", tek)[0], "Turkce disi ad reddediliyor")
    check(EQ.ad_kabul_edilebilir_mi("Silahlı saldırı ve ateş açma", tek)[0],
          "SILAH/ATES adlari HICBIR veto listesinde yok -> engellenmiyor (Shooting kovalanmiyor)")
    check(not EQ.ad_kabul_edilebilir_mi("yangın", EQ.birlestir(S, ["Hayır"] * 4))[0],
          "ipucu olmasa da veto listesi hazir (cagiran taraf zaten adlandirma yapmaz)")


# ---------------------------------------------------------------------- 5
def test_5_guvenlik_kanit_alarmi_yukseltmiyor() -> None:
    print("5 — GUVENLIK (EN ONEMLI): kanit -> AD; kanit -/-> severity/risk/SEVK")

    # (a) NORMAL klip (olay yok) + TUM sorulara EVET diyen sahte VLM
    normal_off = _KanitVLM(olay_json=_BOS_JSON, varsayilan_yanit="Evet")
    ev_off, note_off = _kos(normal_off, evidence_questions=False)
    normal_on = _KanitVLM(olay_json=_BOS_JSON, varsayilan_yanit="Evet")
    ev_on, note_on = _kos(normal_on, evidence_questions=True)
    check(ev_off == ev_on == [], "normal klipte iki kolda da olay YOK")
    check(normal_on.turler == normal_off.turler == ["describe", "extract"],
          f"NORMAL klipte kanit sorusu HIC SORULMADI: {normal_on.turler}")
    check(note_on is None and note_off is None, "normal klipte karar-izi de BIREBIR AYNI")
    check(not any(t == "kanit" for t in normal_on.turler),
          "YAPISAL GARANTI: olay yoksa soru yok -> yanlis-alarm kapisi ACILAMAZ")

    # (b) Olay VARKEN: iki soruya EVET + korkutucu ad onerisi -> yalniz AD degisir
    korkutucu = json.dumps({"adlar": [{"no": 1, "ad": "İki kişi arasında ağır darp ve saldırı"}]},
                           ensure_ascii=False)
    vlm = _KanitVLM(olay_json=_ORTA_JSON, yanitlar={"S1": "Evet", "S2": "Evet"},
                    ad_json=korkutucu)
    once = _kos(_KanitVLM(olay_json=_ORTA_JSON), evidence_questions=False)[0][0]
    sonra = _kos(vlm, evidence_questions=True)[0][0]
    check(sonra.event != once.event, f"olay ADI degisti: {sonra.event!r}")
    for alan in ("severity", "category", "time", "end_time", "bbox", "region"):
        check(getattr(sonra, alan) == getattr(once, alan),
              f"'{alan}' alani BIREBIR AYNI ({getattr(once, alan)!r})")
    check(sonra.severity == Severity.ORTA,
          "ad 'darp/saldırı' dese bile severity YENIDEN KALIBRE EDILMIYOR (Orta kaldi)")
    check(sonra.model_dump(exclude={"event"}) == once.model_dump(exclude={"event"}),
          "TUM alanlar (event disinda) birebir esit — 'kanit -> yalniz AD' invaryanti")
    # ALARM MUHAFIZI: yeniden adlandirilan olay kanit-ONCESI metnini tasir; bu alan
    # SEMA ALANI DEGILDIR -> model_dump()/sozlesme anahtarlari DEGISMEZ.
    check(getattr(sonra, "evidence_prev", None) == once.event,
          f"evidence_prev kanit-oncesi metni sakliyor: {getattr(sonra, 'evidence_prev', None)!r}")
    check("evidence_prev" not in sonra.model_dump(),
          f"evidence_prev model_dump()a SIZMIYOR: {sorted(sonra.model_dump())}")
    check(getattr(once, "evidence_prev", None) is None,
          "kapali kolda evidence_prev HIC yazilmiyor")

    # (c) SEVK KAPISI: yeniden adlandirilmis olayla act() operasyonel cagri YAPMIYOR
    def _sevk(events, risk_level):
        sahte = _KanitVLM(olay_json=json.dumps({"calls": [
            {"function": "guvenlik_ekibi_uyar", "args": {"konum": "sokak", "sebep": "kavga"}}]}))
        eski = G._get_vlm
        G._get_vlm = lambda: sahte  # type: ignore[assignment]
        try:
            with _Cfg(risk_recall_bias=False, policy_dispatch=False):
                return G.act({"events": events,
                              "risk": RiskAssessment(level=risk_level, rationale="r"),
                              "trace": []})["triggered_functions"]
        finally:
            G._get_vlm = eski  # type: ignore[assignment]

    check(_sevk([sonra], Severity.ORTA) == [], "yeniden adlandirilmis Orta olay -> SEVK YOK")
    check(_sevk([once], Severity.ORTA) == [], "taban Orta olay -> SEVK YOK (ayni sonuc)")
    # KONTROL (testin bos olmadigini kanitlar): severity gercekten yukselse kapi ACILIRDI
    yuksek = once.model_copy(update={"severity": Severity.YUKSEK})
    check(_sevk([yuksek], Severity.YUKSEK) != [],
          "KONTROL: severity Yüksek olsaydi sevk kapisi ACILIRDI (test vacuous degil)")

    # (d) Tum sorulara EVET + olay VAR -> ipucu BASTIRILIR, adlandirma cagrisi bile yapilmaz
    hepsi = _KanitVLM(olay_json=_ORTA_JSON, varsayilan_yanit="Evet")
    ev_hepsi, note_hepsi = _kos(hepsi, evidence_questions=True)
    check("adlandirma" not in hepsi.turler,
          f"hepsine EVET -> adlandirma cagrisi YAPILMADI: {hepsi.turler}")
    check(ev_hepsi[0].event == once.event, "hepsine EVET diyen model olay adini DEGISTIREMEDI")
    check(note_hepsi and "BASTIRILDI" in note_hepsi, "bastirma karar-izine yazildi")

    # (e) VETO uctan uca: yangin sorusu Hayır iken model 'yangın' adi onerirse REDDEDILIR
    veto = _KanitVLM(olay_json=_ORTA_JSON, yanitlar={"S1": "Evet"},
                     ad_json=json.dumps({"adlar": [{"no": 1, "ad": "Binada yangın çıktı"}]},
                                        ensure_ascii=False))
    ev_veto, note_veto = _kos(veto, evidence_questions=True)
    check(ev_veto[0].event == once.event, "veto: kanitla CELISEN ad uygulanmadi, eski ad korundu")
    check(note_veto and "reddedildi" in note_veto, "red gerekcesi karar-izinde")


# ---------------------------------------------------------------------- 6
def test_6_fail_open() -> None:
    print("6 — FAIL-OPEN (K3): kanit yolu hatasi analizi COKERTMIYOR")
    taban = _kos(_KanitVLM(olay_json=_ORTA_JSON), evidence_questions=False)[0]

    # (a) soru cagrisi ISTISNA firlatiyor
    v = _KanitVLM(olay_json=_ORTA_JSON, soru_hatasi=True)
    evs, note = _kos(v, evidence_questions=True)
    check(evs[0].event == taban[0].event and len(evs) == 1,
          "soru cagrisi coktu -> olaylar DEGISMEDEN analiz tamamlandi")
    check("adlandirma" not in v.turler, "tum yanitlar BILINMIYOR -> adlandirma cagrisi yok")
    check(note and "kanıt soruları" in note, "durum karar-izine yazildi")

    # (b) adlandirma cagrisi ISTISNA firlatiyor
    v2 = _KanitVLM(olay_json=_ORTA_JSON, yanitlar={"S1": "Evet"}, ad_hatasi=True)
    evs2, note2 = _kos(v2, evidence_questions=True)
    check(evs2[0].event == taban[0].event, "adlandirma coktu -> olay adi DEGISMEDI")
    check(note2 and "atlandı" in note2, "K4: fail-open karar-izine yazildi")

    # (c) bozuk JSON / bos yanit / yanlis sema
    for etiket, payload in (("bozuk JSON", "bu JSON degil <<<>>>"),
                            ("bos yanit", ""),
                            ("yanlis sema", json.dumps({"sonuc": []})),
                            ("bozuk kayit", json.dumps({"adlar": [{"no": "x", "ad": 5}]}))):
        vv = _KanitVLM(olay_json=_ORTA_JSON, yanitlar={"S1": "Evet"}, ad_json=payload)
        ee, _n = _kos(vv, evidence_questions=True)
        check(len(ee) == 1 and ee[0].event == taban[0].event,
              f"{etiket} -> cokme yok, olay adi korundu")

    # (d) bozuk soru seti adi -> varsayilan sete duser
    vv = _KanitVLM(olay_json=_ORTA_JSON, yanitlar={"S1": "Evet"})
    ee, _n = _kos(vv, evidence_questions=True, evidence_question_set="OLMAYAN-SET")
    check(len([t for t in vv.turler if t == "kanit"]) == 4,
          "bilinmeyen soru seti -> VARSAYILAN set kullanildi (fail-open)")
    check(EQ.soru_seti(None) == EQ.soru_seti("") == EQ.soru_seti("sokak"),
          "None/bos set adi da varsayilana duser")

    # (e) bozuk prompt sablonu -> ipucu uygulanmaz ama analiz surer
    orijinal = prompts.EVIDENCE_NAMING_INSTRUCTION
    try:
        prompts.EVIDENCE_NAMING_INSTRUCTION = "BOZUK {bilinmeyen_alan}"
        v3 = _KanitVLM(olay_json=_ORTA_JSON, yanitlar={"S1": "Evet"})
        evs3, note3 = _kos(v3, evidence_questions=True)
        check(evs3[0].event == taban[0].event and note3, "bozuk sablon -> olaylar korundu, akis surdu")
    finally:
        prompts.EVIDENCE_NAMING_INSTRUCTION = orijinal


# ---------------------------------------------------------------------- 7
def test_7_sozlesme() -> None:
    print("7 — SOZLESME (K1): to_sartname_dict TAM 4 anahtar")
    for etiket, acik in (("kapali", False), ("acik", True)):
        vlm = _KanitVLM(yanitlar={"S1": "Evet"})
        evs, _n = _kos(vlm, evidence_questions=acik)
        res = AnalysisResult(summary="özet", events=evs,
                             risk=RiskAssessment(level=Severity.YUKSEK, rationale="r"),
                             actions=[])
        d = res.to_sartname_dict()
        check(sorted(d) == ["actions", "events", "risk", "summary"],
              f"[{etiket}] anahtarlar TAM ve SADECE {sorted(d)}")
        check(all(set(e) == {"time", "event"} for e in d["events"]),
              f"[{etiket}] events ogeleri yalniz {{time, event}}")
        check("kanıt" not in json.dumps(d, ensure_ascii=False).lower()
              and "ipucu" not in json.dumps(d, ensure_ascii=False).lower(),
              f"[{etiket}] kanit/ipucu meta verisi sartname ciktisina SIZMIYOR")


# ---------------------------------------------------------------------- 8
def _pick_clip() -> str:
    for rel in ("data/sample_data/01_yangin.mp4", "data/sample_data/02_dusme.mp4",
                "data/sample_data/03_arac_kazasi.mp4", "data/test_clip.mp4"):
        p = os.path.join(ROOT, rel)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return p
    return ""


def test_8_uctan_uca_mock() -> None:
    print("8 — UCTAN UCA (DILAJAN_MOCK=1): gercek klip, acik ve kapali")
    clip = _pick_clip()
    check(bool(clip), f"test klibi bulundu ({os.path.relpath(clip, ROOT) if clip else 'YOK'})")
    if not clip:
        return
    with _Cfg(mock_mode=True, verify_pose_falls=False, analysis_query="", evidence_questions=False):
        r0 = G.analyze_video(clip)
    with _Cfg(mock_mode=True, verify_pose_falls=False, analysis_query="", evidence_questions=True):
        r1 = G.analyze_video(clip)

    for etiket, r in (("kapali", r0), ("acik", r1)):
        check(isinstance(r, AnalysisResult), f"[{etiket}] AnalysisResult dondu (cokme yok)")
        check(sorted(r.to_sartname_dict()) == ["actions", "events", "risk", "summary"],
              f"[{etiket}] sozlesme TAM 4 anahtar")
        check(r.risk.level.value in [s.value for s in Severity], f"[{etiket}] risk gecerli seviye")
    check(not any("kanıt soruları" in t for t in r0.decision_trace),
          "KAPALI kosuda karar-izinde kanit satiri YOK (regresyon)")
    if r1.events:
        check(any("kanıt soruları" in t for t in r1.decision_trace),
              "ACIK kosuda (olay varken) karar-izinde kanit satiri VAR")
        check(any("ipucu ÜRETİLMEDİ" in t or "BASTIRILDI" in t or "kanıt-adlandırma" in t
                  for t in r1.decision_trace),
              "kanit sonucunun ne oldugu karar-izinde ACIKCA yaziyor")
    else:
        check(not any("kanıt soruları" in t for t in r1.decision_trace),
              "olay uretilmeyen mock kosuda soru da sorulmadi (G2)")


# ---------------------------------------------------------------------- 9
def test_9_konfig_ve_set_sagligi() -> None:
    print("9 — KONFIG (K5) + SORU SETI SAGLIGI")
    check("evidence_questions" in C.REQUEST_SCOPED_FIELDS
          and "evidence_question_set" in C.REQUEST_SCOPED_FIELDS,
          f"iki alan da REQUEST_SCOPED_FIELDS icinde ({C.REQUEST_SCOPED_FIELDS[-2:]})")
    base = settings.evidence_questions
    with request_config(evidence_questions=True, evidence_question_set="tesis"):
        check(settings.evidence_questions is True and settings.evidence_question_set == "tesis",
              "istek icinde override etkin")
    check(settings.evidence_questions == base, "istek bitince ESKI deger geri yuklendi (sizinti yok)")

    os.environ["DILAJAN_EVIDENCE_QUESTIONS"] = "1"
    try:
        check(Settings(_env_file=None).evidence_questions is True,
              "DILAJAN_EVIDENCE_QUESTIONS ortam degiskeniyle acilabiliyor")
    finally:
        os.environ.pop("DILAJAN_EVIDENCE_QUESTIONS", None)

    from benchmark.labels import SEMANTIC_GROUPS  # noqa: E402  (etiket sozlugu ile TUTARLILIK)

    for ad, sorular in EQ.SORU_SETLERI.items():
        n = len(sorular)
        check(1 <= n <= 5, f"[{ad}] soru sayisi {n} (literatur: cok soru ZARARLI, tavan 5)")
        gruplar = [s.grup for s in sorular]
        check(len(set(gruplar)) == n, f"[{ad}] her soru FARKLI grubu ayiriyor: {gruplar}")
        check(all(g in SEMANTIC_GROUPS for g in gruplar),
              f"[{ad}] grup adlari benchmark/labels.py SEMANTIC_GROUPS ile TUTARLI")
        check(all(s.kategoriler and all(k in SEMANTIC_GROUPS[s.grup] for k in s.kategoriler)
                  for s in sorular),
              f"[{ad}] her sorunun kategorileri kendi semantik grubunun UYESI")
        check(len(set(s.sid for s in sorular)) == n, f"[{ad}] soru kimlikleri benzersiz")
        check(all(s.metin.strip().endswith("?") or "?" in s.metin for s in sorular),
              f"[{ad}] tum sorular IKILI soru bicimindeymis gibi soruluyor")
    check(all("silah" not in EQ.katla(k) and "ates" not in EQ.katla(k)
              for s in EQ.SORU_SETLERI["sokak"] for k in s.kokler),
          "Shooting BILEREK kovalanmiyor: silah/ates hicbir veto kokunde yok")


# --------------------------------------------------------------------- 10
class _HakemVLM:
    """`reexamine` hakemi: istemi KAYDEDER ve OLAY METNINE gore karar verir.
    Gercek bir VLM'in metne duyarliligini modeller (adversaryel denetimde olculdu)."""

    _ALARM = ("kavga", "darp", "saldır")

    def __init__(self) -> None:
        self.istemler: list = []

    def gorev(self, _gorev: str):
        return self

    def analyze_frames(self, frames, instr, **kw) -> str:
        self.istemler.append(instr)
        return "CIDDI" if any(k in instr.lower() for k in self._ALARM) else "BELIRSIZ"

    def chat(self, messages, **kw) -> str:
        return "{}"


def test_10_alarm_muhafizi() -> None:
    print("10 — ALARM MUHAFIZI (adversaryel denetim onarimi): kanit adi severity/SEVK ACAMAZ")
    from dilajan.schema import Event, EventCategory

    taban = Event(time="00:03", event="Kadrajın sağında kısa süreli bir hareketlilik",
                  severity=Severity.ORTA, category=EventCategory.ANOMALI)
    # Kanit sorulariyla yeniden adlandirilmis hali (graph._kanit_ile_adlandir ile AYNI desen)
    adli = taban.model_copy(update={"event": _AD_KAVGA, "evidence_prev": taban.event})

    def _reex(ev):
        vlm = _HakemVLM()
        eski = G._get_vlm
        G._get_vlm = lambda: vlm  # type: ignore[assignment]
        try:
            with _Cfg(adaptive_reexamine=True):
                out = G.reexamine({"events": [ev], "segments": [_Seg()], "trace": []})
        finally:
            G._get_vlm = eski  # type: ignore[assignment]
        return out["events"][0], vlm.istemler

    ev_taban, istem_taban = _reex(taban)
    ev_adli, istem_adli = _reex(adli)
    check(istem_taban == istem_adli,
          "reexamine ISTEMI yeniden adlandirmadan ETKILENMIYOR (byte-esit)")
    check(_AD_KAVGA not in "".join(istem_adli),
          "yeni (alarmli) ad reexamine istemine GIRMIYOR")
    check(taban.event in "".join(istem_adli), "hakem kanit-ONCESI metni goruyor")
    check(ev_adli.severity == ev_taban.severity == Severity.ORTA,
          f"severity YUKSELMEDI (taban {ev_taban.severity}, adli {ev_adli.severity})")
    check(ev_adli.event == _AD_KAVGA, "olayin GORUNEN adi yine de yeni ad (ozellik calisiyor)")
    # KONTROL: muhafaza olmasaydi hakem YUKSELTIRDI (test vacuous degil)
    muhafazasiz = taban.model_copy(update={"event": _AD_KAVGA})
    check(_reex(muhafazasiz)[0].severity == Severity.YUKSEK,
          "KONTROL: muhafiz olmasaydi severity Orta->YUKSEK olurdu (kusur gercekti)")

    # (b) SEVK KAPISI: risk Yuksek + tum olaylar Orta + adlandirma yapildi -> SEVK YOK
    def _act(events, renamed):
        sahte = _KanitVLM(olay_json=json.dumps({"calls": [
            {"function": "guvenlik_ekibi_uyar", "args": {"konum": "s", "sebep": "k"}}]}))
        eski = G._get_vlm
        G._get_vlm = lambda: sahte  # type: ignore[assignment]
        try:
            with _Cfg(risk_recall_bias=False, policy_dispatch=False):
                return G.act({"events": events, "evidence_renamed": renamed,
                              "risk": RiskAssessment(level=Severity.YUKSEK, rationale="r"),
                              "trace": []})["triggered_functions"]
        finally:
            G._get_vlm = eski  # type: ignore[assignment]

    check(_act([adli], True) == [],
          "risk Yüksek + olaylar Orta + kanit-adlandirma -> RISK TERIMI MASKELENDI, SEVK YOK")
    check(_act([taban], False) != [],
          "KONTROL: ayni durumda bayrak False iken sevk ACILIR (maske gercekten calisiyor)")
    check(_act([adli.model_copy(update={"severity": Severity.YUKSEK})], True) != [],
          "GERCEK Yüksek olay -> maske SEVKI ENGELLEMEZ (recall korunur)")

    # (c) MUHAFIZ dedupe/persist zincirinde KAYBOLMUYOR
    d = G._dedupe_events([adli])
    check(getattr(d[0], "evidence_prev", None) == taban.event,
          "dedupe sonrasi muhafiz korunuyor")
    with _Cfg(persist_escalation=True):
        yayilan = adli.model_copy(update={"end_time": "00:20",
                                          "category": EventCategory.GUVENLIK})
        d2 = G._dedupe_events([yayilan])
    check(getattr(d2[0], "evidence_prev", None) == taban.event,
          "persist_escalation (Orta->Yüksek) sonrasi muhafiz korunuyor")

    # (c2) N-KEZ ALGI (event_consistency_n>1) KAPSAM DISI — hem cogunluk-oyunu bozmasin
    #      hem de ek cagri N ile carpilmasin (olculdu: 6 -> 18 cagri = 3.0x, K4 tavani).
    v_n1 = _KanitVLM(olay_json=_ORTA_JSON, varsayilan_yanit="Hayır")
    with _Cfg(**{**_KONTROL, "evidence_questions": True, "event_consistency_n": 3}):
        _e, note_n3 = G._segment_consistent_events(v_n1, _Seg(), 3)
    check("kanit" not in v_n1.turler,
          f"event_consistency_n=3 iken kanit sorusu SORULMADI: {v_n1.turler}")
    check(note_n3 and "N-KEZ ALGIDA uygulanmadı" in note_n3,
          "kapsam disi kalmasi karar-izine YAZILDI (sessiz atlamiyor)")
    v_off = _KanitVLM(olay_json=_ORTA_JSON, varsayilan_yanit="Hayır")
    with _Cfg(**{**_KONTROL, "evidence_questions": False, "event_consistency_n": 3}):
        G._segment_consistent_events(v_off, _Seg(), 3)
    check(len(v_n1.cagrilar) == len(v_off.cagrilar),
          f"n=3'te ACIK ve KAPALI cagri sayisi AYNI ({len(v_n1.cagrilar)} = {len(v_off.cagrilar)})")

    # (d) KAPALI kolda bayrak HER ZAMAN False
    vlm = _KanitVLM(olay_json=_ORTA_JSON, yanitlar={"S1": "Evet"})
    evs, _n = _kos(vlm, evidence_questions=False)
    check(not any(getattr(e, "evidence_prev", None) for e in evs),
          "kapali kolda hicbir olayda muhafiz alani yok -> evidence_renamed=False")


def main() -> int:
    for fn in (test_1_kapaliyken_birebir_ayni, test_2_acikken_ek_cagrilar,
               test_3_yanit_ayristirma, test_4_birlestirme,
               test_5_guvenlik_kanit_alarmi_yukseltmiyor, test_6_fail_open,
               test_7_sozlesme, test_8_uctan_uca_mock, test_9_konfig_ve_set_sagligi,
               test_10_alarm_muhafizi):
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
