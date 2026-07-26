#!/usr/bin/env python
"""ESLESTIRILMIS (paired) A/B karsilastirmasi + istatistiksel GUC analizi.

NEDEN BU DOSYA VAR
------------------
"facility_rules ACIK vs KAPALI" gibi iki kosu, benchmark/compare.py ile yan yana
konuldugunda yalnizca iki BAGIMSIZ oran gibi gorunur (recall %25 -> %55). Oysa iki kosu
AYNI kliplerde yapildi: her klip kendi kontrolu. Bagimsiz-orneklem testi bu eslestirmeyi
carcur eder ve guc kaybettirir. Dogru arac McNemar testidir: yalnizca YON DEGISTIREN
klipler (uyusmayan cifler) kanit tasir.

Ornek (olculen): recall'da 8 klip KAPALI->yanlis / ACIK->dogru; 2 klip tersi.
    8-2 -> exact p = 0.109  ->  n=20'de ANLAMLI DEGIL, ama YON TUTARLI.
Ayni oruntu n=100'de (40-10) p < 0.001 olur. Bu dosya hem testi hem de
"kac klip gerekiyor" sorusunu (guc analizi) hesaplar.

DURUSTLUK KURALLARI (K15 uzantisi)
----------------------------------
* KARAR her zaman TAM (exact) McNemar ile verilir; sureklilik-duzeltmeli chi-kare
  yalnizca literaturle kiyas icin, bilgi amacli yazilir.
* Uyusan cifler (ikisi de dogru / ikisi de yanlis) H0 hakkinda bilgi TASIMAZ, ama
  raporda GORUNUR — cunku n=40'ta "8-2" duyuldugunda okuyucunun 30 klibin hic
  degismedigini bilmesi gerekir.
* Etki buyuklugu, farkin GUVEN ARALIGI ile verilir (Newcombe 1998 Method 10,
  eslestirmeye gore phi-duzeltmeli Wilson "square-and-add"). Bu aralik exact testin
  TERSI DEGILDIR; sinirda GA 0'i dislarken exact p > alpha olabilir. Boyle bir
  uyusmazlik raporda ACIKCA isaretlenir.
* Her metrik "YUKSEK = IYI" yonune cevrilir (normal kliplerdeki yanlis-pozitif
  metrikleri "FP YOK = dogru" olarak kodlanir) — boylece b/c ve farkin isareti
  butun tabloda ayni anlami tasir.
* Anomali ve Normal alt kumeleri AYRI raporlanir: birincisi tespit (recall),
  ikincisi yanlis-alarm olcer; tek bir sayida birlestirmek yaniltici olur.

KULLANIM
--------
    # en son iki sonuc dosyasi (eski = A, yeni = B)
    python benchmark/paired_test.py

    # acik dosyalar + etiketler + JSON cikti
    python benchmark/paired_test.py \
        benchmark/results/eval_20260726_002608.json \
        benchmark/results/eval_20260726_003531.json \
        --label-a "kurallar KAPALI" --label-b "kurallar ACIK" \
        --project-n 100 --json benchmark/results/paired_ab.json

Bagimlilik: yalniz stdlib (math/json/argparse) + benchmark.stats_utils.
GPU/vLLM/torch GEREKMEZ — kayitli JSON sonuclar uzerinde calisir.

Birim testi:  python benchmark/test_paired_test.py
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.stats_utils import (  # noqa: E402
    Z95, fmt_rate_dict, mcnemar_chi2_cc, mcnemar_exact_p, mcnemar_power,
    mcnemar_power_analytic, mcnemar_test, newcombe_paired_diff_ci, norm_cdf, norm_ppf,
    phi_coefficient, project_to_n, required_n, required_n_analytic, wilson_ci,
)

__all__ = [
    # yeniden ihrac (test ve dis kullanim tek kapidan gecsin)
    "mcnemar_exact_p", "mcnemar_chi2_cc", "mcnemar_test", "newcombe_paired_diff_ci",
    "phi_coefficient", "mcnemar_power", "mcnemar_power_analytic", "required_n",
    "required_n_analytic", "project_to_n", "norm_cdf", "norm_ppf", "wilson_ci",
    # bu modulun kendi API'si
    "Metric", "METRICS", "load_rows", "pair_rows", "contingency", "compare",
    "format_report", "main",
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "benchmark", "results")


# ===========================================================================
# METRIK KAYIT DEFTERI
# ===========================================================================
# Her metrik "dogru mu?" seklinde IKILI bir yordama indirgenir ve YUKSEK = IYI olacak
# sekilde tanimlanir. Tanimlar benchmark/eval_clips.py'deki toplulastirma ile BIREBIR
# ayni esikleri kullanir (recall: n_events>0, risk: risk_ord>=3, FP: triggered/n_events).

@dataclass(frozen=True)
class Metric:
    """Eslestirilmis testte kullanilan ikili metrik tanimi.

    Attributes:
        name: kisa ad (JSON anahtari)
        subset: "anomali" | "normal" — hangi klip alt kumesinde olculur
        label: tabloda gorunecek insan-okur ad
        desc: "dogru" sayilan durumun tanimi (yuksek = iyi yonunde)
        ok: satir sozlugunden bool ureten yordam (FAIL-OPEN: eksik alan -> False)
    """
    name: str
    subset: str
    label: str
    desc: str
    ok: Callable[[dict], bool]


def _ev(r: dict) -> int:
    return int(r.get("n_events") or 0)


def _trig(r: dict) -> int:
    return len(r.get("triggered") or [])


def _risk(r: dict) -> int:
    return int(r.get("risk_ord") or 0)


def _sev(r: dict) -> int:
    return int(r.get("max_severity") or 0)


METRICS: Tuple[Metric, ...] = (
    # --- ANOMALI klipler: tespit ve dogru siniflandirma olculur ---
    Metric("recall", "anomali", "Anomali RECALL",
           "klipte >=1 olay tespit edildi (n_events>0)",
           lambda r: _ev(r) > 0),
    Metric("cat_match", "anomali", "Kategori eslesme",
           "olay metni beklenen anahtar kelimelerden birini iceriyor",
           lambda r: bool(r.get("category_match"))),
    Metric("risk_cal_anom", "anomali", "Risk kalibrasyonu",
           "risk seviyesi >= Yuksek (risk_ord>=3)",
           lambda r: _risk(r) >= 3),
    Metric("anom_dispatch", "anomali", "Operasyonel tetik",
           "anomalide >=1 arac/fonksiyon tetiklendi (dogru sevk)",
           lambda r: _trig(r) > 0),
    # --- NORMAL klipler: yanlis-alarm olculur; "dogru" = FP YOK ---
    Metric("normal_no_dispatch", "normal", "Sevk FP yok",
           "normal klipte HIC arac/fonksiyon tetiklenmedi",
           lambda r: _trig(r) == 0),
    Metric("normal_no_op_fp", "normal", "Operasyonel FP yok",
           "normal klipte ne olay ne tetik var (n_events==0 ve tetik yok)",
           lambda r: _ev(r) == 0 and _trig(r) == 0),
    Metric("normal_no_strict_fp", "normal", "Dar FP yok",
           "normal klipte Yuksek/Kritik olay YOK ve risk < Yuksek",
           lambda r: not (_sev(r) >= 3 or _risk(r) >= 3)),
    Metric("risk_cal_norm", "normal", "Normal risk=Dusuk",
           "normal klipte risk seviyesi <= Dusuk (risk_ord<=1)",
           lambda r: _risk(r) <= 1),
)


# ===========================================================================
# SONUC YUKLEME + ESLESTIRME
# ===========================================================================

def load_rows(path: str) -> Tuple[Dict[str, dict], List[str]]:
    """eval_*.json dosyasindan klip satirlarini yol->satir sozlugu olarak okur.

    Returns:
        (rows_by_path, uyarilar). Ayni yol iki kez varsa (olmamali) ILKI korunur ve
        uyari uretilir — sessizce ustune yazmak payda sismesi/kaybi demek olurdu.

    Raises:
        FileNotFoundError / json hatalari: cagirana birakilir (sessizce yutulmaz).
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = data.get("rows") or []
    out: Dict[str, dict] = {}
    warn: List[str] = []
    for r in rows:
        key = str(r.get("path") or "").replace("\\", "/")
        if not key:
            warn.append("path alani bos bir satir atlandi")
            continue
        if key in out:
            warn.append(f"MUKERRER yol (ilki korundu): {key}")
            continue
        out[key] = r
    return out, warn


