#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GORSEL DAYANAK — sistemin her olay iddiasi klipte GORUNUYOR mu?

Olcut ve kapilar KOSUMDAN ONCE yazildi:
    docs/on_kayit_gorsel_dayanak_2026-08-26.md

NEDEN YENI BIR ARAC: `judge_independent.py --vision` 1-5'lik bir rubrik
uretiyor; rubrik "HANGI iddia yanlisti" sorusunu yanitlamiyor ve bu depoda
rubrik hakemleri IKI KEZ dejenere cikti (RISK ekseni 5,00 sifir varyans;
dialogue_hard 15/15 = 5,00). Burada iddia BAZINDA, KAPALI cevap uzayinda
olculur ve DUZENEGIN KENDISI olumsuz denetimle sinanir.

NEDEN VIDEO YOLU (kare degil): uzak EVREN servisinde `vlm` ucu goruntu
listesi KABUL ETMIYOR —
    "At most 0 image(s) may be provided in one prompt. (parameter=image)"
Klip TEK VIDEO olarak gonderilmeli. `video_oturumu` videoyu BIR KEZ kodlar
ve ustune cok soru sorar (olculdu: 4,8x hizlanma, on-ek onbellegi).
Her iddia `hatirla=False` ile sorulur -> iddialar BIRBIRINI ETKILEMEZ.

BAGIMSIZLIK SINIRI (raporda da yazilir): hakem `vlm`, ureten `llm-large`.
Farkli modeller; ancak `vlm` gozlem duzleminin kisi/oznitelik slotlarinda da
kullanildigi icin KURAL kaynakli iddialarda bagimsizlik KISMIDIR.

Kullanim:
    python benchmark/gorsel_dayanak.py [arsiv.json] [--n 60]
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import random
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from benchmark.yumusak_esik import _satirlari_al                 # noqa: E402
from dilajan.llm_client import VLMClient                          # noqa: E402

SECENEK = ["DOGRULANDI", "CELISIYOR", "GORULEMIYOR"]

SORU = """Bir otomatik sistem bu klip icin su IDDIAYI uretti:

<<<{iddia}>>>

Yalnizca IZLEDIGIN GORUNTUYE bakarak karar ver. Uc secenekten BIRINI yaz:

DOGRULANDI  — iddia edilen sey goruntude GORULUYOR
CELISIYOR   — goruntu iddianin TERSINI gosteriyor
GORULEMIYOR — goruntu bu konuda bilgi vermiyor (ne dogrular ne yalanlar)

Emin olamadigin durumda CELISIYOR degil GORULEMIYOR de. CELISIYOR yalnizca
goruntu iddianin TERSINI gosteriyorsa kullanilir."""

# Kural motorunun urettigi olaylarin imzasi (model serbest metninden ayirmak icin)
MOTOR = ("Forklift aşırı yük taşıyor", "Pano kapağı açık bırakılmış",
         "Yaya yolu ihlali", "Yetkisiz müdahale", "reflektif yelek yok")


def motor_mu(t: str) -> bool:
    return any(m in t for m in MOTOR)


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    m = (p + z * z / (2 * n)) / d
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, m - s), min(1.0, m + s))


