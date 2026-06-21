"""Kucuk yardimci fonksiyonlar."""
from __future__ import annotations

import json
import re
from typing import Any


def extract_json(text: str) -> Any:
    """Model çiktisindan ilk JSON nesnesini güvenli biçimde ayiklar.

    Modeller bazen ```json ... ``` ile sarar veya öncesinde/sonrasinda metin ekler.
    Bu fonksiyon bunlari tolere eder. Bulamazsa ValueError firlatir.
    """
    if not text:
        raise ValueError("Boş model çiktisi")

    # ```json ... ``` bloklarini temizle
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1)

    # Ilk '{' ile dengeli son '}' arasini al
    start = text.find("{")
    if start == -1:
        raise ValueError(f"JSON bulunamadi: {text[:200]}")

    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                return json.loads(candidate)
    raise ValueError(f"Dengeli JSON bulunamadi: {text[:200]}")


def format_timestamp(seconds: float) -> str:
    """Saniyeyi MM:SS biçimine çevirir."""
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
