# ÖN KAYIT — Kol 2/3/4, **2. koşum** (düzeltilmiş aletler)

Tarih: **2026-08-25**, koşumdan **ÖNCE**. Dal: `d34-isg-veri-kkd`
Önceki: [ön kayıt 1](on_kayit_turkce_kol234_2026-08-25.md) ·
[**1. koşum: ÜÇÜ DE RET**](sonuc_turkce_kol234_kosum1_2026-08-25.md)

## 0. Neden ikinci koşum meşru

1. koşumun RET'leri **kayıtta kalır ve silinmez**. İkinci koşum yapılıyor
çünkü üç ölçütün üçü de **veriye bakılmadan kanıtlanabilir** biçimde
kırıktı — hüküm modelin değil **aletin** hükmüydü:

| kusur | kanıt (sonuçtan bağımsız) | onarım |
|---|---|---|
| varyant dizgesi kanoniğin **alt-dizgesi** (`"kontrol panosu"` ⊂ `"elektrik/kontrol panosu"`) → her kanonik geçiş varyant da sayılıyor, **tavan 0,50**, eşik 0,70 | terim tablosundan türetilir | kanonik geçişler **maskelenir**; 3 sentetik kontrolle doğrulandı (1,000 / 0,000 / 0,500) |
| payda, kolun **değiştiremediği** olay metnini içeriyor | kol yalnız özet promptunu kısıtlar | ölçüt **özet düzleminde** kurulur |
| `tekrar_4gram_orani` **korpus boyutuna** bağlı (15→0,228 · 60→0,415 · 855→0,861) | aynı taban özetleriyle ölçüldü | eşik **aynı koşumun eşleşmiş tabanına** göre kurulur |
| dejenerelik kapısı özdeş **girdileri** de cezalandırıyor | `temperature=0`'da özdeş girdi → özdeş çıktı **doğru** davranıştır | kapı yalnız **olay metni FARKLI** klipler üzerinde çalışır |

**Kol 4 ayrıca değiştirildi** (zayıflık kolda, ölçütte değil): kısıt
yasaklama kipindeydi, **olumlu talimata** çevrildi + açık yasak listesi.

**Yeni tohum: `seed=11`.** 1. koşumun 60 klibi tekrar kullanılmaz.

## 1. Düzenek (1. koşumla aynı, tek fark tohum)

Eşleşmiş, 4 koşul (TABAN / Kol2 / Kol3 / Kol4) × **60 klip**,
`temperature=0.0`, arşivdeki olaylardan özet yeniden üretilir.
Kol 3 olay metni regex ile yeni şablona çevrilir; **kalıntı = 0** olmalı.

## 2. KABUL ÖLÇÜTLERİ (bu koşum için bağlayıcı)

Tüm ölçütler **aynı koşumun eşleşmiş TABANINA** göre; hiçbiri başka bir
korpustan ithal edilmez.

### Kol 2 — terim sözlüğü
Payda **sabitlenir**: pano olayı içeren klipler (özet hepsinde panodan
bahsediyor — 1. koşumda 21/21, koşum başında **doğrulanacak**; bahsetmeyen
klip çıkarsa payda ondan **arındırılır** ve rakam bildirilir).
- **KABUL:** `ozet_kanonik_pano` **≥ taban + 0,25 mutlak** **ve**
  `ozet_kanonik_yelek`, `ozet_kanonik_yaya_yolu` düşmeyecek.

### Kol 3 — şablon onarımı (kalıcı, bayraksız)
- **ZORUNLU KAPI:** `tests/test_sablon_kalip.py` geçecek.
- **KABUL:** `olcek_sizintisi_olay` **≤ 0,10** **ve**
  `forklift_celiskisi` **≤ 0,05**.

### Kol 4 — üslup kısıtı
- **KABUL (üçü birden):** `acilis_Goruntu` **≤ 0,20**
  **ve** `meta_son_cumle` tabandan **düşük**
  **ve** `ort_karakter` tabandan **düşük**.
  (`tekrar_4gram` ölçüt DEĞİL — korpus-bağımlı; yine de **raporlanır**.)

## 3. ZORUNLU KORUMA KAPILARI (değişmedi + biri EKLENDİ)

| # | kapı | saparsa |
|---|---|---|
| K-a | `isg_match` vektörü tabandan sapmayacak (Kol 3 için gerçek risk) | **RET** |
| K-b | `category_match`: McNemar exact tek yönlü p ≥ 0,05 **ve** mutlak düşüş ≤ 3 puan | **RET** |
| K-c | Çıktı sözleşmesi TAM 4 anahtar (K1) | **RET** |
| **K-e** *(YENİ)* | **OLAY DÜŞÜRME artmayacak:** kural tetiklendi, olay listesinde var, ama özet tehlikeyi hiç anmıyor. 1. koşum tabanı **5/69 = 0,072** (hepsi yelek kuralında). Mevcut hiçbir metrik bunu göremez — `isg_match` olay metnini DE okur, jüri ise özeti okur. | **RET** |

