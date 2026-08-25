"""POLITIKA OLUMSUZLAMA KAPISI — gercek Turkce ciktida calisiyor mu?

IKI KUSUR birden yakalandi (2026-08-25):

1) U+0131 ('ı') AYRISMIYOR. `_norm` combining isaretleri siliyordu ama 'ı'
   ASCII 'i'ye donusmuyordu. Kaliplar ASCII yazildigi icin dort kol
   (bulunmadi/saptanmadi/rastlanmadi/olmadi) HIC eslesmiyordu.

2) `yok` Turkce EKLEMEYI kaciriyordu. "ihlal YOKTUR" en yaygin olumsuz
   ifadedir ama "yok" sonrasi kelime siniri olmadigi icin eslesmiyordu.

Sonuc: FAIL-CLOSED olmasi gereken kapi bes kolda ACIKTI ve "ihlal yoktur"
IHLAL sayiliyordu — yani modelin ACIKCA "ihlal yok" demesi, ihlal karari
uretiyordu.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dilajan.policy import _norm, _norm_karar

g = k = 0
def c(ad, kosul):
    global g, k
    if kosul: g += 1; print("  ok  ", ad)
    else: k += 1; print("  FAIL", ad)

print("=== NORMALIZASYON: cikti YALNIZCA ASCII olmali ===")
for ham in ("İhlal", "bulunmadı", "değildir", "görülmemiş", "yoktur", "ışık", "ÇĞİÖŞÜ"):
    n = _norm(ham)
    c(f"{ham!r} -> {n!r} sadece ASCII", all(ord(ch) < 128 for ch in n))

print()
print("=== OLUMSUZLANMIS IFADE -> BELIRSIZ (fail-closed) ===")
OLUMSUZ = ["ihlal yok", "ihlal yoktur", "ihlal yoksa",
           "İhlal tespit edilmemiştir", "ihlal görülmedi", "ihlal görülmemiştir",
           "ihlal bulunmadı", "ihlal bulunmuyor", "ihlal saptanmadı",
           "ihlal rastlanmadı", "ihlal olmadı", "ihlal olmamış",
           "ihlal değildir", "ihlal edilmedi", "no violation", "not a violation"]
for t in OLUMSUZ:
    c(f"{t!r} -> BELIRSIZ", _norm_karar(t) == "BELIRSIZ")

print()
print("=== OLUMLU KARAR DUSURULMEMELI ===")
for t, bek in (("İHLAL", "IHLAL"), ("ihlal", "IHLAL"), ("violation", "IHLAL"),
               ("uygun", "UYGUN"), ("compliant", "UYGUN"),
               ("belirsiz", "BELIRSIZ")):
    c(f"{t!r} -> {bek}", _norm_karar(t) == bek)

print()
print("=== GEREKCELI KARAR YANLISLIKLA DUSURULMEMELI ===")
# "IHLAL (baret yok)" — parantez ici gerekce; karar IHLAL kalmali.
c("'IHLAL (baret yok)' IHLAL kalir", _norm_karar("IHLAL (baret yok)") == "IHLAL")

print()
print(f"gecen={g}  kalan={k}")
sys.exit(1 if k else 0)
