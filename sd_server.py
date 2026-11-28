"""โหลดโมเดลค้างไว้ด้วย sd-server.exe (มากับ sd.cpp/Amuse 4.0) — เจนรูปถัดไปไม่ต้องโหลดโมเดลใหม่.

ใช้ API แบบ A1111 (/sdapi/v1/txt2img, /sdapi/v1/img2img) — ได้รูปตรงกับ sd-cli ทุกพิกเซล
ถ้าส่ง prompt แบบเดียวกับที่ sd-cli เห็น (ตัดแท็ก <lora:...> ออก เว้นวรรคเดิมไว้) แล้วส่ง LoRA
เป็นฟิลด์ "lora" แทน (server ไม่อ่านแท็กใน prompt).

server หนึ่งตัวต่อ (exe + argv โมเดล) — เปลี่ยนโมเดล/engine/โฟลเดอร์ LoRA = ปิดตัวเก่าเปิดใหม่;
ไม่ได้ใช้นาน IDLE_SECS ปิดเองคืน VRAM; ยกเลิกระหว่างเจน = ฆ่า server (บิลด์ 1106 ไม่มี /interrupt).
"""
import atexit
import base64
import io
import json
import os
import re
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request

IDLE_SECS = 600  # ไม่ได้เจน 10 นาที ปิด server คืน VRAM/RAM
START_TIMEOUT = 120  # server ต้องตอบภายในนี้ (โหลดโมเดลจริงตอนรับงานแรก ไม่ใช่ตอนเปิด)
REQUEST_TIMEOUT = 3600  # โมเดลใหญ่ (Qwen/FLUX) เจนรูปเดียวหลายนาที
LORA_TAG = re.compile(r"<lora:[^>]*>")


class ServerCancelled(Exception):
    """ผู้ใช้กดยกเลิกระหว่างรอ server — ผู้เรียกแปลงเป็น GenerationCancelled."""


def server_exe_for(cli):
    """sd-server.exe ที่อยู่ข้าง sd-cli ตัวนี้ — ไม่มีคืนสตริงว่าง (ใช้ sd-cli ต่อไป)."""
    if not cli:
        return ""
    p = os.path.join(os.path.dirname(cli), "sd-server.exe")
    return p if os.path.isfile(p) else ""


def split_lora(prompt):
    """แยก prompt แบบ sd-cli ออกเป็น (prompt ที่ตัดแท็กแล้ว, [(ชื่อ, ความแรง)]) —
    ตัดแค่ตัวแท็ก เว้นวรรครอบ ๆ ไว้ตามเดิม (sd-cli ทำแบบนี้ ไม่งั้นรูปไม่ตรง)."""
    loras = []
    for m in LORA_TAG.finditer(prompt):
        body = m.group(0)[len("<lora:"):-1]
        name, _, mult = body.rpartition(":")
        if not name:
            name, mult = body, "1"
        try:
            loras.append((name, float(mult)))
        except ValueError:
            loras.append((body, 1.0))
    return LORA_TAG.sub("", prompt), loras


def lora_field(loras, lora_dir):
    """[(ชื่อ, แรง)] → ฟิลด์ "lora" ของ server (path = ชื่อไฟล์จริงในโฟลเดอร์ LoRA พร้อมนามสกุล)."""
    out = []
    for name, mult in loras:
        fname = name
        if lora_dir:
            for ext in (".safetensors", ".ckpt", ".pt", ".gguf"):
                if os.path.isfile(os.path.join(lora_dir, name + ext)):
                    fname = name + ext
                    break
        out.append({"path": fname, "multiplier": mult})
    return out


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _popen_flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _b64_png(path):
    from PIL import Image
    with Image.open(path) as im:
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


