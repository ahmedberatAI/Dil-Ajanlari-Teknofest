# Tam set sonucu — 658 benzersiz içerik, kanonik yer gerçeğiyle

Tarih: **2026-08-25** · Ön kayıt: `docs/on_kayit_tam_set_2026-08-25.md`
Arşiv: `benchmark/results/eval_20260825_165802.json`
Yer gerçeği: `benchmark/results/kanonik_etiket.json`
Hüküm: `benchmark/tam_set_hukum.py` (sayılar **hesaplanır**, elle yazılmaz)

## 1. Hüküm

| soru | ölçüt | sonuç |
|---|---|---|
| **S1 REPLİKASYON** | MCC ≥ sevk − 0,15 | **GEÇTİ** |
| **S2 MARJ** | doğruluk − çerçeve tabanı ≥ 0,05 | **GEÇTİ** |
| **S3 YAYA YOLU** | MCC ≥ +0,45 **ve** saha kesinliği ≥ 0,237 | **KALDI** |

### S1 — üç kural da 3,5 kat veride ayakta

| kural | 197 klipte | **658 içerikte** | eşik |
|---|---|---|---|
| `Opened_Panel_Cover` | +0,960 | **+0,842** | +0,810 |
| `Carrying_Overload_with_Forklift` | +0,881 | **+0,795** | +0,731 |
| `Unauthorized_Intervention` | +0,689 | **+0,679** | +0,539 |

Pano ve forklift bir miktar düşüyor — beklenen, daha çeşitli veri daha zor.
Yetkisiz neredeyse hiç değişmiyor.

### S2 — çerçeve tabanını aşıyorlar

| kural | doğruluk | çerçeve tabanı | **marj** |
|---|---|---|---|
| pano | 0,943 | 0,661 | **+0,282** |
| forklift | 0,907 | 0,750 | **+0,157** |
| yetkisiz | 0,856 | 0,797 | **+0,059** |

Çerçeve tabanı: kişiler maskelenmiş arka plandan leave-one-out
en-yakın-merkez, dengeli alt-örneklem ×5. **Etiket görmeden** ölçülür.

**Yetkisiz marjı düne göre değişti** ve sebebi veri düzeltmesidir: dün
n=117 ile +0,049 çıkıp eşiğin altında kalmıştı. Kanonik yer gerçeği çiftin
gerçek büyüklüğünü (n=146) geri verince marj +0,059'a çıktı.

### S3 — yaya yolu, on üçüncü ret

MCC **+0,094** (eşik +0,45). Saha kesinliği 0,372 eşiği geçiyor ama MCC
kesin biçimde kalıyor. 279 içerikte, 3,5 kat veriyle, kanonik etiketle:
sınıf **kapalı**.

## 2. Tam tablo (kanonik)

```
kural            n   TP   FP   FN   TN      MCC   doğruluk   saha kes.
forklift        86   52    4    4   26   +0,795      0,907   0,929 (56)
pano           174  132    0   10   32   +0,842      0,943   0,584 (226)
yetkisiz       146   91    4   17   34   +0,679      0,856   0,268 (340)
yaya           279  175   55   32   17   +0,094      0,688   0,372 (476)
```

## 3. Katmanlı okuma — karıştırıcıdan arınmış

Bu setin en önemli okuması. Klipler arka plan imzasına göre (**etiketsiz**)
kümelendi; her iki etiketi de yeterli sayıda içeren küme, içinde yapılan
ölçümün çerçeve karıştırıcısından arınmış olduğu bir katmandır.

| kural | katman | n | MCC | katman içi çerçeve |
|---|---|---|---|---|
| **yetkisiz** | küme1 | 66 | **+0,668** | **0,606** |
| pano | küme1 | 91 | +0,830 | 0,879 |
| forklift | küme1 | 54 | +0,753 | 0,907 |
| yaya | küme0 | 213 | +0,063 | 0,427 |
| yaya | küme1 | 66 | +0,151 | 0,514 |

**Katmanlaştırmanın işe yarayıp yaramadığı ayrıca ölçüldü** (katman içinde
arka plan etiketi hâlâ tahmin edebiliyor mu):

- **yaya küme0/küme1: 0,427 / 0,514** — çoğunluk oranının altında/eşiğinde.
  Karıştırıcı **kalktı**. Ve o temiz katmanlarda kural yine +0,063/+0,151
  veriyor. Yani yaya sınıfının başarısızlığı karıştırıcıya **bahane
  edilemez**; kural gerçekten ayırt etmiyor.
- **yetkisiz küme1: 0,606** (toplamda 0,797'ydi) — karıştırıcı büyük ölçüde
  kalktı ve kural orada **+0,668** veriyor, doğruluk 0,833, marj **+0,227**.
  Dünkü "yelek kuralının marjı ince" endişesi **çözüldü**: o incelik
  kameralar arası toplamanın yarattığı bir yapaylıktı.
- **pano/forklift küme1: 0,879 / 0,907** — katmanlaştırma bu iki çiftte
  **işe yaramadı**, kümeler hâlâ çerçeve bilgisi taşıyor. Bu yüzden onların
  katmanlı MCC'leri karıştırıcıdan arınmış **sayılmaz**. İkisi de zaten
  toplam marjı geniş farkla aştığı için buna ihtiyaçları yok.

## 4. Aşırı uyum — temiz

| kural | `_tr` | `_te` |
|---|---|---|
| forklift | +0,771 | +0,882 |
| pano | +0,851 | +0,728 |
| yetkisiz | +0,648 | +0,733 |
| yaya | +0,040 | +0,279 |

Sistematik `_tr` > `_te` uçurumu yok. Ayrım **içerik düzeyinde** kuruldu:
bir kopyası `_te` ise içerik teste gider, yani test kümesi kirlenmez.

## 5. Yeni koşum yapılmadı — ve neden

`data/eval_kanonik` (658 benzersiz içerik) kuruldu ama **üzerinde koşum
yapılmadı**: eldeki arşiv zaten 658 benzersiz içeriğin **tamamını** kapsıyor
(`içeriğe bağlanan: 658, bağlanamayan: 0`). Aynı baytlar, deterministik model
→ aynı sayılar. Paylaşımlı servisten 2,5 saat harcamak ölçüme hiçbir şey
katmazdı.

## 6. Sunumda ne verilecek

Üç sayı yan yana, hangisinin ne olduğu açıkça:

| küme | n | pano | forklift | yetkisiz |
|---|---|---|---|---|
| `eval_defense` (sevk ölçümü) | 197 | +0,960 | +0,881 | +0,689 |
| **tam set, kanonik** | **658** | **+0,842** | **+0,795** | **+0,679** |
| karıştırıcıdan arınmış katman | 54–91 | (n/a) | (n/a) | **+0,668** |

`isg_match` iki sayıyla: **0,667** (dört sınıf) ve **0,892** (kapsanan üç).
