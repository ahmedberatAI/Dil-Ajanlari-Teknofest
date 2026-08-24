# Genel İSG senaryolarında performans — ölçüldü

Tarih: 2026-08-24 · Dal: `d34-isg-veri-kkd`

Soru: *"kendi verimize göre değil, genel iş sağlığı güvenliği senaryolarında
mevcut modelin performansı nasıl olabilir?"*

Bunu tahmin etmek yerine **bağımsız bir kaynakta ölçtük**: iSafetyBench
(arXiv 2508.00399), 1100 klip, YouTube kaynaklı, çeşitli endüstriyel ortamlar.
Bizim tesisimizle hiçbir ilgisi yok.

> **Lisans:** `data/isafety_bench` CC BY-NC-SA 4.0 — **yalnızca değerlendirme**.
> Koşumdan önce kapı iki yönlü doğrulandı: değerlendirme izni var, eğitim
> `LisansIhlali` ile reddediliyor. Hiçbir ağırlık üretilmedi.

> **Alan uyarısı:** klipler YouTube kaynaklı, çoğu **hareketli kamera**, kısa.
> Bizim dağıtım ortamımız **sabit kamera CCTV**. Buradaki sayılar bir
> **genelleme stres testidir**, "başka bir fabrikada da böyle olur" kanıtı değil.

---

## 1. Modelin ham genel İSG yeteneği (16 seçenekli MCQ)

Model kareler yerine videoyu görür, 16 seçenekten birini seçmeye **zorlanır**
(`structured_outputs.choice`, temperature=0), klip başına 1 soru
(pseudo-replikasyon önlemi). Şans tabanı **%6,25**.

| model | tehlike klipleri | rutin klipler |
|---|---|---|
| `vlm` (Qwen3-VL-32B) | %44,0 [%36–%52] | %52,7 [%45–%60] |
| `llm-large` (Qwen3.5-122B-A10B) | %54,7 [%47–%62] | %48,7 [%41–%57] |

n=150/kol, tohum 2026 (her iki model **aynı klipleri** gördü).

Okuma: iki model de şansın **7–9 katı** — genel endüstriyel tehlikeleri
gerçekten tanıyorlar. Ama 16 seçenek içinde yaklaşık **yarısını** kaçırıyorlar.
`llm-large` tehlikede daha iyi, `vlm` rutinde; güven aralıkları kısmen örtüşüyor,
yani bu fark eşleştirilmiş bir testle doğrulanmadan kesin sayılmamalı.

> Önceki kayıtlı ölçüm (yerel Qwen3-VL-8B: tehlike %55,3 / rutin %48,7)
> **geçersizdir** — o dönemde vLLM `guided_choice` alanını sessizce yok
> sayıyordu, model serbest metin dönüyordu ve ayrıştırıcı ilk karakteri
> alıyordu ("Bu videoda…" → B).

> Makaledeki %53,4 F1 **çok etiketli** görevin metriğidir; bu sayıyla
> **aynı şey değildir**, yan yana konmamalıdır.

---

## 2. Bizim sistemimiz aynı yabancı kliplerde

MCQ modeli ölçer. Bu koşum **uçtan uca ajanı** ölçer: 60 klip (30 tehlike +
30 rutin), sevk yapılandırması, hiçbir ayar değiştirilmeden.

| küme | ≥1 olay | ≥Yüksek önem | **tesise özgü İSG kuralı ateşledi** |
|---|---|---|---|
| tehlike | 29/30 (%97) | 26/30 (%87) | 15/30 (%50) |
| rutin | 16/30 (%53) | 15/30 (%50) | 15/30 (%50) |

Klip başına medyan 36,0 s.

### 2.1 Anlatı düzlemi iyi genelleşiyor

Tehlike kliplerinin **%97'sinde** olay üretti ve özetler gerçekten isabetli:

- *"bir raf ünitesinde parlak turuncu alev ve kıvılcım oluşumu tespit edilmiştir"*
- *"bir forkliftin yükü fırlatması ve kontrolünü kaybederek devrilmesi"*
- *"dağılmış yük, cam kırıkları ve sıvı döküntüsü … enkaz içinde bulunan personel"*

