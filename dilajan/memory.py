"""Ajan hafizasi (memory) — sartname §7 'memory' agentic-bileseni.

Iki katman:
  1) OTURUM KARAR-GUNLUGU (SESSION_DECISIONS): operatorun diyalogda ONAYLAYIP yurutulen
     operasyonel aksiyonlar. "Az once ne yaptim?" sorusu buradan cevaplanir (B#1 ile esler).
  2) EPISODIK BELLEK (episodes.jsonl): gecmis video analizlerinin ozetleri (zaman/risk/olaylar).
     7/24 operator asistani gecmis olaylara ("bugun kamera-1'de ne oldu") referans verebilir.

Tamamen yerel/offline (dosya tabanli). Fail-open: hata olursa sessizce bos doner."""
from __future__ import annotations

import datetime
import json
import os
from typing import List, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MEM_DIR = os.path.join(_ROOT, "data", "memory")
_EPISODES = os.path.join(_MEM_DIR, "episodes.jsonl")

# --- 1) Oturum karar-gunlugu (in-memory; her yeni analizde sifirlanir) ---
SESSION_DECISIONS: List[dict] = []


def reset_decisions() -> None:
    SESSION_DECISIONS.clear()


def log_decision(function: str, args: dict, result: str) -> dict:
    """Diyalogda onaylanip yurutulen bir operasyonel aksiyonu kaydeder."""
    entry = {
        "function": function,
        "args": args,
        "result": result,
        "ts": datetime.datetime.now().strftime("%H:%M:%S"),
    }
    SESSION_DECISIONS.append(entry)
    return entry


def format_decisions() -> str:
    """Karar-gunlugunu sohbet baglamina uygun metne cevirir (bos ise '')."""
    if not SESSION_DECISIONS:
        return ""
    lines = ["BU OTURUMDA YÜRÜTÜLEN AKSİYONLAR (operatör onayıyla):"]
    lines += [f"  · [{d['ts']}] {d['function']}({', '.join(f'{k}={v}' for k, v in d['args'].items())}) → {d['result']}"
              for d in SESSION_DECISIONS]
    return "\n".join(lines)


# --- 2) Episodik bellek (kalici, JSONL) ---
def append_episode(result, source: Optional[str] = None) -> None:
    """Bir video analizinin kompakt ozetini episodik bellege ekler. Fail-open."""
    try:
        os.makedirs(_MEM_DIR, exist_ok=True)
        ev = [{"time": e.time, "event": e.event, "severity": e.severity.value} for e in result.events[:6]]
        rec = {
            "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": source or "?",
            "risk": result.risk.level.value,
            "summary": result.summary,
            "events": ev,
        }
        with open(_EPISODES, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def recent_episodes(n: int = 5) -> List[dict]:
    """Son n epizodu (en yeni en sonda) dondurur. Fail-open -> []"""
    try:
        if not os.path.exists(_EPISODES):
            return []
        with open(_EPISODES, encoding="utf-8") as f:
            rows = [json.loads(ln) for ln in f if ln.strip()]
        return rows[-n:]
    except Exception:
        return []


def format_episodes(n: int = 5, exclude_source: Optional[str] = None) -> str:
    """Gecmis epizodlari sohbet baglami metnine cevirir (bos ise '')."""
    eps = [e for e in recent_episodes(n + 1) if e.get("source") != exclude_source][-n:]
    if not eps:
        return ""
    lines = ["GEÇMİŞ ANALİZLER (episodik bellek — geçmiş sorulursa kullan):"]
    lines += [f"  · [{e['ts']}] risk={e['risk']} — {e['summary'][:120]}" for e in eps]
    return "\n".join(lines)
