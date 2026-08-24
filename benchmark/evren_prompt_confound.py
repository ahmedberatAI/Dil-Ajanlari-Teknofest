#!/usr/bin/env python
"""D42 — SISTEM PROMPTU x COZUNURLUK 2x2 FAKTORIYEL (KESFEDILEN CONFOUND TESTI).

=== NEDEN BU PROB VAR (kesif, izgara kosarken bulundu) ===
Devir notu su iddiayi tasiyordu ve TUM gorevin gerekcesiydi:
    "yelek 768->1280: MCC 0,000 -> 0,560 · McNemar p=0,0013 = GERCEK"
    "-> cozunurluk yelek sinifinda BELIRLEYICI"
Yeni izgara AYNI hucreyi (llm-large · yelek · 1280) olctu ve 44/50 "GORUNMUYOR"
buldu; MCC 0,000, DEJENERE. Klip klip karsilastirma (evren_izgara_replikasyon.py):
    llm-large · yelek · 768 : ESKI TARAMA 13/50 GORUNMUYOR · YENI IZGARA 47/50
    50 klibin 34'unde (%68) cevaplar FARKLI.
Nondeterminizm elendi: evren_kararlilik_probu.py -> 12/12 klipte tekrar BIREBIR ayni.
Iki on-kayit karsilastirilinca fark BULUNDU:
    evren_cozunurluk_onkayit_...json : "gonderim: ... SISTEM PROMPTU YOK"
    evren_model_kars.py / evren_izgara.py : SISTEM promptu VAR ve son cumlesi
        "Ayirt edemiyorsan KACIS secenegini kullan."
Yani eski tarama, D41 tabanina gore AYNI ANDA IKI SEYI degistirmisti
(sistem promptu + cozunurluk); iki kosumun sayilari tek bir tabloda birlestirilince
"cozunurluk etkisi" gibi gorundu. Tarama KENDI ICINDE temiz (uc cozunurlukte de
prompt yok), ama D41 ile KIYASLANAMAZ.

=== ON-KAYIT (SONUCLARA BAKILMADAN, KOSUMDAN ONCE ILAN EDILDI) ===
HIPOTEZ: yelek sinifinda llm-large'in cokusunun sebebi COZUNURLUK DEGIL,
  sistem promptundaki KACIS TALIMATIdir. Prompt kaldirilinca model cevap verir.
TASARIM: 2x2 TAM FAKTORIYEL, esli (ayni klipler, ayni baytlar)
  faktor A: sistem promptu {VAR (D41 metni) · YOK (mesajda system rolu hic yok)}
  faktor B: cozunurluk    {768/crf28 · 1280/crf26}
  model: llm-large (eski taramanin modeli) · sinif: yelek
  KLIPLER: YALNIZCA _tr (secim kumesi) — n=35. te'ye BAKILMAZ.
  T=0 · max_tokens=24 · structured_outputs.choice · istekler SIRAYLA
  = 4 hucre x 35 klip = 140 istek
BIRINCIL OLCU: KACIS ORANI (GORUNMUYOR + KISI_YOK) / n
  ON-KAYITLI KARAR: prompt ana etkisi "GERCEK" sayilir ancak ve ancak
    kacis oraninda prompt VAR -> YOK dususu, esli McNemar testinde p < 0,05
    VE her iki cozunurlukte de ayni yonde.
IKINCIL OLCU: MCC (karar verilenler) + ikincil sahada-dagitim MCC + dejenerelik.
COZUNURLUK ANA ETKISI: ayni prompt kosulunda 768 vs 1280, McNemar.
ETKILESIM: prompt YOK kosulunda cozunurluk etkisi, prompt VAR kosulundakinden
  buyukse etkilesim vardir (eski taramanin gordugu sey budur).

TAHMIN (kosumdan ONCE):
  P1 prompt VAR  -> kacis orani her iki cozunurlukte de >= 0,80
  P2 prompt YOK  -> kacis orani her iki cozunurlukte de <= 0,45
  P3 prompt ana etkisi McNemar p < 0,001 (buyuk ve net)
  P4 prompt VAR kosulunda 768->1280 cozunurluk etkisi GURULTU (p > 0,05)
  P5 asil belirleyici PROMPT'tur; cozunurluk ikincildir.

    python benchmark/evren_prompt_confound.py [--kuru]
"""
from __future__ import annotations

