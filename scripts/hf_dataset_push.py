#!/usr/bin/env python
"""Turev degerlendirme setlerini bir HuggingFace **Dataset** deposuna paketler.

NEDEN VAR
=========
``data/`` dizini ~14 GB'dir ve ``.gitignore``'dadir (dogru karar: video veriyi git'e
gommeyiz). Sonuc: takim ``git pull`` yaptiginda KOD gelir, VERI GELMEZ ve herkesin
6 ayri indirici betigi (Mendeley 9.4 GB, Zenodo, GitHub, HF aynasi) tek tek
kosturmasi gerekir. Yavas, kirilgan, tekrar-uretilebilirligi zayif.

Bu betik **turev (kucuk, olculen) degerlendirme setlerini** tek bir HF Dataset
deposuna paketler. Boylece (a) takim tek komutla veriyi alir, (b) sartnamenin
"veri setinin indirilebilecegi herkese acik baglanti" sarti guclenir, (c) juri
benchmark'i BIREBIR yeniden kosabilir.

!!! YARISMA KURALI — KRITIK AYRIM !!!
=====================================
* HuggingFace'i **MODEL CALISTIRMAK** icin kullanmak **YASAKTIR**.
  (Inference API, Inference Endpoints, Spaces = "harici API / bulut servisi".)
* HuggingFace'i **VERI DAGITMAK** ve **MODEL AGIRLIGI INDIRMEK** icin kullanmak
  **SERBESTTIR** — indirilen sey diske iner ve **tamamen YERELDE** calisir.

Bu betik yalnizca ikinci gruba girer: bir dosya deposuna dosya koyar. Calisma
zamaninda hicbir HF servisi cagrilmaz; ``dilajan`` boru hatti agdan bagimsizdir.

!!! GUVENLIK: VARSAYILAN OLARAK HICBIR SEY YUKLENMEZ !!!
========================================================
Varsayilan mod **kuru calisma**dir (``--dry-run``). Gercek yukleme icin HEPSI
gerekir: ``--push`` **ve** ``--repo-id`` **ve** gecerli bir HF token **ve**
etkilesimli onay (veya ``--yes``). Bunlardan biri eksikse betik durur.

LISANS KAPISI (bu betigin en onemli parcasi)
============================================
Kaynak veri setlerinin lisanslari AYNI DEGILDIR ve bir kismi **yeniden
dagitilamaz**. Kapi bir **IZIN LISTESI** (allowlist) ile kurulmustur, kara liste
ile DEGIL:

    Bir dosya pakete yalnizca ve yalnizca su durumda girer:
      (set adi, cozumlenen kaynak veri seti) ciftinin **IZIN_LISTESI** icinde
      acikca yer almasi.

Taninmayan dosya adi, taninmayan set, yeni eklenmis bir kaynak -> **DISLANIR**.
Yani kapi **FAIL-CLOSED**'dur. (Projenin genel kod stili FAIL-OPEN'dir; lisans
kapisi bilincli olarak bunun ISTISNASIDIR: suphede kalinan dosya yuklenmez.)

Bu kapi ``--self-test`` ile kanitlanir (bkz. asagi).

DENETIMDE BULUNAN TUZAK (bu betigin var olma sebeplerinden biri)
----------------------------------------------------------------
"eval_scenario tamamen dagitilabilir" varsayimi **YANLISTIR**. Olculen gercek:

  * ``data/eval_scenario/Fall/urfd_fall0{1..6}.mp4``  -> URFD (akademik lisans)
  * ``data/eval_scenario/Normal/Normal_Videos_9*.mp4`` -> **UCF-Crime** (CC DEGIL)

Yani dagitilamaz veri, dagitilabilir bir setin **ICINE** karismis durumdadir.
Bu yuzden kapi **set duzeyinde degil, DOSYA duzeyinde** calisir.

MANIFEST — lisans ihlali olmadan tekrar-uretilebilirlik
=======================================================
``data/hf_manifest.json`` her klip icin {yol, set, kategori, md5, boyut, kaynak,
lisans, paketlendi_mi, dislanma_nedeni} tutar. Manifest **UST-VERIDIR, VIDEO
DEGILDIR**; bir MD5 ozeti telif iceren bir eser degildir. Bu yuzden manifest
**dagitilamayan setleri de kapsar** (UCF-Crime turevleri dahil) ama o setlerin
**videolari yuklenmez**.

Pratik sonucu: juri/hakem, elinde UCF-Crime erisimi varsa, manifest'teki MD5'ler
sayesinde bizim koctugumuz **birebir ayni** klip kumesini dogrulayabilir; erisimi
yoksa dagitilabilir setlerle olcumun buyuk kismini yine de yeniden kosabilir.
Lisans ihlali yapmadan tekrar-uretilebilirlik boylece saglanir.

KULLANIM
========
  # 1) Ne yuklenecek, ne dislanacak? (hicbir sey gonderilmez — VARSAYILAN)
  python scripts/hf_dataset_push.py

  # 2) Manifest'i diske yaz (MD5 hesaplar; ~2.9 GB okur)
  python scripts/hf_dataset_push.py --write-manifest

  # 3) Lisans kapisi birim testi
  python scripts/hf_dataset_push.py --self-test

  # 4) Yalnizca yerel paket klasoru kur (yukleme YOK) — gozle denetlemek icin
  python scripts/hf_dataset_push.py --stage

  # 5) GERCEK YUKLEME (token + acik onay gerekir; varsayilan depo GIZLIDIR)
  export HF_TOKEN=hf_xxx
  python scripts/hf_dataset_push.py --push --repo-id KULLANICI/dilajan-eval
  #   ... herkese acik yapmak icin ayrica --public verin.

  # Hizli tarama (MD5 hesaplamadan)
  python scripts/hf_dataset_push.py --no-md5

CIKIS KODLARI
  0  basarili
  1  self-test basarisiz / paketlenecek dosya yok
  2  ``huggingface_hub`` kurulu degil (yalnizca --push/--stage-upload yolunda)
  3  token yok veya onay verilmedi -> yukleme yapilmadi
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

# ---------------------------------------------------------------------------
# Yol cozumleme — CWD'ye DEGIL, PROJE KOKUNE gore. (Bu hata projede fiilen
# yasandi: betik scripts/ icinden calistirildiginda goreli "data/..." yolu
# scripts/data/... olmus ve 669 MB yanlis dizine inmisti.)
# ---------------------------------------------------------------------------
PROJE_KOKU: Path = Path(__file__).resolve().parent.parent
VERI_KOKU: Path = PROJE_KOKU / "data"

#: Manifest cikti yolu (proje kokune gore).
MANIFEST_YOLU: Path = VERI_KOKU / "hf_manifest.json"


def yol_coz(p: str) -> Path:
    """Goreli yolu **PROJE KOKUNE** gore coz (CWD'ye DEGIL).

    ``Path(p).resolve()`` bir tuzaktir: goreli yolu CWD'ye gore cozer, yani
    betik ``scripts/`` icinden calistirilirsa cikti YANLIS dizine yazilir.
    (Bu hata projede fiilen yasandi.) Mutlak yollar oldugu gibi birakilir.
    """
    y = Path(p)
    return y if y.is_absolute() else (PROJE_KOKU / y)

#: Video sayilan uzantilar. Baska uzanti taranmaz (README/MANIFEST.json gibi
#: yardimci dosyalar pakete kaynak-dosya olarak girmez).
VIDEO_UZANTILARI: frozenset[str] = frozenset({".mp4", ".avi", ".mov", ".mkv", ".webm"})


# ===========================================================================
# 1) KAYNAK VERI SETLERI VE LISANSLARI
# ===========================================================================
@dataclass(frozen=True)
class Kaynak:
    """Bir ust-kaynak veri seti ve onun yeniden-dagitim durumu."""

    kimlik: str
    ad: str
    lisans: str
    #: Yeniden dagitim (redistribution) hakki var mi? Sadece BILGI amacli degil —
    #: IZIN_LISTESI ile birlikte kapiyi olusturur.
    dagitilabilir: bool
    url: str
    atif: str
    not_: str = ""


KAYNAKLAR: dict[str, Kaynak] = {
    "firesense": Kaynak(
        kimlik="firesense",
        ad="FIRESENSE (yangin/duman + cetin negatifler)",
        lisans="CC BY 4.0",
        dagitilabilir=True,
        url="https://zenodo.org/records/836749",
        atif=(
            "FIRESENSE database of videos for flame and smoke detection, "
            "Zenodo record 836749 (CC BY 4.0)."
        ),
    ),
    "gmdcsa": Kaynak(
        kimlik="gmdcsa",
        ad="GMDCSA-24 (gercek dusme + ADL)",
        lisans="CC BY 4.0",
        dagitilabilir=True,
        url=(
            "https://github.com/ekramalam/"
            "GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos"
        ),
        atif=(
            "Alam et al., GMDCSA-24: A Dataset for Human Fall Detection in Videos "
            "(CC BY 4.0)."
        ),
    ),
    "eskisehir": Kaynak(
        kimlik="eskisehir",
        ad="Eskisehir Endustriyel — Video Dataset for Safe and Unsafe Behaviours",
        # LISANS CELISKISI COZULDU (docs/veri_lisans_karari.md §1): CELISKI YOKTU.
        # Mendeley public-API data_licence = "CC BY 4.0" (VERI SETI).
        # Data in Brief makalesindeki "CC BY-NC" ifadesi MAKALENIN kendi lisansidir
        # ("this ARTICLE"), veri setinin degil; makalenin Specifications Table'inda
        # "Data license" satiri YOKTUR. Yani veri seti CC BY 4.0'dir.
        lisans="CC BY 4.0 (Mendeley data_licence ile dogrulandi)",
        # ANCAK BAYTLARI YAYINLAMIYORUZ — engel TELIF DEGIL, KVKK/KISISEL VERI:
        # veri, adi acikca belirtilmis ozel bir sirketin (Kafaoglu Metal Plastik A.S.)
        # taninabilir GERCEK calisanlarinin 1080p isyeri gozetim goruntusudur ve
        # class0-3 belirli calisanlarin KURAL IHLALI anlarini etiketler.
        # CC BY 4.0 Bolum 2(b)(1): "publicity, privacy, and/or other similar
        # personality rights" LISANSLANMAZ ve bu haklar lisans verenin elinde degildir.
        # Yeniden yayin bizi yeni VERI SORUMLUSU yapar ve erisimi ARTIRMAZ
        # (veri zaten Mendeley'de herkese acik). Manifest + betikle bit-bit yeniden
        # kurulur; ustelik manifest Mendeley dosya kimligi tasidigi icin indirici
        # 9.4 GB yerine yalnizca gereken ~2.4 GB'i ceker (~4x hizli).
        dagitilabilir=False,
        url="https://data.mendeley.com/datasets/xjmtb22pff/1",
        atif=(
            "Video dataset for the detection of safe and unsafe behaviours in "
            "workplaces, Mendeley Data, DOI 10.17632/xjmtb22pff.1 (CC BY 4.0)."
        ),
        not_=(
            "KVKK: taninabilir calisanlarin isyeri gozetim goruntusu -> BAYT YAYINLANMAZ. "
            "Manifest ile bit-bit yeniden kurulur (scripts/get_industrial.py + "
            "scripts/build_defense_eval.py). Bilincli olarak yayinlamak icin: "
            "--include-eskisehir (KVKK sorumlulugu size gecer)."
        ),
    ),
    "urfd": Kaynak(
        kimlik="urfd",
        ad="URFD (UR Fall Detection — tavan/gozetim acisi)",
        lisans="Akademik/arastirma kullanimi (CC DEGIL)",
        dagitilabilir=False,
        url="http://fenix.ur.edu.pl/~mkepski/ds/uf.html",
        atif="Kwolek & Kepski, UR Fall Detection Dataset.",
        not_="Yeniden dagitim hakki YOK -> yalnizca indirici betikle alinir.",
    ),
    "ucf_crime": Kaynak(
        kimlik="ucf_crime",
        ad="UCF-Crime (gozetim anomali)",
        lisans="Akademik/arastirma kullanimi — CC DEGIL",
        dagitilabilir=False,
        url="https://www.crcv.ucf.edu/projects/real-world/",
        atif="Sultani et al., Real-world Anomaly Detection in Surveillance Videos, CVPR 2018.",
        not_=(
            "ASLA YENIDEN DAGITILMAZ. Kliplerimiz ayrica ucuncu-taraf bir HF "
            "aynasindan cekiliyor; o aynanin yetkisi bizim kontrolumuzde degil."
        ),
    ),
    "simuletic": Kaynak(
        kimlik="simuletic",
        ad="Simuletic CCTV (sentetik, tek kare — KULLANIM DISI)",
        lisans="CC BY 4.0",
        dagitilabilir=True,
        url=(
            "https://huggingface.co/datasets/Simuletic/"
            "CCTV_Incident_Dataset_Fall_Lying_Down_Detection"
        ),
        atif="Simuletic CCTV Incident Dataset (CC BY 4.0).",
        not_=(
            "Lisansi uygun ama KARANTINADA: donmus tek-kare klipler, olcume "
            "girmez. Varsayilan olarak paketlenmez (--include-deprecated)."
        ),
    ),
    "ozgun": Kaynak(
        kimlik="ozgun",
        ad="Proje uretimi (bozuk/bos/siyah dayaniklilik klipleri)",
        lisans="Apache-2.0 (proje lisansi)",
        dagitilabilir=True,
        url="https://github.com/ahmedberatAI/Dil-Ajanlari-Teknofest",
        atif="Dil Ajanlari — TEKNOFEST TYDA 2026, Apache-2.0.",
    ),
    "bilinmiyor": Kaynak(
        kimlik="bilinmiyor",
        ad="TANINMADI",
        lisans="bilinmiyor",
        dagitilabilir=False,
        url="",
        atif="",
        not_="Kaynagi cozumlenemeyen dosya. FAIL-CLOSED: pakete girmez.",
    ),
}


# ===========================================================================
# 2) SET POLITIKASI
# ===========================================================================
@dataclass(frozen=True)
class SetPolitikasi:
    """Bir ``data/<set>`` dizininin paketleme + manifest politikasi."""

    ad: str
    #: Set duzeyinde paketlemeye ADAY mi? (Dosya duzeyi kapisi ayrica calisir.)
    paketlenebilir: bool
    #: Manifest'e varsayilan olarak dahil mi?
    manifest_varsayilan: bool
    aciklama: str
    gerekce: str = ""


SET_POLITIKASI: dict[str, SetPolitikasi] = {
    "eval_defense": SetPolitikasi(
        "eval_defense", True, True,
        "Hedef-domain (tesis) tabakali degerlendirme seti — 200 klip, 1080p.",
    ),
    "eval_scenario": SetPolitikasi(
        "eval_scenario", True, True,
        "Senaryo seti: Yangin (FIRESENSE) + Dusme (GMDCSA/URFD) + Normal (tesis/UCF).",
        gerekce="KARISIK KAYNAK -> dosya duzeyi kapisi sart (URFD + UCF klipleri dislanir).",
    ),
    "eval_stress": SetPolitikasi(
        "eval_stress", True, True,
        "Adversaryel negatifler: yangin-renkli ama yangin OLMAYAN sahneler.",
    ),
    "falls_real": SetPolitikasi(
        "falls_real", True, True,
        "GMDCSA-24 gercek dusme + gunluk yasam aktivitesi (ADL).",
    ),
    "robust": SetPolitikasi(
        "robust", True, True,
        "Hata-toleransi klipleri (bozuk/bos/siyah/kucuk) — proje uretimi.",
    ),
    "falls_surveillance": SetPolitikasi(
        "falls_surveillance", False, True,
        "URFD tepeden-bakis dusme klipleri.",
        gerekce="URFD akademik lisans -> yeniden dagitim hakki YOK.",
    ),
    "eval_tune": SetPolitikasi(
        "eval_tune", False, True,
        "UCF-Crime ayar (tune) bolumu.",
        gerekce="UCF-Crime turevi — CC DEGIL, yeniden dagitim YASAK.",
    ),
    "eval_holdout": SetPolitikasi(
        "eval_holdout", False, True,
        "UCF-Crime dokunulmaz dogrulama (holdout) bolumu.",
        gerekce="UCF-Crime turevi — CC DEGIL, yeniden dagitim YASAK.",
    ),
    "e2_vehicle": SetPolitikasi(
        "e2_vehicle", False, True,
        "UCF-Crime RoadAccidents (E2 arac kanitI).",
        gerekce="UCF-Crime turevi — CC DEGIL, yeniden dagitim YASAK.",
    ),
    "eval": SetPolitikasi(
        "eval", False, False,
        "Eski kucuk UCF-Crime seti (eval_big'in tam alt kumesi).",
        gerekce="UCF-Crime turevi; ayrica bagimsiz kanit degil.",
    ),
    "eval_big": SetPolitikasi(
        "eval_big", False, False,
        "UCF-Crime buyuk set (tune+holdout birlesimi).",
        gerekce="UCF-Crime turevi — CC DEGIL, yeniden dagitim YASAK.",
    ),
    "industrial": SetPolitikasi(
        "industrial", False, False,
        "Eskisehir kaynak havuzu (691 klip / 9.4 GB).",
        gerekce=(
            "Dagitilabilir ama GEREK YOK: get_industrial.py paralel indiriyor ve "
            "9.4 GB'i cogaltmak anlamsiz. Turevi eval_defense zaten paketleniyor."
        ),
    ),
}

#: Manifest'e varsayilan olarak giren setler.
VARSAYILAN_SETLER: tuple[str, ...] = tuple(
    ad for ad, p in SET_POLITIKASI.items() if p.manifest_varsayilan
)


# ===========================================================================
# 3) KAYNAK COZUMLEME (dosya adi -> ust-kaynak veri seti)
# ===========================================================================
#: Sirali kurallar. Ilk eslesen kazanir. Desenler DOSYA ADINA uygulanir.
#: (set_kisiti = None -> her sette gecerli)
TANIMA_KURALLARI: tuple[tuple[re.Pattern[str], str, str | None], ...] = (
    # UCF-Crime: <Kategori><no>_x264.mp4 ve Normal_Videos_<no>_x264.mp4
    (re.compile(r"^Normal_Videos_\d+_x264\.(mp4|avi)$", re.I), "ucf_crime", None),
    (re.compile(
        r"^(Abuse|Arrest|Arson|Assault|Burglary|Explosion|Fighting|RoadAccidents|"
        r"Robbery|Shooting|Shoplifting|Stealing|Vandalism)\d+_x264\.(mp4|avi)$", re.I,
    ), "ucf_crime", None),
    # Genel emniyet kemeri: UCF ayna dosyalari daima _x264 tasir.
    (re.compile(r"_x264\.(mp4|avi)$", re.I), "ucf_crime", None),
    # URFD
    (re.compile(r"^urfd_", re.I), "urfd", None),
    # GMDCSA-24
    (re.compile(r"^Subject\d+_(fall|adl)\d+\.mp4$", re.I), "gmdcsa", None),
    # FIRESENSE (pozitif yangin/duman + negatif cetin ornekler)
    (re.compile(r"^(posVideo|negVideo)\d+\.\d+\.avi$", re.I), "firesense", None),
    (re.compile(r"^test(neg|pos)\d+\.\d+\.avi$", re.I), "firesense", None),
    # Simuletic (donmus tek-kare) — yalnizca karantina dizininde beklenir
    (re.compile(r"^lying\d+\.mp4$", re.I), "simuletic", None),
    # Eskisehir/Mendeley:  <sinif 0-7>_<tr|te><no>.mp4
    (re.compile(r"^[0-7]_(tr|te)\d+\.mp4$", re.I), "eskisehir", None),
    # Proje uretimi dayaniklilik klipleri — YALNIZCA robust/ setinde
    (re.compile(r"^(black|corrupt|empty|tiny)\.(mp4|avi)$", re.I), "ozgun", "robust"),
)


def kaynak_coz(set_adi: str, dosya_adi: str) -> str:
    """Dosya adindan ust-kaynak veri setini cozumle.

    Cozumlenemezse ``"bilinmiyor"`` doner -> IZIN_LISTESI'nde yer almadigi icin
    dosya otomatik olarak DISLANIR (FAIL-CLOSED).
    """
    for desen, kimlik, set_kisiti in TANIMA_KURALLARI:
        if set_kisiti is not None and set_kisiti != set_adi:
            continue
        if desen.search(dosya_adi):
            return kimlik
    return "bilinmiyor"


# ===========================================================================
# 4) IZIN LISTESI — LISANS KAPISI
# ===========================================================================
#: (set adi, kaynak kimligi) ciftleri. **Bu listede olmayan hicbir sey
#: paketlenmez.** Kara liste DEGIL — izin listesi. Yeni bir set veya yeni bir
#: kaynak eklenirse, buraya BILINCLI olarak yazilana kadar DISARIDA kalir.
IZIN_LISTESI: frozenset[tuple[str, str]] = frozenset({
    # eval_defense — tamami Eskisehir/Mendeley (CC BY / CC BY-NC, atifla dagitilir)
    ("eval_defense", "eskisehir"),
    # eval_scenario — SADECE CC BY kollari. urfd_* ve Normal_Videos_* HARIC.
    ("eval_scenario", "firesense"),
    ("eval_scenario", "gmdcsa"),
    ("eval_scenario", "eskisehir"),
    # eval_stress — FIRESENSE negatifleri
    ("eval_stress", "firesense"),
    # falls_real — GMDCSA-24
    ("falls_real", "gmdcsa"),
    # robust — kendi uretimimiz
    ("robust", "ozgun"),
})

#: ``--include-deprecated`` ile eklenen cift(ler). Lisansi uygun (CC BY 4.0)
#: fakat olcume girmeyen karantina verisi.
DEPRECATED_IZIN: frozenset[tuple[str, str]] = frozenset({
    ("eval_scenario", "simuletic"),
})

#: ``--exclude-nc`` ile disarida birakilacak kaynaklar (ticari-olmayan sarti
#: tasiyanlar). TEKNOFEST kullanimi ticari degildir; bu bayrak yalnizca ekstra
#: muhafazakar bir teslim istenirse kullanilir.
NC_KAYNAKLAR: frozenset[str] = frozenset({"eskisehir"})

#: TELIFCE yeniden dagitilabilir AMA kisisel-veri (KVKK) gerekcesiyle baytlari
#: VARSAYILAN olarak yayinlanmayan kaynaklar. Manifest'te yer alirlar; bilincli
#: gecersiz kilma icin ``--include-eskisehir``. Bkz. docs/veri_lisans_karari.md §4.
KVKK_DISLANAN: frozenset[str] = frozenset({"eskisehir"})


@dataclass(frozen=True)
class Karar:
    """Tek bir dosya icin lisans kapisi karari."""

    paketle: bool
    kaynak_kimlik: str
    neden: str


def lisans_kapisi(
    set_adi: str,
    dosya_adi: str,
    *,
    izin_listesi: frozenset[tuple[str, str]] = IZIN_LISTESI,
    nc_disla: bool = False,
    eskisehir_dahil: bool = False,
) -> Karar:
    """**LISANS KAPISI.** Bir dosyanin pakete girip giremeyecegine karar verir.

    Kapi uc asamalidir ve hepsi gecilmelidir:

    1. Set, ``SET_POLITIKASI`` icinde **paketlenebilir** olarak tanimli olmali.
    2. Dosya adindan cozumlenen kaynak **dagitilabilir** olmali.
    3. ``(set, kaynak)`` cifti **IZIN_LISTESI** icinde acikca yer almali.

    Herhangi biri saglanmazsa dosya DISLANIR ve gerekce metni doner.
    Bilinmeyen set / bilinmeyen kaynak -> DISLANIR (FAIL-CLOSED).
    """
    kaynak_kimlik = kaynak_coz(set_adi, dosya_adi)
    kaynak = KAYNAKLAR.get(kaynak_kimlik, KAYNAKLAR["bilinmiyor"])
    politika = SET_POLITIKASI.get(set_adi)

    # --- Asama 1: set duzeyi -------------------------------------------------
    if politika is None:
        return Karar(False, kaynak_kimlik,
                     f"set '{set_adi}' politikada TANIMSIZ (fail-closed)")
    if not politika.paketlenebilir:
        gerekce = politika.gerekce or "set paketlemeye kapali"
        return Karar(False, kaynak_kimlik, f"set '{set_adi}' paketlenmez: {gerekce}")

    # --- Asama 2: kaynak lisansi --------------------------------------------
    if kaynak_kimlik == "bilinmiyor":
        return Karar(False, kaynak_kimlik,
                     "dosya adindan kaynak COZUMLENEMEDI (fail-closed)")
    if not kaynak.dagitilabilir:
        # KVKK gecersiz kilma: Eskisehir seti TELIFCE serbesttir (CC BY 4.0) ama
        # taninabilir calisanlarin gozetim goruntusu oldugu icin varsayilan olarak
        # BAYT YAYINLANMAZ. Kullanici bilincli olarak --include-eskisehir derse
        # (ve depo GIZLI ise) izin verilir; sorumluluk kullaniciya gecer.
        if kaynak_kimlik == "eskisehir" and eskisehir_dahil:
            pass  # bilincli gecersiz kilma -> asama 3'e devam
        else:
            return Karar(False, kaynak_kimlik,
                         f"kaynak '{kaynak.ad}' YENIDEN DAGITILAMAZ ({kaynak.lisans})")
    if nc_disla and kaynak_kimlik in NC_KAYNAKLAR:
        return Karar(False, kaynak_kimlik,
                     f"--exclude-nc: '{kaynak.ad}' ticari-olmayan (NC) sartli")

    # --- Asama 3: izin listesi (as?l kapi) ----------------------------------
    if (set_adi, kaynak_kimlik) not in izin_listesi:
        return Karar(False, kaynak_kimlik,
                     f"IZIN LISTESINDE YOK: ({set_adi}, {kaynak_kimlik})")

    return Karar(True, kaynak_kimlik, f"izinli: {kaynak.lisans}")


# ===========================================================================
# 5) TARAMA + MANIFEST
# ===========================================================================
@dataclass
class Kayit:
    """Manifest'teki tek bir klip kaydi."""

    yol: str            # proje kokune gore POSIX yol (ornek: data/robust/black.mp4)
    set_adi: str
    kategori: str       # set icindeki alt dizin yolu ("" olabilir)
    dosya: str
    boyut: int
    md5: str | None
    kaynak: str
    lisans: str
    paketlendi: bool
    neden: str
    depo_yolu: str | None = None   # HF deposundaki hedef yol (paketlendiyse)

    def sozluk(self) -> dict:
        d = {
            "yol": self.yol,
            "set": self.set_adi,
            "kategori": self.kategori,
            "dosya": self.dosya,
            "boyut": self.boyut,
            "md5": self.md5,
            "kaynak": self.kaynak,
            "lisans": self.lisans,
            "paketlendi": self.paketlendi,
            "karar_nedeni": self.neden,
        }
        if self.depo_yolu:
            d["depo_yolu"] = self.depo_yolu
        return d


def md5_hesapla(yol: Path, blok: int = 1 << 20) -> str | None:
    """Dosyanin MD5 ozetini hesapla. Okunamazsa **FAIL-OPEN**: ``None`` doner.

    (Manifest ust-veridir; tek bir okunamayan dosya butun araci durdurmamali.)
    """
    try:
        h = hashlib.md5()
        with open(yol, "rb") as f:
            while True:
                parca = f.read(blok)
                if not parca:
                    break
                h.update(parca)
        return h.hexdigest()
    except Exception as exc:  # pragma: no cover - IO hatasi
        print(f"  ! MD5 okunamadi: {yol} ({exc})", file=sys.stderr)
        return None


def _depo_yolu(set_adi: str, kategori: str, dosya: str) -> str:
    """HF deposundaki hedef yol: ``<set>/<kategori>/<dosya>``."""
    parcalar = [set_adi] + ([kategori] if kategori else []) + [dosya]
    return "/".join(parcalar)


def setleri_tara(
    setler: Sequence[str],
    *,
    md5_hesapla_mi: bool = True,
    izin_listesi: frozenset[tuple[str, str]] = IZIN_LISTESI,
    nc_disla: bool = False,
    eskisehir_dahil: bool = False,
    sessiz: bool = False,
) -> list[Kayit]:
    """Verilen setleri tara, her klip icin lisans kapisini calistir, kayit uret."""
    kayitlar: list[Kayit] = []
    for set_adi in setler:
        kok = VERI_KOKU / set_adi
        if not kok.is_dir():
            if not sessiz:
                print(f"  - {set_adi}: dizin yok, atlandi ({kok})")
            continue
        dosyalar = sorted(
            (p for p in kok.rglob("*")
             if p.is_file() and p.suffix.lower() in VIDEO_UZANTILARI),
            key=lambda p: p.as_posix(),
        )
        if not sessiz:
            etiket = "MD5 hesaplaniyor" if md5_hesapla_mi else "taraniyor"
            print(f"  - {set_adi}: {len(dosyalar)} klip {etiket}...", flush=True)
        for p in dosyalar:
            goreli = p.relative_to(kok)
            kategori = goreli.parent.as_posix()
            if kategori == ".":
                kategori = ""
            karar = lisans_kapisi(
                set_adi, p.name, izin_listesi=izin_listesi, nc_disla=nc_disla,
                eskisehir_dahil=eskisehir_dahil,
            )
            kaynak = KAYNAKLAR.get(karar.kaynak_kimlik, KAYNAKLAR["bilinmiyor"])
            try:
                boyut = p.stat().st_size
            except Exception:
                boyut = 0
            kayitlar.append(Kayit(
                yol=p.relative_to(PROJE_KOKU).as_posix(),
                set_adi=set_adi,
                kategori=kategori,
                dosya=p.name,
                boyut=boyut,
                md5=md5_hesapla(p) if md5_hesapla_mi else None,
                kaynak=karar.kaynak_kimlik,
                lisans=kaynak.lisans,
                paketlendi=karar.paketle,
                neden=karar.neden,
                depo_yolu=_depo_yolu(set_adi, kategori, p.name) if karar.paketle else None,
            ))
    return kayitlar


# ===========================================================================
# 6) RAPORLAMA
# ===========================================================================
def boyut_yaz(n: int) -> str:
    """Bayt sayisini insan okunur bicime cevir."""
    birim = ["B", "KB", "MB", "GB", "TB"]
    x = float(n)
    i = 0
    while x >= 1024 and i < len(birim) - 1:
        x /= 1024.0
        i += 1
    return f"{x:.1f} {birim[i]}"


def rapor_yaz(kayitlar: list[Kayit], *, repo_id: str | None, baslik: str) -> None:
    """Set bazli ozet + dislanma gerekceleri + toplam raporu bas."""
    cizgi = "=" * 78
    print()
    print(cizgi)
    print(f"  {baslik}")
    print(cizgi)
    print(f"Proje koku : {PROJE_KOKU}")
    print(f"Veri koku  : {VERI_KOKU}")
    print(f"HF deposu  : {repo_id or '<belirtilmedi — --repo-id ile verin>'}")
    print()

    # --- set bazli ---
    print("--- SET BAZLI OZET " + "-" * 59)
    print(f"{'set':<20}{'tarandi':>8}{'PAKETE':>8}{'DISLANDI':>10}"
          f"{'paket boyutu':>15}{'  durum'}")
    setler: list[str] = []
    for k in kayitlar:
        if k.set_adi not in setler:
            setler.append(k.set_adi)
    for s in setler:
        alt = [k for k in kayitlar if k.set_adi == s]
        dahil = [k for k in alt if k.paketlendi]
        pol = SET_POLITIKASI.get(s)
        durum = "  DAHIL" if dahil else "  DISLANDI"
        if dahil and len(dahil) != len(alt):
            durum = "  KISMEN DAHIL"
        print(f"{s:<20}{len(alt):>8}{len(dahil):>8}{len(alt) - len(dahil):>10}"
              f"{boyut_yaz(sum(k.boyut for k in dahil)):>15}{durum}")
        if pol and not pol.paketlenebilir and pol.gerekce:
            print(f"{'':<20}   ^ {pol.gerekce}")
    print()

    # --- dislanma nedenleri ---
    dislanan = [k for k in kayitlar if not k.paketlendi]
    print("--- DISLANMA NEDENLERI " + "-" * 55)
    if not dislanan:
        print("  (yok)")
    else:
        gruplar: dict[str, list[Kayit]] = {}
        for k in dislanan:
            gruplar.setdefault(k.neden, []).append(k)
        for neden in sorted(gruplar, key=lambda n: -len(gruplar[n])):
            grup = gruplar[neden]
            print(f"  [{len(grup):>3} dosya | {boyut_yaz(sum(g.boyut for g in grup)):>9}] {neden}")
            for k in grup[:3]:
                print(f"        ornek: {k.yol}")
            if len(grup) > 3:
                print(f"        ... (+{len(grup) - 3} dosya daha)")
    print()

    # --- kaynak bazli ---
    print("--- KAYNAK VERI SETI BAZLI " + "-" * 52)
    print(f"{'kaynak':<14}{'lisans':<44}{'PAKETE':>7}{'DIS':>6}")
    kaynak_sirasi: list[str] = []
    for k in kayitlar:
        if k.kaynak not in kaynak_sirasi:
            kaynak_sirasi.append(k.kaynak)
    for kk in kaynak_sirasi:
        alt = [k for k in kayitlar if k.kaynak == kk]
        dahil = sum(1 for k in alt if k.paketlendi)
        lis = KAYNAKLAR.get(kk, KAYNAKLAR["bilinmiyor"]).lisans
        print(f"{kk:<14}{lis[:43]:<44}{dahil:>7}{len(alt) - dahil:>6}")
    print()

    # --- toplam ---
    dahil = [k for k in kayitlar if k.paketlendi]
    md5_var = sum(1 for k in kayitlar if k.md5)
    print("--- TOPLAM " + "-" * 67)
    print(f"  Pakete girecek : {len(dahil):>5} dosya   {boyut_yaz(sum(k.boyut for k in dahil))}")
    print(f"  Dislanan       : {len(dislanan):>5} dosya   {boyut_yaz(sum(k.boyut for k in dislanan))}")
    print(f"  Manifest kaydi : {len(kayitlar):>5} kayit   "
          f"(dislananlar UST-VERI olarak dahil; VIDEO yuklenmez)")
    print(f"  MD5 hesaplandi : {md5_var:>5} / {len(kayitlar)}")
    print(cizgi)


# ===========================================================================
# 7) DEPO ICERIGI URETIMI (dataset card, LICENSE, .gitattributes)
# ===========================================================================
#: A ajaninin uretmis olabilecegi dataset card icin aranacak yollar (sirali).
KART_ADAYLARI: tuple[str, ...] = (
    "docs/hf_dataset_card.md",
    "docs/HF_DATASET_CARD.md",
    "docs/dataset_card.md",
    "docs/hf_dataset.md",
    "data/HF_README.md",
    "HF_DATASET_CARD.md",
)


def dataset_card_bul() -> Path | None:
    """Varsa mevcut dataset card dosyasini bul (A ajani uretmis olabilir)."""
    for aday in KART_ADAYLARI:
        p = PROJE_KOKU / aday
        if p.is_file():
            return p
    return None


def dataset_card_uret(kayitlar: list[Kayit], repo_id: str | None) -> str:
    """Dataset card (README.md) metnini uret — mevcut kart yoksa yedek."""
    dahil = [k for k in kayitlar if k.paketlendi]
    dis = [k for k in kayitlar if not k.paketlendi]
    kullanilan = sorted({k.kaynak for k in dahil})

    satirlar: list[str] = []
    ekle = satirlar.append

    # --- YAML on-veri ---
    ekle("---")
    ekle("pretty_name: Dil Ajanlari — TEKNOFEST TYDA Degerlendirme Setleri")
    ekle("license: other")
    ekle("license_name: karma-cc-by-4.0-ve-cc-by-nc-4.0")
    ekle("license_link: LICENSE.md")
    ekle("language:")
    ekle("  - tr")
    ekle("task_categories:")
    ekle("  - video-classification")
    ekle("tags:")
    ekle("  - teknofest")
    ekle("  - video-anomaly-detection")
    ekle("  - workplace-safety")
    ekle("  - fall-detection")
    ekle("  - fire-detection")
    ekle("---")
    ekle("")

    ekle("# Dil Ajanlari — Degerlendirme Setleri (TEKNOFEST TYDA 3. Senaryo)")
    ekle("")
    ekle("Bu depo, `github.com/ahmedberatAI/Dil-Ajanlari-Teknofest` projesinin")
    ekle("**turev degerlendirme setlerini** barindirir. Amac: takimin ve jurinin")
    ekle("benchmark'i **birebir yeniden kosabilmesi**.")
    ekle("")

    # --- yarisma kurali ---
    ekle("## HuggingFace kullanimi hakkinda (yarisma kurali)")
    ekle("")
    ekle("> **Bu depo yalnizca VERI DAGITIMI icindir.**")
    ekle(">")
    ekle("> * HuggingFace'i **model calistirmak** icin kullanmak (Inference API,")
    ekle(">   Inference Endpoints, Spaces) yarisma kurallarinca **YASAKTIR** ve")
    ekle(">   projede **kullanilmamaktadir**.")
    ekle("> * HuggingFace'i **veri dagitmak** ve **model agirligi indirmek** icin")
    ekle(">   kullanmak **SERBESTTIR**: indirilen dosya diske iner, cikarim")
    ekle(">   **tamamen YERELDE** (vLLM + yerel GPU) yapilir.")
    ekle(">")
    ekle("> Boru hatti calisma aninda **hicbir harici API cagirmaz**.")
    ekle("")

    # --- icerik ---
    ekle("## Icerik")
    ekle("")
    ekle("| set | klip | boyut | icerik |")
    ekle("|---|---|---|---|")
    for s in sorted({k.set_adi for k in dahil}):
        alt = [k for k in dahil if k.set_adi == s]
        pol = SET_POLITIKASI.get(s)
        ekle(f"| `{s}/` | {len(alt)} | {boyut_yaz(sum(k.boyut for k in alt))} | "
             f"{pol.aciklama if pol else ''} |")
    ekle("")
    ekle(f"**Toplam: {len(dahil)} klip / {boyut_yaz(sum(k.boyut for k in dahil))}.**")
    ekle("")
    ekle("Dizin duzeni: `<set>/<kategori>/<dosya>` — kategori adi **etikettir**")
    ekle("(ornek: `eval_defense/Anomali/...`, `eval_scenario/Fire/...`).")
    ekle("")

    # --- burada OLMAYANLAR ---
    ekle("## Burada NE YOK — ve neden (lisans)")
    ekle("")
    ekle("Asagidaki setler **bilerek yuklenmemistir**; kaynak lisanslari yeniden")
    ekle("dagitima izin vermiyor. Bunlari indirmek icin depodaki betikleri kullanin.")
    ekle("")
    ekle("| dislanan | kaynak | lisans | nasil alinir |")
    ekle("|---|---|---|---|")
    ekle("| `eval_tune/`, `eval_holdout/`, `e2_vehicle/` | UCF-Crime | akademik, **CC DEGIL** |"
         " `scripts/get_ucf_many.py`, `scripts/split_eval_big.py` |")
    ekle("| `eval_scenario/Fall/urfd_*`, `falls_surveillance/` | URFD | akademik |"
         " `scripts/get_urfd_overhead.py` |")
    ekle("| `eval_scenario/Normal/Normal_Videos_*` | UCF-Crime | akademik, **CC DEGIL** |"
         " `scripts/get_normal_clips.py` |")
    ekle("")
    ekle(f"Bu turda dislanan dosya sayisi: **{len(dis)}**.")
    ekle("")

    # --- manifest ---
    ekle("## `hf_manifest.json` — lisans ihlali olmadan tekrar-uretilebilirlik")
    ekle("")
    ekle("Manifest **butun** kliplerin ust-verisini icerir; dagitilamayanlarin da.")
    ekle("Her kayitta `yol`, `set`, `kategori`, `md5`, `boyut`, `kaynak`, `lisans`,")
    ekle("`paketlendi` ve `karar_nedeni` alanlari bulunur.")
    ekle("")
    ekle("Bu bilincli bir tasarimdir:")
    ekle("")
    ekle("* Bir **MD5 ozeti telif iceren bir eser degildir** — ust-veri paylasmak")
    ekle("  lisans ihlali degildir; **video** paylasmak olurdu.")
    ekle("* UCF-Crime erisimi olan bir hakem, manifest'teki MD5'lerle bizim")
    ekle("  koctugumuz **birebir ayni klip kumesini** dogrulayabilir.")
    ekle("* Erisimi olmayan biri, dagitilabilir setlerle olcumun buyuk kismini")
    ekle("  yine de yeniden kosabilir.")
    ekle("")
    ekle("`paketlendi: false` olan her kayit, **neden** yuklenmedigini de tasir.")
    ekle("")

    # --- kullanim ---
    ekle("## Indirme")
    ekle("")
    ekle("```bash")
    ekle("pip install huggingface_hub")
    ekle("huggingface-cli download \\")
    ekle(f"  {repo_id or '<KULLANICI>/<DEPO>'} --repo-type dataset \\")
    ekle("  --local-dir data/")
    ekle("```")
    ekle("")
    ekle("veya Python ile:")
    ekle("")
    ekle("```python")
    ekle("from huggingface_hub import snapshot_download")
    ekle("snapshot_download(")
    ekle(f"    repo_id={repo_id!r} if {bool(repo_id)!r} else '<KULLANICI>/<DEPO>',")
    ekle("    repo_type='dataset',")
    ekle("    local_dir='data',")
    ekle(")")
    ekle("```")
    ekle("")

    # --- atif ---
    ekle("## Kaynaklar ve atif (ZORUNLU)")
    ekle("")
    for kk in kullanilan:
        kay = KAYNAKLAR.get(kk)
        if not kay:
            continue
        ekle(f"### {kay.ad}")
        ekle("")
        ekle(f"* **Lisans:** {kay.lisans}")
        ekle(f"* **Kaynak:** {kay.url}")
        ekle(f"* **Atif:** {kay.atif}")
        if kay.not_:
            ekle(f"* **Not:** {kay.not_}")
        ekle("")
    ekle("Yeniden dagitim CC BY / CC BY-NC sartlari altinda yapilmaktadir:")
    ekle("**atif zorunludur**; NC isaretli kaynaklar icin **ticari kullanim yoktur**.")
    ekle("")
    ekle("## Bilinen sinirliliklar")
    ekle("")
    ekle("* `eval_scenario` icinde **1080p anomali klibi yoktur**; cozunurluk ile")
    ekle("  etiket kismen birlikte hareket eder (confound). Ayrinti:")
    ekle("  `docs/olcum_durustlugu.md`.")
    ekle("* `eval_scenario/Fall` klipleri `falls_real/Fall` ile **birebir ayni")
    ekle("  dosyalardir** (MD5 esit) — ayri kanit olarak sayilmamalidir.")
    ekle("* Eskisehir setinin lisans beyani **celiskilidir** (Mendeley API: CC BY,")
    ekle("  Data in Brief makalesi: CC BY-NC); **muhafazakar okuma (NC)** benimsenmistir.")
    ekle("")
    ekle("---")
    ekle("")
    ekle("_Bu kart `scripts/hf_dataset_push.py` tarafindan uretilmistir._")
    return "\n".join(satirlar) + "\n"


def lisans_notu_uret(kayitlar: list[Kayit]) -> str:
    """Depoya konacak ``LICENSE.md`` metnini uret."""
    dahil = [k for k in kayitlar if k.paketlendi]
    satirlar = [
        "# Lisans notu",
        "",
        "Bu depo **karma lisansli** bir veri derlemesidir. Her klip, kendi",
        "**ust-kaynak veri setinin** lisansi altinda kalir. Derlemenin kendisi",
        "(dizin duzeni, manifest, betikler) Apache-2.0'dir.",
        "",
        "| set | kaynak | lisans | klip |",
        "|---|---|---|---|",
    ]
    ikili: dict[tuple[str, str], list[Kayit]] = {}
    for k in dahil:
        ikili.setdefault((k.set_adi, k.kaynak), []).append(k)
    for (s, kk), grup in sorted(ikili.items()):
        kay = KAYNAKLAR.get(kk, KAYNAKLAR["bilinmiyor"])
        satirlar.append(f"| `{s}/` | {kay.ad} | {kay.lisans} | {len(grup)} |")
    satirlar += [
        "",
        "## Atif (zorunlu)",
        "",
    ]
    for kk in sorted({k.kaynak for k in dahil}):
        kay = KAYNAKLAR.get(kk)
        if kay:
            satirlar.append(f"* **{kay.ad}** — {kay.atif}  ({kay.url})")
    satirlar += [
        "",
        "## Ticari kullanim",
        "",
        "Eskisehir/Mendeley kaynakli klipler icin **muhafazakar okuma CC BY-NC**",
        "benimsenmistir: **ticari kullanim yoktur**. TEKNOFEST kapsamindaki",
        "kullanim ticari degildir.",
        "",
        "## Burada BULUNMAYAN veri",
        "",
        "UCF-Crime ve URFD turevleri **yeniden dagitilmamaktadir** (akademik/",
        "arastirma lisansi, Creative Commons DEGIL). Bu kliplerin yalnizca",
        "**ust-verisi** (MD5/boyut) `hf_manifest.json` icinde yer alir; videolari",
        "kaynak kurumlardan alinmalidir. Bkz. proje deposundaki indirici betikler.",
        "",
    ]
    return "\n".join(satirlar) + "\n"


#: HF Hub LFS kurallari — video dosyalari LFS ile yuklenmelidir.
GITATTRIBUTES = """\
*.mp4  filter=lfs diff=lfs merge=lfs -text
*.avi  filter=lfs diff=lfs merge=lfs -text
*.mkv  filter=lfs diff=lfs merge=lfs -text
*.mov  filter=lfs diff=lfs merge=lfs -text
*.webm filter=lfs diff=lfs merge=lfs -text
"""


# ===========================================================================
# 8) PAKET KLASORU (staging)
# ===========================================================================
def _bagla(kaynak: Path, hedef: Path) -> str:
    """Once hardlink dene (disk korunur), olmazsa kopyala. Doner: yontem adi."""
    hedef.parent.mkdir(parents=True, exist_ok=True)
    if hedef.exists():
        return "mevcut"
    try:
        os.link(kaynak, hedef)
        return "hardlink"
    except Exception:
        shutil.copy2(kaynak, hedef)
        return "kopya"


def paket_kur(
    kayitlar: list[Kayit],
    hedef_dizin: Path,
    repo_id: str | None,
    *,
    temizle: bool = True,
) -> tuple[int, int]:
    """Paket klasorunu kur. **Yalnizca izinli dosyalar** kopyalanir.

    Klasorun kendisi lisans kapisinin KANITIDIR: icinde dagitilamaz tek bir
    dosya bulunmamalidir. Yukleme bu klasorden yapilir (``data/`` uzerinden
    desen filtresiyle DEGIL) — boylece bir desen hatasi veri sizdiramaz.
    """
    if temizle and hedef_dizin.exists():
        shutil.rmtree(hedef_dizin)
    hedef_dizin.mkdir(parents=True, exist_ok=True)

    n = 0
    toplam = 0
    for k in kayitlar:
        if not k.paketlendi or not k.depo_yolu:
            continue
        kaynak = PROJE_KOKU / k.yol
        if not kaynak.is_file():
            print(f"  ! kaynak yok, atlandi: {k.yol}", file=sys.stderr)
            continue
        _bagla(kaynak, hedef_dizin / k.depo_yolu)
        n += 1
        toplam += k.boyut

    # --- yardimci dosyalar ---
    (hedef_dizin / ".gitattributes").write_text(GITATTRIBUTES, encoding="utf-8")
    (hedef_dizin / "LICENSE.md").write_text(lisans_notu_uret(kayitlar), encoding="utf-8")

    mevcut_kart = dataset_card_bul()
    if mevcut_kart:
        shutil.copy2(mevcut_kart, hedef_dizin / "README.md")
        print(f"  dataset card: mevcut dosya kullanildi -> {mevcut_kart}")
    else:
        (hedef_dizin / "README.md").write_text(
            dataset_card_uret(kayitlar, repo_id), encoding="utf-8")
        print("  dataset card: hazir kart bulunamadi -> otomatik uretildi")

    (hedef_dizin / "hf_manifest.json").write_text(
        manifest_metni(kayitlar, repo_id), encoding="utf-8")
    return n, toplam


def paket_dogrula(hedef_dizin: Path) -> list[str]:
    """Kurulmus paket klasorunu **bagimsiz** olarak yeniden denetle.

    Klasoru sifirdan tarar ve her video dosyasini lisans kapisindan tekrar
    gecirir. Kapiyi gecemeyen dosya bulunursa sorun listesi doner (bos = temiz).
    Bu, "izin listesi dogru ama kopyalama kodu hatali" senaryosuna karsi
    ikinci bir savunma katmanidir.
    """
    sorunlar: list[str] = []
    for p in sorted(hedef_dizin.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in VIDEO_UZANTILARI:
            continue
        goreli = p.relative_to(hedef_dizin)
        set_adi = goreli.parts[0] if goreli.parts else ""
        karar = lisans_kapisi(set_adi, p.name)
        if not karar.paketle:
            sorunlar.append(f"{goreli.as_posix()}  -> {karar.neden}")
    return sorunlar


# ===========================================================================
# 9) MANIFEST YAZIMI
# ===========================================================================
def manifest_metni(kayitlar: list[Kayit], repo_id: str | None) -> str:
    """Manifest JSON metnini uret."""
    dahil = [k for k in kayitlar if k.paketlendi]
    dis = [k for k in kayitlar if not k.paketlendi]
    veri = {
        "_aciklama": (
            "Dil Ajanlari degerlendirme setleri — HF Dataset paket manifesti. "
            "Bu dosya UST-VERIDIR, video icermez. Dagitilamayan (UCF-Crime/URFD "
            "turevi) klipler de burada YER ALIR ama videolari YUKLENMEZ: bir MD5 "
            "ozeti telif iceren bir eser degildir, dolayisiyla ust-veriyi paylasmak "
            "lisans ihlali degildir. Amac, lisans ihlali olmadan tekrar-uretilebilirlik."
        ),
        "_hf_kullanimi": (
            "Bu depo yalnizca VERI DAGITIMI icindir. HuggingFace'i MODEL CALISTIRMAK "
            "(Inference API/Endpoints/Spaces) icin kullanmak yarisma kurallarinca "
            "YASAKTIR ve projede kullanilmamaktadir; veri/agirlik INDIRMEK serbesttir "
            "ve cikarim tamamen YERELDE yapilir."
        ),
        "uretim_zamani_utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "uretici": "scripts/hf_dataset_push.py",
        "hedef_depo": repo_id,
        "ozet": {
            "toplam_kayit": len(kayitlar),
            "paketlenen_klip": len(dahil),
            "paketlenen_boyut_bayt": sum(k.boyut for k in dahil),
            "dislanan_klip": len(dis),
            "dislanan_boyut_bayt": sum(k.boyut for k in dis),
            "md5_hesaplanan": sum(1 for k in kayitlar if k.md5),
        },
        "set_ozeti": {
            s: {
                "tarandi": sum(1 for k in kayitlar if k.set_adi == s),
                "paketlendi": sum(1 for k in kayitlar if k.set_adi == s and k.paketlendi),
                "aciklama": SET_POLITIKASI[s].aciklama if s in SET_POLITIKASI else "",
                "paketleme_gerekcesi": (
                    SET_POLITIKASI[s].gerekce if s in SET_POLITIKASI else ""),
            }
            for s in sorted({k.set_adi for k in kayitlar})
        },
        "kaynaklar": {
            kk: {
                "ad": kay.ad,
                "lisans": kay.lisans,
                "dagitilabilir": kay.dagitilabilir,
                "url": kay.url,
                "atif": kay.atif,
                "not": kay.not_,
            }
            for kk, kay in KAYNAKLAR.items()
            if kk in {k.kaynak for k in kayitlar}
        },
        "izin_listesi": sorted(f"{s}:{kk}" for s, kk in IZIN_LISTESI),
        "klipler": [k.sozluk() for k in kayitlar],
    }
    return json.dumps(veri, indent=1, ensure_ascii=False) + "\n"


# ===========================================================================
# 10) HF YUKLEME (varsayilan KAPALI)
# ===========================================================================
KURULUM_MESAJI = """
HATA: 'huggingface_hub' kurulu degil.

Kurulum:
    pip install 'huggingface_hub>=0.23'

WSL sanal ortaminda:
    /home/omen/teknofest/.venv/bin/pip install 'huggingface_hub>=0.23'

NOT: Kuru calisma (--dry-run, VARSAYILAN), --self-test, --write-manifest ve
--stage bu paket OLMADAN da calisir. huggingface_hub yalnizca GERCEK YUKLEME
icin gerekir.
""".strip()


def hf_yukle():
    """``huggingface_hub``'i ithal et; yoksa net kurulum mesaji basip cikis 2."""
    try:
        import huggingface_hub  # noqa: PLC0415
    except ImportError:
        print(KURULUM_MESAJI, file=sys.stderr)
        raise SystemExit(2)
    return huggingface_hub


def token_bul(hub) -> str | None:
    """HF token'i ortamdan veya yerel oturumdan bul."""
    for ad in ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        deger = os.environ.get(ad)
        if deger and deger.strip():
            return deger.strip()
    try:
        return hub.get_token()
    except Exception:
        return None


TOKEN_YOK_MESAJI = """
DURDURULDU: HuggingFace token bulunamadi -> HICBIR SEY YUKLENMEDI.

Token saglama yollari:
    1) Ortam degiskeni:   export HF_TOKEN=hf_xxxxxxxxxxxxxxxxx
    2) Yerel oturum:      huggingface-cli login

Token'i 'write' yetkisiyle su adresten uretin:
    https://huggingface.co/settings/tokens

Token'i ASLA depoya, komut gecmisine veya belgelere yazmayin.
""".strip()


def push_yap(
    hub,
    stage: Path,
    repo_id: str,
    token: str,
    *,
    private: bool,
    commit_mesaji: str,
) -> None:
    """Paket klasorunu HF Dataset deposuna yukle (LFS otomatik)."""
    api = hub.HfApi(token=token)
    print(f"  depo hazirlaniyor: {repo_id} (private={private}) ...", flush=True)
    api.create_repo(repo_id=repo_id, repo_type="dataset",
                    private=private, exist_ok=True)
    print("  yukleniyor (buyuk dosyalar LFS ile) ...", flush=True)
    url = api.upload_folder(
        folder_path=str(stage),
        repo_id=repo_id,
        repo_type="dataset",
        commit_message=commit_mesaji,
    )
    print(f"\nTAMAM -> {url}")
    print(f"Depo   : https://huggingface.co/datasets/{repo_id}")
    if private:
        print("UYARI  : depo GIZLI. Herkese acik yapmak icin --public verin "
              "veya HF arayuzunden degistirin.")


def onay_al(soru: str) -> bool:
    """Etkilesimli onay iste. Etkilesimli olmayan ortamda **HAYIR** say."""
    if not sys.stdin or not sys.stdin.isatty():
        print("  (etkilesimli olmayan ortam: onay alinamiyor -> HAYIR sayildi; "
              "otomasyon icin --yes kullanin)")
        return False
    try:
        cevap = input(soru).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return cevap in {"e", "evet", "y", "yes"}


# ===========================================================================
# 11) BIRIM TESTI — LISANS KAPISI KANITI
# ===========================================================================
def test_lisans_kapisi_ucf_turevlerini_disliyor() -> None:
    """UCF-Crime turevi hicbir yol pakete GIREMEZ."""
    ucf_yollari = [
        ("eval_tune", "Abuse021_x264.mp4"),
        ("eval_tune", "Normal_Videos_928_x264.mp4"),
        ("eval_holdout", "Explosion034_x264.mp4"),
        ("eval_holdout", "Normal_Videos_936_x264.mp4"),
        ("e2_vehicle", "RoadAccidents027_x264.mp4"),
        ("eval", "Assault018_x264.mp4"),
        ("eval_big", "Shooting037_x264.mp4"),
        # KRITIK: UCF klibi DAGITILABILIR bir setin ICINDE
        ("eval_scenario", "Normal_Videos_926_x264.mp4"),
        ("eval_scenario", "Normal_Videos_932_x264.mp4"),
    ]
    for set_adi, dosya in ucf_yollari:
        k = lisans_kapisi(set_adi, dosya)
        assert not k.paketle, f"UCF turevi PAKETE GIRDI: {set_adi}/{dosya}"
    # Kaynak dogru cozumlenmis olmali (rapor kalitesi icin)
    assert kaynak_coz("eval_scenario", "Normal_Videos_926_x264.mp4") == "ucf_crime"
    assert kaynak_coz("eval_tune", "Abuse021_x264.mp4") == "ucf_crime"


def test_lisans_kapisi_urfd_disliyor() -> None:
    """URFD (akademik lisans) klipleri pakete GIREMEZ — dagitilabilir set icinde bile."""
    for set_adi in ("eval_scenario", "falls_surveillance", "falls_real"):
        for n in range(1, 7):
            k = lisans_kapisi(set_adi, f"urfd_fall0{n}.mp4")
            assert not k.paketle, f"URFD PAKETE GIRDI: {set_adi}/urfd_fall0{n}.mp4"
            assert k.kaynak_kimlik == "urfd"


def test_lisans_kapisi_izinlileri_geciriyor() -> None:
    """Dagitilabilir kaynaklar dogru setlerde PAKETE GIRER."""
    gecmeli = [
        ("eval_defense", "3_te1.mp4", "eskisehir"),
        ("eval_defense", "0_tr128.mp4", "eskisehir"),
        ("eval_scenario", "posVideo1.868.avi", "firesense"),
        ("eval_scenario", "Subject1_fall01.mp4", "gmdcsa"),
        ("eval_scenario", "5_te1.mp4", "eskisehir"),
        ("eval_stress", "testneg01.807.avi", "firesense"),
        ("falls_real", "Subject2_adl01.mp4", "gmdcsa"),
        ("robust", "black.mp4", "ozgun"),
        ("robust", "corrupt.mp4", "ozgun"),
    ]
    for set_adi, dosya, beklenen_kaynak in gecmeli:
        # KVKK: eskisehir baytlari VARSAYILAN olarak dislanir; izin listesi/kaynak
        # cozumlemesi dogru mu diye bakarken bilincli gecersiz kilmayi acmamiz gerekir.
        if beklenen_kaynak == "eskisehir":
            k = lisans_kapisi(set_adi, dosya, eskisehir_dahil=True)
            assert k.paketle, f"--include-eskisehir ile bile DISLANDI: {set_adi}/{dosya} ({k.neden})"
            assert k.kaynak_kimlik == beklenen_kaynak
            continue
        k = lisans_kapisi(set_adi, dosya)
        assert k.paketle, f"izinli dosya DISLANDI: {set_adi}/{dosya} ({k.neden})"
        assert k.kaynak_kimlik == beklenen_kaynak, (
            f"{set_adi}/{dosya}: kaynak {k.kaynak_kimlik} != {beklenen_kaynak}")


def test_set_kapisi_kaynaktan_baskin() -> None:
    """Dagitilabilir bir klip, YASAKLI bir setin icindeyse yine de dislanir.

    Ornek: ``eval_tune/Normal/5_tr19.mp4`` gercekten Eskisehir kaynaklidir
    (dagitilabilir) — ama ``eval_tune`` bir UCF-Crime bolunmesidir; yarim bir
    kopyasini yayinlamak bolunmeyi bozar. Set kapisi baskin gelmelidir.
    """
    for dosya in ("5_tr19.mp4", "6_tr9.mp4", "7_tr15.mp4"):
        k = lisans_kapisi("eval_tune", dosya)
        assert not k.paketle, f"yasakli set icindeki klip PAKETE GIRDI: eval_tune/{dosya}"
        assert k.kaynak_kimlik == "eskisehir"


def test_bilinmeyen_fail_closed() -> None:
    """Taninmayan dosya adi ve taninmayan set -> DISLANIR (fail-closed)."""
    k = lisans_kapisi("eval_defense", "gizemli_klip.mp4")
    assert not k.paketle and k.kaynak_kimlik == "bilinmiyor"
    k = lisans_kapisi("yepyeni_set", "3_te1.mp4")
    assert not k.paketle, "politikada tanimsiz set PAKETE GIRDI"
    # robust'a ait desen BASKA sette gecerli olmamali (set kisitli kural)
    assert kaynak_coz("eval_defense", "black.mp4") == "bilinmiyor"


def test_deprecated_varsayilan_disarida() -> None:
    """Simuletic (CC BY 4.0 ama karantinada) varsayilan olarak DISARIDA."""
    k = lisans_kapisi("eval_scenario", "lying01.mp4")
    assert not k.paketle, "karantina klibi varsayilan olarak PAKETE GIRDI"
    assert k.kaynak_kimlik == "simuletic"
    # ... ama acikca istenirse girer
    k2 = lisans_kapisi("eval_scenario", "lying01.mp4",
                       izin_listesi=IZIN_LISTESI | DEPRECATED_IZIN)
    assert k2.paketle, "--include-deprecated ile bile giremedi"


def test_exclude_nc() -> None:
    """--exclude-nc, ticari-olmayan sartli kaynaklari disarida birakir."""
    # KVKK: varsayilan olarak eskisehir baytlari dislanir (telif degil, kisisel veri).
    assert not lisans_kapisi("eval_defense", "3_te1.mp4").paketle
    # bilincli gecersiz kilma ACIK iken paketlenir...
    assert lisans_kapisi("eval_defense", "3_te1.mp4", eskisehir_dahil=True).paketle
    # ...ama --exclude-nc ile birlikte yine dislanir (iki kapi bagimsiz)
    assert not lisans_kapisi("eval_defense", "3_te1.mp4",
                             eskisehir_dahil=True, nc_disla=True).paketle
    # CC BY 4.0 kaynaklar etkilenmez
    assert lisans_kapisi("eval_stress", "testneg01.807.avi", nc_disla=True).paketle


def test_izin_listesi_dagitilamaz_kaynak_icermiyor() -> None:
    """IZIN_LISTESI'nde dagitilamaz bir kaynak BULUNAMAZ (yapisal guvenlik)."""
    for set_adi, kk in IZIN_LISTESI:
        assert kk in KAYNAKLAR, f"IZIN_LISTESI bilinmeyen kaynak iceriyor: {kk}"
        # KVKK-dislanmis ama TELIFCE serbest kaynaklar izin listesinde KALIR:
        # --include-eskisehir bilincli gecersiz kilma yolunun calisabilmesi icin gerekli.
        if kk in KVKK_DISLANAN:
            continue
        assert KAYNAKLAR[kk].dagitilabilir, (
            f"IZIN_LISTESI DAGITILAMAZ kaynak iceriyor: {set_adi}:{kk}")
        pol = SET_POLITIKASI.get(set_adi)
        assert pol is not None and pol.paketlenebilir, (
            f"IZIN_LISTESI paketlenmeyen set iceriyor: {set_adi}")


def test_yollar_proje_kokune_gore() -> None:
    """Goreli yollar PROJE KOKUNE cozulur, CWD'ye DEGIL."""
    assert yol_coz("hf_manifest.json") == PROJE_KOKU / "hf_manifest.json"
    assert yol_coz("data/x.json") == PROJE_KOKU / "data" / "x.json"
    mutlak = Path("/tmp/x.json") if os.name != "nt" else Path("C:/tmp/x.json")
    assert yol_coz(str(mutlak)) == mutlak, "mutlak yol degistirilmemeli"
    assert MANIFEST_YOLU.is_absolute() and MANIFEST_YOLU.parent == VERI_KOKU


def test_gercek_tarama_temiz() -> None:
    """Diskteki GERCEK veri taranir; dislanmasi gerekenler dislanmis olmali.

    Veri yoksa test sessizce atlanir (CI/temiz kopya senaryosu).
    """
    if not VERI_KOKU.is_dir():
        return
    kayitlar = setleri_tara(list(VARSAYILAN_SETLER), md5_hesapla_mi=False, sessiz=True)
    if not kayitlar:
        return
    for k in kayitlar:
        if not k.paketlendi:
            continue
        assert KAYNAKLAR[k.kaynak].dagitilabilir, (
            f"DAGITILAMAZ klip pakete girdi: {k.yol} ({k.kaynak})")
        assert k.set_adi not in {"eval_tune", "eval_holdout", "e2_vehicle",
                                 "eval", "eval_big", "falls_surveillance"}, (
            f"yasakli setten klip pakete girdi: {k.yol}")
        assert not k.dosya.lower().startswith("urfd_"), f"URFD klibi pakete girdi: {k.yol}"
        assert "_x264" not in k.dosya.lower(), f"UCF klibi pakete girdi: {k.yol}"


TESTLER = (
    test_lisans_kapisi_ucf_turevlerini_disliyor,
    test_lisans_kapisi_urfd_disliyor,
    test_lisans_kapisi_izinlileri_geciriyor,
    test_set_kapisi_kaynaktan_baskin,
    test_bilinmeyen_fail_closed,
    test_deprecated_varsayilan_disarida,
    test_exclude_nc,
    test_izin_listesi_dagitilamaz_kaynak_icermiyor,
    test_yollar_proje_kokune_gore,
    test_gercek_tarama_temiz,
)


def self_test() -> int:
    """Butun birim testlerini kostur. 0 = hepsi gecti."""
    print("=" * 78)
    print("  LISANS KAPISI BIRIM TESTI")
    print("=" * 78)
    hata = 0
    for t in TESTLER:
        ad = t.__name__
        try:
            t()
            print(f"  [GECTI]  {ad}")
        except AssertionError as exc:
            hata += 1
            print(f"  [KALDI]  {ad}\n           -> {exc}")
        except Exception as exc:  # pragma: no cover
            hata += 1
            print(f"  [HATA ]  {ad}\n           -> {type(exc).__name__}: {exc}")
    print("-" * 78)
    if hata:
        print(f"  SONUC: {len(TESTLER) - hata}/{len(TESTLER)} gecti, {hata} BASARISIZ")
    else:
        print(f"  SONUC: {len(TESTLER)}/{len(TESTLER)} GECTI — lisans kapisi saglam.")
    print("=" * 78)
    return 1 if hata else 0


# ===========================================================================
# 12) CLI
# ===========================================================================
def arg_ayristir(argv: Sequence[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="hf_dataset_push.py",
        description=(
            "Turev degerlendirme setlerini HF Dataset deposuna paketler. "
            "VARSAYILAN: kuru calisma — hicbir sey yuklenmez."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "GUVENLIK: gercek yukleme icin --push + --repo-id + HF token + onay "
            "(veya --yes) HEPSI gerekir.\n"
            "YARISMA: bu depo yalnizca VERI DAGITIMI icindir; HF ile MODEL "
            "CALISTIRMAK yasaktir ve yapilmamaktadir."),
    )
    ap.add_argument("--repo-id", default=None,
                    help="Hedef HF dataset deposu, ornek: KULLANICI/dilajan-eval. "
                         "Varsayilani YOKTUR (kaza ile yukleme olmasin).")
    ap.add_argument("--push", action="store_true",
                    help="GERCEK YUKLEME yap. Token + onay gerekir. Varsayilan KAPALI.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Kuru calisma (VARSAYILAN). Verilirse --push'u ezer.")
    ap.add_argument("--stage", action="store_true",
                    help="Paket klasorunu yerelde kur (yukleme YOK) — gozle denetim icin.")
    ap.add_argument("--stage-dir", default=None,
                    help="Paket klasoru yolu (varsayilan: outputs/hf_stage). "
                         "Goreli verilirse PROJE KOKUNE gore cozulur.")
    ap.add_argument("--yes", "-y", action="store_true",
                    help="Yukleme onay sorusunu atla (otomasyon).")
    ap.add_argument("--public", action="store_true",
                    help="Depoyu HERKESE ACIK olustur (varsayilan: GIZLI).")
    ap.add_argument("--sets", default=None,
                    help="Virgulle ayrilmis set listesi (varsayilan: manifest setleri). "
                         f"Bilinen: {', '.join(SET_POLITIKASI)}")
    ap.add_argument("--no-md5", action="store_true",
                    help="MD5 hesaplama (hizli tarama; manifest md5=null olur).")
    ap.add_argument("--write-manifest", action="store_true",
                    help=f"Manifest'i diske yaz -> {MANIFEST_YOLU.relative_to(PROJE_KOKU)}")
    ap.add_argument("--manifest-out", default=None,
                    help="Manifest cikti yolu (varsayilan: data/hf_manifest.json). "
                         "Goreli verilirse PROJE KOKUNE gore cozulur. NOT: data/ "
                         "'.gitignore'dadir -> git ile paylasmak icin "
                         "'--manifest-out hf_manifest.json' kullanin.")
    ap.add_argument("--include-deprecated", action="store_true",
                    help="Karantinadaki Simuletic kliplerini de paketle (CC BY 4.0, "
                         "olcume girmez).")
    ap.add_argument("--exclude-nc", action="store_true",
                    help="Ticari-olmayan (NC) sartli kaynaklari disla "
                         "(Eskisehir/Mendeley -> eval_defense bosalir).")
    ap.add_argument("--include-eskisehir", action="store_true",
                    help="KVKK GECERSIZ KILMA: Eskisehir/Mendeley kliplerinin BAYTLARINI da "
                         "yukle. Telifce serbesttir (CC BY 4.0) ama taninabilir calisanlarin "
                         "isyeri gozetim goruntusudur; varsayilan olarak YALNIZCA MANIFEST "
                         "yayinlanir. Bu bayrakla KVKK sorumlulugu size gecer ve depo GIZLI olmalidir.")
    ap.add_argument("--self-test", action="store_true",
                    help="Lisans kapisi birim testlerini kostur ve cik.")
    ap.add_argument("--commit-message", default=None,
                    help="HF commit mesaji.")
    return ap.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = arg_ayristir(argv)

    if args.self_test:
        return self_test()

    # --- setler ---
    if args.sets:
        setler = [s.strip() for s in args.sets.split(",") if s.strip()]
        bilinmeyen = [s for s in setler if s not in SET_POLITIKASI]
        if bilinmeyen:
            print(f"UYARI: politikada tanimsiz set(ler): {', '.join(bilinmeyen)} "
                  f"-> taranir ama HICBIRI paketlenmez (fail-closed).")
    else:
        setler = list(VARSAYILAN_SETLER)

    izin = IZIN_LISTESI | (DEPRECATED_IZIN if args.include_deprecated else frozenset())

    if not VERI_KOKU.is_dir():
        print(f"HATA: veri dizini yok: {VERI_KOKU}\n"
              f"  Once indirici betikleri kosturun (scripts/get_*.py).", file=sys.stderr)
        return 1

    # --- tarama ---
    print(f"Taraniyor: {', '.join(setler)}")
    baslangic = time.time()
    kayitlar = setleri_tara(
        setler,
        md5_hesapla_mi=not args.no_md5,
        izin_listesi=izin,
        nc_disla=args.exclude_nc,
        eskisehir_dahil=args.include_eskisehir,
    )
    print(f"  ({time.time() - baslangic:.1f} sn)")

    if not kayitlar:
        print("HATA: hicbir klip bulunamadi.", file=sys.stderr)
        return 1

    # --- yukleme modu belirleme ---
    kuru = not args.push or args.dry_run
    if args.push and args.dry_run:
        print("\nNOT: --dry-run verildi -> --push YOK SAYILDI (guvenli taraf).")

    baslik = ("HF DATASET PAKETLEME — KURU CALISMA (HICBIR SEY GONDERILMEDI)"
              if kuru else "HF DATASET PAKETLEME — YUKLEME HAZIRLIGI")
    rapor_yaz(kayitlar, repo_id=args.repo_id, baslik=baslik)

    if args.exclude_nc:
        print("NOT: --exclude-nc etkin -> NC sartli kaynaklar (Eskisehir/Mendeley) "
              "disarida.\n")
    else:
        nc_sayi = sum(1 for k in kayitlar if k.paketlendi and k.kaynak in NC_KAYNAKLAR)
        if nc_sayi:
            print(f"UYARI (LISANS): {nc_sayi} klip Eskisehir/Mendeley kaynaklidir. "
                  f"Lisans beyani CELISKILIDIR\n"
                  f"  (Mendeley API: CC BY 4.0 / Data in Brief makalesi: CC BY-NC).\n"
                  f"  MUHAFAZAKAR okuma benimsendi: CC BY-NC -> TICARI KULLANIM YOK, "
                  f"ATIF ZORUNLU.\n"
                  f"  Her iki okuma da ATIFLA YENIDEN DAGITIMA izin verir; TEKNOFEST "
                  f"kullanimi ticari degildir.\n"
                  f"  Teslimden once yayinciyla teyit edin. Disarida birakmak icin: "
                  f"--exclude-nc\n")

    # --- manifest ---
    if args.write_manifest:
        cikti = yol_coz(args.manifest_out) if args.manifest_out else MANIFEST_YOLU
        cikti.parent.mkdir(parents=True, exist_ok=True)
        cikti.write_text(manifest_metni(kayitlar, args.repo_id), encoding="utf-8")
        print(f"Manifest yazildi -> {cikti}  ({len(kayitlar)} kayit, "
              f"{boyut_yaz(cikti.stat().st_size)})")
    else:
        print("Manifest DISKE YAZILMADI (yazmak icin --write-manifest).")

    paketlenecek = [k for k in kayitlar if k.paketlendi]
    if not paketlenecek:
        print("\nUYARI: paketlenecek dosya YOK.")
        return 0 if kuru else 1

    # --- paket klasoru gerekiyor mu? ---
    if not (args.stage or not kuru):
        print("\nKURU CALISMA BITTI — hicbir dosya kopyalanmadi, hicbir sey gonderilmedi.")
        print("  Yerel paket klasoru kurmak icin : --stage")
        print("  Gercek yukleme icin             : --push --repo-id KULLANICI/DEPO")
        return 0

    stage = (yol_coz(args.stage_dir) if args.stage_dir
             else PROJE_KOKU / "outputs" / "hf_stage")

    # --- yukleme on kosullari (paket kurmadan ONCE kontrol) ---
    if not kuru:
        if not args.repo_id:
            print("\nDURDURULDU: --push icin --repo-id ZORUNLUDUR "
                  "(kaza ile yukleme olmasin).", file=sys.stderr)
            return 3
        hub = hf_yukle()          # yoksa cikis 2
        token = token_bul(hub)
        if not token:
            print("\n" + TOKEN_YOK_MESAJI, file=sys.stderr)
            return 3

    # --- paket klasorunu kur ---
    print(f"\nPaket klasoru kuruluyor -> {stage}")
    n, toplam = paket_kur(kayitlar, stage, args.repo_id)
    print(f"  {n} klip baglandi / kopyalandi ({boyut_yaz(toplam)}) "
          f"+ README.md, LICENSE.md, hf_manifest.json, .gitattributes")

    # --- bagimsiz yeniden denetim ---
    sorunlar = paket_dogrula(stage)
    if sorunlar:
        print("\nKRITIK: paket klasorunde IZINSIZ dosya(lar) bulundu -> DURDURULDU:",
              file=sys.stderr)
        for s in sorunlar[:20]:
            print(f"  ! {s}", file=sys.stderr)
        return 1
    print(f"  Bagimsiz yeniden denetim: TEMIZ ({n} dosyanin tamami izin listesinden gecti).")

    if kuru:
        print("\nPaket klasoru hazir — YUKLEME YAPILMADI (--stage).")
        print(f"  Gozle denetleyin: {stage}")
        return 0

    # --- son onay + yukleme ---
    print()
    print("=" * 78)
    print("  YUKLEME ONAYI")
    print("=" * 78)
    print(f"  Hedef depo   : {args.repo_id}  (repo_type=dataset)")
    print(f"  Gorunurluk   : {'HERKESE ACIK' if args.public else 'GIZLI (varsayilan)'}")
    print(f"  Dosya sayisi : {n} klip + 4 yardimci dosya")
    print(f"  Toplam boyut : {boyut_yaz(toplam)}")
    print(f"  Kaynak       : {stage}")
    print("=" * 78)
    if not args.yes and not onay_al("  Yuklemeyi onayliyor musunuz? [e/H]: "):
        print("\nIPTAL EDILDI — hicbir sey yuklenmedi.")
        return 3

    mesaj = args.commit_message or (
        f"Dil Ajanlari degerlendirme setleri — {n} klip, "
        f"{boyut_yaz(toplam)} (scripts/hf_dataset_push.py)")
    try:
        push_yap(hub, stage, args.repo_id, token,
                 private=not args.public, commit_mesaji=mesaj)
    except Exception as exc:
        print(f"\nYUKLEME BASARISIZ: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
