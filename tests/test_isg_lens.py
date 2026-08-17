#!/usr/bin/env python
"""D36 — ISG mercegi (config.isg_lens) birim testleri.

    python tests/test_isg_lens.py        # cikis kodu 0 = hepsi gecti

K2 GARANTISI: bayrak KAPALIYKEN uretilen describe promptu, mercek EKLENMEDEN ONCEKI
metinle BIREBIR AYNI olmalidir. Bu test onu byte duzeyinde kanitlar — "herhalde
degismemistir" demek yeterli degil.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan import prompts  # noqa: E402
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


print("=== K2: bayrak KAPALIYKEN prompt birebir ayni ===")

# Mercegin eklendigi noktayi TAKLIT et (graph.py:_perceive_segment ile ayni sira).
def _describe_promptu(isg_acik: bool) -> str:
    instr = prompts.SEGMENT_DESCRIBE_INSTRUCTION.format(start="00:00", end="00:10")
    instr += prompts.THREAT_LENS_SUFFIX          # threat_interpretation varsayilan True
    if isg_acik:
        instr += prompts.ISG_LENS_SUFFIX
    return instr


kapali = _describe_promptu(False)
acik = _describe_promptu(True)

check("varsayilan isg_lens KAPALI", settings.isg_lens is False, f"deger={settings.isg_lens}")
check("bayrak kapaliyken mercek metni prompt'ta YOK",
      prompts.ISG_LENS_SUFFIX not in kapali)
check("bayrak acikken mercek metni prompt'ta VAR",
      prompts.ISG_LENS_SUFFIX in acik)
check("acik prompt = kapali prompt + mercek (SAF EK, ustune yazmiyor)",
      acik == kapali + prompts.ISG_LENS_SUFFIX,
      f"acik uzunluk={len(acik)} beklenen={len(kapali) + len(prompts.ISG_LENS_SUFFIX)}")

print("\n=== Mercek ICERIGI: olculen dort sinifi da kapsiyor mu ===")
m = prompts.ISG_LENS_SUFFIX.lower()
for sinif, anahtarlar in (
        ("Opened_Panel_Cover", ("pano", "koruma")),
        ("Carrying_Overload_with_Forklift", ("yük", "forklift")),
        ("Safe_Walkway_Violation", ("yaya yolu",)),
        ("Unauthorized_Intervention", ("müdahale",))):
    check(f"{sinif} kapsaniyor", all(a in m for a in anahtarlar),
          f"eksik: {[a for a in anahtarlar if a not in m]}")

print("\n=== Bastirma cumlelerine ISTISNA getiriliyor mu ===")
# Temel talimat "ekipman/yuk tasima OLAY DEGILDIR" diyor. Mercek bunu CELISKIYLE degil
# ISTISNAYLA asmali; aksi halde model iki zit emir arasinda kalir ve ikisini de zayif uygular.
check("temel talimatta bastirma cumlesi HALA duruyor (mercek onu SILMIYOR)",
      "OLAY DEĞİLDİR" in prompts.SEGMENT_DESCRIBE_INSTRUCTION)
check("mercek acik ISTISNA kurali iceriyor",
      "İSTİSNA" in prompts.ISG_LENS_SUFFIX)
check("istisna 'rutin tasima hala olay degil' dengesini koruyor",
      "hâlâ OLAY DEĞİLDİR" in prompts.ISG_LENS_SUFFIX)

print("\n=== Anti-halusinasyon korumasi mercekte de var mi ===")
check("UYDURMA yasagi korunmus", "UYDURMA" in prompts.ISG_LENS_SUFFIX)
check("'SAPMA YOK' cikisi korunmus", "SAPMA YOK" in prompts.ISG_LENS_SUFFIX)

print(f"\ngecen={_gecti}  kalan={_kaldi}")
sys.exit(1 if _kaldi else 0)
