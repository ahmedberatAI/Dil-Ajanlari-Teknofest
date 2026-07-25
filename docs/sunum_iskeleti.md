# Sunum İskeleti (slayt-slayt içerik)

> Not: Jüri sunum başlıklarını yarışma sırasında mail ile bildirecek; bu iskelet o
> başlıklara kolayca eşlenecek şekilde modülerdir. Başlangıç `.pptx`: `docs/sunum.pptx`.
>
> **Slaytlara sayı yazarken:** kanonik değerler ve güven aralıkları
> [`docs/olcum_durustlugu.md`](olcum_durustlugu.md)'dedir. Küçük örneklemde ondalıklı yüzde
> ("%98.7") ve mutlak "%0 yanlış-pozitif" ifadeleri **kullanılmaz**; her oran `k/n` +
> %95 aralığıyla verilir.

1. **Kapak** — DilAjanları · Yerel Video Analiz ve Karar Destek Ajanı · TEKNOFEST TYDA 3. Senaryo · Takım adı/üyeleri.

2. **Problem** — Savunma/saha kameraları yüksek hacimli video üretir; manuel analiz pahalı ve hataya açık. İhtiyaç: olayları gerçek zamanlıya yakın, Türkçe, yerel ve güvenilir analiz.

3. **Çözümümüz** — Tamamen yerel/offline, multimodal (video+metin) bir YZ ajanı: zaman damgalı olay tespiti, Türkçe özet, risk değerlendirmesi, operatöre aksiyon önerileri + operasyonel fonksiyon tetikleme. Çıktı: yapılandırılmış JSON.

4. **Mimari** — Diyagram (docs/architecture.md). Qwen3-VL-8B (FP8) + vLLM (yerel servis) + LangGraph (**6 düğüm + koşullu kenar**). Dış API/bulut yok.

5. **Ajan akışı** — ingest → perceive (iki aşamalı algı) → **[koşullu] reexamine** → reason → act (mock fonksiyon dispatch) → finalize. Belirsiz ("Orta") olay varsa ajan kendi tespitini yeniden sorgular (döngü muhafızlı, en fazla bir kez). Altı düğümün dış gövdesi try/except; ayrıca segment-içi fail-open.

6. **Agentic bileşenler** — Tools (6 mock operasyonel fonksiyon), memory (segmentler arası olay birikimi + diyalog hafızası), prompt engineering (Türkçe), dinamik model-tabanlı araç seçimi.

7. **Anahtar yenilik 1 — İki aşamalı algı** — Katı JSON promptu düşük çözünürlüklü gerçek CCTV'de modeli sustuyordu; önce serbest tarif → sonra olay çıkarımı gerçek tespiti çözdü.

8. **Anahtar yenilik 2 — Risk kalibrasyonu** — Severity kalibrasyonu + risk tabanı: gerçek tehditleri yükseltir (QWK 0.733). Normal kliplerde **gözlenen dar-yanlış-pozitif yok** — adversaryel sette 0/9 (%95 üst sınır %30), 1080p endüstriyelde 0/8 (üst sınır %32). Operasyonel-FP (dispatch kapısıyla engellenen zararsız notlar) daha yüksek: 4/12 ve 6/16 — dürüstçe raporlanır.

9. **Otonomi & Diyalog** — Operatör asistanı: grounded, inisiyatif, açıklayıcı soru, **bağlam-değişimi/prompt-injection direnci**. Bağımsız Gemma hakemi 5.00/5 (**n = 7 tek-tur + 4 çok-tur senaryo; hakem std = 0 → tavan-doygunluğu, ölçek ayrım gücünü yitiriyor**). Canlı demoda gösterilecek.

10. **Ölçüm & KPI (dürüst 3-seviyeli)** — Her oran `k/n` + **Wilson %95 güven aralığı** ile (`benchmark/stats_utils.py`); n ≤ 48'de ondalıklı yüzde yok. Senaryo recall **18/18 [%82–%100]**; grenli UCF **44/48 [%80–%97]**. Üç seviyeli (51 bağımsız klip): **TESPİT 49/51 [%87–%99] / AKSİYON 36/51 [%57–%81] / TANIMA 22/51 [%31–%57]** — girdi-tavanı. Özet **4.62 ± 0.53**, aksiyon **4.74 ± 0.44** (bağımsız Gemma). Ayrıca 8+ ölçülüp-reddedilen teknik (dürüstlük disiplini).

10b. **"Yetersizliği biz ölçtük ve yayınladık"** *(ayırt edici slayt)* — Kendi ölçümümüzü denetledik ve düzelttik: mükerrer klip sayımı (81 → 51 bağımsız klip), `eval ⊂ eval_big` sızıntısı (ayrık tune/holdout bölünmesi), donmuş-PNG düşme klipleri (gerçek videoyla değiştirildi), kanıtsız throughput iddiasının geri çekilmesi. Açıkça yazdığımız boşluklar: gece/IR/termal **sıfır kapsam**, hedef domainde **pozitif yok**, kalite hakemi **videoyu görmüyor** (iç tutarlılık ölçüyor). Bkz. `docs/olcum_durustlugu.md`.

11. **Performans & ölçeklenebilirlik** — Prefix-caching → eşzamanlı (×4) throughput **+13.5%** (3.7 → 4.2 video/dk, kayıtlı log); tek-akış ort **0.86 s/vsn** (n=6, 0.44–3.75); tepe VRAM ~21/24 GB; bozuk/olaysız video zarif yönetimi; tamamen yerel. *(Eski "+24% / 4.6 video-dk" iddiası kayıtlı log olmadığı için geri çekildi.)*

12. **Açık kaynak & tekrar üretilebilirlik** — Apache 2.0, requirements-lock, adım adım kurulum, her veri seti için indirici script + herkese açık link, veri envanteri ve lisans beyanı (`docs/veri_kaynaklari.md`). **UCF-Crime'ın CC olmadığını** ve üçüncü-taraf aynadan çekildiğini açıkça yazıyoruz.

13. **Sonuç & gelecek** — Çalışan uçtan uca sistem + kayıtlı artefaktlara bağlı metrikler. Gelecek: kare-kanıtlı kalite hakemi (dayanaklılık ölçümü), hedef-domain pozitif seti (`industrial` class0–3), gece/IR kapsamı, daha yüksek çözünürlük girdi (girdi-tavanını aşmanın asıl yolu — 32B denenip elendi: 24 GB'a sığmaz + tavanı çözmez), EVS video-token budama, çoklu kamera, ses I/O. (Roadmap: `iyilestirmeler.md` §20-§21.)

14. **Teşekkür / Soru-cevap** — Takım, iletişim, demo daveti.
