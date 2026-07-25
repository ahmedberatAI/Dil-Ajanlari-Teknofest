#!/usr/bin/env python
"""benchmark/ground_truth.json URETICISI — DURUST, gercek-klip tabanli ground truth (K7).

NEDEN GEREKTI
-------------
Eski ground_truth.json'da TEK kayit vardi: data/test_clip.mp4 — kareye
"!!! FORKLIFT DEVRILDI !!!" METNI GOMULU sentetik bir PIL karikaturu
(scripts/make_test_video.py urunu). Bir VLM orada video anlama degil OCR yapar;
bu kayit uzerinden alinan her skor sahtedir. Juri-gorunur risk.

NE YAPIYOR
----------
1) Karikatur kaydini (data/test_clip.mp4) KALDIRIR ve neden kaldirildigini _meta'ya yazar.
2) data/ altindaki GERCEK degerlendirme kliplerinden KLIP-DUZEYI GT uretir:
   {dosya: {kategori, anomali, risk_kabul, keywords, kaynak_dataset, ...}}
   Etiket, dataset yayincisinin kategori KLASOR adindan gelir (uydurma degil).
3) MD5 tekillestirme uygular (K10): ayni icerikli klip GT'ye TEK KEZ girer;
   elenenler _meta.dedup altina yazilir.
4) ZAMAN-PENCERESI (temporal) etiketi UYDURMAZ:
   - data/temporal/windows.json = KOMPOZIT-INSA klipleri; splice noktasi tasarim geregi
     KESIN bilinir -> bunlar icin gercek temporal GT yazilir ("temporal_guven": "kesin").
   - Diger tum klipler icin events=[] ve "temporal": "insan-anotasyonu-gerekir".
5) Bilinerek DISLANANLAR (seffaf, _meta.dislanan altinda gerekcesiyle):
   - data/industrial/* : klasor adlari class0..class7, SEMANTIK etiket degil (K14)
   - data/eval_scenario/Fall/lying*.mp4 : tek PNG'nin video'ya sarilmisi, sifir hareket (K8)
     (--include-synthetic ile dahil edilebilir; "sentetik": true damgasiyla)

CIKTI SEMASI (benchmark/evaluate.py ile GERIYE UYUMLU)
-----------------------------------------------------
Duz sozluk: {"_meta": {...}, "<goreli/video/yolu>": {spec}, ...}
"_" ile baslayan anahtarlar metadata'dir; evaluate.py bunlari atlar.

Kullanim:
    python benchmark/build_ground_truth.py
    python benchmark/build_ground_truth.py --out benchmark/ground_truth.json --include-synthetic
"""
from __future__ import annotations

import argparse
import fnmatch
import glob
import json
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from benchmark.dedup import VIDEO_EXTS, dedup_paths, file_md5
    from benchmark.labels import (
        CATEGORY_EXPECT, describe, is_anomaly, keywords_for, origin_for, risk_accept,
    )
except ImportError:  # benchmark/ icinden dogrudan calistirma
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from dedup import VIDEO_EXTS, dedup_paths, file_md5  # type: ignore  # noqa: E402
    from labels import (  # type: ignore  # noqa: E402
        CATEGORY_EXPECT, describe, is_anomaly, keywords_for, origin_for, risk_accept,
    )

DEFAULT_OUT = os.path.join(ROOT, "benchmark", "ground_truth.json")

# Taranacak set kokleri — SIRA ONEMLI: mukerrer icerikte ONCE gelen korunur.
# (eval_big once yazilir; data/eval onun alt kumesi oldugundan tamamen elenir — K9 gorunur olur.)
SCAN_ROOTS: List[str] = [
    "data/eval_big",
    "data/eval_scenario",
    "data/falls_real",
    "data/falls_surveillance",
    "data/e2_vehicle",
    "data/eval_stress",
    "data/eval",
    # Taranir ama EXCLUDE_PREFIXES ile dislanir — dislama gerekcesi _meta'da GORUNUR olsun diye.
    "data/industrial",
]

# GT'ye ALINMAYAN yollar -> gerekce
EXCLUDE_PREFIXES: Dict[str, str] = {
    "data/industrial": (
        "K14: klasor adlari class0..class7 semantik sinif etiketi DEGIL; "
        "guvenli/guvensiz eslesmesi dogrulanmadan etiket uretmek uydurma olur."
    ),
}

