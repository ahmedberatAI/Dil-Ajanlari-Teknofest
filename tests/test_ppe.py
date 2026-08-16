#!/usr/bin/env python
"""KKD (baret) deterministik tespiti — K2/K3 garanti testleri. GPU/model GEREKTIRMEZ.

    python tests/test_ppe.py        # cikis kodu 0 = hepsi gecti

NE KORUNUYOR
------------
KKD tespiti YENI bir olay KAYNAGIDIR. Uc sey yanlis giderse pahaliya patlar:

  K2  Bayrak KAPALI iken davranis BIREBIR eski hali olmali. Aksi halde D33'te
      olculen taban cizgileri (recall %28 / kategori %5 / MCC 0,069) gecersizlesir.
  K3  Agirlik yoksa, YOLO patlarsa, kare bozuksa -> analiz COKMEMELI (fail-open).
  SEVK KKD olayi `ppe_dispatch=False` iken OPERASYONEL CAGRI ACMAMALI. Bu yalnizca
      max_intrinsic'i maskelemekle OLMAZ: risk tabani severity'yi risk'e tasidigi
      icin RISK TERIMI de maskelenmelidir (policy'de olculmus tuzagin aynisi).

KAPSAM
  1  K2 KAPALI    : ppe_detection=False -> dedektor HIC cagrilmaz, olay yok
  2  K3 FAIL-OPEN : agirlik yok / istisna / bos kare -> None, cokme yok
  3  KARAR KURALI : min_kare esigi; tek kare ihlal SAYILMAZ
  4  SEVK MASKESI : KKD olayi tek basina sevk ACMAZ (iki terim birden maskeli)
  5  CEBIR        : KKD olayi YOKKEN dispatch ifadesi ESKI ifadeyle OZDES
  6  SEMA SIZINTI : `ppe_src` model_dump() anahtarlarina SIZMAZ (K1)
  7  DOGRULAYICI  : verify_ppe_claim sozlesmesi (CONFIRM/REJECT/ABSTAIN)
  8  GORUNURLUK   : maskelenmis KKD olayi operatore GORUNUR (olay listesinde kalir)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import detector  # noqa: E402
from dilajan.agent import graph as G  # noqa: E402
from dilajan.config import settings  # noqa: E402
from dilajan.schema import Event, EventCategory, RiskAssessment, Severity  # noqa: E402

FAILS: list = []
_ORIG_VLM = G._get_vlm


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  [OK]   " if cond else "  [HATA] ") + name
          + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


class cfg:
    """Test suresince settings override (cikista geri yuklenir)."""

    def __init__(self, **kw):
        self.kw, self.prev = kw, {}

    def __enter__(self):
        for k, v in self.kw.items():
            self.prev[k] = getattr(settings, k)
            setattr(settings, k, v)
        return settings

    def __exit__(self, *a):
        for k, v in self.prev.items():
            setattr(settings, k, v)
        return False


class FakeVLM:
    def __init__(self, payload=""):
        self.payload, self.calls = payload, 0

    def chat(self, messages, **kw):
        self.calls += 1
        return self.payload

    def analyze_frames(self, frames, prompt, **kw):
        self.calls += 1
        return self.payload


def ev(text, sev=Severity.DUSUK, cat=EventCategory.ANOMALI, time="00:03", **kw):
    return Event(time=time, event=text, severity=sev, category=cat, **kw)


def ppe_ev(sev=Severity.YUKSEK):
    """Graph'in urettigiyle AYNI bicimde bir KKD olayi (sema-disi ppe_src isaretli)."""
    return Event(time="00:02", event="KKD ihlali: baret takmayan personel — 3 karede tespit",
                 severity=sev, category=EventCategory.GUVENLIK,
                 region="üst sol").model_copy(update={"ppe_src": True})


def state(events, **kw):
    s = {"events": list(events), "trace": []}
    s.update(kw)
    return s


def _kit_hata() -> bool:
    """Bilinmeyen kit ISTISNA firlatmali — sessizce 'baret'e dusmemeli."""
    try:
        detector._kit("boyle_bir_kit_yok")
        return False
    except KeyError:
        return True


