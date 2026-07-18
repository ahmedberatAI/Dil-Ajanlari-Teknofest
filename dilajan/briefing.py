"""Vardiya devir-teslim brifingi (hizli-kazanim).

Episodik bellegi (data/memory/episodes.jsonl) + oturum karar-gunlugunu tek bir dogal-Turkce
devir-teslim brifingine indirger. SAF DIL isi -> modelin en guclu oldugu yer, algi-tavani yok.

FAIL-OPEN: model sunucusu erisilemezse verilerden DETERMINISTIK bir ozet doner (yine islevsel).
"""
from __future__ import annotations

from typing import List, Optional

from dilajan import memory
from dilajan.llm_client import VLMClient
from dilajan.prompts import SHIFT_BRIEF_PROMPT, SYSTEM_PERSONA

_client: Optional[VLMClient] = None

_RISK_ORD = {"Düşük": 1, "Orta": 2, "Yüksek": 3, "Kritik": 4}


def _get_client() -> VLMClient:
    global _client
    if _client is None:
        _client = VLMClient()
    return _client


def _format_data(episodes: List[dict], decisions: List[dict]) -> str:
    lines = [f"Analiz sayısı: {len(episodes)}"]
    for e in episodes:
        evs = "; ".join(
            f"[{x.get('time', '?')}] {x.get('event', '')} ({x.get('severity', '?')})"
            for x in e.get("events", [])[:4]
        ) or "kayda değer olay yok"
        lines.append(
            f"- [{e.get('ts', '?')}] kaynak={e.get('source', '?')} risk={e.get('risk', '?')} | "
            f"{(e.get('summary', '') or '')[:160]} | olaylar: {evs}"
        )
    if decisions:
        lines.append("Operatör onayıyla yürütülen aksiyonlar:")
        lines += [
            f"  · [{d.get('ts', '?')}] {d.get('function', '?')}"
            f"({', '.join(f'{k}={v}' for k, v in (d.get('args') or {}).items())}) -> {d.get('result', '')}"
            for d in decisions
        ]
    return "\n".join(lines)


def _fallback(episodes: List[dict], decisions: List[dict]) -> str:
    """Model erisilemezse verilerden dogrudan uretilen deterministik brifing (yine islevsel)."""
    ranked = sorted(episodes, key=lambda e: _RISK_ORD.get(e.get("risk", ""), 0), reverse=True)
    worst = ranked[0] if ranked else {}
    lines = [
        "VARDİYA DEVİR-TESLİM BRİFİNGİ",
        f"1) GENEL DURUM: {len(episodes)} analiz kaydı; en yüksek risk seviyesi: {worst.get('risk', '?')}.",
        "2) ÖNE ÇIKAN OLAYLAR:",
    ]
    for e in ranked[:5]:
        lines.append(f"   - [{e.get('ts', '?')}] risk={e.get('risk', '?')} — {(e.get('summary', '') or '')[:120]}")
    if decisions:
        lines.append("3) YÜRÜTÜLEN AKSİYONLAR:")
        lines += [f"   - {d.get('function', '?')} → {d.get('result', '')}" for d in decisions]
    else:
        lines.append("3) YÜRÜTÜLEN AKSİYONLAR: yok")
    lines.append("4) AÇIK / İZLENECEK: manuel gözden geçirme önerilir (otomatik brifing servisine ulaşılamadı).")
    if worst:
        lines.append(f"5) ÖNCELİK: {(worst.get('summary', '') or '')[:120]}")
    return "\n".join(lines)


def generate_shift_briefing(window_hours: float = 8.0) -> str:
    """Son `window_hours` saatlik episodik bellek + oturum aksiyonlarindan devir-teslim brifingi uretir."""
    episodes = memory.episodes_since(window_hours)
    decisions = list(memory.SESSION_DECISIONS)
    if not episodes:
        return f"Son {window_hours:.0f} saatte analiz kaydı bulunmuyor — devredilecek olay yok."
    data = _format_data(episodes, decisions)
    try:
        out = _get_client().chat(
            [{"role": "system", "content": SYSTEM_PERSONA},
             {"role": "user", "content": SHIFT_BRIEF_PROMPT.format(data=data)}],
            temperature=0.2, max_tokens=700,
        ).strip()
        return out or _fallback(episodes, decisions)
    except Exception:
        return _fallback(episodes, decisions)
