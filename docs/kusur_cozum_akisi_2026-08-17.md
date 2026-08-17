# D36 — Kusur çözüm iş akışı: **7 yamanın 7'si de reddedildi**

7 ölçülmüş kusur için somut yama tasarlandı, her biri **üç bağımsız karşıtsal lensle**
(görünürlük · elenmişlik · gerileme) denetlendi. **21/21 denetim GEÇERSİZ dedi.**

Bu bir başarısızlık değil: denetimlerin tamamı **arşivden, GPU harcamadan**, aritmetikle
gösterdi ki bu yamalar **kendi ön-kayıtlı eşiklerini geçemez**. Tahminen 10+ saat GPU
kurtarıldı.

---

## Reddedilme gerekçeleri

### D1 — İSG merceğini birincil metrik yapmak → **ÖN-KAYIT KİRLİ**

`ISG_LENS_SUFFIX` (benim yazdığım mercek), skorlayıcının aradığı kalıpları
**neredeyse birebir içeriyor**: *"yaya yolu"*, *"dengesiz yük"*, *"elle müdahale"*,
*"elektrik panosu / kapak açık"* — **dört güvensiz sınıfın dördü için de**.

Ölçüldü: taban kolunda **hiç tetiklenmeyen** bu kalıplar mercek kolunda tetikleniyor
(yaya yolu ×6, dengesiz yük ×3, elle müdahale ×3).

> **Mercek modele, metriğin ödüllendirdiği kelimeleri söylemeyi öğretiyor.**
> Bu yetenek değil, **metrik oyunu**.

Ayrıca `MCC_özgül` duyarlılığı **±0,03/klip** — yani **tek klip ≈ eşiğin tamamı**.
Aynı yapılandırmanın tekrar koşusunda özgül-pozitif 3→0 oynuyor.

### D2 — Olumsuzlama kapısı → **geri çekilmiş ölçü + kapı zaten çalışmıyor**

1. Önerilen *"adlandırma-MCC"*, projenin **2026-08-11'de resmen geri çektiği**
   VARLIK ölçüsü: *"herhangi bir taksonomi kelimesi = VARLIK; ölçülmesi gereken
   DOĞRU kategori = DOĞRULUK; ikisi karıştırıldı"*.
2. Onarık kapı **kalıbı zaten elemiyor**: `labels.py:401 _AYIRAC_RE` **virgülü**
   cümlecik ayıracı sayıyor. Modelin şablonu
   *"...tehlike, kaza, yetkisiz giriş veya anormal davranış gözlemlenmedi"*
   cümleciklere bölününce **olumsuzlama, eşleşmeden farklı cümlecikte kalıyor**.

### D3 — Düşürme merdiveni → **tavan, kabul barının ALTINDA**

- Kurtarılabilir havuzun **tamamı 19 olay** (13 anomali / 6 normal).
- **Nedensel hikâye kodda yanlış:** yama `_VERIFY_PROMPT`'u onarıyor ama merdivenin
  kararını `_REEX_PROMPT` veriyor — yama o sabite **dokunmuyor**.
- `reexamine` tek kez koşuyor → yukarı kol Düşük'ü en fazla **Orta**'ya taşır (=2),
  sıkı kapı ise **≥3** istiyor. **Cebirsel olarak imkânsız.**

### D5 / D37 — Düşme silme → **Türkçe büyük-İ hatası**

Silme predikatı, gerekçe saydığı kliplerin **yarısını yakalayamıyor**:
`"İşçi".lower()` = `i` + U+0307 → `_PERSON_RE`'deki `işçi` ile eşleşmiyor.
İddia edilen 6 klip gerçekte **3**.

→ **Bu hatanın kendisi gerçek ve düzeltildi** (aşağıya bakınız).

### D6 — Severity sözlüğü → **elenmiş yaklaşımın daha yıkıcı hali**

`n_events`'i değiştiren tek bileşen ("rutin-betim kapısı"),
`iyilestirmeler.md:718-723`'te **2026-06-23'te ölçülerek reddedilmiş** "benign-kapı"nın
daha sert hali: o yalnızca severity düşürüyordu, bu **siliyor** ve hiçbir şey sormuyor.
Kanıt kaynağı hâlâ **VLM'in kendi metni üzerinde regex** — bağımsız kanıt yok.

