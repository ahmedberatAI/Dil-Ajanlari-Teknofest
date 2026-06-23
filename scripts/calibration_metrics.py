#!/usr/bin/env python
"""ORDINAL RISK-KALIBRASYON metrikleri (Agent-C #1) — ikili '>=Yuksek' yerine.
QWK (quadratic weighted kappa), severity MAE + isaretli sapma (sistematik dusuk-puanlama?),
beklenen-MALIYET (asimetrik: tehlikeyi dusuk-puanlamak 10x pahali), 4x4 karisiklik matrisi.
Kayitli cevaplardan (answers_*.jsonl), GPU'suz, seffaf. Juri-yuzlu kalibrasyon kaniti."""
from __future__ import annotations
import glob, json, os, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORD = {"Düşük": 1, "Orta": 2, "Yüksek": 3, "Kritik": 4}
# Yer-gercegi beklenen severity tier'i (kategori -> tier). Hayati tehdit=4, ciddi guvenlik=3, normal=1.
GT = {
    "Fire": 4, "Explosion": 4, "Shooting": 4, "Fall": 4,
    "Fighting": 3, "Assault": 3, "Abuse": 3, "RoadAccidents": 3, "Burglary": 3, "Vandalism": 3,
    "Normal": 1,
}
# Asimetrik maliyet: under-rate (tehlikeyi dusuk gosterme) AGIR; over-rate hafif.
def cost(gt, pred):
    d = gt - pred
    return (10 * d) if d > 0 else (1 * -d)  # under: 10x/tier, over: 1x/tier


def qwk(gt, pred, k=4):
    gt = np.asarray(gt); pred = np.asarray(pred)
    O = np.zeros((k, k))
    for g, p in zip(gt, pred):
        O[g-1, p-1] += 1
    w = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            w[i, j] = ((i - j) ** 2) / ((k - 1) ** 2)
    gh = O.sum(1); ph = O.sum(0); N = O.sum()
    E = np.outer(gh, ph) / max(N, 1)
    num = (w * O).sum(); den = (w * E).sum()
    return 1 - num / den if den > 0 else 1.0


def pred_tier(r):
    return ORD.get(r.get("risk", "Düşük"), 1)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob(os.path.join(ROOT, "benchmark/results/answers_*.jsonl")))[-1]
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    rows = [r for r in rows if r.get("cat") in GT]
    gts = [GT[r["cat"]] for r in rows]
    prs = [pred_tier(r) for r in rows]

    print(f"Kaynak: {os.path.relpath(path, ROOT)}  (n={len(rows)})\n")
    # genel
    mae = np.mean([abs(g-p) for g, p in zip(gts, prs)])
    bias = np.mean([p-g for g, p in zip(gts, prs)])  # <0 = sistematik dusuk-puanlama
    k = qwk(gts, prs)
    ec = np.mean([cost(g, p) for g, p in zip(gts, prs)])
    print(f"QWK (ordinal uyum, 1=mukemmel)     : {k:.3f}")
    print(f"Severity MAE (kademe)              : {mae:.2f}")
    print(f"İşaretli sapma (<0 = düşük-puanlama): {bias:+.2f}")
    print(f"Beklenen maliyet (asimetrik 10:1)  : {ec:.2f}")

    # 4x4 karisiklik (yer-gercegi satir, tahmin sutun)
    print("\nKarışıklık matrisi (satır=GT tier, sütun=tahmin):")
    print("        D    O    Y    K")
    M = np.zeros((4, 4), int)
    for g, p in zip(gts, prs):
        M[g-1, p-1] += 1
    lbl = ["D", "O", "Y", "K"]
    for i in range(4):
        print(f"  {lbl[i]}  " + " ".join(f"{M[i,j]:4d}" for j in range(4)))

    # anomali alt-kume (tehlike kategorileri) — asil ilgi
    ai = [i for i, r in enumerate(rows) if GT[r["cat"]] >= 3]
    ag = [gts[i] for i in ai]; ap = [prs[i] for i in ai]
    under = sum(1 for g, p in zip(ag, ap) if p < g)
    print(f"\nTehlike klipleri (n={len(ai)}): düşük-puanlanan = {under} ({100*under/max(len(ai),1):.0f}%)  "
          f"| >=Yüksek doğru = {100*sum(1 for p in ap if p>=3)/max(len(ap),1):.0f}%")
    print("\n=> Tek '>=Yüksek %' yerine: QWK + MAE + asimetrik-maliyet, kalibrasyonu ordinal+maliyet-duyarlı ölçer.")


if __name__ == "__main__":
    main()
