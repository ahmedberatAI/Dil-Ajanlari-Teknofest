# v13p izole KKD tesis-beyanı modülü — ön kayıt

Tarih: 2026-08-28

## Kapsam ve hipotez

Görüntüde bir ekipmanın görünmemesi, o ekipmanın tesiste zorunlu olduğu
anlamına gelmez. KKD anlatıları ancak operatörün tesis politikası/kurallarında
açık bir baret veya reflektif yelek zorunluluğu bulunduğunda ya da ilgili kit
`ppe_detection=true` ile bilerek etkinleştirildiğinde görsel kanıt kapısına
aday olabilir.

Bu iterasyon yalnız saf `dilajan/kkd_beyan.py` karar modülünü ve modelsiz
testlerini üretir. Agent graph'a bağlanmaz; üretim davranışı ve ölçümleri bu
iterasyonda değişmez.

## Önceden sabitlenen karar kuralları

- Desteklenen kitler yalnız `baret` ve `yelek`tir.
- `ppe_kits` varsayılan değeri, `ppe_detection=false` iken beyan değildir.
- `zorunlu değil/değildir`, `gerekli değil`, `zorunluluğu yok`, `isteğe bağlı`,
  `opsiyonel`, `aranmaz` ve eşdeğerleri olumsuz beyandır.
- Aynı kit için olumlu ve olumsuz kaynak çatışırsa olumsuzluk baskındır.
- Eldiven, gözlük, maske, kulak koruyucu, emniyet kemeri, ayakkabı veya yüz
  siperi geçen birleşik iddia bütünüyle fail-closed reddedilir.
- Desteklenen iki kit birlikte iddia ediliyorsa ikisi de açıkça beyanlı
  olmalıdır.
- Yalnız "KKD eksikliği" diyen fakat ekipmanı belirtmeyen iddia reddedilir.
- Modül görsel doğrulama yapmaz; kabul yalnız sonraki atomik görsel kapıya
  adaylık verir.
- Model değişimi/indirme, yerel öğrenilmiş çıkarım ve API çağrısı yoktur.
- `data/eval_genelleme_holdout_v13` bu iterasyonda ve kabul ölçümünden önce
  açılmaz.

## Modelsiz yapısal kapı

`tests/test_kkd_beyan.py` tek koşuda aşağıdakilerin tümünü geçmelidir:

1. Boş beyan + varsayılan kit listesi ret.
2. Açık baret/yelek zorunluluğu kabul.
3. Olumsuz veya çelişkili zorunluluk ret.
4. `ppe_detection=true` + destekli kit kabul; desteklenmeyen kit atlama.
5. Eldiven/gözlük/maske gibi birleşik iddia ret.
6. Birleşik baret+yelek iddiasında tüm kitler için beyan zorunluluğu.
7. Uyumlu görünüm ve ekipmanı belirtilmemiş genel KKD iddiası ret.
8. Karar izinde ham tesis politikası metni bulunmaması.

Herhangi bir yapısal test başarısızsa graph entegrasyonu ve veri ölçümü
yapılmaz.

## Entegrasyon sonrası eşlenmiş dev kabul kapısı

Bu modül daha sonra graph'a bağlanırsa tek bir önceden sabitlenmiş v13 dev
örneklemi üzerinde eski ve aday kollar aynı klipler, aynı sabit üç API modeli,
aynı örnekleme ve aynı değerlendirme koduyla karşılaştırılacaktır. Tek taraflı
kazanç kabul edilmez.

Zorunlu iki yönlü kapı:

- **Precision non-regression:** normal operasyonel FP sayısı aday kolda eski
  koldan büyük olamaz; hedef en az bir beyansız KKD FP'sinin silinmesidir.
- **Recall non-regression:** anomali TP/recall sayısı aday kolda eski koldan
  küçük olamaz. Özellikle beyanlı baret ve yelek pozitif kontrollerinin her biri
  korunmalıdır.
- Her iki koşul aynı koşuda sağlanmadıkça değişiklik kabul edilmez. FP azalırken
  tek bir TP kaybı veya recall korunurken tek bir yeni FP oluşması ret nedenidir.
- API/ayrıştırma hatası bulunan eşleşme kabul kanıtı sayılamaz ve koşu şans için
  tekrarlanmaz.
- Operasyonel FP, dispatch FP, TP ve FN ham sayıları raporlanır; yalnız yuvarlak
  oranlarla karar verilmez.

## Durdurma kuralı

Modelsiz kapı geçse dahi eşlenmiş dev ölçümünde precision ve recall
non-regression birlikte sağlanmazsa graph entegrasyonu geri alınır/etkinleştirilmez.
Holdout, başarısız kolu kurtarmak veya eşik seçmek için kullanılmaz.
