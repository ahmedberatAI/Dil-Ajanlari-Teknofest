# KKD (baret) deterministik doğrulayıcı — D34

**Tarih:** 2026-08-16 · **Kapsam:** HANDOFF §6.2
**Önceki:** [`isg_taksonomi_hizalamasi_2026-08-16.md`](isg_taksonomi_hizalamasi_2026-08-16.md) (D33)

---

## 1. Neden bu iş — ve neden VLM ile değil

HANDOFF §5.2, KKD'yi **"İSG'nin en yaygın senaryosu, jürinin ilk test edeceği şey"**
diye işaretlemiş ve bizde hiç yoktu.

§6.2 mimari kararı nettir: **KKD tespiti VLM işi değil, YOLO işidir.** Ham nesne
listesini VLM'e "kanıt" diye vermek yanlış alarmı **%0 → %12** yükseltmişti.

**D33 bu kararı bağımsız olarak doğruladı.** `guided_choice` ile zorunlu seçim
yaptırıldığında model, açık/kapalı pano kapağı sorusunda **20 klibin 20'sinde de
"KAPALI"** dedi — 10'u gerçekte açıkken. İnce, ikili görsel durum bu VLM'in
okuyabildiği bir şey değil. **Baret var/yok tam olarak aynı problem sınıfıdır.**

Yani bu doğrulayıcı bir tahmin üzerine değil, **ölçülmüş bir sınır** üzerine kuruldu.

---

## 2. Veri

`scripts/get_ppe.py` → `scripts/ppe_coco2yolo.py`

| | eğitim | doğrulama | test |
|---|---|---|---|
| görsel | 14.089 | 4.019 | 2.035 |
| kutu | 39.082 | 11.298 | 5.557 |

Sınıflar: `0=baret_var` (baretli kafa) · `1=baret_yok` (**baretsiz kafa — ihlal sinyali**)
Eğitim dağılımı: baret_var 29.285 · baret_yok 9.797

Kaynaklar (ikisi de **CC BY 4.0**, eğitimde kullanılabilir):
`keremberke/hard-hat-detection` + `keremberke/construction-safety-object-detection`

### ⚠️ Yelek neden yok — ölçülmüş gerekçe

Yelek kutuları tüm bölümlerde toplam **91** (baret: 55.937). 66'sı eğitimde.
Bu sayıyla eğitilen bir sınıf **deterministik doğrulayıcı** olamaz — ve
**güvenilmez bir dedektör, hiç dedektör olmamasından kötüdür**: bu sistemde
yanlış alarm en pahalı hatadır (sevk kapısının varlık sebebi, HANDOFF §3).

Veri silinmedi. Yelek için yeterli ve izin-verici lisanslı bir set bulununca eklenir.

### ⚠️ Alan farkı

Eğitim verisi **şantiye**, tesisimiz **üretim/imalat**. Deterministik bir dedektör
için bu fark bir VLM'in sahne anlamasına göre çok daha küçüktür (baret bir kafanın
üzerindedir, şantiyede de fabrikada da) — ama **sıfır değildir**.
En iyi alan eşleşmesi olan **SH17** (üretim sanayi, 17 sınıf) **CC BY-NC-SA**
olduğu için elendi; aynı ShareAlike tuzağı.

---

## 3. Mimari — nereye, nasıl bağlandı

Desen `restricted_zones` geofence'i ile **birebir aynı**: dedektör kendi karar
verir, sonuç **tipli bir olaya** dönüşür. Ham çıktı VLM'e metin olarak **enjekte
edilmez**.

```
perceive → ... → _kanit_adlandirma → geofence → araç → kalabalık → [KKD] → olaylar
```

**Konum gerekçesi:** blok `_kanit_adlandirma`'dan **sonradır** — böylece LLM
adlandırması buradaki sabit metni bozamaz (mevcut deterministik dedektörlerle aynı
gerekçe).

### Karar kuralı (FP'ye karşı bilerek muhafazakâr)

* Bir kare "ihlalli": o karede `baret_yok` kutusu var.
* Segment ihlal: ihlalli kare sayısı **≥ `ppe_min_kare`** (varsayılan **2**).
  **Tek kare yetmez** — kafa dönüşü/bulanıklığın ürettiği geçici yanlış tespitler elenir.
* Sahnede baretli kişilerin olması ihlali **aklamaz** (biri baretliyse diğerinin
  baretsizliği geçerli kalır).

### ⚠️ Ağırlık depoda YOK — yeniden üretilir

`.gitignore` `*.pt` deseniyle **tüm** ağırlıkları dışlar (`yolo11n.pt`,
`yolo11n-pose.pt` de depoda değildir). `yolo11n-ppe.pt` bizim ürettiğimiz olduğu
için indirilebilir de değildir. Bu bilinçli bir tercihtir ve projenin veri
politikasıyla tutarlıdır: **her şey betikle yeniden üretilir, hiçbir büyük
dosya depoya girmez.**

