#!/usr/bin/env python
"""D43 PROB — BORU HATTI NEREDE BILGI KAYBEDIYOR? (K1 algi / K2 cikarim / K3 skorlama)

    python benchmark/bilgi_kaybi_prob.py --kuru         # klip secimini yazdir, model cagirma
    python benchmark/bilgi_kaybi_prob.py --kol boru     # A kolu: mevcut serbest-metin boru hatti
    python benchmark/bilgi_kaybi_prob.py --kol islemsel # B kolu: islemsel soru -> MEKANIK K1

TESHIS EDILEN CELISKI: model DOGRUDAN soruldugunda dogru cevap veriyor
(forklift MCC +0,847 · yelek +0,885 · pano +1,000) ama uctan uca boru hattimiz
isg_ozgul 2/99 aliyor. Bu prob bilginin HANGI ASAMADA kayboldugunu OLCER.

A KOLU (mevcut mimari) her klip icin SU UC METNI ayri ayri kaydeder:
  desc   : perceive'in SERBEST BETIMLEME ciktisi (VLM'in ham algisi)  -> K1
  events : betimlemeden cikarilan olay listesi                        -> K2
  isg_match(events+summary) : eslestiricinin verdigi hukum            -> K3
Ayni sozcuksel eslestirici (benchmark/labels.isg_match) UC METNE DE uygulanir;
boylece "bilgi vardi ama gecmedi" ile "bilgi hic yoktu" ayrilir.

B KOLU (ust sinir) ayni 30 klipte boru hattini BYPASS eder: tek video oturumu
acar, sinif ciftine ait ISLEMSEL soruyu sorar ve cevaptan MEKANIK olarak K1
sozlesmesi (events/risk/actions) uretir. Ayni eslestiriciyle puanlanir.

ONEMLI DURUSTLUK NOTU: B kolunun olay metni SABLONDUR, dolayisiyla eslestirici
"ihlal var" dendiginde HER ZAMAN yakalar. Bu yuzden B kolu icin isg_ozgul TEK
BASINA anlamsizdir; GUVENLI ES SINIFTAKI yanlis-pozitif oran (ozgulluk) HER
ZAMAN yaninda raporlanir. A kolu icin de ayni ozgulluk sayisi verilir.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

SET = os.path.join(KOK, "data/eval_defense")
SONUC = os.path.join(KOK, "benchmark/results")

# --- SINIF CIFTLERI: her ciftten 5 GUVENSIZ + 2-3 GUVENLI = 30 klip ---
CIFTLER = [
    {"ad": "forklift", "ihlal": "Anomali/Carrying_Overload_with_Forklift",
     "normal": "Normal/Safe_Carrying", "n_ihlal": 5, "n_normal": 3},
    {"ad": "yetki", "ihlal": "Anomali/Unauthorized_Intervention",
     "normal": "Normal/Authorized_Intervention", "n_ihlal": 5, "n_normal": 2},
    {"ad": "pano", "ihlal": "Anomali/Opened_Panel_Cover",
     "normal": "Normal/Closed_Panel_Cover", "n_ihlal": 5, "n_normal": 2},
    {"ad": "yol", "ihlal": "Anomali/Safe_Walkway_Violation",
     "normal": "Normal/Safe_Walkway", "n_ihlal": 5, "n_normal": 3},
]


def klip_sec():
    """Deterministik secim: alfabetik sirada esit araliklarla ornekle (cherry-pick YOK)."""
    secili = []
    for c in CIFTLER:
        for alt, n, ihlal in ((c["ihlal"], c["n_ihlal"], True),
                              (c["normal"], c["n_normal"], False)):
            ps = sorted(glob.glob(os.path.join(SET, alt, "*.mp4")))
            if not ps:
                continue
            adim = len(ps) / n
            sec = [ps[min(len(ps) - 1, int(i * adim))] for i in range(n)]
            for p in sec:
                secili.append({"yol": p, "cift": c["ad"], "ihlal": ihlal, "alt": alt})
    return secili


# ---------------------------------------------------------------- B kolu sorular
# Kaynak: benchmark/islemsel_prompt_prob.py KOLLAR (kaynak makalenin GOZLEMLENEBILIR
# olcutleri: "3 blocks or more", "wearing a green vest"). Yeniden turetilmez.
SISTEM_ISLEMSEL = ("Sen bir endustriyel is guvenligi kamerasi analiz sistemisin. Sana bir "
                   "guvenlik kamerasindan alinmis video verilir. YALNIZCA GORDUGUNE dayan.")

ISLEMSEL = {
    "forklift": {
        "soru": ("Forkliftin CATALINDA ust uste kac adet kasa/blok tasiniyor? "
                 "Yalnizca sayiyi yaz."),
        "secenek": ["0", "1", "2", "3", "4", "5", "6+", "GORUNMUYOR"],
        # NOT: sablon metinler TAM TURKCE (diakritikli) yazilir. Ilk surumde ASCII
        # yazilmisti ve `isg_match` yetki sinifini KACIRDI ("yetkisiz mudahale" !=
        # "yetkisiz müdahale") — bu, K3'un (sozcuksel skorlayici kirilganligi)
        # kazara ama net bir kanitidir; olcum notlarinda BOYLE raporlanir.
        "olay": ("Forklift çatalında {c} kasa istiflenmiş — aşırı yük taşınıyor, "
                 "yük dengesiz ve sürücünün görüşü engelli, devrilme riski var"),
        "kategori": "Güvenlik", "severity": "Yüksek",
        "aksiyon": "Forklift operatorunu durdur; yuku guvenli kapasiteye (en fazla 2 kasa) indirt",
    },
    "yetki": {
        "soru": "Makinenin/panonun BASINDA DURAN KISIDE yesil reflektif yelek var mi?",
        "secenek": ["YELEK_VAR", "YELEK_YOK", "KISI_YOK", "GORUNMUYOR"],
        "olay": ("Yelek takmayan bir kişi makineye müdahale ediyor — yetkisiz müdahale"),
        "kategori": "Yetkisiz Erişim", "severity": "Yüksek",
        "aksiyon": "Yetkisiz kisiyi makineden uzaklastir; yetkili teknisyen cagir",
    },
    "pano": {
        "soru": ("Makinenin PANO BOLGESINDE koyu/karanlik bir oyuk (acik kapagin arkasindaki "
                 "bosluk) gorunuyor mu, yoksa orasi duz bir yuzey mi?"),
        "secenek": ["EVET_KOYU_OYUK", "HAYIR_DUZ_YUZEY", "GORUNMUYOR"],
        "olay": ("Elektrik panosu kapağı açık bırakılmış — pano kapağı açık, "
                 "canlı terminaller açıkta"),
        "kategori": "Güvenlik", "severity": "Yüksek",
        "aksiyon": "Pano kapagini kapat ve kilitle; elektrik bakim ekibini bilgilendir",
    },
    "yol": {
        "soru": ("Yerdeki SARI/BEYAZ isaretli yaya seridine bak. Yuruyen kisi bu seridin "
                 "ICINDE mi, yoksa DISINDA (makine/forklift sahasinda) mi?"),
        "secenek": ["SERIT_ICINDE", "SERIT_DISINDA", "KISI_YOK", "GORUNMUYOR"],
        "olay": ("Personel işaretli yaya yolunun dışında yürüyor — yürüme yolu ihlali, "
                 "yol dışına çıkılmış"),
        "kategori": "Güvenlik", "severity": "Yüksek",
        "aksiyon": "Personeli isaretli yaya yoluna yonlendir; saha amirini bilgilendir",
    },
}


def _yorumla(cift: str, cevap: str):
    """True=ihlal · False=ihlal yok · None=karar yok · 'HATA'"""
    c = (cevap or "").strip().upper()
    if not c:
        return None
    if c.startswith("__HATA__"):
        return "HATA"
    if cift == "forklift":
        if c.startswith("GORUNMUYOR"):
            return None
        sayilar = re.findall(r"\d+", c)
        if not sayilar:
            return None
        return int(sayilar[-1]) >= 3
    if cift == "yetki":
        if c.startswith("YELEK_YOK"):
            return True
        if c.startswith("YELEK_VAR"):
            return False
        return None
    if cift == "pano":
        if c.startswith("EVET"):
            return True
        if c.startswith("HAYIR"):
            return False
        return None
    if cift == "yol":
        if c.startswith("SERIT_DISINDA"):
            return True
        if c.startswith("SERIT_ICINDE"):
            return False
        return None
    return None


def kunye(argv) -> dict:
    from dilajan.config import settings as s
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=KOK,
                                capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        commit = "?"
    return {
        "zaman": datetime.now().isoformat(timespec="seconds"),
        "git_commit": commit, "argv": argv,
        "base_url": s.base_url, "uzak_api": s.uzak_api_mi,
        "model_name": s.model_name,
        "gorev_modelleri": {g: s.gorev_modeli(g)
                            for g in ("algi", "sayim", "yapi", "ozet", "diyalog")},
        "mock_mode": s.mock_mode, "temperature": s.temperature,
        "fps_sample": s.fps_sample, "frame_max_side": s.frame_max_side,
        "max_frames_per_segment": s.max_frames_per_segment,
        "isg_lens": s.isg_lens, "threat_interpretation": s.threat_interpretation,
        "single_pass_perceive": s.single_pass_perceive,
        "verify_events": s.verify_events, "spatial_grounding": s.spatial_grounding,
        "adaptive_reexamine": s.adaptive_reexamine,
        "panel_roi": s.panel_roi, "forklift_yuk": s.forklift_yuk,
        "use_detector": s.use_detector,
    }


def saglik() -> str:
    from dilajan.config import settings as s
    if getattr(s, "mock_mode", False):
        return "mock_mode ACIK — olcum anlamsiz"
    from dilajan.llm_client import VLMClient
    try:
        c = VLMClient().chat([{"role": "user", "content": "1"}], max_tokens=2, temperature=0.0)
        return "" if c else "bos yanit"
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def _kullanici_metni(messages) -> str:
    for m in messages:
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            for p in c:
                if isinstance(p, dict) and p.get("type") == "text":
                    return p.get("text", "")
    return ""


# =========================================================== A KOLU: BORU HATTI
def kol_boru(secili, cikti_yolu, kunye_d):
    """Mevcut boru hattini kosar; HER VLM cagrisini kaydeder (desc yakalanabilsin)."""
    import dilajan.llm_client as lc

    kayit = {"cagrilar": []}
    _af = lc.VLMClient.analyze_frames
    _chat = lc.VLMClient.chat

    def af(self, frames, instruction, *a, **kw):
        out = _af(self, frames, instruction, *a, **kw)
        kayit["cagrilar"].append({"tur": "analyze_frames", "model": self.model,
                                  "instr_bas": (instruction or "")[:160], "cikti": out})
        return out

    def chat(self, messages, *a, **kw):
        out = _chat(self, messages, *a, **kw)
        kayit["cagrilar"].append({"tur": "chat", "model": self.model,
                                  "instr_bas": _kullanici_metni(messages)[:160],
                                  "cikti": out})
        return out

    lc.VLMClient.analyze_frames = af
    lc.VLMClient.chat = chat
    try:
        from dilajan.agent.graph import analyze_video
        satirlar = []
        for i, k in enumerate(secili, 1):
            kayit["cagrilar"] = []
            t0 = time.time()
            try:
                res = analyze_video(k["yol"])
                hata = ""
            except Exception as e:
                res, hata = None, f"{type(e).__name__}: {e}"
            dt = time.time() - t0
            desc = [c["cikti"] for c in kayit["cagrilar"]
                    if c["tur"] == "analyze_frames" and c["instr_bas"].startswith("Bu kareler bir")]
            ext = [c["cikti"] for c in kayit["cagrilar"]
                   if c["tur"] == "chat" and "sahne a" in c["instr_bas"]]
            r = {"yol": os.path.relpath(k["yol"], KOK).replace("\\", "/"),
                 "cift": k["cift"], "ihlal": k["ihlal"], "alt": k["alt"],
                 "hata": hata, "sure_s": round(dt, 1),
                 "desc": desc, "ext_ham": ext, "n_cagri": len(kayit["cagrilar"]),
                 "tum_cagrilar": [{"tur": c["tur"], "instr_bas": c["instr_bas"]}
                                  for c in kayit["cagrilar"]]}
            if res is not None:
                r["summary"] = res.summary
                r["events"] = [{"time": e.time, "event": e.event,
                                "severity": e.severity.value,
                                "category": e.category.value} for e in res.events]
                r["risk"] = res.risk.level.value
                r["actions"] = [a.action for a in res.actions]
                r["trace"] = list(res.decision_trace or [])
            satirlar.append(r)
            print(f"  [{i}/{len(secili)}] {os.path.basename(k['yol'])} "
                  f"({k['cift']}, {'IHLAL' if k['ihlal'] else 'normal'}) "
                  f"{dt:.0f}s n_olay={len(r.get('events', []))} {hata}", flush=True)
            with open(cikti_yolu, "w", encoding="utf-8") as f:
                json.dump({"kol": "boru", "kunye": kunye_d, "satirlar": satirlar},
                          f, ensure_ascii=False, indent=1)
        return satirlar
    finally:
        lc.VLMClient.analyze_frames = _af
        lc.VLMClient.chat = _chat


# ====================================================== B KOLU: ISLEMSEL BYPASS
#: KACIS SECENEKLERI — D40 dersi [1]/[2]: "ayirt edemiyorsan kacis kullan" cumlesi +
#: secenek listesindeki kacis, modeli KACMAYA egitiyor (olculdu: sistem promptu VAR +
#: kacis VAR -> MCC +0,000, kacis orani %86; ikisi de YOK -> MCC +0,885). `--kacissiz`
#: bu iki degiskeni birlikte kaldirir.
KACIS = {"GORUNMUYOR", "KISI_YOK"}


def kol_islemsel(secili, cikti_yolu, kunye_d, alias: str = "", kacissiz: bool = False):
    from dilajan.llm_client import VLMClient
    from dilajan.video import servis_videosu

    istemci = VLMClient()
    if alias:
        # D42 dersi [5]: modeller ZIT uzmanlasmis — sayma/geometri llm-large,
        # kisi/oznitelik vlm. Alias KUNYEYE yazilir, sessiz kaymaz.
        istemci = istemci.model_ile(alias)
    sistem = "" if kacissiz else SISTEM_ISLEMSEL
    satirlar = []
    for i, k in enumerate(secili, 1):
        cfg = ISLEMSEL[k["cift"]]
        t0 = time.time()
        try:
            baytlar = servis_videosu(k["yol"], max_side=1280, crf=26)
        except Exception as e:
            satirlar.append({"yol": os.path.relpath(k["yol"], KOK).replace("\\", "/"),
                             "cift": k["cift"], "ihlal": k["ihlal"],
                             "hata": f"kodlama: {type(e).__name__}: {e}"})
            continue
        ot = istemci.video_oturumu(baytlar, system=sistem)
        secenek = [s for s in cfg["secenek"] if s not in KACIS] if kacissiz else cfg["secenek"]
        ham = ot.sor(cfg["soru"], guided_choice=secenek, temperature=0.0,
                     max_tokens=24, hatirla=False) if ot.hazir else None
        if ham is None:
            ham = f"__HATA__ {ot.hata}"
        karar = _yorumla(k["cift"], ham)
        dt = time.time() - t0
        r = {"yol": os.path.relpath(k["yol"], KOK).replace("\\", "/"),
             "cift": k["cift"], "ihlal": k["ihlal"], "alt": k["alt"],
             "soru": cfg["soru"], "ham": ham, "karar": karar,
             "model": istemci.model, "kacissiz": kacissiz, "secenek": secenek,
             "sure_s": round(dt, 1), "video_mb": round(len(baytlar) / 1e6, 2)}
        if karar is True:
            n = re.findall(r"\d+", ham or "")
            r["events"] = [{"time": "00:00",
                            "event": cfg["olay"].format(c=n[-1] if n else "3+"),
                            "severity": cfg["severity"], "category": cfg["kategori"]}]
            r["summary"] = cfg["olay"].format(c=n[-1] if n else "3+") + "."
            r["risk"] = cfg["severity"]
            r["actions"] = [cfg["aksiyon"]]
        else:
            r["events"] = []
            r["summary"] = ("Islemsel kontrolde ihlal olcutu saglanmadi."
                            if karar is False else
                            "Islemsel kontrol karar veremedi.")
            r["risk"] = "Düşük"
            r["actions"] = []
        satirlar.append(r)
        print(f"  [{i}/{len(secili)}] {os.path.basename(k['yol'])} "
              f"({k['cift']}, {'IHLAL' if k['ihlal'] else 'normal'}) "
              f"ham={ham!r} karar={karar} {dt:.0f}s", flush=True)
        with open(cikti_yolu, "w", encoding="utf-8") as f:
            json.dump({"kol": "islemsel", "kunye": kunye_d, "satirlar": satirlar},
                      f, ensure_ascii=False, indent=1)
    return satirlar


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kuru", action="store_true")
    ap.add_argument("--kol", choices=["boru", "islemsel"], default=None)
    ap.add_argument("--cikti", default="")
    ap.add_argument("--n", type=int, default=0, help="ilk N klip (deneme kosusu)")
    ap.add_argument("--alias", default="", help="islemsel kolda model alias (or. vlm)")
    ap.add_argument("--ciftler", default="", help="virgullu sinif cifti filtresi")
    ap.add_argument("--kacissiz", action="store_true",
                    help="kacis secenegini VE sistem promptunu kaldir (D40 dersi [2])")
    a = ap.parse_args()

    secili = klip_sec()
    if a.ciftler:
        istenen = {c.strip() for c in a.ciftler.split(",") if c.strip()}
        secili = [k for k in secili if k["cift"] in istenen]
    if a.n:
        secili = secili[:a.n]
    print(f"SECILEN KLIP: {len(secili)}")
    for k in secili:
        print(f"  {'IHLAL ' if k['ihlal'] else 'normal'} {k['cift']:9s} "
              f"{os.path.relpath(k['yol'], KOK)}")
    if a.kuru or not a.kol:
        sys.exit(0)

    h = saglik()
    if h:
        print(f"\n!! SAGLIK KONTROLU BASARISIZ: {h}\nKOSUM BASLAMADI.")
        sys.exit(2)
    ku = kunye(sys.argv)
    ku["islemsel_alias"] = a.alias or "(varsayilan model_name)"
    ku["kacissiz"] = a.kacissiz
    print("\nKUNYE:", json.dumps(ku, ensure_ascii=False))
    os.makedirs(SONUC, exist_ok=True)
    dmg = datetime.now().strftime("%Y%m%d_%H%M%S")
    yol = a.cikti or os.path.join(SONUC, f"bilgi_kaybi_{a.kol}_{dmg}.json")
    print(f"CIKTI: {yol}\n")
    if a.kol == "boru":
        kol_boru(secili, yol, ku)
    else:
        kol_islemsel(secili, yol, ku, alias=a.alias, kacissiz=a.kacissiz)
    print(f"\nBITTI -> {yol}")
