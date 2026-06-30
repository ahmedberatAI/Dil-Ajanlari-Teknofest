#!/usr/bin/env python
"""Gradio arayuzu: video yukle -> (canli ilerleme) analiz -> sonuclar + sohbet.

Ozellikler: renk-kodlu risk rozeti, olay zaman cizelgesi, canli ilerleme (graph.stream),
operatör asistani sohbeti.

Calistirma:
    1) Ayri terminalde:  python serve_vllm.py
    2) python app.py     (http://127.0.0.1:7860)
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile

import gradio as gr

from dilajan import chat_agent, memory
from dilajan.agent.graph import build_graph
from dilajan.schema import AnalysisResult, Severity

_graph = build_graph()

_SEV_COLOR = {
    Severity.DUSUK.value: "#16a34a",
    Severity.ORTA.value: "#ca8a04",
    Severity.YUKSEK.value: "#ea580c",
    Severity.KRITIK.value: "#dc2626",
}
_NODE_TR = {
    "ingest": "Video işleniyor (kare örnekleme + segmentleme)…",
    "perceive": "Olaylar tespit ediliyor (segmentler paralel analiz ediliyor)…",
    "reason": "Türkçe özet, risk ve aksiyon önerileri üretiliyor…",
    "act": "Operasyonel fonksiyonlar dinamik seçiliyor…",
    "finalize": "Sonuç hazırlanıyor…",
}


def _secs(mmss: str) -> int:
    try:
        m, s = mmss.split(":")
        return int(m) * 60 + int(s)
    except Exception:
        return 0


def risk_badge_html(level: str, rationale: str) -> str:
    color = _SEV_COLOR.get(level, "#6b7280")
    return (
        f"<div style='display:flex;align-items:center;gap:12px;'>"
        f"<span style='background:{color};color:#fff;padding:6px 16px;border-radius:8px;"
        f"font-weight:700;font-size:1.1em;'>RİSK: {level}</span>"
        f"<span style='opacity:.85'>{rationale}</span></div>"
    )


def timeline_html(events, duration_str: str) -> str:
    if not events:
        return "<div style='opacity:.6;padding:8px'>Kayda değer olay tespit edilmedi.</div>"
    total = max([_secs(duration_str)] + [_secs(e.time) for e in events]) or 1
    markers = ""
    for e in events:
        pct = min(100, 100 * _secs(e.time) / total)
        c = _SEV_COLOR.get(e.severity.value, "#6b7280")
        markers += (
            f"<div title='[{e.time}] {e.event} ({e.severity.value})' "
            f"style='position:absolute;left:{pct:.1f}%;top:0;transform:translateX(-50%);'>"
            f"<div style='width:14px;height:14px;border-radius:50%;background:{c};"
            f"border:2px solid #fff;box-shadow:0 0 3px rgba(0,0,0,.4);'></div>"
            f"<div style='font-size:10px;opacity:.7;margin-top:2px;'>{e.time}</div></div>"
        )
    track = (
        "<div style='position:relative;height:44px;margin:8px 4px 4px;'>"
        "<div style='position:absolute;top:6px;left:0;right:0;height:3px;background:#9ca3af;border-radius:2px;'></div>"
        f"{markers}</div>"
    )
    rows = "".join(
        f"<li style='margin:2px 0'><span style='color:{_SEV_COLOR.get(e.severity.value,'#6b7280')};"
        f"font-weight:700'>●</span> <b>{e.time}</b> — {e.event} "
        f"<i style='opacity:.6'>({e.severity.value}/{e.category.value}"
        + (f", konum: {e.region}" if getattr(e, 'region', None) else "") + ")</i></li>"
        for e in events
    )
    return track + f"<ul style='list-style:none;padding-left:4px;margin:6px 0;font-size:.92em'>{rows}</ul>"


def _ensure_playable(path):
    """Yuklenen videoyu tarayicinin OYNATABILECEGI H.264/yuv420p mp4'e transcode eder.

    Sorun: gr.Video'nun HTML5 oynaticisi HEVC/H.265, eski mpeg4 (.avi), bazi .mkv/.mov
    codec'lerini OYNATAMIYOR ("video not playable"). format='mp4' yalnizca container'i
    degistiriyor, codec'i degil -> yetmiyor. Bu fonksiyon codec'i universal H.264 yapar.

    - Zaten H.264 mp4 ise dokunmaz (hizli). Degilse ffmpeg ile transcode eder.
    - PyAV analiz zaten her codec'i okuyabiliyor; bu yalniz TARAYICI ONIZLEMESI icindir
      (transcode edilen dosya analizde de kullanilir; crf=23 ~gorsel-kayipsiz, algi 768'e iniyor).
    - FAIL-OPEN: ffmpeg yoksa/hata/zaman asimi -> orijinal yol (analiz yine calisir)."""
    if not path or not os.path.exists(path):
        return path
    try:
        codec = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=30).stdout.strip()
        if codec == "h264" and path.lower().endswith(".mp4"):
            return path  # zaten oynatilabilir
        out = os.path.join(tempfile.gettempdir(), f"dilajan_play_{abs(hash(path)) % 10**9}.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-preset", "veryfast", "-crf", "23", "-an", "-movflags", "+faststart", out],
            capture_output=True, timeout=600)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return out
    except Exception:
        pass
    return path  # fail-open


def _blank():
    return (gr.update(),) * 9


def analyze(video_path, facility_rules="", restricted_zones=""):
    if not video_path:
        yield ("Lütfen bir video yükleyin.", *_blank())
        return
    memory.reset_decisions()  # yeni analiz -> oturum karar-günlüğü sıfırlanır (B#1/memory)
    # SAVUNMA/tesis: operatörün girdiği kuralları + yasak bölgeleri bu analiz için uygula
    from dilajan.config import settings as _settings
    _settings.facility_rules = (facility_rules or "").strip()
    _settings.restricted_zones = (restricted_zones or "").strip()
    result: AnalysisResult | None = None
    for step in _graph.stream({"video_path": video_path, "trace": []}):
        node, out = next(iter(step.items()))
        if node == "finalize":
            result = out.get("result")
        else:
            yield (f"⏳ {_NODE_TR.get(node, node)}", *_blank())

    if result is None:
        yield ("Analiz tamamlanamadı.", *_blank())
        return

    risk = risk_badge_html(result.risk.level.value, result.risk.rationale)
    timeline = timeline_html(result.events, result.video_duration or "00:00")
    events_rows = [[e.time + (f"–{e.end_time}" if e.end_time else ""), e.event, e.severity.value, e.category.value, e.region or "—"] for e in result.events]
    actions_md = "\n".join(
        f"- **[{a.priority.value}]** {a.action}" + (f"  \n  _{a.rationale}_" if a.rationale else "")
        for a in result.actions
    ) or "—"
    funcs_md = "\n".join(f"- `{f}`" for f in result.triggered_functions) or "— (operasyonel çağrı yapılmadı)"
    trace_md = "\n".join(f"- {t}" for t in result.decision_trace) or "—"
    raw = json.dumps(result.model_dump(), ensure_ascii=False, indent=2)
    ctx = chat_agent.build_context(result)  # mevcut analiz henüz episodik bellekte değil -> "geçmiş" olarak görünmez
    memory.append_episode(result, source=os.path.basename(str(video_path)))
    yield ("✅ Analiz tamamlandı.", result.summary, risk, timeline,
           events_rows, actions_md, funcs_md, trace_md, raw, ctx)


def chat_respond(message, history, context):
    history = list(history or [])
    answer = chat_agent.respond(context, history, message)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})
    return history, ""


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="DilAjanları - Video Analiz ve Karar Destek") as demo:
        gr.Markdown(
            "# 🎥 DilAjanları — Video Analiz ve Karar Destek Ajanı\n"
            "TEKNOFEST TYDA 3. Senaryo · Yerel / offline · Qwen3-VL-8B + vLLM + LangGraph"
        )
        context_state = gr.State("")

        with gr.Row():
            with gr.Column(scale=1):
                # Yuklenen videoyu upload'ta H.264/yuv420p mp4'e TRANSCODE et (_ensure_playable):
                # HEVC/eski-mpeg4/avi/mkv tarayicida oynamiyordu; format="mp4" container-only oldugu
                # icin yetmiyordu. Codec'i universal yapinca onizleme her formatta oynar.
                video_in = gr.Video(label="Video", sources=["upload"])
                with gr.Accordion("🛡️ Savunma / Tesis Ayarları (opsiyonel)", open=False):
                    facility_in = gr.Textbox(
                        label="Tesise özgü güvenlik kuralları",
                        placeholder="Örn: Bu kritik tesise izinsiz giriş yasaktır; baret takmayan personel ihlaldir.",
                        lines=2)
                    zones_in = gr.Textbox(
                        label="Yasak / kısıtlı bölgeler (3×3 ızgara, virgülle)",
                        placeholder="Örn: üst sağ, sağ, alt sağ  → bu bölgelerde kişi = Yasak Bölge İhlali (Yüksek)")
                analyze_btn = gr.Button("🔍 Analiz Et", variant="primary")
                status_out = gr.Markdown("")
                summary_out = gr.Textbox(label="Özet", lines=3)
                risk_out = gr.HTML(label="Risk")
            with gr.Column(scale=1):
                timeline_out = gr.HTML(label="Olay Zaman Çizelgesi")
                events_out = gr.Dataframe(
                    headers=["Zaman", "Olay", "Önem", "Kategori", "Konum"],
                    label="Tespit Edilen Olaylar", wrap=True,
                )

        with gr.Row():
            actions_out = gr.Markdown(label="Aksiyon Önerileri")
            funcs_out = gr.Markdown(label="Tetiklenen Operasyonel Fonksiyonlar")

        with gr.Accordion("🧠 Ajan Karar Günlüğü (açıklanabilirlik)", open=False):
            trace_out = gr.Markdown(label="Karar İzi")

        with gr.Accordion("Ham JSON Çıktısı", open=False):
            json_out = gr.Code(language="json", label="AnalysisResult")

        gr.Markdown("## 💬 Analiz Hakkında Sohbet (Operatör Asistanı)")
        chatbot = gr.Chatbot(height=300, label="Operatör Asistanı")
        with gr.Row():
            chat_in = gr.Textbox(placeholder="Örn: En kritik olay neydi? Hangi aksiyonlar alındı?", scale=4, show_label=False)
            chat_btn = gr.Button("Gönder", scale=1)

        # Upload'ta tarayici-oynatilabilir H.264'e cevir (onizleme + analiz ayni dosyayi kullanir)
        video_in.upload(_ensure_playable, inputs=[video_in], outputs=[video_in])

        analyze_btn.click(
            analyze, inputs=[video_in, facility_in, zones_in],
            outputs=[status_out, summary_out, risk_out, timeline_out,
                     events_out, actions_out, funcs_out, trace_out, json_out, context_state],
        )
        chat_btn.click(chat_respond, [chat_in, chatbot, context_state], [chatbot, chat_in])
        chat_in.submit(chat_respond, [chat_in, chatbot, context_state], [chatbot, chat_in])

    return demo


if __name__ == "__main__":
    # DILAJAN_SHARE=1 -> arkadasa gonderilebilen gecici herkese-acik link (gradio.live tüneli, sadece demo gosterimi)
    # DILAJAN_HOST=0.0.0.0 -> ayni ag uzerindeki cihazlardan LAN IP ile erisim
    share = os.environ.get("DILAJAN_SHARE", "").lower() in ("1", "true", "yes")
    host = os.environ.get("DILAJAN_HOST", "127.0.0.1")
    build_ui().launch(server_name=host, server_port=7860, share=share)
