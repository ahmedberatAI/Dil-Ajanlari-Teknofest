"""Yerel vLLM (OpenAI uyumlu) sunucusuna multimodal istemci.

VLM cagrilari icin OpenAI SDK kullanilir; orkestrasyon LangGraph tarafindadir.

MOCK (modelsiz) MOD — `settings.mock_mode` (env: DILAJAN_MOCK=1), VARSAYILAN KAPALI:
    Acikken bu istemci HICBIR AG CAGRISI YAPMAZ; prompt turunu taniyip DETERMINISTIK sahte
    yanit uretir (dosyanin sonundaki "MOCK MOTORU" bolumu). Boylece GPU/vLLM olmayan bir
    makinede TUM LangGraph akisi ve Gradio arayuzu uctan uca calisir.
    GERCEK YOL DEGISMEZ: mock kontrolu chat() / analyze_frames() / health_check() basinda
    tek bir erken-donus `if`tir; kapaliyken kod yolu bit-bit ayni kalir.
    DURUSTLUK: uretilen ozet MOCK_TAG ("[MOCK]") ile damgalanir ve ilk kullanimda stderr'e
    buyuk bir uyari basilir -> mock ciktisi gercek olcum sanilamaz.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import sys
import threading
from typing import Dict, List, Optional, Sequence, Tuple

from openai import OpenAI

from dilajan.config import settings
from dilajan.prompts import SYSTEM_PERSONA

# (zaman_damgasi, jpeg_bytes)
Frame = Tuple[str, bytes]


def _frames_to_mp4(frames: Sequence[Frame], fps: int = 2) -> bytes:
    """JPEG karelerini bellek-ici bir MP4'e kodlar (EVS video-path icin). PyAV; libx264->mpeg4 fallback."""
    import av  # lazy: yalniz video-path'te gerekli
    import numpy as np
    from PIL import Image

    first = Image.open(io.BytesIO(frames[0][1])).convert("RGB")
    w, h = first.size
    w -= w % 2; h -= h % 2  # x264 cift-boyut sarti
    buf = io.BytesIO()
    cont = av.open(buf, mode="w", format="mp4")
    try:
        stream = cont.add_stream("libx264", rate=fps)
    except Exception:
        stream = cont.add_stream("mpeg4", rate=fps)
    stream.width, stream.height, stream.pix_fmt = w, h, "yuv420p"
    for _, jpeg in frames:
        img = Image.open(io.BytesIO(jpeg)).convert("RGB").resize((w, h))
        for pkt in stream.encode(av.VideoFrame.from_ndarray(np.array(img), format="rgb24")):
            cont.mux(pkt)
    for pkt in stream.encode():
        cont.mux(pkt)
    cont.close()
    return buf.getvalue()


