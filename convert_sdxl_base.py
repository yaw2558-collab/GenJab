"""รวมไฟล์ SDXL-base แบบแยกชิ้นของ Amuse (unet + CLIP-L + CLIP-G + VAE, F32)
เป็น checkpoint เดี่ยวฟอร์แมต original + บีบ F16 — รันครั้งเดียว:

    python convert_sdxl_base.py

ได้ไฟล์ models/sdxl-base-f16.safetensors (~6.5GB)
สูตร mapping ตาม huggingface/diffusers convert_diffusers_to_original_sdxl.py
(สตรีมทีละ tensor — ไม่โหลดทั้งไฟล์ลงแรม)."""
import json
import os
import re
import struct

import numpy as np

AMUSE = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Amuse", "Models")
SRC = {
    "unet": os.path.join(AMUSE, "Diffusion", "stable-diffusion-xl-base-1.0",
                         "unet", "diffusion_pytorch_model.safetensors"),
    "te1": os.path.join(AMUSE, "TextEncoder", "CLIP-VIT-L", "model.safetensors"),
    "te2": os.path.join(AMUSE, "TextEncoder", "CLIP-VIT-G", "model.safetensors"),
    "vae": os.path.join(AMUSE, "AutoEncoder", "StableDiffusionXL",
                        "diffusion_pytorch_model.safetensors"),
}
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models",
                   "sdxl-base-f16.safetensors")

DTYPES = {"F32": (np.float32, 4), "F16": (np.float16, 2)}

# ---------- mapping ตามสูตร official (str.replace ตามลำดับ) ----------
UNET_MAP = [
    ("time_embed.0.weight", "time_embedding.linear_1.weight"),
    ("time_embed.0.bias", "time_embedding.linear_1.bias"),
    ("time_embed.2.weight", "time_embedding.linear_2.weight"),
    ("time_embed.2.bias", "time_embedding.linear_2.bias"),
    ("input_blocks.0.0.weight", "conv_in.weight"),
    ("input_blocks.0.0.bias", "conv_in.bias"),
    ("out.0.weight", "conv_norm_out.weight"),
    ("out.0.bias", "conv_norm_out.bias"),
    ("out.2.weight", "conv_out.weight"),
    ("out.2.bias", "conv_out.bias"),
    ("label_emb.0.0.weight", "add_embedding.linear_1.weight"),
    ("label_emb.0.0.bias", "add_embedding.linear_1.bias"),
    ("label_emb.0.2.weight", "add_embedding.linear_2.weight"),
    ("label_emb.0.2.bias", "add_embedding.linear_2.bias"),
]
UNET_RESNET = [
    ("in_layers.0", "norm1"),
    ("in_layers.2", "conv1"),
    ("out_layers.0", "norm2"),
    ("out_layers.3", "conv2"),
    ("emb_layers.1", "time_emb_proj"),
    ("skip_connection", "conv_shortcut"),
]
UNET_LAYERS = []
for _i in range(3):
    for _j in range(2):
        UNET_LAYERS.append((f"input_blocks.{3 * _i + _j + 1}.0.",
                            f"down_blocks.{_i}.resnets.{_j}."))
        if _i > 0:
            UNET_LAYERS.append((f"input_blocks.{3 * _i + _j + 1}.1.",
                                f"down_blocks.{_i}.attentions.{_j}."))
    for _j in range(4):
        UNET_LAYERS.append((f"output_blocks.{3 * _i + _j}.0.",
                            f"up_blocks.{_i}.resnets.{_j}."))
        if _i < 2:
            UNET_LAYERS.append((f"output_blocks.{3 * _i + _j}.1.",
                                f"up_blocks.{_i}.attentions.{_j}."))
    if _i < 3:
        UNET_LAYERS.append((f"input_blocks.{3 * (_i + 1)}.0.op.",
                            f"down_blocks.{_i}.downsamplers.0.conv."))
        UNET_LAYERS.append((f"output_blocks.{3 * _i + 2}.{1 if _i == 0 else 2}.",
                            f"up_blocks.{_i}.upsamplers.0."))
UNET_LAYERS.append(("output_blocks.2.2.conv.", "output_blocks.2.1.conv."))
UNET_LAYERS.append(("middle_block.1.", "mid_block.attentions.0."))
for _j in range(2):
    UNET_LAYERS.append((f"middle_block.{2 * _j}.", f"mid_block.resnets.{_j}."))

