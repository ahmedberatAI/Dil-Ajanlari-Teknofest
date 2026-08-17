# `eval_defense` — NİHAİ VERİ DENETİMİ (D36)

Üç bağımsız yöntemin sonucu: **görsel denetim** (kontak sayfalarına doğrudan bakma),
**piksel düzeyinde zamansal hizalama** (200×200 çift), **metadata adli incelemesi**.

---

## 🔴 BULGU 1 — Aynı görüntü, ZIT etiket. Üç mutlak çelişki.

Piksel düzeyinde zamansal hizalama (gürültü tabanı ölçülerek, null kontrolüyle):

| kısa klip | uzun klip | ilişki |
|---|---|---|
| `Normal/Safe_Walkway/4_te16` (7,05 sn) | `Anomali/Safe_Walkway_Violation/0_tr13` | **%100 içinde** |
| `Normal/Safe_Walkway/4_tr8` | `Anomali/Opened_Panel_Cover/2_tr119` | **%100 içinde** |
| `Anomali/Opened_Panel_Cover/2_tr104` (7,00 sn) | `Normal/Authorized_Intervention/5_te5` | **%100 içinde** |

Kısa klipte görülen **her şey** uzun klipte de var, ama etiketler zıt.
**Tutarlı davranan bir model bu çiftlerin birinde ZORUNLU olarak yanılır.**
Yani raporlanabilir MCC'nin üst sınırı 1,0 değildir.

Toplam: **12 çapraz çift · 20 klip (%10) · 47,1 sn piksel-özdeş ortak görüntü.**
Ölçüt `med_MAD < 0,50`; gürültü tabanı medyanı 0,476, null kontrol 5–30× daha yüksek.
Eşik duyarlılığı düz (0,33→25 çift, 0,50→26, 0,75→27) — eşik sonuca göre seçilmemiş.

### Bunu ben de görsel olarak yakalamıştım

`4_te16` klibini bağımsız olarak denetlemiş ve *"puslu bölge var ama emin değilim"*
diye BELİRSİZ işaretlemiştim. Meğer bu klip **bütünüyle bir GÜVENSİZ klibin içinde**.
İki yöntem aynı klipte buluştu.

---

## 🔴 BULGU 2 — `Opened_Panel_Cover` görsel olarak ÇÖZÜLEMEZ

Doğrudan karşılaştırma yapıldı (`scratchpad/pano_test.jpg`):

| sınıf | güvenlik | pano durumu |
|---|---|---|
| class2 `Opened_Panel_Cover` | **GÜVENSİZ** | **AÇIK** |
| class5 `Authorized_Intervention` | **GÜVENLİ** | **AÇIK** |
| class6 `Closed_Panel_Cover` | GÜVENLİ | KAPALI |

**class2 ve class5'te pano durumu AYNI.** Ayırt edici işaret panoda değil:
class5'te **hi-vis yelekli yetkili kişi** panoda çalışıyor; class2'de pano açık
ama başında yetkili yok.

Ölçüm bunu bağımsız doğruladı: `2_tr104` (class2) ⊂ `5_te5` (class5) — **aynı görüntü.**

### Sonucu

`Opened_Panel_Cover` recall'ünün **%8** olması bir model zayıflığı DEĞİL:

- Salt pano dedektörü bu iki sınıfı **ayıramaz** (ikisinde de pano açık).
- Ayrım **bileşimsel akıl yürütme** gerektirir: *açık pano **VE** başında yetkili
  (yelekli) kişi yok*.
- D33'te `guided_choice` ile 20/20 "KAPALI" çıkması ayrı ve **gerçek** bir algı
  sınırıdır — ama düzeltilse bile sınıf yine çözülmez.

**Karar:** `Opened_Panel_Cover` için tek başına dedektör yatırımı yapılmamalı.

---

## 🟢 BULGU 3 — Düşük MCC'nin sebebi görsel kısayol EKSİKLİĞİ (iyi haber)

| ölçüt | değer | anlamı |
|---|---|---|
| AUC(aynı etiket > farklı etiket), arka plan | **0,538** | Anomali ve Normal görsel olarak **ayrışmıyor** |
| AUC(aynı etiket), hareket artığı | 0,516 | aynı sonuç |
| AUC(aynı **sınıf**) | 0,792 | sınıf (çekim oturumu) ayrışıyor |

Yani *"Normal taraf başka yerde çekilmiş, model kolay ayırıyor"* türü bir kısayol **YOK**.
Belgelerdeki *"aynı sahne, aynı kamera, fark yalnızca davranış"* iddiası **sayıyla
doğrulandı**. Setin zorluğu **meşru**.

Görsel denetimim de aynı yere çıkmıştı: hassasiyet 0,560 ve MCC +0,069 büyük ölçüde
**gerçek**; ölçüm sisteme haksızlık etmiyor.

---

## 🔴 BULGU 4 — Bu set EĞİTİM/İNCE AYAR için KULLANILAMAZ

