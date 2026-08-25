"""Beyan-Bagli Onem Derecesi — politika hakemligi (Declared-Severity Policy Adjudication).

KUSUR #2 (risk yukseltme) COZUMU. Olculen kusur zinciri: model politika-ihlalini GORUYOR ve
DOGRU ADLANDIRIYOR (recall %47, kategori %33) ama ONEM DERECESINI dusuk veriyor (severity=Dusuk
34/47 klip) -> risk tabani Dusuk kaliyor -> sevk kapisi acilmiyor. Prompt-seviyesi severity
talimati DENENDI ve BASARISIZ (10/100, McNemar p=0.267).

BU MODULUN ILKESI (K1 — "statik kural tabanli cozum dusuk puanlanir"):
  * ONEM DERECESI koddan GELMEZ; operatorun BEYAN ETTIGI politikadan gelir (`settings.facility_policy`).
  * OLAY <-> KURAL eslesmesi ANLAMSAL yapilir (MODEL isi) — alt-dizgi/kelime tablosu YOKTUR.
  * Modelden severity ISTENMEZ; severity onun cikti-uzayinda YOKTUR (kanitlanmis basarisizligin
    yapisal panzehri). Model yalnizca "hangi madde, ihlal mi/uygun mu/belirsiz mi, kanit ne" der.
  * Bu dosyada TEK BIR tesise-ozgu terim yoktur (birim testi grep ile sabitler).

DETERMINIZM NEREDE: kural ayristirma, dort kapi (kapsam/kanit/cekince/tavan), tek-yonlu tavan,
yukseltme butcesi ve sevk yetkisi. MODEL NEREDE: yalnizca anlamsal eslesme.

FAIL-CLOSED (yukseltme yonu) + FAIL-OPEN (sistem davranisi): her belirsizlik/ariza modunda
yukseltme YAPILMAZ, olaylar DOKUNULMADAN gecer, akis surer.
"""
from __future__ import annotations

import hashlib
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from dilajan import prompts
from dilajan.schema import Event, EventCategory, Severity

# --- onem derecesi siralamasi (graph.py'dekiyle AYNI; dongusel import olmasin diye yerel) ---
SEV_ORD: Dict[Severity, int] = {
    Severity.DUSUK: 1, Severity.ORTA: 2, Severity.YUKSEK: 3, Severity.KRITIK: 4,
}
ORD_SEV: Dict[int, Severity] = {v: k for k, v in SEV_ORD.items()}


def _norm(s: Optional[str]) -> str:
    """TR-guvenli normalizasyon: NFD -> combining isaretleri at -> casefold.

    NEDEN: `"İşçi".lower()` Python'da 'i' + U+0307 (COMBINING DOT ABOVE) uretir ve ham alt-dizgi
    eslesmesini SESSIZCE bozar (bu projede olculdu: bir kosunun 101 olay metninin 29'unda).
    Bu fonksiyon YALNIZ bu modulun kapilarinda kullanilir; graph.py'deki mevcut regex'lere
    DOKUNULMAZ (o duzeltme AYRI is / AYRI olcum kolu).

    U+0131 KATLAMA (2026-08-25): 'ı' harfinin AYRISIMI YOKTUR, dolayisiyla
    combining-isaret silme onu ASCII 'i'ye cevirmez. Bu, ASCII yazilmis
    kaliplarla eslesmeyi SESSIZCE bozuyordu:
        "ihlal bulunmadı" -> "ihlal bulunmadı"  ama kalip "bulunmadi"
    Olculdu: `_NEG_RE`'nin 17 kolundan 4'u (bulunmadi/saptanmadi/rastlanmadi/
    olmadi) HIC eslesmiyordu; fail-closed olmasi gereken olumsuzlama kapisi
    o kollarda ACIKTI ve "ihlal bulunmadı" IHLAL sayiliyordu.
    Bu yuzden 'ı' artik 'i'ye katlanir. Karsilastirmalarin IKI TARAFI da bu
    fonksiyondan gectigi icin katlama tutarlidir.

    Normalizasyon sonrasi alfabe: YALNIZCA ASCII harfler.

    DAYANIKLILIK: model ciktisindaki bir alan str OLMAYABILIR (sayi, liste, sozluk). Boyle bir
    deger `unicodedata.normalize`i TypeError ile patlatir ve TEK bozuk alan yuzunden TUM
    kararlar dusrdu. Bu yuzden str-disi degerler once metne cevrilir (fail-open ayristirma).
    """
    if s is None:
        _out = ""
    if not isinstance(s, str):
        try:
            s = str(s)
        except Exception:
            return ""
    d = unicodedata.normalize("NFD", s or "")
    stripped = "".join(c for c in d if not unicodedata.combining(c))
    out = unicodedata.normalize("NFC", stripped).casefold()
    # U+0131 ('ı') KATLAMASI — yukaridaki gerekce. Ayrisimi olmadigi icin
    # combining-silme onu birakmisti ve ASCII kaliplarla eslesmiyordu.
    return out.replace("ı", "i")


