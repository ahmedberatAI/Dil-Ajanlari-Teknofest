#!/usr/bin/env python
"""YELEK dedektorunun GUVEN ESIGI taramasi — kullanilabilir bir nokta var mi?

SORUN (olculdu)
---------------
Yelek dedektoru test bolumunde:
    yelek_var  AP50 0,773  P 0,800  R 0,713
    yelek_yok  AP50 0,582  **P 0,535**  R 0,661     <- IHLAL sinifi
Baret dedektorunde ayni sinif P 0,893 / R 0,891 idi.

P=0,535 demek: "yelek yok" tespitlerinin yarisi YANLIS. Bu sistemde **yanlis alarm
en pahali hatadir** (sevk kapisinin varlik sebebi, HANDOFF §3) -> bu haliyle
deterministik dogrulayici olarak kullanilamaz.

BU BETIK NE YAPAR
-----------------
Guven esigini tarar ve her esikte KUTU DUZEYI precision/recall olcer. Amac tek bir
soruyu yanitlamak: **precision'i kabul edilebilir seviyeye (>=0,85) cikaran bir
esik var mi, ve orada recall'dan ne kaliyor?**

Cevap "hayir" ise dedektor **YAYINLANMAZ** — yetersiz oldugu YAZILIR. Zayif bir
dedektoru "calisiyor" diye sunmak, hic dedektor olmamasindan kotudur.

⚠️ NOT: bu KUTU duzeyi olcumdur. Uretimde ayrica `ppe_min_kare` (varsayilan 2)
KLIP duzeyinde ikinci bir suzgectir — gercek klip-duzeyi precision buradan
DAHA IYI olur. Ama once kutu duzeyinde bir taban gerekir.

Kullanim:
    python scripts/yelek_esik_tara.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

VERI = os.path.join(ROOT, "data", "yelek_yolo", "yelek.yaml")
AGIRLIK = os.path.join(ROOT, "yolo11n-yelek.pt")
#: ---------------------------------------------------------------------------
#: KABUL OLCUTU — IKI TARAFLI OLMAK ZORUNDA
#: ---------------------------------------------------------------------------
#: ⚠️ ILK SURUM YANLISTI: yalnizca `precision >= 0,85` araniyordu. Tarama conf=0,85
#: noktasinda P=1,000 buldu ve "KULLANILABILIR" dedi — ama orada **R=0,049** idi,
#: yani ihlallerin %5'i yakalaniyordu. Tek yanli olcut, ise yaramaz bir dedektore
#: gecer not verdi. (Esigi yukselttikce precision zaten 1'e gider; bu bir basari
#: degil, olcutun kusurudur.)
#:
#: Dogru olcut IKI TARAFLI: hem yanlis alarm kabul edilebilir olmali, hem de
#: dedektor gercekten bir sey YAKALAMALI. Guvenlikte kacirma pahalidir (F2'nin
#: recall'a agirlik vermesinin sebebi de bu, HANDOFF §7.6).
PRECISION_ESIGI = 0.85
RECALL_ESIGI = 0.50


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--esikler", default="0.25,0.35,0.45,0.55,0.65,0.75,0.85")
    ap.add_argument("--split", default="test")
    ap.add_argument("--json", dest="json_out",
                    default=os.path.join("benchmark", "results", "yelek_esik_tarama.json"))
    args = ap.parse_args()

    if not os.path.exists(AGIRLIK):
        print(f"[HATA] {os.path.relpath(AGIRLIK, ROOT)} yok — once egitin")
        return 1

    from ultralytics import YOLO
    m = YOLO(AGIRLIK)
    adlar = list(m.names.values())

    print("=" * 86)
    print("YELEK dedektoru — GUVEN ESIGI TARAMASI")
    print(f"  kabul esigi: ihlal sinifinda precision >= {PRECISION_ESIGI}")
    print("  ⚠️ kutu duzeyi olcum; uretimde ppe_min_kare KLIP duzeyinde ek suzgectir")
    print("=" * 86)
    print(f"{'conf':>6} | {'sinif':12} | {'P':>7} | {'R':>7} | {'F1':>7}")
    print("-" * 86)

    kayit = []
    for e in [float(x) for x in args.esikler.split(",")]:
        try:
            r = m.val(data=VERI, split=args.split, conf=e, device=0, verbose=False)
            kutu = r.box
        except Exception as ex:  # noqa: BLE001
            print(f"{e:>6.2f} | [HATA] {type(ex).__name__}: {ex}")
            continue
        satir = {"conf": e, "siniflar": {}}
        for i, ad in enumerate(adlar):
            p, rc = float(kutu.p[i]), float(kutu.r[i])
            f1 = 2 * p * rc / (p + rc) if (p + rc) else 0.0
            satir["siniflar"][ad] = {"P": round(p, 4), "R": round(rc, 4), "F1": round(f1, 4)}
            isaret = (" ✅" if (ad.endswith("_yok") and p >= PRECISION_ESIGI
                                and rc >= RECALL_ESIGI) else "")
            print(f"{e:>6.2f} | {ad:12} | {p:>7.3f} | {rc:>7.3f} | {f1:>7.3f}{isaret}")
        kayit.append(satir)
        print("-" * 86)

    # --- KARAR ---
    def _y(k):
        return k["siniflar"].get("yelek_yok", {})

    uygun = [k for k in kayit
             if _y(k).get("P", 0) >= PRECISION_ESIGI and _y(k).get("R", 0) >= RECALL_ESIGI]
    print("\n" + "=" * 86)
    print(f"KABUL OLCUTU (IKI TARAFLI): yelek_yok P >= {PRECISION_ESIGI} "
          f"VE R >= {RECALL_ESIGI}")
    if uygun:
        en_iyi = max(uygun, key=lambda k: _y(k)["R"])
        s = _y(en_iyi)
        print(f"KARAR: ✅ KULLANILABILIR — conf={en_iyi['conf']:.2f} noktasinda "
              f"P={s['P']:.3f} R={s['R']:.3f}")
        print(f"       yelek kiti icin `ppe_conf = {en_iyi['conf']:.2f}` yapilmali.")
    else:
        en_p = max((_y(k).get("P", 0) for k in kayit), default=0.0)
        en_r = max((_y(k).get("R", 0) for k in kayit), default=0.0)
        # Precision'i saglayan noktada recall ne oluyor? (olcutun NEDEN dustugunu goster)
        p_ok = [k for k in kayit if _y(k).get("P", 0) >= PRECISION_ESIGI]
        detay = ""
        if p_ok:
            b = max(p_ok, key=lambda k: _y(k)["R"])
            detay = (f" Precision esigi yalnizca conf={b['conf']:.2f}'te saglaniyor "
                     f"(P={_y(b)['P']:.3f}) ama orada R={_y(b)['R']:.3f} — "
                     f"ihlallerin %{100 * _y(b)['R']:.0f}'i yakalaniyor.")
        print(f"KARAR: ❌ **DAGITILMAZ** — hicbir esik IKI kosulu birden saglamiyor.")
        print(f"       en iyi P={en_p:.3f} · en iyi R={en_r:.3f}.{detay}")
        print("       Zayif bir dedektoru 'calisiyor' diye sunmak, hic dedektor")
        print("       olmamasindan KOTUDUR: yanlis alarm en pahali hatadir.")
        print("       Gerekli: yelek sinifi icin DAHA COK veri (su an 741 egitim kutusu;")
        print("       baret dedektorunde 9.797 kutu vardi ve P=0,893 / R=0,891 verdi).")
    print("=" * 86)

    if args.json_out:
        yol = args.json_out if os.path.isabs(args.json_out) else os.path.join(ROOT, args.json_out)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            json.dump({
                "_aciklama": ("Yelek dedektoru guven esigi taramasi. Kabul kosulu: "
                              f"ihlal sinifinda (yelek_yok) precision >= {PRECISION_ESIGI}."),
                "agirlik": os.path.basename(AGIRLIK),
                "split": args.split,
                "precision_esigi": PRECISION_ESIGI,
                "kutu_duzeyi": True,
                "not": ("Uretimde ppe_min_kare KLIP duzeyinde ek suzgectir; gercek "
                        "klip-duzeyi precision bundan daha iyi olur."),
                "tarama": kayit,
                "kullanilabilir": bool(uygun),
            }, f, ensure_ascii=False, indent=2)
        print(f"Kaydedildi: {os.path.relpath(yol, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
