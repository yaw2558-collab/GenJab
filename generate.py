"""Core text-to-image: เรียก sd-cli.exe (stable-diffusion.cpp + Vulkan, ตัวเดียวกับที่ Amuse ใช้)
   กับโมเดล SD-Turbo — เจน 512px ในไม่กี่วินาทีบนการ์ดจอ AMD."""
import argparse
import glob
import os
import random
import subprocess
import tempfile

SD_CLI = os.environ.get(
    "TEXT2IMAGE_SDCLI",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Amuse",
                 "RuntimeStableDiffusionCpp", "vulkan", "sd-cli.exe"))
MODEL = os.environ.get("TEXT2IMAGE_MODEL", "")  # ว่าง = หา sd_turbo.safetensors ใน HF cache เอง
AMUSE_MODELS = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Amuse", "Models")


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
    if name == "anima-turbo":
        f = {"m": os.path.join(AMUSE_MODELS, "Diffusion", "anima-turbo-v1.0.safetensors"),
             "llm": os.path.join(AMUSE_MODELS, "TextEncoder", "Qwen3-0.6B-Q8_0.gguf"),
             "vae": os.path.join(AMUSE_MODELS, "AutoEncoder", "QwenImage",
                                 "diffusion_pytorch_model.safetensors")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(f"ไม่พบไฟล์ anima-turbo: {missing} (ต้องลงโมเดลในแอป Amuse ก่อน)")
        return f
    raise ValueError(f"โมเดลไม่รู้จัก: {name} (มี: sd-turbo, anima-turbo)")


def txt2img(prompt, steps=4, guidance=1.0, size=512, seed=None, negative="", model="sd-turbo"):
    """เจนรูป คืน (PIL Image, seed ที่ใช้จริง) — ไม่ส่ง seed มาสุ่มให้เองทุกครั้ง."""
    from PIL import Image
    if not os.path.isfile(SD_CLI):
        raise FileNotFoundError(f"ไม่พบ sd-cli.exe ที่ {SD_CLI} (ต้องลงแอป Amuse ก่อน)")
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    files = model_files(model)
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "gen.png")
        cmd = [SD_CLI, "-m", files["m"], "-p", prompt, "-o", out,
               "-W", str(size), "-H", str(size),
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


def main():
    ap = argparse.ArgumentParser(description="เจนรูปจากข้อความ (sd.cpp + SD-Turbo)")
    ap.add_argument("prompt", help="คำบรรยายภาพภาษาอังกฤษ")
    ap.add_argument("-o", "--output", default="out/pic.png")
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--cfg", type=float, default=1.0)
    ap.add_argument("-n", "--negative", default="")
    ap.add_argument("--model", default="sd-turbo", choices=["sd-turbo", "anima-turbo"])
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    img, seed = txt2img(args.prompt, steps=args.steps, seed=args.seed,
                          size=args.size, guidance=args.cfg, negative=args.negative,
                          model=args.model)
    img.save(args.output)
    print("saved:", args.output, "seed:", seed)


if __name__ == "__main__":
    main()
