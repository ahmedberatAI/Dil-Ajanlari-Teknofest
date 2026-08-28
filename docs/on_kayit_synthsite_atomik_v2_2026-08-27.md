# Ön kayıt — SynthSite atomik v2 geliştirme ölçümü

**Tarih:** 2026-08-27  
**Durum:** v2 model çıktıları görülmeden yazıldı; sonuçtan sonra değiştirilmez.

## Amaç ve dürüstlük sınırı

Eski Tier-1 koşusunda tek istem üç fiziksel koşulu birlikte sordu ve TP=17,
FP=12, TN=62, FN=59 üretti. Bu v2, hangi koşulun bozulduğunu görünür kılmak
için kararı iki atomik ölçüme ayırır. Tier-1 kliplerinin önceki sonuçları görüldüğü
için bu çalışma **geliştirme ölçümüdür; bağımsız final holdout değildir**.

## Dondurulmuş mimari

1. `vlm`: yük gerçekten kanca/sapan/zincirle havada asılı mı?
2. `llm-large`: çalışan düşme/salınım bölgesinde kesintisiz en az 1 saniye mi?
3. Yalnız iki atom da açık destekse `IHLAL_VAR`; açık çürütme varsa
   `IHLAL_YOK`; belirsizlikte `GORUNMUYOR`; servis hatası `error`.

İki çağrı ayrı istemci/oturum kullanır, önceki yanıtı hatırlamaz, sıcaklık 0'dır
ve cevap uzayları kapalıdır. Etiket istemlere verilmez. `llm-fast` yapı/özet
aliası sözleşmede sabit kalır fakat bu iki görsel ölçümde çağrılmaz.

## Veri ve seçim

- `govtech/SynthSite`, revizyon
  `2904ec01c3dbf2efba09f2cb1b7bdf17841d4d39`
- Yalnız insan değerlendiricilerin tam uzlaşılı Tier-1 etiketi.
- Hızlı geliştirme dilimi kullanılırsa unsafe/safe dengeli ve dosya adı
  SHA-256 sırasıyla deterministik seçilir.
- Her videonun, etiket CSV'sinin, sistem isteminin ve atom istemlerinin SHA-256'sı
  sonuç arşivinde saklanır.

## Sabit çıkarım sözleşmesi

- Yalnız `https://evren-llmapi.ssyz.org.tr/v1`
- `algi=vlm`, `olay=llm-large`, `yapi=llm-fast`, `ozet=llm-fast`
- Yerel öğrenilmiş model ve model indirme yoktur.

## Metrikler ve yorum

Eski dondurulmuş kapılar değişmez: recall/precision/strict accuracy ≥0,90,
FPR ≤0,10, coverage ≥0,90. Geliştirme diliminin geçmesi üretim kabulü değildir;
yalnız tüm 150 üzerinde doğrulama ve daha sonra yeni, görülmemiş insan-etiketli
holdout bu iddiayı destekleyebilir. Atom cevap dağılımları ayrıca kök neden olarak
raporlanacaktır.
