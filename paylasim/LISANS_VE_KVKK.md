# Lisans ve KVKK — okumadan veri paylaşma

Bu proje **Apache 2.0** ile yarışacak. Şartname kodu, veri setlerini ve
**diğer bileşenleri (ağırlıklar dâhil)** kapsıyor. Aşağıdaki kurallar bu
uygunluğu korumak için var.

---

## 🔴 Kural 1 — `data/industrial` ve `data/eval_defense` baytları YENİDEN YAYINLANMAZ

**Lisans engeli yok** — Mendeley `xjmtb22pff`, **CC BY 4.0** (Mendeley
`data_licence` alanından teyitli).

**Engel KVKK.** Bu klipler Eskişehir OSB'de gerçek bir fabrikanın işyeri gözetim
görüntüsüdür. Görsel denetimde şunlar net görüldü: **yüzler, iş kıyafetleri,
firma logoları**. Bu kişisel veridir ve telif lisansı bunu değiştirmez.

**Yapma:**
- Buluta yükleme (Drive, Dropbox, WeTransfer, HF) — üçüncü tarafa **aktarım**dır
- Sunum/rapora çalışan yüzü içeren kare koyma (bulanıklaştırmadan)
- Repoya ekleme (`.gitignore`'da `data/` zaten var, kaldırma)

**Yap:**
- Herkes `paylasim/veri_kur.py` ile **kaynağından** indirsin
- Sunumda görsel gerekiyorsa yüzleri bulanıklaştır

---

## 🔴 Kural 2 — `data/isafety_bench` YALNIZCA DEĞERLENDİRME

**CC BY-NC-SA 4.0.** İki ayrı zehir:

| madde | sonucu |
|---|---|
| **ShareAlike** | Bu veriyle ince ayar yapılırsa model ağırlıkları **türev eser** sayılabilir → modelimiz de CC BY-NC-SA olmak zorunda kalır → **Apache 2.0 şartı ihlal** |
| **NonCommercial** | Yarışma sonrası ticari kullanım **kapanır** |

Ayrıca klipler YouTube'dan derlenmiş (yayıncının "fair use" beyanı) — yeniden
dağıtımı ayrıca sakıncalı.

**Kod düzeyinde kilit var:** `dilajan/veri_lisans.py`, **fail-closed**. Eğitim
yoluna yasaklı dizin girerse işlemi **durdurur**. Bu kilidi kapatma, atlatma,
`try/except` ile yutma.

Test etmek istersen:
```bash
python -c "from dilajan.veri_lisans import egitim_icin_dogrula; egitim_icin_dogrula(['data/isafety_bench'])"
# LisansIhlali firlatmali
```

---

## 🟢 Kural 3 — KKD verisi ve ağırlıkları serbest

| bileşen | lisans | eğitim | dağıtım |
|---|---|---|---|
| `data/ppe`, `data/ppe_yolo` | CC BY 4.0 | ✅ | ✅ atıf ile |
| `data/yelek_yolo` | CC BY 4.0 | ✅ | ✅ atıf ile |
| `yolo11n-ppe.pt`, `yolo11n-yelek.pt` | türev eser, CC BY 4.0 kaynaklı | — | ✅ atıf ile |

Bu yüzden **ağırlıklar bu pakette var** — kişisel veri içermiyorlar ve lisansları temiz.

⚠️ Ama bu ağırlıkların **eğitim verisi künyesi korunmalı**. Yeniden eğitirsen
`data/isafety_bench`'i karıştırma, yoksa ağırlık kirlenir.

---

## 🔴 Kural 4 — `eval_defense` ile İNCE AYAR YAPMA

Bu bir lisans değil **bilimsel geçerlilik** kuralı. Ölçüldü:

| kısayol | doğruluk | şans |
|---|---|---|
| Arka plan imzası → 1-NN etiket | **%76** | %50 |
| Yalnız encoder metadata'sı → etiket | **%65** | %50 |

Sınıf ile çekim oturumu **birebir örtüşüyor**: `class3` %100 CPU-encode,
`class7` %100 HS-kopya. Bu sette eğitilen model davranışı değil, **dosyanın
nasıl kesildiğini** öğrenir — ve değerlendirme seti anında kirlenir.

Ayrıntı: `docs/veri_seti_nihai_denetim_2026-08-17.md`

---

## Atıf metinleri (rapor/sunum için)

```
Endüstriyel güvenlik klipleri: "Video Dataset for Safe and Unsafe Behaviours",
Mendeley Data, doi:10.17632/xjmtb22pff, CC BY 4.0.

KKD veri seti: "Personal Protective Equipment Detection Dataset (5-Class) for
Construction Safety Monitoring", Mendeley Data, doi:10.17632/8vf7z6v5sb, CC BY 4.0.

Değerlendirme (yalnızca): iSafetyBench, CC BY-NC-SA 4.0.
Eğitimde KULLANILMAMIŞTIR.
```

Son madde önemli: iSafetyBench'i **kullandığımızı ama yalnızca değerlendirmede**
kullandığımızı açıkça yazmak, hem dürüstlük hem lisans savunması.

---

## Şüphedeysen

`docs/veri_lisans_karari.md` — tüm lisans kararlarının gerekçesi ve kaynakları.
Yeni bir veri seti eklemeden **önce** oraya bir künye yaz; `veri_lisans.py`
tablosuna eklemeyi unutma, yoksa kapı onu tanımaz.
