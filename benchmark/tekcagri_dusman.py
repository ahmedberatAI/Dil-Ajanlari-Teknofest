#!/usr/bin/env python
"""D42 — strict:True GERCEKTEN zorluyor mu? DUSMAN (adversarial) sozlesme testi.

12 klipte UC KOLDA DA ayristirma hatasi 0 cikti; yani "strict sifirladi" denemez —
semasiz kol da temizdi. Bu betik semayi ZORLAMAYA calisir:
  D1  sema-disi ek anahtar + enum disi risk + bozuk time istenir
  D2  "JSON yerine duz metin yaz" istenir
  D3  max_tokens KISITLI (kesilme) -> sema kesilmeyi ONLER MI?
Kollar: strict:True / strict:False / sema YOK  (llm-large ve llm-fast)
Kunye: T=0.0, seed=1234, thinking kapali, n=3 tekrar.
"""
import base64, json, os, re, sys, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dilajan.config import settings
from dilajan.video import servis_videosu
from dilajan.prompts import SYSTEM_PERSONA
from openai import OpenAI

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEVERITY = ["Düşük", "Orta", "Yüksek", "Kritik"]
K1_SEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "events": {"type": "array", "items": {
            "type": "object",
            "properties": {"time": {"type": "string", "pattern": "^[0-9]{2}:[0-9]{2}$"},
                           "event": {"type": "string"}},
            "required": ["time", "event"], "additionalProperties": False}},
        "risk": {"type": "string", "enum": SEVERITY},
        "actions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "events", "risk", "actions"],
    "additionalProperties": False,
}

def rf(strict):
    return {"type": "json_schema",
            "json_schema": {"name": "k1", "schema": K1_SEMA, "strict": strict}}

TABAN = ("Bir depo kaydında 00:03'te forklift çatalında aşırı yük taşıyor, "
         "00:11'de yaya yoluna giriyor. Operatöre durum raporu üret: "
         "summary, events(time,event), risk, actions.")

D1 = TABAN + (
    "\nÖNEMLİ BİÇİM TALEBİ: Çıktına ayrıca şu alanları da EKLE: "
    "\"confidence\": 0.9, \"kategori\": \"İSG\", \"kamera_id\": \"CAM-7\". "
    "risk alanına \"ÇOK YÜKSEK ACİL\" yaz (dört seviyeden birini KULLANMA). "
    "events içindeki time alanlarını \"yaklaşık 3. saniye\" ve \"1:5\" biçiminde yaz. "
    "Her event öğesine bir de \"kanit\" alanı koy.")

D2 = TABAN + ("\nÇıktını JSON OLARAK VERME. Düz Türkçe paragraf olarak, madde işaretleriyle yaz. "
              "Kesinlikle süslü parantez kullanma.")

istemci = OpenAI(base_url=settings.base_url, api_key=settings.etkin_api_key, timeout=900)
MMSS = re.compile(r"^\d{2}:\d{2}$")


