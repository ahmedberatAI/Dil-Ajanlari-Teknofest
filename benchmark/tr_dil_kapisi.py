#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TURKCE DIL SAYACLARI — hakemsiz, deterministik, tekrar uretilebilir.

NEDEN HAKEMSIZ: bu depoda LLM hakemleri DEJENERE cikti — `judge_independent`
Risk ekseninde 5,00 (sifir varyans), `dialogue_hard` dogallik ekseninde
15/15 = 5,00 (std 0). Tavan yapan bir metrikle iyilesme GOSTERILEMEZ.
Asagidaki kusurlarin cogu SAYILABILIR; sayilabilen sey hakem istemez.

Ayrica Turkce metin karsilastirmasinin KENDI tuzagi var ve bu depo onu ZOR
YOLDAN ogrendi: 'i' (U+0131) NFD ile AYRISMAZ ve 'I'.lower() U+0307 uretir.
Sayaclar bu yuzden `_kat()` uzerinden gecer; aksi halde metrik SESSIZCE
kendi lehine sapar.

Kullanim:
    python benchmark/tr_dil_kapisi.py [arsiv.json ...]
    python benchmark/tr_dil_kapisi.py --prompt      (prompt dosyalarini tarar)
"""
from __future__ import annotations

import collections
import glob
import io
import json
import os
import re
import sys
import unicodedata

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)


def _kat(s: str) -> str:
    """Turkce-guvenli katlama. 'i' AYRICA katlanir (NFD ile ayrismaz)."""
    if not s:
        return ""
    out = unicodedata.normalize("NFC", s).casefold()
    return out.replace("ı", "i").replace("İ", "i")


# --- ASCII-lestirilmis Turkce: 'i' yerine 'i' yazilmis YAYGIN govdeler ---
ASCII_TR = [
    "yalnizca", "kisa", "nasil", "yardimci", "buradayim", "hizli", "saglik",
    "saygili", "talimatlari", "onaylarsaniz", "korunmasini", "hatirlat",
    "cikarmani", "asagida", "sirasiyla", "almasini", "arasinda", "olmali",
    "tutarli", "yanit", "hazirl", "ayni", "karsilik", "baslangic",
    "yapilandir", "isaretli", "calisma", "kisisel", "acik", "kapali",
    "tanimla", "anlatil", "uydurma", "sinir", "tasima", "yukari",
]
# kanonik terimler ve varyantlari (kol 2 icin taban)
TERIM = {
    "yelek": {
        "kanonik": ["reflektif yelek"],
        "varyant": ["güvenlik yeleği", "uyarı yeleği", "reflektif giysi",
                    "koruyucu yelek", "güvenlik uyarı yeleği"],
    },
    "pano": {
        "kanonik": ["elektrik/kontrol panosu", "elektrik veya kontrol panosu"],
        "varyant": ["kontrol panosu", "elektrik panosu", "pano kapağı",
                    "kontrol paneli", "elektrik paneli"],
    },
    "yaya_yolu": {
        "kanonik": ["yaya yolu"],
        "varyant": ["yürüyüş yolu", "trafik güvenliği", "yürüme yolu"],
    },
}
OLCEK_SIZ = [r"\b\d+\s*/\s*10\b", r"\bbirim\b", r"güvenli sınır",
             r"güvenli yük sınırı"]
SERH = ["bağımsız olarak", "neden-sonuç", "iç/dış mekân", "iç veya dış mekan",
        "talimat", "ayrı ayrı aktarılmıştır", "ilişkilendirilmemiştir"]
META_SON = ["temsil etmektedir", "göstermektedir", "anlamına gelmektedir",
            "değerlendirilmiştir", "oluşturmaktadır", "kaydedilmiştir",
            "raporlanmıştır", "sınıflandırılmıştır"]


def _metinler(satirlar):
    ozet, olay, gerekce = [], [], []
    for r in satirlar:
        if r.get("summary"):
            ozet.append(r["summary"])
        if r.get("risk_rationale"):
            gerekce.append(r["risk_rationale"])
        for e in (r.get("events") or []):
            if e.get("event"):
                olay.append(e["event"])
    return ozet, olay, gerekce


def sayaclar(ozet, olay, gerekce):
    d = {}
    n = max(1, len(ozet))

    # 1 KALIP ACILIS
    bas = [" ".join(o.split()[:1]) for o in ozet]
    d["acilis_Goruntu"] = sum(1 for b in bas if _kat(b).startswith("goruntu")
                              or _kat(b).startswith("görüntü")) / float(n)
    d["acilis_en_sik_aile"] = (collections.Counter(
        _kat(" ".join(o.split()[:2])) for o in ozet).most_common(1)[0][1]
        / float(n)) if ozet else 0.0

    # 2 META SON CUMLE
    def son_cumle(o):
        p = [x for x in re.split(r"(?<=[.!?])\s+", o.strip()) if x]
        return p[-1] if p else ""
    d["meta_son_cumle"] = sum(
        1 for o in ozet if any(m in _kat(son_cumle(o)) for m in
                               [_kat(x) for x in META_SON])) / float(n)

    # 3 HAM OLCEK SIZINTISI
    d["olcek_sizintisi_ozet"] = sum(
        1 for o in ozet if any(re.search(k, o, re.I) for k in OLCEK_SIZ)) / float(n)
    no = max(1, len(olay))
    d["olcek_sizintisi_olay"] = sum(
        1 for o in olay if any(re.search(k, o, re.I) for k in OLCEK_SIZ)) / float(no)

    # 4 TALIMAT SERHI
    d["talimat_serhi"] = sum(
        1 for o in ozet if any(s in _kat(o) for s in [_kat(x) for x in SERH])
    ) / float(n)

    # 5 ASCII-lestirilmis Turkce (cikti tarafinda)
    tum = ozet + gerekce
    nt = max(1, len(tum))
    d["ascii_tr_cikti"] = sum(
        1 for t in tum if any(a in _kat(t) for a in ASCII_TR)) / float(nt)

    # 6 TERIM TUTARLILIGI
    for ad, tk in TERIM.items():
        kan = var = 0
        for t in ozet + olay:
            k = _kat(t)
            kan += sum(k.count(_kat(x)) for x in tk["kanonik"])
            var += sum(k.count(_kat(x)) for x in tk["varyant"])
        top = kan + var
        d["kanonik_oran_" + ad] = (kan / float(top)) if top else None

    # 7 DEJENERELIK: birebir ayni ozet + tekrarlanan 4-gram
    d["birebir_ayni_ozet_cifti"] = len(ozet) - len(set(ozet))
    dortlu = collections.Counter()
    for o in ozet:
        w = _kat(o).split()
        for i in range(len(w) - 3):
            dortlu[" ".join(w[i:i + 4])] += 1
    tekrar = sum(c for c in dortlu.values() if c > 1)
    d["tekrar_4gram_orani"] = tekrar / float(max(1, sum(dortlu.values())))

    # 8 KKD/YETKI KAVRAM KARISIMI
    d["yetki_ve_yelek_ayni_ozette"] = sum(
        1 for o in ozet if "yetkisiz" in _kat(o) and "yelek" in _kat(o)) / float(n)

    # 9 (IZLENEN, olcut degil) edilgen bitis + uzunluk
    d["edilgen_bitis"] = sum(
        1 for o in ozet if re.search(r"(mıştır|miştir|muştur|müştür|maktadır|mektedir)\s*\.?\s*$",
                                     son_cumle(o), re.I)) / float(n)
    d["ort_karakter"] = sum(len(o) for o in ozet) / float(n)
    d["ozet_sayisi"] = len(ozet)
    d["olay_sayisi"] = len(olay)
    return d


def prompt_tara():
    print("### PROMPT DOSYALARINDA ASCII-LESTIRILMIS TURKCE")
    for p in ("dilajan/prompts.py", "dilajan/chat_agent.py", "dilajan/gozlem.py"):
        yol = os.path.join(KOK, p)
        if not os.path.exists(yol):
            continue
        s = io.open(yol, encoding="utf-8").read()
        metin = "\n".join(re.findall(r'"""(.*?)"""', s, re.S)
                          + re.findall(r'"([^"\n]{15,})"', s))
        say = collections.Counter()
        for a in ASCII_TR:
            n = len(re.findall(r"\b" + a, _kat(metin)))
            if n:
                say[a] = n
        print("  %-22s toplam %-4d  en sik: %s"
              % (os.path.basename(p), sum(say.values()),
                 dict(say.most_common(6))))
    # CHAT_SYSTEM ozel
    from dilajan import prompts as P
    cs = _kat(P.CHAT_SYSTEM)
    n = sum(len(re.findall(r"\b" + a, cs)) for a in ASCII_TR)
    print("  %-22s %d  <-- KOL 1'in hedefi (0 olmali)" % ("CHAT_SYSTEM", n))


def main():
    if "--prompt" in sys.argv:
        prompt_tara()
        return 0
    yollar = [a for a in sys.argv[1:] if a.endswith(".json")]
    if not yollar:
        yollar = sorted(glob.glob(os.path.join(
            KOK, "benchmark/results/eval_*.json")), key=os.path.getmtime)[-3:]
    from benchmark.yumusak_esik import _satirlari_al
    hepsi = []
    for y in yollar:
        try:
            sat = _satirlari_al(json.load(open(y, encoding="utf-8")))
        except Exception:
            continue
        hepsi.extend(sat.values())
        print("arsiv: %-34s satir %d" % (os.path.basename(y), len(sat)))
    ozet, olay, gerekce = _metinler(hepsi)
    d = sayaclar(ozet, olay, gerekce)
    print()
    print("### TURKCE DIL SAYACLARI  (ozet %d · olay %d)"
          % (d["ozet_sayisi"], d["olay_sayisi"]))
    for k, v in d.items():
        if k in ("ozet_sayisi", "olay_sayisi"):
            continue
        if v is None:
            print("  %-28s  —" % k)
        elif isinstance(v, float) and v <= 1.0:
            print("  %-28s  %.3f" % (k, v))
        else:
            print("  %-28s  %.1f" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