def pair_rows(a: Dict[str, dict], b: Dict[str, dict]) -> Tuple[List[Tuple[str, dict, dict]],
                                                               List[str], List[str]]:
    """Iki kosunun satirlarini YOL uzerinden eslestirir.

    Returns:
        (esleen_ucluler, yalniz_A_yollari, yalniz_B_yollari).
        FAIL-OPEN: eslesmeyenler DISLANIR ama raporda sayilir — eslestirilmis test
        yalnizca kesisim uzerinde mesrudur.
    """
    common = sorted(set(a) & set(b))
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    return [(p, a[p], b[p]) for p in common], only_a, only_b


def _is_anomaly(ra: dict, rb: dict) -> Optional[bool]:
    """Klibin anomali mi oldugunu iki kosudan okur; CELISKI varsa None (dislanir)."""
    va, vb = ra.get("is_anomaly"), rb.get("is_anomaly")
    if va is None or vb is None or bool(va) != bool(vb):
        return None
    return bool(va)


def contingency(pairs: Sequence[Tuple[str, dict, dict]],
                metric: Metric) -> Tuple[int, int, int, int, List[str], List[str]]:
    """Bir metrik icin 2x2 uyusmazlik tablosunu ve YON DEGISTIREN klipleri dondurur.

    Returns:
        (a, b, c, d, sadece_A_dogru_yollari, sadece_B_dogru_yollari)
        a: ikisi de dogru, b: yalniz A dogru, c: yalniz B dogru, d: hicbiri.
    """
    a = b = c = d = 0
    flip_a: List[str] = []
    flip_b: List[str] = []
    want_anom = (metric.subset == "anomali")
    for path, ra, rb in pairs:
        anom = _is_anomaly(ra, rb)
        if anom is None or anom != want_anom:
            continue
        oa, ob = bool(metric.ok(ra)), bool(metric.ok(rb))
        if oa and ob:
            a += 1
        elif oa and not ob:
            b += 1
            flip_a.append(path)
        elif ob and not oa:
            c += 1
            flip_b.append(path)
        else:
            d += 1
    return a, b, c, d, flip_a, flip_b


