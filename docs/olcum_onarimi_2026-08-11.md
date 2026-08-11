# Ölçüm zinciri onarımı — `cat_match` kusuru ve semantik gruplama denemesi

**Tarih:** 2026-08-11 · **GPU kullanılmadı** — tüm sonuçlar arşivlenmiş koşuların yeniden
skorlanmasıyla elde edildi, model hiç çalıştırılmadı (ölçüm gürültüsü **sıfır**).
**Araç:** `benchmark/rescore.py` · **Testler:** `tests/test_rescore.py` (91 kontrol)

---

## 1. Bulunan kusur

`benchmark/eval_clips.py` içinde kategori eşleşmesi şöyle hesaplanıyordu:

```python
cat_match = any(any(k in e.event.lower() for k in keywords) for e in res.events)
```

**Yalnızca `events[].event` taranıyor. `summary` alanına hiç bakılmıyor** — oysa `summary`
şartname çıktı sözleşmesinin (K3) parçasıdır ve operatörün ekranda okuduğu alandır.

Buna ek olarak eşleştiricinin kendisi çok gevşekti:

| Sorun | Somut örnek | Sonuç |
|---|---|---|
| Çıplak alt-dizge | "**kır**mızı sıvı dökülmüş" | `Vandalism` **doğru** sayıldı |
| | "**vur**gulanmadı" | `Assault` tetiklendi |
| | "kapıdan **giriş** yapan personel" | `Burglary` tetiklendi |
| Olumsuzlama sayılıyor | "kaza belirtisi **yok**" | `RoadAccidents` tetiklendi |
| Türkçe `.lower()` hatası | `"İstismar".lower()` → `i̇stismar` (i + U+0307) | `istismar` anahtarıyla **eşleşmiyor** |

---

## 2. Yeniden skorlama — 4 kural, 3 arşiv koşusu

Her kural, D28'in **aynı** çıktı dosyalarına uygulandı. `n=24` anomali klip.

| Kural | A (taban) | B (temiz sorgu) | C (taksonomi) |
|---|---|---|---|
| **1** — ESKİ: yalnız `event`, çıplak alt-dizge | 9/24 · %38 | 10/24 · %42 | 8/24 · %33 |
| **2** — `+summary`, aynı gevşek eşleştirici | 12/24 · %50 | 12/24 · %50 | 14/24 · %58 |
| **3** — `+summary` + **sıkılaştırılmış** eşleştirici | 11/24 · %46 | 11/24 · %46 | 12/24 · %50 |
| **4** — kural 3 + **semantik grup** | 14/24 · %58 | 11/24 · %46 | 12/24 · %50 |

**Hat doğrulaması:** Kural 1, dosyalarda kayıtlı `category_match` değerini üç koşuda da
**24/24 birebir** yeniden üretti. Yani yeniden skorlama hattı sağlam, tablo güvenilir.

### Kural 2 → 3'teki düşüş bir gerileme değil, itiraf

Skor 12→11, 12→11, 14→12 düşüyor. Bunun sebebi, `+summary` kazancının bir kısmının **gerçek
adlandırma değil, şans eseri alt-dizge tutturması** olmasıydı:

> `Vandalism027` — model *"kırmızı sıvı dökülmüş"* demiş. Eski kural bunu **"kır"** kökü
> üzerinden `Vandalism` **doğru** saymış. Model vandalizmi **adlandırmamış.**

Sıkılaştırılmış kural bunu eliyor. Özgüllük (klip başına tetiklenen **yanlış** kategori sayısı):

| | A | B | C |
|---|---|---|---|
| Kural 1 (eski) | 2.67 | 1.92 | 2.25 |
| Kural 2 (+summary, gevşek) | 3.12 | 2.58 | 3.33 |
| **Kural 3 (sıkılaştırılmış)** | **2.04** | **1.62** | **2.12** |

---

## 3. Semantik gruplama — literatür bizde replike olmadı

Literatür (arXiv 2511.07171, Ovis-8B / UCF-Crime): 14 sınıfı anlamsal gruplara indirmek
**eğitim olmadan +15.7 puan** getiriyor.

**Bizde ölçülen:**

| Kol | Kural 3 → Kural 4 | Kazanç |
|---|---|---|
| A | 11 → 14 | **+12.5 puan** |
| B | 11 → 11 | **0.0** |
| C | 12 → 12 | **0.0** |

Ortalama **+4.2 puan** — literatürün vaat ettiğinin dörtte biri. Üstelik tek pozitif sonuç
3 klipten ibaret; ölçülen **%8 gürültü tabanının** sınırında, tek başına kanıt sayılmaz.

### Neden — tahmin edilmedi, ölçüldü

