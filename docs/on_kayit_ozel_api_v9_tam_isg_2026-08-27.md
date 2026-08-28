# Ön kayıt — özel API v9 tam NVIDIA depo İSG geliştirme koşusu

**Tarih:** 2026-08-27  
**Veri:** `data/dev_nvidia_warehouse`, 62 kamera görünümü.  
**Etiket:** `benchmark/nvidia_sdg_dev_visibility.json`, revizyon 3.

Bu etiket dosyası önceki model çıktıları görüldükten sonra revize edildiğinden koşu yalnız
geliştirme/regresyon kanıtıdır; bağımsız final/holdout sonucu diye sunulmayacaktır.

## Değişmez çalışma sözleşmesi

- Öğrenilmiş çıkarım yalnız `https://evren-llmapi.ssyz.org.tr/v1` özel API'sinde.
- Sabit roller: algı=`vlm`, olay=`llm-large`, yapı=`llm-fast`, özet=`llm-fast`.
- Yerel model, model indirme, model/alias A/B'si yok.
- Pipeline: `2026-08-27-isg-grounded-v9-byte-exact-evidence-prompt`.
- `.env` slot/politika sözleşmesi değiştirilmeden kullanılır.
- 3 paralel işçi; sonuç her klipten sonra kimlik-hash'li ara kayda yazılır.

## Görünür pozitif paydalar

- `Warehouse_Visible_Fire`: 2 görünüm;
- `Forklift_Shelf_Collision`: 3 doğrudan destekli görünüm;
- `Forklift_Human_NearMiss`: 20 görünüm.

Kamera dışında gerçekleşen senaryo, o kameranın pozitif etiketi değildir. Çarpışma önerisi
ile bağımsız doğrulama çelişirse `INSUFFICIENT` olur ve olay üretilmez.

## Kabul ölçütleri

- her üç kodda görünür recall en az `%80`;
- her kodun görünür olmayan görüşlerde yanlış alarm oranı en çok `%5`;
- görünür run'ların her birinde kamera çoğunluğu başarılı;
- 20 normal görünümde yüksek-risk FP en çok 1, operasyonel FP en çok 2,
  dispatch FP 0, kritik kanıtsız iddia en çok 1;
- API/slot hatası 0;
- özel API/model sözleşmesi koşudan önce fail-closed doğrulanır.

Sonuçtan sonra bu belge veya eşikler değiştirilmeyecek; kalan hata yeni revizyon ve yeni ön
kayıtla ele alınacaktır.