# Sentetik (gercek video olmayan) klipler -> DOSYA ADI kalibi + gerekce.
# Klasor yoluna DEGIL dosya adina bakariz: klasorler yeniden duzenlenebiliyor
# (or. gercek klipler eval_scenario/Fall'a tasindi, sentetikler karantinaya alindi),
# ama sentetik urunun adi ureticisiyle birlikte sabit kalir.
SYNTHETIC_PATTERNS: Dict[str, str] = {
    "lying*": (
        "K8: lying*.mp4 tek bir PNG'nin 'ffmpeg -loop 1 -t 3' ile sarilmasidir "
        "(1024x1024, 3.0sn, SIFIR hareket). Video anlama olcmez."
    ),
}

# Karikatur/gomulu-metin kliplerinin KARA LISTESI (asla GT'ye girmez)
BLACKLIST: Dict[str, str] = {
    "data/test_clip.mp4": (
        "K7: scripts/make_test_video.py urunu SENTETIK PIL karikaturu; "
        "kareye '!!! FORKLIFT DEVRILDI !!!' METNI GOMULU. VLM burada video anlama degil "
        "OCR yapar -> olculen sey model yetenegi degil metin okuma."
    ),
}

# temporal kompozit dosya adi -> kategori (scripts/make_composite.py COMPS ile ayni)
COMPOSITE_CATEGORY: Dict[str, str] = {
    "comp_fire": "Fire",
    "comp_explosion": "Explosion",
}


def _rel(path: str) -> str:
    return os.path.relpath(path, ROOT).replace("\\", "/")


def _iter_ext(directory: str) -> List[str]:
    """Dizindeki (alt-dizinsiz) video dosyalari."""
    out: List[str] = []
    for ext in VIDEO_EXTS:
        out.extend(glob.glob(os.path.join(directory, "*" + ext)))
    return out


def _sec_to_mmss(sec: float) -> str:
    sec = max(0, int(round(sec)))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _matches(rel: str, prefixes) -> Optional[str]:
    """rel yolu prefix'lerden birinin altindaysa o prefix'i dondurur."""
    for p in prefixes:
        if rel == p or rel.startswith(p + "/"):
            return p
    return None


def _synthetic_pattern(rel: str) -> Optional[str]:
    """Dosya ADI bilinen bir sentetik-uretim kalibina uyuyorsa o kalibi dondurur."""
    base = os.path.basename(rel)
    for pat in SYNTHETIC_PATTERNS:
        if fnmatch.fnmatch(base, pat):
            return pat
    return None


def collect_clips(include_synthetic: bool = False) -> Tuple[List[Tuple[str, str]], List[dict], List[dict]]:
    """(klip_listesi, atlanan_mukerrerler, dislananlar) dondurur.

    klip_listesi: [(mutlak_yol, kategori), ...] — MD5 tekillestirilmis.
    """
    candidates: List[Tuple[str, str]] = []
    excluded: List[dict] = []

    # Kara listedeki klipler SCAN_ROOTS altinda olmasa da KAYDA GECER — "kaldirildi" izi
    # kalmadan sessizce yok olmasinlar (eski GT'nin tek kaydi buydu).
    for rel, sebep in BLACKLIST.items():
        if os.path.exists(os.path.join(ROOT, rel)):
            excluded.append({"path": rel, "sebep": sebep, "eski_gt_kaydiydi": True})

    for root_rel in SCAN_ROOTS:
        root_abs = os.path.join(ROOT, root_rel)
        if not os.path.isdir(root_abs):
            continue
        for cat in sorted(os.listdir(root_abs)):
            cat_dir = os.path.join(root_abs, cat)
            if not os.path.isdir(cat_dir):
                continue
            # Klasor adi BILINEN bir sinif degilse etiket URETME. Karantina/calisma klasorleri
            # (or. "_deprecated_frozen_fall") ya da anlamsiz adlar (class0..7) sinif DEGILDIR;
            # bunlari "anomali" varsayarak GT'ye almak tam olarak kacindigimiz uydurmadir.
            # (Ozel gerekce tanimliysa EXCLUDE_PREFIXES metni kullanilir — daha bilgilendirici.)
            if cat not in CATEGORY_EXPECT:
                generic = (f"'{cat}' klasor adi bilinen bir sinif etiketi DEGIL "
                           f"(bilinen sinif: {', '.join(sorted(CATEGORY_EXPECT))}); "
                           f"etiket uydurulmadi.")
                for p in sorted(_iter_ext(cat_dir)):
                    rel = _rel(p)
                    ex = _matches(rel, EXCLUDE_PREFIXES)
                    excluded.append({"path": rel,
                                     "sebep": EXCLUDE_PREFIXES[ex] if ex else generic})
                continue
            for p in sorted(_iter_ext(cat_dir)):
                rel = _rel(p)
                if rel in BLACKLIST:
                    continue  # zaten yukarida kayda gecti
                ex = _matches(rel, EXCLUDE_PREFIXES)
                if ex:
                    excluded.append({"path": rel, "sebep": EXCLUDE_PREFIXES[ex]})
                    continue
                syn = _synthetic_pattern(rel)
                if syn and not include_synthetic:
                    excluded.append({"path": rel, "sebep": SYNTHETIC_PATTERNS[syn],
                                     "sentetik": True})
                    continue
                candidates.append((p, cat))

    # --- MD5 tekillestirme (K10) ---
    kept_paths, skipped = dedup_paths([p for p, _ in candidates], rel_to=ROOT)
    kept_set = set(kept_paths)
    clips = [(p, c) for p, c in candidates if p in kept_set]
    return clips, skipped, excluded


