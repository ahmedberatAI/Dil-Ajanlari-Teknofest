# D43–D44 — Gözlem düzlemi, ROI kırpması ve olumsuzlama kapsamı

Tarih: 2026-08-24 · Dal: `d34-isg-veri-kkd`

## 1. Ölçülen sorun

İSG ihlalleri uçtan uca **0/20** yakalanıyordu. Kaybın nerede olduğu ölçüldü
(n=20 güvensiz klip):

| aşama | sonuç |
|---|---|
| K1 serbest betimleme ihlali iddia etti | 0/20 |
| K1′ betimleme doğru nesneyi andı | 7/20 (yelek 0/5, pano 0/5) |
| K2 bilgi zorla verilirse olaya geçen | 11/20 (%45 kayıp) |
| K3 olaya geçenden eşleştiricinin yakaladığı | 4/11 (%64 kayıp) |
| **uçtan uca** | **0/20** |
| aynı model, **işlemsel** soru | 12/20 (kaçışlı) · 20/20 (kaçışsız) |

Bilgi algı anında modelde **vardı**. Darboğaz model değil, mimariydi.

## 2. Yapılan

**Gözlem düzlemi** (`dilajan/gozlem.py`): model kapalı cevap uzayında bir slot
doldurur. **Kural motoru** (`dilajan/isg_kural.py`): hükmü deterministik verir.
`Event.event` metni şablon render'ıdır — model nesri değil. Böylece K2 (çıkarım)
ve K3 (sözcüksel kapı) kayıpları yapısal olarak imkânsızlaşır.

## 3. Bu oturumda bulunan ve düzeltilen kusurlar

### 3.1 `ingest` düğümü NameError ile düşüyordu (ÖLÇÜMÜ GEÇERSİZ KILAN)
`_ingest_output()` çağıranın yerel `_kaynak_yol` değişkenine erişmeye
çalışıyordu. K3 fail-open bunu yuttu; boru hattı 0 segmentle "ihlal yok"
özeti üretti. **149 kliplik ilk koşum hiçbir şey ölçmemişti** — tüm hücreler
sıfır, klip başına 2,2 s (gerçek süre ~28 s). Parametreye çevrildi.

### 3.2 Kural ön koşulu yoktu — tabandan yanlış pozitif
Yelek slotu **forklift kamerasında da** "YOK" dönüyordu; orada ne pano ne de
makine başında kişi var. Modelin kaçış seçeneğini kullanmasını beklemek yerine
ön şart **ayrı ve sayısal** bir slot yapıldı (`makine_basinda_kisi`): sıfır
sayma modelin doğal cevabıdır, kaçış değildir. Ölçüldü: kaçış seçeneği teklif
etmek MCC'yi +0,885'ten +0,000'a düşürüyor.

Ön koşul **kendi kuralını** bağlar; forklift kuralı etkilenmez.

### 3.3 Pano slotu tam karede ölü, ROI kırpmasıyla mükemmel
| kol | ACIK cevaplar | KAPALI cevaplar | MCC |
|---|---|---|---|
| tam kare | {8:1, 2:5} | {8:2, 2:4} | **−0,192** |
| dar ROI | {8:11, 7:1} | {7:9, 5:3} | +0,920 |
| **orta ROI (+%8 pay)** | {8:9, 7:2, 2:1} | {3:8, 5:3, 2:1} | **+0,920** |
| geniş ROI | {7:10, 5:1, 8:1} | {5:7, 3:3, …} | +0,833 |

Belirleyici olan modelin yeteneği değil, **sorulan bölgenin karedeki payı**.

"orta" kolu seçildi: eşik 6, ACIK tabanı (7) ile KAPALI tavanı (5) arasında
**2 birimlik boşlukta**. "dar" kolu aynı MCC'yi veriyor ama sınır 7|8 — 1 birim,
kırılgan.

**Ayrılmış kümede doğrulama** (seçimde hiç görülmeyen 12 AÇIK + 13 KAPALI,
eşik koşumdan ÖNCE yazıldı): **MCC +1,000 · 25/25 · Wilson95 [0,867–1,000]**.
Eşik 6-7-8 platosu → seçim kırılgan değil.

### 3.4 Olumsuzlama kapsamı cümleciği aşıyordu
`_AYIRAC_RE` virgülde bölüyor, Türkçede sıralanmış nesneler tek olumsuz fiili
paylaşıyor:

    "güvenlik ihlali, tehlikeli durum veya anomali tespit edilmemiştir"
     └── olumsuzluk fiili bu parçada YOK → olumlu eşleşme sayılıyordu

