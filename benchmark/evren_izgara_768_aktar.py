#!/usr/bin/env python
"""D42 — 768 SUTUNUNU D41 OLCUMUNDEN AKTARIR (yeniden cagri YAPMAZ).

GEREKCE (gorev talimati): "Gereksiz tekrar cagri yapma ... ayni klibi iki kez sorma."
D41 (benchmark/evren_model_kars.py, sonuc evren_model_kars_20260824_114539.json)
768/crf28 hucrelerini ZATEN olctu ve protokolu bu izgarayla BIREBIR ayni:
    max_side=768 crf=28 · T=0 · max_tokens=24 · structured_outputs.choice
    ayni SISTEM promptu · ayni soru metinleri · ayni secenek listeleri
    ayni 3 model · klip basina tek kodlama, 3 modele ayni baytlar
DOGRULAMA: bu betik kunye alanlarini KARSILASTIRIR; uyusmazsa AKTARMAZ.
AKTARILAN satirlar "kaynak" alaniyla DAMGALANIR (token bilgisi D41'de yok -> null).

    python benchmark/evren_izgara_768_aktar.py <hedef.jsonl>
"""
from __future__ import annotations

import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAYNAK = os.path.join(KOK, "benchmark/results/evren_model_kars_20260824_114539.json")

BEKLENEN = {"max_side": 768, "crf": 28, "temperature": 0.0, "max_tokens": 24,
            "guided_choice": True, "modeller": ["vlm", "llm-large", "llm-fast"]}
BEKLENEN_SISTEM = ("Sen bir endustriyel is guvenligi kamerasi analiz sistemisin. Sana bir "
                   "guvenlik kamerasindan alinmis kisa bir video verilir. YALNIZCA GORDUGUNE "
                   "dayan; varsayim yapma. Ayirt edemiyorsan kacis secenegini kullan.")
BEKLENEN_SORU = {
    "forklift": ("Forkliftin catalinda ust uste kac adet kasa/blok tasiniyor? "
                 "Yalnizca sayiyi yaz."),
    "yelek": "Makinenin/panonun basinda duran kiside yesil reflektif yelek var mi?",
    "pano": "Elektrik/kontrol panosunun kapagi acik mi?",
}
# izgarada 768 kosulan siniflar (pano YALNIZ 1280 -> aktarilmaz)
AKTAR_SINIF = ("forklift", "yelek")


def bolum(ad):
    g = os.path.splitext(ad)[0]
    return "tr" if "_tr" in g else ("te" if "_te" in g else "?")


def main():
    hedef = sys.argv[1]
    d = json.load(open(KAYNAK, encoding="utf-8"))
    k = d["kunye"]

    hata = []
    for alan, deger in BEKLENEN.items():
        if k.get(alan) != deger:
            hata.append(f"{alan}: {k.get(alan)!r} != {deger!r}")
    if k.get("sistem_prompt") != BEKLENEN_SISTEM:
        hata.append("sistem_prompt FARKLI")
    for s, soru in BEKLENEN_SORU.items():
        if s in d["kollar"] and d["kollar"][s]["soru"] != soru:
            hata.append(f"soru[{s}] FARKLI")
    if hata:
        print("AKTARIM IPTAL — protokol uyusmuyor:")
        for h in hata:
            print("  -", h)
        sys.exit(2)
    print(f"protokol DOGRULANDI (kaynak {os.path.basename(KAYNAK)}, "
          f"zaman {k['zaman']}, git {k['git']})")

    var = set()
    if os.path.exists(hedef):
        with open(hedef, encoding="utf-8") as f:
            for l in f:
                try:
                    r = json.loads(l)
                except Exception:
                    continue
                if r.get("ham_cevap") is not None:
                    var.add((r["klip"], r["sinif"], r["model"], r["cozunurluk"]))

    n = atlanan = 0
    with open(hedef, "a", encoding="utf-8") as f:
        for sinif in AKTAR_SINIF:
            kol = d["kollar"][sinif]
            for klip in kol["klipler"]:
                ad = klip["klip"]
                for model, cevap in klip["cevap"].items():
                    if (ad, sinif, model, 768) in var:
                        atlanan += 1
                        continue
                    ht = isinstance(cevap, str) and cevap.startswith("__HATA__")
                    f.write(json.dumps({
                        "klip": ad, "sinif": sinif, "bolum": bolum(ad),
                        "etiket": int(klip["ihlal"]), "model": model,
                        "cozunurluk": 768, "crf": 28,
                        "ham_cevap": None if ht else cevap,
                        "hata": cevap if ht else None,
                        "gecikme": klip["sure"].get(model),
                        "giris_tok": None, "cikis_tok": None,
                        "bayt": int(klip["boyut_kb"] * 1024),
                        "kaynak": f"D41:{os.path.basename(KAYNAK)}",
                    }, ensure_ascii=False) + "\n")
                    n += 1
    print(f"aktarildi: {n} satir  (zaten vardi: {atlanan})  -> {hedef}")


if __name__ == "__main__":
    main()
