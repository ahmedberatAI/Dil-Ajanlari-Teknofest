#!/usr/bin/env python
"""Sabit özel-API modelleriyle çarpışma kanıtı kırpım probu.

Bu betik model indirmez ve yerel öğrenilmiş çıkarım çalıştırmaz. Aynı ``vlm``
aliasına, tam kare ile dört sabit örtüşen kırpımı gönderir. Amaç model seçmek
değil, küçük temas nesnesinin karedeki payını artırmanın etkisini ölçmektir.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dilajan.config import settings
from dilajan.gozlem import (GOZLEM_SISTEM, SLOT_DEPO_FORKLIFT_CARPISMA,
                            SLOT_DEPO_FORKLIFT_CARPISMA_DOGRULAMA)
from dilajan.llm_client import VLMClient
from dilajan.video import servis_videosu


CHOICES = ["TEMAS_SONRASI_HAREKET", "YALNIZ_YAKIN_GECIS", "ARAC_YOK", "GORUNMUYOR"]
QUESTION = (
    "Videoyu kronolojik olarak karşılaştır. Kendi tekerlekleri üzerinde hareket eden "
    "bir forklift/endüstriyel araç ile başlangıçta sabit duran ve aracın taşımadığı "
    "bir raf, raf parçası, bariyer, istif veya depo ekipmanı ara. Araç bu hedefe "
    "ulaştığı anda hedef hemen ardından belirgin biçimde yer değiştiriyor, eğiliyor "
    "veya devriliyorsa TEMAS_SONRASI_HAREKET; araç yalnız yakınından geçiyor ve hedef "
    "yerinde kalıyorsa YALNIZ_YAKIN_GECIS; hareketli araç yoksa ARAC_YOK; gerekli an "
    "kırpım dışında ya da ayırt edilemiyorsa GORUNMUYOR yaz. Forkliftin baştan beri "
    "çatallarında taşıdığı yük hedef değildir. İnsan davranışından veya senaryo "
    "varsayımından sonuç çıkarma. Yalnız bu dört etiketten birini yaz."
)
TARGET_CHOICES = ["HEDEF_YER_DEGISTIRDI", "HEDEF_SABIT", "HEDEF_YOK", "GORUNMUYOR"]
TARGET_QUESTION = (
    "Forkliftin/endüstriyel aracın kendi hareketini ve baştan beri çatallarında "
    "taşıdığı yükü tamamen yok say. Videonun başı ile aracın geçişinden sonraki "
    "kısmı arasında, başlangıçta zeminde ya da sabit konumda duran ve taşınmayan "
    "bir raf, raf parçası, bariyer, istif veya depo ekipmanı belirgin biçimde yer "
    "değiştiriyor, eğiliyor veya devriliyor mu? Böyle bir hedefin konum/yön değişimi "
    "kareler boyunca açıkça izleniyorsa HEDEF_YER_DEGISTIRDI; karşılaştırılabilir "
    "hedef yerinde kalıyorsa HEDEF_SABIT; böyle hedef yoksa HEDEF_YOK; başlangıç ve "
    "sonrası ayırt edilemiyorsa GORUNMUYOR yaz. İnsanların ve aracın yer değiştirmesi "
    "hedef hareketi değildir. Yalnız bu dört etiketten birini yaz."
)
PATH_CHOICES = list(SLOT_DEPO_FORKLIFT_CARPISMA_DOGRULAMA.secenekler)
PATH_QUESTION = SLOT_DEPO_FORKLIFT_CARPISMA_DOGRULAMA.soru
PRESENCE_CHOICES = ["SERBEST_HEDEF_VAR", "YALNIZ_SABIT_YAPI", "ARAC_YOK", "GORUNMUYOR"]
PRESENCE_QUESTION = (
    "Videoda hareketli forklift/endüstriyel aracın yakınında, büyük sabit depo rafı "
    "ve duvardan açıkça ayrı duran küçük bir raf ünitesi, tekerlekli raf/araba, "
    "sehpa, bariyer veya benzeri serbest depo ekipmanı görülüyor mu? Açık zeminde "
    "tek başına duran böyle ayrı bir hedef varsa SERBEST_HEDEF_VAR; yalnız duvara/zemine "
    "bağlı uzun sabit raflar, kolonlar ve kutular varsa YALNIZ_SABIT_YAPI; hareketli "
    "araç yoksa ARAC_YOK; ayrı hedef ile sabit yapı ayırt edilemiyorsa GORUNMUYOR yaz. "
    "Burada çarpışma kararı verme; yalnız nesne önkoşulunu ölç. Yalnız etiketi yaz."
)
GAP_CHOICES = ["BOSLUK_SIFIR", "BOSLUK_KALIYOR", "HEDEF_YOK", "GORUNMUYOR"]
GAP_QUESTION = (
    "Çarpışma veya risk yorumu yapma; yalnız görünür geometrik boşluğu ölç. Hareketli "
    "forklift/endüstriyel araç ile ondan ayrı duran küçük raf ünitesi, tekerlekli "
    "raf/araba, bariyer, sehpa veya serbest depo ekipmanını zaman boyunca izle. Herhangi "
    "bir anda aracın dış sınırı ile bu ayrı hedefin sınırı arasındaki görünür boşluk "
    "kapanıp sıfıra iniyorsa BOSLUK_SIFIR; tüm karşılaştırılabilir karelerde arada açık "
    "zemin/boşluk kalıyorsa BOSLUK_KALIYOR; böyle ayrı hedef yoksa HEDEF_YOK; sınırlar "
    "örtülme nedeniyle karşılaştırılamıyorsa GORUNMUYOR yaz. Büyük sabit rafın arkasından "
    "geçen araçtaki perspektif örtüşmesini temas sayma. Yalnız etiketi yaz."
)

# Etiketten bağımsız, sabit ve örtüşen uzamsal tarama. Her kırpım tam karenin
# %56,25'ini kapsar; küçük nesneyi büyütürken araç-hedef ilişkisini korur.
ROIS = {
    "tam": "",
    "sol_ust": "0,0,0.75,0.75",
    "sag_ust": "0.25,0,1,0.75",
    "sol_alt": "0,0.25,0.75,1",
    "sag_alt": "0.25,0.25,1,1",
}


def _ozel_api_sozlesmesini_dogrula() -> dict:
    kunye = {
        "base_url": settings.base_url,
        "model_algi": settings.gorev_modeli("algi"),
        "model_olay": settings.gorev_modeli("olay"),
        "model_yapi": settings.gorev_modeli("yapi"),
        "model_ozet": settings.gorev_modeli("ozet"),
    }
    beklenen = {
        "model_algi": "vlm",
        "model_olay": "llm-large",
        "model_yapi": "llm-fast",
        "model_ozet": "llm-fast",
    }
    if not settings.uzak_api_mi:
        raise RuntimeError("Bu prob yalnız uzak özel API ile çalışır; yerel çıkarım reddedildi.")
    for alan, deger in beklenen.items():
        if kunye[alan] != deger:
            raise RuntimeError(
                f"Sabit model sözleşmesi bozuldu: {alan}={kunye[alan]!r}, beklenen={deger!r}"
            )
    return kunye


def _sor(client: VLMClient, path: Path, roi: str, question: str,
         choices: list[str], bas_sn: float | None = None,
         sure_sn: float | None = None) -> tuple[str, str | None, int]:
    video = servis_videosu(
        str(path), max_side=1920, fps=8, roi_str=roi, sabit_bit="800k",
        bas_sn=bas_sn, sure_sn=sure_sn,
    )
    session = client.video_oturumu(video, system=GOZLEM_SISTEM)
    answer = session.sor(
        question,
        guided_choice=choices,
        temperature=0.0,
        max_tokens=20,
        hatirla=False,
    )
    return (answer or "HATA").strip().upper(), session.hata, len(video)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full-only", action="store_true",
        help="Yalnız tam kareyi ölç (odaklı geliştirme taraması).",
    )
    parser.add_argument(
        "--temporal-windows", action="store_true",
        help="Tam kareyi sabit 5 saniyelik örtüşen pencerelerde ölç.",
    )
    parser.add_argument(
        "--mode", choices=["relationship", "target-motion", "path-contact",
                           "target-presence", "gap", "production-primary",
                           "production-verifier"],
        default="relationship",
    )
    parser.add_argument("clips", nargs="+", type=Path)
    args = parser.parse_args()

    kunye = _ozel_api_sozlesmesini_dogrula()
    client = VLMClient().gorev("algi")
    if args.mode == "target-motion":
        question, choices = TARGET_QUESTION, TARGET_CHOICES
    elif args.mode == "path-contact":
        question, choices = PATH_QUESTION, PATH_CHOICES
    elif args.mode == "target-presence":
        question, choices = PRESENCE_QUESTION, PRESENCE_CHOICES
    elif args.mode == "gap":
        question, choices = GAP_QUESTION, GAP_CHOICES
    elif args.mode == "production-primary":
        question = SLOT_DEPO_FORKLIFT_CARPISMA.soru
        choices = SLOT_DEPO_FORKLIFT_CARPISMA.secenekler
    elif args.mode == "production-verifier":
        question, choices = PATH_QUESTION, PATH_CHOICES
    else:
        question, choices = QUESTION, CHOICES
    rows = []
    for raw in args.clips:
        path = raw if raw.is_absolute() else ROOT / raw
        if not path.is_file():
            raise FileNotFoundError(path)
        print(f"\n{path.name}", flush=True)
        answers = {}
        if args.temporal_windows:
            views = {f"t{bas}_{bas + 5}": ("", float(bas), 5.0)
                     for bas in (0, 4, 8, 12)}
        else:
            rois = {"tam": ""} if args.full_only else ROIS
            views = {name: (roi, None, None) for name, roi in rois.items()}
        for view_name, (roi, bas_sn, sure_sn) in views.items():
            answer, error, size = _sor(
                client, path, roi, question, choices, bas_sn=bas_sn, sure_sn=sure_sn
            )
            answers[view_name] = {
                "roi": roi,
                "start_seconds": bas_sn,
                "duration_seconds": sure_sn,
                "answer": answer,
                "error": error,
                "video_bytes": size,
            }
            print(f"  {view_name:<9} {answer}", flush=True)
        rows.append({
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "any_contact_motion": any(
                x["answer"] in {"TEMAS_SONRASI_HAREKET", "HEDEF_YER_DEGISTIRDI",
                                 "DOGRUDAN_ETKILESIM"}
                for x in answers.values()
            ),
            "answers": answers,
        })

    result = {
        "purpose": "private-api-only collision spatial evidence probe",
        "learned_inference": "special_api_only",
        "model_contract": kunye,
        "mode": args.mode,
        "question": question,
        "choices": choices,
        "spatial_rois": ({"tam": ""} if args.full_only else ROIS),
        "temporal_windows": bool(args.temporal_windows),
        "rows": rows,
    }
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ROOT / "benchmark" / "results" / f"ozel_api_carpisma_kaniti_{stamp}.json"
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nKaydedildi: {dest.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
