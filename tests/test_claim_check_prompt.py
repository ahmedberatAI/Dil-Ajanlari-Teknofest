#!/usr/bin/env python
"""CLAIM-CHECK PROMPT: few-shot sinirlari gevseyemez.

Bu test model kosmaz; yalniz yuksek-risk iddia kontrolu promptunun karar
sinirlarini ve minimal genel few-shot dagilimini kilitler.
"""
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from dilajan import prompts as P  # noqa: E402

g = k = 0


def c(ad, kosul):
    global g, k
    if kosul:
        g += 1
        print("  ok  ", ad)
    else:
        k += 1
        print("  FAIL", ad)


prompt = P.CLAIM_CHECK_INSTRUCTION
lower = prompt.lower()

print("=== KARAR SINIRI NET ===")
for verdict in ("confirm", "split", "weaken", "abstain"):
    c(f"{verdict} tanimli", f"- {verdict}:" in lower)
c("karar sirasi var", "KARAR SIRASI:" in prompt)
c("abstain temel kanit yokken kullanilmiyor",
  "temel görsel kanıt yoksa \"weaken\"" in prompt)
c("split kept_event icinde kanitsiz iddia tekrarlanmaz",
  "kept_event içinde tekrar etme" in prompt)
c("belirsiz coklu karar yok", "split veya confirm" not in lower)
c("belirsiz abstain/confirm yok", "abstain veya confirm" not in lower)

print()
print("=== FEW-SHOT DAGILIMI DENGELI ===")
for parca in (
    "elektrik panosu açık",
    "kişi aniden zemine düşüyor",
    "yerdeki şey koli veya alet",
    "forklift yükle ilerliyor",
    "araç/forklift devrilmiş",
    "alev veya yoğun duman",
    "ışık yansıması/parlama",
    "iki kişi birbirine vuruyor",
    "kişi doğrudan yerde hareketsiz",
):
    c(f"ornek var: {parca}", parca in prompt)

print()
print("=== ALT IDDIALAR AYRIK ===")
for alan in (
    "person_visible",
    "person_on_floor",
    "person_motionless_or_fallen",
    "direct_contact_or_impact",
    "vehicle_impact_or_rollover_visible",
    "fire_or_smoke_visible",
    "weapon_visible",
    "causal_link_supported",
    "object_not_person_risk",
):
    c(f"subclaim var: {alan}", alan in prompt)
c("eski birlesik alan kaldirildi",
  "spark_smoke_fire_or_weapon_visible" not in prompt)

print()
print("=== KAPSAM KORUNDU ===")
c("yeni olay ekleme yasagi var", "Yeni olay ekleme" in prompt)
c("yalniz json sozlesmesi var", "YALNIZCA şu JSON formatında yanıt ver" in prompt)
c("verdict sozlesmesi korunuyor",
  '"verdict":"confirm|weaken|split|abstain"' in prompt)

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