class VLMClient:
    """Qwen2.5-VL gibi bir görsel-dil modeline yerel istemci."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.client = OpenAI(
            base_url=base_url or settings.base_url,
            api_key=api_key or settings.etkin_api_key,
            timeout=settings.etkin_timeout,
        )
        self.model = model or settings.model_name
        #: D42 — son chat() cagrisinin token kullanimi (olcum icin; yoksa None).
        self.son_kullanim: Optional[Dict[str, int]] = None


    # --- SERVIS DAYANIKLILIGI ------------------------------------------------
    #: son `chat()` cagrisinda kac kez yeniden denendi (olcum/karar-izi icin)
    son_deneme_sayisi: int = 0

    @staticmethod
    def _gecici_hata_mi(e: Exception) -> bool:
        """Hata GECICI mi (yeniden denemeye deger mi)?

        EVET: 5xx, 429, zaman asimi, baglanti kopmasi — servis mesgul/dusuk.
        HAYIR: 4xx (400/401/404) — ISTEK yanlistir. Ornegin `vlm` aliasi
        goruntu kabul etmez ve 400 doner; tekrarlamak yalnizca gecikme ekler.
        """
        ad = type(e).__name__
        if ad in ("APITimeoutError", "APIConnectionError", "RateLimitError",
                  "InternalServerError", "APIStatusError"):
            kod = getattr(e, "status_code", None)
            if kod is None:
                return ad != "APIStatusError"       # timeout/baglanti -> gecici
            return kod == 429 or 500 <= int(kod) < 600
        # istemci disi (or. httpx okuma hatasi) — metne bak, temkinli davran
        m = str(e).lower()
        return any(x in m for x in ("timeout", "temporarily", "bad gateway",
                                    "service unavailable", "connection reset",
                                    "502", "503", "504"))

    def _cagir_yeniden_denemeli(self, kwargs: dict):
        """`chat.completions.create` — gecici hatalarda ustel geri cekilmeyle tekrar.

        Jitter VAR: tum isciler ayni anda yeniden denerse servis tekrar cokerdi
        (olcumlerimiz 4 paralel iscide kosuyor).
        """
        import random as _rnd
        import time as _t
        n = max(0, int(getattr(settings, "yeniden_deneme", 0)))
        bekle = float(getattr(settings, "yeniden_deneme_bekleme", 1.5))
        self.son_deneme_sayisi = 0
        son = None
        for deneme in range(n + 1):
            try:
                return self.client.chat.completions.create(**kwargs)
            except Exception as e:                      # noqa: BLE001
                son = e
                if deneme >= n or not self._gecici_hata_mi(e):
                    raise
                self.son_deneme_sayisi = deneme + 1
                _t.sleep(bekle * (2 ** deneme) * (0.75 + 0.5 * _rnd.random()))
        raise son                                        # pragma: no cover

    # --- dusuk seviyeli ---
    @staticmethod
    def _to_data_url(jpeg_bytes: bytes) -> str:
        b64 = base64.b64encode(jpeg_bytes).decode()
        return f"data:image/jpeg;base64,{b64}"

    def chat(
        self,
        messages: list,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        repetition_penalty: Optional[float] = None,
        guided_choice: Optional[Sequence[str]] = None,
        json_schema: Optional[Dict] = None,
        schema_name: str = "cikti",
        logprobs: bool = False,
        top_logprobs: int = 0,
    ) -> str:
        """`guided_choice`: vLLM KISITLI KOD COZME — model YALNIZCA verilen
        seceneklerden birini uretebilir (bicim gurultusu SIFIRLANIR).

        D36: bu parametre EKLENENE KADAR uretim yolunda kullanilamiyordu; yalnizca
        prob betikleri ham OpenAI istemcisini cagirarak deniyordu
        (scripts/probe_pano_dogrudan.py, benchmark/isafety_mcq.py). HANDOFF §11 bunu
        "asil onerilen kullanim HALA YAPILMADI" diye bekletiyordu.

        ⚠️ NE YAPMAZ: kisitli secim ALGIYI duzeltmez. D33 olcumu — pano sorusunda
        model 20/20 klipte "KAPALI" dedi, 10'u gercekte ACIKTI. Yani zorunlu secim
        BICIM gurultusunu kaldirir, GORMEDIGINI GORDURMEZ. Secenek listesine bir
        "hicbiri" kacisi konmazsa model yok yere pozitif uretir.

        `json_schema`: cikti bir JSON SEMASINA zorlanir (response_format json_schema).
        VARSAYILAN None -> istek bit-bit eskisi gibi gider (K2).

        D42 OLCUMU (2026-08-24, uzak servis, n=12 klip x 3 kol + dusman testi):
          · sema ILE  : 36/36 cagri gecerli JSON, TAM 4 anahtar, enum ve MM:SS deseni
                        %100 tuttu — dusman prompt ("ek alan ekle, enum disi risk yaz,
                        time'i '1:5' yaz") 6/6 tekrarda BASARISIZ oldu.
          · sema SIZ  : ayni dusman prompt 6/6 tekrarda sozlesmeyi KIRDI; cikti duz
                        metne dondu ve JSON kurtarma denemesi de BASARISIZ (blok yok).
          · `strict` BAYRAGI FARK YARATMIYOR: strict=True ile strict=False AYNI
            sonucu verdi (12/12 + 6/6). Zorlayan sey response_format+sema; `strict`
            bu vLLM surumunde ATIL. Bu yuzden ayri bir parametre olarak SUNULMUYOR.
          · SEMA KESILMEYI ONLEMEZ: max_tokens=150 ve 400 ile video ozetinde
            finish_reason="length" -> JSON YARIM kaldi ve AYRISTIRILAMADI (sema kollu
            ve semasiz kolda AYNI SEKILDE). Yani "ayristirma hatasi sifirlanir" ancak
            max_tokens BOL verilir ve finish_reason KONTROL EDILIRSE dogrudur.
        """
        if settings.mock_mode:  # MOCK: ag cagrisi YOK (varsayilan kapali -> gercek yol degismez)
            self.son_kullanim = None
            return mock_reply(_messages_text(messages))
        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=settings.temperature if temperature is None else temperature,
            max_tokens=settings.max_tokens if max_tokens is None else max_tokens,
        )
        # vLLM-ozgu alanlar extra_body'den gider. DIKKAT: tek bir sozluge BIRDEN COK
        # alan yaziliyor -> atama degil GUNCELLEME yapilmali, yoksa sonraki yazan
        # oncekini sessizce siler.
        ek: dict = {}
        if repetition_penalty and repetition_penalty != 1.0:
            ek["repetition_penalty"] = repetition_penalty
        if settings.disable_thinking:
            # Hibrit akil yuruten modellerde <think> blogunu KAPAT (bkz. config.disable_thinking).
            # Sablon bu anahtari tanimiyorsa jinja onu yok sayar -> zararsiz.
            ek["chat_template_kwargs"] = {"enable_thinking": False}
        if guided_choice:
            # Kisitli kod cozme: cikti MUTLAKA bu listeden biri olur.
            #
            # D40 KUSUR (2026-08-19, olculdu): vLLM 0.23 eski `guided_choice`
            # alanini SESSIZCE YOK SAYIYOR — hata vermiyor, sadece serbest metin
            # donduruyor. Ayni istegin guided ACIK ve KAPALI ciktilari BIREBIR AYNI
            # cikti. Dogru alan `structured_outputs: {"choice": [...]}`.
            # Denenen varyantlar:
            #   guided_choice              -> serbest metin  (atil)
            #   guided_decoding.choice     -> serbest metin  (atil)
            #   response_format json_schema-> tirnakli '"X"' (calisir ama kirli)
            #   structured_outputs.choice  -> 'X'            <- DOGRUSU
            # ETKI: bu alani kullanan TUM eski olcumler (D33 pano probu,
            # D37 yapilandirilmis prompt probu) kisitsiz kosmustur.
            ek["structured_outputs"] = {"choice": list(guided_choice)}
        if json_schema:
            # Sema zorlamasi: cikti MUTLAKA bu semaya uyar (bkz. docstring D42 olcumu).
            # `strict` bayragi bu serviste ATIL oldugu icin GONDERILMIYOR — zorlamayi
            # response_format+sema yapiyor.
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": json_schema},
            }
        if logprobs:
            # KISITLI COZME + LOGPROB BIRLIKTE CALISIYOR (2026-08-25 sondasi).
            # Yanit govdesinde maskelenmis tokenlar -9999.0 ile gelir; izinli
            # secenekler GERCEK logprob tasir. Yani TEK ileri gecisten, EK
            # MALIYET OLMADAN, izinli cevap kumesi uzerinde tam bir olasilik
            # dagilimi okunabilir.
            #
            # §8'DE REDDEDILEN "self-consistency" ILE ALAKASI YOK: orada AYNI
            # girdi N KEZ sorulup oylaniyordu ve model deterministik oldugu icin
            # ornekler OZDES cikiyordu (bilgi eklemiyordu). Burada ek ornek YOK;
            # zaten yapilan tek gecisin KENDI dagilimi okunuyor.
            kwargs["logprobs"] = True
            kwargs["top_logprobs"] = int(top_logprobs or 20)
        if ek:
            kwargs["extra_body"] = ek
        resp = self._cagir_yeniden_denemeli(kwargs)
        # Son cagrinin ILK TOKEN dagilimi (istenmisse). Donus tipi DEGISMEZ.
        self.son_logprob = None
        if logprobs:
            try:
                lp = resp.choices[0].logprobs
                t0 = (getattr(lp, "content", None) or [None])[0]
                if t0 is not None:
                    self.son_logprob = {
                        "secilen": t0.token,
                        "ust": {x.token: x.logprob for x in (t0.top_logprobs or [])},
                    }
            except Exception:
                self.son_logprob = None
        # D42: son cagrinin token kullanimi OLCUM icin saklanir (donus tipi DEGISMEZ ->
        # tum mevcut cagrilar birebir ayni calisir). Servis usage dondurmezse None.
        try:
            u = getattr(resp, "usage", None)
            self.son_kullanim = (
                {"giris": u.prompt_tokens, "cikis": u.completion_tokens,
                 "toplam": u.total_tokens} if u else None
            )
        except Exception:
            self.son_kullanim = None
        return resp.choices[0].message.content or ""

    # --- yuksek seviyeli ---
    def analyze_frames(
        self,
        frames: Sequence[Frame],
        instruction: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        repetition_penalty: Optional[float] = None,
        as_video: bool = False,
        system: Optional[str] = None,
        guided_choice: Optional[Sequence[str]] = None,
    ) -> str:
        """Zaman damgali kareleri + bir talimati VLM'e gönderir, metin yanit döndürür.
        as_video=True: kareleri tek VIDEO olarak gonderir (EVS temporal-token budama + MRoPE; latency).
        FAIL-OPEN: video kodlama/gonderim hata verirse image-path'e duser.

        D37 — SISTEM/KULLANICI PROMPT AYRIMI (mentor onerisi):
        `system` eskiden SABIT `SYSTEM_PERSONA` idi ve goreve gore degistirilemiyordu.
        Artik parametre; VARSAYILAN None -> SYSTEM_PERSONA (K2: mevcut cagrilarin
        davranisi BIREBIR ayni). Yapilandirilmis siniflandirma gibi gorevler kendi
        dar sistem promptunu verebilir — genel persona o gorevde gurultu yapar
        ("fabrika VARSAYMA" gibi kurallar ISG siniflandirmasinda ters calisir).

        `guided_choice`: kisitli kod cozme — cikti MUTLAKA listeden biri olur.
        Bicim gurultusunu sifirlar ama ALGIYI DUZELTMEZ (bkz. chat() docstring).
        """
        sistem = system if system is not None else SYSTEM_PERSONA
        if settings.mock_mode:  # MOCK: kare/mp4 kodlamasi ve ag cagrisi YOK; tohum karelerden gelir
            return mock_reply(instruction, frames=frames)
        content: List[dict] = []
        # D41 — UZAK SERVISTE VIDEO YOLU ZORUNLU.
        # Servis istek basina EN FAZLA 2 GORUNTU kabul ediyor (olculdu: 8 kare -> HTTP 400
        # "At most 2 image(s) may be provided in one prompt"; vlm ise 0 goruntu).
        # Bizim boru hattimiz 8-12 kare gonderiyor -> uzak serviste HER KLIPTE patlardi.
        # Bu yuzden uzak API aktifken kare yolu KULLANILMAZ, kareler mp4'e kodlanip
        # video olarak gonderilir. Yerelde davranis DEGISMEZ (K2).
        _zorunlu_video = False
        try:
            _zorunlu_video = settings.uzak_api_mi and len(frames) > 2
        except Exception:
            pass
        if (as_video or _zorunlu_video) and len(frames) >= 2:
            try:
                mp4 = _frames_to_mp4(frames)
                url = "data:video/mp4;base64," + base64.b64encode(mp4).decode()
                content.append({"type": "video_url", "video_url": {"url": url}})
                content.append({"type": "text", "text": instruction})
                return self.chat([
                    {"role": "system", "content": sistem},
                    {"role": "user", "content": content},
                ], temperature=temperature, max_tokens=max_tokens,
                    repetition_penalty=repetition_penalty, guided_choice=guided_choice)
            except Exception:
                # Uzak serviste image-path'e dusmek ANLAMSIZ: 3+ goruntu yine 400 verir.
                # Yalnizca YEREL sunucuda geri dusulur.
                if _zorunlu_video:
                    raise
                content = []  # image-path'e fail-open (yalniz yerel)
        for ts, jpeg in frames:
            content.append({"type": "text", "text": f"[Kare zamanı: {ts}]"})
            content.append(
                {"type": "image_url", "image_url": {"url": self._to_data_url(jpeg)}}
            )
        content.append({"type": "text", "text": instruction})

        messages = [
            {"role": "system", "content": sistem},
            {"role": "user", "content": content},
        ]
        return self.chat(messages, temperature=temperature, max_tokens=max_tokens,
                         repetition_penalty=repetition_penalty,
                         guided_choice=guided_choice)

    def model_ile(self, ad: Optional[str]) -> "VLMClient":
        """Ayni baglantiyi paylasan, VERILEN MODEL ADINA bakan hafif gorunum.

        `ad` bos/None ise KENDINI dondurur (cagiran taraf kosul yazmasin).
        Yeni HTTP baglantisi ACILMAZ — `self.client` paylasilir.

        D42: alias A/B olcumleri (ornegin diyalog kolunda llm-large vs llm-fast vs
        router) icin gerekli. `gorev()` gorev ADINDAN modele cozer; bu ise MODEL
        ADINI dogrudan alir, dolayisiyla olcum betikleri settings'i degistirmeden
        kol degistirebilir.
        """
        ad = (ad or "").strip()
        if not ad or ad == self.model:
            return self
        yeni = object.__new__(VLMClient)
        yeni.__dict__.update(self.__dict__)
        yeni.model = ad
        return yeni

    def gorev(self, gorev: str) -> "VLMClient":
        """Ayni baglantiyi paylasan, FARKLI MODELE bakan hafif bir gorunum.

        D41: uzak serviste 10 alias acik; her boru hatti asamasi kendi modelini
        kullanabilir. Yeni HTTP baglantisi ACILMAZ — `self.client` paylasilir.
        """
        return self.model_ile(settings.gorev_modeli(gorev))

    def video_oturumu(self, video: "str | bytes", system: Optional[str] = None,
                      giris_metni: str = "Bu videoyu inceleyeceğiz."):
        """Videoyu BIR KEZ kodlayip ustune COK SORU sormak icin oturum acar.

        D41 — EVREN servisi olculdu: ilk yukleme 17,8 s, sonraki sorular
        4,7 -> 4,1 -> 3,7 s = **4,8x hizlanma**. Kosul: ON-EK ONBELLEGININ
        isabet etmesi icin AYNI KODLANMIS NESNE tekrar kullanilmalidir.
        Video her soru icin yeniden okunup kodlanirsa baytlar degisir ve
        onbellek ISABET ETMEZ (dokumantasyon s.56).

        Bu, bizim islemsel-soru mimarimize birebir oturur: "catalda kac kasa?",
        "panoda koyu oyuk var mi?", "yelek var mi?" — hepsi ayni video uzerine.
        """
        return _VideoOturumu(self, video, system=system, giris_metni=giris_metni)

    def health_check(self) -> bool:
        """Sunucu ayakta ve model yüklü mü?

        MOCK modda True doner (arayuz "model çevrimiçi" gosterir) — ancak uretilen her ozet
        MOCK_TAG ile damgalidir ve ilk kullanimda stderr'e buyuk uyari basilir."""
        if settings.mock_mode:  # MOCK: sunucu yok ama pipeline/arayuz calisabilir
            _mock_warn_once()
            return True
        try:
            models = self.client.models.list()
            return any(m.id == self.model for m in models.data)
        except Exception:
            return False


# ===========================================================================
# MOCK MOTORU (modelsiz mod) — `settings.mock_mode` / DILAJAN_MOCK=1
# ===========================================================================
# NEDEN: takimin GPU'su/WSL'i olmayan uyeleri de TUM pipeline'i (LangGraph dugumleri,
# dedup, risk tabani, dispatch kapisi) ve Gradio arayuzunu uctan uca calistirabilsin.
#
# ILKELER
#   1) SIFIR AG CAGRISI — mock yolunda OpenAI istemcisine HIC dokunulmaz.
#   2) DETERMINIZM      — cikti YALNIZ (prompt metni + kare baytlari) hash'inden turer;
#                         ayni video/prompt -> HER ZAMAN ayni cikti (tekrarlanabilir demo).
#   3) SOZLESME UYUMU   — her prompt turu, pipeline'in o adimda BEKLEDIGI bicimde yanit alir;
#                         taninmayan prompt -> guvenli, sema-uyumlu BOS yanit.
#   4) DURUSTLUK        — ozet MOCK_TAG ile damgalanir + ilk kullanimda stderr'e buyuk uyari.
#                         Mock ciktisi OLCUM/BENCHMARK/DEGERLENDIRME icin KULLANILAMAZ.
#
# NOT (benchmark/eval_clips.py): o dosya bu degisikligin kapsaminda DEGIL ve mock modu ayrica
# denetlemez. Mock ile kosturulursa (a) stderr'deki buyuk uyari ve (b) her ozetteki "[MOCK]"
# damgasi sonucun gercek olmadigini gosterir — raporlanan sayilar GECERSIZDIR.

#: Sahte ciktilarin damgasi (ozet basina eklenir; risk gerekcesinde de gecer).
MOCK_TAG = "[MOCK]"

_MOCK_BANNER = (
    "\n" + "=" * 78 + "\n"
    "  !!! MOCK (MODELSIZ) MOD ETKIN — DILAJAN_MOCK=1 !!!\n"
    "  VLMClient GERCEK MODELE BAGLANMIYOR. Ozet/olay/risk/aksiyon ciktilarinin\n"
    "  TAMAMI SAHTE ve deterministiktir; goruntu icerigini YANSITMAZ.\n"
    "  -> Bu ciktilar OLCUM, DEGERLENDIRME veya BENCHMARK icin KULLANILAMAZ.\n"
    "  -> Gercek analiz icin: DILAJAN_MOCK=0 ve `python serve_vllm.py`.\n"
    + "=" * 78 + "\n"
)

_mock_warned = False
_mock_warn_lock = threading.Lock()


def _mock_warn_once() -> None:
    """Mock modun ILK kullaniminda stderr'e buyuk uyari basar (surec basina bir kez)."""
    global _mock_warned
    if _mock_warned:
        return
    with _mock_warn_lock:
        if _mock_warned:
            return
        _mock_warned = True
        try:
            print(_MOCK_BANNER, file=sys.stderr, flush=True)
        except Exception:  # cikti akisi kapaliysa sessiz gec (fail-open)
            pass


# --- tohumlama (determinizm) ---------------------------------------------
def _seed(*parts: object) -> int:
    """Girdilerden KARARLI (surecler arasi degismez) bir tohum uretir.

    `hash()` KULLANILMAZ: Python'da str/bytes hash'i surec basina tuzlanir (PYTHONHASHSEED)
    -> ayni video iki kosuda FARKLI mock cikti verirdi. blake2b deterministiktir.
    """
    h = hashlib.blake2b(digest_size=8)
    for p in parts:
        h.update(bytes(p) if isinstance(p, (bytes, bytearray)) else str(p).encode("utf-8", "replace"))
        h.update(b"\x00")
    return int.from_bytes(h.digest(), "big")


def _pick(items: Sequence, seed: int):
    """Tohumdan deterministik secim."""
    return items[seed % len(items)] if items else None


def _messages_text(messages: object) -> str:
    """Sohbet mesajlarindan YALNIZ metin parcalarini birlestirir (goruntu data-URL'leri atlanir).

    Goruntuleri disarida birakmak hem ucuzdur hem de tohumu kararli tutar; kare-bagimliligi
    `analyze_frames` yolunda ayrica `frames` digest'i ile saglanir.
    """
    parts: List[str] = []
    try:
        for m in messages or []:  # type: ignore[union-attr]
            c = m.get("content") if isinstance(m, dict) else None
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, list):
                for it in c:
                    if isinstance(it, dict) and it.get("type") == "text":
                        parts.append(str(it.get("text", "")))
    except Exception:  # beklenmeyen mesaj bicimi -> bos metin (unknown yoluna duser)
        return ""
    return "\n".join(parts)


