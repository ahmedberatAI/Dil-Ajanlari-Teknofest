# GitHub Yükleme ve Açık Kaynak Rehberi

Şartname gereği proje, yarışma bitiş tarihinde **Apache License 2.0** ile, **`BilisimVadisi2026`**
etiketiyle GitHub'da açık kaynak paylaşılmalı; **"Türkiye Açık Kaynak Platformu"** etiketlenmeli;
depo, çalıştırma adımlarını + tüm bağımlılıkları + veri setinin herkese açık linkini içermeli.
En az **haftalık** güncelleme (commit) zorunlu.

## 1) Organizasyon ve depo
```bash
# GitHub'da: New organization (örn. takım adınız) -> New repository (public)
cd /mnt/c/Users/omen/Desktop/DilAjanlariTeknofest
git init
git add .
git commit -m "İlk sürüm: yerel video analiz ve karar destek ajanı"
git branch -M main
git remote add origin https://github.com/<ORG>/<REPO>.git
git push -u origin main
```
> `.gitignore` zaten `data/`, `.venv/`, model dosyalarını hariç tutuyor — büyük dosyalar gitmez.

## 2) Lisans
`LICENSE` (Apache 2.0) depoda mevcut. GitHub bunu otomatik tanır.

## 3) Etiketler (Topics)
Depo sayfası → ⚙ (About) → Topics:
- `BilisimVadisi2026`
- ayrıca takım adınız ve `teknofest`, `tyda`, `video-analysis`, `llm-agent` gibi konular.

"Türkiye Açık Kaynak Platformu"nu README'de ve (varsa) yükleme duyurusunda etiketleyin/bahsedin.

## 4) README kontrol listesi (şartname zorunlulukları)
- [x] Çalıştırma adımları (kurulum + komutlar) — `README.md`
- [x] Tüm bağımlılıklar — `requirements.txt` + `requirements-lock.txt`
- [x] Veri setinin herkese açık indirme linki — `data/README.md` (UCF-Crime HF mirror)
- [x] Mimari diyagramı — `docs/architecture.md`
- [x] Kullanılan agentic framework + LLM — README/architecture
- [x] KPI / ölçümleme sonuçları — `benchmark/`

## 5) Haftalık güncelleme
Her hafta en az bir anlamlı commit:
```bash
git add -A && git commit -m "Haftalık güncelleme: <kısa açıklama>" && git push
```
Geliştirme günlüğünü kısa tutmak için commit mesajlarını anlamlı yazın.

## 6) Sunum & demo yükleme
Jüriye sunulan slaytlar (PDF + PPTX) ve demo videosu da depoya/uygun yere yüklenmeli
(şartname: sunumu GitHub hesabına yükleme zorunlu).

## 7) İntihal / özgünlük
Başvuru dosyası Turnitin'e yüklenecek. Tüm kod özgün ve yarışma döneminde üretilmiş;
üçüncü taraf kod parçaları kaynak gösterilmeli.
