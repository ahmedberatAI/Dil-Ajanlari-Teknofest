"""KANIT SORULARI (ASK-HINT deseni) — ikili gorsel sorulardan OLAY ADI ipucu.

LITERATUR (arXiv 2510.02155, WACV 2026)
---------------------------------------
Tek bir "ne oldu?" uretici cagrisi yerine sinif basina INCE-TANELI EYLEM sorulari uretilir
("Ates ya da duman var mi?"); havuz VLM-gudumlu secimle 42 sorudan 6 temsili soruya
SIKISTIRILIR ve HER SORU AYRI IKILI CAGRI olarak sorulur, skorlar birlestirilir.
Olculen: UCF-Crime AUC 74.50 -> 89.83 (DONMUS model, taban Qwen2.5-VL-7B).
KRITIK AYRINTI: sikistirilmamis TAM havuz 67.17 puana DUSUYOR — yani COK SORU SORMAK
ZARARLIDIR. Bu yuzden buradaki setler EN FAZLA 4 soru icerir (K4 gecikme tavani ayni yone
bastigi icin 6 degil 4).

!!! LITERATURDEN BILINCLI SAPMA — BIZIM PROBLEMIMIZ FARKLI !!!
----------------------------------------------------------------
Makale IKILI ANOMALI SKORU (AUC) uretir. Bizim recall'umuz eval_holdout'ta ZATEN %96-100 —
makalenin kapattigi bosluk BIZDE YOK. Bizim olculen bosluğumuz SINIF ADLANDIRMA (%46).
Bu yuzden desen AYNEN kopyalanmadi:

  1. Sorular anomaliyi TESPIT ETMEK icin degil, ZATEN TESPIT EDILMIS bir olayi ADLANDIRMAK
     icin sorulur. Soru yanitlari HICBIR skora, esige veya alarma girmez.
  2. Uretilen ipucu YALNIZCA `Event.event` METNINI etkiler. severity / category / risk /
     sevk zinciri KODDA dokunulmaz kalir (bkz. graph._kanit_ile_adlandir: alanlar
     `model_copy(update={"event": ...})` ile tasinir, yalniz TEK alan degisir).
  3. Sorular YALNIZCA en az bir olay zaten cikarilmissa sorulur (graph._kanit_adlandirma
     ilk satiri). Olaysiz klipte TEK CAGRI bile yapilmaz.

!!! DUZELTME — bu kosul FP guvenligi icin TEK BASINA YETMEZ (adversaryel denetim) !!!
"Normal klipte olay yoktur" varsayimi OLCULDU ve YANLIS cikti: son eval kosusunda 8 normal
klipin 3'u olay uretiyor (biri Orta severity). Yani madde 3, normal kliplerin YALNIZ bir
kismini korur. Gercek FP guvenligi graph.py'deki G4 ALARM MUHAFIZI'na dayanir:
  * `reexamine` hakemi HER ZAMAN kanit-ONCESI metni gorur (Event.evidence_prev) ->
    severity Orta->Yuksek yukseltmesi ozellikten ETKILENMEZ,
  * `act` sevk kapisinda RISK terimi, adlandirma yapildiysa MASKELENIR.
Muhafiz olmadan olculen kusur: severity Orta->Yuksek, sevk [] -> ['guvenlik_ekibi_uyar'].

SORULARIN SECIMI
----------------
Hedef kategoriler (data/eval_holdout): RoadAccidents, Explosion, Fighting, Assault, Abuse,
Burglary, Shooting, Vandalism. Sorular AYIRT EDICI secildi: her biri FARKLI bir semantik
grubu ayirir, ortusme minimumdur (kisi-kisi siddeti / arac / yanma-patlama / mulke yonelik).

SHOOTING BILEREK KOVALANMIYOR: uc kolda ve dort skorlama kuralinda 0/3 kaldi; 320x240
grenli karede silah ~16 piksel — bilgi karede FIZIKSEL OLARAK YOK. Bir soruyu ona harcamak
hem butceyi (bkz. "cok soru zararlidir") hem de yanlis-pozitif yuzeyini bosuna buyutur.
Silah/ates kelimeleri ayrica HICBIR veto listesinde YOKTUR: model betimlemeye dayanarak
"silahli saldiri" demek isterse bu modul onu ENGELLEMEZ.

Grup adlari benchmark/labels.py `SEMANTIC_GROUPS` ile BIREBIR AYNIDIR (Siddet / MalSuclari /
Yikim / Trafik / Dusme) — degerlendirme tarafiyla ayni sozluk kullanilir, yeni bir taksonomi
UYDURULMAZ.

TURKCE BUYUK-I TUZAGI (graph.py:894-905'te ayni tuzak var)
----------------------------------------------------------
`"Hayır".upper()` -> "HAYIR", ama `"HAYIR".lower()` -> "hayir" (NOKTALI i) ve
`"Hayır".lower()` -> "hayır" (NOKTASIZ ı). Yani tek bir `.lower()` + ASCII alt-dizge
karsilastirmasi iki yazimdan BIRINI SESSIZCE KACIRIR. Cozum: `katla()` once Turkce
buyuk-I ayrimini cozer, sonra metni ASCII'ye katlar -> "Hayır", "Hayir", "HAYIR", "hayır"
HEPSI "hayir" olur. (dilajan/policy.py `_yes` bu katlamayi YAPMAZ; orada sonuc fail-closed
oldugu icin zararsizdir, burada ise yanlis "bilinmiyor" demek ipucunu bosa dusururdu.)

Bu modul KASITLI OLARAK saftir: yalniz stdlib kullanir, `dilajan.config`/`llm_client`/
LangGraph ICE AKTARMAZ. Birlestirme kurali SAF ve DETERMINISTIKTIR -> GPU'suz test edilir.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

# --- yanit etiketleri (tek kaynak-dogru) ---
EVET = "evet"
HAYIR = "hayir"
BILINMIYOR = "bilinmiyor"

#: Operatore/karar-izine gosterilecek Turkce etiketler.
ETIKET: Dict[str, str] = {EVET: "Evet", HAYIR: "Hayır", BILINMIYOR: "Bilinmiyor"}

#: Ipucu uretmek icin izin verilen AZAMI "Evet" sayisi. Bunun USTU = model AYIRT ETMIYOR
#: (her soruya evet diyen bir yanit dizisi bilgi tasimaz, yalnizca yanlis-pozitif tasir)
#: -> ipucu tamamen BASTIRILIR. Bu, "cok soru zararlidir" bulgusunun yanit tarafindaki
#: karsiligidir ve ayni zamanda "hepsine EVET diyen model" saldirisina karsi kapidir.
MAX_EVET = 2

#: Onerilen olay adinin azami uzunlugu (karakter). Ustu = model ad yerine paragraf yaziyor.
MAX_AD_UZUNLUK = 160


# ---------------------------------------------------------------------------
# 1) TURKCE-GUVENLI NORMALIZASYON
# ---------------------------------------------------------------------------
#: Turkce'ye ozgu harfleri ASCII karsiliklarina katlar (yalniz ESLESME icin; cikti metni
#: hicbir zaman katlanmis haliyle kullanilmaz).
_KATLAMA = str.maketrans({
    "ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c",
    "â": "a", "î": "i", "û": "u", "ê": "e",
})


def katla(metin: object) -> str:
    """TURKCE-GUVENLI kucuk harf + ASCII katlama (yalniz eslesme amacli).

    Sira ONEMLIDIR: once "I"->"ı" ve "İ"->"i" (Turkce buyuk-I ayrimi), SONRA `lower()`,
    sonra U+0307 (birlesik nokta) temizligi, en son ASCII katlama. Boylece
    "HAYIR" / "Hayır" / "Hayir" / "hayır" -> HEPSI "hayir".

    FAIL-OPEN: str olmayan girdi (sayi/sozluk/None) metne cevrilir, asla istisna atmaz.
    """
    if metin is None:
        return ""
    if not isinstance(metin, str):
        try:
            metin = str(metin)
        except Exception:
            return ""
    s = metin.replace("I", "ı").replace("İ", "i").lower().replace("̇", "")  # U+0307 BIRLESIK NOKTA (gorunmez) — acikca yazildi
    return s.translate(_KATLAMA)


# ---------------------------------------------------------------------------
# 2) SORU HAVUZU
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Soru:
    """Tek bir IKILI kanit sorusu ve tasidigi kategori kanitinin eslemesi."""

    sid: str                      #: kisa kimlik (karar-izinde gorunur): "S1"
    grup: str                     #: benchmark/labels.py SEMANTIC_GROUPS ile AYNI grup adi
    metin: str                    #: modele sorulan Turkce ikili soru
    adlar: str                    #: "Evet" halinde ipucunda onerilecek olay ADLARI
    kategoriler: Tuple[str, ...]  #: kanit tasidigi UCF-Crime sinif adlari (aciklanabilirlik)
    kokler: Tuple[str, ...]       #: VETO kokleri — ASCII-katlanmis, bkz. ad_kabul_edilebilir_mi


#: SOKAK SUCU seti (data/eval_holdout profili). Dort soru, dort AYRI semantik grup.
_SOKAK: Tuple[Soru, ...] = (
    Soru(
        sid="S1", grup="Siddet",
        metin=("Görüntüde iki veya daha fazla kişi arasında saldırgan fiziksel temas "
               "(vurma, itme, tekmeleme, boğuşma, birinin yere savrulması) var mı?"),
        adlar="kavga / fiziksel saldırı / darp",
        kategoriler=("Fighting", "Assault", "Abuse"),
        kokler=("kavga", "dovus", "saldir", "darp", "siddet", "yumruk", "tekme",
                "bogus", "arbede", "istismar", "taciz", "gasp"),
    ),
    Soru(
        sid="S2", grup="Trafik",
        metin=("Görüntüde bir araç çarpıştı, bir kişiye veya nesneye çarptı, devrildi "
               "ya da kontrolden çıktı mı?"),
        adlar="trafik kazası / araç çarpması / aracın devrilmesi",
        kategoriler=("RoadAccidents",),
        kokler=("kaza", "carp", "devril", "takla", "ezil", "trafik"),
    ),
    Soru(
        sid="S3", grup="Yikim",
        metin="Görüntüde ateş, alev, duman veya patlama var mı?",
        adlar="yangın / duman / patlama",
        kategoriler=("Explosion", "Fire", "Smoke"),
        # NOT: "ates" bilerek VETO listesinde DEGIL — "ateş açtı" (silahli olay) ifadesini
        # yanlislikla engellememek icin. Yangin vetosu icin daha ozgul kokler yeterlidir.
        kokler=("yangin", "alev", "duman", "patla", "infilak", "tutus", "kundak", "parlama"),
    ),
    Soru(
        sid="S4", grup="MalSuclari",
        metin=("Bir kişi bir kapıyı, camekânı, kilidi, aracı veya başka bir mülkü zorluyor, "
               "kırıyor ya da bir eşyayı alıp kaçıyor mu?"),
        adlar="hırsızlık / zorla giriş / vandalizm (mala zarar verme)",
        kategoriler=("Burglary", "Vandalism"),
        kokler=("hirsiz", "soygun", "vandal", "tahrip", "caldi", "calin", "calma",
                "zorla gir", "izinsiz gir", "yetkisiz gir", "kirdi", "kiriyor", "kirma"),
    ),
)

#: TESIS seti (savunma/endustriyel dagitim profili). Ayni cerceve, farkli olay evreni.
_TESIS: Tuple[Soru, ...] = (
    Soru(
        sid="T1", grup="Yikim",
        metin="Görüntüde ateş, alev, duman veya patlama var mı?",
        adlar="yangın / duman / patlama",
        kategoriler=("Fire", "Smoke", "Explosion"),
        kokler=("yangin", "alev", "duman", "patla", "infilak", "tutus", "kundak", "parlama"),
    ),
    Soru(
        sid="T2", grup="Dusme",
        # NOT: acikayrac SORU ISARETINDEN ONCE gelir ve "DEĞİL" kelimesi KULLANILMAZ.
        # Gerekce: soru yankilandiginda ("... mi? EVET") ayristirici yalniz "?" SONRASINI
        # okur; ayrica soru metninde olumsuzluk belirteci bulunmasi yankiyi bozardi.
        metin=("Bir kişi yere/zemine düştü, çöktü veya doğrudan yerde hareketsiz kaldı mı "
               "(yatağa/koltuğa uzanmak ya da çömelmek bu soruya girmez)?"),
        adlar="bir kişinin yere düşmesi / yerde hareketsiz kalması",
        kategoriler=("Fall",),
        kokler=("dusme", "dustu", "yigil", "bayil", "baygin", "hareketsiz"),
    ),
    Soru(
        sid="T3", grup="Trafik",
        metin=("Bir araç, forklift veya iş makinesi çarptı, devrildi ya da taşıdığı yükü "
               "düşürdü mü?"),
        adlar="araç/forklift kazası / devrilme / yük düşmesi",
        kategoriler=("RoadAccidents",),
        kokler=("kaza", "carp", "devril", "takla", "ezil"),
    ),
    Soru(
        sid="T4", grup="MalSuclari",
        metin=("Bir kişi çit, kapı, bariyer veya kilit aşarak/zorlayarak kısıtlı bir alana "
               "izinsiz giriyor mu?"),
        adlar="yetkisiz/izinsiz giriş / kısıtlı bölge ihlali",
        kategoriler=("Burglary",),
        kokler=("hirsiz", "soygun", "zorla gir", "izinsiz gir", "yetkisiz gir", "ihlal"),
    ),
)

SORU_SETLERI: Dict[str, Tuple[Soru, ...]] = {"sokak": _SOKAK, "tesis": _TESIS}
VARSAYILAN_SET = "sokak"


def soru_seti(ad: Optional[str] = None) -> Tuple[Soru, ...]:
    """Ada gore soru setini dondurur. Bilinmeyen/bos ad -> VARSAYILAN set (FAIL-OPEN)."""
    return SORU_SETLERI.get(katla(ad).strip(), SORU_SETLERI[VARSAYILAN_SET])


# ---------------------------------------------------------------------------
# 3) YANIT AYRISTIRMA (saglam, asla cokmez)
# ---------------------------------------------------------------------------
# Model "Evet", "evet.", "Evet, iki kişi...", "Hayır", "Hayir", "HAYIR", "Bilmiyorum",
# "" veya tamamen alakasiz metin dondurebilir. Kural: metindeki ILK KARARLI belirtec
# kazanir (modeller kararlarini basa yazar: "Evet, iki kişi ..." -> EVET).
# Ayni konumda cakisirsa sira BILINMIYOR > HAYIR > EVET'tir (temkinli yon: belirsizlik
# ve olumsuzluk, ipucu URETMEME yonunde calisir).
#
# "VAR" BILEREK EVET BELIRTECI DEGILDIR: sorularin hepsi "... var mı?" ile biter; kucuk
# max_tokens'ta bile modelin soruyu YANKILAMASI ("... var mı? HAYIR") mumkundur ve ciplak
# "var" belirteci bu yankiyi YANLIS EVET'e cevirirdi — yani tam da yanlis-pozitif yonunde.
# Yankisiz bir "Var." yaniti ise BILINMIYOR'a duser (ipucu uretilmez): guvenli yon.
# TURKCE EKLEME (agglutinasyon) TUZAGI — adversaryel denetimde OLCULDU:
# `\bdegil\b` yalniz CIPLAK "degil"i yakalar; "degilim / degiliz / degildir / degilse"
# HICBIRINI yakalamaz. Bu yuzden "emin degilim ama evet" yaniti (cekinceli, BILINMIYOR
# olmasi gereken) EVET olarak siniflaniyordu — yani tam da YANLIS-POZITIF yonunde.
# Cozum: Turkce ek alabilen koklerde `\w*` kuyruk toleransi.
_EVET_RE = re.compile(r"\b(evet|dogru|olumlu|mevcut|goruluyor|goruldu|yes)\b")
_HAYIR_RE = re.compile(
    r"\b(hayir|olumsuz|gorunmuyor|gorulmuyor|gorulmedi|no)\b"
    r"|\byok(tur|tu)?\b|\bdegil\w*")
_BILINMIYOR_RE = re.compile(
    r"\b(bilinmiyor|bilmiyor|belirsiz|kararsiz|anlasilmiyor|secilemiyor|unknown)\w*"
    r"|\b(net|emin|kesin|belli)\s+degil\w*")


def yanit_ayristir(ham: object) -> str:
    """Ham model yanitini {EVET, HAYIR, BILINMIYOR} etiketlerinden birine indirger.

    ASLA ISTISNA FIRLATMAZ; taninmayan/bos metin -> BILINMIYOR (temkinli varsayilan,
    ipucu URETILMEZ). Turkce buyuk-I tuzagi icin bkz. `katla()`.
    """
    metin = katla(ham).strip()
    if not metin:
        return BILINMIYOR
    # SORU YANKISI TUZAGI (adversaryel denetimde OLCULDU): kucuk max_tokens'ta model
    # once soruyu TEKRARLAYIP sonra yanitlayabilir ("... var mi? HAYIR"). Soru METNININ
    # KENDISI belirtec icerebilir (or. icinde "DEGIL" gecen bir soru) -> yanki, yaniti
    # SESSIZCE ters cevirirdi. Bu yuzden yalniz SON "?"den SONRAKI kuyruk degerlendirilir.
    # Kuyruk bossa model soruyu tekrarlamis ama YANIT VERMEMISTIR -> BILINMIYOR (dogru ve
    # guvenli yon). Tum soru metinleri "?" ile BITER; testte assert edilir.
    if "?" in metin:
        metin = metin.rsplit("?", 1)[-1].strip()
        if not metin:
            return BILINMIYOR
    adaylar = []
    # oncelik: ayni konumda cakisma olursa BILINMIYOR(0) > HAYIR(1) > EVET(2) — temkinli yon.
    for oncelik, (etiket, kalip) in enumerate(
            ((BILINMIYOR, _BILINMIYOR_RE), (HAYIR, _HAYIR_RE), (EVET, _EVET_RE))):
        m = kalip.search(metin)
        if m:
            adaylar.append((m.start(), oncelik, etiket))
    if not adaylar:
        return BILINMIYOR
    return min(adaylar)[2]  # en erken konum kazanir; esitlikte oncelik sirasi


# ---------------------------------------------------------------------------
# 4) BIRLESTIRME (SAF FONKSIYON — deterministik, test edilebilir)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class KanitOzeti:
    """Kanit sorularinin birlestirilmis sonucu.

    `ipucu` BOS ise cagiran taraf HICBIR SEY yapmaz (ad degismez, ek cagri yapilmaz).
    """

    yanitlar: Tuple[Tuple[str, str], ...]   #: (sid, etiket) ciftleri — kayit/izlenebilirlik
    evet_sorulari: Tuple[Soru, ...]
    hayir_sorulari: Tuple[Soru, ...]
    ipucu: str                              #: adlandirma promptuna girecek metin ("" = yok)
    durum: str                              #: "ipucu" | "kanit-yok" | "cakisma" | "soru-yok"
    ozet_satiri: str                        #: karar-izine yazilacak TEK satir

    @property
    def gruplar(self) -> Tuple[str, ...]:
        """Ipucunu destekleyen semantik grup adlari (yoksa bos demet)."""
        return tuple(s.grup for s in self.evet_sorulari) if self.ipucu else ()


def _ipucu_metni(evet: Sequence[Soru]) -> str:
    """Ipucu blogu — YALNIZ ADLANDIRMA icin. Onem derecesi/risk BILINCLI olarak dislanir."""
    if len(evet) == 1:
        return ("KANIT: Karelere ayrı ayrı sorulan ikili kanıt sorularından biri EVET yanıtı "
                f"verdi -> {evet[0].adlar}. Olayın ADINI bu kanıtla TUTARLI ve BELİRLİ biçimde "
                "yaz; 'anormal durum', 'bir şeyler oluyor', 'fiziksel temas' gibi genel/zayıf "
                "ifadeler yerine olayın TÜRÜNÜ adlandır.")
    liste = " ; ".join(s.adlar for s in evet)
    return ("KANIT: Birden fazla ikili kanıt sorusu EVET yanıtı verdi -> " + liste + ". Bu "
            "kanıtlar ÇELİŞEBİLİR; sahne açıklamasında GERÇEKTEN karşılığı olanı SEÇ, hepsini "
            "birden yazma. Karşılığını göremediğin kanıtı ada KATMA.")


def birlestir(sorular: Sequence[Soru], yanitlar: Sequence[object]) -> KanitOzeti:
    """(soru, yanit) ciftlerinden kategori ipucu uretir — SAF ve DETERMINISTIK.

    `yanitlar` ogeleri ya normalize etiket (EVET/HAYIR/BILINMIYOR) ya da HAM model metni
    olabilir; ham metin `yanit_ayristir` ile indirgenir.

    ELE ALINAN DURUMLAR:
      * hicbir "Evet" yok            -> ipucu URETILMEZ (ad degismez; recall/FP'ye dokunmaz)
      * tek "Evet"                   -> o grubun adlari onerilir
      * iki "Evet" (cakisma)         -> ikisi de yazilir + "gercekten gordugunu SEC" talimati
      * MAX_EVET'ten fazla "Evet"    -> model AYIRT ETMIYOR -> ipucu BASTIRILIR
      * "Bilinmiyor"/bos/sacma yanit -> hicbir yone kanit saymaz (ne evet ne hayir)
      * soru yok / uzunluk uyusmaz   -> guvenli bos ozet
    """
    ciftler: list = []
    for soru, ham in zip(list(sorular or ()), list(yanitlar or ())):
        etiket = ham if ham in (EVET, HAYIR, BILINMIYOR) else yanit_ayristir(ham)
        ciftler.append((soru, etiket))

    evet = tuple(s for s, y in ciftler if y == EVET)
    hayir = tuple(s for s, y in ciftler if y == HAYIR)

    if not ciftler:
        durum, ipucu, sonuc = "soru-yok", "", "soru sorulmadı"
    elif not evet:
        durum, ipucu = "kanit-yok", ""
        sonuc = "hiçbir soru EVET demedi -> ipucu ÜRETİLMEDİ (olay adı değişmez)"
    elif len(evet) > MAX_EVET:
        durum, ipucu = "cakisma", ""
        sonuc = (f"{len(evet)}/{len(ciftler)} soruya birden EVET -> ayırt edici değil, "
                 "ipucu BASTIRILDI")
    else:
        durum = "ipucu"
        ipucu = _ipucu_metni(evet)
        sonuc = "ipucu -> " + ", ".join(s.grup for s in evet)

    detay = " · ".join(f"{s.sid}({s.grup})={ETIKET.get(y, y)}" for s, y in ciftler) or "(yok)"
    return KanitOzeti(
        yanitlar=tuple((s.sid, y) for s, y in ciftler),
        evet_sorulari=evet, hayir_sorulari=hayir,
        ipucu=ipucu, durum=durum,
        ozet_satiri=f"kanıt soruları: {detay} -> {sonuc}",
    )


def kanit_blok(ozet: KanitOzeti, sorular: Sequence[Soru]) -> str:
    """Adlandirma promptuna girecek "soru -> yanit" listesi (aciklanabilirlik + kisitlama)."""
    by_id = {s.sid: s for s in (sorular or ())}
    satirlar = []
    for sid, etiket in ozet.yanitlar:
        soru = by_id.get(sid)
        if soru is None:
            continue
        satirlar.append(f'- "{soru.metin}" -> {ETIKET.get(etiket, etiket).upper()}')
    return "\n".join(satirlar) or "- (kanıt sorusu yok)"


# ---------------------------------------------------------------------------
# 5) VETO — onerilen ad, "Hayir" denen kanitla CELISEMEZ
# ---------------------------------------------------------------------------
#: Turkce disi script (Cince/Japonca/Korece/Kiril/Arapca/Tayca) — graph._FOREIGN ile ayni amac.
_YABANCI = re.compile(r"[一-鿿぀-ヿ가-힯Ѐ-ӿ؀-ۿ฀-๿]")


def ad_kabul_edilebilir_mi(ad: object, ozet: KanitOzeti) -> Tuple[bool, str]:
    """Onerilen olay ADI kabul edilebilir mi? (bool, red_sebebi) doner.

    RED (eski ad korunur) sartlari:
      * bos / cok uzun / Turkce disi karakter iceren ad,
      * kanit sorusu ACIKCA "Hayır" demis bir olguyu ada yazma denemesi
        (or. yangin sorusu Hayır iken adin "yangın" demesi).
    "Bilinmiyor" yanitlari VETO ETMEZ (bilgi yoklugu yasak degildir) — model betimlemeye
    dayanarak yine de adlandirabilir. Boylece soru sorulmayan bir olgu (or. silahli olay)
    hicbir zaman engellenmez.
    """
    if not isinstance(ad, str) or not ad.strip():
        return False, "boş ad"
    if len(ad) > MAX_AD_UZUNLUK:
        return False, f"ad çok uzun ({len(ad)} > {MAX_AD_UZUNLUK})"
    if _YABANCI.search(ad):
        return False, "Türkçe dışı karakter"
    metin = katla(ad)
    for soru in ozet.hayir_sorulari:
        for kok in soru.kokler:
            if kok in metin:
                return False, f"{soru.sid} 'Hayır' dedi ama önerilen ad '{kok}' içeriyor"
    return True, ""