def _frames_digest(frames: Optional[Sequence[Frame]]) -> str:
    """Kare dizisinden ucuz ama iceriga duyarli bir ozet (ilk+son karenin bas baytlari)."""
    h = hashlib.blake2b(digest_size=8)
    try:
        if not frames:
            return ""
        h.update(str(len(frames)).encode())
        for ts, jpeg in (frames[0], frames[-1]):
            h.update(str(ts).encode())
            h.update(bytes(jpeg)[:4096])
    except Exception:
        return ""
    return h.hexdigest()


# --- prompt turu tanima ---------------------------------------------------
# Her satir: (tur, ayirt-edici ipuclari, gereken asgari ipucu sayisi).
# KIRILGANLIK KARSITI: her tur icin BIRDEN COK ipucu; sira EN OZGULDEN genele; hicbiri
# tutmazsa "unknown" -> guvenli/sema-uyumlu bos yanit (asla cokme).
_MOCK_RULES: Tuple[Tuple[str, Tuple[str, ...], int], ...] = (
    # 1) Sohbet katmani (bu sistem promptlari benzersizdir; analiz promptlarinda GECMEZ)
    ("chat_exec", ("ASİSTANIN DAHA ÖNCE ÖNERDİĞİ", "SOHBET GEÇMİŞİ", "YENİ bir onaysa"), 1),
    ("chat", ("KARAR DESTEK ASİSTANISIN", "GÖREVE BAĞLILIK"), 1),
    ("brief", ("VARDİYA DEVİR-TESLİM", "VARDİYA VERİLERİ"), 1),
    ("purify", ("anlamını koruyarak SADECE düzgün Türkçe", "Yalnızca düzeltilmiş metni döndür"), 1),
    # 2) Politika hakemligi (goruntusuz, video basina tek cagri)
    ("policy", ("POLİTİKA MADDELERİ", "GÖZLEMLER (numarali)", '"kural"', "IHLAL | UYGUN | BELIRSIZ"), 2),
    # 3) Oz-dogrulama / grounding / yeniden-inceleme
    ("verify_batch", ('"gercek"', "YÜKSEK ÖNEMLİ olay var", '"sonuc"'), 2),
    ("verify", ("EVET veya HAYIR", "İddia edilen YÜKSEK ÖNEMLİ olay"), 1),
    ("ground", ("bbox_2d", "Sınırlayıcı kutuyu"), 1),
    ("reexamine", ("CIDDI", "RUTIN", "BELIRSIZ."), 3),
    # 4) Aksiyon sevki
    ("dispatch", ("KULLANILABİLİR FONKSİYONLAR", "OPERASYON MERKEZ", '"calls"'), 2),
    # 5) Karar destek (ozet + risk + aksiyon)
    ("decision", ("video analiz raporu hazirliyorsun", '"summary"', '"actions"'), 2),
    # 6) Olay cikarimi / tek-gecisli algi (JSON semasi ISTEYEN her algi promptu)
    ("extract", ('"events"', "DİKKAT ÇEKİCİ olaylari çikar"), 1),
    # 7) Serbest sahne tarifi (JSON ISTEMEYEN algi promptu)
    ("describe", ("BEKLENEN NORMAL", "SAPMA YOK", "GÜVENLİK ANALİSTİ YORUMU",
                  "zaman damgali ve kronolojik"), 1),
)


