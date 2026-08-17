#!/usr/bin/env python
"""D36 — diyalogda BEKLEYEN KRITIK hatirlatmasi (chat_agent._bekleyen_kritik_notu).

    python tests/test_kritik_hatirlatma.py

NEDEN VAR: sertlestirilmis diyalog testinde operator "Video kac saniye?" dedi,
ajan "Video 12 saniye surmektedir." deyip DURDU — baglamda cozulmemis KRITIK
bulgu (00:08 yerde hareketsiz kisi) beklerken. Sartname Otonomi maddesi
"inisiyatif alma" istiyor.

Prompt ile UC iterasyon denendi, YAKINSAMADI (gorev 5,00 -> 4,80 -> 4,60).
Garanti KODA tasindi. Bu test o garantiyi kilitler.

EN KRITIK KONTROL: IKI baglam bicimi de desteklenmeli. Yalniz biri desteklenseydi
testte calisip URETIMDE calismazdi (veya tersi).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.chat_agent import _bekleyen_kritik, _bekleyen_kritik_notu  # noqa: E402
from dilajan.config import settings  # noqa: E402

_gecti = 0
_kaldi = 0


def check(ad, kosul, ayrinti=""):
    global _gecti, _kaldi
    if kosul:
        _gecti += 1
        print(f"  ok   {ad}")
    else:
        _kaldi += 1
        print(f"  FAIL {ad}  {ayrinti}")


DUZ = ("OLAYLAR:\n"
       "- 00:06 | Yüksek | Forklift devrildi\n"
       "- 00:08 | Kritik | Yerde hareketsiz kişi\n"
       "- 00:10 | Düşük | Personel toplandı\n")

URETIM = ("OLAYLAR:\n"
          "  [00:06] Forklift devrildi (önem: Yüksek, tür: Kaza)\n"
          "  [00:08] Yerde hareketsiz kişi (önem: Kritik, tür: Sağlık)\n")

print("=== IKI BAGLAM BICIMI de destekleniyor mu (uretim + test) ===")
for ad, ctx in (("duz bicim (testlerde)", DUZ), ("uretim bicimi (build_context)", URETIM)):
    b = _bekleyen_kritik(ctx)
    check(f"{ad}: bulgu bulundu", b is not None, str(b))
    if b:
        check(f"{ad}: KRITIK secildi (Yuksek degil)", b[1] == "kritik", str(b))
        check(f"{ad}: dogru zaman damgasi", b[0] == "00:08", str(b))
        check(f"{ad}: metin cikarildi", "hareketsiz" in b[2].lower(), str(b))

print("\n=== Hatirlatma NE ZAMAN eklenir ===")
check("yanit bulguyu ANMIYORSA hatirlatma EKLENIR",
      "00:08" in _bekleyen_kritik_notu(DUZ, "Video 12 saniye sürmektedir."))
check("hatirlatma TEK SATIR (paragraf degil)",
      _bekleyen_kritik_notu(DUZ, "Video 12 saniye.").strip().count("\n") == 0)

print("\n=== Hatirlatma NE ZAMAN eklenMEZ (robotlasma onlemi) ===")
check("yanit zaman damgasini ANIYORSA eklenmez",
      _bekleyen_kritik_notu(DUZ, "00:08'deki kişi için sağlık ekibi yönlendirin.") == "")
check("yanit olayi KELIMELERLE aniyorsa eklenmez",
      _bekleyen_kritik_notu(DUZ, "Yerde hareketsiz kalan kişiye müdahale gerekiyor.") == "")
check("baglamda KRITIK/YUKSEK yoksa eklenmez",
      _bekleyen_kritik_notu("OLAYLAR:\n- 00:03 | Düşük | Personel yürüyor\n", "selam") == "")
check("baglam BOSSA eklenmez", _bekleyen_kritik_notu("", "selam") == "")
check("olay YOKSA eklenmez",
      _bekleyen_kritik_notu("OLAYLAR:\n  (kayda değer olay yok)\n", "selam") == "")

print("\n=== Bayrak KAPALIYKEN hicbir sey eklenmez (geri-al yolu) ===")
eski = settings.chat_kritik_hatirlatma
try:
    settings.chat_kritik_hatirlatma = False
    check("bayrak False -> bos string",
          _bekleyen_kritik_notu(DUZ, "Video 12 saniye sürmektedir.") == "")
finally:
    settings.chat_kritik_hatirlatma = eski
check("bayrak geri yuklendi", settings.chat_kritik_hatirlatma == eski)

print("\n=== Bozuk girdide COKMEZ (K3 fail-open) ===")
for bozuk in ("OLAYLAR:\n- bozuk satir\n", "- 99:99 | Kritik |", "[]{}|||"):
    try:
        _bekleyen_kritik_notu(bozuk, "cevap")
        check(f"bozuk girdi cokmedi: {bozuk[:22]!r}", True)
    except Exception as e:
        check(f"bozuk girdi cokmedi: {bozuk[:22]!r}", False, f"{type(e).__name__}: {e}")

print(f"\ngecen={_gecti}  kalan={_kaldi}")
sys.exit(1 if _kaldi else 0)
