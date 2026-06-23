#!/usr/bin/env python
"""CLIP/SigLIP zero-shot TIP-siniflandirma probe (Agent-3 #1). Bagimsiz grounded sinyal:
VLM uretken adlandirma yerine CLIP image<->text benzerligi suc-tipini siralayabilir mi?
(a) ham kosinus, (b) AnomalyCLIP recentering (normal-prototip cikar). Normalde yanlis-atesliyor mu test edilir.
Tek seferlik SigLIP indirme (offline-uyumlu yerel model)."""
from __future__ import annotations
import glob, io, sys
sys.path.insert(0, ".")
import numpy as np
import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor
from dilajan.video import extract_timestamped_frames, build_segments

MODEL = "google/siglip2-so400m-patch16-384"
# tip -> (TR+EN sablon listesi)
TYPES = {
    "Shooting":   ["a person firing a gun", "gunfire shooting attack", "silahla ateş eden kişi, çatışma"],
    "Fighting":   ["people physically fighting", "a violent brawl", "kavga eden, dövüşen insanlar"],
    "Assault":    ["a person assaulting and beating another", "physical assault", "birine saldıran, vuran kişi"],
    "Vandalism":  ["vandalism, smashing and breaking property", "a person destroying objects", "tahrip eden, eşya kıran kişi"],
    "Burglary":   ["burglary, breaking into a building", "a thief stealing", "haneye izinsiz giren hırsız"],
    "RoadAccidents": ["a traffic accident, car crash", "vehicle collision", "trafik kazası, araç çarpışması"],
    "Explosion":  ["an explosion with fire and smoke", "patlama, yangın ve duman"],
    "Normal":     ["normal everyday activity, people walking", "an ordinary calm scene", "olağan, sakin günlük aktivite"],
}

_dev = "cuda" if torch.cuda.is_available() else "cpu"
print("SigLIP yukleniyor:", MODEL)
proc = AutoProcessor.from_pretrained(MODEL)
import torch as _t; model = AutoModel.from_pretrained(MODEL, torch_dtype=_t.float16).to(_dev).eval()


@torch.no_grad()
def img_emb(jpegs):
    ims = [Image.open(io.BytesIO(j)).convert("RGB") for j in jpegs]
    px = proc(images=ims, return_tensors="pt").to(_dev)
    px = {k:(v.half() if v.is_floating_point() else v) for k,v in px.items()}
    e = model.get_image_features(**px)
    e = e if torch.is_tensor(e) else getattr(e,"pooler_output",getattr(e,"image_embeds",None))
    e = e / e.norm(dim=-1, keepdim=True)
    return e.mean(0).cpu().numpy()  # segment ortalama embedding


@torch.no_grad()
def txt_embs():
    out = {}
    for t, prompts in TYPES.items():
        tk = proc(text=prompts, return_tensors="pt", padding="max_length", truncation=True).to(_dev)
        e = model.get_text_features(**tk)
        e = e if torch.is_tensor(e) else getattr(e,"pooler_output",getattr(e,"text_embeds",None))
        e = e / e.norm(dim=-1, keepdim=True)
        out[t] = e.mean(0).cpu().numpy()
    return out


def seg_emb(path):
    fr, _ = extract_timestamped_frames(path, max_side=384)
    seg = build_segments(fr)[0]
    return img_emb([j for _, j in seg.frames])


def main():
    T = txt_embs()
    tnames = list(T.keys()); tmat = np.stack([T[t] for t in tnames])
    # normal prototip (recentering icin)
    normals = sorted(glob.glob("data/eval/Normal/*.mp4"))[:5]
    proto = np.mean([seg_emb(p) for p in normals], axis=0)

    tests = [("Shooting", p) for p in sorted(glob.glob("data/eval/Shooting/*.mp4"))[:3]]
    tests += [("Vandalism", p) for p in sorted(glob.glob("data/eval/Vandalism/*.mp4"))[:2]]
    tests += [("Assault", p) for p in sorted(glob.glob("data/eval/Assault/*.mp4"))[:2]]
    tests += [("Fighting", p) for p in sorted(glob.glob("data/eval/Fighting/*.mp4"))[:2]]
    tests += [("Normal", p) for p in sorted(glob.glob("data/eval/Normal/*.mp4"))[5:8]]

    def pred(emb, recenter):
        v = emb - proto if recenter else emb
        v = v / (np.linalg.norm(v) + 1e-8)
        sims = tmat @ v
        i = int(sims.argmax()); return tnames[i], float(sims[i])

    print(f"\n{'GT':14s} {'klip':26s} {'HAM top1':16s} {'RECENTER top1':16s}")
    print("-" * 78)
    raw_ok = rc_ok = n = 0
    for gt, p in tests:
        e = seg_emb(p)
        r1, rs = pred(e, False); c1, cs = pred(e, True)
        n += 1; raw_ok += int(r1 == gt); rc_ok += int(c1 == gt)
        print(f"{gt:14s} {p.split('/')[-1][:25]:26s} {r1+' '+format(rs,'.2f'):16s} {c1+' '+format(cs,'.2f'):16s}")
    print("-" * 78)
    print(f"HAM top1 dogru: {raw_ok}/{n}={100*raw_ok/n:.0f}%  |  RECENTER top1 dogru: {rc_ok}/{n}={100*rc_ok/n:.0f}%")


if __name__ == "__main__":
    main()
