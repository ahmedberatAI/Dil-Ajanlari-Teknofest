# Jüri soru–cevap hazırlığı

Tarih: 2026-08-25 · TEKNOFEST TYDA 3. Senaryo · VigilantAI (team44)

Her cevap **ölçülmüş bir sayıya** dayanır. Sayıyı hatırlamıyorsanız
"ölçtük, raporda var" demek, uydurmaktan iyidir.

---

## 1. "Şartname yerel çalışma diyordu, siz bulut API kullanıyorsunuz."

Proje tamamen yerel tasarlandı ve **hâlâ yerel çalışabiliyor** (`.env.yerel`
ile tek komutta geçilir). 21 Ağustos 2026'da yarışma düzenleyicisi 8×H200'lük
ortak bir çıkarım servisi tahsis etti ve offline şartı kaldırıldı; biz de
tahsis edilen kaynağı kullanıyoruz.

Ek olarak: **yerel GPU kullanımı kod düzeyinde yasaklandı**
(`config.yerel_cihaz()`), çünkü tahsis edilen kaynak uzak servistir.
`dilajan/` içinde sabit `cuda` referansı kalmadığını bir test doğruluyor.

## 2. "Bu statik bir kural sistemi değil mi? Şartname kural tabanlıyı düşük puanlıyor."

Hayır — ve ayrım önemli. **Model ölçer, kural karar verir.**

- Model, kapalı cevap uzayında bir soruya cevap verir: *"çatalda kaç kasa var?"*
  → `3`. Bu bir **algı** işidir ve modelsiz yapılamaz.
- Kural motoru o sayıyı tesis konvansiyonuyla karşılaştırır (≥3 → ihlal).

Bunu neden yaptığımızı **ölçtük**: serbest metinle çalışan önceki mimari
20 güvensiz klibin **20'sini birden** kaçırıyordu (0/20). Kayıp zinciri:
betimleme ihlali iddia etti 0/20 → nesneyi andı 7/20 → bilgi zorla verilse
olaya geçen 11/20 → eşleştiricinin yakaladığı 4/11.

Aynı model, **işlemsel** soru sorulduğunda 20/20 doğru karar veriyordu.
Yani darboğaz model değil, mimariydi.

Ayrıca sistemin **anlatı düzlemi** tamamen model tabanlıdır ve açık dünya
tehlikelerini (yangın, devrilme, düşme) serbest metinle raporlar — yabancı
veri setinde tehlike kliplerinin %97'sinde olay üretti.

## 3. "Skorlarınız gerçekten görüntüden mi geliyor? Veri sızıntısı olabilir mi?"

Bunu biz de sorduk ve **ölçtük**. Bu veri setinde dosya özellikleri etiketi
tek başına tahmin edebiliyor:

    forklift çifti : bit hızı MCC +1,000 (orijinal dosyalarda)
    yetkisiz çifti : fps      MCC +1,000 (bizim gönderdiğimiz baytlarda)

Yani skorlarımız içerikle ilgisi olmayan bir eşiğin **altındaydı** ve bu
kanıtlanmamıştı. Bunu kapatmak için tüm videoları ortak spekte kodladık
(sabit fps + sabit bit hızı), yorum kuralını **koşumdan önce** yazdık:

| çift | sızıntılı baytlarla | kontrol altında |
|---|---|---|
| pano | +0,960 | **+0,960** |
| forklift | +0,851 | **+0,840** |
| yetkisiz | +0,689 | **+0,689** |

fps kanalı tamamen kapatıldığı halde skorlar değişmedi.


## 3b. "Yetkisiz müdahale çiftinde kamera açısı etiketi ele veriyor. Siz onu okumuyor musunuz?"

Keskin bir soru ve **haklı** — o çiftte iki kamera görüşü var ve dağılım
dengesiz: geniş planın %89'u ihlal. İçeriğe hiç bakmayan, sadece
*"geniş plan ise ihlal de"* diyen bir sistem orada **MCC +0,618** alır.
Bizim skorumuz +0,689; tek başına "üstünde olması" yeterli kanıt değil.

Bu yüzden **katmanlı analiz** yaptık — karıştırıcıyı sabitleyip ilişkinin
kalıp kalmadığına baktık:

| katman | n | MCC |
|---|---|---|
| GÖRÜŞ-A (yakın) | 31 | **+0,563** |
| GÖRÜŞ-B (geniş) | 19 | **+0,574** |

Kural **her iki görüşün içinde** ayırt ediyor → skor kameradan değil,
yelek varlığından geliyor.

Diğer iki çiftte bu sorun yok: klipler tek görüşte ve dengeli; kameraya
bakarak alınabilecek en yüksek skor 0,14 (pano +0,960, forklift +0,881).

