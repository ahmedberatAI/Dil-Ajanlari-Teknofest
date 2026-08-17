# Takım paylaşım paketi — veri kurulumu

Bu paket **ham video/görsel içermez.** İçindekiler: kurulum betiği, doğrulama aracı,
eğitilmiş ağırlıklar ve künyeler. Veriyi **kendi makinende kaynağından** kuracaksın.

## Neden ham veri yok — bu bilinçli bir karar

`data/industrial` (9,4 GB) telif açısından **CC BY 4.0**, yani yeniden dağıtmak
*yasal olarak* mümkün. **Ama dağıtmıyoruz:**

> Gerçek bir fabrikanın (Eskişehir OSB) işyeri gözetim görüntüsü ve içindeki
> **çalışanlar tanınabiliyor**. Denetim sırasında yüzler, iş kıyafetleri ve firma
> logoları net görüldü. Bu **KVKK kapsamında kişisel veridir** ve telif lisansı
> bunu değiştirmez.

Veriyi bir buluta yüklemek = **üçüncü tarafa aktarım**. Bunun yerine herkes
kaynağından indirir: kimsenin sunucusundan kişisel veri geçmez, üstelik paket
17 GB yerine **~12 MB** olur.

`data/isafety_bench` ise **CC BY-NC-SA 4.0** — ShareAlike zehirli haptır,
yeniden dağıtımı ayrıca sakıncalı. Detay: `LISANS_VE_KVKK.md`.

---

## Kurulum (3 adım)

**Ön koşul:** repoyu klonlamış ve `requirements.txt`'i kurmuş ol.

```bash
git clone <repo-url> && cd DilAjanlariTeknofest
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 1) Ağırlıkları yerine koy

```bash
cp paylasim/agirliklar/*.pt .
```

### 2) Veriyi kaynağından kur

```bash
python paylasim/veri_kur.py --hepsi
```

Ne kadar sürer / ne iner:

| bileşen | boyut | kaynak | lisans |
|---|---|---|---|
| `data/industrial` (691 klip) | ~9,4 GB | Mendeley `xjmtb22pff` | CC BY 4.0 |
| `data/eval_defense` (197 klip) | 0 (hardlink) | yukarıdakinden türetilir | — |
| `data/isafety_bench` (1.100 klip) | ~1,3 GB | HF `raiyaanabdullah/isafety-bench` | CC BY-NC-SA ⚠️ |
| `data/ppe` + `ppe_yolo` + `yelek_yolo` | ~2,5 GB | Mendeley + Roboflow | CC BY 4.0 |

Sadece bir kısmını istersen: `--industrial`, `--isafety`, `--ppe`.
İndirme koptuğunda **kaldığı yerden devam eder**.

### 3) Doğrula

```bash
python paylasim/dogrula.py
```

Künyelerdeki MD5'lerle karşılaştırır. **Yeşil değilse ölçüm yapma** — farklı
klip kümesiyle çıkan sayı bizimkiyle karşılaştırılamaz.

---

## Ölçüm yapacaksan bunları bil

**1. `eval_defense` 197 klip, 200 değil.** Üç klip **çıkarıldı** çünkü aynı görüntü
zıt etiketle iki kez sette bulunuyordu (piksel düzeyinde ölçüldü). Karantina:
`data/eval_defense/_celiskili_cikarildi/`. Ayrıntı:
`docs/veri_seti_nihai_denetim_2026-08-17.md`.

**2. Bu veriyle İNCE AYAR YAPMA.** Ölçüldü: arka plan imzasından 1-NN ile etiket
**%76** doğrulukla tahmin ediliyor (şans %50); yalnız encoder metadata'sından **%65**.
Sınıf ile çekim oturumu birebir örtüşüyor. Bu sette eğitilen model davranışı değil,
**dosyanın nasıl kesildiğini** öğrenir.

**3. `isafety_bench` YALNIZCA değerlendirme.** Eğitimde kullanmak model ağırlıklarını
CC BY-NC-SA türev eseri yapabilir → yarışma Apache 2.0 şartı ihlal edilir.
Kod düzeyinde kilit var (`dilajan/veri_lisans.py`, fail-closed) — kapatma.

**4. Güncel taban çizgisi** (8B varsayılan, temiz 197 klip):

| metrik | değer |
|---|---|
| recall | 0,283 |
| hassasiyet | 0,571 |
| tespit MCC | +0,0793 |
| **isg_özgül** (doğru tehlikeyi adlandırma) | **1/99** |
| sevk kapısı MCC | −0,117 |

⚠️ `recall` **doğru tehlikeyi ölçmez** (yalnızca "≥1 olay üretildi"). Gerçek yetenek
`isg_özgül` sütunudur. Rapor yazarken ikisini karıştırma.

---

## Nereden başlamalı

| ne öğrenmek istiyorsan | oku |
|---|---|
| Projenin tam durumu | `docs/HANDOFF.md` (pakette var, repoda yok) |
| Veri setinin sınırları | `docs/veri_seti_nihai_denetim_2026-08-17.md` |
| Neden yamalar reddedildi | `docs/kusur_cozum_akisi_2026-08-17.md` |
| Ölçüm disiplini | `HANDOFF.md` §7 |
| Lisans kararları | `docs/veri_lisans_karari.md` |
