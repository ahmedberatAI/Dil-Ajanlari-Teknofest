# ÖN KAYIT — GÖRSEL DAYANAK: "model ne yaşandığını doğru biliyor mu?"

Tarih: **2026-08-26**, koşumdan **ÖNCE**. Dal: `d34-isg-veri-kkd`

## 0. Neden

Bu soru bugüne kadar **mevcut sistem için hiç ölçülmedi.** Elimizdeki tek
"dayanaklı" koşum (`benchmark/results/independent_scores.json`) bu soruyu
yanıtlamıyor:

| kusur | ayrıntı |
|---|---|
| tarih | **2026-07-28** — gözlem düzleminden, İSG kural motorundan, tesis kilidinden ve Türkçe kollarından **önce** |
| küme | `eval_scenario` (Fall 15 · Fire 10 · Normal 12) — İSG fabrika klibi **yok** |
| dayanak | `gorsel_dayanak: False` — hakem videoyu **hiç görmedi**, metni klasör etiketiyle karşılaştırdı |
| hakem | gemma-3-12b — kendi Türkçesi bozuk (*"Olay dışışıır"*, *"yataşa dışme"*) |
| ölçüt | tek kelimelik etikete (`Fall`) göre "uydurma" sayıyor → karar-destek yorumunu ceza yazıyor. 10 bayrağın **6'sı** bu artefakt. |

Piksele dayanan tek kanıt gözle etiketleme: yelek **12/12**, pano **12/12**
(`docs/coklu_etiket_2026-08-25.md`, Wilson alt sınırı 0,739) — olumlu ama
n=24 ve yalnız iki kural.

## 1. Ölçülecek şey

Sistemin ürettiği **her olay iddiası** için: bu iddia klibin karelerinde
**görülüyor mu?**

Kaynak: **arşivlenmiş çıktı** (`eval_20260825_144105.json`, eval_defense).
Boru hattı yeniden koşulmaz — sevk edilmiş metni yargılıyoruz.

## 2. Hakem ve BAĞIMSIZLIK SINIRI (açıkça bildirilir)

Hakem = **`vlm`** (Qwen3-VL-32B, çok-modlu). Üreten = **`llm-large`**.
Farklı modeller → anlatı düzlemi için makul bağımsızlık.

> **SINIRLILIK:** `vlm`, gözlem düzleminin kişi/öznitelik slotlarında da
> kullanılıyor. Kural kaynaklı olaylar için bağımsızlık **kısmidir**.
> Bu, sonuçla birlikte raporlanır; gizlenmez.

Kapalı cevap uzayı: `structured_outputs.choice` ile
**`DOGRULANDI` / `CELISIYOR` / `GORULEMIYOR`**. `temperature=0`.

## 3. DÜZENEĞİN KENDİSİ SINANIR — bu koşumun en önemli parçası

Bu depoda hakemler **iki kez** dejenere çıktı (`RISK` ekseni 5,00 sıfır
varyans; `dialogue_hard` 15/15 = 5,00). Bu yüzden hüküm, düzenek
sınanmadan verilmez.

### 3a. OLUMSUZ DENETIM (negative control) — ZORUNLU
Kliplerin **%25'inde** hakeme, o klibin kareleriyle birlikte **BAŞKA bir
klibin** iddiası verilir. Doğru davranış `CELISIYOR` veya `GORULEMIYOR`.

- **KAPI:** olumsuz denetimde `DOGRULANDI` oranı **≤ 0,20** olmalı.
  Aşarsa hakem "her şeye evet diyor" demektir → **DÜZENEK GÜVENİLMEZ,
  hiçbir hüküm verilmez.**

### 3b. DEJENERELIK KAPISI
Gerçek iddialarda tek bir seçenek **> %95** çıkarsa tavan şüphesi:
sonuç raporlanır ama **hüküm verilmez**, 5 örnek elle denetlenir.

### 3c. KARE KAPSAMI
Kare çıkarılamayan klip ölçüme **girmez** ve sayısı bildirilir.

## 4. ÖRNEKLEM

Tohum **13**, `eval_defense` arşivinden olay içeren **60 klip**.
Kare sayısı: klip başına **6** (boru hattının kendi örneklemesinden).

## 5. BİRİNCİL ÇIKTILAR (eşik DEĞİL — betimleyici)

| çıktı | tanım |
|---|---|
| `iddia_dogrulama` | `DOGRULANDI` / toplam iddia |
| `iddia_celiski` | `CELISIYOR` / toplam iddia |
| `klip_halusinasyon` | en az bir `CELISIYOR` içeren klip oranı |

**Bu bir kol değil, bir ÖLÇÜMDÜR.** Geçme/kalma eşiği YOKTUR; sayı ne
çıkarsa yazılır. Eşik koymamak bilinçlidir: taban yokken eşik uydurmak
dün üç kolu haksız yere reddettirdi.

Ayrıca **ayrıştırılarak** raporlanır:
- kural motoru kaynaklı iddialar ↔ modelin serbest metin iddiaları
- Anomali ↔ Normal klipler

## 6. ÖN-RET KAPILARI

| # | kapı |
|---|---|
| a | olumsuz denetim `DOGRULANDI` > 0,20 → **düzenek güvenilmez, hüküm yok** |
| b | 60 klipten < 45'i işlenemezse ölçüm **geçersiz** |
| c | hakem cevap uzayı dışına çıkarsa (kısıtlı çözme çalışmıyorsa) → **geçersiz** |

Sonuç ne çıkarsa yazılacak. Hiçbir eski skor silinmeyecek.

---

## 7. ÖN KAYIT DÜZELTMESİ — koşumdan ÖNCE, sonuç görülmeden

Duman testi (n=4) düzeneğin **çalıştığını** gösterdi; hüküm üretmedi
(olumsuz denetim n=2, GA %9–91 — anlamsız). Koşum öncesi iki değişiklik:

**(a) Olumsuz denetim oranı %25 → %50.**
Gerekçe **güç**, sonuç değil: 60 klipte %25 ≈ 15 denetim demek; 15'te
"sağlam alet" (≈%5 yanlış-onay) ile "kör alet" (≈%30) **ayırt edilemez**
— Wilson aralıkları örtüşür. Bu, 2026-08-25'te K-b kapısının n=20'de
tanımsız çıkmasıyla aynı kusur; bu kez **önce** yakalandı. %50 ≈ 30
denetim verir ve 0,20 eşiğini anlamlı kılar. Değişiklik kapıyı
**zorlaştırır**, kolaylaştırmaz.

**(b) Hakemin kare değil VİDEO alması.**
Zorunlu, tercih değil: uzak `vlm` ucu görüntü listesini reddediyor —
`"At most 0 image(s) may be provided in one prompt. (parameter=image)"`.
Klip tek video olarak gönderilir; `video_oturumu` videoyu **bir kez**
kodlar, her iddia `hatirla=False` ile sorulur → iddialar birbirini
**etkilemez**. Kısıtlı çözme (`guided_choice`) bu yolda çalışıyor
(duman testinde doğrulandı).

Eşikler ve birincil çıktılar **değişmedi**.