VAE_MAP = [
    ("nin_shortcut", "conv_shortcut"),
    ("norm_out", "conv_norm_out"),
    ("mid.attn_1.", "mid_block.attentions.0."),
]
for _i in range(4):
    for _j in range(2):
        VAE_MAP.append((f"encoder.down.{_i}.block.{_j}.",
                        f"encoder.down_blocks.{_i}.resnets.{_j}."))
    if _i < 3:
        VAE_MAP.append((f"down.{_i}.downsample.", f"down_blocks.{_i}.downsamplers.0."))
        VAE_MAP.append((f"up.{3 - _i}.upsample.", f"up_blocks.{_i}.upsamplers.0."))
    for _j in range(3):
        VAE_MAP.append((f"decoder.up.{3 - _i}.block.{_j}.",
                        f"decoder.up_blocks.{_i}.resnets.{_j}."))
for _i in range(2):
    VAE_MAP.append((f"mid.block_{_i + 1}.", f"mid_block.resnets.{_i}."))
VAE_ATTN = [
    ("norm.", "group_norm."),
    ("q.", "to_q."),
    ("k.", "to_k."),
    ("v.", "to_v."),
    ("proj_out.", "to_out.0."),
]

TE_LST = [
    ("transformer.resblocks.", "text_model.encoder.layers."),
    ("ln_1", "layer_norm1"),
    ("ln_2", "layer_norm2"),
    (".c_fc.", ".fc1."),
    (".c_proj.", ".fc2."),
    (".attn", ".self_attn"),
    ("ln_final.", "text_model.final_layer_norm."),
    ("token_embedding.weight", "text_model.embeddings.token_embedding.weight"),
    ("positional_embedding", "text_model.embeddings.position_embedding.weight"),
]
_TE_PROTECTED = {re.escape(hf): sd for sd, hf in TE_LST}
_TE_PATTERN = re.compile("|".join(_TE_PROTECTED))


def _relabel_te(k):
    return _TE_PATTERN.sub(lambda m: _TE_PROTECTED[re.escape(m.group(0))], k)


def convert_unet_key(k):
    for sd, hf in UNET_MAP:
        if k == hf:
            return "model.diffusion_model." + sd
    v = k
    if "resnets" in k:
        for sd, hf in UNET_RESNET:
            v = v.replace(hf, sd)
    for sd, hf in UNET_LAYERS:
        v = v.replace(hf, sd)
    return "model.diffusion_model." + v


def convert_vae_key(k):
    v = k
    for sd, hf in VAE_MAP:
        v = v.replace(hf, sd)
    if "attentions" in k:
        for sd, hf in VAE_ATTN:
            v = v.replace(hf, sd)
    return "first_stage_model." + v


def read_header(path):
    with open(path, "rb") as f:
        hlen = struct.unpack("<Q", f.read(8))[0]
        return json.loads(f.read(hlen)), 8 + hlen


def plan():
    """คืน ([jobs], n_src) — job = (ชื่อใหม่, shape ใหม่, [(src, off, nbytes, dtype, shape, op)])"""
    jobs, n_src = [], 0
    # unet + vae: rename ตรง ๆ
    for part, conv in (("unet", convert_unet_key), ("vae", convert_vae_key)):
        header, base = read_header(SRC[part])
        for k, v in header.items():
            if k != "__metadata__":
                assert v["dtype"] in DTYPES, f"{part}/{k}: dtype {v['dtype']} ไม่รองรับ"
        for k, v in header.items():
            if k == "__metadata__":
                continue
            n_src += 1
            new_shape = list(v["shape"])
            if part == "vae" and "mid.attn_1." in convert_vae_key(k) and k.endswith(".weight") and len(new_shape) == 2:
                new_shape = new_shape + [1, 1]  # reshape q/k/v/proj_out ของ official
            jobs.append((conv(k), new_shape,
                         [(SRC[part], base + v["data_offsets"][0],
                           base + v["data_offsets"][1], v["dtype"], v["shape"], None)]))
    # te1: prefix เฉย ๆ
    header, base = read_header(SRC["te1"])
    for k, v in header.items():
        if k == "__metadata__":
            continue
        n_src += 1
        jobs.append(("conditioner.embedders.0.transformer." + k, list(v["shape"]),
                     [(SRC["te1"], base + v["data_offsets"][0],
                       base + v["data_offsets"][1], v["dtype"], v["shape"], None)]))
    # te2: relabel + รวม qkv + transpose text_projection
    header, base = read_header(SRC["te2"])
    qkv_w, qkv_b, rest = {}, {}, []
    for k, v in header.items():
        if k == "__metadata__":
            continue
        n_src += 1
        spec = (SRC["te2"], base + v["data_offsets"][0],
                base + v["data_offsets"][1], v["dtype"], v["shape"], None)
        for code, store in (("weight", qkv_w), ("bias", qkv_b)):
            for qkv in ("q", "k", "v"):
                suffix = f".{qkv}_proj.{code}"
                if k.endswith(".self_attn" + suffix):
                    store.setdefault(k[:-len(suffix)], [None, None, None])[
                        {"q": 0, "k": 1, "v": 2}[qkv]] = spec
                    break
            else:
                continue
            break
        else:
            rest.append((k, v, spec))
    for k, v, spec in rest:
        if k == "text_projection.weight":
            jobs.append(("conditioner.embedders.1.model.text_projection",
                         [v["shape"][1], v["shape"][0]], [(spec[0], spec[1], spec[2],
                         spec[3], spec[4], "T")]))
        else:
            jobs.append(("conditioner.embedders.1.model." + _relabel_te(k),
                         list(v["shape"]), [spec]))
    for store, suffix in ((qkv_w, "in_proj_weight"), (qkv_b, "in_proj_bias")):
        for pre, specs in store.items():
            assert None not in specs, f"qkv ไม่ครบที่ {pre}"
            shape = [sum(s[4][0] for s in specs)] + list(specs[0][4][1:])
            jobs.append(("conditioner.embedders.1.model." + _relabel_te(pre) + "." + suffix,
                         shape, [(s[0], s[1], s[2], s[3], s[4], None) for s in specs]))
    # กันชื่อชน
    names = [j[0] for j in jobs]
    assert len(names) == len(set(names)), "ชื่อ tensor ชนกัน"
    return jobs, n_src