Olumsuzluk artık **cümle kapsamında** değerlendirilir; yayılım yalnızca liste
ayıraçlarıyla bağlı ve **kendi çekimli fiili olmayan** parçalara uygulanır.
`kapsam_yayilimi=False` varsayılan → arşivler birebir korunur (K2).

**Arşiv denetimi** (84 dosya, hiçbiri değiştirilmedi):

| arşiv | onarık kapı | kapsam kapısı | fark |
|---|---|---|---|
| eval_20260818_105759 | 4 | 4 | 0 |
| eval_20260818_141920 | 11 | 11 | 0 |
| **eval_20260818_151618** | **18** | **3** | **−15** |
| eval_20260824_145937 | 88 | 88 | 0 |
| toplam | 121 | 106 | **−12,4%** |

Not: `category_match` kova düzeyi ("Anomali") bir metriktir ve kabadır;
İSG'ye özgü sayı `isg_match`tir (2/197). Bu düzeltme kaba metriği düzeltir,
İSG sayısını değiştirmez.

### 3.5 Aynı ihlal her segmentte tekrar raporlanıyordu
`_isg_tekille`: aynı `isg_kod`'u taşıyan olaylardan yalnızca ilki tutulur.
İSG kodu taşımayan olaylara dokunulmaz → bayrak kapalıyken liste birebir aynı.

## 4. Yerel GPU bağımlılığı kaldırıldı

Tüm LLM/VLM çağrıları zaten uzak servise gidiyordu. Yerel GPU'yu kullanan tek
bileşen deterministik pano dedektörünün kişi kontrolüydü
(`panel_kisi_kontrolu` → RT-DETRv2, ~3,5 GB VRAM, her klipte).

VLM pano slotu (+1,000 doğrulanmış) deterministik dedektörden (197 klipte
+0,270) **daha iyi** olduğu için dedektör devre dışı: hem doğruluk artıyor
hem yerel bağımlılık sıfırlanıyor. Sevk edilen yapılandırmada yerel ağırlık
yüklenmesi sayısı: **0**.

## 5. Sevk edilen yapılandırma

```
DILAJAN_ISG_SLOTLARI=catal_kasa_sayisi,makine_basinda_yelek,pano_koyuluk_0_10
DILAJAN_PANEL_ROI_VLM=0.00,0.47,0.29,0.81
DILAJAN_PANEL_KOYULUK_ESIK=6
DILAJAN_PANEL_ROI=                      # BOŞ — yerel dedektör kapalı
```

Model ataması `.env`den (ölçülmüş): sayım → `llm-fast`, algı → `vlm`.

## 6. Kapsam dışı kalan

`Safe_Walkway_Violation` sınıfı **kapsanmıyor**. Geofence yaklaşımı daha önce
reddedildi: MCC +0,506 görünüyordu ama çerçeveleme tek başına %72,9 (= R1
doğruluğu) veriyordu — skor bilgiden değil kamera açısının etiketle
korelasyonundan geliyordu (Fisher p=0,0024). VLM slotu için çerçeveleme
kontrolü gömülü bir prob yazıldı; kabul ölçütü koşumdan önce kaydedildi
(slot MCC, çerçeveleme tabanını en az +0,25 geçmeli). Ölçülmeden sevk edilmez.

---

# EK — D44 ikinci tur: birleştirme kaybı ve denetim bulguları

## 7. Uçtan uca sayının yarısını yiyen kusur

İlk uçtan uca ölçüm `Unauthorized_Intervention` için **+0,393** verdi. Kayıtlı
slot değerlerine kuralı elle uygulayınca tavanın **+0,689** olduğu görüldü —
yani doğru pozitiflerin yedisi boru hattının **içinde** kayboluyordu.

Düğüm düğüm enstrümantasyon kaybı tek satıra indirdi:

```
>>> _dedupe_events: 2 -> 0   KAYIP!
```

**Kök neden:** `_dedupe_events` birleştirdiği olayı `Event(...)` ile **yeniden
kuruyor**; pydantic şemasında tanımlı olmayan alanlar sessizce düşüyor. Çok
segmentli bir klipte aynı ihlal iki segmentten birden bildirildiğinde ikisi
birleşiyor ve `isg_kod` yok oluyor — olay listede duruyor ama artık hiçbir İSG
sınıfına ait değil, etiket metriği onu hiç görmüyor.

