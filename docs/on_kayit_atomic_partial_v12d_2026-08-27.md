# Ön kayıt — v12d yalnız parçalı atom koruma

Tarih: 2026-08-27  
Durum: Sonuç görülmeden kilitlendi

v12c birleşik adayı recall %62 ile reddedildi. Eşlenmiş hata farkında iki
kanıtlı karma olay geri gelirken dört eski tehlike olayı kayboldu; kayıplar yeni
yük/çökme taksonomisinin eski geniş aileyi değiştirmesiyle ilişkiliydi.

Bu aday yalnız kanıtlanmış yazılım düzeltmesini açar:

- bir cümlede bazı aileler destekli, bazıları reddedilmişse yalnız destekli
  aile sabit şablonla korunur,
- yeni `kontrolsüz yük/çökme` ve `makineye sıkışma/ezilme` aileleri kapalıdır,
- diğer tüm üretim ayarları v11 ile aynıdır.

Geliştirme seti yine `data/eval_genelleme` 50+50'dir. Kabul: recall en az
35/50 (%70), normal operasyonel FP en fazla 7/50 (%14), MCC en az +0,56,
kapsam 100/100 ve hata 0. Geçmezse varsayılan açılmaz; holdout açılmaz.

