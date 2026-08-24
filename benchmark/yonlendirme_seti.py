# -*- coding: utf-8 -*-
"""D42 — ROUTER yonlendirme test seti (ON-KAYITLI).

Etiketler KOSUMDAN ONCE, hicbir model ciktisina bakilmadan belirlendi
(bkz. docs/on_kayit_router_yonlendirme_2026-08-24.md).

SINIF TANIMLARI (etiketlemenin tekrar uretilebilir olmasi icin):
  sayma          : yanit bir SAYI, MESAFE ya da GEOMETRIK KARSILASTIRMA.
  kisi_oznitelik : bir KISININ uzerindeki gorunur donanim/kiyafet.
  durum          : bir NESNENIN/ORTAMIN iki-durumlu hali (acik/kapali, yanik/sonuk...).
  genel          : ozet, gerekce, mevzuat, oneri, rapor, diyalog — tek gorsel hedefi YOK.

`zor=True` olan maddeler ON-KAYITTA tartismali ilan edildi; sonuc bunlar
DAHIL ve HARIC iki kez raporlanir (post-hoc eleme YAPILMAZ).
"""
from __future__ import annotations

# (kimlik, tur, metin, etiket, zor_mu)
# tur: "soru" = operator sorusu · "klip" = klip betimlemesi
SET = [
    # --- sayma (9) ---
    ("S1", "soru", "Forklift çatalında kaç kasa var?", "sayma", False),
    ("S2", "soru", "Görüntüde toplam kaç işçi var?", "sayma", False),
    ("S3", "soru", "Forklift ile en yakın yayanın arası kaç metre?", "sayma", False),
    ("S4", "soru", "İstiflenen yükün yüksekliği forklift direğini aşıyor mu?", "sayma", False),
    ("S5", "soru", "Sarı çizginin dışında kaç kişi duruyor?", "sayma", False),
    ("S6", "klip", "Klip: forklift, çatalında üst üste istiflenmiş kasalarla dar depo koridorunda ilerliyor.", "sayma", False),
    ("S7", "klip", "Klip: yükleme rampasında paletler yan yana dizilmiş, aralarındaki boşluk çok dar.", "sayma", False),
    ("S8", "soru", "Bu vardiyada kaç kez yaya yolu ihlali oldu?", "sayma", True),
    ("S9", "soru", "Vinç kancasının yerden yüksekliği yaklaşık kaç metre?", "sayma", False),

    # --- kisi_oznitelik (9) ---
    ("K1", "soru", "İşçi baret takıyor mu?", "kisi_oznitelik", False),
    ("K2", "soru", "Operatörün üzerinde reflektif yelek var mı?", "kisi_oznitelik", False),
    ("K3", "soru", "Kaynak yapan kişi yüz siperi kullanıyor mu?", "kisi_oznitelik", False),
    ("K4", "soru", "Forklift operatörü emniyet kemeri takmış mı?", "kisi_oznitelik", False),
    ("K5", "soru", "Alandaki kişilerden biri koruyucu eldiven takıyor mu?", "kisi_oznitelik", False),
    ("K6", "klip", "Klip: iki çalışan baretsiz şekilde şantiye sahasında yürüyor.", "kisi_oznitelik", False),
    ("K7", "klip", "Klip: bakım personelinin üzerinde turuncu tulum var, ayağında iş ayakkabısı görünmüyor.", "kisi_oznitelik", False),
    ("K8", "soru", "Merdivende çalışan kişi paraşüt tipi emniyet koşumu takıyor mu?", "kisi_oznitelik", False),
    ("K9", "klip", "Klip: vardiya amiri kask takmış ancak yanındaki ziyaretçinin başı açık.", "kisi_oznitelik", True),

    # --- durum (9) ---
    ("D1", "soru", "Elektrik panosunun kapağı açık mı?", "durum", False),
    ("D2", "soru", "Acil çıkış kapısı kapalı mı?", "durum", False),
    ("D3", "soru", "Zeminde su veya yağ birikintisi var mı?", "durum", False),
    ("D4", "soru", "Makine çalışır durumda mı, yoksa durdurulmuş mu?", "durum", False),
    ("D5", "klip", "Klip: elektrik panosunun kapağı menteşesinden sarkıyor, iç kısmı açıkta.", "durum", False),
    ("D6", "klip", "Klip: yangın tüpü dolabının camı kırık, dolap boş duruyor.", "durum", False),
    ("D7", "soru", "Yaya yolunu gösteren sarı bant zeminde görünür durumda mı?", "durum", False),
    ("D8", "klip", "Klip: koridordaki aydınlatma sönük, alan karanlık.", "durum", False),
    ("D9", "soru", "Konveyör bandının koruma muhafazası yerinde mi?", "durum", False),

    # --- genel (9) ---
    ("G1", "soru", "Bu klipte ne oldu, özetler misin?", "genel", False),
    ("G2", "soru", "Rapora göre hangi aksiyonu önerirsin?", "genel", False),
    ("G3", "soru", "Bu olay için hangi İSG mevzuatı maddesi geçerli?", "genel", False),
    ("G4", "soru", "Vardiya sonu raporunu hazırlar mısın?", "genel", False),
    ("G5", "klip", "Klip: vardiya sonunda çalışanlar alanı düzenli şekilde terk ediyor, olağandışı bir durum yok.", "genel", True),
    ("G6", "soru", "Bu bulguyu iş güvenliği uzmanına nasıl bildirmeliyim?", "genel", False),
    ("G7", "soru", "Az önce bahsettiğin riski biraz daha açar mısın?", "genel", False),
    ("G8", "klip", "Klip: ofis alanında rutin bir toplantı yapılıyor, saha faaliyeti yok.", "genel", False),
    ("G9", "soru", "Risk seviyesini neden Yüksek olarak belirledin?", "genel", False),
]

SINIFLAR = ("sayma", "kisi_oznitelik", "durum", "genel")

#: ON-KAYITLI ESLEME TABLOSU — soru_tipi -> hedef alias.
#: Bu tablo KURAL (denetlenebilir politika); MODEL-TABANLI olan kisim
#: dogal dili soru_tipi'ne cevirmektir.
HEDEF = {
    "sayma": "llm-large",        # olculdu: forklift sayma MCC +0,725
    "kisi_oznitelik": "vlm",     # olculdu: yelek MCC +0,500; llm-large 47/50 "GORUNMUYOR"
    "durum": "vlm",              # OLCULMEDI — kisi_oznitelik ile ayni gerekce (gorsel varlik)
    "genel": "llm-fast",         # OLCULMEDI — dokumantasyon: JSON/arac 1,000=1,000
}
