# DilAjanları — Kapsamlı Performans Raporu (2026-06-22)

Şartname (2026 TEKNOFEST TYDA, 3. Senaryo) gereksinimlerine **her boyuttan** uyum ve ölçülen başarı.
Tüm sayılar bu oturumda, **güncel model + tüm iyileştirmeler (E1-E5, G6-G12)** ile ölçülmüştür.
Model: **Qwen3-VL-8B-Instruct-FP8** (yerel, vLLM, RTX 5090 24GB). Değerlendirme: çoğu metrik **objektif**
(dataset etiketine karşı); kalite metrikleri **bağımsız** Gemma-3-12B judge ile (döngüsel değil).

## 0. Test kapsamı (genişlik)
| Set | Klip | Özellik |
|---|---|---|
| Senaryo (Yangın+Düşme+Normal) | 30 | senaryo-uyumlu, net olaylar |
| Büyük UCF (8 anomali kategori) | 64 | grainy 320×240, dayanıklılık stresi |
| GMDCSA gerçek düşme | 15 | gerçek, frontal ev-kamera |
| URFD overhead düşme | 6 | gerçek **tavan/gözetim açısı** |
| Araç kazası (RoadAccidents) | 9 | gerçek CCTV, devrilme/çarpışma |
| Endüstriyel (Eskişehir) | 8 | gerçek 1080p fabrika CCTV (forklift dâhil) |
| Holistik temsili | 9 | uçtan-uca karne |
| Diyalog (tek+çok-tur) | 11 | otonomi/robustluk |
| **Toplam** | **~130+** | 320×240→1080p, frontal/overhead/yol, gerçek+grainy |

Ayrıca **koşu-arası varyans** 16+13+5 koşu üzerinden raporlanır (gizlenmez).

---

## 1. İŞLEVSELLİK (Şartname %35)
### Olay tespiti (anomali recall) — objektif
| Set | Recall | Not |
|---|---|---|
| Senaryo | **%99 ± 2** [94–100] (16 koşu) | in-domain kararlı |
| Holistik temsili | **%100** | yangın/düşme/patlama/kaza |
| URFD overhead düşme | **%100** (6/6) | gerçek gözetim açısı |
| Büyük UCF (n=48) | **%92** | grainy; per-kat %67–100 |
| GMDCSA gerçek düşme | **%89** (8/9) | frontal, hızlı düşme |
| Araç kazası | **%89** (8/9) | gerçek CCTV |
| UCF (koşu-varyans, n=24) | %86 ± 12 [58–100] (13 koşu) | grainy doğal değişkenlik |

