# ÖN KAYIT — saha kesinliğinin GÖZLE ölçümü

Tarih: **2026-08-25**, örnek çekilmeden ve karelere bakılmadan **ÖNCE**.

## 0. Neden

Saha kesinliği raporun en zayıf görünen sayısı: **pano 0,584 · yetkisiz 0,268**.
Ve bu sayıların **eksik saydığını biliyoruz**: kaynak set her klibe *tek*
davranış etiketi veriyor, oysa aynı karede birden çok tehlike olabiliyor.

Çok-etiketli düzeltme (`kanonik_etiket.json`) bunu kısmen onardı
(yetkisiz 0,197 → 0,268) ama **yalnızca kaynağın kendi kopyaladığı**
kliplerdeki gizli etiketleri geri getirebiliyor. Kopyası olmayan bir klip
hâlâ tek etiketli görünüyor. Yani 0,268 bir **alt sınır**.

Bu ön kayıt, alt sınırı **gerçek tahminle** değiştirmeyi amaçlıyor.

## 1. Yöntem — örnekleme ve hüküm ölçütü

**Örneklem:** her kural için, o kuralın ateşlediği ama klibin o sınıfın
etiketini **taşımadığı** kliplerden **tohumlu** (seed=7 — önceki 12 kliplik
ölçümle aynı tohum) **12 klip**. Klip başına **3 kare** (10., 45., 80.).

**Hüküm ölçütü — şimdi sabitleniyor:**

| kural | soru | EVET sayılır |
|---|---|---|
| yelek | Karelerin herhangi birinde, bir makinenin/panonun **başında veya bitişiğinde** duran, üzerinde reflektif yelek **olmayan** bir kişi var mı? | evet |
| pano | Karelerin herhangi birinde bir elektrik/kontrol panosu kapağı **açık veya çıkarılmış** mı? | evet |

Üç seçenek: **EVET / HAYIR / KARARSIZ**.
**KARARSIZ, DOĞRU SAYILMAZ** (muhafazakâr). Bu, tahmini aşağı çeker —
bilerek.

**Raporlama:** EVET oranı + **Wilson %95 alt sınırı**. Alt sınır, sunumda
verilecek sayıdır.

## 2. Bu ölçüm neyi KANITLAMAZ

- Örneklem **12 klip**; aralık geniş olacak. Nokta tahmini değil **alt sınır**
  raporlanacak.
- Hüküm **benim gözümle** verilecek. Bu, model çıktısından bağımsızdır
  (dairesel değil) ama **öznel**tir. Bu yüzden ölçüt yukarıda yazıldı ve
  kareler seçildikten sonra değiştirilmeyecek.
- Bulgu, çift bazlı MCC'leri **etkilemez** — onlar temiz etiketli çiftte
  ölçülüyor. Yalnızca saha kesinliğinin yorumunu düzeltir.

## 3. Ne olursa ne yazılacak

| sonuç | eylem |
|---|---|
| Wilson alt sınırı > ham değer | saha kesinliği **"ham X, düzeltilmiş ≥ Y"** biçiminde raporlanır |
| alt sınır ≈ ham değer | düzeltme yok; ham değer olduğu gibi kalır |
| KARARSIZ oranı > %40 | ölçüm **sonuçsuz** ilan edilir, sayı değiştirilmez |

Hiçbir mevcut sayı silinmeyecek; sonuç yanına yazılacak.

**KVKK:** çıkarılan kareler yalnızca yerel analiz içindir, yayımlanmaz.
