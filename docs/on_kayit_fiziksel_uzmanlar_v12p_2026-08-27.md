# Ön kayıt — v12p olay-sız fiziksel uzmanlar katmanı

Tarih: 2026-08-27  
Durum: Sonuç görülmeden kilitlendi

Kaynak yalnız `eval_20260827_213224.json` geliştirme sonucu ve iSafetyBench'in bu
geliştirme kliplerine ait doğru açıklamalarıdır. Donmuş holdout açılmaz.

Genellenebilir, doğrudan görülebilen dört fiziksel aile ölçülür:

- destek kaybından sonra yüksek kenar/borudan sarkan kişi,
- aracın/iş makinesinin kontrol kaybı, devrilmesi veya kenardan düşmesi,
- ağır yük düşmesi ya da yük nedeniyle vinç/taşıyıcı dengesizliği,
- karşılıklı sert fiziksel kavga.

Kapalı `llm-large` scout en fazla bir aile seçer; ardından o aile için `vlm` varlık/
geometri atomu ve `llm-large` zamansal/ilişkisel atomu ayrı çağrılarda deterministik
AND ile doğrulanır. Serbest nesir alarm olmaz. Katman yalnız mevcut uçtan uca sistem
olay üretmediyse çalışmaya adaydır.

Pozitif geliştirme örnekleri (6):

- `0RcFgtZFhgg_clip0_trim_2.mp4` — fiziksel kavga,
- `0W6vtPakFt8_trim_2.mp4` — araç içi şiddetli kontrol kaybı/kaza,
- `1s2Tcqr3Rgg_trim_126.mp4` — yük altında vinç dengesizliği,
- `87O1pBSGtR0_trim_24.mp4` — forkliftten düşen yük,
- `aTW27C3AG-o_trim_147.mp4` — destek kaybı sonrası borudan sarkan kişi,
- `aTW27C3AG-o_trim_55.mp4` — kontrolsüz yol silindiri kenardan düşmesi.

Negatifler: v12o'da doğru negatif kalan 48 normal klip.

Kabul: en az 3/6 geri kazanım, 0/48 yeni FP, 0 API hatası. Geçilirse bayrak
arkasında mimariye bağlanır ve yeni tam 50+50 aday ön kaydı yapılır; geçilmezse
uzmanlar üretime bağlanmaz.
