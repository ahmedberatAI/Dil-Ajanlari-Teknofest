# Yaya yolu — onuncu kol, onuncu ret (ve NEDEN'i ölçüldü)

Tarih: **2026-08-25** · Ön kayıt: `docs/on_kayit_yaya_zemin_2026-08-25.md`
Arşiv: `benchmark/results/eval_20260825_121933.json` (197 klip)
Puanlayıcı: `benchmark/yaya_kollari.py`

Bu belge `docs/yaya_yolu_kapanis_2026-08-25.md`'nin **yanına** yazılır,
üzerine değil.

## 1. Karar

**BİRİNCİL kol `zemin`: MCC +0,000 · saha kesinliği 0,000 → RET.**

Eşikler +0,45 ve 0,237 idi. `GRI_BETON` seçeneği **147 ölçümün hiçbirinde
çıkmadı**; kural hiç ateşlemedi (TP0 FP0 FN25 TN23).

| kol | etiket | TP | FP | FN | TN | MCC | saha kes. |
|---|---|---|---|---|---|---|---|
| **zemin** | **BİRİNCİL** | 0 | 0 | 25 | 23 | **+0,000** | 0,000 |
| zemin+kapı | ikincil | 0 | 0 | 25 | 23 | +0,000 | 0,000 |
| mesafe (9. kol) | ikincil | 23 | 14 | 2 | 9 | +0,370 | 0,195 (23/118) |
| mesafe+kapı | ikincil | 12 | 9 | 13 | 14 | +0,089 | 0,324 (12/37) |

Holm düzeltmesinden sonra hiçbir ikincil kol anlamlı değil (düzeltilmiş
p = 0,563).

## 2. Bulaşma kapısı GEÇTİ — ölçüm geçerli

İki ekstra slot sorulmasına rağmen sevk edilen üç sınıfın karışıklık matrisi
**birebir** korundu:

    Carrying_Overload_with_Forklift  TP24 FP2 FN1 TN23   +0,881   birebir
    Opened_Panel_Cover               TP23 FP0 FN1 TN25   +0,960   birebir
    Unauthorized_Intervention        TP19 FP2 FN6 TN23   +0,689   birebir

## 3. "Yanlış seçeneği mi bağladınız?" — ÖLÇÜLDÜ, hayır

Bu, jürinin soracağı ilk sorudur. **Post-hoc / betimleyici** olarak
işaretlenir; karar ölçütü değildir.

### 3.1 Cevap dağılımı sınıftan BAĞIMSIZ

| sınıf | YEŞİL_YOL | SARI_ÇİZGİ | GRİ_BETON | GÖRÜNMÜYOR |
|---|---|---|---|---|
| Safe_Walkway_**Violation** | 8,0% | 52,0% | **0%** | 40,0% |
| Safe_Walkway (normal) | 13,0% | 65,2% | **0%** | 21,7% |
| Opened_Panel_Cover | 4,2% | 50,0% | **0%** | 45,8% |
| Closed_Panel_Cover | 0,0% | 60,0% | **0%** | 40,0% |
| Unauthorized_Intervention | 24,0% | 68,0% | **0%** | 8,0% |
| Authorized_Intervention | 16,0% | 52,0% | **0%** | 32,0% |

İhlal sınıfı ile onun normal karşılığı arasında bile ayrım yok
(52,0% / 65,2% ve 40,0% / 21,7%).

### 3.2 Hiçbir seçenek (ve hiçbir ikili birleşim) eşiği geçmiyor

| ihlal değeri | TP | FP | FN | TN | MCC |
|---|---|---|---|---|---|
| GORUNMUYOR | 10 | 5 | 15 | 18 | **+0,197** (en iyi) |
| YESIL_BOYALI_YOL | 2 | 3 | 23 | 20 | −0,082 |
| SARI_CIZGI_UZERI | 13 | 15 | 12 | 8 | −0,134 |
| GRI_BETON | 0 | 0 | 25 | 23 | +0,000 |

En iyi ikili birleşim de +0,197. Hepsi +0,45'in çok altında. Üstelik en iyi
seçenek `GORUNMUYOR` — "göremiyorum" demeyi ihlal saymak kural olarak saçmadır.

**Sonuç: slot sınıf bilgisi taşımıyor.** Yanlış değer bağlanmadı; bağlanacak
doğru değer yok.

## 4. NEDEN çalışmadı — teşhis

Soru yereldi (*"ayağın altındaki zemin"*) ama **kırpma yerel değildi**.
`yol_roi_vlm = 0,00 0,50 1,00 1,00` karenin **alt yarısının tamamı**. Sarı
sınır çizgisi bu kırpmada neredeyse her klipte görünür durumda, dolayısıyla
model kişinin ayağına değil **kadrajın baskın çizgisine** demirliyor —
ve her sınıfta aynı cevabı veriyor.

Kırpmayı gerçekten yerelleştirmek **kişinin ayaklarının nerede olduğunu
bilmeyi** gerektirir. Bu da tespite bağlar; tespitin geniş planlarda
çalışmadığı aynı gün ölçüldü (`docs/on_kayit_yelek_roi_2026-08-25.md` §1:
iki klipte 0 kişi, üçüncüsünde 22,4x büyütme).

Pano slotunun neden çalıştığı da bu yüzden anlaşılıyor: panonun yeri
**sabittir**, dar bir ROI ile kırpılabilir. Yürüyen kişinin yeri sabit değil.

## 5. `on_azami` çapraz kapısı — mekanizma çalışıyor, yetmiyor

`mesafe` kuralına `makine_basinda_kisi == 0` üst sınırı eklendiğinde:

| | çift içi MCC | saha kesinliği | ateşleme |
|---|---|---|---|
| mesafe | +0,370 | 0,195 | 118 |
| mesafe + kapı | **+0,089** | **0,324** | 37 |

Kapı çapraz ateşlemeyi 118 → 37'ye indiriyor ve saha kesinliğini
0,195 → 0,324'e çıkarıyor (0,237 eşiğini **geçiyor**) — ama çift içi MCC
+0,370'ten +0,089'a çöküyor. **İki kapı hiçbir zaman birlikte geçmiyor.**

Bu, sentezin arşivden yaptığı projeksiyonu doğruluyor. Kapı bilgi taşıyor
ama çift içinde de kesiyor: yol ihlallerinin bir kısmında arka planda
makinede biri duruyor.

Mekanizma (`Kural.on_azami`) kodda kalıyor, varsayılanı sınırsız (K2).

## 6. Sınıfın durumu

**On kol, on ret.** Ama onuncu diğer dokuzdan farklı: ilk dokuzu aynı soru
tipinin parametre varyasyonuydu, onuncusu **soru tipini değiştirdi** ve yine
düştü. Artık elimizde bir tally değil bir **sebep** var:

> Bu ROI'de model, kişinin konumundan bağımsız olarak aynı cevabı veriyor.
> Ayırıcı bilgi kırpmanın içinde yok; kırpmayı daraltmak kişinin yerini
> bilmeyi gerektiriyor, o da bu çözünürlükte ölçülemiyor.

Yeniden açılma koşulu **değişmedi**: çift içi MCC ≥ +0,45 **ve** saha
kesinliği ≥ 0,237. Buna ek olarak artık şu da biliniyor: **soru biçimini
değiştirmek yetmez, kırpmanın kişiye kilitlenmesi gerekir.**

Kod, slot, kural, kapı, testler ve ölçüm kayıtları duruyor. Sevk edilen
yapılandırma değişmedi.
