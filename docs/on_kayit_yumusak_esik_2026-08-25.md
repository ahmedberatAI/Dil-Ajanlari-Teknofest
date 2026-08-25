# ÖN KAYIT — yumuşak eşik (kısıtlı çözme dağılımı)

Tarih: **2026-08-25**, koşumdan **ÖNCE** yazıldı. Dal: `d34-isg-veri-kkd`.
Sonucu gördükten sonra bu belgedeki hiçbir eşik değiştirilmeyecek (§7).

## 0. Bulgu (bu ön kaydı doğuran)

vLLM'in kısıtlı çözmesi (`structured_outputs.choice`) ile `logprobs`
**birlikte çalışıyor**. Yanıt gövdesinde yasak tokenlar `-9999.0` ile
maskelenir, izinli seçenekler gerçek logprob taşır. Yani **tek ileri
geçişten, ek çağrı ve ek gecikme olmadan**, izinli cevap kümesi üzerinde
tam bir olasılık dağılımı okunabiliyor.

Gerçek klipte ölçüldü (`3_te1.mp4`, forklift ihlali):

    catal_kasa_sayisi -> '3'   P(3)=0,622  P(4)=0,378
                               P(kasa >= 3) = 1,000

Kural `argmax >= 3` diye soruyor ve %62 güvenle karar veriyor. Oysa
**eşik üstündeki kütle %100**. Sert kural, kendi sorusunun cevabını
elindeki bilgiden daha az güvenle veriyor.

### §8 ile karıştırılmamalı
Reddedilen "self-consistency N=3", **aynı girdiyi N kez sorup oylamaktı**;
model deterministik olduğu için örnekler özdeş çıkıyordu ve bilgi
eklemiyordu. Burada **ek örnek yok**: zaten yapılan tek geçişin kendi
dağılımı okunuyor. Farklı mekanizma.

### Enstrümantasyon ölçümü bozmuyor
`logprobs` açık/kapalı 2 klip × 4 slot = **8/8 birebir aynı cevap**.
Belirsiz kütle (çok-tokenlı ön ek çakışması) tüm ölçümlerde **0,0000**.

## 1. Ölçüm tasarımı — tek koşum, çok kol, EŞLEŞMİŞ

`slot_guven=1` ile **tek** 197 kliplik koşum yapılacak; her slotun dağılımı
karar izine yazılacak. Sonra tüm kollar **aynı arşiv üzerinden, aynı ileri
geçişlerle** yeniden puanlanacak. Yeni API çağrısı yok.

Bunun iki sonucu var:
- Kollar **eşleşmiş** karşılaştırılabilir (aynı klipler, aynı gözlemler)
  → McNemar uygulanabilir, bağımsız örneklemden güçlü.
- Kollar arası fark **modelden değil yalnızca karar kuralından** gelir.

Künyeye `slot_guven` eklendi; enstrümanlı koşum sevk arşivinin ara-kayıt
dosyasını **paylaşmayacak**.

## 2. Kollar ve KABUL ÖLÇÜTLERİ

Referans (sevk edilen, 197 klip):
`pano +0,960` · `forklift +0,881` · `yetkisiz +0,689` ·
`isg_match 0,646 / 0,865`

### S1 — yumuşak eşik: `P(değer ≥ T) ≥ p*` yerine `argmax ≥ T`
- **p\* = 0,50 ÖNCEDEN SABİT.** Ayarlanmayacak. Gerekçe: kütle çoğunluğu
  ilkeseldir; 0,50 dışında bir değer seçmek, bu veride eşik aramak olurdu
  ve 9 kolluk yaya-yolu deneyiminden sonra bu **çoklu karşılaştırma**
  problemidir.
- Bir p\* taraması AYRICA raporlanacak ama **yalnızca betimleyici** olarak
  etiketlenecek; karar ölçütü değil.
- **KABUL:** üç çiftin hiçbirinde MCC düşmeyecek **ve** en az birinde
  ≥ +0,03 artacak. Aksi hâlde **RET** (sevk edilen sert kural kalır).

### S2 — güvene bağlı kademeli önem derecesi (F3)
`p_maks < 0,60` → önem derecesi **YÜKSEK yerine ORTA**.
- Bu kol **MCC'yi tanım gereği değiştiremez** (MCC ateşleme/ateşlememe
  üzerinden hesaplanır, önem derecesi üzerinden değil). Bu, kolun
  ölçütünün MCC olamayacağı anlamına gelir.
