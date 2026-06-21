#!/usr/bin/env python
"""Hizli risk/severity kontrolu: verilen videolari analiz edip risk+severity yazar."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.agent import analyze_video  # noqa: E402

for v in sys.argv[1:]:
    r = analyze_video(v)
    print(f"{os.path.basename(v):28s} risk={r.risk.level.value:6s} olay={len(r.events)} "
          f"sev={[e.severity.value for e in r.events]}")
