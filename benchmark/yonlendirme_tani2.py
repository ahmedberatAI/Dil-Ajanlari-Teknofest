# -*- coding: utf-8 -*-
"""D42-TANI-2 — birinci tani kosumundaki KENDI HATAMI duzeltir + B hipotezini test eder.

OLCUM HATAM (yonlendirme_tani.py, D kolu): serbest metin yanitindan etiketi
`if s in m` ile cektim. "durum" TURKCEDE SIRADAN BIR SOZCUK — modelin
"bu girdi bir nesnenin DURUMUNU soruyor" gibi ACIKLAMA cumlesi bile
`durum` sayildi. llm-fast serbest kolunda 17 hatanin cogu bu yuzden.
=> O kolun sayilari GECERSIZ. Burada duzeltilmis ayristirici ile TEKRAR olculur:
   - `\b...\b` sozcuk siniri (Turkce eklemeli: "durumunu" ARTIK eslesmez)
   - birden cok etiket varsa EN ERKEN gecen alinir
   - hicbiri yoksa AYRISTIRILAMADI (sessizce bir sinifa atanmaz)

B HIPOTEZI (ilk kosumda test EDILMEDI): buyuk modellerde thinking acik olabilir;
kisitli cozme ilk tokeni etikete zorlayinca akil yurutme butcesi kesiliyor olabilir.
DILAJAN_DISABLE_THINKING=true ile tekrar olculur.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from benchmark.yonlendirme_seti import SET, SINIFLAR  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.yonlendirici import SISTEM  # noqa: E402

_RE = {s: re.compile(r"\b" + s + r"\b", re.I) for s in SINIFLAR}


def ayristir(ham: str) -> str:
    """EN ERKEN gecen, SOZCUK SINIRLI etiket. Yoksa AYRISTIRILAMADI."""
    m = (ham or "").strip().strip('"').lower()
    bul = [(mm.start(), s) for s in SINIFLAR if (mm := _RE[s].search(m))]
    return min(bul)[1] if bul else f"AYRISTIRILAMADI:{m[:50]}"


def kos(alias: str, guided: bool, ad: str) -> dict:
    ist = VLMClient(model=alias)
    try:
        ist.chat([{"role": "system", "content": SISTEM}, {"role": "user", "content": "ısınma"}],
                 temperature=0.0, max_tokens=16, guided_choice=SINIFLAR if guided else None)
    except Exception:
        pass
    kayit, dogru, gec = [], 0, []
    for kim, tur, metin, gercek, zor in SET:
        t0 = time.perf_counter()
        try:
            ham = ist.chat([{"role": "system", "content": SISTEM},
                            {"role": "user", "content": metin}],
                           temperature=0.0, max_tokens=(16 if guided else 96),
                           guided_choice=SINIFLAR if guided else None)
            tah = (ham or "").strip().strip('"').lower() if guided else ayristir(ham)
        except Exception as exc:
            tah, ham = f"HATA:{type(exc).__name__}", ""
        gec.append(time.perf_counter() - t0)
        ok = tah == gercek
        dogru += ok
        kayit.append({"kim": kim, "gercek": gercek, "tahmin": tah, "dogru": ok,
                      "ham": (ham or "")[:160],
                      "kullanim": getattr(ist, "son_kullanim", None)})
    hatalar = [(k["kim"], k["gercek"], k["tahmin"]) for k in kayit if not k["dogru"]]
    gt = [k["kullanim"]["giris"] for k in kayit if k.get("kullanim")]
    ct = [k["kullanim"]["cikis"] for k in kayit if k.get("kullanim")]
    ozet = {"kol": ad, "alias": alias, "guided": guided, "dogru": dogru, "n": len(SET),
            "acc": dogru / len(SET), "medyan_s": sorted(gec)[len(gec) // 2],
            "p90_s": sorted(gec)[int(0.9 * (len(gec) - 1))],
            "giris_tok_ort": (sum(gt) / len(gt)) if gt else None,
            "cikis_tok_ort": (sum(ct) / len(ct)) if ct else None,
            "cikis_tok_top": sum(ct) if ct else None,
            "ayristirilamadi": sum(1 for k in kayit if str(k["tahmin"]).startswith("AYRIS")),
            "hatalar": hatalar, "kayit": kayit}
    print(json.dumps({k: v for k, v in ozet.items() if k not in ("hatalar", "kayit")},
                     ensure_ascii=False), flush=True)
    print("   hatalar:", hatalar, flush=True)
    return ozet


def main() -> int:
    from dilajan.config import settings
    et = "thinkingKAPALI" if settings.disable_thinking else "thinkingVARSAYILAN"
    print(f"[kunye] disable_thinking={settings.disable_thinking} ({et}) T=0 n={len(SET)}", flush=True)
    out = {"kunye": {"tarih": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "disable_thinking": settings.disable_thinking,
                     "ayristirici": "sozcuk-sinirli, EN ERKEN eslesme (D42-TANI-2 duzeltmesi)"},
           "kollar": []}
    for ad, alias, guided in [
        (f"router   · guided · {et}", "router", True),
        (f"llm-fast · guided · {et}", "llm-fast", True),
        (f"llm-large· guided · {et}", "llm-large", True),
        (f"llm-large· SERBEST(duzeltilmis ayristirici) · {et}", "llm-large", False),
        (f"llm-fast · SERBEST(duzeltilmis ayristirici) · {et}", "llm-fast", False),
    ]:
        print(f"\n[{ad}]", flush=True)
        out["kollar"].append(kos(alias, guided, ad))
    yol = os.path.join(ROOT, "benchmark", "results",
                       f"yonlendirme_tani2_{et}_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nYAZILDI: {yol}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
