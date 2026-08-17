#!/usr/bin/env python
"""K14 / D19: HEDEF-DOMAIN (endustriyel tesis) ici TABAKALI degerlendirme seti kurar.

SORUN 1 (denetim bulgusu K14): sistemin hedef domeni gercek 1080p uretim tesisi
guvenlik kamerasi. Depoda bu domenden yalnizca 8 klip vardi ve 8'i de "Normal"
etiketliydi -> hedef domende SIFIR pozitif. Ustelik bu 8 klibin 4'u aslinda
GUVENSIZ davranistir (class0-3), yani etiket YANLISTI: hem recall olculemiyor
hem de yanlis-pozitif orani oldugundan dusuk cikiyordu.

SORUN 2 (D19, ISTATISTIKSEL GUC): K14 ile kurulan set sinif basina 5 klip = 20
anomali + 20 normal idi. Olculen facility_rules A/B sonucu: kurallar KAPALI
recall %25 (5/20) -> ACIK %55 (11/20); eslestirilmis McNemar recall 8-2
(p=0.109), kategori 5-0 (p=0.063). YON TUTARLI ama n=20'de ANLAMLI DEGIL.
Ayni 8-2 oruntusu n=100 anomalide (oransal 40-10) p<0.001'e tasinir.
-> Bu betik artik sinif basina N_PER_CLASS (varsayilan 25) klip secer:
   100 anomali (class0-3) + 100 normal (class4-7) = 200 klip.

ESLEME (kaynak/dogrulama: data/industrial/CLASSES.md — Mendeley API sayimlari
Data in Brief makalesinin sinif tablosuyla 8/8 birebir ortusuyor):
    class0-3 (Safe Walkway Violation, Unauthorized Intervention,
              Opened Panel Cover, Carrying Overload with Forklift)   -> ANOMALI
    class4-7 (Safe Walkway, Authorized Intervention,
              Closed Panel Cover, Safe Carrying)                     -> NORMAL

CIKTI
  data/eval_defense/Anomali/<sinif_adi>/*.mp4      <- ust klasor = ETIKET
  data/eval_defense/Normal/<sinif_adi>/*.mp4          (benchmark/eval_clips.py ic ice tarar)
  data/eval_defense/MANIFEST.json                  <- secim, tohum, havuz parmak izi,
                                                      sizinti raporu, v1 iliskisi, lisans
  data/eval_defense_v1/                            <- ilk 40-klip setin DONMUS kopyasi

GARANTILER
  1) TABAKALI: her sinif icin ayni kota (havuz yetmezse mevcut olan + NET eksik raporu;
     sessizce azaltma YOK).
  2) DETERMINISTIK: sabit tohumlu rastgele orneklem (_sampling.sample_paths_pinned).
     "En kucuk N" yanliligina DUSULMEZ. Ayni tohum + ayni havuz -> ayni secim; havuz
     parmak izi manifest'e yazilir (indirme surerken havuz buyuyebilir).
  3) UST KUME: eski 40-klip set (v1) yeni setin ICINDE sabitlenir (pinned) -> eski olcum
     yeni setin ALT KUMESI kalir, karsilastirilabilir. Ayrica v1 ayrica DONDURULUR.
  4) SIZINTI KONTROLU: ayni klip baska bir degerlendirme setinde (eval_big/tune/holdout/
     scenario/stress) varsa RAPORLANIR ve yeni secimlerde KULLANILMAZ (capraz sayim onlemi).
  5) SILME YOK: klipler hardlink'lenir (olmazsa kopyalanir); kaynak dizin durur.
     Plana girmeyen artik ("yetim") dosyalar RAPORLANIR, silinmez.

Kullanim:
  python scripts/build_defense_eval.py --list              # 200-klip plani (dosya yazmaz)
  python scripts/build_defense_eval.py --list --json       # makine okunur plan (diff icin)
  python scripts/build_defense_eval.py                     # diskteki kliplerle kur
  python scripts/build_defense_eval.py --target-total 200   # toplam hedefle
  N_PER_CLASS=25 python scripts/build_defense_eval.py --fetch   # eksikleri indir + kur
  python scripts/build_defense_eval.py --leak-policy strict     # sizintili v1 klibini de disla

Tam havuzdan (yanlisiz) orneklem icin once TUM seti indirin (~10 GB):
  N_PER_CLASS=999 JOBS=8 python scripts/get_industrial.py
"""
from __future__ import annotations

import argparse
import datetime
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys

from _sampling import DEFAULT_SEED, env_str, get_seed, pool_fingerprint, sample_paths_pinned

#: depo koku (betik nereden kosturulursa kosturulsun goreli yollar cozulebilsin)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SRC = env_str("INDUSTRIAL_OUT", os.path.join("data", "industrial"))
OUT = env_str("DEFENSE_OUT", os.path.join("data", "eval_defense"))
#: v1 (ilk 40-klip) setin dondurulacagi dizin
V1_OUT = env_str("DEFENSE_V1_OUT", os.path.join("data", "eval_defense_v1"))

#: sinif basina sete alinacak klip sayisi. 0 -> diskteki HEPSI.
#: Varsayilan 25 -> 8 sinif x 25 = 200 klip (100 anomali + 100 normal).
DEFAULT_N_PER_CLASS = 25
#: toplam hedef (verilirse siniflara esit bolunur; artan ilk siniflara gider)
DEFAULT_TARGET_TOTAL = 0

#: sizinti taranacak DIGER degerlendirme setleri (goreli yollar; ',' ile ayrilir)
DEFAULT_LEAK_DIRS = ("data/eval,data/eval_big,data/eval_tune,data/eval_holdout,"
                     "data/eval_scenario,data/eval_stress")
#: video uzantilari (sizinti taramasi icin)
VIDEO_EXT = (".mp4", ".avi", ".mkv", ".mov", ".mpg", ".mpeg")

