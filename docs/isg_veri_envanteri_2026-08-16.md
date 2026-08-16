# İSG veri envanteri ve arama kaydı — D35

**Tarih:** 2026-08-16
**Amaç:** "İSG veri setimiz tam mı?" sorusuna **kanıtlı** cevap; ve aynı aramaların
bir daha sıfırdan yapılmaması.

> **Kural (bu belgenin varlık sebebi):** bir kaynak elendiyse **neden** elendiği
> sayısıyla yazılır. Aksi halde üç ay sonra biri aynı seti yeniden bulur, yeniden
> indirir ve yeniden elenir.

---

## 0. Kısa cevap: **HAYIR, tam değil**

| Tehlike | Durum |
|---|---|
| Yürüme yolu ihlali · yetkisiz müdahale · açık pano · forklift aşırı yük | ✅ var (691 klip, tek tesis) |
| **Baret** (KKD) | ✅ dedektör dağıtıma hazır (mAP50 0,934) — ama **bu tesiste baret takılmıyor** |
| **Yelek** (KKD) | 🟡 veri 88× arttı, yeniden eğitiliyor |
| **Yüksekten düşme** | ❌ **izin verici lisanslı açık veri BULUNAMADI** |
| Forklift–yaya çakışma | 🟡 yalnızca forklift+kişi tespiti var, çakışma etiketi yok |
| Makine sıkışma · LOTO · kapalı alan · kimyasal | ❌ bulunamadı |
| **Tesiste KKD ground-truth** | ❌ yok — etiketleme paketi hazır, insan gerekli |

---

## 1. Lisans süzgeci — neyin neden elendiği

**Eğitimde kullanılabilir:** CC BY 4.0 · CC0 · MIT · Apache-2.0
**Eğitimde KULLANILAMAZ:** CC BY-NC-SA · CC BY-NC · CC BY-NC-ND · AGPL-3.0 · GPL-3.0

Gerekçe: ShareAlike/copyleft, ince ayarda model ağırlıklarını türev eser yapabilir →
modelimiz de o lisansa mahkûm olur. NonCommercial ayrıca ticari geleceği kapatır.
Bu kural `dilajan/veri_lisans.py`'de **kod düzeyinde** zorlanır (fail-closed).

### Elenenler (tekrar önerilmesin)

| Aday | Lisans | Neden acı |
|---|---|---|
| **SH17** (8.099 görsel, 17 sınıf, **üretim sanayi**) | CC BY-NC-SA 4.0 | **Alan eşleşmesi EN İYİ adaydı.** Yalnızca lisans yüzünden elendi. |
| **VFP290K** (294.713 kare, 178 video, 49 konum) | **GPL-3.0** | Düşmüş-kişi tespitinde en büyük set; copyleft + indirmesi Google Sites portalı (otomatikleştirilemiyor) |
| Ultralytics Construction-PPE (1.416 görsel) | AGPL-3.0 | copyleft |
| iSafetyBench (1.100 klip) | CC BY-NC-SA 4.0 | ✅ **değerlendirmede kullanılıyor**, eğitimde yasak |
| `IswaryaS/Aerial-PPE-Construction-Safety` | CC BY-NC-ND 4.0 | NC + ND (türetme bile yasak) |
| `shangzx/Forklift-Loading`, `Mobiusi/Forklift-Loading` | CC BY-NC-SA 4.0 | copyleft |
| `UniDataPro/fall-detection`, `ud-smart-city/fall-detection` | CC BY-NC-ND 4.0 | NC + ND |

---

## 2. Alınanlar

| Set | Lisans | Lisans nereden teyitli | İçerik |
|---|---|---|---|
| `data/industrial` | CC BY 4.0 | Mendeley `data_licence` alanı | 691 klip, 8 sınıf, 1080p |
| `data/isafety_bench` | CC BY-NC-SA 4.0 | LICENSE dosyasının kendisi | 1.100 klip — **yalnızca değerlendirme** |
| `data/ppe/hard_hat` | CC BY 4.0 | HF dataset kartı | 19.745 görsel · hardhat/no-hardhat |
| `data/ppe/construction_safety` | CC BY 4.0 | HF dataset kartı | 398 görsel · 17 sınıf |
| `data/ppe/gsnvb_vest` | CC BY 4.0 | kaynağın `data.yaml` → `roboflow.license` | 1.206 görsel · vest/no-vest |
| `data/ppe/mendeley_5sinif` | CC BY 4.0 | Mendeley `data_licence` alanı | 2.585 görsel · 5 sınıf |

### Türetilmiş eğitim setleri

