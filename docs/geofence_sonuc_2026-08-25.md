# Tespit-tabanlı geofence — ölçüldü ve REDDEDİLDİ (bağımsız bilgi taşımıyor)

Tarih: **2026-08-25** · Yaya yolu sınıfı için **on birinci** mekanizma.

## 0. Neden denendi

Reddedilen on kolun hepsi **VLM sorusu** varyasyonuydu. Tespit-tabanlı
geofence — kişinin ayak noktası yeşil boyalı yolun üstünde mi değil mi —
**hiç denenmemişti** ve içerik-temelli, çerçeve-temelli değil:

- kişi konumu **CPU tespitiyle** ölçülür (yerel GPU yasak, CPU serbest)
- zemin boyası **renkten** bulunur (etiket görmez → aşırı uyum yok)
- hüküm **geometrik** verilir (VLM yok)

## 1. Hipotez DOĞRULANDI ama yetmedi

Ayak noktasının en yakın yeşil piksele uzaklığı (klip başına minimum):

| sınıf | medyan |
|---|---|
| `Safe_Walkway` (normal) | **0,025** — biri gerçekten yolun üstünde |
| `Safe_Walkway_Violation` | **0,204** — kimse yolu kullanmıyor |

Sekiz kat fark. Sinyal **gerçek**.

## 2. Ama dürüst eşikle çöküyor

| ölçüm | değer |
|---|---|
| en iyi eşik, TÜM veride taranmış | 0,762 |
| **leave-one-out (eşik dışarıda seçilir)** | **0,625** |
| çerçeve tabanı (kişiler silinmiş arka plandan) | **0,729** |

Eşik taraması skoru **+0,137 şişiriyor**. Dürüst ölçümde geofence, yalnız
kadrajdan tahmin etmenin **altında** kalıyor.

## 3. Şartlı analiz — kesin hüküm

Toplam doğruluk karşılaştırması yetmez: iki yöntem aynı kliplerde doğru
olabilir, o zaman geofence çerçeveyi başka yoldan okuyordur. Doğru test
şartlıdır:

| alt küme | n | geofence doğruluğu |
|---|---|---|
| çerçevenin DOĞRU olduğu klipler | 35 | 0,686 |
| **çerçevenin YANILDIĞI klipler** | 13 | **0,462** |

Çerçevenin yanıldığı yerde geofence **şanstan düşük**. McNemar:
6 düzeltti / 11 bozdu, **p=0,3323**.

**Geofence bağımsız bilgi taşımıyor.** RET.

## 4. Karıştırıcı üç çiftte de var — ama sadece burada BELİRLEYİCİ

Kişiler silinmiş arka plandan etiket tahmini (leave-one-out):

| çift | çerçeve tabanı | kuralın doğruluğu | fark |
|---|---|---|---|
| pano | 0,694 | **0,980** | **+0,286** |
| yetkisiz | 0,800 | 0,840 | +0,040 |
| **yaya yolu** | **0,729** | 0,667 (mesafe kuralı) | **−0,062** |

Karıştırıcının varlığı bir sınıfı diskalifiye etmiyor — pano onu **fark
kadar** aşıyor. Yaya yolunda ise hiçbir kol aşamıyor.

Bu, kapanış belgesindeki *"çerçeveleme tek başına %72,9"* bulgusunun
**bağımsız replikasyonudur** (0,729 birebir çıktı).

## 5. Sınıfın durumu

**On bir mekanizma, on bir ret.** Ve artık ret sebebi tally değil:

> Bu klip çiftinde etiket, içerikten çok **kadrajla** ilişkili. Çıkarabildiğimiz
> hiçbir içerik sinyali — ne VLM sorusu (10 kol), ne geometrik geofence —
> kadraj tabanını aşmıyor.

Yeniden açılma koşulu değişmedi. Yeni bilgi: bir sonraki denemenin
**karıştırıcıdan bağımsız olduğunu ÖNCE göstermesi** gerekir — şartlı analiz
(çerçevenin yanıldığı kliplerde doğruluk) ilk kapı olmalıdır, son değil.