# Epistemik CEKINCE deseni — DIL duzeyi (alan duzeyi DEGIL; K1 icin onemli ayrim).
# "olabilir / supheli / veya / ya da / gibi" iceren gozlem, kural sozlugunu tasisa bile
# YUKSELTILMEZ: yanlis-pozitif butcesi kazanctan onceliklidir (bilincli asimetri).
_HEDGE_TERMS: Tuple[str, ...] = (
    "suphe", "supheli", "olasi", "olabilir", "ihtimal", "belki", "muhtemel",
    "mis gibi", "gibi hareket", " veya ", " ya da ",
    "possibly", "maybe", "appears", "seems", "likely", "might be",
)
_HEDGE_RE = re.compile("|".join(re.escape(_norm(t)) for t in _HEDGE_TERMS))

#: Anlamli token deseni (normalize edilmis metin uzerinde; harf/rakam dizileri).
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)

#: Kanit alintisinda en az bu kadar anlamli token olmali (ciplak tek-kelime dayanak reddedilir).
_MIN_EVIDENCE_TOKENS = 2
#: Kanit tokenlarinin en az bu orani olay metninde GECMELI (uydurma/parafraz dayanak reddedilir).
_MIN_EVIDENCE_COVERAGE = 0.6
#: Bir kural maddesinin "ihlal" tanimi en az bu kadar normalize karakter olmali.
_MIN_RULE_LEN = 12
#: Bir cagrida hakemlige sunulacak azami aday olay (gecikme tavani).
MAX_CANDIDATES = 12


@dataclass(frozen=True)
class PolicyRule:
    """Operatorun BEYAN ETTIGI tek politika maddesi."""

    rid: str                 # "R1".."Rn"
    ihlal: str               # kurala AYKIRI gorunum (zorunlu)
    uygun: str               # kurala UYGUN gorunum (opsiyonel; "" ise model kural metninden cikarir)
    severity: Severity       # OPERATOR BEYANI (severity buradan gelir, koddan GELMEZ)
    sevk: bool               # bu ihlal otomatik ekip sevkine yetkili mi (ayrica policy_dispatch gerekir)


@dataclass(frozen=True)
class Verdict:
    """Modelin tek bir aday gozlem icin verdigi hakemlik karari."""

    no: int                  # aday sirasi (1 tabanli)
    rid: str                 # "R1".."Rn" veya "R0" (hicbir maddeyi ihlal etmiyor)
    karar: str               # "IHLAL" | "UYGUN" | "BELIRSIZ"
    kanit: str               # gozlem metninden alinti


@dataclass
class Adjudication:
    """`adjudicate()` sonucu (dort alan + teshis sayaclari)."""

    events: List[Event] = field(default_factory=list)
    records: List[dict] = field(default_factory=list)
    trace: List[str] = field(default_factory=list)
    max_intrinsic_ord: int = 0
    stats: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 1) KURAL AYRISTIRMA (deterministik; LLM cagrisi YOK) — sha1 onbellekli
# ---------------------------------------------------------------------------
_RULE_CACHE: Dict[str, List[PolicyRule]] = {}
_RULE_LOCK = threading.Lock()
#: Teshis/birim testi icin: gercekten kac kez AYRISTIRMA yapildi (onbellek isabetleri sayilmaz).
PARSE_STATS: Dict[str, int] = {"parse": 0, "hit": 0}

