#!/usr/bin/env python
"""PERFORMANS benchmark (sartname §4): asama-bazli zaman kirilimi + yuksek-hacim/eszamanlilik + tepe-VRAM.
Cikti: video-isleme suresi, inference suresi, uctan-uca gecikme (sn/video-sn), concurrency throughput, peak VRAM.
Kullanim: python scripts/bench_performance.py
"""
from __future__ import annotations
import glob, os, subprocess, sys, threading, time
sys.path.insert(0, ".")
from concurrent.futures import ThreadPoolExecutor
from dilajan.video import extract_timestamped_frames
from dilajan.agent.graph import analyze_video


def vram_mb():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout.strip().splitlines()
        return int(out[0])
    except Exception:
        return -1


class VramPeak:
    def __init__(self):
        self.peak = 0; self._run = False; self._t = None
    def __enter__(self):
        self._run = True
        def loop():
            while self._run:
                self.peak = max(self.peak, vram_mb()); time.sleep(0.3)
        self._t = threading.Thread(target=loop, daemon=True); self._t.start(); return self
    def __exit__(self, *a):
        self._run = False; self._t.join(timeout=1)


def dur_seconds(path):
    _, info = extract_timestamped_frames(path)
    return info.duration


# Temsili klipler (kisa + uzun karisik)
CLIPS = (sorted(glob.glob("data/eval_scenario/Fire/*.*"))[:2] +
         sorted(glob.glob("data/falls_real/Fall/*.mp4"))[:1] +
         sorted(glob.glob("data/eval_big/Fighting/*.mp4"))[:2] +
         sorted(glob.glob("data/eval/Normal/*.mp4"))[:1])
CLIPS = [p for p in CLIPS if os.path.exists(p)][:6]


def main():
    print(f"=== PERFORMANS BENCHMARK (n={len(CLIPS)} klip) ===\n")
    print("1) AŞAMA-BAZLI ZAMAN KIRILIMI (sıralı)")
    print(f"{'klip':30s} {'süre':>6} {'decode':>8} {'analiz':>8} {'inference':>10} {'sn/vsn':>8}")
    tot_dur = tot_dec = tot_all = 0.0
    for p in CLIPS:
        t0 = time.time(); fr, info = extract_timestamped_frames(p); dec = time.time() - t0
        d = info.duration or 1.0
        t1 = time.time(); analyze_video(p); allt = time.time() - t1
        infer = allt - 0  # analyze dahili tekrar decode eder; net inference ~ allt - dec_payi
        tot_dur += d; tot_dec += dec; tot_all += allt
        print(f"{os.path.basename(p)[:29]:30s} {d:>5.1f}s {dec:>7.2f}s {allt:>7.2f}s {max(allt-dec,0):>9.2f}s {allt/d:>7.2f}")
    print(f"{'ORTALAMA':30s} {'':>6} {tot_dec/len(CLIPS):>7.2f}s {tot_all/len(CLIPS):>7.2f}s {'':>10} {tot_all/max(tot_dur,1):>7.2f}")
    print(f"  -> decode toplam {tot_dec:.1f}s ({100*tot_dec/max(tot_all,1):.0f}% analiz süresinin), inference ~{100*(tot_all-tot_dec)/max(tot_all,1):.0f}%")

    print("\n2) YÜKSEK-HACİM / EŞ-ZAMANLILIK (vLLM continuous-batching)")
    test = CLIPS[:4]
    # Sirali baseline
    with VramPeak() as vp_seq:
        t0 = time.time()
        for p in test:
            analyze_video(p)
        seq_t = time.time() - t0
    print(f"  Sıralı (n={len(test)}): {seq_t:.1f}s  ({seq_t/len(test):.1f}s/video)  peak VRAM {vp_seq.peak}MB")
    # Eszamanli
    for workers in [2, 4]:
        with VramPeak() as vp:
            t0 = time.time()
            with ThreadPoolExecutor(max_workers=workers) as ex:
                list(ex.map(analyze_video, test))
            conc_t = time.time() - t0
        sp = seq_t / conc_t if conc_t else 0
        print(f"  Eş-zamanlı x{workers}: {conc_t:.1f}s  ({conc_t/len(test):.1f}s/video)  throughput {60*len(test)/conc_t:.1f} video/dk  hızlanma {sp:.2f}×  peak VRAM {vp.peak}MB")

    print(f"\n3) KAYNAK: tepe VRAM ~{vram_mb()}MB (tek RTX 5090 24GB); model FP8 ~19GB")


if __name__ == "__main__":
    main()