**Bu yüzden yapmadığımız şey:** geniş görüşte yelek kuralının 3 kaçırması
var. "Geniş görüşte farklı soru sor" yaklaşımını **denemedik** — görüş
etiketle 0,833 korele olduğu için görüşe göre davranış değiştirmek etiket
bilgisi sızdırırdı. Bu, daha önce geofence'i reddetme sebebimizin aynısı.

## 4. "Yanlış alarm oranınız %60. Bu çok yüksek değil mi?"

Sayı doğru ama **sistemin hata oranı değil**. Değerlendirme setinde kamera 9'un
dört sınıfı **aynı fiziksel sahnedir** ve her klip **tek bir tehlikeyle**
etiketlidir — oysa bir klipte hem açık pano hem yeleksiz kişi bulunabilir.

Kliplere **gözle** baktık (12 klip, rastgele): bu tesiste standart iş kıyafeti
koyu tulum, yeşil yelek nadir. Bakılan kliplerin neredeyse hepsinde makinenin
başında **gerçekten yeleksiz bir kişi var**. Yani ateşlemeler olgusal olarak
doğru; kıyas kümesi onları farklı bir eksende etiketliyor.

Bunu **ölçtük**: her kural için çapraz ateşlemelerden tohumlu rastgele 12
örnek çekilip gözle etiketlendi (model yeniden sorulmadı — dairesel olurdu):

    yelek : 12/12 karede makine yakınında YELEKSİZ kişi VAR
    pano  : 12/12 karede AÇIK pano boşluğu VAR

Düzeltilmiş saha kesinliği:

    pano   0,390 -> 1,000  [alt sınır 0,852]
    yelek  0,237 -> 0,975  [alt sınır 0,796]
    forklift              0,923  (çapraz ateşleme YOK)

Tutarlılık: pano ateşlemelerinin çoğu yetkisiz müdahale kliplerinde —
**birine müdahale etmek için pano açılır.** İki tehlike gerçekten birlikte
oluşuyor; veri seti klip başına yalnız birini etiketliyor.

Çekince: tek kareye bakılarak verilmiş insan hükmü; bu yüzden alt sınır da
veriliyor.

## 5. "Ölçümleriniz tekrar üretilebilir mi?"

Evet, ve kaynağını araştırdık. Aynı yapılandırmada MCC ±0,05 oynuyordu.
Üç katmanı ayrı ayrı test ettik:

- **Model:** deterministik — 50 klipte 2 slot, 3 tekrar, **50/50 birebir aynı**.
- **Kare çıkarımı:** deterministik — 3/3 aynı.
- **Video kodlaması:** **değil** — 0/8 aynı. Kaynak buydu.

`DILAJAN_KODLAMA_KARARLI=1` ile kodlama tek iş parçacığına alınır ve
**8/8 tekrar üretilebilir** olur (kodlama ~3× yavaşlar, varsayılan kapalı).

## 6. "Dört sınıftan birini neden kapsamıyorsunuz?"

`Safe_Walkway_Violation` için **dokuz farklı yaklaşım** denedik; en iyisi
ayrılmış kümede MCC +0,638 verdi. Buna rağmen sevk etmedik: kural, forklift
kliplerinin **49/50'sinde** ateşliyordu ve ateşlediği 166 klipte gerçek ihlal
oranı 0,151'di.

Kamera görüş muhafızı ekledik — forklift kamerasındaki ateşleme **0/28**'e
düştü. Ama kendi çiftinde MCC yalnızca +0,313 kaldı (ön kayıtlı eşik +0,45).

Çalışan bir özelliği ölçüme dayanarak reddetmek bilinçli bir tercih.
Kod, muhafız ve testler duruyor; ölçüt sağlanınca tek satırla açılır.

## 7. "Bu sistem başka bir fabrikada çalışır mı?"

Ölçtük — bağımsız bir sette (iSafetyBench, YouTube kaynaklı, 1100 klip).

- **Anlatı düzlemi taşınıyor:** yabancı tehlike kliplerinin %97'sinde olay
  üretti, açıklamalar isabetli.
- **Gözlem düzlemi taşınmıyor** ve bunu doğrudan gösterdik: tesise özgü
  kurallar yabancı kliplerin %50'sinde boşa ateşledi. Sebep açık — pano
  ROI'si *bizim* karemizde bir dikdörtgen.

Yeni tesiste sistem **mimari olarak hazır, kalibrasyon olarak sıfırdan**
başlar. Yordam yazılı: ROI seç → eşiği tara → **ayrılmış kümede doğrula**.
Bu projede slot başına ~20 dakika sürdü.

## 8. "Modelin kendi genel İSG bilgisi ne kadar?"

16 seçenekli bağımsız testte (şans %6,25):

    llm-large  tehlike %54,7  ·  rutin %48,7
    vlm        tehlike %44,0  ·  rutin %52,7

