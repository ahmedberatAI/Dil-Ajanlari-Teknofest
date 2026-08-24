#!/usr/bin/env python
"""D41 — EVREN servisi MODEL KARSILASTIRMASI: vlm vs llm-large vs llm-fast.

    python benchmark/evren_model_kars.py --kuru            # cagri yok, plani yazdir
    python benchmark/evren_model_kars.py --smoke 2         # her ciftten 2 klip (boru hatti testi)
    python benchmark/evren_model_kars.py                   # 149 klip x 3 model

=== ON-KAYIT (SONUCLARA BAKILMADAN, KOSUMDAN ONCE ILAN EDILDI) ===
KURULUM (sabit):
  video yolu (kare yolu DEGIL — servis istek basina en fazla 2 goruntu kabul ediyor)
  servis_videosu(max_side=768, crf=28) · T=0 · max_tokens=24 · guided_choice (structured_outputs.choice)
  ayni SISTEM promptu, ayni soru metni, ayni secenek listesi TUM modellerde
  KLIP BIR KEZ kodlanir, ayni baytlar 3 modele de gider (esli tasarim)
  istekler SIRAYLA gonderilir (servis paylasimli); hata basina en fazla 2 yeniden deneme

SORULAR (kaynak makale Onal & Dandil 2024 islemsel olcutleri):
  A forklift : "catalda kac kasa?"     >=3 -> ihlal
  B yelek    : "yesil reflektif yelek?" YOK -> ihlal
  C pano     : "kapak acik mi?"        ACIK -> ihlal

PUANLAMA (olcum disiplini):
  1. KACIS cevaplari (GORUNMUYOR / KISI_YOK) KARARSIZ sayilir; sessizce negatife
     CEVRILMEZ. Ana tablo yalnizca KARAR VERILEN kliplerden hesaplanir; kararsiz ve
     hata sayilari AYRICA yazilir.
  2. HATA alan klip hicbir kolda puanlanmaz, ayrica raporlanir.
  3. Ikincil "sahada dagitim" tablosu (kararsiz -> alarm yok) ACIKCA ikincil
     etiketiyle verilir; manşet sayi ANA tablodan gelir.
  4. TP/FP/FN/TN her zaman yazilir. Wilson %95 GA dogruluk uzerinden verilir.

DEJENERELIK KAPISI (ikisinden biri yeterli -> DEJENERE):
  D1: en sik HAM cevap, koldaki TUM kliplerin >= %85'ini kapliyor
  D2: KARAR VERILEN klipler icinde bir taraf (ihlal / ihlal-degil) >= %85
  DEJENERE kol, MCC ne olursa olsun BASARI SAYILMAZ.

BASARI OLCUTU (kosumdan once ilan):
  Bir kol KULLANILABILIR sayilir ancak ve ancak
    (a) DEJENERE degil, (b) MCC >= +0,40, (c) karar orani >= 0,70,
    (d) dogruluk Wilson alt sinir > 0,50.
  Sinif kazanani = DEJENERE olmayan kollar icinde en yuksek MCC.
  n~50'de 0,05 MCC farki GURULTUDUR -> berabere sayilir.

YEREL TABAN (Qwen3-VL-8B-FP8, 24GB dizustu) — asilmasi gereken cizgi:
  forklift islemsel MCC +0,762 (dogruluk 0,880) · yelek +0,000 DEJENERE (50/50 KISI_YOK)
  pano +0,000 DEJENERE (49/49 GORUNMUYOR)
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SET = os.environ.get("DILAJAN_PROB_SET") or os.path.join(KOK, "data/eval_defense")
CIKTI_DIZIN = os.path.join(KOK, "benchmark/results")

MODELLER = ["vlm", "llm-large", "llm-fast"]
MAX_SIDE, CRF, T, MAX_TOKENS = 768, 28, 0.0, 24
DENEME = 3          # 1 + 2 yeniden deneme
BEKLE = 5.0         # saniye, yeniden denemeler arasi

SISTEM = ("Sen bir endustriyel is guvenligi kamerasi analiz sistemisin. Sana bir "
          "guvenlik kamerasindan alinmis kisa bir video verilir. YALNIZCA GORDUGUNE "
          "dayan; varsayim yapma. Ayirt edemiyorsan kacis secenegini kullan.")
GIRIS = "Bu guvenlik kamerasi videosunu inceleyeceğiz."


# --------------------------------------------------------------- cevap yorumlayici
def _kasa(c):
    """>=3 kasa -> ihlal. Doner: True/False/None(kararsiz)."""
    c = (c or "").strip().upper()
    if c in ("GORUNMUYOR", ""):
        return None
    if c.endswith("+"):
        c = c[:-1]
    try:
        return int(c) >= 3
    except ValueError:
        return None


def _yelek(c):
    """Yelek YOK -> ihlal. KISI_YOK / GORUNMUYOR -> kararsiz."""
    c = (c or "").strip().upper()
    if c == "YELEK_YOK":
        return True
    if c == "YELEK_VAR":
        return False
    return None


def _pano(c):
    """ACIK -> ihlal. GORUNMUYOR -> kararsiz."""
    c = (c or "").strip().upper()
    if c == "ACIK":
        return True
    if c == "KAPALI":
        return False
    return None


KOLLAR = [
    {"ad": "forklift", "ihlal": "Anomali/Carrying_Overload_with_Forklift",
     "normal": "Normal/Safe_Carrying",
     "soru": ("Forkliftin catalinda ust uste kac adet kasa/blok tasiniyor? "
              "Yalnizca sayiyi yaz."),
     "secenek": ["0", "1", "2", "3", "4", "5", "6+", "GORUNMUYOR"],
     "yorum": _kasa, "kural": ">=3 kasa -> ihlal",
     "yerel_taban": {"mcc": 0.762, "dogruluk": 0.880, "dejenere": False,
                     "not": "islemsel soru, Qwen3-VL-8B-FP8 yerel"}},
    {"ad": "yelek", "ihlal": "Anomali/Unauthorized_Intervention",
     "normal": "Normal/Authorized_Intervention",
     "soru": "Makinenin/panonun basinda duran kiside yesil reflektif yelek var mi?",
     "secenek": ["YELEK_VAR", "YELEK_YOK", "KISI_YOK", "GORUNMUYOR"],
     "yorum": _yelek, "kural": "yelek YOK -> ihlal",
     "yerel_taban": {"mcc": 0.000, "dogruluk": None, "dejenere": True,
                     "not": "50/50 KISI_YOK — yerel model kisiyi bulamadi"}},
    {"ad": "pano", "ihlal": "Anomali/Opened_Panel_Cover",
     "normal": "Normal/Closed_Panel_Cover",
     "soru": "Elektrik/kontrol panosunun kapagi acik mi?",
     "secenek": ["ACIK", "KAPALI", "GORUNMUYOR"],
     "yorum": _pano, "kural": "ACIK -> ihlal",
     "yerel_taban": {"mcc": 0.000, "dogruluk": None, "dejenere": True,
                     "not": "49/49 GORUNMUYOR"}},
]


# --------------------------------------------------------------------- istatistik
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


def tablo(satirlar, ikincil=False):
    """satirlar: [{ihlal: bool, karar: True/False/None, hata: bool, ham: str}]

    ikincil=True -> kararsizlar 'alarm yok' (False) sayilir (SAHADA DAGITIM tablosu).
    """
    tp = fp = fn = tn = kararsiz = hata = 0
    for r in satirlar:
        if r["hata"]:
            hata += 1
            continue
        k = r["karar"]
        if k is None:
            if not ikincil:
                kararsiz += 1
                continue
            k = False
        if r["ihlal"] and k:
            tp += 1
        elif r["ihlal"]:
            fn += 1
        elif k:
            fp += 1
        else:
            tn += 1
    n = tp + fp + fn + tn
    m = mcc(tp, fp, fn, tn)
    dog = (tp + tn) / n if n else 0.0
    lo, hi = wilson(tp + tn, n)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "kararsiz": kararsiz,
            "hata": hata, "n_karar": n, "mcc": round(m, 4),
            "dogruluk": round(dog, 4), "ga95": [round(lo, 4), round(hi, 4)]}


def dejenere_kontrol(satirlar):
    """D1: en sik ham cevap >= %85 tum klipler. D2: karar verilenlerde bir taraf >= %85."""
    gecerli = [r for r in satirlar if not r["hata"]]
    n = len(gecerli)
    sayim = {}
    for r in gecerli:
        h = (r["ham"] or "").strip().upper() or "(BOS)"
        sayim[h] = sayim.get(h, 0) + 1
    en_sik, en_sik_n = ("", 0)
    if sayim:
        en_sik, en_sik_n = max(sayim.items(), key=lambda kv: kv[1])
    d1 = bool(n) and en_sik_n >= 0.85 * n
    kararli = [r for r in gecerli if r["karar"] is not None]
    nk = len(kararli)
    poz = sum(1 for r in kararli if r["karar"])
    d2 = bool(nk) and (poz >= 0.85 * nk or (nk - poz) >= 0.85 * nk)
    return {"dejenere": bool(d1 or d2), "D1_ham_cevap": d1, "D2_karar": d2,
            "en_sik_cevap": en_sik, "en_sik_oran": round(en_sik_n / n, 4) if n else 0.0,
            "ham_dagilim": dict(sorted(sayim.items(), key=lambda kv: -kv[1]))}


def kullanilabilir(dej, ana, karar_orani):
    return (not dej["dejenere"] and ana["mcc"] >= 0.40 and karar_orani >= 0.70
            and ana["ga95"][0] > 0.50)


# --------------------------------------------------------------------------- kosum
def klipler(kol):
    a = [(y, True) for y in sorted(glob.glob(os.path.join(SET, kol["ihlal"], "*.mp4")))]
    b = [(y, False) for y in sorted(glob.glob(os.path.join(SET, kol["normal"], "*.mp4")))]
    return a + b


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=KOK,
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kuru", action="store_true")
    ap.add_argument("--smoke", type=int, default=0,
                    help="her siniftan N klip (boru hatti testi)")
    ap.add_argument("--kol", default="hepsi",
                    choices=["hepsi", "forklift", "yelek", "pano"])
    ap.add_argument("--modeller", default="",
                    help="virgulle ayrilmis alt kume (or. 'vlm,llm-fast'); bos=hepsi")
    ap.add_argument("--etiket", default="", help="cikti dosyasi adina ek (or. 'tekrar')")
    a = ap.parse_args()

    global MODELLER
    if a.modeller:
        secilen = [m.strip() for m in a.modeller.split(",") if m.strip()]
        bilinmeyen = [m for m in secilen if m not in MODELLER]
        if bilinmeyen:
            print(f"HATA: bilinmeyen model {bilinmeyen}; gecerli: {MODELLER}")
            sys.exit(2)
        MODELLER = secilen

    kollar = [k for k in KOLLAR if a.kol in ("hepsi", k["ad"])]
    print(f"set={SET}\nmodeller={MODELLER}\n"
          f"kurulum: max_side={MAX_SIDE} crf={CRF} T={T} max_tokens={MAX_TOKENS} "
          f"guided_choice=ACIK\ngit={git_commit()}\n")
    for k in kollar:
        y = klipler(k)
        if a.smoke:
            y = [x for x in y if x[1]][:a.smoke] + [x for x in y if not x[1]][:a.smoke]
        print(f"kol={k['ad']:9s} n={len(y):3d}  kural={k['kural']}\n"
              f"   soru: {k['soru']}\n   secenek: {k['secenek']}")
    if a.kuru:
        print("\n--kuru: cagri yapilmadi.")
        return

    from dilajan.llm_client import VLMClient          # noqa: E402
    from dilajan.video import servis_videosu          # noqa: E402
    from dilajan.config import settings               # noqa: E402

    if settings.mock_mode:
        print("HATA: DILAJAN_MOCK acik — olcum YAPILMAZ.")
        sys.exit(2)

    taban = VLMClient()
    istemciler = {m: VLMClient(model=m) for m in MODELLER}
    for m, c in istemciler.items():
        print(f"  saglik {m}: {'AYAKTA' if c.health_check() else 'YOK'}")

    sonuc = {"kunye": {"zaman": datetime.now().isoformat(timespec="seconds"),
                       "git": git_commit(), "set": SET, "modeller": MODELLER,
                       "max_side": MAX_SIDE, "crf": CRF, "temperature": T,
                       "max_tokens": MAX_TOKENS, "guided_choice": True,
                       "deneme": DENEME, "smoke": a.smoke,
                       "base_url_host": settings.base_url.split("//")[-1].split("/")[0],
                       "sistem_prompt": SISTEM, "argv": sys.argv[1:]},
              "on_kayit": __doc__.split("=== ON-KAYIT")[1].split('"""')[0],
              "kollar": {}}

    for k in kollar:
        yollar = klipler(k)
        if a.smoke:
            yollar = ([x for x in yollar if x[1]][:a.smoke]
                      + [x for x in yollar if not x[1]][:a.smoke])
        print(f"\n=== KOL {k['ad']} · n={len(yollar)} ===", flush=True)
        satirlar = {m: [] for m in MODELLER}
        klip_kayit = []
        t0 = time.time()
        for i, (yol, ihlal) in enumerate(yollar, 1):
            ad = os.path.basename(yol)
            try:
                baytlar = servis_videosu(yol, max_side=MAX_SIDE, crf=CRF)
            except Exception as e:
                print(f"  [KODLAMA HATASI] {ad}: {e}")
                for m in MODELLER:
                    satirlar[m].append({"ihlal": ihlal, "karar": None, "hata": True,
                                        "ham": f"__KODLAMA__{type(e).__name__}"})
                continue
            kayit = {"klip": ad, "ihlal": ihlal, "boyut_kb": round(len(baytlar) / 1024, 1),
                     "cevap": {}, "sure": {}}
            for m in MODELLER:                      # AYNI baytlar, SIRAYLA
                ham, hata_mesaji, s0 = None, None, time.time()
                for deneme in range(DENEME):
                    otu = istemciler[m].video_oturumu(baytlar, system=SISTEM,
                                                      giris_metni=GIRIS)
                    if not otu.hazir:
                        hata_mesaji = otu.hata
                        break
                    c = otu.sor(k["soru"], guided_choice=k["secenek"],
                                temperature=T, max_tokens=MAX_TOKENS, hatirla=False)
                    if c is not None:
                        ham, hata_mesaji = c, None
                        break
                    hata_mesaji = otu.hata
                    if deneme < DENEME - 1:
                        time.sleep(BEKLE)
                sure = round(time.time() - s0, 2)
                hatali = ham is None
                satirlar[m].append({
                    "ihlal": ihlal, "hata": hatali, "ham": ham if ham else (hata_mesaji or ""),
                    "karar": None if hatali else k["yorum"](ham)})
                kayit["cevap"][m] = ham if not hatali else f"__HATA__ {hata_mesaji}"
                kayit["sure"][m] = sure
            klip_kayit.append(kayit)
            print(f"  {i:3d}/{len(yollar)} {ad[:42]:42s} "
                  + " | ".join(f"{m}={str(kayit['cevap'][m])[:24]}" for m in MODELLER),
                  flush=True)

        kol_sonuc = {"soru": k["soru"], "secenek": k["secenek"], "kural": k["kural"],
                     "n_klip": len(yollar), "yerel_taban": k["yerel_taban"],
                     "sure_s": round(time.time() - t0, 1), "klipler": klip_kayit,
                     "modeller": {}}
        for m in MODELLER:
            ana = tablo(satirlar[m])
            ikn = tablo(satirlar[m], ikincil=True)
            dej = dejenere_kontrol(satirlar[m])
            gecerli = len([r for r in satirlar[m] if not r["hata"]])
            karar_orani = round(ana["n_karar"] / gecerli, 4) if gecerli else 0.0
            kol_sonuc["modeller"][m] = {
                "ana": ana, "ikincil_dagitim": ikn, "dejenere_kapisi": dej,
                "karar_orani": karar_orani,
                "kullanilabilir": kullanilabilir(dej, ana, karar_orani)}
        sonuc["kollar"][k["ad"]] = kol_sonuc

        print(f"\n  --- {k['ad']} ozet ---")
        for m in MODELLER:
            r = kol_sonuc["modeller"][m]
            e = r["ana"]
            print(f"  {m:10s} TP={e['tp']:2d} FP={e['fp']:2d} FN={e['fn']:2d} TN={e['tn']:2d} "
                  f"kararsiz={e['kararsiz']:2d} hata={e['hata']:2d} MCC={e['mcc']:+.3f} "
                  f"dog={e['dogruluk']:.3f} [{e['ga95'][0]:.3f}-{e['ga95'][1]:.3f}] "
                  f"karar_orani={r['karar_orani']:.2f}"
                  + ("  ** DEJENERE **" if r["dejenere_kapisi"]["dejenere"] else "")
                  + ("  [KULLANILABILIR]" if r["kullanilabilir"] else ""))
            print(f"             ham dagilim: {r['dejenere_kapisi']['ham_dagilim']}")

    os.makedirs(CIKTI_DIZIN, exist_ok=True)
    etiket = ("smoke_" if a.smoke else "") + (f"{a.etiket}_" if a.etiket else "")
    yol = os.path.join(CIKTI_DIZIN,
                       f"evren_model_kars_{etiket}{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=2)
    print(f"\nyazildi: {yol}")


if __name__ == "__main__":
    main()
