"""LangGraph ajan grafigi.

GERCEK AKIS (kosullu kenar dahil):

    START -> ingest -> perceive -->[route_after_perceive]--> reexamine --> policy_gate -> reason
                                        \\_______________________________/       |
                                          (belirsiz "Orta" olay yoksa dogrudan)   -> act -> finalize -> END

- ingest     : videoyu zaman damgali kare segmentlerine ayirir (kareler onceden verilmisse
               DECODE-ONCE yolu: yeniden decode etmez)
- perceive   : her segmenti VLM ile analiz eder, olaylari toplar (coklu-adim algi, paralel)
- route_after_perceive : KOSULLU KENAR — belirsiz (Orta) olay varsa `reexamine`, yoksa dogrudan
               `policy_gate`. `settings.adaptive_reexamine` kapaliysa veya bir kez
               yeniden-incelendiyse yine `policy_gate`.
- reexamine  : (kosullu/opsiyonel dugum) belirsiz olaylari odakli sorguyla yeniden degerlendirir
               (RUTIN -> Dusuk, CIDDI -> Yuksek); dongu muhafizi `state["reexamined"]`
- policy_gate: POLITIKA HAKEMLIGI — olaylari operatorun BEYAN ETTIGI kural maddeleriyle anlamsal
               esler ve beyan edilen onem derecesine TEK-YONLU yukseltir. `facility_policy`
               bos ise TAM NO-OP (bkz. dilajan/policy.py).
- reason     : olaylar uzerinden Turkce ozet + risk + aksiyon onerileri uretir
- act        : tespit edilen olaylara gore mock operasyonel fonksiyonlari DINAMIK
               secip cagirir (native tool-calling = ajanin araclari)
- finalize   : AnalysisResult'i birlestirir

HATA TOLERANSI (K6): YEDI dugumun (ingest, perceive, reexamine, policy_gate, reason, act,
finalize) dis govdesi de try/except ile sarilidir; bir adim hata verirse akis cokmek yerine
karar-izine (trace) not dusup guvenli varsayilanla devam eder.

ESZAMANLILIK (K1): `act()` operasyonel cagri kaydini modul-globali yerine BAGLAM-YEREL
kayittan (mock_functions.get_log) + kendi YEREL listesinden toplar. Boylece
`analyze_video(n_samples>1)` grafigi paralel kostururken kosularin kayitlari karismaz.
"""
from __future__ import annotations

import datetime
import difflib
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

from langgraph.graph import END, START, StateGraph

from dilajan import evidence_questions, policy, prompts
from dilajan.agent.state import AgentState
from dilajan.config import settings
from dilajan.llm_client import VLMClient
from dilajan.mock_functions import ALL_TOOLS, TOOL_REGISTRY, get_log, reset_log
from dilajan.schema import (
    Action,
    AnalysisResult,
    Event,
    EventCategory,
    RiskAssessment,
    Severity,
)
from dilajan.utils import extract_json
from dilajan.utils import format_timestamp
from dilajan.video import build_segments, detect_scene_cuts, extract_timestamped_frames

# --- tembel istemci ---
_vlm: Optional[VLMClient] = None


def _get_vlm() -> VLMClient:
    global _vlm
    if _vlm is None:
        _vlm = VLMClient()
    return _vlm


class PolicyAgentState(AgentState, total=False):
    """`AgentState`in politika-hakemligi (policy_gate) kanallariyla genisletilmis hali.

    NEDEN BURADA TANIMLI: LangGraph, bir dugumun DONDURDUGU ama durum semasinda BULUNMAYAN
    anahtarlari SESSIZCE DUSURUR (bu ortamda olculdu) — yani yeni alanlar gercek bir KANAL
    olarak tanimlanmadikca policy_gate -> reason -> act zinciri sessizce kopar. Genisletme
    tamamen ADDITIVE'dir (mevcut alanlarin hicbiri degismez); davranissal olarak alanlari
    `agent/state.py`ye eklemekle ozdestir, yalnizca bu degisiklikte o dosyaya dokunulmamistir.
    """

    #: Politika kaynakli severity yukseltmelerinin kaydi (aciklanabilirlik + sevk cebiri).
    policy_escalations: List[dict]
    #: Yukseltme OLMASAYDI olusacak en yuksek olay-severity ordinali (sevk cebirinin 1. terimi).
    policy_max_intrinsic: int
    #: Risk esigi YALNIZ politika yukseltmesiyle mi asildi (sevk cebirinin 3. terim maskesi).
    risk_from_policy_only: bool
    #: `reexamine`in GORSEL olarak "RUTIN" dedigi olay anahtarlari (politika bunlari aday almaz).
    reexamine_routine: List[str]


def _tools_description() -> str:
    """Mock fonksiyonlari (isim, argumanlar, ozet) ajana sunmak icin metne doker."""
    lines = []
    for t in ALL_TOOLS:
        argnames = ", ".join(t.args.keys())
        summary = (t.description or "").strip().splitlines()[0]
        lines.append(f"- {t.name}({argnames}): {summary}")
    return "\n".join(lines)


# --- yardimcilar ---
_SEV_ORD = {Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4}
_ORD_SEV = {v: k for k, v in _SEV_ORD.items()}
# Tehlike kategorileri (zamansal-süreklilik yükseltmesi yalnız bunlara uygulanır; Anomali/Normal/Diğer hariç)
_DANGER_CATS = {EventCategory.GUVENLIK, EventCategory.KAZA, EventCategory.SAGLIK, EventCategory.YETKISIZ_ERISIM}

# Tehdit anahtar kelimeleri -> asgari severity. Model olayi tespit eder (gucu bu);
# bu katman severity'yi kalibre eder (7B model gercek tehdidi sistematik dusuk puanliyor).
# Yanlis-pozitiften kacinmak icin OZGUL kelimeler ( or. "atesli"/"kirmizi"/"dusuk" tetiklemez).
_THREAT_KEYWORDS = [
    (Severity.KRITIK, [
        "patlama", "patladı", "patlad", "yangın", "yangin", "duman", "alev",
        "silah", "ateş et", "ateş aç", "ates et", "ates ac", "vuruldu", "vurdu",
        "çarpış", "carpis", "çarpma", "carpma", "devril", "yaralı", "yarali",
        "yere yığıl", "yere yigil", "kanama", "bayıl", "bayil", "ölü", "olu",
        # dusme / saglik acil durumu (sartname: "yerde hareketsiz kisi")
        # NOT: bare "hareketsiz" cikarildi (normal "isci hareketsiz kalmis" -> yanlis Kritik);
        # zemin baglami gerektiriliyor.
        "yerde yat", "yere yat", "yerde hareketsiz", "hareketsiz yat", "hareketsiz yer",
        "yığıld", "yigild", "yığılm", "yigilm",
        "baygın", "baygin", "bilinçsiz", "bilincsiz", "kıpırdam", "kipirdam",
        "yere seril", "yere kapan",
    ]),
    (Severity.YUKSEK, [
        "kavga", "dövüş", "dovus", "darp", "saldır", "saldir", "şiddet", "siddet",
        "yetkisiz", "hırsız", "hirsiz", "soygun", "tahrip", "vandal", "zorla gir",
        "çatış", "catis", "yere düş", "yere dus", "düştü", "dustu", "itiş", "itis",
        # yerde yatan kisi (acil olmasa da operatorun dikkatini gerektirir)
        "yatmış", "yatmis", "yatıyor", "yatiyor", "yerde yatan", "yere uzan",
    ]),
]


# G11: severity tabani MODEL-ONCELIKLIDIR (Qwen3-VL severity'yi semantik atar; dil-bagimsiz).
# Asagidaki kelimeler yalniz TEK-YONLU bir guvenlik TABANI'dir (model gercek tehdidi dusuk
# puanlarsa devreye girer). Turkce-disi (Ingilizce/OOD) tarifte de kor kalmamak icin Ingilizce
# esdegerler KELIME-SINIRI ile eklendi (Turkce metinle cakismaz; yalniz yukseltir, asla dusurmez).
_THREAT_EN = [
    (Severity.KRITIK, ["fire", "smoke", "explosion", "explosive", "blast", "gunshot", "gunfire",
                       "weapon", "rifle", "pistol", "firearm", "collision", "crash", "overturn",
                       "rollover", "injured", "unconscious", "bleeding", "wounded", "collapsed", "dead"]),
    (Severity.YUKSEK, ["fight", "fighting", "assault", "intruder", "unauthorized", "trespass",
                       "theft", "burglary", "robbery", "vandalism", "fallen", "fall"]),
]
_THREAT_EN_RE = [(sev, re.compile(r"\b(" + "|".join(ws) + r")\b")) for sev, ws in _THREAT_EN]


# Nesne-vs-kisi: dusmus/yerde duran NESNE kritik degil; dusme severity'sini yalniz KISI baglaminda yukselt.
_OBJ_RE = re.compile(r"nesne|alet|malzeme|eşya|esya|koli|kutu|parça|parca|ekipman|tekerlek|cisim|paket")
_PERSON_RE = re.compile(r"kişi|kisi|insan|işçi|isci|adam|kadın|kadin|çocuk|cocuk|personel|operatör|operator|biri|yaya|şahıs|sahis|birey|genç|genc")
_FALL_KW = {
    "yere yığıl", "yere yigil", "yerde yat", "yere yat", "yerde hareketsiz", "hareketsiz yat",
    "hareketsiz yer", "yığıld", "yigild", "yığılm", "yigilm", "yere seril", "yere kapan",
    "yere düş", "yere dus", "düştü", "dustu", "yatmış", "yatmis", "yatıyor", "yatiyor",
    "yerde yatan", "yere uzan",
}


# F1: kisi-dusmesi/hareketsizlik olayi mi? (poz-tabanli dogrulama yalniz bunlara uygulanir)
_FALL_EVENT_RE = re.compile(r"düş|dus|zemine|yere|yerde|yığıl|yigil|çök|hareketsiz|baygın|baygin|bayıl|bayil")


def _is_person_fall_event(text: str) -> bool:
    t = (text or "").lower()
    return bool(_PERSON_RE.search(t)) and bool(_FALL_EVENT_RE.search(t))


def _calibrate_severity(text: str, model_sev: Severity) -> Severity:
    """Olay metnindeki tehdit kelimelerine gore TEK-YONLU severity tabani uygular (TR + EN).
    NESNE (kisi degil) icin dusme/yere kelimeleri severity'yi YUKSELTMEZ (dusmus nesne kritik degil);
    yangin/silah gibi diger tehditlerde nesne olsa bile yukseltir."""
    t = (text or "").lower()
    obj_not_person = bool(_OBJ_RE.search(t)) and not bool(_PERSON_RE.search(t))
    floor = model_sev
    for sev, kws in _THREAT_KEYWORDS:  # once Kritik katmani (Turkce alt-dizgi)
        matched = [k for k in kws if k in t]
        if matched:
            # NESNE + eslesenlerin TUMU dusme/yerde kelimesiyse: yukseltme yapma, sonraki gruba bak
            if obj_not_person and all(k in _FALL_KW for k in matched):
                continue
            if _SEV_ORD[sev] > _SEV_ORD[floor]:
                floor = sev
            break
    for sev, rx in _THREAT_EN_RE:  # Ingilizce/OOD esdeger (kelime-siniri)
        if rx.search(t):
            if _SEV_ORD[sev] > _SEV_ORD[floor]:
                floor = sev
            break
    return floor


def _to_severity(value: str) -> Severity:
    if not value:
        return Severity.ORTA
    v = value.strip().lower()
    for s in Severity:
        if s.value.lower() == v or s.name.lower() == v:
            return s
    if "krit" in v:
        return Severity.KRITIK
    if "yük" in v or "yuk" in v or "high" in v:
        return Severity.YUKSEK
    if "düş" in v or "dus" in v or "low" in v:
        return Severity.DUSUK
    return Severity.ORTA


def _to_category(value: str) -> EventCategory:
    if not value:
        return EventCategory.DIGER
    for c in EventCategory:
        if c.value.lower() == value.strip().lower():
            return c
    return EventCategory.DIGER


# G12: dil-safligi — Turkce-disi script (Cince/Japonca/Korece/Kiril/Arapca/Tayca) sizintisini yakala.
# (Turkce ç/ğ/ı/ö/ş/ü Latin'dir; yalniz YABANCI script tetikler.)
_FOREIGN = re.compile(r"[一-鿿぀-ヿ가-힯Ѐ-ӿ؀-ۿ฀-๿]")


def _has_foreign(text: str) -> bool:
    return bool(_FOREIGN.search(text or ""))


