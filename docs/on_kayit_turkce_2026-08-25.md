# ÖN KAYIT — Türkçe üretim kalitesi

Tarih: **2026-08-25**, ölçüm düzeneği kurulmadan **ÖNCE**. Dal: `d34-isg-veri-kkd`

## 0. Neden

Bu bir **Türkçe** doğal dil işleme yarışması ve şartname Türkçe üretimi
açıkça istiyor:

> *"Sistem tarafından üretilen çıktılar, açık, anlaşılır ve bağlama uygun
> Türkçe ile ifade edilmelidir. Özetler: gereksiz detaydan arındırılmış,
> operatörün hızlı karar almasını destekleyecek şekilde yapılandırılmış,
> anlam bütünlüğü korunmuş."*

Puanlamanın %20'si "Otonomi ve Zeka" ve içinde açıkça *"diyalogun doğal ve
insansı bir akışta ilerlemesi"* var.

**Bugüne kadar Türkçe kalitesini ölçen hiçbir şey yoktu** — metrik yok,
test yok, rubrik yok. Tek dolaylı sinyal `isg_match` ve o, şablon metne
kalıp eşlemesi; model nesrini hiç ölçmüyor.

## 1. Sonda bulguları (hüküm DEĞİL, kolların gerekçesi)

6 klipte 2×2 sonda (model × prompt dili) yapıldı. Bunlar **ön kayıtlı ölçüm
değildir**; kolların neden kurulduğunu gösterirler.

**(a) Küçük model MANTIK HATASI yapıyor.** Forklift özetinde tekrar tekrar:

> `llm-fast`: *"Tespit edilen kasa sayısı, güvenli yük sınırı olan 3 kasanın
> **altı değerindedir**. Bu durum, yükün **aşırı** olduğu ... anlamına
> gelmektedir."* → kendi içinde çelişkili
>
> `llm-large`: *"Bu durum, belirtilen güvenli yük **sınırının aşıldığını**
> göstermektedir."* → doğru

**(b) Prompt'un kendi Türkçesi bozuk.** `dilajan/prompts.py` içinde **132**
açık örnek (`hizli`, `yalnizca`, `almasini`, `olmalidir`…) — ama aynı dosyada
**323 doğru `ı`** var, yani tutarsızlık, bilinçli tasarım değil.
(`gozlem.py` tamamen ASCII: 0 doğru `ı` — o **ölçülmüş ve bilinçli** bir
karar, dokunulmayacak.)

Prompt düzeltilince kalıplaşma göstergesi **0,33 → 0,17** düştü (her iki
modelde de).

**(c) Gecikme maliyeti SIFIR.** Özet çağrısı: `llm-fast` 2,20 sn ·
`llm-large` **2,21 sn** (n=6). MoE olduğu için 3B→10B aktif geçişi kısa
metin üretiminde fark yaratmıyor.

## 2. ÖLÇÜM DÜZENEĞİ — önce bu kurulacak

Ölçülmeyen şey değiştirilmez. Düzenek:

**Rubrik (5 madde, 1-5 ölçek), şartnamenin dilinden türetilmiş:**

| # | madde | ne sorar |
|---|---|---|
| R1 | **Doğruluk** | Özet, verilen olaylarla çelişiyor mu? Uydurma var mı? |
| R2 | **Karar desteği** | Operatör bunu okuyup hızlı karar alabilir mi? |
| R3 | **Dil doğruluğu** | Ek/çekim/imla/`ı`-`i` hataları var mı? |
| R4 | **Terminoloji** | İSG terimleri doğru ve tutarlı mı? |
| R5 | **Akıcılık ve özlük** | Gereksiz dolgu, kalıplaşma, devrik yığılması var mı? |

**Hakem tasarımı — yanlılık panzehirleri ZORUNLU:**
- **Kendi-çıktı yanlılığı:** hakem, değerlendirdiği çıktıyı üreten modelden
  **farklı** olacak. Aday `llm-fast` ise hakem `llm-large`, aday `llm-large`
  ise hakem yine `llm-large` olamaz → **hakem her iki kolda da aynı ve
  adaylardan bağımsız olmalı**. Elimizdeki üçüncü seçenek `vlm`
  (Qwen3-VL-32B, metin de kabul eder). Hakem = `vlm`.
- **Konum yanlılığı:** ikili karşılaştırmada A/B sırası klip başına
  **rastgele çevrilir** (tohumlu) ve sonuç sıraya göre çözülür.
