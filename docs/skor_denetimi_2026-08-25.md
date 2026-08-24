# Skor denetimi — hangi sayılar sorunlu

Tarih: 2026-08-25 · Dal: `d34-isg-veri-kkd`

Soru: *"sorunlu skorlar hangileri?"* Bu belge kendi sayılarımızın dürüst
denetimidir. Hiçbir arşiv silinmedi (§7).

---

## 1. GEÇERSİZ — kullanılmamalı

| skor | kusur |
|---|---|
| iSafetyBench MCQ (tehlike %55,3 · rutin %48,7) | vLLM `guided_choice` alanını **sessizce yok sayıyordu**; model serbest metin dönüyordu, ayrıştırıcı ilk karakteri alıyordu ("Bu videoda…" → B). |
| **D33 ve D37 sonuçları** | Aynı kusur. Kısıtlı çözme hiç çalışmamıştı. |
| İlk 149 kliplik D43 koşumu (tüm hücreler 0) | `_ingest_output()` çağıranın yerel değişkenine erişiyordu → NameError; fail-open yuttu, boru hattı 0 segmentle "ihlal yok" üretti. |
| Yaya yolu geofence +0,506 | Çerçeveleme tek başına %72,9 = R1 doğruluğu. Skor bilgiden değil kamera açısından geliyordu (Fisher p=0,0024). |
| Ajanın forklift +0,718'i | Üreten kod kayboldu, tekrar üretilemedi. Kendi uygulamam +0,280 → (perspektif düzeltmesiyle) +0,641. |
| "Çözünürlük yelek slotunda belirleyici" | Aynı anda iki şey değişmişti (sistem promptu); 2×2 faktöriyel gerçek etkenin **prompt** olduğunu gösterdi. |
| Kırpma probunun "kırpma açıkça daha iyi" hükmü | B kolu dejenereydi (23/24 aynı cevap); başlık doğruluğu karışıklık matrisini gizliyordu. |
| D44 `kapsam_yayilimi` olumsuzlama kapısı | Fiil vekili 21 addan 19'unu fiil sanıyordu; İSG setinde gerçek eşleşmelerin %83'ünü siliyordu. Geri alındı. |
| Yaya yolu ROI "KABUL"ü | Kendi kabul betiğimde `abs(MCC)` kullanmışım; **ters işaretli** bir ilişkiyi kabul diye raporladı. |

---

## 2. GEÇERLİ ama tek başına sunulursa YANILTICI

| skor | neden |
|---|---|
| Çift bazlı MCC'ler | Her kural **yalnız kendi çiftinde** ölçülüyor. Saha kesinlikleri: pano 0,404 · forklift 0,862 · yetkisiz 0,229. |
| Anomali recall %87,9 | Tesise özgü kurallar başka sınıfların anomali kliplerinde de ateşleyip recall'ı şişiriyor. |
| `category_match` %84,9 | Kova düzeyi ("Anomali") metriği; İSG'ye özgü değil. Aynı arşivde `isg_match` 2/197'ydi. |
| Normal FP %58,2 | **Ters yönde** yanıltıcı: ateşlemelerin çoğu, o kuralın ekseninde etiketi olmayan kliplerde. Ölçülebilir eksende kesinlikler 1,000 / 0,905 / 0,862. |
| Yaya yolu +0,638 (ayrılmış küme) | Gerçek ölçüm, ama saha kesinliği 0,151 ve forklift kliplerinin 49/50'sinde ateşliyor. Sevk edilmiyor. |

---

## 3. EN CİDDİ ŞÜPHE — kodlama sızıntısı (araştırıldı, ÇÖZÜLDÜ)

### 3.1 Sızıntı gerçekti ve bizim gönderdiğimiz baytlarda da açıktı

İçerikle ilgisiz dosya özellikleri, tek başına en iyi eşikle:

| çift | orijinal dosyalarda | `servis_videosu` çıktısında |
|---|---|---|
| forklift | bit hızı **+1,000** · boyut **+1,000** | bit hızı **+0,882** · boyut +0,378 |
| yetkisiz | fps +0,882 | fps **+1,000** |
| pano | en yüksek +0,433 | — |
| yol | en yüksek +0,472 | — |

Yani forklift (+0,851) ve yetkisiz (+0,689) skorlarımız, **içerikle hiç ilgisi
olmayan bir eşiğin ulaştığı seviyenin altındaydı**. CRF ile yeniden kodlama
boyut kanalını kırıyor ama bit hızını kırmıyor (CRF kalite hedeflidir, bit hızı
sahne karmaşıklığını izler); fps'e ise hiç dokunulmuyordu.

### 3.2 Kontrol

`kodlama_normalize` → gözlem düzlemi videoları **ortak spekte**: fps=8 sabit,
bit hızı 800k sabit. Kanalların kapandığı ayrıca doğrulandı:

| çift | fps | bit hızı |
|---|---|---|
| forklift | +1,000 → **+0,000** | +0,882 → +0,577 |
| yetkisiz | +1,000 → **+0,000** | +0,480 |
| pano | → **+0,000** | +0,322 |

Yorum kuralı **koşumdan önce** yazıldı (`ONKAYIT_kodlama.md`): forklift ≥+0,70,
yetkisiz ≥+0,60, pano ≥+0,85 ise skor içeriktendir; çökerse geri çekilir.

### 3.3 Sonuç — üç skor da hayatta kaldı

| çift | sızıntılı baytlarla | **normalize edilmiş** | fark |
|---|---|---|---|
| Carrying_Overload_with_Forklift | +0,851 (TP25 FP4 FN0) | **+0,840** (TP23 FP2 FN2) | −0,011 |
| Unauthorized_Intervention | +0,689 | **+0,689** | 0,000 |
| Opened_Panel_Cover | +0,960 | **+0,960** | 0,000 |

fps kanalı tamamen kapatıldığı halde skorlar değişmedi. **Üç skor da kodlama
izinden değil içerikten geliyor.** Forklift'te doğru pozitif 25→23 düşerken
yanlış pozitif 4→2 düştü — MCC neredeyse aynı.

Ek kazanç: klip başına medyan süre **56,3 s → 26,8 s**.

Normalizasyon sevk yapılandırmasına alındı. Sınıf varsayılanı KAPALI kaldı (K2).

---

## 4. Şüpheden temiz olan tek skor, en baştan beri

`Opened_Panel_Cover` **+0,960**: en yüksek kodlama sinyali +0,433 idi, yani
skor sızıntı tavanının **iki katından fazla**. Ayrıca ayrılmış kümede +1,000
(25/25) doğrulandı ve ölçülebilir eksende kesinliği 1,000.

## 5. Hâlâ açık şüpheler

- **Çoklu etiket yokluğu.** Kamera 9'un dört sınıfı aynı sahne; bir klipte hem
  açık pano hem yeleksiz kişi olabilir. Bu çözülmeden ne saha kesinliği ne de
  normal FP kesin olarak yorumlanabilir.
- **Kalan bit hızı sızıntısı +0,577** (forklift). 0,60 eşiğinin altında ama
  sıfır değil. Tam kapatmak için iki sınıfın klip sürelerini de eşitlemek gerekir.
- **Küçük n.** Ayrılmış küme doğrulamaları n=20-25; güven aralıkları geniş.