# ===========================================================================
# KARSILASTIRMA
# ===========================================================================

def compare(path_a: str, path_b: str, alpha: float = 0.05,
            label_a: str = "A", label_b: str = "B",
            project_n: Optional[int] = 100,
            metrics: Sequence[Metric] = METRICS,
            z: float = Z95) -> dict:
    """Iki eval sonucunu eslestirerek karsilastirir; tam rapor sozlugu dondurur.

    Args:
        path_a: temel (baseline) kosunun eval_*.json yolu
        path_b: mudahale (intervention) kosunun eval_*.json yolu
        alpha: anlamlilik esigi (karar exact McNemar ile)
        label_a/label_b: raporda gorunecek kosu adlari
        project_n: guc analizinde hedef klip sayisi (None -> guc bolumu atlanir)
        metrics: olculecek metrik kaydi (varsayilan METRICS)

    Returns:
        {"meta": ..., "metrics": {ad: {...}}, "power": {ad: {...}}, "warnings": [...]}
    """
    rows_a, warn_a = load_rows(path_a)
    rows_b, warn_b = load_rows(path_b)
    pairs, only_a, only_b = pair_rows(rows_a, rows_b)

    warnings: List[str] = [f"[A] {w}" for w in warn_a] + [f"[B] {w}" for w in warn_b]
    if only_a:
        warnings.append(f"{len(only_a)} klip YALNIZ A'da var, eslestirilemedi "
                        f"(ilk 3: {', '.join(only_a[:3])})")
    if only_b:
        warnings.append(f"{len(only_b)} klip YALNIZ B'de var, eslestirilemedi "
                        f"(ilk 3: {', '.join(only_b[:3])})")
    if not pairs:
        warnings.append("HIC eslesen klip yok — eslestirilmis test yapilamaz.")

    n_anom = sum(1 for p, ra, rb in pairs if _is_anomaly(ra, rb) is True)
    n_norm = sum(1 for p, ra, rb in pairs if _is_anomaly(ra, rb) is False)
    n_bad = len(pairs) - n_anom - n_norm
    if n_bad:
        warnings.append(f"{n_bad} klipte is_anomaly etiketi iki kosu arasinda CELISIYOR "
                        f"— bu klipler dislandi.")

    out_metrics: Dict[str, dict] = {}
    out_power: Dict[str, dict] = {}
    for m in metrics:
        a, b, c, d, flip_a, flip_b = contingency(pairs, m)
        if (a + b + c + d) == 0:
            continue
        res = mcnemar_test(a, b, c, d, alpha=alpha, z=z)
        res.update({
            "subset": m.subset,
            "label": m.label,
            "definition": m.desc,
            "flipped_only_a": flip_a,
            "flipped_only_b": flip_b,
        })
        # GA ile exact testin celisip celismedigini ACIKCA isaretle (durustluk)
        ci_excludes_zero = (res["diff_ci_low"] > 0.0) or (res["diff_ci_high"] < 0.0)
        res["ci_excludes_zero"] = ci_excludes_zero
        res["ci_test_disagree"] = bool(ci_excludes_zero != res["significant"])
        out_metrics[m.name] = res

        if project_n:
            n_pairs = a + b + c + d
            try:
                out_power[m.name] = project_to_n(b, c, n_pairs, project_n, alpha=alpha)
            except ValueError as e:  # b+c > n olamaz ama savunmaci kal
                warnings.append(f"{m.name}: guc analizi atlandi ({e})")

    return {
        "meta": {
            "file_a": os.path.relpath(path_a, ROOT).replace("\\", "/"),
            "file_b": os.path.relpath(path_b, ROOT).replace("\\", "/"),
            "label_a": label_a,
            "label_b": label_b,
            "n_pairs": len(pairs),
            "n_anomaly_pairs": n_anom,
            "n_normal_pairs": n_norm,
            "n_only_a": len(only_a),
            "n_only_b": len(only_b),
            "alpha": alpha,
            "project_n": project_n,
            "test": "McNemar exact (iki-yonlu binom, p=0.5)",
            "diff_ci": "Newcombe 1998 Method 10 (paired Wilson square-and-add, phi-corrected)",
        },
        "metrics": out_metrics,
        "power": out_power,
        "warnings": warnings,
    }