def temporal_entries() -> Dict[str, dict]:
    """data/temporal/windows.json'dan KESIN bilinen olay pencerelerini GT kaydina cevirir.

    Bu pencereler KOMPOZIT-INSA yoluyla olusur (normal|OLAY|normal splice); baslangic/bitis
    saniyeleri tasarim geregi bilinir -> gercek temporal ground truth. UYDURMA DEGIL.
    """
    wpath = os.path.join(ROOT, "data", "temporal", "windows.json")
    out: Dict[str, dict] = {}
    if not os.path.exists(wpath):
        return out
    try:
        with open(wpath, encoding="utf-8") as f:
            windows = json.load(f)
    except Exception:
        return out  # FAIL-OPEN: bozuksa temporal GT uretme

    for fname, spec in sorted(windows.items()):
        vid = os.path.join(ROOT, "data", "temporal", fname)
        if not os.path.exists(vid):
            continue
        stem = os.path.splitext(fname)[0]
        cat = COMPOSITE_CATEGORY.get(stem)
        if cat is None:
            continue  # kategori bilinmiyorsa etiket UYDURMA
        rel = _rel(vid)
        start = float(spec.get("event_start", 0))
        end = float(spec.get("event_end", 0))
        if end <= start:
            continue
        org = origin_for(rel)
        out[rel] = {
            "kategori": cat,
            "kategori_tr": describe(cat),
            "anomali": True,
            "risk_kabul": risk_accept(cat),
            "keywords": keywords_for(cat),
            "kaynak_dataset": org["dataset"],
            "kaynak_not": org["not"],
            "md5": file_md5(vid),
            "sure_s": float(spec.get("total", 0)) or None,
            "temporal": "kompozit-insa",
            "temporal_guven": "kesin",
            "temporal_not": (
                f"normal|OLAY|normal splice; olay parcasi kaynagi: "
                f"{spec.get('event_source', '?')}. Pencere tasarim geregi bilinir."
            ),
            "events": [{
                "window": [_sec_to_mmss(start), _sec_to_mmss(end)],
                "keywords": keywords_for(cat),
                "severity": "Yüksek",
                "critical": True,
            }],
        }
    return out


