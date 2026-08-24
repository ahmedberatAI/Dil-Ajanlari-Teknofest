# ÖN KAYIT — yaya yolu kuralına GÖRÜŞ MUHAFIZI (koşumdan ÖNCE yazıldı)

## Neden
Yaya yolu slotu ölçüldü ve ayrılmış kümede doğrulandı (MCC +0,638), ama SEVK
EDİLMEDİ: ateşlemelerinin 49'u **forklift kamerasında** (kamera 14) — yaya
yolu çizgisi sorusunun anlamsız olduğu bir görüntüde. Saha kesinliği 0,151.

Sızıntının 49/128'i tek bir kaynaktan: yanlış kamera.

## Muhafız
`dilajan/pano.py:gorus_imzasi` (16×9 medyan gri, z-normalize) + Pearson.
Kamera 14 referans imzası, forklift-ihlal kliplerinin ortalaması.
Benzerlik ≥ eşik → **kamera 14** → yol slotu SORULMAZ.

Ölçüldü (96 klip): kamera 14 benzerliği min **0,842**, kamera 9 maks **0,575**.
Eşik **0,708** (marj 0,267).

## Sızıntı kontrolü — muhafız ETİKET tahmin etmemeli
Görüş imzasının çift İÇİNDE ihlal/normal ayırma gücü:

    yol   çifti : |MCC| 0,385   -> kabul edilebilir
    pano  çifti : |MCC| 0,275   -> kabul edilebilir
    yetki çifti : |MCC| 0,833   -> SIZINTI

Bu yüzden muhafız **yalnızca yol slotuna** uygulanır. Yelek kuralına
uygulanması YASAKTIR — orada görüş imzası etiketle 0,833 korele.
(Bu tam olarak geofence'in reddedilme sebebiydi.)

## Kabul ölçütü (SONUÇTAN ÖNCE sabitlendi)
1. Yol çiftinin KENDİ karışıklık matrisi **değişmemeli** (muhafız saf gürültü
   filtresidir; kendi çiftinde TP/FP/FN/TN aynı kalmalı). Değişirse muhafız
   etiket bilgisi taşıyor demektir → RET.
2. Forklift kliplerindeki ateşleme **49/50 → ≤ 5** olmalı.
3. Yol kuralının saha kesinliği, hâlihazırda SEVK EDİLEN en düşük kuralın
   (yelek, 0,237) **altına düşmemeli**.

Üçü birden sağlanırsa yol slotu SEVK EDİLİR; yoksa kapalı kalır.
Sonuç ne olursa olsun raporlanır.
