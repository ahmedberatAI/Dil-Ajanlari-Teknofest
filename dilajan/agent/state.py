"""LangGraph ajan durumu (state)."""
from __future__ import annotations

from typing import List, Optional, TypedDict

from dilajan.schema import Action, AnalysisResult, Event, RiskAssessment
from dilajan.video import Segment, VideoInfo


class AgentState(TypedDict, total=False):
    # Girdi
    video_path: str

    # ingest cikti
    segments: List[Segment]
    video_info: VideoInfo
    scene_cuts: List[float]  # M3: sert sahne-kesimi zaman-damgalari (kopuk/spliced bolumler)

    # perceive cikti (segment bazli birikimli olaylar)
    events: List[Event]

    # reason cikti
    summary: str
    risk: RiskAssessment
    actions: List[Action]

    # act cikti (mock fonksiyon cagrilari)
    triggered_functions: List[str]
    action_log: List[dict]

    # finalize
    result: Optional[AnalysisResult]

    # adaptif yeniden-inceleme dongu muhafizi
    reexamined: bool

    # izlenebilirlik / hata toleransi
    trace: List[str]
