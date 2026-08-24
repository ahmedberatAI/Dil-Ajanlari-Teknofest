"""Forklift asiri yuk — IKI BAGIMSIZ YOL (D40).

Kaynak makale (Onal & Dandil 2024, Data in Brief 56:110756) etiketi ISLEMSEL
tanimliyor:

    "carrying 2 blocks or less with a forklift (Safe Carrying), whereas ... an
     example of an unsafe worker behaviour occurs by carrying 3 blocks or more"

Yani karar KASA SAYMAKTIR. Devrilme riski, agirlik kestirimi, agirlik merkezi
GEREKMIYOR. Bu modul kasayi iki farkli yoldan sayar:

  YOL 1 — VLM ("vlm"): modele dogrudan "catalda kac kasa var?" diye sorulur.
  YOL 2 — GEOMETRI ("geometri"): turuncu kasa istifinin en/boy orani sayiya cevrilir.

OLCULDU (2026-08-19, 50 klip: 25 Overload / 25 Safe_Carrying):

    kol                                    MCC      dogruluk
    -------------------------------------  -------  --------
    ANLAMSAL soru ("asiri yuk var mi?")    +0,000   0,500   <- DEJENERE, 50/50 "gorunmuyor"
    ANLAMSAL + mekansal capa               +0,000   0,500   <- DEJENERE
    ISLEMSEL soru ("kac kasa?")            +0,762   0,880

    A -> B: McNemar p = 6,6e-05. A2 ≡ A (p=1) -> kazanan MEKANSAL DIKKAT DEGIL,
    sorunun GOZLEMLENEBILIRLIGI.

KODLAMA IZI KONTROLU (bu veri setinde bit hizi tek basina siniflari MCC +1,000 ile
ayiriyor — hic ortusme yok). 50 klip ORTAK spesifikasyona yeniden kodlandi
(profil/pix_fmt/bit hizi esitlendi): sonuc DUSMEDI, +0,682 -> +0,762 YUKSELDI.
Model sikistirma imzasi okumuyor.

TASINABILIRLIK: "3 kasa" bu TESISIN konvansiyonudur, genel bir ISG kurali degildir.
Baska tesiste esik yeniden belirlenmelidir. Bu yuzden varsayilan KAPALI (K2).

LISANS: geometri yolu yalniz numpy. VLM yolu mevcut istemci. ultralytics KULLANILMAZ.
"""
from __future__ import annotations

import io
import re
from typing import List, Optional, Sequence, Tuple

# Kaynak makalenin esigi: ">= 3 blok" ihlaldir.
ESIK_VARSAYILAN = 3

# --- VLM yolu -------------------------------------------------------------
SORU = ("Forkliftin CATALINDA ust uste kac adet kasa/blok tasiniyor? "
        "Yalnizca sayiyi yaz.")
SECENEKLER = ["0", "1", "2", "3", "4", "5", "6+", "GORUNMUYOR"]
# D42 OLCULDU — "cekimserlige davet" cumlesi PERFORMANSI YIKIYOR.
# Ayni model (llm-large), ayni cozunurluk, ayni klipler, ayni baytlar; 2x2 faktoriyel:
#     sistem promptu VAR + kacis secenegi VAR : kacis %86 · MCC +0,000  DEJENERE
#     sistem promptu VAR + kacis secenegi YOK : kacis  %0 · MCC +0,578
#     sistem promptu YOK + kacis secenegi VAR : kacis %66 · MCC +0,775
#     sistem promptu YOK + kacis secenegi YOK : kacis  %0 · MCC +0,885  <- EN IYI
# Yani belirleyici eksen MODEL de COZUNURLUK de DEGIL; PROMPT.
#
# AMA kacis secenegini korumak GEREKIYOR (D33): IKILI soruda kacis kaldirilinca
# model bu sefer her klibe AYNI etiketi veriyor (pano: 34/34 "KAPALI", FN=21).
# Dogru cozum SORU BICIMI: SAYI iste, evet/hayir isteme. Sayisal soruda model
# zaten kacmiyor (forklift 50/50 karar verdi) ve kacis secenegi zararsiz kaliyor.
SISTEM = ("Sen bir endustriyel is guvenligi kamerasi analiz sistemisin. "
          "YALNIZCA GORDUGUNE dayan; varsayim yapma.")

# --- Geometri yolu --------------------------------------------------------
# Turuncu/pas rengi kasa: kirmizi baskin, mavi dusuk. Esikler goruntu denetimiyle
# secildi (kasalar 1920x1080 CCTV'de belirgin turuncu).
_TURUNCU = dict(r_g_fark=25, r_b_fark=45, r_min=70)
# Tek kasanin boy/en orani. Istif N kasa ise oran ~ N * BIRIM.
# Etiketsiz kestirildi (asagida `birim_kestir`), sabit deger YEDEK olarak durur.
BIRIM_YEDEK = 0.42
# TESISE OZGU kalibrasyon (Kamera 14, forklift yollari) — etiketsiz kestirildi.
# y_ufuk: en(w) ~ k*(y_alt - y_ufuk) regresyonundan; esik: f_pers dagiliminin medyani.
Y_UFUK_VARSAYILAN = 0.3
F_PERS_ESIK_VARSAYILAN = 0.5751


