#!/usr/bin/env python
"""HIZLI SUNUM PDF'i — is akisi ve katmanlar (gorsel agirlikli).

Amac: mentora 10-15 dakikada sistemi ANLATMAK. Kapsamli teknik rapor DEGIL
(o docs/DilAjanlari_Model_Anlatimi.pdf'tedir); bu belge KATMANLARI ve
IS AKISINI gosterir.

Desen kaynagi: scripts/make_model_pdf.py (font kaydi, yardimcilar, diyagram araclari).
Cikti: docs/DilAjanlari_Is_Akisi.pdf
"""
from __future__ import annotations

import os

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIKTI = os.path.join(KOK, "docs", "DilAjanlari_Is_Akisi.pdf")

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
pdfmetrics.registerFont(TTFont("DV", os.path.join(FONT_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DVM", os.path.join(FONT_DIR, "DejaVuSansMono.ttf")))

NAVY = colors.HexColor("#0f2547")
BLUE = colors.HexColor("#1668b3")
TEAL = colors.HexColor("#0d7c86")
GRAY = colors.HexColor("#5a6472")
LIGHT = colors.HexColor("#eef3f8")
GREEN = colors.HexColor("#1a7f45")
AMBER = colors.HexColor("#b06a00")
RED = colors.HexColor("#9d2222")
PURPLE = colors.HexColor("#5b3f8c")

GENIS = 165 * mm

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="DVB", fontSize=17,
                    textColor=NAVY, spaceBefore=2, spaceAfter=3)
KICKER = ParagraphStyle("KICKER", parent=styles["BodyText"], fontName="DVB", fontSize=8.4,
                        textColor=BLUE, spaceAfter=1, leading=10)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="DVB", fontSize=11,
                    textColor=BLUE, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("BODY", parent=styles["BodyText"], fontName="DV", fontSize=9.8,
                      leading=14.2, textColor=colors.HexColor("#1a1a1a"), alignment=TA_LEFT,
                      spaceAfter=5)
BIG = ParagraphStyle("BIG", parent=BODY, fontSize=11.2, leading=16)
BULLET = ParagraphStyle("BULLET", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=4)
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=8.2, textColor=GRAY, leading=11.2)
MONO = ParagraphStyle("MONO", parent=BODY, fontName="DVM", fontSize=8.2, leading=11.8,
                      textColor=NAVY)
CELL = ParagraphStyle("CELL", parent=BODY, fontSize=8.6, leading=11.6, spaceAfter=0)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="DVB")
CELLH = ParagraphStyle("CELLH", parent=CELLB, textColor=colors.white)
TITLE = ParagraphStyle("TITLE", parent=styles["Title"], fontName="DVB", fontSize=27,
                       textColor=colors.white, alignment=TA_CENTER, leading=33)
SUB = ParagraphStyle("SUB", parent=BODY, fontSize=11, textColor=colors.white,
                     alignment=TA_CENTER, spaceAfter=0)
SUB2 = ParagraphStyle("SUB2", parent=BODY, fontSize=9.2, textColor=colors.HexColor("#c2d4ea"),
                      alignment=TA_CENTER, spaceAfter=0)


def P(t, s=BODY):
    return Paragraph(t, s)


def B(t):
    return Paragraph(t, BULLET, bulletText="•")


def tablo(satirlar, genislikler, baslik=True, etiket_sutunu=False):
    data = []
    for i, sat in enumerate(satirlar):
        satir = []
        for j, h in enumerate(sat):
            if baslik and i == 0:
                stil = CELLH
            elif etiket_sutunu and j == 0:
                stil = CELLB
            else:
                stil = CELL
            satir.append(Paragraph(str(h), stil))
        data.append(satir)
    t = Table(data, colWidths=genislikler, hAlign="LEFT", repeatRows=1 if baslik else 0)
    komut = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d2de")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if baslik:
        komut += [("BACKGROUND", (0, 0), (-1, 0), NAVY),
                  ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                   [colors.white, colors.HexColor("#f4f7fb")])]
    if etiket_sutunu:
        komut += [("BACKGROUND", (0, 0), (0, -1), LIGHT)]
    t.setStyle(TableStyle(komut))
    return t


