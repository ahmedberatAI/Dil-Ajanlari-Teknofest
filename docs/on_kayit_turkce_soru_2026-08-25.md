# ÖN KAYIT — slot soruları GERÇEK TÜRKÇE (koşumdan ÖNCE yazıldı)

## Gözlem
Slot soruları ve gözlem sistem promptu **ASCII'leştirilmiş Türkçe** ile yazılı:

    "Makinenin/panonun BASINDA DURAN KISIDE yesil reflektif yelek var mi?"
    "Sen bir endustriyel kamera olcum sistemisin."

Bunlar **modele prompt olarak gidiyor**. Türkçe eğitilmiş bir model için
ASCII bozuk Türkçe dağılım dışıdır; düzgün Türkçe daha iyi çalışabilir.

Kural şablonlarında aynı düzeltme ölçülmüş bir kazanç sağlamıştı
(`isg_match` 0,535 → 0,646) — ama orada mekanizma farklıydı (eşleştirici),
burada modelin **anlaması** söz konusu.

## Kollar
    A  mevcut ASCII sorular          (taban)
    B  gerçek Türkçe sorular + sistem promptu
Aynı klipler, aynı kodlama speki (sevk edilen), aynı eşikler.

## Kabul ölçütü (SONUÇTAN ÖNCE sabitlendi)
B kolu, üç çiftin **MCC toplamını** en az **+0,10** artırmalı VE hiçbir çiftte
**−0,05'ten fazla** düşüş olmamalı.

Sağlanırsa sorular gerçek Türkçeye çevrilir ve tam koşumla doğrulanır.
Sağlanmazsa mevcut ASCII sorular KALIR — ve bu, "ASCII bozuk Türkçe modeli
etkilemiyor" diye ölçülmüş bir bulgu olarak kaydedilir.

NOT: soru metinleri ölçülmüş metinlerdir; bu yüzden değişiklik ancak
ölçümle gerekçelendirilirse yapılır.
