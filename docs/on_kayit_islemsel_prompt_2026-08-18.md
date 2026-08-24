# ÖN-KAYIT — Mentörün prompt tezinin **adil** testi (D40)

**Tarih:** 2026-08-18 · **Sonuçlara bakılmadan önce yazıldı.** Sunucu kapalı, hiç koşulmadı.

## Neden bu test gerekiyor — önceki testim eksikti

Mentörün tezi: *"göndereceğimiz promptlarla modeli yönlendirerek anomali tespitinde
kategorileri ayırabiliriz."*

D37'de bu mimariyi kurup ölçtüm (`benchmark/isg_yapilandirilmis_prob.py`): kapalı
seçenek listesi, `guided_choice`, sınıf başına tanım. Sonuç olumsuzdu (6-yönlü
MCC +0,031, sınıf doğruluğu %7,1 — şansın altında) ve *"darboğaz format değil, algı"*
diye yazdım.

**O sonuç, sorduğum sorunun cevaplanabilir olduğunu varsayıyordu. Değildi.**

Bugün veri setinin kaynak makalesi bulundu (Onal & Dandil 2024, *Data in Brief*
56:110756) ve etiketlerin **işlemsel** tanımları ortaya çıktı. Modele verdiğimiz
tanımlarla karşılaştırınca:

| sınıf | **modele verdiğimiz tanım** (`benchmark/labels.py`) | **gerçek tanım** |
|---|---|---|
| `Carrying_Overload` | "güvenli kapasiteyi aşacak şekilde aşırı/istiflenmiş yük" | **"3 blocks or more"** |
| `Safe_Carrying` | "güvenli kapasitede yük taşıyor" | **"2 blocks or less"** |
| `Unauthorized_Intervention` | "YETKİSİZ kişi müdahale ediyor (yetkili teknisyen dışında)" | **"without an intervention vest"** |
| `Authorized_Intervention` | "yetkili teknisyen usulünce müdahale ediyor" | **"wearing a green vest"** |

Model **"güvenli kapasite"yi göremez**; **"yetkili teknisyen"i göremez**. Bunlar
anlamsal kategorilerdir. Ama **kasa sayabilir** ve **yelek rengi görebilir**.

**Düzeltme:** D37'deki *"darboğaz algı"* sonucum fazla geniş yazılmıştı. Doğrusu:
o promptla ayıramadığını gösterdim; algı sınırı olduğunu **ispatlamadım**.
(Pano sınıfı istisna — orada kırpılmış görüntüde bile 1/12 ölçüldü, algı sınırı ispatlı.)

## Deneyin mantığı — tek değişken: sorunun GÖZLEMLENEBİLİRLİĞİ

Aynı klipler, aynı model, aynı kareler, aynı sıcaklık. **Tek fark sorunun içeriği.**

| kol | soru tipi |
|---|---|
| **A — ANLAMSAL** | bugüne kadar sorduğumuz soru (kategori adı / anlamsal tanım) |
| **B — İŞLEMSEL** | kaynak makalenin ölçütü (sayılabilir / görülebilir) |

**B ≫ A ise:** darboğaz tanımdı, mentörün tezi **doğrulanır**, benim D37 sonucum düzeltilir.
**B ≈ A ise:** darboğaz gerçekten algı, D37 sonucu **doğrulanır** (bu sefer haklı gerekçeyle).

Eşleştirilmiş tasarım → **McNemar exact** ile aynı kliplerde doğrudan karşılaştırma.

## Kollar

| # | sınıf çifti | n | A (anlamsal) | B (işlemsel) |
|---|---|---|---|---|
| 1 | `Carrying_Overload` / `Safe_Carrying` | 25+25 | "aşırı yük ihlali var mı?" | **"çatalda üst üste kaç kasa var?"** → ≥3 ihlal |
| 2 | `Unauthorized_Intervention` / `Authorized_Intervention` | 25+25 | "yetkisiz müdahale var mı?" | **"başındaki kişide parlak lime-yeşil reflektif yelek var mı?"** → yok ise ihlal |
| 3 | `Opened_Panel_Cover` / `Closed_Panel_Cover` | 24+25 | "pano kapağı açık mı?" | **"pano bölgesinde koyu bir oyuk görünüyor mu?"** → evet ise açık |

