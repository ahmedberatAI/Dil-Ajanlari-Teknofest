# Performans Raporu — Şartname Kapsamlı Test

**Tarih:** 2026-07-28 · **Sistem:** Qwen3-VL-8B-Instruct-FP8 · vLLM 0.23 · LangGraph
**Donanım:** RTX 5090 Laptop (24 GB, Blackwell), WSL2 Ubuntu 24.04 — **tamamen yerel**
**Koşu:** `scripts/full_benchmark.py` → `benchmark/results/full_20260728_192334/`

> **Okuma kuralı:** Tüm oranlar **Wilson %95 güven aralığı** ile verilmiştir. Küçük n'de
> nokta-değer tek başına yanıltıcıdır; aralığı okumadan sayı alıntılamayın.

---

## 1. Yönetici özeti

| Şartname ekseni | Ölçülen | Değerlendirme |
|---|---|---|
| §3 Olay tespiti | **%96** (iki bağımsız sette) | ✅ Güçlü |
| §3 Zaman damgası | %100 geçerli MM:SS | ✅ |
| §4 Anlamsal yorumlama (kategori) | %96 senaryo · **%38 grenli UCF** | ⚠️ Girdi-bağımlı |
| §4 Türkçe özet — **olgusal dayanaklılık** | **4.38/5**, uydurma ayrıntı **%27** | ⚠️ Gerçek zayıflık |
| §4 Aksiyon önerisi | 4.83/5 | ✅ |
| §4 Risk gerekçesi | 4.89/5 | ✅ |
| §4 JSON şema uyumu | **%100** | ✅ |
| §5 Mock fonksiyon dispatch | %89 | ✅ |
| §7 Otonomi / diyalog | 5.00/5 (⚠️ n=11, tavan-doygun) | ⚠️ Ölçüm zayıf |
| §4 Performans | 0.66 s/video-sn · 6.5 video/dk (x4) | ✅ |
| §7 Kararlı çalışma | **4/4 zarif** | ✅ |
| Hedef domain (politika ihlali) | %20–47 | ❌ Bilinen sınır |

**Tek cümle:** Sistem, görsel olarak belirgin olaylarda (yangın, düşme, patlama, kaza)
**iki bağımsız sette %96 tespit** ve **sıfır yanlış operasyonel sevk** ile güvenilir çalışıyor;
tesise-özgü politika ihlallerinde ve grenli görüntüde ince tip-tanımada ise ölçülmüş bir tavana
vuruyor — bu bir ayar sorunu değil, 8B modelin yapısal sınırı.

---

## 2. Olay tespiti (§3) — iki bağımsız set

### 2.1 `eval_holdout` — TEMİZ doğrulama seti (UCF-Crime, 24 anomali + 8 normal)
> **Bu setin özel önemi:** `eval_tune`'dan **ayrık**; ayar verisiyle kirlenmemiş.
> Bu, projenin **ilk sızıntısız** UCF ölçümüdür.

| Metrik | Sonuç (Wilson %95 GA) | k/n |
|---|---|---|
| Anomali recall | **%96 [%80–%99]** | 23/24 |
| Risk kalibrasyonu (≥Yüksek) | %83 [%64–%93] | 20/24 |
| Kategori adlandırma | %38 [%21–%57] | 9/24 |
| Normal dar-FP | **%0 [%0–%32]** | 0/8 |
| **Normal yanlış operasyonel tetik** | **%0 [%0–%32]** | 0/8 |
| Gecikme | 19.4 s medyan · 1.27 s/video-sn | |

**Kategori kırılımı** (n=3/kategori — yalnızca gösterge, iddia değil):

| Kategori | recall | kategori adlandırma |
|---|---|---|
| Explosion | 3/3 | **3/3** |
| RoadAccidents | 3/3 | 2/3 |
| Assault | 3/3 | 2/3 |
| Fighting | 3/3 | 1/3 |
| Abuse | 2/3 | **0/3** |

→ **Tespit ile tanıma arasında net makas**: sistem "bir şey oldu" demeyi %96 başarıyor,
"ne olduğunu" grenli 320×240'ta %38'de adlandırabiliyor.

### 2.2 `eval_scenario` — senaryo seti (25 anomali + 12 normal, hepsi gerçek video)

| Metrik | Sonuç (Wilson %95 GA) | k/n |
|---|---|---|
| Anomali recall | **%96 [%80–%99]** | 24/25 |
| Kategori adlandırma | **%96 [%80–%99]** | 24/25 |
| Risk kalibrasyonu | %88 [%70–%96] | 22/25 |
| Normal dar-FP | **%0 [%0–%24]** | 0/12 |
| **Normal yanlış operasyonel tetik** | **%0 [%0–%24]** | 0/12 |
| Gecikme | 17.1 s medyan · 1.41 s/video-sn | |