Yeniden üretim (sabit tohum `seed=2026`, deterministik):

```bash
python scripts/get_ppe.py && python scripts/ppe_coco2yolo.py && python scripts/train_ppe.py
```

Ağırlık yoksa dedektör **sessizce devre dışıdır** (K3 fail-open) ve ilk kullanımda
`stderr`'e ne yapılacağını yazar. `scripts/hazirlik_kontrol.py` bunu uyarı olarak
raporlar.

### Ayarlar — hepsi varsayılan KAPALI (K2)

| Ayar | Varsayılan | Not |
|---|---|---|
| `ppe_detection` | **False** | Kapalıyken blok **tek satır** çalışmaz |
| `ppe_conf` | 0.45 | dedektör güven eşiği |
| `ppe_min_kare` | 2 | geçici FP filtresi |
| `ppe_severity` | Yüksek | KKD ihlali iş kazası riski |
| `ppe_dispatch` | **False** | **sevk yolu kapalı** — aşağıya bakın |

---

## 4. ⚠️ SEVK MASKESİ — iki terimli, tek terim yetmez

`ppe_dispatch=False` iken KKD olayı **operasyonel çağrı açmaz**. Bu iki maskeyle
sağlanır ve **ikisi de gereklidir**:

1. **`max_intrinsic`'ten çıkarma** — KKD olayı sevk eşiğini tek başına aşamaz.
2. **Risk terimini maskeleme** — risk tabanı severity'yi risk'e taşıdığı için,
   yalnızca (1)'i yapmak `ppe_dispatch=False` sözünü **yalan çıkarırdı**.

Bu, `policy_dispatch`'te **ölçülerek** öğrenilmiş bir tuzaktır
(`graph.py` üç terimli kapı yorumu); aynı hata burada tekrarlanmadı.

**Neden kapalı:** dedektörün **tesis alanındaki** doğruluğu henüz ölçülmedi
(eğitim şantiye, tesis üretim). Önce ölç, sonra sevk yetkisi ver.
KKD olayı operatöre **görünür** (olay listesinde, riskte) ama ekip çağırmaz.

---

## 4b. ⚠️ Uygulama sırasında bulunan hata — sessiz maske kaybı

Sevk maskesi `ppe_src` adlı **şema-dışı** bir işarete dayanır (`policy_prev` /
`evidence_prev` ile aynı desen). Ama `graph._dedupe_events`, birleştirdiği olayları
**`Event(...)` ile yeniden kuruyor** ve şema-dışı alanları **düşürüyor** — kodda
yalnızca `evidence_prev` elle taşınıyordu.

**Sonucu ne olurdu:** KKD olayı, aynı kategoride (Güvenlik) ve ortak kelimeli bir
VLM olayıyla birleşseydi `ppe_src` **kaybolur**, `act()` maskesi o olayı göremez ve
**`ppe_dispatch=False` sözü sessizce yalan olurdu** — yani KKD tek başına ekip
çağırabilirdi. Birleşme koşulu zor değil: aynı kategori + tek ortak anlamlı kelime
(kısa olaylarda) yeterli; "personel" gibi kelimeler VLM çıktısında sık.

**Düzeltme (iki parça):**
1. KKD olayları VLM olaylarıyla **birleştirilmez** (kapı `_dedupe_events` başında).
   İkinci gerekçe: KKD metni deterministiktir, birleşme "en bilgilendirici metin"
   seçimiyle sabit ifadeyi bozabilirdi.
2. İki KKD olayı birbiriyle birleşebilir; o durumda işaret **açıkça korunur**.

**Kilit:** `tests/test_ppe.py` (7b) — beş kontrol, hem işaretin korunduğunu hem de
KKD dışı olayların **eskisi gibi birleşmeye devam ettiğini** (gerileme yok) sınar.

> Bu, projenin kendi yorumlarında uyardığı tuzağın ta kendisiydi:
> *"`Event(...)` yeniden-kurması onları sessizce düşürürdü."*
> Uyarı yazılıydı; yeni alan eklenirken gözden kaçtı. Test artık bunu kalıcı kılıyor.

---

## 5. Ölçümler

### 5.1 Dedektör doğruluğu — kendi test bölümünde (n=2.035 görsel / 5.557 kutu)

| | mAP50 | mAP50-95 | P | R |
|---|---|---|---|---|
| **tümü** | **0,934** | 0,591 | 0,906 | 0,892 |
| `baret_var` | 0,939 | — | 0,920 | 0,893 |
| **`baret_yok`** (ihlal sinyali) | **0,929** | — | 0,893 | 0,891 |

