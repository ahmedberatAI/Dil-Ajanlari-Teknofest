#!/usr/bin/env python
"""Gradio arayuzu — VigilantAI Operasyon Konsolu (karanlik SOC temasi).

Video yukle -> canli ajan-pipeline gostergesi (LangGraph dugumleri) -> sonuclar + sohbet.
Ozellikler: radar-animasyonlu marka basligi, sunucu-durum rozeti, parlayan risk paneli +
istatistik cipleri, gelismis olay zaman-cizelgesi (aralik barlari), tutanak/kanit/brifing
panelleri, operator sohbeti. Tamamen yerel: dis font/CDN YOK (sistem fontlari).

Calistirma:
    1) Ayri terminalde:  python serve_vllm.py
    2) python app.py     (http://127.0.0.1:7860)
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import urllib.request

import gradio as gr

from dilajan import chat_agent, memory
from dilajan.agent.graph import build_graph
from dilajan.config import settings
from dilajan.schema import AnalysisResult, Severity

_graph = build_graph()

_SEV_COLOR = {
    Severity.DUSUK.value: "#22c55e",
    Severity.ORTA.value: "#eab308",
    Severity.YUKSEK.value: "#f97316",
    Severity.KRITIK.value: "#ef4444",
}
_SEV_CLASS = {"Düşük": "low", "Orta": "mid", "Yüksek": "high", "Kritik": "crit"}
_SEV_ORD = {"Düşük": 1, "Orta": 2, "Yüksek": 3, "Kritik": 4}

# Ajan pipeline gostergesi (LangGraph dugumleri; reexamine KOSULLU dugumdur)
_PIPELINE = [
    ("ingest", "Görüntü Alımı"),
    ("perceive", "Olay Algısı"),
    ("reexamine", "Yeniden İnceleme"),
    ("reason", "Değerlendirme"),
    ("act", "Aksiyon"),
    ("finalize", "Rapor"),
]
_NODE_NOTE = {
    "ingest": "kare örnekleme + zaman damgalı segmentleme…",
    "perceive": "segmentler VLM ile paralel analiz ediliyor…",
    "reexamine": "belirsiz olaylar odaklı yeniden inceleniyor (adaptif döngü)…",
    "reason": "Türkçe özet · risk · aksiyon önerileri üretiliyor…",
    "act": "operasyonel fonksiyonlar dinamik seçiliyor…",
    "finalize": "sonuç paketleniyor…",
}


def _secs(mmss: str) -> int:
    try:
        m, s = mmss.split(":")
        return int(m) * 60 + int(s)
    except Exception:
        return 0


# --- HTML uretecleri (tema: karanlik SOC konsolu) ---
def _alert(msg: str, kind: str = "warn") -> str:
    return f"<div class='alert {kind}'>{msg}</div>"


def _pipeline_html(seen, done: bool = False) -> str:
    """LangGraph dugum akisini canli gosteren stepper (kosullu reexamine dahil)."""
    seen_set = set(seen)
    active = None
    if not done:
        for key, _label in _PIPELINE:
            if key in seen_set:
                continue
            if key == "reexamine" and "reason" in seen_set:
                continue  # kosullu dugum atlandi
            active = key
            break
    parts = []
    for key, label in _PIPELINE:
        if done or key in seen_set:
            cls, icon = "done", "✓"
        elif key == "reexamine" and "reason" in seen_set:
            cls, icon = "skip", "–"
        elif key == active:
            cls, icon = "active", ""
        else:
            cls, icon = "pend", ""
        parts.append(
            f"<div class='pstep {cls}'><div class='pdot'>{icon}</div>"
            f"<div class='plab'>{label}</div></div>"
        )
    if done:
        tail = "<div class='pipe-note ok'>✅ Analiz tamamlandı — rapor hazır.</div>"
    else:
        note = _NODE_NOTE.get(active, "")
        tail = f"<div class='pipe-note'>⏳ {note}</div>" if note else ""
    return "<div class='pipe'>" + "".join(parts) + "</div>" + tail


def risk_badge_html(level: str, rationale: str) -> str:
    """(Geriye-uyum) Sade risk rozeti."""
    color = _SEV_COLOR.get(level, "#6b7280")
    return (
        f"<div style='display:flex;align-items:center;gap:12px;'>"
        f"<span style='background:{color};color:#fff;padding:6px 16px;border-radius:8px;"
        f"font-weight:700;font-size:1.1em;'>RİSK: {level}</span>"
        f"<span style='opacity:.85'>{rationale}</span></div>"
    )


def risk_panel_html(result: AnalysisResult) -> str:
    """Buyuk risk rozeti + operasyon istatistik cipleri (tek panel)."""
    lvl = result.risk.level.value
    cls = _SEV_CLASS.get(lvl, "mid")
    n_ev = len(result.events)
    max_sev = max((e.severity.value for e in result.events),
                  key=lambda v: _SEV_ORD.get(v, 0), default="—")
    n_fn = len(result.triggered_functions)
    dur = result.video_duration or "—"
    chips = (
        f"<div class='chip'><span class='chip-k'>OLAY</span><span class='chip-v'>{n_ev}</span></div>"
        f"<div class='chip'><span class='chip-k'>EN YÜKSEK ÖNEM</span><span class='chip-v'>{max_sev}</span></div>"
        f"<div class='chip'><span class='chip-k'>OPERASYONEL ÇAĞRI</span><span class='chip-v'>{n_fn}</span></div>"
        f"<div class='chip'><span class='chip-k'>SÜRE</span><span class='chip-v mono'>{dur}</span></div>"
    )
    return (
        "<div class='risk-hero'>"
        f"<div class='risk-xl sev-{cls}'>RİSK: {lvl}</div>"
        f"<div class='risk-rat'>{result.risk.rationale}</div>"
        f"</div><div class='chip-row'>{chips}</div>"
    )


def timeline_html(events, duration_str: str) -> str:
    if not events:
        return "<div class='empty'>Kayda değer olay tespit edilmedi.</div>"
    total = max(
        [_secs(duration_str)] + [_secs(e.time) for e in events]
        + [_secs(e.end_time) for e in events if e.end_time]
    ) or 1
    spans, markers = "", ""
    for e in events:
        c = _SEV_COLOR.get(e.severity.value, "#6b7280")
        pct = min(100, 100 * _secs(e.time) / total)
        if e.end_time and _secs(e.end_time) > _secs(e.time):
            w = max(2.0, min(100, 100 * _secs(e.end_time) / total) - pct)
            spans += (
                f"<div style='position:absolute;left:{pct:.1f}%;width:{w:.1f}%;top:9px;height:8px;"
                f"border-radius:4px;background:{c};opacity:.35;'></div>"
            )
        markers += (
            f"<div title='[{e.time}] {e.event} ({e.severity.value})' "
            f"style='position:absolute;left:{pct:.1f}%;top:0;transform:translateX(-50%);text-align:center;'>"
            f"<div style='width:14px;height:14px;border-radius:50%;background:{c};margin:0 auto;"
            f"border:2px solid #0b1322;box-shadow:0 0 10px {c}99;'></div>"
            f"<div class='mono' style='font-size:10px;opacity:.65;margin-top:3px;'>{e.time}</div></div>"
        )
    track = (
        "<div style='position:relative;height:48px;margin:10px 8px 2px;'>"
        "<div style='position:absolute;top:11px;left:0;right:0;height:4px;border-radius:2px;"
        "background:linear-gradient(90deg,rgba(34,211,238,.10),rgba(148,163,184,.28),rgba(34,211,238,.10));'></div>"
        f"{spans}{markers}"
        f"<div class='mono' style='position:absolute;right:0;top:26px;font-size:10px;opacity:.5;'>{duration_str}</div>"
        "</div>"
    )
    rows = "".join(
        f"<li><span class='sev-chip sev-{_SEV_CLASS.get(e.severity.value, 'mid')}'>{e.severity.value}</span>"
        f"<b class='mono'>{e.time}{('–' + e.end_time) if e.end_time else ''}</b> — {e.event} "
        f"<i class='dim'>({e.category.value}"
        + (f", konum: {e.region}" if getattr(e, 'region', None) else "") + ")</i></li>"
        for e in events
    )
    return track + f"<ul class='ev-list'>{rows}</ul>"


def _server_status() -> str:
    """vLLM sunucu sagligini yoklar (sayfa acilisinda) -> durum rozeti."""
    try:
        urllib.request.urlopen(
            f"http://{settings.vllm_host}:{settings.vllm_port}/health", timeout=2)
        model = settings.model_name.split("/")[-1]
        return (f"<div class='srv on'><span class='sdot online'></span>MODEL ÇEVRİMİÇİ"
                f"<span class='dim'> · {model}</span></div>")
    except Exception:
        return ("<div class='srv off'><span class='sdot offline'></span>MODEL SUNUCUSU KAPALI"
                "<span class='dim'> · başlatmak için: </span><code>python serve_vllm.py</code></div>")


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
    # status disindaki tum ciktilar (summary, risk, timeline, events, actions, funcs, trace,
    # json, context_state, result_state, path_state) icin akis-arasi yer-tutucu
    return (gr.update(),) * 11


def analyze(video_path, facility_rules="", restricted_zones="",
            detect_vehicles=False, vehicle_zones="", detect_crowd=False):
    if not video_path:
        yield (_alert("Lütfen önce bir video yükleyin."), *_blank())
        return
    memory.reset_decisions()  # yeni analiz -> oturum karar-günlüğü sıfırlanır (B#1/memory)
    # SAVUNMA/tesis: operatörün girdiği kuralları + yasak bölgeleri + dedektör senaryolarını uygula
    settings.facility_rules = (facility_rules or "").strip()
    settings.restricted_zones = (restricted_zones or "").strip()
    settings.detect_vehicles = bool(detect_vehicles)
    settings.vehicle_zones = (vehicle_zones or "").strip()
    settings.detect_crowd = bool(detect_crowd)

    seen: list = []
    yield (_pipeline_html(seen), *_blank())  # baslangic: Görüntü Alımı aktif
    result: AnalysisResult | None = None
    for step in _graph.stream({"video_path": video_path, "trace": []}):
        node, out = next(iter(step.items()))
        seen.append(node)
        if node == "finalize":
            result = out.get("result")
        else:
            yield (_pipeline_html(seen), *_blank())

    if result is None:
        yield (_alert("Analiz tamamlanamadı — model sunucusunun çalıştığından emin olun."), *_blank())
        return

    risk = risk_panel_html(result)
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
    # result + video yolu State'lere yazilir -> Tutanak / Kanıt Paketi butonlari bunlari kullanir
    yield (_pipeline_html(seen, done=True), result.summary, risk, timeline,
           events_rows, actions_md, funcs_md, trace_md, raw, ctx, result, str(video_path))


def chat_respond(message, history, context):
    history = list(history or [])
    answer = chat_agent.respond(context, history, message)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})
    return history, ""


def make_briefing(hours):
    """Vardiya devir-teslim brifingi üretir (episodik bellekten)."""
    from dilajan import briefing
    try:
        h = float(hours) if hours else 8.0
    except Exception:
        h = 8.0
    return briefing.generate_shift_briefing(h)


def make_report(result, path):
    """Analiz sonucundan resmi Markdown olay tutanağı üretir."""
    if not result:
        return "Önce bir video analiz edin; ardından tutanak üretebilirsiniz."
    from dilajan import report
    cam = os.path.basename(str(path)) if path else "—"
    return report.build_incident_report(result, camera=cam)


def make_evidence(result, path):
    """Yüksek-önemli olaylar için bbox-overlay kanıt kareleri + hash'li manifest üretir."""
    if not result or not path:
        return None
    from dilajan import evidence
    out_dir = os.path.join(tempfile.gettempdir(), "dilajan_kanit")
    res = evidence.build_evidence_bundle(str(path), result, out_dir)
    files = list(res.get("frames", []))
    if res.get("manifest"):
        files.append(res["manifest"])
    return files or None


