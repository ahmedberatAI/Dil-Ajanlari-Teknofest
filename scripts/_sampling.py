#!/usr/bin/env python
"""Indirici betikler icin ORTAK deterministik orneklem yardimcilari (K12 duzeltmesi).

SORUN (denetim bulgusu K12): build_eval_set / get_ucf_many / get_normal_clips /
get_industrial / get_vehicle_accidents betiklerinin hepsi aday klipleri
``clips.sort()`` ile DOSYA BOYUTUNA gore siralayip ``clips[:N]`` aliyordu.
Bu "en kucuk N" secimi sistematik orneklem yanliligi uretir: kisa/dusuk-bit-hizli/
statik sahneler asiri temsil edilir, uzun ve hareketli sahneler hic secilmez.
Olculen basari orani veri setinin GERCEK zorlugunu yansitmaz.

COZUM: sabit tohumlu (seed) rastgele orneklem.
  * Aday listesi once YOLA gore siralanir -> sunucu/dizin listeleme sirasi degisse
    bile secim ayni kalir (belirlenimcilik ic kaynak sirasindan bagimsiz).
  * ``random.Random(seed).sample(...)`` ile secim yapilir.
  * Tohum ``EVAL_SEED`` ortam degiskeninden okunur, varsayilani SABIT (2026)
    -> ayni komut ayni klipleri verir, tekrar uretilebilir.
  * Kategori/etiket basina tohum ``crc32(label)`` ile turetilir. Python'un
    ``hash()`` fonksiyonu string'lerde SURECLER ARASI RASTGELEDIR (PYTHONHASHSEED),
    bu yuzden asla hash() kullanilmaz.
  * Eski davranis ``--smallest`` bayragi ile opsiyonel olarak korunur
    (dondurulmus eski sonuclari yeniden uretmek gerekirse).
"""
from __future__ import annotations

import argparse
import os
import random
import zlib
from typing import Iterable, Sequence, TypeVar

T = TypeVar("T")

#: Varsayilan tohum. Degistirmeyin -> mevcut secimler yeniden uretilebilir kalsin.
DEFAULT_SEED = 2026


def env_str(name: str, default: str) -> str:
    """Ortam degiskenini oku; TANIMSIZ **veya BOS** ise varsayilana don.

    ``os.environ.get(name, default)`` bir tuzaktir: degisken bos string olarak
    tanimliysa ("" ) bos string doner. Cikti dizini icin bu yikici olur --
    ``os.path.join("", "Fall")`` -> ``"Fall"`` yani dosyalar depo KOKUNE yazilir.
    (Bu hata gelistirme sirasinda fiilen yasandi.)
    """
    val = os.environ.get(name)
    return default if val is None or not val.strip() else val


def get_seed() -> int:
    """EVAL_SEED ortam degiskenini oku (bozuksa varsayilana FAIL-OPEN don)."""
    try:
        return int(os.environ.get("EVAL_SEED", str(DEFAULT_SEED)))
    except Exception:
        return DEFAULT_SEED


def label_seed(label: str, seed: int | None = None) -> int:
    """Etiket (kategori adi) + temel tohumdan platformdan bagimsiz tohum turet.

    crc32 kullanilir cunku Python'un yerlesik ``hash()`` fonksiyonu string'ler icin
    her surecte farkli sonuc verir (PYTHONHASHSEED rastgeleligi) -> tekrar
    uretilebilirligi bozar.
    """
    base = get_seed() if seed is None else seed
    return (base * 1_000_003 + zlib.crc32(label.encode("utf-8"))) & 0x7FFF_FFFF


def sample_clips(
    clips: Sequence[tuple[int, str]],
    n: int,
    label: str,
    *,
    smallest: bool = False,
    seed: int | None = None,
) -> list[tuple[int, str]]:
    """``(boyut, yol)`` adaylarindan n tanesini DETERMINISTIK sec.

    Args:
        clips: aday listesi, her ogesi ``(boyut_bayt, yol)``.
        n: secilecek klip sayisi (aday sayisindan buyukse hepsi doner).
        label: tohum turetmek icin kategori/etiket adi.
        smallest: True ise ESKI davranis (en kucuk n klip). Yanli ornekleme;
            yalnizca dondurulmus eski sonuclari yeniden uretmek icin.
        seed: temel tohum (None -> EVAL_SEED / DEFAULT_SEED).

    Returns:
        Yola gore sirali secim listesi (cikti sirasi da deterministik).
    """
    if n <= 0 or not clips:
        return []
    # Kaynak sirasindan bagimsiz kanonik siralama: once yola gore.
    pool = sorted(clips, key=lambda t: t[1])
    if smallest:
        # ESKI (yanli) davranis: boyuta gore en kucuk n.
        return sorted(sorted(pool, key=lambda t: (t[0], t[1]))[:n], key=lambda t: t[1])
    if n >= len(pool):
        return pool
    rnd = random.Random(label_seed(label, seed))
    return sorted(rnd.sample(pool, n), key=lambda t: t[1])


