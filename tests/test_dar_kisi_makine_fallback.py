"""v13f dar kişi/makine ikinci scout'unun modelsiz yapısal testleri."""
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
        if "ENDUSTRIYEL_ENERJI_OLAYI" in choices:
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
events, note = G._dar_kisi_makine_fallback(f, seg)
check(len(events) == 1 and "Makine sıkışması" in events[0].event,
      "makine yakalama üç atom desteklenince sabit olay üretiyor")
check({x[0] for x in f.calls} == {"algi", "olay"},
      "scout ve atomlar sabit vlm/llm-large rollerini kullanıyor")

f = Fake("KISI_DESTEK_KAYBI")
events, note = G._dar_kisi_makine_fallback(f, seg)
check(len(events) == 1 and "Düşme tehlikesi" in events[0].event,
      "destek kaybı iki atom desteklenince sabit olay üretiyor")

blocked = Fake("ENDUSTRIYEL_ENERJI_OLAYI")
events, note = G._dar_kisi_makine_fallback(blocked, seg)
check(not events and len(blocked.calls) == 1 and "allowlist" in note,
      "v13e FP üreten geniş enerji dalının alarm yetkisi yok")

n = Fake("OLAY_YOK")
events, note = G._dar_kisi_makine_fallback(n, seg)
check(not events and len(n.calls) == 1, "OLAY_YOK alarm üretmiyor")

print("TUM TESTLER GECTI")
