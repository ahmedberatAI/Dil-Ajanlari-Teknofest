# Ön kayıt — SynthSite nesne-merkezli defter v5

**Tarih:** 2026-08-27  
**Durum:** v5 çıktıları görülmeden yazıldı; geliştirme ölçümüdür.

v4 precision %100/FPR %0 sağladı fakat recall %40'a indi. Gerçek pozitiflerin
çoğunda karar-yüklü `engel_derinlik_gozlemi` alanı çıplak `var` üretti ve hakem
bunu gerçek bariyer sanarak veto etti; üç JSON da sınırsız bilinmeyen listesi
yüzünden kesildi.

v5 algı isteminde tehlike/ihlal/güvenli/düşme bölgesi/altında/yanında sözcüklerini
yasaklar. `vlm` yalnız taşınan nesnenin ekran konumu ve teması, en yakın çalışanın
ekran konumu, arada görülen adlandırılmış nesneler ve zamansal değişimi kısa doğal
cümlelerle kaydeder. Alanlar uzunluk sınırlıdır. `llm-large` yalnız bu defteri
hakemler; çıplak `var/yok` açık karşı-kanıt sayılmaz. Sabit özel API/model sözleşmesi
ve v2 AND birleşimi korunur. Aynı n=30 küme kullanıldığından final holdout değildir.
