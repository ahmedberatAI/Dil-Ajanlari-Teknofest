# Sorgu adlandırmaya yardım ediyor mu? — 3 kollu A/B (NEGATİF SONUÇ)

**Tarih:** 2026-08-10 · **Model:** Qwen3-VL-8B-Instruct-FP8 (vLLM, yerel) · **Set:** `data/eval_holdout` (32 klip, 24 anomali)
**Koşucu:** `scripts/run_naming_ab.py` · **Ham çıktı:** `benchmark/results/naming_ab_{A,B,C}_*.json`

---

## 1. Soru

D27'de sorgunun **zarar vermediği** kanıtlanmıştı (yangın 10/10, p=1.0000). Ama o ölçüm
`eval_scenario` üzerinde yapıldı ve orada `cat_match` zaten %92–96 idi — **tavan etkisi**,
iyileşme görülemezdi. Yani sorgunun **fayda** tarafı hiç sınanmamıştı.

Modelin gerçek zayıf noktası `eval_holdout`: **recall %96–100 ama cat_match %38.**
Model olayı *görüyor* ama *adlandıramıyor*.

**Sorulan soru:** Sorgu yönlendirmesi bu boşluğu kapatır mı?

---

## 2. Tasarım — ve ölçüm tuzağına karşı önlem

`cat_match` bir **anahtar kelime içerme** metriğidir ([labels.py](../benchmark/labels.py)):

```
Fighting -> kavga, dövüş, saldır, şiddet, itiş
Shooting -> silah, ateş, vur, çatış
```

Sorguya bu kelimeler yazılırsa model onları yankılar ve cat_match **mekanik** olarak yükselir.
Bu yetenek kazancı değil, cevap anahtarını modele vermektir. Bu yüzden kollar ikiye ayrıldı:

| Kol | Sorgu | Sızıntı (programatik doğrulandı) |
|---|---|---|
| **A** | *(yok)* | — |
| **B** | Alan bağlamı + "olayın ne olduğunu açıkça adlandır" — **hiçbir kategori adı yok** | **0 / 8 kategori** ✅ |
| **C** | Yukarıdaki + 8 kategorilik tam taksonomi | **8 / 8 kategori** ⚠️ kasten kirli |

`temperature=0`, tek değişken `DILAJAN_ANALYSIS_QUERY`, eşli McNemar exact.

**Okuma eşiği koşudan ÖNCE sabitlendi** (sonuç zayıf çıkarsa yuvarlanmasın diye):
%60+ = net kazanç · %38→%50 civarı = gürültü sınırı, yorumlanamaz.

---

## 3. Sonuçlar

| Kol | recall | **cat_match** | A'ya fark |
|---|---|---|---|
| **A** taban | 24/24 (%100) | **9/24 · %38** | — |
| **B** temiz | 24/24 (%100) | **10/24 · %42** | +4 puan |
| **C** taksonomi | 23/24 (%96) | **8/24 · %33** | **−4 puan** |

**Eşli test A vs C:** cat_match −%4, GA **[−%18, +%10]**, **p = 1.0000**

Üç kol da ölçülen **±%8 gürültü tabanının** içinde. Hiçbiri anlamlı değil.

### Kategori kırılımı (her kategoride 3 klip)

| Kategori | A | B | C |
|---|---|---|---|
| Shooting | 0/3 | 0/3 | 0/3 |
| Explosion | 2/3 | 2/3 | 2/3 |
| Fighting | 2/3 | 2/3 | 2/3 |
| Vandalism | 1/3 | 1/3 | 1/3 |
| Abuse | 0/3 | 1/3 | 0/3 |
| Assault | 2/3 | 2/3 | 1/3 |
| Burglary | 1/3 | 0/3 | 1/3 |
| RoadAccidents | 1/3 | 2/3 | 1/3 |

Üst dört kategori **hiç değişmedi**. Alt dördü her iki yöne salındı — çalkantı imzası.

---

## 4. ⚠️ DÜZELTME (2026-08-11) — bu bölümün ilk hâli YANLIŞTI

> **Aşağıdaki iddia geçersizdir. Silinmiyor, çünkü nasıl yanıldığımızın kaydı önemli.**

**İlk yazdığımız (YANLIŞ):**

```
Taksonomi kelimesi geçen anomali klip sayısı:
  A (kelimeler VERİLMEDİ) : 9 / 24
  C (kelimeler VERİLDİ)   : 9 / 24   <- BİREBİR AYNI
=> "Model, eline tutuşturulan cevap anahtarını kullanmadı."
=> "Darboğaz sözcüksel değil, görsel."
```

**Neden yanlış:** O kontrol, metinde *herhangi bir* taksonomi kelimesinin geçip geçmediğini
saydı — **varlık**. Oysa ölçülmesi gereken *doğru* kategorinin kelimesiydi — **doğruluk**.
İkisi karıştırıldı.

**Doğru ölçüm** (aynı arşiv dosyaları, model çalıştırılmadan yeniden skorlama):

| | herhangi bir taksonomi kelimesi | **doğru kategori kelimesi** |
|---|---|---|
| A (kelimeler verilmedi) | 9/24 | **12/24** |
| C (kelimeler verildi) | 9/24 | **14/24** |

Toplam kelime sayısı aynı kaldı ama **C'de geçen kelimeler daha sık DOĞRU olanlardı.**
Model taksonomiyi **kullandı**.

