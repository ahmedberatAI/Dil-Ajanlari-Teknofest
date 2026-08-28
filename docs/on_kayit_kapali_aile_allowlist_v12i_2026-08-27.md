# Ön kayıt — v12i kanıtlanmış aile allowlist'i

Tarih: 2026-08-27  
Durum: Sonuç görülmeden kilitlendi

v12g düzeltme sonrası 8/17 tehlikeyi geri kazandı, fakat 1/43 yeni FP üreten tek
aile `MAKINE_SIKISMA` idi. v12h ek geometri kapısı bu FP'yi kesemedi ve geri alındı.

Bu aday ana mimariden makine sıkışmasını kaldırmaz. Yalnız **olay-sız fallback
tarayıcısının** kapalı seçim uzayından kanıtlanmamış `MAKINE_SIKISMA` seçeneğini
çıkarır. Açık-uçlu algıdaki mevcut makine olayları ve atomik muhafız değişmez.

Örneklem yine v11 sonunda olay-sız 17 tehlike + 43 normaldir. Yöntem, roller,
atomik spekler ve çıktı bütçesi v12g düzeltilmiş koşusuyla aynıdır.

Kabul:

- en az 5/17 tehlike geri kazanımı,
- 0/43 yeni FP,
- 0 API hatası.

Geçilirse aynı allowlist özellik bayrağıyla entegre edilir ve tam 50+50 geliştirme
koşusu ön kaydedilir. Geçilmezse üretime alınmaz. Holdout açılmaz.

