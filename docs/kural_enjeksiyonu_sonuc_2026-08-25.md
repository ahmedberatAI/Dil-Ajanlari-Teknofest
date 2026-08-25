# Tesis kuralı enjeksiyonu — ölçüldü ve REDDEDİLDİ (saf eşik düşürme)

Tarih: **2026-08-25** · Ön kayıt: `docs/on_kayit_kural_enjeksiyonu_2026-08-25.md`
Arşiv: `benchmark/results/eval_20260825_144105.json` (197 klip)
Taban: `benchmark/results/eval_20260825_114341.json`
Puanlayıcı: `benchmark/kural_enjeksiyonu.py`

## 1. Hüküm

| kapı | eşik | ölçülen | sonuç |
|---|---|---|---|
| **P** `Safe_Walkway_Violation` isg_match | ≥ 0,50 | **0,440** | KALDI |
| **A** yaya yolu çift doğruluğu | ≥ 0,80 | **0,375** (TP11 FP16 FN14 TN7) | KALDI |
| **B** bulaşma (üç sevk kuralı) | düşüş ≤ 0,05 | **0,000 · 0,000 · 0,000** | GEÇTİ |
| **C** normal klipte acil müdahale | ≤ 0,15 | **0,204** (taban 0,082) | KALDI |

**RET.** Ön kayıt §3: dördü birden sağlanmazsa RET.

## 2. Kolun cazip görünen yüzü

`isg_match` (4 sınıf) **0,667 → 0,808** çıkıyor. Özetler artık ihlali gerçekten
tarif ediyor:

> *"bir personel sarı güvenlik çizgilerini ve bariyerleri aşarak makine
> çalışma alanına girmiştir"*
>
> *"personel belirlenen güvenli yürüyüş yolu yerine makine sahası yakınındaki
> serbest alanda dolaşmaktadır"*

Bu tesadüf değil: **`facility_rules` bugüne kadar bütün koşumlarda BOŞTU.**
Model, "işaretli yürüme yolunun dışına çıkmak ihlaldir" kuralını hiç
bilmiyordu. Taban koşumda yaya yolu kliplerinin özetlerinde 25 klipte
`yol` sözcüğü **sıfır**, `makine` **14** kez geçiyordu.

## 3. Ama kazanç DEJENERE — dört sınıfta birden ölçüldü

Üretilen metnin (olaylar + özet) sınıf kalıplarıyla eşleşmesi:

| sınıf | recall | sahte alarm | MCC |
|---|---|---|---|
| `Safe_Walkway_Violation` | 0,000 → **0,440** | 0,000 → **0,696** | +0,000 → **−0,257** |
| `Unauthorized_Intervention` | 0,760 → 0,880 | 0,080 → **0,440** | +0,689 → +0,464 |
| `Opened_Panel_Cover` | 0,958 → 0,958 | 0,000 → 0,120 | +0,960 → +0,840 |
| `Carrying_Overload_with_Forklift` | 0,960 → 0,960 | 0,080 → **0,680** | +0,881 → +0,364 |

Desen kusursuz nettir: **recall her yerde artıyor ya da sabit, sahte alarm her
yerde artıyor, MCC her yerde düşüyor.**

Yaya yolunda MCC **negatife** iniyor (−0,257): model **normal** yaya
kliplerinde (0,696) ihlal kliplerinden (0,440) **daha sık** ihlal diyor.

Operasyonel maliyeti de aynı yönde:

| | taban | kural açık |
|---|---|---|
| normal klipte olay üretilen | 0,541 | **0,918** |
| normal klipte acil müdahale | 0,082 | **0,204** |

## 4. D33'ün BAĞIMSIZ REPLİKASYONU

`facility_rules` daha önce A/B edilmişti (**D33, 2026-08-16**): recall +19,
adlandırma +14, ama **MCC 0,069 → 0,071 (değişmedi)** ve normal FP %22 → %40.
O günün yorumu: *"kazanç eşik düşürme, yetenek değil"*.

O ölçüm **gözlem düzleminden önce** yapılmıştı ve sistemin İSG ayrımı şans
düzeyindeydi. Bugün üç sınıf +0,881 ile +0,960 arasında deterministik
kapsanıyor — **tamamen farklı bir yapılandırma** — ve aynı sonuç çıkıyor.
Dokuz gün arayla, farklı mimariyle, aynı bulgu.

## 5. Kapı B — mimari için ÖNEMLİ POZİTİF

Üç sevk kuralının karışıklık matrisi **birebir** korundu:

    Carrying_Overload_with_Forklift  TP24 FP2 FN1 TN23  +0,881   düşüş 0,000
    Opened_Panel_Cover               TP23 FP0 FN1 TN25  +0,960   düşüş 0,000
    Unauthorized_Intervention        TP19 FP2 FN6 TN23  +0,689   düşüş 0,000

Anlatı düzlemi tamamen taşarken deterministik düzlem **hiç etkilenmedi**.
İki düzlemin birbirinden yalıtık olduğu böylece deneyle gösterildi — bu,
"model ölçer, kural hükmeder" ayrımının sadece bir tasarım iddiası değil
**ölçülmüş bir özellik** olduğunun kanıtıdır.

## 6. `policy_gate` neden bu taşmayı süzemez

Akla gelen doğal devam, kural enjeksiyonuyla üretilen adayları
`facility_policy` + `policy_gate` ile ayıklamaktı. **Koşum yapılmadan, kod
incelemesiyle elendi:** `policy_gate` önem derecesini **TEK YÖNLÜ yükseltir,
asla düşürmez** (`graph.py:1512`, `policy.py:458`). Olay üretmez ve olay
bastırmaz. Tasarım gereği bu işi yapamaz.

## 7. Sınıfın durumu — on iki mekanizma

| # | mekanizma | sonuç |
|---|---|---|
| 1-9 | VLM ilişkisel/ikili soru varyasyonları (ROI, fps, eşik) | RET |
| 10 | VLM yerel nitelik sorusu (ayak altındaki zemin) | RET — altı sınıfta özdeş dağılım |
| 10b | çapraz ön koşul (`on_azami=0`) | RET — iki kapı asla birlikte geçmiyor |
| 11 | tespit-tabanlı geofence (CPU + renk maskesi) | RET — çerçevenin yanıldığı yerde 0,462 |
| 12 | tesis kuralı enjeksiyonu | RET — saf eşik düşürme, MCC −0,257 |
| 13 | `policy_gate` ile ayıklama | elendi (tasarım: bastıramaz) |

## 8. Sonuç

`isg_match`'i bu veride yükseltmenin bulunabilen **her** yolu, kuralları daha
geniş ateşletmekten geçiyor. Dört bağımsız ölçüm aynı yere çıkıyor:

1. Yaya çiftinde etiket, kişiler silinmiş arka plandan **%72,9** doğrulukla
   tahmin edilebiliyor — hiçbir içerik sinyali bunu aşmıyor.
2. Yerel nitelik sorusu altı sınıfta **özdeş** cevap dağılımı veriyor.
3. Geofence, çerçevenin yanıldığı kliplerde **şanstan düşük** (0,462).
4. Kural enjeksiyonu recall'u artırırken sahte alarmı **dört sınıfta birden**
   artırıyor ve MCC'yi her yerde düşürüyor.

**Sevk edilen yapılandırma değişmiyor.** `isg_match` iki sayıyla
raporlanmaya devam edecek: **0,667** (dört sınıf) ve **0,892** (gözlem
düzleminin kapsadığı üç sınıf).
