#!/usr/bin/env python
"""ETIKET CELISKISI DUZELTMESI: eski eval setlerindeki YANLIS 'Normal' endustriyel klipleri degistir.

SORUN (denetimde bulundu):
  Mendeley xjmtb22pff sinif eslemesi (makale + API klip-sayimiyla DOGRULANDI):
      class0 Safe Walkway Violation      -> GUVENSIZ (anomali)
      class1 Unauthorized Intervention   -> GUVENSIZ (anomali)
      class2 Opened Panel Cover          -> GUVENSIZ (anomali)
      class3 Carrying Overload w/Forklift-> GUVENSIZ (anomali)
      class4-7 (Safe Walkway / Authorized Intervention / Closed Panel / Safe Carrying) -> GUVENLI
  Ama eski setler (eval_big/Normal, eval_scenario/Normal, eval_holdout/Normal, eval_tune/Normal)
  class0-3 kliplerini 'Normal' olarak etiketliyordu. Yani ajan bu kliplerde GERCEK guvensiz
  davranisi DOGRU tespit ettiginde YANLIS-POZITIF sayilip cezalandiriliyordu
  -> normal-FP orani OLDUGUNDAN YUKSEK olculuyordu.
  Ayrica ayni dosya eval_defense'te 'Anomali', eski setlerde 'Normal' = kendi icinde CELISKI.

COZUM: eski setlerin Normal klasorlerindeki class0-3 kliplerini KULLANILMAYAN class4-7
  (gercekten guvenli) klipleriyle degistir. Cikarilanlar SILINMEZ, karantinaya (_mislabeled_unsafe/)
  tasinir ve nedeni belgelenir.

Kullanim:
    python scripts/fix_industrial_labels.py            # rapor (dry-run)
    python scripts/fix_industrial_labels.py --apply    # uygula
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
IND = os.path.join(DATA, "industrial")

# Denetlenmis esleme: dosya adi oneki = Mendeley sinif numarasi
UNSAFE_CLASSES = {"0", "1", "2", "3"}
SAFE_CLASSES = {"4", "5", "6", "7"}

# Eski (legacy) degerlendirme setlerinin Normal klasorleri
LEGACY_NORMAL_DIRS = [
    os.path.join(DATA, "eval_big", "Normal"),
    os.path.join(DATA, "eval_scenario", "Normal"),
    os.path.join(DATA, "eval_holdout", "Normal"),
    os.path.join(DATA, "eval_tune", "Normal"),
]

QUARANTINE = os.path.join(DATA, "_mislabeled_unsafe")


def _class_of(filename: str) -> str | None:
    """Dosya adi onekinden Mendeley sinif numarasini cikarir ('3_tr45.mp4' -> '3')."""
    base = os.path.basename(filename)
    if "_" not in base:
        return None
    pre = base.split("_", 1)[0]
    return pre if pre.isdigit() and len(pre) == 1 else None


def _all_safe_clips() -> list[str]:
    """industrial/class4..7 altindaki tum guvenli klipleri dondurur."""
    out = []
    for c in sorted(SAFE_CLASSES):
        d = os.path.join(IND, f"class{c}")
        if os.path.isdir(d):
            out += [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".mp4")]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="degisiklikleri UYGULA (varsayilan: rapor)")
    args = ap.parse_args()

    safe_pool = _all_safe_clips()
    if not safe_pool:
        print("[hata] data/industrial/class4..7 altinda guvenli klip bulunamadi.")
        sys.exit(1)

    # Legacy setlerde HALEN kullanilan dosya adlari (ayni klibi iki kez koymamak icin)
    used: set[str] = set()
    for d in LEGACY_NORMAL_DIRS:
        if os.path.isdir(d):
            used |= {f for f in os.listdir(d) if f.endswith(".mp4")}

    planned: list[tuple[str, str, str]] = []   # (hedef_dizin, cikarilan, eklenen)
    for d in LEGACY_NORMAL_DIRS:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.endswith(".mp4"):
                continue
            cls = _class_of(f)
            if cls is None or cls not in UNSAFE_CLASSES:
                continue  # endustriyel olmayan veya zaten guvenli klip -> dokunma
            # kullanilmayan bir guvenli klip sec
            repl = next((p for p in safe_pool if os.path.basename(p) not in used), None)
            if repl is None:
                print(f"[uyari] {d}: {f} icin yedek guvenli klip kalmadi (indirmeyi artirin)")
                continue
            used.add(os.path.basename(repl))
            planned.append((d, f, repl))

    if not planned:
        print("Degistirilecek yanlis-etiketli klip bulunamadi (set zaten temiz).")
        return

    print(f"{'UYGULANIYOR' if args.apply else 'RAPOR (dry-run)'} — {len(planned)} yanlis-etiketli klip:\n")
    for d, f, repl in planned:
        rel = os.path.relpath(d, ROOT).replace("\\", "/")
        print(f"  {rel}/")
        print(f"    - CIKAR : {f}  (class{_class_of(f)} = GUVENSIZ, 'Normal' etiketi YANLIS)")
        print(f"    + EKLE  : {os.path.basename(repl)}  (class{_class_of(os.path.basename(repl))} = guvenli)")

    if not args.apply:
        print("\nUygulamak icin: python scripts/fix_industrial_labels.py --apply")
        return

    os.makedirs(QUARANTINE, exist_ok=True)
    for d, f, repl in planned:
        src = os.path.join(d, f)
        # 1) yanlis etiketli klibi karantinaya TASI (silme yok)
        dst = os.path.join(QUARANTINE, f"{os.path.basename(os.path.dirname(d))}_{f}")
        if os.path.exists(src):
            shutil.move(src, dst)
        # 2) yerine gercekten guvenli klibi koy
        shutil.copy2(repl, os.path.join(d, os.path.basename(repl)))

    with open(os.path.join(QUARANTINE, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(
            "# Yanlis etiketlenmis endustriyel klipler (karantina)\n\n"
            "Bu klipler eski degerlendirme setlerinde **'Normal'** olarak etiketlenmisti, ancak\n"
            "Mendeley `xjmtb22pff` sinif eslemesine gore **class0-3 = GUVENSIZ davranis** "
            "(anomali)dir:\n\n"
            "| class | davranis | etiket |\n|---|---|---|\n"
            "| 0 | Safe Walkway Violation | GUVENSIZ |\n"
            "| 1 | Unauthorized Intervention | GUVENSIZ |\n"
            "| 2 | Opened Panel Cover | GUVENSIZ |\n"
            "| 3 | Carrying Overload with Forklift | GUVENSIZ |\n\n"
            "Esleme kaynagi: veri setinin makalesi (Data in Brief) + Mendeley API klip sayimlarinin\n"
            "birebir eslesmesiyle **dogrulandi** (class0 210, class1 108, class2 142, class3 56,\n"
            "class4 75, class5 38, class6 32, class7 30).\n\n"
            "**Etkisi:** Ajan bu kliplerde gercek guvensiz davranisi DOGRU tespit ettiginde\n"
            "yanlis-pozitif sayiliyordu -> normal-FP orani OLDUGUNDAN YUKSEK olculuyordu.\n\n"
            "Bu klipler silinmedi; dogru etiketleriyle `data/eval_defense/Anomali/` altinda\n"
            "kullanilmaktadir. Buradaki kopyalar yalnizca izlenebilirlik icin saklanmaktadir.\n"
        )
    print(f"\nTAMAM: {len(planned)} klip degistirildi. Cikarilanlar -> {os.path.relpath(QUARANTINE, ROOT)}")


if __name__ == "__main__":
    main()
