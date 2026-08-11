"""LangGraph ajan durumu (state)."""
from __future__ import annotations

from typing import List, Optional, TypedDict

from dilajan.schema import Action, AnalysisResult, Event, RiskAssessment
from dilajan.video import Segment, VideoInfo


class AgentState(TypedDict, total=False):
    # Girdi
    video_path: str

    # canli/decode-once: onceden cikarilmis (zaman, jpeg) kareler + VideoInfo.
    # Verilirse ingest videoyu YENIDEN decode etmez (canli akista mp4 ara-adimini atlar).
    prebuilt_frames: List
    prebuilt_info: Optional[VideoInfo]

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

    # SORGU-GUDUMLU ANALIZ (opsiyonel): operatorun serbest-metin sorgusuna (settings.analysis_query)
    # verilen dogrudan Turkce yanit. Sorgu girilmediyse bu kanal HIC yazilmaz (None kalir).
    # NOT: LangGraph, durum semasinda TANIMSIZ anahtarlari SESSIZCE DUSURUR -> reason'un
    # dondurdugu deger finalize'a ulassin diye alan burada gercek bir KANAL olarak tanimlidir.
    query_answer: Optional[str]

    # KANIT SORULARI (ASK-HINT) — ALARM MUHAFIZI BAYRAGI.
    # Kanit sorulari ve uretilen kategori ipucu `perceive` ICINDE tuketilir; DISARI cikan
    # TEK bilgi budur: "en az bir olayin ADI kanitla yeniden yazildi mi?".
    # NEDEN GEREKLI (adversaryel denetimde OLCULDU): yeniden adlandirilmis metin `reason`
    # tarafindan okunur ve risk seviyesini yukseltebilir; risk >= Yuksek ise `act` sevk
    # kapisini acar. Bu bayrakla `act` RISK terimini maskeler (var olan `risk_recall_bias`
    # deseninin AYNISI) -> sevk YALNIZ olay-severity'sine baglanir, o da `evidence_prev`
    # muhafiziyla kanit-oncesi metne baglidir.
    # LangGraph semada TANIMSIZ anahtarlari SESSIZCE DUSURUR (yukaridaki `query_answer`
    # notu) -> bayrak burada GERCEK bir kanal olarak tanimlidir. Ozellik kapaliyken
    # HER ZAMAN False'tur; `act` cebirsel olarak eski satira indirgenir.
    evidence_renamed: bool

    # act cikti (mock fonksiyon cagrilari)
    triggered_functions: List[str]
    action_log: List[dict]

    # finalize
    result: Optional[AnalysisResult]

    # adaptif yeniden-inceleme dongu muhafizi
    reexamined: bool

    # izlenebilirlik / hata toleransi
    trace: List[str]