def _purify(vlm: VLMClient, text: str) -> str:
    """Metinde Turkce-disi karakter varsa anlamini koruyarak SADECE Turkce'ye yeniden yazdirir.
    Temiz metinde EK CAGRI YAPMAZ (sifir maliyet); yalniz sizinti varsa tek duzeltme cagrisi."""
    if not text or not _has_foreign(text):
        return text
    try:
        fixed = vlm.chat(
            [{"role": "system", "content": prompts.SYSTEM_PERSONA},
             {"role": "user", "content": "Aşağıdaki metni anlamını koruyarak SADECE düzgün Türkçe olarak "
              "yeniden yaz; Türkçe dışı hiçbir karakter veya kelime (Çince/İngilizce vb.) kullanma. "
              "Yalnızca düzeltilmiş metni döndür:\n\n" + text}],
            temperature=0.0, max_tokens=400,
        ).strip()
        return fixed if (fixed and not _has_foreign(fixed)) else text
    except Exception:
        return text


def _events_block(events: List[Event]) -> str:
    if not events:
        return "(Önemli bir olay tespit edilmedi.)"
    return "\n".join(
        f"- [{e.time}{('–' + e.end_time) if e.end_time else ''}] {e.event} "
        f"(önem: {e.severity.value}, tür: {e.category.value}"
        + (f", konum: {e.region}" if e.region else "") + ")"
        for e in events
    )


def _scene_index(time_str: str, cuts: List[float]) -> int:
    """Bir olay zaman-damgasinin hangi sahne/bolume dustugunu dondurur (kesimlere gore)."""
    t = _secs(time_str)
    idx = 0
    for c in cuts:
        if t >= c:
            idx += 1
        else:
            break
    return idx


def _events_block_scened(events: List[Event], cuts: List[float]) -> str:
    """Olaylari KOPUK bolumlere (sahne-kesimleri) gore gruplayarak yazar; tek bolumde normal blok."""
    if not cuts:
        return _events_block(events)
    groups: dict = {}
    for e in events:
        groups.setdefault(_scene_index(e.time, cuts), []).append(e)
    parts = []
    for i in range(len(cuts) + 1):
        evs = groups.get(i, [])
        parts.append(f"[Bölüm {i + 1}]\n" + _events_block(evs))
    return "\n".join(parts)


# --- dugumler ---
def _ingest_output(frames, info, trace: list) -> dict:
    """Cikarilmis karelerden segment + sahne-kesimi cikti sozlugu kurar (ortak yol)."""
    segments = build_segments(frames)
    cuts = detect_scene_cuts(frames) if settings.scene_cut_threshold > 0 else []
    if not segments:
        trace.append("ingest: video okundu ama kare cikarilamadi (boş/bozuk olabilir)")
    else:
        note = f"ingest: {info.duration_str} video, {len(segments)} segment, {info.sampled_frames} kare"
        if cuts:
            note += f"; {len(cuts)+1} kopuk bölüm (kesim: {', '.join(format_timestamp(c) for c in cuts)})"
        trace.append(note)
    return {"segments": segments, "video_info": info, "scene_cuts": cuts, "trace": trace}


def ingest(state: AgentState) -> dict:
    trace = state.get("trace", [])
    # DECODE-ONCE: kareler onceden cikarilmissa (canli akis) videoyu yeniden decode etme
    pf = state.get("prebuilt_frames")
    if pf is not None:
        info = state.get("prebuilt_info")
        try:
            return _ingest_output(pf, info, trace)
        except Exception as ex:
            trace.append(f"ingest: onceden-cikarilmis kare islenemedi: {ex}")
            return {"segments": [], "video_info": info, "trace": trace}
    try:
        frames, info = extract_timestamped_frames(state["video_path"])
        return _ingest_output(frames, info, trace)
    except Exception as ex:  # okunamayan/bozuk video -> toleransli devam
        trace.append(f"ingest: video okunamadi: {ex}")
        return {"segments": [], "video_info": None, "trace": trace}


_VERIFY_PROMPT = (
    "Bu güvenlik kamerası karelerini dikkatle incele. İddia edilen YÜKSEK ÖNEMLİ olay: \"{event}\".\n"
    "Bu, karelerde AÇIKÇA görünen ve GERÇEKTEN ciddi/acil müdahale gerektiren bir güvenlik olayı mı? "
    "Yalnızca EVET veya HAYIR ile başla, ardından tek cümle gerekçe.\n"
    "Şu durumlarda HAYIR de: olay belirsiz veya zayıf bir ihtimalse; yalnızca olağan/günlük aktiviteyse; "
    "ya da ciddi gibi etiketlenmiş ama aslında ÖNEMSİZ ise — ör. yere düşmüş bir NESNE/alet/malzeme "
    "(kişi değil), birinin yürümesi/geçmesi, rutin çalışma/taşıma, ya da birinin YATAĞA/koltuğa/sandalyeye "
    "uzanmasi/oturmasi (bu normaldir, düşme değildir). "
    "Yalnızca yangın/duman/patlama, silah, ciddi kaza/çarpışma veya ZEMİNE düşmüş/yere çökmüş/yerde "
    "hareketsiz bir KİŞİ gibi gerçek ve acil tehlikelerde EVET de."
)


def _verify_event(vlm: VLMClient, frames, event_text: str) -> bool:
    """Yuksek-severity bir olayi segment kareleriyle teyit eder (deduce-then-verify).
    Dogrulanmazsa False (toleransli: hata olursa True dondurup olayi korur)."""
    try:
        ans = vlm.analyze_frames(frames, _VERIFY_PROMPT.format(event=event_text),
                                 temperature=0.0, max_tokens=60)
        a = (ans or "").strip().lower()
        return not (a.startswith("hayır") or a.startswith("hayir") or a.startswith("no"))
    except Exception:
        return True


_VERIFY_BATCH_PROMPT = (
    "Bu güvenlik kamerası karelerini dikkatle incele. Aşağıda iddia edilen {n} YÜKSEK ÖNEMLİ olay var:\n{listing}\n\n"
    "Her olay için: karelerde AÇIKÇA görünen ve GERÇEKTEN ciddi/acil müdahale gerektiren bir güvenlik olayı mı? "
    "Şu durumlarda 'gercek' false olsun: belirsiz/zayıf ihtimal; yalnızca olağan/günlük aktivite; ya da ciddi "
    "etiketli ama ÖNEMSİZ (yere düşmüş NESNE/alet, yürüme/geçme, rutin çalışma/taşıma, yatağa/koltuğa uzanma/oturma). "
    "Yalnızca yangın/duman/patlama, silah, ciddi kaza/çarpışma veya ZEMİNE düşmüş/yerde hareketsiz bir KİŞİ gibi "
    "gerçek+acil tehlikelerde 'gercek' true olsun. SADECE JSON: {{\"sonuc\":[{{\"no\":1,\"gercek\":true}}, ...]}}"
)


def _verify_events_batch(vlm: VLMClient, frames, texts: List[str]) -> List[bool]:
    """N yuksek-sev olayi TEK cagrida teyit eder (deduce-then-verify, batch). Donus: list[bool]
    (True=gercek/koru, False=dusur). FAIL-OPEN: hata/parse-fail -> hepsi True (olaylari korur)."""
    try:
        listing = "\n".join(f"{i + 1}) {t}" for i, t in enumerate(texts))
        raw = vlm.analyze_frames(frames, _VERIFY_BATCH_PROMPT.format(n=len(texts), listing=listing),
                                 temperature=0.0, max_tokens=240)
        data = extract_json(raw)
        res = {}
        for r in data.get("sonuc", []):
            try:
                res[int(r.get("no"))] = bool(r.get("gercek", True))
            except Exception:
                continue
        return [res.get(i + 1, True) for i in range(len(texts))]  # eksik = koru (fail-safe)
    except Exception:
        return [True] * len(texts)


def _normalize_time(raw, fallback: str) -> str:
    """Olay zaman damgasini her zaman gecerli MM:SS'e zorlar (modele guvenme -> JSON %100 uyum)."""
    m = re.search(r"(\d{1,2}):(\d{2})", str(raw or ""))
    if m and int(m.group(2)) < 60:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
    return fallback


def _bbox_to_region(bbox) -> Optional[str]:
    """0-1000 normalize bbox merkezini 3x3 Türkçe ızgara bölgesine eşler."""
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox[:4]]
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        xr = "sol" if cx < 333 else ("sağ" if cx > 667 else None)
        yr = "üst" if cy < 333 else ("alt" if cy > 667 else None)
        if xr and yr:
            return f"{yr} {xr}"
        return yr or xr or "merkez"
    except Exception:
        return None


