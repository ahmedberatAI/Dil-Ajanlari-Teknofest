# InspecSafe-V1 gercek test on kaydi — 2026-08-28

Bu belge, InspecSafe-V1 test kumesinde herhangi bir model ciktisi gorulmeden once
deney tasarimini kilitler. Test sonucuna bakilarak prompt, esik, sinif esleme,
ornek secimi veya hata politikasi degistirilmeyecektir. Sonuc iyi ya da kotu,
eksiksiz raporlanacaktir.

## Kapsam ve kaynak sabitleme

- Tek veri kumesi: `Tetrabot2026/InspecSafe-V1`.
- Hugging Face revizyonu: `f3cb7d3e7827c1afc1c5bfd0524257984bba46ab`.
- Resmi test arsivi: `test.tar.gz`, 5,748,799,871 bayt.
- Beklenen SHA-256 / Hugging Face `X-Linked-ETag`:
  `818086e696f970e036bf6a76758e4fb851fa26f771fe4eac56f8dc073b44358d`.
- Resmi kod revizyonu: `d2f66e0ada2edc4dc65c25213d37b00a4039910f`.
- Resmi uretim betigi SHA-256:
  `70ac21176a1d2051ea182cf04d5ca0b2b5636317367b62c82f0e743c27761448`.
- Resmi confusion-matrix/etiket ayristirma betigi SHA-256:
  `488f4e00aa9813936fcaa0a7dd3b80a04d3d348591003e13e749a6ba45a86a71`.
- Resmi prompt SHA-256:
  `f13a8837108f41e590d2bfddcc41ed55f9f880cea79d621b2cfd993e8ddceb9d`.
- Beklenen test buyuklugu: 1.250 goruntu; 999 normal, 251 anormal.
- Testteki tum uygun goruntuler dosya yoluna gore leksikografik sirada ve tam
  olarak kullanilir. Rastgele alt ornekleme ve elle eleme yoktur.
- Modele yalniz goruntuden deterministik uretilen medya baytlari ile sabit prompt
  gonderilir. Dosya adi, klasor adi, etiket metni, maske ve anotasyon modele
  gonderilmez.

Indirme sonrasi arsiv SHA-256'si, goruntu sayisi, benzersiz goruntu SHA-256
sayisi ve su tutarliliklar kosumdan once zorunlu olarak dogrulanir:

1. `Normal_data` altindaki her ornek `Level04`, `Anomaly_data` altindaki her
   ornek `Level01`-`Level03` olmalidir.
2. Dosya yolundan elde edilen seviye ile eslik eden resmi metin anotasyonundaki
   seviye celismemelidir.
3. Toplam sinif ve normal/anormal sayilari resmi dagilimla uyusmalidir.

Bir kontrol gecmezse model kosumu baslatilmaz.

## Cikarim kapisi ve sabit modeller

Tum ogrenilmis cikarim yalnizca
`https://evren-llmapi.ssyz.org.tr/v1` uzerinden yapilir. Yerel ogrenilmis
cikarim ve model indirme yasaktir. Kosum basinda asagidaki sozlesme dogrulanir:

- `algi = vlm`
- `olay = llm-large`
- `yapi = llm-fast`
- `ozet = llm-fast`

Model aliaslari degistirilmez. Sicaklik `0.0` ve her goruntu icin tek tekrar
kullanilir. Gecici API hatalari en fazla bes denemeyle ussu geri cekilerek
yeniden denenir; son hata strict metriklerde yanlis sayilir.

Ilk mekanik tasima sondasinda ozel API'nin sabit `vlm` aliasi, tek
`image_url` istegini model uretimi yapmadan HTTP 400 ve `max_images=0` ile
reddetti. Modelleri degistirmeden zorunlu video-yerli tasimaya uymak icin her
resim, orijinal uzamsal cozunurlukte iki ozdes kareden olusan MP4'e sarilir:
H.264/libx264, CRF=0, yuv420p, 2 fps; yalniz tek sayili kenarda en cok bir piksel
kirpilir. Bu donusum yeni zamansal bilgi eklemez. Ayni MP4 baytlari tum gorsel
asamalarda kullanilir. Bu zorunlu tasima sapmasi yayin karsilastirmasini
"yon-gosterici" yapar; nihai raporda saklanmayacaktir.

## Kilitli kollar

### D — resmi-protokole yakin dogrudan VLM kolu

`vlm`, tek resmi temsil eden iki ozdes kareli MP4'u resmi 2.802 baytlik
Ingilizce prompt ile gorur ve
resmi `[Image Description]` / `[Safety Level]` biciminde serbest metin uretir.
Sinif, yayinla paylasilan `model_confusion_matrix.py` ile ayni bicimde son
satirin son sozcugunden (`one`, `two`/`ii`/`2`, `three`, `observed`) ayristirilir.
Taninmayan veya `unrecognizable` cikti strict metrikte yanlis sayilir.

Resmi betik `temperature=0.1` kullanirken bu kosum tekrarlanabilirlik icin
`temperature=0.0` kullanir; bu sapma raporda acikca yazilacaktir. Resmi semantik
benzerlik olcumu BGE-M3 gerektirdigi ve model sozlesmesi disinda oldugu icin
calistirilmaz. Bu kol yalniz guvenlik seviyesi dogrulugu bakimindan yayimlanmis
VLM sonuclariyla protokole en yakin koldur.

