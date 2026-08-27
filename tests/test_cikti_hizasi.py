#!/usr/bin/env python
"""analyze() yield SIRASI ile analyze_btn.click(outputs=[...]) SIRASI hizali mi?

NEDEN AYRI BIR TEST: `test_query_driven.py` yalnizca ARITEYI dogruluyor
(13 + status = 14). Arite, ogeler YER DEGISTIRSE de ayni kalir — yani
ISG panelinin HTML'i "operasyon ozeti" kutusuna basilsa test GECERDI.
2026-08-25'te ISG paneli 4. sıraya eklenirken bu bosluk fark edildi;
ayrica ayni yamada panel bilesenі KAZARA IKI KEZ eklenmisti (ikincisi
adi yeniden bagladi, birincisi olu bir yer-tutucu olarak ekranda kaldi).
Bu test her iki kusur sinifini da yakalar.
"""
import os, re, sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import tests.taban as taban  # noqa: E402
taban.taban_uygula()

g = k = 0
def c(ad, kosul):
    global g, k
    if kosul: g += 1; print(f"  ok   {ad}")
    else: k += 1; print(f"  KALAN {ad}")

KAYNAK = open(os.path.join(KOK, "app.py"), encoding="utf-8").read()

# --- outputs=[...] listesi (analyze_btn.click icindeki) ---
# DIKKAT: "analyze_btn.click" ilk once bir YORUM satirinda geciyor
# (`analyze_btn.click(outputs=[...])`). Gercek CAGRIYI ara.
bas = KAYNAK.index("analyze_btn.click(" + chr(10))
m = re.search(r"outputs=\[([^\]]*)\]", KAYNAK[bas:bas + 1200], re.S)
cikislar = [x.strip() for x in m.group(1).split(",") if x.strip()]

# --- son (dolu) yield'in ogeleri ---
g0 = KAYNAK.index("def analyze(")
govde = KAYNAK[g0:KAYNAK.index("\ndef ", g0 + 10)]
son = [mm for mm in re.finditer(r"yield \(", govde)][-1].end()
derinlik, i = 1, son
while derinlik:
    if govde[i] == "(": derinlik += 1
    elif govde[i] == ")": derinlik -= 1
    i += 1
ic = govde[son:i - 1]

# ust duzey virgullere gore bol (ic parantez/koseli/suslu sayilmaz)
ogeler, d, cur = [], 0, ""
for ch in ic:
    if ch in "([{": d += 1
    elif ch in ")]}": d -= 1
    if ch == "," and d == 0:
        ogeler.append(cur.strip()); cur = ""
    else:
        cur += ch
if cur.strip(): ogeler.append(cur.strip())
ogeler = [" ".join(o.split()) for o in ogeler]

print("=== ARITE ===")
c(f"outputs uzunlugu {len(cikislar)} == yield uzunlugu {len(ogeler)}",
  len(cikislar) == len(ogeler))

# --- SIRA: her cikis bilesenine, o konumdaki yield ifadesinde beklenen izler ---
BEKLENEN = {
    "status_out":   ("_pipeline_html", "_alert"),
    "query_out":    ("query_block",),
    "summary_out":  ("summary",),
    "risk_out":     ("risk",),
    "isg_out":      ("_isg_panel_html", "isg_panel"),
    "timeline_out": ("timeline",),
    "events_out":   ("events_rows",),
    "actions_out":  ("actions_md",),
    "funcs_out":    ("funcs_md",),
    "trace_out":    ("trace",),
    "json_out":     ("raw", "json"),   # raw = json.dumps(result.model_dump())
    "path_state":   ("path", "video"),
}
print("=== SIRA HIZASI ===")
for idx, bilesen in enumerate(cikislar):
    izler = BEKLENEN.get(bilesen)
    if not izler or idx >= len(ogeler):
        continue
    ifade = ogeler[idx]
    c(f"[{idx}] {bilesen} <- {ifade[:44]}", any(t in ifade for t in izler))

# --- MUKERRER BILESEN ---
print("=== MUKERRER BILESEN YOK ===")
c("outputs listesinde tekrar eden bilesen yok", len(set(cikislar)) == len(cikislar))
for ad in ("isg_out", "risk_out", "summary_out", "timeline_out"):
    n = len(re.findall(rf"^\s+{ad} = gr\.", KAYNAK, re.M))
    c(f"{ad} TEK KEZ tanimlanmis (bulunan: {n})", n == 1)

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