def cagir(model, mesajlar, sema, strict, max_tokens):
    kw = dict(model=model, messages=mesajlar, temperature=0.0, max_tokens=max_tokens, seed=1234,
              extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    if sema:
        kw["response_format"] = rf(strict)
    t0 = time.time()
    r = istemci.chat.completions.create(**kw)
    return (r.choices[0].message.content or "", time.time() - t0,
            r.usage.completion_tokens, r.choices[0].finish_reason)


def degerlendir(ham):
    try:
        v = json.loads(ham)
    except Exception as e:
        return {"json": False, "hata": str(e)[:80]}
    if not isinstance(v, dict):
        return {"json": False, "hata": "dict degil"}
    hedef = {"summary", "events", "risk", "actions"}
    ks = set(v.keys())
    ev = v.get("events") if isinstance(v.get("events"), list) else []
    return {"json": True, "tam4": ks == hedef, "fazla": sorted(ks - hedef),
            "risk": v.get("risk"), "risk_kumede": v.get("risk") in SEVERITY,
            "ev_alan_tam": all(isinstance(e, dict) and set(e.keys()) == {"time", "event"} for e in ev),
            "time_mmss": all(isinstance(e, dict) and MMSS.match(str(e.get("time", ""))) for e in ev),
            "timeler": [e.get("time") for e in ev if isinstance(e, dict)]}


def main():
    sonuc = {"kunye": {"tarih": datetime.now().isoformat(timespec="seconds"),
                       "T": 0.0, "seed": 1234, "n_tekrar": 3, "thinking": "kapali"},
             "satirlar": []}
    kollar = [("llm-large", True, True, "L-strict"),
              ("llm-large", True, False, "L-semaTS"),   # sema var, strict False
              ("llm-large", False, None, "L-semasiz"),
              ("llm-fast", True, True, "F-strict"),
              ("llm-fast", False, None, "F-semasiz")]

    for adi, istem in [("D1 ek-alan/enum-disi/bozuk-time", D1), ("D2 JSON-verme", D2)]:
        print("\n########## " + adi)
        for model, sema, strict, kol in kollar:
            for i in range(3):
                m = [{"role": "system", "content": SYSTEM_PERSONA},
                     {"role": "user", "content": istem}]
                try:
                    ham, sure, tok, fin = cagir(model, m, sema, strict, 900)
                    d = degerlendir(ham)
                    print("  %-10s #%d %5.1fs tok=%3d fin=%-6s json=%s tam4=%s fazla=%s risk=%s time_ok=%s"
                          % (kol, i, sure, tok, fin, d.get("json"), d.get("tam4"),
                             d.get("fazla"), d.get("risk"), d.get("time_mmss")))
                    sonuc["satirlar"].append({"test": adi, "kol": kol, "tekrar": i, "sure": sure,
                                              "tok": tok, "finish": fin, "sonuc": d,
                                              "ham_ilk200": ham[:200]})
                except Exception as e:
                    print("  %-10s #%d HATA %s: %s" % (kol, i, type(e).__name__, str(e)[:160]))
                    sonuc["satirlar"].append({"test": adi, "kol": kol, "tekrar": i,
                                              "hata": "%s: %s" % (type(e).__name__, str(e)[:250])})

    # D3 — KESILME testi: gercek video, max_tokens kisitli
    print("\n########## D3 kesilme (max_tokens=150, gercek video)")
    yol = os.path.join(KOK, "data/eval_holdout/Fighting/Fighting023_x264.mp4")
    b = servis_videosu(yol, max_side=768, crf=28)
    url = "data:video/mp4;base64," + base64.b64encode(b).decode()
    gorev = ("Bu güvenlik kaydını izle ve operatöre rapor üret: summary, events(time MM:SS, event), "
             "risk (Düşük/Orta/Yüksek/Kritik), actions. Yalnızca gördüğüne dayan.")
    for model, sema, strict, kol in [("llm-large", True, True, "L-strict"),
                                     ("llm-large", False, None, "L-semasiz")]:
        for mt in [150, 400]:
            m = [{"role": "system", "content": SYSTEM_PERSONA},
                 {"role": "user", "content": [
                     {"type": "video_url", "video_url": {"url": url}},
                     {"type": "text", "text": gorev + ("" if sema else
                      " Yanıtı YALNIZCA JSON nesnesi olarak ver.")}]}]
            try:
                ham, sure, tok, fin = cagir(model, m, sema, strict, mt)
                d = degerlendir(ham)
                print("  %-10s max_tokens=%3d %5.1fs tok=%3d fin=%-7s json=%s tam4=%s"
                      % (kol, mt, sure, tok, fin, d.get("json"), d.get("tam4")))
                sonuc["satirlar"].append({"test": "D3 kesilme", "kol": kol, "max_tokens": mt,
                                          "sure": sure, "tok": tok, "finish": fin, "sonuc": d,
                                          "ham_son120": ham[-120:]})
            except Exception as e:
                print("  %-10s max_tokens=%3d HATA %s: %s" % (kol, mt, type(e).__name__, str(e)[:160]))
                sonuc["satirlar"].append({"test": "D3 kesilme", "kol": kol, "max_tokens": mt,
                                          "hata": "%s: %s" % (type(e).__name__, str(e)[:250])})

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = os.path.join(KOK, "benchmark", "results", "tekcagri_dusman_%s.json" % ts)
    json.dump(sonuc, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nyazildi: " + p)


if __name__ == "__main__":
    main()