#: sinif -> (ad, etiket). Kaynak/dogrulama: data/industrial/CLASSES.md
CLASS_MAP: dict[str, tuple[str, str]] = {
    "0": ("Safe_Walkway_Violation", "Anomali"),
    "1": ("Unauthorized_Intervention", "Anomali"),
    "2": ("Opened_Panel_Cover", "Anomali"),
    "3": ("Carrying_Overload_with_Forklift", "Anomali"),
    "4": ("Safe_Walkway", "Normal"),
    "5": ("Authorized_Intervention", "Normal"),
    "6": ("Closed_Panel_Cover", "Normal"),
    "7": ("Safe_Carrying", "Normal"),
}

#: Mendeley API "CC BY" diyor, Data in Brief makalesi "CC BY-NC" diyor -> celiskili.
#: MUHAFAZAKAR okuma: NC (ticari kullanim YOK, atif zorunlu).
LICENSE_NOTE = ("https://data.mendeley.com/datasets/xjmtb22pff — lisans CELISKILI: "
                "Mendeley API=CC BY 4.0, Data in Brief makalesi=CC BY-NC. MUHAFAZAKAR "
                "okuma benimsendi: CC BY-NC (TICARI KULLANIM YOK, atif zorunlu).")


# --------------------------------------------------------------------------- #
# yol yardimcilari
# --------------------------------------------------------------------------- #
def anchor(path: str, *, must_exist: bool = True) -> str:
    """Goreli yolu once CWD'ye, bulunamazsa DEPO KOKUNE gore coz (FAIL-OPEN).

    Betik hem depo kokunden hem baska bir dizinden kosturulabilir; goreli
    ``data/...`` yollari her iki durumda da dogru yeri gostermeli.
    """
    if os.path.isabs(path):
        return path
    if os.path.exists(path):
        return path
    cand = os.path.join(ROOT, path)
    if os.path.exists(cand) or not must_exist:
        return cand
    return path


def env_int(name: str, default: int) -> int:
    """Ortam degiskenini tam sayi olarak oku; bos/bozuksa varsayilana FAIL-OPEN don."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        print(f"# UYARI: {name}={raw!r} sayi degil -> varsayilan {default} kullanildi", flush=True)
        return default


def rel(path: str) -> str:
    """Depo kokune goreli, '/' ayirici yol (manifest'te kararli gosterim)."""
    try:
        return os.path.relpath(path, ROOT).replace("\\", "/")
    except ValueError:          # farkli surucu (Windows) -> mutlak yolu koru
        return path.replace("\\", "/")


def md5(path: str, chunk: int = 1 << 20, _cache: dict[str, str] | None = None) -> str:
    """Dosya MD5'i (akis halinde, istege bagli onbellekli)."""
    if _cache is not None and path in _cache:
        return _cache[path]
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    digest = h.hexdigest()
    if _cache is not None:
        _cache[path] = digest
    return digest


# --------------------------------------------------------------------------- #
# havuz + hedef
# --------------------------------------------------------------------------- #
def on_disk(src: str) -> dict[str, list[str]]:
    """``{sinif: [yol, ...]}`` — diskteki endustriyel klipler (bos/yarim dosyalar HARIC).

    ``.part`` uzantili yarim indirmeler ve 0-bayt dosyalar havuza ALINMAZ; aksi halde
    indirme surerken bozuk klip sete girer.
    """
    found: dict[str, list[str]] = {}
    for cls in sorted(CLASS_MAP):
        paths = []
        for p in sorted(glob.glob(os.path.join(src, f"class{cls}", "*.mp4"))):
            try:
                if os.path.getsize(p) > 0:
                    paths.append(p)
            except OSError:
                continue
        found[cls] = paths
    return found


def resolve_targets(n_per_class: int, target_total: int) -> tuple[dict[str, int], str]:
    """Sinif basina hedef kotayi belirle -> ``({sinif: kota}, aciklama)``.

    ``target_total`` verilirse siniflara ESIT bolunur; bolunemeyen artan sinif
    numarasi sirasiyla ilk siniflara dagitilir (deterministik).
    """
    classes = sorted(CLASS_MAP)
    if target_total and target_total > 0:
        base, rem = divmod(target_total, len(classes))
        tgt = {c: base + (1 if i < rem else 0) for i, c in enumerate(classes)}
        note = f"TARGET_TOTAL={target_total} -> sinif basina {base}" + (f" (+1 x {rem})" if rem else "")
        return tgt, note
    if n_per_class <= 0:
        return {c: 0 for c in classes}, "N_PER_CLASS=0 -> diskteki TUM klipler"
    return {c: n_per_class for c in classes}, (f"N_PER_CLASS={n_per_class} -> "
                                               f"TOPLAM {n_per_class * len(classes)}")


# --------------------------------------------------------------------------- #
# sizinti (capraz-sayim) taramasi
# --------------------------------------------------------------------------- #
def leak_index(dirs: list[str]) -> tuple[dict[str, list[str]], dict[int, list[str]]]:
    """Diger degerlendirme setlerini tara -> ``({dosya_adi: [yol]}, {boyut: [yol]})``.

    ``_`` ile baslayan klasorler ATLANIR: bunlar KARANTINA/metadata'dir, olcume
    girmez (or. ``data/_mislabeled_unsafe``, ``eval_scenario/_deprecated_frozen_fall``)
    — benchmark/eval_clips.py ile ayni kural. Karantinayi sizinti saymak yanlis
    alarm uretirdi.
    """
    by_name: dict[str, list[str]] = {}
    by_size: dict[int, list[str]] = {}
    for d in dirs:
        base = anchor(d.strip())
        if not d.strip() or not os.path.isdir(base):
            continue
        if os.path.basename(base.rstrip("/\\")).startswith("_"):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if not x.startswith("_")]
            for fn in filenames:
                if not fn.lower().endswith(VIDEO_EXT):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    size = os.path.getsize(p)
                except OSError:
                    continue
                by_name.setdefault(fn, []).append(p)
                by_size.setdefault(size, []).append(p)
    return by_name, by_size


