# ÖN KAYIT — yelek kuralı "eksik yelek sayımı" kolu (koşumdan ÖNCE yazıldı)

## Tanı (gözle doğrulandı, 8 ölçülebilir hata incelendi)
Yelek kuralının 6 kaçırması İKİ ayrı sebebe ayrılıyor:

  A) 3 klip — FARKLI KAMERA GÖRÜŞÜ (geniş plan, makine uzakta).
     `makine_basinda_kisi = 0` → kapı kapanıyor. Kapı DOĞRU davranıyor;
     o ölçekte panonun başında kimse seçilemiyor. Bu kolla ÇÖZÜLEMEZ.
  B) 3 klip — makinenin başında 3 KİŞİ var, model "yelek VAR" diyor.
     Görsel doğrulama: 1_tr61'de yelek gerçekten görünüyor. Model YANILMIYOR;
     soru çok kişili sahnede BELİRSİZ: biri yelekliyse "VAR" doğru oluyor,
     ama yeleksiz olan kişi için ihlal duruyor.

## Denenen kol
Mevcut : kisi >= 1  VE  yelek == "YOK"
Yeni   : kisi >= 1  VE  yelekli_kisi < kisi        (biri bile yeleksizse ihlal)

`yelekli_kisi` = "Goruntude yesil reflektif yelek GIYEN kac kisi var?"
Bu soru daha önce TEK BAŞINA ölçüldü (D45 C kolu): MCC +0,788 — mevcut
ikili soruyla aynı. Buradaki iddia farklı: iki sayımın FARKI, tek başına
hiçbirinin taşımadığı bilgiyi taşır.

## Kabul ölçütü (SONUÇTAN ÖNCE sabitlendi)
Yeni kol, Unauthorized_Intervention çiftinde MCC'yi **+0,689'dan en az
+0,75'e** çıkarmalı VE yanlış pozitif sayısı **4'ü geçmemeli** (şu an 2).
Aksi halde MEVCUT KURAL KALIR.

Ulaşılabilir tavan: 25 ihlalin 3'ü (A grubu) bu kolla kurtarılamaz → en fazla
TP 22. Yani +0,75 hedefi gerçekçi ama garanti değil.

Sonuç ne olursa olsun raporlanır; iki kol da arşivlenir.
