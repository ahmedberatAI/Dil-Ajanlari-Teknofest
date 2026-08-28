"""Endustriyel duman/plum icin cok-kanalli kanit ve akutluk hakemligi.

Bu modul ``yangin var mi?`` diye tek bir anlamsal soru sormaz. Ayni kaynak
videoda uc farkli fiziksel olcumu, sabit model rollerinde ve kapali cevap
uzayinda yapar:

* ``vlm``: gorunur, bir kaynaga bagli plum varligi,
* ``llm-large``: kaynaktan cikis + zamansal yukselme/yayilma,
* ``vlm``: duman opakligi ile parlak beyaz yogusma/buhar ayrimi,
* ``llm-large``: kalici aerosol ile hizla incelen yogusma ayrimi,
* ``vlm``: ayri akut yangin belirtisi (yalniz duman desteklendiyse).

Ilk iki API olcumu ile gozlem slotu yalniz kaynak-bagli plum on kosulunu kurar.
Plum, duman demek degildir: duman olayi icin optik ve zamansal madde
olcumlerinin IKISI de duman veya duman+buhar destegi vermelidir. Duman gozlemi
ile acil yangin ayri durumlardir; yalniz ayri akut kanit ``AKUT_YANGIN``
sonucunu acar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Mapping, Optional, Sequence


class DumanDuzeyi(str, Enum):
    YOK = "YOK"
    GOZLEM = "GOZLEM"
    AKUT_YANGIN = "AKUT_YANGIN"


SISTEM = (
    "Sen endustriyel kamera videosunda yalniz dogrudan gorunen fiziksel kaniti "
    "olcen adli bir goruntu aracisin. Madde turunu, tesis amacini veya tehlike "
    "niyetini varsayma. Zamani kronolojik karsilastir. Aciklamasiz yalniz izin "
    "verilen etiketi yaz."
)

GORSEL_SECENEKLER = (
    "KAYNAKTAN_CIKAN_PLUM",
    "ATMOSFERIK_BULUT_SIS",
    "KISA_TOZ_BUHAR",
    "SABIT_PARLAKLIK_GOLGE",
    "PLUM_YOK",
    "GORUNMUYOR",
)

GORSEL_SORU = (
    "Videoyu ilk andan son ana karsilastir. Bina, baca, boru, havalandirma, "
    "makine veya zemin gibi AYNI fiziksel noktadan en az birkac ardisik anda "
    "cikip sinirlari yumusak bicimde sekil degistiren/yukselen/yayilan gorunur "
    "bir plum var mi? Tum gokyuzuyla birlikte kayan atmosferik bulut/sis, tek "
    "anlik toz-buhar pufu, sabit beyaz-gri yuzey, parlaklik ve golge plum degildir. "
    "Renk tek basina karar degildir; beyaz bir endustriyel emisyon da plum olabilir. "
    "Yalniz KAYNAKTAN_CIKAN_PLUM, ATMOSFERIK_BULUT_SIS, KISA_TOZ_BUHAR, "
    "SABIT_PARLAKLIK_GOLGE, PLUM_YOK veya GORUNMUYOR yaz."
)

ZAMANSAL_SECENEKLER = (
    "ENDUSTRIYEL_KAYNAKLI_PLUM",
    "ATMOSFERLE_BIRLIKTE_HAREKET",
    "KISA_GECICI_SALIM",
    "SABIT_GORSEL_IZ",
    "PLUM_YOK",
    "GORUNMUYOR",
)

ZAMANSAL_SORU = (
    "Videoyu kronolojik bir zaman serisi olarak incele. Gorunur yumusak sinirli "
    "olusum, sabit bir endustriyel kaynaktan tekrar tekrar dogup kaynak noktasindan "
    "uzaklasirken bicim degistiriyor, yukseliyor veya ruzgarla yayiliyor mu? Maddeyi "
    "duman/buhar diye tahmin etme; burada yalniz KAYNAK-BAGLILIK ve ZAMANSAL "
    "DAVRANIS olculuyor. Atmosferle birlikte kayan bulut/sis, tek kisa puf/jet, "
    "sabit leke-golge-parlaklik ve olusum yoklugu ayridir. Yalniz "
    "ENDUSTRIYEL_KAYNAKLI_PLUM, ATMOSFERLE_BIRLIKTE_HAREKET, KISA_GECICI_SALIM, "
    "SABIT_GORSEL_IZ, PLUM_YOK veya GORUNMUYOR yaz."
)

OPTIK_SECENEKLER = (
    "DUMAN_OPAKLIGI",
    "DUMAN_BUHAR_KARISIMI",
    "PARLAK_BEYAZ_BUHAR",
    "DUMAN_IZI_YOK",
    "BELIRSIZ",
)

OPTIK_SORU = (
    "Bu soru plum varligini degil, EPA Method 9 benzeri GORUNUR MADDE ayrimini "
    "olcer. Kaynaktan itibaren arka plan kontrastini kalici azaltan gri, mavi-gri, "
    "kahverengi veya yari saydam bir aerosol tabakasi DUMAN_OPAKLIGI sayilir; "
    "duman dusuk opasiteli olabilir ve koyu olmak zorunda degildir. Parlak beyaz, "
    "yuvarlak/billowing yogusma bulutu tek basina dumana kanit degildir. Parlak "
    "beyaz buharla birlikte ondan ayri kalici gri/kahverengi/yari saydam aerosol "
    "bileseni acikca varsa DUMAN_BUHAR_KARISIMI yaz. Yalniz parlak beyaz yogusma "
    "bulutu varsa PARLAK_BEYAZ_BUHAR; duman izi yoksa DUMAN_IZI_YOK; goruntu bu "
    "ayrimi tasimiyorsa BELIRSIZ yaz. Kaynak turunu veya tesis bilgisini tahmin "
    "etme. Yalniz DUMAN_OPAKLIGI, DUMAN_BUHAR_KARISIMI, PARLAK_BEYAZ_BUHAR, "
    "DUMAN_IZI_YOK veya BELIRSIZ yaz."
)

DAGILIM_SECENEKLER = (
    "KALICI_DUMAN_AEROSOLU",
    "DUMAN_BUHAR_BIRLIKTE",
    "HIZLA_INCELEN_YOGUSMA",
    "DUMAN_IZI_YOK",
    "BELIRSIZ",
)

DAGILIM_SORU = (
    "Videoyu kronolojik inceleyerek DUMAN ile SU BUHARI/YOGUSMA arasindaki "
    "zamansal farki olc. Kaynakta veya hemen yaninda gorunup ruzgarla tasinirken "
    "arka plani ortmeye devam eden, sekil degistirse de bir aerosol izi olarak "
    "kalici kalan olusum KALICI_DUMAN_AEROSOLU'dur. Kaynaktan sonra parlak beyaz "
    "buluta donusen ve kisa mesafede hizla incelip kaybolan yogusma "
    "HIZLA_INCELEN_YOGUSMA'dir. Ayni videoda parlak beyaz yogusmadan ayri kalici "
    "aerosol bileseni de acikca suruyorsa DUMAN_BUHAR_BIRLIKTE yaz. Yalniz buyuk "
    "bir plumun varligini duman sayma; madde ayrimi gorunmuyorsa BELIRSIZ yaz. "
    "Yalniz KALICI_DUMAN_AEROSOLU, DUMAN_BUHAR_BIRLIKTE, "
    "HIZLA_INCELEN_YOGUSMA, DUMAN_IZI_YOK veya BELIRSIZ yaz."
)

AKUT_SECENEKLER = (
    "ACIK_ALEV",
    "HIZLA_BUYUYEN_YOGUN_KOYU_DUMAN",
    "YALNIZ_PLUM_EMISYONU",
    "ACIL_BELIRTI_YOK",
    "GORUNMUYOR",
)

AKUT_SORU = (
    "Gorunur plumun ACIL YANGIN kanitini ayri olc. Karelerde titreseyen/suren "
    "turuncu-sari acik alev var mi; veya kisa surede belirgin hacim kaplayacak "
    "bicimde hizla buyuyen yogun koyu duman var mi? Uzak ince/beyaz endustriyel "
    "plum, rutin emisyon, sis-bulut, isik parlamasi ve yalniz insanlarin hareketi "
    "acil yangin kaniti degildir. Insanlarin geri cekilmesi yalniz yardimci "
    "baglamdir; gorunur alev/duman olmadan yeterli degildir. Yalniz ACIK_ALEV, "
    "HIZLA_BUYUYEN_YOGUN_KOYU_DUMAN, YALNIZ_PLUM_EMISYONU, ACIL_BELIRTI_YOK "
    "veya GORUNMUYOR yaz."
)

_GORSEL_DESTEK = {"KAYNAKTAN_CIKAN_PLUM"}
_GORSEL_CURUTME = {
    "ATMOSFERIK_BULUT_SIS", "KISA_TOZ_BUHAR", "SABIT_PARLAKLIK_GOLGE", "PLUM_YOK"
}
_ZAMANSAL_DESTEK = {"ENDUSTRIYEL_KAYNAKLI_PLUM"}
_ZAMANSAL_CURUTME = {
    "ATMOSFERLE_BIRLIKTE_HAREKET", "KISA_GECICI_SALIM", "SABIT_GORSEL_IZ", "PLUM_YOK"
}
_OPTIK_DUMAN_DESTEK = {"DUMAN_OPAKLIGI", "DUMAN_BUHAR_KARISIMI"}
_OPTIK_DUMAN_CURUTME = {"PARLAK_BEYAZ_BUHAR", "DUMAN_IZI_YOK"}
_DAGILIM_DUMAN_DESTEK = {"KALICI_DUMAN_AEROSOLU", "DUMAN_BUHAR_BIRLIKTE"}
_DAGILIM_DUMAN_CURUTME = {"HIZLA_INCELEN_YOGUSMA", "DUMAN_IZI_YOK"}
_AKUT_DESTEK = {"ACIK_ALEV", "HIZLA_BUYUYEN_YOGUN_KOYU_DUMAN"}


def _norm(value: object) -> str:
    return str(value or "").strip().upper()


@dataclass(frozen=True)
class DumanKanitSonucu:
    duzey: DumanDuzeyi
    slot_degeri: str
    cevaplar: Mapping[str, str]
    hatalar: Mapping[str, str] = field(default_factory=dict)
    destek_sayisi: int = 0
    curutme_sayisi: int = 0
    madde_destek_sayisi: int = 0
    madde_curutme_sayisi: int = 0

    @property
    def gozlem_var(self) -> bool:
        return self.duzey in (DumanDuzeyi.GOZLEM, DumanDuzeyi.AKUT_YANGIN)

    @property
    def akut(self) -> bool:
        return self.duzey == DumanDuzeyi.AKUT_YANGIN

    @property
    def refuted(self) -> bool:
        return (
            not self.gozlem_var
            and (self.curutme_sayisi >= 2 or self.madde_curutme_sayisi >= 1)
        )

    def iz_satiri(self) -> str:
        values = [f"slot={self.slot_degeri}"]
        values.extend(f"{key}={value}" for key, value in self.cevaplar.items())
        values.extend(f"{key}=HATA:{value}" for key, value in self.hatalar.items())
        return (
            f"duman-v3:{self.duzey.value}[destek={self.destek_sayisi},"
            f"curutme={self.curutme_sayisi},madde_destek={self.madde_destek_sayisi},"
            f"madde_curutme={self.madde_curutme_sayisi}; "
            + ", ".join(values) + "]"
        )


def sonuclandir(slot_degeri: object, cevaplar: Mapping[str, object],
                hatalar: Optional[Mapping[str, str]] = None) -> DumanKanitSonucu:
    """Uc kanalli oyu deterministik olarak duman gozlemi/akutluk kararina cevir."""
    slot = _norm(slot_degeri)
    norm = {key: _norm(value) for key, value in cevaplar.items()}
    visual = norm.get("gorunur_kaynakli_plum", "")
    temporal = norm.get("zamansal_kaynak", "")
    optical = norm.get("optik_madde", "")
    dispersion = norm.get("zamansal_madde", "")
    acute = norm.get("akut_belirti", "")

    supports = int(slot == "VAR")
    supports += int(visual in _GORSEL_DESTEK)
    supports += int(temporal in _ZAMANSAL_DESTEK)
    refutes = int(slot == "YOK")
    refutes += int(visual in _GORSEL_CURUTME)
    refutes += int(temporal in _ZAMANSAL_CURUTME)

    material_supports = int(optical in _OPTIK_DUMAN_DESTEK)
    material_supports += int(dispersion in _DAGILIM_DUMAN_DESTEK)
    material_refutes = int(optical in _OPTIK_DUMAN_CURUTME)
    material_refutes += int(dispersion in _DAGILIM_DUMAN_CURUTME)

    # Kaynak/plum yalniz on kosuldur. Duman icin iki farkli modelin madde
    # ayrimini ayni yonde desteklemesi gerekir; tek destek ve belirsizlik kapanir.
    observed = supports >= 2 and material_supports == 2
    if not observed:
        level = DumanDuzeyi.YOK
    elif acute in _AKUT_DESTEK:
        level = DumanDuzeyi.AKUT_YANGIN
    else:
        level = DumanDuzeyi.GOZLEM
    return DumanKanitSonucu(
        duzey=level,
        slot_degeri=slot,
        cevaplar=norm,
        hatalar=dict(hatalar or {}),
        destek_sayisi=supports,
        curutme_sayisi=refutes,
        madde_destek_sayisi=material_supports,
        madde_curutme_sayisi=material_refutes,
    )


def dogrula_video(istemci, video: "str | bytes", slot_degeri: object) -> DumanKanitSonucu:
    """Kaynak videoyu tek oturumda sabit ``vlm``/``llm-large`` rolleriyle olc."""
    try:
        oturum = istemci.video_oturumu(video, system=SISTEM)
    except Exception as exc:
        return sonuclandir(slot_degeri, {}, {"oturum": f"{type(exc).__name__}: {exc}"})
    if not getattr(oturum, "hazir", False):
        return sonuclandir(
            slot_degeri, {}, {"oturum": getattr(oturum, "hata", None) or "kurulamadi"}
        )

    answers: Dict[str, str] = {}
    errors: Dict[str, str] = {}
    original_client = oturum.istemci

    def ask(name: str, role: str, question: str, choices: Sequence[str]) -> None:
        try:
            oturum.istemci = istemci.gorev(role)
            answer = oturum.sor(
                question,
                temperature=0.0,
                max_tokens=40,
                guided_choice=choices,
                hatirla=False,
            )
            if answer is None:
                errors[name] = getattr(oturum, "hata", None) or "cevap alinamadi"
            else:
                answers[name] = answer
        except Exception as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"

    try:
        ask("gorunur_kaynakli_plum", "algi", GORSEL_SORU, GORSEL_SECENEKLER)
        ask("zamansal_kaynak", "olay", ZAMANSAL_SORU, ZAMANSAL_SECENEKLER)
        source_supports = int(_norm(slot_degeri) == "VAR")
        source_supports += int(_norm(answers.get("gorunur_kaynakli_plum")) in _GORSEL_DESTEK)
        source_supports += int(_norm(answers.get("zamansal_kaynak")) in _ZAMANSAL_DESTEK)
        if source_supports >= 2:
            ask("optik_madde", "algi", OPTIK_SORU, OPTIK_SECENEKLER)
            ask("zamansal_madde", "olay", DAGILIM_SORU, DAGILIM_SECENEKLER)
        preliminary = sonuclandir(slot_degeri, answers, errors)
        # Akut soru yalniz iki uzmanin destekledigi dumanda sorulur: buharli
        # negatif videoda fazladan API cagrisi ve zorlanmis yangin secimi yoktur.
        if preliminary.gozlem_var:
            ask("akut_belirti", "algi", AKUT_SORU, AKUT_SECENEKLER)
    finally:
        oturum.istemci = original_client
    return sonuclandir(slot_degeri, answers, errors)
