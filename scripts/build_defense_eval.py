#!/usr/bin/env python
"""K14: HEDEF-DOMAIN (endustriyel tesis) ici degerlendirme seti kurar.

SORUN (denetim bulgusu K14): sistemin hedef domeni gercek 1080p uretim tesisi
guvenlik kamerasi. Depoda bu domenden yalnizca 8 klip vardi ve 8'i de "Normal"
etiketliydi -> hedef domende SIFIR pozitif. Ustelik bu 8 klibin 4'u aslinda
GUVENSIZ davranistir (class0-3), yani etiket YANLISTI: hem recall olculemiyor
hem de yanlis-pozitif orani oldugundan dusuk cikiyordu.

COZUM: Mendeley xjmtb22pff sinif eslemesi kullanilarak domain-ici bir set kurulur:
    class0-3 (Safe Walkway Violation, Unauthorized Intervention,
              Opened Panel Cover, Carrying Overload with Forklift)   -> ANOMALI
    class4-7 (Safe Walkway, Authorized Intervention,
              Closed Panel Cover, Safe Carrying)                     -> NORMAL

Esleme kaynagi ve dogrulamasi: data/industrial/CLASSES.md
(Mendeley API'deki 691 dosyanin sinif sayilari, Data in Brief makalesinin
sinif tablosuyla 8/8 birebir ortusuyor.)

CIKTI
  data/eval_defense/Anomali/<sinif_adi>/*.mp4
  data/eval_defense/Normal/<sinif_adi>/*.mp4
  data/eval_defense/MANIFEST.json    <- her klip: sinif, etiket, MD5, kaynak yol

DAVRANIS
  * Diskte VAR OLAN data/industrial/class*/ kliplerinden kurar.
  * Klip yetmiyorsa ne eksik oldugunu SOYLER (uydurmaz) ve indirme komutunu yazar.
  * ``--fetch`` verilirse eksikleri scripts/get_industrial.py ile indirmeyi dener
    (ag gerekir; GPU gerekmez).
  * SILME YOK: klipler hardlink'lenir (olmazsa kopyalanir), kaynak dizin durur.

Kullanim:
  python scripts/build_defense_eval.py --list             # plan
  python scripts/build_defense_eval.py                    # diskteki kliplerle kur
  N_PER_CLASS=5 python scripts/build_defense_eval.py --fetch   # eksikleri indir + kur
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys

from _sampling import env_str, get_seed, sample_paths

SRC = env_str("INDUSTRIAL_OUT", os.path.join("data", "industrial"))
OUT = env_str("DEFENSE_OUT", os.path.join("data", "eval_defense"))
#: sinif basina sete alinacak klip sayisi (0 -> diskteki hepsi)
N_PER_CLASS = int(os.environ.get("N_PER_CLASS", "0"))

#: sinif -> (ad, etiket). Kaynak/dogrulama: data/industrial/CLASSES.md
CLASS_MAP: dict[str, tuple[str, str]] = {
    "0": ("Safe_Walkway_Violation", "Anomali"),
    "1": ("Unauthorized_Intervention", "Anomali"),
    "2": ("Opened_Panel_Cover", "Anomali"),
    "3": ("Carrying_Overload_with_Forklift", "Anomali"),
    "4": ("Safe_Walkway", "Normal"),
    "5": ("Authorized_Intervention", "Normal"),
    "6": ("Closed_Panel_Cover", "Normal"),
    "7": ("Safe_Carrying", "Normal"),
}


def md5(path: str, chunk: int = 1 << 20) -> str:
    """Dosya MD5'i (akis halinde)."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def on_disk() -> dict[str, list[str]]:
    """``{sinif: [yol, ...]}`` — diskteki endustriyel klipler."""
    found: dict[str, list[str]] = {}
    for cls in sorted(CLASS_MAP):
        paths = sorted(glob.glob(os.path.join(SRC, f"class{cls}", "*.mp4")))
        found[cls] = paths
    return found


