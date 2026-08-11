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

import functools
import re
from typing import Dict, List, Optional, Sequence, Set, Tuple

# kategori -> (beklenen anahtar kelimeler, anomali_mi)
#
# !!! D28 UYARISI — BU SOZLUK KASITLI OLARAK DONDURULMUSTUR !!!
# Bu liste ESKI (gevsek) eslestiricinin girdisidir ve arsivlenmis olcumlerin YENIDEN
# URETILEBILIR kalmasi icin DEGISTIRILMEZ (K2/K4). Sikilastirilmis yeni liste asagida
# CATEGORY_PATTERNS'tedir. Iki liste BILEREK yan yana durur: rescore.py ikisini de
# calistirip sonuclari yan yana basar, boylece "metrigi kendimize gore ayarladik"
# itirazi sayilarla cevaplanabilir.
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


# ===========================================================================
# D28 — ESLESTIRICI ONARIMI  (Turkce-guvenli + kelime sinirli + olumsuzlama kapili)
# ===========================================================================
# NEDEN: eski kural `anahtar in metin.lower()` idi. Uc ayri kusuru vardi:
#   1) Python'un .lower()'i Turkce degildir: "İstismar".lower() -> "i̇stismar"
#      (i + U+0307 BIRLESIK NOKTA) ve "istismar" anahtariyla ESLESMEZ.
#      "I".lower() -> "i" olur, oysa Turkce'de "ı" olmalidir.
#   2) Ciplak alt-dizge kelime ortasini da yakalar: "kırmızı" -> "kır" (Burglary+
#      Vandalism), "vurgulanmadı" -> "vur" (Assault), "yüksek" -> "yük" (Anomali).
#      Olculen sonuc: klip basina ~3 YANLIS kategori tetikleniyordu.
#   3) Olumsuzlama gorulmuyordu: "kaza belirtisi YOK" kaza SAYILIYORDU.
#
# TASARIM: kok + KELIME SINIRI + gecerli Turkce EK ZINCIRI. "düş" -> "düştü",
# "düşerek", "düşmüş" ESLESIR; "düşük", "düşünce" ESLESMEZ. Ek zinciri bir mini
# bicimbirim cozumleyicisidir (asagidaki _EKLER); cozulemeyen kalinti REDDEDILIR.

#: Turkce metinlerde kelime govdesi sayilan karakterler icin isalnum() kullanilir.
#: Kok ile kelime arasindaki azami bosluk (cok kelimeli kaliplarda, karakter).
MAX_KALIP_ARA = 24
#: Kok sonrasi cozumlenecek azami ek uzunlugu (patolojik birlesikleri eler).
MAX_EK_UZUNLUK = 14

#: Kok'ten SONRA gelebilecek gecerli Turkce ekler. Zincirlenebilirler
#: ("düş"+"me"+"si", "kaza"+"sı"+"nda"). Liste BILEREK eksiktir: "-ık/-ik/-uk/-ük"
#: (düş->düşük, kır->kırık) ve yalin "-ın/-in/-un/-ün" (düş->düşün...) DISARIDA
#: birakilmistir, cunku bunlar ANLAM DEGISTIREN turetimlerdir.
_EKLER: Tuple[str, ...] = (
    # --- fiil zaman/kip ekleri ---
    "dı", "di", "du", "dü", "tı", "ti", "tu", "tü",
    "mış", "miş", "muş", "müş",
    "yor",
    "acak", "ecek", "acağ", "eceğ",
    "ar", "er", "ır", "ir", "ur", "ür",
    # --- mastar / isim-fiil / olumsuzluk / surerlik ---
    "mak", "mek", "ma", "me", "makta", "mekte",
    # --- sifat-fiil / zarf-fiil ---
    "an", "en", "yan", "yen", "arak", "erek", "ıp", "ip", "up", "üp", "ken",
    # --- cati ekleri ---
    "ıl", "il", "ul", "ül", "ış", "iş", "uş", "üş",
    "dır", "dir", "dur", "dür", "tır", "tir", "tur", "tür",
    "lan", "len",
    # --- isim cekim ekleri ---
    "lar", "ler", "sı", "si", "su", "sü", "nın", "nin", "nun", "nün",
    "da", "de", "ta", "te", "dan", "den", "tan", "ten",
    "na", "ne", "nda", "nde", "ndan", "nden", "nı", "ni", "nu", "nü",
    "ya", "ye", "a", "e", "yı", "yi", "yu", "yü", "ı", "i", "u", "ü",
    "yla", "yle", "la", "le",
    # --- sik yapim ekleri ---
    "lı", "li", "lu", "lü", "sız", "siz", "suz", "süz",
    "lık", "lik", "luk", "lük", "cı", "ci", "cu", "cü", "çı", "çi", "çu", "çü",
    "gan", "gen", "ğı", "ği", "ğu", "ğü",
)

