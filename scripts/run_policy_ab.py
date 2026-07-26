#!/usr/bin/env python
"""Kusur #2 (risk yukseltme) A/B olcum kosucusu — B1 kolu.

A kolu  = ARSIVLENMIS benchmark/results/eval_20260726_171601.json
          (facility_rules ACIK, facility_policy YOK) -> YENIDEN KOSULMAZ.
B1 kolu = AYNI facility_rules + YENI facility_policy (policy_gate devrede, sevk KAPALI).

TEK DEGISKEN: DILAJAN_FACILITY_POLICY. Boylece olculen fark yalnizca politika
hakemligi katmanindan gelir.

Kullanim:  python scripts/run_policy_ab.py            # B1 kolu
           POLICY_DISPATCH=1 python scripts/run_policy_ab.py   # B2 kolu (sevk acik)
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A kosusunda kullanilan facility_rules metni — BIREBIR AYNI olmali (A/B safligi).
FACILITY_RULES = (
    "Bu uretim tesisinin ZORUNLU guvenlik kurallari: "
    "(1) Personel YALNIZCA zeminde isaretli guvenli yurume yolunda yurumelidir; yurume yolunun "
    "disina cikmak, makine/forklift sahasindan gecmek IHLALDIR. "
    "(2) Makinelere, elektrik panolarina ve ekipmana yalnizca YETKILI teknisyen mudahale edebilir; "
    "yetkisiz kisinin makineye/panoya mudahalesi IHLALDIR. "
    "(3) Elektrik pano/kontrol kapaklari her zaman KAPALI olmalidir; ACIK pano kapagi IHLALDIR. "
    "(4) Forklift ile gorusu engelleyecek veya guvenli kapasiteyi asacak sekilde ASIRI/istiflenmis "
    "yuk tasimak IHLALDIR. Bu kurallara aykiri her durumu ihlal/olay olarak raporla; bu ihlaller "
    "is kazasi riski tasidigi icin en az YUKSEK onem derecesi verilmelidir."
)

# YENI: operatorun BEYAN ETTIGI politika (satir basina bir kural).
# Bicim: <ihlal tanimi> | <uygun gorunum> | <onem> [| sevk]
FACILITY_POLICY = "\n".join([
    "Personel yalnızca işaretli yürüyüş yolunda hareket eder | yürüyüş yolu içinde kalmak | Yüksek",
    "Yetkisiz personel makine ve kontrol panellerine müdahale etmez |  | Yüksek",
    "Elektrik ve kontrol panolarının kapakları kapalı tutulur | pano kapağı kapalı | Yüksek",
    "Yük taşıma araçları beyan edilen yük sınırını aşamaz | yük sınırı içinde taşıma | Yüksek",
])


def main() -> None:
    env = dict(os.environ)
    env.update({
        "DILAJAN_EVAL_DIR": "data/eval_defense",
        "DILAJAN_FACILITY_RULES": FACILITY_RULES,
        "DILAJAN_FACILITY_POLICY": FACILITY_POLICY,
        "PYTHONUNBUFFERED": "1",
    })
    if os.environ.get("POLICY_DISPATCH", "").strip() in ("1", "true", "yes"):
        env["DILAJAN_POLICY_DISPATCH"] = "1"
        print("# B2 KOLU: policy_dispatch ACIK (sevk kapisi politika yukseltmesini sayar)")
    else:
        print("# B1 KOLU: policy_dispatch KAPALI (severity yukselir, sevk kapisi DOKUNULMAZ)")
    print(f"# {len(FACILITY_POLICY.splitlines())} kural politikasi enjekte edildi")
    sys.exit(subprocess.run(
        [sys.executable, os.path.join("benchmark", "eval_clips.py")],
        cwd=ROOT, env=env,
    ).returncode)


if __name__ == "__main__":
    main()
