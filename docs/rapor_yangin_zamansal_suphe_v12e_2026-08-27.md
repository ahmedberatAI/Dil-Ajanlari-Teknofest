# Sonuç — v12e zamansal yangın şüphesi kolu

Tarih: 2026-08-27  
Hüküm: **Reddedildi; üretime alınmadı**

Sonuç dosyası:
`benchmark/results/yangin_zamansal_suphe_v12e_20260827_203249.json`

İlk görsel kapı 63 klibin 7'sinde `YENI_ISIK_BULUT` seçti: 5 gerçek yangın ve
2 normal. Bu beş gerçek yangının hiçbiri v11'in kaçırdığı iki yangın klibi değildi;
dolayısıyla ön kayıttaki “en az bir kaçırmayı geri kazan” ölçütü daha ikinci role
bakılmadan matematiksel olarak başarısız oldu.

İkinci rolün uzun etiketi `max_tokens=12` nedeniyle dört yanıtta
`KAYNAKLA_BAGLANTILI_TEP` biçiminde kesildi. Bu nedenle sonuç JSON'undaki 0/13
birleşik recall, geçerli bir birleşik performans tahmini değildir. Bununla birlikte
ilk kapı iki hedef kaçırmayı da seçmediğinden kabul hükmü değişemez; etiketi uzatıp
aynı kol yeniden koşulmadı.

Normalde yeni ışık/bulut seçilen iki klipten biri zaten v11 yangın FP'siydi; diğeri
de yapılandırılmış yangın FP'siydi. Eşiği gevşetmek mevcut toz/buhar hatalarını
yeniden açacağından bu kol ana mimariye eklenmedi.

