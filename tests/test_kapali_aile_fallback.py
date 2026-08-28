"""v12i olay-sız kapalı aile fallback'inin modelsiz yapısal testleri."""
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
        if "OLAY_YOK" in choices:
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

f = Fake("YUK_COKME")
events, note = G._kapali_aile_fallback(f, seg)
check(len(events) == 1 and "Kontrolsüz yük" in events[0].event,
      "yük/çökme yalnız atomik destekten sonra sabit olay üretiyor")
check({x[0] for x in f.calls} == {"algi", "olay"},
      "tarama+kanıt sabit algı ve olay rollerini birlikte kullanıyor")
check("olay üretildi" in note, "karar izi destek hükmünü taşıyor")

n = Fake("OLAY_YOK")
events, note = G._kapali_aile_fallback(n, seg)
check(not events and len(n.calls) == 1, "OLAY_YOK atomik çağrı ve alarm üretmiyor")

old_rules = G.settings.facility_rules
old_policy = G.settings.facility_policy
old_ppe = G.settings.ppe_detection
try:
    G.settings.facility_rules = ""
    G.settings.facility_policy = ""
    G.settings.ppe_detection = False
    k = Fake("KKD_EKSIK")
    events, note = G._kapali_aile_fallback(k, seg)
    check(not events and len(k.calls) == 1 and "KKD_BEYANI_YOK" in note,
          "beyansız KKD scout seçimi atomik çağrı ve alarm üretmiyor")
finally:
    G.settings.facility_rules = old_rules
    G.settings.facility_policy = old_policy
    G.settings.ppe_detection = old_ppe

check("MAKINE_SIKISMA" not in G._KAPALI_AILE_SECENEKLERI,
      "kanıtlanmamış makine ailesi yalnız fallback allowlist'inin dışında")

print("TUM TESTLER GECTI")
