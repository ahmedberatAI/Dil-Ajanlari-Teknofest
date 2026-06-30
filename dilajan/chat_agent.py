"""Diyalog ajani: analiz baglamina dayali, cok-turlu, gercekci ve goreve-bagli sohbet.

Otonomi/diyalog kriterleri (sartname %20): grounding, inisiyatif, aciklayici soru,
baglam-degisimi/prompt-injection direnci, dogal Turkce.
"""
from __future__ import annotations

import re
from typing import List, Optional

from dilajan import memory
from dilajan.llm_client import VLMClient
from dilajan.mock_functions import ALL_TOOLS, TOOL_REGISTRY
from dilajan.prompts import CHAT_EXECUTE_PROMPT, CHAT_SYSTEM
from dilajan.schema import AnalysisResult
from dilajan.utils import extract_json

_client: Optional[VLMClient] = None

# B#1: operatör ONAYI sinyalleri -> kapili icra denetimini tetikler (cheap ön-filtre; asil kapi LLM-cikarim).
# Türkçe sondan-eklemeli oldugu icin SADECE bas-sinir (\b)+kok kullaniriz (ör. 'onay' -> onayla/onaylandi).
_CONFIRM_RE = re.compile(
    r"\b(evet|onay|tamam|gönder|gonder|sevk|çağır|cagir|uygula|başlat|baslat|tetikle|hallet|olur|devam et)",
    re.IGNORECASE)


def _tools_desc() -> str:
    """Mock fonksiyonlarin kompakt listesi (icra-cikarim prompt'u icin)."""
    out = []
    for t in ALL_TOOLS:
        args = ", ".join(getattr(t, "args", {}).keys())
        desc = (getattr(t, "description", "") or "").strip().split("\n")[0]
        out.append(f"- {t.name}({args}): {desc}")
    return "\n".join(out)


def _get_client() -> VLMClient:
    global _client
    if _client is None:
        _client = VLMClient()
    return _client


def build_context(result: AnalysisResult) -> str:
    """AnalysisResult'i sohbet baglam metnine cevirir."""
    # B#2: grounded algi-guveni (cozunurluk advisory'sinden) -> asistan "ne kadar eminsin?"e durust cevap verir
    low_q = any(("çözünürlük" in a.action.lower() or "manuel teyit" in a.action.lower())
                for a in result.actions)
    algi = ("DÜŞÜK — düşük çözünürlük; ayrıntı-kesinliği sınırlı, kritik olaylarda manuel teyit önerilir"
            if low_q else "normal")
    lines = [
        f"ÖZET: {result.summary}",
        f"RİSK: {result.risk.level.value} - {result.risk.rationale}",
        f"ALGI GÜVENİ: {algi}",
        f"VİDEO SÜRESİ: {result.video_duration or '?'}",
        "OLAYLAR:",
    ]
    lines += [
        f"  [{e.time}{('–' + e.end_time) if e.end_time else ''}] {e.event} "
        f"(önem: {e.severity.value}, tür: {e.category.value}"
        + (f", konum: {e.region}" if e.region else "") + ")"
        for e in result.events
    ] or ["  (kayda değer olay yok)"]
    lines.append("AKSİYON ÖNERİLERİ:")
    lines += [f"  - {a.action} (öncelik: {a.priority.value})" for a in result.actions] or ["  (yok)"]
    if result.triggered_functions:
        lines.append("TETİKLENEN OPERASYONEL FONKSİYONLAR: " + ", ".join(result.triggered_functions))
    # C#1: karar-izi (aciklanabilirlik) -> operatör "neden bu karar?" diye sorarsa dayanak
    if result.decision_trace:
        lines.append("KARAR İZİ (açıklanabilirlik — operatör sorarsa bu adımlara dayan):")
        lines += [f"  · {t}" for t in result.decision_trace]
    # Memory: episodik bellek (gecmis analizler) -> "gecmiste ne oldu" sorulursa
    eps = memory.format_episodes(n=5)
    if eps:
        lines.append(eps)
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
    # Live karar-gunlugu (diyalogda yurutulen aksiyonlar) bagama eklenir -> "az once ne yaptim?" cevaplanir
    live_ctx = context
    dec = memory.format_decisions()
    if dec:
        live_ctx = context + "\n" + dec
    # 1) Normal serbest-metin yanit (DEGISMEDI -> baglam-degisimi/injection direnci korunur)
    messages = [{"role": "system", "content": CHAT_SYSTEM.format(context=live_ctx)}]
    for m in history or []:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})
    try:
        answer = _get_client().chat(messages, temperature=0.3, max_tokens=max_tokens).strip()
    except Exception as ex:
        return f"Yanıt üretilirken hata oluştu: {ex}"
    # 2) B#1 KAPILI ICRA: operatör ONAY verdiyse, önerilen aksiyonu GERÇEKTEN çalıştır (insan-onay kapısı)
    if _CONFIRM_RE.search(message or ""):
        executed = _maybe_execute(context, history, message)
        if executed:
            answer += "\n\n" + executed
    return answer


def _maybe_execute(context: str, history: Optional[List[dict]], message: str) -> str:
    """Operatör onayi sonrasi: sohbetten onaylanan mock-fonksiyon(lar)i çikar ve ÇALIŞTIR.
    FAIL-OPEN: belirsizse/parse hatasiysa hiçbir şey yapmaz (bos döner). FP-güvenli: yalniz
    açik öneri+onay varsa çağirir (model 'calls:[]' döndürür aksi halde)."""
    try:
        hist = [m for m in (history or []) if m.get("content")][-6:]
        hist_txt = "\n".join(f"{m['role']}: {m['content']}" for m in hist) + f"\nuser: {message}"
        prompt = CHAT_EXECUTE_PROMPT.format(tools=_tools_desc(), context=context)
        raw = _get_client().chat(
            [{"role": "system", "content": prompt},
             {"role": "user", "content": "SOHBET GEÇMİŞİ:\n" + hist_txt}],
            temperature=0.0, max_tokens=300)
        data = extract_json(raw)
        calls = data.get("calls", []) if isinstance(data, dict) else []
    except Exception:
        return ""
    out = ["✅ Yürütülen operasyonel aksiyonlar:"]
    done = {d["function"] for d in memory.SESSION_DECISIONS}  # bu oturumda çalışan fonksiyonlar
    for c in calls or []:
        fn = c.get("function")
        args = c.get("args", {}) or {}
        tool = TOOL_REGISTRY.get(fn)
        if not tool:
            continue
        if fn in done:  # mükerrer-dispatch koruması: aynı fonksiyon oturumda 1 kez (geçmiş-soru re-icrasını da keser)
            continue
        try:
            res = str(tool.invoke(args))
        except Exception as ex:
            res = f"(çağrı hatası: {ex})"
        memory.log_decision(fn, args, res)
        out.append(f"- {fn} → {res}")
    return "\n".join(out) if len(out) > 1 else ""
