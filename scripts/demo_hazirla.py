#!/usr/bin/env python
"""SUNUM ONU HAZIRLIK — tek komutla demo makinesini temize ceker.

Kullanim:
    python scripts/demo_hazirla.py           # kontrol eder, DEGISTIRMEZ
    python scripts/demo_hazirla.py --uygula  # duzeltmeleri uygular

Ne yapar:
  1) Yapilandirmayi dogrular (uzak servis, ISG slotlari, yerel GPU yasagi).
  2) Servisin AYAKTA oldugunu ve model aliaslarinin var oldugunu yoklar.
  3) Epizodik bellegi YEDEKLEYIP bosaltir — sunum denetiminde goruldu:
     sohbet baglami 8 gun onceki ALAKASIZ sokak kliplerini "gecmis olay"
     diye sayiyordu. Juri "daha once ne analiz ettin?" derse ISG demosunda
     UCF sokak klipleri cikardi.
  4) `.env` icindeki KULLANILMAYAN sirlari (Qdrant anahtari, arayuz parolasi)
     bildirir — sunum makinesinde biri .env'i editorde acarsa parola ekrana gelir.
  5) Prova edilmis demo kliplerinin YERINDE oldugunu dogrular.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.request

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

# --- prova edilmis demo ciftleri (D51, her biri 3 tekrarda KARARLI + DOGRU) ---
DEMO_CIFTLERI = [
    ("YELEK",    "data/eval_defense/Normal/Authorized_Intervention/5_te14.mp4",
                 "data/eval_defense/Anomali/Unauthorized_Intervention/1_tr2.mp4"),
    ("FORKLIFT", "data/eval_defense/Normal/Safe_Carrying/7_te1.mp4",
                 "data/eval_defense/Anomali/Carrying_Overload_with_Forklift/3_tr45.mp4"),
    ("PANO",     "data/eval_defense/Normal/Closed_Panel_Cover/6_te10.mp4",
                 "data/eval_defense/Anomali/Opened_Panel_Cover/2_tr58.mp4"),
]

def _ok(m): print(f"  [OK ] {m}")
def _uy(m): print(f"  [!! ] {m}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true", help="duzeltmeleri UYGULA")
    a = ap.parse_args()
    sorun = 0

    print("\n=== 1. YAPILANDIRMA ===")
    from dilajan.config import settings as s, yerel_cihaz
    from dilajan import isg_kural as K
    if s.uzak_api_mi: _ok(f"uzak servis: {s.base_url}")
    else: _uy("uzak servis KAPALI — .env okunmuyor olabilir"); sorun += 1
    slot = K.gerekli_slotlar(s)
    if len(slot) >= 4: _ok(f"ISG slotlari acik: {slot}")
    else: _uy(f"ISG slotlari EKSIK: {slot}"); sorun += 1
    if yerel_cihaz() == "cpu": _ok("yerel GPU yasagi etkin (cihaz=cpu)")
    else: _uy(f"yerel GPU KULLANILIYOR (cihaz={yerel_cihaz()})"); sorun += 1
    if s.kodlama_normalize: _ok(f"kodlama normalizasyonu acik (fps {s.kodlama_fps})")
    else: _uy("kodlama normalizasyonu KAPALI"); sorun += 1
    if s.yeniden_deneme >= 1: _ok(f"servis yeniden deneme: {s.yeniden_deneme}")
    else: _uy("yeniden deneme KAPALI"); sorun += 1
    # SUNUM ICIN KARARLI KIP: olculdu — kapaliyken pano demo klibi 3 tekrarda
    # IKI FARKLI sonuc veriyordu; acikken 6/6 kol kararli VE dogru.
    if s.kodlama_kararli: _ok("kararli kodlama ACIK (sahnede ayni sonuc)")
    else: _uy("kararli kodlama KAPALI — ayni klip farkli sonuc verebilir"); sorun += 1

    print("\n=== 2. SERVIS ===")
    try:
        t0 = time.time()
        istek = urllib.request.Request(
            s.base_url.rstrip("/") + "/models",
            headers={"Authorization": f"Bearer {s.etkin_api_key}"})
        veri = json.loads(urllib.request.urlopen(istek, timeout=8).read())
        adlar = {m.get("id") for m in veri.get("data", [])}
        _ok(f"/v1/models {time.time()-t0:.1f}s · {len(adlar)} alias")
        for g in ("algi", "sayim", "ozet"):
            m = s.gorev_modeli(g)
            (_ok if m in adlar else _uy)(f"gorev '{g}' -> {m}")
            if m not in adlar: sorun += 1
    except Exception as e:
        _uy(f"SERVISE ULASILAMIYOR: {type(e).__name__}: {str(e)[:90]}"); sorun += 1

    print("\n=== 3. EPIZODIK BELLEK ===")
    ep = os.path.join(KOK, "data", "memory", "episodes.jsonl")
    if os.path.exists(ep) and os.path.getsize(ep) > 0:
        n = sum(1 for _ in open(ep, encoding="utf-8"))
        if a.uygula:
            yedek = ep + f".yedek_{time.strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(ep, yedek); open(ep, "w").close()
            _ok(f"{n} eski kayit YEDEKLENDI ve bellek bosaltildi ({os.path.basename(yedek)})")
        else:
            _uy(f"{n} eski kayit var — sohbet baglamina alakasiz gecmis sizar "
                f"(--uygula ile yedekleyip bosaltir)")
    else:
        _ok("epizodik bellek zaten bos")

    print("\n=== 4. .env ICINDEKI KULLANILMAYAN SIRLAR ===")
    env = os.path.join(KOK, ".env")
    riskli = []
    if os.path.exists(env):
        for satir in open(env, encoding="utf-8"):
            ad = satir.split("=")[0].strip()
            if ad in ("EVREN_QDRANT_KEY", "EVREN_CHAT_PAROLA", "EVREN_CHAT_KULLANICI"):
                riskli.append(ad)
    if riskli:
        _uy(f"kod KULLANMIYOR ama .env'de duruyor: {riskli} — "
            f"sunum makinesinde .env editorde acilirsa ekrana gelir")
    else:
        _ok(".env'de kullanilmayan sir yok")

    print("\n=== 5. PROVA EDILMIS DEMO KLIPLERI ===")
    for ad, n_yol, i_yol in DEMO_CIFTLERI:
        for etiket, y in (("normal", n_yol), ("ihlal ", i_yol)):
            tam = os.path.join(KOK, y)
            (_ok if os.path.exists(tam) else _uy)(f"{ad:9s} {etiket}: {os.path.basename(y)}")
            if not os.path.exists(tam): sorun += 1

    print(f"\n{'='*60}")
    print(f"SONUC: {sorun} sorun" + ("" if a.uygula else "   (--uygula ile duzeltmeleri isle)"))
    return 1 if sorun else 0


if __name__ == "__main__":
    raise SystemExit(main())
