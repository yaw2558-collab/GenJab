"""Text-to-image + image-to-image + text-to-video: เรียก sd-cli.exe (stable-diffusion.cpp + Vulkan,
   ตัวเดียวกับที่ Amuse ใช้) — รูปนิ่ง (SD-Turbo/Anima/Qwen/Iris/MOSS) และวิดีโอ (-M vid_gen)."""
import argparse
import comfy_client
import glob
import json
import math
import os
import random
import sd_server
import struct
import subprocess
import sys
import threading
import tempfile

AMUSE_SD_CLI = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Amuse",
                            "RuntimeStableDiffusionCpp", "vulkan", "sd-cli.exe")
MODEL = os.environ.get("TEXT2IMAGE_MODEL", "")  # ว่าง = หา sd_turbo.safetensors ใน HF cache / models/ เอง
SDXL_TURBO = os.environ.get("TEXT2IMAGE_SDXL_TURBO", "")  # ว่าง = หาใน HF cache / models/ เอง
AMUSE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Amuse")


def resolve_amuse_models():
    """โฟลเดอร์โมเดลของ Amuse — env TEXT2IMAGE_AMUSE_MODELS ก่อน, ตามด้วย DirectoryModel
       ใน Settings.json ของ Amuse (ย้ายโฟลเดอร์โมเดลในแอปแล้วตามไปเอง), สุดท้าย %LOCALAPPDATA%\\Amuse\\Models."""
    env = os.environ.get("TEXT2IMAGE_AMUSE_MODELS", "")
    if env:
        return env
    try:
        with open(os.path.join(AMUSE_DIR, "Settings.json"), encoding="utf-8-sig") as fh:
            d = json.load(fh).get("DirectoryModel")
        if isinstance(d, str) and d:
            return d
    except (OSError, ValueError, AttributeError):
        pass
    return os.path.join(AMUSE_DIR, "Models")


AMUSE_MODELS = resolve_amuse_models()

# ชื่อโฟลเดอร์ย่อยในโฟลเดอร์โมเดลของ Amuse — Amuse 4.0 เปลี่ยนเป็นชื่อแบบ ComfyUI
# (Diffusion→diffusion_models, TextEncoder→text_encoders, AutoEncoder→vae,
# LoraAdapter→loras) — ลองชื่อใหม่ก่อนแล้วค่อยชื่อเก่า (3.x) จะได้ใช้ได้ทั้ง 2 แบบ
AMUSE_SUBDIRS = {
    "diffusion": ("diffusion_models", "Diffusion"),
    "text_encoder": ("text_encoders", "TextEncoder"),
    "vae": ("vae", "AutoEncoder"),
    "lora": ("loras", "LoraAdapter"),
    # ไม่มี "tokenizer" ตัวเล็ก — บน Windows มันซ้อนกับ "Tokenizer" (case-insensitive)
    "tokenizer": ("tokenizers", "Tokenizer"),
    "controlnet": ("controlnet", "ControlNet"),
}


def amuse_subdirs(kind):
    """โฟลเดอร์ Amuse หมวดนี้ทุกชื่อที่เป็นไปได้ — ชื่อใหม่ (4.0) มาก่อนชื่อเก่า (3.x)."""
    return [os.path.join(AMUSE_MODELS, sub) for sub in AMUSE_SUBDIRS[kind]]


def amuse_path(kind, *rest):
    """path ใต้โฟลเดอร์โมเดลของ Amuse — คืนอันที่มีอยู่จริงอันแรก (ใหม่ก่อนเก่า);
    ถ้าไม่มีเลยคืนชื่อใหม่ (layout ปัจจุบัน)."""
    cands = [os.path.join(d, *rest) for d in amuse_subdirs(kind)]
    for p in cands:
        if os.path.exists(p):
            return p
    return cands[0]


