# Hata analizi — yanlış pozitifler gerçekten yanlış mı?

Tarih: 2026-08-25 · Yöntem: kliplerden temsili kare çıkarılıp **gözle** incelendi.
Model yeniden sorulmadı (dairesel olurdu).

## 1. "Yanlış pozitiflerin" çoğu ölçülemez, çünkü o eksende etiket yok

Yelek kuralı kendi ihlal sınıfı dışında **61 klipte** ateşliyor:

| klip kümesi | ateşleme |
|---|---|
| Opened_Panel_Cover (ihlal + normal) | 32 |
| Safe_Walkway_Violation (ihlal + normal) | 22 |
| Carrying_Overload_with_Forklift | 5 |
| Authorized_Intervention | 2 |

Bunlardan rastgele 12'sinin karesine bakıldı (tohum 7).

**Gözlem:** Bu tesiste standart iş kıyafeti **koyu lacivert/siyah tulum**;
yeşil reflektif yelek yalnızca ara sıra görülüyor (12 karenin 2'sinde). Bakılan
12 klibin neredeyse hepsinde makinenin başında **gerçekten yeleksiz bir kişi
var**.

Yani bu ateşlemeler **olgusal olarak doğru**. Değerlendirme seti o klipleri
"pano kapağı kapalı" veya "güvenli yaya yolu" diye etiketlediği için farklı
bir tehlike eksenini işaretliyor; bir klip yalnızca tek tehlikeyle etiketli.

Sonuç: **%56'lık normal yanlış alarm oranı, sistemin hata oranı değildir.**
Ölçülebilir eksende kesinlik 0,905'tir.

## 2. Ölçülebilir hatalar — 2 yanlış pozitif, 6 kaçırma

Yelek kuralının gerçekten ölçülebildiği tek eksen
`Unauthorized_Intervention` ↔ `Authorized_Intervention` çiftidir.

### 6 kaçırma İKİ ayrı sebebe ayrılıyor

| grup | klipler | slot değerleri | tanı |
|---|---|---|---|
| **A** | 1_te5, 1_tr18, 1_tr84 | `kisi=0` | **Farklı kamera görüşü** — geniş plan, makine uzakta. Kapı DOĞRU davranıp kapanıyor; o ölçekte panonun başında kimse seçilemiyor. |
| **B** | 1_tr42, 1_tr61, 1_tr81 | `kisi=3, yelek=VAR` | **Çok kişili sahne belirsizliği.** Makinede 3 kişi var, biri yelekli. Model "VAR" diyor ve YANILMIYOR — 1_tr61'de yelek gözle görülüyor. Ama yeleksiz olan kişi için ihlal duruyor. |

A grubu, bu sınıfta **üçüncü bir kamera görüşü** olduğunu ortaya çıkardı.
Soru tasarımıyla çözülemez.

### 2 yanlış pozitif
5_te2 ve 5_tr12: `kisi=1, yelek=YOK`. İncelenen karede yelek görünmüyor;
klip boyunca görünüyor olabilir. Kenar durum.

## 3. B grubu için denenen çözüm — REDDEDİLDİ

Ön kayıt: `docs/on_kayit_yelek_sayim_2026-08-25.md`

Fikir: "yelek var mı" yerine **yelekli kişi sayısını toplam kişi sayısıyla
karşılaştır** — biri bile yeleksizse ihlal.

| kol | TP | FP | FN | TN | MCC |
|---|---|---|---|---|---|
| mevcut: `kisi≥1 ve yelek=YOK` | 19 | 3 | 6 | 22 | +0,645 |
| yeni: `kisi≥1 ve yelekli<kisi` | 19 | 13 | 6 | 12 | **+0,250** |
| bilgi: `yelekli==0` | 19 | 2 | 6 | 23 | +0,689 |
| bilgi: ikisinin BİRLEŞİMİ | 22 | 13 | 3 | 12 | +0,393 |

Ön kayıtlı ölçüt (MCC ≥ +0,75 ve FP ≤ 4) sağlanmadı → **RET**.

**Neden çalışmadı:** modelin `kisi` ve `yelekli` sayımları aynı kişi kümesini
ölçmüyor. Normal kliplerde sıkça `kisi=2, yelekli=1` çıkıyor ve kural ateşliyor.
Birleşim kolu 3 kaçırmayı kurtarıyor ama 10 yanlış pozitif ekliyor.

Not: bu koşumda mevcut kural +0,645 verdi (ana koşumda +0,689) — slot
cevaplarında koşumlar arası ±0,05 dalgalanma var.

## 4. Yelek kuralının gerçek tavanı

25 ihlal klibinin 3'ü (A grubu) farklı kamera görüşünde ve soru tasarımıyla
kurtarılamaz. Kalan 22'nin 19'u yakalanıyor. Yani ulaşılabilir tavana
**19/22 = %86** oranında yaklaşılmış durumda; MCC'yi asıl sınırlayan şey
model yeteneği değil, sınıfın kendi tanımının çok kişili sahnelerde belirsiz
olması.
