#!/usr/bin/env python
"""Yerel vLLM OpenAI-uyumlu sunucusunu baslatir.

Kullanim:
    python serve_vllm.py

Sunucu http://127.0.0.1:8000/v1 adresinde varsayilan modeli (Qwen3-VL-8B-FP8) servis eder.
Hassasiyet-oncelikli yedek icin: DILAJAN_MODEL_NAME=Qwen/Qwen2.5-VL-7B-Instruct python serve_vllm.py
CUDA ortam degiskenleri (Blackwell/WSL) otomatik ayarlanir.
"""
from __future__ import annotations

import os
import subprocess
import sys

from dilajan.config import apply_cuda_env, settings


def main() -> None:
    apply_cuda_env()  # vLLM import edilmeden once CUDA ortamini hazirla
    # venv bin'i PATH'e ekle (ninja vb. derleme araclari icin)
    os.environ["PATH"] = os.path.dirname(sys.executable) + ":" + os.environ.get("PATH", "")

    cmd = [
        sys.executable,
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model", settings.model_name,
        "--served-model-name", settings.model_name,
        "--host", settings.vllm_host,
        "--port", str(settings.vllm_port),
        "--max-model-len", str(settings.max_model_len),
        "--gpu-memory-utilization", str(settings.gpu_memory_utilization),
        "--dtype", settings.dtype,
        "--limit-mm-per-prompt", '{"image": 16, "video": 1}',
    ]
    if settings.enable_prefix_caching:
        # PERF: paylasilan sistem-prompt prefix'inin KV'sini yeniden kullan (prefill tasarrufu)
        cmd.append("--enable-prefix-caching")
    if settings.max_num_seqs:
        cmd += ["--max-num-seqs", str(settings.max_num_seqs)]
    if settings.kv_cache_dtype:
        cmd += ["--kv-cache-dtype", settings.kv_cache_dtype]
    if settings.trust_remote_code:
        cmd.append("--trust-remote-code")
    if settings.quantization:
        cmd += ["--quantization", settings.quantization]
    if settings.mm_processor_kwargs:
        cmd += ["--mm-processor-kwargs", settings.mm_processor_kwargs]
    if settings.enable_tools:
        # native tool-calling (act JSON-dispatch kullanir; gerekirse DILAJAN_ENABLE_TOOLS=false)
        cmd += ["--enable-auto-tool-choice", "--tool-call-parser", "hermes"]
    print("Sunucu baslatiliyor:\n  " + " ".join(cmd), flush=True)
    raise SystemExit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    main()
