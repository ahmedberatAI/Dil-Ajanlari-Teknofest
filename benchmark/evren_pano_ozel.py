#!/usr/bin/env python
"""D42 — PANO OZEL SALDIRISI: cerceveleme / soru-bicimi / protokol izgarasi.

    python benchmark/evren_pano_ozel.py --kuru            # cagri yok, plani yazdir
    python benchmark/evren_pano_ozel.py --smoke 2         # her siniftan 2 klip
    python benchmark/evren_pano_ozel.py --kume tr         # SECIM kosumu (34 klip)
    python benchmark/evren_pano_ozel.py --kume te --hucre H2,H4   # TUTMA kosumu

=== ON-KAYIT (SONUCLARA BAKILMADAN, HERHANGI BIR MODEL CAGRISINDAN ONCE ILAN EDILDI) ===

NEDEN BU KOSUM VAR
  Pano sinifini UC model de cozemedi: yerel 8B 49/49 "GORUNMUYOR", uzak llm-large
  49/49 "GORUNMUYOR" (BIREBIR ayni), vlm 46/49 "KAPALI" (TP=0), llm-fast MCC -0,086.
  Cozunurluk taramasi (768/1280/1920) TEK KLIBI bile degistirmedi (p=1,0) -> darbogaz
  COZUNURLUK DEGIL. Geriye kalan hipotez: CERCEVELEME (pano tam karenin ~%2'si),
  SORU BICIMI (mutlak ikili yargi) ve PROTOKOL (tek goruntu vs karsilastirma).

VERI VE SECIM/RAPOR AYRIMI (ZORUNLU)
  SECIM kumesi = yalniz _tr : Opened 21 ACIK + Closed 13 KAPALI = 34 klip
  TUTMA kumesi = yalniz _te : Opened  3 ACIK + Closed 12 KAPALI = 15 klip
  TUTMA'da yalniz 3 POZITIF var -> ONCEDEN ILAN: te KARAR VERDIRMEZ, yalnizca
  "secim tamamen cokmus mu" kontroludur. Manset sayi tr'den VERILMEZ; tr sayilari
  SECIM sayisidir ve coklu-karsilastirma duzeltmesiyle birlikte okunur.
  te kliplerine SECIM asamasinda BAKILMAZ.

CERCEVELEME (ROI kaynagi ve DURUSTLUK NOTU)
  ROI = 0.08,0.55,0.21,0.73 — bu kutu BIZIM deterministik dedektorumuzden gelir ve
  AYNI VERI uzerinde kalibre edilmistir. Yani P1/P3/P4/P2 kollari "VLM'e cerceveleme
  problemi COZULMUS halde verilirse ne yapar?" sorusunu olcer; bagimsiz bir uctan-uca
  boru hatti DEGILDIR. Bu KASITLIDIR: VLM bu yardimla bile basaramazsa sonuc DAHA
  GUCLUDUR. Basarirsa da tek basina dagitilabilir bir cozum degildir (ROI'yi bulmak
  icin zaten dedektor gerekir).
  Kirpma kutulari (1920x1080): dar(1.0x) = 153,594,248x194 · baglam(2.0x) = 28,496,498x388
  Kirpilan video max_side=1280'e OLCEKLENIR (buyutme) — pano piksel/token butcesinin
  tamamini alir. crf=26, ses yok.

IZGARA — 7 HUCRE (hepsi SECIM kumesinde, n=34)
  H1 P1a  ROI-dar video      · ikili soru        · llm-large
  H2 P1b  ROI-baglam video   · ikili soru        · llm-large   <- BIRINCIL hipotez
  H3 P1c  ROI-baglam video   · ikili soru        · vlm
  H4 P3   ROI-baglam video   · mekanizma sorusu  · llm-large
  H5 P4   ROI-baglam video   · sayisal 0-10      · llm-large  (esik 1..10 taranir)
  H6 P2   2 GORUNTU (ACIK referans + sorgu karesi, ikisi de ROI-baglam) · llm-large
  H7 P5   ayni 2 GORUNTU protokolu                                     · llm-fast

  IZOLASYON MANTIGI (hangi karsilastirma neyi ayirir):
    H1 vs H2         : kirpma sikiligi (baglam yardim eder mi?)      — cerceveleme
    H2 vs H4 vs H5   : SORU BICIMI, cerceveleme SABIT               — soru
    H2 vs H3         : MODEL, cerceveleme+soru SABIT                — model
    H2 vs H6         : PROTOKOL (mutlak yargi vs karsilastirma)     — protokol
    H6 vs H7         : model, protokol SABIT
    TARIHI KONTROL   : tam-kare + ikili + llm-large = 49/49 GORUNMUYOR (MCC 0,000)

MODEL SECIMI VE GEREKCESI
  llm-large : izgaranin omurgasi. En guclu alias; tam karede "GORUNMUYOR" demesinin
              nedeni ALGI mi CERCEVELEME mi — bunu ancak ayni model uzerinde
              cerceveleme degistirilerek ayirt edebiliriz. Tarihi kontrol de bu model.
  vlm       : pano sorusunda ACIK/KAPALI'ya KARAR VEREN tek koldu (46/49 KAPALI);
              yani "goremiyorum" demiyor, YANLIS goruyor. Video-yerel alias.
              Cerceveleme duzeltilince kararlarinin duzelip duzelmedigi ayri bir soru.
  llm-fast  : yalniz 2-goruntu protokolunde (H7). Gerekce: pano sorusunda diger iki
              modelden FARKLI (dejenere degil ama sansin altinda) davrandi; farkli
              hata modu, karsilastirma protokolunde farkli tepki verebilir.
  vlm 2-goruntu kolunda YOK: servis vlm icin istek basina 0 GORUNTU kabul ediyor
  (olculdu) — teknik olarak imkansiz, atlanmasinin sebebi budur.

SABIT KURULUM
  T=0 · max_tokens=24 · structured_outputs.choice (guided) ACIK · ayni SISTEM promptu
  istekler SIRAYLA · hata basina en fazla 2 yeniden deneme · her klip icin ayni
  kodlanmis baytlar ayni oturumda tekrar kullanilir (on-ek onbellegi)
  H2/H4/H5 TEK video oturumunu paylasir; sorular hatirla=False ile BAGIMSIZ sorulur
  (birbirinin cevabini gormezler) — bu yalnizca yukleme tasarrufudur, olcum degismez.
  H6/H7 referans goruntusu: 2_tr101 orta karesi (ROI-baglam). O klip H6/H7'de
  PUANLANMAZ (n=33) — kendi referansiyla karsilastirilamaz.

PUANLAMA (olcum disiplini)
  1. KACIS cevaplari (GORUNMUYOR / HICBIRI) KARARSIZ sayilir; sessizce negatife
     CEVRILMEZ. Ana tablo yalnizca KARAR VERILEN kliplerden. Kararsiz ve hata AYRI.
  2. TP/FP/FN/TN her hucre icin HER ZAMAN yazilir. Wilson %95 GA verilir.
  3. DEJENERELIK KAPISI: D1 en sik HAM cevap >= %85 tum klipler VEYA D2 karar
     verilenlerde bir taraf >= %85 -> DEJENERE. MCC ne olursa olsun BASARI SAYILMAZ.
  4. COKLU KARSILASTIRMA: 7 hucre + H5'in 10 esigi deneniyor. Maks-istatistigi
     permutasyonu (n=2000, etiketler karistirilir, H5 esigi HER permutasyonda
     YENIDEN taranir) ile bos dagilim kurulur; %95 kuantili ve duzeltilmis p yazilir.
  5. n=34'te 0,05 MCC farki GURULTUDUR -> berabere.

BASARI OLCUTU (kosumdan ONCE ilan)
  Bir hucre KULLANILABILIR sayilir ancak ve ancak
    (a) DEJENERE degil, (b) MCC >= +0,40, (c) karar orani >= 0,70,
    (d) dogruluk Wilson alt sinir > 0,50, (e) duzeltilmis p < 0,05.
  Hicbiri gecmezse KARAR: pano sinifi VLM ile cozulmez, deterministik dedektor KALIR.

TAHMIN (KOSUMDAN ONCE YAZILDI — sonra tutup tutmadigi bildirilecek)
  Ham onsel (kirpmalari GORMEDEN): P1'in basarma olasiligi ~%30.
  DUZELTME: kosumdan once 4 adet _tr kirpmasini (2 ACIK, 2 KAPALI) GOZLE inceledim
  — _te'ye BAKILMADI. Baglam kirpmasinda ACIK pano net bir KARANLIK OYUK + gorunur
  ic kablolama, KAPALI pano duz bej kapak. Insan icin KOLAY bir gorev. Bu yuzden
  tahminimi YUKARI cekiyorum:
    H2 (birincil) : MCC +0,60 · dejenere DEGIL · KULLANILABILIR olma olasiligi ~%60
    H1            : H2 ile berabere (+-0,05); baglamin yardimi kucuk
    H3 (vlm)      : MCC +0,25 · "KAPALI" tarafina egilim surer
    H4 (mekanizma): MCC +0,45 · ikili soruyla berabere veya biraz altinda
    H5 (sayisal)  : tr'de en iyi esikle MCC +0,55 ama esik taramasi SISIRIR;
                    duzeltmeden sonra H2'yi GECMESINI beklemiyorum
    H6/H7 (2 gor.): MCC +0,35 / +0,20 · karsilastirma protokolu, video oturumundan
                    DAHA IYI OLMAYACAK (tek kare < video)
  EN IYI HUCRE duzeltmeden sonra ANLAMLI cikar mi? EVET (~%60).
  GENEL KARAR TAHMINI: cerceveleme duzeltilirse VLM bu sinifi COZER; ama bu,
  deterministik dedektoru gereksiz KILMAZ (ROI'yi bulan sey zaten dedektor).
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

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
sys.path.insert(0, os.path.join(KOK, "benchmark"))

from evren_model_kars import mcc, wilson, tablo, dejenere_kontrol  # noqa: E402

SET = os.environ.get("DILAJAN_PROB_SET") or os.path.join(KOK, "data/eval_defense")
CIKTI_DIZIN = os.path.join(KOK, "benchmark/results")

ACIK_DIZIN = "Anomali/Opened_Panel_Cover"
KAPALI_DIZIN = "Normal/Closed_Panel_Cover"

ROI = (0.08, 0.55, 0.21, 0.73)
MAX_SIDE, CRF, T, MAX_TOKENS = 1280, 26, 0.0, 24
DENEME, BEKLE = 3, 5.0
REFERANS_KLIP = "2_tr101.mp4"          # ACIK referans (H6/H7); o klip puanlanmaz
PERM = 2000

SISTEM = ("Sen bir endustriyel is guvenligi kamerasi analiz sistemisin. Sana bir "
          "guvenlik kamerasindan alinmis kisa bir video verilir. YALNIZCA GORDUGUNE "
          "dayan; varsayim yapma. Ayirt edemiyorsan kacis secenegini kullan.")
SISTEM_GORUNTU = SISTEM.replace("kisa bir video verilir", "bir veya iki goruntu verilir")
GIRIS = ("Bu, bir elektrik/kontrol panosuna YAKINDAN odaklanmis guvenlik kamerasi "
         "goruntusudur. Panonun metal kapagi kadrajin merkezindedir.")
# "tam" kirpmada pano kadrajin merkezinde DEGILDIR — ayni giris metnini kullanmak
# modele YANLIS bilgi vermek olur; bu yuzden notr bir giris kullanilir.
GIRIS_TAM = "Bu bir fabrika ici guvenlik kamerasi videosudur."


def _giris(kirpma: str) -> str:
    return GIRIS_TAM if kirpma == "tam" else GIRIS


# ------------------------------------------------------------------ yorumlayicilar
def _ikili(c):
    c = (c or "").strip().upper()
    return True if c == "ACIK" else False if c == "KAPALI" else None


def _mekanizma(c):
    c = (c or "").strip().upper()
    return True if c == "OYUK_VAR" else False if c == "OYUK_YOK" else None


def _karsilastirma(c):
    """Referans ACIK. IKINCI/IKISI_DE -> sorgu ACIK. BIRINCI -> sorgu KAPALI."""
    c = (c or "").strip().upper()
    if c in ("IKINCI", "IKISI_DE"):
        return True
    if c == "BIRINCI":
        return False
    return None                      # HICBIRI -> model referansi bile goremedi


def _sayisal_yorum(esik):
    def f(c):
        c = (c or "").strip().upper()
        if c in ("GORUNMUYOR", ""):
            return None
        try:
            return int(c) >= esik
        except ValueError:
            return None
    return f


SORU_IKILI = ("Kadrajin merkezindeki elektrik/kontrol panosunun metal kapagi ACIK mi "
              "KAPALI mi?")
SORU_MEKANIZMA = ("Kadrajin merkezindeki panonun govdesinde, icini gosteren KOYU/KARANLIK "
                  "bir OYUK (bosluk) gorunuyor mu?")
SORU_SAYISAL = ("Kadrajin merkezindeki panonun on yuzeyi 0 ile 10 arasinda ne kadar "
                "karanlik? 0 = tamamen acik renkli/duz kapak, 10 = tamamen karanlik "
                "bir bosluk. Yalnizca sayiyi yaz.")
SORU_KARSILASTIRMA = ("Birinci goruntude panonun kapagi ACIKTIR (referans). Ikinci "
                      "goruntudeki panonun kapagi da ACIK mi? Hangi goruntulerde pano "
                      "kapagi aciktir?")

# POST-HOC H8: tam karede "kadrajin merkezi" diye bir capa YOK — panonun nerede
# oldugu SOYLENMELI, yoksa H5 ile kiyaslanan sey soru degil CAPA olur.
SORU_SAYISAL_TAM = ("Goruntunun SOL tarafindaki mavi-bej presin govdesine monteli "
                    "elektrik/kontrol panosunun on yuzeyi 0 ile 10 arasinda ne kadar "
                    "karanlik? 0 = tamamen acik renkli/duz kapak, 10 = tamamen "
                    "karanlik bir bosluk. Yalnizca sayiyi yaz.")

SEC_IKILI = ["ACIK", "KAPALI", "GORUNMUYOR"]
SEC_MEKANIZMA = ["OYUK_VAR", "OYUK_YOK", "GORUNMUYOR"]
SEC_SAYISAL = [str(i) for i in range(11)] + ["GORUNMUYOR"]
SEC_KARSILASTIRMA = ["BIRINCI", "IKINCI", "IKISI_DE", "HICBIRI"]

# hucre tanimi: (kod, yol_adi, kirpma, model, soru, secenek, yorum)
HUCRELER = [
    {"kod": "H1", "yol": "P1a", "kirpma": "dar", "model": "llm-large",
     "protokol": "video", "soru": SORU_IKILI, "secenek": SEC_IKILI, "yorum": _ikili},
    {"kod": "H2", "yol": "P1b", "kirpma": "baglam", "model": "llm-large",
     "protokol": "video", "soru": SORU_IKILI, "secenek": SEC_IKILI, "yorum": _ikili},
    {"kod": "H3", "yol": "P1c", "kirpma": "baglam", "model": "vlm",
     "protokol": "video", "soru": SORU_IKILI, "secenek": SEC_IKILI, "yorum": _ikili},
    {"kod": "H4", "yol": "P3", "kirpma": "baglam", "model": "llm-large",
     "protokol": "video", "soru": SORU_MEKANIZMA, "secenek": SEC_MEKANIZMA,
     "yorum": _mekanizma},
    {"kod": "H5", "yol": "P4", "kirpma": "baglam", "model": "llm-large",
     "protokol": "video", "soru": SORU_SAYISAL, "secenek": SEC_SAYISAL,
     "yorum": None},                 # esik taranir
    {"kod": "H6", "yol": "P2", "kirpma": "baglam", "model": "llm-large",
     "protokol": "2goruntu", "soru": SORU_KARSILASTIRMA,
     "secenek": SEC_KARSILASTIRMA, "yorum": _karsilastirma},
    {"kod": "H7", "yol": "P5", "kirpma": "baglam", "model": "llm-fast",
     "protokol": "2goruntu", "soru": SORU_KARSILASTIRMA,
     "secenek": SEC_KARSILASTIRMA, "yorum": _karsilastirma},

    # --- POST-HOC (SONUCLAR GORULDUKTEN SONRA EKLENDI — ON-KAYIT AILESINE DAHIL
    # DEGIL, coklu-karsilastirma duzeltmesi AYRI yapilir; --hucre ile acikca
    # istenmedikce KOSULMAZ) --------------------------------------------------
    # NEDEN: H5 iki seyi AYNI ANDA degistirdi (ROI kirpma + sayisal soru). Tarihi
    # kontrol ise tam-kare + IKILI soru idi. Yani "kazanan hangisi?" sorusu
    # ON-KAYITLI izgarada CEVAPSIZ kaldi. Bu iki hucre tam o bosluğu kapatir:
    #   H8 = tam kare + SAYISAL  -> ROI kirpma GEREKLI mi? (dedektor gerekli mi?)
    #   H9 = ROI + IKILI, KACIS SECENEGI YOK -> llm-large'in "GORUNMUYOR"u
    #        ALGI hatasi mi, KACIS TERCIHI mi?
    {"kod": "H8", "yol": "PH1", "kirpma": "tam", "model": "llm-large",
     "protokol": "video", "soru": SORU_SAYISAL_TAM, "secenek": SEC_SAYISAL,
     "yorum": None, "posthoc": True},
    {"kod": "H9", "yol": "PH2", "kirpma": "baglam", "model": "llm-large",
     "protokol": "video", "soru": SORU_IKILI, "secenek": ["ACIK", "KAPALI"],
     "yorum": _ikili, "posthoc": True},
]
ON_KAYITLI = ["H1", "H2", "H3", "H4", "H5", "H6", "H7"]


# ---------------------------------------------------------------------- kirpma
def _kutu(pad, W=1920, H=1080):
    x1, y1, x2, y2 = ROI
    cx, cy = (x1 + x2) / 2 * W, (y1 + y2) / 2 * H
    w, h = (x2 - x1) * W * pad, (y2 - y1) * H * pad
    X = max(0, int(cx - w / 2))
    Y = max(0, int(cy - h / 2))
    Wd = min(W - X, int(w))
    Hd = min(H - Y, int(h))
    return X, Y, Wd - Wd % 2, Hd - Hd % 2


PAD = {"dar": 1.0, "baglam": 2.0, "tam": None}


def _vf(kirpma, w=None, h=None):
    if PAD[kirpma] is None:              # "tam" = KIRPMA YOK, yalniz olcekleme
        return f"scale={MAX_SIDE}:-2"
    X, Y, Wd, Hd = _kutu(PAD[kirpma], w or 1920, h or 1080)
    return f"crop={Wd}:{Hd}:{X}:{Y},scale={MAX_SIDE}:-2"


def roi_videosu(yol: str, kirpma: str) -> bytes:
    """Klibi ROI'ye kirpip max_side=1280'e olcekler, mp4 baytlari doner."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        gecici = f.name
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", yol, "-vf", _vf(kirpma),
             "-c:v", "libx264", "-crf", str(CRF), "-preset", "fast", "-an", gecici],
            capture_output=True, timeout=300)
        if r.returncode != 0 or os.path.getsize(gecici) == 0:
            raise RuntimeError(f"ffmpeg: {r.stderr.decode()[:200]}")
        return open(gecici, "rb").read()
    finally:
        try:
            os.unlink(gecici)
        except OSError:
            pass


