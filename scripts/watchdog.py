#!/usr/bin/env python
"""G9: vLLM sunucu WATCHDOG — saglik kontrolu + otomatik yeniden-baslatma.

Sunucu OOM/uyku/cokme ile SESSIZCE olurse (bir kez yasandi) otomatik tespit edip ayaga
kaldirir → uzun-sureli/uretim dagitiminda guvenilirlik. Sunucuyu kendisi baslatip izler.

Kullanim:
    python scripts/watchdog.py            # sunucuyu baslat + izle + dususte restart
    WATCHDOG_INTERVAL=20 WATCHDOG_GRACE=200 python scripts/watchdog.py

Olceklenme notu (tek-GPU darbogazi):
    - Eszamanli kullanici: vLLM gelen istekleri zaten BATCH'ler/kuyruklar (continuous batching).
    - Daha fazla throughput: cok-GPU'da `--tensor-parallel-size N` ile serve_vllm.py uyarlanir.
    - Bu watchdog tek-instans guvenilirligini saglar; yatay olcek icin onune bir yuk-dengeleyici konur.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dilajan.config import settings  # noqa: E402

URL = settings.base_url + "/models"
INTERVAL = float(os.environ.get("WATCHDOG_INTERVAL", "20"))   # saglik kontrolu araligi (sn)
GRACE = float(os.environ.get("WATCHDOG_GRACE", "200"))        # restart sonrasi model-yukleme bekleme (sn)
FAIL_THRESHOLD = int(os.environ.get("WATCHDOG_FAILS", "2"))   # ardisik basarisizlik -> restart


def healthy() -> bool:
    try:
        with urllib.request.urlopen(URL, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def kill_stale() -> None:
    for pat in ("[a]pi_server", "[E]ngineCore", "vllm serve"):
        try:
            subprocess.run(["pkill", "-f", pat], check=False)
        except Exception:
            pass
    time.sleep(5)


def start_server() -> subprocess.Popen:
    log = open(os.path.expanduser("~/teknofest/vllm_server.log"), "ab", buffering=0)
    return subprocess.Popen([sys.executable, os.path.join(ROOT, "serve_vllm.py")],
                            stdout=log, stderr=log, cwd=ROOT)


def main() -> None:
    print(f"[watchdog] izleniyor: {URL}  (interval={INTERVAL}s, grace={GRACE}s)")
    if not healthy():
        print("[watchdog] sunucu kapali — baslatiliyor...")
        kill_stale()
        start_server()
        time.sleep(GRACE)

    fails = 0
    while True:
        if healthy():
            if fails:
                print(f"[watchdog] {time.strftime('%H:%M:%S')} saglikli (toparlandi)")
            fails = 0
        else:
            fails += 1
            print(f"[watchdog] {time.strftime('%H:%M:%S')} YANIT YOK ({fails}/{FAIL_THRESHOLD})")
            if fails >= FAIL_THRESHOLD:
                print("[watchdog] sunucu olu — yeniden baslatiliyor (stale temizle + serve_vllm)...")
                kill_stale()
                start_server()
                time.sleep(GRACE)
                fails = 0
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
