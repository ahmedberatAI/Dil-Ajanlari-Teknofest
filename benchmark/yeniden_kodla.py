#!/usr/bin/env python
"""D40 KONTROL — kodlama izini soken YENIDEN KODLAMA.

    python benchmark/yeniden_kodla.py --sinif Anomali/Carrying_Overload_with_Forklift \
                                       --sinif Normal/Safe_Carrying --cikti /tmp/norm

NEDEN (olculdu, 2026-08-18):
`data/eval_defense`te agir kodlama/oturum sizintisi var. Tasima siniflarinda:

    bit hizi        : ihlal 17,81-21,57 Mbps · normal 4,09-7,06 Mbps -> MCC +1,000
    H.264 profili   : Constrained Baseline 25/25 vs High 25/25       -> MCC +1,000
    pix_fmt         : yuv420p 25/25 vs yuvj420p 25/25                -> MCC +1,000
    dosya boyutu    : 7,18-28,11 MB vs 1,59-7,01 MB                  -> MCC +1,000

VE BU IZ PIKSELLERE GECIYOR: uretim yolundan (2 fps, 768 px, JPEG) gecen karelerin
GLOBAL LUMA STANDART SAPMASI tek skaler olarak tasima ciftini **LOO dogruluk 0,780**
ile ayiriyor (permutasyon p=0,0005). Yani icerigi hic anlamayan bir skaler, bizim
karar esigimizin (0,80) hemen altinda.

SONUC: bir kural/model bu ciftte basarili cikarsa, "icerigi anladi" ile "kodlama
imzasini okudu" AYIRT EDILEMEZ. Bu betik ayrimi mumkun kilar: TUM klipler AYNI
spesifikasyona yeniden kodlanir, sonra olcum TEKRARLANIR.

  sonuc AYNI kalirsa  -> kural icerigi olcuyor
  sonuc COKERSE       -> kural kodlama izini okuyordu

Deterministik forklift dedektoru bu testten GECMISTI (LOO MCC +0,783 -> +0,783,
fiziksel oran 1,576 -> 1,560). Ayni kontrol VLM icin de kosulmalidir.

NOT: yeniden kodlama KAYIPLIDIR ve gorsel icerigi bir miktar degistirir. Bu yuzden
kontrol TEK YONLUDUR: "sonuc hayatta kaldi" guclu kanittir; "sonuc dustu" ise
hem iz-okuma hem de kodlama kaybi anlamina gelebilir ve tek basina RET gerekcesi
degildir (ama uyaridir).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SET = os.path.join(KOK, "data/eval_defense")

# Tum kliplerin zorlanacagi ORTAK spesifikasyon. Degerler kaynak dagilimlarin
# ORTASINDAN secildi (birini kayirmamak icin): bit hizi 4-22 Mbps araligi -> 8 Mbps.
ORTAK = {"vcodec": "libx264", "profile": "main", "pix_fmt": "yuv420p",
         "bitrate": "8M", "fps": "24", "preset": "medium", "g": "48"}


def ffprobe(yol: str) -> dict:
    try:
        c = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=bit_rate,profile,pix_fmt,r_frame_rate,width,height",
             "-show_entries", "format=bit_rate,size", "-of", "json", yol],
            capture_output=True, text=True, timeout=30)
        d = json.loads(c.stdout or "{}")
        s = (d.get("streams") or [{}])[0]
        f = d.get("format") or {}
        return {"profile": s.get("profile"), "pix_fmt": s.get("pix_fmt"),
                "fps": s.get("r_frame_rate"), "w": s.get("width"), "h": s.get("height"),
                "bit_rate": f.get("bit_rate"), "size": f.get("size")}
    except Exception as e:
        return {"hata": f"{type(e).__name__}: {e}"}


def kodla(giris: str, cikis: str) -> bool:
    os.makedirs(os.path.dirname(cikis), exist_ok=True)
    komut = ["ffmpeg", "-y", "-v", "error", "-i", giris,
             "-c:v", ORTAK["vcodec"], "-profile:v", ORTAK["profile"],
             "-pix_fmt", ORTAK["pix_fmt"], "-b:v", ORTAK["bitrate"],
             "-minrate", ORTAK["bitrate"], "-maxrate", ORTAK["bitrate"],
             "-bufsize", "16M", "-r", ORTAK["fps"], "-g", ORTAK["g"],
             "-preset", ORTAK["preset"], "-an", cikis]
    try:
        r = subprocess.run(komut, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            print(f"    ffmpeg hata: {r.stderr.strip()[:160]}")
        return r.returncode == 0
    except Exception as e:
        print(f"    ffmpeg istisna: {type(e).__name__}: {e}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sinif", action="append", required=True,
                    help="eval_defense altindaki dizin (birden fazla verilebilir)")
    ap.add_argument("--cikti", required=True, help="hedef kok dizin")
    ap.add_argument("--denetim", action="store_true",
                    help="yalnizca ONCE/SONRA kunye farkini yazdir, kodlama yapma")
    a = ap.parse_args()

    if not a.denetim:
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=10)
        except Exception:
            print("HATA: ffmpeg bulunamadi (sudo apt install ffmpeg)")
            return 2

    ozet = {}
    for alt in a.sinif:
        yollar = sorted(glob.glob(os.path.join(SET, alt, "*.mp4")))
        print(f"\n{alt}  ({len(yollar)} klip)")
        once, sonra = [], []
        for y in yollar:
            k0 = ffprobe(y)
            once.append(k0)
            if a.denetim:
                continue
            hedef = os.path.join(a.cikti, alt, os.path.basename(y))
            if kodla(y, hedef):
                sonra.append(ffprobe(hedef))
        def dagilim(kl, alan):
            v = [x.get(alan) for x in kl if x.get(alan)]
            if alan in ("bit_rate", "size"):
                v = [int(x) for x in v if str(x).isdigit()]
                return f"{min(v)/1e6:.2f}-{max(v)/1e6:.2f} M" if v else "-"
            return ", ".join(sorted(set(map(str, v))))[:60] or "-"
        print(f"  ONCE   profil={dagilim(once,'profile'):28s} pix={dagilim(once,'pix_fmt'):12s} "
              f"bit={dagilim(once,'bit_rate')}")
        if sonra:
            print(f"  SONRA  profil={dagilim(sonra,'profile'):28s} pix={dagilim(sonra,'pix_fmt'):12s} "
                  f"bit={dagilim(sonra,'bit_rate')}")
        ozet[alt] = {"n": len(yollar), "once": once, "sonra": sonra}

    if not a.denetim:
        print(f"\nYeniden kodlanan klipler: {a.cikti}")
        print("Olcumu tekrarlamak icin: DILAJAN_EVAL_DIR veya prob SET yolunu bu dizine cevirin.")
    json.dump({"ortak_spesifikasyon": ORTAK, "siniflar": ozet},
              open(os.path.join(KOK, "benchmark/results/yeniden_kodlama_kunye.json"),
                   "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
