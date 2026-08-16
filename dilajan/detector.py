"""Hafif uzman nesne dedektoru (YOLO) - heterojen ensemble / kanit enjeksiyonu.

VLM'in tek basina cikaramadigi GROUNDED nesne bilgisini (kisi/arac sayisi vb.) saglar.
Bu kanit, perceive describe adimina enjekte edilir ("Nesne dedektoru raporu: kisi x3, araba x1").
Kucuk model (yolo11n ~6MB) 7B vLLM ile ayni GPU'ya rahat sigar.
"""
from __future__ import annotations

import io
from collections import Counter
from typing import List, Optional, Sequence, Tuple

from PIL import Image

# COCO sinifi -> Turkce (gozetim icin ilgili alt kume; digerleri Ingilizce birakilir)
_TR = {
    "person": "kişi", "bicycle": "bisiklet", "car": "araba", "motorcycle": "motosiklet",
    "bus": "otobüs", "truck": "kamyon", "train": "tren", "boat": "tekne",
    "backpack": "sırt çantası", "handbag": "el çantası", "suitcase": "valiz",
    "knife": "bıçak", "baseball bat": "sopa", "cell phone": "telefon", "fire hydrant": "yangın musluğu",
}

_model = None


def _get_model():
    global _model
    if _model is None:
        from ultralytics import YOLO
        _model = YOLO("yolo11n.pt")  # ilk kullanimda ~6MB indirilir
    return _model


def detect_segment(frames: Sequence[Tuple[str, bytes]], conf: float = 0.35) -> str:
    """Segment karelerindeki nesneleri tespit eder; azami eszamanli sayilarla Turkce ozet doner.
    Hata olursa bos string (toleransli)."""
    try:
        model = _get_model()
        imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in frames]
        results = model.predict(imgs, conf=conf, verbose=False, device="cuda")
        peak: Counter = Counter()
        for r in results:
            names = r.names
            per_frame: Counter = Counter()
            for c in r.boxes.cls.tolist():
                per_frame[names[int(c)]] += 1
            for cls, n in per_frame.items():
                peak[cls] = max(peak[cls], n)  # karelerdeki azami eszamanli varlik
        if not peak:
            return ""
        # en cok 6 sinif, sayiya gore
        parts = [f"{_TR.get(c, c)} x{n}" for c, n in peak.most_common(6)]
        return "Nesne dedektörü (azami eşzamanlı): " + ", ".join(parts)
    except Exception:
        return ""


def persons_present(frames: Sequence[Tuple[str, bytes]], conf: float = 0.35):
    """Segmentte KİŞİ (COCO 0) var mı? None=belirlenemedi (YOLO hata / hiç nesne yok) -> FAIL-OPEN (VLM korunur);
    True=kişi tespit edildi; False=nesne(ler) bulundu ama kişi yok (kişi-merkezli iddia fiziksel olarak şüpheli)."""
    try:
        model = _get_model()
        imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in frames]
        results = model.predict(imgs, conf=conf, verbose=False, device="cuda")
        any_obj = False
        for r in results:
            cls = r.boxes.cls.tolist()
            if cls:
                any_obj = True
            if any(int(c) == 0 for c in cls):
                return True
        return False if any_obj else None  # nesne var/kişi yok -> False; hiç nesne yok -> None (abstain)
    except Exception:
        return None


_pose_model = None


def _get_pose_model():
    global _pose_model
    if _pose_model is None:
        from ultralytics import YOLO
        _pose_model = YOLO("yolo11n-pose.pt")  # ilk kullanimda ~6MB
    return _pose_model


