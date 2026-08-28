# Ön kayıt — NVIDIA depo İSG düzeltme geliştirme ölçümü

Tarih: 2026-08-27  
Kaynak revizyonu: `d5b88d3abcf659f304a107f4336b71b4e2159133`  
Görünürlük kaydı: `benchmark/nvidia_sdg_dev_visibility.json`

## Amaç ve veri ayrımı

Bu koşum, ilk 5 run/senaryo ile yapılan ve `RED` çıkan audit koşumundan
bağımsız bir **geliştirme** ölçümüdür. Aynı shard'ların tar sırasındaki 5 run'ı
atlanmış, sonraki 2 run/senaryo ve bu run'lardaki bütün RGB kameralar seçilmiştir.

- 8 bağımsız run
- 62 kamera videosu
- 20 ramak-kala, 12 forklift-raf çarpışması, 10 yangın, 20 rutin kutu alma
- Model çıktısı bu etiketler ve eşikler dondurulmadan çalıştırılmayacaktır.

## Kamera-bazlı görünürlük

Senaryo adı her kamerada olayın göründüğü anlamına gelmez. Beklenen pozitif,
model cevabından önce kaynak videoların elle incelenmesiyle kamera bazında
sabitlendi.

İlk incelemede 1 FPS temas sayfaları 320 piksel/kareye küçültülmüştü ve duman
yanlışlıkla görünmez sayıldı. Kullanıcı uyarısından sonra, **henüz model koşumu
yapılmadan**, bu ara not geçersiz kılındı. 1920×1080 kaynak kareler ve 3×3
zamansal temas sayfaları yeniden incelendi; iki yangın run'ında toplam 8/10
kamerada hareketli siyah/gri duman görünür olarak etiketlendi. Bu düzeltme
sonuç-sonrası etiket değişikliği değildir; eski düşük çözünürlüklü not hiçbir
model skorunda kullanılmadı.

Donmuş görünür pozitifler:

- Görünür duman/yangın: 8 kamera, 2 run
- Forklift-raf/sabit ekipman çarpışması: 6 kamera, 1 run
- Forklift-insan ramak kala: 20 kamera, 2 run
- Rutin kutu alma: 20 kamera; üç olay ailesinin tamamı için negatif

İkinci çarpışma run'ında forklift görünmesine rağmen açık fiziksel temas/hedef
hareketi görünmediği için o 6 kamera çarpışma pozitifi sayılmadı. Yangında dumanın
rafla tamamen kapandığı 2 kamera da pozitif paydaya alınmadı; bunlarda yanlış
yangın kodu negatif olarak puanlanır.

## Ölçülen sistem

Eski tesise özel yelek-yetki, pano, üç-kasa ve yaya yolu kuralları kapalıdır.
Yalnız şu genel depo slotları açıktır:

- `depo_gorunur_yangin`
- `depo_forklift_raf_carpisma`
- `depo_forklift_kisi_tehlike`

Her slot kapalı `VAR/YOK/GORUNMUYOR` cevap uzayı kullanır. Model yalnız gözlemi
doldurur; olay adı, kategori ve önem derecesi deterministik kural motorundan
gelir. Üç genel depo slotu, küçük/ince görsel kanıt kaybını önlemek için kaynak
1080p videoyu 1920 uzun kenarla ortak tek video oturumunda kullanır. Serbest
anlatı yolu ayrıca çalışmaya devam eder.

Normal videolardaki `Düşük` önem etiketi artık “düşme” iddiası sayılmaz. Buna
karşılık “yerde sürünme, emekleme, panik, denge kaybı” gibi somut kişi-hareketi
iddiaları önem seviyesinden bağımsız olarak görsel doğrulamaya girer; açık kanıt
yoksa olay tamamen silinir.

## Donmuş puanlama ve geliştirme eşikleri

Kapalı gözlem olayı serbest metin anahtar sözcüğüyle değil, arşivdeki birebir
`isg_kod` ile puanlanır:

- `Warehouse_Visible_Fire`
- `Forklift_Shelf_Collision`
- `Forklift_Human_NearMiss`

Eşikler:

- Görünür pozitif örneği olan her olay kodunda görüş recall'u en az `%80`.
- Her görünür pozitif run'da uygun kameraların en az yarısı doğru kodu üretir.
- Her kodun kendi negatif kameralarındaki yanlış-pozitif oranı en fazla `%5`.
- 20 rutin kutu videosunda yüksek/kritik yanlış alarm en fazla `1/20`.
- Rutin kutuda herhangi olay/fonksiyon tetikleme en fazla `2/20`.
- Rutin kutuda yanlış operasyon sevki `0/20`.
- Rutin kutuda somut kritik iddia ailesi en fazla `1/20`.

Wilson `%95` aralıkları, ham `k/n` sayımları ve her kamera sonucu saklanacaktır.
Bu geliştirme kümesidir; eşik geçilse bile nihai genelleme iddiası kurulmaz.
Kod/prompt bu sonuçtan sonra ayarlanırsa aynı sonuç nihai audit diye sunulmaz;
farklı run kimlikleriyle tek seferlik ayrı holdout gerekir.

