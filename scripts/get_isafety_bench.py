#!/usr/bin/env python
"""iSafetyBench'i DEGERLENDIRME seti olarak indirir. GPU GEREKMEZ.

⛔⛔ LISANS — OKUMADAN CALISTIRMA ⛔⛔
=====================================
Bu veri seti **CC BY-NC-SA 4.0** lisanslidir ve klipler **YouTube videolarindan**
derlenmistir (yayincinin "fair use" beyani).

  * **ShareAlike ZEHIRLI HAPTIR.** Bu veriyle ince ayar yapilirsa model
    agirliklari TUREV ESER sayilabilir -> modelimiz de CC BY-NC-SA olmak
    zorunda kalir. Yarisma sonrasi ticari gelecek de KAPANIR (NonCommercial).
  * **KURAL: yalnizca DEGERLENDIRME. Egitim/ince-ayar icin ASLA.**
  * **Baytlar YENIDEN YAYIMLANMAZ** — indirilen dizin .gitignore'dadir.

Bu kural HANDOFF §6.3'te takim karari olarak kayitlidir ve `tests/test_isg_lisans.py`
ile KOD DUZEYINDE kilitlenmistir.

NE INDIRILIR
------------
  1. Videolar   : HF `raiyaanabdullah/isafety-bench` (hazard/ 420 + normal/ 680, ~1.29 GB)
  2. Etiketler  : GitHub `iSafetyBench/data` (annotations_*.json + mcq/)

NEDEN ISE YARAR (D33 olcumune gore)
------------------------------------
`data/eval_defense`'in TAMAMI tek tesis, iki kamera, 39 gun, tek mevsim
(HANDOFF §5.2 Bosluk 1). Farkli bir ortamda genelleme kanitimiz YOK. iSafetyBench
BAGIMSIZ bir kaynaktir ve yayimlanmis taban degerleri vardir (Qwen2.5-VL-7B
onlarin tablosunda) -> KARSILASTIRILABILIR oluruz.

⚠️ AMA ALAN FARKLI: bizim dagitim alanimiz SABIT KAMERA endustriyel CCTV;
iSafetyBench YouTube kaynakli (degisken aci, kurgulu, sik sik el kamerasi).
Buradaki sayilar "farkli bir fabrikada da boyle olur" DEMEZ; genelleme
STRES TESTIDIR. Raporlarken bu ayrim yazilmalidir.

Kullanim:
    python scripts/get_isafety_bench.py             # tam indirme
    python scripts/get_isafety_bench.py --sadece-etiket   # yalniz JSON/mcq (hizli)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEDEF = os.path.join(ROOT, "data", "isafety_bench")

HF_REPO = "raiyaanabdullah/isafety-bench"
GH_REPO = "https://github.com/iSafetyBench/data.git"

LISANS_NOTU = """\
# ⛔ BU DIZIN EGITIMDE KULLANILAMAZ

**Veri seti:** iSafetyBench — https://huggingface.co/datasets/raiyaanabdullah/isafety-bench
**Makale:** arXiv 2508.00399 · **Proje:** https://isafetybench.github.io/
**Lisans:** **CC BY-NC-SA 4.0**
**Kliplerin kaynagi:** halka acik YouTube videolari (yayincinin "fair use" beyani)

## KURAL (HANDOFF §6.3, takim karari)

| Kullanim | Durum |
|---|---|
| Degerlendirme / benchmark | ✅ SERBEST |
| Ince ayar / egitim / damitma | ⛔ **YASAK** |
| Baytlari yeniden yayimlama | ⛔ **YASAK** |
| Turev veri seti yayimlama | ⛔ **YASAK** (ShareAlike) |

## NEDEN

**ShareAlike zehirli haptir.** Bu veriyle ince ayar yapilirsa model agirliklari
turev eser sayilabilir ve **modelimiz de CC BY-NC-SA olmak zorunda kalir**.
**NonCommercial** ayrica yarisma sonrasi ticari gelecegi kapatir.

## ALAN UYARISI (rapor yazarken)

Bizim dagitim alanimiz **sabit kamera endustriyel CCTV** (Eskisehir OSB, 2 IP kamera).
iSafetyBench **YouTube kaynaklidir**: degisken aci, kurgu, el kamerasi, farkli
cozunurluk. Buradan cikan sayilar **genelleme stres testidir**, "baska bir
fabrikada da boyle olur" KANITI DEGILDIR.

## ATIF (zorunlu — CC BY)

> Abdullah, R. et al. *iSafetyBench: An open-vocabulary multi-label action
> recognition dataset for normal and hazardous incidents in industrial
> environments.* arXiv:2508.00399

