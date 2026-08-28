# Eren d-35 / mevcut v13n geliştirme karşılaştırması — ön kayıt

Tarih: 2026-08-28 (Europe/Istanbul)

## Amaç ve kapsam

Bu koşu, `origin/d-35` dalındaki Eren Kayacılar mimarisini mevcut v13n adayımızla
aynı **v13 geliştirme** kümesinde karşılaştırır. Bu bir bağımsız holdout sonucu
değildir: mevcut mimari bu geliştirme kümesi üzerinde iteratif olarak geliştirildiği
için sonuç yalnız geliştirme/teşhis karşılaştırması olarak raporlanacaktır.
`data/eval_genelleme_holdout_v13` bu karşılaştırmada açılmayacak ve çalıştırılmayacaktır.

## Kilitlenen kollar ve girdiler

- Eren kolu: `origin/d-35`, commit
  `86b0f0103e8540b9f6b2f8256e3634dc187f5bec`
  (`fix(perceive): DUMAN/PANİK tespit halüsinasyonunu önle — 4 katman güçlendirme`).
- Mevcut kol: arşivlenmiş v13n sonucu
  `benchmark/results/eval_20260828_012132.json`.
  - Pipeline kimliği: `2026-08-28-isg-evidence-v13n-thermal-dust-terminal-abstain`
  - Sonuç SHA-256:
    `8e82acf5e0ce74f3f6fb0c12b81cf3c0947013b080cf237328f6d74ed68bc6af`
  - Bu sonuç kirli çalışma ağacındaki deneysel v13n koduyla üretildi; daha sonra
    eklenen v13o KKD politika kapısı bu arşivlenmiş koşunun parçası değildir.
- Veri: `data/eval_genelleme_v13_dev`
  - 100 `Anomali/Hazard` + 100 `Normal/Normal`, toplam 200 benzersiz klip.
  - Sıralı `SHA256  göreli-yol\n` listesinin SHA-256 parmak izi:
    `ab0c22d9b77ebb355f213e14fad2694ad48ee7e5d764b26bf5960991ba5252de`
  - Toplam bayt: 222,479,914.

## Sabit çıkarım sözleşmesi

- Tek uç: `https://evren-llmapi.ssyz.org.tr/v1`
- İzin verilen öğrenilmiş model takma adları: `vlm`, `llm-large`, `llm-fast`
- Ana model: `llm-large`
- Görsel algı rolü: `vlm`
- Yapısal rol: `llm-fast`
- Özet rolü yapılandırması: `llm-fast`
- Sıcaklık: `0.0`
- Yerel öğrenilmiş model, yerel nesne/pose dedektörü ve model indirme: kapalı.
  Eren dalındaki ayrı `verify_pose_falls` yolu da açıkça kapalıdır.
- Kareleme: 2 FPS, segment başına en çok 12 kare, azami kenar 768
- Aynı özel API anahtarı, aynı değerlendirme betiği anlamı ve 4 işçi kullanılacak.

Eren dalında görev yönlendirme kodu v13n'den daha eskidir. Bu yüzden yapılandırmada
aynı üç model takma adı sabit kalsa da dalın kendi kodu bazı aşamaları farklı modele
yönlendirebilir veya bir takma adı kullanmayabilir. Bu fark **mimari fark** olarak
raporlanacak; Eren dalına v13n yönlendirme kodu geri taşınmayacaktır.

## Önceden kilitlenen metrikler

Birincil metrik, operasyonel ikili karmaşıklık matrisinden hesaplanan MCC'dir:

- TP: anomali klibinde en az bir olay.
- FN: anomali klibinde olay yok.
- FP: normal klipte en az bir olay **veya** en az bir operasyonel fonksiyon tetiklemesi.
- TN: normal klipte olay ve fonksiyon tetiklemesi yok.

İkincil metrikler:

1. Anomali recall (`TP / 100`).
2. Operasyonel FP (`FP / 100`, düşük daha iyi).
3. Operasyonel precision (`TP / (TP + FP)`).
4. Specificity (`TN / 100`).
5. Dar FP: normalde yüksek/kritik olay veya genel risk en az yüksek.
6. Dispatch FP: normalde operasyonel fonksiyon tetiklemesi.
7. Yeni-kural kategori eşleşmesi; üst etiket yalnız `Anomali` olduğu için yardımcı,
   ince sınıf doğruluğu olarak yorumlanmayacak.
8. Klip başına medyan gecikme.
9. Hata/eksik satır sayısı.

Aynı 200 klipteki doğru/yanlış kararlar için eşlenik hata tablosu ve iki yönlü exact
McNemar testi hesaplanacaktır. MCC farkı ayrıca klip çiftleri üzerinde sabit tohumlu
eşlenik bootstrap ile %95 aralıkla raporlanacaktır. İstatistiksel belirsizlik,
geliştirme kümesi sızıntısı sorununu ortadan kaldırmaz.

## Durdurma ve tekrar kuralları

- Eren dalı tek tam koşu yapacaktır; sonuç görüldükten sonra prompt/ayar değiştirilip
  aynı karşılaştırma yeniden koşturulmayacaktır.
- İlk başlatma, dalın varsayılan-açık `verify_pose_falls` yolunun yerel ağırlık
  indirmeye çalıştığı görülünce 14 klipte sözleşme ihlali nedeniyle kesildi. Üretilen
  ara kayıt ve ağırlık silindi; o satırlar ölçüme alınmaz. Tam koşu, önceden beyan
  edilen “yerel öğrenilmiş çıkarım yok” kuralını gerçekten uygulayan
  `DILAJAN_VERIFY_POSE_FALLS=0` ile sıfırdan yalnız bir kez başlatılacaktır.
- Yalnız altyapı hatası (API erişilememesi, süreç çökmesi, eksik sonuç dosyası) varsa
  ara kayıttan aynı koşu sürdürülebilir.
- Uç veya model sözleşmesi uyuşmazsa herhangi bir klip gönderilmeden koşu durdurulur.
- Eksik/başarısız klip varsa başarı gibi sayılmayacak; sayı açıkça raporlanacaktır.
- Sonuç ne olursa olsun Eren dalı mevcut dala otomatik merge edilmeyecektir.
