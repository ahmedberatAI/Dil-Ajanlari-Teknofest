#!/usr/bin/env python
"""D42 — EVREN TAM IZGARA: model x cozunurluk x sinif (21 hucre).

    python benchmark/evren_izgara.py --kuru          # cagri yok, plani + on-kayit yaz
    python benchmark/evren_izgara.py --smoke 2       # her hucreden 2+2 klip
    python benchmark/evren_izgara.py                 # tam izgara (devam ettirilebilir)

=== ON-KAYIT (SONUCLARA BAKILMADAN, KOSUMDAN ONCE ILAN EDILDI) ===

IZGARA (ilan edildi; disina CIKILMAYACAK):
  model      : vlm · llm-large · llm-fast
  cozunurluk : 768/crf28 · 1280/crf26 · 1920/crf24
  sinif      : forklift(50) · yelek(50) · pano(49)
  pano ISTISNASI: D41'de pano'da cozunurlugun HIC etkisi olmadigi olculdu
    (768/1280/1920 -> UCU DE 49/49 "GORUNMUYOR", tek klip bile farkli degil, p=1,0).
    Bu yuzden pano YALNIZ 1280'de kosulur.
  TOPLAM = 3 model x 3 coz x 2 sinif (forklift,yelek) + 3 model x 1 coz x pano = 21 HUCRE

KOSUM SIRASI (deger sirasi; on-kayitta ilan edildi):
  1) yelek@1280  2) yelek@1920  3) yelek@768
  4) forklift@1280 5) forklift@1920 6) forklift@768  7) pano@1280
  (EN ONEMLI HUCRE: vlm@1280 ve vlm@1920, yelek — cunku yelek kazanani vlm idi
   ama cozunurluk taramasi YALNIZ llm-large ile yapilmisti = OLCUM BOSLUGU.)

KURULUM (sabit, tum hucrelerde AYNI):
  video yolu (kare yolu DEGIL — servis istek basina en fazla 2 goruntu kabul eder)
  servis_videosu(max_side, crf) · T=0 · max_tokens=24
  kisitli kod cozme: extra_body["structured_outputs"]["choice"]  (D40: eski
    `guided_choice` alanini vLLM 0.23 SESSIZCE YOK SAYIYORDU)
  KLIP (sinif,cozunurluk) basina BIR KEZ kodlanir ve base64 dizesi 3 modele de
    AYNEN gonderilir -> esli (paired) tasarim, kodlama farki kol farkina karismaz
  istekler SIRAYLA gonderilir (servis paylasimli) · hata basina 2 yeniden deneme
  sistem promptu ve soru metinleri D41 ile BIREBIR AYNI (karsilastirilabilirlik)

SORULAR (sabit — kaynak makale Onal & Dandil 2024, Data in Brief 56:110756):
  forklift: "Forkliftin catalinda ust uste kac adet kasa/blok tasiniyor? Yalnizca sayiyi yaz."
            secenek ["0","1","2","3","4","5","6+","GORUNMUYOR"] · kural >=3 kasa -> ihlal
  yelek   : "Makinenin/panonun basinda duran kiside yesil reflektif yelek var mi?"
            secenek ["YELEK_VAR","YELEK_YOK","KISI_YOK","GORUNMUYOR"] · yelek YOK -> ihlal
  pano    : "Elektrik/kontrol panosunun kapagi acik mi?"
            secenek ["ACIK","KAPALI","GORUNMUYOR"] · ACIK -> ihlal

*** SECIM / RAPOR AYRIMI (ZORUNLU) ***
  Klip adlarinda kaynak veri setinin KENDI bolunmesi var: "_tr" (train) · "_te" (test).
  TUM model/cozunurluk/esik SECIMI YALNIZCA _tr kliplerinde yapilir.
  MANSET SAYI YALNIZCA _te kliplerinden verilir. te'ye bakarak secim YAPILMAZ.
  n_tr: forklift 39 (21 ihlal + 18 normal) · yelek 35 (21+14) · pano 34 (21+13)
  n_te: forklift 11 (4+7)  · yelek 15 (4+11) · pano 15 (3+12)
  te kumeleri KUCUK -> te tek basina model SECTIRMEZ; yalniz tr'de secilenin
  tutup tutmadigini gosterir. te GA'lari genis olacak, bu ON-KAYITTA kabul edildi.

PUANLAMA (olcum disiplini):
  1. KACIS cevaplari (GORUNMUYOR / KISI_YOK) KARARSIZ sayilir; sessizce negatife
     CEVRILMEZ. ANA tablo yalnizca KARAR VERILEN kliplerden hesaplanir.
  2. TP/FP/FN/TN + kararsiz + hata HER ZAMAN ayri ayri yazilir.
  3. Ikincil "sahada dagitim" tablosu (kararsiz -> alarm yok) ACIKCA ikincil.
  4. Wilson %95 GA dogruluk uzerinden.

DEJENERELIK KAPISI (biri yeterli -> DEJENERE; MCC ne olursa olsun BASARI DEGIL):
  D1: en sik HAM cevap, koldaki TUM gecerli kliplerin >= %85'ini kapliyor
  D2: KARAR VERILEN klipler icinde bir taraf (ihlal / ihlal-degil) >= %85

COKLU KARSILASTIRMA DUZELTMESI (kosumdan once ilan):
  21 hucre deniyoruz; en iyisini secmek MCC'yi SISIRIR. Duzeltme:
  ETIKET PERMUTASYONU + MAKS-ISTATISTIGI. Her permutasyonda TUM hucrelerin
  MCC'si yeniden hesaplanir (AYNI permute edilmis etiketle, kliplerin esli
  yapisi KORUNARAK), maks|MCC| alinir; 10.000 permutasyondan bos dagilim kurulur.
  Bir hucre "coklu karsilastirmaya ragmen gercek" sayilir ancak ve ancak
  gozlenen MCC_tr >= bos maks-dagiliminin %95 kuantili.

BASARI OLCUTU (kosumdan once ilan; YALNIZ tr uzerinde uygulanir):
  Bir hucre KULLANILABILIR sayilir ancak ve ancak
    (a) DEJENERE degil, (b) MCC_tr >= +0,40, (c) karar orani >= 0,70,
    (d) dogruluk Wilson alt siniri > 0,50, (e) maks-permutasyon esigini gecti.
  Sinif kazanani = KULLANILABILIR hucreler icinde en yuksek MCC_tr.
  n~35'te 0,05 MCC farki GURULTUDUR -> berabere sayilir.

TAHMIN (kosumdan ONCE yazildi — tutup tutmadigi sonda bildirilecek):
  T1 vlm@1280 yelek, vlm@768 yelek'i (+0,500) GECER: MCC_tr +0,55..+0,75, DEJENERE degil.
  T2 vlm@1920 yelek ~ vlm@1280 yelek (fark <= 0,05 = berabere) — cunku llm-large'da
     1280->1920 GURULTU cikmisti.
  T3 llm-fast yelek 1280/1920'de de MCC < +0,40 kalir (768'de TN=0 idi).
  T4 forklift'te cozunurlugun etkisi kucuk: en iyi forklift hucresi ile
     llm-large@768 (+0,725) arasindaki fark <= 0,10; hicbir hucre +0,85'e ulasmaz.
  T5 pano@1280'de UC MODEL DE DEJENERE kalir (hepsi ~GORUNMUYOR).
  T6 Coklu karsilastirma bos dagiliminin %95 kuantili 0,45..0,60 araligina duser.
  T7 Genel en degerli yeni hucre = vlm@1280 yelek.

CIKTI:
  benchmark/results/evren_izgara_<zaman>.jsonl   (HER istek icin bir satir; ham cevap
      + gecikme + token; DEVAM ETTIRILEBILIR — ayni klip iki kez SORULMAZ)
  benchmark/results/evren_izgara_onkayit_<zaman>.json  (bu on-kayit, kosumdan ONCE)
"""
from __future__ import annotations