def app_dir():
    """โฟลเดอร์ที่แอปรันอยู่ — exe ที่บิลด์แล้วใช้ข้างตัว exe, รันจากซอร์สใช้ข้างไฟล์นี้."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


LOCAL_MODELS = os.path.join(app_dir(), "models")
LOCAL_LORAS = os.path.join(app_dir(), "loras")
SDXL_DIR = os.path.join(LOCAL_MODELS, "sdxl")


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

# โฟลเดอร์ engine สำรองข้างตัวแอป — เรียงจากใหม่ไปเก่า (1106 = 15/11/2026, new = 9/11/2026)
ALT_ENGINE_DIRS = ("sdcli-1106", "sdcli-new")


def resolve_sd_cli_alt():
    """หา sd-cli.exe ตัวสำรอง — env TEXT2IMAGE_SDCLI_ALT ก่อน,
    ตามด้วย sdcli-1106/bin/ แล้ว sdcli-new/bin/ ข้างตัวแอป — ไม่มีคืนสตริงว่าง."""
    env = os.environ.get("TEXT2IMAGE_SDCLI_ALT", "")
    if env:
        return env
    for d in ALT_ENGINE_DIRS:
        p = os.path.join(app_dir(), d, "bin", "sd-cli.exe")
        if os.path.isfile(p):
            return p
    return ""


SD_CLI_ALT = resolve_sd_cli_alt()

# engine ROCm แยกอีกตัว (local only: โฟลเดอร์ sdcli-rocm/ อยู่ใน .gitignore —
# โผล่ในเมนูเฉพาะเครื่องที่มีไบนารี (ต้องลง HIP SDK ด้วยถึงรันได้))
ROCM_ENGINE_DIR = "sdcli-rocm"


def resolve_sd_cli_rocm():
    """หา sd-cli.exe สาย ROCm — env TEXT2IMAGE_SDCLI_ROCM ก่อน,
    ตามด้วย sdcli-rocm/bin/ ข้างตัวแอป — ไม่มีคืนสตริงว่าง."""
    env = os.environ.get("TEXT2IMAGE_SDCLI_ROCM", "")
    if env:
        return env
    p = os.path.join(app_dir(), ROCM_ENGINE_DIR, "bin", "sd-cli.exe")
    if os.path.isfile(p):
        return p
    return ""


SD_CLI_ROCM = resolve_sd_cli_rocm()

ENGINES = ("amuse", "alt", "rocm")


def default_engine():
    """engine ตั้งต้น — Amuse ก่อน (พฤติกรรมเดิม) ถ้าไม่มีค่อยใช้ตัวสำรอง."""
    if os.path.isfile(SD_CLI):
        return "amuse"
    if SD_CLI_ALT and os.path.isfile(SD_CLI_ALT):
        return "alt"
    return "amuse"


DEFAULT_ENGINE = default_engine()


def available_engines():
    """engine id ที่มีไฟล์จริง — amuse โชว์เสมอ (error บอกวิธีลง),
    alt โชว์เมื่อมีไฟล์และไม่ใช่ไฟล์เดียวกับตัวหลัก (เช่น ตั้ง env ชี้ไปไฟล์เดียวกัน)."""
    ids = ["amuse"]
    if SD_CLI_ALT and os.path.isfile(SD_CLI_ALT):
        same = (os.path.isfile(SD_CLI)
                and os.path.normcase(os.path.abspath(SD_CLI_ALT))
                == os.path.normcase(os.path.abspath(SD_CLI)))
        if not same:
            ids.append("alt")
    if SD_CLI_ROCM and os.path.isfile(SD_CLI_ROCM):
        same = (os.path.isfile(SD_CLI)
                and os.path.normcase(os.path.abspath(SD_CLI_ROCM))
                == os.path.normcase(os.path.abspath(SD_CLI)))
        if not same:
            ids.append("rocm")
    return ids


def path_tag(path):
    """ชื่อสั้นของ path sd-cli ไว้โชว์ใน GUI (1106 / new / amuse / bundled / กำหนดเอง)."""
    low = (path or "").lower()
    for d in ALT_ENGINE_DIRS:
        if d in low:
            return d.replace("sdcli-", "")
    if "amuse" in low:
        return "amuse"
    if "runtime" in low:
        return "bundled"
    return "กำหนดเอง" if path else "—"


def alt_engine_tag():
    """ชื่อสั้นของ engine สำรองไว้โชว์ใน GUI (1106 / new / กำหนดเอง)."""
    return path_tag(SD_CLI_ALT)


def rocm_engine_tag():
    """ชื่อสั้นของ engine ROCm ไว้โชว์ใน GUI (rocm / กำหนดเอง)."""
    return path_tag(SD_CLI_ROCM)


def main_engine_label():
    """ป้าย engine ตัวหลัก — บอกที่มาจริง (env/bundled/Amuse) ไม่ใช่ชื่อตายตัว."""
    if os.environ.get("TEXT2IMAGE_SDCLI"):
        return f"ตัวหลัก ({path_tag(SD_CLI)})"
    if SD_CLI and "runtime" in SD_CLI.lower() and os.path.isfile(SD_CLI):
        return "ตัวหลัก (bundled)"
    return "Amuse (ตัวหลัก)"


# โมเดลที่ต้องใช้ sigmas preset เฉพาะ — engine ไหนไม่มี preset นี้ใช้โมเดลนี้ไม่ได้
# (เช่น sdcli-new บิลด์ 9/11/2026 ไม่มี minimax-h3-image)
MODEL_NEEDS_SIGMA = {"minimax-h3-image": "minimax-h3-image"}

_ENGINE_HELP_CACHE = {}


def _engine_help(path):
    """ข้อความ --help ของ engine (cache ราย path) — รันไม่ได้คืนสตริงว่าง (แล้วค่อยล้มตอนเจนจริง)."""
    if path not in _ENGINE_HELP_CACHE:
        try:
            p = subprocess.run([path, "--help"], capture_output=True, text=True,
                               errors="replace", timeout=15,
                               creationflags=_popen_flags())
            _ENGINE_HELP_CACHE[path] = (p.stdout or "") + (p.stderr or "")
        except (OSError, ValueError, subprocess.SubprocessError):
            _ENGINE_HELP_CACHE[path] = ""
    return _ENGINE_HELP_CACHE[path]


def engine_has(path, keyword):
    """engine ตัวนี้รู้จัก keyword ใน --help ไหม — รันไม่ได้ถือว่ามี (ไม่ขวางทางเจนจริง)."""
    help_text = _engine_help(path)
    return (not help_text) or (keyword in help_text)


def sd_cli_for(engine=None, model=None):
    """คืน path sd-cli.exe ตาม engine — ว่าง = DEFAULT_ENGINE (Amuse ถ้ามี).

    model ที่ต้องใช้ preset เฉพาะจะตรวจก่อน — engine ไม่รองรับ raise RuntimeError พร้อมบอกให้สลับตัว."""
    e = engine or DEFAULT_ENGINE
    if e not in ENGINES:
        raise ValueError(f"engine ไม่รู้จัก: {engine} (มี: {', '.join(ENGINES)})")
    if e in ("alt", "rocm"):
        if e == "alt":
            cli, tag = SD_CLI_ALT, alt_engine_tag()
            hint = ("วางบิลด์ใหม่ไว้ที่ sdcli-1106/bin/ ข้างโปรแกรม "
                    "หรือตั้ง path ผ่าน env TEXT2IMAGE_SDCLI_ALT")
        else:
            cli, tag = SD_CLI_ROCM, rocm_engine_tag()
            hint = ("วางบิลด์ ROCm ไว้ที่ sdcli-rocm/bin/ ข้างโปรแกรม "
                    "(ต้องลง HIP SDK ด้วย) หรือตั้ง path ผ่าน env TEXT2IMAGE_SDCLI_ROCM")
        if not cli or not os.path.isfile(cli):
            raise FileNotFoundError(
                f"ไม่พบ sd-cli.exe ของ engine {e} ที่ {cli or '(ไม่ได้ตั้งค่า)'} — {hint}")
        need = MODEL_NEEDS_SIGMA.get(model or "")
        if need and not engine_has(cli, need):
            raise RuntimeError(
                f"engine {e} ({tag}) ไม่รองรับโมเดล {model} "
                f"(ไม่มี sigmas preset {need}) — สลับ engine เป็น Amuse หรือใช้บิลด์ที่ใหม่กว่า")
        return cli
    if not os.path.isfile(SD_CLI):
        raise FileNotFoundError(f"ไม่พบ sd-cli.exe ที่ {SD_CLI} (ต้องลงแอป Amuse ก่อน หรือติดตั้ง GenJab ใหม่)")
    return SD_CLI


IP_ADAPTER_FLAG = "--ip-adapter"
# ลำดับ engine สำรองตอนตัวที่เลือกไม่มี --ip-adapter (sd.cpp 1132+/Amuse 4.0 ถอดออกแล้ว)
FACE_FALLBACK_ORDER = ("alt", "rocm", "amuse")


def face_engine(engine=None, model=None):
    """engine ที่ใช้คงหน้าเดิม (IP-Adapter) ได้ คืน (engine id, path sd-cli).

    ตัวที่เลือกมีแฟล็ก --ip-adapter ใช้ตัวนั้น ไม่มีค่อยไล่ alt → rocm → amuse
    (Amuse 4.0 = sd.cpp 5fa203c ถอดแฟล็กนี้ออก) — ไม่เหลือสักตัว raise RuntimeError."""
    e = engine or DEFAULT_ENGINE
    cli = sd_cli_for(e, model)
    if engine_has(cli, IP_ADAPTER_FLAG):
        return e, cli
    for o in FACE_FALLBACK_ORDER:
        if o == e:
            continue
        try:
            c = sd_cli_for(o, model)
        except (FileNotFoundError, RuntimeError):
            continue
        if engine_has(c, IP_ADAPTER_FLAG):
            return o, c
    raise RuntimeError(
        f"engine {e} ({path_tag(cli)}) ไม่มี {IP_ADAPTER_FLAG} แล้ว (sd.cpp รุ่นใหม่/Amuse 4.0 ถอดออก) "
        "และไม่มี engine อื่นที่ใช้คงหน้าเดิมได้ — วางบิลด์ 1106 ไว้ที่ sdcli-1106/bin/ "
        "ข้างโปรแกรม หรือเอาติ๊กคงหน้าเดิมออก")


LORA_ENV_DIRS = [p for p in os.environ.get("TEXT2IMAGE_LORA_DIR", "").split(os.pathsep) if p]


def lora_dirs():
    """โฟลเดอร์ที่ค้นหา LoRA — env TEXT2IMAGE_LORA_DIR มาก่อน, ตามด้วยของ Amuse + loras/."""
    return ([os.path.normpath(p) for p in LORA_ENV_DIRS if os.path.isdir(p)]
            + amuse_subdirs("lora")
            + [os.path.join(AMUSE_MODELS, "Models", "loras"),
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


# ตระกูลของโมเดล — LoRA ใช้ข้ามตระกูลไม่ได้ (sd-cli ไม่กัน ใส่ให้เงียบ ๆ แล้วรูปเพี้ยน)
MODEL_FAMILY = {"sd-turbo": "sd2", "sdxl-turbo": "sdxl", "sdxl-base": "sdxl",
                "anima-turbo": "anima", "anima-base": "anima", "anima-aesthetic": "anima",
                "zimage-turbo": "zimage", "moss-sft": "moss"}
_LORA_FAMILY_CACHE = {}
CUSTOM_SDXL_PREFIX = "sdxl:"


def model_family(model):
    """ตระกูลของโมเดล — SDXL ที่วางเองใน models/sdxl/ (sdxl:ชื่อ) นับเป็น sdxl."""
    if str(model).startswith(CUSTOM_SDXL_PREFIX):
        return "sdxl"
    return MODEL_FAMILY.get(model)


def lora_family(path):
    """เดาตระกูลของ LoRA จากชื่อ tensor ใน header — ไม่รู้จัก/อ่านไม่ได้คืน None."""
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        return None
    if key in _LORA_FAMILY_CACHE:
        return _LORA_FAMILY_CACHE[key]
    fam = None
    try:
        with open(path, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            if 0 < n < 100_000_000:
                names = " ".join(json.loads(f.read(n)))
                # LoRA ที่เทรนจาก sd-scripts ไม่มีชั้น adaln — ใช้ชื่อ mlp.layer1 ของ MiniTrainDIT แทน
                if ("adaln_modulation_cross_attn" in names or "llm_adapter" in names
                        or ".mlp.layer1." in names or "_mlp_layer1." in names):
                    fam = "anima"
                elif "double_blocks" in names or "single_transformer_blocks" in names:
                    fam = "flux1"
                elif "lora_te2_" in names or "text_encoder_2" in names:
                    fam = "sdxl"
    except (OSError, ValueError, struct.error):
        fam = None
    _LORA_FAMILY_CACHE[key] = fam
    return fam


def lora_compatible(lora, model):
    """LoRA ใช้กับโมเดลนี้ได้ไหม — รู้ตระกูลทั้งคู่แล้วไม่ตรงกันเท่านั้นถึงคืน False."""
    if not lora:
        return True
    p = list_loras().get(lora) or (lora if os.path.isfile(str(lora)) else None)
    fam = lora_family(p) if p else None
    want = model_family(model)
    return fam is None or want is None or fam == want


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


PREVIEW_FLAG = "--preview"


def preview_args(cli, td, on_preview):
    """แฟล็กดูรูประหว่างเจน (latent projection — ไม่ต้องมีไฟล์โมเดลเพิ่ม) คืน (args, (path, callback)).

    ไม่ส่ง on_preview มา หรือ engine ไม่รู้จัก --preview คืน ([], None) — เจนปกติไม่ดูรูประหว่างทาง."""
    if on_preview is None or not engine_has(cli, PREVIEW_FLAG):
        return [], None
    path = os.path.join(td, "preview.png")
    return (["--preview", "proj", "--preview-path", path, "--preview-interval", "1"],
            (path, on_preview))


def _poll_preview(watch, last):
    """ไฟล์ preview เปลี่ยนตั้งแต่ครั้งก่อนไหม — เปลี่ยนเรียก callback(PIL Image) คืน mtime ใหม่.

    sd-cli เขียนไฟล์ทับระหว่างอ่านได้ เปิดไม่ขึ้นข้ามไปรอรอบหน้า; callback พังไม่ล้มงานเจน."""
    path, cb = watch
    try:
        m = os.path.getmtime(path)
    except OSError:
        return last
    if m == last:
        return last
    try:
        from PIL import Image
        with Image.open(path) as im:
            img = im.convert("RGB")
    except Exception:  # noqa: BLE001 — ไฟล์ยังเขียนไม่เสร็จ
        return last
    try:
        cb(img)
    except Exception:  # noqa: BLE001
        pass
    return m


def _run(cmd, cancel_event=None, preview=None):
    """Run sd-cli, return CompletedProcess - with cancel_event kill it when user cancels.

    preview = (path, callback) จาก preview_args — ระหว่างรันเรียก callback ทุกครั้งที่รูปตัวอย่างเปลี่ยน.
    ปิด sd-server ก่อนเสมอ (คืน VRAM ให้ sd-cli — วิดีโอ/ขยายรูป/คงหน้าเดิม)."""
    sd_server.SERVER.stop()
    _stop_llm()
    if cancel_event is None and preview is None:
        return subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                              creationflags=_popen_flags())
    if cancel_event is None:
        cancel_event = threading.Event()  # ไม่มีปุ่มยกเลิก ใช้ลูปเดียวกันเพื่อดู preview
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
    last_preview = None
    while proc.poll() is None:
        if preview is not None:
            last_preview = _poll_preview(preview, last_preview)
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


def _stop_llm():
    """ปิด llama-server (ตัวแปลไทย) ถ้าเปิดอยู่ — คืน VRAM ให้โมเดลรูป (ไม่ import ถ้าไม่เคยใช้)."""
    m = sys.modules.get("local_llm")
    if m is not None:
        m.LLM.stop()


def _server_gen(cli, model, files, prompt, lora_args, negative, w, h, steps, guidance, seed,
                n=1, init_path=None, strength=None, mask_path=None, cancel_event=None):
    """เจนผ่าน sd-server (โมเดลค้างใน VRAM) คืน [PIL Image] — ใช้ไม่ได้คืน None ให้ผู้เรียกใช้ sd-cli แทน.

    prompt = ตัวที่ผ่าน lora_prompt แล้ว (มีแท็ก) — แยกแท็กออกเป็นฟิลด์ lora ให้ server
    ได้รูปเท่ากับ sd-cli ทุกพิกเซล; กดยกเลิก raise GenerationCancelled."""
    if model in MODEL_EXTRA_ARGS or model == "flux2-dev":
        return None
    exe = sd_server.server_exe_for(cli)
    if not exe:
        return None
    model_args = (["--diffusion-model", files["diffusion"]] if "diffusion" in files
                  else ["-m", files["m"]])
    ctx = model_args + _extra_args(files) + list(lora_args)
    clean, loras = sd_server.split_lora(prompt)
    body = {"prompt": clean, "negative_prompt": negative or "", "steps": int(steps),
            "cfg_scale": float(guidance), "width": int(w), "height": int(h),
            "seed": int(seed), "batch_size": int(n)}
    if loras:
        lora_dir = lora_args[lora_args.index("--lora-model-dir") + 1] if "--lora-model-dir" in lora_args else ""
        body["lora"] = sd_server.lora_field(loras, lora_dir)
    if init_path:
        body["denoising_strength"] = float(strength)
    _stop_llm()
    try:
        imgs = sd_server.SERVER.generate(exe, ctx, body, init_path=init_path,
                                         mask_path=mask_path, cancel_event=cancel_event)
    except sd_server.ServerCancelled:
        raise GenerationCancelled()
    except Exception as e:  # noqa: BLE001 — server พัง ถอยไป sd-cli (ช้ากว่าแต่ชัวร์)
        print(f"[sd-server] ใช้ไม่ได้ ถอยไป sd-cli: {e}", file=sys.stderr)
        sd_server.SERVER.stop()
        return None
    return imgs if len(imgs) == n else None


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
               "llm_vision": "--llm_vision", "audio_vae": "--audio-vae",
               "tokenizer": "--tokenizer"}


def _extra_args(files):
    """แปลงไฟล์เสริมใน dict เป็น argv ของ sd-cli — เรียงตาม EXTRA_FLAGS."""
    args = []
    for key, flag in EXTRA_FLAGS.items():
        if key in files:
            args += [flag, files[key]]
    return args


# argv เสริมรายโมเดล — เติมท้ายคำสั่ง sd-cli เสมอ (เช่น โมเดลใหญ่เกิน VRAM ต้องรันบน CPU)
MODEL_EXTRA_ARGS = {"minimax-h3-image": ["--offload-to-cpu", "--backend", "cpu", "--sampling-method", "euler", "--sigmas", "minimax-h3-image", "--rng", "cpu", "--flash-attn", "off,diffusion=on", "--vae-tiling"]}


def list_sdxl_checkpoints():
    """{ชื่อไฟล์ไม่มีนามสกุล: path} ของ SDXL ไฟล์เดี่ยวที่วางเองใน models/sdxl/ (เช่น RealVisXL, Juggernaut XL)."""
    try:
        names = sorted(os.listdir(SDXL_DIR))
    except OSError:
        return {}
    return {os.path.splitext(f)[0]: os.path.join(SDXL_DIR, f)
            for f in names if f.lower().endswith(".safetensors")}


def model_files(name):
    """คืน dict ของไฟล์โมเดล ({m} + ไฟล์เสริม llm/vae/clip_l/clip_g/t5xxl/llm_vision/audio_vae) —
    รองรับ sd-turbo, sdxl-turbo, sdxl-base, anima-turbo, anima-base, anima-aesthetic, qwen21, qwen21-turbo, iris-3b, iris-turbo, flux2-dev, fibo2-turbo, moss-sft, minimax-h3, minimax-h3-image, wan22-5b, zimage-turbo."""
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
    if str(name).startswith(CUSTOM_SDXL_PREFIX):
        stem = name[len(CUSTOM_SDXL_PREFIX):]
        found = list_sdxl_checkpoints()
        if stem not in found:
            raise FileNotFoundError(f"ไม่พบ models/sdxl/{stem}.safetensors (มี: {', '.join(found) or '—'})")
        return {"m": found[stem]}
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
        f = {"diffusion": amuse_path("diffusion", "qwen_image_2.1_bf16.safetensors"),
             "llm": amuse_path("text_encoder", "Qwen3VL-8B-Instruct-Q8_0.gguf"),
             "llm_vision": amuse_path("text_encoder",
                                        "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"),
             "vae": amuse_path("vae",
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
        f = {"diffusion": diff,
             "llm": amuse_path("text_encoder", "Qwen3VL-8B-Instruct-Q8_0.gguf"),
             "llm_vision": amuse_path("text_encoder", "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"),
             "vae": amuse_path("vae", "qwen_image_2.1_vae_bf16.safetensors")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing Qwen 2.1 Turbo files: {missing} "
                "(load Qwen 2.1 model in Amuse first, Turbo file goes to models/)")
        return f
    if name == "flux2-dev":
        # FLUX.2 dev 32B (GGUF Q4) + Mistral Small 3.2 24B (GGUF Q4) + flux2 VAE — ไฟล์อยู่ใน models/
        # รวม ~34GB — VRAM 16GB ต้องพึ่ง --offload-to-cpu (txt2img ใส่ให้อัตโนมัติ)
        override = os.environ.get("TEXT2IMAGE_FLUX2_DEV", "")
        diff = override if override and os.path.isfile(override) else ""
        if not diff:
            diff = os.path.join(LOCAL_MODELS, "flux2-dev-Q4_K_M.gguf")
        llm = os.path.join(LOCAL_MODELS, "Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf")
        f = {"diffusion": diff, "llm": llm,
             "vae": os.path.join(LOCAL_MODELS, "flux2-vae.safetensors")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing FLUX.2 dev files: {missing} (put them in models/)")
        return f
    if name == "fibo2-turbo":
        # Fibo 2.0 Turbo (GGUF Q8, Amuse) + Qwen3VL-4B + mmproj + Flux2 VAE
        f = {"diffusion": amuse_path("diffusion", "fibo2_edit_turbo-Q8_0.gguf"),
             "llm": amuse_path("text_encoder", "Qwen3VL-4B-Instruct-Q8_0.gguf"),
             "llm_vision": amuse_path("text_encoder",
                                        "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf"),
             "vae": amuse_path("vae", "Flux2",
                                 "diffusion_pytorch_model.safetensors")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing Fibo 2.0 Turbo files: {missing} (load Fibo 2.0 Turbo model in Amuse first)")
        return f
    if name == "zimage-turbo":
        # Z-Image-Turbo GGUF Q4_K + Qwen3-4B-Instruct-2507 GGUF ใน models/ + FLUX.1 VAE ของ Amuse
        override = os.environ.get("TEXT2IMAGE_ZIMAGE_TURBO", "")
        diff = override if override and os.path.isfile(override) else ""
        if not diff:
            diff = os.path.join(LOCAL_MODELS, "z_image_turbo-Q4_K.gguf")
        f = {"diffusion": diff,
             "llm": os.path.join(LOCAL_MODELS, "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"),
             "vae": amuse_path("vae", "Flux1",
                                 "diffusion_pytorch_model.safetensors")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing Z-Image-Turbo files: {missing} (put z_image_turbo-Q4_K.gguf + "
                "Qwen3-4B-Instruct-2507-Q4_K_M.gguf in models/, load a FLUX.1 model in Amuse first)")
        return f
    if name == "iris-3b":
        # Iris-3B เป็นโมเดลภาพนิ่ง (Amuse เรียกผ่าน TextToImage pipeline):
        # diffusion prefix `model.diffusion_model.` + LLM Qwen3VL-4B, ใช้ FakeVAE (ไม่มีไฟล์ vae)
        f = {"diffusion": amuse_path("diffusion", "iris-3b", "model.safetensors"),
             "llm": amuse_path("text_encoder", "Qwen3VL-4B-Instruct-Q8_0.gguf")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing Iris-3B files: {missing} (load Iris model in Amuse first)")
        return f
    if name == "iris-turbo":
        # Iris-3B Turbo 4 steps ไม่ใช้ CFG (distill 12 ต.ค. 2026) — diffusion โหลดเองไว้
        # models/ (Amuse มีแค่ base) + Qwen3VL-4B ชุดเดียวกับ iris-3b, ไม่ใช้ VAE เหมือน base
        override = os.environ.get("TEXT2IMAGE_IRIS_TURBO", "")
        diff = override if override and os.path.isfile(override) else ""
        if not diff:
            for cand in (amuse_path("diffusion", "iris-3b", "turbo",
                                       "model.safetensors"),
                         os.path.join(LOCAL_MODELS, "iris-3b-turbo.safetensors")):
                if os.path.isfile(cand):
                    diff = cand
                    break
        f = {"diffusion": diff or os.path.join(LOCAL_MODELS, "iris-3b-turbo.safetensors"),
             "llm": amuse_path("text_encoder", "Qwen3VL-4B-Instruct-Q8_0.gguf")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing Iris-3B Turbo files: {missing} (put turbo/model.safetensors "
                "from speridlabs/iris-3b in models/ as iris-3b-turbo.safetensors)")
        return f
    if name == "moss-sft":
        # MOSS Image SFT (GGUF Q8, Amuse) + Qwen3.5-9B + Flux2 VAE (ตาม template MossImage_SFT_CPP)
        f = {"diffusion": amuse_path("diffusion", "MOSS-Image-SFT-Q8_0.gguf"),
             "llm": amuse_path("text_encoder", "Qwen3.5-9B-Q8_0.gguf"),
             "vae": amuse_path("vae", "Flux2",
                                 "diffusion_pytorch_model.safetensors"),
             "tokenizer": amuse_path("tokenizer", "MossImage",
                                       "tokenizer.json")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing MOSS Image SFT files: {missing} (load MOSS Image SFT model in Amuse first)")
        return f
    if name == "minimax-h3":
        # MiniMax-H3 (วิดีโอ): diffusion GGUF + LLM Qwen3VL-32B + video VAE + audio VAE
        # ตรงกับที่ Amuse โหลดในล็อก StableDiffusionCpp (MiniMax H3 AV FLOW mode)
        f = {"diffusion": amuse_path("diffusion", "minimax_h3_fl2va_pruned-Q8_0.gguf"),
             "llm": amuse_path("text_encoder",
                                 "qwen3vl_32b_minimax_h3-Q4_K_M.gguf"),
             "vae": amuse_path("vae",
                                 "minimax_h3_video_vae_fp16.safetensors"),
             "audio_vae": amuse_path("vae",
                                       "minimax_h3_audio_vae_fp32.safetensors")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing MiniMax-H3 files: {missing} (load MiniMax-H3 model in Amuse first)")
        return f
    if name == "minimax-h3-image":
        # MiniMax-H3 รูปนิ่ง (Amuse 3.8.7+): diffusion int8 + TE Qwen3VL-32B (ใช้ร่วมกับสายวิดีโอ) + image VAE
        f = {"diffusion": amuse_path("diffusion", "minimax_h3_image_pruned_int8_convrot.safetensors"),
             "llm": amuse_path("text_encoder",
                                 "qwen3vl_32b_minimax_h3-Q4_K_M.gguf"),
             "vae": amuse_path("vae",
                                 "minimax_h3_image_vae_fp16.safetensors")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing MiniMax-H3-Image files: {missing} (load MiniMax-H3 Image model in Amuse first)")
        return f
    if name == "wan22-5b":
        # Wan2.2 TI2V 5B: หา GGUF ใน models/ ก่อน (ชื่อไฟล์ตาม HF) แล้วค่อยของ Amuse
        local = {"diffusion": os.path.join(LOCAL_MODELS, "Wan2.2-TI2V-5B-Q8_0.gguf"),
                 "t5xxl": os.path.join(LOCAL_MODELS, "umt5-xxl-encoder-Q8_0.gguf"),
                 "vae": os.path.join(LOCAL_MODELS, "wan2.2_vae.safetensors")}
        if all(os.path.isfile(p) for p in local.values()):
            return local
        # Wan2.2 TI2V 5B (วิดีโอ t2v/i2v ไฟล์เดียว): diffusion GGUF + UMT5-XXL + Wan22 VAE
        f = {"diffusion": amuse_path("diffusion", "Wan2.2-TI2V-5B-Q8_0.gguf"),
             "t5xxl": amuse_path("text_encoder", "UMT5-XXL", "model.safetensors"),
             "vae": amuse_path("vae", "Wan22", "wan2.2_vae.safetensors")}
        missing = [k for k, p in f.items() if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError(
                f"missing Wan2.2-5B files: {missing} (load Wan2.2 5B model in Amuse first, "
                "or put Wan2.2-TI2V-5B-Q8_0.gguf + umt5-xxl-encoder-Q8_0.gguf + "
                "wan2.2_vae.safetensors in models/)")
        return f
    anima_models = {"anima-turbo": ("anima-turbo-v1.1.safetensors",
                                        "anima-turbo-v1.0.safetensors"),
                    "anima-aesthetic": ("anima-aesthetic-v1.1.safetensors",)}
    if name == "anima-base":
        m = os.path.join(LOCAL_MODELS, "anima-base-sd.cpp.safetensors")
        if not os.path.isfile(m):
            raise FileNotFoundError(
                "ไม่พบ models/anima-base-sd.cpp.safetensors "
                "— รัน `python convert_anima_base.py` ครั้งเดียวก่อน")
    elif name in anima_models:
        # เลือกไฟล์ใหม่สุดที่มี — v1.1 ใน Amuse ก่อน, รองลงมาไฟล์ที่โหลดเองใน models/,
        # สุดท้าย v1.0 เดิมใน Amuse (กันเครื่องที่ยังไม่อัปเดต)
        m = ""
        for fn in anima_models[name]:
            for base in amuse_subdirs("diffusion") + [LOCAL_MODELS]:
                cand = os.path.join(base, fn)
                if os.path.isfile(cand):
                    m = cand
                    break
            if m:
                break
        if not m:
            m = amuse_path("diffusion", anima_models[name][0])
    else:
        raise ValueError(f"โมเดลไม่รู้จัก: {name} (มี: sd-turbo, sdxl-turbo, sdxl-base, anima-turbo, anima-base, anima-aesthetic, qwen21, qwen21-turbo, iris-3b, iris-turbo, flux2-dev, fibo2-turbo, moss-sft, minimax-h3, minimax-h3-image, wan22-5b, zimage-turbo)")
    f = {"m": m,
         "llm": amuse_path("text_encoder", "Qwen3-0.6B-Q8_0.gguf"),
         "vae": amuse_path("vae", "QwenImage",
                             "diffusion_pytorch_model.safetensors")}
    missing = [k for k, p in f.items() if not os.path.isfile(p)]
    if missing:
        raise FileNotFoundError(f"ไม่พบไฟล์ {name}: {missing} (ต้องลงโมเดลในแอป Amuse ก่อน)")
    return f


def txt2img(prompt, steps=4, guidance=1.0, size=512, seed=None, negative="", model="sd-turbo",
            ratio="1:1", width=None, height=None, lora=None, lora_strength=1.0,
            cancel_event=None, engine=None, on_preview=None, server=False, control=None):
    """เจนรูป คืน (PIL Image, seed ที่ใช้จริง) — ไม่ส่ง seed มาสุ่มให้เองทุกครั้ง.

    control = {image, type, strength, net?} คุมโครงรูปด้วย ControlNet (SDXL, ใช้ sd-cli เสมอ).

    on_preview(PIL Image) = ดูรูประหว่างเจนทีละ step (เรียกจากเธรดที่เจน ไม่ใช่เธรด Tk).
    server=True = โหลดโมเดลค้างไว้ใน sd-server (รูปถัดไปเร็วขึ้น ไม่มีภาพระหว่างเจน) — ใช้ไม่ได้ถอยไป sd-cli."""
    from PIL import Image
    cli = sd_cli_for(engine, model)
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    files = model_files(model)
    w, h = resolve_size(size, ratio, width, height)
    if server and not control:
        sp, sl = lora_prompt(prompt, lora, lora_strength)
        imgs = _server_gen(cli, model, files, sp, sl, negative, w, h, steps, guidance, seed,
                           cancel_event=cancel_event)
        if imgs:
            return imgs[0], seed
    with tempfile.TemporaryDirectory() as td:
        prompt, lora_args = lora_prompt(prompt, lora, lora_strength)
        out = os.path.join(td, "gen.png")
        model_args = (["--diffusion-model", files["diffusion"]] if "diffusion" in files
                else ["-m", files["m"]])
        cmd = [cli] + model_args + ["-p", prompt, "-o", out,
               "-W", str(w), "-H", str(h),
               "--steps", str(steps), "--cfg-scale", str(guidance),
               "--seed", str(seed)] + lora_args
        if negative:
            cmd += ["-n", negative]
        cmd += control_args(cli, model, control, w, h, td)
        cmd += _extra_args(files) + MODEL_EXTRA_ARGS.get(model, [])
        if model == "flux2-dev":
            # flux2-dev 32B ใส่ VRAM ไม่หมดอยู่แล้ว — offload ไว้ก่อนเสมอ
            cmd += ["--offload-to-cpu"]
        pv_args, watch = preview_args(cli, td, on_preview)
        p = _run(cmd + pv_args, cancel_event, watch)
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
                  lora=None, lora_strength=1.0, cancel_event=None, engine=None, server=False,
                  control=None):
    """เจนทีเดียว n รูป (โหลดโมเดลครั้งเดียว) คืน [(PIL Image, seed)] — seed ต่อกันทีละรูป (server ดู txt2img)."""
    from PIL import Image
    if n < 1:
        raise ValueError(f"จำนวนรูปต้อง >= 1 (ได้ {n})")
    cli = sd_cli_for(engine, model)
    seeds = _batch_seeds(seed, n)
    prompt, lora_args = lora_prompt(prompt, lora, lora_strength)
    files = model_files(model)
    w, h = resolve_size(size, ratio, width, height)
    if server and not control:
        imgs = _server_gen(cli, model, files, prompt, lora_args, negative, w, h, steps, guidance,
                           seeds[0], n=n, cancel_event=cancel_event)
        if imgs:
            return list(zip(imgs, seeds))
    with tempfile.TemporaryDirectory() as td:
        model_args = (["--diffusion-model", files["diffusion"]] if "diffusion" in files
                else ["-m", files["m"]])
        cmd = [cli] + model_args + ["-p", prompt, "-o", os.path.join(td, "b_%d.png"),
               "-W", str(w), "-H", str(h),
               "--steps", str(steps), "--cfg-scale", str(guidance),
               "--seed", str(seeds[0]), "-b", str(n)] + lora_args
        if negative:
            cmd += ["-n", negative]
        cmd += control_args(cli, model, control, w, h, td)
        cmd += _extra_args(files) + MODEL_EXTRA_ARGS.get(model, [])
        if model == "flux2-dev":
            # flux2-dev 32B ใส่ VRAM ไม่หมดอยู่แล้ว — offload ไว้ก่อนเสมอ
            cmd += ["--offload-to-cpu"]
        p = _run(cmd, cancel_event)
        outs = [os.path.join(td, f"b_{i}.png") for i in range(n)]
        if p.returncode != 0 or not all(os.path.isfile(o) for o in outs):
            raise RuntimeError(f"sd-cli ล้มเหลว:\n{(p.stderr or p.stdout)[-800:]}")
        return [(Image.open(o).convert("RGB"), seeds[i]) for i, o in enumerate(outs)]


def comfy_txt2img(prompt, steps=8, guidance=2.0, size=512, seed=None, negative="",
                  ckpt=comfy_client.DEFAULT_CKPT, ratio="1:1", width=None, height=None,
                  sampler="euler", scheduler="normal", lora=None, lora_strength=1.0,
                  cancel_event=None, timeout=None):
    """เจนรูปผ่าน ComfyUI Server คืน (PIL Image, seed) — signature เดียวกับ txt2img.

    ckpt = ชื่อฝั่ง GenJab ใน comfy_client.COMFY_CKPTS หรือชื่อไฟล์บน server ตรง ๆ.
    lora = ชื่อไฟล์ในโฟลเดอร์ loras ของ ComfyUI server (ต้องวางไฟล์ให้ server เห็นเอง)."""
    import io
    from PIL import Image
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    w, h = resolve_size(size, ratio, width, height)
    server_lora = None
    if lora:
        server_lora = comfy_client.resolve_comfy_lora(lora)
        if server_lora is None:
            raise comfy_client.ComfyError(
                f"LoRA {lora} ยังใช้กับ ComfyUI ไม่ได้ในเฟสนี้ "
                "(ใช้ได้: ganjad-style-sdxl ทั้ง 3 ตัว หรือระบุชื่อไฟล์ .safetensors บน server ตรง ๆ)")
    comfy_client.ensure_server(cancel_event=cancel_event)
    if server_lora:
        comfy_client.check_lora_on_server(server_lora)
    wf = comfy_client.build_txt2img(prompt, negative=negative, seed=seed, steps=steps,
                                    cfg=guidance, w=w, h=h, ckpt=ckpt, sampler=sampler,
                                    scheduler=scheduler, lora=server_lora,
                                    lora_strength=lora_strength)
    pid = comfy_client.queue_prompt(wf)
    outputs = comfy_client.wait_result(pid, timeout=timeout or comfy_client.WAIT_TIMEOUT,
                                       cancel_event=cancel_event)
    blobs = comfy_client.fetch_images(outputs)
    return Image.open(io.BytesIO(blobs[0])).convert("RGB"), seed


def comfy_img2img(init_path, prompt="", strength=0.6, steps=8, seed=None, size=512,
                  guidance=2.0, negative="", ckpt=comfy_client.DEFAULT_CKPT,
                  width=None, height=None, sampler="euler", scheduler="normal",
                  lora=None, lora_strength=1.0, mask=None, cancel_event=None, timeout=None):
    """แปลงรูปต้นฉบับผ่าน ComfyUI Server คืน (PIL Image, seed) — strength = denoise.

    mask = path รูปมาสก์ (ขาว = เจนใหม่, ดำ = คงเดิม) — ย่อให้เท่ารูปต้นฉบับก่อนอัปโหลด."""
    import io
    from PIL import Image
    try:
        s = float(strength)
    except (TypeError, ValueError):
        raise ValueError(f"strength ต้องเป็นตัวเลข 0..1 (ได้ {strength})")
    if not 0 < s < 1:
        raise ValueError(f"strength ต้องอยู่ระหว่าง 0..1 (ได้ {strength})")
    if not init_path or not os.path.isfile(init_path):
        raise FileNotFoundError(f"ไม่พบรูปต้นฉบับ: {init_path}")
    if mask and not os.path.isfile(mask):
        raise FileNotFoundError(f"ไม่พบรูปมาสก์: {mask}")
    if width is not None or height is not None:
        if width is None or height is None:
            raise ValueError(f"ต้องระบุ width/height คู่กัน (ได้ {width}x{height})")
        w, h = int(width), int(height)
        if w <= 0 or h <= 0:
            raise ValueError(f"width/height ต้อง > 0 (ได้ {w}x{h})")
    else:
        with Image.open(init_path) as im:
            iw, ih = im.size
        w, h = fit_init_size(iw, ih, size)
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    server_lora = None
    if lora:
        server_lora = comfy_client.resolve_comfy_lora(lora)
        if server_lora is None:
            raise comfy_client.ComfyError(
                f"LoRA {lora} ยังใช้กับ ComfyUI ไม่ได้ในเฟสนี้ "
                "(ใช้ได้: ganjad-style-sdxl ทั้ง 3 ตัว หรือระบุชื่อไฟล์ .safetensors บน server ตรง ๆ)")
    comfy_client.ensure_server(cancel_event=cancel_event)
    if server_lora:
        comfy_client.check_lora_on_server(server_lora)
    with tempfile.TemporaryDirectory() as td:
        init_up = os.path.join(td, "init.png")
        with Image.open(init_path) as im:
            im.convert("RGB").resize((w, h), Image.LANCZOS).save(init_up)
        init_name = comfy_client.upload_image(init_up)
        mask_name = None
        if mask:
            mask_up = os.path.join(td, "mask.png")
            with Image.open(mask) as m:
                m.convert("L").resize((w, h), Image.LANCZOS).save(mask_up)
            mask_name = comfy_client.upload_image(mask_up)
        wf = comfy_client.build_img2img(prompt, negative=negative, seed=seed, steps=steps,
                                        cfg=guidance, ckpt=ckpt, sampler=sampler,
                                        scheduler=scheduler, lora=server_lora,
                                        lora_strength=lora_strength, init_image=init_name,
                                        strength=s, mask_image=mask_name)
        pid = comfy_client.queue_prompt(wf)
        outputs = comfy_client.wait_result(pid, timeout=timeout or comfy_client.WAIT_TIMEOUT,
                                           cancel_event=cancel_event)
        blobs = comfy_client.fetch_images(outputs)
    return Image.open(io.BytesIO(blobs[0])).convert("RGB"), seed


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


def supports_ip_adapter(model):
    """คงหน้าเดิม (IP-Adapter SDXL) ใช้ได้กับ SDXL ทุกตัว รวมตัวที่วางเองใน models/sdxl/."""
    return model in IP_ADAPTER_MODELS or model_family(model) == "sdxl"
# ---------- ControlNet (คุมโครงรูปจากรูปอ้างอิง — SDXL) ----------
CONTROLNET_DIR = os.path.join(LOCAL_MODELS, "controlnet")
CONTROLNET_EXTS = (".safetensors", ".gguf")
# canny = เส้นขอบจากรูปถ่าย (sd-cli ทำให้เอง), scribble = ภาพวาดเส้นของเรา,
# depth/openpose = ใส่แผนที่ความลึก/โครงท่าทางที่ทำมาแล้ว
CONTROL_TYPES = ("canny", "scribble", "depth", "openpose")
CONTROLNET_HINT = ("โหลด ControlNet Union SDXL (xinsir/controlnet-union-sdxl-1.0 ไฟล์ "
                   "diffusion_pytorch_model_promax.safetensors ~2.5GB) มาไว้ใน models/controlnet/ "
                   "ข้างโปรแกรม (หรือโฟลเดอร์ controlnet ของ Amuse)")


def supports_controlnet(model):
    """ControlNet ใช้ได้กับ SDXL ทุกตัว (ตัวเดียวกับคงหน้าเดิม)."""
    return supports_ip_adapter(model)


def list_controlnets():
    """{ชื่อไฟล์ไม่มีนามสกุล: path} ของ ControlNet ใน models/controlnet/ + โฟลเดอร์ controlnet ของ Amuse."""
    found = {}
    for d in [CONTROLNET_DIR] + amuse_subdirs("controlnet"):
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for f in names:
            stem, ext = os.path.splitext(f)
            if ext.lower() in CONTROLNET_EXTS and stem not in found:
                found[stem] = os.path.join(d, f)
    return found


def resolve_controlnet(name=None):
    """path ControlNet — ไม่ระบุชื่อใช้ตัวแรก; ไม่มีเลย raise พร้อมบอกที่โหลด."""
    nets = list_controlnets()
    if name:
        if name in nets:
            return nets[name]
        raise FileNotFoundError(f"ไม่พบ ControlNet {name} — มี: {', '.join(nets) or '(ไม่มี)'}")
    if not nets:
        raise FileNotFoundError(f"ยังไม่มีไฟล์ ControlNet — {CONTROLNET_HINT}")
    return next(iter(nets.values()))


def control_args(cli, model, control, w, h, td):
    """argv ของ ControlNet จาก dict control = {image, type, strength, net?} — None คืน [].

    ย่อรูปอ้างอิงให้เท่าขนาดเจน (ทุก engine ใช้ได้), canny ให้ sd-cli ทำ ถ้า engine ไม่มี
    --image-preprocess ใช้ PIL หาขอบแทน."""
    if not control:
        return []
    from PIL import Image, ImageFilter, ImageOps
    if not supports_controlnet(model):
        raise ValueError(f"ControlNet ใช้ได้กับโมเดล SDXL เท่านั้น (ได้ {model})")
    img = control.get("image")
    if not img or not os.path.isfile(img):
        raise FileNotFoundError(f"ไม่พบรูปควบคุม (ControlNet): {img}")
    ctype = control.get("type", "canny")
    if ctype not in CONTROL_TYPES:
        raise ValueError(f"ชนิด ControlNet ไม่รู้จัก: {ctype} (มี: {', '.join(CONTROL_TYPES)})")
    try:
        cs = float(control.get("strength", 0.9))
    except (TypeError, ValueError):
        raise ValueError(f"ความแรง ControlNet ต้องเป็นตัวเลข (ได้ {control.get('strength')})")
    if not 0 < cs <= 2:
        raise ValueError(f"ความแรง ControlNet ต้องอยู่ระหว่าง 0..2 (ได้ {cs})")
    net = resolve_controlnet(control.get("net"))
    out = os.path.join(td, "control.png")
    with Image.open(img) as im:
        ref = ImageOps.fit(im.convert("RGB"), (int(w), int(h)), Image.LANCZOS)
    pre = []
    if ctype == "canny":
        if engine_has(cli, "--image-preprocess"):
            pre = ["--image-preprocess", "target=control,canny=true"]
        else:
            ref = ref.convert("L").filter(ImageFilter.FIND_EDGES).point(
                lambda v: 255 if v > 40 else 0).convert("RGB")
    ref.save(out)
    return (["--control-net", net, "--control-image", out, "--control-type", ctype,
             "--control-strength", f"{cs:g}"] + pre)


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
            mask=None, cancel_event=None, engine=None, on_preview=None, server=False):
    """แปลงรูปต้นฉบับตาม prompt คืน (PIL Image, seed ที่ใช้จริง) — on_preview/server ดู txt2img
    (คงหน้าเดิมใช้ sd-cli เสมอ: server ไม่มี IP-Adapter).

    strength 0..1 (น้อย = คงรูปเดิมมาก) — ขนาดผลลัพธ์ย่อจากรูปต้นฉบับให้ด้านยาว = size.
    mask = path รูปมาสก์ (ขาว = เจนใหม่, ดำ = คงเดิม) ใช้ทำ inpaint เฉพาะจุด."""
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
        if not supports_ip_adapter(model):
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
    if mask and not os.path.isfile(mask):
        raise FileNotFoundError(f"ไม่พบรูปมาสก์: {mask}")
    if face_ref:
        _, cli = face_engine(engine, model)  # Amuse 4.0 ไม่มี --ip-adapter → สลับไปตัวที่มี
    else:
        cli = sd_cli_for(engine, model)
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
    if server and not face_ref:
        with tempfile.TemporaryDirectory() as std:
            mask_fit = None
            if mask:  # ขนาดมาสก์ต้องเท่ารูปต้นฉบับ (เหมือนทาง sd-cli)
                mask_fit = os.path.join(std, "mask.png")
                with Image.open(init_path) as im:
                    init_size = im.size
                with Image.open(mask) as m:
                    m.convert("L").resize(init_size, Image.LANCZOS).save(mask_fit)
            sp, sl = lora_prompt(prompt, lora, lora_strength)
            imgs = _server_gen(cli, model, files, sp, sl, negative, w, h, steps, guidance, seed,
                               init_path=os.path.abspath(init_path), strength=s,
                               mask_path=mask_fit, cancel_event=cancel_event)
        if imgs:
            return imgs[0], seed
    with tempfile.TemporaryDirectory() as td:
        prompt, lora_args = lora_prompt(prompt, lora, lora_strength)
        out = os.path.join(td, "gen.png")
        model_args = (["--diffusion-model", files["diffusion"]] if "diffusion" in files
                else ["-m", files["m"]])
        cmd = [cli] + model_args + ["-i", os.path.abspath(init_path),
               "--strength", str(s), "-p", prompt, "-o", out,
               "-W", str(w), "-H", str(h),
               "--steps", str(steps), "--cfg-scale", str(guidance),
               "--seed", str(seed)] + lora_args + face_args
        if mask:
            # sd-cli ต้องการมาสก์ขนาดเท่ารูปต้นฉบับเป๊ะ — ย่อ/ขยายให้ตรงก่อนส่ง
            mask_out = os.path.join(td, "mask.png")
            with Image.open(init_path) as im:
                init_size = im.size
            with Image.open(mask) as m:
                m.convert("L").resize(init_size, Image.LANCZOS).save(mask_out)
            cmd += ["--mask", mask_out]
        if negative:
            cmd += ["-n", negative]
        cmd += _extra_args(files) + MODEL_EXTRA_ARGS.get(model, [])
        if model == "flux2-dev":
            # flux2-dev 32B ใส่ VRAM ไม่หมดอยู่แล้ว — offload ไว้ก่อนเสมอ
            cmd += ["--offload-to-cpu"]
        pv_args, watch = preview_args(cli, td, on_preview)
        p = _run(cmd + pv_args, cancel_event, watch)
        if p.returncode != 0 or not os.path.isfile(out):
            raise RuntimeError(f"sd-cli ล้มเหลว:\n{(p.stderr or p.stdout)[-800:]}")
        return Image.open(out).convert("RGB"), seed


UPSCALE_DIR = os.path.join(LOCAL_MODELS, "upscale")
UPSCALE_EXTS = (".pth", ".safetensors", ".gguf")
UPSCALE_HINT = ("โหลด RealESRGAN_x4plus_anime_6B.pth จาก "
                "https://github.com/xinntao/Real-ESRGAN/releases (v0.2.2.4) "
                "มาไว้ในโฟลเดอร์ models/upscale/ — ไฟล์ .onnx ของ Amuse ใช้กับ sd-cli ไม่ได้")


def list_upscalers():
    """คืน {ชื่อไฟล์ไม่มีนามสกุล: path} ของโมเดล ESRGAN ใน models/upscale/ + env TEXT2IMAGE_UPSCALER."""
    found = {}
    env = os.environ.get("TEXT2IMAGE_UPSCALER", "")
    if env and os.path.isfile(env):
        found[os.path.splitext(os.path.basename(env))[0]] = env
    try:
        names = sorted(os.listdir(UPSCALE_DIR))
    except OSError:
        names = []
    for f in names:
        if f.lower().endswith(UPSCALE_EXTS):
            found.setdefault(os.path.splitext(f)[0], os.path.join(UPSCALE_DIR, f))
    return found


def upscale(src_path, upscaler=None, repeats=1, cancel_event=None, engine=None):
    """ขยายรูปด้วย ESRGAN (sd-cli -M upscale) คืน PIL Image — upscaler = ชื่อ/path, ว่าง = ตัวแรกที่เจอ."""
    from PIL import Image
    if not src_path or not os.path.isfile(src_path):
        raise FileNotFoundError(f"ไม่พบรูปที่จะขยาย: {src_path}")
    repeats = int(repeats)
    if not 1 <= repeats <= 4:
        raise ValueError(f"repeats ต้องอยู่ 1..4 (ได้ {repeats})")
    if upscaler and os.path.isfile(upscaler):
        model = upscaler
    else:
        found = list_upscalers()
        if not found:
            raise FileNotFoundError("ไม่พบโมเดลขยายรูป — " + UPSCALE_HINT)
        if upscaler and upscaler not in found:
            raise ValueError(f"ไม่รู้จักโมเดลขยายรูป: {upscaler} (มี: {', '.join(found)})")
        model = found[upscaler] if upscaler else next(iter(found.values()))
    cli = sd_cli_for(engine)
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "up.png")
        cmd = [cli, "-M", "upscale", "-i", os.path.abspath(src_path),
               "--upscale-model", model, "--upscale-repeats", str(repeats), "-o", out]
        p = _run(cmd, cancel_event)
        if p.returncode != 0 or not os.path.isfile(out):
            raise RuntimeError(f"sd-cli ล้มเหลว:\n{(p.stderr or p.stdout)[-800:]}")
        img = Image.open(out).convert("RGB")
        # โหลดโมเดลไม่ขึ้น sd-cli ยังคืน 0 แล้วเซฟรูปเดิมขนาดเดิม — ถือว่าล้มเหลว
        with Image.open(src_path) as src:
            if img.size == src.size:
                raise RuntimeError(f"ขยายรูปไม่สำเร็จ (โมเดล {os.path.basename(model)} ใช้ไม่ได้?):\n"
                                   f"{(p.stderr or p.stdout)[-800:]}")
        return img


VIDEO_MODELS = ("minimax-h3", "wan22-5b")

# ค่าเริ่มตาม DefaultOptions ในเทมเพลตของ Amuse (Templates.json)
VIDEO_DEFAULTS = {
    "minimax-h3": {"steps": 20, "guidance": 1.0, "frames": 56, "fps": 24,
                   "width": 864, "height": 480},
    "wan22-5b": {"steps": 30, "guidance": 5.0, "frames": 121, "fps": 24,
                 "width": 1280, "height": 704},
}

VIDEO_EXTS = (".webm", ".avi")
COMFY_VIDEO_EXTS = (".mp4",)


def txt2vid(prompt, model, width=None, height=None, frames=None, fps=None,
            steps=None, guidance=None, seed=None, negative="", output="out/vid.webm",
            cancel_event=None, engine=None):
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
    cli = sd_cli_for(engine, model)
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    files = model_files(model)
    out = os.path.abspath(output)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    model_args = (["--diffusion-model", files["diffusion"]] if "diffusion" in files
                  else ["-m", files["m"]])
    cmd = [cli] + model_args + ["-M", "vid_gen", "-p", prompt, "-o", out,
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


I2V_MODELS = ("wan22-5b", "wan22-14b-comfy")

I2V_DEFAULTS = {
    "wan22-5b": {"steps": 12, "guidance": 6.0, "frames": 17, "fps": 16},
    "wan22-14b-comfy": {"steps": 20, "guidance": 6.0, "frames": 49,
                        "fps": 16, "size": 832},
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
            sampler="euler", flow_shift=3.0, output="out/vid.webm", cancel_event=None, engine=None):
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
    cli = sd_cli_for(engine, model)
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    files = model_files(model)
    if w is None:
        with Image.open(init_path) as im:
            iw, ih = im.size
        w, h = fit_video_size(iw, ih, size)
    out = os.path.abspath(output)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    cmd = [cli, "--diffusion-model", files["diffusion"], "-M", "vid_gen",
           "-i", os.path.abspath(init_path), "-p", prompt, "-o", out,
           "-W", str(w), "-H", str(h),
           "--video-frames", str(frames), "--fps", str(fps),
           "--steps", str(steps), "--cfg-scale", str(guidance),
           "--sampling-method", str(sampler), "--flow-shift", str(flow_shift),
           "--seed", str(seed)]
    if negative:
        cmd += ["-n", negative]
    cmd += _extra_args(files) + MODEL_EXTRA_ARGS.get(model, [])
    p = _run(cmd, cancel_event)
    if p.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError(f"sd-cli ล้มเหลว:\n{(p.stderr or p.stdout)[-800:]}")
    return out, seed


def comfy_i2v(init_path, prompt, model="wan22-14b-comfy", size=832,
              width=None, height=None, frames=None, fps=None, steps=None,
              guidance=None, seed=None, negative="", sampler="uni_pc",
              scheduler="simple", shift=8.0, output="out/vid.mp4",
              cancel_event=None, timeout=3600):
    """ทำภาพนิ่งให้ขยับผ่าน ComfyUI (Wan 2.2 14B dual-expert) คืน (path วิดีโอ, seed).

    ค่าไหนไม่ส่งมาใช้ I2V_DEFAULTS ของโมเดลนั้น — ขนาดรูปย่อด้านยาว=size (ปัดลง 16)."""
    from PIL import Image
    if model != "wan22-14b-comfy":
        raise ValueError(f"โมเดล ComfyUI I2V ไม่รู้จัก: {model} (มี: wan22-14b-comfy)")
    if not init_path or not os.path.isfile(init_path):
        raise FileNotFoundError(f"ไม่พบรูปต้นฉบับ: {init_path}")
    d = I2V_DEFAULTS[model]
    length = d["frames"] if frames is None else int(frames)
    fps = d["fps"] if fps is None else int(fps)
    steps = d["steps"] if steps is None else int(steps)
    guidance = d["guidance"] if guidance is None else float(guidance)
    size = d.get("size", 832) if size is None else int(size)
    if length < 1:
        raise ValueError(f"frames ต้อง >= 1 (ได้ {length})")
    if fps < 1:
        raise ValueError(f"fps ต้อง >= 1 (ได้ {fps})")
    ext = os.path.splitext(output)[1].lower()
    if ext not in COMFY_VIDEO_EXTS:
        raise ValueError(f"วิดีโอ ComfyUI ต้องลงท้าย {COMFY_VIDEO_EXTS} (ได้ {output})")
    if width is not None or height is not None:
        if width is None or height is None:
            raise ValueError(f"ต้องระบุ width/height คู่กัน (ได้ {width}x{height})")
        w, h = int(width), int(height)
        if w <= 0 or h <= 0:
            raise ValueError(f"width/height ต้อง > 0 (ได้ {w}x{h})")
    else:
        w = h = None
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    comfy_client.ensure_server(cancel_event=cancel_event)
    comfy_client.check_wan22_i2v_models()
    with tempfile.TemporaryDirectory() as td:
        if w is None:
            with Image.open(init_path) as im:
                iw, ih = im.size
            w, h = fit_video_size(iw, ih, size)
        init_up = os.path.join(td, "init.png")
        with Image.open(init_path) as im:
            im.convert("RGB").resize((w, h), Image.LANCZOS).save(init_up)
        init_name = comfy_client.upload_image(init_up)
        wf = comfy_client.build_wan22_i2v(
            prompt, negative=negative, seed=seed, steps=steps, cfg=guidance,
            sampler=sampler, scheduler=scheduler, shift=shift,
            width=w, height=h, length=length, fps=fps, init_image=init_name)
        pid = comfy_client.queue_prompt(wf)
        outputs = comfy_client.wait_result(pid, timeout=timeout,
                                           cancel_event=cancel_event)
        blobs = comfy_client.fetch_videos(outputs)
    out = os.path.abspath(output)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "wb") as f:
        f.write(blobs[0])
    return out, seed


FFMPEG_ENV = "GENJAB_FFMPEG"


def resolve_ffmpeg():
    """หา ffmpeg.exe สำหรับต่อคลิปยาว — env GENJAB_FFMPEG ก่อน, ข้างตัวแอป, สุดท้ายใน PATH."""
    import shutil
    env = os.environ.get(FFMPEG_ENV, "")
    if env and os.path.isfile(env):
        return env
    bundled = os.path.join(app_dir(), "ffmpeg.exe")
    if os.path.isfile(bundled):
        return bundled
    found = shutil.which("ffmpeg")
    if found:
        return found
    # Amuse ติด ffmpeg 7.1 มาด้วย (มี libopus/aac/webm/mp4 ครบ) — ใช้ต่อคลิปและใส่เพลงได้
    amuse = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Amuse", "ffmpeg.exe")
    if os.path.isfile(amuse):
        return amuse
    raise FileNotFoundError(
        "ไม่พบ ffmpeg.exe (ต้องใช้ต่อคลิปยาว) — วาง ffmpeg.exe ไว้ข้างโปรแกรม "
        f"หรือตั้ง path ผ่าน env {FFMPEG_ENV}")


def extend_segments_needed(target_secs, frames, fps):
    """จำนวนท่อนที่ต้องเจนเพื่อให้คลิปยาวครบ target_secs (วินาที) — อย่างน้อย 1 ท่อน."""
    try:
        secs = float(target_secs)
        frames, fps = int(frames), int(fps)
    except (TypeError, ValueError):
        raise ValueError(
            f"ความยาว/เฟรม/FPS ต้องเป็นตัวเลข (ได้ {target_secs}/{frames}/{fps})")
    if secs <= 0:
        raise ValueError(f"ความยาวเป้าหมายต้อง > 0 (ได้ {target_secs})")
    if frames < 1 or fps < 1:
        raise ValueError(f"frames/fps ต้อง >= 1 (ได้ {frames}/{fps})")
    return max(1, math.ceil(secs * fps / frames))


def extract_frame(video_path, out_png, which="last"):
    """ดึงเฟรมแรก/สุดท้ายของวิดีโอเป็น PNG (ใช้ส่งต่อท่อน auto-extend) — คืน path PNG."""
    if not video_path or not os.path.isfile(video_path):
        raise FileNotFoundError(f"ไม่พบวิดีโอ: {video_path}")
    if which not in ("last", "first"):
        raise ValueError(f"which ต้องเป็น last/first (ได้ {which})")
    ff = resolve_ffmpeg()
    out = os.path.abspath(out_png)
    od = os.path.dirname(out)
    if od:
        os.makedirs(od, exist_ok=True)
    if which == "last":
        cmd = [ff, "-y", "-v", "error", "-sseof", "-0.05", "-i", video_path,
               "-frames:v", "1", out]
    else:
        cmd = [ff, "-y", "-v", "error", "-i", video_path, "-frames:v", "1", out]
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                       creationflags=_popen_flags())
    if p.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError(f"ดึงเฟรมล้มเหลว:\n{(p.stderr or p.stdout)[-800:]}")
    return out


def concat_videos(parts, output):
    """ต่อคลิปหลายท่อนเป็นไฟล์เดียวแบบไม่เข้ารหัสใหม่ (-c copy) — คืน path ผลลัพธ์."""
    parts = list(parts or [])
    if not parts:
        raise ValueError("ไม่มีท่อนวิดีโอให้ต่อ")
    for p in parts:
        if not os.path.isfile(p):
            raise FileNotFoundError(f"ไม่พบท่อนวิดีโอ: {p}")
    ext = os.path.splitext(output)[1].lower()
    if ext not in VIDEO_EXTS:
        raise ValueError(f"ไฟล์วิดีโอต้องลงท้าย {VIDEO_EXTS} (ได้ {output})")
    ff = resolve_ffmpeg()
    out = os.path.abspath(output)
    od = os.path.dirname(out)
    if od:
        os.makedirs(od, exist_ok=True)
    lst = None
    try:
        fd, lst = tempfile.mkstemp(dir=od or ".", prefix="parts", suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for p in parts:
                f.write(f"file '{os.path.abspath(p)}'\n")
        cmd = [ff, "-y", "-v", "error", "-f", "concat", "-safe", "0",
               "-i", lst, "-c", "copy", out]
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                           creationflags=_popen_flags())
        if p.returncode != 0 or not os.path.isfile(out):
            raise RuntimeError(f"ต่อคลิปล้มเหลว:\n{(p.stderr or p.stdout)[-800:]}")
    finally:
        try:
            if lst and os.path.isfile(lst):
                os.remove(lst)
        except OSError:
            pass
    return out


def img2vid_extend(init_path, prompt, target_secs=None, segments=None, model="wan22-5b",
                   size=512, width=None, height=None, frames=None, fps=None, steps=None,
                   guidance=None, seed=None, negative="", sampler="euler", flow_shift=3.0,
                   output="out/vid.webm", on_segment=None, cancel_event=None, engine=None):
    """ทำภาพขยับยาวตามเป้า: เจนท่อนสั้นหลายท่อน (เฟรมท้ายท่อนก่อน → ต้นท่อนถัดไป)
    แล้วต่อเป็นไฟล์เดียว — คืน (path คลิปยาว, [seed ทุกท่อน]).

    ระบุ segments ตรง ๆ หรือ target_secs (วินาที) อย่างใดอย่างหนึ่ง; ท่อนเดียว
    ไม่ต้องใช้ ffmpeg (เรียก img2vid ตรง ๆ)."""
    if model not in I2V_MODELS:
        raise ValueError(f"โมเดลนี้ทำภาพขยับไม่ได้: {model} (ได้: {', '.join(I2V_MODELS)})")
    if not init_path or not os.path.isfile(init_path):
        raise FileNotFoundError(f"ไม่พบรูปต้นฉบับ: {init_path}")
    d = I2V_DEFAULTS[model]
    frames = d["frames"] if frames is None else int(frames)
    fps = d["fps"] if fps is None else int(fps)
    if frames < 1:
        raise ValueError(f"frames ต้อง >= 1 (ได้ {frames})")
    if fps < 1:
        raise ValueError(f"fps ต้อง >= 1 (ได้ {fps})")
    if segments is None:
        if target_secs is None:
            raise ValueError("ต้องระบุ target_secs (วินาที) หรือ segments (จำนวนท่อน)")
        n = extend_segments_needed(target_secs, frames, fps)
    else:
        try:
            n = int(segments)
        except (TypeError, ValueError):
            raise ValueError(f"segments ต้องเป็นจำนวนเต็ม >= 1 (ได้ {segments})")
        if n < 1:
            raise ValueError(f"segments ต้อง >= 1 (ได้ {segments})")
    worker = comfy_i2v if model == "wan22-14b-comfy" else img2vid
    allowed = COMFY_VIDEO_EXTS if worker is comfy_i2v else VIDEO_EXTS
    ext = os.path.splitext(output)[1].lower()
    if worker is comfy_i2v and ext == ".webm":
        output = os.path.splitext(output)[0] + ".mp4"
        ext = ".mp4"
    if ext not in allowed:
        raise ValueError(f"ไฟล์วิดีโอต้องลงท้าย {allowed} (ได้ {output})")
    if width is not None or height is not None:
        if width is None or height is None:
            raise ValueError(f"ต้องระบุ width/height คู่กัน (ได้ {width}x{height})")
    if worker is img2vid:
        sd_cli_for(engine, model)  # ตรวจ engine ก่อน (ล้มเร็ว ไม่ต้องรอเจนท่อนแรก)
    if n == 1:
        if worker is comfy_i2v:
            out, used = worker(init_path, prompt, model=model, size=size,
                               width=width, height=height, frames=frames,
                               fps=fps, steps=steps, guidance=guidance,
                               seed=seed, negative=negative, sampler=sampler,
                               output=output, cancel_event=cancel_event)
        else:
            out, used = worker(init_path, prompt, model=model, size=size, width=width,
                               height=height, frames=frames, fps=fps, steps=steps,
                               guidance=guidance, seed=seed, negative=negative,
                               sampler=sampler, flow_shift=flow_shift, output=output,
                               cancel_event=cancel_event,
                               engine=engine)
        if on_segment is not None:
            on_segment(1, 1)
        return out, [used]
    resolve_ffmpeg()  # ไม่มีให้ล้มเหลวก่อนเจนยาว
    seeds = _batch_seeds(seed, n)
    segs = []
    with tempfile.TemporaryDirectory() as td:
        prev = os.path.abspath(init_path)
        for i in range(n):
            seg = os.path.join(td, f"seg{i:03d}.webm")
            if worker is comfy_i2v:
                seg = os.path.splitext(seg)[0] + ".mp4"
                got, _ = worker(prev, prompt, model=model, size=size,
                                width=width, height=height, frames=frames,
                                fps=fps, steps=steps, guidance=guidance,
                                seed=seeds[i], negative=negative,
                                sampler=sampler, output=seg,
                                cancel_event=cancel_event)
            else:
                got, _ = worker(prev, prompt, model=model, size=size, width=width,
                                height=height, frames=frames, fps=fps, steps=steps,
                                guidance=guidance, seed=seeds[i], negative=negative,
                                sampler=sampler, flow_shift=flow_shift, output=seg,
                                cancel_event=cancel_event,
                                engine=engine)
            segs.append(got)
            if on_segment is not None:
                on_segment(i + 1, n)
            prev = extract_frame(got, os.path.join(td, f"last{i:03d}.png"), which="last")
        if worker is comfy_i2v:
            final = _concat_mp4_copy(segs, output)
        else:
            final = concat_videos(segs, output)
    return final, seeds


def _concat_mp4_copy(parts, output):
    """ต่อคลิป mp4 (h264 ตัวเดียวกันจาก ComfyUI) แบบไม่เข้ารหัสใหม่ — คืน path ผลลัพธ์."""
    parts = list(parts or [])
    if not parts:
        raise ValueError("ไม่มีท่อนวิดีโอให้ต่อ")
    for p in parts:
        if not os.path.isfile(p):
            raise FileNotFoundError(f"ไม่พบท่อนวิดีโอ: {p}")
    ext = os.path.splitext(output)[1].lower()
    if ext not in COMFY_VIDEO_EXTS:
        raise ValueError(f"ไฟล์วิดีโอ ComfyUI ต้องลงท้าย {COMFY_VIDEO_EXTS} (ได้ {output})")
    ff = resolve_ffmpeg()
    out = os.path.abspath(output)
    od = os.path.dirname(out)
    if od:
        os.makedirs(od, exist_ok=True)
    lst = None
    try:
        fd, lst = tempfile.mkstemp(dir=od or ".", prefix="parts", suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for p in parts:
                f.write(f"file '{os.path.abspath(p)}'\n")
        cmd = [ff, "-y", "-v", "error", "-f", "concat", "-safe", "0",
               "-i", lst, "-c", "copy", out]
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                           creationflags=_popen_flags())
        if p.returncode != 0 or not os.path.isfile(out):
            raise RuntimeError(f"ต่อคลิปล้มเหลว:\n{(p.stderr or p.stdout)[-800:]}")
    finally:
        try:
            if lst and os.path.isfile(lst):
                os.remove(lst)
        except OSError:
            pass
    return out


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
    ap.add_argument("--mask", default=None,
                    help="รูปมาสก์ inpaint ขาว = เจนใหม่ ดำ = คงเดิม (เฉพาะ --init-img)")
    ap.add_argument("--model", default="sd-turbo",
                    choices=["sd-turbo", "sdxl-turbo", "sdxl-base", "anima-turbo", "anima-base", "anima-aesthetic",
                    "qwen21", "qwen21-turbo", "iris-3b", "iris-turbo", "flux2-dev", "fibo2-turbo", "minimax-h3", "minimax-h3-image", "wan22-5b", "zimage-turbo"]
                    + [CUSTOM_SDXL_PREFIX + s for s in list_sdxl_checkpoints()])
    ap.add_argument("--count", type=int, default=1, help="จำนวนรูป/คลิปต่อครั้ง (รูปโหลดโมเดลครั้งเดียว)")
    ap.add_argument("--backend", default="sd-cli", choices=["sd-cli", "comfy"],
                    help="เอนจินเจนรูป (comfy = ComfyUI server ผ่าน API)")
    ap.add_argument("--comfy-ckpt", default=comfy_client.DEFAULT_CKPT,
                    choices=sorted(comfy_client.COMFY_CKPTS),
                    help="โมเดลฝั่ง ComfyUI (เฉพาะ --backend comfy)")
    ap.add_argument("--comfy-server", default=None,
                    help="ที่อยู่ ComfyUI server (เช่น http://127.0.0.1:8188)")
    ap.add_argument("--frames", type=int, default=None, help="จำนวนเฟรมวิดีโอ (ค่าเริ่มตามโมเดล)")
    ap.add_argument("--fps", type=int, default=None, help="เฟรมต่อวินาทีของวิดีโอ (ค่าเริ่มตามโมเดล)")
    ap.add_argument("--target-secs", type=float, default=None,
                    help="ความยาวคลิปเป้าหมาย (วินาที) — ต่อหลายท่อนอัตโนมัติ (เฉพาะ --init-img + โมเดลวิดีโอ)")
    ap.add_argument("--segments", type=int, default=None,
                    help="จำนวนท่อนวิดีโอ (เหนือกว่า --target-secs)")
    ap.add_argument("--engine", default=None, choices=list(ENGINES),
                    help=f"engine sd-cli: amuse = ของ Amuse, alt = บิลด์สำรอง ({alt_engine_tag()}) "
                    f"(ค่าเริ่ม {DEFAULT_ENGINE})")
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
                if args.target_secs is not None or args.segments is not None:
                    out, seeds = img2vid_extend(
                        args.init_img, prompt, model=args.model,
                        size=args.size, width=args.width, height=args.height,
                        frames=args.frames, fps=args.fps,
                        steps=args.steps if args.steps != 4 else None,
                        guidance=args.cfg if args.cfg != 1.0 else None,
                        target_secs=args.target_secs, segments=args.segments,
                        seed=seed, negative=negative, output=path, engine=args.engine)
                    print("saved:", out, "seeds:", seeds)
                else:
                    out, seed = img2vid(args.init_img, prompt, model=args.model,
                                        size=args.size, width=args.width, height=args.height,
                                        frames=args.frames, fps=args.fps,
                                        steps=args.steps if args.steps != 4 else None,
                                        guidance=args.cfg if args.cfg != 1.0 else None,
                                        seed=seed, negative=negative, output=path,
                                        engine=args.engine)
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
                                face_ref=face_ref, face_strength=args.face_strength,
                                mask=args.mask, engine=args.engine)
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
                                negative=args.negative, output=path, engine=args.engine)
            print("saved:", out, "seed:", seed)
        return
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    if args.backend == "comfy":
        if args.comfy_server:
            os.environ[comfy_client.SERVER_ENV] = args.comfy_server
        if args.model in VIDEO_MODELS:
            raise ValueError("backend comfy เฟสนี้ยังไม่รองรับโมเดลวิดีโอ")
        if args.keep_face or args.face_ref:
            raise ValueError("backend comfy เฟสนี้ยังไม่รองรับคงหน้าเดิม (IP-Adapter)")
        if args.init_img:
            prompt, negative = apply_style(args.prompt, args.negative, args.style)
            seeds = _batch_seeds(args.seed, args.count)
            base, ext = os.path.splitext(args.output)
            if not ext:
                args.output += ".png"
                base, ext = os.path.splitext(args.output)
            for i, seed in enumerate(seeds):
                img, used = comfy_img2img(
                    args.init_img, prompt, strength=args.strength, steps=args.steps,
                    seed=seed, size=args.size, guidance=args.cfg, negative=negative,
                    ckpt=args.comfy_ckpt, width=args.width, height=args.height,
                    lora=args.lora, lora_strength=args.lora_strength, mask=args.mask)
                path = args.output if args.count == 1 else f"{base}_{i}{ext}"
                img.save(path)
                print("saved:", path, "seed:", used)
            return
        seeds = _batch_seeds(args.seed, args.count)
        base, ext = os.path.splitext(args.output)
        if not ext:
            args.output += ".png"
            base, ext = os.path.splitext(args.output)
        for i, seed in enumerate(seeds):
            img, used = comfy_txt2img(
                args.prompt, steps=args.steps, seed=seed, size=args.size,
                guidance=args.cfg, negative=args.negative, ckpt=args.comfy_ckpt,
                ratio=args.ratio, width=args.width, height=args.height,
                lora=args.lora, lora_strength=args.lora_strength)
            path = args.output if args.count == 1 else f"{base}_{i}{ext}"
            img.save(path)
            print("saved:", path, "seed:", used)
        return
    if args.count > 1:
        results = txt2img_batch(args.prompt, n=args.count, steps=args.steps, seed=args.seed,
                                size=args.size, guidance=args.cfg, negative=args.negative,
                                model=args.model, ratio=args.ratio, lora=args.lora,
                                lora_strength=args.lora_strength,
                                width=args.width, height=args.height, engine=args.engine)
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
                        width=args.width, height=args.height, engine=args.engine)
    img.save(args.output)
    print("saved:", args.output, "seed:", seed)


if __name__ == "__main__":
    main()