#: Ek zinciri cozumleyicisinin YINE DE gecirdigi bilinen yanlis govdeler.
#: Or. "düş"+"ünüyor" = "ü"+"nü"+"yor" olarak COZULUR ama "düşünüyor" bir DUSME degildir.
#: Bunlar el ile, gerekce yazilarak kapatilir (testleri: tests/test_rescore.py).
KOK_ISTISNA: Dict[str, Tuple[str, ...]] = {
    "düş": ("ün", "ük"),      # düşünce/düşünüyor/düşük  != dusme
    "vur": ("gu",),           # vurgu/vurgulanmadı       != vurma
    "kır": ("mızı", "mız"),   # kırmızı                  != kirma
    "yan": ("ın", "lış", "ıt", "sıra", "aş"),  # yanında/yanlış/yanıt != yanma
    "ateş": ("kes",),         # ateşkes                  != ates
}

#: Kategori -> SIKILASTIRILMIS kalip listesi (D28). Tek kelime = kok (ek zinciriyle
#: eslesir); bosluk iceren giris = SIRALI cok-kelimeli kalip (aradaki bosluk
#: MAX_KALIP_ARA karakteri gecemez, cumlecik disina TASAMAZ).
#:
#: TASARIM KURALI — BU LISTE, CATEGORY_EXPECT'IN SIKI BIR ARITIMIDIR (strict refinement):
#: her ozgun anahtar ya AYNEN korunur, ya da OLCULEN bir yanlis-tetigi oldugu icin
#: cok-kelimeli kalibla degistirilir. Ozgun bir anahtari "sezgiyle" ATMAK YASAKTIR —
#: aksi halde skor dususu eslestirici duzeltmesinden mi kelime dagarcigi kaybindan mi
#: geldigi ayirt edilemez. (Ilk taslakta "duman" Explosion'dan dusurulmustu; bu bir
#: HATAYDI ve olculdugu anda geri alindi.)
#:
#: DARALTILAN KOKLER ve HER BIRININ OLCULEN GEREKCESI:
#:   "kır"   (Burglary)  -> "kilidi/kapıyı/camı kır" : "kırmızı sıvı" Burglary tetikliyordu
#:                          (Vandalism'de KALDI: kelime-siniri "kırmızı"yi zaten eliyor)
#:   "giriş" (Burglary)  -> "yetkisiz/izinsiz giriş", "girmeye çalış", "giriş denemesi"
#:                          : "kapıdan giriş yapan personel" Burglary tetikliyordu
#:   "yol"   (Anomali)   -> "yürüyüş yolu", "yaya yolu", "yaya geçidi", "yol ihlal"
#:   "geç"   (Anomali)   -> "yaya geçidi", "geçiş ihlal" : "geçiyor" her klipte var
#:   "açık"  (Anomali)   -> "kapak açık", "açık pano", "pano kapağı"
#:   "risk"  (Anomali)   -> "devrilme riski", "güvenlik riski" : "yüksek risk" her yerde
#:   "yük"   (Anomali)   -> "aşırı yük", "yük taşı" : "YÜKsek" alt-dizgesini yakaliyordu
#:   "tehlike"(Anomali)  -> "tehlikeli davranış", "tehlike arz"
#:   "müdahale"(Anomali) -> "yetkisiz müdahale" : saglik/guvenlik mudahalesi her klipte
#:   "araç"  (RoadAcc.)  -> "araç çarp", "araca çarp" : her CCTV'de arac var
#:   "trafik"(RoadAcc.)  -> "trafik kaza"           : "trafik akışı normal" tetikliyordu
#:   "yan"   (Fire)      -> "yanıyor/yandı/yanan/yanma" : "kapının YANında" tetikliyordu
#:   "is"    (Smoke)     -> ATILDI : iki harflik kok, ek zinciriyle her kelimeye uyuyor
#: Geri kalan TUM ozgun anahtarlar ("düş", "vur", "ateş", "şiddet", "kavga", "yere", ...)
#: AYNEN durur — onlarin yanlis tetikleri kelime-siniri + olumsuzlama kapisiyla cozulur.
CATEGORY_PATTERNS: Dict[str, List[str]] = {
    "RoadAccidents": ["kaza", "çarpış", "çarpma", "devril", "araç çarp", "araca çarp",
                      "kişiye çarp", "trafik kaza", "ezil", "takla at"],
    "Explosion": ["patla", "duman", "yangın", "alev", "parlama", "infilak", "şok dalgası"],
    "Fighting": ["kavga", "dövüş", "saldır", "şiddet", "itiş", "boğuş", "arbede",
                 "yumruk", "tekme"],
    "Assault": ["saldır", "darp", "şiddet", "kavga", "vur", "yumruk", "tekme",
                "bıçakla", "sopayla"],
    "Abuse": ["istismar", "şiddet", "darp", "saldır", "taciz", "kötü muamele", "eziyet"],
    "Burglary": ["hırsız", "soygun", "yetkisiz", "çaldı", "çalın", "çalarak", "çalma",
                 "yetkisiz giriş", "izinsiz giriş", "zorla gir", "gizlice gir",
                 "girmeye çalış", "giriş denemesi", "kilidi kır", "kapıyı kır",
                 "camı kır", "kasa"],
    "Shooting": ["silah", "ateş", "vur", "çatış", "kurşun", "namlu", "tabanca", "tüfek",
                 "ateş aç"],
    "Vandalism": ["vandal", "tahrip", "tahrib", "zarar", "kır", "parçala", "kundak",
                  "duvara yaz"],
    "Fire": ["yangın", "alev", "ateş", "tutuş", "yanıyor", "yandı", "yanan", "yanma"],
    "Smoke": ["duman", "yangın", "tüt", "dumanlan"],
    "Fall": ["düş", "yere", "hareketsiz", "yığıl", "bayıl", "yatıyor", "yatan",
             "kalkamı", "yere serildi", "yerde kalmış"],
    "Anomali": ["ihlal", "yetkisiz", "güvensiz", "forklift", "istif", "panel", "pano",
                "aşırı yük", "yük taşı", "kapak açık", "açık pano", "pano kapağı",
                "elektrik panosu", "yürüyüş yolu", "yaya yolu", "yaya geçidi",
                "yol ihlal", "geçiş ihlal", "tehlikeli davranış", "tehlike arz",
                "devrilme riski", "güvenlik riski", "yetkisiz müdahale",
                "koruyucu ekipman", "baret", "iş güvenliği"],
    "Normal": [],
}

