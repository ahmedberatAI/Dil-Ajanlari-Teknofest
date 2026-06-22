"""LangGraph ajan grafigi.

Akis:  ingest -> perceive -> reason -> act -> finalize

- ingest   : videoyu zaman damgali kare segmentlerine ayirir
- perceive : her segmenti VLM ile analiz eder, olaylari toplar (coklu-adim algi)
- reason   : olaylar uzerinden Turkce ozet + risk + aksiyon onerileri uretir
- act      : tespit edilen olaylara gore mock operasyonel fonksiyonlari DINAMIK
             secip cagirir (native tool-calling = ajanin araclari)
- finalize : AnalysisResult'i birlestirir

Her dugum hata toleranslidir; bir adim hata verirse akis cokmek yerine devam eder.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Tuple

from langgraph.graph import END, START, StateGraph

from dilajan import prompts
from dilajan.agent.state import AgentState
from dilajan.config import settings
from dilajan.llm_client import VLMClient
from dilajan.mock_functions import ALL_TOOLS, OPERATION_LOG, TOOL_REGISTRY, reset_log
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
def ingest(state: AgentState) -> dict:
    trace = state.get("trace", [])
    try:
        frames, info = extract_timestamped_frames(state["video_path"])
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


def _perceive_single_pass(vlm: VLMClient, seg) -> Tuple[List[Event], Optional[str]]:
    """Hizli mod: segment basina TEK VLM cagrisi (describe+extract birlesik).
    verify/grounding YOK -> dusuk gecikme. (olaylar, hata_notu) doner."""
    try:
        instr = prompts.SEGMENT_FAST_INSTRUCTION.format(start=seg.start_str, end=seg.end_str)
        if settings.facility_rules:
            instr += (f"\n\nBu tesisin güvenlik kuralları: {settings.facility_rules}. "
                      "Bu kurallara açıkça aykırı durumları da sapma/olay olarak raporla.")
        raw = vlm.analyze_frames(seg.frames, instr, temperature=0.2, max_tokens=400,
                                 repetition_penalty=settings.perceive_repetition_penalty)
        return _events_from_extraction(extract_json(raw), seg), None
    except Exception as ex:
        return [], f"perceive(fast): segment {seg.index} hatasi: {ex}"


def _analyze_one_segment(vlm: VLMClient, seg) -> Tuple[List[Event], Optional[str]]:
    """Tek segment icin iki asamali algi: serbest tarif -> olay cikarimi.
    (olaylar, hata_notu) doner; hata olursa olaylar boş + not döner (toleransli)."""
    if settings.single_pass_perceive:
        return _perceive_single_pass(vlm, seg)
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
        desc = vlm.analyze_frames(
            seg.frames, instr, temperature=0.2, max_tokens=400,
            repetition_penalty=settings.perceive_repetition_penalty,
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
            verified: List[Event] = []
            for ev in out:
                if _SEV_ORD[ev.severity] >= _SEV_ORD[Severity.YUKSEK] and not _verify_event(vlm, seg.frames, ev.event):
                    ev = Event(time=ev.time, event=ev.event, severity=Severity.ORTA, category=ev.category)
                verified.append(ev)
            out = verified
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
        return out, None
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
                        kept[-1] = Event(time=t0, end_time=(t1 if t1 != t0 else None),
                                         event=better, severity=sev, category=k.category,
                                         bbox=k.bbox or e.bbox, region=k.region or e.region)
                        continue
        kept.append(e)
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
    return kept, note


def perceive(state: AgentState) -> dict:
    """Iki asamali algi (serbest tarif -> olay cikarimi), segmentler PARALEL islenir.
    event_consistency_n>1 ise her segment N kez algılanır ve olaylar çoğunluk-oyuyla süzülür
    (halüsinasyon-azaltma). vLLM eszamanli istekleri batch'ledigi icin paralel calisir."""
    trace = state.get("trace", [])
    vlm = _get_vlm()
    segments = list(state.get("segments", []))
    events: List[Event] = []
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
    return {"events": events, "trace": trace}


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


def reexamine(state: AgentState) -> dict:
    """Belirsiz (Orta) olaylari segment kareleriyle odakli yeniden-degerlendirir:
    RUTIN -> Düşük (FP azalt), CIDDI -> Yüksek (ince gerçek olayi yakala), BELIRSIZ -> korur."""
    trace = state.get("trace", [])
    events = list(state.get("events", []))
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
        try:
            ans = (vlm.analyze_frames(seg.frames, _REEX_PROMPT.format(event=ev.event),
                                      temperature=0.0, max_tokens=20) or "").upper()
        except Exception:
            new_events.append(ev)
            continue
        if "RUTIN" in ans:
            new_events.append(Event(time=ev.time, end_time=ev.end_time, event=ev.event,
                                    severity=Severity.DUSUK, category=ev.category, bbox=ev.bbox, region=ev.region))
            n_down += 1
        elif "CIDDI" in ans:
            new_events.append(Event(time=ev.time, end_time=ev.end_time, event=ev.event,
                                    severity=Severity.YUKSEK, category=ev.category, bbox=ev.bbox, region=ev.region))
            n_up += 1
        else:
            new_events.append(ev)
    trace.append(f"reexamine: belirsiz olaylar yeniden-incelendi (↑{n_up} ciddi, ↓{n_down} rutin)")
    return {"events": new_events, "reexamined": True, "trace": trace}


