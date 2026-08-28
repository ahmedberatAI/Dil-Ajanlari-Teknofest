# On kayit — InspecSafe-V1 hiyerarsik guvenlik karari

Tarih: 2026-08-28

## Amac ve kapsam

Yalniz InspecSafe-V1 kullanilir. Sabit ozel API ve model eslemeleri degismez:

- `algi = vlm`
- `olay = llm-large`
- `yapi = llm-fast`
- `ozet = llm-fast`

Yerel ogrenilmis cikarim ve model indirme yasaktir. InspecSafe-V1'in 1.250
ornekli resmi testindeki eski tahminler gelistirme icin okunmaz; ilk tam kosu
(`6affe2e2f1d92cd8`) degistirilemez taban olarak saklanir. Yeni mimari resmi
testte yeniden kosulursa bu, test ozetindeki recall kusuru bilindikten sonra
yapilan **post-hoc teyit** sayilir; yeni mimarinin tarafsiz kapisi train icinde
ayrilan holdout'tur.

## Kaynak kilitleri

- Dataset revizyonu: `f3cb7d3e7827c1afc1c5bfd0524257984bba46ab`
- Resmi kod revizyonu: `d2f66e0ada2edc4dc65c25213d37b00a4039910f`
- `train.tar.gz` boyutu: `17,886,855,594` bayt
- `train.tar.gz` SHA-256: `ef03b9eb2f9bd91b03f203a8e6cfcc3464cb0d9f0215349a80ad95281fa88cd6`
- Beklenen train: 3.763 kare; 3.014 normal, 749 anormal

Dosya/klasor adi, anotasyon, maske ve alt-kume bilgisi model mesajina girmez.
Her goruntu yalniz ayni govde adli `.txt` anotasyonuyla dogrulanir; eksik
sidecar icin klasordeki baska anotasyonu kullanma fallback'i yoktur.

### Model ciktisi oncesi veri-kunye bulgusu

Train arsivi acilip ilk `--validate-only` kosusu yapildiginda, herhangi bir
API/model ciktisi gorulmeden once tek bir yol/sidecar celiskisi bulundu:

- `coal_conveyor-Level01-SuspendedRail-002557-001.jpg` klasor/yol: Level I
- ayni govdeli resmi `.txt`: `standing water`, **Level 3**

InspecSafe'in resmi `model_confusion_matrix.py` ground truth'u yol adindan
degil ayni govdeli `.txt` dosyasinin son satirindan okur. Bu nedenle `.txt`
sidecar ground-truth otoritesidir; yol seviyesi yalniz denetim alanidir.
Celiski ornegi silinmez ve yolu Level I'e zorlanmaz; Level III olarak kullanilir,
`path_gold` ile birlikte manifeste acikca kaydedilir. Eksik veya tekil seviye
vermeyen sidecar yine fail-closed veri butunluk hatasidir. Bu kural model
ciktisi gorulmeden yazilmistir.

### Model ciktisi oncesi dengeli grup secimi duzeltmesi

Ilk veri-butunluk kosusu, `calibration/oil_gas_chemical` katmaninda 149
bagimsiz unsafe gruba karsilik 131 bagimsiz normal grup oldugunu gosterdi.
Butun unsafe gruplari zorunlu tutan ilk secici bu nedenle 1:1 dengeyi
kuramadi. Henuz hicbir API/model ciktisi gorulmeden secim kurali soyle
kilitlendi:

- Her faz ve alan icin hedef, `min(normal grup, unsafe grup)` olur.
- Iki taraf da bu hedefe deterministik hash sirasi ile indirilir.
- Unsafe taraf azaltilirsa o alanda bulunan her siddet seviyesinden en az bir
  grup korunur; kalan kota dogal seviye oranina en yakin dagitilir.
- Boylece her alan tam 1:1 normal/unsafe olur; dosya sirasi ve model ciktisi
  secimi etkileyemez.

## Onceden yazilan hipotez

Mevcut duz karar `LEVEL_ONE`, `LEVEL_TWO`, `LEVEL_THREE` ve
`NO_ABNORMALITY` arasinda tek argmax alir. Unsafe olasiligi uc ayri seviye
arasinda bolunurken normal tek secenek oldugu icin toplam unsafe kutlesi daha
yuksek olsa bile normal secilebilir.

### Kalibrasyon surerken kullanici tarafindan secilen yuksek-performans profili

Ilk 94 temiz tamamlanmis satirin ara fotografinda, ham `0.50` hiyerarsi
esigi duz kola gore 4-sinif accuracy'yi `%75.53 -> %82.98`, unsafe recall'i
`%58.82 -> %94.12` ve F1'i `%72.73 -> %92.75` cikardi; empirical precision
`%95.24 -> %91.43`, FPR ise `%1.67 -> %5.00` oldu. Bu ara gorunum tam set
sonucu degildir ve esik aramasi icin kullanilmaz; ancak kullanici hiyerarsik
mimarinin birincil gelistirme yonu olmasini acikca secti.