_SEV_LABELS: Tuple[Tuple[Severity, Tuple[str, ...]], ...] = (
    (Severity.KRITIK, ("kritik", "critical")),
    (Severity.YUKSEK, ("yuksek", "high")),
    (Severity.ORTA, ("orta", "medium")),
    (Severity.DUSUK, ("dusuk", "low")),
)
_SEVK_LABELS: Tuple[str, ...] = ("sevk", "dispatch")


def to_severity(value: Optional[str], default: Severity = Severity.ORTA) -> Severity:
    """Metin etiketini Severity'ye cevirir (TR/EN; taninmazsa `default`)."""
    n = _norm(value)
    if not n:
        return default
    for sev, labels in _SEV_LABELS:
        if any(lbl in n for lbl in labels):
            return sev
    return default


def _severity_field(text: str) -> Optional[Severity]:
    """Alan bir ONEM ETIKETI mi? (evetse Severity, degilse None)"""
    n = _norm(text)
    if not n:
        return None
    for sev, labels in _SEV_LABELS:
        if n in labels:  # TAM eslesme (alt-dizgi degil): "uygun gorunum" alani yanlislikla
            return sev   # onem etiketi sanilmasin
    return None


def _sevk_field(text: str) -> bool:
    """Alan SEVK YETKISI etiketi mi?"""
    return _norm(text) in tuple(_norm(s) for s in _SEVK_LABELS)


def _parse_policy_uncached(raw: str, default_sev: Severity, max_rules: int) -> List[PolicyRule]:
    """Satir bicimini ayristirir (ic fonksiyon; onbelleklenmemis).

    SATIR BICIMI (operator yazar; kodda hicbir ornek/terim GECMEZ)::

        <ihlal tanimi> [| <uygun gorunum>] [| Düşük|Orta|Yüksek|Kritik] [| sevk]

    Ilk alan ZORUNLU (ihlal tanimi). Kalan alanlar SIRALI okunur; ancak bir alan onem
    etiketi ("Yüksek") ya da sevk etiketi ("sevk") olarak TANINIRSA o role atanir —
    boylece "<ihlal> | Yüksek" gibi kisa yazim da dogru ayristirilir (toleransli, hala
    deterministik). Bos satirlar ve '#' ile baslayan yorum satirlari atlanir.
    """
    rules: List[PolicyRule] = []
    for line in (raw or "").splitlines():
        if len(rules) >= max(1, max_rules):
            break
        s = line.strip().lstrip("-•*").strip()
        if not s or s.startswith("#"):
            continue
        parts = [p.strip() for p in s.split("|")]
        ihlal = parts[0]
        if len(_norm(ihlal)) < _MIN_RULE_LEN:
            continue  # cok kisa/anlamsiz madde -> REDDEDILIR (cagiran trace'e not duser)
        uygun = ""
        sev: Optional[Severity] = None
        sevk = False
        for p in parts[1:]:
            if not p:
                continue
            if _sevk_field(p):
                sevk = True
                continue
            maybe = _severity_field(p)
            if maybe is not None:
                sev = maybe
                continue
            if not uygun:
                uygun = p
        rules.append(PolicyRule(rid=f"R{len(rules) + 1}", ihlal=ihlal, uygun=uygun,
                                severity=(sev or default_sev), sevk=sevk))
    return rules


def parse_policy(raw: str, default_sev: Severity, max_rules: int = 8) -> List[PolicyRule]:
    """Beyan edilen politika metnini PolicyRule listesine cevirir (sha1 ONBELLEKLI, thread-guvenli).

    n_samples>1 veya paralel kosularda ayni metin yalniz BIR KEZ ayristirilir.
    Hata halinde bos liste doner (FAIL-OPEN: cagiran hicbir yukseltme yapmaz).
    """
    try:
        text = raw or ""
        key = hashlib.sha1(
            f"{max_rules}|{default_sev.value}|{text}".encode("utf-8", "replace")
        ).hexdigest()
        with _RULE_LOCK:
            hit = _RULE_CACHE.get(key)
            if hit is not None:
                PARSE_STATS["hit"] = PARSE_STATS.get("hit", 0) + 1
                return list(hit)
            rules = _parse_policy_uncached(text, default_sev, max_rules)
            _RULE_CACHE[key] = rules
            PARSE_STATS["parse"] = PARSE_STATS.get("parse", 0) + 1
            return list(rules)
    except Exception:
        return []


