#!/usr/bin/env python
"""Gradio arayuzunun hatasiz baslayip servis verdigini dogrular (saf Python)."""
from __future__ import annotations

import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402


def main() -> None:
    demo = app.build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7860,
                prevent_thread_lock=True, quiet=True)
    try:
        time.sleep(4)
        code = urllib.request.urlopen("http://127.0.0.1:7860", timeout=5).getcode()
        print(f"GRADIO HTTP {code}")
        print("UI_SERVE_OK" if code == 200 else "UI_SERVE_FAIL")
    finally:
        demo.close()


if __name__ == "__main__":
    main()