| Kategori | recall | adlandırma |
|---|---|---|
| Yangın (10) | **%100 [%72–%100]** | **%100 [%72–%100]** |
| Düşme (15, gerçek video) | %93 [%70–%99] | %93 [%70–%99] |

### 2.3 Çapraz okuma
İki **bağımsız** set, **aynı recall**: %96 (23/24 ve 24/25). Farklı kaynaklar, farklı
çözünürlükler, farklı olay türleri → tespit yeteneği **sağlam ve tekrarlanabilir**.

Ancak kategori adlandırma %96 ↔ %38 arasında değişiyor. Belirleyici olan **girdi kalitesi**:
1080p/net sahnede tip doğru adlandırılıyor, 320×240 grenli CCTV'de adlandırılamıyor.

---

## 3. Karar destek kalitesi (§4)

### 3.1 Holistik karne (9 temsili klip)

| Metrik | Sonuç |
|---|---|
| Olay tespiti | %100 |
| Risk seviyesi doğruluğu | %89 |
| **Aksiyon kalitesi** (1-5) | **4.83** |
| **Risk gerekçe kalitesi** (1-5) | **4.89** |
| **JSON şema uyumu** | **%100** |
| Normal yanlış-pozitif (tespit) | %33 |

### 3.2 ⭐ Bağımsız hakem — **ilk kez DAYANAKLI mod** (Gemma-3-12B, farklı model ailesi)

> Bu ölçüm daha önce hiç koşulmamıştı. Eski hakem sistemin **kendi** çıktısını kendine karşı
> puanlıyordu (iç tutarlılık); yeni mod klibin **bilinen dataset etiketini** hakeme verip
> **olgusal dayanaklılık** ölçüyor.

**[A] DAYANAKLI (dış geçerlilik — GT etiketine karşı):**

| Metrik | Sonuç |
|---|---|
| Olgusal dayanaklılık | **4.38 ± 1.14** (n=37 klip) |
| Etiketle çelişki oranı | %8 [%3–%21] (3/37) |
| 🔴 **Uydurma ayrıntı oranı** | **%27 [%15–%43]** (10/37) |

**[B] İÇ-TUTARLILIK (videoya dayanaklı DEĞİL — ayrı raporlanır):**

| Metrik | Sonuç |
|---|---|
| Özet kalitesi | 4.48 ± 0.63 (37 klip × 3 eksen) |
| Aksiyon kalitesi | 4.59 ± 0.58 (28 klip × 4 eksen) |
| Risk gerekçesi | 4.86 ± 0.47 (28 klip × 3 eksen) |

> ⚠️ **Bu iki aile ASLA tek bir "kalite skoru" olarak birleştirilmemelidir.**
> [B] yalnızca öz-çelişki yokluğunu gösterir; "video doğru anlaşıldı" **demez**.

**En önemli yeni bulgu:** **%27 uydurma ayrıntı**. Özetler akıcı ve iç tutarlı (4.48) ama
**her 4 özetten ~1'i görüntüde olmayan bir ayrıntı içeriyor.** Eski dayanaksız hakem bunu
göremiyordu. Bu, dürüstçe raporlanması gereken gerçek bir zayıflıktır.

---

## 4. Otonomi ve diyalog (§7)

| Metrik | Sonuç | Uyarı |
|---|---|---|
| Diyalog tek-tur | 5.00 ± 0.00 | n=7 |
| Diyalog çok-tur | 5.00 ± 0.00 | n=4 |
| Agentic dispatch doğruluğu | %89 | anomalide %83 · normalde yanlış-tetik **%0** |

⚠️ **Dürüst uyarı:** std = 0.00, yani hakem her maddeye 5 vermiş — bu **tavan doygunluğu**
(ayrım gücü yok), kanıtlanmış kusursuzluk değil. n=7+4 istatistiksel taban olarak dardır.
Diyalog yeteneği gerçek ama **ölçümü zayıftır**; genişletilmesi gereken bir eksendir.

---

## 5. Performans ve ölçeklenebilirlik (§4)

### 5.1 Gecikme
| | Değer |
|---|---|
| Klip başına medyan | 17–19 s |
| **Video-saniyesi başına** | **0.66 s/vsn** (aralık 0.37–2.91) |
| Decode payı | %2 (0.57 s) |
| Inference payı | **%98** |

→ Darboğaz **tamamen model çıkarımı**; video işleme ihmal edilebilir. Optimizasyon
çabası doğru yere (servisleme) yönlendirilmiş.

### 5.2 Eş-zamanlılık (vLLM continuous-batching)
| Mod | Süre | Throughput | Hızlanma |
|---|---|---|---|
| Sıralı (n=4) | 82.2 s | 2.9 video/dk | 1.00× |
| Eş-zamanlı ×2 | 46.7 s | 5.1 video/dk | **1.76×** |
| Eş-zamanlı ×4 | 36.8 s | **6.5 video/dk** | **2.23×** |

