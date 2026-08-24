"""Elektrik/kontrol panosu kapak durumu — deterministik İSG dedektoru (D39-E).

NEDEN VLM DEGIL (olculdu, 2026-08-18)
-------------------------------------
VLM bu ayrimi yapamiyor:

    tam kare @768        : 12 acik panonun  0'i dogru
    panoya kirpilmis     : 12 acik panonun  1'i dogru  (2,5x detay, ayni token)
    Qwen3.8-27B          : 99 klipte        0 dogru

Ama fiziksel mekanizma basit: **acik kapak = karanlik oyuk**. Dar pano ROI'sinde
kareler boyunca MINIMUM ortalama parlaklik tek skaler olarak class2-vs-class6
algi gorevini %95,9 dogrulukla cozuyor — model yok, egitim yok.

NEDEN TEK BASINA YETMEZ
-----------------------
`Authorized_Intervention` (yetkili bakim) kliplerinde pano da **fiziksel olarak
aciktir**. Yalnizca parlakliga bakan kural orada 25 klibin 20'sine yanlis alarm
verir (gercek guvenlik gorevi: MCC +0,513, FP=21).

**"Pano acik" gorunur; "yetkili mi" GORUNMEZ.** Ayrimi konum terimi saglar:
pano kutusuyla ortusen kisi orani class2 (ihlal) **0,12** — class5 (yetkili)
**0,88**. Yani class5'te biri panonun BASINDA, class2'de pano BASIBOS.

BILESIK KURAL: *pano karanlik* **VE** *basinda kisi yok* -> ihlal.

    gercek guvenlik gorevi (class2 vs class6+class5, n=74):
        yalniz parlaklik : dogruluk 0,703 · MCC +0,513 · FP=21
        BILESIK          : dogruluk 0,932 · MCC +0,845 · FP=1
        BILESIK (tutma)  : dogruluk 0,962 · MCC +0,799 · FP=0   (n=26)

KONTROLLER (docs/pano_dedektoru_2026-08-18.md)
  - maks-istatistigi permutasyonu (8 varyant, n=2000): p = 0,0005
  - mekansal plasebo: PANO +0,845 · AYNA +0,539 · ORTA +0,254
  - dis gecerlilik: class5 ayri oturum, yine de pano-yerel olcum onu dogru yerde tutuyor

UYARI — TASINABILIRLIK (OLCULDU, hafife alinmisti)
ROI ve parlaklik esigi **kamera GORUSUNE ozgudur** — tesise degil. Tam 197 klipte
olculdu: pano siniflarinin gorusunde kural temiz (Closed_Panel_Cover 0/25,
Authorized_Intervention 1/25, tasima siniflari 0/50), ama AYNI TESISIN farkli
kamera cercevesindeki yaya-yolu kliplerinde sabit ROI panoya degil baska bir
karanlik makine parcasina dusuyor ve bosa atesliyor (Safe_Walkway_Violation
17/25, Normal/Safe_Walkway 12/23). MCC +0,845 -> +0,270.

Bu yuzden **GORUS KILIDI** eklendi: `panel_gorus_imza` set edilirse kural yalnizca
kalibre edildigi gorusle eslesen kliplerde calisir. Imza `gorus_imzasi()` ile
uretilir (bkz. scripts/pano_kalibre.py).

Varsayilan yine **KAPALI** (K2).

LISANS: parlaklik yolu yalnizca numpy. Kisi tespiti `algila_rtdetr`
(RT-DETRv2, Apache-2.0). **ultralytics kullanilmaz.**
"""
from __future__ import annotations

import io
from typing import List, Optional, Sequence, Tuple

# Tesisimizde olculmus varsayilan: hicbir KAPALI klipte gorulmeyen karanlik seviye.
LUMA_ESIK_VARSAYILAN = 87.6


def roi_ayristir(s: str) -> Optional[Tuple[float, float, float, float]]:
    """"x1,y1,x2,y2" (0-1 orani) -> demet. Gecersizse None (K3)."""
    if not s or not s.strip():
        return None
    try:
        p = [float(x) for x in s.split(",")]
    except ValueError:
        return None
    if len(p) != 4:
        return None
    x1, y1, x2, y2 = p
    if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
        return None
    return (x1, y1, x2, y2)


def _kutu_pikselde(roi, w: int, h: int) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = roi
    return (int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h))


