# `eval_defense/Normal` görsel denetimi — D36

**Denetleyen:** oturum içinde kontak sayfalarına doğrudan bakılarak (2×2 @760px, en-boy korunmuş).
**Kapsam:** olay üreten 22 Normal klipten **6'sı incelendi**. Kalan 16 için kontak sayfaları
hazır (`scratchpad/denetim/`), aynı yöntemle tamamlanabilir.
**Amaç:** 22 operasyonel yanlış-pozitif gerçek tehlike mi, halüsinasyon mu? Hassasiyet
(0,560) ve MCC (+0,069) olduğundan düşük mü ölçülüyor?

---

## 🔴 EN ÖNEMLİ BULGU — yapısal, tek tek kliplerden bağımsız

**`Normal` klipleri "tehlikesiz sahne" DEĞİLDİR; "belirli bir güvenli davranışın
etiketlendiği sahne"lerdir. Karedeki diğer her şey etiketsizdir.**

İncelenen dört klip — `Safe_Walkway/4_tr7` (class4), `Closed_Panel_Cover/6_tr5` (class6),
`Closed_Panel_Cover/6_te11` (class6), `Authorized_Intervention/5_te6` (class5) —
**AYNI kamera, AYNI makine, AYNI zeminde duran metal halka**. Farklı sınıf etiketleri
taşıyorlar ama fiziksel sahne aynı.

Yani sınıflar ayrı sahneler değil; **aynı çalışma alanının, hangi davranışa bakıldığına
göre farklı etiketlenmiş halleri.**

Sonucu: `benchmark/labels.py:68`'deki
> `"Normal": "OLAGAN faaliyet — kayda deger hicbir guvenlik olayi YOK"`

iddiası **veri tarafından desteklenmiyor.** Kaynak yalnızca "class4-7 = bu dört davranışın
güvenli hali" der. Bu satır düzeltilmelidir.

---

## Klip klip karar

| # | klip | modelin iddiası | gördüğüm | karar |
|---|---|---|---|---|
| 11 | `Closed_Panel_Cover/6_tr5` | *"Yere düşmüş hareketsiz bir kişi"* · **Kritik** · 4 fonksiyon | Yerde **kimse yok**. Ortadaki nesne **metal halka/bobin**. İşçiler ayakta, normal yürüyor. | ❌ **HALÜSİNASYON** |
| 22 | `Safe_Walkway/4_tr7` | *"İşçi makinenin panelini açtı ve içeriye eğildi"* | İşçi **operatör panelinde** duruyor (HMI ekranı). Açık pano kapağı görünmüyor. Yeşil yaya şeridi düzgün kullanılıyor. | ❌ **AŞIRI YORUM** |
| 17 | `Safe_Walkway/4_te16` | *"Makinelerden yoğun duman çıkıyor"* · **Kritik** | Makine çevresinde **puslu bir bölge var** ama buhar mı, ışık yansıması mı ayırt edilemiyor. Yaya yeşil şeritte, davranış doğru. | ⚠️ **BELİRSİZ** |
| 13 | `Safe_Carrying/7_te6` | *"Forklift yolunu kesen kişi"* | Forklift kasa taşıyor, kişi farklı bölgede. Örneklenen 4 karede **çakışma yok** (kısa geçiş kaçmış olabilir). | ⚠️ **BELİRSİZ / TEMİZ** |
| 4 | `Authorized_Intervention/5_te6` | *"Yetkisiz giriş: güvenlik üniforması olmayan kişi üretim alanına girdi"* · **Yüksek** | Hi-vis yelekli işçi makinede çalışıyor (**pano AÇIK** — etiketle tutarlı). **AMA** ayrı bir karede **yeleksiz, sivil kıyafetli** bir kişi üretim alanında yürüyor. | ✅ **GERÇEK ama ETİKETSİZ** |
| 6 | `Closed_Panel_Cover/6_te11` | (olay üretti) | Pano **kapalı** (etiketle tutarlı). İşçi rutin çalışıyor. Bir kişi sarı çizgiyi geçerek yürüyor. | ❌ **muhtemelen YANLIŞ-POZİTİF** |

