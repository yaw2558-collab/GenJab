"""ส่วนที่ไม่ใช่หน้าต่างของ GenJab — ค่าคงที่ เมนูโมเดล การจำค่า ชื่อไฟล์ แกลเลอรี.

แยกจาก app.py ให้เทส/แก้ได้โดยไม่ต้องเปิด GUI — app.py import ชื่อพวกนี้กลับไปใช้ต่อ."""
import json
import os
import shutil

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from generate import (CUSTOM_SDXL_PREFIX, DEFAULT_ENGINE, ENGINES, NO_STYLE, RATIOS,
                      STYLE_PRESETS, alt_engine_tag, list_sdxl_checkpoints,
                      main_engine_label, rocm_engine_tag)

NAS_OUT_DIR = r"\\192.168.1.51\personal_folder\genjab"
LOCAL_OUT_DIR = "out"
OUT_DIR = NAS_OUT_DIR
SETTINGS_FILE = "settings.json"
FLOW_URL = "https://flow.google.com"
FLOW_EXPORT_SUBDIR = "flow"
KINOLOCAL_URL = "https://kinolocal-studio-559158679915.asia-east1.run.app"
KINOLOCAL_EXPORT_SUBDIR = "kinolocal"
ACCENT = "#D97A2B"
ACCENT_HOVER = "#E8933F"
TITLE_FONT = ("Segoe UI", 26, "bold")
HEAD_FONT = ("Segoe UI", 12, "bold")
BODY_FONT = ("Segoe UI", 12)
MODEL_IDS = {"SD-Turbo (เร็ว ~4 วิ)": "sd-turbo", "SDXL-Turbo (512px เร็ว)": "sdxl-turbo",
             "SDXL Base (1024px ละเอียด)": "sdxl-base",
             "Anima Turbo (สวย ~45 วิ)": "anima-turbo",
             "Anima Base (คมชัด)": "anima-base", "Anima Aesthetic (เน้นสวย)": "anima-aesthetic",
             "Qwen 2.1 (1024px ช้า ~9 นาที)": "qwen21",
             "Qwen 2.1 Turbo (1024px เร็ว)": "qwen21-turbo",
             "Iris 3B (ภาพใหญ่ ช้า)": "iris-3b",
             "Iris 3B Turbo (4 steps เร็ว)": "iris-turbo",
             "FLUX.2 Dev 32B (1024px ช้าหนัก)": "flux2-dev",
             "Fibo 2.0 Turbo (1024px เร็ว)": "fibo2-turbo",
             "MOSS Image SFT (1024px ~25 steps)": "moss-sft",
             "Wan2.2 5B (วิดีโอ)": "wan22-5b",
             "Wan2.2 14B (ComfyUI ภาพขยับคุณภาพ)": "wan22-14b-comfy",
             "MiniMax-H3 (วิดีโอ ช้ามาก)": "minimax-h3",
             "MiniMax-H3 Image (1024px)": "minimax-h3-image",
             "Z-Image Turbo (1024px เร็ว)": "zimage-turbo",
             "Juggernaut XL (ComfyUI)": "comfy-juggernaut-xl",
             "Illustrious XL v1 (ComfyUI)": "comfy-illustrious-xl-v1",
             "NoobAI XL (ComfyUI)": "comfy-noobai-xl",
             "SD3.5 Large (ComfyUI)": "comfy-sd35-large",
             "SD 1.5 (ComfyUI)": "comfy-sd15"}