Eğitim: yolo11n, 40 epoch, seed=2026, batch 64, imgsz 640. Süre ~37 dk (RTX 5090),
maks 85 °C / 150 W. **Çıkarım: 1,1 ms/görüntü.**

> İhlal sınıfının (`baret_yok`) precision ve recall'ı **dengeli** (0,89/0,89) —
> yani dedektör ne alarm yağdırıyor ne de körleşiyor. Bu, deterministik doğrulayıcı
> olmanın ön şartıydı.

⚠️ Bu sayılar **şantiye** görüntüsündedir (eğitim verisinin kendi test bölümü).
Tesis alanındaki doğruluk **bu değildir** — bkz. §5.2.

### 5.2 Tesis alanı kontrolü (`scripts/ppe_tesis_kontrol.py`, n=40)

| Kol | Tetiklenme |
|---|---|
| Anomali (class0-3) | **0/20 (%0)** |
| Normal (class4-7) | **1/20 (%5)** |

**Toplam 1/40 (%2,5).** Alan kayması kaynaklı bir alarm yağmuru **yok** — asıl
risk buydu ve gerçekleşmedi.

⚠️ **Bu bir doğruluk ölçümü DEĞİLDİR.** `data/eval_defense`'te KKD ground-truth
yoktur (Mendeley seti baretle ilgili değil), dolayısıyla recall/precision
hesaplanamaz. Tek tetiklenen klip (`5_te1`, güven 0,49 — eşiğe yakın) gerçek bir
baretsiz personel de olabilir; **etiket olmadan söylenemez**.

Gerçek doğruluk için tesis kliplerinden örnek alınıp **elle etiketlenmelidir** —
kalan iş.

### 5.3 Uçtan uca (`scripts/ppe_uctan_uca.py`, 8 klip × 2 kol, gerçek vLLM)

| Garanti | Sonuç |
|---|---|
| **K2** — bayrak KAPALI iken KKD yapıtı | **YOK** ✅ |
| **Sevk maskesi** — KKD olayı çağrı açtı mı | **AÇMADI** ✅ |
| **K4** — gecikme medyan (kapalı → açık) | 14,1s → 12,6s = **0,89×** ✅ |

Maskenin gerçek koşuda çalıştığının kanıtı: `5_te1` klibinde KKD ihlali bulundu,
risk **Yüksek**'e çıktı — ve **sevk yine de açılmadı** (`sevk=0`). Tasarlanan
davranış birebir bu.

K4'te ölçülebilir maliyet yok: YOLO çıkarımı klip başına **0,07 sn**, analiz
bütçesi ~20 sn. Gecikmedeki 0,89× fark gürültüdür (§7.1).

> ⚠️ **"Byte düzeyinde birebir aynı" iddiası bu yığında yeniden-koşumla
> DOĞRULANAMAZ** — %8 gürültü tabanı aynı yapılandırmanın iki koşusunu bile ayırır
> (A vs A′: 100 klipte 24 çevirme). Doğrulanan şey: **kapalıyken KKD kaynaklı
> hiçbir yapıt üretilmiyor.** Kod düzeyi garanti (erken-dönüş) testlerde kilitli.

---

## 5b. ⚠️ GÖRSEL DENETİM — bu tesiste baret DEĞİL, **YELEK** takılıyor

`scripts/ppe_etiket_hazirla.py` ile üretilen inceleme paketindeki kontak
sayfaları ve yakınlaştırılmış kırpmalar **elle incelendi**. Üç bulgu:

**1. Dedektör tesis verisinde DOĞRU çalışıyor.** Yakınlaştırılmış kırpmalarda
kırmızı kutular tam olarak **baretsiz insan kafalarının** üzerinde
(güven 0,48–0,53). Yanlış pozitif değil — gerçek tespit.

**2. `B_baretli` kovası BOŞ: 0 klip.** Dedektör bu tesiste **hiçbir klipte
baretli kafa bulmadı**. Görsel denetim bunu doğruluyor: işçiler baret takmıyor.

**3. ⭐ Kullanılan KKD **yelek**.** Kontak sayfalarında işçilerin üzerinde
**yeşil hi-vis yelek** açıkça görünüyor — baret yok.

