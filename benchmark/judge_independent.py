#!/usr/bin/env python
"""BAGIMSIZ (farkli model ailesi) LLM-as-judge — IKI AYRI metrik ailesi uretir.

E1 (cozulmustu): ureten = puanlayan dongusellıgı. Cozum: farkli aile hakem modeli.

K11 (BU SURUMDE COZULDU) — DAYANAKSIZ HAKEM:
    Onceki surumde hakeme YALNIZCA metin veriliyordu: sistemin KENDI olay listesi +
    sistemin KENDI ozeti. Hakem "ozet, olay listesiyle tutarli mi?" sorusunu yanitliyordu.
    Bu IC TUTARLILIK olcer, VIDEOYA DAYANAKLILIK degil. Kendinden emin bir halusinasyon
    (video ile alakasiz ama kendi icinde tutarli bir anlati) TAM PUAN aliyordu.
    Ozet 4.62 / Aksiyon 4.74 / Risk 5.00 rakamlari bu yuzden paketin en denetlenmemis
    iddiasiydi.

    COZUM — iki metrik ailesi AYRI AYRI raporlanir:

    [A] DAYANAKLI (grounded)  — hakeme klibin BILINEN ground-truth etiketi verilir
        (kategori + anomali/normal; dataset klasor adindan gelir, uydurma degil) ve
        "bu ozet bu etiketle OLGUSAL olarak uyumlu mu? celiski/uydurma var mi?" sorulur.
        Yeni rubrik ekseni: olgusal_dayanaklilik (1-5) + celiski/uydurma bayraklari.
        --> Sistemin ciktisinin DIS gercege uyumunu olcer.

    [B] IC-TUTARLILIK (self-consistency) — eski eksenler (ozet/aksiyon/risk-gerekce).
        KORUNDU ama artik "videoya dayanakli DEGIL" diye ACIKCA etiketlenir.
        --> Yalnizca "sistem kendi ciktisiyla celismiyor mu" sorusunu yanitlar.

    [C] OPSIYONEL GORSEL DAYANAK (--vision / DILAJAN_JUDGE_VISION=1)
        Hakeme klibin birkac KARESI de gonderilir ve ozetin goruntuye sadakati sorulur.
        Cok-modlu hakem modeli + GPU gerektirir; VARSAYILAN KAPALIDIR.

Kullanim (judge modeli vLLM'de servis edildikten SONRA):
    DILAJAN_JUDGE_MODEL=google/gemma-2-9b-it python benchmark/judge_independent.py [eval_xx.json]
    DILAJAN_JUDGE_MODEL=<multimodal> python benchmark/judge_independent.py --vision
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.utils import extract_json  # noqa: E402

try:
    from benchmark.labels import category_from_path, describe, is_anomaly  # noqa: E402
    from benchmark.stats_utils import fmt_rate_dict, mean_sd, rate  # noqa: E402
except ImportError:  # benchmark/ icinden dogrudan calistirma
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from labels import category_from_path, describe, is_anomaly  # type: ignore  # noqa: E402
    from stats_utils import fmt_rate_dict, mean_sd, rate  # type: ignore  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "benchmark", "results")
GT_PATH = os.path.join(ROOT, "benchmark", "ground_truth.json")
JUDGE_MODEL = os.environ.get("DILAJAN_JUDGE_MODEL", "").strip()

SYS = "Sen tarafsiz, titiz bir degerlendirme hakemisin. Yalnizca istenen JSON'u uret."

# Metrik ailesi etiketleri — ciktida hangi metrigin NE oldugu NET gorunsun diye.
T_GROUNDED = "DAYANAKLI (grounded) — klibin BILINEN dataset etiketine karsi olculur"
T_SELF = ("IC-TUTARLILIK (self-consistency) — sistemin KENDI olay listesine karsi olculur; "
          "VIDEOYA DAYANAKLI DEGILDIR")
T_VISION = "DAYANAKLI (gorsel) — klibin gercek KARELERINE karsi olculur"

# ============================================================================
# [A] DAYANAKLI HAKEM — ground-truth etiketine karsi olgusal denetim (K11 cekirdegi)
# ============================================================================
GROUNDED_JUDGE = """Bir video analiz sisteminin urettigi Turkce OZETI, klibin BILINEN
ground-truth etiketine karsi denetleyen tarafsiz hakemsin.