## 4. ÖN-RET KAPILARI (dejenerelik kapısı DÜZELTİLDİ)

| # | kapı |
|---|---|
| a | **DEJENERELİK (düzeltilmiş):** özdeş özet çifti, yalnız **olay metni FARKLI** klipler arasında sayılır. Bu sayı artarsa RET. Özdeş girdiden özdeş çıktı `temperature=0`'da **doğru** davranıştır ve cezalandırılmaz. |
| b | **KAPSAM** — 60 klipten < 45'inde özet üretilemezse ölçüm geçersiz |
| c | **UYDURMA** — özet, olay listesinde bulunmayan tehlike adı üretirse 5 örnek el ile denetlenir |

## 5. Ne olursa ne yapılacak

| sonuç | eylem |
|---|---|
| Kol 2 / Kol 4 geçer | bayrak **açık** sevk edilir + sayaç testine bağlanır |
| Kol 3 geçer | şablon onarımı **kalır** (kalıp testiyle korunur) |
| Kol 3 kalır | şablonlar **geri alınır** (`git revert` düzeyinde) |
| kol kalır | bayrak **kapalı**, ret gerekçesi koda yazılır |

Üçüncü bir koşum **yapılmayacak**. Bu ölçütler bağlayıcıdır.

---

## 6. EK ÖN KAYIT — **BİRLEŞİK KOL** (koşumdan önce yazıldı)

2. koşumda üç kol da tek tek geçti. Ancak sevk edilecek yapılandırma
**Kol 3 şablonları + Kol 2 açık + Kol 4 açık** — yani **üçü birlikte**.
Kollar etkileşebilir ve buna dair **ölçülmüş** bir kanıt var:

> Kol 4 tek başına `ozet_kanonik_pano`'yu **0,571 → 0,158**'e düşürdü.
> Üslup kısıtı modeli kanonik terimden uzaklaştırıyor. Kol 2 aynı sayacı
> 1,000'e çıkarıyor. **Bileşke hangi yöne gider, bilinmiyor.**

Tek tek ölçülmüş kolları birlikte sevk etmek **ölçülmemiş bir
yapılandırmayı sevk etmektir**. Bu yüzden ayrı bir koşum yapılır.

- **Örneklem:** **üçüncü ayrık dilim** (tohum 11, `[120:180]`). 1. ve 2.
  koşumun klipleri tekrar kullanılmaz.
- **Koşul:** TABAN vs **BİRLEŞİK** (Kol 3 olay metni + iki prompt eki).

### KABUL — üç kolun ölçütü de AYNI ANDA sağlanacak
| kaynak | ölçüt |
|---|---|
| Kol 2 | `ozet_kanonik_pano ≥ taban + 0,25` **ve** yelek/yaya düşmeyecek |
| Kol 3 | `olcek_sizintisi_olay ≤ 0,10` **ve** `forklift_celiskisi ≤ 0,05` |
| Kol 4 | `acilis_Goruntu ≤ 0,20` **ve** `meta_son_cumle` < taban **ve** `ort_karakter` < taban |

### KORUMA — K-a, K-b, K-c, K-e ve düzeltilmiş ön-ret (a) aynen geçerli.

**Biri bile saparsa birleşik yapılandırma RET** ve bayraklar **kapalı**
sevk edilir (K2 gereği kapalıyken davranış bayt özdeş).

## 7. SEVK SICAKLIĞI DOĞRULAMASI (koşumdan önce)

1. ön kayıt, kabul eden kol için sevk sıcaklığında (`temperature=0.2`)
tekrar sayım sözü vermişti. **20 klip**, dördüncü ayrık dilim
(`[180:200]`), TABAN vs BİRLEŞİK.
- **KABUL:** `acilis_Goruntu ≤ 0,20` **ve** `olay_dusurme` tabandan
  **artmayacak** **ve** `ozet_kanonik_pano` tabandan **yüksek**.
- Sapma olursa bayraklar **kapalı** sevk edilir.

### 7b. Sıcaklık doğrulaması n=20'de **K-b'yi tanımsız** buldu
n=20'de bir klip **5,0 puan** eder; K-b'nin "mutlak düşüş ≤ 3 puan" kanadı
bu boyutta **sıfır** değişime izin verir — kapı yapısal olarak sağlanamaz.
(Ölçüldü: `category_match` 11→10, McNemar p=0,500 — istatistik kanat
kötüleşme görmüyor.) Kapı **yeniden yorumlanmaz**; doğrulama, kapının
tanımlı olduğu boyutta (**n=60**, beşinci ayrık dilim `[200:260]`,
`temperature=0.2`) **tekrarlanır** ve hüküm oradan verilir.
n=20 sonucu kayıtta kalır.
