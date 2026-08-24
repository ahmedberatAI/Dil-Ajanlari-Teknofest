#!/usr/bin/env python
"""D42 — KACIS SECENEGI TAMIRI: llm-large neden hep "GORUNMUYOR" diyor?

    python benchmark/evren_kacis.py --kuru               # cagri yok, plani yazdir
    python benchmark/evren_kacis.py --smoke 2            # her siniftan 2+2 klip
    python benchmark/evren_kacis.py                      # yelek n=50 + pano n=49
    python benchmark/evren_kacis.py --analiz <jsonl>     # yeniden cagri YOK, sadece hesap

=====================================================================
=== ON-KAYIT — KOSUMDAN ONCE ILAN EDILDI, SONUCLARA BAKILMADI     ===
=====================================================================

OLCULEN SORUN (D41): llm-large @768px, yelek sorusunda 47/50, pano sorusunda 49/49
"GORUNMUYOR" dedi. Ayni model forklift SAYMA sorusunda 50/50 karar verdi.
Yetenek var; bu soru tipinde KACINIYOR.

SABIT KURULUM (tum kollarda AYNI, degistirilmez):
  model llm-large · servis_videosu(max_side=1280, crf=26) · T=0 · max_tokens=24
  structured_outputs.choice (kisitli kod cozme) · video yolu (kare yolu DEGIL)
  KLIP BIR KEZ kodlanir; ayni baytlar TUM kollara gider  -> ESLI (paired) tasarim
  her soru hatirla=False -> kollar birbirini KIRLETMEZ
  istekler SIRAYLA; hata basina 2 yeniden deneme
  Cozunurluk 1280 secildi: D41 taramasi yelek 768->1280 MCC 0,000->0,560
  (McNemar p=0,0013) gosterdi; pano'da 768/1280/1920 farksizdi. 1280 ORTAK zemin.

IZGARA — 2 SINIF x 6 KOL = 12 HUCRE (sonuclara bakmadan ilan edildi, disina cikilmaz)
  A0  TABAN     : D41 sorusu + D41 sistem promptu, YALNIZCA cozunurluk 1280.
                  (768 tabanini 1280'de yeniden olcmeden hicbir hipotez yorumlanamaz)
  H1  KACISSIZ  : secenek listesinden TUM kacislar (GORUNMUYOR/KISI_YOK) CIKARILDI.
  H2  IKI ASAMA : (1) "nesne/kisi var mi?"  (2) varsa asil soru. Iki cagri.
  H3  SISTEM    : sistem promptundaki "Ayirt edemiyorsan kacis secenegini kullan"
                  cumlesi TERSINE cevrildi. Soru ve secenekler A0 ile BIREBIR AYNI.
  H4  CAPA      : soru metnine somut gorsel capa ("parlak sari-yesil (lime)").
  H5  TERSINE   : soru olumsuz soruldu + secenek SIRASI ters (konum yanliligi testi).

ZORUNLU SECIM/RAPOR AYRIMI:
  Klip adlarindaki "_tr" (kaynak veri setinin train bolumu) SECIM kumesi,
  "_te" TUTMA kumesidir. TUM kol/hipotez secimi YALNIZ _tr'de yapilir.
  _te ayrica raporlanir ve secime KARISTIRILMAZ.
  n(_tr): yelek 35 (21 ihlal/14 normal) · pano 34 (21/13)
  n(_te): yelek 15 (4/11)  · pano 15 (3/12)
  -> _te'de pozitif sinif 3-4 klip. ON-KAYIT: _te KARAR VERDIRMEZ, yalnizca
     "secim _te'de catirdiyor mu" diye BAKILIR. _te'den mansetsayi VERILMEZ.

PUANLAMA (D41 ile ayni, degistirilmedi):
  1. KACIS cevabi (GORUNMUYOR / KISI_YOK / PANO_YOK) KARARSIZ sayilir; sessizce
     negatife CEVRILMEZ. Ana tablo yalniz KARAR VERILEN kliplerden hesaplanir.
  2. HATA alan klip puanlanmaz, ayrica yazilir.
  3. Ikincil "sahada dagitim" tablosu (kararsiz -> alarm yok) ACIKCA ikincil.
  4. TP/FP/FN/TN HER ZAMAN yazilir. Wilson %95 GA verilir.
  KARAR ORANI = karar verilen / (hatasiz klip). Karar vermeyen model sahada
  ISE YARAMAZ -> karar orani en az MCC kadar onemli raporlanir.

DEJENERELIK KAPISI (D33 tuzagi — 2 kez dusuldu; ikisinden biri yeterli):
  D1: en sik HAM cevap, koldaki TUM hatasiz kliplerin >= %85'ini kapliyor
  D2: KARAR VERILEN klipler icinde bir taraf >= %85
  DEJENERE kol MCC ne olursa olsun BASARI SAYILMAZ. H1 (kacissiz) bu kapiya
  OZELLIKLE bakilacak: kacisi kaldirmak sahte-pozitif/negatif uretebilir.

COKLU KARSILASTIRMA DUZELTMESI (12 hucre deniyoruz):
  Sinif ICINDE etiketler permute edilir (2000 tur); HER turda 6 kolun MCC'si AYNI
  permute etiketle yeniden hesaplanir ve max|MCC| alinir -> bos dagilim.
  Raporlanan: bos max|MCC| dagiliminin %95 kuantili ve gozlenen en iyi kolun
  duzeltilmis p degeri. Kollar ESLI oldugu icin bu, kollar arasi korelasyonu korur.

BASARI OLCUTU (kosumdan once ilan; hepsi saglanmali):
  Bir kol "TAMIR" sayilir <=> (a) DEJENERE degil, (b) _tr MCC >= +0,40,
  (c) karar orani >= 0,70, (d) _tr MCC > bos max|MCC| dagiliminin %95 kuantili.
  A0'a gore ustunluk ayrica esli McNemar ile sinanir (dogruluk ve karar-verme).
  n~35'te 0,05 MCC farki GURULTUDUR -> berabere denir.

=====================================================================
=== TAHMINIM (kosumdan ONCE yazildi; sonunda tuttu/tutmadi denir)  ===
=====================================================================
T1 A0@1280 yelek karar orani >= 0,50 olacak. Yani "47/50 GORUNMUYOR" buyuk olcude
   768px ARTEFAKTI idi; D41 cozunurluk taramasi bunu zaten ima ediyor (0,000->0,560).
   Bu tutarsa "kacis cok kolay" hipotezi yelekte KISMEN konu disi kalir.
T2 H1 (kacissiz) yelek: karar orani TANIM GEREGI 1,00. MCC, A0'dan 0,10'dan fazla
   DUSMEYECEK ve DEJENERE OLMAYACAK. (yelek gorunur bir oznitelik; pano'dan farkli)
T3 H3 (sistem promptu) yelekte karar oranini A0'a gore >= 0,15 artiracak,
   ama MCC farki 0,10'un altinda (gurultu) kalacak.
T4 H4 (lime capasi) yelekte etkisi GURULTU seviyesinde (|dMCC| < 0,10).
T5 H2 (iki asama) yelekte kliplerin >= %80'inde KISI_VAR diyecek; yani "once kisiyi
   bul" darbogazi 1280'de ANA sebep DEGIL.
T6 PANO: HICBIR kol TAMIR olcutunu gecmeyecek. Ozellikle H1 (kacissiz) pano'da
   DEJENERE cikacak (model neredeyse tum kliplere ayni etiketi verecek; D33'te
   20/20 "KAPALI" demisti). Pano darbogazi SORU FORMULASYONU DEGIL, ALGI.
   Bu tahmin YANLIS cikarsa bu, gorevin en degerli bulgusu olur ve oyle yazilir.
T7 Genel: en iyi yelek kolunun _tr MCC'si +0,40..+0,70 araliginda olacak ve
   coklu-karsilastirma duzeltmesinden SAG cikacak; pano'da hicbir kol cikmayacak.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import subprocess
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SET = os.environ.get("DILAJAN_PROB_SET") or os.path.join(KOK, "data/eval_defense")
CIKTI_DIZIN = os.path.join(KOK, "benchmark/results")

MODEL = "llm-large"
MAX_SIDE, CRF, T, MAX_TOKENS = 1280, 26, 0.0, 24
DENEME = 3
BEKLE = 5.0
PERM = 2000
TOHUM = 20260824

# --- sistem promptlari -------------------------------------------------------
# A0/H1/H2/H4/H5 bu sistemi kullanir (D41 ile BIREBIR AYNI — taban korunur)
SIS_TABAN = ("Sen bir endustriyel is guvenligi kamerasi analiz sistemisin. Sana bir "
             "guvenlik kamerasindan alinmis kisa bir video verilir. YALNIZCA GORDUGUNE "
             "dayan; varsayim yapma. Ayirt edemiyorsan kacis secenegini kullan.")
# H3: SON CUMLE tersine cevrildi; gerisi HARF HARF ayni (tek degisken)
SIS_KACIS_ZOR = ("Sen bir endustriyel is guvenligi kamerasi analiz sistemisin. Sana bir "
                 "guvenlik kamerasindan alinmis kisa bir video verilir. YALNIZCA GORDUGUNE "
                 "dayan; varsayim yapma. Goruntu bulanik, uzak veya kismi olsa bile en "
                 "olasi secenegi isaretle; kacis secenegini YALNIZCA ilgili nesne karede "
                 "hic yoksa kullan.")
GIRIS = "Bu guvenlik kamerasi videosunu inceleyeceğiz."


# --- cevap yorumlayicilar (ihlal=True / degil=False / kararsiz=None) ---------
def _y_taban(c):
    c = (c or "").strip().upper()
    return {"YELEK_YOK": True, "YELEK_VAR": False}.get(c)


def _y_ters(c):
    c = (c or "").strip().upper()
    return {"YELEKSIZ": True, "YELEKLI": False}.get(c)


def _p_taban(c):
    c = (c or "").strip().upper()
    return {"ACIK": True, "KAPALI": False}.get(c)


def _p_capa(c):
    c = (c or "").strip().upper()
    return {"IC_GORUNUYOR": True, "IC_GORUNMUYOR": False}.get(c)


def _p_ters(c):
    c = (c or "").strip().upper()
    return {"KAPAK_ACIK": True, "KAPAK_KAPALI": False}.get(c)


# --- izgara ------------------------------------------------------------------
# her kol: (ad, sistem, [(soru, secenek)], yorum, kapi)
#   kapi=None  -> tek asama
#   kapi=(secenek_deger, ...) -> ilk soru bu cevabi verirse ikinci soru sorulur,
#                                vermezse kol KARARSIZ (kacis) sayilir
YELEK_SORU = "Makinenin/panonun basinda duran kiside yesil reflektif yelek var mi?"
PANO_SORU = "Elektrik/kontrol panosunun kapagi acik mi?"

SINIFLAR = [
    {
        "ad": "yelek",
        "ihlal_dizin": "Anomali/Unauthorized_Intervention",
        "normal_dizin": "Normal/Authorized_Intervention",
        "kural": "yelek YOK -> ihlal",
        "d41_taban_768": {"mcc": 0.000, "karar_orani": 0.06,
                          "not": "47/50 GORUNMUYOR (llm-large @768)"},
        "kollar": [
            {"ad": "A0_taban", "sistem": SIS_TABAN, "yorum": _y_taban,
             "sorular": [(YELEK_SORU, ["YELEK_VAR", "YELEK_YOK", "KISI_YOK", "GORUNMUYOR"])]},
            {"ad": "H1_kacissiz", "sistem": SIS_TABAN, "yorum": _y_taban,
             "sorular": [(YELEK_SORU, ["YELEK_VAR", "YELEK_YOK"])]},
            {"ad": "H2_iki_asama", "sistem": SIS_TABAN, "yorum": _y_taban,
             "kapi": "KISI_VAR",
             "sorular": [("Bu videoda makinenin/panonun yakininda bir insan goruluyor mu?",
                          ["KISI_VAR", "KISI_YOK"]),
                         ("O kiside yesil reflektif yelek var mi?",
                          ["YELEK_VAR", "YELEK_YOK", "GORUNMUYOR"])]},
            {"ad": "H3_sistem", "sistem": SIS_KACIS_ZOR, "yorum": _y_taban,
             "sorular": [(YELEK_SORU, ["YELEK_VAR", "YELEK_YOK", "KISI_YOK", "GORUNMUYOR"])]},
            {"ad": "H4_capa", "sistem": SIS_TABAN, "yorum": _y_taban,
             "sorular": [("Makinenin/panonun basinda duran kisi, parlak sari-yesil (lime) "
                          "renkli reflektif is yelegi giyiyor mu?",
                          ["YELEK_VAR", "YELEK_YOK", "KISI_YOK", "GORUNMUYOR"])]},
            {"ad": "H5_tersine", "sistem": SIS_TABAN, "yorum": _y_ters,
             "sorular": [("Makinenin/panonun basinda duran kisi, reflektif is yelegi "
                          "GIYMEDEN mi calisiyor?",
                          ["YELEKSIZ", "YELEKLI", "KISI_YOK", "GORUNMUYOR"])]},
            # --- EK ON-KAYIT (ilk kosumdan SONRA, ama BU KOLLAR KOSULMADAN once
            # ilan edildi; gerekce ve beklenti asagida) ------------------------
            # BULGU: D41 cozunurluk taramasi (evren_cozunurluk_20260824_120530.json)
            # yelek @768'de yalnizca 20/50 cekimser gordu; D41 model karsilastirmasi
            # AYNI model + AYNI soru + AYNI 768px ile 47/50 GORUNMUYOR gordu.
            # TEK FARK: cozunurluk taramasinda SISTEM PROMPTU HIC YOKTU.
            # Yani "kacis" davranisi buyuk olcude SISTEM PROMPTUNDAN geliyor olabilir.
            # H3 o cumleyi yumusatti ama promptu KALDIRMADI -> eksik hucre.
            # Bu iki kol 2x2 tasarimi TAMAMLAR:
            #        kacis VAR        kacis YOK
            #  sis:  A0               H1
            #  sissiz: F1             F2
            # BEKLENTIM (kosumdan once): F1 karar oranini A0'a gore BUYUK olcude
            # artiracak (>= +0,40) — yani kacisin ana sebebi sistem promptu.
            # F2'nin MCC'si H1'e YAKIN cikacak (fark < 0,10 = gurultu).
            {"ad": "F1_sissiz_kacisli", "sistem": None, "yorum": _y_taban,
             "sorular": [(YELEK_SORU, ["YELEK_VAR", "YELEK_YOK", "KISI_YOK", "GORUNMUYOR"])]},
            {"ad": "F2_sissiz_kacissiz", "sistem": None, "yorum": _y_taban,
             "sorular": [(YELEK_SORU, ["YELEK_VAR", "YELEK_YOK"])]},
        ],
    },
    {
        "ad": "pano",
        "ihlal_dizin": "Anomali/Opened_Panel_Cover",
        "normal_dizin": "Normal/Closed_Panel_Cover",
        "kural": "kapak ACIK -> ihlal",
        "d41_taban_768": {"mcc": 0.000, "karar_orani": 0.00,
                          "not": "49/49 GORUNMUYOR (llm-large @768/1280/1920 AYNI)"},
        "kollar": [
            {"ad": "A0_taban", "sistem": SIS_TABAN, "yorum": _p_taban,
             "sorular": [(PANO_SORU, ["ACIK", "KAPALI", "GORUNMUYOR"])]},
            {"ad": "H1_kacissiz", "sistem": SIS_TABAN, "yorum": _p_taban,
             "sorular": [(PANO_SORU, ["ACIK", "KAPALI"])]},
            {"ad": "H2_iki_asama", "sistem": SIS_TABAN, "yorum": _p_taban,
             "kapi": "PANO_VAR",
             "sorular": [("Bu videoda duvara veya makineye monte bir elektrik/kontrol "
                          "panosu (metal dolap veya kutu) goruluyor mu?",
                          ["PANO_VAR", "PANO_YOK"]),
                         ("O panonun kapagi acik mi?", ["ACIK", "KAPALI", "GORUNMUYOR"])]},
            {"ad": "H3_sistem", "sistem": SIS_KACIS_ZOR, "yorum": _p_taban,
             "sorular": [(PANO_SORU, ["ACIK", "KAPALI", "GORUNMUYOR"])]},
            {"ad": "H4_capa", "sistem": SIS_TABAN, "yorum": _p_capa,
             "sorular": [("Elektrik/kontrol panosunun kapagi acilmis olup ic kismi "
                          "(kablolar, sigortalar, koyu bosluk) disaridan goruluyor mu?",
                          ["IC_GORUNUYOR", "IC_GORUNMUYOR", "GORUNMUYOR"])]},
            {"ad": "H5_tersine", "sistem": SIS_TABAN, "yorum": _p_ters,
             "sorular": [("Elektrik/kontrol panosunun kapagi tamamen kapali ve yerinde mi?",
                          ["KAPAK_KAPALI", "KAPAK_ACIK", "GORUNMUYOR"])]},
            # --- EK ON-KAYIT (kosumdan ONCE ilan) — pano 2x2'sini de tamamla.
            # BEKLENTIM: yelekte F2 (sissiz + kacissiz) MCC'yi 0,578 -> 0,885 tasidi.
            # PANO'da AYNI SEYI BEKLEMIYORUM. Gerekce: D41 cozunurluk taramasi panoyu
            # SISTEM PROMPTU OLMADAN kosmustu ve yine 49/49 "GORUNMUYOR" aldi — yani
            # pano'da kacis sistem promptundan gelmiyor. Tahminim: F2_pano DEJENERE
            # (neredeyse tumu tek etiket) ve MCC < 0,20 kalacak.
            {"ad": "F1_sissiz_kacisli", "sistem": None, "yorum": _p_taban,
             "sorular": [(PANO_SORU, ["ACIK", "KAPALI", "GORUNMUYOR"])]},
            {"ad": "F2_sissiz_kacissiz", "sistem": None, "yorum": _p_taban,
             "sorular": [(PANO_SORU, ["ACIK", "KAPALI"])]},
        ],
    },
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
    dog = (tp + tn) / n if n else 0.0
    lo, hi = wilson(tp + tn, n)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "kararsiz": kararsiz, "hata": hata,
            "n_karar": n, "mcc": round(mcc(tp, fp, fn, tn), 4),
            "dogruluk": round(dog, 4), "ga95": [round(lo, 4), round(hi, 4)]}


def dejenere_kontrol(satirlar):
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


def mcnemar(a_dogru, b_dogru):
    """Esli iki kol; a/b: [True/False/None] ayni klip sirasinda. None -> klip atlanir."""
    b01 = b10 = 0
    for x, y in zip(a_dogru, b_dogru):
        if x is None or y is None:
            continue
        if x and not y:
            b10 += 1
        elif y and not x:
            b01 += 1
    n = b01 + b10
    if n == 0:
        return {"b_A_dogru_B_yanlis": 0, "b_B_dogru_A_yanlis": 0, "p": 1.0}
    # tam iki tarafli binom
    p = min(1.0, 2 * sum(math.comb(n, k) for k in range(0, min(b01, b10) + 1)) / 2 ** n)
    return {"b_A_dogru_B_yanlis": b10, "b_B_dogru_A_yanlis": b01, "p": round(p, 5)}


def max_stat_perm(kol_kararlari, etiketler, tur=PERM, tohum=TOHUM):
    """Coklu karsilastirma duzeltmesi (maks-istatistigi permutasyonu).

    kol_kararlari: {kol_ad: [True/False/None]} — AYNI klip sirasinda (esli).
    etiketler:     [True/False] gercek ihlal etiketleri, ayni sirada.
    HER permutasyonda TUM kollar AYNI permute etiketle puanlanir -> kollar arasi
    korelasyon korunur. Doner: bos max|MCC| dagiliminin kuantilleri + kol basina
    duzeltilmis p (gozlenen |MCC| >= bos MAKS orani).
    """
    rng = random.Random(tohum)
    adlar = list(kol_kararlari)
    gozlenen = {}
    for ad in adlar:
        gozlenen[ad] = abs(tablo([{"ihlal": e, "karar": k, "hata": False, "ham": ""}
                                  for e, k in zip(etiketler, kol_kararlari[ad])])["mcc"])
    bos_maks = []
    for _ in range(tur):
        etk = list(etiketler)
        rng.shuffle(etk)
        m = 0.0
        for ad in adlar:
            v = abs(tablo([{"ihlal": e, "karar": k, "hata": False, "ham": ""}
                           for e, k in zip(etk, kol_kararlari[ad])])["mcc"])
            m = max(m, v)
        bos_maks.append(m)
    bos_maks.sort()
    q = lambda p: round(bos_maks[min(len(bos_maks) - 1, int(p * len(bos_maks)))], 4)
    duz_p = {ad: round((1 + sum(1 for b in bos_maks if b >= gozlenen[ad])) / (tur + 1), 5)
             for ad in adlar}
    return {"tur": tur, "bos_maks_q50": q(0.50), "bos_maks_q90": q(0.90),
            "bos_maks_q95": q(0.95), "bos_maks_q99": q(0.99),
            "gozlenen_abs_mcc": {a: round(v, 4) for a, v in gozlenen.items()},
            "duzeltilmis_p": duz_p}


# --------------------------------------------------------------------------- kosum
def _sor(otu, sis, soru, secenek):
    """Tek soru. `sis is None` -> mesaj listesinde SISTEM ROLU HIC YOK.

    Neden ayri yol: VLMClient.video_oturumu(system=None) SYSTEM_PERSONA'ya duser,
    system="" ise BOS bir sistem mesaji gonderir — ikisi de "sistem promptu yok"
    DEGILDIR. D41 cozunurluk taramasi sistem rolunu HIC gondermemisti; F1/F2
    kollari o kurulumu birebir tekrarlamak zorunda. Ayni kodlanmis video dizesi
    (otu._mesajlar) tekrar kullanilir -> on-ek onbellegi yine isabet eder.
    """
    if sis is not None:
        return otu.sor(soru, guided_choice=secenek, temperature=T,
                       max_tokens=MAX_TOKENS, hatirla=False)
    if not otu.hazir:
        return None
    mesajlar = list(otu._mesajlar) + [{"role": "user", "content": soru}]
    try:
        return otu.istemci.chat(mesajlar, temperature=T, max_tokens=MAX_TOKENS,
                                guided_choice=secenek)
    except Exception as e:
        otu.hata = f"{type(e).__name__}: {e}"
        return None


def klipler(s):
    a = [(y, True) for y in sorted(glob.glob(os.path.join(SET, s["ihlal_dizin"], "*.mp4")))]
    b = [(y, False) for y in sorted(glob.glob(os.path.join(SET, s["normal_dizin"], "*.mp4")))]
    return a + b


def bolum(ad):
    return "te" if "_te" in ad else ("tr" if "_tr" in ad else "?")


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=KOK,
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return "?"


def kosum(a):
    from dilajan.llm_client import VLMClient
    from dilajan.video import servis_videosu
    from dilajan.config import settings

    if settings.mock_mode:
        print("HATA: DILAJAN_MOCK acik — olcum YAPILMAZ.")
        sys.exit(2)
    istemci = VLMClient(model=MODEL)
    print(f"  saglik {MODEL}: {'AYAKTA' if istemci.health_check() else 'YOK'}", flush=True)

    os.makedirs(CIKTI_DIZIN, exist_ok=True)

    # --- DEVAM: yarida kesilen kosumu SURDUR -------------------------------
    # Neden: uzak servis paylasimli; AYNI KLIBI IKI KEZ SORMAK yasak (olcum
    # disiplini + servis nezaketi). Zaten kayitli (sinif, klip, kol) uclusu
    # ATLANIR; dosyaya EKLENIR (append), ustune yazilmaz.
    varolan = set()
    if a.devam:
        jl_yol = a.devam if os.path.isabs(a.devam) else os.path.join(KOK, a.devam)
        with open(jl_yol, encoding="utf-8") as f:
            for ln in f:
                d = json.loads(ln)
                if d.get("tur") == "cevap":
                    varolan.add((d["sinif"], d["klip"], d["kol"]))
        print(f"DEVAM: {jl_yol}\n  zaten kayitli cevap sayisi={len(varolan)} — "
              f"bunlar TEKRAR SORULMAZ", flush=True)
        jl = open(jl_yol, "a", encoding="utf-8")
        jl.write(json.dumps({"tur": "devam_notu", "zaman": datetime.now().isoformat(timespec="seconds"),
                             "atlanan_cevap": len(varolan), "argv": sys.argv[1:]},
                            ensure_ascii=False) + "\n")
        jl.flush()
        return _kosum_dongu(a, istemci, servis_videosu, jl, jl_yol, varolan)

    damga = datetime.now().strftime("%Y%m%d_%H%M%S")
    etiket = ("smoke_" if a.smoke else "")
    jl_yol = os.path.join(CIKTI_DIZIN, f"evren_kacis_{etiket}{damga}.jsonl")
    jl = open(jl_yol, "w", encoding="utf-8")
    jl.write(json.dumps({"tur": "kunye", "zaman": datetime.now().isoformat(timespec="seconds"),
                         "git": git_commit(), "model": MODEL, "max_side": MAX_SIDE,
                         "crf": CRF, "temperature": T, "max_tokens": MAX_TOKENS,
                         "structured_outputs_choice": True, "deneme": DENEME,
                         "smoke": a.smoke, "set": SET, "argv": sys.argv[1:],
                         "sistem_taban": SIS_TABAN, "sistem_kacis_zor": SIS_KACIS_ZOR,
                         "on_kayit": __doc__}, ensure_ascii=False) + "\n")
    jl.flush()
    return _kosum_dongu(a, istemci, servis_videosu, jl, jl_yol, set())


def _kosum_dongu(a, istemci, servis_videosu, jl, jl_yol, varolan):
    siniflar = [s for s in SINIFLAR if a.sinif in ("hepsi", s["ad"])]
    for s in siniflar:
        yollar = klipler(s)
        if a.yalniz_bolum:
            yollar = [x for x in yollar
                      if bolum(os.path.basename(x[0])) == a.yalniz_bolum]
        if a.smoke:
            yollar = ([x for x in yollar if x[1]][:a.smoke]
                      + [x for x in yollar if not x[1]][:a.smoke])
        print(f"\n=== SINIF {s['ad']} · n={len(yollar)} · kollar="
              f"{[k['ad'] for k in s['kollar']]} ===", flush=True)
        t0 = time.time()
        atlandi = 0
        for i, (yol, ihlal) in enumerate(yollar, 1):
            ad = os.path.basename(yol)
            eksik = [k for k in s["kollar"] if (s["ad"], ad, k["ad"]) not in varolan]
            if not eksik:
                atlandi += 1
                continue                      # klip zaten tamam -> TEKRAR SORULMAZ
            try:
                baytlar = servis_videosu(yol, max_side=MAX_SIDE, crf=CRF)
            except Exception as e:
                for k in eksik:
                    jl.write(json.dumps({"tur": "cevap", "sinif": s["ad"], "kol": k["ad"],
                                         "klip": ad, "bolum": bolum(ad), "ihlal": ihlal,
                                         "hata": True, "ham": f"__KODLAMA__{type(e).__name__}",
                                         "adimlar": []}, ensure_ascii=False) + "\n")
                jl.flush()
                print(f"  [KODLAMA HATASI] {ad}: {e}", flush=True)
                continue

            # sistem promptu basina TEK oturum -> on-ek onbellegi isabet eder
            oturumlar = {}
            ozet = []
            for k in eksik:
                sis = k["sistem"]
                if sis not in oturumlar:
                    oturumlar[sis] = istemci.video_oturumu(
                        baytlar, system=("" if sis is None else sis), giris_metni=GIRIS)
                otu = oturumlar[sis]
                adimlar, ham, hatali = [], None, False
                if not otu.hazir:
                    hatali, ham = True, f"__OTURUM__ {otu.hata}"
                else:
                    for j, (soru, secenek) in enumerate(k["sorular"]):
                        c = None
                        for deneme in range(DENEME):
                            c = _sor(otu, sis, soru, secenek)
                            if c is not None:
                                break
                            if deneme < DENEME - 1:
                                time.sleep(BEKLE)
                        adimlar.append({"soru": soru, "secenek": secenek, "cevap": c})
                        if c is None:
                            hatali, ham = True, f"__HATA__ {otu.hata}"
                            break
                        ham = c
                        # kapi: ilk asama beklenen cevabi vermezse ikinci soru SORULMAZ
                        if j == 0 and k.get("kapi") and c.strip().upper() != k["kapi"]:
                            break
                karar = None if hatali else k["yorum"](ham)
                jl.write(json.dumps({"tur": "cevap", "sinif": s["ad"], "kol": k["ad"],
                                     "klip": ad, "bolum": bolum(ad), "ihlal": ihlal,
                                     "hata": hatali, "ham": ham, "karar": karar,
                                     "adimlar": adimlar,
                                     "boyut_kb": round(len(baytlar) / 1024, 1)},
                                    ensure_ascii=False) + "\n")
                ozet.append(f"{k['ad'].split('_')[0]}={str(ham)[:12]}")
            jl.flush()
            print(f"  {i:3d}/{len(yollar)} {bolum(ad)} {ad[:14]:14s} "
                  + " ".join(ozet), flush=True)
        print(f"  sinif suresi {round(time.time() - t0, 1)} s "
              f"(atlanan tamam klip={atlandi})", flush=True)
    jl.close()
    print(f"\nHAM CEVAPLAR: {jl_yol}")
    return jl_yol


# --------------------------------------------------------------------------- analiz
def analiz(jl_yol):
    kunye, satirlar = None, []
    with open(jl_yol, encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            if d.get("tur") == "kunye":
                kunye = d
            elif d.get("tur") == "cevap":
                satirlar.append(d)

    print("=" * 100)
    print(f"ANALIZ {jl_yol}")
    print(f"model={kunye['model']} max_side={kunye['max_side']} crf={kunye['crf']} "
          f"T={kunye['temperature']} git={kunye['git']}")
    rapor = {"kaynak": os.path.basename(jl_yol), "kunye": kunye, "siniflar": {}}

    for s in SINIFLAR:
        sn = s["ad"]
        alt = [r for r in satirlar if r["sinif"] == sn]
        if not alt:
            continue
        klip_sirasi = sorted({r["klip"] for r in alt})
        rapor["siniflar"][sn] = {"kural": s["kural"], "d41_taban_768": s["d41_taban_768"],
                                 "bolumler": {}}
        for bol in ("tr", "te"):
            klipler_b = [c for c in klip_sirasi
                         if any(r["klip"] == c and r["bolum"] == bol for r in alt)]
            if not klipler_b:
                continue
            idx = {(r["kol"], r["klip"]): r for r in alt if r["bolum"] == bol}
            # F1/F2 gibi kollar yalniz _tr'de kosuldu -> o bolumde KAYDI OLMAYAN kol
            # tabloya HIC girmez ("0 satirli kol" yanlislikla 'dejenere degil' gorunmesin)
            kollar_b = [k for k in s["kollar"]
                        if any((k["ad"], c) in idx for c in klipler_b)]
            kol_adlari = [k["ad"] for k in kollar_b]
            etiketler = [idx[(kol_adlari[0], c)]["ihlal"] for c in klipler_b]
            n_poz = sum(etiketler)
            print(f"\n{'='*100}\nSINIF {sn} · BOLUM _{bol} · n={len(klipler_b)} "
                  f"(ihlal={n_poz}, normal={len(klipler_b)-n_poz}) · {s['kural']}")
            print(f"{'kol':14s} {'TP':>3}{'FP':>4}{'FN':>4}{'TN':>4} {'krsz':>5}{'hata':>5} "
                  f"{'MCC':>7} {'dog':>6} {'Wilson95':>15} {'kararO':>7}  bayrak")
            b_rapor, kararlar, dogruluklar = {}, {}, {}
            for k in kollar_b:
                rs = []
                for c in klipler_b:
                    r = idx.get((k["ad"], c))
                    if r is None:
                        continue
                    rs.append({"ihlal": r["ihlal"], "hata": r["hata"],
                               "ham": r.get("ham") or "", "karar": r.get("karar")})
                ana, ikn = tablo(rs), tablo(rs, ikincil=True)
                dej = dejenere_kontrol(rs)
                gecerli = len([r for r in rs if not r["hata"]])
                ko = round(ana["n_karar"] / gecerli, 4) if gecerli else 0.0
                tamir = (not dej["dejenere"] and ana["mcc"] >= 0.40 and ko >= 0.70)
                b_rapor[k["ad"]] = {"ana": ana, "ikincil_dagitim": ikn,
                                    "dejenere_kapisi": dej, "karar_orani": ko,
                                    "on_tamir_olcutu_abc": tamir}
                kararlar[k["ad"]] = [(idx.get((k["ad"], c)) or {}).get("karar")
                                     for c in klipler_b]
                dogruluklar[k["ad"]] = [
                    None if (idx.get((k["ad"], c)) or {}).get("karar") is None
                    else (idx[(k["ad"], c)]["karar"] == idx[(k["ad"], c)]["ihlal"])
                    for c in klipler_b]
                bayrak = ("DEJENERE " if dej["dejenere"] else "") + ("abc-GECTI" if tamir else "")
                print(f"{k['ad']:14s} {ana['tp']:3d}{ana['fp']:4d}{ana['fn']:4d}{ana['tn']:4d} "
                      f"{ana['kararsiz']:5d}{ana['hata']:5d} {ana['mcc']:+7.3f} "
                      f"{ana['dogruluk']:6.3f} [{ana['ga95'][0]:.3f}-{ana['ga95'][1]:.3f}] "
                      f"{ko:7.2f}  {bayrak}")
            print("  ham cevap dagilimlari:")
            for ka in kol_adlari:
                print(f"    {ka:14s} {b_rapor[ka]['dejenere_kapisi']['ham_dagilim']}")
            print("  IKINCIL (sahada dagitim: kararsiz -> alarm yok):")
            for ka in kol_adlari:
                e = b_rapor[ka]["ikincil_dagitim"]
                print(f"    {ka:14s} TP={e['tp']:2d} FP={e['fp']:2d} FN={e['fn']:2d} "
                      f"TN={e['tn']:2d} MCC={e['mcc']:+.3f} dog={e['dogruluk']:.3f}")

            # esli McNemar: A0'a karsi
            taban = kol_adlari[0]
            mc = {}
            for ka in kol_adlari[1:]:
                mc[ka] = {"dogruluk": mcnemar(dogruluklar[taban], dogruluklar[ka]),
                          "karar_verme": mcnemar(
                              [x is not None for x in kararlar[taban]],
                              [x is not None for x in kararlar[ka]])}
            print(f"  McNemar (A0 vs kol) — dogruluk / karar-verme:")
            for ka, v in mc.items():
                print(f"    {ka:14s} dog: A0+{v['dogruluk']['b_A_dogru_B_yanlis']} "
                      f"kol+{v['dogruluk']['b_B_dogru_A_yanlis']} p={v['dogruluk']['p']:.4f}"
                      f"   | karar: A0+{v['karar_verme']['b_A_dogru_B_yanlis']} "
                      f"kol+{v['karar_verme']['b_B_dogru_A_yanlis']} "
                      f"p={v['karar_verme']['p']:.4f}")

            # --- POST-HOC BETIMLEYICI (secim olcutu DEGIL, sonradan eklendi) -----
            # H1'in asil sinavi: A0'in KACTIGI kliplerde zorunlu secim DOGRU mu,
            # yoksa D33'teki gibi tek etikete mi cokuyor?
            kac_idx = [j for j, x in enumerate(kararlar[taban]) if x is None]
            kar_idx = [j for j, x in enumerate(kararlar[taban]) if x is not None]
            kosullu = {}
            for ka in kol_adlari[1:]:
                bl = {}
                for etkt, jj in (("A0_kactiginda", kac_idx), ("A0_karar_verdiginde", kar_idx)):
                    d = [kararlar[ka][j] for j in jj]
                    e = [etiketler[j] for j in jj]
                    ck = [(x, y) for x, y in zip(d, e) if x is not None]
                    dogru = sum(1 for x, y in ck if x == y)
                    poz = sum(1 for x, _ in ck if x)
                    lo, hi = wilson(dogru, len(ck))
                    bl[etkt] = {"n_klip": len(jj), "n_karar": len(ck),
                                "dogru": dogru,
                                "dogruluk": round(dogru / len(ck), 4) if ck else None,
                                "ga95": [round(lo, 4), round(hi, 4)],
                                "ihlal_dedi": poz, "ihlal_degil_dedi": len(ck) - poz,
                                "gercek_ihlal": sum(1 for _, y in ck if y)}
                kosullu[ka] = bl
            print(f"  POST-HOC: A0 kacinca ({len(kac_idx)} klip) kollar ne yapiyor? "
                  f"[secim olcutu DEGIL]")
            for ka, bl in kosullu.items():
                v = bl["A0_kactiginda"]
                if not v["n_karar"]:
                    print(f"    {ka:14s} bu kliplerde de karar YOK")
                    continue
                print(f"    {ka:14s} karar={v['n_karar']}/{v['n_klip']} "
                      f"dogru={v['dogru']} dog={v['dogruluk']:.3f} "
                      f"[{v['ga95'][0]:.3f}-{v['ga95'][1]:.3f}] "
                      f"dedigi: ihlal={v['ihlal_dedi']} degil={v['ihlal_degil_dedi']} "
                      f"(gercek ihlal={v['gercek_ihlal']})")
            b_rapor["__post_hoc_kacis_kosullu"] = kosullu

            perm = max_stat_perm(kararlar, etiketler)
            print(f"  COKLU KARSILASTIRMA (maks-istatistigi permutasyonu, {perm['tur']} tur, "
                  f"{len(kol_adlari)} kol):")
            print(f"    bos max|MCC| kuantilleri: q50={perm['bos_maks_q50']:.3f} "
                  f"q90={perm['bos_maks_q90']:.3f} q95={perm['bos_maks_q95']:.3f} "
                  f"q99={perm['bos_maks_q99']:.3f}")
            for ka in kol_adlari:
                g = perm["gozlenen_abs_mcc"][ka]
                print(f"    {ka:14s} |MCC|={g:.3f} duzeltilmis p={perm['duzeltilmis_p'][ka]:.4f}"
                      + ("  <- q95 UZERINDE" if g > perm["bos_maks_q95"] else ""))
            b_rapor["__mcnemar_A0"] = mc
            b_rapor["__coklu_karsilastirma"] = perm
            b_rapor["__n"] = {"klip": len(klipler_b), "ihlal": n_poz,
                              "normal": len(klipler_b) - n_poz}
            rapor["siniflar"][sn]["bolumler"][bol] = b_rapor

    yol = jl_yol.replace(".jsonl", "_ozet.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(rapor, f, ensure_ascii=False, indent=2)
    print(f"\nOZET: {yol}")
    return rapor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kuru", action="store_true")
    ap.add_argument("--smoke", type=int, default=0)
    ap.add_argument("--sinif", default="hepsi", choices=["hepsi", "yelek", "pano"])
    ap.add_argument("--analiz", default="")
    ap.add_argument("--yalniz_bolum", default="", choices=["", "tr", "te"],
                    help="yalniz secim (tr) veya tutma (te) kliplerini kos")
    ap.add_argument("--devam", default="",
                    help="yarida kesilen JSONL'i SURDUR; kayitli klipler tekrar SORULMAZ")
    a = ap.parse_args()

    if a.analiz:
        analiz(a.analiz)
        return

    print(f"set={SET}\nmodel={MODEL} max_side={MAX_SIDE} crf={CRF} T={T} "
          f"max_tokens={MAX_TOKENS}\ngit={git_commit()}\n")
    for s in SINIFLAR:
        if a.sinif not in ("hepsi", s["ad"]):
            continue
        y = klipler(s)
        tr = [x for x in y if bolum(os.path.basename(x[0])) == "tr"]
        te = [x for x in y if bolum(os.path.basename(x[0])) == "te"]
        print(f"SINIF {s['ad']:6s} n={len(y)} (_tr={len(tr)} SECIM, _te={len(te)} TUTMA) "
              f"kural={s['kural']}")
        for k in s["kollar"]:
            print(f"   {k['ad']:14s} sistem={'KACIS_ZOR' if k['sistem'] is SIS_KACIS_ZOR else 'TABAN'}"
                  f" kapi={k.get('kapi')}")
            for soru, sec in k["sorular"]:
                print(f"      soru: {soru}\n      secenek: {sec}")
    if a.kuru:
        print("\n--kuru: cagri yapilmadi.")
        return
    jl = kosum(a)
    analiz(jl)


if __name__ == "__main__":
    main()
