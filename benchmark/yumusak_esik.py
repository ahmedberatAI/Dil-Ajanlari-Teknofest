#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Yumusak esik kollari — MODEL CALISTIRMADAN, enstrumanli arsivden yeniden puanlama.

NEDEN CALISIR: `slot_guven=1` ile kosulan arsiv, her segmentin SLOT DAGILIMINI
tasir (`guven_trace`). Sert kural `argmax(deger) >= T` sorar; dagilim elimizde
oldugu icin `P(deger >= T) >= p*` gibi BASKA karar kurallari da AYNI ileri
gecislerden puanlanabilir. Yeni API cagrisi YOK.

Bunun iki sonucu var:
  · Kollar ESLESMIS karsilastirilir (ayni klipler, ayni gozlemler) -> McNemar.
  · Kollar arasi fark MODELDEN degil YALNIZCA karar kuralindan gelir.

ON KAYIT: docs/on_kayit_yumusak_esik_2026-08-25.md
  p* = 0,50 KOSUMDAN ONCE sabitlendi. Tarama YALNIZCA betimleyici basilir.

Kullanim:
    python benchmark/yumusak_esik.py benchmark/results/eval_*.json
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

# --- ON KAYITLI SABIT ---
P_YILDIZ = 0.50          # DEGISTIRILMEYECEK (on kayit S1)

# (ad, ihlal dizini, normal dizini, slot, esik, yon)
#   yon "ust"    : deger >= esik ihlal
#   yon "etiket" : yelek kurali (ON KOSUL + etiket esitligi)
CIFTLER = [
    ("forklift", "Anomali/Carrying_Overload_with_Forklift", "Normal/Safe_Carrying",
     "catal_kasa_sayisi", 3, "ust"),
    ("pano", "Anomali/Opened_Panel_Cover", "Normal/Closed_Panel_Cover",
     "pano_koyuluk_0_10", 6, "ust"),
    ("yelek", "Anomali/Unauthorized_Intervention", "Normal/Authorized_Intervention",
     "makine_basinda_yelek", None, "etiket"),
]
YELEK_ON_SLOT, YELEK_ON_ASGARI = "makine_basinda_kisi", 1

ISARET = "gözlem güveni "
_COZUCU = json.JSONDecoder()


def mcc(tp, fp, fn, tn):
    pay = tp * tn - fp * fn
    payda = math.sqrt(float((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)))
    return (pay / payda) if payda else 0.0


def mcnemar(a_dogru, b_dogru):
    """Eslesmis iki kol: B duzeltti (b) / B bozdu (c). Kesin binom, iki yonlu."""
    b = sum(1 for x, y in zip(a_dogru, b_dogru) if not x and y)
    c = sum(1 for x, y in zip(a_dogru, b_dogru) if x and not y)
    n = b + c
    if n == 0:
        return {"duzeltti": 0, "bozdu": 0, "p": 1.0}
    k = min(b, c)
    kuyruk = sum(math.comb(n, i) for i in range(k + 1)) / (2.0 ** n)
    return {"duzeltti": b, "bozdu": c, "p": min(1.0, 2.0 * kuyruk)}


def dagilimlari_oku(satir):
    """guven_trace -> [{slot: dagilim}, ...] (SEGMENT basina bir sozluk).

    DIKKAT — regex ile ayristirilmaz. Karar izi girdileri TEK DIZEDE
    birlesebiliyor (olculdu: 1467 karakterlik bir girdi hem 'gözlem düzlemi'
    hem 'gözlem güveni' notunu tasiyordu). Sona capalanmis bir regex boyle bir
    dizede yalnizca SONUNCU segmenti yakalardi ve coksegmentli kliplerde
    dagilimlarin bir kismi SESSIZCE dusrdu.

    Cozum: her isaretten sonra `raw_decode` ile TAM bir JSON nesnesi okunur —
    ic ice suslu parantezlerden bagimsiz, kac tane olursa olsun hepsi alinir.
    """
    out = []
    for t in (satir.get("guven_trace") or []):
        i = t.find(ISARET)
        while i != -1:
            bas = i + len(ISARET)
            try:
                nesne, son = _COZUCU.raw_decode(t, bas)
                if isinstance(nesne, dict):
                    out.append(nesne)
                i = t.find(ISARET, son)
            except ValueError:
                i = t.find(ISARET, bas)
    return out


def _p_esik_ustu(dag, esik):
    """P(deger >= esik). '6+' -> 6; sayisal olmayan secenekler DISLANIR."""
    top = 0.0
    for secenek, p in ((dag or {}).get("p") or {}).items():
        m = str(secenek).strip().rstrip("+")
        if m.isdigit() and int(m) >= esik:
            top += p
    return top


def _argmaks(dag):
    return (dag or {}).get("maks")


def _sayi_mi_ve_asiyor(deger, esik):
    v = str(deger or "").rstrip("+")
    return v.isdigit() and int(v) >= esik


def klip_atesledi(segmentler, cift, kip, p_yildiz=P_YILDIZ):
    """Kural bu KLIPTE atesliyor mu? (segment kapsamli slotta HERHANGI biri)"""
    _ad, _i, _n, slot, esik, yon = cift
    for seg in segmentler:
        dag = seg.get(slot)
        if not dag:
            continue
        if yon == "ust":
            if kip == "sert":
                if _sayi_mi_ve_asiyor(_argmaks(dag), esik):
                    return True
            else:
                if _p_esik_ustu(dag, esik) >= p_yildiz:
                    return True
        else:
            on = seg.get(YELEK_ON_SLOT)
            if kip == "sert":
                kapi = _sayi_mi_ve_asiyor(_argmaks(on), YELEK_ON_ASGARI)
                ihlal = _argmaks(dag) == "YOK"
            elif kip == "yumusak":          # S1: yalniz KURAL yumusak
                kapi = _sayi_mi_ve_asiyor(_argmaks(on), YELEK_ON_ASGARI)
                ihlal = ((dag.get("p") or {}).get("YOK", 0.0)) >= p_yildiz
            else:                            # S3: yalniz KAPI yumusak
                kapi = _p_esik_ustu(on, YELEK_ON_ASGARI) >= p_yildiz
                ihlal = _argmaks(dag) == "YOK"
            if kapi and ihlal:
                return True
    return False


