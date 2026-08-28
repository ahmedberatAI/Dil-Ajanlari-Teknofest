# Project RISE dengeli endüstriyel duman benchmarkı — ön kayıt

Tarih: 2026-08-28  
Durum: Model sonucu görülmeden kilitlenmiştir.

## Veri ve neden seçildi

Ana kaynak CMU CREATE Lab'in **Project RISE / Deep Smoke Machine** veri setidir.
Repo sürümü `e796bf36988226b8bc657872bdc83c6cbad791cd`, metadata SHA256 değeri
`cc85ad6db07557ae4afacc4f12f443b6e68ae0d88e30869fcf031f4c7dc7ee18` olarak
sabitlenmiştir. Veri seti CC0, kaynak kod BSD-3-Clause lisanslıdır.

Bu kaynak projede daha önce kullanılmamıştır. Eski FireSense veya geliştirme
klipleriyle birleştirilmeyecek ve hiçbir örnek ayar geliştirmede kullanılmayacaktır.

SteelBench önce aday seçilmiş, ancak yayımlanan 50-klip örneğinde genel KKD uyumu,
kişi düzeyi KKD ve açık ihlal metinleri arasında çelişkiler görüldüğü için ana
ölçümden sonuç görülmeden çıkarılmıştır.

## Sonuçtan bağımsız sabit seçim

Resmî metadata üzerinde aşağıdaki filtre uygulanır:

- `camera_id = 0`
- `view_id = 0`
- dosya tarihi `2019-02-02`
- güçlü araştırmacı etiketi `label_state_admin = 23` ise duman var
- güçlü araştırmacı etiketi `label_state_admin = 16` ise duman yok
- filtreye uyan kayıtların tamamı alınır; rastgele örnekleme yapılmaz

Sabit filtre tam `28 duman + 28 dumansız = 56` video verir. Kamera, görüş, tesis ve
gün iki sınıfta aynıdır; model sahne veya kamera kimliğini kestirme yol olarak
kullanamaz. Klipler etiket taşımayan `clips/rise_<id>.mp4` adlarıyla tek dizinde
tutulur. Altın etiket yalnız manifest ve skorlayıcı tarafından okunur.

## Sabit model ve çalıştırma sözleşmesi

- Öğrenilmiş çıkarım yalnız `https://evren-llmapi.ssyz.org.tr/v1` özel API'sinde.
- Üç sabit rol birlikte kullanılır: algı `vlm`, olay/zaman `llm-large`, yapı ve
  özet `llm-fast`.
- Model aliasları değişmez; yerel öğrenilmiş model ve model indirme kapalıdır.
- Sıcaklık `0`; dört işçi; tek tam koşu.
- v13n zincirinin yedi opt-in kapısı açık tutulur; v13o KKD politika kapısı kodda
  kalır. Bu benchmark KKD değil, görsel endüstriyel duman varlığıdır; tesise özel
  kural etikete veya prompta eklenmez.
- Kilitli `data/eval_genelleme_holdout_v13` açılmaz ve okunmaz.

## Önceden belirlenen tahmin ve metrikler

Birincil ikili tahmin, tam üç-model çıktısındaki `events[].event + summary` metninde
`Smoke` sınıfının sıkı Türkçe eşleştiricisi ve onarılmış olumsuzlama kapısıdır.
“Duman gözlenmedi” pozitif sayılmaz. Altın etiket modele/prompta verilmez.

Birincil rapor:

1. TP, FN, FP, TN;
2. duman recall, precision, specificity ve duman FP;
3. F1, dengeli doğruluk ve MCC;
4. her oran için ham `k/n` ve Wilson %95 güven aralığı.

İkincil operasyonel rapor:

1. dumanlı klipte herhangi olay üretme oranı;
2. dumansız klipte herhangi olay/fonksiyon üretme oranı (`operational FP`);
3. dumansız klipte yüksek/kritik risk FP;
4. dumansız klipte gerçek fonksiyon çağrısı (`dispatch FP`);
5. kapsam, API/ayrıştırma hataları ve medyan gecikme.

Sonuçtan sonra eşleştirici, veri seçimi, prompt, bayrak veya eşik değiştirilip aynı
koşu “iyileştirilmiş sonuç” olarak tekrarlanmayacaktır. Hata analizi yapılabilir;
sonraki sürüm ölçümü yeni ve açıkça ayrılmış bir değerlendirme protokolü gerektirir.