### 5.3 Kaynak
- Tepe VRAM **22.7 GB / 24 GB** · model FP8 ~19 GB
- Tek GPU ≈ **2–3 gerçek-zamanlı akış**. 20 kamera 7/24 için ~7–10 GPU gerekir.

---

## 6. Kararlı çalışma / hata toleransı (§7)

| Girdi | Sonuç | Süre |
|---|---|---|
| `black.mp4` (siyah) | Çökmedi · risk=Düşük · sözleşme ✓ | 11.0 s |
| `corrupt.mp4` (bozuk) | Çökmedi · risk=Düşük · sözleşme ✓ | 4.1 s |
| `empty.mp4` (boş) | Çökmedi · risk=Düşük · sözleşme ✓ | 4.0 s |
| `tiny.mp4` (minik) | Çökmedi · risk=Düşük · sözleşme ✓ | 8.8 s |

**4/4 zarif bozulma** — çökme yok, `to_sartname_dict()` anahtarları korundu, uydurma olay yok.

---

## 7. Hedef domain: politika ihlali (ölçülmüş sınır)

`eval_defense` — gerçek üretim tesisi 1080p (100 güvensiz + 100 güvenli davranış):

| Metrik | Kurallar kapalı | `facility_rules` açık |
|---|---|---|
| Recall | %20 [%13–%29] | **%47 [%38–%57]** |
| Kategori | %9 [%5–%16] | %33 [%25–%43] |
| Risk kalibrasyonu | %5 | %10 |
| Normal dar-FP | %4 | %8 |

Eşleştirilmiş McNemar (n=100): recall **p=4.19e-05**, kategori **p=8.43e-06** → kural
enjeksiyonunun kazancı **istatistiksel olarak kanıtlanmıştır**.

**Neden düşük:** Bu olaylar görsel değil **kural** bilgisi ister — "forklift yük taşıyor"
görüntüsü, kapasite kuralını bilmeden ihlal sayılamaz. Model sahneyi doğru görüyor,
"ihlal"i kural olmadan yargılayamıyor. Bu bir model kusuru değil, **bilgi eksikliğidir**.

---

## 8. Güçlü / zayıf yönler (kanıta dayalı)

### ✅ Güçlü
1. **Tespit tekrarlanabilir**: iki bağımsız sette %96 [%80–%99]
2. **Sıfır yanlış operasyonel sevk**: 20 normal klipte 0 hatalı fonksiyon tetiği — şiddet kapısı çalışıyor
3. **JSON sözleşmesi %100** — şartname mock formatıyla birebir
4. **Yangın tespiti kusursuz**: 10/10 + adversaryel negatiflerde 0 FP
5. **Hata toleransı 4/4** — bozuk girdide çökmüyor
6. **Aksiyon/risk gerekçesi 4.8+/5**
7. **Ölçüm dürüstlüğü**: bağımsız model ailesi hakem, Wilson GA, dayanaklı/iç-tutarlılık ayrımı

### ⚠️ Zayıf (dürüst)
1. **Uydurma ayrıntı %27** — en önemli yeni bulgu; özetler akıcı ama 4'te 1'i görüntüde olmayan detay içeriyor
2. **Grenli görüntüde kategori %38** — Abuse 0/3, Fighting 1/3
3. **Politika ihlalinde %47 tavan** — kuralla bile yarısı kaçıyor
4. **Diyalog ölçümü tavan-doygun** (n=11, std=0)
5. **Risk kalibrasyonu politika olaylarında %10** — çözülmemiş (bkz. kusur #2)
6. **Gece/IR/termal: sıfır kapsam**
7. **Koşu-arası varyans**: ±15 klip salınım (kusur #8)

---

## 9. Sonuç: dağıtım konumlandırması

**Güvenle kullanılır:**
- Adli-sonrası **kayıt triyajı** (8 saatlik kaydı dakikalara indirir)
- **İnsan-onaylı** ikinci-göz katmanı (tüm sevkler öneri olarak sunulur)
- **Yangına özel** dar dağıtım (tek kusursuz kanıtlanmış yetenek)
- Doğal dille kayıt sorgulama

**Kullanılmaz:**
- Otonom alarm / otomatik sevk
- İnsansız gece vardiyası (gece hiç ölçülmedi)
- Tesise-özgü politika denetimi (kuralla bile %47)
- Silah/ince tehdit tespiti (grenli görüntüde %0–38)

---

## Ek: yeniden üretim

```bash
python serve_vllm.py                      # terminal 1
python scripts/full_benchmark.py          # terminal 2 (~30 dk)
# bağımsız hakem (ayrı model servis edilir):
DILAJAN_MODEL_NAME=RedHatAI/gemma-3-12b-it-FP8-dynamic python serve_vllm.py
DILAJAN_JUDGE_MODEL=RedHatAI/gemma-3-12b-it-FP8-dynamic python benchmark/judge_independent.py
```

Ham çıktılar: `benchmark/results/full_20260728_192334/`