def mock_kind(text: str) -> str:
    """Prompt metninden cagri turunu cikarir (taninmazsa 'unknown')."""
    t = text or ""
    for kind, cues, need in _MOCK_RULES:
        if sum(1 for c in cues if c in t) >= need:
            return kind
    return "unknown"


# --- zaman yardimcilari ---------------------------------------------------
_MMSS_RE = re.compile(r"\b(\d{1,2}):([0-5]\d)\b")


def _mmss(sec: int) -> str:
    sec = max(0, int(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _segment_window(text: str) -> Tuple[int, int]:
    """Prompttaki ilk iki MM:SS'i segment penceresi olarak okur (bulunamazsa 0-10 sn)."""
    ts = [int(m.group(1)) * 60 + int(m.group(2)) for m in _MMSS_RE.finditer(text or "")][:2]
    if not ts:
        return 0, 10
    start = ts[0]
    end = ts[1] if len(ts) > 1 and ts[1] > start else start + 10
    return start, end


def _time_in(start: int, end: int, seed: int) -> str:
    """Segment penceresinde deterministik bir olay zamani uretir."""
    return _mmss(start + (seed % max(1, end - start)))


# --- senaryo kitapligi ----------------------------------------------------
# Sahte ama GERCEKCI sahneler. Her senaryo hem serbest tarif (describe) hem de ondan
# cikarilacak olaylar (extract) icin TEK kaynaktir -> iki asamali algi TUTARLI kalir.
_SCENARIOS: Dict[str, dict] = {
    "normal": {
        "mekan": "iç mekân; geniş bir koridor/hol",
        "normal": "kişilerin yürüyerek geçmesi, kısa süre durup beklemesi",
        "sapma": "SAPMA YOK",
        "yorum": "Yorum gerektiren bir güvenlik olayı görülmüyor; sahne rutin.",
        "events": [],
    },
    "dusme": {
        "mekan": "iç mekân; mağaza/ofis benzeri açık bir alan",
        "normal": "kişilerin ayakta durması ve yürümesi",
        "sapma": "{t} civarında kadrajın ortasındaki kişi dengesini kaybedip zemine düşüyor ve "
                 "sonraki karelerde yerde hareketsiz kalıyor; yakındaki bir kişi ona doğru yöneliyor.",
        "yorum": "Zemine düşüp yerde hareketsiz kalan kişi olası bir sağlık acili göstergesidir.",
        "events": [{"event": "Bir kişi zemine düştü ve yerde hareketsiz kaldı",
                    "severity": "Kritik", "category": "Sağlık"}],
    },
    "yangin": {
        "mekan": "iç mekân; depo/servis alanı",
        "normal": "sabit aydınlatma ve durağan ekipman",
        "sapma": "{t} civarında sahnenin arka bölümünde yoğun duman yükseliyor, ardından turuncu "
                 "alev parlaması görülüyor; yakındaki kişiler alandan uzaklaşıyor.",
        "yorum": "Duman ve alev, yangın başlangıcı olarak değerlendirilmelidir.",
        "events": [{"event": "Alanın arka bölümünde duman ve alev (yangın başlangıcı) görüldü",
                    "severity": "Kritik", "category": "Güvenlik"}],
    },
    "kavga": {
        "mekan": "dış mekân; sokak/otopark benzeri açık alan",
        "normal": "yayaların geçişi",
        "sapma": "{t} civarında iki kişi arasında itişme başlıyor, sert ve saldırgan fiziksel temas "
                 "sürüyor; çevredeki kişiler geri çekiliyor.",
        "yorum": "Karşılıklı saldırgan temas bir kavga/darp olayıdır.",
        "events": [{"event": "İki kişi arasında fiziksel kavga/darp",
                    "severity": "Yüksek", "category": "Güvenlik"}],
    },
    "arac": {
        "mekan": "dış mekân; yol/saha girişi",
        "normal": "araçların düşük hızda ilerlemesi",
        "sapma": "{t} civarında ilerleyen araç önündeki engele çarpıyor ve yan yatarak duruyor; "
                 "çarpma sonrası sahnede ani hareketlilik oluşuyor.",
        "yorum": "Çarpışma ve devrilme ciddi bir kaza olarak değerlendirilmelidir.",
        "events": [{"event": "Araç çarpışması ve devrilmesi (kaza)",
                    "severity": "Kritik", "category": "Kaza"}],
    },
    "yetkisiz": {
        "mekan": "dış mekân; çevre çiti/perimetre hattı",
        "normal": "çit hattının boş olması",
        "sapma": "{t} civarında bir kişi çevre çitine tırmanıp kısıtlı alana geçiyor ve hızla "
                 "kameranın görüş alanından çıkıyor.",
        "yorum": "Çit aşılarak kısıtlı alana geçilmesi yetkisiz giriştir.",
        "events": [{"event": "Bir kişi çevre çitini aşarak kısıtlı alana girdi (yetkisiz giriş)",
                    "severity": "Yüksek", "category": "Yetkisiz Erişim"}],
    },
}

# Senaryo havuzu: "normal" AGIRLIKLI (gercek gozetim kaydinin cogu rutindir) -> mock demoda
# her segment olay uydurmaz; dedup / risk tabani / dispatch kapisi gercekci calisir.
_SCENARIO_POOL: Tuple[str, ...] = (
    "normal", "normal", "normal", "normal", "normal",
    "dusme", "yangin", "kavga", "arac", "yetkisiz",
)

#: describe -> extract arasinda senaryoyu tasiyan isaret (iki asamali alginin TUTARLILIGI).
_MARK_RE = re.compile(r"mock-senaryo:\s*([a-z_]+)(?:\s*@\s*(\d{1,2}:[0-5]\d))?")

_SEV_ORD_MOCK = {"Düşük": 1, "Orta": 2, "Yüksek": 3, "Kritik": 4}
_ORD_SEV_MOCK = {v: k for k, v in _SEV_ORD_MOCK.items()}


def _scenario_for(text: str, seed: int) -> Tuple[str, dict, str]:
    """(senaryo_id, senaryo, olay_zamani) — once describe'in biraktigi isarete bakar,
    yoksa tohumdan deterministik secer."""
    start, end = _segment_window(text)
    m = _MARK_RE.search(text or "")
    if m and m.group(1) in _SCENARIOS:
        return m.group(1), _SCENARIOS[m.group(1)], (m.group(2) or _mmss(start))
    sid = _pick(_SCENARIO_POOL, seed)
    return sid, _SCENARIOS[sid], _time_in(start, end, seed)


# --- tur bazli uretimler --------------------------------------------------
def _gen_describe(text: str, seed: int) -> str:
    sid, sc, t = _scenario_for(text, seed)
    return (
        f"1) Ortam ve beklenen normal: {sc['mekan']}. Bu ortamda olağan aktivite: {sc['normal']}.\n"
        f"2) Gözlenen sapmalar: {sc['sapma'].format(t=t)}\n"
        f"3) Güvenlik analisti yorumu: {sc['yorum']}\n"
        f"(mock-senaryo: {sid} @{t})"
    )


def _gen_extract(text: str, seed: int) -> str:
    _sid, sc, t = _scenario_for(text, seed)
    events = [{"time": t, "event": e["event"], "severity": e["severity"], "category": e["category"]}
              for e in sc["events"]]
    return json.dumps({"events": events}, ensure_ascii=False)


def _parse_events_block(text: str) -> List[dict]:
    """Karar-destek/sevk promptundaki olay listesini geri okur.

    Beklenen satir: `- [00:07] açıklama (önem: Kritik, tür: Sağlık, konum: üst sol)`
    Ayristirilamayan satir sessizce atlanir (fail-open).
    """
    out: List[dict] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("- ["):
            continue
        m = re.match(r"-\s*\[(\d{1,2}:[0-5]\d)[^\]]*\]\s*(.+?)\s*\(önem:\s*([^,)]+)", line)
        if m:
            out.append({"time": m.group(1), "event": m.group(2).strip(),
                        "severity": m.group(3).strip()})
    return out


def _worst(events: Sequence[dict]) -> str:
    return _ORD_SEV_MOCK.get(
        max((_SEV_ORD_MOCK.get(e.get("severity", ""), 1) for e in events), default=1), "Düşük")


def _top_event(events: Sequence[dict]) -> Optional[dict]:
    return max(events, key=lambda e: _SEV_ORD_MOCK.get(e.get("severity", ""), 1)) if events else None


_KW = {
    "saglik": ("düş", "dus", "yaral", "hareketsiz", "bayg", "yığıl", "yigil", "sağlık"),
    "guvenlik": ("kavga", "darp", "saldır", "saldir", "yetkisiz", "hırsız", "hirsiz",
                 "şüpheli", "supheli", "silah", "tahrip", "giriş"),
    "ekipman": ("forklift", "devril", "çarpış", "carpis", "araç", "arac", "ekipman", "makine"),
    "yangin": ("yangın", "yangin", "duman", "alev", "patlama"),
}


def _flags(events: Sequence[dict]) -> Dict[str, bool]:
    blob = " ".join(str(e.get("event", "")) for e in events).lower()
    return {k: any(w in blob for w in ws) for k, ws in _KW.items()}


#: SORGU-GUDUMLU ANALIZ ipucu — `prompts.QUERY_ANSWER_INSTRUCTION` karar-destek istemine
#: EKLENDIGINDE bu alan adi istemde gecer. Operator sorgusu BOSKEN o blok hic eklenmez
#: (graph._query_answer_block "" doner) -> ipucu de gecmez -> mock alani URETMEZ (K1/B2).
_QA_FIELD_CUE = "query_answer"


def _gen_query_answer(events: Sequence[dict], top: Optional[dict]) -> str:
    """MOCK sorgu yaniti — YALNIZ istemden geri okunan (sahte) olaylardan turer.

    ILKELER
      * DETERMINIZM : girdi olay listesi ayni ise cumle de aynidir (ek tohum kullanilmaz).
      * UYDURMA YOK : olay yoksa "cikarilamadi" denir; prompt'un anti-halusinasyon kurali
                      (`QUERY_ANSWER_INSTRUCTION`) mock tarafinda da AYNEN uygulanir.
      * DURUSTLUK   : yanit MOCK_TAG ile damgalidir; olcum/karar dayanagi olamaz.
      * ENJEKSIYON  : operatorun SORGU METNI yanita KOPYALANMAZ. Sorgu, isteme <<< >>>
                      arasinda VERI olarak girer; onu ciktiya tasimak metni tutanaga,
                      kanit manifestine ve sohbet baglamina yayardi (gereksiz saldiri yuzeyi).
                      Mock yalnizca OLAYLARA dayanan bir cumle kurar.
    """
    if not events:
        return (f"{MOCK_TAG} Bu bilgi videodan çıkarılamadı: sahte akışta sorguyla "
                f"ilişkilendirilebilecek hiçbir olay işaretlenmedi. Yanıt modelsiz modda "
                f"üretildi; görüntü içeriğini YANSITMAZ.")
    listed = "; ".join(f"[{e.get('time', '?')}] {e.get('event', '')}" for e in events[:3])
    extra = f" (+{len(events) - 3} olay daha)" if len(events) > 3 else ""
    worst_s = (f" En ciddi bulgu [{top['time']}] {top['event']} ({top['severity']})."
               if top else "")
    return (f"{MOCK_TAG} Sorguya yalnızca işaretlenen olaylara dayanarak yanıt: sahte akışta "
            f"{len(events)} olay var — {listed}{extra}.{worst_s} Yanıt modelsiz modda üretildi; "
            f"görüntü içeriğini YANSITMAZ, karar dayanağı olamaz.")


def _gen_decision(text: str, seed: int) -> str:
    events = _parse_events_block(text)
    worst = _worst(events)
    fl = _flags(events)
    top = _top_event(events)

    if top is not None:
        summary = (
            f"{MOCK_TAG} SAHTE (modelsiz) ÇIKTI — bu özet gerçek görüntü analizinden ÜRETİLMEDİ. "
            f"Sahte akışta {len(events)} olay işaretlendi; en ciddi olan [{top['time']}] "
            f"{top['event']} ({top['severity']}). Operatör kararı için görüntü mutlaka izlenmeli "
            f"ve analiz gerçek model ile tekrarlanmalıdır."
        )
    else:
        summary = (
            f"{MOCK_TAG} SAHTE (modelsiz) ÇIKTI — bu özet gerçek görüntü analizinden ÜRETİLMEDİ. "
            f"Sahte akışta kayda değer bir olay işaretlenmedi. Bu sonuç videonun güvenli olduğu "
            f"anlamına GELMEZ; analiz gerçek model ile tekrarlanmalıdır."
        )

    actions: List[dict] = []
    if fl["saglik"]:
        actions.append({"action": "Olay yerine sağlık ekibi yönlendirin", "priority": "Kritik",
                        "rationale": "Yerde hareketsiz/düşmüş kişi bildirimi acil müdahale gerektirir."})
    if fl["yangin"]:
        actions.append({"action": "Yangın prosedürünü başlatın ve alanı tahliye edin", "priority": "Kritik",
                        "rationale": "Duman/alev bildirimi hızla yayılma riski taşır."})
    if fl["guvenlik"]:
        actions.append({"action": "Güvenlik ekibini olay bölgesine yönlendirin", "priority": "Yüksek",
                        "rationale": "Şiddet veya yetkisiz erişim bildirimi yerinde doğrulama gerektirir."})
    if fl["ekipman"]:
        actions.append({"action": "İlgili ekipmanı acil durdurup alanı emniyete alın", "priority": "Yüksek",
                        "rationale": "Araç/ekipman kaynaklı kaza bildirimi ikincil kaza riski taşır."})
    if events and not actions:
        actions.append({"action": "Belirtilen zaman damgalarını kamera kaydından izleyin", "priority": "Orta",
                        "rationale": "İşaretlenen olaylar operatör doğrulaması bekliyor."})
    if events:
        actions.append({"action": "Olay kaydı oluşturup görüntüyü arşivleyin", "priority": "Orta",
                        "rationale": "Denetim izi ve sonraki vardiyaya devir için gereklidir."})
    # HER ZAMAN son madde: mock ciktisinin gecersizligi aksiyon listesinde de gorunur olsun.
    actions.append({
        "action": f"{MOCK_TAG} Modelsiz mod kapatılıp (DILAJAN_MOCK=0) analiz gerçek model ile tekrarlanmalı",
        "priority": "Yüksek",
        "rationale": "Bu rapordaki özet, olaylar ve risk seviyesi sahte üretilmiştir; karar dayanağı olamaz.",
    })

    out: Dict[str, object] = {
        "summary": summary,
        "risk": {"level": worst,
                 "rationale": f"{MOCK_TAG} Sahte değerlendirme: risk, işaretlenen sahte olayların en "
                              f"yüksek önem derecesinden ({worst}) türetildi; görüntü kanıtı YOKTUR."},
        "actions": actions[:5],
    }
    # SORGU-GUDUMLU ANALIZ (B2 VARSAYILAN KAPALI): `query_answer` YALNIZCA istem onu ACIKCA
    # istiyorsa uretilir. Sorgusuz akista bu dal HIC calismaz -> JSON birebir eski halidir
    # (sozlesme + demo ciktisi bit-bit korunur; tests/test_query_driven.py grup 13 kanitlar).
    if _QA_FIELD_CUE in (text or ""):
        out["query_answer"] = _gen_query_answer(events, top)
    return json.dumps(out, ensure_ascii=False)


# Sevk argumani -> anlamsal slot (graph._ARG_SLOT_HINTS ile ayni ruh; burada YEREL ve kucuk).
_MOCK_ARG_SLOTS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("konum", ("konum", "alan", "yer", "bolge", "bölge", "lokasyon")),
    ("severity", ("aciliyet", "risk", "oncelik", "öncelik", "seviye", "önem", "onem")),
    ("ekipman", ("ekipman", "makine", "cihaz", "araç", "arac")),
    ("metin", ("ozet", "özet", "sebep", "neden", "mesaj", "aciklama", "açıklama", "not", "durum")),
)


def _mock_arg(name: str, ctx: Dict[str, str]) -> str:
    n = (name or "").strip().lower()
    for slot, keys in _MOCK_ARG_SLOTS:
        if any(k in n for k in keys):
            return ctx.get(slot, ctx["metin"])
    return ctx["metin"]


def _parse_tools(text: str) -> Dict[str, List[str]]:
    """Promptta LISTELENEN araclari (ad -> arguman adlari) okur — uydurma fonksiyon cagirmamak icin."""
    tools: Dict[str, List[str]] = {}
    for m in re.finditer(r"(?m)^\s*-\s*([A-Za-z_][A-Za-z0-9_]*)\(([^)]*)\)\s*:", text or ""):
        tools[m.group(1)] = [a.strip() for a in m.group(2).split(",") if a.strip()]
    return tools


def _gen_dispatch(text: str, seed: int) -> str:
    """Sevk JSON'u — YALNIZCA promptta listelenen araclari, olay turune gore cagirir."""
    tools = _parse_tools(text)
    events = _parse_events_block(text)
    fl = _flags(events)
    rm = re.search(r"RİSK:\s*(\S+)", text or "")
    risk = (rm.group(1).strip() if rm else _worst(events)).strip("-,. ")
    top = _top_event(events)
    ctx = {
        "konum": "Kamera-01 sahası",
        "severity": risk or "Yüksek",
        "ekipman": "forklift" if fl["ekipman"] else "bilinmeyen ekipman",
        "metin": f"{MOCK_TAG} {top['event'] if top else 'Tespit edilen olay'}",
    }

    wanted: List[str] = []
    if fl["saglik"]:
        wanted.append("saglik_ekibi_yonlendir")
    if fl["guvenlik"]:
        wanted.append("guvenlik_ekibi_uyar")
    if fl["ekipman"]:
        wanted += ["acil_durdurma_tetikle", "alan_guvenligini_sagla"]
    if fl["yangin"]:
        wanted.append("alan_guvenligini_sagla")
    wanted.append("olay_kaydi_olustur")
    if _SEV_ORD_MOCK.get(risk, 0) >= _SEV_ORD_MOCK["Yüksek"]:
        wanted.append("yonetici_bilgilendir")

    calls: List[dict] = []
    seen: set = set()
    for name in wanted:
        if name in seen or name not in tools:
            continue
        seen.add(name)
        calls.append({"function": name, "args": {a: _mock_arg(a, ctx) for a in tools[name]}})
    if not calls and tools:  # arac adlari beklenenden farkli -> ilk araci makul argumanlarla cagir
        name = sorted(tools)[0]
        calls.append({"function": name, "args": {a: _mock_arg(a, ctx) for a in tools[name]}})
    return json.dumps({"calls": calls}, ensure_ascii=False)


def _gen_chat_exec(text: str, seed: int) -> str:
    """Operator onayi sonrasi icra: TEK ve dusuk-etkili cagri (olay kaydi) — damgali."""
    tools = _parse_tools(text)
    rm = re.search(r"(?m)^RİSK:\s*(\S+)", text or "")
    ctx = {"konum": "Kamera-01 sahası", "severity": (rm.group(1).strip() if rm else "Yüksek"),
           "ekipman": "bilinmeyen ekipman", "metin": f"{MOCK_TAG} Operatör onayıyla kayıt açıldı"}
    name = "olay_kaydi_olustur" if "olay_kaydi_olustur" in tools else (sorted(tools)[0] if tools else "")
    if not name:
        return json.dumps({"calls": []}, ensure_ascii=False)
    return json.dumps(
        {"calls": [{"function": name, "args": {a: _mock_arg(a, ctx) for a in tools[name]}}]},
        ensure_ascii=False)


def _gen_chat(text: str, seed: int) -> str:
    """Operator sohbeti: analiz baglamindan okunan risk/olayla kisa, DURUST Turkce yanit."""
    rm = re.search(r"(?m)^RİSK:\s*(.+)$", text or "")
    em = re.search(r"(?m)^\s+\[(\d{1,2}:[0-5]\d)[^\]]*\]\s*(.+?)\s*\(önem:", text or "")
    risk = rm.group(1).strip() if rm else "belirlenmedi"
    if em:
        bulgu = f"[{em.group(1)}] {em.group(2)}"
        oneri = "Bu zaman damgasını kayıttan izleyip ekip sevkine karar vermenizi öneririm."
    else:
        bulgu = "kayda değer bir olay işaretlenmedi"
        oneri = "Rutin izlemeye devam edilebilir."
    return (
        f"{MOCK_TAG} Bu yanıt SAHTEDİR (modelsiz mod etkin) — gerçek model üretmedi.\n"
        f"Analiz bağlamındaki risk: {risk}. Öne çıkan bulgu: {bulgu}. {oneri}\n"
        f"Operasyonel karar vermeden önce modelsiz modu kapatıp (DILAJAN_MOCK=0) analizi "
        f"gerçek model ile tekrarlayın."
    )


def _gen_brief(text: str, seed: int) -> str:
    """Vardiya devir-teslim brifingi (SHIFT_BRIEF_PROMPT'un istedigi 5 baslik)."""
    n = len(re.findall(r"(?m)^\s*-\s*\[", text or ""))
    rm = re.search(r"risk=(\S+)", text or "")
    return (
        f"{MOCK_TAG} SAHTE BRİFİNG (modelsiz mod) — gerçek model üretmedi.\n"
        f"1) GENEL DURUM: Vardiya penceresinde {n} analiz kaydı var; kayıtlardaki risk etiketi "
        f"{rm.group(1) if rm else '?'}.\n"
        f"2) ÖNE ÇIKAN OLAYLAR: Kayıtlar sahte üretildiği için öncelik sıralaması güvenilir "
        f"değildir; ham görüntüler operatörce izlenmelidir.\n"
        f"3) YÜRÜTÜLEN AKSİYONLAR: Yalnızca operatör onayıyla tetiklenen çağrılar kayıtlıdır.\n"
        f"4) AÇIK / İZLENECEK: Modelsiz mod açık; hiçbir bulgu doğrulanmış sayılamaz.\n"
        f"5) ÖNCELİK: Önce modelsiz modu kapatın (DILAJAN_MOCK=0) ve vardiyayı gerçek model ile "
        f"yeniden değerlendirin."
    )


def _gen_purify(text: str, seed: int) -> str:
    """Dil-safligi duzeltmesi: mock ciktisi zaten Turkce oldugu icin metni oldugu gibi geri verir."""
    marker = "Yalnızca düzeltilmiş metni döndür:"
    idx = (text or "").rfind(marker)
    return (text[idx + len(marker):].strip() if idx >= 0 else (text or "").strip())


def _gen_verify(text: str, seed: int) -> str:
    """Oz-dogrulama (tekil): FAIL-OPEN — olayi KORU (gercek yolun hata davranisiyla ayni)."""
    return (f"EVET — {MOCK_TAG} modelsiz modda görsel teyit YAPILAMADI; olay düşürülmeden "
            f"korunuyor (fail-open).")


def _gen_verify_batch(text: str, seed: int) -> str:
    """Oz-dogrulama (toplu): tum olaylar korunur (fail-open, gercek yolun hata davranisiyla ayni)."""
    n = len(re.findall(r"(?m)^\s*(\d+)\)\s", text or ""))
    return json.dumps({"sonuc": [{"no": i, "gercek": True} for i in range(1, n + 1)]},
                      ensure_ascii=False)


def _gen_ground(text: str, seed: int) -> str:
    """Mekansal grounding: deterministik ama makul bir bbox (0-1000 normalize)."""
    x1 = 120 + (seed % 500)
    y1 = 120 + ((seed >> 8) % 500)
    return json.dumps([{"bbox_2d": [x1, y1, min(1000, x1 + 220), min(1000, y1 + 260)],
                        "label": f"{MOCK_TAG} sahte konum"}], ensure_ascii=False)


def _gen_reexamine(text: str, seed: int) -> str:
    """Yeniden-inceleme: BELIRSIZ -> severity DEGISMEZ (mock gorsel kanit uretemez)."""
    return "BELIRSIZ"


def _gen_policy(text: str, seed: int) -> str:
    """Politika hakemligi: FAIL-CLOSED — hicbir gozlem yukseltilmez (R0/UYGUN).

    Mock, operatorun beyan ettigi kurali GORSEL olarak dogrulayamaz; sahte bir "IHLAL"
    karariyla risk/sevk zincirini tetiklemek mock modun en zararli davranisi olurdu.
    """
    n = len(re.findall(r"(?m)^\s*(\d+)\)\s", text or ""))
    return json.dumps(
        {"sonuc": [{"no": i, "kural": "R0", "karar": "UYGUN", "kanit": ""} for i in range(1, n + 1)]},
        ensure_ascii=False)


def _gen_unknown(text: str, seed: int) -> str:
    """Taninmayan prompt -> her tuketicinin guvenle ayristirabilecegi BOS, sema-uyumlu yanit."""
    return json.dumps({"events": [], "calls": [], "actions": [], "sonuc": []}, ensure_ascii=False)


_MOCK_GEN = {
    "describe": _gen_describe,
    "extract": _gen_extract,
    "decision": _gen_decision,
    "dispatch": _gen_dispatch,
    "chat_exec": _gen_chat_exec,
    "chat": _gen_chat,
    "brief": _gen_brief,
    "purify": _gen_purify,
    "verify": _gen_verify,
    "verify_batch": _gen_verify_batch,
    "ground": _gen_ground,
    "reexamine": _gen_reexamine,
    "policy": _gen_policy,
    "unknown": _gen_unknown,
}


def mock_reply(prompt_text: str, frames: Optional[Sequence[Frame]] = None) -> str:
    """MOCK yanit uretici — prompt turunu tanir, DETERMINISTIK sahte yanit dondurur.

    Args:
        prompt_text: cagrinin metin govdesi (analyze_frames'te talimat, chat'te mesaj metinleri).
        frames: varsa segment kareleri; tohuma karisir -> ayni video ayni senaryoyu uretir.

    ASLA ISTISNA FIRLATMAZ: beklenmeyen bir durumda guvenli/bos sema-uyumlu yanit doner
    (mock mod bir demo yoludur; pipeline'i cokertmemelidir).
    """
    _mock_warn_once()
    try:
        text = prompt_text or ""
        kind = mock_kind(text)
        return (_MOCK_GEN.get(kind) or _gen_unknown)(text, _seed(kind, text, _frames_digest(frames)))
    except Exception:  # fail-open: mock hicbir kosulda akisi kirmasin
        return _gen_unknown("", 0)


# ---------------------------------------------------------------------------
# D41 — VIDEO OTURUMU (uzak EVREN servisi icin; yerel vLLM'de de calisir)
# ---------------------------------------------------------------------------
# NEDEN AYRI SINIF: `analyze_frames(as_video=True)` kareleri HER CAGRIDA yeniden
# mp4'e kodluyor. Bu, on-ek onbellegini ISKALAR (baytlar her seferinde farkli).
# Ayrica EVREN servisi istek basina EN FAZLA 2 GORUNTU kabul ediyor — bizim
# 8-12 karelik kare-tabanli yolumuz orada CALISMAZ (olculdu).
GOVDE_SINIRI = 256 * 1024 * 1024          # servisin kabul ettigi ust sinir
HAM_SINIR = int(GOVDE_SINIRI / 1.34)      # base64 sismesi icin pay


class _VideoOturumu:
    """Tek videoya cok soru. base64 BIR KEZ uretilir ve TASINIR."""

    def __init__(self, istemci: "VLMClient", video, system: Optional[str] = None,
                 giris_metni: str = "Bu videoyu inceleyeceğiz."):
        self.istemci = istemci
        self.sistem = system if system is not None else SYSTEM_PERSONA
        self.hata: Optional[str] = None

        ham = video if isinstance(video, (bytes, bytearray)) else open(video, "rb").read()
        if len(ham) > HAM_SINIR:
            self.hata = (f"video {len(ham)/1e6:.1f} MB — base64 sonrasi govde "
                         f"sinirini asar ({GOVDE_SINIRI/1e6:.0f} MB); klip bolunmeli")
            self._url = None
        else:
            # BIR KEZ kodlanir; bu dize tum sorularda AYNEN tekrar kullanilir.
            self._url = "data:video/mp4;base64," + base64.b64encode(bytes(ham)).decode()

        self._mesajlar: List[dict] = []
        if self._url:
            self._mesajlar.append({"role": "user", "content": [
                {"type": "text", "text": giris_metni},
                {"type": "video_url", "video_url": {"url": self._url}},
            ]})

    @property
    def hazir(self) -> bool:
        return self._url is not None

    def sor(self, soru: str, guided_choice: Optional[Sequence[str]] = None,
            temperature: Optional[float] = None, max_tokens: Optional[int] = None,
            hatirla: bool = True, logprobs: bool = False) -> Optional[str]:
        """Ayni video uzerine bir soru. Hata olursa None (K3 fail-open).

        hatirla=True: cevap konusma gecmisine eklenir (sonraki sorular gorur).
        hatirla=False: soru sorulur ama gecmise YAZILMAZ — bagimsiz sorular icin
        (or. birbirini etkilememesi gereken ISG olcumleri).
        """
        if not self.hazir:
            return None
        mesajlar = [{"role": "system", "content": self.sistem}] + self._mesajlar +                    [{"role": "user", "content": soru}]
        self.son_logprob = None
        try:
            c = self.istemci.chat(mesajlar, temperature=temperature,
                                  max_tokens=max_tokens, guided_choice=guided_choice,
                                  logprobs=logprobs)
            # Slot seviyesinde model DEGISEBILIYOR (oturum.istemci yeniden atanir),
            # bu yuzden dagilim CAGRILAN istemciden okunur, sabit bir alandan degil.
            self.son_logprob = getattr(self.istemci, "son_logprob", None)
        except Exception as e:
            self.hata = f"{type(e).__name__}: {e}"
            return None
        if hatirla and c:
            self._mesajlar.append({"role": "user", "content": soru})
            self._mesajlar.append({"role": "assistant", "content": c})
        return c
