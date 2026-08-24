"""ISG KURAL MOTORU — gozlem slotlarindan DETERMINISTIK olay uretimi (D43).

KARAR DONGUSUNDE MODEL YOKTUR. Model yalnizca `gozlem.py` icinde bir SLOT
doldurur (kapali cevap uzayi: sayi ya da etiket); hukmu bu modul verir.

BU NEDEN ONEMLI — OLCULDU
--------------------------
Eski mimaride hukum modelin SERBEST METNINE, sonra da SOZCUK ESLESMESINE
emanet edilmisti ve iki asamada bilgi kaybediliyordu:
    cikarim asamasi : %45 kayip (11/20 gecti)
    sozcuksel kapi  : %64 kayip (4/11 yakalandi)
Burada ikisi de YAPISAL OLARAK imkansiz:
  - cikarim yok (cevap zaten tipli),
  - `Event.event` metni SABLON RENDER'idir, model nesri degil.

Olculen uc kacirma mekanizmasi da boylece yok olur:
  (a) es anlamli sozcuk  : model "gorus hattini KAPATIYOR", kalip "gorusu ENGEL"
                           -> forklift sinifinda 5/5 boyle kacmisti
  (b) unsuz yumusamasi   : model "SERIDININ disinda", kalip "SERIT"
  (c) sozluk-tanim ayrismasi

ESIKLER TESISE OZGUDUR
----------------------
"3 kasa" ve "koyuluk >= 3" BU TESISIN konvansiyonudur; kaynak makaleden
(Onal & Dandil 2024, Data in Brief 56:110756) ve kendi kalibrasyonumuzdan gelir.
Baska tesiste YENIDEN BELIRLENMELIDIR. Bu yuzden hepsi ayardan okunur.
"""
from __future__ import annotations

from typing import List, Optional

from dilajan.schema import Event, EventCategory, Severity


class Kural:
    """Tek bir deterministik ISG kurali."""

    def __init__(self, kod: str, slot: str, sablon: str,
                 kategori: EventCategory = EventCategory.GUVENLIK,
                 severity: Severity = Severity.YUKSEK,
                 on_slot: str = "", on_asgari: int = 1):
        self.kod = kod              # ISG sinif kodu (etiket metrigi bunu okur)
        self.slot = slot
        self.sablon = sablon        # Event.event metni — MODEL NESRI DEGIL
        self.kategori = kategori
        self.severity = severity
        # ON KOSUL — kuralin GECERLI oldugu sahneyi tanimlar.
        # Bos ise kural her sahnede degerlendirilir (eski davranis).
        self.on_slot = on_slot
        self.on_asgari = on_asgari

    def on_kosul_saglandi(self, kayit) -> bool:
        """Kuralin sorusu bu sahnede ANLAMLI mi?

        Kacirma degil, GECERSIZLIK filtresi: on slot cozulemediyse ya da
        esigin altindaysa kural SESSIZ kalir. Deterministiktir; modelin
        kendi kendini frenlemesine dayanmaz.
        """
        if not self.on_slot:
            return True
        v = kayit.al(self.on_slot)
        if v is None:
            return False            # olculemedi -> IDDIA ETME
        try:
            return int(v) >= self.on_asgari
        except (TypeError, ValueError):
            return False

    def degerlendir(self, kayit, ayar) -> Optional[dict]:
        raise NotImplementedError


class EsikKurali(Kural):
    """Sayisal slot >= esik ise ihlal."""

    def __init__(self, kod, slot, sablon, esik_alani, esik_varsayilan,
                 **kw):
        super().__init__(kod, slot, sablon, **kw)
        self.esik_alani = esik_alani
        self.esik_varsayilan = esik_varsayilan

    def degerlendir(self, kayit, ayar) -> Optional[dict]:
        if not self.on_kosul_saglandi(kayit):
            return None                      # sahne kural icin GECERSIZ
        v = kayit.al(self.slot)
        if v is None:
            return None                      # slot cozulemedi -> SESSIZ (K3)
        esik = getattr(ayar, self.esik_alani, self.esik_varsayilan)
        if v < esik:
            return None
        return {"kod": self.kod, "metin": self.sablon.format(deger=v, esik=esik),
                "severity": self.severity, "kategori": self.kategori,
                "slot": self.slot, "deger": v}


