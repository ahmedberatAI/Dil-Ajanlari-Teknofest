# ÖN KAYIT — kaynak setin TAMAMINDA ölçüm (691 klip)

Tarih: **2026-08-25**, koşumdan **ÖNCE**. Dal: `d34-isg-veri-kkd`

## 0. Neden

Bugüne kadarki bütün ölçümler `data/eval_defense` üzerinde yapıldı: **197 klip**,
kaynak setin **%29'u**. Yaya yolu sınıfında oran daha da düşük: **25/210 (%12)**.

Kalan üç sorunun **üçü de örnekleme bağlı**:

| sorun | mevcut n | tam settek n |
|---|---|---|
| sınıf başına 24-25 ihlal klibi → Wilson aralıkları geniş | 197 | **691** |
| yaya yolu çift içi çerçeve karıştırıcısı %72,9 | 48 | **285** |
| yelek kuralının kamera tabanına marjı +0,040 | 50 | **146** |

Kaynak: `data/industrial` — Mendeley `xjmtb22pff`, **CC BY 4.0**. Eğitim ve
değerlendirme serbest (`dilajan/veri_lisans.py` yalnız iSafetyBench'i kısıtlar).
Baytlar KVKK gereği yeniden yayımlanmaz; `data/eval_full` yalnızca sembolik bağ.

Sınıf eşlemesi `data/industrial/CLASSES.md`'de **iki bağımsız kaynakla
doğrulanmış** durumda (Mendeley API klip sayıları + Data in Brief makalesi, 8/8).

## 1. Koşum

`DILAJAN_EVAL_DIR=data/eval_full` · 691 klip · `slot_guven=1` ·
`facility_rules` **KAPALI** (bugün reddedildi) ·
slotlar: üç sevk slotu **+ iki yaya slotu** (`yaya_zemin`, `yaya_cizgi_mesafe`).

Yaya slotlarını dahil etmenin maliyeti sıfır: bulaşma kapısı bugün ölçüldü ve
üç sevk matrisi **birebir** korundu (düşüş 0,000). Çevrimdışı puanlayıcı üç
sevk kuralını slot dağılımlarından hesapladığı için replikasyon sorusu
etkilenmez, üstüne yaya sınıfı da 285 klipte ölçülmüş olur.

## 2. SORULAR ve ÖLÇÜTLER

### S1 — REPLİKASYON (birincil)
Üç sevk kuralı 3,5 kat veride ayakta kalıyor mu?

| kural | 197 klipte | **tam sette KABUL** |
|---|---|---|
| `Opened_Panel_Cover` | +0,960 | MCC ≥ **+0,81** |
| `Carrying_Overload_with_Forklift` | +0,881 | MCC ≥ **+0,73** |
| `Unauthorized_Intervention` | +0,689 | MCC ≥ **+0,54** |

Eşik = sevk değeri − **0,15**. Altına düşen bir kural, sevk edilen skorunun
**örnekleme özgü** olduğunu gösterir ve bu açıkça raporlanır.

### S2 — MARJ (bugünkü en zayıf nokta)
Her kural, **aynı tam set üzerinde ölçülen** kendi çerçeve tabanını
en az **0,05** aşmalı. Yelek kuralının 50 klipteki marjı +0,040 idi; asıl
sorulan soru bu marjın 146 klipte ayakta kalıp kalmadığıdır.

Çerçeve tabanı: kişiler maskelenmiş arka plandan leave-one-out
en-yakın-merkez sınıflandırıcı — bugünkü yöntemin **aynısı**.

### S3 — YAYA YOLU (285 klip)
Kapanış belgesinin ölçütü **değiştirilmeden** devralınıyor:
çift içi MCC ≥ **+0,45** VE saha kesinliği ≥ **0,237**.
Ek olarak: çift doğruluğu, aynı sette ölçülen çerçeve tabanını ≥ 0,05 aşmalı.

## 3. ÖN-RET KAPILARI

| # | kapı |
|---|---|
| a | **KAYNAK AYRIMI** — `_tr`/`_te` ayrımı bozulmayacak; her sonuç ikisinde AYRI raporlanacak. Aralarında büyük fark çıkarsa aşırı uyum şüphesi yazılır. |
| b | **SIZINTI** — `sizinti_celiskili` bayrağı taşıyan klipler ayrıca raporlanır; oranı %5'i aşarsa ölçüm şüpheli işaretlenir. |
| c | **DENGESİZLİK** — tam set dengesiz (ör. yaya çiftinde 210/75). MCC dengesizliğe duyarlıdır; bu yüzden **dengeli alt-örneklem** ile de raporlanacak (tohumlu, 5 tekrar). |

## 4. Ne olursa ne yapılacak

| sonuç | eylem |
|---|---|
| S1 geçer | sevk edilen skorlar 3,5 kat veride **teyitli** olur; sunumda n=691 verilir |
| S1 kalır | ilgili kuralın skoru "örnekleme özgü" diye işaretlenir, sevk kararı gözden geçirilir |
| S2 kalır (yelek) | yelek kuralının kamera tabanını aşmadığı **açıkça** raporlanır — bugünkü en zayıf noktanın teyidi |
| S3 geçer | yaya yolu sınıfı açılır; `isg_match` gerçek bir kazanç alır |
| S3 kalır | on üçüncü ret; sınıf kaynak setin TAMAMINDA da kapalı demektir |

Hiçbir eski skor silinmeyecek. Sonuçlar 197 kliplik değerlerin **yanına**
yazılacak.
