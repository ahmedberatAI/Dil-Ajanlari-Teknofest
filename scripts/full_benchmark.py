#!/usr/bin/env python
"""SARTNAME KAPSAMLI PERFORMANS TESTI — tum zorunlu yetenekleri tek kosuda olcer.

Sartname (2026 TYDA 3. Senaryo) yetenekleri -> olcum eslemesi:

  §3 Olay tespiti + zaman damgasi ......... eval_clips (eval_holdout, eval_scenario)
  §4 Anlamsal yorumlama (tur/onem) ........ eval_clips cat_match + judge_category
  §4 Turkce ozet kalitesi ................. judge_independent (DAYANAKLI mod, K11)
  §4 Aksiyon onerisi + karar destek ....... holistic.py (M1 aksiyon, M4 risk gerekcesi)
  §4 Yapilandirilmis JSON ................. holistic.py (M3 sema uyumu)
  §5 Mock fonksiyon dispatch .............. holistic.py (M2 agentic dispatch)
  §7 Otonomi & diyalog .................... gen_dialogue + judge_independent
  §4 Performans (gecikme/VRAM/throughput).. bench_performance.py
  §7 Kararli calisma / hata toleransi ..... data/robust (bozuk/bos/siyah video)

Her adim BAGIMSIZDIR: biri hata verirse digerleri devam eder (sonuc 'HATA' isaretlenir).
Cikti: benchmark/results/full_<zaman>/ altinda her adimin ham ciktisi + ozet.json

Kullanim:
    python scripts/full_benchmark.py              # tam suit
    python scripts/full_benchmark.py --hizli      # uzun adimlari atla
    python scripts/full_benchmark.py --list       # yalnizca plani goster
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


class Adim:
    def __init__(self, kimlik: str, ad: str, sartname: str, cmd: list[str],
                 env: dict | None = None, uzun: bool = False, gpu: bool = True):
        self.kimlik, self.ad, self.sartname = kimlik, ad, sartname
        self.cmd, self.env, self.uzun, self.gpu = cmd, env or {}, uzun, gpu


ADIMLAR = [
    Adim("holdout", "Olay tespiti — TEMIZ HOLDOUT (UCF, 32 klip)",
         "§3 olay/kisi/riskli durum tespiti + zaman damgasi",
         [PY, "benchmark/eval_clips.py"],
         {"DILAJAN_EVAL_DIR": "data/eval_holdout"}, uzun=True),
    Adim("senaryo", "Olay tespiti — SENARYO (yangin/dusme/normal, 37 klip)",
         "§3 tespit · §4 anlamsal yorumlama · kategori adlandirma",
         [PY, "benchmark/eval_clips.py"],
         {"DILAJAN_EVAL_DIR": "data/eval_scenario"}, uzun=True),
    Adim("robust", "Hata toleransi — bozuk/bos/siyah video",
         "§7 kararli calisma · §4 hata isleme",
         [PY, "benchmark/eval_clips.py"],
         {"DILAJAN_EVAL_DIR": "data/robust"}),
    Adim("holistik", "Holistik sartname karnesi",
         "§4 aksiyon kalitesi · risk gerekcesi · JSON sema · §5 mock dispatch",
         [PY, "benchmark/holistic.py"], uzun=True),
    Adim("diyalog", "Diyalog yanitlari (otonomi)",
         "§7 niyet anlama · inisiyatif · dogru soru sorma · baglam-degisimi direnci",
         [PY, "benchmark/gen_dialogue.py"]),
    Adim("performans", "Performans: gecikme · VRAM · throughput",
         "§4 dusuk gecikme · kaynak optimizasyonu · yuksek hacim",
         [PY, "scripts/bench_performance.py"], uzun=True),
    Adim("hakem", "BAGIMSIZ hakem (Gemma) — ozet/aksiyon/diyalog kalitesi",
         "§4 Turkce ozet kalitesi · §7 diyalog kalitesi (DAYANAKLI mod, K11)",
         [PY, "benchmark/judge_independent.py"], gpu=True),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hizli", action="store_true", help="uzun adimlari atla")
    ap.add_argument("--list", action="store_true", help="yalnizca plani goster")
    ap.add_argument("--only", default="", help="virgulle ayrilmis adim kimlikleri")
    args = ap.parse_args()

    secili = [a for a in ADIMLAR
              if (not args.only or a.kimlik in args.only.split(","))
              and (not args.hizli or not a.uzun)]

    print("=" * 78)
    print("  SARTNAME KAPSAMLI PERFORMANS TESTI")
    print("=" * 78)
    for a in secili:
        print(f"  [{a.kimlik:11s}] {a.ad}")
        print(f"  {'':13s} -> {a.sartname}")
    if args.list:
        print("\nLISTE MODU — hicbir olcum yapilmadi.")
        return

    zaman = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    cikti = os.path.join(KOK, "benchmark", "results", f"full_{zaman}")
    os.makedirs(cikti, exist_ok=True)
    print(f"\n  cikti -> {os.path.relpath(cikti, KOK)}\n")

    ozet = {"zaman": zaman, "adimlar": []}
    for i, a in enumerate(secili, 1):
        print("-" * 78)
        print(f"  [{i}/{len(secili)}] {a.ad}")
        print("-" * 78, flush=True)
        env = dict(os.environ)
        env.update(a.env)
        env["PYTHONUNBUFFERED"] = "1"
        log = os.path.join(cikti, f"{a.kimlik}.log")
        t0 = time.time()
        try:
            with open(log, "w", encoding="utf-8") as f:
                p = subprocess.run(a.cmd, cwd=KOK, env=env, stdout=f,
                                   stderr=subprocess.STDOUT, timeout=7200)
            rc = p.returncode
        except Exception as e:
            rc = -1
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"\n[KOSUCU HATASI] {e}\n")
        sure = time.time() - t0
        durum = "OK" if rc == 0 else "HATA"
        print(f"  -> {durum}  ({sure:.0f} sn)  log: {os.path.basename(log)}", flush=True)
        # son satirlari ekrana bas (ozet gorunsun)
        try:
            with open(log, encoding="utf-8") as f:
                son = f.read().strip().splitlines()[-12:]
            for s in son:
                print("     " + s[:110])
        except Exception:
            pass
        ozet["adimlar"].append({
            "kimlik": a.kimlik, "ad": a.ad, "sartname": a.sartname,
            "durum": durum, "cikis_kodu": rc, "sure_sn": round(sure, 1),
            "log": os.path.basename(log),
        })
        print(flush=True)

    with open(os.path.join(cikti, "ozet.json"), "w", encoding="utf-8") as f:
        json.dump(ozet, f, ensure_ascii=False, indent=2)

    ok = sum(1 for a in ozet["adimlar"] if a["durum"] == "OK")
    print("=" * 78)
    print(f"  BITTI: {ok}/{len(ozet['adimlar'])} adim OK  ·  "
          f"toplam {sum(a['sure_sn'] for a in ozet['adimlar']) / 60:.0f} dk")
    print(f"  Sonuclar -> {os.path.relpath(cikti, KOK)}")
    print("=" * 78)


if __name__ == "__main__":
    main()