# ===========================================================================
# RAPORLAMA
# ===========================================================================

def _fmt_p(p: float) -> str:
    """p degerini okunabilir yaz: cok kucukse bilimsel gosterim."""
    if p >= 0.001:
        return f"{p:.4f}"
    if p > 0.0:
        return f"{p:.2e}"
    return "<1e-308"


def _fmt_signed_pct(x: float) -> str:
    return f"{'+' if x >= 0 else '-'}%{abs(x) * 100:.0f}"


def _fmt_diff_ci(lo: float, hi: float) -> str:
    return f"[{_fmt_signed_pct(lo)}, {_fmt_signed_pct(hi)}]"


def _subset_table(res: dict, subset: str, title: str, note: str) -> List[str]:
    rows = [(name, d) for name, d in res["metrics"].items() if d["subset"] == subset]
    if not rows:
        return []
    n_pairs = rows[0][1]["n_pairs"]
    lines = ["", f"--- {title}  (eslesen klip: {n_pairs}) ---", f"    {note}", ""]
    hdr = (f"{'Metrik':<20}{'A':>10}{'B':>10}{'ikisi':>7}{'b':>4}{'c':>4}{'yok':>5}"
           f"{'fark(B-A)':>11}{'fark %95 GA':>20}{'p_exact':>11}  karar")
    lines.append(hdr)
    lines.append("-" * len(hdr))
    for name, d in rows:
        ra, rb = d["rate_a"], d["rate_b"]
        cell_a = f"{ra['k']}/{ra['n']}"
        cell_b = f"{rb['k']}/{rb['n']}"
        karar = "ANLAMLI" if d["significant"] else "-"
        if d["ci_test_disagree"]:
            karar += " (!GA celisiyor)"
        lines.append(
            f"{name:<20}{cell_a:>10}{cell_b:>10}"
            f"{d['both']:>7}{d['b']:>4}{d['c']:>4}{d['neither']:>5}"
            f"{_fmt_signed_pct(d['diff_b_minus_a']):>11}"
            f"{_fmt_diff_ci(d['diff_ci_low'], d['diff_ci_high']):>20}"
            f"{_fmt_p(d['p_exact']):>11}  {karar}"
        )
    lines.append("")
    lines.append("  Nokta-oran + Wilson %95 (kol bazli, K15) ve metrik tanimi:")
    for name, d in rows:
        lines.append(f"    {name:<20} A: {fmt_rate_dict(d['rate_a']):<24} "
                     f"B: {fmt_rate_dict(d['rate_b']):<24}")
        lines.append(f"    {'':<20} dogru = {d['definition']}")
    return lines


