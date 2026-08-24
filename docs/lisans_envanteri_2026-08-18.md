# Lisans envanteri ve Apache-2.0 uyumu (D39-A)

**Tarih:** 2026-08-18 · **Deponun lisansı:** Apache-2.0 (`LICENSE`)
**Yarışma şartı:** kod, veri ve bileşenler (ağırlıklar dahil) Apache-2.0

> Hukuki hüküm değildir. Olgular ölçüldü ve kaynağı gösterildi; karar proje ekibinindir.

## Bulgu

`requirements.txt`'teki **14 paketin 13'ü izin verici**. Tek sorunlu:

| paket | sürüm | lisans | durum |
|---|---|---|---|
| **ultralytics** | 8.4.72 | **AGPL-3.0** | ⚠ **zorunlu olmaktan çıkarıldı** |

Doğrulama:
```
importlib.metadata.metadata("ultralytics")["License"]  ->  'AGPL-3.0'
classifier: License :: OSI Approved :: GNU Affero General Public License v3 or later
```

**Uyumluluk tek yönlüdür:** Apache-2.0 kod AGPL projeye girebilir; **AGPL kod
Apache-2.0 olarak yeniden lisanslanamaz.**

### Olgu düzeltmesi

`requirements.txt`'teki eski not *"vLLM zaten bağımlı olarak çekiyor olabilir"*
diyordu. **Yanlış.** `pip show ultralytics` → `Required-by:` **boş**;
vLLM 0.23.0'ın bağımlılıklarında ultralytics yok. Satırı kaldırmak paketi
temiz ortamda gerçekten kaldırıyor.

## Yapılan (S2 — dağıtımı temizle, ölçümleri koru)

1. `ultralytics` **`requirements.txt`'ten çıkarıldı** → yeni `requirements-kkd.txt`
   (opsiyonel, dosyanın başında AGPL uyarısıyla).
2. `transformers>=5.0` **açıkça beyan edildi** (yeni kod doğrudan ithal ediyor).
3. **`kkd_available()` onarıldı** — bkz. aşağıdaki gerçek hata.
4. Yeni yetenekler `detector.py`'ye **eklenmedi**; Apache-2.0 yolundan gidiyor:
   - `dilajan/algila_rtdetr.py` → **RT-DETRv2** (`PekingU/rtdetr_v2_r50vd`, Apache-2.0)
   - `dilajan/pano.py` → parlaklık yolu yalnızca **numpy**

### Çekirdek dağıtım ultralytics'siz ne kaybeder

| yetenek | durum |
|---|---|
| KKD kitleri (baret mAP50 0,934 · yelek 0,905) | kapalı |
| `verify_pose_falls` (poz ile düşme doğrulaması) | kapalı |
| `restricted_zones` · `detect_vehicles` · `detect_crowd` | kapalı |
| **VLM boru hattı, pano dedektörü, diyalog, rapor** | **çalışır** |

Ölçülmüş KKD değerleri **geçerli kalır** (ağırlık değişmedi); yalnızca varsayılan
olarak kapalıdır.

## Yan bulgu — gerçek hata (D39-D), lisanstan bağımsız

`kkd_available()` yalnızca **dosya varlığına** bakıyordu. ultralytics kurulu
değilken:

1. `kkd_available()` → **True**
2. `_get_kkd_model()` → ImportError
3. `detect_ppe_violation()` → **fail-open, `None`**
4. Sistem **"KKD hazır"** der, hiçbir şey tespit etmez, **karar izine de yazmaz**

Onarım — üç fonksiyona ayrıldı:

| fonksiyon | sorumluluk |
|---|---|
| `kkd_agirlik_var(kit)` | yalnızca dosya varlığı |
| `kkd_neden_yok(kit)` | kullanılamıyorsa **sebep** (Türkçe), yoksa `None` |
| `kkd_available(kit)` | `kkd_neden_yok(kit) is None` |

`graph.py` artık sebebi **karar izine yazıyor**:
`⚠ KKD kiti 'baret' KULLANILAMIYOR — ...; bu kit için tespit YAPILMADI`

K3 (fail-open) korundu, ama **sessizlik kaldırıldı**.

## Kalan açık: KKD ağırlıklarının türev durumu

`yolo11n-ppe.pt` / `yolo11n-yelek.pt`:

- **(a) Biçim:** pickle içinde `ultralytics.nn.modules.conv` GLOBAL opcode'ları var
  → paket olmadan **açılamazlar**
- **(b) Türev:** `scripts/train_ppe.py --model yolo11n.pt` ile, yani Ultralytics'in
  **AGPL ön-eğitimli ağırlığından** ince ayar. **Eğitim verisi temiz** (CC BY 4.0),
  başlangıç ağırlığı değil.

Ayrıca bu ağırlıklar `paylasim/agirliklar/` içinde **arkadaşlara dağıtıldı**.

### Seçenekler (ölçülmüş maliyetle)

| | GPU | mühendislik | ölçümlerimiz |
|---|---|---|---|
| **S2 (uygulandı)** — opsiyonel extra | 0 | ~yarım gün | **korunur** |
| S5 — RT-DETR kişi kutusu + SigLIP2 sınıflandırıcı | <1 sa | ~1 gün | yeni ölçüt gerekir |
| S3 — RT-DETRv2'den sıfırdan eğit | 7-15 sa | **2-3 gün** | **hepsi geçersizleşir** |
| S6 — yalnızca biçim dönüşümü | 0 | ~1 gün | **(b)'yi ÇÖZMEZ** |

S3'ün asıl maliyeti GPU değil: `transformers`'ta hazır tespit eğitim döngüsü
**yok**; döngü + COCO dönüşümü + mAP değerlendirmesi yazılmalı. Veri hazır
(baret 14.089 görsel / 39.082 kutu · yelek 3.185 kutu).

S5 için dürüst çekince: yelek (gövde, büyük alan) için makul; **baret için
kırpıntı çok küçük** — ölçülmeden varsayılamaz.

## Apache-2.0 güvenli liste (doğrulandı)

Tespit **RT-DETR/RT-DETRv2 · D-FINE · RF-DETR · YOLOX · MMDetection** ·
Görsel-dil **SigLIP-2 · DINOv2 · Qwen3-VL** · Poz **ViTPose** ·
Açık-sözcük **Grounding DINO · OWLv2** · Takip **ByteTrack/BoT-SORT/OC-SORT** (MIT)

**Kaçınılacaklar:** Ultralytics YOLO (AGPL-3.0) · YOLO-World (GPL-3.0) ·
VideoMAE ağırlıkları (CC BY-NC) · DINOv3 (kısıtlı) ·
Safe-Construct (CC BY-NC-SA) · CMA veri seti (yalnızca araştırma)

## Zaten yürürlükte olan kilit

`data/eval_defense` (iSafetyBench) **yalnızca değerlendirme**; eğitimde kullanımı
`dilajan/veri_lisans.py` ile **fail-closed** engelleniyor. CC BY-NC-SA 4.0'ın
ShareAlike şartı model ağırlıklarını türev esere çevirir ve Apache-2.0 şartıyla
çelişirdi. Bu kilit **korunuyor**.