def _sure(yol: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "format=duration", "-of", "csv=p=0", yol],
                       capture_output=True, text=True, timeout=60)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 6.0


def roi_karesi(yol: str, kirpma: str) -> bytes:
    """Klibin ORTA karesini ROI'ye kirpip JPEG baytlari doner."""
    import tempfile
    t = max(0.0, _sure(yol) / 2.0)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        gecici = f.name
    try:
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}",
                            "-i", yol, "-frames:v", "1", "-vf", _vf(kirpma),
                            "-q:v", "3", gecici], capture_output=True, timeout=120)
        if r.returncode != 0 or os.path.getsize(gecici) == 0:
            raise RuntimeError(f"ffmpeg: {r.stderr.decode()[:200]}")
        return open(gecici, "rb").read()
    finally:
        try:
            os.unlink(gecici)
        except OSError:
            pass


# ----------------------------------------------------------------------- klipler
def klipler(kume: str):
    out = []
    for alt, ihlal in [(ACIK_DIZIN, True), (KAPALI_DIZIN, False)]:
        for y in sorted(glob.glob(os.path.join(SET, alt, "*.mp4"))):
            ad = os.path.basename(y)
            if kume != "hepsi":
                etiket = "_te" if "_te" in ad else "_tr"
                if etiket != f"_{kume}":
                    continue
            out.append((y, ihlal))
    return out


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=KOK,
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return "?"


