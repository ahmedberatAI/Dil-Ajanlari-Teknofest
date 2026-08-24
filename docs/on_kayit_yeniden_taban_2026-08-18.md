# ÖN-KAYIT — düzeltilmiş kodla YENİDEN TABAN ölçümü (D38)

**Koşumdan ÖNCE yazıldı.** Eşikler sonradan değiştirilmeyecek.

## Neden gerekli

D36'da boru hattını etkileyen **iki gerçek hata** düzeltildi:

1. **`"olu"` alt-dizgisi** (`graph.py` `_calibrate_severity`) — KRITIK listesinde kelime
   sınırı olmadan duruyordu; `yolu` / `oluşumu` / `oluyor` içinde eşleşiyordu.
   Ölçülmüştü: 11 olay **yalnızca bu yüzden** Kritik'e zorlanmış, **8'i "yaya yolu"**
   içeriyordu — yani hata tam da hedef İSG sınıfını vuruyordu.
2. **Türkçe büyük-İ** (`_PERSON_RE`, `_is_person_fall_event`, `_calibrate_severity`) —
   `"İşçi".lower()` = `i`+U+0307, regex `işçi` ile eşleşmiyordu. Ölçülmüştü:
   **267 olay metninin %13,5'i (36 olay)** kişi tespitini kaçırıyordu.

**Arşivdeki tüm eval_defense sayıları bu iki hata AKTİFKEN ölçüldü.** Düzeltilmiş kod
bu sette **hiç koşulmadı**. Dolayısıyla raporladığımız taban çizgisi (recall 0,283 ·
MCC +0,079) **geçerliliğini yitirmiş durumda**.

## Kollar

| kol | ne |
|---|---|
| **ESKİ** | arşiv — `eval_20260816_111114` + `_113306` (hatalı kod, 200 klip) |
| **YENİ** | bugünkü kod, temiz set (197 klip), varsayılan yapılandırma |

⚠️ İki kol **iki bakımdan** farklı: (a) kod düzeltmeleri, (b) 3 çelişkili klip
çıkarıldı. Bu yüzden karşılaştırma **arşivin 197'ye indirgenmiş hali** ile yapılacak
(bu GPU'suz hesaplanabiliyor, D36'da yapıldı: MCC +0,0693 → **+0,0793**).

## Beklenti (koşumdan önce yazılıyor — sonradan uydurmamak için)

Her iki hata da **severity** katmanındaydı, **tespit** katmanında değil. Dolayısıyla:

| metrik | beklenti | gerekçe |
|---|---|---|
| recall (≥1 olay) | **~değişmez** | hatalar olay ÜRETİMİNİ etkilemiyordu |
| severity dağılımı | **değişir** | `"olu"` sahte Kritik üretiyordu → azalmalı |
| risk ≥ Yüksek | **artabilir** | İ hatası kişi-düşmesi yükseltmesini engelliyordu |
| tespit MCC | **belirsiz** | iki hata zıt yönlerde çalışıyordu |

Beklenti tutmazsa bu **kayda geçirilecek**, gizlenmeyecek.

## Raporlanacak metrikler (hepsi YAN YANA — tek metrik yeter tuzağı yok)

- `recall` (≥1 olay) — ⚠️ doğru tehlike olmasını GEREKTİRMEZ
- `hassasiyet`, **tespit MCC**, `F2`
- `category_match` (D28 kapısı) **ve** `category_match_onarik` (onarık kapı)
- **`isg_match`** — sınıfa özgü kalıp + onarık kapı (**asıl yetenek ölçütü**)
- `risk ≥ Yüksek` ayırt etmesi (anomali vs normal) + **sevk kapısı MCC**
- medyan gecikme
- **koşum künyesi** (model, bayraklar, sıcaklık) — artık her arşive yazılıyor

## Koşum

```bash
DILAJAN_EVAL_DIR=data/eval_defense EVAL_CATS=Anomali DILAJAN_TEMPERATURE=0 python benchmark/eval_clips.py
DILAJAN_EVAL_DIR=data/eval_defense EVAL_CATS=Normal  DILAJAN_TEMPERATURE=0 python benchmark/eval_clips.py
```
