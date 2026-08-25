# Kamera karıştırıcısı — skor kameradan mı geliyor?

Tarih: 2026-08-25 · Yöntem: katmanlı (stratified) analiz

## Bulunan veri kusuru

`Unauthorized_Intervention` ↔ `Authorized_Intervention` çiftinde **iki farklı
kamera görüşü** var ve görüş etiketle güçlü korele:

| görüş | ihlal | normal |
|---|---|---|
| GÖRÜŞ-A (yakın plan) | 8 | 23 |
| GÖRÜŞ-B (geniş plan) | **17** | 2 |

Görüş imzasının etiketi tahmin gücü: **|MCC| 0,833**.

Bu, kodlama sızıntısıyla aynı sınıftan bir tuzak: *"her zaman GÖRÜŞ-B'ye ihlal
de"* diyen, görüntünün içeriğine hiç bakmayan bir sistem bu çiftte
**MCC +0,618** alır. Bizim skorumuz +0,689 — yani tek başına "üstünde"
olması yeterli kanıt değil.

> Diğer çiftlerde bu sorun **yok**: görüş imzasının çift içi ayırma gücü
> pano 0,275 · yaya yolu 0,385. Yalnızca yetkisiz müdahale çiftinde güçlü.

## Belirleyici test — katman içi ayrım

Kural her kamera görüşünün **içinde** ayrı ayrı ayırt ediyor mu?
(Cochran–Mantel–Haenszel mantığı: karıştırıcı sabitlendiğinde ilişki kalıyor mu?)

| katman | n | TP | FP | FN | TN | MCC |
|---|---|---|---|---|---|---|
| tümü | 50 | 19 | 2 | 6 | 23 | +0,689 |
| GÖRÜŞ-A | 31 | 5 | 2 | 3 | 21 | **+0,563** |
| GÖRÜŞ-B | 19 | 14 | 0 | 3 | 2 | **+0,574** |
| *yalnızca kameraya bakan sistem* | 50 | 17 | 2 | 8 | 23 | +0,618 |

**Kural her iki katmanda da ayırt ediyor** (+0,563 ve +0,574). Yani skor
kameradan değil, görüntü içeriğinden — yelek varlığından — geliyor. Kamera
görüşü yalnızca bir karıştırıcıdır.

## Neden bu test önemli

Bu projede daha önce **iki** benzer tuzak yakalandı:

1. **Geofence** — MCC +0,506 görünüyordu; çerçeveleme tek başına aynı skoru
   veriyordu. Reddedildi.
2. **Kodlama sızıntısı** — forklift çiftinde bit hızı tek başına +1,000.
   Kontrol koşuldu, skorlar hayatta kaldı.

Bu üçüncüsü. Aynı disiplin uygulandı: karıştırıcıyı ölç, sabitle, ilişki
kalıyor mu bak.

## Sonuç olarak yapılmayan

GÖRÜŞ-B'de yelek kuralının 3 kaçırması var (kapı `kisi=0` diyor, çünkü geniş
planda panonun başında kimse seçilemiyor). "Geniş görüşte farklı soru sor"
yaklaşımı **denenmedi ve denenmemeli**: görüş etiketle 0,833 korele olduğu
için görüşe göre davranış değiştirmek etiket bilgisi sızdırır — geofence'in
reddedilme sebebinin ta kendisi.

Bu yüzden yelek kuralı +0,689'da kalıyor ve tavanı belgeleniyor.

---

## Diğer iki çiftte durum — karıştırıcı yok

Aynı test forklift ve pano çiftlerine de uygulandı:

| çift | görüş dağılımı | yalnızca kamera tabanı | bizim skor | görüş içi |
|---|---|---|---|---|
| pano | 48/49 klip tek görüşte (24 ihlal / 24 normal) | 0,141 | +0,960 | **+0,959** |
| forklift | 49/50 klip tek görüşte (24 ihlal / 25 normal) | 0,143 | +0,881 | **+0,878** |
| yetkisiz | iki görüş, 8/23 ve 17/2 | **0,618** | +0,689 | **+0,563 / +0,574** |

Pano ve forklift çiftlerinde klipler **tek kamera görüşünde** ve sınıflar
dengeli dağılmış; kameraya bakarak alınabilecek en yüksek skor 0,14. Bu iki
çiftte kamera karıştırıcısı **yok**.

Yalnızca yetkisiz müdahale çiftinde ciddi bir karıştırıcı var ve orada da
katman içi ayrım korunuyor.

## Özet

Üç kuralın hiçbirinin skoru kamera açısından gelmiyor:

- pano ve forklift: karıştırıcı zaten yok (taban 0,14)
- yetkisiz: karıştırıcı güçlü (taban 0,62) ama katman içi ayrım +0,56/+0,57
