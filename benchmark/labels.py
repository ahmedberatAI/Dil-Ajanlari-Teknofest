#!/usr/bin/env python
"""Klip-duzeyi ETIKET SOZLUGU — kategori -> (anahtar kelimeler, anomali_mi) + kaynak koken.

Tek kaynak-dogru (single source of truth): hem eval_clips.py hem build_ground_truth.py
hem de judge_independent.py ayni etiket tanimlarini buradan alir.

Bu modul KASITLI OLARAK hafiftir (yalniz stdlib) — dilajan.agent / torch / av ICE AKTARMAZ,
boylece GPU'suz ortamda da ithal edilebilir.

Etiket kaynagi: veri setleri kategori KLASORLERINE bolunmustur; klasor adi = sinif etiketi.
Bu, dataset yayincisinin etiketidir — bizim uydurmamiz degil (K7 durustluk sarti).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# kategori -> (beklenen anahtar kelimeler, anomali_mi)
CATEGORY_EXPECT: Dict[str, Tuple[List[str], bool]] = {
    "RoadAccidents": (["kaza", "çarpış", "araç", "trafik", "devril"], True),
    "Explosion": (["patlama", "duman", "yangın", "alev", "parlama"], True),
    "Fighting": (["kavga", "dövüş", "saldır", "şiddet", "itiş"], True),
    "Assault": (["saldır", "darp", "şiddet", "kavga", "vur"], True),
    "Abuse": (["istismar", "şiddet", "darp", "saldır", "taciz"], True),
    "Burglary": (["hırsız", "soygun", "yetkisiz", "kır", "giriş"], True),
    "Shooting": (["silah", "ateş", "vur", "çatış"], True),
    "Vandalism": (["vandal", "tahrip", "zarar", "kır"], True),
    # --- senaryo-uyumlu kategoriler (endustri/saha guvenligi) ---
    "Fire": (["yangın", "alev", "ateş", "yan", "tutuş"], True),
    "Smoke": (["duman", "is", "yangın", "tüt"], True),
    "Fall": (["düş", "yere", "hareketsiz", "yığıl", "bayıl", "yatıyor", "yatan", "kalkamı"], True),
    # --- hedef-domain (savunma/uretim tesisi) — data/eval_defense (K14) ---
    # Kaynak: Mendeley xjmtb22pff class0-3 = GUVENSIZ davranis (bkz. data/industrial/CLASSES.md).
    # Anahtar kelimeler dort guvensiz sinifi da kapsar: yurume-yolu ihlali, yetkisiz mudahale,
    # acik pano kapagi, forklift ile asiri yuk.
    "Anomali": ([
        "ihlal", "yetkisiz", "güvensiz", "tehlike", "risk",
        "forklift", "yük", "aşırı", "istif",
        "panel", "pano", "kapak", "açık",
        "yürüyüş", "yaya", "yol", "geç", "müdahale",
    ], True),
    "Normal": ([], False),
}

# Kategori -> hakemin/insanin okuyacagi TURKCE olgusal tanim (grounded judge icin, K11)
CATEGORY_TR: Dict[str, str] = {
    "RoadAccidents": "trafik kazasi / arac carpismasi veya devrilmesi",
    "Explosion": "patlama (alev topu, duman, sok dalgasi)",
    "Fighting": "iki veya daha fazla kisi arasinda kavga/dovus",
    "Assault": "bir kisiye fiziksel saldiri / darp",
    "Abuse": "bir kisiye yonelik istismar / siddet",
    "Burglary": "hirsizlik / yetkisiz giris-soygun",
    "Shooting": "silahli saldiri / ates acma",
    "Vandalism": "vandalizm / mala kasitli zarar verme",
    "Fire": "gorunur yangin / alev",
    "Smoke": "gorunur duman",
    "Fall": "bir kisinin yere dusmesi ve yerde hareketsiz kalmasi",
    "Anomali": ("uretim tesisinde GUVENSIZ davranis: guvenli yurume yolu ihlali, yetkisiz "
                "mudahale, acik pano kapagi veya forklift ile asiri yuk tasima"),
    "Normal": "OLAGAN faaliyet — kayda deger hicbir guvenlik olayi YOK",
}

# Anomali kliplerinde kabul edilebilir risk seviyeleri (tek bir 'dogru' seviye iddia ETMIYORUZ)
RISK_ACCEPT_ANOMALY = ["Yüksek", "Kritik"]
RISK_ACCEPT_NORMAL = ["Düşük"]

# Dizin oneki -> (kaynak dataset, lisans/not)  — koken seffafligi (K13/K7)
DATASET_ORIGIN: Dict[str, Dict[str, str]] = {
    "data/eval_big": {
        "dataset": "UCF-Crime (HF mirror: ertiaM/Anomaly_Detection_in_Surveillance_Videos)",
        "not": "gercek CCTV; cogunlukla 320x240 dusuk cozunurluk",
    },
    "data/eval": {
        "dataset": "UCF-Crime (data/eval_big'in ALT KUMESI — K9)",
        "not": "eval_big ile ayni dosyalar; MD5 dedup'ta elenir",
    },
    "data/eval_scenario/Fire": {
        "dataset": "FIRESENSE (posVideo*)",
        "not": "gercek yangin/alev videolari",
    },
    "data/eval_scenario/Fall": {
        "dataset": "GERCEK dusme videolari: GMDCSA-24 (Subject*_fall*, CC BY 4.0) "
                   "+ URFD cam1 (urfd_fall*, CC BY-NC-SA)",
        "not": "K8 GIDERILDI: sentetik lying*.mp4 (donmus PNG) karantinaya alindi, yerine "
               "olculmus gercek video kondu (3.8-14.4 sn, 15-30 fps, kare-arasi hareket "
               "0.40-3.06). scripts/build_scenario_eval.py donmus adayi otomatik REDDEDER. "
               "DIKKAT: klipler falls_real/ + falls_surveillance/ ile HARDLINK ayni dosyadir "
               "— ucu birlikte raporlanirsa CIFT SAYIM olur. URFD kolu CC BY-NC (ticari kullanim yok).",
    },
    "data/eval_scenario/_deprecated_frozen_fall": {
        "dataset": "Simuletic CCTV_Incident_Dataset (lying*) — SENTETIK, KARANTINADA",
        "not": "TEK PNG'nin ffmpeg -loop ile 3sn'ye sarilmasi; SIFIR hareket, video degil (K8). "
               "OLCUME ALINMAZ — yalnizca kusurun kaydi icin saklaniyor.",
    },
    "data/eval_scenario/Normal": {
        "dataset": "karisik: endustriyel (Mendeley xjmtb22pff) + UCF Normal",
        "not": "industrial/ ve eval_big/Normal ile birebir cakisir; dedup'ta elenir",
    },
    "data/eval_stress/Normal": {
        "dataset": "FIRESENSE negatif (testneg*)",
        "not": "yangin-benzeri ama yangin OLMAYAN sahneler (FP stres testi)",
    },
    "data/falls_real": {
        "dataset": "GMDCSA-24 (CC BY 4.0)",
        "not": "gercek dusme + ADL; frontal ev/webcam acisi",
    },
    "data/falls_surveillance": {
        "dataset": "URFD cam1 (CC BY-NC-SA, arastirma)",
        "not": "tavan/overhead gozetim acisi; dusmeler simule (acted)",
    },
    "data/e2_vehicle": {
        "dataset": "UCF-Crime RoadAccidents (HF mirror)",
        "not": "gercek CCTV arac kazalari",
    },
    "data/temporal": {
        "dataset": "KOMPOZIT (scripts/make_composite.py)",
        "not": "normal(15s)+olay(15s)+normal(15s); splice noktalari tasarim geregi KESIN bilinir",
    },
    "data/industrial": {
        "dataset": "Eskisehir endustriyel isyeri guvenligi (Mendeley xjmtb22pff, CC BY, 1080p)",
        "not": "klasor adlari class0..class7 SEMANTIK ETIKET DEGIL — GT'ye alinmaz (K14)",
    },
}


def origin_for(rel_path: str) -> Dict[str, str]:
    """Goreli yola gore en UZUN eslesen koken kaydini dondurur (bilinmiyorsa bos-benzeri)."""
    rel = rel_path.replace("\\", "/")
    best: Optional[str] = None
    for prefix in DATASET_ORIGIN:
        if rel.startswith(prefix + "/") and (best is None or len(prefix) > len(best)):
            best = prefix
    if best is None:
        return {"dataset": "bilinmiyor", "not": "koken kaydi yok"}
    return DATASET_ORIGIN[best]


def is_anomaly(category: str) -> bool:
    """Kategori anomali sinifina mi ait? (bilinmeyen kategori -> anomali varsayilir)"""
    return CATEGORY_EXPECT.get(category, ([], True))[1]


def keywords_for(category: str) -> List[str]:
    """Kategori icin beklenen Turkce anahtar kelimeler."""
    return list(CATEGORY_EXPECT.get(category, ([], True))[0])


def risk_accept(category: str) -> List[str]:
    """Kategori icin KABUL EDILEBILIR risk seviyeleri listesi."""
    return list(RISK_ACCEPT_ANOMALY if is_anomaly(category) else RISK_ACCEPT_NORMAL)


def describe(category: str) -> str:
    """Kategorinin Turkce olgusal tanimi (LLM-hakem promptunda kullanilir)."""
    return CATEGORY_TR.get(category, category)


def category_from_path(rel_path: str) -> Optional[str]:
    """Yol parcalarindan bilinen bir kategori adi cikarir (klasor adi = etiket).

    Or. "data/eval_big/Fighting/Fighting018_x264.mp4" -> "Fighting".
    Bilinen bir kategori yoksa None (uydurma etiket URETMEZ).
    """
    parts = rel_path.replace("\\", "/").split("/")
    for p in reversed(parts[:-1]):  # dosya adini atla, klasorlerde ara
        if p in CATEGORY_EXPECT:
            return p
    return None