MODEL_SIZES = {"sd-turbo": ["256", "512", "768", "1024"],
               "anima-turbo": ["256", "512", "768", "1024", "1344"],
               "sdxl-turbo": ["512", "768", "1024"],
               "sdxl-base": ["512", "768", "1024"],
               "anima-base": ["256", "512", "768", "1024"],
               "anima-aesthetic": ["256", "512", "768", "1024"],
               "qwen21": ["512", "768", "1024"],
               "qwen21-turbo": ["512", "768", "1024"],
               "iris-3b": ["512", "768", "1024", "1344"],
               "iris-turbo": ["512", "768", "1024", "1344"],
               "flux2-dev": ["512", "768", "1024"],
               "fibo2-turbo": ["512", "768", "1024"],
               "moss-sft": ["512", "768", "1024"],
               "wan22-5b": ["256", "480", "704", "1280"],
               "wan22-14b-comfy": ["480", "704", "832"],
               "minimax-h3": ["256", "480", "864"],
               "minimax-h3-image": ["512", "768", "1024"],
               "zimage-turbo": ["512", "768", "1024"],
               "comfy-juggernaut-xl": ["256", "512", "768", "1024"],
               "comfy-illustrious-xl-v1": ["256", "512", "768", "1024"],
               "comfy-noobai-xl": ["256", "512", "768", "1024"],
               "comfy-sd35-large": ["512", "768", "1024"],
               "comfy-sd15": ["256", "512", "768", "1024"]}


# ค่าที่ตั้งให้อัตโนมัติตอนเปลี่ยนโมเดล — โมเดลที่ไม่อยู่ในนี้ใช้ FALLBACK (ไม่แตะ CFG)
MODEL_DEFAULTS = {
    "anima-base": {"steps": 20, "size": "1024", "cfg": 6.0},
    "anima-aesthetic": {"steps": 20, "size": "1024", "cfg": 6.0},
    "anima-turbo": {"steps": 8, "size": "1024", "cfg": 1.0},
    # SDXL-Turbo เทรนที่ 512 — 1024 ได้คนซ้ำ/ตัวเพี้ยน
    "sdxl-turbo": {"steps": 4, "size": "512", "cfg": 1.0},
    "sdxl-base": {"steps": 25, "size": "1024", "cfg": 6.0},
    "qwen21": {"steps": 30, "size": "1024", "cfg": 4.0},
    "qwen21-turbo": {"steps": 8, "size": "1024", "cfg": 4.0},
    "iris-3b": {"steps": 30, "size": "1024", "cfg": 4.0},
    "iris-turbo": {"steps": 4, "size": "1024", "cfg": 1.0},
    "flux2-dev": {"steps": 20, "size": "1024", "cfg": 1.0},
    "fibo2-turbo": {"steps": 4, "size": "1024", "cfg": 1.0},
    "moss-sft": {"steps": 25, "size": "1024", "cfg": 3.0},
    "zimage-turbo": {"steps": 8, "size": "1024", "cfg": 1.0},
    "comfy-juggernaut-xl": {"steps": 8, "size": "512", "cfg": 2.0},
    "comfy-illustrious-xl-v1": {"steps": 8, "size": "512", "cfg": 2.0},
    "comfy-noobai-xl": {"steps": 24, "size": "512", "cfg": 4.5},
    "comfy-sd35-large": {"steps": 20, "size": "1024", "cfg": 4.5},
    "comfy-sd15": {"steps": 20, "size": "512", "cfg": 7.0},
    "wan22-5b": {"steps": 30, "size": "704", "cfg": 5.0,
                 "ratio": "16:9", "frames": "17", "fps": "24"},
    "wan22-14b-comfy": {"steps": 20, "size": "832", "cfg": 6.0,
                        "ratio": "16:9", "frames": "49", "fps": "16"},
    "minimax-h3": {"steps": 20, "size": "480", "cfg": 1.0,
                   "ratio": "16:9", "frames": "17", "fps": "24"},
    "minimax-h3-image": {"steps": 6, "size": "1024", "cfg": 1.0},
}
MODEL_DEFAULTS_FALLBACK = {"steps": 4, "size": "512"}


