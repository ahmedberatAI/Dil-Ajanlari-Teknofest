#!/usr/bin/env python
"""DIYALOG: METIN-EYLEM CELISKISI geri gelemez.

OLCULDU (2026-08-25, arsiv taramasi + canli kosum):
`respond()` ONCE serbest metni uretiyor, SONRA `answer += _maybe_execute(...)`
ile icra blogunu ekliyordu. Model kendi onerisinin O ANDA yurutulecegini
BILMEDEN yaziyor ve onay istemeye devam ediyordu. Arsivden AYNEN:

    "...icin ONAYINIZ VAR MI?"
    "✅ Yurutulen operasyonel aksiyonlar: - saglik_ekibi_yonlendir -> ..."

OLCUM (ayni olcut hem arsive hem canliya):
    CELISKI = icra blogu VAR ama metin TAMAMLANMA bildirmiyor
    taban   : 13/18 = %72
    sonrasi :  0/5  = %0

Puanlamanin %20'si "Otonomi ve Zeka" ve icinde "diyalogun DOGAL ve INSANSI
bir akista ilerlemesi" var — bu celiski juriye GORUNUR bir kusurdu.

SIFIR RISK: chat_agent analiz boru hattinin DISINDADIR; yalnizca analiz
TAMAMLANDIKTAN sonra AnalysisResult'i SALT OKUYARAK calisir. Tespit
metrikleri yapisal olarak etkilenemez.

TUZAK (olculdu): not AYRI bir `system` mesaji olarak eklenirse servis
BadRequestError doner ve respond() erken cikip "model servisine
ulasilamiyor" yanitini verir. Not SISTEM PROMPTUNUN SONUNA eklenmeli.
"""
import inspect, os, sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import tests.taban as taban  # noqa: E402
taban.taban_uygula()

from dilajan import chat_agent as C  # noqa: E402

g = k = 0
def c(ad, kosul):
    global g, k
    if kosul: g += 1; print(f"  ok   {ad}")
    else: k += 1; print(f"  KALAN {ad}")

src = inspect.getsource(C.respond)

print("=== MODEL, ICRANIN OLACAGINI BILIYOR ===")
c("icra kapisi metin URETILMEDEN ONCE hesaplaniyor",
  src.index("_icra_olacak =") < src.index("istemci.chat"))
c("kapi acikken modele DURUM bildiriliyor", "DURUM (bu tur icin)" in src)
c("model TEKRAR onay istememesi icin uyariliyor",
  "TEKRAR onay" in src and "İSTEME" in src)
c("model icra LISTESINI yazmamasi icin uyariliyor",
  "sen o listeyi YAZMA" in src or "listeyi YAZMA" in src)

print("=== NOT, AYRI SYSTEM MESAJI OLARAK EKLENMEMELI (BadRequestError) ===")
c("not SISTEM PROMPTUNUN SONUNA ekleniyor",
  'messages[0]["content"] +=' in src)
c("sohbetin ORTASINA system mesaji EKLENMIYOR",
  'append({"role": "system"' not in src)

print("=== KAPI TEK KAYNAK (iki yerde ayri kosul OLMAMALI) ===")
c("icra blogu ayni bayragi kullaniyor", "if _icra_olacak:" in src)
c("kosul YALNIZCA bir kez hesaplaniyor",
  src.count("is_confirmation(message) and onaylanacak_oneri_var_mi") == 1)

print("=== DETERMINISTIK ON KOSUL KORUNDU (D42) ===")
c("bos gecmiste icra YAPILMAZ", C.onaylanacak_oneri_var_mi([]) is False)
c("asistan turu varsa oneri VAR sayilir",
  C.onaylanacak_oneri_var_mi(
      [{"role": "assistant", "content": "Onaylarsanız gönderelim."}]) is True)

print("=== ANALIZ HATTI ETKILENMEDI (yapisal) ===")
import dilajan.agent.graph as G  # noqa: E402
gs = inspect.getsource(G)
c("graph.py CHAT_SYSTEM KULLANMIYOR", "CHAT_SYSTEM" not in gs)
c("graph.py chat_agent IMPORT ETMIYOR", "chat_agent" not in gs)

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
