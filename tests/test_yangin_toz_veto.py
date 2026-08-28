"""Eski Warehouse_Visible_Fire kodunda tutarlı atomik kanıt kapısı."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import isg_kanit as K
from dilajan.agent import graph as G
from dilajan.schema import Event, EventCategory, Severity


class Sonuc:
    def __init__(self, hukum, temporal, errors=None):
        self.hukum = hukum
        self.cevaplar = {"zamansal_davranis": temporal}
        self.hatalar = errors or {}

    def iz_satiri(self):
        return f"yangın/duman[{self.cevaplar['zamansal_davranis']}]"


def check(cond, msg):
    print(("ok " if cond else "FAIL ") + msg)
    if not cond:
        raise AssertionError(msg)


fire = Event(time="00:00", event="yangın", severity=Severity.KRITIK,
             category=EventCategory.GUVENLIK).model_copy(
                 update={"isg_kod": "Warehouse_Visible_Fire"})
other = Event(time="00:01", event="başka olay", severity=Severity.YUKSEK,
              category=EventCategory.KAZA)
old = K.dogrula
try:
    K.dogrula = lambda *_a, **_k: Sonuc(K.Hukum.REFUTED, "BUHAR_TOZ_PARLAMA")
    kept, note, veto = G._yapisal_yangin_toz_vetosu(object(), [], [fire, other])
    check(kept == [other] and "silindi" in note and veto,
          "açık toz/buhar yalnız yapılandırılmış yangını veto ediyor")

    K.dogrula = lambda *_a, **_k: Sonuc(K.Hukum.REFUTED, "BELIRTI_YOK")
    kept, note, veto = G._yapisal_yangin_toz_vetosu(object(), [], [fire])
    check(kept == [] and "silindi" in note and veto,
          "BELIRTI_YOK açık çürütmesi alarmı korumuyor")

    K.dogrula = lambda *_a, **_k: Sonuc(
        K.Hukum.INSUFFICIENT, "GORUNMUYOR", {"api": "hata"})
    kept, note, veto = G._yapisal_yangin_toz_vetosu(object(), [], [fire])
    check(kept == [] and veto,
          "API hatası kanıtsız Kritik alarmı fail-closed kaldırıyor")

    K.dogrula = lambda *_a, **_k: Sonuc(
        K.Hukum.SUPPORTED, "ALEV_VEYA_YAYILAN_DUMAN")
    kept, note, veto = G._yapisal_yangin_toz_vetosu(object(), [], [fire])
    check(kept == [fire] and "desteklendi" in note and not veto,
          "yalnız SUPPORTED eski yangın alarmını koruyor")

    kept, note, veto = G._yapisal_yangin_toz_vetosu(object(), [], [other])
    check(kept == [other] and note is None and not veto,
          "yapılandırılmış yangın yoksa veto bilgisi üretilmiyor")
finally:
    K.dogrula = old

print("TUM TESTLER GECTI")
