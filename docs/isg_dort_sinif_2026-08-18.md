# Dört İSG sınıfının tamamı — bulgular, kararlar, veri seti kusurları

**Tarih:** 2026-08-18 · Dört sınıf bağımsız ajanlarla analiz edildi; her olumlu
iddia ayrı bir ajana **çürütülmek üzere** verildi.

---

## 0. Oyunu değiştiren bulgu — veri setinin kendi makalesi bulundu

Onal Ö., Dandil E. (2024) *"Video dataset for the detection of safe and unsafe
behaviours in workplaces"*, **Data in Brief 56:110756** —
[PMC11367630](https://pmc.ncbi.nlm.nih.gov/articles/PMC11367630/)

Makale etiketleri **işlemsel olarak** tanımlıyor:

> *"carrying **2 blocks or less** with a forklift (Safe Carrying), whereas … an
> example of an unsafe worker behaviour occurs by carrying **3 blocks or more**"*

> *"a worker wearing a **green vest** (Authorized Intervention), while … an
> unauthorized intervention on the board by a worker **without an intervention vest**"*

**Bu, VLM'imizin neden 1/99'da kaldığını açıklıyor.** Model *anlam* arıyordu
("bu davranış güvenli mi?"); veri ise **sayım** ve **kıyafet konvansiyonu**
kodluyor. Ne format mühendisliği ne de daha büyük model bunu çözebilirdi —
ikisini de ölçüp reddetmiştik, şimdi nedenini biliyoruz.

**Kamera bilgisi (aynı makale):** Kamera 9 = yaya yolu + araç yolu + makine panosu.
Kamera 14 = forklift yolları. İkisi de UNV IPC2122CR3-PF40-A, yerden ~4 m,
1920x1080, 24 fps. Eskişehir OSB, 5 Kas – 13 Ara 2022.

**Kaynak sınıf sayıları (691 klip):** ihlal sınıfları normal sınıflarından 2-4x
fazla. Bizim 197'lik alt kümemiz **dengelenmiş**, yani örnekleme bizim tarafımızda
yapılmış; çerçeve-etiket korelasyonunun bir kısmını bu açıklayabilir.

**Referans başarı:** aynı yazarların *Unsafe-Net* (YOLOv4 + ConvLSTM) çalışması bu
veride **%95,81** doğruluk raporluyor, fabrikada kurulu ve ihlal tekrarını ~%75
azaltmış. Veri **denetimli eğitim için** yapılmış — sıfır-atış VLM için değil.

**Lisans çelişkisi (doğrulanmalı):** Mendeley sayfası CC BY 4.0, PMC makale başlığı
CC BY-NC diyor.

---

## 1. `Carrying_Overload_with_Forklift` — KABUL, en güçlü sonuç

**Mekanizma:** istif yüksekliği. Safe = **2 kasa**, Overload = **3 (bazen 4) kasa**.
Kaynak makalenin tanımıyla birebir aynı — ama ajan bunu makaleyi görmeden,
**gözle bakarak** buldu.

**Fizikle doğrulandı, ve bu tesadüf değil:**

| ölçüm | beklenen | ölçülen |
|---|---|---|
| perspektif-normalize yük yüksekliği oranı (3/2) | **1,500** | **1,576** |
| satır profilinden kasa bandı sayımı (bağımsız 2. ölçüm) | c3=3 · c7=2 | c3=3 · c7=2 |

İki öznitelik arası Spearman **rho +0,800 · p = 8,8e-12**.

**Sonuç (iyimserlik giderilmiş, iç içe LOO — her katlamada eşik yeniden seçilerek):**

| | TP | FP | FN | TN | doğruluk | MCC |
|---|---|---|---|---|---|---|
| iç içe LOO | 17 | **0** | 8 | 25 | 0,840 [0,715-0,917] | **+0,718** |

- **Özgüllük 25/25 = 1,000** [0,867-1,000] — yanlış alarm yok
- **Tesis çapında 0/172 yanlış alarm** — diğer 6 sınıfın 147 klibinde hiç ateşlemiyor.
  Pano kuralını öldüren "yanlış kamera görüşünde boşa ateşleme" hatası **burada yok**
- Maks-istatistiği permütasyonu (25 hücre, B=20.000, bağımsız): **p = 0,00005**
  (boş dağılım ortalaması 0,268 — 25 eşikten en iyisini seçmek tek başına ~0,27 MCC
  "bedava" üretir; bu gürültü tabanı doğru tespit edilmiş)

### Çürütme turu — mekanizma çürütülemedi

Doğrulayıcı ajan sayıların **tamamını bağımsız kodla birebir** yeniden üretti;
etiketleri iddiadan değil dosya sisteminden aldı.

**En sert saldırısı başarısız oldu.** Veride bir kodlama izi buldu:
**bit hızı tek başına MCC +1,000** (c3 17,8-21,6 vs c7 4,1-7,1 Mbit/s, **hiç örtüşme
yok**); `pix_fmt`, H.264 profili, kodlayıcı etiketi, fps ve süre kuantizasyonu da
%100 ayırıcı.

Bunun kuralı açıklayıp açıklamadığını test etmek için **50 klibi ortak spesifikasyona
yeniden kodlayıp boru hattını baştan koşturdu:**

| | önce | yeniden kodlama sonrası |
|---|---|---|
| AUC | 0,839 | **0,845** |
| LOO MCC | +0,783 | **+0,783** |
| karışıklık matrisi | 19/0/6/25 | **aynı** |
| fiziksel oran | 1,576 | **1,560** |

**Kural sıkıştırmaya duyarlı değil, ve fiziksel öngörü iki kodlama rejiminde de tutuyor.**

**Sınır:** duyarlılık 17-19/25. **Altı kaçırmanın altısı da** "yük çok uzakta/kırpık,
ölçülemedi" — ayırt etme hatası değil, **ölçülebilirlik** hatası.

---

## 2. `Unauthorized_Intervention` — ŞARTLI, gerçek ama şişkin

**Mekanizma:** makine başındaki kişide **parlak lime reflektif yelek**.
class5 (yetkili) 23/25'te yelekli kişi var; class1 (yetkisiz) 22/25'te yok.

**Ham sonuç:** hi-vis, makine ROI, tau=800 → TP=22 FP=1 FN=3 TN=24,
doğruluk 0,920, **MCC +0,843**, permütasyon p=0,0002.

### Üç ciddi çekince

**(a) Çerçeve karıştırıcısı burada yaya yolundan 3x güçlü.**
küme0 n=31 (8 ihlal/23 normal) · küme1 n=19 (17/2) ·
**Fisher p = 2,2e-05 · OR = 24,44**.
**Çerçeve kimliği tek başına "yetki"yi %80 doğrulukla tahmin ediyor (MCC +0,618).**

Tek temiz iç-grup ölçümü (küme0, n=31, sabit ön-kayıtlı tau=800): **MCC +0,644** —
çerçeve-tek-başına'nın (+0,618) **kıl payı üstünde**.

**(b) Plasebo kapısı düştü.** Makine ROI'sinin **aynası** (boş koridor zemini)
**+0,655** veriyor; ön-kayıt en fazla 0,422'ye izin veriyordu.
Gerçek − plasebo farkı **+0,188, GA [+0,015 · +0,362]** — sıfırı **kıl payı** dışlıyor.

**(c) Meta-veri sızıntısı.** Konteyner kare hızı tek başına:
`fps < 24,84 → ihlal` → doğruluk 0,920, **MCC +0,851** — en iyi görsel kuralımızdan
**daha iyi**. Sıfır İSG içeriği olan bir kodlama izi.

**Küme-katmanlı permütasyon p = 0,0004** — çerçeve kimliğinin **ötesinde** gerçek
bilgi var. Ama dürüst manşet +0,843 değil, **~+0,64**.

**Dört hatanın dördü de görsel olarak doğrulanmış etiket çelişkisi:**
`1_tr42`, `1_tr61` "yetkisiz" etiketli ama **yelekli**; `5_te2`, `5_tr12` "yetkili"
ama **yeleksiz**. Kural etiketlerden daha tutarlı olabilir.

**Ajan kendi ilk hipotezini ölçümle çürüttü:** "class5'te 2-3 kişi var" izlenimi →
kişi sayısı kuralı MCC **+0,203**, reddedildi.

---

## 3. `Safe_Walkway_Violation` — İKİNCİ KEZ RET

Ölçek-değişmez ölçüt (`ayak_mesafe / kutu_yüksekliği`) **çerçeve kısayolunu
gerçekten kapattı**:

| | 1. deneme | 2. deneme |
|---|---|---|
| A_GENİŞ içinde MCC | +0,117 | **+0,612** |
| dejenerelik ("ihlal" deme oranı) | 0,93 | 0,47 |
| CMH katmanlı p | 0,0546 | **0,0005** |

Birincil ölçüt ve dejenerelik kapısı **geçildi**.

**Ama plasebo kapısı çöktü, ve sebebi öldürücü:**

- Gerçek maskenin **dikey aynası** +0,655 veriyor (gerçeğin **%107'si**), kendi
  null'una karşı da anlamlı (p=0,0045)
- **Maskeyi tamamen atıp** yalnızca kişilerin görüntüdeki y-yayılımına bakınca **+0,582**
- Yani **maskenin tüm katkısı +0,030** — 30 klipte gürültü

**Ajanın kendi ifadesi:** *"İlk deneme ÇERÇEVE kısayoluydu; bu deneme KONUM
kısayolu. Bir karıştırıcıyı kapattım, altından ikincisi çıktı."*

Elenen açıklamalar (ölçüldü, ayırmıyor): saf hareket (48/48 klipte yürüyen var →
MCC 0,000), kare başı kişi sayısı, izlek sayısı, maks izlek hareketi.

Ajan kendi üç hatasını da bildirdi: ızgarayı 80 ilan etmiş ama 53'ü ayırt edilebilir;
hareket kapısı tamamen atıl; kayırıcı bir testin sonucunu kullanmayı **reddetti**.

---

## 4. Veri seti kusuru — projeyi ilgilendiriyor

Bu veride **ağır kodlama/oturum sızıntısı** var:

| sızıntı | ayırma gücü |
|---|---|
| bit hızı (taşıma sınıfları) | **MCC +1,000** — hiç örtüşme yok |
| konteyner fps (müdahale sınıfları) | **MCC +0,851** |
| dosya boyutu | +0,923 |
| çerçeve kimliği (müdahale sınıfları) | +0,618 |

**Sonuç:** bu veride eğitilen herhangi bir sınıflandırıcı **hile yapabilir**, ve
görsel gibi görünen herhangi bir ölçüm şişkin olabilir.

### Benimsenen yeni yöntem — yeniden kodlama kontrolü

Doğrulayıcı ajanın icat ettiği test artık standart: bir kural iddia edildiğinde
klipler **ortak spesifikasyona yeniden kodlanıp** ölçüm tekrarlanır. Forklift kuralı
bu testten geçti (+0,783 → +0,783); geçmeyen bir kural kodlama izini ölçüyordur.

---

## 5. Uçtan uca doğrulama — pano dedektörü boru hattında

`benchmark/eval_clips.py` · 197 klip · aynı model/ayar · yalnızca `panel_roi` farkı
(künyeye eklendi, ara-kayıt izolasyonu sağlandı).

| metrik | taban | **pano açık** | fark |
|---|---|---|---|
| **`isg_özgül` TP** | **1**/99 | **15**/99 | **+14** |
| **`isg_özgül` FP** | 0/98 | **0**/98 | 0 |
| normal klipte olay | 24/98 | 27/98 | +3 |
| tetiklenen normal klip | 5/98 | 7/98 | +2 |

**McNemar (eşli, n=99): taban-only=1 · pano-only=15 · iki yönlü p = 5,19e-04.**

`isg_özgül`, koşumlar arası **birebir kararlı** olduğu ölçülen tek sütundur; `recall`
aynı yapılandırmada +-12 puan salınıyor, bu yüzden karar metriği olarak kullanılmadı.

---

## Karar tablosu

| sınıf | karar | dürüst sayı |
|---|---|---|
| `Opened_Panel_Cover` | **KABUL** (görüş kilidiyle) | uçtan uca özgül 1→15/99 · FP 0/98 · p=5,2e-04 |
| `Carrying_Overload` | **KABUL** | LOO MCC **+0,718** · özgüllük 25/25 · tesis çapında **0/172 FP** |
| `Unauthorized_Intervention` | **ŞARTLI** | iç-grup MCC ~**+0,644** (manşet +0,843 şişkin) |
| `Safe_Walkway_Violation` | **RET** (2. kez) | maskenin katkısı +0,030 = gürültü |

**Dört sınıfın ikisi sağlam çözüldü, biri şartlı, biri bu veride çözülemiyor.**
