#!/usr/bin/env python
"""Mentor icin SADE model tanitim PDF'i uretir (reportlab + DejaVu/Turkce, offline).

Amac: mevcut modelin NE OLDUGUNU ve NE YAPTIGINI net cumlelerle anlatmak.
Pazarlama dili yok; her sayi olculmus ve kaynagi belli.

Cikti: docs/DilAjanlari_Mentor_Sunumu.pdf
"""
from __future__ import annotations

import os

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
CIKTI = os.path.join(KOK, "docs", "DilAjanlari_Mentor_Sunumu.pdf")

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
pdfmetrics.registerFont(TTFont("DV", os.path.join(FONT_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DVM", os.path.join(FONT_DIR, "DejaVuSansMono.ttf")))

NAVY = colors.HexColor("#0f2547")
BLUE = colors.HexColor("#1668b3")
GRAY = colors.HexColor("#5a6472")
LIGHT = colors.HexColor("#eef3ف8".replace("ف", "f"))
GREEN = colors.HexColor("#1a7f45")
AMBER = colors.HexColor("#b06a00")

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="DVB", fontSize=15,
                    textColor=NAVY, spaceBefore=12, spaceAfter=7)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="DVB", fontSize=11,
                    textColor=BLUE, spaceBefore=9, spaceAfter=4)
BODY = ParagraphStyle("BODY", parent=styles["BodyText"], fontName="DV", fontSize=9.6,
                      leading=14, textColor=colors.HexColor("#1a1a1a"), alignment=TA_LEFT,
                      spaceAfter=5)
BULLET = ParagraphStyle("BULLET", parent=BODY, leftIndent=11, bulletIndent=2, spaceAfter=3)
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=8.2, textColor=GRAY, leading=11)
MONO = ParagraphStyle("MONO", parent=BODY, fontName="DVM", fontSize=8.4, leading=12,
                      textColor=NAVY)
CELL = ParagraphStyle("CELL", parent=BODY, fontSize=8.7, leading=11.5, spaceAfter=0)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="DVB")
TITLE = ParagraphStyle("TITLE", parent=styles["Title"], fontName="DVB", fontSize=23,
                       textColor=colors.white, alignment=TA_CENTER, leading=28)
SUB = ParagraphStyle("SUB", parent=BODY, fontSize=10.5, textColor=colors.white,
                     alignment=TA_CENTER, spaceAfter=0)


def P(t, s=BODY):
    return Paragraph(t, s)


def B(t):
    return Paragraph(t, BULLET, bulletText="•")