Bu kök neden **üçüncü kez** işledi: `evidence_prev` (D33), `ppe_src` (D34),
`isg_kod` (D44). İlk ikisi için tek tek koruma yazılmış, üçüncüsü için yazılmamıştı.

**Düzeltme:** birleşik olaya `isg_kod`/`isg_slot`/`isg_deger` `model_copy` ile
taşınır; farklı koda sahip iki olay hiç birleştirilmez. `tests/test_isg_alan_korunumu.py`
(20 iddia) üç alanın da korunduğunu ve D33/D34'ün gerilemediğini doğrular.

**Ön kayıtlı tahmin tuttu:**

| sınıf çifti | önce | tahmin | sonra |
|---|---|---|---|
| Unauthorized_Intervention | +0,393 | +0,689 | **+0,689** |
| Opened_Panel_Cover | +0,960 | +0,960 | **+0,960** |
| Carrying_Overload_with_Forklift | +0,762 | +0,806 | +0,770 |

## 8. Sessiz kusur denetimi — 32 bulgu, doğrulananlar

Beş bağımsız denetçi ajanı kod tabanını "hata fırlatmayan, çıktısı makul görünen,
ölçümü sessizce bozan" kusur sınıfı için taradı. Doğrulama aşaması betik hatasıyla
düştü; bulgular kayıttan geri okunup **tek tek elle doğrulandı**.

### 8.1 Kendi düzeltmem bozuk çıktı — GERİ ALINDI

D44'te eklediğim `kapsam_yayilimi` olumsuzlama kapısı üç test metninin üçünde de
yanlış sonuç verdi:

- Fiil vekili **yaygın adları fiil sanıyor**: test edilen 21 addan 19'u
  (`bir`, `hiçbir`, `demir`, `müdür`, `hazır`, `çukur`, `kusur`, `tedbir`,
  `zincir`, `silindir`, `bakır`, `kömür`, `memur`, `amir`, `fikir`, `satır`,
  `tur`, `kendi`, `şimdi`). Sonuç: kapı tam da yazılma gerekçesi olan cümlede
  ("herhangi **bir** güvenlik ihlali, … tespit edilmemiştir") devre dışı kalıyor.
- Ad yüklemli parçalar ("pano kapağı **açık**") fiilsiz göründüğü için olumsuz
  kapsama alınıyor ve **gerçek tespitler siliniyor** — arşiv ölçümü: İSG hedef
  setinde gerçek eşleşmelerin %83'ü (18 → 3) kayboluyordu.
- Karşıt bağlaçlar (`ancak`/`fakat`/`ama`) liste ayıracı sayılmadığı için
  "Alev gözlemlenmemiştir **ancak** yoğun duman yükselmektedir" tek parça oluyor
  ve duman tespiti eleniyor.

Onarım, onardığı kusurdan daha çok zarar veriyordu. **Kod kaldırıldı**, yerine
yanlış çalışan bir kapı bırakılmadı; `benchmark/labels.py` içinde RET kaydı ve
doğru çözümün ne olması gerektiği duruyor. Tespit edilen asıl kusur (virgülle
ayrılmış nesnelerin ortak olumsuz fiili) **hâlâ açık** ve öyle kaydedildi.

### 8.2 Segment penceresi hiç uygulanmıyordu

`servis_videosu` komutunda `-ss`/`-t` yoktu; `kaynak_yol` her segmente **tüm
videonun** yolunu yazıyordu. İki sonucu vardı:

1. N segmentlik klipte aynı soru N kez tüm videoya soruluyor, N kat ffmpeg ve
   N kat gövde harcanıyordu (`slotlari_doldur_bolgeli` docstring'indeki
   "çağrı sayısı artmaz" iddiası bu yolda geçersizdi).
2. Üretilen olayın zaman damgası ihlalin gerçek anına değil **ilk segmente**
   denk geliyordu — 02:30'daki aşırı yük 00:00 diye raporlanıyordu.

Düzeltildikten sonra duman testi: aynı klibin iki segmenti artık **farklı**
cevap veriyor (çatalda 2 kasa / 3 kasa), yani her segment kendi penceresini görüyor.

### 8.3 "Ölçülemedi" ile "ihlal yok" ayrılmıyordu

