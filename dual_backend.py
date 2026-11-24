"""Backend คู่ Local/Cloud — logic กลางของจุดเข้าแอปรวม (genjab.py).

ไฟล์นี้ไม่แตะ GUI/เน็ต เทสได้แบบ headless (`python test_dual.py`).
ฝั่ง GUI (ปุ่มสลับใน app.py / cloud_app.py) คุยกับ launcher ผ่าน attribute
`switch_requested` บน window — กดสลับ = True แล้วปิดหน้าต่าง  launcher เห็น
flag ก็เปิดอีกฝั่งต่อแทนที่จะจบโปรแกรม.
"""
import json

LOCAL = "local"
CLOUD = "cloud"
BACKENDS = (LOCAL, CLOUD)
DEFAULT_BACKEND = LOCAL
SETTINGS_FILE = "dual_settings.json"


def other(backend):
    """backend อีกฝั่ง — เอาไว้สลับ Local <-> Cloud."""
    return CLOUD if backend == LOCAL else LOCAL


def parse_argv(argv):
    """อ่าน --local / --cloud (หรือ --backend local/cloud) คืนค่าหรือ None."""
    args = list(argv or [])
    if "--local" in args:
        return LOCAL
    if "--cloud" in args:
        return CLOUD
    for i, a in enumerate(args):
        if a == "--backend" and i + 1 < len(args):
            v = args[i + 1].strip().lower()
            if v in BACKENDS:
                return v
    return None


def load_backend(path=SETTINGS_FILE):
    """backend ที่ใช้ล่าสุด (จำไว้ข้ามรอบเปิด) — อ่านไม่ได้คืนค่าเริ่ม."""
    try:
        with open(path, encoding="utf-8") as f:
            v = json.load(f).get("backend", "")
    except (OSError, ValueError, AttributeError):
        return DEFAULT_BACKEND
    return v if v in BACKENDS else DEFAULT_BACKEND


def save_backend(backend, path=SETTINGS_FILE):
    """จำ backend ที่เลือก — คืน False ถ้าค่าไม่ถูกต้อง/เขียนไม่ได้."""
    if backend not in BACKENDS:
        return False
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"backend": backend}, f, ensure_ascii=False)
    except OSError:
        return False
    return True
