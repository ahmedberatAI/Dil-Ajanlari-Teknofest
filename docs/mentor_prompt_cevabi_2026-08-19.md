# Mentöre cevap — prompt tezi ADİL koşulda sınandı (D40)

**Tarih:** 2026-08-19 · Ön-kayıt: `docs/on_kayit_islemsel_prompt_2026-08-18.md`
Sonuç: `benchmark/results/islemsel_prompt_20260819_122138.json`

**Kısa cevap: mentör bir sınıfta net haklı, iki sınıfta değil — ve önceki
"ölçtük, olmadı" cevabımız iki ayrı sebepten geçersizdi.**

---

## 1. Önceki cevabımız neden geçersizdi

### (a) Modele cevaplanamaz soru soruyorduk

Veri setinin kaynak makalesi (Onal & Dandil 2024, *Data in Brief* 56:110756)
etiketleri **işlemsel** tanımlıyor. Bizim `benchmark/labels.py`'de modele
verdiğimiz tanımlarla karşılaştırınca:

| sınıf | **modele verdiğimiz** | **gerçek tanım** |
|---|---|---|
| `Carrying_Overload` | "güvenli kapasiteyi aşacak şekilde" | **"3 blocks or more"** |
| `Unauthorized_Intervention` | "yetkili teknisyen dışında biri" | **"without an intervention vest"** |

Model **"güvenli kapasite"yi göremez**, **"yetkili"yi göremez**. Ama **sayabilir**.

### (b) Kısıtlı kod çözme HİÇ ÇALIŞMIYORDU

**vLLM 0.23, `extra_body`'deki eski `guided_choice` alanını sessizce yok sayıyor**
— hata vermiyor, uyarı vermiyor, serbest metin döndürüyor. Kanıt: aynı isteğin
kısıt açık/kapalı çıktıları **birebir aynıydı**.

| gönderilen alan | sonuç |
|---|---|
| `guided_choice` | serbest metin (**atıl**) |
| `guided_decoding.choice` | serbest metin (atıl) |
| `response_format` json_schema | `'"YELEK_VAR"'` (tırnaklı) |
| **`structured_outputs.choice`** | **`'GORUNMUYOR'` — doğrusu** |

`dilajan/llm_client.py` onarıldı.

**Geriye dönük etki:**
- **D37** — *"mentörün kapalı seçenek mimarisi ölçüldü ve reddedildi"* sonucu,
  **hiç devreye girmemiş** bir mekanizmaya dayanıyordu. O koşumda model kapalı liste
  değil serbest metin üretti. **Mimari hiç test edilmemişti.**
- **D33** — *"guided_choice ile zorunlu seçimde model 20/20 klipte KAPALI dedi"*
  ölçümü de kısıtsız koşmuş.
- **HANDOFF §11** — *"`guided_choice` artık üretim yolunda"* kazanımı yanlıştı.

---

## 2. Adil test — üç kol