import argparse
import glob
import json
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
COZUNURLUKLER = [(768, 28), (1280, 26), (1920, 24)]
T, MAX_TOKENS = 0.0, 24
DENEME = 3          # 1 + 2 yeniden deneme
BEKLE = 5.0
ZAMAN_ASIMI = 300.0

# D41 ile BIREBIR AYNI (karsilastirilabilirlik icin degistirilmedi)
SISTEM = ("Sen bir endustriyel is guvenligi kamerasi analiz sistemisin. Sana bir "
          "guvenlik kamerasindan alinmis kisa bir video verilir. YALNIZCA GORDUGUNE "
          "dayan; varsayim yapma. Ayirt edemiyorsan kacis secenegini kullan.")
GIRIS = "Bu guvenlik kamerasi videosunu inceleyeceğiz."

SINIFLAR = {
    "forklift": {
        "ihlal": "Anomali/Carrying_Overload_with_Forklift",
        "normal": "Normal/Safe_Carrying",
        "soru": ("Forkliftin catalinda ust uste kac adet kasa/blok tasiniyor? "
                 "Yalnizca sayiyi yaz."),
        "secenek": ["0", "1", "2", "3", "4", "5", "6+", "GORUNMUYOR"],
        "kural": ">=3 kasa -> ihlal",
        "cozunurlukler": [768, 1280, 1920],
    },
    "yelek": {
        "ihlal": "Anomali/Unauthorized_Intervention",
        "normal": "Normal/Authorized_Intervention",
        "soru": "Makinenin/panonun basinda duran kiside yesil reflektif yelek var mi?",
        "secenek": ["YELEK_VAR", "YELEK_YOK", "KISI_YOK", "GORUNMUYOR"],
        "kural": "yelek YOK -> ihlal",
        "cozunurlukler": [768, 1280, 1920],
    },
    "pano": {
        "ihlal": "Anomali/Opened_Panel_Cover",
        "normal": "Normal/Closed_Panel_Cover",
        "soru": "Elektrik/kontrol panosunun kapagi acik mi?",
        "secenek": ["ACIK", "KAPALI", "GORUNMUYOR"],
        "kural": "ACIK -> ihlal",
        "cozunurlukler": [1280],          # D41: cozunurluk pano'da HIC fark yaratmadi
    },
}