Rutin kliplerin yarısında da sustu (*"herhangi bir anormal durum … tespit
edilmemiştir"*). Bu düzlem tesise bağlı değil; açık dünya tehlikelerinde çalışıyor.

### 2.2 Gözlem düzlemi TAŞINMIYOR — ve bu doğrudan kanıtlandı

Tesise özgü kurallar **her iki kümede de %50** ateşledi:

| kural | yabancı kliplerde ateşleme |
|---|---|
| `Opened_Panel_Cover` | 18 |
| `Unauthorized_Intervention` | 14 |
| `Carrying_Overload_with_Forklift` | 3 |

Bu kuralların **hiçbiri** o kliplerde ateşlememeliydi. Sebep açık: eşikler ve
ROI'ler bizim kameralarımıza kalibre. `panel_roi_vlm = 0.00,0.47,0.29,0.81`
*bizim* karemizde bir dikdörtgendir; YouTube videosunda rastgele bir bölgeye
düşer ve koyuluk eşiği ateşler.

**Forklift kuralının yalnızca 3 kez ateşlemesi tesadüf değil.** O slot bir
**nesnenin varlığını** sorar ("çatalda kaç kasa?") ve forklift yoksa
`GORUNMUYOR`/`0` döner — kendi kendini sınırlar. Pano ve yelek slotları ise
bir **bölgenin özelliğini** ölçer; bölge her karede vardır, dolayısıyla her
zaman bir sayı üretirler. Bu, kendi setimizde de ölçtüğümüz aynı desen
(bkz. `gozlem_duzlemi_2026-08-24.md` §17).

---

## 3. Yeni bir tesise götürürken ne taşınır, ne taşınmaz

**Taşınmaz (yeniden kalibrasyon şart):**

| öğe | neden tesise özgü |
|---|---|
| `panel_roi_vlm` | belirli bir kameradaki dikdörtgen |
| `panel_koyuluk_esik = 6` | o panonun aydınlatması |
| `forklift_esik = 3` | *bu* tesisin konvansiyonu (kaynak makaleden) |
| yelek = yeşil | *bu* tesisin KKD konvansiyonu |
| slot soruları | "makinenin/panonun başında" — o sahneyi varsayar |

**Taşınır (kod değişmeden):**

- Anlatı düzlemi (açık dünya tehlikeleri) — yabancı veride %97 tehlike recall'i
- Deterministik kural motoru; karar döngüsünde model yok
- Ön koşulun ayrı bir slot olması
- Slot kapsamı (an ölçümü / klip ölçümü) ayrımı
- "Ölçülemedi ≠ ihlal yok" hata kaydı
- Kalibrasyon **yordamı**: ROI seç → eşiği seçim kümesinde tara → **ayrılmış
  kümede doğrula**. Bu projede slot başına ~20 dakika sürdü.

**Tasarım kuralı (bu iki ölçümde de doğrulandı):**
Nesnenin **varlığını** soran slot kendi kendini sınırlar; bir bölgenin
**özelliğini** ölçen slot sınırlamaz ve mutlaka sahne ön koşulu ister.

---

## 4. Özet cevap

- Modelin **ham** genel İSG tanıma yeteneği: 16 seçenekli testte ~%50
  (şansın 8 katı) — gerçek ama tek atışta güvenilir değil.
- **Anlatı düzlemimiz** genel senaryolarda iyi çalışıyor: yabancı tehlike
  kliplerinin %97'sinde olay üretiyor, açıklamaları isabetli.
- **Yüksek İSG skorlarımızı üreten gözlem düzlemi ise taşınmıyor** ve bu
  ölçülerek gösterildi: yabancı kliplerin %50'sinde yanlış ateşliyor.
- Yeni bir tesiste sistem, **mimari olarak** hazır ama **kalibrasyon olarak**
  sıfırdan başlar. İyi haber: yordam yazılı ve ucuz.
