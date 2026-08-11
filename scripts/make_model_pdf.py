#!/usr/bin/env python
"""KAPSAMLI model anlatim PDF'i uretir (reportlab + DejaVu/Turkce, offline).

Amac: DilAjanlari sistemini BASTAN SONA, adim adim, duzgun Turkce ile anlatmak.
Her sayi depodan okunmustur; kaynagi (dosya:satir) metinde belirtilmistir.
Kaynagi bulunamayan yerler SAYISIZ birakilmistir.

Desen kaynagi: scripts/make_mentor_pdf.py (font kaydi, P()/B()/tablo() yardimcilari).
Cikti: docs/DilAjanlari_Model_Anlatimi.pdf
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
CIKTI = os.path.join(KOK, "docs", "DilAjanlari_Model_Anlatimi.pdf")

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
pdfmetrics.registerFont(TTFont("DV", os.path.join(FONT_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DVM", os.path.join(FONT_DIR, "DejaVuSansMono.ttf")))

NAVY = colors.HexColor("#0f2547")
BLUE = colors.HexColor("#1668b3")
GRAY = colors.HexColor("#5a6472")
LIGHT = colors.HexColor("#eef3f8")
GREEN = colors.HexColor("#1a7f45")
AMBER = colors.HexColor("#b06a00")
RED = colors.HexColor("#9d2222")

GENIS = 165 * mm  # kullanilabilir metin genisligi (A4 - 2x22mm kenar bosluk)

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="DVB", fontSize=14.5,
                    textColor=NAVY, spaceBefore=13, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="DVB", fontSize=10.8,
                    textColor=BLUE, spaceBefore=9, spaceAfter=4)
H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName="DVB", fontSize=9.6,
                    textColor=NAVY, spaceBefore=7, spaceAfter=3)
BODY = ParagraphStyle("BODY", parent=styles["BodyText"], fontName="DV", fontSize=9.4,
                      leading=13.6, textColor=colors.HexColor("#1a1a1a"), alignment=TA_LEFT,
                      spaceAfter=5)
BULLET = ParagraphStyle("BULLET", parent=BODY, leftIndent=11, bulletIndent=2, spaceAfter=3)
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=8.1, textColor=GRAY, leading=11)
MONO = ParagraphStyle("MONO", parent=BODY, fontName="DVM", fontSize=8.1, leading=11.6,
                      textColor=NAVY)
CELL = ParagraphStyle("CELL", parent=BODY, fontSize=8.4, leading=11.2, spaceAfter=0)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="DVB")
# Baslik satiri: Paragraph'in KENDI rengi TableStyle TEXTCOLOR'i ezdigi icin
# beyaz yazi ayri bir stille verilmelidir (lacivert zemin uzerinde okunakli olsun).
CELLH = ParagraphStyle("CELLH", parent=CELLB, textColor=colors.white)
TITLE = ParagraphStyle("TITLE", parent=styles["Title"], fontName="DVB", fontSize=24,
                       textColor=colors.white, alignment=TA_CENTER, leading=29)
SUB = ParagraphStyle("SUB", parent=BODY, fontSize=10.5, textColor=colors.white,
                     alignment=TA_CENTER, spaceAfter=0)
SUB2 = ParagraphStyle("SUB2", parent=BODY, fontSize=9, textColor=colors.HexColor("#c2d4ea"),
                      alignment=TA_CENTER, spaceAfter=0)


# --------------------------------------------------------------------------------------
# Yardimcilar
# --------------------------------------------------------------------------------------
def P(t, s=BODY):
    return Paragraph(t, s)


def B(t):
    return Paragraph(t, BULLET, bulletText="•")


def N(t):
    """Numarasiz, girintili alt-madde (tire isaretli)."""
    return Paragraph(t, BULLET, bulletText="–")


def tablo(satirlar, genislikler, baslik=True, etiket_sutunu=False):
    """etiket_sutunu=True: baslik satiri olmayan tablolarda ilk sutun etiket gibi
    (kalin + acik zemin) bicimlendirilir."""
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
    # repeatRows: bir tablo sayfa sinirinda bolunurse baslik satiri YENIDEN basilir.
    # (Aksi halde tasan satirlar bir sonraki sayfada BASLIKSIZ kalir ve okunamaz.)
    t = Table(data, colWidths=genislikler, hAlign="LEFT",
              repeatRows=1 if baslik else 0)
    komut = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d2de")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if baslik:
        komut += [("BACKGROUND", (0, 0), (-1, 0), NAVY),
                  ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                   [colors.white, colors.HexColor("#f4f7fb")])]
    if etiket_sutunu:
        komut += [("BACKGROUND", (0, 0), (0, -1), LIGHT)]
    t.setStyle(TableStyle(komut))
    return t


def kutu_metin(icerik_html, stil=MONO, arka="#f2f6fb", cerceve="#c8d2de"):
    k = Table([[Paragraph(icerik_html, stil)]], colWidths=[GENIS])
    k.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(arka)),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(cerceve)),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return k


def vurgu(baslik, govde, renk=AMBER):
    """Kenar cubuklu vurgu kutusu (ilke / uyari / ders)."""
    ic = [Paragraph(f"<b>{baslik}</b>", ParagraphStyle(
        "vb", parent=BODY, fontName="DVB", fontSize=9, textColor=renk, spaceAfter=2))]
    ic.append(Paragraph(govde, ParagraphStyle("vg", parent=BODY, fontSize=8.9, leading=12.6,
                                              spaceAfter=0)))
    k = Table([[ic]], colWidths=[GENIS])
    k.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbf8f2")),
        ("LINEBEFORE", (0, 0), (0, -1), 2.4, renk),
        ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#e3dccf")),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return k


# --------------------------------------------------------------------------------------
# Akis diyagrami (reportlab Drawing — kutular ve oklar)
# --------------------------------------------------------------------------------------
def _kutu(d, x, y, w, h, metin, renk=NAVY, yazi=colors.white, fs=8.2):
    d.add(Rect(x, y, w, h, fillColor=renk, strokeColor=renk, rx=3, ry=3))
    d.add(String(x + w / 2.0, y + h / 2.0 - fs * 0.36, metin, fontName="DVB", fontSize=fs,
                 fillColor=yazi, textAnchor="middle"))


def _cizgi(d, x1, y1, x2, y2, renk=GRAY, kalinlik=1.1):
    d.add(Line(x1, y1, x2, y2, strokeColor=renk, strokeWidth=kalinlik))


def _uc(d, x, y, yon="sag", renk=GRAY):
    s = 4.0
    if yon == "sag":
        pts = [x, y, x - s * 1.7, y + s, x - s * 1.7, y - s]
    else:  # asagi
        pts = [x, y, x - s, y + s * 1.7, x + s, y + s * 1.7]
    d.add(Polygon(pts, fillColor=renk, strokeColor=renk))


def _etiket(d, x, y, metin, fs=6.6, renk=GRAY, hiza="middle"):
    d.add(String(x, y, metin, fontName="DV", fontSize=fs, fillColor=renk, textAnchor=hiza))


def akis_diyagrami():
    """7 dugumlu LangGraph akisi. Kaynak: dilajan/agent/graph.py:1497-1522."""
    d = Drawing(467, 196)

    y1, y2, h = 148, 40, 26        # ust satir / alt satir taban y, kutu yuksekligi
    om1, om2 = y1 + h / 2.0, y2 + h / 2.0   # ok merkez yukseklikleri

    # --- ust satir: START -> ingest -> perceive -> (kosullu) reexamine
    d.add(Rect(8, om1 - 4.5, 9, 9, fillColor=GREEN, strokeColor=GREEN, rx=4.5, ry=4.5))
    _etiket(d, 12, y1 + h + 6, "START", 6.4, GREEN)
    _cizgi(d, 17, om1, 34, om1); _uc(d, 34, om1)

    _kutu(d, 36, y1, 80, h, "1. ingest")
    _cizgi(d, 116, om1, 142, om1); _uc(d, 142, om1)
    _kutu(d, 144, y1, 88, h, "2. perceive")
    _cizgi(d, 232, om1, 294, om1); _uc(d, 294, om1)
    _etiket(d, 263, y1 + h + 9, "Orta önemde olay VAR", 6.6, AMBER)
    _etiket(d, 263, y1 + h + 1.5, "(koşullu kenar)", 6.2, GRAY)
    _kutu(d, 296, y1, 96, h, "3. reexamine", AMBER)
    _etiket(d, 344, y1 - 9, "koşullu düğüm", 6.2, AMBER)

    # --- perceive'den policy_gate'e dogrudan kol (aksi halde)
    _cizgi(d, 188, y1, 188, 112); _cizgi(d, 188, 112, 82, 112)
    _cizgi(d, 82, 112, 82, y2 + h + 6); _uc(d, 82, y2 + h, yon="asagi")
    _etiket(d, 136, 115, "aksi hâlde", 6.6, GRAY)

    # --- reexamine'den policy_gate'e kol (tek tur; dongu yok)
    _cizgi(d, 344, y1, 344, 88); _cizgi(d, 344, 88, 50, 88)
    _cizgi(d, 50, 88, 50, y2 + h + 6); _uc(d, 50, y2 + h, yon="asagi")

    # --- alt satir: policy_gate -> reason -> act -> finalize -> END
    _kutu(d, 20, y2, 100, h, "4. policy_gate")
    _cizgi(d, 120, om2, 150, om2); _uc(d, 150, om2)
    _kutu(d, 152, y2, 78, h, "5. reason")
    _cizgi(d, 230, om2, 260, om2); _uc(d, 260, om2)
    _kutu(d, 262, y2, 68, h, "6. act")
    _cizgi(d, 330, om2, 360, om2); _uc(d, 360, om2)
    _kutu(d, 362, y2, 86, h, "7. finalize")
    _cizgi(d, 448, om2, 456, om2)
    d.add(Rect(456, om2 - 4.5, 9, 9, fillColor=NAVY, strokeColor=NAVY, rx=4.5, ry=4.5))
    _etiket(d, 460, y2 - 10, "END", 6.4, NAVY)

    _etiket(d, 233, 14,
            "Her iki kol da policy_gate'te birleşir — perceive'den doğrudan reason'a geçiş YOKTUR.",
            6.8, GRAY)
    return d


# --------------------------------------------------------------------------------------
# Kapak
# --------------------------------------------------------------------------------------
def kapak():
    kutu = Table([[Paragraph("DilAjanları", TITLE)],
                  [Paragraph("Yerel Video Analiz ve Karar Destek Ajanı", SUB)],
                  [Paragraph("Modelin Baştan Sona Anlatımı", SUB)],
                  [Paragraph("TEKNOFEST 2026 · Türkçe Yapay Zekâ Dil Ajanları · 3. Senaryo",
                             SUB2)],
                  [Paragraph("Takım VigilantAI · 11 Ağustos 2026", SUB2)]],
                 colWidths=[GENIS])
    kutu.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    return kutu


# --------------------------------------------------------------------------------------
# Icerik
# --------------------------------------------------------------------------------------
def icerik():
    E = []
    E.append(kapak())
    E.append(Spacer(1, 4 * mm))
    E.append(P(
        "<b>Tek cümleyle:</b> DilAjanları, bir güvenlik kamerası videosunu tamamen yerel "
        "çalışan bir görsel-dil modeliyle izleyen, gördüğünü Türkçe olay listesine ve risk "
        "değerlendirmesine çeviren, gerektiğinde operasyonel fonksiyonları çağıran bir "
        "karar-destek ajanıdır."))
    E.append(Spacer(1, 2 * mm))
    E.append(kutu_metin(
        "<b>Bu belge nasıl okunmalı.</b> Bölümler birbirinin üzerine kurulur: önce sistemin "
        "ne yaptığı, sonra hangi parçalardan oluştuğu, sonra her parçanın içi, en sonda "
        "ölçümler ve sınırlar. Belgedeki <b>her sayı depodan okunmuştur</b> ve yanında "
        "kaynağı yazılıdır (dosya:satır veya sonuç dosyası adı). Kaynağı gösterilemeyen "
        "hiçbir rakam bu belgeye alınmamıştır.",
        stil=BODY, arka="#eef3f8"))

    # ==================================================================================
    E.append(P("1. Bir bakışta", H1))
    E.append(P("Sisteme bir video verilir. Sistem videoyu izler ve operatöre şunları üretir:"))
    E.append(B("Videoda ne olduğunun <b>zaman damgalı olay listesi</b> (her olayda önem "
               "derecesi, kategori ve görüntüdeki konum bilgisi de vardır)."))
    E.append(B("Olayları birleştiren <b>kısa Türkçe özet</b>."))
    E.append(B("Gerekçesiyle birlikte <b>risk değerlendirmesi</b>: Düşük, Orta, Yüksek "
               "veya Kritik."))
    E.append(B("Operatörün uygulayabileceği <b>aksiyon önerileri</b>."))
    E.append(B("Yalnızca gerçek yüksek-risk sinyalinde <b>operasyonel fonksiyon çağrıları</b> "
               "(sağlık ekibi yönlendirme, güvenlik uyarısı, alanı güvenliğe alma, acil "
               "durdurma, olay kaydı, yönetici bilgilendirme)."))
    E.append(B("Sistemin o kararlara <b>neden</b> vardığını adım adım gösteren "
               "<b>karar günlüğü</b>, ayrıca resmî olay tutanağı, SHA-256 imzalı kanıt paketi "
               "ve vardiya devir-teslim brifingi."))
    E.append(Spacer(1, 2 * mm))
    E.append(P("Sistem tamamen yereldir: model kendi bilgisayarımızda çalışır, internet "
               "bağlantısı ya da dış servis kullanılmaz.", SMALL))

    # KeepTogether: bu tablo bolunurse son satirlari bir sonraki sayfada tek basina kalir.
    E.append(KeepTogether([
        P("En önemli rakamlar", H2),
        tablo([
        ["Konu", "Değer", "Kaynak"],
        ["Ajan düğümü sayısı", "7 düğüm, 1 koşullu kenar",
         "dilajan/agent/graph.py:1497-1522"],
        ["Varsayılan model", "Qwen/Qwen3-VL-8B-Instruct-FP8", "dilajan/config.py:31"],
        ["Kod büyüklüğü", "6.374 satır (22 dosya)", "wc -l, bu koşumda ölçüldü"],
        ["Test", "540 kontrol, 0 hata (7 dosya) + 27 istatistik testi",
         "bu koşumda yeniden çalıştırıldı"],
        ["Olay tespiti (senaryo seti, n=25)", "24/25 = %96 [%80–%99]",
         "query_ab_A_20260809_182957.json"],
        ["Olay tespiti (holdout seti, n=24)", "23/24 = %96 [%80–%99] · 24/24 = %100 [%86–%100]",
         "eval_20260728_193430.json · naming_ab_A_20260810_210033.json"],
        ["Normal videoda dar yanlış alarm", "0/8 · 0/12 (üst sınır sıfır değildir)",
         "aynı iki dosya"],
        ["Hız", "video saniyesi başına 0,66 sn; 4 eş-zamanlı koşuda 6,5 video/dakika",
         "full_20260728_192334/performans.log:11 ve :17"],
        ["Tepe VRAM", "22.661 MB / 24 GB (model FP8 ~19 GB)",
         "full_20260728_192334/performans.log:17 ve :19"],
        ["Koşu-arası gürültü tabanı", "tespitte 2/25 = %8 · adlandırmada 3/25 = %12",
         "query_ab A ile A′ karşılaştırması, bu koşumda hesaplandı"],
        ], [46 * mm, 62 * mm, 57 * mm]),
    ]))

    E.append(PageBreak())

    # ==================================================================================
    E.append(P("2. Sistem ne işe yarar?", H1))
    E.append(P("Çözdüğü problem", H2))
    E.append(P(
        "Bir tesiste onlarca kamera vardır, izleyecek operatör sayısı ise sınırlıdır. "
        "Kayıtların çoğu olaysızdır; olayın olduğu birkaç dakikayı bulmak saatler alır. "
        "Klasik hareket-algılayıcılar ise \"bir şey kımıldadı\" der, ne olduğunu söylemez. "
        "Operatörün ihtiyacı bir alarm değil, <b>okunabilir bir anlatım</b>dır: ne oldu, "
        "ne zaman oldu, ne kadar ciddi, şimdi ne yapmalı."))
    E.append(P(
        "DilAjanları tam bu boşluğu doldurur. Videoyu izler, gördüğünü Türkçe anlatır, "
        "önem derecesine göre sıralar ve gerekçesini gösterir. Operatör görüntüyü baştan "
        "sona izlemek yerine sistemin işaretlediği anlara bakar."))

    E.append(P("Kim kullanır?", H2))
    E.append(tablo([
        ["Kullanıcı", "Ne için kullanır"],
        ["Güvenlik operatörü (canlı vardiya)",
         "Kameradan gelen kaydı hızlıca tarayıp riskli anları öne çıkarmak; şüpheli bir ana "
         "dair sisteme soru sormak."],
        ["Vardiya amiri",
         "Vardiya sonunda devir-teslim brifingi almak; olay tutanağı ve kanıt paketi üretmek."],
        ["İş güvenliği sorumlusu",
         "Tesise özgü kuralları metin olarak tanımlayıp (\"pano kapakları kapalı tutulur\") "
         "ihlalleri işaretletmek."],
        ["İnceleme / soruşturma",
         "Geçmiş kayıtta belirli bir konuyu aramak: analiz sorgusu kutusuna serbest metin "
         "yazılır, sistem o konuya odaklanır."],
    ], [45 * mm, 120 * mm]))

    E.append(P("Tipik senaryo", H2))
    E.append(P(
        "Operatör bir depo kamerasının kaydını yükler. Sistem videoyu 10 saniyelik parçalara "
        "böler, her parçayı ayrı ayrı inceler ve şunu üretir: <i>00:12'de makinenin yanında "
        "alev ve duman görüldü; 00:24'te personel alanı terk ediyor.</i> Risk seviyesini "
        "Kritik olarak işaretler, gerekçesini yazar, güvenlik ekibi uyarısı ve olay kaydı "
        "fonksiyonlarını çağırır. Operatör karar günlüğünden sistemin bu sonuca hangi "
        "adımlarla vardığını görür ve onaylar."))
    E.append(Spacer(1, 1.5 * mm))
    E.append(vurgu(
        "Konumlandırma — dürüst ifade",
        "Sistem bugün operatörün yerine karar veren bir otonom alarm sistemi DEĞİLDİR. "
        "Ölçülen sınırlar (bölüm 14) bunu desteklemiyor. Sistem, operatöre yardımcı olan bir "
        "<b>inceleme ve triyaj aracıdır</b>. Operasyonel çağrılar öneri olarak sunulur ve "
        "operatör onayına bağlıdır.", RED))

    # ==================================================================================
    E.append(P("3. Teknik yığın ve her seçimin gerekçesi", H1))
    E.append(P(
        "Aşağıdaki sürümler kurulu sanal ortamdan (<font face=\"DVM\">importlib.metadata</font>) "
        "bu koşumda okunmuştur; tahmin değildir."))
    E.append(tablo([
        ["Katman", "Seçim", "Neden bu seçim"],
        ["Model", "Qwen/Qwen3-VL-8B-Instruct-FP8<br/><font size=7.4>config.py:31</font>",
         "Görüntüyü ve metni birlikte anlayan açık kaynak model; Türkçesi akıcı. FP8 "
         "(8 bitlik sayı biçimi) sayesinde ağırlıklar ~19 GB'a iner ve 24 GB'lık karta KV "
         "önbelleğiyle birlikte sığar."],
        ["Yedek model", "Qwen/Qwen2.5-VL-7B-Instruct<br/><font size=7.4>serve_vllm.py:8</font>",
         "Hassasiyet öncelikli alternatif. <b>Varsayılan değildir</b>; "
         "<font face=\"DVM\">DILAJAN_MODEL_NAME</font> ile seçilir."],
        ["Servisleme", "vLLM 0.23.0",
         "Modeli yerelde OpenAI uyumlu bir uç nokta olarak sunar; istekleri toplu işler "
         "(batching) ve önek önbelleği ile tekrarlanan yönerge metnini yeniden hesaplamaz."],
        ["Ajan çerçevesi", "LangGraph 1.2.6",
         "Adımları ve <b>koşullu dallanmayı</b> yönetir. Düz bir boru hattı kütüphanesi "
         "yerine graf seçilmesinin sebebi, akışın duruma göre farklı yollar izlemesidir."],
        ["Arayüz", "Gradio 6.19.0",
         "Operatör konsolu. Dış yazı tipi veya CDN kullanılmaz; tamamen çevrimdışı açılır."],
        ["Video okuma", "PyAV 17.1.0",
         "Zaman damgalı kare çıkarma. Kare çıkarma toplam sürenin yalnızca %2'sini alır "
         "(performans.log:12)."],
        ["Yardımcı algı", "Ultralytics YOLO 8.4.72 (yolo11n, yolo11n-pose)",
         "Kişi/araç sayımı ve düşme pozu doğrulaması gibi <b>kesin, sayısal</b> ölçümler. "
         "Çoğu yolu varsayılan kapalıdır — gerekçesi bölüm 7'de."],
        ["Şema ve ayar", "pydantic 2.13.4 · pydantic-settings 2.14.2",
         "Çıktı sözleşmesini tip düzeyinde zorlar; ayarlar tek merkezden "
         "(<font face=\"DVM\">DILAJAN_</font> ön ekli ortam değişkenleri) yönetilir."],
        ["Çalışma ortamı", "Python 3.12.3 · Ubuntu 24.04.4 (WSL2) · RTX 5090 Laptop, 24.463 MiB",
         "Tek dizüstü GPU üzerinde tam yerel çalışma hedefi. Sürücü 610.62; çekirdek "
         "6.6.114.1-microsoft-standard-WSL2."],
    ], [26 * mm, 50 * mm, 89 * mm]))
    E.append(Spacer(1, 2 * mm))
    E.append(P(
        "<b>Not (dürüstlük).</b> <font face=\"DVM\">ultralytics</font> paketi sanal ortamda "
        "kurulu olmasına rağmen ne <font face=\"DVM\">requirements.txt</font> ne de "
        "<font face=\"DVM\">requirements-lock.txt</font> içinde geçmektedir. Temiz bir kurulumda "
        "varsayılan açık olan poz doğrulaması çalışmazdı; hata toleransı sayesinde sistem "
        "çökmez, \"karar veremedim\" der. Bu bir bağımlılık belgeleme eksiğidir ve "
        "kapatılacaktır.", SMALL))

    E.append(P("vLLM sunucusu hangi bayraklarla açılıyor?", H2))
    E.append(P("Kaynak: <font face=\"DVM\">serve_vllm.py:25-56</font>. Sabit bayraklar her "
               "koşuda aynıdır; koşullu bayraklar ayarlardan türetilir."))
    E.append(tablo([
        ["Bayrak", "Değer", "Ne işe yarar"],
        ["--max-model-len", "8192", "Bir istekte modele verilebilecek azami belirteç (token) "
                                    "sayısı. Kare sayısı ve çözünürlük bu bütçeyle sınırlıdır."],
        ["--gpu-memory-utilization", "0.90", "Kartın %90'ı vLLM'e ayrılır; kalan pay diğer "
                                             "süreçler ve YOLO içindir."],
        ["--dtype", "bfloat16", "Hesap duyarlılığı."],
        ["--limit-mm-per-prompt", "image: 16, video: 1",
         "Bir yönergeye en çok 16 görüntü girebilir; segment başına 12 kare bu tavanın "
         "altındadır."],
        ["--enable-prefix-caching", "açık", "Yönergenin değişmeyen ön kısmı yeniden "
                                            "hesaplanmaz."],
        ["--max-num-seqs", "32", "Aynı anda işlenebilecek dizi sayısı tavanı."],
    ], [42 * mm, 30 * mm, 93 * mm]))

    E.append(PageBreak())

    # ==================================================================================
    E.append(P("4. Mimari genel bakış", H1))
    E.append(P(
        "Sistem bir <b>ajan</b>dır: video, birbirini izleyen düğümlerden geçer ve her düğüm "
        "bir sonrakine bilgi aktarır. Düğümler ve aralarındaki kenarlar LangGraph ile "
        "kurulur (<font face=\"DVM\">build_graph()</font>, graph.py:1497-1522). Toplam "
        "<b>7 düğüm</b> ve <b>1 koşullu kenar</b> vardır."))
    E.append(Spacer(1, 2 * mm))
    E.append(akis_diyagrami())
    E.append(Spacer(1, 2 * mm))
    E.append(P(
        "Diyagramdaki turuncu kutu <b>koşulludur</b>: her koşuda çalışmaz. Bu, mimarinin en "
        "belirleyici özelliğidir — akış düz bir boru hattı değildir, ajan durumuna göre farklı "
        "yol izler. Yönlendirme kararını <font face=\"DVM\">route_after_perceive</font> "
        "(graph.py:850-858) verir."))
    E.append(Spacer(1, 1 * mm))
    E.append(vurgu(
        "Kod okuma bulgusu — belgelenmesi gereken bir ayrıntı",
        "Yönlendirici fonksiyon iki değer döndürür: <font face=\"DVM\">\"reexamine\"</font> ve "
        "<font face=\"DVM\">\"reason\"</font>. Ancak eşleşme tablosunda (graph.py:1515-1516) "
        "<font face=\"DVM\">\"reason\"</font> dizesi <b>policy_gate</b>'e bağlanmıştır. Yani "
        "perceive'den doğrudan reason'a geçiş yoktur; iki kol da policy_gate'te birleşir. "
        "Fonksiyonun kendi açıklama satırı hâlâ \"doğrudan reason\" demektedir — davranış ile "
        "açıklama metni arasında bir tutarsızlık vardır, davranış yukarıdaki diyagramdaki "
        "gibidir."))

    # KeepTogether: baslik + tablo + not tek parca kalsin (aksi halde tablonun son satiri
    # tek basina sonraki sayfaya tasiyor ve sayfanin geri kalani bos goruunuyordu).
    E.append(KeepTogether([
        P("Düğümler arasında ne taşınıyor?", H2),
        P("Düğümler birbirine doğrudan çağrı yapmaz; ortak bir <b>durum</b> nesnesi üzerinden "
          "haberleşir (<font face=\"DVM\">AgentState</font>, dilajan/agent/state.py). Bir düğüm "
          "yalnızca kendi ürettiği alanları döndürür, gerisi olduğu gibi akar."),
        tablo([
        ["Kanal", "Kim yazar", "Ne taşır"],
        ["segments, video_info, scene_cuts", "ingest", "Segmentler, video süresi/çözünürlüğü, "
                                                       "sert sahne kesimleri"],
        ["events", "perceive, reexamine, policy_gate", "Olay listesi (zaman, açıklama, önem, "
                                                       "kategori, konum)"],
        ["reexamined", "reexamine", "Döngü muhafızı — ikinci tur yeniden inceleme olamaz"],
        ["policy_escalations, policy_max_intrinsic", "policy_gate",
         "Kural yükseltmeleri ve yükseltme olmasaydı oluşacak en yüksek önem"],
        ["summary, risk, actions, query_answer", "reason", "Özet, risk, aksiyonlar, sorgu yanıtı"],
        ["triggered_functions, action_log", "act", "Çağrılan fonksiyonlar ve çağrı kaydı"],
        ["trace", "yedi düğümün hepsi", "Karar günlüğü — operatörün okuduğu adım adım gerekçe"],
        ["result", "finalize", "Nihai <font face=\"DVM\">AnalysisResult</font> nesnesi"],
        ], [50 * mm, 43 * mm, 72 * mm]),
        Spacer(1, 1.5 * mm),
        P("<b>Neden bu ayrıntı önemli?</b> LangGraph, durum şemasında tanımlı olmayan anahtarları "
          "sessizce düşürür. Sorgu yanıtı özelliği eklenirken "
          "<font face=\"DVM\">query_answer</font> alanı bu yüzden şemaya gerçek bir kanal olarak "
          "eklenmiştir (state.py:32-36); aksi hâlde reason'ın ürettiği yanıt finalize'a hiç "
          "ulaşmazdı.", SMALL),
    ]))

    E.append(PageBreak())

    # ==================================================================================
    E.append(P("5. Düğüm düğüm anlatım", H1))
    E.append(P(
        "Bu bölüm sistemin kalbidir. Her düğüm için üç soruyu sırayla yanıtlıyoruz: "
        "<b>ne yapar</b>, <b>neden var</b>, <b>hata olursa ne olur</b>."))

    # ---- 5.1 ingest
    E.append(P("5.1 · ingest — görüntü alımı", H2))
    E.append(P("<b>Ne yapar.</b> Videoyu PyAV ile açar ve zaman damgalı kareler çıkarır "
               "(<font face=\"DVM\">extract_timestamped_frames</font>, video.py:92). Kareleri "
               "10 saniyelik <b>segment</b>lere böler ve sert sahne kesimlerini arar."))
    E.append(tablo([
        ["Ayar", "Varsayılan", "Anlamı"],
        ["segment_seconds", "10,0 sn", "Bir segmentin uzunluğu"],
        ["fps_sample", "2,0", "Saniyede kaç kare örneklenir"],
        ["max_frames_per_segment", "12", "Bir segmentten modele en çok kaç kare gider"],
        ["frame_max_side / frame_min_side", "768 / 640", "Karenin ölçekleneceği piksel sınırları"],
        ["scene_cut_threshold", "0,30", "Bu eşiğin üstündeki değişim \"sahne kesimi\" sayılır"],
    ], [46 * mm, 26 * mm, 93 * mm]))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "<b>Neden var.</b> Modelin bağlam bütçesi sınırlıdır: 8192 belirteç. Bütün videoyu tek "
        "seferde vermek mümkün değildir. Segmentlere bölmek üç şey kazandırır: (1) her segment "
        "bütçeye sığar, (2) segmentler <b>paralel</b> işlenebilir, (3) olayların zaman damgası "
        "segment sınırlarından türetilebilir."))
    E.append(P(
        "<b>Sahne kesimi neden aranıyor?</b> Bazı kayıtlar birbirinden bağımsız bölümlerin "
        "arka arkaya eklenmesiyle oluşur. Kesim bulunursa karar aşamasına \"bu video çok "
        "bölümlüdür, bölümler arasında neden-sonuç kurma\" uyarısı iletilir; böylece sistem "
        "alakasız iki sahneyi tek bir olay örgüsüne bağlamaz."))
    E.append(P(
        "<b>Hata olursa.</b> Video okunamazsa akış durmaz: boş segment listesiyle devam eder ve "
        "karar günlüğüne \"video okunamadı\" satırı düşer (graph.py:310-312)."))
    E.append(P(
        "<b>Bir kısayol.</b> Canlı akış yolunda kareler zaten hazırdır; bu durumda ingest "
        "videoyu yeniden çözmez, hazır kareleri doğrudan kullanır (graph.py:299-306). Buna "
        "\"bir kez çöz\" yolu diyoruz.", SMALL))

    # ---- 5.2 perceive
    E.append(P("5.2 · perceive — olay algısı (iki aşamalı)", H2))
    E.append(P(
        "<b>Ne yapar.</b> Her segmenti modele <b>iki ayrı çağrıda</b> sorar. Segmentler "
        "birbirinden bağımsız olduğu için aynı anda en çok 6 segment paralel işlenir "
        "(<font face=\"DVM\">max_parallel_segments = 6</font>)."))
    E.append(Spacer(1, 1 * mm))
    E.append(tablo([
        ["", "1. AŞAMA — serbest tarif", "2. AŞAMA — olay çıkarımı"],
        ["Girdi", "Segmentin kareleri (görüntülü çağrı)",
         "1. aşamanın ürettiği Türkçe metin (görüntüsüz çağrı)"],
        ["Yönerge", "SEGMENT_DESCRIBE_INSTRUCTION (prompts.py:49)",
         "EVENT_EXTRACTION_INSTRUCTION (prompts.py:97)"],
        ["İstenen", "Ortamı ve olağan durumu belirle, sonra gördüğünü <b>serbest Türkçe</b> "
                    "anlat", "Bu tarifi <b>yapılandırılmış olay listesine</b> çevir"],
        ["Ayarlar", "sıcaklık 0,2 · en çok 400 belirteç · tekrar cezası 1,15",
         "sıcaklık 0,1 · en çok 400 belirteç"],
    ], [20 * mm, 73 * mm, 72 * mm]))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "<b>Serbest tarife hangi katmanlar ekleniyor?</b> Yönerge sabit değildir; açık olan "
        "özelliklere göre sırayla katman eklenir (graph.py:569-590):"))
    E.append(N("<b>Tesis kuralları</b> — operatör metin girmişse (varsayılan boş)."))
    E.append(N("<b>Dedektör kanıtı</b> — YOLO nesne sayıları (varsayılan <b>kapalı</b>; "
               "gerekçesi bölüm 7)."))
    E.append(N("<b>Tehdit yorumu katmanı</b> — güvenlik analisti bakış açısı (varsayılan açık)."))
    E.append(N("<b>Hareket belirginliği ipucu</b> — karelerdeki hareketin nerede yoğunlaştığı "
               "(varsayılan açık)."))
    E.append(N("<b>Sorgu odağı bloğu</b> — operatörün serbest metin sorgusu; bilinçli olarak "
               "<b>en sona</b> eklenir (bölüm 7-e)."))
    E.append(Spacer(1, 1.5 * mm))
    E.append(vurgu(
        "Neden doğrudan JSON istemiyoruz? (bu tasarımın en önemli kararı)",
        "Kodda yazılı gerekçe (prompts.py:47-48) şudur: <i>katı JSON yönergesi, düşük "
        "çözünürlüklü gerçek görüntüde modeli aşırı temkinli yapıyor.</i> Model aynı anda hem "
        "\"ne görüyorum\" hem \"hangi alana ne yazmalıyım\" sorularıyla uğraşınca, emin olmadığı "
        "her ayrıntıyı atlıyor ve olay listesi boşalıyor. Serbest tarif modelin <b>tam algısını</b> "
        "ortaya çıkarır; yapılandırma işini ikinci, görüntüsüz ve ucuz bir çağrıya bırakırız. "
        "Ek kazanç: iki aşama arasına doğrulama katmanları sokabiliyoruz.", GREEN))

    E.append(P("2. aşamadan sonra çalışan süzgeçler", H3))
    E.append(P("Olaylar üretildikten sonra, aynı düğüm içinde sırayla şu süzgeçlerden geçer. "
               "Hepsinin ortak ilkesi aynıdır: <b>bir süzgeç olayı silmez, yalnızca önem "
               "derecesini düşürür.</b>"))
    E.append(tablo([
        ["Süzgeç", "Varsayılan", "Ne yapar"],
        ["Öz-doğrulama", "AÇIK",
         "Yüksek ve üzeri önemdeki olaylar için modele \"bunu gerçekten gördün mü\" diye "
         "sorulur. Doğrulanmayan olay <b>silinmez</b>, önemi Orta'ya <b>düşer</b> "
         "(graph.py:606-616)."],
        ["Poz doğrulama", "AÇIK",
         "Düşme iddiası varsa YOLO poz modeliyle gövde açısı ölçülür. Yalnızca kesin "
         "\"REDDET\" kararında önem Orta'ya çekilir; kararsızlıkta modelin sözü geçerlidir."],
        ["Mekânsal dayanaklandırma", "AÇIK",
         "Yüksek ve üzeri olaylara sınırlayıcı kutu (bbox) ve 3×3 ızgarada konum "
         "(\"üst sol\", \"merkez\") eklenir. Kanıt paketindeki işaretli kareler buradan gelir."],
        ["Semantik olabilirlik", "kapalı",
         "Kişi-merkezli bir olay iddia edildiği hâlde karede kişi yoksa önem düşürülür."],
        ["Yasak bölge / araç / kalabalık", "kapalı",
         "Operatör 3×3 ızgarada bölge tanımlarsa ihlal olayı üretilir; araç ve toplanma/panik "
         "tespitleri de bu grupta."],
    ], [37 * mm, 20 * mm, 108 * mm]))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "<b>Hata olursa.</b> Tek bir segment çökse bile diğerleri işlenmeye devam eder "
        "(graph.py:716-717). Düğümün tamamı hata verse bile o ana kadar toplanan olaylar "
        "korunur ve karar günlüğüne not düşülür (graph.py:840-841)."))
    E.append(P(
        "<b>Hızlı mod.</b> Gecikmenin kritik olduğu durumlarda tarif ve çıkarım tek çağrıda "
        "birleştirilebilir (<font face=\"DVM\">single_pass_perceive</font>). Bu modda doğrulama "
        "ve dayanaklandırma çalışmaz; kalite karşılığında süre kazanılır. Varsayılan kapalıdır.",
        SMALL))

    E.append(PageBreak())

    # ---- 5.3 reexamine
    E.append(P("5.3 · reexamine — koşullu yeniden inceleme", H2))
    E.append(P("<b>Ne yapar.</b> Yalnızca <b>Orta</b> önemdeki olaylara geri döner ve o olayın "
               "geçtiği segmentin karelerine <b>tekrar bakar</b>. Modele tek bir soru sorulur "
               "(graph.py:861-865) ve tek kelime yanıt istenir:"))
    E.append(kutu_metin(
        "\"Bu güvenlik kamerası karelerinde şu gözlem var: &quot;{event}&quot;. Bu GERÇEKTEN dikkate "
        "değer/anormal bir olay mı, yoksa olağan/rutin bir aktivite mi? Yalnızca TEK KELİME "
        "yanıt ver: CIDDI (gerçek ciddi olay), RUTIN (olağan, olay değil), veya BELIRSIZ.\""))
    E.append(Spacer(1, 1.5 * mm))
    E.append(tablo([
        ["Yanıt", "Sonuç"],
        ["CIDDI", "Olayın önemi <b>Yüksek</b>'e çıkarılır."],
        ["RUTIN", "Olayın önemi <b>Düşük</b>'e indirilir ve olay \"rutin\" listesine yazılır."],
        ["BELIRSIZ (veya tanımsız yanıt)",
         "Olaya <b>hiç dokunulmaz</b> — mevcut hâliyle korunur."],
    ], [55 * mm, 110 * mm]))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "<b>Neden anahtar kelimeler Türkçe işaretsiz yazılmış?</b> Yanıt "
        "<font face=\"DVM\">.upper()</font> ile büyütülüp <font face=\"DVM\">\"RUTIN\"</font> ve "
        "<font face=\"DVM\">\"CIDDI\"</font> alt dizeleri aranır (graph.py:894-905). Türkçe "
        "\"rutin\" kelimesinin büyük hâli <font face=\"DVM\">RUTİN</font> olsaydı, noktalı "
        "<b>İ</b> ile noktasız <b>I</b> farklı karakterler olduğu için eşleşme <b>tutmazdı</b>. "
        "İşaretsiz yazım burada bilinçli ve işlevseldir — 13.5'teki büyük-İ kusurunun aynısının "
        "bu yolda oluşmasını engeller.", SMALL))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "<b>Ne zaman tetiklenir.</b> Üç koşul birlikte sağlanmalıdır: özellik açık olmalı "
        "(varsayılan açıktır), bu koşuda daha önce yeniden inceleme yapılmamış olmalı ve "
        "olaylardan en az birinin önemi <b>tam olarak Orta</b> olmalıdır. Yüksek veya Düşük "
        "olaylar tetiklemez."))
    E.append(P(
        "<b>Neden var.</b> \"Orta\" sistemin <i>kararsızım</i> dediği yerdir. Bu olayları "
        "olduğu gibi bırakmak iki hataya birden yol açar: gerçek olaylar gözden kaçar, olağan "
        "hareketler gereksiz uyarı üretir. Yeniden inceleme, kararsız durumları ikinci bir "
        "görsel bakışla ayırır. Bu, ajanın <b>adaptif otonomi</b> özelliğidir: sistem işin "
        "zorluğuna göre kendi kendine daha fazla hesap harcamaya karar verir."))
    E.append(P(
        "<b>Sonsuz döngü riski nasıl kesiliyor?</b> Düğüm çalıştığında duruma "
        "<font face=\"DVM\">reexamined = True</font> yazar (graph.py:913, 916). Yönlendirici bu "
        "bayrağı gördüğü an ikinci turu reddeder. Yeniden inceleme bir koşuda en çok bir kez "
        "çalışır."))
    E.append(P(
        "<b>Hata olursa.</b> Tek bir olayın çağrısı başarısız olursa o olay değiştirilmeden "
        "korunur; düğümün tamamı hata verirse olay listesine hiç dokunulmadan devam edilir "
        "(graph.py:911-914). Yani hata hâlinde sistem hiçbir önem derecesini oynatmaz."))

    # ---- 5.4 policy_gate
    E.append(P("5.4 · policy_gate — tesis kuralı hakemliği", H2))
    E.append(P(
        "<b>Ne yapar.</b> Operatörün satır satır yazdığı tesis kurallarını olaylarla eşleştirir. "
        "Kural satırının biçimi şudur (policy.py:170):"))
    E.append(kutu_metin(
        "&lt;ihlal tanımı&gt; | &lt;uygun görünüm&gt; | Düşük|Orta|Yüksek|Kritik | sevk"))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "Eşleşme bulunursa olayın önemi, operatörün <b>beyan ettiği</b> seviyeye "
        "<b>tek yönlü</b> yükseltilir — hiçbir kural bir olayın önemini düşüremez. Video başına "
        "yalnızca <b>tek</b> ve <b>görüntüsüz</b> bir model çağrısı yapılır."))
    E.append(P(
        "<b>Neden bu sırada?</b> Kod içindeki gerekçe (graph.py:1511-1514) üç madde sayar: "
        "(1) reexamine \"Orta\" olayları aşağı çekebildiği için hakemlik ondan <b>sonra</b> "
        "çalışmalıdır, aksi hâlde yükseltme geri alınır ve zaten rutin bulunmuş bir olay "
        "sessizce yükseltilebilirdi; (2) yinelenen olaylar temizlendikten sonra aday sayısı "
        "küçüktür, tek çağrı yeter; (3) policy_gate mutasyon zincirinin sonudur."))
    E.append(P(
        "<b>Varsayılan davranış: hiçbir şey.</b> Tesis kuralı girilmemişse düğüm ilk satırında "
        "çıkar (graph.py:941-942): model çağrılmaz, karar günlüğüne satır bile eklenmez. Bu, "
        "\"varsayılan kapalı\" ilkesinin (bölüm 7-d) somut bir örneğidir."))
    E.append(P(
        "<b>Hata olursa.</b> Düğüm hata verirse olaylar <b>değiştirilmeden</b> döner "
        "(graph.py:990-992); yani sistem kural yokmuş gibi davranır."))

    # ---- 5.5 reason
    E.append(P("5.5 · reason — değerlendirme", H2))
    E.append(P(
        "<b>Ne yapar.</b> Bütün olay listesini tek seferde modele verir ve üç şey ister: "
        "özet, gerekçeli risk seviyesi, aksiyon önerileri. Çağrı görüntüsüzdür; sıcaklık 0,2 ve "
        "en çok 800 belirteçtir (graph.py:1028)."))
    E.append(P(
        "<b>Neden ayrı bir düğüm?</b> Algı ile yargı ayrılmalıdır. perceive \"ne gördüm\" der, "
        "reason \"bu ne anlama geliyor\" der. Bu ayrım sayesinde algı katmanını değiştirmeden "
        "karar politikasını değiştirebiliyoruz."))
    E.append(P("Modelin çıktısı olduğu gibi kabul edilmez; üzerine <b>koruma kuralları</b> "
               "uygulanır:", H3))
    E.append(tablo([
        ["Koruma kuralı", "Ne yapar", "Neden"],
        ["Risk tabanı", "Risk seviyesi, en yüksek olay öneminden düşük olamaz; düşükse "
                        "yükseltilir ve günlüğe yazılır.",
         "Model \"Kritik bir olay var\" deyip riski Orta yazamasın."],
        ["Politika sevk maskesi", "Risk eşiği yalnızca kural yükseltmesiyle aşıldıysa risk "
                                  "operatöre Yüksek gösterilir ama otomatik sevk sinyali "
                                  "<b>maskelenir</b>.",
         "Bu maske olmasaydı \"kural yükseltmesi sevk açmaz\" ayarı yalan olurdu; risk tabanı "
         "önemi riske taşıyıp kapıyı arka kapıdan açardı."],
        ["Teyit-sonra-aksiyon", "Her yükseltilmiş kural için tek bir aksiyon üretilir: "
                                "\"operatör teyidi sonrasi ekip sevki\".",
         "Kural kaynaklı yükseltme insan onayına bağlanır."],
        ["Algı güveni", "Görüntünün kısa kenarı 360 pikselin altındaysa \"manuel teyit "
                        "önerilir\" aksiyonu eklenir.",
         "Düşük çözünürlük ölçülmüş bir zayıflıktır (bölüm 14); sistem bunu kendisi beyan eder."],
        ["Dil saflığı", "Çıktıda Latin dışı yazı sistemi (Çince, Kiril, Arap vb.) tespit "
                        "edilirse metin düzeltilir.",
         "Çıktının tamamı Türkçe olmalıdır."],
    ], [33 * mm, 68 * mm, 64 * mm]))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "<b>Hata olursa.</b> Model çağrısı veya JSON ayrıştırması çökerse yerel varsayılanlar "
        "korunur: özet \"Özet üretilemedi.\", risk Orta / \"Belirlenemedi.\" "
        "(graph.py:1023-1024, 1046-1047). Akış durmaz."))

    E.append(PageBreak())

    # ---- 5.6 act
    E.append(P("5.6 · act — sevk kapısı", H2))
    E.append(P(
        "<b>Ne yapar.</b> Operasyonel fonksiyonların çağrılıp çağrılmayacağına karar verir. "
        "Karar tek bir mantıksal ifadedir (graph.py:1406-1411) ve <b>üç terimin</b> "
        "\"veya\"sıdır:"))
    E.append(tablo([
        ["Terim", "Koşul", "Anlamı"],
        ["1 — Modelin kendi yargısı",
         "Politika yükseltmesi <b>hiç olmasaydı</b> oluşacak en yüksek olay önemi ≥ Yüksek",
         "Sevk yalnızca modelin görüntüye dayalı kendi yargısıyla açılabilir. Operatörün "
         "beyanı bu terimi etkilemez."],
        ["2 — Yetkilendirilmiş kural",
         "Kural satırında <font face=\"DVM\">sevk</font> yetkisi verilmiş <b>ve</b> "
         "<font face=\"DVM\">policy_dispatch</font> açık <b>ve</b> olay önemi ≥ Yüksek",
         "İki ayrı onay birlikte gerekir: kural satırındaki yetki ve sistem ayarı."],
        ["3 — Risk eşiği",
         "Risk ≥ Yüksek, <b>ancak</b> geri-çağırma eğilimi kapalıysa <b>ve</b> risk yalnızca "
         "kural yükseltmesinden gelmiyorsa",
         "İki maskeleme, riskin arka kapıdan sevk açmasını engeller."],
    ], [34 * mm, 66 * mm, 65 * mm]))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "<b>Boş politikada ne olur?</b> Hiç kural yoksa ifade cebirsel olarak şuna indirgenir "
        "(graph.py:1395-1398, birim testiyle doğrulanır): <i>en yüksek olay önemi ≥ Yüksek "
        "VEYA risk ≥ Yüksek</i>. Yani varsayılan kurulumda kapı sade ve öngörülebilirdir."))
    E.append(P(
        "<b>Kapı açıksa</b> model hangi fonksiyonların çağrılacağına karar verir. Çağrılar "
        "körü körüne çalıştırılmaz: bilinmeyen fonksiyon adı en yakın gerçek ada çözülür, "
        "eksik veya sapmış argümanlar olay bağlamından onarılır (graph.py:1232, 1302). "
        "Kullanılabilir altı fonksiyon: "
        "<font face=\"DVM\">saglik_ekibi_yonlendir</font>, "
        "<font face=\"DVM\">guvenlik_ekibi_uyar</font>, "
        "<font face=\"DVM\">alan_guvenligini_sagla</font>, "
        "<font face=\"DVM\">acil_durdurma_tetikle</font>, "
        "<font face=\"DVM\">olay_kaydi_olustur</font>, "
        "<font face=\"DVM\">yonetici_bilgilendir</font> (mock_functions.py:226-233)."))
    E.append(P(
        "<b>Kapı kapalıysa</b> boş liste döner ve — eğer kural yükseltmesi olmuşsa — karar "
        "günlüğüne \"sevk yolu kapalı\" satırı, sebebiyle birlikte yazılır. Operatör neyin "
        "neden olmadığını görür."))
    E.append(P(
        "<b>Hata olursa.</b> Aksiyon seçimi çökerse o ana kadarki çağrı kaydıyla devam edilir "
        "(graph.py:1451-1452)."))

    # ---- 5.7 finalize
    E.append(P("5.7 · finalize — raporlama", H2))
    E.append(P(
        "<b>Ne yapar.</b> Bütün kanalları tek bir <font face=\"DVM\">AnalysisResult</font> "
        "nesnesinde birleştirir: özet, olaylar, risk, aksiyonlar, video süresi, tetiklenen "
        "fonksiyonlar, çağrı kaydı, karar günlüğü ve varsa sorgu yanıtı."))
    E.append(P(
        "<b>Neden ayrı bir düğüm ve neden iki kademeli koruma?</b> Kodda yazılı gerekçe "
        "(graph.py:1461-1462) nettir: <font face=\"DVM\">result</font> alanını döndürmemek, "
        "çağıran tarafı <font face=\"DVM\">KeyError</font> ile çökertirdi. Bu yüzden finalize "
        "iki kademeli güvenli varsayılana sahiptir: birinci kademede Orta riskli "
        "\"Sonuç birleştirilemedi; operatör manuel teyidi önerilir.\" sonucu üretilir; o da "
        "çökerse en küçük geçerli sonuç nesnesi döner. <b>finalize her koşulda bir sonuç "
        "döndürür.</b>"))

    E.append(P("Hata toleransının bütünü", H2))
    E.append(P(
        "Yedi düğümün <b>hepsinin</b> dış gövdesi hata yakalayıcıyla sarılıdır (graph.py:25-27). "
        "İlke şudur: <b>bir adım çökerse akış durmaz; karar günlüğüne not düşülür ve güvenli "
        "varsayılanla devam edilir.</b> Yardımcı katmanlarda da aynı desen vardır — dedektörün "
        "her fonksiyonu hata hâlinde \"olay üretme\" anlamına gelen boş sonuç döndürür."))
    E.append(vurgu(
        "Tek istisna: fail-closed bir seçenek",
        "Yalnızca <font face=\"DVM\">policy_verify_frames</font> ayarı tersine çalışır: kural "
        "yükseltmesini karşıtsal görsel teyide bağlar ve teyit alınamazsa yükseltmeyi reddeder. "
        "Yanlış-pozitif ve gecikme profili <b>ölçülmediği</b> için varsayılan kapalıdır "
        "(config.py:165-166). Ölçülmemiş bir şeyi varsayılan yapmıyoruz."))

    E.append(PageBreak())

    # ==================================================================================
    E.append(P("6. Kritik tasarım kararları", H1))
    E.append(P(
        "Bu bölümdeki her karar aynı üç başlıkla anlatılır: <b>ne yaptık</b>, <b>neden</b>, "
        "<b>ölçülen sonuç</b>. Ölçülemeyen yerlerde bunu açıkça yazıyoruz."))

    E.append(P("6.a · İki aşamalı algı", H2))
    E.append(tablo([
        ["Ne yaptık", "Segmenti modele iki kez sorduk: önce serbest Türkçe betimleme "
                      "(görüntülü), sonra o betimlemeden olay çıkarımı (görüntüsüz)."],
        ["Neden", "Kodda yazılı gerekçe: katı JSON yönergesi düşük çözünürlüklü gerçek "
                  "görüntüde modeli aşırı temkinli yapıyor ve olay listesi boşalıyor "
                  "(prompts.py:47-48). Serbest tarif modelin tam algısını ortaya çıkarır; "
                  "yapılandırmayı ayrı ve ucuz bir çağrıya bırakırız."],
        ["Ölçülen sonuç", "İki aşamalı akış üretim yapılandırmasıdır ve bütün ölçümler bu "
                          "yapılandırmayla alınmıştır. Tek-geçişli alternatif "
                          "(<font face=\"DVM\">single_pass_perceive</font>) hızlı mod için "
                          "korunmuştur; kodda kayıtlı beklentisi gecikmenin yaklaşık yarıya "
                          "inmesidir (prompts.py:130-132). İki akışın doğruluk farkı "
                          "<b>ayrı bir A/B ile ölçülmemiştir</b>."],
    ], [30 * mm, 135 * mm], baslik=False, etiket_sutunu=True))

    E.append(P("6.b · Koşullu yeniden inceleme (adaptif otonomi)", H2))
    E.append(tablo([
        ["Ne yaptık", "Yalnızca \"Orta\" önemli olay varsa çalışan bir düğüm ekledik; ajan o "
                      "segmentin karelerine ikinci kez bakıp olayı yükseltir, düşürür ya da "
                      "olduğu gibi bırakır."],
        ["Neden", "Sabit boru hattı her videoya aynı hesabı harcar. Kararsızlık yoksa ikinci "
                  "bakış israftır; kararsızlık varsa ilk bakış yetersizdir. Ajanın işin "
                  "zorluğuna göre kendi kendine karar vermesi, bu projeyi bir betikten "
                  "ajana dönüştüren özelliktir."],
        ["Ölçülen sonuç", "Mekanizma ölçüm koşularında aktiftir ve karar günlüğüne kaç olayın "
                          "yükseldiğini/düşürüldüğünü yazar. Açık/kapalı A/B'si "
                          "<b>ayrıca ölçülmemiştir</b> — bu belgede sayı verilmemektedir."],
    ], [30 * mm, 135 * mm], baslik=False, etiket_sutunu=True))

    E.append(P("6.c · Sevk kapısı — yanlış alarmı nasıl kestik", H2))
    E.append(tablo([
        ["Ne yaptık", "Operasyonel fonksiyonları riskten değil, <b>modelin kendi görsel "
                      "yargısından</b> tetikledik. Operatör beyanıyla oluşan yükseltmeler için "
                      "iki ayrı onay (kural satırındaki yetki + sistem ayarı) şartı koyduk ve "
                      "riskin arka kapıdan kapıyı açmasını maskelerle engelledik."],
        ["Neden", "Yanlış ekip çağırmak, kaçırılan bir olaydan farklı ve daha pahalı bir "
                  "hatadır: güven kaybettirir ve gerçek çağrıların ciddiye alınmamasına yol "
                  "açar. Bu yüzden tespit eşiğiyle sevk eşiğini <b>ayırdık</b>."],
        ["Ölçülen sonuç", "Normal kliplerde yanlış operasyonel tetik: holdout 0/8 "
                          "(eval_20260728_193430.json) ve senaryo 0/12 "
                          "(eval_20260728_194508.json). Adlandırma A/B'sinde A ve B kollarında "
                          "0/8, C kolunda 1/8 (naming_ab_*.json). Savunma setinde ise "
                          "kurallar kapalıyken 4/100, açıkken 8/100 "
                          "(eval_20260726_162613.json / _171601.json). "
                          "<b>Dürüst okuma:</b> 0/8 gözlemi \"%0\" demek değildir; gerçek oran "
                          "Wilson üst sınırına kadar çıkabilir."],
    ], [30 * mm, 135 * mm], baslik=False, etiket_sutunu=True))

    E.append(P("6.d · Varsayılan-kapalı ilkesi", H2))
    E.append(tablo([
        ["Ne yaptık", "Her yeni özellik <b>kapalı doğar</b>. Açılabilmesi için ölçümle kanıt "
                      "gerekir. Bugün varsayılan açık olan bayraklar yalnızca şunlardır: önek "
                      "önbelleği, algı güveni, tehdit yorumu, hareket ipucu, poz doğrulama, "
                      "olay doğrulama, mekânsal dayanaklandırma, adaptif yeniden inceleme. "
                      "Diğerlerinin hepsi kapalı ya da boştur."],
        ["Neden", "İki sebep. Birincisi bilimsel: ölçülmemiş bir özelliğin varsayılan olması, "
                  "sonraki bütün ölçümleri kirletir. İkincisi pratik: özellik kapalıyken "
                  "yönerge metinlerine <b>tek karakter</b> eklenmez, böylece eski ölçümler "
                  "bit düzeyinde yeniden üretilebilir. Sorgu özelliği eklenirken bu, 11 "
                  "yönerge metninin SHA-256 özetiyle doğrulanmıştır."],
        ["Ölçülen sonuç", "Elenen yolların çoğu (bölüm 13) tam olarak bu disiplin sayesinde "
                          "yakalandı: YOLO kanıt enjeksiyonu, CLAHE, ipucu listesi ve risk "
                          "eğilimi ölçülüp <b>geri alındı</b>, varsayılana yerleşmedi."],
    ], [30 * mm, 135 * mm], baslik=False, etiket_sutunu=True))

    E.append(P("6.e · Sorgu-güdümlü analiz: \"sorgu odaklar, filtrelemez\"", H2))
    E.append(P(
        "Operatör analiz kutusuna serbest metin yazabilir (\"forklift hareketlerine bak\"). "
        "Bu metin iki yerde kullanılır: algı aşamasında <b>odak</b> olarak, karar aşamasında "
        "<b>ek bir yanıt alanı</b> olarak. Sorgunun olay listesini filtrelediği tek bir kod "
        "satırı yoktur."))
    E.append(tablo([
        ["Ne yaptık", "Sorguyu yönergenin <b>en sonuna</b> ekledik ve iki güvence yazdık: "
                      "\"odak konusuyla ilgisiz olsa bile yangın, duman, patlama, silah, ciddi "
                      "kaza, kavga, yere düşmüş kişi gibi kritik durumları HER ZAMAN raporla\" "
                      "(prompts.py:177-181) ve \"sorgu yalnızca ek bir yanıt alanıdır, bir "
                      "filtre değildir\" (prompts.py:225-226)."],
        ["Neden en sona?", "İki gerekçe kodda yazılıdır (graph.py:583-589): (1) <b>saf ek</b> — "
                           "sorgu boşken yönerge bit düzeyinde eskisiyle aynı kalır; "
                           "(2) <b>yakınlık etkisi</b> — modelin okuduğu son talimat \"kritik "
                           "durumları her zaman raporla\" olur."],
        ["Güvenlik", "Sorgu metni bir talimat değil <b>veri</b> olarak işlenir: "
                     "&lt;, &gt;, { ve } karakterleri temizlenir, bütün boşluklar tek boşluğa "
                     "iner (çok satırlı sahte sistem mesajı kalıbı kırılır), 500 karakterde "
                     "kırpılır ve sınırlayıcılar arasına yerleştirilir. Yanıt uzunluğu 1200 "
                     "karakterle sınırlıdır. Sorgu yanıtı çıktı sözleşmesine <b>sızmaz</b>."],
        ["Ölçülen sonuç", "Gerçek modelle A/B yapıldı (bölüm 12.2). En kötü durum seçildi: "
                          "hiç forklift içermeyen bir sette \"sadece forklift hareketlerine "
                          "bak, başka hiçbir şeyle ilgilenme\" sorgusu. <b>Yangın tespiti üç "
                          "koşuda da 10/10 kaldı</b>; anomali tespiti üç koşuda da %96 kaldı."],
    ], [30 * mm, 135 * mm], baslik=False, etiket_sutunu=True))

    E.append(PageBreak())

    # ==================================================================================
    E.append(P("7. Yardımcı algı katmanı — YOLO", H1))
    E.append(P(
        "Görsel-dil modeli \"kalabalık var\" der ama kaç kişi olduğunu güvenilir saymaz. YOLO "
        "ise sayar. Bu yüzden sisteme küçük bir nesne/poz dedektörü eklenmiştir: "
        "<font face=\"DVM\">yolo11n.pt</font> (5.613.764 bayt) ve "
        "<font face=\"DVM\">yolo11n-pose.pt</font> (6.255.593 bayt), her ikisi de GPU üzerinde "
        "çalışır (detector.py:30, :84). Amaç modeli değiştirmek değil, "
        "<b>heterojen bir ikinci görüş</b> eklemektir."))
    E.append(tablo([
        ["Dedektör yolu", "Durum", "Neden bu durumda"],
        ["Poz ile düşme doğrulama<br/><font size=7.4>detector.py:88</font>",
         "<font color='#1a7f45'><b>AÇIK</b></font>",
         "Düşme, ölçülebilir bir geometridir: omuz ve kalça noktalarından gövde açısı "
         "hesaplanır. Açı 30°'nin altındaysa dik, 50°'nin üstündeyse yatay oyu verilir; arası "
         "sayılmaz. Yeterli oy yoksa \"kararsızım\" der. Yalnızca kesin <b>reddetme</b> "
         "kararında önem düşürülür — yani dedektör olay <b>silemez</b>."],
        ["Nesne listesi enjeksiyonu<br/><font size=7.4>detector.py:34</font>",
         "<font color='#9d2222'><b>KAPALI</b></font>",
         "<b>Ölçülüp geri alındı.</b> Ham nesne sayılarını (\"kişi×9, araba×6\") yönergeye "
         "eklemek en kritik metrikte gerileme yarattı: normal kliplerde yanlış-pozitif "
         "%0'dan %12'ye çıktı, kategori adlandırma %25'ten %21'e, risk kalibrasyonu %46'dan "
         "%29'a düştü (iyilestirmeler.md:73-80)."],
        ["Kişi varlığı kontrolü<br/><font size=7.4>detector.py:58</font>",
         "kapalı", "Grenli görüntüde YOLO'nun kişi tespiti güvenilmez; yanlış eleme "
                   "geri-çağırma riski yaratır. İsteğe bağlıya düşürüldü."],
        ["Yasak bölge ihlali<br/><font size=7.4>detector.py:162</font>",
         "kapalı", "Operatör 3×3 ızgarada bölge tanımlamadan anlamsızdır; tanımlanınca açılır."],
        ["Araç ihlali<br/><font size=7.4>detector.py:196</font>",
         "kapalı", "Tesise özgüdür; isteğe bağlı."],
        ["Kalabalık istatistiği<br/><font size=7.4>detector.py:243</font>",
         "kapalı", "Toplanma ve ani dağılma tespiti; isteğe bağlı (eşik: en az 5 kişi)."],
    ], [40 * mm, 18 * mm, 107 * mm]))
    E.append(Spacer(1, 2 * mm))
    E.append(vurgu(
        "Buradan çıkan ders — belgenin en öğretici bulgularından biri",
        "Dedektör sahneleri gerçekten ayırıyordu (anomali sahneleri yoğun, normal sahneler "
        "seyrek). Buna rağmen <b>ham sayıyı yönergeye enjekte etmek zarar verdi</b>: model "
        "kalabalığı tehdit sanmaya başladı. Doğru olan sinyal, yanlış olan sunum biçimiydi. "
        "Bu yüzden bugün yalnızca <b>tek bir</b> dedektör yolu açıktır ve o da ham sayı değil, "
        "geometrik bir <b>yargı</b> (düştü mü, düşmedi mi) üretir."))
    E.append(Spacer(1, 1 * mm))
    E.append(P(
        "<b>Kapsam notu.</b> Depoda deterministik bir kamera sabotaj tespiti de bulunur "
        "(donma, karartma, örtme — dilajan/tamper.py). Bu modül <b>ana ajan akışının parçası "
        "değildir</b>; yalnızca canlı akış betiğinde çağrılır (scripts/live_analyze.py:111). "
        "Bunu \"pipeline'da var\" diye sunmak yanlış olur.", SMALL))

    # ==================================================================================
    E.append(P("8. Çıktı sözleşmesi", H1))
    E.append(P(
        "Şartnamenin istediği JSON <b>tam olarak dört anahtar</b> içerir. Bu sözleşme "
        "bozulamaz ve beş ayrı test dosyasıyla doğrulanır (schema.py:93-105)."))
    E.append(kutu_metin(
        "{<br/>"
        "&nbsp;&nbsp;\"summary\": \"Depoda yangın başlangıcı gözlendi; duman hızla yayılıyor.\","
        "<br/>"
        "&nbsp;&nbsp;\"events\": [<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;{\"time\": \"00:12\", \"event\": \"Makine yanında alev ve duman\"},"
        "<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;{\"time\": \"00:24\", \"event\": \"Personel alanı terk ediyor\"}<br/>"
        "&nbsp;&nbsp;],<br/>"
        "&nbsp;&nbsp;\"risk\": \"Kritik\",<br/>"
        "&nbsp;&nbsp;\"actions\": [\"Güvenlik ekibini uyar\", \"Alanı güvenlik altına al\"]<br/>"
        "}"))
    E.append(Spacer(1, 2 * mm))
    E.append(P(
        "<b>Neden değişmez?</b> Çünkü sözleşme bir arayüz taahhüdüdür. Yeni bir özellik "
        "eklendiğinde çıktıya alan eklemek en kolay yoldur, ama bunu yapan her sistem "
        "entegrasyonu bozar. Bu yüzden zenginleştirmeler <b>ayrı</b> bir kanalda tutulur."))
    E.append(tablo([
        ["Sözleşme (4 anahtar)", "Zengin çıktıda ek olarak bulunanlar"],
        ["<font face=\"DVM\">summary</font> — metin<br/>"
         "<font face=\"DVM\">events</font> — yalnızca <font face=\"DVM\">time</font> ve "
         "<font face=\"DVM\">event</font><br/>"
         "<font face=\"DVM\">risk</font> — tek kelime<br/>"
         "<font face=\"DVM\">actions</font> — metin listesi",
         "<font face=\"DVM\">events</font> içinde ayrıca: önem, kategori, bitiş zamanı, "
         "sınırlayıcı kutu, 3×3 bölge<br/>"
         "<font face=\"DVM\">risk</font> nesnesinde gerekçe<br/>"
         "<font face=\"DVM\">actions</font> içinde öncelik ve gerekçe<br/>"
         "<font face=\"DVM\">video_duration</font>, "
         "<font face=\"DVM\">triggered_functions</font>, "
         "<font face=\"DVM\">action_log</font>, "
         "<font face=\"DVM\">decision_trace</font>, "
         "<font face=\"DVM\">query_answer</font>"],
    ], [70 * mm, 95 * mm]))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "Önem dereceleri dört kademelidir (Düşük, Orta, Yüksek, Kritik); kategoriler yedi "
        "tanedir (Normal, Güvenlik, Kaza, Sağlık, Anomali, Yetkisiz Erişim, Diğer). Bunlardan "
        "dördü \"tehlike\" alt kümesini oluşturur ve koruma kurallarında kullanılır.", SMALL))

    E.append(PageBreak())

    # ==================================================================================
    E.append(P("9. Operatör arayüzü", H1))
    E.append(P(
        "Arayüz bir tasarım taslağı değil, çalışan bir konsoldur (app.py, 778 satır). Karanlık "
        "temalı, dış yazı tipi veya CDN kullanmayan, tamamen çevrimdışı açılan bir Gradio "
        "uygulamasıdır."))
    E.append(tablo([
        ["Panel", "Ne gösterir / ne işe yarar"],
        ["Sunucu durum rozeti", "Yerel model sunucusunun ayakta olup olmadığı."],
        ["Görüntü girişi", "Video yükleme. Yüklenen dosya oynatılabilir biçime dönüştürülür."],
        ["Savunma / tesis ayarları", "Katlanır panel, kapalı başlar: tesis kuralları metni, "
                                     "3×3 ızgarada yasak bölgeler, kalabalık ve araç "
                                     "seçenekleri."],
        ["Analiz sorgusu", "Serbest metin kutusu. Yanında \"sorgu odaklar, filtrelemez\" "
                           "uyarısı yazılıdır."],
        ["Ajan durumu (canlı akış)", "Hangi düğümün çalıştığını adım adım gösteren gösterge; "
                                     "yeniden inceleme atlanırsa \"atlandı\" olarak işaretlenir."],
        ["Risk değerlendirmesi", "Renk kodlu risk rozeti ve gerekçesi."],
        ["Sorgu yanıtı kartı", "Yalnızca sorgu girildiyse görünür; sorgu boşken tamamen gizlidir."],
        ["Operasyon özeti", "Türkçe özet metni."],
        ["Olay zaman çizelgesi", "Olayların videonun neresinde olduğunu gösteren şerit."],
        ["Tespit edilen olaylar", "Tablo: Zaman · Olay · Önem · Kategori · Konum."],
        ["Aksiyon önerileri / tetiklenen fonksiyonlar", "İki ayrı liste — öneri ile fiilî çağrı "
                                                        "birbirine karıştırılmaz."],
        ["Operatör asistanı", "Analiz bağlamına dayalı, çok turlu sohbet paneli. Operatör "
                              "\"ikinci olayı açıkla\" diyebilir."],
        ["Sekme: Ajan karar günlüğü", "Sistemin adım adım neden o kararı verdiği."],
        ["Sekme: Ham JSON", "Zengin çıktının tamamı."],
        ["Sekme: Olay tutanağı ve kanıt paketi", "Resmî Türkçe tutanak (model kullanmadan, "
                                                 "deterministik üretilir) ve sınırlayıcı kutu "
                                                 "çizilmiş anahtar kareler + SHA-256'lı manifest."],
        ["Sekme: Vardiya devir-teslim brifingi", "Seçilen saat penceresindeki oturumları tek bir "
                                                 "doğal Türkçe brifinge indirger."],
    ], [50 * mm, 115 * mm]))
    E.append(Spacer(1, 2 * mm))
    E.append(P(
        "<b>Bulgu (dürüstlük).</b> Arayüzdeki adım göstergesi <b>altı</b> adım listeler; grafta "
        "ise <b>yedi</b> düğüm vardır — <font face=\"DVM\">policy_gate</font> göstergede yoktur "
        "(app.py:41-48). Bunun bilinçli bir sadeleştirme mi yoksa eksik mi olduğu kodda "
        "yazılı değildir; kapatılacak bir açıktır.", SMALL))

    E.append(P("Eş zamanlılık: iki operatör aynı anda analiz başlatırsa?", H2))
    E.append(P(
        "Bu, gerçekten yaşanmış ve çözülmüş bir hatadır. Arayüz her istekte tesis kurallarını "
        "modül düzeyindeki genel ayar nesnesine yazıyordu. İki eş zamanlı analizde A isteğinin "
        "kuralları B'nin analizine <b>sızıyordu</b>; değerler analiz bitince temizlenmediği için "
        "sonraki isteğe de taşınıyordu (config.py:236-241)."))
    E.append(P(
        "<b>Neden bağlam değişkeni (contextvar) kullanılmadı?</b> Çünkü perceive segmentleri "
        "işçi iş parçacıklarında paralel işliyor ve ayarları o iş parçacıklarında okuyor. "
        "Bağlam değişkenleri işçi iş parçacıklarına otomatik taşınmaz; operatörün kuralları "
        "<b>sessizce düşerdi</b> (config.py:242-250)."))
    E.append(P(
        "<b>Seçilen çözüm.</b> Genel değişiklik bir kapıyla korunur ve eski değerler her "
        "durumda geri yüklenir. Kapı için <font face=\"DVM\">Lock</font> değil "
        "<font face=\"DVM\">BoundedSemaphore</font> kullanılır: analiz fonksiyonu bir "
        "üreteçtir ve Gradio üretecin ardışık adımlarını <b>farklı</b> iş parçacıklarında "
        "çalıştırabilir; kilit sahiplik bağlıdır ve başka iş parçacığından bırakılırsa hata "
        "verir, semaforun sahiplik kavramı yoktur (config.py:258-262)."))

    E.append(PageBreak())

    # ==================================================================================
    E.append(P("10. Veri — hangi setler, kaç klip, nereden", H1))
    E.append(P("Aşağıdaki klip sayıları bu koşumda dosya sistemi taranarak sayılmıştır."))
    E.append(tablo([
        ["Set", "Klip", "İçerik", "Köken ve neden bu set"],
        ["eval_holdout", "32", "8 anomali kategorisi × 3 + 8 Normal",
         "UCF-Crime. <b>Ayrılmış doğrulama seti</b>: ayar/geliştirme bu sette yapılmaz. "
         "eval_tune ile kesişimi ölçüldü: 0."],
        ["eval_tune", "31", "24 anomali + 7 Normal",
         "UCF-Crime. Ayar ve geliştirme seti — holdout'a dokunmadan denemek için."],
        ["eval_scenario", "37", "Düşme 15 + Yangın 10 + Normal 12",
         "Yangın kısmı FIRESENSE (CC BY 4.0), düşme kısmı GMDCSA-24 ve URFD. "
         "<b>Senaryo odaklı</b>: şartnamenin örneklediği olay tiplerine yakın. "
         "Dizinde ayrıca <i>_deprecated_frozen_fall/</i> altında 9 klip görünür; bunlar "
         "donmuş kareden oluştuğu için karantinaya alınmıştır ve ölçüme <b>girmez</b> "
         "(alt çizgiyle başlayan klasörler eval_clips.py tarafından atlanır). Dizini "
         "elle sayan 46 dosya görür, ölçülen 37'dir."],
        ["eval_defense", "200", "100 anomali + 100 Normal, tamamı 1080p",
         "Mendeley \"Video Dataset for Safe and Unsafe Behaviours\" — Eskişehir OSB üretim "
         "tesisi, iki IP kamera. <b>Hedef alan</b>: tesise özgü kural ihlali ölçümü buradadır. "
         "Tabakalı, sabit tohumlu örnekleme."],
        ["eval_stress", "9", "Yangın renkli çetin negatifler",
         "FIRESENSE. <b>Karşıtsal set</b>: gün batımı, kırmızı ışık gibi yangına benzeyen "
         "ama yangın olmayan sahneler."],
        ["robust", "4", "siyah · bozuk · boş · çok küçük video",
         "Elle üretildi. Sistemin bozuk girdide çökmediğini göstermek için."],
        ["industrial", "691", "8 sınıf, 1080p, 24 fps",
         "eval_defense'in örneklendiği havuz. Sınıf dağılımı kaynağın kendi API'siyle "
         "birebir doğrulandı."],
    ], [26 * mm, 13 * mm, 46 * mm, 80 * mm]))
    E.append(Spacer(1, 2 * mm))
    E.append(P("Veri disiplini", H2))
    E.append(B("<b>Ayrık bölme.</b> eval_tune ile eval_holdout arasında MD5 kesişimi sıfırdır."))
    E.append(B("<b>Tekilleştirme koşu anında yapılır.</b> Aynı içerik iki dosya adıyla "
               "duruyorsa bir kez sayılır. İncelenen bütün A/B koşularında elenen klip sayısı 0."))
    E.append(B("<b>Sızıntı uyarısı otomatiktir.</b> Bilinen sızıntılı bir set kullanılırsa "
               "sonuç dosyasına uyarı alanı yazılır. İncelenen sekiz koşu dosyasının hepsinde "
               "bu alan boştur — yani sızıntılı set kullanılmamıştır."))
    E.append(B("<b>Yanlış etiketli dört klip</b> tespit edilip setlerden çıkarıldı ve ayrı bir "
               "karantina dizinine taşındı."))
    E.append(Spacer(1, 1 * mm))
    E.append(vurgu(
        "Veriyle ilgili en ciddi kusur: çözünürlük–etiket karışıklığı",
        "eval_holdout ve eval_scenario setlerinde <b>tek bir 1080p anomali klibi yoktur</b>; "
        "buna karşılık normal kliplerin önemli bir kısmı 1080p'dir. Bu durumda modelin "
        "kararının ne kadarı olayın içeriğinden, ne kadarı görüntü kalitesi ipucundan geldiği "
        "<b>ayrıştırılamaz</b>. eval_defense seti (200 klibin tamamı 1080p) tam da bu yüzden "
        "kurulmuştur.", RED))

    # ==================================================================================
    E.append(P("11. Ölçüm metodolojisi", H1))
    E.append(P(
        "Bu bölüm, sayıların nasıl üretildiğini anlatır. Projede ölçüm araçlarının kendisi de "
        "test edilmiştir — bu, ayırt edici bir noktadır."))

    E.append(P("11.1 · Neden Wilson güven aralığı?", H2))
    E.append(P(
        "Küçük örneklemde \"24/25 = %96\" ifadesi tek başına yanıltır. 25 klipte bir klibin "
        "farklı çıkması oranı %4 oynatır. Wilson güven aralığı, gözlenen orandan gerçek oranın "
        "hangi aralıkta olabileceğini verir. Örneğin 24/25 için aralık [%80–%99]'dur: yani "
        "gerçek başarı %80 kadar düşük de olabilir."))
    E.append(P(
        "<b>En önemli kullanımı sıfırlardadır.</b> \"Yanlış alarm %0\" cümlesi bu projede "
        "yasaktır. 0/9 gözleminin Wilson üst sınırı %30'dur — yani dokuz denemede hiç hata "
        "görmemek, gerçek hata oranının %30 olmasıyla uyumludur. Bu yüzden bütün oranlar "
        "\"k/n + aralık\" biçiminde yazılır."))

    E.append(P("11.2 · Neden McNemar (eşli) testi?", H2))
    E.append(P(
        "İki yapılandırmayı karşılaştırırken <b>aynı klipler</b> her iki kolda da koşulur. "
        "Bu durumda bağımsız örneklem testleri yanlıştır. McNemar testi yalnızca "
        "<b>fikir değiştiren</b> klipleri sayar: yalnız A'nın doğru bildikleri (b) ve yalnız "
        "B'nin doğru bildikleri (c). İkisinin de doğru ya da ikisinin de yanlış bildiği "
        "klipler hiçbir kanıt taşımaz."))
    E.append(P(
        "Küçük n'de yaklaşık formüller güvenilmez olduğu için <b>tam (exact) binom</b> testi "
        "kullanılır. Fark için Newcombe (1998) yöntemiyle güven aralığı, ayrıca güç analizi "
        "raporlanır — \"anlamsız çıktı\" ile \"ölçecek gücümüz yoktu\" farklı şeylerdir."))

    E.append(P("11.3 · Gürültü tabanı — neden aynı koşu iki kez aynı sonucu vermiyor?", H2))
    E.append(P(
        "Modele \"rastgelelik yok\" ayarı verilse bile (<font face=\"DVM\">temperature = 0</font>) "
        "iki koşu birebir aynı çıkmıyor. Sebep şudur: vLLM istekleri <b>toplu</b> işler. Aynı "
        "anda kaç isteğin işlendiği, kayan nokta toplamlarının sırasını değiştirir. Ortaya "
        "çıkan çok küçük sayısal farklar, iki kelimenin olasılığı birbirine yakınsa modelin "
        "farklı bir kelime seçmesine yeter. Bir kelime değişince cümle, cümle değişince olay "
        "listesi değişebilir."))
    E.append(P(
        "Bunu <b>ölçtük</b>: aynı yapılandırmayı hiçbir şeyi değiştirmeden ikinci kez koşturduk "
        "(A ve A′). Bu koşumda ham satırlardan yeniden hesapladığım sonuç:"))
    E.append(tablo([
        ["Karşılaştırma", "Tespitte uyuşmazlık", "Adlandırmada uyuşmazlık"],
        ["A ile A′ (aynı yapılandırma, iki koşu)", "<b>2/25 = %8</b>", "<b>3/25 = %12</b>"],
        ["A ile B (farklı sorgu)", "2/25 = %8 — <b>aynı klipler</b>", "3/25 = %12 — aynı klipler"],
        ["A′ ile B", "0/25", "0/25"],
    ], [66 * mm, 50 * mm, 49 * mm]))
    E.append(Spacer(1, 1.5 * mm))
    E.append(vurgu(
        "Bu tablonun anlamı",
        "Yukarıdaki <b>iki metrikte</b> (tespit ve adlandırma) A ile B arasındaki bütün fark, "
        "A ile A′ arasında da vardır — üstelik birebir aynı kliplerde. Yani bu iki metrikte "
        "sorguya <b>atfedilebilecek ek uyuşmazlık sıfır kliptir</b>. (Risk kalibrasyonu için "
        "aynı şey söylenemez; oradaki bir kliplik artık fark 12.2'de açıkça yazılmıştır.) "
        "Daha genel sonuç: n≈25'lik bir "
        "sette yapılan hiçbir A/B, tespitte %8'ten, adlandırmada %12'den küçük bir etkiyi "
        "gürültüden ayıramaz. Bu belgede raporlanan küçük farklar bu ölçekle okunmalıdır. "
        "(Not: adlandırma için %12'lik taban bu koşumda hesaplanmıştır; bazı depo belgeleri "
        "her iki metrik için de %8 kullanmaktadır — düzeltilmesi gereken bir noktadır.)"))

    E.append(P("11.4 · Ölçüm dürüstlüğü ilkelerimiz", H2))
    E.append(B("Her oran <b>k/n biçiminde ve güven aralığıyla</b> yazılır; çıplak yüzde yasaktır."))
    E.append(B("\"%0\" mutlak ifadesi kullanılmaz."))
    E.append(B("n küçükken (≤48) sıralama veya \"şu yöntem daha iyi\" karşılaştırması yapılmaz."))
    E.append(B("<b>Dayanaklı</b> metrikler (klibin bilinen etiketine karşı ölçülen) ile "
               "<b>iç tutarlılık</b> metrikleri (sistemin kendi çıktısına karşı ölçülen) asla "
               "tek skorda birleştirilmez."))
    E.append(B("Eski ölçüm kuralı <b>kasten bozuk bırakılmıştır</b> ve düzeltilmeyecektir — "
               "eski sonuçların yeniden üretilebilmesi için. Yeni ve eski kural, sonuç "
               "dosyasına <b>yan yana</b> yazılır."))

    E.append(PageBreak())

    # ==================================================================================
    E.append(P("12. Ölçülen performans", H1))
    E.append(P(
        "Aşağıdaki bütün tablolar ham sonuç dosyalarından okunmuştur; dosya adları "
        "belirtilmiştir. Köşeli parantez içindekiler %95 Wilson güven aralığıdır."))

    E.append(P("12.1 · İki set, tam koşu (28 Temmuz 2026)", H2))
    E.append(tablo([
        ["Ölçüm", "eval_holdout (grenli, n=24/8)", "eval_scenario (senaryo, n=25/12)"],
        ["Olay tespiti", "<b>23/24 = %96</b> [%80–%99]", "<b>24/25 = %96</b> [%80–%99]"],
        ["Kategori adlandırma", "9/24 = %38 [%21–%57]", "<b>24/25 = %96</b>"],
        ["Risk kalibrasyonu", "20/24 = %83", "22/25 = %88"],
        ["Normal — dar yanlış alarm", "0/8", "0/12"],
        ["Normal — yanlış ekip çağırma", "0/8", "0/12"],
        ["Normal — <i>operasyonel</i> yanlış alarm", "5/8 = %62", "4/12 = %33"],
        ["Gecikme (medyan)", "19,35 sn", "17,1 sn"],
    ], [56 * mm, 55 * mm, 54 * mm]))
    E.append(P("Kaynak: eval_20260728_193430.json · eval_20260728_194508.json", SMALL))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "<b>Üç ayrı yanlış alarm tanımı vardır ve karıştırılmamalıdır:</b> <i>dar</i> tanım "
        "\"normal klipte önem veya risk Yüksek'e çıktı mı\", <i>sevk</i> tanımı \"boşuna ekip "
        "çağrıldı mı\", <i>operasyonel</i> tanım ise \"herhangi bir olay üretildi mi\". "
        "Üçüncüsü kodda açıkça \"dürüst metrik\" olarak etiketlenmiştir ve en zayıf rakamdır. "
        "Bu belgede bilerek gösterilmektedir.", SMALL))

    E.append(P("12.2 · Sorgu A/B — \"sorgu filtreler mi?\" (eval_scenario)", H2))
    E.append(P("A: sorgu yok · B: \"Sadece forklift hareketlerine bak…\" (sette hiç forklift "
               "yoktur) · A′: A'nın birebir tekrarı."))
    E.append(tablo([
        ["Ölçüm", "A", "A′", "B"],
        ["Anomali tespiti (n=25)", "24/25 = %96", "24/25 = %96", "24/25 = %96"],
        ["<b>Yangın tespiti (n=10)</b>", "<b>10/10</b>", "<b>10/10</b>", "<b>10/10</b>"],
        ["Yangın kategori adlandırma", "10/10", "10/10", "10/10"],
        ["Düşme tespiti (n=15)", "14/15", "14/15", "14/15"],
        ["Kategori adlandırma", "23/25 = %92", "24/25 = %96", "24/25 = %96"],
        ["Risk kalibrasyonu", "22/25 = %88", "22/25 = %88", "24/25 = %96"],
        ["Gecikme (medyan)", "16,9 sn", "17,3 sn", "16,6 sn"],
    ], [56 * mm, 36 * mm, 36 * mm, 37 * mm]))
    E.append(P("Kaynak: query_ab_A_20260809_182957.json · query_ab_A_20260809_185259.json · "
               "query_ab_B_20260809_184045.json", SMALL))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "<b>Eşli test (A'ya karşı B):</b> tespit farkı +%0, aralık [−%16, +%16], p = 1,0000. "
        "Yani sistemin en dar sorgu altında bile yangını kaçırmadığı ölçülmüştür. Risk "
        "kalibrasyonunda B lehine +%8 (22/25 → 24/25) görünüyor; bu fark <b>b = 0, c = 2</b> "
        "ile p = 0,50'dir, yani anlamsızdır. Dahası, hiçbir şey değiştirilmeden yapılan "
        "A~A′ tekrarı <b>aynı metrikte de 2 klip oynamaktadır</b> (Subject3_fall01, "
        "Subject3_fall02). İki kliplik bir fark bu sette koşu-arası gürültüden ayrılamaz."))
    E.append(P(
        "<b>Dürüstlük notu.</b> Tespit ve adlandırmada A~B farkının <i>tamamı</i> A~A′ "
        "tekrarında da görülür (birebir aynı klipler). Risk kalibrasyonunda ise durum bu kadar "
        "temiz değildir: A~B'de ayrışan iki klipten biri (urfd_fall03) A~A′'de ayrışmaz. Yani "
        "bu metrikte sorguya atfedilebilecek uyuşmazlık sıfır değil, <b>bir kliptir</b> — "
        "istatistiksel olarak anlamsız, ama \"sıfır\" demek yanlış olurdu.", SMALL))
    E.append(vurgu(
        "Bu ölçümün en öğretici anı: yanıltıcı kanıt",
        "B kolunda bir düşme klibinin özeti <i>\"forklift hareketi gözlemlenmedi, olay yok\"</i> "
        "diyordu — sorgunun olayı bastırdığına dair mükemmel bir kanıt gibi görünüyordu. "
        "Ancak <b>A′ kolu, hiç sorgu almadan aynı klibi kaçırdı</b>. Yani gözlenen şey sorgunun "
        "etkisi değil, sonradan gerekçelendirmeydi. <b>Ders: tekrar koşusu olmadan anlatısal "
        "kanıt yanıltır.</b>", GREEN))

    E.append(P("12.3 · Kural ihlali ölçümü — hedef alan (eval_defense, n=200)", H2))
    E.append(P("Bu, projenin istatistiksel olarak <b>anlamlı</b> tek büyük sonucudur."))
    E.append(tablo([
        ["Ölçüm", "Kural KAPALI", "Kural AÇIK", "Fark ve p değeri"],
        ["Olay tespiti", "20/100", "<b>47/100</b>",
         "<b>+%27</b> [+%15, +%38] · p = 4,19e-05 <b>anlamlı</b>"],
        ["Kategori adlandırma", "9/100", "<b>33/100</b>",
         "<b>+%24</b> [+%14, +%34] · p = 8,43e-06 <b>anlamlı</b>"],
        ["Risk kalibrasyonu", "5/100", "10/100", "+%5 · p = 0,267 anlamsız"],
        ["Normal — dar yanlış alarm", "4/100", "8/100", "p = 0,125"],
        ["Normal — operasyonel yanlış alarm", "17/100", "35/100",
         "<b>p = 0,0014 — anlamlı KÖTÜLEŞME</b>"],
        ["Gecikme (medyan)", "11,7 sn", "14,15 sn", "+2,45 sn maliyet"],
    ], [45 * mm, 27 * mm, 27 * mm, 66 * mm]))
    E.append(P("Kaynak: eval_20260726_162613.json · eval_20260726_171601.json", SMALL))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "<b>Dürüst okuma.</b> Tesise özgü kural bilgisi vermek, görüntüden anlaşılamayan "
        "ihlalleri gerçekten görünür kılıyor — bu kazanç büyük ve istatistiksel olarak "
        "sağlamdır. Ama <b>bedeli vardır</b>: kural açıkken sistem normal kliplerde de daha "
        "çok \"olay\" üretiyor ve operasyonel yanlış alarm anlamlı biçimde artıyor. Ayrıca "
        "%47 bir tavandır: kural verilse bile ihlallerin yarısı kaçırılıyor."))

    E.append(P("12.4 · Hız, kaynak ve dayanıklılık", H2))
    E.append(tablo([
        ["Ölçüm", "Sonuç"],
        ["Video saniyesi başına işlem", "<b>0,66 sn</b> (aralık 0,37–2,91)"],
        ["Zamanın nereye gittiği", "%98 model çıkarımı · %2 video çözme (toplam 3,4 sn)"],
        ["Sıralı koşu (4 video)", "82,2 sn — video başına 20,5 sn"],
        ["Eş zamanlı ×2", "46,7 sn — 5,1 video/dakika · <b>1,76 kat</b> hızlanma"],
        ["Eş zamanlı ×4", "36,8 sn — <b>6,5 video/dakika</b> · <b>2,23 kat</b> hızlanma"],
        ["Tepe VRAM", "22.661 MB / 24 GB (model FP8 ~19 GB)"],
        ["GPU sıcaklığı (uzun koşu)", "ortalama 69,8 °C · en yüksek 86 °C · 80 °C üstü 15 örnek"],
    ], [62 * mm, 103 * mm]))
    E.append(P("Kaynak: full_20260728_192334/performans.log:5-19 (klip bazlı aralık :5-10, "
               "ortalama :11, eş-zamanlılık :15-17, VRAM :19) · benchmark/results/"
               "gpu_telemetri_C.csv (209 örnek, 21:47:13–22:04:42 = 17,5 dakika — bu koşumda "
               "yeniden hesaplandı)", SMALL))

    E.append(P("12.5 · Bağımsız kalite hakemliği", H2))
    E.append(P(
        "Çıktı kalitesi, sistemi çalıştıran modelden <b>farklı</b> bir modelle puanlanmıştır "
        "(Gemma-3-12B). Böylece sistemin kendi kendini puanlaması önlenir. Puanlar iki aileye "
        "ayrılır ve <b>birleştirilmez</b>."))
    E.append(tablo([
        ["DAYANAKLI — klibin bilinen etiketine karşı", "Sonuç"],
        ["Olgusal dayanaklılık (1–5)", "<b>4,38 ± 1,14</b> (n=37 klip)"],
        ["Etiketle çelişki", "3/37 = %8,1 [%2,8–%21,3]"],
        ["<b>Uydurma ayrıntı</b>", "<b>10/37 = %27,0</b> [%15,4–%43,0]"],
        ["Kategori bazında dayanaklılık", "Yangın 4,70 ± 0,67 · Düşme 4,40 ± 1,12 · "
                                          "Normal 4,08 ± 1,44"],
    ], [78 * mm, 87 * mm]))
    E.append(Spacer(1, 1.5 * mm))
    E.append(tablo([
        ["İÇ TUTARLILIK — sistemin kendi olay listesine karşı", "Sonuç"],
        ["Özet kalitesi (1–5)", "4,48 ± 0,63 (37 klip × 3 eksen)"],
        ["Aksiyon kalitesi (1–5)", "4,59 ± 0,58 (28 klip × 4 eksen)"],
        ["Risk gerekçesi kalitesi (1–5)", "4,86 ± 0,47 (28 klip × 3 eksen)"],
        ["JSON şema uyumu (holistik karne, 9 klip)", "<b>%100</b>"],
    ], [78 * mm, 87 * mm]))
    E.append(Spacer(1, 1.5 * mm))
    E.append(vurgu(
        "Bu skorların en kritik sınırı",
        "Hakem model <b>videoyu görmüyor</b> (sonuç dosyasında "
        "<font face=\"DVM\">gorsel_dayanak = False</font> olarak kayıtlıdır). İç tutarlılık "
        "puanları sistemin videoyu doğru anladığını <b>kanıtlamaz</b>; yalnızca kendi çıktısıyla "
        "çelişmediğini gösterir. Kendinden emin bir halüsinasyon bu ölçekte tam puan alabilir. "
        "Dış geçerlilik için yalnızca DAYANAKLI bloğuna bakılmalıdır — ve orada en önemli "
        "rakam <b>%27 uydurma ayrıntıdır</b>.", RED))

    E.append(P("12.6 · Testler", H2))
    E.append(P("Bu koşumda bütün test dosyaları yeniden çalıştırılmıştır (GPU gerekmez):"))
    E.append(tablo([
        ["Test dosyası", "Kontrol", "Kapsam"],
        ["tests/test_query_driven.py", "183", "Sorgu-güdümlü analiz, enjeksiyon direnci, "
                                              "sözleşme izolasyonu"],
        ["tests/test_kusur2_severity.py", "94", "Kural hakemliği ve önem yükseltme mekanizması"],
        ["tests/test_rescore.py", "91", "Yeniden skorlama aracı ve eşleştirici"],
        ["tests/test_mock_mode.py", "56", "GPU'suz demo modu"],
        ["tests/test_capraz_dogrulama.py", "44", "Belgeler arası çapraz doğrulama"],
        ["tests/test_agent_k2_k4_k5.py", "40", "Ajan davranışı"],
        ["tests/test_agent_k1_k3_k6.py", "32", "Kayıt izolasyonu, sözleşme, hata toleransı"],
        ["<b>Toplam</b>", "<b>540</b>", "<b>0 hata</b> — ayrıca ölçüm araçlarının kendi "
                                        "27 birim testi de geçti"],
    ], [56 * mm, 20 * mm, 89 * mm]))

    E.append(PageBreak())

    # ==================================================================================
    E.append(P("13. Denediğimiz ve elediğimiz yollar", H1))
    E.append(P(
        "Bu bölüm bilerek uzun tutulmuştur. Bir yöntemin işe <b>yaramadığını</b> ölçmek, "
        "işe yaradığını ölçmek kadar değerlidir; ve bir projenin bilimsel dürüstlüğü en iyi "
        "burada görülür. Her madde: ne denendi, ne çıktı, neden vazgeçildi."))

    E.append(P("13.1 · Daha büyük / farklı model", H2))
    E.append(tablo([
        ["Denenen", "Sonuç ve karar"],
        ["Qwen2.5-VL-32B-AWQ",
         "<b>Hiç çalışmadı.</b> Ağırlıklar 24 GB'a sığdı ama KV önbelleğine yer kalmadı. "
         "Donanım sınırı."],
        ["InternVL3.5-14B-AWQ",
         "Sığdı ama <b>daha kötü ve daha yavaş</b>: Türkçesi kirli, normal kliplerde yanlış "
         "alarm %12, video saniyesi başına ~3,05 sn (Qwen ~1,4 sn). Elendi."],
        ["Sınır modeller taraması (2026)",
         "InternVL3.5, MiniCPM-V4.5, GLM-4.6V, Ovis2.5, Keye-VL, VideoLLaMA3 <b>literatürden "
         "incelendi</b>; hiçbiri bu donanımda koşturulmadı. O günkü gerekçemiz \"darboğaz "
         "model kapasitesi değil, 320×240 karede bulunmayan bilgidir\" idi. <b>Bu gerekçe "
         "bugün kısmen geri çekilmiştir</b> — bkz. 13.5. Karar (model yükseltmesi yapmamak) "
         "korunmuştur, ama dayanağı artık ölçülmüş bir sonuç değil, <b>ölçülmemiş bir "
         "beklentidir</b>."],
    ], [42 * mm, 123 * mm]))
    E.append(Spacer(1, 1.5 * mm))
    E.append(vurgu(
        "Neden bu satırın dayanağı zayıfladı",
        "\"Darboğaz tamamen görseldir\" iddiasının birincil kanıtı, taksonomi kelimelerini "
        "modele vermenin adlandırmayı hiç değiştirmediği gözlemiydi. 13.5'te gösterildiği gibi "
        "<b>o ölçüm hatalıydı</b>: doğru skorlamayla model taksonomiyi kullandı (12/24'e karşı "
        "14/24). Dolayısıyla bugün ne \"darboğaz tamamen görseldir\" ne de \"sözcükseldir\" "
        "denebilir; n=24'te <b>ayrıştırılamıyor</b>. Yalnızca Silahlı olay için görsel sınır "
        "iddiası ayakta kalır (14.1) — çünkü orada taksonomi <b>verildiği hâlde</b> üç kolun "
        "ve dört skorlama kuralının hepsinde 0/3 alınmıştır.", RED))

    E.append(P("13.2 · Görüntü ön işleme", H2))
    E.append(tablo([
        ["Denenen", "Sonuç ve karar"],
        ["CLAHE kontrast iyileştirme",
         "Tespit %96'da <b>aynı</b>, kategori %25'te <b>aynı</b>; risk kalibrasyonu düştü, "
         "gecikme arttı. <b>Ders: düşük çözünürlük tavanı kontrastla aşılmıyor.</b> "
         "Varsayılan kapalı."],
        ["Çözünürlük ve kare sayısı artırma (768→1280, 16 kare)",
         "Bağlam bütçesini aşıp <b>hata verdi</b>. Aynı belge ailesinde bu maddeye \"+0,69 "
         "puan\" atfeden bir tablo da vardır; o rakamın <b>birincil ölçüm kaydı depoda "
         "bulunamamıştır</b> ve bu belgede kullanılmamaktadır."],
        ["Süper-çözünürlük",
         "Bir özet tabloda \"kanıtla elenmiş\" diye geçmektedir, ancak depoda <b>hiçbir betik, "
         "koşu dosyası veya ölçüm satırı yoktur</b>. Bu belgede <b>doğrulanamamış</b> olarak "
         "işaretlenmektedir; savunulabilir bir bulgu değildir."],
    ], [42 * mm, 123 * mm]))

    E.append(P("13.3 · Yönerge (prompt) düzeyinde denemeler", H2))
    E.append(tablo([
        ["Denenen", "Sonuç ve karar"],
        ["Aksiyon-ipucu kontrol listesi + taksonomi tanımları",
         "<b>Net gerileme:</b> tespit %96→%92, risk kalibrasyonu %46→%33, kategori "
         "%25→%12. Sistem \"aşırı temkinli\" oldu. Temel yapılandırmaya geri alındı."],
        ["Zamansal akıl yürütme zinciri (başlangıç→gelişim→sonuç)",
         "Yukarıdakiyle birlikte risk kalibrasyonunu %46'dan %33'e düşürdü. Geri alındı."],
        ["Yönergeye doğrudan önem talimatı yazmak "
         "(\"bu ihlaller en az YÜKSEK olmalıdır\")",
         "Risk kalibrasyonu 5/100→10/100, <b>p = 0,267 anlamsız</b>. Sonuç: risk yükseltme "
         "yönerge katmanında çözülemiyor."],
    ], [50 * mm, 115 * mm]))

    E.append(P("13.4 · En büyük negatif sonuç: politika hakemliği", H2))
    E.append(P(
        "<b>Ne denendi.</b> Operatör satır başına kural beyan ediyor; sistem video başına tek "
        "bir anlamsal sınıflandırma çağrısıyla olayları kurallarla eşleştiriyor ve eşleşirse "
        "önemi kuralın beyan ettiği seviyeye yükseltiyor. Dört ayrı kapı kurulmuştu: kapsam, "
        "kanıt alıntısı doğrulama, çekince filtresi, bütçe."))
    E.append(P(
        "<b>Ne çıktı.</b> n=200 eşli ölçümde risk kalibrasyonu 10/100'den 14/100'e çıktı, "
        "<b>p = 0,48</b>. Kabul kapısı (≥20/100 ve p&lt;0,05) <b>geçilemedi</b>."))
    E.append(P(
        "<b>Kök neden ölçüldü, tahmin edilmedi.</b> Mekanizma mekanik olarak doğru çalıştı — "
        "91 klipte devreye girdi. Ama <b>yedi yükseltmenin yedisi de aynı kurala</b> eşleşti; "
        "diğer üç kurala sıfır. En çarpıcı örnek: \"forklift aşırı yük taşıyor\" olayı, tam "
        "karşılığı olan aşırı yük kuralıyla <b>hiç eşleşmedi</b>. Ayrıca yedi yükseltmenin "
        "üçü normal kliplerdeydi."))
    E.append(vurgu(
        "Buradan çıkan ders",
        "8B'lik bir model <b>açık uçlu kural eşleştirme</b> görevini yapamıyor. Kurduğumuz "
        "kapılar <b>uydurma kanıtı</b> eliyor, ama \"yanlış ama sadık alıntılı\" yargıyı "
        "elemiyor — model gerçekten gördüğü bir şeyi alıntılıyor, sadece yanlış kurala "
        "bağlıyor. Hata mekanizmada değil <b>modelin yargısında</b> olduğu için kod ve onun "
        "94 kontrollük testi <b>korunmuştur</b>; mekanizma varsayılan kapalıdır."))
    E.append(P(
        "<b>İkinci ve daha rahatsız edici bulgu:</b> mekanizmanın hiç dokunmadığı metrikler de "
        "oynadı — tespitte 14 klip düştü, 17 klip yükseldi. Bu, koşular arasında ±15 kliplik "
        "bir salınım olduğu anlamına gelir ve determinizm sorunu çözülmeden bu mekanizmanın "
        "<b>herhangi bir</b> düzeltmesinin doğrulanamayacağını gösterir.", SMALL))

    E.append(PageBreak())

    E.append(P("13.5 · Ölçüm zincirinin kendisindeki kusur ve onarımı", H2))
    E.append(P(
        "Bu, projenin en öğretici bölümüdür: <b>ölçüm aracının kendisi hatalıydı.</b> Kategori "
        "adlandırma metriği yalnızca olay listesindeki kısa açıklamayı tarıyordu; oysa "
        "<b>özet</b> alanı hem çıktı sözleşmesinin parçası hem de operatörün ekranda okuduğu "
        "asıl metindir. Eşleştirici ayrıca çok gevşekti — gerçek örnekler:"))
    E.append(tablo([
        ["Metin", "Yanlış eşleşme", "Neden yanlış"],
        ["\"<b>kır</b>mızı sıvı dökülmüş\"", "Vandalizm", "\"kır\" kökü çıplak alt dize olarak "
                                                          "arandığı için"],
        ["\"<b>vur</b>gulanmadı\"", "Saldırı", "aynı kusur"],
        ["\"kaza belirtisi <b>YOK</b>\"", "Trafik kazası", "olumsuzlama görmezden gelindiği için"],
        ["\"İstismar\" küçük harfe çevrilince", "hiçbiri", "Türkçe büyük İ, birleştirici "
                                                           "noktayla küçülüyor ve eşleşmiyor"],
    ], [50 * mm, 32 * mm, 83 * mm]))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "<b>Onarım nasıl yapıldı.</b> Dört skorlama kuralı tanımlandı ve arşivdeki sonuçlar "
        "modeli hiç çalıştırmadan yeniden skorlandı. Aşağıdaki tabloyu bu koşumda "
        "<font face=\"DVM\">benchmark/rescore.py</font> ile <b>birebir yeniden ürettim</b>:"))
    E.append(tablo([
        ["Skorlama kuralı", "A", "B", "C", "Özgüllük A / B / C"],
        ["1 — ESKİ (yalnız olay alanı, çıplak alt dize)",
         "9/24 %37,5", "10/24 %41,7", "8/24 %33,3", "2,67 / 1,92 / 2,25"],
        ["2 — + özet alanı, aynı gevşek eşleştirici",
         "12/24 %50,0", "12/24 %50,0", "14/24 %58,3", "3,12 / 2,58 / 3,33"],
        ["<b>3 — + özet + sıkılaştırılmış eşleştirici</b>",
         "<b>11/24 %45,8</b>", "11/24 %45,8", "12/24 %50,0", "<b>2,04 / 1,62 / 2,12</b>"],
        ["4 — kural 3 + semantik gruplama",
         "14/24 %58,3", "11/24 %45,8", "12/24 %50,0", "1,29 / 1,08 / 1,29"],
    ], [56 * mm, 24 * mm, 24 * mm, 24 * mm, 37 * mm]))
    E.append(P("Özgüllük = klip başına tetiklenen <b>yanlış</b> kategori sayısı (düşük iyidir). "
               "Hat doğrulaması: kural 1, üç dosyada da kayıtlı eski değeri 24/24 birebir "
               "yeniden üretti.", SMALL))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "<b>Kural 2'den 3'e düşüş bir gerileme değil, bir itiraftır.</b> Özet alanını eklemenin "
        "getirdiği kazancın bir kısmı şans eseri alt dize tutturmasıydı. Sıkılaştırma o sahte "
        "kazancı geri aldı ve özgüllüğü belirgin biçimde iyileştirdi (2,67→2,04). Sonuç: "
        "onarım, ölçüm tabanını <b>%38'den %46'ya</b> taşıdı. Bu bir iyileştirme değil, bir "
        "<b>düzeltmedir</b> — model hiç değişmedi."))
    E.append(vurgu(
        "Geri çekilen iddia — nasıl yanıldığımızın kaydı",
        "Önceki bir ölçüm şunu iddia etmişti: <i>\"taksonomi kelimesi geçen klip sayısı iki "
        "kolda birebir aynı, demek ki model cevap anahtarını kullanmadı; darboğaz sözcüksel "
        "değil görsel.\"</i> Bu kontrol <b>varlık</b> sayıyordu (herhangi bir taksonomi kelimesi "
        "geçti mi), oysa ölçülmesi gereken <b>doğruluk</b>tu. Doğru ölçümle: 12/24'e karşı "
        "14/24 — <b>model taksonomiyi kullandı</b>. Kazanç özet alanında kaldı, olay listesine "
        "giremedi. Yanlış iddia silinmedi; \"nasıl yanıldığımızın kaydı\" olarak depoda "
        "duruyor. Aynı ölçümün \"metrik kelime hazırlamayla şişirilemez\" maddesi de "
        "<b>geri çekildi</b>.", RED))

    E.append(P("13.6 · Literatürden alınıp bizde tutmayan yöntem", H2))
    E.append(P(
        "<b>Semantik gruplama.</b> Yayımlanmış bir çalışma (arXiv 2511.07171, Ovis-8B / "
        "UCF-Crime) kategorileri anlamsal gruplara indirmenin eğitim yapmadan +15,7 puan "
        "getirdiğini bildiriyor. Bizde aynı fikir kural 4 olarak ölçüldü: A kolunda +12,5 puan, "
        "B ve C kollarında <b>0,0 puan</b> — ortalama +4,2 puan, yani vaat edilenin dörtte biri. "
        "Üstelik tek pozitif sonuç yalnızca <b>3 klipten</b> ibaret ve gürültü tabanının "
        "sınırında."))
    E.append(P(
        "<b>Sebep tahmin edilmedi, ölçüldü.</b> İlk hipotezimiz \"grup içi kelime dağarcıkları "
        "örtüşüyor, katman etkisiz kalıyor\" idi ve <b>yanlış çıktı</b> (ölçülen grup içi "
        "örtüşme küçüktü). Gerçek sebep, kuralın değiştirdiği kliplerin tek tek listelenmesiyle "
        "bulundu: <b>gruplama yalnızca hata grubun içinde kaldığında işe yarıyor.</b> A kolunda "
        "kalan hatalar grup içindeydi (kavga/istismar karışması), B ve C kollarında ise gruplar "
        "arasıydı."))

    E.append(P("13.7 · İsteğe bağlıya düşürülenler", H2))
    E.append(tablo([
        ["Özellik", "Neden varsayılan değil"],
        ["Video belirteci budama", "Yalıtılmış ölçümde tarif adımını %40 hızlandırdı, ama tam "
                                   "akışta kazanç ~0 ve normal yanlış alarm arttı."],
        ["Toplu doğrulama", "Çok olaylı videolarda gecikmeyi %24 düşürüyor, ancak doğruluk "
                            "etkisi kanıtlanmadı."],
        ["Risk geri-çağırma eğilimi", "Görünen +12 kazanç <b>gürültü çıktı</b> (risk "
                                      "kalibrasyonuna katkı +0)."],
        ["Nörosimbolik olabilirlik kontrolü", "Grenli görüntüde YOLO kişi tespiti güvenilmez; "
                                              "tespit kaybı riski."],
        ["Kalıcı önem yükseltme", "Ölçümde dar yanlış alarmı 0'dan 12'ye çıkardı — "
                                  "<b>reddedildi</b>."],
    ], [48 * mm, 117 * mm]))
    E.append(Spacer(1, 1.5 * mm))
    E.append(P(
        "Ayrıca ortam duvarına takılan iki deneme vardır: yeni model çalıştırıcı sürümü "
        "(WSL2 GPU geçişi gereken birleşik adresleme desteğini sağlamıyor) ve FP8 KV önbelleği "
        "(bağlayıcı/ortam reddi). Bunlar doğruluk değil <b>ortam</b> kısıtlarıdır. Bir de "
        "kayıtlı günlüğü bulunamadığı için <b>geri çekilmiş</b> bir iddia vardır: sunucu "
        "bayrağı turunun getirdiği söylenen %24 verim artışı.", SMALL))

    E.append(PageBreak())

    # ==================================================================================
    E.append(P("14. Bilinen sınırlar", H1))
    E.append(P(
        "Aşağıdakiler tahmin değil, <b>ölçülmüş</b> sınırlardır. Bilerek ve açıkça "
        "raporlanmaktadır."))

    E.append(P("14.1 · Yetenek sınırları", H2))
    E.append(tablo([
        ["Sınır", "Ölçülen durum"],
        ["<b>Silahlı olay (Shooting) 0/3</b>",
         "Üç A/B kolunda ve dört skorlama kuralının <b>hepsinde</b> 0/3. Model olayı "
         "<b>görüyor</b> (tespit tam) ama \"silahlı\" demiyor: <i>\"iki kişi arasında fiziksel "
         "temas ve itme\"</i>, <i>\"bir kişi ani şekilde yere düşmüş\"</i> diyor. Semantik "
         "gruplama da kurtaramıyor çünkü \"Silahlı\" <b>tek üyeli</b> bir gruptur. Yayımlanmış "
         "bir çalışma (arXiv 2303.10703) UCF'nin 320×240 karelerinde tabancaların yaklaşık "
         "16 piksel olduğunu ölçüyor — <b>bilgi karede fiziksel olarak yoktur</b>."],
        ["Grenli görüntüde tür adlandırma",
         "İyimser sayı %38, onarılmış ölçümle %46. Kategori kırılımı: Patlama 3/3, "
         "Trafik kazası 2/3, Saldırı 2/3, Kavga 1/3, Hırsızlık 1/3, İstismar 0/3, "
         "Vandalizm 0/3, Silahlı 0/3."],
        ["<b>Özette uydurma ayrıntı</b>",
         "<b>10/37 = %27</b> [%15–%43]. Yani yaklaşık her dört özetten birinde görüntüde "
         "olmayan bir ayrıntı bulunuyor. Ana olay doğru, ayrıntı ekleniyor. Bu, belgedeki "
         "en önemli tek zayıflıktır."],
        ["Tesise özgü kural ihlali", "Kural verilse bile tavan %47 — ihlallerin yarısı "
                                     "kaçırılıyor. Risk kalibrasyonu bu olaylarda %10."],
        ["<b>Gece, kızılötesi, termal</b>", "<b>Sıfır kapsam.</b> Bütün setler gündüz/aydınlatılmış "
                                            "görünür ışıktır. \"Muhtemelen çalışır\" demiyoruz."],
        ["Forklift devrilmesi", "Şartnamenin örneklediği tam bu olay için gerçek açık veri "
                                "<b>yoktur</b>. En yakın kanıt devrilme değil, devrilme "
                                "öncesidir (aşırı yükle taşıma)."],
    ], [42 * mm, 123 * mm]))

    E.append(P("14.2 · Ölçüm sınırları", H2))
    E.append(B("<b>Küçük örneklem.</b> Ana setlerde n=24 ve n=25 anomali vardır. Tek klip "
               "oranı belirgin biçimde oynatır; bu boyutta sıralama karşılaştırması yapılamaz."))
    E.append(B("<b>Gürültü tabanı.</b> Tespitte %8, adlandırmada %12. Bundan küçük hiçbir etki "
               "bu setlerde ayırt edilemez."))
    E.append(B("<b>Güç yetersizliği.</b> Adlandırma A/B'si için mevcut n'de istatistiksel güç "
               "yalnızca %1; %80 güç için gereken klip sayısı <b>597</b>. Yani \"etki yok\" "
               "değil, <b>\"ölçülebilir etki yok\"</b> doğrudur."))
    E.append(B("<b>İnsan altın cetveli yok.</b> Onarılmış %46'nın gerçekten doğru olduğunu "
               "bilmiyoruz; yalnızca eski %38'den <b>daha az yanlış</b> olduğunu biliyoruz. "
               "24 klip üç kişi tarafından bir saatte hakem edilebilir — bu yapılmadı."))
    E.append(B("<b>Tespit tanımı gevşek.</b> Manşet \"tespit\" rakamı yalnızca \"en az bir olay "
               "üretildi mi\" demektir; tür doğruluğu aranmaz. Üç seviyeli dürüst okuma "
               "(51 bağımsız klip): <b>TESPİT 49/51 = %96 · AKSİYON 36/51 = %71 · "
               "TANIMA 22/51 = %43</b>."))
    E.append(B("<b>Hakem videoyu görmüyor.</b> İç tutarlılık skorları dış geçerlilik kanıtı "
               "değildir. Diyalog ölçümü ayrıca tavana doygundur (hakem her maddeye tam puan "
               "vermiş, standart sapma sıfır) — ayrım gücü yoktur, kusursuzluk kanıtı değildir."))
    E.append(B("<b>Onarılmış metrikle canlı koşu yok.</b> %46 rakamı arşiv yeniden "
               "skorlamasından gelmektedir; yeni kuralla üretilmiş taze bir GPU koşusu henüz "
               "yapılmamıştır. Ayrıca senaryo seti bu onarımdan sonra yeniden ölçülmemiştir — "
               "oradaki %92–96 rakamları hâlâ eski kuraldır."))
    E.append(B("<b>Tek donanım, tek dil, tek operatör.</b> Tek GPU, tek model, Türkçe. Farklı "
               "kart, sürücü veya niceleme altında yeniden üretim test edilmemiştir."))

    E.append(KeepTogether([
        P("14.3 · Bu sistem ne için KULLANILMAZ", H2),
        kutu_metin(
            "<b>· Otonom alarm veya insan onayı olmadan otomatik ekip sevki</b><br/>"
            "<b>· İnsansız gece vardiyası</b> (gece/termal kapsam sıfırdır)<br/>"
            "<b>· Tesise özgü politika denetiminin tek dayanağı olmak</b> (tavan %47)<br/>"
            "<b>· Silah veya ince tehdit tespiti</b> (0/3, yapısal sınır)",
            stil=BODY, arka="#fbf2f2", cerceve="#e0c4c4"),
    ]))

    # ==================================================================================
    E.append(P("15. Yol haritası", H1))
    E.append(P("Sıradaki adımlar, yukarıdaki sınırların doğrudan karşılığıdır:"))
    E.append(tablo([
        ["Sıra", "Adım", "Hangi sınırı kapatır"],
        ["1", "<b>Determinizmi sabitlemek</b> — toplu işlem boyutunu sabitleyip koşu-arası "
              "salınımı düşürmek.",
         "Gürültü tabanı %8/%12 olduğu sürece hiçbir küçük iyileştirme doğrulanamıyor. "
         "Bu, diğer bütün adımların önkoşuludur."],
        ["2", "<b>İnsan altın cetveli</b> — 24 klibi üç değerlendiriciyle hakem etmek.",
         "Onarılmış adlandırma metriğinin gerçekten doğru olup olmadığını bilmiyoruz."],
        ["3", "<b>Onarılmış metrikle taze koşu</b> — holdout ve senaryo setlerini yeni "
              "skorlama kuralıyla yeniden ölçmek.",
         "Bugünkü %46, arşiv yeniden skorlamasından geliyor; canlı koşu yok."],
        ["4", "<b>Uydurma ayrıntıyı azaltmak</b> — özet üretiminde dayanaklandırma "
              "kısıtlarını sıkılaştırmak.",
         "%27 uydurma ayrıntı, kalite tarafındaki en büyük tek açık."],
        ["5", "<b>Örneklem büyütmek</b> — adlandırma A/B'si için gereken klip sayısı ölçüldü: "
              "597.",
         "Mevcut güç %1; bu haliyle hiçbir adlandırma müdahalesi kanıtlanamaz."],
        ["6", "<b>Gece / kızılötesi kapsamı</b> — bu koşullarda veri toplamak ve ölçmek.",
         "Bugün sıfır kapsam var; sistem bu koşullarda hiç test edilmedi."],
        ["7", "<b>Bağımlılık ve belge açıklarını kapatmak</b> — ultralytics'i gereksinim "
              "dosyalarına eklemek, arayüz adım göstergesine policy_gate'i yansıtmak, "
              "yönlendirici açıklama metnini davranışla uyumlamak, kaynağı bulunamayan "
              "\"süper-çözünürlük\" iddiasını tablodan çıkarmak.",
         "Bu belgede tespit edilen, kod ile belge arasındaki tutarsızlıklar."],
    ], [13 * mm, 77 * mm, 75 * mm]))

    E.append(Spacer(1, 4 * mm))
    E.append(kutu_metin(
        "<b>Kapanış.</b> Bu belgedeki her sayı depodaki bir dosyadan okunmuştur ve yeniden "
        "üretilebilir. Ölçümler <font face=\"DVM\">benchmark/results/</font> altında ham JSON "
        "olarak durur; skorlama <font face=\"DVM\">benchmark/rescore.py</font> ile model "
        "çalıştırmadan yeniden hesaplanabilir; testler "
        "<font face=\"DVM\">tests/</font> altındadır. Sayı verilemeyen yerlerde cümle "
        "sayısız bırakılmıştır — bir rakamı savunamıyorsak yazmıyoruz.",
        stil=BODY, arka="#eef3f8"))
    return E


# --------------------------------------------------------------------------------------
def main() -> None:
    os.makedirs(os.path.dirname(CIKTI), exist_ok=True)
    doc = SimpleDocTemplate(
        CIKTI, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=18 * mm, bottomMargin=16 * mm,
        title="DilAjanları — Modelin Baştan Sona Anlatımı", author="VigilantAI",
        subject="TEKNOFEST 2026 Türkçe Yapay Zekâ Dil Ajanları · 3. Senaryo",
    )

    def sayfa(canvas, _doc):
        canvas.saveState()
        # ustbilgi
        canvas.setFont("DV", 7.4)
        canvas.setFillColor(GRAY)
        canvas.drawString(22 * mm, A4[1] - 12 * mm,
                          "DilAjanları · Modelin Baştan Sona Anlatımı")
        canvas.drawRightString(A4[0] - 22 * mm, A4[1] - 12 * mm, "VigilantAI · TEKNOFEST 2026")
        canvas.setStrokeColor(colors.HexColor("#c8d2de"))
        canvas.setLineWidth(0.4)
        canvas.line(22 * mm, A4[1] - 14 * mm, A4[0] - 22 * mm, A4[1] - 14 * mm)
        # altbilgi
        canvas.line(22 * mm, 13 * mm, A4[0] - 22 * mm, 13 * mm)
        canvas.drawString(22 * mm, 9 * mm, "Her sayı depodan okunmuştur · 11 Ağustos 2026")
        canvas.drawRightString(A4[0] - 22 * mm, 9 * mm, f"Sayfa {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(icerik(), onFirstPage=sayfa, onLaterPages=sayfa)
    print(f"PDF uretildi -> {os.path.relpath(CIKTI, KOK)}  "
          f"({os.path.getsize(CIKTI) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
