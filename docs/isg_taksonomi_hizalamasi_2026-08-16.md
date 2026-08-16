# İSG taksonomi hizalaması ve ince taneli ölçüm (D33)

**Tarih:** 2026-08-16 · **Kapsam:** HANDOFF §6.1
**Ön-kayıt:** [`docs/on_kayit_isg_2026-08-16.md`](on_kayit_isg_2026-08-16.md)

---

## 1. Çözülen sorun

HANDOFF §6.1'in tarif ettiği durum:

> Modelimiz `dilajan/schema.py` `EventCategory` ile **operasyonel** bir taksonomi
> üretiyor (Normal · Güvenlik · Kaza · Sağlık · Anomali · Yetkisiz Erişim · Diğer)
> — yani *"kimi çağıracağız?"*. Değerlendirme setleri ise farklı taksonomiler
> kullanıyor. Ölçmeden önce **iki taksonomiyi hizalayın**.

Buna ölçüm sırasında bulunan **ikinci ve daha ağır** bir sorun eklendi:

> `eval_clips.py` kategoriyi **üst klasörden** alır. `data/eval_defense` için bu
> yalnızca `Anomali` / `Normal` demektir. **Dört ayrı güvensiz sınıf tek kovaya
> düşüyor.** Model hangi tehlikeyi görüp hangisini kaçırdığı **hiç ölçülmüyordu**.

---

## 2. Yapılanlar

### 2.1 İnce taneli İSG taksonomisi (`benchmark/labels.py`, D33 bölümü)

Mendeley `xjmtb22pff` sınıfları (class0–7) `ISG_SINIFLAR` sözlüğüne alındı.
Alt klasör adı **veri seti yayıncısının etiketidir**, bizim uydurmamız değil
(`data/industrial/CLASSES.md` ile doğrulandı) — K7 dürüstlük şartı.

| Kod | Sınıf | Güvenlik | Kabul edilen `EventCategory` |
|---|---|---|---|
| class0 | Güvenli yürüme yolu ihlali | GÜVENSİZ | Güvenlik · Yetkisiz Erişim · *Anomali* |
| class1 | Yetkisiz müdahale | GÜVENSİZ | Yetkisiz Erişim · Güvenlik · *Anomali* |
| class2 | Açık pano kapağı | GÜVENSİZ | Güvenlik · *Anomali* |
| class3 | Forklift ile aşırı yük | GÜVENSİZ | Güvenlik · Kaza · *Anomali* |
| class4–7 | (güvenli karşılıkları) | GÜVENLİ | Normal (veya hiç olay yok) |

*Eğik yazılan `Anomali` **generic** kovadır — bkz. §2.2.*

### 2.2 Neden üç ayrı skor (ve bir türetilmiş)

| Ölçü | Sorduğu soru |
|---|---|
| **Sözcüksel adlandırma** | Metin **bu sınıfa özgü** tehlikeyi adlandırıyor mu? |
| **Operasyonel eşleşme** | Üretilen `EventCategory` kabul kümesinde mi? → *doğru ekip çağrılır mıydı?* |
| **Ayırt edici eşleşme** | Generic `Anomali`/`Diğer` **dışlandığında** model **spesifik** kategoriyi seçebiliyor mu? |
| **Tam doğru** (türetilmiş) | İlk ikisinin **kesişimi** — adlandırdı **ve** doğru yönlendirdi |

Ayırt edici ölçü ayrı tutulmalı, çünkü operasyonel ölçü **tek başına zayıftır**:
`Anomali` dört güvensiz sınıfın da kabul kümesinde olduğu için model **her şeye
"Anomali" diyerek** o testi bedavaya geçer.

### 2.3 Eşli ayırt etme — setin en değerli özelliği

Mendeley seti her tehlikeyi **güvenli karşılığıyla** verir: aynı sahne, aynı
kamera, aynı ekipman; fark **yalnızca davranış**. Bu, şu soruyu doğrudan ölçmeyi
sağlar: *model tehlikeyi mi görüyor, yoksa sahne türüne mi tepki veriyor?*

Ölçüm: güvensiz sınıftaki isabet (TPR) ile **güvenli eşinde aynı dilin
tetiklenmesi** (FPR) yan yana konur. İkisi yakınsa ayrım yok demektir.
Bu karşılaştırma **eşleşmemiştir** (farklı klipler) → **Fisher tam testi**;
McNemar burada yanlış test olurdu.

