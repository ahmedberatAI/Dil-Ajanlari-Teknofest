# "Normal kliplerde %54 sevk" — ölçüldü, kural DEĞİŞTİRİLMİYOR

Tarih: **2026-08-25** · Arşiv: `benchmark/results/eval_20260825_114341.json`
İlgili: `docs/on_kayit_yumusak_esik_2026-08-25.md` (S2 kolu)

## 1. Soru

Gözlem düzlemi açıldığında normal kliplerde sevk oranı 7/98'den 53/98'e
(%54,1) çıktı ve "Orta" risk seviyesi hiç görünmez oldu. Kademeli önem
derecesi (S2) bunu düzeltir mi?

**Cevap: hayır, çünkü düzeltilecek bir şey yok.** Aşağıdaki üç ölçüm bunu
gösteriyor. Kol **koşulmadı**; koşumdan önce yapılan ölçümler mekanizmanın
yanlış olduğunu ortaya koydu.

## 2. Ölçüm 1 — "%54 sevk" iki farklı şeyi TEK KOVAYA koyuyor

| | NORMAL (n=98) | ANOMALİ (n=99) |
|---|---|---|
| hiç çağrı yok | **%45,9** (45) | %16,2 (16) |
| **yalnız bildir-kaydet** | %45,9 (45) | %65,7 (65) |
| **acil müdahale içeren** | **%8,2** (8) | **%18,2** (18) |

"Bildir-kaydet" = `guvenlik_ekibi_uyar` · `yonetici_bilgilendir` ·
`olay_kaydi_olustur`.
"Acil" = `acil_durdurma_tetikle` · `alan_guvenligini_sagla` ·
`saglik_ekibi_yonlendir`.

Yani normal kliplerde **acil müdahale oranı %8,2**, anomalide %18,2 —
**2,2 kat** ayrım. Basamaklandırma zaten çalışıyor.

Yalnız yelek olayı olan **26 normal klipte acil durdurma sayısı: 0/26.**
Üçü de bildir-kaydet: 26/26. KKD eksikliği için orantılı olan tam budur.

## 3. Ölçüm 2 — bildirimler OLGUSAL OLARAK DOĞRU

`docs/hata_analizi_2026-08-25.md` §1: yelek kuralının kendi sınıfı dışındaki
ateşlemelerinden tohumlu 12 örneğe **gözle** bakıldı; **12/12'sinde makinenin
başında gerçekten yeleksiz bir kişi vardı** (Wilson alt sınırı 0,796).

Bu tesiste standart iş kıyafeti koyu lacivert tulum; yeşil reflektif yelek
seyrek. Değerlendirme seti tek etiketli olduğu için o klipler "pano kapağı
kapalı" ya da "güvenli yaya yolu" diye işaretli — **başka bir tehlike
eksenini** işaretliyorlar, "hiç tehlike yok" demiyorlar.

Yani %54 bir **yanlış alarm oranı değil**, tek-etiketli yer gerçeğinin
artefaktı.

## 4. Ölçüm 3 — önerilen mekanizmalar YANLIŞ

### S2b — güvene bağlı kademelendirme (`p_maks < 0,60 → ORTA`)

| slot | ateşleme | `p_maks < 0,60` olan |
|---|---|---|
| `makine_basinda_yelek` | 165 | **0 (%0,0)** |
| `catal_kasa_sayisi` | 26 | 9 (%34,6) |
| `pano_koyuluk_0_10` | 66 | **66 (%100,0)** |

İki yönden birden yanlış: yelek slotunda model **hiçbir zaman** düşük güvenli
değil (kural hiç tetiklenmez), pano slotunda ise **her zaman** düşük güvenli —
yani kural **+0,960'lık kuralın bütün olaylarını** düşürürdü. Ölü mekanizma.

### S2a — kural bazlı önem derecesi (yelek YÜKSEK → ORTA)

`risk_recall_bias` tarafından nötralize edilir: tehlike kategorisinde
**ORTA ve üstü** bir olay varsa risk zaten YÜKSEK'e çekiliyor
(`graph.py:1664`). ORTA yapmak hiçbir şey değiştirmez; DÜŞÜK yapmak ise
gerçek bir KKD ihlalini görünmez kılar.

## 5. Sonuç

**Kural değiştirilmiyor.** Sevk basamaklandırması ölçüldü ve orantılı çıktı:
normal kliplerde acil müdahale %8,2, anomalide %18,2; yalnız-yelek normal
kliplerinde acil durdurma sıfır.

Operatör tarafındaki gerçek ihtiyaç — *"bu uyarı neden geldi?"* — bir metrik
sorunu değil **sunum** sorunuydu ve arayüzdeki İSG ölçüm paneliyle karşılandı:
ölçülen değer, kural eşiği ve hüküm yan yana gösteriliyor.

## 6. Jüriye verilecek cevap

> "Normal kliplerin %54'ünde alarm üretiyorsunuz, bu çok yüksek değil mi?"

Üç adımda:
1. O %54'ün **%45,9'u bildir-kaydet**, yalnızca **%8,2'si acil müdahale**
   içeriyor — anomalide bu oran %18,2.
2. Bildirimler **olgusal olarak doğru**: gözle doğrulanan 12/12 klipte
   gerçekten yeleksiz kişi var.
3. "Normal" etiketi *o sınıfın* tehlikesinin yokluğunu belirtiyor,
   tehlikesizliği değil. Ölçülebilir eksende yelek kuralının kesinliği
   **0,975** [alt sınır 0,796].
