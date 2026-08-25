# ÖN KAYIT — yarışma hazırlığı: GÖRÜLMEMİŞ İSG videolarında performans

Tarih: **2026-08-25**, koşumdan **ÖNCE**. Dal: `d34-isg-veri-kkd`

## 0. Sorulan soru

Yarışmada bize **hiç görmediğimiz** bir İSG senaryosu videosu verilecek.
Bugüne kadarki bütün ölçümler tek bir tesisin iki kamerasından geliyor
(`data/industrial`). Bu ön kayıt şunu sorar:

> Sevk edilen sistem, **başka bir alandan** gelen İSG videosunda ne yapıyor?

## 1. Küme

**`data/isafety_bench`** — 1100 klip (420 tehlike / 680 normal),
kaynak: halka açık YouTube videoları, `arXiv:2508.00399`.

**Lisans (`data/isafety_bench/LISANS.json`):**
`degerlendirmede_kullanilabilir: true` · `egitimde_kullanilabilir: false` ·
`yeniden_yayimlanabilir: false`. Bu koşum **yalnızca değerlendirmedir**;
ağırlık üretilmez. `dilajan/veri_lisans.py` bunu fail-closed zorluyor.

**Alan uyarısı (kendi lisans kaydımızdan):**
> *"Dağıtım alanı sabit-kamera endüstriyel CCTV; bu set YouTube kaynaklı.
> Sonuçlar GENELLEME STRES TESTİDİR, aynı-alan kanıtı DEĞİL."*

Bu uyarı sonucun yorumunu bağlar: burada çıkan sayı bir *alt sınır*
değil, bir *stres testi* sonucudur. Yarışma videosu muhtemelen bu ikisinin
arasında bir yerde olacak (endüstriyel ama bizim kameramız değil).

**Örneklem:** tohumlu (seed=7) **50 tehlike + 50 normal = 100 klip.**

## 2. Yapılandırma — SEVK EDİLEN, olduğu gibi

Hiçbir şey açılıp kapatılmayacak. Yarışmada ne koşacaksa o koşacak:
`isg_slotlari` üç sevk slotu · `facility_rules` boş · `slot_guven` kapalı ·
`kodlama_normalize` açık. Bu bilerek: **tesise kalibre gözlem düzleminin
alan dışında ne yaptığını da ölçmek** bu testin parçası.

## 3. ÖLÇÜLECEK ÜÇ ŞEY ve ÖLÇÜTLERİ

### G1 — Tehlike ayrımı (birincil)
Sistem tehlike kliplerinde olay üretip normal kliplerde susuyor mu?

| ölçüt | eşik |
|---|---|
| tehlike recall (olay üretilen tehlike klibi oranı) | ≥ **0,70** |
| normal FP (olay üretilen normal klip oranı) | ≤ **0,40** |
| MCC (olay var/yok ↔ tehlike/normal) | ≥ **+0,30** |

Üçü birden sağlanırsa **G1 GEÇTİ**.

**Neden bu eşikler:** kendi setimizde tehlike recall 0,859 · normal FP 0,541.
Alan dışında düşüş beklenir; 0,70 / 0,40 "kullanılabilir ama zayıflamış"
seviyesidir. MCC +0,30 şanstan anlamlı biçimde iyidir.

### G2 — Tesise kalibre kuralların ALAN DIŞI YANLIŞ ATEŞLEMESİ
Pano/forklift/yelek kuralları bu videolarda ateşliyor mu? Ateşliyorsa
**yanlıştır** — o tesisin panosu, forklifti, yeleği burada yok.

| ölçüt | eşik |
|---|---|
| İSG kuralı ateşleyen klip oranı (100 klip içinde) | ≤ **0,25** |

Üstündeyse: gözlem düzlemi alan dışında **gürültü üretiyor** demektir ve
bu, yarışma için **açık bir risktir** — raporlanır.

### G3 — Tehlikeyi ADLANDIRMA (ikincil)
Üretilen Türkçe özet, klibin `gt_actions` etiketiyle örtüşüyor mu?
Tohumlu 15 tehlike klibinde **gözle** değerlendirilecek; ölçüt:

- **EVET** — özet, `gt_actions`'taki tehlikeyi tanınabilir biçimde adlandırıyor
- **KISMEN** — sahneyi doğru anlatıyor ama tehlikeyi adlandırmıyor
- **HAYIR** — yanlış/uydurma

KISMEN ve HAYIR doğru sayılmaz. Ölçüt koşumdan önce sabit.

## 4. ÖN-RET KAPILARI

| # | kapı |
|---|---|
| a | **KOŞUM BÜTÜNLÜĞÜ** — 100 klibin ≥ %90'ı işlenmezse ölçüm geçersiz |
| b | **DEJENERELİK** — sistem 100 klibin ≥ %95'inde olay üretirse veya ≥ %95'inde susarsa ölçüm dejenere, sayı raporlanmaz |
| c | **LİSANS** — bu koşumdan ağırlık/ince ayar üretilmeyecek; yalnızca ölçüm |

## 5. Ne olursa ne yazılacak

| sonuç | eylem |
|---|---|
| G1 geçer, G2 geçer | sistem alan dışında **kullanılabilir**; sunumda bu ölçüm verilir |
| G1 geçer, G2 kalır | anlatı düzlemi genelliyor ama gözlem düzlemi gürültü üretiyor → yarışmada İSG slotlarını kapatma seçeneği değerlendirilir |
| G1 kalır | sistem alan dışında **zayıf**; bu açıkça raporlanır ve sunumda alan sınırı öne çıkarılır |

Sonuç ne olursa olsun yazılacak. Hiçbir eski skor silinmeyecek.