def clear_cache() -> None:
    """Kural onbellegini ve sayaclari temizler (yalniz test/teshis amacli)."""
    with _RULE_LOCK:
        _RULE_CACHE.clear()
        PARSE_STATS["parse"] = 0
        PARSE_STATS["hit"] = 0


def rules_summary(rules: Sequence[PolicyRule]) -> str:
    """K5: ayristirilmis kural tablosunu karar-izine yazilacak tek satira doker.

    Operator NE BEYAN ETTIGINI cikti JSON'unda birebir gorur (denetlenebilirlik)."""
    parts = []
    for r in rules:
        excerpt = r.ihlal if len(r.ihlal) <= 60 else r.ihlal[:57] + "..."
        tag = f"beyan={r.severity.value}" + (", sevk" if r.sevk else "")
        parts.append(f'{r.rid} "{excerpt}" ({tag})')
    return f"{len(rules)} kural ayristirildi — " + "; ".join(parts)


def max_declared_ord(rules: Sequence[PolicyRule]) -> int:
    """Beyan edilen en yuksek onem derecesinin ordinali (aday filtresi esigi)."""
    return max((SEV_ORD[r.severity] for r in rules), default=0)


# ---------------------------------------------------------------------------
# 2) ADAY SECIMI (deterministik) — aday yoksa MODEL CAGRISI HIC YAPILMAZ
# ---------------------------------------------------------------------------
def event_key(ev: Event) -> str:
    """Olay icin kararli anahtar (reexamine <-> policy_gate arasinda tasinir)."""
    return f"{ev.time}|{ev.event}"


def candidates(events: Sequence[Event], rules: Sequence[PolicyRule],
               routine: Optional[set] = None,
               limit: int = MAX_CANDIDATES) -> List[Tuple[int, Event]]:
    """Hakemlige sunulacak aday olaylari secer.

    Filtreler (hepsi deterministik):
      * severity BEYAN EDILEN en yuksek dereceden KUCUK olmali (zaten yeterince ciddi olan
        olay sorulmaz -> senaryo setinde ek gecikme SIFIR),
      * kategori NORMAL olmamali (uyum/olagan olaylar bedava elenir),
      * `reexamine` GORSEL olarak "RUTIN" dediyse ADAY ALINMAZ (politika, olculmus bir gorsel
        karari sessizce ezmesin — bedava yanlis-pozitif kapisi).
    """
    thr = max_declared_ord(rules)
    rt = routine or set()
    out: List[Tuple[int, Event]] = []
    for i, e in enumerate(events):
        if SEV_ORD.get(e.severity, 0) >= thr:
            continue
        if e.category == EventCategory.NORMAL:
            continue
        if event_key(e) in rt:
            continue
        out.append((i, e))
        if len(out) >= max(1, limit):
            break
    return out


# ---------------------------------------------------------------------------
# 3) PROMPT + CEVAP AYRISTIRMA
# ---------------------------------------------------------------------------
def build_prompt(rules: Sequence[PolicyRule], cands: Sequence[Tuple[int, Event]]) -> str:
    """Hakemlik promptunu kurar.

    SIRA prefix-cache dostudur: sabit rubrik (prompts.POLICY_ADJUDICATE_INSTRUCTION govdesi)
    ve dagitima ozgu kural blogu BASTA, degisken gozlem listesi SONDA.
    """
    rblock = []
    for r in rules:
        line = f'{r.rid}: "{r.ihlal}"'
        if r.uygun:
            line += f' (uygun görünüm: "{r.uygun}")'
        rblock.append(line)
    obs = [f"{n}) [{e.time}] {e.event}" for n, (_i, e) in enumerate(cands, start=1)]
    return prompts.POLICY_ADJUDICATE_INSTRUCTION.format(
        rules_block="\n".join(rblock), observations="\n".join(obs)
    )


def _norm_rid(raw, rids: set) -> str:
    """Model kural kimligini normalize eder ("r3"/"3"/"R3" -> "R3"). Taninmazsa "R0"."""
    s = _norm(raw).replace(" ", "")
    m = re.search(r"r?(\d+)", s)
    if not m:
        return "R0"
    rid = f"R{int(m.group(1))}"
    if rid == "R0" or rid in rids:
        return rid
    return "R0"  # aralik disi kimlik -> hicbir kurala baglanmaz (FAIL-CLOSED)


