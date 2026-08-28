"""v13m kaynak-video kesintisiz kişi düşüşü kapısının modelsiz testleri."""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.agent import graph as G


class Oturum:
    def __init__(self, root):
        self.root = root
        self.istemci = root.gorev("olay")
        self.hazir = root.ready
        self.hata = None if root.ready else "hazir degil"

    def sor(self, _prompt, **kwargs):
        ad = G._KESINTISIZ_DUSME_SORULARI[len(self.root.calls)][0]
        self.root.calls.append((ad, self.istemci.role, kwargs))
        cevap = self.root.answers.get(ad)
        if cevap is None:
            self.hata = f"{ad} cevabi yok"
        return cevap


class Rol:
    def __init__(self, root, role):
        self.root, self.role = root, role


class Fake:
    def __init__(self, answers, ready=True):
        self.answers, self.ready, self.calls = answers, ready, []

    def gorev(self, role):
        return Rol(self, role)

    def video_oturumu(self, path, **_kwargs):
        self.path = path
        return Oturum(self)


def check(cond, msg):
    print(("ok " if cond else "FAIL ") + msg)
    if not cond:
        raise AssertionError(msg)


seg = SimpleNamespace(index=0, start_str="00:00", kaynak_yol="ornek.mp4")

all_a = {ad: "A" for ad, _, _ in G._KESINTISIZ_DUSME_SORULARI}
f = Fake(all_a)
events, note = G._kesintisiz_dusme_fallback(f, seg)
check(len(events) == 1 and "Düşme tehlikesi" in events[0].event,
      "dört atomun tamamı A ise sabit kişi-düşme olayı üretiliyor")
check([x[1] for x in f.calls] == ["algi", "olay", "olay", "olay"],
      "sabit vlm/llm-large rol sözleşmesi korunuyor")
check(all(tuple(x[2]["guided_choice"]) == ("A", "B", "C", "D") for x in f.calls),
      "bütün atomlar kapalı A/B/C/D seçimi kullanıyor")

blocked_answers = dict(all_a)
blocked_answers["continuous_chain"] = "B"
f = Fake(blocked_answers)
events, note = G._kesintisiz_dusme_fallback(f, seg)
check(not events and "continuous_chain=B" in note,
      "kimlik/süreklilik atomu karşıtsa olay fail-closed eleniyor")

f = Fake({"person": "A"})
events, note = G._kesintisiz_dusme_fallback(f, seg)
check(not events and "ölçülemedi" in note,
      "eksik API cevabı alarm üretmiyor")

events, note = G._kesintisiz_dusme_fallback(
    Fake(all_a), SimpleNamespace(index=0, start_str="00:00", kaynak_yol=""))
check(not events and "kaynak video yok" in note,
      "kaynak video bulunmazsa karelerden kanıt uydurulmuyor")

print("TUM TESTLER GECTI")
