"""Yeni video yuklemesinin onceki video durumunu tasimadigini dogrular."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch


KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

import tests.taban as taban  # noqa: E402

taban.taban_uygula()

import app  # noqa: E402
from dilajan import chat_agent, memory  # noqa: E402
from dilajan.schema import AnalysisResult, RiskAssessment, Severity  # noqa: E402


class VideoUploadIsolationTests(unittest.TestCase):
    def tearDown(self):
        memory.reset_decisions()

    def test_upload_reset_clears_every_video_scoped_value(self):
        memory.log_decision("ekip_cagir", {"birim": "saglik"}, "ok")

        values = app._reset_for_new_video()

        self.assertEqual(len(values), 20)
        self.assertEqual(memory.SESSION_DECISIONS, [])
        self.assertEqual(values[2], "")        # summary
        self.assertEqual(values[6], [])        # event table
        self.assertEqual(values[10], "")       # raw JSON
        self.assertEqual(values[11], "")       # chat context State
        self.assertIsNone(values[12])          # AnalysisResult State
        self.assertEqual(values[13], "")       # analyzed video path State
        self.assertEqual(values[14], [])       # chatbot history
        self.assertEqual(values[15], "")       # chat draft
        self.assertEqual(values[16], "")       # report
        self.assertIsNone(values[17])          # evidence files
        self.assertEqual(values[18], "")       # rendered briefing
        self.assertEqual(values[19], "")       # per-video analysis query

    def test_single_video_chat_context_excludes_episodic_history(self):
        result = AnalysisResult(
            summary="Yalnizca ikinci video",
            risk=RiskAssessment(level=Severity.DUSUK, rationale="Olay yok"),
        )
        sentinel = "BIRINCI_VIDEO_GECMISI"

        with patch.object(memory, "format_episodes", return_value=sentinel) as formatted:
            isolated = chat_agent.build_context(result, include_history=False)
            historical = chat_agent.build_context(result, include_history=True)

        self.assertNotIn(sentinel, isolated)
        self.assertIn(sentinel, historical)
        self.assertEqual(formatted.call_count, 1)

    def test_ui_binds_reset_before_video_transcode(self):
        demo = app.build_ui()
        config = demo.get_config_file()
        api_names = [str(dep.get("api_name", "")) for dep in config.get("dependencies", [])]

        reset_idx = next(i for i, name in enumerate(api_names) if "reset_for_new_video" in name)
        transcode_idx = next(i for i, name in enumerate(api_names) if "ensure_playable" in name)
        transcode = config["dependencies"][transcode_idx]

        self.assertLess(reset_idx, transcode_idx)
        self.assertEqual(transcode.get("trigger_after"), reset_idx)


if __name__ == "__main__":
    unittest.main(verbosity=2)
