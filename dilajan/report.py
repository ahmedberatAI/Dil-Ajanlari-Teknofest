"""Otomatik olay tutanagi (hizli-kazanim).

AnalysisResult -> resmi, disa-aktarilabilir Turkce Markdown TUTANAK. Tamamen deterministik (LLM yok).
"Alinan aksiyonlar" bolumu OPERATION_LOG'daki GERCEK cagri kayitlarindan (fonksiyon+args+sonuc) gelir.
Denetim/adli/raporlama izi + demoda somut cikti.
"""
from __future__ import annotations

import datetime
import re
from typing import List, Optional

from dilajan.schema import AnalysisResult
from dilajan.utils import QUERY_DATA_NOTE, operator_query_of


def _kayit_no(action_log: List[dict]) -> str:
    """Tutanak kayit-no'sunu OPERATION_LOG'daki olay_kaydi_olustur sonucundan (OLY-####) alir;
    yoksa zaman-tabanli uretir."""
    for d in action_log or []:
        m = re.search(r"OLY-\d{4}", str(d.get("result", "")))
        if m:
            return m.group(0)
    return "OLY-" + datetime.datetime.now().strftime("%Y%m%d%H%M")


def build_incident_report(result: AnalysisResult, action_log: Optional[List[dict]] = None,
                          camera: str = "—", now: Optional[str] = None,
                          query: Optional[str] = None) -> str:
    """AnalysisResult'tan Markdown olay tutanagi uretir. action_log verilmezse result.action_log kullanilir.

    `query`: operatorun serbest-metin analiz sorgusu (opsiyonel). Verilmezse karar-izinden
    geri okunur (`utils.operator_query_of`). Sorgu bolumu YALNIZCA `result.query_answer`
    doluyken eklenir; aksi halde tutanak metni -bolum numaralari dahil- BIREBIR eski halidir.
    """
    now = now or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log = action_log if action_log is not None else list(getattr(result, "action_log", []) or [])
    kayit = _kayit_no(log)

    # --- SORGU-GUDUMLU ANALIZ KAYDI (aciklanabilirlik / denetlenebilirlik) ---------------
    # B4 FAIL-OPEN: getattr + try, eski/yabanci sonuc nesneleri tutanagi cokertmez.
    # B2 VARSAYILAN KAPALI: `qa` bos -> asagidaki tek `if` calismaz, bolum numaralari 1..5
    #    olarak eski haliyle akar (tests/test_query_driven.py grup 14 BIREBIR karsilastirir).
    try:
        qa = str(getattr(result, "query_answer", None) or "").strip()
    except Exception:
        qa = ""
    q_txt = operator_query_of(result, query) if qa else ""

    _no = [0]

    def _sec(baslik: str) -> str:
        """Bolum basligi — numaralar SIRAYLA uretilir (sorgu bolumu eklenince kaymaz)."""
        _no[0] += 1
        return f"## {_no[0]}. {baslik}"

    lines = [
        f"# OLAY TUTANAĞI — {kayit}",
        "",
        f"- **Tarih / Saat:** {now}",
        f"- **Kamera / Konum:** {camera}",
        f"- **Video Süresi:** {result.video_duration or '—'}",
        f"- **Genel Risk:** {result.risk.level.value} — {result.risk.rationale}",
        "",
    ]
    if qa:
        # B5: operator metni VERI olarak, uyari cercevesi ICINDE yazilir — bu tutanak baska
        # bir modele beslenebilir; icindeki komut benzeri ifadeler talimat gibi durmamalidir.
        lines += [
            _sec("Operatör Sorgusu ve Ajan Yanıtı"),
            f"> ⚠️ _{QUERY_DATA_NOTE}_",
            "",
            "- **OPERATÖR SORGUSU (veri):** “"
            + (q_txt or "(sorgu metni bu kayıtta saklanmamış)") + "”",
            f"- **AJAN YANITI:** {qa}",
            "",
            "_Sorgu analizi **odaklar**, filtrelemez: sorguyla ilgisiz kritik olaylar da "
            "aşağıdaki bölümlerde raporlanır._",
            "",
        ]
    lines += [
        _sec("Özet"),
        (result.summary or "—"),
        "",
        _sec("Olay Zaman Çizelgesi"),
    ]
    if result.events:
        lines += ["| Zaman | Olay | Önem | Kategori | Konum |", "|---|---|---|---|---|"]
        for e in result.events:
            span = e.time + (f"–{e.end_time}" if e.end_time else "")
            olay = (e.event or "").replace("|", "/")
            lines.append(f"| {span} | {olay} | {e.severity.value} | {e.category.value} | {e.region or '—'} |")
    else:
        lines.append("_Kayda değer olay tespit edilmedi._")

    lines += ["", _sec("Alınan Operasyonel Aksiyonlar")]
    if log:
        for d in log:
            args = ", ".join(f"{k}={v}" for k, v in (d.get("args") or {}).items())
            lines.append(f"- **[{d.get('ts', '—')}] {d.get('function', '—')}**({args}) → {d.get('result', '')}")
    elif result.triggered_functions:
        lines += [f"- `{f}`" for f in result.triggered_functions]
    else:
        lines.append("- Operasyonel çağrı yapılmadı.")

    lines += ["", _sec("Öneriler")]
    if result.actions:
        for a in result.actions:
            lines.append(f"- **[{a.priority.value}]** {a.action}" + (f" — _{a.rationale}_" if a.rationale else ""))
    else:
        lines.append("- —")

    lines += [
        "", _sec("Onay"),
        "| Hazırlayan (Operatör) | İmza | Vardiya Amiri | İmza |",
        "|---|---|---|---|",
        "|  |  |  |  |",
        "",
        f"_Bu tutanak DilAjanları karar destek sistemi tarafından {now} tarihinde otomatik oluşturulmuştur._",
    ]
    return "\n".join(lines)