#: OLUMSUZLAMA belirtecleri. Model, kapali kumeden ("IHLAL"/"UYGUN"/"BELIRSIZ") SAPIP serbest
#: metin yazabilir; "ihlal yok", "İhlal edilmemiştir", "ihlal tespit edilmedi" gibi ifadeler
#: ham alt-dizgi aramasinda "ihlal" iceriyor diye IHLAL sayilirdi -> YANLIS YUKSELTME.
#: (Adversaryel denetimde FIILEN uretildi: 4 normal olay Düşük->Yüksek yukseldi.)
#: Olumsuzlanmis her ifade BELIRSIZ'e indirgenir (FAIL-CLOSED: yukseltme yok).
#: Desen KARAR SOZCUGUNE BAGLIDIR (serbest olumsuzluk taramasi DEGIL): olumsuzluk eki
#: "ihlal/violation" sozcugunu en fazla bir ara sozcukle takip etmeli. Boylece
#: "ihlal yok" / "ihlal tespit edilmedi" yakalanir, ama "IHLAL (... yok)" bicimindeki
#: parantezli/tireli GEREKCE iceren gecerli bir karar YANLISLIKLA dusurulmez.
_NEG_RE = re.compile(
    r"(?:ihlal|violation)\s*(?:\w+\s+){0,1}"
    # `yok\b` Turkce EKLEMEYI kaciriyordu: "ihlal YOKTUR" en yaygin olumsuz
    # ifade ama "yok" sonrasi kelime siniri YOK -> eslesmiyordu (olculdu).
    # Artik ek alabilir: yok / yoktur / yoksa / yokken.
    r"(?:yok\w*|degil|edilmemis|edilmedi|edilmez|etmemis|etmiyor|etmez|"
    r"bulunmuyor|bulunmadi|bulunmamak|gorulmedi|gorulmemis|saptanmadi|rastlanmadi|"
    r"olmamis|olmadi)"
    r"|\bno\s+violation\b|\bnot\s+a?\s*violation\b|\bnon-?violation\b"
)


def _norm_karar(raw) -> str:
    """Karari kapali kumeye indirger. Taninmayan/celiskili ifade -> BELIRSIZ (FAIL-CLOSED).

    SIRA:
      1) TAM eslesme (modelin sozlesmeye uydugu normal hal) — en ucuz ve en kesin yol.
      2) OLUMSUZLAMA muhafizi — "ihlal yok" gibi serbest metin IHLAL sayilmaz.
      3) alt-dizgi (toleransli) yol; hicbiri tutmazsa BELIRSIZ.
    """
    n = _norm(raw).strip()
    if n in ("ihlal", "violation"):
        return "IHLAL"
    if n in ("uygun", "compliant"):
        return "UYGUN"
    if n in ("belirsiz", "unclear"):
        return "BELIRSIZ"
    if _NEG_RE.search(n):
        return "BELIRSIZ"  # olumsuzlanmis serbest metin -> ASLA yukseltme
    if "uygun" in n:
        return "UYGUN"
    if "belirsiz" in n or "unclear" in n:
        return "BELIRSIZ"
    if "ihlal" in n or "violation" in n:
        return "IHLAL"
    return "BELIRSIZ"


def parse_verdicts(raw: str, n_cand: int, rids: set) -> Dict[int, Verdict]:
    """Model ciktisindan hakemlik kararlarini ayristirir.

    Bozuk JSON / eksik alan / aralik disi sira -> o aday icin KARAR YOK (yukseltme olmaz).

    YINELENEN NUMARA (FAIL-CLOSED): model ayni `no` icin BIRDEN FAZLA karar dondururse
    (cozumleme dongusu / kopyala-yapistir hatasi) o numaranin TUM kararlari ATILIR — "ilk gelen
    kazanir" sessiz bir fail-open'di ve adaya baska bir gozlemin karari baglanabiliyordu.
    Diger adaylarin kararlari ETKILENMEZ (tek bozuk satir tum videoyu cezalandirmasin).
    """
    from dilajan.utils import extract_json  # yerel import: modul saf kalsin

    out: Dict[int, Verdict] = {}
    dup: set = set()
    try:
        data = extract_json(raw)
    except Exception:
        return out
    items = data.get("sonuc") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return out
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            no = int(it.get("no"))
        except Exception:
            continue
        if not (1 <= no <= n_cand):
            continue
        if no in out or no in dup:  # YINELENEN numara -> o adayin karari tamamen dusurulur
            out.pop(no, None)
            dup.add(no)
            continue
        out[no] = Verdict(no=no, rid=_norm_rid(it.get("kural"), rids),
                          karar=_norm_karar(it.get("karar")),
                          kanit=str(it.get("kanit") or "").strip())
    return out