#: SEMANTIK GRUPLAR — arXiv 2511.07171 (Ovis-8B, UCF-Crime %65.31 -> %81.0, EGITIM YOK).
#: Fikir: "Fighting" yerine "Assault" demek OPERATOR ICIN AYNI MUDAHALEYI dogurur
#: (guvenlik ekibi sevk); ceza hukuku ayrimi kamera goruntusunden zaten cikarilamaz.
#: Grup duzeyi eslesme bu ayrimi TOLERE eder, ama "Fighting" yerine "Fire" demeyi ETMEZ.
#: CATEGORY_EXPECT anahtarlari SILINMEDI — gruplar onlarin USTUNE binen bir katmandir.
SEMANTIC_GROUPS: Dict[str, List[str]] = {
    "Siddet": ["Fighting", "Assault", "Abuse"],
    "MalSuclari": ["Burglary", "Vandalism"],
    "Yikim": ["Explosion", "Fire", "Smoke"],
    "Trafik": ["RoadAccidents"],
    "Silahli": ["Shooting"],
    "Dusme": ["Fall"],
}

#: OLUMSUZLAMA kapisi. BILEREK DARDIR: yalnizca VARLIK/GOZLEM fiillerinin olumsuzu
#: sayilir. "durdurulamadı" / "engellenemedi" gibi BASKA fiillerin olumsuzu olayi
#: IPTAL ETMEZ (yanlis eleme, yanlis kabulden daha kotudur — gorev sarti).
_OLUMSUZ_RE = re.compile(
    r"\byok(?:tur)?\b"
    r"|\bdeğil(?:dir)?\b"
    r"|\bmevcut\s+değil"
    r"|\bhiçbir\s+\w+\s+yok"
    r"|(?:gözlen|görül|gör|tespit\s+edil|sapt|izlen|bulun|rastlan|oluş|yaşan|gel|"
    r"belirlen|algılan|fark\s+edil|içer|göster|ol)"
    r"m[ae](?:dı|di|mış|miş|z|makta|mekte|maktadır|mektedir)"
    r"|(?:gözle|görül|bulun|içer|göster|izlen)m[ıiuü]yor"
)

