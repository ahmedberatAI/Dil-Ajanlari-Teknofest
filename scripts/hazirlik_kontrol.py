#!/usr/bin/env python
"""PROJE HAZIRLIK KONTROLU — "hicbir eksigimiz kaldi mi?" sorusunun makine cevabi.

`scripts/doctor.py` bir TAKIM UYESININ MAKINESINI teshis eder (GPU/torch/sunucu).
Bu betik farkli bir soruyu sorar: **PROJE kendi icinde tam ve tutarli mi?**

  * Bozulamaz kisitlar (K1-K6) kod duzeyinde hala gecerli mi?
  * Yeni ozellikler VARSAYILAN KAPALI mi? (K2)
  * Veri setleri yerinde ve lisans kilitleri calisiyor mu?
  * Olcum yapitlari (sonuc JSON'lari) mevcut mu?
  * Belgeler ile KOD arasinda celiski var mi?

GPU/vLLM GEREKTIRMEZ; her kontrol tek tek sarilidir, hicbir kosulda cokmez.

Cikis kodu: 0 = eksik yok · 1 = en az bir KRITIK eksik

Kullanim:
    python scripts/hazirlik_kontrol.py
    python scripts/hazirlik_kontrol.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SONUC: list = []


def kontrol(ad: str, kritik: bool = True):
    """Dekoratör: fonksiyon (bool, mesaj) dondurur; istisna = BASARISIZ."""
    def sar(fn):
        try:
            ok, mesaj = fn()
        except Exception as e:  # noqa: BLE001
            ok, mesaj = False, f"{type(e).__name__}: {e}"
        SONUC.append({"ad": ad, "ok": bool(ok), "mesaj": str(mesaj), "kritik": kritik})
        isaret = "✅" if ok else ("❌" if kritik else "⚠️ ")
        print(f"  {isaret} {ad:44s} {mesaj}")
        return fn
    return sar


def _var(*parcalar) -> bool:
    return os.path.exists(os.path.join(ROOT, *parcalar))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--testleri-atla", action="store_true", help="test paketini kosma (hizli)")
    args = ap.parse_args()

    print("=" * 92)
    print("PROJE HAZIRLIK KONTROLU")
    print("=" * 92)

    # ---------------- K2: yeni ozellikler VARSAYILAN KAPALI ----------------
    print("\n[K2] Yeni ozellikler varsayilan KAPALI mi?")

    @kontrol("ppe_detection varsayilan KAPALI")
    def _():
        from dilajan.config import Settings
        v = Settings().ppe_detection
        return v is False, f"= {v}"

    @kontrol("ppe_dispatch varsayilan KAPALI (sevk yetkisi opt-in)")
    def _():
        from dilajan.config import Settings
        v = Settings().ppe_dispatch
        return v is False, f"= {v}"

    @kontrol("facility_rules / facility_policy varsayilan BOS")
    def _():
        from dilajan.config import Settings
        s = Settings()
        return (s.facility_rules == "" and s.facility_policy == ""),\
            f"rules={s.facility_rules!r} policy={s.facility_policy!r}"

    @kontrol("evidence_questions / use_detector varsayilan KAPALI")
    def _():
        from dilajan.config import Settings
        s = Settings()
        return (s.evidence_questions is False and s.use_detector is False),\
            f"evidence={s.evidence_questions} detector={s.use_detector}"

    # ---------------- K1: cikti sozlesmesi ----------------
    print("\n[K1] Cikti sozlesmesi TAM 4 anahtar mi?")

    @kontrol("to_sartname_dict() tam 4 anahtar")
    def _():
        from dilajan.schema import AnalysisResult, RiskAssessment, Severity
        r = AnalysisResult(summary="x", risk=RiskAssessment(level=Severity.DUSUK, rationale="y"))
        a = set(r.to_sartname_dict().keys())
        bekl = {"summary", "events", "risk", "actions"}
        return a == bekl, f"{sorted(a)}"

    @kontrol("sema-disi alanlar model_dump()'a SIZMIYOR (ppe_src)")
    def _():
        from dilajan.schema import Event
        e = Event(time="00:01", event="x").model_copy(update={"ppe_src": True})
        return "ppe_src" not in e.model_dump(), "temiz"

    # ---------------- LISANS KAPISI ----------------
    print("\n[LISANS] Egitim kapisi calisiyor mu?")

    @kontrol("isafety_bench EGITIMDE yasak")
    def _():
        from dilajan.veri_lisans import egitimde_kullanilabilir
        return egitimde_kullanilabilir("data/isafety_bench") is False, "yasak"

    @kontrol("egitim_icin_dogrula ISTISNA firlatiyor (fail-closed)")
    def _():
        from dilajan.veri_lisans import LisansIhlali, egitim_icin_dogrula
        try:
            egitim_icin_dogrula(["data/isafety_bench"])
            return False, "istisna FIRLATMADI (kapi acik!)"
        except LisansIhlali:
            return True, "fail-closed dogru"

    @kontrol("ppe / industrial EGITIMDE serbest")
    def _():
        from dilajan.veri_lisans import egitimde_kullanilabilir
        return (egitimde_kullanilabilir("data/ppe")
                and egitimde_kullanilabilir("data/industrial")), "serbest"

    @kontrol("isafety_bench kunyesi (LISANS.json) yerinde", kritik=False)
    def _():
        from dilajan.veri_lisans import kunye_oku
        k = kunye_oku("data/isafety_bench")
        return bool(k) and k.get("egitimde_kullanilabilir") is False, \
            (k or {}).get("lisans", "kunye YOK")

    # ---------------- VERI ----------------
    print("\n[VERI] Setler yerinde mi?")

    @kontrol("data/eval_defense 197 klip (3'u karantinada)", kritik=False)
    def _():
        # D36: set 200 -> 197. UC klip KASITLI olarak karantinaya alindi cunku ayni
        # goruntu ZIT etiketle iki kez settedeydi (piksel duzeyinde zamansal hizalama
        # ile olculdu; kisa klip uzun klibin ICINDE %100 kapsanmis). Tutarli bir model
        # o ciftlerin birinde ZORUNLU yaniliyordu -> MCC'nin ust siniri 1,0 DEGILDI.
        # Bu kontrol eskiden 200 bekliyordu; guncellenmeseydi her kosumda SAHTE UYARI
        # cikacak ve birileri "duzeltmek" icin celiskili klipleri GERI KOYABILECEKTI.
        # Gerekce: docs/veri_seti_nihai_denetim_2026-08-17.md
        import glob
        kok = os.path.join(ROOT, "data", "eval_defense")
        n = len(glob.glob(os.path.join(kok, "*", "*", "*.mp4")))
        kar = len(glob.glob(os.path.join(kok, "_celiskili_cikarildi", "*.mp4")))
        if n == 197 and kar == 3:
            return True, f"{n} klip + {kar} karantinada"
        if n == 200:
            return False, ("200 klip — celiskili UC klip karantinaya ALINMAMIS. "
                           "Duzeltme: python scripts/build_defense_eval.py")
        return False, f"{n} klip (beklenen 197), karantina {kar} (beklenen 3)"

    @kontrol("data/isafety_bench 1100 klip + etiketler", kritik=False)
    def _():
        import glob
        n = len(glob.glob(os.path.join(ROOT, "data", "isafety_bench", "videos", "*", "*.mp4")))
        ann = _var("data", "isafety_bench", "annotations", "annotations_hazard.json")
        return n == 1100 and ann, f"{n} klip, etiket={'var' if ann else 'YOK'}"

    @kontrol("data/ppe_yolo YOLO bicimi hazir", kritik=False)
    def _():
        import glob
        n = len(glob.glob(os.path.join(ROOT, "data", "ppe_yolo", "images", "train", "*.jpg")))
        y = _var("data", "ppe_yolo", "ppe.yaml")
        return n > 1000 and y, f"{n} egitim gorseli, yaml={'var' if y else 'YOK'}"

    # ---------------- KKD DEDEKTORU ----------------
    print("\n[KKD] Dedektor hazir mi?")

    @kontrol("KKD 'baret' kiti GERCEKTEN kullanilabilir", kritik=False)
    def _():
        # D39-D: eskiden yalnizca DOSYAYA bakiliyordu; `ultralytics` (opsiyonel,
        # AGPL-3.0) kurulu degilken "var" deyip sessizce hicbir sey tespit
        # etmiyordu. Artik sebep raporlanir.
        from dilajan import detector
        neden = detector.kkd_neden_yok("baret")
        return neden is None, ("hazir" if neden is None else f"KAPALI — {neden}")

    @kontrol("agirlik yokken FAIL-OPEN (cokme yok)")
    def _():
        from dilajan import detector
        orig = detector._get_ppe_model
        detector._get_ppe_model = lambda: None
        try:
            r = detector.detect_ppe_violation([("00:01", b"x")])
            v, _n = detector.verify_ppe_claim([("00:01", b"x")])
            return r is None and v == "ABSTAIN", "None / ABSTAIN"
        finally:
            detector._get_ppe_model = orig

    # ---------------- OLCUM YAPITLARI ----------------
    print("\n[OLCUM] Sonuc dosyalari yerinde mi?")

    for ad, yol in (
        ("D33 A kolu (varsayilan)", "benchmark/results/isg_A_varsayilan_20260816.json"),
        ("D33 B kolu (kurallar)", "benchmark/results/isg_B_kurallar_20260816.json"),
        ("D33 A/B karsilastirmasi", "benchmark/results/isg_ab_tam_20260816.json"),
        ("D33 gurultu tabani (A vs A')", "benchmark/results/isg_gurultu_A_vs_Ap_20260816.json"),
    ):
        def _yap(y=yol, a=ad):
            @kontrol(a, kritik=False)
            def _():
                return _var(*y.split("/")), y
        _yap()

    # ---------------- BELGELER ----------------
    print("\n[BELGE] Kritik belgeler mevcut mu?")
    for ad, yol in (
        ("D33 raporu", "docs/isg_taksonomi_hizalamasi_2026-08-16.md"),
        ("D33 on-kaydi", "docs/on_kayit_isg_2026-08-16.md"),
        ("D34 KKD raporu", "docs/kkd_dogrulayici_2026-08-16.md"),
        ("lisans karari", "docs/veri_lisans_karari.md"),
    ):
        def _yap2(y=yol, a=ad):
            @kontrol(a, kritik=False)
            def _():
                return _var(*y.split("/")), y
        _yap2()

    # ---------------- TESTLER ----------------
    if not args.testleri_atla:
        print("\n[TEST] Tam paket")

        @kontrol("tum testler geciyor")
        def _():
            import glob as _g
            dosyalar = sorted(_g.glob(os.path.join(ROOT, "tests", "test_*.py"))
                              + _g.glob(os.path.join(ROOT, "benchmark", "test_*.py")))
            ortam = dict(os.environ, DILAJAN_MOCK="1")
            kalan = []
            for t in dosyalar:
                r = subprocess.run([sys.executable, t], cwd=ROOT, env=ortam,
                                   capture_output=True, text=True, timeout=900)
                if r.returncode != 0:
                    kalan.append(os.path.basename(t))
            return not kalan, (f"{len(dosyalar)} dosya, hepsi GECTI" if not kalan
                               else f"KALAN: {kalan}")

    # ---------------- OZET ----------------
    kritik_kalan = [s for s in SONUC if not s["ok"] and s["kritik"]]
    uyari = [s for s in SONUC if not s["ok"] and not s["kritik"]]
    print("\n" + "=" * 92)
    print(f"SONUC: {sum(1 for s in SONUC if s['ok'])}/{len(SONUC)} kontrol gecti")
    if uyari:
        print(f"  ⚠️  {len(uyari)} UYARI (kritik degil):")
        for s in uyari:
            print(f"      - {s['ad']}: {s['mesaj']}")
    if kritik_kalan:
        print(f"  ❌ {len(kritik_kalan)} KRITIK EKSIK:")
        for s in kritik_kalan:
            print(f"      - {s['ad']}: {s['mesaj']}")
    else:
        print("  ✅ KRITIK EKSIK YOK")
    print("=" * 92)

    if args.json_out:
        yol = args.json_out if os.path.isabs(args.json_out) else os.path.join(ROOT, args.json_out)
        with open(yol, "w", encoding="utf-8") as f:
            json.dump({"kontroller": SONUC,
                       "kritik_kalan": len(kritik_kalan),
                       "uyari": len(uyari)}, f, ensure_ascii=False, indent=2)
        print(f"Kaydedildi: {os.path.relpath(yol, ROOT)}")
    return 1 if kritik_kalan else 0


if __name__ == "__main__":
    raise SystemExit(main())
