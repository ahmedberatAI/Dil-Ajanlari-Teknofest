#!/usr/bin/env python
"""DilAjanlari — KAPSAMLI sartname-uyum raporu PDF (reportlab + DejaVu/Turkce, offline).
Her sartname gereksinimine 'karsiligimiz + kanit/skor' verir; model + mimari + guncel durust skorlar.
Cikti: docs/DilAjanlari_Sartname_Raporu.pdf
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
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                HRFlowable, PageBreak)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "DilAjanlari_Sartname_Raporu.pdf")
FD = "/usr/share/fonts/truetype/dejavu"
pdfmetrics.registerFont(TTFont("DV", os.path.join(FD, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", os.path.join(FD, "DejaVuSans-Bold.ttf")))

NAVY = colors.HexColor("#0b2545"); BLUE = colors.HexColor("#13315c"); ACCENT = colors.HexColor("#1f6feb")
LIGHT = colors.HexColor("#eef2f7"); GREEN = colors.HexColor("#1a7f37"); GRAY = colors.HexColor("#5a6472")
s = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=s["Heading1"], fontName="DVB", fontSize=14, textColor=NAVY, spaceBefore=10, spaceAfter=5)
H2 = ParagraphStyle("H2", parent=s["Heading2"], fontName="DVB", fontSize=11, textColor=BLUE, spaceBefore=7, spaceAfter=3)
BODY = ParagraphStyle("BODY", parent=s["BodyText"], fontName="DV", fontSize=9.2, leading=12.6, textColor=colors.HexColor("#1a1a1a"))
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=7.8, textColor=GRAY)
CELL = ParagraphStyle("CELL", parent=BODY, fontSize=8.3, leading=10.6)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="DVB")
TITLE = ParagraphStyle("TITLE", parent=s["Title"], fontName="DVB", fontSize=21, textColor=colors.white, alignment=TA_CENTER, leading=25)
SUB = ParagraphStyle("SUB", parent=BODY, fontSize=10, textColor=colors.white, alignment=TA_CENTER)


def P(t, st=BODY):
    return Paragraph(t, st)


def tbl(data, cw, header=True, green_col=None):
    t = Table(data, colWidths=cw, hAlign="LEFT", repeatRows=1)
    cmds = [("FONTNAME", (0, 0), (-1, -1), "DV"), ("FONTSIZE", (0, 0), (-1, -1), 8.3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d0da")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                 ("FONTNAME", (0, 0), (-1, 0), "DVB")]
    t.setStyle(TableStyle(cmds))
    return t


def arch():
    steps = [("ingest", "Video → zaman-damgalı kareler/segmentler (PyAV)"),
             ("perceive", "İki-aşamalı algı: tarif→olay + öz-doğrulama + grounding + poz/geofence"),
             ("reexamine (koşullu)", "Belirsiz (Orta) olayı yeniden-incele → CİDDİ↑ / RUTİN↓"),
             ("reason", "Türkçe özet + risk değerlendirmesi + aksiyon önerileri"),
             ("act", "Risk-kapısı: yüksek-riskte operasyonel fonksiyonları dinamik çağır"),
             ("finalize", "Yapılandırılmış JSON sonuç (olaylar+özet+risk+aksiyon+tetikler)")]
    W, bx, bh, gap = 470, 165, 26, 13
    d = Drawing(W, len(steps) * (bh + gap))
    y = len(steps) * (bh + gap) - bh
    for i, (n, de) in enumerate(steps):
        col = GREEN if "koşullu" in n else ACCENT
        d.add(Rect(0, y, bx, bh, rx=5, ry=5, fillColor=col, strokeColor=col))
        d.add(String(bx / 2, y + bh / 2 - 4, n, fontName="DVB", fontSize=8, fillColor=colors.white, textAnchor="middle"))
        d.add(String(bx + 10, y + bh / 2 - 3, de, fontName="DV", fontSize=7.6, fillColor=colors.HexColor("#1a1a1a")))
        if i < len(steps) - 1:
            ax = bx / 2
            d.add(Line(ax, y, ax, y - gap, strokeColor=GRAY, strokeWidth=1.1))
            d.add(Polygon([ax - 3, y - gap + 5, ax + 3, y - gap + 5, ax, y - gap], fillColor=GRAY, strokeColor=GRAY))
        y -= (bh + gap)
    return d


def build():
    doc = SimpleDocTemplate(OUT, pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm, title="DilAjanlari Sartname Raporu")
    W = doc.width
    E = []
    band = Table([[P("DilAjanları", TITLE)],
                  [P("Yerel Çok-Modlu Video Analiz &amp; Karar-Destek Ajanı", SUB)],
                  [P("TEKNOFEST 2026 TYDA — 3. Senaryo · Şartname-Uyum Raporu", SUB)]], colWidths=[W])
    band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY),
                              ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    E += [band, Spacer(1, 4),
          P("Tarih: 24.06.2026 · Model: <b>Qwen3-VL-8B-Instruct-FP8</b> (Apache-2.0) · Servis: vLLM 0.23 · "
            "Orkestrasyon: LangGraph · Donanım: tek RTX 5090 24GB · <b>Tamamen yerel/offline (yalnız 127.0.0.1)</b>", SMALL),
          Spacer(1, 6)]

    # Yonetici ozeti
    E += [P("Yönetici Özeti", H1),
          P("DilAjanları, savunma/saha gözetim videolarını anlayıp <b>zaman-damgalı olay tespiti, Türkçe özet, "
            "risk değerlendirmesi ve operatör aksiyon önerileri</b> üreten; gerektiğinde operasyonel fonksiyonları "
            "otonom tetikleyen ve operatörle Türkçe konuşan <b>tamamen yerel (bulut/dış-API yok)</b> bir "
            "<b>agentic</b> YZ ajanıdır. Şartmenin tüm zorunlu çıktıları karşılanır; çıktı, verilen mock JSON "
            "şemasıyla birebir uyumludur (%100).", BODY)]
    E += [Spacer(1, 3), tbl([
        ["Manşet Skor", "Değer", "Anlamı"],
        [P("Olay TESPİT-recall", CELLB), P("%96", CELL), P("anomali var/yok doğru bilme (alarm)", CELL)],
        [P("AKSİYON-recall", CELLB), P("%73", CELL), P("doğru güvenlik-tepki sınıfı (kullanım-amacı)", CELL)],
        [P("Flagship (yangın+düşme)", CELLB), P("%100 / %100", CELL), P("recall / risk-kalibrasyon (domain)", CELL)],
        [P("Tehlikeli yanlış-alarm (dar-FP)", CELLB), P("~%0", CELL), P("normalde sahte yüksek-alarm yok", CELL)],
        [P("Risk-kalibrasyon (QWK)", CELLB), P("0.733", CELL), P("ordinal uyum — 'substantial'", CELL)],
        [P("Diyalog kalitesi", CELLB), P("5.0 / 5", CELL), P("çok-turlu, bağımsız judge", CELL)],
    ], [42 * mm, 26 * mm, W - 68 * mm])]

    # 1. Problem + zorunlu ciktilar
    E += [Spacer(1, 6), P("1 · Problem Tanımı & Zorunlu Çıktılar (Şartname Karşılığı)", H1),
          P("3. Senaryo: video analiz eden, olay tespit eden, risk değerlendiren ve operatöre karar-destek sunan "
            "Türkçe YZ ajanı. Şartmenin <b>zorunlu çıktılarının</b> tamamı karşılanır:", BODY), Spacer(1, 3)]
    E += [tbl([
        ["Şartname gereksinimi", "Durum", "Karşılığımız / Kanıt"],
        [P("Video girdisi al + içeriği analiz et", CELL), P("✅", CELLB), P("ingest+perceive (PyAV kare/segment, VLM)", CELL)],
        [P("Olay / kişi / riskli durum tespiti", CELL), P("✅", CELLB), P("iki-aşamalı algı; TESPİT-recall %96", CELL)],
        [P("Kritik anları ZAMAN bilgisiyle belirle", CELL), P("✅", CELLB), P("olay time + zaman-pencereleri [00:30–00:50]", CELL)],
        [P("Kısa, anlaşılır TÜRKÇE özet", CELL), P("✅", CELLB), P("özet kalitesi ~4.6–5.0/5 (bağımsız judge)", CELL)],
        [P("Operatöre aksiyon önerileri", CELL), P("✅", CELLB), P("actions[öncelik,gerekçe] ~4.7/5", CELL)],
        [P("Yapılandırılmış JSON çıktı", CELL), P("✅", CELLB), P("to_sartname_dict — mock ile birebir, uyum %100", CELL)],
        [P("Offline/yerel + dış-API/kapalı-servis YOK", CELL), P("✅", CELLB), P("yalnız 127.0.0.1 (kodda doğrulandı)", CELL)],
        [P("vLLM veya benzeri yerel servisleme", CELL), P("✅", CELLB), P("vLLM 0.23, Qwen3-VL-8B-FP8", CELL)],
    ], [62 * mm, 14 * mm, W - 76 * mm])]

    # 2. Model & Mimari
    E += [Spacer(1, 6), P("2 · Model & Mimari (Framework + LLM)", H1),
          P("LangGraph tabanlı <b>agentic</b> akış; her düğüm hata-toleranslıdır (bir adım hata verse akış çökmeden "
            "devam eder). <b>perceive</b> sonrası <b>koşullu kenar</b> belirsiz olay varsa yeniden-inceleme döngüsü açar — "
            "bu, sistemi statik-doğrusal-pipeline olmaktan çıkarır (şartname: statik kural düşük puan).", BODY),
          Spacer(1, 3), arch(), Spacer(1, 4)]
    E += [tbl([
        ["Bileşen", "Seçim", "Gerekçe"],
        [P("Görsel-Dil Modeli", CELLB), P("Qwen3-VL-8B-Instruct-FP8", CELL), P("akıcı Türkçe + güçlü video anlama; tek 24GB GPU'ya sığar", CELL)],
        [P("Servisleme", CELLB), P("vLLM 0.23 (OpenAI-uyumlu)", CELL), P("düşük gecikme, continuous-batching, yerel", CELL)],
        [P("Orkestrasyon", CELLB), P("LangGraph ajan grafiği", CELL), P("çok-adımlı, koşullu, araç-çağıran akış", CELL)],
        [P("Uzman dedektörler", CELLB), P("YOLO11n / 11n-pose", CELL), P("poz-doğrulama + geofence + nesne kanıtı", CELL)],
        [P("Bağımsız değerlendirici", CELLB), P("Gemma-3-12B-it-FP8", CELL), P("öz-değerlendirme döngüselliğini kırar", CELL)],
    ], [33 * mm, 50 * mm, W - 83 * mm])]

    # 3. Cikti formati
    E += [Spacer(1, 6), P("3 · Çıktı Formatı (Mock JSON Uyumu)", H1),
          P("Her analiz, şartmenin mock örneğiyle <b>birebir uyumlu</b> yapılandırılmış JSON döner (uyum %100): "
            "<font face='DVB'>summary</font> (Türkçe özet), <font face='DVB'>events[]</font> (time, end_time, event, "
            "severity, category, bbox/region), <font face='DVB'>risk</font> (level + rationale), "
            "<font face='DVB'>actions[]</font> (action, priority, rationale), "
            "<font face='DVB'>triggered_functions[]</font> (tetiklenen operasyonel çağrılar). "
            "Açıklanabilirlik: her olayın severity'si, kategorisi, karedeki bölgesi ve risk gerekçesi yazılır.", BODY)]

    # 4. Yetenekler / ek ozellikler
    E += [Spacer(1, 5), P("4 · Yetenekler & Ek Özellikler", H1)]
    for f in [
        "<b>İki-aşamalı algı</b> (serbest tarif → olay çıkarımı) — düşük-çözünürlüklü CCTV'de algıyı açar.",
        "<b>Öz-doğrulama</b> (deduce-then-verify): yüksek-önemli olayı odaklı re-check; aşırı-yorumu reddeder.",
        "<b>Poz-tabanlı düşme doğrulama</b> (YOLO-poz): çömelen/eğilen işçiyi 'düşmüş' sanmaz, gerçek düşmeyi yakalar.",
        "<b>Hareket-belirginliği ipucu</b>: ani çarpışma/kaza anına dikkat → araç-kazası recall %89→100.",
        "<b>Güvenlik-analisti tehdit-yorumu</b>: şiddeti doğru adlandırır (risk-kalib +4, dar-FP −5).",
        "<b>Yasak-bölge geofence</b> (savunma): operatör-tanımlı bölgeye giriş → ihlal (recall %88, precision %100).",
        "<b>Mekânsal grounding</b>: native bbox → 3×3 Türkçe bölge ('üst sağ').",
        "<b>Dinamik dispatch-kapısı</b>: operasyonel fonksiyonlar yalnız gerçek yüksek-riskte → alarm-yorgunluğu kesilir.",
        "<b>Hızlı mod</b>: tek-geçiş algı → ~2.5× hız. <b>Watchdog</b>: tek-GPU otomatik yeniden-başlatma.",
        "<b>Operatör diyaloğu</b>: grounded, çok-turlu, açıklayıcı-soru soran, prompt-injection dirençli (5.0/5).",
    ]:
        E += [P("• " + f, BODY)]

    # 5. Skorlar
    E += [PageBreak(), P("5 · Performans Skorları (Ölçümleme & KPI)", H1),
          P("Tüm sayılar güncel model + tüm iyileştirmelerle ölçülmüştür. Tespit metrikleri <b>objektif</b> "
            "(veri etiketine karşı); kalite metrikleri <b>bağımsız</b> Gemma judge ile (döngüsel değil). "
            "Ham kayıtlar: <font face='DVB'>benchmark/results/</font>.", SMALL), Spacer(1, 3)]
    E += [P("5.1 · Üç-seviyeli recall (dürüst ölçüm)", H2),
          P("Aynı olayı üç farklı sıkılıkta ölçüyoruz — manşet tek-sayı yanıltıcı olmasın diye:", BODY),
          tbl([
              ["Seviye", "Skor", "Ne ölçer"],
              [P("TESPİT-recall", CELLB), P("%96", CELL), P("anomali var mı (alarm) — ikili", CELL)],
              [P("AKSİYON-recall", CELLB), P("%73", CELL), P("doğru güvenlik-TEPKİ sınıfı (kullanım-amacı)", CELL)],
              [P("TANIMA-recall", CELLB), P("%46", CELL), P("ince UCF alt-etiketi — grenli girdi-tavanı", CELL)],
          ], [34 * mm, 22 * mm, W - 56 * mm])]
    E += [Spacer(1, 4), P("5.2 · Veri seti bazında (objektif)", H2), tbl([
        ["Veri seti", "n", "Recall", "Risk-kalib", "dar-FP"],
        ["Senaryo (yangın+düşme+normal)", "30", "%100", "%100", "%0"],
        ["Overhead düşme (URFD)", "6", "%100", "%100", "%0"],
        ["Araç kazası (UCF Road)", "9", "%100", "%67", "%0"],
        ["UCF büyük (8 kategori)", "64", "%96", "%75", "%0"],
        ["UCF dengeli (8 kategori)", "32", "%96", "%75", "%0"],
        ["Gerçek düşme (GMDCSA)", "15", "%78", "%78", "%0"],
    ], [58 * mm, 10 * mm, 22 * mm, 24 * mm, W - 114 * mm])]
    E += [Spacer(1, 4), P("5.3 · Risk-kalibrasyon (ordinal) & kalite & hız", H2), tbl([
        ["Metrik", "Değer", "Kaynak/Not"],
        [P("QWK (ordinal risk uyumu)", CELL), P("0.733", CELL), P("'substantial'; tek '≥Yüksek %' yerine", CELL)],
        [P("Severity MAE / işaretli sapma", CELL), P("0.51 / −0.20", CELL), P("hafif sistematik düşük-puanlama", CELL)],
        [P("Savunma geofence", CELL), P("recall %88 / precision %100", CELL), P("yasak-bölge ihlali (deterministik)", CELL)],
        [P("Özet / aksiyon / risk-gerekçe", CELL), P("~4.6 / ~4.7 / ~5.0 / 5", CELL), P("bağımsız Gemma judge", CELL)],
        [P("Diyalog (tek-tur / çok-tur)", CELL), P("5.0 / 5.0", CELL), P("açıklayıcı-soru + injection direnci", CELL)],
        [P("Gecikme (tam / hızlı mod)", CELL), P("~1.5 / ~0.6 s/video-sn", CELL), P("segment paralel 3.2×", CELL)],
    ], [50 * mm, 40 * mm, W - 90 * mm])]

    # 6. Temel beklentiler uyum
    E += [Spacer(1, 6), P("6 · Temel Beklentiler — Şartname Karşılığı", H1), tbl([
        ["Beklenti", "Durum", "Karşılığımız"],
        [P("Multimodal anlama (sahne/zamansal/akış)", CELL), P("✅", CELLB), P("çok-kareli segment + bağlamsal yorum", CELL)],
        [P("Olay tespiti + anlamsal yorum (tür/önem/etki)", CELL), P("✅", CELLB), P("severity + kategori + risk gerekçesi", CELL)],
        [P("Zamansal farkındalık (başlangıç/gelişim/sonuç)", CELL), P("✅", CELLB), P("zaman-damgası + pencere + akış özeti", CELL)],
        [P("Türkçe doğal dil + özetleme", CELL), P("✅", CELLB), P("akıcılık 5.0; özet ~4.6–5.0/5", CELL)],
        [P("Karar destek (risk + uygulanabilir aksiyon)", CELL), P("✅", CELLB), P("risk-gerekçe ~5.0; aksiyon ~4.7", CELL)],
        [P("Açıklanabilir + yapılandırılmış çıktı", CELL), P("✅", CELLB), P("JSON %100 + bbox/bölge + gerekçe", CELL)],
        [P("Yerel servisleme (düşük gecikme, ~gerçek-zaman)", CELL), P("✅", CELLB), P("~1.5 s/vsn, paralel, FP8 24GB", CELL)],
        [P("Ölçümleme + KPI tanımlama", CELL), P("✅", CELLB), P("benchmark/ (eval/judge/holistic/aggregate)", CELL)],
        [P("Minimum statik yapı + akıllı pipeline", CELL), P("✅", CELLB), P("model-kararı + koşullu döngü + dinamik dispatch", CELL)],
        [P("Açık kaynak + tekrar-üretilebilir + dokümante", CELL), P("✅", CELLB), P("Apache-2.0, README, requirements-lock, docs/", CELL)],
    ], [70 * mm, 14 * mm, W - 84 * mm])]

    # 7. Zorluklar & cozumler (rigor/durustluk)
    E += [Spacer(1, 6), P("7 · Zorluklar & Çözümler (Bilimsel Titizlik)", H1),
          P("Her iyileştirme <b>ölçülmüş</b>; sadece kazandıran tutulmuş, kazandırmayan <b>dürüstçe reddedilmiştir</b> "
            "(kaydı docs/iyilestirmeler.md'de). Bu, 'bir sayıya tune etme' yerine araştırma olgunluğunu gösterir:", BODY),
          Spacer(1, 2), tbl([
              ["Zorluk", "Çözüm / Sonuç"],
              [P("Çömelen işçiyi 'düşmüş' sanma", CELL), P("YOLO-poz doğrulama → sahte düşme kesildi, gerçek korundu", CELL)],
              [P("Araç-kazası anını kaçırma", CELL), P("hareket-belirginliği ipucu → recall %89→100 (FP'siz)", CELL)],
              [P("Şiddeti yüzeysel yorumlama", CELL), P("tehdit-yorumu katmanı → risk-kalib +4, dar-FP −5", CELL)],
              [P("Grenli 320×240'ta tür-tanıma", CELL), P("GİRDİ-TAVANI (zoom/CLIP/poz/silah-det ölçülüp elendi)", CELL)],
              [P("Ölçüm-geçerliliği (recall yanıltıcı)", CELL), P("3-seviyeli recall + ordinal kalibrasyon eklendi", CELL)],
              [P("Tek-GPU güvenilirliği", CELL), P("watchdog otomatik yeniden-başlatma", CELL)],
          ], [55 * mm, W - 55 * mm])]
    E += [P("<b>Reddedilen (ölçülü) yöntemler:</b> 32B/InternVL model, CLAHE, action-cue/temporal-CoT promptu, "
            "evidence-şema, self-consistency (varsayılan), benign-gate, threat-lens V2, persist, risk-bias, LoRA "
            "(no-go) — hepsi A/B ile ölçülüp net kazanç vermediği için elendi. Şeffaf kayıt = jüri güveni.", SMALL)]

    # 8. Otonomi + 9. Yenilik + 10. eksenler
    E += [Spacer(1, 5), P("8 · Otonomi & Zekâ · 9 · Yenilikçilik", H1)]
    E += [P("<b>Otonomi:</b> niyet anlama + akıl yürütme; <b>koşullu yeniden-inceleme döngüsü</b> (graf doğrusal değil); "
            "<b>öz-doğrulama</b>; belirsizlikte <b>açıklayıcı soru</b> sorar; beklenmedik/saldırgan girdiye dayanıklı "
            "(prompt-injection reddi); <b>dinamik araç seçimi</b> (operasyonel fonksiyonları model seçer). Diyalog 5.0/5.", BODY)]
    E += [P("<b>Yenilik (dürüst, kombinasyonel):</b> tespit→<b>operasyonel aksiyon</b> kapatma (risk-kapılı; akademik "
            "sistemler aktüasyona gitmez) · <b>Türkçe</b> egemen + tam-offline + tek-24GB-GPU · <b>poz/geofence uzman "
            "ensemble</b> · <b>3-seviyeli dürüst metrik</b> + bağımsız-judge değerlendirme titizliği.", BODY)]
    E += [Spacer(1, 3), P("10 · Değerlendirme Eksenleri (öz-değerlendirme)", H2), tbl([
        ["Eksen (ağırlık)", "Durum", "Dayanak"],
        [P("Fonksiyonellik (%35)", CELLB), P("Güçlü", CELL), P("uçtan-uca + mock-fonksiyon + kararlı çalışma", CELL)],
        [P("Teknik / Mimari (%35)", CELLB), P("Güçlü", CELL), P("agent+tools+memory+koşullu döngü; ölçüm titizliği", CELL)],
        [P("Otonomi / Zekâ (%20)", CELLB), P("Çok güçlü", CELL), P("açıklayıcı-soru, öz-kontrol, diyalog 5.0", CELL)],
        [P("Yenilikçilik (%10)", CELLB), P("Orta-iyi", CELL), P("operasyonel katman + egemen-offline + metrik", CELL)],
    ], [40 * mm, 22 * mm, W - 62 * mm])]

    # 11. Olcekleme + durust sinirlar + 12 teslimatlar
    E += [Spacer(1, 5), P("11 · Ölçekleme, Dağıtım & Dürüst Sınırlar", H1),
          P("<b>Ölçekleme:</b> segment-paralel (3.2× hızlanma), FP8 ile tek 24GB GPU; canlı kamera/RTSP kayan-pencere "
            "yolu mevcut; hızlı mod yüksek-hacim için. <b>Dağıtım:</b> air-gapped; tesise-özgü kurallar + yasak-bölge "
            "operatörce tanımlanır.", BODY),
          P("<b>Dürüst sınırlar:</b> (1) grenli 320×240 sokak-CCTV'de ince suç-TÜRÜ tanıma girdi-tavanı (%46); "
            "domain-uygun yüksek-res veride tanıma ~%100. (2) Gerçek savunma-tesisi videosu açık veride yok — "
            "savunma-ilgili yetenekler vekil veriyle doğrulandı; tesise özelleştirme kurumun kendi verisiyle yapılır. "
            "(3) Tek-GPU donanımsal (watchdog ile güvenilir).", SMALL)]
    E += [Spacer(1, 4), P("12 · Teslimatlar", H2), tbl([
        ["Teslimat", "Durum"],
        [P("Çalışan kod + kurulum (GitHub, README, requirements-lock)", CELL), P("✅", CELLB)],
        [P("Dokümantasyon (mimari+diyagram, framework+LLM, senaryo, zorluk+çözüm, ölçüm, ölçekleme)", CELL), P("✅", CELLB)],
        [P("Bu rapor (model+mimari+skor+şartname-uyum PDF)", CELL), P("✅", CELLB)],
        [P("Demo videosu (≤10 dk, bağlam-değişimi) · Sunum PDF+PPTX · GitHub topic/başvuru", CELL), P("⚠️ takım-tarafı", CELLB)],
    ], [W - 32 * mm, 32 * mm])]

    E += [Spacer(1, 6), HRFlowable(width="100%", color=colors.HexColor("#c8d0da")),
          P("DilAjanları · TEKNOFEST 2026 TYDA 3. Senaryo · Apache-2.0 · Tamamen yerel/offline · "
            "GitHub: ahmedberatAI/Dil-Ajanlari-Teknofest · Tüm skorlar ölçülmüş ve benchmark/results'ta kayıtlıdır.", SMALL)]

    doc.build(E)
    print(f"PDF yazildi: {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB)")


if __name__ == "__main__":
    build()
