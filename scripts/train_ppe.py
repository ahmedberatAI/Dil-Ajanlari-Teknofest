#!/usr/bin/env python
"""KKD (baret) YOLO dedektorunu egitir. **GPU GEREKIR.**

MIMARI BAGLAM (HANDOFF §6.2 — okumadan calistirma)
--------------------------------------------------
Bu model bir **DETERMINISTIK DOGRULAYICI** olacak; ciktisi VLM'e "kanit" metni
olarak ENJEKTE EDILMEYECEK. Gerekce olculmustur: ham nesne listesini VLM'e vermek
yanlis alarmi **%0 -> %12** yukseltmisti. Dogru desen `detector.verify_fallen`:
YOLO kendi basina karar verir, sonucu tipli bir olaya donusur.

D33 (2026-08-16) bu karari bagimsiz olarak dogruladi: `guided_choice` ile zorunlu
secim yaptirildiginda VLM, acik/kapali pano kapagi sorusunda 20 klibin 20'sinde de
"KAPALI" dedi (10'u gercekte ACIK). Ince, ikili gorsel durum bu VLM'in okuyabildigi
bir sey degil; baret var/yok AYNI problem sinifidir.

VRAM (K6)
---------
Model tek basina ~21 GB tutuyor. Egitim icin **vLLM DURDURULMALIDIR**:
    pkill -f 'api_server|EngineCore|serve_vllm'
Betik baslarken bos VRAM'i olcer ve yetersizse UYARIR.

LISANS KAPISI
-------------
Egitim `dilajan.veri_lisans.egitim_icin_dogrula()` ile baslar. Yasakli bir veri
dizini verilirse **istisna firlatir ve egitim baslamaz** (fail-closed).
Bu, `data/isafety_bench`in (CC BY-NC-SA) kazayla egitime girmesini engeller.

Kullanim:
    python scripts/train_ppe.py                 # varsayilan: yolo11n, 40 epoch
    python scripts/train_ppe.py --epoch 60 --batch 48
    python scripts/train_ppe.py --hizli         # 3 epoch — yalnizca boru hatti denemesi
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dilajan.veri_lisans import egitim_icin_dogrula  # noqa: E402

VERI = os.path.join(ROOT, "data", "ppe_yolo")
YAML = os.path.join(VERI, "ppe.yaml")
CIKTI = os.path.join(ROOT, "data", "ppe_yolo", "egitim")
#: Uretilen agirligin PROJEDE kullanilacak sabit yolu (detector.py bunu arar).
AGIRLIK_HEDEF = os.path.join(ROOT, "yolo11n-ppe.pt")


def _bos_vram_gb() -> float:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15)
        return float(out.stdout.strip().splitlines()[0]) / 1024.0
    except Exception:
        return -1.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="yolo11n.pt", help="baslangic agirligi")
    ap.add_argument("--epoch", type=int, default=40)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--patience", type=int, default=10, help="erken durdurma sabri")
    ap.add_argument("--hizli", action="store_true", help="3 epoch — boru hatti denemesi")
    ap.add_argument("--zorla", action="store_true", help="dusuk VRAM uyarisini yoksay")
    args = ap.parse_args()

    print("=" * 78)
    print("KKD (baret) YOLO egitimi")
    print("=" * 78)

    # --- 1) LISANS KAPISI (fail-closed) ---
    print("[1/4] Lisans kapisi...")
    egitim_icin_dogrula([os.path.relpath(VERI, ROOT)])
    print("      ✅ data/ppe_yolo egitimde kullanilabilir (CC BY 4.0)")

    if not os.path.exists(YAML):
        print(f"[HATA] veri yok: {os.path.relpath(YAML, ROOT)}")
        print("       once: python scripts/get_ppe.py && python scripts/ppe_coco2yolo.py")
        return 1

    # --- 2) VRAM ---
    print("[2/4] VRAM kontrolu...")
    bos = _bos_vram_gb()
    print(f"      bos VRAM: {bos:.1f} GB")
    if 0 <= bos < 4.0 and not args.zorla:
        print("[HATA] Yetersiz VRAM. vLLM calisiyor olabilir — once durdurun:")
        print("       pkill -f 'api_server|EngineCore|serve_vllm'")
        print("       (yoksayma: --zorla)")
        return 1

    # --- 3) EGITIM ---
    epoch = 3 if args.hizli else args.epoch
    print(f"[3/4] Egitim: {args.model} · {epoch} epoch · batch {args.batch} · "
          f"imgsz {args.imgsz}")
    from ultralytics import YOLO
    model = YOLO(args.model)
    model.train(
        data=YAML,
        epochs=epoch,
        batch=args.batch,
        imgsz=args.imgsz,
        patience=args.patience,
        project=CIKTI,
        name="baret",
        exist_ok=True,
        seed=2026,          # proje geneli sabit tohum (bkz. eval_defense MANIFEST)
        deterministic=True,
        device=0,
        val=True,
        plots=True,
        verbose=True,
    )

    # --- 4) DOGRULAMA + AGIRLIGI YERINE KOY ---
    print("[4/4] Test bolumunde dogrulama...")
    en_iyi = os.path.join(CIKTI, "baret", "weights", "best.pt")
    if not os.path.exists(en_iyi):
        print(f"[HATA] agirlik uretilmedi: {en_iyi}")
        return 1
    m = YOLO(en_iyi)
    metrik = m.val(data=YAML, split="test", imgsz=args.imgsz, device=0, verbose=False)
    try:
        kutu = metrik.box
        print(f"      TEST  mAP50={kutu.map50:.4f}  mAP50-95={kutu.map:.4f}")
        for i, ad in enumerate(m.names.values()):
            print(f"        {ad:12s} AP50={kutu.ap50[i]:.4f}  "
                  f"P={kutu.p[i]:.4f}  R={kutu.r[i]:.4f}")
    except Exception as e:  # noqa: BLE001
        print(f"      [UYARI] metrik okunamadi: {e}")

    import shutil
    shutil.copy2(en_iyi, AGIRLIK_HEDEF)
    print(f"\n      Agirlik kopyalandi: {os.path.relpath(AGIRLIK_HEDEF, ROOT)}")
    print("=" * 78)
    print("SONRAKI: DILAJAN_PPE_DETECTION=1 ile deterministik dogrulayici devreye girer")
    print("         (varsayilan KAPALI — K2)")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