def verify_fallen(frames: Sequence[Tuple[str, bytes]], kp_conf: float = 0.5,
                  conf: float = 0.35) -> Tuple[str, str]:
    """VLM'in 'kisi yere dusmus/hareketsiz' iddiasini POZ ile dogrular (dusme vs comelme/egilme).

    Literatur esikleri (PMC7729773 / ACM 3478027): torso dikeyden <30° = DIK (comelme/egilme/oturma,
    DUSME DEGIL); >50° veya (aspect w/h>1 ve spine-ratio<1.2) = YATAY/dusmus. COCO-17: omuz 5,6 / kalca 11,12.
    Donus: ('CONFIRM'|'REJECT'|'ABSTAIN', not). FAIL-SAFE: poz guvenilmezse ABSTAIN (VLM iddiasi korunur).
    REJECT = kisi DIK -> sahte 'dusmus kisi'; severity DUSURULUR (silinmez)."""
    try:
        import numpy as np
        model = _get_pose_model()
        imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in frames]
        results = model.predict(imgs, conf=conf, verbose=False, device="cuda")
        votes = []  # True=dusmus(yatay), False=dik(ADL)
        for r in results:
            kpts = getattr(r, "keypoints", None)
            if kpts is None or kpts.xy is None or len(kpts.xy) == 0:
                continue
            xy = kpts.xy.cpu().numpy()
            cfn = kpts.conf.cpu().numpy() if kpts.conf is not None else None
            # en yuksek keypoint-guvenli kisiyi sec
            bi, bs = -1, -1.0
            for i in range(xy.shape[0]):
                s = float(cfn[i].mean()) if cfn is not None else 1.0
                if s > bs:
                    bs, bi = s, i
            if bi < 0:
                continue
            kp = xy[bi]
            c = cfn[bi] if cfn is not None else np.ones(17)
            if not all(c[j] >= kp_conf for j in (5, 6, 11, 12)):
                continue  # omuz/kalca net degil -> bu kareyi atla (abstain'e katki)
            sh = (kp[5] + kp[6]) / 2.0
            hp = (kp[11] + kp[12]) / 2.0
            v = hp - sh
            ang = float(np.degrees(np.arctan2(abs(v[0]), abs(v[1]))))  # 0=dik, 90=yatay
            pts = kp[c >= kp_conf]
            if len(pts) >= 3:
                w = float(pts[:, 0].max() - pts[:, 0].min())
                h = float(pts[:, 1].max() - pts[:, 1].min())
                ar = w / max(h, 1e-6)
            else:
                ar = 0.0
            sr = float(np.linalg.norm(v)) / max(float(np.linalg.norm(kp[5] - kp[6])), 1e-6)
            if ang < 30.0:
                votes.append(False)                      # DIK = comelme/egilme/oturma
            elif ang > 50.0 or (ar > 1.0 and sr < 1.2):
                votes.append(True)                       # YATAY = dusmus
            # 30-50° belirsiz -> sayma
        n_fall = sum(1 for v in votes if v)   # yatay/dusmus kare sayisi
        n_up = len(votes) - n_fall            # dik kare sayisi
        if len(votes) < max(2, int(0.4 * len(frames))):
            return "ABSTAIN", "poz güvenilmez (omuz/kalça net değil veya kişi yok)"
        # Temporal: dusme = bir noktada YATAY poz olur (dustukten sonra); comelme/egilme HIC yatay olmaz.
        if n_fall >= 2:
            return "CONFIRM", f"{n_fall} karede yatay/düşmüş poz -> düşme doğrulandı"
        # REJECT yalniz SUREKLI-dik (comelme/egilme uzun sure): cok kare DIK + HIC yatay yok.
        # Konservatif esik (n_up>=6) gercek dusmeleri korur (kisa/gecisli -> ABSTAIN -> VLM korunur).
        if n_fall == 0 and n_up >= 6:
            return "REJECT", f"{n_up} güvenilir karede SÜREKLİ DİK torso (çömelme/eğilme), hiç yatay yok -> düşme değil"
        return "ABSTAIN", f"belirsiz/yetersiz (yatay {n_fall}, dik {n_up}) -> VLM korunur"
    except Exception as e:
        return "ABSTAIN", f"poz hata: {e}"


def _region_of(cx: float, cy: float, w: float, h: float) -> str:
    """Piksel merkezini 3x3 Türkçe ızgara bölgesine eşler (graph._bbox_to_region ile tutarlı)."""
    xr = "sol" if cx < w / 3 else ("sağ" if cx > 2 * w / 3 else None)
    yr = "üst" if cy < h / 3 else ("alt" if cy > 2 * h / 3 else None)
    if xr and yr:
        return f"{yr} {xr}"
    return yr or xr or "merkez"


