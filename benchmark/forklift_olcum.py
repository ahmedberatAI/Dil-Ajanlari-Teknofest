#!/usr/bin/env python
"""D40 — dilajan/forklift.py'nin IKI YOLUNU da 50 klipte olcer.

    python benchmark/forklift_olcum.py --yontem geometri   # GPU/sunucu gerekmez
    python benchmark/forklift_olcum.py --yontem vlm
    python benchmark/forklift_olcum.py --yontem hepsi

NEDEN AYRI OLCUM: ajanin bildirdigi +0,718'lik deterministik sonucun kodu
elde kalmadi. Tarif uzerinden yeniden yazilan bu surumun KENDI sayisi olculur;
devralinan bir rakam RAPORLANMAZ.
"""
import argparse, glob, json, math, os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import forklift  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SET = os.environ.get("DILAJAN_PROB_SET") or os.path.join(KOK, "data/eval_defense")
IHLAL = "Anomali/Carrying_Overload_with_Forklift"
NORMAL = "Normal/Safe_Carrying"


def mcc(tp, fp, fn, tn):
    p = math.sqrt((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn))
    return (tp*tn - fp*fn)/p if p else 0.0


def wilson(k, n, z=1.96):
    if not n: return (0.0, 0.0)
    q = k/n; d = 1 + z*z/n
    m = (q + z*z/(2*n))/d
    y = z*math.sqrt(q*(1-q)/n + z*z/(4*n*n))/d
    return (max(0.0, m-y), min(1.0, m+y))


def kareler(yol, n=8):
    fr, _ = extract_timestamped_frames(yol)
    if len(fr) > n:
        a = len(fr)/n
        fr = [fr[min(len(fr)-1, int(i*a))] for i in range(n)]
    return [(f"{int(t)//60:02d}:{int(t)%60:02d}", j) for t, j in fr]


def rapor(ad, satir, esik):
    tp = fp = fn = tn = yok = 0
    for r in satir:
        n = r.get(ad)
        if n is None:
            yok += 1
            t = False
        else:
            t = n >= esik
        if r["ihlal"] and t: tp += 1
        elif r["ihlal"]: fn += 1
        elif t: fp += 1
        else: tn += 1
    N = tp+fp+fn+tn
    m = mcc(tp, fp, fn, tn); dog = (tp+tn)/N if N else 0
    lo, hi = wilson(tp+tn, N)
    poz = tp+fp
    dej = poz >= 0.85*N or (N-poz) >= 0.85*N
    print(f"{ad:14s} TP={tp:2d} FP={fp:2d} FN={fn:2d} TN={tn:2d}  olculemedi={yok:2d}  "
          f"MCC={m:+.3f}  dogruluk={dog:.3f} [{lo:.3f}-{hi:.3f}]"
          f"{'  ** DEJENERE **' if dej else ''}")
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "olculemedi": yok,
            "mcc": m, "dogruluk": dog, "dejenere": dej}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yontem", default="hepsi", choices=["geometri", "vlm", "hepsi"])
    ap.add_argument("--esik", type=int, default=forklift.ESIK_VARSAYILAN)
    a = ap.parse_args()

    yollar = [(y, True) for y in sorted(glob.glob(os.path.join(SET, IHLAL, "*.mp4")))] + \
             [(y, False) for y in sorted(glob.glob(os.path.join(SET, NORMAL, "*.mp4")))]
    print(f"set={SET}\nn={len(yollar)} klip · esik>={a.esik} kasa\n")

    istemci = None
    if a.yontem in ("vlm", "hepsi"):
        from dilajan.llm_client import VLMClient
        istemci = VLMClient()

    satir = []
    for i, (y, ihlal) in enumerate(yollar, 1):
        try:
            kar = kareler(y)
        except Exception as e:
            print(f"  [HATA] {os.path.basename(y)}: {e}"); continue
        r = {"klip": os.path.basename(y), "ihlal": ihlal}
        if a.yontem in ("geometri", "hepsi"):
            # MODULUN KARAR VERDIGI yol: perspektif duzeltmeli olcum.
            # (Ham boy/en orani yalnizca +0,280 veriyor; perspektif SART.)
            r["olcum"] = forklift.istif_olcum(kar)
        if a.yontem in ("vlm", "hepsi"):
            r["vlm"] = forklift.kasa_say_vlm(kar, istemci)
        satir.append(r)
        if i % 10 == 0 or i == len(yollar):
            print(f"  {i}/{len(yollar)}", flush=True)

    print()
    if a.yontem in ("geometri", "hepsi"):
        olc = [r["olcum"] for r in satir if r.get("olcum")]
        yu = forklift.ufuk_kestir(olc)
        fp = [forklift.perspektif_boy(r.get("olcum"), yu) for r in satir]
        gec = sorted([x for x in fp if x])
        esik_f = gec[len(gec)//2] if gec else forklift.F_PERS_ESIK_VARSAYILAN
        print(f"ETIKETSIZ kestirilen ufuk: y_ufuk={yu:.1f} px · "
              f"f_pers esigi (medyan)={esik_f:.4f}")
        print(f"  (modul varsayilanlari: y_ufuk={forklift.Y_UFUK_VARSAYILAN} "
              f"esik={forklift.F_PERS_ESIK_VARSAYILAN})")
        for r, f in zip(satir, fp):
            r["f_pers"] = f
            # ihlal = esigi asmak; rapor() sayiya bakiyor -> 3/0 ile kodla
            r["geometri"] = None if f is None else (3 if f > esik_f else 0)
        rapor("geometri", satir, a.esik)
        # sinif medyan orani — fiziksel dogrulama (3/2 = 1,500 beklenir)
        import statistics as _st
        A = [r["f_pers"] for r in satir if r["ihlal"] and r.get("f_pers")]
        B = [r["f_pers"] for r in satir if not r["ihlal"] and r.get("f_pers")]
        if A and B:
            print(f"  FIZIKSEL DOGRULAMA: ihlal/normal medyan orani = "
                  f"{_st.median(A)/_st.median(B):.3f}  (3/2 = 1,500 bekleniyor)")
    if a.yontem in ("vlm", "hepsi"):
        rapor("vlm", satir, a.esik)

    d = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = os.path.join(KOK, f"benchmark/results/forklift_olcum_{d}.json")
    json.dump({"set": SET, "esik": a.esik, "satirlar": satir},
              open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nKaydedildi: {os.path.relpath(p, KOK)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
