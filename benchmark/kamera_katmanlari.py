#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Kamera katmanlarini hesapla ve KAYDET — karistiricidan arinmis olcum icin.

NEDEN: Bu veri setinde etiket, kisiler silinmis arka plandan %72,8 (yaya) /
%79,7 (yetkisiz) dogrulukla tahmin edilebiliyor — siniflar farkli cekilmis.
Daha fazla veri bunu ZAYIFLATMIYOR (dengeli alt-orneklemde 197 klipteki
degerin AYNISI cikti). Ama daha fazla veri baska bir kapiyi aciyor:

    48 klipte KATMANLI ANALIZ IMKANSIZDI. 285 klipte MUMKUN.

Klipler arka plan imzasina gore kumelenir; her iki etiketi de yeterli sayida
iceren kume, icinde yapilan olcumun KARISTIRICIDAN ARINMIS oldugu bir
katmandir. Kural o katmanda da ayirt ediyorsa skor kadrajdan gelmiyordur.

CPU, API cagrisi YOK. Cikti: benchmark/results/kamera_katmanlari.json

Kullanim:  python benchmark/kamera_katmanlari.py [--k 2]
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
from dilajan.config import yerel_cihaz          # noqa: E402
from ultralytics import YOLO                    # noqa: E402

SET = os.path.join(KOK, "data", "eval_full")
CIFTLER = [
    ("yaya", "Anomali/Safe_Walkway_Violation", "Normal/Safe_Walkway"),
    ("yetkisiz", "Anomali/Unauthorized_Intervention", "Normal/Authorized_Intervention"),
    ("pano", "Anomali/Opened_Panel_Cover", "Normal/Closed_Panel_Cover"),
    ("forklift", "Anomali/Carrying_Overload_with_Forklift", "Normal/Safe_Carrying"),
]
ASGARI = 15          # bir katmanin kullanilabilir sayilmasi icin her etiketten en az


def _kare(yol, n=45, w=320):
    f = tempfile.mktemp(suffix=".png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", yol, "-vf",
                    "select=eq(n\\," + str(n) + "),scale=%d:-2" % w,
                    "-vframes", "1", f], check=False)
    return f if os.path.exists(f) else None


def arkaplan_vektoru(yol, model):
    """Kisiler MASKELENMIS arka plandan 6x8 renk izgarasi (144 boyut)."""
    f = _kare(yol)
    if not f:
        return None
    a = np.asarray(Image.open(f).convert("RGB")).astype(np.float32)
    H, W = a.shape[:2]
    r = model.predict(f, device=yerel_cihaz(), verbose=False, conf=0.20)[0]
    gec = np.ones((H, W), dtype=bool)
    for b in r.boxes:
        if int(b.cls) != 0:
            continue
        x1, y1, x2, y2 = [int(v) for v in b.xyxy[0]]
        dw, dh = int(0.3 * (x2 - x1)), int(0.3 * (y2 - y1))
        gec[max(0, y1 - dh):min(H, y2 + dh),
            max(0, x1 - dw):min(W, x2 + dw)] = False
    os.unlink(f)
    v = []
    for i in range(6):
        for j in range(8):
            dy, dx = H // 6, W // 8
            blok = a[i * dy:(i + 1) * dy, j * dx:(j + 1) * dx]
            m = gec[i * dy:(i + 1) * dy, j * dx:(j + 1) * dx]
            v.extend(list(blok[m].mean(axis=0) / 255.0) if m.sum() > 20
                     else [0.0, 0.0, 0.0])
    return v


def kmeans(X, k, tohum=0, tur=80):
    rng = np.random.RandomState(tohum)
    C = X[rng.choice(len(X), k, replace=False)].copy()
    a = None
    for _ in range(tur):
        d = ((X[:, None, :] - C[None, :, :]) ** 2).sum(axis=2)
        a = d.argmin(axis=1)
        yeni = np.stack([X[a == j].mean(axis=0) if (a == j).any() else C[j]
                         for j in range(k)])
        if np.allclose(yeni, C):
            break
        C = yeni
    return a


def main():
    k = 2
    if "--k" in sys.argv:
        k = int(sys.argv[sys.argv.index("--k") + 1])
    model = YOLO("yolo11n.pt")
    cikti = {"k": k, "asgari": ASGARI, "ciftler": {}}
    for ad, d_ihl, d_nrm in CIFTLER:
        yollar, y = [], []
        for d, et in ((d_ihl, 1), (d_nrm, 0)):
            for p in sorted(glob.glob(os.path.join(SET, d, "*.mp4"))):
                v = arkaplan_vektoru(p, model)
                if v is not None:
                    yollar.append(os.path.basename(p))
                    y.append(et)
                    cikti.setdefault("_X", []).append(v)
        X = np.array(cikti.pop("_X"))
        y = np.array(y)
        a = kmeans(X, k)
        kumeler = []
        print("\n### %s   n=%d (ihlal %d / normal %d)"
              % (ad, len(y), int(y.sum()), int((1 - y).sum())))
        for j in range(k):
            m = a == j
            i1, i0 = int(y[m].sum()), int((1 - y[m]).sum())
            uygun = min(i1, i0) >= ASGARI
            kumeler.append({"kume": j, "n": int(m.sum()), "ihlal": i1,
                            "normal": i0, "kullanilabilir": uygun,
                            "klipler": [yollar[i] for i in np.where(m)[0]]})
            print("   kume%d n=%-4d ihlal=%-4d normal=%-4d %s"
                  % (j, m.sum(), i1, i0,
                     "<< KARISTIRICIDAN ARINMIS KATMAN" if uygun else ""))
        cikti["ciftler"][ad] = kumeler
    yol = os.path.join(KOK, "benchmark", "results", "kamera_katmanlari.json")
    json.dump(cikti, open(yol, "w", encoding="utf-8"), ensure_ascii=False)
    print("\nkaydedildi: " + os.path.relpath(yol, KOK))
    return 0


if __name__ == "__main__":
    sys.exit(main())