# ------------------------------------------------------------------- istatistik
def esik_tara(satirlar_ham):
    """H5: esik 1..10 taranir, en yuksek MCC'li esik secilir. Doner (esik, mcc, satirlar)."""
    en = (None, -2.0, None)
    for e in range(1, 11):
        s = [{"klip": r["klip"], "ihlal": r["ihlal"], "hata": r["hata"], "ham": r["ham"],
              "karar": None if r["hata"] else _sayisal_yorum(e)(r["ham"])}
             for r in satirlar_ham]
        t = tablo(s)
        if t["mcc"] > en[1]:
            en = (e, t["mcc"], s)
    return en


SAYISAL_KODLAR = {h["kod"] for h in HUCRELER if h["yorum"] is None}


def permutasyon(hucre_satirlari, n_perm=PERM, tohum=20260824):
    """MAKS-ISTATISTIGI permutasyonu.

    hucre_satirlari: {kod: [{"klip": ad, "ihlal": bool, "hata": bool,
                             "karar": T/F/None, "ham": str}]}
    Etiketler KLIP duzeyinde karistirilir (tum hucrelerde ayni permutasyon ->
    hucreler arasi bagimlilik korunur). H5 her permutasyonda YENIDEN taranir.
    """
    rng = random.Random(tohum)
    klip_etiket = {}
    for kod, sat in hucre_satirlari.items():
        for r in sat:
            klip_etiket.setdefault(r["klip"], r["ihlal"])
    adlar = sorted(klip_etiket)
    etiketler = [klip_etiket[a] for a in adlar]

    def hucre_mcc(kod, sat, harita):
        if kod in SAYISAL_KODLAR:
            en = -2.0
            for e in range(1, 11):
                s = [{"ihlal": harita[r["klip"]], "hata": r["hata"], "ham": r["ham"],
                      "karar": None if r["hata"] else _sayisal_yorum(e)(r["ham"])}
                     for r in sat]
                en = max(en, tablo(s)["mcc"])
            return en
        s = [{"ihlal": harita[r["klip"]], "hata": r["hata"], "ham": r["ham"],
              "karar": r["karar"]} for r in sat]
        return tablo(s)["mcc"]

    gercek_harita = dict(zip(adlar, etiketler))
    gozlenen = {k: hucre_mcc(k, s, gercek_harita) for k, s in hucre_satirlari.items()}
    gozlenen_maks = max(gozlenen.values()) if gozlenen else 0.0

    bos = []
    for _ in range(n_perm):
        karisik = etiketler[:]
        rng.shuffle(karisik)
        harita = dict(zip(adlar, karisik))
        bos.append(max(hucre_mcc(k, s, harita) for k, s in hucre_satirlari.items()))
    bos.sort()
    q95 = bos[int(0.95 * len(bos))]
    p = (1 + sum(1 for b in bos if b >= gozlenen_maks)) / (len(bos) + 1)
    # her hucre icin AYNI bos dagilima gore duzeltilmis p
    p_hucre = {k: (1 + sum(1 for b in bos if b >= v)) / (len(bos) + 1)
               for k, v in gozlenen.items()}
    return {"n_perm": n_perm, "bos_q95": round(q95, 4),
            "gozlenen_maks": round(gozlenen_maks, 4), "p_duzeltilmis": round(p, 5),
            "p_hucre": {k: round(v, 5) for k, v in p_hucre.items()},
            "bos_ortalama": round(sum(bos) / len(bos), 4)}


