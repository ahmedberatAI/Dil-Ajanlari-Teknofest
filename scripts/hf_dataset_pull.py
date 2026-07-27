#!/usr/bin/env python
"""Turev degerlendirme setlerini bir HuggingFace **dataset** deposundan ``data/``
altina indirir; MD5 ile butunluk dogrulamasi yapar; dagitilamayan (lisansi
kapali) setler icin **dogru kurucu betigi** onerir.

NEDEN
  ``data/`` 14 GB ve ``.gitignore``'dadir. Takim uyesi ``git pull`` yaptiginda KOD
  gelir, VERI GELMEZ; su an 6 ayri indirici betigi (Mendeley 9.4 GB, Zenodo,
  GitHub, HF) tek tek kosturmak gerekiyor. Bu betik, **dagitilabilir** turev
  setleri TEK KOMUTLA getirir; kalanlar icin ne kosulacagini soyler.

LISANS — BU BETIGIN EN ONEMLI ISI (fail-CLOSED)
  Her klip **dosya duzeyinde** kaynagina gore siniflanir; yalnizca lisansi acikca
  yeniden-dagitima izin verenler HF deposuna girer. Kaynagi cozulemeyen dosya
  ``dagitilamaz`` sayilir (bilinmeyen = kapali). Bu, kod tarafindaki genel
  FAIL-OPEN ilkesinin bilincli istisnasidir: bir analiz adimi patlarsa sessizce
  devre disi kalir, ama bir **lisans** belirsizse veri DAGITILMAZ.

  Set duzeyinde degil DOSYA duzeyinde bakmak zorunludur, cunku karisik setler var:
    data/eval_scenario/Fall    -> 9 GMDCSA (CC BY) + 6 URFD (akademik, KAPALI)
    data/eval_scenario/Normal  -> 8 Eskisehir (kosullu) + 4 UCF-Crime (KAPALI)

YARISMA KURALI (kritik ayrim — her uretilen belgede tekrarlanir)
  * HF'i **model CALISTIRMAK** icin kullanmak YASAK
    (Inference API / Endpoints / Spaces = "harici API / bulut").
  * HF'i **VERI DAGITMAK** ve **MODEL AGIRLIGI INDIRMEK** icin kullanmak SERBEST:
    indirilen sey diske iner, cikarim %100 YERELDE (kendi vLLM sunucumuzda) kosar.
  Bu betik yalnizca dosya indirir; hicbir model cagrisi yapmaz.

KULLANIM
  python scripts/hf_dataset_pull.py --list
      Ag YOK. Manifest'ten planı basar: hangi set HF'den gelir, hangisi betikle kurulur.

  python scripts/hf_dataset_pull.py --repo KULLANICI/dilajanlari-eval --dry-run
      Depoyu yoklar (salt-okunur), indirilecek/atlanacak dosyalari listeler, INDIRMEZ.

  python scripts/hf_dataset_pull.py --repo KULLANICI/dilajanlari-eval
      Indirir. Var olan ve MD5'i tutan dosyalari ATLAR; yarim indirmeyi surdurur.

  python scripts/hf_dataset_pull.py --sets eval_defense,eval_scenario --repo ...
      Secmeli indirme (varsayilan: dagitilabilir tum setler).

  python scripts/hf_dataset_pull.py --verify
      Ag YOK. Yereldeki dosyalari manifest MD5'leri ile karsilastirir; eksik/bozuk raporlar.

  python scripts/hf_dataset_pull.py --make-manifest
      (KAPTAN) Yereldeki data/ dizinini tarar, MD5'leri hesaplar, hf_manifest.json uretir.

  python scripts/hf_dataset_pull.py --upload-plan --repo KULLANICI/dilajanlari-eval
      Yalnizca **METIN** basar: kaptanin elle kosacagi ``hf upload`` komutlari + hangi
      dosyanin neden haric tutuldugu. BU BETIK HICBIR SEY YUKLEMEZ.

CIKIS KODLARI
  0 basarili · 2 depo adi verilmedi (yer tutucu) · 3 huggingface_hub yok
  4 depo bulunamadi / erisilemedi · 5 ag hatasi · 6 butunluk dogrulamasi basarisiz
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from typing import Any, Iterable

# --- Yollar: PROJE KOKUNE gore cozulur (CWD'den TAMAMEN bagimsiz) -------------
_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_SCRIPTS)
DATA = os.path.join(ROOT, "data")
#: Depoya commit'lenen kanonik manifest (data/ .gitignore'da oldugu icin KOK'te durur).
MANIFEST_YEREL = os.path.join(ROOT, "hf_manifest.json")
#: ``scripts/hf_dataset_push.py``'in yazdigi / HF deposundan inen kopya.
#: Paketleyici taraf otorite oldugu icin VARSA BU TERCIH EDILIR (bkz. manifest_yolu).
MANIFEST_PAKETLEYICI = os.path.join(DATA, "hf_manifest.json")
#: HF deposundan ayri bir dizine indirilmis kopya (capraz kontrol icin).
MANIFEST_INDIRILEN = os.path.join(DATA, "_hf", "hf_manifest.json")

#: Depo HENUZ YAYINLANMADI. Gercek ad verilene kadar bu yer tutucu kullanilir.
YER_TUTUCU_REPO = "<HF_KULLANICI>/dilajanlari-eval"
VARSAYILAN_REPO = os.environ.get("DILAJAN_HF_REPO", YER_TUTUCU_REPO)

VIDEO_UZANTI = (".mp4", ".avi", ".mkv", ".mov")
MANIFEST_SURUM = 1


# =============================================================================
# 1) KAYNAK -> LISANS tablosu.  docs/veri_kaynaklari.md ile birebir tutulmalidir.
# =============================================================================
KAYNAKLAR: dict[str, dict[str, Any]] = {
    "FIRESENSE": {
        "lisans": "CC BY 4.0",
        "dagitim": "evet",
        "link": "https://zenodo.org/records/836749",
        "atif": "FIRESENSE database of videos for flame and smoke detection (Zenodo 836749)",
        "betik": "python scripts/get_firesense.py",
        "not": "CC BY 4.0 -> atifla yeniden dagitilabilir.",
    },
    "GMDCSA-24": {
        "lisans": "CC BY 4.0",
        "dagitim": "evet",
        "link": "https://github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos",
        "atif": "GMDCSA-24: A Dataset for Human Fall Detection in Videos",
        "betik": "python scripts/get_gmdcsa.py",
        "not": "CC BY 4.0 -> atifla yeniden dagitilabilir.",
    },
    "Eskisehir": {
        "lisans": "CELISKILI: Mendeley API = CC BY 4.0, Data in Brief makalesi = CC BY-NC",
        "dagitim": "kosullu",
        "link": "https://data.mendeley.com/datasets/xjmtb22pff/1",
        "atif": "Eskisehir uretim tesisi guvenli/guvensiz davranis seti (DOI 10.17632/xjmtb22pff.1)",
        "betik": "python scripts/get_industrial.py  &&  python scripts/build_defense_eval.py",
        "not": ("MUHAFAZAKAR okuma benimsendi (data/eval_defense/MANIFEST.json ile ayni): "
                "CC BY-NC 4.0 -> TICARI KULLANIM YOK, atif ZORUNLU. Yeniden dagitim ancak "
                "celiski makale metninden teyit edildikten ve depo karti NC sartini "
                "acikca yazdiktan sonra yapilmalidir."),
    },
    "URFD": {
        "lisans": "Akademik/arastirma izni (CC DEGIL)",
        "dagitim": "hayir",
        "link": "http://fenix.ur.edu.pl/~mkepski/ds/uf.html",
        "atif": "UR Fall Detection Dataset (Kepski & Kwolek)",
        "betik": "python scripts/get_urfd_overhead.py",
        "not": "Yeniden dagitim izni yok -> HF deposuna KONULMAZ, betikle yerelde kurulur.",
    },
    "UCF-Crime": {
        "lisans": "Akademik/arastirma (CC DEGIL)",
        "dagitim": "hayir",
        "link": "https://www.crcv.ucf.edu/projects/real-world/",
        "atif": "UCF-Crime (Sultani et al., CVPR 2018)",
        "betik": "python scripts/get_ucf_many.py",
        "not": ("Yeniden dagitim izni yok -> HF deposuna ASLA KONULMAZ. Ayrica kliplerimiz "
                "ucuncu-taraf bir HF aynasindan cekiliyor; bu bilinen bir kirilganliktir "
                "(bkz. docs/veri_kaynaklari.md)."),
    },
    "Simuletic": {
        "lisans": "CC BY 4.0",
        "dagitim": "evet",
        "link": "https://huggingface.co/datasets/Simuletic/CCTV_Incident_Dataset_Fall_Lying_Down_Detection",
        "atif": "Simuletic CCTV Incident Dataset",
        "betik": "python scripts/get_lying.py",
        "not": "Lisans acik ama klipler DONMUS tek kare -> karantinada, olcume girmez, dagitilmaz.",
    },
    "DilAjanlari": {
        "lisans": "Apache-2.0 (bu projenin kendi uretimi)",
        "dagitim": "evet",
        "link": "https://github.com/ahmedberatAI/Dil-Ajanlari-Teknofest",
        "atif": "DilAjanlari / TEKNOFEST TYDA",
        "betik": None,
        "not": "Bozuk/bos/siyah dayaniklilik klipleri — bizim urettigimiz, serbest.",
    },
    "BILINMIYOR": {
        "lisans": "cozulemedi",
        "dagitim": "hayir",
        "link": None,
        "atif": None,
        "betik": None,
        "not": "Kaynagi cozulemeyen dosya FAIL-CLOSED ile dagitilamaz sayilir.",
    },
}


# =============================================================================
# 2) SET tanimlari — hangi dizin ne, kim kurar
# =============================================================================
SETLER: dict[str, dict[str, Any]] = {
    "eval_defense": {
        "aciklama": "Hedef-domain (Eskisehir uretim tesisi) tabakali set, 1080p, 100 anomali + 100 normal.",
        "tam_liste": True,
        "haric_dizin": (),
        "kurucu": ["python scripts/get_industrial.py", "python scripts/build_defense_eval.py"],
    },
    "eval_scenario": {
        "aciklama": "Senaryo seti: Fire (FIRESENSE) + Fall (GMDCSA + URFD) + Normal (Eskisehir + UCF).",
        "tam_liste": True,
        # _deprecated_frozen_fall: donmus PNG klipler, arsiv — olcume de dagitima da girmez.
        "haric_dizin": ("_deprecated_frozen_fall",),
        "kurucu": ["python scripts/get_firesense.py", "python scripts/get_gmdcsa.py",
                   "python scripts/get_urfd_overhead.py", "python scripts/build_scenario_eval.py"],
    },
    "eval_stress": {
        "aciklama": "Cetin negatifler: yangin-renkli ama yangin OLMAYAN sahneler (FIRESENSE neg).",
        "tam_liste": True,
        "haric_dizin": (),
        "kurucu": ["python scripts/get_firesense.py"],
    },
    "falls_real": {
        "aciklama": "GMDCSA-24 gercek dusme (Fall) + gunluk yasam (Normal) videolari.",
        "tam_liste": True,
        "haric_dizin": (),
        "kurucu": ["python scripts/get_gmdcsa.py"],
    },
    "falls_surveillance": {
        "aciklama": "URFD tavan/gozetim acili dusme klipleri.",
        "tam_liste": True,
        "haric_dizin": (),
        "kurucu": ["python scripts/get_urfd_overhead.py"],
    },
    "robust": {
        "aciklama": "Dayaniklilik testi: bozuk / bos / siyah / minik klipler (bizim uretimimiz).",
        "tam_liste": True,
        "haric_dizin": (),
        "kurucu": [],
    },
    "eval_tune": {
        "aciklama": "UCF-Crime eval_big'in AYAR yarisi (31 klip).",
        "tam_liste": True,
        "haric_dizin": (),
        "kurucu": ["python scripts/get_ucf_many.py", "python scripts/split_eval_big.py"],
    },
    "eval_holdout": {
        "aciklama": "UCF-Crime eval_big'in DOKUNULMAZ yarisi (32 klip) — yalnizca son olcum.",
        "tam_liste": True,
        "haric_dizin": (),
        "kurucu": ["python scripts/get_ucf_many.py", "python scripts/split_eval_big.py"],
    },
    "e2_vehicle": {
        "aciklama": "UCF RoadAccidents — arac/kalabalik (E2) kaniti.",
        "tam_liste": True,
        "haric_dizin": (),
        "kurucu": ["python scripts/get_vehicle_accidents.py"],
    },
    # --- Asagidakiler HAVUZ / ESKI setler: manifest'e yalnizca SET duzeyinde girer
    #     (dosya listesi tutulmaz; ya cok buyukler ya da bagimsiz kanit degiller).
    "eval": {
        "aciklama": "ESKI kucuk UCF seti — eval_big'in %100 alt kumesi, bagimsiz kanit DEGIL.",
        "tam_liste": False,
        "haric_dizin": (),
        "kurucu": ["python scripts/build_eval_set.py", "python scripts/get_normal_clips.py"],
    },
    "eval_big": {
        "aciklama": "UCF-Crime buyuk set (63 benzersiz) — tune/holdout bunun ayrik bolunmesidir.",
        "tam_liste": False,
        "haric_dizin": (),
        "kurucu": ["python scripts/get_ucf_many.py"],
    },
    "industrial": {
        "aciklama": "Eskisehir KAYNAK HAVUZU (691 klip, ~9.4 GB). Dagitilmaz: indirici zaten paralel ceker.",
        "tam_liste": False,
        "haric_dizin": (),
        "kurucu": ["python scripts/get_industrial.py"],
    },
}

#: UCF-Crime kategori klasorleri (dosya adi cozulemezse dizin adindan anlariz).
_UCF_KATEGORI = {
    "abuse", "arrest", "arson", "assault", "burglary", "explosion", "fighting",
    "roadaccidents", "robbery", "shooting", "shoplifting", "stealing", "vandalism",
}
_ESKISEHIR_AD = re.compile(r"^[0-7]_(tr|te)\d+\.", re.IGNORECASE)


def kaynak_bul(set_adi: str, rel: str) -> str:
    """Bir klibin KAYNAK VERI SETINI dosya adindan + konumundan cozer.

    Args:
        set_adi: ``data/`` altindaki ust set adi (or. ``eval_scenario``).
        rel: ``data/`` koku baz alinmis goreli yol (or. ``eval_scenario/Fall/x.mp4``).

    Returns:
        ``KAYNAKLAR`` sozlugunun anahtarlarindan biri; cozulemezse ``"BILINMIYOR"``.
        Cozulemeyen = dagitilamaz (fail-closed).
    """
    parcalar = rel.replace("\\", "/").split("/")
    ad = parcalar[-1].lower()
    dizinler = {p.lower() for p in parcalar[:-1]}

    # 1) Bastan sona tek kaynakli setler
    if set_adi in ("eval", "eval_big", "eval_tune", "eval_holdout", "e2_vehicle"):
        return "UCF-Crime"
    if set_adi in ("eval_defense", "industrial"):
        return "Eskisehir"
    if set_adi == "robust":
        return "DilAjanlari"

    # 2) Karisik setler -> dosya adi imzasi
    if ad.startswith("urfd_"):
        return "URFD"
    if ad.startswith("subject"):                      # Subject1_fall01 / Subject2_adl02
        return "GMDCSA-24"
    if ad.startswith(("posvideo", "negvideo", "testneg", "testpos",
                      "trainneg", "trainpos", "offvideo")):
        return "FIRESENSE"
    if ad.startswith("lying"):
        return "Simuletic"
    if ad.startswith("normal_videos_") or dizinler & _UCF_KATEGORI:
        return "UCF-Crime"
    if _ESKISEHIR_AD.match(ad):                       # 4_tr13.mp4, 0_te11.mp4
        return "Eskisehir"
    return "BILINMIYOR"


def dagitilabilir_mi(kaynak: str, kosullu_dahil: bool) -> bool:
    """Kaynagin yeniden dagitilabilirligi.

    Args:
        kaynak: ``KAYNAKLAR`` anahtari.
        kosullu_dahil: ``kosullu`` (Eskisehir/CC BY-NC celiskisi) setler dahil edilsin mi.
    """
    d = KAYNAKLAR.get(kaynak, KAYNAKLAR["BILINMIYOR"])["dagitim"]
    if d == "evet":
        return True
    if d == "kosullu":
        return kosullu_dahil
    return False


def kayit_dagitilabilir_mi(d: dict[str, Any], kosullu_dahil: bool) -> bool:
    """Tek bir manifest kaydi icin dagitim karari.

    Manifest'te ACIK bir ``dagitilabilir`` alani varsa (paketleyicinin izin-listesi
    karari) o esas alinir; yoksa kaynak-lisans tablosuna dusulur. Her iki yolda da
    bilinmeyen kaynak KAPALIDIR (fail-closed).
    """
    acik = d.get("dagitilabilir")
    if isinstance(acik, bool):
        return acik
    return dagitilabilir_mi(d.get("kaynak", "BILINMIYOR"), kosullu_dahil)


# =============================================================================
# 3) Yardimcilar
# =============================================================================
def md5_dosya(yol: str, blok: int = 1 << 20) -> str:
    """Dosyanin MD5'ini akis halinde hesapla (GB'lik klipler icin bellek dostu)."""
    h = hashlib.md5()
    with open(yol, "rb") as f:
        while True:
            b = f.read(blok)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _mb(bayt: int) -> str:
    """Insan-okunur boyut (robust/ gibi KB'lik setler '0.0 MB' gorunmesin)."""
    if bayt >= 1e9:
        return f"{bayt / 1e9:.2f} GB"
    if bayt >= 1e6:
        return f"{bayt / 1e6:.1f} MB"
    return f"{bayt / 1e3:.1f} KB"


def video_dosyalari(kok: str, haric: Iterable[str] = ()) -> list[str]:
    """``kok`` altindaki video dosyalarini ``kok``'e goreli, sirali dondurur."""
    haric_kume = {h.lower() for h in haric}
    bulunan: list[str] = []
    for dizin, alt_dizinler, dosyalar in os.walk(kok):
        alt_dizinler[:] = [d for d in alt_dizinler if d.lower() not in haric_kume]
        for d in dosyalar:
            if d.lower().endswith(VIDEO_UZANTI):
                tam = os.path.join(dizin, d)
                bulunan.append(os.path.relpath(tam, kok).replace("\\", "/"))
    return sorted(bulunan)


def manifest_yolu(arg: str | None) -> str | None:
    """Kullanilacak manifest yolunu sec.

    Oncelik: ``--manifest`` > paketleyicinin yazdigi kopya > indirilen kopya >
    depoya commit'lenen kopya. Paketleyici (``hf_dataset_push.py``) hangi klibin
    depoya GERCEKTEN girdigine karar veren taraftir; kopyasi varsa o esas alinir.
    """
    for aday in (arg, MANIFEST_PAKETLEYICI, MANIFEST_INDIRILEN, MANIFEST_YEREL):
        if aday and os.path.exists(aday):
            return aday
    return None


def manifest_uyarla(m: dict[str, Any]) -> dict[str, Any]:
    """``hf_dataset_push.py`` bicimini bu betigin ic bicimine cevirir.

    Iki arac ayni isin iki ucudur (paketleme / cekme) ve manifest semalari
    farklidir. Paketleyici DUZ bir ``klipler`` listesi yazar:
    ``{yol: "data/<set>/<...>", set, boyut, md5, kaynak, paketlendi, depo_yolu}``.
    Burada ``setler{... dosyalar[]}`` bicimine cevrilir.

    Onemli iki ayrim:
      * ``yol`` proje kokune goredir (``data/`` onekli) -> ``data/`` soyulur.
      * ``depo_yolu`` HF deposundaki hedeftir; yerel yoldan FARKLI olabilir,
        bu yuzden ayri tasinir.
      * ``paketlendi`` paketleyicinin IZIN LISTESI karari oldugu icin lisans
        konusunda OTORITEDIR; kendi kural motorumuzun onune gecer.
    """
    setler: dict[str, Any] = {}
    for k in m.get("klipler") or []:
        try:
            ham = str(k.get("yol", "")).replace("\\", "/")
            if not ham:
                continue
            yerel = ham[5:] if ham.startswith("data/") else ham
            set_adi = k.get("set") or yerel.split("/")[0]
            kayit = setler.setdefault(set_adi, {
                "aciklama": (m.get("set_ozeti", {}).get(set_adi, {}) or {}).get("aciklama", ""),
                "kurucu_betikler": SETLER.get(set_adi, {}).get("kurucu", []),
                "dosyalar": [],
                "kaynak_dagilimi": {},
                "klip": 0,
                "bayt": 0,
            })
            kaynak = k.get("kaynak") or "BILINMIYOR"
            giris = {
                "yol": yerel,
                "depo_yolu": k.get("depo_yolu") or yerel,
                "bayt": int(k.get("boyut") or 0),
                "kaynak": kaynak,
            }
            if k.get("md5"):
                giris["md5"] = k["md5"]
            if isinstance(k.get("paketlendi"), bool):
                giris["dagitilabilir"] = k["paketlendi"]
            kayit["dosyalar"].append(giris)
            kayit["kaynak_dagilimi"][kaynak] = kayit["kaynak_dagilimi"].get(kaynak, 0) + 1
            kayit["klip"] += 1
            kayit["bayt"] += giris["bayt"]
        except Exception:      # tek bozuk kayit tum manifesti cope atmasin
            continue
    return {**m, "setler": setler, "_uyarlandi": "hf_dataset_push.py bicimi"}


def manifest_oku(arg: str | None) -> dict[str, Any] | None:
    """Manifest'i oku. Yoksa/bozuksa ``None`` doner (cagiran taraf zarifce anlatir)."""
    yol = manifest_yolu(arg)
    if not yol:
        return None
    try:
        with open(yol, "r", encoding="utf-8") as f:
            m = json.load(f)
        # Paketleyici bicimi mi? (duz 'klipler' listesi, 'setler' sozlugu yok)
        if "setler" not in m and isinstance(m.get("klipler"), list):
            m = manifest_uyarla(m)
            print(f"# manifest bicimi uyarlandi (uretici: {m.get('uretici', '?')})", flush=True)
        m["_okundugu_yol"] = yol
        return m
    except Exception as e:  # bozuk JSON kullaniciyi cokertmemeli
        print(f"UYARI: manifest okunamadi ({yol}): {type(e).__name__}: {str(e)[:120]}", flush=True)
        return None


def manifest_yok_mesaji() -> None:
    print(
        "\nHATA: hf_manifest.json bulunamadi.\n"
        f"  Beklenen yer : {MANIFEST_YEREL}\n"
        "  Sebep        : ya kopyaniz eski ya da manifest henuz uretilmedi.\n"
        "  Cozum (uye)  : git pull\n"
        "  Cozum (kaptan): python scripts/hf_dataset_pull.py --make-manifest\n",
        flush=True)


# =============================================================================
# 4) --make-manifest  (KAPTAN)
# =============================================================================
def manifest_uret(secilen: list[str], cikti: str, hizli: bool) -> int:
    """Yerel ``data/`` dizinini tarayarak ``hf_manifest.json`` uretir.

    Args:
        secilen: manifest'e girecek set adlari.
        cikti: yazilacak JSON yolu.
        hizli: ``True`` ise MD5 hesaplanmaz (yalnizca boyut) — hizli taslak icin.
    """
    baslangic = time.time()
    setler_out: dict[str, Any] = {}
    toplam_dosya = toplam_bayt = 0

    for ad in secilen:
        tanim = SETLER[ad]
        kok = os.path.join(DATA, ad)
        if not os.path.isdir(kok):
            print(f"  {ad:<20} YOK (yerelde kurulmamis) — atlandi", flush=True)
            continue

        kayit: dict[str, Any] = {
            "aciklama": tanim["aciklama"],
            "kurucu_betikler": tanim["kurucu"],
            "dosya_listesi_var": bool(tanim["tam_liste"]),
        }
        rel_list = video_dosyalari(kok, tanim["haric_dizin"])
        kaynak_sayim: dict[str, int] = {}
        dosyalar: list[dict[str, Any]] = []
        set_bayt = 0

        for rel in rel_list:
            tam = os.path.join(kok, *rel.split("/"))
            try:
                bayt = os.path.getsize(tam)
            except OSError:
                continue
            kaynak = kaynak_bul(ad, f"{ad}/{rel}")
            kaynak_sayim[kaynak] = kaynak_sayim.get(kaynak, 0) + 1
            set_bayt += bayt
            if tanim["tam_liste"]:
                giris: dict[str, Any] = {
                    "yol": f"{ad}/{rel}",
                    "bayt": bayt,
                    "kaynak": kaynak,
                    "dagitim": KAYNAKLAR.get(kaynak, KAYNAKLAR["BILINMIYOR"])["dagitim"],
                }
                if not hizli:
                    try:
                        giris["md5"] = md5_dosya(tam)
                    except OSError as e:
                        giris["md5_hata"] = f"{type(e).__name__}"
                dosyalar.append(giris)

        kayit["klip"] = len(rel_list)
        kayit["bayt"] = set_bayt
        kayit["kaynak_dagilimi"] = dict(sorted(kaynak_sayim.items()))
        kayit["dagitilabilir_klip"] = sum(
            n for k, n in kaynak_sayim.items() if KAYNAKLAR.get(k, {}).get("dagitim") == "evet")
        kayit["kosullu_klip"] = sum(
            n for k, n in kaynak_sayim.items() if KAYNAKLAR.get(k, {}).get("dagitim") == "kosullu")
        kayit["kapali_klip"] = kayit["klip"] - kayit["dagitilabilir_klip"] - kayit["kosullu_klip"]
        if tanim["tam_liste"]:
            kayit["dosyalar"] = dosyalar
        setler_out[ad] = kayit
        toplam_dosya += len(rel_list)
        toplam_bayt += set_bayt
        print(f"  {ad:<20} {len(rel_list):>4} klip  {_mb(set_bayt):>9}  "
              f"acik={kayit['dagitilabilir_klip']} kosullu={kayit['kosullu_klip']} "
              f"kapali={kayit['kapali_klip']}", flush=True)

    manifest = {
        "_aciklama": ("DilAjanlari turev degerlendirme setleri manifesti. Her klip DOSYA "
                      "duzeyinde kaynagina ve lisansina baglanir. 'dagitim' alani: "
                      "evet = HF deposuna girer; kosullu = lisans celiskisi cozulunce girer; "
                      "hayir = ASLA girmez, yerelde kurucu betikle uretilir."),
        "surum": MANIFEST_SURUM,
        "uretim_zamani_utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "uretici": "scripts/hf_dataset_pull.py --make-manifest",
        "md5_var": not hizli,
        "hf_repo_yer_tutucu": YER_TUTUCU_REPO,
        "yarisma_notu": ("HF bu projede YALNIZCA veri/agirlik INDIRMEK icin kullanilir. "
                         "HF Inference API / Endpoints / Spaces ile MODEL CALISTIRMAK "
                         "yarisma kurallarinca YASAKTIR ve kullanilmamaktadir; cikarim "
                         "%100 yerel vLLM sunucusunda kosar."),
        "lisans_fail_closed": ("Kaynagi cozulemeyen dosya 'BILINMIYOR' isaretlenir ve "
                               "dagitilamaz sayilir."),
        "kaynaklar": KAYNAKLAR,
        "setler": setler_out,
        "toplam": {"klip": toplam_dosya, "bayt": toplam_bayt},
    }
    os.makedirs(os.path.dirname(os.path.abspath(cikti)) or ".", exist_ok=True)
    with open(cikti, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"\nMANIFEST YAZILDI -> {cikti}\n"
          f"  {toplam_dosya} klip, {_mb(toplam_bayt)}, "
          f"{time.time() - baslangic:.1f} sn (md5={'evet' if not hizli else 'HAYIR'})", flush=True)
    return 0


# =============================================================================
# 5) Plan uretimi (indirme oncesi; --list ve --dry-run bunu kullanir)
# =============================================================================
def plan_uret(manifest: dict[str, Any], secilen: list[str],
              kosullu_dahil: bool) -> tuple[list[dict[str, Any]], list[str]]:
    """Secilen setler icin (indirilecek_dosyalar, HF'de_olmayan_setler) ciftini uretir."""
    indirilecek: list[dict[str, Any]] = []
    hf_disi: list[str] = []
    for ad in secilen:
        kayit = manifest.get("setler", {}).get(ad)
        if kayit is None:
            hf_disi.append(ad)
            continue
        dosyalar = kayit.get("dosyalar") or []
        uygun = [d for d in dosyalar if kayit_dagitilabilir_mi(d, kosullu_dahil)]
        if not uygun:
            hf_disi.append(ad)
            continue
        indirilecek.extend(uygun)
    return indirilecek, hf_disi


def kurucu_oneri_bas(set_adlari: list[str], manifest: dict[str, Any]) -> None:
    """HF'de bulunmayan setler icin **dogru kurucu betigi** onerir (uydurma yok)."""
    if not set_adlari:
        return
    print("\n" + "=" * 74, flush=True)
    print("HF DEPOSUNDA OLMAYAN SETLER — lisans yeniden dagitima izin vermiyor.", flush=True)
    print("Bunlari YERELDE su betiklerle kurun (hepsi repoda mevcut):", flush=True)
    print("=" * 74, flush=True)
    for ad in set_adlari:
        kayit = manifest.get("setler", {}).get(ad, {})
        tanim = SETLER.get(ad, {})
        kurucu = kayit.get("kurucu_betikler") or tanim.get("kurucu") or []
        dagilim = kayit.get("kaynak_dagilimi") or {}
        kaynak_metin = ", ".join(f"{k}x{v}" for k, v in dagilim.items()) or "?"
        print(f"\n  data/{ad}   ({kayit.get('klip', '?')} klip · kaynak: {kaynak_metin})", flush=True)
        for k in sorted({d for d in dagilim if KAYNAKLAR.get(d, {}).get("dagitim") != "evet"}):
            print(f"      lisans: {k} -> {KAYNAKLAR.get(k, {}).get('lisans', '?')}", flush=True)
        if kurucu:
            for komut in kurucu:
                print(f"      $ {komut}", flush=True)
        else:
            print("      (kurucu betik tanimli degil — takima sorun)", flush=True)


def kismi_uyari_bas(manifest: dict[str, Any], secilen: list[str], kosullu_dahil: bool) -> None:
    """HF'den KISMEN gelen setleri (bazi klipleri lisans yuzunden disarida) uyarir."""
    satirlar: list[str] = []
    for ad in secilen:
        kayit = manifest.get("setler", {}).get(ad) or {}
        dosyalar = kayit.get("dosyalar") or []
        if not dosyalar:
            continue
        disarida = [d for d in dosyalar
                    if not kayit_dagitilabilir_mi(d, kosullu_dahil)]
        if disarida and len(disarida) < len(dosyalar):
            kaynaklar = sorted({d.get("kaynak", "?") for d in disarida})
            satirlar.append(f"  data/{ad}: {len(disarida)}/{len(dosyalar)} klip HF'de YOK "
                            f"(kaynak: {', '.join(kaynaklar)})")
            satirlar.append(f"      Seti TAMAMLAMAK icin data/{ad} KURUCU betiklerini kosun "
                            "(sirayla):")
            # Kaynagin genel indiricisi degil, SETIN kendi kurucu zinciri onerilir:
            # or. eval_scenario/Normal'daki UCF klipleri get_ucf_many.py degil,
            # build_scenario_eval.py tarafindan yerine konur.
            for b in (kayit.get("kurucu_betikler") or SETLER.get(ad, {}).get("kurucu") or []):
                satirlar.append(f"      $ {b}")
    if satirlar:
        print("\n" + "=" * 74, flush=True)
        print("DIKKAT — KISMEN gelen setler (set EKSIK kalir, olcum sayilari degisir):", flush=True)
        print("=" * 74, flush=True)
        for s in satirlar:
            print(s, flush=True)


# =============================================================================
# 6) Butunluk dogrulamasi (ag GEREKMEZ)
# =============================================================================
def butunluk_dogrula(manifest: dict[str, Any], secilen: list[str],
                     yalniz_dagitilabilir: bool, kosullu_dahil: bool) -> tuple[int, int, int]:
    """Yereldeki dosyalari manifest MD5'leri ile karsilastirir.

    Returns:
        ``(tamam, eksik, bozuk)`` sayilari.
    """
    tamam = eksik = bozuk = 0
    for ad in secilen:
        kayit = manifest.get("setler", {}).get(ad) or {}
        dosyalar = kayit.get("dosyalar") or []
        if not dosyalar:
            print(f"  {ad:<20} manifest'te dosya listesi yok — atlandi", flush=True)
            continue
        toplam_kayitli = len(dosyalar)
        if yalniz_dagitilabilir:
            dosyalar = [d for d in dosyalar
                        if kayit_dagitilabilir_mi(d, kosullu_dahil)]
        if not dosyalar:
            # "tamam=0 -> TAM" yanilticidir: burada HICBIR SEY kontrol edilmedi.
            print(f"  {ad:<20} kontrol edilmedi — {toplam_kayitli} klibin tamami lisans geregi "
                  "HF disi (--verify-all ile dogrulayin)", flush=True)
            continue
        s_tamam = s_eksik = s_bozuk = 0
        kotu_ornek: list[str] = []
        for d in dosyalar:
            tam = os.path.join(DATA, *d["yol"].split("/"))
            if not os.path.exists(tam):
                s_eksik += 1
                if len(kotu_ornek) < 3:
                    kotu_ornek.append(f"EKSIK  {d['yol']}")
                continue
            beklenen = d.get("md5")
            if not beklenen:                       # md5'siz manifest -> boyutla yetin
                if os.path.getsize(tam) == d.get("bayt"):
                    s_tamam += 1
                else:
                    s_bozuk += 1
                continue
            try:
                if md5_dosya(tam) == beklenen:
                    s_tamam += 1
                else:
                    s_bozuk += 1
                    if len(kotu_ornek) < 3:
                        kotu_ornek.append(f"BOZUK  {d['yol']}")
            except OSError as e:
                s_bozuk += 1
                if len(kotu_ornek) < 3:
                    kotu_ornek.append(f"OKUNAMADI {d['yol']} ({type(e).__name__})")
        durum = "TAM" if (s_eksik == 0 and s_bozuk == 0) else "EKSIK/BOZUK"
        print(f"  {ad:<20} tamam={s_tamam:<4} eksik={s_eksik:<4} bozuk={s_bozuk:<4} -> {durum}",
              flush=True)
        for ornek in kotu_ornek:
            print(f"      {ornek}", flush=True)
        tamam += s_tamam
        eksik += s_eksik
        bozuk += s_bozuk
    return tamam, eksik, bozuk


# =============================================================================
# 7) Indirme
# =============================================================================
def hf_yukle():
    """``huggingface_hub``'i ithal et; yoksa NET kurulum mesaji basip ``None`` don."""
    try:
        import huggingface_hub  # noqa: F401
        from huggingface_hub import hf_hub_download, list_repo_files
        from huggingface_hub import errors as hf_errors
        return hf_hub_download, list_repo_files, hf_errors, huggingface_hub.__version__
    except Exception as e:
        print("\n" + "=" * 74, flush=True)
        print("HATA: 'huggingface_hub' kurulu degil (veya ithal edilemedi).", flush=True)
        print(f"  Ayrinti: {type(e).__name__}: {str(e)[:140]}", flush=True)
        print("  Kurulum:  pip install \"huggingface_hub>=0.34\"", flush=True)
        print("  Ag yoksa: python scripts/hf_dataset_pull.py --list   (plani ag'siz gorursunuz)", flush=True)
        print("=" * 74, flush=True)
        return None


def depo_adi_dogrula(repo: str) -> bool:
    """Yer tutucu hala cozulmemisse NET ve YARDIMCI mesaj bas."""
    if "<" not in repo and ">" not in repo and "/" in repo:
        return True
    print("\n" + "=" * 74, flush=True)
    print("DEPO ADI VERILMEDI — indirme yapilamaz.", flush=True)
    print("=" * 74, flush=True)
    print(f"  Su anki deger : {repo}   (yer tutucu — HENUZ GERCEK BIR DEPO DEGIL)", flush=True)
    print("  Sebep         : HF dataset deposu HENUZ YAYINLANMADI.", flush=True)
    print("\n  Ne yapmali?", flush=True)
    print("   1) Depo yayinlandiysa adini verin:", flush=True)
    print("        python scripts/hf_dataset_pull.py --repo KULLANICI/dilajanlari-eval", flush=True)
    print("      veya kalici olarak:", flush=True)
    print("        export DILAJAN_HF_REPO=KULLANICI/dilajanlari-eval      # Linux/WSL/macOS", flush=True)
    print("        $env:DILAJAN_HF_REPO = \"KULLANICI/dilajanlari-eval\"   # Windows PowerShell", flush=True)
    print("   2) Depo HENUZ yayinlanmadiysa veriyi klasik yoldan kurun:", flush=True)
    print("        python scripts/hf_dataset_pull.py --list      # hangi set icin hangi betik", flush=True)
    print("   3) Yalniz arayuz/kod gelistirecekseniz VERIYE HIC GEREK YOK:", flush=True)
    print("        DILAJAN_MOCK=1 python app.py", flush=True)
    print("=" * 74, flush=True)
    return False


def depo_yokla(repo: str, revizyon: str, hf) -> tuple[set[str] | None, int]:
    """Depoyu SALT-OKUNUR yoklar: var mi, icinde hangi dosyalar var?

    Hem ``--dry-run`` hem gercek indirme bu adimdan gecer; boylece "depo yok"
    durumu GB indirmeden ONCE ve NET bir mesajla ogrenilir.

    Returns:
        ``(dosya_kumesi, 0)`` basarili · ``(None, 4)`` depo yok/kapali ·
        ``(None, 5)`` ag hatasi.
    """
    _hf_hub_download, list_repo_files, hf_errors, _surum = hf
    try:
        return set(list_repo_files(repo, repo_type="dataset", revision=revizyon)), 0
    except hf_errors.RepositoryNotFoundError:
        print("\n" + "=" * 74, flush=True)
        print(f"DEPO BULUNAMADI: {repo}  (repo_type=dataset)", flush=True)
        print("=" * 74, flush=True)
        print("  Olasi sebepler ve cozumleri:", flush=True)
        print("   * Depo HENUZ YAYINLANMADI  -> python scripts/hf_dataset_pull.py --list", flush=True)
        print("   * Ad yanlis yazildi        -> https://huggingface.co/datasets/<ad> adresini acin", flush=True)
        print("   * Depo OZEL (private)      -> once giris yapin:  hf auth login", flush=True)
        print("                                 veya HF_TOKEN ortam degiskenini ayarlayin", flush=True)
        print("   * Model deposu sanildi     -> bu bir DATASET deposudur, model degil", flush=True)
        print("\n  Veri olmadan da calisabilirsiniz:  DILAJAN_MOCK=1 python app.py", flush=True)
        print("=" * 74, flush=True)
        return None, 4
    except (hf_errors.GatedRepoError, hf_errors.DisabledRepoError) as e:
        print(f"\nDEPO ERISIME KAPALI ({type(e).__name__}): {repo}\n"
              "  HF sayfasindan kosullari kabul edip 'hf auth login' ile giris yapin.", flush=True)
        return None, 4
    except hf_errors.RevisionNotFoundError:
        print(f"\nSURUM/DAL BULUNAMADI: revision={revizyon!r} (depo: {repo})\n"
              "  --revision main ile deneyin.", flush=True)
        return None, 4
    except Exception as e:
        print(f"\nAG/ERISIM HATASI: {type(e).__name__}: {str(e)[:180]}\n"
              "  Internet baglantinizi kontrol edin. Ag'siz plan:  --list  ·  "
              "Ag'siz dogrulama: --verify", flush=True)
        return None, 5


def indir(repo: str, revizyon: str, indirilecek: list[dict[str, Any]], zorla: bool,
          hf, depo_dosyalari: set[str]) -> tuple[int, int, int]:
    """Dosyalari indirir. Var olan + MD5'i tutan dosyalari ATLAR.

    Returns:
        ``(indirilen, atlanan, basarisiz)`` sayilari.
    """
    hf_hub_download, _list_repo_files, _hf_errors, _surum = hf
    indirilen = atlanan = basarisiz = 0
    eksik_repoda: list[str] = []
    toplam = len(indirilecek)
    for i, d in enumerate(indirilecek, 1):
        rel = d["yol"]                                   # data/ altindaki YEREL yol
        depo_rel = d.get("depo_yolu") or rel             # HF deposundaki yol (farkli olabilir)
        hedef = os.path.join(DATA, *rel.split("/"))
        # a) Zaten var ve MD5 tutuyor mu?
        if not zorla and os.path.exists(hedef):
            try:
                if d.get("md5") and md5_dosya(hedef) == d["md5"]:
                    atlanan += 1
                    continue
                if not d.get("md5") and os.path.getsize(hedef) == d.get("bayt"):
                    atlanan += 1
                    continue
                print(f"  [{i}/{toplam}] MD5 TUTMADI, yeniden indiriliyor: {rel}", flush=True)
            except OSError:
                pass
        # b) Depoda gercekten var mi?
        if depo_dosyalari and depo_rel not in depo_dosyalari:
            eksik_repoda.append(depo_rel)
            basarisiz += 1
            continue
        # c) Indir (hf_hub kismi indirmeyi kendi .cache'inde surdurur)
        try:
            inen = hf_hub_download(repo_id=repo, filename=depo_rel, repo_type="dataset",
                                   revision=revizyon, local_dir=DATA)
            # Depo yolu yerel yoldan farkliysa dosyayi dogru yere tasi.
            if depo_rel != rel and os.path.abspath(inen) != os.path.abspath(hedef):
                os.makedirs(os.path.dirname(hedef), exist_ok=True)
                os.replace(inen, hedef)
            indirilen += 1
            if indirilen % 25 == 0 or indirilen == 1:
                print(f"  [{i}/{toplam}] indirildi: {rel}", flush=True)
        except Exception as e:                     # tek dosya hatasi tum isi bitirmesin
            basarisiz += 1
            print(f"  [{i}/{toplam}] HATA {rel}: {type(e).__name__}: {str(e)[:120]}", flush=True)

    if eksik_repoda:
        print(f"\n  UYARI: {len(eksik_repoda)} dosya manifest'te var ama DEPODA YOK. Ilk 5:", flush=True)
        for r in eksik_repoda[:5]:
            print(f"      {r}", flush=True)
        print("  -> Manifest deponun surumunden yeni olabilir: 'git pull' yapin veya "
              "--revision ile dogru surumu secin.", flush=True)
    return indirilen, atlanan, basarisiz


# =============================================================================
# 8) --upload-plan  (YALNIZCA METIN BASAR — HICBIR SEY YUKLENMEZ)
# =============================================================================
def upload_plani_bas(manifest: dict[str, Any], repo: str, kosullu_dahil: bool) -> None:
    """Kaptanin ELLE kosacagi yukleme komutlarini basar. Bu betik yukleme YAPMAZ."""
    print("=" * 74, flush=True)
    print("YUKLEME PLANI — SALT METIN.  BU BETIK HICBIR SEY YUKLEMEZ.", flush=True)
    print("Asagidaki komutlari, iceriklerini onayladiktan sonra SIZ calistiracaksiniz.", flush=True)
    print("=" * 74, flush=True)

    acik: list[str] = []
    kapali: dict[str, list[str]] = {}
    for ad, kayit in manifest.get("setler", {}).items():
        for d in kayit.get("dosyalar") or []:
            k = d.get("kaynak", "BILINMIYOR")
            if dagitilabilir_mi(k, kosullu_dahil):
                acik.append(d["yol"])
            else:
                kapali.setdefault(k, []).append(d["yol"])

    print(f"\nDAGITILACAK  : {len(acik)} klip", flush=True)
    print(f"DISARIDA     : {sum(len(v) for v in kapali.values())} klip", flush=True)
    for k, v in sorted(kapali.items()):
        print(f"    {k:<12} {len(v):>4} klip  — {KAYNAKLAR.get(k, {}).get('lisans', '?')}", flush=True)
    if not kosullu_dahil:
        print("\n  NOT: 'kosullu' kaynaklar (Eskisehir/Mendeley) VARSAYILAN OLARAK DISARIDA.", flush=True)
        print("       Lisans celiskisi makale metninden teyit edilene kadar boyle kalmalidir.", flush=True)
        print("       Teyit edilirse: --include-conditional ekleyin.", flush=True)

    print("\n--- ON KOSULLAR --------------------------------------------------------", flush=True)
    print("  pip install \"huggingface_hub>=0.34\"", flush=True)
    print("  hf auth login          # token GEREKIR; token'i bu betige VERMEYIN", flush=True)
    print("\n--- 1) DEPOYU OLUSTUR --------------------------------------------------", flush=True)
    print(f"  hf repo create {repo} --repo-type dataset", flush=True)
    print("\n--- 2) MANIFEST + KART -------------------------------------------------", flush=True)
    print(f"  hf upload {repo} hf_manifest.json hf_manifest.json --repo-type dataset", flush=True)
    print("  # README.md (dataset karti) icinde MUTLAKA bulunmasi gerekenler:", flush=True)
    print("  #   * her kaynagin ATFI ve LISANSI (asagidaki liste)", flush=True)
    print("  #   * 'UCF-Crime ve URFD klipleri BU DEPODA YOKTUR' beyani", flush=True)
    print("  #   * 'HF burada yalnizca VERI DAGITIMI icin kullanilir; model YERELDE kosar' notu", flush=True)
    for k, v in KAYNAKLAR.items():
        if k == "BILINMIYOR" or v["dagitim"] == "hayir":
            continue
        print(f"  #   - {k}: {v['lisans']}  |  {v['link']}", flush=True)
    print("\n--- 3) SETLERI YUKLE ---------------------------------------------------", flush=True)
    for ad, kayit in manifest.get("setler", {}).items():
        dosyalar = kayit.get("dosyalar") or []
        uygun = [d for d in dosyalar if kayit_dagitilabilir_mi(d, kosullu_dahil)]
        if not uygun:
            continue
        if len(uygun) == len(dosyalar):
            print(f"  hf upload {repo} data/{ad} {ad} --repo-type dataset"
                  f"    # {len(uygun)} klip, TAM set", flush=True)
        else:
            print(f"  # data/{ad}: {len(uygun)}/{len(dosyalar)} klip dagitilabilir -> "
                  f"TOPLU YUKLEME YAPMAYIN, once ayiklayin:", flush=True)
            alt = sorted({os.path.dirname(d["yol"]) for d in uygun})
            for a in alt:
                n = len([d for d in uygun if os.path.dirname(d["yol"]) == a])
                tum = len([d for d in dosyalar if os.path.dirname(d["yol"]) == a])
                if n == tum:
                    print(f"  hf upload {repo} data/{a} {a} --repo-type dataset"
                          f"    # {n} klip", flush=True)
                else:
                    print(f"  # {a}: {n}/{tum} klip -> DOSYA DOSYA yukleyin "
                          f"(karisik lisans!):", flush=True)
                    for d in uygun:
                        if os.path.dirname(d["yol"]) == a:
                            print(f"  hf upload {repo} data/{d['yol']} {d['yol']} --repo-type dataset",
                                  flush=True)
    print("\n" + "=" * 74, flush=True)
    print("HATIRLATMA: yukleme DISA ACIK bir islemdir. Yukledikten sonra geri almak", flush=True)
    print("zordur. Once --upload-plan ciktisini gozden gecirin, sonra elle kosun.", flush=True)
    print("=" * 74, flush=True)


# =============================================================================
# 9) --selftest  (AG YOK, VERI GEREKMEZ — repodaki --selftest gelenegine uyar)
# =============================================================================
def selftest() -> int:
    """Lisans siniflandirmasini ve indirme mantigini sahte HF ile dogrular.

    Ag kullanmaz, ``data/`` gerektirmez; GPU'suz makinede saniyeler surer.
    """
    import shutil
    import tempfile

    global DATA
    basari = True
    sonuc: list[str] = []

    def bak(ad: str, kosul: bool, ek: str = "") -> None:
        nonlocal basari
        sonuc.append(f"  [{'GECTI' if kosul else 'KALDI'}] {ad} {ek}")
        if not kosul:
            basari = False

    # --- A) Lisans siniflandirmasi (karisik setler dogru ayrisiyor mu?) ---
    vakalar = [
        ("eval_scenario", "eval_scenario/Fall/Subject1_fall01.mp4", "GMDCSA-24"),
        ("eval_scenario", "eval_scenario/Fall/urfd_fall01.mp4", "URFD"),
        ("eval_scenario", "eval_scenario/Fire/posVideo1.868.avi", "FIRESENSE"),
        ("eval_scenario", "eval_scenario/Normal/Normal_Videos_926_x264.mp4", "UCF-Crime"),
        ("eval_scenario", "eval_scenario/Normal/4_tr13.mp4", "Eskisehir"),
        ("eval_defense", "eval_defense/Anomali/Safe_Walkway_Violation/0_te11.mp4", "Eskisehir"),
        ("eval_tune", "eval_tune/Explosion/x.mp4", "UCF-Crime"),
        ("robust", "robust/black.mp4", "DilAjanlari"),
        ("eval_scenario", "eval_scenario/Fall/TANINMAYAN_AD.mp4", "BILINMIYOR"),
    ]
    for s, rel, bekle in vakalar:
        bulunan = kaynak_bul(s, rel)
        bak(f"kaynak_bul {rel.split('/')[-1]:<34} -> {bekle}", bulunan == bekle,
            f"(bulunan={bulunan})")

    bak("BILINMIYOR fail-CLOSED", dagitilabilir_mi("BILINMIYOR", True) is False)
    bak("UCF-Crime her kosulda kapali", dagitilabilir_mi("UCF-Crime", True) is False)
    bak("URFD her kosulda kapali", dagitilabilir_mi("URFD", True) is False)
    bak("Eskisehir varsayilan KAPALI", dagitilabilir_mi("Eskisehir", False) is False)
    bak("Eskisehir --include-conditional ile ACIK", dagitilabilir_mi("Eskisehir", True) is True)
    bak("FIRESENSE acik", dagitilabilir_mi("FIRESENSE", False) is True)

    # --- B) Indirme mantigi (sahte hf_hub_download; AG YOK) ---
    iyi, yeni = b"IYI-ICERIK", b"DEPODAN-GELEN"
    md5 = lambda b: hashlib.md5(b).hexdigest()  # noqa: E731
    tmp = tempfile.mkdtemp(prefix="dilajan_pull_selftest_")
    gercek_data = DATA
    try:
        DATA = tmp
        os.makedirs(os.path.join(tmp, "s"), exist_ok=True)
        with open(os.path.join(tmp, "s", "tutan.mp4"), "wb") as f:
            f.write(iyi)
        with open(os.path.join(tmp, "s", "tutmayan.mp4"), "wb") as f:
            f.write(b"BOZUK")

        dosyalar = [
            {"yol": "s/tutan.mp4", "bayt": len(iyi), "md5": md5(iyi), "kaynak": "DilAjanlari"},
            {"yol": "s/tutmayan.mp4", "bayt": len(yeni), "md5": md5(yeni), "kaynak": "DilAjanlari"},
            {"yol": "s/eksik.mp4", "bayt": len(yeni), "md5": md5(yeni), "kaynak": "DilAjanlari"},
            {"yol": "s/depoda_yok.mp4", "bayt": 1, "md5": md5(b"z"), "kaynak": "DilAjanlari"},
            {"yol": "s/patlayan.mp4", "bayt": 1, "md5": md5(b"q"), "kaynak": "DilAjanlari"},
        ]
        depo = {"s/tutan.mp4", "s/tutmayan.mp4", "s/eksik.mp4", "s/patlayan.mp4"}
        cagrilar: list[str] = []

        def sahte_indir(repo_id, filename, repo_type, revision, local_dir):
            cagrilar.append(filename)
            if filename == "s/patlayan.mp4":
                raise RuntimeError("simule edilmis ag hatasi")
            hedef = os.path.join(local_dir, *filename.split("/"))
            os.makedirs(os.path.dirname(hedef), exist_ok=True)
            with open(hedef, "wb") as f:
                f.write(yeni)
            return hedef

        class _Hatalar:
            class RepositoryNotFoundError(Exception): ...
            class GatedRepoError(Exception): ...
            class DisabledRepoError(Exception): ...
            class RevisionNotFoundError(Exception): ...

        sahte_hf = (sahte_indir, None, _Hatalar, "selftest")
        print("  (asagidaki cikti indirme simulasyonundandir)", flush=True)
        ind, atl, bas = indir("x/y", "main", dosyalar, False, sahte_hf, depo)
        bak("MD5 tutan dosya ATLANDI", "s/tutan.mp4" not in cagrilar and atl == 1, f"(atlanan={atl})")
        bak("MD5 tutmayan YENIDEN indirildi", "s/tutmayan.mp4" in cagrilar)
        bak("depoda olmayan indirilmedi", "s/depoda_yok.mp4" not in cagrilar)
        bak("indirilen=2", ind == 2, f"(indirilen={ind})")
        bak("basarisiz=2", bas == 2, f"(basarisiz={bas})")
        bak("tek dosya hatasi isi COKERTMEDI (fail-open)", "s/patlayan.mp4" in cagrilar)

        cagrilar.clear()
        indir("x/y", "main", [dosyalar[0]], True, sahte_hf, depo)
        bak("--force MD5 kontrolunu atlar", "s/tutan.mp4" in cagrilar)

        def yokla(hata):
            def liste(repo_id, repo_type, revision):
                raise hata("simule")
            return depo_yokla("x/y", "main", (sahte_indir, liste, _Hatalar, "t"))

        bak("RepositoryNotFound -> cikis 4", yokla(_Hatalar.RepositoryNotFoundError) == (None, 4))
        bak("GatedRepo -> cikis 4", yokla(_Hatalar.GatedRepoError) == (None, 4))
        bak("beklenmeyen hata -> cikis 5", yokla(ValueError) == (None, 5))

        # --- C) hf_dataset_push.py manifest bicimi ile birlikte calisabilirlik ---
        ham = {
            "uretici": "scripts/hf_dataset_push.py",
            "set_ozeti": {"eval_stress": {"aciklama": "cetin negatifler"}},
            "klipler": [
                {"yol": "data/eval_stress/Normal/a.avi", "set": "eval_stress", "boyut": 11,
                 "md5": "a" * 32, "kaynak": "FIRESENSE", "paketlendi": True,
                 "depo_yolu": "eval_stress/Normal/a.avi"},
                {"yol": "data/eval_tune/Explosion/b.mp4", "set": "eval_tune", "boyut": 22,
                 "md5": "b" * 32, "kaynak": "UCF-Crime", "paketlendi": False},
            ],
        }
        uy = manifest_uyarla(ham)
        bak("push bicimi -> setler sozlugu", set(uy["setler"]) == {"eval_stress", "eval_tune"})
        es = uy["setler"]["eval_stress"]["dosyalar"][0]
        bak("'data/' oneki soyuldu", es["yol"] == "eval_stress/Normal/a.avi", f"({es['yol']})")
        bak("'boyut' -> 'bayt'", es["bayt"] == 11)
        bak("depo_yolu korundu", es["depo_yolu"] == "eval_stress/Normal/a.avi")
        bak("paketlendi=True -> dagitilabilir", kayit_dagitilabilir_mi(es, False) is True)
        et = uy["setler"]["eval_tune"]["dosyalar"][0]
        bak("paketlendi=False -> dagitilamaz (izin listesi otoritedir)",
            kayit_dagitilabilir_mi(et, True) is False)
        bak("depo_yolu yoksa yerel yola duser", et["depo_yolu"] == "eval_tune/Explosion/b.mp4")
        bak("bozuk kayit tum manifesti cope atmaz",
            len(manifest_uyarla({"klipler": [{"bos": 1}, ham["klipler"][0]]})["setler"]) == 1)
    finally:
        DATA = gercek_data
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 74, flush=True)
    print("SELFTEST — hf_dataset_pull.py (ag YOK, data/ GEREKMEZ)", flush=True)
    print("=" * 74, flush=True)
    for s in sonuc:
        print(s, flush=True)
    print("-" * 74, flush=True)
    print("TUM SELFTESTLER GECTI" if basari else "SELFTEST BASARISIZ", flush=True)
    return 0 if basari else 1


