#!/usr/bin/env python
"""KULLANIM-AMACINA uygun metrik: TANIMA-recall (ince UCF-etiketi) yaninda AKSIYON-recall
(dogru GUVENLIK-TEPKI sinifi). Bir guvenlik ajani icin Shooting'i "siddetli saldiri Yuksek" demek
DOGRU tepkidir; UCF alt-etiketini (Shooting vs Fighting) ayirt etmek grenli'de girdi-tavani.

Super-sinif (guvenlik tepkisi):
  SIDDET   = Shooting/Fighting/Assault/Abuse  -> kavga/saldiri/silah/yere dusme...
  MULK     = Burglary/Vandalism               -> hirsiz/izinsiz/tahrip/kirma...
  KAZA     = RoadAccidents                     -> kaza/carpisma/devrilme...
  YANGIN   = Explosion                         -> patlama/yangin/duman...
Kayitli cevaplardan, GPU'suz, seffaf."""
from __future__ import annotations
import glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUPER = {
    "Shooting": "SIDDET", "Fighting": "SIDDET", "Assault": "SIDDET", "Abuse": "SIDDET",
    "Burglary": "MULK", "Vandalism": "MULK", "RoadAccidents": "KAZA", "Explosion": "YANGIN",
}
TERMS = {
    "SIDDET": ["kavga", "dövüş", "dovus", "saldır", "saldir", "şiddet", "siddet", "darp", "vur", "yumruk",
               "tekme", "çatış", "catis", "silah", "ateş", "ates", "boğuş", "bogus", "itiş", "itis",
               "yere düş", "yere dus", "yere yığıl", "yere yigil", "yerde yat", "yere yat", "müdahale",
               "saldırgan", "saldirgan", "fiziksel temas", "hareketsiz", "vuruldu", "çekiştir"],
    "MULK": ["hırsız", "hirsiz", "soygun", "izinsiz", "yetkisiz", "çal", "cal", "kır", "kir", "tahrip",
             "hasar", "gasp", "haneye", "zorla", "parçala", "parcala", "vandal"],
    "KAZA": ["kaza", "çarpış", "carpis", "çarpma", "carpma", "devril", "ezil", "savrul", "çarptı", "carpti"],
    "YANGIN": ["patlama", "patladı", "patladi", "infilak", "yangın", "yangin", "duman", "alev"],
}


def text_of(r):
    return (" ".join(e.get("olay", "") for e in r.get("events", [])) + " " + r.get("summary", "")).lower()


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob(os.path.join(ROOT, "benchmark/results/answers_*.jsonl")))[-1]
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    cats = {}
    for r in rows:
        if r.get("anom") and r["cat"] in SUPER:
            cats.setdefault(r["cat"], []).append(r)

    print(f"Kaynak: {os.path.relpath(path, ROOT)}\n")
    print(f"{'KATEGORI':14s} {'süper':8s} {'n':>3} {'TESPIT':>7} {'AKSIYON':>8}")
    print("-" * 48)
    tn = tdet = tact = 0
    for c in sorted(cats):
        rs = cats[c]; sup = SUPER[c]; terms = TERMS[sup]
        n = len(rs)
        det = sum(1 for r in rs if r.get("n", 0) > 0)
        act = sum(1 for r in rs if any(t in text_of(r) for t in terms))
        tn += n; tdet += det; tact += act
        print(f"{c:14s} {sup:8s} {n:>3} {100*det/n:>6.0f}% {100*act/n:>7.0f}%")
    print("-" * 48)
    print(f"{'TOPLAM':14s} {'':8s} {tn:>3} {100*tdet/max(tn,1):>6.0f}% {100*tact/max(tn,1):>7.0f}%")
    print(f"\n=> AKSIYON-recall: model dogru GUVENLIK-TEPKI sinifini tetikledi mi (Shooting->'siddet' = DOGRU).")
    print("   Ince UCF alt-etiketi (TANIMA) grenli'de girdi-tavani; aksiyon-duzeyi kullanim-amacina uygun.")


if __name__ == "__main__":
    main()
