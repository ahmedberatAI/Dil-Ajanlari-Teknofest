# Veri Kaynakları, Envanter, Lisanslar ve İndirme

Bu proje **hiçbir video verisini depoda dağıtmaz** — tüm klipler aşağıdaki **herkese açık** kaynaklardan
indirme script'leriyle çekilir (`data/` dizini `.gitignore`'dadır). Her veri seti kendi lisansı altındadır;
proje kodu Apache-2.0'dır ancak veri setleri kendi orijinal lisanslarını korur (lisans zinciri net ayrık).

> Bu belgedeki envanter ve sınırlılık beyanları `docs/olcum_durustlugu.md` ile birebir tutarlıdır.
> Ölçüm sonuçlarının nasıl okunması gerektiği için o belgeye bakınız.

---

## 1. Envanter — kaç video, gerçekten?

Denetimde bulundu: dosya sayısı ile **benzersiz** video sayısı aynı değildi.
Aşağıdaki sayılar **2026-07-25 tarihli `ffprobe` + `md5sum` denetiminden**dir; setler
değiştikçe komutu yeniden koşarak doğrulayın.

| | Değer | Nasıl doğrulanır |
|---|---|---|
| `data/` altındaki video dosyası | 412 | `find data -type f \( -iname '*.mp4' -o -iname '*.avi' \) \| wc -l` |
| **Benzersiz video (MD5)** | **214** | `find … -exec md5sum {} + \| cut -c1-32 \| sort -u \| wc -l` |
| Birebir kopya (aynı dosyanın başka kopyası) | **198** | yukarıdaki iki sayının farkı |
| **Doğruluk ölçümüne giren benzersiz klip** | **140** | değerlendirme dizinleri, MD5-tekil, `_deprecated*` hariç |
| Bu kliplerin toplam süresi | **44.0 dakika** | `ffprobe` toplamı |

**Ham dosya sayısı (412 — denetim anındaki hâliyle 262) video sayısı olarak raporlanmamalıdır.**
Doğru beyan: **214 benzersiz video; ölçüme giren 140 benzersiz klip / 44.0 dakika.**
Kopyaların çoğu, aynı klibin birden fazla değerlendirme setinde yer almasından gelir
(ör. `eval_scenario/Fall` = `falls_real/Fall` + `falls_surveillance/Fall`;
`eval_defense/*` = `industrial/class*`); kalanı ham indirme artığı (`scenario/_dl/`, 49 dosya)
ve denenip kullanılmayan veridir (`nvidia/`, 27 dosya).

Yeniden üretim:

```bash
cd data
find . -type f \( -iname '*.mp4' -o -iname '*.avi' \) -exec md5sum {} + > /tmp/m.txt
wc -l < /tmp/m.txt                          # dosya sayisi
cut -c1-32 /tmp/m.txt | sort -u | wc -l     # benzersiz video
cut -c1-32 /tmp/m.txt | sort | uniq -d | wc -l   # mukerrer md5 grubu
```

### Bilinen mükerrerlikler ve set-sızıntısı

- **`Normal_Videos_936_x264.mp4` ≡ `Normal_Videos_937_x264.mp4`** — birebir aynı dosya
  (MD5 `88800dc18af0bc29d05aa74656b638bf`), hem `eval/Normal` hem `eval_big/Normal` içinde.
  Bu nedenle bu setlerin normal-yanlış-pozitif paydaları **8 ve 16 değil, 7 ve 15**'tir.
- **`data/eval`, `data/eval_big`'in %100 alt kümesiydi** — `eval`'deki 31 benzersiz MD5'in
  31'i de `eval_big`'in 63 benzersiz MD5'i içindeydi. Geçmişte kullanılan *"eval_big ile
  bağımsız büyük-n doğrulaması yaptık"* ifadesi bu yüzden **geri çekilmiştir**.
- **Düzeltme (uygulandı):** `eval_big` artık **ayrık** iki alt-kümeye bölünmüştür —
  `data/eval_tune` (31 benzersiz klip) ve `data/eval_holdout` (32 benzersiz klip);
  **kesişimleri sıfırdır** (MD5 ile doğrulandı) ve birleşimleri `eval_big`'i verir.
  Ayarlama/prompt geliştirme `eval_tune`'da, doğrulama `eval_holdout`'ta yapılmalıdır.
- **Eski `data/eval` dizini duruyor** (geriye dönük uyum için) ve hâlâ `eval_big`'in alt kümesidir.
  **`eval`'den çıkan sonuçlar bağımsız kanıt olarak raporlanmamalıdır.**