Tam calibration sonucu gorulmeden once iki ayri profil kilitlendi:

1. **Yuksek-performans profili (birincil):** coverage en az `%99`, test
   onculune gore unsafe precision en az `%80` ve normal FPR en fazla `%5`
   olan adaylar arasinda test-onculu unsafe F1 en yuksek aday; esitlikte
   test-onculu 4-sinif accuracy, unsafe recall ve daha az severity ek-cagrisi.
2. **Kati gerilemesizlik profili (ikincil):** asagida tanimli mevcut
   precision/recall/FPR ve her-alan kapilarinin tamami. Bu profil kalir fakat
   tek basina hiyerarsik mimariyi arastirma yonu olarak reddetmez.

Birincil profil calibration'da secildikten sonra esigi degistirilmeden
development ve holdout'ta sinanir. Level II/III ayrimi binary kazancindan ayri
bir hata alani olarak raporlanir.

### Calibration-gorunur hata kumesi ve sonraki EPV kolu

Kullanici istegiyle ilk 94 temiz satirin ara skoru acildiktan sonra bu satirlar
artik yalniz gelistirme verisidir. Ham `0.50` binary kolda 3 FP ve 2 FN vardir.
Uc FP'nin orijinal karesi insan tarafindan incelendi:

- islak/parlak metal zemin, yurume yuzeyinde sinirli bir su kutlesi olmadan
  `standing water` diye yorumlandi;
- pasli haznenin altindaki lens damlasi/bulaniklik, kaynaga bagli tutarli plume
  olmadan `steam/vapor` diye yorumlandi;
- boru altindaki golge/lekelenme, akis veya kaynak baglantisi olmadan `liquid
  puddle/leak` diye yorumlandi.

Bu bulgu hiyerarsiyi geri cevirmek icin degil, false-premise dogrulamasi icin
kullanilir. Mevcut calibration kosusunun promptu/kodu degismez. Sonraki aday
kol, siyah-kutu API'ye uygun Explicit Premise Verification desenidir:

1. `llm-fast`, notr gozlemden en fazla iki kapali tehlike-onculu kodu cikarir;
   goruntu veya ground truth almaz.
2. `vlm`, asil karede her onculu atomik `SUPPORTED / NOT_SUPPORTED /
   UNCERTAIN` olarak yeniden kontrol eder. Islaklik/parlama tek basina su
   birikintisi; lens lekesi/pas tek basina plume; golge/renk degisimi tek basina
   sizinti kaniti sayilmaz.
3. `llm-large`, ayni onculun resmi kural kapsaminda gercek bir safety factor
   olup olmadigini hedefli ve kapali secimle kontrol eder.
4. Yalniz mevcut duz kol `NO_ABNORMALITY` iken ve iki dogrulayici da cikarilan
   tum onculeri `NOT_SUPPORTED` bulursa hiyerarsik rescue veto edilir. Her hata,
   bos oncul veya `UNCERTAIN` fail-open'dir; mevcut unsafe karari korunur.

Bu kol yeni API cagrisi yapmadan once kod/test ve cagri butcesiyle ayrica
kilitlenecek; calibration disindaki development/holdout etiketi gorulmeyecek.

Aday A — saf hiyerarsi:

1. `vlm`: etiketsiz, tarafsiz gorunur kanit betimi.
2. `llm-large`: `UNSAFE` / `NORMAL` kisitli secimi ve ilk-token logprob
   dagilimi.
3. Yalniz unsafe esigi gecilirse `llm-large`: Level I / II / III siddet
   secimi.
4. `llm-fast`: kilitli karari JSON rapora cevirir. Gecersiz JSON'da karar
   degistirmeyen deterministik fallback kullanilir.

Aday B — skip-connected hibrit:

- Duz karar unsafe ise binary skor yalniz `veto_threshold` altinda normale
  indirebilir; aksi halde duz seviye korunur.
- Duz karar normal/gecersiz ise binary skor yalniz `rescue_threshold` ustunde
  severity kolunu acar; aksi halde duz normal/gecersiz sonuc korunur.
- Bu kol mevcut dogrulari ara guven bolgesinde baypas ederek gereksiz karar
  degisimini azaltmayi amaclar.
- Yardimci binary veya severity cagrisi hata verirse gecerli duz karar aynen
  korunur; yardimci kol hatasi tek basina kapsami dusurmez.

Aday C — iki-kanitli uzlasi hibriti:

- Resmi promptla ayri `vlm` direct karari, yuksek-recall fakat tek basina
  yuksek-FP bir yardimci kanit olarak kullanilir. Bu gerekce resmi testin
  yalniz onceden gorulmus kol-ozetinden gelir; satir tahminleri okunmaz.
