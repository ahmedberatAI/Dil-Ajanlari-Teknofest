#!/usr/bin/env python
"""DilAjanlari — model + mimari + skorlari anlatan PDF raporu uretir (reportlab + DejaVu/Turkce).
Cikti: docs/DilAjanlari_Rapor.pdf
"""
from __future__ import annotations

import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "DilAjanlari_Rapor.pdf")

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
pdfmetrics.registerFont(TTFont("DV", os.path.join(FONT_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")))

NAVY = colors.HexColor("#0b2545")
BLUE = colors.HexColor("#13315c")
ACCENT = colors.HexColor("#1f6feb")
LIGHT = colors.HexColor("#eef2f7")
GREEN = colors.HexColor("#1a7f37")
GRAY = colors.HexColor("#5a6472")

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="DVB", fontSize=15, textColor=NAVY, spaceBefore=10, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="DVB", fontSize=11.5, textColor=BLUE, spaceBefore=8, spaceAfter=4)
BODY = ParagraphStyle("BODY", parent=styles["BodyText"], fontName="DV", fontSize=9.3, leading=13, textColor=colors.HexColor("#1a1a1a"), alignment=TA_LEFT)
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=8, textColor=GRAY)
CELL = ParagraphStyle("CELL", parent=BODY, fontSize=8.6, leading=11)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="DVB")
TITLE = ParagraphStyle("TITLE", parent=styles["Title"], fontName="DVB", fontSize=22, textColor=colors.white, alignment=TA_CENTER, leading=26)
SUB = ParagraphStyle("SUB", parent=BODY, fontSize=10.5, textColor=colors.white, alignment=TA_CENTER)


def P(t, s=BODY):
    return Paragraph(t, s)


