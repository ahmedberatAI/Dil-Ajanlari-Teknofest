#!/usr/bin/env python
"""Bir log dosyasinda Gradio URL'lerini (ya da hatayi) bekler; bulunca ilgili satirlari basar."""
import sys
import time

F = sys.argv[1]
KEYS = ("gradio.live", "running on", "traceback", "error", "could not", "exception", "address already")
for _ in range(120):
    try:
        txt = open(F, encoding="utf-8", errors="ignore").read()
    except Exception:
        txt = ""
    low = txt.lower()
    if "gradio.live" in low or "traceback" in low or "running on local url" in low:
        for line in txt.splitlines():
            if any(k in line.lower() for k in KEYS):
                print(line.strip())
        sys.exit(0)
    time.sleep(2)
print("TIMEOUT - URL henuz gorunmedi")
sys.exit(1)
