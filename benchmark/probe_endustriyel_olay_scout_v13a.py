#!/usr/bin/env python
"""v13a: yeni dev FN'lerinde dar endüstriyel olay scout + atomik kapı."""
from __future__ import annotations

import concurrent.futures
import json
import os
import statistics
import sys
import time


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from benchmark.eval_clips import _ozel_api_model_sozlesmesini_dogrula  # noqa: E402
from dilajan.isg_kanit import ATOMIK_SISTEM, Hukum, dogrula  # noqa: E402
from dilajan.llm_client import VLMClient  # noqa: E402
from dilajan.video import extract_timestamped_frames  # noqa: E402


BASELINE = os.path.join(ROOT, "benchmark", "results", "eval_20260827_223953.json")
RESULTS = os.path.join(ROOT, "benchmark", "results")
POSITIVES = {
    "0QHQ2nmdE78_clip0_trim_4.mp4": "MAKINE_YAKALAMA",
    "1b1NOLpwCz8_trim_16.mp4": "DUSEN_AGIR_YUK",
    "1b1NOLpwCz8_trim_4.mp4": "DUSEN_AGIR_YUK",
    "1s2Tcqr3Rgg_trim_15.mp4": "ARAC_KONTROL_KAYBI",
    "1s2Tcqr3Rgg_trim_111.mp4": "DUSEN_AGIR_YUK",
    "1s2Tcqr3Rgg_trim_84.mp4": "DUSEN_AGIR_YUK",
    "2uuwpx1ykPQ_trim_0.mp4": "ALEV_DUMAN_GAZ",
    "6ZrAeC5mZ5w_trim_1.mp4": "MAKINE_ARIZASI",
    "6fhnKhZQE4o_trim_3.mp4": "MAKINE_ARIZASI",
    "7QFdUqCdML8_trim_1.mp4": "MAKINE_YAKALAMA",
    "87O1pBSGtR0_trim_102.mp4": "KISI_DESTEK_KAYBI",
    "8t1ci0ezwP8_trim_2.mp4": "KISI_DESTEK_KAYBI",
    "9XXineiOxSo_trim_5.mp4": "MAKINE_YAKALAMA",
    "H4sC0QCkG7I_trim_301.mp4": "ALEV_DUMAN_GAZ",
    "Zag5F6FXlj0_trim_3.mp4": "MAKINE_YAKALAMA",
    "_a46_s5WViY_trim_1.mp4": "MAKINE_YAKALAMA",
    "fs0TzsV5NgU_trim_5.mp4": "DUSEN_AGIR_YUK",
    "fs0TzsV5NgU_trim_6.mp4": "DUSEN_AGIR_YUK",
    "iFbIfo_vBfA_trim_0.mp4": "ARAC_KONTROL_KAYBI",
    "qJLf_5RJFG8_trim_3.mp4": "ALEV_DUMAN_GAZ",
    "uOAJL-g4Y_w_trim_1.mp4": "KISI_DESTEK_KAYBI",
    "zJqzjDX-XFU_trim_45.mp4": "KISI_DESTEK_KAYBI",
}
CHOICES = ("MAKINE_YAKALAMA", "DUSEN_AGIR_YUK", "KISI_DESTEK_KAYBI",
           "ALEV_DUMAN_GAZ", "ARAC_KONTROL_KAYBI", "MAKINE_ARIZASI",
           "OLAY_YOK", "GORUNMUYOR")