class EtiketKurali(Kural):
    """Etiket slotu belirli degere esitse ihlal."""

    def __init__(self, kod, slot, sablon, ihlal_degeri, **kw):
        super().__init__(kod, slot, sablon, **kw)
        self.ihlal_degeri = ihlal_degeri

    def degerlendir(self, kayit, ayar) -> Optional[dict]:
        if not self.on_kosul_saglandi(kayit):
            return None                      # sahne kural icin GECERSIZ
        v = kayit.al(self.slot)
        if v is None or v != self.ihlal_degeri:
            return None
        return {"kod": self.kod, "metin": self.sablon.format(deger=v, esik=""),
                "severity": self.severity, "kategori": self.kategori,
                "slot": self.slot, "deger": v}


# ---------------------------------------------------------------------------
# KURAL KATALOGU
# ---------------------------------------------------------------------------
# Sablon metinleri sinif TANIMINDAN turer ve eslestiricinin kaliplariyla
# UYUMLU yazilir — ama asil kazanc su: metin SABIT oldugu icin eslestiricinin
# es-anlamli/morfoloji kacirmalari YAPISAL OLARAK imkansizdir.
KURALLAR: List[Kural] = [
    EsikKurali(
        kod="Carrying_Overload_with_Forklift",
        slot="catal_kasa_sayisi",
        sablon=("Forklift asiri yuk tasiyor: catalda {deger} kasa istiflenmis "
                "(guvenli sinir {esik} kasanin altidir)"),
        esik_alani="forklift_esik", esik_varsayilan=3,
        severity=Severity.YUKSEK,
    ),
    EsikKurali(
        kod="Opened_Panel_Cover",
        slot="pano_koyuluk_0_10",
        sablon=("Pano kapagi acik birakilmis: elektrik/kontrol panosu bolgesinde "
                "koyu oyuk goruluyor (koyuluk {deger}/10)"),
        esik_alani="panel_koyuluk_esik", esik_varsayilan=3,
        severity=Severity.YUKSEK,
    ),
    EtiketKurali(
        kod="Unauthorized_Intervention",
        slot="makine_basinda_yelek",
        sablon=("Yetkisiz mudahale: makineye mudahale eden kiside reflektif "
                "yelek yok"),
        ihlal_degeri="YOK",
        kategori=EventCategory.YETKISIZ_ERISIM,
        severity=Severity.YUKSEK,
        # ON KOSUL: makinenin onunde EN AZ 1 kisi olmali. Olculdu — bu kapi
        # olmadan kural FORKLIFT kamerasinda da atesleniyordu (orada ne pano
        # ne kisi var; model yine de "yelek YOK" diyordu).
        on_slot="makine_basinda_kisi", on_asgari=1,
    ),
]


def olaylari_uret(kayit, ayar, zaman: str = "00:00") -> List[Event]:
    """Gozlem kaydindan deterministik olay listesi.

    Donen her `Event`, sema-disi `isg_kod` isareti tasir (policy_prev/ppe_src
    ile ayni desen): `model_dump()` anahtarlarina SIZMAZ, ama etiket metrigi
    ve karar-izi onu okuyabilir. Boylece "hangi olay hangi ISG sinifi" sorusu
    SOZCUK ESLESMESI OLMADAN cevaplanir.
    """
    out: List[Event] = []
    if not kayit:
        return out
    for k in KURALLAR:
        s = k.degerlendir(kayit, ayar)
        if not s:
            continue
        out.append(Event(
            time=zaman, event=s["metin"], severity=s["severity"],
            category=s["kategori"],
        ).model_copy(update={"isg_kod": s["kod"], "isg_slot": s["slot"],
                             "isg_deger": s["deger"]}))
    return out


def gerekli_slotlar(ayar) -> List[str]:
    """Ayarda ACIK olan kurallarin ihtiyac duydugu slot adlari.

    Kapali kural icin slot SORULMAZ — gereksiz model cagrisi yapilmaz.
    """
    acik = (getattr(ayar, "isg_slotlari", "") or "").strip()
    if not acik:
        return []
    def _ile_on(kurallar):
        """Kural slotu + (varsa) ON KOSUL slotu — sira korunur, tekrar yok."""
        out: List[str] = []
        for k in kurallar:
            for ad in (k.on_slot, k.slot):
                if ad and ad not in out:
                    out.append(ad)
        return out

    if acik == "*":
        return _ile_on(KURALLAR)
    istenen = {x.strip() for x in acik.split(",") if x.strip()}
    return _ile_on([k for k in KURALLAR
                    if k.slot in istenen or k.kod in istenen])
