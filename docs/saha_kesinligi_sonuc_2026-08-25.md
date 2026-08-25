# Saha kesinliği — gözle ölçüldü, alt sınır gerçek tahminle değişti

Tarih: **2026-08-25** · Ön kayıt: `docs/on_kayit_saha_kesinligi_2026-08-25.md`
(ölçüt örnek çekilmeden ÖNCE sabitlendi)
Arşiv: `eval_20260825_165802` (658 benzersiz içerik, kanonik yer gerçeği)

## 1. Sonuç

| kural | ateşleme | **ham** | örnek | **düzeltilmiş** | **Wilson alt sınır** |
|---|---|---|---|---|---|
| yetkisiz | 340 | 0,268 | 8/12 | 0,756 | **0,554** |
| pano | 226 | 0,584 | 9/12 | 0,896 | **0,779** |

Ön-ret kapısı geçildi: KARARSIZ oranı %8,3 ve %0 (eşik %40).
Yorum kuralı (§3) uygulandı: alt sınır > ham → **düzeltme raporlanır.**

**Sunumda verilecek sayı alt sınırdır:** yetkisiz ≥ 0,554 · pano ≥ 0,779.

## 2. Yöntem

Her kural için, o kuralın ateşlediği ama klibin o sınıfın etiketini
**taşımadığı** kliplerden tohumlu (seed=7) **12 klip**, klip başına **3 kare**.
Hüküm ölçütü örnek çekilmeden önce yazıldı; KARARSIZ **doğru sayılmadı**
(muhafazakâr).

Düzeltilmiş değer:
`(etiketli doğru + etiketsiz × örnek oranı) / toplam ateşleme`

## 3. Pano için BAKMA YÖNTEMİ düzeltildi — ölçüt değil

İlk denemede tam karede pano kapağının açık mı kapalı mı olduğu **seçilemedi**.
Ölçütü gevşetmek yerine bakma yöntemi düzeltildi:

- kareler `panel_roi_vlm` (`0,00 0,47 0,29 0,81`) ile kırpıldı ve büyütüldü
- montaja **kalibrasyon** eklendi: bilinen AÇIK (`class2`) ve bilinen KAPALI
  (`class6`) kliplerden ikişer kare

Kalibrasyon kararı mümkün kıldı: **AÇIK** = krem kontrol dolabının kapağı
menteşeden dışa açık ve içeride koyu boşluk; **KAPALI** = düz krem yüzey.
Bundan sonra 12 klibin 12'si de karara bağlanabildi (KARARSIZ = 0).

## 4. Tek tek hükümler

### yelek kuralı — 8 EVET / 3 HAYIR / 1 KARARSIZ

| # | klip | hüküm |
|---|---|---|
| Y0 | `2_tr78` | KARARSIZ — figür var, makine başında mı belirsiz |
| Y1 | `4_tr49` | **EVET** — makinenin yanında koyu tulumlu kişi |
| Y2 | `2_tr14` | **EVET** — sol altta makinede kişi |
| Y3 | `0_te19` | HAYIR — kişiler koridorda, makineye bitişik değil |
| Y4 | `0_tr45` | HAYIR — üstte iki kişi, makinelerden uzak |
| Y5 | `2_te3` | **EVET** — makinede eğilmiş operatör |
| Y6 | `2_tr103` | **EVET** |
| Y7 | `6_tr7` | **EVET** — makinede oturan kişi |
| Y8 | `0_tr141` | **EVET** |
| Y9 | `2_tr113` | **EVET** |
| Y10 | `2_tr94` | **EVET** |
| Y11 | `0_tr16` | HAYIR — geniş plan, koridorda kişi |

Üç HAYIR'ın **üçü de** geniş-plan yaya klipleri. Bu, daha önce ölçülen
tanıyla tutarlı: o kamerada kişi çözünürlük altında ve kural orada gerçekten
yanlış ateşliyor.

### pano kuralı — 9 EVET / 3 HAYIR / 0 KARARSIZ

| # | klip | hüküm |
|---|---|---|
| P0 | `1_tr44` | **AÇIK** |
| P1 | `0_tr146` | **AÇIK** |
| P2 | `1_tr66` | kapalı |
| P3 | `4_tr18` | farklı makine — ROI'de pano yok |
| P4 | `0_tr127` | **AÇIK** |
| P5 | `0_tr130` | **AÇIK** |
| P6 | `5_tr20` | **AÇIK** — içeri uzanan el görülüyor |
| P7 | `0_tr135` | **AÇIK** |
| P8 | `1_tr57` | kapalı |
| P9 | `4_te2` | **AÇIK** |
| P10 | `0_tr128` | **AÇIK** |
| P11 | `5_tr15` | **AÇIK** |

## 5. Bu ölçüm neyi DEĞİŞTİRMEZ

- **Çift bazlı MCC'ler etkilenmez.** Onlar temiz etiketli çiftte ölçülüyor;
  bu düzeltme yalnızca saha kesinliğinin yorumunu onarır.
- **Örneklem 12 klip.** Aralık geniş; bu yüzden nokta tahmini değil
  **alt sınır** raporlanıyor.
- **Hüküm gözle verildi.** Model çıktısından bağımsız (dairesel değil) ama
  öznel. Ölçüt önceden yazıldı ve karelere bakıldıktan sonra değiştirilmedi.

## 6. Neden bu düzeltme meşru

Kaynak set her klibe **tek** davranış etiketi veriyor. Aynı karede birden
çok tehlike bulunabiliyor — bu, kaynağın kendi kopyalarıyla zaten kanıtlı
(27 `class0` içeriği aynı zamanda `class1`).

Çok-etiketli düzeltme (`kanonik_etiket.json`) bunu kısmen onarmıştı
(yetkisiz 0,197 → 0,268) ama yalnızca **kopyası olan** klipleri
kurtarabiliyordu. Bu ölçüm kalan boşluğu gözle kapatıyor.

Eski sayılar silinmedi; **ham** sütun tabloda duruyor.