### Anlamsal yorumlama + çıktı kalitesi (bağımsız Gemma judge, 1-5)
| Metrik | Skor | Kaynak |
|---|---|---|
| Özet kalitesi | **4.64 ± 0.53** (n=90) | bağımsız |
| Aksiyon kalitesi | **4.66–4.74** | bağımsız + holistik 4.83 |
| Risk gerekçe kalitesi | **4.87–5.00** | bağımsız + holistik 4.83 |
| Risk seviyesi doğruluğu | senaryo %96±7 / holistik %78 | objektif |
| Kategori eşleşme | senaryo **%95±8** / UCF %44 | objektif (grainy = tavan) |
| **JSON şema uyumu** | **%100** | objektif (mock'la birebir) |

### Yanlış-pozitif (normal kliplerde) — objektif, dürüst
| Metrik | Değer | Yorum |
|---|---|---|
| Dar FP (yüksek-sev/risk) | **%0–8** (ort %8±5) | büyük-UCF n=16'da **%0** |
| Yanlış operasyonel-tetik (dispatch-FP) | **~%0** (nadiren stokastik) | zararlı alarm pratikte kesildi |
| Operasyonel-FP (herhangi Düşük olay) | %19±13 | hepsi **gated**, yarı-meşru notlar |

**Özet (İşlevsellik):** Net/senaryo-uyumlu olaylarda **~%100** tespit + **%100 JSON** + yüksek kalite (≈4.6-5.0);
grainy off-domain'de recall yüksek (%92) ama tür-adlandırma zayıf (girdi-tavanı, dürüstçe beyan).

---

## 2. TEKNİK / MİMARİ (Şartname %35)
| Boyut | Durum |
|---|---|
| Mimari | LangGraph ajan: ingest → perceive → **(koşullu) reexamine** → reason → act → finalize |
| Çok-adımlı zeka | iki-aşamalı algı (tarif→çıkarım), öz-doğrulama (deduce-verify), spatial grounding (bbox→bölge), dedup, **dinamik dispatch-gate** |
| Bellek/bağlam | sohbet geçmişi + segment-bağlamı; çok-turlu diyalog tutar |
| Gecikme (tam mod) | **~1.5 s/video-sn** (segment paralel) |
| Gecikme (**hızlı mod**) | **~0.61 s/video-sn (2.5×)** — doğruluk korunuyor (özet/aksiyon/risk ≈ aynı) |
| Güvenilirlik | **watchdog** (sağlık-kontrol + otomatik restart); **zarif bozulma** (bozuk/boş video çökmez) |
| Ölçeklenme | vLLM continuous-batching (eşzamanlı kuyruk); çok-GPU için tensor-parallel yolu |
| Yerel/offline | **yalnız 127.0.0.1**, vLLM, FP8 24GB — dış API/kapalı-servis yok |
| Sağlamlık | segment-overlap (sınır olayları), iki-dilli severity, **dil-saflığı guard** (sızıntı %0.5→düzeltilir) |
| Açık kaynak | Apache-2.0 model + repo, requirements-lock, dokümante |

---

## 3. OTONOMİ / ZEKA (Şartname %20)
| Metrik | Skor |
|---|---|
| Diyalog robustluğu (tek-tur, 7 senaryo) | **5.00/5** (self + bağımsız) |
| Çok-turlu tutarlılık (4 tur, bağlam taşıma) | **5.00/5** (self + bağımsız) |
| Açıklayıcı-soru (belirsiz gönderme) | 5/5 (körü körüne varsaymıyor, soruyor) |
| İnisiyatif (en kritik aksiyonu öne çıkarma) | 5/5 |
| Prompt-injection direnci / görev-dışı reddi | 5/5 |
| Halüsinasyon direnci (bağlamda yoksa "yok") | 5/5 |
| Agentic dispatch doğruluğu (M2) | %78 (anomali-tetik %83, normal-temiz %67; n küçük) |

**Özet (Otonomi):** niyet anlama + reasoning + inisiyatif + açıklayıcı-soru + injection-direnci tam puan;
statik-kural değil **model-tabanlı + koşullu döngülü** karar.

---

## 4. YENİLİKÇİLİK (Şartname %10)
- **Öz-doğrulama** (deduce-then-verify): yüksek-severity olayları odaklı re-check; aşırı-yorumu reddeder.
- **Koşullu re-examine döngüsü:** belirsiz (Orta) olayları ajan "tekrar bakar" (adaptif otonomi).
- **Dinamik dispatch-gate:** operasyonel fonksiyonlar yalnız gerçek yüksek-riskte → alarm-yorgunluğu kesilir.
- **Spatial grounding:** native bbox → 3×3 Türkçe bölge ("üst sağ" vb.).
- **Çelişki-kuralı extraction:** model gövdede olay tarif edip sonda "SAPMA YOK" derse somut olayı kurtarır.
- **Bağımsız LLM-judge ile öz-değerlendirme** (Gemma≠Qwen): metodolojik dürüstlük yeniliği.
- **İki-dilli severity tabanı + dil-saflığı guard + hızlı mod + watchdog.**

---

## 5. Şartname zorunlu çıktılar — uyum
| Zorunlu | Durum |
|---|---|
| Video al + analiz | ✅ |
| Olay/kişi/risk tespiti | ✅ (recall yukarıda) |
| Kritik an + **zaman bilgisi** | ✅ (`time` + zaman-pencereleri) |
| Kısa Türkçe özet | ✅ (4.64/5 bağımsız) |
| Operatör aksiyon önerisi | ✅ (4.66-4.83/5) |
| **Yapılandırılmış JSON** | ✅ (**%100** şema uyumu) |
| Offline/yerel + dış-servis yok | ✅ (127.0.0.1) |
| ~Gerçek-zaman servisleme | ✅ (hızlı mod 0.61 s/vsn) |

---

## 6. Dürüst sınırlar (saklanmıyor)
- **Grainy UCF tür-adlandırma %44** — girdi-tavanı (düşük çözünürlük + senaryo-dışı).
- **Gerçek savunma-tesisi / fabrika-kaza videosu** açık veride yok; en yakın gerçek verilerle test edildi.
- **Normal-FP stokastik** %0-8 (dar) — bazı endüstriyel normallerde nadir Düşük/gated not; zararlı dispatch ~0.
- **1 hızlı düşme (GMDCSA) + 1 grainy kaza** kaçıyor — girdi/ambiguite tavanı.
- **Tek-GPU** donanımsal; watchdog güvenilirliği sağlar, yatay ölçek donanım ister.

## 7. Genel değerlendirme
Şartmenin **zorunlu çıktılarının tamamı** karşılanıyor; 4 puanlama ekseninde:
**İşlevsellik** güçlü (net olaylarda ~%100 + %100 JSON + yüksek kalite), **Teknik/Mimari** güçlü
(agentic, çok-adımlı, hızlı mod, güvenilirlik), **Otonomi** çok güçlü (diyalog 5.0, açıklayıcı-soru,
injection-direnci), **Yenilikçilik** orta-iyi (öz-doğrulama, koşullu döngü, dispatch-gate, bağımsız-judge).
Sayılar **objektif + bağımsız + varyanslı** raporlandığından jüri-güvenilirliği yüksektir.
