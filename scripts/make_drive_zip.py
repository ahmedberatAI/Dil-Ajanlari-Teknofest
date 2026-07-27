#!/usr/bin/env python
"""Takim paylasimi icin Google Drive zip paketleri uretir.

NEDEN: data/ 14 GB ve .gitignore'da. Takim uyeleri `git pull` ile KODU alir ama
VERIYI almaz. HF deposu (ahmedberatt/dilajanlari-eval) bir secenektir; bu betik
HF hesabi olmayan uyeler icin Drive alternatifi uretir.

NE PAKETLENIR (yalnizca DEGERLENDIRME setleri — kaynak havuzlar HARIC):
  Parca 1 "temel"   : eval_scenario, eval_tune, eval_holdout, eval_stress,
                      falls_real, falls_surveillance, e2_vehicle, robust,
                      sample_data, temporal  (~640 MB)
  Parca 2 "defense" : eval_defense (hedef-domain, ~2.6 GB)

NE PAKETLENMEZ ve NEDEN:
  data/industrial/  9.4 GB — KAYNAK HAVUZ; eval setleri zaten ondan turetildi.
                    Gerekirse: N_PER_CLASS=999 JOBS=8 python scripts/get_industrial.py
  data/nvidia/      1.0 GB — denendi, KULLANILMADI (sentetik olaylarda tespit 0)
  data/scenario/    2.0 GB — ham indirme arsivleri (zip/tar) + kopyalar
  _* dizinleri             — karantina (donmus-PNG klipler, yanlis etiketliler)

Videolar zaten sikistirilmis oldugu icin ZIP_STORED kullanilir (hizli, ayni boyut).

Kullanim:
    python scripts/make_drive_zip.py            # paketleri uret
    python scripts/make_drive_zip.py --list     # yalnizca plani goster
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
import zipfile

PROJE_KOKU = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(PROJE_KOKU, "data")
CIKTI = os.path.join(PROJE_KOKU, "outputs", "drive_paket")

#: parca adi -> (dosya adi, set listesi, aciklama)
PARCALAR: list[tuple[str, str, list[str], str]] = [
    (
        "temel",
        "dilajanlari-veri-1-temel.zip",
        ["eval_scenario", "eval_tune", "eval_holdout", "eval_stress",
         "falls_real", "falls_surveillance", "e2_vehicle", "robust",
         "sample_data", "temporal"],
        "Senaryo/dayaniklilik/dusme/arac degerlendirme setleri + ornek klipler",
    ),
    (
        "defense",
        "dilajanlari-veri-2-defense.zip",
        ["eval_defense"],
        "HEDEF-DOMAIN seti: gercek uretim tesisi 1080p (100 anomali + 100 normal)",
    ),
]

#: pakete ek olarak konacak kok dosyalar (parca 1'e)
EK_DOSYALAR = ["hf_manifest.json"]


def dosyalari_topla(set_adi: str) -> list[tuple[str, str]]:
    """(mutlak_yol, arsiv_ici_yol) listesi. '_' ile baslayan dizinler ATLANIR."""
    kok = os.path.join(DATA, set_adi)
    out: list[tuple[str, str]] = []
    if not os.path.isdir(kok):
        return out
    for dp, dirs, fs in os.walk(kok):
        dirs[:] = [d for d in dirs if not d.startswith("_")]  # karantina atla
        for f in sorted(fs):
            if f.endswith(".part"):
                continue
            tam = os.path.join(dp, f)
            out.append((tam, os.path.relpath(tam, DATA).replace("\\", "/")))
    return out


def sha256(yol: str, blok: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for p in iter(lambda: f.read(blok), b""):
            h.update(p)
    return h.hexdigest()


OKUBENI = """# DilAjanları — Veri Paketi (Drive)

Bu paketler `data/` dizinindeki **değerlendirme setlerini** içerir.
Kod GitHub'dadır: https://github.com/ahmedberatAI/Dil-Ajanlari-Teknofest

## Kurulum