- Duz normal/gecersiz karar ancak direct VLM unsafe **ve** binary llm-large
  skoru rescue esigini gecerse severity koluyla kurtarilir.
- Duz unsafe karar ancak direct VLM normal **ve** binary skor veto esiginin
  altindaysa normale indirilir.
- Direct veya binary yardimci cagrisi bozulursa gecerli duz karar korunur.
  Boylece tek bir modelin halusinasyonu karari degistiremez.

Model adlari degismez; yalniz kullanim mimarisi degisir.

## Train icindeki veri bolmeleri

Sizintiyi azaltmak icin ayni inspection-point klasorundeki kareler ve bayt
ozdes goruntuler union-find ile tek grup yapilir. Gruplar
`sha256("inspecsafe-v1-hier-v1|" + group_id)` ile su bantlara atanir:

- calibration: `[0.00, 0.50)`
- development: `[0.50, 0.75)`
- holdout: `[0.75, 1.00]`

Her bolmede butun anormal inspection gruplari kullanilir. Her bes sektorun
kendi anormal grup sayisi kadar normal grup o sektor icinden deterministik
sirayla secilir; boylece her sektor 1:1 dengeli ve hem recall hem FPR icin
olculebilir kalir. Her inspection/duplikat bileseninden metrikte
yalniz bir kare temsilci tutulur; komsu kare veya ayni piksel iki kez agirlik
kazanmaz. Precision, testin yayimlanmis unsafe onculu ile yeniden
agirliklandirilir (`251/1250`); recall ve FPR sinif-kosullu oldugu icin dogrudan
hesaplanir. Dort-sinif accuracy resmi test etiket onculeriyle yeniden
agirliklandirilir.

## Esik secimi

Saf binary unsafe esigi, skor gorulmeden sabitlenen
`0.01, 0.02, ..., 0.99` izgara uzerindedir. Hibrit kol icin veto izgara
`0.01..0.50`, rescue izgara `0.50..0.99` olarak sabittir. Ayni 2.500 esik
cifti hem binary-only hibrit hem iki-kanitli uzlasi hibriti icin denenerek
toplam `99 + 2.500 + 2.500 = 5.099` onceden tanimli aday olusur. Calibration'da su
kosullarin tamamini saglayan adaylar arasindan oncelikle prior-adjusted unsafe
F1, sonra agirlikli dort-sinif accuracy, sonra daha az severity cagrisi, sonra
daha basit mimari secilir:

- unsafe precision tabandan dusmez,
- unsafe recall tabandan dusmez,
- normal FPR tabandan yukselmez,
- dort-sinif agirlikli accuracy tabandan dusmez,
- Level I recall tabandan dusmez,
- en kotu alan unsafe recall'i tabandan dusmez,
- en kotu alan normal FPR'i tabandan yukselmez,
- her alanin unsafe recall'i tabandan dusmez,
- her alanin normal FPR'i tabandan yukselmez,
- tahmin kapsami en az %99'dur,
- precision, recall, FPR veya agirlikli accuracy'den en az biri kati iyilesir.

Uygun esik yoksa aday reddedilir ve development/holdout acilmaz.

## Sirali kapilar

1. Calibration yalniz esigi secer.
2. Development ayni gerilemesizlik kosullarinin tamamini gecmelidir. Kalirsa
   holdout acilmaz; yeni hipotez yalniz calibration uzerinde gelistirilir.
3. Kod, prompt, esik, split manifest SHA'lari, ozel API adresi ve dort rolun
   model alias sozlesmesi kilitlenir; herhangi biri degisirse kosum reddedilir.
   Olusan calibration kilidi ve development gecis onayi yerinde yeniden
   yazilamaz.
4. Train-holdout bir kez kosulur ve ayni kapilar uygulanir.
5. Holdout gecer ise tam uc-model formatter/fallback smoke testi yapilir.
6. Bundan sonra resmi testte tek post-hoc teyit kosusu yapilabilir; sonuc ne
   olursa olsun raporlanir ve ayar tekrar degistirilmez.

Tum API/ayristirma hatalari yanlis sayilir. Ara skorla prompt, esik veya ornek
secimi degistirilmez.

## Sizinti gunlugu

- 2026-08-28: Eski sonuc semasini formatter smoke araci icin denetleyen bir
  yerel komut, mimari ve esik izgarasi yazildiktan sonra resmi testten ilk
  satirin ham kaydini istemeden ekrana basti. Bu satira dayanarak inference
  runner'i, prompt, aday mimari veya esik izgarasi degistirilmeyecektir. Resmi
  test zaten yalniz post-hoc teyittir; tarafsiz karar kapisi train icindeki
  dokunulmamis holdout olmaya devam eder.