| kısayol | ölçüm |
|---|---|
| Arka plan imzası → 1-NN etiket | **%76,0** (şans %49,7) |
| Arka plan imzası → 1-NN sınıf | %61,0 (şans %12,1) |
| **Yalnız encoder metadata'sı → etiket** | **%65,0** (şans %50) |
| Bit hızı → Anomali AUC | 0,690 |

**Sınıf ↔ dışa-aktarma oturumu birebir örtüşüyor:** class3 %100 CPU-encode,
class7 %100 HS (yeniden kodlamasız kopya). **Sınıf ↔ kamera örtüşüyor:**
class3/class7 yalnızca 2. kamerada, class2/class6 yalnızca 1. kamerada.

Bir model bu sette ince ayar yapılırsa **davranışı değil, dosyanın nasıl kesildiğini**
öğrenir. `HANDOFF.md:213-214` uyarısı bu ölçümle **kanıtlandı**.

---

## 🔴 BULGU 5 — `Normal` tehlikesiz değil (görsel denetim, 8/22 klip)

`Normal` klipleri "tehlikesiz sahne" değil, **"belirli bir güvenli davranışın
etiketlendiği sahne"**. Karedeki diğer her şey etiketsiz.

| # | klip | model | gördüğüm | karar |
|---|---|---|---|---|
| 1 | `6_tr5` | *"yere düşmüş hareketsiz kişi"* Kritik | zeminde **metal halka**, kimse yok | ❌ halüsinasyon |
| 2 | `4_tr7` | *"paneli açtı"* | operatör panelinde, pano kapalı | ❌ aşırı yorum |
| 3 | `4_te16` | *"yoğun duman"* Kritik | pus var ama belirsiz — **ayrıca etiket çelişkili** | ⚠️ |
| 4 | `7_te6` | *"forklift yolunu kesen kişi"* | çakışma yok | ⚠️ |
| 5 | `5_te6` | *"üniformasız kişi"* | **yeleksiz sivil kıyafetli kişi VAR** | ✅ gerçek, etiketsiz |
| 6 | `6_te11` | (olay) | pano kapalı, rutin | ❌ |
| 7 | `5_te11` | *"mavi tişörtlü hızlı hareket"* | rutin yürüme | ❌ |
| 8 | `5_te13` | *"yerde nesne + patlama izleri"* | **metal halka gerçek**, patlama izi uydurma | ⚠️ kısmen |

**8 klipte:** 1 kesin halüsinasyon · 3 aşırı yorum · 3 belirsiz/kısmen · **1 gerçek**

### "200 klipte 13 düşme" bilmecesi çözüldü

Zeminde duran **metal halka/bobin**, tepeden çekimde koyu ve yaklaşık insan boyutunda.
Model onu tekrar tekrar "düşmüş kişi" sanıyor. Halka **hem Anomali hem Normal**
kliplerde duruyor → ayırt edici değil, iki tarafta da gürültü üretiyor.

---

## Nihai karar — veri seti hazır mı?

| boyut | durum |
|---|---|
| Lisans / Apache 2.0 uyumu | ✅ **hazır** — kapı fail-closed test edildi |
| Nicelik (200 + 1.100 + ~75k) | ✅ **yeterli** |
| Bayt düzeyinde mükerrer | ✅ **temiz** (200 benzersiz MD5) |
| Görsel kısayol / kolaycılık | ✅ **yok** — zorluk meşru |
| **Sahne düzeyinde sızıntı** | 🔴 **%10 klip, 3 mutlak çelişki** |
| **Sınıf ↔ oturum/kamera karışması** | 🔴 **var** — eğitimde kullanılamaz |
| **`Opened_Panel_Cover` çözülebilirliği** | 🔴 **görsel olarak çözümsüz** |
| **`Normal` = tehlikesiz varsayımı** | 🔴 **yanlış** — düzeltildi |

**Özet:** Veri **değerlendirme için kullanılabilir ve zorluğu meşru**, ama
**kusursuz değil ve kusursuz hale getirilemez** — çelişkiler kaynak veri setinin
tek-etiketli şemasından geliyor.

## Yapılması gerekenler (öncelik sırasıyla)

1. **Üç mutlak çelişkili çiftten birer klip setten çıkarılmalı** veya en azından
   manifeste işaretlenmeli. Aksi halde MCC'nin tavanı sessizce 1,0'ın altında kalır.
2. **`Opened_Panel_Cover` ayrı raporlanmalı** — bu sınıftaki başarısızlık model
   kusuru olarak sunulmamalı, veri kusuru olarak sunulmalı.
3. **Eğitim yasağı koda bağlanmalı:** `data/eval_defense` ve `data/industrial`
   `veri_lisans.py` benzeri bir kapıyla ince ayara karşı korunmalı (şu an yalnız
   belgede uyarı var).
4. Kalan 14 Normal klip + 20 KKD klibi denetlenmeli (oranları sayısallaştırır).
