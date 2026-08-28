"""v12p kapalı fiziksel uzman fallback'inin modelsiz yapısal testleri."""
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
        if "SARKAN_KISI" in choices:
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
f = Fake("SARKAN_KISI")
events, note = G._fiziksel_uzman_fallback(f, seg)
check(len(events) == 1 and "ayak desteğini kaybedip" in events[0].event,
      "scout + iki atom desteklenince sabit sarkma olayı üretiliyor")
check({x[0] for x in f.calls} == {"algi", "olay"},
      "scout ve kanıt sabit vlm/llm-large rollerini birlikte kullanıyor")
check("olay üretildi" in note, "karar izi destek hükmünü taşıyor")

n = Fake("OLAY_YOK")
events, note = G._fiziksel_uzman_fallback(n, seg)
check(not events and len(n.calls) == 1,
      "OLAY_YOK atomik çağrı ve alarm üretmiyor")

check("MAKINE_SIKISMA" not in G._FIZIKSEL_UZMAN_SECENEKLERI,
      "v12h'de ayrıştırılamayan makine ailesi yeni scout'a eklenmedi")

print("TUM TESTLER GECTI")