#: Cumlecik ayiraclari — olumsuzlama YALNIZ kendi cumleciginde gecerlidir.
#: Boylece "yere düşen kişi hareketsiz, tepki vermiyor" cumlesinde "vermiyor"
#: ilk cumlecikteki "düş"u IPTAL ETMEZ.
_AYIRAC_RE = re.compile(r"[.!?;:\n,]|\s+(?:ve|ile|ancak|fakat|ama|çünkü|ayrıca|oysa)\s+")


def tr_lower(s: str) -> str:
    """TURKCE-GUVENLI kucuk harf.

    Python'un str.lower()'i Turkce degildir:
        "İstismar".lower() -> "i̇stismar"  (i + U+0307 BIRLESIK NOKTA)  -> "istismar" ile ESLESMEZ
        "Itfaiye".lower()  -> "itfaiye"    (dogrusu "ıtfaiye")
    Cozum: once "I"->"ı" ve "İ"->"i" cevrilir, SONRA lower() cagrilir. Son adimda
    baska bir yerde .lower() gecmis metinlerde kalmis olabilecek U+0307 temizlenir.
    """
    if not s:
        return ""
    return s.replace("I", "ı").replace("İ", "i").lower().replace("\u0307", "")


@functools.lru_cache(maxsize=8192)
def _ek_zinciri_gecerli(kalan: str) -> bool:
    """Kok sonrasi kalinti GECERLI Turkce ek zinciri olarak cozulebiliyor mu?

    Bos kalinti (tam kelime) her zaman gecerlidir. Cozulemeyen kalinti kokun
    BASKA bir kelimenin icinde kaldigini gosterir ("kır"+"mızı", "vur"+"gulanmadı").
    """
    if not kalan:
        return True
    if len(kalan) > MAX_EK_UZUNLUK:
        return False
    for ek in _EKLER:
        if kalan.startswith(ek) and _ek_zinciri_gecerli(kalan[len(ek):]):
            return True
    return False


def _kok_konumlari(metin: str, kok: str) -> List[Tuple[int, int]]:
    """kok'un metinde KELIME BASINDA gectigi ve gecerli ekle bittigi (bas, son) konumlari."""
    out: List[Tuple[int, int]] = []
    if not kok:
        return out
    istisna = KOK_ISTISNA.get(kok, ())
    ara = 0
    while True:
        i = metin.find(kok, ara)
        if i < 0:
            return out
        ara = i + 1
        if i > 0 and metin[i - 1].isalnum():
            continue                       # kelime ORTASI — sayilmaz ("savur" icinde "vur")
        j = i + len(kok)
        k = j
        while k < len(metin) and metin[k].isalnum():
            k += 1
        kalan = metin[j:k]
        if istisna and any(kalan.startswith(x) for x in istisna):
            continue                       # bilinen yanlis govde
        if _ek_zinciri_gecerli(kalan):
            out.append((i, k))


def _kalip_konumlari(metin: str, kalip: str) -> List[Tuple[int, int]]:
    """Tek-kelimelik kok veya SIRALI cok-kelimeli kalip icin eslesme konumlari."""
    parcalar = kalip.split()
    if len(parcalar) <= 1:
        return _kok_konumlari(metin, kalip)
    sonuc: List[Tuple[int, int]] = []
    for bas, son in _kok_konumlari(metin, parcalar[0]):
        imlec, tamam = son, True
        for p in parcalar[1:]:
            aday = [(s, e) for s, e in _kok_konumlari(metin, p)
                    if s >= imlec and s - imlec <= MAX_KALIP_ARA]
            if not aday:
                tamam = False
                break
            imlec = aday[0][1]
        if tamam:
            sonuc.append((bas, imlec))
    return sonuc


def _cumlecikler(metin: str) -> List[str]:
    """Metni cumleciklere boler (olumsuzlama kapisinin etki alani)."""
    return [c for c in _AYIRAC_RE.split(metin) if c and c.strip()]