`_VideoOturumu.sor()` istisnayı kendi içinde yutup `None` döndürüyor; bu yüzden
`slotlari_doldur` içindeki `except` **hiç ateşlenmiyordu**. Servis 500/timeout
verdiğinde slot sessizce "çözülemedi" oluyor, kural motoru susuyor, karar-izi
`hata=[]` yazıp **hiç hata olmadığını iddia ediyordu**. Ölçüm hücresi sıfır,
görünürde sorun yok.

Aynı sessizlik oturum hiç kurulamadığında da vardı (video gövde sınırını aşarsa
`video_oturumu` istisna atmaz, `hazir=False` döner).

Artık her iki durumda da slot `__HATA__` ile işaretlenir ve karar-izine
`ISG slotlari OLCULEMEDI -> …` satırı yazılır. Kaynak video yokken kullanılan
kare-yedeği yolu da (ROI ve pencere uygulanmaz, ölçülen DEJENERE kip) ize yazılır.

### 8.4 `api_timeout` çalışma zamanında etkisizdi

Alan tanımlıydı ve `.env`de `1800` yazıyordu, ama `VLMClient` her zaman
`request_timeout`u (**120 s**) kullanıyordu; `api_timeout`un tek referansı bir
doğrulama betiğiydi. Dokümantasyon uzak servis için 600 s'yi bile yetersiz
sayıyor. 120 s'yi aşan uzun video istekleri `APITimeoutError` fırlatıyor, o da
§8.3'teki yoldan sessizce "ihlal yok"a dönüşüyordu.

`Settings.etkin_timeout` eklendi: uzakken `api_timeout`, yerelde `request_timeout`
(K2 — yerel davranış değişmez). Doğrulandı: istemcinin gerçek timeout'u artık 1800 s.

### 8.5 `forklift_esik` aynı sınıfta iki kez tanımlıydı

`config.py:235` ve `config.py:254`. Python ikinci tanımı kullanır, pydantic uyarı
vermez. İki değer de 3 olduğu için davranış bugün doğruydu — kusur yalnızca
düzenleme anında ortaya çıkardı: yukarıdaki blokta yapılan bir eşik değişikliği
hiçbir uyarı vermeden etkisiz kalırdı. İkinci tanım kaldırıldı.

### 8.6 Ara-kayıt künyesi ayırt edemiyordu

Ara-kayıt dosya adı `_kosum_kunyesi()` md5'idir; künyede `isg_slotlari`,
`panel_roi_vlm`, `panel_koyuluk_esik`, `forklift_esik` **yoktu**. Yani gözlem
düzlemi AÇIK ve KAPALI kollar aynı ara dosyayı paylaşıyor, ikinci koşum
birincinin satırlarını "tamamlanmış" diye devralıyordu — "kapalı" diye raporlanan
sayılar aslında açık kolun sayıları olurdu. Aynı hata bu dosyada daha önce
`isg_lens` ve `panel_roi` için yaşanmış ve yorumlara kaydedilmişti. Dört bayrak
künyeye eklendi.

### 8.7 Çürütülen ve kapalı daldaki bulgular

- **scipy yok** iddiası (forklift geometri kolunun sessizce yedek algoritmaya
  düştüğü): **çürütüldü** — scipy kurulu.
- **`EVREN_*` çevre değişkenleri okunmuyor**: doğru, `os.environ`a girmiyorlar;
  ancak `.env`de `DILAJAN_` önekli karşılıkları da bulunduğu için bu kurulumda
  `uzak_api_mi=True`. `.env.ornek`teki "ikisi de desteklenir" ifadesi yine de
  yanıltıcı.
- **`_segment_consistent_events` aynı korumalara sahip değil**: doğru, ama
  `event_consistency_n=1` ve `ppe_detection=False` olduğu için kapalı dalda.

---

# EK-2 — Slot kapsamı ve nihai sayılar

## 9. Kapsam bir performans ayarı değil, sorunun anlamının parçası

Segment penceresi düzeltildikten sonra iki kol **ters yönde** ayrıştı:

| sınıf çifti | tüm video | segment penceresi |
|---|---|---|
| Carrying_Overload_with_Forklift | +0,770 | **+0,851** |
| Unauthorized_Intervention | **+0,689** | +0,527 |
| Opened_Panel_Cover | +0,960 | +0,960 |

