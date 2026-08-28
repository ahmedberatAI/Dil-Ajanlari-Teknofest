"""Atomik, cok-rolu ISG iddia dogrulamasi.

Bir guvenlik iddiasi acik-uclu VLM nesrinden dogrudan alarma donusmez. Her
desteklenen aile iki ayri olcume ayrilir:

* ``algi`` (``vlm``): goruntudeki gerekli varlik/olgu gercekten var mi?
* ``olay`` (``llm-large``): iddia edilen fiziksel iliski veya zaman akisi var mi?

Her iki cagri da kapali cevap uzayindadir, onceki cevabi hatirlamaz ve karar
model oz-guveninden degil deterministik AND kuralindan cikar. Acik destek yoksa
``INSUFFICIENT`` veya ``REFUTED`` doner; ikisi de alarm iddiasini tutmaya yetmez.

Bu modul yeni model indirmez. Yalniz projenin sabit ozel-API rollerini kullanir.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Mapping, Sequence


class Hukum(str, Enum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class AtomikSoru:
    ad: str
    gorev: str
    soru: str
    secenekler: tuple[str, ...]
    destek: frozenset[str]
    curutme: frozenset[str]


@dataclass(frozen=True)
class AileSpeki:
    aile: str
    sorular: tuple[AtomikSoru, ...]


@dataclass
class KanitSonucu:
    aile: str
    hukum: Hukum
    cevaplar: Dict[str, str]
    hatalar: Dict[str, str]

    @property
    def supported(self) -> bool:
        return self.hukum == Hukum.SUPPORTED

    def iz_satiri(self) -> str:
        parcalar = [f"{k}={v}" for k, v in self.cevaplar.items()]
        parcalar.extend(f"{k}=HATA:{v}" for k, v in self.hatalar.items())
        return f"{self.aile}:{self.hukum.value}[{', '.join(parcalar)}]"


ATOMIK_SISTEM = (
    "Sen bir video adli-kanit olcum aracisin. Yalniz goruntude dogrudan "
    "desteklenen fiziksel olguyu sec. Sahne turunden, kisilerin niyetinden, "
    "basliktan veya olasi bir senaryodan sonuc cikarma. Zorunlu varlik, iliski "
    "ya da zaman bilgisi gorunmuyorsa belirsiz secenegi kullan. Aciklamasiz "
    "yalniz izin verilen etiketi yaz."
)

# En uzun kapalı etiket (`KONTROLSUZ_DUSME_DEVRILME_COKME`) 12 tokenlık eski
# bütçede servis tarafından sessizce kesiliyordu. Kesilmiş etiket izinli uzaya
# uymadığı için gerçek yük/çökme kanıtı INSUFFICIENT'a dönüyordu. Açıklama
# üretilmediğinden 40 token düşük maliyetli fakat tüm mevcut etiketlere güvenlidir.
ATOMIK_MAX_TOKENS = 40


def _q(ad: str, gorev: str, soru: str, secenekler: Sequence[str],
       destek: Iterable[str], curutme: Iterable[str]) -> AtomikSoru:
    return AtomikSoru(ad, gorev, soru, tuple(secenekler),
                      frozenset(destek), frozenset(curutme))


_KISI = _q(
    "kisi", "algi",
    "Videoda iddiaya konu olabilecek gercek bir insan/çalışan açıkça görünüyor mu? "
    "Kutu, raf, araç, gölge, manken veya makine parçası insan değildir. Yalnız "
    "KISI_VAR, KISI_YOK veya GORUNMUYOR yaz.",
    ("KISI_VAR", "KISI_YOK", "GORUNMUYOR"), ("KISI_VAR",), ("KISI_YOK",),
)


SPEKLER: Mapping[str, AileSpeki] = {
    "yangın/duman": AileSpeki("yangın/duman", (
        _q(
            "gorunur_belirti", "algi",
            "Videoda gerçek alev veya sınırları yumuşak, kareler arasında biçim "
            "değiştiren/yükselen duman benzeri bir bulut açıkça var mı? Sabit koyu "
            "boşluk, raf, gölge ve katı nesne belirti değildir. Yalnız "
            "ALEV_DUMAN_VAR, ALEV_DUMAN_YOK veya GORUNMUYOR yaz.",
            ("ALEV_DUMAN_VAR", "ALEV_DUMAN_YOK", "GORUNMUYOR"),
            ("ALEV_DUMAN_VAR",), ("ALEV_DUMAN_YOK",)),
        _q(
            "zamansal_davranis", "olay",
            "Videoyu kronolojik karşılaştır. İddiadaki oluşum görünür alev ya da "
            "zamanla yükselen/yayılan duman mıdır; yoksa buhar, toz, ışık parlaması, "
            "kamera sıkıştırması veya sabit gölge/nesne midir? Yalnız "
            "ALEV_VEYA_YAYILAN_DUMAN, BUHAR_TOZ_PARLAMA, SABIT_GOLGE_NESNE, "
            "BELIRTI_YOK veya GORUNMUYOR yaz.",
            ("ALEV_VEYA_YAYILAN_DUMAN", "BUHAR_TOZ_PARLAMA", "SABIT_GOLGE_NESNE",
             "BELIRTI_YOK", "GORUNMUYOR"),
            ("ALEV_VEYA_YAYILAN_DUMAN",),
            ("BUHAR_TOZ_PARLAMA", "SABIT_GOLGE_NESNE", "BELIRTI_YOK")),
    )),
    "termal aşırı ısınma": AileSpeki("termal aşırı ısınma", (
        _q(
            "kizgin_yuzey", "algi",
            "Videoda makine, metal yüzey veya ekipmanın geniş bir bölümü ısı nedeniyle "
            "kor/kızgın metal gibi kırmızı-turuncu parlıyor mu? Kırmızı boya, ikaz lambası, "
            "LED, güneş/ışık yansıması ve renkli nesne kızgın yüzey değildir. Yalnız "
            "KIZGIN_YUZEY_VAR, KIRMIZI_BOYA_ISIK, YANSIMA, KIZGIN_YUZEY_YOK veya "
            "GORUNMUYOR yaz.",
            ("KIZGIN_YUZEY_VAR", "KIRMIZI_BOYA_ISIK", "YANSIMA",
             "KIZGIN_YUZEY_YOK", "GORUNMUYOR"),
            ("KIZGIN_YUZEY_VAR",),
            ("KIRMIZI_BOYA_ISIK", "YANSIMA", "KIZGIN_YUZEY_YOK")),
        _q(
            "isinma_gecisi", "olay",
            "Videoyu kronolojik karşılaştır. Makine/metal yüzey normal veya koyu halden "
            "giderek daha geniş kırmızı-turuncu kızgın parlamaya mı geçiyor ya da belirgin "
            "kor ışıması mı sürdürüyor? Sabit kırmızı boya/lamba, kamera beyaz dengesi ve "
            "yansıma termal olay değildir. Yalnız KIZARMA_VEYA_KOR_ISIMASI, "
            "SABIT_BOYA_LAMBA, YANSIMA_RENK_DEGISIMI, DEGISIM_YOK veya GORUNMUYOR yaz.",
            ("KIZARMA_VEYA_KOR_ISIMASI", "SABIT_BOYA_LAMBA",
             "YANSIMA_RENK_DEGISIMI", "DEGISIM_YOK", "GORUNMUYOR"),
            ("KIZARMA_VEYA_KOR_ISIMASI",),
            ("SABIT_BOYA_LAMBA", "YANSIMA_RENK_DEGISIMI", "DEGISIM_YOK")),
    )),
    "destekten sarkan kişi": AileSpeki("destekten sarkan kişi", (
        _q(
            "sarkma_geometrisi", "algi",
            "Videoda gerçek bir kişi yükseltilmiş boru, çatı kenarı, kiriş veya yapı "
            "parçasına elleri/kollarıyla tutunurken gövdesi aşağıda ve ayakları güvenli "
            "bir zemin/platform desteğinde değil mi? Merdivende basamak üzerinde durma, "
            "spor/barfiks ve zeminde ayakta durma sarkma değildir. Yalnız "
            "SARKAN_KISI_ACIK, AYAKLAR_DESTEKLI, RUTIN_TIRMANMA_SPOR, KISI_YOK veya "
            "GORUNMUYOR yaz.",
            ("SARKAN_KISI_ACIK", "AYAKLAR_DESTEKLI", "RUTIN_TIRMANMA_SPOR",
             "KISI_YOK", "GORUNMUYOR"), ("SARKAN_KISI_ACIK",),
            ("AYAKLAR_DESTEKLI", "RUTIN_TIRMANMA_SPOR", "KISI_YOK")),
        _q(
            "destek_kaybi", "olay",
            "Videoyu kronolojik izle. Kişi kayma/dengesizlik sonrasında iki ayağının "
            "desteğini kaybedip esas olarak elleri/kollarıyla yüksek bir kenara veya "
            "boruya asılı kalıyor ya da bacakları havada sallanıyor mu? Kontrollü "
            "merdiven çıkışı, çalışma platformunda durma ve egzersiz değildir. Yalnız "
            "DESTEK_KAYBI_VE_SARKMA, DESTEKLI_TIRMANMA_CALISMA, RUTIN_SPOR, "
            "KISI_YOK veya GORUNMUYOR yaz.",
            ("DESTEK_KAYBI_VE_SARKMA", "DESTEKLI_TIRMANMA_CALISMA", "RUTIN_SPOR",
             "KISI_YOK", "GORUNMUYOR"), ("DESTEK_KAYBI_VE_SARKMA",),
            ("DESTEKLI_TIRMANMA_CALISMA", "RUTIN_SPOR", "KISI_YOK")),
    )),
    "kontrolünü kaybeden araç": AileSpeki("kontrolünü kaybeden araç", (
        _q(
            "arac_baglami", "algi",
            "Videoda motorlu araç, forklift, iş makinesi, yol silindiri veya hareket "
            "halindeki bir aracın kabin/iç mekânı açıkça görülüyor mu? Sıradan sabit "
            "makine ve elde taşınan alet araç değildir. Yalnız ARAC_VEYA_ARAC_ICI_VAR, "
            "ARAC_YOK veya GORUNMUYOR yaz.",
            ("ARAC_VEYA_ARAC_ICI_VAR", "ARAC_YOK", "GORUNMUYOR"),
            ("ARAC_VEYA_ARAC_ICI_VAR",), ("ARAC_YOK",)),
        _q(
            "kontrol_kaybi", "olay",
            "Videoyu kronolojik izle. Araç/iş makinesi belirgin biçimde kontrolsüz "
            "savruluyor, devriliyor, yol/kenardan düşüyor, engellere çarpıyor veya araç "
            "içindeki kişiyi yere/yan tarafa fırlatacak şiddette yön-duruş kaybı yaşıyor "
            "mu? Rutin dönüş, geri manevra, normal sürüş sarsıntısı ve kontrollü duruş "
            "olay değildir. Yalnız KONTROL_KAYBI_DEVRILME_CARPMA, RUTIN_MANEVRA_SURUS, "
            "NORMAL_KAMERA_SARSINTISI, ARAC_YOK veya GORUNMUYOR yaz.",
            ("KONTROL_KAYBI_DEVRILME_CARPMA", "RUTIN_MANEVRA_SURUS",
             "NORMAL_KAMERA_SARSINTISI", "ARAC_YOK", "GORUNMUYOR"),
            ("KONTROL_KAYBI_DEVRILME_CARPMA",),
            ("RUTIN_MANEVRA_SURUS", "NORMAL_KAMERA_SARSINTISI", "ARAC_YOK")),
    )),
    "dengesini kaybeden ağır yük": AileSpeki("dengesini kaybeden ağır yük", (
        _q(
            "agir_yuk_sistemi", "algi",
            "Videoda forklift/vinç tarafından taşınan ağır yük, yük istifi veya yük "
            "taşıyan vinç/forklift sistemi açıkça görülüyor mu? Boş araç, küçük elde "
            "taşınan nesne ve sabit raf tek başına bu olayın yükü değildir. Yalnız "
            "AGIR_YUK_SISTEMI_VAR, YUKSUZ_ARAC_VEYA_KUCUK_NESNE, YUK_YOK veya "
            "GORUNMUYOR yaz.",
            ("AGIR_YUK_SISTEMI_VAR", "YUKSUZ_ARAC_VEYA_KUCUK_NESNE", "YUK_YOK",
             "GORUNMUYOR"), ("AGIR_YUK_SISTEMI_VAR",),
            ("YUKSUZ_ARAC_VEYA_KUCUK_NESNE", "YUK_YOK")),
        _q(
            "yuk_denge_kaybi", "olay",
            "Videoyu kronolojik izle. Ağır yük taşıyıcı üzerindeki destekli konumunu "
            "kaybedip düşüyor/kayıyor mu veya yükün salınımı/kaçıklığı vinç ya da taşıyıcıyı "
            "belirgin biçimde yatırıp dengesizleştiriyor mu? Kontrollü kaldırma, indirme, "
            "geri manevra ve sabit askıda bekleme olay değildir. Yalnız "
            "YUK_DUSMESI_VEYA_SISTEM_DENGESIZLIGI, KONTROLLU_TASIMA, SABIT_ASKIDA_YUK, "
            "YUK_YOK veya GORUNMUYOR yaz.",
            ("YUK_DUSMESI_VEYA_SISTEM_DENGESIZLIGI", "KONTROLLU_TASIMA",
             "SABIT_ASKIDA_YUK", "YUK_YOK", "GORUNMUYOR"),
            ("YUK_DUSMESI_VEYA_SISTEM_DENGESIZLIGI",),
            ("KONTROLLU_TASIMA", "SABIT_ASKIDA_YUK", "YUK_YOK")),
    )),
    "karşılıklı fiziksel kavga": AileSpeki("karşılıklı fiziksel kavga", (
        _q(
            "coklu_kisi", "algi",
            "Videoda cam, kapı veya bölme arkasında olsa da birbirine yakın en az iki "
            "gerçek kişi seçilebiliyor mu? Yansıma, gölge ve ekrandaki görüntü ek kişi "
            "değildir. Yalnız IKI_VEYA_DAHA_COK_KISI, TEK_KISI, KISI_YOK veya "
            "GORUNMUYOR yaz.",
            ("IKI_VEYA_DAHA_COK_KISI", "TEK_KISI", "KISI_YOK", "GORUNMUYOR"),
            ("IKI_VEYA_DAHA_COK_KISI",), ("TEK_KISI", "KISI_YOK")),
        _q(
            "karsilikli_siddet", "olay",
            "Videoyu kronolojik izle. İki veya daha fazla kişi birbirine yönelmiş "
            "biçimde tekrarlanan sert vurma, tekme, itme, çekme veya boğuşma hareketleri "
            "yapıyor mu? Tartışma/el kol hareketi, kalabalıkta yürüme, oyun ve rutin iş "
            "teması kavga değildir. Yalnız KARSILIKLI_FIZIKSEL_KAVGA, SOZLU_TARTISMA, "
            "RUTIN_TEMAS_HAREKET, KISI_YOK veya GORUNMUYOR yaz.",
            ("KARSILIKLI_FIZIKSEL_KAVGA", "SOZLU_TARTISMA",
             "RUTIN_TEMAS_HAREKET", "KISI_YOK", "GORUNMUYOR"),
            ("KARSILIKLI_FIZIKSEL_KAVGA",),
            ("SOZLU_TARTISMA", "RUTIN_TEMAS_HAREKET", "KISI_YOK")),
    )),
    "aktif makine yakalama/sıkışma": AileSpeki("aktif makine yakalama/sıkışma", (
        _q(
            "kisi_makine_bolgesi", "algi",
            "Videoda gerçek kişinin bedeni, eli, ayağı, uzvu veya giysisi hareketli "
            "konveyör, merdane, pres, kapanan makine yüzeyi ya da döner ekipmanın temas/"
            "sıkışma bölgesinde açıkça görülüyor mu? Makine yanında güvenli mesafede "
            "durmak ve yalnız kumanda kullanmak temas bölgesi değildir. Yalnız "
            "KISI_UZUV_MAKINE_BOLGESINDE, KISI_GUVENLI_MESAFEDE, KISI_YOK veya "
            "GORUNMUYOR yaz.",
            ("KISI_UZUV_MAKINE_BOLGESINDE", "KISI_GUVENLI_MESAFEDE", "KISI_YOK",
             "GORUNMUYOR"), ("KISI_UZUV_MAKINE_BOLGESINDE",),
            ("KISI_GUVENLI_MESAFEDE", "KISI_YOK")),
        _q(
            "yakalama_gecisi", "olay",
            "Videoyu kronolojik izle. Kişinin bedeni/uzvu/giysisi hareketli makineye "
            "çekiliyor, iki yüzey arasında kapanıyor, konveyörde sıkışıp ayrılamıyor veya "
            "makine hareketi kişiyi sürüklüyor/ezmeye başlıyor mu? Yakında çalışma, "
            "malzeme besleme, kumanda ayarı ve temas oluşmadan geri çekilme olay değildir. "
            "Yalnız AKTIF_YAKALAMA_SIKISMA_EZILME, RUTIN_YAKIN_CALISMA, TEMAS_YOK, "
            "KISI_YOK veya GORUNMUYOR yaz.",
            ("AKTIF_YAKALAMA_SIKISMA_EZILME", "RUTIN_YAKIN_CALISMA", "TEMAS_YOK",
             "KISI_YOK", "GORUNMUYOR"), ("AKTIF_YAKALAMA_SIKISMA_EZILME",),
            ("RUTIN_YAKIN_CALISMA", "TEMAS_YOK", "KISI_YOK")),
        _q(
            "fiziksel_bag", "algi",
            "İddiadaki kişi/uzuv ile hareketli makine parçası arasında kesintisiz gerçek "
            "fiziksel temas, çevreleme/kapanma veya birlikte sürüklenme açıkça seçiliyor "
            "mu? Su, duman, gölge, perspektif örtüşmesi ve yalnız yakınlık fiziksel bağ "
            "değildir. Yalnız MAKINE_KISI_FIZIKSEL_BAGI, YALNIZ_YAKINLIK_ORTUSME, "
            "MAKINE_VEYA_KISI_YOK veya GORUNMUYOR yaz.",
            ("MAKINE_KISI_FIZIKSEL_BAGI", "YALNIZ_YAKINLIK_ORTUSME",
             "MAKINE_VEYA_KISI_YOK", "GORUNMUYOR"),
            ("MAKINE_KISI_FIZIKSEL_BAGI",),
            ("YALNIZ_YAKINLIK_ORTUSME", "MAKINE_VEYA_KISI_YOK")),
    )),
    "üstten düşen ağır yük/pres": AileSpeki("üstten düşen ağır yük/pres", (
        _q(
            "yukseltilmis_agir_kutle", "algi",
            "Videoda vinç/forklift yükü, ağır kutu/istif, kaldırma platformu veya pres "
            "plakası gibi ağır bir kütle zeminden yükseltilmiş ya da insanların üstünde/"
            "yakınında açıkça görülüyor mu? Küçük elde taşınan nesne ve sabit tavan/yapı "
            "bu yük değildir. Yalnız YUKSELTILMIS_AGIR_KUTLE_VAR, KUCUK_VEYA_SABIT_NESNE, "
            "YUK_YOK veya GORUNMUYOR yaz.",
            ("YUKSELTILMIS_AGIR_KUTLE_VAR", "KUCUK_VEYA_SABIT_NESNE", "YUK_YOK",
             "GORUNMUYOR"), ("YUKSELTILMIS_AGIR_KUTLE_VAR",),
            ("KUCUK_VEYA_SABIT_NESNE", "YUK_YOK")),
        _q(
            "kontrolsuz_inis", "olay",
            "Videoyu kronolojik izle. Ağır yük, platform veya pres destekli konumunu "
            "kaybedip belirgin biçimde düşüyor, kayıyor, yana yatıyor ya da insanların "
            "üzerine kontrolsüz iniyor mu? Kontrollü ve düzgün kaldırma/indirme, sabit "
            "askıda bekleme veya yalnız kameranın hareketi olay değildir. Yalnız "
            "KONTROLSUZ_DUSME_INME_DENGE_KAYBI, KONTROLLU_INDIRME_TASIMA, "
            "SABIT_YUK, YUK_YOK veya GORUNMUYOR yaz.",
            ("KONTROLSUZ_DUSME_INME_DENGE_KAYBI", "KONTROLLU_INDIRME_TASIMA",
             "SABIT_YUK", "YUK_YOK", "GORUNMUYOR"),
            ("KONTROLSUZ_DUSME_INME_DENGE_KAYBI",),
            ("KONTROLLU_INDIRME_TASIMA", "SABIT_YUK", "YUK_YOK")),
    )),
    "kişi destek kaybı/düşme": AileSpeki("kişi destek kaybı/düşme", (
        _q(
            "riskli_kisi_pozu", "algi",
            "Videoda gerçek kişi merdiven/yüksek kenar/halat üzerinde, havada asılı, "
            "düşme hareketinde veya düşüş sonrası zeminde açıkça görülüyor mu? Zeminde "
            "normal yürüme, oturma, çömelme ve çalışma bu olgu değildir. Yalnız "
            "YUKSEKLIK_ASILMA_DUSME_POZU, RUTIN_ZEMIN_HAREKETI, KISI_YOK veya "
            "GORUNMUYOR yaz.",
            ("YUKSEKLIK_ASILMA_DUSME_POZU", "RUTIN_ZEMIN_HAREKETI", "KISI_YOK",
             "GORUNMUYOR"), ("YUKSEKLIK_ASILMA_DUSME_POZU",),
            ("RUTIN_ZEMIN_HAREKETI", "KISI_YOK")),
        _q(
            "destek_kaybi_dusme", "olay",
            "Videoyu kronolojik izle. Kişi ayağının/merdivenin desteğini kaybedip "
            "düşüyor, kayıp zemine çarpıyor/yerde kalıyor veya düşmemek için elleri/"
            "halatla asılı kalıyor mu? Kontrollü iniş, spor, oturma, eğilme ve rutin "
            "merdiven kullanımı olay değildir. Yalnız DESTEK_KAYBI_DUSME_ASILMA, "
            "KONTROLLU_INIS_RUTIN_HAREKET, KISI_YOK veya GORUNMUYOR yaz.",
            ("DESTEK_KAYBI_DUSME_ASILMA", "KONTROLLU_INIS_RUTIN_HAREKET",
             "KISI_YOK", "GORUNMUYOR"), ("DESTEK_KAYBI_DUSME_ASILMA",),
            ("KONTROLLU_INIS_RUTIN_HAREKET", "KISI_YOK")),
    )),
    "yangın/duman/basınçlı gaz": AileSpeki("yangın/duman/basınçlı gaz", (
        _q(
            "gorunur_enerji_salimi", "algi",
            "Videoda gerçek alev, biçim değiştiren yoğun duman veya kırılan/kaçak bir "
            "hat-silindirden kuvvetle çıkan ve genişleyen basınçlı gaz bulutu/jeti açıkça "
            "görülüyor mu? Sabit gölge, sıradan egzoz, ince rutin buhar, toz ve ışık "
            "parlaması olay değildir. Yalnız ALEV_DUMAN_GAZ_SALIMI, RUTIN_BUHAR_EGZOZ_TOZ, "
            "BELIRTI_YOK veya GORUNMUYOR yaz.",
            ("ALEV_DUMAN_GAZ_SALIMI", "RUTIN_BUHAR_EGZOZ_TOZ", "BELIRTI_YOK",
             "GORUNMUYOR"), ("ALEV_DUMAN_GAZ_SALIMI",),
            ("RUTIN_BUHAR_EGZOZ_TOZ", "BELIRTI_YOK")),
        _q(
            "salim_yayilimi", "olay",
            "Videoyu kronolojik izle. Alev sürüyor/büyüyor, duman yükselip yayılıyor "
            "veya basınçlı gaz aniden fışkırıp hacmi genişliyor mu? İnsanların geri "
            "çekilmesi yalnız yardımcı bağlamdır ve görünür salım yoksa yeterli değildir. "
            "Rutin buhar/egzoz, kısa toz kalkması ve kamera parlaması olay değildir. "
            "Yalnız TEHLIKELI_ALEV_DUMAN_GAZ_YAYILIMI, RUTIN_BUHAR_TOZ_EGZOZ, "
            "BELIRTI_YOK veya GORUNMUYOR yaz.",
            ("TEHLIKELI_ALEV_DUMAN_GAZ_YAYILIMI", "RUTIN_BUHAR_TOZ_EGZOZ",
             "BELIRTI_YOK", "GORUNMUYOR"),
            ("TEHLIKELI_ALEV_DUMAN_GAZ_YAYILIMI",),
            ("RUTIN_BUHAR_TOZ_EGZOZ", "BELIRTI_YOK")),
    )),
    "makine arızası/parça fırlaması": AileSpeki("makine arızası/parça fırlaması", (
        _q(
            "makine_ve_parca", "algi",
            "Videoda çalışan bir makine/ekipman ile ondan kopabilecek cam, kapak, parça, "
            "silindir, beam/kiriş veya hareketli bileşen açıkça görülüyor mu? İnsan eliyle "
            "rutin taşınan nesne ve sabit yapı parçası bu makine parçası değildir. Yalnız "
            "MAKINE_VE_HAREKETLI_PARCA_VAR, SABIT_VEYA_ELDE_NESNE, MAKINE_YOK veya "
            "GORUNMUYOR yaz.",
            ("MAKINE_VE_HAREKETLI_PARCA_VAR", "SABIT_VEYA_ELDE_NESNE", "MAKINE_YOK",
             "GORUNMUYOR"), ("MAKINE_VE_HAREKETLI_PARCA_VAR",),
            ("SABIT_VEYA_ELDE_NESNE", "MAKINE_YOK")),
        _q(
            "ani_ariza_gecisi", "olay",
            "Videoyu kronolojik izle. Makine aniden kontrolsüz ve şiddetli sallanıyor, "
            "camı/parçası kırılıp fırlıyor, bir parça kopup düşüyor veya çevredekileri "
            "kaçıran açık mekanik arıza geçişi oluşuyor mu? Normal titreşim, kontrollü "
            "parça çıkarma ve rutin çalışma olay değildir. Yalnız "
            "ANI_ARIZA_KIRILMA_PARCA_FIRLAMA, NORMAL_TITRESIM_CALISMA, "
            "KONTROLLU_PARCA_HAREKETI, MAKINE_YOK veya GORUNMUYOR yaz.",
            ("ANI_ARIZA_KIRILMA_PARCA_FIRLAMA", "NORMAL_TITRESIM_CALISMA",
             "KONTROLLU_PARCA_HAREKETI", "MAKINE_YOK", "GORUNMUYOR"),
            ("ANI_ARIZA_KIRILMA_PARCA_FIRLAMA",),
            ("NORMAL_TITRESIM_CALISMA", "KONTROLLU_PARCA_HAREKETI", "MAKINE_YOK")),
    )),
    "ani endüstriyel enerji/ekipman olayı": AileSpeki(
        "ani endüstriyel enerji/ekipman olayı", (
        _q(
            "endustriyel_kaynak", "algi",
            "Videoda powered/çalışan makine, pres, ağır yük sistemi, basınçlı silindir/hat "
            "veya araç bakım ekipmanı gibi görünür bir endüstriyel enerji/ekipman kaynağı "
            "var mı? Yalnız insanlar, bina, su birikintisi ve sabit mobilya kaynak değildir. "
            "Yalnız ENDUSTRIYEL_ENERJI_EKIPMAN_KAYNAGI, YALNIZ_SABIT_CEVRE, "
            "KAYNAK_YOK veya GORUNMUYOR yaz.",
            ("ENDUSTRIYEL_ENERJI_EKIPMAN_KAYNAGI", "YALNIZ_SABIT_CEVRE",
             "KAYNAK_YOK", "GORUNMUYOR"), ("ENDUSTRIYEL_ENERJI_EKIPMAN_KAYNAGI",),
            ("YALNIZ_SABIT_CEVRE", "KAYNAK_YOK")),
        _q(
            "ani_kontrolsuz_salım", "olay",
            "Videoyu kronolojik izle. Bu kaynakta aniden kontrolsüz ağır hareket/düşme, "
            "kırılma/parça kopması, alev-duman, basınçlı gaz fışkırması veya çevredeki "
            "kişileri geri kaçıran açık enerji/malzeme salımı oluşuyor mu? İnsanların "
            "hareketi yalnız başına yeterli değildir. Rutin çalışma, kontrollü taşıma, "
            "normal titreşim/buhar ve yalnız kamera hareketi olay değildir. Yalnız "
            "ANI_KONTROLSUZ_ENERJI_MALZEME_SALIMI, RUTIN_KONTROLLU_CALISMA, "
            "YALNIZ_KISI_KAMERA_HAREKETI, KAYNAK_YOK veya GORUNMUYOR yaz.",
            ("ANI_KONTROLSUZ_ENERJI_MALZEME_SALIMI", "RUTIN_KONTROLLU_CALISMA",
             "YALNIZ_KISI_KAMERA_HAREKETI", "KAYNAK_YOK", "GORUNMUYOR"),
            ("ANI_KONTROLSUZ_ENERJI_MALZEME_SALIMI",),
            ("RUTIN_KONTROLLU_CALISMA", "YALNIZ_KISI_KAMERA_HAREKETI", "KAYNAK_YOK")),
    )),
    "düşme/yaralı kişi": AileSpeki("düşme/yaralı kişi", (
        _KISI,
        _q(
            "poz_ve_gecis", "olay",
            "Videoyu kronolojik izle. Gerçek bir kişinin dik konumdan zemine düşme "
            "hareketi veya zeminde belirgin biçimde yatarak kalması açıkça görülüyor "
            "mu? Rutin oturma, çömelme, eğilip kutu alma, kısa örtülme ve yerdeki nesne "
            "düşmüş kişi değildir. Yalnız DUSME_GECISI, YERDE_YATAN_KISI, "
            "RUTIN_DURUS_HAREKET, KISI_YOK veya GORUNMUYOR yaz.",
            ("DUSME_GECISI", "YERDE_YATAN_KISI", "RUTIN_DURUS_HAREKET",
             "KISI_YOK", "GORUNMUYOR"),
            ("DUSME_GECISI", "YERDE_YATAN_KISI"),
            ("RUTIN_DURUS_HAREKET", "KISI_YOK")),
    )),
    "şiddet/silah": AileSpeki("şiddet/silah", (
        _KISI,
        _q(
            "fiziksel_eylem", "olay",
            "Videoda bir kişiye yönelik açık vurma, tekmeleme, boğuşma/saldırı ya da "
            "elde açıkça seçilen silah var mı? Rutin çalışma teması, el kol hareketi, "
            "yan yana durma ve alet kullanımı saldırı değildir. Yalnız "
            "ACIK_SALDIRI_VEYA_SILAH, RUTIN_TEMAS_CALISMA, KISI_YOK veya "
            "GORUNMUYOR yaz.",
            ("ACIK_SALDIRI_VEYA_SILAH", "RUTIN_TEMAS_CALISMA", "KISI_YOK",
             "GORUNMUYOR"), ("ACIK_SALDIRI_VEYA_SILAH",),
            ("RUTIN_TEMAS_CALISMA", "KISI_YOK")),
    )),
    "çarpışma/devrilme": AileSpeki("çarpışma/devrilme", (
        _q(
            "ayri_varliklar", "algi",
            "Videoda hareket eden araç/ekipman ile ondan ayrı bir kişi, araç, raf, "
            "bariyer veya depo ekipmanı birlikte açıkça görülüyor mu? Taşınan yük "
            "aracın kendisinden ayrı çarpışma hedefi sayılmaz. Yalnız "
            "IKI_AYRI_VARLIK, AYRI_HEDEF_YOK veya GORUNMUYOR yaz.",
            ("IKI_AYRI_VARLIK", "AYRI_HEDEF_YOK", "GORUNMUYOR"),
            ("IKI_AYRI_VARLIK",), ("AYRI_HEDEF_YOK",)),
        _q(
            "temas_sonucu", "olay",
            "Videoyu kronolojik izle. Hareketli varlık ayrı hedefe fiziksel olarak "
            "ulaşıyor ve temasın hemen ardından hedefte itme, sürüklenme, eğilme, "
            "devrilme veya açık durum değişimi oluyor mu? Yalnız yakın geçiş ve "
            "perspektif örtüşmesi temas değildir. Yalnız DOGRUDAN_TEMAS_VE_SONUC, "
            "YANINDAN_GECIS, PERSPEKTIF_ORTUSMESI, HEDEF_HAREKETSIZ veya "
            "GORUNMUYOR yaz.",
            ("DOGRUDAN_TEMAS_VE_SONUC", "YANINDAN_GECIS", "PERSPEKTIF_ORTUSMESI",
             "HEDEF_HAREKETSIZ", "GORUNMUYOR"),
            ("DOGRUDAN_TEMAS_VE_SONUC",),
            ("YANINDAN_GECIS", "PERSPEKTIF_ORTUSMESI", "HEDEF_HAREKETSIZ")),
    )),
    "yetkisiz giriş/müdahale": AileSpeki("yetkisiz giriş/müdahale", (
        _KISI,
        _q(
            "gorunur_sinir_ihlali", "olay",
            "Yetki niyeti veya kimliği görüntüden tahmin etme. Yalnız görünür fiziksel "
            "kanıtı ölç: kişi kapalı kapı, bariyer, çit, kilitli/kısıtlı alan sınırı "
            "veya açık yasak işaretini aşarak mı giriyor; yoksa rutin açık geçişten mi "
            "yürüyor? Yalnız GORUNUR_SINIR_IHLALI, RUTIN_ACIK_GECIS, "
            "SINIR_ISARETI_YOK, KISI_YOK veya GORUNMUYOR yaz.",
            ("GORUNUR_SINIR_IHLALI", "RUTIN_ACIK_GECIS", "SINIR_ISARETI_YOK",
             "KISI_YOK", "GORUNMUYOR"), ("GORUNUR_SINIR_IHLALI",),
            ("RUTIN_ACIK_GECIS", "SINIR_ISARETI_YOK", "KISI_YOK")),
    )),
    "KKD eksikliği": AileSpeki("KKD eksikliği", (
        _KISI,
        _q(
            "gorunur_kkd", "algi",
            "İddiaya konu çalışanın başı ve gövdesi yeterli büyüklükte seçiliyor mu ve "
            "zorunlu olduğu iddia edilen baret/reflektif yelek eksikliği açıkça "
            "görülüyor mu? Uzak, örtülü veya pikseli yetersiz kişide eksiklik varsayma. "
            "Yalnız KKD_EKSIK_ACIK, KKD_TAM, POLITIKA_BILINMIYOR veya GORUNMUYOR yaz.",
            ("KKD_EKSIK_ACIK", "KKD_TAM", "POLITIKA_BILINMIYOR", "GORUNMUYOR"),
            ("KKD_EKSIK_ACIK",), ("KKD_TAM",)),
    )),
    "askıda yük/düşme bölgesi": AileSpeki("askıda yük/düşme bölgesi", (
        _q(
            "askida_yuk", "algi",
            "Videoda altı zemin/araç/yüzeyle temas etmeyen ve kanca, sapan, zincir "
            "veya halatla havada taşınan gerçek bir yük var mı? Vinç bomu veya kanca "
            "tek başına yük değildir. Yalnız ASILI_YUK, YUK_YERDE_VEYA_ARACTA, "
            "YUK_YOK veya GORUNMUYOR yaz.",
            ("ASILI_YUK", "YUK_YERDE_VEYA_ARACTA", "YUK_YOK", "GORUNMUYOR"),
            ("ASILI_YUK",), ("YUK_YERDE_VEYA_ARACTA", "YUK_YOK")),
        _q(
            "dusme_bolgesi_sure", "olay",
            "Videoyu kronolojik izle. Çalışan, askıda yük düşer veya salınırsa "
            "erişeceği bölgede kesintisiz en az 1 saniye kalıyor mu? Yalnız yakınlık, "
            "farklı derinlik, bariyer arkası ve bir saniyeden kısa geçiş ihlal değildir. "
            "Yalnız DUSME_BOLGESINDE_1S, YALNIZ_YAKIN, KISA_GECIS, "
            "FARKLI_DERINLIK_VEYA_ENGEL, ASILI_YUK_YOK, KISI_YOK veya "
            "GORUNMUYOR yaz.",
            ("DUSME_BOLGESINDE_1S", "YALNIZ_YAKIN", "KISA_GECIS",
             "FARKLI_DERINLIK_VEYA_ENGEL", "ASILI_YUK_YOK", "KISI_YOK",
             "GORUNMUYOR"), ("DUSME_BOLGESINDE_1S",),
            ("YALNIZ_YAKIN", "KISA_GECIS", "FARKLI_DERINLIK_VEYA_ENGEL",
             "ASILI_YUK_YOK", "KISI_YOK")),
    )),
    "kontrolsüz yük/çökme": AileSpeki("kontrolsüz yük/çökme", (
        _q(
            "yuk_veya_yapi", "algi",
            "Videoda olayın konusu olan gerçek bir yük, istif, raf, platform, "
            "levha, boru, ağaç veya yapı parçası açıkça görülüyor mu? Gölge, "
            "yansıma ve sıkıştırma izi nesne değildir. Yalnız YUK_YAPI_VAR, "
            "YUK_YAPI_YOK veya GORUNMUYOR yaz.",
            ("YUK_YAPI_VAR", "YUK_YAPI_YOK", "GORUNMUYOR"),
            ("YUK_YAPI_VAR",), ("YUK_YAPI_YOK",)),
        _q(
            "kontrolsuz_gecis", "olay",
            "Videoyu kronolojik izle. Yük, istif, raf, platform veya yapı "
            "başlangıçtaki destekli konumunu kaybedip kontrolsüz biçimde düşüyor, "
            "devriliyor, kopuyor, kayıyor ya da çöküyor mu? Vinç/forkliftin rutin "
            "ve kontrollü kaldırma, indirme veya taşıması olay değildir. Yalnız "
            "KONTROLSUZ_DUSME_DEVRILME_COKME, KONTROLLU_TASIMA_INDIRME, "
            "HAREKET_YOK veya GORUNMUYOR yaz.",
            ("KONTROLSUZ_DUSME_DEVRILME_COKME", "KONTROLLU_TASIMA_INDIRME",
             "HAREKET_YOK", "GORUNMUYOR"),
            ("KONTROLSUZ_DUSME_DEVRILME_COKME",),
            ("KONTROLLU_TASIMA_INDIRME", "HAREKET_YOK")),
    )),
    "makineye sıkışma/ezilme": AileSpeki("makineye sıkışma/ezilme", (
        _KISI,
        _q(
            "makine_kisi_iliskisi", "olay",
            "Videoyu kronolojik izle. Gerçek kişinin bedeni, uzvu veya giysisi "
            "hareketli/kapanan makine parçası, konveyör, araç ya da ağır nesne "
            "tarafından açıkça yakalanıyor, içeri çekiliyor, iki yüzey arasında "
            "sıkışıyor veya eziliyor mu? Makinenin yanında rutin çalışma, kısa "
            "örtülme ve yalnız tehlikeli yakınlık yeterli değildir. Yalnız "
            "SIKISMA_CEKILME_EZILME, RUTIN_YAKIN_CALISMA, YALNIZ_ORTULME, "
            "KISI_YOK veya GORUNMUYOR yaz.",
            ("SIKISMA_CEKILME_EZILME", "RUTIN_YAKIN_CALISMA", "YALNIZ_ORTULME",
             "KISI_YOK", "GORUNMUYOR"),
            ("SIKISMA_CEKILME_EZILME",),
            ("RUTIN_YAKIN_CALISMA", "YALNIZ_ORTULME", "KISI_YOK")),
    )),
}


def _temiz(cevap: object) -> str:
    return str(cevap or "").strip().upper()


def sonuclandir(spek: AileSpeki, cevaplar: Mapping[str, str],
                hatalar: Mapping[str, str] | None = None) -> KanitSonucu:
    """Saf/deterministik karar fonksiyonu; tests ve benchmark bunu dogrudan kullanir."""
    hatalar = dict(hatalar or {})
    norm = {k: _temiz(v) for k, v in cevaplar.items()}
    if hatalar:
        return KanitSonucu(spek.aile, Hukum.INSUFFICIENT, norm, hatalar)
    durumlar = []
    for soru in spek.sorular:
        c = norm.get(soru.ad, "")
        if c in soru.curutme:
            durumlar.append(Hukum.REFUTED)
        elif c in soru.destek:
            durumlar.append(Hukum.SUPPORTED)
        else:
            durumlar.append(Hukum.INSUFFICIENT)
    if Hukum.REFUTED in durumlar:
        hukum = Hukum.REFUTED
    elif durumlar and all(x == Hukum.SUPPORTED for x in durumlar):
        hukum = Hukum.SUPPORTED
    else:
        hukum = Hukum.INSUFFICIENT
    return KanitSonucu(spek.aile, hukum, norm, hatalar)


def dogrula(istemci, frames, aile: str) -> KanitSonucu:
    """Bir aileyi sabit iki API rolunde atomik sorularla dogrula."""
    spek = SPEKLER.get(aile)
    if spek is None:
        return KanitSonucu(aile, Hukum.INSUFFICIENT, {},
                           {"spek": "desteklenmeyen iddia ailesi"})
    cevaplar: Dict[str, str] = {}
    hatalar: Dict[str, str] = {}
    for soru in spek.sorular:
        try:
            rol = istemci.gorev(soru.gorev)
            cevaplar[soru.ad] = rol.analyze_frames(
                frames, soru.soru, temperature=0.0, max_tokens=ATOMIK_MAX_TOKENS,
                system=ATOMIK_SISTEM, guided_choice=soru.secenekler)
        except Exception as ex:
            hatalar[soru.ad] = f"{type(ex).__name__}: {ex}"
    return sonuclandir(spek, cevaplar, hatalar)


def dogrula_video(istemci, video, aile: str) -> KanitSonucu:
    """Kaynak/yeniden kodlanmış tek video üzerinde iki rolü bağımsız ölç.

    ``analyze_frames`` yolu örnek kareleri yeniden MP4'e kodlar. Küçük duman,
    kıvılcım ve ince temas kanıtında bu ikinci örnekleme ayrıntı kaybettirebilir.
    Bu yol aynı video baytlarını iki role taşır; ``hatirla=False`` sayesinde
    roller birbirinin cevabını görmez. Hata yine fail-closed ``INSUFFICIENT``tir.
    """
    spek = SPEKLER.get(aile)
    if spek is None:
        return KanitSonucu(aile, Hukum.INSUFFICIENT, {},
                           {"spek": "desteklenmeyen iddia ailesi"})
    try:
        oturum = istemci.video_oturumu(video, system=ATOMIK_SISTEM)
    except Exception as ex:
        return KanitSonucu(aile, Hukum.INSUFFICIENT, {},
                           {"oturum": f"{type(ex).__name__}: {ex}"})
    if not getattr(oturum, "hazir", False):
        return KanitSonucu(aile, Hukum.INSUFFICIENT, {},
                           {"oturum": getattr(oturum, "hata", None) or "kurulamadi"})
    cevaplar: Dict[str, str] = {}
    hatalar: Dict[str, str] = {}
    asil = oturum.istemci
    try:
        for soru in spek.sorular:
            try:
                oturum.istemci = istemci.gorev(soru.gorev)
                cevap = oturum.sor(
                    soru.soru, temperature=0.0, max_tokens=ATOMIK_MAX_TOKENS,
                    guided_choice=soru.secenekler, hatirla=False)
                if cevap is None:
                    hatalar[soru.ad] = getattr(oturum, "hata", None) or "cevap alinamadi"
                else:
                    cevaplar[soru.ad] = cevap
            except Exception as ex:
                hatalar[soru.ad] = f"{type(ex).__name__}: {ex}"
    finally:
        oturum.istemci = asil
    return sonuclandir(spek, cevaplar, hatalar)