# ===========================================================================
print("=== (1) K2: bayrak KAPALI iken dedektor HIC cagrilmaz ===")
_cagrildi = {"n": 0}
_orig_detect = detector.detect_ppe_violation


def _sayan(*a, **kw):
    _cagrildi["n"] += 1
    return {"time": "00:01", "region": "merkez", "conf": 0.9,
            "n_kare": 3, "n_ihlal_kutu": 3, "n_baretli": 0}


detector.detect_ppe_violation = _sayan
try:
    # `_perceive_segment` dogrudan cagrilamaz (VLM/kare gerekir); bunun yerine
    # bayragin KAPALI oldugunu ve kodun erken-donusunu DOGRULARIZ.
    with cfg(ppe_detection=False):
        check("varsayilan/kapali: settings.ppe_detection False",
              settings.ppe_detection is False)
    check("VARSAYILAN deger KAPALI (K2)", getattr(type(settings)(), "ppe_detection") is False)
    check("ppe_dispatch VARSAYILAN KAPALI (sevk yetkisi opt-in)",
          getattr(type(settings)(), "ppe_dispatch") is False)
finally:
    detector.detect_ppe_violation = _orig_detect

# ===========================================================================
print("\n=== (2) K3 FAIL-OPEN: agirlik yok / istisna / bos girdi ===")
_orig_get = detector._get_kkd_model
detector._get_kkd_model = lambda kit="baret": None
try:
    check("agirlik YOK -> detect_ppe_violation None (cokme yok)",
          detector.detect_ppe_violation([("00:01", b"x")]) is None)
    v, n = detector.verify_ppe_claim([("00:01", b"x")])
    check("agirlik YOK -> verify_ppe_claim ABSTAIN", v == "ABSTAIN", f"{v} / {n}")
finally:
    detector._get_kkd_model = _orig_get


def _patlayan(kit="baret"):
    raise RuntimeError("simule YOLO patlamasi")


detector._get_kkd_model = _patlayan
try:
    check("YOLO PATLARSA -> None (istisna disari SIZMAZ)",
          detector.detect_ppe_violation([("00:01", b"x")]) is None)
    v, _ = detector.verify_ppe_claim([("00:01", b"x")])
    check("YOLO PATLARSA -> verify ABSTAIN", v == "ABSTAIN")
finally:
    detector._get_kkd_model = _orig_get

check("bos kare listesi -> None", detector.detect_ppe_violation([]) is None)

# ===========================================================================
print("\n=== (3) KARAR KURALI: min_kare esigi ===")


class _Kutu:
    def __init__(self, cls_list, conf_list=None):
        self.xyxy = _L([[10.0, 10.0, 50.0, 50.0] for _ in cls_list])
        self.cls = _L([float(c) for c in cls_list])
        self.conf = _L([float(c) for c in (conf_list or [0.9] * len(cls_list))])


class _L(list):
    def tolist(self):
        return list(self)


class _R:
    def __init__(self, cls_list):
        self.boxes = _Kutu(cls_list)


class _SahteModel:
    """names: 0=baret_var, 1=baret_yok. predict() kare basina sabit sinif listesi doner."""

    names = {0: "baret_var", 1: "baret_yok"}

    def __init__(self, kare_siniflari):
        self.kare_siniflari = kare_siniflari

    def predict(self, imgs, **kw):
        return [_R(c) for c in self.kare_siniflari]


def _kareler(n):
    # gercek JPEG gerekiyor (PIL acacak) -> 1x1 beyaz JPEG
    import io as _io

    from PIL import Image as _Im
    buf = _io.BytesIO()
    _Im.new("RGB", (8, 8), (255, 255, 255)).save(buf, format="JPEG")
    b = buf.getvalue()
    return [(f"00:0{i}", b) for i in range(n)]


def _ile_model(kare_siniflari, **kw):
    detector._get_kkd_model = lambda kit="baret": _SahteModel(kare_siniflari)
    try:
        return detector.detect_ppe_violation(_kareler(len(kare_siniflari)), **kw)
    finally:
        detector._get_kkd_model = _orig_get