def sample_paths(
    paths: Iterable[str],
    n: int,
    label: str,
    *,
    smallest: bool = False,
    seed: int | None = None,
) -> list[str]:
    """Yalnizca yol listesi icin ince sarmalayici (boyut bilinmiyorsa 0 kabul edilir).

    ``smallest=True`` verilirse boyut bilinmedigi icin ALFABETIK ilk n dondurulur
    (eski ``sorted(glob(...))[:N]`` davranisinin karsiligi).
    """
    items = [(0, p) for p in paths]
    if smallest:
        return sorted(sorted(p for _, p in items)[:n])
    return [p for _, p in sample_clips(items, n, label, smallest=False, seed=seed)]


def add_sampling_args(ap: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Indirici betiklere ortak ``--smallest / --list / --seed`` bayraklarini ekler."""
    ap.add_argument(
        "--smallest",
        action="store_true",
        help="ESKI yanli davranis: rastgele yerine en kucuk N klibi sec (K12 oncesi).",
    )
    ap.add_argument(
        "--list",
        "--dry-run",
        dest="list_only",
        action="store_true",
        help="Hicbir sey indirme; yalnizca secilen klipleri listele (dogrulama icin).",
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=None,
        help=f"Orneklem tohumu (varsayilan: EVAL_SEED ya da {DEFAULT_SEED}).",
    )
    return ap


def print_selection(label: str, picked: Sequence[tuple[int, str]], pool_size: int) -> None:
    """Secimi tekrar-uretilebilirlik denetimi icin okunakli bas."""
    print(f"[{label}] havuz={pool_size} secim={len(picked)}", flush=True)
    for size, path in picked:
        mb = f"{size/1e6:.1f} MB" if size else "? MB"
        print(f"    {os.path.basename(path):<40} {mb}", flush=True)


def _selftest() -> int:
    """Ag/GPU gerektirmeyen ic tutarlilik testleri. ``python scripts/_sampling.py``"""
    import subprocess
    import sys

    fails: list[str] = []

    def check(ad: str, kosul: bool) -> None:
        print(f"  {'OK  ' if kosul else 'HATA'}  {ad}", flush=True)
        if not kosul:
            fails.append(ad)

    pool = [(i * 1000, f"data/x/clip{i:03d}.mp4") for i in range(50)]

    # 1) Ayni tohum -> ayni secim
    a = sample_clips(pool, 6, "Kategori", seed=2026)
    b = sample_clips(pool, 6, "Kategori", seed=2026)
    check("ayni tohum ayni secimi verir", a == b)

    # 2) Farkli tohum -> (neredeyse kesin) farkli secim
    c = sample_clips(pool, 6, "Kategori", seed=7)
    check("farkli tohum farkli secim verir", a != c)

    # 3) Kaynak listesinin sirasi secimi ETKILEMEZ (kanonik siralama)
    import random as _r
    shuffled = pool[:]
    _r.Random(99).shuffle(shuffled)
    check("kaynak sirasi secimi degistirmez", sample_clips(shuffled, 6, "Kategori", seed=2026) == a)

    # 4) --smallest gercekten en kucukleri verir
    small = sample_clips(pool, 5, "Kategori", smallest=True)
    check("smallest en kucuk N'i verir", [p for _s, p in small] == [p for _s, p in pool[:5]])

    # 5) Kategori basina farkli secim (etiket tohuma karisiyor)
    check("farkli etiket farkli secim verir", sample_clips(pool, 6, "Baska", seed=2026) != a)

    # 6) n >= havuz -> tum havuz
    check("n havuzdan buyukse hepsi doner", len(sample_clips(pool, 999, "K")) == len(pool))

    # 7) n <= 0 / bos havuz -> bos
    check("n<=0 bos doner", sample_clips(pool, 0, "K") == [] and sample_clips([], 5, "K") == [])

    # 8) label_seed SURECLER ARASI kararli olmali (hash() randomizasyonuna dusmemeli)
    code = ("import sys; sys.path.insert(0, r'%s'); from _sampling import label_seed; "
            "print(label_seed('Kategori', 2026))" % os.path.dirname(os.path.abspath(__file__)))
    outs = set()
    for hs in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
        outs.add(r.stdout.strip())
    check(f"label_seed PYTHONHASHSEED'den bagimsiz ({outs})", len(outs) == 1)

    # 9) env_str bos degeri varsayilana cevirir
    os.environ["_TEST_EMPTY"] = ""
    check("env_str bos degeri varsayilana cevirir", env_str("_TEST_EMPTY", "vars") == "vars")
    os.environ["_TEST_EMPTY"] = "  "
    check("env_str bosluk-dolu degeri varsayilana cevirir", env_str("_TEST_EMPTY", "vars") == "vars")
    os.environ["_TEST_EMPTY"] = "gercek"
    check("env_str gercek degeri korur", env_str("_TEST_EMPTY", "vars") == "gercek")
    del os.environ["_TEST_EMPTY"]

    print(f"\n{'TUM TESTLER GECTI' if not fails else str(len(fails)) + ' TEST BASARISIZ: ' + ', '.join(fails)}",
          flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    import sys as _sys

    _sys.exit(_selftest())
