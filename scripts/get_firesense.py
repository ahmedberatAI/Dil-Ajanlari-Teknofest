#!/usr/bin/env python
"""FIRESENSE yangin/duman video veri setini Zenodo'dan indirir ve degerlendirme
setlerini kurar (K13: TEKRAR-URETILEBILIRLIK ACIGI kapatilir).

NEDEN: ``data/eval_scenario/Fire`` (10 yangin pozitifi) ve ``data/eval_stress/Normal``
(9 cetin negatif: yangin-renkli ama yangin OLMAYAN sahneler) bu veri setinden
geliyor -- yani en iyi baslik rakamlarimizin verisi. Fakat repoda bu veriyi
indiren HICBIR betik yoktu; kliplerin nereden geldigi belgesizdi ve set
sifirdan yeniden kurulamiyordu. Yarisma "herkese acik link + tekrar
uretilebilirlik" istedigi icin bu betik yazildi.

KAYNAK
  Zenodo kayit  : https://zenodo.org/records/836749
  API           : https://zenodo.org/api/records/836749
  Baslik        : "FIRESENSE database of videos for flame and smoke detection"
  Dosyalar      : fire_videos.1406.zip  (~622 MB, md5 7cfe8286cc4b45193149186bf67ea00d)
                  smoke_videos.1407.zip (~198 MB, md5 5ee6bc867c4a9332b4e75f308c26fc23)
  Ic yapi       : her zip -> pos/*.avi (yangin/duman VAR) + neg/*.avi (YOK)

MEVCUT DUZENE UYUM (dosya adlari degistirilmez):
  data/scenario/_dl/fire.zip , data/scenario/_dl/smoke.zip     <- arsivler
  data/scenario/_dl/pos/*.avi , data/scenario/_dl/neg/*.avi    <- acilmis klipler
  data/eval_scenario/Fire/     <- pos/posVideo*.avi ilk N_FIRE (alfabetik)
  data/eval_stress/Normal/     <- neg/testneg*.avi (duman zip'inin negatifleri)

KULLANIM
  python scripts/get_firesense.py --list          # sadece API listesi, indirme YOK
  python scripts/get_firesense.py --probe         # kucuk Range istegiyle GERCEK ag testi
  python scripts/get_firesense.py --verify        # yerel zip'lerin MD5'ini Zenodo ile karsilastir
  python scripts/get_firesense.py                 # indir (varsa atla) + ac + eval setlerini kur
  python scripts/get_firesense.py --extract-only  # indirme yok, mevcut zip'lerden ac
  python scripts/get_firesense.py --no-build-eval # yalnizca _dl/pos + _dl/neg kur
  FIRESENSE_OUT=/tmp/x python scripts/get_firesense.py --extract-only   # baska hedefe ac

NOT: data/ altinda SILME yapilmaz. ``--archive-zips`` arsivleri silmez, yalnizca
``data/_attic/`` altina TASIR (yer kazanmak isteyenler icin, geri alinabilir).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import urllib.request
import zipfile

RECORD = os.environ.get("FIRESENSE_RECORD", "836749")
API = f"https://zenodo.org/api/records/{RECORD}"
# DIKKAT: Zenodo sahte tarayici User-Agent'ini ("Mozilla/5.0") 403 ile REDDEDIYOR
# (fiilen dogrulandi). Tanimlayici bir UA zorunlu; repodaki diger indirici
# betiklerin kullandigi "Mozilla/5.0" burada CALISMAZ.
H = {"User-Agent": "DilAjanlariTeknofest/1.0 (research; TEKNOFEST TYDA)",
     "Accept": "application/json"}

DL_DIR = os.environ.get("FIRESENSE_DL", os.path.join("data", "scenario", "_dl"))
OUT_DIR = os.environ.get("FIRESENSE_OUT", DL_DIR)
FIRE_EVAL = os.environ.get("FIRE_EVAL_OUT", os.path.join("data", "eval_scenario", "Fire"))
STRESS_EVAL = os.environ.get("STRESS_EVAL_OUT", os.path.join("data", "eval_stress", "Normal"))
ATTIC = os.path.join("data", "_attic")

N_FIRE = int(os.environ.get("N_FIRE", "10"))

#: Zenodo dosya adi -> repodaki kisa ad (mevcut duzeni bozmamak icin).
LOCAL_NAME = {"fire": "fire.zip", "smoke": "smoke.zip"}


def local_name(key: str) -> str:
    """``fire_videos.1406.zip`` -> ``fire.zip`` (bilinmeyen ad oldugu gibi kalir)."""
    low = key.lower()
    for k, v in LOCAL_NAME.items():
        if low.startswith(k):
            return v
    return key


def fetch_record() -> dict:
    """Zenodo kaydinin JSON metadata'sini cek."""
    req = urllib.request.Request(API, headers=H)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def md5_file(path: str, chunk: int = 1 << 20) -> str:
    """Dosyanin MD5'ini akis halinde hesapla (buyuk zip'ler icin bellek dostu)."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def expected_md5(entry: dict) -> str:
    """Zenodo ``checksum`` alanindan (``md5:...``) sade hex'i cikar."""
    return str(entry.get("checksum", "")).split(":", 1)[-1].strip()


