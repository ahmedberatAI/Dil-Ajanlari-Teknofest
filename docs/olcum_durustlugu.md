# Ölçüm Dürüstlüğü — Kanonik Değerler ve Ölçüm Sınırlarımız

> **Bu belge projenin tek doğruluk kaynağıdır.** README, `performans_raporu.md`,
> `sartname_uyum.md`, `sunum_iskeleti.md`, `demo_script.md` ve `iyilestirmeler.md`
> içindeki her sayı buraya hizalanmıştır. Bir yerde farklı bir sayı görürseniz
> **buradaki geçerlidir** ve bu bir hatadır — lütfen bildirin.
>
> Amaç: iddiayı kanıtla eşlemek. Elimizde kayıtlı artefakt olmayan hiçbir rakam
> manşete çıkmaz; küçük örneklemde nokta-değer tek başına raporlanmaz.

Son güncelleme: 2026-07-25 · Yöntem modülü: `benchmark/stats_utils.py`

### Önce bunu okuyun: hangi düzeltme araçta, hangisi rakamlarda?

Bu turda bulunan ölçüm kusurlarının bir kısmı **kodda/veride giderildi ama sonuçlar henüz
yeniden üretilmedi** (bu turda model sunucusu kapalıydı). Karışıklığı önlemek için ayırıyoruz:

| Kusur | Araç/veri düzeltmesi | **Rakamlara yansıdı mı?** |
|---|---|---|
| Mükerrer klip sayımı (3 seviyeli recall) | ✔ | ✔ **Evet** — 81 ölçüm → 51 bağımsız klip (§3) |
| Kanıtsız throughput iddiası | ✔ | ✔ **Evet** — geri çekildi, +13.5% kanonik (§5) |
| Ondalık/GA/pseudo-replikasyon hijyeni | ✔ `stats_utils.py` | ✔ **Evet** — tüm belgeler (§0) |
| Payda hataları (mükerrer normal klipler) | ✔ | ✔ **Evet** — 7 ve 15 (§4) |
| `eval ⊂ eval_big` sızıntısı | ✔ ayrık `eval_tune`/`eval_holdout` | ✖ **Hayır** — holdout koşusu bekliyor (§6.9) |
| Donmuş-PNG düşme klipleri | ✔ gerçek videolarla değiştirildi | ✖ **Hayır** — senaryo seti yeniden ölçülecek (§6.7) |
| Dayanaksız kalite hakemi | ✔ üç metrik ailesi + kare-kanıtı | ✖ **Hayır** — skorlar hâlâ eski koşudan (§6.3) |
| Hedef domainde pozitif yok | ✔ `eval_defense` (20+20, 1080p) | ✖ **Hayır** — hiç koşulmadı (§6.5) |

---

## 0. Raporlama kuralları (kendimize koyduğumuz disiplin)

| Kural | Gerekçe |
|---|---|
| **n ≤ 48 ise ondalıklı yüzde yazılmaz** | n=18'de tek bir klip sonucu %5.6 oynatır; "%98.7" sahte kesinliktir. `stats_utils.pct_decimals()` bunu kodda zorlar. |
| **Her oran `k/n` + Wilson %95 GA ile verilir** | `%92` ile `44/48 [%80–%97]` aynı bilgi değildir. Wilson aralığı k=0 ve k=n uçlarında da anlamlıdır (Wald çöker). |
| **"%0 yanlış-pozitif" yasak** | 0/6 gözlem "sıfır" değildir; gerçek oran %39'a kadar çıkabilir. Doğru ifade: "gözlenen yanlış-pozitif yok (0/6; %95 üst sınır %39)". |
| **Alt-skor sayısı ≠ örneklem büyüklüğü** | 30 klibi 3 eksende puanlamak "n=90" değildir. Bağımsız birim **30 klip**tir (pseudo-replikasyon). `stats_utils.pseudo_replication_note()` uyarır. |
| **Kayıtlı log yoksa manşet yok** | Ölçüldüğünü hatırladığımız ama artefaktı olmayan rakamlar geri çekilir (bkz. §5 throughput). |
| **Kategori-bazlı tablolar iddia değil, göstergedir** | n=6/kategori → GA yaklaşık [%19, %81]; bu genişlikte bir aralıktan sıralama çıkarılmaz. |

