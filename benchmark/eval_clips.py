#!/usr/bin/env python
"""Klip-seviyesi degerlendirme: data/eval/<Kategori>/*.mp4 uzerinde ajani calistirir.

Metrikler:
  - Anomali recall        : anomali klibinde >=1 olay tespit edildi mi
  - Risk kalibrasyonu     : anomali -> risk >= Yuksek ; normal -> risk = Dusuk
  - Normal yanlis-pozitif : normal klipte yuksek/kritik olay veya yuksek risk uretildi mi
  - Kategori eslesmesi    : tespit edilen olay metni beklenen anahtar kelimeleri iceriyor mu
  - Gecikme               : klip basina sure ve video-saniyesi basina

D28 — KATEGORI ESLESMESI ONARILDI (OKUMADAN GECME):
Eski kural YALNIZCA events[].event alanini tariyordu; `summary` HIC BAKILMIYORDU.
Oysa summary sartname cikti sozlesmesinin (K3) parcasi ve operatorun OKUDUGU alandir —
adlandirma kazancinin bir kismi orada kaliyor ve olculmuyordu. Ayrica eslestirici
ciplak alt-dizge idi ("kırmızı" -> "kır" -> Burglary) ve Python'un .lower()'i Turkce
degildi ("İstismar" -> "i̇stismar", "istismar" ile eslesmez).

K4 GEREGI metrik SESSIZCE DEGISTIRILMEDI. Her satirda UC alan yan yana yazilir:
    category_match       YENI  : event + summary, sikilastirilmis eslestirici
    category_match_eski  ESKI  : yalniz event, ciplak alt-dizge  (KARSILASTIRMA TABANI)
    category_match_grup  GRUP  : semantik grup duzeyinde eslesme (arXiv 2511.07171)
Eski skor SILINMEZ/GIZLENMEZ/USTUNE YAZILMAZ. DILAJAN_EVAL_MATCH=eski ile
`category_match` alani BIREBIR eski kurala dondurulur (K2 — varsayilana donus yolu).
Arsivlenmis sonuclari model calistirmadan yeniden skorlamak icin: benchmark/rescore.py

K10 — MUKERRER ELEME: ayni MD5'e sahip klipler payda'yi sisirir
(or. Normal_Videos_936/937 BIREBIR AYNI dosya -> Normal paydasi 8 degil 7'dir).
Bu betik artik klipleri icerik-hash'ine gore tekillestirir; atlanan dosyalar cikti
JSON'unda "dedup" alanina yazilir. Kapatmak icin: DILAJAN_EVAL_DEDUP=0

K15 — RAPORLAMA HIJYENI: her oran metrigi ham sayimlar (k/n) ve Wilson %95 guven
araligi ile birlikte raporlanir. Kucuk n'de nokta-deger tek basina yaniltici.

Sonuclar benchmark/results/<zaman>.json olarak kaydedilir (iterasyonlar arasi karsilastirma icin).
Kullanim:  python benchmark/eval_clips.py
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dilajan.agent import analyze_video  # noqa: E402
from dilajan.schema import Severity  # noqa: E402

try:
    from benchmark.dedup import dedup_paths  # noqa: E402
    from benchmark.labels import (CATEGORY_EXPECT, any_match,  # noqa: E402
                                  isg_any_match, isg_sinif_from_path)
    from benchmark.stats_utils import fmt_rate_dict, rate_from_bools  # noqa: E402
except ImportError:  # benchmark/ icinden dogrudan calistirma
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from dedup import dedup_paths  # type: ignore  # noqa: E402
    from labels import (CATEGORY_EXPECT, any_match,  # type: ignore  # noqa: E402
                        isg_any_match, isg_sinif_from_path)
    from stats_utils import fmt_rate_dict, rate_from_bools  # type: ignore  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DILAJAN_EVAL_DIR ile farkli bir degerlendirme seti (or. senaryo-uyumlu) calistirilabilir
EVAL_DIR = os.environ.get("DILAJAN_EVAL_DIR") or os.path.join(ROOT, "data", "eval")

# K9 — SIZINTI UYARISI: eski data/eval, data/eval_big'in %100 ALT KUMESIDIR (31/31 ayni MD5).
# Ayar (tuning) ve dogrulama ayni klipler uzerinde yapilirsa sonuc IYIMSER cikar.
# Temiz, AYRIK cift: data/eval_tune (ayar) + data/eval_holdout (dogrulama).
LEAKY_EVAL_DIRS = {os.path.join(ROOT, "data", "eval"), os.path.join(ROOT, "data", "eval_big")}


def _warn_if_leaky(eval_dir: str) -> Optional[str]:
    """Sizintili eski set kullaniliyorsa operatoru/raporu uyarir (cikti JSON'una da yazilir)."""
    if os.path.normpath(eval_dir) not in {os.path.normpath(p) for p in LEAKY_EVAL_DIRS}:
        return None
    msg = ("UYARI (K9): data/eval, data/eval_big'in %100 alt kumesidir — bu iki set BAGIMSIZ "
           "DEGILDIR. Ayar+dogrulama ayni klipleri paylastigi icin sonuclar IYIMSER olabilir. "
           "Temiz ayrik cift icin: DILAJAN_EVAL_DIR=data/eval_holdout (dogrulama) / data/eval_tune (ayar).")
    print("\n" + "!" * 78 + f"\n{msg}\n" + "!" * 78 + "\n")
    return msg
RESULTS_DIR = os.path.join(ROOT, "benchmark", "results")


def _kosum_kunyesi() -> dict:
    """D36 — kosumun MODEL ve SERVISLEME kunyesi (salt okuma, metrik degistirmez).

    Model degistirerek A/B yapmak, D33'e kadarki tum arsivlerin ortulu varsayimini
    ('hep ayni model') kirar. Kunye olmadan iki arsiv sayisal olarak kiyaslanabilir
    ama HANGI degisikligin farki urettigi arsivden okunamaz.

    gpu_memory_utilization / max_num_seqs de yazilir: buyuk modeli sigdirmak icin
    bunlar degistirilirse KV blok sayisi degisir -> gecikme ve batch davranisi
    degisir. Sapma kayda gecmezse "ayni kosullarda olculdu" iddiasi yanlis olur.
    """
    try:
        from dilajan.config import settings as _s
    except Exception as e:  # ayar okunamazsa olcumu DURDURMA (fail-open, K3)
        return {"hata": f"{type(e).__name__}: {e}"}
    return {
        "model": _s.model_name,
        "quantization": _s.quantization or "(otomatik/yok)",
        "dtype": _s.dtype,
        "kv_cache_dtype": _s.kv_cache_dtype or "(varsayilan)",
        "max_model_len": _s.max_model_len,
        "gpu_memory_utilization": _s.gpu_memory_utilization,
        "max_num_seqs": _s.max_num_seqs,
        "temperature": _s.temperature,
        # D36: hibrit akil yuruten modellerde bu bayrak sonucu KOKTEN degistirir
        # (acikken JSON hic gelmiyor, 0 olay uretiliyor) -> kunyede olmak ZORUNDA.
        "disable_thinking": _s.disable_thinking,
        "fps_sample": _s.fps_sample,
        "max_frames_per_segment": _s.max_frames_per_segment,
        "frame_max_side": _s.frame_max_side,
        # --- OZELLIK BAYRAKLARI ---
        # BURAYA, davranisi degistiren HER bayrak girmelidir. Iki sebeple:
        #   1) arsiv hangi kolun olculdugunu yazmali (raporlama durustlugu),
        #   2) ara-kayit dosya adi bu kunyenin hash'idir -> eksik bayrak, FARKLI
        #      yapilandirmalarin ayni ara dosyayi paylasmasina ve birbirinin satirlarini
        #      devralmasina yol acar. `isg_lens` ilk eklendiginde tam bu hata olustu
        #      (acik/kapali ayni dosya adini uretti) ve testte yakalandi.
        "facility_rules_dolu": bool(_s.facility_rules),
        "ppe_detection": _s.ppe_detection,
        "isg_lens": _s.isg_lens,
        "threat_interpretation": _s.threat_interpretation,
    }


def _sizinti_celiskili(rel_path: str) -> bool:
    """Klip, ZIT etiketli bir klibin tam kapsamasinda mi? (D36 sahne sizintisi)

    Kayit okunamazsa olcumu DURDURMA (K3 fail-open) — yalnizca False don.
    Bu alan hicbir metrigi degistirmez; raporlama durustlugu icindir.
    """
    try:
        from benchmark.sizinti_eval_defense import celiskili_mi
    except Exception:
        try:
            from sizinti_eval_defense import celiskili_mi  # type: ignore
        except Exception:
            return False
    return celiskili_mi(rel_path)


def _ara_kayit_yol() -> str:
    """Ara-kayit dosyasi: hangi SET + hangi KATEGORILER + hangi KUNYE ile kosuldugu.

    Kunye hash'i ada girer -> farkli yapilandirmanin ara kaydi YANLISLIKLA devralinamaz.
    """
    import hashlib
    kimlik = json.dumps({
        "eval_dir": os.path.relpath(EVAL_DIR, ROOT).replace("\\", "/"),
        "cats": os.environ.get("EVAL_CATS", ""),
        "match": MATCH_MODE,
        "kosum": _kosum_kunyesi(),
    }, sort_keys=True, ensure_ascii=False)
    h = hashlib.md5(kimlik.encode("utf-8")).hexdigest()[:10]
    return os.path.join(RESULTS_DIR, f".ara_{h}.jsonl")


def _ara_kayit_yukle():
    """(yol, {path: row}) dondurur. Bozuk satirlar SESSIZCE atlanir (K3 fail-open)."""
    yol = _ara_kayit_yol()
    tamam: dict = {}
    if os.path.exists(yol):
        with open(yol, encoding="utf-8") as f:
            for satir in f:
                satir = satir.strip()
                if not satir:
                    continue
                try:
                    r = json.loads(satir)
                except Exception:
                    continue  # yarim yazilmis son satir (cokme aninda) — atla
                if isinstance(r, dict) and r.get("path"):
                    tamam[r["path"]] = r
    return yol, tamam


def _ara_kayit_ekle(yol: str, row: dict) -> None:
    """Her klipten SONRA hemen diske yaz + fsync — cokmede en fazla 1 klip kaybedilir."""
    try:
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with open(yol, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:  # ara kayit YAZILAMAZSA olcum DURMAZ (K3)
        print(f"[ARA KAYIT UYARI] yazilamadi: {e}")


# K10 mukerrer eleme varsayilan ACIK; DILAJAN_EVAL_DEDUP=0 ile eski davranisa donulur
DEDUP = os.environ.get("DILAJAN_EVAL_DEDUP", "1").strip().lower() not in ("0", "false", "no")
# D28/K2 — `category_match` alanini hangi kural doldurur: "yeni" (event+summary,
# sikilastirilmis) veya "eski" (yalniz event, ciplak alt-dizge). HANGISI SECILIRSE
# SECILSIN her uc alan da (yeni/eski/grup) satira YAZILIR — bilgi kaybi olmaz (K4).
MATCH_MODE = os.environ.get("DILAJAN_EVAL_MATCH", "yeni").strip().lower()

SEV_ORD = {Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4}

# kategori -> beklenen anahtar kelimeler + anomali mi  (tek kaynak: benchmark/labels.py)


def _video_seconds(mmss: str) -> int:
    try:
        m, s = mmss.split(":")
        return int(m) * 60 + int(s)
    except Exception:
        return 0


def evaluate_clip(path: str, category: str) -> dict:
    keywords, is_anomaly = CATEGORY_EXPECT.get(category, ([], True))
    t0 = time.time()
    res = analyze_video(path)
    dt = time.time() - t0

    n_events = len(res.events)
    max_sev = max((SEV_ORD[e.severity] for e in res.events), default=0)
    risk_ord = SEV_ORD.get(res.risk.level, 0)
    dur = _video_seconds(res.video_duration or "00:00")

    # --- D28: kategori eslesmesi UC KURALLA birden hesaplanir (K4 yan yana raporlama) ---
    # ESKI kapsam: yalniz olay metinleri. YENI kapsam: olay metinleri + summary.
    parcalar_eski = [e.event for e in res.events if e.event]
    parcalar_yeni = parcalar_eski + ([res.summary] if res.summary else [])
    if keywords:
        cat_eski = any_match(parcalar_eski, category, mode="loose")   # D28 ONCESI kural
        cat_yeni = any_match(parcalar_yeni, category, mode="strict")  # onarilmis kural
        cat_grup = any_match(parcalar_yeni, category, mode="strict", group=True)
        # --- D36: ONARIK OLUMSUZLAMA KAPISI (SALT EKLEME) ---
        # D28 kapisi `tespit edil` govdesini biliyor ama `gozlemlen` govdesini BILMIYOR.
        # Model sablon inkar cumlesini degistirdiginde skor MODEL YETENEGINDEN BAGIMSIZ
        # olarak ziplyor. Olculdu (ayni iki arsiv):
        #     8B  "...gozlemlenmedi"      -> kapi KACIRIYOR -> 26 eslesme (21'i SAHTE)
        #     27B "...tespit edilmemistir"-> kapi YAKALIYOR ->  7 eslesme (0'i sahte)
        # Onarik kapiyla ayni arsivler 5 ve 7 veriyor -> 27B DAHA IYI, "cokus" yok.
        # Mevcut uc alan DEGISMEDI; bu dorduncu alan kapi-bagimsiz okuma saglar.
        cat_onarik = any_match(parcalar_yeni, category, mode="strict",
                               onarik_olumsuzlama=True)
    else:
        # Normal kategorisinin beklenen anahtar kelimesi YOKTUR -> eslesme TANIMSIZ (eski davranis)
        cat_eski = cat_yeni = cat_grup = cat_onarik = None
    cat_match = cat_eski if MATCH_MODE == "eski" else cat_yeni

    # --- D36: INCE TANELI ISG OLCUMU (SALT EKLEME) ---
    # `recall` = (n_events > 0) ve olayin DOGRU tehlike olup olmadigina BAKMAZ.
    # Olculdu: Opened_Panel_Cover kliplerinde model HIC panodan bahsetmiyor (0/25)
    # ama "yere dusmus metal levha" gibi alakasiz olaylar recall'u kazandiriyor.
    # Ust klasor (Anomali/Normal) kova-duzeyidir; ALT klasor gercek ISG sinifidir.
    # `isg_any_match` sinifa OZGU kaliplari ve ONARIK kapiyi kullanir.
    isg_sinif = isg_sinif_from_path(os.path.relpath(path, ROOT).replace("\\", "/"))
    isg_eslesme = isg_any_match(parcalar_yeni, isg_sinif) if isg_sinif else None

    return {
        "path": os.path.relpath(path, ROOT),
        "category": category,
        "is_anomaly": is_anomaly,
        "n_events": n_events,
        "max_severity": max_sev,
        "risk_ord": risk_ord,
        "risk_level": res.risk.level.value,
        # UCU DE YAZILIR — hangisinin hangi kural oldugu modul basligindaki tabloda (K4)
        "category_match": cat_match,           # secili kural (varsayilan: YENI)
        "category_match_eski": cat_eski,       # ESKI kural — KARSILASTIRMA TABANI, silinmez
        "category_match_grup": cat_grup,       # semantik grup duzeyi
        "category_match_kural": MATCH_MODE,    # `category_match` alanini hangi kural doldurdu
        # D36 — kapi-bagimsiz okuma + ince taneli ISG ozgullugu (ikisi de SALT EK)
        "category_match_onarik": cat_onarik,   # onarik olumsuzlama kapisi
        "isg_sinif": isg_sinif,                # alt klasorden gercek ISG sinifi
        "isg_match": isg_eslesme,              # sinifa OZGU kalip + onarik kapi
        # D36 — SAHNE SIZINTISI (yalnizca GORUNURLUK; metrigi DEGISTIRMEZ):
        # bu klip, ZIT etiketli bir klibin tam kapsamasinda mi? Oyleyse ikili
        # gercek-etiket kendi icinde celiskilidir ve model burada ZORUNLU yanilir.
        "sizinti_celiskili": _sizinti_celiskili(os.path.relpath(path, ROOT)),
        "triggered": res.triggered_functions,
        "duration_s": dur,
        "latency_s": round(dt, 1),
        "summary": res.summary,
        "events": [
            {"time": e.time, "event": e.event, "severity": e.severity.value,
             "category": e.category.value, "region": e.region}
            for e in res.events
        ],
        "risk_rationale": res.risk.rationale,
        # Politika hakemligi TESHISI (yalniz 'policy'/'act: politika' satirlari): B1 kolunda
        # beklenen kazanc cikmazsa hatanin ESLESTIRICIDE mi, CEKINCE kapisinda mi, KANIT
        # dogrulamasinda mi oldugu TEK KOSUDAN okunur. facility_policy bos iken bu liste
        # BOS kalir -> arsivlenmis kosularla karsilastirma etkilenmez (yalnizca EK alan).
        "policy_trace": [t for t in (res.decision_trace or [])
                         if t.startswith("policy") or t.startswith("act: politika")],
        "actions": [
            {"action": a.action, "priority": a.priority.value, "rationale": a.rationale}
            for a in res.actions
        ],
    }


def main() -> None:
    # istege bagli kategori filtresi: EVAL_CATS="Normal" veya "RoadAccidents,Explosion"
    only = {c.strip() for c in os.environ.get("EVAL_CATS", "").split(",") if c.strip()}
    clips = []
    for cat in sorted(os.listdir(EVAL_DIR)) if os.path.isdir(EVAL_DIR) else []:
        # '_' ile baslayan klasorler KARANTINA/METADATA'dir, kategori DEGILDIR ve olcume ALINMAZ.
        # (or. data/eval_scenario/_deprecated_frozen_fall — K8'de sete alinmamak uzere ayrilan
        #  donmus-PNG klipler. Filtre olmazsa bilinmeyen kategori is_anomaly=True varsayilir ve
        #  bu klipler anomali paydasina geri sizar; evaluate.py'nin '_' atlama kuraliyla ayni.)
        if cat.startswith("_"):
            continue
        if only and cat not in only:
            continue
        paths = []
        for ext in ("*.mp4", "*.avi", "*.mkv", "*.mov", "*.mpg", "*.mpeg"):
            paths.extend(glob.glob(os.path.join(EVAL_DIR, cat, ext)))
            # IC ICE kategori klasorlerini de tara (or. data/eval_defense/Anomali/<SinifAdi>/*.mp4).
            # Alt klasor adi yalnizca KOKEN bilgisidir; etiket her zaman UST kategori klasorudur.
            paths.extend(glob.glob(os.path.join(EVAL_DIR, cat, "*", ext)))
        for path in sorted(paths):
            clips.append((path, cat))
    if not clips:
        print(f"data/eval/ altinda klip yok. Once: python scripts/build_eval_set.py")
        return

    # --- K10: MD5 mukerrer eleme (payda sismesini onler) ---
    n_before = len(clips)
    dedup_skipped: list = []
    if DEDUP:
        kept_paths, dedup_skipped = dedup_paths([p for p, _ in clips], rel_to=ROOT)
        kept_set = set(kept_paths)
        clips = [(p, c) for p, c in clips if p in kept_set]
        if dedup_skipped:
            print(f"[DEDUP] {len(dedup_skipped)} mukerrer klip elendi "
                  f"({n_before} -> {len(clips)} benzersiz):")
            for s in dedup_skipped:
                dup_of = s.get("duplicate_of") or "(hash alinamadi)"
                print(f"   - {s['path']}  ==  {dup_of}")
            print()

    # --- D36: ARA KAYIT (checkpoint) ---
    # 2026-08-17'de bilgisayar IKI KEZ restart atti ve her seferinde ~1 saatlik GPU
    # kosusu TAMAMEN kayboldu — cunku sonuc YALNIZCA en sonda yazılıyordu.
    # Artik her klipten sonra JSONL'e eklenir; ayni kunye ile yeniden baslatilirsa
    # tamamlanmis klipler ATLANIR. Kunye farkliysa devam EDILMEZ (farkli yapilandirmanin
    # satirlarini birlestirmek olcumu sessizce bozar) — ara dosya yok sayilir.
    ara_yol, tamamlanan = _ara_kayit_yukle()
    rows = list(tamamlanan.values())
    if rows:
        print(f"[ARA KAYIT] {len(rows)} klip onceki kosumdan devraliniyor "
              f"({os.path.basename(ara_yol)})\n")
    kalan = [(p, c) for p, c in clips
             if os.path.relpath(p, ROOT).replace("\\", "/") not in tamamlanan]

    print(f"{len(kalan)} klip degerlendiriliyor"
          f"{f' (toplam {len(clips)}, {len(rows)} devralindi)' if rows else ''}...\n")
    for path, cat in kalan:
        try:
            r = evaluate_clip(path, cat)
        except Exception as e:
            print(f"[HATA] {path}: {e}")
            continue
        rows.append(r)
        _ara_kayit_ekle(ara_yol, r)
        mark = "✓" if (r["category_match"] or (not r["is_anomaly"] and r["max_severity"] < 3)) else "·"
        print(f"  {mark} [{cat:13s}] olay={r['n_events']} risk={r['risk_level']:6s} "
              f"kat_eslesme={r['category_match']} {r['latency_s']}s  {os.path.basename(path)}",
              flush=True)   # tamponlama yuzunden ilerleme gorunmuyordu

    # --- toplulastir ---
    anom = [r for r in rows if r["is_anomaly"]]
    norm = [r for r in rows if not r["is_anomaly"]]

    # Her metrik icin ham sayimlar + Wilson %95 CI (K15). Nokta-deger TEK BASINA raporlanmaz.
    R = {
        "recall": rate_from_bools([r["n_events"] > 0 for r in anom]),
        "risk_cal_anom": rate_from_bools([r["risk_ord"] >= 3 for r in anom]),
        "cat_match": rate_from_bools([bool(r["category_match"]) for r in anom]),
        # D28/K4: eski ve grup skorlari da HER ZAMAN hesaplanir ki taban cizgisi gorunur kalsin.
        # .get(): arsivlenmis/eski satirlarda bu alanlar YOKTUR — okuyan kod COKMEZ (K3 fail-open).
        "cat_match_eski": rate_from_bools([bool(r.get("category_match_eski")) for r in anom]),
        "cat_match_grup": rate_from_bools([bool(r.get("category_match_grup")) for r in anom]),
        # normal yanlis-pozitif (DAR): yuksek/kritik olay VEYA risk >= yuksek
        "normal_fp": rate_from_bools([(r["max_severity"] >= 3 or r["risk_ord"] >= 3) for r in norm]),
        # normal yanlis-pozitif (OPERASYONEL, durust): normalde HERHANGI olay VEYA fonksiyon tetigi
        "normal_fp_operational": rate_from_bools(
            [(r["n_events"] > 0 or len(r.get("triggered", [])) > 0) for r in norm]),
        "normal_dispatch_fp": rate_from_bools([len(r.get("triggered", [])) > 0 for r in norm]),
        "risk_cal_norm": rate_from_bools([r["risk_ord"] <= 1 for r in norm]),
    }
    # geriye-uyumluluk: eski duz oran alanlari (aggregate.py/compare.py bunlari okuyor)
    recall = R["recall"]["p"]
    risk_cal_anom = R["risk_cal_anom"]["p"]
    cat_match_rate = R["cat_match"]["p"]
    fp = R["normal_fp"]["p"]
    op_fp = R["normal_fp_operational"]["p"]
    dispatch_fp = R["normal_dispatch_fp"]["p"]
    risk_cal_norm = R["risk_cal_norm"]["p"]
    lat = [r["latency_s"] for r in rows]
    persec = [r["latency_s"] / max(r["duration_s"], 1) for r in rows]

    print("\n" + "=" * 72)
    print(f"Anomali klipleri: {len(anom)}   Normal klipleri: {len(norm)}"
          + (f"   (MD5 mukerrer elenen: {len(dedup_skipped)})" if dedup_skipped else ""))
    print("Tum oranlar: nokta-deger [Wilson %95 GA]  (k/n)")
    print("-" * 72)
    print(f"  Anomali RECALL (>=1 olay)      : {fmt_rate_dict(R['recall'])}")
    print(f"  Anomali risk kalibrasyonu(>=Y) : {fmt_rate_dict(R['risk_cal_anom'])}")
    # D28/K4 — UC KURAL YAN YANA. Kural adlari YAZILI; hangisinin ne oldugu tahmine birakilmaz.
    print(f"  Kategori eslesme [ESKI kural]  : {fmt_rate_dict(R['cat_match_eski'])}"
          f"   (yalniz event, ciplak alt-dizge — D28 ONCESI taban)")
    print(f"  Kategori eslesme [YENI kural]  : {fmt_rate_dict(R['cat_match'])}"
          f"   (event+summary, sikilastirilmis eslestirici)")
    print(f"  Kategori eslesme [GRUP duzeyi] : {fmt_rate_dict(R['cat_match_grup'])}"
          f"   (semantik grup: Siddet/MalSuclari/Yikim/...)")
    print(f"    -> 'category_match' alanini dolduran kural: {MATCH_MODE.upper()}"
          f"   (DILAJAN_EVAL_MATCH ile degistirilir)")
    print(f"  NORMAL FP (dar: sev/risk>=Y)   : {fmt_rate_dict(R['normal_fp'])}   (dusuk = iyi)")
    print(f"  NORMAL FP (operasyonel)        : {fmt_rate_dict(R['normal_fp_operational'])}   (durust metrik)")
    print(f"  NORMAL yanlis operasyonel-tetik: {fmt_rate_dict(R['normal_dispatch_fp'])}   (dusuk = iyi)")
    print(f"  Normal risk=Dusuk orani        : {fmt_rate_dict(R['risk_cal_norm'])}")
    if lat:
        print(f"  Gecikme medyan                 : {statistics.median(lat):.1f}s  "
              f"(~{statistics.median(persec):.2f}s/video-sn)")
    print("=" * 72)
    print("UYARI: kucuk n'de ust/alt sinir arasi genistir; '%0 FP' ifadesi tek basina")
    print("       kullanilmamalidir (or. 0/6 -> gercek oran %39'a kadar cikabilir).")
    print("=" * 72)

    # --- per-kategori ---
    print("Kategori bazli (recall / kat_eslesme) — n kucuk, CI ile okuyun:")
    per_category = {}
    for cat in CATEGORY_EXPECT:
        cr = [r for r in rows if r["category"] == cat]
        if not cr:
            continue
        rc = rate_from_bools([r["n_events"] > 0 for r in cr])
        cm = rate_from_bools([bool(r["category_match"]) for r in cr if r["is_anomaly"]])
        per_category[cat] = {"recall": rc, "cat_match": cm}
        print(f"  {cat:14s} recall={fmt_rate_dict(rc):26s} kat={fmt_rate_dict(cm)}")

    # --- kaydet ---
    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS_DIR, f"eval_{stamp}.json")
    summary = {
        "n_anomaly": len(anom), "n_normal": len(norm),
        # --- eski duz alanlar (geriye uyumluluk; TEK BASINA raporlanmamali) ---
        "recall": recall, "risk_cal_anom": risk_cal_anom, "cat_match": cat_match_rate,
        # D28/K4: taban cizgisi duz alan olarak da tasinir (compare.py/aggregate.py okuyabilsin)
        "cat_match_eski": R["cat_match_eski"]["p"], "cat_match_grup": R["cat_match_grup"]["p"],
        "cat_match_kural": MATCH_MODE,
        "normal_fp": fp, "normal_fp_operational": op_fp, "normal_dispatch_fp": dispatch_fp,
        "risk_cal_norm": risk_cal_norm,
        "latency_median": statistics.median(lat) if lat else 0,
        # --- K15: ham sayimlar + Wilson %95 guven araliklari ---
        "ci": R,
        "ci_method": "wilson", "ci_level": 0.95,
        "per_category_ci": per_category,
    }
    leak_warning = _warn_if_leaky(EVAL_DIR)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            # K9: sizintili eski set kullanildiysa sonuc dosyasina da yazilir (rapor durustlugu)
            "leak_warning": leak_warning,
            # D36 KOSUM KUNYESI (SALT EKLEME — hicbir metrigi degistirmez):
            # Model degistirilerek A/B yapildiginda, arsivden HANGI MODELLE kosuldugu
            # okunabilmeli. Bu alan olmadan iki arsiv sayisal olarak karsilastirilabilir
            # ama BILIMSEL olarak karsilastirilamaz. Eski arsivlerde alan YOKTUR
            # (None degil, hic yok) -> okuyan taraf .get("kosum") ile ayirt eder;
            # bos sozluk dondurmek "olculdu ve varsayilandi" yalanini soyler.
            "kosum": _kosum_kunyesi(),
            "eval_dir": os.path.relpath(EVAL_DIR, ROOT).replace("\\", "/"),
            "dedup": {  # K10: hangi dosyalar neden sayilmadi
                "enabled": DEDUP,
                "n_input": n_before,
                "n_unique": len(clips),
                "n_skipped": len(dedup_skipped),
                "skipped": dedup_skipped,
            },
            "rows": rows,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nKaydedildi: {os.path.relpath(out, ROOT)}")
    # Nihai dosya YAZILDIKTAN SONRA ara kaydi sil (once silmek, yazma hata verirse
    # her seyi kaybettirirdi). Silinemezse olcum yine de gecerli — sadece uyar.
    try:
        if os.path.exists(ara_yol):
            os.remove(ara_yol)
    except Exception as e:
        print(f"[ARA KAYIT UYARI] silinemedi ({ara_yol}): {e}")


if __name__ == "__main__":
    main()
