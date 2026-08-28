# Ön kayıt ve kullanım — duman dışı İSG non-regression kapısı

Tarih: **2026-08-28**  
Araç: `benchmark/isg_nonregression_gate.py`

## Amaç ve değişmez karar kuralı

Bu kapı, duman dışındaki İSG değişikliklerinin bir metriği yükseltirken precision
veya recall'ı sessizce düşürmesini engeller. Model/API çalıştırmaz; önceden
üretilmiş iki `eval_clips` JSON arşivini eşleştirilmiş olarak karşılaştırır.

Varsayılan kabul ölçütü sonuçlara bakılmadan sabitlenmiştir:

1. Veri manifesti, `eval_dir`, dedup bilgisi, örnek kimlikleri ve gerçek sınıflar
   birebir aynı olmalıdır.
2. Aday koşumun hata sayısı artmamalıdır.
3. Genel ve **her mevcut tehlike sınıfında** precision azalmamalıdır.
4. Genel ve **her mevcut tehlike sınıfında** recall azalmamalıdır.
5. Genel/sınıf FP, güvenli örneklerde operasyonel FP ve dispatch FP sayıları
   artmamalıdır.
6. Eksik sınıf/alan, farklı coverage/manifest veya precision/recall için sıfır
   payda `INSUFFICIENT`tır; hiçbir zaman `PASS` değildir.

Wilson %95 aralıkları yalnız raporda bağlam sağlar. Non-inferiority kararı ham
sayım ve kesirlerin tam çapraz çarpımıyla verilir; CI örtüşmesi bir regresyonu
kurtaramaz.

## Metriklerin kesin tanımı

- **Örnek kimliği:** sırayla `sample_id`, `id`, `path` alanlarından ilk dolu olan.
- **Gerçek sınıf:** kayıtlı `isg_sinif`; yoksa örnek yolundaki bilinen İSG sınıfı.
  Genel `Hazard/Normal` ceplerinde bunun boş olması geçerlidir; yalnız sınıf-bazlı
  kapı açılmaz.
- **Sınıf tahmini:** `events[].isg_kod` ile tipli olay kodları ve iki arşive aynı
  anda uygulanan `benchmark.labels` İSG metin eşleştiricisinin birleşimi.
- **Genel gerçek pozitif:** satırın `is_anomaly=true` olması.
- **Genel tahmin pozitif:** `n_events > 0` veya `triggered` dolu olması. Böylece
  doğru sınıf adı olmayan ama operatöre olay/alarm gösteren çıktı precision'dan
  gizlenmez.
- **Sınıf matrisi:** her tehlike sınıfı için tüm duman dışı örnekler üzerinde
  one-vs-rest TP/FP/FN/TN.
- **Precision:** `TP/(TP+FP)`; **recall:** `TP/(TP+FN)`.
- **Operasyonel FP:** güvenli örnekte `n_events > 0` **veya** `triggered` dolu.
- **Dispatch FP:** güvenli örnekte `triggered` dolu.
- **Hata:** `error/errors/hata/hatalar/_hata` alanı dolu ya da izde
  `__HATA__`/`OLCULEMEDI` bulunması.

Güvenli satırlardaki kayıtlı `isg_match` sınıf FP hesabında kullanılmaz: alan
satırın kendi güvenli sınıfına karşı üretildiği için normalde sürekli `false`tır
ve precision'ı yapay biçimde 1,0'a şişirir.

`kosum` künyelerinin eşit olması beklenmez; A/B değişkeni zaten orada farklıdır.
İki künye SHA-256 olarak raporlanır. Veri karşılaştırılabilirliği üst-seviye veri
manifest alanları ile örnek kimliği+gerçek etiketlerden türetilen manifest hash'i
üzerinden fail-closed doğrulanır.

## Duman kapsamı

Varsayılan olarak sınıf/kategori/yol adı `Smoke` veya `duman` olan örnekler metrik
hesabından çıkarılır; kimlik manifestinde yine görünür ve iki arşivde bulunmak
zorundadır. `Fire` otomatik dışlanmaz. Duman kolunu ayrıca ölçmek gerekirse açıkça
`--include-smoke` kullanılır; bu ön kaydın duman-dışı kabul iddiasıyla
karıştırılmaz. Bu bayrak yalnız dışlamayı kaldırır; arşiv duman örneğine bilinen
bir `isg_sinif` ve puanlanabilir sınıf çıktısı vermiyorsa kapı yine dürüstçe
`INSUFFICIENT` döner. Bu araç ayrı duman kabul kapısının yerine geçmez.

## Kullanım

```powershell
python benchmark/isg_nonregression_gate.py `
  benchmark/results/eval_BASELINE.json `
  benchmark/results/eval_CANDIDATE.json
```

Beklenen sınıfları ayrıca fail-closed zorlamak için:

```powershell
python benchmark/isg_nonregression_gate.py BASE.json ADAY.json `
  --require-class Safe_Walkway_Violation `
  --require-class Unauthorized_Intervention `
  --require-class Opened_Panel_Cover `
  --require-class Carrying_Overload_with_Forklift
```

Makine-okunur çıktı:

```powershell
python benchmark/isg_nonregression_gate.py BASE.json ADAY.json `
  --json --report-json benchmark/results/isg_nonregression_report.json
```

Çıkış kodları:

- `0`: `PASS`
- `1`: `FAIL` — ham sayımlarda en az bir gerçek regresyon
- `2`: `INSUFFICIENT` — karşılaştırma/coverage/payda yeterli değil

Kapı yalnız arşiv okur; video, `data/eval_genelleme_holdout_v13`, model ağırlığı,
yerel öğrenilmiş model veya özel API'ye erişmez. Holdout'un mühürlü kalması ayrıca
operasyonel süreçle korunmalıdır: bu araca holdout sonucu verilmeden önce aday
eşikler/devreler geliştirme setinde dondurulur.
