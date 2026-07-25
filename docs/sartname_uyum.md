# Şartname Uyum Matrisi (2026 TEKNOFEST TYDA — 3. Senaryo)

Gerçek şartname metnine (19 sayfa) göre madde-madde uyum denetimi. ✅ karşılandı · ⚠️ kısmi/takım-tarafı · 🔴 eksik.

> Buradaki tüm sayılar [`docs/olcum_durustlugu.md`](olcum_durustlugu.md) ile hizalıdır
> (kanonik değerler + Wilson %95 güven aralıkları + ölçüm sınırlarımız).

## 3. Problem Tanımı — zorunlu çıktılar
| Gereksinim | Durum | Kanıt |
|---|---|---|
| Video girdisi al + içeriği analiz et | ✅ | `ingest`+`perceive` (PyAV kare/segment, VLM analiz) |
| Olay/kişi/riskli durum tespiti | ✅ | iki-aşamalı algı; senaryo recall **18/18** [%82–%100], grenli UCF **44/48** [%80–%97] |
| Kritik anları zaman bilgisiyle belirle | ✅ | olay `time` + zaman-pencereleri `[00:30–00:50]` |
| Kısa anlaşılır Türkçe özet | ✅ | özet kalitesi **4.62 ± 0.53** (bağımsız Gemma hakem; 30 klip × 3 eksen) |
| Operatöre aksiyon önerileri | ✅ | `actions[öncelik,gerekçe]`, **4.74 ± 0.44** (18 klip × 4 eksen) |
| Yapılandırılmış JSON | ✅ | `to_sartname_dict` — mock örnekle birebir; şema ihlali gözlenmedi |
| Offline/yerel + dış-API/kapalı-servis yok | ✅ | sadece 127.0.0.1 (kodda doğrulandı) |
| vLLM veya benzeri yerel servisleme | ✅ | vLLM 0.23, Qwen3-VL-8B-FP8 |

## 4. Temel Beklentiler
| Beklenti | Durum | Kanıt/Not |
|---|---|---|
| Multimodal anlama (sahne/zamansal/olay akışı) | ✅ | çok-kareli segment + bağlamsal yorumlama |
| Olay tespiti + anlamsal yorumlama (tür/önem/etki) | ✅ | severity + kategori + risk gerekçesi |
| Zamansal farkındalık + kritik an (başlangıç/gelişim/sonuç) | ✅ | zaman-damgası + pencere; özet akış anlatır |
| Türkçe doğal dil + özetleme (özlü, karar-destekleyici) | ✅ | özet **4.62 ± 0.53** (bağımsız Gemma), diyalog **5.00** (7+4 senaryo, std 0 → tavan-doygun) |
| Aksiyon önerisi + karar destek (risk + uygulanabilir + bağlam-tutarlı) | ✅ | aksiyon **4.74 ± 0.44**, risk-gerekçe **5.00 ± 0.00** (tavan-doygun) |
| Yapılandırılmış + açıklanabilir çıktı (JSON zorunlu) | ✅ | şema ihlali gözlenmedi + severity/kategori/bbox-bölge/gerekçe + `decision_trace` |
| Yerel çalışma + bağımsızlık | ✅ | tam yerel |
| Model servisleme (düşük gecikme, kaynak-optimize, ~gerçek-zaman) | ✅ | **0.86 s/vsn** ort (n=6, 0.44–3.75); ×4 eşzamanlı 4.2 video/dk; FP8 ~21 GB |
| Performans/ölçeklenebilirlik/verimlilik | ⚠️ | gecikme + ×4 eşzamanlılık **ölçüldü ve loglandı**; çok-GPU / çok-yüksek-hacim **ölçülmedi** |
| Ölçümleme + KPI tanımlama | ✅ | `benchmark/` (eval_clips/judge/judge_category/holistic/aggregate) + **`stats_utils`** (Wilson GA, ondalık disiplini, pseudo-replikasyon uyarısı) |
| **Minimum statik yapı + akıllı pipeline (statik kural düşük puan)** | ✅ | model-tabanlı karar + **koşullu döngü** + öz-doğrulama + dinamik dispatch; keyword'ler yalnız tek-yönlü güvenlik-tabanı |
| Açık kaynak + tekrar üretilebilir + dokümante | ✅ | Apache-2.0, README, requirements-lock, docs/ |