Şansın 7–9 katı — genel tehlikeleri tanıyor ama 16 seçenek içinde yaklaşık
yarısını kaçırıyor. Bizim mimarimizin varlık sebebi tam da bu: modelin ham
tanıma yeteneğine güvenmek yerine, ona **ölçülebilir** sorular soruyoruz.

## 9. "Hangi model neyi yapıyor?"

Görev bazlı atama `.env`de ve ölçümle gerekçeli: **algı → `vlm`**
(kişi/öznitelik sorularında tek çalışan), **sayım → `llm-fast`**.
`llm-large` sayma ve özet için ölçüldü, anlamlı fark bulunmadı ve servis tüm
takımlarca paylaşıldığı için büyük model gereksiz meşgul edilmiyor.

## 10. "Çıktı sözleşmesi şartnameye uygun mu?"

Evet — `summary`, `events`, `risk`, `actions`. Arayüzdeki "Ham JSON" sekmesi
bunun **üst kümesini** gösterir (karar-izi, tetiklenen fonksiyonlar dahil);
şartname sözleşmesi `schema.to_sartname_dict()` ile üretilir. Anahtar sayan
bir soruya bu ayrımla cevap verin.

---

## Söylememeniz gerekenler

- ~~"Tamamen offline çalışıyor"~~ — artık uzak servis kullanılıyor.
- ~~"%X doğruluk"~~ tek başına — dengesiz sınıflarda MCC kullanın; hepsine
  "ihlal yok" diyen sistem %50 doğruluk alır ama MCC'si 0 çıkar.
- ~~"Yanlış alarmımız yok"~~ — var; ama ölçülebilir eksende kesinlik 0,90–1,00.

---

## EK 2026-08-25 — "Neden bu sınıfı kapsamıyorsunuz?" ve türevleri

### S: Dört İSG sınıfından birini (yaya yolu) hiç kapsamıyorsunuz. Neden?

Denemedik değil — **on kol denedik, onu da reddettik**, ve artık *neden*
olmadığını biliyoruz.

İlk dokuz kol aynı soru tipinin varyasyonuydu ("kişi çizgiye ne kadar yakın").
Onuncu kol soruyu **yerel** yaptı: *"ayağının altındaki zemin hangisi?"*
Sonuç: cevap dağılımı **altı sınıfta neredeyse özdeş** — ihlal sınıfıyla onun
normal karşılığı arasında bile ayrım yok. Slot sınıf bilgisi taşımıyor.

Sebep ölçülü: soru yereldi ama **kırpma yerel değildi**. Kırpmayı kişiye
kilitlemek kişinin yerini bilmeyi gerektirir; o çözünürlükte CPU dedektörü de
kişiyi bulamıyor (üç geniş-plan klibinin ikisinde **0 kişi**).

**Kapsamadığımız sınıfı kapsıyormuş gibi göstermek yerine sınırı ölçüp ilan
ettik.** `isg_match`'i her zaman iki sayıyla veriyoruz: 0,646 (dört sınıf) ve
0,865 (kapsanan üç sınıf).

### S: Skorlarınız eşik ayarına mı bağlı? Eşikler kırılgan mı?

Ölçtük. Kısıtlı çözmenin olasılık dağılımını okuyup sert eşik
(`argmax ≥ T`) yerine yumuşak eşik (`P(değer ≥ T) ≥ 0,50`) denedik.
Üç çiftte de kazanç **yok** (en iyi ΔMCC +0,006, ölçüt +0,03 idi).

Bu bir başarısızlık değil, **bir kanıt**: eşikler dağılımın kararlı
bölgesinde duruyor, sınırda değil.

### S: Neden kişi tespiti / Set-of-Mark gibi güncel teknikleri kullanmıyorsunuz?

İkisini de değerlendirdik:

- **Set-of-Mark** (numaralı işaret bindirme): açık kaynak modellerde doğruluğu
  **düşürdüğüne** dair ölçüm var. Denemedik çünkü beklenen kazanç negatif.
- **Kişi-başına kırpma**: fizibilitesini ölçtük. Geniş plan kliplerinde CPU
  dedektörü **hiç kişi bulamıyor**; kalabalık kliplerde 11-13 kişi arasından
  "makinedeki kişi"yi seçmek belirsizliği modelden alıp bizim buluşumuza
  taşır — daha önce tam bu sebeple bir kol reddedilmişti.

### S: Model belirsizken bunu görebiliyor musunuz?

Evet, ve **ek maliyet olmadan**. vLLM'in kısıtlı çözmesi ile `logprobs`
birlikte çalışıyor: tek ileri geçişten izinli cevap kümesi üzerinde tam bir
olasılık dağılımı okunuyor. Bu, kaçırmalarımızın kök nedenini ayırmamızı
sağladı — model belirsiz değil, **emin ve yanlış yere bakıyor**.

Ayrıntı: `docs/kalan_sinirlar_2026-08-25.md`
