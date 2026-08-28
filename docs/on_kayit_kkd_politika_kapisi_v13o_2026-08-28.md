# v13o KKD politika kapısı — ön kayıt

Tarih: 2026-08-28

## Hipotez

Görsel ekipman yokluğu, ekipmanın o tesiste zorunlu olduğu anlamına gelmez.
Serbest anlatı veya kapalı-aile scout KKD eksikliği seçse bile olay yalnız
operatörün `facility_rules` / `facility_policy` beyanında açık baret/yelek
zorunluluğu varsa ya da ilgili uzak/yerel KKD kiti bilerek etkinleştirildiyse
üretilebilir. Varsayılan `ppe_kits` tek başına beyan değildir.

## Sabit karar

- Desteklenen kalemler yalnız baret ve yelektir.
- Eldiven, gözlük, maske ve benzeri spekte olmayan birleşik iddialar fail-closed.
- Beyan yoksa atomik API doğrulaması dahi çağrılmaz.
- KKD dışındaki olay aileleri değişmez.
- Üretim varsayılanları ve sabit üç model aliası değişmez.

## Kabul kapıları

- Modelsiz testler: beyansız KKD ret; açık baret zorunluluğu + görsel destek
  kabul; “zorunlu değildir” ret; birleşik desteklenmeyen kalem ret; kapalı scout
  beyansızken atomik çağrı yok.
- v13 dev'deki `MEEGwePfDgM_trim_23.mp4`, boş tesis politikasıyla KKD olayı
  üretmemeli.
- Açık politika içeren sentetik yapısal yol geriye dönüşü korumalı.
- v13 holdout açılmaz.
