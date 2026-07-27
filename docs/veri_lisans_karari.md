# Veri Lisans Kararı — Yeniden Dağıtım Analizi

**Tarih:** 2026-07-27 · **Kapsam:** `data/` altındaki türev değerlendirme setlerinin
herkese açık bir HuggingFace *dataset* deposunda yayınlanabilirliği.
**Durum:** Lisans belirsizliği **çözüldü**; yayın mimarisi **katmanlı** olarak belirlendi.

> Bu belge `docs/veri_kaynaklari.md` (envanter + bilinen kusurlar) ve
> `data/HF_DATASET_README.md` (yayınlanacak depo kartı) ile birlikte okunur.
> Çelişki hâlinde **bu belge** esastır — burada verilen kararlar doğrulanmış
> birincil kaynaklara dayanır (bkz. §8).

---

## 0. Yönetici özeti

| # | Soru | Cevap |
|---|---|---|
| 1 | Mendeley/Eskişehir setinin lisansı CC BY mi CC BY-NC mi? | **CC BY 4.0.** Çelişki *görünürdeydi*; makale lisansı ile veri seti lisansı karıştırılmıştı (§1). |
| 2 | O hâlde `eval_defense` (2.4 GB) yayınlanabilir mi? | **Telif açısından evet, ama yayınlamıyoruz.** Engel telif değil, **KVKK/kişisel veri** (§4). Manifest + yeniden kurma betiği ile birebir tekrar üretilebilir. |
| 3 | UCF-Crime türevleri? | **Asla dağıtılmayacak.** Hiçbir lisans verilmemiş; lisansın yokluğu izin değildir (§5). |
| 4 | URFD? | **Dağıtılmayacak.** CC BY-NC-SA 4.0 — NC + ShareAlike, CC BY olan depoyu kirletir (§6). |
| 5 | Ne yayınlanacak? | FIRESENSE + GMDCSA + `robust/` (+ opsiyonel Simuletic) = **~227 MB, tamamı CC BY 4.0** (§3). |
| 6 | Depo lisansı ne olacak? | `cc-by-4.0` — yayınlanan her parçanın lisansı bu (en kısıtlayıcı = tek ortak payda). |

**Bu analizin ana bulgusu şudur:** en kritik varlığımız olan `eval_defense`'in önündeki
engel, aylardır sanıldığı gibi bir **lisans** engeli değildir — lisans temizdir. Engel,
lisansın *çözemeyeceği* bir **kişisel veri** engelidir. İkisi farklı hukuk dallarıdır ve
CC lisansları ikincisini açıkça kapsam dışı bırakır (§4.2).

---

## 1. Mendeley çelişkisinin çözümü

### 1.1 İddia edilen çelişki

`docs/veri_kaynaklari.md` ve `data/industrial/CLASSES.md` şunu kaydediyordu:

> "⚠️ **ÇELİŞKİLİ KAYNAK — muhafazakâr okuma: CC BY-NC.** Mendeley kayıt sayfası/API'si
> `data_licence` alanında **CC BY** gösteriyor; Data in Brief makalesi ise **CC BY-NC**
> (ticari kullanım yok) diyor."

### 1.2 Doğrulama — ne bulundu

**(a) Mendeley Data API — veri setinin kendi lisansı.**
`https://data.mendeley.com/public-api/datasets/xjmtb22pff` yanıtındaki `data_licence`
alanı, **birebir**:

```json
"data_licence": {
  "id": "01d9c749-3c4d-4431-9df3-620b2dcfe144",
  "description": "You can share, copy and modify this dataset so long as you give
    appropriate credit, provide a link to the CC BY license, and indicate if changes
    were made, but you may not do so in a way that suggests the rights holder has
    endorsed you or your use of the dataset. Note that further permission may be
    required for any content within the dataset that is identified as belonging to
    a third party.",
  "url": "http://creativecommons.org/licenses/by/4.0",
  "category": "Creative",
  "short_name": "CC BY 4.0",
  "full_name": "Creative Commons Attribution 4.0 International"
}
```