def reason(state: AgentState) -> dict:
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
    messages = [
        {"role": "system", "content": prompts.SYSTEM_PERSONA},
        {"role": "user", "content": instr},
    ]
    summary = "Özet üretilemedi."
    risk = RiskAssessment(level=Severity.ORTA, rationale="Belirlenemedi.")
    actions: List[Action] = []
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
    except Exception as ex:
        trace.append(f"reason: hata: {ex}")

    # Risk tabani (guardrail): gercek tehdidi dusuk gostermeyi onle.
    # Risk, tespit edilen en yuksek olay severity'sinden dusuk olamaz.
    if events:
        max_ev = max(_SEV_ORD[e.severity] for e in events)
        if _SEV_ORD[risk.level] < max_ev:
            bumped = _ORD_SEV[max_ev]
            trace.append(f"reason: risk tabani uygulandi {risk.level.value}->{bumped.value}")
            risk = RiskAssessment(level=bumped, rationale=risk.rationale)

    # G12 dil-safligi guard: Turkce-disi karakter sizdiysa ozet/gerekce/aksiyonlari duzelt (temizse no-op)
    if _has_foreign(summary) or _has_foreign(risk.rationale) or any(_has_foreign(a.action) for a in actions):
        summary = _purify(vlm, summary)
        risk = RiskAssessment(level=risk.level, rationale=_purify(vlm, risk.rationale))
        actions = [Action(action=_purify(vlm, a.action), priority=a.priority,
                          rationale=(_purify(vlm, a.rationale) if a.rationale else a.rationale))
                   for a in actions]
        trace.append("reason: dil-safligi guard uygulandi (Türkçe-disi karakter düzeltildi)")

    trace.append(f"reason: risk={risk.level.value}, {len(actions)} aksiyon önerisi")
    return {"summary": summary, "risk": risk, "actions": actions, "trace": trace}


def act(state: AgentState) -> dict:
    """Tespit edilen olaylara gore mock operasyonel fonksiyonlari dinamik cagirir."""
    trace = state.get("trace", [])
    reset_log()
    events = state.get("events", [])
    risk = state.get("risk")

    # Dispatch kapisi: operasyonel fonksiyonlar (saglik/guvenlik/acil-durdurma) YALNIZCA gercek
    # yuksek-risk sinyalinde tetiklenir. Normaldeki "Orta" severity halusinasyonlari bos yere
    # ekip cagirmasin -> operasyonel yanlis-pozitif (alarm yorgunlugu) kesilir. (Juri konsensusu)
    max_ev = max((_SEV_ORD[e.severity] for e in events), default=0)
    risk_ord = _SEV_ORD.get(risk.level, 0) if risk else 0
    if not events or (max_ev < _SEV_ORD[Severity.YUKSEK] and risk_ord < _SEV_ORD[Severity.YUKSEK]):
        trace.append("act: yuksek-risk sinyali yok, operasyonel cagri yapilmadi (dispatch kapisi)")
        return {"triggered_functions": [], "action_log": [], "trace": trace}

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
    # Model cagrilacak fonksiyonlari JSON olarak secer; her birini ilgili mock
    # fonksiyona (LangChain @tool) dispatch ederiz (model-tabanli dinamik secim).
    try:
        raw = vlm.chat(messages, temperature=0.1, max_tokens=600)
        data = extract_json(raw)
        for call in data.get("calls", []):
            name = str(call.get("function", "")).strip()
            args = call.get("args", {}) or {}
            fn = TOOL_REGISTRY.get(name)
            if fn is None:
                trace.append(f"act: bilinmeyen fonksiyon atlandi: {name}")
                continue
            try:
                fn.invoke(args)
            except Exception as ex:
                trace.append(f"act: {name} çağrisi hatasi: {ex}")
    except Exception as ex:
        trace.append(f"act: aksiyon seçimi hatasi: {ex}")

    triggered = [entry["function"] for entry in OPERATION_LOG]
    trace.append(f"act: {len(triggered)} operasyonel fonksiyon çağrildi: {triggered}")
    return {"triggered_functions": triggered, "action_log": list(OPERATION_LOG), "trace": trace}


def finalize(state: AgentState) -> dict:
    info = state.get("video_info")
    result = AnalysisResult(
        summary=state.get("summary", ""),
        events=state.get("events", []),
        risk=state.get("risk") or RiskAssessment(level=Severity.DUSUK, rationale="Olay yok."),
        actions=state.get("actions", []),
        video_duration=info.duration_str if info else None,
        triggered_functions=state.get("triggered_functions", []),
    )
    return {"result": result}


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("ingest", ingest)
    g.add_node("perceive", perceive)
    g.add_node("reexamine", reexamine)
    g.add_node("reason", reason)
    g.add_node("act", act)
    g.add_node("finalize", finalize)

    g.add_edge(START, "ingest")
    g.add_edge("ingest", "perceive")
    # Koşullu kenar (adaptif otonomi): belirsiz olay varsa yeniden-incele, yoksa reason
    g.add_conditional_edges("perceive", route_after_perceive,
                            {"reexamine": "reexamine", "reason": "reason"})
    g.add_edge("reexamine", "reason")
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
