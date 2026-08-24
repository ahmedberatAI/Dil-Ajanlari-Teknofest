# Ölçümler tekrar üretilebilir mi? — kaynağı bulundu

Tarih: 2026-08-25

## Gözlem
Aynı yapılandırmayla iki koşum arasında çift bazlı MCC dalgalanıyordu:

| çift | koşum A | koşum B |
|---|---|---|
| forklift | +0,840 | +0,881 |
| yetkisiz | +0,689 | +0,608 |
| pano | +0,960 | +0,960 |

`temperature=0` olmasına rağmen. Kaynağı bulmak için üç katman ayrı ayrı test edildi.

## 1. Model deterministik mi? — EVET

Aynı video oturumunda her slot 3 kez soruldu (50 klip, 2 slot):

    kisi  slotu 3/3 aynı: 50/50
    yelek slotu 3/3 aynı: 50/50

Tek-atış üç tekrarın üçü de MCC **+0,645** verdi — birebir aynı karışıklık
matrisiyle. **Model, aynı baytlarda tamamen deterministik.**

Bu aynı zamanda **medyan/çoğunluk oylama kolunu reddetti**: örneklerin hepsi
özdeş olduğu için oylamanın kazanacağı hiçbir şey yok
(ön kayıt: `on_kayit_slot_oylama_2026-08-25.md`).

> §8 ayrımı: daha önce reddedilen şey "self-consistency N=3 **severity-hibrit**"ti
> — yargıyı oylatmak. Buradaki kol sayısal bir **ölçümün** medyanıydı; farklı
> mekanizma, ayrı ölçüldü, ayrıca reddedildi.

## 2. Kare çıkarımı deterministik mi? — EVET

Aynı klipten iki kez kare çıkarıldı: 3/3 klipte tüm kareler bayt bayt aynı.

## 3. Video kodlaması deterministik mi? — HAYIR

    ffmpeg varsayılan ayarlarla, aynı klip iki kez: 0/8 aynı

**Dalgalanmanın kaynağı budur.** İlginç ipucu: ROI kırpmalı (düşük çözünürlüklü)
kodlamalar zaten tekrar üretilebilir çıkıyordu — yani sorun x264'ün çözünürlüğe
göre seçtiği iş parçacığı sayısı.

## Çözüm

| kol | tekrar üretilebilir | süre/kodlama |
|---|---|---|
| mevcut | 0/8 | 0,76 s |
| `+bitexact` | kısmi | 0,76 s |
| **`-threads 1`** | **8/8** | 2,13 s |

`+bitexact` (metadata zaman damgalarını siler) kalıcı olarak eklendi — maliyeti
yok. `-threads 1` ise `DILAJAN_KODLAMA_KARARLI=1` ile açılır; **varsayılan
kapalıdır** çünkü kodlamayı ~3× yavaşlatır.

## Bunun anlamı

- Raporlanan tek bir MCC değeri **±0,05 belirsizlik** taşır ve bu dürüstçe
  belirtilmelidir.
- Bir ölçümün **birebir yeniden üretilmesi** gerektiğinde
  `DILAJAN_KODLAMA_KARARLI=1` ile koşulur ve sonuç bayt düzeyinde tekrarlanır.
- Belirsizliğin kaynağı **model değil kodlayıcıdır**; model katmanı
  ölçüldü ve tamamen deterministik çıktı.
