#!/usr/bin/env python
"""EVREN cikarim servisine erisimi dogrular — ANAHTARI ASLA YAZDIRMAZ.

    python scripts/evren_dogrula.py

Kontrol ettikleri:
  1) .env okunuyor mu, anahtar var mi (DEGERI degil, VARLIGI)
  2) GET /v1/models — hangi alias'lar gercekten var
  3) Kota/anahtar bilgisi (/key/info)
  4) Kucuk bir sohbet cagrisi — uctan uca calisiyor mu
  5) MODEL ADI TUZAGI: dokumantasyon uyariyor — bilinmeyen model adi 404
     DONDURMEZ, sessizce llm-fast'e yonlendirilir. Bu betik, ayarlanan model
     adinin /v1/models ciktisinda GERCEKTEN bulundugunu dogrular.

Bu, bugun `guided_choice`'ta yakaladigimiz sessiz-basarisizlik ailesinin aynisi:
hata vermeden yanlis sey olculur. O yuzden olcum almadan ONCE bu kosulmalidir.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecti = 0
_kaldi = 0


def check(ad, kosul, ayrinti=""):
    global _gecti, _kaldi
    if kosul:
        _gecti += 1
        print(f"  ok   {ad}")
    else:
        _kaldi += 1
        print(f"  FAIL {ad}  {ayrinti}")


def gizle(s: str) -> str:
    """Anahtari maskeler — tam deger HICBIR ZAMAN yazdirilmaz."""
    s = (s or "")
    if len(s) < 12:
        return "***"
    return f"{s[:11]}…{s[-2:]}  (uzunluk {len(s)})"


def main() -> int:
    from dilajan.config import settings as s

    print("=== 1) yapilandirma ===")
    print(f"  base_url : {s.base_url}")
    print(f"  uzak API : {s.uzak_api_mi}")
    print(f"  model    : {s.model_name}")
    anahtar = s.etkin_api_key
    print(f"  anahtar  : {gizle(anahtar) if anahtar != 'EMPTY' else '(YOK)'}")

    if not s.uzak_api_mi:
        print("\n  ! base_url hala YEREL. .env icinde DILAJAN_API_BASE_URL ayarlayin.")
        print("    cp .env.ornek .env  ve degerleri doldurun.")
        return 2
    check("anahtar tanimli", anahtar != "EMPTY",
          "-> .env icinde DILAJAN_API_KEY yok")
    if anahtar == "EMPTY":
        return 2

    from openai import OpenAI
    ist = OpenAI(base_url=s.base_url, api_key=anahtar,
                 timeout=float(getattr(s, "api_timeout", 1800.0)), max_retries=0)

    print("\n=== 2) GET /v1/models ===")
    try:
        m = ist.models.list()
        adlar = sorted(x.id for x in m.data)
        print(f"  {len(adlar)} model: {', '.join(adlar)}")
        check("model listesi alindi", bool(adlar))
    except Exception as e:
        check("model listesi alindi", False, f"-> {type(e).__name__}: {e}")
        return 1

    print("\n=== 3) MODEL ADI TUZAGI (dokumantasyon uyarisi) ===")
    # "Bilinmeyen bir model adi gonderilmesi durumunda sistem 404 DONDURMEMEKTE,
    #  istegi SESSIZCE llm-fast hedefine yonlendirmektedir."
    check(f"ayarlanan model '{s.model_name}' listede VAR", s.model_name in adlar,
          f"-> listede yok; cagri SESSIZCE llm-fast'e gider ve YANLIS model olculur")

    print("\n=== 4) anahtar / kota bilgisi ===")
    try:
        import requests
        u = s.base_url.rsplit("/v1", 1)[0] + "/key/info"
        r = requests.get(u, headers={"Authorization": f"Bearer {anahtar}"}, timeout=30)
        print(f"  HTTP {r.status_code}  {r.text[:200]}")
        check("/key/info yanit verdi", r.status_code < 500)
    except Exception as e:
        print(f"  (atlandi: {type(e).__name__}: {e})")

    print("\n=== 5) uctan uca kucuk cagri ===")
    try:
        y = ist.chat.completions.create(
            model=s.model_name,
            messages=[{"role": "user", "content": "Tek kelimeyle cevapla: Turkiye'nin baskenti?"}],
            max_tokens=16, temperature=0.0)
        c = (y.choices[0].message.content or "").strip()
        print(f"  yanit: {c[:80]!r}")
        check("model yanit verdi", bool(c))
        kul = getattr(y, "usage", None)
        if kul:
            print(f"  token: giris={kul.prompt_tokens} cikis={kul.completion_tokens}")
    except Exception as e:
        check("model yanit verdi", False, f"-> {type(e).__name__}: {e}")

    print(f"\ngecen={_gecti}  kalan={_kaldi}")
    return 1 if _kaldi else 0


if __name__ == "__main__":
    raise SystemExit(main())