def tablo(satirlar, genislikler, baslik=True):
    data = []
    for i, sat in enumerate(satirlar):
        stil = CELLB if (baslik and i == 0) else CELL
        data.append([Paragraph(str(h), stil) for h in sat])
    t = Table(data, colWidths=genislikler, hAlign="LEFT")
    komut = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d2de")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if baslik:
        komut += [("BACKGROUND", (0, 0), (-1, 0), NAVY),
                  ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
        komut += [("ROWBACKGROUNDS", (0, 1), (-1, -1),
                   [colors.white, colors.HexColor("#f4f7fb")])]
    t.setStyle(TableStyle(komut))
    return t


def kapak():
    kutu = Table([[Paragraph("DilAjanları", TITLE)],
                  [Paragraph("Yerel Video Analiz ve Karar Destek Ajanı", SUB)],
                  [Paragraph("TEKNOFEST 2026 · Türkçe Yapay Zekâ Dil Ajanları · 3. Senaryo", SUB)]],
                 colWidths=[165 * mm])
    kutu.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    return kutu


def icerik():
    E = []
    E.append(kapak())
    E.append(Spacer(1, 7 * mm))

    # ---------- 1. Sistem ne yapıyor ----------
    E.append(P("1. Sistem ne yapıyor?", H1))
    E.append(P("Sisteme bir güvenlik kamerası videosu verilir. Sistem videoyu izler ve "
               "operatöre dört çıktı üretir:"))
    E.append(B("Videoda ne olduğunun <b>zaman damgalı olay listesi</b>"))
    E.append(B("Olayları özetleyen <b>kısa Türkçe metin</b>"))
    E.append(B("Gerekçesiyle birlikte <b>risk değerlendirmesi</b> (Düşük / Orta / Yüksek / Kritik)"))
    E.append(B("Operatöre <b>uygulanabilir aksiyon önerileri</b>"))
    E.append(Spacer(1, 3 * mm))
    E.append(P("Bunlara ek olarak sistem, riskin yüksek olduğu durumlarda operasyonel "
               "fonksiyonları kendisi çağırır: sağlık ekibi yönlendirme, güvenlik uyarısı, "
               "alanı güvenliğe alma, acil durdurma, olay kaydı, yönetici bilgilendirme."))
    E.append(Spacer(1, 2 * mm))
    E.append(P("Tüm çıktılar JSON biçimindedir. Sistem tamamen yerel çalışır; internet "
               "bağlantısı veya dış servis kullanmaz.", SMALL))

    # ---------- 2. Örnek çıktı ----------
    E.append(P("2. Örnek çıktı", H1))
    E.append(P("Sistemin ürettiği JSON şu yapıdadır:"))
    E.append(Spacer(1, 1.5 * mm))
    ornek = (
        '{<br/>'
        '&nbsp;&nbsp;"summary": "Depoda yangın başlangıcı gözlendi; duman hızla yayılıyor.",<br/>'
        '&nbsp;&nbsp;"events": [<br/>'
        '&nbsp;&nbsp;&nbsp;&nbsp;{"time": "00:12", "event": "Makine yanında alev ve duman"},<br/>'
        '&nbsp;&nbsp;&nbsp;&nbsp;{"time": "00:24", "event": "Personel alanı terk ediyor"}<br/>'
        '&nbsp;&nbsp;],<br/>'
        '&nbsp;&nbsp;"risk": "Kritik",<br/>'
        '&nbsp;&nbsp;"actions": ["Güvenlik ekibini uyar", "Alanı güvenlik altına al", '
        '"Olay kaydı oluştur"]<br/>'
        '}'
    )
    kutu = Table([[Paragraph(ornek, MONO)]], colWidths=[165 * mm])
    kutu.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f6fb")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c8d2de")),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    E.append(kutu)

    # ---------- 3. Nasıl çalışıyor ----------
    E.append(P("3. Nasıl çalışıyor?", H1))
    E.append(P("Sistem bir <b>ajan</b> olarak kurulmuştur. Video, birbirini izleyen adımlardan "
               "geçer. Her adım bir sonrakine bilgi aktarır:"))
    E.append(Spacer(1, 2 * mm))
    E.append(tablo([
        ["Adım", "Ne yapar"],
        ["1. Görüntü alımı", "Videoyu zaman damgalı karelere böler, 10 saniyelik segmentlere ayırır."],
        ["2. Olay algısı", "Her segmenti modele iki aşamada sorar: önce serbest Türkçe tarif, "
                           "sonra bu tariften olay çıkarımı. Segmentler paralel işlenir."],
        ["3. Yeniden inceleme", "<b>Koşulludur.</b> Belirsiz bir olay varsa ajan o segmente "
                                "dönüp tekrar bakar. Belirsizlik yoksa bu adım atlanır."],
        ["4. Değerlendirme", "Tüm olaylara bakarak özet, risk seviyesi ve aksiyon önerileri üretir."],
        ["5. Aksiyon", "Riske göre hangi operasyonel fonksiyonların çağrılacağına model karar verir."],
        ["6. Rapor", "Sonucu JSON olarak paketler."],
    ], [30 * mm, 135 * mm]))
    E.append(Spacer(1, 3 * mm))
    E.append(P("Üçüncü adımın koşullu olması önemlidir: akış düz bir boru hattı değildir, "
               "ajan duruma göre farklı yollar izler.", SMALL))

    E.append(PageBreak())

    # ---------- 4. Kullanılan teknoloji ----------
    E.append(P("4. Kullanılan teknoloji", H1))
    E.append(tablo([
        ["Bileşen", "Seçim", "Neden"],
        ["Model", "Qwen3-VL-8B-Instruct (FP8)", "Video ve metni birlikte anlayan açık kaynak "
                                                "model. Türkçesi akıcı."],
        ["Servisleme", "vLLM 0.23", "Modeli yerelde hızlı çalıştırır. Aynı anda birden çok "
                                    "isteği toplu işler."],
        ["Ajan çerçevesi", "LangGraph", "Adımları ve koşullu dallanmayı yönetir."],
        ["Arayüz", "Gradio", "Operatör konsolu."],
        ["Yardımcı", "YOLO11n", "Kişi/araç sayımı, düşme pozu doğrulama gibi kesin ölçümler."],
    ], [28 * mm, 47 * mm, 90 * mm]))
    E.append(Spacer(1, 3 * mm))
    E.append(P("Geliştirme donanımı: RTX 5090 Laptop, 24 GB VRAM. Model 19 GB yer kaplar, "
               "tepe kullanım 22.7 GB ölçülmüştür.", SMALL))
    E.append(P("Daha büyük modeller de denendi: Qwen2.5-VL-32B (24 GB'a sığmadı) ve "
               "InternVL3.5-14B (Türkçesi zayıf, doğruluğu düşük çıktı). 8B modeli ölçümle seçildi.", SMALL))

    # ---------- 5. Model ne kadar başarılı ----------
    E.append(P("5. Model ne kadar başarılı?", H1))
    E.append(P("Aşağıdaki sayılar 28 Temmuz 2026'da gerçek GPU koşusuyla ölçülmüştür. "
               "Parantez içindekiler %95 güven aralığıdır."))
    E.append(Spacer(1, 2 * mm))
    E.append(P("Olay tespiti — iki ayrı veri seti", H2))
    E.append(tablo([
        ["Ölçüm", "Senaryo seti", "Bağımsız doğrulama seti"],
        ["Olay tespiti", "<b>%96</b> (24/25)", "<b>%96</b> (23/24)"],
        ["Olay türünü doğru adlandırma", "<b>%96</b>", "%38"],
        ["Risk seviyesi doğruluğu", "%88", "%83"],
        ["Normal videoda yanlış alarm", "<b>%0</b>", "<b>%0</b>"],
        ["Normal videoda yanlış ekip çağırma", "<b>%0</b>", "<b>%0</b>"],
    ], [58 * mm, 53 * mm, 54 * mm]))
    E.append(Spacer(1, 2 * mm))
    E.append(P("İki set birbirinden bağımsızdır ve aynı tespit oranını vermiştir. Bu, sonucun "
               "tesadüf olmadığını gösterir. Aradaki fark <b>görüntü kalitesindedir</b>: "
               "senaryo seti net görüntüler içerir, doğrulama seti 320×240 çözünürlüklü eski "
               "kamera kayıtlarıdır. Sistem bulanık görüntüde olayı yakalar ama türünü "
               "adlandıramaz."))

    E.append(Spacer(1, 3 * mm))
    E.append(P("Çıktı kalitesi", H2))
    E.append(tablo([
        ["Ölçüm", "Sonuç"],
        ["JSON biçim uyumu", "<b>%100</b>"],
        ["Aksiyon önerisi kalitesi (1–5)", "4.83"],
        ["Risk gerekçesi kalitesi (1–5)", "4.89"],
        ["Özetin videoya dayanaklılığı (1–5)", "4.38"],
        ["Bozuk / boş / siyah videoda çökme", "<b>Yok</b> (4/4 düzgün sonuç)"],
    ], [95 * mm, 70 * mm]))
    E.append(Spacer(1, 2 * mm))
    E.append(P("Kalite puanları, sistemi geliştiren modelden <b>farklı bir model</b> "
               "(Gemma-3-12B) tarafından verilmiştir. Böylece sistemin kendi kendini "
               "puanlaması önlenmiştir.", SMALL))

    E.append(Spacer(1, 3 * mm))
    E.append(P("Hız", H2))
    E.append(tablo([
        ["Ölçüm", "Sonuç"],
        ["Video saniyesi başına işlem", "0.66 saniye"],
        ["Aynı anda 4 video işlenirken", "2.23 kat hızlanma (6.5 video/dakika)"],
        ["Zamanın nereye gittiği", "%98 model çıkarımı, %2 video okuma"],
    ], [70 * mm, 95 * mm]))

    E.append(PageBreak())

    # ---------- 6. Arayüz ----------
    E.append(P("6. Operatör arayüzü", H1))
    E.append(P("Arayüz bir tasarım taslağı değil, çalışan bir konsoldur. Operatör videoyu "
               "yükler ve şunları görür:"))
    E.append(B("Analiz sırasında <b>hangi adımın çalıştığı</b> canlı olarak gösterilir."))
    E.append(B("<b>Risk rozeti</b> renk kodludur; kritik durumda dikkat çeker."))
    E.append(B("<b>Olay zaman çizelgesi</b> olayların videonun neresinde olduğunu gösterir."))
    E.append(B("<b>Olay tablosu</b> zaman, açıklama, önem, kategori ve konum sütunlarını içerir."))
    E.append(B("<b>Aksiyon önerileri</b> ve <b>tetiklenen fonksiyonlar</b> ayrı listelenir."))
    E.append(B("<b>Karar günlüğü</b> sistemin neden o kararı verdiğini adım adım gösterir."))
    E.append(B("<b>Sohbet paneli</b> ile operatör analiz hakkında soru sorabilir. Operatör "
               "onay verirse önerilen aksiyon gerçekten çalıştırılır."))
    E.append(B("<b>Olay tutanağı</b>, <b>kanıt paketi</b> ve <b>vardiya brifingi</b> üretilebilir."))
    E.append(Spacer(1, 2 * mm))
    E.append(P("Arayüz GPU olmadan da açılabilir (sahte veri modu). Böylece takımın geri kalanı "
               "güçlü donanım olmadan geliştirme yapabilir.", SMALL))

    # ---------- 7. Sınırlar ----------
    E.append(P("7. Sistemin sınırları", H1))
    E.append(P("Aşağıdakiler ölçülmüş gerçek sınırlardır. Bilinerek raporlanmaktadır."))
    E.append(Spacer(1, 2 * mm))
    E.append(tablo([
        ["Sınır", "Açıklama"],
        ["Bulanık görüntüde tür tanıma",
         "320×240 kayıtlarda olay yakalanır ama türü %38 oranında adlandırılabilir."],
        ["Özette uydurma ayrıntı",
         "Özetlerin %27'sinde görüntüde olmayan bir ayrıntı bulunmuştur. Ana olay doğrudur, "
         "ayrıntı eklenebilmektedir."],
        ["Tesise özgü kural ihlalleri",
         "\"Yürüyüş yolu ihlali\" gibi olaylar görüntüden anlaşılmaz; kural bilgisi gerekir. "
         "Kural verildiğinde tespit %20'den %47'ye çıkar (istatistiksel olarak kanıtlanmıştır)."],
        ["Gece ve termal görüntü", "Hiç test edilmemiştir."],
        ["Ölçek", "Tek GPU aynı anda 2–3 kamera akışı taşır."],
    ], [46 * mm, 119 * mm]))

    # ---------- 8. Özet ----------
    E.append(P("8. Özetle", H1))
    E.append(P("<b>Sistem şunları güvenilir biçimde yapıyor:</b>"))
    E.append(B("Yangın, düşme, patlama, kaza gibi <b>görsel olarak belirgin olayları</b> "
               "iki ayrı veri setinde %96 oranında yakalıyor."))
    E.append(B("Normal videolarda <b>boşuna ekip çağırmıyor</b> (yanlış çağrı oranı %0)."))
    E.append(B("Çıktı biçimi <b>her zaman doğru</b> (%100 JSON uyumu)."))
    E.append(B("Bozuk girdide <b>çökmüyor</b>, anlamlı bir sonuç döndürüyor."))
    E.append(Spacer(1, 2 * mm))
    E.append(P("<b>Sistem şunlarda zayıf:</b>"))
    E.append(B("Bulanık görüntüde olayın <b>türünü</b> adlandırmakta."))
    E.append(B("Özetlere <b>fazladan ayrıntı</b> eklemekte."))
    E.append(B("Kural bilgisi gerektiren <b>politika ihlallerinde</b>."))
    E.append(Spacer(1, 3 * mm))
    E.append(P("Bu nedenle sistem şu anda <b>operatörün yerine karar veren</b> bir alarm sistemi "
               "olarak değil, <b>operatöre yardımcı olan</b> bir inceleme ve triyaj aracı olarak "
               "konumlandırılmaktadır. Tüm operasyonel çağrılar öneri olarak sunulur; "
               "operatör onaylamadan hiçbir işlem yapılmaz."))

    E.append(Spacer(1, 5 * mm))
    E.append(P("Tüm ölçümler yeniden üretilebilir: <font face=\"DVM\">python scripts/full_benchmark.py</font>. "
               "Ham çıktılar depoda <font face=\"DVM\">benchmark/results/</font> altındadır.", SMALL))
    return E


def main() -> None:
    os.makedirs(os.path.dirname(CIKTI), exist_ok=True)
    doc = SimpleDocTemplate(
        CIKTI, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="DilAjanları — Model Tanıtımı", author="VigilantAI",
    )

    def sayfa(canvas, _doc):
        canvas.saveState()
        canvas.setFont("DV", 7.5)
        canvas.setFillColor(GRAY)
        canvas.drawRightString(A4[0] - 22 * mm, 10 * mm, f"{canvas.getPageNumber()}")
        canvas.drawString(22 * mm, 10 * mm, "DilAjanları · Model Tanıtımı · 2026-07-29")
        canvas.restoreState()

    doc.build(icerik(), onFirstPage=sayfa, onLaterPages=sayfa)
    print(f"PDF uretildi -> {os.path.relpath(CIKTI, KOK)}  "
          f"({os.path.getsize(CIKTI) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
