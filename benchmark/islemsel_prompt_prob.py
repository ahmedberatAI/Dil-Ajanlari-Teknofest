#!/usr/bin/env python
"""D40 PROB — mentorun prompt tezinin ADIL testi: ANLAMSAL vs CAPALI vs ISLEMSEL soru.

    python benchmark/islemsel_prompt_prob.py --kuru      # model cagirmadan plani yazdir
    python benchmark/islemsel_prompt_prob.py --kol 1     # yalniz forklift kolu
    python benchmark/islemsel_prompt_prob.py             # tum kollar

ON-KAYIT: docs/on_kayit_islemsel_prompt_2026-08-18.md  (KOSUMDAN ONCE yazildi)

=== NEDEN ===
D37'de mentorun yapilandirilmis-prompt mimarisi kuruldu, olumsuz cikti ve "darbogaz
format degil ALGI" yazildi. O sonuc, MODELE SORULAN SORUNUN CEVAPLANABILIR oldugunu
varsayiyordu. Degildi: kaynak makale (Onal & Dandil 2024, Data in Brief 56:110756)
etiketleri ISLEMSEL tanimliyor ("3 blocks or more", "wearing a green vest"), oysa
benchmark/labels.py'de modele verilen tanimlar GOZLEMLENEMEZDI ("guvenli kapasiteyi
asacak sekilde", "yetkili teknisyen disinda").

=== TASARIM — UC KOL, CUNKU "TEK DEGISKEN" IDDIASI YANLISTI ===
Tasarim denetimi (2026-08-18) sunu gosterdi: islemsel soru, anlamsal sorudan UC seyi
birden degistiriyor — (1) nereye bakilacagi, (2) kararin nerede verildigi,
(3) bicim. Bu yuzden ucuncu bir kol eklendi:

  A  ANLAMSAL       : anlamsal olcut, mekansal capa YOK   (bugune kadarki soru)
  A2 ANLAMSAL+CAPA  : anlamsal olcut, B ile AYNI mekansal capa
  B  ISLEMSEL       : kaynak makalenin gozlemlenebilir olcutu + ayni capa

  B > A2 > A ise  : kazanan GOZLEMLENEBILIRLIK (mentorun tezinin cekirdegi)
  B ~= A2 > A ise : kazanan DIKKAT YONLENDIRMESI, gozlemlenebilirlik degil
  hepsi ~= ise    : darbogaz gercekten ALGI

=== DENETIMDE BULUNAN VE ONARILAN OLUMCUL KUSURLAR ===
F1 KARE SINIRI: eski surum TUM kareleri gonderiyordu; vLLM
   --limit-mm-per-prompt {"image": 16} ile kosuyor ve 149 klibin 56'si (%37,6)
   siniri asiyordu — ustelik SINIF-KORELE (kol2 ihlal %72 vs normal %52). vLLM 400
   donuyor, hata "ihlal yok" olarak PUANLANIYORDU. Artik AZAMI_KARE=8 (deponun
   diger tum problarinin kullandigi deger) ve asim ONCEDEN kirpiliyor.
E1 HATA PUANLAMA: hata alan klip artik NEGATIF SAYILMAZ; TUM kollardan DUSURULUR
   (eslestirme korunur) ve ayrica raporlanir.
S1 SAGLIK KONTROLU: sunucu kapali/mock ise kosum BASLAMAZ. Eskiden her cagri
   hata verse bile tablo "dogruluk 0,500 · DEJENERE · KALDI" basiyordu ve bu
   "islemsel soru da ise yaramadi" diye YANLIS yorumlanabilirdi.
S2 KUNYE: model, T, fps, cozunurluk, kare sayisi, secenek listeleri, argv ve
   git commit ciktiya yazilir. (DILAJAN_FAST=1 fps'i ve cozunurlugu SESSIZCE
   dusurur; kunyesiz kosum "uretim ayarlari" iddiasini dogrulayamaz.)
C1 SERBEST METIN AYRISTIRICISI: eski surum ILK tamsayiyi aliyordu; kareler modele
   "[Kare zamani: MM:SS]" etiketiyle gittigi icin ilk tamsayi genelde 0 oluyordu
   -> sistematik NEGATIF kayma. Artik SON tamsayi alinir ve kesilme tespit edilir.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DILAJAN_PROB_SET: yeniden-kodlama kontrolu icin klip kokunu degistirir
# (bkz. benchmark/yeniden_kodla.py ve on-kayit EK-1 "ACIK KALAN").
SET = os.environ.get("DILAJAN_PROB_SET") or os.path.join(KOK, "data/eval_defense")

# Deponun diger TUM VLM problarinin kullandigi deger (isg_yapilandirilmis_prob.py:94,
# isafety_mcq.py:73). vLLM --limit-mm-per-prompt {"image": 16} ile kosuyor; 8 guvenli.
AZAMI_KARE = 8

SISTEM = ("Sen bir endustriyel is guvenligi kamerasi analiz sistemisin. Sana bir "
          "guvenlik kamerasindan alinmis kareler verilir. YALNIZCA GORDUGUNE dayan; "
          "varsayim yapma. Ayirt edemiyorsan kacis secenegini kullan.")


# --------------------------------------------------------------- cevap yorumlayicilar
def _kasa_ihlal(c: str):
    """>= 3 kasa -> ihlal (kaynak makale: '3 blocks or more')."""
    c = (c or "").strip().upper()
    if c.startswith("__HATA__"):
        return "HATA"
    if c in ("GORUNMUYOR", ""):
        return None
    if c.endswith("+"):
        c = c[:-1]
    try:
        return int(c) >= 3
    except ValueError:
        return None


def _kasa_ihlal_serbest(c: str):
    """SON tamsayiyi alir.

    C1: eski surum ILK tamsayiyi aliyordu. Kareler modele "[Kare zamani: MM:SS]"
    etiketiyle gidiyor; model "00:04'te iki kasa..." derse ILK tamsayi 0 olur ve
    0 >= 3 -> False -> sistematik "ihlal yok". Prompt "son satira sadece sayiyi yaz"
    dedigi icin dogru olan SON tamsayidir.
    """
    if (c or "").strip().upper().startswith("__HATA__"):
        return "HATA"
    sayilar = re.findall(r"\d+", c or "")
    if not sayilar:
        return None
    return int(sayilar[-1]) >= 3


def _evet_ihlal(c: str):
    c = (c or "").strip().upper()
    if c.startswith("__HATA__"):
        return "HATA"
    if c.startswith("EVET"):
        return True
    if c.startswith("HAYIR"):
        return False
    return None


def _yelek_ihlal(c: str):
    """Yelek YOKSA ihlal (kaynak makale: 'without an intervention vest')."""
    c = (c or "").strip().upper()
    if c.startswith("__HATA__"):
        return "HATA"
    if c == "YELEK_YOK":
        return True
    if c == "YELEK_VAR":
        return False
    return None          # KISI_YOK / GORUNMUYOR -> karar yok


# --------------------------------------------------------------------------- kollar
# NOT (kol 3): B sorusu kaynak makalenin olcutu DEGIL, kendi dedektorumuzun
# mekanizmasidir (pano.py: ROI'de minimum ortalama parlaklik). Ayrica bu kol MIMARI
# KARARI DEGISTIRMEZ: yalniz-parlaklik kurali kolay ciftte (acik vs kapali) zaten
# %95,9, ama GERCEK guvenlik gorevinde (class2 vs class6+class5) MCC +0,513 / FP=21.
# Bu yuzden kol 3 KESIFSEL isaretlidir ve manşet sayi uretmez.
KOLLAR = [
    {
        "no": 1, "ad": "forklift-asiri-yuk", "kesifsel": False,
        "ihlal": "Anomali/Carrying_Overload_with_Forklift",
        "normal": "Normal/Safe_Carrying",
        "taban_dedektor": "ic ice LOO MCC +0,718 (ozgulluk 25/25, tesis capinda 0/172 YP)",
        "sorular": [
            ("A_anlamsal",
             "Bu karelerde forklift GUVENLI KAPASITEYI ASAN bir yuk tasiyor mu?",
             ["EVET_ASIRI_YUK", "HAYIR_GUVENLI", "GORUNMUYOR"], _evet_ihlal),
            ("A2_anlamsal_capa",
             "Forkliftin CATALINDAKI yuke bak. Bu yuk GUVENLI KAPASITEYI ASIYOR mu?",
             ["EVET_ASIRI_YUK", "HAYIR_GUVENLI", "GORUNMUYOR"], _evet_ihlal),
            ("B_islemsel",
             "Forkliftin CATALINDA ust uste kac adet kasa/blok tasiniyor? "
             "Yalnizca sayiyi yaz.",
             ["0", "1", "2", "3", "4", "5", "6+", "GORUNMUYOR"], _kasa_ihlal),
            ("C_islemsel_serbest",
             "Forkliftin CATALINDA ust uste kac adet kasa/blok tasiniyor? "
             "Kisaca say, sonra SON SATIRA sadece sayiyi yaz.",
             None, _kasa_ihlal_serbest),      # None = guided_choice YOK
        ],
    },
    {
        "no": 2, "ad": "yetki-yelek", "kesifsel": False,
        "ihlal": "Anomali/Unauthorized_Intervention",
        "normal": "Normal/Authorized_Intervention",
        "taban_dedektor": "kume-ici MCC ~+0,644 (havuzlanmis +0,843 SISKIN)",
        "sorular": [
            ("A_anlamsal",
             "Bu karelerde makineye/panoya YETKISIZ bir kisi mudahale ediyor mu?",
             ["EVET_YETKISIZ", "HAYIR_YETKILI", "GORUNMUYOR"], _evet_ihlal),
            ("A2_anlamsal_capa",
             "Makinenin/panonun BASINDA DURAN KISIYE bak. Bu kisi YETKISIZ mi "
             "mudahale ediyor?",
             ["EVET_YETKISIZ", "HAYIR_YETKILI", "GORUNMUYOR"], _evet_ihlal),
            ("B_islemsel",
             "Makinenin/panonun BASINDA DURAN KISIDE yesil reflektif yelek var mi?",
             ["YELEK_VAR", "YELEK_YOK", "KISI_YOK", "GORUNMUYOR"], _yelek_ihlal),
        ],
    },
    {
        "no": 3, "ad": "pano-kapak", "kesifsel": True,     # KESIFSEL — manşet uretmez
        "ihlal": "Anomali/Opened_Panel_Cover",
        "normal": "Normal/Closed_Panel_Cover",
        "taban_dedektor": "yalniz-parlaklik kolay ciftte %95,9; GERCEK guvenlik "
                          "gorevinde MCC +0,513 (FP=21) — bu kol mimari karari DEGISTIRMEZ",
        "sorular": [
            ("A_anlamsal",
             "Bu karelerde elektrik/kontrol panosunun KAPAGI ACIK birakilmis mi?",
             ["EVET_ACIK", "HAYIR_KAPALI", "GORUNMUYOR"], _evet_ihlal),
            ("B_islemsel",
             "Makinenin PANO BOLGESINDE koyu/karanlik bir oyuk (acik kapagin "
             "arkasindaki bosluk) gorunuyor mu, yoksa orasi duz bir yuzey mi?",
             ["EVET_KOYU_OYUK", "HAYIR_DUZ_YUZEY", "GORUNMUYOR"], _evet_ihlal),
        ],
    },
]


# --------------------------------------------------------------------------- olcum
def mcc(tp, fp, fn, tn):
    p = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return (tp * tn - fp * fn) / p if p else 0.0


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    q = k / n
    d = 1 + z * z / n
    m = (q + z * z / (2 * n)) / d
    y = z * math.sqrt(q * (1 - q) / n + z * z / (4 * n * n)) / d
    return (max(0.0, m - y), min(1.0, m + y))


def mcnemar_exact(b: int, c: int) -> float:
    """Iki yonlu exact binom (eslestirilmis uyumsuz ciftler). b=c -> 1,0."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n))


