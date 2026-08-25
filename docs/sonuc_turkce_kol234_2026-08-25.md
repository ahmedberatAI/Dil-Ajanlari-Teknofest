# SONUÇ — Türkçe üretim kolları 2/3/4: **SEVK EDİLDİ**

Tarih: 2026-08-25 · Dal: `d34-isg-veri-kkd`
Ön kayıtlar: [1](on_kayit_turkce_2026-08-25.md) ·
[2](on_kayit_turkce_kol234_2026-08-25.md) ·
[3 (düzeltilmiş)](on_kayit_turkce_kol234_kosum2_2026-08-25.md)
1. koşum: [**ÜÇÜ DE RET**](sonuc_turkce_kol234_kosum1_2026-08-25.md) — silinmedi.

## Hüküm

| kol | ne yapar | durum |
|---|---|---|
| **Kol 2** `ozet_terim_sozlugu` | özette İSG nesnelerinin **adlandırmasını** kanonik terime bağlar | **AÇIK sevk** |
| **Kol 3** şablon onarımı | kural şablonlarından **ham ölçek sızıntısını** ve forklift belirsizliğini kaldırır | **kalıcı** (bayraksız) |
| **Kol 4** `ozet_uslup_kisiti` | kalıp açılış, meta kapanış, ham ölçek ve talimat şerhi yasağı | **AÇIK sevk** |

## Sevk sıcaklığında ölçülen (n=60, `temperature=0.2`, eşleşmiş, beşinci ayrık dilim)

| sayaç | TABAN | BİRLEŞİK |
|---|---|---|
| kalıp açılış (`Görüntüde…`) | 0,917 | **0,000** |
| meta kapanış cümlesi | 0,417 | **0,133** |
| ortalama uzunluk (karakter) | 291,0 | **230,4** |
| olay metninde ham ölçek | 0,380 | **0,058** |
| **özet tehlikeyi düşürüyor** | **10/64** | **0/64** |
| kanonik terim — pano | 0,478 | **1,000** |
| kanonik terim — yelek | 0,583 | **1,000** |
| kanonik terim — yaya yolu | 0,696 | **0,935** |
| dejenerelik (farklı girdi → özdeş özet) | 0 | 0 |

**Koruma kapıları:** `isg_match` vektörü **birebir aynı** ·
`category_match` 37→37 (McNemar exact p=1,000) · sözleşme 0 ihlal ·
olay düşürme **artmadı, sıfırlandı**.

## Bunu bulmak dört koşum aldı — üçü ölçüt onarımıydı

| koşum | n | ne oldu |
|---|---|---|
| 1 (tohum 7, T=0,0) | 60×4 | **üçü de RET** — üç ölçütün üçü de kırıktı |
| 2 (tohum 11, T=0,0) | 60×4 | üçü de tek tek geçti; **etkileşim** görüldü |
| 3 birleşik (T=0,0) | 60×2 | birleşik geçti |
| 4 doğrulama (T=0,2) | 20×2 → 60×2 | n=20'de kapı **tanımsız** çıktı, n=60'ta hüküm |

### Kırık olan ölçütler — hepsi veriye bakmadan kanıtlanabilirdi
1. **Alt-dizge çift sayımı.** `"kontrol panosu"` ⊂ `"elektrik/kontrol panosu"`
   → her kanonik geçiş varyant da sayılıyor → **tavan 0,50**, eşik 0,70'ti.
   Sağlam bir kol bu yüzden RET aldı. Onarıldı, 3 sentetik kontrolle bağlandı.
2. **Payda, kolun değiştiremediği metni içeriyordu.** Sayaç `özet + olay`
   üzerindeydi; kol yalnız özeti kısıtlar, olay metni kural şablonundan gelir.
3. **`tekrar_4gram_orani` korpus boyutuna bağlı** (15→0,228 · 60→0,415 ·
   855→0,861). 855'ten türetilmiş eşik 60'a uygulanmıştı.
4. **Dejenerelik kapısı özdeş girdiyi cezalandırıyordu.** `temperature=0`'da
   özdeş girdi → özdeş çıktı **doğru** davranıştır. Kol 3'ün "kaybettiği"
   çeşitliliğin **5/5'i** kaldırılan `(koyuluk N/10)` ham sayısıyla açıklandı
   — yani **sahte çeşitlilikti**.
5. **K-b n=20'de tanımsız.** Bir klip 5,0 puan ederken "düşüş ≤ 3 puan"
   sıfır değişime izin verir. Kapı yeniden yorumlanmadı; **n=60'ta tekrar
   ölçüldü** ve orada geçti.

## Etkileşim — bu yüzden ikisi BİRLİKTE sevk edilir

Kol 4 **tek başına** `ozet_kanonik_pano`'yu **0,571 → 0,158** düşürüyor:
üslup kısıtı modeli kanonik terimden uzaklaştırıyor. Kol 2 aynı sayacı
1,000'e çıkarıyor ve birleşikte **Kol 2 baskın** (0,400 → 0,944).
**Yalnız birini açmak ölçülmemiş bir yapılandırmadır** —
`tests/test_turkce_kollari.py` ikisinin aynı durumda olmasını zorlar.

## Yeni bulunan kusur: özet, tespit edilen tehlikeyi düşürüyordu

Kural tetikliyor, olay listesinde var, **özet hiç anmıyor** — taban
**10/64**. Mevcut hiçbir metrik bunu göremezdi: `isg_match` ve
`category_match` olay metnini **de** okur, jüri ise **özeti** okur.
Birleşik yapılandırmada **0/64**. Artık `K-e` olarak kalıcı koruma kapısı.

## Sınırlar

- Ölçüm **arşivlenmiş olaylardan özet yeniden üretimiyle** yapıldı; video
  yeniden işlenmedi. Bu, gözlem düzlemini sabit tutar (eşleşmiş tasarımın
  amacı) ama kolların **algı** üzerindeki etkisini ölçmez — zaten yok:
  ikisi de yalnız özet promptuna ek yapar.
- 3. koşumun diliminde forklift klibi çıkmadı → `forklift_celiskisi 0/0`
  **boş** ölçüm. 2. koşumda 0/3, 4. koşumda 0/7 ölçüldü.
- Hakemli (LLM-judge) ölçüm **yapılmadı**: bu depodaki hakemler dejenere
  (`judge_independent` Risk ekseni 5,00 sıfır varyans). Tüm hüküm
  **deterministik sayaçlara** dayanır.
