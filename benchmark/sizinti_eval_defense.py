#!/usr/bin/env python
"""D36 — `data/eval_defense` SAHNE DUZEYINDE SIZINTI KAYDI.

NEDEN VAR: manifest yalnizca dosya adi + MD5 taramasi yapiyordu ve SET-ICI sahne
ortusmesini HIC aramamisti. Piksel duzeyinde zamansal hizalama ile olculdu
(200x200 cift; gurultu tabani 0,476 MAD olculerek, null kontrolu 5-30x daha yuksek,
esik duyarliligi duz: 0,33->25 cift, 0,50->26, 0,75->27).

BULUNAN: 12 capraz (Anomali-Normal) cift, 20 klip (%10), 47,1 sn piksel-ozdes
ortak goruntu. Bunlarin UCU TAM KAPSAMA: kisa klip bututunuyle uzun klibin icinde,
ama etiketler ZIT. Bu uc cift icin ikili gercek-etiket KENDI ICINDE CELISKILIDIR.

SONUCU: tutarli davranan bir model bu ciftlerin BIRINDE ZORUNLU olarak yanilir.
Yani raporlanabilir MCC'nin ust siniri 1,0 DEGILDIR. Bu, model kusuru degil
VERI kusurudur ve oyle raporlanmalidir.

TASARIM: klipler SILINMEZ ve varsayilan davranis DEGISMEZ (K2/K4) — arsivlenmis
olcumlerle karsilastirilabilirlik korunur. Bu modul yalnizca GORUNUR kilar.
Rapor: docs/veri_seti_nihai_denetim_2026-08-17.md
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# (kisa_klip, uzun_klip) — kisa olan uzunun ICINDE, etiketler ZIT.
# Yol biciminde: data/eval_defense/<Etiket>/<Sinif>/<ad>.mp4
TAM_KAPSAMA: List[Tuple[str, str]] = [
    ("data/eval_defense/Normal/Safe_Walkway/4_te16.mp4",
     "data/eval_defense/Anomali/Safe_Walkway_Violation/0_tr13.mp4"),
    ("data/eval_defense/Normal/Safe_Walkway/4_tr8.mp4",
     "data/eval_defense/Anomali/Opened_Panel_Cover/2_tr119.mp4"),
    ("data/eval_defense/Anomali/Opened_Panel_Cover/2_tr104.mp4",
     "data/eval_defense/Normal/Authorized_Intervention/5_te5.mp4"),
]

# Kismi ortusen capraz ciftler (>=0,5 sn piksel-ozdes). Etiket celiskisi MUTLAK degil
# ama ayni cekimin ayni saniyeleri iki farkli etiketle sette bulunuyor.
KISMI_ORTUSME: List[Tuple[str, str, float]] = [
    ("data/eval_defense/Anomali/Unauthorized_Intervention/1_tr38.mp4",
     "data/eval_defense/Normal/Safe_Walkway/4_tr35.mp4", 7.05),
    ("data/eval_defense/Anomali/Unauthorized_Intervention/1_tr42.mp4",
     "data/eval_defense/Normal/Authorized_Intervention/5_te1.mp4", 5.75),
    ("data/eval_defense/Anomali/Opened_Panel_Cover/2_tr40.mp4",
     "data/eval_defense/Normal/Authorized_Intervention/5_tr12.mp4", 4.23),
    ("data/eval_defense/Anomali/Unauthorized_Intervention/1_tr61.mp4",
     "data/eval_defense/Normal/Authorized_Intervention/5_te1.mp4", 3.46),
    ("data/eval_defense/Anomali/Unauthorized_Intervention/1_tr67.mp4",
     "data/eval_defense/Normal/Safe_Walkway/4_tr35.mp4", 2.51),
    ("data/eval_defense/Anomali/Opened_Panel_Cover/2_tr72.mp4",
     "data/eval_defense/Normal/Authorized_Intervention/5_tr5.mp4", 0.99),
    ("data/eval_defense/Anomali/Opened_Panel_Cover/2_tr63.mp4",
     "data/eval_defense/Normal/Authorized_Intervention/5_te11.mp4", 0.71),
    ("data/eval_defense/Anomali/Opened_Panel_Cover/2_tr119.mp4",
     "data/eval_defense/Normal/Safe_Walkway/4_tr7.mp4", 0.68),
    ("data/eval_defense/Anomali/Opened_Panel_Cover/2_tr104.mp4",
     "data/eval_defense/Normal/Safe_Walkway/4_tr40.mp4", 0.68),
]


def _norm(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


# Hizli sorgu icin: klip -> celiskili oldugu klip(ler)
CELISKILI: Dict[str, List[str]] = {}
for _a, _b in TAM_KAPSAMA:
    CELISKILI.setdefault(_norm(_a), []).append(_norm(_b))
    CELISKILI.setdefault(_norm(_b), []).append(_norm(_a))

ORTUSEN: Dict[str, List[str]] = {}
for _a, _b, _s in KISMI_ORTUSME:
    ORTUSEN.setdefault(_norm(_a), []).append(_norm(_b))
    ORTUSEN.setdefault(_norm(_b), []).append(_norm(_a))


def celiskili_mi(rel_path: str) -> bool:
    """Bu klip, ZIT etiketli bir klibin tam kapsamasinda mi?"""
    return _norm(rel_path) in CELISKILI


def ortusuyor_mu(rel_path: str) -> bool:
    """Bu klip, karsit etiketli bir kliple >=0,5 sn piksel-ozdes goruntu paylasiyor mu?"""
    p = _norm(rel_path)
    return p in CELISKILI or p in ORTUSEN


def ozet() -> dict:
    return {
        "tam_kapsama_cifti": len(TAM_KAPSAMA),
        "celiskili_klip": len(CELISKILI),
        "kismi_ortusme_cifti": len(KISMI_ORTUSME),
        "etkilenen_klip_toplam": len(set(CELISKILI) | set(ORTUSEN)),
        "olcum": "piksel duzeyinde zamansal hizalama, med_MAD < 0,50",
        "rapor": "docs/veri_seti_nihai_denetim_2026-08-17.md",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(ozet(), ensure_ascii=False, indent=2))
    print("\nTAM KAPSAMA (etiket CELISKILI):")
    for a, b in TAM_KAPSAMA:
        print(f"  {a}\n    ICINDE-> {b}")
