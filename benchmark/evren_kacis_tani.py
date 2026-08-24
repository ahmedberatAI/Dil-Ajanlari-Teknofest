#!/usr/bin/env python
"""D42 EK — SERBEST METIN TANISI (betimleyici; IZGARANIN PARCASI DEGIL).

Ana izgara (benchmark/evren_kacis.py) "hangi soru formulasyonu daha iyi?" diye
sorar. Bu betik BASKA bir seyi sorar: model videoyu GORUYOR mu?

  kisitli secim (structured_outputs.choice) modeli tek kelimeye zorlar; "GORUNMUYOR"
  cevabinin ALTINDA ne oldugunu gizler. Burada AYNI klip, AYNI sistem promptu ve
  AYNI cozunurlukla ama KISITSIZ sorulur. Boylece "GORUNMUYOR" un anlami ayrisir:
    (a) model sahneyi hic betimleyemiyor            -> video/ALGI sorunu
    (b) sahneyi betimliyor ama panoyu/kisiyi anmiyor -> LOKALIZASYON sorunu
    (c) ikisini de dogru betimliyor                  -> SORU/BICIM sorunu

KURALLAR:
  - YALNIZ _tr (secim) klipleri. _te'ye BAKILMAZ.
  - Sonuc SAYI URETMEZ, hipotez SECMEZ; yalnizca ana bulguyu YORUMLAMAYA yarar.
  - Ham cikti JSONL'e yazilir.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SET = os.environ.get("DILAJAN_PROB_SET") or os.path.join(KOK, "data/eval_defense")
CIKTI = os.path.join(KOK, "benchmark/results")

MODEL, MAX_SIDE, CRF = "llm-large", 1280, 26
# SISTEM PROMPTU YOK: ana olcum (D42) sistem promptunun kacisi TETIKLEDIGINI
# gosterdi (yelek: sissiz+kacissiz MCC 0,885 vs sistemli 0,578). Taniyi en
# elverisli kosulda yapiyoruz ki "model gercekten ne goruyor?" sorusu, prompt
# kaynakli susma ile karismasin.

SORULAR = [
    ("betimle", "Bu videoda ne goruyorsun? 2-3 cumleyle betimle."),
    ("nesneler", "Bu videoda gordugun basli nesneleri virgulle ayirarak listele."),
    ("pano_ara", "Videoda bir elektrik/kontrol panosu, elektrik dolabi veya "
                 "sigorta kutusu var mi? Varsa nerede ve kapagi ne durumda? Kisaca yaz."),
    ("kisi_ara", "Videoda insan var mi? Varsa kac kisi ve ne giyiyorlar? Kisaca yaz."),
]

HEDEF = [  # (sinif, dizin, ihlal, kac klip)
    ("pano", "Anomali/Opened_Panel_Cover", True, 4),
    ("pano", "Normal/Closed_Panel_Cover", False, 2),
    # yelek KONTROL: model sahneyi betimleyebiliyor mu? (pano sonucunu yorumlamak
    # icin gerekli — betimleyemiyorsa sorun panoya OZGU degildir)
    ("yelek", "Anomali/Unauthorized_Intervention", True, 2),
]


def main():
    from dilajan.llm_client import VLMClient
    from dilajan.video import servis_videosu
    from dilajan.config import settings
    if settings.mock_mode:
        print("HATA: DILAJAN_MOCK acik.")
        sys.exit(2)

    istemci = VLMClient(model=MODEL)
    os.makedirs(CIKTI, exist_ok=True)
    yol = os.path.join(CIKTI, f"evren_kacis_tani_{datetime.now():%Y%m%d_%H%M%S}.jsonl")
    f = open(yol, "w", encoding="utf-8")
    f.write(json.dumps({"tur": "kunye", "model": MODEL, "max_side": MAX_SIDE, "crf": CRF,
                        "sistem": None, "not": "BETIMLEYICI TANI — izgaranin parcasi degil; "
                        "yalniz _tr klipleri; SISTEM ROLU GONDERILMEZ",
                        "sorular": SORULAR}, ensure_ascii=False) + "\n")

    for sinif, dizin, ihlal, kac in HEDEF:
        tumu = sorted(g for g in glob.glob(os.path.join(SET, dizin, "*.mp4"))
                      if "_tr" in os.path.basename(g))[:kac]
        for p in tumu:
            ad = os.path.basename(p)
            baytlar = servis_videosu(p, max_side=MAX_SIDE, crf=CRF)
            otu = istemci.video_oturumu(
                baytlar, system="",
                giris_metni="Bu guvenlik kamerasi videosunu inceleyeceğiz.")
            print(f"\n{'='*90}\n{sinif} · {ad} · ihlal={ihlal} · {round(len(baytlar)/1024,1)} kB",
                  flush=True)
            kayit = {"tur": "tani", "sinif": sinif, "klip": ad, "ihlal": ihlal, "cevap": {}}
            for etiket, soru in SORULAR:
                # SISTEM ROLU YOK: mesaj listesi dogrudan kurulur (bkz. evren_kacis._sor)
                c = istemci.chat(list(otu._mesajlar) + [{"role": "user", "content": soru}],
                                 temperature=0.0, max_tokens=220)
                kayit["cevap"][etiket] = c
                print(f"  [{etiket}] {c}", flush=True)
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
            f.flush()
    f.close()
    print(f"\nyazildi: {yol}")


if __name__ == "__main__":
    main()
