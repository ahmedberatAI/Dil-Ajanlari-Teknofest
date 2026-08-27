# HANDOFF — Olay ayrıştırma sorunu

**Tarih:** 2026-08-27 · **Dal:** `d34-isg-veri-kkd` · **HEAD:** `4ecd65c`
**Öncelik:** "tespit var ama HANGİ olay olduğu bilinmiyor" sorunu

Bu belge yeni bir oturumun **sıfırdan başlamaması** için yazıldı. Önce
**§1 ve §2** oku; §3 zaman kaybettirecek yolların listesidir.

---

## 1. SORUN — sayıyla

Sevk tabanı `benchmark/results/eval_20260825_114341.json` (n=197,
`facility_rules` KAPALI — **bu doğru tabandır**, aşağıdaki tuzağa bak):

| ölçüt | değer |
|---|---|
| TESPİT (olay üretildi mi) | **%95** |
| DOĞRU SINIF (hangi olay) | **66/99 = %67** |

Sınıf sınıf `isg_match`:

| sınıf | isabet |
|---|---|
| Forklift aşırı yük | 24/25 · **%96** |
| Pano kapağı açık | 23/24 · **%96** |
| Yetkisiz müdahale | 19/25 · %76 |
| **Yaya yolu ihlali** | **0/25 · %0** |

⚠️ **TUZAK:** `eval_20260825_144105.json` künyesinde `facility_rules_dolu: True`
taşır — o **reddedilmiş** enjeksiyon kolu. O arşivle ölçersen yaya yolu %44
görürsün ve yanılırsın. **Sevk tabanı `114341`.** Bu hata bir kez yapıldı.

**Olayların kaynağı:** %88,5 deterministik kural motoru · %11,5 serbest metin.
Serbest metinden gelen 21 olayın **21'i** kendi sınıfıyla eşleşmiyor.

**Sorunun karakteri:** metin doğru tehlikeyi **anlatıyor**, adı kayboluyor.

> *"…şiddetli alev ve yoğun siyah duman çıkışı ile yangın oluştu"* → kategori **Güvenlik**
> *"Metal boruların kayarak devrilmesi…"* (GT `falling load`) → **Kaza**

---

## 2. AÇIK OLAN TEK CİDDİ HİPOTEZ — ölçülmedi

**Piksel kaybı.** Küçültme zinciri ölçüldü ama **nedensellik sınanmadı**:

```
kaynak 1920x1080  ->  modele giden 768x432   OLCEK 0,40x
  yaya yolu cizgisi   ~25 px -> 10 px
  uzaktaki yelek      40x60  -> 16x24 px
  kucuk alev          60x50  -> 24x20 px
  pano kapagi boslugu 120x80 -> 48x32 px
```

Ayarlar: `fps_sample=2.0` · `max_frames_per_segment=12` · `frame_max_side=768`
· `frame_min_side=640` · JPEG q=88 (`dilajan/video.py:77`).

**En çok piksel isteyen işaret (yerdeki ince çizgi) en çok çöken sınıf.**
Bu korelasyon; nedensellik için aynı klipte çözünürlüğü değiştirip sonucun
değiştiğini göstermek gerekir.

### Yapılacak ölçüm — tasarım hazır

1. `Safe_Walkway_Violation`'dan tohumlu 12 klip, **artı kontrol için**
   `Opened_Panel_Cover`'dan 8 klip (orada %96, çökme YOK)
2. Her klip 3 çözünürlükte:
   `extract_timestamped_frames(yol, max_side=768 / 1080 / 1920)`
3. Aynı kapalı soru + `logprobs` → çözünürlük/doğruluk eğrisi
4. **Kontrol sınıfında aynı eğri var mı?** Yoksa etki çözünürlüğe özgü değildir
5. Karıştırıcıyı ayır: çözünürlüğü sabit tutup **yalnız JPEG kalitesini**
   değiştir (q=88 → q=98). İyileşme oradan geliyorsa çözünürlük değil kodlama.

**Bedel de ölçülmeli:** `son_kullanim` (`llm_client.py:248-253`) ile gerçek
token sayısı · K4 "gecikme 2-3× kabul" · ve en önemlisi **üç İSG matrisi
bozulur mu** (çözünürlük gözlem düzlemini de besliyor).

⚠️ 2026-08-10'da "çözünürlük/kare artırmak (aynı token, +0.69 puan)" **elenmiş**
(`docs/adlandirma_ab_2026-08-10.md:138-143`). **O ret, gözlem düzlemi ve üç İSG
kuralı YOKKEN yapıldı** — kapsamını `git log` ile doğrula. Kapsamıyorsa soru
hâlâ açıktır. "Aynı token" ifadesi de sınanmalı: model kareleri sabit token
bütçesine yeniden örnekliyorsa çözünürlük artışı **modele hiç ulaşmamış** olabilir.

---

## 3. DENENDİ ve REDDEDİLDİ — tekrar önerme

Anlatı düzleminde adlandırmayı düzeltmenin **altı** denemesi, hepsi ölçüldü:

