# ÖN KAYIT (EK) — Kol 2 / Kol 3 / Kol 4

Tarih: **2026-08-25**, ölçüm koşulmadan **ÖNCE**. Dal: `d34-isg-veri-kkd`
Ana ön kayıt: [`on_kayit_turkce_2026-08-25.md`](on_kayit_turkce_2026-08-25.md)

Ana ön kayıt T1/T2/T3'ü tanımlamıştı. Ölçüm düzeneği kurulurken **hakem
kanadı çöktü** (`judge_independent` Risk ekseni 5,00 sıfır varyans;
`dialogue_hard` doğallık 15/15 = 5,00 std 0) — tavan yapan bir metrikle
iyileşme gösterilemez. Bu yüzden hüküm **hakemsiz, deterministik sayaçlara**
bağlanıyor (`benchmark/tr_dil_kapisi.py`). Aşağıdaki üç kol o taban
ölçüldükten **sonra** tanımlandığı için ayrı ön kayıt gerekiyor.

## 0. Ölçülen taban (855 özet + 1385 olay, 3 arşiv)

| sayaç | taban |
|---|---|
| `acilis_Goruntu` | **0,889** |
| `meta_son_cumle` | 0,435 |
| `birebir_ayni_ozet_cifti` | **149** |
| `tekrar_4gram_orani` | 0,861 |
| `olcek_sizintisi_olay` | **0,606** |
| `kanonik_oran_pano` | **0,345** |
| `ascii_tr_cikti` | 0,488 |

## 1. Düzenek

**Eşleşmiş (paired).** Üçü de yalnızca **özet üretimini** etkiler; özet
metin-tabanlı tek bir çağrıdır. Video yeniden işlenmez — arşivdeki
olaylardan özet **yeniden üretilir**. Aynı klip, aynı olaylar, tek fark
prompt eki (Kol 2/4) veya olay metni (Kol 3).

- **Örneklem:** tohum **seed=7**, olay içeren kliplerden **60** klip.
- **Sıcaklık:** ölçümde **0,0** (sevk 0,2). Gerekçe: eşleşmiş tasarımda
  örnekleme gürültüsü kolun etkisini gizler. **Açıkça bildirilir**; kabul
  eden kol ayrıca sevk sıcaklığında (0,2) **20 kliplik doğrulama** alt
  örneklemiyle tekrar sayılır.
- **Kol 3 olay metni:** eski şablonlar arşivde **birebir** duruyor
  (190 forklift · 648 pano · 594 yaya). Regex ile yeni şablona çevrilir;
  çevrimin **tam kapsandığı** (dönüşmemiş kalıntı = 0) koşumdan önce
  doğrulanır, aksi hâlde ölçüm **geçersiz** ilan edilir.

## 2. ÖN KAYITLI KABUL ÖLÇÜTLERİ

### Kol 2 — terim sözlüğü (`ozet_terim_sozlugu`)
- **KABUL:** `kanonik_oran_pano` **≥ 0,70** (taban 0,345) **ve**
  `kanonik_oran_yelek`, `kanonik_oran_yaya_yolu` düşmeyecek.
- Aksi hâlde **RET**.

### Kol 3 — şablon onarımı (kalıcı, bayraksız)
- **ZORUNLU KAPI (ana ön kayıt T3):** `tests/test_sablon_kalip.py` geçecek.
  → koşumdan önce **geçti** (40 kontrol, 0 hata).
- **KABUL:** `olcek_sizintisi_olay` **≤ 0,10** (taban 0,606) **ve**
  `forklift_celiskisi` **≤ 0,05**.
  `forklift_celiskisi` = forklift olayı olan özetlerde, "sınır"ın
  *altında* olduğunu söyleyip aynı metinde yükü *aşırı* ilan eden özet oranı.
- Aksi hâlde **RET**.

### Kol 4 — üslup kısıtı (`ozet_uslup_kisiti`)
- **KABUL (üçü birden):** `acilis_Goruntu` **≤ 0,20** (taban 0,889)
  **ve** `meta_son_cumle` **≤ 0,20** (taban 0,435)
  **ve** `tekrar_4gram_orani` en az **0,10 mutlak** düşecek (taban 0,861).
- Aksi hâlde **RET**. (Bu kol en riskli olan; üç ölçütün üçü de gerekli.)

## 3. ZORUNLU KORUMA KAPILARI — her kol için ayrı ayrı

| # | kapı | saparsa |
|---|---|---|
| K-a | Üç sevk matrisi (`TP24/FP2/FN1/TN23`, `TP23/FP0/FN1/TN25`, `TP19/FP2/FN6/TN23`) **birebir** korunacak | anında **RET** |
| K-b | `category_match` düşmeyecek: eşleşmiş **McNemar exact**, tek yönlü p < 0,05 anlamlı kötüleşme **veya** mutlak düşüş > 3 puan | anında **RET** |
| K-c | Çıktı sözleşmesi TAM 4 anahtar (K1) | anında **RET** |
| K-d | Kapalıyken istek **bayt özdeş** (K2) | anında **RET** |

**Kol 2/4 için K-a yapısaldır** (yalnızca özet promptuna ek yaparlar;
gözlem düzlemi ve kural motoru dokunulmaz) — yine de **koşularak
doğrulanır**, iddiaya güvenilmez.

**Kol 3 için K-a GERÇEK RİSKTİR:** olay metni `isg_match`'i besler.
Bu yüzden `isg_match` yeniden yazılmış olay metinlerinden **çevrimdışı
yeniden hesaplanır** (aynı puanlama fonksiyonu, GPU gerekmez) ve matrisler
karşılaştırılır.

## 4. ÖN-RET KAPILARI

| # | kapı |
|---|---|
| a | **DEJENERELİK** — bir kol özetleri tek kalıba düşürürse (`birebir_ayni_ozet_cifti` **artarsa**) RET; kalıplaşmayı azaltmak için eklenen kısıt kalıplaşmayı artıramaz |
| b | **KAPSAM** — 60 klipten < 45'inde özet üretilemezse ölçüm geçersiz |
| c | **UYDURMA** — özet, olay listesinde bulunmayan bir tehlike adı üretirse el ile 5 örnek denetlenir; sistematikse RET |

## 5. Ne olursa ne yapılacak

| sonuç | eylem |
|---|---|
| kol geçer | bayrağı **açık** sevk edilir, sayaç testine bağlanır |
| kol kalır | bayrak **kapalı** kalır, ret gerekçesi koda yazılır |
| kapsam kapısı düşer | hiçbir kol hükme bağlanmaz |

Hiçbir eski skor silinmeyecek. Sonuç ne olursa olsun yazılacak.
