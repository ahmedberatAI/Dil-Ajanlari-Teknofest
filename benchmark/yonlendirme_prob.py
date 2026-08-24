# -*- coding: utf-8 -*-
"""D42 — yonlendirme probu: kural · router(8B) · llm-fast · llm-large.

ON-KAYIT: docs/on_kayit_router_yonlendirme_2026-08-24.md (kosumdan ONCE yazildi).
Kunye: T=0,0 · max_tokens=16 · structured_outputs.choice · n=36.
seed PLUMBED DEGIL -> belirlenimlilik router kolunda 3 tekrarla AMPIRIK olculur.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as ist
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from benchmark.yonlendirme_seti import SET, SINIFLAR, HEDEF  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.yonlendirici import SISTEM, kural_ile  # noqa: E402

ZOR = {k for k, _, _, _, z in SET if z}


def _sor(istemci: VLMClient, metin: str, T: float, mt: int):
    t0 = time.perf_counter()
    ham = istemci.chat(
        [{"role": "system", "content": SISTEM},
         {"role": "user", "content": metin}],
        temperature=T, max_tokens=mt, guided_choice=SINIFLAR,
    )
    dt = time.perf_counter() - t0
    return (ham or "").strip().strip('"').lower(), dt, getattr(istemci, "son_kullanim", None)


def kol_kos(ad: str, alias: str, T: float, mt: int) -> dict:
    kayit = []
    if alias == "__kural__":
        for kim, tur, metin, etiket, zor in SET:
            t0 = time.perf_counter()
            tah = kural_ile(metin)
            kayit.append({"kim": kim, "tur": tur, "gercek": etiket, "tahmin": tah,
                          "dogru": tah == etiket, "gecikme_s": time.perf_counter() - t0,
                          "kullanim": None, "ham": tah})
    else:
        istemci = VLMClient(model=alias)
        # ISINMA (olcume DAHIL DEGIL): smoke testte ilk cagri 2,18 s, sonrakiler
        # 0,25 s cikti -> on-ek onbellegi/soguk baslangic. Isinma olmadan her kolun
        # ILK maddesi medyani degil ama ortalamayi ve p90'i kirletir.
        try:
            _sor(istemci, "ısınma", T, mt)
        except Exception:
            pass
        for kim, tur, metin, etiket, zor in SET:
            try:
                tah, dt, kul = _sor(istemci, metin, T, mt)
            except Exception as exc:
                tah, dt, kul = f"HATA:{type(exc).__name__}", 0.0, None
            kayit.append({"kim": kim, "tur": tur, "gercek": etiket, "tahmin": tah,
                          "dogru": tah == etiket, "gecikme_s": dt, "kullanim": kul,
                          "ham": tah})
            print(f"  {ad:>10} {kim:>3} {etiket:>14} -> {tah:<16} "
                  f"{'OK' if tah == etiket else 'X '} {dt:.2f}s", flush=True)
    return _ozetle(ad, alias, kayit)


def _ozetle(ad: str, alias: str, kayit: list) -> dict:
    n = len(kayit)
    dogru = sum(1 for k in kayit if k["dogru"])
    kolay = [k for k in kayit if k["kim"] not in ZOR]
    gec = [k["gecikme_s"] for k in kayit]
    gt = [k["kullanim"]["giris"] for k in kayit if k.get("kullanim")]
    ct = [k["kullanim"]["cikis"] for k in kayit if k.get("kullanim")]
    # karisiklik matrisi
    kar = Counter((k["gercek"], k["tahmin"]) for k in kayit)
    # sinif bazli
    sinif = {}
    for s in SINIFLAR:
        alt = [k for k in kayit if k["gercek"] == s]
        sinif[s] = {"n": len(alt), "dogru": sum(1 for k in alt if k["dogru"])}
    # tur bazli (soru vs klip)
    tur = {}
    for t in ("soru", "klip"):
        alt = [k for k in kayit if k["tur"] == t]
        tur[t] = {"n": len(alt), "dogru": sum(1 for k in alt if k["dogru"])}
    return {
        "kol": ad, "alias": alias, "n": n, "dogru": dogru, "acc": dogru / n,
        "acc_zor_haric": (sum(1 for k in kolay if k["dogru"]) / len(kolay)) if kolay else None,
        "n_zor_haric": len(kolay),
        "gecikme_medyan_s": ist.median(gec), "gecikme_ort_s": sum(gec) / n,
        "gecikme_p90_s": sorted(gec)[int(0.9 * (n - 1))],
        "giris_token_ort": (sum(gt) / len(gt)) if gt else None,
        "cikis_token_ort": (sum(ct) / len(ct)) if ct else None,
        "sinif": sinif, "tur": tur,
        "karisiklik": {f"{a}->{b}": c for (a, b), c in sorted(kar.items())},
        "kayit": kayit,
    }


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    m = (p + z * z / (2 * n)) / d
    y = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, m - y), min(1.0, m + y))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--T", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=16)
    ap.add_argument("--tekrar", type=int, default=3, help="router kolu belirlenimlilik tekrari")
    ap.add_argument("--json", dest="json_out", default=None)
    a = ap.parse_args()

    kollar = [("kural", "__kural__"), ("router", "router"),
              ("llm-fast", "llm-fast"), ("llm-large", "llm-large")]
    sonuc = {}
    for ad, alias in kollar:
        print(f"[kol] {ad} ({alias})", flush=True)
        sonuc[ad] = kol_kos(ad, alias, a.T, a.max_tokens)
        s = sonuc[ad]
        lo, hi = wilson(s["dogru"], s["n"])
        print(f"  -> acc={s['acc']:.3f} [%95 GA {lo:.3f}-{hi:.3f}] "
              f"medyan={s['gecikme_medyan_s']:.2f}s", flush=True)

    # --- belirlenimlilik: router kolunu tekrar kos ---
    det = None
    if a.tekrar > 1:
        print(f"[belirlenimlilik] router x{a.tekrar}", flush=True)
        turlar = [[k["tahmin"] for k in sonuc["router"]["kayit"]]]
        for i in range(a.tekrar - 1):
            turlar.append([k["tahmin"] for k in kol_kos("router", "router", a.T, a.max_tokens)["kayit"]])
        farkli = sum(1 for j in range(len(SET)) if len({t[j] for t in turlar}) > 1)
        det = {"tekrar": a.tekrar, "farkli_madde": farkli, "n": len(SET),
               "kararlilik": 1 - farkli / len(SET)}
        print(f"  -> {farkli}/{len(SET)} madde tur-arasi DEGISTI", flush=True)

    # --- kural vs router anlasmazligi (BELIRSIZ dalindaki tirmandirma icin) ---
    anlasmazlik = [k["kim"] for k, r in zip(sonuc["kural"]["kayit"], sonuc["router"]["kayit"])
                   if k["tahmin"] != r["tahmin"]]

    kunye = {
        "tarih": time.strftime("%Y-%m-%d %H:%M:%S"),
        "T": a.T, "max_tokens": a.max_tokens,
        "kisitli_cozme": "structured_outputs.choice",
        "seed": "PLUMBED DEGIL (chat() seed almiyor) -> belirlenimlilik ampirik",
        "n": len(SET), "zor_maddeler": sorted(ZOR),
        "hedef_tablosu": HEDEF,
        "on_kayit": "docs/on_kayit_router_yonlendirme_2026-08-24.md",
    }
    cikti = {"kunye": kunye, "kollar": sonuc, "belirlenimlilik": det,
             "kural_router_anlasmazlik": anlasmazlik,
             "wilson": {ad: wilson(s["dogru"], s["n"]) for ad, s in sonuc.items()}}
    yol = a.json_out or os.path.join(ROOT, "benchmark", "results",
                                     f"yonlendirme_{time.strftime('%Y%m%d_%H%M%S')}.json")
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=2)
    print(f"\nYAZILDI: {yol}")

    print("\n| kol | acc | %95 GA | zor haric | medyan s | p90 s | giris tok | cikis tok |")
    print("|---|---|---|---|---|---|---|---|")
    for ad, s in sonuc.items():
        lo, hi = wilson(s["dogru"], s["n"])
        gt = f"{s['giris_token_ort']:.0f}" if s["giris_token_ort"] else "-"
        ct = f"{s['cikis_token_ort']:.1f}" if s["cikis_token_ort"] else "-"
        print(f"| {ad} | {s['dogru']}/{s['n']} = {s['acc']:.3f} | {lo:.2f}-{hi:.2f} | "
              f"{s['acc_zor_haric']:.3f} | {s['gecikme_medyan_s']:.2f} | "
              f"{s['gecikme_p90_s']:.2f} | {gt} | {ct} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