def detect_zone_intrusion(frames: Sequence[Tuple[str, bytes]], zones: Sequence[str],
                          conf: float = 0.35) -> dict:
    """SAVUNMA geofence: YASAK/kisitli bolgelerde KISI tespit eder (perimetre ihlali).

    VLM'in zone-reasoning'i guvenilmez oldugu icin DETERMINISTIK: YOLO ile kisi(ler)i bulur,
    bbox-merkezinden 3x3 bolge hesaplar; bolge yasak listede ise ihlal. Donus: {bolge: (MM:SS, guven)}
    (her yasak-bolge icin ILK tespit). Hata olursa bos (toleransli — yanlis ihlal uretmez)."""
    try:
        zones_n = {z.strip().lower() for z in zones if z and z.strip()}
        if not zones_n:
            return {}
        model = _get_model()
        imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in frames]
        results = model.predict(imgs, conf=conf, verbose=False, device="cuda")
        hits: dict = {}
        for fi, r in enumerate(results):
            w, h = imgs[fi].size
            for box, cls, cf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(),
                                    r.boxes.conf.tolist()):
                if int(cls) != 0:  # COCO 0 = person
                    continue
                cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                reg = _region_of(cx, cy, w, h)
                if reg.lower() in zones_n and reg not in hits:
                    hits[reg] = (frames[fi][0], round(float(cf), 2))  # ILK tespit (zaman, guven)
        return hits
    except Exception:
        return {}


# Arac COCO siniflari -> Turkce (iri/kaba-sinif -> grenli CCTV'de kisiden guvenilir tespit)
_VEHICLE_CLS = {2: "araba", 3: "motosiklet", 5: "otobüs", 7: "kamyon"}


def detect_vehicle_intrusion(frames: Sequence[Tuple[str, bytes]], zones: Sequence[str] = (),
                             conf: float = 0.35, dwell_frac: float = 0.5) -> List[dict]:
    """Arac (araba/kamyon/otobüs/motosiklet) tespiti — yetkisiz/yanlis-konumlu arac senaryosu.

    `zones` verilirse (3x3 izgara etiketleri): arac MERKEZI yasak bir bolgede ise IHLAL (perimetre/
    yangin-yolu/kapi onu araci). `zones` bos ise: segment karelerinin >= dwell_frac'inda gorulen
    DURAK (dwell) arac bilgi amacli raporlanir. Deterministik + FAIL-OPEN (hata -> []).
    Donus: list[dict] {time, region, label, conf, violation(bool)} (her (bolge,tip) icin ILK tespit)."""
    try:
        model = _get_model()
        imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in frames]
        results = model.predict(imgs, conf=conf, verbose=False, device="cuda")
        zones_n = {z.strip().lower() for z in zones if z and z.strip()}
        first: dict = {}          # (region_or_'*', label) -> (time, conf)
        frames_with_vehicle = 0
        for fi, r in enumerate(results):
            w, h = imgs[fi].size
            frame_has = False
            for box, cls, cf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
                ci = int(cls)
                if ci not in _VEHICLE_CLS:
                    continue
                frame_has = True
                cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                reg = _region_of(cx, cy, w, h)
                label = _VEHICLE_CLS[ci]
                key = ((reg, label) if zones_n else ("*", label))
                if key not in first:
                    first[key] = (frames[fi][0], round(float(cf), 2))
            if frame_has:
                frames_with_vehicle += 1
        n = len(results) or 1
        events: List[dict] = []
        if zones_n:
            for (reg, label), (t, cf) in first.items():
                if reg.lower() in zones_n:
                    events.append({"time": t, "region": reg, "label": label, "conf": cf, "violation": True})
        else:
            # bolge yok -> yalniz SUREKLI (dwell) gorulen durak araci bilgi olarak raporla (FP azalt)
            if frames_with_vehicle >= max(2, int(dwell_frac * n)):
                for (_, label), (t, cf) in first.items():
                    events.append({"time": t, "region": None, "label": label, "conf": cf, "violation": False})
        return events
    except Exception:
        return []


