# Yelek dedektörü — TESİS görsel denetimi (D36)

**Yöntem:** `data/ppe_tesis_etiket/yelek/` kontak sayfalarına doğrudan bakılarak.
Yanlılık disiplinine uyuldu: önce **`__kutusuz`** sayfaya bakılıp karar verildi,
sonra `__kutulu` sayfa yalnızca **hata analizi** için açıldı.
**Kapsam:** 24 klipten **4'ü** denetlendi (A_ihlal 2, B_kaideli 2). Kalan 20 hazır.

---

## 🔴 BULGU 1 — dedektörün kusuru PRECISION'da değil, RECALL'da

`B_kaideli/5_te1`, dedektör kararı: **"5 yelekli kutu, 0 yeleksiz → ihlal_yok"**

Kutusuz sayfada gördüğüm: **tek bir hi-vis yelekli işçi** + **3-4 koyu üniformalı işçi**.

Kutulu sayfada görülen: beş `yelek_var` kutusunun **hepsi AYNI tek kişide**
(farklı karelerde, güven 0,47 · 0,48 · 0,61). Yani "5 yelekli kişi" yok,
**1 kişi 5 karede sayılmış**.

Ve kritik olan: **koyu üniformalı 3-4 işçiye HİÇ kutu çizilmemiş.**
`yelek_yok` sınıfı onlarda **hiç tetiklenmemiş**.

| | |
|---|---|
| İnsan kararı (ground truth) | **yeleksiz kişi VAR → EVET** |
| Dedektör kararı | ihlal_yok |
| Sonuç | ❌ **KAÇIRMA (yanlış-negatif)** |

**Teşhis:** Dedektör parlak yeleği doğru buluyor, ama **yeleksiz insanı bulmuyor.**
Muhtemel sebep: tepeden çekimde, koyu makine zemininde, koyu iş üniforması giymiş
kişide **insan tespitinin kendisi** başarısız oluyor.

### Bunun anlamı — güvenlik açısından iyi, fayda açısından kötü

Kaçırma yönünde hata, yanlış alarm yönünde hataya göre **daha güvenli** bir arıza
modudur (operatörü boşuna meşgul etmez). Ama `ppe_dispatch`'i açmanın gerekçesi
"ihlalleri yakalasın"dı — yakalamıyorsa **açmanın değeri düşük**.

---

## BULGU 2 — A_ihlal kovasında dedektör HAKLI

| klip | dedektör | insan kararı | sonuç |
|---|---|---|---|
| `A_ihlal/1_tr67` | IHLAL (2 yeleksiz, 1 yelekli) | **EVET** — birden fazla yeleksiz kişi, arkada tek yelekli | ✅ doğru |
| `A_ihlal/2_tr35` | IHLAL | **EVET** — yeleksiz oturan operatör + yeleksiz yürüyen kişi | ✅ doğru |

İncelenen 2/2'de yanlış alarm yok. **Precision umut verici** (ama n=2, hiçbir şey ispatlamaz).

---

## 🔴 BULGU 3 — daha derin sorun: "yeleksiz" bu tesiste ihlal MI?

İncelenen tüm kliplerde tesisin **standart kıyafeti koyu iş üniforması** (lacivert,
firma logolu, kırmızı şeritli). Hi-vis yelek **istisna** — yalnızca belirli
kişilerde görülüyor (`5_te1`'de bakım yapan işçi, `5_te6`'da müdahale eden işçi).

Yani yelek bu tesiste **herkese zorunlu bir KKD değil**, muhtemelen belirli
görevlere özgü. Bu durumda:

> **"Yeleksiz kişi var" ≠ "İSG ihlali var".**

Dedektör teknik olarak doğru çalışsa bile, ölçtüğü şey bu tesiste bir ihlal
olmayabilir. `ppe_dispatch`'i açmadan önce **tesisin yelek politikası** bilinmeli —
bu bir model sorunu değil, **kapsam tanımı** sorunudur.

---

## Karar

| soru | cevap |
|---|---|
| Yelek dedektörü tesiste çalışıyor mu? | **Kısmen** — yeleği bulur, yeleksizi bulmaz |
| `ppe_dispatch` açılmalı mı? | **HAYIR** — kaçırma oranı yüksek ve "yeleksiz = ihlal" varsayımı doğrulanmamış |
| Veri eksik mi? | **Hayır** — 24 kliplik paket yeterli, 4'ü denetlendi |
| Sonraki iş | Kalan 20 klibi denetle → precision/recall sayısal ölç; ayrıca tesis yelek politikasını netleştir |

## Yan kusur — üreteç hatası

`data/ppe_tesis_etiket/yelek/etiket_sablonu.csv` **baret** sütun adlarını kullanıyor
(`dedektor_baretsiz_kutu`, `insan_baretsiz_kisi_VAR_MI`) oysa bu **yelek** paketi.
`scripts/ppe_etiket_hazirla.py --kit yelek` çağrısında sütun adları kit'e göre
üretilmiyor. Etiketleyeni yanıltır; düzeltilmeli.
