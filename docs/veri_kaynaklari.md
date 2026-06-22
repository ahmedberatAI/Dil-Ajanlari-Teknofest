# Veri Kaynakları, Lisanslar ve İndirme

Bu proje **hiçbir video verisini depoda dağıtmaz** — tüm klipler aşağıdaki **herkese açık** kaynaklardan
indirme script'leriyle çekilir (`data/` dizini `.gitignore`'dadır). Her veri seti kendi lisansı altındadır;
proje kodu Apache-2.0'dır ancak veri setleri kendi orijinal lisanslarını korur (lisans zinciri net ayrık).

| Veri seti | İçerik | Lisans | Herkese açık link | İndirme |
|---|---|---|---|---|
| **FIRESENSE** | Yangın/duman + negatifler | CC BY 4.0 | https://zenodo.org/records/836749 | `wget` (zenodo doğrudan URL) |
| **GMDCSA-24** | Gerçek düşme + ADL videoları | CC BY 4.0 | https://github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos | `scripts/get_gmdcsa.py` |
| **Eskişehir Kafaoğlu Endüstriyel** | 1080p fabrika güvenli/güvensiz davranış | CC BY 4.0 | https://data.mendeley.com/datasets/xjmtb22pff/1 | `scripts/get_industrial.py` |
| **Simuletic CCTV** | Tepeden-CCTV yerde-yatan kişi (sentetik) | CC BY 4.0 | https://huggingface.co/datasets/Simuletic/CCTV_Incident_Dataset_Fall_Lying_Down_Detection | `scripts/get_lying.py` |
| **UCF-Crime** | Gözetim anomali (dayanıklılık stresi) | Akademik/araştırma | https://www.crcv.ucf.edu/projects/real-world/ (mirror: HF) | `scripts/get_ucf_clip.py` |
| **NVIDIA PhysicalAI Warehouse** | 1080p sentetik depo (denendi, kullanılmadı) | OpenMDW 1.1 | https://huggingface.co/datasets/nvidia/PhysicalAI-WorldModel-Synthetic-Warehouse-Operations-Scenes | (deney; manuel) |

## Lisans uyumu notları
- **Kod**: Apache-2.0 (`LICENSE`). **Model**: Qwen3-VL-8B-Instruct(-FP8) — Apache-2.0.
- **Veri**: Depoya gömülü değil; yalnızca indirme script'leri + bu manifest dağıtılır. UCF-Crime
  yalnızca **akademik/araştırma** değerlendirmesi için kullanılır (yeniden dağıtım yapılmaz).
- Savunma-tesisi senaryosu: Eskişehir seti gerçek tesisten **izinli** toplanmıştır (Kafaoğlu A.Ş.).
  Demo/sunumda gizlilik gereği yüz/kimlik vurgusu yapılmaz.

## Değerlendirme setleri (script'lerle yeniden üretilebilir)
- `data/eval_scenario/` (Yangın + Düşme + Normal) — `scripts/build_scenario_eval.py`
- `data/falls_real/` (GMDCSA-24 gerçek düşme) — `scripts/get_gmdcsa.py`
- `data/eval/` (UCF dengeli set) — `scripts/build_eval_set.py` + `scripts/get_normal_clips.py`
- `data/eval_stress/` (adversaryel yangın-renkli negatifler), `data/robust/` (bozuk/boş/siyah — hata-tolerans)