İlk hipotez *"grup içi kelime dağarcıkları zaten örtüşüyor, grup katmanı no-op"* idi ve
**yanlış çıktı**. Ölçülen grup içi kalıp örtüşmesi küçük: Şiddet 2/17, MalSuçları 0/25,
Yıkım 1/15.

Gerçek sebep, grup kuralının fiilen değiştirdiği kliplerin tek tek listelenmesiyle bulundu:

```
KOL A: 3 klip değişti
   Abuse005      -> grup içi eşleşen: Fighting, Assault  ("fiziksel kavga" denmiş)
   Abuse018      -> grup içi eşleşen: Fighting, Assault  ("fiziksel kavga" denmiş)
   Vandalism014  -> grup içi eşleşen: Burglary
KOL B: 0 klip.   KOL C: 0 klip.
```

**Gruplama yalnızca hata GRUP İÇİNDE kaldığında işe yarıyor** (Abuse'a "kavga" demek gibi).
B ve C kollarında kalan hatalar **gruplar arası** — model olayı bambaşka bir gruba koyuyor,
grup katmanı onu kurtaramıyor.

### `Shooting` 0/3'ün yapısal açıklaması

Üç kolda ve dört kuralın hepsinde **0/3**. Model silahlı olayları şöyle adlandırıyor:

> *"iki kişi arasında fiziksel temas ve itme"* · *"bir kişi ani şekilde yere düşmüş"* ·
> *"şiddetli bir müdahale"*

Yani olayı **görüyor** (recall %100) ama `Silahlı` yerine `Şiddet`/`Düşme` grubuna koyuyor.
`Silahlı` **tek üyeli** bir grup olduğu için semantik gruplama bu 3 klibe (kliplerin %12.5'i)
**yapısal olarak yardım edemez.**

---

## 4. Ölçüm dürüstlüğü — eski skor silinmedi

Metriği değiştirmek taban çizgisini yükseltir; bu, "metriği kendimize göre ayarladık"
görünümü yaratabilir. Karşı önlem olarak `eval_clips.py` artık her satırda **üç** alan yazıyor:

| Alan | Kural |
|---|---|
| `category_match` | YENİ — `event` + `summary`, sıkılaştırılmış eşleştirici |
| `category_match_eski` | ESKİ — yalnız `event`, çıplak alt-dizge |
| `category_match_grup` | Semantik grup düzeyi |

Özet çıktısı üçünü **yan yana** basar. Eski skor hiçbir yerde silinmez, gizlenmez veya
üzerine yazılmaz. `rescore.py` de arşiv dosyalarında bu alanlar yokken çökmez (fail-open).

---

## 5. Sonuç

**Ölçüm onarımı tabanı %38 → %46'ya taşıdı.** Bu bir müdahale değil, bir **düzeltme** —
model hiç değişmedi, yalnızca çıktısının yarısını görmeyen bir metrik onarıldı.

Bunun iki sonucu var:

1. **D28'in ana sonucu geçersiz.** *"Model cevap anahtarını kullanmadı, darboğaz tamamen
   görsel"* zinciri, çıktının yarısını görmeyen bir metrikle kurulmuştu.
   Bkz. [`adlandirma_ab_2026-08-10.md` §4 düzeltmesi](adlandirma_ab_2026-08-10.md).
2. **Kalan boşluk gerçek ama ilk sanılandan küçük.** %46 → %81 arası kapanacaksa bu
   ölçümle değil, model/istem tarafındaki bir müdahaleyle olacak.

**Semantik gruplama (araştırma önerisi #2) denendi ve bizde replike olmadı.** Literatürdeki
+15.7 puanlık kazanç, hataların grup içinde kalmasına dayanıyor; bizim hatalarımız gruplar
arası.

---

## 6. Sınırlar

1. **n=24, gürültü tabanı %8.** Kural 3 ile A/C farkı (11 vs 12) tek klip — yorumlanamaz.
2. **Sıkılaştırılmış eşleştirici de mükemmel değil.** Klip başına hâlâ ~2 yanlış kategori
   tetikleniyor. Tam çözüm anahtar-kelime eşlemesini bırakıp hakem modeliyle (K11) veya
   insan adjudikasyonuyla skorlamaktır.
3. **İnsan altın cetveli yok.** %46'nın gerçekten doğru olduğunu bilmiyoruz — yalnızca eski
   %38'den daha az yanlış olduğunu biliyoruz. 24 klip 3 kişi × 1 saatte adjudike edilebilir;
   bu yapılmadı.
4. **Tek set.** Yalnızca `eval_holdout` (UCF-Crime 320×240). `eval_scenario` bu onarımdan
   sonra yeniden ölçülmedi — oradaki %92-96 rakamları hâlâ ESKİ kuralla.