def convert():
    for part, p in SRC.items():
        if not os.path.isfile(p):
            raise SystemExit(f"ไม่พบไฟล์ {part} ที่ {p} (ต้องโหลด SDXL ในแอป Amuse ก่อน)")
        header, _ = read_header(p)
        for k, v in header.items():
            if k != "__metadata__":
                assert v["dtype"] in DTYPES, f"{part}/{k}: dtype {v['dtype']} ไม่รองรับ"
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    jobs, n_src = plan()
    print(f"tensors: {n_src} แหล่ง -> {len(jobs)} ปลายทาง")
    # เขียน header ก่อน (offset คำนวณล่วงหน้า)
    header, off = {}, 0
    for name, shape, _ in jobs:
        nbytes = int(np.prod(shape, dtype=np.int64)) * 2
        header[name] = {"dtype": "F16", "shape": shape, "data_offsets": [off, off + nbytes]}
        off += nbytes
    blob = json.dumps(header, separators=(",", ":")).encode()
    handles = {}
    done_gb, t0 = 0.0, __import__("time").time()
    with open(DST, "wb") as out:
        out.write(struct.pack("<Q", len(blob)))
        out.write(blob)
        for i, (name, shape, specs) in enumerate(jobs):
            parts = []
            for path, s, e, dtype, shp, op in specs:
                if path not in handles:
                    handles[path] = open(path, "rb")
                handles[path].seek(s)
                arr = np.frombuffer(handles[path].read(e - s),
                                    dtype=DTYPES[dtype][0]).reshape(shp)
                parts.append(arr.T if op == "T" else arr)
            data = parts[0] if len(parts) == 1 else np.concatenate(parts, axis=0)
            # reshape (VAE mid attn) เปลี่ยนแค่ shape ใน header — เทียบจำนวนธาตุ
            assert data.size == int(np.prod(shape, dtype=np.int64)), (name, data.shape, shape)
            buf = data.astype(np.float16).tobytes()
            out.write(buf)
            done_gb += len(buf) / 1e9
            if (i + 1) % 200 == 0:
                dt = __import__("time").time() - t0
                print(f"  {i + 1}/{len(jobs)} ({done_gb:.1f}GB, {dt:.0f}s)")
    for h in handles.values():
        h.close()
    # ตรวจไฟล์ปลายทาง
    back, _ = read_header(DST)
    assert len(back) == len(jobs), (len(back), len(jobs))
    assert all(v["dtype"] == "F16" for v in back.values())
    for probe in ("model.diffusion_model.input_blocks.1.0.in_layers.0.weight",
                  "first_stage_model.encoder.down.0.block.0.norm1.weight",
                  "conditioner.embedders.0.transformer.text_model.embeddings.token_embedding.weight",
                  "conditioner.embedders.1.model.transformer.resblocks.0.attn.in_proj_weight",
                  "conditioner.embedders.1.model.text_projection"):
        assert probe in back, f"หาย: {probe}"
    print(f"saved: {DST} ({os.path.getsize(DST) / 1e9:.2f}GB)")


if __name__ == "__main__":
    convert()