def vurgu(baslik, govde, renk=AMBER):
    ic = [Paragraph(f"<b>{baslik}</b>", ParagraphStyle(
        "vb", parent=BODY, fontName="DVB", fontSize=9.4, textColor=renk, spaceAfter=2))]
    ic.append(Paragraph(govde, ParagraphStyle("vg", parent=BODY, fontSize=9.2, leading=13,
                                              spaceAfter=0)))
    k = Table([[ic]], colWidths=[GENIS])
    k.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbf8f2")),
        ("LINEBEFORE", (0, 0), (0, -1), 2.6, renk),
        ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#e3dccf")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return k


# ---------------------------------------------------------------------------
# Cizim yardimcilari
# ---------------------------------------------------------------------------
def _kutu(d, x, y, w, h, metin, renk=NAVY, yazi=colors.white, fs=8.4, alt=None, afs=6.8):
    d.add(Rect(x, y, w, h, fillColor=renk, strokeColor=renk, rx=3, ry=3))
    dy = h / 2.0 - fs * 0.36 + (4.4 if alt else 0)
    d.add(String(x + w / 2.0, y + dy, metin, fontName="DVB", fontSize=fs,
                 fillColor=yazi, textAnchor="middle"))
    if alt:
        d.add(String(x + w / 2.0, y + h / 2.0 - afs * 0.36 - 5.2, alt, fontName="DV",
                     fontSize=afs, fillColor=yazi, textAnchor="middle"))


def _cerceve(d, x, y, w, h, renk, dolgu="#ffffff"):
    d.add(Rect(x, y, w, h, fillColor=colors.HexColor(dolgu), strokeColor=renk,
               strokeWidth=1.1, rx=4, ry=4))


def _cizgi(d, x1, y1, x2, y2, renk=GRAY, kalinlik=1.2, kesik=None):
    ln = Line(x1, y1, x2, y2, strokeColor=renk, strokeWidth=kalinlik)
    if kesik:
        ln.strokeDashArray = kesik
    d.add(ln)


def _ok_sag(d, x, y, renk=GRAY):
    s = 4.2
    d.add(Polygon([x, y, x - s * 1.7, y + s, x - s * 1.7, y - s],
                  fillColor=renk, strokeColor=renk))


def _ok_asagi(d, x, y, renk=GRAY):
    s = 4.2
    d.add(Polygon([x, y, x - s, y + s * 1.7, x + s, y + s * 1.7],
                  fillColor=renk, strokeColor=renk))


def _yazi(d, x, y, metin, fs=7, renk=GRAY, hiza="middle", kalin=False):
    d.add(String(x, y, metin, fontName="DVB" if kalin else "DV", fontSize=fs,
                 fillColor=renk, textAnchor=hiza))


# ---------------------------------------------------------------------------
# DIYAGRAM 1 — Katman yigini
# ---------------------------------------------------------------------------
def katman_yigini():
    W, H = 468, 300
    d = Drawing(W, H)
    bant = [
        ("5 · SUNUM",       "Operatör konsolu · olay tutanağı · kanıt paketi · vardiya brifingi",
         PURPLE, "#f3f0f9"),
        ("4 · EYLEM",       "Sevk kapısı · operasyonel fonksiyonlar · karar izi",
         RED, "#fbf1f1"),
        ("3 · AKIL YÜRÜTME", "Yeniden inceleme · tesis politikası · özet, risk, aksiyon",
         AMBER, "#fdf7ee"),
        ("2 · ALGI",        "İki aşamalı VLM · YOLO poz/bölge · kurcalama tespiti",
         TEAL, "#eef7f8"),
        ("1 · GİRDİ",       "Video çözme · zaman damgalı kare · segment · sahne kesimi",
         BLUE, "#eef3fb"),
    ]
    yh, bosluk = 44, 8
    y_ust = H - 30                    # bantlarin ustu (baslik altinda)
    y = y_ust
    for ad, aciklama, renk, dolgu in bant:
        y -= yh
        _cerceve(d, 96, y, 336, yh, renk, dolgu)
        d.add(Rect(96, y, 5, yh, fillColor=renk, strokeColor=renk))
        _yazi(d, 112, y + yh - 17, ad, 9, renk, "start", True)
        _yazi(d, 112, y + 11, aciklama, 7.2, colors.HexColor("#333333"), "start")
        y -= bosluk
    y_alt = y + bosluk                # en alttaki bandin alt kenari

    # sol taraf: dikey akis oku (asagidan yukari)
    _cizgi(d, 74, y_alt + 4, 74, y_ust - 4, NAVY, 1.6)
    d.add(Polygon([74, y_ust, 70, y_ust - 7, 78, y_ust - 7],
                  fillColor=NAVY, strokeColor=NAVY))
    orta = (y_ust + y_alt) / 2
    _yazi(d, 58, orta + 5, "VERİ", 7.6, NAVY, "middle", True)
    _yazi(d, 58, orta - 6, "AKIŞI", 7.6, NAVY, "middle", True)

    # sag taraf: butun katmanlari capraz kesen olcum seridi
    _cerceve(d, 442, y_alt, 16, y_ust - y_alt, GRAY, "#f5f6f8")
    harfler = "ÖLÇÜM"
    bas = orta + (len(harfler) - 1) * 6.5
    for i, ch in enumerate(harfler):
        _yazi(d, 450, bas - i * 13, ch, 7.4, GRAY, "middle", True)

    _yazi(d, W / 2, H - 12, "KATMAN MİMARİSİ — veri aşağıdan yukarı akar",
          8.6, NAVY, "middle", True)
    return d


