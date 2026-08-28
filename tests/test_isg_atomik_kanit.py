"""Atomik, çok-rollü İSG kanıt kapısının modelsiz regresyon testi."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.isg_kanit import (ATOMIK_MAX_TOKENS, Hukum, SPEKLER, dogrula,
                              dogrula_video, sonuclandir)

g = k = 0


def c(ad, kosul):
    global g, k
    if kosul:
        g += 1
        print("  ok  ", ad)
    else:
        k += 1
        print("  FAIL", ad)


print("=== SAF KARAR FONKSIYONU ===")
for aile, spek in SPEKLER.items():
    destek = {q.ad: next(iter(q.destek)) for q in spek.sorular}
    c(f"{aile}: tum atomlar destek -> SUPPORTED",
      sonuclandir(spek, destek).hukum == Hukum.SUPPORTED)
    belirsiz = dict(destek)
    belirsiz[spek.sorular[-1].ad] = "GORUNMUYOR"
    c(f"{aile}: belirsiz atom -> INSUFFICIENT",
      sonuclandir(spek, belirsiz).hukum == Hukum.INSUFFICIENT)
    curutulebilir = next((q for q in spek.sorular if q.curutme), None)
    if curutulebilir:
        curuk = dict(destek)
        curuk[curutulebilir.ad] = next(iter(curutulebilir.curutme))
        c(f"{aile}: acik curutme -> REFUTED",
          sonuclandir(spek, curuk).hukum == Hukum.REFUTED)


class _Rol:
    def __init__(self, ad, cagrilar):
        self.ad = ad
        self.cagrilar = cagrilar

    def analyze_frames(self, frames, prompt, **kwargs):
        secenekler = tuple(kwargs.get("guided_choice") or ())
        self.cagrilar.append((self.ad, secenekler, kwargs.get("system"),
                              kwargs.get("max_tokens")))
        return secenekler[0]


class _Istemci:
    def __init__(self):
        self.cagrilar = []

    def gorev(self, ad):
        return _Rol(ad, self.cagrilar)


class _Oturum:
    hazir = True
    hata = None

    def __init__(self, istemci, cagrilar):
        self.istemci = istemci
        self.cagrilar = cagrilar

    def sor(self, _soru, **kwargs):
        secenekler = tuple(kwargs.get("guided_choice") or ())
        self.cagrilar.append((getattr(self.istemci, "ad", "kok"), secenekler,
                              kwargs.get("hatirla"), kwargs.get("max_tokens")))
        return secenekler[0]


class _VideoIstemci(_Istemci):
    ad = "kok"

    def video_oturumu(self, _video, system=None):
        self.video_system = system
        return _Oturum(self, self.cagrilar)


print("\n=== SABIT API ROL YONLENDIRMESI ===")
istemci = _Istemci()
sonuc = dogrula(istemci, [(0.0, b"x")], "yangın/duman")
c("ilk secenekler destek oldugu icin olay desteklendi", sonuc.supported)
c("varlik/olgu vlm rolune gitti", "algi" in [x[0] for x in istemci.cagrilar])
c("zaman/iliski llm-large olay rolune gitti", "olay" in [x[0] for x in istemci.cagrilar])
c("her cagri kapali secenek uzayi tasiyor", all(x[1] for x in istemci.cagrilar))
c("her cagri sabit adli-kanit sistem talimati tasiyor", all(x[2] for x in istemci.cagrilar))
c("atomik butce uzun kapali etiketi kesmeyecek kadar genis",
  ATOMIK_MAX_TOKENS >= 32 and all(x[3] == ATOMIK_MAX_TOKENS for x in istemci.cagrilar))
c("desteklenmeyen aile fail-closed",
  dogrula(istemci, [], "uydurma-aile").hukum == Hukum.INSUFFICIENT)

print("\n=== YUKSEK COZUNURLUKLU TEK VIDEO OTURUMU ===")
video_istemci = _VideoIstemci()
video_sonuc = dogrula_video(video_istemci, b"video", "yangın/duman")
c("video yolu atomik sonucu koruyor", video_sonuc.supported)
c("video yolu iki sabit role gidiyor",
  {x[0] for x in video_istemci.cagrilar} == {"algi", "olay"})
c("video soruları birbirinin cevabını hatırlamıyor",
  all(x[2] is False for x in video_istemci.cagrilar))
c("video oturumu adli-kanit sistem talimatını taşıyor",
  bool(getattr(video_istemci, "video_system", "")))
c("video atomik butcesi de uzun etiketi kesmiyor",
  all(x[3] == ATOMIK_MAX_TOKENS for x in video_istemci.cagrilar))

print(f"\ngecen={g}  kalan={k}")
sys.exit(1 if k else 0)
