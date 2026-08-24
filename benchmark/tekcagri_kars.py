#!/usr/bin/env python
"""D42 — TEK CAGRI vs COK ASAMALI BORU HATTI: birlesik karsilastirma + sozlesme yuvarlak-yolculugu."""
import glob, json, os, re, statistics, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(KOK, "benchmark", "results")

tek = json.load(open(sorted(glob.glob(R + "/tekcagri_k1_*.json"))[-1], encoding="utf-8"))
borular = sorted(glob.glob(R + "/tekcagri_boru_*.json"))
b_var = json.load(open(borular[-1], encoding="utf-8"))     # video-path (12 klip)
b_ilk = json.load(open(borular[-2], encoding="utf-8"))     # varsayilan (image-path, 12 klip)

YOL = {k["etiket"]: k["yol"] for k in tek["klipler"]}
ANOM = {k["etiket"]: k["anomali"] for k in tek["klipler"]}


def sure_s(rel):
    try:
        o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", os.path.join(KOK, rel)],
                           capture_output=True, text=True, timeout=60)
        return float(o.stdout.strip())
    except Exception:
        return None


SUR = {e: sure_s(y) for e, y in YOL.items()}


def mmss_s(t):
    m = re.match(r"^(\d{2}):(\d{2})$", str(t))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def zaman_ihlali(cikti, klip):
    """Bicimi gecerli AMA klip suresini ASAN zaman damgasi (sema yakalayamaz)."""
    d = SUR.get(klip)
    if not d or not cikti:
        return 0, 0
    ts = [mmss_s(e.get("time")) for e in (cikti.get("events") or [])]
    ts = [t for t in ts if t is not None]
    return sum(1 for t in ts if t > d + 1.0), len(ts)


print("=" * 100)
print("A) GECIKME / CAGRI / TOKEN")
print("=" * 100)
satirlar = {}
for kol in ["L-strict", "F-strict", "L-serbest"]:
    rs = [r for r in tek["satirlar"] if r["kol"] == kol and "sure_s" in r]
    satirlar[kol] = {"sure": [r["sure_s"] for r in rs], "cagri": [1] * len(rs),
                     "ptok": [r["girdi_token"] for r in rs], "ctok": [r["cikti_token"] for r in rs]}
for ad, kaynak in [("BORU-varsayilan(image)", b_ilk), ("BORU-video-path", b_var)]:
    rs = [r for r in kaynak["satirlar"] if "sure_s" in r]
    satirlar[ad] = {"sure": [r["sure_s"] for r in rs], "cagri": [r["cagri_sayisi"] for r in rs],
                    "ptok": [r["girdi_token"] for r in rs], "ctok": [r["cikti_token"] for r in rs]}

print("%-22s %8s %8s %8s %10s %10s %10s" % ("kol", "medyan_s", "ort_s", "max_s", "medyan_cagri", "ort_girdi_tok", "ort_cikti_tok"))
for k, v in satirlar.items():
    print("%-22s %8.1f %8.1f %8.1f %10.1f %10.0f %10.0f"
          % (k, statistics.median(v["sure"]), statistics.mean(v["sure"]), max(v["sure"]),
             statistics.median(v["cagri"]), statistics.mean(v["ptok"]), statistics.mean(v["ctok"])))

print()
print("=" * 100)
print("B) SOZLESME DENETIMI (n=12 klip / kol)")
print("=" * 100)
print("%-22s %9s %9s %6s %6s %8s %9s %10s %12s" %
      ("kol", "ayr.hata", "kurtarma", "tam4", "fazla", "time_ok", "risk_kume", "actions_bos", "sure_disi_ts"))
for kol in ["L-strict", "F-strict", "L-serbest"]:
    rs = [r for r in tek["satirlar"] if r["kol"] == kol]
    ha = sum(1 for r in rs if r.get("ayristirma") is None)
    ku = sum(1 for r in rs if r.get("ayristirma") == "kurtarma")
    t4 = sum(1 for r in rs if r.get("denetim", {}).get("tam4"))
    fz = sum(1 for r in rs if r.get("denetim", {}).get("fazla"))
    mm = sum(1 for r in rs if r.get("denetim", {}).get("time_mmss"))
    rk = sum(1 for r in rs if r.get("denetim", {}).get("risk_kumede"))
    ab = sum(1 for r in rs if r.get("denetim", {}).get("actions_bos"))
    ih = to = 0
    for r in rs:
        a, b = zaman_ihlali(r.get("cikti"), r["klip"]); ih += a; to += b
    print("%-22s %9d %9d %6d %6d %8d %9d %10d %12s" % (kol, ha, ku, t4, fz, mm, rk, ab, "%d/%d" % (ih, to)))