# ---------------------------------------------------------------------------
# DIYAGRAM 2 — 7 dugumlu is akisi
# ---------------------------------------------------------------------------
def akis_diyagrami():
    """Dikey yerlesim (yukaridan asagi): baslik · VIDEO · dugum siras · kosullu yay ·
    yardimci katman · cikti. Tum ogeler Drawing sinirlari ICINDE kalir."""
    W, H = 468, 268
    d = Drawing(W, H)
    kw, kh, ara = 58, 40, 7          # 7*58 + 6*7 = 448  ->  10..458 arasi sigar
    y_baslik = H - 11
    y_video = H - 52                 # yukseklik 24
    y_dugum = H - 122                # yukseklik 40
    y_yay = y_dugum - 22             # kosullu atlama yayi
    y_yard = 22                      # yardimci algi kutusu (yukseklik 32)
    y_cikti = 22                     # cikti sozlesmesi (yukseklik 34)

    _yazi(d, W / 2, y_baslik, "LANGGRAPH DURUM MAKİNESİ — 7 düğüm", 8.6, NAVY, "middle", True)

    # --- VIDEO girisi ---
    _kutu(d, 10, y_video, kw, 24, "VİDEO", GRAY, colors.white, 8)
    _cizgi(d, 10 + kw / 2, y_video, 10 + kw / 2, y_dugum + kh + 6)
    _ok_asagi(d, 10 + kw / 2, y_dugum + kh + 2)

    # --- ana zincir ---
    dugumler = [
        ("ingest", "kare çıkar", BLUE),
        ("perceive", "2 aşamalı", TEAL),
        ("reexamine", "koşullu", AMBER),
        ("policy_gate", "tesis kuralı", AMBER),
        ("reason", "özet·risk", AMBER),
        ("act", "sevk kapısı", RED),
        ("finalize", "sözleşme", PURPLE),
    ]
    x = 10
    konum = []
    for ad, alt, renk in dugumler:
        _kutu(d, x, y_dugum, kw, kh, ad, renk, colors.white, 7.8, alt, 6.2)
        konum.append((x, x + kw))
        x += kw + ara
    for i in range(len(dugumler) - 1):
        x1 = konum[i][1]
        _cizgi(d, x1 + 1, y_dugum + kh / 2, x1 + ara - 4, y_dugum + kh / 2)
        _ok_sag(d, x1 + ara, y_dugum + kh / 2)

    # --- kosullu atlama: perceive -> policy_gate (reexamine ATLANIR) ---
    px = konum[1][0] + kw / 2
    gx = konum[3][0] + kw / 2
    _cizgi(d, px, y_dugum, px, y_yay, AMBER, 1.1, [3, 2])
    _cizgi(d, px, y_yay, gx, y_yay, AMBER, 1.1, [3, 2])
    _cizgi(d, gx, y_yay, gx, y_dugum - 4, AMBER, 1.1, [3, 2])
    _ok_asagi(d, gx, y_dugum - 8, AMBER)
    _yazi(d, (px + gx) / 2, y_yay - 11, "olay \"Orta\" değilse ATLA (adaptif otonomi)",
          6.6, AMBER, "middle")

    # --- yardimci algi katmani: perceive'i BESLER (asagidan yukari ok) ---
    # Ok, kosullu yayin dikey kolundan (px) 14 birim SOLDA cizilir ki cakismasin.
    _cerceve(d, 10, y_yard, 186, 32, TEAL, "#eef7f8")
    _yazi(d, 103, y_yard + 21, "YARDIMCI ALGI", 7.4, TEAL, "middle", True)
    _yazi(d, 103, y_yard + 9, "YOLO11n poz · bölge · araç · kurcalama", 6.8,
          colors.HexColor("#333333"), "middle")
    ox = px - 14
    _cizgi(d, ox, y_yard + 32, ox, y_dugum - 5, TEAL, 1.1, [3, 2])
    d.add(Polygon([ox, y_dugum - 1, ox - 4, y_dugum - 8, ox + 4, y_dugum - 8],
                  fillColor=TEAL, strokeColor=TEAL))

    # --- cikti sozlesmesi ---
    _cerceve(d, 248, y_cikti, 210, 34, PURPLE, "#f6f3fb")
    _yazi(d, 353, y_cikti + 22, "ÇIKTI SÖZLEŞMESİ — tam 4 anahtar", 7.4, PURPLE,
          "middle", True)
    _yazi(d, 353, y_cikti + 9, "summary · events[] · risk · actions[]", 7,
          colors.HexColor("#333333"), "middle")
    fx = konum[6][0] + kw / 2
    _cizgi(d, fx, y_dugum, fx, y_cikti + 34 + 6, PURPLE)
    _ok_asagi(d, fx, y_cikti + 34 + 2, PURPLE)
    return d


