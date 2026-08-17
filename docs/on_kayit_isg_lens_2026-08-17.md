# ÖN-KAYIT — İSG merceği A/B (D36)

**Yazılma zamanı: ölçüm KOŞULMADAN ÖNCE.** Eşikler sonradan değiştirilmeyecek.
Değiştirilirse bu dosyanın git geçmişinde görünür.

## Hipotez

`eval_defense`'te anomali kliplerinin %72'si sıfır olay üretiyor. Özetler boş değil,
**kendinden emin olumsuz**: *"herhangi bir tehlike, kaza, yetkisiz giriş veya anormal
davranış gözlemlenmedi"*. Yani model aradığını bulamıyor değil — **yanlış şeyi arıyor.**

`SEGMENT_DESCRIBE_INSTRUCTION` bir suç/güvenlik sözlüğüdür ve İSG tehlikelerini açıkça
yasaklar (*"ekipman/yük taşıma OLAY DEĞİLDİR"*). `ISG_LENS_SUFFIX` sapma sözlüğünü İSG'ye
genişletir ve bastırma cümlelerine açık istisna getirir.

**H1:** İSG merceği açıkken `eval_defense/Anomali` recall'ü anlamlı biçimde artar.

## Kollar

| kol | yapılandırma |
|---|---|
| **C** (taban) | mevcut varsayılan — `isg_lens=False`. **Yeniden koşulmaz**, arşiv kullanılır: `eval_20260816_111114` (Anomali) + `eval_20260816_113306` (Normal) |
| **D** (yeni) | `DILAJAN_ISG_LENS=true`. Başka HİÇBİR ayar değişmez (`facility_rules` boş, `ppe_detection` kapalı, T=0, 8B) |

## Ön-kayıtlı eşikler — MEKANİK uygulanacak

Taban değerler (8B, eval_defense n=100+100):
recall **%28** · tespit MCC **+0,069** · hassasiyet **0,560** · operasyonel FP **%22** ·
medyan gecikme **11,55 sn** · gürültü tabanı **8 puan**.

### KABUL — dördü de sağlanmalı

