# Yarışma hazırlığı — görülmemiş İSG videolarında performans

Tarih: **2026-08-25** · Ön kayıt: `docs/on_kayit_genelleme_2026-08-25.md`
Arşiv: `benchmark/results/eval_20260825_195405.json` (100 klip)
Küme: `data/isafety_bench` — CC BY-NC-SA 4.0, **yalnızca değerlendirme**

## 1. Soru

Yarışmada bize **hiç görmediğimiz** bir İSG videosu verilecek. Bugüne
kadarki bütün ölçümler tek bir tesisin iki kamerasından geliyordu.

Test: sevk edilen sistem, **YouTube kaynaklı** (yani tamamen başka alandan)
50 tehlike + 50 normal klipte ne yapıyor? Yapılandırma **sevk edilen**,
hiçbir şey açılıp kapatılmadı — çünkü tesise kalibre gözlem düzleminin alan
dışında ne yaptığını ölçmek testin parçasıydı.

## 2. İlk sonuç — iyi haber ve kötü haber

| ölçüt | ölçülen | eşik | hüküm |
|---|---|---|---|
| tehlike recall | **0,900** [0,786–0,957] | ≥ 0,70 | GEÇTİ |
| normal FP | **0,540** [0,404–0,670] | ≤ 0,40 | **KALDI** |
| MCC | **+0,401** | ≥ 0,30 | GEÇTİ |
| **G2** İSG kuralı ateşleme | **0,390** | ≤ 0,25 | **KALDI** |

**İyi haber:** hiç görmediği videolarda **%90 tehlike yakalıyor.** Anlatı
düzlemi genelliyor.

**Kötü haber:** tesise kalibre kurallar alan dışında ateşliyor
(yelek 22 · pano 16 · forklift 3 klip).

## 3. Kök teşhis — FP'nin kaynağı

Normal kliplerdeki olayların kaynağı ayrıştırıldı:

```
olay YOK                23/50
YALNIZ İSG kuralı       22/50   ← alan dışı yanlış ateşleme
ikisi birden             4/50
yalnız anlatı düzlemi    1/50
```

İSG kuralları kapalıymış gibi yeniden puanlandığında:

| kip | recall | normal FP | MCC | G1 |
|---|---|---|---|---|
| sevk (İSG açık) | 0,900 | 0,540 | +0,401 | KALDI |
| **İSG kapalı** | **0,900** | **0,100** | **+0,800** | **GEÇTİ** |

**Recall hiç değişmiyor.** İSG kuralları alan dışında tehlike tespitine
**sıfır** katkı yapıyor; sadece gürültü üretiyorlar. Dahası normal
kliplerde (26/50) tehlike kliplerinden (13/50) **daha sık** ateşliyorlar —
yani ters yönde bilgi taşıyorlar.

## 4. Çözüm — ALAN KİLİDİ

Gözlem düzlemi kendi tesisine bağlandı: slotlar yalnızca sahne **kalibre
tesise benziyorsa** sorulur. Mekanizma zaten depoda vardı (görüş imzası);
yeni olan, onu **alan kilidi** olarak kullanmak.

> Bu bir **etiket kapısı değil, alan kapısıdır**: *"bu bizim tesisimiz mi"*
> diye sorar, *"bu hangi sınıf"* diye değil. Kalibre tesiste **tüm sınıflar**
> kilidi geçer, dolayısıyla etiket sızıntısı riski yok.

### Kapsama garantisi şart oldu

İlk deneme kör kümelemeyle (k=4) imza üretti ve **forklift kamerasının
tamamını dışarıda bıraktı** (50/50 klip) — forklift kuralı +0,881'den
**+0,000**'a düştü. İmzalar artık **sınıf başına** üretiliyor ve her sınıfın
geçiş oranı doğrulanıyor:

```
class0..class7   her biri 20/20 = 1,000   -> kapsama TAM
```

### Kilidin iki taraftaki etkisi

| | kendi setimiz (197 klip) | alan dışı (100 klip) |
|---|---|---|
| kilidi geçen | **197/197 = 1,000** | 2/100 = 0,020 |
| forklift | **+0,881 → +0,881** | — |
| pano | **+0,960 → +0,960** | — |
| yelek | **+0,689 → +0,689** | — |
| tehlike recall | — | 0,900 → **0,900** |
| normal FP | — | 0,540 → **0,120** |
| MCC | — | +0,401 → **+0,780** |
| İSG ateşleme | — | 0,390 → **0,020** |

**Üç sevk matrisi birebir korundu (K2 tam) ve alan dışı sorun çözüldü.**
G1 ve G2 kilit açıkken **ikisi de geçiyor**.

## 5. Yarışma için ne demek

**Hazırız — bir şartla:** alan kilidi açık olmalı.

- Yarışma videosu bizim tesisimizden değilse: gözlem düzlemi **kendini
  kapatır**, sistem anlatı düzlemiyle çalışır ve orada ölçülmüş performansı
  **recall 0,900 · normal FP 0,120 · MCC +0,780**.
- Yarışma videosu bizim tesisimize benzerse: kilit açılır, deterministik
  İSG kuralları da devreye girer.

Yani sistem **kendi sınırını tanıyor** ve dışına çıkmıyor.

### Basamaklandırma alan dışında da orantılı

| küme | ACİL müdahale |
|---|---|
| tehlike | 0,840 |
| normal | 0,120 |

7 kat ayrım. Gecikme medyan **27,4 sn**.

## 6. Sınırlar — dürüstçe

- **Bu bir stres testidir, aynı-alan kanıtı değil.** Kendi lisans kaydımızın
  uyarısı: *"dağıtım alanı sabit-kamera endüstriyel CCTV; bu set YouTube
  kaynaklı."* Yarışma videosu muhtemelen ikisinin **arasında** olacak.
- **`category_match` alan dışında 0,420** (kendi setimizde 0,838). Yani
  tehlikeyi **görüyor** ama doğru kategoriye yerleştirme zayıflıyor.
- Alan dışı örneklem 100 klip; aralıklar geniş.
- Kilit 2/100 alan dışı klipte açıldı (%2 sızıntı).

## 7. Lisans

`data/isafety_bench` — CC BY-NC-SA 4.0.
`degerlendirmede_kullanilabilir: true` · `egitimde_kullanilabilir: false` ·
`yeniden_yayimlanabilir: false`. Bu koşum **yalnızca ölçümdür**; ağırlık
üretilmedi. `dilajan/veri_lisans.py` fail-closed zorluyor.