> ### Bunun anlamı: doğru dedektörü eğitmiş olabiliriz ama YANLIŞ SINIF için
>
> Bu bir pres atölyesi; baret muhtemelen **zorunlu değil**. Dolayısıyla
> "baretsiz personel" bu tesiste bir **ihlal olmayabilir** — dedektör doğru
> çalışıyor ama ölçtüğü şey burada anlamlı bir güvenlik olayı değil.
>
> **Bu tesiste anlamlı olan KKD YELEKTİR** — ve yelek tam da veri yetersizliği
> yüzünden (91 kutu) eğitemediğimiz sınıf.
>
> **Sonuç:** KKD önceliği **baret → yelek** olarak değişmelidir. Baret dedektörü
> silinmez (şantiye/inşaat senaryosu için geçerli ve mAP50 0,934) ama **bu
> dağıtım için birincil sınıf değildir**.
>
> Ayrıca bu, `ppe_dispatch=False` kararını **güçlendirir**: doğruluğu yüksek bir
> dedektör bile, tesiste kural değilse yanlış alarm üretir. Sevk kapısı ancak
> tesisin **gerçek KKD kuralı** öğrenildikten sonra açılmalıdır.

## 5c. YELEK dedektörü — eğitildi, **dağıtılmıyor** (ölçülmüş karar)

Bulgu üzerine yelek verisi arandı ve bulundu:
[`LibreYOLO/construction-safety-gsnvb`](https://huggingface.co/datasets/LibreYOLO/construction-safety-gsnvb)
— **CC BY 4.0**, kaynak `data.yaml` içindeki `roboflow.license` alanından birebir teyitli.
`yelek_var` / `yelek_yok` **ayrı etiketli** (ihlal tespiti için şart).

| | kutu |
|---|---|
| önceki elimizdeki | 91 |
| yeni | **2.235** (25×) |
| bunun eğitim bölümü | 1.814 (1.073 var + **741 yok**) |

**Eğitim sonucu (yolo11n, 80 epoch, test bölümü):**

| | mAP50 | P | R |
|---|---|---|---|
| tümü | 0,678 | — | — |
| `yelek_var` | 0,773 | 0,800 | 0,713 |
| **`yelek_yok`** (ihlal) | **0,582** | **0,535** | 0,661 |

Karşılaştırma: baret dedektöründe `baret_yok` P **0,893** / R **0,891**.

### ⛔ KARAR: dağıtılmıyor — eşik taraması

`scripts/yelek_esik_tara.py` güven eşiğini taradı:

| conf | `yelek_yok` P | `yelek_yok` R |
|---|---|---|
| 0,45 | 0,630 | 0,590 |
| 0,65 | 0,721 | 0,508 |
| 0,85 | **1,000** | **0,049** |

**Kabul ölçütü İKİ TARAFLI:** P ≥ 0,85 **ve** R ≥ 0,50. **Hiçbir eşik ikisini
birden sağlamıyor.**

> ⚠️ **Ölçütün ilk hâli tek yanlıydı ve beni yanılttı.** Yalnızca `P ≥ 0,85`
> arandığında tarama `conf=0,85`'i "KULLANILABILIR" işaretledi — ama orada
> **R=0,049**, yani ihlallerin %5'i yakalanıyor. Eşiği yükselttikçe precision
> zaten 1'e gider; bu bir başarı değil, **ölçütün kusurudur**. Düzeltildi.

**Sebep:** yalnızca **741** eğitim kutusu (baret dedektöründe 9.797 vardı).

**Sonuç:** `ppe_kits` varsayılanı **`"baret"`** — yelek opt-in
(`DILAJAN_PPE_KITS="baret,yelek"`). Açılırsa karar-izine **ölçülmüş zayıflığı
yazan bir uyarı** düşer; sessizce güvenilmez olay üretmez.
Ağırlık ve veri **silinmedi** — yeterli veri bulununca yeniden eğitilecek.

**Kalan iş:** yelek için ≥5.000 kutuluk, `yelek_var` / `yelek_yok` ayrı etiketli,
izin verici lisanslı (CC BY 4.0+) veri seti bulmak.

---

## 6. Testler — `tests/test_ppe.py`

| # | Ne korunuyor |
|---|---|
| 1 | **K2**: bayrak varsayılan kapalı; `ppe_dispatch` de kapalı |
| 2 | **K3 fail-open**: ağırlık yok / YOLO patlar / boş girdi → `None`, çökme yok |
| 3 | karar kuralı: tek kare ihlal sayılmaz; karışık sahne ihlal sayılır; **beklenmeyen sınıf adları → karar verme** |
| 4 | **sevk maskesi**: KKD tek başına çağrı açmaz; bağımsız kritik olay açar (maske aşırı geniş değil); `ppe_dispatch=True` opt-in çalışır |
| 5 | **cebir**: KKD olayı yokken dispatch ifadesi eski haliyle özdeş |
| 6 | **K1**: `ppe_src` `model_dump()` anahtarlarına sızmaz |
| 7 | doğrulayıcı sözleşmesi: CONFIRM / REJECT / ABSTAIN |
| 8 | maskelenen olay operatöre **görünür** (silinmez) |
