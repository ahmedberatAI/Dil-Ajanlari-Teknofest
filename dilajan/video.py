"""Video isleme: zaman damgali kare cikarma ve segmentleme (PyAV ile).

VLM'e video gondermek yerine, videoyu belirli bir hizda ornekleyip her kareyi
zaman damgasiyla etiketliyoruz. Bu yaklasim:
  - token kullanimini kontrol altinda tutar (max_frames_per_segment),
  - olaylari net zaman damgalariyla eslestirmeyi saglar,
  - uzun videolari segmentlere bolerek olceklenebilir kilar.
"""
from __future__ import annotations

import os

import io
from dataclasses import dataclass, field
from typing import List, Tuple

import av
from PIL import Image

from dilajan.config import settings
from dilajan.utils import format_timestamp

# (zaman_saniye, jpeg_bytes)
TimedFrame = Tuple[float, bytes]


@dataclass
class VideoInfo:
    path: str
    duration: float          # saniye
    fps: float
    width: int
    height: int
    sampled_frames: int = 0

    @property
    def duration_str(self) -> str:
        return format_timestamp(self.duration)


@dataclass
class Segment:
    index: int
    start: float
    end: float
    frames: List[Tuple[str, bytes]] = field(default_factory=list)  # (MM:SS, jpeg)
    # D43: gozlem duzlemi ORIJINAL videoyu ister (kareleri yeniden kodlamak degil).
    # Olculdu: kareleri 768px'te mp4'e kodlamak yelek/pano slotlarini DEJENERE
    # yapiyor; servis_videosu(orijinal, 1280) ile olculen sonuclar geri geliyor.
    kaynak_yol: str = ""

    @property
    def start_str(self) -> str:
        return format_timestamp(self.start)

    @property
    def end_str(self) -> str:
        return format_timestamp(self.end)


def _enhance_clahe(img: Image.Image) -> Image.Image:
    """Dusuk cozunurluklu/grainy CCTV icin CLAHE kontrast iyilestirmesi (LAB-L kanali)."""
    try:
        import cv2
        import numpy as np
        arr = np.asarray(img.convert("RGB"))
        lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        out = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2RGB)
        return Image.fromarray(out)
    except Exception:
        return img  # cv2 yoksa/hata olursa orijinali dondur (toleransli)


def _resize_jpeg(img: Image.Image, max_side: int, min_side: int = 0, quality: int = 88) -> bytes:
    w, h = img.size
    longest = max(w, h)
    # buyukse kucult; dusuk cozunurluklu (CCTV) kareleri buyut
    if longest > max_side:
        scale = max_side / longest
    elif min_side and longest < min_side:
        scale = min_side / longest
    else:
        scale = 1.0
    if scale != 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    if img.mode != "RGB":
        img = img.convert("RGB")
    if settings.frame_enhance:
        img = _enhance_clahe(img)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def extract_timestamped_frames(
    path: str,
    fps_sample: float | None = None,
    max_side: int | None = None,
) -> Tuple[List[TimedFrame], VideoInfo]:
    """Videoyu `fps_sample` hizinda ornekler; (zaman, jpeg) listesi + VideoInfo döner."""
    fps_sample = fps_sample or settings.fps_sample
    max_side = max_side or settings.frame_max_side

    container = av.open(path)
    stream = container.streams.video[0]
    stream.thread_type = "AUTO"

    tb = stream.time_base
    fps = float(stream.average_rate) if stream.average_rate else 0.0
    if stream.duration is not None and tb is not None:
        duration = float(stream.duration * tb)
    elif container.duration is not None:
        duration = container.duration / av.time_base
    else:
        duration = 0.0

    interval = 1.0 / fps_sample
    next_t = 0.0
    frames: List[TimedFrame] = []
    width = height = 0

    for frame in container.decode(stream):
        t = float(frame.pts * tb) if frame.pts is not None else (frames[-1][0] + interval if frames else 0.0)
        if t + 1e-6 >= next_t:
            img = frame.to_image()
            width, height = img.size
            frames.append((t, _resize_jpeg(img, max_side, settings.frame_min_side)))
            next_t = t + interval

    container.close()
    if duration <= 0.0 and frames:
        duration = frames[-1][0]

    info = VideoInfo(
        path=path, duration=duration, fps=fps,
        width=width, height=height, sampled_frames=len(frames),
    )
    return frames, info