def _ortusuyor(kutu: Sequence[float], hedef: Tuple[int, int, int, int]) -> bool:
    """Kisi kutusu pano kutusuyla kesisiyor mu (alan > 0)."""
    ax1, ay1, ax2, ay2 = kutu
    bx1, by1, bx2, by2 = hedef
    return (min(ax2, bx2) > max(ax1, bx1)) and (min(ay2, by2) > max(ay1, by1))


# --- GORUS KILIDI -----------------------------------------------------------
# Sabit ROI yalnizca kalibre edildigi kamera gorusunde anlamlidir. Imza, sahnenin
# kaba yapisidir: kareler medyani -> 16x9 gri -> z-normalize. Karsilastirma
# Pearson korelasyonu ile. Olculmus ayrim (48 klip, iki cerceve):
# gorus-ICI ciftler ort +0,938 · gorus-ARASI +0,175 -> 0,60 esigi genis marjla ayirir.
IMZA_W, IMZA_H = 16, 9
GORUS_ESIK_VARSAYILAN = 0.60


def _kaba_gri(frames) -> "object":
    import numpy as np
    from PIL import Image
    yig = []
    for _, jpeg in frames:
        im = Image.open(io.BytesIO(jpeg)).convert("L").resize(
            (IMZA_W, IMZA_H), Image.BILINEAR)
        yig.append(np.asarray(im, dtype=np.float32))
    if not yig:
        return None
    a = np.median(np.stack(yig), axis=0).ravel()   # medyan: hareketli kisiler silinir
    sd = float(a.std())
    return (a - a.mean()) / sd if sd > 1e-6 else None


def gorus_imzasi(frames: Sequence[Tuple[str, bytes]]) -> str:
    """Sahnenin kaba yapi imzasi (kalibrasyon icin). Uretilemezse bos dize."""
    try:
        v = _kaba_gri(frames)
        if v is None:
            return ""
        return ",".join(f"{x:.3f}" for x in v)
    except Exception:
        return ""


def gorus_uyuyor(frames: Sequence[Tuple[str, bytes]], imza: str,
                 esik: float = GORUS_ESIK_VARSAYILAN) -> bool:
    """Klip, kalibre edilen gorusle ayni mi? Imza bossa **kilit yok** -> True."""
    if not imza or not imza.strip():
        return True
    try:
        import numpy as np
        ref = np.array([float(x) for x in imza.split(",")], dtype=np.float32)
        cur = _kaba_gri(frames)
        if cur is None or cur.shape != ref.shape:
            return False
        return float(np.dot(ref, cur) / len(ref)) >= esik
    except Exception:
        return False          # imza cozulemiyorsa ATESLEMEYIZ (guvenli yon)


def pano_durumu(frames: Sequence[Tuple[str, bytes]], roi_str: str,
                luma_esik: float = LUMA_ESIK_VARSAYILAN,
                kisi_kontrolu: bool = True,
                conf: float = 0.35,
                gorus_imza: str = "",
                gorus_esik: float = GORUS_ESIK_VARSAYILAN) -> Optional[dict]:
    """Pano kapagi ACIK ve BASIBOS mu?

    Donus (ihlal varsa):
        {"time": "MM:SS", "luma": float, "esik": float, "kisi_vardi": bool,
         "n_kare": int}
    Ihlal yoksa **None**. Hata olursa da **None** (K3 fail-open — yanlis olay uretmez).
    """
    roi = roi_ayristir(roi_str)
    if roi is None or not frames:
        return None
    # GORUS KILIDI — sabit ROI yanlis kamera gorusunde anlamsizdir (olculdu).
    if not gorus_uyuyor(frames, gorus_imza, gorus_esik):
        return None
    try:
        import numpy as np
        from PIL import Image
    except Exception:
        return None

    try:
        lumalar: List[float] = []
        kutular: Optional[Tuple[int, int, int, int]] = None
        for ts, jpeg in frames:
            im = Image.open(io.BytesIO(jpeg)).convert("L")
            w, h = im.size
            if kutular is None:
                kutular = _kutu_pikselde(roi, w, h)
            x1, y1, x2, y2 = kutular
            a = np.asarray(im, dtype=np.float32)[y1:y2, x1:x2]
            lumalar.append(float(a.mean()) if a.size else 255.0)
        if not lumalar or kutular is None:
            return None
        en_karanlik = min(lumalar)
        if en_karanlik >= luma_esik:
            return None                     # pano KAPALI -> olay yok
        idx = int(min(range(len(lumalar)), key=lambda i: lumalar[i]))

        kisi_vardi = False
        if kisi_kontrolu:
            from dilajan import algila_rtdetr
            kareler = algila_rtdetr.kisileri_bul(frames, conf=conf)
            # "ANY": HERHANGI bir karede panonun basinda biri varsa -> yetkili bakim
            for kare in kareler:
                for p in kare:
                    if _ortusuyor(p["kutu"], kutular):
                        kisi_vardi = True
                        break
                if kisi_vardi:
                    break
            if kisi_vardi:
                return None                 # acik AMA basinda biri var -> ihlal degil

        return {"time": frames[idx][0], "luma": round(en_karanlik, 1),
                "esik": float(luma_esik), "kisi_vardi": kisi_vardi,
                "n_kare": len(lumalar)}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# D42 — VLM YOLU: SAYISAL SORU (ikili soru CALISMIYOR, sayisal soru CALISIYOR)