Yayimlanan ek belge S2 normal ciktiyi `Level four` diye yazarken, yayin
sonuclarini puanlamak icin paylasilan calistirilabilir resmi kod hem promptta hem
confusion-matrix ayristiricisinda `no abnormalities observed` kullanir. Bu kosum
tekrar uretilebilir calistirilabilir kaynagi izler; bu kaynaklar-arasi tutarsizlik
nihai raporda karsilastirma siniri olarak korunur.

### S — mevcut uc modelli sistem kolu (birincil)

1. `vlm` ayni tek-kare MP4 temsilinden yalniz gorulebilir nesne, insan davranisi,
   cevre kosulu ve risk kanitlarini en cok 120 Ingilizce kelimeyle tarafsiz
   betimler; sinif veya gorunmeyen neden uydurmaz.
2. `llm-large` ayni tek-kare MP4 temsilini, tarafsiz betimi ve resmi dort seviyeli
   endustri kurallarini birlikte gorur. `structured_outputs.choice` ile tam
   olarak `LEVEL_ONE`, `LEVEL_TWO`, `LEVEL_THREE` veya `NO_ABNORMALITY` secer.
3. `llm-fast`, secilen kodu degistirme yetkisi olmadan, tarafsiz betim ve kilitli
   kodu sabit JSON semasina donusturur. Urettigi kod kilitli kodla ayni degilse
   veya JSON gecersizse uctan uca sistem kapsami basarisiz sayilir.

Birincil sistem skoru, `llm-fast` yapilandirma kapisi dahil uc asamanin da
basarili olmasini isteyen uctan uca strict skordur. `llm-large` semantik karar
skoru yalniz tani amacli ayri raporlanir. Boylece bicim arizasi ile semantik
karar hatasi birbirine gizlenmez ve "sistem" skoru gercekten uc modeli kapsar.

Kilitli kosucu ve prompt SHA-256 degerleri:

- `benchmark/inspecsafe_v1.py`:
  `c5882e3e625ea34ea51ab87e712291bde62d2324e80b6b3b92d6d53fd029eefa`
- tarafsiz gozlem sistem promptu:
  `769d4f8d23906567d43f7d40e066bf91acc5a3ff5fc673bda4eb0079b8f843aa`
- tarafsiz gozlem kullanici promptu:
  `049a9f2aa33bdda7a85401b5e7c260053c07794003bfd08ed01bfb5a82d9f19a`
- siniflama sistem promptu:
  `97d2427bad7923707be3eaa54818371318f1b639d68fc197fc22a1be7782c868`
- siniflama ek promptu:
  `bcfdb7ebb56053c4f28632f0c89b0deb75885cf497e03199d58f45493dc85ed9`
- yapilandirma sistem promptu:
  `c0db9be27da7c4189049040ae1734d3efded82992d94018dd3995766857e71f6`
- yapilandirma kullanici promptu:
  `058db2c9ef52ca48db30c0af056e2e9a6cae51f8078fdbc000fcf9728efd83f9`

Token tavanlari dogrudan/algilama/siniflama/yapilandirma icin sirasiyla
`768 / 256 / 8 / 320` olarak kilitlidir. Tam kosudan once yapilacak en cok dort
satirlik duman testi yalniz API ve bicim kapilarini dogrular; skor, tahmin ve
altin etiket ekrana yazilmaz. Bu satirlar ayni checkpoint jurnalinden tam kosuda
yeniden kullanilir ve duman testi sonucuna gore prompt degistirilmez.

## Etiketler ve metrikler

Altin dortlu etiket eslemesi:

- `Level01 -> LEVEL_ONE`
- `Level02 -> LEVEL_TWO`
- `Level03 -> LEVEL_THREE`
- `Level04 -> NO_ABNORMALITY`

Ikili esleme: Level01-Level03 `unsafe`, Level04 `normal`.

Birincil metrik, S kolunun uc modeli de kapsayan uctan uca 1.250 ornek
uzerindeki dort-sinif **strict accuracy** degeridir; API/bicim hatalari yanlis
sayilir. Ek olarak su metriklerin tamami raporlanir:

- dort-sinif confusion matrix, macro precision/recall/F1, balanced accuracy;
- ikili unsafe precision, recall, F1, specificity, false-positive rate, MCC ve
  balanced accuracy;
- Level01 recall, ciddi eksik-cagri orani (Level01'i Level03/Level04 ve
  Level02'yi Level04 deme), kapsama ve hata sayisi;
- endustri alani bazinda accuracy ve en kotu alan;
- accuracy, unsafe precision/recall ve FPR icin Wilson %95 guven araliklari;
- cagri ve satir gecikmesi p50/p95;
- D ve S arasinda eslesik dogruluk farki ve exact McNemar testi.

Sinif dengesizligi nedeniyle yalniz accuracy ile hukum verilmeyecektir. Uctan
uca S kolu D koluna karsi ancak dort-sinif accuracy, unsafe precision ve unsafe
recall azalmiyor, normal FPR artmiyor ve uctan uca kapsama en az %99 ise
gerilemesiz kabul edilir. Bu kural test sonucuna gore degistirilemez.

## Gecerlilik sinirlari

InspecSafe-V1 tek anahtar kareli robot denetim sahneleridir; video-zamansalligi,
olay baslangici veya insan tepkisi olcmez. Test dagilimi agir bicimde normaldir.
Bu nedenle sonuc, genel butun ISG dunyasi icin tek basina yeterlilik iddiasi
degildir. Yine de daha once kullanilmamis, insan etiketli ve farkli bes
endustri alanini kapsayan dis test olarak dagilim-disi kanit sayilacaktir.
