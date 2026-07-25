#!/usr/bin/env python
"""Senaryo-uyumlu degerlendirme seti kurar -> data/eval_scenario/<Kategori>/

Kategoriler:
  Fire   : FIRESENSE pozitif (yangin/duman) klipleri  (bkz. scripts/get_firesense.py)
  Fall   : GERCEK dusme videolari (GMDCSA-24 + URFD)  (bkz. scripts/get_gmdcsa.py,
           scripts/get_urfd_overhead.py)
  Normal : yuksek-cozunurluklu endustriyel (Mendeley) + UCF normal klipleri

K8 DUZELTMESI -- Fall kategorisi:
  Eskiden ``data/eval_scenario/Fall`` icindeki 8 klip (lying*.mp4) VIDEO DEGILDI:
  ``get_lying.py`` tek bir PNG'yi ``ffmpeg -loop 1 -t 3 -r 5`` ile sarmaliyordu
  (1024x1024, 3.0 sn, 5 fps, kare-arasi hareket ~0.001/255 = SIFIR). Bir VLM
  boyle bir klipte "dusme" olayini gozlemleyemez; yalnizca duran bir fotografi
  betimler. Buna ragmen bu 8 klip senaryo-recall pozitiflerinin buyuk bolumunu
  olusturuyordu.

  Artik Fall kategorisi diskteki GERCEK dusme kliplerinden kurulur:
    data/falls_real/Fall/*.mp4          (GMDCSA-24, 1280x720, ~30fps, 3.8-8.5 sn)
    data/falls_surveillance/Fall/*.mp4  (URFD tepeden bakis, 640x480, 15fps)

  Eski donmus klipler SILINMEZ: ``data/eval_scenario/_deprecated_frozen_fall/``
  altina TASINIR ve oraya bir README yazilir.

  KORUMA: PyAV varsa her aday klip kurulum sirasinda olculur; DONMUS (kare-arasi
  hareket ~0) klipler sete ALINMAZ. Boylece K8 bir daha sessizce geri gelemez.
  (PyAV yoksa FAIL-OPEN: olcum atlanir, uyari basilir.)

Kullanim:
  python scripts/build_scenario_eval.py --list     # ne yapilacagini goster
  python scripts/build_scenario_eval.py            # kur
  N_FALL=8 python scripts/build_scenario_eval.py   # Fall'dan yalnizca 8 klip sec
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil

from _sampling import env_str, get_seed, sample_paths

OUT = env_str("SCENARIO_OUT", os.path.join("data", "eval_scenario"))
N_FIRE = int(os.environ.get("N_FIRE", "10"))
N_IND = int(os.environ.get("N_IND", "8"))
N_UCF_NORM = int(os.environ.get("N_UCF_NORM", "4"))
#: 0 -> diskteki TUM gercek dusme klipleri
N_FALL = int(os.environ.get("N_FALL", "0"))

DEPRECATED = os.path.join(OUT, "_deprecated_frozen_fall")
#: Gercek dusme kliplerinin kaynak dizinleri (FALL_SRC ile os.pathsep ayrilmis ezilebilir)
FALL_SOURCES = [p for p in env_str(
    "FALL_SRC",
    os.pathsep.join([os.path.join("data", "falls_real", "Fall"),
                     os.path.join("data", "falls_surveillance", "Fall")]),
).split(os.pathsep) if p]

DEPRECATED_README = """# _deprecated_frozen_fall — DEGERLENDIRMEDE KULLANILMAZ

Bu klasordeki `lying*.mp4` dosyalari `data/eval_scenario/Fall/` altindan buraya
TASINDI (silinmedi). Sebep (denetim bulgusu **K8**):

Bu dosyalar **video degildir**. `scripts/get_lying.py` tek bir PNG goruntusunu
`ffmpeg -loop 1 -t 3 -r 5` ile sarmalayarak uretmistir:

| ozellik              | deger                                   |
|----------------------|-----------------------------------------|
| cozunurluk           | 1024x1024                               |
| sure                 | 3.0 sn                                  |
| fps                  | 5                                       |
| kare-arasi hareket   | ~0.0002 - 0.022 (255 olceginde) = SIFIR |

Olculen degerler (`scripts/verify_clips.py` ile, PyAV):

```
lying01.mp4  3.0sn  5fps  1024x1024  motion_mean=0.0005  motion_max=0.0015
lying15.mp4  3.0sn  5fps  1024x1024  motion_mean=0.0004  motion_max=0.0017
lying30.mp4  3.0sn  5fps  1024x1024  motion_mean=0.0008  motion_max=0.0022
lying45.mp4  3.0sn  5fps  1024x1024  motion_mean=0.0103  motion_max=0.0220
lying60.mp4  3.0sn  5fps  1024x1024  motion_mean=0.0002  motion_max=0.0017
lying75.mp4  3.0sn  5fps  1024x1024  motion_mean=0.0002  motion_max=0.0011
lying90.mp4  3.0sn  5fps  1024x1024  motion_mean=0.0005  motion_max=0.0016
lying99.mp4  3.0sn  5fps  1024x1024  motion_mean=0.0011  motion_max=0.0058
```

Karsilastirma — ayni olcumle **gercek** dusme klipleri 100-1000 kat daha hareketli:

```
Subject1_fall01.mp4  6.87sn  29.6fps  1280x720  motion_mean=2.99  motion_max=3.49
urfd_fall04.mp4      6.40sn  15.0fps   640x480  motion_mean=2.56  motion_max=3.12
```

## Neden olcum gecerli degildi

Hareketsiz tek kare uzerinde bir VLM **video anlama** yapamaz; yalnizca duran bir
fotografi betimler. "Dusme tespiti" iddiasinin bu kliplerle desteklenmesi,
olculen yetenegi (zamansal olay anlama) olculmeyen bir yetenekle (tek-kare
betimleme) degistirir.

