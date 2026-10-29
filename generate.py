"""Text-to-image + image-to-image + text-to-video: เรียก sd-cli.exe (stable-diffusion.cpp + Vulkan,
   ตัวเดียวกับที่ Amuse ใช้) — รูปนิ่ง (SD-Turbo/Anima/Qwen/Iris) และวิดีโอ (-M vid_gen)."""
import argparse
import glob
import math
import os
import random
import subprocess
import sys
import threading
import tempfile

AMUSE_SD_CLI = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Amuse",
                            "RuntimeStableDiffusionCpp", "vulkan", "sd-cli.exe")
MODEL = os.environ.get("TEXT2IMAGE_MODEL", "")  # ว่าง = หา sd_turbo.safetensors ใน HF cache / models/ เอง
SDXL_TURBO = os.environ.get("TEXT2IMAGE_SDXL_TURBO", "")  # ว่าง = หาใน HF cache / models/ เอง
AMUSE_MODELS = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Amuse", "Models")


def app_dir():
    """โฟลเดอร์ที่แอปรันอยู่ — exe ที่บิลด์แล้วใช้ข้างตัว exe, รันจากซอร์สใช้ข้างไฟล์นี้."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


LOCAL_MODELS = os.path.join(app_dir(), "models")
LOCAL_LORAS = os.path.join(app_dir(), "loras")


def resolve_sd_cli():
    """หา sd-cli.exe — env TEXT2IMAGE_SDCLI ก่อน, ตามด้วย runtime/ ที่ห่อมากับแอป, สุดท้ายของ Amuse."""
    env = os.environ.get("TEXT2IMAGE_SDCLI", "")
    if env:
        return env
    bundled = os.path.join(app_dir(), "runtime", "sd-cli.exe")
    if os.path.isfile(bundled):
        return bundled
    return AMUSE_SD_CLI


SD_CLI = resolve_sd_cli()
LORA_ENV_DIRS = [p for p in os.environ.get("TEXT2IMAGE_LORA_DIR", "").split(os.pathsep) if p]


def lora_dirs():
    """โฟลเดอร์ที่ค้นหา LoRA — env TEXT2IMAGE_LORA_DIR มาก่อน, ตามด้วยของ Amuse + loras/."""
    return ([os.path.normpath(p) for p in LORA_ENV_DIRS if os.path.isdir(p)]
            + [os.path.join(AMUSE_MODELS, "LoraAdapter"),
               os.path.join(AMUSE_MODELS, "Models", "LoraAdapter"),
               LOCAL_LORAS])


def list_loras():
    """{ชื่อไม่รวมนามสกุล: path เต็ม} ของ LoRA ที่เจอ — ชื่อซ้ำเอาอันที่เจอก่อน."""
    found = {}
    for d in lora_dirs():
        try:
            files = glob.glob(os.path.join(d, "*.safetensors"))
        except OSError:
            continue
        for p in sorted(files):
            found.setdefault(os.path.splitext(os.path.basename(p))[0], p)
    return found


def resolve_lora(name):
    """คืน (โฟลเดอร์, ชื่อไม่รวมนามสกุล) ของ LoRA — รับชื่อหรือ path ตรง ๆ ก็ได้."""
    if not name or not str(name).strip():
        raise ValueError("ชื่อ LoRA ว่าง")
    p = os.path.expanduser(str(name).strip())
    if os.path.isfile(p):
        full = os.path.abspath(p)
        return os.path.dirname(full), os.path.splitext(os.path.basename(full))[0]
    stem = p
    for ext in (".safetensors", ".ckpt", ".pt"):
        if stem.lower().endswith(ext):
            stem = stem[:-len(ext)]
            break
    stem = os.path.basename(stem)
    found = list_loras()
    if stem in found:
        return os.path.dirname(found[stem]), stem
    raise FileNotFoundError(
        f"ไม่พบ LoRA '{name}' — ค้นใน {', '.join(lora_dirs())} "
        f"(มี: {', '.join(sorted(found)) or '—'})")


def lora_prompt(prompt, lora=None, strength=1.0):
    """ต่อแท็ก <lora:ชื่อ:ความแรง> ท้าย prompt + คืน args --lora-model-dir — ไม่ใช้คืนเดิม."""
    if not lora:
        return prompt, []
    try:
        s = float(strength)
    except (TypeError, ValueError):
        raise ValueError(f"ความแรง LoRA ต้องเป็นตัวเลข (ได้ {strength})")
    if s == 0:
        raise ValueError("ความแรง LoRA ต้องไม่เป็น 0 (ไม่ใช้ให้เลือก '(ไม่ใช้)')")
    d, stem = resolve_lora(lora)
    return f"{prompt} <lora:{stem}:{s:g}>", ["--lora-model-dir", d]

def _popen_flags():
    """ซ่อนหน้าต่างคอนโซลของ sd-cli บน Windows — แพลตฟอร์มอื่นคืน 0."""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


class GenerationCancelled(Exception):
    """User pressed cancel - worker catches it and ends as cancelled, not an error."""


def _run(cmd, cancel_event=None):
    """Run sd-cli, return CompletedProcess - with cancel_event kill it when user cancels."""
    if cancel_event is None:
        return subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                              creationflags=_popen_flags())
    if cancel_event.is_set():
        raise GenerationCancelled()
    kw = {}
    flag = _popen_flags()
    if flag:
        kw["creationflags"] = flag
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, errors="replace", **kw)
    box = {}

    def _drain():
        try:
            box["out"], box["err"] = proc.communicate()
        except Exception as e:  # noqa: BLE001
            box["exc"] = e

    drainer = threading.Thread(target=_drain, daemon=True)
    drainer.start()
    cancelled = False
    while proc.poll() is None:
        if cancel_event.wait(0.05):
            cancelled = True
            try:
                proc.kill()
            except OSError:
                pass
            break
    drainer.join()
    if "exc" in box:
        raise box["exc"]
    if cancelled:
        raise GenerationCancelled()
    return subprocess.CompletedProcess(cmd, proc.returncode,
                                       box.get("out", ""), box.get("err", ""))


RATIOS = {"1:1": (1, 1), "3:4": (3, 4), "9:16": (9, 16), "16:9": (16, 9)}


def resolve_size(size=512, ratio="1:1", width=None, height=None):
    """แปลง size + ratio เป็น (W, H) — size คือด้านยาว (3:4/9:16 = แนวตั้ง, 16:9 = แนวนอน).

    รองรับ width/height ตรง ๆ (เหนือกว่า size/ratio) และ size แบบ "512x768".
    ด้านสั้นปัดขึ้นให้ลงตัวกับ 64 (ตรงกับที่ sd-cli ปัดให้ — ขนาดที่ขอคือขนาดที่ได้จริง)."""
    if width is not None or height is not None:
        if width is None or height is None:
            raise ValueError(f"ต้องระบุ width/height คู่กัน (ได้ {width}x{height})")
        w, h = int(width), int(height)
        if w <= 0 or h <= 0:
            raise ValueError(f"width/height ต้อง > 0 (ได้ {w}x{h})")
        return (w, h)
    if isinstance(size, str) and "x" in size.lower():
        w, h = size.lower().split("x", 1)
        return resolve_size(width=int(w), height=int(h))
    long_side = int(size)
    if long_side <= 0:
        raise ValueError(f"size ต้อง > 0 (ได้ {size})")
    if ratio not in RATIOS:
        raise ValueError(f"สัดส่วนไม่รู้จัก: {ratio} (มี: {', '.join(RATIOS)})")
    rw, rh = RATIOS[ratio]
    if rw == rh:
        return (long_side, long_side)
    short = max(64, math.ceil(long_side * min(rw, rh) / max(rw, rh) / 64) * 64)
    if rh > rw:  # แนวตั้ง
        return (short, long_side)
    return (long_side, short)


EXTRA_FLAGS = {"llm": "--llm", "vae": "--vae", "clip_l": "--clip_l",
               "clip_g": "--clip_g", "t5xxl": "--t5xxl",
               "llm_vision": "--llm_vision", "audio_vae": "--audio-vae"}


def _extra_args(files):
    """แปลงไฟล์เสริมใน dict เป็น argv ของ sd-cli — เรียงตาม EXTRA_FLAGS."""
    args = []
    for key, flag in EXTRA_FLAGS.items():
        if key in files:
            args += [flag, files[key]]
    return args


def model_files(name):
    """คืน dict ของไฟล์โมเดล ({m} + ไฟล์เสริม llm/vae/clip_l/clip_g/t5xxl/llm_vision/audio_vae) —
    รองรับ sd-turbo, sdxl-turbo, sdxl-base, anima-turbo, anima-base, anima-aesthetic, qwen21, qwen21-turbo, iris-3b, flux2-klein, minimax-h3, wan22-5b, flux1-dev."""
    if name == "sd-turbo":
        if MODEL and os.path.isfile(MODEL):
            return {"m": MODEL}
        hits = glob.glob(os.path.expanduser(
            "~/.cache/huggingface/hub/models--stabilityai--sd-turbo/snapshots/*/sd_turbo.safetensors"))
        hits += glob.glob(os.path.join(LOCAL_MODELS, "sd_turbo.safetensors"))
        hits += glob.glob(os.path.join(LOCAL_MODELS, "sd-turbo*.safetensors"))
        if hits:
            return {"m": hits[0]}
        raise FileNotFoundError(
            "ไม่พบโมเดล sd_turbo.safetensors — วางไฟล์ไว้ในโฟลเดอร์ models/ "
            "(ข้างโปรแกรม) หรือตั้ง path เองผ่าน env TEXT2IMAGE_MODEL")
    if name == "sdxl-turbo":
        if SDXL_TURBO and os.path.isfile(SDXL_TURBO):
            return {"m": SDXL_TURBO}
        hits = glob.glob(os.path.expanduser(
            "~/.cache/huggingface/hub/models--stabilityai--sdxl-turbo/snapshots/*/sd_xl_turbo_*.safetensors"))
        hits += glob.glob(os.path.join(LOCAL_MODELS, "sdxl-turbo*.safetensors"))
        hits += glob.glob(os.path.join(LOCAL_MODELS, "sd_xl_turbo_*.safetensors"))
        if hits:
            return {"m": hits[0]}
        raise FileNotFoundError(
            "ไม่พบโมเดล SDXL-Turbo — โหลดไฟล์ sd_xl_turbo_1.0_fp16.safetensors "
            "จาก https://huggingface.co/stabilityai/sdxl-turbo มาไว้ในโฟลเดอร์ models/ "
            "หรือตั้ง path เองผ่าน env TEXT2IMAGE_SDXL_TURBO")
    if name == "sdxl-base":
        # ไฟล์เดี่ยวที่รวมจากของ Amuse 4 ชิ้น + บีบ F16 (ดู convert_sdxl_base.py)
        override = os.environ.get("TEXT2IMAGE_SDXL_BASE", "")
        if override and os.path.isfile(override):
            return {"m": override}
        m = os.path.join(LOCAL_MODELS, "sdxl-base-f16.safetensors")
        if os.path.isfile(m):
            return {"m": m}
        raise FileNotFoundError(
            "ไม่พบ models/sdxl-base-f16.safetensors "
            "— รัน `python convert_sdxl_base.py` ครั้งเดียวก่อน "
            "(ต้องโหลด Stable Diffusion XL ในแอป Amuse ก่อน)")
    if name == "qwen21":
        f = {"diffusion": os.path.join(AMUSE_MODELS, "Diffusion", "qwen_image_2.1_bf16.safetensors"),
             "llm": os.path.join(AMUSE_MODELS, "TextEncoder", "Qwen3VL-8B-Instruct-Q8_0.gguf"),
             "llm_vision": os.path.join(AMUSE_MODELS, "TextEncoder",
                                        "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"),
             "vae": os.path.join(AMUSE_MODELS, "AutoEncoder",
                                 "qwen_image_2.1_vae_bf16.safetensors")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing Qwen 2.1 files: {missing} (load Qwen 2.1 model in Amuse first)")
        return f
    if name == "qwen21-turbo":
        # Turbo 8 steps: diffusion ไฟล์เดียว (Comfy-Org) + TE/VAE ชุดเดียวกับ qwen21
        override = os.environ.get("TEXT2IMAGE_QWEN_TURBO", "")
        diff = override if override and os.path.isfile(override) else ""
        if not diff:
            diff = os.path.join(LOCAL_MODELS, "qwen_image_2.1_turbo_bf16.safetensors")
        te = os.path.join(AMUSE_MODELS, "TextEncoder")
        ae = os.path.join(AMUSE_MODELS, "AutoEncoder")
        f = {"diffusion": diff,
             "llm": os.path.join(te, "Qwen3VL-8B-Instruct-Q8_0.gguf"),
             "llm_vision": os.path.join(te, "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"),
             "vae": os.path.join(ae, "qwen_image_2.1_vae_bf16.safetensors")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing Qwen 2.1 Turbo files: {missing} "
                "(load Qwen 2.1 model in Amuse first, Turbo file goes to models/)")
        return f
    if name == "flux2-klein":
        # FLUX.2 klein 4B (GGUF Q8) + Qwen3-4B + flux2 VAE — ไฟล์อยู่ใน models/
        override = os.environ.get("TEXT2IMAGE_FLUX2_KLEIN", "")
        diff = override if override and os.path.isfile(override) else ""
        if not diff:
            diff = os.path.join(LOCAL_MODELS, "flux-2-klein-4b-Q8_0.gguf")
        llm = os.path.join(LOCAL_MODELS, "qwen3-4b-q4_k_m.gguf")
        if not os.path.isfile(llm):
            llm = os.path.join(LOCAL_MODELS, "Qwen3-4B-Q4_K_M.gguf")
        f = {"diffusion": diff, "llm": llm,
             "vae": os.path.join(LOCAL_MODELS, "flux2-vae.safetensors")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing FLUX.2 klein files: {missing} (put them in models/)")
        return f
    if name == "flux1-dev":
        # Flux.1 Dev (fp8 DiT + CLIP-L + T5-XXL fp8 + flux VAE) — files live in models/
        override = os.environ.get("TEXT2IMAGE_FLUX1_DEV", "")
        diff = override if override and os.path.isfile(override) else ""
        if not diff:
            diff = os.path.join(LOCAL_MODELS, "flux1-dev-fp8.safetensors")
        f = {"diffusion": diff,
             "clip_l": os.path.join(LOCAL_MODELS, "clip_l.safetensors"),
             "t5xxl": os.path.join(LOCAL_MODELS, "t5xxl_fp8_e4m3fn.safetensors"),
             "vae": os.path.join(LOCAL_MODELS, "flux-vae-bf16.safetensors")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing Flux.1 Dev files: {missing} (put them in models/)")
        return f
    if name == "iris-3b":
        # Iris-3B เป็นโมเดลภาพนิ่ง (Amuse เรียกผ่าน TextToImage pipeline):
        # diffusion prefix `model.diffusion_model.` + LLM Qwen3VL-4B, ใช้ FakeVAE (ไม่มีไฟล์ vae)
        f = {"diffusion": os.path.join(AMUSE_MODELS, "Diffusion", "iris-3b", "model.safetensors"),
             "llm": os.path.join(AMUSE_MODELS, "TextEncoder", "Qwen3VL-4B-Instruct-Q8_0.gguf")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing Iris-3B files: {missing} (load Iris model in Amuse first)")
        return f
    if name == "minimax-h3":
        # MiniMax-H3 (วิดีโอ): diffusion GGUF + LLM Qwen3VL-32B + video VAE + audio VAE
        # ตรงกับที่ Amuse โหลดในล็อก StableDiffusionCpp (MiniMax H3 AV FLOW mode)
        f = {"diffusion": os.path.join(AMUSE_MODELS, "Diffusion", "minimax_h3_fl2va_pruned-Q8_0.gguf"),
             "llm": os.path.join(AMUSE_MODELS, "TextEncoder",
                                 "qwen3vl_32b_minimax_h3-Q4_K_M.gguf"),
             "vae": os.path.join(AMUSE_MODELS, "AutoEncoder",
                                 "minimax_h3_video_vae_fp16.safetensors"),
             "audio_vae": os.path.join(AMUSE_MODELS, "AutoEncoder",
                                       "minimax_h3_audio_vae_fp32.safetensors")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing MiniMax-H3 files: {missing} (load MiniMax-H3 model in Amuse first)")
        return f
    if name == "wan22-5b":
        # Wan2.2 TI2V 5B: หา GGUF ใน models/ ก่อน (ชื่อไฟล์ตาม HF) แล้วค่อยของ Amuse
        local = {"diffusion": os.path.join(LOCAL_MODELS, "Wan2.2-TI2V-5B-Q8_0.gguf"),
                 "t5xxl": os.path.join(LOCAL_MODELS, "umt5-xxl-encoder-Q8_0.gguf"),
                 "vae": os.path.join(LOCAL_MODELS, "wan2.2_vae.safetensors")}
        if all(os.path.isfile(p) for p in local.values()):
            return local
        # Wan2.2 TI2V 5B (วิดีโอ t2v/i2v ไฟล์เดียว): diffusion GGUF + UMT5-XXL + Wan22 VAE
        f = {"diffusion": os.path.join(AMUSE_MODELS, "Diffusion", "Wan2.2-TI2V-5B-Q8_0.gguf"),
             "t5xxl": os.path.join(AMUSE_MODELS, "TextEncoder", "UMT5-XXL", "model.safetensors"),
             "vae": os.path.join(AMUSE_MODELS, "AutoEncoder", "Wan22", "wan2.2_vae.safetensors")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing Wan2.2-5B files: {missing} (load Wan2.2 5B model in Amuse first, "
                "or put Wan2.2-TI2V-5B-Q8_0.gguf + umt5-xxl-encoder-Q8_0.gguf + "
                "wan2.2_vae.safetensors in models/)")
        return f
    anima_models = {"anima-turbo": "anima-turbo-v1.0.safetensors",
                    "anima-aesthetic": "anima-aesthetic-v1.1.safetensors"}
    if name == "anima-base":
        m = os.path.join(LOCAL_MODELS, "anima-base-sd.cpp.safetensors")
        if not os.path.isfile(m):
            raise FileNotFoundError(
                "ไม่พบ models/anima-base-sd.cpp.safetensors "
                "— รัน `python convert_anima_base.py` ครั้งเดียวก่อน")
    elif name in anima_models:
        m = os.path.join(AMUSE_MODELS, "Diffusion", anima_models[name])
    else:
        raise ValueError(f"โมเดลไม่รู้จัก: {name} (มี: sd-turbo, sdxl-turbo, sdxl-base, anima-turbo, anima-base, anima-aesthetic, qwen21, qwen21-turbo, iris-3b, flux2-klein, minimax-h3, wan22-5b, flux1-dev)")
    f = {"m": m,
         "llm": os.path.join(AMUSE_MODELS, "TextEncoder", "Qwen3-0.6B-Q8_0.gguf"),
         "vae": os.path.join(AMUSE_MODELS, "AutoEncoder", "QwenImage",
                             "diffusion_pytorch_model.safetensors")}
    missing = [k for k, p in f.items() if not os.path.isfile(p)]
    if missing:
        raise FileNotFoundError(f"ไม่พบไฟล์ {name}: {missing} (ต้องลงโมเดลในแอป Amuse ก่อน)")
    return f


def txt2img(prompt, steps=4, guidance=1.0, size=512, seed=None, negative="", model="sd-turbo",
            ratio="1:1", width=None, height=None, lora=None, lora_strength=1.0,
            cancel_event=None):
    """เจนรูป คืน (PIL Image, seed ที่ใช้จริง) — ไม่ส่ง seed มาสุ่มให้เองทุกครั้ง."""
    from PIL import Image
    if not os.path.isfile(SD_CLI):
        raise FileNotFoundError(f"ไม่พบ sd-cli.exe ที่ {SD_CLI} (ต้องลงแอป Amuse ก่อน หรือติดตั้ง GenJab ใหม่)")
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    files = model_files(model)
    w, h = resolve_size(size, ratio, width, height)
    with tempfile.TemporaryDirectory() as td:
        prompt, lora_args = lora_prompt(prompt, lora, lora_strength)
        out = os.path.join(td, "gen.png")
        model_args = (["--diffusion-model", files["diffusion"]] if "diffusion" in files
                else ["-m", files["m"]])
        cmd = [SD_CLI] + model_args + ["-p", prompt, "-o", out,
               "-W", str(w), "-H", str(h),
               "--steps", str(steps), "--cfg-scale", str(guidance),
               "--seed", str(seed)] + lora_args
        if negative:
            cmd += ["-n", negative]
        cmd += _extra_args(files)
        cmd += _extra_args(files)
        if lora and model == "flux1-dev":
            # flux1-dev fp8 + LoRA needs CPU offload (Vulkan CPY buffer fails otherwise)
            cmd += ["--offload-to-cpu"]
        p = _run(cmd, cancel_event)
        if p.returncode != 0 or not os.path.isfile(out):
            raise RuntimeError(f"sd-cli ล้มเหลว:\n{(p.stderr or p.stdout)[-800:]}")
        return Image.open(out).convert("RGB"), seed


def _batch_seeds(seed, n):
    """คืน seed รายรูปจำนวน n ค่า — ต่อกันทีละรูป อยู่ในช่วง 0..2**31-1 ไม่ซ้ำกันในชุด."""
    if seed is None:
        seed = random.randint(0, 2**31 - 1 - (n - 1))
    else:
        seed %= 2**31
        if seed + n > 2**31:
            seed = 2**31 - n
    return [seed + i for i in range(n)]


def txt2img_batch(prompt, n=2, steps=4, guidance=1.0, size=512, seed=None,
                  negative="", model="sd-turbo", ratio="1:1", width=None, height=None,
                  lora=None, lora_strength=1.0, cancel_event=None):
    """เจนทีเดียว n รูป (โหลดโมเดลครั้งเดียว) คืน [(PIL Image, seed)] — seed ต่อกันทีละรูป."""
    from PIL import Image
    if n < 1:
        raise ValueError(f"จำนวนรูปต้อง >= 1 (ได้ {n})")
    if not os.path.isfile(SD_CLI):
        raise FileNotFoundError(f"ไม่พบ sd-cli.exe ที่ {SD_CLI} (ต้องลงแอป Amuse ก่อน หรือติดตั้ง GenJab ใหม่)")
    seeds = _batch_seeds(seed, n)
    prompt, lora_args = lora_prompt(prompt, lora, lora_strength)
    files = model_files(model)
    w, h = resolve_size(size, ratio, width, height)
    with tempfile.TemporaryDirectory() as td:
        model_args = (["--diffusion-model", files["diffusion"]] if "diffusion" in files
                else ["-m", files["m"]])
        cmd = [SD_CLI] + model_args + ["-p", prompt, "-o", os.path.join(td, "b_%d.png"),
               "-W", str(w), "-H", str(h),
               "--steps", str(steps), "--cfg-scale", str(guidance),
               "--seed", str(seeds[0]), "-b", str(n)] + lora_args
        if negative:
            cmd += ["-n", negative]
        cmd += _extra_args(files)
        cmd += _extra_args(files)
        if lora and model == "flux1-dev":
            # flux1-dev fp8 + LoRA needs CPU offload (Vulkan CPY buffer fails otherwise)
            cmd += ["--offload-to-cpu"]
        p = _run(cmd, cancel_event)
        outs = [os.path.join(td, f"b_{i}.png") for i in range(n)]
        if p.returncode != 0 or not all(os.path.isfile(o) for o in outs):
            raise RuntimeError(f"sd-cli ล้มเหลว:\n{(p.stderr or p.stdout)[-800:]}")
        return [(Image.open(o).convert("RGB"), seeds[i]) for i, o in enumerate(outs)]


NO_STYLE = "(ไม่ใช้สไตล์)"

# preset สไตล์เทศกาลสำหรับโหมดแปลงรูป — fragment ภาษาอังกฤษต่อท้าย prompt/negative ของ user
STYLE_PRESETS = {
    "สงกรานต์": {
        "prompt": ("Songkran Thai water festival style, joyful water splashes, "
                   "traditional Thai flower garlands, vibrant colors, festive lights, "
                   "celebration atmosphere"),
        "negative": "dry dull scene, desaturated, gloomy",
    },
    "ลอยกระทง": {
        "prompt": ("Loy Krathong night festival style, floating lanterns on river, "
                   "glowing krathong, full moon, water reflections, magical lights"),
        "negative": "daylight, harsh sun, washed out",
    },
    "งานวัด": {
        "prompt": ("Thai temple fair at night style, ferris wheel with colorful lights, "
                   "food stalls, string lights, festive crowd, nostalgic funfair"),
        "negative": "empty dark scene, blurry crowd",
    },
    "Diwali": {
        "prompt": ("Diwali festival of lights style, glowing oil lamps diyas, "
                   "fireworks in night sky, marigold decorations, warm golden glow"),
        "negative": "cold blue tone, dark underexposed",
    },
    "Holi": {
        "prompt": ("Holi festival of colors style, vibrant colored powder clouds in air, "
                   "joyful celebration, vivid colors, dynamic motion"),
        "negative": "monochrome, desaturated, dull gray",
    },
    "คาร์นิวัล": {
        "prompt": ("street carnival parade style, colorful feather costumes, "
                   "confetti in air, dancers, festive energy, vivid colors"),
        "negative": "empty street, dull, overcast",
    },
}


def apply_style(prompt="", negative="", style=None):
    """ต่อสไตล์เทศกาลท้าย prompt/negative — ไม่เลือกสไตล์คืนเดิม, ชื่อผิด raise ValueError."""
    if not style or style == NO_STYLE:
        return prompt, negative
    if style not in STYLE_PRESETS:
        raise ValueError(f"สไตล์ไม่รู้จัก: {style} (มี: {', '.join(STYLE_PRESETS)})")
    frag = STYLE_PRESETS[style]
    full_p = f"{prompt}, {frag['prompt']}" if prompt else frag["prompt"]
    full_n = f"{negative}, {frag['negative']}" if negative else frag["negative"]
    return full_p, full_n


def fit_init_size(w, h, long_side=512):
    """ย่อขนาดรูปต้นฉบับให้ด้านยาว = long_side คงสัดส่วน — แต่ละด้านปัดให้ลงตัวกับ 64 ขั้นต่ำ 64."""
    w, h = int(w), int(h)
    if w <= 0 or h <= 0:
        raise ValueError(f"ขนาดรูปต้นฉบับต้อง > 0 (ได้ {w}x{h})")
    long_side = int(long_side)
    if long_side <= 0:
        raise ValueError(f"size ต้อง > 0 (ได้ {long_side})")
    scale = long_side / max(w, h)
    return (max(64, round(w * scale / 64) * 64),
            max(64, round(h * scale / 64) * 64))


IP_ADAPTER_MODELS = ("sdxl-turbo", "sdxl-base")
IP_ADAPTER_FILE = "ip-adapter-plus_sdxl_vit-h.safetensors"
CLIP_VISION_FILE = "clip_vision_h.safetensors"


def ip_adapter_files():
    """คืน {"ip_adapter": ..., "clip_vision": ...} สำหรับคงหน้าเดิม (SDXL) — ไม่มี raise พร้อมบอกที่โหลด."""
    a = os.environ.get("TEXT2IMAGE_IP_ADAPTER", "") or os.path.join(LOCAL_MODELS, IP_ADAPTER_FILE)
    v = os.environ.get("TEXT2IMAGE_CLIP_VISION", "") or os.path.join(LOCAL_MODELS, CLIP_VISION_FILE)
    missing = [p for p in (a, v) if not os.path.isfile(p)]
    if missing:
        raise FileNotFoundError(
            "ไม่พบไฟล์คงหน้าเดิม: " + ", ".join(missing)
            + " — โหลดจาก https://huggingface.co/h94/IP-Adapter "
            "(sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors + "
            "models/image_encoder/model.safetensors เปลี่ยนชื่อเป็น clip_vision_h.safetensors) "
            "มาไว้ในโฟลเดอร์ models/")
    return {"ip_adapter": a, "clip_vision": v}


def img2img(init_path, prompt="", strength=0.6, steps=4, guidance=1.0, size=512,
            seed=None, negative="", model="sd-turbo", width=None, height=None,
            lora=None, lora_strength=1.0, face_ref=None, face_strength=0.6,
            cancel_event=None):
    """แปลงรูปต้นฉบับตาม prompt คืน (PIL Image, seed ที่ใช้จริง).

    strength 0..1 (น้อย = คงรูปเดิมมาก) — ขนาดผลลัพธ์ย่อจากรูปต้นฉบับให้ด้านยาว = size."""
    from PIL import Image
    if model in VIDEO_MODELS:
        raise ValueError(f"โมเดลวิดีโอใช้แปลงรูปไม่ได้: {model}")
    try:
        s = float(strength)
    except (TypeError, ValueError):
        raise ValueError(f"strength ต้องเป็นตัวเลข 0..1 (ได้ {strength})")
    if not 0 < s < 1:
        raise ValueError(f"strength ต้องอยู่ระหว่าง 0..1 (ได้ {strength})")
    if not init_path or not os.path.isfile(init_path):
        raise FileNotFoundError(f"ไม่พบรูปต้นฉบับ: {init_path}")
    if width is not None or height is not None:
        if width is None or height is None:
            raise ValueError(f"ต้องระบุ width/height คู่กัน (ได้ {width}x{height})")
        w, h = int(width), int(height)
        if w <= 0 or h <= 0:
            raise ValueError(f"width/height ต้อง > 0 (ได้ {w}x{h})")
    else:
        w = h = None
    if face_ref:
        if model not in IP_ADAPTER_MODELS:
            raise ValueError(f"คงหน้าเดิมใช้ได้กับโมเดล SDXL เท่านั้น (ได้ {model})")
        if not os.path.isfile(face_ref):
            raise FileNotFoundError(f"ไม่พบรูปอ้างอิงใบหน้า: {face_ref}")
        try:
            fs = float(face_strength)
        except (TypeError, ValueError):
            raise ValueError(f"face_strength ต้องเป็นตัวเลข 0..1 (ได้ {face_strength})")
        if not 0 < fs <= 1:
            raise ValueError(f"face_strength ต้องอยู่ระหว่าง 0..1 (ได้ {face_strength})")
    else:
        fs = None
    if not os.path.isfile(SD_CLI):
        raise FileNotFoundError(f"ไม่พบ sd-cli.exe ที่ {SD_CLI} (ต้องลงแอป Amuse ก่อน หรือติดตั้ง GenJab ใหม่)")
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    files = model_files(model)
    face_args = []
    if face_ref:
        face_files = ip_adapter_files()
        face_args = ["--clip_vision", face_files["clip_vision"],
                     "--ip-adapter", face_files["ip_adapter"],
                     "--ip-adapter-image", os.path.abspath(face_ref),
                     "--ip-adapter-strength", str(fs)]
    if w is None:
        with Image.open(init_path) as im:
            iw, ih = im.size
        w, h = fit_init_size(iw, ih, size)
    with tempfile.TemporaryDirectory() as td:
        prompt, lora_args = lora_prompt(prompt, lora, lora_strength)
        out = os.path.join(td, "gen.png")
        model_args = (["--diffusion-model", files["diffusion"]] if "diffusion" in files
                else ["-m", files["m"]])
        cmd = [SD_CLI] + model_args + ["-i", os.path.abspath(init_path),
               "--strength", str(s), "-p", prompt, "-o", out,
               "-W", str(w), "-H", str(h),
               "--steps", str(steps), "--cfg-scale", str(guidance),
               "--seed", str(seed)] + lora_args + face_args
        if negative:
            cmd += ["-n", negative]
        cmd += _extra_args(files)
        if lora and model == "flux1-dev":
            # flux1-dev fp8 + LoRA needs CPU offload (Vulkan CPY buffer fails otherwise)
            cmd += ["--offload-to-cpu"]
        p = _run(cmd, cancel_event)
        if p.returncode != 0 or not os.path.isfile(out):
            raise RuntimeError(f"sd-cli ล้มเหลว:\n{(p.stderr or p.stdout)[-800:]}")
        return Image.open(out).convert("RGB"), seed


VIDEO_MODELS = ("minimax-h3", "wan22-5b")

# ค่าเริ่มตาม DefaultOptions ในเทมเพลตของ Amuse (Templates.json)
VIDEO_DEFAULTS = {
    "minimax-h3": {"steps": 20, "guidance": 1.0, "frames": 56, "fps": 24,
                   "width": 864, "height": 480},
    "wan22-5b": {"steps": 30, "guidance": 5.0, "frames": 121, "fps": 24,
                 "width": 1280, "height": 704},
}

VIDEO_EXTS = (".webm", ".avi")


def txt2vid(prompt, model, width=None, height=None, frames=None, fps=None,
            steps=None, guidance=None, seed=None, negative="", output="out/vid.webm",
            cancel_event=None):
    """เจนวิดีโอจากข้อความด้วย sd-cli `-M vid_gen` คืน (path ไฟล์วิดีโอ, seed ที่ใช้จริง).

    ค่าไหนไม่ส่งมาใช้ VIDEO_DEFAULTS ของโมเดลนั้น (ตรงกับที่ Amuse ใช้)."""
    if model not in VIDEO_MODELS:
        raise ValueError(f"โมเดลวิดีโอไม่รู้จัก: {model} (มี: {', '.join(VIDEO_MODELS)})")
    d = VIDEO_DEFAULTS[model]
    width = d["width"] if width is None else int(width)
    height = d["height"] if height is None else int(height)
    frames = d["frames"] if frames is None else int(frames)
    fps = d["fps"] if fps is None else int(fps)
    steps = d["steps"] if steps is None else int(steps)
    guidance = d["guidance"] if guidance is None else float(guidance)
    if width <= 0 or height <= 0:
        raise ValueError(f"width/height ต้อง > 0 (ได้ {width}x{height})")
    if frames < 1:
        raise ValueError(f"frames ต้อง >= 1 (ได้ {frames})")
    if fps < 1:
        raise ValueError(f"fps ต้อง >= 1 (ได้ {fps})")
    ext = os.path.splitext(output)[1].lower()
    if ext not in VIDEO_EXTS:
        raise ValueError(f"ไฟล์วิดีโอต้องลงท้าย {VIDEO_EXTS} (ได้ {output})")
    if not os.path.isfile(SD_CLI):
        raise FileNotFoundError(f"ไม่พบ sd-cli.exe ที่ {SD_CLI} (ต้องลงแอป Amuse ก่อน หรือติดตั้ง GenJab ใหม่)")
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    files = model_files(model)
    out = os.path.abspath(output)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    model_args = (["--diffusion-model", files["diffusion"]] if "diffusion" in files
                  else ["-m", files["m"]])
    cmd = [SD_CLI] + model_args + ["-M", "vid_gen", "-p", prompt, "-o", out,
           "-W", str(width), "-H", str(height),
           "--video-frames", str(frames), "--fps", str(fps),
           "--steps", str(steps), "--cfg-scale", str(guidance),
           "--seed", str(seed)]
    if negative:
        cmd += ["-n", negative]
    if "llm" in files:
        cmd += ["--llm", files["llm"]]
    if "t5xxl" in files:
        cmd += ["--t5xxl", files["t5xxl"]]
    if "vae" in files:
        cmd += ["--vae", files["vae"]]
    if "audio_vae" in files:
        cmd += ["--audio-vae", files["audio_vae"]]
    p = _run(cmd, cancel_event)
    if p.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError(f"sd-cli ล้มเหลว:\n{(p.stderr or p.stdout)[-800:]}")
    return out, seed


I2V_MODELS = ("wan22-5b",)

I2V_DEFAULTS = {
    "wan22-5b": {"steps": 12, "guidance": 6.0, "frames": 17, "fps": 16},
}


def fit_video_size(w, h, long_side=512):
    """ย่อขนาดคลิปให้ด้านยาว = long_side คงสัดส่วน — แต่ละด้านปัดให้ลงตัวกับ 16 ขั้นต่ำ 16."""
    w, h = int(w), int(h)
    if w <= 0 or h <= 0:
        raise ValueError(f"ขนาดรูปต้นฉบับต้อง > 0 (ได้ {w}x{h})")
    long_side = int(long_side)
    if long_side <= 0:
        raise ValueError(f"size ต้อง > 0 (ได้ {long_side})")
    scale = long_side / max(w, h)
    return (max(16, round(w * scale / 16) * 16),
            max(16, round(h * scale / 16) * 16))


def img2vid(init_path, prompt, model="wan22-5b", size=512, width=None, height=None,
            frames=None, fps=None, steps=None, guidance=None, seed=None, negative="",
            sampler="euler", flow_shift=3.0, output="out/vid.webm", cancel_event=None):
    """ทำภาพนิ่งให้ขยับ (`-M vid_gen` + `-i`) คืน (path ไฟล์วิดีโอ, seed ที่ใช้จริง).

    ค่าไหนไม่ส่งมาใช้ I2V_DEFAULTS ของโมเดลนั้น."""
    from PIL import Image
    if model not in I2V_MODELS:
        raise ValueError(f"โมเดลนี้ทำภาพขยับไม่ได้: {model} (ได้: {', '.join(I2V_MODELS)})")
    if not init_path or not os.path.isfile(init_path):
        raise FileNotFoundError(f"ไม่พบรูปต้นฉบับ: {init_path}")
    d = I2V_DEFAULTS[model]
    frames = d["frames"] if frames is None else int(frames)
    fps = d["fps"] if fps is None else int(fps)
    steps = d["steps"] if steps is None else int(steps)
    guidance = d["guidance"] if guidance is None else float(guidance)
    if frames < 1:
        raise ValueError(f"frames ต้อง >= 1 (ได้ {frames})")
    if fps < 1:
        raise ValueError(f"fps ต้อง >= 1 (ได้ {fps})")
    ext = os.path.splitext(output)[1].lower()
    if ext not in VIDEO_EXTS:
        raise ValueError(f"ไฟล์วิดีโอต้องลงท้าย {VIDEO_EXTS} (ได้ {output})")
    if width is not None or height is not None:
        if width is None or height is None:
            raise ValueError(f"ต้องระบุ width/height คู่กัน (ได้ {width}x{height})")
        w, h = int(width), int(height)
        if w <= 0 or h <= 0:
            raise ValueError(f"width/height ต้อง > 0 (ได้ {w}x{h})")
    else:
        w = h = None
    if not os.path.isfile(SD_CLI):
        raise FileNotFoundError(f"ไม่พบ sd-cli.exe ที่ {SD_CLI} (ต้องลงแอป Amuse ก่อน หรือติดตั้ง GenJab ใหม่)")
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    files = model_files(model)
    if w is None:
        with Image.open(init_path) as im:
            iw, ih = im.size
        w, h = fit_video_size(iw, ih, size)
    out = os.path.abspath(output)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    cmd = [SD_CLI, "--diffusion-model", files["diffusion"], "-M", "vid_gen",
           "-i", os.path.abspath(init_path), "-p", prompt, "-o", out,
           "-W", str(w), "-H", str(h),
           "--video-frames", str(frames), "--fps", str(fps),
           "--steps", str(steps), "--cfg-scale", str(guidance),
           "--sampling-method", str(sampler), "--flow-shift", str(flow_shift),
           "--seed", str(seed)]
    if negative:
        cmd += ["-n", negative]
    cmd += _extra_args(files)
    p = _run(cmd, cancel_event)
    if p.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError(f"sd-cli ล้มเหลว:\n{(p.stderr or p.stdout)[-800:]}")
    return out, seed


def main():
    ap = argparse.ArgumentParser(description="เจนรูป/วิดีโอจากข้อความ (sd.cpp + Amuse runtime)")
    ap.add_argument("prompt", help="คำบรรยายภาพภาษาอังกฤษ")
    ap.add_argument("-o", "--output", default="out/pic.png")
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--size", default=512,
                    help="ด้านยาวของรูป (เช่น 512) หรือ WxH ตรง ๆ (เช่น 512x768)")
    ap.add_argument("--ratio", default="1:1", choices=sorted(RATIOS),
                    help="สัดส่วนรูป (3:4/9:16 = แนวตั้ง, 16:9 = แนวนอน)")
    ap.add_argument("--width", type=int, default=None, help="ความกว้างตรง ๆ (เหนือกว่า size/ratio)")
    ap.add_argument("--height", type=int, default=None, help="ความสูงตรง ๆ (เหนือกว่า size/ratio)")
    ap.add_argument("--cfg", type=float, default=1.0)
    ap.add_argument("--lora", default=None,
                    help="ชื่อ LoRA (เช่น anima-turbo-lora-v0.2) หรือ path ตรง ๆ")
    ap.add_argument("--lora-strength", type=float, default=1.0, help="ความแรง LoRA")
    ap.add_argument("-n", "--negative", default="")
    ap.add_argument("--init-img", default=None, help="รูปต้นฉบับสำหรับโหมดแปลงรูป")
    ap.add_argument("--strength", type=float, default=0.6,
                    help="ความแรงแปลงรูป 0..1 (เฉพาะ --init-img)")
    ap.add_argument("--style", default=None, choices=list(STYLE_PRESETS),
                    help="สไตล์เทศกาลต่อท้าย prompt (เฉพาะ --init-img)")
    ap.add_argument("--keep-face", action="store_true",
                    help="คงหน้าเดิมจากรูปต้นฉบับ (เฉพาะ --init-img + โมเดล SDXL)")
    ap.add_argument("--face-ref", default=None,
                    help="รูปอ้างอิงใบหน้าแยก (เฉพาะ --init-img + โมเดล SDXL)")
    ap.add_argument("--face-strength", type=float, default=0.6,
                    help="ความแรงคงหน้า 0..1 (เฉพาะ --init-img)")
    ap.add_argument("--model", default="sd-turbo",
                    choices=["sd-turbo", "sdxl-turbo", "sdxl-base", "anima-turbo", "anima-base", "anima-aesthetic",
                    "qwen21", "qwen21-turbo", "iris-3b", "flux2-klein", "minimax-h3", "wan22-5b", "flux1-dev"])
    ap.add_argument("--count", type=int, default=1, help="จำนวนรูป/คลิปต่อครั้ง (รูปโหลดโมเดลครั้งเดียว)")
    ap.add_argument("--frames", type=int, default=None, help="จำนวนเฟรมวิดีโอ (ค่าเริ่มตามโมเดล)")
    ap.add_argument("--fps", type=int, default=None, help="เฟรมต่อวินาทีของวิดีโอ (ค่าเริ่มตามโมเดล)")
    args = ap.parse_args()
    if args.init_img:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        prompt, negative = apply_style(args.prompt, args.negative, args.style)
        face_ref = args.face_ref or (args.init_img if args.keep_face else None)
        if args.model in VIDEO_MODELS:
            if args.lora:
                raise ValueError("โมเดลวิดีโอไม่รองรับ LoRA")
            seeds = _batch_seeds(args.seed, args.count)
            base, ext = os.path.splitext(args.output)
            if ext.lower() not in VIDEO_EXTS:
                args.output = base + ".webm"
                base, ext = os.path.splitext(args.output)
            for i, seed in enumerate(seeds):
                path = args.output if args.count == 1 else f"{base}_{i}{ext}"
                out, seed = img2vid(args.init_img, prompt, model=args.model,
                                    size=args.size, width=args.width, height=args.height,
                                    frames=args.frames, fps=args.fps,
                                    steps=args.steps if args.steps != 4 else None,
                                    guidance=args.cfg if args.cfg != 1.0 else None,
                                    seed=seed, negative=negative, output=path)
                print("saved:", out, "seed:", seed)
            return
        seeds = _batch_seeds(args.seed, args.count)
        base, ext = os.path.splitext(args.output)
        if not ext:
            args.output += ".png"
            base, ext = os.path.splitext(args.output)
        for i, seed in enumerate(seeds):
            img, used = img2img(args.init_img, prompt, strength=args.strength,
                                steps=args.steps, seed=seed, size=args.size,
                                guidance=args.cfg, negative=negative,
                                model=args.model, width=args.width,
                                height=args.height, lora=args.lora,
                                lora_strength=args.lora_strength,
                                face_ref=face_ref, face_strength=args.face_strength)
            path = args.output if args.count == 1 else f"{base}_{i}{ext}"
            img.save(path)
            print("saved:", path, "seed:", used)
        return
    if args.model in VIDEO_MODELS:
        if args.lora:
            raise ValueError("โมเดลวิดีโอไม่รองรับ LoRA")
        seeds = _batch_seeds(args.seed, args.count)
        base, ext = os.path.splitext(args.output)
        if ext.lower() not in VIDEO_EXTS:
            args.output = base + ".webm"
            base, ext = os.path.splitext(args.output)
        for i, seed in enumerate(seeds):
            path = args.output if args.count == 1 else f"{base}_{i}{ext}"
            out, seed = txt2vid(args.prompt, model=args.model, seed=seed,
                                width=args.width, height=args.height,
                                frames=args.frames, fps=args.fps,
                                steps=args.steps if args.steps != 4 else None,
                                guidance=args.cfg if args.cfg != 1.0 else None,
                                negative=args.negative, output=path)
            print("saved:", out, "seed:", seed)
        return
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    if args.count > 1:
        results = txt2img_batch(args.prompt, n=args.count, steps=args.steps, seed=args.seed,
                                size=args.size, guidance=args.cfg, negative=args.negative,
                                model=args.model, ratio=args.ratio, lora=args.lora,
                                lora_strength=args.lora_strength,
                                width=args.width, height=args.height)
        base, ext = os.path.splitext(args.output)
        for i, (img, seed) in enumerate(results):
            path = f"{base}_{i}{ext}"
            img.save(path)
            print("saved:", path, "seed:", seed)
        return
    img, seed = txt2img(args.prompt, steps=args.steps, seed=args.seed, lora=args.lora,
                        lora_strength=args.lora_strength,
                        size=args.size, guidance=args.cfg, negative=args.negative,
                        model=args.model, ratio=args.ratio,
                        width=args.width, height=args.height)
    img.save(args.output)
    print("saved:", args.output, "seed:", seed)


if __name__ == "__main__":
    main()
