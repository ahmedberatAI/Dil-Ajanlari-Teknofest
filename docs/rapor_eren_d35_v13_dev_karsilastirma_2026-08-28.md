# Eren d-35 / mevcut v13n performans karşılaştırması

Tarih: 2026-08-28 (Europe/Istanbul)

## Kısa sonuç

Kilitli v13 geliştirme etiketlerine göre Eren `d-35`, anomali recall'unu
`%77 -> %90` yükseltti; fakat operasyonel normal FP'yi `%6 -> %22` ve dar FP'yi
`%5 -> %15` çıkardı. Ön kayıtlı birincil MCC mevcut v13n lehine
`0,7205 -> 0,6849` oldu. Eren kolu yaklaşık `1,92x` daha hızlıdır.

Bu, tek tarafın her ölçütte üstün olduğu bir sonuç değildir. Eşlenik testte Eren'in
recall kazancı ve mevcut modelin normal-FP avantajı ayrı ayrı güçlüdür; toplam doğru
klip sayısı farkı ise anlamlı değildir. Eren değişikliğini olduğu gibi birleştirmek
önerilmez. Duman/panik duyarlılığı, mevcut kanıt kapıları içinde seçici olarak
taşınmalıdır.

## Koşu kimliği

- Ön kayıt: `docs/on_kayit_eren_d35_v13_dev_karsilastirma_2026-08-28.md`
- Veri: `data/eval_genelleme_v13_dev`
  - 100 `Anomali/Hazard`, 100 `Normal/Normal`, 200 benzersiz klip.
  - Sıralı dosya-listesi parmak izi:
    `ab0c22d9b77ebb355f213e14fad2694ad48ee7e5d764b26bf5960991ba5252de`
- Mevcut kol sonucu:
  `benchmark/results/eval_20260828_012132.json`
  - Pipeline: `2026-08-28-isg-evidence-v13n-thermal-dust-terminal-abstain`
  - SHA-256: `8e82acf5e0ce74f3f6fb0c12b81cf3c0947013b080cf237328f6d74ed68bc6af`
- Eren kolu: `origin/d-35` @
  `86b0f0103e8540b9f6b2f8256e3634dc187f5bec`
- Eren sonucu:
  `benchmark/results/eren_d35_eval_20260828_020417.json`
  - SHA-256: `c497fba5e842970703abdeb5f263eb4de8a57562b7e29bbe8b4748e941559792`
- Her iki sonuçta 200/200 satır, 0 değerlendirme hatası vardır.
- `data/eval_genelleme_holdout_v13` açılmadı ve çalıştırılmadı.

## Çıkarım sözleşmesi ve mimari fark

Her iki kolda yalnız özel API
`https://evren-llmapi.ssyz.org.tr/v1` ve sabit model havuzu kullanıldı:

- `vlm`
- `llm-large`
- `llm-fast`

Sıcaklık `0.0`; yerel nesne/pose/KKD modelleri ve model indirme kapalıdır. Eren
kolundaki varsayılan-açık `verify_pose_falls`, ilk başlatmada yerel
`yolo11n-pose.pt` indirmeye kalktığı anda koşu 14 klipte durduruldu. Ağırlık ile ara
kayıt silindi ve bu satırlar sonuca katılmadı. Temiz tam koşu
`DILAJAN_VERIFY_POSE_FALLS=0` ile sıfırdan yapıldı; sonunda yerel model dosyası yoktu.

Bu bir yalnız-prompt A/B'si değildir:

- Mevcut v13n; görsel atom/slotları `vlm`, açık olay-zaman algısını `llm-large`,
  yapısal karar ve özeti `llm-fast` rollerine açıkça yönlendirir.
- Eren `d-35` ana graph yolunda `_get_vlm()` üzerinden varsayılan `llm-large` ile
  betimleme, olay çıkarma ve reason çağrılarını yapar. Slot gözlemleri `vlm` veya
  `llm-large` kullanabilir; bu benchmark yolunda `llm-fast` yapılandırılmış olsa da
  ana graph tarafından çağrılmaz.

