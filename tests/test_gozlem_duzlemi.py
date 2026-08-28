#!/usr/bin/env python
"""D43 — GOZLEM DUZLEMI regresyon kilidi.

    python tests/test_gozlem_duzlemi.py

NEDEN (olculdu, n=20 guvensiz klip): serbest-metin boru hatti 0/20 ISG olayi
uretiyordu; AYNI model AYNI kliplerde ISLEMSEL soru soruldugunda 12-20/20.
Kayip zinciri: K1 algi 0/20 · K2 cikarim %45 · K3 sozcuksel kapi %64.
Gozlem duzlemi K2 ve K3'u YAPISAL olarak ortadan kaldirir.
"""
"""D43 gozlem duzlemi — modelsiz birim testleri."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dilajan import gozlem as G, isg_kural as K
from dilajan.config import Settings
g = k = 0
def c(ad, kosul, ek=""):
    global g, k
    if kosul: g += 1; print(f"  ok   {ad}")
    else: k += 1; print(f"  FAIL {ad}  {ek}")

print("=== K2: bayrak KAPALI iken hicbir sey istenmez ===")
s = Settings()
from tests.taban import sinif_varsayilani
c("varsayilan isg_slotlari BOS (SINIF varsayilani, .env DEGIL)",
  sinif_varsayilani("isg_slotlari") == "")
class _Kapali: isg_slotlari = ""
c("kapali iken gerekli slot YOK", K.gerekli_slotlar(_Kapali()) == [])

print("\n=== slot secimi ===")
class A: pass
a = A(); a.isg_slotlari = "*"; a.yelek_yetki_kurali = True; a.panel_koyuluk_kurali = True; a.forklift_kasa_kurali = True
c("'*' tum kural slotlarini ister", 
  set(K.gerekli_slotlar(a)) >= {k.slot for k in K.KURALLAR})
c("'*' ON KOSUL slotlarini da ister", 
  set(K.gerekli_slotlar(a)) >= {k.on_slot for k in K.KURALLAR if k.on_slot})
c("ON KOSUL slotu kendi kuralindan ONCE sorulur",
  all(K.gerekli_slotlar(a).index(k.on_slot) < K.gerekli_slotlar(a).index(k.slot)
      for k in K.KURALLAR if k.on_slot))
a.isg_slotlari = "catal_kasa_sayisi"
c("tek slot secilebilir", K.gerekli_slotlar(a) == ["catal_kasa_sayisi"])
a.isg_slotlari = "makine_basinda_yelek"
c("yelek secilince ON KOSUL slotu da istenir",
  K.gerekli_slotlar(a) == ["makine_basinda_kisi", "makine_basinda_yelek"])
a.isg_slotlari = "Opened_Panel_Cover"
c("sinif KODUYLA da secilebilir", K.gerekli_slotlar(a) == ["pano_koyuluk_0_10"])

print("\n=== slot cozumleyicileri ===")
for ham, bek in (("3", 3), ("0", 0), ("6+", 6), ("GORUNMUYOR", None), ("", None),
                 ("__HATA__ X", None)):
    c(f"sayi {ham!r} -> {bek}", G._sayi(ham) == bek)
for ham, bek in (("VAR", "VAR"), ("YOK", "YOK"), ("KISI_YOK", None), ("GORUNMUYOR", None)):
    c(f"uclu {ham!r} -> {bek}", G._uclu(ham) == bek)
for ham, bek in (("DOGRUDAN_ETKILESIM", "VAR"), ("YANINDAN_GECIS", "YOK"),
                 ("ARAC_YOK", "YOK"), ("GORUNMUYOR", None), ("VAR", None)):
    c(f"carpisma dogrulama {ham!r} -> {bek}",
      G._carpisma_dogrulama(ham) == bek)
for ham, bek in (("ASILI_YUK", "VAR"), ("YUK_YERDE_VEYA_ARACTA", "YOK"),
                 ("YUK_YOK", "YOK"), ("GORUNMUYOR", None)):
    c(f"askida yuk {ham!r} -> {bek}", G._askida_yuk(ham) == bek)
for ham, bek in (("DUSME_BOLGESINDE_1S", "VAR"), ("YALNIZ_YAKIN", "YOK"),
                 ("KISA_GECIS", "YOK"), ("GORUNMUYOR", None)):
    c(f"askida yuk iliskisi {ham!r} -> {bek}", G._askida_yuk_iliskisi(ham) == bek)

print("\n=== KURAL MOTORU — deterministik, modelsiz ===")
ay = Settings()
ay.yelek_yetki_kurali = True  # bu bolum eski, beyanli tesis sozlesmesini olcer
ay.panel_koyuluk_kurali = True
ay.forklift_kasa_kurali = True
kayit = G.GozlemKaydi()
kayit.koy(G.SLOT_CATAL_KASA, "3")
o = K.olaylari_uret(kayit, ay, zaman="00:04")
c("3 kasa -> 1 olay", len(o) == 1, f"-> {len(o)}")
c("tesis esigi beyan edilmezse 3 kasa otomatik ihlal DEGIL",
  K.olaylari_uret(kayit, Settings(_env_file=None)) == [])
if o:
    e = o[0]
    c("olay isg_kod tasiyor", getattr(e, "isg_kod", None) == "Carrying_Overload_with_Forklift",
      f"-> {getattr(e,'isg_kod',None)}")
    # SABLON metni GERCEK TURKCE'dir (operatore gosterilir ve ISG kaliplariyla
    # eslesmesi gerekir); ASCII'lestirilmis hali IKI sablonu kalıplardan
    # kopariyordu. Kontrol, degerin metne GIRDIGINI dogrular.
    c("olay metni SABLON (model nesri degil)",
      "çatalda 3 kasa" in e.event, f"-> {e.event}")
    c("zaman damgasi tasindi", e.time == "00:04")
    c("isg_kod model_dump()'a SIZMIYOR (K1 sozlesmesi)", "isg_kod" not in e.model_dump())

kayit2 = G.GozlemKaydi(); kayit2.koy(G.SLOT_CATAL_KASA, "2")
c("2 kasa -> olay YOK (esik alti)", K.olaylari_uret(kayit2, ay) == [])
kayit3 = G.GozlemKaydi(); kayit3.koy(G.SLOT_CATAL_KASA, "GORUNMUYOR")
c("cozulemeyen slot -> SESSIZ (K3 fail-open)", K.olaylari_uret(kayit3, ay) == [])

print("\n=== pano + yelek kurallari ===")
kp = G.GozlemKaydi(); kp.koy(G.SLOT_PANO_KOYULUK, "9")
op = K.olaylari_uret(kp, ay)
c("koyuluk 9 -> pano olayi", len(op) == 1 and getattr(op[0], "isg_kod", "") == "Opened_Panel_Cover")
kp2 = G.GozlemKaydi(); kp2.koy(G.SLOT_PANO_KOYULUK, "1")
c("koyuluk 1 -> olay YOK", K.olaylari_uret(kp2, ay) == [])
ky = G.GozlemKaydi(); ky.koy(G.SLOT_MAKINE_KISI, "1"); ky.koy(G.SLOT_YELEK, "YOK")
oy = K.olaylari_uret(ky, ay)
c("kisi VAR + yelek YOK -> yetkisiz mudahale", len(oy) == 1 and getattr(oy[0], "isg_kod", "") == "Unauthorized_Intervention")
ay_yetkisiz_kapali = Settings(_env_file=None)
c("tesis beyani YOK -> yelek yoklugu yetkisiz mudahale DEGIL",
  K.olaylari_uret(ky, ay_yetkisiz_kapali) == [])
ky2 = G.GozlemKaydi(); ky2.koy(G.SLOT_MAKINE_KISI, "1"); ky2.koy(G.SLOT_YELEK, "VAR")
c("yelek VAR -> olay YOK", K.olaylari_uret(ky2, ay) == [])
ky3 = G.GozlemKaydi(); ky3.koy(G.SLOT_MAKINE_KISI, "1"); ky3.koy(G.SLOT_YELEK, "KISI_YOK")
c("KISI_YOK -> olay YOK (kararsiz, negatif DEGIL)", K.olaylari_uret(ky3, ay) == [])

print()
print("=== ON KOSUL KAPISI (olculdu: kapisiz kural forkliftte de atesleniyordu) ===")
kg1 = G.GozlemKaydi(); kg1.koy(G.SLOT_MAKINE_KISI, "0"); kg1.koy(G.SLOT_YELEK, "YOK")
c("makinede KIMSE YOK -> yelek YOK olsa bile olay YOK", K.olaylari_uret(kg1, ay) == [])
kg2 = G.GozlemKaydi(); kg2.koy(G.SLOT_YELEK, "YOK")
c("ON KOSUL HIC olculmedi -> IDDIA EDILMEZ", K.olaylari_uret(kg2, ay) == [])
kg3 = G.GozlemKaydi(); kg3.koy(G.SLOT_MAKINE_KISI, "GORUNMUYOR"); kg3.koy(G.SLOT_YELEK, "YOK")
c("ON KOSUL cozulemedi -> IDDIA EDILMEZ", K.olaylari_uret(kg3, ay) == [])
kg4 = G.GozlemKaydi(); kg4.koy(G.SLOT_MAKINE_KISI, "3"); kg4.koy(G.SLOT_YELEK, "YOK")
c("kalabalik (3 kisi) -> kural yine gecerli", len(K.olaylari_uret(kg4, ay)) == 1)
kg5 = G.GozlemKaydi(); kg5.koy(G.SLOT_MAKINE_KISI, "0"); kg5.koy(G.SLOT_CATAL_KASA, "4")
c("ON KOSUL yalnizca KENDI kuralini baglar (forklift etkilenmez)",
  len(K.olaylari_uret(kg5, ay)) == 1 and getattr(K.olaylari_uret(kg5, ay)[0], "isg_kod", "") == "Carrying_Overload_with_Forklift")

print("\n=== SLOT SEVIYESINDE MODEL SECIMI (modeller ters uzmanlasmis) ===")
c("kasa sayimi -> 'sayim' gorevi", G.SLOT_CATAL_KASA.gorev == "sayim")
c("yelek -> 'algi' gorevi (vlm)", G.SLOT_YELEK.gorev == "algi")
c("pano koyulugu -> 'sayim' gorevi", G.SLOT_PANO_KOYULUK.gorev == "sayim")
c("eski tesis slotlari olculmus 1280 spekini korur",
  G.SLOT_YELEK.max_side == 1280 and G.SLOT_PANO_KOYULUK.max_side == 1280)
c("genel depo olay slotlari kaynak 1080p kullanir",
  all(x.max_side == 1920 for x in (G.SLOT_DEPO_YANGIN,
                                   G.SLOT_DEPO_HAREKETLI_FORKLIFT,
                                   G.SLOT_DEPO_FORKLIFT_CARPISMA_DOGRULAMA,
                                   G.SLOT_DEPO_FORKLIFT_CARPISMA,
                                   G.SLOT_DEPO_FORKLIFT_KISI,
                                   G.SLOT_DEPO_ASKIDA_YUK,
                                   G.SLOT_DEPO_ASKIDA_YUK_KISI)))
c("ilişki/doğrulama slotları olay rolünde",
  G.SLOT_DEPO_FORKLIFT_CARPISMA_DOGRULAMA.gorev == "olay"
  and G.SLOT_DEPO_FORKLIFT_KISI.gorev == "olay"
  and G.SLOT_DEPO_ASKIDA_YUK_KISI.gorev == "olay")
c("yangin slotu tehlike adini degil fiziksel bulut olgusunu olcer",
  "BULUTUMSU" in G.SLOT_DEPO_YANGIN.soru.upper()
  and "yangın var mı" not in G.SLOT_DEPO_YANGIN.soru.lower())
c("ramak kala kurali once hareketli arac varligini ister",
  all(k.on_slot == "depo_hareketli_forklift" and k.on_etiket == "VAR"
      for k in K.KURALLAR if k.kod == "Forklift_Human_NearMiss"))
c("carpisma kurali bagimsiz dogrudan-etkilesim destegi ister",
  all(k.on_slot == "depo_forklift_carpisma_dogrulama" and k.on_etiket == "VAR"
      for k in K.KURALLAR if k.kod == "Forklift_Shelf_Collision"))
c("askida yuk kurali varlik kapisi ister",
  all(k.on_slot == "depo_askida_yuk" and k.on_etiket == "VAR"
      for k in K.KURALLAR if k.kod == "Worker_Under_Suspended_Load"))

_gate_yok = G.GozlemKaydi()
_gate_yok.degerler.update({"depo_hareketli_forklift": "YOK",
                           "depo_forklift_kisi_tehlike": "VAR"})
c("forklift yoksa iliski VAR olsa bile ramak kala olayi uretilmez",
  not any(getattr(e, "isg_kod", "") == "Forklift_Human_NearMiss"
          for e in K.olaylari_uret(_gate_yok, a)))
_gate_var = G.GozlemKaydi()
_gate_var.degerler.update({"depo_hareketli_forklift": "VAR",
                           "depo_forklift_kisi_tehlike": "VAR"})
c("forklift varlik kapisi aciksa ramak kala iliskisi korunur",
  any(getattr(e, "isg_kod", "") == "Forklift_Human_NearMiss"
      for e in K.olaylari_uret(_gate_var, a)))

_carpisma_celiski = G.GozlemKaydi()
_carpisma_celiski.degerler.update({"depo_forklift_raf_carpisma": "VAR",
                                   "depo_forklift_carpisma_dogrulama": "YOK"})
c("carpisma onerisi VAR ama bagimsiz destek YOK -> olay uretilmez",
  not any(getattr(e, "isg_kod", "") == "Forklift_Shelf_Collision"
          for e in K.olaylari_uret(_carpisma_celiski, a)))
_carpisma_destek = G.GozlemKaydi()
_carpisma_destek.degerler.update({"depo_forklift_raf_carpisma": "VAR",
                                  "depo_forklift_carpisma_dogrulama": "VAR"})
c("iki bagimsiz carpisma olcumu VAR -> deterministik olay",
  any(getattr(e, "isg_kod", "") == "Forklift_Shelf_Collision"
      for e in K.olaylari_uret(_carpisma_destek, a)))

print("\n=== CEKIMSERLIGE DAVET YOK (olculdu: MCC 0,885 -> 0,000) ===")
for s_ in G.SLOT_KATALOG.values():
    c(f"{s_.ad}: 'ayirt edemiyorsan' ifadesi YOK",
      "ayirt edemiyorsan" not in s_.soru.lower() and "kacis" not in s_.soru.lower())


print()
print("=== ALT-ESIK KURALI (yaya yolu — yon KURALIN TANIMINDA sabit) ===")
ky1 = G.GozlemKaydi(); ky1.koy(G.SLOT_YAYA_CIZGI_MESAFE, "0")
oy1 = K.olaylari_uret(ky1, ay)
c("cizgiye uzaklik 0 -> yaya yolu ihlali",
  len(oy1) == 1 and getattr(oy1[0], "isg_kod", "") == "Safe_Walkway_Violation")
ky2 = G.GozlemKaydi(); ky2.koy(G.SLOT_YAYA_CIZGI_MESAFE, "7")
c("uzaklik 7 (esigin kendisi) -> olay YOK", K.olaylari_uret(ky2, ay) == [])
ky3 = G.GozlemKaydi(); ky3.koy(G.SLOT_YAYA_CIZGI_MESAFE, "9")
c("uzaklik 9 -> olay YOK", K.olaylari_uret(ky3, ay) == [])
ky4 = G.GozlemKaydi(); ky4.koy(G.SLOT_YAYA_CIZGI_MESAFE, "GORUNMUYOR")
c("olculemedi -> SESSIZ (K3, negatif DEGIL)", K.olaylari_uret(ky4, ay) == [])
c("yon EsikKurali'nin TERSI (ayri sinif, cevrilebilir bayrak DEGIL)",
  K.AltEsikKurali is not K.EsikKurali)
c("yol slotu ROI alanina bagli", G.SLOT_YAYA_CIZGI_MESAFE.roi_alani == "yol_roi_vlm")
c("yol slotu KLIP kapsamli (sevk edilen = olculen)",
  G.SLOT_YAYA_CIZGI_MESAFE.kapsam == "klip")
from tests.taban import sinif_varsayilani
c("yol_roi_vlm varsayilani BOS (K2)", sinif_varsayilani("yol_roi_vlm") == "")
c("yol_mesafe_esik varsayilani 7 (olculen esik)",
  sinif_varsayilani("yol_mesafe_esik") == 7)

print()
print("=== KURAL KODU ILE SLOT SECIMI ===")
a2 = A(); a2.isg_slotlari = "Safe_Walkway_Violation"
# 2026-08-25: `Safe_Walkway_Violation` kodunu artik IKI kural paylasiyor —
# ILISKISEL soru (yaya_cizgi_mesafe) ve YEREL soru (yaya_zemin, + on kosul
# slotu makine_basinda_kisi). Ikisi de AYNI kodu tasimak ZORUNDA cunku kod
# ISG sinif etiketidir ve `isg_match` onun uzerinden eslesir. Dolayisiyla
# kod ile secim her ikisinin slotlarini birden getirir — bu KASITLI.
c("kural KODU ile secilebilir (iki kural ayni kodu paylasir)",
  K.gerekli_slotlar(a2) == ["yaya_cizgi_mesafe", "makine_basinda_kisi",
                            "yaya_zemin"])
c("ILISKISEL slot hala secilebiliyor (kol karsilastirmasi icin sart)",
  "yaya_cizgi_mesafe" in K.gerekli_slotlar(a2))
c("YEREL slot da geliyor", "yaya_zemin" in K.gerekli_slotlar(a2))
a3 = A(); a3.isg_slotlari = "*"; a3.yelek_yetki_kurali = True; a3.panel_koyuluk_kurali = True; a3.forklift_kasa_kurali = True
c("'*' yol slotunu da ister", "yaya_cizgi_mesafe" in K.gerekli_slotlar(a3))

print(f"\ngecen={g}  kalan={k}")
sys.exit(1 if k else 0)
