"""Diyalog ajani: analiz baglamina dayali, cok-turlu, gercekci ve goreve-bagli sohbet.

Otonomi/diyalog kriterleri (sartname %20): grounding, inisiyatif, aciklayici soru,
baglam-degisimi/prompt-injection direnci, dogal Turkce.
"""
from __future__ import annotations

from typing import List, Optional

from dilajan.llm_client import VLMClient
from dilajan.prompts import CHAT_SYSTEM
from dilajan.schema import AnalysisResult

_client: Optional[VLMClient] = None


def _get_client() -> VLMClient:
    global _client
    if _client is None:
        _client = VLMClient()
    return _client


def build_context(result: AnalysisResult) -> str:
    """AnalysisResult'i sohbet baglam metnine cevirir."""
    lines = [
        f"ÖZET: {result.summary}",
        f"RİSK: {result.risk.level.value} - {result.risk.rationale}",
        f"VİDEO SÜRESİ: {result.video_duration or '?'}",
        "OLAYLAR:",
    ]
    lines += [
        f"  [{e.time}] {e.event} (önem: {e.severity.value}, tür: {e.category.value}"
        + (f", konum: {e.region}" if e.region else "") + ")"
        for e in result.events
    ] or ["  (kayda değer olay yok)"]
    lines.append("AKSİYON ÖNERİLERİ:")
    lines += [f"  - {a.action} (öncelik: {a.priority.value})" for a in result.actions] or ["  (yok)"]
    if result.triggered_functions:
        lines.append("TETİKLENEN OPERASYONEL FONKSİYONLAR: " + ", ".join(result.triggered_functions))
    return "\n".join(lines)


def respond(
    context: str,
    history: Optional[List[dict]],
    message: str,
    max_tokens: int = 400,
) -> str:
    """Bir operatör mesajina, analiz baglami + sohbet gecmisine dayanarak yanit uretir."""
    if not context:
        return ("Önce bir video analiz edin; ardından analizle ilgili sorularınızı "
                "yanıtlayabilir ve aksiyon önerebilirim.")
    messages = [{"role": "system", "content": CHAT_SYSTEM.format(context=context)}]
    for m in history or []:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})
    try:
        return _get_client().chat(messages, temperature=0.3, max_tokens=max_tokens).strip()
    except Exception as ex:
        return f"Yanıt üretilirken hata oluştu: {ex}"
