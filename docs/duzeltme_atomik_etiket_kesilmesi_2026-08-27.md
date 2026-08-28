# Düzeltme — atomik kapalı etiket kesilmesi

Tarih: 2026-08-27

v12g ilk koşusunda `kontrolsüz yük/çökme` ilişki rolü beş gerçek tehlikede
`KONTROLSUZ_DUSME_DEVRILME_C...` üretti. İzinli tam etiket
`KONTROLSUZ_DUSME_DEVRILME_COKME` idi. Neden model kararı değil, atomik çağrıların
`max_tokens=12` çıktı bütçesiydi.

`dilajan.isg_kanit.ATOMIK_MAX_TOKENS=40` yapıldı ve hem kare hem kaynak-video
yollarına uygulandı. Kapalı seçim açıklama üretmediği için bu değişiklik karar
uzayını genişletmez; yalnız izinli uzun etiketin tamamının taşınmasını sağlar.
Regresyon testi iki yolun da aynı bütçeyi kullandığını doğrular.

`benchmark/results/kapali_aile_tarama_v12g_20260827_204144.json` yük/çökme
ailesi için altyapı-hatalı ölçümdür. Ön kayıt kuralı ve örneklem değiştirilmeden
v12g tekrar koşulacaktır; ilk sonuç performans iddiası olarak kullanılmayacaktır.

