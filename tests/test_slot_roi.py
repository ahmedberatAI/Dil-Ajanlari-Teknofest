"""D44 — SLOT BASINA ROI testi (model cagrisi YOK, sahte istemci).

OLCULEN GEREKCE: pano sorusu TAM KAREDE dejenere (n=24, MCC -0,192);
ayni soru %8 payli KIRPILMIS ROI'de MCC +0,920. Yani belirleyici olan
modelin yetenegi degil, sorulan bolgenin karedeki PAYI.

Bu test MEKANIZMAYI dogrular: ayni ROI'yi paylasan slotlar TEK video
uretir (K4 — cagri sayisi artmaz), farkli ROI'ler AYRI video alir,
ROI bos iken davranis eski haliyle BIREBIR aynidir (K2).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dilajan import gozlem as G

g = k = 0
def c(ad, kosul):
    global g, k
    if kosul: g += 1; print("  ok  ", ad)
    else: k += 1; print("  FAIL", ad)

class SahteOturum:
    hazir = True
    def __init__(self, etiket): self.etiket = etiket; self.istemci = None
    def sor(self, soru, guided_choice=None, **kw):
        # ROI etiketini cevaba gomeriz -> hangi videodan geldigi izlenebilir
        return CEVAP.get((self.etiket, soru), "1")

class SahteIstemci:
    def __init__(self): self.acilan = []
    def gorev(self, g_): return self
    def video_oturumu(self, video, system=""):
        self.acilan.append(video)
        return SahteOturum(video)

class Ayar:
    panel_roi_vlm = "0.0,0.4,0.3,0.8"

uretilen = []
def video_uret(roi, kapsam="segment", fps=None):
    # `fps` SLOTA OZGU kare hizidir (ROI ve kapsam ile ayni desen); muhafizsiz
    # ve fps'siz slotlarda None gelir.
    uretilen.append((roi, kapsam))
    return f"VIDEO[{roi}|{kapsam}|{fps}]"

CEVAP = {}

print("=== ROI COZUMU ===")
ay = Ayar()
c("ROI alani tanimli slot ayardan okur",
  G.roi_coz(G.SLOT_PANO_KOYULUK, ay) == "0.0,0.4,0.3,0.8")
c("ROI alani OLMAYAN slot tam kare ister",
  G.roi_coz(G.SLOT_CATAL_KASA, ay) == "")
class Bos: panel_roi_vlm = ""
c("ayar BOS ise tam kare (K2 — varsayilan davranis)",
  G.roi_coz(G.SLOT_PANO_KOYULUK, Bos()) == "")

print()
print("=== GRUPLAMA: ayni ROI TEK video ===")
uretilen.clear(); ist = SahteIstemci()
# AYNI ROI ve AYNI KAPSAM: tek grup, tek video (kapsam ayrimi icin asagidaki
# "SLOT KAPSAMI" bolumune bakin).
G.slotlari_doldur_bolgeli(ist, [G.SLOT_MAKINE_KISI, G.SLOT_YELEK], video_uret, ay)
c("iki tam-kare slotu TEK video uretir", uretilen == [("", "klip")])
c("TEK oturum acilir (K4: cagri sayisi artmaz)", len(ist.acilan) == 1)

uretilen.clear(); ist2 = SahteIstemci()
G.slotlari_doldur_bolgeli(ist2, [G.SLOT_CATAL_KASA, G.SLOT_PANO_KOYULUK], video_uret, ay)
c("farkli ROI -> IKI video",
  sorted(uretilen) == sorted([("", "segment"), ("0.0,0.4,0.3,0.8", "segment")]))
c("farkli ROI -> IKI oturum", len(ist2.acilan) == 2)

uretilen.clear(); ist3 = SahteIstemci()
G.slotlari_doldur_bolgeli(ist3, [G.SLOT_CATAL_KASA, G.SLOT_PANO_KOYULUK], video_uret, Bos())
c("ROI ayari BOS -> hepsi TEK videoda (eski davranis)", uretilen == [("", "segment")])

print()
print("=== K3 FAIL-OPEN: bir ROI grubu coktugunde digerleri surer ===")
class CokenIstemci(SahteIstemci):
    def video_oturumu(self, video, system=""):
        if "0.0,0.4" in str(video):
            raise RuntimeError("kirpma basarisiz")
        return SahteOturum(video)
kayit = G.slotlari_doldur_bolgeli(CokenIstemci(),
        [G.SLOT_CATAL_KASA, G.SLOT_PANO_KOYULUK], video_uret, ay)
c("coken grup HATA kaydeder", "pano_koyuluk_0_10" in kayit.hatalar)
c("saglam grup DEGER uretir", "catal_kasa_sayisi" in kayit.degerler)
c("kural motoru coken slotu SESSIZ gecer",
  kayit.al("pano_koyuluk_0_10") is None)

print()
print("=== PANO SLOTU ROI ALANINA BAGLI ===")
c("SLOT_PANO_KOYULUK panel_roi_vlm okur",
  G.SLOT_PANO_KOYULUK.roi_alani == "panel_roi_vlm")
c("forklift slotu ROI istemez", G.SLOT_CATAL_KASA.roi_alani == "")
from tests.taban import sinif_varsayilani
c("panel_roi_vlm varsayilani BOS (SINIF varsayilani, .env DEGIL)",
  sinif_varsayilani("panel_roi_vlm") == "")

print()
print("=== SLOT KAPSAMI (segment / klip) ===")
c("yelek slotu KLIP kapsamli", G.SLOT_YELEK.kapsam == "klip")
c("on kosul slotu KLIP kapsamli", G.SLOT_MAKINE_KISI.kapsam == "klip")
c("forklift slotu SEGMENT kapsamli", G.SLOT_CATAL_KASA.kapsam == "segment")
c("pano slotu SEGMENT kapsamli", G.SLOT_PANO_KOYULUK.kapsam == "segment")

uretilen.clear(); ist4 = SahteIstemci()
G.slotlari_doldur_bolgeli(ist4, [G.SLOT_CATAL_KASA, G.SLOT_MAKINE_KISI], video_uret, ay)
c("ayni ROI ama FARKLI kapsam -> IKI video",
  sorted(uretilen) == sorted([("", "segment"), ("", "klip")]))
c("iki AYRI oturum acilir", len(ist4.acilan) == 2)

uretilen.clear(); ist5 = SahteIstemci()
G.slotlari_doldur_bolgeli(ist5, [G.SLOT_MAKINE_KISI, G.SLOT_YELEK], video_uret, ay)
c("ayni kapsam+ROI -> TEK video (K4)", uretilen == [("", "klip")])

print()
print("=== SLOT COZUNURLUGU (ince duman / uzak temas) ===")
uretilen4 = []
def video_uret4(roi, kapsam="segment", fps=None, max_side=1280):
    uretilen4.append((roi, kapsam, fps, max_side))
    return f"VIDEO[{roi}|{kapsam}|{fps}|{max_side}]"
ist6 = SahteIstemci()
G.slotlari_doldur_bolgeli(
    ist6,
    [G.SLOT_DEPO_YANGIN, G.SLOT_DEPO_FORKLIFT_CARPISMA_DOGRULAMA,
     G.SLOT_DEPO_FORKLIFT_CARPISMA,
     G.SLOT_DEPO_FORKLIFT_KISI],
    video_uret4, ay)
c("dort genel depo slotu 1920 spekinde TEK video paylasir",
  uretilen4 == [("", "segment", None, 1920)] and len(ist6.acilan) == 1)

uretilen4.clear(); ist7 = SahteIstemci()
G.slotlari_doldur_bolgeli(
    ist7, [G.SLOT_CATAL_KASA, G.SLOT_DEPO_YANGIN], video_uret4, ay)
c("1280 ve 1920 spekleri sessizce ayni oturuma karismaz",
  sorted(x[3] for x in uretilen4) == [1280, 1920] and len(ist7.acilan) == 2)

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
