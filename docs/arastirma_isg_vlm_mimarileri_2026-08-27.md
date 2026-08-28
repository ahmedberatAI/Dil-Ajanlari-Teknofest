# İSG video/VLM mimarileri — araştırma ve proje kararı

**Tarih:** 2026-08-27  
**Amaç:** İSG videolarında serbest VLM anlatısından kaynaklanan yanlış olayları azaltırken
yangın/duman, forklift–raf çarpışması ve forklift–insan ramak kala olaylarını kaçırmamak.

## Sonuç

Birincil kaynakların ortak sonucu, genel amaçlı VLM'nin tek başına alarm sahibi yapılmaması
gerektiğidir. Proje için hedef mimari:

```text
RTSP / video + zaman eşleme + ring buffer
                |
                v
uzman algı: duman/alev + kişi/forklift + takip
                |
                v
fizik motoru: süreklilik, dünya düzlemi mesafesi, TTC/PET, temas
                |
                v
dar olay klibi + bbox/mask/track/ölçüm kanıt paketi
                |
                v
VLM: SUPPORTED | REFUTED | INSUFFICIENT
                |
                v
deterministik kural -> alarm / insan incelemesi / ret
```

VLM olay adını serbestçe üretmez. Olay sınıfı öneri katmanından sabit gelir; VLM yalnız
kanıt paketini kapalı seçenekle doğrular. Nihai alarm, modelin öz-güven metninden değil
uzman skorları, süreklilik ve kalibre eşiklerden çıkar.

## Birincil kanıtlar

### Endüstriyel güvenlik

