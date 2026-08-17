# Mentör önerisi: yapılandırılmış prompt mimarisi — değerlendirme ve **ölçüm**

## Öneri (aynen)

> VLM yönlendirmesi için doğru prompt yazımı (çoktan seçmeli, JSON field'larına uygun);
> **sistem prompt ve user prompt farkına** bakılmalı. Örnek: her etiket için **ACTION
> DEFINITIONS** + **kapalı seçenek listesi**
> (`Options for "action": [walking, running, ... dropping_object]`).

## Değerlendirme — teknik olarak sağlam, üstelik burada özel bir çekiciliği vardı

Bugün bulduğumuz **dört ölçüm kusurunun dördü de sözcüksel eşleştirmeden** geliyordu:

| kusur | mekanizma |
|---|---|
| `"olu"` alt-dizgisi | `yolu` / `oluşumu` içinde eşleşiyordu |
| olumsuzlama kapısı | *"gözlemlenmedi"* kaçıyordu — 26 eşleşmenin **21'i sahte** |
| morfoloji | `forkliftin` eşleşmiyor ama `Forklift'in` eşleşiyor |
| `recall` tanımı | olayın **doğru** olması gerekmiyordu |

**Kapalı etiket seti bunların hepsini gereksiz kılar:** etiket ya `class2`'dir ya
değildir. Sözcük yok → eşleştirici yok → kapı yok → morfoloji yok.

Ayrıca bugün kendi yazdığım İSG merceğinin **metrik oyunu** çıktığını ölçmüştük
(skorlayıcının aradığı kelimeleri modele öğretiyordu). Etiket tabanlı değerlendirmede
o risk **yapısal olarak yok** — ödüllendirilecek bir sözcük kalmıyor.

Ve HANDOFF §11 bu kullanımı zaten bekletiyordu:
> *"`guided_choice` … kategori taksonomisi için de kullanılabilir (**asıl önerilen
> kullanım hâlâ yapılmadı**)"*

### Uygularken üç şeyi değiştirdim

1. **Taksonomi:** mentörün örneği suç odaklı (`fighting`, `weapon`, `suitcase`).
   Bugün tam bu çerçeve uyumsuzluğunu teşhis ettik → **İSG sınıfları** kullanıldı.
2. **Kaçış şart:** D33 ölçtü — zorunlu seçimde model pano sorusunda **20/20 "KAPALI"**
   dedi, 10'u açıktı. Listeye `guvenli_durum` ve `belirsiz` konmasaydı model yok yere
   pozitif üretirdi.
3. **Tanımlar tek kaynaktan:** `labels.py`'deki `ISG_SINIFLAR[...]["tanim"]` alanından
   üretiliyor. Prompt ile skorlayıcı **aynı tanıma** bakar, birbirinden kayamaz.

---

## Ölçüm sonucu — **çalışmadı**, ve nedeni öğretici

`benchmark/isg_yapilandirilmis_prob.py` · eval_defense 197 klip · T=0 · 8 kare

| yaklaşım | TP | FP | FN | TN | **MCC** | recall |
|---|---|---|---|---|---|---|
| yapılandırılmış **6-yönlü** | 28 | 25 | 71 | 73 | **+0,031** | %28 |
| yapılandırılmış **ikili** | 1 | 0 | 98 | 98 | +0,071 | **%1** |
| **mevcut boru hattı (serbest metin)** | 28 | 22 | 71 | 76 | **+0,067** | %28 |

**6-yönlü:** sınıf doğruluğu **%7,1** — şansın (%16,7) **altında**. Model 197 klibin
**144'ünde (%73)** `guvenli_durum` dedi.

**İkili:** model **196/197** klipte `ihlal_yok` dedi. Dejenere.

### ⚠️ Bir metrik tuzağı (kayda değer)

İkili kolun MCC'si (+0,071) boru hattından (+0,067) **yüksek görünüyor** — ama o
sınıflandırıcı **neredeyse hiç ateşlemiyor** (recall %1). Tek doğru tahmini MCC'yi
iyi gösteriyor. **MCC tek başına dejenere sınıflandırıcıyı ele vermez**; recall'le
birlikte okunmalı. Bu, projenin "tek metrik yeter" tuzağına bir örnek daha.

---

## Sonuç: darboğaz **format değil, algı**

Yapılandırılmış çıktı **biçim gürültüsünü** sıfırlar. Ama bizim sorunumuz biçim değil:
model bu görüntülerde İSG ihlalini **göremiyor**. Commit etmeye zorlandığında
"güvenli" diyor — çünkü ayırt edecek sinyali bulamıyor.

Bu, bugün ölçtüğümüz her şeyle **tutarlı**:

- `isg_özgül` taban = **1/99**
- `class2` (Opened_Panel_Cover) ile `class5` (Authorized_Intervention) **aynı görüntü**
  — 8 sınıfın 2'si zaten ayrılamaz
- **AUC(aynı etiket) = 0,538** — fark gerçekten ince ve davranışsal
- Qwen3.8-27B'de hassasiyet **birebir aynı** kaldı (0,560 → 0,556)
- 7 yamanın 7'si karşıtsal denetimde reddedildi

**Serbest metin, zorunlu seçimden daha iyi çalışıyor** — çünkü model fark ettiğini
raporlayabiliyor, eşleştirici de sonra bakıyor. Zorunlu seçim ise destekleyemediği
bir etikete commit ettiriyor.

---

## Kalıcı kazanımlar (öneri reddedilse de duruyor)

Mentörün mimarisinin **altyapısı** doğruydu ve iki gerçek eksiği kapattı:

1. **`guided_choice` artık üretim yolunda** (`llm_client.chat` + `analyze_frames`).
   Önceden yalnızca prob betikleri ham OpenAI istemcisiyle deniyordu; HANDOFF §11
   bunu bekletiyordu. Artık herhangi bir görev kısıtlı seçim isteyebilir.
2. **Sistem promptu artık göreve göre değişebilir** (`analyze_frames(system=...)`).
   Önceden `SYSTEM_PERSONA` **sabitti**. Bu, mentörün "sistem/user ayrımı" noktasının
   tam karşılığı ve gerçek bir mimari eksikti — genel persona dar görevlerde gürültü
   yapıyor (ör. *"fabrika VARSAYMA"* kuralı İSG sınıflandırmasında ters çalışır).
   Varsayılan `None` → eski davranış **birebir** (K2).

## Mentöre verilecek cevap (özet)

> Öneriyi uyguladık ve ölçtük. Teknik olarak doğru bir mimari; altyapısını kalıcı
> olarak aldık (`guided_choice` üretimde, sistem promptu artık parametrik).
> **Ama bizim darboğazımızı çözmüyor:** 6-yönlü kapalı seçimde sınıf doğruluğu
> %7,1 (şans %16,7), model %73 oranında "güvenli" diyor; ikili sorulunca 196/197
> "ihlal yok". Serbest metin boru hattı (MCC +0,067) yapılandırılmış seçimden
> (+0,031) **daha iyi**. Sebebi ölçtük: `class2` ve `class5` **aynı görüntü**,
> Anomali/Normal görsel AUC'si **0,538** — ayırt edici sinyal veride zayıf.
> Format mühendisliği bunu düzeltemiyor.
