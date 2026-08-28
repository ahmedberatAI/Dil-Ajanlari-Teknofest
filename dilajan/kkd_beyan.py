"""KKD olaylari icin tesis-beyani kapisi (saf, modelsiz, fail-closed).

Bu modul goruntuden KKD tespiti yapmaz. Yalniz operatorun verdigi
``facility_policy`` / ``facility_rules`` metinleri ile ``ppe_detection`` +
``ppe_kits`` seciminden hangi KKD kalemlerinin bu tesiste acikca zorunlu
kilindigini cikarir. Desteklenen karar uzayi bilerek dardir: ``baret`` ve
``yelek``.

Modul ``dilajan.config`` veya agent state'e bagli degildir. Bu sayede istekler
arasinda durum sizdirmaz, API/model cagrisi yapmaz ve graph'a baglanmadan
modelsiz test edilebilir.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Iterable


DESTEKLENEN_KITLER = ("baret", "yelek")

_KIT_ALIASES = {
    "baret": (
        "baret", "baretsiz", "hardhat", "hard hat", "helmet", "kask",
    ),
    "yelek": (
        "yelek", "yeleg", "yeleksiz", "reflektif yelek", "guvenlik yelegi",
        "hi vis", "high visibility vest", "safety vest",
    ),
}

# Bunlar mevcut atomik KKD speki ve mevcut PPE kitleri tarafindan
# dogrulanamiyor. Desteklenen bir iddiayla birlesik gecseler bile tum iddia
# fail-closed reddedilir; aksi halde dogrulanmamis alt-iddia nesirde kalir.
_DESTEKLENMEYEN_ALIASES = {
    "eldiven": ("eldiven", "eldivensiz", "glove", "gloves"),
    "gozluk": (
        "gozluk", "gozlug", "gozluksuz", "goggle", "goggles", "safety glasses",
    ),
    "maske": ("maske", "maskesiz", "respirator", "face mask"),
    "kulak_koruyucu": (
        "kulaklik", "kulaklig", "kulak koruyucu", "earplug", "earmuff",
        "hearing protection",
    ),
    "emniyet_kemeri": (
        "emniyet kemeri", "guvenlik kemeri", "harness", "safety belt",
    ),
    "ayakkabi": (
        "is ayakkabisi", "koruyucu ayakkabi", "celik burun", "safety shoe",
        "safety boot",
    ),
    "yuz_siperi": ("yuz siperi", "yuz siper", "vizor", "face shield"),
}

_OLUMSUZ_BEYAN_RE = re.compile(
    r"(?:zorunlu|mecburi|gerekli)\s+(?:degil|degildir|olmayan)|"
    r"zorunlulugu\s+yok|gerekmez|gerekmiyor|aranmaz|istege\s+bagli|opsiyonel|"
    r"not\s+required|isn'?t\s+required|optional|no\s+requirement"
)

_ACIK_ZORUNLULUK_RE = re.compile(
    r"\b(?:zorunlu|zorunludur|mecburi|mecburidir|gereklidir|gerekli|gerekir|"
    r"sarttir|sart|"
    r"takmalidir|takilmali|takmali|kullanmalidir|kullanilmali|kullanmali|"
    r"required|must|shall)\b"
)

_POLITIKA_IHLAL_RE = re.compile(
    r"\b(?:baretsiz|yeleksiz)\b.{0,40}\b(?:calisma[a-z]*|giris[a-z]*|bulunma[a-z]*|"
    r"personel|ihlal|yasak[a-z]*)\b|"
    r"\b(?:baret|yelek)\b.{0,30}\b(?:eksikligi|eksik|takilmamasi|kullanilmamasi)\b"
)

_KURAL_IHLAL_RE = re.compile(
    r"\b(?:baretsiz|yeleksiz)\b.{0,40}\b(?:yasak[a-z]*|ihlal)\b|"
    r"\b(?:baret|yelek)\b.{0,30}\b(?:eksikligi|takilmamasi|kullanilmamasi)\b"
    r".{0,20}\b(?:yasak|ihlal)\b"
)

_EKIPMAN_KULLANIMI_YASAK_RE = re.compile(
    r"\b(?:baret|yelek)\b.{0,20}\b(?:takmak|takilmasi|kullanmak|kullanilmasi)\b"
    r".{0,15}\byasak\b"
)

_IHLAL_IDDIASI_RE = re.compile(
    r"\b(?:baretsiz|yeleksiz)\b|"
    r"\b(?:baret[a-z]{0,8}|yelek[a-z]{0,8}|yeleg[a-z]{0,8}|hardhat|hard\s+hat|"
    r"helmet|kask[a-z]{0,8}|safety\s+vest)\b"
    r".{0,35}\b(?:eksik|yok|takmiyor|kullanmiyor|giymiyor|takmamasi|"
    r"takilmamasi|kullanmamasi|giymemesi|olmadan|takilmadan|kullanmadan|"
    r"giymeden|yerine|without|missing)\b|"
    r"\b(?:eksik|without|missing|no)\b.{0,25}"
    r"\b(?:baret|yelek|hardhat|hard\s+hat|helmet|safety\s+vest)\b|"
    r"\b(?:kkd|ppe|kisisel\s+koruyucu)\b.{0,20}\b(?:eksik|ihlali|ihlal)\b"
)

_IHLAL_YOK_RE = re.compile(
    r"\b(?:kkd|ppe)\b.{0,15}\b(?:tam|uygun)\b|"
    r"\b(?:baret[a-z]{0,8}|yelek[a-z]{0,8}|yeleg[a-z]{0,8})\b.{0,25}"
    r"\b(?:eksik\s+degil|takili|mevcut|takiyor|var)\b"
)

_ACIK_YOKLUK_RE = re.compile(
    r"\b(?:baretsiz|yeleksiz)\b|\b(?:eksik|yok|takmiyor|kullanmiyor|giymiyor|"
    r"takmamasi|takilmamasi|kullanmamasi|giymemesi|olmadan|takilmadan|"
    r"kullanmadan|giymeden|yerine|without|missing)\b"
)

_ACIK_OLUMSUZ_IDDIA_RE = re.compile(
    r"\b(?:eksik|yok|takmiyor|kullanmiyor|giymiyor)\s+(?:degil|degildir)\b|"
    r"\b(?:no|without|missing)\s+(?:violation|issue)\b"
)


def _norm(text: str) -> str:
    """Turkceyi ASCII karar uzayina katlar ve bosluklari kararlilastirir."""
    value = (text or "").translate(str.maketrans({
        "ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G",
        "ü": "u", "Ü": "U", "ö": "o", "Ö": "O", "ç": "c", "Ç": "C",
    }))
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
    value = re.sub(r"[^a-z0-9|]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _clauses(text: str) -> Iterable[str]:
    # Virgul de sinirdir: "baret zorunlu, yelek zorunlu degil" cumlesinde
    # yelek olumsuzlugunun bareti yanlislikla ezmesini onler. Liste seklindeki
    # "baret, yelek zorunlu" ifadesinde baretin dusmesi bilincli fail-closed'dur.
    for raw in re.split(r"[\r\n.;,!?]+", text or ""):
        clause = _norm(raw)
        if clause:
            yield clause


def _contains_alias(text: str, aliases: Iterable[str]) -> bool:
    # Turkce ekleri ve yumusamayi kapsa: "bareti", "baretli", "yelegi".
    # Sol sinir tam tutulur; boylece baska bir kelimenin icinde rastlanti olmaz.
    return any(bool(re.search(
        rf"(?<![a-z0-9]){re.escape(_norm(alias))}[a-z]{{0,8}}(?![a-z0-9])", text))
        for alias in aliases)


def _kit_mentions(text: str) -> set[str]:
    norm = _norm(text)
    return {
        kit for kit, aliases in _KIT_ALIASES.items()
        if _contains_alias(norm, aliases)
    }


def _unsupported_mentions(text: str) -> set[str]:
    norm = _norm(text)
    return {
        kit for kit, aliases in _DESTEKLENMEYEN_ALIASES.items()
        if _contains_alias(norm, aliases)
    }


@dataclass(frozen=True)
class KkdBeyan:
    """Tesis girdilerinden cikarilan denetlenebilir KKD beyani."""

    kitler: tuple[str, ...]
    kaynaklar: tuple[str, ...]
    olumsuzlanan_kitler: tuple[str, ...] = ()
    atlanan_ppe_kitleri: tuple[str, ...] = ()

    def iz_satiri(self) -> str:
        kit = ",".join(self.kitler) or "YOK"
        kaynak = ",".join(self.kaynaklar) or "YOK"
        olumsuz = ",".join(self.olumsuzlanan_kitler) or "YOK"
        atlanan = ",".join(self.atlanan_ppe_kitleri) or "YOK"
        return (f"KKD_BEYANI[kit={kit}; kaynak={kaynak}; "
                f"olumsuz={olumsuz}; atlanan={atlanan}]")


@dataclass(frozen=True)
class KkdIddiaKarari:
    """Bir serbest-metin KKD iddiasinin beyan kapisi sonucu."""

    izinli: bool
    hukum: str
    iddia_kitleri: tuple[str, ...]
    desteklenmeyen_kitler: tuple[str, ...]
    eksik_beyanlar: tuple[str, ...]
    beyan: KkdBeyan

    def iz_satiri(self) -> str:
        iddia = ",".join(self.iddia_kitleri) or "YOK"
        desteklenmeyen = ",".join(self.desteklenmeyen_kitler) or "YOK"
        eksik = ",".join(self.eksik_beyanlar) or "YOK"
        return (f"KKD_{self.hukum}[iddia={iddia}; desteklenmeyen={desteklenmeyen}; "
                f"eksik_beyan={eksik}; beyanli={','.join(self.beyan.kitler) or 'YOK'}]")


def _metin_beyanlari(text: str, kaynak: str, *, politika: bool) -> tuple[set[str], set[str], list[str]]:
    olumlu: set[str] = set()
    olumsuz: set[str] = set()
    izler: list[str] = []
    for no, clause in enumerate(_clauses(text), start=1):
        for kit, aliases in _KIT_ALIASES.items():
            if not _contains_alias(clause, aliases):
                continue
            negatif = bool(_OLUMSUZ_BEYAN_RE.search(clause))
            # "baret takmak yasak" baret zorunlulugu degildir. Buna karsilik
            # "baretsiz calisma yasak" pozitif ihlal kalibidir.
            if _EKIPMAN_KULLANIMI_YASAK_RE.search(clause):
                negatif = True
            if negatif:
                olumsuz.add(kit)
                izler.append(f"{kaynak}:{no}:{kit}:OLUMSUZ")
                continue
            acik_zorunluluk = bool(_ACIK_ZORUNLULUK_RE.search(clause))
            ihlal = bool((_POLITIKA_IHLAL_RE if politika else _KURAL_IHLAL_RE).search(clause))
            if acik_zorunluluk or ihlal:
                olumlu.add(kit)
                izler.append(f"{kaynak}:{no}:{kit}:ZORUNLU")
    return olumlu, olumsuz, izler


def beyanlari_cikar(
    facility_policy: str = "",
    facility_rules: str = "",
    ppe_detection: bool = False,
    ppe_kits: str = "",
) -> KkdBeyan:
    """Yalniz acikca zorunlu kilinan baret/yelek beyanlarini cikarir.

    Olumsuz bir tesis beyani, baska bir kaynakta pozitif veya etkin kit olsa
    dahi ayni ekipman icin baskindir. Celiski halinde alarm yetkisi vermemek
    fail-closed davranistir.
    """
    p_olumlu, p_olumsuz, p_iz = _metin_beyanlari(
        facility_policy, "facility_policy", politika=True)
    r_olumlu, r_olumsuz, r_iz = _metin_beyanlari(
        facility_rules, "facility_rules", politika=False)

    olumlu = p_olumlu | r_olumlu
    olumsuz = p_olumsuz | r_olumsuz
    kaynaklar = p_iz + r_iz
    atlanan: set[str] = set()

    if ppe_detection:
        for raw in (ppe_kits or "").split(","):
            token = _norm(raw)
            if not token:
                continue
            eslesen = _kit_mentions(token)
            if eslesen:
                for kit in sorted(eslesen):
                    olumlu.add(kit)
                    kaynaklar.append(f"ppe_detection:{kit}:ZORUNLU")
            else:
                atlanan.add(token.replace(" ", "_"))

    son = olumlu - olumsuz
    # Yalniz son karara katkisi olan pozitif kaynaklari ve butun olumsuzluklari
    # tut. Boylece iz "baret zorunlu" deyip kit listesini bos gostermiyor.
    temiz_iz = []
    for iz in kaynaklar:
        parca = iz.split(":")
        kit = parca[-2] if len(parca) >= 2 else ""
        if iz.endswith(":OLUMSUZ") or kit in son:
            temiz_iz.append(iz)
    return KkdBeyan(
        kitler=tuple(sorted(son)),
        kaynaklar=tuple(temiz_iz),
        olumsuzlanan_kitler=tuple(sorted(olumsuz)),
        atlanan_ppe_kitleri=tuple(sorted(atlanan)),
    )


def iddia_karari(
    iddia: str,
    *,
    facility_policy: str = "",
    facility_rules: str = "",
    ppe_detection: bool = False,
    ppe_kits: str = "",
) -> KkdIddiaKarari:
    """Bir KKD ihlal iddiasini tesis beyanina baglar.

    Bu karar gorsel dogrulamanin yerine gecmez. ``izinli=True`` yalnizca
    iddianin atomik gorsel kanit kapisina sunulabilecegi anlamina gelir.
    """
    beyan = beyanlari_cikar(
        facility_policy=facility_policy,
        facility_rules=facility_rules,
        ppe_detection=ppe_detection,
        ppe_kits=ppe_kits,
    )
    iddia_kitleri = _kit_mentions(iddia)
    desteklenmeyen = _unsupported_mentions(iddia)

    if desteklenmeyen:
        return KkdIddiaKarari(
            False, "DESTEKLENMEYEN_KIT", tuple(sorted(iddia_kitleri)),
            tuple(sorted(desteklenmeyen)), (), beyan)
    if not iddia_kitleri:
        return KkdIddiaKarari(False, "IDDIA_KITI_YOK", (), (), (), beyan)

    norm = _norm(iddia)
    # Acik ihlal kalibi yoksa "baret takiyor" gibi uyumlu gozlem alarm olamaz.
    # Hem olumlu hem olumsuz gorunum varsa da yorum yapmayip fail-closed kal.
    ihlal_var = bool(_IHLAL_IDDIASI_RE.search(norm))
    uyumlu_ifade = bool(_IHLAL_YOK_RE.search(norm))
    acik_yokluk = bool(_ACIK_YOKLUK_RE.search(norm))
    acik_olumsuz = bool(_ACIK_OLUMSUZ_IDDIA_RE.search(norm))
    if acik_olumsuz or not ihlal_var or (uyumlu_ifade and not acik_yokluk):
        return KkdIddiaKarari(
            False, "IHLAL_IDDIASI_YOK", tuple(sorted(iddia_kitleri)), (), (), beyan)

    eksik = iddia_kitleri - set(beyan.kitler)
    if eksik:
        return KkdIddiaKarari(
            False, "BEYAN_YOK", tuple(sorted(iddia_kitleri)), (),
            tuple(sorted(eksik)), beyan)
    return KkdIddiaKarari(
        True, "BEYANLI", tuple(sorted(iddia_kitleri)), (), (), beyan)


__all__ = [
    "DESTEKLENEN_KITLER",
    "KkdBeyan",
    "KkdIddiaKarari",
    "beyanlari_cikar",
    "iddia_karari",
]
