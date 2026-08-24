# ÖN-KAYIT — birleşik dağıtım kolu (D38-B)

**Koşumdan ÖNCE yazıldı.**

## Neden bu koşum

Varsayılan dağıtım yapılandırması `isg_özgül = 1/99` veriyor. Elimizde bunu
belirgin biçimde yükselten **iki ayar var ve ikisi de KAPALI**:

| kol | özgül TP | özgül FP | özgül MCC | isabet% |
|---|---|---|---|---|
| varsayılan | 1 | 2 | −0,042 | 4-6% |
| `facility_rules` | 16 | 23 | −0,092 | 35% |
| `isg_lens` | 10 | 7 | **+0,053** | 23% |

Bu koşum ikisini **birlikte** ölçer.

## Birincil ölçüt DEĞİŞTİ — gerekçesiyle

Önceki ön-kayıtlar `tespit MCC`'yi birincil almıştı. **O metrik bu sette
ölçülemez olduğu bugün kanıtlandı:** aynı yapılandırmanın iki koşusu
**+0,0793** ve **−0,1035** verdi (0,18 salınım). Aynı iki koşuda `özgül`
sütunu **birebir aynı** çıktı (1 TP / 2 FP / −0,0421).

→ Birincil ölçüt: **özgül MCC**. `recall` ve `tespit MCC` raporlanır ama
**karar verMEZ** (gürültü-baskın oldukları kayda geçti).

## Eşikler (mekanik uygulanacak)

| karar | koşul |
|---|---|
| **DAĞIT** | özgül MCC ≥ **+0,05** (mercek tek başına bu değerde) **ve** özgül FP ≤ **12** |
| **RET** | özgül MCC < 0 **veya** özgül FP > 20 (`facility_rules` tek başına 23'tü) |
| **BELİRSİZ** | arada → mercek TEK BAŞINA dağıtılır (tek pozitif özgül MCC'ye sahip kol) |

Ek koruma: medyan gecikme > 2× ise (23 sn) RET — K4.

## ⚠️ Bilinen çekince (sonucu yorumlarken unutma)

Karşıtsal denetim, `ISG_LENS_SUFFIX`'in skorlayıcının aradığı kalıpları
içerdiğini buldu. `isg_match` sözcüksel bir eşleştirici → **özgül kazancın bir
kısmı metrik oyunu olabilir.**

Ayırt edici işaret: saf gaming'de TP ve FP **orantılı** artar. Mercek tek başına
10 TP / 7 FP verdi (oran lehte), `facility_rules` 16/23 (oran aleyhte). Birleşik
kolda FP oransal olarak TP'den hızlı artarsa **gaming lehine kanıt** sayılacak.

## Koşum

```bash
DILAJAN_ISG_LENS=true DILAJAN_FACILITY_RULES="<tesis kurallari>" \
DILAJAN_EVAL_DIR=data/eval_defense DILAJAN_TEMPERATURE=0 python benchmark/eval_clips.py
```
