# DilAjanları — Kapsamlı Performans Raporu

Şartname (2026 TEKNOFEST TYDA, 3. Senaryo) gereksinimlerine **her boyuttan** uyum ve **ölçülen** başarı.
Model: **Qwen3-VL-8B-Instruct-FP8** (yerel, vLLM, RTX 5090 Laptop 24 GB).
Değerlendirme: recall / yanlış-pozitif / risk-kalibrasyon / kategori metrikleri **objektif**
(veri seti etiketine karşı); kalite metrikleri **bağımsız** Gemma-3-12B hakemiyle (döngüsel değil).

> **Bu belgedeki her sayı [`docs/olcum_durustlugu.md`](olcum_durustlugu.md) ile hizalıdır.**
> Çelişki görürseniz o belge geçerlidir.
>
> **Raporlama kuralı:** oranlar `k/n` + Wilson %95 güven aralığı ile verilir; n ≤ 48'de ondalıklı
> yüzde yazılmaz; "%0" mutlak ifadesi kullanılmaz. Hesap: `benchmark/stats_utils.py`.

---

## 0. Test kapsamı — ve kapsamın dürüst sınırı

| Set | Benzersiz klip | Özellik | Bilinen kusur |
|---|---|---|---|
| Senaryo (Yangın 10 + Düşme 15 + Normal 12) | 37 | senaryo-uyumlu, net olaylar | düşme klipleri `falls_real`+`falls_surveillance` ile **birebir aynı** (bağımsız değil); **kompozisyon değişti, yeniden ölçülecek** |
| UCF büyük `eval_big` (48 anomali + 16 normal) | 63 benzersiz / 64 dosya | grenli 320×240, dayanıklılık stresi | 2 normal aynı dosya; anomalilerin %100'ü 320×240 |
| → ayrık bölünme `eval_tune` / `eval_holdout` | 31 / 32 | ayarlama ve doğrulama ayrımı | **holdout ölçümü henüz koşulmadı** |
| UCF dengeli `eval` (24 + 8) | 31 | eski set | **`eval_big`'in tam alt kümesi** — bağımsız değil |
| GMDCSA gerçek düşme | 15 | gerçek 720p60, frontal ev-kamerası | gözetim açısı değil |
| URFD overhead düşme | 6 | gerçek **tavan/gözetim açısı** 480p | düşmeler simüle |
| Araç kazası (RoadAccidents) | 9 | gerçek CCTV | 6'sı `eval_big` ile örtüşüyor |
| Endüstriyel havuz (Eskişehir) | 40 | gerçek 1080p fabrika CCTV, 8 sınıf | ham havuz; eşleme `industrial/CLASSES.md`'de doğrulandı |
| **Hedef-domain `eval_defense`** (20 anomali + 20 normal) | 40 | **1080p gerçek tesis, domain-içi POZİTİF** | **ölçüm henüz koşulmadı** |
| Adversaryel yangın-renkli negatif | 9 | FP stres testi | — |
| Diyalog (tek + çok-tur) | 11 senaryo | otonomi/robustluk | tek değerlendirici |
| **Toplamda ölçüme giren** | **140 benzersiz klip / 44.0 dk** | 320×240 → 1080p; frontal/overhead/yol/tesis | tümü **gündüz görünür-ışık** |

**Kapsam beyanı düzeltmesi.** Bu tablo daha önce "~130+ klip" olarak toplanıyordu; `data/` altında
412 dosya var ama yalnızca **214'ü benzersiz** (MD5) ve ölçüme girebilecek olan **140**'ı. Setler arası
örtüşme (aynı klibin birden fazla sette bulunması) sayımı şişiriyordu. **Bu 140'ın 40'ı
(`eval_defense`) henüz hiç ölçülmedi.** Ayrıntı ve yeniden-üretim komutu:
[`veri_kaynaklari.md`](veri_kaynaklari.md) §1.

---

## 1. İŞLEVSELLİK (Şartname %35)

### 1.1 Olay tespiti (anomali recall) — objektif

**Tanım uyarısı:** buradaki recall **gevşektir** — bir anomali klibinde model **≥1 herhangi bir
olay** ürettiyse "yakaladı" sayılır; olay tipinin doğru olması gerekmez. Katı tanım §1.2'dedir.

> ⚠️ **Senaryo satırları eski kompozisyona aittir.** `eval_scenario/Fall`'ın 8 donmuş-PNG klibi
> gerçek videolarla değiştirildi ve set 18 → **25 anomali** oldu; yeni sette ölçüm henüz koşulmadı.

