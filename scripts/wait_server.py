#!/usr/bin/env python
"""vLLM sunucusu hazir olana (ya da olene) kadar bekler; tek satir sonuc basar."""
import subprocess
import sys
import time
import urllib.request

for _ in range(150):
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3)
        print("READY")
        sys.exit(0)
    except Exception:
        pass
    if subprocess.run(["pgrep", "-f", "[a]pi_server"], capture_output=True).returncode != 0:
        print("SERVER_DIED")
        sys.exit(1)
    time.sleep(5)
print("TIMEOUT")
sys.exit(1)
