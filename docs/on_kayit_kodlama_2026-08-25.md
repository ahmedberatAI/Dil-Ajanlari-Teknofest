# ÖN KAYIT — yeniden kodlama kontrolü (koşumdan ÖNCE yazıldı)

## Neden
Bu sette dosya özellikleri etiketi tek başına tahmin edebiliyor. Bizim
GÖNDERDİĞİMİZ baytlarda ölçüldü:

    forklift çifti : bit hızı +0,882  (orijinalde +1,000)
    yetkisiz çifti : fps      +1,000  (orijinalde +0,882)
    pano çifti     : en yüksek +0,433

Yani forklift (+0,851) ve yetkisiz (+0,689) skorlarımız, içerikle ilgisiz
bir eşiğin ulaştığı seviyenin ALTINDA. Bu skorların görsel anlamadan
geldiği KANITLANMAMIŞTIR.

## Kontrol
`kodlama_normalize=True` → gözlem düzlemi videoları ORTAK SPEKTE kodlanır:
fps=8 sabit, bit hızı 800k sabit. Doğrulandı: fps kanalı +0,000'a düşüyor,
forklift bit hızı +0,882 → +0,577.

## Yorum kuralı (SONUÇTAN ÖNCE sabitlendi)
- Skor **hayatta kalırsa** (≥ +0,70 forklift, ≥ +0,60 yetkisiz, ≥ +0,85 pano):
  içerikten geliyor demektir; sızıntı skoru üretmiyor.
- Skor **çökerse**: önceki sayı kodlama izini okuyordu ve GERİ ÇEKİLMELİDİR.
- Ara değerler: kısmi katkı; iki sayı da yan yana raporlanır, tek sayı
  seçilmez.

Hangi sonuç çıkarsa çıksın raporlanır. Kontrol kolu ARŞİVLENİR, eskisi SİLİNMEZ.
