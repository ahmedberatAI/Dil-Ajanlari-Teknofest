# -*- coding: utf-8 -*-
"""D42-TANI — "8B, 122B'yi yendi" iddiasini KIRMAYA calisan kontroller.

Ana kosumda llm-fast/llm-large hatalarinin 20/24'u TEK YONE gitti: `-> genel`.
Tek yonlu hata bir ANLAMA hatasi degil, bir COZME/BIAS artifakti olabilir.
Iddiayi ilan etmeden once uc rakip aciklama test edilir:

  B) thinking ACIK mi? -> DILAJAN_DISABLE_THINKING=true ile tekrarla
  C) SECENEK SIRASI bias'i mi? -> secenek listesi TERSTEN verilir
     ("genel" bastayken hatalar hala 'genel'e mi gidiyor, yoksa yeni sona mi?)
  D) KISITLI COZME'nin kendisi mi bozuyor? -> guided KAPALI, serbest metin + ayristir
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from benchmark.yonlendirme_seti import SET, SINIFLAR  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.yonlendirici import SISTEM  # noqa: E402

TERS = tuple(reversed(SINIFLAR))  # ("genel","durum","kisi_oznitelik","sayma")


def _ayristir(ham: str) -> str:
    m = (ham or "").strip().strip('"').lower()
    for s in SINIFLAR:          # serbest metinden etiket cek
        if s in m:
            return s
    return f"AYRISTIRILAMADI:{m[:40]}"


def kos(alias: str, secenekler, guided: bool, etiket_ad: str) -> dict:
    ist = VLMClient(model=alias)
    try:
        ist.chat([{"role": "system", "content": SISTEM}, {"role": "user", "content": "ısınma"}],
                 temperature=0.0, max_tokens=16,
                 guided_choice=secenekler if guided else None)
    except Exception:
        pass
    kayit, dogru = [], 0
    for kim, tur, metin, gercek, zor in SET:
        try:
            ham = ist.chat([{"role": "system", "content": SISTEM},
                            {"role": "user", "content": metin}],
                           temperature=0.0, max_tokens=(16 if guided else 64),
                           guided_choice=secenekler if guided else None)
            tah = (ham or "").strip().strip('"').lower() if guided else _ayristir(ham)
        except Exception as exc:
            tah = f"HATA:{type(exc).__name__}"
        ok = tah == gercek
        dogru += ok
        kayit.append({"kim": kim, "gercek": gercek, "tahmin": tah, "dogru": ok})
    hatalar = [(k["kim"], k["gercek"], k["tahmin"]) for k in kayit if not k["dogru"]]
    # hatalarin kacinin secenek listesinin SON elemanina gittigini say (sira bias'i testi)
    son = secenekler[-1]
    ilk = secenekler[0]
    ozet = {"kol": etiket_ad, "alias": alias, "guided": guided,
            "secenek_sirasi": list(secenekler),
            "acc": dogru / len(SET), "dogru": dogru, "n": len(SET),
            "hata_sayisi": len(hatalar),
            "hata_-> 'genel'": sum(1 for _, _, t in hatalar if t == "genel"),
            "hata_-> listenin SONU": sum(1 for _, _, t in hatalar if t == son),
            "hata_-> listenin BASI": sum(1 for _, _, t in hatalar if t == ilk),
            "hatalar": hatalar}
    print(json.dumps({k: v for k, v in ozet.items() if k != "hatalar"},
                     ensure_ascii=False), flush=True)
    print("   hatalar:", hatalar, flush=True)
    return ozet


def main() -> int:
    from dilajan.config import settings
    print(f"[kunye] disable_thinking={settings.disable_thinking} T=0 n={len(SET)}", flush=True)
    out = {"kunye": {"tarih": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "disable_thinking": settings.disable_thinking,
                     "T": 0.0, "n": len(SET)}, "kollar": []}
    plan = [
        ("router  · duz sira · guided", "router", SINIFLAR, True),
        ("router  · TERS sira · guided", "router", TERS, True),
        ("llm-fast · TERS sira · guided", "llm-fast", TERS, True),
        ("llm-large· TERS sira · guided", "llm-large", TERS, True),
        ("llm-large· duz sira · SERBEST", "llm-large", SINIFLAR, False),
        ("llm-fast · duz sira · SERBEST", "llm-fast", SINIFLAR, False),
    ]
    for ad, alias, sec, guided in plan:
        print(f"\n[{ad}]", flush=True)
        out["kollar"].append(kos(alias, sec, guided, ad))
    yol = os.path.join(ROOT, "benchmark", "results",
                       f"yonlendirme_tani_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nYAZILDI: {yol}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