def crowd_stats(frames: Sequence[Tuple[str, bytes]], conf: float = 0.35,
                min_persons: int = 5) -> dict:
    """Kisi-sayimi zaman serisinden toplanma (gathering) ve ani-dagilma/panik (dispersal) tespiti.

    Deterministik: her karede COCO-kisi sayilir; zirve >= min_persons ise TOPLANMA. Zirveden sonra
    sayim yariya (<= peak//2) DUSERSE ani-dagilma/panik. FAIL-OPEN (hata -> {}).
    Donus: {peak, peak_time, gathering, dispersal, dispersal_time, counts}."""
    try:
        model = _get_model()
        imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in frames]
        results = model.predict(imgs, conf=conf, verbose=False, device="cuda")
        counts = [sum(1 for c in r.boxes.cls.tolist() if int(c) == 0) for r in results]
        if not counts:
            return {}
        peak = max(counts)
        peak_i = counts.index(peak)
        gathering = peak >= min_persons
        dispersal, dispersal_time = False, None
        if gathering:  # panik = toplanmadan sonra ani cozulme
            for j in range(peak_i + 1, len(counts)):
                if counts[j] <= max(1, peak // 2):
                    dispersal, dispersal_time = True, frames[j][0]
                    break
        return {"peak": peak, "peak_time": frames[peak_i][0], "gathering": gathering,
                "dispersal": dispersal, "dispersal_time": dispersal_time, "counts": counts}
    except Exception:
        return {}


# ===========================================================================
# D33 — KKD (BARET) DETERMINISTIK TESPITI
# ===========================================================================
# MIMARI (HANDOFF §6.2): KKD tespiti VLM isi DEGIL. Bu fonksiyonun ciktisi VLM'e
# "kanit" METNI olarak ENJEKTE EDILMEZ — olculdu: ham nesne listesini VLM'e vermek
# yanlis alarmi %0 -> %12 yukseltmisti. Desen `detect_zone_intrusion` (geofence)
# ile aynidir: dedektor KENDI karar verir, sonuc TIPLI bir olaya donusur.
#
# D33 EK KANIT: `guided_choice` ile zorunlu secim yaptirildiginda VLM, acik/kapali
# pano kapagi sorusunda 20 klibin 20'sinde de "KAPALI" dedi (10'u gercekte ACIK).
# Ince, ikili gorsel durum bu VLM'in okuyabildigi bir sey degil; baret var/yok
# AYNI problem sinifidir -> deterministik dedektor.
#
# EGITIM: scripts/train_ppe.py (data/ppe_yolo, CC BY 4.0, 14.089 gorsel/39.082 kutu)
# SINIFLAR: 0 = baret_var, 1 = baret_yok
#
# ⚠️ ALAN FARKI: egitim verisi SANTIYE, tesisimiz URETIM. Deterministik dedektor
# icin bu fark VLM'e gore kucuktur ama SIFIR DEGILDIR.

#: ---------------------------------------------------------------------------
#: KKD KITLERI — her biri AYRI egitilmis bir dedektor
#: ---------------------------------------------------------------------------
#: NEDEN AYRI MODELLER: baret ve yelek veri setlerinin ETIKET UZAYLARI AYRIK.
#: Baret seti (keremberke, 39k kutu) yelekleri ETIKETLEMEZ. Tek modelde
#: birlestirilseydi, baret setindeki YELEKLI bir isci "etiketsiz" kalir ve modele
#: "burada yelek YOK" diye ogretilirdi -> yelek sinifi icin SISTEMATIK
#: yanlis-negatif. Iki cikarim klip basina ~2.2 ms; K4 butcesinde (klip basina
#: ~20 sn) ihmal edilebilir.
#:
#: D35 GORSEL DENETIM: hedef tesiste isciler BARET TAKMIYOR, hi-vis YELEK giyiyor
#: -> bu dagitim icin ANLAMLI KIT "yelek"tir. "baret" santiye senaryosu icin durur.
KKD_KITLERI = {
    "baret": {
        "agirlik": "yolo11n-ppe.pt",
        "var": "baret_var", "yok": "baret_yok",
        "olay": "baret takmayan personel",
        "uret": "python scripts/train_ppe.py --profil baret",
        # test mAP50 0,934 · baret_yok P 0,893 / R 0,891 (39.082 kutu ile egitildi)
        "dagitima_hazir": True,
        "olcum": "test mAP50 0,934 · baret_yok P 0,893 / R 0,891",
    },
    "yelek": {
        "agirlik": "yolo11n-yelek.pt",
        "var": "yelek_var", "yok": "yelek_yok",
        "olay": "hi-vis yelek giymeyen personel",
        "uret": "python scripts/train_ppe.py --profil yelek",
        # ⛔ DAGITIMA HAZIR DEGIL — OLCULDU (scripts/yelek_esik_tara.py):
        # Kullanilabilir recall'da precision YETERSIZ. Esik taramasi (test bolumu):
        #   conf 0,45 -> P 0,630 / R 0,590
        #   conf 0,65 -> P 0,721 / R 0,508
        #   conf 0,85 -> P 1,000 / R 0,049   (ihlallerin %5'i — ise yaramaz)
        # Kabul olcutu IKI TARAFLI (P>=0,85 VE R>=0,50); hicbir esik saglamiyor.
        # SEBEP: yalnizca 741 egitim kutusu (baret dedektorunde 9.797 vardi).
        # Agirlik ve veri SILINMEDI — daha cok veri bulununca yeniden egitilecek.
        "dagitima_hazir": False,
        "olcum": ("test mAP50 0,678 · yelek_yok P 0,535 / R 0,661 — "
                  "kullanilabilir recall'da precision YETERSIZ"),
    },
}

#: Geriye uyumluluk: eski adlar (tests/test_ppe.py ve mevcut cagrilar bunlari kullanir)
PPE_AGIRLIK = KKD_KITLERI["baret"]["agirlik"]
PPE_SINIF_BEKLENEN = {0: "baret_var", 1: "baret_yok"}

_kkd_modeller: dict = {}
_kkd_uyarildi: set = set()


def _kit(kit: str) -> dict:
    k = KKD_KITLERI.get(kit)
    if k is None:
        raise KeyError(f"bilinmeyen KKD kiti: {kit!r} (gecerli: {sorted(KKD_KITLERI)})")
    return k


def _get_kkd_model(kit: str = "baret"):
    """Kit modelini yukler. Agirlik yoksa None (FAIL-OPEN — o kit devre disi)."""
    if kit in _kkd_modeller:
        return _kkd_modeller[kit]
    import os as _os
    k = _kit(kit)
    kok = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    yol = _os.path.join(kok, k["agirlik"])
    if not _os.path.exists(yol):
        if kit not in _kkd_uyarildi:
            _kkd_uyarildi.add(kit)
            print(f"[detector] KKD '{kit}' agirligi yok ({k['agirlik']}); bu kit KAPALI. "
                  f"Uretmek icin: {k['uret']}")
        return None
    from ultralytics import YOLO
    m = YOLO(yol)
    _kkd_modeller[kit] = m
    return m


def _get_ppe_model():
    """Geriye uyumlu takma ad — 'baret' kitini dondurur (mevcut testler bunu yamalar)."""
    return _get_kkd_model("baret")


def kkd_available(kit: str = "baret") -> bool:
    """Bu kitin egitilmis agirligi mevcut mu?"""
    import os as _os
    kok = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    return _os.path.exists(_os.path.join(kok, _kit(kit)["agirlik"]))


def kkd_mevcut_kitler() -> list:
    """Agirligi HAZIR olan kitler (sirali)."""
    return [k for k in sorted(KKD_KITLERI) if kkd_available(k)]


def ppe_available() -> bool:
    """Geriye uyumlu: 'baret' kiti hazir mi?"""
    return kkd_available("baret")


def _ppe_say(frames: Sequence[Tuple[str, bytes]], conf: float,
             kit: str = "baret") -> Optional[dict]:
    """Kit modelini TEK GECISTE calistirir ve sayimlari dondurur.

    `detect_ppe_violation` ve `verify_ppe_claim` AYNI sayimlari kullanir; ayri ayri
    predict cagirmak K4 gecikme butcesini bosa harcardi (2x YOLO cikarimi).

    Donus: {ihlalli_kare, n_ihlal_kutu, n_baretli, ilk} veya None (agirlik yok /
    beklenmeyen sinif adlari / hata -> FAIL-OPEN).
    NOT: `n_baretli` alan adi geriye uyumluluk icin korundu; anlami "KKD'si OLAN
    kisi sayisi" (yelek kitinde yelekli).
    """
    k = _kit(kit)
    model = _get_kkd_model(kit)
    if model is None:
        return None
    imgs = [Image.open(io.BytesIO(j)).convert("RGB") for _, j in frames]
    results = model.predict(imgs, conf=conf, verbose=False, device="cuda")

    # Sinif indeksini ADA gore coz — agirlik degisirse indeks kaymasina karsi.
    adlar = getattr(model, "names", None) or {0: k["var"], 1: k["yok"]}
    cift = adlar.items() if isinstance(adlar, dict) else enumerate(adlar)
    cift = list(cift)
    yok_idx = {i for i, ad in cift if str(ad) == k["yok"]}
    var_idx = {i for i, ad in cift if str(ad) == k["var"]}
    if not yok_idx:                          # beklenmeyen agirlik -> karar VERME
        return None

    ihlalli_kare = 0
    n_ihlal_kutu = n_baretli = 0
    ilk: Optional[dict] = None
    for fi, r in enumerate(results):
        w, h = imgs[fi].size
        kare_ihlal = False
        for box, cls, cf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(),
                                r.boxes.conf.tolist()):
            ci = int(cls)
            if ci in var_idx:
                n_baretli += 1
            elif ci in yok_idx:
                kare_ihlal = True
                n_ihlal_kutu += 1
                if ilk is None:
                    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                    ilk = {"time": frames[fi][0], "region": _region_of(cx, cy, w, h),
                           "conf": round(float(cf), 2)}
        if kare_ihlal:
            ihlalli_kare += 1
    return {"ihlalli_kare": ihlalli_kare, "n_ihlal_kutu": n_ihlal_kutu,
            "n_baretli": n_baretli, "ilk": ilk}


