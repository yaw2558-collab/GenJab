"""Core text-to-image: เรียก sd-cli.exe (stable-diffusion.cpp + Vulkan, ตัวเดียวกับที่ Amuse ใช้)
   กับโมเดล SD-Turbo — เจน 512px ในไม่กี่วินาทีบนการ์ดจอ AMD."""
import argparse
import glob
import math
import os
import random
import subprocess
import sys
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


def model_files(name):
    """คืน dict ของไฟล์โมเดล ({m} + อาจมี llm/vae) — รองรับ sd-turbo, anima-turbo."""
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
        raise ValueError(f"โมเดลไม่รู้จัก: {name} (มี: sd-turbo, sdxl-turbo, anima-turbo, anima-base, anima-aesthetic)")
    f = {"m": m,
         "llm": os.path.join(AMUSE_MODELS, "TextEncoder", "Qwen3-0.6B-Q8_0.gguf"),
         "vae": os.path.join(AMUSE_MODELS, "AutoEncoder", "QwenImage",
                             "diffusion_pytorch_model.safetensors")}
    missing = [k for k, p in f.items() if not os.path.isfile(p)]
    if missing:
        raise FileNotFoundError(f"ไม่พบไฟล์ {name}: {missing} (ต้องลงโมเดลในแอป Amuse ก่อน)")
    return f


def txt2img(prompt, steps=4, guidance=1.0, size=512, seed=None, negative="", model="sd-turbo",
            ratio="1:1", width=None, height=None, lora=None, lora_strength=1.0):
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
        cmd = [SD_CLI, "-m", files["m"], "-p", prompt, "-o", out,
               "-W", str(w), "-H", str(h),
               "--steps", str(steps), "--cfg-scale", str(guidance),
               "--seed", str(seed)] + lora_args
        if negative:
            cmd += ["-n", negative]
        if "llm" in files:
            cmd += ["--llm", files["llm"]]
        if "vae" in files:
            cmd += ["--vae", files["vae"]]
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
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
                  lora=None, lora_strength=1.0):
    """เจนทีเดียว n รูป (โหลดโมเดลครั้งเดียว) คืน [(PIL Image, seed)] — seed ต่อกันทีละรูป."""
    from PIL import Image
    if not os.path.isfile(SD_CLI):
        raise FileNotFoundError(f"ไม่พบ sd-cli.exe ที่ {SD_CLI} (ต้องลงแอป Amuse ก่อน หรือติดตั้ง GenJab ใหม่)")
    if n < 1:
        raise ValueError(f"จำนวนรูปต้อง >= 1 (ได้ {n})")
    seeds = _batch_seeds(seed, n)
    prompt, lora_args = lora_prompt(prompt, lora, lora_strength)
    files = model_files(model)
    w, h = resolve_size(size, ratio, width, height)
    with tempfile.TemporaryDirectory() as td:
        cmd = [SD_CLI, "-m", files["m"], "-p", prompt, "-o", os.path.join(td, "b_%d.png"),
               "-W", str(w), "-H", str(h),
               "--steps", str(steps), "--cfg-scale", str(guidance),
               "--seed", str(seeds[0]), "-b", str(n)] + lora_args
        if negative:
            cmd += ["-n", negative]
        if "llm" in files:
            cmd += ["--llm", files["llm"]]
        if "vae" in files:
            cmd += ["--vae", files["vae"]]
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        outs = [os.path.join(td, f"b_{i}.png") for i in range(n)]
        if p.returncode != 0 or not all(os.path.isfile(o) for o in outs):
            raise RuntimeError(f"sd-cli ล้มเหลว:\n{(p.stderr or p.stdout)[-800:]}")
        return [(Image.open(o).convert("RGB"), seeds[i]) for i, o in enumerate(outs)]


def main():
    ap = argparse.ArgumentParser(description="เจนรูปจากข้อความ (sd.cpp + SD-Turbo)")
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
    ap.add_argument("--model", default="sd-turbo",
                    choices=["sd-turbo", "sdxl-turbo", "anima-turbo", "anima-base", "anima-aesthetic"])
    ap.add_argument("--count", type=int, default=1, help="จำนวนรูปต่อครั้ง (โหลดโมเดลครั้งเดียว)")
    args = ap.parse_args()
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
