#!/usr/bin/env python
"""class2 KESIN TESHIS — VLM'e DOGRUDAN sorar, ajan boru hattini ATLAR.

NEDEN AYRI BIR PROB
-------------------
`scripts/probe_pano.py` sorguyu ajan uzerinden gonderiyordu; ama `query_answer`
alani `dilajan/prompts.py:276` geregi YALNIZCA "yukarida listelenen olaylara
DAYANARAK" uretiliyor ve karsiligi yoksa "Bu bilgi videodan çıkarılamadı" diyor.
Yani o prob MODELIN ALGISINI degil, OLAY CIKARIMI BORU HATTINI olcuyordu.

Bu prob `VLMClient.analyze_frames` ile modele DOGRUDAN sorar ve vLLM'in
`guided_choice` KISITLI KOD COZUMU ile uc secenekten birini SECTIRIR:
    AÇIK · KAPALI · GÖRÜNMÜYOR
Boylece cekinceli/kacamak cevap imkansizdir; model bir sey SECMEK ZORUNDADIR.

(HANDOFF §11 `guided_choice` kolunu "denenmedi" diye listeliyordu — bu onu da kapatir.)

OKUMA
-----
  ~%50 dogru (yazi-tura)        -> ALGI SINIRI: deterministik dogrulayici gerekir
  belirgin >%50                 -> model GORUYOR; sorun ifade/cikarim zincirinde
  cogunlukla "GÖRÜNMÜYOR"       -> pano kadrajda cozunur DEGIL: veri/kamera sorunu

Kullanim:
    python scripts/probe_pano_dogrudan.py            # sinif basina 10 klip
    python scripts/probe_pano_dogrudan.py --n 15
"""
from __future__ import annotations

import argparse
import collections
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.config import settings  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECENEKLER = ["AÇIK", "KAPALI", "GÖRÜNMÜYOR"]

TALIMAT = (
    "Bu bir üretim tesisinin güvenlik kamerası görüntüsüdür. Sahnede elektrik panosu "
    "veya makine kontrol paneli bulunuyor.\n\n"
    "GÖREV: Pano/panel KAPAĞININ durumunu belirle.\n"
    "  AÇIK       = kapak açılmış, iç kısım/kablolar görünüyor\n"
    "  KAPALI     = kapak kapalı ve yerinde\n"
    "  GÖRÜNMÜYOR = görüntüde pano/panel kapağı seçilemiyor\n\n"
    "Yalnızca bu üç kelimeden BİRİNİ yaz, başka hiçbir şey yazma."
)

KOLLAR = (
    (os.path.join(ROOT, "data", "eval_defense", "Anomali", "Opened_Panel_Cover"),
     "class2 KAPAK ACIK", "AÇIK"),
    (os.path.join(ROOT, "data", "eval_defense", "Normal", "Closed_Panel_Cover"),
     "class6 KAPAK KAPALI", "KAPALI"),
)


def sor(istemci: VLMClient, yol: str) -> str:
    """Klipten kare cikarir ve KISITLI kod cozumuyle tek kelime cevap alir."""
    kareler, _info = extract_timestamped_frames(yol)
    if not kareler:
        return "(kare yok)"
    # Ilk/orta/son -> panonun durumu klip boyunca sabittir; 3 kare yeterli ve hizli.
    sec = [kareler[0], kareler[len(kareler) // 2], kareler[-1]]
    frames = [(f"{int(t) // 60:02d}:{int(t) % 60:02d}", jpg) for t, jpg in sec]

    # guided_choice vLLM'e OZGUDUR ve extra_body ile gecer; VLMClient.chat bunu
    # tasimadigi icin ham istemci KULLANILIR (HANDOFF §2: ChatOpenAI'ye gecilmemeli,
    # cunku tam da bu extra_body parametreleri dolayli ve kirilgan olur).
    icerik = []
    for zaman, jpg in frames:
        icerik.append({"type": "text", "text": f"[{zaman}]"})
        icerik.append({"type": "image_url",
                       "image_url": {"url": VLMClient._to_data_url(jpg)}})
    icerik.append({"type": "text", "text": TALIMAT})

    resp = istemci.client.chat.completions.create(
        model=istemci.model,
        messages=[{"role": "user", "content": icerik}],
        temperature=0.0,
        max_tokens=8,
        extra_body={"guided_choice": SECENEKLER},
    )
    return (resp.choices[0].message.content or "").strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=10, help="sinif basina klip sayisi")
    args = ap.parse_args()

    if settings.mock_mode:
        print("⚠ DILAJAN_MOCK acik — bu prob GERCEK model ister. Cikiliyor.")
        return 1

    istemci = VLMClient()
    print("=" * 92)
    print("class2 KESIN TESHIS — VLM'e DOGRUDAN soru + guided_choice (kisitli kod cozumu)")
    print(f"SECENEKLER: {SECENEKLER}   ·   temperature=0")
    print("=" * 92)

    dogru = toplam = 0
    dagilim: dict = {}
    for dizin, ad, gercek in KOLLAR:
        klipler = sorted(glob.glob(os.path.join(dizin, "*.mp4")))[:args.n]
        if not klipler:
            print(f"\n[ATLANDI] klip yok: {dizin}")
            continue
        say: collections.Counter = collections.Counter()
        print(f"\n--- {ad}  (GERCEK: {gercek}, n={len(klipler)}) ---")
        for yol in klipler:
            try:
                cevap = sor(istemci, yol)
            except Exception as e:  # noqa: BLE001  (K3 fail-open)
                print(f"  [HATA] {os.path.basename(yol)}: {type(e).__name__}: {e}")
                continue
            say[cevap] += 1
            toplam += 1
            if cevap == gercek:
                dogru += 1
            isaret = "✓" if cevap == gercek else "✗"
            print(f"  {isaret} {os.path.basename(yol):16s} -> {cevap}")
        dagilim[ad] = dict(say)
        print(f"      dagilim: {dict(say)}")

    print("\n" + "=" * 92)
    if toplam:
        oran = 100.0 * dogru / toplam
        print(f"DOGRUDAN + ZORUNLU SECIM: {dogru}/{toplam} dogru (%{oran:.0f})")
        print(f"  cevap dagilimi: {dagilim}")
        print()
        print("  ~%50           -> yazi-tura: ALGI SINIRI, deterministik dogrulayici gerekir")
        print("  belirgin >%50  -> model GORUYOR; sorun cikarim zincirinde (ucuz cozum)")
        print("  cogu GÖRÜNMÜYOR-> pano kadrajda cozunur degil (veri/kamera sorunu)")
    else:
        print("Hic klip islenemedi.")
    print("⚠ TESHIS probudur: n kucuk, tek kosu. Karar icin tam kol kosulmali (§7.2).")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
