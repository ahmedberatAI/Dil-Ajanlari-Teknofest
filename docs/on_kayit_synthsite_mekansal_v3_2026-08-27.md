# Ön kayıt — SynthSite mekânsal karşı-kanıt v3

**Tarih:** 2026-08-27  
**Durum:** v3 çıktıları görülmeden yazıldı; geliştirme ölçümüdür.

Atomik v2 dengeli n=30 dilimde recall %93,3 fakat FPR %53,3 verdi. Sekiz FP'nin
tamamında iki atom da olumlu olduğu için kalan hata, düşme bölgesinin sahne
önselinden çıkarılmasıdır. Görsel denetimde baskın karşı örnekler: çalışan önde/
yan tarafta, farklı derinlikte, bariyer arkasında veya yükün destek üzerinde olması.

v3, etiketi/tam v2 cevabını görmeyen ayrı bir `vlm` oturumunda yalnız mekânsal
geometriyi ölçer. Dikey izdüşüm, çalışanın ayak noktası, derinlik ve fiziksel engel
kapalı seçeneklerdir. Metinsel few-shot'lar yalnız kural tanımı ve hard-negative
örnekleridir; video etiketleri isteme eklenmez. Nihai pozitif yalnız `v2=IHLAL_VAR`
ve `v3=DOGRUDAN_DUSUM_BOLGESI` birlikteyse üretilir.

Sabit model/API sözleşmesi değişmez; yerel öğrenilmiş çıkarım ve indirme yoktur.
Başarı kapıları v2 ile aynıdır. Aynı n=30 klipler tasarım için kullanıldığı için
olumlu sonuç bağımsız genelleme kanıtı sayılmaz.