**Kol 1'e ek C alt-kolu:** aynı sayma sorusu **serbest metinle** (kısıtsız). Gerekçe:
kısıtlı kod çözmenin muhakemeyi bozduğu ölçülmüş bir etkidir
([Tam ve ark., EMNLP 2024 Industry](https://aclanthology.org/2024.emnlp-industry.91/)).
Sayma bir muhakeme görevi; kısıt onu bozuyorsa bunu görmemiz gerekir.

## Sabitler — koşumdan önce ilan edildi

- Model: `Qwen/Qwen3-VL-8B-Instruct-FP8` (dağıtımdaki), **T = 0,0**
- Kareler: üretim yolu (`extract_timestamped_frames`, `fps_sample=2.0`,
  `frame_max_side=768`) — **ölçülen şey üretimde koşacak şeydir**
- `max_tokens = 24`, `guided_choice` (C alt-kolu hariç)
- **Kaçış seçeneği her listede ZORUNLU** (`GORUNMUYOR` / `BELIRSIZ`).
  D33 dersi: kaçışsız zorunlu seçimde model 20/20 klipte "KAPALI" demişti.

## Karar ölçütü — önceden sabit

1. Her kol için **TP/FP/FN/TN, MCC, Wilson %95 GA** yazılır. Tek metriğe bakılmaz.
2. **Dejenerelik kapısı:** bir kol kliplerin ≥%85'ine aynı etiketi veriyorsa
   **DEJENERE** işaretlenir ve MCC'si ne olursa olsun başarı sayılmaz.
   (Bu tuzağa iki kez düştük; bir kez MCC +0,071 ile recall %1'i gizledi.)
3. **Asıl karar:** A ile B arasında **McNemar exact**, iki yönlü.
   **B'nin A'yı geçtiği söylenebilmesi için p < 0,05 ve B'nin MCC'si A'nınkinden
   en az +0,20 yüksek olmalı.** İkisi birden sağlanmazsa "fark yok" denir.
4. Çoklu karşılaştırma: 3 kol × 2 soru = 6 test. **Bonferroni: eşik 0,05/3 = 0,0167**
   (kol başına bir A-vs-B karşılaştırması).

## Karşılaştırma tabanı — deterministik dedektörlerimiz

Aynı sınıf çiftlerinde ölçülmüş sayılar (bugün):

| sınıf çifti | deterministik dedektör |
|---|---|
| forklift | LOO MCC **+0,718** · özgüllük 25/25 · tesis çapında 0/172 FP |
| yelek | iç-grup MCC ~**+0,644** (havuzlanmış +0,843 şişkin) |
| pano | uçtan uca özgül **15/99**, FP 0/98 |

VLM bunlara **yaklaşamazsa** mimari kararımız (deterministik dedektör karar verir)
doğrulanır. **Yaklaşır veya geçerse** mimariyi yeniden düşünmemiz gerekir.

## Bu, §8'de elenen ASK-HINT değil

Elenen şey **genel ipucu listeleriydi** ("duman ara, yangın ara") ve net gerileme
üretmişti (recall %96→92, kategori %25→12). Burada verilen şey **tek, spesifik,
doğrulanabilir bir ölçüt**. Farklı müdahale; ayrıca A/B tasarımı sayesinde
zararlıysa **ölçümde görülecek**.

## Dürüstlük çekincesi — sonuç olumlu çıksa bile

"≥3 kasa = ihlal" demek, **bu tesisin konvansiyonunu prompta gömmektir**. Başka bir
tesiste yeniden kalibrasyon gerekir. Bu bir kusur değil — `facility_rules` ve
deterministik dedektörlerimiz için de aynısı geçerli — ama **genel bir İSG yeteneği
olarak sunulamaz** ve raporda böyle yazılacaktır.

## Zaten var olan kısmi kanıt

`facility_rules` (tesise özgü kuralları prompta koymak) arşivimizdeki **en iyi
prompt-temelli sonuçtur**: özgül TP **1 → 16/99**. Reddetme gerekçemiz doğruluk
değil bedeldi (FP 2 → 23/98). Yani mentörün tezinin lehinde ölçülmüş kanıt
**hâlihazırda vardır**; bu test onu adil koşulda sınar.

## Geri çekilme sözü

Eşikler koşumdan sonra gevşetilmeyecek. Sonuç ne çıkarsa — mentörün tezini
doğrulasa da, benim D37 sonucumu doğrulasa da — olduğu gibi yazılacak ve
`benchmark/results/` altına kaydedilecek.

---

# EK-1 — Tasarım denetimi sonrası düzeltmeler (koşumdan önce)

Prob, koşulmadan önce **üç bağımsız ajana çürütülmek üzere** verildi. Hepsi
**"DÜZELTİLDİKTEN SONRA"** hükmü verdi. Bulunan kusurlar ve yapılan düzeltmeler:

## Ölümcül kusurlar (koşumu geçersiz kılardı)

**F1 — Kare sınırı aşımı.** Prob tüm kareleri gönderiyordu; vLLM
`--limit-mm-per-prompt {"image": 16}` ile koşuyor. Ölçüldü: **149 klibin 56'sı
(%37,6)** sınırı aşıyor ve aşım **sınıfla korele** (kol2 ihlal %72 vs normal %52).
Zincir: vLLM 400 → hata yakalanır → **"ihlal yok" olarak puanlanır**. Deponun diğer
tüm probları 8 kareye kısıyor; bu prob tek istisnaydı.
→ **`AZAMI_KARE = 8`**, aşım önceden kırpılıyor.

**E1 — Hata sessizce negatife dönüşüyordu.** API hatası `None` → negatif sayılıyordu.
→ Hata artık `"HATA"` olarak işaretlenir, ilgili klip **tüm kollardan düşürülür**
(eşleştirme korunur) ve **ayrıca raporlanır**. %20'den fazla düşerse koşum
"GÜVENİLİR DEĞİL" damgası alır.

**S1 — Sessiz çöküş yanlış sonuç yazdırırdı.** Her B çağrısı hata verse tablo
*"doğruluk 0,500 · Wilson [0,366-0,634] · DEJENERE · KALDI"* basıyordu — makul bir
şans-düzeyi satırı gibi okunur ve *"işlemsel soru da işe yaramadı → darboğaz algı"*
diye yazılırdı. **Tam da benim önyargım yönünde.**
→ Koşum öncesi **sağlık kontrolü**; sunucu kapalı veya `mock_mode` açıksa **başlamaz**.

**C1 — Serbest metin ayrıştırıcısı bozuktu.** `re.search` **ilk** tamsayıyı alıyordu;
kareler modele `[Kare zamanı: MM:SS]` etiketiyle gittiği için ilk tamsayı genelde
**0** oluyordu → `0 >= 3` → sistematik "ihlal yok".
→ **Son** tamsayı alınır; birim testle doğrulandı.

**S2 — Künye yoktu.** `DILAJAN_FAST=1` fps'i 2,0→1,0 ve çözünürlüğü 768→512'ye
**sessizce** düşürür; künyesiz koşum "üretim ayarları" iddiasını doğrulayamazdı.
→ Model, T, fps, çözünürlük, kare sayısı, seçenek listeleri, argv, **git commit**
çıktıya yazılır.

## Kavramsal kusur — "tek değişken" iddiam yanlıştı

İşlemsel soru, anlamsal sorudan **üç şeyi birden** değiştiriyor:

1. **Nereye bakılacağı** — B mekânsal çapa veriyor ("çatalda", "başında duran kişide"),
   A vermiyor. Mekânsal dikkat yönlendirmesi ayrı ve bilinen bir etkidir.
2. **Kararın nerede verildiği** — eşik (≥3) **kodda**, modelde değil. Yani
   B = *"VLM öznitelik çıkarıcı + elle yazılmış kural"*, ki bu **zaten bizim
   deterministik dedektör mimarimizdir**.
3. **Biçim** — A evet/hayır, B sayı.

→ **A2 kolu eklendi**: anlamsal ölçüt + B ile **aynı mekânsal çapa**.

| gözlem | yorum |
|---|---|
| B > A2 > A | kazanan **gözlemlenebilirlik** — mentörün tezinin çekirdeği doğrulanır |
| B ≈ A2 > A | kazanan **dikkat yönlendirmesi**, gözlemlenebilirlik değil |
| hepsi ≈ | darboğaz gerçekten **algı** |

## Güç — "fark yok" sonucu ne demek DEĞİL

Benzetim (20.000 tekrar, 25+25):

| A → B doğruluk | ≈ΔMCC | güç |
|---|---|---|
| 0,50 → 0,60 | +0,20 | %5–8 |
| 0,50 → 0,70 | +0,40 | **%28–42** |
| 0,50 → 0,80 | +0,60 | %69–87 |
| 0,50 → 0,85 | +0,70 | %89–97 |

**%80 güç için B'nin ~0,82–0,85 doğruluğa çıkması gerekiyor.**

**Bu yüzden açıkça yazılıyor: "fark yok" sonucu "etki yok" demek DEĞİLDİR;
"etki ~0,30 doğruluktan küçük" demektir.**

Ayrıca: ilan edilen `ΔMCC ≥ +0,20` kapısı **ölü koddu** — bağlayıcı olan McNemar'ın
kendisi ve o fiilen **≥ +0,28** dayatıyor. Kapı kaldırıldı, bağlayıcı eşik olarak
**yalnızca McNemar + Bonferroni** ilan ediliyor.

**Bonferroni düzeltildi:** karşılaştırma sayısı kol başına hesaplanır
(Kol 1: 3, Kol 2: 2, Kol 3: 1), eşik `0,05 / adet`.

## Mutlak taban — A'yı geçmek YETMEZ

Eski karar kuralında B için mutlak taban yoktu; B, MCC +0,25 ile A'yı geçip "GEÇTİ"
damgası alabilir ve üretimde işe yaramaz bir sayı olabilirdi.

→ Rapor artık her kolda **ilgili deterministik dedektörün ölçülmüş değerini**
yan yana basar ve şunu yazar: *"A'yı geçmek tek başına yeterli değildir; B, ilgili
dedektörün değerine yaklaşmıyorsa üretim kararı DEĞİŞMEZ."*

## Kol 3 KEŞİFSEL işaretlendi

Kol 3'ün B sorusu kaynak makalenin ölçütü **değil**, kendi dedektörümüzün
mekanizmasıdır (`pano.py`: ROI'de minimum ortalama parlaklık). Ve karar değeri
neredeyse sıfırdır: yalnız-parlaklık kuralı **kolay çiftte** (açık vs kapalı) zaten
%95,9, ama **gerçek güvenlik görevinde** (class2 vs class6+class5) MCC +0,513 / FP=21.
→ Kol 3 **manşet sayı üretmez**.

Kol 1 ve 2 farklı: oradaki B **kaynak makalenin yayımlanmış tanımıdır**
("3 blocks or more", "green vest") — cevabı prompta koymak değil, **etiket tanımını**
vermektir. (Kol 2'de "parlak lime-yeşil reflektif" ifadesi bizim renk kalibrasyonumuzdu;
makalenin sözcüğüne — **"yeşil reflektif"** — çekildi.)

## AÇIK KALAN — koşulmadan önce karara bağlanmalı

**Kodlama izi piksellere geçiyor.** Denetim ölçtü: üretim yolundan geçen karelerin
**global luma standart sapması** tek başına Kol 1'i **LOO doğruluk 0,780** ile
ayırıyor (permütasyon p=0,0005). Bizim kapımız 0,80 civarında geçmeye başlıyor.

**Sonuç: Kol 1'de B geçerse, "modele kasa saydırdık" ile "model pozlama/sıkıştırma
imzasını okudu" AYIRT EDİLEMEZ.**

Bu iz deterministik dedektörü **açıklamıyor** — 50 klip ortak spesifikasyona yeniden
kodlandı, LOO MCC +0,783 → +0,783, fiziksel oran 1,576 → 1,560. Aynı kontrol **VLM
için de koşulmalıdır.**

**Karar: Kol 1'de B olumlu çıkarsa, yeniden-kodlama kontrolü koşulmadan sonuç
raporlanmayacaktır.** Bu kontrol henüz uygulanmadı ve bu eksiklik burada kayıtlıdır.

## Denetimin koşum öncesi tahminleri (kayıt için)

| kol | tahmin | gerekçe |
|---|---|---|
| Kol 1 A | MCC ≈ **+0,15** (−0,05…+0,35), dejenere-negatif olasılığı %45 | D37'de model 197 klibin 196'sında "ihlal_yok" demişti |
| Kol 1 B | MCC ≈ **+0,35** (+0,10…+0,60) | sinyal piksellerde gerçekten var (oran 1,576), ama 768 px'te yük küçük |
| Kol 1 B alt-tahmin | cevapların **>%80'i {2,3}** kümesinde olacak | sayım değil ikili ayrım yapıyor olacak |
| Kol 1 C | MCC ≈ **+0,00, dejenere** — *bu bir KOD tahminiydi* | ayrıştırıcı kusuru; **düzeltildi**, tahmin artık geçersiz |

Bu tahminler koşum sonrası gerçek sonuçla karşılaştırılacaktır.
