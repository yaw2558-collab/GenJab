"""แปลง Anima ของ Amuse (ชื่อ tensor แบบ `net.*`) ให้ sd-cli อ่านได้
(แบบ `model.diffusion_model.*` เหมือนไฟล์ turbo) — รันครั้งเดียวต่อโมเดล:

    python convert_anima_base.py                 # anima-base (ค่าเริ่ม)
    python convert_anima_base.py anima-lavender  # Anima Light Lavender

ได้ไฟล์ใน `models/` ตาม `ANIMA_CONVERTED` ใน generate.py (ค่า weight เหมือนเดิมทุกบิต)."""
import json
import os
import struct
import sys

from generate import ANIMA_CONVERTED, amuse_path


def paths(model="anima-base"):
    """(SRC, DST) ของโมเดล — id ไม่รู้จัก raise SystemExit บอกตัวที่มี."""
    if model not in ANIMA_CONVERTED:
        raise SystemExit(f"ไม่รู้จัก {model} (มี: {', '.join(ANIMA_CONVERTED)})")
    src, dst = ANIMA_CONVERTED[model]
    return (amuse_path("diffusion", src),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", dst))


def main(model="anima-base"):
    SRC, DST = paths(model)
    if not os.path.isfile(SRC):
        raise SystemExit(f"ไม่พบไฟล์ต้นฉบับที่ {SRC} (ต้องลงโมเดลในแอป Amuse ก่อน)")
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(SRC, "rb") as f:
        hlen = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(hlen))
        fixed = {}
        for k, v in header.items():
            if k == "__metadata__":
                fixed[k] = v
                continue
            assert k.startswith("net."), k
            fixed["model.diffusion_model." + k[4:]] = v
        blob = json.dumps(fixed, separators=(",", ":")).encode()
        with open(DST, "wb") as out:
            out.write(struct.pack("<Q", len(blob)))
            out.write(blob)
            while True:
                chunk = f.read(64 * 1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    print("saved:", DST)


if __name__ == "__main__":
    main(*sys.argv[1:2])