1. Depoyu klonla / güncelle:
   ```bash
   git clone https://github.com/ahmedberatAI/Dil-Ajanlari-Teknofest.git
   cd Dil-Ajanlari-Teknofest
   ```
2. Zip'leri **proje kökünde** aç — içerik doğrudan `data/` altına gider:
   ```bash
   unzip dilajanlari-veri-1-temel.zip      # -> data/eval_scenario, data/falls_real, ...
   unzip dilajanlari-veri-2-defense.zip    # -> data/eval_defense
   ```
3. Doğrula:
   ```bash
   python scripts/audit_eval_sets.py
   ```

## İçindekiler

{icindekiler}

## Bu pakette OLMAYANLAR (bilerek)

| Dizin | Boyut | Neden | Nasıl elde edilir |
|---|---|---|---|
| `data/industrial/` | 9.4 GB | Kaynak havuz; eval setleri zaten ondan türetildi | `N_PER_CLASS=999 JOBS=8 python scripts/get_industrial.py` |
| `data/nvidia/` | 1.0 GB | Denendi, kullanılmadı (sentetik olaylarda tespit 0) | gerekmez |
| `data/scenario/` | 2.0 GB | Ham indirme arşivleri + kopyalar | `python scripts/get_firesense.py` |
| `_*` dizinleri | — | Karantina (donmuş-PNG klipler, yanlış etiketliler) | gerekmez |

**Model ağırlıkları bu pakette YOK** — gerekmiyor. Qwen3-VL-8B-FP8 herkese açıktır ve
ilk çalıştırmada otomatik iner (~10 GB). HF hesabı gerekmez.

## ⚠️ Lisans ve gizlilik — LÜTFEN OKUYUN

Bu klipler **üçüncü taraf veri setlerinden** türetilmiştir. Ayrıntı: `docs/veri_lisans_karari.md`

| Kaynak | Lisans | Kısıt |
|---|---|---|
| FIRESENSE (yangın/duman) | CC BY 4.0 | atıf zorunlu |
| GMDCSA-24 (düşme) | CC BY 4.0 | atıf zorunlu |
| Eskişehir Endüstriyel (`eval_defense`) | CC BY 4.0 | atıf zorunlu — **aşağıdaki nota bakın** |
| URFD (`urfd_*`) | CC BY-NC-SA 4.0 | ticari kullanım yok, aynı lisansla paylaş |
| UCF-Crime (`eval_tune`, `eval_holdout`, `e2_vehicle`) | Akademik/araştırma | **CC değil** — yeniden dağıtmayın |

> ### 🔒 `eval_defense` hakkında (önemli)
> Bu klipler, adı açıkça belirtilmiş bir üretim tesisinin (Kafaoğlu Metal Plastik A.Ş.)
> **tanınabilir gerçek çalışanlarının** işyeri gözetim görüntüsüdür ve bazı sınıflar
> belirli kişilerin **kural ihlali** anlarını etiketler.
>
> Telif açısından serbest (CC BY 4.0) olsa da **kişilik/mahremiyet hakları lisans
> kapsamında değildir** (CC BY 4.0 §2(b)(1)). Bu nedenle:
> - **Takım dışına dağıtmayın**, herkese açık bir yere yüklemeyin
> - Sunum/demo'da yüz ve kimlik vurgusu yapmayın
> - Yalnızca bu yarışma kapsamında akademik amaçla kullanın
>
> Orijinal kaynak herkese açıktır: https://data.mendeley.com/datasets/xjmtb22pff/1

## Bütünlük doğrulama

`SHA256.txt` zip'lerin özetini içerir:
```bash
sha256sum -c SHA256.txt
```
Klip bazlı MD5 doğrulaması için `hf_manifest.json` (351 kayıt) kullanılır.

## Atıf

- Eskişehir: *Video dataset for the detection of safe and unsafe behaviours in
  workplaces*, Mendeley Data, DOI 10.17632/xjmtb22pff.1 (CC BY 4.0)
