# Ön kayıt — SynthSite nötr kanıt defteri v4

**Tarih:** 2026-08-27  
**Durum:** v4 çıktıları görülmeden yazıldı; geliştirme ölçümüdür.

v3 mekânsal doğrudan etiketi 30 klibin 29'unda aynı olumlu etiketi verdi ve v2'yi
iyileştirmedi. Buna karşılık tanısal yapılandırılmış yanıttaki serbest gözlem metni,
incelenen FP'lerde bariyer/yan taraf/destek karşı-kanıtlarını doğru betimledi. v4 bu
ayrımı mimariye taşır:

1. `vlm` hiçbir risk/ihlal/etiket kararı vermeden yük desteği, en yakın çalışanın
   konumu, engel/derinlik ve süre hakkında yalnız doğrudan gözlem cümleleri çıkarır.
2. `llm-large` videoyu görmez; yalnız bu defterin dört fiziksel önkoşulu açık ve
   çelişkisiz destekleyip desteklemediğini ölçer.
3. Yalnız v2 pozitif ve defter hakemi uyumluysa pozitif. Açık karşı-kanıt negatif,
   eksik/çelişkili defter kaçınmadır.

Hakem seçenek sırası dosya adı SHA-256'sıyla deterministik döndürülür; tek bir ilk
seçenek yanlılığı bütün kümeye aynı yönde etki edemez. API/model sözleşmesi sabittir,
yerel öğrenilmiş çıkarım ve indirme yoktur. Aynı n=30 geliştirme klipleri kullanıldığı
için sonuç final genelleme kanıtı değildir.
