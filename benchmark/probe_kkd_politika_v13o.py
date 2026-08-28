#!/usr/bin/env python
"""v13o: önceki politikasız KKD FP'sinin tek-klip özel API kontrolü."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from benchmark.eval_clips import (  # noqa: E402
    _ozel_api_model_sozlesmesini_dogrula,
    evaluate_clip,
)


_ozel_api_model_sozlesmesini_dogrula()
row = evaluate_clip(
    os.path.join(ROOT, "data/eval_genelleme_v13_dev/Normal/Normal/MEEGwePfDgM_trim_23.mp4"),
    "Normal",
)
print(json.dumps({
    "n_events": row["n_events"],
    "events": [x["event"] for x in row["events"]],
    "isg_trace": row["isg_trace"],
    "accepted": row["n_events"] == 0,
}, ensure_ascii=False, indent=2))
