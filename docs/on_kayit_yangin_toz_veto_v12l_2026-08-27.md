# Ön kayıt — v12l yapılandırılmış yangında asimetrik toz/buhar vetosu

Tarih: 2026-08-27  
Durum: Sonuç görülmeden kilitlendi

Katı v12 yangın AND kapısı 15/15 negatif öneriyi kesti fakat yalnız 7/11 gerçek
yangını tuttuğu için reddedilmişti. Bu aday yangını yeniden “kanıtlama” şartı
getirmez. Yalnız `llm-large` zamansal atomu açık alternatif açıklama olarak tam
`BUHAR_TOZ_PARLAMA` seçerse yapılandırılmış `Warehouse_Visible_Fire` olayı veto
edilir. `BELIRTI_YOK`, `GORUNMUYOR`, hata ve diğer cevaplarda olay korunur.

Örneklem v11'de yapılandırılmış yangın önerisi bulunan aynı 11 gerçek yangın + 15
negatif kliptir. `vlm` görünür belirti atomu iz için yine çalışır; hükmü yalnız açık
toz/buhar etiketi verir. Modeller ve özel API değişmez.

Kabul:

- gerçek yangınlardan en az 10/11 korunmalı,
- negatif önerilerden en az 10/15 veto edilmeli,
- API hatası 0.

Geçilirse özellik bayrağıyla yalnız yapılandırılmış yangın olaylarına entegre edilir;
v12i fallback açık tam 50+50 koşusu yeniden ön kaydedilir. Holdout açılmaz.

