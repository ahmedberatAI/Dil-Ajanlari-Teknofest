# Ön kayıt — özel API v7 çarpışma kanıt etiketi

**Tarih:** 2026-08-27  
**Önceki kol:** v6 odak koşusu ilk destekli `cam_00` örneğinde başarısız oldu ve
durduruldu. Ana slot `VAR`, doğrulama slotu `YOK` üretti. v6 ön kaydı değiştirilmedi.

## Tek değişiklik

Model, endpoint, video bayt speki, fiziksel soru ve karar kuralı sabittir. Yalnız doğrulama
slotunun kapalı cevap sözlüğü soyut `VAR/YOK` yerine fiziksel anlam taşıyan
`DOGRUDAN_ETKILESIM / YANINDAN_GECIS / ARAC_YOK / GORUNMUYOR` olur. Sabit parser ilkini
`VAR`, ikinci ve üçüncüyü `YOK`, sonuncuyu ölçülemedi olarak eşler.

Aynı özel API `vlm` modeli ve aynı video üzerinde ön tanıda soyut etiket `YOK`, anlamlı
etiket `DOGRUDAN_ETKILESIM` verdi. Bu nedenle değişiklik model seçimi değil, cevap
uzayındaki ölçüm tanımının açıklaştırılmasıdır.

## Değişmez sözleşme ve kabul

- endpoint: `https://evren-llmapi.ssyz.org.tr/v1`;
- sabit roller: algı=`vlm`, olay=`llm-large`, yapı/özet=`llm-fast`;
- yerel model/indirme yok;
- dilim ve görünürlük tanımı v6 ön kaydıyla aynıdır;
- destekli görünürlük recall `3/3`;
- kanıtsız/belirsiz aynı-senaryo çarpışma alarmı `0/9`;
- çapraz zor negatif çarpışma alarmı `0/2`;
- API/slot hatası `0`;
- öneri-doğrulama çelişkisi karar izinde `INSUFFICIENT` olmalıdır.

Sonuç görüldükten sonra bu ön kayıt değiştirilmeyecektir.
