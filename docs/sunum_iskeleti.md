# Sunum İskeleti (slayt-slayt içerik)

> Not: Jüri sunum başlıklarını yarışma sırasında mail ile bildirecek; bu iskelet o
> başlıklara kolayca eşlenecek şekilde modülerdir. Başlangıç `.pptx`: `docs/sunum.pptx`.

1. **Kapak** — DilAjanları · Yerel Video Analiz ve Karar Destek Ajanı · TEKNOFEST TYDA 3. Senaryo · Takım adı/üyeleri.

2. **Problem** — Savunma/saha kameraları yüksek hacimli video üretir; manuel analiz pahalı ve hataya açık. İhtiyaç: olayları gerçek zamanlıya yakın, Türkçe, yerel ve güvenilir analiz.

3. **Çözümümüz** — Tamamen yerel/offline, multimodal (video+metin) bir YZ ajanı: zaman damgalı olay tespiti, Türkçe özet, risk değerlendirmesi, operatöre aksiyon önerileri + operasyonel fonksiyon tetikleme. Çıktı: yapılandırılmış JSON.

4. **Mimari** — Diyagram (docs/architecture.md). Qwen2.5-VL-7B + vLLM (yerel servis) + LangGraph (5 düğüm). Dış API/bulut yok.

5. **Ajan akışı** — ingest → perceive (iki aşamalı algı) → reason → act (mock fonksiyon dispatch) → finalize. Her düğüm hata toleranslı.

6. **Agentic bileşenler** — Tools (6 mock operasyonel fonksiyon), memory (segmentler arası olay birikimi + diyalog hafızası), prompt engineering (Türkçe), dinamik model-tabanlı araç seçimi.

7. **Anahtar yenilik 1 — İki aşamalı algı** — Katı JSON promptu düşük çözünürlüklü gerçek CCTV'de modeli sustuyordu; önce serbest tarif → sonra olay çıkarımı gerçek tespiti çözdü.

8. **Anahtar yenilik 2 — Risk kalibrasyonu** — Severity kalibrasyonu + risk tabanı: gerçek tehditleri yükseltir, normal videolarda yanlış-pozitif %0.

9. **Otonomi & Diyalog** — Operatör asistanı: grounded, inisiyatif, açıklayıcı soru, **bağlam-değişimi/prompt-injection direnci**. Robustluk testi 4.33/5 (canlı demoda gösterilecek).

10. **Ölçüm & KPI** — Dengeli değerlendirme seti (anomali+normal), benchmark altyapısı. Recall %96, risk-kalibrasyon, normal-FP %0, özet kalitesi (LLM-judge), diyalog robustluğu. Baseline→Faz 2 veri karşılaştırması.

11. **Performans & ölçeklenebilirlik** — Segment paralelleştirme → 3.2× hızlanma; CUDA graphs ile ~37 tok/s; bozuk/olaysız video zarif yönetimi; tamamen yerel.

12. **Açık kaynak & tekrar üretilebilirlik** — Apache 2.0, requirements-lock, adım adım kurulum, herkese açık veri seti linki (UCF-Crime), dokümantasyon.

13. **Sonuç & gelecek** — Çalışan uçtan uca sistem + kanıtlanmış metrikler. Gelecek: daha büyük model (32B), daha yüksek çözünürlük, ses analizi, çoklu kamera.

14. **Teşekkür / Soru-cevap** — Takım, iletişim, demo daveti.