# ---------------------------------------------------------------------------
# Haftalarca "VLM bu sinifi goremiyor" dedik. Yanlisti: goruyor, ama IKILI SORU
# bicimi o bilgiye erisimi yok ediyor. Ayni model, AYNI VIDEO, AYNI oturum:
#
#   soru bicimi                              sonuc
#   ---------------------------------------  -----------------------------------
#   "kapak ACIK mi KAPALI mi?"               34/34 "GORUNMUYOR"   MCC +0,000
#   ayni soru, kacis secenegi YOK            34/34 "KAPALI"       MCC +0,000 (FN=21)
#   "koyu/karanlik OYUK gorunuyor mu?"       34/34 "GORUNMUYOR"   MCC +0,000
#   "0-10 arasi ne kadar KARANLIK?"          ACIK'lara 8-9, KAPALI'lara 2  MCC +1,000
#
# Ve KIRPMA GEREKMIYOR: ayni sayisal soru TAM KAREDE de calisti (MCC +0,817,
# dogruluk 0,912, dejenere DEGIL). ROI kirpmasiyla farki n=34'te anlamli degil (p=0,25).
#
# DURUSTLUK — bu yolu KULLANMADAN once bilinmeli: tutma kumesinde (n=15) VLM,
# yukaridaki 3 satirlik luma dedektoruyle 15/15 klipte BIREBIR AYNI karari verdi
# (ayni TP/FP/FN/TN, ayni tek hata 2_te12). Yani dogruluk acisindan VLM'in
# dedektore EKLEDIGI sey OLCULEBILIR DEGIL — ama bir uzak GPU cagrisina mal oluyor.
# VLM yolunun degeri baska: (a) ROI kalibrasyonu GEREKTIRMEZ (tasinabilir),
# (b) sartnamenin "model tabanli karar mekanizmasi" beklentisini karsilar.
KARANLIK_SORU = ("Makinenin on yuzeyindeki elektrik/kontrol panosu bolgesi "
                 "0 ile 10 arasinda ne kadar KARANLIK? Yalnizca sayiyi yaz "
                 "(0 = tamamen aydinlik duz yuzey, 10 = zifiri karanlik oyuk).")
KARANLIK_SECENEK = [str(i) for i in range(11)]
KARANLIK_ESIK = 3          # >= bu deger -> kapak ACIK
# NOT: cekimserlige davet eden cumle YOK — olculdu, MCC'yi +0,885'ten +0,000'a dusuruyor.
VLM_SISTEM = ("Sen bir endustriyel is guvenligi kamerasi analiz sistemisin. "
              "YALNIZCA GORDUGUNE dayan; varsayim yapma.")


def pano_acik_vlm(video_baytlari: bytes, istemci, esik: int = KARANLIK_ESIK,
                  roi_str: str = "") -> Optional[bool]:
    """VLM'e SAYISAL soru sorarak kapak acik mi? Cozulemezse None (K3).

    roi_str verilirse video o bolgeye kirpilmis olmalidir (cagiran taraf kirpar);
    bos ise TAM KARE gonderilir — olculdu, tam karede de calisiyor (MCC +0,817).
    """
    if not video_baytlari or istemci is None:
        return None
    try:
        o = istemci.video_oturumu(video_baytlari, system=VLM_SISTEM)
        if not o.hazir:
            return None
        c = o.sor(KARANLIK_SORU, guided_choice=KARANLIK_SECENEK,
                  temperature=0.0, max_tokens=8, hatirla=False)
    except Exception:
        return None
    try:
        return int((c or "").strip()) >= esik
    except (ValueError, TypeError):
        return None
