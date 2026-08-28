# v13b doğrudan aile saflaştırma sonucu

Sonuç: **Doğrudan çalışma reddedildi**  
Ham sonuç: `benchmark/results/endustriyel_aile_saflastirma_v13b_20260827_225105.json`

Scout olmadan 109 negatifte doğrudan stres:

- geniş endüstriyel enerji/ekipman: 4/5 TP, 1 FP,
- fiziksel bağ atomlu makine sıkışması: 3/3 TP, 5 FP,
- kişi destek kaybı: 2/2 TP, 7 FP.

Hiçbiri doğrudan fallback olarak kullanılamaz. Kilitli v13a scout seçimiyle çevrimdışı
bileşimde üç dal toplam 9 TP/0 FP verdiği için yalnız scout+allowlist biçimi v13c'de
yeni bağımsız API tekrarıyla sınanacaktır.
