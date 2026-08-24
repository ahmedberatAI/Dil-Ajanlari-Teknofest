"""GOZLEM DUZLEMI — yapilandirilmis algi (D43).

NEDEN VAR — OLCULDU, TAHMIN DEGIL (2026-08-24, n=20 guvensiz klip)
-------------------------------------------------------------------
Mevcut boru hatti ISG ihlallerini KACIRIYORDU ve kaybin nerede oldugu olculdu:

    asama                                          sonuc
    ---------------------------------------------  -------------------
    K1  serbest betimleme ihlali IDDIA ETTI          0/20   <- kayip BURADA basliyor
    K1' betimleme dogru NESNEYI en azindan andi      7/20   (yelek 0/5, pano 0/5)
    K2  bilgi ZORLA verilirse olaya gecen           11/20   (%45 kayip)
    K3  olaya gecenden eslestiricinin yakaladigi     4/11   (%64 kayip)
    UCTAN UCA                                        0/20

AMA AYNI MODEL, AYNI KLIPLER, AYNI VIDEO — ISLEMSEL soru soruldugunda:
    kacisli  : 12/20 dogru karar (yanlis pozitif 2/10)
    kacissiz : 20/20 dogru karar (yanlis pozitif 6/10)

Yani bilgi algi aninda MODELDE VAR. Serbest betimleme promptu onu HIC ISTEMIYOR
ve varsayilan cikti "SAPMA YOK" (19/20). Darbogaz MODEL DEGIL, MIMARI.

TASARIM
-------
Iki duzlem AYNI `events` listesinde birlesir:

  ANLATI DUZLEMI (mevcut, DEGISMIYOR): video -> betimle -> cikar -> Event
      Acik dunya olaylari (yangin/duman/kavga/dusme). Olculen %96 recall'i
      koruyan tek yol; KALDIRILMIYOR. Urettigi olay `isg_kod` TASIMAZ.

  GOZLEM DUZLEMI (bu modul): slot doldur -> KURAL MOTORU -> Event(sablon)
      Karar dongusunde MODEL YOKTUR. Model yalnizca KAPALI cevap uzayinda bir
      SLOT doldurur (sayi/etiket); hukmu deterministik kural verir.

BU NEDEN K2/K3 KAYBINI YAPISAL OLARAK SIFIRLAR
----------------------------------------------
K2 (cikarim) kalkar: cevap zaten yapilandirilmis, "metinden olay cikarma" adimi yok.
K3 (sozcuksel kapi) kalkar: `Event.event` metni MODEL NESRI DEGIL, sinif
tanimindan turemis SABLONUN render'idir. Olculen uc kacirma mekanizmasi da
tek hamlede yok olur:
  (a) es anlamli sozcuk  — model "gorus hattini kapatiyor" der, kalip "gorusu engel"  (5/5 forklift boyle kacti)
  (b) Turkce unsuz yumusamasi — model "seridinin", kalip "serit"
  (c) sozluk-tanim ayrismasi

LISANS: saf Python + pydantic. Model cagrisi `llm_client` uzerinden.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence

# ---------------------------------------------------------------------------
# SLOT TANIMLARI
# ---------------------------------------------------------------------------
# Her slot: KAPALI cevap uzayi + hangi aliasa gidecegi + soru metni.
# Model secimi SLOT SEVIYESINDEDIR, boru hatti seviyesinde DEGIL — cunku
# modeller TERS UZMANLASMIS (olculdu):
#   llm-large : sayma/olcek iyi  · kisi/oznitelik sorularinda %94 "GORUNMUYOR"
#   vlm       : kisi/oznitelik iyi · saymada en zayifi (FP=13)


# GOZLEM DUZLEMININ SISTEM PROMPTU — MINIMAL, KASITLI.
#
# OLCULDU (2x2 faktoriyel, ayni model/cozunurluk/klip/bayt, yelek slotu n=35):
#     SYSTEM_PERSONA + kacis secenegi : MCC +0,000  (kacis %86, DEJENERE)
#     sistem promptu YOK              : MCC +0,775
#     sistem YOK + kacis YOK          : MCC +0,885
# Bizim `SYSTEM_PERSONA`'miz genel anlati icin yazilmis ve CEKIMSERLIGE davet
# eden kurallar tasiyor ("emin degilsen 'belirsiz' de", "VARSAYMA"). O kurallar
# ANLATI duzleminde DOGRU (halusinasyonu kesiyor) ama GOZLEM duzleminde modeli
# olcum yapmaktan alikoyuyor.
#
# Bu yuzden gozlem duzlemi KENDI minimal promptunu kullanir. Anlati duzlemi
# SYSTEM_PERSONA ile calismaya DEVAM EDER — degistirilmedi.
GOZLEM_SISTEM = ("Sen bir endustriyel kamera olcum sistemisin. Sana sorulan sey "
                 "bir OLCUMDUR. Gordugun kareye bakarak istenen sayiyi veya "
                 "etiketi ver.")


class Slot:
    """Tek bir yapilandirilmis gozlem alani."""

    def __init__(self, ad: str, soru: str, secenekler: Sequence[str],
                 gorev: str, coz: Callable[[str], Optional[object]],
                 aciklama: str = "", roi_alani: str = "",
                 kapsam: str = "segment",
                 dislanan_gorus_alani: str = "", gorus_esik_alani: str = ""):
        self.ad = ad
        self.soru = soru
        self.secenekler = list(secenekler)
        self.gorev = gorev          # llm_client.gorev(...) -> alias
        self.coz = coz              # ham cevap -> tipli deger (None = cozulemedi)
        self.aciklama = aciklama
        # ROI ALANI — bu slotun sorusu KARENIN TAMAMINA degil, ayardan okunan
        # bir bolgeye sorulur. Bos ise tam kare kullanilir.
        # OLCULDU (n=24): pano sorusu TAM KAREDE dejenere (MCC -0,192),
        # ayni soru KIRPILMIS ROI'de MCC +0,920. Belirleyici olan modelin
        # yetenegi degil, sorulan bolgenin karedeki PAYI.
        self.roi_alani = roi_alani
        # KAPSAM — sorunun ZAMAN olcegi. OLCULDU (149 klip, iki kol):
        #   "segment": soru segmentin KENDI penceresine sorulur.
        #       Forklift asiri yuk BIR ANA aittir; pencere daraltilinca
        #       MCC +0,770 -> +0,851 ve kacirma 1 -> 0.
        #   "klip"   : soru TUM klibe sorulur, yalnizca ILK segmentte.
        #       "Makinenin basinda kisi var mi" bir AN olcumu degil, klip
        #       duzeyinde bir ON KOSULDUR; pencere daraltilinca kisi
        #       goruntunun bir bolumunde kaliyor ve kapi yanlis kapaniyordu
        #       (MCC +0,689 -> +0,527).
        # Yani kapsam bir performans ayari degil, sorunun ANLAMININ parcasi.
        self.kapsam = kapsam
        # GORUS MUHAFIZI — slot YALNIZCA dogru kamerada sorulur.
        # `dislanan_gorus_alani`: ayardan okunan REFERANS imza; sahnenin
        # benzerligi esigi ASARSA slot HIC sorulmaz (o kamera bu soru icin
        # gecersizdir).
        #
        # NEDEN SADECE BAZI SLOTLARDA: gorus imzasi bazi sinif ciftlerinde
        # ETIKETLE korele. Olculdu (96 klip, cift ICINDE |MCC|):
        #     yol   cifti 0,385 · pano cifti 0,275  -> muhafiz GUVENLI
        #     yetki cifti 0,833                     -> muhafiz YASAK
        # Yetkisiz mudahale sinifinda muhafiz kullanmak, reddedilen geofence
        # yaklasiminin ta kendisi olurdu: skor bilgiden degil kameradan gelir.
        self.dislanan_gorus_alani = dislanan_gorus_alani
        self.gorus_esik_alani = gorus_esik_alani

    def __repr__(self) -> str:      # pragma: no cover
        return f"<Slot {self.ad} -> {self.gorev}>"


def _sayi(c: str) -> Optional[int]:
    c = (c or "").strip().upper()
    if not c or c.startswith("GORUNMUYOR") or c.startswith("__HATA__"):
        return None
    if c.endswith("+"):
        c = c[:-1]
    try:
        return int(c)
    except ValueError:
        return None


def _uclu(c: str) -> Optional[str]:
    """VAR / YOK / (kacis -> None)."""
    c = (c or "").strip().upper()
    if c in ("VAR", "YOK"):
        return c
    return None


# --- SLOT KATALOGU ---------------------------------------------------------
# NOT: soru metinleri OLCULMUS metinlerdir; degistirilirse YENIDEN OLCULMELIDIR.
# "Ayirt edemiyorsan kacis kullan" gibi CEKIMSERLIGE DAVET eden cumle YOKTUR —
# olculdu: o cumle MCC'yi +0,885'ten +0,000'a dusuruyor.

SLOT_CATAL_KASA = Slot(
    ad="catal_kasa_sayisi",
    soru=("Forkliftin CATALINDA ust uste kac adet kasa/blok tasiniyor? "
          "Yalnizca sayiyi yaz."),
    secenekler=["0", "1", "2", "3", "4", "5", "6+", "GORUNMUYOR"],
    gorev="sayim",
    coz=_sayi,
    aciklama="Kaynak makale: <=2 kasa guvenli, >=3 kasa ihlal. Olculen MCC +0,762.",
)

SLOT_PANO_KOYULUK = Slot(
    ad="pano_koyuluk_0_10",
    soru=("Makinenin on yuzeyindeki elektrik/kontrol panosu bolgesi 0 ile 10 "
          "arasinda ne kadar KARANLIK? Yalnizca sayiyi yaz "
          "(0 = tamamen aydinlik duz yuzey, 10 = zifiri karanlik oyuk)."),
    secenekler=[str(i) for i in range(11)] + ["GORUNMUYOR"],
    gorev="sayim",
    coz=_sayi,
    roi_alani="panel_roi_vlm",
    aciklama=("IKILI soru ('acik mi kapali mi') AYNI modelde 34/34 'GORUNMUYOR' "
              "veriyordu; SAYISAL soru MCC +1,000. Belirleyici olan SORU BICIMI. "
              "Ayrica TAM KARE dejenere (-0,192); ROI kirpmasi sart (+0,920)."),
)

SLOT_YELEK = Slot(
    ad="makine_basinda_yelek",
    soru=("Makinenin/panonun BASINDA DURAN KISIDE yesil reflektif yelek var mi? "
          "VAR veya YOK yaz."),
    secenekler=["VAR", "YOK", "KISI_YOK", "GORUNMUYOR"],
    gorev="algi",       # -> vlm; llm-large bu soruda 47/50 kaciyor (olculdu)
    coz=_uclu,
    kapsam="klip",      # kiyafet klip boyunca DEGISMEZ; pencere daraltmak zarar

    aciklama="Kaynak makale: yesil yelek = yetkili mudahale, yeleksiz = yetkisiz.",
)


# ON-KOSUL SLOTU — kuralin KENDI on sartini olcer.
#
# NEDEN VAR (olculdu 2026-08-24): yelek slotu FORKLIFT kamerasinda da "YOK"
# donduruyordu. O goruntude ne pano ne de makine basinda kisi var; "YOK"
# cevabi yanlis degil, SORUNUN GECERSIZ oldugu yerde verilmis bir cevap.
# Sonuc: Unauthorized_Intervention'da tabandan yanlis pozitif.
#
# Modelin KACIS secenegini ("KISI_YOK") kullanmasini beklemek yerine on sarti
# AYRI ve SAYISAL bir soru yapiyoruz: sifir-sayma modelin dogal olarak verdigi
# bir cevaptir, kacis ise degildir (olculdu: kacis secenegi teklif etmek
# MCC'yi +0,885'ten +0,000'a dusuruyordu).
SLOT_MAKINE_KISI = Slot(
    ad="makine_basinda_kisi",
    soru=("Elektrik/kontrol panosunun veya makinenin ONUNDE kac kisi duruyor? "
          "Yalnizca sayiyi yaz."),
    secenekler=["0", "1", "2", "3", "4", "5+", "GORUNMUYOR"],
    gorev="algi",
    coz=_sayi,
    kapsam="klip",      # ON KOSUL klip duzeyindedir (olculdu: segment kapsami
                        # kapiyi yanlis kapatiyor, MCC +0,689 -> +0,527)
    aciklama=("Yetkisiz mudahale kuralinin ON KOSULU. 0 ise kural HIC "
              "degerlendirilmez — yelek sorusu anlamsizdir."),
)

# YAYA YOLU — OLCULEN SEY, VARSAYILAN NEDEN DEGIL.
#
# DIKKAT — SEMANTIK CEKINCE (kasitli olarak burada duruyor):
# Slot, kisinin yerdeki isaretli cizgiye UZAKLIGINI olcer. Olculen iliski su
# yonde: MESAFE KUCUK -> Safe_Walkway_Violation.
#     ayrilmis kume (n=20): IHLAL {0: 7, 5: 4} · NORMAL {7: 5, 5: 2, 3: 1, 0: 1}
# "Isaretli yolun ICINDE yurumek guvenlidir" seklindeki sezgisel okumayla bu
# TERS gorunuyor. Bu tesiste cizginin ne oldugunu (yaya yolu siniri mi, arac
# seridi kenari mi) BILMIYORUZ. Bu yuzden slot adi ve kural metni OLCULEN
# BUYUKLUGU anlatir; nedensel bir hikaye ANLATMAZ.
#
# OLCUM ZINCIRI (hicbiri silinmedi):
#   tam kare, ikili soru    : 28 klibin 27'si "DISINDA" -> DEJENERE
#   tam kare, sayim         : MCC -0,280
#   tam kare, mesafe        : MCC +0,192
#   ROI (alt yari), mesafe  : MCC +0,466  <- esik BU kumede secildi
#   AYRILMIS KUME, esik 7   : MCC +0,638 · TP11 FP4 FN0 TN5 · n=20
#   cerceveleme tabani      : MCC -0,072 (kamera acisi tek basina sinyal TASIMIYOR)
#
# Cerceveleme tabaninin dusuk olmasi onemli: bu sinifta daha once geofence
# yaklasimi REDDEDILMISTI cunku skorun tamami cerceveden geliyordu. Burada
# oyle degil.
SLOT_YAYA_CIZGI_MESAFE = Slot(
    ad="yaya_cizgi_mesafe",
    soru=("Yuruyen kisi ile yerdeki isaretli yaya yolu cizgisi arasindaki mesafe "
          "0 ile 10 arasinda ne kadar? Yalnizca sayiyi yaz "
          "(0 = tam cizginin uzerinde/icinde, 10 = yoldan cok uzakta)."),
    secenekler=[str(i) for i in range(11)] + ["GORUNMUYOR"],
    gorev="algi",
    coz=_sayi,
    roi_alani="yol_roi_vlm",
    kapsam="klip",      # olcum TUM klip uzerinde yapildi; sevk edilen = olculen
    dislanan_gorus_alani="yol_dislanan_gorus",
    gorus_esik_alani="yol_gorus_esik",
    aciklama=("Yerdeki isaretli cizgiye uzaklik. ROI kirpmasi ZORUNLU: tam "
              "karede ayni soru MCC +0,192, ROI ile +0,638 (ayrilmis kume)."),
)

SLOT_KATALOG: Dict[str, Slot] = {
    s.ad: s for s in (SLOT_CATAL_KASA, SLOT_PANO_KOYULUK, SLOT_YELEK,
                      SLOT_MAKINE_KISI, SLOT_YAYA_CIZGI_MESAFE)
}


# ---------------------------------------------------------------------------
# GOZLEM KAYDI
# ---------------------------------------------------------------------------
class GozlemKaydi:
    """Bir segment icin doldurulmus slotlar. Tipli, serbest metin YOK."""

    def __init__(self):
        self.degerler: Dict[str, object] = {}
        self.ham: Dict[str, str] = {}
        self.hatalar: Dict[str, str] = {}
        #: gorus muhafizi tarafindan ATLANAN slotlar (hata DEGIL — sahne gecersiz)
        self.atlanan: Dict[str, str] = {}

    def koy(self, slot: Slot, ham_cevap: str) -> None:
        self.ham[slot.ad] = ham_cevap
        if (ham_cevap or "").strip().upper().startswith("__HATA__"):
            self.hatalar[slot.ad] = ham_cevap
            return
        v = slot.coz(ham_cevap)
        if v is not None:
            self.degerler[slot.ad] = v

    def al(self, ad: str, varsayilan=None):
        return self.degerler.get(ad, varsayilan)

    def __bool__(self) -> bool:
        return bool(self.degerler)

    def __repr__(self) -> str:      # pragma: no cover
        return f"<GozlemKaydi {self.degerler}>"


def slotlari_doldur(oturum, slotlar: Sequence[Slot], istemci,
                    max_tokens: int = 12) -> GozlemKaydi:
    """Ayni VIDEO OTURUMU uzerinde slotlari doldurur.

    `hatirla=False` UC isi birden yapar (tasarim geregi, opsiyon degil):
      1) slotlar birbirinden BAGIMSIZ kalir (biri otekini yonlendirmez),
      2) on-ek SABIT kalir -> onbellek isabet eder,
      3) model KENDI ONCEKI METNINI OKUMAZ — literaturde belgelenen
         "akil yurutme zinciri uzadikca gorsel icerikten sapma" yolu kapanir
         (DRP, arXiv:2509.23322).

    K3 fail-open: bir slot cozulemezse ATLANIR, digerleri devam eder.
    """
    kayit = GozlemKaydi()
    if oturum is None or not getattr(oturum, "hazir", False):
        # OLCULEMEDI != IHLAL YOK. Oturum kurulamadiysa (video govde sinirini
        # asti, ffmpeg dustu, servis kapali) her slot HATA olarak isaretlenir.
        # Aksi halde kural motoru "deger yok -> sessiz" der ve olcum hucresi
        # SIFIR olur; karar-izi de "hata=[]" yazip HIC HATA OLMADIGINI iddia eder.
        neden = getattr(oturum, "hata", None) or "oturum kurulamadi"
        for s_ in slotlar:
            kayit.hatalar[s_.ad] = f"__HATA__ oturum: {neden}"
        return kayit
    asil_istemci = oturum.istemci
    try:
        for s in slotlar:
            try:
                # SLOT SEVIYESINDE MODEL SECIMI — modeller ters uzmanlasmis (olculdu):
                # sayma -> llm-large · kisi/oznitelik -> vlm.
                # .gorev() ayni HTTP baglantisini paylasir, yeni baglanti ACMAZ.
                if istemci is not None:
                    oturum.istemci = istemci.gorev(s.gorev)
                c = oturum.sor(s.soru, guided_choice=s.secenekler,
                               temperature=0.0, max_tokens=max_tokens,
                               hatirla=False)
                if c is None:
                    # `sor()` istisnayi KENDI ICINDE yutar ve None doner
                    # (llm_client.py, K3 fail-open) — bu yuzden asagidaki
                    # `except` ASLA atesLENMEZ. Nedeni oturumdan geri okuyup
                    # HATA olarak isaretlemezsek, ag/servis hatasi sessizce
                    # "cozulemedi"ye ve oradan "ihlal yok"a donusur.
                    kayit.koy(s, f"__HATA__ {getattr(oturum, 'hata', None) or 'cevap alinamadi'}")
                else:
                    kayit.koy(s, c)
            except Exception as e:
                kayit.hatalar[s.ad] = f"__HATA__ {type(e).__name__}: {e}"
    finally:
        oturum.istemci = asil_istemci      # oturumu bozmadan birak
    return kayit


def roi_coz(slot: Slot, ayar) -> str:
    """Slotun ROI dizgisini ayardan okur (alan tanimsizsa tam kare)."""
    if not getattr(slot, "roi_alani", ""):
        return ""
    return (getattr(ayar, slot.roi_alani, "") or "").strip()


def gorus_uygun_mu(slot: Slot, ayar, frames) -> bool:
    """Bu slot BU SAHNEDE sorulmali mi? (kamera gorus muhafizi)

    Muhafiz tanimli degilse HER ZAMAN True — yani muhafiz KULLANMAYAN
    slotlarin davranisi BIREBIR degismez (K2).

    Kare yoksa (or. onceden cikarilmis kare yolu) muhafiz UYGULANMAZ ve
    slot sorulur: sessizce kapatmak, olculmemis bir davranis uretmek olurdu.
    """
    ad = getattr(slot, "dislanan_gorus_alani", "")
    if not ad:
        return True
    imza = (getattr(ayar, ad, "") or "").strip()
    if not imza or not frames:
        return True
    esik_ad = getattr(slot, "gorus_esik_alani", "")
    esik = float(getattr(ayar, esik_ad, 0.708)) if esik_ad else 0.708
    try:
        from dilajan.pano import gorus_uyuyor
        # gorus_uyuyor: sahne REFERANSA benziyorsa True.
        # Referans DISLANAN kameradir -> benziyorsa slot SORULMAZ.
        return not gorus_uyuyor(frames, imza, esik)
    except Exception:
        return True                      # muhafiz cozulemedi -> engelleme (K3)


def slotlari_doldur_bolgeli(istemci, slotlar: Sequence[Slot], video_uret,
                            ayar, system: str = GOZLEM_SISTEM,
                            max_tokens: int = 12, frames=None) -> GozlemKaydi:
    """Slotlari ROI'ye GORE GRUPLAYIP doldurur.

    `video_uret(roi_str) -> bytes` her FARKLI ROI icin BIR KEZ cagrilir; ayni
    ROI'yi paylasan slotlar TEK video oturumunu paylasir. Boylece kirpma
    destegi eklenirken cagri sayisi ARTMAZ (K4).

    K3 fail-open: bir ROI grubunun videosu/oturumu kurulamazsa yalnizca O
    GRUP hata kaydeder, digerleri devam eder.
    """
    kayit = GozlemKaydi()
    # GORUS MUHAFIZI — yanlis kameradaki slotlar HIC sorulmaz (cagri da yapilmaz).
    if frames is not None:
        _atlanan = [x for x in slotlar if not gorus_uygun_mu(x, ayar, frames)]
        for x in _atlanan:
            kayit.atlanan[x.ad] = "gorus muhafizi: bu kamera bu soru icin gecersiz"
        slotlar = [x for x in slotlar if x not in _atlanan]
    # GRUPLAMA (ROI, KAPSAM) ikilisine gore: ayni bolgeyi VE ayni zaman
    # olcegini paylasan slotlar TEK video oturumunu paylasir.
    gruplar: Dict[tuple, List[Slot]] = {}
    for s in slotlar:
        gruplar.setdefault((roi_coz(s, ayar),
                            getattr(s, "kapsam", "segment")), []).append(s)
    for (roi, kapsam), grup in gruplar.items():
        try:
            oturum = istemci.video_oturumu(video_uret(roi, kapsam), system=system)
        except Exception as e:
            for s_ in grup:
                kayit.hatalar[s_.ad] = f"__HATA__ {type(e).__name__}: {e}"
            continue
        alt = slotlari_doldur(oturum, grup, istemci, max_tokens=max_tokens)
        kayit.degerler.update(alt.degerler)
        kayit.ham.update(alt.ham)
        kayit.hatalar.update(alt.hatalar)
    return kayit