| # | ölçüt | eşik |
|---|---|---|
| 1 | recall artışı | **≥ +16 puan** (gürültü tabanının 2×'i) |
| 2 | eşleşmiş anlamlılık | McNemar **p ≤ 0,05** |
| 3 | **tespit MCC artışı** | **≥ +0,05** (yani ≥ 0,119) |
| 4 | operasyonel FP artışı | **≤ +10 puan** |

### RET — biri yeterli

| # | ölçüt | eşik |
|---|---|---|
| 1 | MCC artışı | **< +0,02** — D33'ün 0,069→0,071'inin tekrarı; eşik düşürme demektir |
| 2 | operasyonel FP artışı | **> +15 puan** |
| 3 | medyan gecikme | **> 1,5×** (model değişmiyor, yalnız prompt uzuyor) |

### BELİRSİZ

Arada kalırsa **`isg_lens` KAPALI kalır.** Varsayılanı değiştirmemek bedavadır;
değiştirmek kanıt gerektirir.

## Neden MCC şart koşuldu

Bu projede recall **iki kez** eşik düşürerek "arttı":

| olay | recall | MCC |
|---|---|---|
| D33 `facility_rules` enjeksiyonu | %28 → %47 (+19) | 0,069 → 0,071 (**değişmedi**) |
| D36 Qwen3.8-27B | %28 → %40 (+12) | 0,069 → 0,083 (hassasiyet 0,560 → 0,556 **aynı**) |

İkisinde de hassasiyet sabit kaldı, FP orantılı arttı — çalışma noktası aynı ROC eğrisi
üzerinde kaydı. **Recall ve F2 tek başına raporlanırsa ikisi de "başarı" görünür.**
Bu yüzden MCC bu ön-kayıtta ZORUNLU kriterdir.

## Ölçülecek ama karar vermeyecek (gözlem)

- Sınıf bazlı recall — özellikle `Opened_Panel_Cover`.
  **Mercek onu düzeltmeyi vaat ETMİYOR**: D33'te `guided_choice` ile zorunlu seçimde VLM
  20/20 "KAPALI" dedi (10'u açıktı). Bu bir algı sınırıdır, sözcük dağarcığı sorunu değil.
  Düzelirse şaşırırız ve nedenini araştırırız; düzelmezse hipotez zaten bunu öngörüyordu.
- Kategori eşleşmesi (strict/loose) — eşleştiricinin İSG sözlüğüne körlüğü ayrı sorun (P4).
- Sevk kapısı MCC'si — ayrı sorun (P2), bu mercek onu hedeflemiyor.

## Koşum

```bash
DILAJAN_ISG_LENS=true DILAJAN_EVAL_DIR=data/eval_defense EVAL_CATS=Anomali DILAJAN_TEMPERATURE=0 python benchmark/eval_clips.py
DILAJAN_ISG_LENS=true DILAJAN_EVAL_DIR=data/eval_defense EVAL_CATS=Normal  DILAJAN_TEMPERATURE=0 python benchmark/eval_clips.py
```

---

# SONUÇ (koşuldu 2026-08-17) — **RET**

Arşiv: `eval_20260817_143517.json` (Anomali) · `eval_20260817_145730.json` (Normal).
Künye doğrulandı: `isg_lens=True`, model `Qwen3-VL-8B-Instruct-FP8`.

| | C (taban) | D (mercek) | fark |
|---|---|---|---|
| recall | 0,280 | **0,440** | **+16,0 puan** |
| **hassasiyet** | **0,560** | **0,489** | **−0,071** |
| **tespit MCC** | **+0,069** | **−0,020** | **−0,089** |
| operasyonel FP | 22 | **46** | **+24** |
| kategori | 26 | 32 | +6 |
| medyan gecikme | 11,6 sn | 12,7 sn | 1,10× |

### Eşiklerin mekanik uygulaması

| KABUL (dördü de) | eşik | ölçülen | sonuç |
|---|---|---|---|
| 1 recall artışı | ≥ +16 | **+16,0** | **GEÇTİ** |
| 2 McNemar p | ≤ 0,05 | 0,0226 | GEÇTİ |
| 3 MCC artışı | ≥ +0,05 | **−0,089** | KALDI |
| 4 opFP artışı | ≤ +10 | **+24** | KALDI |

| RET (biri yeterli) | eşik | ölçülen | tetik |
|---|---|---|---|
| 1 MCC artışı < +0,02 | eşik düşürme | **−0,089** | **TETİK** |
| 2 opFP artışı > +15 | | **+24** | **TETİK** |
| 3 gecikme > 1,5× | | 1,10× | — |

→ **KARAR: RET.** `isg_lens` varsayılan KAPALI kalır.

⚠️ Karar betiği 1. kriteri "KALDI" yazdı; bu bir **kayan nokta artefaktı**
(`0,44 − 0,28 = 0,15999999999999998 < 0,16`). Gerçekte recall artışı **tam +16 puan**
ve eşiği **karşılıyor**. Karar bundan etkilenmez — 3 ve 4 açık farkla kalıyor.

## Ne öğrendik

**Hipotezin YÖNÜ doğrulandı, UYGULAMASI reddedildi.**

Recall gerçekten arttı (+16 puan = gürültü tabanının 2×'i, p=0,023) ve tam da
bastırılan sınıflarda:

| sınıf | C | D |
|---|---|---|
| `Opened_Panel_Cover` | %8 | **%44** |
| `Carrying_Overload_with_Forklift` | %20 | **%40** |
| `Unauthorized_Intervention` | %36 | **%44** |
| `Safe_Walkway_Violation` | %48 | %48 (değişmedi) |

**AMA bedeli kazançtan büyük:** hassasiyet 0,560 → 0,489, operasyonel FP 22 → 46
(iki katından fazla). MCC **pozitiften negatife** düştü. Yani mercek modele yeni
bir *görme* yeteneği kazandırmadı; **her yerde tehlike görmesini** sağladı.

Bu, D33 (`facility_rules`) ve D36 (27B) ile aynı hikâyenin ÜÇÜNCÜ tekrarıdır:
**recall satın alınabilir, ayırt etme edilemez.**

### `Opened_Panel_Cover` %8 → %44: dikkat, bu bir başarı DEĞİL

Ön-kayıtta *"mercek bunu düzeltmeyi vaat ETMİYOR, bu bir algı sınırıdır"* yazmıştım.
36 puan sıçradı. İki açıklama var ve FP'nin ikiye katlanması ikincisini işaret ediyor:

1. D33'ün `guided_choice` sonucu yanlış/dardı, veya
2. **Model artık her klipte "pano açık" diyor** — doğru olduğu için değil.

Ayırt etmenin tek yolu: aynı sınıfın NORMAL kliplerinde de aynı sıçrama var mı.
Karar için kullanılmadı; ön-kayıt bunu gözlem olarak işaretlemişti.

## Sonraki hipotez (YENİ ön-kayıt gerektirir)

Sorun sözcük dağarcığının **darlığı** değilmiş — **kanıt eşiğinin gevşekliği**.
Mercek "şunları da say" diyor ama "şu kadar kanıt görmeden sayma" demiyor.

⚠️ **P-hacking riski:** prompt'u metrik geçene kadar döndürmek ölçüm değildir.
Bir sonraki deneme AYRI ön-kayıt dosyası alacak ve iterasyon numarası
raporlanacak — "ilk denemede tuttu" izlenimi verilmeyecek.