def find_leaks(pool: dict[str, list[str]], idx: tuple[dict[str, list[str]], dict[int, list[str]]],
               *, verify_md5: bool = True) -> dict[str, list[str]]:
    """Havuzdaki hangi klipler BASKA setlerde de var? -> ``{dosya_adi: [karsi yol, ...]}``.

    Iki asamali: (1) dosya adi eslesmesi (Mendeley adlari ayirt edici: ``4_te16.mp4``),
    (2) ad eslesmesi yoksa AYNI BOYUTtaki adaylar MD5 ile dogrulanir (yeniden
    adlandirilmis kopyalari yakalar). MD5 yalnizca boyut cakismasinda hesaplanir ->
    tarama ucuz kalir.
    """
    by_name, by_size = idx
    cache: dict[str, str] = {}
    leaks: dict[str, list[str]] = {}
    for paths in pool.values():
        for p in paths:
            name = os.path.basename(p)
            hits = list(by_name.get(name, []))
            if not hits and verify_md5:
                try:
                    same_size = by_size.get(os.path.getsize(p), [])
                except OSError:
                    same_size = []
                if 0 < len(same_size) <= 8:          # patlamayi onle
                    for q in same_size:
                        try:
                            if md5(p, _cache=cache) == md5(q, _cache=cache):
                                hits.append(q)
                        except OSError:
                            continue
            if hits:
                leaks[name] = sorted({rel(h) for h in hits})
    return leaks


# --------------------------------------------------------------------------- #
# v1 (eski 40-klip set) surekliligi
# --------------------------------------------------------------------------- #
def _names_from_manifest(mpath: str) -> dict[str, list[str]]:
    """Manifest'ten ``{sinif: [dosya_adi]}`` cikar (v1 anahtari varsa onu tercih eder)."""
    try:
        with open(mpath, encoding="utf-8") as f:
            man = json.load(f)
    except Exception:
        return {}
    v1 = man.get("v1") or {}
    if isinstance(v1.get("klipler"), dict) and v1["klipler"]:
        return {str(k): sorted(v) for k, v in v1["klipler"].items()}
    out: dict[str, list[str]] = {}
    for row in man.get("klipler") or []:
        cls = str(row.get("sinif", ""))
        ad = row.get("ad")
        if cls and ad:
            out.setdefault(cls, []).append(ad)
    return {k: sorted(v) for k, v in out.items()}


def _names_from_tree(root: str) -> dict[str, list[str]]:
    """Dizin agacindan ``{sinif: [dosya_adi]}`` cikar (dosya adi oneki = sinif)."""
    out: dict[str, list[str]] = {}
    if not os.path.isdir(root):
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [x for x in dirnames if not x.startswith("_")]
        for fn in filenames:
            if not fn.lower().endswith(VIDEO_EXT):
                continue
            cls = fn.split("_")[0]
            if cls in CLASS_MAP:
                out.setdefault(cls, []).append(fn)
    return {k: sorted(set(v)) for k, v in out.items()}


def load_v1(out_dir: str, v1_dir: str) -> tuple[dict[str, list[str]], str]:
    """v1 setinin sinif basina dosya adlarini ve KAYNAGINI dondur.

    Oncelik sirasi (en guvenilir once):
      1. dondurulmus ``data/eval_defense_v1/MANIFEST.json``
      2. dondurulmus v1 dizin agaci
      3. mevcut ``data/eval_defense/MANIFEST.json`` icindeki ``v1`` kaydi
      4. mevcut manifest'in klip listesi (ILK kurulumda mevcut set = v1)
      5. mevcut dizin agaci
    """
    v1_man = os.path.join(v1_dir, "MANIFEST.json")
    if os.path.isfile(v1_man):
        got = _names_from_manifest(v1_man)
        if got:
            return got, f"{rel(v1_man)} (dondurulmus)"
    got = _names_from_tree(v1_dir)
    if got:
        return got, f"{rel(v1_dir)} (dondurulmus dizin)"
    cur_man = os.path.join(out_dir, "MANIFEST.json")
    if os.path.isfile(cur_man):
        got = _names_from_manifest(cur_man)
        if got:
            return got, rel(cur_man)
    got = _names_from_tree(out_dir)
    if got:
        return got, f"{rel(out_dir)} (dizin taramasi)"
    return {}, "yok (v1 bulunamadi — ilk kurulum)"


def freeze_v1(out_dir: str, v1_dir: str) -> str:
    """Mevcut seti ``data/eval_defense_v1`` altina DONDUR (video=hardlink, metin=kopya).

    MANIFEST.json KOPYALANIR, hardlink'lenmez: ayni inode olsa yeni manifest yazimi
    (``open(..., "w")``) dondurulmus kopyayi da EZERDI.
    Var olan v1 dizinine DOKUNULMAZ (dondurulmus = dondurulmus).
    """
    if not os.path.isdir(out_dir):
        return "kaynak set yok — dondurulacak bir sey yok"
    if os.path.isdir(v1_dir) and any(os.scandir(v1_dir)):
        return f"zaten dondurulmus: {rel(v1_dir)} (dokunulmadi)"
    n_link = n_copy = 0
    for dirpath, _dirnames, filenames in os.walk(out_dir):
        sub = os.path.relpath(dirpath, out_dir)
        dst_dir = v1_dir if sub == "." else os.path.join(v1_dir, sub)
        os.makedirs(dst_dir, exist_ok=True)
        for fn in filenames:
            src, dst = os.path.join(dirpath, fn), os.path.join(dst_dir, fn)
            if os.path.exists(dst):
                continue
            if fn.lower().endswith(VIDEO_EXT):
                try:
                    os.link(src, dst)
                    n_link += 1
                    continue
                except Exception:
                    pass
            shutil.copy2(src, dst)
            n_copy += 1
    return f"donduruldu -> {rel(v1_dir)} ({n_link} hardlink, {n_copy} kopya)"


