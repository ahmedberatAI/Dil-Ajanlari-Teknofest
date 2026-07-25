#!/usr/bin/env python
"""K10/K17: ``data/`` altindaki birebir MUKERRER dosyalari bulur ve raporlar.

SORUN (denetim bulgulari):
  K10 -- 262 video dosyasinin buyuk bolumu ayni icerigin kopyasiydi. Bu yalnizca
         disk israfi degil, OLCUM HATASIDIR: ayni klip iki sette birden sayilinca
         "bagimsiz n" oldugundan buyuk gorunur ve paydalar sisar. Ornek:
         ``Normal_Videos_936_x264.mp4`` ile ``Normal_Videos_937_x264.mp4``
         AYNI MD5'e sahiptir -> Normal yanlis-pozitif paydasi 8 ve 16 degil,
         gercekte 7 ve 15 olmalidir.
  K17 -- Buyuk atil yukler (kullanilmayan indirme onbellekleri, acilmis
         arsivlerin yaninda duran zip'ler).

DAVRANIS
  * VARSAYILAN: yalnizca RAPOR. Hicbir dosya silinmez/degistirilmez.
  * ``--apply``: mukerrer kopyalari HARDLINK'e cevirir (icerik ayni kalir,
    MD5 degismez, her yol calismaya devam eder; yalnizca disk kazanilir).
    Hardlink kurulamayan durumda dosyaya DOKUNULMAZ.
  * SILME HICBIR MODDA YAPILMAZ.

Hizli tarama: once dosya BOYUTUNA gore gruplanir, yalnizca ayni boyuttaki
dosyalar icin MD5 hesaplanir (buyuk video agaclarinda cok daha hizli).

Kullanim:
  python scripts/dedupe_data.py                    # rapor
  python scripts/dedupe_data.py --json rapor.json  # makine-okur rapor
  python scripts/dedupe_data.py --apply            # kopyalari hardlink yap
  python scripts/dedupe_data.py --root data/eval_big
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict

VIDEO_EXTS = (".mp4", ".avi", ".mkv", ".mov", ".webm")


def md5(path: str, chunk: int = 1 << 20) -> str:
    """Dosya MD5'i (akis halinde; buyuk videolar icin bellek dostu)."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def walk(root: str, videos_only: bool, exclude: list[str] | None = None) -> list[str]:
    """Kok altindaki dosyalari topla (``exclude`` alt-yollari atlanir)."""
    out: list[str] = []
    skip = [e.replace("\\", "/").rstrip("/") for e in (exclude or [])]
    for dp, _dn, fns in os.walk(root):
        norm = dp.replace("\\", "/")
        if any(norm == s or norm.startswith(s + "/") for s in skip):
            continue
        for fn in fns:
            if videos_only and not fn.lower().endswith(VIDEO_EXTS):
                continue
            p = os.path.join(dp, fn)
            try:
                if os.path.isfile(p) and os.path.getsize(p) > 0:
                    out.append(p)
            except OSError:
                continue
    return sorted(out)


def same_inode(a: str, b: str) -> bool:
    """Iki yol ayni fiziksel dosyayi mi gosteriyor (zaten hardlink mi)?"""
    try:
        sa, sb = os.stat(a), os.stat(b)
        return sa.st_ino == sb.st_ino and sa.st_ino != 0 and sa.st_dev == sb.st_dev
    except OSError:
        return False