- **Yayınlanmış rakamlar tune/holdout ayrımından ÖNCE üretilmiştir.** Yani mevcut `eval_big`
  sonuçları hâlâ "ayarlamanın yapıldığı veriyle aynı veri" üzerindedir; temiz holdout ölçümü
  yeni bölünmeyle **yeniden koşulmalıdır**.

---

## 2. Kaynaklar ve lisanslar

| Veri seti | İçerik | Lisans (dürüst hâli) | Herkese açık link | İndirme |
|---|---|---|---|---|
| **FIRESENSE** | Yangın/duman + negatifler | CC BY 4.0 | https://zenodo.org/records/836749 | `scripts/get_firesense.py` (yeni — aşağıya bkz.) |
| **GMDCSA-24** | Gerçek düşme + ADL videoları | CC BY 4.0 | https://github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos | `scripts/get_gmdcsa.py` |
| **Eskişehir Endüstriyel (güvenli/güvensiz davranış)** | 1080p @24fps fabrika CCTV; 691 klip, ~10 GB; 4 GÜVENSİZ + 4 GÜVENLİ sınıf | Mendeley API'sinde **CC BY 4.0** — ⚠️ teslimden önce makaleden teyit edilecek | https://data.mendeley.com/datasets/xjmtb22pff/1 (DOI 10.17632/xjmtb22pff.1) | `scripts/get_industrial.py` · eşleme: `data/industrial/CLASSES.md` |
| **URFD (overhead düşme)** | Tavan/gözetim açısı gerçek düşme | Akademik/araştırma | http://fenix.ur.edu.pl/~mkepski/ds/uf.html | `scripts/get_urfd_overhead.py` |
| **Simuletic CCTV** | Tepeden-CCTV yerde-yatan kişi — **sentetik, tek kare** | CC BY 4.0 | https://huggingface.co/datasets/Simuletic/CCTV_Incident_Dataset_Fall_Lying_Down_Detection | `scripts/get_lying.py` |
| **UCF-Crime** | Gözetim anomali (dayanıklılık stresi) | ⚠️ **CC DEĞİL** — akademik/araştırma kullanımı; klipler **üçüncü-taraf HF aynasından** çekiliyor | https://www.crcv.ucf.edu/projects/real-world/ | `scripts/get_ucf_clip.py`, `get_ucf_many.py`, `get_normal_clips.py` |
| **NVIDIA PhysicalAI Warehouse** | 1080p sentetik depo (denendi, **kullanılmadı**) | OpenMDW 1.1 | https://huggingface.co/datasets/nvidia/PhysicalAI-WorldModel-Synthetic-Warehouse-Operations-Scenes | (deney; manuel) |

### Lisans uyumu — açık beyan
- **Kod:** Apache-2.0 (`LICENSE`). **Model:** Qwen3-VL-8B-Instruct(-FP8) — Apache-2.0.
- **Veri depoya gömülü değildir**; yalnızca indirme script'leri + bu manifest dağıtılır.
- **UCF-Crime bir Creative Commons veri seti DEĞİLDİR.** UCF CRCV tarafından **akademik/araştırma**
  kullanımı için sunulur; yeniden dağıtım yapmıyoruz. Ayrıca kliplerimizi resmî sayfadan değil,
  **üçüncü-taraf bir HuggingFace aynasından** (`ertiaM/Anomaly_Detection_in_Surveillance_Videos`)
  çekiyoruz — bu aynanın sürekliliği ve yetkisi bizim kontrolümüzde değildir. Tekrar-üretilebilirlik
  açısından bu bilinen bir kırılganlıktır.
- **Eskişehir seti:** Mendeley genel API'si (`data.mendeley.com/public-api/datasets/xjmtb22pff`)
  lisansı **CC BY 4.0** olarak bildiriyor ve `scripts/get_industrial.py` bunu esas alıyor.
  İlgili yayında **CC BY-NC** geçme ihtimali vardır; **teslimden önce makale metninden teyit edilecektir.**
  Set gerçek bir tesisten izinli toplanmıştır (Kafaoğlu A.Ş.); demo/sunumda gizlilik gereği
  yüz/kimlik vurgusu yapılmaz.