**İncelenen 6 klipte:** 1 kesin halüsinasyon · 2 aşırı yorum/YP · 2 belirsiz · **1 gerçek ama etiketsiz tehlike**

---

## Üç yan bulgu (hepsi ölçümü etkiliyor)

### 1. "Yere düşmüş kişi" iddiaları halüsinasyon — sebebi de bulundu

200 klipte 13 düşme iddiası vardı ve fizyolojik olarak inandırıcı değildi.
`6_tr5`'te sebep net görüldü: **zeminde duran metal halka/bobin**, tepeden çekimde
koyu ve yaklaşık insan boyutunda. Model bunu tekrar tekrar "düşmüş kişi" sanıyor.

Aynı halka **birçok klipte** duruyor — hem Anomali hem Normal tarafta. Yani
ayırt edici değil, ama **her iki tarafta da yanlış olay üretiyor**.

### 2. Açık pano GÖRSEL OLARAK tespit edilebilir — D33'ün bulgusu doğrulandı

`5_te6`'da makinenin yan panosunun açık olduğunu **ben net görebiliyorum**. Yani
VLM'in `Opened_Panel_Cover` sınıfında 20/20 "KAPALI" demesi görüntü kalitesinden
değil — **gerçek bir model algı sınırı**. Deterministik dedektör kararı doğru.

### 3. Metal halka aslında gerçek bir İSG tehlikesi olabilir

Yaya geçiş güzergâhının yakınında zeminde duran büyük metal nesne = takılma tehlikesi.
Model bunu bazen "yolu kesen malzeme" diye doğru adlandırıyor. Ama nesne **hem güvenli
hem güvensiz kliplerde** olduğu için sınıf ayrımına katkı sağlamıyor; yalnızca gürültü
üretiyor.

---

## Ölçüme etkisi — dürüst değerlendirme

**Beklentimin aksine, denetim hassasiyeti YUKARI çekmiyor.**

İncelenen 6 klibin yalnızca **1'i** (`5_te6`) "gerçek ama etiketsiz tehlike" olarak
savunulabilir. 3'ü modelin hatası. 2'si belirsiz.

Bu oran 22'ye genellenirse (⚠️ n=6, Wilson %95 GA çok geniş: %1–%64) düzeltme
**birkaç puanı geçmez**. Yani:

> **Hassasiyet 0,560 ve MCC +0,069 büyük ölçüde GERÇEK.**
> Sistem yanlış alarm üretiyor; ölçüm haksızlık etmiyor.

Bu, ölçümü savunmak açısından **iyi haber** (rakamlarımız dürüst), performans açısından
**kötü haber** (iyileştirilecek yer gerçekten modelde/boru hattında).

---

## Veri setine dair karar

| soru | cevap |
|---|---|
| `Normal` seti kirli mi? | **Kısmen** — tehlikesiz değil, "belirli davranışı güvenli" |
| Ölçüm haksız mı? | **Hayır** — düzeltme birkaç puan, yön değişmiyor |
| `labels.py:68` doğru mu? | **HAYIR** — düzeltilmeli |
| Yeni veri toplanmalı mı? | Bu bulguya göre **hayır**; sorun veride değil boru hattında |

## Yapılacaklar

1. `benchmark/labels.py:68`'deki "hiçbir güvenlik olayı YOK" iddiasını gerçeğe uydur.
2. Kalan 16 klibi aynı yöntemle denetle (kontak sayfaları hazır) — oranı n=22'ye taşır.
3. Zemindeki metal halkayı **bilinen sahne öğesi** olarak belgele; "düşmüş kişi"
   halüsinasyonlarının tek kaynağı bu.
