# v13l sonuç atomlu kişi destek-kaybı — deney raporu

Tarih: 2026-08-28

## Sonuç

Ön kayıt kapısı **geçilmedi**.

- Kayıtlı destek-kaybı pozitiflerinde semantik kurtarma: `2/3`.
- Ön kayıt negatiflerinde yeni destek: `3/116`.
- API/oturum/ayrıştırma hatası: `0`.
- Karar: **reddedildi; doğrudan uzman olarak entegre edilmedi**.

Sonuç dosyası:
`benchmark/results/sonuclu_destek_kaybi_v13l_20260828_001944.json`.

## Yanlış desteklerin görsel denetimi

Üç yeni destek normal sınıfta değil, anomali karşıtlarındadır; ancak bu durum
onları kişi-düşmesi açısından doğru yapmaz:

- `1b1NOLpwCz8_trim_16.mp4`: kişi yükseltilmiş platform/lift üzerinde büyük bir
  yük taşımaktadır. Örneklenen karelerde kişinin bedeninin zemine düştüğü veya
  destekten asılı kaldığı açık değildir. Kapı yük hareketini kişi sonucu olarak
  yorumlamıştır.
- `9XXineiOxSo_trim_5.mp4`: konveyör çevresinde birden fazla kişi ve müdahale
  görünür. Önceden yerde/konveyörde bulunan kişi ile sonradan hareket eden kişinin
  kimliği ve tek bir kesintisiz düşme geçişi güvenilir biçimde bağlanamamaktadır.
- `J9WlxhcRAPo_trim_4.mp4`: oturan/eğilen kişiler vardır; örneklenen karelerde
  destekli dik durumdan tamamlanmış beden düşüşü açık değildir.

Doğru desteklerden `zJqzjDX-XFU_trim_45.mp4` kesintisiz koşma, takılma/destek
kaybı, zemine temas ve toparlanma zincirini açıkça göstermektedir. Diğer kayıtlı
pozitif `uOAJL-g4Y_w_trim_1.mp4` desteklenmiş olsa da küçük/uzak kişi geometrisi
nedeniyle daha belirsizdir. `87O1pBSGtR0_trim_102.mp4` kişi-görünürlüğü atomunda
reddedilmiştir.

## Kök neden

Üç bağımsız ve hafızasız soru aynı kişiyi gerçekten takip ettiğini kanıtlamadan
ayrı ayrı `A` üretebilmektedir. Özellikle yük, oturma/eğilme ve kalabalık müdahale
sahneleri; `geçiş` ile `sonuç` cevaplarının aynı kişiye ve aynı kesintisiz plana
ait olduğu yanılsamasını yaratmaktadır.

Bu nedenle v13l sonucu sonradan yeniden etiketlenmeyecek ve kabul edilmiş gibi
raporlanmayacaktır. Bir sonraki aday, bu üç atomun üstüne aynı kişi + açık önce
durum + kesintisiz geçiş + fiziksel son durum bağını tek kapalı seçimde ayrıca
zorunlu tutmalıdır.
