# Şartname Uyum Matrisi (2026 TEKNOFEST TYDA — 3. Senaryo)

Gerçek şartname metnine (19 sayfa) göre madde-madde uyum denetimi. ✅ karşılandı · ⚠️ kısmi/takım-tarafı · 🔴 eksik.

## 3. Problem Tanımı — zorunlu çıktılar
| Gereksinim | Durum | Kanıt |
|---|---|---|
| Video girdisi al + içeriği analiz et | ✅ | `ingest`+`perceive` (PyAV kare/segment, VLM analiz) |
| Olay/kişi/riskli durum tespiti | ✅ | iki-aşamalı algı; senaryo recall %99±2 |
| Kritik anları zaman bilgisiyle belirle | ✅ | olay `time` + zaman-pencereleri `[00:30–00:50]` |
| Kısa anlaşılır Türkçe özet | ✅ | özet kalitesi 4.98/5 (LLM-judge) |
| Operatöre aksiyon önerileri | ✅ | `actions[öncelik,gerekçe]`, 4.71/5 |
| Yapılandırılmış JSON | ✅ | `to_sartname_dict` — mock örnekle birebir; uyum %100 |
| Offline/yerel + dış-API/kapalı-servis yok | ✅ | sadece 127.0.0.1 (kodda doğrulandı) |
| vLLM veya benzeri yerel servisleme | ✅ | vLLM 0.23, Qwen3-VL-8B-FP8 |

## 4. Temel Beklentiler
| Beklenti | Durum | Kanıt/Not |
|---|---|---|
| Multimodal anlama (sahne/zamansal/olay akışı) | ✅ | çok-kareli segment + bağlamsal yorumlama |
| Olay tespiti + anlamsal yorumlama (tür/önem/etki) | ✅ | severity + kategori + risk gerekçesi |
| Zamansal farkındalık + kritik an (başlangıç/gelişim/sonuç) | ✅ | zaman-damgası + pencere; özet akış anlatır |
| Türkçe doğal dil + özetleme (özlü, karar-destekleyici) | ✅ | özet 4.98/5, akıcılık 5.0 |
| Aksiyon önerisi + karar destek (risk + uygulanabilir + bağlam-tutarlı) | ✅ | aksiyon 4.71/5, risk-gerekçe 5.0 |
| Yapılandırılmış + açıklanabilir çıktı (JSON zorunlu) | ✅ | JSON %100 + severity/kategori/bbox-bölge/gerekçe |
| Yerel çalışma + bağımsızlık | ✅ | tam yerel |
| Model servisleme (düşük gecikme, kaynak-optimize, ~gerçek-zaman) | ✅ | ~1.6 s/vsn, segment paralel 3.2×, FP8 24GB, canlı-akış yolu |
| Performans/ölçeklenebilirlik/verimlilik | ⚠️ | gecikme+paralel ölçüldü; çok-yüksek-hacim daha az test |
| Ölçümleme + KPI tanımlama | ✅ | `benchmark/` (eval_clips/judge/judge_category/holistic/aggregate) |
| **Minimum statik yapı + akıllı pipeline (statik kural düşük puan)** | ✅ | model-tabanlı karar + **koşullu döngü** + öz-doğrulama + dinamik dispatch; keyword'ler yalnız tek-yönlü güvenlik-tabanı |
| Açık kaynak + tekrar üretilebilir + dokümante | ✅ | Apache-2.0, README, requirements-lock, docs/ |

## 6. Teslim Edilmesi Gerekenler
| Teslimat | Durum | Not |
|---|---|---|
| Çalışan proje kodu + kurulum adımları | ✅ | GitHub + README + requirements-lock |
| Demo videosu (maks 10 dk; bağlam-değişimi göster) | ⚠️ | senaryo hazır (`docs/demo_script.md`); **çekim takım-tarafı** |
| Dokümantasyon (mimari+diagram, framework+LLM, senaryo+mock, kurulum, zorluklar+çözümler, ek özellikler, ölçüm, ölçekleme) | ✅ | `docs/architecture.md` + `iyilestirmeler.md` (zorluklar/çözümler/ölçüm dolu) |
| Sunum (PDF **ve** PPTX) | ⚠️ | PPTX var (`docs/sunum.pptx`); **PDF export gerekli** |

## 7/12. Değerlendirme Eksenleri
| Eksen (%)| Durum | Kanıt |
|---|---|---|
| Fonksiyonellik (35) | Güçlü | uçtan-uca senaryo + mock-fonksiyon ajan-aracı + kararlı çalışma |
| Teknik/Mimari (35) | Güçlü | agent+tools+**memory**(sohbet+segment)+prompt; dinamik dispatch, bağlam yönetimi, çok-adımlı zincir, hata işleme; modüler kod |
| Otonomi/Zeka (20) | Güçlü | niyet anlama+reasoning, **inisiyatif + açıklayıcı soru**, beklenmedik duruma tepki (5.0/5), doğal Türkçe akış (çok-tur 5.0) |
| Yenilikçilik (10) | Orta-iyi | öz-doğrulama, grounding, hassasiyet modları, koşullu döngü; sunum/doküman kalitesi |

## 🔴 Açık uyum maddeleri (takım/web-tarafı)
- GitHub: **`BilisimVadisi2026` topic'i** + **"Türkiye Açık Kaynak Platformu" etiketi** + **takım adları** eklenmeli.
- **En az haftalık commit** (hâlihazırda 3 commit; düzenli devam).
- **Sunum PDF+PPTX** GitHub'a yüklenmeli (PDF export gerekli).
- Başvuru (t3kys.com, son 12 Temmuz) + takım tanıtım sunumu + Turnitin (proje bu dönem yeni olmalı).
