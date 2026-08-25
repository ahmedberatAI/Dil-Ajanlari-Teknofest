# Yumuşak eşik — ölçüldü ve REDDEDİLDİ

Tarih: **2026-08-25** · Ön kayıt: `docs/on_kayit_yumusak_esik_2026-08-25.md`
Arşiv: `benchmark/results/eval_20260825_114341.json` (197 klip, `slot_guven=1`)
Puanlayıcı: `benchmark/yumusak_esik.py`

## 1. Karar

| kol | ön kayıtlı ölçüt | ölçülen | karar |
|---|---|---|---|
| **S1** yumuşak eşik `P(≥T) ≥ 0,50` | hiçbirinde düşme yok **ve** en az birinde ΔMCC ≥ +0,03 | en iyi ΔMCC **+0,006** | **RET** |
| **S3** yumuşak ön koşul kapısı | `Unauthorized_Intervention` MCC ≥ +0,75 ve FP ≤ 4 | MCC **+0,689**, FP 2 | **RET** |
| **S2** kademeli önem derecesi | — | ölçülmedi (kendi koşumunu gerektiriyor, bkz. ön kayıt eki) | açık |

Sevk edilen sert kural yerinde kalıyor.

## 2. Sayılar

```
cift      kip                           TP  FP  FN  TN      MCC   saha kes.
forklift  sert (SEVK EDILEN)            24   2   1  23   +0,881   0,923 (24/26)
forklift  S1 yumusak esik p*=0,50       25   3   0  22   +0,886   0,833 (25/30)
            -> McNemar   duzeltti=1 bozdu=1 p=1,0000   dMCC=+0,006

pano      sert (SEVK EDILEN)            23   0   1  25   +0,960   0,411 (23/56)
pano      S1 yumusak esik p*=0,50       23   0   1  25   +0,960   0,442 (23/52)
            -> McNemar   duzeltti=0 bozdu=0 p=1,0000   dMCC=+0,000

yelek     sert (SEVK EDILEN)            19   2   6  23   +0,689   0,237 (19/80)
yelek     S1 yumusak esik p*=0,50       19   2   6  23   +0,689   0,237 (19/80)
yelek     S3 yumusak ON KOSUL p*=0,50   19   2   6  23   +0,689   0,221 (19/86)
            -> McNemar   duzeltti=0 bozdu=0 p=1,0000   dMCC=+0,000
```

Forklift'te tek düzelen klibe karşı tek bozulan klip var (McNemar p=1,00) ve
saha kesinliği **0,923 → 0,833** düşüyor: yumuşak eşik biraz daha çabuk
ateşliyor. Yani +0,006'lık çift-içi kazanç sahada bedelli.

## 3. Geçerlilik kontrolü — ÖNEMLİ

Sert kip, sevk edilen üç karışıklık matrisini **birebir** yeniden üretti:

    Carrying_Overload_with_Forklift  TP24 FP2 FN1 TN23   +0,881
    Opened_Panel_Cover               TP23 FP0 FN1 TN25   +0,960
    Unauthorized_Intervention        TP19 FP2 FN6 TN23   +0,689

Yani (a) çevrimdışı yeniden puanlama sadıktır, (b) `logprobs` enstrümantasyonu
kararları değiştirmiyor, (c) koşum tekrar üretilebilir kipte kaldı.
197/197 satır güven izi taşıyor — sessiz başarısızlık yok.

## 4. S3 neden başarısız oldu — koşumdan ÖNCE öngörülmüştü

Ön kayıt §3'te F2B için yazılmıştı; F2A için de aynısı çıktı. Altı bilinen
kaçırmanın dağılımları:

| klip | grup | `argmax(kişi)` | `P(kişi ≥ 1)` | yelek | güven |
|---|---|---|---|---|---|
| 1_tr18 | A (geniş plan) | 0 | **0,418** | YOK | 0,9998 |
| 1_tr84 | A | 0 | **0,358** | YOK | 0,9999 |
| 1_te5 | A | 0 | **0,101** | YOK | 1,0000 |
| 1_tr42 | B (çok kişi) | 3 | 1,000 | **VAR** | 0,9968 |
| 1_tr61 | B | 3 | 1,000 | **VAR** | 0,9978 |
| 1_tr81 | B | 3 | 1,000 | **VAR** | 0,9242 |

**A grubu:** kalan kütle üçünde de 0,50'nin altında. Kapıyı yumuşatmak
onları geçirmiyor. Eşiği 0,35'e çekmek ikisini kurtarırdı — ama eşik koşumdan
önce 0,50'de sabitlendi ve **oynatılmadı**. Bu sınıfta zaten 9 kol denenmiş
durumda; sonucu görüp eşik seçmek tam olarak kaçınılması gereken şey.

**B grubu:** model "yelek VAR" diyor ve **%92-99,7 emin**. Emin olmakta da
haklı — baktığı kişide gerçekten yelek var. Sorun **hangi kişiye baktığı**.
Bu bir kalibrasyon değil **referans (grounding)** sorunudur ve hiçbir olasılık
eşiği çözemez.

## 5. p* taraması — BETİMLEYİCİ, karar ölçütü DEĞİL

```
cift          0,10    0,20    0,30    0,40    0,50    0,60    0,70    0,80    0,90
forklift    +0,333  +0,469  +0,562  +0,718  +0,886  +0,840  +0,851  +0,783  +0,783
pano        -0,147  +0,802  +0,960  +0,960  +0,960  +0,960  +0,960  +0,960  +0,451
yelek       +0,602  +0,602  +0,645  +0,645  +0,689  +0,689  +0,689  +0,689  +0,689
```

Forklift eğrisi **kararsız**: +0,333'ten +0,886'ya çıkıp +0,783'e iniyor.
`p*`'yi bu veride seçmek doğrudan çoklu-karşılaştırma hatasıdır. 0,50'nin
tepeye yakın düşmesi hoş bir tesadüf, kanıt değil.

## 6. Kol reddedildi ama ölçüm boşa gitmedi

1. **Enstrümantasyon kodda kalıyor** (`slot_guven`, varsayılan KAPALI, K2).
   Ek çağrı ve ek gecikme yok; açıldığında her slotun dağılımı kaydediliyor.
2. **F2B'nin kök nedeni artık ölçülmüş durumda.** Daha önce "çok kişili sahne
   belirsizliği" deniyordu; şimdi biliyoruz ki model **emin ve haklı**, yanlış
   olan referans. Bu, kişi-başına kırpma kolunu gerekçelendiren ölçüm.
3. **Sert kuralın sağlamlığı doğrulandı.** Yumuşak eşiğin hiçbir çiftte
   anlamlı kazanç üretmemesi, mevcut eşiklerin dağılımın kararlı bölgesinde
   olduğunu gösteriyor — kırılgan bir noktada durmuyorlar.

## 7. Arşiv

Hiçbir eski skor silinmedi. Bu belge
`docs/skor_denetimi_2026-08-25.md` ve `docs/hata_analizi_2026-08-25.md`
belgelerinin **yanına** eklenir; §4'teki tablo hata analizinin "6 kaçırma iki
ayrı sebebe ayrılıyor" bulgusunu sayısallaştırır.