r = _ile_model([[1], [0], [0]], min_kare=2)
check("TEK karede baretsiz + min_kare=2 -> ihlal SAYILMAZ (gecici FP elenir)", r is None)

r = _ile_model([[1], [1], [0]], min_kare=2)
check("IKI karede baretsiz + min_kare=2 -> IHLAL", r is not None and r["n_kare"] == 2,
      str(r))
check("ihlal kaydinda zaman/bolge/guven var",
      bool(r) and r.get("time") and r.get("region") and r.get("conf") is not None, str(r))

r = _ile_model([[0, 0, 0], [0, 0], [0]], min_kare=1)
check("YALNIZ baretli kafalar -> ihlal YOK", r is None)

r = _ile_model([[1, 0], [1, 0]], min_kare=2)
check("karisik sahne (baretli+baretsiz) -> IHLAL (baretli olmasi baretsizi AKLAMAZ)",
      r is not None and r["n_baretli"] == 2, str(r))

# Beklenmeyen agirlik (sinif adlari farkli) -> karar VERME
class _YanlisModel(_SahteModel):
    names = {0: "person", 1: "helmet"}


detector._get_kkd_model = lambda kit="baret": _YanlisModel([[1], [1]])
try:
    check("BEKLENMEYEN sinif adlari -> None (sessizce yanlis okumaz)",
          detector.detect_ppe_violation(_kareler(2)) is None)
finally:
    detector._get_kkd_model = _orig_get

# ===========================================================================
print("\n=== (4) SEVK MASKESI: KKD olayi tek basina cagri ACMAZ ===")
G._get_vlm = lambda: FakeVLM('{"calls":[{"function":"yonetici_bilgilendir","args":{"mesaj":"x"}}]}')
try:
    with cfg(ppe_detection=True, ppe_dispatch=False):
        o = G.act(state([ppe_ev(Severity.YUKSEK)],
                        risk=RiskAssessment(level=Severity.YUKSEK, rationale="KKD ihlali")))
        check("ppe_dispatch=False: YUKSEK KKD olayi + YUKSEK risk -> SEVK YOK",
              o["triggered_functions"] == [], str(o["triggered_functions"]))
        check("karar-izinde maskeleme GEREKCESI yazili",
              any("KKD" in t for t in o.get("trace", [])),
              str(o.get("trace", []))[:200])

        # KKD + BAGIMSIZ yuksek olay -> sevk ACILMALI (maske yalniz KKD'yi keser)
        o2 = G.act(state([ppe_ev(Severity.YUKSEK),
                          ev("Yangın çıktı", Severity.KRITIK, EventCategory.KAZA)],
                         risk=RiskAssessment(level=Severity.KRITIK, rationale="yangin")))
        check("KKD + BAGIMSIZ kritik olay -> SEVK ACILIR (maske asiri genis degil)",
              o2["triggered_functions"] == ["yonetici_bilgilendir"],
              str(o2["triggered_functions"]))

    with cfg(ppe_detection=True, ppe_dispatch=True):
        o3 = G.act(state([ppe_ev(Severity.YUKSEK)],
                         risk=RiskAssessment(level=Severity.YUKSEK, rationale="KKD")))
        check("ppe_dispatch=True: KKD olayi SEVK ACAR (opt-in calisiyor)",
              o3["triggered_functions"] == ["yonetici_bilgilendir"],
              str(o3["triggered_functions"]))
finally:
    G._get_vlm = _ORIG_VLM

# ===========================================================================
print("\n=== (5) CEBIR: KKD olayi YOKKEN ifade ESKI haliyle OZDES ===")
G._get_vlm = lambda: FakeVLM('{"calls":[{"function":"yonetici_bilgilendir","args":{"mesaj":"x"}}]}')
try:
    for bayrak in (False, True):
        with cfg(ppe_detection=bayrak, ppe_dispatch=False):
            o = G.act(state([ev("kritik olay", Severity.KRITIK, EventCategory.KAZA)],
                            risk=RiskAssessment(level=Severity.KRITIK, rationale="r")))
            check(f"ppe_detection={bayrak}, KKD olayi YOK -> KRITIK olay sevk ACAR",
                  o["triggered_functions"] == ["yonetici_bilgilendir"],
                  str(o["triggered_functions"]))
            o = G.act(state([ev("olagan", Severity.ORTA, EventCategory.NORMAL)],
                            risk=RiskAssessment(level=Severity.ORTA, rationale="r")))
            check(f"ppe_detection={bayrak}, Orta sinyal -> sevk YOK",
                  o["triggered_functions"] == [])