def probe(entry: dict) -> bool:
    """Indirme URL'sini KUCUK bir Range istegiyle gercekten dene (GB indirmeden).

    ZIP dosyalarinin ilk 4 baytinin ``PK\\x03\\x04`` olmasi beklenir.
    """
    url = entry["links"]["self"]
    req = urllib.request.Request(url, headers={**H, "Range": "bytes=0-2047"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            head = r.read(2048)
            code = r.status
    except Exception as e:
        print(f"  PROBE HATA {entry['key']}: {type(e).__name__}: {str(e)[:120]}", flush=True)
        return False
    ok = head[:4] == b"PK\x03\x04"
    print(f"  probe {entry['key']}: HTTP {code}, {len(head)} bayt, "
          f"imza={'ZIP OK' if ok else head[:4]!r}", flush=True)
    return ok


def download(entry: dict, dest: str, verify: bool = True) -> bool:
    """Zip'i indir (kismi dosya varsa Range ile devam et) ve MD5 dogrula."""
    url = entry["links"]["self"]
    size = int(entry.get("size") or 0)
    have = os.path.getsize(dest) if os.path.exists(dest) else 0
    if have and have >= size:
        print(f"  zaten var: {os.path.basename(dest)} ({have/1e6:.1f} MB)", flush=True)
    else:
        headers = dict(H)
        mode = "wb"
        if have:
            headers["Range"] = f"bytes={have}-"
            mode = "ab"
            print(f"  devam ediliyor: {have/1e6:.1f}/{size/1e6:.1f} MB", flush=True)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=300) as r, open(dest, mode) as w:
                done = have
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    w.write(b)
                    done += len(b)
                    if size and done % (50 << 20) < (1 << 20):
                        print(f"    {done/1e6:.0f}/{size/1e6:.0f} MB", flush=True)
        except Exception as e:
            print(f"  indirme hatasi {entry['key']}: {type(e).__name__}: {str(e)[:140]}", flush=True)
            return False
    if not verify:
        return True
    want = expected_md5(entry)
    got = md5_file(dest)
    ok = (got == want)
    print(f"  MD5 {os.path.basename(dest)}: {got} {'== BEKLENEN (OK)' if ok else f'!= {want} (BOZUK)'}",
          flush=True)
    return ok


def extract(zip_path: str, out_root: str) -> tuple[int, int]:
    """Zip icindeki ``pos/`` ve ``neg/`` klasorlerini ``out_root`` altina ac.

    Returns:
        ``(pozitif_sayisi, negatif_sayisi)`` — yeni acilan + zaten var olan.
    """
    n_pos = n_neg = 0
    if not os.path.exists(zip_path):
        print(f"  zip yok, atlandi: {zip_path}", flush=True)
        return 0, 0
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if info.is_dir() or not name.lower().endswith((".avi", ".mp4")):
                    continue
                parts = name.split("/")
                bucket = next((p for p in parts if p in ("pos", "neg")), None)
                if bucket is None:
                    continue
                dst_dir = os.path.join(out_root, bucket)
                os.makedirs(dst_dir, exist_ok=True)
                dst = os.path.join(dst_dir, os.path.basename(name))
                if not (os.path.exists(dst) and os.path.getsize(dst) > 0):
                    with zf.open(info) as src, open(dst, "wb") as w:
                        shutil.copyfileobj(src, w, 1 << 20)
                if bucket == "pos":
                    n_pos += 1
                else:
                    n_neg += 1
    except Exception as e:
        print(f"  acma hatasi {zip_path}: {type(e).__name__}: {str(e)[:140]}", flush=True)
    return n_pos, n_neg


def build_eval(out_root: str) -> None:
    """Acilmis kliplerden degerlendirme setlerini kur (mevcut duzeni birebir uretir).

    * ``eval_scenario/Fire``  <- pos/posVideo*.avi, alfabetik ilk N_FIRE
    * ``eval_stress/Normal``  <- neg/testneg*.avi (duman zip'inin cetin negatifleri)
    """
    import glob

    pos = sorted(glob.glob(os.path.join(out_root, "pos", "posVideo*.avi")))[:N_FIRE]
    neg = sorted(glob.glob(os.path.join(out_root, "neg", "testneg*.avi")))
    for dst_dir, srcs, tag in ((FIRE_EVAL, pos, "Fire"), (STRESS_EVAL, neg, "Stress-Normal")):
        os.makedirs(dst_dir, exist_ok=True)
        n = 0
        for s in srcs:
            d = os.path.join(dst_dir, os.path.basename(s))
            if not os.path.exists(d):
                shutil.copy2(s, d)
            n += 1
        print(f"  {tag}: {n} klip -> {dst_dir}", flush=True)


def archive_zips(paths: list[str]) -> None:
    """Zip'leri SILMEZ; data/_attic/ altina tasir (geri alinabilir yer kazanimi)."""
    os.makedirs(ATTIC, exist_ok=True)
    for p in paths:
        if os.path.exists(p):
            dst = os.path.join(ATTIC, os.path.basename(p))
            shutil.move(p, dst)
            print(f"  arsivlendi (SILINMEDI): {p} -> {dst}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", "--dry-run", dest="list_only", action="store_true",
                    help="Yalnizca Zenodo dosya listesini ve planlanan islemleri goster.")
    ap.add_argument("--probe", action="store_true",
                    help="Indirme URL'lerini kucuk Range istegiyle gercekten dene (GB indirmeden).")
    ap.add_argument("--verify", action="store_true",
                    help="Yerel zip'lerin MD5'ini Zenodo checksum'i ile karsilastir.")
    ap.add_argument("--extract-only", action="store_true", help="Indirme yok; mevcut zip'lerden ac.")
    ap.add_argument("--no-verify", action="store_true", help="Indirmeden sonra MD5 dogrulamasini atla.")
    ap.add_argument("--no-build-eval", action="store_true",
                    help="eval_scenario/Fire + eval_stress/Normal kurulmasin.")
    ap.add_argument("--archive-zips", action="store_true",
                    help="Basarili acmadan sonra zip'leri data/_attic/ altina TASI (silme yok).")
    args = ap.parse_args()

    os.makedirs(DL_DIR, exist_ok=True)
    entries: list[dict] = []
    try:
        rec = fetch_record()
        entries = rec.get("files", [])
        print(f"# Zenodo {RECORD}: {rec.get('metadata', {}).get('title', '?')}", flush=True)
    except Exception as e:
        print(f"# Zenodo API'ye ulasilamadi ({type(e).__name__}: {str(e)[:120]})", flush=True)
        if not args.extract_only:
            print("# AG YOK -> yalnizca --extract-only calisabilir. Cikiliyor.", flush=True)
            return

    zips: list[str] = []
    for e in entries:
        dest = os.path.join(DL_DIR, local_name(e["key"]))
        zips.append(dest)
        have = os.path.exists(dest)
        print(f"  {e['key']:<26} {int(e.get('size') or 0)/1e6:8.1f} MB  md5={expected_md5(e)}  "
              f"yerel={'VAR' if have else 'yok'} -> {dest}", flush=True)

    if args.list_only:
        print("LISTE MODU: hicbir sey indirilmedi/acilmadi.", flush=True)
        return
    if args.probe:
        ok = all(probe(e) for e in entries)
        print(f"PROBE {'BASARILI' if ok else 'BASARISIZ'} (indirme yapilmadi).", flush=True)
        return
    if args.verify:
        allok = True
        for e in entries:
            dest = os.path.join(DL_DIR, local_name(e["key"]))
            if not os.path.exists(dest):
                print(f"  yerel dosya yok: {dest}", flush=True)
                allok = False
                continue
            got, want = md5_file(dest), expected_md5(e)
            same = got == want
            allok &= same
            print(f"  {os.path.basename(dest)}: yerel={got} zenodo={want} -> "
                  f"{'AYNI (kaynak ile birebir)' if same else 'FARKLI'}", flush=True)
        print(f"DOGRULAMA {'BASARILI' if allok else 'BASARISIZ'}", flush=True)
        return

    if not args.extract_only:
        for e in entries:
            dest = os.path.join(DL_DIR, local_name(e["key"]))
            download(e, dest, verify=not args.no_verify)
    elif not zips:  # ag yoktu; yerel zip'leri tara
        zips = [os.path.join(DL_DIR, n) for n in ("fire.zip", "smoke.zip")]

    tot_pos = tot_neg = 0
    for z in zips:
        p, n = extract(z, OUT_DIR)
        print(f"  acildi {os.path.basename(z)}: pos={p} neg={n}", flush=True)
        tot_pos += p
        tot_neg += n
    print(f"TOPLAM: pos={tot_pos} neg={tot_neg} -> {OUT_DIR}", flush=True)

    if not args.no_build_eval:
        build_eval(OUT_DIR)
    if args.archive_zips and tot_pos and tot_neg:
        archive_zips(zips)


if __name__ == "__main__":
    main()