def detect_ppe_violation(frames: Sequence[Tuple[str, bytes]], conf: float = 0.45,
                         min_kare: int = 2, kit: str = "baret") -> Optional[dict]:
    """BARETSIZ kafa tespiti — deterministik KKD ihlali.

    KARAR KURALI (FP'ye karsi bilerek muhafazakar — yanlis alarm en pahali hatadir):
      * Bir kare "ihlalli" sayilir: o karede `baret_yok` kutusu var.
      * Segment ihlal sayilir: ihlalli kare sayisi >= `min_kare`.
        TEK kare yetmez — gecici yanlis tespitler (kafa donusu, bulaniklik) elenir.

    Donus: ihlal varsa {time, region, conf, n_kare, n_ihlal_kutu, n_baretli},
    yoksa None. Agirlik yok / hata / kutu yok -> None (FAIL-OPEN, K3).

    NOT: `n_baretli` bilgi amaclidir — sahnede baretli kisiler de olabilir; ihlal
    kararini DEGISTIRMEZ (bir kisinin baretli olmasi digerinin baretsizligini aklamaz).
    """
    try:
        s = _ppe_say(frames, conf, kit=kit)
        if not s or s["ihlalli_kare"] < min_kare or s["ilk"] is None:
            return None
        return {**s["ilk"], "n_kare": s["ihlalli_kare"], "kit": kit,
                "n_ihlal_kutu": s["n_ihlal_kutu"], "n_baretli": s["n_baretli"]}
    except Exception:
        return None                          # FAIL-OPEN (K3)


