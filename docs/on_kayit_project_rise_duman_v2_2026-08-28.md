# Ön kayıt — Project RISE duman mimarisi v2

Tarih: 2026-08-28  
Durum: Model çıkarımından önce kilitlendi

## Amaç

Donmuş ilk Project RISE sonucunda gözlenen üç kusuru birlikte düzeltmek:

1. Depoya özgü `Warehouse_Visible_Fire` hükmünün uzak endüstriyel bacaya taşması.
2. Atomik hakem `REFUTED` dediği halde olayın yalnız tek bir özel etiket dışında korunması.
3. Görünür duman/plüm gözleminin doğrudan `Kritik` ve operasyonel sevke dönüşmesi.

İlk 56 kliplik `camera=0, view=0, 2019-02-02` sonucu dondurulmuştur ve ayar
verisi olarak yeniden kullanılmayacaktır.

## Veri bölmeleri

Resmî Project RISE metadata snapshot'ı:

- kaynak commit: `e796bf36988226b8bc657872bdc83c6cbad791cd`
- metadata SHA256: `cc85ad6db07557ae4afacc4f12f443b6e68ae0d88e30869fcf031f4c7dc7ee18`
- yalnız güçlü araştırmacı etiketleri: `23=duman`, `16=duman yok`

Geliştirme:

- `camera=0`, `view=5`, `2018-06-11`
- ham: 33 duman, 51 duman yok
- sabit nicelik örneklemesi: 33 + 33
- seçim SHA256: `efba09b5213f2ad054af96aad25392558e99c830d424fde40c7592077dfbd82a`

Kilitli doğrulama:

- `camera=2`, `view=0`, `2018-06-12`
- ham: 27 duman, 23 duman yok
- sabit nicelik örneklemesi: 23 + 23
- seçim SHA256: `08ec161fdfdfc5eb1854e2cd63903a9e0abfdad22e16247ad168796ea57cb485`
- geliştirme bitmeden çalıştırılmayacak; sonuç görüldükten sonra ayar yapılmayacak

Her sınıfta kayıtlar `(start_time, id)` ile sıralanır. Sınıf hedef sayıdan
büyükse `round(i*(N-1)/(target-1))` indeksleri alınır. Model çıktısına bağlı
örnek seçimi yoktur.

## Sabit model/API sözleşmesi

- Görsel algı: `vlm`
- Zamansal olay hakemi: `llm-large`
- Yapı/özet/karar desteği: `llm-fast`
- Tüm öğrenilebilir çıkarım yalnız özel Evren API üzerinden
- Yerel öğrenilmiş çıkarım ve model indirme kapalı
- Modeller değiştirilmeyecek; yalnız kullanım mimarisi değişebilir

## Önceden belirlenmiş mimari

1. Geniş aday ölçümü, depoyu varsaymadan görünür ve biçim değiştiren bir
   endüstriyel plüm/duman oluşumunu kapalı cevap uzayında ölçer.
2. İkinci görsel ölçüm, oluşumun en az birkaç ardışık anda aynı fiziksel
   kaynaktan çıkıp çıkmadığını sınar.
3. Zamansal hakem, plümün endüstriyel kaynağa bağlı yükselme/yayılmasını;
   atmosferik bulut/sis, sabit parlaklık/gölge ve kısa toz/buhar jetinden ayırır.
4. Üç bağımsız kanaldan en az ikisi destekliyorsa yalnız bir
   `Industrial_Visible_Plume` gözlem olayı üretilir. Açık çürütme artık
   “yangını koru” olarak yorumlanmaz.
5. Gözlem olayı `Orta`, otomatik sevke kapalı ve “madde türü/acil durum statüsü
   görüntüden kesinleştirilmedi” ibaresiyle sunulur.
6. `Kritik` yangın ve sevk yalnız ayrı akut kanıt kapısıyla açılır: açık alev
   veya hızla büyüyen yoğun/koyu dumanla birlikte doğrudan acil durum belirtisi.
   İnsan hareketi yalnız yardımcı kanıttır; duman tespitinin ön koşulu değildir.
7. Yapılandırılmış duman gözlemi genel `reexamine` düğümünde rutin/ciddi diye
   yeniden yükseltilemez. Dispatch hesabı `dispatch_eligible=False` işaretli
   olayları hem olay-severity hem risk geri besleme yolundan çıkarır.

## Geliştirme kuralı ve ölçütler

Geliştirme setinde en fazla iki tam ileri koşu yapılacaktır:

1. mevcut mimari tabanı,
2. önceden belirlenmiş v2 mimarisi.

İkinci koşudan sonra yalnız kod/test hatası varsa aynı karar kuralıyla tekrar
koşulabilir; metrik görerek eşik araması yapılmayacaktır.

Birincil metrikler:

- smoke recall
- smoke false-positive rate
- precision, F1, MCC, balanced accuracy
- operasyonel FP, yüksek-risk FP, dispatch FP
- API/ayrıştırma hatası ve kapsama

Başarı yorumu tek sayıya indirgenmeyecektir. Hedef sıralaması:

1. Duman gözleminin otomatik `Kritik+dispatch` üretmesini yapısal olarak sıfırlamak.
2. Açık çürütmelerin olay olarak kalmasını sıfırlamak.
3. Geliştirme ve görülmemiş doğrulamada recall/precision dengesini ilk donmuş
   sonuçtan anlamlı biçimde iyileştirmek.