# on-kayitta ilan edilen kosum sirasi.
# NOT (duzeltme, 12:20 — SONUCLARA BAKILMADAN, yalniz KAYNAK gerekcesiyle):
#   Smoke olcumu servisin su an D41'e gore ~5x yavas oldugunu gosterdi
#   (1280'de ~10 s/istek; D41'de 1,9 s). 1047 istegin tamami ~3,5 saat surer.
#   Kosum SIRASI degistirildi ki iki oncelikli hucre (yelek@1280, yelek@1920)
#   ONCE bitsin, en az bilgi tasidigi TAHMIN EDILEN pahali blok (forklift@1920)
#   EN SONA kalsin. HICBIR HUCRE DUSURULMEDI; izgara ayni 21 hucre.
#   Bu bir SONUC-SONRASI secim degil: hicbir tr sonucu goruilmeden yapildi.
SIRA = [("yelek", 1280), ("yelek", 1920), ("yelek", 768),
        ("forklift", 1280), ("forklift", 768), ("pano", 1280),
        ("forklift", 1920)]

CRF = {768: 28, 1280: 26, 1920: 24}


def klipler(sinif: str):
    """ihlal ve normal kliplerini SIRAYLA HARMANLAR (deterministik).

    NEDEN (duzeltme 12:5x, sonuclara bakilmadan): eskiden once TUM ihlal, sonra
    TUM normal klipler kosuluyordu. Kosum yarida kalirsa o hucrede YALNIZ pozitif
    sinif olur -> TN=FP=0, hucre YORUMLANAMAZ (yapay olarak "dejenere" gorunur).
    Harmanlanmis sirada yarim kalan hucre bile SINIF-DENGELI bir alt kume olur.
    Bu YALNIZCA SIRA degisikligidir: olculen klipler, sorular, kodlama, protokol
    AYNIDIR; hicbir sonuc etkilenmez (esli tasarim klip adiyla eslesir).
    """
    k = SINIFLAR[sinif]
    a = [(y, True) for y in sorted(glob.glob(os.path.join(SET, k["ihlal"], "*.mp4")))]
    b = [(y, False) for y in sorted(glob.glob(os.path.join(SET, k["normal"], "*.mp4")))]
    harman = []
    for i in range(max(len(a), len(b))):
        if i < len(a):
            harman.append(a[i])
        if i < len(b):
            harman.append(b[i])
    return harman


def bolum(ad: str) -> str:
    """Dosya adindan kaynak veri setinin kendi bolunmesi: tr (secim) / te (tutma)."""
    g = os.path.splitext(ad)[0]
    if "_tr" in g:
        return "tr"
    if "_te" in g:
        return "te"
    return "?"


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=KOK,
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return "?"


