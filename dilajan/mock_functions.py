"""Mock operasyonel fonksiyonlar - ajanin 'araçlari'.

Bunlar gerçek bir operasyon merkezindeki aksiyonlari simüle eder (sağlik ekibi
yönlendirme, güvenlik uyarisi, olay kaydi vb.). Ajan, tespit edilen olaylara göre
bu fonksiyonlardan uygun olanlari DINAMIK olarak seçip çağirir (native tool-calling).

Gerçek bir entegrasyonda bu gövdeler bir API/telsiz/SCADA çağrisiyla degistirilebilir.
Her fonksiyon, çagri kaydini OPERATION_LOG'a ekler ve simüle bir sonuç döndürür.
"""
from __future__ import annotations

import datetime
from typing import Callable, Dict, List

from langchain_core.tools import tool

# Bu analiz oturumunda tetiklenen tüm operasyonel çağrilar
OPERATION_LOG: List[dict] = []


def _log(name: str, args: dict, result: str) -> dict:
    entry = {
        "function": name,
        "args": args,
        "result": result,
        "ts": datetime.datetime.now().strftime("%H:%M:%S"),
    }
    OPERATION_LOG.append(entry)
    return entry


@tool
def saglik_ekibi_yonlendir(konum: str, aciliyet: str) -> str:
    """Olay yerine sağlık/ilk yardım ekibi yönlendirir. Yaralanma, düşme, hareketsiz
    kişi veya kaza durumlarinda kullan.

    Args:
        konum: Olayin yeri (ör. 'Depo - 2. koridor' veya 'KAMERA-01 sahasi').
        aciliyet: Aciliyet seviyesi ('Düşük', 'Orta', 'Yüksek', 'Kritik').
    """
    _log("saglik_ekibi_yonlendir", {"konum": konum, "aciliyet": aciliyet},
         f"Sağlık ekibi {konum} konumuna yönlendirildi (aciliyet: {aciliyet}).")
    return f"Sağlık ekibi {konum} konumuna sevk edildi. Tahmini varış: 4 dk."


@tool
def guvenlik_ekibi_uyar(konum: str, sebep: str) -> str:
    """Güvenlik ekibini uyarir. Yetkisiz giriş, kavga, şüpheli davranış veya alan
    güvenliği gereken durumlarda kullan.

    Args:
        konum: Olayin yeri.
        sebep: Güvenlik ekibinin uyarilma sebebi.
    """
    _log("guvenlik_ekibi_uyar", {"konum": konum, "sebep": sebep},
         f"Güvenlik ekibi uyarıldı: {sebep} ({konum}).")
    return f"Güvenlik ekibi {konum} için uyarıldı. Sebep: {sebep}."


@tool
def alan_guvenligini_sagla(alan: str) -> str:
    """Belirtilen alani güvenlik altina alir / erişimi kisitlar. Kaza sonrasi veya
    tehlikeli durum tespit edildiğinde kullan.

    Args:
        alan: Güvenlik altina alinacak alan.
    """
    _log("alan_guvenligini_sagla", {"alan": alan},
         f"{alan} güvenlik altına alındı, erişim kısıtlandı.")
    return f"{alan} çevresi güvenlik şeridine alındı, personel erişimi kısıtlandı."


@tool
def acil_durdurma_tetikle(ekipman: str) -> str:
    """Bir ekipmani/makineyi acil olarak durdurur. Forklift devrilmesi, makine
    arizasi gibi ekipman kaynakli tehlikelerde kullan.

    Args:
        ekipman: Durdurulacak ekipman (ör. 'forklift', 'konveyör').
    """
    _log("acil_durdurma_tetikle", {"ekipman": ekipman},
         f"{ekipman} acil durdurma tetiklendi.")
    return f"{ekipman} için acil durdurma sinyali gönderildi."


@tool
def olay_kaydi_olustur(ozet: str, risk: str) -> str:
    """Olayi kalici kayit altina alir (denetim/raporlama için). Önemli her olayda kullan.

    Args:
        ozet: Olayin kisa özeti.
        risk: Risk seviyesi.
    """
    kayit_no = f"OLY-{len(OPERATION_LOG) + 1:04d}"
    _log("olay_kaydi_olustur", {"ozet": ozet, "risk": risk},
         f"Olay kaydı {kayit_no} oluşturuldu.")
    return f"Olay kaydı {kayit_no} oluşturuldu (risk: {risk})."


@tool
def yonetici_bilgilendir(mesaj: str) -> str:
    """Vardiya amirini/yöneticiyi bilgilendirir. Yüksek/kritik risk durumlarinda kullan.

    Args:
        mesaj: Yöneticiye iletilecek kisa bilgilendirme.
    """
    _log("yonetici_bilgilendir", {"mesaj": mesaj},
         f"Yönetici bilgilendirildi: {mesaj}")
    return f"Vardiya amiri bilgilendirildi: {mesaj}"


# Ajana baglanacak araç listesi ve isim->fonksiyon kaydi
ALL_TOOLS = [
    saglik_ekibi_yonlendir,
    guvenlik_ekibi_uyar,
    alan_guvenligini_sagla,
    acil_durdurma_tetikle,
    olay_kaydi_olustur,
    yonetici_bilgilendir,
]

TOOL_REGISTRY: Dict[str, Callable] = {t.name: t for t in ALL_TOOLS}


def reset_log() -> None:
    OPERATION_LOG.clear()