| Set | Anomali klip | Sonuç | Wilson %95 GA |
|---|---|---|---|
| Senaryo (yangın+düşme) — *eski kompozisyon* | 18 | **18/18** (çoğu kayıtlı koşu) | [%82, %100] |
| Senaryo — en kötü kayıtlı koşu | 18 | 17/18 | [%74, %99] |
| Yangın alt-kümesi | 10 | 10/10 | [%72, %100] |
| UCF `eval_big` — en iyi koşu | 48 | **44/48** | [%80, %97] |
| UCF `eval_big` — diğer 2 kayıtlı koşu | 48 | 42/48 | [%75, %94] |
| GMDCSA gerçek düşme | 9 | 8/9 | [%56, %98] |
| URFD overhead düşme | 6 | 6/6 | [%61, %100] |
| Araç kazası | 9 | 8/9 – 9/9 | [%56, %98] – [%70, %100] |

**Koşu-arası varyans dürüstçe:** senaryo setinde her koşu ya 18/18 ya 17/18 çıkar — yani
**tek bir klip** ortalamayı %100'den %94'e taşır. `eval_big`'de üç kayıtlı koşu 44/48, 42/48,
42/48'dir; **manşetimiz en iyi koşu değil, aralıktır.** Eski belgelerdeki "%99 ± 2" / "%92" gibi
tek-değer ifadeleri bu yüzden `k/n + GA` biçimine çevrilmiştir.

### 1.2 Üç seviyeli recall — mükerrer-arınmış (dürüst manşet)

`scripts/strict_recall.py` + `scripts/action_recall.py`, kayıtlı cevaplardan, GPU'suz.

| Seviye | Ne ölçer | **Kanonik (51 bağımsız klip)** | Wilson %95 GA |
|---|---|---|---|
| **TESPİT** | bir şey oldu mu? | **49/51** | [%87, %99] |
| **AKSİYON** | doğru güvenlik-tepki sınıfı mı? | **36/51** | [%57, %81] |
| **TANIMA** | UCF alt-etiketi birebir doğru mu? | **22/51** | [%31, %57] |

> **Düzeltme:** bu ölçüm daha önce "81 suç klibi" üzerinden %96 / %73 / %46 olarak raporlanmıştı.
> `data/eval`, `data/eval_big`'in alt kümesi olduğu için **27 klip iki kez sayılmıştı**; gerçek
> bağımsız klip sayısı 51'dir. Tekilleştirilmiş değerler yukarıdadır.

**Kategori kırılımı — gösterge amaçlı, iddia DEĞİL** (n = 6/kategori → GA ≈ [%19, %81]):
RoadAccidents 7/9 · Abuse/Assault/Burglary/Explosion/Fighting 3/6 · Shooting 0/6 · Vandalism 0/6.
Bu genişlikte aralıklardan kategori sıralaması çıkarılamaz; gizlemiyoruz ama iddiaya dönüştürmüyoruz.

**Dürüst yorum:** sistem güçlü bir **ikili anomali-tespitçisi**, makul bir **tepki-sınıflandırıcısı**,
zayıf bir **ince suç-tipi sınıflandırıcısıdır**. Üçüncüsü bir **girdi-bilgi tavanıdır** (320×240'ta
tabanca < 20 px, DORI tanıma eşiğinin altında); 5 ayrı kaldıraç ölçülüp elendi → `iyilestirmeler.md` §15–§16.

### 1.3 Anlamsal yorumlama + çıktı kalitesi (bağımsız Gemma hakem, 1–5)

Kaynak artefakt: `benchmark/results/independent_scores.json`.

| Metrik | Kanonik değer | Bağımsız birim | Not |
|---|---|---|---|
| Özet kalitesi | **4.62 ± 0.53** | 30 klip × 3 eksen | "n=90" bağımsız gözlem değildir |
| Aksiyon kalitesi | **4.74 ± 0.44** | 18 klip × 4 eksen | belgelerdeki 4.66/4.69/4.71/4.83 varyantları **geri çekildi** |
| Risk gerekçe kalitesi | **5.00 ± 0.00** | 18 klip × 3 eksen | **std = 0 → tavan-doygunluğu** |
| Risk seviyesi doğruluğu | senaryo 18/18 [%82–%100] | objektif | `eval_big`'de 36/48 [%61–%86] |
| Kategori eşleşme | senaryo 18/18 [%82–%100] · `eval_big` 21/48 [%31–%58] | objektif | grenli = girdi-tavanı |
| **JSON şema uyumu** | **%100** | objektif, tüm koşularda | şema ihlali gözlenmedi |