### 2.4 UCF sınıfları arşive alındı, **silinmedi**

`KAPSAM` sözlüğü her kategoriyi `arsiv_ucf` / `isg_senaryo` / `isg_ikili` diye
etiketler. UCF kategorileri `CATEGORY_EXPECT` ve `CATEGORY_PATTERNS` içinde
**duruyor** — silinseydi arşivlenmiş ölçümler yeniden üretilemezdi (K4).
Yangın/duman/düşme kategorileri **kapsamda kaldı**: bunlar İSG'nin de olaylarıdır.

---

## 3. ⚠ Ölçüm sırasında bulunan KUSUR — olumsuzlama kapısı

D28 olumsuzlama kapısı (`_OLUMSUZ_RE`) `gözlen` kökünü tanıyor, ama model
neredeyse her zaman **"gözlemlenmedi"** yazıyor (gövde `gözlemlen`). 71 sonuç
dosyası tarandı: `gözlemlenmedi` **477**, `gözlemlenmemiş` 35,
`gözlemlenmemektedir` 8 geçiş — **üçü de kapıdan kaçıyor**.
(`tespit edilmedi` 984 kez geçiyor ve **doğru** yakalanıyor; kusur yalnızca bu gövdede.)

**Sonucu:** modelin

> *"Görüntülerde herhangi bir tehlike, kaza, **yetkisiz giriş** veya anormal
> davranış **gözlemlenmedi**."*

cümlesi, içindeki `yetkisiz` kelimesi yüzünden **doğru kategori adlandırması**
sayılıyordu. Yani model *"hiçbir şey yok"* derken puan alıyordu.