def _ground_event(vlm: VLMClient, frames, event_text: str):
    """Olayin karedeki konumunu (bbox_2d, 0-1000) + bölgesini çıkarır (Qwen3-VL native grounding).
    (bbox, region) döner; bulunamazsa (None, None) — toleranslı."""
    try:
        mid = frames[len(frames) // 2: len(frames) // 2 + 1]  # tek temsili kare
        q = (f"Bu güvenlik kamerası karesinde şu olay nerede konumlanmış: \"{event_text}\"? "
             'Sınırlayıcı kutuyu JSON ver: [{"bbox_2d":[x1,y1,x2,y2],"label":"..."}]. Sadece JSON.')
        raw = vlm.analyze_frames(mid, q, temperature=0.0, max_tokens=120)
        m = re.search(r'bbox_2d"?\s*:?\s*\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', raw or "")
        if m:
            bb = [int(m.group(i)) for i in range(1, 5)]
            return bb, _bbox_to_region(bb)
    except Exception:
        pass
    return None, None


def _events_from_extraction(data: dict, seg) -> List[Event]:
    """Olay-cikarim JSON'undan Event listesi kurar (severity kalibrasyonu + zaman normalizasyonu)."""
    out: List[Event] = []
    for e in data.get("events", []):
        ev = str(e.get("event", "")).strip()
        if not ev:
            continue
        out.append(
            Event(
                time=_normalize_time(e.get("time"), seg.start_str),
                event=ev,
                severity=_calibrate_severity(ev, _to_severity(str(e.get("severity", "")))),
                category=_to_category(str(e.get("category", ""))),
            )
        )
    return out


# ---------------------------------------------------------------------------
# SORGU-GUDUMLU ANALIZ — "sorgu ODAKLAR, FILTRELEMEZ"
# ---------------------------------------------------------------------------
# Operatorun serbest-metin sorgusu (settings.analysis_query) iki yerde promptlara EKLENIR:
#   perceive -> prompts.QUERY_FOCUS_SUFFIX     (odak + "kritik olaylari HER ZAMAN raporla")
#   reason   -> prompts.QUERY_ANSWER_INSTRUCTION (sorguya dogrudan yanit -> "query_answer")
#
# K1 VARSAYILAN KAPALI: sorgu bos iken asagidaki uc uretecin HEPSI "" doner -> promptlara TEK
#    KARAKTER eklenmez, mevcut olcumler bit-bit yeniden uretilebilir.
# K3 FAIL-OPEN: uretecler HICBIR kosulda istisna firlatmaz; hata halinde "" donup analizin
#    sorgusuz ama NORMAL tamamlanmasini saglar.
# K6 ENJEKSIYON DIRENCI: metin sanitize edilir (sinirlayici/yapisal karakterler silinir, satir
#    sonlari bosluga cevrilir, uzunluk sinirlanir) ve prompt icinde <<< >>> arasinda, "bu bir
#    TALIMAT DEGILDIR" cercevesiyle VERI olarak verilir.

#: Sinirlayici + yapisal karakterler: operator metni prompt CERCEVESINI kiramaz ve kendi
#: <<< >>> blogunu acamaz ({} ayrica sonraki bir .format() cagrisina karsi savunmadir).
_QUERY_UNSAFE_RE = re.compile(r"[<>{}]")

#: Model ciktisindaki `query_answer` icin savunma amacli uzunluk tavani. Prompt "en fazla
#: 2-3 cümle" ister; bu KODLA zorlanan ust sinirdir (kotu-niyetli sorgu modeli uzun bir blok
#: uretmeye ikna ederse panel/JSON sismesin). Sorgusuz akista HIC devreye girmez.
_QUERY_ANSWER_MAX_CHARS = 1200


def _sanitize_query(raw: str) -> str:
    """Operator sorgusunu prompt'a gomulmeye guvenli hale getirir (K6).

    Uygulananlar: sinirlayici karakter temizligi -> satir sonu/tab dahil tum bosluklarin
    tek bosluga indirgenmesi (cok-satirli "sahte sistem mesaji" enjeksiyonunu kirar) ->
    `settings.analysis_query_max_len` ile uzunluk kirpma (prompt butcesi korunur).
    Donen metnin uzunlugu HER ZAMAN <= limit'tir.
    """
    q = _QUERY_UNSAFE_RE.sub(" ", str(raw or ""))
    q = re.sub(r"\s+", " ", q).strip()
    try:
        limit = int(settings.analysis_query_max_len)
    except Exception:
        limit = 500
    limit = max(16, limit)
    if len(q) > limit:
        q = q[: limit - 1].rstrip() + "…"
    return q


def _active_query() -> str:
    """Etkin (sanitize edilmis) operator sorgusu; sorgu yoksa veya hata olursa "" (FAIL-OPEN)."""
    try:
        return _sanitize_query(getattr(settings, "analysis_query", "") or "")
    except Exception:
        return ""


def _query_focus_block() -> str:
    """perceive promptuna eklenecek ODAK bloku — sorgu yoksa/hata olursa BOS metin (K1/K3)."""
    q = _active_query()
    if not q:
        return ""
    try:
        return prompts.QUERY_FOCUS_SUFFIX.format(query=q)
    except Exception:
        return ""


def _query_answer_block() -> str:
    """reason promptuna eklenecek SORGU-YANITI bloku — sorgu yoksa/hata olursa BOS (K1/K3)."""
    q = _active_query()
    if not q:
        return ""
    try:
        return prompts.QUERY_ANSWER_INSTRUCTION.format(query=q)
    except Exception:
        return ""


def _query_trace_line(prefix: str, suffix: str) -> Optional[str]:
    """K4 izlenebilirlik: sorgu kullanildiginda karar-izine yazilacak NET satir (yoksa None)."""
    q = _active_query()
    if not q:
        return None
    shown = q if len(q) <= 60 else q[:60] + "…"
    return f'{prefix}"{shown}"{suffix}'


# ---------------------------------------------------------------------------
# KANIT SORULARI (ASK-HINT, arXiv 2510.02155) — "kanit -> olay ADI"
# ---------------------------------------------------------------------------
# Akis (yalniz `settings.evidence_questions` ACIK ve segmentte >=1 olay VARSA):
#   betimleme -> olay cikarimi -> [N ikili kanit sorusu] -> birlestirme -> [1 adlandirma cagrisi]
#
# UC YAPISAL GARANTI (hepsi tests/test_evidence_questions.py'de assert edilir):
#
#  G1  VARSAYILAN KAPALI (K2): bayrak kapaliyken `_kanit_adlandirma` ILK SATIRDA doner —
#      prompt metni ve VLM cagri sayisi BIREBIR eski halidir.
#
#  G2  YANLIS-POZITIF KAPISI ACILMAZ (gorevin "KRITIK RISK" maddesi): sorular YALNIZCA
#      olay listesi BOS DEGILSE sorulur. Normal klipte olay yoktur -> soru sorulmaz ->
#      ipucu uretilmez -> hicbir alarm/severity/sevk terimi degismez. Yani olculen
#      dar-FP %0 ve sevk-FP %0 profili bir prompt sozune degil, BU KOSULA dayanir.
#
#  G3  "KANIT -> AD, KANIT -/-> ALARM": adlandirma adimi olaylari `model_copy(update=
#      {"event": ..., "evidence_prev": ...})` ile tasir. severity / category / time /
#      end_time / bbox / region alanlarina TEK BIR KOD YOLU dokunmaz. Ayrica bu adim ALGI
#      ZINCIRININ SONUNDA, SEGMENT ICINDE severity'yi degistiren TUM adimlardan (severity
#      kalibrasyonu, verify_events, semantic_plausibility, verify_pose_falls) SONRA calisir.
#
#  G4  ALARM MUHAFIZI (adversaryel denetim sonrasi EKLENDI — G3 tek basina YETMIYORDU):
#      `perceive` DISINDA da metne bakip alarm yukselten iki adim var ve ikisi de bu adimdan
#      SONRA calisir. Denetimde OLCULDU (sahte VLM, tek soruya "Evet"):
#          severity Orta -> YUKSEK · risk Orta -> Yuksek · sevk [] -> ['guvenlik_ekibi_uyar']
#      Kapatilan iki yol:
#        (a) `reexamine` olay METNINI modele sorup Orta->Yuksek yukseltir. ARTIK hakeme
#            `ev.evidence_prev or ev.event` gonderilir -> istem metni ozellik KAPALIYKENKI
#            ile BYTE-ESIT, dolayisiyla severity karari da AYNI.
#        (b) `reason` olay metnini okuyup RISK seviyesini yukseltebilir; risk >= Yuksek sevk
#            kapisinin 3. terimidir. ARTIK `evidence_renamed` bayragi bu terimi MASKELER
#            (risk_recall_bias ile ayni desen) -> risk operatore FLAG olur, SEVK ACMAZ.
#      KALAN (kapatilmayan, bilerek): operatore GOSTERILEN risk seviyesi yeniden adlandirilmis
#      metin yuzunden yukselebilir. Bu bilincli bir taviz — ozetin olay adiyla TUTARLI olmasi
#      icin `reason` yeni adi GORMELIDIR. Bu artis A/B betiginin `fp_dar` olcutuyle
#      OLCULUR ve artis varsa kol REDDEDILIR (scripts/run_evidence_ab.py).
#
# G2'NIN SINIRI (durustluk notu — OLCULDU): "normal klipte olay yoktur" varsayimi
# eval_holdout'ta 8 normal klipin 3'unde YANLIS (olay uretiliyor, biri Orta severity).
# Yani FP guvenligi G2'ye DEGIL, G4'e dayanir.

#: "EVET/HAYIR/BİLİNMİYOR" icin fazlasiyla yeterli (gorev sarti: 8-16).
_KANIT_MAX_TOKENS = 12
#: Sorular ES ZAMANLI sorulur — vLLM eszamanli istekleri batch'ler; K4 gecikme tavani icin
#: N ardisik cagri yerine ~1 cagri suresi. `pool.map` SIRAYI KORUR (yanit-soru eslesmesi guvenli).
_KANIT_MAX_WORKERS = 4
#: Adlandirma promptuna giren betimleme uzunluk tavani (prompt butcesi).
_KANIT_DESC_MAX = 1500


def _kanit_yanitla(vlm: VLMClient, frames, soru) -> str:
    """Tek IKILI kanit sorusunu sorar ve etiketi dondurur.
    FAIL-OPEN: cagri/parse hatasi -> BILINMIYOR (o soru hicbir yone kanit saymaz)."""
    try:
        ham = vlm.analyze_frames(
            frames, prompts.EVIDENCE_QUESTION_INSTRUCTION.format(soru=soru.metin),
            temperature=0.0, max_tokens=_KANIT_MAX_TOKENS)
    except Exception:
        return evidence_questions.BILINMIYOR
    return evidence_questions.yanit_ayristir(ham)


def _kanit_ile_adlandir(vlm: VLMClient, seg, desc: Optional[str], events: List[Event],
                        ozet, sorular) -> Tuple[List[Event], str]:
    """Kanit ozetine gore olaylarin YALNIZCA `event` metnini yeniler (GORUNTUSUZ tek cagri).

    G3: donen olaylar `model_copy(update={"event": ...})` ile uretilir -> severity/category/
    zaman/bbox alanlari BIREBIR korunur. Onerilen ad `ad_kabul_edilebilir_mi` vetosundan
    gecmezse (bos/uzun/yabanci karakter ya da "Hayır" denen kanitla celiskili) ESKI AD KALIR.
    """
    instr = prompts.EVIDENCE_NAMING_INSTRUCTION.format(
        start=seg.start_str, end=seg.end_str,
        description=(str(desc or "").strip() or "(açıklama üretilemedi)")[:_KANIT_DESC_MAX],
        kanit_block=evidence_questions.kanit_blok(ozet, sorular),
        ipucu=ozet.ipucu,
        olay_block="\n".join(f"{i + 1}) {e.event}" for i, e in enumerate(events)),
    )
    raw = vlm.chat(
        [{"role": "system", "content": prompts.SYSTEM_PERSONA},
         {"role": "user", "content": instr}],
        temperature=0.0, max_tokens=320,
    )
    onerilen: Dict[int, str] = {}
    for kayit in (extract_json(raw) or {}).get("adlar", []):
        try:
            onerilen[int(kayit.get("no"))] = str(kayit.get("ad", "")).strip()
        except Exception:  # tek bozuk kayit digerlerini dusurmesin
            continue
    out: List[Event] = []
    degisen = red = 0
    redler: List[str] = []
    for i, ev in enumerate(events):
        ad = onerilen.get(i + 1, "")
        if ad and ad != ev.event:
            uygun, sebep = evidence_questions.ad_kabul_edilebilir_mi(ad, ozet)
            if uygun:
                # G3: severity/kategori/zaman/bbox alanlarina DOKUNULMAZ. `evidence_prev`
                # ALARM MUHAFIZIDIR: yeniden adlandirmadan onceki metni saklar ki
                # `reexamine` gibi METNE BAKIP severity yukseltebilen adimlar kararlarini
                # ozellik KAPALIYKENKI metinle versin. `evidence_prev` SEMA ALANI DEGILDIR
                # (policy_ref/policy_prev ile ayni desen) -> model_dump()/sozlesme DEGISMEZ.
                ev = ev.model_copy(update={
                    "event": ad,
                    "evidence_prev": getattr(ev, "evidence_prev", None) or ev.event})
                degisen += 1
            else:
                red += 1
                redler.append(sebep)
        out.append(ev)
    not_ = (f"kanıt-adlandırma: {degisen}/{len(events)} olay adı kanıtla güncellendi"
            + (f", {red} öneri reddedildi ({'; '.join(redler[:2])})" if red else "")
            + " — önem derecesi, kategori ve risk DEĞİŞMEDİ")
    return out, not_


def _kanit_adlandirma(vlm: VLMClient, seg, desc: Optional[str],
                      events: List[Event]) -> Tuple[List[Event], List[str]]:
    """ASK-HINT ana akisi: ikili kanit sorulari -> kategori ipucu -> olay ADI yenileme.

    K2/G1: ozellik kapaliysa VEYA segmentte olay yoksa TEK CAGRI bile yapilmaz.
    K3   : her ariza modunda (soru cagrisi patlar, JSON bozuk, sablon hatali) olaylar
           DEGISMEDEN doner ve analiz normal surer.
    """
    if not settings.evidence_questions or not events:
        return events, []  # <-- G1 + G2: erken donus; olcumler ve FP profili korunur
    # N-KEZ ALGI (event_consistency_n>1) KAPSAM DISI — iki gerekce (denetimde OLCULDU):
    #  (1) DOGRULUK: cogunluk-oyu kumeleme olay METNINI (_dedup_words) kullanir. Kosular
    #      arasinda kanit yanitlari farkli cikarsa AYNI olay farkli adlarla gelir, ayni
    #      kumeye DUSMEZ ve esigin altinda kalip ELENIR -> recall KAYBI.
    #  (2) GECIKME (K4): ek cagri N ile carpilir; olculdu n=3'te 6 -> 18 cagri (3.0x) ve
    #      adlandirmayla birlikte 3x tavani ASAR.
    # Ikisi de OPT-IN'dir; varsayilan n=1'de bu satir hicbir sey yapmaz. Bilgilendirme
    # `_segment_consistent_events`in kendi notuna yazilir (bu fonksiyonun notu orada dusuyor).
    if settings.event_consistency_n > 1:
        return events, []
    notes: List[str] = []
    try:
        sorular = evidence_questions.soru_seti(settings.evidence_question_set)
        if not sorular:
            return events, []
        workers = max(1, min(len(sorular), _KANIT_MAX_WORKERS))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            yanitlar = list(pool.map(lambda s: _kanit_yanitla(vlm, seg.frames, s), sorular))
        ozet = evidence_questions.birlestir(sorular, yanitlar)
        notes.append(f"perceive: segment {seg.index} {ozet.ozet_satiri}")
        if not ozet.ipucu:  # kanit yok / cakisma -> ek cagri YAPILMAZ, olaylar aynen kalir
            return events, notes
        events, ad_notu = _kanit_ile_adlandir(vlm, seg, desc, events, ozet, sorular)
        notes.append(f"perceive: segment {seg.index} {ad_notu}")
    except Exception as ex:  # FAIL-OPEN (K3)
        notes.append(f"perceive: segment {seg.index} kanıt soruları atlandı "
                     f"(toleranslı devam, olaylar değiştirilmedi): {ex}")
    return events, notes


def _perceive_single_pass(vlm: VLMClient, seg) -> Tuple[List[Event], Optional[str]]:
    """Hizli mod: segment basina TEK VLM cagrisi (describe+extract birlesik).
    verify/grounding YOK -> dusuk gecikme. (olaylar, hata_notu) doner."""
    try:
        instr = prompts.SEGMENT_FAST_INSTRUCTION.format(start=seg.start_str, end=seg.end_str)
        if settings.facility_rules:
            instr += (f"\n\nBu tesisin güvenlik kuralları: {settings.facility_rules}. "
                      "Bu kurallara açıkça aykırı durumları da sapma/olay olarak raporla.")
        if settings.motion_saliency_cue:
            instr += _motion_cue(seg)
        # Sorgu-gudumlu odak — bkz. _analyze_one_segment'teki ayni satirin gerekcesi (EN SONA).
        instr += _query_focus_block()
        raw = vlm.analyze_frames(seg.frames, instr, temperature=0.2, max_tokens=400,
                                 repetition_penalty=settings.perceive_repetition_penalty)
        return _events_from_extraction(extract_json(raw), seg), None
    except Exception as ex:
        return [], f"perceive(fast): segment {seg.index} hatasi: {ex}"


def _motion_cue(seg) -> str:
    """Segment karelerinde en belirgin ANI gorsel degisim (hareket) anini bulur; BELIRGIN, IZOLE bir
    zirve varsa perceive'e YUMUSAK dikkat ipucu doner (motion-saliency / video-anomali literaturunde
    hareket-belirginligi). IDDIA DEGIL — model yine kendi karar verir, "emin degilsen normal de" denir.
    Zirve yoksa (uniform/dusuk hareket) bos doner -> normal videoda FP riski yok.

    Gerekce: gecici olay (carpisma/devrilme onset) ON PLANDAKI buyuk nesnenin golgesinde kalip
    kacirilabiliyor; hareket zirvesi modelin dikkatini DOGRU ana yonlendirir."""
    try:
        import io as _io
        import numpy as np
        from PIL import Image
        frames = seg.frames
        if len(frames) < 3:
            return ""
        grays = [np.asarray(Image.open(_io.BytesIO(j)).convert("L").resize((64, 64)), dtype=np.float32)
                 for _, j in frames]
        diffs = [float(np.abs(grays[i] - grays[i - 1]).mean()) for i in range(1, len(grays))]
        if not diffs:
            return ""
        mean = sum(diffs) / len(diffs)
        peak_i = max(range(len(diffs)), key=lambda i: diffs[i])
        peak = diffs[peak_i]
        # Belirgin + izole zirve sarti: hem mutlak (>6) hem goreli (>2x ortalama). Aksi halde sessiz.
        if mean < 1e-6 or peak < 6.0 or peak / mean < 2.0:
            return ""
        ts = frames[peak_i + 1][0]  # zirve karesinin zaman damgasi (MM:SS)
        return (f"\n\nHareket-analizi (yardımcı ipucu): en belirgin ANİ görsel değişim ~{ts} civarında. "
                "O kısa ana ÖZELLİKLE dikkat et — ani çarpışma, devrilme, düşme veya kaza olabilir. "
                "Yalnızca gerçekten gördüğünü raporla; emin değilsen olağan/normal olarak değerlendir.")
    except Exception:
        return ""


def _analyze_one_segment(vlm: VLMClient, seg) -> Tuple[List[Event], Optional[str]]:
    """Tek segment icin iki asamali algi: serbest tarif -> olay cikarimi.
    (olaylar, hata_notu) doner; hata olursa olaylar boş + not döner (toleransli).
    NOT: `hata_notu` birden cok satir icerebilir (karar-izine tek girdi olarak yazilir)."""
    if settings.single_pass_perceive:
        evs, note = _perceive_single_pass(vlm, seg)
        # ASK-HINT hizli modda UYGULANMAZ: tek-gecisli algida ayri bir betimleme metni yoktur
        # ve fast_mode'un tek amaci gecikmedir (K4). Sessiz kalmamak icin karar-izine yazilir.
        if settings.evidence_questions:
            note = "\n".join(filter(None, [
                note, f"perceive: segment {seg.index} kanıt soruları HIZLI MODDA uygulanmadı "
                      "(tek-geçişli algı)"]))
        return evs, note
    try:
        instr = prompts.SEGMENT_DESCRIBE_INSTRUCTION.format(start=seg.start_str, end=seg.end_str)
        if settings.facility_rules:
            instr += (f"\n\nBu tesisin güvenlik kuralları: {settings.facility_rules}. "
                      "Bu kurallara açıkça aykırı durumları da sapma/olay olarak raporla.")
        if settings.use_detector:
            from dilajan import detector
            evidence = detector.detect_segment(seg.frames)
            if evidence:
                instr += (f"\n\nYardimci kanit — {evidence}. Bu nesne bilgisini betimlemende "
                          "dikkate al (ama yalnizca gerçekten gördüğünü raporla).")
        if settings.threat_interpretation:
            instr += prompts.THREAT_LENS_SUFFIX
        if settings.motion_saliency_cue:
            instr += _motion_cue(seg)
        # SORGU-GUDUMLU ODAK — bilerek EN SONA eklenir (facility_rules/detector/threat-lens/
        # motion-cue katmanlarinin HICBIRINE dokunmadan):
        #   (1) SAF EK: bos sorguda prompt bit-bit eskisiyle ayni, sorguluyken ise metin
        #       "eski_prompt + blok" olur -> K1 regresyonu byte-duzeyinde kanitlanabilir.
        #   (2) RECENCY: modelin okudugu SON talimat "sorguyla ILGISIZ olsa bile yangin/silah/
        #       dusmus kisi gibi KRITIK durumlari HER ZAMAN raporla" olur — dar sorgunun
        #       kritik olayi bastirma riskine karsi en guclu konum.
        instr += _query_focus_block()
        desc = vlm.analyze_frames(
            seg.frames, instr, temperature=0.2, max_tokens=400,
            repetition_penalty=settings.perceive_repetition_penalty,
            as_video=(settings.video_pruning_rate > 0),  # EVS video-path (yalniz perceive-describe)
        )
        ext = vlm.chat(
            [
                {"role": "system", "content": prompts.SYSTEM_PERSONA},
                {"role": "user", "content": prompts.EVENT_EXTRACTION_INSTRUCTION.format(
                    description=desc, start=seg.start_str, end=seg.end_str)},
            ],
            temperature=0.1, max_tokens=400,
        )
        out: List[Event] = _events_from_extraction(extract_json(ext), seg)
        # Oz-dogrulama: yuksek-severity olaylari odakli sorguyla teyit et (FP azaltir, recall korur).
        if settings.verify_events and out:
            hi = [i for i, ev in enumerate(out) if _SEV_ORD[ev.severity] >= _SEV_ORD[Severity.YUKSEK]]
            # PERF: >=2 yuksek-sev olay -> TEK batch cagri (N->1); aksi halde per-event (degisiklik yok). Recall-safe.
            if settings.batch_verify and len(hi) >= 2:
                keep = _verify_events_batch(vlm, seg.frames, [out[i].event for i in hi])
            else:
                keep = [_verify_event(vlm, seg.frames, out[i].event) for i in hi]
            for k, i in enumerate(hi):
                if not keep[k]:
                    ev = out[i]
                    out[i] = Event(time=ev.time, event=ev.event, severity=Severity.ORTA, category=ev.category)
        # NEUROSIMBOLIK semantik-olabilirlik: KİŞİ-merkezli yuksek-sev olay (yarali/dusmus/saldiri vb.) iddia
        # ediliyor ama YOLO segmentte nesne bulup KİŞİ bulamadiysa -> fiziksel olarak suheli -> Orta'ya cek.
        # FAIL-OPEN: YOLO abstain (None) veya kisi-var (True) ise DOKUNMA -> grenli'de gercek kisi-olayi recall'i korunur.
        if settings.semantic_plausibility and out and any(
                _SEV_ORD[e.severity] >= _SEV_ORD[Severity.YUKSEK] and _PERSON_RE.search(e.event) for e in out):
            try:
                from dilajan import detector
                pp = detector.persons_present(seg.frames)
            except Exception:
                pp = None
            if pp is False:  # nesne var ama kisi yok (None=abstain'de dokunmayiz)
                for i, ev in enumerate(out):
                    if _SEV_ORD[ev.severity] >= _SEV_ORD[Severity.YUKSEK] and _PERSON_RE.search(ev.event):
                        out[i] = Event(time=ev.time, event=ev.event, severity=Severity.ORTA, category=ev.category)
        # F1: POZ-TABANLI DOGRULAMA (Woodpecker/Semantic-Drive deseni; fall vs comelme/egilme).
        # VLM "kisi yere dusmus/hareketsiz" der ama YOLO-poz kisinin EMIN bicimde DIK (comelmis/egilmis)
        # oldugunu gosterirse severity'yi dispatch-esiginin ALTINA (Orta) cek -> sahte "dusmus kisi Kritik+cagri"
        # kesilir. FAIL-OPEN: poz guvenilmez/kisi yoksa (ABSTAIN) VLM korunur -> gercek dusme recall'i bozulmaz.
        notes: List[str] = []
        if settings.verify_pose_falls and out and any(_is_person_fall_event(e.event) for e in out):
            try:
                from dilajan import detector
                verdict, vnote = detector.verify_fallen(seg.frames)
            except Exception as ex:
                verdict, vnote = "ABSTAIN", f"detector hata: {ex}"
            if verdict == "REJECT":
                adj: List[Event] = []
                for ev in out:
                    if _is_person_fall_event(ev.event) and _SEV_ORD[ev.severity] > _SEV_ORD[Severity.ORTA]:
                        ev = Event(time=ev.time, end_time=ev.end_time, event=ev.event,
                                   severity=Severity.ORTA, category=ev.category, bbox=ev.bbox, region=ev.region)
                    adj.append(ev)
                out = adj
                notes.append(f"perceive: segment {seg.index} poz-doğrulama [{vnote}] "
                             "-> kişi-düşme severity↓Orta")
        # Mekansal grounding: onemli olaylarin karedeki konumunu (bbox + bölge) cikar
        if settings.spatial_grounding and out:
            grounded: List[Event] = []
            for ev in out:
                if _SEV_ORD[ev.severity] >= _SEV_ORD[Severity.YUKSEK]:
                    bb, reg = _ground_event(vlm, seg.frames, ev.event)
                    if bb:
                        ev = Event(time=ev.time, event=ev.event, severity=ev.severity,
                                   category=ev.category, bbox=bb, region=reg)
                grounded.append(ev)
            out = grounded
        # KANIT SORULARI (ASK-HINT) — BURAYA KONUMLANDIRILDI, iki gerekceyle:
        #  (a) severity'yi degistirebilen TUM adimlar (kalibrasyon, verify_events,
        #      semantic_plausibility, verify_pose_falls) ve grounding ARTIK BITTI ->
        #      o kararlarin hepsi olayin ORIJINAL metniyle alindi (G3);
        #  (b) asagidaki DETERMINISTIK dedektor olaylari (geofence/arac/kalabalik) HENUZ
        #      eklenmedi -> LLM adlandirmasi onlarin sabit metnini BOZAMAZ.
        out, kanit_notlari = _kanit_adlandirma(vlm, seg, desc, out)
        notes.extend(kanit_notlari)
        # SAVUNMA geofence: yasak/kisitli bolgelerde KISI -> "Yasak Bölge İhlali" (deterministik YOLO).
        # Opt-in (restricted_zones bos=kapali -> mevcut davranis degismez); VLM zone-reasoning guvenilmez
        # oldugu icin uzman dedektorle yapilir (perimetre/tesis guvenligi cekirdegi).
        if settings.restricted_zones:
            try:
                from dilajan import detector
                zones = settings.restricted_zones.split(",")
                hits = detector.detect_zone_intrusion(seg.frames, zones)
            except Exception:
                hits = {}
            existing = {(e.region, e.category) for e in out}
            for reg, (t, cf) in hits.items():
                if (reg, EventCategory.YETKISIZ_ERISIM) in existing:
                    continue  # ayni bolgede zaten yetkisiz-erisim olayi var -> tekrar etme
                out.append(Event(
                    time=t, event=f"Yasak bölge ihlali: yetkisiz kişi '{reg}' kısıtlı bölgesinde tespit edildi",
                    severity=Severity.YUKSEK, category=EventCategory.YETKISIZ_ERISIM, region=reg))
        # Hizli-kazanim: YETKISIZ/YANLIS-KONUMLU ARAC (deterministik YOLO; araclar iri -> grenli-guvenli).
        # vehicle_zones set ise: yasak bolgedeki arac -> ihlal; bos ise: durak (dwell) arac bilgi amacli.
        if settings.detect_vehicles:
            try:
                from dilajan import detector
                vzones = settings.vehicle_zones.split(",") if settings.vehicle_zones else []
                vhits = detector.detect_vehicle_intrusion(seg.frames, vzones)
            except Exception:
                vhits = []
            for vh in vhits:
                if vh.get("violation"):
                    out.append(Event(
                        time=vh["time"],
                        event=f"Yetkisiz/yanlış konumlu araç: {vh['label']} '{vh['region']}' kısıtlı bölgesinde",
                        severity=Severity.YUKSEK, category=EventCategory.YETKISIZ_ERISIM, region=vh.get("region")))
                else:
                    out.append(Event(
                        time=vh["time"], event=f"Durağan araç tespit edildi ({vh['label']})",
                        severity=Severity.ORTA, category=EventCategory.ANOMALI))
        # Hizli-kazanim: KALABALIK/TOPLANMA + ANI DAGILMA (panik). Sartname ornegi: "personel toplanmasi".
        if settings.detect_crowd:
            try:
                from dilajan import detector
                cs = detector.crowd_stats(seg.frames, min_persons=settings.crowd_min_persons)
            except Exception:
                cs = {}
            if cs.get("gathering"):
                out.append(Event(
                    time=cs.get("peak_time", seg.start_str),
                    event=f"Personel/insan toplanması ({cs['peak']} kişi bir arada)",
                    severity=Severity.ORTA, category=EventCategory.ANOMALI))
            if cs.get("dispersal"):
                out.append(Event(
                    time=cs.get("dispersal_time", seg.start_str),
                    event=f"Ani dağılma / panik hareketi (kalabalık {cs['peak']} kişiden hızla azaldı)",
                    severity=Severity.YUKSEK, category=EventCategory.GUVENLIK))
        return out, ("\n".join(notes) if notes else None)
    except Exception as ex:  # hata toleransi: segment atlanir
        return [], f"perceive: segment {seg.index} hatasi: {ex}"


_DEDUP_STOP = {
    "bir", "bu", "ile", "için", "olan", "var", "yok", "gibi", "çok", "daha", "ama",
    "arasında", "görüntüleri", "görüntü", "kamera", "kareler", "karede", "video",
    "gözleniyor", "gözlemleniyor", "görünüyor", "tespit", "edildi", "ediliyor",
}


def _dedup_words(text: str) -> set:
    """Anlamli (>=4 harf, stopword olmayan) kelime kumesi."""
    return {w for w in re.findall(r"[a-zçğıöşü]+", text.lower()) if len(w) >= 4 and w not in _DEDUP_STOP}


def _dedupe_events(events: List[Event]) -> List[Event]:
    """Ardisik + ayni kategori + benzer olaylari tek olaya birlestirir (surekli olay
    her segmentte tekrar raporlanmasin). Recall/risk/kategori'yi korur: en bilgilendirici
    metni, en yuksek severity'yi ve en erken zaman damgasini tutar."""
    kept: List[Event] = []
    for e in events:
        if kept:
            k = kept[-1]
            if k.category == e.category:
                ew, kw = _dedup_words(e.event), _dedup_words(k.event)
                if ew and kw:
                    inter = len(ew & kw)
                    union = len(ew | kw)
                    jacc = inter / union if union else 0.0
                    # yuksek ortusme VEYA kisa olaylar ortak anlamli kelime paylasiyorsa birlestir
                    if jacc >= 0.5 or (inter >= 1 and (len(ew) <= 4 or len(kw) <= 4)):
                        better = e.event if len(e.event) > len(k.event) else k.event
                        sev = e.severity if _SEV_ORD[e.severity] > _SEV_ORD[k.severity] else k.severity
                        # olay birden cok segmente yayiliyor -> zaman PENCERESI [baslangic, bitis]
                        t0 = min(k.time, e.time)
                        t1 = max(k.end_time or k.time, e.end_time or e.time)
                        birlesik = Event(time=t0, end_time=(t1 if t1 != t0 else None),
                                         event=better, severity=sev, category=k.category,
                                         bbox=k.bbox or e.bbox, region=k.region or e.region)
                        # ALARM MUHAFIZI birlestirmede KAYBOLMAMALI (sema-disi alan, `Event(...)`
                        # yeniden-kurmasi onu dusurur): `better` hangi olaydan geldiyse onun
                        # kanit-oncesi metni tasinir, yoksa digerininki. Temkinli yon: alarm
                        # karari HER ZAMAN kanit-ONCESI metinle verilsin.
                        _pe, _pk = (getattr(e, "evidence_prev", None),
                                    getattr(k, "evidence_prev", None))
                        prev = (_pe if better == e.event else _pk) or _pk or _pe
                        if prev:
                            birlesik = birlesik.model_copy(update={"evidence_prev": prev})
                        kept[-1] = birlesik
                        continue
        kept.append(e)
    # Zamansal-SUREKLILIK yukseltmesi (Agent-C): bir TEHLIKE olayi >=2 bitisik segmentte surduyse
    # (end_time set) ve severity Orta'da takildiysa Yuksek'e cek (+1, capped). Gercek tehlike surer,
    # halusinasyon izoledir; tek-yonlu/yukari -> recall'i bozmaz. (sistematik dusuk-puanlamayi duzeltir)
    if settings.persist_escalation:
        esc: List[Event] = []
        for e in kept:
            if (e.end_time and e.end_time != e.time
                    and e.category in _DANGER_CATS and e.severity == Severity.ORTA):
                # model_copy: TUM alanlar + sema-disi ALARM MUHAFIZI (`evidence_prev`)
                # korunur; `Event(...)` yeniden-kurmasi onlari sessizce dusururdu.
                e = e.model_copy(update={"severity": Severity.YUKSEK})
            esc.append(e)
        kept = esc
    return kept


def _segment_consistent_events(vlm: VLMClient, seg, n: int) -> Tuple[List[Event], Optional[str]]:
    """Algı self-consistency (SelfCheckGPT + AnomalyRuler aggregation): segmenti N kez algılar,
    bir olayı YALNIZCA koşuların ÇOĞUNDA (>= n//2+1) tekrar ederse tutar. Stokastik halüsinasyon
    (tek koşuda beliren uydurma olay) elenir; gerçek/tutarlı olay korunur. Severity self-rating'e
    güvenmez — tutarlılık grounding vekilidir."""
    runs: List[List[Event]] = []
    for _ in range(n):
        evs, _note = _analyze_one_segment(vlm, seg)
        runs.append(evs)
    clusters: list = []  # her biri: {"cat","words","events","runs"(set)}
    for ri, evs in enumerate(runs):
        for e in evs:
            ew = _dedup_words(e.event)
            placed = False
            for c in clusters:
                if c["cat"] != e.category or not ew:
                    continue
                inter, union = len(ew & c["words"]), len(ew | c["words"])
                jacc = inter / union if union else 0.0
                if jacc >= 0.5 or (inter >= 1 and (len(ew) <= 4 or len(c["words"]) <= 4)):
                    c["events"].append(e); c["runs"].add(ri); c["words"] |= ew
                    placed = True
                    break
            if not placed:
                clusters.append({"cat": e.category, "words": set(ew), "events": [e], "runs": {ri}})
    # COGUNLUK-OYU (SelfCheckGPT): olay yalniz kosularin >= n//2+1'inde tekrar ederse tutulur.
    # OLCULDU (docs/iyilestirmeler.md §9): FER %31->12 (halusinasyon duser) AMA recall %88->72 (grainy'de
    # gercek olay da stokastik). OPT-IN "yuksek-hassasiyet modu"dur; varsayilan KAPALI (n=1) -> recall-oncelik.
    thr = n // 2 + 1
    kept = [max(c["events"], key=lambda e: (_SEV_ORD[e.severity], len(e.event)))
            for c in clusters if len(c["runs"]) >= thr]
    note = (f"perceive: segment {seg.index} self-consistency {n}× -> "
            f"{len(clusters)} aday, {len(kept)} tutuldu (eşik {thr}/{n})")
    if settings.evidence_questions:
        # Sessiz kalmamak icin karar-izine yazilir (fast_mode ile AYNI desen).
        note += ("\nperceive: kanıt soruları N-KEZ ALGIDA uygulanmadı "
                 f"(event_consistency_n={n}; çoğunluk-oyu olay METNİNE dayanır, "
                 "yeniden adlandırma oyu bozardı — ayrıca K4 gecikme tavanı)")
    return kept, note


def perceive(state: AgentState) -> dict:
    """Iki asamali algi (serbest tarif -> olay cikarimi), segmentler PARALEL islenir.
    event_consistency_n>1 ise her segment N kez algılanır ve olaylar çoğunluk-oyuyla süzülür
    (halüsinasyon-azaltma). vLLM eszamanli istekleri batch'ledigi icin paralel calisir."""
    trace = state.get("trace", [])
    events: List[Event] = []
    # K6: dugum-seviyesi hata toleransi — VLM/istemci/segment isleme cokerse akis durmaz,
    # o ana kadar toplanan olaylarla (veya bos listeyle) devam eder.
    try:
        # K4 izlenebilirlik: sorgu kullanildiysa karar-izinde NET olarak gorunur (ve juriye
        # karsi kanit: odak eklendi ama kritik olaylar bastirilmadi).
        qline = _query_trace_line("perceive: analiz operatör sorgusuna ODAKLANDI: ",
                                  " (kritik olaylar bastırılmadı — sorgu odaklar, filtrelemez)")
        if qline:
            trace.append(qline)
        vlm = _get_vlm()
        segments = list(state.get("segments", []))
        if segments:
            N = max(1, settings.event_consistency_n)
            analyze = ((lambda s: _segment_consistent_events(vlm, s, N)) if N > 1
                       else (lambda s: _analyze_one_segment(vlm, s)))
            workers = max(1, min(len(segments), settings.max_parallel_segments))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for evs, note in pool.map(analyze, segments):
                    events.extend(evs)
                    if note:
                        trace.append(note)
            events.sort(key=lambda e: e.time)
            n_raw = len(events)
            events = _dedupe_events(events)
            trace.append(f"perceive: {len(events)} olay ({n_raw} ham, {len(segments)} segment, {workers} paralel)")
    except Exception as ex:
        trace.append(f"perceive: dugum hatasi (toleransli devam, {len(events)} olay korundu): {ex}")
    # ALARM MUHAFIZI bayragi: en az bir olayin adi kanit sorulariyla yeniden yazildi mi?
    # `act` bu bayrakla RISK terimini sevk kapisindan maskeler (risk_recall_bias ile AYNI
    # desen). Ozellik kapaliyken HER ZAMAN False -> sevk cebiri bit-bit eskisiyle ayni.
    return {"events": events, "trace": trace,
            "evidence_renamed": any(getattr(e, "evidence_prev", None) for e in events)}


def _secs(mmss: str) -> int:
    m = re.search(r"(\d{1,2}):(\d{2})", str(mmss or ""))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else 0


def route_after_perceive(state: AgentState) -> str:
    """Koşullu kenar: belirsiz (Orta) olay varsa yeniden-incele, yoksa doğrudan reason.
    Ajanin 'tekrar bakayim' kararini temsil eder (adaptif otonomi)."""
    if not settings.adaptive_reexamine or state.get("reexamined"):
        return "reason"
    events = state.get("events", [])
    if any(_SEV_ORD.get(e.severity, 0) == _SEV_ORD[Severity.ORTA] for e in events):
        return "reexamine"
    return "reason"


_REEX_PROMPT = (
    "Bu güvenlik kamerası karelerinde şu gözlem var: \"{event}\". Bu GERÇEKTEN dikkate değer/anormal "
    "bir olay mı, yoksa olağan/rutin bir aktivite mi? Yalnızca TEK KELİME yanıt ver: "
    "CIDDI (gerçek ciddi olay), RUTIN (olağan, olay değil), veya BELIRSIZ."
)


def reexamine(state: PolicyAgentState) -> dict:
    """Belirsiz (Orta) olaylari segment kareleriyle odakli yeniden-degerlendirir:
    RUTIN -> Düşük (FP azalt), CIDDI -> Yüksek (ince gerçek olayi yakala), BELIRSIZ -> korur.

    Ayrica "RUTIN" denen olaylarin anahtarlarini `reexamine_routine`e yazar: politika hakemligi
    (policy_gate) bu olaylari ADAY ALMAZ, boylece operator beyani, GORSEL olarak zaten rutin
    bulunmus bir olayi sessizce yukseltemez (bedava yanlis-pozitif kapisi)."""
    trace = state.get("trace", [])
    events = list(state.get("events", []))
    routine: List[str] = list(state.get("reexamine_routine", []) or [])
    # K6: dugum-seviyesi hata toleransi — yeniden-inceleme cokerse olaylar OLDUGU GIBI korunur
    # (guvenli varsayilan: severity'ye dokunma), akis reason'a devam eder.
    try:
        segments = state.get("segments", [])
        vlm = _get_vlm()
        n_up = n_down = 0
        new_events: List[Event] = []
        for ev in events:
            if _SEV_ORD.get(ev.severity, 0) != _SEV_ORD[Severity.ORTA]:
                new_events.append(ev)
                continue
            t = _secs(ev.time)
            seg = next((s for s in segments if _secs(s.start_str) <= t <= _secs(s.end_str)), None)
            if seg is None:
                new_events.append(ev)
                continue
            # ALARM MUHAFIZI (adversaryel denetimde OLCULEN kusur): bu cagri severity'yi
            # Orta->YUKSEK'e cikarabilir ve YUKSEK dogrudan sevk kapisini acar. Kanit
            # sorulari olayin ADINI daha belirli/alarmli hale getirdiginde bu kapi
            # ozellik yuzunden aciliyordu (olculdu: Orta -> Yuksek, sevk [] -> ['guvenlik_ekibi_uyar']).
            # Cozum: hakem HER ZAMAN kanit-ONCESI metni gorur -> verdigi karar ozellik
            # KAPALIYKENKI ile BIREBIR AYNIDIR (istem metni de byte-esit olur).
            hakem_metni = getattr(ev, "evidence_prev", None) or ev.event
            try:
                ans = (vlm.analyze_frames(seg.frames, _REEX_PROMPT.format(event=hakem_metni),
                                          temperature=0.0, max_tokens=20) or "").upper()
            except Exception:
                new_events.append(ev)
                continue
            # model_copy: alanlarin tamami + sema-disi ALARM MUHAFIZI korunur
            # (`Event(...)` yeniden-kurmasi `evidence_prev`i sessizce dusururdu).
            if "RUTIN" in ans:
                new_events.append(ev.model_copy(update={"severity": Severity.DUSUK}))
                routine.append(policy.event_key(ev))
                n_down += 1
            elif "CIDDI" in ans:
                new_events.append(ev.model_copy(update={"severity": Severity.YUKSEK}))
                n_up += 1
            else:
                new_events.append(ev)
    except Exception as ex:
        trace.append(f"reexamine: dugum hatasi (toleransli devam, olaylar degistirilmedi): {ex}")
        return {"events": events, "reexamined": True, "trace": trace,
                "reexamine_routine": routine}
    trace.append(f"reexamine: belirsiz olaylar yeniden-incelendi (↑{n_up} ciddi, ↓{n_down} rutin)")
    return {"events": new_events, "reexamined": True, "trace": trace,
            "reexamine_routine": routine}


def _frames_at(segments, time_str: str):
    """Bir zaman damgasini iceren segmentin karelerini dondurur (yoksa None)."""
    t = _secs(time_str)
    seg = next((s for s in segments if _secs(s.start_str) <= t <= _secs(s.end_str)), None)
    return getattr(seg, "frames", None) if seg is not None else None


def policy_gate(state: PolicyAgentState) -> dict:
    """POLITIKA HAKEMLIGI — beyan-bagli onem derecesi (kusur #2 cozumu).

    Video basina TEK ve GORUNTUSUZ bir LLM cagrisiyla aday olaylari operatorun BEYAN ETTIGI
    kural maddelerine karsi uc-degerli (IHLAL/UYGUN/BELIRSIZ) siniflandirir; dort deterministik
    kapiyi gecen olayin severity'sini kuralin BEYAN EDILEN seviyesine TEK-YONLU yukseltir.
    Risk zincire kendiliginden akar (reason'daki risk tabani); SEVK ise ayri ve varsayilan
    KAPALI bir kapidan gecer (settings.policy_dispatch).

    K2 (GERI-UYUM): `settings.facility_policy` bos ise TAM NO-OP — ilk satirda `return {}`.
    Model cagrisi yapilmaz, olay kopyalanmaz, karar-izine SATIR BILE eklenmez.
    K6 (FAIL-OPEN): her ariza modunda olaylar DEGISTIRILMEDEN gecer, akis reason'a devam eder.
    """
    events = state.get("events", [])
    if not (settings.facility_policy or "").strip() or not events:
        return {}  # <-- K2: tam no-op (bayrak sozune degil, BU SATIRA dayanir)
    trace = state.get("trace", [])
    try:
        rules = policy.parse_policy(
            settings.facility_policy,
            _to_severity(settings.policy_default_severity),
            settings.policy_max_rules,
        )
        if not rules:
            trace.append("policy: beyan edilen politikadan gecerli kural cikarilamadi "
                         "(madde cok kisa/bos olabilir) -> yukseltme yok")
            return {"trace": trace}
        routine = set(state.get("reexamine_routine", []) or [])
        cands = policy.candidates(events, rules, routine)
        if not cands:
            trace.append("policy: aday olay yok (hepsi zaten beyan seviyesinde, Normal kategorili "
                         "veya reexamine 'RUTIN' demis) -> model cagrisi YAPILMADI")
            return {"trace": trace}
        trace.append("policy: " + policy.rules_summary(rules))  # K5: kural tablosu AYNEN karar-izine
        raw = _get_vlm().chat(
            [{"role": "system", "content": prompts.SYSTEM_PERSONA},
             {"role": "user", "content": policy.build_prompt(rules, cands)}],
            temperature=0.0, max_tokens=400,  # GORUNTUSUZ + video basina TEK cagri
        )
        verdicts = policy.parse_verdicts(raw, len(cands), {r.rid for r in rules})
        adj = policy.adjudicate(
            events, cands, verdicts, rules,
            accept_hedged=settings.policy_accept_hedged,
            max_esc=settings.policy_max_escalations,
        )
        if settings.policy_verify_frames and adj.records:  # OPT-IN, varsayilan KAPALI
            segments = state.get("segments", []) or []
            adj = policy.verify_with_frames(
                _get_vlm(), lambda t: _frames_at(segments, t), adj, rules)
        trace.extend(adj.trace)  # K5: her yukseltme/red NEDENIYLE yazildi
        st = adj.stats
        trace.append(
            f"policy: {st.get('aday', 0)} aday, {st.get('yukseltme', 0)} yukseltme, "
            f"{st.get('red', 0)} red (kapsam {st.get('red_kapsam', 0)}, kanit {st.get('red_kanit', 0)}, "
            f"cekince {st.get('red_cekince', 0)}, tavan {st.get('red_tavan', 0)}, "
            f"butce {st.get('red_butce', 0)}, karar-yok {st.get('karar_yok', 0)}); "
            f"karar dagilimi IHLAL {st.get('ihlal', 0)}/UYGUN {st.get('uygun', 0)}/"
            f"BELIRSIZ {st.get('belirsiz', 0)}/R0 {st.get('r0', 0)}; "
            f"sevk yolu {'ACIK' if settings.policy_dispatch else 'KAPALI'} "
            f"(policy_dispatch={settings.policy_dispatch})"
        )
        return {"events": adj.events, "policy_escalations": adj.records,
                "policy_max_intrinsic": adj.max_intrinsic_ord, "trace": trace}
    except Exception as ex:  # FAIL-OPEN: mevcut davranisa coker
        trace.append(f"policy_gate: dugum hatasi (toleransli devam, olaylar degistirilmedi): {ex}")
        return {"trace": trace}


def reason(state: PolicyAgentState) -> dict:
    trace = state.get("trace", [])
    vlm = _get_vlm()
    events = state.get("events", [])
    info = state.get("video_info")
    duration = info.duration_str if info else "?"
    cuts = state.get("scene_cuts", []) or []

    instr = prompts.DECISION_SUPPORT_INSTRUCTION.format(
        events_block=_events_block_scened(events, cuts), duration=duration
    )
    # M3: cok-bolumlu/kopuk video -> bolumleri bagimsiz ele al, neden-sonuc/oyku kurma
    if cuts:
        instr += (
            f"\n\nÖNEMLİ — ÇOK BÖLÜMLÜ VİDEO: Bu video {len(cuts) + 1} AYRI ve KOPUK bölümden oluşuyor "
            f"(sahne kesimleri: {', '.join(format_timestamp(c) for c in cuts)}). Bölümler BİRBİRİNDEN "
            "BAĞIMSIZDIR; aralarında neden-sonuç ilişkisi veya tek bir olay öyküsü KURMA "
            "(ör. 'önce ... sonra ...' deme). Özette her bölümü AYRI cümleyle değerlendir; genel risk "
            "en ciddi bölüme göre belirlenir."
        )
    # SORGU-GUDUMLU: operator sorgusu varsa karar-destek promptuna DOGRUDAN-YANIT alani eklenir.
    # Bos sorgu -> qa_block "" -> instr ve tum asagidaki davranis BIT-BIT eskisiyle ayni (K1).
    qa_block = _query_answer_block()
    instr += qa_block
    messages = [
        {"role": "system", "content": prompts.SYSTEM_PERSONA},
        {"role": "user", "content": instr},
    ]
    summary = "Özet üretilemedi."
    risk = RiskAssessment(level=Severity.ORTA, rationale="Belirlenemedi.")
    actions: List[Action] = []
    query_answer: Optional[str] = None
    try:
        raw = vlm.chat(messages, temperature=0.2, max_tokens=800)
        data = extract_json(raw)
        summary = str(data.get("summary", summary)).strip()
        r = data.get("risk", {})
        risk = RiskAssessment(
            level=_to_severity(str(r.get("level", "Orta"))),
            rationale=str(r.get("rationale", "")).strip() or "Belirtilmedi.",
        )
        for a in data.get("actions", []):
            actions.append(
                Action(
                    action=str(a.get("action", "")).strip(),
                    priority=_to_severity(str(a.get("priority", ""))),
                    rationale=(str(a.get("rationale", "")).strip() or None),
                )
            )
        if qa_block:  # yalniz sorgu varken okunur -> sorgusuz akista TEK SATIR bile calismaz
            query_answer = str(data.get("query_answer", "") or "").strip() or None
    except Exception as ex:
        trace.append(f"reason: hata: {ex}")

    # K3 FAIL-OPEN: sorgu yaniti uretilemediyse (model alani dondurmedi / JSON bozuk / cagri
    # coktu) ANALIZ NORMAL DEVAM EDER; operatore uydurma yerine DURUST bir not gosterilir.
    if qa_block:
        if query_answer:
            # Savunma amacli UZUNLUK TAVANI: prompt "en fazla 2-3 cümle" ister ama bu KODDA
            # zorlanmiyordu. Kotu-niyetli bir sorgu modeli uzun bir blok uretmeye ikna
            # ederse hem operator paneli hem zengin JSON sisebilir -> sessizce kirp.
            if len(query_answer) > _QUERY_ANSWER_MAX_CHARS:
                query_answer = query_answer[: _QUERY_ANSWER_MAX_CHARS - 1].rstrip() + "…"
                trace.append("reason: sorgu yanıtı aşırı uzundu -> "
                             f"{_QUERY_ANSWER_MAX_CHARS} karaktere kırpıldı")
            trace.append(_query_trace_line("reason: operatör sorgusu yanıtlandı: ", "")
                         or "reason: operatör sorgusu yanıtlandı")
        else:
            query_answer = ("Sorgu yanıtı üretilemedi (model 'query_answer' alanını döndürmedi); "
                            "özet ve olay listesini inceleyiniz.")
            trace.append("reason: operatör sorgusu yanıtlanamadı -> fail-open "
                         "(analiz ve şartname çıktısı normal şekilde tamamlandı)")

    # MODELIN KENDI risk yargisi (taban/yukseltme uygulanmadan ONCE) — politika kaynakli
    # risk artisini modelin kendi yargisindan ayirt etmek icin gerekli (act sevk cebiri).
    model_risk_ord = _SEV_ORD.get(risk.level, 0)

    # Risk tabani (guardrail): gercek tehdidi dusuk gostermeyi onle.
    # Risk, tespit edilen en yuksek olay severity'sinden dusuk olamaz.
    if events:
        max_ev = max(_SEV_ORD[e.severity] for e in events)
        if _SEV_ORD[risk.level] < max_ev:
            bumped = _ORD_SEV[max_ev]
            trace.append(f"reason: risk tabani uygulandi {risk.level.value}->{bumped.value}")
            risk = RiskAssessment(level=bumped, rationale=risk.rationale)

    # Agent-C #1: risk-RECALL-bias (maliyet-asimetrik). Tehlike-kategori olay Orta+ ise genel RISK >= Yuksek.
    # Alarm recall-yanli (kacirilan tehlike >> fazladan uyari); DISPATCH (act) AYRI/hassas kapida -> dar-FP kontrollu.
    if settings.risk_recall_bias and events:
        if any(e.category in _DANGER_CATS and _SEV_ORD[e.severity] >= _SEV_ORD[Severity.ORTA] for e in events):
            if _SEV_ORD[risk.level] < _SEV_ORD[Severity.YUKSEK]:
                trace.append(f"reason: risk-recall-bias {risk.level.value}->Yüksek (tehlike-olay Orta+)")
                risk = RiskAssessment(level=Severity.YUKSEK, rationale=risk.rationale)

    # --- POLITIKA HAKEMLIGI: sevk maskesi + confirm-then-act aksiyonlari (K3/K5) ---
    # Risk TABANI politika yukseltmesini otomatik olarak risk'e tasir (istenen: risk kalibrasyonu).
    # Ancak act()'teki sevk kapisinin IKINCI terimi de risk'e bagli oldugu icin, maskelenmezse
    # politika yukseltmesi SESSIZCE operasyonel cagri tetiklerdi. Asagidaki bayrak bu sizintiyi kapatir.
    risk_from_policy_only = False
    try:  # K6: bu katman hicbir kosulda reason'i cokertmemeli
        _recs = state.get("policy_escalations") or []
        _max_intr = state.get("policy_max_intrinsic")
        if _max_intr is None:
            _max_intr = policy.intrinsic_max_ord(events)
        risk_from_policy_only = bool(_recs) and _max_intr < _SEV_ORD[Severity.YUKSEK] \
            and model_risk_ord < _SEV_ORD[Severity.YUKSEK]
        if risk_from_policy_only:
            # ikinci (yedek) tasima yolu: kanal dusse bile act() bayragi risk nesnesinden okur
            risk = risk.model_copy(update={"policy_only": True})
            trace.append("policy: risk esigi YALNIZ operator beyanindan geldi -> operatore YUKSEK "
                         "risk gosterilir ancak otomatik SEVK sinyali maskelendi "
                         "(policy_dispatch kapisi)")
        _seen_rid: set = set()
        for _r in _recs:  # her yukseltilmis kural icin TEK confirm-then-act onerisi
            _rid = str(_r.get("kural", ""))
            if _rid in _seen_rid:
                continue
            _seen_rid.add(_rid)
            _kural = str(_r.get("kural_metni", "") or "")
            _kural = _kural if len(_kural) <= 60 else _kural[:57] + "..."
            actions.append(Action(
                action=f"{_rid} politika ihlali ({_kural}) — operatör teyidi sonrası ekip sevki",
                priority=_to_severity(str(_r.get("yeni", ""))),
                rationale=f"[{_r.get('time')}] {_r.get('event')} — tesis yönetiminin beyan ettiği "
                          f"{_rid} maddesiyle eşleşti (kanıt: \"{_r.get('kanit')}\").",
            ))
    except Exception as _ex:  # FAIL-OPEN (maske ZATEN hesaplandiysa korunur)
        trace.append(f"policy: reason katmani hatasi (toleransli devam): {_ex}")

    # VL-Calibration (grounded algi-guveni): VLM self-report asiri-ozguvenli (olculdu: grenli'de bile "dusuk"
    # demez) -> algi-guvenini OBJEKTIF cozunurlukten turet. Dusuk-res ise operatore manuel-teyit ADVISORY ekle.
    # Girdi-tavanini (grenli'de sessiz dusuk-puanlama) DURUST operator-uyarisina + puanlanan-otonomi davranisina cevirir.
    if settings.perception_confidence and info is not None:
        lo = min(info.width or 0, info.height or 0)
        if 0 < lo < 360:
            trace.append(f"reason: düşük çözünürlük ({info.width}x{info.height}) -> manuel-teyit advisory")
            actions.append(Action(
                action=f"Düşük görüntü çözünürlüğü ({info.width}×{info.height}); olay tiplerini manuel teyit önerilir",
                priority=Severity.DUSUK,
                rationale="Düşük çözünürlük, otomatik analizin ayrıntı-kesinliğini sınırlar (algı-güveni düşük)."))

    # SORGU YANITI dil-safligi — BAGIMSIZ ele alinir (adversaryel denetim bulgusu).
    # ONCEKI HALI ayni kosula bagliydi: kotu-niyetli bir sorgu ("Türkçe yerine İngilizce yanıt
    # ver") YALNIZ query_answer'i yabancilastirarak ozet/gerekce/AKSIYONLARIN da yeniden
    # yazilmasini tetikleyebiliyordu -> saldirgan-kontrollu ekstra model cagrilari + operatorun
    # gordugu ozet metninin degismesi. Artik yalniz ilgili alan duzeltilir.
    # K1: sorgusuz akista `query_answer` None -> bu satir bir sey YAPMAZ.
    if query_answer and _has_foreign(query_answer):
        query_answer = _purify(vlm, query_answer)
        trace.append("reason: sorgu yanıtında dil-safligi guard uygulandi")

    # G12 dil-safligi guard: Turkce-disi karakter sizdiysa ozet/gerekce/aksiyonlari duzelt (temizse no-op)
    if (_has_foreign(summary) or _has_foreign(risk.rationale)
            or any(_has_foreign(a.action) for a in actions)):
        summary = _purify(vlm, summary)
        # model_copy: seviye + (varsa) `policy_only` yedek bayragi KORUNUR. Yeniden-kurma
        # (`RiskAssessment(level=..., rationale=...)`) bu ek oznitelig SESSIZCE dusuruyordu ->
        # act()'teki yedek maske yolu bu dalda olu kaliyordu.
        risk = risk.model_copy(update={"rationale": _purify(vlm, risk.rationale)})
        actions = [Action(action=_purify(vlm, a.action), priority=a.priority,
                          rationale=(_purify(vlm, a.rationale) if a.rationale else a.rationale))
                   for a in actions]
        trace.append("reason: dil-safligi guard uygulandi (Türkçe-disi karakter düzeltildi)")

    trace.append(f"reason: risk={risk.level.value}, {len(actions)} aksiyon önerisi")
    return {"summary": summary, "risk": risk, "actions": actions, "trace": trace,
            "risk_from_policy_only": risk_from_policy_only, "query_answer": query_answer}


# --- K3: argüman onarimi (sessiz dusen dispatch'i onler) ---
# Modelin urettigi argüman ADLARI aracin imzasindan sapabilir ("konum" yerine "yer" gibi).
# Pydantic dogrulama hatasi verince cagri SESSIZCE dusuyordu; asagidaki katman argümanlari
# onarip TEK KEZ yeniden dener, basarisiz olursa karar-izine NET uyari yazar.

# Argüman adi -> anlamsal "slot". Es-anlamli isim eslesmesi ve eksik-argüman varsayilani
# ayni tablodan turer (or. "yer"/"lokasyon" -> konum slotu -> hedef argüman "konum").
_ARG_SLOT_HINTS = (
    ("konum", ("konum", "yer", "alan", "bolge", "bölge", "lokasyon", "mahal", "saha", "location")),
    ("severity", ("aciliyet", "risk", "oncelik", "öncelik", "seviye", "onem", "önem",
                  "severity", "priority", "urgency")),
    ("ekipman", ("ekipman", "makine", "cihaz", "arac", "araç", "equipment", "machine")),
    ("metin", ("sebep", "neden", "ozet", "özet", "mesaj", "aciklama", "açiklama", "not",
               "detay", "bilgi", "olay", "durum", "message", "reason", "summary")),
)


def _arg_slot(name: str) -> Optional[str]:
    """Bir argüman adinin anlamsal slotunu dondurur (bulunamazsa None)."""
    n = (name or "").strip().lower()
    if not n:
        return None
    for slot, keys in _ARG_SLOT_HINTS:
        if any(k in n for k in keys):
            return slot
    return None


def _tool_arg_spec(fn) -> Tuple[List[str], List[str]]:
    """Arac icin (tum argüman adlari, ZORUNLU argüman adlari) dondurur.
    Sema okunamazsa tum adlar zorunlu sayilir (toleransli/fail-open)."""
    try:
        names = list(fn.args.keys())
    except Exception:
        return [], []
    required = list(names)
    try:
        schema = fn.args_schema.model_json_schema()
        req = schema.get("required")
        if isinstance(req, list):
            required = [n for n in names if n in req]
    except Exception:
        pass
    return names, required


def _dispatch_context(events: List[Event], risk: Optional[RiskAssessment]) -> Dict[str, str]:
    """Eksik argümani doldurmak icin olay baglami (konum / severity / serbest metin / ekipman)."""
    top = max(events, key=lambda e: _SEV_ORD.get(e.severity, 0)) if events else None
    sev = (top.severity.value if top else
           (risk.level.value if risk else Severity.ORTA.value))
    return {
        "konum": (top.region if (top and top.region) else "Bilinmiyor"),
        "severity": sev,
        "metin": (top.event if top else "Tespit edilen güvenlik olayi"),
        "ekipman": "Bilinmeyen ekipman",
    }


def _stringify(value) -> str:
    """Arac imzalari `str` bekliyor; model sayi/liste/sozluk verirse metne cevirir."""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)
    return str(value)