Açıklama: **aşırı yük bir ana ait bir ölçümdür** — pencere daraldıkça ihlal
anı izole olur, kaçırma 1'den 0'a düşer. **"Makinenin başında kişi var mı"
ise klip düzeyinde bir ön koşuldur** — pencere daraldıkça kişi görüntünün
yalnızca bir bölümünde kalır ve kapı yanlış kapanır.

Bu yüzden slotlara `kapsam` alanı eklendi:

- `kapsam="segment"` — soru segmentin kendi zaman penceresine sorulur
  (`catal_kasa_sayisi`, `pano_koyuluk_0_10`)
- `kapsam="klip"` — soru tüm klibe, yalnızca ilk segmentte sorulur
  (`makine_basinda_kisi`, `makine_basinda_yelek`)

Slotlar artık `(ROI, kapsam)` ikilisine göre gruplanır; aynı bölge **ve** aynı
zaman ölçeğini paylaşan slotlar tek video oturumunu paylaşır (K4).

Ön kayıt koşumdan önce yazıldı; kabul ölçütü *yetkisiz ≥ +0,650 ve
forklift ≥ +0,800* idi. **Her ikisi de sağlandı.**

## 10. Nihai ölçüm — sevk edilen yapılandırma

149 klip, tamamen uzak (yerel ağırlık yüklenmesi: 0), klip başına medyan 38,7 s.

| sınıf çifti | TP | FP | FN | TN | MCC | doğruluk | Wilson95 |
|---|---|---|---|---|---|---|---|
| Opened_Panel_Cover | 23 | 0 | 1 | 25 | **+0,960** | 0,980 | [0,893–0,996] |
| Carrying_Overload_with_Forklift | 25 | 4 | 0 | 21 | **+0,851** | 0,920 | [0,812–0,968] |
| Unauthorized_Intervention | 19 | 2 | 6 | 23 | **+0,689** | 0,840 | [0,715–0,917] |

Aynı kliplerde eski serbest metin boru hattı: **0/20 İSG olayı**, `isg_match` 2/197.

Yol boyunca ölçülen ara durumlar (hiçbiri silinmedi):

| aşama | forklift | yetkisiz | pano |
|---|---|---|---|
| serbest metin boru hattı (D42) | — | — | — (uçtan uca 0/20) |
| gözlem düzlemi, `ingest` kusurlu | +0,000 | +0,000 | +0,000 |
| `ingest` düzeltildi | +0,762 | +0,393 | +0,960 |
| birleştirme kaybı düzeltildi | +0,770 | +0,689 | +0,960 |
| segment penceresi | +0,851 | +0,527 | +0,960 |
| **kapsam ayrımı (sevk edilen)** | **+0,851** | **+0,689** | **+0,960** |

## 11. Hâlâ açık olanlar

- **`Safe_Walkway_Violation` kapsanmıyor.** Geofence yaklaşımı çerçeveleme
  kısayolu çıktığı için reddedildi; VLM slotu için çerçeveleme kontrolü gömülü
  bir prob yazıldı ama henüz koşulmadı. Ölçülmeden sevk edilmez.
- **Yetkisiz müdahalede 6 kaçırma.** Slot düzeyi tavanı da +0,689 — yani kayıp
  artık boru hattında değil, slotun kendisinde: 25 ihlal klibinin 3'ünde model
  "yelek VAR" diyor, 3'ünde ön koşul kapanıyor.
- **Sınıflar arası gürültü.** Yelek kuralı pano kliplerinin 36/49'unda da
  ateşliyor. Çift bazlı metriği etkilemiyor ama sahada operatöre gider.
- **Virgülle ayrılmış nesnelerin ortak olumsuz fiili** (§8.1) — gerçek kusur,
  denenen onarım geri alındı, çözüm açık.

---

# EK-3 — D45: dördüncü sınıf ve yelek tavanı

## 12. Yelek slotu bilgi tavanına oturmuş — soru biçimi burada çare değil

Yetkisiz müdahaledeki 6 kaçırmanın kaynağı boru hattı değil, slotun kendisiydi
(uçtan uca +0,689 = slot tavanı). Pano dersini ("soru biçimi belirleyici")
yeleğe uyguladım: aynı 28 klip, aynı video baytları, beş kol.

