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
                 on_slot: str = "", on_asgari: int = 1,
                 on_azami: int = 10 ** 9, on_bayrak_alani: str = ""):
        self.kod = kod              # ISG sinif kodu (etiket metrigi bunu okur)
        self.slot = slot
        self.sablon = sablon        # Event.event metni — MODEL NESRI DEGIL
        self.kategori = kategori
        self.severity = severity
        # ON KOSUL — kuralin GECERLI oldugu sahneyi tanimlar.
        # Bos ise kural her sahnede degerlendirilir (eski davranis).
        self.on_slot = on_slot
        self.on_asgari = on_asgari
        self.on_azami = on_azami
        # Bos degilse: ayardaki bu bayrak False iken ON KOSUL ATLANIR.
        self.on_bayrak_alani = on_bayrak_alani

    def on_kosul_saglandi(self, kayit, ayar=None) -> bool:
        """Kuralin sorusu bu sahnede ANLAMLI mi?

        Kacirma degil, GECERSIZLIK filtresi: on slot cozulemediyse ya da
        esigin altindaysa kural SESSIZ kalir. Deterministiktir; modelin
        kendi kendini frenlemesine dayanmaz.
        """
        if not self.on_slot:
            return True
        # BAYRAKLA KAPATILABILIR on kosul. `ayar` verilmezse (eski cagrilar)
        # davranis BIREBIR ayni kalir -> K2.
        if self.on_bayrak_alani and ayar is not None:
            if not getattr(ayar, self.on_bayrak_alani, True):
                return True                      # kapi KAPALI -> kural serbest
        v = kayit.al(self.on_slot)
        if v is None:
            return False            # olculemedi -> IDDIA ETME
        try:
            n = int(v)
        except (TypeError, ValueError):
            return False
        # UST SINIR (`on_azami`) `on_asgari`nin simetrigidir: bazi kurallar
        # on slotun COK olmasi degil AZ olmasi kosuluna baglidir. Yaya yolu
        # kuralinda ayirt edici sey kisinin KONUMUDUR — pano/yetkisiz
        # kliplerinde kisi makinenin basinda DURUR, yol kliplerinde zeminde
        # YURUR. `on_azami=0` ayni kamerada iki tehlikeyi ayirir.
        # VARSAYILAN SINIRSIZ -> mevcut kurallarin davranisi DEGISMEZ (K2).
        return self.on_asgari <= n <= self.on_azami

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
        if not self.on_kosul_saglandi(kayit, ayar):
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