## Neden saklaniyor

Silinmedi cunku eski (dondurulmus) benchmark rakamlari bu kliplerle uretildi;
gecmis sonuclarla karsilastirma yapilabilmesi icin arsivde tutuluyor.
**Yeni olcumlerde KULLANILMAMALIDIR.**

Yerine gecen gercek set: `data/eval_scenario/Fall/` (GMDCSA-24 + URFD).
"""


def is_frozen(path: str) -> bool | None:
    """Klip donmus mu? True/False, olculemezse None (FAIL-OPEN)."""
    try:
        from verify_clips import classify, probe
    except Exception:
        return None
    info = probe(path)
    if info.get("error"):
        return None
    _ok, warn = classify(info)
    return any(w.startswith("DONMUS") for w in warn)


def migrate_frozen(dry: bool) -> int:
    """Fall/ altindaki donmus lying*.mp4 kliplerini _deprecated_frozen_fall/ altina TASI."""
    fall = os.path.join(OUT, "Fall")
    frozen = sorted(glob.glob(os.path.join(fall, "lying*.mp4")))
    if not frozen:
        return 0
    print(f"  K8: {len(frozen)} donmus klip -> {DEPRECATED} (SILINMEZ, TASINIR)", flush=True)
    if dry:
        return len(frozen)
    os.makedirs(DEPRECATED, exist_ok=True)
    n = 0
    for src in frozen:
        dst = os.path.join(DEPRECATED, os.path.basename(src))
        if os.path.exists(dst):
            # Arsivde ayni adli dosya zaten var -> SILME YOK, elle bakilsin.
            print(f"    uyari: arsivde zaten var, tasinmadi: {src}", flush=True)
            continue
        shutil.move(src, dst)
        n += 1
    with open(os.path.join(DEPRECATED, "README.md"), "w", encoding="utf-8") as f:
        f.write(DEPRECATED_README)
    return n


def link_into(cat: str, srcs: list[str], dry: bool, check_motion: bool = False) -> int:
    """Klipleri hedef kategoriye baglar (hardlink; olmazsa kopyalar)."""
    d = os.path.join(OUT, cat)
    if not dry:
        os.makedirs(d, exist_ok=True)
    n = 0
    skipped = 0
    for s in srcs:
        if check_motion:
            frozen = is_frozen(s)
            if frozen is True:
                print(f"    ATLANDI (DONMUS): {os.path.basename(s)}", flush=True)
                skipped += 1
                continue
            if frozen is None:
                print(f"    uyari: hareket olculemedi (PyAV yok?), yine de alindi: "
                      f"{os.path.basename(s)}", flush=True)
        dst = os.path.join(d, os.path.basename(s))
        if not dry and not os.path.exists(dst):
            try:
                os.link(s, dst)          # ayni birimde disk harcamaz, MD5 ayni kalir
            except Exception:
                shutil.copy2(s, dst)
        n += 1
    if skipped:
        print(f"    ({skipped} klip donmus oldugu icin sete alinmadi)", flush=True)
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", "--dry-run", dest="dry", action="store_true",
                    help="Hicbir dosya tasima/kopyalama yapma; plani goster.")
    ap.add_argument("--no-motion-check", action="store_true",
                    help="Fall adaylarinda donmus-klip kontrolunu atla (onerilmez).")
    args = ap.parse_args()

    # --- Fire (FIRESENSE pozitifleri) --------------------------------------
    # NOT: secim bilerek ALFABETIK ilk N_FIRE olarak birakildi -> mevcut
    # benchmark rakamlari yeniden uretilebilir kalsin (K12 kapsami disi).
    fire = sorted(glob.glob("data/scenario/_dl/pos/posVideo*.avi"))[:N_FIRE]

    # --- Fall (K8: GERCEK dusme videolari) ---------------------------------
    migrate_frozen(args.dry)
    fall_pool: list[str] = []
    for src_dir in FALL_SOURCES:
        fall_pool.extend(sorted(glob.glob(os.path.join(src_dir, "*.mp4"))))
    fall = fall_pool if N_FALL <= 0 else sample_paths(fall_pool, N_FALL, "Fall")

    # --- Normal ------------------------------------------------------------
    ind = sorted(glob.glob("data/industrial/class*/*.mp4"))[:N_IND]
    ucf = sorted(glob.glob("data/eval/Normal/*.mp4"))[:N_UCF_NORM]

    print(f"# cikti={OUT}  seed={get_seed()}  "
          f"(Fall kaynagi: {', '.join(FALL_SOURCES)})", flush=True)
    nf = link_into("Fire", fire, args.dry)
    print(f"  Fall adaylari: {len(fall_pool)} (secilen {len(fall)})", flush=True)
    nfall = link_into("Fall", fall, args.dry, check_motion=not args.no_motion_check)
    nn = link_into("Normal", ind + ucf, args.dry)
    print(f"Fire={nf}  Fall={nfall}  Normal={nn} "
          f"({len(ind)} endustriyel + {len(ucf)} UCF) -> {OUT}"
          + ("   [LISTE MODU: degisiklik yapilmadi]" if args.dry else ""))
    if not args.dry:
        print("\nUYARI: data/eval_scenario/Fall icerigi DEGISTI. benchmark/ground_truth.json"
              "\n  yeniden uretilmeli (benchmark/build_ground_truth.py) ve ayni dosyadaki"
              "\n  SYNTHETIC_PREFIXES['data/eval_scenario/Fall'] kaydi KALDIRILMALIDIR;"
              "\n  aksi halde yeni GERCEK klipler yanlislikla 'sentetik' isaretlenir.", flush=True)


if __name__ == "__main__":
    main()
