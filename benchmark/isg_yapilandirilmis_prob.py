#!/usr/bin/env python
"""D37 PROB — YAPILANDIRILMIS ISG SINIFLANDIRMASI (mentor onerisi, guclendirilmis).

    python benchmark/isg_yapilandirilmis_prob.py [--n 40]

MENTOR ONERISI (aynen): VLM yonlendirmesi icin coktan secmeli / JSON-alanina uygun
prompt; sistem ve user prompt ayrimi; her etiket icin ACIK TANIM + KAPALI SECENEK
LISTESI.

=== NEDEN BU PROJEDE MANTIKLI (elenme kaydiyla birlikte) ===
En yakin onceki deneme §3.4'te ELENDI ("kategori tanimlari" -> NET REGRESYON).
AMA elenme gerekcesinin IKI dayanagi da BU KAPSAMDA GECERSIZ:
    "zaten %96 recall'dayiz"   -> eval_defense'te recall %28
    "320x240 grainy goruntu"   -> eval_defense 1920x1080 CCTV
Ayrica HANDOFF §11 su tavsiyeyi BEKLETIYOR:
    "guided_choice ... kategori taksonomisi icin de kullanilabilir
     (asil onerilen kullanim HALA YAPILMADI)"

=== NEDEN OLCUM ACISINDAN DEGERLI (asil gerekce) ===
Bugun bulunan DORT olcum kusurunun DORDU DE sozcuksel eslestirmeden kaynaklaniyordu:
  1) "olu" alt-dizgisi         -> yolu/olusumu icinde esleSiyordu
  2) olumsuzlama kapisi deligi -> "gozlemlenmedi" kacurluyordu (26 eslesmenin 21'i SAHTE)
  3) morfoloji delikleri       -> "forkliftin" eslesmiyor ama "Forklift'in" eslesiyor
  4) recall tanimi             -> olayin DOGRU olmasi gerekmiyordu
KAPALI ETIKET SETI bunlarin HEPSINI gecersiz kilar: etiket ya class2'dir ya degildir.
Sozcuk yok -> eslestirici yok -> kapi yok -> morfoloji yok.

=== BUGUN OGRENILEN TUZAK, BU TASARIMDA ONLENIYOR ===
Bugun yazdigim ISG mercegi METRIK OYUNU cikti: skorlayicinin aradigi KELIMELERI
modele ogretiyordu. Burada o risk YOK, cunku model KELIME degil ETIKET uretiyor ve
etiket dogrudan gercek-etiketle karsilastiriliyor; odullendirilecek bir sozcuk yok.

=== D33'TEN GELEN UYARI (secenek listesine kacis SART) ===
Zorunlu secim ALGIYI DUZELTMEZ: pano sorusunda model 20/20 klipte "KAPALI" dedi,
10'u gercekte ACIKTI. Bu yuzden listede "guvenli_durum" ve "belirsiz" kacislari VAR;
olmasaydi model yok yere pozitif uretirdi.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.labels import ISG_SINIFLAR, isg_sinif_from_path  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- KAPALI SECENEK LISTESI (mentor onerisi) + IKI KACIS (D33 uyarisi) ---
GUVENSIZ = [k for k, v in ISG_SINIFLAR.items() if v.get("guvensiz")]
SECENEKLER = GUVENSIZ + ["guvenli_durum", "belirsiz"]

# --- SISTEM PROMPTU: rol + degismeyen kisitlar (cagridan cagriya SABIT) ---
SISTEM = (
    "Sen bir üretim tesisinin İŞ SAĞLIĞI VE GÜVENLİĞİ (İSG) kamera analiz uzmanısın. "
    "Sana bir güvenlik kamerasından alınmış kareler verilir ve TEK BİR sınıf etiketi "
    "seçersin. Yalnızca gerçekten GÖRDÜĞÜNE dayan; göremediğin bir durumu VARSAYMA. "
    "Emin değilsen tahmin yürütmek yerine 'belirsiz' seç — yanlış etiket, boş etiketten "
    "daha zararlıdır."
)


def _gorev_promptu() -> str:
    """KULLANICI promptu: gorev + ETIKET TANIMLARI + kapali secenek listesi.

    Tanimlar `benchmark/labels.py`'deki ISG_SINIFLAR[...]['tanim'] alanindan uretilir —
    TEK KAYNAK. Prompt ile skorlayici AYNI tanima bakar, birbirinden KAYAMAZ.
    """
    satirlar = ["Bu karelerde hangi İSG durumu var? TANIMLAR (kararını bunlara göre ver):", ""]
    for k in GUVENSIZ:
        v = ISG_SINIFLAR[k]
        satirlar.append(f'- "{k}": {v.get("tanim", "")}')
    satirlar += [
        '- "guvenli_durum": Yukarıdaki ihlallerin HİÇBİRİ yok; personel ve ekipman '
        'kurallara uygun çalışıyor.',
        '- "belirsiz": Görüntü yetersiz veya durum ayırt edilemiyor.',
        "",
        "Seçenekler: [" + ", ".join(SECENEKLER) + "]",
        "",
        "YALNIZCA seçeneklerden birini yaz. Açıklama, noktalama veya başka metin YAZMA.",
    ]
    return "\n".join(satirlar)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=40, help="sinif basina klip")
    p.add_argument("--kare", type=int, default=8)
    p.add_argument("--ikili", action="store_true",
                   help="ITER-2: 6 yonlu yerine IKILI sor (ihlal var/yok)")
    a = p.parse_args()

    istemci = VLMClient()
    if a.ikili:
        # ITER-2 GEREKCESI: 6 yonlu kosumda model 197 klibin 144'unde (%73)
        # "guvenli_durum" dedi -> ince ayrimi yapamiyor, kacis kapisina siginiyor.
        # Ayrica class2 (Opened_Panel_Cover) ile class5 (Authorized_Intervention)
        # AYNI GORUNTU oldugu olculdu -> 8 sinifin 2'si zaten AYRILAMAZ.
        # Bu yuzden asil ihtiyaca indirgeniyor: IHLAL VAR MI?
        secenekler = ["ihlal_var", "ihlal_yok"]
        gorev = "\n".join(
            ["Bu güvenlik kamerası karelerinde bir İŞ GÜVENLİĞİ İHLALİ var mı?", "",
             "İHLAL SAYILAN DURUMLAR (tanımlar):"]
            + [f'- {ISG_SINIFLAR[k].get("tr_ad", k)}: {ISG_SINIFLAR[k].get("tanim","")}'
               for k in GUVENSIZ]
            + ["",
               "Bunların HİÇBİRİ yoksa veya ayırt edemiyorsan: ihlal_yok",
               "",
               "Seçenekler: [ihlal_var, ihlal_yok]",
               "YALNIZCA seçeneklerden birini yaz."])
    else:
        secenekler = SECENEKLER
        gorev = _gorev_promptu()
    print(f"secenekler ({len(secenekler)}): {secenekler}\n")

    klipler = []
    kok = os.path.join(ROOT, "data", "eval_defense")
    for etiket in ("Anomali", "Normal"):
        for kok2, _dz, fs in os.walk(os.path.join(kok, etiket)):
            for f in sorted(fs):
                if f.endswith((".mp4", ".avi")):
                    yol = os.path.join(kok2, f)
                    gercek = isg_sinif_from_path(os.path.relpath(yol, ROOT).replace("\\", "/"))
                    if gercek:
                        klipler.append((yol, gercek))
    # sinif basina en fazla n
    sayac: collections.Counter = collections.Counter()
    secili = []
    for yol, g in klipler:
        if sayac[g] < a.n:
            secili.append((yol, g))
            sayac[g] += 1
    print(f"{len(secili)} klip · sinif dagilimi: {dict(sayac)}\n")

    satirlar = []
    t0 = time.time()
    for i, (yol, gercek) in enumerate(secili, 1):
        try:
            tumu, _bilgi = extract_timestamped_frames(yol)
            # Esit araliklarla en fazla `--kare` kare (bastan almak klibin sonunu kaybettirir)
            if len(tumu) > a.kare:
                adim = len(tumu) / a.kare
                kareler = [tumu[int(i * adim)] for i in range(a.kare)]
            else:
                kareler = tumu
            tahmin = istemci.analyze_frames(
                kareler, gorev, system=SISTEM, temperature=0.0,
                max_tokens=24, guided_choice=secenekler).strip()
        except Exception as e:
            print(f"  [HATA] {os.path.basename(yol)}: {type(e).__name__}: {e}")
            continue
        guvensiz_gercek = ISG_SINIFLAR.get(gercek, {}).get("guvensiz", False)
        guvensiz_tahmin = (tahmin == "ihlal_var") if a.ikili else (tahmin in GUVENSIZ)
        satirlar.append({"yol": os.path.relpath(yol, ROOT).replace("\\", "/"),
                         "gercek": gercek, "tahmin": tahmin,
                         "sinif_dogru": tahmin == gercek,
                         "ikili_dogru": guvensiz_gercek == guvensiz_tahmin})
        if i % 20 == 0:
            print(f"  {i}/{len(secili)} ...", flush=True)

    n = len(satirlar)
    if not n:
        print("hic sonuc yok")
        return 1
    sinif = sum(s["sinif_dogru"] for s in satirlar)
    ikili = sum(s["ikili_dogru"] for s in satirlar)
    print()
    print("=" * 78)
    print(f"n={n}  ·  sure {(time.time()-t0)/60:.1f} dk  ·  klip basina "
          f"{(time.time()-t0)/n:.1f} sn")
    print("=" * 78)
    print(f"  SINIF DOGRULUGU (tam etiket) : {sinif}/{n} = %{100*sinif/n:.1f}"
          f"   (sans ~%{100/len(SECENEKLER):.1f})")
    print(f"  IKILI DOGRULUK (guvensiz/mi) : {ikili}/{n} = %{100*ikili/n:.1f}   (sans %50)")
    print()
    print("  KARISIKLIK (gercek -> tahmin):")
    kar: collections.Counter = collections.Counter()
    for s in satirlar:
        kar[(s["gercek"], s["tahmin"])] += 1
    for (g, t), v in kar.most_common(14):
        isaret = "OK " if g == t else "   "
        print(f"    {isaret}{g[:30]:32s} -> {t[:30]:32s} {v:>3d}")

    yol = os.path.join(ROOT, "benchmark", "results", ("isg_yapilandirilmis_ikili.json" if a.ikili else "isg_yapilandirilmis_prob.json"))
    json.dump({"secenekler": secenekler, "sistem": SISTEM, "gorev": gorev,
               "n": n, "sinif_dogru": sinif, "ikili_dogru": ikili,
               "satirlar": satirlar},
              open(yol, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nKaydedildi: {os.path.relpath(yol, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
