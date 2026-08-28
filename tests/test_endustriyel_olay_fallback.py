"""v13c saflaştırılmış endüstriyel fallback'in modelsiz yapısal testleri."""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.agent import graph as G


class Rol:
    def __init__(self, root, ad):
        self.root, self.ad = root, ad

    def analyze_frames(self, _frames, _prompt, **kw):
        choices = tuple(kw.get("guided_choice") or ())
        self.root.calls.append((self.ad, choices))
        if "MAKINE_YAKALAMA" in choices:
            return self.root.scan
        return choices[0]


class Fake:
    def __init__(self, scan):
        self.scan, self.calls = scan, []

    def gorev(self, ad):
        return Rol(self, ad)


def check(cond, msg):
    print(("ok " if cond else "FAIL ") + msg)
    if not cond:
        raise AssertionError(msg)


seg = SimpleNamespace(index=0, start_str="00:00", frames=[("00:00", b"x")])
f = Fake("MAKINE_YAKALAMA")
events, note = G._endustriyel_olay_fallback(f, seg)
check(len(events) == 1 and "Makine sıkışması" in events[0].event,
      "allowlist dalı üç atom desteklenince sabit olay üretiyor")
check({x[0] for x in f.calls} == {"algi", "olay"},
      "scout ve atomlar sabit vlm/llm-large rollerini kullanıyor")

blocked = Fake("DUSEN_AGIR_YUK")
events, note = G._endustriyel_olay_fallback(blocked, seg)
check(not events and len(blocked.calls) == 1 and "allowlist" in note,
      "v13c'de ayrıştırılmayan scout dalı atomik çağrı/alarm üretmiyor")

n = Fake("OLAY_YOK")
events, note = G._endustriyel_olay_fallback(n, seg)
check(not events and len(n.calls) == 1, "OLAY_YOK alarm üretmiyor")

print("TUM TESTLER GECTI")