Dolayısıyla ölçülen şey, aynı sabit model havuzunu farklı kullanan iki tam mimaridir.
Eren'in düşük gecikmesi de yalnız model hızından değil, daha az kanıt/koruma çağrısı
yapmasından gelir.

## Sonuçlar

Operasyonel ikili sınıflandırmada TP, anomali klibinde en az bir olaydır. FP, normal
klipte en az bir olay veya operasyonel fonksiyon tetiklemesidir.

| Metrik | Mevcut v13n | Eren d-35 | Fark / yorum |
|---|---:|---:|---|
| TP / FN / FP / TN | 77 / 23 / 6 / 94 | 90 / 10 / 22 / 78 | Eren daha duyarlı, çok daha fazla FP |
| Anomali recall | %77,0 | **%90,0** | Eren +13 puan |
| Recall Wilson %95 GA | %67,9–%84,2 | %82,6–%94,5 | — |
| Operasyonel normal FP | **%6,0** | %22,0 | Eren +16 puan kötüleşme |
| Operasyonel FP Wilson %95 GA | %2,8–%12,5 | %15,0–%31,1 | — |
| Operasyonel precision | **%92,77** | %80,36 | mevcut +12,41 puan |
| Specificity | **%94,0** | %78,0 | mevcut +16 puan |
| Dar normal FP | **%5,0** | %15,0 | mevcut daha iyi |
| Dispatch FP | **%5,0** | %15,0 | mevcut daha iyi |
| Anomali risk kalibrasyonu | %77,0 | %78,0 | hemen hemen aynı |
| Yeni-kural kategori eşleşmesi | %23,0 | %25,0 | yardımcı; ince sınıf etiketi yok |
| Accuracy / balanced accuracy | **%85,5** | %84,0 | mevcut +1,5 puan |
| F1 | %84,15 | **%84,91** | Eren +0,75 puan; TN'leri ödüllendirmez |
| MCC | **0,7205** | 0,6849 | mevcut +0,0355 |
| Medyan gecikme | 26,05 sn | **13,55 sn** | Eren yaklaşık 1,92x hızlı |

Eren 90 olay tespit etmesine rağmen yalnız 78 anomalide risk en az `Yüksek` oldu.
Başka deyişle 12 anomali klibinde olay üretilmiş fakat operasyonel risk seviyesi
eşik altında kalmıştır.

## Eşlenik istatistik

Aynı klipler dosya adına göre birebir eşlendi.

- Anomali tespiti: Eren'in tek başına doğru bulduğu 16, mevcut modelin tek başına
  doğru bulduğu 3 klip vardır. İki yönlü exact McNemar `p=0,00443`.
- Normal operasyonel FP kaçınması: mevcut modelin tek başına doğru bıraktığı 18,
  Eren'in tek başına doğru bıraktığı 2 klip vardır. Exact McNemar `p=0,000402`.
- Tüm 200 klipte toplam doğruluk: mevcut tek-başına-doğru 21, Eren
  tek-başına-doğru 18; exact McNemar `p=0,749`. Genel doğru/yanlış farkı için kesin
  üstünlük kanıtı yoktur.
- 50.000 tekrar, tohum `20260828`, sınıf-korumalı eşlenik bootstrap ile
  `MCC(mevcut)-MCC(Eren)` %95 aralığı `[-0,0757, +0,1464]` oldu. Aralık sıfırı
  içerdiği için MCC nokta farkı tek başına kesin üstünlük değildir.
- Aynı bootstrapta `recall(mevcut)-recall(Eren)` aralığı `[-0,21, -0,05]`,
  `operasyonel_FP(mevcut)-operasyonel_FP(Eren)` aralığı `[-0,24, -0,08]` oldu.

Sonuç bir işletim noktası takasıdır: Eren açık biçimde recall-yanlı, mevcut v13n
ise precision/specificity-yanlıdır.

## Duman/alev FP denetimi

Eren normal kliplerin 5'inde duman/alev/toz/gaz ailesi iddiası üretti. Klip boyunca
eşit aralıklı 12 karelik görsel denetim yapıldı; kilitli metrikler sonradan
değiştirilmedi.

