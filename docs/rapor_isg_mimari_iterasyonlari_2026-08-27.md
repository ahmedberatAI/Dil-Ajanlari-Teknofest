# İSG VLM mimari iterasyon raporu — 2026-08-27

## Sonuç

Sabit özel API ve sabit `vlm / llm-large / llm-fast` model sözleşmesi korunarak
SynthSite Tier-1 askıda-yük geliştirme kümesinde dört yeni mimari kol ölçüldü.
Hiçbiri beş kabul kapısının tamamını geçmedi. Bu nedenle askıda-yük sınıfı kritik
üretim alarmı olarak etkinleştirilmedi; başarısız bir benchmark sonucu sevk koduna
başarı gibi taşınmadı.

| Kol | n | TP | FP | TN | FN/kaçınma | Recall | Precision | FPR | Coverage | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Eski birleşik `vlm` Tier-1 | 150 | 17 | 12 | 62 | 59 | %22,4 | %58,6 | %16,2 | %100 | RED |
| v2 atomik `vlm` + `llm-large` | 30 | 14 | 8 | 7 | 1 | %93,3 | %63,6 | %53,3 | %100 | RED |
| v3 kontrastif mekânsal etiket | 30 | 14 | 8 | 7 | 1 | %93,3 | %63,6 | %53,3 | %100 | RED |
| v4 nötr defter + metin hakemi | 30 | 6 | 0 | 14 | 10* | %40,0 | %100 | %0 | %86,7 | RED |
| v5 nesne defteri | 30 | 0 | 0 | 0 | 30* | %0 | tanımsız | %0 | %0 | GEÇERSİZ |

`*` v4'te 6 kararlı FN + 4 hata/kaçınma; v5'te 30/30 JSON kesilmesi.

## Kök nedenler

1. Eski tek istem askıda yük, düşme bölgesi ve ≥1 saniye koşullarını ayırmadığı
   için çoğu pozitif kaçtı.
2. Atomik v2 recall'ı büyük ölçüde onardı; ancak ilişki rolü askıda yük bulunan
   güvenli sahnelerde çalışanı sahne önseliyle doğrudan bölgede saydı.
3. v3'te `vlm` 30 klibin 29'unda aynı olumlu mekânsal etiketi verdi. Seçenek sırası
   ters çevrilmiş dört FP tanısında yalnız biri değişti; sorun yalnız ilk-seçenek
   yanlılığı değildi.
4. v4 nötr kanıt defteri yanlış alarmı tamamen kesti, fakat karar-yüklü `engel var
   mı?` alanı gerçek pozitiflerde çıplak `var` üretti ve hakem bunu fiziksel bariyer
   saydı. Üç JSON sınırsız liste nedeniyle kesildi.
5. v5 karar sözcüklerini kaldırdı; fakat servis JSON şemasındaki `maxLength`i
   uygulamadı ve 360 token sınırında 30 yanıtın tamamı kesildi. Bu koşu algı
   başarısızlığı değil, koşu-geçerlilik başarısızlığıdır.

## Üretime alınanlar

- Serbest anlatıdaki yedi somut İSG ailesi için iki rollü atomik, fail-closed kanıt
  kapısı.
- Ailesiz veya yalnız muğlak kişi-hareketi olan açık-dünya nesrinin alarm olamaması.
- Yapılandırılmış İSG/KKD olayının yakındaki serbest anlatı kopyasını gölgelemesi.
- Aynı sınıfın yalnız bitişik segmentlerde birleşmesi; uzun aradan sonraki yeni olayın
  korunması.
- Olayın tek kare değil segment zaman aralığı taşıması.
- Kaynak video SHA-256, başlangıç/orta/bitiş storyboard'u ve gerçek hash zincirli
  kanıt manifesti.
- Özel API profilinde yerel öğrenilmiş YOLO/RT-DETR/pose çıkarımının ve model
  indirmenin varsayılan olarak engellenmesi.

## Üretime alınmayanlar

- Askıda-yük kuralı: kod/benchmarkta deneysel olarak durur, etkin slot listesinde yok.
- v3 mekânsal doğrudan etiket kapısı: v2'ye hiçbir kazanç sağlamadı.
- v4'ü tek alarm eşiği yapmak: precision iyi olsa da recall kabul edilemez.
- v5 JSON defteri: coverage sıfır olduğu için skorlanamaz.

## Doğru operasyonel kullanım

v2 ve v4 sonuçları tek bir ikili eşikte birleştirilemez. İleride yeni, görülmemiş ve
zaman/bbox alt-etiketli holdout sağlandığında v2 benzeri kol yalnız “inceleme adayı”,
v4 benzeri kol “doğrulanmış alarm” olarak ayrı kalibre edilmelidir. Mevcut n=30
sonuçları geliştirme sırasında görüldüğünden final genelleme kanıtı değildir.