Yeniden üretmek için:

```bash
python -c "from benchmark.stats_utils import fmt_rate; print(fmt_rate(44,48))"
# -> %92 [%80–%97]  (44/48)
python benchmark/test_stats_utils.py     # birim testler
```

---

## 1. Kanonik kalite skorları (bağımsız hakem)

Kaynak artefakt: **`benchmark/results/independent_scores.json`**
Hakem: `RedHatAI/gemma-3-12b-it-FP8-dynamic` (Gemma ≠ Qwen — üreten model puanlamıyor).

| Eksen | Kanonik değer | Alt-skor sayısı | **Bağımsız birim** |
|---|---|---|---|
| Özet kalitesi | **4.62 ± 0.53** | 90 | **30 klip × 3 eksen** |
| Aksiyon kalitesi | **4.74 ± 0.44** | 72 | **18 klip × 4 eksen** |
| Risk gerekçe kalitesi | **5.00 ± 0.00** | 54 | **18 klip × 3 eksen** |
| Diyalog robustluğu (tek-tur) | **5.00 ± 0.00** | 7 | **7 senaryo** |
| Diyalog tutarlılığı (çok-tur) | **5.00 ± 0.00** | 4 | **4 tur** |

**Geri çekilen varyantlar.** Belgelerde geçmiş turlardan kalan aksiyon-kalitesi değerleri
(4.66 / 4.69 / 4.71 / 4.83) artık kullanılmıyor; hepsi ya ara koşu, ya alt-küme ortalaması,
ya da başka bir modun sonucuydu. **Kanonik tek değer: 4.74**; özet için **4.62**.

**Bu değerlerin geldiği koşu — tam beyan.** Elimizde kalan tek hakem artefaktı
`independent_scores.json`'dur ve bu dosya, `iyilestirmeler.md` §7'deki tam-mod / hızlı-mod A/B
karşılaştırmasının **hızlı-mod kolundan** gelmektedir (aynı 30 kliplik senaryo seti).
Tam-mod kolunun rakamları (özet 4.64, aksiyon 4.66, risk 4.87) o karşılaştırma tablosunda
raporlanmıştı ama **ayrı bir artefakt dosyası olarak kaydedilmedi.** İki kol arasındaki fark
(≤ 0.13) ölçüm gürültüsü içindedir; yine de kanonik değer olarak **kaydı bulunan** koşuyu
alıyoruz. Tam-mod skorlarını manşete taşımak için yeniden koşup kaydetmek gerekir.

**"n=90" uyarısı.** Bu 90 bağımsız gözlem değildir: 30 klip, her biri 3 kalite ekseninde
puanlanmıştır. Aynı klibin eksenleri birbiriyle ilişkilidir; güven aralığı **n=30** üzerinden
okunmalıdır. Aynı şekilde n=72 → **18 klip × 4 eksen**, n=54 → **18 klip × 3 eksen**.

**"5.00/5" uyarısı (tavan-doygunluğu).** Risk-gerekçe ve diyalog skorlarında **std = 0.00**:
hakem her örneğe tam not vermiş. Bu, "kusursuz" değil **ölçüm tavanına dayanmış** demektir —
5'li ölçek bu görevde ayrım gücünü kaybediyor. Ayrıca diyalog için bağımsız birim yalnızca
**7 tek-tur + 4 çok-tur senaryo**dur. Bu skorları "sistem mükemmel" olarak değil,
"bu 11 senaryoda hakem hiçbir kusur işaretlemedi" olarak okuyun.

