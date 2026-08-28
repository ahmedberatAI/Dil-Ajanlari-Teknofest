# Project RISE duman v3 optik ayrim on kaydi

Tarih: 2026-08-28 (Europe/Istanbul)

## Neden yeni gelistirme cebi

`dev` bolmesindeki v14-smoke-v2 kosusu kaynak-bagli endustriyel plum varligini
guvenilir bicimde buldu, fakat duman ile su buhari/plumu ayirmadi: 33/33 duman
yakalanirken 32/33 dumansiz klip de pozitif oldu. Resmi Project RISE belgesi
verinin yuksek/dusuk opasiteli duman, buhar ve buhar+duman ornekleri icerdigini
aciklar. Bu nedenle `dev` artik hata analizi verisidir ve v3 sonucunu olcmek icin
yeniden kullanilmayacaktir.

V3 icin model ciktisi gorulmeden secilen yeni bolme:

- kamera: `1` (Braddock)
- gorus: `0`
- gun: `2018-08-24`
- arastirmaci etiketi 16: 24 klip
- arastirmaci etiketi 23: ham 34 klipten zamana yayili sabit nicelikle 24 klip
- toplam: 48, dengeli ve ayni ortam
- secim: `(start_time,id)` sirasi uzerinden `round(i*(N-1)/(23))`
- secim SHA256: `28067603835b712b790ebeab1026e3db46265399795c334163fd61328ab121ae`

Kilitli nihai bolme `camera=2, view=0, 2018-06-12` bu asamada acilmayacaktir.

## Degismeyen model sozlesmesi

- gorsel/optik olcum: ozel API `vlm`
- zamansal olcum: ozel API `llm-large`
- yapisal ozet: mevcut akista ozel API `llm-fast`
- yerel ogrenilmis cikarim, model indirme ve model degisikligi: yasak

## V3 kanit kapisi

Kaynak-bagli plum varligi tek basina duman sayilmayacaktir. Plum desteklendikten
sonra iki ayri olcum yapilir:

1. `vlm` optik madde olcumu: kaynaktan itibaren kalici gri/kahverengi/koyu veya
   yari saydam opaklik; parlak beyaz yogusma bulutu; duman+buhar karisimi; yok;
   gorunmuyor/belirsiz.
2. `llm-large` zamansal dagilma olcumu: kaynaktan gorunur baslayip arka plani
   kalici bicimde orten/tasinarak suren aerosol; kaynaktan kisa bosluk sonra
   beyazlasip hizla incelen yogusma; ikisinin birlikte bulunmasi; yok;
   gorunmuyor/belirsiz.

Duman gozlemi ancak iki optik-zamansal olcumden ikisi de duman veya duman+buhar
destegi verirse uretilir. Tek destek, belirsiz cevap veya API hatasi fail-closed
olarak duman olayi uretmez. Kaynak/plum olcumu yalniz on kosuldur; duman oyu
degildir. Akut yangin ayri bir kapidir ve yalniz acik alev ya da hem optik hem
zamansal olarak hizla buyuyen koyu duman destegiyle acilir. Siradan endustriyel
duman gozlemi `Orta`, dispatch-disidir.

## Tek gelistirme kosusu ve kabul kurali

`dev_optical` uzerinde bir tam v3 kosusu yapilacaktir. V2'nin `dev` sonucu ile
farkli manifest oldugu icin metrikler dogrudan regresyon karsilastirmasi degil,
yeni mimarinin gecis kapisidir.

Asgari gecis kosullari:

- kapsama: %100 ve API/pipeline hatasi: 0
- smoke precision >= %70
- smoke recall >= %70
- operasyonel FP orani <= %30
- dispatch FP orani <= %5
- F1 >= 0.70

Kosullar gecilmezse kilitli holdout acilmaz. Sonuc goruldukten sonra bu bolmede
esik/etiket/prompt ayari yapilmaz; gerekirse yeni bir on kayit ve tamamen ayrik
gelistirme cebi gerekir.

Gerceklesen tek kosu: `deep_smoke_dev_optical_v15-smoke-v3-optical_20260828_031917.json`.
Sonuc dosyasi SHA256: `19cea18de2fd111e6764f007635e6f427ee38786945a671e022012ceec1dcd4b`.
Sonuc: TP=22, FN=2, FP=5, TN=19; precision=%81.48, recall=%91.67,
operasyonel FP=%20.83, dispatch FP=%0, F1=0.8627, kapsama=48/48 ve hata=0.
Butun on-kayit esikleri gecildi.

## Nihai non-regresyon

Kilitli holdout ancak v3 bu kapiyi gectikten ve genel ISG regresyon kapisi hazir
olduktan sonra bir kez acilir. Kabul icin eslesen manifestte aday precision ve
recall degerlerinin her biri tabandan dusmeyecek; FP ve dispatch FP artmayacak;
kapsama dusmeyecek ve hata sayisi artmayacaktir.

## Holdout oncesi kod dondurma karmalari

- `dilajan/duman_kanit.py`: `92f31881395d14c4b345701f266477f979bde3be504efff4cb49214dbfbd28af`
- `dilajan/agent/graph.py`: `9b17bccd57f87b769ca18855d76819fe5233fff273f6dfe11a65565187c2fd4e`
- `dilajan/gozlem.py`: `eb90076461195e06e9d825dfceac9075169dba704e887537659d7366dde902c7`
- `dilajan/isg_kural.py`: `4e23b179b5a2f437ce9b4507f108dda17c7bd58e5998feeb41d127b124f0740a`
- `benchmark/deep_smoke_eval.py`: `5a5fa5ce07fafa25c1806eb9c67bc5f806c471693e1e87bb4a2539230f4f8edf`
- `benchmark/eval_clips.py`: `f36228b4924ee6f8ddf3a4ae4c45ce8b7d261e02fc9b08a30bc27e201e64d31f`