KLIBIN GERCEK ETIKETI (veri setinin yayincisindan gelir, KESIN kabul et):
- Sinif      : {kategori}
- Anlami     : {kategori_tr}
- Durum      : {durum}

SISTEMIN URETTIGI OZET:
"{summary}"

SISTEMIN BILDIRDIGI OLAYLAR:
{events}

GOREV: Ozetin bu ETIKETLE OLGUSAL uyumunu denetle. Dil akiciligi/yazim guzelligi ONEMSIZ.
Yalnizca sunlara bak:
1) Ozet, etiketteki olayi dogru tanimliyor mu?
2) Etiketle CELISEN bir iddia var mi? (or. "Normal" etiketli klipte yangin/kavga iddiasi,
   ya da "Fire" etiketli klipte "olagan faaliyet, sorun yok" demek)
3) Etiketin desteklemedigi SOMUT ayrinti uyduruyor mu? (kisi sayisi, arac plakasi, silah
   turu, yaralanma derecesi, bolum/tesis adi gibi etiketten CIKARILAMAYAN kesin iddialar)

PUANLAMA — olgusal_dayanaklilik (1-5):
5 = etiketle tam uyumlu; uydurma somut ayrinti YOK
4 = uyumlu; kucuk asiri-yorum var ama celiski yok
3 = olay dogru fakat en az bir ONEMLI uydurma ayrinti var
2 = etiketle buyuk olcude celisiyor VEYA etiketteki olayi tamamen kaciriyor
1 = tamamen yanlis/celiskili (or. Normal klipte kritik olay iddiasi)

YALNIZCA JSON:
{{"olgusal_dayanaklilik": n, "celiski": true, "uydurma": true, "gerekce": "tek cumle"}}"""

# ============================================================================
# [C] OPSIYONEL — gorsel dayanak (kare-tabanli). GPU + cok-modlu hakem gerekir.
# ============================================================================
VISION_JUDGE = """Yukarida bir guvenlik kamerasi klibinden zaman damgali ornek KARELER var.
Bir video analiz sisteminin ayni klip icin urettigi Turkce ozet asagida.

SISTEMIN OZETI:
"{summary}"

GOREV: Ozetin GORDUGUN KARELERE sadakatini denetle. Karelerde DOGRULANAMAYAN somut iddialari
"gorulmeyen iddia" say. Karelerin araligi sinirlidir; kareler arasinda olabilecek seyleri
otomatik olarak yanlis sayma — yalnizca karelerle CELISEN veya karelerde hicbir dayanagi
olmayan KESIN iddialari cezalandir.

PUANLAMA — gorsel_sadakat (1-5):
5 = her iddia karelerle uyumlu/desteklenir
3 = ana olay dogru ama dayanaksiz somut ayrinti var
1 = kareler ile acikca celisiyor

YALNIZCA JSON:
{{"gorsel_sadakat": n, "gorulmeyen_iddia": true, "gerekce": "tek cumle"}}"""

# ============================================================================
# [B] IC-TUTARLILIK HAKEMLERI (eski eksenler — KORUNDU, ayri raporlanir)
# ============================================================================
SUMMARY_JUDGE = """Bir video analiz sisteminin urettigi Turkce OZETI degerlendiren tarafsiz hakemsin.

DIKKAT: Asagidaki olay listesi SISTEMIN KENDI ciktisidir, dogrulanmis gercek DEGILDIR.
Bu nedenle burada yalnizca IC TUTARLILIK ve dil kalitesi puanlanir.