**Daha derin sınır (§6.3'te ayrıntılı).** Hakem şu an yalnızca **metin** görüyor
(sistemin kendi olay listesi + kendi özeti). Yani bu skorlar **iç tutarlılık** ölçüyor,
**videoya dayanaklılık** değil.

---

## 2. Kanonik olay-tespiti (recall) değerleri

Kaynak artefaktlar: `benchmark/results/eval_*.json`, `benchmark/results/all_datasets_*.json`.
Recall tanımı (**gevşek**): bir anomali klibinde model **≥1 herhangi bir olay** ürettiyse "yakaladı".
Tipin doğru olması gerekmez — bu tanımın ne kadar hoşgörülü olduğu §3'te ölçülmüştür.

> ⚠️ **Senaryo seti değişti.** Aşağıdaki senaryo satırları, `eval_scenario/Fall`'ın 8 klibi hâlâ
> donmuş-PNG iken (18 anomali) alınmış kayıtlı koşulardır. Klipler o zamandan beri gerçek düşme
> videolarıyla değiştirildi ve set **25 anomali + 12 normal** oldu; **yeni kompozisyonda ölçüm
> henüz koşulmadı**. Ayrıntı §6.7.

| Set | Klip (anomali) | Tek koşu sonucu | Wilson %95 GA |
|---|---|---|---|
| Senaryo (yangın+düşme) — *eski kompozisyon* | 18 | **18/18** (çoğu koşu) | [%82, %100] |
| Senaryo — en kötü kayıtlı koşu | 18 | **17/18** | [%74, %99] |
| Yangın alt-kümesi | 10 | **10/10** | [%72, %100] |
| UCF büyük (`eval_big`) — en iyi koşu | 48 | **44/48** | [%80, %97] |
| UCF büyük — diğer 2 kayıtlı koşu | 48 | **42/48** | [%75, %94] |
| GMDCSA gerçek düşme | 9 | **8/9** | [%56, %98] |
| URFD overhead düşme | 6 | **6/6** | [%61, %100] |
| Araç kazası (RoadAccidents) | 9 | **8/9 – 9/9** | [%56, %98] – [%70, %100] |

**Koşu-arası varyans.** Senaryo setinde 10+ kayıtlı koşunun ortalaması ~%99'dur, ama bu
"±%2 hassasiyet" demek değil: her koşu ya 18/18 ya 17/18 çıkıyor — yani **tek bir klip**
ortalamayı %99'dan %94'e taşıyor. `eval_big`'de üç kayıtlı koşu 44/48, 42/48, 42/48'dir;
**manşetimiz en iyi koşu değil, aralıktır: %88–%92.**

**Neyi geri çektik.** Eski belgelerde "senaryo recall %98.7" / "%99 ± 2" biçiminde ondalıklı
ifadeler vardı. n=18'de ondalık anlamsızdır; yerine `k/n + GA` kullanılıyor.

---

## 3. Üç seviyeli recall — ve mükerrer-klip düzeltmesi

"≥1 olay üretti" tanımı, silahı görmeyen bir Shooting klibini bile "yakaladı" sayar. Bunu
kendimiz yakalayıp üç seviyede yeniden ölçtük (`scripts/strict_recall.py`, `scripts/action_recall.py`;
kayıtlı cevaplardan, GPU'suz, şeffaf):

- **TESPİT** — bir şey oldu mu? (hoşgörülü, eski manşet tanımı)
- **AKSİYON** — doğru güvenlik-tepki sınıfı mı? (şiddet / mülk / kaza / yangın)
- **TANIMA** — UCF alt-etiketini birebir doğru adlandırdı mı? (en katı)

**Düzeltme (K9/K15).** Bu ölçüm "81 suç klibi" olarak raporlanıyordu. Ancak `data/eval`,
`data/eval_big`'in **%100 alt kümesi** olduğu için 27 klip **iki kez** sayılmıştı;
gerçek bağımsız klip sayısı **51**'dir. Mükerrerleri atıp yeniden çalıştırdık:

| Seviye | Eski (81 ölçüm) | **Kanonik (51 bağımsız klip)** | Wilson %95 GA |
|---|---|---|---|
| TESPİT | %96 (78/81) | **%96 (49/51)** | [%87, %99] |
| AKSİYON | %73 (59/81) | **%71 (36/51)** | [%57, %81] |
| TANIMA | %46 (37/81) | **%43 (22/51)** | [%31, %57] |

Yeniden üretim:

```bash
python scripts/strict_recall.py benchmark/results/answers_20260623_184153.jsonl
python scripts/action_recall.py benchmark/results/answers_20260623_184153.jsonl
# (mükerrer-arınmış sayı için aynı dosyayı `file` alanına göre tekilleştirerek çalıştırın)
```

**Kategori kırılımı — gösterge amaçlı, iddia DEĞİL.** Kategori başına n = 6 (RoadAccidents 9).
Bu büyüklükte Wilson aralığı **3/6 → [%19, %81]** kadar geniştir; yani kategoriler arası
sıralama yapmak istatistiksel olarak savunulamaz. Yine de gizlemiyoruz:

| Kategori | n | TANIMA | GA | Not |
|---|---|---|---|---|
| RoadAccidents | 9 | 7/9 | [%45, %94] | — |
| Abuse / Assault / Burglary / Explosion / Fighting | 6 | 3/6 | [%19, %81] | tek klip ±%17 oynatır |
| Shooting | 6 | 0/6 | [%0, %39] | 320×240'ta silah <20px (DORI eşiği altı) |
| Vandalism | 6 | 0/6 | [%0, %39] | aynı girdi-tavanı |

**Dürüst yorum:** sistem güçlü bir **ikili anomali-tespitçisi** (TESPİT %96), makul bir
**tepki-sınıflandırıcısı** (AKSİYON %71), ama grenli 320×240'ta **zayıf bir ince suç-tipi
sınıflandırıcısı** (TANIMA %43). Bu üçüncüsü prompting'le aşılamayan bir **girdi-bilgi
tavanıdır** — 5 ayrı kaldıraç ölçülüp elendi (`docs/iyilestirmeler.md` §15–§16).

---

## 4. Yanlış-pozitif — "sıfır" demiyoruz

| Set | Normal klip (benzersiz) | Gözlenen dar-FP | Wilson %95 GA |
|---|---|---|---|
| Senaryo normal | 12 | 0/12 (bazı koşularda 1/12) | [%0, %24] · (1/12 → [%1, %35]) |
| `eval_big` normal | **15** (16 dosya, 2'si aynı MD5) | 0/15 – 2/15 | [%0, %20] – [%4, %36] |
| `eval` normal | **7** (8 dosya, 2'si aynı MD5) | 0/7 – 1/7 | [%0, %35] |
| Adversaryel yangın-renkli (`eval_stress`) | 9 | 0/9 | **[%0, %30]** |
| Endüstriyel 1080p (`industrial`, *eski 8-klip havuzu*) | 8 | 0/8 | **[%0, %32]** |
| Hedef-domain (`eval_defense`) | 20 | **ölçülmedi** | — |

**Payda düzeltmesi (K10).** `Normal_Videos_936_x264.mp4` ve `Normal_Videos_937_x264.mp4`
**birebir aynı dosyadır** (MD5 `88800dc1…`). Bu yüzden normal-FP paydaları 8 ve 16 değil
**7 ve 15**'tir. Ölçüm sonucunu değiştirmiyor (her ikisinde de FP yok) ama paydayı şişiriyordu.

**"%0 yanlış-pozitif" ifadesi tüm belgelerden kaldırıldı.** Yerine: *"gözlenen yanlış-pozitif
yok (0/9; %95 üst sınır %30)"*. 9 normal klipte hiç alarm görmemek, gerçek FP oranının
%30'a kadar olabilmesiyle tamamen uyumludur. Bunu jüriden saklamak yerine yazıyoruz.

**Operasyonel-FP (herhangi "Düşük" seviyeli not) ayrı ve daha yüksektir:** senaryo normalinde
4/12 (%33 [%14, %61]), `eval_big` normalinde 6/16 (%38 [%18, %61]). Bunların tamamı
dispatch-kapısıyla engellenmiş, zararsız notlardır — ama "%0 FP" manşetinin neden
yanıltıcı olduğunu gösterirler.

---

## 5. Performans — kanonik ölçüm ve geri çekilen iddia

**Kayıtlı artefaktlar:** `benchmark/results/bench_perf_baseline_20260625.log` ve
`benchmark/results/bench_perf_prefixcache_20260625.log` (her ikisi n=6 klip).

| Metrik | Baseline | Prefix-cache (varsayılan) | Değişim |
|---|---|---|---|
| Eş-zamanlı (×4) throughput | 3.7 video/dk | **4.2 video/dk** | **+13.5%** |
| Eş-zamanlı (×4) gecikme | 16.3 s/video | **14.3 s/video** | −12% |
| Sıralı → ×4 hızlanma | 1.70× | **1.95×** | — |
| Tek-akış ortalama | 0.93 s/video-sn | **0.86 s/video-sn** | −8% |
| Tepe VRAM | 20.9 GB | **21.0 GB** | ~aynı (24 GB kart) |

**GERİ ÇEKİLEN İDDİA:** Belgelerde "eş-zamanlı ×4 throughput **+24%** (3.7 → 4.6 video/dk)"
yazıyordu. Bu, prefix-cache üstüne uygulanan serving-flag turunun (gpu-util 0.90 +
max-num-seqs 32) oturum-içi ölçümüydü ve **kayıtlı log artefaktı yoktur**. Kanıtlanamayan
rakamı manşette tutmuyoruz. **Kanonik değer: +13.5% (3.7 → 4.2 video/dk)** — iki log dosyasıyla
doğrulanabilir. Flag turunun ek kazancı gerçek olabilir; yeniden ölçülüp loglanana kadar
iddia edilmez.

**Tek-akış gecikme.** Kanonik: **0.86 s/video-saniyesi ortalama (n=6 klip; klip başına
0.44–3.75 aralığı)**. Kısa kliplerde sabit yük baskın olduğu için ortalama tek başına
yanıltıcıdır; aralığı birlikte veriyoruz. Bazı belgelerde geçen "~1.5 s/vsn" farklı bir
klip karışımından gelir ve artık manşet değildir.

---

## 6. **Ölçüm Sınırlarımız** (bilinçli olarak yayınlıyoruz)

Bu bölüm projeyi zayıflatmak için değil, **ölçüm disiplinini göstermek** için var.
Yetersizliği biz ölçtük ve yayınladık.

### 6.1 Küçük örneklem, varyans-baskın sonuçlar
En büyük tek değerlendirme setimiz 48 anomali + 16 normaldir. Bu boyutta bir klip
%2–17 arası oynama yaratır. Bu yüzden hiçbir yüzdeyi tek başına vermiyoruz; her biri
`k/n` + Wilson %95 aralığıyla birlikte. Sıralama, kategori-şampiyonluğu ya da
"%X daha iyi" türü karşılaştırmalar bu boyutta yapılamaz.

### 6.2 Recall tanımı gevşek
Manşet recall "**≥1 herhangi bir olay üretildi**" demektir; olay tipinin doğru olması
gerekmez. Bunu kendimiz yakaladık ve §3'te üç seviyeye ayırdık: aynı sistem
TESPİT %96 · AKSİYON %71 · **TANIMA %43**. Manşet rakamı okurken hangi tanımın
kullanıldığını sormak meşrudur.

### 6.3 Yayınlanan kalite skorları "dayanaklılık" değil "iç tutarlılık" ölçüyor
**Denetimde bulunan kusur:** `benchmark/judge_independent.py` hakeme **yalnızca metin** veriyordu —
sistemin ürettiği olay listesi + sistemin ürettiği özet. Hakem videoyu görmüyordu. Dolayısıyla
4.62 / 4.74 / 5.00 skorları *"özet, olay listesiyle tutarlı ve iyi yazılmış mı"* sorusunu
yanıtlıyor; *"özet videoda gerçekten olanı anlatıyor mu"* sorusunu **yanıtlamıyor**. Bu tasarımda
**kendinden emin bir halüsinasyon tam puan alabilir.**

**Araç düzeltildi.** Hakem betiği artık üç metrik ailesini **ayrı ayrı** raporluyor:
**[A] Dayanaklı** — hakeme klibin bilinen ground-truth etiketi verilir ve özetin o etiketle
olgusal uyumu (çelişki/uydurma bayraklarıyla) puanlanır; **[B] İç-tutarlılık** — eski eksenler,
artık "videoya dayanaklı DEĞİL" diye açıkça etiketli; **[C] Görsel dayanak** (`--vision`) —
klip kareleri çok-modlu hakeme gönderilir (GPU gerektirir, varsayılan kapalı).

**Ama ölçüm henüz yeniden koşulmadı.** Bu belgedeki 4.62 / 4.74 / 5.00 rakamları hâlâ **eski,
yalnızca-metin** koşusundan gelmektedir. Yani düzeltme araçtadır, **rakamlarda değil**.
Bu skorlar [A] ve [C] aileleriyle yeniden üretilene kadar "iç tutarlılık ölçüsü" olarak
okunmalıdır — paketin en denetlenmemiş iddiası hâlâ budur.

### 6.4 Gece / IR / termal görüntüde **sıfır kapsam**
Değerlendirme setlerimizin tamamı gündüz/aydınlatılmış görünür-ışık videosudur. Kızılötesi,
düşük-ışık ve termal kamera kaynağında sistemin nasıl davrandığı hakkında **hiçbir ölçümümüz yok**.
Savunma tesisi senaryosunun gerçek dağıtımında bunlar birincil kaynaktır — bu, sonucu
bilinmeyen bir boşluktur, "muhtemelen çalışır" demiyoruz.

### 6.5 Hedef domainde **ölçülmüş** pozitif yok (veri boşluğu kapandı, ölçüm boşluğu duruyor)
Şartnamenin hedeflediği domain: savunma tesisi / fabrika içi.

**Denetimde bulunan kusur:** tek gerçek 1080p tesis verimiz `data/industrial`'dı ve oradaki
**8 klibin 8'i de "Normal"** referans etiketiyle kullanılıyordu — yani hedef domainde tek bir
pozitif örneğimiz yoktu; tesis-içi tespit iddialarımız komşu domainlerden (ev düşmesi, sokak
kazası, açık-alan yangını) **transfer varsayımına** dayanıyordu.

**Veri boşluğu kapatıldı.** Kaynak set (Mendeley `xjmtb22pff`, 691 klip) 4 GÜVENSİZ + 4 GÜVENLİ
sınıf içeriyor; eşleme `data/industrial/CLASSES.md`'de Mendeley API'si ve makale tablosuyla
çapraz doğrulandı. Buradan **`data/eval_defense/`** üretildi: **20 anomali + 20 normal, tamamı
1920×1080 gerçek tesis görüntüsü**, sabit tohumlu (seed 2026) ve MD5-manifestli.
Anomali sınıfları: güvenli yürüme yolu ihlali · yetkisiz müdahale · açık pano kapağı ·
**forklift ile aşırı yük taşıma**.

**Ölçüm boşluğu duruyor:** bu sette **henüz hiçbir değerlendirme koşulmamıştır** (bu turda model
sunucusu kapalıydı). Yani "hedef domainde ölçülmüş performansımız" hâlâ **yok** — sadece artık
ölçebilecek veriye sahibiz. Bu ölçüm koşulana kadar tesis-içi iddialar transfer varsayımı olarak
okunmalıdır.

### 6.6 Forklift **devrilmesi** için gerçek açık veri yok
Şartname örneği "forklift devrildi"dir. Açık lisanslı gerçek forklift **devrilme** videosu
bulunamadı — bu boşluk duruyor.

Elimizdeki en yakın gerçek kanıtlar:
- **`eval_defense/Anomali/Carrying_Overload_with_Forklift`** — 5 klip, gerçek 1080p tesis
  görüntüsünde **forklift ile aşırı yük taşıma** (devrilme değil, devrilme *öncesi* riskli durum).
- UCF `RoadAccidents` devrilme/çarpışma klipleri (320×240, grenli).

`data/test_clip.mp4` bu olayı **kareye gömülü metinle** taşıyan sentetik bir karikatürdür —
orada model video anlama değil **OCR** yapmaktadır ve bir yetenek kanıtı olarak sunulamaz.

### 6.7 Donmuş-kare klipler — giderildi, ama sonuçlar henüz yeniden ölçülmedi
**Denetimde bulunan kusur:** `data/eval_scenario/Fall` altındaki 8 klip **video değildi** —
tek bir PNG'nin `ffmpeg -loop 1 -t 3 -r 5` ile sarılmasıyla üretilmiş 1024×1024, 3.0 sn,
**sıfır hareketli** dosyalardı. Bir düşme *hareketini* değil, "yerde yatan kişi" *pozunu*
ölçüyorlardı ve senaryo-seti pozitiflerinin 8/18'ini oluşturuyorlardı.

**Durum: giderildi.** Klipler gerçek düşme videolarıyla değiştirildi (ffprobe doğrulaması):
9 × GMDCSA 1280×720 @60 fps (3.8–8.4 sn) + 6 × URFD 640×480 @15 fps (6.4–14.4 sn).

**Ama iki dürüst çekince:**
1. **Bu belgedeki senaryo-seti rakamları (18/18, 17/18) ESKİ kompozisyona aittir.** Set artık
   10 yangın + **15 gerçek düşme** = 25 anomali + 12 normaldir. **Yeni kompozisyonda henüz
   ölçüm koşulmamıştır** (bu turda model sunucusu kapalıydı). Yeni sayılar üretilene kadar
   senaryo recall'ı "8 donmuş-kare klip içeren eski set üzerinde ölçülmüştür" notuyla okunmalıdır.
2. **Yeni düşme klipleri bağımsız değil:** 15'inin 15'i de `data/falls_real/Fall` (9) ve
   `data/falls_surveillance/Fall` (6) ile **birebir aynı dosyadır** (MD5 doğrulandı). Yani
   "senaryo seti düşme recall'ı" ile "GMDCSA recall'ı" ve "URFD recall'ı" **ayrı kanıt değildir**;
   aynı 15 klip üç ayrı satırda raporlanırsa çift sayım olur.

### 6.8 Çözünürlük–etiket karışımı (confound)
Değerlendirme setlerimizde çözünürlük ile etiket birbirine karışmıştır:

| Set | Anomali klipleri | Normal klipler |
|---|---|---|
| `eval_big` | **48/48'i 320×240** (%100 grenli) | 8/16'sı 1920×1080 (%50), 8'i 320×240 |
| `eval_scenario` (güncel) | **1080p hiç yok** — yangın 320×240…480×272, düşme 640×480 / 1280×720 | 8/12'si 1920×1080 (%67) |
| `eval_scenario` (denetim anındaki hâli) | 1080p yok; düşme 1024×1024 **sentetik donmuş kare** | aynı |

Yani "anomali" ile "düşük çözünürlük" istatistiksel olarak birlikte hareket ediyor: her iki sette de
**tek bir 1080p anomali klibi yok**, buna karşılık normallerin yarısı ya da üçte ikisi 1080p.
Model kararının ne kadarının olay içeriğinden, ne kadarının görüntü kalitesi ipucundan geldiğini
mevcut setlerle **ayrıştıramayız**. Donmuş-PNG düzeltmesi confound'u *azalttı* (düşme klipleri
artık 640×480–1280×720) ama **ortadan kaldırmadı**. Bu, hem recall'ı hem normal-FP'yi
etkileyebilecek gerçek bir sınırlılıktır.

### 6.9 "Bağımsız büyük-n doğrulaması" iddiası geri çekildi + tune/holdout ayrımı
`data/eval` (31 benzersiz klip), `data/eval_big`'in (63 benzersiz klip) **%100 alt kümesiydi**
— 31/31 MD5 birebir aynı. Dolayısıyla "küçük sette bulduğumuzu bağımsız büyük sette doğruladık"
ifadesi **yanlıştı** ve geri çekilmiştir.

**Düzeltme uygulandı:** `eval_big` artık ayrık iki alt-kümeye bölünmüştür —
`data/eval_tune` (31 klip) ve `data/eval_holdout` (32 klip); **kesişimleri sıfırdır**
(MD5 ile doğrulandı). Ayarlama `eval_tune`'da, doğrulama `eval_holdout`'ta yapılır.

**Ama bu belgedeki `eval_big` rakamları bölünmeden ÖNCE üretilmiştir** — yani hâlâ
"ayarlamanın yapıldığı veriyle aynı veri" üzerindedir. Temiz holdout ölçümü **henüz
koşulmamıştır** ve rakamların bir miktar iyimser olması beklenmelidir. Eski `data/eval`
dizini geriye dönük uyum için duruyor; ondan çıkan sonuçlar bağımsız kanıt sayılmamalıdır.

### 6.10 Tek donanım, tek dil, tek operatör
Tüm ölçümler tek bir RTX 5090 Laptop (24 GB) + WSL2 üzerinde, tek modelle, Türkçe çıktıda
yapılmıştır. Farklı GPU/sürücü/quantization altında sayıların yeniden üretilmesi test edilmedi.
Diyalog skorları tek bir değerlendiricinin yazdığı 11 senaryodan gelmektedir.

---

## 7. Belge-arası tutarlılık kontrol listesi

Bir sayıyı değiştirirken bu listeyi güncelleyin:

| Değer | Kanonik | Nerede geçer |
|---|---|---|
| Özet kalitesi | 4.62 ± 0.53 (30 klip × 3 eksen) | README, performans_raporu, sartname_uyum, sunum_iskeleti |
| Aksiyon kalitesi | 4.74 ± 0.44 (18 klip × 4 eksen) | aynı |
| Risk gerekçe | 5.00 ± 0.00 (18 klip × 3 eksen, tavan-doygun) | aynı |
| Diyalog | 5.00 (7 tek-tur + 4 çok-tur, tavan-doygun) | aynı + demo_script |
| Senaryo recall | 18/18 [%82–%100] · en kötü koşu 17/18 [%74–%99] — **eski kompozisyon, yeniden ölçülecek** | README, performans_raporu |
| `eval_big` recall | 44/48 [%80–%97] · diğer koşular 42/48 [%75–%94] | README, performans_raporu |
| 3 seviyeli recall | TESPİT 49/51 · AKSİYON 36/51 · TANIMA 22/51 | README, performans_raporu, sunum_iskeleti |
| Throughput | +13.5% (3.7 → 4.2 video/dk), loglu | README, architecture, performans_raporu, sunum_iskeleti |
| Tek-akış gecikme | 0.86 s/vsn ort (n=6, 0.44–3.75) | aynı |
| Veri envanteri | **214 benzersiz** / 412 dosya; ölçümde **140 klip / 44.0 dk** (2026-07-25 denetimi) | README, veri_kaynaklari |
| Hedef-domain seti | `eval_defense` 20 anomali + 20 normal, 1080p — **ölçüm henüz koşulmadı** | README, performans_raporu, veri_kaynaklari |