| Set | Sınıf | Kutu |
|---|---|---|
| `data/ppe_yolo` | `baret_var` / `baret_yok` | 55.937 (eğitim: 39.082) |
| `data/yelek_yolo` | `yelek_var` / `yelek_yok` | **7.963** (eğitim: 6.390) |

**Mükerrer denetimi yapıldı:** gsnvb ↔ mendeley arasında **0 ortak MD5**
(Roboflow `.rf.` içerik hash'inde de 0). Mendeley'nin kendi içindeki **31 kopya
elendi**; bölme **dedup'tan SONRA** yapıldı → eğitim/test sızıntısı yok (K10).

---

## 3. Yüksekten düşme — arama kaydı (**sonuç: yok**)

En ölümcül İSG kategorisi ve bizde **sıfır** kapsam var. Elimizdeki düşme
verileri (GMDCSA-24, URFD) **ev/laboratuvar** ortamı — işyeri değil.

**Aranan yerler ve sonuç:**

- **HuggingFace** (`fall detection` araması, 19 set): **hepsi ev/yaşlı odaklı.**
  Hiçbiri işyeri/inşaat/merdiven/iskele/yükseklik içermiyor.
  İzin verici olanlar (`kamalchibrani` apache-2.0, `DeZan` mit, `Simuletic` cc-by-4.0)
  bizim zaten sahip olduğumuz türden veri — **yeni kapsam eklemiyorlar**.
- **VFP290K** — en büyük düşmüş-kişi seti, ama **GPL-3.0** (yukarıda).
- **Zenodo / Mendeley** — inşaat güvenliği setleri var ama **KKD ve nesne tespiti**
  odaklı; yüksekten düşme **video** seti çıkmadı.
- Literatürde yüksekten düşme çalışmaları çoğunlukla **IMU/giyilebilir sensör**
  verisi kullanıyor (kamera değil) — bizim mimarimize uymuyor.

> **Sonuç:** Bu boşluk **açık veriyle kapatılamıyor.** Seçenekler:
> (a) kapsam dışı olduğunu açıkça beyan etmek,
> (b) sahnelenmiş (acted) kendi verimizi üretmek — *ama* projede sentetik/donmuş
> veri kullanmanın acı bir geçmişi var (HANDOFF K8: tek PNG'nin video diye
> sarılması), o yüzden üretilirse **gerçek hareket** şartı aranmalı,
> (c) lisansı uygun ticari/kurumsal bir kaynakla anlaşmak.

---

## 4. Forklift–yaya çakışma (**kısmi**)

| Aday | Lisans | Not |
|---|---|---|
| `keremberke/forklift-object-detection` | **CC BY 4.0** | 421 görsel (295/84/42), sınıflar: forklift, person |
| `HuyButter/Forklift-Person-Dataset` | Apache-2.0 | ⚠️ kart **boş**, görüntüleyici bozuk, içerik doğrulanamadı |
| `bsebench-org/aalborg-forklift-...` | CC BY 4.0 | ham sensör verisi (LFP), kamera değil |

**Çakışma/ramak-kala etiketli veri YOK.** Ama bu zaten doğru mimari değil:
forklift+kişi kutuları üzerine **deterministik yakınlık kuralı** koymak gerekir —
`restricted_zones` geofence'iyle aynı desen, VLM yargısı değil.

⚠️ **421 görsel muhtemelen yetersiz.** Yelek deneyi bunu pahalıya öğretti:
741 kutuyla eğitilen sınıf P=0,72 verdi ve **dağıtılamadı**. Aynı hatayı
tekrarlamamak için bu set **indirilmedi/eğitilmedi** — önce daha fazla forklift
verisi bulunmalı.

---

## 5. Makine sıkışma · LOTO · kapalı alan · kimyasal

Bu alanlarda **hiçbir açık veri seti bulunamadı.** Aranan terimler:
machine guard bypass, lockout-tagout detection, confined space entry monitoring,
chemical spill detection dataset, machine entrapment video.

Bulunanlar ya genel inşaat KKD setleri ya da metin/rapor tabanlı (kaza raporu)
veri; **video/görüntü tespiti** için kullanılabilir bir şey yok.

---

## 6. Kapatılabilecek en ucuz boşluk: **tesiste KKD ground-truth**

Dış veri gerektirmiyor, GPU gerektirmiyor, ~20 dakika insan işi.
Paket hazır: `scripts/ppe_etiket_hazirla.py` → `data/ppe_tesis_etiket/`

Üç kova (A ihlal · B kurallı · C boş) — **C kovası recall için şart**, atlanırsa
yalnızca precision ölçülür. Yakınlaştırılmış kırpmalar üretiliyor çünkü tesis
kamerasında kafa ~20-30 piksel ve tam kare üzerinden insan karar veremiyor.

Bu tamamlanmadan `ppe_dispatch` açılmamalıdır.
