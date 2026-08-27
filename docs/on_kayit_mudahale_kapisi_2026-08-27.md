# Ön kayıt — yetkisiz müdahale için görünür eylem kapısı

Tarih: 2026-08-27

## Sorun

`makine_basinda_kisi >= 1` ve `yelek = YOK` gözlemleri, kişinin gerçekten
bakım/müdahale yaptığını göstermiyor. Rutin kumanda kullanımı veya makine
yanında oturma da bu iki koşulu sağlayabiliyor. Sonuçta sistem görünür bir
eylem kanıtı olmadan "yetkisiz müdahale" hükmü kuruyor.

Zor negatif: `data/_mislabeled_unsafe/eval_big_0_tr128.mp4`. Bu klipte kişi
makine yanında rutin kullanım yapıyor; yaralı/hareketsiz kişi yok.

## Önceden belirlenen kol

Kapalı cevaplı yeni gözlem:

- `BAKIM_MUDAHALE`: koruyucu kapak açma, makinenin içine el/alet uzatma,
  parça sökme-takma veya görünür bakım/arızaya müdahale.
- `RUTIN_KULLANIM`: kumanda kullanma, sandalyede oturma, normal üretim veya
  yalnızca makine yanında durma.
- `KISI_YOK`, `GORUNMUYOR`: kaçış seçenekleri.

Yetkisiz müdahale kuralı ancak mevcut kişi+yelek koşullarına ek olarak
`makine_faaliyet_turu == BAKIM_MUDAHALE` ise çalışacak.

## Ölçüm ve kabul

Eşlenmiş küme: `Unauthorized_Intervention` 25 pozitif +
`Authorized_Intervention` 25 negatif. Mevcut sevk tahmini arşivdeki aynı
slotlardan yeniden kurulacak; tek yeni ileri geçiş faaliyet slotudur.

Kol şu koşulların tümünde kabul edilir:

1. zor negatif `RUTIN_KULLANIM` veya eşdeğer biçimde ret edilir;
2. yeni kapı dejenere değildir (tek cevap oranı <%90);
3. çift içi MCC mevcut +0,689 tabanından 0,05'ten fazla düşmez;
4. yanlış pozitif sayısı mevcut 2'nin üzerine çıkmaz;
5. forklift ve pano kurallarının kod yoluna dokunulmaz.

Sonuç görülmeden soru, seçenekler ve eşikler bu dosyada sabitlendi.

## Sonuç — RED

Koşum: `benchmark/results/mudahale_kapisi_20260827_122650.json`.

- Zor negatif doğru biçimde `RUTIN_KULLANIM` seçildi.
- Ancak 50 eşlenmiş klibin 47'sinde `BAKIM_MUDAHALE` seçildi: tek cevap
  oranı %94 ile önceden belirlenen <%90 dejenere-olmama eşiğini aştı.
- Matris TP17 FP1 FN8 TN24, MCC +0,667 oldu; +0,689 tabanına göre kabul
  aralığında kalsa da dejenere-olmama koşulu bağımsız ve zorunluydu.

Bu nedenle faaliyet slotu kural motoruna eklenmedi. Genel çözüm, görünür
eylemi bu zayıf kapalı soruyla tahmin etmek yerine `yelek yok -> yetkisiz`
eşlemesini tesis beyanına bağlamaktır; beyan yoksa kural hiç çalışmaz.
