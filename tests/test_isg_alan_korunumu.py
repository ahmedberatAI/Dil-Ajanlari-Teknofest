"""D44 — SEMA-DISI ALAN KORUNUMU (`_dedupe_events` birlestirmesi).

BU KUSUR UC KEZ ISLEDI: `evidence_prev` (D33), `ppe_src` (D34), `isg_kod` (D44).
Kok neden HER SEFERINDE ayni: birlestirme olayi `Event(...)` ile YENIDEN KURUYOR
ve pydantic semasinda TANIMLI OLMAYAN alanlari sessizce dusuruyor.

ISG icin OLCULEN etki (enstrumantasyon, 149 kliplik kosum):
    `_dedupe_events: 2 -> 0`  — cok segmentli kliplerde AYNI ihlali iki segment
    birden bildirdiginde ISG sinifi TAMAMEN kayboluyordu. Uctan uca
    Unauthorized_Intervention MCC +0,393 olculdu, oysa slot degerlerinin
    tavani +0,689 idi. Aradaki fark TAMAMEN bu kusurdu.

Bu test alan alan KORUNUMU dogrular — yeni bir sema-disi alan eklendiginde
buraya bir satir eklenmelidir.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dilajan.agent.graph import (_dedupe_events, _isg_anlati_golgele,
                                 _isg_tekille)
from dilajan.schema import Event, EventCategory, Severity

g = k = 0
def c(ad, kosul):
    global g, k
    if kosul: g += 1; print("  ok  ", ad)
    else: k += 1; print("  FAIL", ad)

def isg(t, metin, kod="Unauthorized_Intervention", slot="makine_basinda_yelek",
        deger="YOK", kat=EventCategory.YETKISIZ_ERISIM):
    return Event(time=t, event=metin, severity=Severity.YUKSEK,
                 category=kat).model_copy(
        update={"isg_kod": kod, "isg_slot": slot, "isg_deger": deger})

METIN = "Yetkisiz mudahale: makineye mudahale eden kiside reflektif yelek yok"

print("=== AYNI KOD, IKI SEGMENT -> TEK OLAY, KOD KORUNUR ===")
r = _dedupe_events([isg("00:00", METIN), isg("00:10", METIN)])
c("iki olay tek olaya indi", len(r) == 1)
c("isg_kod KORUNDU", getattr(r[0], "isg_kod", None) == "Unauthorized_Intervention")
c("isg_slot KORUNDU", getattr(r[0], "isg_slot", None) == "makine_basinda_yelek")
c("isg_deger KORUNDU", getattr(r[0], "isg_deger", None) == "YOK")
c("zaman PENCERESI kuruldu", r[0].time == "00:00" and r[0].end_time == "00:10")

print()
print("=== FARKLI ISG KODU BIRLESTIRILMEZ (biri sessizce yutulmasin) ===")
a = isg("00:00", METIN)
b = isg("00:02", "Pano kapagi acik birakilmis", kod="Opened_Panel_Cover",
        slot="pano_koyuluk_0_10", deger=8, kat=EventCategory.YETKISIZ_ERISIM)
r2 = _dedupe_events([a, b])
c("iki FARKLI kod ayri kalir", len(r2) == 2)
c("kodlar dogru", sorted(getattr(x, "isg_kod", None) for x in r2)
  == ["Opened_Panel_Cover", "Unauthorized_Intervention"])

print()
print("=== ISG OLAYI ANLATI OLAYIYLA BIRLESMEZ ===")
anlati = Event(time="00:01", event="Yetkisiz kisi makineye mudahale ediyor",
               severity=Severity.YUKSEK, category=EventCategory.YETKISIZ_ERISIM)
r3 = _dedupe_events([isg("00:00", METIN), anlati])
c("ayri kalirlar", len(r3) == 2)
c("ISG olayinin kodu duruyor",
  any(getattr(x, "isg_kod", None) == "Unauthorized_Intervention" for x in r3))
c("anlati olayi kod EDINMEDI",
  sum(1 for x in r3 if getattr(x, "isg_kod", None)) == 1)

print()
print("=== KKD ISARETI HALA KORUNUYOR (D34 gerilemedi) ===")
p1 = Event(time="00:00", event="Baret takilmamis", severity=Severity.YUKSEK,
           category=EventCategory.GUVENLIK).model_copy(update={"ppe_src": True})
p2 = Event(time="00:05", event="Baret takilmamis", severity=Severity.YUKSEK,
           category=EventCategory.GUVENLIK).model_copy(update={"ppe_src": True})
r4 = _dedupe_events([p1, p2])
c("iki KKD olayi birlesti", len(r4) == 1)
c("ppe_src KORUNDU", getattr(r4[0], "ppe_src", False) is True)

print()
print("=== ALARM MUHAFIZI HALA KORUNUYOR (D33 gerilemedi) ===")
e1 = Event(time="00:00", event="uzun metin uzun metin uzun", severity=Severity.YUKSEK,
           category=EventCategory.GUVENLIK).model_copy(update={"evidence_prev": "onceki"})
e2 = Event(time="00:05", event="uzun metin uzun", severity=Severity.YUKSEK,
           category=EventCategory.GUVENLIK)
r5 = _dedupe_events([e1, e2])
c("birlesti", len(r5) == 1)
c("evidence_prev KORUNDU", getattr(r5[0], "evidence_prev", None) == "onceki")

print()
print("=== K2: ISG ALANI TASIMAYAN LISTE BIREBIR AYNI ===")
duz = [Event(time="00:00", event="A olayi burada", severity=Severity.ORTA,
             category=EventCategory.ANOMALI),
       Event(time="00:09", event="Bambaska bir sey", severity=Severity.DUSUK,
             category=EventCategory.DIGER)]
r6 = _dedupe_events(list(duz))
c("ISG'siz olaylar etkilenmedi", len(r6) == 2)
c("hicbiri isg_kod EDINMEDI",
  all(getattr(x, "isg_kod", None) is None for x in r6))
c("_isg_tekille ISG'siz listeyi BIREBIR dondurur",
  [x.event for x in _isg_tekille(list(duz))] == [x.event for x in duz])

print()
print("=== _isg_tekille: BITISIK TEKRAR BIRLESIR, YENI OLAY KORUNUR ===")
r7 = _isg_tekille([isg("00:00", METIN), anlati, isg("00:20", METIN)])
c("20 saniye sonra yeniden olusan ayni kod korunur",
  sum(1 for x in r7 if getattr(x, "isg_kod", None) == "Unauthorized_Intervention") == 2)
c("anlati olayi silinmedi", len(r7) == 3)
c("EN ERKEN zaman korunur",
  next(x for x in r7 if getattr(x, "isg_kod", None)).time == "00:00")
r7b = _isg_tekille([isg("00:00", METIN), anlati, isg("00:05", METIN)])
c("bitisik iki segment tek surekli olaya iner",
  sum(1 for x in r7b if getattr(x, "isg_kod", None) == "Unauthorized_Intervention") == 1)

print()
print("=== YAPILANDIRILMIS ISG, AYNI SERBEST ANLATI KOPYASINI GOLGELER ===")
near = isg("00:00", "Forklift ile kisi arasinda ramak kala",
           kod="Forklift_Human_NearMiss", slot="depo_forklift_kisi_tehlike",
           deger="VAR", kat=EventCategory.KAZA)
near_kopya = Event(
    time="00:01",
    event="Personel ile palet kaldiricisi arasinda carpisma riski ve ani kacis hareketi",
    severity=Severity.KRITIK, category=EventCategory.KAZA)
gercek_carpisma = Event(
    time="00:02", event="Forklift rafa carpti ve raf devrildi",
    severity=Severity.KRITIK, category=EventCategory.KAZA)
r8, silinen = _isg_anlati_golgele([near, near_kopya, gercek_carpisma])
c("near-miss serbest anlati kopyasi silindi", near_kopya.event in silinen)
c("yapisal near-miss korundu", near in r8)
c("ayni anda gercek ayri carpisma olayi korunur", gercek_carpisma in r8)
r9, silinen9 = _isg_anlati_golgele([near, near_kopya], etkin=False)
c("politika kapaliyken liste BIREBIR korunur",
  r9 == [near, near_kopya] and silinen9 == [])

print()
print("=== KKD VE ASKIDA YUK YAPISAL OLAYLARI DA ANLATI KOPYASINI GOLGELER ===")
ppe = Event(time="00:10", event="Baret eksikliği", severity=Severity.YUKSEK,
            category=EventCategory.GUVENLIK).model_copy(update={"ppe_src": True})
ppe_nesir = Event(time="00:11", event="Çalışanda KKD ve baret eksikliği var",
                  severity=Severity.KRITIK, category=EventCategory.GUVENLIK)
askida = isg("00:20", "Askıda yük düşme bölgesi ihlali",
             kod="Worker_Under_Suspended_Load", slot="depo_askida_yuk_kisi_iliskisi",
             deger="VAR", kat=EventCategory.GUVENLIK)
askida_nesir = Event(time="00:21", event="İşçi asılı yük altında ve düşme bölgesinde",
                     severity=Severity.KRITIK, category=EventCategory.GUVENLIK)
r10, silinen10 = _isg_anlati_golgele([ppe, ppe_nesir, askida, askida_nesir])
c("KKD serbest anlatı kopyası silindi", ppe_nesir.event in silinen10)
c("askıda yük serbest anlatı kopyası silindi", askida_nesir.event in silinen10)
c("iki yapısal olay korundu", ppe in r10 and askida in r10)

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
