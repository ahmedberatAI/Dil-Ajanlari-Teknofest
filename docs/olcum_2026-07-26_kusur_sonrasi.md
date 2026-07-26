# Kusur-Giderme Sonrası Ölçümler — 2026-07-26

Bu belge, denetimde bulunan 17 kusurun (K1–K17) giderilmesinden **sonra** yapılan
yeniden-ölçümleri içerir. Buradaki sayılar **kanoniktir** ve daha önceki tüm
senaryo-seti rakamlarının yerine geçer.

> **Neden yeniden ölçtük:** Eski amiral rakam (`senaryo recall %98.7`) 18 pozitiften
> 8'i **donmuş tek-kare PNG** olan bir set üzerinde ölçülmüştü (bkz. K8). Ayrıca 4
> "Normal" klip aslında **güvensiz davranış** içeriyordu (K14/etiket çelişkisi).
> Set düzeltildikten sonra eski sayılar **başka bir sete** ait hale geldi.

Ortam: Qwen3-VL-8B-Instruct-FP8 · vLLM (127.0.0.1) · tek RTX 5090 Laptop (24 GB) ·
tüm oranlar **Wilson %95 güven aralığı** ile.

---

## 1. Senaryo seti — `data/eval_scenario` (25 anomali + 12 normal)

Sonuç dosyası: `benchmark/results/eval_20260726_001725.json`

| Metrik | Sonuç (Wilson %95 GA) | k/n |
|---|---|---|
| Anomali recall (≥1 olay) | **%96 [%80–%99]** | 24/25 |
| Kategori eşleşme | **%96 [%80–%99]** | 24/25 |
| Risk kalibrasyonu (≥Yüksek) | %88 [%70–%96] | 22/25 |
| Normal dar-FP (sev/risk ≥ Yüksek) | **%0 [%0–%24]** | 0/12 |
| **Normal yanlış operasyonel tetik** | **%0 [%0–%24]** | 0/12 |
| Normal risk=Düşük | %100 [%76–%100] | 12/12 |
| Gecikme (medyan) | 17.3 s | ~1.39 s/video-sn |

**Kategori kırılımı** (n küçük — GA ile okuyun):

| Kategori | recall | kategori adlandırma |
|---|---|---|
| Fire (10) | %100 [%72–%100] | %100 [%72–%100] |
| Fall (15, **gerçek video**) | %93 [%70–%99] | %93 [%70–%99] |

