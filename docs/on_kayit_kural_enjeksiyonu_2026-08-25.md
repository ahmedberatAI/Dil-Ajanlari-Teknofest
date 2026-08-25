# ÖN KAYIT — tesis kuralı enjeksiyonu, gözlem düzlemi AÇIKKEN

Tarih: **2026-08-25**, koşumdan **ÖNCE**. Dal: `d34-isg-veri-kkd`

## 0. Neden bu kol

`isg_match` açığının tamamı `Safe_Walkway_Violation` sınıfında ve o sınıf
**0/25**. Bugün üç mekanizma daha denendi ve üçü de reddedildi
(yerel nitelik sorusu, çapraz ön koşul, tespit-tabanlı geofence).

Bugün ayrıca **ölçüldü** ki: bu klip çiftinde etiket, kişiler silinmiş arka
plandan **%72,9** doğrulukla tahmin edilebiliyor. Yani mekân/çerçeve temelli
her yöntem karıştırıcıyı okuma riski taşıyor.

Ve bugün fark edildi ki: **`facility_rules` bütün koşumlarda BOŞTU.**
Model, "işaretli yürüme yolunun dışına çıkmak ihlaldir" kuralını **hiç
bilmiyordu.** Yaya yolu kliplerinin özetlerinde 25 klipte `yol` sözcüğü
**sıfır** kez geçiyor; `makine` 14 kez geçiyor. Model gördüğünü anlatıyor
ama neyin ihlal sayıldığını bilmiyor.

TEKNOFEST senaryosunun kendisi tam olarak budur: tesis kurallarını bildirir,
ajan uygular.

## 1. Bu ölçüm neden YENİ

`facility_rules` daha önce A/B edildi (**D33, 2026-08-16**, `docs/HANDOFF.md`):
anomali recall %28 → %47 (p=0,0094), İSG tam doğru %1 → %16 (p=0,0001),
normal FP %22 → %40 (p=0,0021), **MCC 0,069 → 0,071 (değişmedi)**.
O zamanki yorum: *"kazanç eşik düşürme, yetenek değil"*.

**Ama o ölçüm gözlem düzleminden ÖNCE yapıldı** — sistemin İSG ayrımı o
tarihte şans düzeyindeydi (MCC 0,07). Bugün üç sınıf deterministik kuralla
**+0,881 ile +0,960** arasında kapsanıyor.

Yani sorulan soru farklı: *"gözlem düzlemi üç sınıfı deterministik olarak
kapsarken, kural enjeksiyonu DÖRDÜNCÜ sınıfı diğer üçünü bozmadan ekliyor mu?"*
Bu yapılandırma **hiç ölçülmedi**.

## 2. Kol

`DILAJAN_FACILITY_RULES` = `scripts/run_policy_ab.py::FACILITY_RULES`
(dört maddeyi de içerir — tesis bütün kurallarını bildirir).
Gözlem düzlemi **sevk yapılandırmasıyla aynı** kalır
(`catal_kasa_sayisi, makine_basinda_yelek, pano_koyuluk_0_10`).
`slot_guven=1` (teşhis için, davranışı değiştirmiyor — 8/8 doğrulandı).

## 3. KABUL ÖLÇÜTÜ — DÖRDÜ BİRDEN

| # | kapı | eşik | mevcut |
|---|---|---|---|
| **P** | **BİRİNCİL:** `Safe_Walkway_Violation` isg_match | **≥ 0,50** | 0,000 |
| A | yaya yolu ÇİFT doğruluğu (ihlal işaretlenir / normal işaretlenmez) | **≥ 0,80** | — |
| B | üç sevk kuralının çift MCC'si | hiçbiri **0,05'ten fazla** düşmeyecek | +0,881 / +0,960 / +0,689 |
| C | normal kliplerde **acil müdahale** oranı | **≤ 0,15** | 0,082 |

**Dördü birden sağlanmazsa RET.**

**Kapı A neden 0,80:** bu çiftte yalnız çerçeveden **0,729** doğruluk elde
ediliyor. 0,80 eşiği, kazancın çerçeveden değil **kuraldan** geldiğini
gösterecek gerçek bir marjdır. Kapı A, "kural verilince model her klibe
yaya yolu ihlali der" dejenerasyonunu da yakalar.

Kapı A'nın ölçümü: `Safe_Walkway_Violation` ve `Safe_Walkway` kliplerinde
üretilen metnin (olaylar + özet) yaya yolu kalıplarıyla eşleşip eşleşmediği.
Kalıp listesi **DEĞİŞTİRİLMEYECEK** — mevcut `ISG_SINIFLAR` listesi kullanılır.

**Kapı C neden var:** D33 ölçümü kural enjeksiyonunun normal FP'yi %22 → %40
çıkardığını gösterdi. Bugünkü ölçüm sevk basamaklandırmasının orantılı
olduğunu gösterdi (normal kliplerde acil %8,2). Kural enjeksiyonu bunu
bozarsa kazanç operasyonel olarak bedelli demektir.

## 4. ÖN-RET KAPILARI (sonuca bakmadan)

| # | kapı |
|---|---|
| a | **DEJENERELİK** — dört sınıfın hepsinde isg_match ≥ 0,90 çıkarsa model her klibe her şeyi diyordur → RET |
| b | **BULAŞMA** — kapı B'nin ihlali ölçümü geçersiz kılar; kol değerlendirilmez, önce sapmanın kaynağı bulunur |
| c | **KALIP OYNAMASI** — `ISG_SINIFLAR` kalıp listeleri bu koşum için değiştirilirse ölçüm geçersizdir. Değiştirilmeyecek. |

## 5. Ne olursa ne yapılacak

| sonuç | eylem |
|---|---|
| dört kapı da geçer | `facility_rules` sevke alınır; `isg_match` yeni değeriyle **eski değerinin yanına** yazılır |
| P geçer, A geçmez | kazanç dejenere — RET, ve "kural enjeksiyonu eşik düşürüyor" bulgusu D33 ile birlikte teyit edilmiş olur |
| P geçer, B geçmez | gözlem düzlemi ile kural enjeksiyonu ÇAKIŞIYOR → ayrı bir kol gerekir (yalnız yaya kuralını enjekte et) |
| P geçer, C geçmez | sevk edilebilir ama **operasyonel bedeli açıkça raporlanır** |
| P geçmez | yaya yolu sınıfı bu veriyle kapatılır; on birinci ret |

Hiçbir eski skor silinmeyecek. Bu koşum ayrı künye ile ayrı ara-kayıt
dosyasına yazılacak (`facility_rules_dolu` künyede zaten var).