### Kapatılan tekrar-üretilebilirlik boşluğu: FIRESENSE
Yarışma "herkese açık link + tekrar üretilebilirlik" istiyor. **Denetim anında FIRESENSE için
indirici script yoktu** — oysa en iyi başlık rakamlarımızın bir kısmı (yangın kliplerinde 10/10;
adversaryel `eval_stress` setinde gözlenen FP yok, 0/9) bu veriye dayanıyor; yani o rakamların
verisi depodan yeniden kurulamıyordu. `scripts/get_firesense.py` bu boşluğu kapatmak için
eklenmiştir. **Not:** script eklendi ancak mevcut `data/eval_scenario/Fire` ve `data/eval_stress`
klipleri script'ten *önce* elle indirilmiştir; script'in ürettiği setle birebir aynı olduğu
**henüz doğrulanmadı** — teslimden önce sıfırdan indirip yeniden koşulacaktır.

---

## 3. Değerlendirme setleri ve bilinen kusurları

| Set | Klip | Üretici script | Bilinen kusur |
|---|---|---|---|
| `data/eval_scenario/` (Yangın 10 + Düşme 15 + Normal 12) | 37 | `scripts/build_scenario_eval.py` | düşme klipleri `falls_real`+`falls_surveillance` ile birebir aynı; **1080p anomali yok** |
| `data/eval_big/` (48 anomali / 16 normal) | 63 benzersiz / 64 dosya | `scripts/get_ucf_many.py` | Anomalilerin %100'ü 320×240; 2 normal aynı dosya |
| `data/eval_tune/` (24 anomali / 7 normal) | 31 | `eval_big` ayrık bölünmesi | ayarlama tarafı — sonuç raporlanmaz |
| `data/eval_holdout/` (24 anomali / 8 normal) | 32 | `eval_big` ayrık bölünmesi | **temiz doğrulama tarafı; henüz koşulmadı** |
| `data/eval/` (24 anomali / 8 normal) | 31 | `scripts/build_eval_set.py` + `get_normal_clips.py` | eski set — **`eval_big`'in tam alt kümesi**, bağımsız kanıt değil |
| `data/falls_real/` (GMDCSA) | 15 | `scripts/get_gmdcsa.py` | gerçek video ✓; frontal ev-kamerası (gözetim açısı değil) |
| `data/falls_surveillance/` (URFD) | 6 | `scripts/get_urfd_overhead.py` | gerçek gözetim açısı ✓; düşmeler simüle |
| `data/e2_vehicle/` (RoadAccidents) | 9 | `scripts/get_vehicle_accidents.py` | 6'sı `eval_big` ile örtüşüyor |
| `data/industrial/` (1080p tesis, sınıf başına 5 klip) | 40 | `scripts/get_industrial.py` | ham havuz; sınıf→anlam eşlemesi `industrial/CLASSES.md`'de doğrulandı |
| **`data/eval_defense/`** (20 anomali + 20 normal, 1080p) | 40 | `scripts/build_defense_eval.py` | **hedef-domain-içi ilk pozitif set** — `industrial`'ın kopyası; **henüz ölçüm koşulmadı** |
| `data/eval_stress/` (yangın-renkli negatifler) | 9 | `scripts/get_firesense.py` (yeni) | elle indirilen mevcut kliplerle birebir eşleştiği doğrulanmadı |
| `data/robust/` (bozuk/boş/siyah) | 4 | — | hata-toleransı testi; doğruluk ölçümüne girmez |

### 3.1 `eval_scenario/Fall` — donmuş PNG sorunu (giderildi)
**Denetimde bulunan kusur:** bu 8 klip **hareketsizdi**. `scripts/get_lying.py` tek bir PNG'yi
`ffmpeg -loop 1 -t 3 -r 5` ile sarıyordu; `ffprobe` doğrulaması: 1024×1024, 3.00 sn, 5 fps,
15 kare — hepsi aynı görüntü. Yani bir düşme *hareketini* değil, "yerde yatan kişi" *pozunu*
ölçüyorlardı ve senaryo-seti pozitiflerinin 8/18'ini oluşturuyorlardı.

**Durum: giderildi.** Klipler gerçek düşme videolarıyla değiştirildi (`ffprobe` ile doğrulandı):

| Kaynak | Klip | Çözünürlük / fps | Süre |
|---|---|---|---|
| GMDCSA-24 (`Subject{1,2,3}_fall{01,02,03}`) | 9 | 1280×720 @ 60 fps | 3.8–8.4 sn |
| URFD overhead (`urfd_fall0{1..6}`) | 6 | 640×480 @ 15 fps | 6.4–14.4 sn |

**İki dürüst çekince:**
1. Set kompozisyonu değişti: senaryo seti artık 10 yangın + **15 düşme** = 25 anomali + 12 normaldir
   (eskiden 18 + 12). **Yayınlanmış senaryo-seti rakamları eski kompozisyona aittir ve yeniden
   ölçülmelidir.**
