"""Storyboard, kaynak mühürü ve hash-zinciri testi."""
import hashlib
import io
import json
import os
import sys
import tempfile
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import evidence as E
from dilajan.schema import AnalysisResult, Event, EventCategory, RiskAssessment, Severity

g = k = 0


def c(ad, kosul):
    global g, k
    if kosul:
        g += 1
        print("  ok  ", ad)
    else:
        k += 1
        print("  FAIL", ad)


def jpeg(renk):
    b = io.BytesIO()
    Image.new("RGB", (64, 48), renk).save(b, format="JPEG")
    return b.getvalue()


with tempfile.TemporaryDirectory() as td:
    video = os.path.join(td, "kaynak.mp4")
    with open(video, "wb") as fh:
        fh.write(b"ornek-video-baytlari")
    out = os.path.join(td, "kanit")
    olay = Event(time="00:00", end_time="00:04", event="Görünür duman",
                 severity=Severity.KRITIK, category=EventCategory.GUVENLIK,
                 bbox=[100, 100, 500, 500]).model_copy(
                     update={"isg_kod": "Warehouse_Visible_Fire",
                             "isg_slot": "depo_gorunur_yangin", "isg_deger": "VAR"})
    sonuc = AnalysisResult(
        summary="özet", events=[olay],
        risk=RiskAssessment(level=Severity.KRITIK, rationale="kanıt"))
    kareler = [(0.0, jpeg("red")), (2.0, jpeg("green")), (4.0, jpeg("blue"))]
    with patch.object(E, "extract_timestamped_frames", return_value=(kareler, object())):
        paket = E.build_evidence_bundle(video, sonuc, out)
    with open(paket["manifest"], encoding="utf-8") as fh:
        m = json.load(fh)

    c("uc farkli storyboard karesi", paket["count"] == 3)
    c("bir olay kaydi", paket["event_count"] == 1 and len(m["olaylar"]) == 1)
    c("kaynak video SHA-256", m["video_sha256"] == hashlib.sha256(b"ornek-video-baytlari").hexdigest())
    c("ISG sema-disi alanlari manifeste tasindi",
      m["olaylar"][0]["isg_kod"] == "Warehouse_Visible_Fire")
    onceki = m["zincir_koku_sha256"]
    zincir_gecerli = True
    for fr in m["olaylar"][0]["kareler"]:
        zincir_gecerli &= fr["onceki_kayit_sha256"] == onceki
        govde = dict(fr)
        bek = govde.pop("kayit_sha256")
        zincir_gecerli &= E._kanonik_sha(govde) == bek
        onceki = bek
    c("tum kareler kaynak koklu gercek hash-zincirinde", zincir_gecerli)
    c("manifest zincir sonunu kaydediyor", m["zincir_sonu_sha256"] == onceki)
    c("geriye uyumlu ilk-kare alanlari korunuyor",
      m["olaylar"][0]["dosya"].endswith(".png") and len(m["olaylar"][0]["sha256"]) == 64)

print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
