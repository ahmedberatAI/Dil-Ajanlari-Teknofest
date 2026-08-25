# ÖN KAYIT — yaya yolu: ilişkisel soru yerine YEREL NİTELİK sorusu

Tarih: **2026-08-25**, kod yazılmadan ve koşumdan **ÖNCE**. Dal: `d34-isg-veri-kkd`.
Bu belgedeki hiçbir eşik sonuç görüldükten sonra değiştirilmeyecek (§7).

## 0. Neden yeniden açılıyor

`Safe_Walkway_Violation` dört İSG sınıfından biri ve **kapsanmıyor**.
Kapsansaydı `isg_match` 0,646 → 0,865 olurdu; yani dört-sınıf skorundaki
açığın **tamamı** bu sınıf.

Daha önce **dokuz kol denendi, dokuzu da reddedildi**
(`docs/yaya_yolu_kapanis_2026-08-25.md`). Ama dokuzunun hepsi aynı soru
tipinin varyasyonuydu: *"kişi çizgiye ne kadar yakın"* (ilişkisel) ya da
*"içinde mi dışında mı"* (ikili). Değişen şey hep ROI, fps veya eşikti.

**Soru tipinin kendisi hiç değişmedi.** Bu kol onu değiştiriyor.

### Emsal — bu deponun kendi tarihinden
Pano slotu da önce ilişkisel/anlamsal soruldu (*"pano kapağı açık mı?"*) ve
**dejenere** çıktı: 34/34 klipte aynı cevap. Aynı fiziği **yerel ve ölçülebilir**
bir nitelik olarak sorunca (*"pano bölgesi 0-10 arası ne kadar koyu?"*)
MCC +0,960'a çıktı.

Yaya yolunda da aynı dönüşüm deneniyor: iki nesne arasındaki **mesafe** yerine
tek bir noktadaki **yüzey**.

## 1. Kol tanımı

**Yeni slot** `yaya_zemin` — *"Yürüyen kişinin ayaklarının altındaki zemin
hangisi?"*

    secenekler = ["YESIL_BOYALI_YOL", "SARI_CIZGI_UZERI", "GRI_BETON", "GORUNMUYOR"]

Kural: `GRI_BETON` → `Safe_Walkway_Violation`.

ROI, kapsam, fps ve görüş muhafızı alanları **mevcut mesafe slotuyla birebir
aynı** tutulacak. Böylece iki slot arasındaki tek fark **soru tipi** olur;
başka hiçbir değişken oynamaz.

**İkinci kol (İKİNCİL)** `ON_AZAMI` — yol kuralına
`on_slot="makine_basinda_kisi", on_azami=0` üst sınırı: makinenin başında biri
duruyorsa yol kuralı ateşlemez. Ek VLM çağrısı **yok** (slot zaten dolduruluyor).

## 2. BİRİNCİL kol tek ve şimdiden ilan ediliyor

**BİRİNCİL: `yaya_zemin` (tek başına).** Diğer üç karar kuralı
(mesafe / mesafe+kapı / zemin+kapı) **İKİNCİL** etiketiyle raporlanacak ve
**Holm** düzeltmesine tabi olacak.

Gerekçe: bu sınıfta daha önce 9 kol denendi; bu koşumla toplam karşılaştırma
13'e çıkıyor. Birincil kolu önceden tek olarak ilan etmek, çoklu karşılaştırma
şişmesini engelleyen tek dürüst yol.

**Bir ikincil kol geçerse bu SEVK KARARI DEĞİLDİR** — yalnızca ikinci bağımsız
bir teyit koşumu adayı olur.

## 3. KABUL ÖLÇÜTÜ — kapanış belgesinden DEĞİŞTİRİLMEDEN devralındı

Aynı anda ikisi birden:

| kapı | eşik | mevcut (mesafe slotu) |
|---|---|---|
| çift içi MCC | **≥ +0,45** | +0,313 |
| saha kesinliği | **≥ 0,237** | 0,190 |