| # | deneme | sonuç | belge |
|---|---|---|---|
| 1 | İngilizce prompt (27 klip, eşleşmiş, kontrol kümeli) | sessiz kaçırma **0/9**; yalnız yanlış-pozitifte 2/7 | `sonda_ingilizce_prompt_2026-08-26.md` |
| 2 | `d-35 a333f24` nedensel ayrım | yangın **0/6**; yanlış kavga 6/6→4/6 (**fayda**) | `olcum_d35_kollari_2026-08-26.md` |
| 3 | `d-35 ff46622` mutlak yangın önceliği + kavga eşiği | isabet **5/6→3/6** (**ZARARLI**) | aynı |
| 4 | tehdit merceği ablasyonu | alev/duman 4/4 ham betimlemede yok | workflow `wf_2ef0d0db-034` |
| 5 | kapalı ikili panel + logprob | aynı-set AUC 0,792 ama kavga 0,990 > yangın 0,777 | — |
| 6 | menülü olay paneli (16 yaprak) | **A %28,6 > B %21,4**, üç kapı düştü | `sonuc_olay_adi_paneli_2026-08-27.md` |

**§8 elenmiş liste** (`docs/iyilestirmeler.md`): VLM öz-doğrulama · ASK-HINT
ipucu listesi · ham YOLO nesne listesi · öz-tutarlılık N=3 · benign-gate ·
basit çoğunluk oylaması · slot medyan oylaması · yelekli<kişi sayma · slot
sorularını gerçek Türkçeye çevirme (MCC −0,199) · görünüme uyarlanmış sorular ·
`facility_rules`/`isg_lens` enjeksiyonu (isg_lens MCC −0,089, opFP 22→46) ·
kişi-başı kırpma · Set-of-Mark · yumuşak eşik · tespit coğrafi çiti.

**NOT — iki yanlış hatırlama düzeltildi:**
- "İnce taneli **ikili sorular**" elenmiş **değil**; "hâlâ açık" sütununda
  (`adlandirma_ab_2026-08-10.md:140`). Elenen şey ASK-HINT'in *ipucu listesiydi*.
- Mentörün kapalı-seçenek mimarisi 2026-08-19'da **geçersiz** ilan edildi:
  vLLM eski `guided_choice` alanını **sessizce yok sayıyormuş**. Doğru alan
  `structured_outputs.choice` (`llm_client.py:208`).

---

## 4. ÖLÇÜM ALTYAPISI — hazır, tekrar yazma

| araç | ne yapar |
|---|---|
| `benchmark/gorsel_dayanak.py` | iddia bazlı görsel doğrulama + **olumsuz denetim** |
| `benchmark/isg_rescore.py` | arşivden yeniden puanlama, **yeni koşum gerekmez** |
| `benchmark/isafety_mcq.py` | iSafetyBench MCQ (16 seçenek, zorunlu seçim) |
| `dilajan/gozlem.py::secim_dagilimi` | kısıtlı çözmenin **ilk-token logprob**'undan tam dağılım, ek çağrı YOK |
| `scratchpad/panel_asama1.py` | A/B/C kollu panel ölçümü |
| `scratchpad/cozunurluk_durum.py` | küçültme zinciri + piksel kaybı tablosu |
| `scratchpad/dogru_rapor.py` | 8 klipli **iki yönlü** panel (isabet + yanlış tehlike) |

**Hakemler dejenere — üç kez:** `judge_independent` RİSK ekseni 5,00 sıfır
varyans · `dialogue_hard` 15/15 = 5,00 · görsel dayanak hakemi olumsuz denetimde
**%37 yanlış-onay** (eşik %20, kapı ateşledi). **LLM hakemine dayanan ölçüt
kurma.** Deterministik sayaç kullan (`benchmark/tr_dil_kapisi.py`) veya
mutlaka olumsuz denetim koy.

---

## 5. MODEL MİMARİSİ — doğrulandı, bir istisna var

Serviste 10 model, **yalnız 3'ü aday**: `llm-large`, `llm-fast`, `vlm`.
`router` ve `guard` video sorusuna **boş** dönüyor; `embed`, `bge-m3-*`,
`rerank` sohbet ucu bile değil (NotFound). Bugün koşularak doğrulandı.

2026-08-24 karşılaştırması **MCC yazmamış** (yalnız `karar_orani`). Ham
cevaplardan bugün hesaplandı:

| slot | vlm | llm-large | llm-fast | sevkte |
|---|---|---|---|---|
| forklift | +0,548 | **+0,725** | — | `llm-large` ✅ |
| yelek | **+0,708** | +0,000 DEJENERE | +0,000 DEJENERE | `vlm` ✅ |
| pano | +0,000 **DEJENERE** (TP 0 · FN 22) | 49/49 kararsız | −0,086 | `vlm` ⚠️ |

Pano satırında üçü de çalışmıyor — ama **sevk edilen pano kuralı bu ikili
soruyu kullanmıyor**, `pano_koyuluk_0_10` ölçeğini kullanıyor (MCC +0,960).
Karşılaştırma sevk edilmeyen bir soru biçimini ölçmüş.

**Ders:** karar oranı ≠ doğruluk. Bu depoda bir kez karıştırıldı.

