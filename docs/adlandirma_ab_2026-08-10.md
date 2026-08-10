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

## 4. Belirleyici kanıt: model verilen kelimeleri KULLANMADI

C kolunda modele 8 kategorinin tamamı açıkça verildi. Eğer darboğaz sözcüksel olsaydı,
model bu kelimeleri kullanır ve cat_match mekanik olarak fırlardı. Ölçüm:

```
Taksonomi kelimesi geçen anomali klip sayısı:
  A (kelimeler VERİLMEDİ) : 9 / 24
  C (kelimeler VERİLDİ)   : 9 / 24   <- BİREBİR AYNI
```

**Model, eline tutuşturulan cevap anahtarını kullanmadı.** Yani "kavga" demeyi bilmediği için
değil, **kavgayı göremediği için** adlandıramıyor.

Bu, mekanik yankı ihtimalini tamamen ortadan kaldırır ve sonucu tek yorumla bırakır:
**darboğaz sözcüksel değil, görsel.**

### Destekleyici gözlem
`Shooting` üç kolda da **0/3**. Model 320×240 grenli görüntüde silahı hiç seçemiyor; hiçbir
talimat bunu değiştirmiyor. Raporun kendi teşhisiyle tutarlı: *"belirleyici olan girdi kalitesi"*.

---

## 5. Sonuç

**Hipotez çürüdü — ve bu değerli bir bulgu.**

Sorgu yönlendirmesinin `cat_match` üzerinde ölçülebilir bir etkisi yok; ne temiz bağlam (B),
ne de doğrudan taksonomi enjeksiyonu (C) yardım ediyor. %38'lik adlandırma boşluğu bir
**prompt mühendisliği** problemi değil, bir **girdi çözünürlüğü** problemidir.

**Yan kazanç — jüriye cevap:** Jürinin 1 numaralı bulgusu *"anahtar kelime ablasyonu koşun,
cat_match kolay oynanabilir olabilir"* idi. Bu koşu tam tersini gösterdi: modele anahtar
kelimelerin **tamamı** verildiğinde bile cat_match yükselmedi. Metrik kelime hazırlamayla
şişirilemiyor.

### Bunun anlamı (yön değişikliği)

| Yanlış kaldıraç | Doğru kaldıraç |
|---|---|
| Daha iyi prompt / sorgu | Daha yüksek çözünürlüklü giriş, daha çok kare |
| Taksonomi tanımı | Bu domaine özgü ince ayar (fine-tune) |
| | Grenli girdide özel ön işleme (üst-ölçekleme) |

Sorgu özelliği (D26) **kendi işini yapıyor** — operatör niyetini anlıyor, kritik olayı
bastırmıyor. Sadece **bu** boşluğu kapatmıyor; kapatması da beklenmemeliydi.

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
