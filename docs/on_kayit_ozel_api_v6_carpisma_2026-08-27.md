# Ön kayıt — özel API v6 forklift–ekipman çarpışması

**Tarih:** 2026-08-27  
**Durum:** Sonuçlara bakılmadan önce donduruldu. Bu dilim model çıktısı sonrası revize
edilmiş geliştirme etiketlerini kullandığı için bağımsız final kanıtı değildir.

## Değişmez çalışma sözleşmesi

- Öğrenilmiş çıkarım yalnız `https://evren-llmapi.ssyz.org.tr/v1` özel API'sinde yapılır.
- Model rolleri sabittir: algı=`vlm`, olay=`llm-large`, yapı=`llm-fast`, özet=`llm-fast`.
- Model indirme, yerel model sunma, alias/model A/B'si yoktur.
- Değişken yalnız kanıt sorusu ve deterministik kabul-red kapısıdır.
- Kodlama: 1920 uzun kenar, 8 fps, sabit 800k bit hızı, bitexact.

## Karar kuralı

`Forklift_Shelf_Collision` yalnız şu iki bağımsız kapalı `vlm` ölçümü birlikte `VAR`
olduğunda üretilir:

1. araç ile taşınmayan ayrı hedef arasında temas/temas sonrası fiziksel etki önerisi;
2. hedefin doğrudan sürüş yolunda olduğu ve aracın hedefe fiziksel olarak ulaştığı doğrulaması.

Öneri `VAR`, doğrulama `YOK/GORUNMUYOR/ölçülemedi` ise sonuç `INSUFFICIENT`tır;
alarm üretilmez ve çelişki karar izine yazılır.

## Dondurulmuş odak dilimi

- Destekli pozitif: `00476...run_14` içindeki `cam_00`, `cam_01`, `cam_05` (3).
- Kanıtsız/belirsiz görüş: aynı run içindeki `cam_02`, `cam_03`, `cam_04` (3).
- Kanıtsız ikinci çarpışma run'ı: `004934...run_12` içindeki altı kamera (6).
- Çapraz zor negatif: `nearmiss...run_2...eye_04` (1).
- Normal zor negatif: `box_pickup...run_10...cam_03` (1).

Etiket ilkesi: olayın senaryo düzeyinde gerçekleşmesi, her kamerayı pozitif yapmaz.
Araç–hedef sınırlarının görünür teması veya hedefte doğrudan hareket kanıtı yoksa o
kamera için kesin çarpışma iddiası desteklenmez.

## Kabul ölçütü

- destekli görünürlük recall: `3/3`;
- kanıtsız/belirsiz aynı-senaryo görünümünde çarpışma alarmı: `0/9`;
- çapraz zor negatiflerde çarpışma alarmı: `0/2`;
- API/slot hatası: `0`;
- her öneri-doğrulama çelişkisi karar izinde `INSUFFICIENT` olarak görünür.

Bu ölçütlerden biri kalırsa v6 kabul edilmez; sonuç görüldükten sonra bu ön kayıt
değiştirilmez. Yeni yaklaşım ayrı revizyon ve ayrı ön kayıt gerektirir.
