# Sorgu-güdümlü analiz (D26) — gerçek modelle A/B ölçümü

**Tarih:** 2026-08-09 · **Model:** Qwen3-VL-8B-Instruct-FP8 (vLLM, yerel) · **Donanım:** RTX 5090 Laptop 24 GB
**Koşu dosyaları:** `benchmark/results/query_ab_{A,B}_*.json`
**Koşucu:** `scripts/run_query_ab.py`

---

## 1. Neden bu ölçüm yapıldı

D26 ile eklenen sorgu-güdümlü analizde tasarım ilkesi şuydu: **sorgu odaklar, filtrelemez.**
Yani operatör "sadece forklift hareketlerine bak" dese bile yangın, duman, silah, düşmüş kişi
gibi kritik durumlar her zaman raporlanmalıdır.

Bu iddia commit anında yalnızca **prompt yapısı, kod yolu ve mock** düzeyinde kanıtlanmıştı.
Jürinin soracağı soru ise ampirikti:

> *"Operatör forklift sordu. Yangını kaçırdınız mı?"*

Bu belge o soruya sayıyla cevap verir.

---

## 2. Tasarım

| | |
|---|---|
| **Set** | `data/eval_scenario` — Fall 15 + Fire 10 + Normal 12 = **37 klip** |
| **A kolu** | Sorgu YOK (taban) |
| **B kolu** | `"Sadece forklift hareketlerine bak. Yalnızca forkliftlerin nereye gittiğini ve yük taşıyıp taşımadıklarını rapor et. Başka hiçbir şeyle ilgilenme."` |
| **Tek değişken** | `DILAJAN_ANALYSIS_QUERY` |
| **Örnekleme** | Her iki kol `temperature=0` (açgözlü) |
| **İstatistik** | McNemar exact + Newcombe 1998 Method 10 fark GA (`benchmark/paired_test.py`) |

**Set neden bu:** `eval_scenario` içinde **hiç forklift yok.** B kolundaki sorgu sete tamamen
ilgisiz ve üstüne "başka hiçbir şeyle ilgilenme" baskısı taşıyor. Sorgu bir filtre gibi
davransaydı yangın ve düşme tespiti çökerdi. Yani en kötü durum sınandı.

**Üçüncü koşu (A′):** A kolu, hiçbir şey değiştirilmeden **birebir tekrarlandı**. Bu, koşudan
koşuya gürültü tabanını ölçer ve "fark sorgudan mı, gürültüden mi?" sorusunu ayırt eder.
Bu adım olmadan A/B tek başına yorumlanamazdı.

---

## 3. Sonuçlar

### 3.1 Ana metrik — tespit

| Koşu | Anomali tespiti | Yangın | Wilson %95 GA |
|---|---|---|---|
| **A** (sorgusuz) | 24/25 · %96 | **10/10** | [%80–%99] |
| **A′** (sorgusuz tekrar) | 24/25 · %96 | **10/10** | [%80–%99] |
| **B** (dar sorgu) | 24/25 · %96 | **10/10** | [%80–%99] |

**A → B farkı: +%0**, GA **[−%16, +%16]**, **p_exact = 1.0000**

Yangın tespiti üç koşuda da **10/10**. Dar ve ilgisiz bir sorgu altında yangın kaçırılmadı.

### 3.2 Yan metrikler (anomali alt kümesi)

| Metrik | A | B | Fark | p |
|---|---|---|---|---|
| Kategori adlandırma | 23/25 (%92) | 24/25 (%96) | +%4 | 1.0000 |
| Risk kalibrasyonu | 22/25 (%88) | 24/25 (%96) | +%8 | 0.5000 |
| Doğru sevk | 22/25 (%88) | 24/25 (%96) | +%8 | 0.5000 |