## 6. Teslim Edilmesi Gerekenler
| Teslimat | Durum | Not |
|---|---|---|
| Çalışan proje kodu + kurulum adımları | ✅ | GitHub + README + requirements-lock |
| Demo videosu (maks 10 dk; bağlam-değişimi göster) | ⚠️ | senaryo hazır (`docs/demo_script.md`); **çekim takım-tarafı** |
| Dokümantasyon (mimari+diagram, framework+LLM, senaryo+mock, kurulum, zorluklar+çözümler, ek özellikler, ölçüm, ölçekleme) | ✅ | `architecture.md` (koşullu kenar dâhil diyagram) + `iyilestirmeler.md` + **`olcum_durustlugu.md`** + `veri_kaynaklari.md` |
| Veri seti: herkese açık link + tekrar üretilebilirlik | ⚠️ | tüm setler için indirici script var (FIRESENSE dâhil, yeni); **mevcut kliplerin script çıktısıyla birebir eşleştiği doğrulanmadı** |
| Sunum (PDF **ve** PPTX) | ⚠️ | PPTX var (`docs/sunum.pptx`); **PDF export gerekli** |

## 7/12. Değerlendirme Eksenleri
| Eksen (%)| Durum | Kanıt |
|---|---|---|
| Fonksiyonellik (35) | Güçlü | uçtan-uca senaryo + mock-fonksiyon ajan-aracı + kararlı çalışma; recall/FP `k/n`+GA ile |
| Teknik/Mimari (35) | Güçlü | agent+tools+**memory**(sohbet+segment)+prompt; **koşullu kenar**, dinamik dispatch, altı düğümde try/except + segment-içi fail-open, çağrı-yerel kayıt (paralel-güvenli), araç-argümanı onarımı; modüler kod |
| Otonomi/Zeka (20) | Güçlü | niyet anlama+reasoning, **inisiyatif + açıklayıcı soru**, beklenmedik duruma tepki, doğal Türkçe akış (bağımsız hakem 5.00; **n=7+4, std 0 → tavan-doygun**) |
| Yenilikçilik (10) | Orta-iyi | öz-doğrulama, grounding, hassasiyet modları, koşullu döngü; **kendi ölçümünü denetleyip düzeltme** (üç seviyeli recall, Wilson GA, mükerrer-klip düzeltmesi) |

## 🔴 Açık uyum maddeleri (takım/web-tarafı)
- GitHub: **`BilisimVadisi2026` topic'i** + **"Türkiye Açık Kaynak Platformu" etiketi** + **takım adları** eklenmeli.
- **En az haftalık commit** (yarışma penceresinde düzenli devam edilecek).
- **Sunum PDF+PPTX** GitHub'a yüklenmeli (PDF export gerekli).
- Başvuru (t3kys.com, son 12 Temmuz) + takım tanıtım sunumu + Turnitin (proje bu dönem yeni olmalı).

## 🟡 Açık ölçüm maddeleri (bizim tarafımız — dürüstçe listeleniyor)
- **Senaryo seti yeniden ölçülecek:** donmuş-PNG düşme klipleri gerçek videolarla değiştirildi;
  yayınlanan senaryo rakamları eski kompozisyona ait.
- **Temiz holdout koşusu:** `eval_big` ayrık `eval_tune`/`eval_holdout`'a bölündü; holdout ölçümü henüz koşulmadı.
- **Kalite skorları kare-kanıtlı hakemle yeniden koşulacak:** hakem betiği üç aileye ayrıldı
  ([A] ground-truth'a olgusal dayanaklılık · [B] iç-tutarlılık · [C] opsiyonel kare-kanıtı) ama
  **yayınlanan 4.62/4.74/5.00 hâlâ eski yalnızca-metin koşusundan** (paketin en denetlenmemiş iddiası).
- **Hedef domain ölçümü:** `data/eval_defense` (20 anomali + 20 normal, 1080p gerçek tesis) üretildi
  ama **henüz hiç koşulmadı**; tesis-içi performansımız hâlâ ölçülmemiş durumda.
- **Gece/IR/termal kapsam yok** — bu koşullarda hiçbir ölçümümüz bulunmuyor.

Gerekçeler ve sayılar: [`docs/olcum_durustlugu.md`](olcum_durustlugu.md) §6.
