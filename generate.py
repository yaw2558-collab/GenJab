"""Core text-to-image: เรียก sd-cli.exe (stable-diffusion.cpp + Vulkan, ตัวเดียวกับที่ Amuse ใช้)
   กับโมเดล SD-Turbo — เจน 512px ในไม่กี่วินาทีบนการ์ดจอ AMD."""
import argparse
import glob
import math
import os
import random
import subprocess
import tempfile

SD_CLI = os.environ.get(
    "TEXT2IMAGE_SDCLI",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Amuse",
                 "RuntimeStableDiffusionCpp", "vulkan", "sd-cli.exe"))
MODEL = os.environ.get("TEXT2IMAGE_MODEL", "")  # ว่าง = หา sd_turbo.safetensors ใน HF cache เอง
SDXL_TURBO = os.environ.get("TEXT2IMAGE_SDXL_TURBO", "")  # ว่าง = หาใน HF cache / models/ เอง
AMUSE_MODELS = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Amuse", "Models")
LOCAL_MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

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
        if hits:
            return {"m": hits[0]}
        raise FileNotFoundError(
            "ไม่พบโมเดล sd_turbo.safetensors ใน HF cache (เคยโหลดไว้ที่ "
            "models--stabilityai--sd-turbo) — ตั้ง path เองผ่าน env TEXT2IMAGE_MODEL")
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
            ratio="1:1", width=None, height=None):
    """เจนรูป คืน (PIL Image, seed ที่ใช้จริง) — ไม่ส่ง seed มาสุ่มให้เองทุกครั้ง."""
    from PIL import Image
    if not os.path.isfile(SD_CLI):
        raise FileNotFoundError(f"ไม่พบ sd-cli.exe ที่ {SD_CLI} (ต้องลงแอป Amuse ก่อน)")
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    files = model_files(model)
    w, h = resolve_size(size, ratio, width, height)
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "gen.png")
        cmd = [SD_CLI, "-m", files["m"], "-p", prompt, "-o", out,
               "-W", str(w), "-H", str(h),
               "--steps", str(steps), "--cfg-scale", str(guidance),
               "--seed", str(seed)]
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
                  negative="", model="sd-turbo", ratio="1:1", width=None, height=None):
    """เจนทีเดียว n รูป (โหลดโมเดลครั้งเดียว) คืน [(PIL Image, seed)] — seed ต่อกันทีละรูป."""
    from PIL import Image
    if not os.path.isfile(SD_CLI):
        raise FileNotFoundError(f"ไม่พบ sd-cli.exe ที่ {SD_CLI} (ต้องลงแอป Amuse ก่อน)")
    if n < 1:
        raise ValueError(f"จำนวนรูปต้อง >= 1 (ได้ {n})")
    seeds = _batch_seeds(seed, n)
    files = model_files(model)
    w, h = resolve_size(size, ratio, width, height)
    with tempfile.TemporaryDirectory() as td:
        cmd = [SD_CLI, "-m", files["m"], "-p", prompt, "-o", os.path.join(td, "b_%d.png"),
               "-W", str(w), "-H", str(h),
               "--steps", str(steps), "--cfg-scale", str(guidance),
               "--seed", str(seeds[0]), "-b", str(n)]
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
    ap.add_argument("-n", "--negative", default="")
    ap.add_argument("--model", default="sd-turbo",
                    choices=["sd-turbo", "sdxl-turbo", "anima-turbo", "anima-base", "anima-aesthetic"])
    ap.add_argument("--count", type=int, default=1, help="จำนวนรูปต่อครั้ง (โหลดโมเดลครั้งเดียว)")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    if args.count > 1:
        results = txt2img_batch(args.prompt, n=args.count, steps=args.steps, seed=args.seed,
                                size=args.size, guidance=args.cfg, negative=args.negative,
                                model=args.model, ratio=args.ratio,
                                width=args.width, height=args.height)
        base, ext = os.path.splitext(args.output)
        for i, (img, seed) in enumerate(results):
            path = f"{base}_{i}{ext}"
            img.save(path)
            print("saved:", path, "seed:", seed)
        return
    img, seed = txt2img(args.prompt, steps=args.steps, seed=args.seed,
                        size=args.size, guidance=args.cfg, negative=args.negative,
                        model=args.model, ratio=args.ratio,
                        width=args.width, height=args.height)
    img.save(args.output)
    print("saved:", args.output, "seed:", seed)


if __name__ == "__main__":
    main()
