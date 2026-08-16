#!/usr/bin/env python
"""KKD dedektorunu TESIS verisinde dener — ALAN FARKI kontrolu. GPU gerekir (yalniz YOLO).

⚠️ BU BIR DOGRULUK OLCUMU DEGILDIR
-----------------------------------
`data/eval_defense` kliplerinde **KKD ground-truth YOKTUR** (Mendeley seti baret
etiketi icermez). Dolayisiyla burada recall/precision HESAPLANAMAZ.

Bu betigin olctugu sey **TETIKLENME ORANI**dir ve tek bir soruyu yanitlar:

    Santiye verisiyle egitilmis dedektor, URETIM tesisi goruntusunde
    makul mu davraniyor, yoksa her klipte alarm mi uretiyor?

OKUMA
-----
  Cok yuksek tetiklenme (or. >%50)  -> alan kaymasi/FP suphesi; esik yukseltilmeli
                                       veya tesis verisiyle ince ayar gerekir
  Cok dusuk (~%0)                   -> ya tesiste gercekten baret takiliyor, ya da
                                       dedektor bu goruntude kafayi hic goremiyor
  Ikisi de "iyi/kotu" DEMEK DEGIL   -> etiket olmadan yon tayini yapilir, KARAR verilmez

Gercek dogruluk icin tesis kliplerinden ornek alinip **elle etiketlenmelidir**
(HANDOFF §6.2 kalan isi). Bu betik o isin gerekli olup olmadigini gosterir.

Kullanim:
    python scripts/ppe_tesis_kontrol.py                 # 40 klip (20 anomali + 20 normal)
    python scripts/ppe_tesis_kontrol.py --n 60 --conf 0.5
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dilajan import detector  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402

KOLLAR = (
    ("Anomali", os.path.join(ROOT, "data", "eval_defense", "Anomali")),
    ("Normal", os.path.join(ROOT, "data", "eval_defense", "Normal")),
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=40, help="toplam klip (kollara esit bolunur)")
    ap.add_argument("--conf", type=float, default=0.45)
    ap.add_argument("--min-kare", type=int, default=2)
    ap.add_argument("--json", dest="json_out",
                    default=os.path.join("benchmark", "results", "ppe_tesis_kontrol.json"))
    args = ap.parse_args()

    if not detector.ppe_available():
        print("[HATA] yolo11n-ppe.pt yok — once: python scripts/train_ppe.py")
        return 1

    print("=" * 82)
    print("KKD dedektoru — TESIS verisi ALAN FARKI kontrolu")
    print(f"  conf={args.conf}  min_kare={args.min_kare}")
    print("  ⚠️ Tesis verisinde KKD ground-truth YOK -> bu bir DOGRULUK olcumu DEGIL,")
    print("     yalnizca TETIKLENME ORANI (alan kaymasi gostergesi).")
    print("=" * 82)

    per_kol = {}
    sure = []
    for kol_ad, kok in KOLLAR:
        klipler = sorted(glob.glob(os.path.join(kok, "*", "*.mp4")))[: args.n // 2]
        if not klipler:
            print(f"[ATLA] klip yok: {kok}")
            continue
        tetik = 0
        ornekler = []
        print(f"\n--- {kol_ad} (n={len(klipler)}) ---")
        for yol in klipler:
            try:
                kareler, _ = extract_timestamped_frames(yol)
                frames = [(f"{int(t) // 60:02d}:{int(t) % 60:02d}", j) for t, j in kareler]
                t0 = time.time()
                r = detector.detect_ppe_violation(frames, conf=args.conf,
                                                  min_kare=args.min_kare)
                sure.append(time.time() - t0)
            except Exception as e:  # noqa: BLE001
                print(f"  [HATA] {os.path.basename(yol)}: {type(e).__name__}: {e}")
                continue
            if r:
                tetik += 1
                ornekler.append({"klip": os.path.basename(yol), **r})
                print(f"  ⚠ {os.path.basename(yol):16s} baretsiz {r['n_ihlal_kutu']} kutu / "
                      f"{r['n_kare']} kare · guven {r['conf']} · baretli {r['n_baretli']}")
        n = len(klipler)
        per_kol[kol_ad] = {"n": n, "tetik": tetik,
                           "oran": round(tetik / n, 3) if n else None,
                           "ornekler": ornekler[:10]}
        print(f"  -> tetiklenme: {tetik}/{n} (%{100.0 * tetik / max(n, 1):.0f})")

    print("\n" + "=" * 82)
    print("OZET")
    for kol, d in per_kol.items():
        print(f"  {kol:8s} {d['tetik']:3d}/{d['n']:<3d}  (%{100 * (d['oran'] or 0):.0f})")
    if sure:
        import statistics
        print(f"  KKD dedektoru gecikmesi: medyan {statistics.median(sure):.2f} sn/klip "
              f"(K4 butcesi: klip basina ~20 sn analiz)")
    print("-" * 82)
    print("YORUM KILAVUZU:")
    print("  Anomali ve Normal kollarinda tetiklenme BENZERSE -> dedektor tesiste")
    print("  ayirt etmiyor demektir; ama zaten KKD ile class0-3 arasinda MANTIKSAL")
    print("  bag YOKTUR (Mendeley sinifllari baretle ilgili degil). Yani benzer oran")
    print("  BEKLENEN durumdur ve KUSUR DEGILDIR.")
    print("  ASIL sinyal: MUTLAK oran. Cok yuksekse (>%50) alan kaymasi/FP suphesi.")
    print("=" * 82)

    if args.json_out:
        yol = args.json_out if os.path.isabs(args.json_out) else os.path.join(ROOT, args.json_out)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            json.dump({
                "_aciklama": ("KKD dedektoru TESIS verisi tetiklenme orani. GROUND-TRUTH YOK "
                              "-> dogruluk olcumu DEGILDIR, alan kaymasi gostergesidir."),
                "conf": args.conf, "min_kare": args.min_kare,
                "egitim_alani": "santiye (keremberke ×2, CC BY 4.0)",
                "test_alani": "uretim tesisi (Eskisehir OSB, data/eval_defense)",
                "kollar": per_kol,
            }, f, ensure_ascii=False, indent=2)
        print(f"Kaydedildi: {os.path.relpath(yol, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
