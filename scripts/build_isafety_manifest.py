#!/usr/bin/env python
"""iSafetyBench icin MANIFEST.json uretir + BUTUNLUK denetimi yapar. GPU GEREKMEZ.

NEDEN
-----
Indirilen klipler ile etiketler AYRI kaynaklardan gelir (videolar HuggingFace,
etiketler GitHub). Ikisi arasinda eslesmeyen dosya olursa bu SESSIZCE olur ve
payda yanlis cikar. Bu betik eslesmeyi DENETLER ve sayilari MANIFEST'e yazar —
`data/eval_defense/MANIFEST.json` ile ayni desen.

Ayrica setin **nasil kullanilabilecegini** makine-okunur bicimde kaydeder:
degerlendirme SERBEST, egitim YASAK (CC BY-NC-SA — HANDOFF §6.3).

Kullanim:
    python scripts/build_isafety_manifest.py
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KOK = os.path.join(ROOT, "data", "isafety_bench")
ANN = os.path.join(KOK, "annotations")
VID = os.path.join(KOK, "videos")


def _json_yukle(ad: str):
    yol = os.path.join(ANN, ad)
    if not os.path.exists(yol):
        return None
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


def _kategori_sozlugu() -> dict:
    """actions.txt bir Python sozluk LITERALIDIR; ast ile guvenli ayristirilir."""
    yol = os.path.join(ANN, "actions.txt")
    if not os.path.exists(yol):
        return {}
    import ast
    metin = open(yol, encoding="utf-8").read()
    out = {}
    # "<ad> = { ... }" bloklarini ayikla
    for m in re.finditer(r"(\w+)\s*=\s*(\{)", metin):
        ad, bas = m.group(1), m.start(2)
        derinlik, i = 0, bas
        while i < len(metin):
            if metin[i] == "{":
                derinlik += 1
            elif metin[i] == "}":
                derinlik -= 1
                if derinlik == 0:
                    break
            i += 1
        try:
            out[ad] = ast.literal_eval(metin[bas:i + 1])
        except (ValueError, SyntaxError):
            pass
    return out


def main() -> int:
    if not os.path.isdir(ANN):
        print(f"[HATA] etiketler yok: {os.path.relpath(ANN, ROOT)}")
        print("       once: python scripts/get_isafety_bench.py")
        return 1

    print("=" * 78)
    print("iSafetyBench — MANIFEST + BUTUNLUK DENETIMI")
    print("=" * 78)

    kollar = {}
    for kol, ann_ad in (("hazard", "annotations_hazard.json"),
                        ("normal", "annotations_normal.json")):
        ann = _json_yukle(ann_ad) or []
        etiketli = {r["video_name"] for r in ann if r.get("video_name")}
        vdir = os.path.join(VID, kol)
        diskte = {f for f in os.listdir(vdir)} if os.path.isdir(vdir) else set()

        eksik = sorted(etiketli - diskte)       # etiketi var, videosu YOK
        fazla = sorted(diskte - etiketli)       # videosu var, etiketi YOK
        eslesen = sorted(etiketli & diskte)

        # gt_actions dagilimi
        say = collections.Counter()
        for r in ann:
            for a in (r.get("gt_actions") or []):
                say[a] += 1

        kollar[kol] = {
            "etiket_dosyasi": ann_ad,
            "n_etiket": len(etiketli),
            "n_video_diskte": len(diskte),
            "n_eslesen": len(eslesen),
            "n_etiketi_var_videosu_yok": len(eksik),
            "n_videosu_var_etiketi_yok": len(fazla),
            "eksik_ornek": eksik[:5],
            "fazla_ornek": fazla[:5],
            "n_farkli_eylem": len(say),
            "en_sik_eylemler": say.most_common(10),
        }
        durum = "TAMAM" if not eksik and not fazla else "⚠ UYUSMAZLIK"
        print(f"\n[{kol}] {durum}")
        print(f"   etiket: {len(etiketli):5d}   diskte: {len(diskte):5d}   "
              f"eslesen: {len(eslesen):5d}")
        if eksik:
            print(f"   ⚠ etiketi var videosu YOK : {len(eksik)}  {eksik[:3]}")
        if fazla:
            print(f"   ⚠ videosu var etiketi YOK : {len(fazla)}  {fazla[:3]}")
        print(f"   farkli eylem etiketi: {len(say)}")
        print(f"   en sik: {[a for a, _ in say.most_common(5)]}")

    # MCQ dosyalari
    mcq = {}
    mdir = os.path.join(ANN, "mcq")
    if os.path.isdir(mdir):
        for f in sorted(os.listdir(mdir)):
            if not f.endswith(".json"):
                continue
            try:
                d = json.load(open(os.path.join(mdir, f), encoding="utf-8"))
                mcq[f] = {"n_soru": len(d),
                          "ort_secenek": (round(sum(len(x.get("choices") or []) for x in d)
                                                / len(d), 1) if d else 0)}
            except (OSError, json.JSONDecodeError):
                mcq[f] = {"n_soru": None}
    print(f"\n[mcq] {mcq}")

    sozluk = _kategori_sozlugu()
    kat_ozet = {k: {"grup": len(v), "eylem": sum(len(x) for x in v.values())}
                for k, v in sozluk.items() if isinstance(v, dict)}
    print(f"\n[actions.txt] {kat_ozet}")

    manifest = {
        "_aciklama": ("iSafetyBench — BAGIMSIZ genelleme degerlendirme seti. "
                      "Videolar HuggingFace'ten, etiketler GitHub'dan gelir; bu "
                      "manifest ikisinin ESLESTIGINI denetler."),
        "kaynak_videolar": "https://huggingface.co/datasets/raiyaanabdullah/isafety-bench",
        "kaynak_etiketler": "https://github.com/iSafetyBench/data",
        "makale": "arXiv:2508.00399",
        "lisans": "CC BY-NC-SA 4.0 (LICENSE dosyasindan BIREBIR teyitli)",
        "klip_kaynagi": "halka acik YouTube videolari (yayincinin fair-use beyani)",
        "kullanim": {
            "degerlendirme": True,
            "egitim": False,
            "yeniden_yayimlama": False,
            "gerekce": ("ShareAlike ince ayarda agirliklari turev eser yapabilir; "
                        "NonCommercial ticari kullanimi kapatir. HANDOFF §6.3."),
            "kod_kilidi": "dilajan/veri_lisans.py + tests/test_isg_lisans.py",
        },
        "alan_uyarisi": ("Dagitim ortamimiz SABIT KAMERA endustriyel CCTV (Eskisehir OSB, "
                         "2 IP kamera). Bu set YOUTUBE kaynaklidir: degisken aci, kurgu, "
                         "el kamerasi. Buradaki sayilar GENELLEME STRES TESTIDIR, "
                         "'baska bir fabrikada da boyle olur' KANITI DEGILDIR."),
        "yayimlanmis_taban": ("Ovis2-8B %53,4 F1 (tehlike, en iyi); Qwen2.5-VL-7B de "
                              "tabloda — MCQ bicimiyle kosulursa KARSILASTIRILABILIR oluruz."),
        "gorev_bicimi": "coktan secmeli (tek-etiketli ve cok-etiketli) · dil: INGILIZCE",
        "dil_notu": ("Bizim cikti sozlesmemiz TURKCE. MCQ kolu kosulacaksa ya secenekler "
                     "cevrilmeli ya da bu kol AYRI raporlanmalidir (cikti sozlesmesi K1 "
                     "DEGISMEZ)."),
        "kollar": kollar,
        "mcq": mcq,
        "kategori_sozlugu": kat_ozet,
    }
    yol = os.path.join(KOK, "MANIFEST.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nKaydedildi: {os.path.relpath(yol, ROOT)}")

    toplam_eksik = sum(k["n_etiketi_var_videosu_yok"] for k in kollar.values())
    toplam_esles = sum(k["n_eslesen"] for k in kollar.values())
    print("=" * 78)
    print(f"KULLANILABILIR (etiket+video eslesen): {toplam_esles} klip")
    if toplam_eksik:
        print(f"⚠ {toplam_eksik} klibin etiketi var ama videosu indirilmemis — "
              f"indirme yarim kalmis olabilir.")
    print("⛔ EGITIMDE KULLANILAMAZ (CC BY-NC-SA) — kod kilidi: dilajan/veri_lisans.py")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
