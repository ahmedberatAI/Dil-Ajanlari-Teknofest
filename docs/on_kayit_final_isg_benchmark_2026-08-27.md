# Ön kayıt — final İSG benchmarkı (tesis ön-kurallı)

Tarih: 2026-08-27  
Kod: `4e9c3a3`  
Durum: Sonuç görülmeden yazılan ölçüm protokolü

## Neden yeni ön kayıt

`benchmark/results/eval_20260827_133724.json`, genel varsayılanlarla yapılan
bir keşif koşusudur. Eski `eval_defense` etiketleri tesis sözleşmesi gerektiren
pano, yelek/yetki, kasa eşiği ve yaya yolu sınıflarını içerdiği halde bu
kurallar kapalıydı. Bu nedenle o koşunun tek anomali-recall sayısı nihai kanıt
olarak kullanılmayacaktır.

Bu belge, tesis ön-kuralları açık ölçümün konfigürasyonunu ve başarı
ölçütlerini sonuç görülmeden kilitler. Aynı veri daha önce geliştirme sırasında
görüldüğü için deney bağımsız bir gizli-test iddiası taşımaz; amacı post-hoc
eşik seçimini engelleyen tekrarlanabilir bir son durum ölçümüdür.

## Kilitli veri ve koşum

- Veri: `data/eval_defense`
- Kapsam: 99 güvensiz + 98 güvenli = 197 benzersiz klip
- MD5 mükerrer eleme: açık
- İşçi: 4
- Olay modeli: `llm-large`
- Sıcaklık: `0.0`
- İddia doğrulama, özet-kanıt koruması ve risk-olay tavanı: açık
- Koşu tek sefer yapılacak; sonuçtan sonra eşik/model/prompt değiştirilip aynı
  raporun üzerine yazılmayacak.

Çalıştırılacak komut:

```bash
DILAJAN_EVAL_DIR=data/eval_defense \
EVAL_ISCI=4 \
DILAJAN_ISG_SLOTLARI='*' \
DILAJAN_YELEK_YETKI_KURALI=1 \
DILAJAN_PANEL_KOYULUK_KURALI=1 \
DILAJAN_FORKLIFT_KASA_KURALI=1 \
python benchmark/eval_clips.py
```

## Sonuçtan önce kilitlenen tesis ön-kuralları

1. Forklift: `çatal_kasa_sayisi >= 3` ise aşırı yük.
2. Pano: kalibre sabit ROI'de `pano_koyuluk_0_10 >= 6` ise açık pano.
3. Yetki: makine başında en az bir kişi varken reflektif yelek yoksa, bu
   tesiste yetkisiz müdahale.
4. Yaya yolu: kalibre alt-yarım ROI'de çizgi mesafesi `< 7` veya yerel zemin
   kuralı ihlalse yaya yolu olayı.
5. Alan/görüş kilidi ve kodlama normalizasyonu `.env` içindeki mevcut sabit
   değerleriyle korunur; sonuçtan sonra değiştirilmez.

Bu kurallar **genel dünya bilgisi değildir**. Ölçüm yalnız bu veri kümesinin
tesis sözleşmesini sınar; genel UI varsayılanlarının kapalı kalması bu koşulla
çelişmez.

## Önceden belirlenen birincil ölçüler

Tek toplam recall yerine aşağıdaki ölçüler birlikte raporlanacak:

1. Her dört güvensiz sınıfta exact TPR ve güvenli eşinde exact FPR.
2. Her eşlenmiş sınıf için MCC.
3. 98 normal klipte yüksek/kritik yanlış alarm oranı.
4. 98 normal klipte operasyonel olay ve yanlış fonksiyon tetikleme oranı.
5. Normal kliplerde serbest anlatı kaynaklı somut iddia aileleri:
   yangın/duman, düşme/yaralı, şiddet/silah, çarpışma/devrilme,
   yetkisiz erişim ve KKD.
6. Anomali olayı, yüksek risk ve kategori eşleşmesi ikincil özet olarak
   verilecek; tek başına başarı kanıtı sayılmayacak.

## Önceden belirlenen kabul / ret kuralları

Bir sınıf kolu ancak aşağıdakilerin hepsini sağlarsa `KABUL`:

- exact TPR en az `%80` (25 örnekte en az 20; pano için 24 örnekte en az 20),
- exact FPR en fazla `%10` (yaklaşık en çok 2/25),
- MCC en az `+0.60`.

Sistemin tesis-ön-kurallı bütünü ancak aşağıdakilerin hepsini sağlarsa
`KABUL`:

- normal yüksek/kritik yanlış alarm en fazla `%10`,
- normal yanlış operasyon tetiklemesi en fazla `%5`,
- normal serbest anlatıda doğrulanmamış somut kritik iddia ailesi `0`.

Bir koşulun kaçması diğer başarılı sayılarla ortalanmayacak; ilgili kol veya
bütün açıkça `RED` yazılacak. Wilson `%95` güven aralıkları ham `k/n` ile
birlikte verilecek.

## Geliştirme örneği ayrımı

`data/_mislabeled_unsafe/eval_big_0_tr128.mp4` hata ayıklamada kullanıldığı
için doğrulama metriğine eklenmeyecek. Yalnız regresyon/sentinel sonucu olarak
ayrı raporlanabilir.

## Sonuç

Bu bölüm koşu tamamlandıktan sonra yalnız sonuç eklemek için doldurulacaktır;
yukarıdaki protokol ve eşikler değiştirilmemelidir.
