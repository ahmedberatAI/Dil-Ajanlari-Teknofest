# Veri setleri — kaynak bağlantıları ve indirme

> Bu belgenin bir kopyasi `data/INDIRME_LINKLERI.md` altindadir (o dizin
> `.gitignore`lu oldugu icin asil kopya burada tutulur).

Takım arkadaşları için. **Videoları paylaşmıyoruz; herkes kaynağından indiriyor.**
Bu hem lisans hem KVKK açısından doğru yol, hem de 40 GB'lık arşiv taşımaktan kurtarır.

Her set için kuran betik `scripts/` altında zaten var ve **indirmeyi kendisi yapar**.

> **Eskişehir OSB tesis videoları bu listede yok** — ekip kararı.
> (Not: o setin de halka açık akademik kaynağı var, aşağıda "Dışarıda bırakılan"
> başlığında yazılı. Kaynağa yönlendirmek yeniden yayım değildir; karar sizin.)

---

## Hızlı kurulum

```bash
python scripts/get_ucf_many.py          # UCF-Crime buyuk set  -> data/eval_big
python scripts/split_eval_big.py        # ayrik tune/holdout bolmesi
python scripts/get_firesense.py         # yangin/duman         -> data/eval_scenario/Fire + eval_stress
python scripts/get_gmdcsa.py            # gercek dusme         -> data/falls_real
python scripts/get_urfd_overhead.py     # tepeden dusme        -> data/falls_surveillance
python scripts/get_vehicle_accidents.py # arac kazasi          -> data/e2_vehicle
python scripts/get_ppe.py               # KKD (baret/yelek)    -> data/ppe
python scripts/get_isafety_bench.py     # iSafetyBench         -> data/isafety_bench
python scripts/make_test_video.py       # sentetik test klibi  -> data/test_clip.mp4
```

---

## Kaynak tablosu