| kol | MCC | karışıklık |
|---|---|---|
| A mevcut ikili + `vlm` (taban) | +0,788 | TP13 FP2 FN1 TN12 |
| B mevcut ikili + `llm-large` | +0,788 | TP13 FP2 FN1 TN12 |
| C sayım: yelekli kaç kişi | +0,788 | TP12 FP1 FN2 TN13 |
| D sayısal: yeleğin yeşilliği 0-10 | +0,788 | TP13 FP2 FN1 TN12 |
| E sayım: yeleksiz kaç kişi | −0,229 | dejenere |

Dört farklı biçim **birebir aynı** sonuca oturuyor, model değişimi dahil. Aynı
klipler yanlış okunuyor. Pano'da belirleyici olan soru biçimiydi; burada değil —
slot bilgi tavanında. Mevcut soru kalıyor. (E kolu reddedildi: "yeleksiz kaç
kişi" sorusu modelden iki adımlı çıkarım istiyor ve çöküyor.)

## 13. Safe_Walkway_Violation — dört ret, sonra ROI ile kabul

Bu sınıfta daha önce geofence yaklaşımı **reddedilmişti**: MCC +0,506 görünüyordu
ama çerçeveleme tek başına aynı skoru veriyordu. Bu yüzden çerçeveleme kontrolü
proba **gömülü** koşuldu.

**Çerçeveleme tabanı: MCC −0,072** (n=28) — bu sınıfta kamera açısı tek başına
sinyal taşımıyor. Yani buradaki bir skor, geofence'ten farklı olarak, çerçeveden
gelemez.

Ölçüm zinciri (hiçbiri silinmedi):

| kol | IHLAL dağılımı | NORMAL dağılımı | MCC |
|---|---|---|---|
| tam kare, ikili (içinde/dışında) | DIŞINDA 13 | DIŞINDA 14 | −0,192 (dejenere) |
| tam kare, sayım | 1:7, 0:4, 2:3 | 1:7, 2:6 | −0,280 |
| tam kare, mesafe 0-10 | 5:9 | 5:11 | +0,192 |
| **ROI alt yarı, mesafe 0-10** | 0:5, 5:7 | 7:5, 5:7 | **+0,466** |
| ROI alt şerit, mesafe | — | — | +0,082 |
| ROI, ikili | DIŞINDA 14 | DIŞINDA 14 | dejenere |

Yine pano'daki mekanizma: **tam karede ölü, ROI kırpmasıyla canlı.**

### Kendi kabul ölçütümdeki hata

Betiğim kolları `abs(MCC)` ile sıralıyordu ve en iyi kolu "+0,466" diye değil
**−0,466** diye buldu, yani ters işaretli bir ilişkiyi "KABUL" diye raporladı.
İşaretli hesap doğru kuralı verdi: *çizgiye uzaklık < 7 → ihlal*, MCC +0,466.

### Ayrılmış kümede doğrulama

Eşik seçim kümesinde belirlendiği için, pano'ya uyguladığım standardın aynısı
uygulandı — seçimde hiç görülmeyen 11 İHLAL + 9 NORMAL klip, eşik koşumdan önce
sabitlenmiş:

**MCC +0,638 · TP11 FP4 FN0 TN5 · doğruluk 0,800 [0,584–0,919]**

Seçim kümesinden (+0,466) *daha yüksek* ve 11 ihlalin hepsini yakalıyor. Kabul.

### Açık bırakılan semantik çekince

Ölçülen ilişki **"mesafe küçük → ihlal"** yönünde. "İşaretli yolun içinde yürümek
güvenlidir" sezgisiyle bu ters görünüyor. Bu tesiste çizginin ne olduğunu
(yaya yolu sınırı mı, araç şeridi kenarı mı) bilmiyoruz. Bu yüzden:

- Slot adı **ölçülen büyüklüğü** anlatır: `yaya_cizgi_mesafe`.
- Kural metni de öyle: *"kişi yerdeki işaretli çizginin hemen üzerinde/bitişiğinde
  yürüyor (çizgiye uzaklık {değer}/10)"* — nedensel bir hikâye iddia etmez.
- Yön, çevrilebilir bir bayrak değil, **ayrı bir kural sınıfının tanımında**
  sabittir (`AltEsikKurali`). Böylece "sonuç kötü çıktıysa yönü çevir" kapısı kapalı.

---

# EK-4 — Çift bazlı metriğin gizlediği şey

## 14. Saha kesinliği: kural yalnız kendi çifti içinde ölçülüyordu

Şimdiye kadar raporladığım MCC'ler **çift bazlıdır**: her kural yalnızca kendi
sınıf çiftinin klipleri içinde değerlendiriliyor. Operatör ise bütün klipleri
görür. 197 kliplik evrende ölçüm:

| kural | çift MCC | ateşlediği | doğru | **saha kesinliği** |
|---|---|---|---|---|
| Carrying_Overload_with_Forklift | +0,851 | 29 | 25 | **0,862** |
| Opened_Panel_Cover | +0,960 | 57 | 23 | 0,404 |
| Unauthorized_Intervention | +0,689 | 83 | 19 | 0,229 |
| Safe_Walkway_Violation | +0,535 | 166 | 25 | 0,151 |

Kural × çift matrisi:

```
KURAL \ ÇİFT   forklift   yetkisiz    pano       yol
forklift        29/50      0/50       0/49      0/48    ← hiç sızmıyor
yetkisiz         4/50     21/50      36/49     22/48
pano             0/50     21/50      23/49     13/48
yol             49/50     33/50      46/49     38/48    ← her yerde
```

## 15. Kamera ayrımı bu tabloyu iki farklı olguya ayırıyor

Kaynak makaleye göre **kamera 14** forklift sınıflarını, **kamera 9** pano /
yetkisiz müdahale / yaya yolu sınıflarını çekiyor. Yani son üç sınıfın klipleri
**aynı görüntüdedir**.

Bu ayrımla:

- **Kamera 9 içindeki çapraz ateşleme yanlış olduğu kanıtlanamaz.** Klipler
  tek etiketlidir; bir klipte hem açık pano hem yeleksiz kişi gerçekten
  bulunabilir. Bunları "yanlış pozitif" saymak veriden fazlasını iddia etmek olur.
- **Kameralar arası sızıntı kesinlikle sahtedir.** Forklift kamerasında yaya
  yolu çizgisi sorusu anlamsızdır; model yine de bir sayı üretir.

Yaya yolu kuralı **kapalıyken** kalan üç kuralın kameralar arası sızıntısı:

| kural | başka kamerada ateşleme |
|---|---|
| Carrying_Overload_with_Forklift | 0/29 |
| Opened_Panel_Cover | 0/57 |
| Unauthorized_Intervention | 4/83 |
| **toplam** | **4/169 = %2,4** |

## 16. Yaya yolu slotu SEVK EDİLMİYOR

Slot çalışıyor, ayrılmış kümede doğrulandı (+0,638) ve çift bazlı ölçümü
pozitif (+0,535). Buna rağmen sevk edilmiyor:

- **forklift kliplerinin 49/50'sinde ateşliyor** — tamamen başka bir kamera.
- Ateşlediği 166 klipte gerçek ihlal oranı **0,151**.
- Taranan 10 eşiğin **hiçbirinde** genel kesinlik %15'i geçmiyor; bu bir eşik
  ayarı meselesi değil.

Kod ve ölçüm kaydı duruyor (§7). Açılmadan önce bir **sahne ön koşulu** (kamera
görüş muhafızı) eklenmelidir; `dilajan/pano.py:gorus_imzasi` altyapısı bunun için
hazır ve deterministik pano dedektöründe zaten kullanılmıştı.

## 17. Forklift kuralı neden sızmıyor — genelleştirilebilir ders

"Çatalda kaç kasa taşınıyor?" sorusu forklift olmayan sahnede `GORUNMUYOR`
ya da `0` döndürüyor; slot **kendi kendini sınırlıyor**. Pano ve yol slotları
ise her sahnede bir sayı üretiyor, çünkü sorulan bölge (ROI) her karede vardır.

Ders: **ROI ile sınırlanan bir slot, sorduğu nesnenin o karede var olduğunu
doğrulamaz.** Nesnenin varlığını sorgulayan slotlar kendi kendini sınırlar;
bölgenin bir özelliğini ölçen slotlar sınırlamaz ve ön koşula ihtiyaç duyar.
Yetkisiz müdahale kuralına eklenen `makine_basinda_kisi` kapısı tam olarak budur.

---

# EK-5 — Tam değerlendirme, yanlış pozitif anatomisi ve reddedilen sıkılaştırma

## 18. 197 klip, standart değerlendirme (sevk edilen yapılandırma)

| ölçüt | gözlem düzlemi ÖNCESİ | **sevk edilen** |
|---|---|---|
| `isg_match` (İSG'ye özgü) | 0,020 | **0,545** |
| Anomali recall (≥1 olay) | 0,131 | **0,879** |
| Normal yanlış pozitif | 0,051 | 0,582 |
| Kategori eşleşme | — | 0,849 |
| Medyan gecikme | — | 42,7 s |

İSG'ye özgü tespit **27 kat** arttı. Aynı anda normal kliplerdeki yanlış alarm
%5'ten %58'e çıktı. Bu bir ödünleşme ve gizlenmemeli.

## 19. 57 yanlış pozitifin anatomisi

Kaynak ayrımı: **53'ü deterministik kurallardan**, 1'i anlatı düzleminden,
2'si ikisinden birden.

| üreten kural | normal klipte ateşleme |
|---|---|
| yelek (`Unauthorized_Intervention`) | 32 |
| pano (`Opened_Panel_Cover`) | 23 |
| forklift | 4 |

Alt sınıfa göre: `Closed_Panel_Cover` %72 · `Safe_Walkway` %70 ·
`Authorized_Intervention` %64 · `Safe_Carrying` %28.

### Ama bu ateşlemelerin çoğu YANLIŞ OLDUĞU KANITLANAMAZ

Kamera 9'daki dört sınıf **aynı fiziksel sahnedir** ve klipler **tek
etiketlidir**. Bir kuralın yanlış pozitifi ancak o kuralın **kendi ekseninde
etiketli** kliplerde ölçülebilir:

| kural | ölçülebilir eksende | **kesinlik** | ekseninde etiketi olmayan kliplerde |
|---|---|---|---|
| pano | TP 23 / FP 0 | **1,000** | 34 ateşleme |
| yelek | TP 19 / FP 2 | **0,905** | 62 ateşleme |
| forklift | TP 25 / FP 4 | **0,862** | 0 ateşleme |

Yani üç kural da **ölçülebildiği yerde yüksek kesinlikte**. Yelek kuralı,
yeleğin gerçekten bulunduğu `Authorized_Intervention` kliplerinde yalnızca
2/25 ateşliyor — yelek varken doğru şekilde susuyor. Diğer 62 ateşlemesi,
yelek durumunun **etiketlenmediği** kliplerde.

Bu bir savunma değil, ölçüm çerçevesinin sınırı: sistem gördüğü tüm tehlikeleri
raporluyor, kıyas kümesi ise klip başına tek tehlike etiketliyor. Kesin cevap
için tesise özgü çoklu-etiket doğrulaması gerekir (bekleyen iş #12).

## 20. Ön koşul sıkılaştırma DENENDİ ve REDDEDİLDİ

Yelek kuralının ön koşulu şu an *"panonun/makinenin önünde kaç kişi duruyor"*.
Kamera 9'un dört sınıfı aynı sahne olduğu için koridordan geçen herkes bu kapıyı
açıyor. Kapı **varlık** soruyor, oysa sınıfın tanımı **müdahale**.

Denenen: *"makineye/panoya eliyle dokunan, kapağını açan kaç kişi var?"*

| kol | İHLAL'de açılma | NORMAL'de açılma |
|---|---|---|
| K0 mevcut (önünde duran) | %80,0 | %76,7 |
| K1 müdahale (eliyle dokunan) | %40,0 | %43,3 |

Ön kayıtlı ölçüt: *normalde ≥%25 azalma **ve** ihlalde ≤%10 kayıp*. Gerçekleşen:
normalde −%33 (iyi) ama ihlalde **−%40** (bütçenin dört katı). **RET — K0 kalıyor.**

Not: K1 tam hedeflenen yerde işe yarıyordu (`Closed_Panel_Cover` 7→1,
`Safe_Walkway` 6→2) ama gerçek müdahaleleri de görmüyor. `Authorized_Intervention`
kliplerinde 10/10 açılıyor — orada gerçekten müdahale var ve yelek slotu
doğru şekilde "VAR" diyor, yani oradaki FP kapıdan gelmiyor.

## 21. Hata kaydı düzeltmesi sahada çalıştı

Bu prob sırasında servis 10 istekte **502 Bad Gateway** döndürdü. Sonuç
`__HATA__ InternalServerError: ...` olarak kaydedildi — sessizce "ihlal yok"a
dönüşmedi. Düzeltme öncesinde bu 10 klip ölçüm tablosunda sıfır hücre olarak
görünür ve karar-izi `hata=[]` yazardı (bkz. §8.3).