def build(include_synthetic: bool = False) -> dict:
    clips, skipped, excluded = collect_clips(include_synthetic)

    gt: Dict[str, dict] = {}
    # 1) temporal (kesin pencereli) kayitlar once
    temporal = temporal_entries()
    gt.update(temporal)

    # 2) klip-duzeyi kayitlar
    n_anom = n_norm = n_syn = 0
    per_cat: Dict[str, int] = {}
    for path, cat in clips:
        rel = _rel(path)
        anom = is_anomaly(cat)
        org = origin_for(rel)
        entry = {
            "kategori": cat,
            "kategori_tr": describe(cat),
            "anomali": anom,
            "risk_kabul": risk_accept(cat),
            "keywords": keywords_for(cat),
            "kaynak_dataset": org["dataset"],
            "kaynak_not": org["not"],
            "md5": file_md5(path),
            "temporal": "insan-anotasyonu-gerekir",
            "temporal_guven": "yok",
            "temporal_not": (
                "Bu klip icin olay baslangic/bitis saniyesi BILINMIYOR. Klip-duzeyi etiket "
                "(kategori/anomali) dataset klasorunden gelir; zaman penceresi UYDURULMAMISTIR. "
                "Temporal metrik icin insan anotasyonu gerekir."
            ),
            "events": [],
        }
        syn = _synthetic_pattern(rel)
        if syn:
            entry["sentetik"] = True
            entry["sentetik_not"] = SYNTHETIC_PATTERNS[syn]
            n_syn += 1
        gt[rel] = entry
        per_cat[cat] = per_cat.get(cat, 0) + 1
        n_anom += int(anom)
        n_norm += int(not anom)

    for rel, e in temporal.items():
        per_cat[e["kategori"]] = per_cat.get(e["kategori"], 0) + 1
        n_anom += 1

    meta = {
        "sema_surumu": 2,
        "uretici": "benchmark/build_ground_truth.py",
        "uretildi": time.strftime("%Y-%m-%d %H:%M:%S"),
        "aciklama": (
            "Klip-duzeyi ground truth. Etiket kaynagi: dataset yayincisinin kategori KLASOR "
            "adi. Zaman-penceresi etiketi YALNIZCA kompozit-insa kliplerde vardir (splice "
            "noktasi tasarim geregi bilinir); diger tum kliplerde events=[] ve temporal alani "
            "'insan-anotasyonu-gerekir' olarak isaretlidir."
        ),
        "durustluk_notlari": [
            "K7: sentetik karikatur data/test_clip.mp4 GT'den KALDIRILDI (gerekce: _meta.dislanan).",
            "K10: ayni MD5'e sahip klipler TEK KEZ sayilir; elenenler _meta.dedup.atlananlar.",
            "K9: data/eval, data/eval_big'in alt kumesidir; dedup sonrasi tamamen elenir.",
            "Temporal metrik yalnizca _meta.sayimlar.temporal_kesin kadar klipte MESRUDUR.",
        ],
        "risk_politikasi": (
            "Tek bir 'dogru' risk seviyesi iddia edilmez; 'risk_kabul' KABUL EDILEBILIR "
            "seviyeler listesidir (anomali -> Yüksek/Kritik, normal -> Düşük)."
        ),
        "sayimlar": {
            "toplam_klip": len(gt),
            "anomali": n_anom,
            "normal": n_norm,
            "sentetik_dahil": n_syn,
            "temporal_kesin": len(temporal),
            "temporal_anotasyonsuz": len(gt) - len(temporal),
            "kategori_bazli": dict(sorted(per_cat.items())),
        },
        "dedup": {
            "yontem": "MD5 (birebir icerik esitligi)",
            "n_atlanan": len(skipped),
            "atlananlar": skipped,
        },
        "dislanan": excluded,
        "sentetik_dahil_edildi": bool(include_synthetic),
    }
    return {"_meta": meta, **gt}


def main() -> None:
    ap = argparse.ArgumentParser(description="Durust klip-duzeyi ground truth uretici (K7)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="cikti JSON yolu")
    ap.add_argument("--include-synthetic", action="store_true",
                    help="sentetik (donmus-PNG) Fall kliplerini de dahil et; 'sentetik':true damgali")
    args = ap.parse_args()

    gt = build(include_synthetic=args.include_synthetic)
    meta = gt["_meta"]

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(gt, f, ensure_ascii=False, indent=2)

    s = meta["sayimlar"]
    print("=" * 70)
    print("GROUND TRUTH URETILDI (K7)")
    print("=" * 70)
    print(f"  Cikti                    : {_rel(os.path.abspath(args.out))}")
    print(f"  Toplam klip              : {s['toplam_klip']}  "
          f"(anomali={s['anomali']}, normal={s['normal']})")
    print(f"  Temporal GT KESIN        : {s['temporal_kesin']} klip (kompozit-insa)")
    print(f"  Temporal anotasyonsuz    : {s['temporal_anotasyonsuz']} klip "
          f"(events=[], insan anotasyonu gerekir)")
    print(f"  MD5 mukerrer elendi      : {meta['dedup']['n_atlanan']}")
    print(f"  Dislanan (etiket/sentetik/karikatur): {len(meta['dislanan'])}")
    print("-" * 70)
    print("  Kategori bazli:")
    for c, n in s["kategori_bazli"].items():
        print(f"    {c:16s} n={n}")
    print("-" * 70)
    print("  KALDIRILAN karikatur kayitlari:")
    for e in meta["dislanan"]:
        if e["path"] in BLACKLIST:
            print(f"    {e['path']}\n      -> {e['sebep']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
