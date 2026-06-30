# Sunum İskeleti (slayt-slayt içerik)

> Not: Jüri sunum başlıklarını yarışma sırasında mail ile bildirecek; bu iskelet o
> başlıklara kolayca eşlenecek şekilde modülerdir. Başlangıç `.pptx`: `docs/sunum.pptx`.

1. **Kapak** — DilAjanları · Yerel Video Analiz ve Karar Destek Ajanı · TEKNOFEST TYDA 3. Senaryo · Takım adı/üyeleri.

2. **Problem** — Savunma/saha kameraları yüksek hacimli video üretir; manuel analiz pahalı ve hataya açık. İhtiyaç: olayları gerçek zamanlıya yakın, Türkçe, yerel ve güvenilir analiz.

3. **Çözümümüz** — Tamamen yerel/offline, multimodal (video+metin) bir YZ ajanı: zaman damgalı olay tespiti, Türkçe özet, risk değerlendirmesi, operatöre aksiyon önerileri + operasyonel fonksiyon tetikleme. Çıktı: yapılandırılmış JSON.

4. **Mimari** — Diyagram (docs/architecture.md). Qwen3-VL-8B (FP8) + vLLM (yerel servis) + LangGraph (5 düğüm). Dış API/bulut yok.

5. **Ajan akışı** — ingest → perceive (iki aşamalı algı) → reason → act (mock fonksiyon dispatch) → finalize. Her düğüm hata toleranslı.

6. **Agentic bileşenler** — Tools (6 mock operasyonel fonksiyon), memory (segmentler arası olay birikimi + diyalog hafızası), prompt engineering (Türkçe), dinamik model-tabanlı araç seçimi.

7. **Anahtar yenilik 1 — İki aşamalı algı** — Katı JSON promptu düşük çözünürlüklü gerçek CCTV'de modeli sustuyordu; önce serbest tarif → sonra olay çıkarımı gerçek tespiti çözdü.

8. **Anahtar yenilik 2 — Risk kalibrasyonu** — Severity kalibrasyonu + risk tabanı: gerçek tehditleri yükseltir (QWK 0.733); normalde dar-yanlış-pozitif ~%0 (operasyonel-FP ~%8–10 dürüstçe raporlanır).

9. **Otonomi & Diyalog** — Operatör asistanı: grounded, inisiyatif, açıklayıcı soru, **bağlam-değişimi/prompt-injection direnci**. Diyalog robustluğu 5.00/5 (bağımsız Gemma; canlı demoda gösterilecek).

10. **Ölçüm & KPI (dürüst 3-seviyeli)** — Dengeli değerlendirme seti (anomali+normal) + ortalama±std. Senaryo recall %99±2; grainy-UCF **TESPİT %96 / AKSİYON %73 / TANIMA %46** (girdi-tavanı); QWK 0.733; dar-FP ~%0 (op-FP ~%8–10); özet ~4.6/5 (bağımsız Gemma); diyalog 5.0/5. Ayrıca 8+ ölçülüp-reddedilen teknik (dürüstlük disiplini).

11. **Performans & ölçeklenebilirlik** — Prefix-caching + serving-flag'leri → eşzamanlı (x4) throughput **+24%** (3.7→4.6 video/dk); tek-akış ~1.5 s/vsn (hızlı mod ~0.6); bozuk/olaysız video zarif yönetimi; tamamen yerel (24GB).

12. **Açık kaynak & tekrar üretilebilirlik** — Apache 2.0, requirements-lock, adım adım kurulum, herkese açık veri seti linki (UCF-Crime), dokümantasyon.

13. **Sonuç & gelecek** — Çalışan uçtan uca sistem + kanıtlanmış metrikler. Gelecek: daha yüksek çözünürlük girdi (girdi-tavanını aşmanın asıl yolu — 32B denenip elendi: 24GB'a sığmaz + tavanı çözmez), EVS video-token budama, çoklu kamera, ses I/O. (Roadmap: `iyilestirmeler.md` §20-§21.)

14. **Teşekkür / Soru-cevap** — Takım, iletişim, demo daveti.