Kayıt sayfası (`https://data.mendeley.com/datasets/xjmtb22pff/1`) da aynı rozeti
gösteriyor: **"CC BY 4.0"**. Bu alan, veriyi yatıran hak sahibi (kayıt sahibi:
Emre Dandıl, `owner_id` 562b8eae-…) tarafından yatırma anında seçilir.

**(b) Data in Brief makalesi — makalenin kendi lisansı.**
PMC11367630 künyesinde, birebir:

> "This is an open access article under the CC BY-NC license
> (http://creativecommons.org/licenses/by-nc/4.0/)."

Cümlenin öznesi **"this ... article"**tır — *"this dataset"* değil.

**(c) Makale, veri setinin lisansı hakkında hiçbir iddiada bulunmuyor.**
Data in Brief'in zorunlu *Specifications Table*'ındaki "Data accessibility" satırı,
birebir, yalnızca konumu bildiriyor:

> "Repository name: Mendeley Data
> Data identification number: 10.17632/xjmtb22pff.1
> Direct URL to data: https://data.mendeley.com/datasets/xjmtb22pff/1"

Tabloda **"Data license" satırı yoktur**; makale metnindeki tek lisans beyanı (b)'deki
künye satırıdır ve o da makaleye aittir.

### 1.3 Karar ve gerekçe

> **KARAR: Veri seti CC BY 4.0'dır. Ortada gerçek bir lisans çelişkisi yoktur.**

Görünürdeki çelişki bir **kategori hatasıdır**: iki farklı eserin iki farklı lisansı
karşılaştırılmıştı.

| Eser | Nerede yayımlandı | Lisansı veren | Lisans |
|---|---|---|---|
| **Veri seti** (691 mp4) | Mendeley Data, DOI `10.17632/xjmtb22pff.1` | Hak sahibi (Önal & Dandıl), yatırma anında | **CC BY 4.0** |
| **Makale** (veriyi *anlatan* metin, şekiller, tablolar) | Data in Brief, DOI `10.1016/j.dib.2024.110791` | Elsevier / yazar tercihi | CC BY-NC 4.0 |

Data in Brief bir *"data descriptor"* dergisidir: makale, başka bir yerde barındırılan
veriyi tarif eder. Verinin lisansını **barındıran depodaki beyan** belirler; derginin
künye satırı **makale metnini** kapsar. Dolayısıyla:

- Makaleden **alıntı/şekil kullanımı** → CC BY-NC koşullarına tabidir (ticari kullanım yok).
- **Videoların kendisi** → CC BY 4.0'dır; paylaşma, kopyalama, değiştirme ve
  **yeniden dağıtma** atıf koşuluyla serbesttir.

**Önceki "muhafazakâr olarak NC kabul et" kaydı geri çekilmiştir.** Muhafazakârlık
doğru refleksti, ancak yanlış eksende uygulanmıştı: gerçek risk NC değil, §4'teki
kişisel veri riskidir. `data/industrial/CLASSES.md`'deki "ÇELİŞKİLİ KAYNAK" uyarısı
bu bulguyla güncellenmelidir (bkz. §9 açık işler).

### 1.4 Lisansın *kendi içindeki* uyarısı — atlanmaması gereken cümle

CC BY 4.0 metninin Mendeley'deki özetinde, son cümle:

> "Note that further permission may be required for any content within the dataset
> that is identified as belonging to a third party."

Bu cümle §4'ün kapısını açar: lisans, **hak sahibinin sahip olduğu hakları** verir;
sahip olmadıklarını veremez.

---

## 2. Kaynak bazında yeniden dağıtım karar tablosu

| Kaynak | Doğrulanmış lisans | Yeniden dağıtım (telif) | Koşul | Bizim setimizde nerede | **KARAR** |
|---|---|---|---|---|---|
| **FIRESENSE** | CC BY 4.0 (Zenodo 836749) | ✅ Serbest | Atıf | `eval_scenario/Fire` (10), `eval_stress` (9) | **YAYINLA** |
| **GMDCSA-24** | CC BY 4.0 (Zenodo 12921216) | ✅ Serbest | Atıf | `falls_real` (15), `eval_scenario/Fall` (9) | **YAYINLA** |
| **Simuletic CCTV** | CC BY 4.0 (HF kart) | ✅ Serbest | Atıf | `eval_scenario/_deprecated_frozen_fall` (8) | **OPSİYONEL** (ölçüme girmez, kusur kanıtı) |
| **`robust/`** | Bizim ürettiğimiz | ✅ Serbest | — | `robust` (4) | **YAYINLA** (Apache-2.0) |
| **Eskişehir / Mendeley** | **CC BY 4.0** (§1) | ✅ Telifçe serbest | Atıf | `eval_defense` (200), `eval_scenario/Normal` (8), `industrial` (691) | **YAYINLAMA — manifest ile** (§4) |
| **URFD** | **CC BY-NC-SA 4.0** | ⚠️ Şartlı | NC + ShareAlike | `falls_surveillance` (6), `eval_scenario/Fall` (6) | **YAYINLAMA** (§6) |
| **UCF-Crime** | **Lisans beyanı YOK** | ❌ Yasak | — | `eval_tune` (31), `eval_holdout` (32), `e2_vehicle` (9), `eval`, `eval_big`, `eval_scenario/Normal` (4) | **ASLA YAYINLAMA** (§5) |

---

## 3. Yayın mimarisi — üç katman

Tek bir "hepsini yükle / hiçbirini yükleme" kararı yerine, her parçayı kendi hukuki
durumuna göre ele alan üç katman:

### KATMAN A — Baytları yayınla (CC BY 4.0, temiz)

| Alt-set | Kaynak | Klip | Boyut |
|---|---|---|---|
| `eval_scenario/Fire` | FIRESENSE | 10 | 43.4 MB |
| `eval_stress/Normal` | FIRESENSE (negatifler) | 9 | 66.9 MB |
| `falls_real/{Fall,Normal}` | GMDCSA-24 | 15 | 115.0 MB |
| `eval_scenario/Fall` | GMDCSA-24 (alt küme) | 9 | 58.5 MB |
| `robust/` | Bizim | 4 | ~9 KB |
| *(ops.)* `_deprecated_frozen_fall` | Simuletic | 8 | 2.0 MB |
| **Toplam (ops. dâhil)** | | **55 dosya / 46 benzersiz** | **~286 MB** |

> `eval_scenario/Fall`'ın 9 klibi `falls_real/Fall`'ın 9 klibiyle **birebir aynıdır**
> (MD5 doğrulandı). Depoda iki kez durmaları kasıtlıdır (set bütünlüğü), ama
> **bağımsız kanıt değildirler** — birlikte raporlanamazlar.

### KATMAN B — Manifest yayınla, baytları yayınlama (Eskişehir)

`eval_defense` (200 klip / 2.57 GB) ve `eval_scenario/Normal`'ın 8 Eskişehir klibi.
Telifçe serbest olmalarına rağmen bayt olarak taşınmazlar (§4). Bunun yerine:

`manifest/eval_defense.jsonl` — her satırda: hedef yol, orijinal Mendeley dosya adı,
Mendeley `file id`, MD5, sınıf etiketi, Anomali/Normal ataması.

Yeniden kurma: `scripts/get_industrial.py` → `scripts/build_defense_eval.py`.
Doğrulama: manifest MD5'leri ile birebir eşleşme. **Jüri seti bit-bit yeniden kurabilir.**

> **Yan kazanç:** manifest Mendeley dosya kimliklerini taşıdığı için indirici,
> 691 klibin tamamını (9.4 GB) değil yalnızca gereken 200 klibi (2.4 GB) çekebilir.
> Takımın asıl derdi olan indirme süresi **~4 kat** kısalır. (Betik değişikliği
> gerektirir — §9.)

### KATMAN C — Yalnızca dosya adı listesi (UCF-Crime)

`eval_tune`, `eval_holdout`, `e2_vehicle` ve `eval_scenario/Normal`'ın 4 UCF klibi.
Yayınlanan tek şey **dosya adları + MD5 + set ataması**dır — bu bir metin listesidir,
videonun kendisi değildir. UCF-Crime erişimi olan bir jüri üyesi seti kendi
kopyasından yeniden kurabilir; erişimi olmayan **kuramaz** ve bu bilinçli bir
sınırlılıktır (bkz. `docs/olcum_durustlugu.md`).

---

## 4. `eval_defense` neden yayınlanmıyor — telif değil, KVKK

Bu, belgedeki en önemli ayrımdır ve yanlış anlaşılmaya çok müsaittir:

> **Lisans temiz. Sorun lisans değil.**

### 4.1 Verinin niteliği

Mendeley API'sinin `description` ve `method` alanlarından, birebir:

> "The dataset was collected from the security cameras of a production facility
> operating in an organised industrial zone in Eskişehir, Turkey, **after obtaining
> the necessary permissions from company officials and employees**."

> "The videos in the workplaces for this dataset were obtained between 5 November 2022
> and 13 December 2022 from **\"Kafaoğlu Metal Plastik Makine San. ve Tic. A.Ş.\"**
> in Eskisehir, Turkey."

Yani veri: **adı açıkça belirtilmiş özel bir şirkette**, **tanınabilir gerçek
çalışanların**, 1920×1080 çözünürlükte, 39 gün boyunca kaydedilmiş iş yeri gözetim
görüntüsüdür. Üstelik `class0` ("Güvenli yürüme yolu ihlali") gibi sınıflar, belirli
çalışanların **kural ihlali yaptığı anları** etiketlemektedir.

### 4.2 CC BY 4.0 bu hakları vermez — veremez

CC BY 4.0 hukuki metni, Bölüm 2(b)(1), birebir:

> "Moral rights, such as the right of integrity, are not licensed under this Public
> License, nor are publicity, privacy, and/or other similar personality rights"

Devamındaki feragat cümlesi ise yalnızca **"any such rights held by the Licensor"** ile
sınırlıdır. Görüntüdeki çalışanların özel hayat ve kişilik hakları **lisans verenin
(Önal & Dandıl) elinde tuttuğu haklar değildir**; dolayısıyla CC BY ile devredilemez.

Mendeley'in kendi lisans özeti de aynı şeyi söylüyordu (§1.4):

> "Note that further permission may be required for any content within the dataset
> that is identified as belonging to a third party."

### 4.3 Sonuç: rıza kapsamı ve yeni veri sorumluluğu

- Rıza, **orijinal araştırmacılara, kendi çalışmaları için** verilmiştir. Bu rızanın
  üçüncü bir tarafın (bizim) **kendi adımıza açtığımız yeni bir kamuya açık depoda**
  yeniden yayınlamamızı kapsadığı **gösterilemez**.
- KVKK (6698 sayılı Kanun) bakımından, görüntüleri kendi hesabımızda yeniden
  yayınlamak bizi **yeni bir veri sorumlusu** hâline getirir; aydınlatma, hukuki
  sebep ve silme taleplerini karşılama yükümlülükleri **bize** geçer.
- Kazanç ise **sıfıra yakındır**: veri zaten Mendeley'den kimlik doğrulaması olmadan
  herkese açıktır. Yeniden barındırma erişimi artırmaz — yalnızca sorumluluğu bize taşır.

> **KARAR: `eval_defense` bayt olarak yayınlanmaz. Manifest + yeniden kurma betiği
> ile tekrar üretilebilirlik tam olarak korunur.**
>
> Bu bir *lisans* kısıtı değil, *ihtiyat* kararıdır. Ticari olmayan yarışma
> kullanımımız her iki okumada da (CC BY veya CC BY-NC) zaten uygundur; tartışılan
> tek şey **yeniden yayınlamak**tır.

### 4.4 Bu karar hangi koşulda değişebilir

Yayınlama yine de istenirse, **önce** şunlar yapılmalıdır (hiçbiri bu görev
kapsamında yapılmamıştır):

1. Danışman hoca ve/veya kurum hukuk biriminden **yazılı görüş**.
2. Orijinal yazarlara (Önal & Dandıl) **bilgilendirme e-postası** ve tercihen onay.
3. Depo kartında açık **kaldırma (take-down) taahhüdü** ve iletişim adresi.
4. `eval_defense`'in yüz bulanıklaştırma uygulanmış bir sürümünün yeterli olup
   olmadığının değerlendirilmesi (ölçüm geçerliliğini bozabilir — ayrı bir karar).

---

## 5. UCF-Crime — neden "asla"

**Bulgu: UCF-Crime için herhangi bir lisans beyanı doğrulanamadı.** Resmî CRCV
sayfasına erişim TLS sertifika hatası nedeniyle başarısız oldu; arama üzerinden de
açık bir kullanım şartı/lisans metni bulunamadı.

Bu, kararı **zayıflatmaz — güçlendirir**:

- Telif hukukunda **lisansın yokluğu izin değildir**. İzin verilmediyse, verilmemiştir.
- CC benzeri hiçbir açık lisans işareti yoktur; set akademik/araştırma kullanımı için
  sunulmaktadır.
- Ayrıca kliplerimizi **resmî kaynaktan değil**, üçüncü-taraf bir HuggingFace
  aynasından (`ertiaM/Anomaly_Detection_in_Surveillance_Videos`) çekiyoruz. **O aynanın
  kendi yeniden dağıtım yetkisi de belirsizdir.** Bir başkasının belirsiz yetkiyle
  yaptığı yeniden dağıtım, bize yetki üretmez; yetkisiz bir aynadan alıp yeniden
  yayınlamak ihlali **çoğaltır**.

> **KARAR: UCF-Crime türevi hiçbir video baytı yayınlanmayacaktır.** Yalnızca dosya
> adı + MD5 listesi (Katman C) yayınlanır.

Etkilenen setler: `eval_tune` (31), `eval_holdout` (32), `e2_vehicle` (9),
`eval` (31), `eval_big` (63) ve `eval_scenario/Normal` içindeki 4 klip.

---

## 6. URFD — CC BY-NC-SA 4.0 bulgusu

**Envanterdeki kayıt güncellenmelidir.** `docs/veri_kaynaklari.md` URFD'yi belirsiz
biçimde "Akademik/araştırma" olarak listeliyordu. Resmî sayfadan doğrulanan gerçek
lisans, birebir:

> "This work is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike
> 4.0 International License and is intended for non-commercial academic use."

Yani URFD aslında **gerçek bir CC lisansına sahiptir** ve teknik olarak yeniden
dağıtılabilir. Buna rağmen **yayınlamıyoruz**, çünkü:

1. **NC bulaşması.** Deponun geri kalanı CC BY 4.0'dır (ticari kullanım serbest).
   URFD eklenirse depo genelinde NC kısıtı doğar ve tek bir basit `license:` alanı
   artık doğruyu söylemez.
2. **ShareAlike bulaşması.** Kliplerimiz ham değildir: `scripts/get_urfd_overhead.py`
   PNG dizisini `ffmpeg` ile mp4'e çevirmektedir — bu, *Adapted Material* sayılmaya
   açık bir işlemdir ve ShareAlike'ı tetikleyerek türev setin CC BY-NC-SA ile
   lisanslanmasını gerektirebilir.
3. **Maliyet çok düşük.** Toplam 6 klip / 3.9 MB. `get_urfd_overhead.py` bunları
   yerelde saniyeler içinde yeniden üretir.

> **KARAR: URFD yayınlanmaz.** `eval_scenario/Fall`'ın HF'deki sürümü 15 değil
> **9 klip** (yalnızca GMDCSA) içerir; 6 URFD klibi yerelde betikle eklenir.
> Bu, HF sürümü ile yerel sürüm arasında **kasıtlı bir kompozisyon farkıdır** ve
> depo kartında açıkça belirtilmiştir.

---

## 7. Atıf metinleri (zorunlu)

Yayınlanan her alt-set için atıf **zorunludur** (CC BY 4.0 md. 3(a)). Aşağıdaki
metinler `data/HF_DATASET_README.md`'ye birebir aktarılmıştır.

**FIRESENSE** — `eval_scenario/Fire`, `eval_stress`
```bibtex
@dataset{grammalidis_firesense,
  author    = {Grammalidis, Nikos and Dimitropoulos, Kosmas and Cetin, Enis},
  title     = {{FIRESENSE} database of videos for flame and smoke detection},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.836749},
  url       = {https://zenodo.org/records/836749},
  note      = {CC BY 4.0}
}
```

**GMDCSA-24** — `falls_real`, `eval_scenario/Fall`
```bibtex
@dataset{alam_gmdcsa24,
  author    = {Alam, Ekram and Sufian, Abu and Dutta, Paramartha
               and Leo, Marco and Hameed, Ibrahim A.},
  title     = {{GMDCSA24}: A Dataset for Human Fall Detection in Videos},
  year      = {2024},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.12921216},
  note      = {CC BY 4.0}
}
```

**Eskişehir / Kafaoğlu** — `eval_defense`, `industrial` (manifest ile yeniden kurulur;
veri kullanıldığı için atıf yine de zorunludur)
```bibtex
@misc{onal_dandil_dataset,
  author    = {Önal, Oğuzhan and Dandıl, Emre},
  title     = {Video Dataset for Safe and Unsafe Behaviours},
  year      = {2024},
  publisher = {Mendeley Data},
  version   = {V1},
  doi       = {10.17632/xjmtb22pff.1},
  note      = {CC BY 4.0}
}

@article{onal_dandil_dib,
  author  = {Önal, Oğuzhan and Dandıl, Emre},
  title   = {Video dataset for the detection of safe and unsafe behaviours
             in workplaces},
  journal = {Data in Brief},
  year    = {2024},
  doi     = {10.1016/j.dib.2024.110791},
  note    = {Makale CC BY-NC 4.0; tarif ettiği veri seti CC BY 4.0}
}
```

**URFD** — yalnızca yerel kullanım (yayınlanmıyor)
```bibtex
@article{kwolek_kepski_urfd,
  author  = {Kwolek, Bogdan and Kepski, Michal},
  title   = {Human fall detection on embedded platform using depth maps
             and wireless accelerometer},
  journal = {Computer Methods and Programs in Biomedicine},
  volume  = {117}, number = {3}, pages = {489--501}, year = {2014},
  issn    = {0169-2607},
  note    = {CC BY-NC-SA 4.0}
}
```

**UCF-Crime** — yalnızca yerel kullanım (yayınlanmıyor)
```bibtex
@inproceedings{sultani_ucf_crime,
  author    = {Sultani, Waqas and Chen, Chen and Shah, Mubarak},
  title     = {Real-world Anomaly Detection in Surveillance Videos},
  booktitle = {IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
  year      = {2018}
}
```

**Simuletic** — opsiyonel, ölçüme girmez
```bibtex
@dataset{simuletic_cctv,
  author    = {{Simuletic}},
  title     = {{CCTV} Incident Dataset: Fall / Lying Down Detection},
  publisher = {Hugging Face},
  url       = {https://huggingface.co/datasets/Simuletic/CCTV_Incident_Dataset_Fall_Lying_Down_Detection},
  note      = {CC BY 4.0; sentetik}
}
```

---

## 8. Doğrulama kaydı

Tüm erişimler **2026-07-27** tarihinde, **yalnızca okuma** amacıyla yapılmıştır.
Hiçbir yükleme, hesap oluşturma veya yazma işlemi gerçekleştirilmemiştir.

| # | Kaynak | Erişim | Elde edilen |
|---|---|---|---|
| 1 | `data.mendeley.com/public-api/datasets/xjmtb22pff` | ✅ Ham JSON | `data_licence.short_name = "CC BY 4.0"`; `description`; `method`; 691 dosya |
| 2 | `data.mendeley.com/datasets/xjmtb22pff/1` | ✅ | Sayfa rozeti: "CC BY 4.0" |
| 3 | `pmc.ncbi.nlm.nih.gov/articles/PMC11367630/` | ✅ | Makale künyesi CC BY-NC; Specifications Table'da **"Data license" satırı yok** |
| 4 | `sciencedirect.com/…/S235234092400756X` | ❌ HTTP 403 | — (3 numaralı kayıt aynı makalenin PMC nüshasıdır) |
| 5 | `creativecommons.org/licenses/by/4.0/legalcode.en` | ✅ | Bölüm 2(b)(1) kişilik hakları istisnası |
| 6 | `zenodo.org/records/836749` | ✅ | FIRESENSE = "Creative Commons Attribution 4.0 International" |
| 7 | `zenodo.org/records/12921216` | ✅ | GMDCSA24 = "Creative Commons Attribution 4.0 International" |
| 8 | `github.com/ekramalam/GMDCSA24-…` | ✅ | Depo MIT (kod); veri lisansı için 7 numara esastır |
| 9 | `fenix.ur.edu.pl/~mkepski/ds/uf.html` | ✅ | URFD = CC BY-NC-SA 4.0 (birebir alıntı §6) |
| 10 | `huggingface.co/datasets/Simuletic/…` | ✅ | `license: cc-by-4.0`; sentetik |
| 11 | `crcv.ucf.edu/projects/real-world/` | ❌ TLS sertifika hatası | **Lisans doğrulanamadı** → §5 muhafazakâr karar |

**Dürüstlük notu:** 4 ve 11 numaralı kaynaklara erişilememiştir. 4'ün etkisi yoktur
(aynı makaleye PMC üzerinden erişildi). 11'in etkisi vardır ve **kararı daha
kısıtlayıcı** yönde belirlemiştir: UCF-Crime için lisans **bulunamadığı** için
"izin yok" kabul edilmiştir. Hiçbir lisans metni tahmin edilmemiş veya uydurulmamıştır.

### Yerel envanterin doğrulanması

Aşağıdaki sayılar bu belge yazılırken ölçülmüştür (`ffprobe`/`md5sum` değil, dosya
sistemi + MD5):

```bash
cd data
# Katman A (yayınlanacak) — 47 dosya (+8 ops.), 38 benzersiz MD5, 283.8 MB
find eval_scenario/Fire eval_stress falls_real robust -type f \( -name '*.mp4' -o -name '*.avi' \)
find eval_scenario/Fall -name 'Subject*.mp4'        # 9 GMDCSA (urfd_* HARİÇ)

# Katman B (manifest) — 208 dosya, 200 benzersiz, 2 608.1 MB
find eval_defense -name '*.mp4'                      # 200
find eval_scenario/Normal -name '*.mp4' ! -name 'Normal_Videos_*'   # 8

# Katman C (yalnızca liste) — 76 dosya, 66 benzersiz, 297.0 MB
find eval_tune eval_holdout e2_vehicle -type f -name '*.mp4'
find eval_scenario/Normal -name 'Normal_Videos_*'    # 4
```

**Ölçüm sonucu (2026-07-27):**

| Katman | Dosya | Benzersiz MD5 | Boyut |
|---|---|---|---|
| A — yayınlanacak | 47 (+8 ops.) | 38 (+8) | 283.8 MB (+2.0) |
| B — manifest | 208 | 200 | 2 608.1 MB |
| C — yalnızca liste | 76 | 66 | 297.0 MB |

> A katmanındaki 47 dosya 38 benzersiz MD5'e karşılık gelir: `eval_scenario/Fall`'ın
> 9 GMDCSA klibi `falls_real/Fall` ile aynıdır. B katmanındaki 208 dosya 200 benzersizdir:
> `eval_scenario/Normal`'ın 8 Eskişehir klibi `eval_defense/Normal` içinde de vardır.
> **Bu mükerrerlikler ölçüm raporlarında çift sayılmamalıdır.**

**Katman C saf UCF değildir — önemli bulgu.** `eval_tune` ve `eval_holdout`'un `Normal`
klasörleri **karışıktır**: 76 dosyanın 8'i aslında Eskişehir kökenlidir
(`eval_tune/Normal/{5_tr19,6_tr9,7_tr15}`, `eval_holdout/Normal/{4_tr13,6_te10,6_te12,6_tr17,6_tr8}`),
geri kalan **68'i gerçek UCF-Crime** klibidir (58 benzersiz MD5, 260.0 MB).
Setin *bir kısmının* dağıtılabilir olması setin *tamamını* dağıtılabilir yapmaz:
UCF bileşeni tüm seti kilitler. Bu yüzden `eval_tune`/`eval_holdout` bütün olarak
Katman C'dedir.

Aynı şekilde `eval_scenario/Normal`'ın 12 klibinden 8'i Eskişehir (Katman B), **4'ü
UCF-Crime**'dır (`Normal_Videos_{926,928,929,932}_x264.mp4`, Katman C). Bu, görev
tanımında `eval_scenario/Normal` "tamamen Eskişehir" varsayıldığı için **denetimde
yakalanan bir hatadır**; setin HF sürümü bu 4 klibi içermez.

---

## 9. Açık işler (bu görev kapsamı dışında)

Bu belge yalnızca **karar ve gerekçe** üretir. Aşağıdakiler ayrı iştir:

1. **`data/industrial/CLASSES.md` güncellenmeli** — "⚠️ ÇELİŞKİLİ KAYNAK — muhafazakâr
   okuma: CC BY-NC" satırı artık yanlıştır; §1.3 ile değiştirilmelidir.
2. **`docs/veri_kaynaklari.md` §2 tablosu güncellenmeli** — Eskişehir satırındaki
   "teslimden önce makaleden teyit edilecek" notu **kapatılmıştır** (§1);
   URFD satırı "Akademik/araştırma" → **"CC BY-NC-SA 4.0"** olmalıdır (§6).
3. **Manifest üretici betik yazılmalı** — Katman B/C için
   `scripts/make_data_manifest.py` (yol + MD5 + Mendeley file-id + sınıf + set).
4. **`get_industrial.py` seçici indirmeye geçmeli** — manifest'teki 200 dosya kimliğini
   kullanarak 9.4 GB yerine 2.4 GB çeksin (§3, Katman B yan kazancı).
5. **HF deposu oluşturulmalı ve yüklenmeli** — **kullanıcı onayı ve HF token gerektirir.**
   Bu görevde **hiçbir şey yüklenmemiştir**; `data/HF_DATASET_README.md` yalnızca taslaktır.
6. **§4.4 maddeleri** — `eval_defense` için yayın kararı yeniden ele alınacaksa.

---

## 10. Yarışma kuralı — HF kullanımının meşruiyeti

Şartname harici API/bulut üzerinden **model çalıştırmayı** yasaklar. Burada önerilen
kullanım bu kapsama girmez ve ayrım her iki belgede de açıkça yazılmıştır:

| Kullanım | Durum | Bu projede |
|---|---|---|
| HF Inference API / Endpoints / Spaces ile **model çalıştırma** | ❌ **YASAK** | **Kullanılmıyor.** |
| HF'den **model ağırlığı indirme** (sonra yerelde çalıştırma) | ✅ Serbest | Qwen3-VL-8B-FP8 indirilir, vLLM ile **yerelde** servis edilir. |
| HF'de **veri seti barındırma / indirme** | ✅ Serbest | Bu belgenin konusu. Veri indirilir, değerlendirme **yerelde** koşar. |

Çıkarım anında hiçbir ağ çağrısı yapılmaz; HF yalnızca **kurulum zamanı bir dosya
deposudur**. Bu, `pip install` ile paket indirmekten farklı değildir.