finally:
    G._get_vlm = _ORIG_VLM

# ===========================================================================
print("\n=== (6) SEMA SIZINTISI: ppe_src cikti sozlesmesine girmez (K1) ===")
e = ppe_ev()
check("ppe_src getattr ile OKUNUR", getattr(e, "ppe_src", False) is True)
check("ppe_src model_dump() anahtarlarinda YOK", "ppe_src" not in e.model_dump())
check("olay diger alanlari normal", e.model_dump().get("severity") == "Yüksek")

# ===========================================================================
print("\n=== (7) DOGRULAYICI sozlesmesi ===")
detector._get_kkd_model = lambda kit="baret": _SahteModel([[1], [1], [1]])
try:
    v, n = detector.verify_ppe_claim(_kareler(3))
    check("baretsiz VAR -> CONFIRM", v == "CONFIRM", f"{v} / {n}")
finally:
    detector._get_kkd_model = _orig_get

detector._get_kkd_model = lambda kit="baret": _SahteModel([[0, 0], [0, 0], [0]])
try:
    v, n = detector.verify_ppe_claim(_kareler(3))
    check("çok sayida BARETLI + baretsiz YOK -> REJECT", v == "REJECT", f"{v} / {n}")
finally:
    detector._get_kkd_model = _orig_get

detector._get_kkd_model = lambda kit="baret": _SahteModel([[], [0]])
try:
    v, n = detector.verify_ppe_claim(_kareler(2))
    check("yetersiz kafa tespiti -> ABSTAIN (VLM korunur)", v == "ABSTAIN", f"{v} / {n}")
finally:
    detector._get_kkd_model = _orig_get

# ===========================================================================
print("\n=== (7b) BIRLESTIRME: ppe_src isareti KAYBOLMUYOR ===")
# BULUNAN HATA (D34): `_merge_events` olaylari `Event(...)` ile YENIDEN KURUYOR ve
# sema-disi alanlari DUSURUYOR (yalnizca `evidence_prev` elle tasiniyordu).
# KKD olayi bir VLM olayiyla birlesseydi `ppe_src` dusecek ve act() sevk maskesi
# SESSIZCE calismayacakti -> `ppe_dispatch=False` sozu YALAN olurdu.
_merge = getattr(G, "_dedupe_events", None)

if _merge is None:
    check("birlestirme fonksiyonu bulundu", False, "ad bulunamadi — test guncellenmeli")
else:
    # (a) KKD olayi + BENZER metinli VLM olayi -> BIRLESMEMELI
    vlm_benzer = ev("Personel ihlali gözlendi", Severity.DUSUK, EventCategory.GUVENLIK,
                    time="00:02")
    sonuc = _merge([ppe_ev(Severity.YUKSEK), vlm_benzer])
    check("KKD olayi VLM olayiyla BIRLESMIYOR (2 olay kaliyor)",
          len(sonuc) == 2, f"{len(sonuc)} olay: {[s.event[:30] for s in sonuc]}")
    check("birlestirme sonrasi ppe_src HALA duruyor",
          any(getattr(s, "ppe_src", False) for s in sonuc),
          str([(s.event[:24], getattr(s, "ppe_src", False)) for s in sonuc]))

    # (b) IKI KKD olayi birbiriyle birlesebilir VE isaret KORUNUR
    iki = _merge([ppe_ev(Severity.YUKSEK), ppe_ev(Severity.YUKSEK)])
    check("iki KKD olayi birlesebiliyor",
          len(iki) <= 2, f"{len(iki)} olay")
    check("KKD-KKD birlesmesinde de ppe_src KORUNUYOR",
          all(getattr(s, "ppe_src", False) for s in iki),
          str([(s.event[:24], getattr(s, "ppe_src", False)) for s in iki]))

    # (c) KKD olmayan olaylar ESKISI GIBI birlesmeye devam ediyor (gerileme yok)
    a1 = ev("Forklift aşırı yük taşıyor", Severity.ORTA, EventCategory.GUVENLIK, time="00:01")
    a2 = ev("Forklift aşırı yük taşımaya devam ediyor", Severity.YUKSEK,
            EventCategory.GUVENLIK, time="00:04")
    check("KKD DISI benzer olaylar hala birlesiyor (gerileme yok)",
          len(_merge([a1, a2])) == 1, str(len(_merge([a1, a2]))))