def _repair_args(fn, raw_args, ctx: Dict[str, str]) -> Tuple[dict, List[str]]:
    """Model argümanlarini aracin BEKLEDIGI imzaya onarir. (onarilmis_args, duzeltme_notlari) doner.

    Sira: (1) birebir ad eslesmesi, (2) anlamsal es-anlamli eslesme ("yer"->"konum"),
    (3) yakin-isim/yazim-hatasi eslesmesi (difflib), (4) tek-fazla<->tek-eksik konumsal esleme,
    (5) fazladan anahtarlari at, (6) hala eksik ZORUNLU argümani baglamdan makul varsayilanla doldur.
    """
    names, required = _tool_arg_spec(fn)
    src = dict(raw_args or {})
    if not names:  # sema okunamadi -> oldugu gibi dene
        return src, []
    fixes: List[str] = []
    fixed: dict = {}

    # (1) birebir (buyuk/kucuk harf + bosluk toleransli)
    lowered = {str(k).strip().lower(): k for k in src}
    for n in names:
        k = lowered.get(n.lower())
        if k is not None:
            fixed[n] = src.pop(k)
    remaining = [n for n in names if n not in fixed]

    # (2) anlamsal es-anlamli eslesme
    for k in list(src.keys()):
        if not remaining:
            break
        slot = _arg_slot(str(k))
        if slot is None:
            continue
        target = next((r for r in remaining if _arg_slot(r) == slot), None)
        if target:
            fixed[target] = src.pop(k)
            remaining.remove(target)
            fixes.append(f"'{k}'->'{target}' (anlamsal)")

    # (3) yakin-isim (yazim hatasi) eslesmesi
    for k in list(src.keys()):
        if not remaining:
            break
        m = difflib.get_close_matches(str(k).strip().lower(), [r.lower() for r in remaining],
                                      n=1, cutoff=0.6)
        if m:
            target = next(r for r in remaining if r.lower() == m[0])
            fixed[target] = src.pop(k)
            remaining.remove(target)
            fixes.append(f"'{k}'->'{target}' (yakin-isim)")

    # (4) tek fazla anahtar <-> tek eksik argüman: konumsal esle
    if len(src) == 1 and len(remaining) == 1:
        k = next(iter(src))
        target = remaining[0]
        fixed[target] = src.pop(k)
        remaining.remove(target)
        fixes.append(f"'{k}'->'{target}' (konumsal)")

    # (5) kalan fazladan anahtarlar atilir (pydantic 'extra' hatasini onler)
    for k in src:
        fixes.append(f"fazladan '{k}' atildi")

    # (6) eksik zorunlu argümanlar -> olay baglamindan makul varsayilan
    for n in required:
        v = fixed.get(n)
        if v is None or (isinstance(v, str) and not v.strip()):
            slot = _arg_slot(n) or "metin"
            fixed[n] = ctx.get(slot) or "Bilinmiyor"
            fixes.append(f"eksik '{n}' varsayilanla dolduruldu ('{fixed[n]}')")

    return {k: _stringify(v) for k, v in fixed.items()}, fixes