class SdServer:
    """sd-server ตัวเดียวทั้งแอป — ensure() เปิด/ใช้ซ้ำ, generate() ส่งงาน, stop() ปิด."""

    def __init__(self):
        self.lock = threading.RLock()
        self.proc = None
        self.key = None
        self.port = None
        self.log_path = None
        self._idle = None

    # ---------- วงจรชีวิต ----------
    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        """ปิด server (ถ้ามี) — เรียกซ้ำได้, เรียกก่อนรัน sd-cli ทุกครั้งเพื่อคืน VRAM."""
        with self.lock:
            if self._idle is not None:
                self._idle.cancel()
                self._idle = None
            proc, self.proc, self.key, self.port = self.proc, None, None, None
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
                proc.wait(timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass

    def _arm_idle(self):
        if self._idle is not None:
            self._idle.cancel()
        self._idle = threading.Timer(IDLE_SECS, self.stop)
        self._idle.daemon = True
        self._idle.start()

    def ensure(self, exe, ctx_args, cancel_event=None):
        """เปิด server สำหรับ (exe, argv โมเดล) — ตัวเดิมยังรันอยู่ใช้ซ้ำ คืน base URL."""
        key = (os.path.normcase(os.path.abspath(exe)), tuple(ctx_args))
        with self.lock:
            if self.alive() and self.key == key:
                return f"http://127.0.0.1:{self.port}"
        self.stop()
        port = _free_port()
        log = os.path.join(tempfile.gettempdir(), "genjab-sd-server.log")
        kw = {}
        if _popen_flags():
            kw["creationflags"] = _popen_flags()
        with open(log, "w", encoding="utf-8", errors="replace") as fh:
            proc = subprocess.Popen([exe] + list(ctx_args) + ["--listen-port", str(port)],
                                    stdout=fh, stderr=subprocess.STDOUT, **kw)
        with self.lock:
            self.proc, self.key, self.port, self.log_path = proc, key, port, log
        url = f"http://127.0.0.1:{port}"
        t0 = time.time()
        while True:
            if cancel_event is not None and cancel_event.is_set():
                self.stop()
                raise ServerCancelled()
            if proc.poll() is not None:
                self.stop()
                raise RuntimeError(f"sd-server เปิดไม่ขึ้น:\n{self.tail_log()}")
            try:
                urllib.request.urlopen(url + "/sdapi/v1/options", timeout=2).read()
                return url
            except (urllib.error.URLError, OSError):
                pass
            if time.time() - t0 > START_TIMEOUT:
                self.stop()
                raise RuntimeError(f"sd-server ไม่ตอบภายใน {START_TIMEOUT} วิ:\n{self.tail_log()}")
            time.sleep(0.3)

    def tail_log(self, n=800):
        try:
            with open(self.log_path, encoding="utf-8", errors="replace") as f:
                return f.read()[-n:]
        except (OSError, TypeError):
            return ""

    # ---------- ส่งงาน ----------
    def _post(self, url, body, cancel_event):
        """POST แบบยกเลิกได้ — ส่งในเธรดแยก กดยกเลิกแล้วฆ่า server ให้ request หลุดเอง."""
        box = {}

        def go():
            try:
                req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                             headers={"Content-Type": "application/json"})
                box["out"] = json.loads(urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT).read())
            except urllib.error.HTTPError as e:
                box["err"] = RuntimeError(f"sd-server ตอบ {e.code}: "
                                          f"{e.read().decode('utf-8', 'replace')[:400]}")
            except Exception as e:  # noqa: BLE001
                box["err"] = e

        t = threading.Thread(target=go, daemon=True)
        t.start()
        while t.is_alive():
            if cancel_event is not None and cancel_event.wait(0.1):
                self.stop()
                t.join(15)
                raise ServerCancelled()
            if cancel_event is None:
                t.join(0.1)
        if "err" in box:
            if not self.alive():
                err = RuntimeError(f"sd-server ล้มระหว่างเจน:\n{self.tail_log()}")
                self.stop()
                raise err
            raise box["err"]
        return box["out"]

    def generate(self, exe, ctx_args, body, init_path=None, mask_path=None, cancel_event=None):
        """เจนผ่าน server คืน [PIL Image] — init_path = img2img (+ mask_path = inpaint)."""
        from PIL import Image
        url = self.ensure(exe, ctx_args, cancel_event)
        with self.lock:
            if self._idle is not None:
                self._idle.cancel()
                self._idle = None
        body = dict(body)
        route = "/sdapi/v1/txt2img"
        if init_path:
            route = "/sdapi/v1/img2img"
            body["init_images"] = [_b64_png(init_path)]
            if mask_path:
                body["mask"] = _b64_png(mask_path)
        try:
            out = self._post(url + route, body, cancel_event)
        finally:
            with self.lock:
                if self.alive():
                    self._arm_idle()
        imgs = []
        for b in out.get("images", []):
            imgs.append(Image.open(io.BytesIO(base64.b64decode(b))).convert("RGB"))
        if not imgs:
            raise RuntimeError(f"sd-server ไม่ส่งรูปกลับมา:\n{self.tail_log()}")
        return imgs


SERVER = SdServer()
atexit.register(SERVER.stop)
