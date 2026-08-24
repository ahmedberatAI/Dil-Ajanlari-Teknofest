# ÖN KAYIT — yol slotuna KENDİ fps'i (koşumdan ÖNCE yazıldı)

## Ne öğrenildi
Bit hızı hipotezi ÇÜRÜTÜLDÜ: 800k CBR ile CRF26 birebir aynı (+0,217).
Kaybın kaynağı **fps**: normalizasyon yokken +0,535, fps 8'de +0,217.

Dağılımlar sebebi gösteriyor:
    fps 8   IHLAL: {5:11, 0:9, 7:4, 6:1}    <- bazı ihlaller "7" (uzak) diyor
    özgün   IHLAL: {0:12, 5:11, 6:2}        <- hiç 7 yok

Yaya yolu ihlali **anlık** bir durumdur — kişi çizgiyi bir anda geçer.
Kare seyreltmek o anı kaçırıyor. Pano statik, forklift süreklidir; bu yüzden
onlar fps 8'den etkilenmiyor (pano +0,960 ve forklift +0,881 normalize spekte
ölçüldü).

## Değişiklik
Slotlara **kendi fps'i** verilebiliyor (ROI ve kapsam ile aynı desen).
Yol slotu özgün fps ile kodlanır; diğer üç slot fps 8'de kalır.

## Kabul ölçütü (SONUÇTAN ÖNCE sabitlendi)
197 kliplik tam koşumda, görüş muhafızı AÇIK:
  1. yol çifti MCC **≥ +0,45**
  2. yol kuralının **saha kesinliği ≥ 0,237** (sevk edilen en düşük kural,
     yelek, bu seviyede)
  3. diğer üç kuralın MCC'si **düşmemeli** (yol slotu bağımsızdır; düşerse
     bir yan etki var demektir)
Üçü birden sağlanırsa yol slotu SEVK EDİLİR. Aksi halde KAPALI kalır ve
`isg_match` üç sınıf (0,865) ve dört sınıf (0,646) üzerinden YAN YANA raporlanır.