# ------------------------------------------------------------------------- yardimci
def kunye(argv) -> dict:
    """S2: kosum tekrar uretilebilir olmali. DILAJAN_FAST fps/cozunurlugu SESSIZCE
    dusurur — burada kayda gecer."""
    try:
        from dilajan.config import settings as s
        ayar = {"model": s.model_name, "temperature_ayari": s.temperature,
                "fps_sample": s.fps_sample, "frame_max_side": s.frame_max_side,
                "max_frames_per_segment": s.max_frames_per_segment,
                "fast_mode": getattr(s, "fast_mode", None),
                "mock_mode": getattr(s, "mock_mode", None)}
    except Exception as e:
        ayar = {"hata": f"{type(e).__name__}: {e}"}
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=KOK,
                                capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        commit = "?"
    return {**ayar, "azami_kare": AZAMI_KARE, "prob_temperature": 0.0,
            "git_commit": commit, "argv": argv,
            "eval_dir": SET,
            "zaman": datetime.now().isoformat(timespec="seconds")}


def saglik_kontrolu() -> str:
    """S1: sunucu kapali/mock ise KOSMA. Bos dize = saglikli."""
    try:
        from dilajan.config import settings as s
        if getattr(s, "mock_mode", False):
            return "mock_mode ACIK — gercek model cagrilmaz, olcum anlamsiz"
    except Exception:
        pass
    try:
        from dilajan.llm_client import VLMClient
        i = VLMClient()
        c = i.chat([{"role": "user", "content": "1"}], max_tokens=2, temperature=0.0)
        return "" if c is not None else "model bos yanit dondu"
    except Exception as e:
        return f"sunucuya ulasilamiyor: {type(e).__name__}: {e}"


