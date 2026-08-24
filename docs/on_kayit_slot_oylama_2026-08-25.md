# ÖN KAYIT — slot düzeyinde MEDYAN OYLAMA (koşumdan ÖNCE yazıldı)

## Gözlem
Aynı yapılandırmayla iki koşum arasında çift bazlı MCC dalgalanıyor:

    forklift : +0,840  ve  +0,881
    yetkisiz : +0,689  ve  +0,608
    pano     : +0,960  ve  +0,960   (kararlı)

temperature=0 olmasına rağmen uzak servis birebir tekrar üretmiyor. Bu,
raporlanan tek bir sayının ±0,05 belirsizlik taşıdığı anlamına gelir.

## §8 AYRIMI
Daha önce **REDDEDİLEN** şey "self-consistency N=3 **severity-hibrit**"ti —
model çıktısının ÖNEM DERECESİNİ oylatmak. Buradaki mekanizma farklı:
kapalı cevap uzayındaki **sayısal bir ÖLÇÜMÜN** medyanı. Ölçüm tekrarını
ortalamak, yargıyı oylatmak değildir. Bu daha önce denenmedi.

## Kol
Her slot 3 kez sorulur (aynı video oturumu, hatirla=False → bağımsız),
sayısal slotlarda **medyan**, etiket slotlarında **çoğunluk** alınır.

## Kabul ölçütü (SONUÇTAN ÖNCE sabitlendi)
Yetkisiz müdahale çiftinde (n=50), 3 tekrarlı medyan kol:
  - MCC, tek-atış kolun **iki koşumunun ortalamasını (+0,649) en az +0,05
    geçmeli** (yani ≥ +0,70), VE
  - yanlış pozitif sayısı 4'ü geçmemeli.
Aksi halde tek-atış kalır ve dalgalanma DÜRÜSTÇE raporlanır.

Maliyet: slot çağrısı 3×. Kabul edilirse gecikme artışı ayrıca raporlanır.
