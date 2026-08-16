#!/usr/bin/env python
"""KKD dedektorunun UCTAN UCA dogrulamasi — K2 (cikti) + K4 (gecikme). vLLM GEREKIR.

NE DOGRULANIYOR
---------------
K2  Bayrak KAPALI iken cikti KKD'den HIC etkilenmiyor: uretilen olaylarda,
    karar-izinde ve tetiklenen fonksiyonlarda KKD izi YOK.

    ⚠️ DURUSTLUK NOTU: "byte duzeyinde birebir ayni" iddiasi bu yiginda
    YENIDEN-KOSUMLA DOGRULANAMAZ — HANDOFF §7.1'deki %8 gurultu tabani (A vs A':
    100 klipte 24 cevirme) ayni yapilandirmanin iki kosusunu bile ayirir.
    Burada dogrulanan sey: KAPALI iken KKD KAYNAKLI hicbir yapit yok.
    Kod duzeyi garanti (erken-donus) tests/test_ppe.py'de kilitlidir.

K4  Bayrak ACIK iken gecikme artisi butcede mi (klip basina ~20 sn; 2-3 kat
    kabul edilebilir, 10 kat degil).

AYRICA: dedektor ACIK iken sevk kapisi maskesi GERCEK kosuda calisiyor mu
(KKD olayi var ama operasyonel cagri yok) — `ppe_dispatch=False` sozunun
uctan uca kaniti.

Kullanim:
    python scripts/ppe_uctan_uca.py                # 6 klip x 2 kol
    python scripts/ppe_uctan_uca.py --n 10
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dilajan.agent import analyze_video  # noqa: E402
from dilajan.config import request_config, settings  # noqa: E402

#: KKD izini aramak icin kullanilan isaretler (buyuk/kucuk harf duyarsiz)
KKD_IZLERI = ("kkd", "baret")


def _klipler(n: int):
    """Anomali ve Normal'den dengeli ornek."""
    out = []
    for ust in ("Anomali", "Normal"):
        yollar = sorted(glob.glob(os.path.join(
            ROOT, "data", "eval_defense", ust, "*", "*.mp4")))
        out += yollar[: max(1, n // 2)]
    return out


def _kkd_izi_var(res) -> dict:
    """Sonucta KKD kaynakli yapit var mi? (olay metni / kategori / karar-izi)"""
    olay = [e.event for e in res.events
            if any(s in (e.event or "").lower() for s in KKD_IZLERI)]
    iz = [t for t in (res.decision_trace or [])
          if any(s in t.lower() for s in KKD_IZLERI)]
    ppe_isaretli = [e.event for e in res.events if getattr(e, "ppe_src", False)]
    return {"olay": olay, "iz": iz, "ppe_src_isaretli": ppe_isaretli}


def kol(klipler, ppe: bool) -> dict:
    ad = "ACIK" if ppe else "KAPALI"
    print(f"\n--- KKD {ad} ---")
    satirlar, sureler = [], []
    for yol in klipler:
        t0 = time.time()
        try:
            with request_config(ppe_detection=ppe):
                res = analyze_video(yol)
        except Exception as e:  # noqa: BLE001
            print(f"  [HATA] {os.path.basename(yol)}: {type(e).__name__}: {e}")
            continue
        dt = time.time() - t0
        sureler.append(dt)
        izler = _kkd_izi_var(res)
        satirlar.append({
            "klip": os.path.relpath(yol, ROOT).replace("\\", "/"),
            "sure": round(dt, 1),
            "n_olay": len(res.events),
            "risk": res.risk.level.value,
            "tetiklenen": list(res.triggered_functions),
            **izler,
        })
        isaret = "🪖" if izler["ppe_src_isaretli"] else "  "
        print(f"  {isaret} {os.path.basename(yol):16s} {dt:5.1f}s  olay={len(res.events)} "
              f"risk={res.risk.level.value:6s} sevk={len(res.triggered_functions)}"
              + (f"  KKD: {izler['ppe_src_isaretli'][0][:44]}" if izler["ppe_src_isaretli"] else ""))
    return {"satirlar": satirlar,
            "gecikme_medyan": round(statistics.median(sureler), 1) if sureler else None,
            "n": len(satirlar)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--json", dest="json_out",
                    default=os.path.join("benchmark", "results", "ppe_uctan_uca.json"))
    args = ap.parse_args()

    klipler = _klipler(args.n)
    if not klipler:
        print("[HATA] klip bulunamadi")
        return 1

    print("=" * 88)
    print(f"KKD UCTAN UCA — {len(klipler)} klip x 2 kol")
    print(f"  ppe_dispatch = {settings.ppe_dispatch}  (False ise KKD olayi SEVK ACMAMALI)")
    print("=" * 88)

    kapali = kol(klipler, ppe=False)
    acik = kol(klipler, ppe=True)

    # --- K2: KAPALI kolda KKD yapiti OLMAMALI ---
    kirli = [s for s in kapali["satirlar"]
             if s["olay"] or s["iz"] or s["ppe_src_isaretli"]]
    k2 = not kirli

    # --- SEVK MASKESI: KKD olayi olan kliplerde sevk acilmis mi? ---
    kkd_klipleri = [s for s in acik["satirlar"] if s["ppe_src_isaretli"]]
    maske_ihlali = [s for s in kkd_klipleri if s["tetiklenen"]] if not settings.ppe_dispatch else []

    # --- K4: gecikme ---
    a, b = kapali["gecikme_medyan"], acik["gecikme_medyan"]
    kat = round(b / a, 2) if (a and b) else None

    print("\n" + "=" * 88)
    print("SONUC")
    print("-" * 88)
    print(f"  K2  KAPALI kolda KKD yapiti      : {'YOK ✅' if k2 else f'VAR ❌ ({len(kirli)} klip)'}")
    print(f"  KKD ACIK kolda ihlal bulunan klip: {len(kkd_klipleri)}/{acik['n']}")
    if not settings.ppe_dispatch:
        print(f"  SEVK maskesi (ppe_dispatch=False): "
              f"{'TUTTU ✅' if not maske_ihlali else f'IHLAL ❌ ({len(maske_ihlali)})'}")
    print(f"  K4  gecikme medyan KAPALI/ACIK   : {a}s / {b}s"
          + (f"  -> {kat}x" if kat else ""))
    if kat:
        karar = ("BUTCEDE ✅" if kat <= 3.0 else
                 ("SINIRDA ⚠️" if kat <= 4.0 else "BUTCE DISI ❌"))
        print(f"      K4 butcesi: 2-3 kat kabul edilebilir, 10 kat degil -> {karar}")
    print("=" * 88)
    print("⚠️ NOT: 'byte duzeyinde birebir' iddiasi BURADA KANITLANMAZ — %8 gurultu")
    print("   tabani ayni yapilandirmanin iki kosusunu bile ayirir (§7.1). Kanitlanan:")
    print("   KAPALI iken KKD KAYNAKLI hicbir yapit uretilmiyor.")
    print("=" * 88)

    if args.json_out:
        yol = args.json_out if os.path.isabs(args.json_out) else os.path.join(ROOT, args.json_out)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            json.dump({
                "k2_kapali_temiz": k2, "k2_kirli_klipler": kirli,
                "kkd_bulunan_klip": len(kkd_klipleri),
                "ppe_dispatch": settings.ppe_dispatch,
                "sevk_maske_ihlali": maske_ihlali,
                "gecikme": {"kapali": a, "acik": b, "kat": kat},
                "durustluk_notu": ("byte-identity YENIDEN-KOSUMLA dogrulanamaz (%8 gurultu "
                                   "tabani); dogrulanan: KAPALI iken KKD yapiti yok"),
                "kollar": {"kapali": kapali, "acik": acik},
            }, f, ensure_ascii=False, indent=2)
        print(f"Kaydedildi: {os.path.relpath(yol, ROOT)}")

    return 0 if (k2 and not maske_ihlali) else 1


if __name__ == "__main__":
    raise SystemExit(main())