def format_report(res: dict, show_flips: bool = False) -> str:
    """Karsilastirma sozlugunu insan-okur metne cevirir."""
    m = res["meta"]
    L: List[str] = []
    L.append("=" * 100)
    L.append("ESLESTIRILMIS A/B KARSILASTIRMA — McNemar TAM (exact) testi, iki-yonlu")
    L.append("=" * 100)
    L.append(f"  A (temel)    : {m['label_a']:<24} {m['file_a']}")
    L.append(f"  B (mudahale) : {m['label_b']:<24} {m['file_b']}")
    L.append(f"  Eslesen klip : {m['n_pairs']}  "
             f"(anomali {m['n_anomaly_pairs']} + normal {m['n_normal_pairs']}; "
             f"yalniz A: {m['n_only_a']}, yalniz B: {m['n_only_b']})")
    L.append(f"  alpha        : {m['alpha']}")
    L.append(f"  fark GA      : {m['diff_ci']}")
    L.append("  OKUMA: b = yalniz A dogru, c = yalniz B dogru. Yalnizca b ve c kanit tasir;")
    L.append("         'ikisi'/'yok' sutunlari kac klibin HIC degismedigini gosterir.")
    L.append("         Butun metrikler YUKSEK = IYI yonundedir (normalde 'FP yok' = dogru).")
    if res["warnings"]:
        L.append("")
        L.append("  UYARILAR:")
        for w in res["warnings"]:
            L.append(f"    ! {w}")

    L += _subset_table(res, "anomali", "ANOMALI klipler",
                       "olculen: TESPIT yetenegi (recall / kategori / risk / sevk)")
    L += _subset_table(res, "normal", "NORMAL klipler",
                       "olculen: YANLIS-ALARM (dusuk FP = yuksek 'dogru' orani)")

    if show_flips:
        L.append("")
        L.append("--- YON DEGISTIREN klipler (uyusmayan cifler) ---")
        for name, d in res["metrics"].items():
            if not (d["flipped_only_a"] or d["flipped_only_b"]):
                continue
            L.append(f"  {name}:")
            for p in d["flipped_only_a"]:
                L.append(f"    [b] yalniz A dogru : {p}")
            for p in d["flipped_only_b"]:
                L.append(f"    [c] yalniz B dogru : {p}")

    if res.get("power"):
        pn = m["project_n"]
        L.append("")
        L.append("=" * 100)
        L.append(f"GUC ANALIZI — mevcut n yeterli mi? n={pn}'de ne olur?")
        L.append("=" * 100)
        L.append("  Model: cift ya UYUSUR (kanit tasimaz) ya da uyusmaz; uyusmazsa "
                 "ratio=c/b oraninda B lehine.")
        L.append("  Guc: exact McNemar'in kosulsuz gucu (ayrik test oldugu icin "
                 "normal-yaklasimdan DUSUK cikar).")
        L.append("  'olceklenmis' satiri bir TAHMIN DEGIL: 'ayni oruntu n'de birebir "
                 "tekrarlanirsa' senaryosudur.")
        for name, pw in res["power"].items():
            obs, sc = pw["observed"], pw["scaled"]
            req = pw["required_n_power80"]
            req_a = pw["required_n_power80_analytic"]
            L.append("")
            L.append(f"  {name}  (alt kume: {res['metrics'][name]['subset']})")
            L.append(f"    gozlenen        : b={obs['b']} c={obs['c']}  n={obs['n']}  "
                     f"p={_fmt_p(obs['p_exact'])}  "
                     f"{'ANLAMLI' if obs['significant'] else 'ANLAMLI DEGIL'}")
            L.append(f"    uyusmazlik      : oran={pw['p_disagree']}  "
                     f"ratio(c/b)={pw['ratio_c_over_b']}")
            L.append(f"    mevcut n'de guc : %{pw['power_at_n_obs'] * 100:.0f}")
            L.append(f"    %80 guc icin n  : "
                     f"{req if req is not None else 'ulasilamaz (etki yok/cok kucuk)'}"
                     f"   (analitik saglama: {req_a if req_a is not None else 'n/a'})")
            L.append(f"    n={pn} senaryosu : b={sc['b']} c={sc['c']}  "
                     f"p={_fmt_p(sc['p_exact'])}  "
                     f"{'ANLAMLI' if sc['significant'] else 'ANLAMLI DEGIL'}")
            L.append(f"    n={pn}'de guc    : %{pw['power_at_n_target'] * 100:.1f}")
    L.append("")
    return "\n".join(L)