import argparse
import base64
import collections
import glob
import json
import math
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SET = os.environ.get("DILAJAN_PROB_SET") or os.path.join(KOK, "data/eval_defense")

SISTEM = ("Sen bir endustriyel is guvenligi kamerasi analiz sistemisin. Sana bir "
          "guvenlik kamerasindan alinmis kisa bir video verilir. YALNIZCA GORDUGUNE "
          "dayan; varsayim yapma. Ayirt edemiyorsan kacis secenegini kullan.")
GIRIS = "Bu guvenlik kamerasi videosunu inceleyeceğiz."
SORU = "Makinenin/panonun basinda duran kiside yesil reflektif yelek var mi?"
SECENEK = ["YELEK_VAR", "YELEK_YOK", "KISI_YOK", "GORUNMUYOR"]
KACIS = {"GORUNMUYOR", "KISI_YOK"}
MODEL = "llm-large"
COZ = [(768, 28), (1280, 26)]


def mcc(tp, fp, fn, tn):
    p = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return (tp * tn - fp * fn) / p if p else 0.0


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    q = k / n
    d = 1 + z * z / n
    m = (q + z * z / (2 * n)) / d
    y = z * math.sqrt(q * (1 - q) / n + z * z / (4 * n * n)) / d
    return (max(0.0, m - y), min(1.0, m + y))


def mcnemar(a, b):
    """a,b: esli ikili vektorler (True=olay). b=A'da 1 B'de 0 ..."""
    x = sum(1 for i, j in zip(a, b) if i and not j)
    y = sum(1 for i, j in zip(a, b) if j and not i)
    n = x + y
    if n == 0:
        return {"b": x, "c": y, "p": 1.0}
    k = min(x, y)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return {"b": x, "c": y, "p": round(min(1.0, p), 6)}