def _sayiya_cevir(cevap: str) -> Optional[int]:
    """VLM cevabini kasa sayisina cevirir. Cozulemezse None."""
    c = (cevap or "").strip().upper()
    if not c or c.startswith("GORUNMUYOR") or c.startswith("__HATA__"):
        return None
    if c.endswith("+"):
        c = c[:-1]
    try:
        return int(c)
    except ValueError:
        pass
    s = re.findall(r"\d+", c)          # serbest metin geldiyse SON sayi
    return int(s[-1]) if s else None


def kasa_say_vlm(frames: Sequence[Tuple[str, bytes]], istemci,
                 azami_kare: int = 8) -> Optional[int]:
    """VLM'e dogrudan sorar. Hata/kararsizlik -> None (K3 fail-open)."""
    if not frames:
        return None
    kar = list(frames)
    if len(kar) > azami_kare:           # vLLM --limit-mm-per-prompt image:16
        adim = len(kar) / azami_kare
        kar = [kar[min(len(kar) - 1, int(i * adim))] for i in range(azami_kare)]
    try:
        c = istemci.analyze_frames(kar, SORU, system=SISTEM, temperature=0.0,
                                   max_tokens=24, guided_choice=SECENEKLER)
    except Exception:
        return None
    return _sayiya_cevir(c)


def _turuncu_maske(a):
    import numpy as np
    r = a[..., 0].astype(np.int16)
    g = a[..., 1].astype(np.int16)
    b = a[..., 2].astype(np.int16)
    return ((r - g > _TURUNCU["r_g_fark"]) & (r - b > _TURUNCU["r_b_fark"])
            & (r > _TURUNCU["r_min"]))


def _en_buyuk_bilesen(m):
    """En buyuk bagli bilesenin sinir kutusu (x1,y1,x2,y2) veya None."""
    import numpy as np
    try:
        from scipy import ndimage
        et, n = ndimage.label(m)
        if not n:
            return None
        boy = ndimage.sum(m, et, range(1, n + 1))
        i = int(np.argmax(boy)) + 1
        if boy[i - 1] < 400:            # cok kucuk -> yuk degil
            return None
        ys, xs = np.where(et == i)
    except Exception:
        ys, xs = np.where(m)
        if len(ys) < 400:
            return None
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def istif_olcum(frames: Sequence[Tuple[str, bytes]]) -> Optional[dict]:
    """Turuncu istifin HAM olcumleri (kareler medyani).

    Donus: {"h": boy_px, "w": en_px, "y_alt": alt_kenar_px, "oran": h/w}
    Perspektif duzeltmesi icin y_alt SART: kameraya uzak yuk KUCUK gorunur.
    """
    import numpy as np
    from PIL import Image
    hh, ww, yy = [], [], []
    for _, jpeg in frames:
        try:
            a = np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))
        except Exception:
            continue
        kutu = _en_buyuk_bilesen(_turuncu_maske(a))
        if kutu is None:
            continue
        x1, y1, x2, y2 = kutu
        hh.append(max(1, y2 - y1)); ww.append(max(1, x2 - x1)); yy.append(y2)
    if not hh:
        return None
    return {"h": float(np.median(hh)), "w": float(np.median(ww)),
            "y_alt": float(np.median(yy)),
            "oran": float(np.median(np.array(hh) / np.array(ww)))}


def ufuk_kestir(olcumler: Sequence[dict]) -> float:
    """Ufuk cizgisini ETIKETSIZ kestirir.

    Sabit fiziksel boyutlu bir nesne icin goruntudeki EN (w), kameradan uzakliga
    ters orantilidir: w ~ k*(y_alt - y_ufuk). w'yi y_alt'a regresyon edip
    w=0 noktasi bulunur -> y_ufuk. EN kullanilir cunku en, istif YUKSEKLIGINDEN
    (yani sinif etiketinden) BAGIMSIZDIR — boy kullanmak etiket sizdirirdi.
    """
    import numpy as np
    v = [(o["y_alt"], o["w"]) for o in olcumler if o]
    if len(v) < 8:
        return -60.0
    y = np.array([a for a, _ in v]); w = np.array([b for _, b in v])
    if float(np.std(y)) < 1e-6:
        return -60.0
    egim, kesme = np.polyfit(y, w, 1)
    if abs(egim) < 1e-9:
        return -60.0
    return float(-kesme / egim)


def perspektif_boy(olcum: dict, y_ufuk: float) -> Optional[float]:
    """Perspektiften arindirilmis istif yuksekligi (birimsiz).

    f_pers = h / (y_alt - y_ufuk).  Kameraya uzaklik telafi edilir.
    """
    if not olcum:
        return None
    payda = olcum["y_alt"] - y_ufuk
    return float(olcum["h"] / payda) if payda > 1e-6 else None


