# Ön kayıt — v13 yeni geliştirme taban koşusu

Tarih: 2026-08-27  
Durum: Sonuç görülmeden kilitlendi

Veri yalnız `data/eval_genelleme_v13_dev` içindeki daha önce görülmemiş 100 tehlike
+ 100 normal kliptir. `data/eval_genelleme_holdout_v13` açılmaz.

Davranış, v12r adayının aynısıdır ve özel API'deki sabit üç modeli birlikte kullanır:
`vlm`, `llm-large`, `llm-fast`. Bayraklar: kapalı aile, asimetrik yangın vetosu,
termal fallback ve tek kapalı fiziksel scout açık; decomposition ve extended family
kapalı; yerel öğrenilmiş model/model indirme yok.

Bu bir yayın kabul koşusu değil, yeni geliştirme tabanıdır. Sonuçlar yalnız bu v13
geliştirme bölümünde sonraki hipotezleri ön kaydetmek ve ölçmek için kullanılabilir.
v12 holdout satırları/etiketleri ayar seçmekte kullanılmaz.

Yeni adayın v13 holdout'a ilerleyebilmesi için geliştirme kapısı daha sonra sonuçtan
önce ayrıca kilitlenecektir; hedef en az %75 recall, en fazla %12 normal FP,
MCC en az +0,65 ve sıfır işleme hatasıdır.
