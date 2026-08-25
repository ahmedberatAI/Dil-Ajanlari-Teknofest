# Sistemin kalan sınırları — beş ret, tek sebep

Tarih: **2026-08-25** · Dal: `d34-isg-veri-kkd`

Bu belge, 2026-08-25'te ölçülen beş kolun sonucunu **tek bir açıklamada**
toplar. Amacı skor raporlamak değil, sistemin **neyi ölçebildiğini ve neyi
ölçemediğini** kanıtlı biçimde sınırlamaktır.

## 1. Ne denendi, ne çıktı

Güncel görüntü-dil modeli literatüründen 44 teknik tarandı, altı kol tasarlandı,
beşi ölçüldü. Hepsi **ön kayıtlı** ölçütle, eşikler koşumdan önce sabitlenerek.

| kol | mekanizma | hedef | ölçüt | ölçülen | karar |
|---|---|---|---|---|---|
| S1 | yumuşak eşik `P(≥T) ≥ 0,50` | eşik kırılganlığı | ΔMCC ≥ +0,03 | +0,006 | RET |
| S3 | yumuşak ön koşul kapısı | geniş plan kaçırmaları | MCC ≥ +0,75 | +0,689 | RET |
| — | kişi-başına kırpma (CPU tespiti) | referans | fizibilite | geniş planda **0 kişi** | açılmadı |
| 10 | yaya yolu: ilişkisel → yerel soru | kapsanmayan sınıf | MCC ≥ +0,45 | **+0,000** | RET |
| 10b | çapraz ön koşul (`on_azami`) | çapraz ateşleme | iki kapı birden | 0,324 **ama** +0,089 | RET |
| B1 | yelek sorusu ROI kırpmasında | referans | MCC ≥ +0,78 | **+0,500** | RET |
| S2 | kademeli önem derecesi | sevk oranı | — | mekanizma yanlış | koşulmadı |

Ayrıca **Set-of-Mark** elendi (açık kaynak modellerde zarar verdiğine dair
ölçüm) ve **yelek dedektörünü hüküm için kullanmak** elendi (ölçülüp çürütüldü).

## 2. Beş retin ORTAK sebebi

Kollar birbirinden bağımsız tasarlandı ama hepsi aynı duvara çarptı:

> **Gözlem düzlemi, yeri SABİT olan şeyleri ölçebiliyor.
> Yeri değişen şeyleri ölçemiyor.**

Bunu tesadüf değil, kanıt yapan şey sevk edilen üç kuralın da aynı ilkeye
uyması:

| kural | ölçülen şeyin yeri | MCC |
|---|---|---|
| `Opened_Panel_Cover` | pano **sabit** — dar ROI ile kırpılabiliyor | **+0,960** |
| `Carrying_Overload_with_Forklift` | çatal forklifte sabit, forklift kadrajı dolduruyor | **+0,881** |
| `Unauthorized_Intervention` | "makinenin başındaki **kişi**" — yeri değişken | **+0,689** |
| `Safe_Walkway_Violation` | yürüyen **kişi** + çizgiyle **ilişkisi** | kapsanmıyor |

Sıralama tam olarak "ölçülen şeyin yeri ne kadar sabit" sırasıdır.

### Kanıt 1 — kırpmayı zorlamak sinyali yok ediyor (B1)
Yelek sorusunu pano ROI'sine taşıdık. Referans tekleşmedi, **cevap tekleşti**:
ihlal sınıfında 25/25 "YOK" (üç kaçırma kurtuldu) ama normal sınıfta da
11/25 "YOK" (dokuz doğru cevap kayboldu). Kırpma panoyu içeriyor, kişinin
yeleğinin bulunduğu gövdeyi kesiyor. MCC +0,689 → +0,500.

### Kanıt 2 — kırpmayı kişiye kilitlemek mümkün değil
Kişiyi bulmak için CPU'da tespit denendi (yerel GPU yasak, CPU serbest).
Bilinen üç geniş-plan kaçırmasında: **iki klipte 0 kişi**, üçüncüsünde en iyi
kutu karenin %3×%12'si (22,4x büyütme gerekir). Yani "geniş planda kişi
seçilemiyor" tanısı VLM'e özgü değil — **o ölçekte kişi çözünürlük altında.**

