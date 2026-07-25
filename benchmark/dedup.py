#!/usr/bin/env python
"""MD5 tabanli MUKERRER KLIP ELEME (K10).

NEDEN: data/eval/Normal/Normal_Videos_936_x264.mp4 ve ..._937_x264.mp4 BAYT-BAYT AYNI
dosya. Ikisi de sayilinca "Normal yanlis-pozitif" paydasi 8 (ve eval_big'de 16) gorunuyor;
gercekte 7 ve 15. Ayni icerik iki kez sayildiginda hem payda hem de metrik sisiyor.

Bu modul, bir klip listesini icerik-hash'ine gore TEKILLESTIRIR: ayni MD5'e sahip
dosyalardan yalnizca ILKI (siralamada once gelen) korunur, digerleri "atlandi" olarak
raporlanir ve cikti JSON'una yazilir.

FAIL-OPEN: bir dosyanin hash'i alinamazsa (izin/IO hatasi) dosya ELENMEZ, korunur;
"hash alinamadi" notu ile rapora dusulur. Olcumu sessizce kucultmek yerine sesli birakiriz.

Kullanim (kod icinden):
    from benchmark.dedup import dedup_paths
    kept, skipped = dedup_paths(paths)

Kullanim (CLI tarama raporu):
    python benchmark/dedup.py                      # varsayilan eval setlerini tarar
    python benchmark/dedup.py data/eval data/eval_big
"""
from __future__ import annotations

import hashlib
import os
import sys
from typing import Dict, Iterable, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VIDEO_EXTS = (".mp4", ".avi", ".mkv", ".mov", ".mpg", ".mpeg", ".webm")

# CLI varsayilani: olcum iddialarinin dayandigi setler
DEFAULT_SCAN_DIRS = [
    "data/eval", "data/eval_big", "data/eval_scenario", "data/eval_stress",
    "data/falls_real", "data/falls_surveillance", "data/e2_vehicle",
    "data/industrial", "data/temporal",
]

_HASH_CACHE: Dict[Tuple[str, int, int], str] = {}


def file_md5(path: str, chunk_size: int = 1 << 20) -> Optional[str]:
    """Dosyanin MD5 ozetini dondurur; okunamazsa None (FAIL-OPEN).

    (yol, boyut, mtime_ns) anahtarli bellek-ici cache ile ayni kosuda tekrar okumaz.
    MD5 burada KRIPTOGRAFIK amacla degil, birebir kopya tespiti icin kullaniliyor.
    """
    try:
        st = os.stat(path)
        key = (os.path.abspath(path), st.st_size, st.st_mtime_ns)
    except OSError:
        return None
    cached = _HASH_CACHE.get(key)
    if cached:
        return cached
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while True:
                b = f.read(chunk_size)
                if not b:
                    break
                h.update(b)
    except OSError:
        return None
    digest = h.hexdigest()
    _HASH_CACHE[key] = digest
    return digest


def dedup_paths(paths: Iterable[str],
                seen: Optional[Dict[str, str]] = None,
                rel_to: Optional[str] = ROOT) -> Tuple[List[str], List[dict]]:
    """Ayni icerikli (ayni MD5) kliplerden yalnizca ilkini korur.

    Args:
        paths: degerlendirilecek dosya yollari (siralama onemlidir: ilk gelen korunur)
        seen: onceden gorulmus {md5: yol} sozlugu — birden fazla cagri arasinda
              kumulatif tekillestirme icin disaridan verilebilir (yerinde guncellenir)
        rel_to: rapordaki yollar bu koke gore goreli yazilir (None -> mutlak)

    Returns:
        (korunan_yollar, atlanan_kayitlar)
        atlanan_kayitlar: [{"path":..., "duplicate_of":..., "md5":...}, ...]
    """
    if seen is None:
        seen = {}

    def _rel(p: str) -> str:
        if not rel_to:
            return p
        try:
            return os.path.relpath(p, rel_to).replace("\\", "/")
        except ValueError:  # farkli surucu (Windows) -> mutlak birak
            return p

    kept: List[str] = []
    skipped: List[dict] = []
    for p in paths:
        digest = file_md5(p)
        if digest is None:
            # hash alinamadi -> ELEME, sesli birak
            kept.append(p)
            skipped.append({"path": _rel(p), "duplicate_of": None,
                            "md5": None, "note": "hash alinamadi — elenmedi"})
            continue
        first = seen.get(digest)
        if first is not None:
            skipped.append({"path": _rel(p), "duplicate_of": _rel(first), "md5": digest})
            continue
        seen[digest] = p
        kept.append(p)
    return kept, skipped


def iter_videos(directory: str, exts: Iterable[str] = VIDEO_EXTS) -> List[str]:
    """Dizin agacindaki video dosyalarini siralanmis olarak dondurur."""
    exts = tuple(e.lower() for e in exts)
    out: List[str] = []
    for dirpath, _dirnames, filenames in os.walk(directory):
        for fn in filenames:
            if fn.lower().endswith(exts):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def scan_report(dirs: Iterable[str]) -> dict:
    """Verilen dizinleri tarar; mukerrer gruplarini ve sayilarini raporlar."""
    by_hash: Dict[str, List[str]] = {}
    unreadable: List[str] = []
    n_files = 0
    for d in dirs:
        full = d if os.path.isabs(d) else os.path.join(ROOT, d)
        if not os.path.isdir(full):
            continue
        for p in iter_videos(full):
            n_files += 1
            digest = file_md5(p)
            if digest is None:
                unreadable.append(os.path.relpath(p, ROOT).replace("\\", "/"))
                continue
            by_hash.setdefault(digest, []).append(
                os.path.relpath(p, ROOT).replace("\\", "/"))
    groups = {h: sorted(ps) for h, ps in by_hash.items() if len(ps) > 1}
    n_unique = len(by_hash) + len(unreadable)
    return {
        "n_files": n_files,
        "n_unique": n_unique,
        "n_duplicate_files": n_files - n_unique,
        "n_duplicate_groups": len(groups),
        "duplicate_groups": dict(sorted(groups.items(), key=lambda kv: -len(kv[1]))),
        "unreadable": unreadable,
    }


def main() -> None:
    dirs = sys.argv[1:] or DEFAULT_SCAN_DIRS
    rep = scan_report(dirs)
    print("=" * 70)
    print("MD5 MUKERRER TARAMASI (K10)")
    print("=" * 70)
    print("Taranan dizinler: " + ", ".join(dirs))
    print(f"  Toplam dosya            : {rep['n_files']}")
    print(f"  Benzersiz icerik        : {rep['n_unique']}")
    print(f"  MUKERRER dosya          : {rep['n_duplicate_files']}")
    print(f"  Mukerrer grup sayisi    : {rep['n_duplicate_groups']}")
    if rep["unreadable"]:
        print(f"  Okunamayan (elenmedi)   : {len(rep['unreadable'])}")
    print("-" * 70)
    for h, ps in rep["duplicate_groups"].items():
        print(f"  [{h[:12]}] x{len(ps)}")
        for p in ps:
            print(f"      {p}")
    print("=" * 70)
    print("Not: eval_clips.py bu tekillestirmeyi otomatik uygular; atlanan dosyalar")
    print("     cikti JSON'unda 'dedup' alanina yazilir.")


if __name__ == "__main__":
    main()
