"""ส่วนที่ไม่ใช่หน้าต่างของ GenJab — ค่าคงที่ เมนูโมเดล การจำค่า ชื่อไฟล์ แกลเลอรี.

แยกจาก app.py ให้เทส/แก้ได้โดยไม่ต้องเปิด GUI — app.py import ชื่อพวกนี้กลับไปใช้ต่อ."""
import json
import os
import shutil

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from generate import CUSTOM_SDXL_PREFIX, NO_STYLE, RATIOS, STYLE_PRESETS, list_sdxl_checkpoints

OUT_DIR = "out"
SETTINGS_FILE = "settings.json"
FLOW_URL = "https://flow.google.com"
FLOW_EXPORT_SUBDIR = "flow"
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
             "FLUX.2 Klein 4B (1024px \เร็ว)": "flux2-klein",
             "Wan2.2 5B (วิดีโอ)": "wan22-5b",
             "MiniMax-H3 (วิดีโอ ช้ามาก)": "minimax-h3",
             "Flux.1 Dev (1024px + LoRA)": "flux1-dev"}
MODEL_SIZES = {"sd-turbo": ["256", "512", "768", "1024"],
               "anima-turbo": ["256", "512", "768", "1024", "1344"],
               "sdxl-turbo": ["512", "768", "1024"],
               "sdxl-base": ["512", "768", "1024"],
               "anima-base": ["256", "512", "768", "1024"],
               "anima-aesthetic": ["256", "512", "768", "1024"],
               "qwen21": ["512", "768", "1024"],
               "qwen21-turbo": ["512", "768", "1024"],
               "iris-3b": ["512", "768", "1024", "1344"],
               "flux2-klein": ["512", "768", "1024"],
               "wan22-5b": ["256", "480", "704", "1280"],
               "minimax-h3": ["256", "480", "864"],
               "flux1-dev": ["512", "768", "1024"]}


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
    "flux2-klein": {"steps": 4, "size": "1024", "cfg": 1.0},
    "wan22-5b": {"steps": 30, "size": "704", "cfg": 5.0,
                 "ratio": "16:9", "frames": "17", "fps": "24"},
    "minimax-h3": {"steps": 20, "size": "480", "cfg": 1.0,
                   "ratio": "16:9", "frames": "17", "fps": "24"},
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


def next_path(out_dir):
    """คืน path ไฟล์รูปถัดไป (picNNN.png) ในโฟลเดอร์ที่เลือก — ไม่ชนชื่อเดิม."""

    return next_paths(out_dir, 1)[0]


def next_paths(out_dir, n, prefix="pic", ext=".png"):
    """จองชื่อไฟล์ทีเดียว n ชื่อ (picNNN.. / vidNNN..) — กันนับซ้ำตอนโฟลเดอร์เน็ตเวิร์กเห็นไฟล์ช้า."""
    try:
        taken = {f for f in os.listdir(out_dir) if f.endswith(ext)}
    except OSError:
        taken = set()
    paths, i = [], 1
    while len(paths) < n:
        name = f"{prefix}{i:03d}{ext}"
        if name not in taken:
            paths.append(os.path.join(out_dir, name))
            taken.add(name)
        i += 1
    return paths


DEFAULT_PROMPT = "a cute robot holding a red umbrella, digital art"


def default_settings():
    """ค่าเริ่มต้นทั้งหมด — ใช้ตอนยังไม่เคยจำ + เป็นฐานเวลาอ่านไฟล์."""
    return {"prompt": DEFAULT_PROMPT, "negative": "", "model": "sd-turbo",
            "size": "512", "ratio": "1:1", "count": "1", "lora": "(ไม่ใช้)",
            "lora_strength": 1.0, "steps": 4, "cfg": 1.0, "seed": "",
            "out_dir": "", "mode": MODE_TXT, "init_img": "",
            "style": NO_STYLE, "strength": 0.6,
            "keep_face": False, "face_strength": 0.6, "upscaler": "", "extend_secs": "1"}


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


def load_out_dir():
    """อ่านที่เก็บรูปที่จำไว้ — ไฟล์หาย/พัง หรือโฟลเดอร์ไม่อยู่แล้ว กลับไปใช้ out."""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            d = json.load(f).get("out_dir", "")
        if d and os.path.isdir(d):
            return os.path.normpath(d)
    except (OSError, ValueError):
        pass
    return OUT_DIR


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
META_SKIP = ("out_dir", "count", "upscaler", "extend_secs")


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
