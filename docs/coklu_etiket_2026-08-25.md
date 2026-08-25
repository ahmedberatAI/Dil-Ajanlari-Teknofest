# Çapraz ateşlemeler gerçekten yanlış mı? — ölçüldü

Tarih: 2026-08-25 · Yöntem: tohumlu rastgele örnek + **gözle etiketleme**

## Sorun

Her kural, kendi ihlal sınıfı **dışındaki** kliplerde de ateşliyor. O
kliplerde ilgili eksende **etiket yoktur**, dolayısıyla ateşlemenin yanlış
olduğu kanıtlanamaz — ama doğru olduğu da kanıtlanmamıştı. Bu, projenin en
büyük açık sorusuydu: raporlanan "saha kesinliği" gerçek mi?

## Yöntem

Her kural için, kendi ihlal sınıfı dışında ateşlediği kliplerden **tohumlu**
(seed 2026) rastgele 12 örnek çekildi; örnek sonuç görülmeden **önce**
sabitlendi. Kareler çıkarılıp montaj hâline getirildi ve **gözle** etiketlendi.

**Model yeniden sorulmadı** — dairesel olurdu.

## Bulgu

| kural | soru | sonuç |
|---|---|---|
| yelek | Makine yakınında yeşil yeleksiz bir kişi **var mı**? | **12/12 VAR** |
| pano | Makinenin sol-alt bölgesinde **açık/koyu pano boşluğu var mı**? | **12/12 VAR** |

Wilson %95 alt sınırı (12/12 için): **0,739**.

İki karede küçük ölçekte şüphe oluştu; tam boyutta bakıldığında ikisi de
doğrulandı — birinde makinenin başında **iki** koyu tulumlu kişi, diğerinde
merkezde yeleksiz bir kişi.

### Tutarlılık kontrolü
Pano ateşlemelerinin çoğu `Unauthorized_Intervention` kliplerinde. Bu
beklenen bir şey: **birine müdahale etmek için pano açılır.** İki tehlike
gerçekten birlikte oluşuyor; veri seti klip başına yalnız birini etiketliyor.

## Düzeltilmiş saha kesinliği

| kural | ateşliyor | kendi çifti | çapraz | ham | **düzeltilmiş** |
|---|---|---|---|---|---|
| yelek | 80 | 19 | 59 | 0,237 | **0,975** [alt sınır 0,796] |
| pano | 59 | 23 | 36 | 0,390 | **1,000** [alt sınır 0,852] |
| forklift | 26 | 24 | 0 | 0,923 | — (çapraz ateşleme yok) |

Alt sınır, örneklem oranının Wilson alt sınırı (0,739) kullanılarak hesaplandı;
yani "en kötü makul durumda" bile kesinlik 0,80–0,85 aralığında.

## Bunun anlamı

Standart değerlendirmedeki **%60 normal yanlış alarm oranı, sistemin hata
oranı değildir.** Kamera 9'un dört sınıfı aynı fiziksel sahnedir ve klipler
tek etiketlidir; sistem gördüğü tüm tehlikeleri raporlar, kıyas kümesi klip
başına yalnız birini kabul eder.

## Çekince — bilerek bırakılıyor

Bu, **tek kareye bakılarak** verilmiş insan hükmüdür. Yelek örtülü olabilir;
uzaktaki figürler için "makinenin başında" bir yorum meselesidir. Bu yüzden
nokta tahmininin yanında **alt sınır** da veriliyor ve sonuç "kesin doğruluk"
değil, "çapraz ateşlemelerin büyük çoğunluğu gerçek tehlikedir" biçiminde
ifade edilmelidir.

Kesin cevap için tesise özgü **çoklu etiketli** doğrulama gerekir (n=197'nin
tamamı, üç eksende). Bu örneklem (n=24) o çalışmanın yerini tutmaz ama
sorunun yönünü kesinleştirir.