# ---------------------------------------------------------------------------
# DIYAGRAM 3 — Algi katmani ic akisi
# ---------------------------------------------------------------------------
def algi_diyagrami():
    W, H = 468, 152
    d = Drawing(W, H)
    kw, kh = 100, 40
    ara = (W - 20 - 4 * kw) / 3.0     # 4 kutu esit araliklarla tam sigar
    y = 74
    adim = [
        ("Segment kareleri", "12 kare · 640 px", GRAY),
        ("1. AŞAMA", "serbest Türkçe betim", TEAL),
        ("2. AŞAMA", "olay çıkarımı (JSON)", TEAL),
        ("Önem kalibrasyonu", "poz · doğrulama", BLUE),
    ]
    x = 10
    kon = []
    for ad, alt, renk in adim:
        _kutu(d, x, y, kw, kh, ad, renk, colors.white, 7.6, alt, 6.2)
        kon.append((x, x + kw))
        x += kw + ara
    for i in range(len(adim) - 1):
        x1 = kon[i][1]
        _cizgi(d, x1 + 1, y + kh / 2, x1 + ara - 5, y + kh / 2)
        _ok_sag(d, x1 + ara - 1, y + kh / 2)

    _yazi(d, W / 2, H - 12, "ALGI KATMANI — neden iki aşama?", 8.6, NAVY, "middle", True)
    for i, s in enumerate([
        "Modelden DOĞRUDAN JSON istenirse şablonu doldurmaya odaklanır ve sahneye",
        "gerçekten BAKMAZ. Önce serbest anlatım istenince gerçekten inceler; sonra o",
        "zengin metinden yapılandırılmış çıktı üretmek kolaydır.",
    ]):
        _yazi(d, W / 2, 46 - i * 12, s, 7.4, colors.HexColor("#333333"), "middle")
    return d


