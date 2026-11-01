"""ส่วนที่ไม่ใช่หน้าต่างของ GenJab Cloud — จำค่า เซฟรูป ฝังค่าใน PNG (เทสได้ไม่ต้องเปิด GUI)."""
import io
import json
import os

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from cloud_providers import PROVIDERS, RATIOS

OUT_DIR = "cloud_out"
SETTINGS_FILE = "cloud_settings.json"
META_KEY = "genjab_cloud"
DEFAULT_PROMPT = "a cute robot holding a red umbrella in a rainy Bangkok street, digital art"


def default_settings():
    return {"provider": "pollinations", "model": PROVIDERS["pollinations"]["models"][0],
            "prompt": DEFAULT_PROMPT, "negative": "", "ratio": "1:1", "count": 1, "seed": "-1",
            "out_dir": OUT_DIR, "keys": {}}


def normalize_settings(d):
    s = default_settings()
    if not isinstance(d, dict):
        return s
    if d.get("provider") in PROVIDERS:
        s["provider"] = d["provider"]
        s["model"] = PROVIDERS[s["provider"]]["models"][0]
    for k in ("model", "prompt", "negative", "out_dir"):
        if isinstance(d.get(k), str) and (d[k].strip() or k == "negative"):
            s[k] = d[k]
    if d.get("ratio") in RATIOS:
        s["ratio"] = d["ratio"]
    try:
        s["count"] = max(1, min(4, int(d.get("count", 1))))
    except (TypeError, ValueError):
        pass
    try:
        s["seed"] = str(int(d.get("seed", -1)))
    except (TypeError, ValueError):
        pass
    if isinstance(d.get("keys"), dict):
        s["keys"] = {p: v for p, v in d["keys"].items() if p in PROVIDERS and isinstance(v, str) and v}
    return s


def load_settings(path=SETTINGS_FILE):
    try:
        with open(path, encoding="utf-8") as f:
            return normalize_settings(json.load(f))
    except (OSError, ValueError):
        return default_settings()


def save_settings(d, path=SETTINGS_FILE):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(normalize_settings(d), f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def next_paths(out_dir, n):
    """จองชื่อไฟล์ cloudNNN.png ทีเดียว n ชื่อ ไม่ชนของเดิม."""
    try:
        taken = set(os.listdir(out_dir))
    except OSError:
        taken = set()
    paths, i = [], 1
    while len(paths) < n:
        name = f"cloud{i:03d}.png"
        if name not in taken:
            paths.append(os.path.join(out_dir, name))
            taken.add(name)
        i += 1
    return paths


def save_images(blobs, out_dir, params):
    """แปลง bytes รูปจากคลาวด์เป็น PNG + ฝังค่าที่ใช้เจน คืน list path."""
    os.makedirs(out_dir, exist_ok=True)
    paths = next_paths(out_dir, len(blobs))
    for i, (blob, path) in enumerate(zip(blobs, paths)):
        with Image.open(io.BytesIO(blob)) as im:
            img = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
        p = dict(params, index=i)
        info = PngInfo()
        info.add_text(META_KEY, json.dumps(p, ensure_ascii=False))
        lines = [p.get("prompt", "")]
        if p.get("negative"):
            lines.append(f"Negative prompt: {p['negative']}")
        lines.append(f"Seed: {p.get('seed')}, Size: {img.width}x{img.height}, "
                     f"Model: {p.get('provider')}/{p.get('model')}")
        info.add_text("parameters", "\n".join(lines))
        img.save(path, pnginfo=info)
    return paths


def read_params(path):
    try:
        with Image.open(path) as im:
            raw = (getattr(im, "text", None) or im.info).get(META_KEY)
        d = json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001
        return None
    return d if isinstance(d, dict) else None


def gallery_paths(out_dir, limit=40):
    """รูปล่าสุดก่อน."""
    try:
        files = [os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.lower().endswith(".png")]
    except OSError:
        return []
    files.sort(key=lambda p: (os.path.getmtime(p), p), reverse=True)
    return files[:limit]