### D7 — Sevk kapısı → **`n_events≥2` KANIT değil SÜRE ölçüyor**

Olaylar **segment başına** üretiliyor ve `segment_seconds=10`. Ölçüldü (temiz 197):

| n_events | medyan klip süresi |
|---|---|
| 0 | 7,0 sn |
| 1 | 10,0 sn |
| 2 | 11,0 sn |
| 3 | 15,0 sn |

Tek segmentli (≤10 sn) kliplerde n≥2 oranı **%3,2**; çok segmentlide **%14,6–%34,1**
(4–9 kat). Yani "en az 2 olay" koşulu **uzun klibi** seçiyor, **kanıtlı klibi** değil.

Ayrıca OR-kapısının `max_intrinsic≥Yüksek` terimi **net zararlı**: 8B'de +1 TP / +3 FP.

### D8 — Eşleştirici morfolojisi → **ölü kod + D33 kusurunun aynası**

1. **Kesme işareti dalı ispatlanabilir ölü kod:** kökten sonra `'` gelirse
   `isalnum()` False → `k == j` → kalıntı `""` → `_ek_zinciri_gecerli("")` **her zaman
   True** → break. İkinci aday **hiç değerlendirilmiyor**. Sayaç takıldı: 5 kez üretildi,
   **0 kez kazandı**.
2. **'y' kaynaştırma kuralı olumsuz fiilleri açıyor:** `düşmeyecek`, `devrilmeyecek`,
   `yanmayan`, `engellemeyen` — eski zincir hepsini reddediyordu, yeni kural kabul
   ediyor. **İki olumsuzlama kapısı da bu aileyi görmüyor** → D33 kusurunun aynası.

---

## ✅ Akıştan çıkan GERÇEK kazanç: Türkçe büyük-İ hatası

Karşıtsal denetimlerin yan ürünü. **Mevcut üretim kodunda, tasarım değil açık hata.**

```python
"İşçi".lower()  ->  "i" + U+0307 + "şçi"    # regex "işçi" ile ESLESMEZ
```

**Ölçüldü (6 arşiv, 267 olay metni): %13,5'i (36 olay) etkileniyordu.**
Ve tam da önemli olanlar:

> *"İşçi zemine düşmüş ve hareketsiz kalmış"* · *"İşçi ani şekilde devrildi ve yere düştü"* · *"İşçi yere düştü"*

**İki katlı etkisi:**
1. `_is_person_fall_event` False döner → `verify_pose_falls` o olaya **hiç uygulanmaz**
2. `_calibrate_severity`'deki NESNE-vs-KİŞİ mantığı kişiyi **nesne sanar** → düşme
   severity'sini yükseltmez

**Düzeltildi:** `dilajan/agent/graph.py` içine `_tr_lower` eklendi (aynı çözüm
`benchmark/labels.py:402`'de zaten vardı; ajan katmanı benchmark'a bağımlı olmasın
diye bilinçli olarak tekrarlandı). `tests/test_tr_lower.py` ile kilitlendi — 19 kontrol.

---

## 🔴 Meta-ders: müdahale havuzları çok küçük

D3'ün kurtarılabilir havuzunun **tamamı 19 olay**. D5'inki **3 klip**. D7'nin ek terimi
**net zararlı**. Yani bu boru hattını yamayarak `eval_defense`'te anlamlı kazanç
**elde edilemez** — yamaların kalitesinden bağımsız olarak.

Veri denetimi de aynı yere çıkmıştı: **AUC(aynı etiket) = 0,538**, yani Anomali ile
Normal arasındaki fark gerçekten **ince ve davranışsal**. Setin zorluğu meşru, ama
ayırt edici sinyal **zayıf**.

### Bunun anlamı

`eval_defense` üzerinde boru hattı optimizasyonu **doygunluğa ulaştı**. Kalan 9 günde
buraya harcanan her saat, şartnamenin puan verdiği alanlardan (**Otonomi %20**,
**Fonksiyonellik %35**) çalınmış olur.

**Öneri:** bu cephede durulsun. Ölçüm külliyatı, hata analizi ve veri denetimi zaten
**Mimari %35** için güçlü bir anlatı sağlıyor — *"iyileştiremedik"* değil,
*"nerede iyileştirilemeyeceğini ölçtük ve gösterdik"*.