# ---------------------------------------------------------------------------
# 4) DETERMINISTIK KAPILAR
# ---------------------------------------------------------------------------
def hedged(text: str) -> bool:
    """G3: olay metni epistemik CEKINCE tasiyor mu (supheli/olasi/veya/ya da ...)?"""
    return bool(_HEDGE_RE.search(" " + _norm(text) + " "))


def evidence_ok(quote: str, event_text: str) -> bool:
    """G2: kanit alintisi olay metnine DAYANIYOR mu?

    >= 2 anlamli token VE tokenlarin >= %60'i olay metninde gecmeli. Uydurma veya
    asiri-parafraz dayanak REDDEDILIR (ungrounded match filtresi).
    """
    q, e = _norm(quote), _norm(event_text)
    if not q or not e:
        return False
    toks = [t for t in _TOKEN_RE.findall(q) if len(t) >= 3]
    if len(toks) < _MIN_EVIDENCE_TOKENS:
        return False
    hits = sum(1 for t in toks if t in e)
    return (hits / len(toks)) >= _MIN_EVIDENCE_COVERAGE


def _excerpt(text: str, n: int = 72) -> str:
    t = (text or "").replace("\n", " ")
    return t if len(t) <= n else t[: n - 3] + "..."


def adjudicate(events: Sequence[Event], cands: Sequence[Tuple[int, Event]],
               verdicts: Dict[int, Verdict], rules: Sequence[PolicyRule], *,
               accept_hedged: bool = False, max_esc: int = 4) -> Adjudication:
    """SAF fonksiyon: kararlari dort kapidan gecirip severity'yi TEK-YONLU yukseltir.

    KAPILAR (hepsi gecilmeli):
      G1 KAPSAM  : karar == "IHLAL" ve kural R1..Rn icinde  (UYGUN/BELIRSIZ/R0 -> yukseltme yok)
      G2 KANIT   : evidence_ok(kanit, olay metni)
      G3 CEKINCE : accept_hedged veya olay metninde cekince YOK
      G4 TAVAN   : yeni = max(mevcut, beyan);  yalniz yeni > mevcut ise uygulanir
                   (TEK-YONLU: asla dusurmez, beyan edilen dereceyi ASLA asmaz)
      G0 BUTCE   : severity-acigi buyuk olanlar oncelikli, en fazla `max_esc` yukseltme

    Metin / kategori / zaman / bbox / region / end_time DEGISMEZ; YENI OLAY URETILMEZ.
    `max_intrinsic_ord`: yukseltme OLMASAYDI olusacak en yuksek olay-severity ordinali
    (act()'teki uc-terimli sevk cebiri bunu kullanir).
    """
    new_events: List[Event] = list(events)
    records: List[dict] = []
    trace: List[str] = []
    stats: Dict[str, int] = {
        "aday": len(cands), "ihlal": 0, "uygun": 0, "belirsiz": 0, "r0": 0, "karar_yok": 0,
        "red_kapsam": 0, "red_kanit": 0, "red_cekince": 0, "red_tavan": 0, "red_butce": 0,
        "yukseltme": 0,
    }
    by_id = {r.rid: r for r in rules}

    # --- kapilardan gecen adaylari topla (henuz uygulanmadi; butce siralamasi icin) ---
    passed: List[Tuple[int, int, Event, PolicyRule, Verdict]] = []  # (aciklik, idx, ev, kural, karar)
    for no, (idx, ev) in enumerate(cands, start=1):
        v = verdicts.get(no)
        if v is None:
            stats["karar_yok"] += 1
            continue
        if v.karar == "UYGUN":
            stats["uygun"] += 1
        elif v.karar == "BELIRSIZ":
            stats["belirsiz"] += 1
        else:
            stats["ihlal"] += 1
        if v.rid == "R0":
            stats["r0"] += 1
        rule = by_id.get(v.rid)
        # G1 KAPSAM
        if v.karar != "IHLAL" or rule is None:
            stats["red_kapsam"] += 1
            if v.karar == "UYGUN" and rule is not None:
                trace.append(f'policy: [{ev.time}] "{_excerpt(ev.event)}" -> {v.rid} karar=UYGUN '
                             f"-> YUKSELTME YOK (kurala uygun gorunum)")
            continue
        # G2 KANIT
        if not evidence_ok(v.kanit, ev.event):
            stats["red_kanit"] += 1
            trace.append(f'policy: [{ev.time}] "{_excerpt(ev.event)}" -> {v.rid} IHLAL ama KANIT '
                         f'kapisi (dayanak olay metnine oturmuyor: "{_excerpt(v.kanit, 40)}") '
                         f"-> YUKSELTME YOK")
            continue
        # G3 CEKINCE
        if not accept_hedged and hedged(ev.event):
            stats["red_cekince"] += 1
            trace.append(f'policy: [{ev.time}] "{_excerpt(ev.event)}" -> {v.rid} IHLAL ama CEKINCE '
                         f"kapisi (metin kesin degil) -> YUKSELTME YOK")
            continue
        # G4 TAVAN (tek-yonlu)
        cur = SEV_ORD.get(ev.severity, 0)
        target = max(cur, SEV_ORD[rule.severity])
        if target <= cur:
            stats["red_tavan"] += 1
            trace.append(f'policy: [{ev.time}] "{_excerpt(ev.event)}" -> {v.rid} IHLAL ama mevcut '
                         f"onem ({ev.severity.value}) beyan ({rule.severity.value}) kadar veya "
                         f"uzerinde -> YUKSELTME YOK (tek-yonlu)")
            continue
        passed.append((target - cur, idx, ev, rule, v))

    # --- G0 BUTCE: severity-acigi buyuk olanlar oncelikli ---
    passed.sort(key=lambda t: (-t[0], t[1]))
    for rank, (gap, idx, ev, rule, v) in enumerate(passed):
        if rank >= max(0, max_esc):
            stats["red_butce"] += 1
            trace.append(f'policy: [{ev.time}] "{_excerpt(ev.event)}" -> {v.rid} IHLAL ama '
                         f"YUKSELTME BUTCESI doldu (max={max_esc}) -> YUKSELTME YOK")
            continue
        prev = ev.severity
        new_sev = ORD_SEV[SEV_ORD[prev] + gap]
        # model_copy: end_time/bbox/region/kategori/metin KORUNUR (Event(...) yeniden-kurma
        # desenindeki alan-dusurme tuzagina DUSULMEZ). policy_ref/policy_prev aciklanabilirlik
        # icin olaya eklenir; to_sartname_dict/model_dump SOZLESMESI DEGISMEZ (sema alani degil).
        new_events[idx] = ev.model_copy(update={
            "severity": new_sev, "policy_ref": rule.rid, "policy_prev": prev,
            "policy_sevk": rule.sevk,
        })
        records.append({
            "time": ev.time, "event": ev.event, "onceki": prev.value, "yeni": new_sev.value,
            "kural": rule.rid, "kural_metni": rule.ihlal, "kanit": v.kanit, "sevk": rule.sevk,
        })
        stats["yukseltme"] += 1
        trace.append(f'policy: [{ev.time}] "{_excerpt(ev.event)}" -> {rule.rid} karar=IHLAL '
                     f'kanit="{_excerpt(v.kanit, 40)}" -> onem {prev.value}->{new_sev.value} '
                     f"(operator beyani)")

    # yukseltme OLMASAYDI olusacak en yuksek severity (sevk cebiri)
    stats["red"] = (stats["red_kapsam"] + stats["red_kanit"] + stats["red_cekince"]
                    + stats["red_tavan"] + stats["red_butce"] + stats["karar_yok"])
    return Adjudication(events=new_events, records=records, trace=trace,
                        max_intrinsic_ord=intrinsic_max_ord(new_events), stats=stats)


