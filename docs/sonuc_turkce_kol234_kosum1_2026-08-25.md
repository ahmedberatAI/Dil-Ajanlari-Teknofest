# SONUÇ — Kol 2/3/4, **1. koşum: ÜÇÜ DE RET**

Tarih: 2026-08-25 · Ön kayıt: [`on_kayit_turkce_kol234_2026-08-25.md`](on_kayit_turkce_kol234_2026-08-25.md)
Düzenek: eşleşmiş, n=60, tohum 7, `temperature=0.0`, 4 koşul × 60 = **240 özet**

**Bu hüküm değiştirilmeyecek.** Aşağıdaki tanı, hükmü geri almaz.

## Hüküm

| kol | kabul ölçütü | sonuç |
|---|---|---|
| **Kol 2** terim sözlüğü | `kanonik_oran_pano ≥ 0,70` | **0,391 → RET** |
| **Kol 3** şablon onarımı | ölçek sızıntısı ≤0,10 **ve** forklift çelişkisi ≤0,05 | ölçüt **geçti** (0,032 · 0/4) ama **ön-ret (a) dejenerelik ateşledi** (özdeş özet 8→11) → **RET** |
| **Kol 4** üslup kısıtı | üç ölçüt birden | `acilis_Goruntu` 0,383 (≤0,20 gerek) · `tekrar_4gram` −0,014 (−0,10 gerek) → **RET** |

## Koruma kapıları — üçünde de GEÇTİ

| kol | K-a `isg_match` | K-b `category_match` | K-c sözleşme |
|---|---|---|---|
| Kol 2 | 1 klip değişti (Safe_Walkway 8/10→9/10, **lehte**) | 42→41, McNemar p=0,500, düşüş 1,7 pun → geçti | 0 ihlal |
| Kol 3 | **birebir aynı** | 42→42, p=1,000 | 0 ihlal |
| Kol 4 | **birebir aynı** | 42→42, p=0,750 | 0 ihlal |

Kapsam kapısı: 60/60 özet üretildi (≥45 gerek). Kol 3 çevrimi **tam**: 50 olay
dönüştü, kalıntı **0**.

## Tanı — üç RET'in üçü de ÖLÇÜT kusuruna iniyor

Bu tanılar sonuçlara **bakılmadan da** kanıtlanabilirdi; kaçırılmış olmaları
düzeneğin kusurudur, kolların değil.

### 1. `kanonik_oran_pano` eşiği MATEMATİKSEL OLARAK ULAŞILAMAZ
Kanonik dizge `"elektrik/kontrol panosu"`, varyant dizge `"kontrol panosu"` —
varyant kanoniğin **alt-dizgesi**. `str.count` her kanonik geçişi aynı anda
varyant sayıyor → oranın **tavanı tam 0,50**. Eşik **0,70** konmuştu.
Ölçülen: Kol 2, özet düzleminde **gerçek varyantı sıfıra indirdi**
(taban 11 gerçek varyant → kol **2**, kalan ikisi de "pano kapağı").

### 2. Payda, kolun DEĞİŞTİREMEDİĞİ metni içeriyor
Sayaç `özet + olay` üzerinde çalışıyor. Kol yalnız **özet** promptunu
kısıtlar; olay metni **kural şablonundan** gelir. Olay düzleminde oran
taban ve kolda **aynı** (0,328 · 0,328) — sabit, hareket edemez.

### 3. `tekrar_4gram_orani` KORPUS BOYUTUNA bağlı
Aynı taban özetleri: 15 özette 0,228 · 30'da 0,315 · 45'te 0,398 ·
60'ta 0,415 · 855'te 0,861. **855'ten türetilmiş eşik 60'a uygulanamaz.**

### 4. Dejenerelik kapısı Kol 3 için YANLIŞ HEDEFLİ — sınandı ve doğrulandı
Kapının gerekçesi üslup kısıtları içindi. Kol 3'te yeni özdeş grupların
**5/5'i** kaldırılan ham sayıyla açıklanıyor: eski pano şablonu klip başına
değişen `(koyuluk N/10)` taşıyordu; o sayı çıkınca olay metinleri özdeşleşti,
`temperature=0`'da özdeş girdi özdeş çıktı verdi. Yani kaybolan çeşitlilik
**sahte çeşitlilikti** — ön kaydın kendisinin "kaldırılacak kusur" diye
adlandırdığı ham ölçek sızıntısı.

Sınama: yeni özdeş grupların eski olayları **farklıydı** (True), ham sayı
çıkarılınca **aynıydı** (True), yeni olayları **aynı** (True) → 5/5.

### 5. Kol 4'ün kaçırdığı ölçüt GEÇERLİ — kol zayıf, ölçüt değil
`acilis_Goruntu` ölçek-bağımsız bir orandır; 0,933 → 0,383 gerçek ve büyük
bir düşüş ama eşik 0,20'ydi. Kalan 23 özetin **hepsi** "Görüntülerde"(17) /
"Görüntüde"(3) / "Görüntülerde,"(3) ile başlıyor. Kısıt **yasaklama** kipinde
yazılmış; olumlu talimat verilmemiş.

Kolun ölçüt almayan ama ölçülen etkileri: `meta_son_cumle` 0,250→**0,083** ·
ortalama uzunluk 302→**264** karakter · özdeş özet çifti 8→**5**.

## Ne yapılacak

Ölçüt kusurları **kanıtlanabilir ve sonuçtan bağımsızdır**; kırık bir aleti
onarıp **yeni ön kayıtla, YENİ TOHUMLA** tekrar ölçmek meşrudur. Ama bu
koşumun RET'leri kayıtta kalır ve silinmez. 2. koşum ayrı ön kayıtla yapılır.