FAMILIES = {
    "MAKINE_YAKALAMA": "aktif makine yakalama/sıkışma",
    "DUSEN_AGIR_YUK": "üstten düşen ağır yük/pres",
    "KISI_DESTEK_KAYBI": "kişi destek kaybı/düşme",
    "ALEV_DUMAN_GAZ": "yangın/duman/basınçlı gaz",
    "ARAC_KONTROL_KAYBI": "kontrolünü kaybeden araç",
    "MAKINE_ARIZASI": "makine arızası/parça fırlaması",
}
SCAN_PROMPT = (
    "Bu kısa videoyu kronolojik incele; yalnız doğrudan görülen en belirgin fiziksel "
    "endüstriyel olayı seç. MAKINE_YAKALAMA: beden/uzuv/giysi hareketli makine, konveyör, "
    "pres veya kapanan yüzeye çekilir/sıkışır. DUSEN_AGIR_YUK: ağır yük/platform/pres "
    "kontrolsüz düşer, kayar veya insanların üstüne iner. KISI_DESTEK_KAYBI: kişi kayar, "
    "düşer ya da ayak desteğini kaybedip asılı kalır. ALEV_DUMAN_GAZ: gerçek alev, "
    "yayılan yoğun duman veya basınçlı gaz salımı vardır. ARAC_KONTROL_KAYBI: araç/iş "
    "makinesi savrulur, devrilir, çarpar veya kontrolsüz döner. MAKINE_ARIZASI: makine "
    "aniden şiddetle sallanır, cam/parça kırılır, kopar veya fırlar. Rutin çalışma, "
    "kontrollü indirme, normal titreşim/buhar/egzoz ve yalnız niyet tahmini olay değildir. "
    "Hiçbiri açık değilse OLAY_YOK; görüntü yetersizse GORUNMUYOR. Yalnız etiketi yaz."
)


def _items():
    with open(BASELINE, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for row in data["rows"]:
        name = os.path.basename(row["path"])
        positive = name in POSITIVES
        # Fiziksel hedef olmayan olay-sız tehlikeler de kasıtlı karşıt negatiftir.
        contrast = row["is_anomaly"] and not row["n_events"] and not positive
        normal_tn = not row["is_anomaly"] and not row["n_events"]
        if positive or contrast or normal_tn:
            out.append({"path": os.path.join(ROOT, row["path"]),
                        "rel_path": row["path"], "positive": positive,
                        "contrast_negative": bool(contrast),
                        "target": POSITIVES.get(name)})
    return out


def _run(item):
    start = time.perf_counter()
    frames, _ = extract_timestamped_frames(item["path"])
    root = VLMClient()
    errors = {}
    selected = ""
    try:
        selected = root.gorev("olay").analyze_frames(
            frames, SCAN_PROMPT, temperature=0.0, max_tokens=24,
            system=ATOMIK_SISTEM, guided_choice=CHOICES).strip().upper()
    except Exception as ex:
        errors["scan"] = f"{type(ex).__name__}: {ex}"
    family = FAMILIES.get(selected)
    result = None
    if family and not errors:
        result = dogrula(root, frames, family)
        if result.hatalar:
            errors["evidence"] = result.hatalar
    supported = bool(result and result.hukum == Hukum.SUPPORTED and not errors)
    return {**{k: v for k, v in item.items() if k != "path"},
            "selected": selected, "family": family, "supported": supported,
            "prediction": result.hukum.value if result else None,
            "answers": result.cevaplar if result else {}, "errors": errors,
            "latency_s": round(time.perf_counter() - start, 2)}


def main() -> int:
    contract = _ozel_api_model_sozlesmesini_dogrula()
    items = _items()
    pos = [x for x in items if x["positive"]]
    neg = [x for x in items if not x["positive"]]
    contrasts = sum(x["contrast_negative"] for x in neg)
    if (len(pos), len(neg), contrasts) != (22, 109, 13):
        raise RuntimeError(
            f"Ön kayıt örneklemi değişti: pos={len(pos)} neg={len(neg)} contrast={contrasts}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, items))
    pos_rows = [x for x in rows if x["positive"]]
    neg_rows = [x for x in rows if not x["positive"]]
    recovered = sum(x["supported"] for x in pos_rows)
    target_supported = sum(x["supported"] and x["selected"] == x["target"]
                           for x in pos_rows)
    fp = sum(x["supported"] for x in neg_rows)
    errors = sum(bool(x["errors"]) for x in rows)
    summary = {"positive": len(pos_rows), "negative": len(neg_rows),
               "contrast_negative": contrasts, "recovered": recovered,
               "target_supported": target_supported, "new_fp": fp,
               "errors": errors,
               "latency_median": statistics.median(x["latency_s"] for x in rows),
               "accepted": recovered >= 8 and target_supported >= 8
                           and fp <= 1 and errors == 0}
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"endustriyel_olay_scout_v13a_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"contract": contract, "baseline": os.path.relpath(BASELINE, ROOT),
                   "summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(os.path.relpath(out, ROOT).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