def intrinsic_max_ord(events: Sequence[Event]) -> int:
    """Politika yukseltmesi OLMASAYDI olusacak en yuksek olay-severity ordinali.

    Yukseltilmis olaylarda `policy_prev` (yukseltme oncesi derece) esas alinir. Politika hic
    calismadiysa bu deger max(olay severity) ile BIREBIR aynidir -> sevk cebiri indirgenir.
    """
    return max((SEV_ORD.get(getattr(e, "policy_prev", None) or e.severity, 0) for e in events),
               default=0)


def revert(events: Sequence[Event], keys: set) -> List[Event]:
    """Verilen anahtarlardaki politika yukseltmelerini GERI ALIR (fail-closed yollar icin)."""
    out: List[Event] = []
    for e in events:
        prev = getattr(e, "policy_prev", None)
        if prev is not None and event_key(e) in keys:
            e = e.model_copy(update={"severity": prev, "policy_ref": None,
                                     "policy_prev": None, "policy_sevk": False})
        out.append(e)
    return out


# ---------------------------------------------------------------------------
# 5) OPSIYONEL (VARSAYILAN KAPALI) — karsitsal GORSEL teyit kapisi
# ---------------------------------------------------------------------------
_VERIFY_POS = ('Bu güvenlik kamerası karelerinde şu durum AÇIKÇA görünüyor mu: "{ihlal}"? '
               "Yalnızca EVET veya HAYIR yaz. Emin değilsen HAYIR yaz.")