# ---------------------------------------------------------------------------
# DIYAGRAM 4 — Sevk kapisi
# ---------------------------------------------------------------------------
def sevk_diyagrami():
    W, H = 468, 176
    d = Drawing(W, H)
    _yazi(d, W / 2, H - 12, "EYLEM KATMANI — yanlış alarmın kesildiği yer", 8.6, NAVY,
          "middle", True)
    # sol: girdi
    _kutu(d, 10, 106, 116, 36, "Tespit edilen olay", GRAY, colors.white, 7.6,
          "önem derecesiyle", 6.2)
    # orta: kapi
    _cerceve(d, 156, 96, 140, 56, RED, "#fbf1f1")
    _yazi(d, 226, 139, "SEVK KAPISI", 8.2, RED, "middle", True)
    _yazi(d, 226, 127, "yalnızca modelin KENDİ", 6.6, colors.HexColor("#333333"), "middle")
    _yazi(d, 226, 117, "kanıtlı yargısı geçer", 6.6, colors.HexColor("#333333"), "middle")
    _yazi(d, 226, 104, "politika/risk şişmesi GEÇEMEZ", 6.3, RED, "middle")
    _cizgi(d, 126, 124, 151, 124, RED)
    _ok_sag(d, 155, 124, RED)
    # sag: iki cikis
    _kutu(d, 336, 128, 122, 26, "Operasyonel fonksiyon", GREEN, colors.white, 7.2)
    _cizgi(d, 296, 141, 331, 141, GREEN)
    _ok_sag(d, 335, 141, GREEN)
    _kutu(d, 336, 94, 122, 26, "Yalnızca operatör bilgisi", GRAY, colors.white, 7.2)
    _cizgi(d, 296, 107, 331, 107, GRAY)
    _ok_sag(d, 335, 107, GRAY)
    # aciklama
    for i, (s, renk, kalin) in enumerate([
        ("NEDEN: Yanlış alarm bir güvenlik sisteminde en pahalı hatadır.",
         colors.HexColor("#333333"), False),
        ("Operatör 3 kere boşuna koştuysa 4.'ye bakmaz — alarm yorgunluğu.",
         colors.HexColor("#333333"), False),
        ("Ölçüm: dar tanımlı yanlış alarm 0/8 · sevk yanlış alarmı 0/8", GREEN, True),
        ("(n=8 küçük — tekrar koşularında 0–1 arası oynuyor; \"%0\" mutlak değil)",
         GRAY, False),
    ]):
        _yazi(d, W / 2, 68 - i * 13, s, 7.4 if i < 3 else 6.6, renk, "middle", kalin)
    return d


# ---------------------------------------------------------------------------
# Sayfa suslemesi
# ---------------------------------------------------------------------------
def _sayfa(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 12 * mm, A4[0], 12 * mm, stroke=0, fill=1)
    canvas.setFont("DVB", 8)
    canvas.setFillColor(colors.white)
    canvas.drawString(20 * mm, A4[1] - 8.2 * mm, "DilAjanları · VigilantAI")
    canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 8.2 * mm,
                           "İş Akışı ve Katmanlar")
    canvas.setFont("DV", 7.6)
    canvas.setFillColor(GRAY)
    canvas.drawCentredString(A4[0] / 2, 11 * mm, "%d" % doc.page)
    canvas.restoreState()


