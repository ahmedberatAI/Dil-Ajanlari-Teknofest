#!/usr/bin/env python
"""Takim kurulum betigi — veriyi KAYNAGINDAN kurar. GPU gerekmez.

NEDEN BOYLE: `data/industrial` telifce CC BY 4.0 ama icinde TANINABILIR CALISANLAR
var (gercek fabrika gozetim goruntusu, KVKK kisisel veri). Baytlari bir buluta
yuklemek ucuncu tarafa AKTARIM olur. Herkes kaynagindan indirirse kimsenin
sunucusundan kisisel veri gecmez.

Kullanim:
    python paylasim/veri_kur.py --hepsi
    python paylasim/veri_kur.py --industrial --ppe      # secmeli
    python paylasim/veri_kur.py --hepsi --kuru          # ne yapacagini yaz, YAPMA
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (bayrak, aciklama, [betik + argumanlar], tahmini_dk, lisans_uyarisi)
ADIMLAR = [
    ("industrial", "Mendeley endustriyel klipler (691 klip, ~9,4 GB)",
     ["scripts/get_industrial.py", "--hepsi"], 45,
     "CC BY 4.0 — baytlari YENIDEN YAYINLANMAZ (KVKK: taninabilir calisanlar)"),

    ("industrial", "eval_defense degerlendirme setini kur (197 klip, hardlink)",
     ["scripts/build_defense_eval.py"], 2,
     None),

    ("isafety", "iSafetyBench degerlendirme seti (1.100 klip, ~1,3 GB)",
     ["scripts/get_isafety_bench.py"], 20,
     "CC BY-NC-SA 4.0 — YALNIZCA DEGERLENDIRME. Egitimde kullanmak model "
     "agirliklarini turev eser yapar ve Apache 2.0 sartini ihlal eder."),

    ("ppe", "KKD veri seti — baret (Mendeley 5-sinif, CC BY 4.0)",
     ["scripts/get_mendeley_ppe.py"], 15, None),

    ("ppe", "KKD veri seti — ek kaynak", ["scripts/get_ppe.py"], 15, None),

    ("ppe", "KKD -> YOLO bicimine cevir", ["scripts/ppe_coco2yolo.py"], 5, None),

    ("ppe", "Yelek veri setini hazirla", ["scripts/yelek_veri_hazirla.py"], 5, None),
]


def kos(betik_arg, kuru: bool) -> bool:
    yol = os.path.join(KOK, betik_arg[0])
    if not os.path.exists(yol):
        print(f"    !! betik YOK: {betik_arg[0]} — atlaniyor")
        return False
    cmd = [sys.executable, yol] + betik_arg[1:]
    if kuru:
        print(f"    [kuru] {' '.join(betik_arg)}")
        return True
    t0 = time.time()
    r = subprocess.run(cmd, cwd=KOK)
    dk = (time.time() - t0) / 60
    if r.returncode == 0:
        print(f"    OK ({dk:.0f} dk)")
        return True
    print(f"    HATA (cikis {r.returncode}, {dk:.0f} dk) — sonraki adima geciliyor")
    return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--hepsi", action="store_true")
    p.add_argument("--industrial", action="store_true")
    p.add_argument("--isafety", action="store_true")
    p.add_argument("--ppe", action="store_true")
    p.add_argument("--kuru", action="store_true", help="ne yapacagini yaz, YAPMA")
    a = p.parse_args()

    secili = {k for k in ("industrial", "isafety", "ppe") if getattr(a, k)}
    if a.hepsi:
        secili = {"industrial", "isafety", "ppe"}
    if not secili:
        p.print_help()
        return 1

    plan = [s for s in ADIMLAR if s[0] in secili]
    toplam_dk = sum(s[3] for s in plan)
    print("=" * 74)
    print(f"{len(plan)} adim  ·  tahmini {toplam_dk} dk  ·  kok: {KOK}")
    print("=" * 74)

    # Lisans uyarilarini ONCE goster — indirdikten sonra okumak gec olur.
    uyarilar = [(s[1], s[4]) for s in plan if s[4]]
    if uyarilar:
        print("\n⚠️  LISANS UYARILARI — indirmeden ONCE oku:\n")
        for ad, u in uyarilar:
            print(f"  • {ad}\n      {u}\n")

    basarili = 0
    for i, (_, ad, betik, dk, _u) in enumerate(plan, 1):
        print(f"\n[{i}/{len(plan)}] {ad}  (~{dk} dk)")
        if kos(betik, a.kuru):
            basarili += 1

    print("\n" + "=" * 74)
    print(f"{basarili}/{len(plan)} adim tamam")
    if not a.kuru:
        print("\nSIRADAKI: python paylasim/dogrula.py")
        print("Kunyeler tutmuyorsa OLCUM YAPMA — farkli klip kumesiyle cikan sayi")
        print("bizim arsivlerimizle karsilastirilamaz.")
    return 0 if basarili == len(plan) else 1


if __name__ == "__main__":
    raise SystemExit(main())
