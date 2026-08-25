# Veri kusuru — kök teşhis ve kök düzeltme

Tarih: **2026-08-25** · Denetim: `benchmark/veri_kusuru_denetimi.py`
Düzeltme: `benchmark/kanonik_etiket.py` + `benchmark/kanonik_puanla.py`
Koruma: `tests/test_veri_butunlugu.py`

## 1. Kusur nasıl bulundu

691 kliplik koşum başlarken değerlendirme şu satırı yazdı:

    [DEDUP] 33 mukerrer klip elendi (691 -> 658 benzersiz)
       - Unauthorized_Intervention/1_te1.mp4  ==  Safe_Walkway_Violation/0_te8.mp4

Yani aynı dosya iki farklı sınıfta duruyor. Tam denetim yapıldı.

## 2. Kusurun boyutu

```
691 dosya  →  658 benzersiz içerik.  32 mükerrer grup, 33 fazla kopya.

  aynı sınıf içinde tekrar        :  0     ← hiç yok
  FARKLI SINIF / aynı kova        : 28
  GÜVENLİ ↔ GÜVENSİZ çelişkisi    :  4
  eğitim/test ayrımı delinmiş     :  9 grup (aynı içerik hem _tr hem _te)
```

Çakışan sınıf çiftleri:

| çift | grup | not |
|---|---|---|
| class0 ↔ class1 | **27** | yaya ihlali + yetkisiz müdahale |
| class0 ↔ class4 | 3 | **güvensiz ↔ güvenli** |
| class1 ↔ class4 | 1 | **güvensiz ↔ güvenli** |
| class0 ↔ class5 | 1 | **güvensiz ↔ güvenli** |
| class1 ↔ class2 | 1 | |
| class4 ↔ class6 | 1 | |

## 3. Kök sebep — TAHMİN DEĞİL, görüntüye bakılarak

Dört "çelişki"nin karelerine bakıldı. Sahne: solda pres makineleri, ortada
sarı çizgi, sağda **yeşil boyalı yaya yolu**, aralarında gri beton koridor.

| # | gözlem | hüküm |
|---|---|---|
| C1 | hi-vis kişi gri koridorda yürüyüp sona doğru yeşile geçiyor | ihlal **gerçek** |
| C2 | kişi koridorun tamamını gri betonda yürüyor | ihlal **gerçek** |
| C3 | makinede oturan operatör **ve** üstte yürüyen ayrı bir kişi | iki etiket **farklı kişiler** hakkında |
| C4 | net değil | — |

**C3 kilit.** `class0` (yaya ihlali) ile `class5` (yetkili müdahale) birbiriyle
çelişmiyor — aynı karede farklı iki kişiyi anlatıyorlar. Aynı mantık 27
`class0↔class1` grubu için de geçerli.

> **Kaynak etiketler klip başına değil, DAVRANIŞ başına.** Aynı video birden
> çok davranış barındırabilir; kaynak set bunu her sınıfa bir kopya koyarak
> ifade etmiş.

## 4. Kök düzeltme

Hangi etiketin "doğru" olduğu tahmin **edilmedi**. Yer gerçeği çok-etiketli
modellendi:

1. **İçerik (sha256) başına ETİKET KÜMESİ.** 658 içerik: 626 tek etiket,
   31 çift etiket, 1 üç etiket.
2. **Kova kuralı:** kümede güvensiz etiket varsa içerik güvensizdir.
   → 488 güvensiz / 170 güvenli.
3. **Çift üyeliği:** içerik, çiftin güvensiz sınıfını taşıyorsa POZİTİF;
   yalnız güvenli sınıfını taşıyorsa NEGATİF; **ikisini de taşıyorsa o
   çiftten DIŞLANIR** (temiz negatif olamaz).
4. **Ayrım:** herhangi bir kopyası `_te` ise içerik **teste** gider —
   test kümesi kirlenmez. → 535 tr / 123 te.