**İkinci ve daha ağır kusur:** `cat_match` yalnızca `events[].event` tarıyordu; `summary`
alanına hiç bakmıyordu — oysa `summary` şartname çıktı sözleşmesinin (K3) parçası ve
operatörün okuduğu alandır. C kolunun kazancı tam olarak orada duruyordu.

Ayrıntılı düzeltilmiş ölçüm: [`docs/olcum_onarimi_2026-08-11.md`](olcum_onarimi_2026-08-11.md)

### Ayakta kalan tek bulgu
`Shooting` üç kolda ve **denenen dört skorlama kuralının hepsinde 0/3**. Bu bir eşleştirici
artefaktı değil. Model silahlı olayları *"iki kişi arasında fiziksel temas"*, *"bir kişi ani
şekilde yere düşmüş"*, *"şiddetli bir müdahale"* diye adlandırıyor — yani görüyor ama
`Silahlı` yerine `Şiddet`/`Düşme` grubuna koyuyor. CCTV-Gun (arXiv 2303.10703) UCF 320×240'ta
tabancaların **~16 piksel** olduğunu ölçüyor. Bilgi karede fiziksel olarak yok.

---

## 5. Sonuç (2026-08-11 tarihinde düzeltildi)

**İlk yazdığımız sonuç — "sorgu adlandırmaya yardım etmiyor, darboğaz tamamen görsel" —
ölçüm kusurlu olduğu için KANITLANMAMIŞTIR.**

Düzeltilmiş tabloda C kolu (taksonomi) A'nın üstünde çıkıyor, ama fark hâlâ ölçülen **%8
gürültü tabanının** içinde. Yani doğru ifade: *"taksonominin yardım ettiği yönünde işaret var,
n=24'te kanıtlanamıyor."* Ne "yardım ediyor" ne de "etmiyor" denebilir.

**Jüri maddesi hakkında da geri adım:** *"cat_match kelime hazırlamayla şişirilemiyor"*
demiştik. Şişiriliyor — sadece ölçüm o kanalı (`summary`) görmediği için görünmüyordu.
Ayrıca eşleştirici o kadar gevşekti ki *"kırmızı sıvı dökülmüş"* ifadesi **"kır"** kökü
üzerinden `Vandalism` **doğru** sayılıyordu. Jürinin anahtar-kelime ablasyonu uyarısı
haklıydı.

### Bunun anlamı (yön)

Ölçüm onarımı tabanı %38'den **%46**'ya taşıdı (bkz. düzeltme raporu) — %81'e değil.
Kalan boşluk gerçek bir yetenek açığı, ama büyüklüğü ilk sandığımızdan **küçük**.

| Kanıtla elenmiş | Hâlâ açık |
|---|---|
| Süper-çözünürlük (doğruluğu düşürüyor, halüsinasyon üretiyor) | ASK-HINT deseni (ince-taneli ikili sorular) |
| Çözünürlük/kare artırmak (aynı token, +0.69 puan) | Kısıtlı kod çözme (`guided_choice`) |
| Semantik gruplama (bizde A +12.5, B 0, C 0) | Değerlendirme setini n≥100'e çıkarmak |
| `Shooting` kategorisi (bilgi karede yok) | |

Sorgu özelliği (D26) **kendi işini yapıyor** — operatör niyetini anlıyor, kritik olayı
bastırmıyor (D27'de yangın 10/10, p=1.0000). Bu düzeltme onu etkilemiyor.

---

## 6. Sınırlar

1. **n=24 anomali, gürültü tabanı %8.** GA [−%18, +%10]; bu ölçüm %18'lik bir düşüşü veya
   %10'luk bir artışı dışlayamaz. "Etki yok" değil, **"ölçülebilir etki yok"** doğrudur.
2. **İki sorgu metni denendi.** Farklı formülasyonlar farklı sonuç verebilir — ancak C kolunun
   yankı ölçümü (9/24 = 9/24) mekanizmanın kendisini dışladığı için bu risk düşüktür.
3. **Tek set.** Yalnızca `eval_holdout` (UCF-Crime 320×240). Daha yüksek çözünürlüklü bir
   sette sorgu farklı davranabilir — nitekim `eval_scenario`'da cat_match zaten %96.

---

## 7. Donanım notu — koşu sırasında sistem çöktü

İlk denemede (3 kol ardışık) sistem **21:12:52'de kendiliğinden yeniden başladı**
(Kernel-Power 41). BSOD yok, WHEA/termal/sürücü hata kaydı yok, prizde ve %100 şarjda.
A ve B sonuçları diskte sağlam kaldı; yalnızca C kaybedildi.

C tek başına yeniden koşuldu ve bu sefer GPU telemetrisi kaydedildi
(`benchmark/results/gpu_telemetri_C.csv`, 5 sn aralık, 160 örnek / ~13 dk):

| | Değer |
|---|---|
| Sıcaklık | min 52 · ort 74 · **maks 86 °C** |
| Güç | min 12 · ort 120 · **maks 175 W** |
| >80 °C örnek | 15 / 160 |

86 °C dizüstü GPU için kritik değil ama düşük de değil. Çöküşün 3. kolun başında, ~23 dakika
kesintisiz yükten sonra gelmesi **birikimli termal/güç yükünü** akla getiriyor.

**Öneri:** Uzun ölçüm koşularını **kol kol** yapın, aralarında soğuma bırakın. Tekrar
yaşanırsa `nvidia-smi -pl` ile GPU güç tavanını geçici olarak düşürmek (örn. 120 W) ani
sıçramaları törpüler.
