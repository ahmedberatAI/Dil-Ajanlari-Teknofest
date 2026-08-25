# Yelek kuralının ön koşul kapısı — yapısal olarak gereksiz

Tarih: **2026-08-25** · Arşiv: `eval_20260825_165802` (658 benzersiz içerik)
Yer gerçeği: kanonik (`benchmark/results/kanonik_etiket.json`)

## 0. DÜRÜSTLÜK NOTU — bu kol ön kayıtlı DEĞİL

Bu bulgu, hata dağılımına **bakılarak** keşfedildi; ölçüt koşumdan önce
yazılmadı. Etki tahmini bu yüzden iyimser olabilir. Aşağıda hem bunu
karşılayan kanıtlar hem de kalan şüphe açıkça yazılıyor.

Kolu meşru kılan asıl şey **veriden bağımsız bir mekanizma argümanıdır**:
*bir kapı çiftin negatif tarafında hiçbir şey tutmuyorsa, yalnızca
kaybettirebilir.* Bu, hiçbir sayı görülmeden de doğrudur.

## 1. Kusurun anatomisi

Tam sette yetkisiz müdahale kuralının **17 kaçırması** var. 197 klipte 6
kaçırma vardı ve iki sebebe ayrılıyordu; 3,5 kat veride desen netleşti:

| grup | n | `kişi` | `P(kişi≥1)` | `yelek` | güven |
|---|---|---|---|---|---|
| **A** | **12** | 0 | 0,005 – 0,559 | **YOK** | **1,000** |
| B | 5 | 3 | 1,000 | VAR | 0,905 – 0,998 |

**A grubunun tamamında yelek cevabı DOĞRU ve model kesin emin** (güven
1,000). Kaçıran şey algı değil, **ön koşul kapısı**: ayrı sorulan kişi
sayımı 0 diyor ve çelişkide kapı kazanıyor.

## 2. Kapı negatif tarafta HİÇBİR ŞEY tutmuyor

Doğru reddedilen 34 `Authorized_Intervention` klibinin dağılımı:

```
yelek VAR  → slot KENDİ tutuyor                34
sadece kapı tutuyor (yelek YOK ama kişi=0)      0
```

**Sıfır.** Kapının çiftin negatif tarafına katkısı yok. Yalnızca doğru
pozitifleri kesiyor.

Sebep yapısal: yelek slotunun seçenek kümesi
`[VAR, YOK, KISI_YOK, GORUNMUYOR]` — yani **"kişi var mı" sorusu slotun
içinde zaten soruluyor.** Model `YOK` dediğinde *"burada yeleksiz bir kişi
var"* demiş oluyor. Ayrı kapı aynı soruyu tekrar soruyor ve iki cevap
çeliştiğinde **zayıf olana** güveniyor.

## 3. Ölçüm

| kip | TP | FP | FN | TN | MCC | saha kes. | ateşleme |
|---|---|---|---|---|---|---|---|
| **sert kapı (sevk)** | 91 | 4 | 17 | 34 | **+0,679** | 0,268 | 340 |
| kapı p\*=0,50 | 92 | 4 | 16 | 34 | +0,690 | 0,258 | 356 |
| kapı p\*=0,30 | 96 | 4 | 12 | 34 | +0,740 | 0,245 | 392 |
| kapı p\*=0,20 | 98 | 4 | 10 | 34 | +0,767 | 0,238 | 412 |
| **KAPI YOK** | **103** | **4** | **5** | **34** | **+0,841** | **0,175** | **587** |

`FP` ve `TN` **hiçbir kipte değişmiyor** — mekanizma argümanının sayısal
karşılığı budur.

### Kazanç her iki ayrımda da tutuyor

| ayrım | n | sert kapı | kapı yok | ΔMCC |
|---|---|---|---|---|
| tümü | 146 | +0,679 | +0,841 | **+0,163** |
| `_tr` | 116 | +0,648 | +0,822 | +0,174 |
| `_te` | 30 | +0,733 | +0,874 | +0,141 |

Test ayrımında `FN` **2 → 0**. Kol veriye bakarak keşfedildiği için bu tam
bir holdout değil, ama iki ayrımda birden tutması destekleyici kanıttır.

## 4. Bedel — ve neden bu bir SEVK KARARI değil

Kapı kalkınca kural **658 klibin 587'sinde** ateşliyor (%89). Saha kesinliği
0,268 → 0,175.

Ek 247 ateşlemenin sınıf dağılımı: `class0` 94 · `class3` 49 · `class4` 32 ·
`class2` 27 · `class7` 27 · `class1` 12 · `class6` 10.

**Operasyonel değerlendirme:** her ateşleme olgusal olarak doğru olsa bile
(bu tesiste yeleksiz personel yaygın; 12/12 gözle doğrulanmıştı), kliplerin
%89'unda alarm üreten bir kural **operatöre bilgi taşımaz.** Çift içi MCC
+0,841 doğru bir sayıdır ama tek başına sevk gerekçesi değildir.

## 5. Denenen ve REDDEDİLEN çözüm: görüş muhafızı

Kapının eklenme gerekçesi kayıtlı: *"bu kapı olmadan kural forklift
kamerasında da ateşliyordu"*. Yani kapı aslında bir **sahne geçerliliği**
kontrolüydü, ama yanlış araçla.

Doğru araç görüş muhafızı gibi görünüyordu — yol slotunda kullanılıyor ve
forklift kamerasını 10/10 dışlıyor. **Mevcut bir ölçüm bunu yasakladı:**

> Bu çiftte **görüş, etiketle 0,833 korele** (`tests/test_gorus_muhafizi.py`).
> Muhafız sahne geçerliliği yerine **etiketi sızdırırdı.**

Yol slotunda muhafız meşru çünkü orada dışlanan kamera (forklift) **çiftin
dışında** kalıyor; yelek çiftinde ise görüş farkının kendisi etikete bağlı.

Ayrıca ölçüldü: muhafız ek ateşlemenin yalnızca **%31'ini** (76/247)
keserdi — kalan 171'i kamera 9'da, yani sahne zaten geçerli.

## 6. Durum

`yelek_on_kosul` ayarı eklendi, **varsayılan `True` = sevk edilen davranış**
(K2). Kol kodda hazır, açık değil.

**Sevk önerisi: HAYIR** — çift içi kazanç gerçek ve büyük, ama %89 ateşleme
oranı operasyonel olarak savunulamaz. Kolun asıl değeri şudur:

> Yetkisiz müdahale kuralının kaçırmalarının **12/17'si algı sorunu değil,
> kural tasarımı sorunudur.** Model doğru görüyor; kural onu susturuyor.

Bu, sınıfın tavanının +0,679 değil **+0,841** olduğunu gösterir — sadece o
tavana ulaşmanın kabul edilebilir bir yolu henüz bulunmadı.

## 7. Açık kalan yol

Kapının yerine geçebilecek, etiket sızdırmayan bir **sahne geçerliliği**
sinyali gerekiyor. Aday: panonun/makinenin kadrajda olup olmadığını ölçen
bir slot (panonun yeri **sabit** — pano kuralının +0,842'yi bu yüzden
alıyor). Ölçülmedi; ön kayıt gerektirir.
