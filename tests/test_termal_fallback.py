"""v12n olay-sız termal fallback'inin modelsiz yapısal testleri."""
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
        return choices[0]


class Fake:
    def __init__(self):
        self.calls = []

    def gorev(self, ad):
        return Rol(self, ad)


def check(cond, msg):
    print(("ok " if cond else "FAIL ") + msg)
    if not cond:
        raise AssertionError(msg)


seg = SimpleNamespace(index=0, start_str="00:00", frames=[("00:00", b"x")])
f = Fake()
events, note, terminal = G._termal_fallback(f, seg)
check(len(events) == 1 and "Termal aşırı ısınma" in events[0].event,
      "iki atom desteklenince sabit termal olay üretiliyor")
check(not terminal, "çelişki yoksa normal termal kabul terminal değil")
check({x[0] for x in f.calls} == {"algi", "olay"},
      "kanıt sabit vlm ve llm-large rollerini birlikte kullanıyor")
check("olay üretildi" in note, "karar izi destek hükmünü taşıyor")


class RefutingRol(Rol):
    def analyze_frames(self, _frames, _prompt, **kw):
        choices = tuple(kw.get("guided_choice") or ())
        self.root.calls.append((self.ad, choices))
        return choices[1]


class RefutingFake(Fake):
    def gorev(self, ad):
        return RefutingRol(self, ad)


r = RefutingFake()
events, note, terminal = G._termal_fallback(r, seg, fire_dust_veto=True)
check(not events and "REFUTED" in note and not terminal,
      "açık boya/lamba/yansıma alternatifi fail-closed kalıyor")

f = Fake()
events, note, terminal = G._termal_fallback(f, seg, fire_dust_veto=True)
check(not events and terminal and "TERMINAL_ABSTAIN" in note,
      "toz/buhar vetosu ile destekli termal yorum çatışırsa olay yok ve terminal")

print("TUM TESTLER GECTI")
