#!/usr/bin/env python
"""iSafetyBench ÇOKTAN SEÇMELİ değerlendirmesi — GENELLEME stres testi. GPU gerekir.

⛔ LISANS: `data/isafety_bench` **CC BY-NC-SA 4.0**tir. Bu betik YALNIZCA
DEGERLENDIRME yapar; hicbir agirlik uretmez/guncellemez. Egitim YASAK
(`dilajan/veri_lisans.py` kod duzeyinde kilitler).

NE OLCULUYOR — VE NE OLCULMUYOR
-------------------------------
Bu betik **MODELIN kendisini** olcer (kareler -> soru -> zorunlu secim), ajan
boru hattini DEGIL. Gerekce: yayimlanmis taban degerleri (Ovis2-8B, Qwen2.5-VL-7B)
bu bicimde uretilmistir; KARSILASTIRILABILIR olmak icin ayni bicim gerekir.

  ✅ olculur : modelin endustriyel tehlike/rutin eylemleri TANIMA yetenegi,
               BAGIMSIZ bir kaynakta (genelleme)
  ❌ olculmez: bizim urunumuzun (7 dugumlu ajan, Turkce cikti sozlesmesi,
               sevk kapisi) bu videolardaki davranisi

⚠️ ALAN UYARISI: klipler YOUTUBE kaynaklidir; dagitim ortamimiz SABIT KAMERA
endustriyel CCTV. Buradaki sayilar **genelleme stres testidir**, "baska bir
fabrikada da boyle olur" KANITI DEGILDIR.

⚠️ METRIK UYARISI: burada **tek-etiketli MCQ dogrulugu** olculur. Makaledeki
"%53,4 F1" **cok-etiketli** gorevin metrigidir — AYNI SAYI DEGILDIR, dogrudan
karsilastirilmamalidir. Iki gorev de sette mevcuttur; cok-etiketli kol bu betikte
KOSULMAZ (her secenek icin ayri soru gerekir -> 16x maliyet).

YONTEM
------
vLLM `guided_choice` ile model 16 secenekten BIRINI secmeye ZORLANIR (kacamak
cevap imkansiz; D33'te pano teshisinde ayni yontem kullanildi). temperature=0.

Kullanim:
    python benchmark/isafety_mcq.py                    # 150+150 soru (hizli)
    python benchmark/isafety_mcq.py --n 400            # kol basina 400
    python benchmark/isafety_mcq.py --n 0              # TAMAMI (uzun)
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
from typing import List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dilajan.config import settings  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.veri_lisans import degerlendirmede_kullanilabilir  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402

try:
    from benchmark.stats_utils import fmt_rate_dict, rate_from_bools
except ImportError:  # benchmark/ icinden
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from stats_utils import fmt_rate_dict, rate_from_bools  # type: ignore

KOK = os.path.join(ROOT, "data", "isafety_bench")
HARFLER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

TALIMAT = (
    "You are analysing a short industrial workplace video.\n"
    "Question: which statement best describes what happens in the video?\n\n"
    "{secenekler}\n\n"
    "Answer with the letter of the single best option only."
)


def _kareler(yol: str, azami: int = 8):
    """Klipten esit araliklarla en fazla `azami` kare alir (maliyet/dogruluk dengesi)."""
    ham, _ = extract_timestamped_frames(yol)
    if not ham:
        return []
    if len(ham) > azami:
        adim = len(ham) / azami
        ham = [ham[int(i * adim)] for i in range(azami)]
    return [(f"{int(t) // 60:02d}:{int(t) % 60:02d}", j) for t, j in ham]


def _sor(istemci: VLMClient, frames, secenekler: List[str]) -> Optional[int]:
    """Modeli 16 secenekten BIRINI secmeye zorlar; secilen indeksi doner."""
    harfler = [HARFLER[i] for i in range(len(secenekler))]
    metin = TALIMAT.format(secenekler="\n".join(
        f"{HARFLER[i]}. {s}" for i, s in enumerate(secenekler)))
    icerik = []
    for zaman, jpg in frames:
        icerik.append({"type": "text", "text": f"[{zaman}]"})
        icerik.append({"type": "image_url",
                       "image_url": {"url": VLMClient._to_data_url(jpg)}})
    icerik.append({"type": "text", "text": metin})
    resp = istemci.client.chat.completions.create(
        model=istemci.model,
        messages=[{"role": "user", "content": icerik}],
        temperature=0.0, max_tokens=4,
        extra_body={"guided_choice": harfler},
    )
    cevap = (resp.choices[0].message.content or "").strip().upper()[:1]
    return HARFLER.index(cevap) if cevap in harfler else None


def kol_kos(istemci: VLMClient, kol: str, n: int, tohum: int) -> dict:
    """Bir kolu (hazard/normal) tek-etiketli MCQ ile kosar."""
    mcq_yol = os.path.join(KOK, "annotations", "mcq", f"{kol}_mcq_single.json")
    vid_dir = os.path.join(KOK, "videos", kol)
    if not os.path.exists(mcq_yol):
        print(f"  [ATLA] {mcq_yol} yok")
        return {}
    with open(mcq_yol, encoding="utf-8") as f:
        sorular = json.load(f)
    # Klip basina EN FAZLA 1 soru: ayni klibin birden cok sorusu BAGIMSIZ degildir
    # (pseudo-replikasyon; stats_utils.pseudo_replication_note ile ayni gerekce).
    gorulen, tekil = set(), []
    for s in sorular:
        if s["video_name"] not in gorulen:
            gorulen.add(s["video_name"])
            tekil.append(s)
    rastgele = random.Random(tohum)
    rastgele.shuffle(tekil)
    if n > 0:
        tekil = tekil[:n]

    print(f"\n--- {kol}: {len(tekil)} soru (klip basina 1, tohum {tohum}) ---")
    dogru, atlanan = [], 0
    sureler = []
    for i, s in enumerate(tekil, 1):
        yol = os.path.join(vid_dir, s["video_name"])
        if not os.path.exists(yol):
            atlanan += 1
            continue
        try:
            fr = _kareler(yol)
            if not fr:
                atlanan += 1
                continue
            t0 = time.time()
            sec = _sor(istemci, fr, s["choices"])
            sureler.append(time.time() - t0)
        except Exception as e:  # noqa: BLE001
            print(f"    [HATA] {s['video_name']}: {type(e).__name__}: {e}")
            atlanan += 1
            continue
        d = (sec == s["answer_index"])
        dogru.append(d)
        if i % 25 == 0:
            oran = 100.0 * sum(dogru) / max(len(dogru), 1)
            print(f"    {i}/{len(tekil)}  dogruluk %{oran:.1f}")
    oran = rate_from_bools(dogru)
    print(f"  -> {kol}: {fmt_rate_dict(oran)}"
          + (f"   (atlanan {atlanan})" if atlanan else ""))
    return {"n_soru": len(dogru), "atlanan": atlanan, "dogruluk": oran,
            "gecikme_medyan": round(statistics.median(sureler), 2) if sureler else None,
            "sans_tabani": round(1.0 / 16, 4)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=150, help="kol basina soru (0 = tamami)")
    ap.add_argument("--tohum", type=int, default=2026)
    ap.add_argument("--json", dest="json_out",
                    default=os.path.join("benchmark", "results", "isafety_mcq.json"))
    args = ap.parse_args()

    if not os.path.isdir(KOK):
        print("[HATA] data/isafety_bench yok — once: python scripts/get_isafety_bench.py")
        return 1
    # LISANS: degerlendirme SERBEST olmali (egitim degil)
    if not degerlendirmede_kullanilabilir("data/isafety_bench"):
        print("[HATA] lisans kapisi degerlendirmeye izin vermiyor")
        return 1

    print("=" * 84)
    print("iSafetyBench — TEK ETIKETLI MCQ (guided_choice, temperature=0)")
    print("  ⛔ CC BY-NC-SA: YALNIZCA degerlendirme; agirlik URETILMEZ")
    print("  ⚠️ YouTube kaynakli -> GENELLEME STRES TESTI, ayni-alan kaniti DEGIL")
    print("  ⚠️ Makaledeki %53,4 F1 COK-ETIKETLI metriktir; bu sayi ONUNLA AYNI DEGIL")
    print(f"  sans tabani: 1/16 = %6,3")
    print("=" * 84)

    istemci = VLMClient()
    sonuc = {}
    for kol in ("hazard", "normal"):
        sonuc[kol] = kol_kos(istemci, kol, args.n, args.tohum)

    print("\n" + "=" * 84)
    print("OZET")
    for kol, d in sonuc.items():
        if d:
            print(f"  {kol:8s} {fmt_rate_dict(d['dogruluk'])}   "
                  f"gecikme medyan {d.get('gecikme_medyan')} sn/soru")
    print("  sans tabani %6,3 (16 secenek)")
    print("=" * 84)

    if args.json_out:
        yol = args.json_out if os.path.isabs(args.json_out) else os.path.join(ROOT, args.json_out)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            json.dump({
                "_aciklama": ("iSafetyBench tek-etiketli MCQ. MODELI olcer, ajan boru "
                              "hattini DEGIL. Yayimlanmis tabanla ayni BICIM, ama "
                              "makaledeki F1 COK-ETIKETLI metriktir -> ayni sayi DEGIL."),
                "model": settings.model_name,
                "yontem": "vLLM guided_choice (16 secenek), temperature=0, klip basina <=8 kare",
                "klip_basina_soru": 1,
                "pseudo_replikasyon_notu": ("ayni klibin birden cok MCQ sorusu BAGIMSIZ "
                                            "degildir; klip basina 1 soru alindi"),
                "lisans": "CC BY-NC-SA 4.0 — yalnizca degerlendirme",
                "alan_uyarisi": ("YouTube kaynakli; dagitim ortami sabit-kamera CCTV. "
                                 "Genelleme stres testi."),
                "tohum": args.tohum,
                "kollar": sonuc,
            }, f, ensure_ascii=False, indent=2)
        print(f"Kaydedildi: {os.path.relpath(yol, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
