# Farklılaşma Analizi — Bu sistemi benzerlerinden ayıran gerçekten var mı? (2026-06-22)

6 paralel literatür/pazar araştırmasının (akademik VLM-VAD, ticari gözetim-analitiği, on-prem/savunma,
endüstriyel-güvenlik, değerlendirme-metodolojisi, Türk savunma-AI/LLM ekosistemi) **dürüst** sentezi.
Kural: gerçek kaynaklarla doğrulanmış; abartı yok — teknik bilen bir jüri yakalar.

## Kısa cevap
**Evet, gerçek ayırt ediciler var — ama DAR ve KOMBİNASYONEL; kavramsal "ilk/yeni" değil.**
Tek tek aldığımız her bileşen (VLM-VAD, NL özet, agentic akış, öz-doğrulama, grounding, LLM-judge, on-prem,
aksiyon-dispatch) literatürde/pazarda mevcut. Ayırt edici olan **kesişim**: Türkçe + tam-offline + açık-kaynak
+ tek-commodity-GPU + operasyonel-aksiyon-katmanlı agentic karar-destek — bu **bütünü** dolduran ne bir
akademik sistem, ne bir ticari ürün, ne de bir Türk oyuncu var.

---

## A) COMMODITY — bunları "yenilik" diye sunMA (kanıt: gerçek sistemler)
| İddia | Neden commodity | Kanıt |
|---|---|---|
| VLM ile video analizi + NL açıklama | 2024'ten beri varsayılan paradigma | LAVAD (CVPR'24), Holmes-VAD, VAD-LLaMA |
| İki-aşamalı algı (tarif→akıl) | LAVAD şablonu = alan standardı | LAVAD |
| Öz-doğrulama / deduce-then-verify / self-reflection | Yaygın | AnomalyRuler (ECCV'24), VAU-R1, PANDA |
| Spatial/temporal grounding | Standart alt-görev | VAU-R1 ödülleri |
| Tek yerel Qwen-VL omurgası | **PANDA birebir Qwen2.5-VL-7B; NVIDIA VSS Qwen3-VL-8B'yi listeliyor** | PANDA (2509.26386), VSS |
| Agentic + tool + self-reflection pipeline | Genç ama yerleşik yön | PANDA + 2026 "agentic anomaly" survey |
| Operatör diyaloğu (video Q&A) | Var | AssistPDA (streaming), Spot AI Iris |
| NL özet/arama ticari ürünlerde | "Table-stakes" | Verkada, Genetec, Camio, NVIDIA VSS |
| Aksiyon-dispatch / "active response" | Ticari trend | Spot AI Iris, Intenseye Sentinel (makine durdurma) |
| LLM-as-judge değerlendirme | Standart (2023'ten) | MT-Bench (Zheng), G-Eval |
| Nesne tespiti/takip | TR primleri dünya çapında, yıllarca önde | ASELSAN, STM (KARGU), Baykar |
| On-prem video analitiği | Olgun pazar | BriefCam/Milestone, Avigilon, Intenseye edge |

## B) GERÇEK AYIRT EDİCİLER — dar, net, kanıtlı (kesişim + katman)
1. **Tespit→AKSİYON kapatma (operasyonel dispatch + risk-kapısı).**
   Akademik sistemlerin TAMAMI skor/açıklamada duruyor — *aktüasyona* gitmiyor (kanıt: A subagent, PANDA dâhil
   hiçbiri operatör fonksiyonu çağırmıyor). Ticari aktüasyon = sabit-kablolu interlock (yakınlıkta durdur),
   VLM-akıl-yürütmeli değil (D: Voxel açıkça serbest-LLM reddediyor). Bizim **risk-koşullu fonksiyon-çağrımı**
   (sağlık/güvenlik/acil-durdurma yalnız gerçek yüksek-riskte) bu boşlukta. → "agentic VAD" değil, **"operasyonel
   aksiyon katmanı"** diye çerçevele.
2. **Türkçe operatör-NL + korumalı çok-turlu diyalog (injection-dirençli).**
   Literatür İngilizce-only; ticari ürünler İngilizce-öncelikli; TR primleri CV yapıyor NL-video değil; TR-yerli
   VLM'lerin hepsi **image-only + araştırma-seviyesi** → **Türkçe-yerli VIDEO VLM YOK** (F). HAVELSAN Eyeminer
   bile tespit/alarmda duruyor (B). Bu alan **fiilen boş**.
3. **Tam-offline / air-gapped / açık-kaynak — TEK 24GB commodity GPU.**
   NVIDIA VSS 1-4× **80GB datacenter** GPU ister + "tam-yerel agent" hâlâ *roadmap* (C). Bulut kohortu
   (Verkada/Camio/Eagle Eye/Spot AI) savunma için eleniyor. NATO bile air-gapped *Google* cloud'a gidiyor —
   bizde **sıfır yabancı-vendor**, TR yerlileştirme/KVKK doktrinine daha iyi oturuyor.
4. **Değerlendirme titizliği (yarışma bağlamında).**
   Çapraz-aile judge + objektif/judged ayrımı + mean±std varyans + dürüst başarısızlık = araştırma-standardı
   (yeni değil), ama yarışmacıların neredeyse hiçbiri yapmaz (E). Jüri dürüstlük/tekrar-üretilebilirlik
   değer veriyorsa gerçek edge.

## C) DÜRÜST UYARILAR — abartılırsa jüri yakalar
- **Temel model Türkçe değil** (Qwen3-VL). Yerlileştirme **uygulama/UX/açık-kaynak** katmanında — model
  katmanında değil. (Savunulabilir: Türkçe-yerli video VLM yok; ama "yerli model" deme.)
- **Agent/öz-doğrulama/judge/yerel-VLM'de yenilik İDDİA ETME** — hepsi yayınlanmış (PANDA en yakın analog).
- **Doğruluk/olgunluk/ölçekte öndeyiz deme** — Intenseye ($90M+, TR-merkezli), Voxel (5B+ saat, %77 yaralanma↓),
  Protex ($36M) sertleşmiş CV modelleri, gerçek ROI, saniye-altı, EHS-entegrasyon ile **yıllarca önde**.
  Onların klasik-CV tercihi **bilinçli** (hassasiyet + düşük-FP; VLM halüsinasyon yapabilir, GPU-ağır).
- **Tespit/takip primitifini pitch'leme** — TR primleri dünya çapında.
- Tek farklı-aile judge yine de perplexity-bias taşır → **"bias'ı azalttık + raporladık"**, "yok ettik" değil.

## D) Savunulabilir tek-cümle konum (jüri/sunum için)
> "Türkçe çalışan, tamamen air-gapped, açık-kaynak, **operasyonel aksiyon katmanlı agentic VLM video
> karar-destek** sistemi — tek commodity 24GB GPU üzerinde. Bu **kesişimi** ne bir akademik sistem, ne bir
> ticari ürün, ne de bir Türk oyuncu dolduruyor; parçalar ayrı ayrı var ama **bütünleşik + yerelleştirilmiş +
> egemen + sahaya-konuşlanabilir** hâli boş. Daha doğru/olgun değiliz; **farklı biçimliyiz** — yüksek-hassasiyet
> bulut-ölçek alarm motoru değil, egemen-offline Türkçe açıklayıcı karar-destek ajanı."

## E) Farklılaşmayı GÜÇLENDİRecek somut adımlar (opsiyonel)
- **2. bağımsız judge ekle** (PoLL paneli) veya küçük insan-kalibrasyonu (G-Eval) → değerlendirme edge'ini
  en güçlü karşı-argümana (tek-judge perplexity bias) karşı kapatır.
- **Operasyonel aksiyon katmanını** sunumda öne çıkar (literatürün durduğu yer; en savunulabilir teknik fark).
- **Türkçe + air-gapped + sıfır-yabancı-vendor** üçlüsünü egemenlik/yerlileştirme hikâyesi olarak vurgula.

### Karşılaştırma için anahtar gerçek sistemler (doğrulanmış)
Akademik: LAVAD · AnomalyRuler · Holmes-VAD/VAU · VAD-LLaMA · VERA · AssistPDA · VAU-R1 · **PANDA** (en yakın).
Ticari: NVIDIA Metropolis VSS · Verkada · BriefCam/Milestone · Genetec · Camio · Spot AI Iris · Coram.
Endüstriyel: **Intenseye (TR)** · Protex AI · Voxel · Everguard · Chooch. TR savunma: ASELSAN · STM · Baykar · HAVELSAN MAIN/Eyeminer.
Metodoloji: MT-Bench/Zheng · self-preference-bias (2410.21819) · PoLL · G-Eval.
