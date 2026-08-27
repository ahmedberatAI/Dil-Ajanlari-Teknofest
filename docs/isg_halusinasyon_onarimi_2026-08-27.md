# İSG halüsinasyon onarımı — 2026-08-27

## Amaç

Genel İSG olaylarında görüntü kanıtını aşan somut iddiaları azaltmak; bunu
gerçek yangın, düşme ve kaza duyarlılığını topluca susturmadan yapmak.

## Bulunan kök nedenler

1. Serbest olay algısı, yapılandırılmış çıktı başarısı için seçilmiş
   `llm-fast` modeline yönlenmişti. Bu iki görev aynı değildir; normal kliplerde
   yangın, düşme ve çarpışma iddiaları belirgin biçimde artıyordu.
2. Eski doğrulayıcı yalnız yüksek/kritik önem derecesine bakıyordu. Model somut
   bir olayı düşük/orta önemle yazınca iddia doğrulamadan geçebiliyordu.
3. Olay listesi kanıtlı olsa bile özet, risk ve aksiyon aşamaları yeni olay
   ekleyebiliyor veya olayların önemini aşabiliyordu.
4. Tesise/kameraya özgü üç varsayım genel İSG gerçeği gibi uygulanıyordu:
   yeşil yelek = yetki, sabit ROI koyuluğu = açık pano ve üç kasa = forklift
   aşırı yükü.

## Uygulanan yapısal onarımlar

- Serbest olay algısı `olay` görevine ayrıldı ve `llm-large` modeline
  yönlendirildi. Yapılandırılmış çıkarım/karar görevleri kendi uygun
  modellerinde bırakıldı.
- Sıcaklık olay algısı, çıkarım, özet ve aksiyon aşamalarında `0.0` yapıldı.
- Yangın/duman, düşme/yaralı, şiddet/silah, çarpışma/devrilme, yetkisiz
  erişim/müdahale ve KKD iddiaları önem derecesinden bağımsız olarak odaklı
  görsel doğrulamaya bağlandı. Yalnız açık `EVET/YES` kabul ediliyor;
  belirsizlik ve servis hatası iddiayı düşürüyor.
- Özet/aksiyonların olay listesinde olmayan kritik bir iddia ailesi eklemesi
  engellendi. Genel risk, doğrulanmış en yüksek olay önemini aşamıyor.
- Yeşil yelek-yetki, sabit pano ROI ve forklift kasa eşiği varsayılan kapalı,
  istek kapsamlı tesis beyanları oldu. Kapalı kuralın model slotu da gereksiz
  yere sorulmuyor.
- Arayüze üç ayrı, varsayılan kapalı tesis kalibrasyonu seçeneği eklendi.
- Ölçüm künyesine model yönlendirmesi ve bütün yeni koruma/beyan bayrakları
  eklendi.

## Kullanıcının bildirdiği klip

`data/_mislabeled_unsafe/eval_big_0_tr128.mp4`

Eski çıktı, görüntüyle ilgisiz biçimde “yetkisiz erişim”, “KKD eksikliği” ve
“hareketsiz yaralı kişi” iddia ediyordu.

Son gerçek model koşusu:

- olay sayısı: `0`
- risk: `Düşük`
- özet: `Videoda doğrulanmış yüksek öncelikli bir İSG veya güvenlik olayı tespit edilmedi.`

## Ölçümler

### 197 kliplik uyumluluk koşusu

Arşiv: `benchmark/results/eval_20260827_130900.json`

Bu koşu eski veri-kümesi tesis sözleşmesini karşılaştırabilmek için pano,
yelek-yetki ve forklift eşik kuralları etkin halde alınmıştır.

- anomali olayı yakalama: `86/99` (`%86,9`)
- yüksek/kritik risk: `84/99` (`%84,9`)
- kategori eşleşmesi: `83/99` (`%83,8`)
- normal kliplerde serbest anlatıdan gelen somut kritik iddia aileleri: `0`
- kaydedilmiş yüksek yanlış alarm: `51/98`; bunun baskın kaynağı açık tutulan
  tesis kurallarıdır (pano 23 satır, yelek-yetki 31 satır, forklift 2 satır).

Yeni genel varsayılanlar arşiv satırlarına mekanik olarak uygulandığında
(üç tesis kuralını kaldırıp risk tavanını kalan olaylara uygulama):

- yüksek yanlış alarm projeksiyonu: `0/98`
- operasyonel yanlış alarm projeksiyonu: `9/98`

Bu iki sayı yeni bir tam ileri geçiş değil, açıkça bir **projeksiyondur**.
Varsayılanların etkisi ayrıca aşağıdaki gerçek tek-klip koşularında doğrulandı.

### Pozitif kontrol: yangın + düşme

Arşiv: `benchmark/results/eval_20260827_131349.json`

- yangın: `10/10` yakalandı
- düşme: `13/15` yakalandı
- toplam kritik pozitif kontrol: `23/25` (`%92`)

Bu koşudaki 12 normal klibin tek yüksek yanlış alarmı, üç kasa eşik kuralıydı.
Kural tesis beyanına bağlandıktan sonra aynı `7_tr15.mp4` klibinin gerçek
yeniden koşusu `0 olay / Düşük risk` verdi. Buna göre son varsayılanın bu küçük
normal alt kümedeki mekanik sonucu `0/12` yüksek ve `5/12` operasyonel alarmdır.
Kalan beş olay düşük/orta önemlidir; “cihaz kullanımı” veya “ani hareket” gibi
görülebilir davranışlarla etiket-kümesi kapsamı arasındaki farkı ayırmak için
ayrıca olay-düzeyi insan etiketi gerekir.

## Regresyon doğrulaması

- Python derleme kontrolleri geçti.
- `tests/test_*.py` altındaki 43 test dosyasının tamamı geçti.
- Kural kapalıyken forklift slotunun istenmemesi ve üç kasanın otomatik ihlal
  sayılmaması birim testle kilitlendi.
- Arayüz yenilenerek `olay llm-large` yönlendirmesi ve üç varsayılan-kapalı
  tesis seçeneği DOM üzerinden doğrulandı.

## Sonraki ölçüm

En dürüst sonraki adım, 197 klibin tamamını son genel varsayılanlarla yeniden
ileri geçirmek ve yukarıdaki `0/98` ile `9/98` projeksiyonlarını gerçek ölçüme
çevirmektir. Bunun yanında iki kaçırılan düşme klibi ayrı hata analizi ister;
halüsinasyon azaltımı adına eşiği gevşetmek, ölçülmeden yapılmamalıdır.
