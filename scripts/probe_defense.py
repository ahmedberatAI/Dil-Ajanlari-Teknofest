#!/usr/bin/env python
"""Savunma-perimetre baseline probe: facility_rules (yasak bölge / kritik tesis) ile
izinsiz-giris (Burglary), silahli-tehdit (Shooting) ve kisitli-bolge senaryolarinda sistem ne uretiyor?
Eksigi gormek icin (eklemeden ONCE)."""
from __future__ import annotations
import glob, os, sys
sys.path.insert(0, ".")
from dilajan.config import settings
from dilajan.agent.graph import analyze_video


def sv(x):
    return getattr(x, "value", x)


def show(tag, path, rule):
    settings.facility_rules = rule
    r = analyze_video(path)
    print(f"\n### {tag}  —  {os.path.basename(path)}")
    print(f"   KURAL: {rule[:90]}")
    print(f"   RISK: {sv(r.risk.level)}")
    for e in r.events:
        reg = f", bölge={e.region}" if getattr(e, "region", None) else ""
        print(f"     [{e.time}] {e.event[:70]} ({sv(e.severity)}/{sv(e.category)}{reg})")
    print(f"   OZET: {r.summary[:160]}")


PERIM = ("Bu KRİTİK TESİS çevresine izinsiz giriş YASAKTIR. Çevre/tel-örgü/duvar aşan veya "
         "yetkisiz bölgeye giren herhangi bir kişi PERİMETRE İHLALİ'dir (en az Yüksek önem).")
ZONE = ("Karenin ÜST-SAĞ bölgesi YASAK askeri bölgedir. Bu bölgede görünen herhangi bir KİŞİ "
        "izinsiz bölge ihlalidir (Yüksek). Diğer bölgeler serbesttir.")

burg = sorted(glob.glob("data/eval_big/Burglary/*.mp4"))[:2]
shoot = sorted(glob.glob("data/eval_big/Shooting/*.mp4"))[:1]
norm = sorted(glob.glob("data/eval/Normal/*.mp4"))[:1]

for p in burg:
    show("İZİNSİZ GİRİŞ (Burglary)", p, PERIM)
for p in shoot:
    show("SİLAHLI TEHDİT (Shooting)", p, PERIM)
for p in norm:
    show("KISITLI-BÖLGE (Normal + yasak-bölge kuralı)", p, ZONE)
