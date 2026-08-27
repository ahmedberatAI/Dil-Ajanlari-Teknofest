# SONUÇ — Olay adı paneli, aşama 1: **RET, aşama 2'ye geçilmedi**

Tarih: 2026-08-27 · Ön kayıt: [`on_kayit_olay_adi_paneli_2026-08-27.md`](on_kayit_olay_adi_paneli_2026-08-27.md)
Veri: `eval_genelleme` 50 tehlike klibi (arşivin **tamamı**, örnekleme yok)
Arşiv: `benchmark/results/eval_20260825_195405.json` · yer gerçeği `hazard_mcq_single.json`

## Hüküm

| kapı | eşik | ölçülen | |
|---|---|---|---|
| G1 | B top-1 ≥ %40,0 | **%21,4** | **KALDI** |
| G2 | B − A ≥ +12,0 puan | **−7,1 puan** | **KALDI** |
| G3 | McNemar p < 0,05 | p=0,5811 (b=8 c=5) | **KALDI** |
| G4 | bilgisiz kontrol ≤ %8,0 | %0,0 | geçti |

**Aşama 2'ye (80 dk canlı koşum) GEÇİLMEDİ.**

| kol | dar ölçüt | geniş ölçüt |
|---|---|---|
| **A** sözcüksel (model çağrısı YOK) | **12/42 = %28,6** [17–44] | %40,5 |
| **B** panel (kapalı seçim) | **9/42 = %21,4** [12–36] | %35,7 |
| **C** bilgisiz kontrol | 0/42 = %0,0 | %0,0 |

Panel, **sözcüksel eşleştirmeden kötü**. Sentezin dayandığı D48 farkı
(*"aynı metinden zorunlu seçim %48, anahtar kelime %28"*) bu kümede
**tekrarlanmadı, ters yöne çıktı**.

## Ölçüm sağlam — düzenek suçlu değil

- **Bilgisiz kontrol %0,0** → model prior'dan tahmin etmiyor, gerçekten metne bakıyor
- **Menü kapsam tavanı %84,0** (geniş %88,0), **koşumdan önce** ölçüldü →
  düşük skor "menü yetersiz" değil, **seçim** darboğazı
- **Dejenerelik yok**: "LİSTEDE YOK" %12,0 · en çok seçilen yaprak %12,0 ·
  17 yaprağın 15'i kullanılmış
- Örnekleme yok: arşivin tamamı (50/50), cherry-pick imkânsız

Yani model metni okuyor, menüyü kullanıyor, **yanlış yaprağı seçiyor**.

## Menü ve harita (donduruldu, kayıt için)

16 yaprak + `LİSTEDE YOK`: Yangın · Duman/patlama · Yüksekten düşme ·
Yükün düşmesi · Yapısal çökme · Vinç denge kaybı · Araç kontrol kaybı ·
Araç çarpması · Makineye kapılma · Sıkışma/ezilme · Ağır cisim kayması ·
Raf devrilmesi · Kaldırma platformu hatalı kullanımı · Forklift kullanım
hatası · Kavga/saldırı · Kasıtlı hasar.

Kapsanmayan 6 GT etiketi hepsi **insan tepkisi veya tehlike olmayan**:
`moving in a suspicious manner`(2) · `watching incident passively`(2) ·
`escaping from danger` · `police search` · `rescue effort` · `tree falling nearby`.

## Bu, anlatı düzleminde ALTINCI ret

| # | deneme | sonuç |
|---|---|---|
| 1 | İngilizce prompt (27 klip, eşleşmiş) | sessiz kaçırma **0/9** |
| 2 | `d-35 a333f24` nedensel ayrım (6 tekrar) | yangın **0/6** |
| 3 | `d-35 ff46622` mutlak öncelik | isabet 5/6 → **3/6** (zararlı) |
| 4 | tehdit merceği ablasyonu | alev/duman 4/4 ham betimlemede yok |
| 5 | ikili panel + logprob | kavga 0,990 > yangın 0,777 |
| 6 | **menülü olay paneli** | **A %28,6 > B %21,4** |

Altısı da anlatı düzlemine dokundu, altısı da kaybetti. Gözlem düzlemi
(kapalı slot + deterministik kural) **+0,960 / +0,881** veriyor.

**Ölçülmüş gözlem:** anlatı düzleminde adlandırmayı düzeltme girişimlerinin
altısı da başarısız oldu. Kazandıran tek desen slot + kural, ve o yalnız
kalibre edilmiş eksenlerde çalışıyor.

Betik: `scratchpad/panel_asama1.py` · ham çıktı `/tmp/panel_asama1.json`