def timedframes_from_bgr(
    bgr_frames: List,
    timestamps: List[float],
    max_side: int | None = None,
    min_side: int | None = None,
) -> List[TimedFrame]:
    """cv2 (BGR) kare dizisini (zaman, jpeg) TimedFrame listesine cevirir — DECODE-ONCE.

    Canli akista kareler zaten decode edilmis olur; bunlari gecici bir mp4'e yazip PyAV ile
    YENIDEN decode etmek yerine dogrudan JPEG'e kodlariz (mp4 yaz->yeniden-oku gidis-donusu yok).
    _resize_jpeg ile ayni olcek/kalite (analiz akisi degismez)."""
    import numpy as np
    max_side = max_side or settings.frame_max_side
    min_side = settings.frame_min_side if min_side is None else min_side
    out: List[TimedFrame] = []
    for bgr, t in zip(bgr_frames, timestamps):
        rgb = np.ascontiguousarray(np.asarray(bgr)[:, :, ::-1])  # BGR -> RGB
        img = Image.fromarray(rgb)
        out.append((float(t), _resize_jpeg(img, max_side, min_side)))
    return out


def build_video_info(path: str, frames: List[TimedFrame], fps: float,
                     width: int, height: int) -> VideoInfo:
    """Onceden-cikarilmis kareler icin VideoInfo uretir (width/height ORIJINAL cozunurluk;
    perception_confidence dusuk-res advisory'sinin dogru calismasi icin)."""
    duration = frames[-1][0] if frames else 0.0
    return VideoInfo(path=path, duration=duration, fps=fps,
                     width=width, height=height, sampled_frames=len(frames))


def detect_scene_cuts(
    frames: List[TimedFrame],
    threshold: float | None = None,
    min_gap: float = 2.0,
) -> List[float]:
    """Ardisik ornek kareler arasi ANI gorsel degisimi (sert sahne-kesimi) tespit eder.

    Splice/kopuk video bolumlerini (or. gozetim klibi + sonradan eklenmis sahne) ayirmak icin:
    her kareyi 32x32 gri-tonlamaya indirger, ardisik kareler arasi normalize ortalama-mutlak-fark
    esigi asarsa kesim sayar. Donus: kesim zaman-damgalari (saniye).
    """
    threshold = settings.scene_cut_threshold if threshold is None else threshold
    if len(frames) < 2:
        return []
    try:
        import numpy as np
    except Exception:
        return []

    def _hist(jpeg: bytes):
        # 4x4x4 = 64 kovali normalize RGB renk-histogrami. Renk dagilimi sahne-degisimine duyarli;
        # sahne-ICI hareket/titreme (or. yangin) renk dagilimini buyuk olcude korur -> daha az yanlis kesim.
        a = np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB").resize((64, 64)), dtype=np.float32)
        q = (a / 64).astype(int).clip(0, 3)
        idx = q[..., 0] * 16 + q[..., 1] * 4 + q[..., 2]
        h = np.bincount(idx.ravel(), minlength=64).astype(np.float32)
        return h / h.sum() if h.sum() else h

    cuts: List[float] = []
    try:
        prev = _hist(frames[0][1])
    except Exception:
        return []
    last_cut = -1e9
    for t, jpeg in frames[1:]:
        try:
            cur = _hist(jpeg)
        except Exception:
            continue
        # histogram-kesisim mesafesi: 1 - sum(min(h1,h2)) ∈ [0,1]; buyuk = renk dagilimi koklu degisti
        dist = 1.0 - float(np.minimum(cur, prev).sum())
        if dist > threshold and (t - last_cut) >= min_gap:
            cuts.append(round(t, 1))
            last_cut = t
        prev = cur
    return cuts


