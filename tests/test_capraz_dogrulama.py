"""CAPRAZ DOGRULAMA duman testleri — bes ajanin ONARIMLARI BIR ARADA calisiyor mu?

Bu dosya tek tek kusurlari (K1..K17) degil, ONARIMLARIN KESISIMINI test eder:
ajanlar birbirinin varsayimini bozmus olabilir. Hicbiri GPU/vLLM GEREKTIRMEZ
(VLM temas noktalari sahte istemciyle degistirilir).

Kosum:
    wsl.exe -d Ubuntu-24.04 -- /home/omen/teknofest/.venv/bin/python tests/test_capraz_dogrulama.py
"""
from __future__ import annotations

import concurrent.futures as cf
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_FAILS: list = []


def chk(cond: bool, msg: str) -> None:
    print(("  [OK]   " if cond else "  [FAIL] ") + msg)
    if not cond:
        _FAILS.append(msg)


# ---------------------------------------------------------------- 1) sozlesme
def test_cikti_sozlesmesi() -> None:
    """BOZULAMAZ sozlesme: to_sartname_dict -> {summary, events[{time,event}], risk, actions}."""
    print("\n=== 1) CIKTI SOZLESMESI (to_sartname_dict) ===")
    from dilajan.schema import (AnalysisResult, Action, Event, RiskAssessment,
                                Severity)
    r = AnalysisResult(
        summary="Depoda isci dustu.",
        events=[Event(time="00:05", event="Isci dustu", severity=Severity.KRITIK,
                      region="alt sol", bbox=[1, 2, 3, 4])],
        risk=RiskAssessment(level=Severity.KRITIK, rationale="hareketsiz"),
        actions=[Action(action="Saglik ekibi yonlendir", priority=Severity.KRITIK)],
        video_duration="00:30",
    )
    d = r.to_sartname_dict()
    chk(set(d) == {"summary", "events", "risk", "actions"},
        "ust anahtarlar TAM {summary,events,risk,actions} -> %s" % sorted(d))
    chk(all(set(e) == {"time", "event"} for e in d["events"]),
        "her olay TAM {time,event} (bbox/severity SIZMIYOR)")
    chk(isinstance(d["risk"], str) and d["risk"] == "Kritik",
        "risk duz string -> %r" % d["risk"])
    chk(d["actions"] == ["Saglik ekibi yonlendir"], "actions duz string listesi")
    chk(json.loads(json.dumps(d, ensure_ascii=False)) == d, "JSON round-trip")


# ------------------------------------------------- 2) paralel act log izolasyonu
def test_paralel_act_log_izolasyonu() -> None:
    """K1: n_samples>1 paralel kosuda her act() YALNIZ kendi cagrilarini gormeli."""
    print("\n=== 2) n_samples>1 PARALEL act() log izolasyonu (K1) ===")
    from dilajan import mock_functions as mf

    def kosu(i: int) -> int:
        mf.reset_log()
        mf.saglik_ekibi_yonlendir.invoke({"konum": "Bolge-%d" % i, "aciliyet": "Kritik"})
        if i % 2 == 0:
            mf.olay_kaydi_olustur.invoke({"ozet": "olay-%d" % i, "risk": "Kritik"})
        kayitlar = list(mf.get_log())
        # SIZINTI TESTI: baska kosunun konumu benim logumda GORUNMEMELI
        yabanci = [k for k in kayitlar
                   if "Bolge-" in str(k.get("args", {})) and "Bolge-%d" % i not in str(k.get("args", {}))]
        beklenen = 2 if i % 2 == 0 else 1
        return 0 if (len(kayitlar) == beklenen and not yabanci) else 1

    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        bozuk = sum(ex.map(kosu, range(24)))
    chk(bozuk == 0, "24 paralel act kosusunda capraz-sizinti YOK (bozuk=%d)" % bozuk)

    # OPERATION_LOG geriye-uyumlulugu (report.py / app.py bunu okuyor)
    mf.reset_log()
    mf.saglik_ekibi_yonlendir.invoke({"konum": "Depo", "aciliyet": "Yüksek"})
    L = mf.OPERATION_LOG
    chk(len(L) == 1 and isinstance(L[0], dict), "OPERATION_LOG len/getitem geriye-uyumlu")
    chk(set(L[0]) >= {"function", "args", "result"}, "kayit semasi korunuyor -> %s" % sorted(L[0]))