# --------------------------------------------------------------------------- #
# indirme (istege bagli)
# --------------------------------------------------------------------------- #
def fetch_missing(need: int) -> None:
    """Eksik klipleri get_industrial.py ile indirmeyi dene (ag gerekir, GPU gerekmez)."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "get_industrial.py")
    env = dict(os.environ, N_PER_CLASS=str(need))
    print(f"# eksikler indiriliyor: N_PER_CLASS={need}\n"
          f"#   NOT: yanlisiz orneklem icin TUM havuz onerilir: "
          f"N_PER_CLASS=999 JOBS=8 python scripts/get_industrial.py", flush=True)
    try:
        subprocess.run([sys.executable, script], env=env, check=False)
    except Exception as e:
        print(f"  indirme calistirilamadi: {type(e).__name__}: {str(e)[:120]}", flush=True)


# --------------------------------------------------------------------------- #
# ana akis
# --------------------------------------------------------------------------- #
def build_plan(disk: dict[str, list[str]], targets: dict[str, int],
               sabitler: dict[str, list[str]], leaks: dict[str, list[str]],
               *, seed: int, pin: bool, leak_policy: str) -> dict[str, dict]:
    """Sinif basina secimi ve muhasebesini uret (dosya YAZMAZ).

    Args:
        disk: ``{sinif: [havuz yolu]}``.
        targets: ``{sinif: kota}`` (0 -> hepsi).
        sabitler: ``{sinif: [zorunlu dosya adi]}`` — v1 (+ istege bagli --pin-existing).
        leaks: ``{dosya_adi: [karsi set yolu]}``.
        pin: sabitleme acik mi (``--no-pin-v1`` ile kapatilir).
        leak_policy: avoid | report | strict.
    """
    plan: dict[str, dict] = {}
    for cls in sorted(CLASS_MAP):
        name, label = CLASS_MAP[cls]
        pool = disk.get(cls, [])
        on_disk_names = {os.path.basename(p) for p in pool}
        want = sorted(sabitler.get(cls, [])) if pin else []
        # sabitlenmesi gerekip diskte OLMAYAN klip -> ust kume kirilir, raporlanir
        sabit_eksik = [n for n in want if n not in on_disk_names]
        pinned = [n for n in want if n in on_disk_names]
        # 'strict': sizintili sabit klip de sabitlenmez (ust kume BILEREK kirilir)
        sabit_sizintili = [n for n in pinned if n in leaks]
        if leak_policy == "strict":
            pinned = [n for n in pinned if n not in leaks]
        exclude = list(leaks) if leak_policy in ("avoid", "strict") else []
        picked = sample_paths_pinned(pool, targets[cls], f"defense{cls}",
                                     pinned=pinned, exclude=exclude, seed=seed)
        tgt = targets[cls]
        # sizinti nedeniyle rastgele doldurmada KULLANILAMAYAN aday sayisi
        pinned_set, exclude_set = set(pinned), set(exclude)
        blocked = sum(1 for p in pool if os.path.basename(p) in exclude_set
                      and os.path.basename(p) not in pinned_set)
        plan[cls] = {
            "sinif": cls, "sinif_adi": name, "etiket": label,
            "havuz": len(pool), "havuz_parmak_izi": pool_fingerprint(pool),
            "hedef": tgt, "secilen": picked,
            "sabit": pinned, "sabit_diskte_yok": sabit_eksik, "sabit_sizintili": sabit_sizintili,
            "sizinti_ile_elenen_aday": blocked,
            "eksik": max(0, tgt - len(picked)) if tgt > 0 else 0,
        }
    return plan


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", "--dry-run", dest="dry", action="store_true",
                    help="Dosya olusturma; yalnizca plani goster.")
    ap.add_argument("--json", action="store_true",
                    help="Plani makine-okunur JSON olarak da bas (tekrar-uretilebilirlik diff'i icin).")
    ap.add_argument("--n-per-class", type=int, default=None,
                    help=f"Sinif basina klip (varsayilan: N_PER_CLASS ya da {DEFAULT_N_PER_CLASS}; 0 -> hepsi).")
    ap.add_argument("--target-total", type=int, default=None,
                    help="Toplam hedef (siniflara esit bolunur). Or. 200.")
    ap.add_argument("--seed", type=int, default=None,
                    help=f"Orneklem tohumu (varsayilan: EVAL_SEED ya da {DEFAULT_SEED}).")
    ap.add_argument("--leak-policy", choices=("avoid", "report", "strict"), default=None,
                    help="avoid(varsayilan): sizintili klipleri YENI secimde kullanma; "
                         "report: yalnizca raporla; strict: sizintili v1 klibini de disla "
                         "(ust kume ozelligi BILEREK kirilir).")
    ap.add_argument("--no-leak-check", action="store_true",
                    help="Sizinti taramasini atla (hizli; capraz-sayim riski RAPORLANMAZ).")
    ap.add_argument("--no-pin-v1", action="store_true",
                    help="Eski 40-klip seti sabitleme (yeni set eski setin ust kumesi OLMAZ).")
    ap.add_argument("--pin-existing", action="store_true",
                    help="v1'in yaninda cikti dizinindeki TUM mevcut klipleri de sabitle "
                         "(set yalnizca BUYUR, yetim dosya olusmaz). DIKKAT: indirme surerken "
                         "kurulmus bir set boylece kalicilasir -> 'ilk indirilenler' yanliligi.")
    ap.add_argument("--no-freeze-v1", action="store_true",
                    help="Mevcut seti data/eval_defense_v1 altina dondurma.")
    ap.add_argument("--freeze-only", action="store_true",
                    help="YALNIZCA mevcut seti data/eval_defense_v1 altina dondur ve cik "
                         "(cikti seti DEGISTIRILMEZ; indirme surerken guvenli).")
    ap.add_argument("--copy", action="store_true",
                    help="Hardlink yerine KOPYALA (ayri dosya sistemi / yedekleme icin).")
    ap.add_argument("--fetch", action="store_true",
                    help="Eksik klipleri scripts/get_industrial.py ile indirmeyi dene (ag gerekir).")
    args = ap.parse_args()

    # --- ayarlar: CLI > ortam > varsayilan ---
    n_per_class = (args.n_per_class if args.n_per_class is not None
                   else env_int("N_PER_CLASS", DEFAULT_N_PER_CLASS))
    target_total = (args.target_total if args.target_total is not None
                    else env_int("TARGET_TOTAL", DEFAULT_TARGET_TOTAL))
    seed = args.seed if args.seed is not None else get_seed()
    leak_policy = args.leak_policy or env_str("LEAK_POLICY", "avoid")
    if leak_policy not in ("avoid", "report", "strict"):
        print(f"# UYARI: LEAK_POLICY={leak_policy!r} taninmadi -> 'avoid' kullanildi", flush=True)
        leak_policy = "avoid"
    src = anchor(SRC)
    out = anchor(OUT, must_exist=False)
    v1_dir = anchor(V1_OUT, must_exist=False)
    leak_dirs = [d for d in env_str("LEAK_DIRS", DEFAULT_LEAK_DIRS).split(",") if d.strip()]
    targets, tgt_note = resolve_targets(n_per_class, target_total)

    if args.fetch and not args.dry:
        fetch_missing(max(targets.values()) if max(targets.values()) > 0 else 999)

    disk = on_disk(src)
    v1, v1_src = load_v1(out, v1_dir)
    v1_adlar = {a for v in v1.values() for a in v}
    n_v1 = len(v1_adlar)
    # Sabitlenecekler = v1 (+ istege bagli mevcut cikti seti). v1 sozlugu KIRLETILMEZ:
    # manifest'te "v1" alani gercek v1'i, "ek_sabitlenen" ise fazlasini gosterir.
    sabitler: dict[str, list[str]] = {c: sorted(v) for c, v in v1.items()}
    pin_extra: dict[str, list[str]] = {}
    if args.pin_existing:
        for cls, adlar in _names_from_tree(out).items():
            yeni = sorted(set(adlar) - set(v1.get(cls, [])))
            if yeni:
                pin_extra[cls] = yeni
            sabitler[cls] = sorted(set(sabitler.get(cls, [])) | set(adlar))
    n_extra = sum(len(v) for v in pin_extra.values())

    leaks: dict[str, list[str]] = {}
    if not args.no_leak_check:
        leaks = find_leaks(disk, leak_index(leak_dirs))

    plan = build_plan(disk, targets, sabitler, leaks, seed=seed,
                      pin=not args.no_pin_v1, leak_policy=leak_policy)

    # --- rapor ---
    print(f"# kaynak={rel(src)}  cikti={rel(out)}  tohum(seed)={seed}", flush=True)
    print(f"# hedef: {tgt_note}", flush=True)
    print(f"# v1 surekliligi: {'KAPALI' if args.no_pin_v1 else 'ACIK (pinned)'}  "
          f"kaynak={v1_src}  v1_klip={n_v1}"
          + (f"  + ek sabitlenen {n_extra} klip (--pin-existing)" if n_extra else ""), flush=True)
    print(f"# sizinti politikasi: {leak_policy}  "
          f"taranan: {', '.join(leak_dirs) if not args.no_leak_check else 'TARAMA KAPALI'}", flush=True)
    print(f"# baglama: {'KOPYA' if args.copy else 'hardlink (olmazsa kopya)'}", flush=True)

    hdr = (f"\n{'sinif':<8}{'ad':<34}{'etiket':<9}{'havuz':>6}{'hedef':>7}"
           f"{'sabit':>7}{'sizinti':>9}{'secilen':>9}{'eksik':>7}")
    print(hdr, flush=True)
    print("-" * len(hdr.strip("\n")), flush=True)

    rows: list[dict] = []
    n_anom = n_norm = n_eksik = 0
    for cls in sorted(CLASS_MAP):
        p = plan[cls]
        print(f"class{cls:<3}{p['sinif_adi']:<34}{p['etiket']:<9}{p['havuz']:>6}"
              f"{p['hedef'] or '-':>7}{len(p['sabit']):>7}"
              f"{p['sizinti_ile_elenen_aday']:>9}{len(p['secilen']):>9}"
              f"{p['eksik'] or '-':>7}", flush=True)
        for path in p["secilen"]:
            ad = os.path.basename(path)
            rows.append({"sinif": cls, "sinif_adi": p["sinif_adi"], "etiket": p["etiket"],
                         "kaynak": rel(path), "ad": ad,
                         "v1": ad in v1_adlar,
                         "diger_setlerde_de_var": leaks.get(ad, [])})
        if p["etiket"] == "Anomali":
            n_anom += len(p["secilen"])
        else:
            n_norm += len(p["secilen"])
        n_eksik += p["eksik"]

    print("-" * len(hdr.strip("\n")), flush=True)
    hedef_toplam = sum(targets.values())
    print(f"{'TOPLAM':<51}{sum(len(v) for v in disk.values()):>6}"
          f"{hedef_toplam or '-':>7}{sum(len(plan[c]['sabit']) for c in plan):>7}"
          f"{sum(plan[c]['sizinti_ile_elenen_aday'] for c in plan):>9}"
          f"{n_anom + n_norm:>9}{n_eksik or '-':>7}", flush=True)
    print(f"\nANOMALI (guvensiz, class0-3) = {n_anom}   NORMAL (guvenli, class4-7) = {n_norm}"
          f"   TOPLAM = {n_anom + n_norm}"
          + (f"   (hedef {hedef_toplam})" if hedef_toplam else ""), flush=True)

    # --- v1 ust kume denetimi ---
    if n_v1 and not args.no_pin_v1:
        secilen_adlar = {os.path.basename(x) for cls in plan for x in plan[cls]["secilen"]}
        disarida = sorted(v1_adlar - secilen_adlar)
        if disarida:
            print(f"\n!! v1 UST KUME KIRILDI: {len(disarida)}/{len(v1_adlar)} eski klip yeni sette YOK "
                  f"-> eski olcum yeni setin alt kumesi DEGIL: {', '.join(disarida[:12])}"
                  + (" ..." if len(disarida) > 12 else ""), flush=True)
        else:
            print(f"\nv1 UST KUME: {len(v1_adlar)}/{len(v1_adlar)} eski klip yeni setin ICINDE "
                  f"-> eski olcum yeni setin ALT KUMESI (karsilastirilabilir).", flush=True)

    # --- sizinti raporu ---
    if args.no_leak_check:
        print("\nUYARI: sizinti taramasi KAPALI — bu setle baska bir setin ayni klibi "
              "iki kez sayilabilir (capraz sayim).", flush=True)
    elif leaks:
        secilen_adlar = {os.path.basename(x) for cls in plan for x in plan[cls]["secilen"]}
        sizan_secili = sorted(n for n in leaks if n in secilen_adlar)
        print(f"\n!! SIZINTI: havuzdaki {len(leaks)} klip BASKA degerlendirme setlerinde de var; "
              f"bunlardan {len(sizan_secili)} tanesi bu sette de SECILI:", flush=True)
        for nm in sizan_secili:
            print(f"   - {nm:<16} <-> {', '.join(leaks[nm])}", flush=True)
        if sizan_secili:
            print("   ETKI: bu klipler eval_defense ve digerinde AYNI dosyadir; iki setin "
                  "sonuclari TOPLANARAK raporlanirsa capraz sayim olur. Ayri ayri "
                  "raporlanmalari sorun degil.", flush=True)
            if leak_policy != "strict":
                print("   POLITIKA(avoid): YENI secimler sizintisiz adaylardan yapildi; "
                      "yukaridakiler v1 surekliligi icin KORUNDU (--leak-policy strict ile "
                      "bunlar da dislanir, ama v1 ust kume ozelligi kirilir).", flush=True)
    else:
        print("\nSIZINTI: yok — secilen kliplerin hicbiri diger degerlendirme setlerinde bulunmuyor.",
              flush=True)

    # --- eksik raporu (SESSIZ AZALTMA YOK) ---
    bos = [f"class{c}" for c in sorted(CLASS_MAP) if not disk.get(c)]
    if bos:
        print(f"\n!! EKSIK: {', '.join(bos)} icin diskte klip YOK.", flush=True)
    if n_eksik:
        det = ", ".join(f"class{c}: {plan[c]['eksik']}" for c in sorted(CLASS_MAP) if plan[c]["eksik"])
        print(f"\n!! HEDEFE ULASILMADI: {n_anom + n_norm}/{hedef_toplam} klip "
              f"(EKSIK {n_eksik}). Sinif basina eksik -> {det}", flush=True)
        print("   Havuz buyudukce hedef kendiliginden dolar. Tum seti indirmek icin:\n"
              "     N_PER_CLASS=999 JOBS=8 python scripts/get_industrial.py\n"
              "   (Mendeley havuz ust siniri: class0=210 1=108 2=142 3=56 4=75 5=38 6=32 7=30 "
              "-> sinif basina 25 hedefi TUM siniflar icin ULASILABILIR.)", flush=True)
    if n_anom == 0:
        print("!! HEDEF DOMENDE HALA SIFIR POZITIF VAR — set anlamli degil.", flush=True)
    if 0 < n_anom < 50:
        print(f"\nUYARI (istatistiksel guc): n_anomali={n_anom}. Olculen 8-2 McNemar oruntusu "
              f"n=20'de p=0.109 ile ANLAMSIZ kalir; p<0.05 icin ~100 anomali gerekir. "
              f"Bu setle uretilen oranlari Wilson GA'siz raporlamayin.", flush=True)

    # --- yetim (plana girmeyen ama cikti dizininde duran) dosyalar ---
    mevcut = _names_from_tree(out)
    plan_adlar = {os.path.basename(x) for cls in plan for x in plan[cls]["secilen"]}
    yetim = sorted({a for v in mevcut.values() for a in v} - plan_adlar)
    if yetim:
        print(f"\n!! YETIM DOSYA: {rel(out)} altinda plana girmeyen {len(yetim)} klip var "
              f"(sebep: onceki kurulum farkli tohum/kota ile ya da HAVUZ BUYUMEDEN ONCE yapilmis): "
              f"{', '.join(yetim[:12])}" + (" ..." if len(yetim) > 12 else ""), flush=True)
        print("   Bu betik SILMEZ. eval_clips.py bunlari da olcer -> set tanimi bulanir. Secenekler:\n"
              "     (a) dizini elle bosaltip yeniden kurun (temiz, onerilen),\n"
              "     (b) DEFENSE_OUT=<yeni dizin> ile ayri set kurun,\n"
              "     (c) --pin-existing ile mevcutlari da sabitleyin (set yalnizca buyur; "
              "ama 'ilk indirilenler' yanliligi girer).", flush=True)

    if args.json:
        print("\n--- PLAN (JSON) ---", flush=True)
        print(json.dumps({
            "seed": seed, "hedef_toplam": hedef_toplam, "hedef_notu": tgt_note,
            "sizinti_politikasi": leak_policy, "pin_v1": not args.no_pin_v1,
            "siniflar": {c: {"havuz": plan[c]["havuz"],
                             "havuz_parmak_izi": plan[c]["havuz_parmak_izi"],
                             "hedef": plan[c]["hedef"],
                             "secilen": [os.path.basename(x) for x in plan[c]["secilen"]]}
                         for c in sorted(CLASS_MAP)},
            "anomali": n_anom, "normal": n_norm, "eksik": n_eksik,
            "sizinti": {k: v for k, v in sorted(leaks.items())},
        }, indent=1, ensure_ascii=False, sort_keys=True), flush=True)

    if args.dry:
        print("\nLISTE MODU: hicbir dosya olusturulmadi/degistirilmedi.", flush=True)
        return
    if args.freeze_only:
        # Yalnizca v1'i dondur: cikti seti (data/eval_defense) DEGISTIRILMEZ.
        # Indirme surerken kullanilir -> olculmus 40-klip set kaybolmadan guvenceye alinir.
        print(f"\nv1 dondurma: {freeze_v1(out, v1_dir)}", flush=True)
        print("FREEZE-ONLY: cikti seti degistirilmedi (kurulum icin bayragi kaldirin).", flush=True)
        return
    if not rows:
        print("\nkurulacak klip yok — cikiliyor.", flush=True)
        return

    # --- v1'i DONDUR (yeni kurulum eski seti ezmesin) ---
    v1_durum = "atlandi (--no-freeze-v1)" if args.no_freeze_v1 else freeze_v1(out, v1_dir)
    print(f"\nv1 dondurma: {v1_durum}", flush=True)

    # --- kur: hardlink (olmazsa kopya) ---
    n_link = n_copy = 0
    for i, r in enumerate(rows, 1):
        d = os.path.join(out, r["etiket"], r["sinif_adi"])
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, r["ad"])
        srcp = os.path.join(ROOT, r["kaynak"])
        if not os.path.exists(dst):
            if args.copy:
                shutil.copy2(srcp, dst)
                n_copy += 1
            else:
                try:
                    os.link(srcp, dst)
                    n_link += 1
                except Exception:
                    shutil.copy2(srcp, dst)
                    n_copy += 1
        r["hedef"] = rel(dst)
        r["md5"] = md5(dst)
        r["boyut"] = os.path.getsize(dst)
        if i % 50 == 0:
            print(f"  [{i}/{len(rows)}] kuruldu/dogrulandi", flush=True)

    manifest = {
        "_aciklama": ("K14 + D19: hedef-domain (Eskisehir uretim tesisi, Mendeley xjmtb22pff) ici "
                      "TABAKALI degerlendirme seti. class0-3 = GUVENSIZ -> Anomali, "
                      "class4-7 = GUVENLI -> Normal. Esleme dogrulamasi: data/industrial/CLASSES.md. "
                      "Etiket = UST klasor (Anomali/Normal); alt klasor yalnizca KOKEN bilgisidir."),
        "kaynak_veri_seti": LICENSE_NOTE,
        "lisans_muhafazakar_okuma": "CC BY-NC 4.0 (ticari kullanim YOK, atif zorunlu)",
        "kurulum_zamani_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "seed": seed,
        "hedef": {"notu": tgt_note, "sinif_basina": targets, "toplam": hedef_toplam},
        "orneklem_yontemi": ("sabit tohumlu rastgele (scripts/_sampling.sample_paths_pinned); "
                             "'en kucuk N' yanliligi YOK. Ayni tohum + ayni havuz -> ayni secim; "
                             "havuz parmak izi sinif basina kayitli (indirme surerken havuz buyur)."),
        "baglama_yontemi": ("KOPYA (--copy)" if args.copy else
                            "hardlink (olmazsa kopya) — diski korur, kaynak data/industrial durur. "
                            "MD5-dedup acisindan sorun degil: hardlink kaynak dizinle AYNI dosyadir, "
                            "ama benchmark/dedup.py yalnizca TEK setin ICINDEKI ayni-MD5 klipleri "
                            "eler; kaynak dizin ayri set oldugu icin secilen klip elenmez."),
        "anomali_sayisi": n_anom,
        "normal_sayisi": n_norm,
        "toplam": n_anom + n_norm,
        "eksik_toplam": n_eksik,
        "olcum_notu": ("D19 gerekcesi: 20 anomali + 20 normal ile olculen facility_rules A/B'de "
                       "recall %25 -> %55 ve eslestirilmis McNemar recall 8-2 (p=0.109), kategori "
                       "5-0 (p=0.063) cikti: YON TUTARLI ama n=20'de ANLAMLI DEGIL. n=100 anomalide "
                       "ayni orantili oruntu (40-10) p<0.001'e tasinir. Bkz. "
                       "docs/olcum_2026-07-26_kusur_sonrasi.md"),
        "sinif_eslemesi": {f"class{k}": {"ad": v[0], "etiket": v[1]} for k, v in CLASS_MAP.items()},
        "sinif_ozeti": {f"class{c}": {
            "ad": plan[c]["sinif_adi"], "etiket": plan[c]["etiket"],
            "havuz": plan[c]["havuz"], "havuz_parmak_izi": plan[c]["havuz_parmak_izi"],
            "hedef": plan[c]["hedef"], "secilen": len(plan[c]["secilen"]),
            "eksik": plan[c]["eksik"], "sabit": len(plan[c]["sabit"]),
            "sizinti_ile_elenen_aday": plan[c]["sizinti_ile_elenen_aday"],
        } for c in sorted(CLASS_MAP)},
        "v1": {
            "aciklama": ("Ilk 40-klip set (sinif basina 5; docs/olcum_2026-07-26_kusur_sonrasi.md "
                         "icindeki A/B bu set uzerinde olculdu). IKI onlem BIRLIKTE alindi: "
                         "(a) DONDURULDU -> data/eval_defense_v1 (video hardlink, manifest KOPYA), "
                         "(b) SABITLENDI (pinned) -> yeni set v1'in UST KUMESI, boylece eski A/B "
                         "olcumu yeni setin alt kumesi olarak karsilastirilabilir kalir."),
            "kaynak": v1_src,
            "dondurulan_dizin": rel(v1_dir),
            "dondurma_durumu": v1_durum,
            "sabitleme": "kapali (--no-pin-v1)" if args.no_pin_v1 else "acik",
            "klip_sayisi": n_v1,
            "klipler": {c: sorted(v1.get(c, [])) for c in sorted(CLASS_MAP) if v1.get(c)},
            "yeni_set_ust_kumesi": (not args.no_pin_v1) and not (
                v1_adlar - {os.path.basename(x) for c in plan for x in plan[c]["secilen"]}),
            "diskte_bulunamayan_v1_klipleri": {c: plan[c]["sabit_diskte_yok"]
                                               for c in sorted(CLASS_MAP) if plan[c]["sabit_diskte_yok"]},
            "ek_sabitlenen": {"aciklama": ("--pin-existing: v1 DISINDA, cikti dizininde zaten duran "
                                           "ve bu kurulumda da korunan klipler (set yalnizca buyur)."),
                              "sayi": n_extra, "klipler": pin_extra},
        },
        "sizinti": {
            "aciklama": ("Ayni klip birden fazla degerlendirme setinde ise iki setin sonuclari "
                         "TOPLANARAK raporlandiginda capraz sayim olur. Tarama: dosya adi + "
                         "(ad eslesmezse) ayni boyuttakiler icin MD5. '_' ile baslayan klasorler "
                         "KARANTINA kabul edilip atlanir."),
            "taranan_dizinler": leak_dirs if not args.no_leak_check else [],
            "politika": "TARAMA KAPALI" if args.no_leak_check else leak_policy,
            "politika_anlami": {
                "avoid": "yeni secimler sizintisiz adaylardan yapilir; sabitlenmis (v1) klipler korunur",
                "report": "yalnizca raporlanir, secim degismez",
                "strict": "sizintili v1 klipleri de dislanir (v1 ust kume ozelligi kirilir)",
            }.get(leak_policy, ""),
            "onceden_var_olan_cakisma_notu": (
                "v1'in 20 Normal klibinin 16'si eval_big/eval_tune/eval_holdout/eval_scenario "
                "Normal setlerinde de bulunuyordu (D19 oncesi durum). 'avoid' politikasinda bunlar "
                "v1 surekliligi icin KORUNUR; yeni secimler sizintisizlardan yapilir. Bu setle "
                "digerlerinin sonuclari TOPLANMAMALIDIR."),
            "havuzdaki_sizinti": {k: v for k, v in sorted(leaks.items())},
            "bu_sette_secili_sizintili_klipler": sorted(
                n for n in leaks if n in {os.path.basename(x) for c in plan for x in plan[c]["secilen"]}),
        },
        "yetim_dosyalar": yetim,
        "klipler": rows,
    }
    os.makedirs(out, exist_ok=True)
    mpath = os.path.join(out, "MANIFEST.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(f"\nkuruldu: {len(rows)} klip ({n_link} hardlink, {n_copy} kopya, "
          f"{len(rows) - n_link - n_copy} zaten vardi) -> {rel(out)}\nmanifest -> {rel(mpath)}",
          flush=True)
    _celiskilileri_karantinaya_al(out)


def _celiskilileri_karantinaya_al(out: str) -> None:
    """D36 — ZIT ETIKETLI TAM-KAPSAMA ciftlerini olcumden cikar.

    NEDEN OTOMATIK: bu karantina 2026-08-17'de ELLE yapilmisti. Ama bu betik
    her kosumda seti YENIDEN kuruyor ve karantinadan HABERSIZDI -> baska bir
    makinede kurulum 200 klip uretiyordu. Sonuc: o makinedeki olcumler bizim
    arsivlerimizle KARSILASTIRILAMAZ hale geliyordu ve bunu fark etmek zordu.

    Piksel duzeyinde zamansal hizalama ile olculdu: uc kisa klip, ZIT etiketli
    uzun kliplerin ICINDE %100 kapsanmis durumda. Tutarli bir model bu ciftlerin
    birinde ZORUNLU yanilir -> MCC'nin ust siniri 1,0 DEGILDI.

    KURAL: kapsanan (kisa) cikarilir, kapsayan (uzun) KALIR — uzun klip kisa
    olanin icerdigi her seyi zaten iceriyor, bilgi kaybi en az.
    Klipler SILINMEZ, `_celiskili_cikarildi/` altina tasinir; `_` ile baslayan
    klasorler eval_clips tarafindan ATLANIR. Geri almak tek `mv`.

    Rapor: docs/veri_seti_nihai_denetim_2026-08-17.md
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from benchmark.sizinti_eval_defense import TAM_KAPSAMA
    except Exception as e:  # kayit okunamazsa kurulumu DURDURMA, ama SESSIZ de kalma
        print(f"[KARANTINA UYARI] celiskili klip kaydi okunamadi ({type(e).__name__}); "
              f"set 200 klip kaldi. benchmark/sizinti_eval_defense.py'yi kontrol et.",
              flush=True)
        return

    kar = os.path.join(out, "_celiskili_cikarildi")
    tasinan = 0
    for goreli, kapsayan in TAM_KAPSAMA:
        # goreli: "data/eval_defense/<Etiket>/<Sinif>/<ad>.mp4" -> out'a gore ic yol
        ic = goreli.split("data/eval_defense/", 1)[-1]
        kaynak = os.path.join(out, ic.replace("/", os.sep))
        if not os.path.exists(kaynak):
            continue
        os.makedirs(kar, exist_ok=True)
        shutil.move(kaynak, os.path.join(kar, ic.replace("/", "__")))
        tasinan += 1
        print(f"  [KARANTINA] {ic}\n              (kapsayan sette KALDI: "
              f"{kapsayan.split('data/eval_defense/', 1)[-1]})", flush=True)

    if tasinan:
        print(f"\n{tasinan} celiskili klip karantinaya alindi -> set 197 klip "
              f"(Anomali 99 + Normal 98). Gerekce: "
              f"docs/veri_seti_nihai_denetim_2026-08-17.md", flush=True)


if __name__ == "__main__":
    main()
