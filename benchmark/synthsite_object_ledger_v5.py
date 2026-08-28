#!/usr/bin/env python
"""SynthSite v5: karar sözcüksüz nesne-merkezli kanıt defteri."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from benchmark.synthsite_atomik_v2 import (  # noqa: E402
    ATOMIK_SISTEM, DATA_ROOT, RESULTS, _development_subset, _sha_file,
    model_sozlesmesini_dogrula, puanla, tier1_etiketleri,
)
from benchmark.synthsite_ledger_v4 import (  # noqa: E402
    JUDGE_CHOICES, JUDGE_SYSTEM, _combine, _judge_prediction, _rotated_choices,
)
from dilajan.llm_client import VLMClient  # noqa: E402

REVISION = "synthsite-object-ledger-v5"
SCHEMA = {
    "type": "object",
    "properties": {
        "tasınan_nesne": {"type": "string", "maxLength": 320},
        "en_yakin_calisan": {"type": "string", "maxLength": 320},
        "arada_gorulen_nesneler": {"type": "string", "maxLength": 320},
        "zaman_icindeki_degisim": {"type": "string", "maxLength": 320},
        "secilemeyen_ana_ayrinti": {"type": "string", "maxLength": 200},
    },
    "required": ["tasınan_nesne", "en_yakin_calisan", "arada_gorulen_nesneler",
                 "zaman_icindeki_degisim", "secilemeyen_ana_ayrinti"],
    "additionalProperties": False,
}
PROMPT = (
    "Yalnız nesne-merkezli video betimi yap; risk, ISG, tehlike, ihlal, güvenli, "
    "düşme bölgesi, altında veya yanında sözcüklerini KULLANMA. Bir karar verme. "
    "Videonun başlangıç, orta ve sonunu karşılaştır. Taşınan katı nesnenin rengi/"
    "biçimi, ekrandaki sol-merkez-sağ ve üst-orta-alt konumu, neye bağlı/değiyor "
    "olduğu ve hareketini tam cümleyle yaz. Ona ekranda en yakın çalışanın ayak/"
    "gövde ekran konumunu ve hareketini ayrı yaz. Bu ikisinin arasındaki kadraj "
    "bölgesinde görülen korkuluk, bariyer, duvar, araç, istif veya boşluğu nesne "
    "adı ve ekran konumuyla yaz; hiçbir ayırıcı nesne seçilmiyorsa bunu açık cümleyle "
    "söyle. Zaman içindeki değişimi gerçek anları karşılaştırarak yaz. Sahne türünden "
    "ilişki varsayma; görünmeyen tek ana ayrıntıyı son alana yaz."
)
JUDGE_PROMPT = (
    "Aşağıdaki nesne-merkezli defterden yalnız bu kuralı ölç: katı yük gerçekten "
    "havada asılı; en yakın çalışanın ekran/derinlik konumu yük dikey inse erişeceği "
    "bölgede; arada fiziksel ayırıcı yok; ilişki en az 1 saniye.\n"
    "ACIK_KARSI_KANIT yalnız defter açıkça şu olgulardan birini betimliyorsa: yük "
    "zemin/araç/istife değiyor; çalışan yatay olarak ayrı veya belirgin ön/arka "
    "plandadır; adlandırılmış bariyer/korkuluk/duvar ikisinin arasındadır; ilişki "
    "bir saniyeden kısadır. KANIT_UYUMLU yalnız dört koşul da açıkça destekleniyorsa. "
    "Kadraj konumları veya süre eksik/çelişkiliyse KANIT_YETERSIZ. Videoyu görmediğin "
    "için defter dışı tahmin yapma.\n\nNESNE DEFTERI:\n{ledger}"
)


def _probe(item: dict, base: dict) -> dict:
    path = DATA_ROOT / "videos" / item["filename"]
    t0 = time.perf_counter(); raw = None; ledger_error = None; judge_raw = None; judge_error = None
    try:
        client = VLMClient().gorev("algi")
        session = client.video_oturumu(str(path), system=ATOMIK_SISTEM,
                                       giris_metni="Tarafsız nesne-merkezli video betimi.")
        raw = session.sor(PROMPT, temperature=0.0, max_tokens=360, hatirla=False,
                          json_schema=SCHEMA, schema_name="nesne_kanit_defteri")
        ledger_error = session.hata
        if not ledger_error:
            json.loads(raw or "")
    except Exception as exc:
        ledger_error = f"{type(exc).__name__}: {exc}"
    judge = "error"
    if raw and not ledger_error:
        try:
            llm = VLMClient().gorev("olay")
            judge_raw = llm.chat([
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": JUDGE_PROMPT.format(ledger=raw)},
            ], temperature=0.0, max_tokens=12,
                guided_choice=_rotated_choices(item["filename"]))
        except Exception as exc:
            judge_error = f"{type(exc).__name__}: {exc}"
        judge = _judge_prediction(judge_raw, judge_error)
    return {**item, "generator": base["generator"], "video_sha256": base["video_sha256"],
            "base_prediction": base["prediction"], "base_answers": base["answers"],
            "ledger": raw, "ledger_error": ledger_error, "judge": judge,
            "judge_raw": judge_raw, "judge_error": judge_error,
            "prediction": _combine(base["prediction"], judge),
            "latency_s": round(time.perf_counter() - t0, 3)}


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--base", required=True)
    ap.add_argument("--workers", type=int, default=4); args = ap.parse_args()
    contract = model_sozlesmesini_dogrula(); base_path = Path(args.base)
    base_doc = json.loads(base_path.read_text(encoding="utf-8"))
    base_rows = {r["filename"]: r for r in base_doc["rows"]}
    items = _development_subset(tier1_etiketleri(), len(base_rows))
    if set(base_rows) != {x["filename"] for x in items}:
        raise RuntimeError("v2 tabanı ile geliştirme dilimi eşleşmiyor")
    key_src = json.dumps({"rev": REVISION, "base": _sha_file(base_path), "prompt": PROMPT,
                          "schema": SCHEMA, "judge": JUDGE_PROMPT, "contract": contract},
                         ensure_ascii=False, sort_keys=True)
    key = hashlib.sha256(key_src.encode()).hexdigest()[:12]
    journal = RESULTS / f".synthsite_object_ledger_v5_{key}.jsonl"; done = {}
    if journal.exists():
        for line in journal.read_text(encoding="utf-8").splitlines():
            try: row = json.loads(line)
            except json.JSONDecodeError: continue
            if row.get("filename"): done[row["filename"]] = row
    pending = [x for x in items if x["filename"] not in done]
    print(f"SynthSite object-ledger v5: n={len(items)}, kalan={len(pending)}, workers={args.workers}")
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        fs = {pool.submit(_probe, x, base_rows[x["filename"]]): x for x in pending}
        for i, f in enumerate(as_completed(fs), 1):
            row = f.result(); done[row["filename"]] = row
            with journal.open("a", encoding="utf-8") as h:
                h.write(json.dumps(row, ensure_ascii=False) + "\n"); h.flush(); os.fsync(h.fileno())
            print(f"[{i}/{len(pending)}] {row['filename']}: {row['judge']} => "
                  f"{row['prediction']} ({row['latency_s']}s)")
    rows = [done[x["filename"]] for x in items]; metrics = puanla(rows)
    out = {"benchmark": "SynthSite object-ledger v5 development",
           "created_at": datetime.now().astimezone().isoformat(),
           "development_only": True, "independent_holdout": False,
           "base_result": str(base_path), "base_sha256": _sha_file(base_path),
           "inference": {"learned_inference": "special_api_only", "model_contract": contract,
                         "pipeline_revision": REVISION, "ledger_prompt": PROMPT,
                         "ledger_schema": SCHEMA, "judge_prompt": JUDGE_PROMPT,
                         "decision": "v2 AND object-ledger judge"},
           "metrics": metrics, "rows": rows}
    target = RESULTS / f"synthsite_object_ledger_v5_{datetime.now():%Y%m%d_%H%M%S}.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2)); print(target)


if __name__ == "__main__": main()
