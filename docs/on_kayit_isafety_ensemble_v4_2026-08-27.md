# Ön kayıt — iSafety seçici sabit-model ensemble v4

**Tarih:** 2026-08-27  
**Durum:** v4 çıktıları görülmeden yazıldı; geliştirme ölçümüdür.

Aynı 40 klipte doğrudan `llm-large` 20/40, betimleme zinciri 18/40 ve doğrudan
`vlm` 20/40'tır. `llm-large` ile `vlm` birbirinin dörder hatasını düzeltir; üç kol
oracle 26/40'tır. Oracle sevk yöntemi değildir.

v4 yalnız aday harfler ayrıştığında `llm-fast`e nötr VLM betimi, tüm seçenek
metinleri ve benzersiz aday harfleri verir. Hakem çoğunluk oyu yapamaz ve aday
dışı harf üretemez. Tüm kollar aynıysa çağrı yoktur. Doğrudan `llm-large` tabanına
karşı satır-eşli accuracy farkı ve exact McNemar raporlanır. Başarı için toplam
accuracy artmalı, coverage düşmemeli ve hazard/normal kollarından hiçbiri 5 puandan
fazla gerilememelidir. Aynı geliştirme klipleri kullanıldığı için final kanıt değildir.