2. Yeni 15 klibin 15'i de `data/falls_real/Fall` (9) ve `data/falls_surveillance/Fall` (6) ile
   **birebir aynı dosyadır** (MD5 doğrulandı). Bu bir veri kalitesi kazancıdır ama **bağımsız kanıt
   eklemez**: "senaryo düşme recall'ı", "GMDCSA recall'ı" ve "URFD recall'ı" aynı 15 klibi ölçer;
   üçünü ayrı ayrı sayarsak çift sayım yaparız.

### 3.2 Çözünürlük–etiket karışımı (confound) — sınırlılık
Ölçülmüş dağılım (`ffprobe`):

| Set | Anomali klipleri | Normal klipler |
|---|---|---|
| `eval_big` (ve tune/holdout bölünmeleri) | **48/48'i 320×240** (%100) | 8/16'sı 1920×1080 (%50), 8'i 320×240 |
| `eval_scenario` — **güncel** | **1080p hiç yok**: yangın 320×240…480×272 (10), düşme 1280×720 (9) + 640×480 (6) | 8/12'si 1920×1080 (%67) |
| `eval_scenario` — denetim anındaki hâli | 1080p yok; düşme 1024×1024 **sentetik donmuş kare** | aynı |

Her iki sette de **tek bir 1080p anomali klibi yoktur**, buna karşılık normallerin yarısı ya da
üçte ikisi 1080p'dir. Yani "anomali" etiketi ile "düşük çözünürlük" istatistiksel olarak birlikte
hareket ediyor. Model kararının ne kadarının olay içeriğinden, ne kadarının görüntü kalitesi
ipucundan geldiğini **mevcut setlerle ayrıştıramıyoruz.** Donmuş-PNG düzeltmesi confound'u
*azalttı* (düşme klipleri artık gerçek 640×480–1280×720 video) ama **ortadan kaldırmadı**.
Bu bir sınırlılıktır ve hem recall'ı hem normal-FP'yi etkileyebilir. Giderme yolu: her etiket
için dengeli çözünürlük dağılımı — `industrial` setinde domain-içi 1080p **pozitif** üretimi
bunun ilk adımıdır.

### 3.3 Örneklem yanlılığı (giderildi)
İndirici script'ler eskiden klipleri **dosya boyutuna göre sıralayıp en küçük N**'i alıyordu →
sistematik olarak en kısa (dolayısıyla en az olaylı) klipler aşırı temsil ediliyordu.
`scripts/_sampling.py` ile **sabit tohumlu deterministik rastgele örnekleme**ye geçildi;
eski davranış `--smallest` bayrağıyla korunur.

### 3.4 `data/test_clip.mp4` — yetenek kanıtı değildir (ground truth'tan çıkarıldı)
`scripts/make_test_video.py` ile üretilen bu klip, olayı **karenin içine gömülü metinle**
("FORKLIFT DEVRİLDİ") taşıyan sentetik bir karikatürdür. Modelin burada yaptığı iş video anlama
değil **OCR**'dır. Denetim anında `benchmark/ground_truth.json` **yalnızca bu tek kaydı** içeriyordu —
yani referans etiketimizin tamamı bir OCR testinden ibaretti.

**Düzeltildi:** klip ground truth'tan çıkarıldı; `benchmark/ground_truth.json` artık
`benchmark/build_ground_truth.py` ile üretiliyor ve **108 gerçek klibi** (kategori klasör adından
gelen yayıncı etiketiyle, MD5-tekilleştirilmiş) kapsıyor. `test_clip.mp4` yalnızca boru hattının
uçtan uca çalıştığını göstermek için (duman testi) kullanılır; hiçbir başarı iddiasının dayanağı değildir.

---

## 4. Atıl yük (temizlik listesi)
- `data/nvidia/` — 27 klip / ~1 GB, denendi ve **kullanılmıyor**.
- `data/scenario/_dl/*.zip` — ~780 MB ham indirme artığı.
- `data/eval_scenario/_deprecated_frozen_fall/` — değiştirilen 8 donmuş-PNG klip (kanıt olarak
  tutuluyor; **ölçüme girmez**).
- Birebir kopyalar — çoğu, aynı klibin birden fazla değerlendirme setinde bulunmasından kaynaklanır.

Bunlar `.gitignore` kapsamındadır (depoya girmezler) ama yerel disk ve envanter sayımını şişirirler;
temizlik betiği (`scripts/dedupe_data.py`) hazırlanmaktadır.