- FIRESENSE: Zenodo 836749 (CC BY 4.0)
- GMDCSA-24: Alam et al. (CC BY 4.0)
- UCF-Crime: Sultani et al., *Real-world Anomaly Detection in Surveillance Videos*
- URFD: Kwolek & Kepski, UR Fall Detection Dataset (CC BY-NC-SA 4.0)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="yalnizca plani goster")
    ap.add_argument("--out", default=CIKTI, help="cikti dizini")
    args = ap.parse_args()

    plan = []
    for kimlik, dosya_adi, setler, aciklama in PARCALAR:
        dosyalar: list[tuple[str, str]] = []
        for s in setler:
            dosyalar += dosyalari_topla(s)
        boyut = sum(os.path.getsize(p) for p, _ in dosyalar)
        plan.append((kimlik, dosya_adi, setler, aciklama, dosyalar, boyut))

    print("=" * 78)
    print("  DRIVE PAKET PLANI")
    print("=" * 78)
    satirlar = []
    for kimlik, dosya_adi, setler, aciklama, dosyalar, boyut in plan:
        print(f"\n  [{kimlik}] {dosya_adi}")
        print(f"    {aciklama}")
        print(f"    {len(dosyalar)} dosya · {boyut / 1e6:.1f} MB")
        for s in setler:
            n = len(dosyalari_topla(s))
            if n:
                print(f"      - data/{s}  ({n} dosya)")
        satirlar.append(
            f"### `{dosya_adi}`\n\n{aciklama}\n\n"
            f"- **{len(dosyalar)} dosya · {boyut / 1e6:.0f} MB**\n"
            + "".join(f"- `data/{s}/` — {len(dosyalari_topla(s))} dosya\n" for s in setler if dosyalari_topla(s))
        )
    toplam = sum(p[5] for p in plan)
    print(f"\n  TOPLAM: {toplam / 1e9:.2f} GB")

    if args.list:
        print("\nLISTE MODU — hicbir dosya olusturulmadi.")
        return

    os.makedirs(args.out, exist_ok=True)
    uretilen: list[str] = []
    for kimlik, dosya_adi, setler, aciklama, dosyalar, boyut in plan:
        hedef = os.path.join(args.out, dosya_adi)
        print(f"\n  paketleniyor -> {dosya_adi} ({len(dosyalar)} dosya, {boyut / 1e6:.0f} MB)")
        t0 = time.time()
        with zipfile.ZipFile(hedef, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
            for i, (tam, ic) in enumerate(dosyalar, 1):
                z.write(tam, "data/" + ic)
                if i % 50 == 0 or i == len(dosyalar):
                    print(f"    [{i}/{len(dosyalar)}]", flush=True)
            if kimlik == "temel":
                for ek in EK_DOSYALAR:
                    kaynak = os.path.join(PROJE_KOKU, ek)
                    if os.path.exists(kaynak):
                        z.write(kaynak, ek)
        print(f"    bitti ({time.time() - t0:.0f} sn, {os.path.getsize(hedef) / 1e6:.0f} MB)")
        uretilen.append(hedef)

    # OKUBENI + SHA256
    okubeni = os.path.join(args.out, "OKUBENI.md")
    with open(okubeni, "w", encoding="utf-8") as f:
        f.write(OKUBENI.format(icindekiler="\n".join(satirlar)))
    print(f"\n  yazildi -> OKUBENI.md")

    sha_yol = os.path.join(args.out, "SHA256.txt")
    with open(sha_yol, "w", encoding="utf-8") as f:
        for p in uretilen:
            print(f"  SHA-256 hesaplaniyor: {os.path.basename(p)} ...", flush=True)
            f.write(f"{sha256(p)}  {os.path.basename(p)}\n")
    print(f"  yazildi -> SHA256.txt")

    print("\n" + "=" * 78)
    print(f"  TAMAM -> {args.out}")
    for p in uretilen:
        print(f"    {os.path.basename(p):40s} {os.path.getsize(p) / 1e6:8.0f} MB")
    print("  Bu dizini Google Drive'a yukleyin ve takim uyeleriyle paylasin.")
    print("=" * 78)


if __name__ == "__main__":
    main()