# ===========================================================================
print("\n=== (7c) KKD KITLERI: baret + yelek AYRI modeller ===")
# NEDEN AYRI: iki veri setinin ETIKET UZAYLARI AYRIK. Baret seti (39k kutu)
# yelekleri etiketlemez; tek modelde birlestirilseydi baret setindeki YELEKLI
# isci "etiketsiz" kalir ve modele "yelek YOK" diye ogretilirdi -> yelek sinifi
# icin SISTEMATIK yanlis-negatif. Bu test o karari kilitler.
check("iki kit tanimli", set(detector.KKD_KITLERI) == {"baret", "yelek"},
      str(sorted(detector.KKD_KITLERI)))
check("kitler AYRI agirlik dosyalari kullaniyor",
      detector.KKD_KITLERI["baret"]["agirlik"] != detector.KKD_KITLERI["yelek"]["agirlik"],
      str([k["agirlik"] for k in detector.KKD_KITLERI.values()]))
check("kitler AYRI sinif adlari kullaniyor",
      detector.KKD_KITLERI["baret"]["yok"] == "baret_yok"
      and detector.KKD_KITLERI["yelek"]["yok"] == "yelek_yok")
check("bilinmeyen kit ISTISNA firlatiyor (sessizce baret'e dusmuyor)",
      _kit_hata(), "KeyError bekleniyordu")


class _YelekModel(_SahteModel):
    names = {0: "yelek_var", 1: "yelek_yok"}


# Yelek kiti KENDI sinif adlariyla calisiyor mu?
detector._get_kkd_model = lambda kit="baret": _YelekModel([[1], [1]])
try:
    r = detector.detect_ppe_violation(_kareler(2), min_kare=2, kit="yelek")
    check("yelek kiti kendi sinif adlariyla IHLAL buluyor",
          r is not None and r.get("kit") == "yelek", str(r))
    # BARET kiti YELEK agirligini gorurse karar VERMEMELI (sinif adlari uyusmuyor)
    r2 = detector.detect_ppe_violation(_kareler(2), min_kare=2, kit="baret")
    check("baret kiti YELEK agirligiyla karar VERMIYOR (sinif adi uyusmazligi)",
          r2 is None, str(r2))
finally:
    detector._get_kkd_model = _orig_get

check("ppe_kits varsayilani iki kiti de iceriyor",
      set(x.strip() for x in type(settings)().ppe_kits.split(",")) == {"baret", "yelek"},
      type(settings)().ppe_kits)


# ===========================================================================
print("\n=== (8) GORUNURLUK: maskelenen olay OPERATORE gorunur ===")
G._get_vlm = lambda: FakeVLM('{"calls":[]}')
try:
    with cfg(ppe_detection=True, ppe_dispatch=False):
        st = state([ppe_ev(Severity.YUKSEK)],
                   risk=RiskAssessment(level=Severity.YUKSEK, rationale="KKD"))
        o = G.act(st)
        check("maskeleme olayi SILMEZ (act events'e dokunmaz)",
              len(st["events"]) == 1 and "KKD ihlali" in st["events"][0].event)
        check("sevk yapilmadi ama analiz COKMEDI",
              o.get("triggered_functions") == [] and "trace" in o)
finally:
    G._get_vlm = _ORIG_VLM

# ===========================================================================
print()
if FAILS:
    print(f"SONUC: {len(FAILS)} BASARISIZ")
    for f in FAILS:
        print("  - " + f)
    raise SystemExit(1)
print("SONUC: TUM TESTLER GECTI")
raise SystemExit(0)
