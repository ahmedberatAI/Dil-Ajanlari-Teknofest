#!/usr/bin/env python
"""OLCUM BUTUNLUGU DENETCISI: ``data/`` altindaki TUM degerlendirme setlerini tarar.

NEDEN VAR: bu depodaki en pahali hatalar model hatalari degil, OLCUM hatalariydi
ve hepsi ELLE bulundu. Set 40 klipten 200 klibe cikarken ayni hatalarin sessizce
geri gelmesi kacinilmazdir -- bu betik onlari OTOMATIK yakalar:

  K8  sahte klip   : ``eval_scenario/Fall`` altindaki 8 "dusme" klibi video degildi
                     (tek PNG'nin ``ffmpeg -loop`` ile sarilmasi; kare-arasi hareket 0).
  K9  sizinti      : ``data/eval``, ``data/eval_big``'in %100 ALT KUMESIYDI -> "bagimsiz
                     dogrulama" iddiasi gecersizdi.
  K10 mukerrer     : ayni MD5'li iki dosya paydayi sisiriyordu (Normal-FP paydasi 8
                     degil 7'ydi).
  K14 etiket hatasi: Mendeley class0-3 GUVENSIZ davranistir ama eski setlerde "Normal"
                     etiketliydi -> ajan DOGRU tespit ettiginde cezalandiriliyordu.
  K15 kucuk-n      : n=20'de tek klip orani ~%5 oynatir; kategori-duzeyi iddia kurulamaz.
  K16 confound     : etiket ile cozunurluk KORELE ise model olayi degil goruntu
                     keskinligini ayirt ediyor olabilir -- olcum gecersizdir.

DENETIMLER
  1) MUKERRER (MD5)            : set-ICI (payda sismesi) + setler-ARASI (capraz sayim)
  2) SIZINTI / ALT KUME        : bir set bir baskasinin alt kumesi mi (ust/alt iliskileri)
  3) SAHTE / BOZUK KLIP        : donmus, tek-kare-dongusu, <2 sn, <8 fps, okunamayan (PyAV)
  4) ETIKET TUTARSIZLIGI       : klip-ici (ad<->kategori) + MD5-arasi + ad-arasi celiskiler
  5) COZUNURLUK-ETIKET CONFOUND: anomali/normal cozunurluk dagilimi + korelasyon +
                                 "cozunurluk TEK BASINA etiketi ne kadar biliyor" testi
  6) SINIF DENGESI / KUCUK-n   : sinif basina n, dengesizlik, n<30 uyarisi
  7) BUTUNLUK EKLERI           : yarim indirme (*.part), MANIFEST.json <-> disk tutarliligi

SEVIYE POLITIKASI
  KRITIK -> olcumu GECERSIZ kilan, BELGELENMEMIS bulgu. Cikis kodu 1 (CI).
  UYARI  -> raporda not gerektiren ama bilinen/kacinilmaz durum (bkz. ``BILINEN`` listesi;
            ornegin K9 sizintisi ``data/EVAL_SETS.md``'de belgelenmistir). ``--strict``
            ile uyarilar da cikis kodunu 1 yapar.
  BILGI  -> karantina/kasitli-bozuk setlerdeki beklenen bulgular.

Sahte kesinlik uretmemek icin: bilinmeyen kategori icin ETIKET IDDIA EDILMEZ (None),
her sayim hem dosya hem BENZERSIZ ICERIK olarak raporlanir.

``data/`` altina HICBIR SEY YAZMAZ (yalnizca okur). Model/GPU GEREKTIRMEZ.

Kullanim:
  python scripts/audit_eval_sets.py
  python scripts/audit_eval_sets.py --json rapor.json
  python scripts/audit_eval_sets.py --only eval_defense,industrial --frames 12
  python scripts/audit_eval_sets.py --no-probe            # yalnizca MD5/etiket denetimleri (hizli)
  python scripts/audit_eval_sets.py --strict              # uyarilar da cikis kodu 1
  wsl.exe -d Ubuntu-24.04 -- /home/omen/teknofest/.venv/bin/python scripts/audit_eval_sets.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from itertools import combinations
from typing import Optional

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_SCRIPTS)
for _p in (ROOT, _SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ORTAK YARDIMCI: klip saglik olcumu verify_clips.py'de tanimli, burada TEKRAR YAZILMAZ.
from verify_clips import (  # noqa: E402
    DENETIM_ESIK,
    EXTS,
    PROBE_SURUM,
    Esikler,
    collect,
    cozunurluk,
    piksel,
    probe,
    sorunlar,
)

# --- istege bagli ic bagimliliklar (FAIL-OPEN: yoksa ilgili denetim ZAYIFLAR, cokmez) ---
try:
    from benchmark.labels import CATEGORY_EXPECT  # noqa: E402
except Exception as _e:  # pragma: no cover
    CATEGORY_EXPECT = {}
    print(f"[uyari] benchmark/labels.py okunamadi ({_e}) -> kategori etiketleri bilinmeyecek",
          flush=True)
try:
    # Mendeley xjmtb22pff sinif -> (ad, etiket) eslemesi; tek kaynak-dogru.
    from build_defense_eval import CLASS_MAP as IND_CLASS_MAP  # noqa: E402
except Exception as _e:  # pragma: no cover
    IND_CLASS_MAP = {}
    print(f"[uyari] build_defense_eval.CLASS_MAP okunamadi ({_e}) -> K14 denetimi zayif",
          flush=True)
try:
    from benchmark.stats_utils import wilson_ci  # noqa: E402
except Exception:  # pragma: no cover
    wilson_ci = None  # type: ignore

ANOM = "Anomali"
NORM = "Normal"
KRITIK, UYARI, BILGI = "KRITIK", "UYARI", "BILGI"

#: Olcum IDDIALARININ dayandigi setler. Kaynak: data/EVAL_SETS.md ozet tablosu +
#: scripts/eval_all_datasets.py DATASETS listesi. Buradaki bir kusur RAPORU BOZAR.
OLCUM_SETLERI = {
    "data/eval", "data/eval_big", "data/eval_tune", "data/eval_holdout",
    "data/eval_scenario", "data/eval_stress", "data/eval_defense",
    "data/falls_real", "data/falls_surveillance", "data/e2_vehicle", "data/temporal",
}

#: Bulgulari TASARIM GEREGI beklenen setler -> bulgular BILGI'ye dusurulur.
BEKLENEN_KUSURLU = {
    "data/robust": "kasitli bozuk klip seti (dayaniklilik testi) — bozukluk BEKLENIR",
}

#: BILINEN + BELGELENMIS durumlar. Imza -> gerekce. Bunlar KRITIK degil UYARI olarak
#: raporlanir (CI'yi kalici kirmiz yapmasinlar) ama ASLA sessize alinmaz.
#: Yeni bir madde eklemek = "bu kusuru biliyor ve kabul ediyoruz" demektir; gerekce
#: yazmadan eklenmemelidir.  --no-allowlist ile ham seviyeler gorulur.
BILINEN: dict[str, str] = {
    "SIZINTI:data/eval<=data/eval_big":
        "K9, belgelenmis (data/EVAL_SETS.md): data/eval, eval_big'in %100 alt kumesi. "
        "eval_clips.py kosuda uyari basar; temiz ayrik cift eval_tune + eval_holdout.",
    "MUKERRER_SET_ICI:data/eval/Normal:Normal_Videos_936_x264.mp4+Normal_Videos_937_x264.mp4":
        "K10, belgelenmis (data/EVAL_SETS.md): kaynak veri setinden gelen birebir kopya. "
        "eval_clips.py MD5 dedup ile eler -> gercek payda 7.",
    "MUKERRER_SET_ICI:data/eval_big/Normal:Normal_Videos_936_x264.mp4+Normal_Videos_937_x264.mp4":
        "K10, belgelenmis (data/EVAL_SETS.md): ayni kaynak kopyasi -> gercek payda 15.",
    "SIZINTI:data/falls_surveillance<=data/eval_scenario":
        "Belgelenmis (benchmark/labels.py DATASET_ORIGIN, data/eval_scenario/Fall notu): "
        "eval_scenario/Fall klipleri falls_real + falls_surveillance ile AYNI dosyalardir "
        "(hardlink). Ucu BIRLIKTE raporlanamaz; ayri ayri raporlanir.",
}

#: Bunun altinda kategori-duzeyi ORAN iddiasi kurulmamali (n=20'de 1 klip ~%5).
KUCUK_N = 30
#: Cozunurluk-etiket korelasyonu bu buyuklugu asarsa confound uyarisi.
CONFOUND_R = 0.5
#: Cozunurluk tek basina etiketi bu dogrulukla biliyorsa confound uyarisi.
CONFOUND_ACC = 0.80

#: Mendeley xjmtb22pff dosya adlandirmasi: "<sinif>_<te|tr><no>.mp4" (or. 0_tr128.mp4).
#: Kalip DISINDAKI adlardan sinif CIKARILMAZ (yanlis kanit uretmemek icin).
IND_AD_RE = re.compile(r"^([0-7])_(te|tr)\d+\.(mp4|avi|mkv|mov)$", re.IGNORECASE)

#: --verbose: toplulastirilmis bulgularin TAM listesini de bas (main() doldurur)
VERBOSE = False


# --------------------------------------------------------------------------- veri tipleri
@dataclass
class Klip:
    """Denetlenen tek klip + hakkinda toplanan tum kanitlar."""

    yol: str                      # mutlak yol
    rel: str                      # depo kokune goreli, '/' ayirici
    set_ad: str                   # or. "data/eval_big"
    kategori: str                 # set kokunun ALTINDAKI ilk klasor ("" -> kokte)
    alt: str                      # kategori altindaki koken klasoru ("" yoksa)
    ad: str                       # dosya adi
    karantina: bool               # set veya kategori '_' ile basliyor -> olcume alinmaz
    md5: Optional[str] = None
    boyut: int = 0
    inode: int = 0
    etiket_kat: Optional[str] = None   # kategori klasorunden gelen etiket
    sinif: Optional[str] = None        # Mendeley sinifi (varsa)
    etiket_ds: Optional[str] = None    # kaynak veri setinden gelen etiket
    olcum: dict = field(default_factory=dict)   # probe() sonucu
    kodlar: list[str] = field(default_factory=list)

    @property
    def etiket(self) -> Optional[str]:
        """Setin ILAN ETTIGI etiket (kategori klasoru). Bilinmiyorsa None."""
        return self.etiket_kat

    @property
    def etkin_etiket(self) -> Optional[str]:
        """Bu klip icin bilinen EN IYI etiket: once kategori, yoksa kaynak veri seti.

        Neden gerekli: ``data/industrial/class0`` bir semantik kategori DEGILDIR, bu
        yuzden kategori etiketi yoktur; ama Mendeley sinif eslemesi class0'i GUVENSIZ
        (Anomali) olarak tanimlar. Etiket celiskisi denetimi bu bilgiyi kullanmazsa
        havuz icindeki "ayni video hem GUVENSIZ hem GUVENLI" celiskisini KACIRIR
        (olculdu: 0_tr123 = 1_tr55 = 4_te4).
        """
        return self.etiket_kat or self.etiket_ds

    @property
    def etiket_kaynagi(self) -> str:
        """Etkin etiketin nereden geldigi (rapor seffafligi)."""
        if self.etiket_kat:
            return f"kategori '{self.kategori}'"
        if self.etiket_ds:
            return f"dataset class{self.sinif}"
        return "bilinmiyor"


@dataclass
class Bulgu:
    """Tek denetim bulgusu."""

    duzey: str
    kod: str
    baslik: str
    satirlar: list[str] = field(default_factory=list)
    bilinen: Optional[str] = None   # BILINEN listesindeki gerekce (varsa)

    def to_dict(self) -> dict:
        d = {"duzey": self.duzey, "kod": self.kod, "baslik": self.baslik,
             "satirlar": self.satirlar}
        if self.bilinen:
            d["bilinen_gerekce"] = self.bilinen
        return d


class Rapor:
    """Bulgulari toplar, seviye politikasini (allowlist / karantina) uygular."""

    def __init__(self, allowlist: bool = True) -> None:
        self.bulgular: list[Bulgu] = []
        self.allowlist = allowlist

    def ekle(self, duzey: str, kod: str, baslik: str,
             satirlar: Optional[list[str]] = None, imza: Optional[str] = None) -> Bulgu:
        gerekce = BILINEN.get(imza or "") if self.allowlist else None
        if gerekce and duzey == KRITIK:
            duzey = UYARI          # bilinen+belgelenmis -> CI'yi kirmaz, ama raporda kalir
        b = Bulgu(duzey, kod, baslik, list(satirlar or []), gerekce)
        self.bulgular.append(b)
        return b

    def say(self, duzey: str) -> int:
        return sum(1 for b in self.bulgular if b.duzey == duzey)

    def yaz(self, b: Bulgu) -> None:
        """Bulguyu konsola bas."""
        print(f"  [{b.duzey}] {b.baslik}", flush=True)
        for s in b.satirlar:
            print(f"      {s}", flush=True)
        if b.bilinen:
            print(f"      -> BILINEN: {b.bilinen}", flush=True)


# --------------------------------------------------------------------------- yardimcilar
def _rel(p: str) -> str:
    """Depo kokune goreli, '/' ayiricili yol."""
    try:
        return os.path.relpath(p, ROOT).replace("\\", "/")
    except ValueError:      # farkli surucu (Windows)
        return p.replace("\\", "/")


_MD5_CACHE: dict[tuple, str] = {}


def md5_of(path: str, chunk: int = 1 << 20) -> Optional[str]:
    """Dosya MD5'i; okunamazsa None (FAIL-OPEN -> "bilinmiyor", "ayni degil" DEMEZ).

    (dev, inode, boyut, mtime) anahtarli cache: HARDLINK'lenmis kopyalar (bu depoda
    eval_defense <-> industrial boyle) ikinci kez OKUNMAZ.
    """
    try:
        st = os.stat(path)
        key = ((st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns) if st.st_ino
               else (os.path.abspath(path), st.st_size, st.st_mtime_ns))
    except OSError:
        return None
    hit = _MD5_CACHE.get(key)
    if hit:
        return hit
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while True:
                b = f.read(chunk)
                if not b:
                    break
                h.update(b)
    except OSError:
        return None
    _MD5_CACHE[key] = h.hexdigest()
    return _MD5_CACHE[key]


def kategori_etiketi(kategori: str) -> Optional[str]:
    """Kategori klasoru adindan etiket. BILINMEYEN kategori -> None (iddia yok).

    benchmark/labels.py tek kaynak-dogrudur. Oradaki ``is_anomaly()`` bilinmeyen
    kategoriyi anomali VARSAYAR; denetimde bu yanlis olur (or. "fc_extract" bir
    etiket degil), bu yuzden burada acikca uyelik sorgulanir.
    """
    if not kategori or kategori.startswith("_"):
        return None
    kayit = CATEGORY_EXPECT.get(kategori)
    if not kayit:
        return None
    return ANOM if kayit[1] else NORM


def endustriyel_sinif(rel: str, ad: str) -> Optional[str]:
    """Klibin Mendeley sinifi ('0'..'7') veya None.

    Iki kanit: (1) yol ``industrial/classN`` altinda, (2) dosya adi dataset
    adlandirma kalibina uyuyor. Kalip disi ad -> None.
    """
    m = re.search(r"/industrial/class([0-7])/", "/" + rel.replace("\\", "/"))
    if m:
        return m.group(1)
    m2 = IND_AD_RE.match(ad)
    return m2.group(1) if m2 else None


def dataset_etiketi(sinif: Optional[str]) -> Optional[str]:
    """Mendeley sinifindan KAYNAK-DOGRU etiket (class0-3 GUVENSIZ -> Anomali)."""
    if not sinif:
        return None
    kayit = IND_CLASS_MAP.get(sinif)
    if not kayit:
        return None
    et = str(kayit[1]).strip().lower()
    return ANOM if et in ("anomali", "unsafe", "guvensiz") else NORM


def olcum_seti(set_ad: str) -> bool:
    """Set, olcum iddialarinin dayandigi setlerden biri mi?"""
    return set_ad in OLCUM_SETLERI


def _pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    """Pearson r (etiket ikili oldugunda = nokta-cift-serili korelasyon). Sabit dizi -> None."""
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / (sxx * syy) ** 0.5


def _en_iyi_esik(vals: list[float], etiketler: list[int]) -> tuple[float, float, str]:
    """"Tek bir sayisal esik etiketi ne kadar dogru biliyor?" testi.

    Returns:
        (en_iyi_dogruluk, esik, yon)  --  yon: ">" ise deger>esik -> anomali.
        Bu, cozunurluk-etiket confound'unun EN ANLASILIR olcusudur: dogruluk 1.0 ise
        model videoyu hic izlemeden yalnizca cozunurluge bakarak %100 "basarili" olur.
    """
    n = len(vals)
    if n == 0:
        return (0.0, 0.0, ">")
    adaylar = sorted(set(vals))
    # Orta noktalar + IKI UC esik. Uc esikler "hepsini ayni sinifa ata" kuralini temsil
    # eder; onlar olmadan tek-cozunurluklu bir sette dogruluk taban oranin ALTINA
    # duser ve rapor kafa karistirir (olculdu: data/eval %25 vs taban %75).
    esikler = ([adaylar[0] - 1.0]
               + [(a + b) / 2 for a, b in zip(adaylar, adaylar[1:])]
               + [adaylar[-1] + 1.0])
    en_iyi = (0.0, esikler[0], ">")
    for t in esikler:
        for yon in (">", "<"):
            dogru = sum(1 for v, y in zip(vals, etiketler)
                        if ((v > t) if yon == ">" else (v < t)) == bool(y))
            acc = dogru / n
            if acc > en_iyi[0]:
                en_iyi = (acc, t, yon)
    return en_iyi


def _ci_metni(n: int) -> str:
    """n buyuklugunde %50 gozlenen oran icin Wilson %95 araligi (kesinlik gostergesi)."""
    if not wilson_ci or n <= 0:
        return ""
    lo, hi = wilson_ci(n // 2, n)
    return f"p=%50 gozlenirse GA = [%{lo*100:.0f}–%{hi*100:.0f}] (+-%{(hi-lo)*50:.0f})"


# --------------------------------------------------------------------------- tarama
def setleri_bul(kok: str, only: list[str], haric: list[str]) -> dict[str, list[str]]:
    """``{set_adi: [video yollari]}``. Set = ``data/`` altindaki UST DUZEY dizin.

    Kokte duran basibos videolar ``data/(kok)`` sahte setinde toplanir (bunlar da
    yanlislikla olcume girebilir; gorunur olmalari gerekir).
    """
    setler: dict[str, list[str]] = {}
    if not os.path.isdir(kok):
        return setler
    kok_dosya = sorted(os.path.join(kok, f) for f in os.listdir(kok)
                       if f.lower().endswith(EXTS) and os.path.isfile(os.path.join(kok, f)))
    if kok_dosya:
        setler[_rel(kok) + "/(kok)"] = kok_dosya
    for ad in sorted(os.listdir(kok)):
        d = os.path.join(kok, ad)
        if not os.path.isdir(d):
            continue
        vids = collect([d])
        if vids:
            setler[_rel(d)] = vids

    def _tut(s: str) -> bool:
        if only and not any(o in s for o in only):
            return False
        if haric and any(h in s for h in haric):
            return False
        return True

    return {k: v for k, v in setler.items() if _tut(k)}


def klipleri_topla(setler: dict[str, list[str]]) -> list[Klip]:
    """Yol listelerini Klip nesnelerine cevir (etiket kanitlarini da doldurur)."""
    out: list[Klip] = []
    for set_ad, yollar in setler.items():
        set_kok = os.path.join(ROOT, *set_ad.split("/")) if not set_ad.endswith("(kok)") \
            else os.path.join(ROOT, *set_ad.split("/")[:-1])
        for p in yollar:
            rel = _rel(p)
            try:
                icsel = os.path.relpath(p, set_kok).replace("\\", "/")
            except ValueError:
                icsel = os.path.basename(p)
            parca = icsel.split("/")
            kategori = parca[0] if len(parca) > 1 else ""
            alt = parca[1] if len(parca) > 2 else ""
            ad = os.path.basename(p)
            sinif = endustriyel_sinif(rel, ad)
            out.append(Klip(
                yol=p, rel=rel, set_ad=set_ad, kategori=kategori, alt=alt, ad=ad,
                karantina=set_ad.split("/")[-1].startswith("_") or kategori.startswith("_"),
                etiket_kat=kategori_etiketi(kategori),
                sinif=sinif, etiket_ds=dataset_etiketi(sinif),
            ))
    return out


def hashle(klipler: list[Klip], jobs: int) -> None:
    """Tum kliplerin MD5 + boyut + inode bilgisini doldur (paralel, IO-bagli)."""
    def _one(k: Klip) -> None:
        k.md5 = md5_of(k.yol)
        try:
            st = os.stat(k.yol)
            k.boyut, k.inode = st.st_size, st.st_ino
        except OSError:
            pass

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        list(ex.map(_one, klipler))


def olcumle(klipler: list[Klip], esik: Esikler, jobs: int,
            cache_yol: Optional[str]) -> tuple[int, int]:
    """Klipleri PyAV ile olc (verify_clips.probe). ``(olculen, cache_isabet)`` dondurur.

    Cache anahtari MD5 + kare butcesi: ayni icerik (hardlink kopyalari dahil) BIR KEZ
    cozulur. ``--cache`` verilirse sonuclar JSON'a yazilir (data/ ALTINA DEGIL).
    """
    disk: dict[str, dict] = {}
    if cache_yol and os.path.isfile(cache_yol):
        try:
            with open(cache_yol, "r", encoding="utf-8") as f:
                disk = json.load(f) or {}
        except Exception:
            disk = {}
    bellek: dict[str, dict] = {}
    isabet = 0

    def _key(k: Klip) -> Optional[str]:
        # PROBE_SURUM anahtarda: olcum algoritmasi degisirse eski onbellek KULLANILMAZ.
        return f"{k.md5}:{esik.max_frames}:v{PROBE_SURUM}" if k.md5 else None

    # ayni icerigi tek kez coz: temsilci klip listesi
    temsilci: dict[str, Klip] = {}
    tekil: list[Klip] = []
    for k in klipler:
        key = _key(k)
        if key is None:
            tekil.append(k)
            continue
        if key not in temsilci:
            temsilci[key] = k
    yapilacak = [k for key, k in temsilci.items() if key not in disk] + tekil

    def _one(k: Klip) -> None:
        bellek[_key(k) or k.rel] = probe(k.yol, esik)

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        list(ex.map(_one, yapilacak))

    for k in klipler:
        key = _key(k)
        if key is not None and key in disk:
            k.olcum = dict(disk[key])
            isabet += 1
        else:
            k.olcum = dict(bellek.get(key or k.rel, {}))
        k.olcum.pop("path", None)
        k.kodlar = [kod for kod, _m in sorunlar(k.olcum, esik)] if k.olcum else []

    if cache_yol:
        disk.update({key: v for key, v in bellek.items() if ":" in key})
        try:
            os.makedirs(os.path.dirname(os.path.abspath(cache_yol)) or ".", exist_ok=True)
            with open(cache_yol, "w", encoding="utf-8") as f:
                json.dump(disk, f, ensure_ascii=False)
        except Exception as e:
            print(f"[uyari] cache yazilamadi: {type(e).__name__}: {str(e)[:80]}", flush=True)
    return (len(yapilacak), isabet)


# --------------------------------------------------------------------------- raporlama
def bolum(no: int, ad: str) -> None:
    print(f"\n{'=' * 78}\n[{no}] {ad}\n{'=' * 78}", flush=True)


def _seviye(set_ad: str, karantina: bool, temel: str = KRITIK) -> str:
    """Bulgu seviyesini setin NITELIGINE gore ayarla (karantina/kasitli-bozuk -> BILGI)."""
    if karantina or set_ad in BEKLENEN_KUSURLU:
        return BILGI
    if not olcum_seti(set_ad):
        return UYARI if temel == KRITIK else temel
    return temel


def set_ozeti(klipler: list[Klip], part: dict[str, int]) -> list[dict]:
    """Set basina sayimlar (dosya + BENZERSIZ ICERIK ayri ayri)."""
    rows: list[dict] = []
    by_set: dict[str, list[Klip]] = defaultdict(list)
    for k in klipler:
        by_set[k.set_ad].append(k)
    for s in sorted(by_set):
        ks = by_set[s]
        uniq_md5 = {k.md5 for k in ks if k.md5}
        rows.append({
            "set": s,
            "olcum_seti": olcum_seti(s),
            "karantina": all(k.karantina for k in ks),
            "klip": len(ks),
            "benzersiz": len(uniq_md5) + sum(1 for k in ks if not k.md5),
            "anomali": sum(1 for k in ks if k.etiket == ANOM),
            "normal": sum(1 for k in ks if k.etiket == NORM),
            "etiketsiz": sum(1 for k in ks if k.etiket is None),
            "part": part.get(s, 0),
            "kategoriler": dict(sorted(Counter(k.kategori or "(kok)" for k in ks).items())),
        })
    return rows


# --------------------------------------------------------------------------- 1) MUKERRER
def denetim_mukerrer(klipler: list[Klip], rap: Rapor) -> dict:
    bolum(1, "MUKERRER KLIP (MD5) — K10: payda sismesi / capraz sayim")
    by_md5: dict[str, list[Klip]] = defaultdict(list)
    for k in klipler:
        if k.md5:
            by_md5[k.md5].append(k)
    okunamayan = [k for k in klipler if not k.md5]

    # --- 1a) SET-ICI: ayni set icinde ayni icerik -> payda sisiyor
    print("\n 1a) SET-ICI mukerrer (paydayi SISIRIR)", flush=True)
    ic_gruplar: list[dict] = []
    ic: dict[tuple[str, str], list[Klip]] = defaultdict(list)
    for k in klipler:
        if k.md5:
            ic[(k.set_ad, k.md5)].append(k)
    # Ayni SEBEBI paylasan gruplar (ayni set + ayni kategori bilesimi) TEK bulguda
    # toplanir; aksi halde tek bir kusur (or. Mendeley class0/class1 cakismasi) onlarca
    # ayni satir uretip KRITIK listesini bogar. BILINEN listesinde kaydi olan gruplar
    # ayri ayri raporlanir (allowlist imzasi grup-basinadir).
    ham: list[dict] = []
    for (s, h), ks in sorted(ic.items()):
        if len(ks) < 2:
            continue
        adlar = sorted(k.ad for k in ks)
        kats = sorted({k.kategori or "(kok)" for k in ks})
        yer = f"{s}/{kats[0]}" if len(kats) == 1 else s
        karantina = all(k.karantina for k in ks)
        # Ayni icerik BIRDEN FAZLA kategori/sinif klasorunde ise bu yalnizca payda sismesi
        # degil ETIKET sorunudur: ya etiketlerden biri yanlis ya da siniflar ayrik degil.
        # Kaynak havuzda bile KRITIK'tir -- oradan kurulan sete sizar (bkz. eval_defense).
        duzey = KRITIK if (len(kats) > 1 and not karantina) else _seviye(s, karantina)
        ham.append({"set": s, "md5": h, "kategoriler": kats, "klipler": ks, "duzey": duzey,
                    "imza": f"MUKERRER_SET_ICI:{yer}:{'+'.join(adlar)}"})
        ic_gruplar.append({"set": s, "md5": h, "kategoriler": kats,
                           "yollar": [k.rel for k in ks]})

    kova: dict[tuple, list[dict]] = defaultdict(list)
    for g in ham:
        if BILINEN.get(g["imza"]):        # belgelenmis -> tek tek raporlanir
            kova[(g["set"], tuple(g["kategoriler"]), g["md5"])].append(g)
        else:
            kova[(g["set"], tuple(g["kategoriler"]), None)].append(g)

    for (s, kats, _tek), gruplar in sorted(kova.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        cok_kat = len(kats) > 1
        aciklama = (["Ayni video birden fazla sinif klasorunde: sinif-basina-n sayimlari "
                     "SISKIN ve bu havuzdan orneklem yapan betik ayni klibi IKI KEZ sete "
                     "koyabilir (etiketler ayrik degil)."] if cok_kat else
                    ["Ayni icerik iki kez sayiliyor -> PAYDA siskin."])
        if len(gruplar) == 1:
            g = gruplar[0]
            ks = g["klipler"]
            b = rap.ekle(g["duzey"], "MUKERRER_SET_ICI",
                         f"{s}: {len(ks)} dosya AYNI icerik (md5 {g['md5'][:12]}) -> gercek n = "
                         f"{len(ks)} degil 1"
                         + (f"   [{len(kats)} FARKLI kategori: {', '.join(kats)}]"
                            if cok_kat else f"   [{kats[0]}]"),
                         [f"{k.rel}  ({k.boyut/1e6:.1f} MB)" for k in ks] + aciklama,
                         imza=g["imza"])
        else:
            fazla = sum(len(g["klipler"]) - 1 for g in gruplar)
            satir = [f"{g['md5'][:12]}  " + "  =  ".join(k.rel for k in g["klipler"])
                     for g in (gruplar if VERBOSE else gruplar[:8])]
            if not VERBOSE and len(gruplar) > 8:
                satir.append(f"... +{len(gruplar)-8} grup daha (--verbose / --json)")
            yer = (f"{kats[0]} <-> {', '.join(kats[1:])} arasinda" if cok_kat
                   else f"{kats[0]} icinde")
            b = rap.ekle(gruplar[0]["duzey"], "MUKERRER_SET_ICI",
                         f"{s}: {len(gruplar)} mukerrer grup ({yer}) -> bu setin klip "
                         f"sayisi BENZERSIZ icerikten {fazla} FAZLA",
                         satir + aciklama)
        rap.yaz(b)
    if not ic_gruplar:
        print("      set-ici mukerrer YOK", flush=True)

    # --- 1b) SETLER-ARASI: ayni icerik birden fazla sette
    # Her MD5 icin ayri bulgu basmak raporu bogar (yuzlerce satir). Bulgular SET
    # BILESIMINE gore toplulastirilir; tam liste JSON'a ve --verbose ciktisina yazilir.
    print("\n 1b) SETLER-ARASI mukerrer (birlikte raporlanirsa CIFT SAYIM)", flush=True)
    capraz: list[dict] = []
    gruplu: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    for h, ks in sorted(by_md5.items()):
        setler = tuple(sorted({k.set_ad for k in ks}))
        if len(setler) < 2:
            continue
        hardlink = all(k.inode for k in ks) and len({k.inode for k in ks}) == 1
        kayit = {"md5": h, "setler": list(setler), "yollar": [k.rel for k in ks],
                 "etiketler": sorted({k.etiket for k in ks if k.etiket}), "hardlink": hardlink}
        capraz.append(kayit)
        gruplu[setler].append(kayit)

    for setler, kayitlar in sorted(gruplu.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        olcumlu = [s for s in setler if olcum_seti(s)]
        duzey = UYARI if len(olcumlu) >= 2 else BILGI
        hep_hardlink = all(k["hardlink"] for k in kayitlar)
        ornek = [f"{k['md5'][:12]}  " + " = ".join(k["yollar"]) for k in kayitlar[:3]]
        if len(kayitlar) > 3:
            ornek.append(f"... +{len(kayitlar)-3} grup daha (tam liste: --verbose / --json)")
        b = rap.ekle(duzey, "MUKERRER_SETLER_ARASI",
                     f"{len(kayitlar)} klip AYNI icerikle {len(setler)} sette: "
                     f"{', '.join(setler)}"
                     + ("  [hepsi ayni inode = hardlink]" if hep_hardlink else ""),
                     ([f"Bu {len(olcumlu)} OLCUM seti birlikte raporlanirsa ortak klipler "
                       f"iki kez sayilir."] if len(olcumlu) >= 2 else []) + ornek)
        rap.yaz(b)
    if not capraz:
        print("      setler-arasi mukerrer YOK", flush=True)
    elif VERBOSE:
        print("\n      --- tam liste (--verbose) ---", flush=True)
        for k in sorted(capraz, key=lambda k: (-len(k["setler"]), k["md5"])):
            print(f"      {k['md5'][:12]}  " + " = ".join(k["yollar"]), flush=True)

    if okunamayan:
        b = rap.ekle(UYARI, "HASH_ALINAMADI",
                     f"{len(okunamayan)} dosyanin MD5'i alinamadi -> mukerrer/etiket "
                     f"denetimlerinden HARIC (sessizce elenmediler)",
                     [k.rel for k in okunamayan[:20]])
        rap.yaz(b)

    print(f"\n  ozet: set-ici grup={len(ic_gruplar)}  setler-arasi grup={len(capraz)}  "
          f"okunamayan={len(okunamayan)}", flush=True)
    return {"set_ici": ic_gruplar, "setler_arasi": capraz,
            "okunamayan": [k.rel for k in okunamayan]}


# --------------------------------------------------------------------------- 2) SIZINTI
def denetim_sizinti(klipler: list[Klip], rap: Rapor) -> list[dict]:
    bolum(2, "SIZINTI / ALT KUME — K9: bir set baskasinin alt kumesi mi?")
    md5_set: dict[str, set[str]] = defaultdict(set)
    for k in klipler:
        if k.md5:
            md5_set[k.set_ad].add(k.md5)
    setler = sorted(s for s in md5_set if md5_set[s])
    iliskiler: list[dict] = []

    for a, b_ in combinations(setler, 2):
        sa, sb = md5_set[a], md5_set[b_]
        kesisim = sa & sb
        if not kesisim:
            continue
        if sa == sb:
            tur, alt, ust = "ESIT", a, b_
        elif sa <= sb:
            tur, alt, ust = "ALT_KUME", a, b_
        elif sb <= sa:
            tur, alt, ust = "ALT_KUME", b_, a
        else:
            tur, alt, ust = "KISMI", a, b_
        kucuk = min(len(sa), len(sb))
        oran = 100.0 * len(kesisim) / kucuk if kucuk else 0.0
        iliskiler.append({"tur": tur, "alt": alt, "ust": ust, "a": a, "b": b_,
                          "kesisim": len(kesisim), "n_a": len(sa), "n_b": len(sb),
                          "kucuk_yuzde": round(oran, 1)})

    if not iliskiler:
        print("      kesisen set cifti YOK (tum setler ayrik)", flush=True)
        return iliskiler

    for r in sorted(iliskiler, key=lambda r: (r["tur"] != "ESIT", r["tur"] != "ALT_KUME",
                                              -r["kesisim"])):
        a, b_ = r["a"], r["b"]
        ikisi_olcum = olcum_seti(a) and olcum_seti(b_)
        if r["tur"] in ("ESIT", "ALT_KUME"):
            imza = f"SIZINTI:{r['alt']}<={r['ust']}"
            duzey = KRITIK if ikisi_olcum else UYARI
            isaret = "==" if r["tur"] == "ESIT" else "<="
            bulgu = rap.ekle(duzey, "SIZINTI",
                             f"{r['alt']} {isaret} {r['ust']}  "
                             f"({r['kesisim']}/{min(r['n_a'], r['n_b'])} benzersiz klip = "
                             f"%{r['kucuk_yuzde']:.0f})",
                             ["BAGIMSIZ DEGIL: ayar+dogrulama ayni klipleri paylasiyorsa sonuc "
                              "IYIMSER cikar; bu ikisi BIRLIKTE raporlanamaz."],
                             imza=imza)
        else:
            duzey = UYARI if ikisi_olcum else BILGI
            bulgu = rap.ekle(duzey, "KISMI_ORTUSME",
                             f"{a} <-> {b_} kismi ortusme: {r['kesisim']} klip "
                             f"(kucuk setin %{r['kucuk_yuzde']:.0f}'i)",
                             ["Birlikte raporlanirsa ortak klipler IKI KEZ sayilir."])
        rap.yaz(bulgu)
    return iliskiler


# --------------------------------------------------------------------------- 3) BOZUK KLIP
#: KANITLI kusur: klibin degerlendirmeye uygun OLMADIGINI kanitlar (KRITIK)
KANITLI_KODLAR = {"COZULEMEDI", "KARE_YOK", "TEK_KARE_DONGUSU", "KISA", "DUSUK_FPS"}
#: ZAYIF kanit: "cok az hareket". Olculdu: gercek UCF-Crime klipleri de (statik kamera,
#: uzak/kucuk hareket) motion_max<0.5 verebiliyor (or. Normal_Videos_939 = 0.011) --
#: tek basina SAHTE KANITI DEGILDIR, insan gozuyle bakilmak uzere UYARI olarak listelenir.
ZAYIF_KODLAR = {"DONMUS"}


def _satir(k: Klip) -> str:
    """Sorunlu klip icin tek satir olcum ozeti."""
    o = k.olcum
    ad = (k.kategori + "/" if k.kategori else "") + k.ad
    if len(ad) > 44:                      # uzun adlar sutunu tasirmasin (nvidia dosyalari)
        ad = ad[:20] + "..." + ad[-21:]
    return (f"{ad:<46}"
            f"sure={o.get('sure_sn', '?')}s fps={o.get('fps', '?')} "
            f"{cozunurluk(o)} kare={o.get('kare', '?')} uniq={o.get('uniq_frames', '?')} "
            f"mot_mean={o.get('motion_mean', '?')} mot_max={o.get('motion_max', '?')} "
            f"[{o.get('ornekleme', '?')}]  -> {','.join(k.kodlar)}")


def denetim_bozuk(klipler: list[Klip], rap: Rapor, esik: Esikler) -> list[dict]:
    bolum(3, f"SAHTE / BOZUK KLIP — K8 (esik: <{esik.min_sec}sn, <{esik.min_fps}fps, "
             f"hareket<{esik.motion_eps})")
    olculdu = [k for k in klipler if k.olcum]
    if not olculdu:
        print("      olcum yok (--no-probe) -> bu denetim ATLANDI", flush=True)
        return []
    kotu = [k for k in olculdu if k.kodlar]
    rows: list[dict] = []
    by_set: dict[str, list[Klip]] = defaultdict(list)
    for k in kotu:
        by_set[k.set_ad].append(k)
        rows.append({"yol": k.rel, "set": k.set_ad, "kodlar": k.kodlar,
                     "kanitli": bool(set(k.kodlar) & KANITLI_KODLAR),
                     "karantina": k.karantina, "olcum": k.olcum})

    print("\n 3a) KANITLI kusurlu klip (cozulemeyen / tek-kare-dongusu / cok kisa / cok dusuk fps)",
          flush=True)
    n_kanitli = 0
    for s in sorted(by_set):
        ks = [k for k in by_set[s] if set(k.kodlar) & KANITLI_KODLAR]
        if not ks:
            continue
        n_kanitli += len(ks)
        hepsi_karantina = all(k.karantina for k in ks)
        not_ = BEKLENEN_KUSURLU.get(s)
        b = rap.ekle(_seviye(s, hepsi_karantina), "BOZUK_KLIP",
                     f"{s}: {len(ks)} KANITLI kusurlu klip"
                     + (f"   [{not_}]" if not_ else "")
                     + ("   [KARANTINA — olcume alinmaz]" if hepsi_karantina else ""),
                     [_satir(k) for k in ks])
        rap.yaz(b)
    if not n_kanitli:
        print("      kanitli kusurlu klip YOK", flush=True)

    print("\n 3b) ZAYIF kanit: COK AZ HAREKET (statik sahne de olabilir — insan gozu gerekir)",
          flush=True)
    n_zayif = 0
    for s in sorted(by_set):
        ks = [k for k in by_set[s]
              if (set(k.kodlar) & ZAYIF_KODLAR) and not (set(k.kodlar) & KANITLI_KODLAR)]
        if not ks:
            continue
        n_zayif += len(ks)
        hepsi_karantina = all(k.karantina for k in ks)
        b = rap.ekle(BILGI if (hepsi_karantina or s in BEKLENEN_KUSURLU) else UYARI,
                     "AZ_HAREKET",
                     f"{s}: {len(ks)} klipte kare-arasi hareket < {esik.motion_eps}",
                     [_satir(k) for k in ks]
                     + ["Bu tek basina 'sahte klip' KANITI DEGILDIR: gercek sabit-kamera "
                        "gozetim klipleri de bu araliga duser. Sette tutulacaksa, olayin "
                        "gorsel olarak var oldugu ELLE dogrulanmali."])
        rap.yaz(b)
    if not n_zayif:
        print("      az-hareketli klip YOK", flush=True)

    print(f"\n  ozet: {len(olculdu)} klip olculdu | KANITLI kusurlu={n_kanitli} | "
          f"az-hareketli={n_zayif}", flush=True)
    return rows


# --------------------------------------------------------------------------- 4) ETIKET
def denetim_etiket(klipler: list[Klip], rap: Rapor) -> dict:
    bolum(4, "ETIKET TUTARSIZLIGI — K14: ayni icerik iki sette FARKLI etiket")

    # --- 4a) KLIP-ICI: kaynak veri setinin sinifi ile bulundugu kategori celisiyor
    print("\n 4a) KLIP-ICI celiski (kaynak dataset sinifi <-> kategori klasoru)", flush=True)
    ici = [k for k in klipler if k.etiket and k.etiket_ds and k.etiket != k.etiket_ds
           and not k.karantina]
    if IND_CLASS_MAP:
        by_set: dict[str, list[Klip]] = defaultdict(list)
        for k in ici:
            by_set[k.set_ad].append(k)
        for s in sorted(by_set):
            ks = by_set[s]
            b = rap.ekle(KRITIK if olcum_seti(s) else UYARI, "ETIKET_CELISKI_KLIP_ICI",
                         f"{s}: {len(ks)} klip YANLIS etiketli (kaynak dataset sinifi baska diyor)",
                         [f"{k.rel}  kategori='{k.kategori}'({k.etiket}) ama "
                          f"class{k.sinif}='{IND_CLASS_MAP.get(k.sinif, ('?',))[0]}' -> "
                          f"{k.etiket_ds}" for k in ks])
            rap.yaz(b)
        if not ici:
            print("      celiski YOK (dataset sinifi ile kategori uyusuyor)", flush=True)
    else:
        print("      ATLANDI (CLASS_MAP okunamadi)", flush=True)

    # --- 4b) MD5-ARASI: ayni icerik farkli etiketlerle
    # Etiket kaynagi: kategori klasoru VEYA (kategori yoksa) kaynak veri seti sinifi.
    print("\n 4b) MD5-ARASI celiski (AYNI icerik, FARKLI etiket)", flush=True)
    by_md5: dict[str, list[Klip]] = defaultdict(list)
    for k in klipler:
        if k.md5 and not k.karantina:
            by_md5[k.md5].append(k)
    md5_celiski: list[dict] = []
    for h, ks in sorted(by_md5.items()):
        etiketler = {k.etkin_etiket for k in ks if k.etkin_etiket}
        if len(etiketler) > 1:
            b = rap.ekle(KRITIK, "ETIKET_CELISKI_MD5",
                         f"md5 {h[:12]}: AYNI video hem {' hem '.join(sorted(etiketler))} "
                         f"olarak etiketli",
                         [f"{k.rel}  -> {k.etkin_etiket}  ({k.etiket_kaynagi})" for k in ks]
                         + ["Bu icerik hem anomali hem normal paydasina girerse model ne "
                            "uretirse uretsin BIRINDE yanlis sayilir; iki yari BAGIMSIZ "
                            "OLMAZ. Set kurulurken bu icerik DISLANMALI."])
            rap.yaz(b)
            md5_celiski.append({"md5": h, "etiketler": sorted(etiketler),
                                "yollar": [f"{k.rel}={k.etkin_etiket}" for k in ks]})
    if not md5_celiski:
        print("      celiski YOK", flush=True)

    # --- 4c) AD-ARASI: ayni dosya adi farkli etiketle (md5 farkli olsa bile)
    print("\n 4c) AD-ARASI celiski (ayni dosya ADI, farkli etiket)", flush=True)
    by_ad: dict[str, list[Klip]] = defaultdict(list)
    for k in klipler:
        if not k.karantina:
            by_ad[k.ad].append(k)
    ad_celiski: list[dict] = []
    for ad, ks in sorted(by_ad.items()):
        etiketler = {k.etiket for k in ks if k.etiket}
        if len(etiketler) > 1:
            md5ler = {k.md5 for k in ks}
            b = rap.ekle(KRITIK, "ETIKET_CELISKI_AD",
                         f"'{ad}': ayni ad {', '.join(sorted(etiketler))} olarak etiketli"
                         + ("  (icerik de FARKLI -> ad cakismasi)" if len(md5ler) > 1 else ""),
                         [f"{k.rel}  -> {k.etiket}  md5={(k.md5 or '?')[:12]}" for k in ks])
            rap.yaz(b)
            ad_celiski.append({"ad": ad, "etiketler": sorted(etiketler),
                               "yollar": [f"{k.rel}={k.etiket}" for k in ks]})
    if not ad_celiski:
        print("      celiski YOK", flush=True)

    return {"klip_ici": [k.rel for k in ici], "md5": md5_celiski, "ad": ad_celiski}


# --------------------------------------------------------------------- 5) CONFOUND
def denetim_confound(klipler: list[Klip], rap: Rapor) -> list[dict]:
    bolum(5, "COZUNURLUK-ETIKET CONFOUND — K16: etiket cozunurlukten okunabiliyor mu?")
    olculdu = [k for k in klipler if k.olcum and piksel(k.olcum) > 0]
    if not olculdu:
        print("      olcum yok (--no-probe) -> bu denetim ATLANDI", flush=True)
        return []
    by_set: dict[str, list[Klip]] = defaultdict(list)
    for k in olculdu:
        if k.etiket and not k.karantina:
            by_set[k.set_ad].append(k)

    rows: list[dict] = []
    for s in sorted(by_set):
        ks = by_set[s]
        anom = [k for k in ks if k.etiket == ANOM]
        norm = [k for k in ks if k.etiket == NORM]
        c_an = Counter(cozunurluk(k.olcum) for k in anom)
        c_no = Counter(cozunurluk(k.olcum) for k in norm)
        print(f"\n  {s}   (anomali={len(anom)}, normal={len(norm)})", flush=True)
        print(f"      anomali cozunurluk: {dict(c_an.most_common()) or '-'}", flush=True)
        print(f"      normal  cozunurluk: {dict(c_no.most_common()) or '-'}", flush=True)
        if len(anom) < 3 or len(norm) < 3:
            print("      (tek etiket veya n<3 -> confound testi ANLAMSIZ, atlandi)", flush=True)
            continue
        vals = [float(piksel(k.olcum)) for k in ks]
        ys = [1 if k.etiket == ANOM else 0 for k in ks]
        r = _pearson(vals, [float(y) for y in ys])
        acc, esik_v, yon = _en_iyi_esik(vals, ys)
        taban = max(len(anom), len(norm)) / len(ks)
        ayrik = not (set(c_an) & set(c_no))
        print(f"      r(piksel, anomali) = {'-' if r is None else f'{r:+.2f}'}   "
              f"tek-esik dogrulugu = %{acc*100:.0f}  (taban %{taban*100:.0f}; "
              f"esik {esik_v/1e6:.2f} MP {yon})", flush=True)
        rows.append({"set": s, "n_anomali": len(anom), "n_normal": len(norm),
                     "anomali_cozunurluk": dict(c_an), "normal_cozunurluk": dict(c_no),
                     "r": None if r is None else round(r, 3),
                     "tek_esik_dogruluk": round(acc, 3), "taban": round(taban, 3),
                     "cozunurluk_ayrik": ayrik})
        if ayrik and acc >= 0.999:
            b = rap.ekle(KRITIK if olcum_seti(s) else UYARI, "CONFOUND_TAM",
                         f"{s}: cozunurluk etiketi TEK BASINA %100 belirliyor "
                         f"(anomali ve normal cozunurluk kumeleri AYRIK)",
                         ["Model videoyu HIC izlemeden yalnizca kare boyutuna bakarak "
                          "'basarili' olabilir; bu setteki recall/FP rakamlari olayi degil "
                          "GORUNTU KAYNAGINI olcuyor olabilir.",
                          f"anomali={dict(c_an)}  normal={dict(c_no)}"])
            rap.yaz(b)
        elif (r is not None and abs(r) >= CONFOUND_R) or acc >= max(CONFOUND_ACC, taban + 0.15):
            b = rap.ekle(UYARI, "CONFOUND_KISMI",
                         f"{s}: cozunurluk ile etiket KORELE (r={r if r is None else round(r, 2)}, "
                         f"tek-esik dogrulugu %{acc*100:.0f} vs taban %{taban*100:.0f})",
                         ["Sonuc raporunda bu karistirici acikca belirtilmeli; tek basina "
                          "'model olayi anliyor' iddiasi kurulamaz."])
            rap.yaz(b)
    if not rows:
        print("\n      confound testi uygulanabilir set YOK", flush=True)
    return rows


# --------------------------------------------------------------------- 6) DENGE / n
def denetim_denge(ozet: list[dict], rap: Rapor) -> None:
    bolum(6, f"SINIF DENGESI ve KUCUK-n — K15 (esik n<{KUCUK_N})")
    print(f"\n{'set':<34}{'klip':>6}{'benzrs':>8}{'anom':>6}{'norm':>6}{'etiketsiz':>10}  denge",
          flush=True)
    print("-" * 78, flush=True)
    for r in ozet:
        a, n = r["anomali"], r["normal"]
        denge = f"{a}:{n}" if (a or n) else "-"
        if a and n:
            oran = max(a, n) / min(a, n)
            denge += f"  ({oran:.1f}x)"
        print(f"{r['set']:<34}{r['klip']:>6}{r['benzersiz']:>8}{a:>6}{n:>6}"
              f"{r['etiketsiz']:>10}  {denge}", flush=True)
    print("-" * 78, flush=True)

    for r in ozet:
        s = r["set"]
        if not olcum_seti(s):
            continue
        a, n = r["anomali"], r["normal"]
        if a and n:
            if a < KUCUK_N or n < KUCUK_N:
                b = rap.ekle(UYARI, "KUCUK_N",
                             f"{s}: anomali={a}, normal={n} -> n<{KUCUK_N}; "
                             f"KATEGORI-DUZEYI oran iddiasi kurulamaz",
                             [f"anomali icin {_ci_metni(a)}",
                              f"normal  icin {_ci_metni(n)}",
                              "Kucuk n'de tek klip orani buyuk oynatir; nokta-deger yerine "
                              "Wilson GA ile raporlayin (benchmark/stats_utils.py)."])
                rap.yaz(b)
            if min(a, n) and max(a, n) / min(a, n) >= 2.0:
                b = rap.ekle(UYARI, "SINIF_DENGESIZ",
                             f"{s}: siniflar {max(a,n)/min(a,n):.1f}x dengesiz (anomali={a}, "
                             f"normal={n}) -> 'dogruluk' metrigi yaniltici",
                             ["Dengesiz sette taban dogruluk zaten yuksektir; recall ve FP "
                              "AYRI AYRI raporlanmali."])
                rap.yaz(b)
        elif (a or n) and not r["karantina"]:
            b = rap.ekle(UYARI, "TEK_ETIKET",
                         f"{s}: yalnizca {'anomali' if a else 'normal'} etiketli klip var "
                         f"(a={a}, n={n}) -> tek basina recall VEYA FP olculur, ikisi birden DEGIL")
            rap.yaz(b)
        if r["etiketsiz"]:
            b = rap.ekle(BILGI, "ETIKETSIZ",
                         f"{s}: {r['etiketsiz']} klibin kategorisi benchmark/labels.py'de "
                         f"TANIMSIZ -> etiket IDDIA EDILMEDI",
                         [f"kategoriler: {', '.join(k for k in r['kategoriler'])}"])
            rap.yaz(b)


# --------------------------------------------------------------------- 7) EKLER
def denetim_ekler(setler: dict[str, list[str]], klipler: list[Klip],
                  part: dict[str, int], rap: Rapor) -> list[dict]:
    bolum(7, "BUTUNLUK EKLERI — yarim indirme (*.part) + MANIFEST <-> disk")
    for s, n in sorted(part.items()):
        if n:
            b = rap.ekle(UYARI, "YARIM_INDIRME",
                         f"{s}: {n} adet *.part dosyasi var -> INDIRME SURUYOR, set su an EKSIK",
                         ["Bu set uzerinde su anda olcum yapmayin: n degisecek."])
            rap.yaz(b)
    if not any(part.values()):
        print("      yarim indirme (*.part) YOK", flush=True)

    rows: list[dict] = []
    by_set: dict[str, list[Klip]] = defaultdict(list)
    for k in klipler:
        by_set[k.set_ad].append(k)
    for s in sorted(setler):
        mpath = os.path.join(ROOT, *s.split("/"), "MANIFEST.json")
        if not os.path.isfile(mpath):
            continue
        try:
            with open(mpath, "r", encoding="utf-8") as f:
                man = json.load(f)
        except Exception as e:
            b = rap.ekle(UYARI, "MANIFEST_OKUNAMADI", f"{s}/MANIFEST.json okunamadi: {e}")
            rap.yaz(b)
            continue
        kayit = man.get("klipler")
        if not isinstance(kayit, list):
            print(f"      {s}/MANIFEST.json: 'klipler' alani yok -> atlandi", flush=True)
            continue
        disk_md5 = {k.md5: k.rel for k in by_set.get(s, []) if k.md5}
        eksik, md5_fark = [], []
        for r in kayit:
            hedef = str(r.get("hedef") or "").replace("\\", "/")
            beklenen = r.get("md5")
            tam = os.path.join(ROOT, *hedef.split("/")) if hedef else ""
            if hedef and not os.path.isfile(tam):
                eksik.append(hedef)
                continue
            if beklenen and tam:
                gercek = md5_of(tam)
                if gercek and gercek != beklenen:
                    md5_fark.append(f"{hedef}  manifest={beklenen[:12]} disk={gercek[:12]}")
        fazla = [rel for md5, rel in disk_md5.items()
                 if md5 not in {r.get("md5") for r in kayit}]
        beyan = (man.get("anomali_sayisi"), man.get("normal_sayisi"))
        gercek_a = sum(1 for k in by_set.get(s, []) if k.etiket == ANOM)
        gercek_n = sum(1 for k in by_set.get(s, []) if k.etiket == NORM)
        rows.append({"set": s, "manifest_klip": len(kayit), "disk_klip": len(by_set.get(s, [])),
                     "eksik": eksik, "md5_fark": md5_fark, "manifest_disi": fazla,
                     "beyan": list(beyan), "disk_anomali": gercek_a, "disk_normal": gercek_n})
        print(f"\n  {s}/MANIFEST.json: manifest={len(kayit)} klip, disk={len(by_set.get(s, []))} klip",
              flush=True)
        if eksik or md5_fark or fazla:
            b = rap.ekle(KRITIK if olcum_seti(s) else UYARI, "MANIFEST_UYUSMAZLIK",
                         f"{s}: MANIFEST ile disk UYUSMUYOR "
                         f"(eksik={len(eksik)}, md5_fark={len(md5_fark)}, "
                         f"manifest_disi={len(fazla)})",
                         [f"EKSIK: {p}" for p in eksik[:10]]
                         + [f"MD5 FARKLI: {p}" for p in md5_fark[:10]]
                         + [f"MANIFEST DISI (diskte var, manifestte yok): {p}" for p in fazla[:10]])
            rap.yaz(b)
        if beyan[0] is not None and (beyan[0] != gercek_a or beyan[1] != gercek_n):
            b = rap.ekle(KRITIK if olcum_seti(s) else UYARI, "MANIFEST_SAYIM",
                         f"{s}: MANIFEST anomali={beyan[0]}/normal={beyan[1]} diyor, "
                         f"diskte anomali={gercek_a}/normal={gercek_n}",
                         ["Rapordaki PAYDA yanlis olur; manifest yeniden uretilmeli "
                          "(scripts/build_defense_eval.py)."])
            rap.yaz(b)
        if not (eksik or md5_fark or fazla) and (beyan[0] is None or
                                                (beyan[0] == gercek_a and beyan[1] == gercek_n)):
            print("      manifest <-> disk TUTARLI", flush=True)
    if not rows:
        print("\n      MANIFEST.json bulunan set yok", flush=True)
    return rows


# --------------------------------------------------------------------------- main
YARIM_UZANTI = (".part", ".tmp", ".crdownload")


def part_sayimi(setler: dict[str, list[str]]) -> dict[str, int]:
    """Set basina yarim indirilmis (*.part) dosya sayisi.

    ``data/(kok)`` sahte seti icin YALNIZCA kokteki dosyalar sayilir; alt dizinlere
    inilmez (aksi halde her alt setin .part'lari koke de eklenir -> cift sayim).
    """
    out: dict[str, int] = {}
    for s in setler:
        base = os.path.join(ROOT, *s.split("/"))
        if s.endswith("(kok)"):
            base = os.path.dirname(base)
            try:
                out[s] = sum(1 for f in os.listdir(base)
                             if f.lower().endswith(YARIM_UZANTI)
                             and os.path.isfile(os.path.join(base, f)))
            except OSError:
                out[s] = 0
            continue
        n = 0
        for _dp, _dn, fns in os.walk(base):
            n += sum(1 for f in fns if f.lower().endswith(YARIM_UZANTI))
        out[s] = n
    return out


# --------------------------------------------------------------------------- selftest
def _sentetik_klip(yol: str, genislik: int, yukseklik: int, kare: int, fps: int,
                   hareketli: bool) -> bool:
    """Kucuk sentetik mp4 uret (PyAV ile). Hareketli: icinde gezen parlak blok.

    Selftest fixture'i icin: hicbir gercek klibe ve ``data/`` icerigine BAGLI OLMAZ.
    """
    try:
        import av
        import numpy as np
    except Exception:
        return False
    try:
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with av.open(yol, "w") as c:
            st = c.add_stream("mpeg4", rate=fps)   # her ffmpeg yapisinda bulunur
            st.width, st.height = genislik, yukseklik
            st.pix_fmt = "yuv420p"
            blok = max(8, min(genislik, yukseklik) // 6)
            for i in range(kare):
                arr = np.full((yukseklik, genislik, 3), 40, dtype=np.uint8)
                x = (i * max(1, (genislik - blok) // max(1, kare - 1))) if hareketli else 0
                x = min(x, genislik - blok)
                arr[yukseklik // 3: yukseklik // 3 + blok, x: x + blok] = 220
                for pkt in st.encode(av.VideoFrame.from_ndarray(arr, format="rgb24")):
                    c.mux(pkt)
            for pkt in st.encode():
                c.mux(pkt)
        return os.path.getsize(yol) > 0
    except Exception as e:
        print(f"  [selftest] klip uretilemedi ({yol}): {type(e).__name__}: {str(e)[:80]}",
              flush=True)
        return False


def selftest() -> int:
    """Denetleyicilerin FIILEN atesledigini sentetik fixture uzerinde dogrular.

    Neden gerekli: bu betigin tek isi kusur YAKALAMAK. Sessizce hicbir sey bulmayan
    bir denetci, kusursuz bir depodan AYIRT EDILEMEZ. Bu test her denetimin en az bir
    bilinen kusuru yakaladigini ve SAGLAM kliplere yanlis alarm URETMEDIGINI gosterir.
    ``data/`` OKUNMAZ, gecici dizinde calisir.
    """
    import shutil
    import tempfile

    kok = tempfile.mkdtemp(prefix="audit_selftest_")
    hatalar: list[str] = []

    def kontrol(ad: str, kosul: bool) -> None:
        print(f"  {'OK  ' if kosul else 'HATA'}  {ad}", flush=True)
        if not kosul:
            hatalar.append(ad)

    try:
        j = os.path.join
        # --- fixture ---
        # setA: kendi icinde mukerrer + yanlis etiketli (endustriyel ad kalibi) + bozuk klip
        saglam = j(kok, "setA", "Normal", "saglam.mp4")
        if not _sentetik_klip(saglam, 320, 240, 30, 10, hareketli=True):
            print("  [selftest] PyAV ile klip uretilemedi -> test ATLANDI", flush=True)
            return 0
        shutil.copyfile(saglam, j(kok, "setA", "Normal", "kopya.mp4"))          # 1a
        shutil.copyfile(saglam, j(kok, "setA", "Normal", "0_tr9999.mp4"))      # 4a (class0=Anomali)
        _sentetik_klip(j(kok, "setA", "Anomali", "donmus.mp4"), 320, 240, 30, 10,
                       hareketli=False)                                         # 3a TEK_KARE
        _sentetik_klip(j(kok, "setA", "Anomali", "kisa.mp4"), 320, 240, 8, 10,
                       hareketli=True)                                          # 3a KISA
        # setB: setA ile ayni icerigi TERS etikette tutar -> 1b + 4b + 4c
        os.makedirs(j(kok, "setB", "Anomali"), exist_ok=True)
        shutil.copyfile(saglam, j(kok, "setB", "Anomali", "saglam.mp4"))
        # setC: alt kume (setB'nin tamami) -> 2 SIZINTI
        os.makedirs(j(kok, "setC", "Anomali"), exist_ok=True)
        shutil.copyfile(saglam, j(kok, "setC", "Anomali", "saglam.mp4"))
        # setD: COZUNURLUK-ETIKET tam ayrisma -> 5 CONFOUND_TAM
        for i in range(3):
            _sentetik_klip(j(kok, "setD", "Anomali", f"buyuk{i}.mp4"), 640, 480, 30, 10, True)
            _sentetik_klip(j(kok, "setD", "Normal", f"kucuk{i}.mp4"), 320, 240, 30, 10, True)

        # --- denetimi kostur ---
        esik = replace(DENETIM_ESIK, max_frames=12)
        setler = setleri_bul(kok, [], [])
        klipler = klipleri_topla(setler)
        hashle(klipler, 2)
        olcumle(klipler, esik, 2, None)
        rap = Rapor()
        denetim_mukerrer(klipler, rap)
        denetim_sizinti(klipler, rap)
        bozuk = denetim_bozuk(klipler, rap, esik)
        denetim_etiket(klipler, rap)
        denetim_confound(klipler, rap)
        denetim_denge(set_ozeti(klipler, part_sayimi(setler)), rap)
        kodlar = {b.kod for b in rap.bulgular}

        print("\n--- SELFTEST SONUCLARI ---", flush=True)
        kontrol("1a set-ici mukerrer yakalandi", "MUKERRER_SET_ICI" in kodlar)
        kontrol("1b setler-arasi mukerrer yakalandi", "MUKERRER_SETLER_ARASI" in kodlar)
        kontrol("2 sizinti/alt kume yakalandi", "SIZINTI" in kodlar)
        kontrol("3a kanitli bozuk klip yakalandi", "BOZUK_KLIP" in kodlar)
        kontrol("3a tek-kare-dongusu kodu uretildi",
                any("TEK_KARE_DONGUSU" in r["kodlar"] for r in bozuk))
        kontrol("3a kisa klip kodu uretildi", any("KISA" in r["kodlar"] for r in bozuk))
        kontrol("4a klip-ici etiket celiskisi yakalandi (K14 imzasi)",
                "ETIKET_CELISKI_KLIP_ICI" in kodlar)
        kontrol("4b md5-arasi etiket celiskisi yakalandi", "ETIKET_CELISKI_MD5" in kodlar)
        kontrol("4c ad-arasi etiket celiskisi yakalandi", "ETIKET_CELISKI_AD" in kodlar)
        kontrol("5 tam cozunurluk-etiket confound yakalandi", "CONFOUND_TAM" in kodlar)
        # YANLIS ALARM kontrolu: saglam klipler bozuk listesinde OLMAMALI
        saglam_adlar = {"saglam.mp4", "kopya.mp4", "0_tr9999.mp4"} | {
            f"{o}{i}.mp4" for o in ("buyuk", "kucuk") for i in range(3)}
        yanlis = [r["yol"] for r in bozuk if os.path.basename(r["yol"]) in saglam_adlar]
        kontrol(f"saglam kliplere yanlis alarm yok ({len(yanlis)} yanlis)", not yanlis)
        if yanlis:
            for y in yanlis:
                print(f"        yanlis alarm: {y}", flush=True)
    finally:
        shutil.rmtree(kok, ignore_errors=True)

    print(f"\n{'TUM SELFTESTLER GECTI' if not hatalar else str(len(hatalar)) + ' SELFTEST BASARISIZ: ' + ', '.join(hatalar)}",
          flush=True)
    return 1 if hatalar else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true",
                    help="sentetik fixture uzerinde denetleyicileri dogrula (data/ OKUNMAZ)")
    ap.add_argument("--root", default=os.path.join(ROOT, "data"),
                    help="taranacak kok (varsayilan: <depo>/data)")
    ap.add_argument("--only", default="", help="yalniz adinda bu altdizgeler gecen setler (virgullu)")
    ap.add_argument("--exclude", default="", help="bu altdizgeleri iceren setleri atla (virgullu)")
    ap.add_argument("--json", nargs="?", const="-", default=None, metavar="DOSYA",
                    help="makine-okur rapor; DOSYA verilmezse stdout")
    ap.add_argument("--no-probe", action="store_true",
                    help="PyAV ile klip cozme (bozuk/confound denetimleri) YAPMA — hizli mod")
    ap.add_argument("--frames", type=int, default=24,
                    help="klip basina cozulecek en fazla kare (varsayilan 24)")
    ap.add_argument("--min-sec", type=float, default=DENETIM_ESIK.min_sec,
                    help=f"asgari klip suresi (varsayilan {DENETIM_ESIK.min_sec})")
    ap.add_argument("--min-fps", type=float, default=DENETIM_ESIK.min_fps,
                    help=f"asgari fps (varsayilan {DENETIM_ESIK.min_fps})")
    ap.add_argument("--jobs", type=int, default=4, help="paralel is parcacigi (varsayilan 4)")
    ap.add_argument("--cache", default=None,
                    help="olcum onbellegi JSON yolu (data/ ALTINA VERMEYIN)")
    ap.add_argument("--strict", action="store_true", help="UYARI da cikis kodunu 1 yapar")
    ap.add_argument("--no-allowlist", action="store_true",
                    help="BILINEN (belgelenmis) durumlari da KRITIK say")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="toplulastirilmis bulgularin TAM listesini de bas")
    args = ap.parse_args()

    global VERBOSE
    VERBOSE = args.verbose
    if args.selftest:
        return selftest()

    esik = replace(DENETIM_ESIK, min_sec=args.min_sec, min_fps=args.min_fps,
                   max_frames=max(2, args.frames))
    only = [x.strip() for x in args.only.split(",") if x.strip()]
    haric = [x.strip() for x in args.exclude.split(",") if x.strip()]

    t0 = time.time()
    print("=" * 78, flush=True)
    print("OLCUM BUTUNLUGU DENETIMI  (scripts/audit_eval_sets.py)", flush=True)
    print("=" * 78, flush=True)
    setler = setleri_bul(args.root, only, haric)
    if not setler:
        print(f"video iceren set bulunamadi: {args.root}", flush=True)
        return 0
    klipler = klipleri_topla(setler)
    part = part_sayimi(setler)

    print(f"kok={_rel(args.root)}  set={len(setler)}  klip={len(klipler)}  "
          f"probe={'KAPALI' if args.no_probe else f'acik ({esik.max_frames} kare)'}  "
          f"jobs={args.jobs}", flush=True)
    print("MD5 hesaplaniyor...", flush=True)
    hashle(klipler, args.jobs)
    if not args.no_probe:
        print("klipler PyAV ile olculuyor (GPU gerekmez)...", flush=True)
        n_yeni, n_cache = olcumle(klipler, esik, args.jobs, args.cache)
        print(f"  olculen benzersiz icerik={n_yeni}  onbellekten={n_cache}", flush=True)

    ozet = set_ozeti(klipler, part)
    rap = Rapor(allowlist=not args.no_allowlist)

    bolum(0, "SETLER")
    print(f"{'set':<34}{'klip':>6}{'benzrs':>8}{'anom':>6}{'norm':>6}{'?':>4}{'part':>6}  nitelik",
          flush=True)
    print("-" * 78, flush=True)
    for r in ozet:
        nitelik = []
        if r["olcum_seti"]:
            nitelik.append("OLCUM")
        if r["karantina"]:
            nitelik.append("karantina")
        if r["set"] in BEKLENEN_KUSURLU:
            nitelik.append("kasitli-bozuk")
        if not nitelik:
            nitelik.append("kaynak/havuz")
        print(f"{r['set']:<34}{r['klip']:>6}{r['benzersiz']:>8}{r['anomali']:>6}"
              f"{r['normal']:>6}{r['etiketsiz']:>4}{r['part']:>6}  {','.join(nitelik)}",
              flush=True)
    print("-" * 78, flush=True)
    print(f"{'TOPLAM':<34}{sum(r['klip'] for r in ozet):>6}"
          f"{len({k.md5 for k in klipler if k.md5}):>8}"
          f"{sum(r['anomali'] for r in ozet):>6}{sum(r['normal'] for r in ozet):>6}"
          f"{sum(r['etiketsiz'] for r in ozet):>4}{sum(part.values()):>6}", flush=True)

    mukerrer = denetim_mukerrer(klipler, rap)
    sizinti = denetim_sizinti(klipler, rap)
    bozuk = denetim_bozuk(klipler, rap, esik)
    etiket = denetim_etiket(klipler, rap)
    confound = denetim_confound(klipler, rap)
    denetim_denge(ozet, rap)
    manifest = denetim_ekler(setler, klipler, part, rap)

    n_k, n_u, n_b = rap.say(KRITIK), rap.say(UYARI), rap.say(BILGI)
    print(f"\n{'=' * 78}\nOZET\n{'=' * 78}", flush=True)
    print(f"set={len(setler)}  klip={len(klipler)}  "
          f"benzersiz icerik={len({k.md5 for k in klipler if k.md5})}  "
          f"sure={time.time()-t0:.1f}s", flush=True)
    print(f"KRITIK={n_k}   UYARI={n_u}   BILGI={n_b}", flush=True)
    def _liste(duzey: str, baslik: str, limit: int) -> None:
        secim = [b for b in rap.bulgular if b.duzey == duzey]
        if not secim:
            return
        print(f"\n{baslik}", flush=True)
        for b in secim[:limit] if not VERBOSE else secim:
            print(f"  - [{b.kod}] {b.baslik}"
                  + ("   (BILINEN/belgelenmis)" if b.bilinen else ""), flush=True)
        if not VERBOSE and len(secim) > limit:
            print(f"  ... +{len(secim)-limit} bulgu daha (yukaridaki bolumlerde / --verbose)",
                  flush=True)

    if n_k:
        _liste(KRITIK, "KRITIK bulgular (olcumu GECERSIZ kilar):", 40)
    else:
        print("\nKRITIK bulgu YOK.", flush=True)
    _liste(UYARI, "UYARI bulgulari (raporda not gerektirir):", 25)

    if args.json:
        cikti = {
            "kok": _rel(args.root),
            "olculdu": time.strftime("%Y-%m-%d %H:%M:%S"),
            "probe": not args.no_probe,
            "esikler": {"min_sec": esik.min_sec, "min_fps": esik.min_fps,
                        "motion_eps": esik.motion_eps, "max_frames": esik.max_frames},
            "setler": ozet,
            "mukerrer": mukerrer,
            "sizinti": sizinti,
            "bozuk_klipler": bozuk,
            "etiket_celiskileri": etiket,
            "confound": confound,
            "manifest": manifest,
            "bulgular": [b.to_dict() for b in rap.bulgular],
            "ozet": {"kritik": n_k, "uyari": n_u, "bilgi": n_b,
                     "klip": len(klipler),
                     "benzersiz": len({k.md5 for k in klipler if k.md5})},
        }
        metin = json.dumps(cikti, indent=1, ensure_ascii=False)
        if args.json == "-":
            print("\n" + metin, flush=True)
        else:
            with open(args.json, "w", encoding="utf-8") as f:
                f.write(metin)
            print(f"\nJSON rapor -> {args.json}", flush=True)

    return 1 if (n_k or (args.strict and n_u)) else 0


if __name__ == "__main__":
    sys.exit(main())