def fetch_missing(need: int) -> None:
    """Eksik klipleri get_industrial.py ile indirmeyi dene (ag gerekir)."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "get_industrial.py")
    env = dict(os.environ, N_PER_CLASS=str(need))
    print(f"# eksikler indiriliyor: N_PER_CLASS={need}", flush=True)
    try:
        subprocess.run([sys.executable, script], env=env, check=False)
    except Exception as e:
        print(f"  indirme calistirilamadi: {type(e).__name__}: {str(e)[:120]}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", "--dry-run", dest="dry", action="store_true",
                    help="Dosya olusturma; yalnizca plani goster.")
    ap.add_argument("--fetch", action="store_true",
                    help="Eksik klipleri scripts/get_industrial.py ile indirmeyi dene (ag gerekir).")
    args = ap.parse_args()

    if args.fetch and not args.dry:
        fetch_missing(N_PER_CLASS if N_PER_CLASS > 0 else 3)

    disk = on_disk()
    print(f"# kaynak={SRC}  cikti={OUT}  seed={get_seed()}", flush=True)
    print(f"\n{'sinif':<8}{'ad':<34}{'etiket':<10}{'diskte':>8}{'secilen':>9}", flush=True)
    print("-" * 70, flush=True)

    rows: list[dict] = []
    n_anom = n_norm = 0
    for cls, (name, label) in CLASS_MAP.items():
        paths = disk.get(cls, [])
        picked = paths if N_PER_CLASS <= 0 else sample_paths(paths, N_PER_CLASS, f"defense{cls}")
        print(f"class{cls:<3}{name:<34}{label:<10}{len(paths):>8}{len(picked):>9}", flush=True)
        for p in picked:
            rows.append({"sinif": cls, "sinif_adi": name, "etiket": label,
                         "kaynak": p.replace("\\", "/"), "ad": os.path.basename(p)})
        if label == "Anomali":
            n_anom += len(picked)
        else:
            n_norm += len(picked)
    print("-" * 70, flush=True)
    print(f"{'TOPLAM':<52}{sum(len(v) for v in disk.values()):>8}{n_anom + n_norm:>9}", flush=True)
    print(f"\nANOMALI (guvensiz, class0-3) = {n_anom}   NORMAL (guvenli, class4-7) = {n_norm}", flush=True)

    bos = [f"class{c}" for c in CLASS_MAP if not disk.get(c)]
    if bos:
        print(f"\n!! EKSIK: {', '.join(bos)} icin diskte klip YOK.", flush=True)
    if n_anom == 0:
        print("!! HEDEF DOMENDE HALA SIFIR POZITIF VAR — set anlamli degil.", flush=True)
    if n_anom < 5 or n_norm < 5:
        print("\nUYARI: sinif basina klip sayisi cok dusuk; bu setle uretilen orani "
              "\n  ondalikli raporlamayin (n<10'da tek klip ~%10 oynatir). Daha fazlasi icin:"
              "\n  N_PER_CLASS=10 python scripts/get_industrial.py", flush=True)

    if args.dry:
        print("\nLISTE MODU: hicbir dosya olusturulmadi.", flush=True)
        return
    if not rows:
        print("\nkurulacak klip yok — cikiliyor.", flush=True)
        return

    for r in rows:
        d = os.path.join(OUT, r["etiket"], r["sinif_adi"])
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, r["ad"])
        if not os.path.exists(dst):
            try:
                os.link(r["kaynak"], dst)
            except Exception:
                shutil.copy2(r["kaynak"], dst)
        r["hedef"] = dst.replace("\\", "/")
        r["md5"] = md5(dst)
        r["boyut"] = os.path.getsize(dst)

    manifest = {
        "_aciklama": ("K14: hedef-domain (Eskisehir uretim tesisi, Mendeley xjmtb22pff) ici "
                      "degerlendirme seti. class0-3 = GUVENSIZ -> Anomali, "
                      "class4-7 = GUVENLI -> Normal. Esleme dogrulamasi: data/industrial/CLASSES.md"),
        "kaynak_veri_seti": "https://data.mendeley.com/datasets/xjmtb22pff (CC BY 4.0)",
        "seed": get_seed(),
        "anomali_sayisi": n_anom,
        "normal_sayisi": n_norm,
        "sinif_eslemesi": {f"class{k}": {"ad": v[0], "etiket": v[1]} for k, v in CLASS_MAP.items()},
        "klipler": rows,
    }
    os.makedirs(OUT, exist_ok=True)
    mpath = os.path.join(OUT, "MANIFEST.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(f"\nkuruldu: {len(rows)} klip -> {OUT}\nmanifest -> {mpath}", flush=True)


if __name__ == "__main__":
    main()