### Eski vs yeni (dürüstlük notu)
| | ESKİ (18 anomali, 8'i donmuş PNG) | YENİ (25 anomali, hepsi gerçek video) |
|---|---|---|
| recall | %98.7 (şişirilmiş) | **%96** |
| düşme recall | — (sentetik %100 / gerçek %67) | **%93** (gerçek video) |

Set **büyüdü ve zorlaştı** (18→25 gerçek pozitif) ama recall yalnızca ~3 puan düştü;
düşme tarafında gerçek-video performansı %67 → %93'e **yükseldi** (GMDCSA + URFD birlikte).
Yani eski rakamın fazlası sahte kolaylıktan geliyordu, sistemin kendisi sağlam.

---

## 2. 🔴 Hedef-domain seti — `data/eval_defense` (20 güvensiz + 20 güvenli)

Gerçek üretim tesisi güvenlik kamerası, 1920×1080 (Mendeley `xjmtb22pff`).
Sınıf eşlemesi: `data/industrial/CLASSES.md` (class0-3 = GÜVENSİZ).
**Projenin ilk hedef-domain ölçümü.**

| Metrik | Kurallar **KAPALI** | Kurallar **AÇIK** (`facility_rules`) |
|---|---|---|
| Anomali recall | **%25 [%11–%47]** (5/20) | **%55 [%34–%74]** (11/20) |
| Kategori eşleşme | %10 [%3–%30] (2/20) | **%35 [%18–%57]** (7/20) |
| Risk kalibrasyonu | %10 [%3–%30] | %5 [%1–%24] |
| Normal dar-FP | %5 [%1–%24] (1/20) | %15 [%5–%36] (3/20) |
| Normal yanlış tetik | %5 (1/20) | %15 (3/20) |
| Gecikme | ~1.43 s/vsn | ~1.48 s/vsn |

Sonuç dosyaları: `eval_20260726_002608.json` (kapalı) · `eval_20260726_003531.json` (açık)

### 2.1 Neden saf VLM burada %25'te kalıyor?
Senaryo setindeki olaylar **görsel olarak dramatik** (alev, yere düşen insan).
Buradakiler ise **politika ihlali** — görüntü aynı, ihlal olup olmadığı **tesis kuralına** bağlı:

| sınıf | görüntüde ne görünür | neden tek başına anlaşılamaz |
|---|---|---|
| Safe Walkway Violation | yürüyen bir insan | yürüme yolunun nerede olduğu **kurala** bağlı |
| Unauthorized Intervention | makineye dokunan biri | "yetkisiz" olduğu **kimlik/yetki** bilgisi ister |
| Opened Panel Cover | açık pano kapağı | kapalı olması gerektiği **kural** |
| Carrying Overload w/ Forklift | yük taşıyan forklift | "aşırı" olduğu **kapasite kuralı** ister |

Bu bir model kusuru değil, **bilgi eksikliğidir**: kural verilmeden bu olaylar
prensipte de çıkarılamaz. `facility_rules` mimarisi tam olarak bunun için vardır.

### 2.2 Kural enjeksiyonunun ölçülen etkisi (eşleştirilmiş McNemar, n=20)

| Metrik | Kural lehine | Kapalı lehine | McNemar exact p |
|---|---|---|---|
| Recall | **+8 klip** | +2 klip | p = 0.109 |
| Kategori adlandırma | **+5 klip** | +0 klip | p = 0.063 |
| Normal yanlış tetik (maliyet) | +2 fazla tetik | 0 | p = 0.50 |

**Dürüst yorum:** Nokta tahmininde recall **iki katına** (%25→%55), kategori adlandırma
**3.5 katına** (%10→%35) çıkıyor ve yön tutarlı (8-2 ve 5-0). **ANCAK n=20'de hiçbiri
p<0.05 eşiğini geçmiyor.** Yani şu an elimizdeki dürüst ifade:

> *"Kural enjeksiyonu bu sette recall'ı iki katına çıkardı (5/20 → 11/20); etki yönü
> tutarlı (8 klip iyileşti, 2 klip bozuldu) ancak n=20 istatistiksel anlamlılık için
> yetersizdir (p=0.11). Doğrulama için daha büyük n gereklidir."*

Bu, projenin kendi denetiminde tespit ettiği **istatistiksel güç eksikliğinin**
canlı örneğidir — ve çözümü elimizde: kaynak veri setinde **691 klip** var, bizde
şu an yalnızca 40'ı kullanılıyor.

### 2.3 Maliyet dürüstçe
Kural enjeksiyonu bedelsiz değil: normal kliplerde yanlış operasyonel tetik
%5 → %15'e çıkıyor (2 ek klip). Ayrıca risk kalibrasyonu düşüyor (%10 → %5) —
model daha çok olay buluyor ama bunları risk seviyesine **yansıtmıyor**.
Bu, `facility_rules` ile birlikte risk-eşiği ayarının gerektiğini gösteriyor.

---

---

## 2.5 ⭐ n=200 KESİN A/B — `facility_rules` kazancı İSTATİSTİKSEL OLARAK KANITLANDI

Mendeley setinin **tamamı indirildi** (691 klip / 9.4 GB) ve `eval_defense`
**40 → 200 klibe** çıkarıldı: **100 anomali (class0-3) + 100 normal (class4-7)**,
sınıf başına 25, tabakalı + deterministik (seed=2026), 200/200 benzersiz MD5.
Eski 40-klip set hem `data/eval_defense_v1` olarak donduruldu hem de yeni setin
**üst kümesi** (40/40 sabitlendi) → eski ölçüm karşılaştırılabilir kaldı.

Sonuç dosyaları: `eval_20260726_162613.json` (kapalı) · `eval_20260726_171601.json` (açık)
Test: `benchmark/paired_test.py` — McNemar **exact**, iki-yönlü; fark GA'sı Newcombe (1998) Method 10.

### ANOMALİ klipler (eşleşen n=100)

| Metrik | Kapalı | Açık | b | c | fark (GA) | p_exact | karar |
|---|---|---|---|---|---|---|---|
| **recall** | 20/100 | **47/100** | 8 | 35 | **+%27 [+%15, +%38]** | **4.19e-05** | ✅ **ANLAMLI** |
| **kategori adlandırma** | 9/100 | **33/100** | 3 | 27 | **+%24 [+%14, +%34]** | **8.43e-06** | ✅ **ANLAMLI** |
| risk kalibrasyonu | 5/100 | 10/100 | 4 | 9 | +%5 [-%2, +%13] | 0.267 | — |
| doğru sevk | 5/100 | 10/100 | 4 | 9 | +%5 [-%2, +%13] | 0.267 | — |

### NORMAL klipler (eşleşen n=100) — maliyet tarafı

| Metrik | Kapalı | Açık | fark (GA) | p_exact | karar |
|---|---|---|---|---|---|
| yanlış operasyonel tetik YOK | 96/100 | 92/100 | -%4 [-%10, +%0] | 0.125 | — (kapı tuttu) |
| dar-FP YOK | 96/100 | 92/100 | -%4 [-%10, +%0] | 0.125 | — |
| **operasyonel-FP YOK** | 83/100 | **65/100** | **-%18 [-%28, -%8]** | **0.0014** | ⚠️ **ANLAMLI (kötü)** |
| normal risk=Düşük | 90/100 | 84/100 | -%6 [-%14, +%2] | 0.210 | — |

### Yorum — üç net sonuç

**1. HİPOTEZ DOĞRULANDI (asıl kazanım).** n=20'de yön tutarlı ama anlamsız olan örüntü
(8-2, p=0.109), n=100'de **35-8**'e çıktı ve **p=4.19e-05**'e ulaştı. Kategori adlandırma
için **27-3, p=8.43e-06**. Yani:

> *`facility_rules` kural enjeksiyonu, hedef-domain politika ihlallerinde recall'ı
> %20'den %47'ye (+%27, GA [+%15, +%38]) ve doğru olay adlandırmayı %9'dan %33'e
> (+%24, GA [+%14, +%34]) çıkarır. Her iki kazanç da p<0.0001 düzeyinde anlamlıdır.*

Bu, projenin mimari tercihinin (saf model yerine model + tesise-özgü kural katmanı)
**ölçülmüş kanıtıdır** — artık n=1 sanity testi değil.

**2. HİPOTEZ ÇÜRÜTÜLDÜ (dürüst negatif sonuç).** Kural metnine bilinçli olarak
*"bu ihlaller iş kazası riski taşıdığı için en az YÜKSEK önem derecesi verilmelidir"*
cümlesi eklendi. Buna rağmen risk kalibrasyonu %5 → %10 (p=0.267, **anlamsız**).
**Sonuç: prompt'a severity talimatı yazmak riski yükseltmiyor.** Model ihlali görüyor,
"olay" olarak yazıyor, ama ciddiyet derecesini yükseltmiyor. Risk yükseltme
prompt katmanında değil, **kod tarafında** (severity kalibrasyonu / risk tabanı)
çözülmesi gereken bir iş olarak kalıyor.

**3. MALİYET ÖLÇÜLDÜ ve sınırı belli.** Operasyonel-FP anlamlı biçimde kötüleşti
(%83 → %65 "temiz", p=0.0014): kural açıkken normal kliplerde de daha çok "olay"
işaretleniyor. **AMA kritik olan şu:** dar-FP ve yanlış *operasyonel tetik*
istatistiksel olarak **bozulmadı** (96→92, p=0.125). Yani şiddet kapısı görevini
yapmaya devam ediyor — kural enjeksiyonu operatöre daha fazla *gürültü* getiriyor,
sahte *ekip sevkiyatı* getirmiyor. Dağıtımda kabul edilebilir bir takas.

### Güç kazancı (n=20 → n=200)
| | n=20 | n=200 |
|---|---|---|
| recall GA genişliği | %40 puan | **%16 puan** |
| recall p | 0.109 (anlamsız) | **4.19e-05** |
| kategori p | 0.063 (anlamsız) | **8.43e-06** |

Denetimde tespit edilen "istatistiksel güç yok" kusuru bu ölçümle **fiilen giderildi**.

---

---

## 2.6 ❌ DENENDİ ve BAŞARISIZ: Politika Hakemliği (`facility_policy`) — negatif sonuç

**Hedef:** Kusur #2 (risk yükseltme). Ölçülmüştü ki model politika ihlalini *görüyor ve doğru
adlandırıyor* ama `severity=Düşük` veriyor (47 tespitin 34'ü). Prompt'a severity talimatı
yazmanın çalışmadığı da kanıtlanmıştı (p=0.267), bu yüzden **kod tarafında** bir çözüm denendi.

**Uygulanan mekanizma (`dilajan/policy.py` + `policy_gate` düğümü):** Operatör satır başına
bir kural beyan eder (`<ihlal> | <uygun görünüm> | <önem>`); video başına tek anlamsal
sınıflandırma çağrısıyla tespit edilen olaylar kurallarla eşlenir; eşleşirse severity
**operatörün beyan ettiği** seviyeye tek-yönlü yükselir. Dört kapı: kapsam, kanıt-alıntısı
doğrulama, çekince filtresi, bütçe. Ana anahtar `facility_policy` **boşsa tam no-op**.

**Ölçüm (n=100 anomali + 100 normal, eşleştirilmiş McNemar):**

| Metrik | Politika YOK | Politika VAR | p_exact | Kabul kapısı |
|---|---|---|---|---|
| Risk kalibrasyonu | 10/100 | 14/100 | **0.48** | ≥20/100 & p<0.05 → ❌ **GEÇİLEMEDİ** |
| Kategori | 33/100 | 36/100 | 0.69 | değişmemeliydi |
| Recall | 47/100 | 50/100 | 0.72 | değişmemeliydi |
| Normal risk=Düşük | 84/100 | 79/100 | 0.33 | ≥79 → sınırda |

Sonuç dosyası: `eval_20260726_192353.json`

### KÖK NEDEN — model açık-küme kural eşleştirmesi yapamıyor

Mekanizma **mekanik olarak doğru çalıştı** (91 klipte devreye girdi, kapılar işledi, izler temiz).
Sorun modelin **yargısında**: 7 yükseltmenin **7'si de R3'e** ("pano kapakları kapalı tutulur")
eşleşti. R1/R2/R4'e **sıfır** eşleşme.

```
"makinelerin etrafında yoğun duman oluştu"          → R3 (pano kapağı)  ❌
"Merdivenin altında motorlu araba benzeri nesne"    → R3                ❌
"Merkezde yerde hareketsiz bir nesne var"           → R3                ❌
"İşçi, yere bırakılmış metal parça üzerine basmış"  → R3                ❌
```

En çarpıcısı: *"Forklift aşırı yük taşıyor"* olayı, tam karşılığı olan **R4 (aşırı yük
kuralı) ile hiç eşleşmedi**. 7 yükseltmenin 3'ü **normal** klipte (yanlış yükseltme).

Bu, tasarım denetiminin **önceden uyardığı** yapısal riskin gerçekleşmesidir:
> *"Dört kapı UYDURMA DAYANAĞA karşı korur, YANLIŞ YARGIYA karşı korumaz. Model bir adaya
> İHLAL deyip kanıtı olay metninden sadık kopyalarsa hiçbir kapı ayırt edemez."*

**Ders:** 8B model, *açık-küme kural eşleştirme* ("bu 4 kuraldan hangisi ihlal edildi?")
görevini yapamıyor. Bu, prompt-severity denemesiyle (p=0.267) **aynı sınıf** başarısızlıktır:
model bu yargı görevinde güvenilir değil. Kapılar uydurma kanıtı eler, ama **yanlış ama
sadık-alıntılı** yargıyı elemez.

### İKİNCİ BULGU — ölçüm zaten güvenilmez (kusur #8 önkoşul)

Mekanizmanın **dokunmadığı** metrikler oynadı: recall'da 14 klip düştü, 17 klip yükseldi
(net +3). Bu sızıntı değil, **koşu-arası stokastik gürültü**. Yani mevcut kurulumda
**±15 kliplik salınım** var ve 5–10 puanlık bir etki **ölçülemez**.

> **Sonuç: Kusur #2'nin herhangi bir çözümü, kusur #8 (determinizm) giderilmeden
> doğrulanamaz.** #8 bir "iyileştirme" değil, #2'nin **ölçüm önkoşuludur**.

### DURUM ve gelecek yol
- Mekanizma **varsayılan KAPALI** (`facility_policy=""` → tam no-op, 0 model çağrısı).
  Hiçbir mevcut rakamı etkilemez; regresyon testleriyle kanıtlandı.
- Kod, testleri (66 kontrol) ve izlenebilirliğiyle **korunuyor** — çünkü hata mekanizmada
  değil, modelin eşleştirme yargısında.
- **Denenecek düzeltme (yapılmadı):** (a) kuralın KENDİ metninden türetilen sözcüksel çapa
  (R3'ün kelimeleri "duman"/"forklift" ile örtüşmediği için o eşleşmeler baştan reddedilir;
  koda sabit terim eklenmez), (b) açık-küme seçim yerine **kural başına ikili soru**
  ("bu olay R4'ü ihlal ediyor mu? evet/hayır").
- **Sıralama kararı:** önce #8 (determinizm) ve #9 (gece kapsamı), sonra #2'ye ölçülebilir
  zeminde dönülecek.

---

## 3. Bu ölçümlerden çıkan net konumlandırma

**Sistem güçlü:** görsel olarak belirgin olaylarda (yangın, düşme, kaza) —
gerçek videoda **%96 tespit / %96 kategori**, sıfır yanlış operasyonel tetik.

**Sistem sınırlı:** tesise-özgü politika ihlallerinde — kural olmadan %25,
kuralla %55. Bu alanda **otonom alarm olarak kullanılmamalıdır**;
operatör-destek ve kayıt-triyajı olarak kullanılmalıdır.

**✅ YAPILDI:** Mendeley setinin tamamı (691 klip / 9.4 GB) indirildi ve `eval_defense`
200 klibe çıkarıldı; A/B n=100 anomali ile yeniden koşuldu. Sonuç: kural enjeksiyonu
kazancı **p<0.0001** düzeyinde kanıtlandı (bkz. §2.5). Beklenti doğrulandı.

**Sonraki adımlar (kalan iş):**
1. **Risk yükseltme kod tarafında çözülmeli** — §2.5'te kanıtlandı ki prompt'a
   "en az Yüksek önem ver" yazmak çalışmıyor (p=0.267). Politika-ihlali kategorileri
   için `_calibrate_severity` / risk-tabanı katmanına deterministik bir yükseltme
   gerekiyor (tesis kuralı eşleşmesi → severity tabanı).
2. **Operasyonel-FP'yi düşürmek** — kural açıkken %35'e çıkıyor (p=0.0014). Dar-FP ve
   dispatch bozulmadığı için acil değil, ama operatör gürültüsü olarak iyileştirilmeli.
3. Gece/IR/termal kapsam hâlâ **sıfır**.
4. `data/industrial` içinde kaynak-kaynaklı **26 mükerrer grup** var (aynı video
   `class0` ve `class1` altında; 691 dosya = 658 benzersiz içerik). eval_defense
   seçimine sızmadı (200/200 benzersiz MD5) ama kaynak veri setinin bilinen bir
   etiket belirsizliği olarak belgelenmiştir.
