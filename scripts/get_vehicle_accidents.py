#!/usr/bin/env python
"""E2: gercek arac-kazasi/devrilme klipleri (UCF RoadAccidents, HF mirror) indirir.

Acik-lisansli gercek FORKLIFT-devrilme videosu yok (arastirma ile dogrulandi);
en yakin gercek "devrilme/carpisma" kaniti UCF RoadAccidents (gercek CCTV goruntusu).
Bu betik N RoadAccidents klibini data/e2_vehicle/RoadAccidents/ altina indirir.

BETIK <-> DISK UYUMSUZLUGU (giderildi):
  1. Varsayilan ``N=6`` idi ama diskte 9 klip var -> betik dizini yeniden uretmiyordu.
     Varsayilan N artik 9 (diskteki kadar) ve ``N_E2`` ile degistirilebilir.
  2. ``got`` sayaci YALNIZCA yeni indirmeleri sayiyordu; zaten var olan dosyalar
     ``continue`` ile atlanip sayilmiyordu -> betik her yeniden kosuluşta N klip
     DAHA indirip dizini buyutuyordu (idempotent degildi). Artik OUT dizininde
     mevcut klipler hedefe SAYILIR; hedef doluysa hicbir sey indirilmez.
  3. Dislama kumesi yalnizca ``data/eval/RoadAccidents`` idi. Diskteki 9 klibin
     6'si ``data/eval_big/RoadAccidents`` ile, 3'u ``data/eval/RoadAccidents``
     ile CAKISIYOR -> "bagimsiz E2 kaniti" degildi. Artik her iki dizin de
     varsayilan olarak dislanir (``--allow-overlap`` ile kapatilabilir).
  4. Secim boyuta gore "en kucuk N" idi (K12 yanliligi) -> artik deterministik
     rastgele; eski davranis ``--smallest``.

Kullanim:
  python scripts/get_vehicle_accidents.py --list
  N_E2=9 python scripts/get_vehicle_accidents.py
  python scripts/get_vehicle_accidents.py --list --smallest --allow-overlap  # eski secim
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request

from _sampling import add_sampling_args, get_seed, print_selection, sample_clips

REPO = "ertiaM/Anomaly_Detection_in_Surveillance_Videos"
API_BASE = f"https://huggingface.co/api/datasets/{REPO}"
DL_BASE = f"https://huggingface.co/datasets/{REPO}"
CAT = "RoadAccidents"
# eski varsayilan 6 idi; diskteki set 9 klip -> uyumsuzluk. N_E2 ile ezilebilir.
N = int(os.environ.get("N_E2", os.environ.get("N", "9")))
OUT = os.path.join("data", "e2_vehicle", CAT)
EXCLUDE = [
    os.path.join("data", "eval", CAT),
    os.path.join("data", "eval_big", CAT),
]


def existing(paths: list[str]) -> set[str]:
    """Verilen dizinlerdeki mp4 dosya adlarini topla (yoksa sessizce atla)."""
    out: set[str] = set()
    for p in paths:
        if os.path.isdir(p):
            out.update(f for f in os.listdir(p) if f.endswith(".mp4"))
    return out


def list_clips() -> list[tuple[int, str]]:
    """RoadAccidents kategorisinin tum Part dallarini tara."""
    found: list[tuple[int, str]] = []
    for part in range(1, 5):
        api = f"{API_BASE}/tree/main/Anomaly-Videos-Part-{part}/{CAT}?limit=1000"
        try:
            data = json.load(urllib.request.urlopen(api, timeout=40))
        except Exception:
            continue
        for f in data:
            if isinstance(f, dict) and f.get("path", "").endswith(".mp4"):
                found.append((f.get("size", 0) or 0, f["path"]))
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_sampling_args(ap)
    ap.add_argument(
        "--allow-overlap",
        action="store_true",
        help="eval / eval_big ile cakisan klipler de secilebilsin (eski davranis).",
    )
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    have_out = existing([OUT])                       # hedefe SAYILAN mevcut klipler
    blocked = set() if args.allow_overlap else existing(EXCLUDE)
    need = max(0, N - len(have_out - blocked))

    mode = "en-kucuk-N (ESKI/YANLI)" if args.smallest else f"rastgele (seed={args.seed or get_seed()})"
    print(f"# orneklem: {mode}  |  hedef N={N}  |  OUT'ta mevcut={len(have_out)}  |  eksik={need}", flush=True)
    if blocked:
        print(f"# ayriklik: {len(blocked)} klip adi dislandi (eval + eval_big)", flush=True)
        overlap = have_out & blocked
        if overlap:
            print(f"# UYARI: OUT'taki {len(overlap)} klip dislama kumesiyle CAKISIYOR: "
                  f"{', '.join(sorted(overlap))}", flush=True)

    pool = [c for c in list_clips() if os.path.basename(c[1]) not in blocked
            and os.path.basename(c[1]) not in have_out]
    picked = sample_clips(pool, need, CAT, smallest=args.smallest, seed=args.seed)
    if args.list_only:
        print_selection(CAT, picked, len(pool))
        print("LISTE MODU: hicbir dosya indirilmedi.", flush=True)
        return

    got = 0
    for size, path in picked:
        name = os.path.basename(path)
        out = os.path.join(OUT, name)
        try:
            urllib.request.urlretrieve(f"{DL_BASE}/resolve/main/{path}", out)
            print(f"indirildi: {name} ({size/1e6:.1f} MB)", flush=True)
            got += 1
        except Exception as e:
            print(f"hata {name}: {e}", flush=True)
    print(f"DONE: {got} yeni klip -> {OUT} (toplam {len(existing([OUT]))})")


if __name__ == "__main__":
    main()
