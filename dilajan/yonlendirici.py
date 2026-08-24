# -*- coding: utf-8 -*-
"""D42 — MODEL-TABANLI yonlendirme (router alias, Qwen3-8B).

SARTNAME BAGI (docs/sartname_metni_2026.txt s.206-211):
  "sabit kurallara dayali basit bir pipeline yerine ... MODEL TABANLI KARAR
   MEKANIZMALARI iceren bir mimari" — "statik, yalnizca kural tabanli cozumler
   DUSUK PUANLANACAKTIR."

NE YAPAR: dogal dildeki bir operator sorusunu ya da klip betimlemesini dort
soru tipinden birine ayirir, sonra ON-KAYITLI bir tablo ile hedef alias'a esler.

  MODEL-TABANLI olan kisim : dogal dil -> soru_tipi  (belirsiz, kurala sigmaz)
  KURAL olan kisim         : soru_tipi -> hedef alias (denetlenebilir politika)

⚠️ DURUSTLUK SINIRI — BU KODUN IDDIA ETMEDIGI SEY:
  router alias'i **Qwen3-8B, YALNIZ METIN**. VIDEO GOREMEZ. Yonlendirme karari
  video ICERIGINE degil, SORU/BETIMLEME METNINE dayanir. "Router videoyu analiz
  edip model seciyor" ifadesi YANLIS olur. Klip betimlemesi girdi olarak
  verildiginde bile router, betimlemeyi URETEN modelin ciktisini okur — kendisi
  bir kare bile gormez.

K3 FAIL-OPEN: her hata yolu (ag, zaman asimi, beklenmedik cikti) `genel` +
`settings.model_name` ile doner ve `gerekce` alanina nedeni yazar. Yonlendirme
ASLA analizi durdurmaz; en kotu ihtimalle sistem D41 oncesindeki tek-model
davranisina duser.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence

from dilajan.config import settings

SINIFLAR: tuple = ("sayma", "kisi_oznitelik", "durum", "genel")

#: ON-KAYITLI ESLEME. Kaynak: kendi olcumlerimiz (D38-D41).
#:   sayma          -> llm-large : forklift sayma MCC +0,725 (llm-large en iyi)
#:   kisi_oznitelik -> vlm       : yelek MCC +0,500; llm-large 47/50 "GORUNMUYOR"
#:   durum          -> vlm       : OLCULMEDI, kisi_oznitelik ile ayni gerekce
#:   genel          -> llm-fast  : OLCULMEDI, dokumantasyon JSON/arac 1,000=1,000
HEDEF_ALIAS: Dict[str, str] = {
    "sayma": "llm-large",
    "kisi_oznitelik": "vlm",
    "durum": "vlm",
    "genel": "llm-fast",
}

#: Hedef yanit vermedigi (soyutlandigi) zaman denenecek IKINCI alias.
#: Bkz. `ikincil_alias` — soyutlanma-tetikli yeniden yonlendirme.
YEDEK_ALIAS: Dict[str, str] = {
    "sayma": "vlm",
    "kisi_oznitelik": "llm-large",
    "durum": "llm-large",
    "genel": "llm-large",
}

#: Hedefin "goremedim" dediginin isaretleri (kucuk harfe cevrilmis metinde aranir).
SOYUTLANMA = ("görünmüyor", "gorunmuyor", "bilinmiyor", "belirlenemedi",
              "seçilemiyor", "secilemiyor", "tespit edilemedi", "net değil")

SISTEM = (
    "Bir İSG video-analiz ajanının yönlendirme birimisin. Sana ya bir operatör "
    "sorusu ya da bir klip betimlemesi gelir. İşin, girdinin hangi soru tipine "
    "girdiğini belirlemek; soruyu yanıtlamak değil.\n"
    "Soru tipleri:\n"
    "- sayma: yanıtı bir SAYI, mesafe ya da geometrik karşılaştırma olan girdiler "
    "(kaç adet, kaç metre, yüksekliği aşıyor mu).\n"
    "- kisi_oznitelik: bir KİŞİNİN üzerindeki görünür donanım veya kıyafet "
    "(baret, yelek, eldiven, emniyet kemeri, yüz siperi, tulum).\n"
    "- durum: bir NESNENİN ya da ORTAMIN iki durumlu hâli (kapak açık/kapalı, "
    "ışık yanık/sönük, zemin ıslak/kuru, muhafaza yerinde/değil).\n"
    "- genel: özet, gerekçe, mevzuat, öneri, rapor ya da diyalog; tek bir görsel "
    "hedefi yoktur."
)


@dataclass
class Yonlendirme:
    """Bir yonlendirme karari + izlenebilirlik kunyesi."""
    soru_tipi: str
    hedef_alias: str
    gerekce: str = ""
    gecikme_s: float = 0.0
    kullanim: Optional[Dict[str, int]] = None
    model: str = ""
    yedege_dustu: bool = False

    def sozluk(self) -> dict:
        return {"soru_tipi": self.soru_tipi, "hedef_alias": self.hedef_alias,
                "gerekce": self.gerekce, "gecikme_s": round(self.gecikme_s, 3),
                "kullanim": self.kullanim, "model": self.model,
                "yedege_dustu": self.yedege_dustu}


# --- KURAL TABANLI TABAN CIZGISI (kontrol kolu; uretim yolu DEGIL) -----------
# Bunun VAR OLMA sebebi olcum durustlugu: model-tabanli yonlendiricinin bir
# if/else yiginindan GERCEKTEN daha iyi olup olmadigini gormeden "model tabanli"
# demek bos bir iddia olur. Ayrica router tamamen erisilemez oldugunda son care.
_RE_SAYMA = re.compile(r"\bkaç\b|\bkac\b|\bsayı\b|\bmetre\b|\badet\b|\btoplam\b|aşıyor|yüksekli", re.I)
_RE_KISI = re.compile(r"baret|kask|yelek|eldiven|emniyet kemeri|koşum|kosum|siper|tulum|ayakkab|maske|kulaklık", re.I)
_RE_DURUM = re.compile(r"kapağı|kapagi|kapalı|kapali|açık|acik|yanık|sönük|sonuk|ıslak|islak|muhafaza|kırık|kirik|birikinti|görünür durumda", re.I)


def kural_ile(metin: str) -> str:
    """Sozcuksel taban cizgisi. ONCELIK: sayma > kisi_oznitelik > durum > genel."""
    m = metin or ""
    if _RE_SAYMA.search(m):
        return "sayma"
    if _RE_KISI.search(m):
        return "kisi_oznitelik"
    if _RE_DURUM.search(m):
        return "durum"
    return "genel"


def yonlendir(metin: str, istemci=None, temperature: float = 0.0,
              max_tokens: int = 16) -> Yonlendirme:
    """Girdiyi siniflandirip hedef alias'i secer. HATA -> genel + varsayilan model.

    `istemci` verilmezse `VLMClient().gorev("yonlendirme")` kurulur (router alias).
    Kisitli kod cozme (`structured_outputs.choice`) ile cikti MUTLAKA 4 etiketten
    biridir; ayristirma hatasi YUZEY YOK.
    """
    t0 = time.perf_counter()
    try:
        if istemci is None:
            from dilajan.llm_client import VLMClient
            istemci = VLMClient().gorev("yonlendirme")
        ham = istemci.chat(
            [{"role": "system", "content": SISTEM},
             {"role": "user", "content": (metin or "").strip()}],
            temperature=temperature, max_tokens=max_tokens,
            guided_choice=SINIFLAR,
        )
        etiket = (ham or "").strip().strip('"').lower()
        gecikme = time.perf_counter() - t0
        if etiket not in HEDEF_ALIAS:
            # Kisitli cozme calismadiysa (bkz. D40 kusuru) kural tabanina duselim.
            etiket_k = kural_ile(metin)
            return Yonlendirme(etiket_k, HEDEF_ALIAS[etiket_k],
                               gerekce=f"kisitli cozme tutmadi (ham={ham!r}) -> kural tabani",
                               gecikme_s=gecikme, model=getattr(istemci, "model", ""),
                               kullanim=getattr(istemci, "son_kullanim", None),
                               yedege_dustu=True)
        return Yonlendirme(etiket, HEDEF_ALIAS[etiket], gerekce="router",
                           gecikme_s=gecikme, model=getattr(istemci, "model", ""),
                           kullanim=getattr(istemci, "son_kullanim", None))
    except Exception as exc:  # K3 FAIL-OPEN: yonlendirme analizi ASLA durdurmaz
        return Yonlendirme("genel", settings.model_name,
                           gerekce=f"FAIL-OPEN: {type(exc).__name__}: {exc}",
                           gecikme_s=time.perf_counter() - t0, yedege_dustu=True)


def alias_dogrula(adaylar: Optional[Sequence[str]] = None, istemci=None) -> Dict[str, bool]:
    """Alias adlarini servisin /v1/models listesiyle karsilastirir.

    ⚠️ NEDEN GEREKLI — D42'de OLCULDU (2026-08-24):
    Paylasilan servis **TANIMADIGI MODEL ADINI REDDETMIYOR**. Hata donmuyor;
    istegi kabul ediyor, yanitliyor ve `response.model` alaninda gonderdigimiz
    dizeyi AYNEN geri yaziyor -> yanit alani kimlik DOGRULAMAZ, yalnizca yankidir.
    Kimlik hata-imzasiyla tespit edildi: bilinmeyen alias'i **llm-fast** karsiliyor
    (36 maddelik sette imza 8/8 birebir esti).
    Alias'lar ayrica BUYUK/KUCUK HARFE DUYARLI: "ROUTER" != "router" ve "ROUTER"
    sessizce llm-fast'e dustu (yonlendirme dogrulugu 35/36 -> 28/36).

    ETKI: `DILAJAN_MODEL_*` icindeki bir yazim hatasi SESSIZ. Olcum "router ile"
    diye kaydedilirken baska bir model kosuyor olabilir. Bu, yalnizca yonlendirmeyi
    degil TUM D41 alias mimarisini ilgilendirir -> acilista bir kez cagrilmali.

    FAIL-OPEN: liste alinamazsa {} doner (dogrulama YAPILAMADI), akis durmaz.
    """
    if adaylar is None:
        adaylar = sorted({settings.model_name, *HEDEF_ALIAS.values(),
                          *YEDEK_ALIAS.values(),
                          settings.gorev_modeli("yonlendirme")})
    try:
        if istemci is None:
            from dilajan.llm_client import VLMClient
            istemci = VLMClient()
        bilinen = {m.id for m in istemci.client.models.list().data}
    except Exception:
        return {}
    return {a: (a in bilinen) for a in adaylar}  # buyuk/kucuk harf DUYARLI (bilerek)


def soyutlandi_mi(yanit: object) -> bool:
    """Hedef model 'goremedim' mi dedi? (yeniden yonlendirme tetikleyicisi)"""
    m = str(yanit or "").lower()
    return any(im in m for im in SOYUTLANMA)


def ikincil_alias(soru_tipi: str) -> str:
    """Hedef soyutlandiysa denenecek IKINCI alias.

    NEDEN: en pahali yonlendirme hatasi, kisi_oznitelik sorusunun llm-large'a
    gitmesidir — model 47/50 "GORUNMUYOR" der ve bu ISG'de KACIRMA (FN) demektir.
    Soyutlanma metinden ucuza saptanabildigi icin tek bir yeniden deneme,
    yanlis yonlendirmenin en agir sonucunu kaldirir.
    """
    return YEDEK_ALIAS.get(soru_tipi, settings.model_name)
