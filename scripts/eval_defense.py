#!/usr/bin/env python
"""SAVUNMA yetenegi eval: (1) yasak-bolge geofence recall+precision, (2) perimetre/izinsiz-giris recall."""
from __future__ import annotations
import glob, sys
sys.path.insert(0, ".")
from dilajan.config import settings
from dilajan.video import extract_timestamped_frames, build_segments
from dilajan import detector
from dilajan.agent.graph import analyze_video

ALL = ["üst sol","üst","üst sağ","sol","merkez","sağ","alt sol","alt","alt sağ"]
EMPTY_TRY = ["üst sol","üst sağ","alt sol","alt sağ","alt","üst"]
PERIM = ("Bu KRİTİK TESİS çevresine izinsiz giriş YASAKTIR; yetkisiz/izinsiz giren herhangi bir kişi "
         "perimetre ihlalidir (en az Yüksek).")


def occupied_regions(path):
    fr, _ = extract_timestamped_frames(path)
    occ = {}
    for s in build_segments(fr):
        occ.update(detector.detect_zone_intrusion(s.frames, ALL))
    return list(occ.keys())


def has_zone_evt(r):
    return any("yasak bölge" in e.event.lower() for e in r.events)


def main():
    # --- 1) GEOFENCE: kisi iceren klipler ---
    clips = (sorted(glob.glob("data/eval_big/Burglary/*.mp4"))[:4] +
             sorted(glob.glob("data/eval/Normal/*.mp4"))[:4])
    rec_hit = rec_tot = prec_ok = prec_tot = 0
    print("=== GEOFENCE (yasak-bölge ihlali) ===")
    for p in clips:
        occ = occupied_regions(p)
        if not occ:
            print(f"  {p.split('/')[-1]:30s} kişi yok, atla"); continue
        settings.restricted_zones = occ[0]
        rec_tot += 1
        hit = has_zone_evt(analyze_video(p))
        rec_hit += int(hit)
        empty = next((z for z in EMPTY_TRY if z not in occ), None)
        pr = ""
        if empty:
            settings.restricted_zones = empty
            prec_tot += 1
            fp = has_zone_evt(analyze_video(p))
            prec_ok += int(not fp)
            pr = f"| precision(boş='{empty}'): {'FP✗' if fp else 'temiz✓'}"
        print(f"  {p.split('/')[-1]:30s} dolu='{occ[0]}' recall:{'VAR✓' if hit else 'YOK✗'} {pr}")
    settings.restricted_zones = ""

    # --- 2) PERIMETRE/IZINSIZ-GIRIS recall (Burglary + PERIM kurali) ---
    print("\n=== PERİMETRE / İZİNSİZ GİRİŞ (Burglary + tesis kuralı) ===")
    settings.facility_rules = PERIM
    burg = sorted(glob.glob("data/eval_big/Burglary/*.mp4"))
    det = 0
    for p in burg:
        r = analyze_video(p)
        evs = [e for e in r.events if e.category.value == "Yetkisiz Erişim" or "izinsiz" in e.event.lower() or "yetkisiz" in e.event.lower()]
        hi = any(e.severity.value in ("Yüksek", "Kritik") for e in evs)
        det += int(bool(evs))
        print(f"  {p.split('/')[-1]:30s} izinsiz-giriş:{'VAR' if evs else 'YOK'} (Yüksek+:{'E' if hi else 'H'}) n_olay={len(r.events)}")
    settings.facility_rules = ""

    print("\n" + "=" * 60)
    print(f"GEOFENCE recall : {rec_hit}/{rec_tot} = {100*rec_hit/max(rec_tot,1):.0f}%")
    print(f"GEOFENCE prec.  : {prec_ok}/{prec_tot} = {100*prec_ok/max(prec_tot,1):.0f}% (boş bölgede yanlış-ihlal yok)")
    print(f"İZİNSİZ-GİRİŞ   : {det}/{len(burg)} = {100*det/max(len(burg),1):.0f}% (Burglary tespit)")


if __name__ == "__main__":
    main()