# --- Tema & stil (tamamen yerel: dis font/CDN yok) ---
_FORCE_DARK_JS = """
() => {
  // Konsol her zaman karanlik temada calisir (sistem acik-temada olsa bile).
  window.__vigilant_dark = 1;
  document.body.classList.add('dark');
  const url = new URL(window.location.href);
  if (url.searchParams.get('__theme') !== 'dark') {
    url.searchParams.set('__theme', 'dark');
    window.history.replaceState(null, '', url.toString());
  }
}
"""

_THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.cyan,
    neutral_hue=gr.themes.colors.slate,
    font=["Segoe UI Variable Text", "Segoe UI", "system-ui", "-apple-system", "sans-serif"],
    font_mono=["Cascadia Code", "Consolas", "ui-monospace", "monospace"],
)

_CSS = """
/* ====== VigilantAI Operasyon Konsolu — karanlik SOC temasi ====== */
/* Gradio tema-degiskenlerini HER IKI modda da karanliga zorla (sistem acik-temada olsa bile
   konsol tutarli gorunur; js'e guvenmeden salt-CSS garanti). */
body, body.dark, .gradio-container {
  --body-background-fill: #05070d;
  --background-fill-primary: #0b1120;
  --background-fill-secondary: #0d1526;
  --block-background-fill: rgba(15,23,42,.45);
  --panel-background-fill: rgba(15,23,42,.45);
  --body-text-color: #dbe4f0;
  --body-text-color-subdued: #8fa3bd;
  --block-label-text-color: #8fa3bd;
  --block-title-text-color: #a5b4c8;
  --block-border-color: rgba(148,163,184,.14);
  --border-color-primary: rgba(148,163,184,.16);
  --border-color-accent: rgba(34,211,238,.4);
  --input-background-fill: rgba(2,6,17,.65);
  --input-border-color: rgba(148,163,184,.18);
  --input-placeholder-color: #5c6c84;
  --checkbox-background-color: rgba(2,6,17,.65);
  --checkbox-border-color: rgba(148,163,184,.3);
  --checkbox-label-text-color: #c7d2e3;
  --table-even-background-fill: rgba(10,16,30,.6);
  --table-odd-background-fill: rgba(14,21,38,.6);
  --table-border-color: rgba(148,163,184,.12);
  --button-secondary-background-fill: rgba(8,14,26,.8);
  --button-secondary-text-color: #a5f3fc;
  --color-accent: #22d3ee;
  --color-accent-soft: rgba(34,211,238,.14);
  --link-text-color: #7dd3fc;
  --code-background-fill: #060b16;
  --shadow-drop: 0 8px 26px rgba(0,0,0,.35);
}
.gradio-container {
  background: #05070d !important;
  max-width: 1440px !important;
  margin: 0 auto !important;
  color: #dbe4f0;
}
.gradio-container::before {  /* atmosferik parlama */
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background:
    radial-gradient(900px 420px at 18% -5%, rgba(34,211,238,.10), transparent 60%),
    radial-gradient(800px 420px at 85% 0%, rgba(99,102,241,.09), transparent 60%);
}
.gradio-container::after {  /* ince taktik izgara */
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background-image:
    linear-gradient(rgba(148,163,184,.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148,163,184,.035) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: linear-gradient(180deg, rgba(0,0,0,.9), rgba(0,0,0,.25) 60%, transparent);
}
.gradio-container > * { position: relative; z-index: 1; }
footer { display: none !important; }
::-webkit-scrollbar { width: 9px; height: 9px; }
::-webkit-scrollbar-thumb { background: rgba(148,163,184,.25); border-radius: 6px; }
::-webkit-scrollbar-track { background: transparent; }
.mono { font-family: "Cascadia Code", Consolas, ui-monospace, monospace; }
.dim { opacity: .6; }

/* ---- ust baslik ---- */
.hdr { display: flex; align-items: center; gap: 16px; padding: 14px 6px 4px; }
.radar {
  width: 52px; height: 52px; border-radius: 50%; position: relative; flex: none;
  border: 1px solid rgba(34,211,238,.4);
  background:
    repeating-radial-gradient(circle at center, transparent 0 7px, rgba(34,211,238,.12) 7px 8px),
    radial-gradient(circle at center, rgba(34,211,238,.20) 0%, rgba(2,6,17,.9) 72%);
  box-shadow: 0 0 24px rgba(34,211,238,.18), inset 0 0 16px rgba(34,211,238,.10);
  overflow: hidden;
}
.radar::before { content: ""; position: absolute; left: 50%; top: 50%; width: 4px; height: 4px;
  border-radius: 50%; background: #67e8f9; transform: translate(-50%,-50%); box-shadow: 0 0 8px #67e8f9; }
.radar::after { content: ""; position: absolute; inset: 1px; border-radius: 50%;
  background: conic-gradient(from 0deg, rgba(103,232,249,.65), rgba(103,232,249,.08) 70deg, transparent 110deg);
  animation: sweep 3.4s linear infinite; }
@keyframes sweep { to { transform: rotate(360deg); } }
.brand-top { font-size: .68rem; letter-spacing: .34em; color: #67e8f9; font-weight: 700; }
.brand { font-size: 1.65rem; font-weight: 800; letter-spacing: .02em; line-height: 1.15;
  background: linear-gradient(92deg, #f1f5f9, #7dd3fc 70%, #22d3ee);
  -webkit-background-clip: text; background-clip: text; color: transparent; }
.brand-sub { font-size: .8rem; color: #8fa3bd; margin-top: 2px; }
.srv { display: inline-flex; align-items: center; gap: 8px; font-size: .72rem; font-weight: 700;
  letter-spacing: .08em; padding: 8px 14px; border-radius: 999px;
  border: 1px solid rgba(148,163,184,.16); background: rgba(10,16,28,.7); white-space: nowrap; }
.srv code { font-size: .72rem; color: #7dd3fc; background: transparent; }
.srv.on { color: #6ee7b7; border-color: rgba(52,211,153,.3); }
.srv.off { color: #fda4af; border-color: rgba(244,63,94,.3); }
.sdot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.sdot.online { background: #34d399; box-shadow: 0 0 10px #34d399; animation: blink 2.2s infinite; }
.sdot.offline { background: #f43f5e; box-shadow: 0 0 10px #f43f5e; }
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: .35; } }

/* ---- paneller ---- */
.panel {
  background: linear-gradient(180deg, rgba(15,23,42,.72), rgba(9,13,25,.80)) !important;
  border: 1px solid rgba(148,163,184,.13) !important;
  border-radius: 16px !important;
  padding: 14px 16px !important;
  box-shadow: 0 10px 32px rgba(0,0,0,.38);
  backdrop-filter: blur(12px);
  animation: fadeUp .45s ease both;
}
@keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.panel .block, .panel .form { background: transparent !important; border: none !important; box-shadow: none !important; }
.panel textarea, .panel input[type="text"], .panel input[type="number"] {
  background: rgba(2,6,17,.65) !important; border: 1px solid rgba(148,163,184,.16) !important;
  color: #dbe4f0 !important; border-radius: 10px !important;
}
.panel label span { color: #8fa3bd; font-size: .78rem; }
.card-title { display: flex; align-items: center; gap: 8px; font-size: .78rem; font-weight: 800;
  letter-spacing: .16em; color: #67e8f9; margin: 2px 2px 10px; padding-bottom: 8px;
  border-bottom: 1px solid rgba(103,232,249,.14); }

/* ---- birincil buton ---- */
#analyze-btn {
  background: linear-gradient(135deg, #06b6d4, #3b82f6) !important;
  border: none !important; color: #041225 !important; font-weight: 800 !important;
  letter-spacing: .06em; font-size: 1rem !important; border-radius: 12px !important;
  box-shadow: 0 6px 22px rgba(6,182,212,.35);
  transition: transform .15s ease, box-shadow .15s ease;
}
#analyze-btn:hover { transform: translateY(-1px); box-shadow: 0 10px 28px rgba(6,182,212,.5); }
.tool-btn { border: 1px solid rgba(103,232,249,.3) !important; background: rgba(8,14,26,.8) !important;
  color: #a5f3fc !important; border-radius: 10px !important; font-weight: 600 !important; }
.tool-btn:hover { border-color: rgba(103,232,249,.6) !important; background: rgba(14,24,42,.9) !important; }

/* ---- pipeline stepper ---- */
.pipe { display: flex; align-items: flex-start; margin: 6px 2px 2px; }
.pstep { flex: 1; text-align: center; position: relative; }
.pstep:not(:first-child)::before { content: ""; position: absolute; top: 8px; left: -50%;
  width: 100%; height: 2px; background: rgba(148,163,184,.18); z-index: 0; }
.pstep.done:not(:first-child)::before { background: linear-gradient(90deg, rgba(34,211,238,.5), rgba(34,211,238,.8)); }
.pdot { width: 18px; height: 18px; border-radius: 50%; margin: 0 auto; position: relative; z-index: 1;
  display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 800;
  background: #0c1322; border: 2px solid rgba(148,163,184,.3); color: #05070d; }
.pstep.done .pdot { background: #22d3ee; border-color: #22d3ee; box-shadow: 0 0 10px rgba(34,211,238,.5); }
.pstep.active .pdot { border-color: #67e8f9; animation: ping 1.15s ease-in-out infinite; }
.pstep.skip .pdot { border-style: dashed; color: #64748b; background: transparent; }
@keyframes ping { 0% { box-shadow: 0 0 0 0 rgba(103,232,249,.45); } 100% { box-shadow: 0 0 0 10px rgba(103,232,249,0); } }
.plab { font-size: .68rem; margin-top: 6px; color: #7c8ea8; letter-spacing: .03em; }
.pstep.done .plab { color: #a5f3fc; }
.pstep.active .plab { color: #e0f2fe; font-weight: 700; }
.pstep.skip .plab { color: #52627a; text-decoration: line-through; }
.pipe-note { font-size: .8rem; color: #8fa3bd; margin: 10px 4px 0; }
.pipe-note.ok { color: #6ee7b7; font-weight: 600; }

/* ---- risk paneli ---- */
.risk-hero { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.risk-xl { font-size: 1.12rem; font-weight: 800; letter-spacing: .05em; color: #fff;
  padding: 10px 22px; border-radius: 12px; }
.risk-xl.sev-low  { background: linear-gradient(135deg,#16a34a,#22c55e); box-shadow: 0 0 22px rgba(34,197,94,.35); }
.risk-xl.sev-mid  { background: linear-gradient(135deg,#a16207,#eab308); box-shadow: 0 0 22px rgba(234,179,8,.35); }
.risk-xl.sev-high { background: linear-gradient(135deg,#c2410c,#f97316); box-shadow: 0 0 22px rgba(249,115,22,.4); }
.risk-xl.sev-crit { background: linear-gradient(135deg,#b91c1c,#ef4444); animation: glow 1.6s ease-in-out infinite; }
@keyframes glow { 0%,100% { box-shadow: 0 0 16px rgba(239,68,68,.45); } 50% { box-shadow: 0 0 34px rgba(239,68,68,.8); } }
.risk-rat { flex: 1; min-width: 220px; font-size: .92rem; color: #c7d2e3; }
.chip-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
.chip { display: flex; flex-direction: column; gap: 2px; padding: 8px 14px; border-radius: 10px;
  background: rgba(2,6,17,.55); border: 1px solid rgba(148,163,184,.14); min-width: 96px; }
.chip-k { font-size: .62rem; letter-spacing: .12em; color: #64748b; font-weight: 700; }
.chip-v { font-size: 1.05rem; font-weight: 800; color: #e2e8f0; }

/* ---- zaman cizelgesi & olay listesi ---- */
.ev-list { list-style: none; padding: 4px 2px 0; margin: 8px 0 0; font-size: .88rem; }
.ev-list li { margin: 5px 0; display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.sev-chip { font-size: .66rem; font-weight: 800; letter-spacing: .05em; padding: 2px 9px;
  border-radius: 999px; color: #fff; flex: none; }
.sev-chip.sev-low  { background: #16a34a; } .sev-chip.sev-mid  { background: #a16207; }
.sev-chip.sev-high { background: #c2410c; } .sev-chip.sev-crit { background: #b91c1c; }
.empty { opacity: .55; padding: 10px 4px; font-size: .9rem; }
.alert { padding: 12px 16px; border-radius: 12px; font-size: .92rem; font-weight: 600;
  background: rgba(234,179,8,.09); border: 1px solid rgba(234,179,8,.35); color: #fde68a; }

/* ---- tablo ---- */
#events-table table { border-collapse: collapse; }
#events-table th { background: rgba(6,182,212,.07) !important; color: #7dd3fc !important;
  font-size: .72rem !important; letter-spacing: .07em; }
#events-table td { border-color: rgba(148,163,184,.09) !important; font-size: .86rem !important; }

/* ---- sekmeler ---- */
.tab-nav button, button[role="tab"] { color: #8fa3bd !important; font-weight: 600 !important; }
.tab-nav button.selected, button[role="tab"][aria-selected="true"] { color: #67e8f9 !important; }

/* ---- sohbet ---- */
#op-chat { border-radius: 14px !important; }
#op-chat .message.user, #op-chat [data-testid="user"] { background: rgba(6,182,212,.14) !important; }
#op-chat .message.bot, #op-chat [data-testid="bot"] { background: rgba(15,23,42,.85) !important; }

/* ---- markdown/prose ---- */
.panel .prose, .panel .md { color: #c7d2e3 !important; }
.panel .prose table, .panel .md table { border-color: rgba(148,163,184,.15); }
.panel .prose code, .panel .md code { color: #7dd3fc; }

.app-footer { text-align: center; font-size: .74rem; color: #5c6c84; letter-spacing: .06em;
  padding: 18px 0 10px; }
.app-footer b { color: #7dd3fc; }
"""

