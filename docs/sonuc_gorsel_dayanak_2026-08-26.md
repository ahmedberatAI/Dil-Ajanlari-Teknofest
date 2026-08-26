# SONUÇ — Görsel dayanak: **DÜZENEK GÜVENİLMEZ, hüküm verilmedi**

Tarih: 2026-08-26 · Ön kayıt: [`on_kayit_gorsel_dayanak_2026-08-26.md`](on_kayit_gorsel_dayanak_2026-08-26.md)
Düzenek: `benchmark/gorsel_dayanak.py` · arşiv `eval_20260825_144105.json`
Örneklem: 60 klip (tohum 13), 128 iddia, 41 olumsuz denetim · hakem `vlm` · `temperature=0`

## Hüküm: ÖN-RET (a) TETİKLENDİ

| kapı | eşik | ölçülen | sonuç |
|---|---|---|---|
| kapsam | ≥ 45 klip | **60/60** | geçti |
| **olumsuz denetim** | `DOGRULANDI` ≤ **0,20** | **15/41 = 0,37** [0,24–0,52] | **DÜŞTÜ** |

Hakeme, klibin görüntüsüyle birlikte **başka bir klibin iddiası** verildi.
Doğru cevap `CELISIYOR` veya `GORULEMIYOR`. Hakem 41 denemenin **15'inde**
yine `DOGRULANDI` dedi.

**Bu yüzden aşağıdaki sayılar HÜKÜM DEĞİLDİR** — kayıt için yazılıyor:

| | oran |
|---|---|
| `DOGRULANDI` | 90/128 = %70,3 [62–78] |
| `GORULEMIYOR` | 38/128 = %29,7 |
| **`CELISIYOR`** | **0/128 = %0** |
| kural motoru iddiaları doğrulandı | 38/60 = %63,3 |
| model metni iddiaları doğrulandı | 52/68 = %76,5 |

## İkinci dejenerelik işareti: hakem HİÇ "çelişiyor" demiyor

`CELISIYOR` **128 gerçek iddianın sıfırında** çıktı — ve 41 olumsuz denetimin
de sıfırında. Yani hakem üç seçenekli değil, fiilen **iki seçenekli**
çalışıyor: `DOGRULANDI` veya `GORULEMIYOR`. Hiçbir şeyi yalanlamıyor.

Kısıtlı çözme çalışıyor (cevapsız 0/128), yani sorun biçimde değil
**hakemin ayırt edememesinde**.

## Bu, bu depoda hakemlerin ÜÇÜNCÜ dejenere çıkışı

| # | hakem | belirti |
|---|---|---|
| 1 | `judge_independent` iç-tutarlılık | RİSK ekseni **5,00**, sıfır varyans |
| 2 | `dialogue_hard` doğallık | **15/15 = 5,00**, std 0 |
| 3 | **bu koşum** | olumsuz denetimde **%37 yanlış-onay**, `CELISIYOR` %0 |

Fark şu: bu kez **koşumdan önce** yazılmış bir kapı bunu yakaladı ve sahte
bir sayı rapor edilmedi. Önceki ikisinde tavan yapan puanlar bir süre
"sonuç" diye taşındı.

## Ne ölçülmedi

**"Model bir olayda ne yaşandığını doğru biliyor mu?"** sorusu **hâlâ
yanıtsız.** Elimizdeki tek dayanaklı kanıt, gözle etiketlenmiş iki küçük
çalışma (`docs/coklu_etiket_2026-08-25.md` — yelek 12/12, pano 12/12,
Wilson alt sınırı 0,739).

## Neden başarısız oldu — ve daha iyi düzenek ne olurdu

Sorulan soru bir **doğrulama** görevi: *"bu iddia görüntüde var mı?"*
LLM'ler bu biçimde makul görünen her iddiayı onaylamaya eğilimli — ölçtük,
%37.

Daha sağlam biçim **iki-seçenekli zorunlu ayrım (2AFC)**: hakeme AYNI anda
biri gerçek biri yabancı **iki iddia** verilir ve *"hangisi bu klibe ait?"*
sorulur. Şans düzeyi tam **%50** ve bilinir; hakem şansı geçemiyorsa körlük
kanıtlanır. Doğrulama görevindeki "evet" yanlılığı bu tasarımda **yapısal
olarak** yok, çünkü her iki seçenek de aynı biçimde sunulur.

Bu koşum tekrarlanacaksa 2AFC ile ve **yeni ön kayıtla** yapılmalıdır.
Bu koşumun sonucu silinmeyecek.