def patterns_for(category: str) -> List[str]:
    """Kategori icin SIKILASTIRILMIS kalip listesi (D28)."""
    return list(CATEGORY_PATTERNS.get(category, []))


def group_of(category: str) -> Optional[str]:
    """Kategorinin semantik grup adi (grubu yoksa None)."""
    for grup, uyeler in SEMANTIC_GROUPS.items():
        if category in uyeler:
            return grup
    return None


def group_members(category: str) -> List[str]:
    """Kategoriyle AYNI semantik gruptaki kategoriler (grup yoksa kategorinin kendisi)."""
    grup = group_of(category)
    return list(SEMANTIC_GROUPS[grup]) if grup else [category]


def loose_match(text: str, category: str) -> bool:
    """ESKI (gevsek) kural: ciplak alt-dizge + Python .lower(). D28 ONCESI davranis.

    K4 — BU FONKSIYON KASITLI OLARAK KUSURLUDUR ve DUZELTILMEYECEKTIR: arsivlenmis
    olcumlerin birebir yeniden uretilebilmesi icin eski kuralin canli kaydidir.
    """
    if not text:
        return False
    kelimeler = keywords_for(category)
    if not kelimeler:
        return False
    t = text.lower()
    return any(k in t for k in kelimeler)


def match_category(text: str, category: str, *, negation: bool = True) -> bool:
    """YENI (sikilastirilmis) kural: Turkce-guvenli + kelime sinirli + olumsuzlama kapili."""
    if not text:
        return False
    kaliplar = patterns_for(category)
    if not kaliplar:
        return False
    for cumlecik in _cumlecikler(tr_lower(text)):
        for kalip in kaliplar:
            for _bas, son in _kalip_konumlari(cumlecik, tr_lower(kalip)):
                if negation and _OLUMSUZ_RE.search(cumlecik, son):
                    continue               # "kaza belirtisi YOK" -> sayilmaz
                return True
    return False


def group_match(text: str, category: str, *, negation: bool = True) -> bool:
    """SEMANTIK GRUP duzeyi eslesme: ayni gruptaki HERHANGI bir kategori eslesirse dogru."""
    return any(match_category(text, c, negation=negation) for c in group_members(category))


def _olcum_kategorileri() -> List[str]:
    """OZGULLUK sayiminda kullanilan kategoriler (Normal disinda, kalibi olan hepsi)."""
    return [c for c in CATEGORY_EXPECT if c != "Normal" and (CATEGORY_PATTERNS.get(c)
                                                             or CATEGORY_EXPECT[c][0])]


def matched_categories(text: str, *, mode: str = "strict") -> Set[str]:
    """Metnin TETIKLEDIGI tum kategoriler. mode: "loose" (eski) | "strict" (yeni).

    OZGULLUK olcumu icin: dogru kategori disindakiler YANLIS tetiktir.
    """
    fn = loose_match if mode == "loose" else match_category
    return {c for c in _olcum_kategorileri() if fn(text, c)}


def matched_groups(text: str) -> Set[str]:
    """Metnin tetikledigi SEMANTIK GRUPLAR (ozgullugun grup duzeyindeki karsiligi)."""
    out: Set[str] = set()
    for c in matched_categories(text, mode="strict"):
        out.add(group_of(c) or c)
    return out


def row_text(row: dict, *, with_summary: bool) -> List[str]:
    """Bir eval satirindan eslestirmeye girecek METIN PARCALARI.

    with_summary=False -> yalniz events[].event (D28 ONCESI kapsam)
    with_summary=True  -> events[].event + summary (sartname K3 cikti sozlesmesinin
                          operatorun OKUDUGU alani; adlandirma kazanci burada kaliyordu)
    """
    parcalar = [str(e.get("event") or "") for e in (row.get("events") or [])]
    if with_summary:
        parcalar.append(str(row.get("summary") or ""))
    return [p for p in parcalar if p]


def any_match(parts: Sequence[str], category: str, *, mode: str = "strict",
              group: bool = False) -> bool:
    """Metin parcalarindan HERHANGI biri kategoriyle (veya grubuyla) eslesiyor mu?"""
    if mode == "loose":
        return any(loose_match(p, category) for p in parts)
    fn = group_match if group else match_category
    return any(fn(p, category) for p in parts)