# =============================================================================
# 10) CLI
# =============================================================================
def set_listesi_coz(arg: str | None, manifest: dict[str, Any] | None) -> list[str]:
    """``--sets`` degerini cozer. Varsayilan: manifest'te dosya listesi olan tum setler."""
    if arg and arg.strip().lower() not in ("all", "hepsi", ""):
        istenen = [s.strip() for s in arg.split(",") if s.strip()]
        bilinmeyen = [s for s in istenen if s not in SETLER]
        if bilinmeyen:
            print(f"UYARI: bilinmeyen set adi(lari): {', '.join(bilinmeyen)}", flush=True)
            print(f"  Gecerli setler: {', '.join(sorted(SETLER))}", flush=True)
        return [s for s in istenen if s in SETLER]
    if manifest:
        return [s for s in SETLER if s in manifest.get("setler", {})
                and (manifest["setler"][s].get("dosyalar") is not None)]
    return [s for s, t in SETLER.items() if t["tam_liste"]]


def liste_modu_bas(manifest: dict[str, Any], secilen: list[str], kosullu_dahil: bool) -> None:
    """Ag'siz plan ciktisi: hangi set nereden gelir."""
    print("=" * 74, flush=True)
    print("VERI PLANI (ag kullanilmadi)", flush=True)
    print(f"manifest: {manifest.get('_okundugu_yol')}  ·  uretim: "
          f"{manifest.get('uretim_zamani_utc', '?')}", flush=True)
    print("=" * 74, flush=True)
    print(f"{'set':<20} {'klip':>5} {'boyut':>10}  {'HF':>5} {'yerel':>6}  kaynak", flush=True)
    print("-" * 74, flush=True)
    hf_disi: list[str] = []
    for ad in secilen:
        kayit = manifest.get("setler", {}).get(ad) or {}
        dosyalar = kayit.get("dosyalar") or []
        uygun = [d for d in dosyalar if kayit_dagitilabilir_mi(d, kosullu_dahil)]
        # Dosya listesi olmayan setlerde (industrial/eval/eval_big) "yerel=0" YANILTICI olur:
        # sayilamadigi icin 0 gorunur. Bunlari acikca "-" ile isaretle.
        if dosyalar:
            var = str(sum(1 for d in dosyalar
                          if os.path.exists(os.path.join(DATA, *d["yol"].split("/")))))
        else:
            var = "-"
        dagilim = kayit.get("kaynak_dagilimi") or {}
        print(f"{ad:<20} {kayit.get('klip', 0):>5} {_mb(kayit.get('bayt', 0)):>10}  "
              f"{len(uygun):>5} {var:>6}  {', '.join(dagilim) or '-'}", flush=True)
        if not uygun:
            hf_disi.append(ad)
    print("-" * 74, flush=True)
    print("HF = bu setten HF deposuna KONABILECEK klip sayisi · yerel = simdi diskte olan", flush=True)
    kismi_uyari_bas(manifest, [s for s in secilen if s not in hf_disi], kosullu_dahil)
    kurucu_oneri_bas(hf_disi, manifest)
    print("\nYARISMA KURALI: HF burada yalnizca VERI/AGIRLIK INDIRMEK icin kullanilir.", flush=True)
    print("Model HF uzerinde CALISTIRILMAZ (Inference API/Endpoints/Spaces YASAK);", flush=True)
    print("cikarim %100 yerel vLLM sunucusunda kosar.", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=VARSAYILAN_REPO,
                    help=f"HF dataset deposu (varsayilan: {VARSAYILAN_REPO!r}; "
                         "DILAJAN_HF_REPO ortam degiskeni ile de verilebilir).")
    ap.add_argument("--revision", default="main", help="Depo dali/etiketi (varsayilan: main).")
    ap.add_argument("--sets", default=None,
                    help="Virgulle ayrilmis set adlari (or. eval_defense,eval_scenario). "
                         "Varsayilan: manifest'teki tum setler.")
    ap.add_argument("--manifest", default=None,
                    help="Alternatif manifest yolu (varsayilan: hf_manifest.json).")
    ap.add_argument("--list", "--plan", dest="liste", action="store_true",
                    help="AG YOK: hangi set HF'den gelir, hangisi betikle kurulur — plani bas.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Depoyu yoklar ve indirilecek/atlanacak dosyalari listeler; INDIRMEZ.")
    ap.add_argument("--verify", action="store_true",
                    help="AG YOK: yerel dosyalari manifest MD5'leri ile karsilastir.")
    ap.add_argument("--verify-all", action="store_true",
                    help="--verify ile birlikte: dagitilamayan (yerelde uretilen) setleri de dogrula.")
    ap.add_argument("--make-manifest", action="store_true",
                    help="(KAPTAN) Yerel data/ dizinini tarayip hf_manifest.json uret.")
    ap.add_argument("--manifest-out", default=MANIFEST_YEREL,
                    help="--make-manifest ciktisinin yolu.")
    ap.add_argument("--no-md5", action="store_true",
                    help="--make-manifest: MD5 hesaplama (hizli taslak; butunluk dogrulamasi zayiflar).")
    ap.add_argument("--upload-plan", action="store_true",
                    help="SALT METIN: kaptanin elle kosacagi yukleme komutlarini bas. YUKLEME YAPMAZ.")
    ap.add_argument("--include-conditional", action="store_true",
                    help="Lisansi 'kosullu' kaynaklari (Eskisehir/Mendeley) da dahil et. "
                         "Yalnizca lisans celiskisi TEYIT EDILDIKTEN sonra kullanin.")
    ap.add_argument("--force", action="store_true",
                    help="Var olan dosyalari MD5 kontrol etmeden yeniden indir.")
    ap.add_argument("--selftest", action="store_true",
                    help="AG YOK, VERI GEREKMEZ: lisans siniflandirmasi + indirme mantigi testleri.")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    # --- (A) Manifest uretimi: manifest'e ihtiyac duymaz -------------------
    if args.make_manifest:
        secilen = set_listesi_coz(args.sets, None) or list(SETLER)
        if not args.sets:
            secilen = list(SETLER)
        print(f"# data/ taraniyor -> {args.manifest_out}", flush=True)
        if not os.path.isdir(DATA):
            print(f"HATA: {DATA} yok. Once veriyi kurun.", flush=True)
            return 1
        return manifest_uret(secilen, args.manifest_out, hizli=args.no_md5)

    manifest = manifest_oku(args.manifest)
    if manifest is None:
        manifest_yok_mesaji()
        return 1
    secilen = set_listesi_coz(args.sets, manifest)
    kosullu = args.include_conditional

    # --- (B) Ag GEREKTIRMEYEN modlar --------------------------------------
    if args.upload_plan:
        upload_plani_bas(manifest, args.repo, kosullu)
        return 0

    if args.verify:
        print("=" * 74, flush=True)
        print(f"BUTUNLUK DOGRULAMASI (MD5) — manifest: {manifest.get('_okundugu_yol')}", flush=True)
        if not manifest.get("md5_var", True):
            print("UYARI: manifest MD5'siz uretilmis (--no-md5) -> yalnizca BOYUT karsilastirilir.",
                  flush=True)
        print("=" * 74, flush=True)
        tamam, eksik, bozuk = butunluk_dogrula(
            manifest, secilen, yalniz_dagitilabilir=not args.verify_all, kosullu_dahil=kosullu)
        print("-" * 74, flush=True)
        print(f"TOPLAM: tamam={tamam}  eksik={eksik}  bozuk={bozuk}", flush=True)
        if bozuk:
            print("\nBOZUK dosyalar icin: ayni komutu --force ile yeniden kosun.", flush=True)
        if eksik:
            print("EKSIK dosyalar icin: --repo ... ile indirin ya da asagidaki betikleri kosun.",
                  flush=True)
            _, hf_disi = plan_uret(manifest, secilen, kosullu)
            kurucu_oneri_bas(hf_disi, manifest)
        return 0 if (eksik == 0 and bozuk == 0) else 6

    if args.liste:
        liste_modu_bas(manifest, secilen, kosullu)
        return 0

    # --- (C) Indirme: once depo adi, sonra kutuphane ----------------------
    if not depo_adi_dogrula(args.repo):
        return 2
    hf = hf_yukle()
    if hf is None:
        return 3

    indirilecek, hf_disi = plan_uret(manifest, secilen, kosullu)
    print("=" * 74, flush=True)
    print(f"DEPO   : {args.repo}  (repo_type=dataset, revision={args.revision})", flush=True)
    print(f"HEDEF  : {DATA}", flush=True)
    print(f"PLAN   : {len(indirilecek)} dosya, {_mb(sum(d.get('bayt', 0) for d in indirilecek))}",
          flush=True)
    print("=" * 74, flush=True)

    # Depoyu SALT-OKUNUR yokla — dry-run'da da yapilir ki "depo yok" durumu
    # tek bayt indirilmeden ve NET bir mesajla ogrenilsin.
    print("  depo yoklaniyor (salt-okunur)...", flush=True)
    depo_dosyalari, hata = depo_yokla(args.repo, args.revision, hf)
    if depo_dosyalari is None:
        return hata
    print(f"  depoda {len(depo_dosyalari)} dosya var.", flush=True)

    if args.dry_run:
        var = indirilir = eksik_repoda = 0
        satirlar: list[str] = []
        for d in indirilecek:
            tam = os.path.join(DATA, *d["yol"].split("/"))
            if os.path.exists(tam):
                durum, var = "VAR", var + 1
            elif (d.get("depo_yolu") or d["yol"]) not in depo_dosyalari:
                durum, eksik_repoda = "DEPODA-YOK", eksik_repoda + 1
            else:
                durum, indirilir = "indir", indirilir + 1
            if len(satirlar) < 10:
                satirlar.append(f"    [{durum:<10}] {d['yol']}")
        print(f"  yerelde zaten var (atlanacak, MD5 ile teyit edilir): {var}", flush=True)
        print(f"  indirilecek                                        : {indirilir}", flush=True)
        print(f"  manifest'te var ama DEPODA YOK                     : {eksik_repoda}", flush=True)
        for s in satirlar:
            print(s, flush=True)
        if len(indirilecek) > 10:
            print(f"    ... (+{len(indirilecek) - 10} dosya daha)", flush=True)
        kismi_uyari_bas(manifest, secilen, kosullu)
        kurucu_oneri_bas(hf_disi, manifest)
        print("\nDRY-RUN: hicbir dosya indirilmedi.", flush=True)
        return 0

    indirilen, atlanan, basarisiz = indir(args.repo, args.revision, indirilecek, args.force,
                                          hf, depo_dosyalari)
    print("-" * 74, flush=True)
    print(f"INDIRME: yeni={indirilen}  atlandi(zaten dogru)={atlanan}  basarisiz={basarisiz}",
          flush=True)

    # Indirme sonrasi ZORUNLU butunluk dogrulamasi
    print("\n" + "=" * 74, flush=True)
    print("INDIRME SONRASI BUTUNLUK DOGRULAMASI (MD5)", flush=True)
    print("=" * 74, flush=True)
    tamam, eksik, bozuk = butunluk_dogrula(manifest, secilen, yalniz_dagitilabilir=not kosullu,
                                           kosullu_dahil=kosullu)
    print("-" * 74, flush=True)
    print(f"TOPLAM: tamam={tamam}  eksik={eksik}  bozuk={bozuk}", flush=True)

    kismi_uyari_bas(manifest, [s for s in secilen if s not in hf_disi], kosullu)
    kurucu_oneri_bas(hf_disi, manifest)
    if eksik or bozuk:
        print("\nBUTUNLUK DOGRULAMASI BASARISIZ -> eksik/bozuk dosyalar icin komutu "
              "--force ile yeniden kosun.", flush=True)
        return 6
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nIptal edildi (yarim indirme korunur; ayni komutu tekrar kosun).", flush=True)
        sys.exit(130)