Sistemin o videoda tespit ettigini bildirdigi olaylar:
{events}

Uretilen ozet:
"{summary}"

Bu ozeti 1-5 puanla (5 en iyi):
- dogruluk: Ozet, sistemin BILDIRDIGI olaylari sadik/tutarli yansitiyor mu (ic celiski var mi)
- akicilik: Turkce dil bilgisi + akicilik (yabanci kelime/karakter sizintisi varsa dusur)
- ozluluk: Gereksiz tekrar yok, operatorun hizli karar almasini destekler mi
YALNIZCA JSON: {{"dogruluk": n, "akicilik": n, "ozluluk": n}}"""

ACT_JUDGE = """Bir guvenlik operasyon merkezi karar-destek sisteminin urettigi AKSIYON onerilerini degerlendiren tarafsiz hakemsin.
DIKKAT: olay listesi SISTEMIN KENDI ciktisidir; burada IC TUTARLILIK puanlanir.
Tespit edilen olaylar: {events}
Risk: {risk}
Uretilen aksiyon onerileri: {actions}
1-5 puanla: alaka (olay/riskle iliskili mi), uygulanabilirlik (somut/emir kipinde/operatorun yapabilecegi), oncelik (onem sirasi dogru mu), kapsama (kritik olay icin gerekli aksiyon eksik mi).
YALNIZCA JSON: {{"alaka":n,"uygulanabilirlik":n,"oncelik":n,"kapsama":n}}"""

RISK_JUDGE = """Bir risk degerlendirmesinin GEREKCESINI degerlendiren tarafsiz hakemsin.
DIKKAT: olay listesi SISTEMIN KENDI ciktisidir; burada IC TUTARLILIK puanlanir.
Tespit edilen olaylar: {events}
Risk seviyesi: {level}
Risk gerekcesi: "{rationale}"
1-5 puanla: dayanaklilik (gerekce sistemin bildirdigi olaylara dayaniyor mu, ic-celiski yok), tutarlilik (gerekce ile seviye celismiyor mu), eyleme_donukluk (neden-aciliyet veriyor mu).
YALNIZCA JSON: {{"dayanaklilik":n,"tutarlilik":n,"eyleme_donukluk":n}}"""

SINGLE_JUDGE = """Bir guvenlik karar-destek asistaninin verdigi yaniti degerlendiren tarafsiz hakemsin.
Senaryo turu: {stype}
Beklenen davranis: {expected}
Operator mesaji: "{msg}"
Asistanin yaniti: "{resp}"
Asistan beklenen davranisi ne kadar karsiladi? 1-5 (5=tam). YALNIZCA JSON: {{"uygunluk": n}}"""

MT_JUDGE = """Bir guvenlik asistaniyla cok-turlu sohbette asistanin SON yanitini degerlendiren tarafsiz hakemsin.
Su ana kadarki sohbet:
{history}
Operatorun son mesaji: "{msg}"
Asistanin son yaniti: "{resp}"
Beklenen davranis: {expected}
Asistan ONCEKI turlarin baglamini dogru kullandi mi (gonderme/zaman/oz-referans), tutarli ve grounded mi?
1-5 (5=tam). YALNIZCA JSON: {{"uygunluk": n}}"""


# ---------------------------------------------------------------- yardimcilar
def _ask(client: VLMClient, prompt: str, maxt: int = 150, content=None):
    """Hakeme sorar ve JSON sozlugu dondurur; basarisizsa None (FAIL-OPEN)."""
    user = content if content is not None else prompt
    try:
        raw = client.chat([{"role": "system", "content": SYS},
                           {"role": "user", "content": user}],
                          temperature=0.0, max_tokens=maxt)
        obj = extract_json(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _score(client: VLMClient, prompt: str, keys: list, maxt: int = 150) -> list:
    """Verilen eksenlerden 1-5 araligindaki gecerli puanlari toplar."""
    s = _ask(client, prompt, maxt)
    if not s:
        return []
    vals = []
    for k in keys:
        try:
            v = float(s.get(k, 0))
        except (TypeError, ValueError):
            continue
        if 1 <= v <= 5:
            vals.append(v)
    return vals


def _events_text(row: dict) -> str:
    evs = row.get("events", [])
    if not evs:
        return "(olay yok)"
    return "; ".join(f"[{e.get('time')}] {e.get('event')} (onem:{e.get('severity')})" for e in evs)


def _load_gt() -> dict:
    """benchmark/ground_truth.json (varsa) — en guvenilir etiket kaynagi."""
    try:
        with open(GT_PATH, encoding="utf-8") as f:
            gt = json.load(f)
        return {k: v for k, v in gt.items() if not k.startswith("_") and isinstance(v, dict)}
    except Exception:
        return {}


def resolve_label(row: dict, gt: dict):
    """Klibin ground-truth etiketini cozer: GT dosyasi > satir alanlari > yol ayristirma.

    Returns:
        (kategori, anomali_mi, kaynak) ya da etiket cikarilamiyorsa (None, None, None).
        ASLA etiket UYDURMAZ — bilinmiyorsa dayanakli puanlama YAPILMAZ.
    """
    path = (row.get("path") or "").replace("\\", "/")
    spec = gt.get(path)
    if spec and spec.get("kategori"):
        return spec["kategori"], bool(spec.get("anomali", True)), "ground_truth.json"
    cat = row.get("category")
    if cat:
        anom = row.get("is_anomaly")
        return cat, bool(anom) if anom is not None else is_anomaly(cat), "eval satiri"
    cat = category_from_path(path)
    if cat:
        return cat, is_anomaly(cat), "yol/klasor adi"
    return None, None, None


def _durum_text(anom: bool) -> str:
    return ("ANOMALI — etikette belirtilen olay bu klipte GERCEKTEN vardir"
            if anom else
            "NORMAL — bu klipte kayda deger HICBIR guvenlik olayi YOKTUR (olagan faaliyet)")


def _vision_content(path: str, summary: str, n_frames: int) -> list:
    """Klipten n_frames kare ornekleyip cok-modlu hakem icin icerik listesi kurar.

    GPU/dekoder gerektirir; yalnizca --vision ile cagrilir. FAIL-OPEN: hata -> None.
    """
    try:
        from dilajan.video import extract_timestamped_frames  # lazy: yalniz vision-path
        from dilajan.utils import format_timestamp
    except Exception:
        return None
    try:
        frames, _info = extract_timestamped_frames(path)
    except Exception:
        return None
    if not frames:
        return None
    step = max(1, len(frames) // max(1, n_frames))
    picked = frames[::step][:n_frames]
    content = []
    for t, jpeg in picked:
        content.append({"type": "text", "text": f"[Kare zamani: {format_timestamp(t)}]"})
        content.append({"type": "image_url",
                        "image_url": {"url": VLMClient._to_data_url(jpeg)}})
    content.append({"type": "text", "text": VISION_JUDGE.format(summary=summary)})
    return content


def _block(vals: list, n_klip: int, n_eksen: int, tur: str) -> dict:
    """Kalite skoru blogu — n_klip (BAGIMSIZ birim) ile n_altskor AYRI alanlar (K15)."""
    m, sd, n = mean_sd(vals)
    return {
        "mean": None if m is None else round(m, 2),
        "std": round(sd, 2),
        "n_klip": n_klip,
        "n_eksen": n_eksen,
        "n_altskor": n,
        "metrik_turu": tur,
        "not": ("n_altskor = n_klip x n_eksen; guven araligi n_klip uzerinden okunmalidir "
                "(pseudo-replikasyon)"),
    }


# ---------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description="Bagimsiz + DAYANAKLI LLM hakem (K11)")
    ap.add_argument("eval_json", nargs="?", default=None,
                    help="degerlendirilecek benchmark/results/eval_*.json (varsayilan: en yenisi)")
    ap.add_argument("--vision", action="store_true",
                    help="[C] klip karelerini de hakeme gonder (COK-MODLU hakem + GPU gerekir)")
    ap.add_argument("--vision-frames", type=int, default=6, help="--vision icin kare sayisi")
    ap.add_argument("--no-self", action="store_true",
                    help="[B] ic-tutarlilik eksenlerini atla (yalniz dayanakli olc)")
    args = ap.parse_args()

    if os.environ.get("DILAJAN_JUDGE_VISION", "").strip() in ("1", "true", "yes"):
        args.vision = True

    if not JUDGE_MODEL:
        print("HATA: DILAJAN_JUDGE_MODEL ayarli degil. Or: DILAJAN_JUDGE_MODEL=google/gemma-2-9b-it ...")
        sys.exit(1)
    client = VLMClient(model=JUDGE_MODEL)
    if not client.health_check():
        print(f"HATA: judge modeli '{JUDGE_MODEL}' vLLM'de servis edilmiyor. Once swap-serve et.")
        sys.exit(1)
    print(f"BAGIMSIZ JUDGE: {JUDGE_MODEL}" + ("  [+GORSEL DAYANAK]" if args.vision else ""))
    print("=" * 72)

    gt = _load_gt()
    print(f"Ground truth etiketleri: {len(gt)} klip "
          f"({os.path.relpath(GT_PATH, ROOT) if gt else 'YOK — once build_ground_truth.py'})")

    path = args.eval_json
    if not path:
        files = sorted(glob.glob(os.path.join(RESULTS_DIR, "eval_*.json")))
        path = files[-1] if files else None

    out = {
        "judge_model": JUDGE_MODEL,
        "gorsel_dayanak": bool(args.vision),
        "metrik_aileleri": {
            "DAYANAKLI": T_GROUNDED,
            "IC_TUTARLILIK": T_SELF,
            "GORSEL": T_VISION if args.vision else "kapali",
        },
        "uyari": ("IC-TUTARLILIK skorlari sistemin videoyu DOGRU anladigini KANITLAMAZ; "
                  "yalnizca kendi ciktisiyla celismedigini gosterir. Dis gecerlilik icin "
                  "DAYANAKLI bloguna bakilmalidir."),
    }

    if path and os.path.exists(path):
        doc = json.load(open(path, encoding="utf-8"))
        rows = doc["rows"]
        print(f"Analiz ciktilari: {os.path.relpath(path, ROOT)} ({len(rows)} klip)")
        print("-" * 72)

        # --- [A] DAYANAKLI: GT etiketine karsi olgusal denetim ---
        g_scores, g_by_cat = [], {}
        n_celiski = n_uydurma = n_labeled = 0
        etiketsiz = []
        g_details = []
        # --- [B] IC-TUTARLILIK (eski eksenler) ---
        summ, act, risk = [], [], []
        n_summ = n_act = n_risk = 0
        # --- [C] GORSEL ---
        v_scores, n_vision, n_gorulmeyen = [], 0, 0

        for r in rows:
            ev_txt = _events_text(r)
            summary = r.get("summary") or ""
            cat, anom, src = resolve_label(r, gt)

            # ---- [A] dayanakli ----
            if summary and cat:
                n_labeled += 1
                s = _ask(client, GROUNDED_JUDGE.format(
                    kategori=cat, kategori_tr=describe(cat),
                    durum=_durum_text(bool(anom)), summary=summary, events=ev_txt), maxt=220)
                if s:
                    try:
                        val = float(s.get("olgusal_dayanaklilik", 0))
                    except (TypeError, ValueError):
                        val = 0
                    if 1 <= val <= 5:
                        g_scores.append(val)
                        g_by_cat.setdefault(cat, []).append(val)
                        n_celiski += int(bool(s.get("celiski")))
                        n_uydurma += int(bool(s.get("uydurma")))
                        g_details.append({
                            "path": r.get("path"), "kategori": cat, "anomali": anom,
                            "etiket_kaynagi": src, "olgusal_dayanaklilik": val,
                            "celiski": bool(s.get("celiski")), "uydurma": bool(s.get("uydurma")),
                            "gerekce": str(s.get("gerekce", ""))[:300],
                        })
            elif summary and not cat:
                etiketsiz.append(r.get("path"))

            # ---- [C] gorsel dayanak (opsiyonel) ----
            if args.vision and summary and r.get("path"):
                vp = os.path.join(ROOT, r["path"])
                content = _vision_content(vp, summary, args.vision_frames) if os.path.exists(vp) else None
                if content:
                    s = _ask(client, "", maxt=200, content=content)
                    if s:
                        try:
                            val = float(s.get("gorsel_sadakat", 0))
                        except (TypeError, ValueError):
                            val = 0
                        if 1 <= val <= 5:
                            n_vision += 1
                            v_scores.append(val)
                            n_gorulmeyen += int(bool(s.get("gorulmeyen_iddia")))

            # ---- [B] ic-tutarlilik ----
            if args.no_self:
                continue
            if summary:
                n_summ += 1
                summ += _score(client, SUMMARY_JUDGE.format(events=ev_txt, summary=summary),
                               ["dogruluk", "akicilik", "ozluluk"])
            if r.get("events") and r.get("actions"):
                n_act += 1
                act_txt = "; ".join(f"[{a.get('priority')}] {a.get('action')}" for a in r["actions"])
                act += _score(client, ACT_JUDGE.format(events=ev_txt, risk=r.get("risk_level"),
                                                       actions=act_txt),
                              ["alaka", "uygulanabilirlik", "oncelik", "kapsama"], maxt=120)
            if r.get("events") and r.get("risk_rationale"):
                n_risk += 1
                risk += _score(client, RISK_JUDGE.format(events=ev_txt, level=r.get("risk_level"),
                                                         rationale=r["risk_rationale"]),
                               ["dayanaklilik", "tutarlilik", "eyleme_donukluk"], maxt=120)

        # ---------------- [A] rapor ----------------
        print("\n[A] DAYANAKLI (grounded) — dataset GT etiketine karsi OLGUSAL denetim")
        print("    " + T_GROUNDED)
        m, sd, n = mean_sd(g_scores)
        if m is not None:
            r_cel = rate(n_celiski, n)
            r_uyd = rate(n_uydurma, n)
            print(f"  olgusal_dayanaklilik  : {m:.2f} ± {sd:.2f}   (n_klip={n})")
            print(f"  ETIKETLE CELISKI orani: {fmt_rate_dict(r_cel)}   (dusuk = iyi)")
            print(f"  UYDURMA ayrinti orani : {fmt_rate_dict(r_uyd)}   (dusuk = iyi)")
            out["OLGUSAL DAYANAKLILIK"] = _block(g_scores, n, 1, T_GROUNDED)
            out["OLGUSAL DAYANAKLILIK"]["etiketle_celiski"] = r_cel
            out["OLGUSAL DAYANAKLILIK"]["uydurma_ayrinti"] = r_uyd
            out["OLGUSAL DAYANAKLILIK"]["kategori_bazli"] = {
                c: _block(v, len(v), 1, T_GROUNDED) for c, v in sorted(g_by_cat.items())
            }
            out["dayanakli_detay"] = g_details
        else:
            print("  (etiketlenebilir klip yok — build_ground_truth.py calistirilmali)")
        if etiketsiz:
            print(f"  ETIKETSIZ (dayanakli puanlanmadi): {len(etiketsiz)} klip "
                  f"— etiket UYDURULMADI")
            out["etiketsiz_klipler"] = etiketsiz

        # ---------------- [C] rapor ----------------
        if args.vision:
            print("\n[C] GORSEL DAYANAK — klip karelerine karsi")
            m, sd, n = mean_sd(v_scores)
            if m is not None:
                r_gor = rate(n_gorulmeyen, n)
                print(f"  gorsel_sadakat        : {m:.2f} ± {sd:.2f}   (n_klip={n})")
                print(f"  GORULMEYEN iddia orani: {fmt_rate_dict(r_gor)}   (dusuk = iyi)")
                out["GORSEL SADAKAT"] = _block(v_scores, n, 1, T_VISION)
                out["GORSEL SADAKAT"]["gorulmeyen_iddia"] = r_gor
            else:
                print("  (kare cikarilamadi / cok-modlu hakem yanit vermedi)")

        # ---------------- [B] rapor ----------------
        if not args.no_self:
            print("\n[B] IC-TUTARLILIK (self-consistency) — VIDEOYA DAYANAKLI DEGIL")
            print("    " + T_SELF)
            for name, vals, nk, ne in [("OZET kalitesi", summ, n_summ, 3),
                                       ("AKSIYON kalitesi", act, n_act, 4),
                                       ("RISK gerekce", risk, n_risk, 3)]:
                m, sd, n = mean_sd(vals)
                if m is None:
                    continue
                print(f"  {name:18s}: {m:.2f} ± {sd:.2f}   "
                      f"(n_klip={nk}, n_eksen={ne}, n_altskor={n})")
                out[name] = _block(vals, nk, ne, T_SELF)
    else:
        print("(eval_*.json yok — once: python benchmark/eval_clips.py)")

    # --- diyalog ciktilari (ic-tutarlilik ailesi) ---
    dpath = os.path.join(RESULTS_DIR, "dialogue_responses.json")
    if os.path.exists(dpath) and not args.no_self:
        d = json.load(open(dpath, encoding="utf-8"))
        print(f"\nDiyalog yanitlari: dialogue_responses.json "
              f"(tek={len(d['single'])}, cok-tur={len(d['multi'])})")
        single = []
        for it in d["single"]:
            single += _score(client, SINGLE_JUDGE.format(stype=it["stype"], expected=it["expected"],
                             msg=it["msg"], resp=it["resp"]), ["uygunluk"], maxt=80)
        multi = []
        for it in d["multi"]:
            multi += _score(client, MT_JUDGE.format(history=it["history"], msg=it["msg"],
                            resp=it["resp"], expected=it["expected"]), ["uygunluk"], maxt=80)
        for name, vals, nk in [("DIYALOG tek-tur", single, len(d["single"])),
                               ("DIYALOG cok-tur", multi, len(d["multi"]))]:
            m, sd, n = mean_sd(vals)
            if m is not None:
                print(f"  {name:18s}: {m:.2f} ± {sd:.2f}   (n_senaryo={nk}, n_altskor={n})")
                out[name] = _block(vals, nk, 1, T_SELF)
    elif not args.no_self:
        print("\n(dialogue_responses.json yok — once: python benchmark/gen_dialogue.py)")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    op = os.path.join(RESULTS_DIR, "independent_scores.json")
    with open(op, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n" + "=" * 72)
    print(f"Kaydedildi: {os.path.relpath(op, ROOT)}")
    print("METRIK OKUMA KURALI:")
    print("  [A] DAYANAKLI  -> dis gecerlilik iddiasi burada YAPILIR (GT etiketine karsi).")
    print("  [B] IC-TUTARLILIK -> yalniz oz-celiski yoklugu; 'video dogru anlasildi' DEMEZ.")
    print("  Bu ikisi ASLA tek bir 'kalite skoru' olarak birlestirilmemelidir.")


if __name__ == "__main__":
    main()