**Ölçülen büyüklük (yeniden skorlama, GPU'suz):**

| Koşu | D28 kapısı | Onarılmış kapı | Fark |
|---|---|---|---|
| Taze A1 (varsayılan, n=100 anomali) | 26/100 | **5/100** | −21 |
| 26 Tem, kurallar AÇIK (n=100) | 42/100 | **25/100** | −17 |

**K2/K4 uyumu:** eski kapı **değiştirilmedi**; `match_category` varsayılan olarak
onu kullanmaya devam ediyor ve arşiv birebir yeniden üretilebiliyor. Onarılmış
kapı `benchmark/rescore.py`'de **5. kural** olarak yan yana raporlanıyor.
Yeni yazılan İSG ölçümü (`isg_match`) arşiv yükü taşımadığı için **baştan**
onarılmış kapıyı kullanır.

**Ek düzeltme:** `rescore.py` hat doğrulaması D28 **sonrası** her dosyada sahte
`!!! TABLO ŞÜPHELİ !!!` alarmı veriyordu — kural 1'i (eski) `category_match`
alanıyla karşılaştırıyordu, oysa o alanı D28 sonrası **yeni** kural dolduruyor.
Artık `category_match_eski` ile karşılaştırıyor; iki dosyada da 100/100 **TAMAM**.

---

## 4. Eklenen araçlar

| Dosya | İş |
|---|---|
| `benchmark/isg_rescore.py` | İnce taneli İSG yeniden skorlama — **GPU gerekmez**, arşive geriye dönük uygulanır |
| `benchmark/merge_arms.py` | Kol kol koşulmuş sonuçları birleştirir (§9 termal önlemi); özet `eval_clips.py` ile **birebir** formüllerle yeniden hesaplanır |
| `benchmark/stats_utils.fisher_exact_p` | Eşleşmemiş iki oran için Fisher tam testi |
| `tests/test_isg_labels.py` | Taksonomi + kalıp + hizalama + kusur onarımı testleri |
| `tests/test_merge_arms.py` | **Yuvarlak yolculuk**: n=200 arşivi ikiye böl → birleştir → özet orijinalle birebir |

`merge_arms.py`'nin formülleri `eval_clips.py`'den **kopyadır**; "iki kaynak-doğru"
riskini kapatmak için `tests/test_merge_arms.py` gerçek bir arşiv koşusunu ikiye
bölüp birleştiriyor ve üretilen özeti dosyanın **kendi** `summary` alanıyla alan
alan karşılaştırıyor. Formüller ayrışırsa test kırmızı yanar.

---

## 5. Sonuçlar

### 5.1 A kolu — VARSAYILAN yapılandırma (n=200, T=0, 2026-08-16)

Dosyalar: `eval_20260816_111114.json` (Anomali) + `eval_20260816_113306.json` (Normal)
→ birleşik: `isg_A_varsayilan_20260816.json`

| Metrik | Değer [Wilson %95] | 26 Tem aynı yapılandırma |
|---|---|---|
| Anomali recall | **%28** [%20–%38] (28/100) | %20 |
| Kategori eşleşme — **eski** kural | **%10** [%6–%17] | **%9** ← replike oldu |
| Kategori eşleşme — yeni (D28) kural | %26 [%18–%35] | — |
| Kategori eşleşme — **onarılmış kapı** | **%5** | — |
| Risk kalibrasyonu (≥Yüksek) | **%1** (1/100) | — |
| Normal FP (dar) | %5 [%2–%11] | %4 |
| Normal FP (operasyonel) | %22 [%15–%31] | — |
| Normal risk=Düşük | %90 [%83–%95] | — |
| Gecikme medyan | 11,6 sn (~1,6 sn/video-sn) | — |

**Ölçüm zinciri sağlam:** eski kuralla %10 vs arşivdeki %9 — arşivle bağ kopmamış.
Recall'daki +8 puan **tam gürültü tabanında** (§7.1: %8); tek koşuda **kanıtlanamaz**.

**Standart ML metrikleri (gevşek tanım, n=200, prevalans 0,50):**

| | |
|---|---|
| Precision / Recall | 0,560 / 0,280 |
| Specificity | 0,780 |
| F2 (güvenlikte ana metrik) | **0,311** |
| Balanced accuracy | 0,530 |
| **MCC** | **0,069** |
| Cohen κ | 0,060 |

> **MCC 0,069 · κ 0,060 → varsayılan yapılandırmada güvensiz/güvenli ayrımı
> pratikte ŞANS DÜZEYİNDE.** Accuracy 0,53 bunu gizler; §7.6'nın "dengesizlikte
> accuracy yanıltıcı, MCC ve F2 kullan" kuralı burada birebir doğrulandı.

### 5.2 İnce taneli görünüm — kaba metriğin gizlediği

| Sınıf | Kaba ikili (kayıtlı) | Sözcüksel (ince) | Operasyonel | Ayırt edici | **Tam doğru** |
|---|---|---|---|---|---|
| class0 yürüme yolu ihlali | %28 (7/25) | **%0** (0/25) | %36 | %16 | **%0** |
| class1 yetkisiz müdahale | %20 (5/25) | **%0** (0/25) | %28 | %4 | **%0** |
| class2 açık pano kapağı | %28 (7/25) | **%0** (0/25) | **%0** | %0 | **%0** |
| class3 forklift aşırı yük | %28 (7/25) | %4 (1/25) | %16 | %0 | %4 |

`class2`: 25 klibin **23'ünde hiç olay üretilmiyor**; hiçbirinde "pano/panel/kapak"
kelimesi geçmiyor. Bunun **eşleştirici hatası olmadığı** ayrı bir testle
kanıtlandı (`tests/test_isg_labels.py` test 10).

**Eşli ayırt etme (aynı sahne/kamera/ekipman, fark yalnızca davranış):**

| Karşılaştırma | TPR | FPR (güvenli eşi) | Fark | Fisher p | Karar |
|---|---|---|---|---|---|
| class0 vs class4 | %0 | %0 | +0 | 1,00 | **ayrım kanıtlanamadı** |
| class1 vs class5 | %0 | %4 | −4 | 1,00 | **ayrım kanıtlanamadı** |
| class2 vs class6 | %0 | %0 | +0 | 1,00 | **ayrım kanıtlanamadı** |
| class3 vs class7 | %4 | %0 | +4 | 1,00 | **ayrım kanıtlanamadı** |

Arşiv koşusunda (26 Tem, **kurallar açık**) aynı tablo: p = 0,70 / 1,00 / 1,00 / 0,14
— orada da dördünde de ayrım kanıtlanamamıştı.

### 5.3 Kalıp listesi çok mu dar? — denetlendi, HAYIR

"Kaba=True ama ince=False" olan klipler tek tek okundu. İki kaynak çıktı:

1. **Olumsuzlama kusuru** (§3) — "hiçbir şey gözlemlenmedi" cümleleri.
2. **Model başka bir şey anlatıyor.** Örnekler (26 Tem, kurallar açık):
   `class2` klibinde *"Yetkisiz kişi makineye müdahale ediyor"*,
   `class2` klibinde *"Güvenlik yolu dışına çıkan kişi"*,
   `class0` klibinde *"Ortamda yoğun duman oluşumu"*.

Yani kaçırılanlar **farklı ifadeyle anlatılmış aynı tehlike değil**; model
etiketli tehlikeye değil, **genel bir İSG anlatısına** tepki veriyor.
Kalıp listesi genişletilerek kapatılabilecek bir boşluk **değildir**.

### 5.4 B kolu — `facility_rules` AÇIK (anomali kolu, n=100)

Dosya: `eval_20260816_115736.json`

**Arşivle birebir replikasyon:**

| Metrik | Taze B1 (16 Ağu) | 26 Tem kurallar-açık |
|---|---|---|
| Anomali recall | **47/100** | **47/100** ← birebir |
| Kategori eşleşme (eski kural) | **33/100** | **33/100** ← birebir |
| Risk kalibrasyonu (≥Yüksek) | 10/100 | 10/100 ← birebir |

Üç metrikte de birebir aynı sayı — 21 gün arayla, ara sürümlerden sonra.
Ölçüm hattının kararlılığı için güçlü kanıt.

### 5.5 A vs B — ÖN-KAYITLI EŞİKLER (McNemar exact, eşleştirilmiş, n=100)

| Metrik | A (varsayılan) | B (kurallar) | Fark [GA] | p | Karar |
|---|---|---|---|---|---|
| Anomali recall | %28 | %47 | **+19** [+6, +32] | **0,0094** | **H1 GEÇTİ** |
| Kategori — *D28 kapısı* | %26 | %31 | +5 [−7, +17] | 0,5114 | — |
| Kategori — **onarılmış kapı** | %5 | %19 | **+14** [+5, +23] | **0,0043** | **H2 GEÇTİ** |
| İSG **tam doğru** | %1 | %16 | **+15** [+8, +23] | **0,0001** | — |

> ### ⭐ EN ÖNEMLİ BULGU — kusurlu metrik GERÇEK ETKİYİ GİZLİYORDU
>
> Kırık D28 kapısıyla bakıldığında kural enjeksiyonunun kazancı
> **+5 puan, p=0,51 → "kanıtlanamaz"** görünüyor.
> Onarılmış kapıyla **+14 puan, p=0,0043 → ANLAMLI**.
>
> Sebep: kırık kapı **A kolunu şişiriyordu** (5/100 yerine 26/100), çünkü A kolunda
> model çoğunlukla *"hiçbir şey gözlemlenmedi"* diyor ve bu cümleler yanlışlıkla
> "doğru adlandırma" sayılıyordu. Yani ölçüm kusuru yalnızca skoru yükseltmiyor —
> **taban çizgisini şişirerek gerçek bir müdahalenin etkisini görünmez yapıyordu.**
>
> Bu, §7.3'ün ("metriği değiştirirsen eski skoru silme, yan yana raporla")
> neden kritik olduğunun somut örneğidir.

### 5.6 İnce taneli: kural enjeksiyonu hangi sınıfa yarıyor?

**Sözcüksel adlandırma / tam doğru (n=25 her sınıf):**

| Sınıf | A (varsayılan) | B (kurallar) | Değişim |
|---|---|---|---|
| class0 yürüme yolu ihlali | %0 / %0 | **%20 / %20** | +20 |
| class1 yetkisiz müdahale | %0 / %0 | %8 / %8 | +8 |
| class2 açık pano kapağı | %0 / %0 | **%0 / %0** | **0 — hiç değişmedi** |
| class3 forklift aşırı yük | %4 / %4 | **%36 / %36** | +32 |

**`class2` (açık pano kapağı) DÖRT ölçümün dördünde de %0:**
varsayılan (taze), kurallar açık (taze), varsayılan (26 Tem), kurallar açık (26 Tem).
Model 100 pano klibinin hiçbirinde "pano/panel/kapak" kelimesini kullanmıyor.
Kural metninde madde 3 **açıkça** *"Elektrik pano/kontrol kapakları her zaman KAPALI
olmalıdır"* dediği halde. Bu bir **bilgi eksikliği değildir** — kural verildi, yine %0.

### 5.7 H3 — kural enjeksiyonunun BEDELİ (normal klipler, n=100)

| | A (varsayılan) | B (kurallar) | Fark [GA] | p |
|---|---|---|---|---|
| Normal klip TEMİZ (hiç olay/tetik yok) | %78 | %60 | **−18** [−28, −7] | **0,0021** |
| Normal FP (operasyonel) | %22 | %40 | +18 | — |
| Normal FP (dar: sev/risk≥Y) | %5 | %7 | +2 | — |
| Normal risk=Düşük | %90 | %83 | −7 | — |

**H3 GEÇTİ** — maliyet gerçek. 26 Temmuz'daki ölçüm: %83 → %65, yani **−18 puan**
(p=0,0014). Bugün **−18 puan** (p=0,0021). Bedelin büyüklüğü de replike oldu.

### 5.8 ⚠ EN DERİN BULGU — kural enjeksiyonu AYIRT ETMEYİ İYİLEŞTİRMİYOR

| Metrik (n=200, gevşek tanım) | A (varsayılan) | B (kurallar) |
|---|---|---|
| Recall | %28 | **%47** |
| FPR (normalde yanlış alarm) | %22 | **%40** |
| Precision | 0,560 | 0,540 |
| F2 (recall ağırlıklı) | 0,311 | **0,483** |
| Balanced accuracy | 0,530 | 0,535 |
| **MCC** | **0,069** | **0,071** |
| Cohen κ | 0,060 | 0,070 |

> Kural enjeksiyonu recall'ı %28 → %47 çıkarıyor, ama yanlış alarmı da
> %22 → %40 çıkarıyor — **neredeyse aynı oranda**. Sonuç: **MCC 0,07'de sabit.**
>
> Yani model kuralla birlikte **daha çok olay bildiriyor**, ama güvensizi
> güvenliden **daha iyi ayırt etmiyor**. Etkisi bir eşik düşürme etkisidir,
> bir yetenek kazancı değil.
>
> **F2'nin 0,31 → 0,48 yükselmesi gerçek ve operasyonel olarak anlamlıdır**
> (güvenlikte kaçırma yanlış alarmdan pahalıdır — §7.6). Ama F2 tek başına
> raporlanırsa yanıltır: MCC dört hücreyi de kullandığı için gerçeği söyler.
> **İkisi birlikte raporlanmalıdır.**

Eşli ayırt etme kurallar açıkken de aynı sonucu veriyor — **dört sınıfın hiçbirinde
ayrım kanıtlanamadı**:

| Karşılaştırma | TPR | FPR (güvenli eşi) | Fark | Fisher p |
|---|---|---|---|---|
| class0 vs class4 | %20 | %8 | +12 | 0,4174 |
| class1 vs class5 | %8 | %20 | **−12** | 0,4174 |
| class2 vs class6 | %0 | %0 | +0 | 1,0000 |
| class3 vs class7 | %36 | %12 | +24 | 0,0955 |

`class1` **ters yönde**: model "yetkisiz müdahale" dilini **yetkili** müdahale
kliplerinde daha sık kullanıyor. `class3` en umut verici (+24 puan) ama n=25'te
p=0,096 — **kanıtlanamaz**. Sınıf düzeyinde bir şey kanıtlamak için n büyümeli
(§5.2 Boşluk 3; HANDOFF §6.4'teki kalan 491 klip tam da bunun için).

### 5.9 GÜRÜLTÜ TABANI — A vs A′ (aynı yapılandırma, iki koşu, ~1,5 sa arayla)

§7.2 gereği koşuldu (`eval_20260816_125336.json`). **Aynı** yapılandırma, **aynı**
klipler, `temperature=0` — aradaki her fark saf çalışma-arası değişkenliktir.

| Metrik | A | A′ | **gürültü** | klip-düzeyi çevirme | A/B kazancı | oran |
|---|---|---|---|---|---|---|
| Anomali recall | %28 | %20 | **8 puan** | 24 | +19 | **2,4×** |
| Kategori — *D28 kapısı* | %26 | %27 | 1 puan | **31** | +5 | 5× |
| Kategori — **onarılmış** | %5 | %5 | **0 puan** | **8** | +14 | **≫** |
| İSG tam doğru | %1 | %0 | 1 puan | 1 | +15 | 15× |

**Üç sonuç:**

1. **Recall gürültü tabanı %8** — HANDOFF §7.1'deki değeri bu sette **birebir
   doğruladı**. A/B'deki +19 puan bunun **2,4 katı** ⇒ sağlam.
2. **Taze A recall'ünün %28'i, gürültü bandının üst ucuymuş.** A′ tam %20 verdi —
   yani arşivdeki %20 ile aynı. Gerçek taban ~%20–28 arasında, ortası ~%24.
   Daha önce "arşivle +8 fark var" derken bunu gürültü sanmıştım; **doğrulandı.**
3. **Onarılmış kapı SADECE daha doğru değil, daha KARARLI.** İki koşu arasında
   D28 kapısı **31 klip çeviriyor** (net +1'de sönümleniyor), onarılmış kapı
   yalnızca **8**. Yani onarım metriği klip düzeyinde ~4× stabilize ediyor.
   Bu, "onarım skoru düşürüyor" itirazına verilecek asıl cevaptır: skor düştü ama
   **ölçüm aleti sağlamlaştı** — ve zaten §5.5'te gerçek etkiyi bu sayede gördük.

`benchmark/isg_ab.py --gurultu` bu kipi destekler: aynı-yapılandırma koşularında
hipotez kararı **basmaz**, gürültü tabanı raporlar (yanlış okumayı engeller).

---

## 6. Ölçüme dayalı öneriler

### Ö1 — `facility_rules` dağıtımda AÇIK olmalı, ama **abartılmadan**

Şu an **varsayılan boş**. Ölçülen kazanç (n=100, eşleştirilmiş):
recall **+19 puan** (p=0,0094) · adlandırma **+14 puan** (p=0,0043) ·
İSG tam doğru **+15 puan** (p=0,0001) · F2 0,31 → 0,48.
26 Temmuz'da aynı yön ve büyüklük; **iki bağımsız ölçüm, 21 gün arayla**
→ §7.2'nin tekrar koşusu şartı bu iddia için **sağlandı**.

⚠️ **İki çekince, birlikte söylenmeli:**
1. **Bedeli ölçüldü** (§5.7): normal kliplerde temizlik %78 → %60 (−18 puan,
   p=0,0021). Operatöre giden yanlış alarm **iki katına** çıkıyor.
2. **Ayırt etmeyi iyileştirmiyor** (§5.8): MCC 0,069 → 0,071. Kazanç bir
   **eşik düşürme** etkisidir, yetenek kazancı değil.

Yani "kuralları aç" doğru bir karardır (güvenlikte kaçırma pahalıdır), ama
**"sistem İSG ihlallerini tanıyor" diye sunulamaz.** Sunumda F2 ve MCC
yan yana verilmelidir.

### Ö2 — `class2` (pano kapağı) VLM işi DEĞİL — **KANITLANDI**

Dört ölçümün dördünde %0. Kural verilmesi hiçbir şey değiştirmedi. Peki bu
**algı sınırı** mı yoksa model sadece **söylemiyor** mu? İki prob koşuldu:

**Prob 1 — ajan üzerinden sorgu** (`scripts/probe_pano.py`, n=16):
16/16 klipte *"Bu bilgi videodan çıkarılamadı."*
⚠️ Ama bu **kesin değil**: `query_answer` alanı `dilajan/prompts.py:276` gereği
yalnızca *"yukarıda listelenen olaylara DAYANARAK"* üretiliyor. Yani bu prob
modelin algısını değil, **olay çıkarımı boru hattını** ölçtü.

**Prob 2 — VLM'e DOĞRUDAN soru + zorunlu seçim** (`scripts/probe_pano_dogrudan.py`):
Ajan boru hattı atlandı; `VLMClient` ile ilk/orta/son kare gönderildi ve vLLM'in
**`guided_choice`** kısıtlı kod çözümüyle model `AÇIK · KAPALI · GÖRÜNMÜYOR`
arasından **seçmeye zorlandı** (temperature=0, kaçamak cevap imkânsız).

| Gerçek durum | n | Modelin cevabı |
|---|---|---|
| class2 — kapak **AÇIK** | 10 | **KAPALI ×10** |
| class6 — kapak **KAPALI** | 10 | **KAPALI ×10** |

**20/20 klipte "KAPALI".** Doğruluk 10/20 = %50 — dengeli bir sette **sabit cevabın**
verdiği değerin ta kendisi. Fisher p = 1,00. Model pano kapağının durumunu
**hiç okumuyor**; bir ön-kabul ("panolar genelde kapalıdır") üretiyor.

> ### ⇒ SONUÇ: bu bir ALGI SINIRIDIR, ifade veya prompt sorunu DEĞİL.
> Sorgu ile çözülemez. HANDOFF §6.2'nin KKD için verdiği mimari kararın **aynısı**
> geçerlidir:
>
> *"KKD tespiti VLM işi DEĞİL, YOLO işidir. Deterministik doğrulayıcı olarak
> ekleyin, metin enjeksiyonu olarak değil."*
>
> Pano kapağı da aynı sınıf problemdir: **küçük, sabit konumlu, ikili görsel durum**.
> Bu bulgu, §6.2'deki KKD kararının **bağımsız bir doğrulamasıdır**: aynı model
> ailesi, aynı çözünürlük, aynı tesis — ve aynı başarısızlık türü.

*Yan kazanç:* HANDOFF §11'de "denenmedi" diye duran **`guided_choice` kolu**
bu probla kapandı. Kısıtlı kod çözümü çalışıyor ve teşhisi kesinleştiriyor —
ama burada gösterdiği şey, modelin **bilmediğini** kesin biçimde söylemesidir.

### Ö3 — `class0` (yürüme yolu) geometrik problem, anlamsal değil

Model "güvenlik yolu dışında" dilini **güvenli** yürüme yolu kliplerinde de
kullanıyor (§5.2 eşli tablo). Ama depoda **zaten** bir çözüm var ve İSG'de
kullanılmıyor:

> `dilajan/config.py:122` `restricted_zones` — YOLO-geofence, 3×3 ızgara.
> *"Deterministik (VLM zone-reasoning güvenilmez); opt-in."*

Savunma perimetresi için yazılmış. İSG koşulları **daha da uygun**: kamera sabit
(2 IP kamera, tek tesis), yürüme yolu görüntüde **sabit konumda**. Yani sınır
bir kez tanımlanır ve kişi-kutusu testi deterministik olur.

### Ö3b — `class3` (forklift aşırı yük) tek umut verici sınıf ama n yetmiyor

Kurallar açıkken tek doğru okunan sınıf: sözcüksel %36, tam doğru %36,
eşli ayırt etme **+24 puan** — ama n=25'te **p=0,0955**, yani kanıtlanamaz.
`data/industrial`'da class3'ün **56 klibi** var (25'i kullanılıyor).
HANDOFF §6.4 (kalan 491 klibi değerlendirmeye katma) tam da bu sınıfı
kanıtlanabilir hale getirir. `benchmark/labels.py` artık `class0..class7`
dizin adlarını da çözdüğü için **bu iş artık kod değişikliği gerektirmiyor**.

### Ö4 — Asıl darboğaz TESPİT değil, ÖNEM DERECESİ

| | A (varsayılan) | B (kurallar) |
|---|---|---|
| Anomali recall | %28 | %47 |
| Risk ≥ Yüksek | **%1** | **%10** |

Model tehlikeyi adlandırdığında bile **önem derecesini Düşük veriyor** → risk tabanı
Düşük kalıyor → **sevk kapısı hiç açılmıyor**. Bu zaten `dilajan/config.py:165`'te
"kusur #2" olarak kayıtlı ve prompt-seviyesi çözümü **denenip başarısız olmuş**
(10/100, McNemar p=0,267).

**Sonuç:** İSG veri zenginleştirmesi (§6.2–6.4) tespit oranını yükseltse bile,
önem derecesi düzelmeden **operasyonel çıktı değişmez**. Veri eklemeden önce
bu kapının açılması gerekir.

---

## 6b. GENELLEME — iSafetyBench (bağımsız kaynak, D34)

`benchmark/isafety_mcq.py` · `guided_choice` ile 16 şıktan zorunlu seçim ·
temperature=0 · klip başına **1 soru** (aynı klibin birden çok sorusu bağımsız
değildir — pseudo-replikasyon önlemi).

| Kol | Doğruluk [Wilson %95] | n |
|---|---|---|
| **hazard** (tehlikeli) | **%55,3 [%47,3–%63,1]** | 150 |
| **normal** (rutin) | **%48,7 [%40,8–%56,6]** | 150 |
| *şans tabanı* | *%6,3* | *16 şık* |

**İkisi de şans tabanının ~8–9 katı.** Bu, **bağımsız bir kaynakta** (farklı ülke,
farklı tesisler, YouTube görüntüsü) elde edildi → **§5.2 Boşluk 1 (tek kaynak)
için ilk gerçek genelleme kanıtı**.

> ⚠️ **Metrik uyarısı:** makaledeki "Ovis2-8B %53,4 F1" **çok-etiketli** görevin
> metriğidir; buradaki sayı **tek-etiketli doğruluk**tur. **Aynı sayı değildir**,
> doğrudan karşılaştırılmamalıdır. Aynı *biçimde* (MCQ) ölçüldüğü için
> mertebe olarak konumlandırma yapılabilir, sıralama iddiası yapılamaz.

> ⚠️ **Alan uyarısı:** klipler YouTube kaynaklıdır (değişken açı, kurgu, el
> kamerası); dağıtım ortamımız sabit-kamera CCTV. Bu bir **genelleme stres
> testidir**, "başka bir fabrikada da böyle olur" kanıtı değildir.

### ⭐ Bu sonucun asıl söylediği: darboğaz TANIMA değil

| Ölçüm | Sonuç |
|---|---|
| iSafetyBench MCQ (şıklar verilmiş, bağımsız kaynak) | **%55** |
| Kendi tesisimizde ince taneli **kendiliğinden adlandırma** | **%0–4** |
| Kendi tesisimizde güvenli/güvensiz **ayırt etme** | **şans düzeyi** (MCC 0,07) |

Model **tanıyabiliyor** — ama:
1. **açık uçlu üretimde** o bilgiyi kendiliğinden dile getirmiyor, ve
2. **politikaya bağlı** yargılarda (bu tesiste yürüme yolu nerede?) kural olmadan
   karar veremiyor — ki bu bir model kusuru değil, **bilgi eksikliğidir**.

Bu, §6'daki öneri sırasını doğrular: model büyütmek/değiştirmek değil,
**kural enjeksiyonu + deterministik doğrulayıcılar + önem derecesi kapısı**
doğru yatırım yönüdür.

---

## 7. Bu ölçümün KANITLAMADIĞI şeyler

Ön-kayıtta (§4) yazılanlar aynen geçerli; ölçüm sonrası eklenenler:

1. ~~A ve B kollarının kendi tekrarları koşulmadı.~~ ✅ **A′ koşuldu (§5.9).**
   Gürültü tabanı ölçüldü ve üç A/B kazancının da tabandan 2,4×–15× büyük olduğu
   gösterildi. ⚠️ **B kolunun kendi tekrarı (B vs B′) hâlâ koşulmadı** — ama
   B, 26 Temmuz'un kurallar-açık koşusuyla üç metrikte **birebir** aynı çıktı
   (47/100 · 33/100 · 10/100), bu de-facto bir replikasyondur.
2. **Sınıf düzeyinde hiçbir şey kanıtlanmadı.** n=25'te Wilson aralıkları
   ~±%18 genişliğinde. `class3`'ün +24 puanı bile p=0,096.
3. **`class2` bulgusu n=20'lik bir teşhis probuna dayanıyor.** Sonuç kesin
   görünüyor (20/20 sabit cevap) ama tam kol koşulmadı.
4. **Genelleme yok.** Tek tesis, iki kamera, 39 gün, tek mevsim.
5. **`eval_defense`, `industrial`'dan örneklenmiştir** — `industrial` üzerinde
   ince ayar yapılırsa bu set **anında kirlenir**.
