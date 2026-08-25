# ÖN KAYIT — yelek sorusu ROI kırpmasında (referans sorununa saldırı)

Tarih: **2026-08-25**, kod yazılmadan ve koşumdan **ÖNCE**. Dal: `d34-isg-veri-kkd`
İlgili: `docs/yumusak_esik_sonuc_2026-08-25.md` §4

## 0. Çözülmeye çalışılan şey

`Unauthorized_Intervention` +0,689, altı kaçırma. Bu kaçırmaların kök nedeni
artık **ölçülmüş** durumda (kalibrasyon koşumundan):

| grup | klipler | ölçülen | tanı |
|---|---|---|---|
| **A** | `1_te5`, `1_tr18`, `1_tr84` | `P(kişi ≥ 1)` = 0,101 / 0,418 / 0,358 | geniş plan; kişi çözünürlük altında |
| **B** | `1_tr42`, `1_tr61`, `1_tr81` | `yelek=VAR` güveni %92–99,7 | model **emin ve haklı** — **yanlış kişiye bakıyor** |

B grubu bir kalibrasyon değil **referans (grounding)** sorunudur.

## 1. Kişi-başına kırpma kolu — ÖLÇÜLDÜ ve AÇILMIYOR

Kişi-başına kırpma (CPU'da tespit + kutu başına soru) fizibilitesi ölçüldü.
**Model çağrılmadı**, yalnızca dedektör:

| grup | klip | CPU tespiti (3 kare) | en yakın kutu | gereken büyütme |
|---|---|---|---|---|
| A | `1_te5` | **0 kişi** | — | — |
| A | `1_tr84` | **0 kişi** | — | — |
| A | `1_tr18` | 4 kişi | %3 × %12 kare | **22,4x** |
| B | `1_tr42` | 12 kişi | örtüşme 0,334 | 6,9x |
| B | `1_tr61` | 13 kişi | örtüşme 0,246 | 6,3x |
| B | `1_tr81` | 11 kişi | örtüşme 0,552 | 12,1x |

**A grubu için kol ölü:** dedektör de kimseyi görmüyor. Yani "geniş planda kişi
seçilemiyor" tanısı VLM'e özgü değil; o ölçekte kişi gerçekten çözünürlük
altında. Hata analizinin *"soru tasarımıyla çözülemez"* hükmü genişletiliyor:
**tespitle de çözülemez.**

**B grubu için açılmıyor:** 11–13 kişi arasından "makinedeki kişi"yi seçmek
yeni bir tahmin noktası yaratır. §8'de reddedilen `yelekli < kişi` kuralı tam
olarak bu belirsizlikten patlamıştı (MCC +0,250, FP 3→13). Belirsizliği
modelden alıp kendi buluşuma taşımak ilerleme değildir.

## 2. Açılan kol — ROI'YE SORMAK (seçici YOK, dedektör YOK)

Kural zaten *"makinenin/panonun başında duran kişi"* diyor. `panel_roi_vlm`
**makine başını zaten tanımlıyor** ve pano slotunda +0,960 veriyor.

**Kol:** yelek slotuna `roi_alani="panel_roi_vlm"` verilir. Kırpma makine
bölgesini içerdiği için *"başındaki kişi"* referansı **yapısal olarak** tekleşir
— diğer 10-12 kişi kadraj dışında kalır. Ek soru yok, dedektör yok, CPU yok.

Maliyet: yelek slotu farklı bir (ROI, kapsam) grubuna düşer → bir ek video
kodlaması ve bir ek oturum. VLM **soru sayısı değişmez**.

## 3. KABUL ÖLÇÜTÜ

Referans: `Unauthorized_Intervention` sert kip **+0,689** (TP19 FP2 FN6 TN23),
saha kesinliği **0,237**.

**KABUL — üçü birden:**
1. çift içi MCC ≥ **+0,78**
2. saha kesinliği ≥ **0,237** (düşmeyecek)
3. diğer iki çiftin karışıklık matrisi **birebir** korunacak
   (`TP24/FP2/FN1/TN23`, `TP23/FP0/FN1/TN25`)

Üçünden biri sağlanmazsa **RET**. Ara değerler için pazarlık yok.

**Neden +0,78:** B grubunun üçünü de kurtarmak TP19→22, FN6→3 demek; FP sabit
kalırsa MCC +0,801 olur. +0,78 eşiği "üçünden en az ikisini kurtar ve hiçbir
şeyi bozma" seviyesidir. Bunun altındaki bir kazanç, ek kodlama maliyetini ve
sevk edilen bir kurala dokunma riskini karşılamaz.

## 4. ÖN-RET KAPILARI (sonuca bakmadan)

| # | kapı | eşik |
|---|---|---|
| a | **DEJENERELİK** | yelek cevaplarının ≥ %90'ı aynı seçenek olursa RET |
| b | **KAPI ÇÖKMESİ** | `makine_basinda_kisi` ROI içinde ölçülüp `P(kişi≥1)` çoğunlukta 0 çıkarsa (ön koşul kapanır, kural hiç ateşlemez) RET |
| c | **BULAŞMA** | diğer iki çiftin matrisi saparsa ölçüm geçersiz; önce sapmanın kaynağı bulunur |

Kapı (b) gerçek bir risk: ROI kırpması makinenin **önündeki** kişiyi kadraj
dışında bırakabilir. Ön koşul slotu da aynı ROI'ye taşınmalı mı, taşınmamalı
mı — bu **iki ayrı kol** olarak ölçülür ve ikisi de önceden ilan edilir:

- **B1 (BİRİNCİL):** yalnız yelek slotu ROI'ye taşınır, ön koşul tam karede kalır
- **B2 (İKİNCİL):** yelek + ön koşul birlikte ROI'ye taşınır

İkincil kol geçer birincil geçmezse bu **sevk kararı değildir**; teyit koşumu
adayıdır.

## 5. Ne olursa ne yapılacak

| sonuç | eylem |
|---|---|
| B1 üç kapıyı da geçer | sevke alınır, sert tam-kare kolu yedek olarak kodda kalır |
| yalnız B2 geçer | teyit koşumu adayı; tek başına sevk YOK |
| ön-ret kapılarından biri kapanır | anında RET, sebep yazılır |
| hepsi RET | `Unauthorized_Intervention` +0,689'da kalır; A grubunun bu veriyle çözülemez olduğu kayda geçer |

Hiçbir eski skor silinmeyecek.

## 6. Sıra ve zaman

Bu kol, yaya yolu koşumu (`docs/on_kayit_yaya_zemin_2026-08-25.md`)
**bittikten sonra** koşulacak — servis paylaşımlı, iki değerlendirme aynı anda
koşturulmuyor. Yaya yolu daha yüksek ödüllü (isg_match 0,646 → 0,865 potansiyeli);
bu kolun tavanı isg_match'e yaklaşık +0,03.
