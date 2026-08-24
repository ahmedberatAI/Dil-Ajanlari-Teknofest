#!/usr/bin/env python
"""D43 EK PROB — K2 (cikarim) ve K3 (skorlama) asamalarini K1'den YALITARAK olcer.

    python benchmark/bilgi_kaybi_k2_probu.py --boru <boru.json>

NEDEN GEREKLI: ana probda betimleme (K1) ihlali HIC anmadigi icin K2 ve K3
"olculemez" durumda kaldi — kaybedilecek bilgi yoktu. Bu prob o kisiti kaldirir:

  Ayni klibin GERCEK boru-hatti betimlemesi alinir ve "2) Sapmalar" bolumune
  TEK BIR GOZLEM cumlesi EKLENIR (or. "Forkliftin catalinda ust uste 3 kasa
  istiflenmis; yuk surucunun gorusunu engelleyecek yukseklikte."). Cumle
  GOZLEMDIR, HUKUM DEGILDIR — icinde "ihlal"/"tehlike"/"guvensiz" gecmez.
  Betimlemenin geri kalani BIT BIT AYNIDIR.

Sonra boru hattinin GERCEK olay-cikarim promptu (prompts.EVENT_EXTRACTION_
INSTRUCTION) ayni modelle calistirilir:

  K2 olcusu : eklenen gozlem OLAY LISTESINE gecti mi?
  K3 olcusu : gecti ise, MODELIN KENDI kelimeleriyle yazdigi olay metnini
              benchmark/labels.isg_match YAKALIYOR mu? (sablon degil, model
              metni -> gercek sozcuksel-kapi testi)

Boylece "bilgi vardi ama gecmedi" (K2) ile "gecti ama eslesmedi" (K3) ilk kez
ayri ayri sayilabilir.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from benchmark.labels import isg_match  # noqa: E402

CIFT_SINIF = {"forklift": "Carrying_Overload_with_Forklift",
              "yetki": "Unauthorized_Intervention",
              "pano": "Opened_Panel_Cover",
              "yol": "Safe_Walkway_Violation"}

#: EKLENEN GOZLEM CUMLELERI — hukum DEGIL, olcum.
#: Kasitli olarak ISG_SINIFLAR kaliplarinin cogunu ICERMEZ; amac modelin
#: gozlemi olaya CEVIRIP CEVIRMEDIGINI ve KENDI kelimesiyle nasil yazdigini
#: olcmek. ("ihlal", "guvensiz", "tehlike", "risk" kelimeleri YOK.)
GOZLEM = {
    "forklift": ("*   **00:02:** Forkliftin çatalında üst üste {c} kasa istiflenmiş "
                 "durumda taşınıyor; istif sürücünün ön görüş hattının üzerine çıkıyor."),
    "yetki": ("*   **00:02:** Makinenin başında duran ve elleriyle makineye dokunan "
              "kişinin üzerinde reflektif yelek yok; diğer personelde yelek var."),
    "pano": ("*   **00:02:** Makinenin yan yüzündeki elektrik panosunun kapağı açık "
             "duruyor; kapağın arkasındaki boşlukta kablo ve terminaller görünüyor."),
    "yol": ("*   **00:02:** Yürüyen personel zemindeki sarı işaretli yaya şeridinin "
            "dışında, makinelerin ve forklift güzergâhının olduğu alanda ilerliyor."),
}

_SAPMA_BAS = re.compile(r"(\*{0,2}\s*#{0,4}\s*\*{0,2}\s*2\s*\)?\s*[\.\-–]?\s*sapma[^\n]*\n)",
                        re.I)


def enjekte(desc: str, cumle: str) -> str:
    """Gozlem cumlesini '2) Sapmalar' basliginin HEMEN ALTINA koyar.
    Baslik bulunamazsa metnin SONUNA eklenir (o zaman da ayni bolumdedir)."""
    m = _SAPMA_BAS.search(desc)
    if m:
        i = m.end()
        return desc[:i] + cumle + "\n" + desc[i:]
    return desc.rstrip() + "\n\n**2) Sapmalar:**\n" + cumle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boru", required=True)
    ap.add_argument("--cikti", default="")
    a = ap.parse_args()

    from dilajan import prompts
    from dilajan.config import settings
    from dilajan.llm_client import VLMClient
    from dilajan.utils import extract_json

    if settings.mock_mode:
        print("mock_mode ACIK — kosum anlamsiz"); sys.exit(2)

    d = json.load(open(a.boru, encoding="utf-8"))
    satirlar = [r for r in d["satirlar"] if r["ihlal"] and r.get("desc")]
    istemci = VLMClient()   # boru hattiyla AYNI: graph.py gorev() KULLANMIYOR
    print(f"model: {istemci.model} · {len(satirlar)} guvensiz klip\n")

    cikti = []
    for i, r in enumerate(satirlar, 1):
        cift = r["cift"]
        desc0 = r["desc"][0]
        cumle = GOZLEM[cift].format(c=3)
        desc1 = enjekte(desc0, cumle)
        t0 = time.time()
        try:
            ham = istemci.chat([
                {"role": "system", "content": prompts.SYSTEM_PERSONA},
                {"role": "user", "content": prompts.EVENT_EXTRACTION_INSTRUCTION.format(
                    description=desc1, start="00:00", end="00:10")},
            ], temperature=0.1, max_tokens=400)
        except Exception as e:
            ham = f"__HATA__ {type(e).__name__}: {e}"
        veri = extract_json(ham) or {}
        olaylar = [e for e in (veri.get("events") or []) if isinstance(e, dict)]
        metinler = [str(e.get("event", "")) for e in olaylar]
        sinif = CIFT_SINIF[cift]
        # K2: eklenen gozlem olaya dondu mu? (konu-anahtarlari, sinif kalibindan BAGIMSIZ)
        konu = {"forklift": r"kasa|istif|çatal|görüş|yük",
                "yetki": r"yelek|koruyucu|donanım|kkd",
                "pano": r"pano|kapak|terminal|kablo|panel",
                "yol": r"şerit|yaya|yol|çizgi|güzergâh|guzergah"}[cift]
        gecti = [m for m in metinler if re.search(konu, m, re.I)]
        eslesti = [m for m in metinler if isg_match(m, sinif)]
        cikti.append({
            "yol": r["yol"], "cift": cift, "eklenen": cumle,
            "n_olay": len(olaylar), "olaylar": olaylar,
            "K2_gozlem_olaya_dondu": bool(gecti),
            "K3_isg_match": bool(eslesti),
            "isg_match_tum_metin": isg_match("\n".join(metinler), sinif),
            "sure_s": round(time.time() - t0, 1), "ham": ham[:1200],
        })
        print(f"  [{i}/{len(satirlar)}] {os.path.basename(r['yol']):<14}{cift:<10}"
              f"n_olay={len(olaylar)} K2={bool(gecti)} K3={bool(eslesti)}"
              f"   {gecti[0][:80] if gecti else ''}", flush=True)

    yol = a.cikti or os.path.join(
        KOK, "benchmark/results",
        "bilgi_kaybi_k2_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump({"model": istemci.model, "kaynak_boru": a.boru,
                   "gozlem_cumleleri": GOZLEM, "satirlar": cikti},
                  f, ensure_ascii=False, indent=1)

    n = len(cikti)
    k2 = sum(r["K2_gozlem_olaya_dondu"] for r in cikti)
    k3 = sum(r["K3_isg_match"] for r in cikti)
    print(f"\n{'=' * 78}")
    print(f"K2 — eklenen GOZLEM olay listesine gecti  : {k2}/{n}")
    print(f"K3 — gecen olayi isg_match YAKALADI       : {k3}/{n}"
          f"   (gecenlerin {k3}/{k2}'i)")
    print(f"kayip: K2'de {n - k2} klip · K3'te {k2 - k3} klip")
    for c in ("forklift", "yetki", "pano", "yol"):
        g = [r for r in cikti if r["cift"] == c]
        if g:
            print(f"   {c:<10} K2 {sum(r['K2_gozlem_olaya_dondu'] for r in g)}/{len(g)}"
                  f"   K3 {sum(r['K3_isg_match'] for r in g)}/{len(g)}")
    print(f"\n-> {yol}")


if __name__ == "__main__":
    main()