def _resolve_tool(name: str):
    """Arac adini cozer; birebir yoksa YAKIN-ISIM eslesmesi dener (model 'saglik_ekibi_gonder'
    gibi yakin ama yanlis bir ad uretirse cagri sessizce dusmesin). (arac, cozulen_ad) doner."""
    fn = TOOL_REGISTRY.get(name)
    if fn is not None:
        return fn, name
    if not name:
        return None, name
    m = difflib.get_close_matches(name.strip().lower(),
                                  [n.lower() for n in TOOL_REGISTRY], n=1, cutoff=0.75)
    if m:
        real = next(n for n in TOOL_REGISTRY if n.lower() == m[0])
        return TOOL_REGISTRY[real], real
    return None, name


def _as_args_dict(args) -> dict:
    """Model argümanlari sozluk yerine JSON metni verirse cozer; cozulemezse bos sozluk."""
    if isinstance(args, dict):
        return args
    if isinstance(args, str) and args.strip():
        try:
            parsed = extract_json(args)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def _invoke_tool(fn, name: str, args: dict, ctx: Dict[str, str],
                 call_log: List[dict], trace: List[str]) -> bool:
    """Araci cagirir; pydantic/argüman hatasinda ONARIP TEK KEZ yeniden dener.

    Basarili cagrinin kaydini `call_log`'a ekler (K1: modul-globali degil, act()'e ozel
    YEREL liste -> paralel kosularda karisma yok). Kalici basarisizlikta trace'e NET uyari yazar.
    True/False = cagri gerceklesti mi.
    """
    before = len(get_log())  # baglam-yerel kaydin bu cagridan onceki uzunlugu

    def _capture(result) -> bool:
        entries = list(get_log())[before:]
        if entries:
            call_log.extend(entries)
        else:  # savunmaci: kayit gorulemedi -> cagri yine de kayit disi kalmasin
            call_log.append({"function": name, "args": dict(args), "result": _stringify(result),
                             "ts": datetime.datetime.now().strftime("%H:%M:%S")})
        return True

    try:
        return _capture(fn.invoke(args))
    except Exception as ex:
        fixed, fixes = _repair_args(fn, args, ctx)
        if fixed == args and not fixes:
            trace.append(f"act: UYARI — '{name}' çağrisi basarisiz ve onarilacak argüman "
                         f"bulunamadi; OPERASYONEL ÇAĞRI YAPILAMADI. args={args}, hata={ex}")
            return False
        try:
            ok = _capture(fn.invoke(fixed))
            trace.append(f"act: '{name}' argümanlari onarildi [{'; '.join(fixes) or 'yeniden deneme'}] "
                         f"-> çağri basarili (ilk hata: {ex})")
            return ok
        except Exception as ex2:
            trace.append(f"act: UYARI — '{name}' çağrisi ONARIMA RAĞMEN basarisiz, OPERASYONEL "
                         f"ÇAĞRI YAPILAMADI. ham_args={args}, onarilmis={fixed}, hata={ex2}")
            return False


