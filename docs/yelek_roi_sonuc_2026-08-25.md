# Yelek ROI kolu — ölçüldü ve REDDEDİLDİ (kırpma sinyali yok ediyor)

Tarih: **2026-08-25** · Ön kayıt: `docs/on_kayit_yelek_roi_2026-08-25.md`
Arşiv: `benchmark/results/eval_20260825_125540.json` (197 klip)
Taban arşivi: `benchmark/results/eval_20260825_114341.json`

## 1. Karar

**B1 (BİRİNCİL): MCC +0,500 → RET.** Ölçüt ≥ +0,78 idi.
Ayrıca ön-ret kapısı (a) **dejenerelik** de kapandı: %90,9 ≥ %90.

**B2 (ikincil) koşulmadı — ölçülmüş sebeple elendi.** B2'de yelek slotunun
ROI'si B1 ile **birebir aynıdır**; dolayısıyla dejenerelik kapısı yapı gereği
yine kapanır. Ayrıca aşağıdaki teşhis, sorunun ön koşul kapısı değil
**sinyal kaybı** olduğunu gösteriyor; ön koşulu da aynı kırpmaya taşımak
kapıyı daha da kapatır, sinyali geri getirmez.

| | taban (tam kare) | B1 (ROI) |
|---|---|---|
| TP / FP / FN / TN | 19 / 2 / 6 / 23 | 22 / 10 / 3 / 15 |
| **MCC** | **+0,689** | **+0,500** |
| saha kesinliği | 0,237 (19/80) | 0,237 (22/93) |

## 2. Hipotezin YARISI doğrulandı

Kolun hipotezi şuydu: kırpma "makinenin başındaki kişi" referansını yapısal
olarak tekler, B grubundaki üç kaçırma kalkar.

**Kaçırma tarafı doğrulandı.** `Unauthorized_Intervention`'da yelek cevabı:

| | YOK | VAR |
|---|---|---|
| taban | 22 | 3 |
| **B1** | **25** | **0** |

Üç kaçırmanın üçü de kurtarıldı — FN 6 → 3.

**Ama normal taraf çöktü.** `Authorized_Intervention`'da:

| | VAR | YOK |
|---|---|---|
| taban | 23 | 2 |
| **B1** | **14** | **11** |

Dokuz doğru "VAR" cevabı "YOK"a döndü — FP 2 → 10.

Net etki negatif: MCC +0,689 → +0,500.

## 3. Teşhis — kırpma referansı düzeltmedi, KANITI yok etti

`panel_roi_vlm = 0,00 0,47 0,29 0,81` bir **pano kırpmasıdır, kişi kırpması
değil.** Kadraj panoyu içeriyor ama panonun önünde duran kişinin **gövdesini
kesiyor** — yelek tam orada.

Model kanıtı göremediğinde varsayılan cevabı "YOK" oluyor. Yani:

> Referans tekleşmedi; **cevap tekleşti.**

Kanıt: ihlal sınıfında 25/25 "YOK" çıkması bir başarı gibi görünüyor ama
normal sınıfta da 11/25 "YOK" çıkması aynı mekanizmanın ürünü. Slot ayırt
etmeyi bıraktı, sabit cevaba yaklaştı — dejenerelik kapısının ölçtüğü şey
tam olarak bu.

Dejenerelik kapısının **doğru kurulduğu** ayrıca doğrulandı: aynı kapı
sevk edilen tam-kare kolda **%83,8** ile açık kalıyor (YOK 165 / VAR 32) ve
o kolda sınıf ayrımı çok net (`Unauthorized` YOK 22/VAR 3 ·
`Authorized` VAR 23/YOK 2). Yani kapı çalışan kuralı reddetmiyor, bozulanı
yakalıyor.

## 4. Bulaşma kapısı GEÇTİ

Diğer iki çift birebir korundu:

    Carrying_Overload_with_Forklift  TP24 FP2 FN1 TN23  +0,881   birebir
    Opened_Panel_Cover               TP23 FP0 FN1 TN25  +0,960   birebir

## 5. F2B'nin durumu — kapatılıyor

Üç ayrı mekanizma denendi, üçü de ölçüldü:

| yaklaşım | sonuç |
|---|---|
| yumuşak eşik / güven kalibrasyonu | model **emin ve haklı** — kalibrasyon sorunu değil (RET) |
| kişi-başına kırpma (CPU tespiti) | geniş planda **0 kişi**, kalabalıkta 11-13 kişi arasından seçim = yeni tahmin noktası (açılmadı) |
| sabit ROI kırpması | referans değil **kanıt** kayboldu, MCC +0,689 → +0,500 (RET) |

Ortak sonuç: **kırpmanın kişiyi içermesi gerekiyor, ama kişinin yeri sabit
değil ve bu çözünürlükte bulunamıyor.** Yaya yolu sınıfında çıkan teşhisin
aynısı — ve pano slotunun neden çalıştığını açıklayan aynı ilke:
**panonun yeri sabittir, kişinin yeri değildir.**

`Unauthorized_Intervention` **+0,689'da kalıyor.** Altı kaçırmanın ikisi de
bu veriyle çözülemez olarak kayda geçiyor:
- A grubu (3 klip): kişi çözünürlük altında — VLM de dedektör de göremiyor
- B grubu (3 klip): kişi görünür ama referans tekilleştirilemiyor

## 6. Kod

`yelek_roi_vlm` ve `yelek_on_roi_vlm` alanları **varsayılan BOŞ** olarak kodda
kalıyor (K2: sevk davranışı bayt özdeş). Mekanizma ileride daha dar bir
kişi-kilitli kırpma mümkün olursa hazır.