⚠️ **AÇIK KUSUR:** `graph.py`'de altı çağrı noktası (`perceive`, `reexamine`,
`policy_gate`×2, `reason`, `act`) `.gorev()` **çağırmıyor** — hepsi
`model_name`'e gidiyor. `gozlem.py:440` doğru yönlendiriyor. Yani göreve-göre
model **slot tarafında gerçek**, anlatı tarafında **kâğıt üstünde**. Künye ve
arayüz yönlendirmeyi **var gibi** raporluyor.

---

## 6. SEVK EDİLEN DURUM — bozmadan çalış

```
uc ISG kurali (eval_defense n=197):
  pano     TP23 FP0 FN1 TN25   MCC +0,960
  forklift TP24 FP2 FN1 TN23   MCC +0,881
  yetkisiz TP19 FP2 FN6 TN23   MCC +0,689
tesis kilidi ACIK (isg_gorus_imza, 8 imza, esik 0,60)
  alan disi FP 0,540 -> 0,120 · MCC +0,401 -> +0,780
Turkce kollari ACIK: ozet_terim_sozlugu + ozet_uslup_kisiti (BIRLIKTE)
41 test dosyasi, 0 hata
```

**Her yeni kol:** K2 varsayılan KAPALI + kapalıyken **bayt özdeş** · K1 çıktı
TAM 4 anahtar · K3 fail-open · üç matris **birebir** korunmalı ·
`category_match` düşmemeli.

**Türkçe kolları BİRLİKTE açılmalı** — Kol 4 tek başına kanonik terim oranını
0,571 → 0,158 düşürüyor; Kol 2 baskın çıkıp 0,944'e taşıyor.

---

## 7. ÖLÇÜM DİSİPLİNİ — bugün üç kez kurtardı

1. **Eşiği koşumdan ÖNCE yaz**, mekanik uygula. Panel aşama 1'de 10 dakikada
   durduk, 80 dakikalık koşuma girmedik.
2. **Olumsuz/bilgisiz kontrol koy.** Görsel dayanak hakemi %37 yanlış-onayla
   yakalandı; panel ölçümünde bilgisiz kontrol %0,0 çıkıp ölçümü doğruladı.
3. **Kapsam tavanını önce ölç.** Menü tavanı %84 bilindiği için düşük skorun
   "menü yetersiz" değil "seçim kötü" olduğu netleşti.
4. **Küme karıştırma.** `eval_defense` + `eval_full` aynı içeriği iki kez sayar.
   `eval` ⊂ `eval_big` (%100). Bkz. `data/EVAL_SETS.md` §K9.
5. **Eşiği ölçümün yapılacağı n'de türet.** 855 özetten türetilmiş eşik 60'a
   uygulanamaz; n=20'de "düşüş ≤ 3 puan" sıfır değişime izin verir.

---

## 8. SIRADAKİ ADIM — önerim

1. **Piksel kaybı nedensellik ölçümü** (§2). Tek gerçekten açık hipotez.
   ~1 saat. Kontrol sınıfı ve JPEG-kalitesi ayrımı **şart**.
2. Sonuca göre: **ROI kırpma** — `config`'te `panel_roi` / `yol_roi` alanları
   **zaten var**; ölçülüp ölçülmediklerini ve açık mı kapalı mı olduklarını
   koddan doğrula. ROI = çözünürlük kaybetmeden büyütme.
3. `d-35` birleştirme: `a333f24` + `1ecae92` **al** (determinizm + yanlış kavga
   6/6→4/6), `ff46622` **alma** (isabet 5/6→3/6). `1ecae92` öncesi üç matrisin
   korunduğu koşularak doğrulanmalı.
   Worktree: `C:\Users\omen\Desktop\DilAjanlari_d35`

**Yapma:** anlatı düzleminde yedinci prompt denemesi. Altısı ölçüldü, altısı
da kaybetti.

---

## 9. ORTAM

```
Windows + WSL2. YEREL GPU YASAK (config.yerel_cihaz zorluyor).
Uzak servis: https://evren-llmapi.ssyz.org.tr/v1  (llm-large, llm-fast, vlm)
Python: wsl.exe -d Ubuntu-24.04 -e bash -c 'cd /mnt/c/Users/omen/Desktop/DilAjanlariTeknofest && /home/omen/teknofest/.venv/bin/python -u <betik>'
Arayuz: python app.py -> http://127.0.0.1:7860 (Gradio)

TUZAKLAR (§9 kabuk):
  $VAR ve $(...) Git Bash -> WSL gecisinde bozulur
  heredoc icinde \n ve \b GERCEK karakter olur, Python dizgesini kirar
  PowerShell 5.1 UTF-8'i ANSI okur; uzun tire (—) dizgeyi kirar -> ASCII yaz
  PowerShell'de && ve || YOK
```

**Veri:** `data/` gitignore'lu. Kaynak bağlantıları
`docs/veri_indirme_linkleri.md`. `eval_kanonik`/`eval_full`/`eval_genelleme`
artık **sabit bağ** (2026-08-26'da sembolik bağdan çevrildi; Windows sembolik
bağı çözemiyordu, 1449 klip görünmezdi).
