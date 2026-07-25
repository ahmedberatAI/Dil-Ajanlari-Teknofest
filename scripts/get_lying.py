#!/usr/bin/env python
r"""!!! UYARI: BU BETIK GERCEK VIDEO URETMEZ — DEGERLENDIRMEDE KULLANILMAMALIDIR !!!

    ============================================================================
    Bu betik STATIK PNG DONGUSU uretir. Cikardigi mp4'ler *video degildir*:
    tek bir hareketsiz goruntu `ffmpeg -loop 1 -t 3 -r 5` ile 3 saniyeye
    sarmalanir. Sonuc: 1024x1024, 3.0 sn, 5 fps ve KARELER ARASI SIFIR HAREKET
    (olculen kare-arasi fark ~0.0002-0.022 / 255; gercek dusme videolarinda ayni
    olcu 2.1-4.0, yani 100-1000 KAT daha yuksek).

    NEDEN ONEMLI (denetim bulgusu K8):
      Bir gorme-dil modeli hareketsiz tek kare uzerinde ZAMANSAL OLAY ANLAMA
      yapamaz; yalnizca duran bir fotografi betimler. Bu kliplerle olculen
      "dusme tespiti" basarisi, olculmek istenen yetenegi (video anlama)
      olculmeyen bir yetenekle (tek-kare betimleme) degistirir. Bu klipler bir
      donem `data/eval_scenario/Fall` altinda senaryo-recall pozitiflerinin
      buyuk bolumunu olusturuyordu ve rakamlari sisiriyordu.

    IZIN VERILEN KULLANIM:  yalnizca hizli goz kontrolu (sanity) ve gorsel demo.
    YASAK KULLANIM       :  benchmark, recall/precision, jurili degerlendirme.

    GERCEK DUSME VERISI ICIN BUNLARI KULLANIN:
      scripts/get_gmdcsa.py         -> data/falls_real/         (GMDCSA-24, 1280x720, ~30fps)
      scripts/get_urfd_overhead.py  -> data/falls_surveillance/ (URFD, tepeden bakis)
      scripts/build_scenario_eval.py -> bu kaynaklardan data/eval_scenario/Fall kurar
                                        (donmus klipleri OTOMATIK reddeder)
      scripts/verify_clips.py       -> bir klibin gercekten hareketli olup olmadigini olcer

    Eski uretilen klipler silinmedi; su dizine tasindi:
      data/eval_scenario/_deprecated_frozen_fall/   (gerekce README'de)
    ============================================================================

Cikti (varsayilan): data/scenario/_sanity_lying/lyingNN.mp4
  -- DIKKAT: eskiden dogrudan data/eval_scenario/Fall altina yaziyordu; bu,
     sentetik kliplerin degerlendirme setine sessizce sizmasina yol aciyordu.
     Artik degerlendirme dizinine YAZMAZ. Eski davranis icin: --unsafe-eval-dir
"""
from __future__ import annotations

import argparse
import os
import subprocess
import urllib.request

H = {"User-Agent": "Mozilla/5.0"}
BASE = ("https://huggingface.co/datasets/Simuletic/CCTV_Incident_Dataset_Fall_Lying_Down_Detection"
        "/resolve/main/laying_dataset/images/")
IMG_DIR = os.path.join("data", "scenario", "lying")
#: Sentetik ciktilar ARTIK degerlendirme dizinine yazilmaz (K8).
VID_DIR = os.path.join("data", "scenario", "_sanity_lying")
EVAL_DIR = os.path.join("data", "eval_scenario", "Fall")
IDXS = [1, 15, 30, 45, 60, 75, 90, 99]


def main() -> None:
    ap = argparse.ArgumentParser(description="STATIK PNG dongusu uretir — degerlendirmede KULLANMAYIN.")
    ap.add_argument(
        "--unsafe-eval-dir",
        action="store_true",
        help="ESKI (SAKINCALI) davranis: ciktiyi dogrudan data/eval_scenario/Fall altina yaz. "
             "Sentetik klipleri degerlendirme setine sizdirir (K8). Kullanmayin.",
    )
    args = ap.parse_args()
    out_dir = EVAL_DIR if args.unsafe_eval_dir else VID_DIR

    print("!" * 78, flush=True)
    print("UYARI: Bu betik GERCEK VIDEO uretmez — tek PNG'nin 3sn'lik dongusudur.", flush=True)
    print("       SIFIR kare-arasi hareket. BENCHMARK/DEGERLENDIRMEDE KULLANMAYIN (K8).", flush=True)
    print(f"       Cikti: {out_dir}", flush=True)
    if args.unsafe_eval_dir:
        print("       --unsafe-eval-dir SECILDI: sentetik klipler DEGERLENDIRME dizinine", flush=True)
        print("       yaziliyor. Bu, olculen rakamlari GECERSIZ kilar.", flush=True)
    print("!" * 78, flush=True)

    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for i in IDXS:
        name = f"laying{i:02d}.png"
        png = os.path.join(IMG_DIR, name)
        mp4 = os.path.join(out_dir, f"lying{i:02d}.mp4")
        if not os.path.exists(png):
            try:
                req = urllib.request.Request(BASE + name + "?download=true", headers=H)
                with urllib.request.urlopen(req, timeout=90) as r, open(png, "wb") as w:
                    w.write(r.read())
            except Exception as e:
                print(f"indirme hatasi {name}: {str(e)[:60]}", flush=True)
                continue
        if not os.path.exists(mp4):
            # statik gorseli 3sn'lik mp4'e cevir (5 fps yeterli)
            subprocess.run(
                ["ffmpeg", "-y", "-loop", "1", "-i", png, "-t", "3", "-r", "5",
                 "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", mp4],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        if os.path.exists(mp4):
            n += 1
            print(f"hazir: {mp4}", flush=True)
    print(f"BITTI: {n} STATIK (video olmayan) klip -> {out_dir}", flush=True)
    print("HATIRLATMA: bu klipler DEGERLENDIRMEDE kullanilmamalidir (K8).", flush=True)


if __name__ == "__main__":
    main()
