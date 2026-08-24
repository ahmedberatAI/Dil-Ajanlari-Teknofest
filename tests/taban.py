"""TABAN AYARI — ozellik bayraklarini KAPALI sabitler.

NEDEN VAR (2026-08-24, yeniden basladiktan sonra olculdu):
Dort test, "ozellik kapaliyken davranis birebir eski" sozlesmesini dogruluyordu
ama bayragin kapali oldugunu VARSAYIYORDU — canli `settings` nesnesinden okuyarak.
Sevk yapilandirmasi `.env`e yazilir yazilmaz (yani sistem GERCEKTEN kurulur
kurulmaz) dordu birden coktu. Test, operator sistemi yapilandirdigi icin
kirilmamalidir.

Iki kural:
  1) TABAN davranisi dogrulayan test, ilgili bayragi ACIKCA kapatir (ortamdan
     miras ALMAZ).
  2) "varsayilan KAPALI" iddiasi SINIF VARSAYILANINA bakar (`model_fields`),
     ortamdan yuklenmis ornek degerine DEGIL — aksi halde iddia, kodun
     varsayilanini degil kullanicinin .env'ini test eder.
"""
from contextlib import contextmanager

from dilajan.config import Settings, settings

# D43/D44 gozlem duzlemi + dedektor bayraklari
TABAN_BAYRAKLAR = ("isg_slotlari", "panel_roi", "panel_roi_vlm", "forklift_yuk",
                   "use_detector", "ppe_detection")


def sinif_varsayilani(ad: str):
    """Alanin KODDAKI varsayilani (ortamdan bagimsiz)."""
    return Settings.model_fields[ad].default


@contextmanager
def taban_ayari(**ek):
    """Ozellik bayraklarini SINIF VARSAYILANINA cek; cikista geri koy."""
    eski = {a: getattr(settings, a) for a in TABAN_BAYRAKLAR}
    eski.update({a: getattr(settings, a) for a in ek})
    try:
        for a in TABAN_BAYRAKLAR:
            setattr(settings, a, sinif_varsayilani(a))
        for a, v in ek.items():
            setattr(settings, a, v)
        yield settings
    finally:
        for a, v in eski.items():
            setattr(settings, a, v)


def taban_uygula():
    """Baglam yoneticisi kullanamayan modul-duzeyi testler icin kalici kapatma."""
    for a in TABAN_BAYRAKLAR:
        setattr(settings, a, sinif_varsayilani(a))