def _kapak(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
    canvas.setFillColor(BLUE)
    canvas.rect(0, A4[1] - 118 * mm, A4[0], 2.2 * mm, stroke=0, fill=1)
    canvas.restoreState()


# ---------------------------------------------------------------------------
def icerik():
    E = []

    # ---------------- KAPAK ----------------
    E.append(Spacer(1, 78 * mm))
    E.append(P("DilAjanları", TITLE))
    E.append(Spacer(1, 5 * mm))
    E.append(P("Yerel Video Analiz ve Karar Destek Ajanı", SUB))
    E.append(Spacer(1, 26 * mm))
    E.append(P("İŞ AKIŞI ve KATMAN MİMARİSİ", SUB))
    E.append(Spacer(1, 3 * mm))
    E.append(P("hızlı tanıtım", SUB2))
    E.append(Spacer(1, 42 * mm))
    E.append(P("Takım VigilantAI · TEKNOFEST 2026 TYDA · 3. Senaryo", SUB2))
    E.append(P("12 Ağustos 2026", SUB2))
    E.append(PageBreak())

    # ---------------- 1. BIR BAKISTA ----------------
    E.append(P("NE YAPIYOR", KICKER))
    E.append(P("Bir bakışta", H1))
    E.append(P("Güvenlik kamerası görüntüsünü <b>tamamen yerel olarak</b> analiz eder; "
               "olayı bulur, Türkçe yorumlar, risk seviyesi biçer ve operatöre aksiyon "
               "önerir. İnternet bağlantısı gerektirmez.", BIG))
    E.append(Spacer(1, 4 * mm))
    E.append(tablo([
        ["Ne", "Değer"],
        ["Model", "Qwen3-VL-8B-Instruct-FP8 (yerel, vLLM 0.23)"],
        ["Çerçeve", "LangGraph durum makinesi — 7 düğüm"],
        ["Donanım", "RTX 5090 Laptop 24 GB · WSL2 Ubuntu 24.04"],
        ["Bellek", "~21 GB VRAM"],
        ["Gecikme", "klip başına medyan ~20 sn"],
        ["Çıktı", "Türkçe — özet · olaylar · risk · aksiyonlar"],
    ], [42 * mm, 123 * mm]))
    E.append(Spacer(1, 5 * mm))
    E.append(vurgu("Tasarım ilkesi",
                   "Sistem <b>otonom alarm</b> değil, <b>karar destek</b> aracıdır. "
                   "Operatörün yerine geçmez; ona ne gördüğünü, neden önemli olduğunu ve "
                   "ne yapabileceğini söyler. Nihai karar insandadır.", BLUE))
    E.append(PageBreak())

    # ---------------- 2. KATMAN YIGINI ----------------
    E.append(P("MİMARİ", KICKER))
    E.append(P("Beş katman", H1))
    E.append(katman_yigini())
    E.append(Spacer(1, 3 * mm))
    E.append(P("Her katman bir öncekinin çıktısını alır ve zenginleştirir. "
               "<b>Ölçüm</b> katmanı hepsini dikey olarak keser: her katmanın çıktısı "
               "ayrı ayrı ölçülebilir, böylece bir iyileştirmenin nereden geldiği "
               "izlenebilir.", BODY))
    E.append(PageBreak())

    # ---------------- 3. IS AKISI ----------------
    E.append(P("İŞ AKIŞI", KICKER))
    E.append(P("Yedi düğüm", H1))
    E.append(akis_diyagrami())
    E.append(Spacer(1, 2 * mm))
    E.append(tablo([
        ["Düğüm", "Görevi"],
        ["<b>ingest</b>", "Videoyu zaman damgalı karelere böler, segmentlere ayırır. "
         "Bozuk videoda çökmez — boş segmentle devam eder."],
        ["<b>perceive</b>", "İki aşamalı algı: önce serbest Türkçe betimleme, sonra olay çıkarımı."],
        ["<b>reexamine</b>", "<b>Koşullu.</b> Model kararsızsa (\"Orta\" önem) o olaya tekrar bakar. "
         "Net olaylarda bu adım atlanır."],
        ["<b>policy_gate</b>", "Operatörün yazdığı tesis kurallarına göre hakemlik. Varsayılan kapalı."],
        ["<b>reason</b>", "Özet, risk seviyesi ve aksiyon önerileri üretir."],
        ["<b>act</b>", "Sevk kapısı — operasyonel fonksiyonları yalnızca kanıtlı sinyalde tetikler."],
        ["<b>finalize</b>", "Şartname sözleşmesine paketler: tam 4 anahtar."],
    ], [30 * mm, 135 * mm]))
    E.append(PageBreak())

    # ---------------- 4. ALGI KATMANI ----------------
    E.append(P("KATMAN 2", KICKER))
    E.append(P("Algı — mimarinin kalbi", H1))
    E.append(algi_diyagrami())
    E.append(Spacer(1, 2 * mm))
    E.append(P("Yardımcı algı: YOLO ne için var?", H2))
    E.append(P("YOLO'yu her yerde değil, <b>ölçüp kazandırdığı yerde</b> kullanıyoruz.", BODY))
    E.append(tablo([
        ["Kullanım", "Durum", "Ölçülen sonuç"],
        ["Poz ile düşme doğrulama", "<b>AÇIK</b>", "Çömelmeyi \"düşme\" sanmayı engelliyor"],
        ["Nesne listesi kanıtı", "kapalı", "Yanlış alarmı %0 → %12 <b>yükseltti</b>"],
        ["Kişi varlığı kontrolü", "kapalı", "Grenli 320×240'ta kişiyi kaçırıyor — gerçek olayı bastırma riski"],
        ["Yasak bölge · araç · kalabalık", "opsiyonel", "Deterministik geometri; operatör açar"],
    ], [46 * mm, 22 * mm, 97 * mm]))
    E.append(Spacer(1, 3 * mm))
    E.append(vurgu("Ders",
                   "YOLO <b>kesin geometrik ölçümde</b> (poz, bölge, sayım) kazandırıyor. "
                   "Ama ham nesne listesini VLM'e \"kanıt\" diye vermek yanlış alarmı "
                   "artırıyor — model listeyi aşırı yorumluyor.", TEAL))
    E.append(PageBreak())

    # ---------------- 5. EYLEM KATMANI ----------------
    E.append(P("KATMAN 4", KICKER))
    E.append(P("Eylem — güvenlik mimarisi", H1))
    E.append(sevk_diyagrami())
    E.append(Spacer(1, 2 * mm))
    E.append(P("Sistem altı mock operasyonel fonksiyona sahiptir (sağlık ekibi yönlendir, "
               "güvenlik ekibi uyar, acil durdurma tetikle, alan güvenliğini sağla, "
               "olay kaydı oluştur, yönetici bilgilendir). Bunlar <b>gerçekten çağrılır</b> "
               "ve karar izine yazılır — ama yalnızca kapıdan geçebilirse.", BODY))
    E.append(PageBreak())

    # ---------------- 6. CIKTI ----------------
    E.append(P("KATMAN 5", KICKER))
    E.append(P("Çıktı ve sunum", H1))
    E.append(P("Şartname sözleşmesi — <b>değişmez</b>", H2))
    E.append(Table([[Paragraph(
        '{ "summary": "…",  "events": [{"time": "MM:SS", "event": "…"}],<br/>'
        '&nbsp;&nbsp;"risk": "Düşük|Orta|Yüksek|Kritik",  "actions": ["…"] }', MONO)]],
        colWidths=[GENIS], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f6fb")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c8d2de")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)])))
    E.append(Spacer(1, 2 * mm))
    E.append(P("Bu dört anahtar hiçbir koşulda değişmez. Zengin alanlar (karar izi, "
               "kanıt paketi, sorgu yanıtı) ayrı bir çıktıda döner.", SMALL))
    E.append(P("Operatör konsolu", H2))
    E.append(tablo([
        ["Bileşen", "Ne sağlar"],
        ["Analiz sorgusu kutusu", "Operatör serbest metinle analizi yönlendirir "
         "(\"yangın riski var mı?\"). Sorgu <b>odaklar, filtrelemez</b>."],
        ["Karar günlüğü", "Her düğümün ne yaptığı satır satır — \"neden alarm verdin?\" sorusunun cevabı"],
        ["Olay tutanağı", "Resmî kayıt biçiminde çıktı"],
        ["Kanıt paketi", "Kutu çizili kare görüntüleri + SHA-256 manifest"],
        ["Vardiya brifingi", "Devir teslim özeti"],
    ], [40 * mm, 125 * mm]))
    E.append(PageBreak())

    # ---------------- 7. OLCUM ----------------
    E.append(P("DİKEY KATMAN", KICKER))
    E.append(P("Ölçüm — iddialarımızın dayanağı", H1))
    E.append(P("Ölçüm katmanı ürünün parçası değil, <b>iddialarımızın</b> parçası. "
               "Her performans rakamı bu araçlarla üretilir.", BODY))
    E.append(tablo([
        ["Araç", "Ne yapar"],
        ["Wilson %95 güven aralığı", "Küçük örneklemde oranın belirsizliğini dürüstçe gösterir"],
        ["Eşli McNemar (exact)", "İki kolu <b>aynı klipler</b> üzerinde karşılaştırır"],
        ["Newcombe fark aralığı", "İki oran arasındaki farkın güven aralığı"],
        ["MD5 tekilleştirme", "Aynı klibin iki kez sayılmasını önler"],
        ["Sızıntı uyarısı", "Ayar seti ile holdout kesişirse uyarır"],
        ["Bağımsız hakem", "Farklı model ailesi (Gemma-3-12B) çıktıyı puanlar"],
    ], [46 * mm, 119 * mm]))
    E.append(Spacer(1, 4 * mm))
    E.append(vurgu("Ölçüm dürüstlüğü ilkemiz",
                   "Bir metriği değiştirdiğimizde <b>eski ve yeni skoru yan yana</b> "
                   "raporlarız; eski skoru silmeyiz. Negatif sonuçları da yayımlarız. "
                   "Koşudan koşuya oynama (gürültü tabanı) ölçülür ve her iddianın yanında "
                   "belirtilir.", GREEN))
    E.append(PageBreak())

    # ---------------- 8. RAKAMLAR ----------------
    E.append(P("SONUÇ", KICKER))
    E.append(P("Ölçülen performans", H1))
    E.append(P("Anomali tespiti — bağımsız holdout seti (24 anomali + 8 normal)", H2))
    E.append(tablo([
        ["Metrik", "Gevşek eşik", "Sıkı eşik"],
        ["Recall (duyarlılık)", "<b>0,917</b>", "0,792"],
        ["Precision", "0,880", "<b>1,000</b>"],
        ["F2 (recall ağırlıklı)", "<b>0,909</b>", "0,826"],
        ["MCC", "0,567", "<b>0,698</b>"],
        ["Balanced accuracy", "0,771", "0,896"],
    ], [58 * mm, 53 * mm, 54 * mm]))
    E.append(Spacer(1, 2 * mm))
    E.append(P("<b>Neden F2 ve MCC?</b> Sınıf dengesizliği var (24/8). \"Her şeye anomali de\" "
               "diyen boş bir tahminci accuracy 0,750 alır — accuracy tek başına yanıltıcı. "
               "MCC dört hücreyi birden kullanır. F2 recall'a ağırlık verir: kaçırılan yangın, "
               "yanlış alarmdan pahalıdır.", SMALL))
    E.append(P("Senaryo seti (yangın · düşme · normal)", H2))
    E.append(tablo([
        ["Ölçüm", "Sonuç"],
        ["Anomali tespiti", "24/25 · %96  [%80–%99]"],
        ["Yangın tespiti", "<b>10/10</b> — üç bağımsız koşuda da"],
        ["Kategori adlandırma", "%92–96"],
    ], [58 * mm, 107 * mm]))
    E.append(Spacer(1, 4 * mm))
    E.append(vurgu("Dürüstlük notu — açık sorun",
                   "Grenli 320×240 sokak görüntüsünde <b>olay türü adlandırma zayıf</b>. "
                   "Sebebini teşhis ettik: modelimiz operasyonel bir taksonomi üretiyor "
                   "(Güvenlik · Kaza · Sağlık · Yetkisiz Erişim), kıyaslama seti ise suç "
                   "taksonomisi kullanıyor. Beş suç sınıfı bizim tek \"Güvenlik\" kutumuza "
                   "düşüyor. Model kendi taksonomisinde <b>%64</b> isabetli; "
                   "çapraz ölçümde %20,8 görünüyor. Bu bir <b>ölçüm hizalama</b> sorunu.",
                   AMBER))
    E.append(PageBreak())

    # ---------------- 9. DURUM ----------------
    E.append(P("NEREDEYİZ", KICKER))
    E.append(P("Olgunluk durumu", H1))
    E.append(tablo([
        ["Alan", "Durum"],
        ["Olay tespiti", "<b>Çalışıyor</b> — recall 0,92; yangın 10/10"],
        ["Türkçe özet ve aksiyon", "<b>Çalışıyor</b> — bağımsız hakemle 4,48/5"],
        ["Yanlış alarm kontrolü", "<b>Çalışıyor</b> — sevk kapısı kanıtlı sinyale bağlı"],
        ["Hata toleransı", "<b>Çalışıyor</b> — bozuk/boş/siyah videoda çökmüyor"],
        ["Olay türü adlandırma", "<b>Açık sorun</b> — ölçüm hizalaması yapılacak"],
        ["Silah tespiti", "<b>Kapsam dışı</b> — 320×240'ta silah ~16 piksel"],
        ["Gece / kızılötesi", "<b>Kapsam dışı</b> — veri yok, iddia da etmiyoruz"],
    ], [50 * mm, 115 * mm]))
    E.append(Spacer(1, 4 * mm))
    E.append(P("Test kapsamı", H2))
    E.append(P("10 test dosyası · 600'den fazla otomatik kontrol · her koşuda sıfır hata. "
               "Testler yalnızca kodun çalıştığını değil, <b>güvenlik garantilerinin</b> "
               "korunduğunu da doğruluyor: sözleşme dört anahtar kalıyor mu, kapalı özellik "
               "davranışı değiştiriyor mu, kanıt katmanı alarmı yükseltebiliyor mu.", BODY))
    E.append(Spacer(1, 4 * mm))
    E.append(P("Ayrıntılı teknik anlatım: <b>docs/DilAjanlari_Model_Anlatimi.pdf</b> (27 sayfa)",
               SMALL))
    return E


def main() -> None:
    os.makedirs(os.path.dirname(CIKTI), exist_ok=True)
    doc = SimpleDocTemplate(
        CIKTI, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=20 * mm, bottomMargin=18 * mm,
        title="DilAjanları — İş Akışı ve Katman Mimarisi",
        author="VigilantAI",
    )
    doc.build(icerik(), onFirstPage=_kapak, onLaterPages=_sayfa)
    kb = os.path.getsize(CIKTI) / 1024
    print("PDF uretildi -> %s  (%.0f KB)" % (os.path.relpath(CIKTI, KOK), kb))


if __name__ == "__main__":
    main()