def find_dupes(paths: list[str]) -> dict[str, list[str]]:
    """MD5 -> ayni icerige sahip yollar (yalnizca 2+ olanlar)."""
    by_size: dict[int, list[str]] = defaultdict(list)
    for p in paths:
        try:
            by_size[os.path.getsize(p)].append(p)
        except OSError:
            continue
    by_hash: dict[str, list[str]] = defaultdict(list)
    for size, group in by_size.items():
        if len(group) < 2:
            continue                     # tek basina -> kopyasi olamaz
        for p in group:
            try:
                by_hash[md5(p)].append(p)
            except OSError:
                continue
    return {h: sorted(v) for h, v in by_hash.items() if len(v) > 1}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.join("data"), help="taranacak kok (varsayilan: data)")
    ap.add_argument("--all-files", action="store_true", help="yalnizca video degil, TUM dosyalari tara")
    ap.add_argument("--apply", action="store_true",
                    help="kopyalari HARDLINK'e cevir (silme yok, icerik degismez)")
    ap.add_argument("--json", dest="json_out", help="raporu JSON olarak bu dosyaya yaz")
    ap.add_argument("--exclude", action="append", default=[],
                    help="taramadan haric tutulacak alt-yol (birden fazla kez verilebilir)")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        print(f"kok yok: {args.root}", flush=True)
        return
    paths = walk(args.root, videos_only=not args.all_files, exclude=args.exclude)
    dupes = find_dupes(paths)

    n_files = len(paths)
    n_groups = len(dupes)
    n_extra = sum(len(v) - 1 for v in dupes.values())
    wasted = 0
    already_linked = 0
    rows = []
    for h, group in sorted(dupes.items(), key=lambda kv: -os.path.getsize(kv[1][0])):
        size = os.path.getsize(group[0])
        linked = all(same_inode(group[0], g) for g in group[1:])
        if linked:
            already_linked += len(group) - 1
        else:
            wasted += size * (len(group) - 1)
        rows.append({"md5": h, "boyut": size, "adet": len(group),
                     "zaten_hardlink": linked, "yollar": [p.replace("\\", "/") for p in group]})

    print(f"kok={args.root}  taranan dosya={n_files}  benzersiz icerik={n_files - n_extra}", flush=True)
    print(f"mukerrer grup={n_groups}  fazla kopya={n_extra}  "
          f"(bunlarin {already_linked} tanesi ZATEN hardlink)", flush=True)
    print(f"geri kazanilabilir disk = {wasted/1e6:.1f} MB\n", flush=True)

    for r in rows:
        flag = "  [zaten hardlink]" if r["zaten_hardlink"] else ""
        print(f"{r['boyut']/1e6:8.1f} MB x{r['adet']}  md5={r['md5'][:12]}...{flag}", flush=True)
        for p in r["yollar"]:
            print(f"           {p}", flush=True)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({"kok": args.root, "taranan": n_files, "grup": n_groups,
                       "fazla_kopya": n_extra, "zaten_hardlink": already_linked,
                       "geri_kazanilabilir_bayt": wasted, "gruplar": rows},
                      f, indent=1, ensure_ascii=False)
        print(f"\nJSON rapor -> {args.json_out}", flush=True)

    if not args.apply:
        print("\n(RAPOR MODU: hicbir dosya degistirilmedi. Hardlink icin --apply)", flush=True)
        return

    linked = 0
    saved = 0
    for r in rows:
        if r["zaten_hardlink"]:
            continue
        keep = r["yollar"][0]
        for other in r["yollar"][1:]:
            if same_inode(keep, other):
                continue
            tmp = other + ".dedupe_tmp"
            try:
                os.link(keep, tmp)          # once yeni baglantiyi kur
                os.replace(tmp, other)      # atomik degistir -> veri kaybi riski yok
                linked += 1
                saved += r["boyut"]
                print(f"hardlink: {other}  ->  {keep}", flush=True)
            except Exception as e:
                for junk in (tmp,):
                    if os.path.exists(junk):
                        try:
                            os.remove(junk)
                        except OSError:
                            pass
                print(f"atlandi (hardlink kurulamadi): {other}: {type(e).__name__}: {str(e)[:80]}",
                      flush=True)
    print(f"\nBITTI: {linked} kopya hardlink'e cevrildi, ~{saved/1e6:.1f} MB kazanildi. "
          f"HICBIR DOSYA SILINMEDI.", flush=True)


if __name__ == "__main__":
    main()