Tasarım, koşulmadan önce üç bağımsız ajana çürütüldü (hepsi "düzeltilmeden
koşulamaz" dedi). Buldukları kusurlar onarıldı; en önemlisi kavramsaldı:

> İşlemsel soru, anlamsal sorudan **üç şeyi birden** değiştiriyor: nereye
> bakılacağı, kararın nerede verildiği, biçim. "Tek değişken" iddiası yanlıştı.

Bu yüzden **A2 kolu** eklendi — anlamsal ölçüt + B ile **aynı mekânsal çapa**.

| kol | soru |
|---|---|
| **A** | anlamsal, çapa yok — bugüne kadarki soru |
| **A2** | anlamsal + aynı mekânsal çapa |
| **B** | kaynak makalenin gözlemlenebilir ölçütü |

---

## 3. Sonuç

Aynı klipler · aynı model (Qwen3-VL-8B-FP8) · T=0 · 8 kare · üretim çözünürlüğü

| kol | A anlamsal | A2 + çapa | **B işlemsel** | deterministik dedektör |
|---|---|---|---|---|
| **forklift** | 0,000 *(dejenere)* | 0,000 *(dejenere)* | **+0,762** | +0,718 |
| **yelek** | −0,300 | 0,000 *(dejenere)* | **0,000** | ~+0,644 |
| **pano** *(keşifsel)* | +0,147 *(dejenere)* | — | **0,000** | 15/99 |

### Forklift — mentör haklı

| | TP | FP | FN | TN | doğruluk | MCC |
|---|---|---|---|---|---|---|
| A anlamsal | 0 | 0 | 25 | 25 | 0,500 | 0,000 |
| **B işlemsel** | **21** | **2** | 4 | 23 | **0,880** [0,762–0,944] | **+0,762** |

**A → B: p = 6,6×10⁻⁵** (Bonferroni eşiği 0,0125).

**A2 ≡ A (p = 1).** Mekânsal çapa **tek başına hiçbir şey yapmadı**. Yani kazanan
dikkat yönlendirmesi değil, **gözlemlenebilirlik**.

### Yelek ve pano — mentör haksız, ama soru yüzünden değil

Kısıt artık çalışırken model şunu döndürdü:

| kol | cevap dağılımı |
|---|---|
| yelek B | **50/50 `KISI_YOK`** |
| pano B | **49/49 `GORUNMUYOR`** |

Model, makine başındaki **kişiyi bulamıyor bile** — RT-DETRv2 aynı kliplerin
23/25'inde yelekli kişi buluyor. Bu, çalışan bir kısıt ve cevaplanabilir bir soruyla
ölçülmüş **gerçek algı sınırı**.

---

## 4. Kodlama izi kontrolü — sonucu ayakta tutan test

Bu veri setinde ağır kodlama sızıntısı var: **bit hızı tek başına taşıma sınıflarını
MCC +1,000 ile ayırıyor** (hiç örtüşme yok). Yani "model saydı" ile "model sıkıştırma
imzasını okudu" ayırt edilmeliydi. Ön-kayıtta bu söz verilmişti.

50 klip **ortak spesifikasyona yeniden kodlandı** (`benchmark/yeniden_kodla.py`):

| | önce | sonra |
|---|---|---|
| Overload bit hızı | 17,81–21,58 M | **6,06–7,28 M** |
| Safe bit hızı | 4,10–7,06 M | **6,39–7,37 M** |
| profil / pix_fmt | Constrained Baseline / `yuv420p` **vs** High / `yuvj420p` | **ikisi de** Main / `yuv420p` |
| **B işlemsel MCC** | +0,682 | **+0,762** |

**Kodlama farkı tamamen silindi ve sonuç DÜŞMEDİ, YÜKSELDİ.**
Model imza okumuyor — **gerçekten sayıyor**.

---

## 5. Mentöre ne der, ne DEMEZ

### Der

- **Soru gözlemlenebilir bir ölçüte çevrildiğinde**, aynı model aynı karelerde
  **0,000'dan +0,762'ye** çıkıyor. Mentörün tezinin çekirdeği **doğrulanır**:
  prompt, tesise özgü kuralı sisteme sokmanın geçerli bir yeridir.
- Bu, arşivdeki kanıtla da tutarlı: `facility_rules` özgül TP'yi **1 → 16/99**
  yapmıştı; reddetme gerekçemiz doğruluk değil, FP bedeliydi (2 → 23/98).
- **Bizim D37 cevabımız yanlıştı** ve iki ayrı sebepten: cevaplanamaz soru +
  çalışmayan kısıt.

### DEMEZ

- **"Promptla ayrılabiliyor" ≠ "dedektöre gerek yok".** Bu yalnızca **dört sınıfın
  birinde** oldu. Diğer ikisinde model kişiyi/panoyu **göremiyor**; orada prompt
  ne yapılırsa yapılsın çözüm değil.
- **"Genel bir İSG yeteneği" değil.** *"≥3 kasa = ihlal"* demek, **bu tesisin
  konvansiyonunu prompta gömmektir**. Başka tesiste yeniden kalibrasyon gerekir —
  tıpkı `facility_rules` ve deterministik dedektörlerimiz gibi.
- **Kararı hâlâ kod veriyor.** B kolunda eşik (≥3) **modelde değil, kodda**. Yani
  kazanan yapı *"VLM gözlemlenebilir özniteliği çıkarır + kural dışarıda uygulanır"* —
  ki bu **zaten bizim mimarimiz**. Fark şu: öznitelik çıkarıcı YOLO değil, VLM olabilir.
- **n=50.** B'nin Wilson %95 GA'sı [0,762–0,944]. Güç analizi: bu tasarım ancak
  ~0,30 doğruluktan büyük etkileri güvenle yakalar. *"Fark yok"* sonucu
  *"etki yok"* demek değildir.

---

## 6. Bunun mimariye etkisi

Forklift sınıfında **iki geçerli yol** var:

| yol | MCC | maliyet | taşınabilirlik |
|---|---|---|---|
| deterministik dedektör (istif yüksekliği) | +0,718 | ~0 GPU | ROI/kalibrasyon gerek |
| **VLM + işlemsel soru** | **+0,762** | 1 VLM çağrısı/klip | prompt değişir, kod değişmez |

VLM yolu **daha esnek** (yeni kural = yeni cümle), dedektör yolu **daha ucuz ve
kararlı**. Kararı ölçüm veriyor: ikisi de çalışıyor.

**Yelek ve pano için tartışma yok** — VLM göremiyor, deterministik dedektör görüyor.
