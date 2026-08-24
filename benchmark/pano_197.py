#!/usr/bin/env python
"""D39-E GERCEK SINAV — pano kurali TAM 197 klipte, URETIM KOD YOLUYLA.

Onceki olcum yalnizca class2/5/6 (74 klip) uzerindeydi ve TAM COZUNURLUK
kullaniyordu. Bu betik iki acigi kapatir:

  1) DIGER 123 KLIP: kural yaya-yolu / yetkisiz-mudahale / asiri-yuk / guvenli
     tasima kliplerinde BOSA ATESLIYOR MU? (dagitim yanlis-pozitifi)
  2) COZUNURLUK: uretim kareleri `frame_max_side` (varsayilan 768) ile
     KUCULTUR. Esik 87,6 tam cozunurlukte kalibre edildi. Kucultme ortalama
     parlakligi korumali ama VARSAYILMAZ — ikisi de olculur.

`dilajan.pano.pano_durumu` DOGRUDAN cagrilir (yeniden yazim yok) ve kareler
`dilajan.video.extract_timestamped_frames` ile uretilir — yani olculen sey
URETIMDE KOSACAK KODUN AYNISIDIR.
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import pano  # noqa: E402
from dilajan.config import settings  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SET = os.path.join(KOK, "data/eval_defense")

# (dizin, etiket) — etiket: True = ANOMALI (ihlal), False = NORMAL
SINIFLAR = [
    ("Anomali/Safe_Walkway_Violation", True), ("Anomali/Opened_Panel_Cover", True),
    ("Anomali/Unauthorized_Intervention", True), ("Anomali/Carrying_Overload_with_Forklift", True),
    ("Normal/Safe_Walkway", False), ("Normal/Closed_Panel_Cover", False),
    ("Normal/Authorized_Intervention", False), ("Normal/Safe_Carrying", False),
]
HEDEF = "Anomali/Opened_Panel_Cover"      # kuralin ATESLEMESI GEREKEN tek sinif


def kareler(yol, max_side):
    fr, _bilgi = extract_timestamped_frames(yol, max_side=max_side)
    return [(f"{int(t)//60:02d}:{int(t)%60:02d}", j) for t, j in fr]


def kos(max_side, roi, esik, kisi_kontrolu, imza=""):
    satir = []
    for alt, anomali in SINIFLAR:
        d = os.path.join(SET, alt)
        if not os.path.isdir(d):
            print(f"  [YOK] {alt}"); continue
        for yol in sorted(glob.glob(os.path.join(d, "*.mp4"))):
            try:
                fr = kareler(yol, max_side)
                r = pano.pano_durumu(fr, roi, luma_esik=esik,
                                     kisi_kontrolu=kisi_kontrolu,
                                     gorus_imza=imza)
            except Exception as ex:
                print(f"  [HATA] {os.path.basename(yol)}: {type(ex).__name__}: {ex}")
                continue
            satir.append({"sinif": alt, "klip": os.path.basename(yol),
                          "anomali": anomali, "hedef": alt == HEDEF,
                          "atesledi": r is not None,
                          "luma": (r or {}).get("luma"),
                          "kisi_vardi": (r or {}).get("kisi_vardi")})
        print(f"  {alt:44s} {sum(1 for s in satir if s['sinif'] == alt):3d} klip",
              flush=True)
    return satir


def rapor(satir, baslik):
    print(f"\n{'=' * 74}\n{baslik}\n{'=' * 74}")
    print(f"{'sinif':44s} {'n':>3s} {'atesledi':>9s} {'oran':>7s}")
    print("-" * 74)
    for alt, _ in SINIFLAR:
        alt_s = [s for s in satir if s["sinif"] == alt]
        if not alt_s:
            continue
        a = sum(1 for s in alt_s if s["atesledi"])
        yildiz = "  <- HEDEF" if alt == HEDEF else ""
        print(f"{alt:44s} {len(alt_s):3d} {a:9d} {a/len(alt_s):7.2f}{yildiz}")

    hedef = [s for s in satir if s["hedef"]]
    diger = [s for s in satir if not s["hedef"]]
    tp = sum(1 for s in hedef if s["atesledi"])
    fn = len(hedef) - tp
    fp = sum(1 for s in diger if s["atesledi"])
    tn = len(diger) - fp
    import math
    pd = math.sqrt((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn))
    mcc = (tp*tn - fp*fn)/pd if pd else 0.0
    print(f"\n  HEDEF SINIF (Opened_Panel_Cover) vs DIGER 173 KLIP")
    print(f"    TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"    kesinlik {tp}/{tp+fp}={tp/(tp+fp) if tp+fp else 0:.3f}   "
          f"duyarlilik {tp}/{tp+fn}={tp/(tp+fn) if tp+fn else 0:.3f}   MCC={mcc:+.3f}")

    # DAGITIM YANLIS-POZITIFI: NORMAL etiketli kliplerde atesleme
    norm = [s for s in satir if not s["anomali"]]
    nfp = sum(1 for s in norm if s["atesledi"])
    print(f"\n  DAGITIM YANLIS-POZITIFI (98 NORMAL klipte atesleme): {nfp}/{len(norm)}")
    for s in norm:
        if s["atesledi"]:
            print(f"      {s['sinif']:42s} {s['klip']:14s} luma={s['luma']}")
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "mcc": mcc, "normal_fp": nfp}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roi", default="0.08,0.55,0.21,0.73")
    ap.add_argument("--esik", type=float, default=pano.LUMA_ESIK_VARSAYILAN)
    ap.add_argument("--gorus-imza", default="",
                    help="scripts/pano_kalibre.py ciktisi; bos = GORUS KILIDI YOK")
    ap.add_argument("--imza-dosya", default="",
                    help="imzayi dosyadan oku (uzun dize icin)")
    ap.add_argument("--max-side", type=int, default=0,
                    help="0 = HEM uretim (settings.frame_max_side) HEM tam cozunurluk")
    a = ap.parse_args()

    imza = a.gorus_imza
    if a.imza_dosya:
        imza = open(a.imza_dosya, encoding="utf-8").read().strip()
    print(f"GORUS KILIDI: {'ACIK' if imza else 'KAPALI'}")

    boyutlar = ([a.max_side] if a.max_side
                else [settings.frame_max_side, 4096])   # 4096 = pratikte kucultme yok
    ozet = {}
    for ms in boyutlar:
        ad = "URETIM (max_side=%d)" % ms if ms == settings.frame_max_side else \
             "TAM COZUNURLUK (max_side=%d)" % ms
        print(f"\n>>> {ad}", flush=True)
        satir = kos(ms, a.roi, a.esik, kisi_kontrolu=True, imza=imza)
        ozet[ad] = rapor(satir, ad)
        ozet[ad]["satirlar"] = satir

    yol = os.path.join(KOK, "benchmark/results/pano_197.json")
    json.dump({"roi": a.roi, "esik": a.esik, "ozet": ozet},
              open(yol, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nkaydedildi: {os.path.relpath(yol, KOK)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