_VERIFY_NEG = ('Bu güvenlik kamerası karelerinde durum aslında şu KURALA UYGUN hâlde mi: "{uygun}"? '
               "Yalnızca EVET veya HAYIR yaz. Emin değilsen HAYIR yaz.")


def _yes(ans: Optional[str]) -> Optional[bool]:
    a = _norm(ans).strip()
    if a.startswith("evet") or a.startswith("yes"):
        return True
    if a.startswith("hayir") or a.startswith("no"):
        return False
    return None


def verify_with_frames(vlm, frames_for: Callable[[str], Optional[object]],
                      adj: Adjudication, rules: Sequence[PolicyRule]) -> Adjudication:
    """OPT-IN (settings.policy_verify_frames) karsitsal 2/2 gorsel teyit — FAIL-CLOSED.

    Her yukseltme icin IKI karsit soru sorulur (ihlal gorunuyor mu? / aslinda uygun mu?).
    Yalniz "EVET + HAYIR" ikilisi yukseltmeyi AYAKTA tutar; kare yok, hata, belirsiz veya
    celiskili cevap -> yukseltme GERI ALINIR.

    DIKKAT: bu modun yanlis-pozitif ve gecikme profili OLCULMEMISTIR (geri-alma merdiveninin
    3. adimi). Varsayilan KAPALI.
    """
    if not adj.records:
        return adj
    by_id = {r.rid: r for r in rules}
    drop: set = set()
    for rec in list(adj.records):
        rule = by_id.get(rec.get("kural"))
        ok = False
        try:
            frames = frames_for(rec.get("time", ""))
            if frames and rule is not None:
                a = _yes(vlm.analyze_frames(frames, _VERIFY_POS.format(ihlal=rule.ihlal),
                                            temperature=0.0, max_tokens=8))
                uygun = rule.uygun or f"kural gereğine uygun davranış ({rule.ihlal} durumu YOK)"
                b = _yes(vlm.analyze_frames(frames, _VERIFY_NEG.format(uygun=uygun),
                                            temperature=0.0, max_tokens=8))
                ok = (a is True and b is False)
        except Exception:
            ok = False
        if not ok:
            drop.add(f"{rec.get('time')}|{rec.get('event')}")
            adj.records.remove(rec)
            adj.trace.append(f"policy: [{rec.get('time')}] {rec.get('kural')} yukseltmesi GORSEL "
                             f"TEYIT kapisindan gecemedi (2/2 karsitsal, fail-closed) -> geri alindi")
            adj.stats["yukseltme"] = max(0, adj.stats.get("yukseltme", 0) - 1)
            adj.stats["red_gorsel"] = adj.stats.get("red_gorsel", 0) + 1
    if drop:
        adj.events = revert(adj.events, drop)
        adj.max_intrinsic_ord = intrinsic_max_ord(adj.events)
    return adj