Biri sağlanmazsa **RET**. (Saha kesinliği = doğru sınıf ateşlemesi / tüm
ateşleme, 197 klip üzerinde. Çift bazlı metrik saha davranışını gizler.)

**İkincil sayı:** `isg_match` (4 sınıf) 0,646'dan ≥ **0,76**'ya çıkmalı.
Altında kalırsa kol *"ölçüsel olarak geçti ama sistem faydası yok"* diye
işaretlenir ve **sevk edilmez**.

## 4. ÖN-RET KAPILARI — sonuca bakmadan uygulanır

| # | kapı | eşik |
|---|---|---|
| a | **DEJENERELİK** | sorulan kliplerin ≥ %90'ı aynı seçeneği verirse anında RET (dokuz kolun 1. ve 5.'si tam böyle düştü) |
| b | **BULAŞMA** | aynı koşumda sevk edilen üç sınıfın karışıklık matrisi `TP23/FP0/FN1/TN25`, `TP24/FP2/FN1/TN23`, `TP19/FP2/FN6/TN23` değerlerinden **saparsa** ölçüm geçersiz; kol değerlendirilmez, önce sapmanın kaynağı bulunur |
| c | **ÇERÇEVELEME** | yalnız kamera açısından kurulan taban bu çiftte `\|MCC\| ≥ 0,30` verirse skor bilgiden değil çerçeveden geliyordur → RET |

## 5. Ölçüm tasarımı

Tek koşum, çok kol, **eşleşmiş**. Koşumda `yaya_zemin` + `yaya_cizgi_mesafe` +
`makine_basinda_kisi` **birlikte** doldurulur; sonra dört karar kuralı **aynı
ileri geçiş kümesinden** yeniden puanlanır. Kollar arası fark modelden değil
**yalnızca karar kuralından** gelir. Eşleşmiş test: **McNemar exact**.
Eşlenemeyen satırlar sessizce atılmaz, raporlanır.

Yol slotları sevk arşivini kirletir → **ayrı koşum, ayrı ara-kayıt dosyası**.
Künyeye yeni alanların girdiği koşumdan önce doğrulanacak (`isg_lens` ve
`panel_roi`'de iki kez yaşanan kusur).

## 6. Bilinen risk — kayda geçiriliyor

Beklenen RET olasılığı **yüksek (~%60)**. En olası kırılmalar:
1. Geniş plan grubunda yol uzak ve küçük; ROI içinde ayak bölgesi birkaç piksel
   kalır ve renk sorusu da dejenere olur.
2. Beyaz dengesi klipten klibe kayıyor (yeşil-mavi ekseninde %40 düşüş ölçüldü);
   "yeşil" kararsız olabilir.
3. Kapı 2 (saha kesinliği) tek başına bu kolla geçilemeyebilir — bu yüzden
   `ON_AZAMI` aynı koşumda ölçülüyor.

**Arşivden hesaplanan projeksiyonlar kanıt değildir**, post-hoc triyaj verisidir.
Gerçek sonuçlar o tavanların altında beklenmelidir.

## 7. Ne olursa ne yapılacak

| sonuç | eylem |
|---|---|
| birincil kol iki kapıyı da geçer **ve** isg_match ≥ 0,76 | sevke alınır |
| iki kapıyı geçer ama isg_match < 0,76 | "faydasız geçiş" olarak yazılır, SEVK EDİLMEZ |
| ön-ret kapılarından biri kapanır | anında RET, sebep yazılır |
| ikincil kol geçer, birincil geçmez | teyit koşumu adayı; tek başına sevk YOK |
| hepsi RET | onuncu ret olarak kayda geçer, sınıf kapalı kalır |

Hiçbir eski skor silinmeyecek. `docs/yaya_yolu_kapanis_2026-08-25.md`
güncellenecek, üzerine yazılmayacak.
