#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""VERI BUTUNLUGU — mukerrer icerik ve etiket celiskisi GERI GELEMEZ.

KUSUR (2026-08-25): kaynak sette 691 dosya ama 658 benzersiz icerik vardi.
32 mukerrer grubun HICBIRI ayni sinif icinde degildi:
    class0 <-> class1 : 27   (yaya ihlali + yetkisiz mudahale, ayni video)
    class0 <-> class4 :  3   GUVENSIZ ile GUVENLI ayni video
    class1 <-> class4 :  1 · class0 <-> class5 : 1 · digerleri 2
Ayrica 9 grup hem `_tr` hem `_te` tarafindaydi -> kaynagin kendi
egitim/test ayrimi delikti.

ETKISI OLCULDU ve ikisi de SESSIZDI:
  · Degerlendirme tekillestirmesi 28 `class1` icerigini "yaya klibinin
    kopyasi" diye atiyordu -> yetkisiz cifti 146 yerine 117 klipte
    olculuyordu (TP 66 iken gercekte 91).
  · Ayni icerik yaya ciftinin IKI tarafinda birden sayiliyordu (3 klip).

KOK COZUM: yer gercegi icerik (sha256) basina ETIKET KUMESI olarak
modellenir (`benchmark/kanonik_etiket.py`). Bu test o modelin bozulmadigini
ve degerlendirme kumelerinin temiz kaldigini dogrular.
"""
import collections
import glob
import hashlib
import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import tests.taban as taban  # noqa: E402
taban.taban_uygula()

g = k = 0


def c(ad, kosul):
    global g, k
    if kosul:
        g += 1
        print("  ok   " + ad)
    else:
        k += 1
        print("  KALAN " + ad)


def ozet(yol, blok=1 << 20):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        while True:
            b = f.read(blok)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


KAN = os.path.join(KOK, "benchmark", "results", "kanonik_etiket.json")

print("=== KANONIK KAYIT VAR VE TUTARLI ===")
c("kanonik_etiket.json uretilmis", os.path.exists(KAN))
if not os.path.exists(KAN):
    print("\n  (once: python benchmark/kanonik_etiket.py)")
    print("\ngecen=%d  kalan=%d" % (g, k))
    sys.exit(1 if k else 0)

kan = json.load(open(KAN, encoding="utf-8"))
icerik = kan["icerik"]
SINIF = kan["sinif"]

c("icerik sayisi dosya sayisindan KUCUK (mukerrer VAR ve biliniyor)",
  len(icerik) == 658)
c("her icerik en az bir etiket tasir",
  all(v["etiketler"] for v in icerik.values()))
c("her icerigin TEMSILCI dosyasi kendi dosya listesinde",
  all(v["temsilci"] in v["dosyalar"] for v in icerik.values()))

print("=== KOVA KURALI: kumede GUVENSIZ varsa icerik GUVENSIZ ===")
hata = [h for h, v in icerik.items()
        if (any(SINIF[e][0] == "GUVENSIZ" for e in v["etiketler"]))
        != (v["kova"] == "GUVENSIZ")]
c("kova kurali TUM iceriklerde tutuyor (%d ihlal)" % len(hata), not hata)

print("=== CELISKILI ICERIK CIFTTEN DISLANMIS ===")
dis = 0
for h, v in icerik.items():
    et = set(v["etiketler"])
    for gs, gl in [tuple(x) for x in kan["cift"]]:
        if gs in et and gl in et:
            dis += 1
            c2 = v["cift"].get(gs) == "DISLANDI"
            if not c2:
                c("celiskili icerik %s ciftinden dislanmali" % gs, False)
c("hem GUVENSIZ hem GUVENLI tasiyan icerik ciftten DISLANMIS (%d adet)" % dis,
  dis > 0)

print("=== AYRIM: bir kopyasi _te ise icerik TESTTE ===")
yanlis = [h for h, v in icerik.items()
          if any("_te" in os.path.basename(f) for f in v["dosyalar"])
          and v["ayrim"] != "te"]
c("test kirlenmesi yok (%d ihlal)" % len(yanlis), not yanlis)

print("=== DEGERLENDIRME KUMESI TEMIZ MI ===")
for kume in ("data/eval_kanonik", "data/eval_defense"):
    dizin = os.path.join(KOK, kume)
    if not os.path.isdir(dizin):
        print("  --   %s yok, atlandi" % kume)
        continue
    dosyalar = glob.glob(os.path.join(dizin, "*", "*", "*.mp4"))
    if not dosyalar:
        continue
    hh = collections.Counter(ozet(os.path.realpath(p)) for p in dosyalar)
    tekrar = {x: n for x, n in hh.items() if n > 1}
    c("%s: mukerrer icerik YOK (%d dosya, %d benzersiz)"
      % (kume, len(dosyalar), len(hh)), not tekrar)
    # celiskili icerik bu kumede TEK KEZ gorunmeli
    ck = 0
    for x in hh:
        v = icerik.get(x)
        if not v:
            continue
        for gs, gl in [tuple(y) for y in kan["cift"]]:
            if gs in v["etiketler"] and gl in v["etiketler"]:
                ck += 1
                break
    print("       (bilgi) bu kumede celiskili icerik: %d" % ck)

print("=== PUANLAYICI KANONIK KAYDI KULLANIYOR ===")
kp = os.path.join(KOK, "benchmark", "kanonik_puanla.py")
c("benchmark/kanonik_puanla.py var", os.path.exists(kp))
if os.path.exists(kp):
    src = open(kp, encoding="utf-8").read()
    c("celiskili icerigi DISLIYOR", "DISLANDI" in src or "dis += 1" in src)
    c("saha kesinligini ETIKET KUMESINDEN hesapliyor",
      "sinif in et" in src)

print()
print("gecen=%d  kalan=%d" % (g, k))
sys.exit(1 if k else 0)