Hepsi B lehine ama **hiçbiri anlamlı değil** — ve A′ karşılaştırmasında bu kazanç kayboluyor
(risk kalibrasyonu A′'de de 22/25). Yani bu iyileşmeler gürültüdür, sorgunun katkısı değildir.

### 3.3 Yanlış alarm (normal klipler, n=12)

| Metrik | A | B | Fark | p |
|---|---|---|---|---|
| Sevk tetiklenmedi | 12/12 (%100) | 11/12 (%92) | −%8 | 1.0000 |
| Katı FP yok | 12/12 (%100) | 11/12 (%92) | −%8 | 1.0000 |
| Risk ≤ Düşük | 11/12 (%92) | 10/12 (%83) | −%8 | 1.0000 |

Hiçbiri anlamlı değil; n=12 zaten çok küçük (GA'lar ±%35 genişliğinde).

### 3.4 Gecikme

| Koşu | Medyan | Toplam |
|---|---|---|
| A | 16.9 sn | 10.7 dk |
| B | 16.6 sn | 10.8 dk |

Sorgu ölçülebilir bir gecikme maliyeti getirmiyor.
*(Not: bu koşular CPU boşken yapıldı; sayılar karşılaştırılabilir.)*

---

## 4. Gürültü tabanı — bu ölçümün en önemli çıktısı

`temperature=0` olmasına **rağmen** aynı yapılandırmanın iki koşusu aynı sonucu vermedi:

| Klip | A | A′ | B |
|---|---|---|---|
| `Subject2_fall03.mp4` | tespit | **kaçırdı** | **kaçırdı** |
| `Subject3_fall01.mp4` | **kaçırdı** | tespit | tespit |

```
A vs A' uyuşmazlık (SAF GÜRÜLTÜ, aynı yapılandırma) : 2 / 25 klip
A vs B  uyuşmazlık (sorgu + gürültü)                : 2 / 25 klip
-> sorguya atfedilebilir EK uyuşmazlık              : 0 klip
```

Kararsız iki klip her iki karşılaştırmada da **aynı** ve A′ (sorgusuz) ikisinde de B ile
**aynı yönde** davrandı. Sorgu, hiçbir ek uyuşmazlık üretmiyor.

### Yanıltıcı görünen kanıt ve nasıl çürüdü

B kolunda `Subject2_fall03` için üretilen özet ilk bakışta sorgunun sızdığını gösteriyordu:

> **A:** "Bir kişi yataktan aşağıya kayarak yüzüstü yatarak düşmüştür…"
> **B:** "Video süresince herhangi bir olay tespit edilmedi. Görüntüde forklift hareketi veya
> yük taşıma faaliyeti gözlemlenmedi."

Model *"forklift yok → olay yok"* diye akıl yürütmüş gibi duruyor. Ancak **A′ koşusu — hiç
sorgu almadan — aynı klibi kaçırdı.** Yani bu cümle, modelin zaten yapacağı bir kaçırmayı
sonradan gerekçelendirmesidir; sorgunun sebep olduğu bir kayıp değildir.

Ders: **tek koşuluk A/B'de ikna edici görünen anlatısal kanıt yanıltıcı olabilir.**
Tekrar koşusu olmadan bu bulgu yanlışlıkla "gerçek kusur" diye raporlanacaktı.

### Diğer 4 klipte doğru davranış

B kolunda 4 anomali klibinin özetinde "forklift" geçiyor. Bunların 3'ünde model **doğru**
davranmış — tehlikeyi raporlamış *ve* sorguyu ayrıca yanıtlamış:

> "00:03'te kişi yere düşerek hareketsiz kaldı. Bu durum, çevredeki forklift hareketlerine
> doğrudan bağlantı kurulamadığı için, yalnızca kişiye ait bir sağlık olayıdır."

Yani "odakla, filtreleme" talimatı metinde de gözlemlenebiliyor.

---

## 5. Sonuç

**İddia doğrulandı:** Sorgu-güdümlü analiz, dar ve ilgisiz bir sorgu altında bile kritik olay
tespitini düşürmüyor. Yangın tespiti üç koşuda da 10/10; recall farkı +%0, p=1.0000.

Jürinin *"forklift sordunuz, yangını kaçırdınız mı?"* sorusunun cevabı: **hayır** — ve bu artık
prompt metnine değil, ölçüme dayanıyor.

---

## 6. Sınırlar (dürüstlük notu)

1. **n küçük.** Anomali alt kümesi 25 klip. Fark GA'sı **[−%16, +%16]** — yani bu ölçüm
   %16'dan küçük bir düşüşü *dışlayamaz*. "Etki yok" değil, **"ölçülebilir bir etki yok"**
   demek doğrudur.

2. **Gürültü tabanı %8.** 25 klipte 2 klip kararsız. Bu, `n=25` üzerinde yapılan **hiçbir**
   A/B'nin ~%8'den küçük bir etkiyi ayırt edemeyeceği anlamına gelir. Kusur #2 politika
   ölçümünün neden başarısız olduğunu (p=0.48) bu retroaktif olarak açıklıyor: ölçüm,
   gürültü tabanına karşı güçsüzdü.

3. **`temperature=0` determinizm sağlamıyor.** vLLM toplu-işlem (batching) kaynaklı
   belirsizlik kalıyor. Kusur #8 bu ölçümle **sayısallaştı**: aynı yapılandırma, 2/25 klip
   oynuyor. Tam determinizm için toplu-işlem boyutunun sabitlenmesi gerekir.

4. **Tek sorgu metni denendi.** Farklı dar sorgular farklı davranabilir. Kod düzeyinde
   10 dar sorgu için koruma metninin varlığı test edilmiştir
   (`tests/test_query_driven.py`), ancak ampirik olarak yalnızca bu biri koşuldu.

5. **Normal klip sayısı çok az** (n=12). Yanlış alarm tarafındaki −%8'lik farklar
   yorumlanamaz.

### Yapılırsa değeri olan

- Aynı A/B'yi `eval_holdout` (32 klip) üzerinde tekrarlamak → n≈57'ye çıkar, GA daralır
- 2-3 farklı dar sorgu metniyle koşmak → tek metne bağımlılığı kaldırır
- Kusur #8: toplu-işlem boyutunu sabitleyip gürültü tabanını sıfıra indirmek — bundan sonraki
  **her** A/B'nin gücünü artırır
