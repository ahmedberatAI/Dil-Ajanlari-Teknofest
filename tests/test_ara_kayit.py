#!/usr/bin/env python
"""D36 — eval_clips ARA KAYIT (checkpoint) testleri.

    python tests/test_ara_kayit.py       # cikis kodu 0 = hepsi gecti

NEDEN VAR: 2026-08-17'de bilgisayar iki kez restart atti; sonuc yalnizca en sonda
yazildigi icin her seferinde ~1 saatlik GPU kosusu TAMAMEN kayboldu.

EN KRITIK TEST: ara-kayit dosya adi kosum kunyesinin hash'idir. Kunyeye davranis
degistiren bir bayrak EKLENMEZSE, acik/kapali kollar AYNI ara dosyayi paylasir ve
birbirinin satirlarini devralir -> A/B olcumu SESSIZCE zehirlenir. `isg_lens` ilk
eklendiginde tam bu hata olustu.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PY = sys.executable
_gecti = 0
_kaldi = 0


def check(ad, kosul, ayrinti=""):
    global _gecti, _kaldi
    if kosul:
        _gecti += 1
        print(f"  ok   {ad}")
    else:
        _kaldi += 1
        print(f"  FAIL {ad}  {ayrinti}")


def ara_yol(env_ek: dict) -> str:
    """Alt surecte cagirir — settings modul yuklenirken env'den okundugu icin sart."""
    env = dict(os.environ)
    env.update(env_ek)
    kod = ("import sys, os; sys.path.insert(0, %r);"
           "from benchmark.eval_clips import _ara_kayit_yol;"
           "print(os.path.basename(_ara_kayit_yol()))" % ROOT)
    return subprocess.run([PY, "-c", kod], capture_output=True, text=True,
                          env=env, cwd=ROOT).stdout.strip()


print("=== KUNYE IZOLASYONU: farkli yapilandirma -> farkli ara dosya ===")
temel = {"EVAL_CATS": "Anomali", "DILAJAN_EVAL_DIR": "data/eval_defense"}
adlar = {}
for etiket, ek in (
        ("isg_lens=false", {"DILAJAN_ISG_LENS": "false"}),
        ("isg_lens=true", {"DILAJAN_ISG_LENS": "true"}),
        ("ppe_detection=true", {"DILAJAN_ISG_LENS": "false", "DILAJAN_PPE_DETECTION": "true"}),
        ("kategori=Normal", {"DILAJAN_ISG_LENS": "false", "EVAL_CATS": "Normal"})):
    d = dict(temel)
    d.update(ek)
    adlar[etiket] = ara_yol(d)
    print(f"    {etiket:22s} -> {adlar[etiket]}")

check("hepsi bos degil (alt surec calisti)", all(adlar.values()), str(adlar))
check("dort yapilandirma DORT AYRI dosya kullaniyor",
      len(set(adlar.values())) == 4,
      f"benzersiz={len(set(adlar.values()))}/4 -> {adlar}")
check("isg_lens acik/kapali AYRI dosya (A/B zehirlenmesini onler)",
      adlar["isg_lens=false"] != adlar["isg_lens=true"])

print("\n=== YAZ / OKU / COKME DAYANIKLILIGI ===")
from benchmark.eval_clips import _ara_kayit_ekle, _ara_kayit_yukle  # noqa: E402

yol = os.path.join(ROOT, "benchmark", "results", ".ara_TEST_gecici.jsonl")
if os.path.exists(yol):
    os.remove(yol)
try:
    _ara_kayit_ekle(yol, {"path": "a/b.mp4", "n_events": 2})
    _ara_kayit_ekle(yol, {"path": "a/c.mp4", "n_events": 0})
    check("iki satir yazildi", os.path.exists(yol))

    # COKME TAKLIDI: son satir yarim kalmis (fsync ortasinda elektrik kesilmis gibi)
    with open(yol, "a", encoding="utf-8") as f:
        f.write('{"path": "a/d.mp')

    # _ara_kayit_yukle() yolu kunyeden kendi hesaplar; burada gecici dosyayi AYNI
    # ayristirma mantigiyla dogrudan okuyoruz (yarim satir davranisini sinamak icin).
    okunan = {}
    with open(yol, encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if not satir:
                continue
            try:
                r = json.loads(satir)
            except Exception:
                continue
            if isinstance(r, dict) and r.get("path"):
                okunan[r["path"]] = r
    check("yarim satir SESSIZCE atlandi, saglam satirlar korundu",
          sorted(okunan) == ["a/b.mp4", "a/c.mp4"], str(sorted(okunan)))
finally:
    if os.path.exists(yol):
        os.remove(yol)

print("\n=== YAZILAMAZ YOL: olcum DURMAMALI (K3 fail-open) ===")
try:
    _ara_kayit_ekle("/olmayan_kok_dizin_xyz/ara.jsonl", {"path": "x"})
    check("yazilamayan ara kayit istisna FIRLATMADI", True)
except Exception as e:
    check("yazilamayan ara kayit istisna FIRLATMADI", False, f"{type(e).__name__}: {e}")

print(f"\ngecen={_gecti}  kalan={_kaldi}")
sys.exit(1 if _kaldi else 0)
