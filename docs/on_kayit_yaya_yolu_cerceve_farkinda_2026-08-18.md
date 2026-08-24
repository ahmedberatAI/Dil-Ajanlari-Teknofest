# ÖN-KAYIT — Yaya yolu, ÇERÇEVE-FARKINDA İKİNCİ DENEME (D39-B2)

**Tarih:** 2026-08-18 · **Sonuçlara bakılmadan önce yazıldı.**
İlk deneme (`on_kayit_yaya_yolu_geofence_2026-08-18.md`) **RET** edildi: R1
"kimsenin ayağı yeşilde değil" havuzlanmış MCC +0,506 verdi ama A_GENİŞ grubu
içinde MCC +0,117 (p=0,52, dejenere, doğruluğu hep-ihlal tabanına EŞİT).
Kısayol: çerçeve tek başına %72,9 doğruluk veriyor, R1 de tam %72,9.

## Bu denemenin tek hipotezi

R1'in kusuru **ölçek duyarlılığıydı**: A_GENİŞ'te yol uzak ve küçük, "ayak tam
maskenin üstünde mi" ikili testi orada fiilen hep 0. Ölçekten arındırılmış bir
yakınlık ölçütü çerçeve etkisini **fiziksel olarak** telafi etmeli:

    u(kişi, kare) = ayak_mesafe(px) / kutu_yüksekliği(px)     [birim: "boy"]

Hem mesafe hem boy 1/derinlik ile ölçeklenir; oranı **boyutsuzdur**.

## Ölçüm ÖNCESİ, ETİKETSİZ çerçeve-nötrlük kanıtı (adım 0'da koşuldu)

`u` eşik geçme oranları, **etiketlere bakılmadan**, çerçeve grubuna göre:

| yüklem | A_GENİŞ | B_YAKIN | oran B/A |
|---|---|---|---|
| `u = 0` (**eski R1'in ilkeli**: ayak tam maskede) | 0,007 | 0,039 | **5,6×** |
| `u ≤ 0,10` | 0,043 | 0,083 | 1,9× |
| **`u ≤ 0,25`** | **0,098** | **0,118** | **1,2×** |
| `u ≤ 0,50` | 0,173 | 0,141 | 0,8× |
| `u ≤ 1,00` | 0,224 | 0,188 | 0,8× |

Yani `θ ∈ [0,25 · 1,00]` bandında ilkel yüklem **çerçeveye neredeyse duyarsız**.
Bu, etiket görmeden ölçüldü ve ızgaranın merkezini belirledi. Kısayol kanalı
**kapatılmaya çalışılıyor**, kapandığı garanti edilmiyor — ölçülecek.

## Ön-kayıtlı kural ailesi — SONUÇLARA BAKMADAN sabitlendi

Veri: `<SCRATCH>/yol_oznitelik_yenimaske.json` (48 klip × 16 kare, RT-DETRv2
kutuları, jüri kazananı `maske_sari_sinir` maskesi, α=0,914 ayak noktası).

| # | kural | okunuşu |
|---|---|---|
| **S1(θ)** | hiçbir kişi-karede `u < θ` yok → **İHLAL** | "kimse yola yakın değil" |
| **S2(θ,τ)** | `ρ = (u<θ olan kişi-kare)/(tüm kişi-kare) < τ` → **İHLAL** | oransal doluluk |
| **S3(θ,τ)** | izlek başına `occ(t)=(u<θ kare)/(t'nin kareleri)`; `max_t occ(t) < τ` → **İHLAL** | "hiçbir BİREY yolu kullanmıyor" |
| **S4(θ,τ,μ)** | yalnız **yürüyenler** (`hareket(t) ≥ μ boy`) arasında `max occ < τ` → **İHLAL**; hiç yürüyen yoksa → **NORMAL** | tezgâhtaki işçiyi eler |

`hareket(t)` = izleğin ayak noktasının toplam yer değiştirmesi / medyan boyu (boyutsuz).
İzlek kurma: ardışık örneklenmiş karelerde açgözlü ayak-noktası eşlemesi,
kapı **2,0 boy** — bu **sabittir, ızgaraya dahil değildir** (çokluluk şişirmemek için).

### Eşik ızgarası — DIŞINA ÇIKILMAYACAK

```
θ ∈ {0,10 · 0,25 · 0,50 · 1,00 · 2,00}      (boy)
τ ∈ {0,10 · 0,25 · 0,50}
μ ∈ {0,5 · 1,0 · 2,0}                        (boy)
```
Nominal yapılandırma: S1=5, S2=15, S3=15, S4=45 → **80**.
**Ayırt edilebilir** (tahmin vektörü tekilleştirilmiş) sayı rapor edilecek —
ilk denemedeki "15 yapılandırmanın 7'si gerçek" dersi.

## KARAR ÖLÇÜTÜ — ilan edildi, değiştirilmeyecek

**BİRİNCİL:** A_GENİŞ grubu **İÇİNDE** (n=30, 21 İHLAL / 9 NORMAL):

1. **MCC ≥ +0,35**, **ve**
2. **p < 0,05**, burada p = **maks-istatistiği permütasyon** p-değeri
   (A_GENİŞ içinde etiket permütasyonu, 20 000 tekrar, ızgaranın TAMAMI üzerinden
   maksimum MCC alınarak) → çoklu-karşılaştırma **içerilmiş** olur.

**DEJENERELİK KAPISI** (ilk denemenin batış sebebi, şart):

3. A_GENİŞ'te kuralın "İHLAL" deme oranı **[0,15 · 0,85]** aralığında olmalı.
4. A_GENİŞ doğruluğu, önemsiz çoğunluk sınıflandırıcısını (**0,700**) **aşmalı**.

**PLASEBO KAPISI** (§4 zorunlu):

5. **Mekânsal plasebo:** aynı kural, gerçek maskenin (a) yatay aynası,
   (b) dikey aynası, (c) 180° döndürülmüşü ve (d) aynı alanlı rastgele
   yerleştirilmiş bölge ile yeniden koşulur. Plasebolardan herhangi biri
   A_GENİŞ'te gerçek maskenin MCC'sinin **%70'ine** ulaşırsa → **RET**.
6. **Öznitelik plasebosu:** `u` değerleri klip içinde karıştırılır (marjinaller
   korunur, kişi↔yol ilişkisi bozulur). Kazanç kalırsa → **RET**.

**RAPORLAMA ŞARTI:** her kural için TP/FP/FN/TN, MCC, Wilson %95 GA,
grup-İÇİ sayılar. Havanlanmış tek sayı **manşet yapılmayacak**. B_YAKIN'de
yalnızca 4 pozitif var → tek başına kanıt sayılmaz, yalnızca bilgi olarak verilir.

## Geri çekilme sözü

Bu ölçütlerden **herhangi biri** geçilmezse kural **REDDEDİLİR** ve "çalışmıyor"
diye belgelenir. Eşikler sonradan gevşetilmeyecek. Negatif sonuç, veri setinin
sınırını belgelediği için değerlidir.

---

# SONUÇ — **RET.** Birincil ölçüt geçildi, **plasebo kapısı geçilemedi.**

**Tarih:** 2026-08-18, ön-kayıttan sonra · Sayılar olduğu gibi duruyor.

## 1. Izgara mekanik uygulandı

80 nominal yapılandırma → A_GENİŞ içinde **53'ü ayırt edilebilir**.
(İlk denemenin "15 yapılandırmanın 7'si gerçek" kusurunu **tekrarladım**; aşağıda §5.)

### A_GENİŞ içinde ilk 5 (n=30 · 21 İHLAL / 9 NORMAL · taban 0,700)

| kural | TP | FP | FN | TN | MCC | doğruluk | "İHLAL" deme oranı |
|---|---|---|---|---|---|---|---|
| **S4 θ=0,25 τ=0,50 μ=0,5** | 14 | **0** | 7 | 9 | **+0,612** | 0,767 | 0,467 |
| S4 θ=0,10 τ=0,25 μ=0,5 | 15 | 1 | 6 | 8 | +0,554 | 0,767 | 0,533 |
| S2 θ=0,25 τ=0,10 | 18 | 3 | 3 | 6 | +0,524 | 0,800 | 0,700 |
| S4 θ=0,10 τ=0,10 μ=0,5 | 14 | 1 | 7 | 8 | +0,509 | 0,733 | 0,500 |
| S4 θ=0,25 τ=0,50 μ=1,0 | 14 | 1 | 7 | 8 | +0,509 | 0,733 | 0,500 |

### Seçilen kuralın tam raporu

| kesit | n | TP | FP | FN | TN | MCC (önyükleme %95 GA) | duyarlılık (Wilson) | özgüllük (Wilson) |
|---|---|---|---|---|---|---|---|---|
| **A_GENİŞ** | 30 | 14 | 0 | 7 | 9 | **+0,612** [+0,408 · +0,818] | 0,667 [0,454·0,828] | 1,000 [0,701·1,000] |
| B_YAKIN | 18 | 2 | 1 | 2 | 13 | +0,478 [−0,125 · +1,000] | 0,500 [0,150·0,850] | 0,929 [0,685·0,987] |
| havuz | 48 | 16 | 1 | 9 | 22 | +0,623 [+0,421 · +0,808] | 0,640 [0,445·0,798] | 0,957 [0,790·0,992] |

Cochran-Mantel-Haenszel (çerçeveye katmanlı): **χ² = 12,182 · p = 0,0005**.
Maks-istatistiği permütasyon (A_GENİŞ, 53 yapılandırma, 20 000 tekrar): **p = 0,0048**.

**Ön-kayıtlı birincil ölçüt (MCC ≥ +0,35 · p < 0,05) GEÇİLDİ.**
**Dejenerelik kapısı da GEÇİLDİ**: "İHLAL" deme oranı 0,467 ∈ [0,15·0,85];
doğruluk 0,767 > taban 0,700. İlk denemedeki çöküş (A_GENİŞ MCC +0,117, %93 dejenerelik)
**gerçekten onarıldı** — çerçeve kısayolu kapatıldı.

## 2. Ama PLASEBO KAPISI ÇÖKTÜ — belirleyici sayı

Aynı ızgara, aynı ayar hakkı, sahte bölgeler. Her varyant **kendi** permütasyon null'una karşı:

| varyant | maks A_GENİŞ MCC | ayırt edilebilir yapıl. | kendi null q95 | p | |
|---|---|---|---|---|---|
| **gerçek** | +0,612 | 53 | +0,488 | **0,0048** | ANLAMLI |
| p_yatay (yatay ayna) | +0,428 | 46 | +0,509 | 0,148 | — |
| **p_dikey (dikey ayna)** | **+0,655** | 56 | +0,524 | **0,0045** | **ANLAMLI** |
| p_rot180 | +0,218 | 35 | +0,505 | 0,699 | — |
| p_otele (rastgele öteleme) | +0,386 | 55 | +0,524 | 0,320 | — |
| p_karış (klip-içi mesafe karıştırma) | +0,535 | 59 | +0,535 | 0,0515 | — |

**plasebo / gerçek = 0,655 / 0,612 = 1,07.**
Ön-kayıt: *"herhangi biri %70'ine ulaşırsa → RET"*. Ulaşan **%107**.
Üstelik dikey ayna **kendi başına da anlamlı** (p=0,0045) — yani yolun **gerçek konumu
sinyalin kaynağı olarak gösterilemedi**. Yaya yolunu görüntüde baş aşağı çevirin,
kural aynı işi yapar.

## 3. Maskesiz taban çizgisi — asıl mahcup edici sayı

Maskeyi **tamamen atın**, yalnız kişilerin görüntüdeki konum istatistiklerini kullanın
(A_GENİŞ, aynı 17-eşik maksimizasyon serbestliğiyle):

| öznitelik (maske YOK) | TP | FP | FN | TN | MCC |
|---|---|---|---|---|---|
| **ayak y-yayılımı `sy` ≥ 0,143** | 20 | 4 | 1 | 5 | **+0,582** |
| ayak x-yayılımı `sx` < 0,354 | 16 | 2 | 5 | 7 | +0,505 |
| medyan ayak x `mx` < 0,262 | 20 | 5 | 1 | 4 | +0,488 |
| medyan ayak y `my` < 0,423 | 5 | 0 | 16 | 9 | +0,293 |

Yaya yolu maskesinin **tüm katkısı +0,612 − +0,582 = +0,030**. Bu, ölçüm disiplininin
5. maddesine göre (25-30 klipte +0,05 gürültüdür) **sıfırdan ayırt edilemez**.
`sy` ayrımı zaten zayıf: İHLAL 0,176±0,029 vs NORMAL 0,146±0,023 — **1σ örtüşme**.

## 4. Hareket terimi ÖLÜ — kendi tasarım kusurum

`μ` parametresi tamamen atıl: 48 klibin **48'inde** `hareket ≥ 3,0 boy` olan izlek var,
yani S4'ün *"yürüyen yoksa → NORMAL"* kolu **hiç ateşlenmedi**. "Tezgâhtaki işçiyi
eleyeceğim" gerekçesi ölçümde karşılık bulmadı:

| maskesiz saf hareket kuralı | TP | FP | FN | TN | MCC |
|---|---|---|---|---|---|
| yürüyen var (μ = 0,25 … 3,0, **hepsi**) | 21 | 9 | 0 | 0 | **0,000** |
| kare başı kişi ≥ 2 … ≥ 8 | — | — | — | — | −0,12 … +0,05 |
| izlek sayısı ≥ 10 … ≥ 30 | — | — | — | — | −0,11 … +0,17 |

## 5. İlk denemenin kusurunu TEKRARLADIM

Izgarayı 80 yapılandırma diye ilan ettim; A_GENİŞ'te yalnızca **53'ü** ayırt edilebilir.
`μ`'nün üç değeri büyük ölçüde aynı tahmini veriyor. Permütasyon testi maks-istatistiği
üzerinden kurulduğu için p-değeri **bundan zarar görmedi**, ama ön-kayıtta
"80 yapılandırma" demem yanlıştı. İlk denemenin dersini **tam öğrenmemişim**.

## 6. Dürüstlük notu — kararı DEĞİŞTİRMEYEN karşı-kanıt

**Eşleşmiş yapılandırmada** (θ=0,25 τ=0,50 μ=0,5 sabit, yalnız bölge değişiyor):

| varyant | TP | FP | FN | TN | MCC |
|---|---|---|---|---|---|
| gerçek | 14 | 0 | 7 | 9 | **+0,612** |
| p_otele | 21 | 8 | 0 | 1 | +0,284 |
| p_dikey | 17 | 5 | 4 | 4 | +0,263 |
| p_yatay | 18 | 6 | 3 | 3 | +0,218 |
| p_rot180 | 14 | 5 | 7 | 4 | +0,106 |
| p_karış | 17 | 7 | 4 | 2 | +0,036 |

Bu tabloda gerçek maske plaseboları **açık ara** yeniyor (oran 0,46 < 0,70).
**Ama bu karşılaştırma yanlıdır**: eşikler 53 yapılandırma içinden *gerçek maskeye göre*
seçildi, plaseboya hiç ayar hakkı verilmedi. Ön-kayıt bilerek **adil olanı**
(her varyanta aynı ızgara serbestliği) kapı yaptı. **Eşiği sonradan gevşetmiyorum.**
Bu tablo, "gelecekte daha çok veriyle bakmaya değer" notu olarak kalır — kanıt olarak değil.

## Karar

**REDDEDİLDİ.** Dağıtılmayacak.

Ölçekten arındırma **kendi işini yaptı** (çerçeve kısayolu kapandı: A_GENİŞ MCC
+0,117 → +0,612, dejenerelik 0,93 → 0,47). Ama **ikinci bir kısayol** ortaya çıktı:
kural, yaya yoluna yakınlığı değil, kişilerin **görüntüdeki genel konum dağılımını**
ölçüyor. Dikey ayna plasebosu gerçek maskeyi geçiyor ve maskesiz konum istatistiği
+0,582'ye ulaşıyor.

**Bu veri setinde 30 klip, bir geofence kuralını konum artefaktından ayırmaya yetmiyor.**
Ölçü budur ve veri setinin sınırıdır.