# ------------------------------------------------------- 3) arg-farkinda dedup
def test_arg_farkinda_dedup() -> None:
    """K4: ayni fn + FARKLI arg -> 2 cagri; ayni fn + ayni arg -> 1 cagri."""
    print("\n=== 3) ARG-FARKINDA DEDUP (K4) ===")
    from dilajan.chat_agent import _dedup_key
    a = _dedup_key("saglik_ekibi_yonlendir", {"konum": "Depo A", "aciliyet": "Kritik"})
    b = _dedup_key("saglik_ekibi_yonlendir", {"aciliyet": "  KRITIK ", "konum": "depo   a"})
    c = _dedup_key("saglik_ekibi_yonlendir", {"konum": "Depo B", "aciliyet": "Kritik"})
    chk(a == b, "ayni cagri (sira/bosluk/harf gurultusu) AYNI anahtar -> dedup eder")
    chk(a != c, "FARKLI konum FARKLI anahtar -> ikinci cagri ENGELLENMEZ")
    done = {a}
    chk(c not in done, "Depo B ayri olay olarak icra edilebilir (K4 duzeldi)")


# --------------------------------------------------- 4) olumsuzlama-guvenli onay
def test_olumsuzlama_guvenli_onay() -> None:
    """K5: Turkce olumsuzlamalar icra TETIKLEMEMELI."""
    print("\n=== 4) OLUMSUZLAMA-GUVENLI ONAY (K5) ===")
    from dilajan.chat_agent import is_confirmation
    for m in ["gonderme", "gönderme", "onaylamiyorum", "tamam degil", "iptal et",
              "hayir, sevk etme", "saglik ekibi cagirma", "yapma", "su an gerek yok"]:
        chk(is_confirmation(m) is False, "NEGATIF -> icra YOK: %r" % m)
    for m in ["evet gonder", "onayliyorum", "tamam sevk et", "onayla ve uygula"]:
        chk(is_confirmation(m) is True, "POZITIF -> icra VAR: %r" % m)
    chk(is_confirmation("") is False and is_confirmation(None) is False, "bos/None -> False")


# -------------------------------------------------------------- 5) Wilson GA
def test_wilson_guven_araligi() -> None:
    """K15: Wilson %95 GA referans degerleri."""
    print("\n=== 5) WILSON GUVEN ARALIGI (K15) ===")
    from benchmark.stats_utils import wilson_ci
    for k, n, lo, hi in [(17, 18, 0.742, 0.990), (18, 18, 0.824, 1.000), (0, 6, 0.000, 0.390)]:
        a, b = wilson_ci(k, n)
        chk(abs(a - lo) < 0.002 and abs(b - hi) < 0.002,
            "wilson_ci(%d,%d) = [%.4f, %.4f] (beklenen ~[%.3f, %.3f])" % (k, n, a, b, lo, hi))
    chk(wilson_ci(0, 6)[1] > 0.30,
        "0/6 ust siniri %%39 — '%%0 yanlis pozitif' tek basina KULLANILAMAZ")


# ------------------------------------------------------ 6) dispatch arg onarimi
def test_dispatch_arg_onarimi() -> None:
    """K3: yanlis arg-adi uretilse bile operasyonel cagri DUSMEMELI."""
    print("\n=== 6) DISPATCH ARG ONARIMI (K3) ===")
    from dilajan.agent.graph import _dispatch_context, _repair_args, _resolve_tool
    from dilajan import mock_functions as mf

    t, ad = _resolve_tool("saglik_ekibi_yonlendir")
    chk(t is not None and ad == "saglik_ekibi_yonlendir", "arac cozuldu: %s" % ad)
    ctx = _dispatch_context([], None)
    ctx["konum"] = "Depo-2"
    fixed, notlar = _repair_args(t, {"yer": "Depo-2"}, ctx)
    chk("konum" in fixed and "yer" not in fixed,
        "anlamsal esleme 'yer' -> 'konum' (onarilmis args=%s, not=%s)" % (fixed, notlar))
    mf.reset_log()
    t.invoke(fixed)
    chk(len(mf.get_log()) == 1, "onarilmis argümanlarla cagri GERCEKTEN yapildi (sessiz dusme yok)")

    # yazim hatasi olan fonksiyon adi da cozulmeli (cagri sessizce dusmesin)
    bozuk, cozulen = _resolve_tool("saglik_ekibi_yonlendirr")
    chk(bozuk is not None and cozulen == "saglik_ekibi_yonlendir",
        "yakin-isimli hatali fonksiyon adi cozuluyor -> %r" % cozulen)
    # gercekten bilinmeyen ad UYDURULMAMALI
    yok, yok_ad = _resolve_tool("uzay_gemisi_firlat")
    chk(yok is None, "gercekten bilinmeyen fonksiyon UYDURULMUYOR -> %r" % (yok_ad,))


