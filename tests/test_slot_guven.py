#!/usr/bin/env python
"""Kisitli cozme dagilimi (slot guveni) — cozucu dogru mu, K2 korunuyor mu?

NEDEN: `structured_outputs.choice` ile `logprobs` BIRLIKTE calisiyor
(2026-08-25 sondasi). Bu, TEK ileri gecisten izinli cevap kumesi uzerinde
tam bir olasilik dagilimi verir. Sert kural `argmax >= T` sorar; dagilim
`P(deger >= T)` sormayi mumkun kilar — olculdu ki argmax "3" (p=0,62) iken
P(>=3) = 1,00 olabiliyor.

Bu test UC seyi korur:
  1. cozucunun ON EK mantigi (secenekler cok-tokenli: "6+", "GORUNMUYOR")
  2. maskelenmis tokenlarin (-9999) DISLANMASI
  3. K2: bayrak KAPALIYKEN `sor()` cagrisina `logprobs` argumaninin
     HIC GECIRILMEMESI. (Ilk yazimda kosulsuz gecirildi ve `sor()` imzasini
     duck-type eden test sahtelerini TypeError ile kirdi; K3 fail-open onu
     yutup slotu "olculemedi"ye cevirdi -> SESSIZ BASARISIZLIK.)
"""
import os, sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import tests.taban as taban  # noqa: E402
taban.taban_uygula()

from dilajan import gozlem as G  # noqa: E402

g = k = 0
def c(ad, kosul):
    global g, k
    if kosul: g += 1; print(f"  ok   {ad}")
    else: k += 1; print(f"  KALAN {ad}")

print("=== COZUCU: maskeleme ve normalizasyon ===")
ust = {"3": -0.474, "4": -0.974, "5": -9.2, "G": -9999.0, "x": -9999.0}
d = G.secim_dagilimi(G.SLOT_CATAL_KASA.secenekler, ust)
c("maskeli tokenlar (-9999) DISLANDI", d["p"]["GORUNMUYOR"] == 0.0)
c("olasiliklar 1'e toplaniyor", abs(sum(d["p"].values()) + d["belirsiz"] + d["yetim"] - 1.0) < 1e-6)
c("argmax dogru", d["maks"] == "3")
c("p_maks makul", 0.60 < d["p_maks"] < 0.65)

print("=== ESIK USTU KUTLE — sert kuraldan FARKLI ===")
c("P(>=3) = 1,000 iken argmax guveni 0,62", G.esik_ustu_kutle(d, 3) > 0.999)
c("P(>=5) neredeyse sifir", G.esik_ustu_kutle(d, 5) < 0.001)
c("P(>=0) = 1", abs(G.esik_ustu_kutle(d, 0) - 1.0) < 1e-6)

print("=== COK-TOKENLI SECENEK: ON EK ESLEMESI ===")
# model 'Y' uretip devam eder; "YOK" secenegine yazilmali
d2 = G.secim_dagilimi(G.SLOT_YELEK.secenekler,
                      {"Y": -0.0004, "VAR": -8.0, "K": -15.0, "G": -16.0})
c("'Y' -> YOK", d2["maks"] == "YOK" and d2["p"]["YOK"] > 0.99)
c("'K' -> KISI_YOK (yetim DEGIL)", d2["yetim"] < 1e-6)
c("'G' -> GORUNMUYOR", "GORUNMUYOR" in d2["p"])

print("=== SAYISAL OLMAYAN SECENEK esik kutlesine GIRMEZ ===")
d3 = G.secim_dagilimi(G.SLOT_YELEK.secenekler, {"G": -0.01, "Y": -5.0})
c("GORUNMUYOR sayisal esikte sayilmaz", G.esik_ustu_kutle(d3, 1) == 0.0)
d4 = G.secim_dagilimi(G.SLOT_CATAL_KASA.secenekler, {"6": -0.01, "0": -9.0})
c("'6+' -> 6 sayilir, P(>=3)~1", G.esik_ustu_kutle(d4, 3) > 0.99)

print("=== BOS/BOZUK GIRDI: K3 fail-open ===")
c("ust None -> {}", G.secim_dagilimi(G.SLOT_YELEK.secenekler, None) == {})
c("hepsi maskeli -> {}", G.secim_dagilimi(G.SLOT_YELEK.secenekler, {"a": -9999.0}) == {})
c("bos dagilimda esik kutlesi 0", G.esik_ustu_kutle({}, 3) == 0.0)

