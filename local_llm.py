"""แปล prompt ไทย→อังกฤษในเครื่อง ด้วย llama-server (llama.cpp ที่มากับ Amuse 4.0) — ไม่ต้องใช้เน็ต/คีย์.

โมเดล: env GENJAB_LLM_MODEL ก่อน, ตามด้วย Qwen3-4B-Instruct*.gguf ใน models/ ข้างโปรแกรม,
สุดท้ายไฟล์ .gguf ในโฟลเดอร์ llm ของ Amuse. ตัวรัน: env GENJAB_LLAMA_SERVER หรือของ Amuse.

server เปิดตอนแปลครั้งแรก (~7 วิ) แปลรอบต่อไป < 1 วิ — ปิดเองเมื่อไม่ได้ใช้ IDLE_SECS
และ generate ปิดให้ก่อนเจนรูปทุกครั้ง (คืน VRAM ให้โมเดลรูป). ผลแปลจำไว้รายข้อความ.
"""
import atexit
import glob
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request

from cloud_translate import SYSTEM_PROMPT, has_thai

IDLE_SECS = 300
START_TIMEOUT = 180
AMUSE_LLAMA = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Amuse", "RuntimeLlamaCpp",
                           "vulkan", "llama-server.exe")


def _app_dir():
    import generate
    return generate.app_dir()


def llama_server_exe():
    """llama-server.exe — env GENJAB_LLAMA_SERVER ก่อน แล้วของ Amuse 4.0; ไม่มีคืนสตริงว่าง."""
    env = os.environ.get("GENJAB_LLAMA_SERVER", "")
    if env:
        return env if os.path.isfile(env) else ""
    return AMUSE_LLAMA if os.path.isfile(AMUSE_LLAMA) else ""


def llm_model():
    """ไฟล์ .gguf ที่ใช้แปล — ไม่มีคืนสตริงว่าง."""
    env = os.environ.get("GENJAB_LLM_MODEL", "")
    if env:
        return env if os.path.isfile(env) else ""
    hits = sorted(glob.glob(os.path.join(_app_dir(), "models", "Qwen3-4B-Instruct*.gguf")))
    if hits:
        return hits[0]
    import generate
    for d in [os.path.join(generate.AMUSE_MODELS, "llm")]:
        hits = sorted(glob.glob(os.path.join(d, "**", "*.gguf"), recursive=True))
        hits = [h for h in hits if "mmproj" not in os.path.basename(h).lower()]
        if hits:
            return hits[0]
    return ""


def available():
    """แปลในเครื่องได้ไหม (มีทั้งตัวรันและโมเดล)."""
    return bool(llama_server_exe() and llm_model())


MISSING_HINT = ("แปลในเครื่องต้องมี llama-server ของ Amuse 4.0 + โมเดล "
                "Qwen3-4B-Instruct-2507-Q4_K_M.gguf ใน models/ ข้างโปรแกรม")


def clean(text):
    """ตัดเครื่องหมายคำพูด/หัวข้อที่โมเดลชอบแถมมา."""
    text = (text or "").strip()
    if "</think>" in text:
        text = text.split("</think>", 1)[1].strip()
    text = text.strip().strip('"').strip("“”").strip()
    if text.lower().startswith("english prompt:"):
        text = text[len("english prompt:"):].strip()
    return text


class LlamaServer:
    def __init__(self):
        self.lock = threading.RLock()
        self.proc = None
        self.port = None
        self.key = None
        self._idle = None
        self.cache = {}

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        with self.lock:
            if self._idle is not None:
                self._idle.cancel()
                self._idle = None
            proc, self.proc, self.port, self.key = self.proc, None, None, None
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
                proc.wait(timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass

    def _ensure(self, exe, model):
        key = (exe, model)
        with self.lock:
            if self.alive() and self.key == key:
                return f"http://127.0.0.1:{self.port}"
        self.stop()
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        log = os.path.join(tempfile.gettempdir(), "genjab-llama-server.log")
        kw = {}
        flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if flag:
            kw["creationflags"] = flag
        with open(log, "w", encoding="utf-8", errors="replace") as fh:
            proc = subprocess.Popen([exe, "-m", model, "--port", str(port), "-ngl", "99",
                                     "-c", "2048", "--jinja"],
                                    stdout=fh, stderr=subprocess.STDOUT, **kw)
        with self.lock:
            self.proc, self.port, self.key = proc, port, key
        url = f"http://127.0.0.1:{port}"
        t0 = time.time()
        while True:
            if proc.poll() is not None:
                self.stop()
                raise RuntimeError(f"llama-server เปิดไม่ขึ้น (ดู {log})")
            try:
                r = json.loads(urllib.request.urlopen(url + "/health", timeout=2).read())
                if r.get("status") == "ok":
                    return url
            except (urllib.error.URLError, OSError, ValueError):
                pass
            if time.time() - t0 > START_TIMEOUT:
                self.stop()
                raise RuntimeError(f"llama-server ไม่ตอบภายใน {START_TIMEOUT} วิ (ดู {log})")
            time.sleep(0.3)

    def translate(self, text):
        """ไทย→อังกฤษ — ไม่มีอักษรไทยคืนเดิม (ไม่เปิด server)."""
        text = (text or "").strip()
        if not has_thai(text):
            return text
        if text in self.cache:
            return self.cache[text]
        exe, model = llama_server_exe(), llm_model()
        if not exe or not model:
            raise FileNotFoundError(MISSING_HINT)
        url = self._ensure(exe, model)
        body = {"messages": [{"role": "system", "content": SYSTEM_PROMPT},
                             {"role": "user", "content": text}],
                "temperature": 0, "max_tokens": 300}
        req = urllib.request.Request(url + "/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=300).read())
        finally:
            with self.lock:
                if self.alive():
                    if self._idle is not None:
                        self._idle.cancel()
                    self._idle = threading.Timer(IDLE_SECS, self.stop)
                    self._idle.daemon = True
                    self._idle.start()
        out = clean(((d.get("choices") or [{}])[0].get("message") or {}).get("content", ""))
        if not out:
            raise RuntimeError("โมเดลแปลไม่ได้ส่งคำแปลกลับมา")
        self.cache[text] = out
        return out


LLM = LlamaServer()
atexit.register(LLM.stop)


def translate(text):
    return LLM.translate(text)