⚠️ **Bu skorların ölçtüğü şey:** yukarıdaki rakamlar, hakeme **yalnızca metin** verilen
(sistemin kendi olay listesi + kendi özeti) bir koşudan gelir; hakem **videoyu görmemiştir**.
Dolayısıyla **iç tutarlılık** ölçerler, **videoya dayanaklılık** değil — kendinden emin bir
halüsinasyon tam puan alabilir. `judge_independent.py` bu turda üç aileye ayrıldı
([A] ground-truth'a karşı olgusal dayanaklılık, [B] iç-tutarlılık, [C] opsiyonel kare-kanıtı),
**ancak ölçüm henüz yeniden koşulmadı** — düzeltme araçtadır, rakamlarda değil.
Paketin en denetlenmemiş iddiası hâlâ budur.

### 1.4 Yanlış-pozitif (normal kliplerde) — objektif, "sıfır" demeden

| Set | Normal klip (**benzersiz**) | Gözlenen dar-FP | Wilson %95 GA |
|---|---|---|---|
| Adversaryel yangın-renkli | 9 | **0/9** | **[%0, %30]** |
| Endüstriyel 1080p | 8 | **0/8** | **[%0, %32]** |
| Senaryo normal | 12 | 0/12 (bazı koşularda 1/12) | [%0, %24] · (1/12 → [%1, %35]) |
| `eval_big` normal | **15** (16 dosya, 2'si aynı MD5) | 0/15 – 2/15 | [%0, %20] – [%4, %36] |
| `eval` normal | **7** (8 dosya, 2'si aynı MD5) | 0/7 – 1/7 | [%0, %35] |

- **Payda düzeltmesi:** `Normal_Videos_936` ve `_937` birebir aynı dosyadır (MD5 `88800dc1…`) →
  paydalar 8 ve 16 değil **7 ve 15**. Sonucu değiştirmez, ama paydayı şişiriyordu.
- **Operasyonel-FP** (dispatch kapısıyla engellenen, "Düşük" seviyeli zararsız notlar) daha
  yüksektir ve ayrı raporlanır: senaryo normalinde **4/12 [%14–%61]**, `eval_big` normalinde
  **6/16 [%18–%61]**.
- **Yanlış operasyonel-tetik (dispatch-FP):** kayıtlı koşuların çoğunda 0; en kötü kayıtlı koşuda
  `eval_big` normalinde 2/16 [%4–%36].

**Özet (İşlevsellik):** senaryo-uyumlu net olaylarda tespit tavanda (18/18), JSON şema uyumu tam,
kalite yüksek (4.62–5.00, ama §1.3 uyarısıyla). Grenli off-domain'de tespit yüksek (44/48) ama
tür-adlandırma zayıf (22/51) — girdi-tavanı, dürüstçe beyan.

---

## 2. TEKNİK / MİMARİ (Şartname %35)

| Boyut | Durum |
|---|---|
| Mimari | LangGraph ajanı, **6 düğüm + koşullu kenar**: ingest → perceive → **(koşullu) reexamine** → reason → act → finalize |
| Çok-adımlı zekâ | iki-aşamalı algı (tarif→çıkarım), öz-doğrulama (deduce-verify), spatial grounding (bbox→bölge), dedup, **dinamik dispatch-kapısı** |
| Bellek/bağlam | sohbet geçmişi + segment bağlamı; çok-turlu diyalog tutar |
| Gecikme (tam mod) | **0.86 s/video-sn** ortalama (n=6 klip; 0.44–3.75 aralığı) — kayıtlı log |
| Gecikme (hızlı mod) | ~2.5× hızlı; ölçülen sette özet/aksiyon/risk kalitesi ≈ aynı |
| Eşzamanlı throughput | ×4'te **4.2 video/dk**, prefix-caching ile 3.7'den **+13.5%**; hızlanma 1.95× |
| Kaynak | tepe VRAM ~21 GB / 24 GB (FP8 ağırlık ~19 GB) |
| Güvenilirlik | watchdog (sağlık-kontrol + otomatik restart); zarif bozulma (bozuk/boş video çökmez) |
| Hata toleransı | **altı düğümün dış gövdesi try/except** + segment-içi fail-open (§`architecture.md`) |
| Eşzamanlılık güvenliği | `act()` çağrı kayıtları modül-globali değil çağrı-yerel liste → paralel koşular karışmaz |
| Araç-çağrısı sağlamlığı | yanlış argüman adında **onar + tek kez yeniden dene**; kalıcı hatada karar-izine net UYARI |
| Ölçeklenme | vLLM continuous-batching; çok-GPU için tensor-parallel yolu (**ölçülmedi**) |
| Çalışma kipi | 2026-08-21 sonrası: yarışma tahsisli 8×H200 uzak servis. Yerel vLLM yolu korunur (`.env.yerel`); yerel GPU kod düzeyinde yasak. |
| Açık kaynak | Apache-2.0 kod + model, `requirements-lock.txt`, dokümante |

> **Geri çekilen performans iddiası:** "eşzamanlı ×4 throughput +24% (3.7→4.6 video/dk)" için
> kayıtlı log artefaktı yoktur; serving-flag turunun ek kazancı yeniden ölçülüp loglanana kadar
> iddia edilmiyor. Kanonik değer **+13.5% (3.7→4.2)**, iki log dosyasıyla doğrulanabilir.

---

## 3. OTONOMİ / ZEKÂ (Şartname %20)

| Metrik | Skor | Bağımsız birim / uyarı |
|---|---|---|
| Diyalog robustluğu (tek-tur) | **5.00 ± 0.00** | **7 senaryo** — hakem std = 0 (tavan-doygun) |
| Çok-turlu tutarlılık (bağlam taşıma) | **5.00 ± 0.00** | **4 tur** — aynı uyarı |
| Açıklayıcı-soru (belirsiz gönderme) | tam | alt-senaryo, n = 1 |
| İnisiyatif (en kritik aksiyonu öne çıkarma) | tam | alt-senaryo, n = 1 |
| Prompt-injection direnci / görev-dışı reddi | tam | alt-senaryo, n = 1 |
| Halüsinasyon direnci (bağlamda yoksa "yok") | tam | alt-senaryo, n = 1 |
| Agentic dispatch doğruluğu | **14/18** | GA [%55, %91] — anomali-tetik ve normal-temiz karışık |

⚠️ **"5.00/5" nasıl okunmalı:** hakem 11 senaryonun hiçbirinde kusur işaretlemedi ve **standart
sapma 0.00** çıktı. Bu, sistemin kusursuz olduğunu değil, **5'li ölçeğin bu görevde ayrım gücünü
kaybettiğini** (tavan-doygunluğu) gösterir. Ayrıca senaryolar tek bir değerlendirici tarafından
yazılmıştır. Doğru okuma: *"bu 11 senaryoda hakem hiçbir kusur işaretlemedi."*

**Özet (Otonomi):** niyet anlama + akıl yürütme + inisiyatif + açıklayıcı soru + injection direnci
gözlenen tüm senaryolarda başarılı; karar statik-kural değil **model-tabanlı + koşullu döngülü**.
Ancak senaryo sayısı küçüktür ve ölçek tavana dayanmıştır.

---

## 4. YENİLİKÇİLİK (Şartname %10)
- **Öz-doğrulama** (deduce-then-verify): yüksek-severity olayları odaklı yeniden kontrol; aşırı-yorumu reddeder.
- **Koşullu re-examine döngüsü:** belirsiz (Orta) olayları ajan "tekrar bakar" (adaptif otonomi, döngü muhafızlı).
- **Dinamik dispatch-kapısı:** operasyonel fonksiyonlar yalnız gerçek yüksek-riskte → alarm yorgunluğu kesilir.
- **Spatial grounding:** native bbox → 3×3 Türkçe bölge ("üst sağ" vb.).
- **Çelişki-kuralı çıkarımı:** model gövdede olay tarif edip sonda "SAPMA YOK" derse somut olayı kurtarır.
- **Bağımsız LLM-hakem ile öz-değerlendirme** (Gemma ≠ Qwen) + **kendi ölçümümüzün denetimi**
  (üç seviyeli recall, Wilson aralıkları, mükerrer-klip düzeltmesi): metodolojik dürüstlük yeniliği.
- **İki-dilli severity tabanı + dil-saflığı guard + hızlı mod + watchdog.**

---

## 5. Şartname zorunlu çıktılar — uyum

| Zorunlu | Durum | Kanıt |
|---|---|---|
| Video al + analiz | ✅ | `ingest` + `perceive` |
| Olay/kişi/risk tespiti | ✅ | recall §1.1 (18/18 senaryo; 44/48 grenli) |
| Kritik an + **zaman bilgisi** | ✅ | olay `time` + zaman pencereleri |
| Kısa Türkçe özet | ✅ | 4.62 ± 0.53 (bağımsız hakem; §1.3 uyarısıyla) |
| Operatör aksiyon önerisi | ✅ | 4.74 ± 0.44 (bağımsız hakem) |
| **Yapılandırılmış JSON** | ✅ | şema uyumu %100, ihlal gözlenmedi |
| Offline/yerel + dış servis yok | ✅ | yalnız `127.0.0.1` |
| ~Gerçek-zamana yakın servisleme | ✅ | 0.86 s/video-sn ort; hızlı modda ~2.5× |

---

## 6. Dürüst sınırlar (saklanmıyor)

Tam liste ve gerekçeler → [`olcum_durustlugu.md`](olcum_durustlugu.md) §6. Özet:

1. **Küçük örneklem** — en büyük set 48+16; tek klip %2–17 oynatır. Sıralama iddiası yapılamaz.
2. **Recall tanımı gevşek** — "≥1 herhangi olay"; katı ölçümde TANIMA 22/51'e düşer.
3. **Kalite hakemi videoyu görmüyor** — iç tutarlılık ölçüyor, dayanaklılık değil.
4. **Gece / IR / termal kapsam sıfır** — savunma dağıtımının birincil kaynağı hakkında ölçüm yok.
5. **Hedef domainde ÖLÇÜLMÜŞ pozitif yok** — veri boşluğu `data/eval_defense` (20+20, 1080p gerçek tesis)
   ile kapatıldı ama **o sette henüz ölçüm koşulmadı**; tesis-içi iddia hâlâ transfer varsayımı.
6. **Forklift devrilmesi için gerçek açık veri yok** — en yakın gerçek kanıt `eval_defense`'teki
   5 forklift aşırı-yük klibi (devrilme değil). `test_clip.mp4` kareye gömülü metinli sentetik
   karikatürdür (model orada OCR yapar) ve yetenek kanıtı değildir.
7. **Sentetik/donmuş klipler** — `eval_scenario/Fall`'ın 8 klibi hareketsiz PNG idi; **giderildi**,
   ama senaryo rakamları eski kompozisyona ait ve yeniden ölçülmeli. Yeni klipler `falls_real` +
   `falls_surveillance` ile birebir aynı → bağımsız kanıt eklemiyor.
8. **Çözünürlük–etiket confound'u** — her iki sette de tek bir 1080p **anomali** klibi yok;
   `eval_big` anomalilerinin %100'ü 320×240, normallerinin %50'si 1080p.
9. **`eval ⊂ eval_big`** — "bağımsız büyük-n doğrulaması" iddiası geri çekildi. Ayrık
   `eval_tune`/`eval_holdout` bölünmesi yapıldı; **temiz holdout ölçümü henüz koşulmadı**, mevcut
   `eval_big` rakamları ayarlama verisiyle aynı veri üzerindedir (bir miktar iyimser beklenmeli).
10. **Tek donanım / tek değerlendirici** — farklı GPU-quantization altında yeniden üretim test edilmedi.
11. **Tek-GPU** donanımsal sınır; yatay ölçek yolu belgelendi ama **ölçülmedi**.

---

## 7. Genel değerlendirme

Şartnamenin **zorunlu çıktılarının tamamı** karşılanıyor. Dört puanlama ekseninde:
**İşlevsellik** güçlü (senaryo tespiti tavanda, JSON tam, kalite yüksek), **Teknik/Mimari** güçlü
(agentic, koşullu akış, hata toleransı, eşzamanlılık güvenliği, ölçülü performans),
**Otonomi** güçlü ama ölçek tavana dayanmış (11 senaryo), **Yenilikçilik** orta-iyi
(öz-doğrulama, koşullu döngü, dispatch-kapısı, bağımsız hakem + kendi ölçümünü denetleme).

Sayılar `k/n` + güven aralığıyla, kayıtlı artefaktlara bağlı ve **kendi bulduğumuz ölçüm
kusurları düzeltilmiş** hâlde raporlanmaktadır. İddiamız "her şey mükemmel" değil,
**"neyi ne kadar ölçtüğümüzü biliyoruz ve yayınlıyoruz"**dur.