def kareler_uret(yol):
    """F1: AZAMI_KARE ile SINIRLI. Fazlasi vLLM'de 400 uretiyordu ve hata
    'ihlal yok' olarak puanlaniyordu."""
    from dilajan.video import extract_timestamped_frames
    fr, _ = extract_timestamped_frames(yol)      # uretim ayarlari (fps 2.0, 768 px)
    if len(fr) > AZAMI_KARE:
        adim = len(fr) / AZAMI_KARE
        fr = [fr[min(len(fr) - 1, int(i * adim))] for i in range(AZAMI_KARE)]
    return [(f"{int(t)//60:02d}:{int(t)%60:02d}", j) for t, j in fr]


def klipler(alt):
    return sorted(glob.glob(os.path.join(SET, alt, "*.mp4")))


# ----------------------------------------------------------------------------- kosum
def kol_kos(kol, istemci, kuru=False):
    yollar = [(y, True) for y in klipler(kol["ihlal"])] + \
             [(y, False) for y in klipler(kol["normal"])]
    print(f"\n{'=' * 78}")
    print(f"KOL {kol['no']} — {kol['ad']}   ({len(yollar)} klip)"
          + ("   [KESIFSEL]" if kol["kesifsel"] else ""))
    print(f"  karsilastirma tabani: {kol['taban_dedektor']}")
    print(f"{'=' * 78}", flush=True)
    if kuru:
        for ad, soru, sec, _ in kol["sorular"]:
            print(f"  [{ad:20s}] guided={'VAR' if sec else 'YOK '}  {soru[:64]}...")
        return None

    satir = []
    for i, (yol, ihlal) in enumerate(yollar, 1):
        try:
            kar = kareler_uret(yol)
        except Exception as e:
            print(f"  [KARE HATASI] {os.path.basename(yol)}: {type(e).__name__}: {e}")
            continue
        kayit = {"klip": os.path.basename(yol), "ihlal": ihlal, "n_kare": len(kar)}
        for ad, soru, sec, yorum in kol["sorular"]:
            try:
                cevap = istemci.analyze_frames(
                    kar, soru, system=SISTEM, temperature=0.0,
                    max_tokens=24 if sec else 200, guided_choice=sec).strip()
            except Exception as e:
                cevap = f"__HATA__ {type(e).__name__}: {e}"
            kayit[ad + "_ham"] = cevap
            kayit[ad] = yorum(cevap)
        satir.append(kayit)
        if i % 10 == 0 or i == len(yollar):
            print(f"  {i}/{len(yollar)}", flush=True)
    return satir


