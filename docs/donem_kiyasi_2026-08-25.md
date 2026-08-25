# Yerel dönem ile şimdiki karşılaştırma

Tarih: 2026-08-25 · Aynı değerlendirme kümesi (`data/eval_defense`, 197 klip)
· **Tüm arşivler bugünkü puanlayıcıyla yeniden puanlandı** (puanlayıcı-sürümü
karıştırıcısı kaldırıldı; arşivlerin kendisine dokunulmadı).

## Ham tablo

| tarih | dönem | gözlem düzlemi | recall | normal FP | `isg_match` | medyan gecikme |
|---|---|---|---|---|---|---|
| 26 Tem | yerel Qwen3-VL-8B | — | 0,200 | 0,040 | 0,010 | 11,7 s |
| 26 Tem | yerel Qwen3-VL-8B | — | 0,470 | 0,080 | 0,160 | 14,2 s |
| 26 Tem | yerel Qwen3-VL-8B | — | 0,500 | 0,110 | **0,170** | 12,4 s |
| 18 Ağu | yerel Qwen3-VL-8B | — | 0,384 | 0,071 | 0,152 | 13,2 s |
| 24 Ağu | **uzak** llm-fast | — | 0,131 | 0,051 | **0,020** | 5,7 s |
| 24 Ağu | uzak llm-large | VAR | 0,879 | 0,582 | 0,545 | 42,7 s |
| 25 Ağu | uzak llm-large | VAR | 0,869 | 0,561 | 0,535 | 24,5 s |
| 25 Ağu | uzak llm-large | VAR | 0,848 | 0,602 | **0,646** | 30,3 s |

## Okunuşu

### 1. Donanım yükseltmesi tek başına İSG tespitini İYİLEŞTİRMEDİ

Yerel dönemin en iyisi `isg_match` **0,170**. Uzak servise geçtikten sonra,
mimari değişmeden: **0,020**. Yani daha güçlü altyapıya geçmek skoru
düşürdü.

> **Çekince:** o koşum ana yolda `llm-fast` kullanıyordu (3B *aktif* MoE),
> yerel model ise 8B *yoğun*. Yani bu tek başına "uzak daha kötü" demek
> değil — "daha küçük aktif modele geçtik" de demek. Temiz bir
> "uzak llm-large, gözlem düzlemi kapalı" koşumumuz yok.
>
> Ancak sonuç aynı yöne işaret ediyor: **model büyüklüğü darboğaz değildi.**
> Bunu ayrıca ölçtük — aynı model işlemsel soru sorulduğunda 20/20 doğru
> karar veriyordu, serbest metin boru hattı ise 0/20 kaçırıyordu.

### 2. Kazancı mimari getirdi

Uzak dönemin içinde, aynı servis ve aynı model ile gözlem düzlemi eklenince:
**0,020 → 0,646 (32×)**. Yerel dönemin en iyisiyle kıyaslandığında **3,8×**.

### 3. Yanlış alarm — iki farklı ölçüm

Ham `normal FP` 0,071 → 0,602 diye görünüyor. Ama bu iki sayı **aynı şeyi
ölçmüyor**:

- Yerel dönemde tesise özgü kural **yoktu**; 0,071 anlatı düzleminin yanlış
  alarmıydı.
- Bugünkü 0,602'nin büyük kısmı, kuralın **ekseninde etiket olmayan**
  kliplerdeki ateşlemelerden geliyor.

Her kuralın **kendi çiftindeki** normal kliplerde verdiği yanlış pozitif:

| kural | normal klip | yanlış pozitif | oran |
|---|---|---|---|
| Opened_Panel_Cover | 25 | 0 | 0,000 |
| Carrying_Overload_with_Forklift | 25 | 2 | 0,080 |
| Unauthorized_Intervention | 25 | 2 | 0,080 |
| **toplam** | **75** | **4** | **0,053** |

Yani **ölçülebilir eksende yanlış alarm oranı 0,053** — yerel dönemin
0,071–0,110'undan *daha düşük*, üstelik İSG tespiti 4 kat yüksek.

### 4. Gecikme

Yerel: 11,7–14,2 s. Şimdi: 24,5–30,3 s. Yaklaşık **2× yavaş**.

Sebep: gözlem düzlemi klip başına ek video kodlamaları ve slot çağrıları
ekliyor; ayrıca sunum için `kodlama_kararli=1` (tek iş parçacığı) açık.
Uzak servis ham hızda daha hızlı — gözlem düzlemi kapalıyken 5,7 s.

## Özet

| ölçüt | yerel dönem (en iyi) | şimdi | değişim |
|---|---|---|---|
| İSG'ye özgü tespit | 0,170 | **0,646** | **3,8×** |
| Anomali recall | 0,500 | 0,848 | +0,348 |
| Ölçülebilir eksende yanlış alarm | 0,071–0,110 | **0,053** | daha iyi |
| Medyan gecikme | 12,4 s | 30,3 s | 2,4× yavaş |

**Tek cümleyle:** güçlü donanım tek başına hiçbir şey kazandırmadı; kazancın
tamamı, soruyu serbest metinden kapalı cevap uzayına taşıyan mimariden geldi.
Bedeli iki kat gecikme.

---

## EK — "Hâlâ geride olduğumuz yer var mı?" (net döküm)

Aynı küme, tüm ölçütler yan yana:

| ölçüt | yerel (18 Ağu) | şimdi | durum |
|---|---|---|---|
| anomali recall | 0,384 | 0,848 | **ileride** |
| risk kalibrasyonu (≥Yüksek) | 0,172 | 0,828 | **ileride** |
| kategori eşleşmesi | 0,364 | 0,828 | **ileride** |
| olay / anomali klip | 0,42 | 1,30 | **ileride** |
| İSG'ye özgü tespit | 0,152 | 0,646 | **ileride** |
| **normal klipte yanlış alarm** | **0,071** | **0,602** | **geride** |
| **normal klipte risk=Düşük** | **0,857** | **0,398** | **geride** |
| **olay / normal klip** | **0,33** | **0,80** | **geride** |
| **medyan gecikme** | **13,2 s** | **30,3 s** | **geride** |

Geride görünen dört satırın **üçü aynı olgunun** farklı yüzü: normal
kliplerde daha çok alarm üretiyoruz.

### O alarmların kaynağı ayrıştırıldı

| kaynak | normal klip oranı |
|---|---|
| yalnız **anlatı düzlemi** | **0,010** |
| yalnız kural motoru | 0,541 |
| ikisi birden | 0,020 |
| toplam | 0,571 |

Yerel dönemde tesise özgü kural **yoktu**; oradaki 0,071 saf anlatı
düzlemiydi. Bugün anlatı düzleminin yanlış alarmı **0,010** — yani
**7 kat daha iyi**.

Artışın tamamı kural motorundan geliyor ve o ateşlemelerin örneklenen
12/12'sinde gerçek bir tehlike vardı (makine başında yeleksiz kişi /
açık pano). Kuralların **ölçülebildiği** eksende yanlış alarm 0,053 —
yine yerel dönemden daha iyi.

### Sonuç

**Gerçekten geride olan tek şey hız:** 13,2 s → 30,3 s (2,4×).

Normal klip alarmı ham sayıda geride görünüyor ama her eşdeğer
karşılaştırmada ileride:
- anlatı düzlemi: 0,071 → 0,010
- kuralın ölçülebildiği eksen: 0,053

Ham 0,602 rakamı, kliplerin tek etiketli olmasından doğuyor.