- **Uzunluk yanlılığı:** rubrikte uzunluk ödüllendirilmez; R5 açıkça
  "gereksiz dolgu" cezalandırır. Ayrıca ortalama karakter sayısı **ayrıca**
  raporlanır.
- **Tekrarlanabilirlik:** `temperature=0`, aynı tohum, hakem çağrısı
  `structured_outputs.choice` ile **kapalı cevap uzayına** zorlanır.

**Düzeneğin KENDİSİ doğrulanacak:** 10 klipte hakem **iki kez** çalıştırılır
(A/B sırası çevrilmiş olarak). Hakem aynı çifte zıt hüküm veriyorsa
**tutarsızlık oranı** raporlanır; **> %30 ise düzenek güvenilmez ilan edilir
ve hiçbir kol hükme bağlanmaz.**

**Örneklem:** tohumlu (seed=7) **40 klip**, olay üretilenlerden.
**İstatistik:** eşleşmiş (aynı klip, aynı olaylar) → **McNemar exact** +
Wilson aralıkları.

## 3. KOLLAR ve ÖN KAYITLI ÖLÇÜTLER

### T1 — Özet modeli `llm-fast` → `llm-large` (BİRİNCİL)
- **KABUL:** ikili karşılaştırmada `llm-large` **≥ %65** klipte tercih
  edilecek (40 klipte ≥26) **ve** R1 (doğruluk) ortalaması düşmeyecek.
- **BEDEL KAPISI:** özet çağrısı gecikmesi **≤ 2×** artacak.
- Aksi hâlde **RET**.

### T2 — Anlatı promptlarının Türkçesi düzeltilecek (BİRİNCİL)
Yalnızca `dilajan/prompts.py`; `ı`-`i` ve benzeri imla. **Anlam
değiştirilmeyecek** — talimatların içeriği aynı kalacak.
- **KABUL:** ikili karşılaştırmada düzeltilmiş **≥ %60** tercih edilecek
  **veya** kalıplaşma göstergesi **≥ %30** düşecek; **ve** R1 düşmeyecek.
- Aksi hâlde **RET**.

### T3 — Kural şablonlarının Türkçesi (İKİNCİL, RİSKLİ)
*"güvenli yük sınırı 3 kasanın altıdır"* ifadesi modeli şaşırtıyor.
- **ZORUNLU KAPI:** `tests/test_sablon_kalip.py` geçmeye devam edecek
  (şablonlar `isg_any_match` kalıplarıyla eşleşmezse `isg_match` çöker).
- **KABUL:** üç sevk matrisi **birebir** korunacak **ve** özet doğruluğu
  (R1) yükselecek. Matris saparsa **anında RET**.

## 4. ZORUNLU KORUMA — tespit metrikleri

Bu kolların **hiçbiri** İSG tespit skorlarını değiştirmemeli. Her kol için:

> Üç sevk çiftinin karışıklık matrisi (`TP24/FP2/FN1/TN23`,
> `TP23/FP0/FN1/TN25`, `TP19/FP2/FN6/TN23`) **birebir** korunacak.
> Saparsa kol **RET**.

Gerekçe: T1 ve T2 yalnızca **anlatı düzlemini** değiştirir; gözlem düzlemi
ve kural motoru dokunulmaz. Bu kapı o iddiayı **doğrular**.

## 5. ÖN-RET KAPILARI

| # | kapı |
|---|---|
| a | **HAKEM GÜVENİLMEZ** — tutarsızlık > %30 → hiçbir kol hükme bağlanmaz |
| b | **DEJENERELİK** — bir kol kliplerin ≥ %95'inde tercih edilirse hakem yanlı olabilir; el ile 5 örnek denetlenir |
| c | **SÖZLEŞME** — çıktı hâlâ TAM 4 anahtarlı olmalı (K1). Bozulursa anında RET |

## 6. Ne olursa ne yapılacak

| sonuç | eylem |
|---|---|
| T1 geçer | özet modeli `llm-large`'a alınır (gecikme bedeli sıfır ölçüldü) |
| T2 geçer | prompt Türkçesi düzeltilir |
| T3 geçer | şablonlar düzeltilir, kalıp testi ile korunur |
| hakem güvenilmez | düzenek raporlanır, **hiçbir değişiklik yapılmaz** |

Hiçbir eski skor silinmeyecek. Sonuç ne olursa olsun yazılacak.