def build_segments(
    frames: List[TimedFrame],
    segment_seconds: float | None = None,
    max_frames_per_segment: int | None = None,
    overlap: float | None = None,
) -> List[Segment]:
    """Kareleri zaman pencerelerine böler; her segmentte azami kare sayisini asarsa
    eşit araliklarla alt-örnekler. `overlap`>0 ise ardisik pencereler ortusur (segment-siniri
    olaylari iki pencerede de gorunur; dedup birlestirir) — uzun videolarda sinir-kaybini onler."""
    segment_seconds = segment_seconds or settings.segment_seconds
    max_frames = max_frames_per_segment or settings.max_frames_per_segment
    overlap = settings.segment_overlap if overlap is None else overlap
    # guvenlik: ortusme segment uzunlugundan kucuk olmali (ilerleme garantisi)
    overlap = max(0.0, min(overlap, segment_seconds - 1.0))

    if not frames:
        return []

    total = frames[-1][0]
    segments: List[Segment] = []
    idx = 0
    start = 0.0
    while start <= total + 1e-6:
        end = start + segment_seconds
        bucket = [(t, j) for (t, j) in frames if start <= t < end]
        if bucket:
            if len(bucket) > max_frames:
                step = len(bucket) / max_frames
                bucket = [bucket[int(i * step)] for i in range(max_frames)]
            seg = Segment(
                index=idx,
                start=start,
                end=min(end, total),
                frames=[(format_timestamp(t), j) for (t, j) in bucket],
            )
            segments.append(seg)
            idx += 1
        start = end - overlap if overlap > 0 else end
    return segments


