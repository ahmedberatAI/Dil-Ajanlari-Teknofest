# NVIDIA geliştirme görünürlük etiketi — revizyon 2

**Tarih:** 2026-08-27  
**Kapsam:** `benchmark/nvidia_sdg_dev_visibility.json` yangın kamera etiketleri  
**Önemli:** Bu düzeltme model çıktısı görüldükten sonra yapıldı. Geliştirme/tanı amaçlıdır;
bağımsız final performans kanıtı sayılamaz.

## Hata

İlk 320 piksel temas sayfaları dumanı kaçırdı. Bunun ardından kaynak çözünürlükte yapılan ilk
düzeltme ise ters yönde aşırıya gitti: `Fire` senaryo adını ve insanların kaçışını kamera-bazlı
doğrudan yangın kanıtına sızdırarak iki koşuda toplam 8/10 kamerayı görünür-pozitif saydı.

Kaynak 1920×1080, 1 fps, 3×3 temas sayfaları yeniden incelendi. Doğrudan biçim değiştiren/yayılan
siyah-gri duman yalnız şu iki görüşte açıktır:

- `001b05...run_1.../ceiling_01`
- `002ad0...run_4.../ceiling_01`

Diğer `ceiling_00/02/03/04` görüşlerinde kaçan insanlar görünür; doğrudan alev, duman veya yanan
nesne görünmez. Yangın/duman slotu davranıştan neden çıkarmaz.

Denetim varlıkları:

- `data/dev_nvidia_warehouse/_visibility_detail/fire__001b05ebcbc9f4ca0755_run_1_seed_1308650293__ceiling_00__native_1fps.jpg`
- `data/dev_nvidia_warehouse/_visibility_detail/fire__001b05ebcbc9f4ca0755_run_1_seed_1308650293__ceiling_01__native_1fps.jpg`
- `data/dev_nvidia_warehouse/_visibility_detail/fire__001b05ebcbc9f4ca0755_run_1_seed_1308650293__ceiling_02__native_1fps.jpg`
- `data/dev_nvidia_warehouse/_visibility_detail/fire__001b05ebcbc9f4ca0755_run_1_seed_1308650293__ceiling_04__native_1fps.jpg`
- `data/dev_nvidia_warehouse/_visibility_detail/fire__002ad0d8fa9252052de6_run_4_seed_2134546766__ceiling_01__native_1fps.jpg`
- `data/dev_nvidia_warehouse/_visibility_detail/fire__002ad0d8fa9252052de6_run_4_seed_2134546766__ceiling_02__native_1fps.jpg`
- `data/dev_nvidia_warehouse/_visibility_detail/fire__002ad0d8fa9252052de6_run_4_seed_2134546766__ceiling_03__native_1fps.jpg`

## Etki ve koruma

- Geliştirme yangın paydası 8 görünür kameradan 2 görünür kameraya iner.
- Senaryo recall'u ayrıca raporlanabilir; fakat görünmeyen kamera, doğrudan-duman recall paydasına girmez.
- Revizyon model sonucundan sonra yapıldığı için buradaki puan yalnız tuning geri bildirimi sayılır.
- Bağımsız holdout görünürlük dosyası, model koşturulmadan önce aynı doğrudan-fiziksel-kanıt
  ölçütüyle dondurulacak ve sonradan değiştirilmeyecektir.