def istif_orani(frames: Sequence[Tuple[str, bytes]]) -> Optional[float]:
    """Turuncu istifin BOY/EN orani (kareler medyani). Bulunamazsa None.

    Fizik: kasa boyutu sabit oldugundan N kasalik istifin boy/en orani ~ N*birim.
    Ajanin olcumu bunu dogruluyor: sinif medyan orani 3/2 = 1,500 beklenirken
    1,576 olculdu.
    """
    import numpy as np
    from PIL import Image
    oranlar = []
    for _, jpeg in frames:
        try:
            a = np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))
        except Exception:
            continue
        kutu = _en_buyuk_bilesen(_turuncu_maske(a))
        if kutu is None:
            continue
        x1, y1, x2, y2 = kutu
        w, h = max(1, x2 - x1), max(1, y2 - y1)
        oranlar.append(h / w)
    if not oranlar:
        return None
    return float(np.median(oranlar))


def birim_kestir(oranlar: Sequence[float]) -> float:
    """Tek kasanin boy/en birimini ETIKETSIZ kestirir.

    Dagilim iki tepelidir (2 kasa ve 3 kasa). Alt tepenin medyani ~2*birim.
    Etiket KULLANILMAZ — yalnizca oran dagiliminin kendi yapisi.
    """
    import numpy as np
    v = np.array([o for o in oranlar if o and o > 0], dtype=float)
    if len(v) < 8:
        return BIRIM_YEDEK
    esik = float(np.median(v))
    alt = v[v <= esik]
    return float(np.median(alt) / 2.0) if len(alt) else BIRIM_YEDEK


def asiri_yuk_geometri(frames: Sequence[Tuple[str, bytes]],
                       y_ufuk: float = Y_UFUK_VARSAYILAN,
                       esik: float = F_PERS_ESIK_VARSAYILAN) -> Optional[bool]:
    """Perspektif duzeltmeli istif yuksekligi ESIGI asiyor mu?

    OLCULDU (50 klip, kendi yeniden yazimim):
        ham boy/en orani (perspektifsiz) : MCC +0,280
        PERSPEKTIF duzeltmeli f_pers     : MCC +0,641  TP=20 FP=4 FN=5 TN=21
    Fiziksel dogrulama: sinif medyan orani 1,331 (3/2 = 1,500 bekleniyor).

    DURUSTLUK: alt ajanin bildirdigi +0,718'e ULASILAMADI (kodu elde kalmadi,
    tarif uzerinden yeniden yazildi). Rapor edilen sayi BU surumun sayisidir.
    Ayrica esik ayni 50 klibin medyanindan geldigi icin hafif iyimserdir.
    """
    o = istif_olcum(frames)
    f = perspektif_boy(o, y_ufuk) if o else None
    return None if f is None else (f > esik)


def kasa_say_geometri(frames: Sequence[Tuple[str, bytes]],
                      birim: float = BIRIM_YEDEK) -> Optional[int]:
    """Turuncu istif oranindan KABA kasa sayisi (perspektifsiz — zayif).

    Yalnizca bilgi amaclidir; karar icin `asiri_yuk_geometri` kullanilir.
    """
    o = istif_orani(frames)
    if o is None or birim <= 0:
        return None
    return max(0, int(round(o / birim)))


def asiri_yuk(frames: Sequence[Tuple[str, bytes]], yontem: str = "vlm",
              esik: int = ESIK_VARSAYILAN, istemci=None,
              y_ufuk: float = Y_UFUK_VARSAYILAN,
              f_pers_esik: float = F_PERS_ESIK_VARSAYILAN) -> Optional[dict]:
    """`esik` veya daha fazla kasa -> ihlal.

    yontem: "vlm" · "geometri" · "ikisi" (ikisi = HER IKISI de esigi gecerse ihlal;
    yanlis alarmi dusurur, duyarliligi dusurur — olculmeden dagitilmamali).

    Donus: {"time", "kasa", "yontem", "vlm", "geometri"} veya None (K3 fail-open).
    """
    if not frames:
        return None
    v_sayi = g_asiri = None
    if yontem in ("vlm", "ikisi") and istemci is not None:
        v_sayi = kasa_say_vlm(frames, istemci)
    if yontem in ("geometri", "ikisi"):
        g_asiri = asiri_yuk_geometri(frames, y_ufuk=y_ufuk, esik=f_pers_esik)

    v_asiri = None if v_sayi is None else (v_sayi >= esik)

    if yontem == "vlm":
        karar = v_asiri
    elif yontem == "geometri":
        karar = g_asiri
    else:                                # "ikisi": IKISI de ihlal demeli
        if v_asiri is None or g_asiri is None:
            return None
        karar = v_asiri and g_asiri

    if not karar:
        return None
    return {"time": frames[0][0], "yontem": yontem,
            "vlm_kasa": v_sayi, "geometri_asiri": g_asiri}