def act(state: PolicyAgentState) -> dict:
    """Tespit edilen olaylara gore mock operasyonel fonksiyonlari dinamik cagirir."""
    trace = state.get("trace", [])
    reset_log()  # K1: BAGLAM-YEREL kayit (yeni liste atanir; paralel kosular etkilenmez)
    events = state.get("events", [])
    risk = state.get("risk")

    # Dispatch kapisi: operasyonel fonksiyonlar (saglik/guvenlik/acil-durdurma) YALNIZCA gercek
    # yuksek-risk sinyalinde tetiklenir. Normaldeki "Orta" severity halusinasyonlari bos yere
    # ekip cagirmasin -> operasyonel yanlis-pozitif (alarm yorgunlugu) kesilir. (Juri konsensusu)
    max_ev = max((_SEV_ORD.get(e.severity, 0) for e in events), default=0)
    risk_ord = _SEV_ORD.get(risk.level, 0) if risk else 0
    # Dispatch sinyali: normalde grounded olay-severity VEYA risk. AMA risk_recall_bias acikken risk
    # recall-yanli sisirilmis olabilir -> dispatch'i YALNIZ grounded olay-severity'ye bagla (biased-risk
    # operatore Yuksek FLAG verir ama sahte operasyonel-cagri YAPMAZ). Boylece bias risk-kalibrasyonu
    # yukseltirken dispatch HASSAS kalir (Agent-C: recall-yanli alarm + hassas dispatch).
    #
    # POLITIKA HAKEMLIGI (K3 YAPISAL GARANTISI) — UC TERIMLI KAPI:
    #   1) max_intrinsic : politika yukseltmesi OLMASAYDI ki en yuksek olay-severity
    #                      (yani sevk YALNIZ modelin kendi grounded yargisiyla acilir)
    #   2) esc_sevk      : operator hem kural satirinda 'sevk' yetkisi verdiyse HEM DE
    #                      policy_dispatch=True ise politika yukseltmesi sevke yetkilidir (B2 kolu)
    #   3) risk terimi   : risk esigi YALNIZ politika yukseltmesiyle asildiysa MASKELENIR
    #                      (risk tabani severity'yi risk'e tasidigi icin tek basina 1. terimi
    #                       maskelemek YETMEZ; bu maske olmadan policy_dispatch=False yalan olurdu)
    # BOS POLITIKADA CEBIRSEL INDIRGEME (birim testle assert edilir):
    #   recs=[] -> max_intrinsic==max_ev, esc_sevk=False, policy_only=False
    #   => (max_ev>=3) or False or (risk_ord>=3 and not risk_recall_bias and not False)
    #   == (max_ev>=3) or (risk_ord>=3 and not risk_recall_bias)      [eski satirin AYNISI]
    recs = state.get("policy_escalations") or []
    max_intrinsic = state.get("policy_max_intrinsic")
    if max_intrinsic is None:  # kanal yoksa olaylarin policy_prev alanindan turet (ayni deger)
        max_intrinsic = policy.intrinsic_max_ord(events)
    esc_sevk = bool(recs) and settings.policy_dispatch and any(r.get("sevk") for r in recs)
    policy_only = bool(state.get("risk_from_policy_only", False)) or bool(
        getattr(risk, "policy_only", False))
    # KANIT-ADLANDIRMA MASKESI (risk_recall_bias ile AYNI desen, ayni gerekce):
    # kanit sorulari bir olayin ADINI daha belirli/alarmli hale getirdiyse, `reason`
    # bu METNI okuyup riski yukseltebilir. Risk operatore FLAG olarak gosterilebilir ama
    # OPERASYONEL SEVK'i acmamalidir -> risk terimi maskelenir. Sevk boylece yalniz
    # olay-severity'sine (max_intrinsic) baglanir; o da `Event.evidence_prev` muhafizi
    # sayesinde kanit-ONCESI metinle karara baglanmistir. Ozellik kapali/adlandirma
    # yapilmamissa bayrak False -> ifade cebirsel olarak ESKI SATIRIN AYNISIDIR.
    kanit_adli = bool(state.get("evidence_renamed", False))
    dispatch_signal = (
        (max_intrinsic >= _SEV_ORD[Severity.YUKSEK])
        or (esc_sevk and max_ev >= _SEV_ORD[Severity.YUKSEK])
        or (risk_ord >= _SEV_ORD[Severity.YUKSEK] and not settings.risk_recall_bias
            and not policy_only and not kanit_adli)
    )
    if (kanit_adli and risk_ord >= _SEV_ORD[Severity.YUKSEK]
            and max_intrinsic < _SEV_ORD[Severity.YUKSEK] and not esc_sevk):
        trace.append("act: risk terimi MASKELENDI (en az bir olay adi kanit sorulariyla yeniden "
                     "yazildi; risk operatore FLAG olarak gorunur ama SEVK acmaz)")
    if not events or not dispatch_signal:
        if recs:
            trace.append(f"act: politika yukseltmesi var ({len(recs)}) ancak SEVK yolu kapali "
                         f"(policy_dispatch={settings.policy_dispatch}, sevk-yetkili kural="
                         f"{any(r.get('sevk') for r in recs)}); operatör teyidi önerisi aksiyonlarda")
        trace.append("act: yuksek-risk sinyali yok, operasyonel cagri yapilmadi (dispatch kapisi)")
        return {"triggered_functions": [], "action_log": [], "trace": trace}

    # Model cagrilacak fonksiyonlari JSON olarak secer; her birini ilgili mock
    # fonksiyona (LangChain @tool) dispatch ederiz (model-tabanli dinamik secim).
    # K1: cagri kayitlari bu act() cagrisina OZEL yerel listede toplanir -> paralel
    # kosularda (n_samples>1) baska bir kosunun kayitlari buraya karisamaz.
    call_log: List[dict] = []
    ctx = _dispatch_context(events, risk)  # K3: eksik argüman icin olay baglami
    try:
        vlm = _get_vlm()
        risk_line = f"{risk.level.value} - {risk.rationale}" if risk else "Belirsiz"
        instr = prompts.ACTION_DISPATCH_INSTRUCTION.format(
            tools=_tools_description(),
            risk=risk_line,
            events_block=_events_block(events),
        )
        messages = [
            {"role": "system", "content": prompts.SYSTEM_PERSONA},
            {"role": "user", "content": instr},
        ]
        raw = vlm.chat(messages, temperature=0.1, max_tokens=600)
        data = extract_json(raw)
        for call in data.get("calls", []):
            name = str(call.get("function", "")).strip()
            args = _as_args_dict(call.get("args", {}) or {})
            fn, resolved = _resolve_tool(name)
            if fn is None:
                trace.append(f"act: UYARI — bilinmeyen fonksiyon atlandi: '{name}' "
                             f"(kayitli araclar: {list(TOOL_REGISTRY)})")
                continue
            if resolved != name:
                trace.append(f"act: bilinmeyen '{name}' -> yakin-isim '{resolved}' olarak çözüldü")
            _invoke_tool(fn, resolved, args, ctx, call_log, trace)
    except Exception as ex:
        trace.append(f"act: aksiyon seçimi hatasi: {ex}")

    triggered = [str(entry.get("function", "")) for entry in call_log]
    trace.append(f"act: {len(triggered)} operasyonel fonksiyon çağrildi: {triggered}")
    return {"triggered_functions": triggered, "action_log": call_log, "trace": trace}


