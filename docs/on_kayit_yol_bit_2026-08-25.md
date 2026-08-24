# ÖN KAYIT — yaya yolu slotu: kodlama spekinin etkisi (koşumdan ÖNCE yazıldı)

## Gözlem
Yol slotu, kodlama normalizasyonu **öncesi** ayrılmış kümede MCC **+0,638**
verdi. Sevk edilen spekte (fps 8 + 800k sabit bit hızı) aynı slot **+0,119**.

## Hipotez
Yol sorusu zemindeki **ince çizgileri** okur. 800k sabit bit hızı, tam
genişlikte (1280×~360) bir ROI'de bu ince yapıları siliyor olabilir. Yani
kaybın sebebi fps değil **bit hızı**.

## Kollar (aynı 48 klip, aynı ROI, aynı soru)
    A  sevk edilen  : fps 8 + 800k CBR          (beklenen ~+0,12)
    B  fps 8 + CRF 26 (bit hızı serbest)
    C  normalizasyon YOK (özgün +0,638 speki)

## Kabul ölçütü (SONUÇTAN ÖNCE sabitlendi)
Kol B, A'yı en az **+0,30 MCC** geçerse bit hızı hipotezi doğrulanır ve yol
slotu için **ayrı bir kodlama speki** tanımlanabilir. Ayrıca:
  - Bit hızı bir SIZINTI kanalı olduğu için (forklift çiftinde +0,882),
    yol slotuna özel spek YALNIZCA yol çiftinde sızıntı ölçülüp
    **+0,60'ın altında** kaldığı doğrulanırsa kullanılabilir.
  - Yol çiftinde daha önce ölçülen bit hızı sızıntısı: **+0,227** (orijinal
    dosyalarda), yani bu şart hâlihazırda sağlanıyor gibi görünüyor —
    ama yeni spekte YENİDEN ölçülecek.

Kol B kazanamazsa yol slotu KAPALI kalır ve `isg_match` üç sınıf üzerinden
(0,865) ve dört sınıf üzerinden (0,646) YAN YANA raporlanır.
