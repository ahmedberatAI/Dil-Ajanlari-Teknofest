# ÖN KAYIT — Olay adı paneli (aşama 1: arşiv tekrarı)

Tarih: **2026-08-27**, koşumdan **ÖNCE**. Dal: `d34-isg-veri-kkd`

## 0. Soru

Boru hattımızın ürettiği **Türkçe metin**, doğru olay adını seçmeye yetiyor mu?

Bugün ölçüldü: metin doğru tehlikeyi **anlatıyor** ama **adı kayboluyor**.
> *"…şiddetli alev ve yoğun siyah duman çıkışı ile yangın oluştu"* → kategori **Güvenlik**

Bu aşama **model çağrısı olmadan** A kolunu, tek metin çağrısıyla B kolunu üretir.
Video yeniden işlenmez. Amaç: 80 dakikalık canlı koşuma girmeden **yola değer mi**
sorusunu yanıtlamak.

## 1. Veri

`benchmark/results/eval_20260825_195405.json` (eval_genelleme, sevk yapılandırma,
alan kilidi AÇIK). Yer gerçeği `data/isafety_bench/annotations/mcq/hazard_mcq_single.json`.
**50/50 klip eşleşiyor** (doğrulandı). Örneklem yok — arşivin tamamı, cherry-pick imkânsız.

## 2. MENÜ — donduruldu

16 yaprak + kaçış:

```
A Yangın                B Duman veya patlama       C Yüksekten düşme
D Yükün düşmesi         E Yapısal çökme            F Vinç denge kaybı
G Araç kontrol kaybı    H Araç çarpması            I Makineye kapılma
J Sıkışma veya ezilme   K Ağır cisim kayması       L Raf devrilmesi
M Kaldırma platformu hatalı kullanımı              N Forklift kullanım hatası
O Kavga veya saldırı    P Kasıtlı hasar (vandalizm)
Q LİSTEDE YOK
```

Yaprak→GT haritası `scratchpad/menu_kapsam.py` içinde donduruldu.

## 3. MENÜ KAPSAM TAVANI — koşumdan ÖNCE ölçüldü

| | |
|---|---|
| birincil GT yaprakla ifade edilebilen | **42/50 = %84,0** |
| birincil veya diğer etiketlerden biri | 44/50 = %88,0 |

Kapsanmayan 6 klip: `moving in a suspicious manner`(2) · `watching incident
passively`(2) · `escaping from danger` · `police search` · `rescue effort` ·
`tree falling nearby` — hepsi **insan tepkisi veya tehlike olmayan** etiketler.

**Bu sayı önce ölçüldüğü için hüküm netleşir:** tavan %84 ≥ %70 olduğundan,
düşük top-1 çıkarsa darboğaz **menü değil SEÇİMDİR**.

## 4. KOLLAR

| kol | ne | model çağrısı |
|---|---|---|
| **A** sözcüksel | mevcut arşiv metninde yaprağın anahtar kelimesi geçiyor mu | **YOK** |
| **B** panel | aynı metin → kapalı seçim (`structured_outputs.choice`, harf, `temperature=0`, `logprobs`) | 50 |
| **C** bilgisiz kontrol | sabit, bilgi içermeyen metin → aynı menü | 50 |

A ve B **aynı metni** görür — fark yalnızca çıkarma yöntemidir.
C, skorun metinden mi yoksa modelin ön yargısından mı geldiğini ayırır.

## 5. KABUL ÖLÇÜTLERİ — mekanik

```
G1  B top-1 >= %40,0          (yayimlanmis en iyi tek-etiketli hazard tabani ~%40,3)
G2  B - A >= +12,0 MUTLAK PUAN
G3  McNemar exact p < 0,05    (n=50, eslesmis, ayni klipler, ayni metin)
G4  C (bilgisiz) <= %8,0
DORDU DE saglanmazsa AŞAMA 2'YE GECILMEZ.
```

## 6. VAZGEÇME

```
B top-1 < %40,0                    -> VAZGEC
B - A < +12,0 VEYA McNemar p>=0,05 -> VAZGEC
C > %8,0                           -> skor metinden degil PRIOR'dan; VAZGEC
"LISTEDE YOK" orani > %60          -> menu alani kapsamiyor; VAZGEC
tek yapragin payi > %60            -> dejenere; VAZGEC
```

## 7. ZORUNLU RAPOR

Karışıklık matrisi · her yaprağın payı · "LİSTEDE YOK" oranı · McNemar b/c
hücreleri · Wilson %95 GA · geniş ölçüt (`other_gt_actions` dahil) ayrıca.

Bu aşama **hiçbir kodu değiştirmez**; yalnız ölçer. Sonuç ne çıkarsa yazılır,
eski skorlar silinmez.