for ad, kaynak in [("BORU-varsayilan(image)", b_ilk), ("BORU-video-path", b_var)]:
    rs = [r for r in kaynak["satirlar"] if "denetim" in r]
    t4 = sum(1 for r in rs if r["denetim"]["tam4"])
    mm = sum(1 for r in rs if r["denetim"]["time_mmss"])
    rk = sum(1 for r in rs if r["denetim"]["risk_kumede"])
    ab = sum(1 for r in rs if r["denetim"]["actions_bos"])
    ih = to = 0
    for r in rs:
        a, b = zaman_ihlali(r.get("cikti"), r["klip"]); ih += a; to += b
    print("%-22s %9s %9s %6d %6d %8d %9d %10d %12s" % (ad, "-(pydantic)", "-", t4, 0, mm, rk, ab, "%d/%d" % (ih, to)))

print()
print("=" * 100)
print("C) ICERIK: risk kalibrasyonu + olay uretimi (ayni 12 klip)")
print("=" * 100)
print("%-22s %-24s %-24s %-14s" % ("kol", "anomali risk>=Yuksek", "normal risk=Dusuk", "toplam olay"))
for kol in ["L-strict", "F-strict", "L-serbest"]:
    rs = [r for r in tek["satirlar"] if r["kol"] == kol]
    an = [r for r in rs if r["anomali"]]; no = [r for r in rs if not r["anomali"]]
    a_ok = sum(1 for r in an if r["denetim"]["risk"] in ("Yüksek", "Kritik"))
    n_ok = sum(1 for r in no if r["denetim"]["risk"] == "Düşük")
    tev = sum(r["denetim"].get("n_event") or 0 for r in rs)
    print("%-22s %-24s %-24s %-14d" % (kol, "%d/%d" % (a_ok, len(an)), "%d/%d" % (n_ok, len(no)), tev))
for ad, kaynak in [("BORU-varsayilan(image)", b_ilk), ("BORU-video-path", b_var)]:
    rs = [r for r in kaynak["satirlar"] if "denetim" in r]
    an = [r for r in rs if r["anomali"]]; no = [r for r in rs if not r["anomali"]]
    a_ok = sum(1 for r in an if r["denetim"]["risk"] in ("Yüksek", "Kritik"))
    n_ok = sum(1 for r in no if r["denetim"]["risk"] == "Düşük")
    tev = sum(r["denetim"]["n_event"] for r in rs)
    print("%-22s %-24s %-24s %-14d" % (ad, "%d/%d" % (a_ok, len(an)), "%d/%d" % (n_ok, len(no)), tev))

print()
print("=" * 100)
print("D) KLIP BAZINDA RISK — tek cagri vs boru hatti")
print("=" * 100)
bv = {r["klip"]: r for r in b_var["satirlar"] if "denetim" in r}
bi = {r["klip"]: r for r in b_ilk["satirlar"] if "denetim" in r}
tk = {}
for r in tek["satirlar"]:
    tk.setdefault(r["kol"], {})[r["klip"]] = r
print("%-24s %-6s %-10s %-10s %-14s %-14s" % ("klip", "anom", "TEK-L", "TEK-F", "BORU-video", "BORU-varsayilan"))
for e in YOL:
    print("%-24s %-6s %-10s %-10s %-14s %-14s" % (
        e, ANOM[e], tk["L-strict"][e]["denetim"]["risk"], tk["F-strict"][e]["denetim"]["risk"],
        bv[e]["denetim"]["risk"] if e in bv else "-", bi[e]["denetim"]["risk"] if e in bi else "-"))

print()
print("=" * 100)
print("E) SOZLESME YUVARLAK-YOLCULUGU: tek-cagri JSON -> AnalysisResult -> to_sartname_dict()")
print("=" * 100)
from dilajan.schema import AnalysisResult, Event, Action, RiskAssessment, Severity
ok = bozuk = 0
for r in tek["satirlar"]:
    if r["kol"] != "L-strict" or not r.get("cikti"):
        continue
    c = r["cikti"]
    try:
        ar = AnalysisResult(
            summary=c["summary"],
            events=[Event(time=e["time"], event=e["event"]) for e in c["events"]],
            risk=RiskAssessment(level=Severity(c["risk"]), rationale="(tek cagri: gerekce alani YOK)"),
            actions=[Action(action=a) for a in c["actions"]],
        )
        geri = ar.to_sartname_dict()
        ayni = (geri == c)
        ok += ayni; bozuk += (not ayni)
        if not ayni:
            print("  FARK:", r["klip"])
    except Exception as ex:
        bozuk += 1
        print("  KURULAMADI %s: %s" % (r["klip"], str(ex)[:120]))
print("  BIREBIR yuvarlak-yolculuk: %d/%d  (bozuk %d)" % (ok, ok + bozuk, bozuk))

print()
print("=" * 100)
print("F) TEK CAGRININ VERMEDIGI ALANLAR (boru hattinin urettigi, sartname/aciklanabilirlik)")
print("=" * 100)
print("  tek cagri semasi alanlari      :", ["summary", "events(time,event)", "risk", "actions"])
print("  boru hattinin ek urettikleri   :", ["event.severity", "event.category", "event.bbox/region",
                                             "risk.rationale", "action.priority/rationale",
                                             "decision_trace", "triggered_functions", "action_log",
                                             "query_answer"])