print("=== K2: BAYRAK KAPALIYKEN CAGRI IMZASI DEGISMEZ ===")
gorulen = []
class Oturum:
    hazir = True
    istemci = None
    def sor(self, soru, guided_choice=None, **kw):
        gorulen.append(sorted(kw))
        return "1"
class Ist:
    def gorev(self, _g): return self

G.slotlari_doldur(Oturum(), [G.SLOT_CATAL_KASA], Ist(), guven=False)
c("KAPALI: 'logprobs' argumani HIC gecmiyor",
  gorulen and all("logprobs" not in kw for kw in gorulen))
gorulen.clear()
G.slotlari_doldur(Oturum(), [G.SLOT_CATAL_KASA], Ist(), guven=True)
c("ACIK: 'logprobs' argumani geciyor",
  gorulen and all("logprobs" in kw for kw in gorulen))

print("=== ALAN KORUNUMU: bolgeli birlestirme `guven`i DUSURMEMELI ===")
# Bu tam olarak yasandi: alt kayitlar dagilimi topluyordu ama
# slotlari_doldur_bolgeli yalnizca degerler/ham/hatalar'i birlestiriyordu.
# Kosum "calisiyor" gorunurken guven_trace BOS kaliyordu.
class Ayar2:
    slot_guven = True
    panel_roi_vlm = ""          # tek grup yeter
class Oturum2:
    hazir = True
    istemci = None
    son_logprob = {"secilen": "3", "ust": {"3": -0.4, "4": -1.0, "G": -9999.0}}
    def sor(self, soru, guided_choice=None, **kw): return "3"
class Ist2:
    def gorev(self, _g): return self
    def video_oturumu(self, video, system=""): return Oturum2()

_k = G.slotlari_doldur_bolgeli(Ist2(), [G.SLOT_CATAL_KASA],
                               lambda roi, kapsam="segment", fps=None: b"x", Ayar2())
c("bolgeli kayitta `guven` DOLU", bool(_k.guven))
c("dagilim dogru slota yazildi", "catal_kasa_sayisi" in _k.guven)
c("deger de korunuyor", _k.degerler.get("catal_kasa_sayisi") == 3)

# ayar KAPALIYKEN guven BOS kalmali (K2)
class Ayar3(Ayar2): slot_guven = False
_k2 = G.slotlari_doldur_bolgeli(Ist2(), [G.SLOT_CATAL_KASA],
                                lambda roi, kapsam="segment", fps=None: b"x", Ayar3())
c("ayar KAPALIYKEN guven BOS", _k2.guven == {})

print("=== ARSIV: guven izi eval satirina GIRIYOR ===")
_ec = open(os.path.join(KOK, "benchmark", "eval_clips.py"), encoding="utf-8").read()
c("eval satirinda guven_trace alani var", '"guven_trace":' in _ec)
_gp = open(os.path.join(KOK, "dilajan", "agent", "graph.py"), encoding="utf-8").read()
c("graph.py guven izini YAZIYOR", "gözlem güveni" in _gp)
c("arsiv filtresi ile iz metni AYNI ANAHTARI kullaniyor",
  _ec.count('"gözlem güveni" in t') == 1)

print("=== K2: config varsayilani KAPALI ===")
c("slot_guven SINIF varsayilani False", taban.sinif_varsayilani("slot_guven") is False)

print("=== `logprobs` KAPALIYKEN istek govdesine EKLENMEZ ===")
import inspect  # noqa: E402
from dilajan import llm_client as LC  # noqa: E402
kaynak = inspect.getsource(LC.VLMClient.chat)
c("kwargs['logprobs'] yalniz kosul altinda yaziliyor",
  'if logprobs:' in kaynak and 'kwargs["logprobs"] = True' in kaynak)

print("=== SLOT GUVENI KUNYEDE (arsiv karismasin) ===")
kn = open(os.path.join(KOK, "benchmark", "eval_clips.py"), encoding="utf-8").read()
c("eval kunyesinde slot_guven var", '"slot_guven": _s.slot_guven,' in kn)

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