# ---------------------------------------------------------------------------
# D41 — SERVIS ICIN VIDEO HAZIRLAMA (uzak EVREN cikarim servisi)
# ---------------------------------------------------------------------------
# OLCULDU (2026-08-24, 3_te1.mp4, llm-large):
#
#   gonderilen           boyut      base64     sure            giris token   cevap
#   -------------------  ---------  ---------  --------------  -----------   -----
#   orijinal 1080p       24,5 MB    32,7 MB    82 / 71 / 190 s      12.221    '3' dogru
#   768px CRF28          0,25 MB    0,33 MB     6,4 / 4,2 / 3,2 s    3.621    '3' dogru
#
#   saf metin cagrisi: 0,4 s  -> sistem YUK ALTINDA DEGILDI; yavasligin kaynagi
#   BIZIM gonderdigimiz govdeydi.
#
# ~20x hizlanma, AYNI DOGRU CEVAP. 197 klip: 3,3 saat -> ~16 dakika.
#
# COZUNURLUK TARAMASI (2026-08-24, 297 istek, hata 0) — VARSAYILAN 1280 SECILDI:
#
#   sinif   768        1280       1920       yorum
#   ------  ---------  ---------  ---------  ------------------------------------
#   yelek   MCC 0,000  MCC 0,560  MCC 0,564  768 -> 1280 GERCEK (McNemar p=0,0013,
#           (yazi-tura)                      16 klip duzeldi/2 bozuldu). 1280 -> 1920
#                                            GURULTU (6/6, p=1,000) ve ikincil
#                                            eslemede 1920 DAHA KOTU.
#   pano    49/49 "gorunmuyor" — UC KOLDA DA AYNI. Esli karsilastirmada TEK KLIP
#           bile farkli cevaplanmadi (p=1,0). 1920, 768'e gore 26x bayt + 8x
#           gecikme harcayip HICBIR SEY degistirmedi.
#           => pano darbogazi COZUNURLUK DEGIL; cerceveleme/ROI + dedektor gerek.
#
# DUZELTME: daha once "768 yeter" izlenimi TEK BIR forklift klibinden, BASKA bir
# soruda alinmisti; yelek sinifina GENELLENMIYOR. O genelleme HATALIYDI.
def servis_videosu(yol: str, max_side: int = 1280, crf: int = 26,
                   fps: float | None = None, roi_str: str = "",
                   bas_sn: float | None = None, sure_sn: float | None = None,
                   sabit_bit: str = "") -> bytes:
    """Klibi servise gonderilecek KUCUK bir mp4'e cevirir ve baytlari doner.

    Ag gövdesi ve piksel butcesi icin kucultulur. ffmpeg yoksa veya hata olursa
    ORIJINAL baytlar doner (K3 fail-open — olcum durmaz, yalnizca yavaslar).

    `sabit_bit` (or. "800k") verilirse CRF yerine SABIT BIT HIZI kullanilir.
    NEDEN VAR — YENIDEN KODLAMA KONTROLU: bu sette dosya ozellikleri etiketi
    TEK BASINA tahmin edebiliyor (olculdu, orijinal dosyalar):
        forklift cifti : bit hizi MCC +1,000 · boyut +1,000
        yetkisiz cifti : fps      MCC +0,851
    CRF ile yeniden kodlamak boyut sizintisini kiriyor ama bit hizini
    kirmiyor (+0,882 kaliyor), cunku CRF kalite hedeflidir ve bit hizi sahne
    karmasikligini izler. FPS ise hic dokunulmadigi icin AYNEN geciyor
    (yeniden kodlama sonrasi +1,000).
    `fps` + `sabit_bit` birlikte verildiginde iki kanal da kapanir; skor
    HAYATTA KALIRSA icerikten geliyordur.

    `bas_sn`/`sure_sn` verilirse yalnizca O ZAMAN PENCERESI kodlanir.
    NEDEN: gozlem duzlemi HER SEGMENT icin slot dolduruyor, ama segmentin
    kendi penceresi UYGULANMADIGI surece her segment TUM videoyu gonderiyordu.
    Iki sonucu vardi: (1) 6 segmentlik klipte AYNI soru 6 kez TUM videoya
    soruluyor ve ayni cevap geliyordu (N kat ffmpeg + N kat govde), (2) uretilen
    olayin zaman damgasi ihlalin gercek anina degil ILK segmente denk geliyordu
    — 02:30'daki asiri yuk 00:00 diye raporlaniyordu.

    `roi_str` ("x1,y1,x2,y2" — 0..1 orani) verilirse once KIRPILIR, sonra
    olceklenir. NEDEN: tam karede sorulan pano sorusu OLCULDU ve DEJENERE
    cikti (12 klipte yalnizca {2, 8}, MCC -0,192); ayni soru KIRPILMIS ROI
    uzerinde MCC +1,000 veriyordu. Yani belirleyici olan modelin yetenegi
    degil, sorulan bolgenin karedeki PAYI.
    """
    import subprocess, tempfile, os as _os

    def _kararli():
        """Tekrar uretilebilir kodlama istendiyse tek is parcacigi.

        Ayardan okunur ki cagri yerleri degismesin. Varsayilan KAPALI ->
        komut satiri BIREBIR eskisi gibi (K2).
        """
        try:
            from dilajan.config import settings as _s
            return ["-threads", "1"] if getattr(_s, "kodlama_kararli", False) else []
        except Exception:
            return []

    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            gecici = f.name
        # -ss GIRDIDEN ONCE gelir (hizli arama); -t ondan sonra.
        girdi_oncesi = []
        if bas_sn is not None and bas_sn > 0:
            girdi_oncesi += ["-ss", f"{bas_sn:.3f}"]
        vf = []
        if roi_str:
            try:
                x1, y1, x2, y2 = (float(v) for v in roi_str.split(","))
                # ffmpeg crop: genislik:yukseklik:x:y — oranlar iw/ih ile carpilir.
                # Cift sayiya yuvarlanir (libx264 tek boyut kabul etmez).
                vf.append(f"crop=trunc(iw*{x2 - x1:.6f}/2)*2:"
                          f"trunc(ih*{y2 - y1:.6f}/2)*2:"
                          f"trunc(iw*{x1:.6f}):trunc(ih*{y1:.6f})")
            except (ValueError, TypeError):
                pass                      # bozuk ROI -> kirpma YOK (K3)
        vf.append(f"scale={max_side}:-2")
        _kalite = (["-b:v", sabit_bit, "-minrate", sabit_bit, "-maxrate", sabit_bit,
                    "-bufsize", sabit_bit] if sabit_bit else ["-crf", str(crf)])
        # TEKRAR URETILEBILIRLIK — OLCULDU (2026-08-25):
        # ffmpeg varsayilan ayarlarla ayni klibi iki kez kodlayinca BAYT BAYT
        # FARKLI cikti uretiyordu (0/6 ayni). Kare cikarimi ise tamamen
        # kararliydi (3/3 ayni) ve model ayni oturumda 50/50 klipte birebir
        # ayni cevabi veriyordu. Yani olcumlerimizdeki kosumlar arasi ~0,05'lik
        # MCC dalgalanmasinin kaynagi MODEL DEGIL, KODLAYICIYDI.
        # `+bitexact` (+ metadata silme) bunu 3/3 tekrar uretilebilir yapiyor
        # ve ek maliyeti YOK. `-threads 1` de calisiyordu ama 5x yavas.
        # GIRDI ve CIKTI bayraklari AYRIDIR: `-map_metadata` yalnizca cikti
        # secenegidir ve girdi tarafina konursa ffmpeg hata verir.
        _be_girdi = ["-fflags", "+bitexact"]
        _be_cikti = ["-flags:v", "+bitexact", "-map_metadata", "-1",
                     "-fflags", "+bitexact"]
        komut = (["ffmpeg", "-y", "-v", "error"] + _be_girdi + girdi_oncesi
                 + ["-i", yol]
                 + (["-t", f"{sure_sn:.3f}"] if sure_sn and sure_sn > 0 else [])
                 + ["-vf", ",".join(vf), "-c:v", "libx264"]
                 + _kalite + _be_cikti + _kararli() + ["-preset", "fast", "-an"])
        if fps:
            komut += ["-r", str(fps)]
        komut.append(gecici)
        r = subprocess.run(komut, capture_output=True, timeout=300)
        if r.returncode == 0 and _os.path.getsize(gecici) > 0:
            veri = open(gecici, "rb").read()
            _os.unlink(gecici)
            return veri
        _os.unlink(gecici)
    except Exception:
        pass
    # FAIL-OPEN SINIRI. ffmpeg yoksa/patlarsa ORIJINAL dosya donuyordu; buyuk
    # bir dosyada bu (a) ~40 MB'lik base64 govde -> 413/zaman asimi,
    # (b) ROI ve zaman penceresi UYGULANMAMIS = olculmus DEJENERE kip demek.
    # Kucuk dosyada eski davranis korunur (yalnizca yavaslar, K3); buyukte
    # SESSIZCE bozuk olcum uretmektense ACIK hata verilir.
    HAM_YEDEK_SINIRI = 12_000_000
    _boy = os.path.getsize(yol)
    if _boy > HAM_YEDEK_SINIRI:
        raise RuntimeError(
            f"video yeniden kodlanamadi (ffmpeg yok veya hata verdi) ve ham "
            f"dosya {_boy/1e6:.1f} MB — yedek yol yalnizca "
            f"{HAM_YEDEK_SINIRI/1e6:.0f} MB altinda kullanilir. ffmpeg kurulu mu?")
    return open(yol, "rb").read()