### Kanıt 3 — soru tipini değiştirmek de yetmiyor (10. kol)
Yaya yolunda dokuz kol "mesafe"/"içinde-dışında" varyasyonuydu. Onuncu kol
soruyu **yerel** yaptı: *"ayağının altındaki zemin hangisi?"* Sonuç: cevap
dağılımı **altı sınıfta neredeyse özdeş** (ihlal sınıfıyla onun normal
karşılığı arasında bile ayrım yok). Slot sınıf bilgisi taşımıyor.

Sebep aynı: soru yereldi ama **kırpma yerel değildi** — ROI karenin alt
yarısının tamamı, sarı çizgi her klipte kadrajda, model kişinin ayağına değil
kadrajın baskın çizgisine demirliyor.

### Kanıt 4 — sorun kalibrasyon DEĞİL
Kısıtlı çözmenin dağılımı okundu (tek geçiş, ek maliyet yok). Kaçırılan
kliplerde model **%92-99,7 emin** ve baktığı kişi için **haklı**. Yani belirsiz
değil, yanlış yere bakıyor. Hiçbir olasılık eşiği bunu çözemez — S1 ve S3'ün
düşme sebebi budur.

## 3. Bunun anlamı

**Sistem kırılgan değil, sınırlı.** Ve sınır ölçülmüş durumda:

- Sabit konumlu tehlikeler: **+0,881 ile +0,960 arası** (iki kural)
- Değişken konumlu tehlikeler: **+0,689** (bir kural), kapsanmayan bir sınıf
- Bu sınırı aşmak, kişiyi **konumlandırabilen** bir algı katmanı gerektirir;
  mevcut çözünürlük ve yerel-GPU kısıtı altında ölçüldü ve **çalışmıyor**

Sevk edilen eşiklerin kırılgan olmadığı ayrıca doğrulandı: yumuşak eşik hiçbir
çiftte anlamlı kazanç üretmedi, yani eşikler dağılımın **kararlı** bölgesinde
duruyor.

## 4. Kapatılan soru işaretleri

| soru | cevap | belge |
|---|---|---|
| Eşikler kırılgan mı? | Hayır — yumuşak eşik kazanç üretmiyor, kararlı bölgede | `yumusak_esik_sonuc` |
| Yaya yolu neden kapsanmıyor? | Slot sınıf bilgisi taşımıyor; kırpma kişiye kilitlenemiyor | `yaya_zemin_sonuc` |
| Altı kaçırma neden? | A: çözünürlük altı (tespit de göremiyor) · B: referans, kalibrasyon değil | `yelek_roi_sonuc` |
| %54 sevk çok değil mi? | %45,9 bildir-kaydet, **%8,2** acil; bildirimler olgusal olarak doğru | `sevk_oraninin_anatomisi` |
| Ölçüm altyapısı güvenilir mi? | Künye tamlığı artık **mekanik** olarak test ediliyor (6 eksik bulundu) | `test_kunye_tamligi.py` |

## 5. Sevk edilen yapılandırma DEĞİŞMEDİ

Beş kolun hiçbiri sevke girmedi. Üç kural, eşikleri ve ayarlarıyla aynı:

    Opened_Panel_Cover               +0,960   TP23 FP0 FN1 TN25
    Carrying_Overload_with_Forklift  +0,881   TP24 FP2 FN1 TN23
    Unauthorized_Intervention        +0,689   TP19 FP2 FN6 TN23
    isg_match  0,646 (4 sınıf) / 0,865 (kapsanan 3 sınıf)

Bu üç matris, **dört bağımsız koşumda birebir** yeniden üretildi (biri iki
ekstra slot sorulurken, biri yelek ROI'si açıkken). Tekrar üretilebilirlik
kanıtlı.

Yeni yetenekler kodda **varsayılan KAPALI** duruyor (K2): `slot_guven`,
`yelek_roi_vlm`, `yelek_on_roi_vlm`, `yaya_zemin` slotu, `Kural.on_azami`.
