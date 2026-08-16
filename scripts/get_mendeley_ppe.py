#!/usr/bin/env python
"""Mendeley 5-sinifli KKD veri setini indirir (CC BY 4.0). GPU GEREKMEZ.

KAYNAK
------
"Personal Protective Equipment Detection Dataset (5-Class) for Construction
Safety Monitoring" — https://data.mendeley.com/datasets/8vf7z6v5sb

**Lisans: CC BY 4.0** — Mendeley public-api'nin `data_licence` alanindan teyitli.
Bu, projenin `data/industrial` lisans celiskisini cozerken kullandigi AYNI
yetkili kaynaktir (bkz. docs/veri_lisans_karari.md §1).

NEDEN
-----
D35 gorsel denetimi: hedef tesiste isciler baret TAKMIYOR, hi-vis YELEK giyiyor.
Yelek dedektorumuz egitildi ama **dagitilamadi**: yalnizca 741 egitim kutusuyla
kullanilabilir recall'da precision 0,72 (baraj 0,85) — bkz. scripts/yelek_esik_tara.py.

Bu set yelek kutusu sayisini artirmak icin indiriliyor. Sinif dagilimi indirme
sonrasi OLCULUR; yeterli degilse yine egitilmez (sayilar karari verir, umut degil).

Kullanim:
    python scripts/get_mendeley_ppe.py
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIMLIK = "8vf7z6v5sb"
META = f"https://data.mendeley.com/public-api/datasets/{KIMLIK}"
HEDEF = os.path.join(ROOT, "data", "ppe", "mendeley_5sinif")
H = {"User-Agent": "Mozilla/5.0"}


def _meta() -> dict:
    return json.load(urllib.request.urlopen(
        urllib.request.Request(META, headers=H), timeout=60))


def _indir(f: dict) -> tuple:
    ad = f.get("filename")
    yol = os.path.join(HEDEF, ad)
    if os.path.exists(yol) and os.path.getsize(yol) > 0:
        return ad, True, "atlandi"
    url = (f.get("content_details") or {}).get("download_url") or f.get("download_url")
    if not url:
        return ad, False, "url yok"
    try:
        req = urllib.request.Request(url, headers=H)
        with urllib.request.urlopen(req, timeout=300) as r, open(yol + ".tmp", "wb") as w:
            w.write(r.read())
        os.replace(yol + ".tmp", yol)
        return ad, True, "indi"
    except Exception as e:  # noqa: BLE001
        return ad, False, f"{type(e).__name__}: {e}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args()

    print("=" * 80)
    print("Mendeley 5-sinifli KKD veri seti")
    d = _meta()
    lis = (d.get("data_licence") or {})
    print(f"  ad     : {(d.get('name') or '').strip()}")
    print(f"  lisans : {lis.get('short_name')} — {lis.get('full_name')}")
    if "CC BY 4.0" not in str(lis.get("short_name", "")):
        print("[HATA] Beklenen lisans CC BY 4.0 degil — indirme DURDURULDU.")
        print("       Lisans degismis olabilir; elle dogrulayin.")
        return 1
    print("=" * 80)

    os.makedirs(HEDEF, exist_ok=True)
    dosyalar = d.get("files") or []
    print(f"  {len(dosyalar)} dosya indiriliyor ({args.jobs} paralel)...")

    ok = hata = 0
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        isler = {ex.submit(_indir, f): f for f in dosyalar}
        for i, fut in enumerate(as_completed(isler), 1):
            _ad, basarili, _not = fut.result()
            ok += int(basarili)
            hata += int(not basarili)
            if i % 500 == 0:
                print(f"    {i}/{len(dosyalar)}  ok={ok} hata={hata}")
    print(f"  bitti: ok={ok} hata={hata}")

    # --- kunye ---
    with open(os.path.join(HEDEF, "LISANS.json"), "w", encoding="utf-8") as f:
        json.dump({
            "veri_seti": (d.get("name") or "").strip(),
            "kaynak": f"https://data.mendeley.com/datasets/{KIMLIK}",
            "lisans": lis.get("short_name"),
            "lisans_teyidi": "Mendeley public-api data_licence alani",
            "egitimde_kullanilabilir": True,
            "degerlendirmede_kullanilabilir": True,
            "yeniden_yayimlanabilir": True,
            "alan_uyarisi": "Santiye goruntusu; tesisimiz URETIM. Fark kucuk ama sifir degil.",
        }, f, ensure_ascii=False, indent=2)

    # --- SINIF DAGILIMI: karari SAYILAR verir ---
    say: collections.Counter = collections.Counter()
    n_txt = 0
    for ad in os.listdir(HEDEF):
        if not ad.endswith(".txt"):
            continue
        n_txt += 1
        try:
            for satir in open(os.path.join(HEDEF, ad), encoding="utf-8"):
                p = satir.split()
                if p:
                    say[p[0]] += 1
        except OSError:
            pass
    print("\n  SINIF DAGILIMI (ham indeks — sinif adlari icin README'ye bakin):")
    for k, v in say.most_common():
        print(f"    sinif {k}: {v} kutu")
    print(f"  etiket dosyasi: {n_txt}   toplam kutu: {sum(say.values())}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