def tbl(data, col_widths, header=True):
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    cmds = [
        ("FONTNAME", (0, 0), (-1, -1), "DV"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d0da")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                 ("FONTNAME", (0, 0), (-1, 0), "DVB")]
    t.setStyle(TableStyle(cmds))
    return t


def arch_diagram():
    """Dikey akis diyagrami: ingest -> perceive -> (kosullu) reexamine -> reason -> act -> finalize."""
    steps = [
        ("ingest", "Video → zaman-damgali kareler / segmentler (PyAV, overlap)"),
        ("perceive", "İki-aşamalı algı: tarif → olay çıkarımı + öz-doğrulama + grounding"),
        ("reexamine  (koşullu)", "Belirsiz (Orta) olayları yeniden-incele → CIDDI↑ / RUTIN↓"),
        ("reason", "Türkçe özet + risk değerlendirmesi + aksiyon önerileri (JSON)"),
        ("act", "Risk-kapısı: yüksek-riskte mock operasyonel fonksiyonları dinamik çağır"),
        ("finalize", "Yapılandırılmış sonuç (olaylar + özet + risk + aksiyon + tetikler)"),
    ]
    W, bx, bh, gap = 470, 150, 30, 16
    H = len(steps) * (bh + gap)
    d = Drawing(W, H)
    y = H - bh
    for i, (name, desc) in enumerate(steps):
        col = ACCENT if "koşullu" not in name else GREEN
        d.add(Rect(0, y, bx, bh, rx=5, ry=5, fillColor=col, strokeColor=col))
        d.add(String(bx / 2, y + bh / 2 - 4, name, fontName="DVB", fontSize=8.5, fillColor=colors.white, textAnchor="middle"))
        d.add(String(bx + 12, y + bh / 2 - 3, desc, fontName="DV", fontSize=8, fillColor=colors.HexColor("#1a1a1a")))
        if i < len(steps) - 1:
            ax = bx / 2
            d.add(Line(ax, y, ax, y - gap, strokeColor=GRAY, strokeWidth=1.2))
            d.add(Polygon([ax - 3, y - gap + 5, ax + 3, y - gap + 5, ax, y - gap], fillColor=GRAY, strokeColor=GRAY))
        y -= (bh + gap)
    return d


def build():
    doc = SimpleDocTemplate(OUT, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm, title="DilAjanlari Raporu")
    E = []

    # --- Baslik bandi ---
    band = Table([[P("DilAjanları", TITLE)], [P("Yerel Çok-Modlu Video Analiz &amp; Karar-Destek Ajanı", SUB)],
                  [P("TEKNOFEST 2026 TYDA — 3. Senaryo · Model + Mimari + Skorlar", SUB)]],
                 colWidths=[doc.width])
    band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("TOPPADDING", (0, 0), (-1, -1), 7),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    E += [band, Spacer(1, 5), P("Tarih: 22.06.2026 · Model: Qwen3-VL-8B-Instruct-FP8 (Apache-2.0) · "
                                "Donanım: tek RTX 5090 24GB · Tamamen yerel/offline (yalnız 127.0.0.1)", SMALL),
          Spacer(1, 8)]

    # --- 1. Model ---
    E += [P("1 · Model ve Yaklaşım", H1)]
    E += [P("Sistem, savunma/endüstriyel gözetim videolarını anlayıp <b>zaman-damgalı olay tespiti, "
            "Türkçe özet, risk değerlendirmesi ve operatör aksiyon önerileri</b> üreten; ayrıca operatörle "
            "Türkçe konuşan <b>tamamen yerel (bulut/dış-API yok)</b> bir <b>agentic</b> yapay-zekâ ajanıdır.", BODY)]
    E += [tbl([
        ["Bileşen", "Seçim", "Gerekçe"],
        [P("Görsel-Dil Modeli", CELLB), P("Qwen3-VL-8B-Instruct-FP8", CELL), P("Akıcı Türkçe + güçlü video anlama; tek 24GB GPU'ya sığar (FP8)", CELL)],
        [P("Servisleme", CELLB), P("vLLM 0.23 (OpenAI-uyumlu)", CELL), P("Düşük gecikme, continuous-batching, yerel", CELL)],
        [P("Orkestrasyon", CELLB), P("LangGraph ajan grafiği", CELL), P("Çok-adımlı, koşullu, araç-çağıran akış", CELL)],
        [P("Yedek model", CELLB), P("Qwen2.5-VL-7B", CELL), P("Hassasiyet-öncelikli alternatif", CELL)],
        [P("Çalışma", CELLB), P("Offline / air-gapped", CELL), P("Sadece 127.0.0.1; veri tesisten çıkmaz", CELL)],
    ], [33 * mm, 52 * mm, doc.width - 85 * mm])]

    # --- 2. Mimari ---
    E += [Spacer(1, 6), P("2 · Mimari", H1)]
    E += [P("LangGraph tabanlı agentic akış; her düğüm hata-toleranslıdır (bir adım hata verirse akış çökmeden "
            "devam eder). <b>perceive</b> sonrası <b>koşullu kenar</b> belirsiz olay varsa yeniden-inceleme döngüsü açar.", BODY)]
    E += [Spacer(1, 4), arch_diagram(), Spacer(1, 6)]
    E += [P("Öne çıkan teknik bileşenler", H2)]
    feats = [
        "<b>İki-aşamalı algı</b> (serbest tarif → yapılandırılmış olay çıkarımı) — düşük-çözünürlüklü CCTV'de algıyı açar.",
        "<b>Öz-doğrulama</b> (deduce-then-verify): yüksek-önemli olayı odaklı re-check; aşırı-yorumu reddeder.",
        "<b>Mekânsal grounding</b>: native bbox → 3×3 Türkçe bölge ('üst sağ' vb.).",
        "<b>Dinamik dispatch-kapısı</b>: operasyonel fonksiyonlar (sağlık/güvenlik/acil-durdurma) yalnız gerçek yüksek-riskte → alarm-yorgunluğu kesilir.",
        "<b>Hızlı mod</b>: tek-geçiş algı → ~2.5× hız, doğruluk korunur (gerçeğe-yakın).",
        "<b>Güvenilirlik</b>: watchdog (otomatik yeniden-başlatma) + zarif bozulma + iki-dilli severity + Türkçe dil-saflığı guard.",
        "<b>Operatör diyaloğu</b>: grounded, çok-turlu, açıklayıcı-soru soran, prompt-injection dirençli Türkçe sohbet.",
    ]
    for f in feats:
        E += [P("• " + f, BODY)]

    # --- 3. Skorlar ---
    E += [Spacer(1, 6), P("3 · Performans Skorları", H1)]
    E += [P("Tüm sayılar güncel model + tüm iyileştirmelerle ölçülmüştür. Tespit metrikleri <b>objektif</b> "
            "(dataset etiketine karşı); kalite metrikleri <b>bağımsız</b> Gemma-3-12B judge ile (döngüsel değil).", SMALL)]

    E += [Spacer(1, 4), P("3.1 · Olay tespiti (anomali recall) — objektif", H2)]
    E += [tbl([
        ["Veri seti", "n", "Recall", "Risk-kalib.", "Not"],
        ["Senaryo (yangın+düşme+normal)", "30", "%99 ± 2", "%96", "in-domain, kararlı"],
        ["Holistik temsili", "9", "%100", "—", "yangın/düşme/patlama/kaza"],
        ["URFD overhead düşme", "6", "%100", "%100", "gerçek gözetim/tavan açısı"],
        ["Büyük UCF (8 kategori)", "48", "%92", "%75", "grainy 320×240, büyük-n"],
        ["GMDCSA gerçek düşme", "15", "%89", "%78", "gerçek, frontal"],
        ["Araç kazası (RoadAccidents)", "9", "%89", "%67", "gerçek CCTV, devrilme"],
    ], [55 * mm, 10 * mm, 22 * mm, 22 * mm, doc.width - 109 * mm])]

    E += [Spacer(1, 5), P("3.2 · Çıktı kalitesi — bağımsız judge (1–5) ve şema", H2)]
    E += [tbl([
        ["Metrik", "Skor", "Kaynak"],
        ["Özet kalitesi", "4.64 / 5", "bağımsız (Gemma), n=90"],
        ["Aksiyon kalitesi", "4.66 – 4.83 / 5", "bağımsız + holistik"],
        ["Risk gerekçe kalitesi", "4.87 – 5.00 / 5", "bağımsız + holistik"],
        ["JSON şema uyumu", "%100", "objektif (mock'la birebir)"],
        ["Diyalog (tek-tur / çok-tur)", "5.0 / 5.0", "self + bağımsız"],
    ], [50 * mm, 35 * mm, doc.width - 85 * mm])]

    E += [Spacer(1, 5), P("3.3 · Gecikme ve koşu-arası varyans (dürüstlük)", H2)]
    E += [tbl([
        ["Boyut", "Değer", "Açıklama"],
        ["Gecikme — tam mod", "~1.5 sn / video-sn", "segment paralel"],
        ["Gecikme — hızlı mod", "~0.61 sn / video-sn (2.5×)", "doğruluk korunur"],
        ["Varyans — Senaryo", "%99 ± 2 [94–100]", "16 koşu (objektif)"],
        ["Varyans — UCF grainy", "%86 ± 12 [58–100]", "13 koşu (off-domain stres)"],
        ["Varyans — GMDCSA düşme", "%80 ± 11 [67–89]", "5 koşu"],
        ["Normal yanlış-pozitif", "dar %0–8 · dispatch ~%0", "zararlı alarm kesildi"],
    ], [45 * mm, 50 * mm, doc.width - 95 * mm])]

    # --- 4. Sartname + farklilasma ---
    E += [Spacer(1, 6), P("4 · Şartname Uyumu ve Konumlanma", H1)]
    E += [P("<b>Zorunlu çıktıların tamamı karşılanıyor:</b> video analizi · zaman-damgalı kritik an · "
            "kısa Türkçe özet · risk · operatör aksiyonu · yapılandırılmış JSON (%100) · offline · ~gerçek-zaman. "
            "Puanlama eksenleri: İşlevsellik <b>güçlü</b>, Teknik/Mimari <b>güçlü</b>, Otonomi <b>çok güçlü</b> "
            "(diyalog 5.0), Yenilikçilik <b>orta-iyi</b>.", BODY)]
    E += [Spacer(1, 3), P("Benzerlerinden ayıran (dürüst, dar ve kombinasyonel)", H2)]
    for f in [
        "Tespit→<b>operasyonel aksiyon</b> kapatma (risk-kapılı) — akademik sistemler skor/açıklamada durur, aktüasyona gitmez.",
        "<b>Türkçe</b> operatör NL + korumalı çok-turlu diyalog — kamuya açık Türkçe video-anlama gözetim ajanı bulunamadı.",
        "<b>Tam-offline + açık-kaynak + tek 24GB GPU</b> — referans sistemler (NVIDIA VSS) 1–4× 80GB datacenter ister.",
        "<b>Değerlendirme titizliği</b> — çapraz-aile judge + objektif/judged ayrımı + varyans (yarışmada nadir).",
    ]:
        E += [P("• " + f, BODY)]
    E += [Spacer(1, 3), P("Dürüst sınırlar: temel model Türkçe değil (yerlileştirme uygulama/UX katmanında); "
                          "grainy off-domain tür-adlandırma zayıf (%44, girdi-tavanı); gerçek savunma-tesisi "
                          "videosu açık veride yok; tek-GPU donanımsal (watchdog ile güvenilir).", SMALL)]
    E += [Spacer(1, 6), HRFlowable(width="100%", color=colors.HexColor("#c8d0da")),
          P("DilAjanları · TEKNOFEST 2026 TYDA 3. Senaryo · Apache-2.0 · GitHub: ahmedberatAI/Dil-Ajanlari-Teknofest", SMALL)]

    doc.build(E)
    print(f"PDF yazildi: {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB)")


if __name__ == "__main__":
    build()
