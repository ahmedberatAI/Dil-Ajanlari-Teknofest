"""Mock operasyonel fonksiyonlar - ajanin 'araçlari'.

Bunlar gerçek bir operasyon merkezindeki aksiyonlari simüle eder (sağlik ekibi
yönlendirme, güvenlik uyarisi, olay kaydi vb.). Ajan, tespit edilen olaylara göre
bu fonksiyonlardan uygun olanlari DINAMIK olarak seçip çağirir (native tool-calling).

Gerçek bir entegrasyonda bu gövdeler bir API/telsiz/SCADA çağrisiyla degistirilebilir.
Her fonksiyon, çagri kaydini o anki BAGLAMIN operasyon kaydina ekler ve simüle bir
sonuç döndürür.

K1 — YARIS DURUMU DUZELTMESI (eszamanlilik):
    Kayit listesi artik MODUL-GLOBALI DEGIL, BAGLAM-YEREL'dir (`contextvars.ContextVar`).
    `analyze_video(n_samples>1)` grafigi bir ThreadPoolExecutor icinde PARALEL kostururken
    her kosunun `act()` dugumu basta `reset_log()` cagirip sonda kaydi okuyordu; tek bir
    modul-globali uzerinde bu, kayitlarin birbirine karismasina (ve `triggered_functions`in
    guvenilmez olmasina) yol aciyordu. ContextVar sayesinde her thread/gorev KENDI listesini
    gorur.

    GERIYE-UYUM: `OPERATION_LOG` adi korunur — artik liste gibi davranan ince bir PROXY'dir
    ve tum islemleri o anki baglamin listesine delege eder (iter/len/getitem/append/clear...).
    Boylece disaridaki `for e in OPERATION_LOG`, `len(OPERATION_LOG)`, `list(OPERATION_LOG)`
    kullanimlari aynen calismaya devam eder.

    NOT (LangChain uyumu): `BaseTool.run()` arac gövdesini `copy_context()` icinde kosar.
    Kopyalanan baglam ContextVar DEGERLERINI (liste NESNESINI) paylastigi icin arac
    içindeki `append` cagiran `act()`in listesine yazar; tersine `set()` kopyada kalir.
    Bu yuzden YENI liste ATAMASI (`reset_log`) daima arac disinda, `act()` govdesinde yapilir.
"""
from __future__ import annotations

import datetime
from contextvars import ContextVar
from typing import Callable, Dict, List

from langchain_core.tools import tool

# Baglam-yerel (thread/gorev basina) operasyon kaydi.
# default=None -> bu baglamda henuz reset_log() cagrilmamis demektir; o durumda eski
# modul-global davranisini koruyan _FALLBACK_LOG kullanilir (kayit kaybolmaz).
_LOG_CV: ContextVar = ContextVar("dilajan_operation_log", default=None)
_FALLBACK_LOG: List[dict] = []

# Bellek muhafizi: reset_log() cagrilmayan uzun-omurlu baglamlarda (or. Gradio sohbet
# oturumu) yedek listenin sinirsiz buyumesini onler. Analiz yolu her zaman reset_log()
# cagirdigi icin varsayilan davranisi etkilemez.
_FALLBACK_MAX = 1000


def get_log() -> List[dict]:
    """O anki BAGLAMIN operasyon kayit listesini (canli referans) dondurur."""
    lst = _LOG_CV.get()
    return _FALLBACK_LOG if lst is None else lst


def reset_log() -> None:
    """Bu baglam icin YENI ve BOS bir kayit listesi baslatir.

    Bilerek `clear()` degil ATAMA yapar: baska bir thread'in (paralel kosunun) hâlâ
    okudugu liste nesnesi asla bosaltilmaz -> yaris durumu ortadan kalkar.
    """
    _LOG_CV.set([])


class _OperationLogProxy:
    """`OPERATION_LOG` icin geriye-uyumlu liste-benzeri proxy.

    Eskiden modul-duzeyi bir `list` idi. Disaridaki kod kirilmasin diye ayni arayuzu
    sunar ama tum islemleri `get_log()` ile o anki baglamin listesine delege eder.
    """

    __slots__ = ()

    def _lst(self) -> List[dict]:
        return get_log()

    # --- okuma ---
    def __iter__(self):
        return iter(list(self._lst()))  # anlik kopya: iterasyon sirasinda degisime dayanikli

    def __len__(self) -> int:
        return len(self._lst())

    def __getitem__(self, item):
        return self._lst()[item]

    def __contains__(self, item) -> bool:
        return item in self._lst()

    def __bool__(self) -> bool:
        return bool(self._lst())

    def __reversed__(self):
        return reversed(list(self._lst()))

    def __eq__(self, other) -> bool:
        if isinstance(other, _OperationLogProxy):
            other = list(other)
        return list(self._lst()) == other

    def __repr__(self) -> str:
        return repr(self._lst())

    def index(self, *args):
        return self._lst().index(*args)

    def count(self, item) -> int:
        return self._lst().count(item)

    def copy(self) -> List[dict]:
        return list(self._lst())

    # --- yazma ---
    def append(self, item: dict) -> None:
        self._lst().append(item)

    def extend(self, items) -> None:
        self._lst().extend(items)

    def pop(self, index: int = -1):
        return self._lst().pop(index)

    def clear(self) -> None:
        """Geriye-uyum: eski `OPERATION_LOG.clear()` cagrisi reset_log() ile ayni anlama gelir."""
        reset_log()


# Bu analiz oturumunda (baglaminda) tetiklenen tüm operasyonel çağrilar
OPERATION_LOG = _OperationLogProxy()


def _log(name: str, args: dict, result: str) -> dict:
    entry = {
        "function": name,
        "args": args,
        "result": result,
        "ts": datetime.datetime.now().strftime("%H:%M:%S"),
    }
    lst = get_log()
    lst.append(entry)
    if lst is _FALLBACK_LOG and len(lst) > _FALLBACK_MAX:  # bellek muhafizi (yukariya bkz.)
        del lst[:-_FALLBACK_MAX]
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
    kayit_no = f"OLY-{len(get_log()) + 1:04d}"
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


def snapshot_log() -> List[dict]:
    """O anki baglamin kaydinin KOPYASINI dondurur (disariya sizdirilan referans olmaz)."""
    return list(get_log())


__all__ = [
    "ALL_TOOLS",
    "OPERATION_LOG",
    "TOOL_REGISTRY",
    "get_log",
    "reset_log",
    "snapshot_log",
    "saglik_ekibi_yonlendir",
    "guvenlik_ekibi_uyar",
    "alan_guvenligini_sagla",
    "acil_durdurma_tetikle",
    "olay_kaydi_olustur",
    "yonetici_bilgilendir",
]
