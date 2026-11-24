"""คุยกับ ComfyUI Server ผ่าน HTTP API — ใช้ urllib ล้วน ไม่ต้องลงไลบรารีเพิ่ม.

เอนจินที่สองของ GenJab (คู่กับ sd-cli ใน generate.py): ส่ง workflow แบบ
API format ด้วย POST /prompt, รอผลด้วยการ poll GET /history/{prompt_id},
ดึงรูปด้วย GET /view, ยกเลิกด้วย POST /interrupt.
ที่อยู่ server ผ่าน env GENJAB_COMFY_URL (ค่าเริ่ม http://127.0.0.1:8188).

ConnectionError จาก urllib ถูกแปลงเป็น ComfyError ภาษาไทยทั้งหมดแล้ว
ฝั่งเรียกไม่ต้องแยกชนิด exception — เทสได้โดย mock urlopen (ดู test_comfy.py).
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

SERVER_ENV = "GENJAB_COMFY_URL"
DEFAULT_SERVER = "http://127.0.0.1:8188"
POLL_INTERVAL = 0.5
WAIT_TIMEOUT = 900
HTTP_TIMEOUT = 60

# เปิดตรง ไม่ผ่าน proxy ของเครื่อง (localhost/LAN + env CI ที่ตั้ง proxy ดักไว้
# ทำให้ค้างได้ — เจอจริง: HTTP_PROXY ชี้ 127.0.0.1:57816 แล้ว /prompt ค้าง)
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# สตาร์ท ComfyUI ใน WSL อัตโนมัติเมื่อ server หลักไม่ติด (ค่าเริ่มของ GENJAB_COMFY_URL เท่านั้น)
SERVER_START_TIMEOUT = 300
SERVER_START_CMD_ENV = "GENJAB_COMFY_START"
DEFAULT_START_CMD = "cd ~/ComfyUI && ./start-comfy.sh"


def _is_managed_server():
    """URL ใช่ server หลักบนเครื่องนี้ที่ GenJab สตาร์ทเองได้ไหม."""
    from urllib.parse import urlparse
    try:
        h = urlparse(server_url()).hostname or ""
    except ValueError:
        return False
    return h in ("127.0.0.1", "localhost", "::1")


def server_healthy(timeout=10):
    """server ตอบ /system_stats ไหม — ไม่ตอบคืน False (ไม่ raise)."""
    try:
        _http("GET", "/system_stats", timeout=timeout)
    except ComfyError:
        return False
    return True


def ensure_server(timeout=SERVER_START_TIMEOUT, poll=2.0, cancel_event=None):
    """การันตีว่า ComfyUI server พร้อมก่อนยิงงาน — ไม่พร้อมสตาร์ท WSL ให้เอง.

    server หลัก (127.0.0.1:8188) ไม่ติด → รัน start script ใน WSL แบบ detached
    แล้วรอจนตอบ /system_stats. URL อื่น/ไม่มี wsl/หมดเวลา → ComfyError ภาษาไทย."""
    from generate import GenerationCancelled
    if server_healthy(timeout=10):
        return True
    if not _is_managed_server():
        raise ComfyError(
            f"ต่อ ComfyUI ไม่ได้ ({server_url()}) — เปิด server ที่อยู่นี้ก่อน")
    import shutil
    import subprocess
    if shutil.which("wsl") is None:
        raise ComfyError("ต่อ ComfyUI ไม่ได้และไม่มีคำสั่ง wsl — เปิด ComfyUI server เองก่อน")
    cmd = os.environ.get(SERVER_START_CMD_ENV, "").strip() or DEFAULT_START_CMD
    flags = getattr(subprocess, "DETACHED_PROCESS", 0)
    flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        subprocess.Popen(["wsl", "-e", "bash", "-lc", cmd],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    except OSError as e:
        raise ComfyError(f"สั่งสตาร์ท ComfyUI ใน WSL ไม่ได้: {e}") from e
    t0 = time.time()
    while True:
        if cancel_event is not None and cancel_event.is_set():
            raise GenerationCancelled()
        if server_healthy(timeout=10):
            return True
        if time.time() - t0 > timeout:
            raise ComfyError(
                "สั่งสตาร์ท ComfyUI ใน WSL แล้วแต่ server ไม่ติดในเวลาที่กำหนด "
                f"(เปิด WSL แล้วรัน `{cmd}` เองดู error)")
        time.sleep(poll)


def _open(req, timeout):
    return _opener.open(req, timeout=timeout)


class ComfyError(Exception):
    """เจนผ่าน ComfyUI ไม่สำเร็จ — ข้อความเป็นภาษาไทยพร้อมโชว์ผู้ใช้ได้เลย."""


def server_url():
    """ที่อยู่ ComfyUI server — env มาก่อน ไม่มีใช้ค่าเริ่ม (ตัด / ท้าย)."""
    return os.environ.get(SERVER_ENV, "").strip().rstrip("/") or DEFAULT_SERVER


def _http(method, path, obj=None, timeout=HTTP_TIMEOUT, raw=None, content_type=None):
    """ยิง HTTP คืน bytes — แปลงข้อผิดพลาดเน็ตเป็น ComfyError ภาษาไทย."""
    data = None
    headers = {}
    if raw is not None:
        data, headers = raw, {"Content-Type": content_type or "application/octet-stream"}
    elif obj is not None:
        data = json.dumps(obj).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(server_url() + path, data=data,
                                 headers=headers, method=method)
    try:
        with _open(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", "replace")
        raise ComfyError(f"ComfyUI ตอบ HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise ComfyError(
            f"ต่อ ComfyUI ไม่ได้ ({server_url()}) — เปิด server ก่อน "
            f"หรือตั้ง {SERVER_ENV} ให้ตรง (สาเหตุ: {e.reason})") from e
    except TimeoutError as e:
        raise ComfyError("ComfyUI ไม่ตอบในเวลาที่กำหนด ลองใหม่อีกที") from e


def system_stats(timeout=30):
    """คืน dict จาก GET /system_stats (มี devices/vram) — ใช้เช็กว่า server เปิดอยู่."""
    try:
        return json.loads(_http("GET", "/system_stats", timeout=timeout))
    except ValueError as e:
        raise ComfyError("ComfyUI ตอบกลับไม่ใช่ JSON") from e


def list_models(folder, timeout=30):
    """ชื่อไฟล์โมเดลในโฟลเดอร์ของ ComfyUI (เช่น checkpoints, loras)."""
    try:
        return json.loads(_http("GET", "/models/" + folder, timeout=timeout))
    except ValueError as e:
        raise ComfyError("ComfyUI ตอบกลับไม่ใช่ JSON") from e


def queue_prompt(workflow, timeout=HTTP_TIMEOUT):
    """ส่ง workflow (API format) เข้าคิว คืน prompt_id — validation ไม่ผ่าน raise ทันที."""
    try:
        r = json.loads(_http("POST", "/prompt", {"prompt": workflow}, timeout=timeout))
    except ValueError as e:
        raise ComfyError("ComfyUI ตอบกลับไม่ใช่ JSON") from e
    if not isinstance(r, dict) or "prompt_id" not in r:
        detail = ""
        if isinstance(r, dict):
            if r.get("error"):
                detail = str(r["error"])[:300]
            elif r.get("node_errors"):
                bad = ", ".join(sorted(r["node_errors"])[:5])
                detail = f"โหนดมีปัญหา: {bad}"
        raise ComfyError("ComfyUI ไม่รับ workflow" + (f": {detail}" if detail else ""))
    return r["prompt_id"]


def wait_result(prompt_id, timeout=WAIT_TIMEOUT, poll=POLL_INTERVAL, cancel_event=None):
    """poll /history จนมี outputs คืน dict outputs — cancel_event ถูก set ส่ง /interrupt แล้ว raise."""
    from generate import GenerationCancelled
    t0 = time.time()
    while True:
        if cancel_event is not None and cancel_event.is_set():
            try:
                _http("POST", "/interrupt", {"prompt_id": prompt_id}, timeout=10)
            except ComfyError:
                pass
            raise GenerationCancelled()
        try:
            h = json.loads(_http("GET", "/history/" + prompt_id, timeout=HTTP_TIMEOUT))
        except ComfyError:
            if time.time() - t0 > timeout:
                raise
            time.sleep(poll)
            continue
        if not isinstance(h, dict):
            raise ComfyError("ComfyUI ตอบ history กลับมาผิดรูปแบบ")
        item = h.get(prompt_id, {})
        if item.get("status", {}).get("status_str") == "error":
            msgs = []
            for v in (item.get("status", {}).get("messages") or [])[:3]:
                msgs.append(str(v[1])[:200] if isinstance(v, (list, tuple)) and len(v) > 1 else str(v)[:200])
            raise ComfyError("ComfyUI เจนล้มเหลว" + (": " + "; ".join(msgs) if msgs else ""))
        if item.get("outputs"):
            return item["outputs"]
        if time.time() - t0 > timeout:
            raise ComfyError(f"รอ ComfyUI เกิน {int(timeout)} วิ — server อาจค้างคิว ลองใหม่")
        time.sleep(poll)


def fetch_images(outputs, timeout=120):
    """ดึงไฟล์รูปทุกใบจาก outputs ของ history คืน list ของ bytes."""
    blobs = []
    for node in (outputs or {}).values():
        for im in (node or {}).get("images", []):
            q = urllib.parse.urlencode({"filename": im.get("filename", ""),
                                        "subfolder": im.get("subfolder", ""),
                                        "type": im.get("type", "output")})
            try:
                with _open(urllib.request.Request(server_url() + "/view?" + q),
                           timeout=timeout) as r:
                    data = r.read()
            except (urllib.error.URLError, TimeoutError) as e:
                raise ComfyError(f"ดึงรูปจาก ComfyUI ไม่ได้: {e}") from e
            if data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff":
                blobs.append(data)
            else:
                raise ComfyError("ComfyUI ส่งไฟล์ที่ไม่ใช่รูปกลับมา")
    if not blobs:
        raise ComfyError("ComfyUI เจนเสร็จแต่ไม่มีรูปออกมา")
    return blobs


# ---------------- workflow template + mapping ----------------

WORKFLOW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "comfy_workflows")

# ชื่อฝั่ง GenJab → ไฟล์ checkpoint บน ComfyUI server (เฟสแรก: เฉพาะตระกูล checkpoint)
COMFY_CKPTS = {
    "juggernaut-xl": "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
    "illustrious-xl-v1": "Illustrious-XL-v1.0.safetensors",
    "illustrious-xl-v0": "Illustrious-XL-v0.1.safetensors",
    "noobai-xl": "NoobAI-XL-Vpred-v1.0.safetensors",
    "sd35-large": "sd3.5_large.safetensors",
    "sd15": "v1-5-pruned-emaonly.safetensors",
}
DEFAULT_CKPT = "juggernaut-xl"

LORA_NODE = "10"

# LoRA ฝั่ง GenJab (stem ไม่มีนามสกุล) → ไฟล์บน ComfyUI server.
# เงื่อนไข: tensor ต้องตรงสถาปัตย์ checkpoint — เฟสนี้มีเฉพาะ SDXL ที่ใช้ได้จริง
# (flux-*/anima-* อยู่บน server หรือเครื่องนี้แต่คนละสถาปัตย์ จึงไม่ใส่ตาราง)
COMFY_LORAS = {
    "ganjad-style-sdxl": "ganjad-style-sdxl.safetensors",
    "ganjad-style-sdxl-000002": "ganjad-style-sdxl-000002.safetensors",
    "ganjad-style-sdxl-000004": "ganjad-style-sdxl-000004.safetensors",
}
# ไฟล์บน server อย่างเดียว (ไม่มีใน loras/ ฝั่งนี้) แต่ใช้กับ SDXL ได้ — ระบุชื่อไฟล์ตรง ๆ
COMFY_LORA_SERVER_ONLY = ("lcm-lora-sdxl.safetensors",)


def resolve_comfy_lora(lora):
    """ชื่อ LoRA ฝั่ง GenJab → ชื่อไฟล์บน server — คืน None ถ้าใช้กับ ComfyUI เฟสนี้ไม่ได้.

    รับตาราง COMFY_LORAS, ไฟล์ server-only ที่เข้ากัน (lcm-lora ฯลฯ),
    และชื่อไฟล์ตรง ๆ ที่ลงท้าย .safetensors — นอกนั้น (anima-*/flux-*/ชื่อไม่รู้จัก)
    คืน None ให้ฝั่งเรียกปฏิเสธพร้อมข้อความไทย."""
    if not lora or lora == "(ไม่ใช้)":
        return None
    s = str(lora).strip()
    if s in COMFY_LORAS:
        return COMFY_LORAS[s]
    if s in COMFY_LORA_SERVER_ONLY:
        return s
    base = os.path.basename(s)
    if base.lower().endswith(".safetensors"):
        return base
    return None


def check_lora_on_server(server_file, timeout=30):
    """ยืนยันว่า server มีไฟล์ LoRA นี้ — ไม่มี raise พร้อมรายชื่อที่มีให้เลือก."""
    available = list_models("loras", timeout=timeout)
    if server_file in (available or []):
        return True
    hint = ", ".join([f for f in (available or []) if "sdxl" in f.lower()][:8]) or "—"
    raise ComfyError(
        f"บน ComfyUI server ไม่มี LoRA {server_file} "
        f"(ที่มีและใช้กับ SDXL ได้: {hint}) — ก๊อปไฟล์เข้าโฟลเดอร์ models/loras ของ server ก่อน")


# ---------------- Wan 2.2 14B I2V (dual-expert, core nodes ล้วน) ----------------

# ไฟล์โมเดลฝั่ง server — ตรงกับ Comfy-Org/Wan_2.2_ComfyUI_Repackaged
# (14B ใช้ VAE ของ Wan 2.1 + latent 16ch สายเดียวกับ Wan 2.1 I2V,
#  text encoder ไฟล์เดียว type wan รวม umt5+xlm-roberta)
WAN22_I2V_HIGH = "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"
WAN22_I2V_LOW = "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"
WAN22_I2V_UMT5 = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
WAN22_I2V_VAE = "wan_2.1_vae.safetensors"
WAN22_I2V_CLIP_VISION = "clip_vision_h.safetensors"
# lightx2v 4-step LoRA (โหมดเร็วบน 16GB) — มีเมื่อโหลดเพิ่ม ไม่บังคับ
WAN22_I2V_LORA_HIGH = "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"
WAN22_I2V_LORA_LOW = "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"

WAN22_I2V_FILES = {
    "diffusion_models": (WAN22_I2V_HIGH, WAN22_I2V_LOW),
    "text_encoders": (WAN22_I2V_UMT5,),
    "vae": (WAN22_I2V_VAE,),
    "clip_vision": (WAN22_I2V_CLIP_VISION,),
}

WAN22_I2V_HF = ("https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged"
               "/resolve/main/split_files")


def check_wan22_i2v_models(timeout=30):
    """ยืนยันว่า server มีไฟล์ Wan 2.2 14B I2V ครบ — ไม่มี raise พร้อมบอกที่โหลด."""
    missing = []
    for folder, names in WAN22_I2V_FILES.items():
        try:
            have = set(list_models(folder, timeout=timeout) or [])
        except ComfyError:
            raise
        for n in names:
            if n not in have:
                missing.append(f"{folder}/{n}")
    if missing:
        raise ComfyError(
            "บน ComfyUI server ยังไม่มีโมเดล Wan 2.2 14B I2V: "
            + ", ".join(missing)
            + f" — โหลดจาก {WAN22_I2V_HF}/<folder>/<ชื่อไฟล์> "
              "ใส่โฟลเดอร์ models/ ของ server แล้ว restart server")
    return True


def build_wan22_i2v(prompt, negative="", seed=0, steps=20, cfg=6.0,
                    sampler="uni_pc", scheduler="simple", shift=8.0,
                    width=832, height=480, length=49, fps=16,
                    init_image="", split_at=None,
                    lora_high=None, lora_low=None, lora_strength=1.0,
                    prefix="genjab-i2v"):
    """ประกอบ workflow Wan 2.2 14B I2V (API format) — dual-expert 2 ช่วง denoise.

    โหนดหลักล้วน (UNETLoader/CLIPLoader/VAELoader/CLIPVision/CLIPTextEncode/
    LoadImage/WanImageToVideo/KSamplerAdvanced x2/ModelSamplingSD3/VHS VideoCombine).
    latent 16ch สายเดียวกับ Wan 2.1 I2V (ไม่ใช่ Wan22ImageToVideoLatent ของรุ่น 5B).
    split_at = จุดสลับ high→low (เริ่มครึ่งทาง); LoRA ใส่แยกทีละ expert ได้."""
    if not (prompt or "").strip():
        raise ComfyError("พิมพ์คำบรรยายภาพก่อน (บอกด้วยว่าอยากให้อะไรขยับ)")
    if not init_image:
        raise ComfyError("ต้องมีรูปต้นฉบับ")
    try:
        steps = int(steps)
        w, h, length = int(width), int(height), int(length)
        fps = int(fps)
    except (TypeError, ValueError):
        raise ComfyError(f"ขนาด/เฟรมต้องเป็นตัวเลข (ได้ {width}x{height} {length}f @{fps}fps)")
    if w <= 0 or h <= 0 or w % 16 or h % 16:
        raise ComfyError(f"width/height ต้อง > 0 และลงตัวกับ 16 (ได้ {w}x{h})")
    if length < 1:
        raise ComfyError(f"length ต้อง >= 1 (ได้ {length})")
    if fps < 1:
        raise ComfyError(f"fps ต้อง >= 1 (ได้ {fps})")
    if steps < 2:
        raise ComfyError(f"steps ต้อง >= 2 สำหรับ dual-expert (ได้ {steps})")
    split = steps // 2 if split_at is None else int(split_at)
    if not 0 < split < steps:
        raise ComfyError(f"split_at ต้องอยู่ระหว่าง 0..steps (ได้ {split}/{steps})")
    try:
        seed = int(seed)
        cfg = float(cfg)
        shift = float(shift)
    except (TypeError, ValueError):
        raise ComfyError("seed/cfg/shift ต้องเป็นตัวเลข")

    def shifted(unet_id, lora_name):
        mid = unet_id
        if lora_name:
            lid = unet_id + "-lora"
            wf[lid] = {"class_type": "LoraLoaderModelOnly",
                       "inputs": {"model": [unet_id, 0], "lora_name": lora_name,
                                  "strength_model": float(lora_strength)}}
            mid = lid
        sid = unet_id + "-shift"
        wf[sid] = {"class_type": "ModelSamplingSD3",
                   "inputs": {"model": [mid, 0], "shift": shift}}
        return sid

    wf = {
        "10": {"class_type": "UNETLoader",
               "inputs": {"unet_name": WAN22_I2V_HIGH, "weight_dtype": "default"}},
        "13": {"class_type": "UNETLoader",
               "inputs": {"unet_name": WAN22_I2V_LOW, "weight_dtype": "default"}},
        "20": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": WAN22_I2V_UMT5, "type": "wan"}},
        "21": {"class_type": "VAELoader",
               "inputs": {"vae_name": WAN22_I2V_VAE}},
        "22": {"class_type": "CLIPTextEncode",
               "inputs": {"text": prompt, "clip": ["20", 0]}},
        "23": {"class_type": "CLIPTextEncode",
               "inputs": {"text": negative or "", "clip": ["20", 0]}},
        "24": {"class_type": "LoadImage",
               "inputs": {"image": init_image}},
        "26": {"class_type": "CLIPVisionLoader",
               "inputs": {"clip_name": WAN22_I2V_CLIP_VISION}},
        "27": {"class_type": "CLIPVisionEncode",
               "inputs": {"clip_vision": ["26", 0], "image": ["24", 0],
                          "crop": "center"}},
        "25": {"class_type": "WanImageToVideo",
               "inputs": {"positive": ["22", 0], "negative": ["23", 0],
                          "vae": ["21", 0], "width": w, "height": h,
                          "length": length, "batch_size": 1,
                          "clip_vision_output": ["27", 0],
                          "start_image": ["24", 0]}},
    }
    high = shifted("10", lora_high)
    low = shifted("13", lora_low)
    wf["30"] = {"class_type": "KSamplerAdvanced",
                "inputs": {"model": [high, 0], "add_noise": "enable",
                           "noise_seed": seed, "steps": steps, "cfg": cfg,
                           "sampler_name": sampler, "scheduler": scheduler,
                           "positive": ["25", 0], "negative": ["25", 1],
                           "latent_image": ["25", 2],
                           "start_at_step": 0, "end_at_step": split,
                           "return_with_leftover_noise": "enable"}}
    wf["31"] = {"class_type": "KSamplerAdvanced",
                "inputs": {"model": [low, 0], "add_noise": "disable",
                           "noise_seed": seed, "steps": steps, "cfg": cfg,
                           "sampler_name": sampler, "scheduler": scheduler,
                           "positive": ["25", 0], "negative": ["25", 1],
                           "latent_image": ["30", 0],
                           "start_at_step": split, "end_at_step": steps,
                           "return_with_leftover_noise": "disable"}}
    wf["32"] = {"class_type": "VAEDecode",
                "inputs": {"samples": ["31", 0], "vae": ["21", 0]}}
    wf["33"] = {"class_type": "VHS_VideoCombine",
                "inputs": {"images": ["32", 0],
                           "frame_rate": fps, "loop_count": 0,
                           "filename_prefix": prefix or "genjab-i2v",
                           "format": "video/h264-mp4",
                           "pingpong": False, "save_output": True}}
    return wf


def fetch_videos(outputs, timeout=120):
    """ดึงไฟล์วิดีโอทุกไฟล์จาก outputs ของ history คืน list ของ bytes (mp4)."""
    blobs = []
    for node in (outputs or {}).values():
        for v in (node or {}).get("gifs", []):
            q = urllib.parse.urlencode({"filename": v.get("filename", ""),
                                        "subfolder": v.get("subfolder", ""),
                                        "type": v.get("type", "output")})
            try:
                with _open(urllib.request.Request(server_url() + "/view?" + q),
                           timeout=timeout) as r:
                    data = r.read()
            except (urllib.error.URLError, TimeoutError) as e:
                raise ComfyError(f"ดึงวิดีโอจาก ComfyUI ไม่ได้: {e}") from e
            if len(data) > 12 and (data[4:8] == b"ftyp" or data[:3] == b"GIF"
                                   or data[:4] == b"\x1a\x45\xdf\xa3"):
                blobs.append(data)
            else:
                raise ComfyError("ComfyUI ส่งไฟล์ที่ไม่ใช่วิดีโอกลับมา")
    if not blobs:
        raise ComfyError("ComfyUI เจนเสร็จแต่ไม่มีวิดีโอออกมา")
    return blobs


def upload_image(path, timeout=120):
    """อัปโหลดรูปไปโฟลเดอร์ input ของ server คืนชื่อไฟล์บน server (ไว้ใส่ LoadImage)."""
    try:
        with open(path, "rb") as f:
            blob = f.read()
    except OSError as e:
        raise ComfyError(f"อ่านรูป {path} ไม่ได้: {e}") from e
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        ctype, ext = "image/png", ".png"
    elif blob[:3] == b"\xff\xd8\xff":
        ctype, ext = "image/jpeg", ".jpg"
    elif blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        ctype, ext = "image/webp", ".webp"
    else:
        raise ComfyError(f"ไฟล์ {path} ไม่ใช่รูป PNG/JPEG/WebP — แปลงก่อนอัปโหลด")
    import uuid
    boundary = uuid.uuid4().hex
    fname = os.path.splitext(os.path.basename(path))[0][:40] or "genjab"
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\ninput\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{fname}{ext}"\r\n'
        f'Content-Type: {ctype}\r\n\r\n'
    ).encode() + blob + f"\r\n--{boundary}--\r\n".encode()
    try:
        r = json.loads(_http("POST", "/upload/image", raw=body,
                             content_type=f"multipart/form-data; boundary={boundary}",
                             timeout=timeout))
    except ValueError as e:
        raise ComfyError("ComfyUI ตอบกลับไม่ใช่ JSON") from e
    if not isinstance(r, dict) or not r.get("name"):
        raise ComfyError("อัปโหลดรูปไป ComfyUI ไม่สำเร็จ")
    return r["name"]


def load_template(name="sdxl_t2i.json"):
    """อ่าน workflow template (API format) จาก comfy_workflows/."""
    path = os.path.join(WORKFLOW_DIR, name)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise ComfyError(f"อ่าน template {name} ไม่ได้: {e}") from e


def build_txt2img(prompt, negative="", seed=0, steps=8, cfg=2.0, w=512, h=512,
                  ckpt=DEFAULT_CKPT, sampler="euler", scheduler="normal",
                  lora=None, lora_strength=1.0):
    """ประกอบ workflow txt2img จาก template — คืน dict พร้อมส่ง POST /prompt."""
    if not (prompt or "").strip():
        raise ComfyError("พิมพ์คำบรรยายภาพก่อน")
    ckpt_file = COMFY_CKPTS.get(ckpt, COMFY_CKPTS.get(str(ckpt).removeprefix("comfy-"), ckpt))
    if not ckpt_file:
        raise ComfyError(f"ไม่รู้จักโมเดล ComfyUI: {ckpt}")
    wf = load_template()
    for k in list(wf):
        if k == "comment":
            wf.pop(k, None)
    try:
        wf["4"]["inputs"]["ckpt_name"] = ckpt_file
        wf["6"]["inputs"]["text"] = prompt
        wf["7"]["inputs"]["text"] = negative or ""
        wf["5"]["inputs"]["width"] = int(w)
        wf["5"]["inputs"]["height"] = int(h)
        ks = wf["3"]["inputs"]
        ks.update({"seed": int(seed), "steps": int(steps), "cfg": float(cfg),
                   "sampler_name": sampler, "scheduler": scheduler})
    except (KeyError, TypeError, ValueError) as e:
        raise ComfyError(f"template เสียหาย: {e}") from e
    if lora:
        wf[LORA_NODE] = {"class_type": "LoraLoader",
                         "inputs": {"model": ["4", 0], "clip": ["4", 1],
                                    "lora_name": lora,
                                    "strength_model": float(lora_strength),
                                    "strength_clip": float(lora_strength)}}
        wf["6"]["inputs"]["clip"] = [LORA_NODE, 1]
        ks["model"] = [LORA_NODE, 0]
    return wf


def build_img2img(prompt, negative="", seed=0, steps=8, cfg=2.0,
                  ckpt=DEFAULT_CKPT, sampler="euler", scheduler="normal",
                  lora=None, lora_strength=1.0, init_image="", strength=0.6,
                  mask_image=None):
    """ประกอบ workflow แปลงรูป (img2img/inpaint) — denoise = strength, ขาวในมาสก์ = เจนใหม่.
    ขนาดรูปมาจากไฟล์ที่อัปโหลด (ฝั่งเรียกย่อให้ก่อน) ไม่ต้องส่ง w/h."""
    if not (prompt or "").strip():
        raise ComfyError("พิมพ์คำบรรยายภาพก่อน")
    if not init_image:
        raise ComfyError("ต้องมีรูปต้นฉบับ")
    ckpt_file = COMFY_CKPTS.get(ckpt, COMFY_CKPTS.get(str(ckpt).removeprefix("comfy-"), ckpt))
    if not ckpt_file:
        raise ComfyError(f"ไม่รู้จักโมเดล ComfyUI: {ckpt}")
    wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt_file}},
        "11": {"class_type": "LoadImage", "inputs": {"image": init_image}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": prompt}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": negative or ""}},
        "3": {"class_type": "KSampler",
              "inputs": {"cfg": float(cfg), "denoise": float(strength),
                         "latent_image": ["12", 0], "model": ["4", 0],
                         "negative": ["7", 0], "positive": ["6", 0],
                         "sampler_name": sampler, "scheduler": scheduler,
                         "seed": int(seed), "steps": int(steps)}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": "genjab", "images": ["8", 0]}},
    }
    if mask_image:
        wf["13"] = {"class_type": "LoadImage", "inputs": {"image": mask_image}}
        wf["14"] = {"class_type": "ImageToMask",
                    "inputs": {"image": ["13", 0], "channel": "red"}}
        wf["12"] = {"class_type": "VAEEncodeForInpaint",
                    "inputs": {"pixels": ["11", 0], "vae": ["4", 2],
                               "mask": ["14", 0], "grow_mask_by": 6}}
    else:
        wf["12"] = {"class_type": "VAEEncode",
                    "inputs": {"pixels": ["11", 0], "vae": ["4", 2]}}
    if lora:
        wf[LORA_NODE] = {"class_type": "LoraLoader",
                         "inputs": {"model": ["4", 0], "clip": ["4", 1],
                                    "lora_name": lora,
                                    "strength_model": float(lora_strength),
                                    "strength_clip": float(lora_strength)}}
        wf["6"]["inputs"]["clip"] = [LORA_NODE, 1]
        wf["3"]["inputs"]["model"] = [LORA_NODE, 0]
    return wf
