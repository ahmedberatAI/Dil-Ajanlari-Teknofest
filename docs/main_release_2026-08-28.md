# Main sürüm kaydı — 2026-08-28

Bu kayıt, 2026-08-27/28 İSG güvenilirlik çalışmalarından `main` dalına alınan
durumu özetler. Çalışan modeller değiştirilmemiştir: `vlm`, `llm-large` ve
`llm-fast`. Öğrenilmiş çıkarım yalnız
`https://evren-llmapi.ssyz.org.tr/v1` özel API'si üzerinden yapılır; yerel model
indirme ve yerel öğrenilmiş çıkarım varsayılan olarak kapalıdır.
Eksik veya boş API adresi artık sessizce yerel vLLM'e düşmez; temiz kurulum da
sabit özel API'yi ve yalnız bu üç model takma adını kullanır.

## Korunan çalışma yolu

- Serbest İSG iddiaları nesne/olgu ve fiziksel ilişki/zaman atomlarına ayrılır;
  yalnız gerekli kanıtların tamamı destekliyse olay tutulur.
- Duman/plüm gözlemi tek başına akut yangın veya sevk sinyali sayılmaz.
- KKD iddiası yalnız tesisin açıkça zorunlu kıldığı ve ölçülebilen kalemlerde
  üretilebilir.
- Deneysel recall fallback'leri, bağımsız kabul kapıları geçmediği için
  varsayılan olarak kapalıdır.
- Art arda yüklenen videoların analiz durumları birbirinden yalıtılmıştır.

## InspecSafe-V1 karar profilleri

Birincil geliştirme profili
`benchmark/results/inspecsafe_hier_primary_receipt_1561cd7592a2e498.json`
içinde kilitlenmiştir:

- mimari: `hybrid`
- rescue eşiği: `0.70`
- veto eşiği: `0.21`
- calibration kapsamı: 734/734
- unsafe recall: %78,47
- normal FPR: %3,00
- test-öncüllü unsafe precision/F1: %86,80 / %82,43

Katı gerilemesizlik profili ayrıca
`benchmark/results/inspecsafe_hier_lock_1561cd7592a2e498.json` içinde korunur.
Birincil profil henüz development ve holdout kapılarını geçmediği için sonucu
"nihai saha skoru" olarak yorumlanmamalıdır. InspecSafe hiyerarşisi sürümlü
benchmark karar yoludur; genel video arayüzündeki olay çıkarımı kanıt-temelli
ajan grafiğinden geçer.

Deneysel açık-öncül veto katmanı main çalışma yoluna alınmamıştır: calibration
üzerinde FP sayısını 11'den düşürmedi ve FN sayısını 79'dan 83'e yükseltti.

## Doğrulama ve temizlik

- 78 pytest testi geçti.
- 47 bağımsız tarihsel denetim betiği geçti.
- 61 yeni JSON artefaktının tamamı ayrıştırıldı.
- Güncel Python kaynaklarının tamamı bytecode derlemesinden geçti.
- API anahtarı veya gizli değer commit kapsamına alınmadı.
- Yeniden üretilebilir journal/checkpoint dosyaları ve cache'ler temizlendi.
- 62.928.173 bayt ham/tekrarlı sonuç silinmeden yerel, Git-dışı
  `outputs/benchmark_raw_archive_2026-08-28/` dizinine taşındı.