| Klip | Eren iddiası | Görsel denetim | Hüküm |
|---|---|---|---|
| `3xr0dRq2QfM_trim_0.mp4` | Siyah-gri duman, aktif yangın | Kirli/lekeli duvar-tavan ve kablo var; yayılan plume/alev yok | Açık duman/yangın halüsinasyonu |
| `ZKn7Ja4ojbY_clip0_trim_2.mp4` | Turuncu-kızıl alev/parlama | Kapalı makine içindeki sabit proses ışığı/sıcak parça görünümü; açık alev yok | Proses parıltısını yangına çevirme |
| `ZQVQZdOgDlQ_trim_1.mp4` | Alev, kıvılcım ve duman | Kırmızı/sarı hareketli makine parçası var; görünür plume/alev yok | Renk/hareketi yangına çevirme |
| `YW5XdwOgcnU_clip0_trim_5.mp4` | Beyaz/gri toz bulutu | Görünür beyaz plume gerçekten var | Gözlem dayanıklı; bunun olay olup olmadığı tesis kuralı/etiket sorunu |
| `vOySf5EIjRA_clip0_trim_7.mp4` | Yoğun beyaz/gri duman veya gaz | Makineden görünür beyaz/gri plume gerçekten çıkıyor | Gözlem dayanıklı; “gaz/acil yangın” yorumu kanıtsız olabilir |

Bu denetim iki önemli sonucu birlikte gösterir:

1. Eren promptundaki “gri/koyu alan = dumandır” ve “turuncu/sarı ışık = yangındır”
   eşlemeleri üç açık halüsinasyon üretiyor; bu biçimde birleştirilmemelidir.
2. İki `Normal` klipte plume gerçekten görünür. Veri etiketi bunları normal saydığı
   için kilitli benchmarkta FP'dir; ancak tesis kuralı “görünür proses dumanı/tozu da
   alarmdır” diyorsa bu iki etiket/politika yeniden ele alınmalıdır. Özellikle
   `YW5X...` klibini Eren bulurken mevcut model olay üretmedi; `vOy...trim_7` ise her
   iki modelde olaydır fakat mevcut modelin olay metni görsel plume ile ilişkili
   değildir.

Dolayısıyla `%22 FP` sayısı aynı etiket sözleşmesinde geçerli ve kıyaslanabilir olsa
da, “22'sinin tamamı saf görsel halüsinasyondur” denemez. Bu veri genel İSG gerçeğini
değil, mevcut `Normal/Anomali` sözleşmesine uyumu ölçer.

## Karar ve öneri

1. `origin/d-35` olduğu gibi merge edilmemeli. Ön kayıtlı MCC daha düşük; operasyonel
   FP ve dispatch FP üç katına çıkıyor.
2. Eren'in recall kazancı gerçektir ve yok sayılmamalıdır. Özellikle ani plume,
   parlama ve toplu kaçış adaylarını ikinci incelemeye gönderen **aday üretici**
   katman olarak değerlidir.
3. “Gri alan=duman”, “turuncu ışık=alev”, “aynı yöne hareket=yangın” doğrudan karar
   kuralları olmamalıdır. Bunlar yalnız hipotez üretmeli; karar için zamansal
   oluşum/yayılma, fiziksel kaynak, süreklilik ve karşı-olgusal negatif kontroller
   zorunlu olmalıdır.
4. `VISIBLE_PLUME`, `FIRE/COMBUSTION` ve `EMERGENCY` ayrı tipli gözlemler olmalıdır.
   Görünür proses tozu, otomatik olarak yangın veya acil sevk değildir.
5. Mevcut v13n'in structured fire/dust veto ve terminal abstain kapıları korunmalı;
   Eren'in duyarlılık promptu ancak bu kapıların önünde aday üretecek biçimde
   seçici taşınmalıdır.
6. Holdout kararı verilmeden önce iki görünür-plume normal klibi için tesis kuralı
   açıkça yazılmalı; etiket değişecekse iki kola da aynı anda, önceden kayıtlı biçimde
   uygulanmalıdır.

Bu rapor karşılaştırma içindir; Eren dalından mevcut dala merge veya push yapılmadı.
