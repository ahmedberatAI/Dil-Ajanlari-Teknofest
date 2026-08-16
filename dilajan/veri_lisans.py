#!/usr/bin/env python
"""VERI LISANS KAPISI — hangi veri dizini NE ICIN kullanilabilir. GPU GEREKMEZ.

NEDEN BU DOSYA VAR
------------------
Bazi veri setleri **degerlendirmede serbest ama egitimde YASAK**tir:

  * `data/isafety_bench` — **CC BY-NC-SA 4.0**. ShareAlike ZEHIRLI HAPTIR: bu
    veriyle ince ayar yapilirsa model agirliklari turev eser sayilabilir ve
    modelimiz de CC BY-NC-SA olmak zorunda kalir. NonCommercial ayrica ticari
    gelecegi kapatir. (HANDOFF §6.3 takim karari.)

Bu kural bir BELGEDE kalirsa aylar sonra biri farkinda olmadan cigner. Bu modul
kurali **makine-okunur** yapar ve `egitim_icin_dogrula()` ile **kod duzeyinde**
kilitler. `tests/test_isg_lisans.py` kilidi surekli sinar.

TASARIM
-------
Kaynak-dogru **veri dizinindeki `LISANS.json`** dosyasidir (indirme betigi yazar).
Boylece kural veriyle BIRLIKTE seyahat eder; birisi seti elle kopyalasa bile
kunye yaninda gider. Asagidaki `BILINEN` tablosu yalnizca kunye YOKSA devreye
giren guvenli varsayilandir.

K3 FAIL-OPEN DEGIL — BU KAPI BILEREK FAIL-CLOSED
------------------------------------------------
Projenin geri kalani fail-open'dir (hicbir yeni kod analizi cokertmez). Ama
LISANS kapisi TERSIDIR: supheli durumda **egitimi durdurur**. Gerekce: yanlis
alarm bir analizde tolere edilebilir, lisans ihlali edilemez.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Kunye dosyasi YOKSA kullanilacak guvenli varsayilanlar (goreli yol -> kural).
#: "egitim" = ince ayar/damitma/agirlik uretimi. "degerlendirme" = olcum.
BILINEN: Dict[str, dict] = {
    "data/isafety_bench": {
        "lisans": "CC BY-NC-SA 4.0",
        "egitimde_kullanilabilir": False,
        "degerlendirmede_kullanilabilir": True,
        "gerekce": "ShareAlike agirliklari turev eser yapabilir; NonCommercial ticari kullanimi kapatir",
    },
    "data/industrial": {
        "lisans": "CC BY 4.0 (muhafazakar okuma: CC BY-NC)",
        "egitimde_kullanilabilir": True,
        "degerlendirmede_kullanilabilir": True,
        "gerekce": ("Mendeley xjmtb22pff. ⚠️ KVKK: taninabilir calisanlar — BAYTLAR "
                    "YENIDEN YAYIMLANMAZ. Ayrica eval_defense buradan orneklenmistir: "
                    "burada ince ayar yapilirsa O SET KIRLENIR."),
    },
    "data/eval_defense": {
        "lisans": "data/industrial ile ayni",
        "egitimde_kullanilabilir": False,
        "degerlendirmede_kullanilabilir": True,
        "gerekce": "DEGERLENDIRME setidir; uzerinde egitim yapmak olcumu gecersiz kilar",
    },
    "data/eval_holdout": {
        "lisans": "UCF-Crime (arastirma)",
        "egitimde_kullanilabilir": False,
        "degerlendirmede_kullanilabilir": True,
        "gerekce": "dogrulama (holdout) seti — egitimde kullanilirsa sizinti olur",
    },
    "data/ppe": {
        "lisans": "CC BY 4.0",
        "egitimde_kullanilabilir": True,
        "degerlendirmede_kullanilabilir": True,
        "gerekce": ("KKD YOLO dogrulayicisi icin BILEREK izin verici lisansli setler "
                    "secildi. SH17 (alan eslesmesi EN IYI olan aday) CC BY-NC-SA "
                    "oldugu icin ELENDI. ⚠️ ALAN FARKI: setler SANTIYE, tesisimiz URETIM."),
    },
    "data/ppe_yolo": {
        "lisans": "CC BY 4.0 (data/ppe'den turetilmis)",
        "egitimde_kullanilabilir": True,
        "degerlendirmede_kullanilabilir": True,
        "gerekce": ("scripts/ppe_coco2yolo.py ciktisi — kaynak lisansi CC BY 4.0 "
                    "oldugu icin turev de serbest. Yelek sinifi BILEREK yok "
                    "(egitimde 66 kutu; dogrulayici icin yetersiz)."),
    },
}


class LisansIhlali(RuntimeError):
    """Lisans/olcum-butunlugu kurali cignendi. BILEREK yakalanmamalidir."""


def _kunye_yolu(dizin: str) -> str:
    return os.path.join(dizin, "LISANS.json")


def kunye_oku(dizin: str) -> Optional[dict]:
    """Veri dizinindeki LISANS.json'u okur (yoksa/bozuksa None)."""
    yol = _kunye_yolu(dizin if os.path.isabs(dizin) else os.path.join(ROOT, dizin))
    if not os.path.exists(yol):
        return None
    try:
        with open(yol, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _normalize(yol: str) -> str:
    """Mutlak/goreli yolu depo-koku goreli, ileri-bolulu bicime cevirir."""
    p = os.path.abspath(yol if os.path.isabs(yol) else os.path.join(ROOT, yol))
    try:
        rel = os.path.relpath(p, ROOT)
    except ValueError:            # farkli surucu (Windows)
        return p.replace("\\", "/")
    return rel.replace("\\", "/")


def kural_bul(yol: str) -> Optional[dict]:
    """Yol icin gecerli kurali dondurur: once KUNYE, sonra BILINEN tablosu.

    Yol bir ALT dizin olabilir (or. data/isafety_bench/videos/hazard) — en UZUN
    eslesen kayit kullanilir.
    """
    rel = _normalize(yol)
    en_iyi: Optional[str] = None
    for onek in BILINEN:
        if rel == onek or rel.startswith(onek + "/"):
            if en_iyi is None or len(onek) > len(en_iyi):
                en_iyi = onek
    # KUNYE her zaman onceliklidir (veriyle birlikte seyahat eder)
    kok = en_iyi or rel
    kunye = kunye_oku(kok)
    if kunye is not None:
        return {**BILINEN.get(kok, {}), **kunye, "_kaynak": "LISANS.json", "_dizin": kok}
    if en_iyi is not None:
        return {**BILINEN[en_iyi], "_kaynak": "BILINEN tablosu", "_dizin": en_iyi}
    return None


def egitimde_kullanilabilir(yol: str) -> bool:
    """Bu yol EGITIMDE kullanilabilir mi? Kural yoksa True (bilinmeyen veri serbest).

    NOT: bilinmeyen veri icin True donmesi kasitlidir — bu kapi BILINEN yasaklari
    zorlar, tum veriyi beyaz-listeye almaz. Yeni bir kisitli set eklenirse
    BILINEN'e (veya kunyesine) YAZILMALIDIR.
    """
    k = kural_bul(yol)
    return True if k is None else bool(k.get("egitimde_kullanilabilir", True))


def degerlendirmede_kullanilabilir(yol: str) -> bool:
    k = kural_bul(yol)
    return True if k is None else bool(k.get("degerlendirmede_kullanilabilir", True))


def egitim_icin_dogrula(yollar: List[str] | str) -> None:
    """EGITIM yolunun BASINDA cagrilir. Yasakli dizin varsa ISTISNA FIRLATIR.

    FAIL-CLOSED (K3'un bilerek istisnasi): supheli durumda egitimi durdurur.
    Lisans ihlali, bir analizin cokmesinden daha pahalidir.

    Kullanim:
        from dilajan.veri_lisans import egitim_icin_dogrula
        egitim_icin_dogrula(["data/industrial", "data/ppe"])   # -> sessizce gecer
        egitim_icin_dogrula("data/isafety_bench")              # -> LisansIhlali
    """
    if isinstance(yollar, str):
        yollar = [yollar]
    ihlaller = []
    for y in yollar:
        if not egitimde_kullanilabilir(y):
            k = kural_bul(y) or {}
            ihlaller.append(
                f"  ⛔ {_normalize(y)}\n"
                f"     lisans : {k.get('lisans', '?')}\n"
                f"     gerekce: {k.get('gerekce', '?')}\n"
                f"     kaynak : {k.get('_kaynak', '?')}"
            )
    if ihlaller:
        raise LisansIhlali(
            "EGITIMDE KULLANILAMAZ veri tespit edildi — islem DURDURULDU:\n"
            + "\n".join(ihlaller)
            + "\n\nBu kural HANDOFF §6.3 takim kararidir. Kaldirmak icin once o karari degistirin."
        )


def rapor() -> str:
    """Tum bilinen veri dizinlerinin kural ozeti (insan-okur)."""
    satirlar = ["VERI LISANS KAPISI — kayitli kurallar", "=" * 78]
    for onek in sorted(BILINEN):
        k = kural_bul(onek) or BILINEN[onek]
        var = os.path.isdir(os.path.join(ROOT, onek))
        e = "EVET" if k.get("egitimde_kullanilabilir") else "HAYIR"
        d = "EVET" if k.get("degerlendirmede_kullanilabilir") else "HAYIR"
        satirlar.append(
            f"{onek:26s} {'[var]' if var else '[yok]':6s} "
            f"egitim={e:5s} degerlendirme={d:5s}  {k.get('lisans', '?')}")
        satirlar.append(f"{'':26s} kaynak={k.get('_kaynak', 'BILINEN tablosu')}")
    return "\n".join(satirlar)


if __name__ == "__main__":
    print(rapor())