# ---------------------------------------- 7) karantina klipleri olcume girmiyor
def test_karantina_klipleri_olcume_girmiyor() -> None:
    """CAPRAZ KIRILMA: _deprecated_frozen_fall (K8 donmus PNG) anomali paydasina SIZMAMALI."""
    print("\n=== 7) KARANTINA KLIPLERI OLCUME GIRMIYOR (K8 capraz) ===")
    scen = os.path.join(ROOT, "data", "eval_scenario")
    if not os.path.isdir(scen):
        print("  [ATLA] data/eval_scenario yok")
        return
    kategoriler, klipler = [], []
    for cat in sorted(os.listdir(scen)):
        if cat.startswith("_"):          # eval_clips/eval_*_all.py ile AYNI kural
            continue
        cdir = os.path.join(scen, cat)
        if not os.path.isdir(cdir):
            continue
        kategoriler.append(cat)
        for e in ("*.mp4", "*.avi", "*.mkv", "*.mov", "*.mpg", "*.mpeg"):
            klipler.extend(glob.glob(os.path.join(cdir, e)))
    chk("_deprecated_frozen_fall" not in kategoriler,
        "karantina klasoru KATEGORI olarak alinmiyor -> %s" % kategoriler)
    chk(not [p for p in klipler if "deprecated" in p or "lying" in os.path.basename(p)],
        "donmus lying*.mp4 klipleri olcum listesinde YOK")

    # eval_clips ve iki toplu-eval betigi AYNI kurali uyguluyor mu (kod-duzeyi kontrol)
    for rel in ("benchmark/eval_clips.py", "scripts/eval_all_datasets.py",
                "scripts/eval_answers_all.py"):
        src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        chk('cat.startswith("_")' in src, "%s '_' klasor filtresini iceriyor" % rel)


# ------------------------------------------- 8) ground truth <-> disk tutarliligi
def test_ground_truth_disk_tutarliligi() -> None:
    """CAPRAZ KIRILMA: GT'deki her klip diskte olmali ve koken bilgisi GERCEGI yansitmali."""
    print("\n=== 8) GROUND TRUTH <-> DISK TUTARLILIGI (K7/K8 capraz) ===")
    p = os.path.join(ROOT, "benchmark", "ground_truth.json")
    if not os.path.exists(p):
        print("  [ATLA] ground_truth.json yok")
        return
    gt = json.load(open(p, encoding="utf-8"))
    klipler = {k: v for k, v in gt.items() if not k.startswith("_")}
    eksik = [k for k in klipler if not os.path.exists(os.path.join(ROOT, k))]
    chk(not eksik, "GT'deki tum klipler diskte MEVCUT (eksik=%d)" % len(eksik))
    chk(not [k for k in klipler if "lying" in k],
        "GT'de sentetik lying*.mp4 kaydi YOK")
    chk(not [k for k in klipler if "test_clip" in k],
        "GT'de karikatur test_clip.mp4 kaydi YOK (K7)")

    fall = [k for k in klipler if "eval_scenario/Fall" in k.replace("\\", "/")]
    chk(len(fall) == 15, "eval_scenario/Fall 15 GERCEK klip -> %d" % len(fall))
    yanlis = [k for k in fall if "SENTETIK" in str(klipler[k].get("kaynak_dataset", ""))]
    chk(not yanlis,
        "GERCEK Fall klipleri 'SENTETIK' diye ETIKETLENMIYOR (yanlis kayit=%d)" % len(yanlis))


def main() -> int:
    test_cikti_sozlesmesi()
    test_paralel_act_log_izolasyonu()
    test_arg_farkinda_dedup()
    test_olumsuzlama_guvenli_onay()
    test_wilson_guven_araligi()
    test_dispatch_arg_onarimi()
    test_karantina_klipleri_olcume_girmiyor()
    test_ground_truth_disk_tutarliligi()
    print("\n" + "=" * 50)
    if _FAILS:
        print("BASARISIZ (%d):" % len(_FAILS))
        for f in _FAILS:
            print("  -", f)
        return 1
    print("TUM CAPRAZ DOGRULAMA TESTLERI GECTI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
