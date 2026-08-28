# Ön kayıt — iSafety eşleştirilmiş doğrudan VLM kolu v3

**Tarih:** 2026-08-27  
**Durum:** v3 çıktıları görülmeden yazıldı; geliştirme ölçümüdür.

Satır-bazlı v2'de doğrudan `llm-large` 20/40 (%50), `vlm` betimleme →
`llm-large` sınıflama 18/40 (%45) verdi; fark −5 puan, McNemar p=0,754.
Cascade üretime alınmaz. Aynı sabit model sözleşmesinde son bağımsız karşılaştırma,
`vlm`nin aynı 40 videoyu doğrudan kapalı MCQ ile yanıtlamasıdır.

Video/şık sırası/GT/prompt v2 ile aynıdır; yalnız rol `algi=vlm` olur. Satır bazlı
ham tahmin/hata saklanır. `llm-large` doğrudan kola karşı exact McNemar ve üç kolun
yalnız tanısal oracle tavanı raporlanır. Oracle üretim yöntemi değildir; yalnız hata
tamamlayıcılığını gösterir. Özel API, yerel model yasağı ve sabit aliaslar korunur.