_HEADER_HTML = """
<div class="hdr">
  <div class="radar"></div>
  <div style="flex:1">
    <div class="brand-top">VIGILANTAI · OPERASYON KONSOLU</div>
    <div class="brand">DilAjanları</div>
    <div class="brand-sub">Yerel Video Analiz &amp; Karar Destek Ajanı · Qwen3-VL-8B + vLLM + LangGraph · TEKNOFEST TYDA 3. Senaryo</div>
  </div>
</div>
"""

_FOOTER_HTML = """
<div class="app-footer">
  🛡️ <b>Tamamen yerel &amp; çevrimdışı</b> — dış API / bulut bağımlılığı yok ·
  Apache-2.0 · <b>BilisimVadisi2026</b> · VigilantAI
</div>
"""


def build_ui() -> gr.Blocks:
    # NOT (Gradio 6): theme/css/js artik launch()'a verilir (asagida __main__).
    with gr.Blocks(title="DilAjanları — VigilantAI Operasyon Konsolu") as demo:
        context_state = gr.State("")
        result_state = gr.State(None)   # son AnalysisResult (tutanak/kanit icin)
        path_state = gr.State("")       # son analiz edilen video yolu (kanit karesi cikarimi icin)

        # --- baslik + sunucu durumu ---
        with gr.Row():
            with gr.Column(scale=8):
                gr.HTML(_HEADER_HTML)
            with gr.Column(scale=3, min_width=260):
                server_badge = gr.HTML("<div class='srv off'><span class='sdot offline'></span>DURUM SORGULANIYOR…</div>")

        # --- ana satir: giris (sol) | canli durum + risk + ozet (sag) ---
        with gr.Row(equal_height=False):
            with gr.Column(scale=5):
                with gr.Group(elem_classes="panel"):
                    gr.HTML("<div class='card-title'>🎬 GÖRÜNTÜ GİRİŞİ</div>")
                    # Yuklenen videoyu upload'ta H.264/yuv420p mp4'e TRANSCODE et (_ensure_playable):
                    # HEVC/eski-mpeg4/avi/mkv tarayicida oynamiyordu; format="mp4" container-only oldugu
                    # icin yetmiyordu. Codec'i universal yapinca onizleme her formatta oynar.
                    video_in = gr.Video(label="Video", sources=["upload"], elem_id="video-in")
                    with gr.Accordion("🛡️ Savunma / Tesis Ayarları (opsiyonel)", open=False):
                        facility_in = gr.Textbox(
                            label="Tesise özgü güvenlik kuralları",
                            placeholder="Örn: Bu kritik tesise izinsiz giriş yasaktır; baret takmayan personel ihlaldir.",
                            lines=2)
                        zones_in = gr.Textbox(
                            label="Yasak / kısıtlı bölgeler (3×3 ızgara, virgülle)",
                            placeholder="Örn: üst sağ, sağ, alt sağ  → bu bölgelerde kişi = Yasak Bölge İhlali (Yüksek)")
                        with gr.Row():
                            crowd_in = gr.Checkbox(label="👥 Kalabalık / toplanma + ani dağılma tespiti", value=False)
                            vehicles_in = gr.Checkbox(label="🚗 Araç tespiti (yasak bölge)", value=False)
                        vehicle_zones_in = gr.Textbox(
                            label="Araç yasak bölgeleri (3×3 ızgara, virgülle — boşsa durağan araç bilgi amaçlı)",
                            placeholder="Örn: alt sağ, sağ  → bu bölgelerde araç = Yetkisiz/Yanlış Konumlu Araç (Yüksek)")
                    analyze_btn = gr.Button("🔍  ANALİZİ BAŞLAT", variant="primary", elem_id="analyze-btn", size="lg")
            with gr.Column(scale=7):
                with gr.Group(elem_classes="panel"):
                    gr.HTML("<div class='card-title'>📡 AJAN DURUMU — LANGGRAPH AKIŞI</div>")
                    status_out = gr.HTML("<div class='empty'>Analiz bekleniyor — video yükleyip <b>ANALİZİ BAŞLAT</b>'a basın.</div>")
                with gr.Group(elem_classes="panel"):
                    gr.HTML("<div class='card-title'>⚠️ RİSK DEĞERLENDİRMESİ</div>")
                    risk_out = gr.HTML("<div class='empty'>—</div>")
                with gr.Group(elem_classes="panel"):
                    gr.HTML("<div class='card-title'>📝 OPERASYON ÖZETİ</div>")
                    summary_out = gr.Textbox(label=None, show_label=False, lines=3,
                                             placeholder="Analiz sonrası Türkçe operasyon özeti burada görünecek…")

        # --- zaman cizelgesi (tam genislik) ---
        with gr.Group(elem_classes="panel"):
            gr.HTML("<div class='card-title'>⏱️ OLAY ZAMAN ÇİZELGESİ</div>")
            timeline_out = gr.HTML("<div class='empty'>—</div>")

        # --- olaylar + aksiyonlar ---
        with gr.Row(equal_height=False):
            with gr.Column(scale=7):
                with gr.Group(elem_classes="panel"):
                    gr.HTML("<div class='card-title'>🗂️ TESPİT EDİLEN OLAYLAR</div>")
                    events_out = gr.Dataframe(
                        headers=["Zaman", "Olay", "Önem", "Kategori", "Konum"],
                        label=None, show_label=False, wrap=True, elem_id="events-table",
                    )
            with gr.Column(scale=5):
                with gr.Group(elem_classes="panel"):
                    gr.HTML("<div class='card-title'>🎯 AKSİYON ÖNERİLERİ</div>")
                    actions_out = gr.Markdown("—")
                with gr.Group(elem_classes="panel"):
                    gr.HTML("<div class='card-title'>⚙️ TETİKLENEN OPERASYONEL FONKSİYONLAR</div>")
                    funcs_out = gr.Markdown("—")

        # --- ikincil paneller: sekmeler ---
        with gr.Group(elem_classes="panel"):
            with gr.Tabs():
                with gr.Tab("🧠 Ajan Karar Günlüğü"):
                    trace_out = gr.Markdown("—")
                with gr.Tab("🧾 Ham JSON"):
                    json_out = gr.Code(language="json", label=None, elem_id="json-out")
                with gr.Tab("📄 Olay Tutanağı & Kanıt Paketi"):
                    with gr.Row():
                        report_btn = gr.Button("📄 Olay Tutanağı Üret", elem_classes="tool-btn")
                        evidence_btn = gr.Button("🖼️ Kanıt Paketi Oluştur", elem_classes="tool-btn")
                    report_out = gr.Markdown()
                    evidence_out = gr.File(label="Kanıt kareleri + manifest (bbox-overlay, SHA-256)", file_count="multiple")
                with gr.Tab("🕐 Vardiya Devir-Teslim Brifingi"):
                    with gr.Row():
                        brief_hours = gr.Number(value=8, label="Pencere (saat)", precision=0, scale=1)
                        brief_btn = gr.Button("Brifing Oluştur", elem_classes="tool-btn", scale=2)
                    brief_out = gr.Markdown()

        # --- operator sohbeti ---
        with gr.Group(elem_classes="panel"):
            gr.HTML("<div class='card-title'>💬 OPERATÖR ASİSTANI — ANALİZ HAKKINDA SOHBET</div>")
            chatbot = gr.Chatbot(height=340, label=None, show_label=False, elem_id="op-chat")
            with gr.Row():
                chat_in = gr.Textbox(placeholder="Örn: En kritik olay neydi? Hangi aksiyonlar alındı? · Onaylarsanız aksiyonu gerçekten yürütür.",
                                     scale=5, show_label=False)
                chat_btn = gr.Button("Gönder ➤", scale=1, elem_classes="tool-btn")

        gr.HTML(_FOOTER_HTML)

        # --- baglantilar ---
        # Sayfa acilisinda: sunucu-durum rozeti + karanlik-tema js'i (load-event js'i 6.x'te calisir;
        # calismasa bile ustteki CSS degisken-zorlamasi karanligi salt-CSS garanti eder).
        try:
            demo.load(_server_status, None, server_badge, js=_FORCE_DARK_JS)
        except TypeError:  # eski/degisik imza -> js'siz yukle
            demo.load(_server_status, None, server_badge)

        # Upload'ta tarayici-oynatilabilir H.264'e cevir (onizleme + analiz ayni dosyayi kullanir)
        video_in.upload(_ensure_playable, inputs=[video_in], outputs=[video_in])

        analyze_btn.click(
            analyze, inputs=[video_in, facility_in, zones_in, vehicles_in, vehicle_zones_in, crowd_in],
            outputs=[status_out, summary_out, risk_out, timeline_out,
                     events_out, actions_out, funcs_out, trace_out, json_out, context_state,
                     result_state, path_state],
        )
        chat_btn.click(chat_respond, [chat_in, chatbot, context_state], [chatbot, chat_in])
        chat_in.submit(chat_respond, [chat_in, chatbot, context_state], [chatbot, chat_in])

        # Hizli-kazanim UI baglantilari
        report_btn.click(make_report, [result_state, path_state], [report_out])
        evidence_btn.click(make_evidence, [result_state, path_state], [evidence_out])
        brief_btn.click(make_briefing, [brief_hours], [brief_out])

    return demo


if __name__ == "__main__":
    # DILAJAN_SHARE=1 -> arkadasa gonderilebilen gecici herkese-acik link (gradio.live tüneli, sadece demo gosterimi)
    # DILAJAN_HOST=0.0.0.0 -> ayni ag uzerindeki cihazlardan LAN IP ile erisim
    share = os.environ.get("DILAJAN_SHARE", "").lower() in ("1", "true", "yes")
    host = os.environ.get("DILAJAN_HOST", "127.0.0.1")
    # Gradio 6: tema/stil/js launch()'ta verilir (VigilantAI karanlik SOC konsolu)
    build_ui().launch(server_name=host, server_port=7860, share=share,
                      theme=_THEME, css=_CSS, js=_FORCE_DARK_JS)