# ===========================================================================
# CLI
# ===========================================================================

def _default_files() -> List[str]:
    files = sorted(glob.glob(os.path.join(RESULTS_DIR, "eval_*.json")))
    return files[-2:]


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Iki eval_*.json sonucunu AYNI klipler uzerinde eslestirerek "
                    "karsilastirir (McNemar exact) ve istatistiksel guc analizi yapar.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Ornek:\n"
               "  python benchmark/paired_test.py results/eval_A.json results/eval_B.json \\\n"
               "      --label-a 'kurallar KAPALI' --label-b 'kurallar ACIK' --project-n 100\n")
    ap.add_argument("files", nargs="*", help="A.json B.json (bos ise en son iki sonuc)")
    ap.add_argument("--alpha", type=float, default=0.05, help="anlamlilik esigi (0.05)")
    ap.add_argument("--label-a", default=None, help="A kosusunun adi")
    ap.add_argument("--label-b", default=None, help="B kosusunun adi")
    ap.add_argument("--project-n", type=int, default=100,
                    help="guc analizinde hedef klip sayisi (0 -> guc bolumu kapali)")
    ap.add_argument("--json", dest="json_out", default=None,
                    help="tam sonucu bu yola JSON olarak yaz")
    ap.add_argument("--flips", action="store_true",
                    help="yon degistiren kliplerin yollarini da listele")
    args = ap.parse_args(list(argv) if argv is not None else None)

    files = list(args.files) or _default_files()
    if len(files) != 2:
        print("Iki sonuc dosyasi gerekli (bulunan: "
              f"{len(files)}). Ornek: python benchmark/paired_test.py A.json B.json",
              file=sys.stderr)
        return 2
    for f in files:
        if not os.path.isfile(f):
            print(f"Dosya yok: {f}", file=sys.stderr)
            return 2

    res = compare(
        files[0], files[1],
        alpha=args.alpha,
        label_a=args.label_a or "A (temel)",
        label_b=args.label_b or "B (mudahale)",
        project_n=(args.project_n or None),
    )
    print(format_report(res, show_flips=args.flips))

    if args.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)) or ".", exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=2)
        print(f"JSON yazildi: {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
