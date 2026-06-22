#!/usr/bin/env python
"""Bagimsiz judge modelini (Gemma 3 12B FP8) indirir — E1 self-eval donguselligini kirmak icin."""
from huggingface_hub import snapshot_download

MODEL = "RedHatAI/gemma-3-12b-it-FP8-dynamic"
path = snapshot_download(MODEL)
print(f"DL_DONE: {path}")