- [iSafetyBench (ICCVW 2025)](https://openaccess.thecvf.com/content/ICCV2025W/VISION%2725/papers/Abdullah_iSafetyBench_A_video-language_benchmark_for_safety_in_industrial_environment_ICCVW_2025_paper.pdf),
  [proje](https://isafetybench.github.io), [veri](https://github.com/iSafetyBench/data):
  1.100 gerçek endüstriyel klip. Genel VLM'ler belirgin olaylara kıyasla ince insan–makine
  etkileşimlerinde belirgin biçimde zayıf. Bu, yalnız model/prompt değiştirmenin saha güvenliği
  sağlamadığını gösterir.

- [Clip2Safety](https://arxiv.org/abs/2408.07146),
  [resmî kod](https://github.com/Ed1sonChen/Clip2Safety): PPE için sahne/PPE politikası,
  kişi ve ekipman kırpması, açık-vocabulary dedektör ve VLM doğrulamasını kademeli kullanır.
  Kişi/nesne kırpmasının bildirilen yaklaşık 16 puanlık katkısı, tam kare VLM yerine hedefli
  kanıt paketini destekler.

- [SafeVision](https://doi.org/10.1016/j.neucom.2025.132479),
  [resmî depo](https://github.com/Murtazaabidi1/SafeVision-Vision-Language-Reasoning-for-Context-Aware-Safety-Monitoring):
  sahne bağlamı ve yerel bölge akıl yürütmesini birleştirir. Ancak depo 2026-08-27 itibarıyla
  uygulanabilir kod/ağırlık yayımlamıyor; doğrudan entegrasyon adayı değildir.

### Duman ve yangın

- [SmokeBench (WACV 2026)](https://openaccess.thecvf.com/content/WACV2026/html/Qi_SmokeBench_Evaluating_Multimodal_Large_Language_Models_for_Wildfire_Smoke_Detection_WACV_2026_paper.html):
  küçük/erken duman sınıflandırma ve lokalizasyonunda genel MLLM'ler zayıf; bildirilen kutu
  mIoU'su genel modellerde 0 iken GroundingDINO 0,245 ve uzman YOLOv8n 0,773. Genel VLM,
  birincil duman alarmı değil uzman dedektör sonrası bağlam doğrulayıcı olmalıdır.

- [ContextFire-VLM](https://www.nature.com/articles/s41598-026-48743-5),
  [resmî kod](https://github.com/tmdeptrai/ContextFire-VLM): serbest altyazı zinciri yerine
  yapılandırılmış bağlam ve sınırlı sınıf uzayı kullanır. İnce ayarlı kontrollü veri sonuçları
  ümit vericidir; fakat ConFire etiketlerinin bir bölümünün model yardımıyla üretilmesi ve saha
  CCTV sim-to-real farkı bağımsız doğrulama gerektirir.

- [MS-FSDB](https://arxiv.org/abs/2410.16631),
  [resmî veri/kod](https://github.com/XiaoyiHan6/MS-FSDB) ve
  [FASDD](https://github.com/OyamingO/FASDD): bulut/gün batımı gibi zor negatifleri olan uzman
  yangın-duman veri kaynaklarıdır. Endüstriyel buhar, toz ve kaynak dumanı ayrıca saha negatifi
  olarak eklenmelidir.

### Zamansal grounding ve halüsinasyon

- [VideoHallucer](https://arxiv.org/abs/2406.16338),
  [resmî kod/veri](https://github.com/patrick-tssn/VideoHallucer): nesne-ilişki, temporal ve
  semantik ayrıntı halüsinasyonlarını eşlenmiş doğru/yanlış sorularla ayrı ölçer. Projede yalnız
  toplam accuracy değil ilişki ve zaman hatasının ayrı raporlanması gerekir.

- [Woodpecker](https://arxiv.org/abs/2310.16045),
  [resmî kod](https://github.com/BradyFU/Woodpecker): iddiayı atomlara ayırıp bağımsız
  grounding/VQA araçlarıyla doğrulama desenini gösterir. Görüntü sonuçları doğrudan İSG video
  garantisi değildir; mimari desen olarak kullanılmalıdır.

- [QD-DETR](https://arxiv.org/abs/2303.13874) ve
  [HawkEye](https://arxiv.org/abs/2403.10228): ilgisiz video–sorgu çiftleri ve negatif zaman
  aralıklarını eğitimde kullanarak temporal grounding'in boş/yanlış aralık üretmesini azaltır.

- [UniversalVTG](https://arxiv.org/abs/2604.08522),
  [resmî kod](https://github.com/jbistanbul/universalvtg): uzun videoda hafif temporal öneri
  katmanı için adaydır. Fabrika/İSG üzerinde doğrulanmadığından önce yalnız araştırma kolunda
  değerlendirilmelidir.

### Literatürdeki açık model adayları (proje dışı)

Bu bölüm yalnız araştırma bağlamıdır. Projenin çalışma mimarisinde model indirme, yerel model
sunma veya model aliası değiştirme yapılmayacaktır. Tüm öğrenilmiş çıkarımlar mevcut özel API
üzerinden ve sabit görev dağılımıyla yürür: `vlm` algı, `llm-large` olay/kanıt doğrulama,
`llm-fast` yapılandırma ve özet. İyileştirme alanı; kanıt seçimi, kırpım/zaman penceresi,
çağrı sırası ve deterministik kabul-red kapılarıdır.

- [Qwen3-VL-8B](https://github.com/QwenLM/Qwen3-VL): mevcut entegrasyon maliyeti en düşük
  doğrulayıcı; bu projedeki ölçümde tek başına alarm sahibi olamayacağı görülmüştür.
- [NVIDIA Cosmos-Reason2 2B/8B](https://github.com/nvidia-cosmos/cosmos-reason2): fiziksel
  akıl yürütme ve 2B/3B grounding nedeniyle ilk A/B adayıdır. Model kartı sonuçları NVIDIA'nın
  kendi ölçümleridir; bağımsız depo CCTV kanıtı değildir. Ağırlık lisansı Apache-2.0 kod
  lisansından ayrıdır ve dağıtım öncesi denetlenmelidir.
- [LLaVA-OneVision-2](https://github.com/EvolvingLMMs-Lab/LLaVA-OneVision-2): codec ve yoğun
  kare yollarını birlikte kullanması olay başlangıcı için ilginçtir; ince statik ayrıntı ve
  kişi–forklift ilişkisi yine dedektör/takip ister.
- [VideoLLaMA3](https://github.com/DAMO-NLP-SG/VideoLLaMA3): açık video modeli olmasına rağmen
  iSafetyBench endüstriyel tehlike sonuçları birincil alarm için yeterli değildir.
- [VadCLIP](https://github.com/nwpu-zxr/VadCLIP) ve
  [VERA](https://github.com/vera-framework/VERA): zayıf etiketli anomali/olay önerisi için aday;
  son güvenlik hükmü olarak kullanılmamalıdır.

## Projeye uygulanacak sıra

1. **Şimdi:** Açık anlatı alarmını İSG-odaklı fiziksel ailelerle sınırla; yangın, raf çarpışması
   ve ramak kala için kapalı fiziksel gözlem slotu + deterministik olay kodu kullan. `GORUNMUYOR`
   ölçülmüş negatif değildir; insan incelemesine ayrılabilir.
2. **Yangın:** MS-FSDB/FASDD ön eğitimi ve tesisin buhar/toz/kaynak negatifleriyle uzman
   duman/alev dedektörü; ardışık kare sürekliliği, alan büyümesi ve mümkünse çok kamera uyumu.
3. **Forklift:** forklift/kişi dedektörü, BoT-SORT benzeri track, kamera homografisi ve dünya
   düzleminde minimum mesafe, göreli hız, TTC/PET. Near-miss kararı bbox örtüşmesinden çıkmaz.
4. **Kanıt paketi:** tetik öncesi/sonrası 8–24 saniye klip, zaman damgalı kare, bbox/mask,
   track kimliği ve sayısal yörünge. VLM çıktısı yalnız
   `SUPPORTED | REFUTED | INSUFFICIENT` ve kanıt kimlikleri.
5. **Sabit-model A/B:** aynı dondurulmuş geliştirme/holdout üzerinde yalnız mevcut özel API
   aliasları korunur. A/B deneyleri model değil; tam kare/kırpılmış kanıt, zaman penceresi,
   kapalı doğrulama sorusu ve deterministik kapı kombinasyonlarını karşılaştırır.
6. **Saha geçişi:** sentetik NVIDIA verisi yalnız regresyon/geliştirme içindir. Zaman ayrımlı,
   kamera ayrımlı gerçek depo CCTV holdout'u olmadan üretim güvenliği iddiası kurulmaz.

## Kabul metrikleri

- olay bazlı recall ve precision;
- yanlış alarm / kamera-saat;
- başlangıç gecikmesi p50/p95 ve temporal IoU;
- TTC/PET ve minimum mesafe hatası;
- `INSUFFICIENT`/insan incelemesi oranı ve risk–coverage eğrisi;
- küçük duman, gece, sıkıştırma, motion blur, oklüzyon ve kamera-dışı OOD dilimleri;
- p95 gecikme, VRAM ve ağ gövdesi.

Sentetik klipte yüksek görüntü-başı doğruluk, gerçek sahada güvenli alarm sistemi anlamına gelmez.