def kol_puanla(satirlar, cift, kip, p_yildiz=P_YILDIZ):
    _ad, ihl, nrm = cift[0], cift[1], cift[2]
    tp = fp = fn = tn = 0
    dogru, isim = [], []
    for yol, r in sorted(satirlar.items()):
        y = "/" + yol.replace("\\", "/")
        pozitif = ("/" + ihl + "/") in y
        negatif = ("/" + nrm + "/") in y
        if not (pozitif or negatif):
            continue
        atesledi = klip_atesledi(dagilimlari_oku(r), cift, kip, p_yildiz)
        if pozitif:
            if atesledi:
                tp += 1
            else:
                fn += 1
        else:
            if atesledi:
                fp += 1
            else:
                tn += 1
        dogru.append(atesledi == pozitif)
        isim.append(y)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "mcc": mcc(tp, fp, fn, tn), "dogru": dogru, "klipler": isim}


def saha_kesinligi(satirlar, cift, kip, p_yildiz=P_YILDIZ):
    """TUM kliplerde: ateslemenin kacinda klip GERCEKTEN o sinifin ihlali?

    Cift bazli metrik saha davranisini gizler. Operatorun gordugu sayi budur.
    """
    ihl = cift[1]
    ates = dogru_ates = 0
    for yol, r in satirlar.items():
        y = "/" + yol.replace("\\", "/")
        if not klip_atesledi(dagilimlari_oku(r), cift, kip, p_yildiz):
            continue
        ates += 1
        if ("/" + ihl + "/") in y:
            dogru_ates += 1
    return dogru_ates, ates


def _satirlari_al(ham):
    for anahtar in ("rows", "satirlar", "clips", "klipler"):
        v = ham.get(anahtar)
        if isinstance(v, list) and v and isinstance(v[0], dict) and "path" in v[0]:
            return {r["path"]: r for r in v}
    return {}


def main():
    desen = sys.argv[1] if len(sys.argv) > 1 else "benchmark/results/eval_*.json"
    dosyalar = sorted(glob.glob(os.path.join(KOK, desen)), key=os.path.getmtime)
    if not dosyalar:
        print("arsiv bulunamadi: " + desen)
        return 1
    yol = dosyalar[-1]
    ham = json.load(open(yol, encoding="utf-8"))
    satirlar = _satirlari_al(ham)
    print("arsiv: " + os.path.relpath(yol, KOK) + "   satir: " + str(len(satirlar)))
    if not satirlar:
        print("!! satir okunamadi — anahtarlar: " + str(sorted(ham.keys())))
        return 2

    kunye = ham.get("kosum") or ham.get("kunye") or {}
    print("kunye slot_guven=" + str(kunye.get("slot_guven"))
          + "  isg_slotlari=" + str(kunye.get("isg_slotlari")))
    kapsayan = sum(1 for r in satirlar.values() if r.get("guven_trace"))
    print("guven izi TASIYAN satir: " + str(kapsayan) + "/" + str(len(satirlar)))
    if kapsayan == 0:
        print("!! DAGILIM YOK — kol puanlanamaz (sessiz basarisizlik kontrolu)")
        return 3
    print()

    KIPLER = [("sert (SEVK EDILEN)", "sert"),
              ("S1 yumusak esik p*=0,50", "yumusak"),
              ("S3 yumusak ON KOSUL p*=0,50", "kapi")]

    print("%-10s%-28s%4s%4s%4s%4s%9s%12s" %
          ("cift", "kip", "TP", "FP", "FN", "TN", "MCC", "saha kes."))
    print("-" * 80)
    taban = {}
    for cift in CIFTLER:
        for etiket, kip in KIPLER:
            if kip == "kapi" and cift[0] != "yelek":
                continue                     # ON KOSUL yalniz yelek kuralinda
            s = kol_puanla(satirlar, cift, kip)
            d, a = saha_kesinligi(satirlar, cift, kip)
            sk = (float(d) / a) if a else 0.0
            print("%-10s%-28s%4d%4d%4d%4d%+9.3f%8.3f (%d/%d)" %
                  (cift[0], etiket, s["tp"], s["fp"], s["fn"], s["tn"],
                   s["mcc"], sk, d, a))
            if kip == "sert":
                taban[cift[0]] = s
            else:
                mc = mcnemar(taban[cift[0]]["dogru"], s["dogru"])
                print("%-10s%-28sduzeltti=%d bozdu=%d p=%.4f   dMCC=%+.3f" %
                      ("", "  -> McNemar", mc["duzeltti"], mc["bozdu"], mc["p"],
                       s["mcc"] - taban[cift[0]]["mcc"]))
        print()

    print("=" * 80)
    print("p* TARAMASI — BETIMLEYICI. Karar olcutu p*=0,50'dir (on kayit).")
    ps = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    print("%-10s" % "cift" + "".join("%8.2f" % p for p in ps))
    for cift in CIFTLER:
        satir = "%-10s" % cift[0]
        for p in ps:
            s = kol_puanla(satirlar, cift, "yumusak", p)
            satir += "%+8.3f" % s["mcc"]
        print(satir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
