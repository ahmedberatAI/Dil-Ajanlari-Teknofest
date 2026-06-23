#!/usr/bin/env python
"""ÖLÇÜM DÜRÜSTLÜĞÜ: 'tespit-recall' (n_olay>0, hosgorulu) vs 'TANIMA-recall' (olay TIPI dogru mu, kati).

Sorun: mevcut recall = herhangi bir olay uretildi mi -> silahi kaciran Shooting klibi bile 'yakaladi'
sayiliyor. Bu betik, modelin olay-tipini DOGRU adlandirip adlandirmadigini olcer (kategori-ozel terimler).
Kayitli cevaplardan (answers_*.jsonl) okur — saydam, tekrar-uretilebilir, GPU yok."""
from __future__ import annotations
import glob, json, os, sys, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Her kategori icin modelin DOGRU tanima icin uretmesi GEREKEN olay-tipi terimleri (genis sinonim).
TERMS = {
    "Shooting":   ["silah", "ateş", "ates", "vuruldu", "vurdu", "tabanca", "kurşun", "kursun", "çatış", "catis", "atış", "atis", "namlu"],
    "Fighting":   ["kavga", "dövüş", "dovus", "çatış", "catis", "saldır", "saldir", "darp", "yumruk", "tekme", "şiddet", "siddet", "boğuş", "bogus"],
    "Assault":    ["saldır", "saldir", "darp", "şiddet", "siddet", "vur", "dövme", "dovme", "çatış", "catis", "yere düş", "yere dus", "yere yığıl", "yere yigil"],
    "Abuse":      ["şiddet", "siddet", "darp", "taciz", "saldır", "saldir", "vur", "istismar", "iter", "itme", "çekiştir"],
    "Burglary":   ["hırsız", "hirsiz", "soygun", "soyma", "gasp", "izinsiz", "yetkisiz", "çal", "cal", "kır", "kir", "zorla gir", "haneye"],
    "RoadAccidents": ["kaza", "çarpış", "carpis", "çarpma", "carpma", "devril", "ezil", "savrul", "çarptı", "carpti"],
    "Explosion":  ["patlama", "patladı", "patladi", "infilak", "patlay"],
    "Vandalism":  ["tahrip", "kır", "kir", "hasar", "vandal", "parçala", "parcala", "kırıl", "kiril", "zarar"],
}


def text_of(rec):
    return (" ".join(e.get("olay", "") for e in rec.get("events", [])) + " " + rec.get("summary", "")).lower()


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob(os.path.join(ROOT, "benchmark/results/answers_*.jsonl")))[-1]
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    cats = {}
    for r in rows:
        if not r.get("anom"):
            continue
        c = r["cat"]
        if c not in TERMS:   # Fire/Fall vb. — bu betik suc-tipi tanima icin TERMS'li kategorilere bakar
            continue
        cats.setdefault(c, []).append(r)

    print(f"Kaynak: {os.path.relpath(path, ROOT)}\n")
    print(f"{'KATEGORI':14s} {'n':>3} {'TESPIT-recall':>14} {'TANIMA-recall':>14}")
    print("-" * 50)
    tot_n = tot_det = tot_id = 0
    for c, rs in sorted(cats.items()):
        n = len(rs)
        det = sum(1 for r in rs if r.get("n", 0) > 0)                       # hosgorulu (mevcut metrik)
        idd = sum(1 for r in rs if any(t in text_of(r) for t in TERMS[c]))  # olay-tipi dogru adlandirildi mi
        tot_n += n; tot_det += det; tot_id += idd
        print(f"{c:14s} {n:>3} {100*det/n:>12.0f}% {100*idd/n:>13.0f}%")
    print("-" * 50)
    print(f"{'TOPLAM (suç)':14s} {tot_n:>3} {100*tot_det/max(tot_n,1):>12.0f}% {100*tot_id/max(tot_n,1):>13.0f}%")
    print(f"\n=> TESPIT-recall 'bir şey oldu mu' (hoşgörülü); TANIMA-recall 'olay TİPİ doğru mu' (dürüst).")
    print("   Fark = modelin kaçırdığı/yanlış-adlandırdığı suçlar (ölçüme yansımayan hatalar).")


if __name__ == "__main__":
    main()
