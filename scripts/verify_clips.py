#!/usr/bin/env python
"""Klip dogrulayici: bir dizindeki videolarin GERCEK video mu yoksa DONMUS
(hareketsiz/tek-kare-dongusu) mu oldugunu PyAV ile olcup raporlar.

NEDEN (denetim bulgusu K8): ``data/eval_scenario/Fall`` altindaki 8 "dusme"
klibi aslinda VIDEO DEGILDI -- ``get_lying.py`` tek bir PNG'yi
``ffmpeg -loop 1 -t 3 -r 5`` ile sarmalayarak uretmisti: 1024x1024, 3.0 sn,
5 fps ve KARELER ARASI SIFIR degisim. Bir VLM boyle bir klipte "dusme"
tespiti yapamaz; yalnizca tek bir fotografi betimler. Bu betik boyle
kliplerin degerlendirme setine sizmasini KANITLA engellemek icin yazildi.

OLCULEN METRIKLER
  sure (sn), fps, cozunurluk, kare sayisi
  motion_mean : ardisik kareler arasindaki ortalama mutlak fark (0-255 olcegi)
  motion_max  : en buyuk kare-arasi fark
  uniq_frames : birbirinden farkli (hash'i ayri) kare sayisi

KARAR (esikler ``Esikler`` ile tasinir; ortam degiskeni veya CLI ile ayarlanir)
  DONMUS           : motion_max < MOTION_EPS (varsayilan 0.5) veya uniq_frames <= 1
  TEK-KARE-DONGUSU : uniq_frames == 1 ama kare >= 2 (tek fotograf N kez tekrar)
  KISA             : sure < MIN_SEC (varsayilan 3.0)
  DUSUK-FPS        : fps < MIN_FPS (varsayilan 10)
  KARE-YOK         : hic kare cozulemedi

ORTAK YARDIMCI: bu modul ayni zamanda bir KUTUPHANEDIR. ``probe()`` / ``sorunlar()``
/ ``classify()`` / ``collect()`` fonksiyonlarini
  * ``scripts/build_scenario_eval.py`` (donmus adayi reddetmek icin)
  * ``scripts/audit_eval_sets.py``     (tum eval setlerini denetlemek icin)
kullanir -- ayni olcum mantigi IKINCI KEZ YAZILMAZ.

Kullanim:
  python scripts/verify_clips.py data/eval_scenario/Fall
  python scripts/verify_clips.py data/eval_scenario/Fall data/falls_real/Fall --strict
  python scripts/verify_clips.py data/eval_defense --min-sec 2 --min-fps 8
  MAX_FRAMES=60 python scripts/verify_clips.py data/eval_scenario/Fall --json

NOT: PyAV gerekir (WSL venv'inde kurulu). GPU/model GEREKTIRMEZ.
  wsl.exe -d Ubuntu-24.04 -- /home/omen/teknofest/.venv/bin/python scripts/verify_clips.py <dizin>
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
from dataclasses import dataclass, replace

MIN_SEC = float(os.environ.get("MIN_SEC", "3.0"))
MIN_FPS = float(os.environ.get("MIN_FPS", "10"))
MOTION_EPS = float(os.environ.get("MOTION_EPS", "0.5"))
MAX_FRAMES = int(os.environ.get("MAX_FRAMES", "48"))
#: taranan video uzantilari (dedup/denetim araclariyla ORTAK kume)
EXTS = (".mp4", ".avi", ".mkv", ".mov", ".webm", ".mpg", ".mpeg")


@dataclass(frozen=True)
class Esikler:
    """Klip saglik esikleri. Varsayilanlar ortam degiskenlerinden gelir.

    Neden ayri bir tip: ayni olcum (``probe``) farkli KARAR esikleriyle
    kullanilmak zorunda. Ornek: ``build_scenario_eval`` sete girecek klipten
    >=3 sn ister; ``audit_eval_sets`` var olan setlerde yalnizca *acikca sahte*
    olani (<2 sn, <8 fps) kritik sayar. Esikler modul-global olsaydi bu iki
    kullanim birbirini bozardi.
    """

    min_sec: float = MIN_SEC
    min_fps: float = MIN_FPS
    motion_eps: float = MOTION_EPS
    max_frames: int = MAX_FRAMES


#: modul varsayilani (eski davranisla birebir ayni)
VARSAYILAN_ESIK = Esikler()
#: denetim profili: "sette bulunmasi kabul edilemez" alt sinirlar (audit_eval_sets.py)
DENETIM_ESIK = Esikler(min_sec=2.0, min_fps=8.0)


#: guvenlik siniri: bir klipte en fazla bu kadar kare COZULUR (patolojik uzun dosya korumasi)
MAX_DECODE = int(os.environ.get("MAX_DECODE", "6000"))

#: OLCUM ALGORITMASI SURUMU. Ornekleme/olcum mantigi degistiginde ARTIRILMALIDIR:
#: audit_eval_sets.py olcum onbellegini bu surumle anahtarlar, boylece eski algoritmayla
#: uretilmis degerler sessizce yeniden kullanilmaz. (v1: bastan ardisik N kare;
#: v2: klibin tamamina yayilmis adimli ornekleme.)
PROBE_SURUM = 2


def _kucult(frame) -> "object":
    """Kareyi gri + 1/4 olcege indir (hiz; hareket olcusu icin yeterli cozunurluk)."""
    return frame.to_ndarray(format="gray")[::4, ::4].astype("int16")


def probe(path: str, esik: Esikler | None = None) -> dict:
    """Tek klibi coz ve olcum sozlugu dondur (FAIL-OPEN: hata -> {'error': ...}).

    ORNEKLEME (onemli): kareler klibin BASINDAN degil, TUM SURESINE YAYILMIS
    demirleme noktalarindan alinir. Neden: 30 fps'lik 80 saniyelik bir gozetim
    klibinde ilk 16 kare = 0.5 saniyedir ve o yarim saniye neredeyse her zaman
    durgundur. Bas-16-kare olcumu gercek UCF-Crime kliplerini "DONMUS" gosteriyordu
    (olculdu: Fighting023 motion_max=0.0033) -- yani sahte-klip denetimi YANLIS
    ALARM uretiyordu. Yayilmis ornekleme ile ayni klip 3.06'ya cikar.

    ``ornekleme`` alani hangi yontemin kullanildigini bildirir: ``"yayilmis"``
    (demirleme noktalari) veya ``"ardisik"`` (sure/seek yok -> bastan ardisik).
    """
    esik = esik or VARSAYILAN_ESIK
    try:
        import av  # gec import: PyAV yoksa yalnizca bu fonksiyon patlasin
        import numpy as np
    except Exception as e:  # pragma: no cover - ortam bagimli
        return {"path": path, "error": f"PyAV/numpy yok: {e}"}

    info: dict = {"path": path}
    try:
        info["boyut_mb"] = round(os.path.getsize(path) / 1e6, 2)
    except OSError:
        info["boyut_mb"] = 0.0
    try:
        with av.open(path) as c:
            st = c.streams.video[0]
            info["fps"] = round(float(st.average_rate or 0), 2)
            info["genislik"] = st.codec_context.width
            info["yukseklik"] = st.codec_context.height
            dur = float(c.duration / 1e6) if c.duration else 0.0
            if not dur and st.duration and st.time_base:
                dur = float(st.duration * st.time_base)
            info["sure_sn"] = round(dur, 2)

            diffs: list[float] = []
            hashes: set[str] = set()
            n = 0            # OLCULEN (ndarray'e cevrilen) kare sayisi
            cozulen = 0      # akistan cozulen toplam kare (maliyet gostergesi)

            # ORNEKLEM ADIMI: klibin tamamina yayilmis ~max_frames kare olcmek icin
            # her ``adim`` karede bir CIFT (j, j+1) ornekle. Cift olmasi sart: hareket
            # ancak ARDISIK iki kare arasinda olculur.
            # NOT: burada seek KULLANILMAZ. PyAV seek'i en yakin ONCEKI anahtar kareye
            # dusuyor; UCF kliplerinde anahtar kare araligi klip boyu kadar oldugu icin
            # tum demirleme noktalari klibin BASINA cokuyordu (olculdu: uniq=3/15).
            toplam = 0
            try:
                toplam = int(st.frames or 0)
            except Exception:
                toplam = 0
            if not toplam and dur and info.get("fps"):
                toplam = int(round(dur * float(info["fps"])))
            cift = max(1, esik.max_frames // 2)
            adim = max(2, toplam // cift) if toplam > 2 * cift else 1

            prev = None
            for frame in c.decode(video=0):
                cozulen += 1
                if cozulen > MAX_DECODE:
                    break
                faz = (cozulen - 1) % adim
                if adim > 1 and faz > 1:
                    continue            # bu kare ATLANIR: yalnizca cozulur, olculmez
                small = _kucult(frame)
                hashes.add(hashlib.md5(small.tobytes()).hexdigest())
                if prev is not None:
                    diffs.append(float(np.abs(small - prev).mean()))
                prev = small if (adim == 1 or faz == 0) else None
                n += 1
                if adim == 1 and n >= esik.max_frames:
                    break

            info["ornekleme"] = "yayilmis" if adim > 1 else "ardisik"
            info["adim"] = adim
            info["cozulen_kare"] = cozulen
            info["kare"] = n
            info["uniq_frames"] = len(hashes)
            info["motion_mean"] = round(sum(diffs) / len(diffs), 4) if diffs else 0.0
            info["motion_max"] = round(max(diffs), 4) if diffs else 0.0
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return info


def sorunlar(info: dict, esik: Esikler | None = None) -> list[tuple[str, str]]:
    """Olcum sozlugunden ``[(kod, insan_okur_mesaj), ...]`` uret.

    Kodlar makine-okur (JSON/denetim raporu), mesajlar konsol icindir.
    Kod kumesi: COZULEMEDI, KARE_YOK, DONMUS, TEK_KARE_DONGUSU, KISA, DUSUK_FPS.
    """
    esik = esik or VARSAYILAN_ESIK
    if info.get("error"):
        return [("COZULEMEDI", f"COZULEMEDI ({info['error']})")]
    out: list[tuple[str, str]] = []
    kare = int(info.get("kare", 0) or 0)
    uniq = int(info.get("uniq_frames", 0) or 0)
    if kare == 0:
        out.append(("KARE_YOK", "KARE-YOK (video akisi cozuldu ama kare gelmedi)"))
    # DIKKAT: build_scenario_eval.is_frozen() bu mesajin "DONMUS" ile BASLAMASINA
    # dayanir. Kosul veya metin degistirilirse orasi da guncellenmeli.
    if uniq <= 1 or float(info.get("motion_max", 0.0) or 0.0) < esik.motion_eps:
        out.append(("DONMUS", "DONMUS (kare-arasi hareket ~0)"))
    if uniq == 1 and kare >= 2:
        out.append(("TEK_KARE_DONGUSU", f"TEK-KARE-DONGUSU ({kare} kare, 1 benzersiz)"))
    if float(info.get("sure_sn", 0.0) or 0.0) < esik.min_sec:
        out.append(("KISA", f"KISA (<{esik.min_sec}sn)"))
    if float(info.get("fps", 0.0) or 0.0) < esik.min_fps:
        out.append(("DUSUK_FPS", f"DUSUK-FPS (<{esik.min_fps})"))
    return out


def classify(info: dict, esik: Esikler | None = None) -> tuple[bool, list[str]]:
    """Olcumlerden (gecti_mi, uyari_listesi) uret (geriye donuk uyumlu sarmalayici)."""
    problems = sorunlar(info, esik)
    return (not problems), [m for _kod, m in problems]


def piksel(info: dict) -> int:
    """Kare alani (genislik*yukseklik); bilinmiyorsa 0. Cozunurluk-etiket confound icin."""
    try:
        return int(info.get("genislik") or 0) * int(info.get("yukseklik") or 0)
    except (TypeError, ValueError):
        return 0


def cozunurluk(info: dict) -> str:
    """``"1920x1080"`` biciminde cozunurluk metni (bilinmiyorsa ``"?x?"``)."""
    return f"{info.get('genislik', '?')}x{info.get('yukseklik', '?')}"


def collect(targets: list[str]) -> list[str]:
    """Dizin/dosya/glob karisimindan video yollari topla."""
    out: list[str] = []
    for t in targets:
        if os.path.isdir(t):
            for e in EXTS:
                out.extend(glob.glob(os.path.join(t, "**", "*" + e), recursive=True))
        else:
            out.extend(glob.glob(t))
    return sorted(set(p for p in out if p.lower().endswith(EXTS)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="+", help="dizin(ler) / dosya(lar) / glob")
    ap.add_argument("--json", action="store_true", help="ham olcumleri JSON olarak bas")
    ap.add_argument("--strict", action="store_true", help="uyari varsa cikis kodu 1 olsun")
    ap.add_argument("--min-sec", type=float, default=None, help=f"asgari sure sn (varsayilan {MIN_SEC})")
    ap.add_argument("--min-fps", type=float, default=None, help=f"asgari fps (varsayilan {MIN_FPS})")
    ap.add_argument("--motion-eps", type=float, default=None,
                    help=f"donmus esigi, kare-arasi fark (varsayilan {MOTION_EPS})")
    ap.add_argument("--frames", type=int, default=None,
                    help=f"klip basina cozulecek en fazla kare (varsayilan {MAX_FRAMES})")
    args = ap.parse_args()

    esik = VARSAYILAN_ESIK
    if args.min_sec is not None:
        esik = replace(esik, min_sec=args.min_sec)
    if args.min_fps is not None:
        esik = replace(esik, min_fps=args.min_fps)
    if args.motion_eps is not None:
        esik = replace(esik, motion_eps=args.motion_eps)
    if args.frames is not None:
        esik = replace(esik, max_frames=args.frames)

    paths = collect(args.targets)
    if not paths:
        print("video bulunamadi", flush=True)
        return 0

    rows = []
    n_bad = 0
    hdr = f"{'dosya':<34}{'sure':>7}{'fps':>7}{'cozunurluk':>13}{'kare':>6}{'uniq':>6}{'mot_mean':>10}{'mot_max':>9}  durum"
    if not args.json:
        print(f"# esikler: min_sec={esik.min_sec} min_fps={esik.min_fps} "
              f"motion_eps={esik.motion_eps} max_frames={esik.max_frames}", flush=True)
        print(hdr, flush=True)
        print("-" * len(hdr), flush=True)
    for p in paths:
        info = probe(p, esik)
        problems = sorunlar(info, esik)
        ok = not problems
        info["gecti"] = ok
        info["uyarilar"] = [m for _k, m in problems]
        info["kodlar"] = [k for k, _m in problems]
        rows.append(info)
        if not ok:
            n_bad += 1
        if not args.json:
            print(f"{os.path.basename(p):<34}{info.get('sure_sn', 0):>7}{info.get('fps', 0):>7}"
                  f"{cozunurluk(info):>13}"
                  f"{info.get('kare', 0):>6}{info.get('uniq_frames', 0):>6}"
                  f"{info.get('motion_mean', 0):>10}{info.get('motion_max', 0):>9}  "
                  f"{'OK' if ok else ' | '.join(info['uyarilar'])}", flush=True)
    if args.json:
        print(json.dumps(rows, indent=1, ensure_ascii=False))
    else:
        print(f"\nTOPLAM {len(paths)} klip | GERCEK VIDEO {len(paths)-n_bad} | SORUNLU {n_bad}", flush=True)
    return 1 if (args.strict and n_bad) else 0


if __name__ == "__main__":
    sys.exit(main())
