#!/usr/bin/env python
"""Bir video icin sahne-kesimi + bolum-bazli olay/ozet ciktisini yazar (M3 dogrulama)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.agent.graph import build_graph  # noqa: E402

g = build_graph()
for path in sys.argv[1:]:
    st = g.invoke({"video_path": path, "trace": []})
    res = st["result"]
    print(f"\n######## {os.path.basename(path)} ########")
    print("KESİM/BÖLÜM izi:", [t for t in st.get("trace", []) if "kopuk" in t or "ingest" in t])
    print("OLAYLAR:")
    for e in res.events:
        print(f"   [{e.time}] ({e.severity.value}/{e.category.value}) {e.event}")
    print("RİSK:", res.risk.level.value, "—", res.risk.rationale[:120])
    print("ÖZET:", res.summary)