def custom_sdxl_defaults(stem):
    """ค่าเริ่มของ SDXL ที่วางเอง เดาจากชื่อไฟล์ — Lightning/Turbo/Hyper เจนไม่กี่ step CFG ต่ำ."""
    low = stem.lower()
    if "lightning" in low or "hyper" in low:
        return {"steps": 5, "size": "1024", "cfg": 1.5}
    if "turbo" in low:
        return {"steps": 6, "size": "1024", "cfg": 2.0}
    return {"steps": 25, "size": "1024", "cfg": 5.0}


def _add_custom_sdxl():
    """ใส่ SDXL ที่วางไว้ใน models/sdxl/ ลงเมนู (id = sdxl:ชื่อไฟล์) — เรียกครั้งเดียวตอน import."""
    for stem in list_sdxl_checkpoints():
        mid = CUSTOM_SDXL_PREFIX + stem
        MODEL_IDS[f"{stem} (SDXL)"] = mid
        MODEL_SIZES[mid] = ["512", "768", "1024"]
        MODEL_DEFAULTS[mid] = custom_sdxl_defaults(stem)


_add_custom_sdxl()

NO_UPSCALER = "(ยังไม่มีโมเดลขยายรูป)"
MODE_TXT = "เจนรูป"
MODE_CONVERT = "แปลงรูป"
EXTEND_DURATIONS = ("1", "3", "5", "10", "30", "60", "120")

# ป้าย engine ในเมนู GUI — id คือค่าที่ส่งให้ generate (amuse/alt/rocm)
ENGINE_LABELS = {"amuse": main_engine_label(), "alt": f"Alt ({alt_engine_tag()})",
                 "rocm": f"ROCm ({rocm_engine_tag()})"}


def engine_label(eid):
    """ป้ายเมนูของ engine id — id ผิดคืนป้ายของ DEFAULT_ENGINE."""
    return ENGINE_LABELS.get(eid, ENGINE_LABELS[DEFAULT_ENGINE])


def engine_id(label):
    """id ของป้ายเมนู engine — ป้ายผิดคืน DEFAULT_ENGINE."""
    for k, v in ENGINE_LABELS.items():
        if v == label:
            return k
    return DEFAULT_ENGINE


def next_path(out_dir):
    """คืน path ไฟล์รูปถัดไป (picNNN.png) ในโฟลเดอร์ที่เลือก — ไม่ชนชื่อเดิม."""

    return next_paths(out_dir, 1)[0]


# ไฟล์จำเลขล่าสุดที่จองไป (ข้าง settings.json) — ย้าย/ลบรูปต้นฉบับไปแล้วเลขไม่วนกลับ
# (ย้ายรูปรอบหลังชื่อเลยไม่ซ้ำ) — อยากเริ่มเลขใหม่ลบไฟล์นี้ทิ้งได้
SEQ_FILE = "genjab_seq.json"


