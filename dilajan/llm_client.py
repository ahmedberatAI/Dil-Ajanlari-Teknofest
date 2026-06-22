"""Yerel vLLM (OpenAI uyumlu) sunucusuna multimodal istemci.

VLM cagrilari icin OpenAI SDK kullanilir; orkestrasyon LangGraph tarafindadir.
"""
from __future__ import annotations

import base64
from typing import List, Optional, Sequence, Tuple

from openai import OpenAI

from dilajan.config import settings
from dilajan.prompts import SYSTEM_PERSONA

# (zaman_damgasi, jpeg_bytes)
Frame = Tuple[str, bytes]


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
    ) -> str:
        """Zaman damgali kareleri + bir talimati VLM'e gönderir, metin yanit döndürür."""
        content: List[dict] = []
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
