# Ön kayıt — pano koyuluğu için başıboşluk kapısı

Tarih: 2026-08-27

## Sorun

`pano_koyuluk_0_10 >= 6` yalnızca sabit ROI'de koyu oyuk ölçer. Bu gözlem
tek başına kapağın tehlikeli biçimde **açık bırakıldığını** kanıtlamaz:
`Authorized_Intervention` kliplerinde yetkili kişi makine/pano başındayken de
aynı oyuk fiziksel olarak görünür. Mevcut şablon buna rağmen "açık
bırakılmış" hükmü kuruyor.

## Önceden belirlenen kol

`Opened_Panel_Cover` kuralı ancak iki gözlem birlikte sağlanırsa çalışır:

- `pano_koyuluk_0_10 >= panel_koyuluk_esik`;
- `makine_basinda_kisi == 0`.

Yeni model sorusu, yeni eşik veya etiket bilgisi eklenmeyecek. İkinci slot
zaten yetkisiz müdahale gözlem düzleminde bulunmaktadır. Ölçülemeyen kişi
sayısı ihlal sayılmayacak (fail-closed).

## Ölçüm ve kabul

Sonuç görülmeden sabitlenen kaynak:
`benchmark/results/eval_20260825_114341.json` içindeki slot güven izleri.

Kol şu koşulların tümünde kabul edilir:

1. `Opened_Panel_Cover` / `Closed_Panel_Cover` çiftinde MCC, +0,960
   tabanından 0,05'ten fazla düşmez;
2. panel pozitiflerinde FN en fazla 2 olur;
3. tüm normal kümede yalnız panel olayından kaynaklanan en az 5 yüksek yanlış
   alarm mekanik olarak kapanır;
4. forklift ve yetkisiz müdahale kural tanımlarına dokunulmaz;
5. kişi slotu ölçülemiyorsa pano olayı üretilmez.

## Sonuç — RED

Arşiv slot izleriyle mekanik sonuç:

- TP5 FP0 FN19 TN25, MCC +0,344;
- yalnız panel yüksek olayından gelen 17 normal alarmı kapatıyor;
- fakat panel pozitiflerinin 19/24'ünü de kesiyor.

Birinci ve ikinci kabul koşulları açık biçimde başarısızdır. Bu nedenle kişi
sayısı pano kuralına eklenmedi. Kök neden kişi sayımı değil, sabit ROI
kalibrasyonunun her videoda evrensel bir "açık bırakılmış pano" hükmü gibi
çalıştırılmasıdır. Güvenli çözüm bu kamera/tesis kuralını açık operatör
beyanına bağlamak; beyan yokken kuralı ve slot çağrısını çalıştırmamaktır.