Bu dizin `.gitignore`dadir; baytlar depoya girmez.
"""


def _kos(cmd: list, cwd: str | None = None) -> int:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd).returncode


def etiketleri_indir() -> bool:
    """GitHub deposundan annotations_*.json + mcq/ ceker (videolar HF'te)."""
    etiket_dir = os.path.join(HEDEF, "annotations")
    if os.path.isdir(os.path.join(etiket_dir, ".git")):
        print("  [ATLA] etiket deposu zaten var; guncelleniyor...")
        return _kos(["git", "pull", "--ff-only"], cwd=etiket_dir) == 0
    os.makedirs(HEDEF, exist_ok=True)
    return _kos(["git", "clone", "--depth", "1", GH_REPO, etiket_dir]) == 0


def videolari_indir() -> bool:
    """HF'ten videolari ceker (huggingface_hub; token GEREKMEZ, depo aciktir)."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("  [HATA] huggingface_hub yok: pip install huggingface_hub")
        return False
    video_dir = os.path.join(HEDEF, "videos")
    os.makedirs(video_dir, exist_ok=True)
    print(f"  HF'ten indiriliyor: {HF_REPO} -> {video_dir}  (~1.29 GB)")
    try:
        snapshot_download(
            repo_id=HF_REPO, repo_type="dataset", local_dir=video_dir,
            allow_patterns=["hazard/*", "normal/*", "README.md"],
            max_workers=4,
        )
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  [HATA] indirme basarisiz: {type(e).__name__}: {e}")
        return False


def kunye_yaz() -> None:
    os.makedirs(HEDEF, exist_ok=True)
    with open(os.path.join(HEDEF, "NOKULLAN_EGITIM.md"), "w", encoding="utf-8") as f:
        f.write(LISANS_NOTU)
    # Makine-okunur bayrak: testler ve egitim betikleri BUNU okur.
    with open(os.path.join(HEDEF, "LISANS.json"), "w", encoding="utf-8") as f:
        json.dump({
            "veri_seti": "iSafetyBench",
            "kaynak_hf": f"https://huggingface.co/datasets/{HF_REPO}",
            "kaynak_github": GH_REPO,
            "makale": "arXiv:2508.00399",
            "lisans": "CC BY-NC-SA 4.0",
            "klip_kaynagi": "halka acik YouTube videolari (yayincinin fair-use beyani)",
            "egitimde_kullanilabilir": False,
            "degerlendirmede_kullanilabilir": True,
            "yeniden_yayimlanabilir": False,
            "gerekce": ("ShareAlike: ince ayar model agirliklarini turev eser yapabilir; "
                        "NonCommercial ticari kullanimi kapatir. HANDOFF §6.3 takim karari."),
            "alan_uyarisi": ("Dagitim alani sabit-kamera endustriyel CCTV; bu set YouTube "
                             "kaynakli. Sonuclar GENELLEME STRES TESTIDIR, ayni-alan kaniti DEGIL."),
        }, f, ensure_ascii=False, indent=2)
    print(f"  Kunye yazildi: {os.path.relpath(HEDEF, ROOT)}/LISANS.json + NOKULLAN_EGITIM.md")


def ozet() -> None:
    for alt in ("videos/hazard", "videos/normal"):
        p = os.path.join(HEDEF, alt)
        n = len([x for x in os.listdir(p)]) if os.path.isdir(p) else 0
        print(f"    {alt:20s} {n:5d} dosya")
    ann = os.path.join(HEDEF, "annotations")
    if os.path.isdir(ann):
        js = [x for x in os.listdir(ann) if x.endswith(".json")]
        print(f"    annotations/         {len(js):5d} json  {js[:4]}")
    try:
        toplam = sum(os.path.getsize(os.path.join(dp, f))
                     for dp, _, fs in os.walk(HEDEF) for f in fs)
        print(f"    TOPLAM BOYUT         {toplam / 1e9:.2f} GB")
    except OSError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sadece-etiket", action="store_true",
                    help="yalniz annotations/mcq indir (video indirme, hizli)")
    args = ap.parse_args()

    print("=" * 78)
    print("iSafetyBench — DEGERLENDIRME SETI KURULUMU")
    print("⛔ LISANS: CC BY-NC-SA 4.0 — EGITIMDE KULLANILAMAZ (HANDOFF §6.3)")
    print("=" * 78)

    if not shutil.which("git"):
        print("[HATA] git bulunamadi.")
        return 1

    kunye_yaz()
    print("\n[1/2] Etiketler (GitHub)...")
    if not etiketleri_indir():
        print("  [UYARI] etiketler alinamadi — videolar etiketsiz ISE YARAMAZ.")

    if args.sadece_etiket:
        print("\n--sadece-etiket verildi; videolar ATLANDI.")
    else:
        print("\n[2/2] Videolar (HuggingFace, ~1.29 GB)...")
        if not videolari_indir():
            return 1

    print("\nOZET:")
    ozet()
    print("\n" + "=" * 78)
    print("⛔ HATIRLATMA: bu dizin YALNIZCA degerlendirme icindir.")
    print("   Egitim/ince-ayar YASAK. tests/test_isg_lisans.py bunu kilitler.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
