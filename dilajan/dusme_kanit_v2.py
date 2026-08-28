"""Kisi dusmesi/destek kaybi icin dort atomlu, fail-closed kanit kapisi.

Bu modul v13m gelistirme probunda olculen dort bagimsiz soruyu yeniden
kullanilabilir bir arayuzde toplar. Karar modeli veya serbest metin kullanmaz:
ayni kaynak video, sabit ozel-API rollerinde ve birbirinin cevabini hatirlamayan
kapali sorularla olculur. Yalniz dort atomun da acik destegi alarm adayina izin
verir.

Modul kendi basina boru hattina bagli degildir. Model indirmez, yerel ogrenilmis
cikarim calistirmaz ve yalniz kendisine verilen istemcinin ``video_oturumu`` ile
``gorev`` arayuzlerini kullanir.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Dict, Iterable, Mapping, Sequence


class DusmeHukmu(str, Enum):
    """Dort atomun deterministik birlesik hukmu."""

    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class DusmeAtomu:
    """Tek bir kapali kanit sorusu ve sabit API rolu."""

    ad: str
    gorev: str
    soru: str
    secenekler: tuple[str, ...]
    destek: frozenset[str]
    curutme: frozenset[str]


@dataclass
class DusmeKanitSonucu:
    """Saf karar ve API adaptorunun ortak, izlenebilir sonucu."""

    aile: str
    hukum: DusmeHukmu
    cevaplar: Dict[str, str]
    atom_hukumleri: Dict[str, DusmeHukmu]
    hatalar: Dict[str, str]

    @property
    def supported(self) -> bool:
        return self.hukum == DusmeHukmu.SUPPORTED

    @property
    def refuted(self) -> bool:
        return self.hukum == DusmeHukmu.REFUTED

    def iz_satiri(self) -> str:
        parcalar = [f"{ad}={self.cevaplar.get(ad, '')}:{hukum.value}"
                    for ad, hukum in self.atom_hukumleri.items()]
        parcalar.extend(f"{ad}=HATA:{hata}" for ad, hata in self.hatalar.items())
        return f"{self.aile}:{self.hukum.value}[{', '.join(parcalar)}]"


DUSME_AILESI = "kişi destek kaybı/düşme v2"
DUSME_MAX_TOKENS = 8

# Bu sabit yalniz sozlesmeyi belgeler. Modul model yaratmaz veya model adi secmez;
# istemcinin `gorev` yonlendirmesi bu alias'lari mevcut ozel API'ye baglar.
SABIT_MODEL_SOZLESMESI: Mapping[str, str] = MappingProxyType({
    "algi": "vlm",
    "olay": "llm-large",
    "yapi": "llm-fast",
    "ozet": "llm-fast",
})

DUSME_SISTEM = (
    "Sen bir video adli-kanıt ölçüm aracısın. Yalnız görüntüde doğrudan "
    "desteklenen fiziksel olguyu seç. Sahne türünden, niyetten, başlıktan veya "
    "olası senaryodan sonuç çıkarma. Aynı kişi, zaman sırası ya da fiziksel "
    "sonuç açık değilse belirsiz veya olumsuz seçeneği kullan. Açıklamasız "
    "yalnız izin verilen etiketi yaz."
)


def _atom(ad: str, gorev: str, soru: str,
          secenekler: Sequence[str] = ("A", "B", "C", "D"),
          destek: Iterable[str] = ("A",),
          curutme: Iterable[str] = ("B", "C")) -> DusmeAtomu:
    return DusmeAtomu(
        ad=ad,
        gorev=gorev,
        soru=soru,
        secenekler=tuple(secenekler),
        destek=frozenset(destek),
        curutme=frozenset(curutme),
    )


DUSME_ATOMLARI: tuple[DusmeAtomu, ...] = (
    _atom(
        "person", "algi",
        "Videoda olay boyunca izlenebilen gerçek bir kişi, bedeni ve destek/zemin "
        "ilişkisi seçilebilir biçimde görünüyor mu? A: Gerçek kişi ve bedeni yeterli "
        "açıklıkta görünür. B: Yalnız nesne, gölge, araç veya çok küçük/örtülü şekil. "
        "C: Kişi yok. D: Görüntü yetersiz. Açıklamasız yalnız A, B, C veya D yaz.",
    ),
    _atom(
        "transition", "olay",
        "Videoyu kronolojik izle. Aynı gerçek kişi destekli/dik konumdan istemsiz "
        "ve kontrolsüz biçimde aşağı hareket edip dengesini veya ayak desteğini "
        "kaybediyor mu? A: Kontrolsüz destek kaybı/düşey düşüş açık. B: Rutin eğilme, "
        "çömelme, yük kaldırma, planlı iniş, normal koşma/yürüme veya sahne kesimi. "
        "C: Böyle geçiş yok. D: Görüntü yetersiz. Açıklamasız yalnız A, B, C veya D yaz.",
    ),
    _atom(
        "outcome", "olay",
        "Videoyu kronolojik izle. Aynı kişinin kontrolsüz geçişi fiziksel bir sonuçla "
        "tamamlanıyor mu: bedeni zemine/sert yüzeye temas ediyor, kişi destekten asılı "
        "kalıyor veya düşme temasından sonra yeniden toparlanıyor mu? A: Aynı kişide "
        "düşme teması/asılma ve sonucu açık. B: Yalnız yürüme/koşma, rutin taşıma veya "
        "nesne düşürme; kişi düşmüyor. C: Farklı kişi/sahne ya da sonuç yok. "
        "D: Görüntü yetersiz. Açıklamasız yalnız A, B, C veya D yaz.",
    ),
    _atom(
        "continuous_chain", "olay",
        "Videonun tamamını kronolojik izle ve yalnız tek kesintisiz görsel zinciri "
        "değerlendir. A yalnız şu dört koşul birlikte açıksa seçilir: aynı gerçek kişi "
        "başlangıçta destekli/dik ve bedeni görünürdür; kişi istemsiz destek kaybıyla "
        "aşağı geçer; aynı kişinin bedeni daha aşağıda zemine/sert yüzeye temas eder "
        "veya kaybettiği destekten asılı kalır; bunlar sahne kesilmeden izlenir. "
        "A: Bu kesintisiz kişi-düşme/asılma zinciri açık. B: Başlangıçtan beri oturan, "
        "yerde veya örtülü kişi; rutin eğilme/çömelme; platformda yük taşıma; yalnız "
        "nesne hareketi; ya da önceden başlamış kalabalık müdahale var. C: Farklı "
        "kişi/sahne, kesinti veya tamamlanmış zincir yok. D: Görüntü bu ayrım için "
        "yetersiz. Açıklamasız yalnız A, B, C veya D yaz.",
    ),
)


def _temiz(deger: object) -> str:
    return str(deger or "").strip().upper()


def sonuclandir(cevaplar: Mapping[str, str],
                hatalar: Mapping[str, object] | None = None) -> DusmeKanitSonucu:
    """Dort atomu modelsiz ve deterministik olarak birlestir.

    Hata her zaman ``INSUFFICIENT``tir. Hata yoksa acik bir B/C cevabi curutme
    sayilir; yalniz dort A birlikte ``SUPPORTED`` olabilir. Eksik, D veya izin
    disi cevap ``INSUFFICIENT`` kalir.
    """

    norm = {atom.ad: _temiz(cevaplar.get(atom.ad, "")) for atom in DUSME_ATOMLARI}
    hata_metni = {str(ad): str(hata) for ad, hata in (hatalar or {}).items()}
    atom_hukumleri: Dict[str, DusmeHukmu] = {}
    for atom in DUSME_ATOMLARI:
        cevap = norm[atom.ad]
        if cevap in atom.curutme:
            atom_hukumleri[atom.ad] = DusmeHukmu.REFUTED
        elif cevap in atom.destek:
            atom_hukumleri[atom.ad] = DusmeHukmu.SUPPORTED
        else:
            atom_hukumleri[atom.ad] = DusmeHukmu.INSUFFICIENT

    if hata_metni:
        hukum = DusmeHukmu.INSUFFICIENT
    elif DusmeHukmu.REFUTED in atom_hukumleri.values():
        hukum = DusmeHukmu.REFUTED
    elif atom_hukumleri and all(
            deger == DusmeHukmu.SUPPORTED for deger in atom_hukumleri.values()):
        hukum = DusmeHukmu.SUPPORTED
    else:
        hukum = DusmeHukmu.INSUFFICIENT

    return DusmeKanitSonucu(
        aile=DUSME_AILESI,
        hukum=hukum,
        cevaplar=norm,
        atom_hukumleri=atom_hukumleri,
        hatalar=hata_metni,
    )


def dogrula_video(istemci, video: str | bytes) -> DusmeKanitSonucu:
    """Ayni kaynak videoyu sabit rollerde dort hafizasiz atomla olc.

    Bu adaptor istemci disinda model calistirmaz. Oturum kurma, rol secme,
    cevap alma veya oturumu geri yukleme hatalarinin tamami fail-closed olarak
    sonuca yazilir; istisna alarm kararina sizmaz.
    """

    try:
        oturum = istemci.video_oturumu(video, system=DUSME_SISTEM)
    except Exception as ex:  # pragma: no branch - ayri birim testi var
        return sonuclandir({}, {"oturum": f"{type(ex).__name__}: {ex}"})

    if oturum is None or not getattr(oturum, "hazir", False):
        hata = getattr(oturum, "hata", None) if oturum is not None else None
        return sonuclandir({}, {"oturum": hata or "kurulamadi"})

    cevaplar: Dict[str, str] = {}
    hatalar: Dict[str, str] = {}
    yok = object()
    asil_istemci = getattr(oturum, "istemci", yok)
    try:
        for atom in DUSME_ATOMLARI:
            try:
                oturum.istemci = istemci.gorev(atom.gorev)
                cevap = oturum.sor(
                    atom.soru,
                    guided_choice=atom.secenekler,
                    temperature=0.0,
                    max_tokens=DUSME_MAX_TOKENS,
                    hatirla=False,
                )
                if cevap is None:
                    hatalar[atom.ad] = getattr(oturum, "hata", None) or "cevap alinamadi"
                else:
                    cevaplar[atom.ad] = cevap
            except Exception as ex:
                hatalar[atom.ad] = f"{type(ex).__name__}: {ex}"
    finally:
        if asil_istemci is not yok:
            try:
                oturum.istemci = asil_istemci
            except Exception as ex:  # pragma: no cover - savunmaci adaptor yolu
                hatalar["oturum_geri_yukleme"] = f"{type(ex).__name__}: {ex}"

    return sonuclandir(cevaplar, hatalar)


__all__ = [
    "DUSME_AILESI",
    "DUSME_ATOMLARI",
    "DUSME_MAX_TOKENS",
    "DUSME_SISTEM",
    "SABIT_MODEL_SOZLESMESI",
    "DusmeAtomu",
    "DusmeHukmu",
    "DusmeKanitSonucu",
    "dogrula_video",
    "sonuclandir",
]