def finalize(state: AgentState) -> dict:
    trace = state.get("trace", [])
    # K6: dugum-seviyesi hata toleransi. finalize'in `result` DONDURMEMESI cagirani (analyze_video)
    # KeyError ile cokertir; bu yuzden hata halinde en azindan GUVENLI bir AnalysisResult uretilir.
    try:
        info = state.get("video_info")
        result = AnalysisResult(
            summary=state.get("summary", ""),
            events=state.get("events", []),
            risk=state.get("risk") or RiskAssessment(level=Severity.DUSUK, rationale="Olay yok."),
            actions=state.get("actions", []),
            video_duration=info.duration_str if info else None,
            triggered_functions=state.get("triggered_functions", []),
            action_log=state.get("action_log", []),
            decision_trace=state.get("trace", []),
            # Sorgu-gudumlu analiz: sorgu girilmediyse None kalir. SOZLESME KORUNUR —
            # to_sartname_dict() bu alani ICERMEZ (yalniz zengin model_dump()'ta gorunur).
            query_answer=state.get("query_answer"),
        )
        return {"result": result}
    except Exception as ex:
        trace = list(trace) + [f"finalize: dugum hatasi (guvenli varsayilan sonuç uretildi): {ex}"]
        try:
            return {"result": AnalysisResult(
                summary=str(state.get("summary", "") or "Sonuç birleştirilemedi (finalize hatasi)."),
                events=[],
                risk=RiskAssessment(level=Severity.ORTA,
                                    rationale="Sonuç birleştirilemedi; operatör manuel teyidi önerilir."),
                actions=[],
                decision_trace=trace,
            )}
        except Exception:  # son care: sozlesme bozulmasin diye None yerine minimum sonuc
            return {"result": AnalysisResult(
                summary="Sonuç birleştirilemedi.",
                risk=RiskAssessment(level=Severity.ORTA, rationale="Bilinmiyor."),
            )}


