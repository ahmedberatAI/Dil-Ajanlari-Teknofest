# Benchmark'larımızda ne sorunlu, ne değil

Tarih: 2026-08-25 · Bu belge kendi ölçüm altyapımızın dürüst eleştirisidir.

## A. SAĞLAM olanlar

**Üç sınıf çiftinin MCC'si.** Üç ayrı karıştırıcıya karşı test edildi ve
hepsinden geçti:

| karıştırıcı | test | sonuç |
|---|---|---|
| kodlama sızıntısı (bit hızı/fps) | ortak spekte yeniden kodlama | skorlar değişmedi |
| kamera açısı | katmanlı analiz | görüş içi +0,563/+0,574 |
| aşırı uyum | kaynak setin `_tr`/`_te` ayrımı | fark yok (aşağıda) |

**Tekrar üretilebilirlik.** İki bağımsız koşum yalnız MCC'de değil karışıklık
matrislerinde de birebir aynı çıktı (`kodlama_kararli=1`).

**Genelleme ölçümü.** Bağımsız kaynak (iSafetyBench), tohumlu örneklem,
kısıtlı çözme ile zorunlu seçim.

## B. SORUNLU olanlar

### B1. Küçük örneklem — en ciddi kısıt
Sınıf çiftleri 48–50 klip, ama asıl sorun **ihlal klibi sayısı**: her sınıfta
24–25. Kaynak setin kendi test ayrımında ise sınıf başına yalnız **3–4 ihlal**
klibi var. Bu, temiz bir ayrılmış küme değerlendirmesini bu veriyle
**imkânsız** kılıyor.

Sonuç: Wilson aralıkları geniş (ör. yetkisiz doğruluk 0,840 [0,715–0,917]) ve
tek bir klibin kaçması MCC'yi belirgin oynatıyor.

### B2. Çift bazlı metrik saha davranışını gizler
Her kural yalnız kendi çiftinde ölçülüyor. Operatör tüm klipleri görür.
Ham saha kesinlikleri: pano 0,390 · yelek 0,237 · forklift 0,923.
(Düzeltilmiş hâlleri için B4.)

### B3. Yanıltıcı üst düzey metrikler
- **Anomali recall %84,9** — kurallar başka sınıfların anomali kliplerinde de
  ateşleyip oranı şişiriyor.
- **`category_match` %82,8** — kova düzeyi ("Anomali"), İSG'ye özgü değil.
- **`isg_match` 0,646 / 0,865** — dört sınıf mı üç sınıf mı; tek başına
  hangisi verilirse verilsin eksik anlatır. İkisi yan yana verilmeli.
- **Normal FP %60,2** — ters yönde yanıltıcı (B4).

### B4. Çoklu etiket düzeltmesi ÖLÇÜM DEĞİL, ÖRNEKLEM
"Çapraz ateşlemelerin çoğu gerçek tehlike" bulgusu **24 klibe gözle
bakılarak** elde edildi (12 yelek + 12 pano, tohumlu). 12/12 doğru çıktı ve
Wilson alt sınırı 0,739.

Ama bu **tek kareye bakılmış insan hükmüdür**, sertifikalı etiket değil.
Düzeltilmiş kesinlikler (yelek 0,975 · pano 1,000) bu yüzden **alt sınırla
birlikte** verilmelidir (0,796 / 0,852). Kesin cevap 197 klibin tamamının üç
eksende etiketlenmesini gerektirir.

### B5. Kalan bit hızı sızıntısı
Forklift çiftinde normalizasyon sonrası bit hızı hâlâ +0,577 (0,60 eşiğinin
altında ama sıfır değil). Tam kapatmak için sınıfların klip **sürelerinin** de
eşitlenmesi gerekir.

### B6. iSafetyBench karşılaştırması
İki modelin tehlike kolları örtüşen güven aralıklarına sahip
(%54,7 [47–62] vs %44,0 [36–52]). **"llm-large daha iyi" denemez** —
eşleştirilmiş bir test yapılmadı.

### B7. Veri setinin kendi kusurları
Bunlar bizim değil verinin sorunu ama sonuçları etkiliyor: kodlama sızıntısı,
kamera karıştırıcısı (yetkisiz çiftinde |MCC| 0,833), tek etiketlilik,
mükerrer/çelişkili klipler (karantinaya alındı).

## C. AŞIRI UYUM KONTROLÜ — yeni yapıldı

Klip adlarındaki `_tr`/`_te` kaynak veri setinin kendi eğitim/test ayrımıdır
(151/49). Bizim 197'lik kümemiz ikisini karıştırıyor ve geliştirme
kararlarının bir kısmı bu karışık küme üzerinde alındı.

| çift | tümü | `_tr` | `_te` | `_te` ihlal sayısı |
|---|---|---|---|---|
| Opened_Panel_Cover | +0,960 | +1,000 (n=34) | +0,784 (n=15) | **3** |
| Carrying_Overload_with_Forklift | +0,881 | +0,846 (n=39) | +1,000 (n=11) | **4** |
| Unauthorized_Intervention | +0,689 | +0,677 (n=35) | +0,659 (n=15) | **4** |

**Aşırı uyum belirtisi yok:** yetkisiz neredeyse aynı (+0,677 → +0,659),
forklift test kümesinde daha iyi. Pano'daki düşüş 3 ihlal klibinin 1'ini
kaçırmaktan geliyor — o örneklemde MCC zaten çok oynak.

**Ama bu kontrol kesin değil:** test ayrımında sınıf başına 3–4 ihlal klibi
var. Bu, aşırı uyumu *dışlamak* için yeterli değil; yalnızca *belirti
görülmediğini* söyler.

## D. Özetle

Ölçüm altyapısı üç ciddi karıştırıcıya karşı test edildi ve geçti; sonuçlar
bayt düzeyinde tekrar üretilebilir. **Asıl kısıt istatistikseldir**: sınıf
başına 24–25 ihlal klibi, test ayrımında 3–4. Raporlanan her sayı güven
aralığıyla birlikte okunmalı ve tek bir metrik tek başına sunulmamalıdır.