def kullanilabilir(dej, ana, karar_orani, p_duz):
    return (not dej["dejenere"] and ana["mcc"] >= 0.40 and karar_orani >= 0.70
            and ana["ga95"][0] > 0.50 and p_duz < 0.05)


# ----------------------------------------------------------------------- kosum
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kuru", action="store_true")
    ap.add_argument("--smoke", type=int, default=0)
    ap.add_argument("--kume", default="tr", choices=["tr", "te", "hepsi"])
    ap.add_argument("--hucre", default="", help="virgulle ayrilmis (or. 'H2,H4'); bos=hepsi")
    ap.add_argument("--etiket", default="")
    ap.add_argument("--h5-esik", type=int, default=0,
                    help="H5 esigini SABITLE (TUTMA kosumu icin ZORUNLU: tr'de secilen "
                         "deger verilir; 0 = esik tr'de taranir). te'de tarama YAPILMAZ.")
    a = ap.parse_args()
    if a.kume == "te" and not a.h5_esik and (not a.hucre or "H5" in a.hucre.upper()):
        print("HATA: TUTMA kosumunda --h5-esik ZORUNLU (esik SECIM kumesinde secilir).")
        return 2

    # POST-HOC hucreler VARSAYILAN OLARAK KOSULMAZ (on-kayit ailesi korunur).
    hucreler = [h for h in HUCRELER if not h.get("posthoc")]
    if a.hucre:
        sec = [x.strip().upper() for x in a.hucre.split(",") if x.strip()]
        bilinmeyen = [x for x in sec if x not in {h["kod"] for h in HUCRELER}]
        if bilinmeyen:
            print(f"HATA: bilinmeyen hucre {bilinmeyen}")
            return 2
        hucreler = [h for h in HUCRELER if h["kod"] in sec]

    yollar = klipler(a.kume)
    if a.smoke:
        yollar = ([x for x in yollar if x[1]][:a.smoke]
                  + [x for x in yollar if not x[1]][:a.smoke])
    n_poz = sum(1 for _, i in yollar if i)
    print(f"set={SET}\nkume={a.kume}  n={len(yollar)}  (ACIK={n_poz} KAPALI={len(yollar)-n_poz})")
    print(f"ROI={ROI}  dar={_kutu(1.0)}  baglam={_kutu(2.0)}  max_side={MAX_SIDE} crf={CRF}")
    print(f"T={T} max_tokens={MAX_TOKENS} guided=ACIK deneme={DENEME} git={git_commit()}\n")
    for h in hucreler:
        print(f"  {h['kod']} ({h['yol']:4s}) kirpma={h['kirpma']:7s} model={h['model']:10s} "
              f"protokol={h['protokol']:9s}\n       soru: {h['soru'][:88]}\n"
              f"       secenek: {h['secenek']}")
    if a.kuru:
        print("\n--kuru: cagri yapilmadi.")
        return 0

    from dilajan.llm_client import VLMClient           # noqa: E402
    from dilajan.config import settings                # noqa: E402
    if settings.mock_mode:
        print("HATA: DILAJAN_MOCK acik — olcum YAPILMAZ.")
        return 2

    modeller = sorted({h["model"] for h in hucreler})
    istemciler = {m: VLMClient(model=m) for m in modeller}
    for m, c in istemciler.items():
        print(f"  saglik {m}: {'AYAKTA' if c.health_check() else 'YOK'}", flush=True)

    zaman = datetime.now().strftime("%Y%m%d_%H%M%S")
    ek = f"_{a.etiket}" if a.etiket else ""
    jsonl_yol = os.path.join(CIKTI_DIZIN, f"evren_pano_ozel_{a.kume}{ek}_{zaman}.jsonl")
    os.makedirs(CIKTI_DIZIN, exist_ok=True)
    jf = open(jsonl_yol, "a", encoding="utf-8")

    kunye = {"tur": "kunye", "zaman": datetime.now().isoformat(timespec="seconds"),
             "git": git_commit(), "kume": a.kume, "n": len(yollar), "n_pozitif": n_poz,
             "roi": list(ROI), "kutu_dar": _kutu(1.0), "kutu_baglam": _kutu(2.0),
             "max_side": MAX_SIDE, "crf": CRF, "temperature": T,
             "max_tokens": MAX_TOKENS, "guided": True, "deneme": DENEME,
             "referans_klip": REFERANS_KLIP, "sistem": SISTEM, "giris": GIRIS,
             "giris_tam": GIRIS_TAM, "on_kayitli_aile": ON_KAYITLI,
             "posthoc": [h["kod"] for h in hucreler if h.get("posthoc")],
             "hucreler": [{k: v for k, v in h.items() if k != "yorum"} for h in hucreler],
             "base_url_host": settings.base_url.split("//")[-1].split("/")[0],
             "argv": sys.argv[1:],
             "on_kayit": __doc__.split("=== ON-KAYIT")[1]}
    jf.write(json.dumps(kunye, ensure_ascii=False) + "\n")
    jf.flush()

    # --- H6/H7 referans goruntusu -------------------------------------------
    ref_jpeg = None
    if any(h["protokol"] == "2goruntu" for h in hucreler):
        ref_yol = os.path.join(SET, ACIK_DIZIN, REFERANS_KLIP)
        if os.path.exists(ref_yol):
            ref_jpeg = roi_karesi(ref_yol, "baglam")
            print(f"  referans (ACIK) {REFERANS_KLIP}: {len(ref_jpeg)/1024:.1f} KB")
        else:
            print(f"  UYARI: referans klip yok ({REFERANS_KLIP}) — 2goruntu kollari ATLANIR")
            hucreler = [h for h in hucreler if h["protokol"] != "2goruntu"]

    satirlar = {h["kod"]: [] for h in hucreler}
    t0 = time.time()

    for i, (yol, ihlal) in enumerate(yollar, 1):
        ad = os.path.basename(yol)
        # kirpilan videolar KLIP BASINA BIR KEZ uretilir; ayni baytlar tum
        # ayni-kirpmali hucrelere gider (esli tasarim + on-ek onbellegi)
        video_bayt, kare_bayt = {}, {}
        cevaplar = {}
        for kirpma in sorted({h["kirpma"] for h in hucreler if h["protokol"] == "video"}):
            try:
                video_bayt[kirpma] = roi_videosu(yol, kirpma)
            except Exception as e:
                video_bayt[kirpma] = None
                print(f"  [KODLAMA HATASI] {ad} {kirpma}: {e}")
        if any(h["protokol"] == "2goruntu" for h in hucreler):
            try:
                kare_bayt["baglam"] = roi_karesi(yol, "baglam")
            except Exception as e:
                kare_bayt["baglam"] = None
                print(f"  [KARE HATASI] {ad}: {e}")

        # --- VIDEO KOLLARI: (model, kirpma) basina TEK oturum, cok soru --------
        gruplar = {}
        for h in hucreler:
            if h["protokol"] == "video":
                gruplar.setdefault((h["model"], h["kirpma"]), []).append(h)
        for (model, kirpma), grup in sorted(gruplar.items()):
            baytlar = video_bayt.get(kirpma)
            if baytlar is None:
                for h in grup:
                    satirlar[h["kod"]].append({"klip": ad, "ihlal": ihlal, "hata": True,
                                               "ham": "__KODLAMA__", "karar": None})
                    cevaplar[h["kod"]] = "__KODLAMA_HATASI__"
                continue
            otu, hata_mesaji = None, None
            for deneme in range(DENEME):
                otu = istemciler[model].video_oturumu(baytlar, system=SISTEM,
                                                      giris_metni=_giris(kirpma))
                if otu.hazir:
                    break
                hata_mesaji = otu.hata
                otu = None
                if deneme < DENEME - 1:
                    time.sleep(BEKLE)
            for h in grup:
                ham, hm = None, hata_mesaji
                if otu is not None:
                    for deneme in range(DENEME):
                        c = otu.sor(h["soru"], guided_choice=h["secenek"],
                                    temperature=T, max_tokens=MAX_TOKENS, hatirla=False)
                        if c is not None:
                            ham, hm = c, None
                            break
                        hm = otu.hata
                        if deneme < DENEME - 1:
                            time.sleep(BEKLE)
                hatali = ham is None
                satirlar[h["kod"]].append({
                    "klip": ad, "ihlal": ihlal, "hata": hatali,
                    "ham": ham if ham else (hm or ""),
                    "karar": None if (hatali or h["yorum"] is None) else h["yorum"](ham)})
                cevaplar[h["kod"]] = ham if not hatali else f"__HATA__ {hm}"

        # --- 2 GORUNTU KOLLARI -------------------------------------------------
        for h in [x for x in hucreler if x["protokol"] == "2goruntu"]:
            if ad == REFERANS_KLIP:
                cevaplar[h["kod"]] = "__REFERANS_ATLANDI__"
                continue
            sorgu = kare_bayt.get("baglam")
            if sorgu is None or ref_jpeg is None:
                satirlar[h["kod"]].append({"klip": ad, "ihlal": ihlal, "hata": True,
                                           "ham": "__KODLAMA__", "karar": None})
                cevaplar[h["kod"]] = "__KODLAMA_HATASI__"
                continue
            ist = istemciler[h["model"]]
            mesajlar = [
                {"role": "system", "content": SISTEM_GORUNTU},
                {"role": "user", "content": [
                    {"type": "text", "text": h["soru"]},
                    {"type": "image_url",
                     "image_url": {"url": VLMClient._to_data_url(ref_jpeg)}},
                    {"type": "image_url",
                     "image_url": {"url": VLMClient._to_data_url(sorgu)}},
                ]},
            ]
            ham, hm = None, None
            for deneme in range(DENEME):
                try:
                    c = ist.chat(mesajlar, temperature=T, max_tokens=MAX_TOKENS,
                                 guided_choice=h["secenek"])
                except Exception as e:
                    hm = f"{type(e).__name__}: {e}"
                    c = None
                if c is not None:
                    ham, hm = c, None
                    break
                if deneme < DENEME - 1:
                    time.sleep(BEKLE)
            hatali = ham is None
            satirlar[h["kod"]].append({
                "klip": ad, "ihlal": ihlal, "hata": hatali,
                "ham": ham if ham else (hm or ""),
                "karar": None if hatali else h["yorum"](ham)})
            cevaplar[h["kod"]] = ham if not hatali else f"__HATA__ {hm}"

        kayit = {"tur": "klip", "klip": ad, "ihlal": ihlal, "kume": a.kume,
                 "cevap": cevaplar,
                 "boyut_kb": {k: (round(len(v) / 1024, 1) if v else None)
                              for k, v in video_bayt.items()}}
        jf.write(json.dumps(kayit, ensure_ascii=False) + "\n")
        jf.flush()
        print(f"  {i:3d}/{len(yollar)} {ad:14s} {'ACIK ' if ihlal else 'KAPALI'} | "
              + " ".join(f"{k}={str(v)[:12]}" for k, v in sorted(cevaplar.items())),
              flush=True)

    print(f"\ntoplam sure {time.time()-t0:.0f} s")

    # ------------------------------------------------------------------ rapor
    ozet = {}
    h5_esik = None
    for h in hucreler:
        sat = satirlar[h["kod"]]
        # SAYISAL hucre = "yorum" None olan her hucre (H5 ve post-hoc H8).
        # KUSUR (bulundu ve duzeltildi): bu blok eskiden YALNIZCA kod=="H5" icin
        # calisiyordu; H8 sayisal olmasina ragmen karar URETMIYOR, 34 klibin
        # tamami "kararsiz" sayilip MCC 0,000 raporlaniyordu. Ham cevaplar
        # dogruydu, PUANLAMA yanlisti.
        if h["yorum"] is None:
            if a.h5_esik:
                # TUTMA: esik SECIM kumesinde secildi, burada SABIT — tarama YOK.
                h5_esik = a.h5_esik
                sat = [{"klip": r["klip"], "ihlal": r["ihlal"], "hata": r["hata"],
                        "ham": r["ham"],
                        "karar": None if r["hata"] else _sayisal_yorum(h5_esik)(r["ham"])}
                       for r in sat]
                print(f"\n{h['kod']} esigi SABIT = {h5_esik} "
                      f"(SECIM kumesinden; te'de tarama YAPILMADI)")
            else:
                ham_sat = satirlar[h["kod"]]
                h5_esik, _m, sat = esik_tara(ham_sat)
                print(f"\n{h['kod']} esik taramasi -> en iyi esik = {h5_esik} (tr'de secildi)")
                print("  esik duyarliligi (tr):", {e: tablo([
                    {"klip": r["klip"], "ihlal": r["ihlal"], "hata": r["hata"],
                     "ham": r["ham"],
                     "karar": None if r["hata"] else _sayisal_yorum(e)(r["ham"])}
                    for r in ham_sat])["mcc"] for e in range(1, 11)})
            satirlar[h["kod"]] = sat
        ana = tablo(sat)
        ikincil = tablo(sat, ikincil=True)
        dej = dejenere_kontrol(sat)
        gecerli = [r for r in sat if not r["hata"]]
        karar_orani = (ana["n_karar"] / len(gecerli)) if gecerli else 0.0
        ozet[h["kod"]] = {"yol": h["yol"], "kirpma": h["kirpma"], "model": h["model"],
                          "protokol": h["protokol"], "ana": ana, "ikincil": ikincil,
                          "dejenere": dej, "karar_orani": round(karar_orani, 4),
                          "esik": h5_esik if h["yorum"] is None else None,
                          "satirlar": sat}

    perm = permutasyon({k: satirlar[k] for k in ozet}) if a.kume == "tr" else None

    print(f"\n{'='*104}\nANA TABLO — KARAR VERILEN KLIPLER (kacislar KARARSIZ, negatife CEVRILMEDI)\n{'='*104}")
    print(f"{'kod':4s} {'yol':4s} {'kirpma':7s} {'model':10s} {'prot':9s} "
          f"{'TP':>3s} {'FP':>3s} {'FN':>3s} {'TN':>3s} {'krsz':>4s} {'hata':>4s} "
          f"{'n':>3s} {'MCC':>7s} {'dogr':>6s} {'GA95':>13s} {'karar':>6s} {'DEJ':>4s} {'p*':>7s}")
    print("-" * 104)
    for kod, o in ozet.items():
        an = o["ana"]
        p_h = perm["p_hucre"].get(kod) if perm else None
        print(f"{kod:4s} {o['yol']:4s} {o['kirpma']:7s} {o['model']:10s} {o['protokol']:9s} "
              f"{an['tp']:3d} {an['fp']:3d} {an['fn']:3d} {an['tn']:3d} "
              f"{an['kararsiz']:4d} {an['hata']:4d} {an['n_karar']:3d} "
              f"{an['mcc']:+7.3f} {an['dogruluk']:6.3f} "
              f"[{an['ga95'][0]:.2f},{an['ga95'][1]:.2f}] {o['karar_orani']:6.2f} "
              f"{'EVET' if o['dejenere']['dejenere'] else '  - ':4s} "
              + (f"{p_h:7.4f}" if p_h is not None else "      -"))

    print(f"\n{'='*104}\nIKINCIL — SAHADA DAGITIM (kacis = alarm yok) · ANA TABLO DEGIL\n{'='*104}")
    for kod, o in ozet.items():
        ik = o["ikincil"]
        print(f"{kod:4s} TP={ik['tp']:3d} FP={ik['fp']:3d} FN={ik['fn']:3d} TN={ik['tn']:3d} "
              f"MCC={ik['mcc']:+.3f} dogruluk={ik['dogruluk']:.3f}")

    print(f"\n{'='*104}\nDEJENERELIK\n{'='*104}")
    for kod, o in ozet.items():
        d = o["dejenere"]
        print(f"{kod:4s} dejenere={'EVET' if d['dejenere'] else 'hayir':5s} "
              f"D1={d['D1_ham_cevap']} D2={d['D2_karar']} "
              f"en_sik={d['en_sik_cevap']!r} ({d['en_sik_oran']:.2f})  "
              f"dagilim={d['ham_dagilim']}")

    if perm:
        print(f"\n{'='*104}\nCOKLU KARSILASTIRMA — MAKS-ISTATISTIGI PERMUTASYONU\n{'='*104}")
        print(f"  hucre sayisi={len(ozet)} (H5 icin 10 esik HER permutasyonda yeniden tarandi)")
        print(f"  permutasyon={perm['n_perm']}  bos dagilim ortalamasi={perm['bos_ortalama']:+.3f}")
        print(f"  BOS DAGILIM %95 KUANTILI = {perm['bos_q95']:+.3f}   <- bir hucre bunu "
              f"GECMEDIKCE sans ile aciklanabilir")
        print(f"  gozlenen en yuksek MCC = {perm['gozlenen_maks']:+.3f}  "
              f"duzeltilmis p = {perm['p_duzeltilmis']:.5f}")

    print(f"\n{'='*104}\nBASARI OLCUTU (kosumdan ONCE ilan edildi)\n{'='*104}")
    gecen = []
    for kod, o in ozet.items():
        p_h = perm["p_hucre"].get(kod, 1.0) if perm else 1.0
        ok = kullanilabilir(o["dejenere"], o["ana"], o["karar_orani"], p_h)
        if ok:
            gecen.append(kod)
        print(f"  {kod}: {'KULLANILABILIR' if ok else 'kaldi'}")
    print(f"\n  GECEN HUCRE: {gecen if gecen else 'HICBIRI'}")

    ozet_kayit = {"tur": "ozet", "kume": a.kume,
                  "hucre": {k: {x: y for x, y in v.items() if x != "satirlar"}
                            for k, v in ozet.items()},
                  "permutasyon": perm, "gecen": gecen, "h5_esik": h5_esik}
    jf.write(json.dumps(ozet_kayit, ensure_ascii=False) + "\n")
    jf.close()

    json_yol = os.path.join(CIKTI_DIZIN, f"evren_pano_ozel_{a.kume}{ek}_{zaman}.json")
    json.dump({"kunye": kunye, "ozet": ozet, "permutasyon": perm, "gecen": gecen},
              open(json_yol, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nham: {os.path.relpath(jsonl_yol, KOK)}\nozet: {os.path.relpath(json_yol, KOK)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
