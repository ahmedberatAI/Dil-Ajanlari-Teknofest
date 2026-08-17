#!/usr/bin/env python
"""Kurulan verinin BIZIMKIYLE AYNI oldugunu dogrular. GPU gerekmez.

NEDEN SART: farkli klip kumesiyle cikan sayi bizim arsivlerimizle
KARSILASTIRILAMAZ. Ornegin eval_defense'te 200 klip goruyorsan uc celiskili
klibi cikarmamissin demektir ve tum MCC degerlerin bizimkinden kayar.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = (".mp4", ".avi", ".mkv", ".mov")

# Beklenen durum — D36 sonrasi (2026-08-17)
BEKLENEN = {
    "data/eval_defense/Anomali": 99,
    "data/eval_defense/Normal": 98,
    "data/isafety_bench": 1100,
}
AGIRLIKLAR = ["yolo11n-ppe.pt", "yolo11n-yelek.pt"]
KARANTINA = "data/eval_defense/_celiskili_cikarildi"

_ok = _hata = _uyari = 0


def sonuc(ad, durum, ayrinti=""):
    global _ok, _hata, _uyari
    isaret = {"ok": "  OK  ", "hata": " HATA ", "uyari": "UYARI "}[durum]
    print(f"{isaret} {ad}" + (f"   {ayrinti}" if ayrinti else ""))
    if durum == "ok":
        _ok += 1
    elif durum == "hata":
        _hata += 1
    else:
        _uyari += 1


def say(rel):
    tam = os.path.join(KOK, rel)
    if not os.path.isdir(tam):
        return None
    n = 0
    for _k, _d, dosyalar in os.walk(tam):
        n += sum(1 for f in dosyalar if f.lower().endswith(VIDEO))
    return n


print("=" * 74)
print("KLIP SAYILARI")
print("=" * 74)
for rel, bek in BEKLENEN.items():
    n = say(rel)
    if n is None:
        sonuc(rel, "hata", "dizin YOK — veri_kur.py kosuldu mu?")
    elif n == bek:
        sonuc(rel, "ok", f"{n} klip")
    elif rel.startswith("data/eval_defense") and n == bek + 1:
        sonuc(rel, "hata", f"{n} klip (beklenen {bek}) — CELISKILI KLIPLER CIKARILMAMIS. "
                           f"Bkz. {KARANTINA}")
    else:
        sonuc(rel, "hata", f"{n} klip, beklenen {bek}")

print()
print("=" * 74)
print("KARANTINA (uc celiskili klip olcume GIRMEMELI)")
print("=" * 74)
kar = os.path.join(KOK, KARANTINA)
if os.path.isdir(kar):
    n = sum(1 for f in os.listdir(kar) if f.lower().endswith(VIDEO))
    sonuc("karantina klasoru", "ok" if n == 3 else "uyari", f"{n} klip (beklenen 3)")
else:
    sonuc("karantina klasoru", "uyari",
          "YOK — build_defense_eval.py eski surum olabilir; 197 sayisi tutuyorsa sorun degil")

print()
print("=" * 74)
print("KUNYE (MANIFEST) MD5 KONTROLU — ornekleme")
print("=" * 74)
man = os.path.join(KOK, "data/eval_defense/MANIFEST.json")
if not os.path.exists(man):
    sonuc("eval_defense/MANIFEST.json", "hata", "YOK")
else:
    d = json.load(open(man, encoding="utf-8"))
    kayitlar = [k for k in (d.get("klipler") or d.get("kayitlar") or [])
                if isinstance(k, dict) and k.get("md5") and k.get("hedef")]
    if not kayitlar:
        sonuc("MANIFEST icerigi", "uyari", "md5/hedef alani bulunamadi, atlaniyor")
    else:
        # Ilk 8 kaydi ornekle — tamami dakikalar surer
        kontrol = kayitlar[:8]
        tut = kay = 0
        for k in kontrol:
            yol = os.path.join(KOK, str(k["hedef"]).replace("\\", "/"))
            if not os.path.exists(yol):
                kay += 1
                continue
            h = hashlib.md5(open(yol, "rb").read()).hexdigest()
            tut += (h == k["md5"])
        if kay:
            sonuc("MD5 ornekleme", "uyari",
                  f"{kay}/{len(kontrol)} dosya bulunamadi (karantinaya alinmis olabilir)")
        sonuc("MD5 ornekleme", "ok" if tut == len(kontrol) - kay else "hata",
              f"{tut}/{len(kontrol) - kay} eslesti")

print()
print("=" * 74)
print("EGITILMIS AGIRLIKLAR")
print("=" * 74)
for a in AGIRLIKLAR:
    yol = os.path.join(KOK, a)
    if os.path.exists(yol):
        sonuc(a, "ok", f"{os.path.getsize(yol)/1e6:.1f} MB")
    else:
        sonuc(a, "hata", "YOK — `cp paylasim/agirliklar/*.pt .`")

print()
print("=" * 74)
print("LISANS KAPISI (fail-closed calisiyor mu)")
print("=" * 74)
sys.path.insert(0, KOK)
try:
    from dilajan.veri_lisans import LisansIhlali, egitim_icin_dogrula
    try:
        egitim_icin_dogrula(["data/isafety_bench"])
        sonuc("lisans kapisi", "hata", "KAPI ACIK KALDI — yasakli dizin gecti!")
    except LisansIhlali:
        sonuc("lisans kapisi", "ok", "fail-closed dogrulandi")
except Exception as e:
    sonuc("lisans kapisi", "uyari", f"sinanamadi: {type(e).__name__}")

print()
print("=" * 74)
print(f"OK={_ok}  HATA={_hata}  UYARI={_uyari}")
if _hata:
    print("\n⛔ HATA VAR — OLCUM YAPMA. Farkli klip kumesiyle cikan sayi bizim")
    print("   arsivlerimizle karsilastirilamaz.")
else:
    print("\n✅ Kurulum bizimkiyle uyumlu. Olcume gecebilirsin.")
raise SystemExit(1 if _hata else 0)