def verify_ppe_claim(frames: Sequence[Tuple[str, bytes]], conf: float = 0.45,
                     kit: str = "baret") -> Tuple[str, str]:
    """VLM'in "baret takmiyor/KKD ihlali" iddiasini dedektorle dogrular.

    `verify_fallen` ile AYNI sozlesme: ('CONFIRM'|'REJECT'|'ABSTAIN', not).
      CONFIRM : baretsiz kafa bulundu -> iddia destekleniyor
      REJECT  : GUVENILIR bicimde yalnizca BARETLI kafalar var -> iddia supheli,
                severity DUSURULUR (silinmez)
      ABSTAIN : kafa bulunamadi / agirlik yok / hata -> VLM iddiasi KORUNUR

    REJECT esigi bilerek YUKSEK (>=3 baretli kutu ve HIC baretsiz yok): gercek
    ihlalleri yanlislikla elemektense kararsiz kalmak yeglenir.
    """
    try:
        # TEK GECIS: hem ihlal karari hem KKD'li sayimi ayni cikarimdan gelir (K4).
        s = _ppe_say(frames, conf, kit=kit)
        if s is None:
            return "ABSTAIN", "KKD ağırlığı yok veya beklenmeyen sınıf adları"
        ad = _kit(kit)["olay"].split()[0]     # "baret" / "hi-vis"
        if s["ihlalli_kare"] >= 1 and s["ilk"] is not None:
            return "CONFIRM", (f"{s['ihlalli_kare']} karede {ad}siz personel "
                               f"(güven {s['ilk']['conf']}) -> KKD ihlali doğrulandı")
        n_var = s["n_baretli"]
        if n_var >= 3:
            return "REJECT", (f"{n_var} adet {ad}li personel tespit edildi, ihlal YOK "
                              "-> KKD ihlali iddiası şüpheli")
        return "ABSTAIN", f"yeterli tespit yok ({ad}li {n_var}) -> VLM korunur"
    except Exception as e:  # noqa: BLE001
        return "ABSTAIN", f"KKD doğrulama hatası: {e}"


def available() -> bool:
    try:
        import ultralytics  # noqa: F401
        return True
    except Exception:
        return False
