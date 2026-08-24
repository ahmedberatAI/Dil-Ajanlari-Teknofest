# Skorlarımız — ölçülmüş durum (18 Ağustos 2026)

Bu belge **sunuma girecek sayıları** ve **girmemesi gerekenleri** ayırır.

---

## ⛔ ÖNCE: RAPORLANMAYACAK İKİ METRİK

`eval_defense` üzerinde **aynı yapılandırmanın üç koşusu**:

| koşu | recall | tespit MCC |
|---|---|---|
| 16 Ağu A | %28,3 | +0,0793 |
| 16 Ağu A′ | %19,2 | — |
| 18 Ağu | %16,2 | **−0,1035** |

**`recall` 12 puan, `tespit MCC` 0,18 salınıyor** — model, ayar ve sıcaklık aynı.
Sebep HANDOFF §11'de zaten açık kusur olarak duruyordu (*"`temperature=0` yeterli
değil, toplu-işlem boyutu sabitlenmeli"*); bugün **niceliği** ölçüldü.

→ Bu iki metrik **hiçbir kararda ve hiçbir slaytta** tek başına kullanılmaz.

**Kararlı olan:** aynı iki koşuda `özgül` sütunu **birebir aynı** çıktı
(1 TP / 2 FP / −0,0421). Karar metriği budur.

---

## 1. İSG tespiti — `eval_defense` (197 klip, gerçek fabrika CCTV)

**En zorlu setimiz. Burada zayıfız ve nedenini ölçtük.**

| yapılandırma | özgül TP | özgül FP | özgül MCC | isabet% |
|---|---|---|---|---|
| **varsayılan (dağıtımdaki)** | **1**/99 | 2/98 | −0,042 | %4-6 |
| `facility_rules` açık | **16**/99 | 23/98 | −0,092 | **%35** |
| İSG merceği açık | 10/99 | 7/98 | **+0,053** | %23 |
| Qwen3.8-27B | 0/99 | 1/98 | −0,072 | %0 |

*isabet% = olay üreten kliplerin yüzde kaçı doğru tehlikeyi adlandırdı*

### Neden bu kadar zor — ölçülmüş üç sebep

1. **`Opened_Panel_Cover` görsel olarak çözümsüz.** class2 (GÜVENSİZ) ve class5
   (GÜVENLİ) **ikisinde de pano açık**; fark yetkili kişinin varlığı. Ölçümle
   doğrulandı: `2_tr104` klibi **bütünüyle** `5_te5`'in içinde. 8 sınıfın 2'si
   yapısal olarak ayrılamaz.
2. **Sinyal zayıf.** AUC(aynı etiket) = **0,538** — Anomali ve Normal görsel olarak
   ayrışmıyor. Fark gerçekten davranışsal.
3. **Etiket şeması tek etiketli**, klipler çok tehlikeli. Kaynak veri setinde bile
   aynı video iki sınıf altında (26 mükerrer grup).

---

## 2. Genel anomali tespiti — güçlü olduğumuz yer

| set | n | recall | kategori |
|---|---|---|---|
| `eval_scenario` | 25 | **%96** | **%96** |
| `eval_holdout` | 24 | **%96-100** | %38-50 |

Kaza, düşme, yangın, kavga gibi **belirgin olaylarda sistem çalışıyor**.
Zayıflık ince İSG davranış ayrımına özgü.

---

## 3. Model yeteneği — iSafetyBench MCQ (bağımsız set)

| kol | doğruluk | %95 GA | n | şans |
|---|---|---|---|---|
| hazard | **%55,3** | %47–%63 | 150 | %6,25 |
| normal | %48,7 | %41–%57 | 150 | %6,25 |

**Şansın ~9 katı.** Model tehlikeyi doğrudan sorulduğunda tanıyor.
⚠️ Alan uyarısı: YouTube kaynaklı, bizim ortam sabit-kamera CCTV → **genelleme
stres testi**, aynı-alan kanıtı değil.

---

## 4. KKD dedektörleri (YOLO11n, kendi eğitimimiz)

| model | test mAP50 | precision | recall |
|---|---|---|---|
| `yolo11n-ppe` (baret) | **0,934** | 0,893 | 0,891 |
| `yolo11n-yelek` | **0,905** | **0,898** | 0,783 |

⚠️ **Tesiste doğrulanmadı — ve ölçüm bunu gösteriyor:**
`ppe_tesis_kontrol`: Anomali kolunda **0/20** tetikleme, Normal kolunda 1/20.
Yani şantiyede eğitilen dedektör, üretim tesisinde **neredeyse hiç ateşlemiyor**.
Görsel denetimde sebebi görüldü: dedektör yeleği doğru buluyor ama **yeleksiz
kişiyi bulmuyor**. Bu yüzden `ppe_dispatch` **kapalı**.

---

## 5. Otonomi / diyalog (şartname %20)

| | görev | doğallık |
|---|---|---|
| tek-tur (n=10, tuzaklı) | 5,00/5 | 5,00/5 |
| çok-tur (n=5) | 5,00/5 | 5,00/5 |
| tuzağa düşülen | **0/15** | |

Gürültü tabanı **0** (T=0'da A vs A′ **15/15 birebir**).

⚠️ **Bu sayı tek başına verilmemeli.** LLM hakemi **üç kez** açık kusuru 5/5
puanladı (prompt sızıntısı, tekrar döngüsü, tuzağa taviz). Sunumda **örnek
diyalog** gösterilmeli.

**Ölçülmüş ve düzeltilmiş gerçek kusur:** asimetrik itaat — operatör yanlış bir şey
*eklerse* reddediyordu (5/5), doğru bir şeyi *küçümserse* uyuyordu (1/5).

---

## 6. Sistem / mimari

| | |
|---|---|
| Gecikme (8B) | **~12 sn/klip** (27B: 23 sn) |
| Çıktı sözleşmesi K1 | tam 4 anahtar, testle kilitli |
| Hazırlık kontrolü | **24/24** |
| Test paketi | **20 dosya**, hepsi geçiyor |
| Lisans kapısı | fail-closed, test edildi |
| Tamamen yerel | dış API yok |

---

## Dürüst özet

**Güçlü:** genel anomali tespiti (%96) · Türkçe akıcılık · model yeteneği (MCQ 9× şans) ·
KKD dedektörleri (mAP 0,90+) · diyalog/otonomi · ölçüm disiplini ve mimari.

**Zayıf:** ince İSG davranış sınıflandırması — varsayılan yapılandırmada **1/99**.

**Ama:** elimizde bunu **16/99**'a çıkaran (`facility_rules`) ve **özgül MCC'yi tek
pozitif değere** taşıyan (İSG merceği) iki ayar var ve **ikisi de kapalı**.
Kapalı olmalarının sebebi ölçüm aletinin bozukluğuydu — bugün düzeldi.

**Sıradaki hamle:** birleşik kolu ölç, kazananı dağıt.