def _load_seq():
    """อ่านเลขล่าสุดที่จำไว้ {prefix+ext: เลข} — ไฟล์ไม่มี/พังคืน {} (แล้วตั้งต้นจากไฟล์จริง)."""
    try:
        with open(SEQ_FILE, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(d, dict):
        return {}
    out = {}
    for k, v in d.items():
        if not isinstance(k, str):
            continue
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if n >= 0:
            out[k] = n
    return out


def _save_seq(d):
    try:
        with open(SEQ_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f)
    except OSError:
        pass


def _seq_seed(prefix, ext, taken):
    """เลขมากสุดในไฟล์ที่มีอยู่ (picNNN) — ใช้ตั้งต้นตัวนับครั้งแรก/ตอนไฟล์จำหาย."""
    best = 0
    for name in taken:
        if not name.startswith(prefix) or not name.endswith(ext):
            continue
        mid = name[len(prefix):len(name) - len(ext)] if ext else name[len(prefix):]
        try:
            n = int(mid)
        except ValueError:
            continue
        best = max(best, n)
    return best


def next_paths(out_dir, n, prefix="pic", ext=".png"):
    """จองชื่อไฟล์ทีเดียว n ชื่อ (picNNN.. / vidNNN..) — เลขเดินหน้าอย่างเดียวไม่วนกลับ
    (จำเลขล่าสุดใน genjab_seq.json — ย้าย/ลบรูปไปแล้วชื่อรอบหลังไม่ซ้ำ)
    + กันนับซ้ำตอนโฟลเดอร์เน็ตเวิร์กเห็นไฟล์ช้า."""
    try:
        taken = {f for f in os.listdir(out_dir) if f.endswith(ext)}
    except OSError:
        taken = set()
    key = prefix + ext
    seq = _load_seq()
    start = seq.get(key)
    if start is None:
        start = _seq_seed(prefix, ext, taken)
    paths, i = [], start + 1
    while len(paths) < n:
        name = f"{prefix}{i:03d}{ext}"
        if name not in taken:
            paths.append(os.path.join(out_dir, name))
            taken.add(name)
        i += 1
    if paths:
        seq[key] = max(seq.get(key, 0), i - 1)
        _save_seq(seq)
    return paths


DEFAULT_PROMPT = "a cute robot holding a red umbrella, digital art"


def default_settings():
    """ค่าเริ่มต้นทั้งหมด — ใช้ตอนยังไม่เคยจำ + เป็นฐานเวลาอ่านไฟล์."""
    return {"prompt": DEFAULT_PROMPT, "negative": "", "model": "sd-turbo",
            "size": "512", "ratio": "1:1", "count": "1", "lora": "(ไม่ใช้)",
            "lora_strength": 1.0, "steps": 4, "cfg": 1.0, "seed": "",
            "out_dir": "", "mode": MODE_TXT, "init_img": "",
            "style": NO_STYLE, "strength": 0.6,
            "keep_face": False, "face_strength": 0.6, "upscaler": "", "extend_secs": "1",
            "engine": DEFAULT_ENGINE, "keep_model": True, "translate_local": True}


def load_settings():
    """อ่าน settings ที่จำไว้ทั้งชุด — คีย์ไหนหาย/ไฟล์พังใช้ default ข้อนั้น."""
    d = default_settings()
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return d
    if isinstance(saved, dict):
        for k in d:
            if k in saved:
                d[k] = saved[k]
    return d


def save_settings(d):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _num(v, default, lo, hi):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f:  # NaN
        return default
    return min(hi, max(lo, f))


def normalize_settings(d):
    """ตรวจชนิด/ช่วงรายข้อ — ค่าพังกลับไปใช้ default ข้อนั้น (ไม่ทิ้งทั้งชุด)."""
    base = default_settings()
    if not isinstance(d, dict):
        return base
    s = dict(base)
    if "prompt" in d:
        s["prompt"] = str(d["prompt"])
    if "negative" in d:
        s["negative"] = str(d["negative"])
    mid = d.get("model", "")
    s["model"] = mid if mid in MODEL_IDS.values() else "sd-turbo"
    sizes = MODEL_SIZES[s["model"]]
    s["size"] = str(d.get("size", "")) if str(d.get("size", "")) in sizes else "512"
    s["ratio"] = d.get("ratio", "") if d.get("ratio", "") in RATIOS else "1:1"
    s["count"] = d.get("count", "") if d.get("count", "") in ("1", "2", "4") else "1"
    if "lora" in d:
        s["lora"] = str(d["lora"])
    s["lora_strength"] = _num(d.get("lora_strength"), 1.0, 0.1, 2.0)
    s["steps"] = int(_num(d.get("steps"), 4, 1, 30))
    s["cfg"] = _num(d.get("cfg"), 1.0, 1.0, 7.0)
    if "seed" in d:
        s["seed"] = str(d["seed"])
    if "out_dir" in d:
        s["out_dir"] = str(d["out_dir"])
    s["mode"] = d.get("mode", "") if d.get("mode", "") in (MODE_TXT, MODE_CONVERT) else MODE_TXT
    if "init_img" in d:
        s["init_img"] = str(d["init_img"])
    st = d.get("style", "")
    s["style"] = st if st in ([NO_STYLE] + list(STYLE_PRESETS)) else NO_STYLE
    s["strength"] = _num(d.get("strength"), 0.6, 0.05, 0.95)
    s["keep_face"] = d.get("keep_face", False) is True
    s["face_strength"] = _num(d.get("face_strength"), 0.6, 0.05, 1.0)
    if "upscaler" in d:
        s["upscaler"] = str(d["upscaler"])
    s["extend_secs"] = str(d.get("extend_secs", "")) if str(d.get("extend_secs", "")) in EXTEND_DURATIONS else "1"
    s["engine"] = d.get("engine", "") if d.get("engine", "") in ENGINES else DEFAULT_ENGINE
    s["keep_model"] = d.get("keep_model", True) is not False
    s["translate_local"] = d.get("translate_local", True) is not False
    return s


def next_vid_path(out_dir):
    """คืน path ไฟล์วิดีโอถัดไป (vidNNN.webm) ในโฟลเดอร์ที่เลือก — ไม่ชนชื่อเดิม."""
    return next_vid_paths(out_dir, 1)[0]


def next_vid_paths(out_dir, n):
    """จองชื่อไฟล์วิดีโอทีเดียว n ชื่อ (vidNNN.webm)."""
    return next_paths(out_dir, n, "vid", ".webm")


def unique_path(dest_dir, name):
    """คืน path ใน dest_dir ที่ยังไม่มีไฟล์ — ชื่อชนเติม _2, _3..."""
    base, ext = os.path.splitext(name)
    dest = os.path.join(dest_dir, name)
    i = 2
    while os.path.exists(dest):
        dest = os.path.join(dest_dir, f"{base}_{i}{ext}")
        i += 1
    return dest


def copy_to_flow(src_path, out_dir):
    """ก๊อปรูปไปโฟลเดอร์ flow ใต้ out_dir คืน path ปลายทาง — ชื่อชนเติม _2, _3..."""
    if not src_path or not os.path.isfile(src_path):
        raise FileNotFoundError(f"ไม่พบรูปต้นฉบับ: {src_path}")
    dest_dir = os.path.join(out_dir, FLOW_EXPORT_SUBDIR)
    os.makedirs(dest_dir, exist_ok=True)
    dest = unique_path(dest_dir, os.path.basename(src_path))
    shutil.copy2(src_path, dest)
    return dest


def copy_to_kinolocal(src_path, out_dir):
    """ก๊อปรูปไปโฟลเดอร์ kinolocal ใต้ out_dir คืน path ปลายทาง — ชื่อชนเติม _2, _3..."""
    if not src_path or not os.path.isfile(src_path):
        raise FileNotFoundError(f"ไม่พบรูปต้นฉบับ: {src_path}")
    dest_dir = os.path.join(out_dir, KINOLOCAL_EXPORT_SUBDIR)
    os.makedirs(dest_dir, exist_ok=True)
    dest = unique_path(dest_dir, os.path.basename(src_path))
    shutil.copy2(src_path, dest)
    return dest


def load_out_dir():
    """อ่านที่เก็บรูปที่จำไว้ — ค่าที่จำไว้ใช้ได้เอาไปก่อน ไม่งั้นใช้ NAS ถ้าถึงได้ ไม่งั้นใช้ out ในเครื่อง."""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            d = json.load(f).get("out_dir", "")
        if d and os.path.isdir(d):
            return os.path.normpath(d)
    except (OSError, ValueError):
        pass
    if os.path.isdir(NAS_OUT_DIR):
        return os.path.normpath(NAS_OUT_DIR)
    os.makedirs(LOCAL_OUT_DIR, exist_ok=True)
    return LOCAL_OUT_DIR


def save_out_dir(out_dir):
    d = load_settings()
    d["out_dir"] = out_dir
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:


            json.dump(d, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


GALLERY_LIMIT = 40


def load_gallery_thumbs(paths, size=84):
    """เปิด+ย่อรูปทีละไฟล์ คืน [(path, PIL.Image)] — ไม่แตะ Tk รันใน worker thread ได้."""
    thumbs = []
    for path in paths:
        try:
            with Image.open(path) as im:
                thumb = im.convert("RGB")
                thumb.thumbnail((size, size))
                thumbs.append((path, thumb))
        except Exception:  # noqa: BLE001, PERF203
            continue
    return thumbs


def fit_size(img_w, img_h, box_w, box_h):
    """ขนาดย่อรูปลงกล่องโดยคงสัดส่วน — คืน (w, h) อย่างน้อย 1px."""
    scale = min(box_w / img_w, box_h / img_h)
    return (max(1, int(img_w * scale)), max(1, int(img_h * scale)))


def ctk_image_size(img_w, img_h, box_w, box_h, scaling=1.0):
    """ขนาด CTkImage (logical) จากกล่อง physical — หาร scaling ก่อน fit กันรูปใหญ่เกินจอที่สเกล >100%."""
    if not scaling or scaling <= 0:
        scaling = 1.0
    return fit_size(img_w, img_h, box_w / scaling, box_h / scaling)


META_KEY = "genjab"
# ค่าที่ไม่ฝังในรูป — ที่เก็บรูป/จำนวนรูป/ตัวขยายรูปเป็นเรื่องของเครื่อง/รอบนั้น ไม่ใช่ของรูป
META_SKIP = ("out_dir", "count", "upscaler", "extend_secs", "keep_model", "translate_local")


def gen_params(settings, seed, **extra):
    """ค่าที่ใช้เจนรูปนี้จริง (ฝังลง PNG) — seed รายรูป + extra เช่น upscaled_from."""
    p = {k: v for k, v in settings.items() if k not in META_SKIP}
    p["seed"] = str(seed)
    p.update(extra)
    return p


def _a1111_text(p, size):
    """บรรทัด parameters แบบ A1111 — โปรแกรมอื่น (เช่น civitai) อ่านพรอมจากรูปได้."""
    lines = [p.get("prompt", "")]
    if p.get("negative"):
        lines.append(f"Negative prompt: {p['negative']}")
    lines.append(f"Steps: {p.get('steps')}, CFG scale: {p.get('cfg')}, Seed: {p.get('seed')}, "
                 f"Size: {size[0]}x{size[1]}, Model: {p.get('model')}")
    return "\n".join(lines)


def save_png(img, path, params=None):
    """เซฟรูป PNG พร้อมฝังค่าที่ใช้เจน (คีย์ genjab = JSON + parameters แบบ A1111)."""
    info = None
    if params:
        info = PngInfo()
        info.add_text(META_KEY, json.dumps(params, ensure_ascii=False))
        info.add_text("parameters", _a1111_text(params, img.size))
    img.save(path, pnginfo=info)


def read_params(path):
    """อ่านค่าที่ฝังในรูป คืน dict — รูปไม่มี/อ่านไม่ได้คืน None."""
    try:
        with Image.open(path) as im:
            raw = (getattr(im, "text", None) or im.info).get(META_KEY)
    except Exception:  # noqa: BLE001
        return None
    if not raw:
        return None
    try:
        d = json.loads(raw)
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def params_to_settings(params, current):
    """เอาค่าจากรูปทับค่าปัจจุบัน แล้วตรวจช่วงด้วย normalize_settings — คีย์ใน META_SKIP คงค่าปัจจุบัน."""
    s = dict(current)
    for k in default_settings():
        if k in params and k not in META_SKIP:
            s[k] = params[k]
    return normalize_settings(s)
