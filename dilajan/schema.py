"""Yapilandirilmis cikti semasi (sartnamedeki JSON sozlesmesi + aciklanabilirlik alanlari).

Sartname asgari formati:
    {"summary": str, "events": [{"time": "MM:SS", "event": str}],
     "risk": str, "actions": [str]}

Asagidaki model bu formati kapsar ve uzerine severity/kategori/gerekce gibi
aciklanabilirlik alanlari ekler. `to_sartname_dict()` ile sade format da uretilir.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    DUSUK = "Düşük"
    ORTA = "Orta"
    YUKSEK = "Yüksek"
    KRITIK = "Kritik"


class EventCategory(str, Enum):
    NORMAL = "Normal"
    GUVENLIK = "Güvenlik"
    KAZA = "Kaza"
    SAGLIK = "Sağlık"
    ANOMALI = "Anomali"
    YETKISIZ_ERISIM = "Yetkisiz Erişim"
    DIGER = "Diğer"


class Event(BaseModel):
    """Videoda tespit edilen tek bir olay (zaman damgali)."""

    time: str = Field(description="Olayin zaman damgasi, MM:SS biçiminde (ör. '00:15')")
    event: str = Field(description="Olayin Türkçe kisa açiklamasi")
    severity: Severity = Field(default=Severity.ORTA, description="Olayin önem derecesi")
    category: EventCategory = Field(default=EventCategory.DIGER)
    bbox: Optional[List[int]] = Field(default=None, description="Olayin karedeki konumu (bbox_2d, 0-1000 normalize)")
    region: Optional[str] = Field(default=None, description="Olayin karedeki bölgesi (ör. 'üst sol', 'merkez')")


class Action(BaseModel):
    """Operatöre sunulan uygulanabilir aksiyon önerisi."""

    action: str = Field(description="Önerilen aksiyon (Türkçe, emir kipinde)")
    priority: Severity = Field(default=Severity.ORTA)
    rationale: Optional[str] = Field(default=None, description="Bu aksiyonun gerekçesi")


class RiskAssessment(BaseModel):
    level: Severity = Field(description="Genel risk seviyesi")
    rationale: str = Field(description="Risk seviyesinin Türkçe gerekçesi")


class AnalysisResult(BaseModel):
    """Bir videonun tam analiz sonucu."""

    summary: str = Field(description="Videonun kisa ve anlasilir Türkçe özeti")
    events: List[Event] = Field(default_factory=list)
    risk: RiskAssessment
    actions: List[Action] = Field(default_factory=list)

    # Aciklanabilirlik / izlenebilirlik
    video_duration: Optional[str] = Field(default=None, description="Video süresi MM:SS")
    triggered_functions: List[str] = Field(
        default_factory=list,
        description="Ajanin çağirdigi mock operasyonel fonksiyonlar",
    )

    def to_sartname_dict(self) -> dict:
        """Sartnamenin sade JSON formatini üretir."""
        return {
            "summary": self.summary,
            "events": [{"time": e.time, "event": e.event} for e in self.events],
            "risk": self.risk.level.value,
            "actions": [a.action for a in self.actions],
        }
