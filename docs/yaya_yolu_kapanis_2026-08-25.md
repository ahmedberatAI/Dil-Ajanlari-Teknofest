# Yaya yolu sınıfı — dokuz kol, dokuz ret

Tarih: 2026-08-25 · Karar: **sevk edilmiyor**

`Safe_Walkway_Violation`, dört İSG sınıfından biri ve 25 anomali klibi
(anomali kümesinin %25'i). Kapsanmadığı için `isg_match` 0,646'da kalıyor;
kapsansaydı 0,865 olurdu. Bu yüzden ısrarla denendi.

## Denenen kolların tamamı

| # | kol | sonuç |
|---|---|---|
| 1 | tam kare, ikili soru (içinde/dışında) | dejenere — 28 klibin 27'si "DIŞINDA" |
| 2 | tam kare, sayım (yol dışında kaç kişi) | −0,280 |
| 3 | tam kare, mesafe 0-10 | +0,192 |
| 4 | ROI alt şerit, mesafe | +0,082 |
| 5 | ROI, ikili soru | dejenere |
| 6 | ROI alt yarı, mesafe — **seçim kümesi** | +0,466 |
| 7 | ROI alt yarı — **ayrılmış küme** | **+0,638** · ama saha kesinliği 0,151 |
| 8 | ROI + görüş muhafızı + fps 8 | +0,119 |
| 9 | ROI + görüş muhafızı + özgün fps | **+0,313** · saha kesinliği 0,190 |

Ayrıca ayrı bir hipotez olarak **bit hızı** test edildi ve çürütüldü:
800k CBR ile CRF26 birebir aynı sonucu verdi (+0,217).

## Neden ısrar edildi ve neden bırakıldı

Kol 7 gerçek bir sonuçtu: eşik koşumdan önce sabitlenmiş, ayrılmış kümede
MCC +0,638, 11 ihlalin hepsi yakalanmış. Sorun **saha davranışıydı** —
kural, forklift kliplerinin 49/50'sinde ateşliyordu.

Kol 8-9'da bu kapatıldı: kamera görüş muhafızı forklift kamerasında
**0/28** ateşleme bıraktı (kamera 9'da 42/42 sorulmaya devam etti). Yani
kameralar arası sızıntı tamamen bitti. Buna rağmen:

- kendi çiftinde MCC yalnızca **+0,313** (ön kayıtlı eşik +0,45)
- saha kesinliği **0,190** (sevk edilen en düşük kural, yelek, 0,237)

Kalan yanlış ateşlemelerin tamamı **kamera 9'un içinde** — pano ve yetkisiz
müdahale kliplerinde. Orada yaya yolu çizgisi görünür durumda olduğu için
görüş muhafızı bunları ayıramaz.

## Öğrenilen — diğer sınıflara da uygulanan

**Yaya yolu ihlali ANLIK bir durumdur.** Kişi çizgiyi bir anda geçer.
Kare seyreltmek o anı kaçırıyor:

    özgün fps  IHLAL: {0:12, 5:11, 6:2}     -> hiç "7" yok
    fps 8      IHLAL: {5:11, 0:9, 7:4, 6:1} -> bazı ihlaller "uzak" diyor

Pano **statik**, forklift **sürekli** bir durumdur; ikisi de fps 8'de
bozulmuyor (+0,960 ve +0,843). Bu gözlem slotlara **kendi kare hızını**
verme özelliğini doğurdu — ROI ve kapsam ile aynı desen. Yol slotu için
yetmedi ama mekanizma kodda kaldı ve test edildi.

## Ne zaman yeniden açılmalı

Sınıfın kendi çiftinde MCC ≥ +0,45 **ve** saha kesinliği ≥ 0,237 sağlanana
kadar kapalı. Kod, muhafız, testler ve ölçüm kayıtları duruyor:
`DILAJAN_ISG_SLOTLARI` listesine `yaya_cizgi_mesafe` eklenmesi yeterli.

Muhtemel yol: kamera 9 içinde yaya yolu ihlalini pano/yelek ihlallerinden
ayıran bir **ön koşul** — örneğin "yürüyen kişi var mı" — ama bu ölçülmeden
açılmamalıdır.