def tablo(kayitlar, ikincil=False):
    tp = fp = fn = tn = krsz = 0
    for et, c in kayitlar:
        k = None if c in KACIS else (True if c == "YELEK_YOK" else
                                     (False if c == "YELEK_VAR" else None))
        if k is None:
            if not ikincil:
                krsz += 1
                continue
            k = False
        if et and k:
            tp += 1
        elif et:
            fn += 1
        elif k:
            fp += 1
        else:
            tn += 1
    n = tp + fp + fn + tn
    lo, hi = wilson(tp + tn, n)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "kararsiz": krsz, "n": n,
            "mcc": round(mcc(tp, fp, fn, tn), 4),
            "dog": round((tp + tn) / n, 4) if n else 0.0,
            "ga95": [round(lo, 3), round(hi, 3)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kuru", action="store_true")
    a = ap.parse_args()

    ihlal = [(y, True) for y in sorted(glob.glob(
        os.path.join(SET, "Anomali/Unauthorized_Intervention/*.mp4")))]
    norm = [(y, False) for y in sorted(glob.glob(
        os.path.join(SET, "Normal/Authorized_Intervention/*.mp4")))]
    hepsi = ihlal + norm
    tr = [(y, e) for y, e in hepsi if "_tr" in os.path.basename(y)]
    print(f"2x2 FAKTORIYEL · model={MODEL} · sinif=yelek · YALNIZ tr · n={len(tr)}")
    print(f"  prompt: VAR/YOK  x  cozunurluk: 768/1280  = 4 hucre x {len(tr)} "
          f"= {4*len(tr)} istek")
    zaman = f"{datetime.now():%Y%m%d_%H%M%S}"
    ok = os.path.join(KOK, "benchmark/results", f"evren_prompt_confound_onkayit_{zaman}.json")
    with open(ok, "w", encoding="utf-8") as f:
        json.dump({"zaman": datetime.now().isoformat(timespec="seconds"),
                   "on_kayit": __doc__, "n_tr": len(tr)}, f, ensure_ascii=False, indent=2)
    print(f"on-kayit (KOSUMDAN ONCE): {ok}")
    if a.kuru:
        print("--kuru: cagri yok.")
        return

    from dilajan.llm_client import VLMClient
    from dilajan.video import servis_videosu
    from dilajan.config import settings
    if settings.mock_mode:
        print("HATA: DILAJAN_MOCK acik."); sys.exit(2)
    ist = VLMClient().client.with_options(timeout=300.0)

    sonuc = collections.defaultdict(dict)      # (prompt,coz) -> klip -> cevap
    etiket = {}
    for i, (yol, e) in enumerate(tr, 1):
        ad = os.path.basename(yol)
        etiket[ad] = e
        satir = []
        for ms, crf in COZ:
            baytlar = servis_videosu(yol, max_side=ms, crf=crf)
            url = "data:video/mp4;base64," + base64.b64encode(baytlar).decode()
            kul = [{"role": "user", "content": [
                {"type": "text", "text": GIRIS},
                {"type": "video_url", "video_url": {"url": url}}]},
                {"role": "user", "content": SORU}]
            for pr in ("VAR", "YOK"):
                msj = ([{"role": "system", "content": SISTEM}] + kul) if pr == "VAR" else kul
                c = None
                for _ in range(3):
                    try:
                        r = ist.chat.completions.create(
                            model=MODEL, messages=msj, temperature=0.0, max_tokens=24,
                            extra_body={"structured_outputs": {"choice": SECENEK}})
                        c = (r.choices[0].message.content or "").strip().upper()
                        break
                    except Exception:
                        time.sleep(5)
                sonuc[(pr, ms)][ad] = c or "__HATA__"
                satir.append(f"{pr}@{ms}={c}")
        print(f"  {i:3d}/{len(tr)} {ad:16s} " + " | ".join(satir), flush=True)

    print("\n" + "=" * 92)
    print(f"{'hucre':16s} {'kacis':>7s} {'TP':>3s}{'FP':>3s}{'FN':>3s}{'TN':>3s} "
          f"{'MCC':>8s} {'dog':>6s} {'ikincilMCC':>10s}  ham dagilim")
    ozet = {}
    for pr in ("VAR", "YOK"):
        for ms, _ in COZ:
            kl = sorted(sonuc[(pr, ms)])
            kay = [(etiket[k], sonuc[(pr, ms)][k]) for k in kl]
            kac = sum(1 for _, c in kay if c in KACIS) / len(kay)
            t, ik = tablo(kay), tablo(kay, ikincil=True)
            dg = collections.Counter(c for _, c in kay)
            ozet[(pr, ms)] = {"kacis": round(kac, 3), "ana": t, "ikincil": ik,
                              "dagilim": dict(dg.most_common())}
            print(f"prompt={pr}@{ms:<5d} {kac:7.0%} {t['tp']:3d}{t['fp']:3d}"
                  f"{t['fn']:3d}{t['tn']:3d} {t['mcc']:+8.3f} {t['dog']:6.3f} "
                  f"{ik['mcc']:+10.3f}  {dict(dg.most_common())}")

    print("\nESLI TESTLER (McNemar, kacis olayi uzerinde)")
    kl = sorted(etiket)
    for ms, _ in COZ:
        av = [sonuc[("VAR", ms)][k] in KACIS for k in kl]
        ay = [sonuc[("YOK", ms)][k] in KACIS for k in kl]
        m = mcnemar(av, ay)
        print(f"  PROMPT etkisi @{ms}: VAR-kacti/YOK-kacmadi={m['b']}  "
              f"YOK-kacti/VAR-kacmadi={m['c']}  p={m['p']}"
              + ("  <- GERCEK" if m["p"] < 0.05 else "  (gurultu)"))
    for pr in ("VAR", "YOK"):
        a7 = [sonuc[(pr, 768)][k] in KACIS for k in kl]
        a12 = [sonuc[(pr, 1280)][k] in KACIS for k in kl]
        m = mcnemar(a7, a12)
        print(f"  COZUNURLUK etkisi (prompt={pr}): 768-kacti/1280-kacmadi={m['b']}  "
              f"ters={m['c']}  p={m['p']}"
              + ("  <- GERCEK" if m["p"] < 0.05 else "  (gurultu)"))

    cik = os.path.join(KOK, "benchmark/results", f"evren_prompt_confound_{zaman}.json")
    with open(cik, "w", encoding="utf-8") as f:
        json.dump({"on_kayit_dosyasi": os.path.basename(ok),
                   "ham": {f"{p}@{m}": sonuc[(p, m)] for p, m in sonuc},
                   "etiket": etiket,
                   "ozet": {f"{p}@{m}": v for (p, m), v in ozet.items()}},
                  f, ensure_ascii=False, indent=2)
    print(f"\nyazildi: {cik}")


if __name__ == "__main__":
    main()
