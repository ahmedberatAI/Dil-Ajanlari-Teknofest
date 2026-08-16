# ÖN-KAYIT — İSG taze ölçümü (D33, 2026-08-16)

> **HANDOFF §7.4 gereği yazıldı: bu belge B kolları KOŞULMADAN ÖNCE tamamlandı.**
> Amaç, sonucu gördükten sonra eşiği kaydırma ("hangi sayı çıkarsa onu başarı
> sayma") tuzağını kapatmak. §7.4 ayrıca **mekanik uygulama** şartını koyuyor:
> D31'de red kriteri gürültüye takılmıştı ve tekrar ölçümü kurtarmıştı.

---

## 0. Neden bu ölçüm yapılıyor

HANDOFF §6.0: `eval_defense` üzerindeki en güncel rakam 26 Temmuz'dan ve D29 metrik
onarımından **önce**. "Nerede olduğumuzu bilmeden veri eklemek kör atıştır."

**Ölçüm öncesi ortaya çıkan ek gerekçe (bu oturumda bulundu):**
HANDOFF §4'te İSG başarımı olarak yazılı **"recall %50 · cat_match %36"** rakamı
`eval_20260726_192353.json` koşusundan geliyor ve o koşu **`facility_rules` +
`facility_policy` AÇIK** idi. Aynı gün **varsayılan** yapılandırmayla koşulan
`eval_20260726_162613.json` ise **recall %20 · cat %9** vermiş.
Yani belgedeki başarı rakamı, varsayılan yapılandırmanın rakamı **değil**.
Bu yüzden taze ölçüm **iki yapılandırmayı da** kapsıyor.

---

## 1. Kollar

Hepsinde ortak: `DILAJAN_EVAL_DIR=data/eval_defense`, `DILAJAN_TEMPERATURE=0`,
`facility_policy=""`, `evidence_questions=False`, `use_detector=False`,
`adaptive_reexamine=True` (varsayılan). Termal güvenlik için (§9) Anomali/Normal
ayrı kollar; birleştirme `benchmark/merge_arms.py` ile.

| Kol | Kategori | `facility_rules` | Sonuç dosyası |
|---|---|---|---|
| **A1** | Anomali (n=100) | **BOŞ** (varsayılan) | `eval_20260816_111114.json` ✔ koştu |
| **A2** | Normal (n=100) | **BOŞ** (varsayılan) | koşuyor |
| **B1** | Anomali (n=100) | `scripts/run_policy_ab.py:23` metni **birebir** | — |
| **B2** | Normal (n=100) | aynı | — |

**TEK DEĞİŞKEN:** A ile B arasında yalnızca `DILAJAN_FACILITY_RULES` farkı vardır.
Ortam değişkeninin gerçekten okunduğu koşumdan önce doğrulandı
(`settings.facility_rules` dolu / boş).

---

## 2. Eşleştirme ve test seçimi

- **A vs B**: aynı klipler, iki yapılandırma → **EŞLEŞTİRİLMİŞ** → McNemar exact.
- **Güvensiz sınıf vs güvenli eşi** (ör. class0 vs class4): **farklı klipler** →
  **EŞLEŞMEMİŞ** → **Fisher tam testi** (`benchmark/stats_utils.fisher_exact_p`,
  bu oturumda eklendi, çay-tadımı 2×2 = 0,1 ve Fisher'ın kendi örneğiyle doğrulandı).
  McNemar burada **yanlış test** olurdu.

---

## 3. ÖN-KAYITLI EŞİKLER (koşumdan önce sabitlendi)

Gürültü tabanı §7.1'e göre **%8**; n=100'de %12'den küçük etkiler kanıtlanamaz sayılır.

| # | İddia | Eşik | Eşik tutmazsa yazılacak |
|---|---|---|---|
| **H1** | Kural enjeksiyonu recall'ı artırır | B−A ≥ **+15 puan** **ve** McNemar p<0,05 | "26 Temmuz'daki +27 puan REPLİKE OLMADI" |
| **H2** | Kural enjeksiyonu kategori adlandırmayı artırır (**onarılmış** olumsuzlama kapısıyla) | B−A ≥ **+12 puan** **ve** p<0,05 | "kanıtlanamaz" |
| **H3** | Kural enjeksiyonunun BEDELİ: normal kliplerde operasyonel FP artışı | artış ≥ **+15 puan** ise **maliyet olarak raporlanır** | maliyet kanıtlanamadı |
| **H4** | Model güvensiz sınıfı güvenli eşinden ayırt eder | Fisher p<0,05 (sınıf başına) | "**ayrım kanıtlanamadı**" |

**H2 notu:** kategori adlandırma **onarılmış** kapıyla ölçülür. Gerekçe: D28
kapısı `gözlemlenmedi` biçimini kaçırıyor ve modelin *"hiçbir tehlike ... yetkisiz
giriş ... gözlemlenmedi"* cümlesini **doğru adlandırma** sayıyor. Ölçülen büyüklük:
taze A1'de 26/100 → **5/100**; 26 Tem kurallar-açık koşusunda 42/100 → **25/100**.
Eski kural **silinmedi**, yan yana raporlanıyor (§7.3).

**H4 notu:** bu, veri setinin en değerli özelliğini kullanır — her tehlikenin
**güvenli karşılığı** var (aynı sahne/kamera/ekipman, fark yalnızca davranış).
Arşiv koşusunda (26 Tem, kurallar açık) dört sınıfın **hiçbirinde** ayrım
kanıtlanamamıştı: p = 0,70 / 1,00 / 1,00 / 0,14.

---

## 4. Bu ölçümün KANITLAYAMAYACAĞI şeyler (baştan yazıldı)

1. **Tek koşu yeter demiyoruz.** §7.2 gereği asıl iddialar için tekrar koşusu
   (A′) gerekir. Tekrar koşulmayan her sayı "tek koşu" etiketiyle raporlanacak.
2. **Genelleme yok.** 691 klibin tamamı tek tesis, iki kamera, 39 gün, tek mevsim
   (§5.2 Boşluk 1). Buradaki hiçbir sayı "farklı bir fabrikada da böyle" demez.
3. **`eval_defense`, `industrial`'dan örneklenmiştir.** `industrial` üzerinde
   herhangi bir ince ayar yapılırsa bu set **anında kirlenir** (§5.2 Boşluk 3).
4. **Sınıf başına n=25.** Sınıf düzeyi Wilson aralıkları geniştir; nokta değer
   tek başına raporlanmayacak.