def kol_rapor(kol, satir):
    adlar = [a for a, _, _, _ in kol["sorular"]]

    # E1: HATA alan klip TUM kollardan DUSURULUR (eslestirme korunur), negatif SAYILMAZ.
    hatali = [r for r in satir if any(r.get(a) == "HATA" for a in adlar)]
    temiz = [r for r in satir if r not in hatali]
    print(f"\n--- KOL {kol['no']} SONUC ({kol['ad']})"
          + ("  [KESIFSEL — manşet uretmez]" if kol["kesifsel"] else "") + " ---")
    if hatali:
        print(f"  ! {len(hatali)}/{len(satir)} klip API hatasi nedeniyle DUSURULDU "
              f"(negatif sayilmadi): "
              + ", ".join(r["klip"] for r in hatali[:6])
              + (" ..." if len(hatali) > 6 else ""))
    if len(temiz) < 0.8 * len(satir):
        print(f"  !! UYARI: kliplerin %{100*(1-len(temiz)/max(1,len(satir))):.0f}'i "
              f"dusuruldu — bu kosum GUVENILIR DEGIL")
    if not temiz:
        print("  !! hicbir temiz klip yok — kol raporlanamaz")
        return {"hata": "temiz klip yok", "dusurulen": len(hatali)}

    print(f"\n{'alt kol':22s} {'TP':>3s} {'FP':>3s} {'FN':>3s} {'TN':>3s} {'kararsiz':>9s} "
          f"{'MCC':>8s} {'dogruluk':>9s}  {'Wilson95':>16s}  not")
    print("-" * 110)
    ozet = {}
    for ad in adlar:
        tp = fp = fn = tn = kararsiz = 0
        for r in temiz:
            t = r.get(ad)
            if t is None:
                kararsiz += 1
                t = False        # kararsiz = "olay uretmedi" (dagitim davranisi)
            if r["ihlal"] and t:
                tp += 1
            elif r["ihlal"] and not t:
                fn += 1
            elif (not r["ihlal"]) and t:
                fp += 1
            else:
                tn += 1
        n = tp + fp + fn + tn
        m, dog = mcc(tp, fp, fn, tn), (tp + tn) / n if n else 0.0
        lo, hi = wilson(tp + tn, n)
        poz = tp + fp
        dej = (poz >= 0.85 * n) or ((n - poz) >= 0.85 * n)
        ozet[ad] = {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "kararsiz": kararsiz,
                    "mcc": m, "dogruluk": dog, "dejenere": dej, "n": n}
        print(f"{ad:22s} {tp:3d} {fp:3d} {fn:3d} {tn:3d} {kararsiz:9d} {m:+8.3f} "
              f"{dog:9.3f}  [{lo:.3f}-{hi:.3f}]  {'** DEJENERE **' if dej else ''}")

    # --- eslestirilmis karsilastirmalar (DOGRULUK bazinda: kim DOGRU bildi)
    # C3: karsilastirma sayisi -> Bonferroni. Kol1: A-A2, A2-B, B-C = 3; Kol2: 2; Kol3: 1.
    ciftler = []
    if len(adlar) >= 2:
        ciftler = [(adlar[i], adlar[i + 1]) for i in range(len(adlar) - 1)]
        if "A_anlamsal" in adlar and "B_islemsel" in adlar:
            ciftler.append(("A_anlamsal", "B_islemsel"))      # asil karsilastirma
    ciftler = list(dict.fromkeys(ciftler))
    esik = 0.05 / max(1, len(ciftler))
    print(f"\n  eslestirilmis karsilastirma: {len(ciftler)} adet -> Bonferroni esik "
          f"p < {esik:.4f}")
    for X, Y in ciftler:
        dX = [bool(r.get(X)) == r["ihlal"] for r in temiz]
        dY = [bool(r.get(Y)) == r["ihlal"] for r in temiz]
        b = sum(1 for x, y in zip(dX, dY) if x and not y)
        c = sum(1 for x, y in zip(dX, dY) if y and not x)
        p = mcnemar_exact(b, c)
        dm = ozet[Y]["mcc"] - ozet[X]["mcc"]
        gecti = (p < esik) and not ozet[Y]["dejenere"]
        print(f"    {X:22s} -> {Y:22s}  yalniz-{X[:1]}={b:2d} yalniz-{Y[:1]}={c:2d}  "
              f"p={p:.4g}  dMCC={dm:+.3f}  {'GECTI' if gecti else 'kaldi'}")
        ozet[f"{X}__vs__{Y}"] = {"p": p, "dmcc": dm, "gecti": gecti, "b": b, "c": c}

    # --- MUTLAK TABAN (denetim onerisi): A'yi gecmek YETMEZ, uretilebilir olmali
    if "B_islemsel" in ozet and not kol["kesifsel"]:
        print(f"\n  MUTLAK TABAN — B'nin MCC'si: {ozet['B_islemsel']['mcc']:+.3f}")
        print(f"    dedektor tabani: {kol['taban_dedektor']}")
        print(f"    NOT: A'yi gecmek TEK BASINA yeterli degildir; B, ilgili "
              f"deterministik dedektorun degerine yaklasmiyorsa uretim karari DEGISMEZ.")
    return ozet


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kol", type=int, default=0, help="0 = hepsi")
    ap.add_argument("--kuru", action="store_true", help="model cagirmadan plani yazdir")
    a = ap.parse_args()

    print("D40 — ANLAMSAL vs ANLAMSAL+CAPA vs ISLEMSEL soru probu")
    print("On-kayit: docs/on_kayit_islemsel_prompt_2026-08-18.md")
    print(f"Kare siniri: {AZAMI_KARE} (vLLM --limit-mm-per-prompt image:16)")

    istemci = None
    if not a.kuru:
        hata = saglik_kontrolu()
        if hata:
            print(f"\n!! KOSUM BASLAMADI — {hata}")
            print("   (Sessiz cokme, 'islemsel soru da ise yaramadi' diye YANLIS "
                  "yorumlanabilecek sahte bir tablo uretirdi.)")
            return 2
        from dilajan.llm_client import VLMClient
        istemci = VLMClient()
        print("saglik kontrolu: TAMAM")

    hepsi = {}
    for kol in KOLLAR:
        if a.kol and kol["no"] != a.kol:
            continue
        satir = kol_kos(kol, istemci, kuru=a.kuru)
        if satir is None:
            continue
        hepsi[kol["ad"]] = {"satirlar": satir, "ozet": kol_rapor(kol, satir),
                            "kesifsel": kol["kesifsel"]}

    if hepsi:
        damga = datetime.now().strftime("%Y%m%d_%H%M%S")
        yol = os.path.join(KOK, f"benchmark/results/islemsel_prompt_{damga}.json")
        json.dump({"on_kayit": "docs/on_kayit_islemsel_prompt_2026-08-18.md",
                   "kunye": kunye(sys.argv), "kollar": hepsi},
                  open(yol, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\nKaydedildi: {os.path.relpath(yol, KOK)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