`data/eval_kanonik` içerik başına tek dosya bırakır (temsilci seçimi
deterministik: güvensiz öncelikli, eşitlikte en küçük sınıf no). Diğer
etiketler kaybolmaz; puanlama `kanonik_etiket.json` üzerinden yapılır.

## 5. Düzeltmenin ölçülen etkisi

Aynı arşiv (`eval_20260825_165802`, 658 satır), iki farklı yer gerçeğiyle:

### 5.1 Çift metriği — SESSİZ bir eksik ölçüm bulundu

| kural | eski n | **kanonik n** | eski TP | **kanonik TP** | MCC |
|---|---|---|---|---|---|
| forklift | 86 | 86 | 52 | 52 | +0,795 |
| pano | 174 | 174 | 132 | 132 | +0,842 |
| **yetkisiz** | **117** | **146** | **66** | **91** | +0,680 → **+0,679** |
| yaya | 281 | 279 (3 dışlandı) | 177 | 175 | +0,094 |

Yetkisiz çifti **29 klip eksik ölçülüyordu.** Tekilleştirme o içerikleri
"yaya klibinin kopyası" diye atıyordu; oysa aynı içerik `class1` etiketini
de taşıyor ve yetkisiz çiftinin meşru pozitifi. MCC neredeyse aynı kaldı
(+0,680 → +0,679) — yani skor sağlam ama **örneklem eksikti**.

### 5.2 Saha kesinliği — artık tahmin değil, hash'ten kesin

| kural | ham | **çok-etiketli** | kazanç |
|---|---|---|---|
| forklift | 0,929 | 0,929 | +0,000 |
| pano | 0,584 | 0,584 | +0,000 |
| **yetkisiz** | **0,197** | **0,268** | **+0,071** |
| yaya | 0,372 | 0,372 | +0,000 |

Yelek kuralının 24 "çapraz" ateşlemesi aslında **doğruymuş**: o içerikler
`class1` etiketini de taşıyor. Bu düzeltme daha önce 12 klibe **gözle**
bakılarak tahmin ediliyordu (`docs/hata_analizi_2026-08-25.md` §1); artık
dosya hash'inden **kesin** olarak biliniyor.

**Sınır — dürüstçe:** bu düzeltme yalnızca kaynağın kendi kopyaladığı
kliplerdeki gizli etiketleri geri getirir. Yeleksiz kişi gösterip yalnızca
`class0` etiketli, kopyası olmayan bir klip hâlâ tek etiketli görünür.
Yani 0,268 bir **alt sınırdır**, tam düzeltme değil.

### 5.3 Aşırı uyum kontrolü — temiz

| kural | `_tr` | `_te` |
|---|---|---|
| forklift | +0,771 | +0,882 |
| pano | +0,851 | +0,728 |
| yetkisiz | +0,648 | +0,733 |
| yaya | +0,040 | +0,279 |

Hiçbir kuralda sistematik `_tr` > `_te` uçurumu yok. (Yaya `_te` değeri
n=57'de gürültülü.)

## 6. Geri gelmesi engellendi

`tests/test_veri_butunlugu.py` (12 kontrol) şunları doğrular:
kanonik kaydın tutarlılığı · kova kuralının tüm içeriklerde tutması ·
çelişkili içeriğin çiftten dışlanmış olması · test kümesinin kirlenmemiş
olması · değerlendirme kümelerinde mükerrer içerik bulunmaması ·
puanlayıcının kanonik kaydı gerçekten kullanması.

## 7. Bu kusur eski skorları geçersiz kılıyor mu?

**Hayır, ama iki niteleme gerekiyor:**

- `data/eval_defense` (197 klip) içinde **mükerrer içerik yok** — orada
  ölçülen üç skor bu kusurdan etkilenmedi.
- O sette **1 çelişkili içerik** var (yaya çiftinde). Yaya sınıfı zaten
  sevk edilmiyor.
- Yetkisiz çiftinin eksik ölçümü yalnızca **tam sette** ortaya çıktı;
  197 kliplik sette o klipler zaten yoktu.

Hiçbir eski skor silinmedi. Bu belge onların **yanına** yazılır.