- **KABUL:** normal kliplerde sevk oranı 0,59'dan **≤ 0,40**'a inecek
  **ve** üç çiftin MCC'si **birebir değişmeyecek** (değişirse kolda
  istenmeyen bir yan etki var demektir → RET).

### S3 — yumuşak ön koşul kapısı (F2A)
Yelek kuralının ön koşulu `argmax(kişi) ≥ 1` yerine `P(kişi ≥ 1) ≥ 0,50`.
- Hedef: A grubu 3 kaçırma (`1_te5`, `1_tr18`, `1_tr84` — geniş plan).
- **KABUL:** `Unauthorized_Intervention` MCC ≥ **+0,75** ve yanlış
  pozitif ≤ **4**. Aksi hâlde RET.

### S4 — yaya yolu, yumuşak eşikle yeniden açılış
Kapanış belgesindeki ölçüt **değiştirilmeden** devralınıyor:
kendi çiftinde MCC ≥ **+0,45** VE saha kesinliği ≥ **0,237**.
Ayrı koşum (slot açılınca kural ateşler, ana koşumu kirletir).

## 3. Önceden bilinen NEGATİF sonuç — kayda geçiriliyor

F2B (çok kişili sahne, `kişi=3 yelek=VAR`) **yumuşak eşikle çözülemez.**
`1_tr42` klibinde ölçüldü: `yelek=VAR` güveni **0,997**. Model emin ve
kendi baktığı kişi için haklı; sorun **hangi kişiye baktığı**. Bu bir
kalibrasyon değil **referans (grounding)** sorunudur.

Yani S1/S3 F2B'yi kurtarırsa bu **şüpheli** sayılmalı, başarı değil.

## 4. Ne olursa ne yapılacak

| sonuç | eylem |
|---|---|
| S1 KABUL | yumuşak eşik sevke alınır, sert kural yedek olarak kodda kalır |
| S1 RET | sert kural kalır; dağılım yalnızca S2 için kaydedilir |
| S2 KABUL | kademeli önem derecesi açılır |
| S3 KABUL | yumuşak kapı yalnızca yelek kuralında açılır |
| hepsi RET | enstrümantasyon KAPALI varsayılanla kodda kalır (K2), belge yazılır |

Hiçbir eski skor silinmeyecek; yeni sayılar eskinin **yanına** yazılacak.

---

## EK — 2026-08-25, koşum SÜRERKEN, sonuç GÖRÜLMEDEN yazıldı

**Yöntem açıklaması (ölçüt değişikliği DEĞİL).** S2'nin çevrimdışı
puanlanamayacağı fark edildi.

Sevk kararını (`triggered_functions`) deterministik bir eşleme vermiyor:
`act` düğümü olayları ve risk satırını bir LLM'e verip fonksiyonları
**seçtiriyor**. Dolayısıyla önem derecesini YÜKSEK→ORTA çekmek sevk oranını
ancak LLM'in yargısı üzerinden değiştirir. Bu, arşivden yeniden puanlanamaz.

**Sonuç:** S1 ve S3 tek enstrümanlı koşumdan eşleşmiş olarak ölçülür.
**S2 kendi koşumunu gerektirir** ve ancak S1/S3 sonuçlandıktan sonra,
zaman kalırsa yapılır. S2'nin §2'de yazılı kabul ölçütü **aynen** geçerlidir
(sevk oranı ≤ 0,40 **ve** üç çiftin MCC'si birebir değişmeyecek).

Bu ek, ölçütü değiştirmiyor; yalnızca hangi kolun hangi koşumdan
ölçüleceğini kayda geçiriyor.

**Ayrıca ölçüldü (F2B altyapı fizibilitesi, karar değil):** yerel CPU'da
kişi tespiti çalışıyor — `yerel_cihaz()` "cpu" dönüyor (GPU yasağı sağlam),
YOLO11n kare başına **1,16 sn**, F2B kaçırma klibi `1_tr42`'de **6 kişi**
bulundu. Kişi-başına sorgu 6 ek VLM çağrısı demek; bu kol ancak araştırma
bulguları geldikten sonra ön kayıtla açılacak.