class AltEsikKurali(Kural):
    """Sayisal slot < esik ise ihlal (EsikKurali'nin TERSI).

    Ayri bir sinif olmasinin sebebi: yonu bir bayrakla degistirilebilir yapmak,
    "sonuc kotu ciktiysa yonu cevir" kapisini acardi. Yon KURALIN TANIMINDA
    sabittir ve hangi olcumden geldigi slot aciklamasinda yazilidir.
    """

    def __init__(self, kod, slot, sablon, esik_alani, esik_varsayilan, **kw):
        super().__init__(kod, slot, sablon, **kw)
        self.esik_alani = esik_alani
        self.esik_varsayilan = esik_varsayilan

    def degerlendir(self, kayit, ayar) -> Optional[dict]:
        if not self.on_kosul_saglandi(kayit, ayar):
            return None
        v = kayit.al(self.slot)
        if v is None:
            return None                      # slot cozulemedi -> SESSIZ (K3)
        esik = getattr(ayar, self.esik_alani, self.esik_varsayilan)
        if v >= esik:
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
        if not self.on_kosul_saglandi(kayit, ayar):
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
# SABLON METINLERI GERCEK TURKCE YAZILIR — ASCII'lestirilmez.
# Bu metinler OPERATORE gosterilir (arayuzdeki olay tablosu) ve etiket
# metrigi de bunlar uzerinden calisir. ASCII'lestirilmis hallerinde:
#   (a) juriye "Pano kapagi acik birakilmis" gibi bozuk Turkce gorunuyordu,
#   (b) `isg_any_match` kaliplari gercek Turkce oldugu icin DORT sablondan
#       IKISI kendi sinifiyla ESLESMIYORDU — yani kural DOGRU ateslese bile
#       olcum onu kacirma sayiyordu.
# Kod yorumlari ASCII kalir (depo kurali); KULLANICIYA GIDEN metin Turkcedir.
KURALLAR: List[Kural] = [
    EsikKurali(
        kod="Carrying_Overload_with_Forklift",
        slot="catal_kasa_sayisi",
        sablon=("Forklift aşırı yük taşıyor: çatalda {deger} kasa istiflenmiş — "
                "güvenli yük sınırı {esik} kasanın altıdır"),
        esik_alani="forklift_esik", esik_varsayilan=3,
        severity=Severity.YUKSEK,
    ),
    EsikKurali(
        kod="Opened_Panel_Cover",
        slot="pano_koyuluk_0_10",
        sablon=("Pano kapağı açık bırakılmış: elektrik/kontrol panosu bölgesinde "
                "koyu oyuk görülüyor (koyuluk {deger}/10)"),
        esik_alani="panel_koyuluk_esik", esik_varsayilan=3,
        severity=Severity.YUKSEK,
    ),
    AltEsikKurali(
        kod="Safe_Walkway_Violation",
        slot="yaya_cizgi_mesafe",
        # METIN OLCULEN SEYI ANLATIR. Cizginin bu tesiste ne oldugunu
        # bilmiyoruz; "yaya yolunun disina cikti" gibi bir NEDEN iddia etmek
        # olcumun otesine gecmek olurdu.
        sablon=("Yaya yolu ihlali: kişi yerdeki işaretli çizginin hemen "
                "üzerinde/bitişiğinde yürüyor (çizgiye uzaklık {deger}/10, "
                "güvenli sınır {esik} ve üzeridir)"),
        esik_alani="yol_mesafe_esik", esik_varsayilan=7,
        severity=Severity.YUKSEK,
    ),
    # KOL 1 (BIRINCIL) — ILISKISEL degil YEREL soru.
    # Mesafe kurali (yukarida) SILINMEDI: ayni kosumda YAN YANA doldurulur ve
    # dort karar kurali (mesafe / mesafe+kapi / zemin / zemin+kapi) AYNI ileri
    # gecis kumesinden ESLESMIS olarak puanlanir.
    # On kayit: docs/on_kayit_yaya_zemin_2026-08-25.md
    EtiketKurali(
        kod="Safe_Walkway_Violation",
        slot="yaya_zemin",
        # METIN OLCULEN SEYI ANLATIR: olculen sey ayagin altindaki YUZEYDIR.
        sablon=("Yaya yolu ihlali: kişi işaretli yaya yolunun dışında, "
                "boyasız beton zeminde yürüyor"),
        ihlal_degeri="GRI_BETON",
        severity=Severity.YUKSEK,
        # KOL 2 (IKINCIL) — CAPRAZ ON KOSUL.
        # Ayni kamerada (kamera 9) yol ihlali, pano ve yetkisiz mudahale
        # klipleriyle karisiyordu; gorus muhafizi bunlari AYIRAMIYOR cunku
        # yol cizgisi o kliplerde de gorunur. Ayirt edici sey kisinin
        # KONUMU: pano/yetkisiz kliplerinde kisi makinenin BASINDA DURUR.
        # Ek VLM cagrisi YOK — bu slot zaten dolduruluyor.
        on_slot="makine_basinda_kisi", on_asgari=0, on_azami=0,
    ),
    EtiketKurali(
        kod="Unauthorized_Intervention",
        slot="makine_basinda_yelek",
        sablon=("Yetkisiz müdahale: makineye müdahale eden kişide "
                "reflektif yelek yok"),
        ihlal_degeri="YOK",
        kategori=EventCategory.YETKISIZ_ERISIM,
        severity=Severity.YUKSEK,
        # ON KOSUL: makinenin onunde EN AZ 1 kisi olmali. Olculdu — bu kapi
        # olmadan kural FORKLIFT kamerasinda da atesleniyordu (orada ne pano
        # ne kisi var; model yine de "yelek YOK" diyordu).
        on_slot="makine_basinda_kisi", on_asgari=1,
        on_bayrak_alani="yelek_on_kosul",
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