| dizin | veri seti | kaynak | lisans | eğitim | yeniden yayım |
|---|---|---|---|---|---|
| `eval/`, `eval_big/`, `eval_tune/`, `eval_holdout/` | **UCF-Crime** | [ertiaM/Anomaly_Detection_in_Surveillance_Videos](https://huggingface.co/datasets/ertiaM/Anomaly_Detection_in_Surveillance_Videos) · normaller: [shahadalll/UCF-cime-binary-balanced](https://huggingface.co/datasets/shahadalll/UCF-cime-binary-balanced) · resmî: [crcv.ucf.edu](https://www.crcv.ucf.edu/projects/real-world/) | akademik / araştırma | — | — |
| `eval_scenario/Fire`, `eval_stress/` | **FIRESENSE** | [zenodo.org/records/836749](https://zenodo.org/records/836749) | Zenodo kaydı | — | — |
| `falls_real/` | **GMDCSA-24** | [github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos](https://github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos) | kaynak repoda | — | — |
| `falls_surveillance/` | **URFD** (tepeden bakış) | [fenix.ur.edu.pl/mkepski/ds/uf.html](https://fenix.ur.edu.pl/mkepski/ds/uf.html) | akademik | — | — |
| `e2_vehicle/` | UCF **RoadAccidents** alt kümesi | yukarıdaki UCF-Crime aynası | akademik | — | — |
| `scenario/lying` | **CCTV Fall / Lying Down** | [Simuletic/CCTV_Incident_Dataset_Fall_Lying_Down_Detection](https://huggingface.co/datasets/Simuletic/CCTV_Incident_Dataset_Fall_Lying_Down_Detection) | kaynakta | — | — |
| `ppe/hard_hat/` | **Hard Hat Detection** (19.745 görsel) | [keremberke/hard-hat-detection](https://huggingface.co/datasets/keremberke/hard-hat-detection) | **CC BY 4.0** | ✅ | ✅ |
| `ppe/construction_safety/` | **Construction Safety** (398 görsel, 17 sınıf) | [keremberke/construction-safety-object-detection](https://huggingface.co/datasets/keremberke/construction-safety-object-detection) | **CC BY 4.0** | ✅ | ✅ |
| `yelek_yolo/` | **hi-vis yelek** (gsnvb türevi) | [LibreYOLO/construction-safety-gsnvb](https://huggingface.co/datasets/LibreYOLO/construction-safety-gsnvb) | **CC BY 4.0** | ✅ | ✅ |
| `ppe_yolo/` | KKD YOLO eğitim derlemesi | yukarıdaki iki CC BY 4.0 setten türetildi | CC BY 4.0 | ✅ | ✅ |
| `isafety_bench/` | **iSafetyBench** (1.100 klip) | [raiyaanabdullah/isafety-bench](https://huggingface.co/datasets/raiyaanabdullah/isafety-bench) · [github.com/iSafetyBench/data](https://github.com/iSafetyBench/data) · makale [arXiv:2508.00399](https://arxiv.org/abs/2508.00399) | **CC BY-NC-SA 4.0** | ❌ **YASAK** | ❌ |
| (aday, alınmadı) | Mendeley PPE `8vf7z6v5sb` | [data.mendeley.com/datasets/8vf7z6v5sb](https://data.mendeley.com/datasets/8vf7z6v5sb) | — | — | — |

### Üretilenler — indirmeye gerek yok

| dizin | nasıl üretilir |
|---|---|
| `eval_kanonik/`, `eval_full/` | `scripts/eval_kanonik_kur.py`, `scripts/eval_full_kur.py` (tesis verisinden, **internetsiz**) |
| `eval_genelleme/` | `scripts/eval_genelleme_kur.py` (iSafetyBench'ten, **internetsiz**) |
| `sample_data/`, `test_clip.mp4` | `scripts/make_test_video.py` — sentetik, internetsiz |
| `robust/` | bozuk/boş/minik test klipleri — depoda üretilir |
| `temporal/` | mevcut kliplerden birleştirilmiş pencere testleri |

---

## Dikkat edilecekler

**iSafetyBench — eğitimde KULLANILAMAZ.** CC BY-NC-SA 4.0; ShareAlike ince ayar
ağırlıklarını türev eser yapabilir. `dilajan/veri_lisans.py` bunu **kod düzeyinde**
zorluyor (fail-closed) — yanlışlıkla eğitime sokarsanız kod durur.
Ayrıntı: `data/isafety_bench/NOKULLAN_EGITIM.md`

**Sızıntı — birlikte raporlanmaması gerekenler** (`data/EVAL_SETS.md` §K9):

| birlikte raporlanamaz | neden |
|---|---|
| `eval` + `eval_big` | `eval`, `eval_big`'in **%100 alt kümesi** |
| `eval` + `eval_holdout` | 15/31 klip ortak (%48) |

`eval_tune` ↔ `eval_holdout` ayrıktır (MD5 kesişimi 0) — ayar `tune`'da, son ölçüm
`holdout`'ta yapılır.

**Alan farkı.** KKD setleri **şantiye** görüntüsüdür; dağıtım ortamımız **üretim
tesisi**. iSafetyBench **YouTube** kaynaklıdır. Bu setlerden çıkan sayılar
*genelleme stres testidir*, aynı-alan kanıtı değildir.

**Elenmiş adaylar — tekrar önerilmesin** (`docs/isg_veri_envanteri_2026-08-16.md`):
SH17 (CC BY-NC-SA, alan eşleşmesi en iyisiydi) · VFP290K (GPL-3.0) ·
Ultralytics Construction-PPE (AGPL-3.0) · Aerial-PPE (CC BY-NC-ND) ·
Forklift-Loading setleri (CC BY-NC-SA).

---

## Dışarıda bırakılan: Eskişehir OSB tesis videoları

`industrial/` ve ondan türeyen `eval_defense/`, `eval_defense_v1/`, `eval_full/`,
`eval_kanonik/`, `eval_holdout/`(kısmen), `eval_tune/`(kısmen), `ppe_tesis_etiket/`.

- 691 klip, 1920×1080, 24 fps · Eskişehir OSB'de bir üretim tesisi, 2 IP kamera,
  5 Kasım – 13 Aralık 2022
- Akademik kaynağı **vardır**: Mendeley Data DOI [`xjmtb22pff`](https://data.mendeley.com/datasets/xjmtb22pff),
  kuran betik `scripts/get_industrial.py`
- Lisans **çelişkili**: Mendeley API `CC BY 4.0` diyor, Data in Brief makalesi
  `CC BY-NC`. Depoda **muhafazakâr okuma** benimsendi: CC BY-NC (ticari kullanım yok,
  atıf zorunlu). Bkz. `docs/veri_lisans_karari.md`
- **Baytları yeniden yayımlanmaz**: tanınabilir çalışanların işyeri gözetim
  görüntüsüdür (KVKK). Telif serbest olsa da bu ayrı bir yükümlülüktür.

Sınıf eşlemesi ve dosya adı biçimi: `data/industrial/CLASSES.md`
