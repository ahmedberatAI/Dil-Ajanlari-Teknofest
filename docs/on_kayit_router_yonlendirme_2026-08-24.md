# ÖN-KAYIT — model tabanlı yönlendirme (router, D42)

**Koşumdan ÖNCE yazıldı. Hiçbir model çıktısına bakılmadı.**

## Neden bu koşum

Şartname (docs/sartname_metni_2026.txt s.206-211) aynen: *"sabit kurallara
dayalı basit bir pipeline yerine ... MODEL TABANLI KARAR MEKANİZMALARI içeren
bir mimari"*, ve *"statik, yalnızca kural tabanlı çözümler DÜŞÜK
PUANLANACAKTIR."* Bizde dispatch şu an if/else.

Yönlendirmeyi **gerektiren** kendi ölçümümüz: `llm-large` sayma sorusunda 50/50
karar üretiyor ama kişi/öznitelik sorusunda 47/50 "GÖRÜNMÜYOR" diyor; `vlm` tam
tersi. Yani soru tipine göre model seçmek zaten zorunlu — soru şu: bu seçimi
**bir model** yeterince iyi yapabiliyor mu?

## Ölçülecek şey

Girdi: operatör sorusu **veya** klip betimlemesi (metin).
Çıktı: `soru_tipi ∈ {sayma, kisi_oznitelik, durum, genel}`.
`hedef_alias` bundan **deterministik tabloyla** türer (aşağıda) → alias doğruluğu
soru_tipi doğruluğuyla **birebir aynı**, ayrı metrik değildir.

| soru_tipi | hedef alias | dayanak |
|---|---|---|
| sayma | `llm-large` | **ölçüldü** — forklift sayma MCC +0,725 |
| kisi_oznitelik | `vlm` | **ölçüldü** — yelek MCC +0,500; llm-large 47/50 "GÖRÜNMÜYOR" |
| durum | `vlm` | **ÖLÇÜLMEDİ** — kişi/öznitelik ile aynı gerekçe (görsel varlık) varsayıldı |
| genel | `llm-fast` | **ÖLÇÜLMEDİ** — dokümantasyon JSON/araç 1,000=1,000 |

Alt iki satır **varsayım**; bu koşum onları test etmez, yalnızca sınıflandırmayı
test eder. Rapora bu ayrım yazılacak.

## Kollar (4)

1. `kural` — regex if/else taban çizgisi (API çağrısı YOK). **Kontrol kolu.**
2. `router` — Qwen3-8B (`DILAJAN_MODEL_YONLENDIRME=router`)
3. `llm-fast` — Qwen3.6-35B-A3B
4. `llm-large` — Qwen3.5-122B-A10B

Dört kol da **aynı** sistem promptunu ve **aynı** kısıtlı kod çözmeyi
(`structured_outputs.choice`) kullanır (1. kol hariç — o model kullanmaz).

## Küntye (tekrar üretilebilirlik)

- T = **0,0** · max_tokens = **16** · `structured_outputs.choice` = 4 etiket
- **seed PLUMBED DEĞİL**: `VLMClient.chat()` seed parametresi almıyor. Bunun
  yerine belirlenimlilik **ampirik** ölçülür: router kolu tüm sette **3 kez**
  koşulur, birebir aynı olmayan madde sayısı raporlanır. (Kendi kaydımız: 13
  token çıktıda 20/20 aynı — burada çıktı ~1-6 token, yüksek kararlılık beklenir.)
- n = **36** (sınıf başına 9; 22 operatör sorusu + 14 klip betimlemesi)
- Etiketler: `benchmark/yonlendirme_seti.py` — bu dosya bu belgeden ÖNCE yazıldı
  ve koşumdan sonra DEĞİŞTİRİLMEYECEK.

### Önceden ilan edilen tartışmalı maddeler (post-hoc eleme YOK)

`S8` ("bu vardiyada kaç kez ihlal oldu" — sayım mı özet mi), `K9` (iki kişi,
biri baretli biri değil), `G5` ("olağandışı durum yok" — genel mi durum mu).
Sonuç bu 3 madde **dahil** ve **hariç** iki kez verilecek.

## Eşikler (sonuçlara bakmadan, mekanik uygulanacak)

| karar | koşul |
|---|---|
| **ROUTER'I BENİMSE** | router doğruluk ≥ %80 **ve** (llm-large − router) ≤ 10 pp **ve** router medyan gecikme < llm-large medyan gecikme |
| **RET** | router doğruluk < %70 **veya** (llm-large − router) > 15 pp |
| **BELİRSİZ** | arada → router kalır ama `kural` ile **anlaşmazlıkta** llm-fast'e tırmandırılır |

Ek koşul — **kontrol kolu kapısı**: `kural` kolu router'a ≤ 5 pp yaklaşırsa,
"model tabanlı yönlendirme daha DOĞRU" iddiası **kurulmamış** sayılır ve rapora
böyle yazılır. Şartname uyumu ayrı bir gerekçedir; doğruluk gerekçesi değildir.

## Maliyet analizi (önceden tanımlı)

Karşılaştırma: `router çağrısı + hedef çağrısı` vs `doğrudan llm-large çağrısı`.
Yönlendirme ek yükü, aşağı akıştaki **video** çağrısının kendi kayıtlı
maliyetine oranlanacak (D41 ölçümü: ilk yükleme 17,8 s; sonraki sorular
4,7 → 4,1 → 3,7 s). Yeni video çağrısı YAPILMAZ — servis paylaşımlı.

## Başarısızlık modu (önceden tanımlı)

Yanlış yönlendirmenin **maliyeti simetrik değil**:
- kisi_oznitelik → `llm-large`: model "GÖRÜNMÜYOR" der → İSG'de **KAÇIRMA (FN)**. En pahalı hata.
- sayma → `vlm`: sayı bozulur → yanlış şiddet. Orta.
- genel → `vlm`/`llm-large`: yalnızca **maliyet** artar, doğruluk düşmez. Ucuz.

Geri çekilme (K3 fail-open uyumlu), `dilajan/yonlendirici.py` içinde kodlandı:
1. Çağrı/ağ hatası → `genel` + `settings.model_name`, gerekçe kayda geçer, akış **durmaz**.
2. Kısıtlı çözme tutmazsa → `kural_ile()` taban çizgisi.
3. Hedef "GÖRÜNMÜYOR" derse → `ikincil_alias()` ile **tek** yeniden deneme.

## Koşum

```
python benchmark/yonlendirme_prob.py --tekrar 3
```