def _coz(c):
    c = (c or "").strip().upper()
    for s in SECENEK:
        if c.startswith(s):
            return s
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("arsiv", nargs="?")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--tohum", type=int, default=13)
    ap.add_argument("--hakem", default="vlm")
    ap.add_argument("--cikti", default="benchmark/results/gorsel_dayanak.json")
    a = ap.parse_args()

    yol = a.arsiv or sorted(
        glob.glob(os.path.join(KOK, "benchmark/results/eval_*.json")),
        key=os.path.getmtime)[-1]
    sat = _satirlari_al(json.load(open(yol, encoding="utf-8")))
    olayli = [(p, r) for p, r in sorted(sat.items()) if (r.get("events") or [])]
    random.Random(a.tohum).shuffle(olayli)
    secilen = olayli[:a.n]

    print("### GORSEL DAYANAK  (klip TEK VIDEO olarak gonderilir)")
    print("  arsiv   : %s (%d satir, %d olayli)"
          % (os.path.basename(yol), len(sat), len(olayli)))
    print("  ornek   : %d klip (tohum %d)" % (len(secilen), a.tohum))
    print("  hakem   : %s   (ureten: llm-large)" % a.hakem)
    print("  SINIR   : `vlm` gozlem duzleminde de kullaniliyor ->")
    print("            KURAL kaynakli iddialarda bagimsizlik KISMIDIR.")
    print()

    istemci = VLMClient().model_ile(a.hakem)
    rng = random.Random(a.tohum + 1)
    havuz = [e.get("event", "") for _, r in olayli
             for e in (r.get("events") or []) if e.get("event")]

    kayit, olumsuz, hatalar = [], [], collections.Counter()
    kapsam_disi = 0
    for i, (p, r) in enumerate(secilen, 1):
        tam = p if os.path.isabs(p) else os.path.join(KOK, p)
        if not os.path.exists(tam):
            kapsam_disi += 1
            hatalar["dosya yok"] += 1
            continue
        try:
            ot = istemci.video_oturumu(tam)
        except Exception as ex:
            kapsam_disi += 1
            hatalar[type(ex).__name__] += 1
            continue
        if not ot.hazir:
            kapsam_disi += 1
            hatalar[str(ot.hata)[:40] or "oturum hazir degil"] += 1
            continue

        iddialar = [e.get("event", "") for e in (r.get("events") or [])
                    if e.get("event")]
        for iddia in iddialar:
            c = _coz(ot.sor(SORU.format(iddia=iddia), guided_choice=SECENEK,
                            temperature=0.0, max_tokens=12, hatirla=False))
            kayit.append({"path": p, "iddia": iddia, "cevap": c,
                          "motor": motor_mu(iddia)})
        # OLUMSUZ DENETIM: kliplerin ~%50sinde BASKA klibin iddiasi sorulur
        if rng.random() < 0.50:   # on kayit §7a: guc gerekcesiyle %25 -> %50
            yabanci = [x for x in havuz if x not in iddialar]
            if yabanci:
                sahte = rng.choice(yabanci)
                c = _coz(ot.sor(SORU.format(iddia=sahte), guided_choice=SECENEK,
                                temperature=0.0, max_tokens=12, hatirla=False))
                olumsuz.append({"path": p, "iddia": sahte, "cevap": c})
        if i % 10 == 0:
            print("   ... %d/%d klip · %d iddia · %d olumsuz denetim"
                  % (i, len(secilen), len(kayit), len(olumsuz)))

    # ---------------------------- HUKUM ----------------------------
    print()
    print("=" * 72)
    print("### 0) KAPSAM  (on-ret b: >= 45 klip islenmeli)")
    islenen = len(set(k["path"] for k in kayit))
    print("   islenen klip %d/%d · kapsam disi %d  %s"
          % (islenen, len(secilen), kapsam_disi,
             dict(hatalar) if hatalar else ""))
    gecerli = islenen >= 45

    print()
    print("### 1) DUZENEK SINAMASI — OLUMSUZ DENETIM")
    print("   (baska klibin iddiasi soruluyor; hakem DOGRULANDI derse KORDUR)")
    no = len(olumsuz)
    nd = sum(1 for x in olumsuz if x["cevap"] == "DOGRULANDI")
    if no:
        lo, hi = wilson(nd, no)
        print("   soruldu %d · hakem yine DOGRULANDI dedi %d = %.0f%% [%.0f%%-%.0f%%]"
              % (no, nd, 100.0 * nd / no, 100 * lo, 100 * hi))
        print("   dagilim: %s" % dict(collections.Counter(
            x["cevap"] for x in olumsuz)))
        saglam = (nd / float(no)) <= 0.20
        print("   -> ON-RET (a) esigi 0,20  ->  DUZENEK %s"
              % ("GUVENILIR" if saglam else "GUVENILMEZ (hukum VERILMEZ)"))
    else:
        saglam = False
        print("   !! olumsuz denetim yapilamadi -> hukum VERILMEZ")

    print()
    print("### 2) GERCEK IDDIALAR")
    n = len(kayit)
    say = collections.Counter(k["cevap"] for k in kayit)
    for s in SECENEK + [None]:
        k = say.get(s, 0)
        if not n:
            continue
        lo, hi = wilson(k, n)
        print("   %-12s %3d/%3d = %5.1f%%  [%.0f%%-%.0f%%]"
              % (s or "(cevapsiz)", k, n, 100.0 * k / n, 100 * lo, 100 * hi))
    dejenere = bool(n) and (say.most_common(1)[0][1] / float(n)) > 0.95
    if dejenere:
        print("   !! ON-RET DEJENERELIK: tek secenek >%95 -> hukum VERILMEZ")

    print()
    print("### 3) AYRISTIRMA — kural motoru mu, modelin serbest metni mi?")
    for ad, alt in (("KURAL MOTORU", [k for k in kayit if k["motor"]]),
                    ("MODEL METNI", [k for k in kayit if not k["motor"]])):
        if not alt:
            continue
        c = collections.Counter(x["cevap"] for x in alt)
        d = c.get("DOGRULANDI", 0)
        lo, hi = wilson(d, len(alt))
        print("   %-14s n=%-4d DOGRULANDI %3d = %5.1f%% [%.0f%%-%.0f%%]  %s"
              % (ad, len(alt), d, 100.0 * d / len(alt), 100 * lo, 100 * hi,
                 dict(c)))

    print()
    print("### 4) KLIP DUZEYI")
    per = collections.defaultdict(list)
    for k in kayit:
        per[k["path"]].append(k["cevap"])
    hal = sum(1 for v in per.values() if "CELISIYOR" in v)
    tam = sum(1 for v in per.values() if v and all(x == "DOGRULANDI" for x in v))
    if per:
        lo, hi = wilson(hal, len(per))
        print("   en az bir CELISIYOR : %d/%d = %.0f%% [%.0f%%-%.0f%%]"
              % (hal, len(per), 100.0 * hal / len(per), 100 * lo, 100 * hi))
        lo, hi = wilson(tam, len(per))
        print("   TUM iddialari dogru : %d/%d = %.0f%% [%.0f%%-%.0f%%]"
              % (tam, len(per), 100.0 * tam / len(per), 100 * lo, 100 * hi))

    print()
    print("### 5) CELISEN IDDIA ORNEKLERI")
    k = 0
    for x in kayit:
        if x["cevap"] != "CELISIYOR":
            continue
        k += 1
        if k > 6:
            break
        print("   %-22s [%s] %s"
              % (os.path.basename(x["path"]),
                 "kural" if x["motor"] else "model", x["iddia"][:88]))

    json.dump({"arsiv": os.path.basename(yol), "hakem": a.hakem,
               "tohum": a.tohum,
               "bagimsizlik_siniri": "vlm gozlem duzleminde de kullaniliyor",
               "kapsam_gecerli": gecerli, "duzenek_saglam": saglam,
               "dejenere": dejenere,
               "iddialar": kayit, "olumsuz_denetim": olumsuz},
              open(os.path.join(KOK, a.cikti), "w", encoding="utf-8"),
              ensure_ascii=False)
    print()
    print("   -> %s" % a.cikti)
    if not (gecerli and saglam) or dejenere:
        print("   *** ON-RET KAPISI DUSTU: yukaridaki sayilar HUKUM DEGILDIR.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
