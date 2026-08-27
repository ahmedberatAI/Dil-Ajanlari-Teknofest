# ON KAYIT — D48 KOL 4: aday-kisitli siniflandirma vs. serbest metin
# YAZILMA ZAMANI: kosumdan ONCE (2026-08-27). Kosum sonrasi DEGISTIRILMEZ.

## SORU
"Aday kumesi verilirse model HANGI olay oldugunu biliyor" (olculdu: %44-55)
ama bizim boru hattimiz aday vermiyor. AYNI KLIPLERDE fark KAC PUAN?

## KLIP SECIMI (mekanik, cherry-pick YOK)
hazard_mcq_single.json -> video_name'e gore TEKILLESTIR (ilk kayit kalir,
pseudo-replikasyon onlemi) -> random.Random(2026).shuffle -> ILK 25.
Bu kume, isafety_uzak_20260824_233450.json'un 150 klibinin ONEKIDIR
(ayni tohum, ayni tekillestirme) -> taban sayilariyla ayni evren.

## A KOLU — ADAY KISITLI (yayimlanmis bicimle AYNI)
- Aday kumesi: kaydin KENDI "choices" listesi (16 secenek), harfler A..P
- structured_outputs.choice=[A..P], temperature=0, max_tokens=4, hatirla=False
- video_oturumu(servis_videosu(yol)) — uzak vlm ucu goruntu listesi kabul etmiyor
- logprobs=True, top_logprobs=20 -> gozlem.secim_dagilimi ile HARF dagilimi
- Modeller: vlm VE llm-large. IKISI DE raporlanir (secim yok).
- Metrik: top-1 dogruluk, top-3 dogruluk (dagilimda en yuksek 3 harf),
  Wilson %95 GA, sans tabani 1/16 = %6,25

## B KOLU — SERBEST METIN (bizim boru hattimiz)
- AYNI 25 klipte analyze_video (varsayilan ayarlar, n_samples=1)
- "serbest metin" = summary + tum event.event metinleri (birlestirilmis)
- IKI ayri, MEKANIK olcut:

  B1 ANAHTAR KELIME (kullanicinin istedigi olcut)
      chosen_gt_action -> Turkce anahtar kelime listesi (ASAGIDA, kosumdan
      ONCE yazildi). Metin diyakritikten arindirilip kucultulur; listedeki
      HERHANGI bir dizge gecerse ISABET.
      Birincil sayim YALNIZ chosen_gt_action uzerinden. other_gt_actions
      isabeti AYRICA sayilir ama birincil skora KATILMAZ.

  B2 ZORUNLU SECIM HAKEMI (A ile AYNI BICIM -> dogrudan karsilastirilabilir)
      llm-large'a YALNIZCA bizim Turkce metnimiz verilir (VIDEO YOK), ayni 16
      secenekten birini secmeye ZORLANIR (structured_outputs.choice, T=0).
      Dogru = answer_index. Sans tabani yine %6,25. top-3 de kaydedilir.
      Bu, "serbest metnimizin tasidigi bilgi" icin UST SINIRDIR: hakem metinde
      olmayan bir seyi bilemez.

## KARSILASTIRMA (onceden secildi)
Birincil kiyas: A(vlm) top-1  vs  B2 top-1, AYNI 25 klipte ESLESMIS
-> McNemar exact p + fark. n=25 kucuktur; GA'lar birlikte raporlanir.

## RAPORLAMA KURALI
Tum sayilar, sonuc ne cikarsa ciksin raporlanir. Kosum tekrarlanmaz,
esik sonradan degistirilmez. Atlanan klip sayisi ayrica yazilir.

## LISANS
data/isafety_bench CC BY-NC-SA 4.0 — YALNIZCA DEGERLENDIRME. Agirlik
uretilmez; veri_lisans kapisi kosum basinda iki yonlu dogrulanir.

## B1 SOZLUGU (kosumdan ONCE yazildi, kosum sirasinda DEGISTIRILMEZ)
fire incident                            : yangin, alev, ates, tutus, yanma, yaniyor
extinguishing fire                       : sondur, itfaiye, yangin tup, yangin hortum
watching incident passively              : izliyor, seyrediyor, izleyen, seyirci, mudahale etmeden, pasif
vandalism or intentional property damage : vandal, tahrip, kasitli, kasten, zarar ver, kirip dok
trapped between closing machine sides    : sikis, arasinda kal, kapan, pres
body pulled into machine                 : makineye kapil, icine cekil, makineye cekil, sarildi, kapilma
falling load                             : yuk dus, dusen yuk, yukun dusme, yuk devril
hanging from something after slip        : asili kal, sarkiyor, tutunmus, asili
person falling down                      : kisi dus, isci dus, personel dus, yere dus, dusen kisi, dusen isci, dusen personel, dengesini kayb
operating forklift                       : forklift, istif makin, transpalet
forklift blade detaching                 : catal ayril, catal kop, catal dus, catalin kop
searching debris for victims             : enkaz, moloz, arama kurtarma, kurtarma calis
machine part flying off                  : parca firla, firlayan parca, kopan parca, parca kop
adjusting machine while running          : calisirken mudahale, calisan makine, makine calisirken, ayar yap
platform failure                         : platform, iskele, sehpa, kaldirma platformu

NOT: "duman" BILEREK yangin listesine ALINMADI (cokme/patlama tozunu da
yakalar -> yanli pozitif). Bu karar kosumdan ONCE verildi.

## EK — C KOLU (kosumdan ONCE yazildi, A/B sonuclari gorulduKTEN sonra EKLENDI;
##      A/B sayilarina DOKUNULMAZ, C ayri bir soruyu yanitlar)
SORU: 16 secenek veri setinin KENDI celdiricileridir; uretimde boyle bir liste
YOK. Mekanizma SABIT taksonomiyle de ayakta kaliyor mu?
- Aday kumesi: actions.txt `hazard_action_dict` — 10 KATEGORI / 62 EYLEM, SABIT.
- Asama 1: 10 kategori, zorunlu secim (A..J), video oturumu, T=0, logprob.
  Gercek kategori = chosen_gt_action'i iceren kategori. top-1 + top-3.
- Asama 2: SECILEN kategorinin eylemleri arasinda zorunlu secim.
  Uctan uca dogru = asama1 dogru VE asama2 dogru (gercekci kol).
  Ayrica GERCEK kategori verilerek asama 2 (oracle kol) — ust sinir.
- Sans: kategori 1/10 = %10; cogunluk-kategori tabani ayrica hesaplanir.
- Model: vlm (boru hattimizin algi modeli). Raporlama kosulsuz.

## EK — D KOLU (kosumdan ONCE yazildi)
SORU: C kolu SABIT taksonomiyi VIDEOYA sordu (kategori %36). Ayni SABIT
taksonomi BIZIM KENDI TURKCE METNIMIZE sorulursa ne olur? (uretimde
kullanilabilir tek bicim budur: klibe ozel 16'lik liste YOKTUR)
- Girdi: B kolunun urettigi rapor (ozet + olaylar), VIDEO YOK
- Model: llm-large · structured_outputs.choice · T=0 · logprobs
- Asama 1: 10 sabit kategori; Asama 2: secilen kategorinin eylemleri
- Metrik: kategori top-1/top-3, uctan uca top-1, oracle-kategori eylem top-1
- Kiyas: C kolu (video) ile ESLESMIS McNemar. Sonuc ne olursa olsun raporlanir.
- KONTROL: ayni iki asama BILGISIZ sabit metinle de kosulur (sifir-bilgi tabani).