def _sor(client, model, url, soru, secenekler):
    """Tek istek. Doner: (cevap|None, giris_tok, cikis_tok, gecikme, hata)."""
    mesajlar = [
        {"role": "system", "content": SISTEM},
        {"role": "user", "content": [
            {"type": "text", "text": GIRIS},
            {"type": "video_url", "video_url": {"url": url}},
        ]},
        {"role": "user", "content": soru},
    ]
    t0 = time.time()
    try:
        r = client.chat.completions.create(
            model=model, messages=mesajlar, temperature=T, max_tokens=MAX_TOKENS,
            extra_body={"structured_outputs": {"choice": list(secenekler)}},
        )
    except Exception as e:
        return None, 0, 0, round(time.time() - t0, 2), f"{type(e).__name__}: {e}"[:300]
    gec = round(time.time() - t0, 2)
    u = getattr(r, "usage", None)
    gt = getattr(u, "prompt_tokens", 0) or 0
    ct = getattr(u, "completion_tokens", 0) or 0
    return (r.choices[0].message.content or ""), gt, ct, gec, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kuru", action="store_true")
    ap.add_argument("--smoke", type=int, default=0)
    ap.add_argument("--devam", default="", help="mevcut jsonl yolu (devam et)")
    ap.add_argument("--sadece", default="", help="or. 'yelek@1280,yelek@1920'")
    ap.add_argument("--modeller", default="",
                    help="virgulle ayrilmis alt kume (or. 'vlm'); bos=hepsi")
    a = ap.parse_args()

    global MODELLER
    if a.modeller:
        sec = [m.strip() for m in a.modeller.split(",") if m.strip()]
        bilinmeyen = [m for m in sec if m not in MODELLER]
        if bilinmeyen:
            print(f"HATA: bilinmeyen model {bilinmeyen}; gecerli: {MODELLER}")
            sys.exit(2)
        MODELLER = sec

    sira = SIRA
    if a.sadece:
        istek = [s.strip() for s in a.sadece.split(",") if s.strip()]
        sira = [(s, int(c)) for s, c in (i.split("@") for i in istek)]

    print("=== EVREN TAM IZGARA ===")
    print(f"set={SET}  git={git_commit()}")
    print(f"modeller={MODELLER}  T={T} max_tokens={MAX_TOKENS} structured_outputs=ACIK")
    toplam = 0
    for sinif, coz in sira:
        y = klipler(sinif)
        if a.smoke:
            y = [x for x in y if x[1]][:a.smoke] + [x for x in y if not x[1]][:a.smoke]
        tr = sum(1 for p, _ in y if bolum(os.path.basename(p)) == "tr")
        te = sum(1 for p, _ in y if bolum(os.path.basename(p)) == "te")
        toplam += len(y) * len(MODELLER)
        print(f"  {sinif:9s}@{coz:<5d} crf={CRF[coz]}  n={len(y):3d} (tr={tr} te={te})"
              f"  x{len(MODELLER)} model = {len(y)*len(MODELLER):4d} istek")
    print(f"  TOPLAM {len(sira)*len(MODELLER)} hucre · {toplam} istek")

    zaman = f"{datetime.now():%Y%m%d_%H%M%S}"
    os.makedirs(CIKTI_DIZIN, exist_ok=True)
    onkayit_yol = os.path.join(CIKTI_DIZIN, f"evren_izgara_onkayit_{zaman}.json")
    with open(onkayit_yol, "w", encoding="utf-8") as f:
        json.dump({"zaman": datetime.now().isoformat(timespec="seconds"),
                   "git": git_commit(), "on_kayit": __doc__,
                   "sira": [f"{s}@{c}" for s, c in sira],
                   "modeller": MODELLER, "T": T, "max_tokens": MAX_TOKENS,
                   "toplam_istek": toplam}, f, ensure_ascii=False, indent=2)
    print(f"on-kayit yazildi (KOSUMDAN ONCE): {onkayit_yol}")

    if a.kuru:
        print("--kuru: cagri yapilmadi.")
        return

    from dilajan.llm_client import VLMClient          # noqa: E402
    from dilajan.video import servis_videosu          # noqa: E402
    from dilajan.config import settings               # noqa: E402
    import base64                                     # noqa: E402

    if settings.mock_mode:
        print("HATA: DILAJAN_MOCK acik — olcum YAPILMAZ.")
        sys.exit(2)

    ham_istemci = VLMClient().client.with_options(timeout=ZAMAN_ASIMI)

    jsonl_yol = a.devam or os.path.join(
        CIKTI_DIZIN, f"evren_izgara_{'smoke_' if a.smoke else ''}{zaman}.jsonl")
    yapildi = set()
    if os.path.exists(jsonl_yol):
        with open(jsonl_yol, encoding="utf-8") as f:
            for l in f:
                try:
                    d = json.loads(l)
                except Exception:
                    continue
                # HATA (bulundu ve duzeltildi, 12:31): burada "cevap" yaziyordu ama
                # satirlar "ham_cevap" alaniyla yaziliyor -> DEVAM ETME CALISMIYORDU,
                # 312 satir yeniden sorulacakti. Yanlis alan adi duzeltildi.
                if d.get("ham_cevap") is not None:
                    yapildi.add((d["klip"], d["sinif"], d["model"], d["cozunurluk"]))
        print(f"devam: {len(yapildi)} istek zaten yapilmis, atlanacak")
    print(f"jsonl: {jsonl_yol}\n", flush=True)

    cikti = open(jsonl_yol, "a", encoding="utf-8")
    t_bas = time.time()
    sayac = 0
    for sinif, coz in sira:
        k = SINIFLAR[sinif]
        yollar = klipler(sinif)
        if a.smoke:
            yollar = ([x for x in yollar if x[1]][:a.smoke]
                      + [x for x in yollar if not x[1]][:a.smoke])
        print(f"\n=== {sinif}@{coz} (crf {CRF[coz]}) · n={len(yollar)} ===", flush=True)
        for i, (yol, ihlal) in enumerate(yollar, 1):
            ad = os.path.basename(yol)
            eksik = [m for m in MODELLER if (ad, sinif, m, coz) not in yapildi]
            if not eksik:
                continue
            try:
                e0 = time.time()
                baytlar = servis_videosu(yol, max_side=coz, crf=CRF[coz])
                enc_s = round(time.time() - e0, 2)
                url = "data:video/mp4;base64," + base64.b64encode(baytlar).decode()
            except Exception as e:
                for m in eksik:
                    cikti.write(json.dumps({
                        "klip": ad, "sinif": sinif, "bolum": bolum(ad), "etiket": int(ihlal),
                        "model": m, "cozunurluk": coz, "crf": CRF[coz],
                        "ham_cevap": None, "hata": f"__KODLAMA__{type(e).__name__}: {e}"[:200],
                        "gecikme": 0.0, "giris_tok": 0, "cikis_tok": 0,
                    }, ensure_ascii=False) + "\n")
                cikti.flush()
                print(f"  [KODLAMA HATASI] {ad}: {e}", flush=True)
                continue

            parcalar = []
            for m in eksik:                      # AYNI base64 dizesi, SIRAYLA
                cevap = hata = None
                for deneme in range(DENEME):
                    cevap, gt, ct, gec, hata = _sor(ham_istemci, m, url,
                                                    k["soru"], k["secenek"])
                    if cevap is not None:
                        break
                    if deneme < DENEME - 1:
                        time.sleep(BEKLE)
                cikti.write(json.dumps({
                    "klip": ad, "sinif": sinif, "bolum": bolum(ad), "etiket": int(ihlal),
                    "model": m, "cozunurluk": coz, "crf": CRF[coz],
                    "ham_cevap": cevap, "hata": hata,
                    "gecikme": gec, "giris_tok": gt, "cikis_tok": ct,
                    "bayt": len(baytlar), "enc_s": enc_s,
                    "deneme": deneme + 1,
                }, ensure_ascii=False) + "\n")
                sayac += 1
                parcalar.append(f"{m}={(cevap if cevap is not None else '__HATA__')[:14]}")
            cikti.flush()
            hiz = sayac / max(time.time() - t_bas, 1e-9)
            print(f"  {i:3d}/{len(yollar)} {ad[:20]:20s} {len(baytlar)/1e6:5.2f}MB  "
                  + " | ".join(parcalar) + f"   [{hiz*60:.0f} istek/dk]", flush=True)
    cikti.close()
    print(f"\nBITTI. {sayac} yeni istek · {time.time()-t_bas:.0f} s\nyazildi: {jsonl_yol}")


if __name__ == "__main__":
    main()
