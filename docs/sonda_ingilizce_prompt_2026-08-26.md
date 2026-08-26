# SONDA — İngilizce prompt, hata kümesi + kontrol kümesi

Tarih: 2026-08-26 · **SONDA'dır, HÜKÜM DEĞİLDİR**
Düzenek: eşleşmiş, 27 klip (17 hata + 10 kontrol), 2 koşul, tam boru hattı

**Neden hüküm değil:** hata kümesi tanımı gereği yanlıdır — yalnızca
başarısız olduğumuz klipler seçildi, orada ancak iyileşme görülebilir.
Kontrol kümesi bu yüzden var: asıl soru *"hatalar düzeliyor mu"* değil,
**"düzelirken doğruları bozuyor muyuz"**.

Çeviri **anlamı birebir** korudu; tehdit merceğinin şiddet ağırlıklı seçenek
listesi aynen çevrildi, "düzeltilmedi" — aksi hâlde dil etkisi içerik
etkisiyle karışırdı. Çıktı dili Türkçe kaldı (şartname §4).

## Sonuç

| küme | n | sonuç |
|---|---|---|
| **kontrol** (şu an doğru) | 8 ölçülebilir | **bozulan 0** · korunan 8 |
| sessiz kaçırma (İSG ihlali var, model "anormal yok" dedi) | 9 | **düzelen 0** · aynı 9 |
| sahte tehlike (Normal klipte uydurma) | 7 | **düzelen 2** · aynı 5 |
| yanlış yorum (yangın→kavga) | 1 | kavga iddiası düştü, yangın yine yok |

"Anormal durum yok" diyen klip: TR **8/27** → EN **9/27** (değişmedi).

Düzelen iki klip: `Normal_Videos_928` (olay 1→0, risk Yüksek→Düşük),
`Normal_Videos_932` (olay 1→0, risk Orta→Düşük).

## Yorum

İngilizce prompt **tek yönlü ve küçük** bir etki üretiyor: model **daha az
iddia** ediyor. Bu, yanlış-pozitif hatalarda yardım ediyor (7'de 2), kaçırma
hatalarında **hiç** etmiyor (9'da 0).

Yani bu bir **eşik kayması**, algı iyileşmesi değil — reddedilen beş İSG
prompt kolunun mekanizmasının aynısı, sadece ters yönde. `isg_lens` eşiği
aşağı çekip recall'u şişirmişti; İngilizce eşiği yukarı çekip iddiayı
kısıyor. İkisi de modelin **gördüğünü** değiştirmiyor.

## Sınırlar

- Yangın klibi sonucu **n=1** ve güvenilmez: aynı klipte 6 tekrarla ölçüldü,
  kavga iddiası koşumdan koşuma değişiyor (bizim main 6/6, d-35 4/6).
- Kontrol kümesinde "bozulan 0" n=8'de ölçüldü; Wilson üst sınırı ~%30.
  "Bozmuyor" demek için yeterli değil, "bariz bozmuyor" demek için yeterli.
- Boru hattı `temperature=0` değil; tek koşumlu karşılaştırmalar gürültülü.

## Karar

**Sevk edilmez.** Kazanç küçük ve tek yönlü, ölçüm zayıf, ve şartname
açısından gereksiz bir görüntü riski taşıyor (bkz. aşağı). Asıl kusur —
modelin yangını/yaya ihlalini **görmemesi** — dil değişikliğiyle
çözülmüyor.

**Şartname notu:** İngilizce prompt kurallara aykırı DEĞİL. Türkçe
zorunluluğu geçen dört maddenin dördü de **çıktıya** bağlı
("Sistem tarafından üretilen çıktılar ... Türkçe ile ifade edilmelidir").
Prompt, kod ve iç muhakeme hiçbir maddede geçmiyor. Puanlama tablosu da
prompt'u dil olarak değil **etkinlik** olarak ölçüyor ("prompt engineering").
