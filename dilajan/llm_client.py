"""Yerel vLLM (OpenAI uyumlu) sunucusuna multimodal istemci.

VLM cagrilari icin OpenAI SDK kullanilir; orkestrasyon LangGraph tarafindadir.
"""
from __future__ import annotations

import base64
import io
from typing import List, Optional, Sequence, Tuple

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
            api_key=api_key or settings.api_key,
            timeout=settings.request_timeout,
        )
        self.model = model or settings.model_name

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
    ) -> str:
        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=settings.temperature if temperature is None else temperature,
            max_tokens=settings.max_tokens if max_tokens is None else max_tokens,
        )
        # vLLM-ozgu repetition_penalty (degenerate dongu/tekrar kirmak icin) -> extra_body
        if repetition_penalty and repetition_penalty != 1.0:
            kwargs["extra_body"] = {"repetition_penalty": repetition_penalty}
        resp = self.client.chat.completions.create(**kwargs)
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
    ) -> str:
        """Zaman damgali kareleri + bir talimati VLM'e gönderir, metin yanit döndürür.
        as_video=True: kareleri tek VIDEO olarak gonderir (EVS temporal-token budama + MRoPE; latency).
        FAIL-OPEN: video kodlama/gonderim hata verirse image-path'e duser."""
        content: List[dict] = []
        if as_video and len(frames) >= 2:
            try:
                mp4 = _frames_to_mp4(frames)
                url = "data:video/mp4;base64," + base64.b64encode(mp4).decode()
                content.append({"type": "video_url", "video_url": {"url": url}})
                content.append({"type": "text", "text": instruction})
                return self.chat([
                    {"role": "system", "content": SYSTEM_PERSONA},
                    {"role": "user", "content": content},
                ], temperature=temperature, max_tokens=max_tokens, repetition_penalty=repetition_penalty)
            except Exception:
                content = []  # image-path'e fail-open
        for ts, jpeg in frames:
            content.append({"type": "text", "text": f"[Kare zamanı: {ts}]"})
            content.append(
                {"type": "image_url", "image_url": {"url": self._to_data_url(jpeg)}}
            )
        content.append({"type": "text", "text": instruction})

        messages = [
            {"role": "system", "content": SYSTEM_PERSONA},
            {"role": "user", "content": content},
        ]
        return self.chat(messages, temperature=temperature, max_tokens=max_tokens,
                         repetition_penalty=repetition_penalty)

    def health_check(self) -> bool:
        """Sunucu ayakta ve model yüklü mü?"""
        try:
            models = self.client.models.list()
            return any(m.id == self.model for m in models.data)
        except Exception:
            return False