def build_graph():
    g = StateGraph(PolicyAgentState)
    g.add_node("ingest", ingest)
    g.add_node("perceive", perceive)
    g.add_node("reexamine", reexamine)
    g.add_node("policy_gate", policy_gate)
    g.add_node("reason", reason)
    g.add_node("act", act)
    g.add_node("finalize", finalize)

    g.add_edge(START, "ingest")
    g.add_edge("ingest", "perceive")
    # Koşullu kenar (adaptif otonomi): belirsiz olay varsa yeniden-incele, yoksa policy_gate.
    # route_after_perceive'in DONUS DEGERLERI DEGISMEDI; yalnizca eslesme tablosu yonlendirir.
    # SIRA GEREKCESI: (1) reexamine "Orta" olaylari ASAGI cekebiliyor -> hakemlik ondan SONRA
    # calisir ki yukseltme geri alinmasin ve rutin bulunan olaylar aday olmasin; (2) _dedupe_events
    # sonrasi aday sayisi kucuk (video basina TEK cagri yeter); (3) policy_gate MUTASYON
    # ZINCIRININ SONU -> policy_ref/policy_prev alanlari sonraki Event(...) kurulumlarinda dusmez.
    g.add_conditional_edges("perceive", route_after_perceive,
                            {"reexamine": "reexamine", "reason": "policy_gate"})
    g.add_edge("reexamine", "policy_gate")
    g.add_edge("policy_gate", "reason")
    g.add_edge("reason", "act")
    g.add_edge("act", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


_GRAPH = None


def _vote(results: List[AnalysisResult]) -> AnalysisResult:
    """Self-consistency: risk seviyesini cogunlukla oyla, temsili kosuyu sec.
    'Hatalar tek calismada olusabilir ama N calisma boyunca tutarli olmaz' ilkesi."""
    from collections import Counter

    results = [r for r in results if r is not None]
    if len(results) == 1:
        return results[0]
    maj = Counter(r.risk.level.value for r in results).most_common(1)[0][0]
    cands = [r for r in results if r.risk.level.value == maj] or results
    # cogunluk-riskli kosular arasinda olay sayisi medyan olani (aykiri kosulari ele) sec
    cands = sorted(cands, key=lambda r: len(r.events))
    return cands[len(cands) // 2]


def analyze_video(video_path: str, n_samples: Optional[int] = None) -> AnalysisResult:
    """Bir videoyu uctan uca analiz edip AnalysisResult dondurur.
    n_samples>1 ise self-consistency: grafik N kez (paralel) calisir, risk oylanir."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    n = n_samples if n_samples is not None else settings.n_samples
    if n <= 1:
        return _GRAPH.invoke({"video_path": video_path, "trace": []})["result"]
    with ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(
            lambda _: _GRAPH.invoke({"video_path": video_path, "trace": []})["result"],
            range(n),
        ))
    return _vote(results)


def analyze_prepared(frames, info, n_samples: Optional[int] = None) -> AnalysisResult:
    """Onceden-cikarilmis (zaman, jpeg) karelerden uctan-uca analiz — DECODE-ONCE (canli akis).

    Videoyu yeniden decode etmez (canli akista mp4 yaz->PyAV-oku gidis-donusunu atlar) -> dusuk gecikme.
    `frames`: video.timedframes_from_bgr ciktisi; `info`: video.build_video_info ciktisi."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    n = n_samples if n_samples is not None else settings.n_samples
    if n <= 1:
        return _GRAPH.invoke({"prebuilt_frames": frames, "prebuilt_info": info, "trace": []})["result"]
    with ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(
            lambda _: _GRAPH.invoke({"prebuilt_frames": frames, "prebuilt_info": info, "trace": []})["result"],
            range(n),
        ))
    return _vote(results)
